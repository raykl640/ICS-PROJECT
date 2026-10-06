# Build the HakiAI desktop app for Windows (D34): dist\HakiAI\ and dist\HakiAI-Setup-x64.exe (+ .sha256), using
# Inno Setup 6 (iscc on PATH or in its default folder). Same steps as build_desktop.sh: indexes when missing or stale,
# the frontend, PyInstaller, then the packaged app's --self-test before the installer is made.
param([string]$Version = "0.0.0-dev")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$py = if (Test-Path .venv\Scripts\python.exe) { ".venv\Scripts\python.exe" } else { "python" }

function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
}

if (-not (Test-Path data\processed\chunks.json)) {
    throw "data\processed\chunks.json is missing (build it: python -m backend.app.ingestion.build_corpus)"
}
& $py -c "import sys; from backend.app.config import get_settings; from backend.app.preflight import index_problems; sys.exit(1 if index_problems(get_settings()) else 0)"
if ($LASTEXITCODE -ne 0) { Invoke-Checked $py @("-m", "backend.app.ingestion.build_index") }

Push-Location frontend
try {
    if (-not (Test-Path node_modules)) { Invoke-Checked npm @("ci") }
    Invoke-Checked npm @("run", "build")
} finally { Pop-Location }

Invoke-Checked $py @("-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", "dist", "--workpath", "build\pyinstaller", "desktop\hakiai.spec")
Invoke-Checked "dist\HakiAI\HakiAI.exe" @("--self-test")

$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe" }
Invoke-Checked $iscc @("/DAppVersion=$Version", "desktop\windows\hakiai.iss")

$hash = (Get-FileHash dist\HakiAI-Setup-x64.exe -Algorithm SHA256).Hash.ToLower()
"$hash  HakiAI-Setup-x64.exe" | Set-Content -Encoding ascii dist\HakiAI-Setup-x64.exe.sha256
Write-Host "built dist\HakiAI-Setup-x64.exe"
