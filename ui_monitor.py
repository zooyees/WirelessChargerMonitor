# ui_monitor.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLCDNumber,
                             QPushButton, QFrame, QComboBox, QGroupBox, QSplitter, QSizePolicy, QPlainTextEdit,
                             QScrollArea, QApplication)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
import pyqtgraph as pg

# ================== 全局图形抗锯齿与主题配置 ==================
pg.setConfigOptions(antialias=True)  # 强制开启全局抗锯齿
pg.setConfigOption('background', '#1E293B')  # 外层背景，与面板颜色融为一体
pg.setConfigOption('foreground', '#CBD5E1')  # 全局默认前景色


class Ui_MonitorWindow(object):
    _PANEL_BG = '#1E293B'
    _CANVAS_BG = '#0F172A'
    _SURFACE_BG = '#151D2E'
    _TEXT_PRIMARY = '#F8FAFC'
    _TEXT_SECONDARY = '#E2E8F0'
    _TEXT_MUTED = '#B8C5D3'
    _BORDER = '#5B6B7C'
    _ACCENT = '#38BDF8'
    _LOG_TEXT = '#DCE8F5'

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
        MainWindow.setWindowTitle("手机无线充电监控系统")
        scale = self._ui_scale()
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            MainWindow.resize(int(geo.width() * 0.88), int(geo.height() * 0.88))
        else:
            MainWindow.resize(1600, 950)

        MainWindow.setStyleSheet(f"""
            QMainWindow, QWidget#centralwidget {{
                background-color: {self._CANVAS_BG};
                color: {self._TEXT_PRIMARY};
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }}
            QLabel#main_title {{
                font-size: {max(11, round(13 * scale))}pt;
                font-weight: bold;
                color: {self._TEXT_PRIMARY};
                padding: 4px 2px;
                background-color: #111D2B;
                border-radius: 4px;
            }}
            QGroupBox {{
                font-weight: bold;
                color: {self._TEXT_PRIMARY};
                background-color: {self._PANEL_BG};
                border: 1px solid {self._BORDER};
                border-radius: 6px;
                margin-top: 8px;
                padding: 10px 5px 5px 5px;
                font-size: {max(9, round(10 * scale))}pt;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: {self._TEXT_PRIMARY};
            }}
            QFrame#side_panel, QFrame#log_panel, QFrame#chart_panel {{
                background-color: {self._PANEL_BG};
                border-radius: 12px;
            }}
            QWidget#side_content {{
                background-color: {self._PANEL_BG};
                color: {self._TEXT_PRIMARY};
            }}
            QScrollArea#side_scroll {{
                background-color: {self._PANEL_BG};
                border: none;
            }}
            QScrollBar:vertical {{
                background: {self._PANEL_BG};
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: #64748B;
                min-height: 24px;
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QLabel#data_label {{
                color: {self._TEXT_SECONDARY};
                font-size: {max(8, round(9 * scale))}pt;
                font-weight: 600;
            }}
            QLCDNumber {{
                background-color: {self._SURFACE_BG};
                color: #FDE047;
                border: 1px solid {self._BORDER};
                border-radius: 4px;
            }}
            QComboBox {{
                background-color: #2D3A4F;
                border: 1px solid {self._BORDER};
                border-radius: 4px;
                color: {self._TEXT_PRIMARY};
                padding: 2px 6px;
                min-height: {max(22, round(25 * scale))}px;
                font-size: {max(8, round(9 * scale))}pt;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2D3A4F;
                color: {self._TEXT_PRIMARY};
                selection-background-color: #0EA5E9;
                selection-color: #FFFFFF;
            }}
            QPushButton {{
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                font-weight: bold;
                border-radius: 6px;
                padding: {max(6, round(8 * scale))}px;
                color: {self._TEXT_PRIMARY};
                border: none;
                font-size: {max(9, round(10 * scale))}pt;
                background-color: #3D4F66;
            }}
            QPushButton#btn_start {{
                background-color: #0EA5E9;
                color: #FFFFFF;
            }}
            QPushButton#btn_stop {{
                background-color: #52657A;
                color: #FFFFFF;
            }}
            QPushButton#btn_stop:disabled {{
                background-color: #334155;
                color: {self._TEXT_MUTED};
            }}
            QPushButton#btn_export {{
                background-color: {self._SURFACE_BG};
                border: 1px solid #0EA5E9;
                color: #7DD3FC;
            }}
            QPushButton#btn_report {{
                background-color: {self._SURFACE_BG};
                border: 1px solid #38BDF8;
                color: #BAE6FD;
            }}
            QPushButton#btn_log_tool {{
                background-color: #3D4F66;
                border: 1px solid {self._BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: {max(7, round(8 * scale))}pt;
                color: {self._TEXT_SECONDARY};
                min-height: {max(18, round(20 * scale))}px;
            }}
            QPushButton#btn_log_tool:hover {{
                background-color: #52657A;
                color: #FFFFFF;
            }}
            QPushButton:hover {{
                background-color: #52657A;
            }}
            QPushButton#btn_start:hover {{
                background-color: #0284C7;
            }}
            QPlainTextEdit {{
                background-color: {self._SURFACE_BG};
                color: {self._LOG_TEXT};
                border: 1px solid {self._BORDER};
                border-radius: 6px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: {max(8, round(9 * scale))}pt;
                padding: 5px;
            }}
            QToolTip {{
                color: #F8FAFC;
                background-color: #1E293B;
                border: 1px solid #0EA5E9;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                font-size: {max(9, round(10 * scale))}pt;
            }}
        """)

        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self._apply_dark_bg(self.centralwidget, self._CANVAS_BG)
        MainWindow.setCentralWidget(self.centralwidget)
        self.root_layout = QVBoxLayout(self.centralwidget)
        self.root_layout.setContentsMargins(10, 5, 10, 10)
        self.root_layout.setSpacing(5)

        self.lbl_main_title = QLabel("手机无线充电监控系统")
        self.lbl_main_title.setObjectName("main_title")
        self.lbl_main_title.setAlignment(Qt.AlignCenter)
        self.lbl_main_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.root_layout.addWidget(self.lbl_main_title)

        self.splitter = QSplitter(Qt.Horizontal)

        # --- 左侧面板（可滚动，避免高 DPI 下控件被裁切）---
        self.side_panel = QFrame()
        self.side_panel.setObjectName("side_panel")
        self.side_panel.setMinimumWidth(int(220 * scale))
        self._apply_dark_bg(self.side_panel, self._PANEL_BG)
        self.side_scroll = QScrollArea()
        self.side_scroll.setObjectName("side_scroll")
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setFrameShape(QFrame.NoFrame)
        self.side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._apply_dark_bg(self.side_scroll, self._PANEL_BG)
        self.side_scroll.viewport().setAutoFillBackground(True)
        vp_pal = self.side_scroll.viewport().palette()
        vp_pal.setColor(QPalette.Background, QColor(self._PANEL_BG))
        self.side_scroll.viewport().setPalette(vp_pal)

        side_content = QWidget()
        side_content.setObjectName("side_content")
        self._apply_dark_bg(side_content, self._PANEL_BG)
        side_layout = QVBoxLayout(side_content)
        side_layout.setContentsMargins(10, 5, 10, 10)
        side_layout.setSpacing(max(2, round(3 * scale)))

        side_panel_outer = QVBoxLayout(self.side_panel)
        side_panel_outer.setContentsMargins(0, 0, 0, 0)
        side_panel_outer.addWidget(self.side_scroll)
        self.side_scroll.setWidget(side_content)

        self.group_config = QGroupBox("连接配置")
        config_vbox = QVBoxLayout(self.group_config)
        config_vbox.setContentsMargins(5, 15, 5, 5)
        config_vbox.setSpacing(2)

        port_hbox = QHBoxLayout()
        self.cb_port = QComboBox()
        self.btn_refresh_ports = QPushButton("🔄")
        self.btn_refresh_ports.setObjectName("btn_log_tool")
        self.btn_refresh_ports.setFixedWidth(36)
        self.btn_refresh_ports.setToolTip("刷新串口列表")
        port_hbox.addWidget(self.cb_port)
        port_hbox.addWidget(self.btn_refresh_ports)
        config_vbox.addLayout(port_hbox)
        self.cb_baudrate = QComboBox()
        # 🟢 修复：补回丢失的波特率配置与布局添加代码
        self.cb_baudrate.addItems(["115200", "921600", "2000000"])
        config_vbox.addWidget(self.cb_baudrate)

        side_layout.addWidget(self.group_config)

        def create_lcd(name, color):
            box = QVBoxLayout()
            box.setSpacing(0)
            lbl = QLabel(name)
            lbl.setObjectName("data_label")
            lcd_h = max(26, round(30 * scale))
            lcd = QLCDNumber()
            lcd.setMinimumHeight(lcd_h)
            lcd.setMaximumHeight(lcd_h + 4)
            lcd.setStyleSheet(
                f"background-color: {self._SURFACE_BG}; color: {color}; "
                f"border: 1px solid {self._BORDER}; border-radius: 4px;"
            )
            lcd.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            box.addWidget(lbl)
            box.addWidget(lcd)
            return box, lcd

        l1, self.lcd_v_in    = create_lcd("输入电压 (V_in)", "#FDE047")
        l2, self.lcd_i_in    = create_lcd("输入电流 (I_in)", "#4ADE80")
        l3, self.lcd_v_out   = create_lcd("输出电压 (V_out)", "#FDE047")
        l4, self.lcd_i_out   = create_lcd("输出电流 (I_out)", "#4ADE80")
        l5, self.lcd_power   = create_lcd("输出功率 (Power W)", "#C084FC")
        l7, self.lcd_v_bat   = create_lcd("电池电压 (V_bat)", "#FDE047")
        l8, self.lcd_i_bat   = create_lcd("电池电流 (I_bat)", "#4ADE80")
        l9, self.lcd_temp    = create_lcd("线圈温度 (°C)", "#FB923C")
        l10, self.lcd_battery = create_lcd("当前电量 (%)", "#34D399")

        for l in [l1, l2, l3, l4, l5, l7, l8, l9, l10]: side_layout.addLayout(l)

        self.lbl_charge_state = QLabel("⚡ 充电状态: 等待接入...")
        self.lbl_charge_state.setAlignment(Qt.AlignCenter)
        self.lbl_charge_state.setWordWrap(True)
        self.lbl_charge_state.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.lbl_charge_state.setStyleSheet(f"""
            background-color: {self._SURFACE_BG};
            color: {self._TEXT_SECONDARY};
            border: 1px dashed {self._BORDER};
            border-radius: 6px;
            padding: {max(6, round(8 * scale))}px;
            font-size: {max(9, round(11 * scale))}pt;
            font-weight: bold;
            margin-bottom: 5px;
        """)
        side_layout.addWidget(self.lbl_charge_state)

        btn_box = QVBoxLayout()
        btn_box.setSpacing(max(4, round(5 * scale)))
        self.btn_start = QPushButton("▶ 开始")
        self.btn_start.setObjectName("btn_start")
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.btn_export = QPushButton("💾 导出 CSV")
        self.btn_export.setObjectName("btn_export")
        self.btn_report = QPushButton("📄 导出 PDF 报告")
        self.btn_report.setObjectName("btn_report")
        for btn in (self.btn_start, self.btn_stop, self.btn_export, self.btn_report):
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btn_box.addWidget(self.btn_start)
        btn_box.addWidget(self.btn_stop)
        btn_box.addWidget(self.btn_export)
        btn_box.addWidget(self.btn_report)
        side_layout.addLayout(btn_box)
        side_layout.addStretch(1)

        # ==================== 中间面板：PyQtGraph 深度美化版 ====================
        self.chart_panel = QFrame()
        self.chart_panel.setObjectName("chart_panel")
        self._apply_dark_bg(self.chart_panel, self._PANEL_BG)
        chart_layout = QVBoxLayout(self.chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        self.graph_widget = pg.GraphicsLayoutWidget()
        chart_layout.addWidget(self.graph_widget)

        self.graph_widget.ci.layout.setSpacing(12)
        self.graph_widget.ci.layout.setContentsMargins(10, 10, 15, 10)

        self.vbs = []

        chart_fs = max(8, min(12, round(8 * scale)))
        font_css = {'font-size': f'{chart_fs}pt', 'font-family': 'Microsoft YaHei', 'font-weight': 'bold'}
        axis_pen = pg.mkPen(color='#475569', width=1.2)
        text_pen = pg.mkPen(color='#CBD5E1')

        def add_plot(row, title, label1, color1, label2=None, color2=None, link_plot=None):
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

            if link_plot: p.setXLink(link_plot)
            else: self.p_main = p

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

        self.p_p, self.line_power, _ = add_plot(0, "POWER", "POWER (W)", "#A855F7")
        self.p_in, self.line_v_in, self.line_i_in = add_plot(1, "INPUT", "INPUT (V)", "#FACC15", "INPUT (A)", "#22C55E", link_plot=self.p_p)
        self.p_out, self.line_v_out, self.line_i_out = add_plot(2, "OUTPUT", "OUTPUT (V)", "#FACC15", "OUTPUT (A)", "#22C55E", link_plot=self.p_p)
        self.p_bat, self.line_v_bat, self.line_i_bat = add_plot(3, "BATTERY", "BATTERY (V)", "#FACC15", "BATTERY (A)", "#22C55E", link_plot=self.p_p)

        self.p_p.getAxis('bottom').setStyle(showValues=False)
        self.p_in.getAxis('bottom').setStyle(showValues=False)
        self.p_out.getAxis('bottom').setStyle(showValues=False)

        def updateViews():
            for p, vb in self.vbs:
                vb.setGeometry(p.vb.sceneBoundingRect())
                vb.linkedViewChanged(p.vb, vb.XAxis)
        updateViews()
        for p, _ in self.vbs:
            p.vb.sigResized.connect(updateViews)

        # --- 右侧面板 ---
        self.log_panel = QFrame()
        self.log_panel.setObjectName("log_panel")
        self.log_panel.setMinimumWidth(int(320 * scale))
        self._apply_dark_bg(self.log_panel, self._PANEL_BG)
        log_layout = QVBoxLayout(self.log_panel)
        log_layout.setContentsMargins(10, 10, 10, 10)
        log_layout.setSpacing(5)

        log_header_lay = QHBoxLayout()
        self.lbl_log_title = QLabel("📡 报文实时监控")
        self.lbl_log_title.setStyleSheet(f"color: {self._TEXT_PRIMARY}; font-weight: bold; font-size: {max(9, round(10 * scale))}pt;")

        self.btn_rollback = QPushButton("🔄 历史查阅")
        self.btn_rollback.setObjectName("btn_log_tool")
        self.btn_export_log = QPushButton("💾 导出全量日志")
        self.btn_export_log.setObjectName("btn_log_tool")

        log_header_lay.addWidget(self.lbl_log_title)
        log_header_lay.addStretch(1)
        log_header_lay.addWidget(self.btn_rollback)
        log_header_lay.addWidget(self.btn_export_log)
        log_layout.addLayout(log_header_lay)

        self.text_log = QPlainTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.document().setMaximumBlockCount(1000)
        log_layout.addWidget(self.text_log)

        self.splitter.addWidget(self.side_panel)
        self.splitter.addWidget(self.chart_panel)
        self.splitter.addWidget(self.log_panel)

        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 11)
        self.splitter.setStretchFactor(2, 6)
        self.root_layout.addWidget(self.splitter)
