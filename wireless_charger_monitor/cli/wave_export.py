"""Waveform / session export helpers (SQLite + live points)."""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from ..db.schema import db_path, init_db
from ..db.sessions import get_session_info
from ..paths import project_path
from .errors import CliError

CHANNEL_UNITS = {
    'rel_t': 's',
    'v_in': 'V',
    'i_in': 'A',
    'v_out': 'V',
    'i_out': 'A',
    'v_bat': 'V',
    'i_bat': 'A',
    'p': 'W',
    'eff': '%',
    't': 'C',
    'b': '%',
}

DEFAULT_CHANNELS = ['rel_t', 'v_in', 'i_in', 'v_out', 'i_out', 'v_bat', 'i_bat', 'p']


def metrics_to_wave(metrics: list[dict], channels: list[str] | None = None) -> dict[str, Any]:
    chans = channels or DEFAULT_CHANNELS
    if 'rel_t' not in chans:
        chans = ['rel_t'] + chans
    points = []
    for m in metrics:
        row = []
        for c in chans:
            key = 't' if c == 'temp' else ('b' if c == 'battery' else c)
            if key == 'p' and key not in m and 'p' in m:
                key = 'p'
            row.append(m.get(key, m.get(c)))
        points.append(row)
    sample_rate = None
    if len(metrics) >= 2:
        dt = metrics[-1]['rel_t'] - metrics[0]['rel_t']
        if dt > 0:
            sample_rate = round((len(metrics) - 1) / dt, 3)
    return {
        'sample_rate_hz_est': sample_rate,
        'channels': chans,
        'points': points,
        'units': {c: CHANNEL_UNITS.get(c, '') for c in chans},
    }


def fetch_session_metrics(
    session_id: int,
    rel_from: float | None = None,
    rel_to: float | None = None,
) -> list[dict]:
    path = db_path()
    if not Path(path).is_file():
        raise CliError('DB_NOT_FOUND', f'Database not found: {path}')
    info = get_session_info(session_id)
    if not info:
        raise CliError('SESSION_NOT_FOUND', f'Session {session_id} not found')

    conn = sqlite3.connect(path)
    try:
        sql = (
            'SELECT rel_time, v_in, i_in, v_out, i_out, v_bat, i_bat, eff, power, temp, battery, timestamp '
            'FROM charging_metrics WHERE session_id=? '
        )
        params: list[Any] = [session_id]
        if rel_from is not None:
            sql += 'AND rel_time >= ? '
            params.append(rel_from)
        if rel_to is not None:
            sql += 'AND rel_time <= ? '
            params.append(rel_to)
        sql += 'ORDER BY rel_time ASC'
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    metrics = []
    for r in rows:
        metrics.append({
            'rel_t': r[0],
            'v_in': r[1],
            'i_in': r[2],
            'v_out': r[3],
            'i_out': r[4],
            'v_bat': r[5],
            'i_bat': r[6],
            'eff': r[7],
            'p': r[8],
            't': r[9],
            'b': r[10],
            'timestamp': r[11],
        })
    return metrics


def fetch_session_logs(session_id: int) -> list[dict]:
    path = db_path()
    if not Path(path).is_file():
        raise CliError('DB_NOT_FOUND', f'Database not found: {path}')
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            'SELECT rel_time, timestamp, message FROM tx0_logs WHERE session_id=? ORDER BY id ASC',
            (session_id,),
        ).fetchall()
    finally:
        conn.close()
    return [{'rel_t': r[0], 'timestamp': r[1], 'raw': r[2]} for r in rows]


def list_sessions(limit: int = 50) -> list[dict]:
    path = db_path()
    if not Path(path).is_file():
        return []
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            'SELECT id, session_uuid, started_at, ended_at, port, baudrate, demo_mode '
            'FROM test_sessions ORDER BY id DESC LIMIT ?',
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            'session_id': r[0],
            'session_uuid': r[1],
            'started_at': r[2],
            'ended_at': r[3],
            'port': r[4],
            'baudrate': r[5],
            'demo_mode': bool(r[6]),
        }
        for r in rows
    ]


def export_metrics_file(metrics: list[dict], out_path: str | Path, fmt: str = 'json') -> str:
    path = Path(out_path)
    if not path.is_absolute():
        path = project_path(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower()
    if fmt == 'csv':
        fields = ['rel_t', 'v_in', 'i_in', 'v_out', 'i_out', 'v_bat', 'i_bat', 'eff', 'p', 't', 'b']
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            for m in metrics:
                writer.writerow(m)
    elif fmt in ('json', 'jsonl'):
        if fmt == 'jsonl':
            with open(path, 'w', encoding='utf-8') as f:
                for m in metrics:
                    f.write(json.dumps(m, ensure_ascii=False) + '\n')
        else:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2)
    else:
        raise CliError('INVALID_ARGS', f'Unsupported format: {fmt}')
    return str(path.resolve())


def save_capture_to_db(port: str, baud: int, metrics: list[dict], logs: list[dict], demo_mode: bool = False) -> int:
    """Persist a CLI capture as a test session. Returns session_id."""
    from ..db.sessions import close_session, create_session

    init_db()
    session_id, _, _ = create_session(port, baud, demo_mode=demo_mode)
    conn = sqlite3.connect(db_path())
    try:
        cur = conn.cursor()
        for m in metrics:
            cur.execute(
                '''INSERT INTO charging_metrics
                   (session_id, rel_time, v_in, i_in, v_out, i_out, v_bat, i_bat, eff, power, temp, battery)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    session_id, m.get('rel_t'), m.get('v_in'), m.get('i_in'), m.get('v_out'), m.get('i_out'),
                    m.get('v_bat'), m.get('i_bat'), m.get('eff'), m.get('p'), m.get('t'), m.get('b'),
                ),
            )
        for entry in logs:
            cur.execute(
                'INSERT INTO tx0_logs (session_id, rel_time, message) VALUES (?,?,?)',
                (session_id, entry.get('rel_t'), entry.get('raw')),
            )
        conn.commit()
    finally:
        conn.close()
        close_session(session_id)
    return session_id
