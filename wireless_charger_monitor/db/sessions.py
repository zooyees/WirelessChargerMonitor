import datetime
import sqlite3
import uuid

from ..logging_setup import logger
from .schema import db_path


def create_session(port, baudrate, demo_mode=False):
    conn = sqlite3.connect(db_path())
    started_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    session_uuid = str(uuid.uuid4())[:8].upper()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO test_sessions (session_uuid, started_at, port, baudrate, demo_mode) VALUES (?,?,?,?,?)',
        (session_uuid, started_at, port, baudrate, int(demo_mode)),
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    logger.info('Session created: id=%s uuid=%s port=%s', session_id, session_uuid, port)
    return session_id, started_at, session_uuid


def close_session(session_id):
    if not session_id:
        return
    conn = sqlite3.connect(db_path())
    ended_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('UPDATE test_sessions SET ended_at=? WHERE id=?', (ended_at, session_id))
    conn.commit()
    conn.close()
    logger.info('Session closed: id=%s ended_at=%s', session_id, ended_at)


def get_session_info(session_id):
    conn = sqlite3.connect(db_path())
    row = conn.execute(
        'SELECT id, session_uuid, started_at, ended_at, port, baudrate, demo_mode FROM test_sessions WHERE id=?',
        (session_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        'session_id': row[0], 'session_uuid': row[1], 'started_at': row[2], 'ended_at': row[3],
        'port': row[4], 'baudrate': row[5], 'demo_mode': bool(row[6]),
    }
