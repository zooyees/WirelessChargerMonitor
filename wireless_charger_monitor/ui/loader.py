"""Qt Designer 界面加载与 PyQtGraph 图表注入。"""
import os

import pyqtgraph as pg
from PyQt5 import uic
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QApplication, QSizePolicy, QVBoxLayout, QWidget

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', '#1E293B')
pg.setConfigOption('foreground', '#CBD5E1')

_UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
UI_FILE = os.path.join(_UI_DIR, 'monitor_window.ui')

_WIDGET_NAMES = (
    'centralwidget', 'root_layout', 'lbl_main_title', 'splitter',
    'side_panel', 'side_scroll', 'side_content', 'group_config',
    'cb_port', 'btn_refresh_ports', 'cb_baudrate',
    'lcd_v_in', 'lcd_i_in', 'lcd_v_out', 'lcd_i_out', 'lcd_power',
    'lcd_v_bat', 'lcd_i_bat', 'lcd_temp', 'lcd_battery',
    'lbl_charge_state', 'btn_start', 'btn_stop', 'btn_export', 'btn_report',
    'chart_panel', 'chart_container', 'log_panel',
    'lbl_log_title', 'btn_rollback', 'btn_export_log', 'text_log',
)


class Ui_MonitorWindow:
    _PANEL_BG = '#1E293B'
    _CANVAS_BG = '#0F172A'
    _SURFACE_BG = '#151D2E'
    _TEXT_PRIMARY = '#F8FAFC'
    _TEXT_SECONDARY = '#E2E8F0'
    _BORDER = '#5B6B7C'

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
        self._bind_widgets(MainWindow)
        self._apply_scaled_layout(MainWindow)
        self._apply_widget_styles()
        self._setup_side_scroll_palette()
        self._setup_charts()
        self._configure_splitter()

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

        self.side_panel.setMinimumWidth(int(220 * scale))
        self.log_panel.setMinimumWidth(int(320 * scale))
        self._apply_dark_bg(self.centralwidget, self._CANVAS_BG)
        self._apply_dark_bg(self.side_panel, self._PANEL_BG)
        self._apply_dark_bg(self.side_scroll, self._PANEL_BG)
        self._apply_dark_bg(self.side_content, self._PANEL_BG)
        self._apply_dark_bg(self.chart_panel, self._PANEL_BG)
        self._apply_dark_bg(self.log_panel, self._PANEL_BG)
        self.text_log.document().setMaximumBlockCount(1000)

        for btn in (self.btn_start, self.btn_stop, self.btn_export, self.btn_report):
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.lbl_main_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lbl_charge_state.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _apply_widget_styles(self):
        scale = self._ui_scale()
        self.lbl_main_title.setObjectName('main_title')
        self.btn_refresh_ports.setObjectName('btn_log_tool')
        self.btn_rollback.setObjectName('btn_log_tool')
        self.btn_export_log.setObjectName('btn_log_tool')
        for lbl in self.find_data_labels():
            lbl.setObjectName('data_label')

        charge_pad = max(6, round(8 * scale))
        self.lbl_charge_state.setStyleSheet(
            f'background-color: {self._SURFACE_BG}; color: {self._TEXT_SECONDARY}; '
            f'border: 1px dashed {self._BORDER}; border-radius: 6px; padding: {charge_pad}px; '
            f'font-size: {max(9, round(11 * scale))}pt; font-weight: bold; margin-bottom: 5px;'
        )
        log_fs = max(9, round(10 * scale))
        self.lbl_log_title.setStyleSheet(
            f'color: {self._TEXT_PRIMARY}; font-weight: bold; font-size: {log_fs}pt;'
        )

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

    def _setup_side_scroll_palette(self):
        self.side_scroll.viewport().setAutoFillBackground(True)
        vp_pal = self.side_scroll.viewport().palette()
        vp_pal.setColor(QPalette.Background, QColor(self._PANEL_BG))
        self.side_scroll.viewport().setPalette(vp_pal)

    def _configure_splitter(self):
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 11)
        self.splitter.setStretchFactor(2, 6)

    def _setup_charts(self):
        self.graph_widget = pg.GraphicsLayoutWidget()
        layout = self.chart_container.layout()
        if layout is None:
            layout = QVBoxLayout(self.chart_container)
            layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.graph_widget)

        scale = self._ui_scale()
        self.graph_widget.ci.layout.setSpacing(12)
        self.graph_widget.ci.layout.setContentsMargins(10, 10, 15, 10)

        self.vbs = []
        chart_fs = max(8, min(12, round(8 * scale)))
        font_css = {'font-size': f'{chart_fs}pt', 'font-family': 'Microsoft YaHei', 'font-weight': 'bold'}
        axis_pen = pg.mkPen(color='#475569', width=1.2)
        text_pen = pg.mkPen(color='#CBD5E1')

        def add_plot(row, label1, color1, label2=None, color2=None, link_plot=None):
            p = self.graph_widget.addPlot(row=row, col=0)
            p.getViewBox().setBackgroundColor('#0F172A')
            p.setDefaultPadding(0.08)
            p.setMinimumHeight(int(120 * scale))

            ax_left = p.getAxis('left')
            ax_left.setLabel(label1, color=color1, **font_css)
            ax_left.setPen(axis_pen)
            ax_left.setTextPen(text_pen)
            ax_left.setGrid(70)

            ax_bottom = p.getAxis('bottom')
            ax_bottom.setPen(axis_pen)
            ax_bottom.setTextPen(text_pen)
            ax_bottom.setGrid(70)

            if link_plot:
                p.setXLink(link_plot)
            else:
                self.p_main = p

            line1 = p.plot(pen=pg.mkPen(color=color1, width=2.0))
            line2 = None
            if label2 and color2:
                vb2 = pg.ViewBox()
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
                line2 = pg.PlotDataItem(pen=pg.mkPen(color=color2, width=1.5))
                vb2.addItem(line2)
            return p, line1, line2

        self.p_p, self.line_power, _ = add_plot(0, 'POWER (W)', '#A855F7')
        self.p_in, self.line_v_in, self.line_i_in = add_plot(
            1, 'INPUT (V)', '#FACC15', 'INPUT (A)', '#22C55E', link_plot=self.p_p,
        )
        self.p_out, self.line_v_out, self.line_i_out = add_plot(
            2, 'OUTPUT (V)', '#FACC15', 'OUTPUT (A)', '#22C55E', link_plot=self.p_p,
        )
        self.p_bat, self.line_v_bat, self.line_i_bat = add_plot(
            3, 'BATTERY (V)', '#FACC15', 'BATTERY (A)', '#22C55E', link_plot=self.p_p,
        )

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
