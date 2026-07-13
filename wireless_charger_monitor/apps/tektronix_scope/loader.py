"""Load Tektronix scope panel chrome (code-built front panel; .ui optional legacy)."""
from PyQt5.QtWidgets import QWidget

from ...ui.theme import apply_tektronix_scope_theme


def load_tektronix_scope_ui(panel: QWidget) -> None:
    """Apply theme to an already-constructed TektronixScopePanel."""
    apply_tektronix_scope_theme(panel)
