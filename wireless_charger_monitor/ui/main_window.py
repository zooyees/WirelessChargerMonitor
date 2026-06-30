"""Main window controller."""
import bisect
import datetime
import os
import sqlite3
import time

import pyqtgraph as pg
import serial.tools.list_ports
from PyQt5.QtCore import QEvent, Qt, QTimer
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
    QPlainTextEdit,
    QSizePolicy,
    QTextEdit,
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
from ..workers import DBWorker, FetchWorker, SerialWorker
from ..i18n import get_language, init_language, is_known_log_default_name, set_language, tr, tr_in
from .loader import Ui_MonitorWindow
from .log_tab_page import LogTabPage
from .tab_utils import refresh_tab_widget
from .theme import (
    FS_BODY,
    FS_CAPTION,
    FS_SUBTITLE,
    FONT_FAMILY_MONO,
    LCD_TEMP,
    TEXT_MUTED,
    apply_data_label_style,
    apply_editable_combo_line_edit,
    apply_log_control_panel_metrics,
    apply_status_message_style,
    apply_status_session_style,
    menu_bar_stylesheet,
    status_bar_stylesheet,
    ui_font_css,
    FW_NORMAL,
)

class MonitorWindow(QMainWindow):


    def __init__(self, cli_demo_mode=False):
        super().__init__()
        init_language(config_module.CONFIG.get('ui', {}).get('language', 'en'))
        self._cli_demo_mode = cli_demo_mode
        self._demo_mode_active = False
        self.current_session_id = None
        self.ui = Ui_MonitorWindow()
        self.ui.setupUi(self)
        init_db()
        self._setup_view_menu()

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
        self.timer.timeout.connect(self.render_ui)
        self.timer.start(config_module.CONFIG['ui']['render_interval_ms'])

        self._log_tabs_by_path = {}
        self._live_log_page = None
        self._live_log_file = None
        self._live_log_file_path = None
        self._setup_log_file_tabs()
        self._setup_live_log_settings()

        self.ui.btn_start.clicked.connect(self._toggle_monitor)
        self.ui.btn_open_log.clicked.connect(self.open_log_files)
        self.ui.btn_browse_log_dir.clicked.connect(self._browse_live_log_dir)
        self.ui.btn_new_live_log.clicked.connect(self._new_live_log_tab)

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
        self._view_menu.setTitle(tr('menu.settings'))
        self._panel_menu.setTitle(tr('menu.panels'))
        self._lang_menu.setTitle(tr('menu.language'))
        self._act_show_chart.setText(tr('tab.oscilloscope'))
        self._act_show_log.setText(tr('tab.log_monitor'))
        if get_language() == 'en':
            self._act_lang_en.setChecked(True)
        else:
            self._act_lang_zh.setChecked(True)

        tabs = self.ui.main_tabs
        tabs.setTabText(tabs.indexOf(self.ui.chart_panel), tr('tab.oscilloscope'))
        tabs.setTabText(tabs.indexOf(self.ui.log_panel), tr('tab.log_monitor'))

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
        refresh_tab_widget(self.ui.main_tabs, preset='main')

    def _refresh_log_file_tabs(self):
        refresh_tab_widget(self.ui.log_file_tabs, preset='file')

    def _apply_toolbar_metrics(self):
        scale = getattr(self, '_ui_scale', 1.0)
        en = get_language() == 'en'
        toolbar_sizes = (
            ('cb_port', 100 if en else 110),
            ('cb_baudrate', 88 if en else 96),
            ('btn_start', 72 if en else 88),
            ('btn_new_live_log', 52 if en else 56),
            ('edit_live_log_name', 96 if en else 120),
            ('edit_live_log_dir', 120 if en else 140),
            ('btn_browse_log_dir', 76 if en else 88),
            ('btn_open_log', 72 if en else 88),
        )
        for name, min_w in toolbar_sizes:
            if hasattr(self.ui, name):
                widget = getattr(self.ui, name)
                widget.setMinimumWidth(int(min_w * scale))
                widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        apply_log_control_panel_metrics(self.ui, scale)
        if hasattr(self.ui, 'edit_live_log_dir'):
            self.ui.edit_live_log_dir.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if hasattr(self.ui, 'edit_live_log_name'):
            self.ui.edit_live_log_name.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

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

    def _default_live_log_dir(self):
        rel = self._live_log_cfg().get('save_dir', 'logs')
        return str(project_path(rel))

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

    def _setup_live_log_settings(self):
        self.ui.edit_live_log_name.setText(self._default_live_log_name())
        self.ui.edit_live_log_dir.setText(self._default_live_log_dir())
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
        if self._live_log_page is None:
            return
        new_path = os.path.abspath(self._live_log_filepath())
        old_path = self._live_log_page.filepath or self._live_log_file_path
        if old_path:
            old_path = os.path.abspath(old_path)

        self._update_live_log_tab_title()

        if old_path and os.path.normcase(old_path) == os.path.normcase(new_path):
            return

        if old_path and os.path.isfile(old_path):
            if os.path.exists(new_path):
                QMessageBox.warning(self, tr('dialog.rename_failed'), tr('msg.file_exists', path=new_path))
                return
            try:
                had_open_handle = (
                    self._live_log_file is not None
                    and self._live_log_file_path
                    and os.path.normcase(self._live_log_file_path) == os.path.normcase(old_path)
                )
                if had_open_handle:
                    self._close_live_log_file()
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                os.rename(old_path, new_path)
            except OSError as e:
                logger.warning("Failed to rename live log file %s -> %s: %s", old_path, new_path, e)
                QMessageBox.warning(
                    self,
                    tr('dialog.rename_failed'),
                    tr('msg.cannot_rename', old_path=old_path, new_path=new_path, error=e),
                )
                if self.worker and self.worker.isRunning():
                    self._open_live_log_file()
                return
        else:
            try:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                if not os.path.exists(new_path):
                    with open(new_path, 'w', encoding='utf-8-sig', newline='\n'):
                        pass
            except OSError as e:
                logger.warning("Failed to create live log file %s: %s", new_path, e)
                QMessageBox.warning(self, tr('dialog.create_failed'), tr('msg.cannot_create_log', path=new_path, error=e))
                return

        self._live_log_page.filepath = new_path
        if self.worker and self.worker.isRunning():
            self._open_live_log_file()
        self._set_status(tr('status.log_updated', name=self._live_log_tab_title()), 'info')

    def _on_live_log_dir_changed(self):
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
            self._live_log_file = open(path, 'a', encoding='utf-8-sig', newline='\n')
            self._live_log_file_path = path
            if self._live_log_page is not None:
                self._live_log_page.filepath = path
        except OSError as e:
            logger.warning("Cannot open live log file %s: %s", path, e)
            self._set_status(tr('status.cannot_create_log', name=os.path.basename(path)), 'warn')
            QMessageBox.warning(self, tr('dialog.save_failed'), tr('msg.cannot_create_log', path=path, error=e))

    def _close_live_log_file(self):
        if self._live_log_file is not None:
            try:
                self._live_log_file.close()
            except OSError:
                pass
            self._live_log_file = None
        self._live_log_file_path = None

    def _reopen_live_log_file_if_active(self):
        if self.worker and self.worker.isRunning():
            self._open_live_log_file()

    def _write_live_log_line(self, msg):
        if self._live_log_file is None:
            return
        try:
            self._live_log_file.write(msg + '\n')
            self._live_log_file.flush()
        except OSError as e:
            logger.warning("Failed to write live log file: %s", e, exc_info=True)
            self._close_live_log_file()
            self._set_status(tr('status.log_write_failed'), 'error')

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
            norm = os.path.normcase(os.path.abspath(path))
            existing = self._log_tabs_by_path.get(norm)
            if existing is not None and self.ui.log_file_tabs.indexOf(existing) >= 0:
                self.ui.log_file_tabs.setCurrentWidget(existing)
                continue
            try:
                with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
                    content = f.read()
            except OSError as e:
                QMessageBox.warning(self, tr('dialog.open_failed'), tr('msg.cannot_read_file', path=path, error=e))
                continue
            page = self._create_log_tab_page(filepath=norm)
            page.set_content(content)
            title = os.path.splitext(os.path.basename(path))[0] or os.path.basename(path)
            self.ui.log_file_tabs.addTab(page, title)
            self.ui.log_file_tabs.setCurrentWidget(page)
            self._refresh_log_file_tabs()
            self._log_tabs_by_path[norm] = page
            opened += 1
        if opened:
            self._set_status(tr('status.opened_logs', count=opened), 'info')

    def _set_status(self, text, level='normal'):
        colors_map = {
            'normal': TEXT_MUTED, 'info': '#BAE6FD', 'warn': '#FDE047',
            'error': '#FCA5A5', 'success': '#86EFAC',
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
            selection.format.setBackground(QColor("#0284C7"))
            selection.format.setForeground(QColor("#FFFFFF"))
            selection.cursor = found_cursor
            selection.cursor.select(QTextCursor.BlockUnderCursor)
            edit.setExtraSelections([selection])
            QTimer.singleShot(3000, lambda e=edit, p=page: p.refresh_filter_highlights(e))
            break

    # ========================== 基础生命周期区 ==========================
    def append_log(self, ts, msg):
        self.log_buffer.append(msg)
        self._write_live_log_line(msg)
        if hasattr(self, 'db_worker'):
            t = (ts - self.start_time + self.time_offset) if self.start_time > 0 else 0.0
            self.db_worker.queue.put({
                'type': 'log', 'rel_time': t, 'msg': msg,
                'session_id': self.current_session_id,
            })

    def setup_crosshair(self):
        self.v_lines = []
        for p in [self.ui.p_p, self.ui.p_in, self.ui.p_out, self.ui.p_bat]:
            v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color='#38BDF8', width=1.5, style=Qt.DashLine))
            v_line.setVisible(False)
            p.addItem(v_line, ignoreBounds=True)
            self.v_lines.append(v_line)
        self.hud_label = QLabel(self.ui.graph_widget)
        self.hud_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hud_label.setStyleSheet(
            "QLabel { background-color: rgba(15, 23, 42, 250); color: #FFFFFF; "
            "border: 1px solid #38BDF8; border-radius: 6px; padding: 10px; "
            f"{ui_font_css(FS_SUBTITLE, FW_NORMAL, family=FONT_FAMILY_MONO)} }}"
        )
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
                    f"<div style='font-size: {FS_SUBTITLE}pt; line-height: 1.5; color:#FFFFFF;'>"
                    f"<b style='color:#FFFFFF; font-size: {FS_SUBTITLE + 1}pt;'>⏱ {closest_x:.2f} s</b>"
                    f"<hr style='border: 1px solid #64748B; margin: 4px 0;'>"
                )
                if active_p == self.ui.p_p: html += f"<b>PWR:</b> <span style='color:#E879F9'>{p_val:.2f} W</span>"
                elif active_p == self.ui.p_in: html += f"<b>IN :</b> <span style='color:#FFE566'>{vi_val:.2f} V</span> / <span style='color:#4ADE80'>{ii_val:.2f} A</span>"
                elif active_p == self.ui.p_out: html += f"<b>OUT:</b> <span style='color:#FFE566'>{vo_val:.2f} V</span> / <span style='color:#4ADE80'>{io_val:.2f} A</span>"
                elif active_p == self.ui.p_bat: html += f"<b>BAT:</b> <span style='color:#FFE566'>{vb_val:.2f} V</span> / <span style='color:#4ADE80'>{ib_val:.2f} A</span>"
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
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet(menu_bar_stylesheet())
        self._view_menu = menu_bar.addMenu(tr('menu.settings'))
        self._panel_menu = self._view_menu.addMenu(tr('menu.panels'))

        self._act_show_chart = self._panel_menu.addAction(tr('tab.oscilloscope'))
        self._act_show_chart.setCheckable(True)
        self._act_show_chart.setChecked(True)

        self._act_show_log = self._panel_menu.addAction(tr('tab.log_monitor'))
        self._act_show_log.setCheckable(True)
        self._act_show_log.setChecked(True)

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

        self._panel_toggles = (
            (self._act_show_chart, self.ui.chart_panel),
            (self._act_show_log, self.ui.log_panel),
        )
        for action, _panel in self._panel_toggles:
            action.toggled.connect(self._on_panel_visibility_changed)
        self.ui.main_tabs.currentChanged.connect(self._on_main_tab_changed)

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
        if not self._act_show_chart.isChecked():
            return False
        return self.ui.main_tabs.currentWidget() == self.ui.chart_panel

    def _ensure_visible_tab(self):
        tabs = self.ui.main_tabs
        current = tabs.currentWidget()
        if current is not None and self._is_tab_visible(current):
            return
        for panel in (self.ui.log_panel, self.ui.chart_panel):
            if self._is_tab_visible(panel):
                tabs.setCurrentWidget(panel)
                return

    def _on_main_tab_changed(self, _index):
        self.hide_tooltip()
        if self._is_chart_tab_active() and hasattr(self.ui, 'graph_widget'):
            QTimer.singleShot(0, self.ui.graph_widget.updateGeometry)

    def _on_panel_visibility_changed(self, _checked=False):
        if not any(action.isChecked() for action, _ in self._panel_toggles):
            sender = self.sender()
            if sender is not None:
                sender.blockSignals(True)
                sender.setChecked(True)
                sender.blockSignals(False)
            return
        for action, panel in self._panel_toggles:
            self._set_tab_visible(panel, action.isChecked())
        self._ensure_visible_tab()
        QTimer.singleShot(0, self._finalize_panel_layout)

    def _finalize_panel_layout(self):
        if not self._is_chart_tab_active():
            self.hide_tooltip()
        if self._is_chart_tab_active() and hasattr(self.ui, 'graph_widget'):
            self.ui.graph_widget.updateGeometry()

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, '_initial_layout_done', False):
            QTimer.singleShot(0, self._finalize_panel_layout)
            self._initial_layout_done = True

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

    def render_ui(self):
        if self.log_buffer:
            self.ui_lock = True
            self._live_log().append_lines(list(self.log_buffer))
            self.ui_lock = False
            self.log_buffer.clear()
        if self.latest_data:
            d = self.latest_data
            for lcd, val in [(self.ui.lcd_v_in, d['v_in']),(self.ui.lcd_i_in, d['i_in']),(self.ui.lcd_v_out, d['v_out']),(self.ui.lcd_i_out, d['i_out']),(self.ui.lcd_power, d['p']),(self.ui.lcd_v_bat, d['v_bat']),(self.ui.lcd_i_bat, d['i_bat']),(self.ui.lcd_battery, d['b']),(self.ui.lcd_temp, d['t'])]: lcd.display(f"{val:.2f}" if isinstance(val, float) else f"{val}")

            ovp = config_module.CONFIG['alerts'].get('ovp_threshold', 25.0)
            ocp = config_module.CONFIG['alerts'].get('ocp_threshold', 3.0)
            temp_w = config_module.CONFIG['alerts'].get('temp_warning_threshold', 60)
            temp_r = config_module.CONFIG['alerts'].get('temp_recovery_threshold', 55)
            max_v = max(d['v_in'], d['v_out'])
            if max_v >= ovp:
                if 'OVP' not in self._active_alerts:
                    self._active_alerts.add('OVP')
                    self.show_protection_alert(tr('protect.ovp'), max_v, ovp, "V")
            elif max_v < ovp - 1.0: self._active_alerts.discard('OVP')

            max_i = max(d['i_in'], d['i_out'])
            if max_i >= ocp:
                if 'OCP' not in self._active_alerts:
                    self._active_alerts.add('OCP')
                    self.show_protection_alert(tr('protect.ocp'), max_i, ocp, "A")
            elif max_i < ocp - 0.2: self._active_alerts.discard('OCP')

            if d['t'] >= temp_w:
                self.ui.lcd_temp.setStyleSheet(
                    'background-color: #450A0A; color: #FECACA; border: 2px solid #EF4444; border-radius: 4px;'
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
                self.ui.lcd_temp.setStyleSheet(
                    f'background-color: #151D2E; color: {LCD_TEMP}; border: 1px solid #5B6B7C; border-radius: 4px;'
                )
                if d['t'] < temp_r: self._temp_warned = False; self._active_alerts.discard('OTP')

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

        if self.worker and self.worker.isRunning():
            if self.auto_scroll_chart:
                if not self.x_data: return
                self.ui.line_power.setData(self.x_data, self.y_p)
                self.ui.line_v_in.setData(self.x_data, self.y_vi)
                self.ui.line_i_in.setData(self.x_data, self.y_ii)
                self.ui.line_v_out.setData(self.x_data, self.y_vo)
                self.ui.line_i_out.setData(self.x_data, self.y_io)
                self.ui.line_v_bat.setData(self.x_data, self.y_vb)
                self.ui.line_i_bat.setData(self.x_data, self.y_ib)
                self.view_data = {'x': self.x_data, 'p': self.y_p, 'vi': self.y_vi, 'ii': self.y_ii, 'vo': self.y_vo, 'io': self.y_io, 'vb': self.y_vb, 'ib': self.y_ib, 't': self.y_t, 'b': self.y_b}
                cur_t = self.x_data[-1]
                win = config_module.CONFIG['ui'].get('default_window_size_sec', 60.0)
                xlim = [cur_t-win, cur_t+win*0.05] if cur_t > win else [0, max(cur_t+1, win)]
                self.ui.p_p.setXRange(xlim[0], xlim[1], padding=0)
                self.last_forced_xlim = xlim
            else: self.request_chart_fetch()

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
        [a.clear() for a in [self.x_data, self.y_vi, self.y_ii, self.y_vo, self.y_io, self.y_vb, self.y_ib, self.y_eff, self.y_p, self.y_t, self.y_b]]; self.view_data = {'x':[], 'p':[], 'vi':[], 'ii':[], 'vo':[], 'io':[], 'vb':[], 'ib':[], 't':[], 'b':[]}
        serial_cfg = config_module.CONFIG.get('serial', {})
        self.worker = SerialWorker(
            port, baud, demo_mode=demo_mode,
            auto_reconnect=serial_cfg.get('auto_reconnect', True),
            reconnect_interval=serial_cfg.get('reconnect_interval_sec', 3.0),
            max_reconnect_attempts=serial_cfg.get('max_reconnect_attempts', 5),
        )
        self.worker.data_ready.connect(self.process_data)
        self.worker.log_ready.connect(self.append_log)
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
        if hasattr(self, '_port_watcher'):
            self._port_watcher.stop()
        if hasattr(self, 'db_worker'):
            self.db_worker.stop()
        if hasattr(self, 'fetch_worker'):
            self.fetch_worker.stop()
        event.accept()
