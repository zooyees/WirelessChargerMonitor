# Build single-file EXE (Windows). Equivalent to: make dist
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VenvPy = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPy)) {
    python -c "import pathlib, venv; p=pathlib.Path('.venv'); venv.create(p, with_pip=True) if not p.exists() else None"
}
if (-not (Test-Path $VenvPy)) {
    throw 'Failed to create .venv'
}

# Ignore user/global pip mirrors (e.g. tsinghua) that can break index-url on some setups.
$env:HTTP_PROXY = ''
$env:HTTPS_PROXY = ''
$env:ALL_PROXY = ''
$env:NO_PROXY = '*'
$env:PIP_CONFIG_FILE = 'NUL'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$PipArgs = @(
    '--isolated',
    '--index-url', 'https://pypi.org/simple',
    '--trusted-host', 'pypi.org',
    '--trusted-host', 'files.pythonhosted.org'
)

& $VenvPy -m pip install @PipArgs -r requirements-build.txt
& $VenvPy -c "import PyQt5, pyqtgraph, serial; from wireless_charger_monitor.app import main; print('OK')"
& $VenvPy -m PyInstaller packaging/wcm_monitor.spec --noconfirm --clean

$Exe = Join-Path $Root 'dist\WiParse.exe'
if (-not (Test-Path $Exe)) {
    throw "Build failed: missing $Exe"
}
$SizeMiB = (Get-Item $Exe).Length / 1MB
Write-Host "Built: $Exe"
Write-Host ("Size: {0:N2} MiB" -f $SizeMiB)
