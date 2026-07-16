"""泰克示波器面板 — MDO3000 风格前面板 + 波形显示 + SCPI 遥控."""
from __future__ import annotations

from typing import Any, Callable

from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...i18n import get_language, tr
from ...logging_setup import logger
from .client import ScopeError, TektronixScopeClient
from .front_panel import TekFrontPanel


def _L(zh: str, en: str) -> str:
    return zh if get_language().startswith('zh') else en

# Live waveform budget (USB + plot)
_LIVE_INTERVAL_MS = 250
_LIVE_XFER_POINTS = 4000
_LIVE_DISPLAY_POINTS = 2000
_MANUAL_XFER_POINTS = 10000
_MANUAL_DISPLAY_POINTS = 4000


class _VisaWorker(QObject):
    """Run blocking VISA calls off the UI thread."""

    finished = pyqtSignal(object)  # result or Exception

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            self.finished.emit(self._fn(*self._args, **self._kwargs))
        except Exception as exc:
            self.finished.emit(exc)


class TektronixScopePanel(QWidget):
    """Embedded tab: MDO3000 front-panel UI controlling a real USB scope."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = TektronixScopeClient()
        self._pix: QPixmap | None = None
        self._thread: QThread | None = None
        self._worker: _VisaWorker | None = None
        self._busy = False
        self._pending_nudge: Callable | None = None
        self._pending_nudge_ok: Callable | None = None
        self._running = False
        self._zoom_on = False
        self._play_on = False
        self._mark_armed = False
        self._multi_mode = 0  # 0: a=trig/b=hpos · 1: a=hscale/b=hpos
        self._live = False
        self._live_skip_log = False
        self._live_frame = 0
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(_LIVE_INTERVAL_MS)
        self._live_timer.timeout.connect(self._on_live_tick)

        self.front = TekFrontPanel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.front)

        # Keep legacy attribute names used by shell/theme
        self.lineEdit = self.front.model_edit
        self.textEdit = self.front.log_edit
        self.label = self.front.preview_label
        self.pushButton_connect = self.front.btn_connect
        self.pushButton_save = self.front.btn_shot
        self.pushButton_save_2 = self.front.btn_shot

        self._wire()
        self.retranslate_ui()
        self.reapply_theme()

    # ── lifecycle ────────────────────────────────────────────────────────

    def retranslate_ui(self) -> None:
        self.front.retranslate_ui()
        if self.front.side_frame.isVisible() and self.front.side_stack.currentIndex() > 0:
            key = getattr(self, '_open_side_menu_key', None)
            if key and key.startswith('ch_'):
                self._show_channel_side_menu(key[3:])
            elif key:
                self._on_menu(key)

    def reapply_theme(self) -> None:
        from ...ui.theme import apply_tektronix_scope_theme
        apply_tektronix_scope_theme(self)

    def release_scopes(self) -> None:
        self._live_timer.stop()
        self._live = False
        self._client.close()

    def _on_live_toggled(self, on: bool) -> None:
        self._live = on
        self.front.wave_plot.set_live_mode(on)
        if on:
            if not self._ensure_connected():
                self.front.btn_live.setChecked(False)
                self._live = False
                return
            self._log(tr('tool.tektronix_scope.live_on', ms=_LIVE_INTERVAL_MS))
            self._live_timer.start()
            self._on_refresh_wave(live=True)
        else:
            self._live_timer.stop()
            self._log(tr('tool.tektronix_scope.live_off'))

    def _on_live_tick(self) -> None:
        if not self._live or not self._client.connected:
            return
        # Yield to knob/control traffic
        if self._busy:
            return
        self._on_refresh_wave(live=True)

    def _invalidate_wfm(self) -> None:
        try:
            self._client.invalidate_waveform_cache(self._index())
        except Exception:
            pass

    # ── wiring ───────────────────────────────────────────────────────────

    def _wire(self) -> None:
        f = self.front
        f.connectClicked.connect(self._on_connect)
        f.refreshWaveClicked.connect(lambda: self._on_refresh_wave(live=False))
        f.liveToggled.connect(self._on_live_toggled)
        f.hardcopyClicked.connect(self._on_hardcopy)
        f.runStopClicked.connect(self._on_run_stop)
        f.singleClicked.connect(self._on_single)
        f.forceTriggerClicked.connect(lambda: self._scpi(self._client.force_trigger))
        f.autosetClicked.connect(self._on_autoset)
        f.defaultSetupClicked.connect(self._on_default_setup)

        f.channelMenuClicked.connect(self._on_channel_menu)
        f.channelScaleRotated.connect(self._on_ch_scale)
        f.channelPositionRotated.connect(self._on_ch_pos)
        f.channelPositionPushed.connect(
            lambda ch: self._scpi(self._client.center_channel_position, ch)
        )

        f.horizScaleRotated.connect(self._on_h_scale)
        f.horizPositionRotated.connect(self._on_h_pos)
        f.horizPositionPushed.connect(lambda: self._scpi(self._client.center_horizontal_position))
        f.triggerLevelRotated.connect(self._on_trig_level)
        f.triggerLevelPushed.connect(lambda: self._scpi(self._client.set_trigger_level_50pct))

        f.menuClicked.connect(self._on_menu)
        f.menuOffClicked.connect(self.front.hide_side_menu)
        f.cursorClicked.connect(self._on_cursor)
        f.wave_plot.measureReadoutChanged.connect(
            lambda s: self._log(s) if s else None
        )
        f.zoomClicked.connect(self._on_zoom)
        f.intensityClicked.connect(lambda: self._on_menu('intensity'))
        f.saveClicked.connect(lambda: self._on_hardcopy(self.front.scope_index.currentIndex()))
        f.digitalClicked.connect(lambda: self._log(tr('tool.tektronix_scope.need_mso')))
        f.markPrevClicked.connect(lambda: self._scpi_write('MARK PREVious'))
        f.markNextClicked.connect(lambda: self._scpi_write('MARK NEXT'))
        f.markSetClearClicked.connect(self._on_mark_set_clear)
        f.playPauseClicked.connect(self._on_play_pause)
        f.fineToggled.connect(lambda on: self._log(tr('tool.tektronix_scope.fine_on' if on else 'tool.tektronix_scope.fine_off')))
        f.multiARotated.connect(lambda d: self._on_multi('a', d))
        f.multiBRotated.connect(lambda d: self._on_multi('b', d))
        f.selectClicked.connect(self._on_select)
        f.panRotated.connect(self._on_pan)
        f.zoomScaleRotated.connect(self._on_zoom_scale)
        f.scope_index.currentIndexChanged.connect(self._on_scope_index_changed)

    def _index(self) -> int:
        idx = max(0, self.front.scope_index.currentIndex())
        n = self._client.scope_count
        if n > 0:
            return min(idx, n - 1)
        return idx

    def _fine(self) -> bool:
        return self.front.fine_mode

    def _log(self, msg: str) -> None:
        self.front.append_log(msg)

    def _ensure_connected(self) -> bool:
        if not self._client.connected:
            self._log(tr('tool.tektronix_scope.conn_none'))
            return False
        return True

    # ── async helper ─────────────────────────────────────────────────────

    def _run_async(
        self,
        fn: Callable,
        on_ok: Callable | None = None,
        on_err: Callable | None = None,
        *,
        coalesce: bool = False,
    ) -> None:
        if self._busy:
            if coalesce:
                # Keep latest knob nudge; run after current VISA op finishes
                self._pending_nudge = fn
                self._pending_nudge_ok = on_ok
                return
            # Avoid spamming log on rapid taps
            return
        self._busy = True
        thread = QThread(self)
        worker = _VisaWorker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def _done(result: Any) -> None:
            self._busy = False
            thread.quit()
            thread.wait(2000)
            worker.deleteLater()
            thread.deleteLater()
            self._thread = None
            self._worker = None
            if isinstance(result, Exception):
                if isinstance(result, ScopeError):
                    self._log(result.message)
                    if result.hint:
                        self._log(result.hint)
                else:
                    logger.exception('Scope async error: %s', result)
                    self._log(str(result))
                if on_err:
                    on_err(result)
            else:
                if on_ok:
                    on_ok(result)
            # Drain coalesced knob action
            if self._pending_nudge is not None:
                nxt, nxt_ok = self._pending_nudge, self._pending_nudge_ok
                self._pending_nudge = None
                self._pending_nudge_ok = None
                self._run_async(nxt, on_ok=nxt_ok, coalesce=True)

        worker.finished.connect(_done)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _scpi(self, method: Callable, *args, **kwargs) -> None:
        if not self._ensure_connected():
            return
        idx = self._index()

        def call():
            return method(*args, index=idx, **kwargs)

        def ok(_result=None):
            self._sync_status()

        self._run_async(call, on_ok=ok)

    def _nudge_async(self, fn: Callable, on_ok: Callable | None = None) -> None:
        """Knob/touch auto-repeat friendly async (coalesce while busy)."""
        if not self._ensure_connected():
            return
        self._run_async(fn, on_ok=on_ok, coalesce=True)

    def _scpi_write(self, cmd: str) -> None:
        if not self._ensure_connected():
            return
        idx = self._index()
        self._run_async(lambda: self._client.write(cmd, index=idx), on_ok=lambda _: self._log(f'→ {cmd}'))

    # ── connection / capture / wave ──────────────────────────────────────

    def _on_connect(self) -> None:
        def work():
            return self._client.connect()

        def ok(info: dict):
            idn = info.get('idn', '')
            parts = idn.split(',')
            model = parts[1].strip() if len(parts) > 1 else idn
            self.front.set_model_text(model)
            self._log(tr('tool.tektronix_scope.conn_success', count=info.get('count', 1)))
            self._log(idn)
            self._refresh_scope_combo()
            self._sync_status()
            self._on_refresh_wave()

        self._run_async(work, on_ok=ok)

    def _refresh_scope_combo(self) -> None:
        """Clamp selection to connected scope count."""
        combo = self.front.scope_index
        n = self._client.scope_count
        if n <= 0:
            return
        combo.blockSignals(True)
        if combo.currentIndex() >= n:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)
        # Update model text with live count hint in status
        self.front.set_status(
            tr('tool.tektronix_scope.conn_success', count=n)
        )

    def _on_scope_index_changed(self, _index: int) -> None:
        if not self._client.connected:
            return
        if self._index() >= self._client.scope_count:
            self._log(tr('tool.tektronix_scope.scope_unavailable', index=self._index() + 1))
            return
        self._invalidate_wfm()
        self._sync_status()
        self._on_refresh_wave()

    def _on_hardcopy(self, index: int = 0) -> None:
        if not self._ensure_connected():
            return

        def work():
            return self._client.capture_png(index=index)

        def ok(info: dict):
            path = info['path']
            img = QImage(path)
            if img.isNull():
                self._log(tr('tool.tektronix_scope.save_error'))
                return
            self._pix = QPixmap.fromImage(img)
            self.front.preview_label.setPixmap(self._pix)
            self.front.btn_preview_toggle.setChecked(True)
            self.front.preview_label.show()
            self._log(tr('tool.tektronix_scope.save_ok', path=path))
            try:
                QApplication.clipboard().setPixmap(self._pix)
                self._log(tr('tool.tektronix_scope.copy_ok'))
            except Exception:
                self._log(tr('tool.tektronix_scope.copy_failed'))

        self._run_async(work, on_ok=ok)

    def _on_refresh_wave(self, live: bool = False) -> None:
        if not self._ensure_connected():
            return
        idx = self._index()
        xfer = _LIVE_XFER_POINTS if live else _MANUAL_XFER_POINTS
        disp = _LIVE_DISPLAY_POINTS if live else _MANUAL_DISPLAY_POINTS

        def work():
            if live:
                # Light status every ~2s (8 frames @ 250ms)
                status = None
                if (self._live_frame % 8) == 0:
                    status = self._client.read_status(index=idx, light=True)
                waves = self._client.read_waveforms(
                    index=idx,
                    points=xfer,
                    display_points=disp,
                )
                return {'status': status, 'waves': waves, 'live': True}
            status = self._client.read_status(index=idx)
            waves = self._client.read_waveforms(
                index=idx,
                points=xfer,
                display_points=disp,
            )
            return {'status': status, 'waves': waves, 'live': False}

        def ok(payload: dict):
            status = payload.get('status')
            if status:
                if payload.get('live'):
                    # Only update acquire/channel on flags for light status
                    acq = (status.get('acquire_state') or '').upper()
                    self._running = acq in ('1', 'ON', 'RUN')
                    self.front.set_run_state(self._running)
                    for ch, info in (status.get('channels') or {}).items():
                        self.front.set_channel_active(ch, bool(info.get('selected')))
                else:
                    self._apply_status(status)
            self.front.wave_plot.set_waveforms(
                payload['waves'],
                auto_range=not payload.get('live'),
            )
            if not payload.get('live'):
                self._log(tr('tool.tektronix_scope.wave_ok', n=len(payload['waves'])))
            self._live_frame += 1

        self._run_async(work, on_ok=ok, coalesce=live)

    def _sync_status(self) -> None:
        if not self._client.connected:
            return
        idx = self._index()

        def work():
            return self._client.read_status(index=idx)

        self._run_async(work, on_ok=self._apply_status)

    def _apply_status(self, status: dict) -> None:
        acq = (status.get('acquire_state') or '').upper()
        self._running = acq in ('1', 'ON', 'RUN')
        self.front.set_run_state(self._running)

        def fmt_scale(v, unit):
            try:
                x = float(v)
            except (TypeError, ValueError):
                return '—'
            if unit == 's':
                if x < 1e-6:
                    return f'{x * 1e9:.2f} ns/div'
                if x < 1e-3:
                    return f'{x * 1e6:.2f} µs/div'
                if x < 1:
                    return f'{x * 1e3:.2f} ms/div'
                return f'{x:.2f} s/div'
            # volts
            if abs(x) < 1:
                return f'{x * 1e3:.1f} mV/div'
            return f'{x:.2f} V/div'

        chs = status.get('channels') or {}
        readouts = {
            'acquire': f"采集: {'RUN' if self._running else 'STOP'}",
            'trigger': (
                f"触发: {status.get('trigger_source') or '?'} "
                f"{status.get('trigger_slope') or ''} "
                f"{status.get('trigger_level') or ''}V"
            ),
            'sample': f"采样: {status.get('sample_rate') or '—'}  记录: {status.get('record_length') or '—'}",
            'horiz': f"水平: {fmt_scale(status.get('horizontal_scale'), 's')}",
        }
        for ch in ('CH1', 'CH2', 'CH3', 'CH4'):
            info = chs.get(ch) or {}
            on = bool(info.get('selected'))
            self.front.set_channel_active(ch, on)
            sc = fmt_scale(info.get('scale'), 'V') if on else '关'
            readouts[ch.lower()] = f'{ch}: {sc}'
        self.front.set_readouts(readouts)
        self.front.set_status(
            f"{'运行' if self._running else '停止'} · {status.get('idn', '')}"
        )

    # ── transport ────────────────────────────────────────────────────────

    def _on_run_stop(self) -> None:
        if not self._ensure_connected():
            self.front.set_run_state(self._running)
            return
        if self._busy:
            # Revert optimistic checkable toggle until VISA is free
            self.front.set_run_state(self._running)
            return
        want_run = not self._running
        idx = self._index()

        def work():
            if want_run:
                self._client.run(index=idx)
            else:
                self._client.stop(index=idx)
            return want_run

        def ok(running: bool):
            self._running = running
            self.front.set_run_state(running)

        def err(_e):
            self.front.set_run_state(self._running)

        self._run_async(work, on_ok=ok, on_err=err)

    def _on_single(self) -> None:
        if not self._ensure_connected():
            return
        idx = self._index()

        def work():
            self._client.single(index=idx)
            return True

        def ok(_):
            self._running = False
            self.front.set_run_state(False)

        self._run_async(work, on_ok=ok)

    def _on_autoset(self) -> None:
        def work():
            self._client.autoset(index=self._index())
            return True

        def ok(_):
            self._log(tr('tool.tektronix_scope.autoset_ok'))
            self._on_refresh_wave()

        if self._ensure_connected():
            self._run_async(work, on_ok=ok)

    def _on_default_setup(self) -> None:
        def work():
            self._client.default_setup(index=self._index())
            return True

        def ok(_):
            self._log(tr('tool.tektronix_scope.default_ok'))
            self._on_refresh_wave()

        if self._ensure_connected():
            self._run_async(work, on_ok=ok)

    # ── knobs ────────────────────────────────────────────────────────────

    def _on_ch_scale(self, ch: str, direction: int) -> None:
        fine = self._fine()
        idx = self._index()

        def work():
            return self._client.nudge_channel_scale(ch, direction, fine=fine, index=idx)

        self._nudge_async(work, on_ok=lambda v: (self._invalidate_wfm(), self._log(f'{ch} 标度 → {v:g} V/div')))

    def _on_ch_pos(self, ch: str, direction: int) -> None:
        fine = self._fine()
        idx = self._index()

        def work():
            return self._client.nudge_channel_position(ch, direction, fine=fine, index=idx)

        self._nudge_async(work, on_ok=lambda v: self._log(f'{ch} 位置 → {v:.2f} div'))

    def _on_h_scale(self, direction: int) -> None:
        fine = self._fine()
        idx = self._index()

        def work():
            return self._client.nudge_horizontal_scale(direction, fine=fine, index=idx)

        self._nudge_async(work, on_ok=lambda v: (self._invalidate_wfm(), self._log(f'水平标度 → {v:g} s/div')))

    def _on_h_pos(self, direction: int) -> None:
        fine = self._fine()
        idx = self._index()

        def work():
            return self._client.nudge_horizontal_position(direction, fine=fine, index=idx)

        self._nudge_async(work, on_ok=lambda v: self._log(f'水平位置 → {v:.1f}%'))

    def _on_trig_level(self, direction: int) -> None:
        fine = self._fine()
        idx = self._index()

        def work():
            return self._client.nudge_trigger_level(direction, fine=fine, index=idx)

        self._nudge_async(work, on_ok=lambda v: self._log(f'触发电平 → {v:g} V'))

    def _on_pan(self, direction: int) -> None:
        if not self._ensure_connected():
            return
        if not self._zoom_on:
            self._on_h_pos(direction)
            return
        fine = self._fine()
        idx = self._index()
        step = 1.0 if fine else 5.0

        def work():
            try:
                cur = float(self._client.query('ZOOm:ZOOM1:POSition?', index=idx))
            except ScopeError:
                cur = float(self._client.query('HORizontal:POSition?', index=idx))
            nxt = cur + (step if direction > 0 else -step)
            try:
                self._client.write(f'ZOOm:ZOOM1:POSition {nxt}', index=idx)
            except ScopeError:
                self._client.write(f'HORizontal:POSition {nxt}', index=idx)
            return nxt

        self._nudge_async(work, on_ok=lambda v: self._log(f'缩放平移 → {v:.1f}%'))

    def _on_zoom_scale(self, direction: int) -> None:
        if not self._ensure_connected():
                return
        idx = self._index()

        def work():
            try:
                cur = float(self._client.query('ZOOm:ZOOM1:SCAle?', index=idx))
                factor = 1.05 if self._fine() else 1.25
                nxt = cur * (factor if direction > 0 else 1 / factor)
                self._client.write(f'ZOOm:ZOOM1:SCAle {nxt}', index=idx)
                return nxt
            except ScopeError:
                return self._client.nudge_horizontal_scale(direction, fine=self._fine(), index=idx)

        self._nudge_async(work, on_ok=lambda v: self._log(f'缩放比例 → {v:g}'))

    def _on_channel_menu(self, ch: str) -> None:
        """Toggle channel display and open a compact vertical side menu."""
        btn = self.front.channel_btns.get(ch)
        if not self._ensure_connected():
            if btn is not None:
                btn.setChecked(bool(self.front._ch_on.get(ch, False)))
            return
        idx = self._index()

        def work():
            on = not self._client.channel_selected(ch, index=idx)
            self._client.select_channel(ch, on, index=idx)
            return on

        def ok(on: bool):
            self.front.set_channel_active(ch, on)
            self._log(f'{ch} → {"开" if on else "关"}')
            self._show_channel_side_menu(ch)
            if on:
                self.front.wave_plot.set_preferred_channel(ch)
                self._on_refresh_wave()

        def err(_e):
            if btn is not None:
                btn.setChecked(bool(self.front._ch_on.get(ch, False)))

        self._run_async(work, on_ok=ok, on_err=err)

    def _show_channel_side_menu(self, ch: str) -> None:
        """Quick vertical controls for the selected channel."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        tip = QLabel(tr('tool.tektronix_scope.ch_side_tip', ch=ch))
        tip.setWordWrap(True)
        tip.setStyleSheet('color:#E2E8F0;font-size:11px;')
        lay.addWidget(tip)
        actions = [
            (f'{ch}:COUPling DC', tr('tool.tektronix_scope.coup_dc')),
            (f'{ch}:COUPling AC', tr('tool.tektronix_scope.coup_ac')),
            (f'{ch}:BANdwidth FULl', tr('tool.tektronix_scope.bw_full')),
            (f'{ch}:BANdwidth TWEnty', tr('tool.tektronix_scope.bw_20')),
            (f'{ch}:PRObe:GAIN 1', tr('tool.tektronix_scope.probe_1x')),
            (f'{ch}:PRObe:GAIN 10', tr('tool.tektronix_scope.probe_10x')),
        ]
        for cmd, label in actions:
            b = QPushButton(label)
            b.setMinimumHeight(30)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=cmd: self._scpi_write(c))
            lay.addWidget(b)
        lay.addStretch(1)
        self._open_side_menu_key = f'ch_{ch}'
        self.front.show_side_menu(tr('tool.tektronix_scope.side_vertical', ch=ch), w)

    def _on_cursor(self) -> None:
        """Toggle local plot cursors (X1/X2/Y1/Y2); also sync instrument when connected."""
        on = bool(self.front.btn_cursor.isChecked())
        # Prefer first selected channel for V/A unit matching
        preferred = None
        for ch, btn in self.front.channel_btns.items():
            if btn.isChecked():
                preferred = ch
                break
        self.front.wave_plot.set_preferred_channel(preferred)
        self.front.wave_plot.set_cursors_enabled(on)
        if on:
            self._log(tr('tool.tektronix_scope.cursors_on'))
        else:
            self._log(tr('tool.tektronix_scope.cursors_off'))
        if not self._client.connected:
            return
        idx = self._index()

        def work():
            if on:
                try:
                    self._client.write('CURSor:FUNCtion WAVEform', index=idx)
                except ScopeError:
                    try:
                        self._client.write('CURSor:FUNCtion HBArs', index=idx)
                    except ScopeError:
                        pass
                return 'ON'
            try:
                self._client.write('CURSor:FUNCtion OFF', index=idx)
            except ScopeError:
                pass
            return 'OFF'

        self._run_async(work)

    def _on_zoom(self) -> None:
        if not self._ensure_connected():
            self.front.btn_zoom.setChecked(self._zoom_on)
            return
        # Prefer button checked state (avoid double-toggle vs internal flag)
        on = bool(self.front.btn_zoom.isChecked())
        idx = self._index()

        def ok(_):
            self._zoom_on = on
            self._log(f'缩放 → {"ON" if on else "OFF"}')

        def err(_e):
            self._zoom_on = not on
            self.front.btn_zoom.setChecked(not on)

        self._run_async(lambda: self._client.set_zoom(on, index=idx), on_ok=ok, on_err=err)

    def _on_multi(self, which: str, direction: int) -> None:
        # Mode 0: a → trigger level, b → horizontal position
        # Mode 1: a → horizontal scale, b → horizontal position
        if which == 'a':
            if self._multi_mode == 0:
                self._on_trig_level(direction)
            else:
                self._on_h_scale(direction)
        else:
            self._on_h_pos(direction)

    def _on_select(self) -> None:
        self._multi_mode = (self._multi_mode + 1) % 2
        tip_key = (
            'tool.tektronix_scope.multi_mode_0'
            if self._multi_mode == 0
            else 'tool.tektronix_scope.multi_mode_1'
        )
        self._log(tr(tip_key))

    def _on_play_pause(self) -> None:
        """Wave Inspector play/pause — enable zoom if needed, then browse with pan."""
        if not self._ensure_connected():
            self.front.btn_play.setChecked(self._play_on)
            return
        self._play_on = bool(self.front.btn_play.isChecked())
        if self._play_on and not self._zoom_on:
            self.front.btn_zoom.blockSignals(True)
            self.front.btn_zoom.setChecked(True)
            self.front.btn_zoom.blockSignals(False)
            self._zoom_on = True
            idx = self._index()
            self._run_async(lambda: self._client.set_zoom(True, index=idx))
        self._log(
            tr('tool.tektronix_scope.play_on') if self._play_on else tr('tool.tektronix_scope.play_off')
        )
        if self._play_on:
            self._log(tr('tool.tektronix_scope.play_hint'))

    def _on_mark_set_clear(self) -> None:
        if not self._ensure_connected():
            return
        self._mark_armed = not self._mark_armed
        if self._mark_armed:
            self._scpi_write('MARK:CREATE CH1')
        else:
            self._scpi_write('MARK:DELEte ALL')

    # ── side menus ───────────────────────────────────────────────────────

    def _on_menu(self, key: str) -> None:
        self._open_side_menu_key = key
        builders = {
            'acquire': self._build_acquire_menu,
            'trigger': self._build_trigger_menu,
            'measure': self._build_simple_menu(tr('tool.tektronix_scope.side_measure'), [
                ('MEASUrement:MEAS1:STATE ON', _L('打开测量 1', 'Enable Meas 1')),
                ('MEASUrement:MEAS1:TYPe FREQuency', _L('类型: 频率', 'Type: Frequency')),
                ('MEASUrement:MEAS1:TYPe PK2Pk', _L('类型: 峰峰值', 'Type: Peak-Peak')),
                ('MEASUrement:MEAS1:TYPe MEAN', _L('类型: 均值', 'Type: Mean')),
                ('MEASUrement:MEAS1:SOUrce1 CH1', _L('源: CH1', 'Source: CH1')),
            ]),
            'search': self._build_simple_menu(tr('tool.tektronix_scope.side_search'), [
                ('SEARCH:SEARCH1:STATE ON', _L('打开搜索 1', 'Enable Search 1')),
                ('SEARCH:SEARCH1:STATE OFF', _L('关闭搜索 1', 'Disable Search 1')),
            ]),
            'math': self._build_simple_menu(tr('tool.tektronix_scope.side_math'), [
                ('SELect:MATH ON', _L('显示 MATH', 'Show MATH')),
                ('SELect:MATH OFF', _L('关闭 MATH', 'Hide MATH')),
                ('MATH1:TYPe DUAL', _L('类型: 双波形', 'Type: Dual')),
                ('MATH1:DEFine "CH1-CH2"', 'CH1-CH2'),
                ('MATH1:DEFine "CH1*CH2"', 'CH1*CH2'),
            ]),
            'ref': self._build_simple_menu(tr('tool.tektronix_scope.side_ref'), [
                ('SELect:REF1 ON', _L('显示 REF1', 'Show REF1')),
                ('SELect:REF1 OFF', _L('关闭 REF1', 'Hide REF1')),
            ]),
            'bus1': self._build_simple_menu(tr('tool.tektronix_scope.side_bus1'), [
                ('SELect:BUS1 ON', _L('显示 B1', 'Show B1')),
                ('SELect:BUS1 OFF', _L('关闭 B1', 'Hide B1')),
            ]),
            'bus2': self._build_simple_menu(tr('tool.tektronix_scope.side_bus2'), [
                ('SELect:BUS2 ON', _L('显示 B2', 'Show B2')),
                ('SELect:BUS2 OFF', _L('关闭 B2', 'Hide B2')),
            ]),
            'afg': self._build_simple_menu(tr('tool.tektronix_scope.side_afg'), [
                ('AFG:OUTPut:STATE ON', _L('AFG 输出开', 'AFG Output ON')),
                ('AFG:OUTPut:STATE OFF', _L('AFG 输出关', 'AFG Output OFF')),
                ('AFG:FUNCtion SINusoid', _L('正弦', 'Sine')),
                ('AFG:FUNCtion SQUare', _L('方波', 'Square')),
            ]),
            'rf': self._build_simple_menu(tr('tool.tektronix_scope.side_rf'), [
                ('SELect:RF_NORMal ON', _L('RF Normal 开', 'RF Normal ON')),
                ('SELect:RF_NORMal OFF', _L('RF Normal 关', 'RF Normal OFF')),
            ]),
            'test': self._build_simple_menu(tr('tool.tektronix_scope.side_test'), [
                ('*TST?', _L('自检 *TST?', 'Self-test *TST?')),
                ('DIAg:LOOP:STATE?', _L('诊断循环状态', 'Diag loop state')),
            ]),
            'save_recall': self._build_simple_menu(tr('tool.tektronix_scope.side_save_recall'), [
                ('SAVe:SETUp "setup1.set"', _L('保存设置 setup1', 'Save setup1')),
                ('RECAll:SETUp "setup1.set"', _L('调出设置 setup1', 'Recall setup1')),
                ('SAVe:IMAGe "shot.png"', _L('保存图像', 'Save image')),
            ]),
            'utility': self._build_simple_menu(tr('tool.tektronix_scope.side_utility'), [
                ('*IDN?', _L('查询 *IDN?', 'Query *IDN?')),
                ('*RST', _L('复位 *RST', 'Reset *RST')),
                ('HEADER OFF', _L('关闭响应头', 'Header OFF')),
            ]),
            'intensity': self._build_intensity_menu,
        }
        builder = builders.get(key)
        if builder is None:
            self._log(f'menu not implemented: {key}')
            return
        title, widget = builder()
        self.front.show_side_menu(title, widget)

    def _build_simple_menu(self, title: str, actions: list[tuple[str, str]]):
        def build():
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setSpacing(6)
            for cmd, label in actions:
                btn = QPushButton(label)
                btn.setMinimumHeight(40)
                btn.setCursor(Qt.PointingHandCursor)
                if cmd.endswith('?'):
                    btn.clicked.connect(lambda _=False, c=cmd: self._query_cmd(c))
                else:
                    btn.clicked.connect(lambda _=False, c=cmd: self._scpi_write(c))
                lay.addWidget(btn)
            lay.addStretch(1)
            return title, w
        return build

    def _query_cmd(self, cmd: str) -> None:
        if not self._ensure_connected():
            return
        idx = self._index()
        self._run_async(
            lambda: self._client.query(cmd, index=idx),
            on_ok=lambda r: self._log(f'{cmd} → {r}'),
        )

    def _build_acquire_menu(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        mode = QComboBox()
        mode.addItems(['SAMple', 'PEAKdetect', 'HIRes', 'AVErage', 'ENVelope'])
        rec = QSpinBox()
        rec.setRange(1000, 10000000)
        rec.setSingleStep(1000)
        rec.setValue(10000)
        form.addRow(tr('tool.tektronix_scope.acq_mode'), mode)
        form.addRow(tr('tool.tektronix_scope.record_length'), rec)
        lay.addLayout(form)

        apply_btn = QPushButton(tr('tool.tektronix_scope.apply'))
        apply_btn.setMinimumHeight(40)

        def apply():
            if not self._ensure_connected():
                return
            idx = self._index()
            m = mode.currentText()
            n = rec.value()

            def work():
                self._client.set_acquire_mode(m, index=idx)
                self._client.set_record_length(n, index=idx)
                return True

            self._run_async(work, on_ok=lambda _: self._log(f'acquire={m}, record={n}'))

        apply_btn.clicked.connect(apply)
        lay.addWidget(apply_btn)
        for label, cmd in (
            (_L('快速采集 ON', 'FastAcq ON'), 'ACQuire:FASTAcq:STATE ON'),
            (_L('快速采集 OFF', 'FastAcq OFF'), 'ACQuire:FASTAcq:STATE OFF'),
            ('MagniVu ON', 'ACQuire:MAGnivu ON'),
        ):
            b = QPushButton(label)
            b.setMinimumHeight(40)
            b.clicked.connect(lambda _=False, c=cmd: self._scpi_write(c))
            lay.addWidget(b)
        lay.addStretch(1)
        return tr('tool.tektronix_scope.side_acquire'), w

    def _build_trigger_menu(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        src = QComboBox()
        src.addItems(['CH1', 'CH2', 'CH3', 'CH4', 'EXT', 'LINE', 'AUX'])
        slope = QComboBox()
        slope.addItems(['RISe', 'FALL'])
        mode = QComboBox()
        mode.addItems(['AUTO', 'NORMal'])
        form.addRow(tr('tool.tektronix_scope.edge_source'), src)
        form.addRow(tr('tool.tektronix_scope.slope'), slope)
        form.addRow(tr('tool.tektronix_scope.trig_mode'), mode)
        lay.addLayout(form)
        apply_btn = QPushButton(tr('tool.tektronix_scope.apply_edge'))
        apply_btn.setMinimumHeight(40)

        def apply():
            if not self._ensure_connected():
                return
            idx = self._index()
            s, sl, m = src.currentText(), slope.currentText(), mode.currentText()

            def work():
                self._client.write('TRIGger:A:TYPe EDGE', index=idx)
                self._client.set_trigger_source(s, index=idx)
                self._client.set_trigger_slope(sl, index=idx)
                self._client.set_trigger_mode(m, index=idx)
                return True

            self._run_async(work, on_ok=lambda _: self._sync_status())

        apply_btn.clicked.connect(apply)
        lay.addWidget(apply_btn)
        lay.addStretch(1)
        return tr('tool.tektronix_scope.side_trigger'), w

    def _build_intensity_menu(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        items = (
            (_L('波形亮度 35%', 'Wave intensity 35%'), 35, 'wave'),
            (_L('波形亮度 70%', 'Wave intensity 70%'), 70, 'wave'),
            (_L('格线亮度 50%', 'Graticule 50%'), 50, 'grat'),
        )
        for label, pct, kind in items:
            b = QPushButton(label)
            b.setMinimumHeight(40)
            b.setCursor(Qt.PointingHandCursor)
            if kind == 'grat':
                b.clicked.connect(
                    lambda _=False, p=pct: self._scpi(self._client.set_intensity_graticule, float(p))
                )
            else:
                b.clicked.connect(
                    lambda _=False, p=pct: self._scpi(self._client.set_intensity_waveform, float(p))
                )
            lay.addWidget(b)
        lay.addStretch(1)
        return tr('tool.tektronix_scope.side_intensity'), w


# Back-compat alias
TektronixScopeWindow = TektronixScopePanel
