"""Load ``tektronix_scope.ui`` into an embedded panel widget."""
import os

from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget

_UI_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tektronix_scope.ui')


def load_tektronix_scope_ui(panel: QWidget) -> None:
    """Bind reference-layout widgets onto ``panel`` and apply WiParse theme."""
    if not os.path.isfile(_UI_FILE):
        raise FileNotFoundError(f'未找到 UI 文件: {_UI_FILE}')

    from ...ui.theme import apply_tektronix_scope_theme

    uic.loadUi(_UI_FILE, panel)
    panel.lineEdit.setFocusPolicy(Qt.NoFocus)
    apply_tektronix_scope_theme(panel)
