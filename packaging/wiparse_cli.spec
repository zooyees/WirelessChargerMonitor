# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: single-file console CLI (wiparse.exe).
# Built alongside WiParse.exe by packaging/build.ps1

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
    # CLI does not need the full GUI chart stack
    'pyqtgraph',
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
    (str(ROOT / 'packaging' / 'default_config.json'), '.'),
]

_icon_file = (ROOT / 'packaging' / 'WiParse.ico').resolve()
icon_kw = {}
if _icon_file.is_file():
    icon_kw['icon'] = str(_icon_file)

hiddenimports = [
    'serial.tools.list_ports',
    'serial.tools.list_ports_common',
    'serial.tools.list_ports_windows',
    'pyvisa',
    'pyvisa_py',
    'wireless_charger_monitor.cli',
    'wireless_charger_monitor.cli.main',
    'wireless_charger_monitor.cli.serial_capture',
    'wireless_charger_monitor.cli.wave_export',
    'wireless_charger_monitor.cli.capture',
    'wireless_charger_monitor.apps.tektronix_scope.client',
    'wireless_charger_monitor.protocol.qi_parser',
    'wireless_charger_monitor.protocol.protocol_defs',
]

a = Analysis(
    [str(ROOT / 'wiparse_cli.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / 'packaging' / 'runtime_hook.py')],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='wiparse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[
        'vcruntime140.dll',
        'python*.dll',
    ],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    **icon_kw,
)
