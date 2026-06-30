"""泰克示波器 — USB 截图与剪贴板复制。"""
import os
from datetime import datetime

import pyvisa
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ... import config as config_module
from ...i18n import tr
from ...logging_setup import logger
from ...paths import project_path
from ...ui.theme import FS_BODY, MONITOR_WINDOW_STYLESHEET, ui_font_css

_TEK_USB_VID = '0x0699'


class TektronixScopeWindow(QMainWindow):
    """Connect to Tektronix scopes over USB and capture PNG screenshots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scopes = []
        self._rm = None
        self._pix = None
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QGridLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(8)

        self.btn_connect = QPushButton()
        self.btn_connect.setMinimumSize(100, 30)
        self.btn_connect.setMaximumWidth(160)
        self.btn_connect.clicked.connect(self._on_connect)
        left.addWidget(self.btn_connect)

        self.edit_model = QLineEdit()
        self.edit_model.setReadOnly(True)
        self.edit_model.setFocusPolicy(Qt.NoFocus)
        self.edit_model.setAlignment(Qt.AlignHCenter)
        self.edit_model.setMinimumSize(100, 28)
        self.edit_model.setMaximumWidth(160)
        left.addWidget(self.edit_model)

        left.addSpacing(24)

        self.btn_capture1 = QPushButton()
        self.btn_capture1.setMinimumSize(100, 30)
        self.btn_capture1.setMaximumWidth(160)
        self.btn_capture1.clicked.connect(lambda: self._on_capture(0))
        left.addWidget(self.btn_capture1)

        self.btn_capture2 = QPushButton()
        self.btn_capture2.setMinimumSize(100, 30)
        self.btn_capture2.setMaximumWidth(160)
        self.btn_capture2.clicked.connect(lambda: self._on_capture(1))
        left.addWidget(self.btn_capture2)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumWidth(120)
        self.log_view.setMaximumWidth(200)
        self.log_view.setStyleSheet(
            f'QTextEdit {{ {ui_font_css(FS_BODY)} background: #070B14; color: #E2E8F0; '
            f'border: 1px solid #8BA3BD; border-radius: 4px; }}'
        )
        left.addWidget(self.log_view, 1)

        layout.addLayout(left, 0, 0)

        self.preview = QLabel()
        self.preview.setMinimumSize(320, 240)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet(
            'QLabel { background: #070B14; border: 1px solid #8BA3BD; border-radius: 6px; }'
        )
        layout.addWidget(self.preview, 0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(0, 1)

        self.setStyleSheet(MONITOR_WINDOW_STYLESHEET)
        self.resize(720, 480)
        self.setMinimumSize(520, 360)

    def retranslate_ui(self):
        self.setWindowTitle(tr('tool.tektronix_scope.title'))
        self.btn_connect.setText(tr('tool.tektronix_scope.connect'))
        self.btn_capture1.setText(tr('tool.tektronix_scope.capture1'))
        self.btn_capture2.setText(tr('tool.tektronix_scope.capture2'))

    def _save_dir(self) -> str:
        apps_cfg = config_module.CONFIG.get('apps', {})
        rel = apps_cfg.get('tektronix_scope', {}).get('save_dir')
        if not rel:
            rel = config_module.CONFIG.get('tektronix_scope', {}).get('save_dir', 'scope_captures')
        path = project_path(rel)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def _append_log(self, message: str):
        self.log_view.append(message)

    def _close_scopes(self):
        for handle in self._scopes:
            try:
                handle.close()
            except Exception:
                logger.warning('Failed to close scope handle', exc_info=True)
        self._scopes.clear()
        if self._rm is not None:
            try:
                self._rm.close()
            except Exception:
                logger.warning('Failed to close VISA resource manager', exc_info=True)
            self._rm = None

    def _on_connect(self):
        self._close_scopes()
        self.edit_model.clear()
        try:
            self._rm = pyvisa.ResourceManager()
            resources = self._rm.list_resources('USB?*INSTR')
        except Exception as exc:
            logger.exception('VISA list_resources failed')
            self._append_log(tr('tool.tektronix_scope.conn_failed_list'))
            self._append_log(str(exc))
            return

        opened = []
        for addr in resources:
            if 'USB' not in addr or _TEK_USB_VID not in addr:
                continue
            try:
                opened.append(self._rm.open_resource(addr))
            except Exception:
                logger.exception('Failed to open VISA resource %s', addr)
                self._append_log(tr('tool.tektronix_scope.conn_failed_open'))
                return

        for handle in opened:
            if not isinstance(handle, pyvisa.resources.usb.USBInstrument):
                try:
                    handle.close()
                except Exception:
                    pass
                continue
            try:
                idn = handle.query('*IDN?')
            except Exception:
                logger.exception('*IDN? failed on scope handle')
                self._append_log(tr('tool.tektronix_scope.conn_failed'))
                try:
                    handle.close()
                except Exception:
                    pass
                continue
            if 'TEKTRONIX' not in idn.upper():
                try:
                    handle.close()
                except Exception:
                    pass
                continue
            self._scopes.append(handle)
            fields = idn.split(',')
            if len(fields) > 1:
                self.edit_model.setText(fields[1].strip())

        if self._scopes:
            self._append_log(tr('tool.tektronix_scope.conn_success', count=len(self._scopes)))
        else:
            self._append_log(tr('tool.tektronix_scope.conn_none'))

    def _on_capture(self, index: int):
        if index >= len(self._scopes):
            self._append_log(tr('tool.tektronix_scope.scope_unavailable', index=index + 1))
            return
        self._capture_scope(self._scopes[index])

    def _capture_scope(self, handle):
        save_dir = self._save_dir()
        try:
            handle.write('SAVe:IMAGe:FILEFormat PNG')
            handle.write('SAVe:IMAGe:INKSaver ON')
            handle.write('HARDCopy STARt')
            img_data = handle.read_raw()

            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = os.path.join(save_dir, f'{stamp}.png')
            with open(file_path, 'wb') as img_file:
                img_file.write(img_data)

            img = QImage(file_path)
            if img.isNull():
                self._append_log(tr('tool.tektronix_scope.save_error'))
                return
            self.preview.setScaledContents(True)
            self._pix = QPixmap.fromImage(img)
            self.preview.setPixmap(self._pix)
            self._append_log(tr('tool.tektronix_scope.save_ok', path=file_path))
            self._copy_to_clipboard()
        except Exception:
            logger.exception('Scope capture failed')
            self._append_log(tr('tool.tektronix_scope.save_error'))

    def _copy_to_clipboard(self):
        if self._pix is None or self._pix.isNull():
            self._append_log(tr('tool.tektronix_scope.copy_failed'))
            return
        try:
            QApplication.clipboard().setPixmap(self._pix)
            self._append_log(tr('tool.tektronix_scope.copy_ok'))
        except Exception:
            logger.exception('Clipboard copy failed')
            self._append_log(tr('tool.tektronix_scope.copy_failed'))

    def closeEvent(self, event):
        self._close_scopes()
        super().closeEvent(event)
