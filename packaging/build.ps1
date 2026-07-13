# Build single-file EXE (Windows). Equivalent to: make dist
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Default: Python 3.13 installed for all users. Override with env PYTHON_HOME.
$PythonHome = if ($env:PYTHON_HOME) { $env:PYTHON_HOME } else { 'C:\Program Files\Python313' }
$SystemPython = Join-Path $PythonHome 'python.exe'

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    if (Test-Path $SystemPython) {
        & $SystemPython @Args
        return
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.13 @Args
        return
    }
    & python @Args
}

Write-Host "Using Python: $(Invoke-Python -Args @('-c', 'import sys; print(sys.executable)'))"

$VenvDir = Join-Path $Root '.venv'
$VenvPy = Join-Path $VenvDir 'Scripts\python.exe'
$ExpectedMinor = if (Test-Path $SystemPython) {
    & $SystemPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
} else {
    '3.10'
}
if (Test-Path $VenvPy) {
    $VenvMinor = & $VenvPy -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($VenvMinor -ne $ExpectedMinor) {
        Write-Host "Recreating .venv (found Python $VenvMinor, need $ExpectedMinor)"
        try {
            Remove-Item $VenvDir -Recurse -Force -ErrorAction Stop
        } catch {
            Write-Warning "Could not remove .venv ($($_.Exception.Message)); reusing existing environment."
        }
    }
}
if (-not (Test-Path $VenvPy)) {
    Invoke-Python -Args @(
        '-c',
        "import pathlib, venv; p=pathlib.Path('.venv'); venv.create(p, with_pip=True) if not p.exists() else None"
    )
}
if (-not (Test-Path $VenvPy)) {
    throw "Failed to create .venv with $SystemPython"
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
& $VenvPy -c @"
from wireless_charger_monitor.app import main
from wireless_charger_monitor.cli.main import main as cli_main
from wireless_charger_monitor.apps.tektronix_scope import TektronixScopePanel
from wireless_charger_monitor.ui import MonitorWindow
print('OK')
"@
if (-not (Test-Path (Join-Path $Root 'Icon\WiParse.ico'))) {
    throw 'Missing Icon\WiParse.ico — place WiParse.ico under the Icon folder.'
}
& $VenvPy packaging/prepare_icon.py

Write-Host 'Building GUI: WiParse.exe ...'
& $VenvPy -m PyInstaller packaging/wcm_monitor.spec --noconfirm --clean

$Exe = Join-Path $Root 'dist\WiParse.exe'
if (-not (Test-Path $Exe)) {
    throw "Build failed: missing $Exe"
}
$SizeMiB = (Get-Item $Exe).Length / 1MB
Write-Host "Built: $Exe"
Write-Host ("Size: {0:N2} MiB" -f $SizeMiB)

Write-Host 'Building CLI: WiParseCLI.exe ...'
& $VenvPy -m PyInstaller packaging/wiparse_cli.spec --noconfirm --clean

$CliExe = Join-Path $Root 'dist\WiParseCLI.exe'
if (-not (Test-Path $CliExe)) {
    throw "Build failed: missing $CliExe"
}
$CliSizeMiB = (Get-Item $CliExe).Length / 1MB
Write-Host "Built: $CliExe"
Write-Host ("Size: {0:N2} MiB" -f $CliSizeMiB)

# Only remove a leftover named exactly "wiparse.exe" (not WiParse.exe).
# Windows is case-insensitive, so Test-Path 'wiparse.exe' would also match WiParse.exe.
Get-ChildItem (Join-Path $Root 'dist') -Filter '*.exe' -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ceq 'wiparse.exe' } |
    Remove-Item -Force

Write-Host ''
Write-Host 'Distribute both from dist\:'
Write-Host '  WiParse.exe     — GUI'
Write-Host '  WiParseCLI.exe  — CLI (AI / scripts)'
