"""PyQtGraph waveform display for Tektronix CURVe data (perf-tuned).

Supports:
  - Movable X1/X2/Y1/Y2 cursors with live Δt / ΔY / freq readouts
  - Right-click measure: start → rubber-band → end → Δt / Δamplitude
"""
from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

CHANNEL_COLORS = {
    'CH1': '#FFEB3B',
    'CH2': '#69F0AE',
    'CH3': '#EA80FC',
    'CH4': '#82B1FF',
    'MATH': '#FF9800',
    'REF1': '#FFFFFF',
}


def _fmt_eng(value: float, unit: str) -> str:
    """Format SI value with engineering prefixes."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return f'— {unit}'
    av = abs(v)
    if unit in ('s', 'sec', 'S'):
        if av >= 1.0:
            return f'{v:.4g} s'
        if av >= 1e-3:
            return f'{v * 1e3:.4g} ms'
        if av >= 1e-6:
            return f'{v * 1e6:.4g} µs'
        return f'{v * 1e9:.4g} ns'
    # Amplitude: V or A (and derivatives)
    base = 'A' if _is_current_unit(unit) else 'V'
    if av >= 1.0:
        return f'{v:.4g} {base}'
    if av >= 1e-3:
        return f'{v * 1e3:.4g} m{base}'
    if av >= 1e-6:
        return f'{v * 1e6:.4g} µ{base}'
    return f'{v * 1e9:.4g} n{base}'


def _is_current_unit(unit: str | None) -> bool:
    if not unit:
        return False
    u = unit.strip().upper().replace('"', '')
    # "A", "AA", "AMPS" — not "V" / "VOLTS"
    if 'V' in u and 'A' not in u.replace('VA', ''):
        return False
    return u in ('A', 'AA', 'AMP', 'AMPS', 'AMPERE', 'AMPERES') or u.endswith('A') and 'V' not in u


def _normalize_y_unit(unit: str | None) -> str:
    if _is_current_unit(unit):
        return 'A'
    return 'V'


class ScopeWaveformPlot(QWidget):
    """Multi-channel scope-style plot (time vs volts/amps) with cursors."""

    cursorReadoutChanged = pyqtSignal(str)
    measureReadoutChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: dict[str, Any] = {}
        self._wave_xy: dict[str, tuple[Any, Any]] = {}
        self._wave_meta: dict[str, dict[str, Any]] = {}
        self._plot = None
        self._widget = None
        self._auto_range = True
        self._live = False
        self._cursors_on = False
        self._pg = None
        self._preferred_channel: str | None = None
        self._cursors_placed = False

        self._x1 = self._x2 = self._y1 = self._y2 = None
        self._cursor_label = None
        self._meas_start = None  # (x, y) data coords
        self._meas_curve = None
        self._meas_label = None
        self._meas_scatter = None
        self._click_proxy = None
        self._move_proxy = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._hud = QLabel('')
        self._hud.setWordWrap(True)
        self._hud.setStyleSheet(
            'QLabel{background:#0F172ACC;color:#F8FAFC;font-size:11px;font-weight:600;'
            'padding:4px 8px;border:1px solid #475569;border-radius:4px;}'
        )
        self._hud.hide()
        layout.addWidget(self._hud)

        try:
            import pyqtgraph as pg

            self._pg = pg
            pg.setConfigOptions(antialias=False, background='#0B1220', foreground='#E2E8F0')
            self._widget = pg.GraphicsLayoutWidget()
            self._plot = self._widget.addPlot(row=0, col=0)
            self._plot.showGrid(x=True, y=True, alpha=0.25)
            self._plot.setLabel('bottom', 'Time', units='s')
            self._plot.setLabel('left', 'Amplitude', units='V')
            self._plot.addLegend(offset=(10, 10))
            self._plot.setClipToView(True)
            self._plot.setDownsampling(mode='peak')
            try:
                self._plot.setDefaultPadding(0.02)
            except Exception:
                pass
            # Disable stock context menu — we use RMB for measure
            self._plot.setMenuEnabled(False)
            vb = self._plot.getViewBox()
            vb.setMenuEnabled(False)

            self._build_cursor_items(pg)
            self._build_measure_items(pg)
            self._wire_mouse(pg)
            layout.addWidget(self._widget, stretch=1)
        except Exception:
            lab = QLabel('pyqtgraph 不可用，无法显示波形')
            lab.setStyleSheet('color:#94A3B8;padding:12px;')
            layout.addWidget(lab)

    # ── construction helpers ─────────────────────────────────────────────

    def _build_cursor_items(self, pg) -> None:
        label_opts = {
            'position': 0.95,
            'color': '#F8FAFC',
            'fill': '#0F172A',
            'movable': True,
        }
        self._x1 = pg.InfiniteLine(
            angle=90, movable=True, pen=pg.mkPen('#38BDF8', width=1.5),
            label='X1', labelOpts=dict(label_opts),
        )
        self._x2 = pg.InfiniteLine(
            angle=90, movable=True, pen=pg.mkPen('#7DD3FC', width=1.5, style=Qt.DashLine),
            label='X2', labelOpts=dict(label_opts),
        )
        self._y1 = pg.InfiniteLine(
            angle=0, movable=True, pen=pg.mkPen('#F472B6', width=1.5),
            label='Y1', labelOpts=dict(label_opts),
        )
        self._y2 = pg.InfiniteLine(
            angle=0, movable=True, pen=pg.mkPen('#F9A8D4', width=1.5, style=Qt.DashLine),
            label='Y2', labelOpts=dict(label_opts),
        )
        for line in (self._x1, self._x2, self._y1, self._y2):
            line.setZValue(20)
            line.sigPositionChanged.connect(self._on_cursor_moved)
            line.hide()

    def _build_measure_items(self, pg) -> None:
        self._meas_curve = self._plot.plot(
            [], [], pen=pg.mkPen('#FBBF24', width=2), antialias=False
        )
        self._meas_curve.setZValue(25)
        self._meas_scatter = pg.ScatterPlotItem(
            size=10, brush=pg.mkBrush('#FBBF24'), pen=pg.mkPen('#FFFFFF', width=1)
        )
        self._meas_scatter.setZValue(26)
        self._plot.addItem(self._meas_scatter)
        self._meas_label = pg.TextItem(color='#FDE68A', anchor=(0, 1))
        self._meas_label.setZValue(27)
        self._plot.addItem(self._meas_label)
        self._meas_label.hide()

    def _wire_mouse(self, pg) -> None:
        scene = self._plot.scene()
        self._click_proxy = pg.SignalProxy(
            scene.sigMouseClicked, rateLimit=40, slot=self._on_mouse_clicked
        )
        self._move_proxy = pg.SignalProxy(
            scene.sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved
        )

    # ── public API ───────────────────────────────────────────────────────

    def set_live_mode(self, live: bool) -> None:
        self._live = live
        self._auto_range = not live

    def set_preferred_channel(self, channel: str | None) -> None:
        """Prefer this channel for unit / sample readouts (e.g. selected CH)."""
        self._preferred_channel = channel.upper() if channel else None
        if self._cursors_on:
            self._apply_axis_unit()
            self._update_cursor_readout()

    def set_cursors_enabled(self, on: bool) -> None:
        """Show/hide movable X1/X2/Y1/Y2 and update readout."""
        self._cursors_on = bool(on)
        if self._plot is None:
            return
        if self._cursors_on:
            self._ensure_cursors_on_plot()
            if not self._cursors_placed:
                self._place_cursors_in_view()
                self._cursors_placed = True
            for line in (self._x1, self._x2, self._y1, self._y2):
                line.show()
            self._update_cursor_readout()
        else:
            for line in (self._x1, self._x2, self._y1, self._y2):
                if line is not None:
                    line.hide()
            self.clear_measure()
            self._set_hud('')
            self.cursorReadoutChanged.emit('')

    def clear_measure(self) -> None:
        self._meas_start = None
        if self._meas_curve is not None:
            self._meas_curve.setData([], [])
        if self._meas_scatter is not None:
            self._meas_scatter.setData([])
        if self._meas_label is not None:
            self._meas_label.hide()
        self.measureReadoutChanged.emit('')
        if not self._cursors_on:
            self._set_hud('')

    def clear(self) -> None:
        if self._plot is None:
            return
        self._plot.clear()
        self._curves.clear()
        self._wave_xy.clear()
        self._wave_meta.clear()
        self._plot.addLegend(offset=(10, 10))
        # Re-attach cursor / measure items after clear()
        if self._pg is not None:
            for line in (self._x1, self._x2, self._y1, self._y2):
                if line is not None:
                    self._plot.addItem(line)
                    if not self._cursors_on:
                        line.hide()
            if self._meas_curve is not None:
                self._plot.addItem(self._meas_curve)
            if self._meas_scatter is not None:
                self._plot.addItem(self._meas_scatter)
            if self._meas_label is not None:
                self._plot.addItem(self._meas_label)
                self._meas_label.hide()

    def set_waveform(self, channel: str, x, y, *, y_unit: str = 'V', meta: dict | None = None) -> None:
        if self._plot is None:
            return
        import pyqtgraph as pg

        ch = channel.upper()
        color = CHANNEL_COLORS.get(ch, '#FFFFFF')
        try:
            import numpy as np
            if not isinstance(x, np.ndarray):
                x = np.asarray(x, dtype=np.float64)
            if not isinstance(y, np.ndarray):
                y = np.asarray(y, dtype=np.float64)
        except ImportError:
            pass

        self._wave_xy[ch] = (x, y)
        self._wave_meta[ch] = {
            'y_unit': _normalize_y_unit(y_unit if y_unit else (meta or {}).get('y_unit', 'V')),
            'x_unit': 's',
            **(meta or {}),
        }
        self._apply_axis_unit()

        if ch in self._curves:
            self._curves[ch].setData(x, y, skipFiniteCheck=True)
        else:
            pen = pg.mkPen(color=color, width=1.2)
            curve = self._plot.plot(x, y, pen=pen, name=ch, antialias=False)
            try:
                curve.setClipToView(True)
                curve.setDownsampling(auto=True, method='peak')
            except Exception:
                pass
            self._curves[ch] = curve

    def set_waveforms(self, waves: list[dict], *, auto_range: bool | None = None) -> None:
        """Update curves from a list of {channel,x,y[,y_unit]} dicts."""
        if self._plot is None:
            return
        keep = {w['channel'].upper() for w in waves}
        for ch in list(self._curves):
            if ch not in keep:
                self._plot.removeItem(self._curves.pop(ch))
                self._wave_xy.pop(ch, None)
                self._wave_meta.pop(ch, None)
        for w in waves:
            self.set_waveform(
                w['channel'],
                w['x'],
                w['y'],
                y_unit=w.get('y_unit') or (w.get('preamble') or {}).get('yunit', 'V'),
                meta=w.get('preamble'),
            )
        do_range = self._auto_range if auto_range is None else auto_range
        if waves and do_range:
            self._plot.autoRange()
            # Place once after first data if cursors already on but never placed
            if self._cursors_on and not self._cursors_placed:
                self._place_cursors_in_view()
                self._cursors_placed = True
        if self._cursors_on:
            self._update_cursor_readout()

    # ── cursors ──────────────────────────────────────────────────────────

    def _ensure_cursors_on_plot(self) -> None:
        if self._plot is None:
            return
        for line in (self._x1, self._x2, self._y1, self._y2):
            if line is not None and line.scene() is None:
                self._plot.addItem(line)

    def _place_cursors_in_view(self) -> None:
        if self._plot is None:
            return
        (xmin, xmax), (ymin, ymax) = self._plot.viewRange()
        if not (xmax > xmin and ymax > ymin):
            return
        # Avoid resetting while user is dragging
        dx = xmax - xmin
        dy = ymax - ymin
        self._x1.blockSignals(True)
        self._x2.blockSignals(True)
        self._y1.blockSignals(True)
        self._y2.blockSignals(True)
        self._x1.setValue(xmin + 0.25 * dx)
        self._x2.setValue(xmin + 0.75 * dx)
        self._y1.setValue(ymin + 0.25 * dy)
        self._y2.setValue(ymin + 0.75 * dy)
        self._x1.blockSignals(False)
        self._x2.blockSignals(False)
        self._y1.blockSignals(False)
        self._y2.blockSignals(False)

    def _on_cursor_moved(self, *_args) -> None:
        if self._cursors_on:
            self._update_cursor_readout()

    def _primary_channel(self) -> str | None:
        pref = self._preferred_channel
        if pref and pref in self._wave_xy:
            return pref
        for ch in ('CH1', 'CH2', 'CH3', 'CH4', 'MATH'):
            if ch in self._wave_xy:
                return ch
        return next(iter(self._wave_xy), None)

    def _y_unit(self) -> str:
        ch = self._primary_channel()
        if ch and ch in self._wave_meta:
            return _normalize_y_unit(self._wave_meta[ch].get('y_unit'))
        return 'V'

    def _apply_axis_unit(self) -> None:
        if self._plot is None:
            return
        yu = self._y_unit()
        name = 'Current' if yu == 'A' else 'Voltage'
        self._plot.setLabel('left', name, units=yu)

    def _y_at_x(self, ch: str, x: float) -> float | None:
        xy = self._wave_xy.get(ch)
        if xy is None:
            return None
        xs, ys = xy
        try:
            import numpy as np
            xs = np.asarray(xs, dtype=np.float64)
            ys = np.asarray(ys, dtype=np.float64)
            if xs.size < 2:
                return float(ys[0]) if ys.size else None
            if x < xs[0] or x > xs[-1]:
                return float(np.interp(x, xs, ys))
            return float(np.interp(x, xs, ys))
        except Exception:
            return None

    def _update_cursor_readout(self) -> None:
        if not self._cursors_on or self._x1 is None:
            return
        x1, x2 = float(self._x1.value()), float(self._x2.value())
        y1, y2 = float(self._y1.value()), float(self._y2.value())
        dt = x2 - x1
        dy = y2 - y1
        yu = self._y_unit()
        parts = [
            f'X1={_fmt_eng(x1, "s")}',
            f'X2={_fmt_eng(x2, "s")}',
            f'Δt={_fmt_eng(dt, "s")}',
        ]
        if abs(dt) > 0:
            parts.append(f'1/Δt={abs(1.0 / dt):.4g} Hz')
        parts += [
            f'Y1={_fmt_eng(y1, yu)}',
            f'Y2={_fmt_eng(y2, yu)}',
            f'ΔY={_fmt_eng(dy, yu)}',
        ]
        ch = self._primary_channel()
        if ch:
            v1 = self._y_at_x(ch, x1)
            v2 = self._y_at_x(ch, x2)
            if v1 is not None and v2 is not None:
                chu = _normalize_y_unit(self._wave_meta.get(ch, {}).get('y_unit', yu))
                parts.append(f'{ch}@X1={_fmt_eng(v1, chu)}')
                parts.append(f'{ch}@X2={_fmt_eng(v2, chu)}')
                parts.append(f'{ch} Δ={_fmt_eng(v2 - v1, chu)}')
        text = '  |  '.join(parts)
        self._set_hud(text)
        self.cursorReadoutChanged.emit(text)

    # ── right-click measure ──────────────────────────────────────────────

    def _map_scene_to_data(self, scene_pos):
        if self._plot is None:
            return None
        vb = self._plot.getViewBox()
        if not vb.sceneBoundingRect().contains(scene_pos):
            return None
        mouse = vb.mapSceneToView(scene_pos)
        return float(mouse.x()), float(mouse.y())

    def _on_mouse_clicked(self, event_args) -> None:
        if self._plot is None:
            return
        try:
            ev = event_args[0] if isinstance(event_args, (tuple, list)) else event_args
        except Exception:
            return
        if not hasattr(ev, 'button'):
            return
        # Only right button for measure tool (requires cursors soft-key ON)
        if ev.button() != Qt.RightButton:
            return
        if not self._cursors_on:
            return
        if hasattr(ev, 'accept'):
            ev.accept()
        pos = self._map_scene_to_data(ev.scenePos())
        if pos is None:
            return
        x, y = pos
        # Snap Y to primary waveform sample at this time when available
        ch = self._primary_channel()
        if ch:
            vy = self._y_at_x(ch, x)
            if vy is not None:
                y = vy
        if self._meas_start is None:
            self._meas_start = (x, y)
            self._meas_scatter.setData([x], [y])
            self._meas_curve.setData([x], [y])
            self._meas_label.setText('…')
            self._meas_label.setPos(x, y)
            self._meas_label.show()
            tip = self._tr_meas_start(x, y)
            self._set_hud(tip, keep_cursor=True)
        else:
            x0, y0 = self._meas_start
            self._finalize_measure(x0, y0, x, y)
            self._meas_start = None

    def _on_mouse_moved(self, event_args) -> None:
        if self._meas_start is None or self._plot is None:
            return
        try:
            pos = event_args[0] if isinstance(event_args, (tuple, list)) else event_args
        except Exception:
            return
        mapped = self._map_scene_to_data(pos)
        if mapped is None:
            return
        x, y = mapped
        x0, y0 = self._meas_start
        ch = self._primary_channel()
        if ch:
            vy = self._y_at_x(ch, x)
            if vy is not None:
                y = vy
        self._meas_curve.setData([x0, x], [y0, y])
        self._meas_scatter.setData([x0, x], [y0, y])
        preview = self._format_measure(x0, y0, x, y)
        self._meas_label.setText(preview.replace('  |  ', '\n'))
        self._meas_label.setPos(x, y)
        self._set_hud(preview, keep_cursor=True)

    def _finalize_measure(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self._meas_curve.setData([x0, x1], [y0, y1])
        self._meas_scatter.setData([x0, x1], [y0, y1])
        text = self._format_measure(x0, y0, x1, y1)
        self._meas_label.setText(text.replace('  |  ', '\n'))
        self._meas_label.setPos(x1, y1)
        self._meas_label.show()
        self._set_hud(text, keep_cursor=True)
        self.measureReadoutChanged.emit(text)

    def _format_measure(self, x0: float, y0: float, x1: float, y1: float) -> str:
        dt = x1 - x0
        dy = y1 - y0
        yu = self._y_unit()
        kind = '电流' if yu == 'A' else '电压'
        parts = [
            f'Δt={_fmt_eng(dt, "s")}',
            f'Δ{kind}={_fmt_eng(dy, yu)}',
            f'起点=({_fmt_eng(x0, "s")}, {_fmt_eng(y0, yu)})',
            f'终点=({_fmt_eng(x1, "s")}, {_fmt_eng(y1, yu)})',
        ]
        if abs(dt) > 0:
            parts.insert(1, f'1/Δt={abs(1.0 / dt):.4g} Hz')
        # Also report primary-channel samples at the two times
        ch = self._primary_channel()
        if ch:
            v0 = self._y_at_x(ch, x0)
            v1 = self._y_at_x(ch, x1)
            if v0 is not None and v1 is not None:
                chu = _normalize_y_unit(self._wave_meta.get(ch, {}).get('y_unit', yu))
                parts.append(f'{ch}采样Δ={_fmt_eng(v1 - v0, chu)}')
        return '  |  '.join(parts)

    def _tr_meas_start(self, x: float, y: float) -> str:
        yu = self._y_unit()
        return f'测距起点 {_fmt_eng(x, "s")}, {_fmt_eng(y, yu)}  — 再右键定点'

    def _set_hud(self, text: str, *, keep_cursor: bool = False) -> None:
        if not text:
            if self._cursors_on and keep_cursor:
                self._update_cursor_readout()
                return
            self._hud.hide()
            self._hud.setText('')
            return
        if self._cursors_on and keep_cursor:
            # Show measure on top; cursor details stay available via signal
            self._hud.setText(text)
        else:
            self._hud.setText(text)
        self._hud.show()
