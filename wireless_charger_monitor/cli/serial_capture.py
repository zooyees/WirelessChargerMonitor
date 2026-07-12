"""Headless serial capture (no Qt)."""
from __future__ import annotations

import datetime
import os
import time
from collections.abc import Callable
from typing import Any

import serial
import serial.tools.list_ports

from ..logging_setup import logger
from ..paths import project_path
from ..protocol.protocol_defs import all_known_ask_headers, all_known_fsk_headers
from .errors import CliError

_UNKNOWN_LOG = 'Unknown_Qi_Commands_Log.txt'

MetricCallback = Callable[[dict], None]
LogCallback = Callable[[dict], None]
EventCallback = Callable[[dict], None]


def list_ports_detail() -> list[dict[str, str]]:
    ports = []
    for p in serial.tools.list_ports.comports():
        ports.append({
            'device': p.device,
            'description': p.description or '',
            'hwid': p.hwid or '',
        })
    return ports


def parse_metric_frame(line: str) -> dict | None:
    try:
        start = line.find('AA55')
        end = line.find('EDED')
        if start < 0 or end < 0:
            return None
        parts = line[start:end + 4].split(':')
        if len(parts) != 10:
            return None
        v_in, i_in, v_out, i_out, v_bat, i_bat = [float(x) / 1000 for x in parts[1:7]]
        p_out = v_out * i_out
        p_bat = v_bat * i_bat
        eff = min(100.0, (p_bat / p_out * 100.0) if p_out > 0.1 else 0.0)
        return {
            'ts': time.time(),
            'v_in': v_in,
            'i_in': i_in,
            'v_out': v_out,
            'i_out': i_out,
            'v_bat': v_bat,
            'i_bat': i_bat,
            'eff': eff,
            'p': p_out,
            't': int(parts[7]),
            'b': int(parts[8]),
        }
    except (ValueError, IndexError):
        return None


class SerialCapture:
    """Open a COM port and collect electrical metrics + Qi log lines."""

    KNOWN_ASK = all_known_ask_headers()
    KNOWN_FSK = all_known_fsk_headers()

    def __init__(self, port: str, baudrate: int = 2000000, demo_mode: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.demo_mode = demo_mode
        self.serial_conn: serial.Serial | None = None
        self.last_log_time = datetime.datetime.now()
        self._unknown_cmd_cache: set[str] = set()
        self._unknown_log_path = project_path(_UNKNOWN_LOG)
        self._t0: float | None = None

    def _ensure_port_exists(self) -> None:
        devices = {p.device for p in serial.tools.list_ports.comports()}
        if self.port not in devices and not self.demo_mode:
            raise CliError(
                'PORT_NOT_FOUND',
                f'Port {self.port} was not found',
                hint='Run `wiparse ports` to list available devices',
            )

    def open(self) -> None:
        self._ensure_port_exists()
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=0)
            self.serial_conn.reset_input_buffer()
            self._t0 = time.time()
        except serial.SerialException as exc:
            msg = str(exc).lower()
            if 'access is denied' in msg or 'busy' in msg or 'permission' in msg:
                raise CliError(
                    'PORT_BUSY',
                    f'Port {self.port} is already in use',
                    hint='Close the GUI serial connection or choose another port',
                ) from exc
            raise CliError('PORT_BUSY', f'Failed to open {self.port}: {exc}') from exc

    def close(self) -> None:
        conn = self.serial_conn
        self.serial_conn = None
        if conn is not None:
            try:
                if conn.is_open:
                    conn.close()
            except Exception:
                logger.warning('Failed to close serial port %s', self.port, exc_info=True)

    def get_strict_timestamp(self) -> str:
        now = datetime.datetime.now()
        if now <= self.last_log_time:
            now = self.last_log_time + datetime.timedelta(milliseconds=1)
        self.last_log_time = now
        return f"[{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}]"

    def _rel_t(self, ts: float) -> float:
        if self._t0 is None:
            self._t0 = ts
        return round(ts - self._t0, 6)

    def _with_rel(self, metric: dict) -> dict:
        out = dict(metric)
        out['rel_t'] = self._rel_t(out['ts'])
        return out

    def check_and_log_unknown(self, line: str) -> None:
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
            known = self.KNOWN_ASK if p_type == 'ASK' else self.KNOWN_FSK
            if raw[0] not in known:
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

    def _process_text_line(
        self,
        line: str,
        on_metric: MetricCallback | None,
        on_log: LogCallback | None,
        metrics: list[dict],
        logs: list[dict],
    ) -> None:
        line = line.strip()
        if not line:
            return
        if 'AA55' in line and 'EDED' in line:
            metric = parse_metric_frame(line)
            if metric:
                metric = self._with_rel(metric)
                metrics.append(metric)
                if on_metric:
                    on_metric(metric)
            return
        payload = line
        if line.startswith('TX0:') or line.startswith('TX1:'):
            payload = line.split(':', 1)[1].strip()
        elif line.startswith('TX0') or line.startswith('TX1'):
            payload = line[3:].strip().lstrip(':').strip()
        msg = f'{self.get_strict_timestamp()} {payload}'
        ts = time.time()
        entry = {'ts': ts, 'rel_t': self._rel_t(ts), 'raw': msg}
        logs.append(entry)
        self.check_and_log_unknown(msg)
        if on_log:
            on_log(entry)

    def _feed_bytes(
        self,
        buffer: bytearray,
        chunk: bytes,
        on_metric: MetricCallback | None,
        on_log: LogCallback | None,
        metrics: list[dict],
        logs: list[dict],
    ) -> None:
        buffer.extend(chunk)
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
            metric = parse_metric_frame(frame)
            if metric:
                metric = self._with_rel(metric)
                metrics.append(metric)
                if on_metric:
                    on_metric(metric)
            del buffer[:end + 4]

        while b'\n' in buffer:
            line_bytes, rest = buffer.split(b'\n', 1)
            buffer.clear()
            buffer.extend(rest)
            line = line_bytes.decode('ascii', errors='ignore')
            self._process_text_line(line, on_metric, on_log, metrics, logs)

    def _run_demo(
        self,
        duration: float | None,
        max_metrics: int | None,
        max_logs: int | None,
        on_metric: MetricCallback | None,
        on_log: LogCallback | None,
        on_event: EventCallback | None,
        metrics: list[dict],
        logs: list[dict],
    ) -> None:
        if on_event:
            on_event({'name': 'demo'})
        self._t0 = time.time()
        deadline = None if duration is None else (self._t0 + duration)
        while True:
            now = time.time()
            if deadline is not None and now >= deadline:
                break
            if max_metrics is not None and len(metrics) >= max_metrics:
                break
            if max_logs is not None and len(logs) >= max_logs:
                break
            time.sleep(0.05)
            metric = parse_metric_frame('AA55:9000:1500:8500:1400:4000:3000:45:80:EDED')
            if metric:
                metric = self._with_rel(metric)
                metrics.append(metric)
                if on_metric:
                    on_metric(metric)
            ts = self.get_strict_timestamp()
            t = time.time()
            if int(t) % 3 == 0:
                msg = f'{ts} ASK 51 3E 00 00 00 00 F'
            elif int(t) % 3 == 1:
                msg = f'{ts} ASK 71 22 12 34 00 00 00 00 F'
            else:
                msg = f'{ts} FSK 40 03 F'
            entry = {'ts': t, 'rel_t': self._rel_t(t), 'raw': msg}
            logs.append(entry)
            if on_log:
                on_log(entry)

    def capture(
        self,
        duration: float | None = None,
        max_metrics: int | None = None,
        max_logs: int | None = None,
        on_metric: MetricCallback | None = None,
        on_log: LogCallback | None = None,
        on_event: EventCallback | None = None,
        require_data: bool = False,
    ) -> dict[str, Any]:
        """Blocking capture until duration / count limits are hit."""
        if duration is None and max_metrics is None and max_logs is None:
            duration = 5.0

        metrics: list[dict] = []
        logs: list[dict] = []
        t_start = time.time()

        if self.demo_mode:
            try:
                self.open()
            except CliError:
                self._run_demo(duration, max_metrics, max_logs, on_metric, on_log, on_event, metrics, logs)
                duration_sec = time.time() - t_start
                return self._result(duration_sec, metrics, logs)
            # Port opened; still allow demo if empty? Prefer real data when open succeeds.

        try:
            if self.serial_conn is None or not self.serial_conn.is_open:
                self.open()
            if on_event:
                on_event({'name': 'connected', 'port': self.port, 'baud': self.baudrate})
            self._t0 = time.time()
            deadline = None if duration is None else (self._t0 + duration)
            buffer = bytearray()
            while True:
                now = time.time()
                if deadline is not None and now >= deadline:
                    break
                if max_metrics is not None and len(metrics) >= max_metrics:
                    break
                if max_logs is not None and len(logs) >= max_logs:
                    break
                waiting = self.serial_conn.in_waiting if self.serial_conn else 0
                if waiting > 0:
                    chunk = self.serial_conn.read(waiting)
                    self._feed_bytes(buffer, chunk, on_metric, on_log, metrics, logs)
                else:
                    time.sleep(0.001)
        finally:
            self.close()

        duration_sec = time.time() - t_start
        if require_data and not metrics and not logs:
            raise CliError(
                'SERIAL_TIMEOUT',
                f'No serial data received within {duration_sec:.2f}s on {self.port}',
                hint='Check baud rate, cable, and that the device is transmitting',
            )
        return self._result(duration_sec, metrics, logs)

    def stream_demo(
        self,
        on_metric: MetricCallback | None = None,
        on_log: LogCallback | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        """Infinite demo stream until KeyboardInterrupt."""
        metrics: list[dict] = []
        logs: list[dict] = []
        if on_event:
            on_event({'name': 'demo'})
        while True:
            metrics.clear()
            logs.clear()
            self._run_demo(0.15, None, None, on_metric, on_log, None, metrics, logs)

    def stream(
        self,
        types: set[str] | None = None,
        on_metric: MetricCallback | None = None,
        on_log: LogCallback | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        """Run until KeyboardInterrupt."""
        want_metrics = types is None or 'metrics' in types
        want_logs = types is None or 'logs' in types
        self.open()
        try:
            if on_event:
                on_event({'name': 'connected', 'port': self.port, 'baud': self.baudrate})
            self._t0 = time.time()
            buffer = bytearray()
            metrics: list[dict] = []
            logs: list[dict] = []

            def _m(m: dict) -> None:
                if want_metrics and on_metric:
                    on_metric(m)

            def _l(entry: dict) -> None:
                if want_logs and on_log:
                    on_log(entry)

            while True:
                waiting = self.serial_conn.in_waiting if self.serial_conn else 0
                if waiting > 0:
                    chunk = self.serial_conn.read(waiting)
                    metrics.clear()
                    logs.clear()
                    self._feed_bytes(
                        buffer,
                        chunk,
                        _m if want_metrics else None,
                        _l if want_logs else None,
                        metrics,
                        logs,
                    )
                else:
                    time.sleep(0.001)
        finally:
            self.close()
            if on_event:
                on_event({'name': 'disconnected'})

    def _result(self, duration_sec: float, metrics: list[dict], logs: list[dict]) -> dict[str, Any]:
        ask_count = sum(1 for x in logs if ' ASK ' in x.get('raw', ''))
        fsk_count = sum(1 for x in logs if ' FSK ' in x.get('raw', ''))
        powers = [m['p'] for m in metrics]
        summary = {
            'metrics_count': len(metrics),
            'logs_count': len(logs),
            'ask_count': ask_count,
            'fsk_count': fsk_count,
        }
        if powers:
            summary['p_avg'] = round(sum(powers) / len(powers), 4)
            summary['p_max'] = round(max(powers), 4)
            summary['p_min'] = round(min(powers), 4)
        return {
            'port': self.port,
            'baud': self.baudrate,
            'duration_sec': round(duration_sec, 3),
            'metrics': metrics,
            'logs': logs,
            'summary': summary,
            'artifacts': {},
        }
