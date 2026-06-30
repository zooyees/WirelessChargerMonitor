"""Application entry: QApplication bootstrap and main window."""
import argparse
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QStyleFactory

from . import config as config_module
from .config import load_config
from .i18n import init_language
from .paths import app_icon_path
from .ui import MonitorWindow


def _load_app_icon() -> QIcon | None:
    path = app_icon_path()
    if path is None:
        return None
    icon = QIcon(str(path))
    return icon if not icon.isNull() else None


def main(argv=None):
    parser = argparse.ArgumentParser(description='WiParse')
    parser.add_argument(
        '--demo', action='store_true',
        help='串口不可用时启用演示模式（模拟数据，不可用于正式测试）',
    )
    args = parser.parse_args(argv)

    load_config()
    init_language(config_module.CONFIG.get('ui', {}).get('language', 'en'))

    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('WiParse.App.1')
        except Exception:
            pass

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except AttributeError:
        pass

    app = QApplication(sys.argv if argv is None else argv)
    app_icon = _load_app_icon()
    if app_icon is not None:
        app.setWindowIcon(app_icon)
    if 'Fusion' in QStyleFactory.keys():
        app.setStyle('Fusion')
    win = MonitorWindow(cli_demo_mode=args.demo)
    if app_icon is not None:
        win.setWindowIcon(app_icon)
    win.show()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
