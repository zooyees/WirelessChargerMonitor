@echo off
REM WiParse single-file build (Python 3.13). Override: set PYTHON_HOME=C:\Path\To\Python313
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0packaging\build.ps1" %*
if errorlevel 1 exit /b 1
