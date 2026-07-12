"""单个报文文件 Tab：可选分窗显示（仅 UI，不影响文件存储）。"""

import os
from collections import deque
from functools import partial

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ...i18n import get_language, tr
from ...ui.tab_utils import refresh_tab_widget
from ...ui import theme as ui_theme
from ...ui.theme import (
    FS_BODY,
    LOG_FILTER_SCROLL_H,
    LOG_SPLIT_TOOLBAR_H,
    apply_log_split_checkbox_style,
    apply_log_split_column_title_style,
    apply_log_split_filter_label_style,
    apply_log_split_host_style,
    apply_log_split_line_edit_style,
    apply_log_split_scroll_style,
    apply_log_split_spinbox_style,
    apply_log_split_toolbar_style,
    apply_log_pane_style,
    apply_log_tool_label_style,
)

_MAX_LIVE_LINES = 10000
_STREAM_FILE_THRESHOLD_BYTES = 2 * 1024 * 1024
_STREAM_BATCH_LINES = 5000
_BULK_HIGHLIGHT_LINE_THRESHOLD = 64
_FILTER_LABEL_WIDTH = 76
_FILTER_EDIT_WIDTH = 152
_FILTER_GROUP_SPACING = 8
_LOG_FONT_MAX = 24
_LOG_FONT_DEFAULT = FS_BODY
_FILTER_HIGHLIGHT_COLOR = QColor(ui_theme.FILTER_HIGHLIGHT)
_SEARCH_GOTO_HIGHLIGHT = QColor(ui_theme.ACCENT)
_SEARCH_GOTO_HIGHLIGHT.setAlpha(72)


def _parse_filter_patterns(raw):
    """Parse filter input into substring patterns. ``|`` splits without trimming segments."""
    if raw is None or raw == '':
        return None
    if '|' in raw:
        return tuple(raw.split('|'))
    return (raw,)


class _FilterMatchHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._filter_patterns = None
        self._case_sensitive = False
        self._highlight_format = QTextCharFormat()
        self._highlight_format.setForeground(_FILTER_HIGHLIGHT_COLOR)

    def set_filter_text(self, filter_patterns, *, case_sensitive=False, rehighlight=True):
        self._filter_patterns = filter_patterns or None
        self._case_sensitive = case_sensitive
        if rehighlight:
            self.rehighlight()

    def highlightBlock(self, text):
        if self.document().property('_highlight_suspended'):
            return
        patterns = self._filter_patterns
        if not patterns:
            return
        hay = text if self._case_sensitive else text.casefold()
        for pattern in patterns:
            if not pattern:
                continue
            needle = pattern if self._case_sensitive else pattern.casefold()
            start = 0
            match_len = len(pattern)
            while True:
                idx = hay.find(needle, start)
                if idx < 0:
                    break
                self.setFormat(idx, match_len, self._highlight_format)
                start = idx + match_len


class LogTabPage(QWidget):
    def __init__(self, live=False, filepath=None, parent=None):
        super().__init__(parent)
        self.live = live
        self.filepath = filepath
        self._master_lines = self._new_master_store()
        self._filter_edits = []
        self._parse_checkboxes = []
        self._panes = []
        self._event_filter = None
        self._cached_filters = []
        self._same_page_columns = []
        self._pane_highlighters = {}
        self._search_result_line_map = []
        self._pane_master_maps: list[list[int]] = []
        self._pane_search_ui: list[dict] = []

        self.setObjectName('log_tab_page')

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self._toolbar = QFrame()
        apply_log_split_toolbar_style(self._toolbar)
        self._toolbar.setFixedHeight(LOG_SPLIT_TOOLBAR_H)
        toolbar = QHBoxLayout(self._toolbar)
        toolbar.setContentsMargins(6, 3, 6, 3)
        toolbar.setSpacing(6)

        self.chk_split = QCheckBox(tr('log.split_enable'))
        apply_log_split_checkbox_style(self.chk_split)
        self.chk_split.setToolTip(tr('log.split_tooltip'))
        self.lbl_count = QLabel(tr('log.split_count'))
        apply_log_tool_label_style(self.lbl_count)
        self.spin_count = QSpinBox()
        apply_log_split_spinbox_style(self.spin_count)
        self.spin_count.setToolTip(tr('log.panes_tooltip'))
        self.spin_count.setMinimum(1)
        self.spin_count.setMaximum(16)
        self.spin_count.setValue(2)
        self.spin_count.setFixedWidth(52)
        self.spin_count.setEnabled(False)
        self.lbl_count.setEnabled(False)

        toolbar.addWidget(self.chk_split)
        toolbar.addWidget(self.lbl_count)
        toolbar.addWidget(self.spin_count)

        self.chk_same_page = QCheckBox(tr('log.same_page'))
        apply_log_split_checkbox_style(self.chk_same_page)
        self.chk_same_page.setToolTip(tr('log.same_page_tooltip'))
        self.chk_same_page.setEnabled(False)
        toolbar.addWidget(self.chk_same_page)

        self._filter_scroll = QScrollArea()
        apply_log_split_scroll_style(self._filter_scroll)
        self._filter_scroll.setWidgetResizable(True)
        self._filter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._filter_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._filter_scroll.setFrameShape(QScrollArea.NoFrame)
        self._filter_scroll.setFixedHeight(LOG_FILTER_SCROLL_H)
        self._filter_scroll.setVisible(True)
        self._filter_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._filter_host = QWidget()
        apply_log_split_host_style(self._filter_host)
        self._filter_host.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._filter_layout = QHBoxLayout(self._filter_host)
        self._filter_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_layout.setSpacing(_FILTER_GROUP_SPACING)
        self._filter_scroll.setWidget(self._filter_host)
        toolbar.addWidget(self._filter_scroll, 1)

        self.chk_case_sensitive = QCheckBox(tr('log.case_sensitive'))
        apply_log_split_checkbox_style(self.chk_case_sensitive)
        self.chk_case_sensitive.setToolTip(tr('log.case_sensitive_tooltip'))
        self.chk_case_sensitive.setParent(self._filter_host)

        root.addWidget(self._toolbar)

        self.content_tabs = QTabWidget()
        self.content_tabs.setObjectName('log_split_tabs')
        self.content_tabs.setDocumentMode(False)
        self.content_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._same_page_splitter = QSplitter(Qt.Horizontal)
        self._same_page_splitter.setObjectName('log_split_same_page')
        self._same_page_splitter.setChildrenCollapsible(False)
        self._same_page_splitter.setHandleWidth(6)
        self._same_page_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._view_stack = QStackedWidget()
        self._view_stack.setObjectName('log_split_view_stack')
        self._view_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._view_stack.addWidget(self.content_tabs)
        self._view_stack.addWidget(self._same_page_splitter)

        self._main_splitter = QSplitter(Qt.Vertical)
        self._main_splitter.setObjectName('log_main_splitter')
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.setHandleWidth(6)
        self._main_splitter.addWidget(self._view_stack)
        self._build_search_results_panel(-1)
        self._main_splitter.addWidget(self._search_panel)
        self._main_splitter.setStretchFactor(0, 3)
        self._main_splitter.setStretchFactor(1, 1)
        self._search_panel.setVisible(False)
        root.addWidget(self._main_splitter, 1)

        self.chk_split.toggled.connect(self._on_split_toggled)
        self.chk_same_page.toggled.connect(self._on_same_page_toggled)
        self.chk_case_sensitive.toggled.connect(self._on_case_sensitive_toggled)
        self.spin_count.valueChanged.connect(self._on_count_changed)

        self._build_single_pane()
        self._build_single_filter()
        refresh_tab_widget(self.content_tabs, preset='split')

    def reapply_theme(self):
        apply_log_split_toolbar_style(self._toolbar)
        apply_log_split_checkbox_style(self.chk_split)
        apply_log_tool_label_style(self.lbl_count)
        apply_log_split_spinbox_style(self.spin_count)
        apply_log_split_checkbox_style(self.chk_same_page)
        apply_log_split_checkbox_style(self.chk_case_sensitive)
        apply_log_split_scroll_style(self._filter_scroll)
        apply_log_split_host_style(self._filter_host)
        for i in range(self._filter_layout.count()):
            widget = self._filter_layout.itemAt(i).widget()
            if isinstance(widget, QLabel):
                apply_log_split_filter_label_style(widget)
            elif isinstance(widget, QLineEdit):
                apply_log_split_line_edit_style(widget)
            elif isinstance(widget, QCheckBox):
                apply_log_split_checkbox_style(widget)
        for pane in self._panes:
            apply_log_pane_style(pane)
        for column in self._same_page_columns:
            layout = column.layout()
            if layout is None:
                continue
            title = layout.itemAt(0).widget()
            if isinstance(title, QLabel):
                apply_log_split_column_title_style(title)
        global _FILTER_HIGHLIGHT_COLOR
        _FILTER_HIGHLIGHT_COLOR = QColor(ui_theme.FILTER_HIGHLIGHT)
        for edit in self._panes:
            self.refresh_filter_highlights(edit)
        for highlighter in self._pane_highlighters.values():
            highlighter._highlight_format.setForeground(QColor(ui_theme.FILTER_HIGHLIGHT))
            highlighter.rehighlight()
        if hasattr(self, '_search_results_edit'):
            apply_log_pane_style(self._search_results_edit)
            apply_log_split_column_title_style(self._search_results_title)
            if self._search_results_highlighter:
                self._search_results_highlighter._highlight_format.setForeground(
                    QColor(ui_theme.FILTER_HIGHLIGHT)
                )
                self._search_results_highlighter.rehighlight()
        for ui in self._pane_search_ui:
            apply_log_pane_style(ui['edit'])
            apply_log_split_column_title_style(ui['title'])
            ui['highlighter']._highlight_format.setForeground(QColor(ui_theme.FILTER_HIGHLIGHT))
            ui['highlighter'].rehighlight()
        global _SEARCH_GOTO_HIGHLIGHT
        _SEARCH_GOTO_HIGHLIGHT = QColor(ui_theme.ACCENT)
        _SEARCH_GOTO_HIGHLIGHT.setAlpha(72)

    def _new_master_store(self, lines=None):
        """Live tab: bounded deque for filter/split; file tab: unbounded list."""
        if self.live:
            return deque(lines or [], maxlen=_MAX_LIVE_LINES)
        return list(lines or [])

    def retranslate_ui(self):
        self.chk_split.setText(tr('log.split_enable'))
        self.chk_split.setToolTip(tr('log.split_tooltip'))
        self.lbl_count.setText(tr('log.split_count'))
        self.spin_count.setToolTip(tr('log.panes_tooltip'))
        self.chk_same_page.setText(tr('log.same_page'))
        self.chk_same_page.setToolTip(tr('log.same_page_tooltip'))
        self.chk_case_sensitive.setText(tr('log.case_sensitive'))
        self.chk_case_sensitive.setToolTip(tr('log.case_sensitive_tooltip'))
        saved = self._saved_filter_texts()
        saved_parse = self._saved_parse_states()
        if self.chk_split.isChecked():
            count = max(1, len(self._filter_edits))
            self._rebuild_filters(count)
        else:
            self._build_single_filter()
        self._restore_filter_texts(saved)
        self._restore_parse_states(saved_parse)
        for chk in self._parse_checkboxes:
            chk.setText(tr('log.auto_parse'))
            chk.setToolTip(tr('log.auto_parse_tooltip'))
        self._retranslate_pane_titles()
        if hasattr(self, '_search_results_title'):
            self._update_search_results_title()
        for ui in self._pane_search_ui:
            ui['close'].setText(tr('log.search_results_close'))
            self._update_search_results_title(ui=ui)
        refresh_tab_widget(self.content_tabs, preset='split')

    def _retranslate_pane_titles(self):
        if not self._panes:
            return
        if self._is_same_page_view():
            for index, column in enumerate(self._same_page_columns):
                layout = column.layout()
                if layout is None:
                    continue
                title = layout.itemAt(0).widget()
                if isinstance(title, QLabel):
                    title.setText(tr('log.pane_tab', n=index + 1))
        elif self.chk_split.isChecked():
            for index, pane in enumerate(self._panes):
                self.content_tabs.setTabText(index, tr('log.pane_tab', n=index + 1))
        elif self.content_tabs.count() > 0:
            self.content_tabs.setTabText(0, tr('log.all'))

    def _saved_filter_texts(self):
        return [edit.text() for edit in self._filter_edits]

    def _restore_filter_texts(self, texts):
        if not self._filter_edits:
            return
        for edit, text in zip(self._filter_edits, texts or []):
            edit.blockSignals(True)
            edit.setText(text)
            edit.blockSignals(False)
        self._rebuild_display()

    def primary_editor(self):
        return self._panes[0] if self._panes else None

    def current_editor(self):
        if self._is_same_page_view() and self._panes:
            return self._panes[0]
        widget = self.content_tabs.currentWidget()
        pane = self._pane_from_tab_widget(widget)
        if pane is not None:
            return pane
        return self.primary_editor()

    @staticmethod
    def _pane_from_tab_widget(widget):
        if isinstance(widget, QPlainTextEdit):
            return widget
        if isinstance(widget, QSplitter) and widget.count() > 0:
            top = widget.widget(0)
            if isinstance(top, QPlainTextEdit):
                return top
        return None

    def _is_same_page_view(self):
        return self.chk_split.isChecked() and self.chk_same_page.isChecked()

    def focus_editor(self, edit):
        if edit not in self._panes:
            return
        if self._is_same_page_view():
            edit.setFocus()
            return
        for index, pane in enumerate(self._panes):
            if pane is not edit:
                continue
            if self.chk_split.isChecked() and self._use_search_results_panel():
                tab_widget = self.content_tabs.widget(index)
                if tab_widget is not None:
                    self.content_tabs.setCurrentIndex(index)
                    edit.setFocus()
                    return
            break
        self.content_tabs.setCurrentWidget(edit)

    def _detach_pane_from_column(self, column):
        layout = column.layout()
        if layout is None:
            return
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, QPlainTextEdit):
                widget.setParent(None)
                return

    def _clear_pane_views(self):
        while self.content_tabs.count():
            widget = self.content_tabs.widget(0)
            self.content_tabs.removeTab(0)
            if widget is not None:
                widget.setParent(None)

        while self._same_page_splitter.count():
            column = self._same_page_splitter.widget(0)
            if column is not None:
                self._detach_pane_from_column(column)
                column.setParent(None)
                column.deleteLater()
        self._same_page_columns = []

    def _clear_content_panes(self):
        for pane in self._panes:
            self._pane_highlighters.pop(pane, None)
            pane.setParent(None)
            pane.deleteLater()
        self._panes = []
        self._clear_pane_views()

    def _mount_pane_views(self):
        self._clear_pane_views()
        if not self._panes:
            self._view_stack.setCurrentWidget(self.content_tabs)
            return

        if self.chk_split.isChecked() and self._use_search_results_panel():
            self._ensure_pane_search_ui(len(self._panes))

        if self._is_same_page_view():
            self._view_stack.setCurrentWidget(self._same_page_splitter)
            for index, pane in enumerate(self._panes):
                column = self._make_same_page_column(index, pane)
                self._same_page_columns.append(column)
                self._same_page_splitter.addWidget(column)
            self._equalize_same_page_sizes()
        else:
            self._view_stack.setCurrentWidget(self.content_tabs)
            if len(self._panes) == 1 and not self.chk_split.isChecked():
                self.content_tabs.addTab(self._panes[0], tr('log.all'))
            else:
                for index, pane in enumerate(self._panes):
                    tab_widget = self._make_pane_tab_widget(index, pane)
                    self.content_tabs.addTab(tab_widget, tr('log.pane_tab', n=index + 1))
        self._sync_search_panel_mode()
        self._retranslate_pane_titles()
        self._refresh_event_filters()
        refresh_tab_widget(self.content_tabs, preset='split')

    def _make_pane_tab_widget(self, pane_idx, pane):
        if not (self.chk_split.isChecked() and self._use_search_results_panel()):
            return pane
        ui = self._pane_search_ui[pane_idx]
        splitter = QSplitter(Qt.Vertical)
        splitter.setObjectName('log_pane_search_splitter')
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        pane.setParent(splitter)
        ui['panel'].setParent(splitter)
        splitter.addWidget(pane)
        splitter.addWidget(ui['panel'])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        ui['splitter'] = splitter
        ui['panel'].setVisible(False)
        splitter.setSizes([1, 0])
        return splitter

    def _make_same_page_column(self, index, pane):
        column = QFrame()
        column.setObjectName('log_split_column')
        column.setFrameShape(QFrame.StyledPanel)
        column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        title = QLabel(tr('log.pane_tab', n=index + 1))
        apply_log_split_column_title_style(title)
        layout.addWidget(title)

        if self.chk_split.isChecked() and self._use_search_results_panel():
            ui = self._pane_search_ui[index]
            splitter = QSplitter(Qt.Vertical)
            splitter.setObjectName('log_pane_search_splitter')
            splitter.setChildrenCollapsible(False)
            splitter.setHandleWidth(6)
            pane.setParent(splitter)
            ui['panel'].setParent(splitter)
            splitter.addWidget(pane)
            splitter.addWidget(ui['panel'])
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 1)
            ui['splitter'] = splitter
            ui['panel'].setVisible(False)
            splitter.setSizes([1, 0])
            pane.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            pane.show()
            layout.addWidget(splitter, 1)
        else:
            pane.setParent(column)
            pane.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            pane.show()
            layout.addWidget(pane, 1)
        return column

    def _equalize_same_page_sizes(self):
        count = self._same_page_splitter.count()
        if count <= 0:
            return
        width = max(count * 120, self._same_page_splitter.width())
        size = max(120, width // count)
        self._same_page_splitter.setSizes([size] * count)

    def _ensure_master_lines(self):
        if self._master_lines:
            return
        self._sync_master_from_panes_if_empty()

    def _on_same_page_toggled(self, _checked):
        if not self.chk_split.isChecked() or not self._panes:
            return
        self._ensure_master_lines()
        self._mount_pane_views()
        self._rebuild_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._is_same_page_view():
            self._equalize_same_page_sizes()

    def all_editors(self):
        return list(self._panes)

    def pane_index_for_edit(self, edit):
        try:
            return self._panes.index(edit)
        except ValueError:
            return -1

    def is_auto_parse_enabled(self, pane_idx):
        if pane_idx < 0 or pane_idx >= len(self._parse_checkboxes):
            return False
        return self._parse_checkboxes[pane_idx].isChecked()

    def is_auto_parse_enabled_for_edit(self, edit):
        return self.is_auto_parse_enabled(self.pane_index_for_edit(edit))

    def _use_search_results_panel(self):
        """文件文档分析：筛选结果显示在下方独立面板（分窗时亦同）。"""
        return not self.live

    def _case_sensitive(self) -> bool:
        return self.chk_case_sensitive.isChecked()

    def _sync_highlighter(self, highlighter, filter_patterns, *, rehighlight=False):
        if highlighter is None:
            return
        highlighter.set_filter_text(
            filter_patterns,
            case_sensitive=self._case_sensitive(),
            rehighlight=rehighlight,
        )

    def _use_per_pane_search(self) -> bool:
        return self._use_search_results_panel() and self.chk_split.isChecked()

    def _ensure_pane_search_ui(self, count: int) -> None:
        while len(self._pane_search_ui) < count:
            pane_idx = len(self._pane_search_ui)
            self._pane_search_ui.append(self._build_search_results_panel(pane_idx))
        while len(self._pane_search_ui) > count:
            ui = self._pane_search_ui.pop()
            ui['panel'].setParent(None)
            ui['panel'].deleteLater()

    def _sync_search_panel_mode(self) -> None:
        if self._use_per_pane_search():
            self._hide_search_results_panel()
        else:
            for ui in self._pane_search_ui:
                ui['panel'].setVisible(False)
                if ui.get('splitter') is not None:
                    ui['splitter'].setSizes([1, 0])

    def _search_ui_for_pane(self, pane_idx: int):
        if self._use_per_pane_search():
            if 0 <= pane_idx < len(self._pane_search_ui):
                return self._pane_search_ui[pane_idx]
            return None
        if pane_idx != 0:
            return None
        return {
            'panel': self._search_panel,
            'title': self._search_results_title,
            'close': self._search_results_close,
            'edit': self._search_results_edit,
            'highlighter': self._search_results_highlighter,
            'line_map': self._search_result_line_map,
            'splitter': self._main_splitter,
        }

    def _build_search_results_panel(self, pane_idx=-1):
        panel = QFrame()
        panel.setObjectName('log_search_results_panel')
        panel.setFrameShape(QFrame.StyledPanel)
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName('log_search_results_header')
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 6, 4)
        header_layout.setSpacing(6)

        title = QLabel()
        apply_log_split_column_title_style(title)
        close_btn = QPushButton(tr('log.search_results_close'))
        close_btn.setObjectName('log_search_results_close')
        close_btn.setFixedWidth(52)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(close_btn)

        edit = QPlainTextEdit()
        apply_log_pane_style(edit)
        edit.setObjectName('log_search_results_pane')
        edit.setReadOnly(True)
        edit.setToolTip(tr('log.search_results_tooltip'))
        edit.setProperty('_search_pane_idx', pane_idx)
        highlighter = _FilterMatchHighlighter(edit.document())
        self._pane_highlighters[edit] = highlighter
        font = QFont('Consolas')
        font.setStyleHint(QFont.Monospace)
        font.setPointSizeF(float(_LOG_FONT_DEFAULT))
        edit.setFont(font)
        edit.document().setDefaultFont(font)

        layout.addWidget(header)
        layout.addWidget(edit, 1)

        close_btn.clicked.connect(partial(self._hide_search_results_panel, pane_idx))
        edit.viewport().installEventFilter(self)

        ui = {
            'panel': panel,
            'title': title,
            'close': close_btn,
            'edit': edit,
            'highlighter': highlighter,
            'line_map': [],
            'splitter': None,
        }
        self._update_search_results_title(ui=ui)

        if pane_idx < 0:
            self._search_panel = panel
            self._search_results_title = title
            self._search_results_close = close_btn
            self._search_results_edit = edit
            self._search_results_highlighter = highlighter
            self._search_result_line_map = ui['line_map']

        return ui

    def _update_search_results_title(self, count=None, *, ui=None):
        if ui is None:
            ui = self._search_ui_for_pane(0)
        if ui is None:
            return
        if count is None:
            count = len(ui['line_map'])
        ui['title'].setText(tr('log.search_results_count', n=count))

    def _show_search_results_panel(self, pane_idx=-1):
        if pane_idx >= 0 and self._use_per_pane_search():
            ui = self._pane_search_ui[pane_idx]
            ui['panel'].setVisible(True)
            splitter = ui.get('splitter')
            if splitter is not None:
                total = max(splitter.height(), 240)
                bottom = max(80, int(total * 0.38))
                splitter.setSizes([max(120, total - bottom), bottom])
            return
        self._search_panel.setVisible(True)
        total = max(self._main_splitter.height(), 480)
        bottom = max(120, int(total * 0.38))
        top = max(160, total - bottom)
        self._main_splitter.setSizes([top, bottom])

    def _hide_search_results_panel(self, pane_idx=-1):
        if pane_idx >= 0 and self._use_per_pane_search():
            if pane_idx < len(self._pane_search_ui):
                ui = self._pane_search_ui[pane_idx]
                ui['panel'].setVisible(False)
                if ui.get('splitter') is not None:
                    ui['splitter'].setSizes([1, 0])
            return
        self._search_panel.setVisible(False)
        self._main_splitter.setSizes([1, 0])

    def _hide_all_search_panels(self):
        self._hide_search_results_panel()
        for pane_idx in range(len(self._pane_search_ui)):
            self._hide_search_results_panel(pane_idx)

    def _format_search_result_line(self, master_idx, line):
        return f'{master_idx + 1:6d} | {line}'

    def _collect_search_results(self, filter_idx=0):
        patterns = self._committed_filter_text(filter_idx)
        if patterns is None:
            return [], []
        display_lines = []
        line_map = []
        for master_idx, line in enumerate(self._master_lines):
            if self._line_matches_filter(patterns, line):
                display_lines.append(self._format_search_result_line(master_idx, line))
                line_map.append(master_idx)
        return display_lines, line_map

    def _write_search_results(self, display_lines, patterns, ui):
        text = '\n'.join(display_lines) if display_lines else ''
        cache_key = (text, patterns, self._case_sensitive())
        edit = ui['edit']
        if edit.property('_display_cache_key') == cache_key:
            return
        highlighter = ui['highlighter']
        if highlighter:
            self._sync_highlighter(highlighter, patterns, rehighlight=False)
        edit.blockSignals(True)
        edit.setPlainText(text)
        edit.blockSignals(False)
        edit.setProperty('_display_cache_key', cache_key)
        self._update_search_results_title(len(display_lines), ui=ui)

    def _update_pane_search_results(self, pane_idx: int) -> None:
        ui = self._search_ui_for_pane(pane_idx)
        if ui is None:
            return
        patterns = self._committed_filter_text(pane_idx)
        if patterns is None:
            ui['line_map'].clear()
            self._hide_search_results_panel(pane_idx if self._use_per_pane_search() else -1)
            return
        display_lines, line_map = self._collect_search_results(pane_idx)
        ui['line_map'].clear()
        ui['line_map'].extend(line_map)
        self._write_search_results(display_lines, patterns, ui)
        self._show_search_results_panel(pane_idx if self._use_per_pane_search() else -1)

    def _update_search_results_panel(self, filter_idx=None):
        if not self._use_search_results_panel():
            self._hide_all_search_panels()
            return
        if self._use_per_pane_search():
            if filter_idx is not None:
                self._update_pane_search_results(filter_idx)
            else:
                for idx in range(len(self._panes)):
                    self._update_pane_search_results(idx)
        else:
            self._update_pane_search_results(0)

    def _append_pane_search_results(self, pane_idx, lines, base_master_idx):
        ui = self._search_ui_for_pane(pane_idx)
        if ui is None:
            return
        patterns = self._committed_filter_text(pane_idx)
        if patterns is None:
            return
        additions = []
        mapping_add = []
        for offset, line in enumerate(lines):
            master_idx = base_master_idx + offset
            if self._line_matches_filter(patterns, line):
                additions.append(self._format_search_result_line(master_idx, line))
                mapping_add.append(master_idx)
        if not additions:
            return
        ui['line_map'].extend(mapping_add)
        edit = ui['edit']
        highlighter = ui['highlighter']
        if highlighter and highlighter._filter_patterns != patterns:
            self._sync_highlighter(highlighter, patterns, rehighlight=False)
        prefix = '\n' if edit.document().characterCount() > 0 else ''
        edit.appendPlainText(prefix + '\n'.join(additions))
        edit.setProperty('_display_cache_key', None)
        self._update_search_results_title(ui=ui)
        self._show_search_results_panel(pane_idx if self._use_per_pane_search() else -1)

    def _append_search_results_for_lines(self, lines, base_master_idx, filter_idx=0):
        if self._use_per_pane_search():
            for pane_idx in range(len(self._panes)):
                self._append_pane_search_results(pane_idx, lines, base_master_idx)
        else:
            self._append_pane_search_results(filter_idx, lines, base_master_idx)

    def _goto_master_line(self, master_idx, pane_idx=None):
        if master_idx < 0:
            return
        if pane_idx is not None and self.chk_split.isChecked():
            self._goto_master_line_in_pane(pane_idx, master_idx)
            return
        if self.chk_split.isChecked() and self._pane_master_maps:
            for idx, pane_map in enumerate(self._pane_master_maps):
                if master_idx in pane_map:
                    self._goto_master_line_in_pane(idx, master_idx)
                    return
            return
        edit = self.primary_editor()
        if edit is None:
            return
        block = edit.document().findBlockByNumber(master_idx)
        if not block.isValid():
            return
        self._highlight_editor_block(edit, block)
        edit.setFocus()

    def _goto_master_line_in_pane(self, pane_idx, master_idx):
        if pane_idx < 0 or pane_idx >= len(self._panes):
            return
        if pane_idx >= len(self._pane_master_maps):
            return
        try:
            block_idx = self._pane_master_maps[pane_idx].index(master_idx)
        except ValueError:
            return
        edit = self._panes[pane_idx]
        block = edit.document().findBlockByNumber(block_idx)
        if not block.isValid():
            return
        self._highlight_editor_block(edit, block)
        self.focus_editor(edit)

    def _highlight_editor_block(self, edit, block):
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        edit.setTextCursor(cursor)
        edit.centerCursor()
        extra = QPlainTextEdit.ExtraSelection()
        extra.cursor = cursor
        fmt = QTextCharFormat()
        fmt.setBackground(_SEARCH_GOTO_HIGHLIGHT)
        extra.format = fmt
        edit.setExtraSelections([extra])

    def _goto_search_result_line(self, result_line_idx, pane_idx=-1):
        ui = self._search_ui_for_pane(pane_idx if pane_idx >= 0 else 0)
        if ui is None:
            return
        line_map = ui['line_map']
        if result_line_idx < 0 or result_line_idx >= len(line_map):
            return
        master_idx = line_map[result_line_idx]
        if self._use_per_pane_search() and pane_idx >= 0:
            self._goto_master_line(master_idx, pane_idx=pane_idx)
        else:
            self._goto_master_line(master_idx)

    def _make_editor(self):
        edit = QPlainTextEdit()
        apply_log_pane_style(edit)
        edit.setReadOnly(True)
        edit.setPlaceholderText('')
        edit.setMouseTracking(True)
        edit.viewport().setMouseTracking(True)
        if self.live:
            edit.document().setMaximumBlockCount(_MAX_LIVE_LINES)
        edit.setProperty('_log_font_point_size', float(_LOG_FONT_DEFAULT))
        highlighter = _FilterMatchHighlighter(edit.document())
        self._pane_highlighters[edit] = highlighter
        self._apply_pane_font(edit)
        return edit

    def _pane_highlighter(self, edit):
        return self._pane_highlighters.get(edit)

    def _pane_font_size(self, edit):
        size = edit.property('_log_font_point_size')
        return float(size) if size else float(_LOG_FONT_DEFAULT)

    def _apply_pane_font(self, edit):
        font = QFont('Consolas')
        font.setStyleHint(QFont.Monospace)
        font.setPointSizeF(self._pane_font_size(edit))
        edit.setFont(font)
        edit.document().setDefaultFont(font)

    def _adjust_log_font_size(self, edit, delta):
        if edit not in self._panes or not delta:
            return
        size = self._pane_font_size(edit) + delta
        if size <= 0 or size > _LOG_FONT_MAX:
            return
        edit.setProperty('_log_font_point_size', float(size))
        self._apply_pane_font(edit)

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.MouseButtonDblClick
            and event.button() == Qt.LeftButton
        ):
            for pane_idx, ui in enumerate(self._pane_search_ui):
                if obj is ui['edit'].viewport():
                    cursor = ui['edit'].cursorForPosition(event.pos())
                    self._goto_search_result_line(cursor.blockNumber(), pane_idx)
                    return True
            if hasattr(self, '_search_results_edit') and obj is self._search_results_edit.viewport():
                cursor = self._search_results_edit.cursorForPosition(event.pos())
                self._goto_search_result_line(cursor.blockNumber(), -1)
                return True
        if event.type() == QEvent.Wheel and event.modifiers() & Qt.ControlModifier:
            for edit in self._panes:
                if obj is edit.viewport():
                    delta = event.angleDelta().y()
                    if delta:
                        self._adjust_log_font_size(edit, 1 if delta > 0 else -1)
                    return True
        return super().eventFilter(obj, event)

    def _build_single_pane(self):
        self._clear_content_panes()
        edit = self._make_editor()
        self._panes = [edit]
        self._mount_pane_views()

    def set_event_filter(self, event_filter):
        self._event_filter = event_filter
        self._refresh_event_filters()

    def _refresh_event_filters(self):
        for edit in self.all_editors():
            edit.viewport().removeEventFilter(self)
            if self._event_filter is not None:
                edit.viewport().removeEventFilter(self._event_filter)
        for edit in self.all_editors():
            edit.viewport().installEventFilter(self)
            if self._event_filter is not None:
                edit.viewport().installEventFilter(self._event_filter)

    def _on_split_toggled(self, enabled):
        self._sync_master_from_panes_if_empty()
        saved = self._saved_filter_texts()
        saved_parse = self._saved_parse_states()
        if enabled:
            self.lbl_count.setEnabled(enabled)
        self.spin_count.setEnabled(enabled)
        self.chk_same_page.setEnabled(enabled)
        if not enabled:
            self.chk_same_page.setChecked(False)
        if enabled:
            self._rebuild_panes(self.spin_count.value())
            self._restore_filter_texts(saved[:1])
            self._restore_parse_states(saved_parse[:1])
        else:
            self._pane_search_ui.clear()
            self._build_single_pane()
            self._build_single_filter()
            self._restore_filter_texts(saved[:1])
            self._restore_parse_states(saved_parse[:1])

    def _on_case_sensitive_toggled(self, _checked):
        self._sync_master_from_panes_if_empty()
        self._refresh_filter_cache()
        self._rebuild_display()

    def _sync_master_from_panes_if_empty(self):
        if self._master_lines or not self._panes:
            return
        merged = []
        for pane in self._panes:
            text = pane.toPlainText()
            if text:
                merged.extend(text.splitlines())
        if merged:
            self._master_lines = self._new_master_store(merged)

    def _on_count_changed(self, value):
        if self.chk_split.isChecked():
            saved = self._saved_filter_texts()
            saved_parse = self._saved_parse_states()
            self._rebuild_panes(value)
            self._restore_filter_texts(saved)
            self._restore_parse_states(saved_parse)

    def _clear_filters(self):
        self._filter_layout.removeWidget(self.chk_case_sensitive)
        self.chk_case_sensitive.setParent(self._filter_host)
        self.chk_case_sensitive.hide()
        while self._filter_layout.count():
            item = self._filter_layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self.chk_case_sensitive:
                widget.deleteLater()
        self._filter_edits = []
        self._parse_checkboxes = []

    def _saved_parse_states(self):
        return [chk.isChecked() for chk in self._parse_checkboxes]

    def _restore_parse_states(self, states):
        if not self._parse_checkboxes:
            return
        for chk, checked in zip(self._parse_checkboxes, states or []):
            chk.blockSignals(True)
            chk.setChecked(bool(checked))
            chk.blockSignals(False)

    def _on_auto_parse_toggled(self, _checked):
        QToolTip.hideText()

    def _filter_label_width(self):
        return 58 if get_language() == 'en' else _FILTER_LABEL_WIDTH

    def _add_filter_row(self, label_text, *, with_case_sensitive=False):
        lbl = QLabel(label_text)
        apply_log_split_filter_label_style(lbl)
        lbl.setFixedWidth(self._filter_label_width())
        edit = QLineEdit()
        apply_log_split_line_edit_style(edit)
        edit.setPlaceholderText(tr('log.filter_placeholder'))
        edit.setFixedWidth(_FILTER_EDIT_WIDTH)
        edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        filter_idx = len(self._filter_edits)
        edit.returnPressed.connect(partial(self._on_filter_enter, filter_idx))
        chk_parse = QCheckBox(tr('log.auto_parse'))
        apply_log_split_checkbox_style(chk_parse)
        chk_parse.setToolTip(tr('log.auto_parse_tooltip'))
        chk_parse.toggled.connect(self._on_auto_parse_toggled)
        self._filter_layout.addWidget(lbl)
        self._filter_layout.addWidget(edit)
        if with_case_sensitive:
            self.chk_case_sensitive.show()
            self._filter_layout.addWidget(self.chk_case_sensitive)
        self._filter_layout.addWidget(chk_parse)
        self._filter_edits.append(edit)
        self._parse_checkboxes.append(chk_parse)
        return edit

    def _build_single_filter(self):
        self._clear_filters()
        self._add_filter_row(tr('log.filter'), with_case_sensitive=True)
        self._filter_layout.addStretch(1)

    def _rebuild_filters(self, count):
        self._clear_filters()
        for i in range(count):
            self._add_filter_row(
                tr('log.pane_filter', n=i + 1),
                with_case_sensitive=(i == 0),
            )
        self._filter_layout.addStretch(1)

    def _rebuild_panes(self, count):
        count = max(1, min(16, int(count)))
        self._rebuild_filters(count)
        self._clear_content_panes()
        for _ in range(count):
            self._panes.append(self._make_editor())
        self._mount_pane_views()
        self._rebuild_display()

    def _on_filter_enter(self, filter_idx=0):
        self._sync_master_from_panes_if_empty()
        self._refresh_filter_cache()
        if self.chk_split.isChecked():
            self._rebuild_display(search_filter_idx=filter_idx)
            if not self._is_same_page_view() and 0 <= filter_idx < len(self._panes):
                self.content_tabs.setCurrentIndex(filter_idx)
        else:
            self._refresh_single_pane()

    def _lines_for_split_pane(self, pane_idx, filters=None):
        filters = self._split_filters() if filters is None else filters
        return [
            line for line in self._master_lines
            if self._line_belongs_in_split_pane(line, pane_idx, filters)
        ]

    def _line_matches_filter(self, patterns, line, *, case_sensitive=None):
        if patterns is None:
            return True
        if case_sensitive is None:
            case_sensitive = self._case_sensitive()
        haystack = line if case_sensitive else line.casefold()
        for pattern in patterns:
            if not pattern:
                continue
            needle = pattern if case_sensitive else pattern.casefold()
            if needle in haystack:
                return True
        return False

    def _line_belongs_in_split_pane(self, line, pane_idx, filters):
        text = filters[pane_idx] if pane_idx < len(filters) else None
        if text is None:
            return True
        return self._line_matches_filter(text, line)

    def _distribute_lines_for_split(self, lines, filters=None, base_master_idx=0):
        """分窗 N 按「分窗 N 筛选」独立显示；筛选为空则显示全部；可重复出现在多分窗。"""
        filters = self._split_filters() if filters is None else filters
        pane_count = len(self._panes)
        buckets = [[] for _ in range(pane_count)]
        master_maps = [[] for _ in range(pane_count)]
        show_all = [
            filters[pane_idx] is None if pane_idx < len(filters) else True
            for pane_idx in range(pane_count)
        ]
        for offset, line in enumerate(lines):
            master_idx = base_master_idx + offset
            for pane_idx in range(pane_count):
                if show_all[pane_idx] or self._line_matches_filter(filters[pane_idx], line):
                    buckets[pane_idx].append(line)
                    master_maps[pane_idx].append(master_idx)
        return buckets, master_maps

    def _refresh_single_pane(self):
        if not self._panes:
            return
        if self._use_search_results_panel():
            self._set_pane_texts([list(self._master_lines)])
            self._update_search_results_panel()
            return
        filter_text = self._committed_filter_text(0)
        if filter_text is None:
            visible = self._master_lines
        else:
            visible = [line for line in self._master_lines if self._line_matches_filter(filter_text, line)]
        self._set_pane_texts([visible])

    def _committed_filter_text(self, index=0):
        if index < len(self._cached_filters):
            return self._cached_filters[index]
        return None

    def _refresh_filter_cache(self):
        self._cached_filters = [self._filter_text(edit.text()) for edit in self._filter_edits]
        pane_count = len(self._panes) if self.chk_split.isChecked() else len(self._filter_edits)
        if pane_count <= 0:
            return
        if len(self._cached_filters) < pane_count:
            self._cached_filters.extend([None] * (pane_count - len(self._cached_filters)))
        elif len(self._cached_filters) > pane_count:
            self._cached_filters = self._cached_filters[:pane_count]

    def _split_filters(self):
        """分窗模式下保证筛选条件数量与分窗数量一致。"""
        return list(self._cached_filters[:len(self._panes)])

    def _line_visible_in_single_pane(self, line, filter_text=None):
        if filter_text is None:
            filter_text = self._committed_filter_text(0)
        if filter_text is None:
            return True
        return self._line_matches_filter(filter_text, line)

    def _append_to_panes(self, lines):
        if not lines or not self._panes:
            return []
        targets: list[tuple] = []
        if self.chk_split.isChecked():
            filters = self._split_filters()
            batches, master_maps = self._distribute_lines_for_split(lines, filters)
            if len(self._pane_master_maps) != len(self._panes):
                self._pane_master_maps = [[] for _ in range(len(self._panes))]
            for pane_idx, (pane, batch, filter_text) in enumerate(zip(self._panes, batches, filters)):
                if batch:
                    from_block = self._append_pane_lines(pane, batch, filter_text)
                    targets.append((pane, from_block))
                self._pane_master_maps[pane_idx].extend(master_maps[pane_idx])
            if self._use_search_results_panel():
                base_idx = len(self._master_lines) - len(lines)
                self._append_search_results_for_lines(lines, base_idx)
        else:
            if self._use_search_results_panel():
                base_idx = len(self._master_lines) - len(lines)
                patterns = self._committed_filter_text(0)
                from_block = self._append_pane_lines(self._panes[0], lines, patterns)
                targets.append((self._panes[0], from_block))
                self._append_search_results_for_lines(lines, base_idx)
            else:
                batch = [line for line in lines if self._line_visible_in_single_pane(line)]
                if batch:
                    from_block = self._append_pane_lines(
                        self._panes[0],
                        batch,
                        self._committed_filter_text(0),
                    )
                    targets.append((self._panes[0], from_block))
        return targets

    def _append_pane_lines(self, edit, lines, filter_patterns):
        highlighter = self._pane_highlighter(edit)
        if highlighter and highlighter._filter_patterns != (filter_patterns or None):
            self._sync_highlighter(highlighter, filter_patterns, rehighlight=False)
        edit.setProperty('_display_cache_key', None)
        doc = edit.document()
        rehighlight_from = doc.blockCount() if doc.characterCount() > 0 else 0
        prefix = '\n' if doc.characterCount() > 0 else ''
        edit.appendPlainText(prefix + '\n'.join(lines))
        return rehighlight_from

    def _rehighlight_blocks_from(self, edit, from_block: int) -> None:
        highlighter = self._pane_highlighter(edit)
        if highlighter is None:
            return
        block = edit.document().findBlockByNumber(from_block)
        while block.isValid():
            highlighter.rehighlightBlock(block)
            block = block.next()

    def _write_pane_lines(self, edit, lines, filter_patterns):
        text = '\n'.join(lines) if lines else ''
        case_sensitive = self._case_sensitive()
        cache_key = (text, filter_patterns, case_sensitive)
        old_key = edit.property('_display_cache_key')
        if old_key == cache_key:
            return False
        highlighter = self._pane_highlighter(edit)
        bulk = len(lines) >= _BULK_HIGHLIGHT_LINE_THRESHOLD
        if bulk:
            edit.document().setProperty('_highlight_suspended', True)
        if old_key and old_key[0] == text:
            if highlighter and not bulk:
                self._sync_highlighter(highlighter, filter_patterns, rehighlight=True)
            edit.setProperty('_display_cache_key', cache_key)
            if bulk:
                edit.document().setProperty('_highlight_suspended', False)
            return True
        if highlighter:
            self._sync_highlighter(highlighter, filter_patterns, rehighlight=False)
        edit.blockSignals(True)
        edit.setPlainText(text)
        edit.blockSignals(False)
        edit.setProperty('_display_cache_key', cache_key)
        if bulk:
            edit.document().setProperty('_highlight_suspended', False)
            if highlighter and filter_patterns:
                self._sync_highlighter(highlighter, filter_patterns, rehighlight=True)
        return True

    def _apply_filter_highlights(self, edit, filter_text):
        self._sync_highlighter(self._pane_highlighter(edit), filter_text, rehighlight=True)

    def _pane_filter_texts(self):
        if not self._panes:
            return []
        if self.chk_split.isChecked():
            return self._split_filters()
        return [self._committed_filter_text(0)]

    def refresh_filter_highlights(self, edit=None):
        targets = [edit] if edit is not None else list(self._panes)
        filter_texts = self._pane_filter_texts()
        for index, pane in enumerate(self._panes):
            if pane not in targets:
                continue
            filter_text = filter_texts[index] if index < len(filter_texts) else None
            self._apply_filter_highlights(pane, filter_text)

    def _set_pane_texts(self, pane_line_buckets):
        filter_texts = self._pane_filter_texts()
        if len(filter_texts) < len(pane_line_buckets):
            filter_texts.extend([None] * (len(pane_line_buckets) - len(filter_texts)))
        for edit in self._panes:
            edit.setUpdatesEnabled(False)
        try:
            for edit, lines, filter_text in zip(self._panes, pane_line_buckets, filter_texts):
                changed = self._write_pane_lines(edit, lines, filter_text)
                if changed:
                    edit.moveCursor(QTextCursor.End)
                    edit.show()
        finally:
            for edit in self._panes:
                edit.setUpdatesEnabled(True)
        if self._is_same_page_view():
            self._equalize_same_page_sizes()
        elif self._panes:
            self._panes[-1].viewport().update()

    def _rebuild_display(self, search_filter_idx=None):
        if not self._panes:
            return
        self._sync_master_from_panes_if_empty()
        self._refresh_filter_cache()
        self.setUpdatesEnabled(False)
        try:
            if self.chk_split.isChecked():
                buckets, master_maps = self._distribute_lines_for_split(self._master_lines)
                self._pane_master_maps = master_maps
                self._set_pane_texts(buckets)
                if self._use_search_results_panel():
                    self._update_search_results_panel(search_filter_idx)
            elif self._use_search_results_panel():
                self._set_pane_texts([list(self._master_lines)])
                self._update_search_results_panel()
            else:
                visible = [
                    line for line in self._master_lines
                    if self._line_visible_in_single_pane(line)
                ]
                self._set_pane_texts([visible])
        finally:
            self.setUpdatesEnabled(True)

    def _filter_text(self, raw):
        if raw is None:
            return None
        if not raw:
            return None
        return _parse_filter_patterns(raw)

    def _set_highlight_suspended(self, suspended: bool) -> None:
        for edit in self._panes:
            edit.document().setProperty('_highlight_suspended', suspended)
        if hasattr(self, '_search_results_edit'):
            self._search_results_edit.document().setProperty('_highlight_suspended', suspended)
        for ui in self._pane_search_ui:
            ui['edit'].document().setProperty('_highlight_suspended', suspended)

    @staticmethod
    def should_stream_load(path: str) -> bool:
        try:
            return os.path.getsize(path) >= _STREAM_FILE_THRESHOLD_BYTES
        except OSError:
            return False

    def load_file_streaming(self, path: str, status_callback=None) -> int:
        """Load a large log file in batches to avoid a single huge setPlainText."""
        self.clear()
        self._set_highlight_suspended(True)
        total = 0
        batch: list[str] = []
        try:
            with open(path, 'r', encoding='utf-8-sig', errors='replace') as handle:
                for raw in handle:
                    batch.append(raw.rstrip('\n\r'))
                    if len(batch) >= _STREAM_BATCH_LINES:
                        self._master_lines.extend(batch)
                        self._append_to_panes(batch)
                        total += len(batch)
                        batch = []
                        if status_callback:
                            status_callback(total)
                        QApplication.processEvents()
                if batch:
                    self._master_lines.extend(batch)
                    self._append_to_panes(batch)
                    total += len(batch)
                    if status_callback:
                        status_callback(total)
                    QApplication.processEvents()
        finally:
            self._set_highlight_suspended(False)
            self.refresh_filter_highlights()
        return total

    def append_lines(self, lines):
        if not lines:
            return
        if isinstance(lines, str):
            lines = [lines]
        self._master_lines.extend(lines)
        suspend = self.live or len(lines) >= _BULK_HIGHLIGHT_LINE_THRESHOLD
        if suspend:
            self._set_highlight_suspended(True)
        try:
            targets = self._append_to_panes(lines)
        finally:
            if suspend:
                self._set_highlight_suspended(False)
                if self.live:
                    for edit, from_block in targets:
                        self._rehighlight_blocks_from(edit, from_block)
                else:
                    self.refresh_filter_highlights()

    def set_content(self, text):
        lines = text.splitlines() if text else []
        self._master_lines = self._new_master_store(lines)
        self._search_result_line_map.clear()
        for ui in self._pane_search_ui:
            ui['line_map'].clear()
        self._hide_all_search_panels()
        bulk = len(lines) >= _BULK_HIGHLIGHT_LINE_THRESHOLD
        if bulk:
            self._set_highlight_suspended(True)
        try:
            self._rebuild_display()
        finally:
            if bulk:
                self._set_highlight_suspended(False)
                self.refresh_filter_highlights()

    def clear(self):
        self._master_lines.clear()
        self._search_result_line_map.clear()
        self._pane_master_maps = []
        self._hide_all_search_panels()
        for edit in self._panes:
            edit.clear()
        if hasattr(self, '_search_results_edit'):
            self._search_results_edit.clear()
            self._search_results_edit.setProperty('_display_cache_key', None)
        for ui in self._pane_search_ui:
            ui['line_map'].clear()
            ui['edit'].clear()
            ui['edit'].setProperty('_display_cache_key', None)