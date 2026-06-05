import queue
import sqlite3

from PyQt5.QtCore import QThread, pyqtSignal

from ..db.schema import db_path
from ..logging_setup import logger


class FetchWorker(QThread):
    chart_fetched = pyqtSignal(tuple)
    log_fetched = pyqtSignal(str, bool, str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.log_queue = queue.Queue()
        self.latest_xlim = None
        self.chart_request = False
        self.db_name = db_path()

    def run(self):
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        cur = conn.cursor()
        while self.running:
            if self.chart_request and self.latest_xlim:
                self.chart_request = False
                xlim = self.latest_xlim
                margin = (xlim[1] - xlim[0]) * 0.1
                try:
                    cur.execute(
                        '''SELECT rel_time, power, v_in, i_in, v_out, i_out, v_bat, i_bat, temp, battery
                           FROM charging_metrics WHERE rel_time BETWEEN ? AND ? ORDER BY rel_time ASC''',
                        (xlim[0] - margin, xlim[1] + margin),
                    )
                    rows = cur.fetchall()
                    if rows:
                        if len(rows) > 2000:
                            step = len(rows) // 2000
                            rows = rows[::step]
                        self.chart_fetched.emit(tuple(zip(*rows)))
                    else:
                        self.chart_fetched.emit(([], [], [], [], [], [], [], [], [], []))
                except Exception:
                    logger.exception('FetchWorker: chart query failed')
            try:
                log_task = self.log_queue.get(timeout=0.05)
                r = cur.execute(
                    'SELECT message FROM (SELECT id, message FROM tx0_logs ORDER BY id DESC LIMIT 1000 OFFSET ?) ORDER BY id ASC',
                    (log_task['offset'],),
                ).fetchall()
                if r:
                    self.log_fetched.emit('\n'.join([row[0] for row in r]), True, log_task['direction'])
                else:
                    self.log_fetched.emit('', False, log_task['direction'])
            except queue.Empty:
                pass
            except Exception:
                logger.exception('FetchWorker: log query failed')
        conn.close()
        logger.info('FetchWorker stopped')

    def stop(self):
        self.running = False
        self.wait()
