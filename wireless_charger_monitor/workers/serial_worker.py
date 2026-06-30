import datetime
import os
import time

import serial
from PyQt5.QtCore import QThread, pyqtSignal

from ..i18n import tr
from ..logging_setup import logger
from ..paths import project_path

_UNKNOWN_LOG = 'Unknown_Qi_Commands_Log.txt'


class SerialWorker(QThread):
    data_ready = pyqtSignal(dict)
    log_ready = pyqtSignal(float, str)
    connection_failed = pyqtSignal(str)
    connection_opened = pyqtSignal()
    connection_lost = pyqtSignal(str)
    reconnecting = pyqtSignal(int, int)
    KNOWN_ASK = {
        0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x09, 0x15, 0x22, 0x31, 0x51, 0x71,
        0x13, 0x18, 0x19, 0x1A, 0x1B, 0x20, 0x23, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B,
        0x2C, 0x2D, 0x36, 0x37, 0x38, 0x39, 0x46, 0x47, 0x48, 0x49, 0x50, 0x56, 0x57,
        0x58, 0x59, 0x66, 0x67, 0x78, 0x76, 0x77, 0x79, 0x81, 0x84, 0x85, 0x88, 0x90,
        0x96, 0xA8,
    }
    KNOWN_FSK = {
        0x00, 0x55, 0x33, 0xFF, 0x01, 0x0A, 0x11, 0x14, 0x1C, 0x1B, 0x1D, 0x1E, 0x1F,
        0x23, 0x26, 0x27, 0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x34, 0x36, 0x37, 0x3E, 0x3F,
        0x40, 0x43, 0x46, 0x47, 0x4E, 0x4F, 0x54, 0x56, 0x57, 0x5A, 0x5E, 0x5F, 0x61,
        0x66, 0x67, 0x76, 0x77, 0x88, 0x8E, 0x8F, 0xA0,
    }

    def __init__(self, port, baudrate, demo_mode=False, auto_reconnect=True,
                 reconnect_interval=3.0, max_reconnect_attempts=5):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.demo_mode = demo_mode
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.serial_conn = None
        self.last_log_time = datetime.datetime.now()
        self._unknown_cmd_cache = set()
        self._unknown_log_path = project_path(_UNKNOWN_LOG)

    def _open_serial(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=0)
        self.serial_conn.reset_input_buffer()

    def get_strict_timestamp(self):
        now = datetime.datetime.now()
        if now <= self.last_log_time:
            now = self.last_log_time + datetime.timedelta(milliseconds=1)
        self.last_log_time = now
        return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"

    def _run_demo_loop(self):
        logger.warning('Demo mode active on %s — emitting simulated data only', self.port)
        while self.running:
            time.sleep(0.05)
            t = time.time()
            ts = self.get_strict_timestamp()
            self.parse_line('AA55:9000:1500:8500:1400:4000:3000:45:80:EDED')
            if int(t) % 3 == 0:
                msg = f'{ts} ASK 51 3E 00 00 00 00 F '
            elif int(t) % 3 == 1:
                msg = f'{ts} ASK 71 22 12 34 00 00 00 00 F '
            else:
                msg = f'{ts} FSK 40 03 F'
            self.log_ready.emit(time.time(), msg)
            self.check_and_log_unknown(msg)

    def _read_loop(self):
        buffer = ''
        while self.running:
            waiting = self.serial_conn.in_waiting
            if waiting > 0:
                buffer += self.serial_conn.read(waiting).decode('ascii', errors='ignore')
                while 'AA55' in buffer and 'EDED' in buffer:
                    start = buffer.find('AA55')
                    end = buffer.find('EDED', start)
                    if end != -1:
                        self.parse_line(buffer[start:end + 4])
                        buffer = buffer[end + 4:]
                    else:
                        buffer = buffer[start:]
                        break
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if not line:
                        continue
                    if 'AA55' in line and 'EDED' in line:
                        self.parse_line(line)
                        continue
                    payload = line
                    if line.startswith('TX0:') or line.startswith('TX1:'):
                        payload = line.split(':', 1)[1].strip()
                    elif line.startswith('TX0') or line.startswith('TX1'):
                        payload = line[3:].strip().lstrip(':').strip()
                    msg = f"{self.get_strict_timestamp()} {payload}"
                    self.log_ready.emit(time.time(), msg)
                    self.check_and_log_unknown(msg)
            else:
                time.sleep(0.001)

    def run(self):
        try:
            self._open_serial()
            logger.info('Serial connected: %s @ %d', self.port, self.baudrate)
            self.connection_opened.emit()
        except Exception as e:
            err_msg = tr('msg.serial_open_failed', port=self.port, baud=self.baudrate, error=e)
            logger.error(err_msg)
            self.connection_failed.emit(err_msg)
            if self.demo_mode:
                self._run_demo_loop()
            return

        reconnect_count = 0
        while self.running:
            try:
                self._read_loop()
                break
            except Exception as e:
                logger.exception('Serial read error on %s', self.port)
                if not self.auto_reconnect or reconnect_count >= self.max_reconnect_attempts:
                    self.connection_lost.emit(str(e))
                    break
                reconnect_count += 1
                self.reconnecting.emit(reconnect_count, self.max_reconnect_attempts)
                logger.warning('Reconnect attempt %d/%d on %s', reconnect_count, self.max_reconnect_attempts, self.port)
                time.sleep(self.reconnect_interval)
                try:
                    self._open_serial()
                    logger.info('Serial reconnected: %s', self.port)
                    reconnect_count = 0
                except Exception:
                    logger.warning('Reconnect failed on %s', self.port, exc_info=True)

    def parse_line(self, line):
        try:
            p = line[line.find('AA55'):line.find('EDED') + 4].split(':')
            if len(p) == 10:
                v_in, i_in, v_out, i_out, v_bat, i_bat = [float(x) / 1000 for x in p[1:7]]
                p_out = v_out * i_out
                p_bat = v_bat * i_bat
                eff = min(100.0, (p_bat / p_out * 100.0) if p_out > 0.1 else 0.0)
                self.data_ready.emit({
                    'ts': time.time(), 'v_in': v_in, 'i_in': i_in, 'v_out': v_out, 'i_out': i_out,
                    'v_bat': v_bat, 'i_bat': i_bat, 'eff': eff, 'p': p_out, 't': int(p[7]), 'b': int(p[8]),
                })
            else:
                logger.debug('parse_line: unexpected field count (%d) in %r', len(p), line[:80])
        except (ValueError, IndexError) as e:
            logger.debug('parse_line: parse error %s for %r', e, line[:80])

    def check_and_log_unknown(self, line):
        if 'ASK ' not in line and 'FSK ' not in line:
            return
        try:
            p_type = 'ASK' if 'ASK ' in line else 'FSK'
            start = line.find(f'{p_type} ') + 4
            end = line.find(' F ', start) if p_type == 'ASK' else line.find('(', start)
            hex_str = line[start:end].strip() if end != -1 else line[start:].strip()
            raw = [int(x, 16) for x in hex_str.replace('0x', '').replace(',', ' ').split() if x.isalnum()]
            if not raw:
                return
            if (p_type == 'ASK' and raw[0] not in self.KNOWN_ASK) or (p_type == 'FSK' and raw[0] not in self.KNOWN_FSK):
                cache_key = f'{p_type}_0x{raw[0]:02X}'
                if cache_key not in self._unknown_cmd_cache:
                    self._unknown_cmd_cache.add(cache_key)
                    log_path = str(self._unknown_log_path)
                    with open(log_path, 'a', encoding='utf-8-sig') as f:
                        if not os.path.exists(log_path) or os.path.getsize(log_path) == 0:
                            f.write('=== Qi 2.2.1 未知指令拦截对照表 ===\n\n')
                        f.write(
                            f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] "
                            f'发现未知 {p_type} | Header: 0x{raw[0]:02X} | 示例: {hex_str}\n'
                        )
        except Exception:
            logger.warning('check_and_log_unknown failed for line: %s', line[:120], exc_info=True)

    def stop(self):
        self.running = False
        conn = self.serial_conn
        if conn is not None:
            try:
                if conn.is_open:
                    conn.close()
            except Exception:
                logger.warning('Failed to close serial port %s', self.port, exc_info=True)
            self.serial_conn = None
        if not self.wait(3000):
            logger.warning('Serial worker did not stop within 3s on %s', self.port)
            self.terminate()
            self.wait(1000)
