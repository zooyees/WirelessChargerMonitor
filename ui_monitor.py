# ui_monitor.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLCDNumber, 
                             QPushButton, QFrame, QComboBox, QGroupBox, QSplitter, QSizePolicy, QPlainTextEdit)
from PyQt5.QtCore import Qt
import pyqtgraph as pg

# ================== 全局图形抗锯齿与主题配置 ==================
pg.setConfigOptions(antialias=True)  # 强制开启全局抗锯齿
pg.setConfigOption('background', '#1E293B')  # 外层背景，与面板颜色融为一体
pg.setConfigOption('foreground', '#64748B')  # 全局默认前景色

class Ui_MonitorWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setWindowTitle("手机无线充电监控系统")
        MainWindow.resize(1600, 950)
        
        MainWindow.setStyleSheet("""
            QMainWindow { background-color: #0F172A; }
            QLabel#main_title { font-size: 13pt; font-weight: bold; color: #CBD5E1; padding: 4px 2px; background-color: #111D2B; border-radius: 4px; }
            QGroupBox { font-weight: bold; color: #94A3B8; border: 1px solid #334155; border-radius: 6px; margin-top: 5px; padding: 10px 5px 5px 5px; font-size: 10pt; }
            QFrame#side_panel, QFrame#log_panel { background-color: #1E293B; border-radius: 12px; }
            QLabel#data_label { color: #CBD5E1; font-size: 9pt; font-weight: bold; }
            QLCDNumber { background-color: #0D1117; border: 1px solid #334155; border-radius: 4px; }
            QComboBox { background-color: #334155; border: 1px solid #475569; border-radius: 4px; color: white; padding: 2px; min-height: 25px; font-size: 9pt; }
            QPushButton { font-family: 'Microsoft YaHei'; font-weight: bold; border-radius: 6px; padding: 8px; color: white; border: none; font-size: 10pt; }
            QPushButton#btn_start { background-color: #0EA5E9; }
            QPushButton#btn_stop { background-color: #475569; }
            QPushButton#btn_export { border: 1px solid #0EA5E9; color: #0EA5E9; background: transparent; }
            QPushButton#btn_log_tool { background-color: #334155; border: 1px solid #475569; border-radius: 4px; padding: 4px 8px; font-size: 8pt; color: #CBD5E1; min-height: 20px;}
            QPushButton#btn_log_tool:hover { background-color: #475569; color: white; }
            QPlainTextEdit { background-color: #0D1117; color: #38BDF8; border: 1px solid #334155; border-radius: 6px; font-family: Consolas, monospace; font-size: 8pt; padding: 5px;}
            QToolTip { color: #F8FAFC; background-color: #0F172A; border: 1px solid #0EA5E9; border-radius: 6px; padding: 10px; font-family: 'Microsoft YaHei'; font-size: 10pt; }
        """)

        self.centralwidget = QWidget(MainWindow)
        MainWindow.setCentralWidget(self.centralwidget)
        self.root_layout = QVBoxLayout(self.centralwidget)
        self.root_layout.setContentsMargins(10, 5, 10, 10); self.root_layout.setSpacing(5)

        self.lbl_main_title = QLabel("手机无线充电监控系统")
        self.lbl_main_title.setObjectName("main_title")
        self.lbl_main_title.setAlignment(Qt.AlignCenter)
        self.lbl_main_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.root_layout.addWidget(self.lbl_main_title)

        self.splitter = QSplitter(Qt.Horizontal)
        
        # --- 左侧面板 ---
        self.side_panel = QFrame(); self.side_panel.setMinimumWidth(200)
        side_layout = QVBoxLayout(self.side_panel) 
        side_layout.setContentsMargins(10, 5, 10, 10); side_layout.setSpacing(2)

        self.group_config = QGroupBox("连接配置")
        config_vbox = QVBoxLayout(self.group_config)
        config_vbox.setContentsMargins(5, 15, 5, 5); config_vbox.setSpacing(2)

        port_hbox = QHBoxLayout() 
        self.cb_port = QComboBox()
        port_hbox.addWidget(self.cb_port) 
        config_vbox.addLayout(port_hbox)
        self.cb_baudrate = QComboBox() 
        # 🟢 修复：补回丢失的波特率配置与布局添加代码
        self.cb_baudrate.addItems(["115200", "921600", "2000000"]) 
        config_vbox.addWidget(self.cb_baudrate)
        
        side_layout.addWidget(self.group_config)

        def create_lcd(name, color):
            box = QVBoxLayout(); box.setSpacing(0)
            lbl = QLabel(name); lbl.setObjectName("data_label")
            lcd = QLCDNumber(); lcd.setMinimumHeight(35); lcd.setStyleSheet(f"color: {color}; border: 1px solid #334155;")
            lcd.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            box.addWidget(lbl); box.addWidget(lcd)
            return box, lcd

        l1, self.lcd_v_in    = create_lcd("输入电压 (V_in)", "#FACC15")
        l2, self.lcd_i_in    = create_lcd("输入电流 (I_in)", "#22C55E")
        l3, self.lcd_v_out   = create_lcd("输出电压 (V_out)", "#FACC15")
        l4, self.lcd_i_out   = create_lcd("输出电流 (I_out)", "#22C55E")
        l5, self.lcd_power   = create_lcd("输出功率 (Power W)", "#A855F7")
        l7, self.lcd_v_bat   = create_lcd("电池电压 (V_bat)", "#FACC15")
        l8, self.lcd_i_bat   = create_lcd("电池电流 (I_bat)", "#22C55E")
        l9, self.lcd_temp    = create_lcd("线圈温度 (°C)", "#FB923C")
        l10, self.lcd_battery = create_lcd("当前电量 (%)", "#10B981")
        
        for l in [l1, l2, l3, l4, l5, l7, l8, l9, l10]: side_layout.addLayout(l)
        side_layout.addStretch(1)

        # 🟢 预埋 CC/CV 充电状态显示大屏占位符
        self.lbl_charge_state = QLabel("⚡ 充电状态: 等待接入...")
        self.lbl_charge_state.setAlignment(Qt.AlignCenter)
        self.lbl_charge_state.setStyleSheet("""
            background-color: #0F172A; 
            color: #94A3B8; 
            border: 1px dashed #334155; 
            border-radius: 6px; 
            padding: 10px; 
            font-size: 11pt; 
            font-weight: bold; 
            margin-bottom: 5px;
        """)
        side_layout.addWidget(self.lbl_charge_state)

        btn_box = QVBoxLayout(); btn_box.setSpacing(5)
        self.btn_start = QPushButton("▶ 开始")
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setEnabled(False)
        self.btn_export = QPushButton("💾 导出 CSV")

        self.btn_export = QPushButton("💾 导出 CSV")
        self.btn_report = QPushButton("📄 导出 PDF 报告") # 🟢 新增
        self.btn_report.setStyleSheet("background-color: #1E293B; border: 1px solid #38BDF8; color: #38BDF8;")
        
        btn_box.addWidget(self.btn_start)
        btn_box.addWidget(self.btn_stop)
        btn_box.addWidget(self.btn_export)
        btn_box.addWidget(self.btn_report) # 🟢 新增
        side_layout.addLayout(btn_box)

        # ==================== 中间面板：PyQtGraph 深度美化版 ====================
        self.chart_panel = QFrame()
        chart_layout = QVBoxLayout(self.chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        
        self.graph_widget = pg.GraphicsLayoutWidget()
        chart_layout.addWidget(self.graph_widget)
        
        self.graph_widget.ci.layout.setSpacing(12) 
        self.graph_widget.ci.layout.setContentsMargins(10, 10, 15, 10)

        self.vbs = []
        
        font_css = {'font-size': '8pt', 'font-family': 'Microsoft YaHei', 'font-weight': 'bold'}
        axis_pen = pg.mkPen(color='#334155', width=1.2)
        text_pen = pg.mkPen(color='#94A3B8')            

        def add_plot(row, title, label1, color1, label2=None, color2=None, link_plot=None):
            p = self.graph_widget.addPlot(row=row, col=0)
            p.getViewBox().setBackgroundColor('#0F172A')
            p.setDefaultPadding(0.08)

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
        self.log_panel = QFrame(); self.log_panel.setObjectName("log_panel")
        self.log_panel.setMinimumWidth(350) 
        log_layout = QVBoxLayout(self.log_panel); log_layout.setContentsMargins(10, 10, 10, 10); log_layout.setSpacing(5)
        
        log_header_lay = QHBoxLayout()
        self.lbl_log_title = QLabel("📡 报文实时监控")
        self.lbl_log_title.setStyleSheet("color: #CBD5E1; font-weight: bold; font-size: 10pt;")
        
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