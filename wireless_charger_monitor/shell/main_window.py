"""WiParse application shell — main window controller."""
import bisect
import datetime
import os
import sqlite3
import time

import pyqtgraph as pg
import serial.tools.list_ports
from PyQt5.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QIntValidator, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QAction,
    QActionGroup,
    QComboBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QMenu,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QToolTip,
)

from ..charge_state import ChargeStateTracker
from .. import config as config_module
from ..config import update_config
from ..db import (
    close_session,
    create_session,
    db_path,
    get_session_info,
    init_db,
)
from ..logging_setup import logger
from ..paths import project_path
from ..serial_ports import SerialPortWatcher
from ..protocol.qi_parser import Qi22Parser
from ..workers import DBWorker, FetchWorker, LiveLogWriter, SerialWorker
from ..apps.serial_tool import LogTabPage
from ..i18n import get_language, init_language, is_known_log_default_name, set_language, tr, tr_in
from ..ui.loader import Ui_MonitorWindow
from ..ui.tab_utils import reflow_tab_widget, refresh_tab_widget
from ..ui.theme import (
    FS_BODY,
    FS_CAPTION,
    FS_SUBTITLE,
    FONT_FAMILY_MONO,
    LCD_TEMP,
    LCD_BG,
    TEXT_MUTED,
    ACCENT,
    SELECTION_TEXT,
    CROSSHAIR_COLOR,
    HUD_BG_RGBA,
    HUD_BORDER,
    HUD_TEXT,
    CHART_POWER,
    CHART_VOLTAGE,
    CHART_CURRENT,
    STATUS_INFO,
    STATUS_WARN,
    STATUS_ERROR,
    STATUS_SUCCESS,
    TEMP_ALERT_BG,
    TEMP_ALERT_FG,
    TEMP_ALERT_BORDER,
    TEMP_NORMAL_BORDER,
    apply_data_label_style,
    apply_lcd_style,
    apply_editable_combo_line_edit,
    apply_log_control_panel_metrics,
    apply_log_control_panel_theme,
    apply_status_message_style,
    apply_status_session_style,
    full_stylesheet,
    get_theme,
    init_theme,
    menu_bar_stylesheet,
    set_theme,
    status_bar_stylesheet,
    ui_font_css,
    FW_NORMAL,
)

class MonitorWindow(QMainWindow):
    _live_log_write_error = pyqtSignal(object)

    def __init__(self, cli_demo_mode=False):
        super().__init__()
        init_language(config_module.CONFIG.get('ui', {}).get('language', 'en'))
        init_theme(config_module.CONFIG.get('ui', {}).get('theme', 'dark'))
        self._cli_demo_mode = cli_demo_mode
        self._demo_mode_active = False
        self.current_session_id = None
        self.ui = Ui_MonitorWindow()
        self.ui.setupUi(self)
        init_db()
        self._setup_view_menu()
        self._setup_unified_header()
        self._setup_menu_bar_auto_hide()

        self.statusBar().setStyleSheet(status_bar_stylesheet())
        self._status_default = QLabel(tr('status.ready'))
        apply_status_message_style(self._status_default, TEXT_MUTED)
        self.statusBar().addWidget(self._status_default, 1)
        self._status_session = QLabel("")
        apply_status_session_style(self._status_session)
        self.statusBar().addPermanentWidget(self._status_session)
        self._alert_clear_timer = QTimer(self)
        self._alert_clear_timer.setSingleShot(True)
        self._alert_clear_timer.timeout.connect(lambda: self._set_status(tr('status.ready'), 'normal'))
        self.qi_parser = Qi22Parser()
        self._charge_state_tracker = ChargeStateTracker(config_module.CONFIG.get('charge_state', {}))
        self._active_alerts = set()
        self._full_charge_start_time = None
        self._full_charge_alerted = False

        scale = max(1.0, (QApplication.primaryScreen().logicalDotsPerInchX() / 96.0) if QApplication.primaryScreen() else 1.0)
        self._ui_scale = scale
        self._apply_toolbar_metrics()
        if hasattr(self.ui, 'edit_live_log_dir'):
            self.ui.edit_live_log_dir.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.worker = None
        self.x_data, self.y_vi, self.y_ii, self.y_vo, self.y_io, self.y_vb, self.y_ib, self.y_eff, self.y_p, self.y_t, self.y_b = [],[],[],[],[],[],[],[],[],[],[]
        self.latest_data, self.start_time, self.time_offset = None, 0.0, 0.0
        self.view_data = {'x':[], 'p':[], 'vi':[], 'ii':[], 'vo':[], 'io':[], 'vb':[], 'ib':[], 't':[], 'b':[]}
        self.auto_scroll_chart = True
        self.log_buffer, self.ui_lock = [], False
        self._last_lcd_snapshot: dict[str, float | int] = {}
        self._hover_state = None
        self._monitoring_active = False
        self._starting_monitor = False
        self._stopping_monitor = False

        self.db_worker = DBWorker()
        self.db_worker.start()
        self.fetch_worker = FetchWorker()
        self.fetch_worker.chart_fetched.connect(self.on_chart_fetched)
        self.fetch_worker.start()

        self.setup_crosshair()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.render_log_ui)
        self.timer.start(config_module.CONFIG['ui'].get('render_interval_ms', 100))

        self._metrics_timer = QTimer(self)
        self._metrics_timer.timeout.connect(self.render_metrics_ui)
        self._metrics_timer.start(config_module.CONFIG['ui'].get('render_interval_ms', 100))

        self._chart_timer = QTimer(self)
        self._chart_timer.timeout.connect(self.render_chart_ui)
        self._chart_timer.start(config_module.CONFIG['ui'].get('chart_render_interval_ms', 200))

        self._log_tabs_by_path = {}
        self._live_log_page = None
        self._live_log_writer = LiveLogWriter()
        self._live_log_write_error.connect(self._handle_live_log_write_error)
        self._live_log_file_path = None
        self._setup_log_file_tabs()
        self._setup_live_log_settings()

        self.ui.btn_start.clicked.connect(self._toggle_monitor)
        self.ui.btn_open_log.clicked.connect(self.open_log_files)
        self.ui.btn_browse_log_dir.clicked.connect(self._browse_live_log_dir)
        self.ui.btn_new_live_log.clicked.connect(self._new_live_log_tab)
        self.ui.btn_clear_live_log.clicked.connect(self._clear_live_log_display)

        self.ui.p_p.vb.sigRangeChanged.connect(self.on_chart_manual_interaction)
        self.ui.graph_widget.scene().sigMouseClicked.connect(self.on_chart_double_clicked)

        self.ui.cb_baudrate.clear()
        self._setup_baudrate_combo()

        poll_ms = config_module.CONFIG.get('serial', {}).get('port_poll_interval_ms', 2000)
        self._port_watcher = SerialPortWatcher(poll_interval_ms=poll_ms, parent=self)
        self._port_watcher.ports_changed.connect(lambda: self.scan_ports(notify=True))
        self._port_watcher.start()

        self.scan_ports()
        self._port_watcher.sync_known()
        self.auto_scroll_chart = False
        try:
            conn = sqlite3.connect(db_path())
            max_t = conn.execute("SELECT MAX(rel_time) FROM charging_metrics").fetchone()[0]
            conn.close()
            if max_t:
                self.ui.p_p.setXRange(max_t-60, max_t+5, padding=0)
                self.fetch_worker.latest_xlim = [max_t-60, max_t+5]
                self.fetch_worker.chart_request = True
        except Exception:
            logger.warning("Failed to restore chart view from database", exc_info=True)

        self._retranslate_ui()
        self._restore_open_log_files()

    def _saved_open_log_files(self):
        raw = config_module.CONFIG.get('log_monitor', {}).get('open_log_files', [])
        if not isinstance(raw, list):
            return []
        paths = []
        seen = set()
        for item in raw:
            if not item or not isinstance(item, str):
                continue
            norm = os.path.normcase(os.path.abspath(item))
            if norm in seen:
                continue
            seen.add(norm)
            paths.append(norm)
        return paths

    def _persist_open_log_files(self, paths=None):
        if paths is None:
            paths = self._collect_open_log_file_paths()
        update_config({'log_monitor': {'open_log_files': paths}})

    def _collect_open_log_file_paths(self):
        paths = []
        tabs = self.ui.log_file_tabs
        for index in range(tabs.count()):
            page = tabs.widget(index)
            if isinstance(page, LogTabPage) and not page.live and page.filepath:
                paths.append(os.path.normcase(os.path.abspath(page.filepath)))
        return paths

    def _register_open_log_file(self, path):
        norm = os.path.normcase(os.path.abspath(path))
        paths = [p for p in self._saved_open_log_files() if p != norm]
        paths.append(norm)
        self._persist_open_log_files(paths)

    def _unregister_open_log_file(self, path):
        if not path:
            return
        norm = os.path.normcase(os.path.abspath(path))
        paths = [p for p in self._saved_open_log_files() if p != norm]
        self._persist_open_log_files(paths)

    def _open_log_file(self, path, *, show_errors=True, focus=True):
        norm = os.path.normcase(os.path.abspath(path))
        existing = self._log_tabs_by_path.get(norm)
        if existing is not None and self.ui.log_file_tabs.indexOf(existing) >= 0:
            if focus:
                self.ui.log_file_tabs.setCurrentWidget(existing)
            return True
        try:
            if LogTabPage.should_stream_load(path):
                page = self._create_log_tab_page(filepath=norm)

                def _progress(count):
                    self._set_status(tr('status.loading_log_lines', n=count), 'info')

                page.load_file_streaming(path, status_callback=_progress)
            else:
                with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
                    content = f.read()
                page = self._create_log_tab_page(filepath=norm)
                page.set_content(content)
        except OSError as e:
            if show_errors:
                QMessageBox.warning(
                    self,
                    tr('dialog.open_failed'),
                    tr('msg.cannot_read_file', path=path, error=e),
                )
            self._unregister_open_log_file(path)
            return False
        title = os.path.splitext(os.path.basename(path))[0] or os.path.basename(path)
        self.ui.log_file_tabs.addTab(page, title)
        if focus:
            self.ui.log_file_tabs.setCurrentWidget(page)
        self._refresh_log_file_tabs()
        self._log_tabs_by_path[norm] = page
        self._register_open_log_file(norm)
        return True

    def _restore_open_log_files(self):
        paths = self._saved_open_log_files()
        if not paths:
            return
        opened = 0
        kept = []
        for path in paths:
            if self._open_log_file(path, show_errors=True, focus=False):
                kept.append(os.path.normcase(os.path.abspath(path)))
                opened += 1
        if kept != paths:
            self._persist_open_log_files(kept)
        if opened:
            first_file_idx = 1 if self.ui.log_file_tabs.count() > 1 else 0
            self.ui.log_file_tabs.setCurrentIndex(first_file_idx)
            self._set_status(tr('status.opened_logs', count=opened), 'info')

    def _setup_baudrate_combo(self):
        combo = self.ui.cb_baudrate
        combo.clear()
        combo.addItems(config_module.CONFIG['serial'].get('default_baudrates', ['115200']))
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setValidator(QIntValidator(1, 10_000_000, self))
        if combo.count() > 0:
            combo.setCurrentIndex(0)
        apply_editable_combo_line_edit(combo)

    def _iter_log_pages(self):
        tabs = self.ui.log_file_tabs
        for index in range(tabs.count()):
            page = tabs.widget(index)
            if isinstance(page, LogTabPage):
                yield page

    def _set_language(self, lang):
        if get_language() == lang:
            return
        set_language(lang)
        partial = {'ui': {'language': lang}}
        cfg_name = (self._live_log_cfg().get('default_filename') or '').strip()
        edit_name = self._sanitize_log_basename(self.ui.edit_live_log_name.text())
        if not cfg_name or is_known_log_default_name(cfg_name) or is_known_log_default_name(edit_name):
            partial['log_monitor'] = {'default_filename': tr('log.default_filename')}
        update_config(partial)
        self._retranslate_ui()

    def _on_language_selected(self, action):
        lang = 'en' if action is self._act_lang_en else 'zh'
        self._set_language(lang)

    def _retranslate_ui(self):
        self.setWindowTitle(tr('app.title'))
        self._panel_menu.setTitle(tr('menu.panels'))
        self._act_tool_serial.setText(tr('tool.serial_tool.name'))
        self._act_tool_waveform.setText(tr('tool.waveform_scope.name'))
        self._act_tool_tektronix.setText(tr('tool.tektronix_scope.name'))
        self._sync_panel_menu_checks()
        self._sync_settings_btn_text()
        self._lang_menu.setTitle(tr('menu.language'))
        self._theme_menu.setTitle(tr('menu.theme'))
        self._act_theme_dark.setText(tr('menu.theme_dark'))
        self._act_theme_light.setText(tr('menu.theme_light'))
        self._sync_theme_menu_checks()
        if get_language() == 'en':
            self._act_lang_en.setChecked(True)
        else:
            self._act_lang_zh.setChecked(True)

        tabs = self.ui.main_tabs
        tabs.setTabText(tabs.indexOf(self.ui.chart_panel), tr('tool.waveform_scope.name'))
        tabs.setTabText(tabs.indexOf(self.ui.log_panel), tr('tool.serial_tool.name'))
        tabs.setTabText(tabs.indexOf(self.ui.tektronix_panel), tr('tool.tektronix_scope.name'))

        lcd_labels = (
            ('lbl_lcd_v_in', 'lcd.v_in'),
            ('lbl_lcd_i_in', 'lcd.i_in'),
            ('lbl_lcd_v_out', 'lcd.v_out'),
            ('lbl_lcd_i_out', 'lcd.i_out'),
            ('lbl_lcd_power', 'lcd.power'),
            ('lbl_lcd_v_bat', 'lcd.v_bat'),
            ('lbl_lcd_i_bat', 'lcd.i_bat'),
            ('lbl_lcd_temp', 'lcd.temp'),
            ('lbl_lcd_battery', 'lcd.battery'),
        )
        for attr, key in lcd_labels:
            widget = getattr(self.ui, attr, None)
            if widget is not None:
                widget.setText(tr(key))
                apply_data_label_style(widget, compact=(get_language() == 'en'))

        placeholder = getattr(self.ui, 'chart_placeholder', None)
        if placeholder is not None:
            placeholder.setText(tr('chart.placeholder'))

        self.ui.btn_new_live_log.setText(tr('btn.new'))
        self.ui.btn_new_live_log.setToolTip(tr('log.new_tooltip'))
        self.ui.btn_clear_live_log.setText(tr('btn.clear'))
        self.ui.btn_clear_live_log.setToolTip(tr('log.clear_tooltip'))
        self.ui.lbl_live_log_name.setText(tr('log.filename'))
        self.ui.edit_live_log_name.setPlaceholderText(tr('log.name_placeholder'))
        self.ui.edit_live_log_name.setToolTip(tr('log.name_tooltip'))
        self.ui.lbl_live_log_dir.setText(tr('log.save_dir'))
        self.ui.edit_live_log_dir.setToolTip(tr('log.dir_tooltip'))
        self.ui.btn_browse_log_dir.setText(tr('btn.browse_dir'))
        self.ui.btn_browse_log_dir.setToolTip(tr('btn.browse_tooltip'))
        self.ui.btn_open_log.setText(tr('btn.open_log'))
        self.ui.btn_open_log.setToolTip(tr('log.open_tooltip'))

        self._refresh_main_tabs()
        self._refresh_log_file_tabs()

        self._update_monitor_button()
        self._update_session_label()
        self._sync_localized_log_defaults()
        self._apply_toolbar_metrics()
        for page in self._iter_log_pages():
            page.retranslate_ui()
        if hasattr(self.ui, 'tektronix_scope'):
            self.ui.tektronix_scope.retranslate_ui()
        self.scan_ports()
        self._retranslate_idle_status()

    # ========================== 核心扩展功能区 ==========================
    def _current_log_page(self):
        widget = self.ui.log_file_tabs.currentWidget()
        if isinstance(widget, LogTabPage):
            return widget
        return self._live_log_page

    def _current_log_edit(self):
        page = self._current_log_page()
        return page.current_editor() if page else None

    def _log_edit_for_viewport(self, viewport):
        tabs = self.ui.log_file_tabs
        for index in range(tabs.count()):
            page = tabs.widget(index)
            if not isinstance(page, LogTabPage):
                continue
            for edit in page.all_editors():
                if edit.viewport() is viewport:
                    return edit
        return None

    def _log_page_for_edit(self, edit):
        tabs = self.ui.log_file_tabs
        for index in range(tabs.count()):
            page = tabs.widget(index)
            if isinstance(page, LogTabPage) and edit in page.all_editors():
                return page
        return None

    def _create_log_tab_page(self, live=False, filepath=None):
        page = LogTabPage(live=live, filepath=filepath)
        page.set_event_filter(self)
        return page

    def _live_log_cfg(self):
        return config_module.CONFIG.get('log_monitor', {})

    def _live_log_extension(self):
        return self._live_log_cfg().get('file_extension', 'txt').lstrip('.')

    def _default_live_log_name(self):
        cfg_name = (self._live_log_cfg().get('default_filename') or '').strip()
        if not cfg_name or is_known_log_default_name(cfg_name):
            return tr('log.default_filename')
        return cfg_name

    def _refresh_main_tabs(self):
        reflow_tab_widget(self.ui.main_tabs, preset='main')
        apply_log_control_panel_theme(self.ui)

    def _refresh_log_file_tabs(self):
        refresh_tab_widget(self.ui.log_file_tabs, preset='file')

    def _apply_toolbar_metrics(self):
        scale = getattr(self, '_ui_scale', 1.0)
        sidebar_w = int(140 * scale)
        sidebar_controls = (
            'cb_port', 'cb_baudrate', 'btn_start', 'btn_new_live_log', 'btn_clear_live_log',
            'edit_live_log_name', 'edit_live_log_dir', 'btn_browse_log_dir', 'btn_open_log',
        )
        for name in sidebar_controls:
            if hasattr(self.ui, name):
                widget = getattr(self.ui, name)
                widget.setMinimumWidth(0)
                widget.setMaximumWidth(sidebar_w)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        apply_log_control_panel_metrics(self.ui, scale)

    def _sync_localized_log_defaults(self):
        current = self._sanitize_log_basename(self.ui.edit_live_log_name.text())
        if not is_known_log_default_name(current):
            return
        localized = tr('log.default_filename')
        if current == localized:
            self._update_live_log_tab_title()
            return
        self.ui.edit_live_log_name.blockSignals(True)
        self.ui.edit_live_log_name.setText(localized)
        self.ui.edit_live_log_name.blockSignals(False)
        self._update_live_log_tab_title()

    def _retranslate_idle_status(self):
        current = self._status_default.text()
        if current in (tr_in('zh', 'status.ready'), tr_in('en', 'status.ready')):
            self._set_status(tr('status.ready'), 'normal')

    def _resolve_log_save_dir(self, save_dir):
        path = (save_dir or '').strip() or 'log'
        if os.path.isabs(path):
            return os.path.abspath(path)
        return str(project_path(path))

    def _default_live_log_dir(self):
        return self._resolve_log_save_dir(self._live_log_cfg().get('save_dir', 'log'))

    def _persist_live_log_save_dir(self, directory):
        directory = os.path.abspath(os.path.expanduser(directory))
        app_root = str(project_path('.'))
        try:
            rel = os.path.relpath(directory, app_root)
            stored = rel if not rel.startswith('..') else directory
        except ValueError:
            stored = directory
        current = self._resolve_log_save_dir(self._live_log_cfg().get('save_dir', 'log'))
        if os.path.normcase(directory) == os.path.normcase(current):
            return
        update_config({'log_monitor': {'save_dir': stored}})

    def _sanitize_log_basename(self, name):
        name = (name or '').strip()
        ext = self._live_log_extension()
        for suffix in (f'.{ext}', '.txt', '.log'):
            if name.lower().endswith(suffix.lower()):
                name = name[: -len(suffix)]
                break
        for ch in '\\/:*?"<>|':
            name = name.replace(ch, '_')
        return name.strip() or self._default_live_log_name()

    def _live_log_tab_title(self):
        return self._sanitize_log_basename(self.ui.edit_live_log_name.text())

    def _live_log_dir(self):
        raw = self.ui.edit_live_log_dir.text().strip()
        if raw:
            return os.path.abspath(os.path.expanduser(raw))
        return self._default_live_log_dir()

    def _live_log_filepath(self):
        return os.path.join(self._live_log_dir(), f"{self._live_log_tab_title()}.{self._live_log_extension()}")

    def _generate_live_log_name(self):
        base = self._default_live_log_name()
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        name = f"{base}_{stamp}"
        directory = self._live_log_dir()
        ext = self._live_log_extension()
        candidate = name
        suffix = 1
        while os.path.exists(os.path.join(directory, f"{candidate}.{ext}")):
            candidate = f"{name}_{suffix}"
            suffix += 1
        return candidate

    def _archive_current_live_log_tab(self):
        if self._live_log_page is None:
            return
        old = self._live_log_page
        idx = self.ui.log_file_tabs.indexOf(old)
        if idx >= 0:
            path = old.filepath
            if path:
                title = os.path.splitext(os.path.basename(path))[0] or self.ui.log_file_tabs.tabText(idx)
            else:
                title = self.ui.log_file_tabs.tabText(idx)
            self.ui.log_file_tabs.setTabText(idx, title)
        old.live = False
        self._live_log_page = None

    def _new_live_log_tab(self):
        self._archive_current_live_log_tab()
        new_name = self._generate_live_log_name()
        self.ui.edit_live_log_name.blockSignals(True)
        self.ui.edit_live_log_name.setText(new_name)
        self.ui.edit_live_log_name.blockSignals(False)

        self._live_log_page = self._create_log_tab_page(live=True)
        self.ui.log_file_tabs.insertTab(0, self._live_log_page, self._live_log_tab_title())
        self.ui.log_file_tabs.setCurrentWidget(self._live_log_page)
        self._refresh_log_file_tabs()
        self.log_buffer.clear()

        path = self._live_log_filepath()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8-sig', newline='\n'):
                pass
            self._live_log_page.filepath = path
        except OSError as e:
            logger.warning("Cannot create live log file %s: %s", path, e)
            QMessageBox.warning(self, tr('dialog.create_failed'), tr('msg.cannot_create_log', path=path, error=e))

        if self.worker and self.worker.isRunning():
            self._open_live_log_file()
        else:
            self._close_live_log_file()

        self._set_status(tr('status.new_log', name=self._live_log_tab_title()), 'info')

    def _clear_live_log_display(self):
        """Clear live packet view only; file on disk and capture continue unchanged."""
        self.log_buffer.clear()
        page = self._live_log_page
        if page is None or self.ui.log_file_tabs.indexOf(page) < 0:
            page = self._ensure_live_log_tab()
        page.clear()

    def _setup_live_log_settings(self):
        self.ui.edit_live_log_name.setText(self._default_live_log_name())
        self.ui.edit_live_log_dir.setText(self._default_live_log_dir())
        try:
            os.makedirs(self._default_live_log_dir(), exist_ok=True)
        except OSError:
            logger.warning("Could not create default log directory", exc_info=True)
        self.ui.edit_live_log_name.textChanged.connect(self._on_live_log_name_changed)
        self.ui.edit_live_log_name.returnPressed.connect(self._on_live_log_name_return_pressed)
        self.ui.edit_live_log_dir.editingFinished.connect(self._on_live_log_dir_changed)
        self._update_live_log_tab_title()

    def _on_live_log_name_changed(self, _text=''):
        self._update_live_log_tab_title()

    def _on_live_log_name_return_pressed(self):
        cleaned = self._live_log_tab_title()
        self.ui.edit_live_log_name.blockSignals(True)
        self.ui.edit_live_log_name.setText(cleaned)
        self.ui.edit_live_log_name.blockSignals(False)
        self._apply_live_log_rename()

    def _apply_live_log_rename(self):
        self._ensure_live_log_tab()
        new_path = os.path.abspath(self._live_log_filepath())
        old_path = self._live_log_file_path or self._live_log_page.filepath
        if old_path:
            old_path = os.path.abspath(old_path)

        self._update_live_log_tab_title()

        if old_path and os.path.normcase(old_path) == os.path.normcase(new_path):
            return

        try:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
        except OSError as e:
            logger.warning("Failed to prepare live log directory for %s: %s", new_path, e)
            QMessageBox.warning(self, tr('dialog.create_failed'), tr('msg.cannot_create_log', path=new_path, error=e))
            return

        was_writing = self._live_log_writer.is_open
        if was_writing:
            self._close_live_log_file()

        self._live_log_page.filepath = new_path

        monitoring = self.worker and self.worker.isRunning()
        if was_writing or monitoring:
            self._open_live_log_file()

        self._set_status(tr('status.log_updated', name=self._live_log_tab_title()), 'info')

    def _on_live_log_dir_changed(self):
        raw = self.ui.edit_live_log_dir.text().strip()
        if not raw:
            return
        directory = os.path.abspath(os.path.expanduser(raw))
        if directory != raw:
            self.ui.edit_live_log_dir.blockSignals(True)
            self.ui.edit_live_log_dir.setText(directory)
            self.ui.edit_live_log_dir.blockSignals(False)
        self._persist_live_log_save_dir(directory)
        self._reopen_live_log_file_if_active()

    def _browse_live_log_dir(self):
        directory = QFileDialog.getExistingDirectory(self, tr('filedialog.save_dir'), self._live_log_dir())
        if directory:
            self.ui.edit_live_log_dir.setText(directory)
            self._on_live_log_dir_changed()

    def _update_live_log_tab_title(self):
        if self._live_log_page is None:
            return
        idx = self.ui.log_file_tabs.indexOf(self._live_log_page)
        if idx >= 0:
            self.ui.log_file_tabs.setTabText(idx, self._live_log_tab_title())
            self._refresh_log_file_tabs()

    def _open_live_log_file(self):
        self._close_live_log_file()
        path = self._live_log_filepath()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._live_log_writer.open(path, on_error=self._schedule_live_log_write_error)
            self._live_log_file_path = path
            if self._live_log_page is not None:
                self._live_log_page.filepath = path
        except OSError as e:
            logger.warning("Cannot open live log file %s: %s", path, e)
            self._set_status(tr('status.cannot_create_log', name=os.path.basename(path)), 'warn')
            QMessageBox.warning(self, tr('dialog.save_failed'), tr('msg.cannot_create_log', path=path, error=e))

    def _schedule_live_log_write_error(self, exc: Exception) -> None:
        self._live_log_write_error.emit(exc)

    def _handle_live_log_write_error(self, exc: Exception) -> None:
        logger.warning("Failed to write live log file: %s", exc, exc_info=True)
        self._close_live_log_file()
        self._set_status(tr('status.log_write_failed'), 'error')

    def _close_live_log_file(self):
        self._live_log_writer.close()
        self._live_log_file_path = None

    def _reopen_live_log_file_if_active(self):
        if self.worker and self.worker.isRunning():
            self._open_live_log_file()

    def _write_live_log_line(self, msg):
        self._live_log_writer.write_line(msg)

    def _ensure_live_log_tab(self):
        if self._live_log_page is not None and self.ui.log_file_tabs.indexOf(self._live_log_page) >= 0:
            return self._live_log_page
        self._live_log_page = self._create_log_tab_page(live=True)
        self.ui.log_file_tabs.insertTab(0, self._live_log_page, self._live_log_tab_title())
        self._refresh_log_file_tabs()
        return self._live_log_page

    def _live_log(self):
        return self._ensure_live_log_tab()

    def _setup_log_file_tabs(self):
        tabs = self.ui.log_file_tabs
        tabs.tabCloseRequested.connect(self._on_log_tab_close_requested)
        tabs.currentChanged.connect(self._on_log_file_tab_changed)
        bar = tabs.tabBar()
        bar.setContextMenuPolicy(Qt.CustomContextMenu)
        bar.customContextMenuRequested.connect(self._on_log_tab_context_menu)
        self._ensure_live_log_tab()

    def _on_log_tab_context_menu(self, pos):
        bar = self.ui.log_file_tabs.tabBar()
        index = bar.tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        act_close = menu.addAction(tr('log.tab.close_current'))
        act_close.triggered.connect(lambda _checked=False, idx=index: self._close_log_tab_at(idx))
        act_close_all = menu.addAction(tr('log.tab.close_all'))
        act_close_all.setEnabled(self.ui.log_file_tabs.count() > 1)
        act_close_all.triggered.connect(self._close_all_log_tabs_except_live)
        menu.exec_(bar.mapToGlobal(pos))

    def _close_log_tab_at(self, index):
        self._on_log_tab_close_requested(index)

    def _close_all_log_tabs_except_live(self):
        tabs = self.ui.log_file_tabs
        for index in range(tabs.count() - 1, 0, -1):
            self._close_log_tab_at(index)

    def _on_log_file_tab_changed(self, _index):
        self._hover_state = None
        QToolTip.hideText()

    def _on_log_tab_close_requested(self, index):
        tabs = self.ui.log_file_tabs
        page = tabs.widget(index)
        if not isinstance(page, LogTabPage):
            return
        if page is self._live_log_page and self.worker and self.worker.isRunning():
            QMessageBox.warning(self, tr('dialog.notice'), tr('msg.cannot_close_live_tab'))
            return
        path = page.filepath
        if path:
            self._unregister_open_log_file(path)
        if path and self._log_tabs_by_path.get(path) is page:
            del self._log_tabs_by_path[path]
        if page is self._live_log_page:
            self._live_log_page = None
        tabs.removeTab(index)
        if tabs.count() == 0:
            self._ensure_live_log_tab()

    def open_log_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr('filedialog.open_logs'),
            self._live_log_dir(),
            tr('filedialog.filter'),
        )
        if not paths:
            return
        opened = 0
        for path in paths:
            if self._open_log_file(path):
                opened += 1
        if opened:
            self._set_status(tr('status.opened_logs', count=opened), 'info')

    def _set_status(self, text, level='normal'):
        colors_map = {
            'normal': TEXT_MUTED,
            'info': STATUS_INFO,
            'warn': STATUS_WARN,
            'error': STATUS_ERROR,
            'success': STATUS_SUCCESS,
        }
        self._status_default.setText(text)
        apply_status_message_style(self._status_default, colors_map.get(level, colors_map['normal']))

    def _update_session_label(self):
        if self.current_session_id:
            info = get_session_info(self.current_session_id)
            label = tr('status.session', id=self.current_session_id)
            if info and info.get('session_uuid'):
                label += f" ({info['session_uuid']})"
            self._status_session.setText(label)
        else:
            self._status_session.setText("")
        apply_status_session_style(self._status_session)

    def show_full_charge_alert(self, debounce_sec):
        ts_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self.append_log(
            time.time(),
            tr('msg.full_charge_log', time=ts_str, seconds=debounce_sec),
        )
        self.msg_full_charge = QMessageBox(self)
        self.msg_full_charge.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.msg_full_charge.setIcon(QMessageBox.Information)
        self.msg_full_charge.setWindowTitle(tr('dialog.full_charge_title'))
        self.msg_full_charge.setText(tr('msg.full_charge_html'))
        self.msg_full_charge.setInformativeText(tr('msg.full_charge_info', seconds=debounce_sec))
        self.msg_full_charge.setStandardButtons(QMessageBox.Ok)
        self.msg_full_charge.show()
        QTimer.singleShot(10000, self.close_full_charge_alert)

    def close_full_charge_alert(self):
        if hasattr(self, 'msg_full_charge') and self.msg_full_charge.isVisible(): self.msg_full_charge.accept()

    def _is_monitoring(self):
        return self._monitoring_active

    def _update_monitor_button(self):
        btn = self.ui.btn_start
        if self._monitoring_active:
            btn.setText(tr('btn.stop'))
            btn.setObjectName('btn_stop')
            btn.setEnabled(not self._stopping_monitor)
        else:
            btn.setText(tr('btn.start'))
            btn.setObjectName('btn_start')
            btn.setEnabled(not self._starting_monitor)
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        btn.update()
        busy = self._monitoring_active or self._starting_monitor or self._stopping_monitor
        self.ui.cb_port.setEnabled(not busy)

    def _schedule_monitor_button_update(self):
        QTimer.singleShot(0, self._update_monitor_button)

    def _toggle_monitor(self):
        if self._starting_monitor or self._stopping_monitor:
            return
        if self._monitoring_active:
            self.stop_mon()
        else:
            self.start_mon()

    def _on_worker_finished(self):
        worker = self.sender()
        if worker is not self.worker or self._stopping_monitor:
            return
        self.worker = None
        if self._starting_monitor:
            self._starting_monitor = False
            self._schedule_monitor_button_update()
            return
        if not self._monitoring_active:
            return
        logger.warning('Serial worker exited while monitoring was active')
        self._monitoring_active = False
        self._close_live_log_file()
        if self.current_session_id:
            close_session(self.current_session_id)
            self.current_session_id = None
            self._update_session_label()
        self.auto_scroll_chart = False
        self.hide_tooltip()
        self._schedule_monitor_button_update()

    def sync_log_to_time(self, target_time):
        if self.auto_scroll_chart:
            self.auto_scroll_chart = False
            self.request_chart_fetch()
        try:
            conn = sqlite3.connect(db_path())
            cur = conn.cursor()
            cur.execute("SELECT id, message FROM tx0_logs WHERE rel_time IS NOT NULL ORDER BY ABS(rel_time - ?) LIMIT 1", (target_time,))
            res = cur.fetchone()
            if not res:
                conn.close()
                return
            target_id, target_msg = res
            start_id = max(0, target_id - 500)
            cur.execute("SELECT message FROM tx0_logs WHERE id >= ? AND id <= ? ORDER BY id ASC", (start_id, target_id + 500))
            rows = cur.fetchall()
            conn.close()
            if rows:
                live = self._live_log()
                self.ui.log_file_tabs.setCurrentWidget(live)
                log_text = "\n".join([r[0] for r in rows])
                self.ui_lock = True
                live.set_content(log_text)
                self.ui_lock = False
                QTimer.singleShot(50, lambda: self.highlight_log(target_msg))
        except Exception:
            logger.warning("sync_log_to_time failed for t=%s", target_time, exc_info=True)

    def highlight_log(self, target_msg):
        page = self._live_log()
        for edit in page.all_editors():
            doc = edit.document()
            cursor = edit.textCursor()
            cursor.setPosition(0)
            found_cursor = doc.find(target_msg, cursor)
            if found_cursor.isNull():
                continue
            page.focus_editor(edit)
            edit.setTextCursor(found_cursor)
            edit.centerCursor()
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(ACCENT))
            selection.format.setForeground(QColor(SELECTION_TEXT))
            selection.cursor = found_cursor
            selection.cursor.select(QTextCursor.BlockUnderCursor)
            edit.setExtraSelections([selection])
            QTimer.singleShot(3000, lambda e=edit, p=page: p.refresh_filter_highlights(e))
            break

    # ========================== 基础生命周期区 ==========================
    def append_log(self, ts, msg):
        self.log_buffer.append(msg)
        self._write_live_log_line(msg)
        self._queue_log_db_entry(ts, msg)

    def append_logs_batch(self, entries):
        if not entries:
            return
        msgs = [msg for _, msg in entries]
        self.log_buffer.extend(msgs)
        self._live_log_writer.write_lines(msgs)
        for ts, msg in entries:
            self._queue_log_db_entry(ts, msg)

    def _queue_log_db_entry(self, ts, msg):
        if hasattr(self, 'db_worker'):
            t = (ts - self.start_time + self.time_offset) if self.start_time > 0 else 0.0
            self.db_worker.queue.put({
                'type': 'log', 'rel_time': t, 'msg': msg,
                'session_id': self.current_session_id,
            })

    def setup_crosshair(self):
        self.v_lines = []
        for p in [self.ui.p_p, self.ui.p_in, self.ui.p_out, self.ui.p_bat]:
            v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color=CROSSHAIR_COLOR, width=1.5, style=Qt.DashLine))
            v_line.setVisible(False)
            p.addItem(v_line, ignoreBounds=True)
            self.v_lines.append(v_line)
        self.hud_label = QLabel(self.ui.graph_widget)
        self.hud_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._apply_crosshair_theme()
        self.hud_label.hide()
        self.ui.graph_widget.installEventFilter(self)
        self.proxy = pg.SignalProxy(self.ui.graph_widget.scene().sigMouseMoved, rateLimit=60, slot=self.on_mouse_moved)

    def hide_tooltip(self):
        if hasattr(self, 'hud_label') and self.hud_label.isVisible(): self.hud_label.hide()
        if hasattr(self, 'v_lines'):
            for line in self.v_lines: line.setVisible(False)

    def on_mouse_moved(self, evt):
        try:
            if (
                not self._is_chart_tab_active()
                or self.auto_scroll_chart
                or not getattr(self, 'view_data', {}).get('x')
            ):
                self.hide_tooltip()
                return
            pos = evt[0]
            mouse_point = None
            active_p = None
            for p in [self.ui.p_p, self.ui.p_in, self.ui.p_out, self.ui.p_bat]:
                if p.sceneBoundingRect().contains(pos): mouse_point = p.vb.mapSceneToView(pos); active_p = p; break
            if mouse_point and active_p:
                x_val = mouse_point.x()
                x_arr = self.view_data['x']
                idx = bisect.bisect_left(x_arr, x_val)
                idx = max(0, min(idx, len(x_arr) - 1))
                if idx > 0 and abs(x_val - x_arr[idx-1]) < abs(x_val - x_arr[idx]): idx = idx - 1
                closest_x = x_arr[idx]
                try: p_val, vi_val, ii_val, vo_val, io_val, vb_val, ib_val = self.view_data['p'][idx], self.view_data['vi'][idx], self.view_data['ii'][idx], self.view_data['vo'][idx], self.view_data['io'][idx], self.view_data['vb'][idx], self.view_data['ib'][idx]
                except IndexError: self.hide_tooltip(); return
                for line in self.v_lines: line.setPos(closest_x); line.setVisible(True)
                html = (
                    f"<div style='font-size: {FS_SUBTITLE}pt; line-height: 1.5; color:{HUD_TEXT};'>"
                    f"<b style='color:{HUD_TEXT}; font-size: {FS_SUBTITLE + 1}pt;'>⏱ {closest_x:.2f} s</b>"
                    f"<hr style='border: 1px solid {TEMP_NORMAL_BORDER}; margin: 4px 0;'>"
                )
                if active_p == self.ui.p_p: html += f"<b>PWR:</b> <span style='color:{CHART_POWER}'>{p_val:.2f} W</span>"
                elif active_p == self.ui.p_in: html += f"<b>IN :</b> <span style='color:{CHART_VOLTAGE}'>{vi_val:.2f} V</span> / <span style='color:{CHART_CURRENT}'>{ii_val:.2f} A</span>"
                elif active_p == self.ui.p_out: html += f"<b>OUT:</b> <span style='color:{CHART_VOLTAGE}'>{vo_val:.2f} V</span> / <span style='color:{CHART_CURRENT}'>{io_val:.2f} A</span>"
                elif active_p == self.ui.p_bat: html += f"<b>BAT:</b> <span style='color:{CHART_VOLTAGE}'>{vb_val:.2f} V</span> / <span style='color:{CHART_CURRENT}'>{ib_val:.2f} A</span>"
                self.hud_label.setText(html + "</div>")
                self.hud_label.adjustSize()
                local_pos = self.ui.graph_widget.mapFromGlobal(QCursor.pos())
                self.hud_label.move(local_pos.x() + 15, local_pos.y() + 15)
                self.hud_label.raise_()
                self.hud_label.show()
            else: self.hide_tooltip()
        except Exception:
            logger.debug("on_mouse_moved failed", exc_info=True)
            self.hide_tooltip()

    def _setup_view_menu(self):
        self._view_menu = QMenu(self)

        self._panel_menu = self._view_menu.addMenu(tr('menu.panels'))
        panels_cfg = config_module.CONFIG.get('ui', {}).get('panels', {})

        self._act_tool_serial = self._panel_menu.addAction(tr('tool.serial_tool.name'))
        self._act_tool_serial.setCheckable(True)
        self._act_tool_serial.setChecked(bool(panels_cfg.get('serial_tool', True)))

        self._act_tool_waveform = self._panel_menu.addAction(tr('tool.waveform_scope.name'))
        self._act_tool_waveform.setCheckable(True)
        self._act_tool_waveform.setChecked(bool(panels_cfg.get('waveform_scope', False)))

        self._act_tool_tektronix = self._panel_menu.addAction(tr('tool.tektronix_scope.name'))
        self._act_tool_tektronix.setCheckable(True)
        self._act_tool_tektronix.setChecked(bool(panels_cfg.get('tektronix_scope', True)))

        self._panel_toggles = (
            (self._act_tool_serial, self.ui.log_panel),
            (self._act_tool_waveform, self.ui.chart_panel),
            (self._act_tool_tektronix, self.ui.tektronix_panel),
        )
        for action, _panel in self._panel_toggles:
            action.toggled.connect(self._on_panel_visibility_changed)

        self._view_menu.addSeparator()

        self._lang_menu = self._view_menu.addMenu(tr('menu.language'))
        self._lang_group = QActionGroup(self)
        self._act_lang_en = self._lang_menu.addAction('English')
        self._act_lang_en.setCheckable(True)
        self._lang_group.addAction(self._act_lang_en)
        self._act_lang_zh = self._lang_menu.addAction('中文')
        self._act_lang_zh.setCheckable(True)
        self._lang_group.addAction(self._act_lang_zh)
        self._lang_group.triggered.connect(self._on_language_selected)
        if get_language() == 'en':
            self._act_lang_en.setChecked(True)
        else:
            self._act_lang_zh.setChecked(True)

        self._theme_menu = self._view_menu.addMenu(tr('menu.theme'))
        self._theme_group = QActionGroup(self)
        self._act_theme_dark = self._theme_menu.addAction(tr('menu.theme_dark'))
        self._act_theme_dark.setCheckable(True)
        self._theme_group.addAction(self._act_theme_dark)
        self._act_theme_light = self._theme_menu.addAction(tr('menu.theme_light'))
        self._act_theme_light.setCheckable(True)
        self._theme_group.addAction(self._act_theme_light)
        self._theme_group.triggered.connect(self._on_theme_selected)
        self._sync_theme_menu_checks()
        self._apply_view_menu_theme()

        self.ui.main_tabs.currentChanged.connect(self._on_main_tab_changed)
        self._apply_panel_visibility_from_menu()

    def _apply_panel_visibility_from_menu(self):
        for action, panel in getattr(self, '_panel_toggles', ()):
            self._set_tab_visible(panel, action.isChecked())
        self._ensure_visible_tab()
        QTimer.singleShot(0, self._finalize_panel_layout)

    def _apply_view_menu_theme(self):
        from ..ui.theme import menu_popup_stylesheet
        self._view_menu.setStyleSheet(menu_popup_stylesheet())

    def _tool_panels(self):
        return (self.ui.log_panel, self.ui.chart_panel, self.ui.tektronix_panel)

    def _sync_panel_menu_checks(self):
        for action, panel in getattr(self, '_panel_toggles', ()):
            action.blockSignals(True)
            action.setChecked(self._is_tab_visible(panel))
            action.blockSignals(False)

    def _on_panel_visibility_changed(self, _checked=False):
        if not any(action.isChecked() for action, _ in self._panel_toggles):
            sender = self.sender()
            if sender is not None:
                sender.blockSignals(True)
                sender.setChecked(True)
                sender.blockSignals(False)
            return
        sender = self.sender()
        for action, panel in self._panel_toggles:
            visible = action.isChecked()
            self._set_tab_visible(panel, visible)
            if sender is action and visible:
                self.ui.main_tabs.setCurrentWidget(panel)
        self._ensure_visible_tab()
        QTimer.singleShot(0, self._finalize_panel_layout)

    def _on_theme_selected(self, action):
        theme = 'light' if action is self._act_theme_light else 'dark'
        self._set_theme(theme)

    def _sync_theme_menu_checks(self):
        if get_theme() == 'light':
            self._act_theme_light.setChecked(True)
        else:
            self._act_theme_dark.setChecked(True)

    def _set_theme(self, theme):
        if get_theme() == theme:
            return
        set_theme(theme)
        update_config({'ui': {'theme': theme}})
        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet(full_stylesheet())
        self.statusBar().setStyleSheet(status_bar_stylesheet())
        self.menuBar().setStyleSheet(menu_bar_stylesheet())
        self.ui.reapply_theme(self)
        for page in self._iter_log_pages():
            page.reapply_theme()
        self._apply_crosshair_theme()
        apply_editable_combo_line_edit(self.ui.cb_baudrate)
        self._refresh_main_tabs()
        self._refresh_log_file_tabs()
        self._update_monitor_button()
        self._update_session_label()
        self._retranslate_idle_status()
        self._sync_theme_menu_checks()
        self._apply_view_menu_theme()
        self.qi_parser.clear_parse_cache()

    def _apply_crosshair_theme(self):
        if not hasattr(self.ui, 'graph_widget'):
            return
        for v_line in getattr(self, 'v_lines', []):
            v_line.setPen(pg.mkPen(color=CROSSHAIR_COLOR, width=1.5, style=Qt.DashLine))
        self.hud_label.setStyleSheet(
            f"QLabel {{ background-color: {HUD_BG_RGBA}; color: {HUD_TEXT}; "
            f"border: 1px solid {HUD_BORDER}; border-radius: 6px; padding: 10px; "
            f"{ui_font_css(FS_SUBTITLE, FW_NORMAL, family=FONT_FAMILY_MONO)} }}"
        )

    def _setup_unified_header(self):
        """WiParse settings (tools, language, theme) on the tab bar corner."""
        btn = QToolButton(self)
        btn.setObjectName('settings_menu_btn')
        btn.setPopupMode(QToolButton.InstantPopup)
        btn.setMenu(self._view_menu)
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.setCursor(Qt.ArrowCursor)
        self._settings_btn = btn
        self._sync_settings_btn_text()
        self.ui.main_tabs.setCornerWidget(btn, Qt.TopRightCorner)
        self.menuBar().hide()
        QTimer.singleShot(0, self._cache_header_height)

    def _sync_settings_btn_text(self):
        btn = getattr(self, '_settings_btn', None)
        if btn is not None:
            btn.setText(tr('menu.settings').replace('&', ''))

    def _main_header_widgets(self):
        widgets = [self.ui.main_tabs.tabBar()]
        btn = getattr(self, '_settings_btn', None)
        if btn is not None:
            widgets.append(btn)
        return widgets

    def _setup_menu_bar_auto_hide(self):
        self._menu_bar_auto_hide = bool(
            config_module.CONFIG.get('ui', {}).get('menu_bar_auto_hide', False)
        )
        self._menu_bar_hide_timer = QTimer(self)
        self._menu_bar_hide_timer.setSingleShot(True)
        self._menu_bar_hide_timer.setInterval(400)
        self._menu_bar_hide_timer.timeout.connect(self._hide_menu_bar_if_needed)
        self._header_poll_timer = QTimer(self)
        self._header_poll_timer.setInterval(80)
        self._header_poll_timer.timeout.connect(self._poll_header_auto_hide)
        self._cached_header_height = 0

        for widget in self._main_header_widgets():
            widget.setContextMenuPolicy(Qt.CustomContextMenu)
            widget.customContextMenuRequested.connect(self._on_menu_bar_context_menu)
            widget.installEventFilter(self)

        self.ui.main_tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.main_tabs.customContextMenuRequested.connect(self._on_menu_bar_context_menu)
        self.ui.main_tabs.setMouseTracking(True)
        self.ui.main_tabs.installEventFilter(self)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        central = self.centralWidget()
        if central is not None:
            central.setMouseTracking(True)
            central.installEventFilter(self)
        self.setMouseTracking(True)
        self.installEventFilter(self)

        if self._menu_bar_auto_hide:
            self._hide_main_header()
            self._header_poll_timer.start()

    def _cache_header_height(self):
        bar = self.ui.main_tabs.tabBar()
        btn = getattr(self, '_settings_btn', None)
        heights = [bar.sizeHint().height(), bar.height()]
        if btn is not None:
            heights.extend((btn.sizeHint().height(), btn.height()))
        h = max(h for h in heights if h > 0) if any(h > 0 for h in heights) else 0
        if h > 0:
            self._cached_header_height = h

    def _header_reveal_zone_height(self):
        scale = getattr(self, '_ui_scale', 1.0)
        cached = getattr(self, '_cached_header_height', 0)
        return max(cached, int(28 * scale)) + int(4 * scale)

    def _pointer_in_header_reveal_zone(self):
        if not self.isVisible():
            return False
        pos = self.mapFromGlobal(QCursor.pos())
        if pos.x() < 0 or pos.x() > self.width() or pos.y() < 0:
            return False
        zone = self._header_reveal_zone_height()
        if getattr(self, '_menu_bar_auto_hide', False):
            return pos.y() <= zone
        tabs = self.ui.main_tabs
        tabs_top = tabs.mapTo(self, tabs.rect().topLeft()).y()
        return tabs_top <= pos.y() <= tabs_top + zone

    def _is_header_context_menu_event(self, event):
        if event.type() == QEvent.ContextMenu:
            return True
        return event.type() == QEvent.MouseButtonPress and event.button() == Qt.RightButton

    def _poll_header_auto_hide(self):
        if not getattr(self, '_menu_bar_auto_hide', False) or not self.isVisible():
            return
        widgets = self._main_header_widgets()
        visible = any(w.isVisible() for w in widgets)
        in_zone = self._pointer_in_header_reveal_zone()
        if not visible and in_zone:
            self._menu_bar_hide_timer.stop()
            self._show_main_header()
        elif visible and not in_zone and not self._menu_bar_hide_timer.isActive():
            self._menu_bar_hide_timer.start()

    def _on_menu_bar_context_menu(self, pos):
        sender = self.sender()
        if sender is not None:
            self._show_header_context_menu(sender.mapToGlobal(pos))
        else:
            self._show_header_context_menu(QCursor.pos())

    def _show_header_context_menu(self, global_pos):
        if self._menu_bar_auto_hide:
            self._menu_bar_hide_timer.stop()
            self._show_main_header()
        menu = QMenu(self)
        group = QActionGroup(self)
        act_auto_hide = menu.addAction(tr('menu.menu_bar_auto_hide'))
        act_auto_hide.setCheckable(True)
        group.addAction(act_auto_hide)
        act_always_show = menu.addAction(tr('menu.menu_bar_always_show'))
        act_always_show.setCheckable(True)
        group.addAction(act_always_show)
        if self._menu_bar_auto_hide:
            act_auto_hide.setChecked(True)
        else:
            act_always_show.setChecked(True)

        def on_selected(selected):
            self._set_menu_bar_auto_hide(selected is act_auto_hide)

        group.triggered.connect(on_selected)
        menu.exec_(global_pos)

    def _set_menu_bar_auto_hide(self, auto_hide):
        if auto_hide == self._menu_bar_auto_hide:
            return
        self._menu_bar_auto_hide = auto_hide
        update_config({'ui': {'menu_bar_auto_hide': auto_hide}})
        self._menu_bar_hide_timer.stop()
        if auto_hide:
            self._hide_menu_bar_if_needed()
            self._header_poll_timer.start()
        else:
            self._header_poll_timer.stop()
            self._show_main_header()

    def _show_main_header(self):
        for widget in self._main_header_widgets():
            if not widget.isVisible():
                widget.show()
        QTimer.singleShot(0, self._cache_header_height)

    def _hide_main_header(self):
        for widget in self._main_header_widgets():
            widget.hide()

    def _hide_menu_bar_if_needed(self):
        if not self._menu_bar_auto_hide:
            return
        if self._pointer_in_header_reveal_zone():
            return
        self._hide_main_header()

    def _tab_index(self, panel):
        return self.ui.main_tabs.indexOf(panel)

    def _set_tab_visible(self, panel, visible):
        idx = self._tab_index(panel)
        if idx < 0:
            return
        tab_bar = self.ui.main_tabs.tabBar()
        if hasattr(tab_bar, 'setTabVisible'):
            tab_bar.setTabVisible(idx, visible)

    def _is_tab_visible(self, panel):
        idx = self._tab_index(panel)
        if idx < 0:
            return False
        tab_bar = self.ui.main_tabs.tabBar()
        if hasattr(tab_bar, 'isTabVisible'):
            return tab_bar.isTabVisible(idx)
        return True

    def _is_chart_tab_active(self):
        if not self._is_tab_visible(self.ui.chart_panel):
            return False
        return self.ui.main_tabs.currentWidget() == self.ui.chart_panel

    def _ensure_visible_tab(self):
        tabs = self.ui.main_tabs
        current = tabs.currentWidget()
        if current is not None and self._is_tab_visible(current):
            return
        for panel in self._tool_panels():
            if self._is_tab_visible(panel):
                tabs.setCurrentWidget(panel)
                return

    def _on_main_tab_changed(self, _index):
        self.hide_tooltip()
        if self._is_chart_tab_active() and hasattr(self.ui, 'graph_widget'):
            QTimer.singleShot(0, self.ui.graph_widget.updateGeometry)

    def _finalize_panel_layout(self):
        reflow_tab_widget(self.ui.main_tabs, preset='main')
        apply_log_control_panel_theme(self.ui)
        if not self._is_chart_tab_active():
            self.hide_tooltip()
        current = self.ui.main_tabs.currentWidget()
        if current is not None:
            current.updateGeometry()
        if self._is_chart_tab_active() and hasattr(self.ui, 'graph_widget'):
            self.ui.graph_widget.updateGeometry()
        tek_panel = getattr(self.ui, 'tektronix_panel', None)
        if tek_panel is not None and self.ui.main_tabs.currentWidget() is tek_panel:
            scope = getattr(self.ui, 'tektronix_scope', None)
            if scope is not None and hasattr(scope, 'label'):
                scope.label.updateGeometry()

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, '_initial_layout_done', False):
            QTimer.singleShot(0, self._finalize_panel_layout)
            self._initial_layout_done = True
        QTimer.singleShot(0, self._cache_header_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.hide_tooltip()
        if self._is_chart_tab_active() and hasattr(self.ui, 'graph_widget'):
            self.ui.graph_widget.updateGeometry()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowDeactivate:
            self.hide_tooltip()

    def eventFilter(self, obj, event):
        if self._is_header_context_menu_event(event) and self.isActiveWindow() and self._pointer_in_header_reveal_zone():
            self._show_header_context_menu(event.globalPos())
            return True
        if getattr(self, '_menu_bar_auto_hide', False):
            header_widgets = set(self._main_header_widgets())
            if obj in header_widgets:
                if event.type() == QEvent.Enter:
                    self._menu_bar_hide_timer.stop()
                    self._show_main_header()
                elif event.type() == QEvent.Leave:
                    self._menu_bar_hide_timer.start()
            elif obj in (self, self.centralWidget(), self.ui.main_tabs):
                if event.type() == QEvent.MouseMove and self._pointer_in_header_reveal_zone():
                    self._menu_bar_hide_timer.stop()
                    self._show_main_header()
        if obj == self.ui.graph_widget and event.type() in (QEvent.Leave, QEvent.Hide):
            self.hide_tooltip()
        edit = self._log_edit_for_viewport(obj)
        if edit is not None:
            page = self._log_page_for_edit(edit)
            parse_enabled = page.is_auto_parse_enabled_for_edit(edit) if page else False
            if event.type() == QEvent.MouseMove:
                if not parse_enabled:
                    if self._hover_state is not None:
                        QToolTip.hideText()
                        self._hover_state = None
                    return super().eventFilter(obj, event)
                cursor = edit.cursorForPosition(event.pos())
                hover = (edit, cursor.blockNumber())
                if hover != self._hover_state:
                    self._hover_state = hover
                    info = self.qi_parser.parse_message(cursor.block().text())
                    if info:
                        QToolTip.showText(event.globalPos(), info, edit)
                    else:
                        QToolTip.hideText()
            elif event.type() == QEvent.Leave:
                QToolTip.hideText()
                self._hover_state = None
        return super().eventFilter(obj, event)

    def show_protection_alert(self, alert_type, trigger_val, threshold_val, unit):
        ts_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self.append_log(
            time.time(),
            tr(
                'status.protection_log',
                time=ts_str,
                type=alert_type,
                value=trigger_val,
                unit=unit,
                threshold=threshold_val,
            ),
        )
        self._set_status(
            tr('status.alert', type=alert_type, value=trigger_val, unit=unit, threshold=threshold_val),
            'error',
        )
        self._alert_clear_timer.start(15000)
        self.statusBar().showMessage(tr('status.alert_bar', type=alert_type), 8000)

    def render_log_ui(self):
        if self.log_buffer:
            self.ui_lock = True
            self._live_log().append_lines(list(self.log_buffer))
            self.ui_lock = False
            self.log_buffer.clear()

    def _lcd_value_changed(self, key: str, val) -> bool:
        prev = self._last_lcd_snapshot.get(key)
        if isinstance(val, float):
            if prev is not None and abs(float(prev) - val) < 0.005:
                return False
        elif prev == val:
            return False
        self._last_lcd_snapshot[key] = val
        return True

    def _update_lcds_if_changed(self, d):
        mapping = (
            ('v_in', self.ui.lcd_v_in),
            ('i_in', self.ui.lcd_i_in),
            ('v_out', self.ui.lcd_v_out),
            ('i_out', self.ui.lcd_i_out),
            ('p', self.ui.lcd_power),
            ('v_bat', self.ui.lcd_v_bat),
            ('i_bat', self.ui.lcd_i_bat),
            ('b', self.ui.lcd_battery),
            ('t', self.ui.lcd_temp),
        )
        for key, lcd in mapping:
            val = d[key]
            if self._lcd_value_changed(key, val):
                lcd.display(f"{val:.2f}" if isinstance(val, float) else f"{val}")

    def render_metrics_ui(self):
        if not self.latest_data:
            return
        d = self.latest_data
        self._update_lcds_if_changed(d)

        ovp = config_module.CONFIG['alerts'].get('ovp_threshold', 25.0)
        ocp = config_module.CONFIG['alerts'].get('ocp_threshold', 3.0)
        temp_w = config_module.CONFIG['alerts'].get('temp_warning_threshold', 60)
        temp_r = config_module.CONFIG['alerts'].get('temp_recovery_threshold', 55)
        max_v = max(d['v_in'], d['v_out'])
        if max_v >= ovp:
            if 'OVP' not in self._active_alerts:
                self._active_alerts.add('OVP')
                self.show_protection_alert(tr('protect.ovp'), max_v, ovp, "V")
        elif max_v < ovp - 1.0:
            self._active_alerts.discard('OVP')

        max_i = max(d['i_in'], d['i_out'])
        if max_i >= ocp:
            if 'OCP' not in self._active_alerts:
                self._active_alerts.add('OCP')
                self.show_protection_alert(tr('protect.ocp'), max_i, ocp, "A")
        elif max_i < ocp - 0.2:
            self._active_alerts.discard('OCP')

        if d['t'] >= temp_w:
            self.ui.lcd_temp.setStyleSheet(
                f'background-color: {TEMP_ALERT_BG}; color: {TEMP_ALERT_FG}; '
                f'border: 2px solid {TEMP_ALERT_BORDER}; border-radius: 4px;'
            )
            if not getattr(self, '_temp_warned', False):
                self.append_log(
                    time.time(),
                    tr('status.temp_warning_log', time=datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3], temp=d['t']),
                )
                self._temp_warned = True
            if 'OTP' not in self._active_alerts:
                self._active_alerts.add('OTP')
                self.show_protection_alert(tr('protect.otp'), d['t'], temp_w, "°C")
        else:
            apply_lcd_style(self.ui.lcd_temp, LCD_TEMP)
            if d['t'] < temp_r:
                self._temp_warned = False
                self._active_alerts.discard('OTP')

        if self.worker and self.worker.isRunning():
            stable = self._charge_state_tracker.update(self.y_vb, self.y_ib)
            battery_pct = float(d.get('b', 0) or 0)
            if stable == 'trickle' and battery_pct >= 100.0:
                if self._full_charge_start_time is None:
                    self._full_charge_start_time = time.time()
                else:
                    debounce = config_module.CONFIG['alerts'].get('full_charge_debounce_sec', 20.0)
                    if not self._full_charge_alerted and (time.time() - self._full_charge_start_time >= debounce):
                        self.show_full_charge_alert(debounce)
                        self._full_charge_alerted = True
            else:
                self._full_charge_start_time = None
                self._full_charge_alerted = False

    def render_chart_ui(self):
        if not (self.worker and self.worker.isRunning()):
            return
        if self.auto_scroll_chart:
            if not self.x_data:
                return
            self.ui.line_power.setData(self.x_data, self.y_p)
            self.ui.line_v_in.setData(self.x_data, self.y_vi)
            self.ui.line_i_in.setData(self.x_data, self.y_ii)
            self.ui.line_v_out.setData(self.x_data, self.y_vo)
            self.ui.line_i_out.setData(self.x_data, self.y_io)
            self.ui.line_v_bat.setData(self.x_data, self.y_vb)
            self.ui.line_i_bat.setData(self.x_data, self.y_ib)
            self.view_data = {
                'x': self.x_data, 'p': self.y_p, 'vi': self.y_vi, 'ii': self.y_ii,
                'vo': self.y_vo, 'io': self.y_io, 'vb': self.y_vb, 'ib': self.y_ib,
                't': self.y_t, 'b': self.y_b,
            }
            cur_t = self.x_data[-1]
            win = config_module.CONFIG['ui'].get('default_window_size_sec', 60.0)
            xlim = [cur_t - win, cur_t + win * 0.05] if cur_t > win else [0, max(cur_t + 1, win)]
            self.ui.p_p.setXRange(xlim[0], xlim[1], padding=0)
            self.last_forced_xlim = xlim
        else:
            self.request_chart_fetch()

    def render_ui(self):
        """Backward-compatible alias for legacy callers."""
        self.render_log_ui()
        self.render_metrics_ui()
        self.render_chart_ui()

    def on_chart_fetched(self, data):
        if not data or len(data) < 10 or not data[0]: return
        hx, hp, hvi, hii, hvo, hio, hvb, hib, ht, hb = data
        self.ui.line_power.setData(hx, hp)
        self.ui.line_v_in.setData(hx, hvi)
        self.ui.line_i_in.setData(hx, hii)
        self.ui.line_v_out.setData(hx, hvo)
        self.ui.line_i_out.setData(hx, hio)
        self.ui.line_v_bat.setData(hx, hvb)
        self.ui.line_i_bat.setData(hx, hib)
        self.view_data = {'x':hx, 'p':hp, 'vi':hvi, 'ii':hii, 'vo':hvo, 'io':hio, 'vb':hvb, 'ib':hib, 't':ht, 'b':hb}

    def _is_demo_mode_enabled(self):
        return self._cli_demo_mode or config_module.CONFIG.get('serial', {}).get('demo_mode', False)

    def _reset_monitor_ui_after_failure(self):
        self._demo_mode_active = False
        self._monitoring_active = False
        self._starting_monitor = False
        self._stopping_monitor = False
        self.auto_scroll_chart = False
        self._charge_state_tracker.reset()
        if self.worker:
            self.worker.stop()
            self.worker = None
        self._close_live_log_file()
        self._schedule_monitor_button_update()

    def on_serial_connection_failed(self, msg):
        if self._is_demo_mode_enabled():
            self._starting_monitor = False
            self._monitoring_active = True
            self._demo_mode_active = True
            self._schedule_monitor_button_update()
            logger.warning("Serial unavailable, continuing in demo mode: %s", msg)
            QMessageBox.warning(
                self,
                tr('dialog.demo_mode'),
                tr('msg.demo_body', detail=msg),
            )
            return
        logger.error("Serial connection failed, monitoring stopped: %s", msg)
        QMessageBox.critical(
            self,
            tr('dialog.serial_failed'),
            tr('msg.serial_failed_body', detail=msg),
        )
        close_session(self.current_session_id)
        self.current_session_id = None
        self._update_session_label()
        self._reset_monitor_ui_after_failure()

    def on_serial_connection_lost(self, msg):
        logger.error("Serial connection lost: %s", msg)
        self._set_status(tr('status.serial_stopped'), 'error')
        QMessageBox.warning(
            self,
            tr('dialog.serial_lost'),
            tr('msg.serial_lost_body', detail=msg),
        )
        close_session(self.current_session_id)
        self.current_session_id = None
        self._update_session_label()
        self._reset_monitor_ui_after_failure()

    def on_serial_reconnecting(self, attempt, maximum):
        self._set_status(tr('status.reconnecting', attempt=attempt, maximum=maximum), 'warn')

    def _on_serial_connection_opened(self):
        if not self._starting_monitor:
            return
        self._starting_monitor = False
        self._monitoring_active = True
        self._schedule_monitor_button_update()
        logger.info('Serial port opened; monitoring active')

    def _finalize_monitor_stop(self):
        self._monitoring_active = False
        self._starting_monitor = False
        self._stopping_monitor = False
        self._close_live_log_file()
        if self.current_session_id:
            close_session(self.current_session_id)
            self._set_status(tr('status.session_ended', id=self.current_session_id), 'normal')
        self.current_session_id = None
        self._update_session_label()
        self.auto_scroll_chart = False
        self.hide_tooltip()
        self._schedule_monitor_button_update()
        self.request_chart_fetch()

    def start_mon(self):
        if self._monitoring_active or self._starting_monitor or self._stopping_monitor:
            return
        if self.ui.cb_port.currentText() == tr('port.none'):
            QMessageBox.warning(self, tr('dialog.no_device'), tr('msg.no_serial_device'))
            return
        self._demo_mode_active = False
        demo_mode = self._is_demo_mode_enabled()
        port = self.ui.cb_port.currentText()
        baud_text = self.ui.cb_baudrate.currentText().strip()
        try:
            baud = int(baud_text)
        except ValueError:
            QMessageBox.warning(self, tr('dialog.notice'), tr('msg.invalid_baudrate', value=baud_text))
            return
        if baud <= 0:
            QMessageBox.warning(self, tr('dialog.notice'), tr('msg.invalid_baudrate', value=baud_text))
            return
        self.current_session_id, _, _ = create_session(port, baud, demo_mode)
        self._update_session_label()
        self._set_status(tr('status.monitoring', id=self.current_session_id), 'info')
        try:
            conn = sqlite3.connect(db_path())
            max_t = conn.execute("SELECT MAX(rel_time) FROM charging_metrics").fetchone()[0]
            conn.close()
            self.time_offset = (max_t if max_t is not None else 0.0) + 1.0
        except Exception:
            logger.warning("Failed to read max rel_time, starting from 0", exc_info=True)
            self.time_offset = 0.0
        self.start_time, self.ui_lock = time.time(), True
        live = self._live_log()
        self.ui.log_file_tabs.setCurrentWidget(live)
        self._update_live_log_tab_title()
        live.clear()
        self.ui_lock = False
        self.log_buffer.clear()
        self._open_live_log_file()
        self.auto_scroll_chart = True
        self.hide_tooltip()
        self._temp_warned = False
        self._active_alerts.clear()
        self._charge_state_tracker.reset()
        self._full_charge_start_time = None
        self._full_charge_alerted = False
        self._last_lcd_snapshot.clear()
        for arr in (self.x_data, self.y_vi, self.y_ii, self.y_vo, self.y_io, self.y_vb, self.y_ib, self.y_eff, self.y_p, self.y_t, self.y_b):
            arr.clear()
        self.view_data = {'x': [], 'p': [], 'vi': [], 'ii': [], 'vo': [], 'io': [], 'vb': [], 'ib': [], 't': [], 'b': []}
        serial_cfg = config_module.CONFIG.get('serial', {})
        self.worker = SerialWorker(
            port, baud, demo_mode=demo_mode,
            auto_reconnect=serial_cfg.get('auto_reconnect', True),
            reconnect_interval=serial_cfg.get('reconnect_interval_sec', 3.0),
            max_reconnect_attempts=serial_cfg.get('max_reconnect_attempts', 5),
        )
        self.worker.data_ready.connect(self.process_data)
        self.worker.log_ready.connect(self.append_log)
        self.worker.logs_batch_ready.connect(self.append_logs_batch)
        self.worker.connection_opened.connect(self._on_serial_connection_opened)
        self.worker.connection_failed.connect(self.on_serial_connection_failed)
        self.worker.connection_lost.connect(self.on_serial_connection_lost)
        self.worker.reconnecting.connect(self.on_serial_reconnecting)
        self.worker.finished.connect(self._on_worker_finished)
        self._starting_monitor = True
        self.worker.start()
        self._schedule_monitor_button_update()
        logger.info("Monitoring start requested: session=%s port=%s baud=%s demo=%s", self.current_session_id, port, baud, demo_mode)

    def stop_mon(self):
        if self._stopping_monitor:
            return
        if not (self._monitoring_active or self._starting_monitor or self.worker):
            return
        self._stopping_monitor = True
        self._schedule_monitor_button_update()
        worker = self.worker
        if worker is not None:
            try:
                worker.finished.disconnect(self._on_worker_finished)
            except (TypeError, RuntimeError):
                pass
            worker.stop()
            self.worker = None
        self._finalize_monitor_stop()
        logger.info('Monitoring stopped after serial close confirmed')

    def scan_ports(self, notify=False):
        prev = self.ui.cb_port.currentText()
        if prev in (tr_in('zh', 'port.none'), tr_in('en', 'port.none'), 'No Device', 'No port'):
            prev = tr('port.none')
        ports = list(serial.tools.list_ports.comports())
        devices = [p.device for p in ports]
        expected = devices if devices else [tr('port.none')]
        current_items = [self.ui.cb_port.itemText(i) for i in range(self.ui.cb_port.count())]
        if current_items == expected:
            return False

        monitoring = self._monitoring_active or self._starting_monitor or self._stopping_monitor
        self.ui.cb_port.blockSignals(True)
        self.ui.cb_port.clear()
        if not devices:
            self.ui.cb_port.addItem(tr('port.none'))
        else:
            for device in devices:
                self.ui.cb_port.addItem(device)
        if not monitoring:
            idx = self.ui.cb_port.findText(prev)
            if idx >= 0:
                self.ui.cb_port.setCurrentIndex(idx)
            elif len(devices) == 1:
                self.ui.cb_port.setCurrentIndex(0)
        self.ui.cb_port.blockSignals(False)

        count = len(devices)
        if notify:
            if count:
                self._set_status(tr('status.ports_updated', count=count), 'info')
            else:
                self._set_status(tr('status.no_ports'), 'warn')
        logger.info("Ports scanned: %d device(s)", count)
        return True

    def process_data(self, data):
        self.latest_data = data
        t = data['ts'] - self.start_time + self.time_offset
        self.db_worker.queue.put({
            'type': 'metric', 'rel_time': t, 'data': data,
            'session_id': self.current_session_id,
        })
        self.x_data.append(t)
        self.y_vi.append(data['v_in'])
        self.y_ii.append(data['i_in'])
        self.y_vo.append(data['v_out'])
        self.y_io.append(data['i_out'])
        self.y_vb.append(data['v_bat'])
        self.y_ib.append(data['i_bat'])
        self.y_eff.append(data['eff'])
        self.y_p.append(data['p'])
        self.y_t.append(data['t'])
        self.y_b.append(data['b'])
        max_pts = config_module.CONFIG['ui'].get('chart_max_points', 500)
        if len(self.x_data) > max_pts:
            [a.pop(0) for a in [self.x_data, self.y_vi, self.y_ii, self.y_vo, self.y_io, self.y_vb, self.y_ib, self.y_eff, self.y_p, self.y_t, self.y_b]]

    def on_chart_manual_interaction(self, *args, **kwargs):
        xlim = self.ui.p_p.viewRange()[0]
        if self.auto_scroll_chart and hasattr(self, 'last_forced_xlim'):
            if abs(xlim[0] - self.last_forced_xlim[0]) < 0.5: return
        if self.x_data and xlim[1] >= self.x_data[-1] - max(1.0, (xlim[1]-xlim[0])*0.05):
            if not self.auto_scroll_chart:
                self.auto_scroll_chart = True
                self.hide_tooltip()
            return
        if self.auto_scroll_chart:
            self.auto_scroll_chart = False
        self.request_chart_fetch()

    def on_chart_double_clicked(self, evt):
        if evt.double():
            pos = evt.scenePos()
            mouse_point = None
            for p in [self.ui.p_p, self.ui.p_in, self.ui.p_out, self.ui.p_bat]:
                if p.sceneBoundingRect().contains(pos): mouse_point = p.vb.mapSceneToView(pos); break
            if mouse_point: self.sync_log_to_time(mouse_point.x())

    def request_chart_fetch(self):
        if not self.auto_scroll_chart: self.fetch_worker.latest_xlim, self.fetch_worker.chart_request = self.ui.p_p.viewRange()[0], True

    def closeEvent(self, event):
        if self.current_session_id:
            close_session(self.current_session_id)
            self.current_session_id = None
        self.stop_mon()
        self.hide_tooltip()
        self._close_live_log_file()
        if hasattr(self, '_port_watcher'):
            self._port_watcher.stop()
        if hasattr(self, 'db_worker'):
            self.db_worker.stop()
        if hasattr(self, 'fetch_worker'):
            self.fetch_worker.stop()
        if hasattr(self.ui, 'tektronix_scope'):
            self.ui.tektronix_scope.release_scopes()
        self._persist_open_log_files()
        event.accept()
