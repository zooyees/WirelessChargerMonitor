"""Tektronix scope app package.

Import client modules directly for headless CLI to avoid pulling Qt UI:
``from wireless_charger_monitor.apps.tektronix_scope.client import TektronixScopeClient``
"""

from .client import ScopeError, TektronixScopeClient

__all__ = ['TektronixScopePanel', 'TektronixScopeClient', 'ScopeError', 'TektronixScopeWindow']


def __getattr__(name: str):
    if name in ('TektronixScopePanel', 'TektronixScopeWindow'):
        from .panel import TektronixScopePanel

        if name == 'TektronixScopeWindow':
            return TektronixScopePanel
        return TektronixScopePanel
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
