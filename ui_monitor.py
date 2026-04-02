# ui_monitor.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLCDNumber, 
                             QPushButton, QFrame, QComboBox, QGroupBox, QSplitter, QSizePolicy, QPlainTextEdit)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.style as mplstyle
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False
mplstyle.use('fast')

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
            QPushButton#btn_refresh { background-color: #334155; border: 1px solid #475569; font-size: 9pt; min-height: 25px; }
            QPushButton#btn_log_tool { background-color: #334155; border: 1px solid #475569; border-radius: 4px; padding: 4px 8px; font-size: 8pt; color: #CBD5E1; min-height: 20px;}
            QPushButton#btn_log_tool:hover { background-color: #475569; color: white; }
            QPlainTextEdit { background-color: #0D1117; color: #38BDF8; border: 1px solid #334155; border-radius: 6px; font-family: Consolas, monospace; font-size: 8pt; padding: 5px;}
            
            /* 协议解析弹窗 - 专业黑客质感 */
            QToolTip { 
                color: #F8FAFC; 
                background-color: #0F172A; 
                border: 1px solid #0EA5E9; 
                border-radius: 6px; 
                padding: 10px; 
                font-family: 'Microsoft YaHei'; 
                font-size: 10pt; 
            }
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
        
        self.side_panel = QFrame(); self.side_panel.setMinimumWidth(200)
        side_layout = QVBoxLayout(self.side_panel) 
        side_layout.setContentsMargins(10, 5, 10, 10)
        side_layout.setSpacing(2)

        self.group_config = QGroupBox("连接配置")
        config_vbox = QVBoxLayout(self.group_config)
        config_vbox.setContentsMargins(5, 15, 5, 5)
        config_vbox.setSpacing(2)

        port_hbox = QHBoxLayout() 
        self.cb_port = QComboBox()

        # self.btn_refresh_port = QPushButton("刷新")
        # self.btn_refresh_port.setObjectName("btn_refresh")
        # self.btn_refresh_port.setFixedWidth(50)

        port_hbox.addWidget(self.cb_port) 
        # port_hbox.addWidget(self.btn_refresh_port)
        config_vbox.addLayout(port_hbox)
        self.cb_baudrate = QComboBox() 
        self.cb_baudrate.addItems(["115200", "921600", "2000000"])
        config_vbox.addWidget(self.cb_baudrate)
        side_layout.addWidget(self.group_config)

        def create_lcd(name, color):
            box = QVBoxLayout(); box.setSpacing(0)
            lbl = QLabel(name); lbl.setObjectName("data_label")
            lcd = QLCDNumber(); lcd.setMinimumHeight(35); lcd.setStyleSheet(f"color: {color};")
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

        btn_box = QVBoxLayout(); btn_box.setSpacing(5); ctrl_lay = QHBoxLayout(); ctrl_lay.setSpacing(5)
        self.btn_start = QPushButton("▶ 开始"); self.btn_stop = QPushButton("⏹ 停止"); self.btn_stop.setEnabled(False)
        ctrl_lay.addWidget(self.btn_start); ctrl_lay.addWidget(self.btn_stop)
        self.btn_export = QPushButton("💾 导出 CSV"); btn_box.addLayout(ctrl_lay); btn_box.addWidget(self.btn_export)
        side_layout.addLayout(btn_box)

        self.chart_panel = QFrame(); chart_layout = QVBoxLayout(self.chart_panel); chart_layout.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(tight_layout=True, facecolor='#1E293B'); self.canvas = FigureCanvas(self.figure); chart_layout.addWidget(self.canvas)

        def beautify_ax(ax, ylabel, color):
            ax.set_facecolor('#0F172A'); ax.set_ylabel(ylabel, color=color, fontweight='bold', fontsize=8)
            ax.tick_params(axis='both', colors='#64748B', labelsize=8); ax.grid(True, linestyle=':', alpha=0.3, color='#475569')
            for s in ['top', 'right']: ax.spines[s].set_visible(False)
            ax.spines['left'].set_edgecolor('#334155'); ax.spines['bottom'].set_edgecolor('#334155')

        self.ax_p = self.figure.add_subplot(411); beautify_ax(self.ax_p, "POWER(W)", "#A855F7")
        self.line_power, = self.ax_p.plot([], [], color='#A855F7', linewidth=2)
        
        self.ax_in = self.figure.add_subplot(412, sharex=self.ax_p); beautify_ax(self.ax_in, "INPUT(V)", "#FACC15")
        self.line_v_in, = self.ax_in.plot([], [], color='#FACC15', linewidth=1.5)
        self.ax_in_i = self.ax_in.twinx(); beautify_ax(self.ax_in_i, "INPUT(A)", "#22C55E")
        self.line_i_in, = self.ax_in_i.plot([], [], color='#22C55E', linewidth=1.5)
        
        self.ax_out = self.figure.add_subplot(413, sharex=self.ax_p); beautify_ax(self.ax_out, "OUTPUT(V)", "#FACC15")
        self.line_v_out, = self.ax_out.plot([], [], color='#FACC15', linewidth=1.5)
        self.ax_out_i = self.ax_out.twinx(); beautify_ax(self.ax_out_i, "OUTPUT(A)", "#22C55E")
        self.line_i_out, = self.ax_out_i.plot([], [], color='#22C55E', linewidth=1.5)
        
        self.ax_bat = self.figure.add_subplot(414, sharex=self.ax_p); beautify_ax(self.ax_bat, "BATTERY(V)", "#FACC15")
        self.line_v_bat, = self.ax_bat.plot([], [], color='#FACC15', linewidth=1.5)
        self.ax_bat_i = self.ax_bat.twinx(); beautify_ax(self.ax_bat_i, "BATTERY(A)", "#22C55E")
        self.line_i_bat, = self.ax_bat_i.plot([], [], color='#22C55E', linewidth=1.5)
        
        plt.setp(self.ax_p.get_xticklabels(), visible=False); plt.setp(self.ax_in.get_xticklabels(), visible=False); plt.setp(self.ax_out.get_xticklabels(), visible=False)

        self.log_panel = QFrame(); self.log_panel.setObjectName("log_panel")
        self.log_panel.setMinimumWidth(600) 
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
        
        # 严格执行 3:11:6 拉伸分配
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 11) 
        self.splitter.setStretchFactor(2, 6) 
        
        self.root_layout.addWidget(self.splitter)