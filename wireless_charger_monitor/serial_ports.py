"""串口列表变化监测（Windows 设备管理器事件 + 轮询兜底）。"""
import sys

import serial.tools.list_ports
from PyQt5.QtCore import QAbstractNativeEventFilter, QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication

_WM_DEVICECHANGE = 0x0219


def list_com_devices():
    return [p.device for p in serial.tools.list_ports.comports()]


class _WindowsDeviceFilter(QAbstractNativeEventFilter):
    def __init__(self, on_device_change):
        super().__init__()
        self._on_device_change = on_device_change

    def nativeEventFilter(self, eventType, message):
        if sys.platform != 'win32' or eventType != b'windows_generic_MSG':
            return False, 0
        try:
            from ctypes import wintypes

            msg = wintypes.MSG.from_address(int(message))
            if msg.message == _WM_DEVICECHANGE:
                self._on_device_change()
        except Exception:
            pass
        return False, 0


class SerialPortWatcher(QObject):
    """监听系统串口插拔，仅在 COM 列表变化时发出 ports_changed。"""

    ports_changed = pyqtSignal()

    def __init__(self, poll_interval_ms=2000, parent=None):
        super().__init__(parent)
        self._known = frozenset(list_com_devices())
        self._filter = None

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(400)
        self._debounce.timeout.connect(self._emit_if_changed)

        self._poll = QTimer(self)
        self._poll.setInterval(poll_interval_ms)
        self._poll.timeout.connect(self._schedule_check)

    def start(self):
        app = QApplication.instance()
        if sys.platform == 'win32' and app is not None and self._filter is None:
            self._filter = _WindowsDeviceFilter(self._schedule_check)
            app.installNativeEventFilter(self._filter)
        self._poll.start()

    def stop(self):
        self._poll.stop()
        self._debounce.stop()
        app = QApplication.instance()
        if self._filter is not None and app is not None:
            app.removeNativeEventFilter(self._filter)
            self._filter = None

    def sync_known(self):
        self._known = frozenset(list_com_devices())

    def _schedule_check(self):
        self._debounce.start()

    def _emit_if_changed(self):
        current = frozenset(list_com_devices())
        if current == self._known:
            return
        self._known = current
        self.ports_changed.emit()
