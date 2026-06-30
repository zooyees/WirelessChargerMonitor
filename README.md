# WiParse

面向 Qi 2.2.1 协议的手机无线充电测试上位机，支持实时波形监控、报文解析、安全告警、数据持久化与 PDF 测试报告导出。

## 环境要求

- Python 3.8+
- Windows 10/11（推荐，PDF 中文渲染依赖系统字体）
- USB 串口采集硬件

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
# 正常模式（连接真实硬件）
python main.py

# 演示模式（无硬件时 UI 调试，数据为模拟生成，不可用于正式测试）
python main.py --demo

# 或使用模块方式启动
python -m wireless_charger_monitor --demo
```

## 硬件数据格式

### 电参数据帧

```
AA55:<Vin_mV>:<Iin_mA>:<Vout_mV>:<Iout_mA>:<Vbat_mV>:<Ibat_mA>:<Temp>:<Battery>:EDED
```

示例：

```
AA55:9000:1500:8500:1400:4000:3000:45:80:EDED
```

各字段单位为 mV / mA（程序内自动换算为 V / A）。

### Qi 报文日志

```
TX0:[HH:MM:SS.mmm] ASK 51 3E 00 00 00 00 F
TX0:[HH:MM:SS.mmm] FSK 40 03 F
```

## 配置文件 `config.json`

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `system.db_name` | SQLite 数据库路径 | `charging_data.db` |
| `system.log_file` | 运行日志文件 | `monitor.log` |
| `system.log_level` | 日志级别 | `INFO` |
| `system.db_commit_interval_sec` | 数据库定时提交间隔（秒） | `1.0` |
| `system.db_commit_batch_size` | 批量提交条数阈值 | `100` |
| `ui.render_interval_ms` | UI 刷新间隔 | `100` |
| `ui.chart_max_points` | 实时曲线最大点数 | `500` |
| `ui.default_window_size_sec` | 图表默认时间窗口 | `60.0` |
| `alerts.ovp_threshold` | 过压告警阈值 (V) | `25.0` |
| `alerts.ocp_threshold` | 过流告警阈值 (A) | `3.0` |
| `alerts.temp_warning_threshold` | 过温告警阈值 (°C) | `60` |
| `alerts.full_charge_debounce_sec` | 满电提示 debounce (秒) | `20.0` |
| `serial.default_baudrates` | 可选波特率列表 | 见配置文件 |
| `serial.demo_mode` | 串口失败时启用演示模式 | `false` |
| `serial.auto_reconnect` | 串口断线自动重连 | `true` |
| `serial.reconnect_interval_sec` | 重连间隔 (秒) | `3.0` |
| `serial.max_reconnect_attempts` | 最大重连次数 | `5` |

## 功能概览

- **实时监控**：输入/输出/电池电压电流、功率、温度、电量
- **Qi 2.2.1 解析**：报文悬停 tooltip 深度解码
- **测试会话**：每次「开始」创建独立 session，CSV/PDF/日志按当前会话导出
- **安全告警**：OVP / OCP / OTP 非模态状态栏提示
- **数据导出**：CSV 表格、PDF 专业测试报告、全量报文日志
- **历史浏览**：图表十字准线、双击跳转日志、日志分页加载

## 工程结构

```
WiParse/
├── main.py                          # 启动入口（薄封装）
├── config.json                      # 用户配置（相对路径基于项目根目录）
├── requirements.txt
├── compile_ui.bat                   # 可选：.ui → Python 桩代码
├── tools/                           # 开发与维护脚本
└── wireless_charger_monitor/        # 主包
    ├── app.py                       # QApplication 与 argparse
    ├── config.py                    # 配置加载与默认值
    ├── paths.py                     # 项目根路径解析
    ├── logging_setup.py             # 日志初始化
    ├── db/                          # SQLite 持久化
    │   ├── schema.py                # 表结构与 init_db
    │   └── sessions.py              # 测试会话 CRUD
    ├── workers/                     # 后台线程
    │   ├── serial_worker.py         # 串口采集 / Demo
    │   ├── db_worker.py             # 异步写库
    │   └── fetch_worker.py          # 历史图表 / 日志分页
    ├── ui/                          # 界面层
    │   ├── monitor_window.ui        # Qt Designer 布局（可编辑）
    │   ├── loader.py                # 加载 .ui + PyQtGraph 图表
    │   └── main_window.py           # 主窗口业务逻辑
    ├── protocol/
    │   └── qi_parser.py             # Qi 2.2.1 协议解析
    └── report/
        └── engine.py                # PDF 测试报告
```

运行时自动生成（已在 `.gitignore` 中忽略）：`charging_data.db`、`monitor.log`、`Unknown_Qi_Commands_Log.txt`、导出 PDF/CSV 等。

## 文件说明

| 路径 | 说明 |
|------|------|
| `main.py` | 启动入口，调用 `wireless_charger_monitor.app.main()` |
| `wireless_charger_monitor/ui/monitor_window.ui` | Qt Designer 界面定义 |
| `wireless_charger_monitor/ui/loader.py` | 加载 `.ui` 并注入 PyQtGraph 图表 |
| `wireless_charger_monitor/ui/main_window.py` | 监控主窗口控制器 |
| `compile_ui.bat` | 可选：将 `.ui` 编译为 Python 桩代码 |
| `config.json` | 运行参数（数据库、告警阈值、串口等） |

## 常见问题

**Q: 串口连接失败？**  
检查 COM 口是否正确、设备是否被其他程序占用，点击「刷新端口」后重试。

**Q: PDF 中文乱码？**  
确保系统已安装「微软雅黑」或「黑体」字体（Windows 默认有）。

**Q: 演示模式与正式测试的区别？**  
演示模式在串口不可用时生成模拟数据，界面会显示橙色「演示模式」警示，不可用于正式测试报告。

**Q: 如何用 Qt Designer 修改界面？**  
用 Designer 打开 `wireless_charger_monitor/ui/monitor_window.ui`，保存后直接运行即可。样式以 `theme.py` 为单一来源；修改主题后请运行 `python tools/generate_monitor_ui.py` 同步 `.ui` 预览效果。PyQtGraph 图表区域由 `loader.py` 运行时注入，Design 模式下显示占位提示。
