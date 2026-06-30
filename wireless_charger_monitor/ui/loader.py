"""Qt Designer 界面加载与 PyQtGraph 图表注入。"""
import os

import pyqtgraph as pg
from PyQt5 import uic
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QApplication, QFrame, QSizePolicy, QVBoxLayout, QWidget

from ..apps.tektronix_scope import TektronixScopePanel
from ..apps.waveform_scope import attach_waveform_charts
from .tab_utils import refresh_tab_widget

from . import theme as ui_theme

from .theme import (
    full_stylesheet,
    LCD_STYLES,
    apply_data_label_style,
    apply_editable_combo_line_edit,
    apply_lcd_style,
    apply_line_edit_palette,
    apply_log_control_panel_metrics,
    apply_log_control_panel_theme,
    apply_log_tool_label_style,
)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', ui_theme.PANEL_BG)
pg.setConfigOption('foreground', ui_theme.CHART_TEXT)

_UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
UI_FILE = os.path.join(_UI_DIR, 'monitor_window.ui')

_WIDGET_NAMES = (
    'centralwidget', 'root_layout', 'main_tabs',
    'chart_panel', 'chart_lcd_scroll', 'chart_lcd_content',
    'cb_port', 'cb_baudrate',
    'lbl_lcd_v_in', 'lbl_lcd_i_in', 'lbl_lcd_v_out', 'lbl_lcd_i_out', 'lbl_lcd_power',
    'lbl_lcd_v_bat', 'lbl_lcd_i_bat', 'lbl_lcd_temp', 'lbl_lcd_battery',
    'lcd_v_in', 'lcd_i_in', 'lcd_v_out', 'lcd_i_out', 'lcd_power',
    'lcd_v_bat', 'lcd_i_bat', 'lcd_temp', 'lcd_battery',
    'btn_start',
    'chart_container', 'log_panel', 'log_control_panel',
    'btn_new_live_log', 'lbl_live_log_name', 'edit_live_log_name', 'lbl_live_log_dir',
    'edit_live_log_dir', 'btn_browse_log_dir',
    'btn_open_log', 'log_file_tabs',
)


class Ui_MonitorWindow:
    def _ui_scale(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return 1.0
        return max(1.0, screen.logicalDotsPerInchX() / 96.0)

    @staticmethod
    def _apply_panel_bg(widget, color):
        widget.setAutoFillBackground(True)
        pal = widget.palette()
        pal.setColor(QPalette.Window, QColor(color))
        pal.setColor(QPalette.WindowText, QColor(ui_theme.TEXT_PRIMARY))
        widget.setPalette(pal)

    def reapply_theme(self, MainWindow):
        MainWindow.setStyleSheet(full_stylesheet())
        self._apply_panel_bg(self.centralwidget, ui_theme.CANVAS_BG)
        self._apply_panel_bg(self.main_tabs, ui_theme.CANVAS_BG)
        self._apply_panel_bg(self.chart_lcd_scroll, ui_theme.PANEL_BG)
        self._apply_panel_bg(self.chart_lcd_content, ui_theme.PANEL_BG)
        chart_lcd_pal = self.chart_lcd_content.palette()
        chart_lcd_pal.setColor(QPalette.WindowText, QColor(ui_theme.TEXT_PRIMARY))
        self.chart_lcd_content.setPalette(chart_lcd_pal)
        self._apply_panel_bg(self.chart_panel, ui_theme.PANEL_BG)
        self._apply_panel_bg(self.log_panel, ui_theme.PANEL_BG)
        if hasattr(self, 'tektronix_panel'):
            self._apply_panel_bg(self.tektronix_panel, ui_theme.PANEL_BG)
        self._apply_panel_bg(self.log_control_panel, ui_theme.PANEL_BG)
        self._apply_panel_bg(self.log_file_tabs, ui_theme.PANEL_BG)
        self._setup_scroll_palettes()
        self._apply_widget_styles()
        self._reapply_chart_colors()
        pg.setConfigOption('background', ui_theme.PANEL_BG)
        pg.setConfigOption('foreground', ui_theme.CHART_TEXT)
        if hasattr(self, 'graph_widget'):
            self.graph_widget.setBackground(ui_theme.CHART_BG)
        if hasattr(self, 'tektronix_scope'):
            self.tektronix_scope.reapply_theme()
        apply_log_control_panel_theme(self)

    def _reapply_chart_colors(self):
        if not hasattr(self, 'p_p'):
            return
        axis_pen = pg.mkPen(color=ui_theme.CHART_AXIS, width=1.2)
        text_pen = pg.mkPen(color=ui_theme.CHART_TEXT)
        plots = [self.p_p, self.p_in, self.p_out, self.p_bat]
        for plot in plots:
            plot.getViewBox().setBackgroundColor(ui_theme.CHART_BG)
            for axis_name in ('left', 'bottom', 'right'):
                axis = plot.getAxis(axis_name)
                if axis is not None:
                    axis.setPen(axis_pen)
                    axis.setTextPen(text_pen)
        for line, color, width in getattr(self, 'line_specs', ()):
            if line is not None:
                line.setPen(pg.mkPen(color=color, width=width))
        self._apply_panel_bg(self.chart_container, ui_theme.CHART_BG)
        placeholder = getattr(self, 'chart_placeholder', None)
        if placeholder is None:
            placeholder = self.chart_container.findChild(QWidget, 'chart_placeholder')
        if placeholder is not None:
            pal = placeholder.palette()
            pal.setColor(QPalette.WindowText, QColor(ui_theme.TEXT_MUTED))
            placeholder.setPalette(pal)

    def setupUi(self, MainWindow):
        if not os.path.isfile(UI_FILE):
            raise FileNotFoundError(f'未找到 UI 文件: {UI_FILE}')

        uic.loadUi(UI_FILE, MainWindow)
        MainWindow.setStyleSheet(full_stylesheet())
        self._bind_widgets(MainWindow)
        self._apply_scaled_layout(MainWindow)
        self._apply_widget_styles()
        self._setup_scroll_palettes()
        attach_waveform_charts(self)
        self._reapply_chart_colors()
        self._setup_tektronix_panel()
        self._configure_tabs()
        apply_log_control_panel_theme(self)

    def _bind_widgets(self, MainWindow):
        for name in _WIDGET_NAMES:
            widget = getattr(MainWindow, name, None)
            if widget is None:
                widget = MainWindow.findChild(QWidget, name)
            if widget is None:
                raise RuntimeError(f'UI 缺少控件: {name}')
            setattr(self, name, widget)

    def _apply_scaled_layout(self, MainWindow):
        scale = self._ui_scale()
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            MainWindow.resize(int(geo.width() * 0.88), int(geo.height() * 0.88))

        self.log_control_panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        apply_log_control_panel_metrics(self, scale)
        self.edit_live_log_dir.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.chart_lcd_scroll.setMinimumWidth(int(220 * scale))
        self._apply_panel_bg(self.centralwidget, ui_theme.CANVAS_BG)
        self._apply_panel_bg(self.main_tabs, ui_theme.CANVAS_BG)
        self._apply_panel_bg(self.chart_lcd_scroll, ui_theme.PANEL_BG)
        self._apply_panel_bg(self.chart_lcd_content, ui_theme.PANEL_BG)
        chart_lcd_pal = self.chart_lcd_content.palette()
        chart_lcd_pal.setColor(QPalette.WindowText, QColor(ui_theme.TEXT_PRIMARY))
        self.chart_lcd_content.setPalette(chart_lcd_pal)
        self._apply_panel_bg(self.chart_panel, ui_theme.PANEL_BG)
        self._apply_panel_bg(self.log_panel, ui_theme.PANEL_BG)
        self._apply_panel_bg(self.log_control_panel, ui_theme.PANEL_BG)
        panel_layout = self.log_panel.layout()
        if panel_layout is not None:
            panel_layout.setStretch(0, 0)
            panel_layout.setStretch(1, 1)
            content_item = panel_layout.itemAt(1)
            if content_item is not None:
                content_layout = content_item.layout()
                if content_layout is not None:
                    content_layout.setStretch(0, 1)
                    m = int(4 * scale)
                    content_layout.setContentsMargins(int(8 * scale), m, int(8 * scale), int(6 * scale))
                    content_layout.setSpacing(int(3 * scale))
        self.log_file_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._configure_log_file_tabs()

        for btn in (self.btn_start, self.btn_open_log, self.btn_browse_log_dir, self.btn_new_live_log):
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for lbl in (self.lbl_live_log_name, self.lbl_live_log_dir):
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.cb_port.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cb_baudrate.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.edit_live_log_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.main_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _configure_log_file_tabs(self):
        tabs = self.log_file_tabs
        tabs.setDocumentMode(False)
        tabs.setTabPosition(tabs.North)
        tabs.setTabsClosable(True)
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._apply_panel_bg(tabs, ui_theme.PANEL_BG)
        refresh_tab_widget(tabs, preset='file')

    def _apply_widget_styles(self):
        scale = self._ui_scale()
        for lbl in self.find_data_labels():
            apply_data_label_style(lbl)

        for lbl in (self.lbl_live_log_name, self.lbl_live_log_dir):
            apply_log_tool_label_style(lbl)

        for name in ('edit_live_log_name', 'edit_live_log_dir'):
            edit = getattr(self, name, None)
            if edit is not None:
                apply_line_edit_palette(edit)
        apply_editable_combo_line_edit(self.cb_baudrate)

        for lcd_name, color in LCD_STYLES.items():
            lcd = getattr(self, lcd_name, None)
            if lcd is not None:
                apply_lcd_style(lcd, color)

    def find_data_labels(self):
        labels = []
        for lcd_name in (
            'lcd_v_in', 'lcd_i_in', 'lcd_v_out', 'lcd_i_out', 'lcd_power',
            'lcd_v_bat', 'lcd_i_bat', 'lcd_temp', 'lcd_battery',
        ):
            lbl = getattr(self, f'lbl_{lcd_name}', None)
            if lbl is not None:
                labels.append(lbl)
        return labels

    def _setup_scroll_palettes(self):
        for scroll in (self.chart_lcd_scroll,):
            scroll.viewport().setAutoFillBackground(True)
            vp_pal = scroll.viewport().palette()
            vp_pal.setColor(QPalette.Background, QColor(ui_theme.PANEL_BG))
            scroll.viewport().setPalette(vp_pal)

    def _configure_tabs(self):
        tabs = self.main_tabs
        tabs.setTabPosition(tabs.North)
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_idx = tabs.indexOf(self.log_panel)
        if log_idx > 0:
            tabs.tabBar().moveTab(log_idx, 0)
        tabs.setCurrentWidget(self.log_panel)
        refresh_tab_widget(tabs, preset='main')

    def _setup_tektronix_panel(self):
        self.tektronix_panel = QFrame()
        self.tektronix_panel.setObjectName('tektronix_panel')
        self.tektronix_panel.setFrameShape(QFrame.NoFrame)
        self.tektronix_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._apply_panel_bg(self.tektronix_panel, ui_theme.PANEL_BG)
        layout = QVBoxLayout(self.tektronix_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tektronix_scope = TektronixScopePanel(self.tektronix_panel)
        self.tektronix_scope.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.tektronix_scope)
        self.main_tabs.addTab(self.tektronix_panel, 'Tektronix Scope')
