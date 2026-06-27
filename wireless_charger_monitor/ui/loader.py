"""Qt Designer 界面加载与 PyQtGraph 图表注入。"""
import os

import pyqtgraph as pg
from PyQt5 import uic
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QApplication, QSizePolicy, QVBoxLayout, QWidget

from .tab_utils import refresh_tab_widget

from .theme import (
    MONITOR_WINDOW_STYLESHEET,
    CANVAS_BG,
    CHART_AXIS,
    CHART_BG,
    CHART_CURRENT,
    CHART_POWER,
    CHART_TEXT,
    CHART_VOLTAGE,
    LCD_STYLES,
    PANEL_BG,
    SURFACE_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BORDER,
    FS_CAPTION,
    FS_SUBTITLE,
    apply_data_label_style,
    apply_lcd_style,
    apply_log_control_panel_metrics,
    apply_log_tool_label_style,
)

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', PANEL_BG)
pg.setConfigOption('foreground', CHART_TEXT)

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
    _PANEL_BG = PANEL_BG
    _CANVAS_BG = CANVAS_BG
    _SURFACE_BG = SURFACE_BG
    _TEXT_PRIMARY = TEXT_PRIMARY
    _TEXT_SECONDARY = TEXT_SECONDARY
    _BORDER = BORDER

    def _ui_scale(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return 1.0
        return max(1.0, screen.logicalDotsPerInchX() / 96.0)

    @staticmethod
    def _apply_dark_bg(widget, color):
        widget.setAutoFillBackground(True)
        pal = widget.palette()
        pal.setColor(QPalette.Window, QColor(color))
        widget.setPalette(pal)

    def setupUi(self, MainWindow):
        if not os.path.isfile(UI_FILE):
            raise FileNotFoundError(f'未找到 UI 文件: {UI_FILE}')

        uic.loadUi(UI_FILE, MainWindow)
        MainWindow.setStyleSheet(MONITOR_WINDOW_STYLESHEET)
        self._bind_widgets(MainWindow)
        self._apply_scaled_layout(MainWindow)
        self._apply_widget_styles()
        self._setup_scroll_palettes()
        self._setup_charts()
        self._configure_tabs()

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

        self.log_control_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        apply_log_control_panel_metrics(self, scale)
        self.edit_live_log_dir.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.chart_lcd_scroll.setMinimumWidth(int(220 * scale))
        self._apply_dark_bg(self.centralwidget, self._CANVAS_BG)
        self._apply_dark_bg(self.main_tabs, self._CANVAS_BG)
        self._apply_dark_bg(self.chart_lcd_scroll, self._PANEL_BG)
        self._apply_dark_bg(self.chart_lcd_content, self._PANEL_BG)
        chart_lcd_pal = self.chart_lcd_content.palette()
        chart_lcd_pal.setColor(QPalette.WindowText, QColor(self._TEXT_PRIMARY))
        self.chart_lcd_content.setPalette(chart_lcd_pal)
        self._apply_dark_bg(self.chart_panel, self._PANEL_BG)
        self._apply_dark_bg(self.log_panel, self._PANEL_BG)
        self._apply_dark_bg(self.log_control_panel, self._PANEL_BG)
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
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        for lbl in (self.lbl_live_log_name, self.lbl_live_log_dir):
            lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.cb_port.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.cb_baudrate.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.edit_live_log_name.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.main_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _configure_log_file_tabs(self):
        tabs = self.log_file_tabs
        tabs.setDocumentMode(False)
        tabs.setTabPosition(tabs.North)
        tabs.setTabsClosable(True)
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._apply_dark_bg(tabs, self._PANEL_BG)
        refresh_tab_widget(tabs, preset='file')

    def _apply_widget_styles(self):
        scale = self._ui_scale()
        for lbl in self.find_data_labels():
            apply_data_label_style(lbl)

        for lbl in (self.lbl_live_log_name, self.lbl_live_log_dir):
            apply_log_tool_label_style(lbl)

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
            vp_pal.setColor(QPalette.Background, QColor(self._PANEL_BG))
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

    def _setup_charts(self):
        layout = self.chart_container.layout()
        if layout is None:
            layout = QVBoxLayout(self.chart_container)
        else:
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
        layout.setContentsMargins(0, 0, 0, 0)

        self.graph_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graph_widget)

        scale = self._ui_scale()
        self.graph_widget.ci.layout.setSpacing(12)
        self.graph_widget.ci.layout.setContentsMargins(10, 10, 15, 10)

        self.vbs = []
        self.dual_plots = []
        chart_fs = max(FS_CAPTION, min(FS_SUBTITLE, round(FS_CAPTION * scale)))
        font_css = {'font-size': f'{chart_fs}pt', 'font-family': 'Microsoft YaHei', 'font-weight': 'bold'}
        axis_pen = pg.mkPen(color=CHART_AXIS, width=1.2)
        text_pen = pg.mkPen(color=CHART_TEXT)

        def add_plot(row, label1, color1, label2=None, color2=None, link_plot=None):
            p = self.graph_widget.addPlot(row=row, col=0)
            p.getViewBox().setBackgroundColor(CHART_BG)
            p.setDefaultPadding(0.08)
            p.setMinimumHeight(int(120 * scale))
            p.enableAutoRange(x=False, y=True)
            p.getViewBox().enableAutoRange(x=False, y=True)

            ax_left = p.getAxis('left')
            ax_left.setLabel(label1, color=color1, **font_css)
            ax_left.setPen(axis_pen)
            ax_left.setTextPen(text_pen)
            ax_left.setGrid(100)

            ax_bottom = p.getAxis('bottom')
            ax_bottom.setPen(axis_pen)
            ax_bottom.setTextPen(text_pen)
            ax_bottom.setGrid(100)

            if link_plot:
                p.setXLink(link_plot)
            else:
                self.p_main = p

            line1 = p.plot(pen=pg.mkPen(color=color1, width=2.2))
            line2 = None
            if label2 and color2:
                vb2 = pg.ViewBox()
                vb2.enableAutoRange(x=False, y=True)
                self.vbs.append((p, vb2))
                p.scene().addItem(vb2)
                p.getAxis('right').linkToView(vb2)
                vb2.setXLink(p)
                vb2.setZValue(10)
                ax_right = p.getAxis('right')
                ax_right.setLabel(label2, color=color2, **font_css)
                ax_right.setPen(axis_pen)
                ax_right.setTextPen(text_pen)
                p.showAxis('right')
                line2 = pg.PlotDataItem(pen=pg.mkPen(color=color2, width=2.0))
                vb2.addItem(line2)
            return p, line1, line2

        self.p_p, self.line_power, _ = add_plot(0, 'POWER (W)', CHART_POWER)
        self.p_in, self.line_v_in, self.line_i_in = add_plot(
            1, 'INPUT (V)', CHART_VOLTAGE, 'INPUT (A)', CHART_CURRENT, link_plot=self.p_p,
        )
        self.p_out, self.line_v_out, self.line_i_out = add_plot(
            2, 'OUTPUT (V)', CHART_VOLTAGE, 'OUTPUT (A)', CHART_CURRENT, link_plot=self.p_p,
        )
        self.p_bat, self.line_v_bat, self.line_i_bat = add_plot(
            3, 'BATTERY (V)', CHART_VOLTAGE, 'BATTERY (A)', CHART_CURRENT, link_plot=self.p_p,
        )

        self.dual_plots = [
            (self.p_in, self.vbs[0][1], 'vi', 'ii'),
            (self.p_out, self.vbs[1][1], 'vo', 'io'),
            (self.p_bat, self.vbs[2][1], 'vb', 'ib'),
        ]

        self.p_p.getAxis('bottom').setStyle(showValues=False)
        self.p_in.getAxis('bottom').setStyle(showValues=False)
        self.p_out.getAxis('bottom').setStyle(showValues=False)

        def update_views():
            for p, vb in self.vbs:
                vb.setGeometry(p.vb.sceneBoundingRect())
                vb.linkedViewChanged(p.vb, vb.XAxis)

        update_views()
        for p, _ in self.vbs:
            p.vb.sigResized.connect(update_views)
