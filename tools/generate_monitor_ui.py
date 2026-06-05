#!/usr/bin/env python3
"""Generate ui/monitor_window.ui from the legacy layout definition."""
import os
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_PATH = os.path.join(ROOT, 'wireless_charger_monitor', 'ui', 'monitor_window.ui')

BASE_STYLE = """
QMainWindow, QWidget#centralwidget {
    background-color: #0F172A;
    color: #F8FAFC;
    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
}
QLabel#main_title {
    font-size: 13pt;
    font-weight: bold;
    color: #F8FAFC;
    padding: 4px 2px;
    background-color: #111D2B;
    border-radius: 4px;
}
QGroupBox {
    font-weight: bold;
    color: #F8FAFC;
    background-color: #1E293B;
    border: 1px solid #5B6B7C;
    border-radius: 6px;
    margin-top: 8px;
    padding: 10px 5px 5px 5px;
    font-size: 10pt;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #F8FAFC;
}
QFrame#side_panel, QFrame#log_panel, QFrame#chart_panel {
    background-color: #1E293B;
    border-radius: 12px;
}
QWidget#side_content {
    background-color: #1E293B;
    color: #F8FAFC;
}
QScrollArea#side_scroll {
    background-color: #1E293B;
    border: none;
}
QScrollBar:vertical {
    background: #1E293B;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #64748B;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QLabel#data_label {
    color: #E2E8F0;
    font-size: 9pt;
    font-weight: 600;
}
QLCDNumber {
    background-color: #151D2E;
    color: #FDE047;
    border: 1px solid #5B6B7C;
    border-radius: 4px;
}
QComboBox {
    background-color: #2D3A4F;
    border: 1px solid #5B6B7C;
    border-radius: 4px;
    color: #F8FAFC;
    padding: 2px 6px;
    min-height: 25px;
    font-size: 9pt;
}
QComboBox QAbstractItemView {
    background-color: #2D3A4F;
    color: #F8FAFC;
    selection-background-color: #0EA5E9;
    selection-color: #FFFFFF;
}
QPushButton {
    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
    font-weight: bold;
    border-radius: 6px;
    padding: 8px;
    color: #F8FAFC;
    border: none;
    font-size: 10pt;
    background-color: #3D4F66;
}
QPushButton#btn_start {
    background-color: #0EA5E9;
    color: #FFFFFF;
}
QPushButton#btn_stop {
    background-color: #52657A;
    color: #FFFFFF;
}
QPushButton#btn_stop:disabled {
    background-color: #334155;
    color: #B8C5D3;
}
QPushButton#btn_export {
    background-color: #151D2E;
    border: 1px solid #0EA5E9;
    color: #7DD3FC;
}
QPushButton#btn_report {
    background-color: #151D2E;
    border: 1px solid #38BDF8;
    color: #BAE6FD;
}
QPushButton#btn_log_tool {
    background-color: #3D4F66;
    border: 1px solid #5B6B7C;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 8pt;
    color: #E2E8F0;
    min-height: 20px;
}
QPushButton#btn_log_tool:hover {
    background-color: #52657A;
    color: #FFFFFF;
}
QPushButton:hover {
    background-color: #52657A;
}
QPushButton#btn_start:hover {
    background-color: #0284C7;
}
QPlainTextEdit {
    background-color: #151D2E;
    color: #DCE8F5;
    border: 1px solid #5B6B7C;
    border-radius: 6px;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 9pt;
    padding: 5px;
}
QToolTip {
    color: #F8FAFC;
    background-color: #1E293B;
    border: 1px solid #0EA5E9;
    border-radius: 6px;
    padding: 10px;
    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
    font-size: 10pt;
}
"""

LCD_ITEMS = [
    ('layout_v_in', 'lcd_v_in', '输入电压 (V_in)', '#FDE047'),
    ('layout_i_in', 'lcd_i_in', '输入电流 (I_in)', '#4ADE80'),
    ('layout_v_out', 'lcd_v_out', '输出电压 (V_out)', '#FDE047'),
    ('layout_i_out', 'lcd_i_out', '输出电流 (I_out)', '#4ADE80'),
    ('layout_power', 'lcd_power', '输出功率 (Power W)', '#C084FC'),
    ('layout_v_bat', 'lcd_v_bat', '电池电压 (V_bat)', '#FDE047'),
    ('layout_i_bat', 'lcd_i_bat', '电池电流 (I_bat)', '#4ADE80'),
    ('layout_temp', 'lcd_temp', '线圈温度 (°C)', '#FB923C'),
    ('layout_battery', 'lcd_battery', '当前电量 (%)', '#34D399'),
]


def qproperty(name, value, string=True):
    prop = ET.Element('property')
    n = ET.SubElement(prop, 'name')
    n.text = name
    if string:
        s = ET.SubElement(prop, 'string')
        s.text = str(value)
    return prop


def qbool(name, value):
    prop = ET.Element('property')
    n = ET.SubElement(prop, 'name')
    n.text = name
    b = ET.SubElement(prop, 'bool')
    b.text = 'true' if value else 'false'
    return prop


def qnumber(name, value):
    prop = ET.Element('property')
    n = ET.SubElement(prop, 'name')
    n.text = name
    num = ET.SubElement(prop, 'number')
    num.text = str(value)
    return prop


def qsize(w, h):
    prop = ET.Element('property')
    n = ET.SubElement(prop, 'name')
    n.text = 'minimumSize'
    size = ET.SubElement(prop, 'size')
    ET.SubElement(size, 'width').text = str(w)
    ET.SubElement(size, 'height').text = str(h)
    return prop


def qrect(x, y, w, h):
    prop = ET.Element('property')
    n = ET.SubElement(prop, 'name')
    n.text = 'geometry'
    rect = ET.SubElement(prop, 'rect')
    ET.SubElement(rect, 'x').text = str(x)
    ET.SubElement(rect, 'y').text = str(y)
    ET.SubElement(rect, 'width').text = str(w)
    ET.SubElement(rect, 'height').text = str(h)
    return prop


def qenum(name, value):
    prop = ET.Element('property')
    n = ET.SubElement(prop, 'name')
    n.text = name
    e = ET.SubElement(prop, 'enum')
    e.text = value
    return prop


def qlayout(name, layout_class='QVBoxLayout'):
    lay = ET.Element('layout')
    ET.SubElement(lay, 'property').append(ET.Element('name')).text = name
    cls = ET.SubElement(lay, 'property')
    ET.SubElement(cls, 'name').text = 'name'
    ET.SubElement(cls, 'string').text = layout_class
    return lay


def margins(lay, left, top, right, bottom):
    m = ET.SubElement(lay, 'property')
    ET.SubElement(m, 'name').text = 'leftMargin'
    ET.SubElement(m, 'number').text = str(left)
    m2 = ET.SubElement(lay, 'property')
    ET.SubElement(m2, 'name').text = 'topMargin'
    ET.SubElement(m2, 'number').text = str(top)
    m3 = ET.SubElement(lay, 'property')
    ET.SubElement(m3, 'name').text = 'rightMargin'
    ET.SubElement(m3, 'number').text = str(right)
    m4 = ET.SubElement(lay, 'property')
    ET.SubElement(m4, 'name').text = 'bottomMargin'
    ET.SubElement(m4, 'number').text = str(bottom)
    return lay


def spacing(lay, val):
    s = ET.SubElement(lay, 'property')
    ET.SubElement(s, 'name').text = 'spacing'
    ET.SubElement(s, 'number').text = str(val)
    return lay


def add_widget(lay, widget_elem):
    item = ET.SubElement(lay, 'item')
    item.append(widget_elem)
    return lay


def add_layout(parent_lay, child_lay):
    item = ET.SubElement(parent_lay, 'item')
    item.append(child_lay)
    return parent_lay


def add_stretch(lay, stretch=0):
    item = ET.SubElement(lay, 'item')
    sp = ET.SubElement(item, 'spacer')
    ET.SubElement(sp, 'property').append(ET.Element('name')).text = 'name'
    name_prop = sp.find('property')
    if name_prop is None:
        name_prop = ET.SubElement(sp, 'property')
        ET.SubElement(name_prop, 'name').text = 'name'
    ET.SubElement(name_prop, 'string').text = 'verticalSpacer'
    hp = ET.SubElement(sp, 'property')
    ET.SubElement(hp, 'name').text = 'orientation'
    ET.SubElement(hp, 'enum').text = 'Qt::Vertical'
    sp2 = ET.SubElement(sp, 'property')
    ET.SubElement(sp2, 'name').text = 'sizeHint'
    sh = ET.SubElement(sp2, 'size')
    ET.SubElement(sh, 'width').text = '20'
    ET.SubElement(sh, 'height').text = '40'
    if stretch:
        ip = ET.SubElement(item, 'property')
        ET.SubElement(ip, 'name').text = 'stretch'
        ET.SubElement(ip, 'number').text = str(stretch)
    return lay


def widget(class_name, name, props=None, children=None):
    w = ET.Element('widget')
    w.set('class', class_name)
    w.set('name', name)
    if props:
        for p in props:
            w.append(p)
    if children:
        for c in children:
            w.append(c)
    return w


def lcd_block(layout_name, lcd_name, label_text, color):
    lay = qlayout(layout_name)
    spacing(lay, 0)
    lbl = widget('QLabel', f'lbl_{lcd_name}', [
        qproperty('text', label_text),
        qenum('alignment', 'Qt::AlignLeading|Qt::AlignLeft|Qt::AlignVCenter'),
    ])
    lbl.find('widget')  # noqa - structure fix
    lbl_props = lbl
    obj = ET.SubElement(lbl_props[0] if False else lbl, 'property')
    # fix objectName for label
    for p in list(lbl):
        if p.tag == 'property' and p.find('name') is not None and p.find('name').text == 'text':
            continue
    obj = ET.Element('property')
    ET.SubElement(obj, 'name').text = 'objectName'
    ET.SubElement(obj, 'string').text = 'data_label'
    lbl.insert(0, obj)

    lcd = widget('QLCDNumber', lcd_name, [
        qsize(0, 30),
        qproperty('styleSheet', (
            f"background-color: #151D2E; color: {color}; "
            "border: 1px solid #5B6B7C; border-radius: 4px;"
        )),
        qenum('sizePolicy', 'Expanding'),  # invalid - skip
    ])
    # Remove invalid enum, use min/max height instead
    lcd = widget('QLCDNumber', lcd_name, [
        qproperty('minimumSize', None),
        qproperty('styleSheet', (
            f"background-color: #151D2E; color: {color}; "
            "border: 1px solid #5B6B7C; border-radius: 4px;"
        )),
    ])
    min_h = ET.Element('property')
    ET.SubElement(min_h, 'name').text = 'minimumHeight'
    ET.SubElement(min_h, 'number').text = '30'
    max_h = ET.Element('property')
    ET.SubElement(max_h, 'name').text = 'maximumHeight'
    ET.SubElement(max_h, 'number').text = '34'
    lcd.append(min_h)
    lcd.append(max_h)

    add_widget(lay, lbl)
    add_widget(lay, lcd)
    return lay


def build_ui():
    ui = ET.Element('ui')
    ui.set('version', '4.0')
    ET.SubElement(ui, 'class').text = 'MonitorWindow'

    mw = widget('QMainWindow', 'MonitorWindow', [
        qproperty('windowTitle', '手机无线充电监控系统'),
        qrect(0, 0, 1600, 950),
        qproperty('styleSheet', BASE_STYLE.strip()),
    ])

    central = widget('QWidget', 'centralwidget', [])
    root = qlayout('root_layout')
    margins(root, 10, 5, 10, 10)
    spacing(root, 5)

    title = widget('QLabel', 'lbl_main_title', [
        qproperty('text', '手机无线充电监控系统'),
        qenum('alignment', 'Qt::AlignCenter'),
    ])
    obj = ET.Element('property')
    ET.SubElement(obj, 'name').text = 'objectName'
    ET.SubElement(obj, 'string').text = 'main_title'
    title.insert(0, obj)

    splitter = widget('QSplitter', 'splitter', [qenum('orientation', 'Qt::Horizontal')])

    # --- side panel ---
    side_panel = widget('QFrame', 'side_panel', [qsize(220, 0)])
    side_outer = qlayout('side_panel_outer')
    margins(side_outer, 0, 0, 0, 0)
    side_scroll = widget('QScrollArea', 'side_scroll', [
        qbool('widgetResizable', True),
        qenum('frameShape', 'QFrame::NoFrame'),
        qenum('horizontalScrollBarPolicy', 'Qt::ScrollBarAlwaysOff'),
    ])
    side_content = widget('QWidget', 'side_content', [])
    side_layout = qlayout('side_layout')
    margins(side_layout, 10, 5, 10, 10)
    spacing(side_layout, 3)

    group_config = widget('QGroupBox', 'group_config', [qproperty('title', '连接配置')])
    config_v = qlayout('config_vbox')
    margins(config_v, 5, 15, 5, 5)
    spacing(config_v, 2)
    port_row = qlayout('port_hbox', 'QHBoxLayout')
    cb_port = widget('QComboBox', 'cb_port', [])
    btn_refresh = widget('QPushButton', 'btn_refresh_ports', [
        qproperty('text', '🔄'),
        qproperty('toolTip', '刷新串口列表'),
    ])
    btn_refresh_obj = ET.Element('property')
    ET.SubElement(btn_refresh_obj, 'name').text = 'objectName'
    ET.SubElement(btn_refresh_obj, 'string').text = 'btn_log_tool'
    btn_refresh.insert(0, btn_refresh_obj)
    fw = ET.Element('property')
    ET.SubElement(fw, 'name').text = 'minimumWidth'
    ET.SubElement(fw, 'number').text = '36'
    fw2 = ET.Element('property')
    ET.SubElement(fw2, 'name').text = 'maximumWidth'
    ET.SubElement(fw2, 'number').text = '36'
    btn_refresh.append(fw)
    btn_refresh.append(fw2)
    add_widget(port_row, cb_port)
    add_widget(port_row, btn_refresh)
    cb_baud = widget('QComboBox', 'cb_baudrate', [])
    for rate in ('115200', '921600', '2000000'):
        item_el = ET.SubElement(cb_baud, 'item')
        ET.SubElement(item_el, 'property').append(ET.Element('string')).text = rate
    add_layout(config_v, port_row)
    add_widget(config_v, cb_baud)
    group_config.append(config_v)
    add_widget(side_layout, group_config)

    for layout_name, lcd_name, label_text, color in LCD_ITEMS:
        add_layout(side_layout, lcd_block(layout_name, lcd_name, label_text, color))

    lbl_charge = widget('QLabel', 'lbl_charge_state', [
        qproperty('text', '⚡ 充电状态: 等待接入...'),
        qenum('alignment', 'Qt::AlignCenter'),
        qbool('wordWrap', True),
        qproperty('styleSheet', (
            'background-color: #151D2E; color: #E2E8F0; border: 1px dashed #5B6B7C; '
            'border-radius: 6px; padding: 8px; font-size: 11pt; font-weight: bold; margin-bottom: 5px;'
        )),
    ])

    btn_box = qlayout('btn_box')
    spacing(btn_box, 5)
    btn_start = widget('QPushButton', 'btn_start', [qproperty('text', '▶ 开始')])
    btn_stop = widget('QPushButton', 'btn_stop', [
        qproperty('text', '⏹ 停止'),
        qbool('enabled', False),
    ])
    btn_export = widget('QPushButton', 'btn_export', [qproperty('text', '💾 导出 CSV')])
    btn_report = widget('QPushButton', 'btn_report', [qproperty('text', '📄 导出 PDF 报告')])
    for b in (btn_start, btn_stop, btn_export, btn_report):
        add_widget(btn_box, b)
    add_widget(side_layout, lbl_charge)
    add_layout(side_layout, btn_box)
    add_stretch(side_layout)

    side_content.append(side_layout)
    side_scroll.append(side_content)
    add_widget(side_outer, side_scroll)
    side_panel.append(side_outer)

    # --- chart panel ---
    chart_panel = widget('QFrame', 'chart_panel', [])
    chart_layout = qlayout('chart_layout')
    margins(chart_layout, 0, 0, 0, 0)
    chart_container = widget('QWidget', 'chart_container', [
        qproperty('toolTip', 'PyQtGraph 图表区域（运行时注入）'),
    ])
    add_widget(chart_layout, chart_container)
    chart_panel.append(chart_layout)

    # --- log panel ---
    log_panel = widget('QFrame', 'log_panel', [qsize(320, 0)])
    log_layout = qlayout('log_layout')
    margins(log_layout, 10, 10, 10, 10)
    spacing(log_layout, 5)
    log_header = qlayout('log_header_lay', 'QHBoxLayout')
    lbl_log = widget('QLabel', 'lbl_log_title', [
        qproperty('text', '📡 报文实时监控'),
        qproperty('styleSheet', 'color: #F8FAFC; font-weight: bold; font-size: 10pt;'),
    ])
    btn_rollback = widget('QPushButton', 'btn_rollback', [qproperty('text', '🔄 历史查阅')])
    btn_export_log = widget('QPushButton', 'btn_export_log', [qproperty('text', '💾 导出全量日志')])
    for b in (btn_rollback, btn_export_log):
        objp = ET.Element('property')
        ET.SubElement(objp, 'name').text = 'objectName'
        ET.SubElement(objp, 'string').text = 'btn_log_tool'
        b.insert(0, objp)
    add_widget(log_header, lbl_log)
    add_stretch(log_header)
    add_widget(log_header, btn_rollback)
    add_widget(log_header, btn_export_log)
    text_log = widget('QPlainTextEdit', 'text_log', [qbool('readOnly', True)])
    add_layout(log_layout, log_header)
    add_widget(log_layout, text_log)
    log_panel.append(log_layout)

    # assemble splitter
    split_lay = qlayout('splitter_layout')  # QSplitter uses addWidget not layout - fix
    # QSplitter children are direct widget children
    for child in (side_panel, chart_panel, log_panel):
        splitter.append(child)

    add_widget(root, title)
    add_widget(root, splitter)
    central.append(root)
    mw.append(central)

    cw = ET.SubElement(mw, 'widget')
    cw.set('class', 'QWidget')
    cw.set('name', 'centralwidget')
    # rebuild - the central widget structure was wrong. Let me fix by replacing mw children

    return ui, mw, central, root, title, splitter, side_panel, chart_panel, log_panel


# Simpler approach: write XML as template string
UI_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>MonitorWindow</class>
 <widget class="QMainWindow" name="MonitorWindow">
  <property name="geometry">
   <rect><x>0</x><y>0</y><width>1600</width><height>950</height></rect>
  </property>
  <property name="windowTitle"><string>手机无线充电监控系统</string></property>
  <property name="styleSheet"><string>STYLE_PLACEHOLDER</string></property>
  <widget class="QWidget" name="centralwidget">
   <layout class="QVBoxLayout" name="root_layout">
    <property name="leftMargin"><number>10</number></property>
    <property name="topMargin"><number>5</number></property>
    <property name="rightMargin"><number>10</number></property>
    <property name="bottomMargin"><number>10</number></property>
    <property name="spacing"><number>5</number></property>
    <item>
     <widget class="QLabel" name="lbl_main_title">
      <property name="text"><string>手机无线充电监控系统</string></property>
      <property name="alignment"><set>Qt::AlignCenter</set></property>
     </widget>
    </item>
    <item>
     <widget class="QSplitter" name="splitter">
      <property name="orientation"><enum>Qt::Horizontal</enum></property>
      <widget class="QFrame" name="side_panel">
       <property name="minimumSize"><size><width>220</width><height>0</height></size></property>
       <layout class="QVBoxLayout" name="side_panel_outer">
        <property name="leftMargin"><number>0</number></property>
        <property name="topMargin"><number>0</number></property>
        <property name="rightMargin"><number>0</number></property>
        <property name="bottomMargin"><number>0</number></property>
        <item>
         <widget class="QScrollArea" name="side_scroll">
          <property name="widgetResizable"><bool>true</bool></property>
          <property name="frameShape"><enum>QFrame::NoFrame</enum></property>
          <property name="horizontalScrollBarPolicy"><enum>Qt::ScrollBarAlwaysOff</enum></property>
          <widget class="QWidget" name="side_content">
           <layout class="QVBoxLayout" name="side_layout">
            <property name="leftMargin"><number>10</number></property>
            <property name="topMargin"><number>5</number></property>
            <property name="rightMargin"><number>10</number></property>
            <property name="bottomMargin"><number>10</number></property>
            <property name="spacing"><number>3</number></property>
            <item>
             <widget class="QGroupBox" name="group_config">
              <property name="title"><string>连接配置</string></property>
              <layout class="QVBoxLayout" name="config_vbox">
               <property name="leftMargin"><number>5</number></property>
               <property name="topMargin"><number>15</number></property>
               <property name="rightMargin"><number>5</number></property>
               <property name="bottomMargin"><number>5</number></property>
               <property name="spacing"><number>2</number></property>
               <item>
                <layout class="QHBoxLayout" name="port_hbox">
                 <item><widget class="QComboBox" name="cb_port"/></item>
                 <item>
                  <widget class="QPushButton" name="btn_refresh_ports">
                   <property name="text"><string>🔄</string></property>
                   <property name="toolTip"><string>刷新串口列表</string></property>
                   <property name="minimumSize"><size><width>36</width><height>0</height></size></property>
                   <property name="maximumSize"><size><width>36</width><height>16777215</height></size></property>
                  </widget>
                 </item>
                </layout>
               </item>
               <item><widget class="QComboBox" name="cb_baudrate">
                <item><property name="text"><string>115200</string></property></item>
                <item><property name="text"><string>921600</string></property></item>
                <item><property name="text"><string>2000000</string></property></item>
               </widget></item>
              </layout>
             </widget>
            </item>
LCD_BLOCKS
            <item>
             <widget class="QLabel" name="lbl_charge_state">
              <property name="text"><string>⚡ 充电状态: 等待接入...</string></property>
              <property name="alignment"><set>Qt::AlignCenter</set></property>
              <property name="wordWrap"><bool>true</bool></property>
              <property name="styleSheet"><string>background-color: #151D2E; color: #E2E8F0; border: 1px dashed #5B6B7C; border-radius: 6px; padding: 8px; font-size: 11pt; font-weight: bold; margin-bottom: 5px;</string></property>
             </widget>
            </item>
            <item>
             <layout class="QVBoxLayout" name="btn_box">
              <property name="spacing"><number>5</number></property>
              <item><widget class="QPushButton" name="btn_start"><property name="text"><string>▶ 开始</string></property></widget></item>
              <item><widget class="QPushButton" name="btn_stop"><property name="text"><string>⏹ 停止</string></property><property name="enabled"><bool>false</bool></property></widget></item>
              <item><widget class="QPushButton" name="btn_export"><property name="text"><string>💾 导出 CSV</string></property></widget></item>
              <item><widget class="QPushButton" name="btn_report"><property name="text"><string>📄 导出 PDF 报告</string></property></widget></item>
             </layout>
            </item>
            <item><spacer name="side_spacer"><property name="orientation"><enum>Qt::Vertical</enum></property><property name="sizeHint"><size><width>20</width><height>40</height></size></property></spacer></item>
           </layout>
          </widget>
         </widget>
        </item>
       </layout>
      </widget>
      <widget class="QFrame" name="chart_panel">
       <layout class="QVBoxLayout" name="chart_layout">
        <property name="leftMargin"><number>0</number></property>
        <property name="topMargin"><number>0</number></property>
        <property name="rightMargin"><number>0</number></property>
        <property name="bottomMargin"><number>0</number></property>
        <item>
         <widget class="QWidget" name="chart_container">
          <property name="toolTip"><string>PyQtGraph 图表（程序运行时注入）</string></property>
         </widget>
        </item>
       </layout>
      </widget>
      <widget class="QFrame" name="log_panel">
       <property name="minimumSize"><size><width>320</width><height>0</height></size></property>
       <layout class="QVBoxLayout" name="log_layout">
        <property name="leftMargin"><number>10</number></property>
        <property name="topMargin"><number>10</number></property>
        <property name="rightMargin"><number>10</number></property>
        <property name="bottomMargin"><number>10</number></property>
        <property name="spacing"><number>5</number></property>
        <item>
         <layout class="QHBoxLayout" name="log_header_lay">
          <item><widget class="QLabel" name="lbl_log_title"><property name="text"><string>📡 报文实时监控</string></property><property name="styleSheet"><string>color: #F8FAFC; font-weight: bold; font-size: 10pt;</string></property></widget></item>
          <item><spacer name="log_header_spacer"><property name="orientation"><enum>Qt::Horizontal</enum></property><property name="sizeHint"><size><width>40</width><height>20</height></size></property></spacer></item>
          <item><widget class="QPushButton" name="btn_rollback"><property name="text"><string>🔄 历史查阅</string></property></widget></item>
          <item><widget class="QPushButton" name="btn_export_log"><property name="text"><string>💾 导出全量日志</string></property></widget></item>
         </layout>
        </item>
        <item>
         <widget class="QPlainTextEdit" name="text_log">
          <property name="readOnly"><bool>true</bool></property>
         </widget>
        </item>
       </layout>
      </widget>
     </widget>
    </item>
   </layout>
  </widget>
 </widget>
 <resources/>
 <connections/>
</ui>
'''


def lcd_block_xml(lcd_name, label_text, color):
    return f'''            <item>
             <layout class="QVBoxLayout" name="layout_{lcd_name}">
              <property name="spacing"><number>0</number></property>
              <item>
               <widget class="QLabel" name="lbl_{lcd_name}">
                <property name="text"><string>{label_text}</string></property>
               </widget>
              </item>
              <item>
               <widget class="QLCDNumber" name="{lcd_name}">
                <property name="minimumHeight"><number>30</number></property>
                <property name="maximumHeight"><number>34</number></property>
                <property name="styleSheet"><string>background-color: #151D2E; color: {color}; border: 1px solid #5B6B7C; border-radius: 4px;</string></property>
               </widget>
              </item>
             </layout>
            </item>
'''


def main():
    os.makedirs(os.path.dirname(UI_PATH), exist_ok=True)
    lcd_blocks = ''.join(lcd_block_xml(n, t, c) for _, n, t, c in LCD_ITEMS)
    style_escaped = BASE_STYLE.strip().replace('&', '&amp;')
    content = UI_XML.replace('LCD_BLOCKS', lcd_blocks).replace('STYLE_PLACEHOLDER', style_escaped)
    with open(UI_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Wrote {UI_PATH}')


if __name__ == '__main__':
    main()
