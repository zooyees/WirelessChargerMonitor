import sqlite3

from ..config import CONFIG
from ..logging_setup import logger
from ..paths import project_path


def db_path() -> str:
    return str(project_path(CONFIG['system']['db_name']))


def init_db():
    db_name = db_path()
    conn = sqlite3.connect(db_name)
    conn.execute('PRAGMA journal_mode=WAL;')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS test_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_uuid TEXT,
                        started_at TEXT NOT NULL,
                        ended_at TEXT,
                        port TEXT,
                        baudrate INTEGER,
                        demo_mode INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS charging_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        rel_time REAL, v_in REAL, i_in REAL, v_out REAL, i_out REAL,
                        v_bat REAL, i_bat REAL, eff REAL, power REAL, temp REAL, battery REAL)''')
    for ddl in (
        'CREATE INDEX IF NOT EXISTS idx_rel_time ON charging_metrics(rel_time)',
        'CREATE INDEX IF NOT EXISTS idx_metrics_session ON charging_metrics(session_id)',
    ):
        try:
            cursor.execute(ddl)
        except sqlite3.OperationalError:
            pass
    try:
        cursor.execute('ALTER TABLE charging_metrics ADD COLUMN session_id INTEGER')
    except sqlite3.OperationalError:
        pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS tx0_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        rel_time REAL,
                        message TEXT)''')
    try:
        cursor.execute('ALTER TABLE tx0_logs ADD COLUMN rel_time REAL')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE tx0_logs ADD COLUMN session_id INTEGER')
    except sqlite3.OperationalError:
        pass
    for ddl in (
        'CREATE INDEX IF NOT EXISTS idx_tx0_rel_time ON tx0_logs(rel_time)',
        'CREATE INDEX IF NOT EXISTS idx_logs_session ON tx0_logs(session_id)',
    ):
        try:
            cursor.execute(ddl)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()
    logger.info('Database initialized: %s', db_name)
