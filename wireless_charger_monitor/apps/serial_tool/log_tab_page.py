"""单个报文文件 Tab：可选分窗显示（仅 UI，不影响文件存储）。"""

from collections import deque
from functools import partial

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
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
_FILTER_LABEL_WIDTH = 76
_FILTER_EDIT_WIDTH = 112
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
        self._highlight_format = QTextCharFormat()
        self._highlight_format.setForeground(_FILTER_HIGHLIGHT_COLOR)

    def set_filter_text(self, filter_patterns, *, rehighlight=True):
        self._filter_patterns = filter_patterns or None
        if rehighlight:
            self.rehighlight()

    def highlightBlock(self, text):
        patterns = self._filter_patterns
        if not patterns:
            return
        for pattern in patterns:
            if not pattern:
                continue
            start = 0
            match_len = len(pattern)
            while True:
                idx = text.find(pattern, start)
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
        self._search_panel = self._build_search_results_panel()
        self._main_splitter.addWidget(self._search_panel)
        self._main_splitter.setStretchFactor(0, 3)
        self._main_splitter.setStretchFactor(1, 1)
        self._search_panel.setVisible(False)
        root.addWidget(self._main_splitter, 1)

        self.chk_split.toggled.connect(self._on_split_toggled)
        self.chk_same_page.toggled.connect(self._on_same_page_toggled)
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
        if isinstance(widget, QPlainTextEdit):
            return widget
        return self.primary_editor()

    def _is_same_page_view(self):
        return self.chk_split.isChecked() and self.chk_same_page.isChecked()

    def focus_editor(self, edit):
        if edit not in self._panes:
            return
        if self._is_same_page_view():
            edit.setFocus()
            return
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
                    self.content_tabs.addTab(pane, tr('log.pane_tab', n=index + 1))
        self._retranslate_pane_titles()
        self._refresh_event_filters()
        refresh_tab_widget(self.content_tabs, preset='split')

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
        pane.setParent(column)
        pane.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pane.show()
        layout.addWidget(title)
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
        """文件文档分析：单窗模式下筛选结果显示在下方独立面板。"""
        return not self.live and not self.chk_split.isChecked()

    def _build_search_results_panel(self):
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

        self._search_results_title = QLabel()
        apply_log_split_column_title_style(self._search_results_title)
        self._search_results_close = QPushButton(tr('log.search_results_close'))
        self._search_results_close.setObjectName('log_search_results_close')
        self._search_results_close.setFixedWidth(52)
        header_layout.addWidget(self._search_results_title)
        header_layout.addStretch(1)
        header_layout.addWidget(self._search_results_close)

        self._search_results_edit = QPlainTextEdit()
        apply_log_pane_style(self._search_results_edit)
        self._search_results_edit.setObjectName('log_search_results_pane')
        self._search_results_edit.setReadOnly(True)
        self._search_results_edit.setToolTip(tr('log.search_results_tooltip'))
        self._search_results_highlighter = _FilterMatchHighlighter(self._search_results_edit.document())
        self._pane_highlighters[self._search_results_edit] = self._search_results_highlighter
        font = QFont('Consolas')
        font.setStyleHint(QFont.Monospace)
        font.setPointSizeF(float(_LOG_FONT_DEFAULT))
        self._search_results_edit.setFont(font)
        self._search_results_edit.document().setDefaultFont(font)

        layout.addWidget(header)
        layout.addWidget(self._search_results_edit, 1)

        self._search_results_close.clicked.connect(self._hide_search_results_panel)
        self._search_results_edit.viewport().installEventFilter(self)
        self._update_search_results_title()
        return panel

    def _update_search_results_title(self, count=None):
        if count is None:
            count = len(self._search_result_line_map)
        self._search_results_title.setText(tr('log.search_results_count', n=count))

    def _show_search_results_panel(self):
        self._search_panel.setVisible(True)
        total = max(self._main_splitter.height(), 480)
        bottom = max(120, int(total * 0.38))
        top = max(160, total - bottom)
        self._main_splitter.setSizes([top, bottom])

    def _hide_search_results_panel(self):
        self._search_panel.setVisible(False)
        self._main_splitter.setSizes([1, 0])

    def _format_search_result_line(self, master_idx, line):
        return f'{master_idx + 1:6d} | {line}'

    def _collect_search_results(self):
        patterns = self._committed_filter_text(0)
        if patterns is None:
            return [], []
        display_lines = []
        line_map = []
        for master_idx, line in enumerate(self._master_lines):
            if self._line_matches_filter(patterns, line):
                display_lines.append(self._format_search_result_line(master_idx, line))
                line_map.append(master_idx)
        return display_lines, line_map

    def _write_search_results(self, display_lines, patterns):
        text = '\n'.join(display_lines) if display_lines else ''
        cache_key = (text, patterns)
        edit = self._search_results_edit
        if edit.property('_display_cache_key') == cache_key:
            return
        highlighter = self._search_results_highlighter
        if highlighter:
            highlighter.set_filter_text(patterns, rehighlight=False)
        edit.blockSignals(True)
        edit.setPlainText(text)
        edit.blockSignals(False)
        edit.setProperty('_display_cache_key', cache_key)
        self._update_search_results_title(len(display_lines))

    def _update_search_results_panel(self):
        if not self._use_search_results_panel():
            self._hide_search_results_panel()
            return
        display_lines, line_map = self._collect_search_results()
        patterns = self._committed_filter_text(0)
        if patterns is None:
            self._search_result_line_map = []
            self._hide_search_results_panel()
            return
        self._search_result_line_map = line_map
        self._write_search_results(display_lines, patterns)
        self._show_search_results_panel()

    def _append_search_results_for_lines(self, lines, base_master_idx):
        if not self._search_panel.isVisible():
            return
        patterns = self._committed_filter_text(0)
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
        self._search_result_line_map.extend(mapping_add)
        edit = self._search_results_edit
        highlighter = self._search_results_highlighter
        if highlighter and highlighter._filter_patterns != patterns:
            highlighter.set_filter_text(patterns, rehighlight=False)
        prefix = '\n' if edit.document().characterCount() > 0 else ''
        edit.appendPlainText(prefix + '\n'.join(additions))
        edit.setProperty('_display_cache_key', None)
        self._update_search_results_title(len(self._search_result_line_map))

    def _goto_master_line(self, master_idx):
        edit = self.primary_editor()
        if edit is None or master_idx < 0:
            return
        block = edit.document().findBlockByNumber(master_idx)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        edit.setTextCursor(cursor)
        edit.centerCursor()
        edit.setFocus()
        extra = QPlainTextEdit.ExtraSelection()
        extra.cursor = cursor
        fmt = QTextCharFormat()
        fmt.setBackground(_SEARCH_GOTO_HIGHLIGHT)
        extra.format = fmt
        edit.setExtraSelections([extra])

    def _goto_search_result_line(self, result_line_idx):
        if result_line_idx < 0 or result_line_idx >= len(self._search_result_line_map):
            return
        self._goto_master_line(self._search_result_line_map[result_line_idx])

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
            hasattr(self, '_search_results_edit')
            and obj is self._search_results_edit.viewport()
            and event.type() == QEvent.MouseButtonDblClick
            and event.button() == Qt.LeftButton
        ):
            cursor = self._search_results_edit.cursorForPosition(event.pos())
            self._goto_search_result_line(cursor.blockNumber())
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
            self._hide_search_results_panel()
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
            self._build_single_pane()
            self._build_single_filter()
            self._restore_filter_texts(saved[:1])
            self._restore_parse_states(saved_parse[:1])

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
        while self._filter_layout.count():
            item = self._filter_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
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

    def _add_filter_row(self, label_text):
        lbl = QLabel(label_text)
        apply_log_split_filter_label_style(lbl)
        lbl.setFixedWidth(self._filter_label_width())
        edit = QLineEdit()
        apply_log_split_line_edit_style(edit)
        edit.setPlaceholderText(tr('log.filter_placeholder'))
        edit.setToolTip(tr('log.filter_tooltip'))
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
        self._filter_layout.addWidget(chk_parse)
        self._filter_edits.append(edit)
        self._parse_checkboxes.append(chk_parse)
        return edit

    def _build_single_filter(self):
        self._clear_filters()
        self._add_filter_row(tr('log.filter'))
        self._filter_layout.addStretch(1)

    def _rebuild_filters(self, count):
        self._clear_filters()
        for i in range(count):
            self._add_filter_row(tr('log.pane_filter', n=i + 1))
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
            self._rebuild_display()
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

    def _line_matches_filter(self, patterns, line):
        if patterns is None:
            return True
        return any(pattern in line for pattern in patterns)

    def _line_belongs_in_split_pane(self, line, pane_idx, filters):
        text = filters[pane_idx] if pane_idx < len(filters) else None
        if text is None:
            return True
        return self._line_matches_filter(text, line)

    def _distribute_lines_for_split(self, lines, filters=None):
        """分窗 N 按「分窗 N 筛选」独立显示；筛选为空则显示全部；可重复出现在多分窗。"""
        filters = self._split_filters() if filters is None else filters
        pane_count = len(self._panes)
        buckets = [[] for _ in range(pane_count)]
        show_all = [
            filters[pane_idx] is None if pane_idx < len(filters) else True
            for pane_idx in range(pane_count)
        ]
        for line in lines:
            for pane_idx in range(pane_count):
                if show_all[pane_idx] or self._line_matches_filter(filters[pane_idx], line):
                    buckets[pane_idx].append(line)
        return buckets

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
            return
        if self.chk_split.isChecked():
            filters = self._split_filters()
            batches = self._distribute_lines_for_split(lines, filters)
            for pane, batch, filter_text in zip(self._panes, batches, filters):
                if batch:
                    self._append_pane_lines(pane, batch, filter_text)
        else:
            if self._use_search_results_panel():
                base_idx = len(self._master_lines) - len(lines)
                patterns = self._committed_filter_text(0)
                self._append_pane_lines(self._panes[0], lines, patterns)
                self._append_search_results_for_lines(lines, base_idx)
            else:
                batch = [line for line in lines if self._line_visible_in_single_pane(line)]
                if batch:
                    self._append_pane_lines(
                        self._panes[0],
                        batch,
                        self._committed_filter_text(0),
                    )

    def _append_pane_lines(self, edit, lines, filter_patterns):
        highlighter = self._pane_highlighter(edit)
        if highlighter and highlighter._filter_patterns != (filter_patterns or None):
            highlighter.set_filter_text(filter_patterns, rehighlight=False)
        edit.setProperty('_display_cache_key', None)
        prefix = '\n' if edit.document().characterCount() > 0 else ''
        edit.appendPlainText(prefix + '\n'.join(lines))

    def _write_pane_lines(self, edit, lines, filter_patterns):
        text = '\n'.join(lines) if lines else ''
        cache_key = (text, filter_patterns)
        old_key = edit.property('_display_cache_key')
        if old_key == cache_key:
            return False
        highlighter = self._pane_highlighter(edit)
        if old_key and old_key[0] == text:
            if highlighter:
                highlighter.set_filter_text(filter_patterns)
            edit.setProperty('_display_cache_key', cache_key)
            return True
        if highlighter:
            highlighter.set_filter_text(filter_patterns, rehighlight=False)
        edit.blockSignals(True)
        edit.setPlainText(text)
        edit.blockSignals(False)
        edit.setProperty('_display_cache_key', cache_key)
        return True

    def _apply_filter_highlights(self, edit, filter_text):
        highlighter = self._pane_highlighter(edit)
        if highlighter is None:
            return
        highlighter.set_filter_text(filter_text)

    def _pane_filter_texts(self):
        if not self._panes:
            return []
        if self._use_search_results_panel():
            return [self._committed_filter_text(0)]
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

    def _rebuild_display(self):
        if not self._panes:
            return
        self._sync_master_from_panes_if_empty()
        self._refresh_filter_cache()
        self.setUpdatesEnabled(False)
        try:
            if self.chk_split.isChecked():
                buckets = self._distribute_lines_for_split(self._master_lines)
                self._set_pane_texts(buckets)
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

    def append_lines(self, lines):
        if not lines:
            return
        if isinstance(lines, str):
            lines = [lines]
        self._master_lines.extend(lines)
        self._append_to_panes(lines)

    def set_content(self, text):
        lines = text.splitlines() if text else []
        self._master_lines = self._new_master_store(lines)
        self._search_result_line_map = []
        self._hide_search_results_panel()
        self._rebuild_display()

    def clear(self):
        self._master_lines.clear()
        self._search_result_line_map = []
        self._hide_search_results_panel()
        for edit in self._panes:
            edit.clear()
        if hasattr(self, '_search_results_edit'):
            self._search_results_edit.clear()
            self._search_results_edit.setProperty('_display_cache_key', None)