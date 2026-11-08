param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$pythonPath = Join-Path $backendPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Backend virtual environment is missing.' }
if ($CheckOnly) { & $pythonPath (Join-Path $PSScriptRoot 'check_local.py'); exit $LASTEXITCODE }
$alreadyRunning = $false
try { $health = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 3; $alreadyRunning = $health.status -eq 'ok' } catch { }
if (-not $alreadyRunning) {
    $occupied = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($occupied) { throw 'Port 8000 is occupied. No process was stopped; check the existing app.' }
    Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $backendPath -WindowStyle Hidden
}
$ready = $false
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    try { $health = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2; if ($health.status -eq 'ok') { $ready = $true; break } } catch { }
    Start-Sleep -Milliseconds 800
}
if (-not $ready) { throw 'FastAPI did not become ready. Run it in your VS Code backend terminal to inspect startup errors.' }
Write-Output 'ENWEN is running at http://127.0.0.1:8000/. Existing records and processes were preserved.'
Write-Output 'Ollama, PostgreSQL and Mailpit are checked below; this script never installs services or sends messages.'
& $pythonPath (Join-Path $PSScriptRoot 'check_local.py')
exit $LASTEXITCODE
