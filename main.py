# main.py - 手机无线充电监控系统
import sys, time, datetime, sqlite3, serial, csv, os, math, re
import queue
import serial.tools.list_ports
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog, QToolTip, QSizePolicy
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QEvent
from ui_monitor import Ui_MonitorWindow

# ================== 数据库初始化 ==================
def init_db():
    conn = sqlite3.connect('charging_data.db')
    conn.execute('PRAGMA journal_mode=WAL;') 
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS charging_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        rel_time REAL, v_in REAL, i_in REAL, v_out REAL, i_out REAL, 
                        v_bat REAL, i_bat REAL, eff REAL, power REAL, temp REAL, battery REAL)''')
    try: cursor.execute('CREATE INDEX idx_rel_time ON charging_metrics(rel_time)')
    except: pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS tx0_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        message TEXT)''')
    conn.commit(); conn.close()

# ================== 异步工作线程 ==================
class DBWorker(QThread):
    def __init__(self):
        super().__init__(); self.queue = queue.Queue(); self.running = True
    def run(self):
        conn = sqlite3.connect('charging_data.db', check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        cur = conn.cursor()
        while self.running:
            try:
                task = self.queue.get(timeout=0.1) 
                if task['type'] == 'metric':
                    d = task['data']
                    cur.execute("INSERT INTO charging_metrics (rel_time, v_in, i_in, v_out, i_out, v_bat, i_bat, eff, power, temp, battery) VALUES (?,?,?,?,?,?,?,?,?,?,?)", 
                                (task['rel_time'], d['v_in'], d['i_in'], d['v_out'], d['i_out'], d['v_bat'], d['i_bat'], d['eff'], d['p'], d['t'], d['b']))
                elif task['type'] == 'log':
                    cur.execute("INSERT INTO tx0_logs (message) VALUES (?)", (task['msg'],))
                conn.commit()
            except queue.Empty: continue
            except Exception: pass
        conn.close()
    def stop(self): self.running = False; self.wait()

class FetchWorker(QThread):
    chart_fetched = pyqtSignal(tuple)
    log_fetched = pyqtSignal(str, bool, str) 
    def __init__(self):
        super().__init__()
        self.running = True
        self.log_queue = queue.Queue()
        self.latest_xlim = None
        self.chart_request = False

    def run(self):
        conn = sqlite3.connect('charging_data.db', check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        cur = conn.cursor()

        while self.running:
            if self.chart_request and self.latest_xlim:
                self.chart_request = False
                xlim = self.latest_xlim
                margin = (xlim[1] - xlim[0]) * 0.1

                try:
                    cur.execute('''SELECT rel_time, power, v_in, i_in, v_out, i_out, v_bat, i_bat FROM charging_metrics WHERE rel_time BETWEEN ? AND ? ORDER BY rel_time ASC''', (xlim[0]-margin, xlim[1]+margin))
                    rows = cur.fetchall()
                    if rows:
                        limit_points = 2000
                        if len(rows) > limit_points:
                            step = len(rows) // limit_points
                            rows = rows[::step]
                        self.chart_fetched.emit(tuple(zip(*rows)))
                    else: self.chart_fetched.emit(([],[],[],[],[],[],[],[]))
                except Exception: pass
            try:
                log_task = self.log_queue.get(timeout=0.05)
                r = cur.execute("SELECT message FROM (SELECT id, message FROM tx0_logs ORDER BY id DESC LIMIT 1000 OFFSET ?) ORDER BY id ASC", (log_task['offset'],)).fetchall()
                if r: self.log_fetched.emit("\n".join([row[0] for row in r]), True, log_task['direction'])
                else: self.log_fetched.emit("", False, log_task['direction'])
            except queue.Empty: 
                pass

        conn.close()
    def stop(self): 
        self.running = False
        self.wait()

class SerialWorker(QThread):
    data_ready = pyqtSignal(dict)
    log_ready = pyqtSignal(str) 

    def __init__(self, port, baudrate):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.last_log_time = datetime.datetime.now() 

    def get_strict_timestamp(self):
        now = datetime.datetime.now()
        if now <= self.last_log_time: now = self.last_log_time + datetime.timedelta(milliseconds=1)
        self.last_log_time = now
        return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"
    def run(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=0); self.serial_conn.reset_input_buffer()
        except Exception:
            while self.running:
                time.sleep(0.05); t = time.time(); ts = self.get_strict_timestamp()
                self.parse_line(f"AA55:9000:1500:8500:1400:4000:3000:45:80:EDED")
                if int(t)%3==0: self.log_ready.emit(f"{ts} ASK 51 3E 00 00 00 00 F ") 
                elif int(t)%3==1: self.log_ready.emit(f"{ts} ASK 71 22 12 34 00 00 00 00 F ")
                else: self.log_ready.emit(f"{ts} FSK 40 03 F")
            return
        buffer = ""
        while self.running:
            try:
                waiting = self.serial_conn.in_waiting
                if waiting > 0:
                    buffer += self.serial_conn.read(waiting).decode('ascii', errors='ignore')
                    while "AA55" in buffer and "EDED" in buffer:
                        start = buffer.find("AA55") 
                        end = buffer.find("EDED", start)
                        
                        if end != -1: 
                            self.parse_line(buffer[start:end+4])
                            buffer = buffer[end+4:] 
                        else: 
                            buffer = buffer[start:]
                            break 

                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1); line = line.strip()
                        if line.startswith("TX0"):
                            clean = line[3:].strip().strip(':').strip()
                            self.log_ready.emit(f"{self.get_strict_timestamp()} {clean}")
                        elif "AA55" in line and "EDED" in line: 
                            self.parse_line(line)

                else: 
                    time.sleep(0.001)
            except: 
                break

    def parse_line(self, line):
        try:
            p = line[line.find("AA55"):line.find("EDED")+4].split(':')
            if len(p) == 10:
                v_in, i_in, v_out, i_out, v_bat, i_bat = [float(x)/1000 for x in p[1:7]]
                p_out = v_out * i_out; p_bat = v_bat * i_bat; eff = min(100.0, (p_bat/p_out*100.0) if p_out > 0.1 else 0.0)
                self.data_ready.emit({'ts':time.time(),'v_in':v_in,'i_in':i_in,'v_out':v_out,'i_out':i_out,'v_bat':v_bat,'i_bat':i_bat,'eff':eff,'p':p_out,'t':int(p[7]),'b':int(p[8])})
        except: pass
    def stop(self): self.running = False; self.wait()

# ================== 主窗口：核心业务逻辑 ==================
class MonitorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MonitorWindow()
        self.ui.setupUi(self)
        init_db()
        
        for name, min_w in [('cb_port', 150), ('cb_baudrate', 120), ('btn_start', 100), ('btn_stop', 100)]:
            if hasattr(self.ui, name):
                widget = getattr(self.ui, name)
                widget.setMinimumWidth(min_w)
                widget.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        
        self.worker = None 
        self.x_data, self.y_vi, self.y_ii, self.y_vo, self.y_io, self.y_vb, self.y_ib, self.y_eff, self.y_p, self.y_t, self.y_b = [],[],[],[],[],[],[],[],[],[],[]
        self.latest_data, self.start_time, self.time_offset = None, 0.0, 0.0
        
        self.auto_scroll_chart, self.log_mode, self.log_offset, self.is_fetching_logs = True, 'live', 0, False
        self.log_buffer, self.ui_lock, self.last_hovered_line = [], False, -1
        self.is_dragging = False 
        
        self.db_worker = DBWorker(); self.db_worker.start()
        self.fetch_worker = FetchWorker(); self.fetch_worker.chart_fetched.connect(self.on_chart_fetched)
        self.fetch_worker.log_fetched.connect(self.on_log_fetched); self.fetch_worker.start()
        
        self.timer = QTimer(self); self.timer.timeout.connect(self.render_ui); self.timer.start(100)
        self.log_interaction_timer = QTimer(self); self.log_interaction_timer.setSingleShot(True); self.log_interaction_timer.timeout.connect(self.force_live_mode)
        
        self.ui.text_log.setMouseTracking(True); self.ui.text_log.viewport().setMouseTracking(True)
        self.ui.text_log.viewport().installEventFilter(self); self.ui.text_log.verticalScrollBar().installEventFilter(self)
        
        self.ui.btn_start.clicked.connect(self.start_mon); self.ui.btn_stop.clicked.connect(self.stop_mon)
        # self.ui.btn_refresh_port.clicked.connect(self.scan_ports); 
        self.ui.btn_export.clicked.connect(self.export_csv)
        self.ui.btn_rollback.clicked.connect(self.toggle_log_mode); self.ui.btn_export_log.clicked.connect(self.export_tx0_logs)
        self.ui.canvas.mpl_connect('scroll_event', self.on_chart_scroll); self.ui.canvas.mpl_connect('button_press_event', self.on_chart_press)
        self.ui.canvas.mpl_connect('motion_notify_event', self.on_chart_motion); self.ui.canvas.mpl_connect('button_release_event', self.on_chart_release)
        self.ui.text_log.verticalScrollBar().valueChanged.connect(self.on_log_scroll)
        
        self.scan_ports(); self.auto_scroll_chart = False
        try:
            conn = sqlite3.connect('charging_data.db'); max_t = conn.execute("SELECT MAX(rel_time) FROM charging_metrics").fetchone()[0]; conn.close()
            if max_t: self.ui.ax_p.set_xlim(max_t-60, max_t+5); self.request_chart_fetch()
        except: pass

    # ========================== 全局自适应引擎 (完美比例 3:11:6) ==========================
    def adjust_panel_widths(self):
        """严格按照 左侧(3):中间(11):右侧(6) 的物理像素比例进行首屏分割"""
        try:
            center_point = self.geometry().center()
            current_screen = QApplication.screenAt(center_point)
            if not current_screen:
                current_screen = QApplication.primaryScreen()
                
            screen_width = current_screen.geometry().width()
            
            # 计算比例因子 (3 + 11 + 6 = 20)
            left_target_width = int(screen_width * 3 / 20)
            mid_target_width = int(screen_width * 11 / 20)
            # 剩余的给右侧，防止浮点数精度截断导致的像素缝隙
            right_target_width = screen_width - left_target_width - mid_target_width

            if hasattr(self.ui, 'splitter'):
                self.ui.splitter.setSizes([left_target_width, mid_target_width, right_target_width])

        except Exception as e:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_initial_layout_done'):
            self.adjust_panel_widths()
            self._initial_layout_done = True

    def moveEvent(self, event):
        super().moveEvent(event)

    # ========================== WPC Qi 2.2.1 深度字段解析引擎 ==========================
    def parse_qi_message(self, line):
        line = re.sub(r'\s+', ' ', line).strip() + " "
        if "ASK " in line:
            start = line.find("ASK ") + 4
            end = line.find(" F ", start)
            if end != -1: return self.decode_mpp_full(line[start:end].strip(), "ASK")
        if "FSK " in line:
            start = line.find("FSK ") + 4
            return self.decode_mpp_full(line[start:].strip().split('(')[0], "FSK")
        return None

    def decode_mpp_full(self, hex_str, p_type):
        try:
            raw = [int(x, 16) for x in hex_str.replace('0x','').replace(',',' ').split()]
            if not raw: return None
            header = raw[0]
            
            cs, payload, cs_st = None, raw[1:], "N/A"
            if len(raw) > 1:
                calc = 0
                for b in raw[:-1]: calc ^= b
                if calc == raw[-1]: cs, payload, cs_st = raw[-1], raw[1:-1], "<span style='color:#22C55E;'>✅ OK</span>"
                else: cs, payload, cs_st = raw[-1], raw[1:-1], "<span style='color:#EF4444;'>❌ ERR</span>"
            
            if p_type == "ASK": info, detail = self.ask_qi22_map(header, payload)
            else: info, detail = self.fsk_qi22_map(header, payload)

            title_color = '#38BDF8' if p_type == 'ASK' else '#FB923C'
            html = f"<div style='min-width: 200px; font-family: Consolas, monospace;'>"
            html += f"<b style='color:{title_color}; font-size: 11pt;'>{'🔵 ASK (PRx ➔ PTx)' if p_type=='ASK' else '🟠 FSK (PTx ➔ PRx)'}</b>"
            html += f"<hr style='border:1px solid #334155; margin: 5px 0;'>"
            html += f"<b>指令 Header:</b> <span style='color:#FACC15;'>0x{header:02X}</span> [{info}]<br>"
            html += f"<b>原始 Payload:</b> {' '.join([f'{x:02X}' for x in payload]) if payload else 'None'}<br>"
            if cs is not None: html += f"<b>XOR 校验和:</b> 0x{cs:02X} ({cs_st})<br>"
            html += f"<hr style='border:1px dashed #334155; margin: 5px 0;'>"
            html += f"<b>📑 字节/位级深度破译:</b><br><div style='color:#E2E8F0; padding-top: 5px; line-height: 1.4;'>{detail}</div>"
            html += "</div>"
            return html
        except Exception as e: return f"解析异常: {e}"

    def ask_qi22_map(self, header, payload):
        """ASK (PRx -> PTx) 接收端到发射端 - Wireshark 级解析"""
        d = {
            0x01: ("SIG", "信号强度 (Signal Strength)"),
            0x02: ("EPT", "停止充电 (End Power Transfer)"),
            0x03: ("CE", "控制误差 (Control Error)"),
            0x04: ("RP8", "接收功率 (8-bit Received Power)"),
            0x05: ("CHS", "充电状态 (Charge Status)"),
            0x06: ("PCH", "功率控制保持 (Power Control Hold-off)"),
            0x07: ("GRQ", "通用请求 (General Request)"),
            0x09: ("RENEG", "重新协商 (Renegotiate)"),
            0x22: ("FOD", "异物检测状态 (FOD Status)"),
            0x31: ("RP24", "接收功率 (24-bit Received Power)"),
            0x51: ("CFG", "配置数据包 (Configuration)"),
            0x71: ("ID", "身份识别数据包 (Identification)"),
            0x13:("MSR", " Mode Select Request"),
            0x18:("CLOAK", " Cloak Request"),
            0x19:("XCE", " Extended Control Error"),
            0x1A:("PROP/1a", " MPP PRx Proprietary Packet"),
            0x1B:("PROP/1b", " MPP PRx Proprietary Packet"),
            0x20:("SRQ", " Specific Request [PLA]"),
            0x23:("CAL_OP", " Calibration Operation"),
            0x26:("SADT/1e", " Simultaneous Auxiliary Data Transport (even)"),
            0x27:("SADT/1o", " Simultaneous Auxiliary Data Transport (odd)"), 
            0x28:("GET Get", " request"),
            0x29:("EDS", " Enabled Data Streams"),
            0x2A:("PROP/2a", " MPP PRx Proprietary Packet"),
            0x2B:("PROP/2b", " MPP PRx Proprietary Packet"),
            0x2C:("CAL_ENTER", " Enter Calibration"),
            0x2D:("CAL_EXIT", " Exit Calibration"),
            0x36:("SADT/2e", " Simultaneous Auxiliary Data Transport (even)"),
            0x37:("SADT/2o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x38:("SDSR", " Simultaneous Data Stream Response"),
            0x39:("PROP/39", " MPP PRx Proprietary Packet"),
            0x46:("SADT/3e", " Simultaneous Auxiliary Data Transport (even)"),
            0x47:("SADT/3o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x48:("SADC", " Simultaneous Auxiliary Data Control"),
            0x49:("PROP/49", " MPP PRx Proprietary Packet"),
            0x50:("KEST-COEFF", " K-est Coefficients"),
            0x56:("SADT/4e", " Simultaneous Auxiliary Data Transport (even)"),
            0x57:("SADT/4o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x58:("REPORT/PLA", " Report/Power Loss Accounting"),
            0x59:("PROP/59", " MPP PRx Proprietary Packet"),
            0x66:("SADT/5e", " Simultaneous Auxiliary Data Transport (even)"),
            0x67:("SADT/5o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x78:("PLAP", " Power Loss Accounting Parameters"),
            0x76:("SADT/6e", " Simultaneous Auxiliary Data Transport (even)"),
            0x77:("SADT/6o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x79:("PROP/79", " MPP PRx Proprietary Packet "),
            0x81:("MPP-XID", " MPP Extended Identification"),
            0x84:("ECAP", " Extended Received Capabilities"),
            0x85:("PROP/85", " MPP PRx Proprietary Packet "),
            0x88:("PLA_2", " Power Loss Accounting"),
            0x90:("PLAP_2", " Power Loss Accounting Parameters"),
            0x96:("CAL_CAPTURE", " Calibration Capture"),
            0xA8:("MATEDQ-COEFF", " Mated-Q Coefficients"),


        }
        name, _ = d.get(header, (f"UNK_0x{header:02X}", "未知/专有指令"))
        desc = ""
        plen = len(payload)

        if header == 0x01 and plen >= 1:
            val = payload[0]
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{val:02X}<br>"
            desc += f"  ↳ 耦合强度映射值: <b>{val}</b> / 255 ({(val/255)*100:.1f}%)"

        elif header == 0x02 and plen >= 1:
            e_map = {0x00: "未知", 0x01: "<span style='color:#22C55E'>充电完成</span>", 0x02: "<span style='color:#EF4444'>内部故障</span>", 0x03: "<span style='color:#EF4444'>过温</span>", 0x04: "<span style='color:#EF4444'>过压</span>", 0x05: "<span style='color:#EF4444'>过流</span>", 0x06: "<span style='color:#EF4444'>电池故障</span>", 0x0A: "重启传输", 0x0B: "<span style='color:#EF4444'>鉴权失败</span>"}
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} ➔ <b>{e_map.get(payload[0], '保留原因')}</b>"

        elif header == 0x03 and plen >= 1:
            val = payload[0]
            ce = val - 256 if val > 127 else val
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{val:02X}<br>"
            desc += f"  ↳ 误差值 (Signed 8-bit): <b style='color:{'#22C55E' if ce<0 else '#EF4444'};'>{ce}</b><br>"
            desc += f"  <i>* 负值要求 PTx 降功率，正值要求升功率</i>"

        elif header == 0x04 and plen >= 1:
            val = payload[0]
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{val:02X}<br>"
            desc += f"  ↳ 接收功率比: <b>{val}</b> / 128 ({(val/128)*100:.1f}% Max Power)"

        elif header == 0x05 and plen >= 1:
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} ➔ 电池电量: <b style='color:#22C55E'>{payload[0]} %</b>"

        elif header == 0x06 and plen >= 1:
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} ➔ 保持时间: <b>{payload[0] * 10} ms</b>"

        elif header == 0x13 and plen >= 1:
            align = payload[0] & 0x0F
            couple = (payload[0] >> 4) & 0x0F
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} (磁吸状态)<br>"
            desc += f"  ↳ 对齐质量 (Alignment) [Bit 0-3]: <b>{align}</b>/15<br>"
            desc += f"  ↳ 耦合强度 (Coupling)  [Bit 4-7]: <b>{couple}</b>/15<br>"
            if plen >= 2:
                flags = payload[1]
                desc += f"• <span style='color:#38BDF8'>Byte 1:</span> 0x{flags:02X} (PRx Flags)<br>"
                desc += f"  ↳ Bit 0 (过压保护): {'<b style=''color:#EF4444''>触发</b>' if flags & 0x01 else '正常'}<br>"
                desc += f"  ↳ Bit 1 (过流保护): {'<b style=''color:#EF4444''>触发</b>' if flags & 0x02 else '正常'}"

        elif header == 0x23 and plen >= 2:
            val = (payload[0] << 8) | payload[1]
            ce = val - 65536 if val > 32767 else val
            desc = f"• <span style='color:#38BDF8'>Byte 0-1:</span> 0x{payload[0]:02X} 0x{payload[1]:02X}<br>"
            desc += f"  ↳ 16-bit 高精度误差: <b style='color:{'#22C55E' if ce<0 else '#EF4444'};'>{ce}</b>"

        elif header == 0x28 and plen >= 1:
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} ➔ 请求 PTx 发送 <b>0x{payload[0]:02X}</b> 报文"

        elif header == 0x31 and plen >= 3:
            mode = payload[0] & 0x07
            val = payload[1] | (payload[2] << 8)
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} ➔ 功率计算模式: Mode <b>{mode}</b><br>"
            desc += f"• <span style='color:#38BDF8'>Byte 1-2:</span> 0x{payload[1]:02X} 0x{payload[2]:02X}<br>"
            desc += f"  ↳ 24-bit 接收功率参考值: <b>{val}</b>"

        elif header == 0x51 and plen >= 5:
            p_class = payload[0] >> 6
            max_p_val = payload[0] & 0x3F
            prop = (payload[1] >> 7) & 1
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X}<br>"
            desc += f"  ↳ 功率级别 (Power Class): Class <b>{p_class}</b><br>"
            desc += f"  ↳ 最大协商功率 (Max Pwr): <b>{max_p_val * 0.5:.1f} W</b><br>"
            desc += f"• <span style='color:#38BDF8'>Byte 1:</span> 0x{payload[1]:02X}<br>"
            desc += f"  ↳ 专有扩展标志 (Proprietary): <b>{'Yes' if prop else 'No'}</b><br>"
            desc += f"  ↳ 窗口极性/深度位掩码: [0x{payload[1]&0x7F:02X}]<br>"
            desc += f"• <span style='color:#38BDF8'>Byte 3:</span> 0x{payload[3]:02X} ➔ 期望包数 (Count): <b>{payload[3]}</b><br>"
            desc += f"• <span style='color:#38BDF8'>Byte 4:</span> 0x{payload[4]:02X} ➔ 窗口时间偏移 (Window Offset)"

        elif header == 0x71 and plen >= 7:
            ver_major = payload[0] >> 4
            ver_minor = payload[0] & 0x0F
            ext = (payload[0] >> 7) & 1
            ptmc = (payload[1] << 8) | payload[2]
            dev_id = f"{payload[3]:02X} {payload[4]:02X} {payload[5]:02X} {payload[6]:02X}"
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X}<br>"
            desc += f"  ↳ Qi 版本号: <b>{ver_major}.{ver_minor}</b> (Ext: {ext})<br>"
            desc += f"• <span style='color:#38BDF8'>Byte 1-2:</span> 0x{payload[1]:02X} 0x{payload[2]:02X}<br>"
            desc += f"  ↳ 制造商代码 (PTMC): <b>0x{ptmc:04X}</b><br>"
            desc += f"• <span style='color:#38BDF8'>Byte 3-6:</span> {dev_id}<br>"
            desc += f"  ↳ 基本设备 ID (Basic Device ID)"

        elif header in [0x48, 0x38, 0xA8]:
            desc = f"• 鉴权安全负载 (Auth Data Stream)<br>"
            desc += f"• 负载长度: <b>{plen} Bytes</b><br>"
            desc += f"• 报文片段: <span style='color:#94A3B8'>{' '.join([f'{b:02X}' for b in payload[:12]])} ...</span>"

        else:
            if not payload: desc = "<i>无 Payload (Empty Packet)</i>"
            else:
                desc = f"• 载荷长度: {plen} Bytes<br>"
                desc += f"• HEX: <span style='color:#94A3B8'>{' '.join([f'{b:02X}' for b in payload])}</span>"

        return name, desc

    def fsk_qi22_map(self, header, payload):
        """FSK (PTx -> PRx) 发射端到接收端 - Wireshark 级解析"""
        d = {
            0x00: ("NAK", "拒绝"),
            0x55: ("ND", "未定义 (Not Defined)"),
            0x33: ("ATN", "注意 (Attention)"),
            0xFF: ("ACK", "同意 (Acknowledge)"),
            0x01: ("ERR", "Error Status"),
            0x0A: ("EPTR", "End Power Transfer Request"),
            0x14: ("CAL_CAPTURE_RSP", " Calibration Capture Response"),
            0x1C: ("PROP/1c", " MPP PTx Proprietary Packet"),
            0x1B: ("CAL_OP_RSP", " Calibration Operation Response"),
            0x1D: ("PROP/1d MPP", " PTx Proprietary Packet"),
            0x1E: ("0x00 CLOAK", " Cloak Request"),
            0x1E: ("0x03 RCS", " Regulation Control Status"),
            0x1F: ("CHS", " Charge Status"),
            0x23: ("MSS", " Mode Select Status"),
            0x26: ("SADT/1e", " Simultaneous Auxiliary Data Transport (even)"),
            0x27: ("SADT/1o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x2C: ("PROP/2c", " MPP PTx Proprietary Packet"),
            0x2D: ("PROP/2d", " MPP PTx Proprietary Packet"),
            0x2E: ("GET", " Get Request"),
            0x2F: ("EDS", " Enabled Data Streams"),
            0x34: ("CAL_ENTER_RSP", " Enter Calibration Response"),
            0x36: ("SADT/2e", " Simultaneous Auxiliary Data Transport (even)"),
            0x37: ("SADT/2o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x3E: ("PROP/3e", " MPP PTx Proprietary Packet "),
            0x3F: ("INV/SDSR/KEST", "0x00:Inverter Voltage 0x01:Simultaneous Data Stream Response 0x02:Estimated K"),
            0x40: ("MATEDQ_RES", " Mated-Q Results "),
            0x43: ("CAL_CAP", " Calibration Capabilities "),
            0x46: ("SADT/3e", " Simultaneous Auxiliary Data Transport (even) "),
            0x47: ("SADT/3o", " Simultaneous Auxiliary Data Transport (odd) "),
            0x4E: ("PROP/4e", " MPP PTx Proprietary Packet "),
            0x4F: ("SADC", " Simultaneous Auxiliary Data Control "),
            0x54: ("dPCAL_PARAM", " Calibration Parameter "),
            0x56: ("SADT/4e", " Simultaneous Auxiliary Data Transport (even)"),
            0x57: ("SADT/4o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x5A: ("MODECAP", " Power Modes Capabilities"),
            0x5E: ("PROP/5e", " MPP PTx Proprietary Packet"),
            0x5F: ("PLAP", " Power Loss Accounting Parameters"),
            0x61: ("GMP", " Gain Measurement Parameters"),
            0x66: ("SADT/5e", " Simultaneous Auxiliary Data Transport (even)"),
            0x67: ("SADT/5o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x76: ("SADT/6e", " Simultaneous Auxiliary Data Transport (even)"),
            0x77: ("SADT/6o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x88: ("PLAP_2", " Power Loss Accounting Parameters"),
            0x8E: ("PROP/8e", " MPP PTx Proprietary Packet"),
            0x8F: ("XID/ECAP", " 0x00:Extended Power Transmitter Identification 0x01:Extended Power Transmitter Extended Capabilities"),
            0xA0: ("MODEXCAP", " Power Modes Extended Capabilities"),
        }
        name, _ = d.get(header, (f"UNK_0x{header:02X}", "扩展/专有 FSK 指令"))
        desc = ""
        plen = len(payload)

        if header == 0x01: desc = "<b style='color:#22C55E'>✓ ACK (接受/确认上一条 PRx 指令)</b>"
        elif header == 0x02: desc = "<b style='color:#EF4444'>✗ NACK (拒绝/条件不支持)</b>"
        elif header == 0x03: desc = "<b style='color:#FACC15'>⚠ ND (指令格式不识别)</b>"
        
        elif header == 0x09 and plen >= 1:
            r = {0x00: "<b style='color:#22C55E'>ACK</b>", 0x01: "<b style='color:#EF4444'>NACK</b>", 0x02: "<b style='color:#FACC15'>ND</b>", 0x03: "<b style='color:#38BDF8'>ATN</b>"}
            desc = f"• <span style='color:#FB923C'>Byte 0:</span> 0x{payload[0]:02X} ➔ 响应类型: {r.get(payload[0], 'Reserved')}"

        elif header == 0x40 and plen >= 1:
            flags = payload[0]
            desc = f"• <span style='color:#FB923C'>Byte 0:</span> 0x{flags:02X} (PTx 状态标志位图)<br>"
            desc += f"  ↳ Bit 0 (功率限制): {'<b style=''color:#EF4444''>触发降额</b>' if flags & 0x01 else '未激活'}<br>"
            desc += f"  ↳ Bit 1 (温度限制): {'<b style=''color:#EF4444''>触发过温保护</b>' if flags & 0x02 else '未激活'}<br>"
            desc += f"  ↳ Bit 2 (疑似异物 FOD): {'<b style=''color:#EF4444''>报警 (FOD)</b>' if flags & 0x04 else '<b style=''color:#22C55E''>正常</b>'}<br>"
            desc += f"  ↳ Bit 3 (鉴权状态): {'<b style=''color:#38BDF8''>处理中/完成</b>' if flags & 0x08 else '无鉴权'}"

        elif header == 0x43 and plen >= 2:
            max_p = payload[0] * 0.5
            auth_cap = (payload[1] >> 4) & 1
            desc = f"• <span style='color:#FB923C'>Byte 0:</span> 0x{payload[0]:02X}<br>"
            desc += f"  ↳ PTx 保证输出功率 (Guaranteed): <b>{max_p:.1f} W</b><br>"
            desc += f"• <span style='color:#FB923C'>Byte 1:</span> 0x{payload[1]:02X}<br>"
            desc += f"  ↳ 鉴权硬件 (Auth Capable): <b>{'具备' if auth_cap else '不具备'}</b>"

        elif header in [0x11, 0x76, 0x77]:
            desc = f"• PTx 鉴权下行安全通道 (Security Channel)<br>"
            desc += f"• 负载长度: <b>{plen} Bytes</b><br>"
            if plen > 0:
                desc += f"• 报文片段: <span style='color:#94A3B8'>{' '.join([f'{b:02X}' for b in payload[:12]])} ...</span>"

        else:
            if not payload: desc = "<i>无 Payload (Empty Packet)</i>"
            else:
                desc = f"• 载荷长度: {plen} Bytes<br>"
                desc += f"• HEX: <span style='color:#94A3B8'>{' '.join([f'{b:02X}' for b in payload])}</span>"
        
        return name, desc

    # ========================== 交互逻辑：出口函数与 Y 轴自适应 ==========================
    def export_csv(self):
        p, _ = QFileDialog.getSaveFileName(self, "导出表格数据", f"Qi_Monitor_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "CSV (*.csv)")
        if p:
            try:
                c = sqlite3.connect('charging_data.db')
                r = c.execute("SELECT timestamp, v_in, i_in, v_out, i_out, v_bat, i_bat, eff, power, temp, battery FROM charging_metrics ORDER BY rel_time ASC").fetchall()
                c.close()
                with open(p, 'w', newline='', encoding='utf-8-sig') as f:
                    csv.writer(f).writerow(["时间戳","Vin","Iin","Vout","Iout","Vbat","Ibat","效率","功率","温度","电量"])
                    csv.writer(f).writerows(r)
                QMessageBox.information(self, "成功", "数据导出成功！")
            except Exception as e: QMessageBox.critical(self, "错误", f"导出失败: {e}")

    @staticmethod
    def apply_strict_smart_ylim(ax, y_data, min_span):
        if not y_data: return
        ymin, ymax = min(y_data), max(y_data)
        if (ymax - ymin) < min_span:
            center = (ymax + ymin) / 2.0; ax.set_ylim(center - min_span / 2.0, center + min_span / 2.0)
        else:
            span = ymax - ymin; ax.set_ylim(ymin - span * 0.1, ymax + span * 0.1)

    def eventFilter(self, obj, event):
        if obj == self.ui.text_log.viewport():
            if event.type() == QEvent.MouseMove:
                if self.worker and self.worker.isRunning():
                    self.log_interaction_timer.start(3000); QToolTip.hideText()
                else:
                    cursor = self.ui.text_log.cursorForPosition(event.pos())
                    if cursor.blockNumber() != self.last_hovered_line:
                        self.last_hovered_line = cursor.blockNumber()
                        info = self.parse_qi_message(cursor.block().text())
                        if info: QToolTip.showText(event.globalPos(), info, self.ui.text_log)
                        else: QToolTip.hideText()
            elif event.type() == QEvent.Leave: QToolTip.hideText(); self.last_hovered_line = -1
        return super().eventFilter(obj, event)

    # ========================== UI 调度引擎 ==========================
    def render_ui(self):
        if self.log_buffer:
            if self.log_mode == 'live':
                self.ui_lock = True; self.ui.text_log.appendPlainText("\n".join(self.log_buffer)); self.ui_lock = False
            self.log_buffer.clear()
        if self.latest_data:
            d = self.latest_data
            for k,lcd in zip(['v_in','i_in','v_out','i_out','p','v_bat','i_bat','t','b'], 
                             [self.ui.lcd_v_in, self.ui.lcd_i_in, self.ui.lcd_v_out, self.ui.lcd_i_out, self.ui.lcd_power, self.ui.lcd_v_bat, self.ui.lcd_i_bat, self.ui.lcd_temp, self.ui.lcd_battery]):
                lcd.display(f"{d[k]:.2f}" if isinstance(d[k], float) else d[k])
        if self.auto_scroll_chart and self.worker and self.worker.isRunning():
            if not self.x_data: return
            self.ui.line_power.set_data(self.x_data, self.y_p)
            self.ui.line_v_in.set_data(self.x_data, self.y_vi); self.ui.line_i_in.set_data(self.x_data, self.y_ii)
            self.ui.line_v_out.set_data(self.x_data, self.y_vo); self.ui.line_i_out.set_data(self.x_data, self.y_io)
            self.ui.line_v_bat.set_data(self.x_data, self.y_vb); self.ui.line_i_bat.set_data(self.x_data, self.y_ib)
            for ax,y,span in [(self.ui.ax_p,self.y_p,1.0),(self.ui.ax_in,self.y_vi,1.0),(self.ui.ax_in_i,self.y_ii,0.5),(self.ui.ax_out,self.y_vo,1.0),(self.ui.ax_out_i,self.y_io,0.5),(self.ui.ax_bat,self.y_vb,1.0),(self.ui.ax_bat_i,self.y_ib,0.5)]: self.apply_strict_smart_ylim(ax,y,span)
            cur_t, win = self.x_data[-1], 60
            self.ui.ax_p.set_xlim(cur_t-win, cur_t+win*0.05) if cur_t > win else self.ui.ax_p.set_xlim(0, max(cur_t+1,10))
            self.ui.canvas.draw_idle()

    # ========================== 其他逻辑分支 ==========================
    def start_mon(self):
        if self.ui.cb_port.currentText() == "无设备": return
        self.ui.btn_start.setEnabled(False); self.ui.btn_stop.setEnabled(True); self.ui.cb_port.setEnabled(False)
        try:
            conn = sqlite3.connect('charging_data.db'); max_t = conn.execute("SELECT MAX(rel_time) FROM charging_metrics").fetchone()[0]; conn.close()
            self.time_offset = (max_t if max_t is not None else 0.0) + 1.0 
        except: self.time_offset = 0.0
        self.start_time, self.ui_lock = time.time(), True
        self.ui.text_log.clear(); self.ui_lock = False; self.log_buffer.clear()
        self.auto_scroll_chart, self.log_mode = True, 'live'
        [a.clear() for a in [self.y_vi, self.y_ii, self.y_vo, self.y_io, self.y_vb, self.y_ib, self.y_eff, self.y_p, self.y_t, self.y_b]]
        self.worker = SerialWorker(self.ui.cb_port.currentText(), int(self.ui.cb_baudrate.currentText()))
        self.worker.data_ready.connect(self.process_data); self.worker.log_ready.connect(self.append_log); self.worker.start()

    def stop_mon(self):
        self.ui.btn_start.setEnabled(True); self.ui.btn_stop.setEnabled(False); self.ui.cb_port.setEnabled(True)
        if self.worker: self.worker.stop(); self.worker = None
        self.log_interaction_timer.stop()

    def force_live_mode(self):
        if self.log_mode != 'live':
            self.log_mode, self.log_offset, self.ui_lock = 'live', 0, True
            self.ui.btn_rollback.setText("🔄 历史查阅"); self.ui.text_log.clear(); self.ui_lock = False
            self.fetch_worker.log_queue.put({'offset':0, 'direction':'down'})
        else: self.safe_set_scroll(self.ui.text_log.verticalScrollBar().maximum())

    def safe_set_scroll(self, val): self.ui_lock = True; self.ui.text_log.verticalScrollBar().setValue(val); self.ui_lock = False

    def scan_ports(self):
        self.ui.cb_port.clear(); ports = list(serial.tools.list_ports.comports())
        if not ports: self.ui.cb_port.addItem("无设备")
        else: [self.ui.cb_port.addItem(p.device) for p in ports]

    def on_log_scroll(self, value):
        if getattr(self, 'ui_lock', False) or self.is_fetching_logs: return
        scrollbar = self.ui.text_log.verticalScrollBar()
        if scrollbar.maximum() < 5: return 
        if value <= 2:
            self.is_fetching_logs = True
            if self.log_mode == 'live':
                self.log_mode, self.log_offset = 'history', 1000
                self.ui.btn_rollback.setText("⬇️ 返回最新"); self.ui_lock = True
                self.ui.text_log.document().setMaximumBlockCount(0); self.ui_lock = False
            else: self.log_offset += 1000
            self.fetch_worker.log_queue.put({'offset': self.log_offset, 'direction': 'up'})
        elif value >= scrollbar.maximum() - 2 and self.log_mode == 'history':
            self.is_fetching_logs, self.log_offset = True, self.log_offset - 1000
            if self.log_offset <= 0: self.force_live_mode(); self.is_fetching_logs = False
            else: self.fetch_worker.log_queue.put({'offset': self.log_offset, 'direction': 'down'})

    def on_log_fetched(self, text, success, direction):
        scrollbar = self.ui.text_log.verticalScrollBar()
        if success:
            self.ui_lock = True; self.ui.text_log.blockSignals(True); self.ui.text_log.setPlainText(text); self.ui.text_log.blockSignals(False)
            if direction == 'up': QTimer.singleShot(10, lambda: self.safe_set_scroll(scrollbar.maximum() - 10))
            else:
                if self.log_offset == 0: QTimer.singleShot(10, lambda: self.safe_set_scroll(scrollbar.maximum()))
                else: QTimer.singleShot(10, lambda: self.safe_set_scroll(10))
            self.ui_lock = False
        self.is_fetching_logs = False

    def on_chart_fetched(self, data):
        hx, hp, hvi, hii, hvo, hio, hvb, hib = data
        self.ui.line_power.set_data(hx, hp)
        self.ui.line_v_in.set_data(hx, hvi); self.ui.line_i_in.set_data(hx, hii)
        self.ui.line_v_out.set_data(hx, hvo); self.ui.line_i_out.set_data(hx, hio)
        self.ui.line_v_bat.set_data(hx, hvb); self.ui.line_i_bat.set_data(hx, hib)
        if hx:
            for ax,y,span in [(self.ui.ax_p,hp,1.0),(self.ui.ax_in,hvi,1.0),(self.ui.ax_in_i,hii,0.5),(self.ui.ax_out,hvo,1.0),(self.ui.ax_out_i,hio,0.5),(self.ui.ax_bat,hvb,1.0),(self.ui.ax_bat_i,hib,0.5)]: self.apply_strict_smart_ylim(ax,y,span)
        self.ui.canvas.draw_idle()

    def process_data(self, data):
        self.latest_data = data; t = data['ts'] - self.start_time + self.time_offset
        if self.x_data and t <= self.x_data[-1]: t = self.x_data[-1] + 0.001 
        self.db_worker.queue.put({'type': 'metric', 'rel_time': t, 'data': data})
        self.x_data.append(t); self.y_vi.append(data['v_in']); self.y_ii.append(data['i_in'])
        self.y_vo.append(data['v_out']); self.y_io.append(data['i_out']); self.y_vb.append(data['v_bat']); self.y_ib.append(data['i_bat'])
        self.y_eff.append(data['eff']); self.y_p.append(data['p']); self.y_t.append(data['t']); self.y_b.append(data['b'])
        if len(self.x_data) > 500: [a.pop(0) for a in [self.x_data, self.y_vi, self.y_ii, self.y_vo, self.y_io, self.y_vb, self.y_ib, self.y_eff, self.y_p, self.y_t, self.y_b]]

    def append_log(self, full_msg):
        self.db_worker.queue.put({'type': 'log', 'msg': full_msg})
        self.log_buffer.append(full_msg)
        self.check_and_log_unknown(full_msg)

    def check_and_log_unknown(self, line):
        if "ASK " not in line and "FSK " not in line: 
            return
        try:
            p_type = "ASK" if "ASK " in line else "FSK"
            start = line.find(f"{p_type} ") + 4
            if p_type == "ASK":
                end = line.find(" F ", start)
                hex_str = line[start:end].strip() if end != -1 else line[start:].strip()
            else:
                end = line.find("(", start)
                hex_str = line[start:end].strip() if end != -1 else line[start:].strip()
            
            raw = [int(x, 16) for x in hex_str.replace('0x','').replace(',',' ').split() if x.isalnum()]
            if not raw: return
            header = raw[0]
            
            is_unknown = False
            if p_type == "ASK":
                name, _ = self.ask_qi22_map(header, []) 
                if name.startswith("UNK_"): is_unknown = True
            else:
                name, _ = self.fsk_qi22_map(header, [])
                if name.startswith("UNK_"): is_unknown = True
                
            if is_unknown:
                if not hasattr(self, '_unknown_cmd_cache'): self._unknown_cmd_cache = set()
                cache_key = f"{p_type}_0x{header:02X}"
                if cache_key not in self._unknown_cmd_cache:
                    self._unknown_cmd_cache.add(cache_key)
                    log_file = "Unknown_Qi_Commands_Log.txt"
                    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    with open(log_file, "a", encoding="utf-8-sig") as f:
                        if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
                            f.write("=== Qi 2.2.1 未知指令拦截对照表 ===\n\n")
                        f.write(f"[{ts}] 发现未知 {p_type} | Header: 0x{header:02X} | 示例: {hex_str}\n")
        except Exception: pass

    def request_chart_fetch(self):
        if not self.auto_scroll_chart: self.fetch_worker.latest_xlim, self.fetch_worker.chart_request = self.ui.ax_p.get_xlim(), True

    def toggle_log_mode(self):
        if self.log_mode == 'live':
            self.log_mode, self.log_offset = 'history', 0
            self.ui.btn_rollback.setText("⬇️ 返回最新"); self.ui_lock = True
            self.ui.text_log.document().setMaximumBlockCount(0); self.ui_lock = False; self.on_log_scroll(0)
        else: self.force_live_mode()

    def export_tx0_logs(self):
        p, _ = QFileDialog.getSaveFileName(self, "导出报文日志", "Logs.txt", "Text Files (*.txt)")
        if p:
            try:
                c = sqlite3.connect('charging_data.db'); r = c.execute("SELECT message FROM tx0_logs ORDER BY id ASC").fetchall(); c.close()
                with open(p, 'w', encoding='utf-8-sig') as f:
                    for row in r: f.write(row[0] + '\n')
                QMessageBox.information(self, "成功", f"导出 {len(r)} 条记录！")
            except: pass

    def on_chart_scroll(self, event):
        if event.inaxes is None: return
        self.auto_scroll_chart = False; cur_xlim = self.ui.ax_p.get_xlim(); scale = 0.8 if event.button == 'up' else 1.2
        new_w = (cur_xlim[1] - cur_xlim[0]) * scale
        self.ui.ax_p.set_xlim([event.xdata - new_w * (event.xdata - cur_xlim[0]) / (cur_xlim[1] - cur_xlim[0]), event.xdata + new_w * (1 - (event.xdata - cur_xlim[0]) / (cur_xlim[1] - cur_xlim[0]))])
        self.request_chart_fetch() 

    def on_chart_press(self, event):
        if event.inaxes is None or event.button != 1: return
        if event.dblclick: self.auto_scroll_chart = True; self.ui.canvas.draw_idle(); return
        self.auto_scroll_chart, self.is_dragging, self.press_x, self.orig_xlim = False, True, event.xdata, self.ui.ax_p.get_xlim()

    def on_chart_motion(self, event):
        if self.is_dragging and event.xdata: dx = event.xdata - self.press_x; self.ui.ax_p.set_xlim([self.orig_xlim[0]-dx, self.orig_xlim[1]-dx]); self.ui.canvas.draw_idle(); self.request_chart_fetch() 

    def on_chart_release(self, event): self.is_dragging = False; self.request_chart_fetch()

    def closeEvent(self, event):
        self.stop_mon()
        if hasattr(self, 'db_worker'): self.db_worker.stop()
        if hasattr(self, 'fetch_worker'): self.fetch_worker.stop()
        event.accept()

if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True); app = QApplication(sys.argv); win = MonitorWindow(); win.show(); sys.exit(app.exec_())