"""QTabWidget / QTabBar sizing helpers (fit tab label width, no elide)."""
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtWidgets import QTabBar, QTabWidget

_TAB_MIN_H = 30
_V_PAD = 12

TAB_PRESETS = {
    'main': dict(scroll_threshold=3, h_pad=36, closable_extra=0, use_bold=True),
    'file': dict(scroll_threshold=8, h_pad=34, closable_extra=28, use_bold=False),
    'split': dict(scroll_threshold=6, h_pad=32, closable_extra=0, use_bold=False),
}


class AdaptiveTabBar(QTabBar):
    """Tab bar that sizes each tab to its label (PyQt5 requires a subclass, not monkey-patch)."""

    def __init__(self, parent=None, *, h_pad=28, closable_extra=24, use_bold=False):
        super().__init__(parent)
        self._h_pad = h_pad
        self._closable_extra = closable_extra
        self._use_bold = use_bold
        self.setElideMode(Qt.ElideNone)
        self.setExpanding(False)
        self.setDrawBase(False)

    def tabSizeHint(self, index):
        fm = QFontMetrics(self._measure_font())
        text = self.tabText(index)
        text_w = fm.horizontalAdvance(text) if hasattr(fm, 'horizontalAdvance') else fm.width(text)
        extra = self._closable_extra if self.tabsClosable() else 0
        height = max(fm.lineSpacing() + _V_PAD, _TAB_MIN_H)
        return QSize(text_w + self._h_pad + extra, height)

    def _measure_font(self):
        font = QFont(self.font())
        if self._use_bold:
            font.setBold(True)
        return font


def _snapshot_tabs(tab_widget: QTabWidget):
    bar = tab_widget.tabBar()
    current = tab_widget.currentIndex()
    saved = []
    for index in range(tab_widget.count()):
        visible = True
        if hasattr(bar, 'isTabVisible'):
            visible = bar.isTabVisible(index)
        saved.append(
            (
                tab_widget.widget(index),
                tab_widget.tabText(index),
                tab_widget.tabToolTip(index),
                visible,
            )
        )
    return current, saved


def _restore_tabs(tab_widget: QTabWidget, current_index, saved):
    bar = tab_widget.tabBar()
    for widget, text, tooltip, visible in saved:
        index = tab_widget.addTab(widget, text)
        tab_widget.setTabToolTip(index, tooltip)
        if hasattr(bar, 'setTabVisible'):
            bar.setTabVisible(index, visible)
    if 0 <= current_index < tab_widget.count():
        tab_widget.setCurrentIndex(current_index)


def ensure_adaptive_tab_bar(
    tab_widget: QTabWidget,
    *,
    h_pad: int = 28,
    closable_extra: int = 24,
    use_bold: bool = False,
) -> AdaptiveTabBar:
    bar = tab_widget.tabBar()
    if isinstance(bar, AdaptiveTabBar):
        bar._h_pad = h_pad
        bar._closable_extra = closable_extra
        bar._use_bold = use_bold
        bar.setElideMode(Qt.ElideNone)
        bar.setExpanding(False)
        bar.setDrawBase(False)
        return bar

    current_index, saved = _snapshot_tabs(tab_widget)
    while tab_widget.count() > 0:
        tab_widget.removeTab(0)

    new_bar = AdaptiveTabBar(tab_widget, h_pad=h_pad, closable_extra=closable_extra, use_bold=use_bold)
    new_bar.setTabsClosable(bar.tabsClosable())
    new_bar.setUsesScrollButtons(bar.usesScrollButtons())
    new_bar.setMovable(bar.isMovable())
    tab_widget.setTabBar(new_bar)
    _restore_tabs(tab_widget, current_index, saved)
    return new_bar


def refresh_tab_widget(tab_widget: QTabWidget, *, preset: str | None = None, **kwargs) -> None:
    """Recompute tab widths from current labels and sync tab tooltips."""
    if tab_widget is None:
        return
    options = dict(TAB_PRESETS.get(preset or '', {}))
    options.update(kwargs)
    scroll_threshold = options.pop('scroll_threshold', 5)
    bar = ensure_adaptive_tab_bar(tab_widget, **options)
    count = tab_widget.count()
    bar.setUsesScrollButtons(count > scroll_threshold)
    for index in range(count):
        text = tab_widget.tabText(index)
        bar.setTabToolTip(index, text)
    bar.updateGeometry()
    bar.adjustSize()
    tab_widget.updateGeometry()


def patch_tab_bar(tab_bar: QTabBar) -> None:
    """Legacy hook: prefer refresh_tab_widget() on the owning QTabWidget."""
    tab_bar.setElideMode(Qt.ElideNone)
    tab_bar.setExpanding(False)
    tab_bar.setDrawBase(False)
