"""高对比度 UI 主题（深色 / 浅色可切换）。"""

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

from .theme_palette import active_tokens, get_theme, set_theme as _set_palette_theme

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
LOG_CONTROL_PANEL_WIDTH = 140
LOG_SPLIT_TOOLBAR_H = 34
LOG_FILTER_SCROLL_H = 28
CTRL_MIN_H_COMBO = 22
CTRL_MIN_H_INPUT = 20

# Runtime color tokens (updated by set_theme / init_theme)
TEXT_PRIMARY = '#FFFFFF'
TEXT_SECONDARY = '#F1F5F9'
TEXT_MUTED = '#CBD5E1'
LABEL_ACCENT = '#FFFFFF'
CANVAS_BG = '#0B1220'
PANEL_BG = '#162032'
SURFACE_BG = '#1A2332'
LCD_BG = '#070B14'
BORDER = '#8BA3BD'
BORDER_STRONG = '#C7D2E0'
HEADER_BG = '#111827'
INPUT_BG = '#243049'
INPUT_BTN_BG = '#3D526E'
BUTTON_BG = '#3D526E'
BUTTON_HOVER = '#52657A'
ACCENT = '#0284C7'
ACCENT_HOVER = '#0369A1'
ACCENT_BORDER = '#38BDF8'
ACCENT_TEXT = '#FFFFFF'
TOOLTIP_BG = '#1E293B'
TOOLTIP_BORDER = '#38BDF8'
MENU_ITEM_HOVER = '#243049'
SETTINGS_BTN_HOVER = '#243049'
TAB_INACTIVE_BG = '#151D2E'
TAB_BORDER = '#334155'
TAB_ACCENT = '#38BDF8'
TAB_HOVER_BG = '#243049'
TAB_INACTIVE_TEXT = '#94A3B8'
TAB_CLOSE_HOVER = '#475569'
TAB_CLOSE_PRESSED = '#64748B'
CHART_BG = '#0B1220'
CHART_AXIS = '#94A3B8'
CHART_TEXT = '#F1F5F9'
CHART_POWER = '#E879F9'
CHART_VOLTAGE = '#FFE566'
CHART_CURRENT = '#4ADE80'
LCD_VOLTAGE = '#FFEB3B'
LCD_CURRENT = '#69F0AE'
LCD_POWER = '#EA80FC'
LCD_TEMP = '#FFB74D'
LCD_BATTERY = '#64FFDA'
STATUS_SESSION = '#7DD3FC'
STATUS_INFO = '#BAE6FD'
STATUS_WARN = '#FDE047'
STATUS_ERROR = '#FCA5A5'
STATUS_SUCCESS = '#86EFAC'
SELECTION_BG = '#0284C7'
SELECTION_TEXT = '#FFFFFF'
BTN_STOP_BG = '#475569'
BTN_STOP_DISABLED_BG = '#334155'
HUD_BG_RGBA = 'rgba(15, 23, 42, 250)'
HUD_BORDER = '#38BDF8'
HUD_TEXT = '#FFFFFF'
CROSSHAIR_COLOR = '#38BDF8'
TEMP_ALERT_BG = '#450A0A'
TEMP_ALERT_FG = '#FECACA'
TEMP_ALERT_BORDER = '#EF4444'
TEMP_NORMAL_BORDER = '#5B6B7C'
FILTER_HIGHLIGHT = '#FACC15'
LCD_STYLES: dict[str, str] = {}


def _sync_exports() -> None:
    global TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, LABEL_ACCENT
    global CANVAS_BG, PANEL_BG, SURFACE_BG, LCD_BG, BORDER, BORDER_STRONG
    global HEADER_BG, INPUT_BG, INPUT_BTN_BG, BUTTON_BG, BUTTON_HOVER
    global ACCENT, ACCENT_HOVER, ACCENT_BORDER, ACCENT_TEXT
    global TOOLTIP_BG, TOOLTIP_BORDER, MENU_ITEM_HOVER, SETTINGS_BTN_HOVER
    global TAB_INACTIVE_BG, TAB_BORDER, TAB_ACCENT, TAB_HOVER_BG, TAB_INACTIVE_TEXT
    global TAB_CLOSE_HOVER, TAB_CLOSE_PRESSED
    global CHART_BG, CHART_AXIS, CHART_TEXT, CHART_POWER, CHART_VOLTAGE, CHART_CURRENT
    global LCD_VOLTAGE, LCD_CURRENT, LCD_POWER, LCD_TEMP, LCD_BATTERY
    global STATUS_SESSION, STATUS_INFO, STATUS_WARN, STATUS_ERROR, STATUS_SUCCESS
    global SELECTION_BG, SELECTION_TEXT, BTN_STOP_BG, BTN_STOP_DISABLED_BG
    global HUD_BG_RGBA, HUD_BORDER, HUD_TEXT, CROSSHAIR_COLOR
    global TEMP_ALERT_BG, TEMP_ALERT_FG, TEMP_ALERT_BORDER, TEMP_NORMAL_BORDER, FILTER_HIGHLIGHT
    global LCD_STYLES

    t = active_tokens()
    TEXT_PRIMARY = t.TEXT_PRIMARY
    TEXT_SECONDARY = t.TEXT_SECONDARY
    TEXT_MUTED = t.TEXT_MUTED
    LABEL_ACCENT = t.TEXT_PRIMARY
    CANVAS_BG = t.CANVAS_BG
    PANEL_BG = t.PANEL_BG
    SURFACE_BG = t.SURFACE_BG
    LCD_BG = t.LCD_BG
    BORDER = t.BORDER
    BORDER_STRONG = t.BORDER_STRONG
    HEADER_BG = t.HEADER_BG
    INPUT_BG = t.INPUT_BG
    INPUT_BTN_BG = t.INPUT_BTN_BG
    BUTTON_BG = t.BUTTON_BG
    BUTTON_HOVER = t.BUTTON_HOVER
    ACCENT = t.ACCENT
    ACCENT_HOVER = t.ACCENT_HOVER
    ACCENT_BORDER = t.ACCENT_BORDER
    ACCENT_TEXT = t.ACCENT_TEXT
    TOOLTIP_BG = t.TOOLTIP_BG
    TOOLTIP_BORDER = t.TOOLTIP_BORDER
    MENU_ITEM_HOVER = t.MENU_ITEM_HOVER
    SETTINGS_BTN_HOVER = t.SETTINGS_BTN_HOVER
    TAB_INACTIVE_BG = t.TAB_INACTIVE_BG
    TAB_BORDER = t.TAB_BORDER
    TAB_ACCENT = t.TAB_ACCENT
    TAB_HOVER_BG = t.TAB_HOVER_BG
    TAB_INACTIVE_TEXT = t.TAB_INACTIVE_TEXT
    TAB_CLOSE_HOVER = t.TAB_CLOSE_HOVER
    TAB_CLOSE_PRESSED = t.TAB_CLOSE_PRESSED
    CHART_BG = t.CHART_BG
    CHART_AXIS = t.CHART_AXIS
    CHART_TEXT = t.CHART_TEXT
    CHART_POWER = t.CHART_POWER
    CHART_VOLTAGE = t.CHART_VOLTAGE
    CHART_CURRENT = t.CHART_CURRENT
    LCD_VOLTAGE = t.LCD_VOLTAGE
    LCD_CURRENT = t.LCD_CURRENT
    LCD_POWER = t.LCD_POWER
    LCD_TEMP = t.LCD_TEMP
    LCD_BATTERY = t.LCD_BATTERY
    STATUS_SESSION = t.STATUS_SESSION
    STATUS_INFO = t.STATUS_INFO
    STATUS_WARN = t.STATUS_WARN
    STATUS_ERROR = t.STATUS_ERROR
    STATUS_SUCCESS = t.STATUS_SUCCESS
    SELECTION_BG = t.SELECTION_BG
    SELECTION_TEXT = t.SELECTION_TEXT
    BTN_STOP_BG = t.BTN_STOP_BG
    BTN_STOP_DISABLED_BG = t.BTN_STOP_DISABLED_BG
    HUD_BG_RGBA = t.HUD_BG_RGBA
    HUD_BORDER = t.HUD_BORDER
    HUD_TEXT = t.HUD_TEXT
    CROSSHAIR_COLOR = t.CROSSHAIR_COLOR
    TEMP_ALERT_BG = t.TEMP_ALERT_BG
    TEMP_ALERT_FG = t.TEMP_ALERT_FG
    TEMP_ALERT_BORDER = t.TEMP_ALERT_BORDER
    TEMP_NORMAL_BORDER = t.TEMP_NORMAL_BORDER
    FILTER_HIGHLIGHT = t.FILTER_HIGHLIGHT
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


def set_theme(name: str | None) -> str:
    theme = _set_palette_theme(name)
    _sync_exports()
    return theme


def init_theme(name: str | None = None) -> str:
    return set_theme(name or 'dark')


def full_stylesheet() -> str:
    return _build_app_stylesheet() + menu_popup_stylesheet() + _monitor_widget_styles()


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


def menu_popup_stylesheet() -> str:
    """Popup menus (Settings corner button, submenus) — not covered by hidden menu bar."""
    return f"""
QMenu {{
    background: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px 0;
    {ui_font_css(FS_BODY, FW_NORMAL)}
}}
QMenu::item {{
    padding: 6px 28px 6px 20px;
    color: {TEXT_PRIMARY};
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: {ACCENT_TEXT};
}}
QMenu::indicator {{
    width: 14px;
    height: 14px;
    margin-left: 8px;
    border: 1px solid {BORDER_STRONG};
    border-radius: 3px;
    background: {INPUT_BG};
}}
QMenu::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT_BORDER};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}
"""


def menu_bar_stylesheet() -> str:
    return f"""
QMenuBar {{
    background: {HEADER_BG};
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
    background: {MENU_ITEM_HOVER};
    color: {TEXT_PRIMARY};
}}
{menu_popup_stylesheet()}
"""


def apply_status_message_style(label: QLabel, color: str, *, weight: str = FW_NORMAL) -> None:
    label.setStyleSheet(f'color: {color}; padding: 0 8px; {ui_font_css(FS_CAPTION, weight)}')


def apply_status_session_style(label: QLabel) -> None:
    apply_status_message_style(label, STATUS_SESSION, weight=FW_MEDIUM)


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
        f'QCheckBox#log_split_chk::indicator:checked {{ background-color: {ACCENT}; border-color: {ACCENT_BORDER}; }}'
    )


def apply_log_split_spinbox_style(spinbox: QSpinBox):
    spinbox.setObjectName('log_split_count')
    spinbox.setStyleSheet(
        f'QSpinBox#log_split_count {{ background-color: {INPUT_BG}; border: 1px solid {BORDER}; '
        f'border-radius: 4px; color: {TEXT_PRIMARY}; padding: 1px 4px; min-height: 20px; '
        f'{ui_font_css(FS_CAPTION, FW_NORMAL)} }}'
        f'QSpinBox#log_split_count::up-button, QSpinBox#log_split_count::down-button '
        f'{{ width: 16px; border: none; background-color: {INPUT_BTN_BG}; }}'
    )


def apply_log_split_line_edit_style(edit: QLineEdit):
    edit.setObjectName('log_split_filter')
    pal = edit.palette()
    pal.setColor(QPalette.Base, QColor(INPUT_BG))
    pal.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.PlaceholderText, QColor(TEXT_MUTED))
    edit.setPalette(pal)
    edit.setStyleSheet(
        f'QLineEdit#log_split_filter {{ background-color: {INPUT_BG}; border: 1px solid {BORDER}; '
        f'border-radius: 4px; color: {TEXT_PRIMARY}; padding: 2px 6px; min-height: 20px; '
        f'{ui_font_css(FS_CAPTION, FW_NORMAL)} }}'
        f'QLineEdit#log_split_filter:focus {{ border: 1px solid {ACCENT_BORDER}; }}'
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
    apply_text_edit_palette(edit)
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


def _build_app_stylesheet() -> str:
    return f"""
QMainWindow, QWidget#centralwidget {{
    background-color: {CANVAS_BG};
    color: {TEXT_PRIMARY};
    {ui_font_css(FS_BODY, FW_NORMAL)}
}}
QWidget {{
    color: {TEXT_PRIMARY};
}}
QLabel#main_title {{
    {ui_font_css(FS_SUBTITLE, FW_SEMIBOLD)}
    color: {TEXT_PRIMARY};
    padding: 4px 2px;
    background-color: {HEADER_BG};
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
QFrame#log_panel, QFrame#chart_panel, QFrame#tektronix_panel {{
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
    background-color: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_PRIMARY};
    padding: 1px 6px;
    min-height: {CTRL_MIN_H_COMBO}px;
    {ui_font_css(FS_BODY, FW_NORMAL)}
}}
QComboBox QAbstractItemView {{
    background-color: {INPUT_BG};
    color: {TEXT_PRIMARY};
    selection-background-color: {SELECTION_BG};
    selection-color: {SELECTION_TEXT};
}}
QComboBox:editable {{
    background-color: {INPUT_BG};
}}
QComboBox QLineEdit {{
    background-color: {INPUT_BG};
    color: {TEXT_PRIMARY};
    border: none;
    border-radius: 0;
    padding: 0 2px;
    min-height: 0;
    selection-background-color: {SELECTION_BG};
    selection-color: {SELECTION_TEXT};
}}
QLineEdit {{
    background-color: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_PRIMARY};
    padding: 2px 6px;
    min-height: {CTRL_MIN_H_INPUT}px;
    {ui_font_css(FS_BODY, FW_NORMAL)}
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT_BORDER};
}}
QPushButton {{
    {ui_font_css(FS_BODY, FW_SEMIBOLD)}
    border-radius: 5px;
    padding: 4px 10px;
    color: {TEXT_PRIMARY};
    border: none;
    background-color: {BUTTON_BG};
}}
QPushButton#btn_start {{
    background-color: {ACCENT};
    color: {ACCENT_TEXT};
    padding: 3px 10px;
    min-height: 0;
    {ui_font_css(FS_BODY, FW_SEMIBOLD)}
}}
QPushButton#btn_stop {{
    background-color: {BTN_STOP_BG};
    color: {ACCENT_TEXT};
}}
QPushButton#btn_stop:disabled {{
    background-color: {BTN_STOP_DISABLED_BG};
    color: {TEXT_MUTED};
}}
QPushButton#btn_log_tool {{
    background-color: {BUTTON_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 2px 8px;
    {ui_font_css(FS_CAPTION, FW_MEDIUM)}
    color: {TEXT_SECONDARY};
    min-height: 0;
}}
QPushButton#btn_log_tool:hover {{
    background-color: {BUTTON_HOVER};
    color: {TEXT_PRIMARY};
}}
QPushButton:hover {{
    background-color: {BUTTON_HOVER};
}}
QPushButton#btn_start:hover {{
    background-color: {ACCENT_HOVER};
}}
QPlainTextEdit {{
    background-color: {SURFACE_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    {ui_font_css(FS_BODY, FW_NORMAL, family=FONT_FAMILY_MONO)}
    padding: 6px;
    selection-background-color: {ACCENT_HOVER};
    selection-color: {SELECTION_TEXT};
}}
QTextEdit {{
    background-color: {SURFACE_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    {ui_font_css(FS_BODY, FW_NORMAL, family=FONT_FAMILY_MONO)}
    padding: 6px;
    selection-background-color: {ACCENT_HOVER};
    selection-color: {SELECTION_TEXT};
}}
QToolTip {{
    color: {TEXT_PRIMARY};
    background-color: {TOOLTIP_BG};
    border: 1px solid {TOOLTIP_BORDER};
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
    background: {TAB_CLOSE_HOVER};
}}
{scope} QTabBar::close-button:pressed {{
    background: {TAB_CLOSE_PRESSED};
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
QToolButton#settings_menu_btn {{
    background: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    border-radius: 4px;
    padding: 4px 12px 5px 12px;
    margin: 2px 6px 0 4px;
    {ui_font_css(FS_BODY, FW_NORMAL)}
}}
QToolButton#settings_menu_btn:hover {{
    background: {SETTINGS_BTN_HOVER};
    color: {TEXT_PRIMARY};
}}
QToolButton#settings_menu_btn::menu-indicator {{
    image: none;
    width: 0;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {PANEL_BG};
    top: -1px;
}}
{_tab_strip_styles('QTabWidget#main_tabs', PANEL_BG, font_weight=FW_SEMIBOLD)}
QTabWidget#main_tabs QTabBar {{
    background: {HEADER_BG};
    border-bottom: 1px solid {BORDER};
}}
QScrollArea#chart_lcd_scroll {{
    background-color: {PANEL_BG};
    border: none;
    border-right: 1px solid {BORDER};
}}
QFrame#log_control_panel {{
    background-color: {PANEL_BG};
    border: none;
    border-right: 1px solid {BORDER};
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
QFrame#chart_panel, QFrame#log_panel, QFrame#tektronix_panel {{
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
    background-color: {ACCENT};
    border-color: {ACCENT_BORDER};
}}
QLabel#log_split_filter_label {{
    color: {TEXT_MUTED};
    background-color: transparent;
    {ui_font_css(FS_CAPTION, FW_MEDIUM)}
    padding: 0;
}}
QSpinBox#log_split_count {{
    background-color: {INPUT_BG};
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
    background-color: {INPUT_BTN_BG};
}}
QLineEdit#log_split_filter {{
    background-color: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_PRIMARY};
    padding: 2px 6px;
    min-height: 20px;
    {ui_font_css(FS_CAPTION, FW_NORMAL)}
}}
QLineEdit#log_split_filter:focus {{
    border: 1px solid {ACCENT_BORDER};
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
QWidget#TektronixScopePanel {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
}}
QLineEdit#tek_scope_model {{
    background-color: {INPUT_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    {ui_font_css(FS_BODY, FW_SEMIBOLD)}
    padding: 2px 6px;
}}
QTextEdit#tek_scope_log {{
    background-color: {SURFACE_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    {ui_font_css(FS_BODY, FW_NORMAL)}
}}
QLabel#tek_scope_preview {{
    background-color: {CHART_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_MUTED};
}}
{lcd_rules}
"""


def apply_widget_surface_bg(widget: QWidget, color: str | None = None) -> None:
    """Panel/surface background via palette (stylesheet alone is unreliable after tab rebuild)."""
    bg = color or PANEL_BG
    widget.setAutoFillBackground(True)
    pal = widget.palette()
    pal.setColor(QPalette.Window, QColor(bg))
    pal.setColor(QPalette.WindowText, QColor(TEXT_PRIMARY))
    widget.setPalette(pal)


def apply_log_control_panel_theme(ui) -> None:
    """Serial tool left sidebar — palettes must be refreshed after main tab bar rebuild."""
    panel = getattr(ui, 'log_control_panel', None)
    if panel is None:
        return
    apply_widget_surface_bg(panel, PANEL_BG)
    panel.setStyleSheet(
        f'QFrame#log_control_panel {{ background-color: {PANEL_BG}; border: none; '
        f'border-right: 1px solid {BORDER}; }}'
    )
    log_panel = getattr(ui, 'log_panel', None)
    if log_panel is not None:
        apply_widget_surface_bg(log_panel, PANEL_BG)
    for name in ('cb_port', 'cb_baudrate'):
        combo = getattr(ui, name, None)
        if combo is not None:
            apply_combo_palette(combo)
    for name in ('edit_live_log_name', 'edit_live_log_dir'):
        edit = getattr(ui, name, None)
        if edit is not None:
            apply_line_edit_palette(edit)
    for name in ('lbl_live_log_name', 'lbl_live_log_dir'):
        lbl = getattr(ui, name, None)
        if lbl is not None:
            apply_log_tool_label_style(lbl)
    for name in ('btn_start', 'btn_new_live_log', 'btn_browse_log_dir', 'btn_open_log', 'btn_clear_live_log'):
        btn = getattr(ui, name, None)
        if btn is not None:
            btn.setStyleSheet('')
            btn.style().unpolish(btn)
            btn.style().polish(btn)


def apply_log_toolbar_button_style(button: QPushButton) -> None:
    """Secondary log toolbar buttons — caption tier; objectName must be btn_log_tool for QSS."""
    button.setObjectName('btn_log_tool')
    button.style().unpolish(button)
    button.style().polish(button)


def apply_editable_combo_line_edit(combo: QComboBox) -> None:
    """Editable QComboBox embeds a QLineEdit that may ignore global QSS on Windows."""
    apply_combo_palette(combo)


def apply_combo_palette(combo: QComboBox) -> None:
    """Ensure combo text/background contrast (QSS alone is unreliable on Windows)."""
    combo.setAutoFillBackground(True)
    pal = combo.palette()
    pal.setColor(QPalette.Base, QColor(INPUT_BG))
    pal.setColor(QPalette.Button, QColor(INPUT_BG))
    pal.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.WindowText, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor(ACCENT_TEXT))
    combo.setPalette(pal)
    line_edit = combo.lineEdit()
    if line_edit is not None:
        line_edit.setFrame(False)
        apply_line_edit_palette(line_edit)


def apply_line_edit_palette(line_edit: QLineEdit, *, read_only: bool = False) -> None:
    """Ensure line edit text/background contrast (QSS alone is unreliable on Windows)."""
    pal = line_edit.palette()
    pal.setColor(QPalette.Base, QColor(INPUT_BG))
    pal.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor(ACCENT_TEXT))
    line_edit.setPalette(pal)
    line_edit.setAutoFillBackground(True)
    if read_only:
        line_edit.setFrame(True)


def apply_text_edit_palette(text_edit) -> None:
    """Ensure QTextEdit / QPlainTextEdit contrast (viewport needs palette on Windows)."""
    text_edit.setAutoFillBackground(True)
    pal = text_edit.palette()
    pal.setColor(QPalette.Base, QColor(SURFACE_BG))
    pal.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.WindowText, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor(ACCENT_TEXT))
    text_edit.setPalette(pal)
    viewport = text_edit.viewport() if hasattr(text_edit, 'viewport') else None
    if viewport is not None:
        viewport.setAutoFillBackground(True)
        vp = viewport.palette()
        vp.setColor(QPalette.Base, QColor(SURFACE_BG))
        vp.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
        viewport.setPalette(vp)


def apply_tektronix_scope_theme(panel) -> None:
    """Theme-aware styling for the embedded Tektronix scope panel."""
    panel.setObjectName('TektronixScopePanel')
    # Legacy .ui widgets (optional)
    if hasattr(panel, 'lineEdit') and hasattr(panel.lineEdit, 'setObjectName'):
        try:
            panel.lineEdit.setObjectName('tek_scope_model')
            if hasattr(panel.lineEdit, 'setReadOnly'):
                apply_line_edit_palette(panel.lineEdit, read_only=True)
        except Exception:
            pass
    if hasattr(panel, 'textEdit'):
        panel.textEdit.setObjectName('tek_scope_log')
        try:
            apply_text_edit_palette(panel.textEdit)
        except Exception:
            pass
        panel.textEdit.setStyleSheet('')
    if hasattr(panel, 'label'):
        panel.label.setObjectName('tek_scope_preview')
        panel.label.setStyleSheet('')
    for btn_name in ('pushButton_connect', 'pushButton_save', 'pushButton_save_2'):
        btn = getattr(panel, btn_name, None)
        if btn is not None:
            btn.setStyleSheet('')
            btn.style().unpolish(btn)
            btn.style().polish(btn)
    # Front-panel action buttons — high-contrast labels on dark chrome
    panel.setStyleSheet(
        panel.styleSheet()
        + """
        QPushButton[tekRole="menu"] {
            text-align: left;
            padding: 4px 8px;
            border: 1px solid #64748B;
            border-radius: 3px;
            background: #1E293B;
            color: #FFFFFF;
            font-weight: 600;
        }
        QPushButton[tekRole="menu"]:hover { background: #334155; color: #FFFFFF; }
        QPushButton[tekRole="menu"]:checked {
            background: #0284C7;
            color: #FFFFFF;
        }
        QPushButton[tekRole="action"] {
            padding: 4px 10px;
            border: 1px solid #94A3B8;
            border-radius: 4px;
            background: #334155;
            color: #FFFFFF;
            font-weight: 600;
        }
        QPushButton[tekRole="action"]:hover { background: #475569; color: #FFFFFF; }
        QPushButton[tekRole="action"]:checked {
            background: #B91C1C;
            border-color: #F87171;
            color: #FFFFFF;
        }
        QPushButton[tekRole="accent"] {
            padding: 4px 10px;
            border: 1px solid #7DD3FC;
            border-radius: 4px;
            background: #0369A1;
            color: #FFFFFF;
            font-weight: 700;
        }
        QPushButton[tekRole="accent"]:hover { background: #0284C7; color: #FFFFFF; }
        QPushButton[tekRole="accent"]:checked {
            background: #B91C1C;
            border-color: #FCA5A5;
            color: #FFFFFF;
        }
        QGroupBox {
            border: 1px solid #64748B;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
            color: #FFFFFF;
            font-weight: 700;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: #FFFFFF;
        }
        QComboBox {
            color: #FFFFFF;
            background: #1E293B;
            border: 1px solid #64748B;
            border-radius: 4px;
            padding: 2px 8px;
        }
        QComboBox QAbstractItemView {
            color: #FFFFFF;
            background: #1E293B;
            selection-background-color: #0284C7;
        }
        QToolButton {
            color: #F8FAFC;
            font-weight: 600;
        }
        QLabel {
            color: #F1F5F9;
        }
        """
    )
    panel.style().unpolish(panel)
    panel.style().polish(panel)


def apply_log_toolbar_control_height(widget, *, primary=False, scale: float = 1.0) -> None:
    """Fix log connection-row control height for a single compact toolbar line."""
    base = LOG_TOOLBAR_BTN_START_H if primary else LOG_TOOLBAR_CTRL_H
    widget.setFixedHeight(int(base * scale))


def apply_log_control_panel_metrics(ui, scale: float = 1.0) -> None:
    """Apply compact metrics to the log monitor left sidebar."""
    panel = getattr(ui, 'log_control_panel', None)
    sidebar_w = int(LOG_CONTROL_PANEL_WIDTH * scale)
    if panel is not None:
        panel.setFixedWidth(sidebar_w)
    for name in ('btn_new_live_log', 'btn_browse_log_dir', 'btn_open_log', 'btn_clear_live_log'):
        widget = getattr(ui, name, None)
        if widget is not None:
            apply_log_toolbar_button_style(widget)
    for name in (
        'cb_port', 'cb_baudrate', 'edit_live_log_name', 'edit_live_log_dir',
        'btn_new_live_log', 'btn_clear_live_log', 'btn_browse_log_dir', 'btn_open_log',
    ):
        widget = getattr(ui, name, None)
        if widget is not None:
            apply_log_toolbar_control_height(widget, scale=scale)
    btn_start = getattr(ui, 'btn_start', None)
    if btn_start is not None:
        apply_log_toolbar_control_height(btn_start, primary=True, scale=scale)
    for name in (
        'cb_port', 'cb_baudrate', 'btn_start', 'btn_new_live_log', 'btn_clear_live_log',
        'edit_live_log_name', 'edit_live_log_dir', 'btn_browse_log_dir', 'btn_open_log',
    ):
        widget = getattr(ui, name, None)
        if widget is not None:
            widget.setMinimumWidth(0)
            widget.setMaximumWidth(sidebar_w)
    layout = panel.layout() if panel is not None else None
    if layout is not None:
        m = int(4 * scale)
        layout.setContentsMargins(int(8 * scale), m, int(8 * scale), m)
        layout.setSpacing(int(6 * scale))


# Qt Designer 与运行时共用（单一来源）
set_theme('dark')
MONITOR_WINDOW_STYLESHEET = full_stylesheet()
