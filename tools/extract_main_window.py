"""One-off helper: extract MonitorWindow from legacy main.py."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
legacy = ROOT / 'tools' / '_legacy_main.py'
source = legacy if legacy.is_file() else ROOT / 'main.py'
main_lines = source.read_text(encoding='utf-8').splitlines()
body = main_lines[492:1226]
if not body:
    raise SystemExit(f'No MonitorWindow body found in {source} ({len(main_lines)} lines)')

HEADER = '''"""Main window controller."""
import bisect
import csv
import datetime
import os
import sqlite3
import time

import pyqtgraph as pg
import serial.tools.list_ports
from PyQt5.QtCore import QEvent, Qt, QTimer
from PyQt5.QtGui import QColor, QCursor, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QTextEdit,
    QToolTip,
)

from ..config import CONFIG
from ..db import (
    close_session,
    create_session,
    db_path,
    get_session_info,
    init_db,
    pick_report_session,
    resolve_export_session_id,
)
from ..logging_setup import logger
from ..protocol.qi_parser import Qi22Parser
from ..report.engine import ReportEngine
from ..workers import DBWorker, FetchWorker, SerialWorker
from .loader import Ui_MonitorWindow

'''

out = ROOT / 'wireless_charger_monitor' / 'ui' / 'main_window.py'
out.write_text(HEADER + '\n'.join(body) + '\n', encoding='utf-8')
print(f'Wrote {out} ({len(body)} lines)')
