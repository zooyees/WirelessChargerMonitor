"""高对比度 UI 主题（深色背景 + 高亮文字）。"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QLCDNumber,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QWidget,
)

# 文字
TEXT_PRIMARY = '#FFFFFF'
TEXT_SECONDARY = '#F1F5F9'
TEXT_MUTED = '#CBD5E1'
LABEL_ACCENT = '#FFFFFF'

# 背景 / 边框
CANVAS_BG = '#0B1220'
PANEL_BG = '#162032'
SURFACE_BG = '#1A2332'
LCD_BG = '#070B14'
BORDER = '#8BA3BD'
BORDER_STRONG = '#C7D2E0'

# Typography — single scale for the whole app
FONT_FAMILY_UI = "'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
FONT_FAMILY_MONO = "Consolas, 'Courier New', monospace"
FS_CAPTION = 9      # status bar, field labels, secondary controls
FS_BODY = 10        # inputs, tabs, menus, buttons
FS_SUBTITLE = 11    # section headings (e.g. Real-Time Packet Monitor)
FW_NORMAL = 'normal'
FW_MEDIUM = '500'
FW_SEMIBOLD = '600'

# Compact log header stack (connection row + file tabs + split/filter toolbar)
LOG_TOOLBAR_CTRL_H = 28
LOG_TOOLBAR_BTN_START_H = 28
LOG_CONTROL_PANEL_MAX_H = 44
LOG_SPLIT_TOOLBAR_H = 34
LOG_FILTER_SCROLL_H = 28
CTRL_MIN_H_COMBO = 22
CTRL_MIN_H_INPUT = 20


def ui_font_css(size_pt: int, weight: str = FW_NORMAL, *, family: str | None = None) -> str:
    fam = family or FONT_FAMILY_UI
    return f'font-family: {fam}; font-size: {size_pt}pt; font-weight: {weight};'


def status_bar_stylesheet() -> str:
    return f"""
QStatusBar {{
    background: {PANEL_BG};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
    {ui_font_css(FS_CAPTION, FW_NORMAL)}
    padding: 3px 6px;
}}
QStatusBar QLabel {{
    background: transparent;
    {ui_font_css(FS_CAPTION, FW_NORMAL)}
    padding: 0 8px;
}}
"""


def menu_bar_stylesheet() -> str:
    return f"""
QMenuBar {{
    background: #111827;
    color: {TEXT_SECONDARY};
    border-bottom: 1px solid {BORDER};
    {ui_font_css(FS_BODY, FW_NORMAL)}
    padding: 2px 0;
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: #243049;
    color: {TEXT_PRIMARY};
}}
QMenu {{
    background: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px 0;
    {ui_font_css(FS_BODY, FW_NORMAL)}
}}
QMenu::item {{
    padding: 6px 28px 6px 20px;
}}
QMenu::item:selected {{
    background: #0284C7;
}}
QMenu::indicator {{
    width: 16px;
    height: 16px;
    margin-left: 6px;
}}
"""


def apply_status_message_style(label: QLabel, color: str, *, weight: str = FW_NORMAL) -> None:
    label.setStyleSheet(f'color: {color}; padding: 0 8px; {ui_font_css(FS_CAPTION, weight)}')


def apply_status_session_style(label: QLabel) -> None:
    apply_status_message_style(label, '#7DD3FC', weight=FW_MEDIUM)


# LCD 数值色（高亮，与深底强对比）
LCD_VOLTAGE = '#FFEB3B'
LCD_CURRENT = '#69F0AE'
LCD_POWER = '#EA80FC'
LCD_TEMP = '#FFB74D'
LCD_BATTERY = '#64FFDA'

# Tab strip (shared palette)
TAB_INACTIVE_BG = '#151D2E'
TAB_BORDER = '#334155'
TAB_ACCENT = '#38BDF8'
TAB_HOVER_BG = '#243049'
TAB_INACTIVE_TEXT = '#94A3B8'

# 图表
CHART_BG = '#0B1220'
CHART_AXIS = '#94A3B8'
CHART_TEXT = '#F1F5F9'
CHART_POWER = '#E879F9'
CHART_VOLTAGE = '#FFE566'
CHART_CURRENT = '#4ADE80'

LCD_STYLES = {
    'lcd_v_in': LCD_VOLTAGE,
    'lcd_i_in': LCD_CURRENT,
    'lcd_v_out': LCD_VOLTAGE,
    'lcd_i_out': LCD_CURRENT,
    'lcd_power': LCD_POWER,
    'lcd_v_bat': LCD_VOLTAGE,
    'lcd_i_bat': LCD_CURRENT,
    'lcd_temp': LCD_TEMP,
    'lcd_battery': LCD_BATTERY,
}


def lcd_stylesheet(color: str) -> str:
    return (
        f'background-color: {LCD_BG}; color: {color}; '
        f'border: 1px solid {BORDER_STRONG}; border-radius: 4px;'
    )


def apply_lcd_style(lcd: QLCDNumber, digit_color: str, bg_color: str = LCD_BG):
    """QLCDNumber 需通过 Palette + Flat 模式设置数字颜色，仅 CSS 无效。"""
    lcd.setSegmentStyle(QLCDNumber.Flat)
    lcd.setAutoFillBackground(True)
    pal = lcd.palette()
    pal.setColor(QPalette.Window, QColor(bg_color))
    pal.setColor(QPalette.WindowText, QColor(digit_color))
    lcd.setPalette(pal)
    lcd.setStyleSheet(
        f'background-color: {bg_color}; color: {digit_color}; '
        f'border: 1px solid {BORDER_STRONG}; border-radius: 4px;'
    )


def apply_log_tool_label_style(label: QLabel, *, muted=True):
    """报文监控顶部工具栏字段名：次级 caption，不抢主标题视觉。"""
    label.setObjectName('log_tool_label')
    label.setAutoFillBackground(False)
    color = TEXT_MUTED if muted else TEXT_SECONDARY
    pal = label.palette()
    pal.setColor(QPalette.WindowText, QColor(color))
    label.setPalette(pal)
    label.setStyleSheet(
        f'color: {color}; background-color: transparent; '
        f'{ui_font_css(FS_CAPTION, FW_MEDIUM)} padding: 0 4px;'
    )


def apply_log_split_filter_label_style(label: QLabel):
    """分窗筛选行标签。"""
    label.setObjectName('log_split_filter_label')
    label.setAutoFillBackground(False)
    label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    pal = label.palette()
    pal.setColor(QPalette.WindowText, QColor(TEXT_SECONDARY))
    label.setPalette(pal)
    label.setStyleSheet(
        f'color: {TEXT_MUTED}; background-color: transparent; '
        f'{ui_font_css(FS_CAPTION, FW_MEDIUM)} padding: 0;'
    )


def apply_log_split_column_title_style(label: QLabel):
    """同页分窗列标题。"""
    label.setObjectName('log_split_column_title')
    label.setAutoFillBackground(False)
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    pal = label.palette()
    pal.setColor(QPalette.WindowText, QColor(TEXT_PRIMARY))
    label.setPalette(pal)
    label.setStyleSheet(
        f'color: {TEXT_SECONDARY}; background-color: transparent; '
        f'{ui_font_css(FS_CAPTION, FW_SEMIBOLD)} padding: 2px 4px;'
    )


def apply_log_split_checkbox_style(checkbox: QCheckBox):
    checkbox.setObjectName('log_split_chk')
    pal = checkbox.palette()
    pal.setColor(QPalette.WindowText, QColor(TEXT_SECONDARY))
    pal.setColor(QPalette.Text, QColor(TEXT_SECONDARY))
    checkbox.setPalette(pal)
    checkbox.setStyleSheet(
        f'QCheckBox#log_split_chk {{ color: {TEXT_SECONDARY}; '
        f'{ui_font_css(FS_CAPTION, FW_MEDIUM)} spacing: 4px; }}'
        f'QCheckBox#log_split_chk::indicator {{ width: 13px; height: 13px; border: 1px solid {BORDER_STRONG}; '
        f'border-radius: 3px; background-color: {SURFACE_BG}; }}'
        f'QCheckBox#log_split_chk::indicator:checked {{ background-color: #0284C7; border-color: #38BDF8; }}'
    )


def apply_log_split_spinbox_style(spinbox: QSpinBox):
    spinbox.setObjectName('log_split_count')
    spinbox.setStyleSheet(
        f'QSpinBox#log_split_count {{ background-color: #243049; border: 1px solid {BORDER}; '
        f'border-radius: 4px; color: {TEXT_PRIMARY}; padding: 1px 4px; min-height: 20px; '
        f'{ui_font_css(FS_CAPTION, FW_NORMAL)} }}'
        f'QSpinBox#log_split_count::up-button, QSpinBox#log_split_count::down-button '
        f'{{ width: 16px; border: none; background-color: #3D526E; }}'
    )


def apply_log_split_line_edit_style(edit: QLineEdit):
    edit.setObjectName('log_split_filter')
    pal = edit.palette()
    pal.setColor(QPalette.Base, QColor('#243049'))
    pal.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.PlaceholderText, QColor(TEXT_MUTED))
    edit.setPalette(pal)
    edit.setStyleSheet(
        f'QLineEdit#log_split_filter {{ background-color: #243049; border: 1px solid {BORDER}; '
        f'border-radius: 4px; color: {TEXT_PRIMARY}; padding: 2px 6px; min-height: 20px; '
        f'{ui_font_css(FS_CAPTION, FW_NORMAL)} }}'
        f'QLineEdit#log_split_filter:focus {{ border: 1px solid #38BDF8; }}'
    )


def apply_log_split_scroll_style(scroll: QScrollArea):
    scroll.setObjectName('log_split_filter_scroll')
    scroll.setStyleSheet(
        'QScrollArea#log_split_filter_scroll { background: transparent; border: none; }'
    )
    scroll.viewport().setAutoFillBackground(True)
    vp_pal = scroll.viewport().palette()
    vp_pal.setColor(QPalette.Background, QColor(SURFACE_BG))
    scroll.viewport().setPalette(vp_pal)


def apply_log_split_host_style(host: QWidget):
    host.setObjectName('log_split_filter_host')
    host.setAutoFillBackground(False)
    host.setStyleSheet('background-color: transparent;')


def apply_log_split_toolbar_style(toolbar: QFrame):
    """分窗工具栏：须显式设置深色底，避免 documentMode/原生样式导致白底白字。"""
    toolbar.setObjectName('log_split_toolbar')
    toolbar.setAutoFillBackground(True)
    pal = toolbar.palette()
    pal.setColor(QPalette.Window, QColor(SURFACE_BG))
    toolbar.setPalette(pal)
    toolbar.setStyleSheet(
        f'QFrame#log_split_toolbar {{ background-color: {SURFACE_BG}; '
        f'border: 1px solid {BORDER}; border-radius: 4px; }}'
    )


def apply_log_pane_style(edit: QPlainTextEdit):
    """报文文本区：显式设置前景/背景色。"""
    edit.setObjectName('log_split_pane')
    edit.setAutoFillBackground(True)
    pal = edit.palette()
    pal.setColor(QPalette.Base, QColor(SURFACE_BG))
    pal.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
    edit.setPalette(pal)
    edit.setStyleSheet(
        f'QPlainTextEdit#log_split_pane {{ background-color: {SURFACE_BG}; color: {TEXT_PRIMARY}; '
        f"border: none; {ui_font_css(FS_BODY, FW_NORMAL, family=FONT_FAMILY_MONO)} "
        'padding: 6px; min-height: 120px; }}'
    )


def apply_data_label_style(label: QLabel, *, compact: bool = False):
    """LCD 上方参数名标签：须显式设置 Palette，否则在深色面板上会发灰。"""
    label.setObjectName('data_label')
    label.setAutoFillBackground(False)
    pal = label.palette()
    pal.setColor(QPalette.WindowText, QColor(TEXT_PRIMARY))
    label.setPalette(pal)
    font_size = FS_CAPTION if compact else FS_BODY
    label.setStyleSheet(
        f'color: {TEXT_PRIMARY}; background-color: transparent; '
        f'{ui_font_css(font_size, FW_MEDIUM)} padding: 2px 0;'
    )


APP_STYLESHEET = f"""
QMainWindow, QWidget#centralwidget {{
    background-color: {CANVAS_BG};
    color: {TEXT_PRIMARY};
    {ui_font_css(FS_BODY, FW_NORMAL)}
}}
QLabel#main_title {{
    {ui_font_css(FS_SUBTITLE, FW_SEMIBOLD)}
    color: {TEXT_PRIMARY};
    padding: 4px 2px;
    background-color: #111827;
    border-radius: 4px;
}}
QGroupBox {{
    {ui_font_css(FS_BODY, FW_SEMIBOLD)}
    color: {TEXT_PRIMARY};
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 8px;
    padding: 10px 5px 5px 5px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: {TEXT_PRIMARY};
}}
QFrame#log_panel, QFrame#chart_panel {{
    background-color: {PANEL_BG};
    border-radius: 12px;
}}
QWidget#side_content {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
}}
QScrollArea#side_scroll {{
    background-color: {PANEL_BG};
    border: none;
}}
QScrollBar:vertical {{
    background: {PANEL_BG};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
    border-radius: 4px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QLabel#data_label {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    {ui_font_css(FS_BODY, FW_MEDIUM)}
    padding: 2px 0;
}}
QLCDNumber {{
    background-color: {LCD_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
}}
QComboBox {{
    background-color: #243049;
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_PRIMARY};
    padding: 1px 6px;
    min-height: {CTRL_MIN_H_COMBO}px;
    {ui_font_css(FS_BODY, FW_NORMAL)}
}}
QComboBox QAbstractItemView {{
    background-color: #243049;
    color: {TEXT_PRIMARY};
    selection-background-color: #0284C7;
    selection-color: #FFFFFF;
}}
QComboBox:editable {{
    background-color: #243049;
}}
QComboBox QLineEdit {{
    background-color: #243049;
    color: {TEXT_PRIMARY};
    border: none;
    border-radius: 0;
    padding: 0 2px;
    min-height: 0;
    selection-background-color: #0284C7;
    selection-color: #FFFFFF;
}}
QLineEdit {{
    background-color: #243049;
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_PRIMARY};
    padding: 2px 6px;
    min-height: {CTRL_MIN_H_INPUT}px;
    {ui_font_css(FS_BODY, FW_NORMAL)}
}}
QLineEdit:focus {{
    border: 1px solid #38BDF8;
}}
QPushButton {{
    {ui_font_css(FS_BODY, FW_SEMIBOLD)}
    border-radius: 5px;
    padding: 4px 10px;
    color: {TEXT_PRIMARY};
    border: none;
    background-color: #3D526E;
}}
QPushButton#btn_start {{
    background-color: #0284C7;
    color: #FFFFFF;
    padding: 3px 10px;
    min-height: 0;
    {ui_font_css(FS_BODY, FW_SEMIBOLD)}
}}
QPushButton#btn_stop {{
    background-color: #475569;
    color: #FFFFFF;
}}
QPushButton#btn_stop:disabled {{
    background-color: #334155;
    color: {TEXT_MUTED};
}}
QPushButton#btn_log_tool {{
    background-color: #3D526E;
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 2px 8px;
    {ui_font_css(FS_CAPTION, FW_MEDIUM)}
    color: {TEXT_SECONDARY};
    min-height: 0;
}}
QPushButton#btn_log_tool:hover {{
    background-color: #52657A;
    color: {TEXT_PRIMARY};
}}
QPushButton:hover {{
    background-color: #52657A;
}}
QPushButton#btn_start:hover {{
    background-color: #0369A1;
}}
QPlainTextEdit {{
    background-color: {SURFACE_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    {ui_font_css(FS_BODY, FW_NORMAL, family=FONT_FAMILY_MONO)}
    padding: 6px;
    selection-background-color: #0369A1;
    selection-color: #FFFFFF;
}}
QToolTip {{
    color: {TEXT_PRIMARY};
    background-color: #1E293B;
    border: 1px solid #38BDF8;
    border-radius: 6px;
    padding: 8px 10px;
    {ui_font_css(FS_CAPTION, FW_NORMAL)}
}}
"""


def _tab_close_button_styles(scope: str) -> str:
    return f"""
{scope} QTabBar::close-button {{
    subcontrol-position: right;
    subcontrol-origin: padding;
    width: 12px;
    height: 12px;
    margin-left: 6px;
    border-radius: 6px;
    background: transparent;
}}
{scope} QTabBar::close-button:hover {{
    background: #475569;
}}
{scope} QTabBar::close-button:pressed {{
    background: #64748B;
}}
"""


def _tab_strip_styles(scope: str, pane_bg: str, *, font_weight: str = FW_MEDIUM) -> str:
    """Unified tab bar styling for main / file / split tab widgets."""
    return f"""
{scope} QTabBar {{
    background: transparent;
}}
{scope} QTabBar::tab {{
    background: {TAB_INACTIVE_BG};
    color: {TAB_INACTIVE_TEXT};
    border: 1px solid {TAB_BORDER};
    border-bottom: none;
    border-top: 2px solid transparent;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 4px 14px 5px 14px;
    min-height: 18px;
    margin-right: 3px;
    {ui_font_css(FS_BODY, font_weight)}
}}
{scope} QTabBar::tab:selected {{
    background: {pane_bg};
    color: {TEXT_PRIMARY};
    border: 1px solid {TAB_ACCENT};
    border-top: 2px solid {TAB_ACCENT};
    border-bottom: 1px solid {pane_bg};
    padding-bottom: 4px;
    margin-bottom: -1px;
}}
{scope} QTabBar::tab:hover {{
    background: {TAB_HOVER_BG};
    color: {TEXT_SECONDARY};
}}
{scope} QTabBar::tab:selected:hover {{
    background: {pane_bg};
    color: {TEXT_PRIMARY};
}}
{_tab_close_button_styles(scope)}
"""


def _monitor_widget_styles() -> str:
    """控件级样式：与 loader 运行时一致，供 Qt Designer 预览。"""
    lcd_rules = '\n'.join(
        f'QLCDNumber#{name} {{ background-color: {LCD_BG}; color: {color}; '
        f'border: 1px solid {BORDER_STRONG}; border-radius: 4px; '
        f'min-height: 32px; max-height: 36px; }}'
        for name, color in LCD_STYLES.items()
    )
    return f"""
QTabWidget#main_tabs {{
    background-color: {CANVAS_BG};
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {PANEL_BG};
    top: -1px;
}}
{_tab_strip_styles('QTabWidget#main_tabs', PANEL_BG, font_weight=FW_SEMIBOLD)}
QScrollArea#chart_lcd_scroll {{
    background-color: {PANEL_BG};
    border: none;
    border-right: 1px solid {BORDER};
}}
QFrame#log_control_panel {{
    background-color: {PANEL_BG};
    border: none;
    border-bottom: 1px solid {BORDER};
}}
QTabWidget#log_file_tabs {{
    background-color: {PANEL_BG};
}}
QTabWidget#log_file_tabs::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {SURFACE_BG};
    top: -1px;
}}
{_tab_strip_styles('QTabWidget#log_file_tabs', SURFACE_BG, font_weight=FW_MEDIUM)}
QTabWidget#log_file_tabs QPlainTextEdit {{
    background-color: {SURFACE_BG};
    color: {TEXT_PRIMARY};
    border: none;
    {ui_font_css(FS_BODY, FW_NORMAL, family=FONT_FAMILY_MONO)}
    padding: 6px;
}}
QFrame#chart_panel, QFrame#log_panel {{
    border: none;
}}
QLabel#log_tool_label {{
    color: {TEXT_MUTED};
    background-color: transparent;
    {ui_font_css(FS_CAPTION, FW_MEDIUM)}
    padding: 0 4px;
}}
QWidget#log_tab_page {{
    background-color: transparent;
}}
QFrame#log_split_toolbar {{
    background-color: {SURFACE_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QWidget#log_split_filter_host {{
    background-color: transparent;
}}
QCheckBox#log_split_chk {{
    color: {TEXT_SECONDARY};
    {ui_font_css(FS_CAPTION, FW_MEDIUM)}
    spacing: 4px;
    padding: 0 2px;
}}
QCheckBox#log_split_chk::indicator {{
    width: 13px;
    height: 13px;
    border: 1px solid {BORDER_STRONG};
    border-radius: 3px;
    background-color: {PANEL_BG};
}}
QCheckBox#log_split_chk::indicator:checked {{
    background-color: #0284C7;
    border-color: #38BDF8;
}}
QLabel#log_split_filter_label {{
    color: {TEXT_MUTED};
    background-color: transparent;
    {ui_font_css(FS_CAPTION, FW_MEDIUM)}
    padding: 0;
}}
QSpinBox#log_split_count {{
    background-color: #243049;
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_PRIMARY};
    padding: 1px 4px;
    min-height: 20px;
    {ui_font_css(FS_CAPTION, FW_NORMAL)}
}}
QSpinBox#log_split_count::up-button, QSpinBox#log_split_count::down-button {{
    width: 16px;
    border: none;
    background-color: #3D526E;
}}
QLineEdit#log_split_filter {{
    background-color: #243049;
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_PRIMARY};
    padding: 2px 6px;
    min-height: 20px;
    {ui_font_css(FS_CAPTION, FW_NORMAL)}
}}
QLineEdit#log_split_filter:focus {{
    border: 1px solid #38BDF8;
}}
QScrollArea#log_split_filter_scroll {{
    background: transparent;
    border: none;
}}
QFrame#log_split_same_page {{
    background-color: transparent;
    border: none;
}}
QStackedWidget#log_split_view_stack {{
    background-color: transparent;
}}
QFrame#log_split_column {{
    background-color: {SURFACE_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QLabel#log_split_column_title {{
    color: {TEXT_SECONDARY};
    background-color: transparent;
    {ui_font_css(FS_CAPTION, FW_SEMIBOLD)}
    padding: 2px 4px;
}}
QPlainTextEdit#log_split_pane {{
    background-color: {SURFACE_BG};
    color: {TEXT_PRIMARY};
    border: none;
    border-top: 1px solid {BORDER};
    border-radius: 0;
    {ui_font_css(FS_BODY, FW_NORMAL, family=FONT_FAMILY_MONO)}
    padding: 6px;
    min-height: 120px;
}}
QSplitter#log_split_same_page::handle {{
    background-color: {BORDER};
    width: 4px;
    margin: 2px 0;
}}
QTabWidget#log_split_tabs::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background-color: {SURFACE_BG};
    top: -1px;
}}
{_tab_strip_styles('QTabWidget#log_split_tabs', SURFACE_BG, font_weight=FW_MEDIUM)}
QWidget#chart_container {{
    background-color: {CHART_BG};
    min-height: 480px;
}}
QLabel#chart_placeholder {{
    color: {TEXT_MUTED};
    {ui_font_css(FS_BODY, FW_NORMAL)}
    padding: 24px;
    background-color: transparent;
}}
{lcd_rules}
"""


def apply_log_toolbar_button_style(button: QPushButton) -> None:
    """Secondary log toolbar buttons — caption tier; objectName must be btn_log_tool for QSS."""
    button.setObjectName('btn_log_tool')
    button.style().unpolish(button)
    button.style().polish(button)


def apply_editable_combo_line_edit(combo: QComboBox) -> None:
    """Editable QComboBox embeds a QLineEdit that may ignore global QSS on Windows."""
    line_edit = combo.lineEdit()
    if line_edit is None:
        return
    line_edit.setFrame(False)
    pal = line_edit.palette()
    pal.setColor(QPalette.Base, QColor('#243049'))
    pal.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.Highlight, QColor('#0284C7'))
    pal.setColor(QPalette.HighlightedText, QColor('#FFFFFF'))
    line_edit.setPalette(pal)
    line_edit.setAutoFillBackground(True)


def apply_log_toolbar_control_height(widget, *, primary=False, scale: float = 1.0) -> None:
    """Fix log connection-row control height for a single compact toolbar line."""
    base = LOG_TOOLBAR_BTN_START_H if primary else LOG_TOOLBAR_CTRL_H
    widget.setFixedHeight(int(base * scale))


def apply_log_control_panel_metrics(ui, scale: float = 1.0) -> None:
    """Apply compact vertical metrics to the log monitor connection toolbar."""
    panel = getattr(ui, 'log_control_panel', None)
    if panel is not None:
        panel.setMaximumHeight(int(LOG_CONTROL_PANEL_MAX_H * scale))
    for name in ('btn_new_live_log', 'btn_browse_log_dir', 'btn_open_log'):
        widget = getattr(ui, name, None)
        if widget is not None:
            apply_log_toolbar_button_style(widget)
    for name in (
        'cb_port', 'cb_baudrate', 'edit_live_log_name', 'edit_live_log_dir',
        'btn_new_live_log', 'btn_browse_log_dir', 'btn_open_log',
    ):
        widget = getattr(ui, name, None)
        if widget is not None:
            apply_log_toolbar_control_height(widget, scale=scale)
    btn_start = getattr(ui, 'btn_start', None)
    if btn_start is not None:
        apply_log_toolbar_control_height(btn_start, primary=True, scale=scale)
    layout = panel.layout() if panel is not None else None
    if layout is not None:
        m = int(4 * scale)
        layout.setContentsMargins(int(8 * scale), m, int(8 * scale), m)
        layout.setSpacing(int(6 * scale))


# Qt Designer 与运行时共用（单一来源）
MONITOR_WINDOW_STYLESHEET = APP_STYLESHEET + _monitor_widget_styles()
