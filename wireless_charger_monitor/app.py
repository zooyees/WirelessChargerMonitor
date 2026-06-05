"""Application entry: QApplication bootstrap and main window."""
import argparse
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from .ui import MonitorWindow


def main(argv=None):
    parser = argparse.ArgumentParser(description='手机无线充电监控系统')
    parser.add_argument(
        '--demo', action='store_true',
        help='串口不可用时启用演示模式（模拟数据，不可用于正式测试）',
    )
    args = parser.parse_args(argv)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except AttributeError:
        pass

    app = QApplication(sys.argv if argv is None else argv)
    win = MonitorWindow(cli_demo_mode=args.demo)
    win.show()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
