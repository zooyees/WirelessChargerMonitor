from .loader import Ui_MonitorWindow

__all__ = ['Ui_MonitorWindow', 'MonitorWindow']


def __getattr__(name: str):
    if name == 'MonitorWindow':
        from ..shell.main_window import MonitorWindow
        return MonitorWindow
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
