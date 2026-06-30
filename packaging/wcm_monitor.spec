# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: single-file GUI executable (size-optimized).
# Build: build.bat  (or: make dist / packaging/build.ps1)
# Python 3.13 recommended; default host: C:\Program Files\Python313

from pathlib import Path

_spec_dir = Path(SPECPATH).resolve()
ROOT = _spec_dir.parent
PKG = ROOT / 'wireless_charger_monitor'

block_cipher = None

excludes = [
    'matplotlib',
    'tkinter',
    'tcl',
    'tk',
    '_tkinter',
    'pytest',
    'setuptools',
    'pip',
    'wheel',
    'IPython',
    'jupyter',
    'notebook',
    'scipy',
    'pandas',
    'PIL',
    'cv2',
    'unittest',
    'xmlrpc',
    'numpy.tests',
    'numpy.testing',
    'PyQt5.QtWebEngine',
    'PyQt5.QtWebEngineCore',
    'PyQt5.QtWebEngineWidgets',
    'PyQt5.QtBluetooth',
    'PyQt5.QtMultimedia',
    'PyQt5.QtMultimediaWidgets',
    'PyQt5.QtNetworkAuth',
    'PyQt5.QtLocation',
    'PyQt5.QtNfc',
    'PyQt5.QtPositioning',
    'PyQt5.QtQuick',
    'PyQt5.QtQuickWidgets',
    'PyQt5.QtQml',
    'PyQt5.QtWebSockets',
    'PyQt5.QtDesigner',
    'PyQt5.QtHelp',
    'PyQt5.QtSql',
    'PyQt5.QtTest',
    'PyQt5.QtXml',
    'PyQt5.QtXmlPatterns',
]

datas = [
    (str(PKG / 'ui' / 'monitor_window.ui'), 'wireless_charger_monitor/ui'),
    (str(PKG / 'apps' / 'tektronix_scope' / 'tektronix_scope.ui'), 'wireless_charger_monitor/apps/tektronix_scope'),
    (str(ROOT / 'packaging' / 'default_config.json'), '.'),
    (str(ROOT / 'packaging' / 'WiParse.ico'), 'Icon'),
]

_icon_file = (ROOT / 'packaging' / 'WiParse.ico').resolve()
if not _icon_file.is_file():
    raise SystemExit(
        f'Missing build icon: {_icon_file}\n'
        'Run: python packaging/prepare_icon.py'
    )

hiddenimports = [
    'serial.tools.list_ports',
    'serial.tools.list_ports_common',
    'serial.tools.list_ports_windows',
    'pyqtgraph',
    'pyvisa',
    'pyvisa_py',
    'numpy.lib.format',
    # pyqtgraph.parametertree.interactive imports pydoc at startup
    'pydoc',
    'pydoc_data',
    'doctest',
]

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / 'packaging' / 'runtime_hook.py')],
    excludes=excludes,
    noarchive=False,
    # optimize=2 strips docstrings; NumPy 2.x fails at import without them.
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WiParse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX can break the PE icon resource table; Explorer / shortcuts then show generic icon.
    upx=False,
    upx_exclude=[
        'vcruntime140.dll',
        'python*.dll',
        'Qt5Core.dll',
        'Qt5Gui.dll',
        'Qt5Widgets.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_icon_file),
)
