"""UI package — keep imports lazy so headless CLI does not pull PyQtGraph."""

__all__ = ['Ui_MonitorWindow', 'MonitorWindow']


def __getattr__(name: str):
    if name == 'Ui_MonitorWindow':
        from .loader import Ui_MonitorWindow
        return Ui_MonitorWindow
    if name == 'MonitorWindow':
        from ..shell.main_window import MonitorWindow
        return MonitorWindow
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
