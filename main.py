# ==========================================
# Project: 手机无线充电监控系统 (专业工业级上位机)
# Author: Roy Zhao @ 御风智联
# Date: 2026-04-14 (v3.0 Final - 全功能完美集成版)
# ==========================================
import sys, time, datetime, sqlite3, serial, csv, os, math, re, json, bisect
import queue
import traceback
import serial.tools.list_ports
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog, QToolTip, QSizePolicy, QLabel, QTextEdit
from PyQt5.QtGui import QCursor, QTextCursor, QTextCharFormat, QColor  
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QEvent
from ui_monitor import Ui_MonitorWindow
import pyqtgraph as pg
import pyqtgraph.exporters 

# PDF 报表生成引擎
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

from qi_parser import Qi22Parser

def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            "system": {"db_name": "charging_data.db"},
            "ui": {"render_interval_ms": 100, "chart_max_points": 500, "default_window_size_sec": 60.0},
            "alerts": {"temp_warning_threshold": 60, "temp_recovery_threshold": 55, "ovp_threshold": 25.0, "ocp_threshold": 3.0, "full_charge_debounce_sec": 20.0},
            "serial": {"default_baudrates": ["115200", "921600", "2000000"]}
        }

CONFIG = load_config()

def init_db():
    db_name = CONFIG['system']['db_name']
    conn = sqlite3.connect(db_name)
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
                        rel_time REAL,
                        message TEXT)''')
    try: cursor.execute('ALTER TABLE tx0_logs ADD COLUMN rel_time REAL')
    except: pass
    try: cursor.execute('CREATE INDEX idx_tx0_rel_time ON tx0_logs(rel_time)')
    except: pass
    
    conn.commit(); conn.close()

# ================== 核心报表引擎 ==================
class ReportEngine:
    @staticmethod
    def generate(filename, summary_data, alert_logs, chart_images):
        c = canvas.Canvas(filename, pagesize=A4)
        w, h = A4
        
        # 1. 标题与分割线
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(w/2, h - 50, "Wireless Charging Test Analysis Report")
        c.setStrokeColor(colors.dodgerblue)
        c.line(50, h - 60, w - 50, h - 60)
        
        # 2. 基础元数据
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, h - 90, "1. Test Execution Summary")
        c.setFont("Helvetica", 11)
        y = h - 110
        items = [
            f"Test Start Time: {summary_data['start']}",
            f"Test End Time:   {summary_data['end']}",
            f"Total Duration:  {summary_data['duration']}",
            f"Total Samples:   {summary_data['samples']} points",
            f"Max Output Pwr:  {summary_data['max_p']:.2f} W",
            f"Peak Temperature: {summary_data['max_t']:.1f} C"
        ]
        for item in items:
            c.drawString(70, y, item); y -= 18
            
        # 3. 异常监控日志
        y -= 20
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "2. Safety Alerts & Protection Events")
        y -= 20
        c.setFont("Helvetica", 10)
        if not alert_logs:
            c.setFillOpacity(0.5)
            c.drawString(70, y, "No critical alerts triggered during this session.")
            c.setFillOpacity(1.0); y -= 20
        else:
            c.setFillColor(colors.red)
            for log in alert_logs[:8]:
                c.drawString(70, y, f"• {log}"); y -= 15
            c.setFillColor(colors.black)
            if len(alert_logs) > 8:
                c.drawString(70, y, f"... and {len(alert_logs)-8} more events (see full log)."); y -= 15

        # 4. 波形图渲染
        y -= 30
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "3. Complete Cycle Waveforms")
        
        # 第一页图表
        chart_positions = [[50, h/2 - 20, 500, 200], [50, h/2 - 240, 500, 200]]
        for i, img_path in enumerate(chart_images[:2]):
            if os.path.exists(img_path): c.drawImage(img_path, *chart_positions[i], preserveAspectRatio=True)
        
        c.showPage() 
        
        # 第二页图表
        chart_positions_p2 = [[50, h - 250, 500, 200], [50, h - 480, 500, 200]]
        for i, img_path in enumerate(chart_images[2:]):
            if os.path.exists(img_path): c.drawImage(img_path, *chart_positions_p2[i], preserveAspectRatio=True)

        c.setFont("Helvetica-Oblique", 9)
        c.drawRightString(w - 50, 30, f"Generated by Yufeng Zhilian Monitoring System - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
        c.save()

# ================== 异步工作线程 ==================
class DBWorker(QThread):
    def __init__(self):
        super().__init__(); self.queue = queue.Queue(); self.running = True
        self.db_name = CONFIG['system']['db_name']
        
    def run(self):
        conn = sqlite3.connect(self.db_name, check_same_thread=False); conn.execute('PRAGMA journal_mode=WAL;')
        cur = conn.cursor()
        while self.running:
            try:
                task = self.queue.get(timeout=0.1) 
                if task['type'] == 'metric':
                    d = task['data']
                    cur.execute("INSERT INTO charging_metrics (rel_time, v_in, i_in, v_out, i_out, v_bat, i_bat, eff, power, temp, battery) VALUES (?,?,?,?,?,?,?,?,?,?,?)", 
                                (task['rel_time'], d['v_in'], d['i_in'], d['v_out'], d['i_out'], d['v_bat'], d['i_bat'], d['eff'], d['p'], d['t'], d['b']))
                elif task['type'] == 'log':
                    cur.execute("INSERT INTO tx0_logs (rel_time, message) VALUES (?, ?)", (task.get('rel_time', 0.0), task['msg']))
                if self.queue.empty(): conn.commit()
            except queue.Empty: continue
            except Exception: pass
        try: conn.commit() 
        except: pass
        conn.close()
    def stop(self): self.running = False; self.wait()

class FetchWorker(QThread):
    chart_fetched = pyqtSignal(tuple)
    log_fetched = pyqtSignal(str, bool, str) 
    def __init__(self):
        super().__init__(); self.running = True; self.log_queue = queue.Queue()
        self.latest_xlim = None; self.chart_request = False; self.db_name = CONFIG['system']['db_name']

    def run(self):
        conn = sqlite3.connect(self.db_name, check_same_thread=False); conn.execute('PRAGMA journal_mode=WAL;')
        cur = conn.cursor()
        while self.running:
            if self.chart_request and self.latest_xlim:
                self.chart_request = False; xlim = self.latest_xlim; margin = (xlim[1] - xlim[0]) * 0.1
                try:
                    cur.execute('''SELECT rel_time, power, v_in, i_in, v_out, i_out, v_bat, i_bat, temp, battery 
                                   FROM charging_metrics WHERE rel_time BETWEEN ? AND ? ORDER BY rel_time ASC''', (xlim[0]-margin, xlim[1]+margin))
                    rows = cur.fetchall()
                    if rows:
                        if len(rows) > 2000: step = len(rows) // 2000; rows = rows[::step]
                        self.chart_fetched.emit(tuple(zip(*rows)))
                    else: self.chart_fetched.emit(([],[],[],[],[],[],[],[],[],[]))
                except Exception: pass
            try:
                log_task = self.log_queue.get(timeout=0.05)
                r = cur.execute("SELECT message FROM (SELECT id, message FROM tx0_logs ORDER BY id DESC LIMIT 1000 OFFSET ?) ORDER BY id ASC", (log_task['offset'],)).fetchall()
                if r: self.log_fetched.emit("\n".join([row[0] for row in r]), True, log_task['direction'])
                else: self.log_fetched.emit("", False, log_task['direction'])
            except queue.Empty: pass
        conn.close()
    def stop(self): self.running = False; self.wait()

class SerialWorker(QThread):
    data_ready = pyqtSignal(dict); log_ready = pyqtSignal(float, str) 
    KNOWN_ASK = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x09, 0x22, 0x31, 0x51, 0x71, 0x13, 0x18, 0x19, 0x1A, 0x1B, 0x20, 0x23, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x36, 0x37, 0x38, 0x39, 0x46, 0x47, 0x48, 0x49, 0x50, 0x56, 0x57, 0x58, 0x59, 0x66, 0x67, 0x78, 0x76, 0x77, 0x79, 0x81, 0x84, 0x85, 0x88, 0x90, 0x96, 0xA8}
    KNOWN_FSK = {0x00, 0x55, 0x33, 0xFF, 0x01, 0x0A, 0x14, 0x1C, 0x1B, 0x1D, 0x1E, 0x1F, 0x23, 0x26, 0x27, 0x2C, 0x2D, 0x2E, 0x2F, 0x34, 0x36, 0x37, 0x3E, 0x3F, 0x40, 0x43, 0x46, 0x47, 0x4E, 0x4F, 0x54, 0x56, 0x57, 0x5A, 0x5E, 0x5F, 0x61, 0x66, 0x67, 0x76, 0x77, 0x88, 0x8E, 0x8F, 0xA0}

    def __init__(self, port, baudrate):
        super().__init__(); self.port = port; self.baudrate = baudrate; self.running = True
        self.last_log_time = datetime.datetime.now(); self._unknown_cmd_cache = set()

    def get_strict_timestamp(self):
        now = datetime.datetime.now()
        if now <= self.last_log_time: now = self.last_log_time + datetime.timedelta(milliseconds=1)
        self.last_log_time = now
        return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"
        
    def run(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=0)
            self.serial_conn.reset_input_buffer()
        except Exception:
            while self.running:
                time.sleep(0.05); t = time.time(); ts = self.get_strict_timestamp()
                self.parse_line(f"AA55:9000:1500:8500:1400:4000:3000:45:80:EDED")
                if int(t)%3==0: msg = f"{ts} ASK 51 3E 00 00 00 00 F "
                elif int(t)%3==1: msg = f"{ts} ASK 71 22 12 34 00 00 00 00 F "
                else: msg = f"{ts} FSK 40 03 F"
                self.log_ready.emit(time.time(), msg); self.check_and_log_unknown(msg)
            return
            
        buffer = ""
        while self.running:
            try:
                waiting = self.serial_conn.in_waiting
                if waiting > 0:
                    buffer += self.serial_conn.read(waiting).decode('ascii', errors='ignore')
                    while "AA55" in buffer and "EDED" in buffer:
                        start = buffer.find("AA55"); end = buffer.find("EDED", start)
                        if end != -1: 
                            self.parse_line(buffer[start:end+4]); buffer = buffer[end+4:] 
                        else: buffer = buffer[start:]; break 
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1) 
                        line = line.strip()
                        if line.startswith("TX0"):
                            msg = f"{self.get_strict_timestamp()} {line[3:].strip().strip(':').strip()}"
                            self.log_ready.emit(time.time(), msg); self.check_and_log_unknown(msg)
                        elif "AA55" in line and "EDED" in line: self.parse_line(line)
                else: time.sleep(0.001)
            except: break

    def parse_line(self, line):
        try:
            p = line[line.find("AA55"):line.find("EDED")+4].split(':')
            if len(p) == 10:
                v_in, i_in, v_out, i_out, v_bat, i_bat = [float(x)/1000 for x in p[1:7]]
                p_out = v_out * i_out; p_bat = v_bat * i_bat
                eff = min(100.0, (p_bat/p_out*100.0) if p_out > 0.1 else 0.0)
                self.data_ready.emit({'ts':time.time(),'v_in':v_in,'i_in':i_in,'v_out':v_out,'i_out':i_out,'v_bat':v_bat,'i_bat':i_bat,'eff':eff,'p':p_out,'t':int(p[7]),'b':int(p[8])})
        except: pass
        
    def check_and_log_unknown(self, line):
        if "ASK " not in line and "FSK " not in line: return
        try:
            p_type = "ASK" if "ASK " in line else "FSK"; start = line.find(f"{p_type} ") + 4
            end = line.find(" F ", start) if p_type == "ASK" else line.find("(", start)
            hex_str = line[start:end].strip() if end != -1 else line[start:].strip()
            raw = [int(x, 16) for x in hex_str.replace('0x','').replace(',',' ').split() if x.isalnum()]
            if not raw: return
            if (p_type == "ASK" and raw[0] not in self.KNOWN_ASK) or (p_type == "FSK" and raw[0] not in self.KNOWN_FSK):
                cache_key = f"{p_type}_0x{raw[0]:02X}"
                if cache_key not in self._unknown_cmd_cache:
                    self._unknown_cmd_cache.add(cache_key)
                    with open("Unknown_Qi_Commands_Log.txt", "a", encoding="utf-8-sig") as f:
                        if not os.path.exists("Unknown_Qi_Commands_Log.txt") or os.path.getsize("Unknown_Qi_Commands_Log.txt") == 0:
                            f.write("=== Qi 2.2.1 未知指令拦截对照表 ===\n\n")
                        f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] 发现未知 {p_type} | Header: 0x{raw[0]:02X} | 示例: {hex_str}\n")
        except: pass
    def stop(self): self.running = False; self.wait()

# ================== 主窗口交互与控制中心 ==================
class MonitorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MonitorWindow()
        self.ui.setupUi(self)
        init_db()
        
        self.qi_parser = Qi22Parser()
        self._active_alerts = set() 
        self._last_cc_cv_state = ""
        self._full_charge_start_time = None
        self._full_charge_alerted = False
        
        for name, min_w in [('cb_port', 150), ('cb_baudrate', 120), ('btn_start', 100), ('btn_stop', 100)]:
            if hasattr(self.ui, name):
                widget = getattr(self.ui, name)
                widget.setMinimumWidth(min_w)
                widget.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
                
        self.worker = None 
        self.x_data, self.y_vi, self.y_ii, self.y_vo, self.y_io, self.y_vb, self.y_ib, self.y_eff, self.y_p, self.y_t, self.y_b = [],[],[],[],[],[],[],[],[],[],[]
        self.latest_data, self.start_time, self.time_offset = None, 0.0, 0.0
        self.view_data = {'x':[], 'p':[], 'vi':[], 'ii':[], 'vo':[], 'io':[], 'vb':[], 'ib':[], 't':[], 'b':[]}
        self.auto_scroll_chart, self.log_mode, self.log_offset, self.is_fetching_logs = True, 'live', 0, False
        self.log_buffer, self.ui_lock, self.last_hovered_line = [], False, -1
        
        self.db_worker = DBWorker(); self.db_worker.start()
        self.fetch_worker = FetchWorker(); self.fetch_worker.chart_fetched.connect(self.on_chart_fetched)
        self.fetch_worker.log_fetched.connect(self.on_log_fetched); self.fetch_worker.start()
        
        self.setup_crosshair()
        
        self.timer = QTimer(self); self.timer.timeout.connect(self.render_ui); self.timer.start(CONFIG['ui']['render_interval_ms'])
        self.log_interaction_timer = QTimer(self); self.log_interaction_timer.setSingleShot(True); self.log_interaction_timer.timeout.connect(self.force_live_mode)
        
        self.ui.text_log.setMouseTracking(True); self.ui.text_log.viewport().setMouseTracking(True)
        self.ui.text_log.viewport().installEventFilter(self); self.ui.text_log.verticalScrollBar().installEventFilter(self)
        
        self.ui.btn_start.clicked.connect(self.start_mon); self.ui.btn_stop.clicked.connect(self.stop_mon)
        self.ui.btn_export.clicked.connect(self.export_csv)
        self.ui.btn_rollback.clicked.connect(self.toggle_log_mode); self.ui.btn_export_log.clicked.connect(self.export_tx0_logs)
        self.ui.text_log.verticalScrollBar().valueChanged.connect(self.on_log_scroll)

        # 🟢 防御性编程：兼容用户可能忘了在 UI 文件加按钮的情况
        if hasattr(self.ui, 'btn_report'): 
            self.ui.btn_report.clicked.connect(self.export_pdf_report)

        self.ui.p_p.vb.sigRangeChanged.connect(self.on_chart_manual_interaction)
        self.ui.graph_widget.scene().sigMouseClicked.connect(self.on_chart_double_clicked)

        self.scan_ports(); self.auto_scroll_chart = False
        try:
            conn = sqlite3.connect(CONFIG['system']['db_name']); max_t = conn.execute("SELECT MAX(rel_time) FROM charging_metrics").fetchone()[0]; conn.close()
            if max_t: 
                self.ui.p_p.setXRange(max_t-60, max_t+5, padding=0)
                self.fetch_worker.latest_xlim = [max_t-60, max_t+5]
                self.fetch_worker.chart_request = True
        except: pass

    # ========================== 核心扩展功能区 ==========================
    def export_pdf_report(self):
        filename, _ = QFileDialog.getSaveFileName(self, "导出 PDF 测试报告", f"Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf", "PDF Files (*.pdf)")
        if not filename: return
        try:
            conn = sqlite3.connect(CONFIG['system']['db_name']); cur = conn.cursor()
            cur.execute("SELECT MIN(timestamp), MAX(timestamp), MAX(rel_time), COUNT(*), MAX(power), MAX(temp) FROM charging_metrics")
            summary_res = cur.fetchone()
            
            cur.execute("SELECT message FROM tx0_logs WHERE message LIKE '%🚨%' OR message LIKE '%⚠️%' ORDER BY id ASC")
            alert_logs = [r[0] for r in cur.fetchall()]
            conn.close()

            if not summary_res or summary_res[0] is None:
                QMessageBox.warning(self, "提示", "当前数据库为空，无法生成报告！"); return

            summary_data = {
                "start": summary_res[0], "end": summary_res[1], 
                "duration": f"{summary_res[2]:.2f} s", "samples": summary_res[3],
                "max_p": summary_res[4] or 0.0, "max_t": summary_res[5] or 0.0
            }

            temp_imgs = []; plot_configs = [(self.ui.p_p, "power_full.png"), (self.ui.p_in, "input_full.png"), (self.ui.p_out, "output_full.png"), (self.ui.p_bat, "battery_full.png")]
            
            # 全量视图截图渲染
            for plot, img_name in plot_configs:
                plot.enableAutoRange() 
                exporter = pg.exporters.ImageExporter(plot); exporter.parameters()['width'] = 1200
                exporter.export(img_name); temp_imgs.append(img_name)

            ReportEngine.generate(filename, summary_data, alert_logs, temp_imgs)
            for img in temp_imgs: 
                if os.path.exists(img): os.remove(img)
            
            QMessageBox.information(self, "成功", f"报告已生成至：\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"报告生成过程中发生错误：\n{str(e)}"); traceback.print_exc()

    def show_full_charge_alert(self, debounce_sec):
        ts_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self.append_log(time.time(), f"[{ts_str}] 🎉 提示：充电已完成 (稳定维持涓流状态 {debounce_sec} 秒)！")
        self.msg_full_charge = QMessageBox(self); self.msg_full_charge.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.msg_full_charge.setIcon(QMessageBox.Information); self.msg_full_charge.setWindowTitle("充电完成 🔋")
        self.msg_full_charge.setText("<h3>🎉 充电已完成！</h3>")
        self.msg_full_charge.setInformativeText(f"设备已稳定维持涓流满电状态 {debounce_sec} 秒。<br><span style='color:#94A3B8;'>本提示将在 10 秒后自动关闭。</span>")
        self.msg_full_charge.setStandardButtons(QMessageBox.Ok); self.msg_full_charge.show()
        QTimer.singleShot(10000, self.close_full_charge_alert)

    def close_full_charge_alert(self):
        if hasattr(self, 'msg_full_charge') and self.msg_full_charge.isVisible(): self.msg_full_charge.accept()

    def sync_log_to_time(self, target_time):
        if self.auto_scroll_chart:
            self.auto_scroll_chart = False; self.ui.btn_start.setText("⏸ 历史浏览 (点击恢复)"); self.request_chart_fetch()
        self.log_mode = 'history_jump'; self.ui.btn_rollback.setText("⬇️ 返回最新")
        try:
            conn = sqlite3.connect(CONFIG['system']['db_name']); cur = conn.cursor()
            cur.execute("SELECT id, message FROM tx0_logs WHERE rel_time IS NOT NULL ORDER BY ABS(rel_time - ?) LIMIT 1", (target_time,))
            res = cur.fetchone()
            if not res: conn.close(); return
            target_id, target_msg = res; start_id = max(0, target_id - 500)
            cur.execute("SELECT message FROM tx0_logs WHERE id >= ? AND id <= ? ORDER BY id ASC", (start_id, target_id + 500))
            rows = cur.fetchall(); conn.close()
            if rows:
                log_text = "\n".join([r[0] for r in rows])
                self.ui_lock = True; self.ui.text_log.blockSignals(True); self.ui.text_log.document().setMaximumBlockCount(0) 
                self.ui.text_log.setPlainText(log_text); self.ui.text_log.blockSignals(False); self.ui_lock = False
                self.log_offset = start_id
                QTimer.singleShot(50, lambda: self.highlight_log(target_msg))
        except Exception: pass

    def highlight_log(self, target_msg):
        doc = self.ui.text_log.document(); cursor = self.ui.text_log.textCursor(); cursor.setPosition(0)
        found_cursor = doc.find(target_msg, cursor)
        if not found_cursor.isNull():
            self.ui.text_log.setTextCursor(found_cursor); self.ui.text_log.centerCursor() 
            selection = QTextEdit.ExtraSelection(); selection.format.setBackground(QColor("#0284C7")); selection.format.setForeground(QColor("#FFFFFF"))
            selection.cursor = found_cursor; selection.cursor.select(QTextCursor.BlockUnderCursor)
            self.ui.text_log.setExtraSelections([selection]); QTimer.singleShot(3000, lambda: self.ui.text_log.setExtraSelections([]))

    # ========================== 基础生命周期区 ==========================
    def append_log(self, ts, msg):
        self.log_buffer.append(msg)
        if hasattr(self, 'db_worker'): 
            t = (ts - self.start_time + self.time_offset) if self.start_time > 0 else 0.0
            self.db_worker.queue.put({'type': 'log', 'rel_time': t, 'msg': msg})

    def setup_crosshair(self):
        self.v_lines = []
        for p in [self.ui.p_p, self.ui.p_in, self.ui.p_out, self.ui.p_bat]:
            v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color='#38BDF8', width=1.5, style=Qt.DashLine))
            v_line.setVisible(False); p.addItem(v_line, ignoreBounds=True)
            self.v_lines.append(v_line)
        self.hud_label = QLabel(); self.hud_label.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint); self.hud_label.setAttribute(Qt.WA_TranslucentBackground) 
        self.hud_label.setStyleSheet("QLabel { background-color: rgba(15, 23, 42, 240); color: #CBD5E1; border: 1px solid #38BDF8; border-radius: 6px; padding: 10px; font-family: Consolas, monospace; }")
        self.hud_label.hide()
        self.proxy = pg.SignalProxy(self.ui.graph_widget.scene().sigMouseMoved, rateLimit=60, slot=self.on_mouse_moved)

    def hide_tooltip(self):
        if hasattr(self, 'hud_label') and self.hud_label.isVisible(): self.hud_label.hide()
        if hasattr(self, 'v_lines'):
            for line in self.v_lines: line.setVisible(False)

    def on_mouse_moved(self, evt):
        try:
            pos = evt[0]
            if self.auto_scroll_chart or not getattr(self, 'view_data', {}).get('x'):
                self.hide_tooltip(); return
            mouse_point = None; active_p = None
            for p in [self.ui.p_p, self.ui.p_in, self.ui.p_out, self.ui.p_bat]:
                if p.sceneBoundingRect().contains(pos): mouse_point = p.vb.mapSceneToView(pos); active_p = p; break
            if mouse_point and active_p:
                x_val = mouse_point.x(); x_arr = self.view_data['x']
                idx = bisect.bisect_left(x_arr, x_val); idx = max(0, min(idx, len(x_arr) - 1))
                if idx > 0 and abs(x_val - x_arr[idx-1]) < abs(x_val - x_arr[idx]): idx = idx - 1
                closest_x = x_arr[idx]
                try: p_val, vi_val, ii_val, vo_val, io_val, vb_val, ib_val = self.view_data['p'][idx], self.view_data['vi'][idx], self.view_data['ii'][idx], self.view_data['vo'][idx], self.view_data['io'][idx], self.view_data['vb'][idx], self.view_data['ib'][idx]
                except IndexError: self.hide_tooltip(); return
                for line in self.v_lines: line.setPos(closest_x); line.setVisible(True)
                html = f"<div style='font-size: 10pt; line-height: 1.4;'><b style='color:#F8FAFC; font-size: 11pt;'>⏱ {closest_x:.2f} s</b><hr style='border: 1px solid #334155; margin: 4px 0;'>"
                if active_p == self.ui.p_p: html += f"<b>PWR:</b> <span style='color:#A855F7'>{p_val:.2f} W</span>"
                elif active_p == self.ui.p_in: html += f"<b>IN :</b> <span style='color:#FACC15'>{vi_val:.2f} V</span> / <span style='color:#22C55E'>{ii_val:.2f} A</span>"
                elif active_p == self.ui.p_out: html += f"<b>OUT:</b> <span style='color:#FACC15'>{vo_val:.2f} V</span> / <span style='color:#22C55E'>{io_val:.2f} A</span>"
                elif active_p == self.ui.p_bat: html += f"<b>BAT:</b> <span style='color:#FACC15'>{vb_val:.2f} V</span> / <span style='color:#22C55E'>{ib_val:.2f} A</span>"
                self.hud_label.setText(html + "</div>"); self.hud_label.adjustSize(); self.hud_label.move(QCursor.pos().x() + 15, QCursor.pos().y() + 15); self.hud_label.show()
            else: self.hide_tooltip()
        except Exception: self.hide_tooltip()

    def adjust_panel_widths(self):
        try:
            current_screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
            w = current_screen.geometry().width()
            if hasattr(self.ui, 'splitter'): self.ui.splitter.setSizes([int(w * 3 / 20), int(w * 11 / 20), w - int(w * 3 / 20) - int(w * 11 / 20)])
        except Exception: pass

    def showEvent(self, event): super().showEvent(event); getattr(self, '_initial_layout_done', self.adjust_panel_widths())

    def export_csv(self):
        p, _ = QFileDialog.getSaveFileName(self, "导出表格数据", f"Qi_Monitor_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "CSV (*.csv)")
        if p:
            try:
                conn = sqlite3.connect(CONFIG['system']['db_name']); r = conn.execute("SELECT timestamp, v_in, i_in, v_out, i_out, v_bat, i_bat, eff, power, temp, battery FROM charging_metrics ORDER BY rel_time ASC").fetchall(); conn.close()
                with open(p, 'w', newline='', encoding='utf-8-sig') as f:
                    csv.writer(f).writerow(["时间戳","Vin","Iin","Vout","Iout","Vbat","Ibat","效率","功率","温度","电量"]); csv.writer(f).writerows(r)
                QMessageBox.information(self, "成功", "数据导出成功！")
            except Exception as e: QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def eventFilter(self, obj, event):
        if obj == self.ui.text_log.viewport():
            if event.type() == QEvent.MouseMove:
                if self.worker and self.worker.isRunning() and self.auto_scroll_chart:
                    self.log_interaction_timer.start(3000); QToolTip.hideText()
                else:
                    cursor = self.ui.text_log.cursorForPosition(event.pos())
                    if cursor.blockNumber() != self.last_hovered_line:
                        self.last_hovered_line = cursor.blockNumber()
                        info = self.qi_parser.parse_message(cursor.block().text())
                        if info: QToolTip.showText(event.globalPos(), info, self.ui.text_log)
                        else: QToolTip.hideText()
            elif event.type() == QEvent.Leave: QToolTip.hideText(); self.last_hovered_line = -1
        return super().eventFilter(obj, event)

    def show_protection_alert(self, alert_type, trigger_val, threshold_val, unit):
        ts_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self.append_log(time.time(), f"[{ts_str}] 🚨 硬件保护触发：{alert_type}！当前值 {trigger_val:.2f}{unit}，安全阈值 {threshold_val:.2f}{unit}")
        msg = QMessageBox(self); msg.setIcon(QMessageBox.Critical); msg.setWindowTitle("硬件保护触发 🚨")
        msg.setText(f"<h3>{alert_type}</h3>")
        msg.setInformativeText(f"系统检测到危险参数，请检查测试环境！<br><br><b>当前触发值:</b> <span style='color:#EF4444;'>{trigger_val:.2f} {unit}</span><br><b>系统安全阈值:</b> {threshold_val:.2f} {unit}")
        msg.setStandardButtons(QMessageBox.Ok); msg.exec_() 

    def render_ui(self):
        if self.log_buffer:
            if self.log_mode == 'live': self.ui_lock = True; self.ui.text_log.appendPlainText("\n".join(self.log_buffer)); self.ui_lock = False
            self.log_buffer.clear()
        if self.latest_data:
            d = self.latest_data
            for lcd, val in [(self.ui.lcd_v_in, d['v_in']),(self.ui.lcd_i_in, d['i_in']),(self.ui.lcd_v_out, d['v_out']),(self.ui.lcd_i_out, d['i_out']),(self.ui.lcd_power, d['p']),(self.ui.lcd_v_bat, d['v_bat']),(self.ui.lcd_i_bat, d['i_bat']),(self.ui.lcd_battery, d['b']),(self.ui.lcd_temp, d['t'])]: lcd.display(f"{val:.2f}" if isinstance(val, float) else f"{val}")
            
            ovp = CONFIG['alerts'].get('ovp_threshold', 25.0); ocp = CONFIG['alerts'].get('ocp_threshold', 3.0); temp_w = CONFIG['alerts'].get('temp_warning_threshold', 60); temp_r = CONFIG['alerts'].get('temp_recovery_threshold', 55)
            max_v = max(d['v_in'], d['v_out'])
            if max_v >= ovp:
                if 'OVP' not in self._active_alerts: self._active_alerts.add('OVP'); self.show_protection_alert("过压保护 (OVP)", max_v, ovp, "V")
            elif max_v < ovp - 1.0: self._active_alerts.discard('OVP')

            max_i = max(d['i_in'], d['i_out'])
            if max_i >= ocp:
                if 'OCP' not in self._active_alerts: self._active_alerts.add('OCP'); self.show_protection_alert("过流保护 (OCP)", max_i, ocp, "A")
            elif max_i < ocp - 0.2: self._active_alerts.discard('OCP')

            if d['t'] >= temp_w:
                self.ui.lcd_temp.setStyleSheet("color: #EF4444; background-color: #450a0a; border: 2px solid #EF4444;")
                if not getattr(self, '_temp_warned', False): self.append_log(time.time(), f"[{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]}] ⚠️ 警告：线圈温度过高 ({d['t']}°C)！"); self._temp_warned = True
                if 'OTP' not in self._active_alerts: self._active_alerts.add('OTP'); self.show_protection_alert("过温保护 (OTP)", d['t'], temp_w, "°C")
            else:
                self.ui.lcd_temp.setStyleSheet("color: #FB923C; background-color: #0D1117; border: 1px solid #334155;")
                if d['t'] < temp_r: self._temp_warned = False; self._active_alerts.discard('OTP')
                    
            if len(self.y_vb) >= 20: 
                curr_p = d['p']; curr_v = d['v_bat']; curr_i = d['i_bat']
                if curr_p < 0.5: state_text = "🔌 未充电 / 待机中"; color = "#94A3B8"; border_style = "dashed"
                else:
                    border_style = "solid"; dv = curr_v - self.y_vb[-20]; di = curr_i - self.y_ib[-20]
                    if curr_i < 0.15: state_text = "🟢 涓流阶段 / 已满电"; color = "#10B981"
                    elif abs(dv) <= 0.05 and di < -0.05: state_text = "🟡 恒压充电阶段 (CV)"; color = "#FACC15"
                    elif dv > 0.02 and abs(di) <= 0.1: state_text = "🔵 恒流充电阶段 (CC)"; color = "#38BDF8"
                    else: state_text = "🔄 动态功率协商中..."; color = "#A855F7"
                
                if self._last_cc_cv_state != state_text:
                    self.ui.lbl_charge_state.setText(state_text); self.ui.lbl_charge_state.setStyleSheet(f"background-color: #0F172A; color: {color}; border: 2px {border_style} {color}; border-radius: 6px; padding: 10px; font-size: 11pt; font-weight: bold; margin-bottom: 5px;")
                    self._last_cc_cv_state = state_text

                if state_text == "🟢 涓流阶段 / 已满电":
                    if self._full_charge_start_time is None: self._full_charge_start_time = time.time()
                    else:
                        debounce = CONFIG['alerts'].get('full_charge_debounce_sec', 20.0)
                        if not self._full_charge_alerted and (time.time() - self._full_charge_start_time >= debounce): self.show_full_charge_alert(debounce); self._full_charge_alerted = True 
                else: self._full_charge_start_time = None; self._full_charge_alerted = False

        if self.worker and self.worker.isRunning():
            if self.auto_scroll_chart:
                if not self.x_data: return
                self.ui.line_power.setData(self.x_data, self.y_p); self.ui.line_v_in.setData(self.x_data, self.y_vi); self.ui.line_i_in.setData(self.x_data, self.y_ii); self.ui.line_v_out.setData(self.x_data, self.y_vo); self.ui.line_i_out.setData(self.x_data, self.y_io); self.ui.line_v_bat.setData(self.x_data, self.y_vb); self.ui.line_i_bat.setData(self.x_data, self.y_ib)
                self.view_data = {'x': self.x_data, 'p': self.y_p, 'vi': self.y_vi, 'ii': self.y_ii, 'vo': self.y_vo, 'io': self.y_io, 'vb': self.y_vb, 'ib': self.y_ib, 't': self.y_t, 'b': self.y_b}
                cur_t = self.x_data[-1]; win = CONFIG['ui'].get('default_window_size_sec', 60.0)
                xlim = [cur_t-win, cur_t+win*0.05] if cur_t > win else [0, max(cur_t+1, win)]
                self.ui.p_p.setXRange(xlim[0], xlim[1], padding=0)
            else: self.request_chart_fetch()

    def on_chart_fetched(self, data):
        if not data or len(data) < 10 or not data[0]: return 
        hx, hp, hvi, hii, hvo, hio, hvb, hib, ht, hb = data
        self.ui.line_power.setData(hx, hp); self.ui.line_v_in.setData(hx, hvi); self.ui.line_i_in.setData(hx, hii); self.ui.line_v_out.setData(hx, hvo); self.ui.line_i_out.setData(hx, hio); self.ui.line_v_bat.setData(hx, hvb); self.ui.line_i_bat.setData(hx, hib)
        self.view_data = {'x':hx, 'p':hp, 'vi':hvi, 'ii':hii, 'vo':hvo, 'io':hio, 'vb':hvb, 'ib':hib, 't':ht, 'b':hb}

    def start_mon(self):
        if self.ui.cb_port.currentText() == "无设备": return
        if self.worker and self.worker.isRunning():
            self.auto_scroll_chart = True; self.ui.btn_start.setText("▶ 监控中")
            for p in [self.ui.p_p, self.ui.p_in, self.ui.p_out, self.ui.p_bat]: p.enableAutoRange(axis='y')
            self.force_live_mode(); return
        self.ui.btn_start.setEnabled(False); self.ui.btn_stop.setEnabled(True); self.ui.cb_port.setEnabled(False); self.ui.btn_start.setText("▶ 监控中")
        try: conn = sqlite3.connect('charging_data.db'); max_t = conn.execute("SELECT MAX(rel_time) FROM charging_metrics").fetchone()[0]; conn.close(); self.time_offset = (max_t if max_t is not None else 0.0) + 1.0 
        except: self.time_offset = 0.0
        self.start_time, self.ui_lock = time.time(), True; self.ui.text_log.clear(); self.ui_lock = False; self.log_buffer.clear()
        self.auto_scroll_chart, self.log_mode = True, 'live'
        self._temp_warned = False; self._active_alerts.clear(); self._last_cc_cv_state = ""; self._full_charge_start_time = None; self._full_charge_alerted = False
        self.ui.lbl_charge_state.setText("⚡ 数据采集中..."); self.ui.lbl_charge_state.setStyleSheet("background-color: #0F172A; color: #94A3B8; border: 1px dashed #334155; border-radius: 6px; padding: 10px; font-size: 11pt; font-weight: bold; margin-bottom: 5px;")
        [a.clear() for a in [self.x_data, self.y_vi, self.y_ii, self.y_vo, self.y_io, self.y_vb, self.y_ib, self.y_eff, self.y_p, self.y_t, self.y_b]]; self.view_data = {'x':[], 'p':[], 'vi':[], 'ii':[], 'vo':[], 'io':[], 'vb':[], 'ib':[], 't':[], 'b':[]}
        for p in [self.ui.p_p, self.ui.p_in, self.ui.p_out, self.ui.p_bat]: p.enableAutoRange(axis='y')
        self.worker = SerialWorker(self.ui.cb_port.currentText(), int(self.ui.cb_baudrate.currentText())); self.worker.data_ready.connect(self.process_data); self.worker.log_ready.connect(self.append_log); self.worker.start()

    def stop_mon(self):
        self.ui.btn_start.setEnabled(True); self.ui.btn_stop.setEnabled(False); self.ui.cb_port.setEnabled(True); self.ui.btn_start.setText("▶ 开始")
        if self.worker: self.worker.stop(); self.worker = None
        self.log_interaction_timer.stop(); self.auto_scroll_chart = False; self.ui.btn_start.setText("⏸ 历史浏览 (点击恢复)"); self.request_chart_fetch()

    def force_live_mode(self):
        if self.log_mode != 'live': self.log_mode = 'live'; self.log_offset = 0; self.ui.btn_rollback.setText("🔄 历史查阅"); self.ui_lock = True; self.ui.text_log.document().setMaximumBlockCount(1000); self.ui_lock = False

    def safe_set_scroll(self, val): self.ui_lock = True; self.ui.text_log.verticalScrollBar().setValue(val); self.ui_lock = False

    def scan_ports(self):
        self.ui.cb_port.clear(); ports = list(serial.tools.list_ports.comports())
        if not ports: self.ui.cb_port.addItem("无设备")
        else: [self.ui.cb_port.addItem(p.device) for p in ports]
        self.ui.cb_baudrate.clear(); self.ui.cb_baudrate.addItems(CONFIG['serial'].get('default_baudrates', ["115200"]))

    def on_log_scroll(self, value):
        if getattr(self, 'ui_lock', False) or self.is_fetching_logs or getattr(self, 'log_mode', 'live') == 'history_jump': return 
        sb = self.ui.text_log.verticalScrollBar()
        if sb.maximum() < 5: return 
        if value <= 2:
            self.is_fetching_logs = True
            if self.log_mode == 'live': self.log_mode, self.log_offset = 'history', 1000; self.ui.btn_rollback.setText("⬇️ 返回最新"); self.ui_lock = True; self.ui.text_log.document().setMaximumBlockCount(0); self.ui_lock = False
            else: self.log_offset += 1000
            self.fetch_worker.log_queue.put({'offset': self.log_offset, 'direction': 'up'})
        elif value >= sb.maximum() - 2 and self.log_mode == 'history':
            self.is_fetching_logs, self.log_offset = True, self.log_offset - 1000
            if self.log_offset <= 0: self.force_live_mode(); self.is_fetching_logs = False
            else: self.fetch_worker.log_queue.put({'offset': self.log_offset, 'direction': 'down'})

    def on_log_fetched(self, text, success, direction):
        if success:
            self.ui_lock = True; self.ui.text_log.blockSignals(True); self.ui.text_log.setPlainText(text); self.ui.text_log.blockSignals(False)
            target = self.ui.text_log.verticalScrollBar().maximum()-10 if direction=='up' else (self.ui.text_log.verticalScrollBar().maximum() if self.log_offset==0 else 10)
            QTimer.singleShot(10, lambda: self.safe_set_scroll(target)); self.ui_lock = False
        self.is_fetching_logs = False

    def process_data(self, data):
        self.latest_data = data; t = data['ts'] - self.start_time + self.time_offset
        self.db_worker.queue.put({'type': 'metric', 'rel_time': t, 'data': data})
        self.x_data.append(t); self.y_vi.append(data['v_in']); self.y_ii.append(data['i_in']); self.y_vo.append(data['v_out']); self.y_io.append(data['i_out']); self.y_vb.append(data['v_bat']); self.y_ib.append(data['i_bat']); self.y_eff.append(data['eff']); self.y_p.append(data['p']); self.y_t.append(data['t']); self.y_b.append(data['b'])
        if len(self.x_data) > 500: [a.pop(0) for a in [self.x_data, self.y_vi, self.y_ii, self.y_vo, self.y_io, self.y_vb, self.y_ib, self.y_eff, self.y_p, self.y_t, self.y_b]]

    def on_chart_manual_interaction(self, *args, **kwargs):
        xlim = self.ui.p_p.viewRange()[0]
        if self.auto_scroll_chart and hasattr(self, 'last_forced_xlim'):
            if abs(xlim[0] - self.last_forced_xlim[0]) < 0.5: return 
        if self.x_data and xlim[1] >= self.x_data[-1] - max(1.0, (xlim[1]-xlim[0])*0.05):
            if not self.auto_scroll_chart: self.auto_scroll_chart = True; self.ui.btn_start.setText("▶ 监控中")
            return 
        if self.auto_scroll_chart: self.auto_scroll_chart = False; self.ui.btn_start.setText("⏸ 历史浏览 (点击恢复)")
        self.request_chart_fetch()

    def on_chart_double_clicked(self, evt):
        if evt.double():
            pos = evt.scenePos(); mouse_point = None
            for p in [self.ui.p_p, self.ui.p_in, self.ui.p_out, self.ui.p_bat]:
                if p.sceneBoundingRect().contains(pos): mouse_point = p.vb.mapSceneToView(pos); break
            if mouse_point: self.sync_log_to_time(mouse_point.x())

    def request_chart_fetch(self):
        if not self.auto_scroll_chart: self.fetch_worker.latest_xlim, self.fetch_worker.chart_request = self.ui.p_p.viewRange()[0], True

    def toggle_log_mode(self):
        if self.log_mode == 'live': self.log_mode, self.log_offset = 'history', 0; self.ui.btn_rollback.setText("⬇️ 返回最新"); self.ui_lock = True; self.ui.text_log.document().setMaximumBlockCount(0); self.ui_lock = False; self.on_log_scroll(0)
        else: self.force_live_mode()

    def export_tx0_logs(self):
        p, _ = QFileDialog.getSaveFileName(self, "导出报文日志", "Logs.txt", "Text Files (*.txt)")
        if p:
            try: conn = sqlite3.connect(CONFIG['system']['db_name']); r = conn.execute("SELECT message FROM tx0_logs ORDER BY id ASC").fetchall(); conn.close()
            except: return
            with open(p, 'w', encoding='utf-8-sig') as f: [f.write(row[0] + '\n') for row in r]
            QMessageBox.information(self, "成功", f"导出 {len(r)} 条记录！")

    def closeEvent(self, event):
        self.stop_mon(); self.hide_tooltip(); getattr(self, 'db_worker', QThread).stop(); getattr(self, 'fetch_worker', QThread).stop(); event.accept()

if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True); app = QApplication(sys.argv); win = MonitorWindow(); win.show(); sys.exit(app.exec_())