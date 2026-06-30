@echo off
REM 从 Qt Designer .ui 生成 Python 桩代码（可选）
set UI=wireless_charger_monitor\ui\monitor_window.ui
set OUT=wireless_charger_monitor\ui\ui_monitor_generated.py

where pyuic5 >nul 2>&1
if errorlevel 1 (
    python -m PyQt5.uic.pyuic %UI% -o %OUT%
) else (
    pyuic5 %UI% -o %OUT%
)

if errorlevel 1 (
    echo 编译失败。请确认已安装 PyQt5: pip install PyQt5
    exit /b 1
)
echo 已生成 %OUT%
echo 程序默认通过 uic.loadUi 加载 .ui，无需此步骤亦可运行。
