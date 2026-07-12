"""泰克示波器面板 — embedded tab (ported from TektronixScopeTool ``mainDlg.py``)."""
import os
from datetime import datetime

import pyvisa
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QWidget

from ... import config as config_module
from ...i18n import tr
from ...logging_setup import logger
from ...paths import project_path
from .loader import load_tektronix_scope_ui

_TEK_USB_VID = '0x0699'


class TektronixScopePanel(QWidget):
    """USB Tektronix scope screenshot panel (HARDCopy PNG + clipboard)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scopes = []
        self._rm = None
        self._pix = None
        load_tektronix_scope_ui(self)
        self._wire_signals()
        self.retranslate_ui()

    def _wire_signals(self):
        self.lineEdit.setFocusPolicy(Qt.NoFocus)
        self.lineEdit.setAlignment(Qt.AlignHCenter)
        self.pushButton_connect.clicked.connect(self._on_connect)
        self.pushButton_save.clicked.connect(self._on_capture_first)
        self.pushButton_save_2.clicked.connect(self._on_capture_second)

    def retranslate_ui(self):
        self.pushButton_connect.setText(tr('tool.tektronix_scope.connect'))
        self.pushButton_save.setText(tr('tool.tektronix_scope.capture1'))
        self.pushButton_save_2.setText(tr('tool.tektronix_scope.capture2'))

    def reapply_theme(self):
        from ...ui.theme import apply_tektronix_scope_theme
        apply_tektronix_scope_theme(self)

    def release_scopes(self):
        """Close VISA handles when the host window closes."""
        self._close_scopes()

    def _save_dir(self) -> str:
        apps_cfg = config_module.CONFIG.get('apps', {})
        rel = apps_cfg.get('tektronix_scope', {}).get('save_dir')
        if not rel:
            rel = config_module.CONFIG.get('tektronix_scope', {}).get('save_dir', 'scope_captures')
        path = project_path(rel)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def _append_log(self, message: str):
        self.textEdit.append(message)

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
        self.lineEdit.clear()
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
                self.lineEdit.setText(fields[1].strip())
            self._append_log(tr('tool.tektronix_scope.conn_success_single'))

        if not self._scopes:
            self._append_log(tr('tool.tektronix_scope.conn_none'))

    def _on_capture_first(self):
        if not self._scopes:
            self._append_log(tr('tool.tektronix_scope.scope_unavailable', index=1))
            return
        self._capture_scope(self._scopes[0])

    def _on_capture_second(self):
        try:
            if len(self._scopes) < 2:
                self._append_log(tr('tool.tektronix_scope.scope_unavailable', index=2))
                return
            self._capture_scope(self._scopes[1])
        except Exception:
            logger.exception('Scope capture failed on scope 2')
            self._append_log(tr('tool.tektronix_scope.save_error'))

    def _capture_scope(self, handle):
        save_dir = self._save_dir()
        try:
            from .client import hardcopy_png_to_file

            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = os.path.join(save_dir, f'{stamp}.png')
            hardcopy_png_to_file(handle, file_path)

            img = QImage()
            img.load(file_path)
            if img.isNull():
                self._append_log(tr('tool.tektronix_scope.save_error'))
                return
            self.label.setScaledContents(True)
            self._pix = QPixmap.fromImage(img)
            self.label.setPixmap(self._pix)
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
