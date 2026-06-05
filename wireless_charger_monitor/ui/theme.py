"""高对比度 UI 主题（深色背景 + 高亮文字）。"""

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QLCDNumber, QLabel

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

# LCD 数值色（高亮，与深底强对比）
LCD_VOLTAGE = '#FFEB3B'
LCD_CURRENT = '#69F0AE'
LCD_POWER = '#EA80FC'
LCD_TEMP = '#FFB74D'
LCD_BATTERY = '#64FFDA'

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


def apply_data_label_style(label: QLabel):
    """LCD 上方参数名标签：须显式设置 Palette，否则在深色面板上会发灰。"""
    label.setObjectName('data_label')
    label.setAutoFillBackground(False)
    pal = label.palette()
    pal.setColor(QPalette.WindowText, QColor(TEXT_PRIMARY))
    label.setPalette(pal)
    label.setStyleSheet(
        f'color: {TEXT_PRIMARY}; background-color: transparent; '
        'font-size: 10pt; font-weight: 700; padding: 2px 0;'
    )


APP_STYLESHEET = f"""
QMainWindow, QWidget#centralwidget {{
    background-color: {CANVAS_BG};
    color: {TEXT_PRIMARY};
    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
}}
QLabel#main_title {{
    font-size: 14pt;
    font-weight: bold;
    color: {TEXT_PRIMARY};
    padding: 4px 2px;
    background-color: #111827;
    border-radius: 4px;
}}
QGroupBox {{
    font-weight: bold;
    color: {TEXT_PRIMARY};
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 8px;
    padding: 10px 5px 5px 5px;
    font-size: 10pt;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: {TEXT_PRIMARY};
}}
QFrame#side_panel, QFrame#log_panel, QFrame#chart_panel {{
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
    font-size: 10pt;
    font-weight: 700;
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
    padding: 2px 6px;
    min-height: 25px;
    font-size: 10pt;
}}
QComboBox QAbstractItemView {{
    background-color: #243049;
    color: {TEXT_PRIMARY};
    selection-background-color: #0284C7;
    selection-color: #FFFFFF;
}}
QPushButton {{
    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
    font-weight: bold;
    border-radius: 6px;
    padding: 8px;
    color: {TEXT_PRIMARY};
    border: none;
    font-size: 10pt;
    background-color: #3D526E;
}}
QPushButton#btn_start {{
    background-color: #0284C7;
    color: #FFFFFF;
}}
QPushButton#btn_stop {{
    background-color: #475569;
    color: #FFFFFF;
}}
QPushButton#btn_stop:disabled {{
    background-color: #334155;
    color: {TEXT_MUTED};
}}
QPushButton#btn_export {{
    background-color: {SURFACE_BG};
    border: 1px solid #38BDF8;
    color: #E0F2FE;
}}
QPushButton#btn_report {{
    background-color: {SURFACE_BG};
    border: 1px solid #7DD3FC;
    color: #F0F9FF;
}}
QPushButton#btn_log_tool {{
    background-color: #3D526E;
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 9pt;
    color: {TEXT_SECONDARY};
    min-height: 20px;
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
    font-family: Consolas, 'Courier New', monospace;
    font-size: 10pt;
    padding: 6px;
    selection-background-color: #0369A1;
    selection-color: #FFFFFF;
}}
QToolTip {{
    color: {TEXT_PRIMARY};
    background-color: #1E293B;
    border: 1px solid #38BDF8;
    border-radius: 6px;
    padding: 10px;
    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
    font-size: 10pt;
}}
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
QFrame#side_panel, QFrame#chart_panel, QFrame#log_panel {{
    border: none;
}}
QLabel#lbl_charge_state {{
    background-color: {SURFACE_BG};
    color: {TEXT_PRIMARY};
    border: 1px dashed {BORDER};
    border-radius: 6px;
    padding: 8px;
    font-size: 11pt;
    font-weight: bold;
    margin-bottom: 5px;
}}
QLabel#lbl_log_title {{
    color: {TEXT_PRIMARY};
    font-weight: bold;
    font-size: 11pt;
}}
QWidget#chart_container {{
    background-color: {CHART_BG};
    min-height: 480px;
}}
QLabel#chart_placeholder {{
    color: {TEXT_MUTED};
    font-size: 10pt;
    padding: 24px;
    background-color: transparent;
}}
{lcd_rules}
"""


# Qt Designer 与运行时共用（单一来源）
MONITOR_WINDOW_STYLESHEET = APP_STYLESHEET + _monitor_widget_styles()
