"""UI internationalization (English / Chinese)."""

from __future__ import annotations

_current_language = 'en'

# (zh_CN, en_US)
STRINGS: dict[str, tuple[str, str]] = {
    'app.title': ('WiParse', 'WiParse'),
    'status.ready': ('就绪', 'Ready'),
    'menu.settings': ('设置(&S)', '&Settings'),
    'menu.panels': ('显示面板', 'Panels'),
    'tool.open': ('打开', 'Open'),
    'tool.serial_tool.name': ('串口工具', 'Serial Tool'),
    'tool.waveform_scope.name': ('示波器工具', 'Scope Tool'),
    'tool.tektronix_scope.name': ('泰克示波器', 'Tektronix Scope'),
    'tool.tektronix_scope.title': ('泰克示波器', 'Tektronix Scope'),
    'tool.tektronix_scope.connect': ('连接', 'Connect'),
    'tool.tektronix_scope.capture1': ('截图并复制1', 'Capture & Copy 1'),
    'tool.tektronix_scope.capture2': ('截图并复制2', 'Capture & Copy 2'),
    'tool.tektronix_scope.refresh_wave': ('刷新', 'Refresh'),
    'tool.tektronix_scope.refresh_wave_tip': ('手动拉取波形（CURVe）', 'Manually refresh waveforms (CURVe)'),
    'tool.tektronix_scope.live': ('实时', 'Live'),
    'tool.tektronix_scope.capture_shot': ('截图', 'Shot'),
    'tool.tektronix_scope.capture_shot_tip': ('HARDCopy 截图并复制到剪贴板', 'HARDCopy screenshot and copy to clipboard'),
    'tool.tektronix_scope.model_tip': ('已连接示波器型号', 'Connected scope model'),
    'tool.tektronix_scope.live_tip': ('开启后按固定间隔拉取 CURVe（已做降采样与节流）', 'Periodically fetch CURVe (downsampled & throttled)'),
    'tool.tektronix_scope.live_on': ('实时波形已开启（间隔 {ms} ms）', 'Live waveform ON (interval {ms} ms)'),
    'tool.tektronix_scope.live_off': ('实时波形已关闭', 'Live waveform OFF'),
    'tool.tektronix_scope.scope_n': ('示波器 {n}', 'Scope {n}'),
    'tool.tektronix_scope.status_disconnected': ('未连接', 'Disconnected'),
    'tool.tektronix_scope.grp_session': ('连接', 'Session'),
    'tool.tektronix_scope.grp_function': ('功能键', 'Function'),
    'tool.tektronix_scope.grp_vertical': ('垂直', 'Vertical'),
    'tool.tektronix_scope.grp_multipurpose': ('通用 a / b', 'Multipurpose a / b'),
    'tool.tektronix_scope.grp_dock': ('前面板控制', 'Front Panel'),
    'tool.tektronix_scope.grp_softkeys': ('屏下软键', 'Soft Keys'),
    'tool.tektronix_scope.grp_wave_inspector': ('导航', 'Navigator'),
    'tool.tektronix_scope.grp_horizontal': ('水平', 'Horizontal'),
    'tool.tektronix_scope.grp_trigger': ('触发', 'Trigger'),
    'tool.tektronix_scope.grp_acquire_ctrl': ('采集', 'Acquire'),
    'tool.tektronix_scope.menu_measure': ('测量', 'Measure'),
    'tool.tektronix_scope.menu_search': ('搜索', 'Search'),
    'tool.tektronix_scope.menu_acquire': ('采集', 'Acquire'),
    'tool.tektronix_scope.menu_trigger': ('触发菜单', 'Trigger Menu'),
    'tool.tektronix_scope.menu_math': ('M', 'M'),
    'tool.tektronix_scope.menu_ref': ('R', 'R'),
    'tool.tektronix_scope.menu_afg': ('AFG', 'AFG'),
    'tool.tektronix_scope.menu_rf': ('射频', 'RF'),
    'tool.tektronix_scope.menu_test': ('测试', 'Test'),
    'tool.tektronix_scope.menu_off': ('关菜单', 'Menu Off'),
    'tool.tektronix_scope.side_placeholder': ('按左侧功能键\n打开侧菜单', 'Press a function key\nto open side menu'),
    'tool.tektronix_scope.preview_show': ('截图预览 ▸', 'Screenshot ▸'),
    'tool.tektronix_scope.preview_hide': ('截图预览 ▾', 'Screenshot ▾'),
    'tool.tektronix_scope.preview_empty': ('截图预览（HARDCopy）', 'Screenshot preview (HARDCopy)'),
    'tool.tektronix_scope.log_show': ('状态日志 ▸', 'Status Log ▸'),
    'tool.tektronix_scope.log_hide': ('状态日志 ▾', 'Status Log ▾'),
    'tool.tektronix_scope.log_placeholder': ('状态日志…', 'Status log…'),
    'tool.tektronix_scope.fine': ('精细', 'Fine'),
    'tool.tektronix_scope.fine_tip': ('粗调 / 细调切换（影响所有旋钮步进）', 'Coarse / fine step for all knobs'),
    'tool.tektronix_scope.select': ('选择', 'Select'),
    'tool.tektronix_scope.select_tip': (
        '按「选择」切换通用旋钮 a/b 绑定',
        'Press Select to cycle multipurpose a/b bindings',
    ),
    'tool.tektronix_scope.multi_mode_0': (
        '通用旋钮：a=触发电平，b=水平位置',
        'Multipurpose: a=trig level, b=horiz pos',
    ),
    'tool.tektronix_scope.multi_mode_1': (
        '通用旋钮：a=水平时基，b=水平位置',
        'Multipurpose: a=horiz scale, b=horiz pos',
    ),
    'tool.tektronix_scope.ch_side_tip': (
        '{ch} 垂直快捷：耦合 / 带宽 / 探头',
        '{ch} vertical shortcuts: coupling / BW / probe',
    ),
    'tool.tektronix_scope.side_vertical': ('垂直 {ch}', 'Vertical {ch}'),
    'tool.tektronix_scope.coup_dc': ('耦合 DC', 'Coupling DC'),
    'tool.tektronix_scope.coup_ac': ('耦合 AC', 'Coupling AC'),
    'tool.tektronix_scope.bw_full': ('带宽 Full', 'Bandwidth Full'),
    'tool.tektronix_scope.bw_20': ('带宽 20 MHz', 'Bandwidth 20 MHz'),
    'tool.tektronix_scope.probe_1x': ('探头 1×', 'Probe 1×'),
    'tool.tektronix_scope.probe_10x': ('探头 10×', 'Probe 10×'),
    'tool.tektronix_scope.save_recall': ('存/调', 'Save/Rcl'),
    'tool.tektronix_scope.default_setup': ('默认', 'Default'),
    'tool.tektronix_scope.utility': ('辅助', 'Utility'),
    'tool.tektronix_scope.bus1': ('B1', 'B1'),
    'tool.tektronix_scope.bus2': ('B2', 'B2'),
    'tool.tektronix_scope.ref': ('R', 'R'),
    'tool.tektronix_scope.math': ('M', 'M'),
    'tool.tektronix_scope.cursors': ('光标', 'Cursors'),
    'tool.tektronix_scope.intensity': ('亮度', 'Intens'),
    'tool.tektronix_scope.digital': ('D15-D0', 'D15-D0'),
    'tool.tektronix_scope.save': ('保存', 'Save'),
    'tool.tektronix_scope.zoom': ('缩放', 'Zoom'),
    'tool.tektronix_scope.zoom_tip': ('打开/关闭缩放模式', 'Enable / disable zoom mode'),
    'tool.tektronix_scope.mark_prev': ('←标记', '←Mark'),
    'tool.tektronix_scope.mark_set': ('设/清', 'Set/Clr'),
    'tool.tektronix_scope.mark_next': ('标记→', 'Mark→'),
    'tool.tektronix_scope.play_pause': ('播放', 'Play'),
    'tool.tektronix_scope.force_trigger': ('强制', 'Force'),
    'tool.tektronix_scope.autoset': ('自动', 'Autoset'),
    'tool.tektronix_scope.autoset_tip': ('自动设置垂直 / 水平 / 触发', 'Autoset vertical / horizontal / trigger'),
    'tool.tektronix_scope.single': ('单次', 'Single'),
    'tool.tektronix_scope.run_stop': ('运行/停止', 'Run/Stop'),
    'tool.tektronix_scope.run_stop_tip': ('开始或停止采集（亮起=正在运行）', 'Start or stop acquisition (lit = running)'),
    'tool.tektronix_scope.stop': ('停止', 'Stop'),
    'tool.tektronix_scope.knob_position': ('位置', 'Position'),
    'tool.tektronix_scope.knob_scale': ('标度', 'Scale'),
    'tool.tektronix_scope.knob_center': ('居中', 'Center'),
    'tool.tektronix_scope.knob_hpos': ('位移', 'H Pos'),
    'tool.tektronix_scope.knob_hscale': ('时基', 'H Scale'),
    'tool.tektronix_scope.knob_hpos_push': ('10%/居中', '10%/Ctr'),
    'tool.tektronix_scope.knob_trig': ('电平', 'Level'),
    'tool.tektronix_scope.knob_trig_push': ('50%', '50%'),
    'tool.tektronix_scope.knob_pan': ('平移', 'Pan'),
    'tool.tektronix_scope.knob_zoom_scale': ('比例', 'Scale'),
    'tool.tektronix_scope.knob_a': ('a', 'a'),
    'tool.tektronix_scope.knob_b': ('b', 'b'),
    'tool.tektronix_scope.ch_tip': ('{ch}：按下显示/关闭通道并打开垂直菜单', '{ch}: show/hide channel and open vertical menu'),
    'tool.tektronix_scope.pos_tip': ('{ch} 垂直位置 · 按下居中', '{ch} vertical position · push to center'),
    'tool.tektronix_scope.scale_tip': ('{ch} 伏/格', '{ch} V/div'),
    'tool.tektronix_scope.push_tip': ('对应真机旋钮“按下”功能', 'Corresponds to pushing the physical knob'),
    'tool.tektronix_scope.side_acquire': ('采集', 'Acquire'),
    'tool.tektronix_scope.side_trigger': ('触发菜单', 'Trigger Menu'),
    'tool.tektronix_scope.side_measure': ('测量', 'Measure'),
    'tool.tektronix_scope.side_search': ('搜索', 'Search'),
    'tool.tektronix_scope.side_math': ('数学', 'Math'),
    'tool.tektronix_scope.side_ref': ('参考', 'Reference'),
    'tool.tektronix_scope.side_bus1': ('总线 B1', 'Bus B1'),
    'tool.tektronix_scope.side_bus2': ('总线 B2', 'Bus B2'),
    'tool.tektronix_scope.side_afg': ('AFG', 'AFG'),
    'tool.tektronix_scope.side_rf': ('射频', 'RF'),
    'tool.tektronix_scope.side_test': ('测试', 'Test'),
    'tool.tektronix_scope.side_save_recall': ('保存/调出', 'Save/Recall'),
    'tool.tektronix_scope.side_utility': ('辅助功能', 'Utility'),
    'tool.tektronix_scope.side_intensity': ('亮度', 'Intensity'),
    'tool.tektronix_scope.apply': ('应用', 'Apply'),
    'tool.tektronix_scope.apply_edge': ('应用边沿触发', 'Apply Edge Trigger'),
    'tool.tektronix_scope.acq_mode': ('采集模式', 'Acquire Mode'),
    'tool.tektronix_scope.record_length': ('记录长度', 'Record Length'),
    'tool.tektronix_scope.edge_source': ('边沿源', 'Edge Source'),
    'tool.tektronix_scope.slope': ('斜率', 'Slope'),
    'tool.tektronix_scope.trig_mode': ('模式', 'Mode'),
    'tool.tektronix_scope.conn_failed_list': ('连接失败：无法枚举 USB 设备', 'Connection failed: cannot list USB instruments'),
    'tool.tektronix_scope.conn_failed_open': ('连接失败：无法打开设备', 'Connection failed: cannot open instrument'),
    'tool.tektronix_scope.conn_failed': ('连接失败：设备无响应', 'Connection failed: instrument did not respond'),
    'tool.tektronix_scope.conn_success': ('连接成功（发现 {count} 台示波器）', 'Connected ({count} scope(s) found)'),
    'tool.tektronix_scope.conn_success_single': ('连接成功！', 'Connection successful!'),
    'tool.tektronix_scope.conn_none': ('未发现泰克示波器 / 未连接', 'No Tektronix scope found / not connected'),
    'tool.tektronix_scope.save_error': ('截图保存失败', 'Failed to capture screenshot'),
    'tool.tektronix_scope.save_ok': ('已保存：{path}', 'Saved: {path}'),
    'tool.tektronix_scope.copy_ok': ('已复制到剪贴板', 'Copied to clipboard'),
    'tool.tektronix_scope.copy_failed': ('复制到剪贴板失败', 'Failed to copy to clipboard'),
    'tool.tektronix_scope.scope_unavailable': ('示波器 {index} 不可用', 'Scope {index} is not available'),
    'tool.tektronix_scope.busy': ('示波器忙，请稍候…', 'Scope busy, please wait…'),
    'tool.tektronix_scope.wave_ok': ('已刷新 {n} 路波形', 'Refreshed {n} waveform(s)'),
    'tool.tektronix_scope.autoset_ok': ('已执行自动设置', 'Autoset executed'),
    'tool.tektronix_scope.default_ok': ('已恢复默认设置', 'Default setup restored'),
    'tool.tektronix_scope.fine_on': ('精细调节：开', 'Fine adjust: ON'),
    'tool.tektronix_scope.fine_off': ('精细调节：关', 'Fine adjust: OFF'),
    'tool.tektronix_scope.need_mso': ('D15–D0 需要 MDO3MSO 选件', 'D15–D0 requires MDO3MSO option'),
    'tool.tektronix_scope.play_hint': ('播放/暂停：用平移旋钮控制方向与速度（Wave Inspector）', 'Play/Pause: use pan knob for direction/speed'),
    'tool.tektronix_scope.play_on': ('播放：开（可用平移旋钮浏览）', 'Play: ON (pan knob to browse)'),
    'tool.tektronix_scope.play_off': ('播放：关', 'Play: OFF'),
    'menu.language': ('语言', 'Language'),
    'menu.menu_bar_auto_hide': ('自动隐藏', 'Auto Hide'),
    'menu.menu_bar_always_show': ('始终显示 (不隐藏)', 'Always Show'),
    'menu.theme': ('风格', 'Theme'),
    'menu.theme_dark': ('深色', 'Dark'),
    'menu.theme_light': ('浅色', 'Light'),
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
    'charge.analyzing': ('⚡ 充电状态分析中...', '⚡ Analyzing charge phase…'),
    'charge.idle': ('🔌 未充电 / 待机中', '🔌 Idle / Standby'),
    'charge.cc': ('🔵 恒流充电阶段 (CC)', '🔵 CC Phase'),
    'charge.cv': ('🟡 恒压充电阶段 (CV)', '🟡 CV Phase'),
    'charge.trickle': ('🟢 涓流阶段 / 已满电', '🟢 Trickle / Full'),
    'charge.negotiate': ('🔄 动态功率协商中...', '🔄 Power negotiation…'),
    'chart.placeholder': (
        '📈 实时波形区域\n（程序运行时由 PyQtGraph 加载）',
        '📈 Waveform Plot\n(rendered at runtime)',
    ),
    'btn.start': ('▶ 开始', '▶ Start'),
    'btn.stop': ('⏹ 停止', '⏹ Stop'),
    'btn.new': ('新建', 'New'),
    'btn.clear': ('清屏', 'Clear'),
    'btn.browse_dir': ('📁 选择路径', '📁 Browse…'),
    'btn.open_log': ('📂 打开文件', '📂 Open…'),
    'btn.browse_tooltip': ('选择实时报文保存目录', 'Select the output directory for live capture files'),
    'log.filename': ('文件名', 'Log Name'),
    'log.save_dir': ('保存路径', 'Output Directory'),
    'log.default_filename': ('实时报文', 'Live Packet Log'),
    'log.name_placeholder': ('实时报文', 'Live Packet Log'),
    'log.name_tooltip': (
        '不含扩展名；Enter 仅切换当前页写入的新文件名（不新建标签）',
        'Base name without extension; Enter switches the current live file only (no new tab)',
    ),
    'log.dir_tooltip': ('实时报文 TXT 文件保存目录', 'Directory where live capture files (.txt) are saved'),
    'log.new_tooltip': (
        '新建一段采集：新标签页 + 自动时间戳文件名，旧实时页保留在右侧',
        'New capture session: fresh tab with timestamped filename; previous live tab stays on the right',
    ),
    'log.clear_tooltip': (
        '清空实时报文窗口显示（不删除已保存文件）',
        'Clear the live packet view only (saved file is not deleted)',
    ),
    'log.open_tooltip': ('打开本地 TXT 日志文件（可多选）', 'Open one or more capture/log files (.txt)'),
    'log.filter': ('数据筛选', 'Filter'),
    'log.filter_placeholder': ('完整匹配·回车', 'Exact match · Enter'),
    'log.split_enable': ('数据分窗', 'Split View'),
    'log.split_tooltip': ('启用后将报文按条件分到多个窗口显示', 'Route packets into separate panes by filter criteria'),
    'log.panes_tooltip': ('分窗数量（启用 Split View 后有效）', 'Number of panes (when Split View is enabled)'),
    'log.filter_tooltip': (
        '完整字符串匹配；多个关键词用 | 分隔（保留空格）；按 Enter 应用；'
        '打开文件时结果显示在下方，双击可跳转原文',
        'Exact substring match; separate multiple terms with | (spaces preserved); press Enter; '
        'for opened files, results appear below — double-click to jump',
    ),
    'log.case_sensitive': ('区分大小写', 'Case sensitive'),
    'log.case_sensitive_tooltip': (
        '勾选后搜索严格区分大小写；未勾选时不区分大小写',
        'When checked, search matches letter case exactly; otherwise case-insensitive',
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
    'log.search_results': ('搜索结果', 'Search Results'),
    'log.search_results_count': ('搜索结果 ({n})', 'Search Results ({n})'),
    'log.search_results_close': ('关闭', 'Close'),
    'log.search_results_tooltip': (
        '双击某行可在上方原文中跳转到对应行',
        'Double-click a row to jump to that line in the document above',
    ),
    'log.tab.close_current': ('关闭当前', 'Close Current'),
    'log.tab.close_all': ('关闭所有', 'Close All'),
    'dialog.create_failed': ('创建失败', 'Create Failed'),
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
    'status.loading_log_lines': ('正在加载日志… 已读取 {n} 行', 'Loading log… {n} lines read'),
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
