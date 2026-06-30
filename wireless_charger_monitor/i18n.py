"""UI internationalization (English / Chinese)."""

from __future__ import annotations

_current_language = 'en'

# (zh_CN, en_US)
STRINGS: dict[str, tuple[str, str]] = {
    'app.title': ('WiParse', 'WiParse'),
    'status.ready': ('就绪', 'Ready'),
    'menu.settings': ('设置(&S)', '&Settings'),
    'menu.panels': ('显示面板', 'Panels'),
    'menu.language': ('语言', 'Language'),
    'tab.oscilloscope': ('示波器', 'Scope'),
    'tab.log_monitor': ('串口', 'Uart'),
    'lcd.v_in': ('输入电压 (V_in)', 'Vin (V)'),
    'lcd.i_in': ('输入电流 (I_in)', 'Iin (A)'),
    'lcd.v_out': ('输出电压 (V_out)', 'Vout (V)'),
    'lcd.i_out': ('输出电流 (I_out)', 'Iout (A)'),
    'lcd.power': ('输出功率 (Power W)', 'Pout (W)'),
    'lcd.v_bat': ('电池电压 (V_bat)', 'Vbat (V)'),
    'lcd.i_bat': ('电池电流 (I_bat)', 'Ibat (A)'),
    'lcd.temp': ('线圈温度 (°C)', 'Tcoil (°C)'),
    'lcd.battery': ('当前电量 (%)', 'SOC (%)'),
    'charge.waiting': ('⚡ 充电状态: 等待接入...', '⚡ Waiting for device…'),
    'charge.analyzing': ('⚡ 充电状态分析中...', '⚡ Analyzing charge phase…'),
    'charge.idle': ('🔌 未充电 / 待机中', '🔌 Idle / Standby'),
    'charge.cc': ('🔵 恒流充电阶段 (CC)', '🔵 CC Phase'),
    'charge.cv': ('🟡 恒压充电阶段 (CV)', '🟡 CV Phase'),
    'charge.trickle': ('🟢 涓流阶段 / 已满电', '🟢 Trickle / Full'),
    'charge.trickle_not_full': ('🟢 涓流阶段 (电量未满)', '🟢 Trickle (SOC < 100%)'),
    'charge.negotiate': ('🔄 动态功率协商中...', '🔄 Power negotiation…'),
    'charge.collecting': ('⚡ 数据采集中...', '⚡ Acquiring samples…'),
    'charge.demo': ('⚠️ 演示模式 — 模拟数据', '⚠️ Demo mode (simulated data)'),
    'chart.placeholder': (
        '📈 实时波形区域\n（程序运行时由 PyQtGraph 加载）',
        '📈 Waveform Plot\n(rendered at runtime)',
    ),
    'btn.start': ('▶ 开始', '▶ Start'),
    'btn.stop': ('⏹ 停止', '⏹ Stop'),
    'btn.new': ('新建', 'New'),
    'btn.browse_dir': ('📁 选择路径', '📁 Browse…'),
    'btn.open_log': ('📂 打开文件', '📂 Open…'),
    'btn.browse_tooltip': ('选择实时报文保存目录', 'Select the output directory for live capture files'),
    'log.filename': ('文件名', 'Log Name'),
    'log.save_dir': ('保存路径', 'Output Directory'),
    'log.title': ('📡 报文实时监控', '📡 Real-Time Packet Monitor'),
    'log.default_filename': ('实时报文', 'Live Packet Log'),
    'log.name_placeholder': ('实时报文', 'Live Packet Log'),
    'log.name_tooltip': ('不含扩展名，保存为 TXT 格式，Enter 确认', 'Base name without extension (.txt); press Enter to apply'),
    'log.dir_tooltip': ('实时报文 TXT 文件保存目录', 'Directory where live capture files (.txt) are saved'),
    'log.new_tooltip': ('新建实时报文文件，当前标签右移', 'Start a new capture file; the current tab shifts right'),
    'log.open_tooltip': ('打开本地 TXT 日志文件（可多选）', 'Open one or more capture/log files (.txt)'),
    'log.filter': ('数据筛选', 'Filter'),
    'log.filter_placeholder': ('完整匹配·回车', 'Exact match · Enter'),
    'log.split_enable': ('数据分窗', 'Split View'),
    'log.split_tooltip': ('启用后将报文按条件分到多个窗口显示', 'Route packets into separate panes by filter criteria'),
    'log.panes_tooltip': ('分窗数量（启用 Split View 后有效）', 'Number of panes (when Split View is enabled)'),
    'log.filter_tooltip': (
        '完整字符串匹配；多个关键词用 | 分隔（保留空格）；按 Enter 刷新显示',
        'Exact substring match; separate multiple terms with | (spaces preserved); press Enter to apply',
    ),
    'log.split_count': ('分窗数', 'Panes'),
    'log.same_page': ('同页显示', 'Side-by-Side'),
    'log.same_page_tooltip': (
        '勾选后各分窗在同一页面并排显示；取消则每个分窗单独占一个标签页',
        'Show split panes side-by-side in one view; unchecked, each pane uses its own tab',
    ),
    'log.all': ('全部', 'All'),
    'log.pane_tab': ('分窗{n}', 'Pane {n}'),
    'log.pane_filter': ('分窗{n}筛选', 'Pane {n}'),
    'log.auto_parse': ('自动解析', 'Auto Parse'),
    'log.auto_parse_tooltip': (
        '悬停报文行时显示 Qi 协议解析；关闭后不进行解析以节省 CPU',
        'Show Qi packet decode on hover; when off, no parsing runs to save CPU',
    ),
    'log.tab.close_current': ('关闭当前', 'Close Current'),
    'log.tab.close_all': ('关闭所有', 'Close All'),
    'dialog.create_failed': ('创建失败', 'Create Failed'),
    'dialog.rename_failed': ('重命名失败', 'Rename Failed'),
    'dialog.save_failed': ('保存失败', 'Save Failed'),
    'dialog.open_failed': ('打开失败', 'Open Failed'),
    'dialog.notice': ('提示', 'Notice'),
    'dialog.demo_mode': ('演示模式', 'Demo Mode'),
    'dialog.serial_failed': ('串口连接失败', 'Serial Connection Failed'),
    'dialog.serial_lost': ('串口连接断开', 'Serial Link Lost'),
    'dialog.no_device': ('无可用设备', 'No Serial Port'),
    'dialog.full_charge_title': ('充电完成 🔋', 'Charge Complete 🔋'),
    'msg.invalid_baudrate': ('无效的波特率：{value}', 'Invalid baud rate: {value}'),
    'msg.cannot_create_log': ('无法创建日志文件：\n{path}\n{error}', 'Cannot create capture file:\n{path}\n{error}'),
    'msg.file_exists': ('目标文件已存在：\n{path}', 'Target file already exists:\n{path}'),
    'msg.cannot_rename': (
        '无法重命名文件：\n{old_path}\n→\n{new_path}\n\n{error}',
        'Cannot rename file:\n{old_path}\n→\n{new_path}\n\n{error}',
    ),
    'msg.cannot_read_file': ('无法读取文件：\n{path}\n{error}', 'Cannot read file:\n{path}\n{error}'),
    'msg.cannot_close_live_tab': ('监控进行中，无法关闭当前实时报文标签。', 'Monitoring is active; the capture tab cannot be closed.'),
    'msg.demo_body': (
        '{detail}\n\n已启用演示模式，当前数据为模拟生成，不可用于正式测试。',
        '{detail}\n\nDemo mode enabled; data is simulated and not valid for formal testing.',
    ),
    'msg.serial_failed_body': (
        '{detail}\n\n监控已停止，请检查设备连接与端口设置后重试。',
        '{detail}\n\nMonitoring stopped. Check the device connection and port settings, then retry.',
    ),
    'msg.serial_lost_body': (
        '串口通信异常：{detail}\n\n已尝试自动重连但未恢复，请检查线缆与设备后重新开始。',
        'Serial communication error: {detail}\n\nAuto-reconnect failed. Check cabling and device, then start again.',
    ),
    'msg.no_serial_device': (
        '未检测到串口设备，请连接硬件后等待系统自动识别。',
        'No serial port detected. Connect hardware and wait for auto-detection.',
    ),
    'msg.serial_open_failed': (
        '无法打开串口 {port} (波特率 {baud}): {error}',
        'Failed to open {port} @ {baud} baud: {error}',
    ),
    'msg.full_charge_html': ('<h3>🎉 充电已完成！</h3>', '<h3>🎉 Charge complete!</h3>'),
    'msg.full_charge_info': (
        '设备已稳定维持涓流满电状态 {seconds:g} 秒。<br><span style=\'color:#94A3B8;\'>本提示将在 10 秒后自动关闭。</span>',
        'Device has remained in trickle full-charge state for {seconds:g} s.<br><span style=\'color:#94A3B8;\'>This notice closes in 10 seconds.</span>',
    ),
    'msg.full_charge_log': (
        '[{time}] 🎉 提示：充电已完成 (稳定维持涓流状态 {seconds:g} 秒)！',
        '[{time}] 🎉 Charge complete (trickle state held for {seconds:g} s).',
    ),
    'status.new_log': ('已新建报文文件: {name}', 'Capture started: {name}'),
    'status.log_updated': ('报文文件已更新: {name}', 'Capture file updated: {name}'),
    'status.cannot_create_log': ('无法创建日志文件: {name}', 'Failed to create capture file: {name}'),
    'status.log_write_failed': ('实时报文文件写入失败', 'Capture file write failed'),
    'status.opened_logs': ('已打开 {count} 个日志文件', 'Opened {count} capture file(s)'),
    'status.session': ('会话 #{id}', 'Session #{id}'),
    'status.monitoring': ('监控中 — 会话 #{id}', 'Monitoring — Session #{id}'),
    'status.session_ended': ('会话 #{id} 已结束', 'Session #{id} ended'),
    'status.ports_updated': ('串口列表已更新 ({count} 个设备)', 'Serial ports updated ({count})'),
    'status.no_ports': ('未检测到串口设备', 'No serial port detected'),
    'status.reconnecting': ('串口断开，正在重连 ({attempt}/{maximum})…', 'Serial reconnect {attempt}/{maximum}…'),
    'status.serial_stopped': ('串口连接已断开，监控已停止', 'Serial link lost — monitoring stopped'),
    'status.alert': ('🚨 {type}：{value:.2f}{unit} (阈值 {threshold:.2f}{unit})', '🚨 {type}: {value:.2f}{unit} (limit {threshold:.2f}{unit})'),
    'status.alert_bar': ('安全告警 — {type}', 'Safety Alert — {type}'),
    'status.protection_log': (
        '[{time}] 🚨 硬件保护触发：{type}！当前值 {value:.2f}{unit}，安全阈值 {threshold:.2f}{unit}',
        '[{time}] 🚨 Hardware protection: {type}! Value {value:.2f}{unit}, limit {threshold:.2f}{unit}',
    ),
    'status.temp_warning_log': (
        '[{time}] ⚠️ 警告：线圈温度过高 ({temp}°C)！',
        '[{time}] ⚠️ Warning: coil temperature too high ({temp}°C)!',
    ),
    'protect.ovp': ('过压保护 (OVP)', 'Over-Voltage (OVP)'),
    'protect.ocp': ('过流保护 (OCP)', 'Over-Current (OCP)'),
    'protect.otp': ('过温保护 (OTP)', 'Over-Temperature (OTP)'),
    'port.none': ('无设备', '(none)'),
    'filedialog.save_dir': ('选择保存路径', 'Select Output Directory'),
    'filedialog.open_logs': ('打开日志文件', 'Open Capture Files'),
    'filedialog.filter': ('文本文件 (*.txt);;日志文件 (*.log);;所有文件 (*)', 'Text files (*.txt);;Log files (*.log);;All files (*)'),
    'qi.dir_ask': ('🔵 ASK (PRx ➔ PTx)', '🔵 ASK (PRx ➔ PTx)'),
    'qi.dir_fsk': ('🟠 FSK (PTx ➔ PRx)', '🟠 FSK (PTx ➔ PRx)'),
    'qi.header': ('Header:', 'Header:'),
    'qi.payload': ('Payload ({n} B):', 'Payload ({n} B):'),
    'qi.xor': ('XOR 校验:', 'XOR checksum:'),
    'qi.fields': ('📑 字段解析:', '📑 Field decode:'),
    'qi.unknown_pkt': ('未知 / 专有指令', 'Unknown / proprietary'),
    'qi.unknown_vendor': ('未知厂商 (PRMC 0x{code:04X})', 'Unknown vendor (PRMC 0x{code:04X})'),
    'qi.parse_error': ('解析异常: {error}', 'Parse error: {error}'),
    'qi.insufficient': ('载荷不足', 'Insufficient payload'),
    'qi.no_payload': ('无载荷', 'No payload'),
    'qi.reneg_no_payload': ('无载荷 — 请求进入重新协商阶段', 'No payload — renegotiation request'),
    'qi.need_payload_3b': ('需要 3 字节载荷', 'Requires 3-byte payload'),
    'qi.ack_prx': ('确认上一条 PRx 指令', 'Acknowledges previous PRx packet'),
    'qi.fast_ack': ('快速确认 / 调节状态', 'Fast ACK / regulation status'),
    'qi.prop_no_payload': ('专有包 — 无载荷', 'Proprietary packet — no payload'),
    'qi.empty_pkt': ('无 Payload (空包)', 'Empty packet (no payload)'),
}

KNOWN_LOG_DEFAULT_NAMES = frozenset({'实时报文', 'Live Packet Log', 'Live Capture', 'Live Log'})


def init_language(lang: str | None = None) -> str:
    global _current_language
    if lang:
        _current_language = normalize_language(lang)
    return _current_language


def normalize_language(lang: str) -> str:
    text = str(lang or 'en').strip().lower()
    if text.startswith('zh') or text in ('cn', 'chinese'):
        return 'zh'
    return 'en'


def get_language() -> str:
    return _current_language


def set_language(lang: str) -> None:
    global _current_language
    _current_language = normalize_language(lang)


def tr(key: str, **kwargs) -> str:
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry[1] if _current_language == 'en' else entry[0]
    if kwargs:
        return text.format(**kwargs)
    return text


def tr_in(lang: str, key: str, **kwargs) -> str:
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry[1] if normalize_language(lang) == 'en' else entry[0]
    if kwargs:
        return text.format(**kwargs)
    return text


def is_known_log_default_name(name: str) -> bool:
    return (name or '').strip() in KNOWN_LOG_DEFAULT_NAMES
