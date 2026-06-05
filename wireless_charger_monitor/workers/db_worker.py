import queue
import sqlite3
import time

from PyQt5.QtCore import QThread

from ..config import CONFIG
from ..db.schema import db_path
from ..logging_setup import logger

_METRIC_SQL = (
    'INSERT INTO charging_metrics (session_id, rel_time, v_in, i_in, v_out, i_out, '
    'v_bat, i_bat, eff, power, temp, battery) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)'
)
_LOG_SQL = 'INSERT INTO tx0_logs (session_id, rel_time, message) VALUES (?, ?, ?)'


class DBWorker(QThread):

    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self.running = True
        self.db_name = db_path()
        sys_cfg = CONFIG.get('system', {})
        self.commit_interval = sys_cfg.get('db_commit_interval_sec', 1.0)
        self.commit_batch = sys_cfg.get('db_commit_batch_size', 100)
        self._pending_count = 0
        self._last_commit = time.time()

    def _maybe_commit(self, conn):
        now = time.time()
        if (self._pending_count >= self.commit_batch
                or (now - self._last_commit) >= self.commit_interval
                or self.queue.empty()):
            conn.commit()
            self._pending_count = 0
            self._last_commit = now

    def _execute_task(self, cur, task):
        if task['type'] == 'metric':
            d = task['data']
            cur.execute(
                _METRIC_SQL,
                (task.get('session_id'), task['rel_time'], d['v_in'], d['i_in'], d['v_out'], d['i_out'],
                 d['v_bat'], d['i_bat'], d['eff'], d['p'], d['t'], d['b']),
            )
        elif task['type'] == 'log':
            cur.execute(
                _LOG_SQL,
                (task.get('session_id'), task.get('rel_time', 0.0), task['msg']),
            )

    def run(self):
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        cur = conn.cursor()
        while self.running:
            try:
                task = self.queue.get(timeout=0.1)
                self._execute_task(cur, task)
                self._pending_count += 1
                self._maybe_commit(conn)
            except queue.Empty:
                if self._pending_count:
                    try:
                        conn.commit()
                        self._pending_count = 0
                        self._last_commit = time.time()
                    except Exception:
                        logger.exception('DBWorker: idle commit failed')
                continue
            except Exception:
                logger.exception('DBWorker: failed to process task')
        while not self.queue.empty():
            try:
                task = self.queue.get_nowait()
                self._execute_task(cur, task)
                self._pending_count += 1
            except queue.Empty:
                break
            except Exception:
                logger.exception('DBWorker: failed to flush remaining task')
        try:
            conn.commit()
        except Exception:
            logger.exception('DBWorker: final commit failed')
        conn.close()
        logger.info('DBWorker stopped')

    def stop(self):
        self.running = False
        self.wait()
