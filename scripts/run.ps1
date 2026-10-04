# Start HakiAI on Windows: build the frontend once, check Ollama (start it if installed but not running), then serve
# the API and the built frontend on one port (host/port from backend/app/config.py). Untested on Windows; see README.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$Py = if ($env:PYTHON) { $env:PYTHON } elseif (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

if (-not (Test-Path "frontend\dist\index.html")) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Write-Error "frontend\dist is missing and npm is not installed (install Node.js 20+)" }
    Push-Location frontend
    npm ci; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm run build; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Pop-Location
}

& $Py -m backend.app.preflight
$status = $LASTEXITCODE
if ($status -eq 3 -and (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "starting Ollama in the background"
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        & $Py -m backend.app.preflight *> $null
        $status = $LASTEXITCODE
        if ($status -ne 3) { break }
    }
    if ($status -ne 0) { & $Py -m backend.app.preflight }
}
if ($status -ne 0) { exit $status }

$address = (& $Py -m backend.app.preflight --address).Split(" ")
Write-Host "HakiAI is starting on http://$($address[0]):$($address[1]) (Ctrl+C stops it)"
& $Py -m uvicorn backend.app.main:app --host $address[0] --port $address[1]
