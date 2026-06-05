import datetime
import sqlite3
import uuid

from PyQt5.QtWidgets import QInputDialog

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


def resolve_export_session_id(current_session_id):
    """导出时优先使用当前会话，否则取最近一次会话。"""
    if current_session_id:
        return current_session_id
    conn = sqlite3.connect(db_path())
    row = conn.execute('SELECT id FROM test_sessions ORDER BY id DESC LIMIT 1').fetchone()
    conn.close()
    return row[0] if row else None


def pick_report_session(parent, default_session_id=None):
    """弹出会话选择框，供 PDF 报告导出使用。"""
    conn = sqlite3.connect(db_path())
    rows = conn.execute(
        '''SELECT s.id, s.session_uuid, s.started_at, s.ended_at, s.port,
                  (SELECT COUNT(*) FROM charging_metrics m WHERE m.session_id = s.id) AS samples
           FROM test_sessions s ORDER BY s.id DESC LIMIT 30'''
    ).fetchall()
    conn.close()
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0][0]
    default_idx = next((i for i, r in enumerate(rows) if r[0] == default_session_id), 0)
    items = []
    for r in rows:
        status = r[3] if r[3] else '进行中'
        items.append(f"#{r[0]} [{r[1]}] {r[2]} → {status} | {r[4] or '-'} | {r[5]}点")
    item, ok = QInputDialog.getItem(
        parent, '选择测试会话', '请选择要生成 PDF 报告的测试会话：', items, default_idx, False,
    )
    if not ok:
        return None
    return rows[items.index(item)][0]
