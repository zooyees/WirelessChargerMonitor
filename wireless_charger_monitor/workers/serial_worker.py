import datetime
import os
import time

import serial
from PyQt5.QtCore import QThread, pyqtSignal

from ..i18n import tr
from ..logging_setup import logger
from ..paths import project_path
from ..protocol.protocol_defs import all_known_ask_headers, all_known_fsk_headers

_UNKNOWN_LOG = 'Unknown_Qi_Commands_Log.txt'


class SerialWorker(QThread):
    data_ready = pyqtSignal(dict)
    log_ready = pyqtSignal(float, str)
    logs_batch_ready = pyqtSignal(list)
    connection_failed = pyqtSignal(str)
    connection_opened = pyqtSignal()
    connection_lost = pyqtSignal(str)
    reconnecting = pyqtSignal(int, int)
    KNOWN_ASK = all_known_ask_headers()
    KNOWN_FSK = all_known_fsk_headers()

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

    def _emit_log_batch(self, batch: list[tuple[float, str]]) -> None:
        if not batch:
            return
        if len(batch) == 1:
            ts, msg = batch[0]
            self.log_ready.emit(ts, msg)
        else:
            self.logs_batch_ready.emit(batch)

    def _process_text_line(self, line: str, log_batch: list[tuple[float, str]]) -> None:
        line = line.strip()
        if not line:
            return
        if 'AA55' in line and 'EDED' in line:
            self.parse_line(line)
            return
        payload = line
        if line.startswith('TX0:') or line.startswith('TX1:'):
            payload = line.split(':', 1)[1].strip()
        elif line.startswith('TX0') or line.startswith('TX1'):
            payload = line[3:].strip().lstrip(':').strip()
        msg = f"{self.get_strict_timestamp()} {payload}"
        log_batch.append((time.time(), msg))
        self.check_and_log_unknown(msg)

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
            self._emit_log_batch([(time.time(), msg)])

    def _read_loop(self):
        buffer = bytearray()
        while self.running:
            waiting = self.serial_conn.in_waiting
            if waiting > 0:
                buffer.extend(self.serial_conn.read(waiting))
                log_batch: list[tuple[float, str]] = []

                while True:
                    start = buffer.find(b'AA55')
                    if start == -1:
                        break
                    end = buffer.find(b'EDED', start)
                    if end == -1:
                        if start > 0:
                            del buffer[:start]
                        break
                    frame = buffer[start:end + 4].decode('ascii', errors='ignore')
                    self.parse_line(frame)
                    del buffer[:end + 4]

                while b'\n' in buffer:
                    line_bytes, rest = buffer.split(b'\n', 1)
                    buffer = bytearray(rest)
                    line = line_bytes.decode('ascii', errors='ignore')
                    self._process_text_line(line, log_batch)

                self._emit_log_batch(log_batch)
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
            end = line.find(' F ', start)
            if end == -1 and p_type == 'FSK':
                end = line.find('(', start)
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
