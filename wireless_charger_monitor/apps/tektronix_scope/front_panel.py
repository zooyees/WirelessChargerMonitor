"""MDO3000-style front-panel chrome — layout aligned to real instrument."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...i18n import tr
from .knobs import KnobControl
from .wave_plot import CHANNEL_COLORS, ScopeWaveformPlot

# Touch-friendly minimums (also comfortable for mouse)
_BTN_H = 34
_BTN_H_COMPACT = 26
_MENU_W = 148
_SIDE_W = 200
_VERT_W = 252  # room for dual knobs + ± without scrollbar clip
_DOCK_KNOB = 34
_DOCK_MOD_MIN_H = 118
_CH_KNOB = 40


def _menu_btn(text: str, checkable: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setCheckable(checkable)
    btn.setMinimumHeight(_BTN_H)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setProperty('tekRole', 'menu')
    btn.setFocusPolicy(Qt.StrongFocus)
    return btn


def _action_btn(text: str, *, checkable: bool = False, accent: bool = False, compact: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setCheckable(checkable)
    btn.setMinimumHeight(_BTN_H_COMPACT if compact else _BTN_H)
    btn.setMinimumWidth(56 if compact else 76)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setProperty('tekRole', 'accent' if accent else 'action')
    btn.setFocusPolicy(Qt.StrongFocus)
    return btn


class TekFrontPanel(QWidget):
    """
    Layout mirrors MDO3000 physical front panel (User Manual §熟悉仪器):

      [连接+功能键 | 波形屏 + 侧菜单 | 垂直 CH]
      [前面板控制坞（仅左侧，不侵占垂直栏）]
    """

    connectClicked = pyqtSignal()
    refreshWaveClicked = pyqtSignal()
    hardcopyClicked = pyqtSignal(int)
    liveToggled = pyqtSignal(bool)

    runStopClicked = pyqtSignal()
    singleClicked = pyqtSignal()
    forceTriggerClicked = pyqtSignal()
    autosetClicked = pyqtSignal()
    defaultSetupClicked = pyqtSignal()

    channelMenuClicked = pyqtSignal(str)
    channelScaleRotated = pyqtSignal(str, int)
    channelPositionRotated = pyqtSignal(str, int)
    channelPositionPushed = pyqtSignal(str)

    horizScaleRotated = pyqtSignal(int)
    horizPositionRotated = pyqtSignal(int)
    horizPositionPushed = pyqtSignal()
    triggerLevelRotated = pyqtSignal(int)
    triggerLevelPushed = pyqtSignal()

    fineToggled = pyqtSignal(bool)
    multiARotated = pyqtSignal(int)
    multiBRotated = pyqtSignal(int)
    selectClicked = pyqtSignal()

    menuClicked = pyqtSignal(str)
    cursorClicked = pyqtSignal()
    zoomClicked = pyqtSignal()
    markPrevClicked = pyqtSignal()
    markNextClicked = pyqtSignal()
    markSetClearClicked = pyqtSignal()
    playPauseClicked = pyqtSignal()
    intensityClicked = pyqtSignal()
    menuOffClicked = pyqtSignal()
    saveClicked = pyqtSignal()
    digitalClicked = pyqtSignal()
    panRotated = pyqtSignal(int)
    zoomScaleRotated = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.fine_mode = False
        self._ch_on: dict[str, bool] = {f'CH{i}': False for i in range(1, 5)}
        self._build()

    # ── public API ───────────────────────────────────────────────────────

    def set_model_text(self, text: str) -> None:
        self.model_edit.setText(text)

    def append_log(self, msg: str) -> None:
        self.log_edit.append(msg)
        if not self.log_edit.isVisible():
            self.btn_log_toggle.setChecked(True)
            self.log_edit.show()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_readouts(self, lines: dict[str, str]) -> None:
        for key, label in self._readouts.items():
            if key in lines:
                label.setText(lines[key])

    def set_channel_active(self, channel: str, on: bool) -> None:
        ch = channel.upper()
        self._ch_on[ch] = on
        btn = self.channel_btns.get(ch)
        if btn is not None:
            btn.setChecked(on)

    def set_run_state(self, running: bool) -> None:
        self.btn_run_stop.setChecked(running)
        self.btn_run_stop.setText(
            tr('tool.tektronix_scope.stop') if running else tr('tool.tektronix_scope.run_stop')
        )

    def retranslate_ui(self) -> None:
        """Refresh all visible labels for current language."""
        self.btn_connect.setText(tr('tool.tektronix_scope.connect'))
        self.btn_refresh.setText(tr('tool.tektronix_scope.refresh_wave'))
        self.btn_live.setText(tr('tool.tektronix_scope.live'))
        self.btn_live.setToolTip(tr('tool.tektronix_scope.live_tip'))
        self.btn_shot.setText(tr('tool.tektronix_scope.capture_shot'))
        for i in range(self.scope_index.count()):
            self.scope_index.setItemText(i, tr('tool.tektronix_scope.scope_n', n=i + 1))
        if not self.status_label.text() or self.status_label.text() in (
            '未连接', 'Disconnected', '—',
        ):
            self.status_label.setText(tr('tool.tektronix_scope.status_disconnected'))

        self.grp_session.setTitle(tr('tool.tektronix_scope.grp_session'))
        self.grp_function.setTitle(tr('tool.tektronix_scope.grp_function'))
        self.grp_vertical.setTitle(tr('tool.tektronix_scope.grp_vertical'))
        self.grp_multipurpose.setTitle(tr('tool.tektronix_scope.grp_multipurpose'))
        self.grp_dock.setTitle(tr('tool.tektronix_scope.grp_dock'))
        self.lbl_sec_acquire.setText(tr('tool.tektronix_scope.grp_acquire_ctrl'))
        self.lbl_sec_horiz.setText(tr('tool.tektronix_scope.grp_horizontal'))
        self.lbl_sec_trig.setText(tr('tool.tektronix_scope.grp_trigger'))
        self.lbl_sec_nav.setText(tr('tool.tektronix_scope.grp_wave_inspector'))
        self.lbl_sec_soft.setText(tr('tool.tektronix_scope.grp_softkeys'))

        menu_keys = {
            'measure': 'tool.tektronix_scope.menu_measure',
            'search': 'tool.tektronix_scope.menu_search',
            'acquire': 'tool.tektronix_scope.menu_acquire',
            'trigger': 'tool.tektronix_scope.menu_trigger',
            'math': 'tool.tektronix_scope.menu_math',
            'ref': 'tool.tektronix_scope.menu_ref',
            'afg': 'tool.tektronix_scope.menu_afg',
            'rf': 'tool.tektronix_scope.menu_rf',
            'test': 'tool.tektronix_scope.menu_test',
        }
        for key, i18n_key in menu_keys.items():
            btn = self.menu_btns.get(key)
            if btn is not None:
                btn.setText(tr(i18n_key))

        self.side_placeholder.setText(tr('tool.tektronix_scope.side_placeholder'))
        self.btn_side_menu_off.setText(tr('tool.tektronix_scope.menu_off'))
        self.btn_preview_toggle.setText(
            tr('tool.tektronix_scope.preview_hide')
            if self.btn_preview_toggle.isChecked()
            else tr('tool.tektronix_scope.preview_show')
        )
        if self.preview_label.pixmap() is None or self.preview_label.pixmap().isNull():
            self.preview_label.setText(tr('tool.tektronix_scope.preview_empty'))

        for ch, btn in self.channel_btns.items():
            btn.setToolTip(tr('tool.tektronix_scope.ch_tip', ch=ch))
            pos = self.ch_pos_knobs[ch]
            scale = self.ch_scale_knobs[ch]
            pos.set_label(tr('tool.tektronix_scope.knob_position'))
            pos.set_push_text(tr('tool.tektronix_scope.knob_center'))
            pos.set_push_tooltip(tr('tool.tektronix_scope.push_tip'))
            pos.setToolTip(tr('tool.tektronix_scope.pos_tip', ch=ch))
            scale.set_label(tr('tool.tektronix_scope.knob_scale'))
            scale.setToolTip(tr('tool.tektronix_scope.scale_tip', ch=ch))

        self.knob_a.set_label(tr('tool.tektronix_scope.knob_a'))
        self.knob_b.set_label(tr('tool.tektronix_scope.knob_b'))
        self.btn_fine.setText(tr('tool.tektronix_scope.fine'))
        self.btn_fine.setToolTip(tr('tool.tektronix_scope.fine_tip'))
        self.btn_select.setText(tr('tool.tektronix_scope.select'))
        self.btn_select.setToolTip(tr('tool.tektronix_scope.select_tip'))

        self.btn_save_recall.setText(tr('tool.tektronix_scope.save_recall'))
        self.btn_default.setText(tr('tool.tektronix_scope.default_setup'))
        self.btn_utility.setText(tr('tool.tektronix_scope.utility'))
        self.btn_bus1.setText(tr('tool.tektronix_scope.bus1'))
        self.btn_bus2.setText(tr('tool.tektronix_scope.bus2'))
        self.btn_ref.setText(tr('tool.tektronix_scope.ref'))
        self.btn_math.setText(tr('tool.tektronix_scope.math'))
        self.btn_cursor.setText(tr('tool.tektronix_scope.cursors'))
        self.btn_cursor.setToolTip(tr('tool.tektronix_scope.cursors_tip'))
        self.btn_intensity.setText(tr('tool.tektronix_scope.intensity'))
        self.btn_digital.setText(tr('tool.tektronix_scope.digital'))
        self.btn_save.setText(tr('tool.tektronix_scope.save'))
        self.btn_menu_off.setText(tr('tool.tektronix_scope.menu_off'))

        self.btn_zoom.setText(tr('tool.tektronix_scope.zoom'))
        self.btn_zoom.setToolTip(tr('tool.tektronix_scope.zoom_tip'))
        self.knob_pan.set_label(tr('tool.tektronix_scope.knob_pan'))
        self.knob_zoom_scale.set_label(tr('tool.tektronix_scope.knob_zoom_scale'))
        self.btn_mark_prev.setText(tr('tool.tektronix_scope.mark_prev'))
        self.btn_mark_set.setText(tr('tool.tektronix_scope.mark_set'))
        self.btn_mark_next.setText(tr('tool.tektronix_scope.mark_next'))
        self.btn_play.setText(tr('tool.tektronix_scope.play_pause'))

        self.knob_hpos.set_label(tr('tool.tektronix_scope.knob_hpos'))
        self.btn_hpos_push.setText(tr('tool.tektronix_scope.knob_hpos_push'))
        self.btn_hpos_push.setToolTip(tr('tool.tektronix_scope.push_tip'))
        self.knob_hscale.set_label(tr('tool.tektronix_scope.knob_hscale'))
        self.knob_trig.set_label(tr('tool.tektronix_scope.knob_trig'))
        self.btn_trig_push.setText(tr('tool.tektronix_scope.knob_trig_push'))
        self.btn_trig_push.setToolTip(tr('tool.tektronix_scope.push_tip'))
        self.btn_force.setText(tr('tool.tektronix_scope.force_trigger'))
        self.btn_autoset.setText(tr('tool.tektronix_scope.autoset'))
        self.btn_autoset.setToolTip(tr('tool.tektronix_scope.autoset_tip'))
        self.btn_single.setText(tr('tool.tektronix_scope.single'))
        self.btn_run_stop.setToolTip(tr('tool.tektronix_scope.run_stop_tip'))
        self.set_run_state(self.btn_run_stop.isChecked())

        self.btn_log_toggle.setText(
            tr('tool.tektronix_scope.log_hide')
            if self.btn_log_toggle.isChecked()
            else tr('tool.tektronix_scope.log_show')
        )
        self.log_edit.setPlaceholderText(tr('tool.tektronix_scope.log_placeholder'))

    def show_side_menu(self, title: str, widget: QWidget | None) -> None:
        self.side_title.setText(title)
        while self.side_stack.count() > 1:
            w = self.side_stack.widget(1)
            self.side_stack.removeWidget(w)
            w.deleteLater()
        if widget is None:
            self.side_stack.setCurrentIndex(0)
            self.side_frame.hide()
            return
        self.side_stack.addWidget(widget)
        self.side_stack.setCurrentIndex(1)
        self.side_frame.show()

    def hide_side_menu(self) -> None:
        self.show_side_menu('', None)

    # ── build ────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        root.addWidget(self._build_workspace(), stretch=1)
        root.addWidget(self._build_log_row(), stretch=0)

        self.hide_side_menu()

    def _build_workspace(self) -> QWidget:
        """
        Grid: left | scope | side-menu | vertical(span 2 rows).
        Vertical bottom aligns with the front-panel dock bottom.
        """
        wrap = QWidget()
        grid = QGridLayout(wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)

        left = self._build_left_rail()
        display = self._build_display_area()
        side = self._build_side_menu_frame()
        vertical = self._build_right_vertical()
        dock = self._build_control_dock()

        # Row 0–1: vertical spans full height (scope + front panel), bottom flush with dock
        grid.addWidget(left, 0, 0)
        grid.addWidget(display, 0, 1)
        grid.addWidget(side, 0, 2)
        grid.addWidget(vertical, 0, 3, 2, 1)
        grid.setRowStretch(0, 1)
        grid.setRowMinimumHeight(0, 320)

        # Row 1: control dock under cols 0–2 only (vertical already occupies col 3)
        dock_cell = QWidget()
        dock_cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        dock_lay = QHBoxLayout(dock_cell)
        dock_lay.setContentsMargins(0, 0, 0, 0)
        dock_lay.setSpacing(0)
        dock.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        dock_lay.addWidget(dock)
        grid.addWidget(dock_cell, 1, 0, 1, 3)

        grid.setRowStretch(1, 0)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 0)
        return wrap

    def _build_left_rail(self) -> QWidget:
        """
        Left column: session controls (was top bar) + function keys.
        Saves a full row of vertical space for the waveform.
        """
        rail = QWidget()
        rail.setFixedWidth(_MENU_W)
        rail.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        root = QVBoxLayout(rail)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # ── Session / connect ────────────────────────────────────────────
        self.grp_session = QGroupBox(tr('tool.tektronix_scope.grp_session'))
        self.grp_session.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        slay = QVBoxLayout(self.grp_session)
        slay.setContentsMargins(5, 10, 5, 5)
        slay.setSpacing(4)

        self.btn_connect = _action_btn(tr('tool.tektronix_scope.connect'), accent=True)
        self.btn_connect.setMinimumHeight(_BTN_H)
        self.btn_connect.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_connect.clicked.connect(self.connectClicked.emit)
        slay.addWidget(self.btn_connect)

        self.model_edit = QLabel('—')
        self.model_edit.setObjectName('tek_scope_model')
        self.model_edit.setMinimumHeight(26)
        self.model_edit.setMaximumHeight(40)
        self.model_edit.setAlignment(Qt.AlignCenter)
        self.model_edit.setWordWrap(True)
        self.model_edit.setToolTip(tr('tool.tektronix_scope.model_tip'))
        self.model_edit.setStyleSheet(
            'QLabel#tek_scope_model{background:#0F172A;border:1px solid #64748B;'
            'border-radius:4px;padding:2px 4px;color:#FFFFFF;font-weight:700;font-size:11px;}'
        )
        slay.addWidget(self.model_edit)

        self.scope_index = QComboBox()
        self.scope_index.addItems([
            tr('tool.tektronix_scope.scope_n', n=1),
            tr('tool.tektronix_scope.scope_n', n=2),
        ])
        self.scope_index.setMinimumHeight(28)
        self.scope_index.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        slay.addWidget(self.scope_index)

        # Wave ops: 刷新 | 实时 / 截图 (2×2-ish grid for balance)
        self.btn_refresh = _action_btn(tr('tool.tektronix_scope.refresh_wave'), compact=True)
        self.btn_refresh.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_refresh.setToolTip(tr('tool.tektronix_scope.refresh_wave_tip'))
        self.btn_refresh.clicked.connect(self.refreshWaveClicked.emit)
        self.btn_live = _action_btn(tr('tool.tektronix_scope.live'), checkable=True, accent=True, compact=True)
        self.btn_live.setToolTip(tr('tool.tektronix_scope.live_tip'))
        self.btn_live.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_live.toggled.connect(self.liveToggled.emit)
        self.btn_shot = _action_btn(tr('tool.tektronix_scope.capture_shot'), compact=True)
        self.btn_shot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_shot.setToolTip(tr('tool.tektronix_scope.capture_shot_tip'))
        self.btn_shot.clicked.connect(lambda: self.hardcopyClicked.emit(self.scope_index.currentIndex()))

        wave_grid = QGridLayout()
        wave_grid.setContentsMargins(0, 0, 0, 0)
        wave_grid.setHorizontalSpacing(3)
        wave_grid.setVerticalSpacing(3)
        wave_grid.addWidget(self.btn_refresh, 0, 0)
        wave_grid.addWidget(self.btn_live, 0, 1)
        wave_grid.addWidget(self.btn_shot, 1, 0, 1, 2)
        slay.addLayout(wave_grid)

        self.status_label = QLabel(tr('tool.tektronix_scope.status_disconnected'))
        self.status_label.setStyleSheet(
            'color:#E2E8F0;padding:2px 1px;font-weight:600;font-size:10px;'
        )
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.status_label.setMaximumHeight(36)
        slay.addWidget(self.status_label)

        root.addWidget(self.grp_session, stretch=0)

        # ── Function keys ────────────────────────────────────────────────
        self.grp_function = QGroupBox(tr('tool.tektronix_scope.grp_function'))
        self.grp_function.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        flay = QVBoxLayout(self.grp_function)
        flay.setSpacing(3)
        flay.setContentsMargins(5, 10, 5, 5)

        menus = [
            ('measure', 'tool.tektronix_scope.menu_measure'),
            ('search', 'tool.tektronix_scope.menu_search'),
            ('acquire', 'tool.tektronix_scope.menu_acquire'),
            ('trigger', 'tool.tektronix_scope.menu_trigger'),
            ('math', 'tool.tektronix_scope.menu_math'),
            ('ref', 'tool.tektronix_scope.menu_ref'),
            ('afg', 'tool.tektronix_scope.menu_afg'),
            ('rf', 'tool.tektronix_scope.menu_rf'),
            ('test', 'tool.tektronix_scope.menu_test'),
        ]
        self.menu_btns: dict[str, QPushButton] = {}
        for key, i18n_key in menus:
            btn = _menu_btn(tr(i18n_key))
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setMinimumHeight(26)
            btn.setMaximumHeight(44)
            btn.clicked.connect(lambda _=False, k=key: self.menuClicked.emit(k))
            self.menu_btns[key] = btn
            flay.addWidget(btn, stretch=1)

        root.addWidget(self.grp_function, stretch=1)
        return rail

    def _build_display_area(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName('tek_display')
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame.setStyleSheet(
            'QFrame#tek_display{background:#0B1220;border:2px solid #475569;border-radius:4px;}'
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)

        strip = QHBoxLayout()
        strip.setSpacing(8)
        self._readouts: dict[str, QLabel] = {}
        for key in ('acquire', 'trigger', 'sample', 'horiz', 'ch1', 'ch2', 'ch3', 'ch4'):
            lab = QLabel('—')
            lab.setStyleSheet('color:#F8FAFC;font-size:11px;font-weight:600;')
            lab.setMinimumHeight(18)
            self._readouts[key] = lab
            strip.addWidget(lab)
        strip.addStretch(1)
        lay.addLayout(strip)

        self.wave_plot = ScopeWaveformPlot()
        self.wave_plot.setMinimumHeight(280)
        self.wave_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.wave_plot, stretch=1)

        # Screenshot as collapsible strip (don't steal waveform space by default)
        prev_row = QHBoxLayout()
        self.btn_preview_toggle = QToolButton()
        self.btn_preview_toggle.setText(tr('tool.tektronix_scope.preview_show'))
        self.btn_preview_toggle.setCheckable(True)
        self.btn_preview_toggle.setMinimumHeight(26)
        self.btn_preview_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_preview_toggle.setStyleSheet('color:#F8FAFC;font-weight:600;')
        self.preview_label = QLabel(tr('tool.tektronix_scope.preview_empty'))
        self.preview_label.setObjectName('tek_scope_preview')
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMaximumHeight(140)
        self.preview_label.setMinimumHeight(80)
        self.preview_label.setStyleSheet('background:#020617;color:#94A3B8;')
        self.preview_label.setScaledContents(True)
        self.preview_label.hide()
        self.btn_preview_toggle.toggled.connect(self._toggle_preview)
        prev_row.addWidget(self.btn_preview_toggle)
        prev_row.addStretch(1)
        lay.addLayout(prev_row)
        lay.addWidget(self.preview_label)
        return frame

    def _toggle_preview(self, on: bool) -> None:
        self.preview_label.setVisible(on)
        self.btn_preview_toggle.setText(
            tr('tool.tektronix_scope.preview_hide') if on else tr('tool.tektronix_scope.preview_show')
        )

    def _build_side_menu_frame(self) -> QWidget:
        """Bezel side menu — sits at right edge of screen like real MDO."""
        self.side_frame = QFrame()
        self.side_frame.setObjectName('tek_side_menu')
        self.side_frame.setFixedWidth(_SIDE_W)
        self.side_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.side_frame.setStyleSheet(
            'QFrame#tek_side_menu{background:#1E293B;border:1px solid #64748B;border-radius:4px;}'
        )
        lay = QVBoxLayout(self.side_frame)
        lay.setContentsMargins(6, 6, 6, 6)
        self.side_title = QLabel('')
        self.side_title.setStyleSheet('font-weight:700;color:#FFFFFF;font-size:13px;')
        lay.addWidget(self.side_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.side_stack = QStackedWidget()
        self.side_placeholder = QLabel(tr('tool.tektronix_scope.side_placeholder'))
        self.side_placeholder.setAlignment(Qt.AlignCenter)
        self.side_placeholder.setStyleSheet('color:#CBD5E1;')
        self.side_stack.addWidget(self.side_placeholder)
        scroll.setWidget(self.side_stack)
        lay.addWidget(scroll, stretch=1)

        self.btn_side_menu_off = _action_btn(tr('tool.tektronix_scope.menu_off'))
        self.btn_side_menu_off.clicked.connect(self.menuOffClicked.emit)
        lay.addWidget(self.btn_side_menu_off)
        return self.side_frame

    def _build_right_vertical(self) -> QWidget:
        """
        Vertical channel strip — same height as the scope window (grid row 0).
        Wide enough for dual knobs + ± without clipping.
        """
        wrap = QWidget()
        wrap.setFixedWidth(_VERT_W)
        wrap.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        wrap_lay = QVBoxLayout(wrap)
        wrap_lay.setContentsMargins(0, 0, 0, 0)
        wrap_lay.setSpacing(0)

        self.grp_vertical = QGroupBox(tr('tool.tektronix_scope.grp_vertical'))
        self.grp_vertical.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer = QVBoxLayout(self.grp_vertical)
        outer.setSpacing(4)
        outer.setContentsMargins(6, 12, 6, 6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        inner = QWidget()
        inner.setMinimumWidth(_VERT_W - 28)
        lay = QVBoxLayout(inner)
        lay.setSpacing(6)
        lay.setContentsMargins(2, 2, 8, 2)  # right pad keeps ± clear of scrollbar

        self.channel_btns: dict[str, QPushButton] = {}
        self.ch_pos_knobs: dict[str, KnobControl] = {}
        self.ch_scale_knobs: dict[str, KnobControl] = {}

        for i in range(1, 5):
            ch = f'CH{i}'
            color = CHANNEL_COLORS[ch]
            ch_box = QFrame()
            ch_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            ch_box.setStyleSheet(
                f'QFrame{{border:1px solid {color}88;border-radius:6px;background:#0F172A;}}'
            )
            ch_lay = QVBoxLayout(ch_box)
            ch_lay.setContentsMargins(6, 4, 6, 4)
            ch_lay.setSpacing(3)

            btn = _menu_btn(ch, checkable=True)
            btn.setStyleSheet(
                f'QPushButton{{color:{color};font-weight:700;min-height:{_BTN_H - 6}px;}}'
                f'QPushButton:checked{{background:{color};color:#0F172A;}}'
            )
            btn.setToolTip(tr('tool.tektronix_scope.ch_tip', ch=ch))
            btn.clicked.connect(lambda _=False, c=ch: self.channelMenuClicked.emit(c))
            self.channel_btns[ch] = btn
            ch_lay.addWidget(btn)

            pos = KnobControl(
                tr('tool.tektronix_scope.knob_position'),
                accent=color,
                diameter=_CH_KNOB,
                push_enabled=True,
                push_text=tr('tool.tektronix_scope.knob_center'),
                compact=True,
            )
            scale = KnobControl(
                tr('tool.tektronix_scope.knob_scale'),
                accent=color,
                diameter=_CH_KNOB,
                push_enabled=False,
                compact=True,
            )
            pos.setToolTip(tr('tool.tektronix_scope.pos_tip', ch=ch))
            scale.setToolTip(tr('tool.tektronix_scope.scale_tip', ch=ch))
            pos.set_push_tooltip(tr('tool.tektronix_scope.push_tip'))
            pos.rotated.connect(lambda d, c=ch: self.channelPositionRotated.emit(c, d))
            pos.pushClicked.connect(lambda c=ch: self.channelPositionPushed.emit(c))
            scale.rotated.connect(lambda d, c=ch: self.channelScaleRotated.emit(c, d))
            self.ch_pos_knobs[ch] = pos
            self.ch_scale_knobs[ch] = scale
            knobs = QHBoxLayout()
            knobs.setSpacing(6)
            knobs.setContentsMargins(0, 0, 0, 0)
            knobs.addStretch(1)
            knobs.addWidget(pos)
            knobs.addWidget(scale)
            knobs.addStretch(1)
            ch_lay.addLayout(knobs, stretch=1)
            lay.addWidget(ch_box, stretch=3)

        self.grp_multipurpose = QGroupBox(tr('tool.tektronix_scope.grp_multipurpose'))
        self.grp_multipurpose.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        mlay = QVBoxLayout(self.grp_multipurpose)
        mlay.setSpacing(3)
        mlay.setContentsMargins(4, 8, 4, 4)
        ab = QHBoxLayout()
        ab.setSpacing(6)
        ab.addStretch(1)
        self.knob_a = KnobControl(
            tr('tool.tektronix_scope.knob_a'), accent='#F59E0B', diameter=_CH_KNOB, push_enabled=False, compact=True
        )
        self.knob_b = KnobControl(
            tr('tool.tektronix_scope.knob_b'), accent='#F59E0B', diameter=_CH_KNOB, push_enabled=False, compact=True
        )
        self.knob_a.rotated.connect(self.multiARotated.emit)
        self.knob_b.rotated.connect(self.multiBRotated.emit)
        ab.addWidget(self.knob_a)
        ab.addWidget(self.knob_b)
        ab.addStretch(1)
        mlay.addLayout(ab)
        fb = QHBoxLayout()
        self.btn_fine = _menu_btn(tr('tool.tektronix_scope.fine'), checkable=True)
        self.btn_fine.setToolTip(tr('tool.tektronix_scope.fine_tip'))
        self.btn_fine.toggled.connect(self._on_fine)
        self.btn_select = _menu_btn(tr('tool.tektronix_scope.select'))
        self.btn_select.clicked.connect(self.selectClicked.emit)
        fb.addWidget(self.btn_fine)
        fb.addWidget(self.btn_select)
        mlay.addLayout(fb)
        lay.addWidget(self.grp_multipurpose, stretch=2)

        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)
        wrap_lay.addWidget(self.grp_vertical)
        return wrap

    def _on_fine(self, on: bool) -> None:
        self.fine_mode = on
        self.fineToggled.emit(on)

    def _section_label(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet(
            'color:#F8FAFC;font-size:10px;font-weight:700;padding:0;'
            'background:transparent;'
        )
        lab.setAlignment(Qt.AlignCenter)
        lab.setFixedHeight(16)
        return lab

    def _dock_module(self, title: str) -> tuple[QFrame, QVBoxLayout, QLabel]:
        """Equal-weight module card for the control dock."""
        frame = QFrame()
        frame.setObjectName('tek_dock_mod')
        frame.setMinimumHeight(_DOCK_MOD_MIN_H)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        frame.setStyleSheet(
            'QFrame#tek_dock_mod{'
            'background:#0F172A;border:1px solid #475569;border-radius:5px;}'
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(2)
        title_lab = self._section_label(title)
        lay.addWidget(title_lab)
        return frame, lay, title_lab

    def _dock_fill_btn(self, btn: QPushButton) -> QPushButton:
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        btn.setMinimumHeight(_BTN_H_COMPACT)
        return btn

    def _dock_knob(self, label: str, accent: str) -> KnobControl:
        return KnobControl(
            label,
            accent=accent,
            diameter=_DOCK_KNOB,
            push_enabled=False,
            compact=True,
        )

    def _build_control_dock(self) -> QWidget:
        """
        Single-row modular dock: Acquire | Horizontal | Trigger | Navigator | Soft Keys.
        Equal column stretch, matching module height, no dead stretch gaps.
        """
        self.grp_dock = QGroupBox(tr('tool.tektronix_scope.grp_dock'))
        self.grp_dock.setObjectName('tek_control_dock')
        self.grp_dock.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.grp_dock.setStyleSheet(
            'QGroupBox#tek_control_dock{'
            'padding-top:8px;margin-top:1px;font-weight:700;}'
        )
        root = QHBoxLayout(self.grp_dock)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ── 采集 ─────────────────────────────────────────────────────────
        mod_acq, lay_acq, self.lbl_sec_acquire = self._dock_module(
            tr('tool.tektronix_scope.grp_acquire_ctrl')
        )
        self.btn_autoset = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.autoset'), accent=True, compact=True)
        )
        self.btn_autoset.setToolTip(tr('tool.tektronix_scope.autoset_tip'))
        self.btn_autoset.clicked.connect(self.autosetClicked.emit)
        self.btn_single = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.single'), compact=True)
        )
        self.btn_single.clicked.connect(self.singleClicked.emit)
        self.btn_run_stop = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.run_stop'), checkable=True, accent=True, compact=True)
        )
        self.btn_run_stop.setToolTip(tr('tool.tektronix_scope.run_stop_tip'))
        self.btn_run_stop.clicked.connect(self.runStopClicked.emit)
        for b in (self.btn_autoset, self.btn_single, self.btn_run_stop):
            lay_acq.addWidget(b, stretch=1)

        # ── 水平 ─────────────────────────────────────────────────────────
        mod_horiz, lay_horiz, self.lbl_sec_horiz = self._dock_module(
            tr('tool.tektronix_scope.grp_horizontal')
        )
        hk = QHBoxLayout()
        hk.setSpacing(2)
        hk.setAlignment(Qt.AlignCenter)
        self.knob_hpos = self._dock_knob(tr('tool.tektronix_scope.knob_hpos'), '#38BDF8')
        self.knob_hscale = self._dock_knob(tr('tool.tektronix_scope.knob_hscale'), '#38BDF8')
        self.knob_hpos.rotated.connect(self.horizPositionRotated.emit)
        self.knob_hscale.rotated.connect(self.horizScaleRotated.emit)
        hk.addWidget(self.knob_hpos)
        hk.addWidget(self.knob_hscale)
        lay_horiz.addLayout(hk, stretch=1)
        self.btn_hpos_push = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.knob_hpos_push'), compact=True)
        )
        self.btn_hpos_push.setToolTip(tr('tool.tektronix_scope.push_tip'))
        self.btn_hpos_push.clicked.connect(self.horizPositionPushed.emit)
        lay_horiz.addWidget(self.btn_hpos_push)

        # ── 触发 ─────────────────────────────────────────────────────────
        mod_trig, lay_trig, self.lbl_sec_trig = self._dock_module(
            tr('tool.tektronix_scope.grp_trigger')
        )
        trig_mid = QHBoxLayout()
        trig_mid.setSpacing(4)
        trig_mid.setAlignment(Qt.AlignCenter)
        self.knob_trig = self._dock_knob(tr('tool.tektronix_scope.knob_trig'), '#F87171')
        self.knob_trig.rotated.connect(self.triggerLevelRotated.emit)
        trig_btns = QVBoxLayout()
        trig_btns.setSpacing(2)
        self.btn_trig_push = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.knob_trig_push'), compact=True)
        )
        self.btn_trig_push.setToolTip(tr('tool.tektronix_scope.push_tip'))
        self.btn_trig_push.clicked.connect(self.triggerLevelPushed.emit)
        self.btn_force = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.force_trigger'), compact=True)
        )
        self.btn_force.clicked.connect(self.forceTriggerClicked.emit)
        trig_btns.addWidget(self.btn_trig_push, stretch=1)
        trig_btns.addWidget(self.btn_force, stretch=1)
        trig_mid.addWidget(self.knob_trig)
        trig_mid.addLayout(trig_btns, stretch=1)
        lay_trig.addLayout(trig_mid, stretch=1)

        # ── 导航 ─────────────────────────────────────────────────────────
        mod_nav, lay_nav, self.lbl_sec_nav = self._dock_module(
            tr('tool.tektronix_scope.grp_wave_inspector')
        )
        nav_top = QHBoxLayout()
        nav_top.setSpacing(2)
        self.btn_zoom = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.zoom'), checkable=True, compact=True)
        )
        self.btn_zoom.setToolTip(tr('tool.tektronix_scope.zoom_tip'))
        self.btn_zoom.clicked.connect(self.zoomClicked.emit)
        self.knob_pan = self._dock_knob(tr('tool.tektronix_scope.knob_pan'), '#A78BFA')
        self.knob_zoom_scale = self._dock_knob(tr('tool.tektronix_scope.knob_zoom_scale'), '#A78BFA')
        self.knob_pan.rotated.connect(self.panRotated.emit)
        self.knob_zoom_scale.rotated.connect(self.zoomScaleRotated.emit)
        nav_top.addWidget(self.btn_zoom, stretch=1)
        nav_top.addWidget(self.knob_pan)
        nav_top.addWidget(self.knob_zoom_scale)
        lay_nav.addLayout(nav_top, stretch=1)

        nav_bot = QHBoxLayout()
        nav_bot.setSpacing(2)
        self.btn_mark_prev = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.mark_prev'), compact=True)
        )
        self.btn_mark_prev.clicked.connect(self.markPrevClicked.emit)
        self.btn_mark_set = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.mark_set'), compact=True)
        )
        self.btn_mark_set.clicked.connect(self.markSetClearClicked.emit)
        self.btn_mark_next = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.mark_next'), compact=True)
        )
        self.btn_mark_next.clicked.connect(self.markNextClicked.emit)
        self.btn_play = self._dock_fill_btn(
            _action_btn(tr('tool.tektronix_scope.play_pause'), checkable=True, compact=True)
        )
        self.btn_play.clicked.connect(self.playPauseClicked.emit)
        for b in (self.btn_mark_prev, self.btn_mark_set, self.btn_mark_next, self.btn_play):
            nav_bot.addWidget(b, stretch=1)
        lay_nav.addLayout(nav_bot, stretch=1)

        # ── 软键（3×4 均匀网格）─────────────────────────────────────────
        mod_soft, lay_soft, self.lbl_sec_soft = self._dock_module(
            tr('tool.tektronix_scope.grp_softkeys')
        )
        soft_grid = QGridLayout()
        soft_grid.setContentsMargins(0, 0, 0, 0)
        soft_grid.setHorizontalSpacing(2)
        soft_grid.setVerticalSpacing(2)
        for c in range(4):
            soft_grid.setColumnStretch(c, 1)
        for r in range(3):
            soft_grid.setRowStretch(r, 1)

        self.btn_save_recall = _action_btn(tr('tool.tektronix_scope.save_recall'), compact=True)
        self.btn_save_recall.clicked.connect(lambda: self.menuClicked.emit('save_recall'))
        self.btn_default = _action_btn(tr('tool.tektronix_scope.default_setup'), compact=True)
        self.btn_default.clicked.connect(self.defaultSetupClicked.emit)
        self.btn_utility = _action_btn(tr('tool.tektronix_scope.utility'), compact=True)
        self.btn_utility.clicked.connect(lambda: self.menuClicked.emit('utility'))
        self.btn_bus1 = _action_btn(tr('tool.tektronix_scope.bus1'), compact=True)
        self.btn_bus1.clicked.connect(lambda: self.menuClicked.emit('bus1'))
        self.btn_bus2 = _action_btn(tr('tool.tektronix_scope.bus2'), compact=True)
        self.btn_bus2.clicked.connect(lambda: self.menuClicked.emit('bus2'))
        self.btn_ref = _action_btn(tr('tool.tektronix_scope.ref'), compact=True)
        self.btn_ref.clicked.connect(lambda: self.menuClicked.emit('ref'))
        self.btn_math = _action_btn(tr('tool.tektronix_scope.math'), compact=True)
        self.btn_math.clicked.connect(lambda: self.menuClicked.emit('math'))
        self.btn_cursor = _action_btn(tr('tool.tektronix_scope.cursors'), checkable=True, compact=True)
        self.btn_cursor.setToolTip(tr('tool.tektronix_scope.cursors_tip'))
        self.btn_cursor.clicked.connect(self.cursorClicked.emit)
        self.btn_intensity = _action_btn(tr('tool.tektronix_scope.intensity'), compact=True)
        self.btn_intensity.clicked.connect(self.intensityClicked.emit)
        self.btn_digital = _action_btn(tr('tool.tektronix_scope.digital'), compact=True)
        self.btn_digital.clicked.connect(self.digitalClicked.emit)
        self.btn_save = _action_btn(tr('tool.tektronix_scope.save'), accent=True, compact=True)
        self.btn_save.clicked.connect(self.saveClicked.emit)
        self.btn_menu_off = _action_btn(tr('tool.tektronix_scope.menu_off'), compact=True)
        self.btn_menu_off.clicked.connect(self.menuOffClicked.emit)

        soft_btns = (
            self.btn_save_recall, self.btn_default, self.btn_utility, self.btn_bus1,
            self.btn_bus2, self.btn_ref, self.btn_math, self.btn_cursor,
            self.btn_intensity, self.btn_digital, self.btn_save, self.btn_menu_off,
        )
        for i, b in enumerate(soft_btns):
            self._dock_fill_btn(b)
            soft_grid.addWidget(b, i // 4, i % 4)
        lay_soft.addLayout(soft_grid, stretch=1)

        # Equal column weights: soft keys slightly wider (more buttons)
        root.addWidget(mod_acq, stretch=2)
        root.addWidget(mod_horiz, stretch=2)
        root.addWidget(mod_trig, stretch=2)
        root.addWidget(mod_nav, stretch=3)
        root.addWidget(mod_soft, stretch=4)

        self.grp_softkeys = self.grp_dock
        self.grp_wave_inspector = self.grp_dock
        self.grp_horizontal = self.grp_dock
        self.grp_trigger = self.grp_dock
        self.grp_acquire_ctrl = self.grp_dock
        return self.grp_dock

    def _vsep(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet('color:#64748B;')
        line.setFixedWidth(1)
        return line

    def _build_log_row(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.btn_log_toggle = QToolButton()
        self.btn_log_toggle.setText(tr('tool.tektronix_scope.log_show'))
        self.btn_log_toggle.setCheckable(True)
        self.btn_log_toggle.setMinimumHeight(26)
        self.btn_log_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_log_toggle.setStyleSheet('color:#F8FAFC;font-weight:600;')
        self.log_edit = QTextEdit()
        self.log_edit.setObjectName('tek_scope_log')
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(90)
        self.log_edit.setPlaceholderText(tr('tool.tektronix_scope.log_placeholder'))
        self.log_edit.hide()
        self.btn_log_toggle.toggled.connect(self._toggle_log)
        lay.addWidget(self.btn_log_toggle)
        lay.addWidget(self.log_edit)
        return wrap

    def _toggle_log(self, on: bool) -> None:
        self.log_edit.setVisible(on)
        self.btn_log_toggle.setText(
            tr('tool.tektronix_scope.log_hide') if on else tr('tool.tektronix_scope.log_show')
        )
