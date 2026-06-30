# WiParse — single-file EXE build (Windows)
#
# Prerequisites: Python 3.13, pip, GNU Make (Git for Windows / MSYS2)
#
# Usage:
#   make deps    # install runtime + PyInstaller into .venv
#   make dist    # build dist/WiParse.exe
#   make clean   # remove build artifacts
#   make size    # show output file size
#
# Windows (no Make):  build.bat
#   or: powershell -ExecutionPolicy Bypass -File packaging/build.ps1
#
# Default Python: C:/Program Files/Python313/python.exe
# Override: make dist PYTHON="C:/Path/To/python.exe"
#
# Optional: install UPX (https://github.com/upx/upx/releases) and add to PATH
# to further compress the executable (spec enables UPX when available).

PYTHON ?= "C:/Program Files/Python313/python.exe"
VENV ?= .venv
VENV_PY := $(VENV)/Scripts/python.exe
VENV_PIP := $(VENV)/Scripts/pip.exe

ifeq ($(wildcard $(VENV_PY)),)
  PY := $(PYTHON)
  PIP := $(PYTHON) -m pip
else
  PY := $(VENV_PY)
  PIP := $(VENV_PIP)
endif

SPEC := packaging/wcm_monitor.spec
DIST_EXE := dist/WiParse.exe
APP_NAME := WiParse

.PHONY: all help deps venv dist clean size run check prepare-icon

all: dist

help:
	@echo Targets:
	@echo "  make venv   - create .venv"
	@echo "  make deps   - install requirements + PyInstaller"
	@echo "  make dist   - build single-file $(DIST_EXE)"
	@echo "  make size    - print exe size"
	@echo "  make run     - launch built exe with --demo"
	@echo "  make clean  - remove build/, dist/, PyInstaller cache"
	@echo "  make check  - verify imports before packaging"

venv:
	$(PYTHON) -c "import pathlib, venv; p=pathlib.Path('$(VENV)'); venv.create(p, with_pip=True) if not p.exists() else None"

deps: venv
	-$(PY) -m pip install --isolated --index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements-build.txt

check:
	$(PY) -c "from wireless_charger_monitor.app import main; from wireless_charger_monitor.apps.tektronix_scope import TektronixScopePanel; from wireless_charger_monitor.ui import MonitorWindow; print('OK')"

prepare-icon:
	$(PY) packaging/prepare_icon.py

dist: deps check prepare-icon
	$(PY) -m PyInstaller $(SPEC) --noconfirm --clean
	@echo
	@echo Built: $(DIST_EXE)
	@$(PY) -c "import os; p=r'$(DIST_EXE)'; print('Size: %.2f MiB' % (os.path.getsize(p)/1024/1024)) if os.path.isfile(p) else print('Build failed: missing', p)"

size:
	@$(PY) -c "import os; p=r'$(DIST_EXE)'; print('%.2f MiB' % (os.path.getsize(p)/1024/1024)) if os.path.isfile(p) else print('Not built yet. Run: make dist')"

run: dist
	$(DIST_EXE) --demo

clean:
	-$(PY) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ('build','dist','__pycache__')]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__') if p.is_dir()]"
