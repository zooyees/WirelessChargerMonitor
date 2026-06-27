#!/usr/bin/env python3
"""从 theme.py 同步生成 wireless_charger_monitor/ui/monitor_window.ui。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from wireless_charger_monitor.ui.theme import LCD_STYLES, MONITOR_WINDOW_STYLESHEET  # noqa: E402

UI_PATH = os.path.join(ROOT, 'wireless_charger_monitor', 'ui', 'monitor_window.ui')

LCD_ITEMS = [
    ('lcd_v_in', '输入电压 (V_in)'),
    ('lcd_i_in', '输入电流 (I_in)'),
    ('lcd_v_out', '输出电压 (V_out)'),
    ('lcd_i_out', '输出电流 (I_out)'),
    ('lcd_power', '输出功率 (Power W)'),
    ('lcd_v_bat', '电池电压 (V_bat)'),
    ('lcd_i_bat', '电池电流 (I_bat)'),
    ('lcd_temp', '线圈温度 (°C)'),
    ('lcd_battery', '当前电量 (%)'),
]


def _xml_prop_object_name(name: str) -> str:
    return f'      <property name="objectName"><string>{name}</string></property>\n'


def lcd_block_xml(lcd_name: str, label_text: str) -> str:
    return f'''            <item>
             <layout class="QVBoxLayout" name="layout_{lcd_name}">
              <property name="spacing"><number>0</number></property>
              <item>
               <widget class="QLabel" name="lbl_{lcd_name}">
{_xml_prop_object_name('data_label')}                <property name="text"><string>{label_text}</string></property>
               </widget>
              </item>
              <item>
               <widget class="QLCDNumber" name="{lcd_name}">
                <property name="minimumHeight"><number>32</number></property>
                <property name="maximumHeight"><number>36</number></property>
                <property name="digitCount"><number>8</number></property>
                <property name="segmentStyle"><enum>QLCDNumber::Flat</enum></property>
               </widget>
              </item>
             </layout>
            </item>
'''


UI_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>MonitorWindow</class>
 <widget class="QMainWindow" name="MonitorWindow">
  <property name="geometry">
   <rect><x>0</x><y>0</y><width>1600</width><height>950</height></rect>
  </property>
  <property name="windowTitle"><string>串口分析工具</string></property>
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
      <property name="objectName"><string>main_title</string></property>
      <property name="text"><string>串口分析工具</string></property>
      <property name="alignment"><set>Qt::AlignCenter</set></property>
     </widget>
    </item>
    <item>
     <widget class="QSplitter" name="splitter">
      <property name="orientation"><enum>Qt::Horizontal</enum></property>
      <widget class="QFrame" name="side_panel">
       <property name="frameShape"><enum>QFrame::NoFrame</enum></property>
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
                   <property name="objectName"><string>btn_log_tool</string></property>
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
                <item><property name="text"><string>1000000</string></property></item>
                <item><property name="text"><string>2000000</string></property></item>
               </widget></item>
              </layout>
             </widget>
            </item>
LCD_BLOCKS
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
       <property name="frameShape"><enum>QFrame::NoFrame</enum></property>
       <layout class="QVBoxLayout" name="chart_layout">
        <property name="leftMargin"><number>0</number></property>
        <property name="topMargin"><number>0</number></property>
        <property name="rightMargin"><number>0</number></property>
        <property name="bottomMargin"><number>0</number></property>
        <item>
         <widget class="QWidget" name="chart_container">
          <layout class="QVBoxLayout" name="chart_container_layout">
           <property name="leftMargin"><number>0</number></property>
           <property name="topMargin"><number>0</number></property>
           <property name="rightMargin"><number>0</number></property>
           <property name="bottomMargin"><number>0</number></property>
           <item>
            <widget class="QLabel" name="chart_placeholder">
             <property name="text"><string>📈 实时波形区域&#xa;（程序运行时由 PyQtGraph 加载）</string></property>
             <property name="alignment"><set>Qt::AlignCenter</set></property>
            </widget>
           </item>
          </layout>
         </widget>
        </item>
       </layout>
      </widget>
      <widget class="QFrame" name="log_panel">
       <property name="frameShape"><enum>QFrame::NoFrame</enum></property>
       <property name="minimumSize"><size><width>320</width><height>0</height></size></property>
       <layout class="QVBoxLayout" name="log_layout">
        <property name="leftMargin"><number>10</number></property>
        <property name="topMargin"><number>10</number></property>
        <property name="rightMargin"><number>10</number></property>
        <property name="bottomMargin"><number>10</number></property>
        <property name="spacing"><number>5</number></property>
        <item>
         <layout class="QHBoxLayout" name="log_header_lay">
          <item><widget class="QLabel" name="lbl_log_title"><property name="text"><string>📡 报文实时监控</string></property></widget></item>
          <item><spacer name="log_header_spacer"><property name="orientation"><enum>Qt::Horizontal</enum></property><property name="sizeHint"><size><width>40</width><height>20</height></size></property></spacer></item>
          <item><widget class="QPushButton" name="btn_rollback">
           <property name="objectName"><string>btn_log_tool</string></property>
           <property name="text"><string>🔄 历史查阅</string></property>
          </widget></item>
          <item><widget class="QPushButton" name="btn_export_log">
           <property name="objectName"><string>btn_log_tool</string></property>
           <property name="text"><string>💾 导出全量日志</string></property>
          </widget></item>
         </layout>
        </item>
        <item>
         <widget class="QPlainTextEdit" name="text_log">
          <property name="readOnly"><bool>true</bool></property>
          <property name="placeholderText"><string>TX0 报文将在此显示…</string></property>
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


def main():
    os.makedirs(os.path.dirname(UI_PATH), exist_ok=True)
    lcd_blocks = ''.join(lcd_block_xml(name, text) for name, text in LCD_ITEMS)
    style_escaped = MONITOR_WINDOW_STYLESHEET.strip().replace('&', '&amp;')
    content = UI_XML.replace('LCD_BLOCKS', lcd_blocks).replace('STYLE_PLACEHOLDER', style_escaped)
    with open(UI_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f'Wrote {UI_PATH} ({len(LCD_STYLES)} LCD styles from theme.py)')


if __name__ == '__main__':
    main()
