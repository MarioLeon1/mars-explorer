<#
.SYNOPSIS
  Start the backend API (port 8000) and the frontend (port 5173) in two new terminal
  windows, wait until both answer, then open the app in the browser.
  Close the two windows (or press Ctrl+C in them) to stop the servers.
#>
param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'

foreach ($tool in 'uv', 'npm') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: '$tool' not found. Run .\scripts\setup.ps1 first (see docs/SETUP.md)." -ForegroundColor Red
        exit 1
    }
}
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Write-Host "ERROR: frontend dependencies missing. Run .\scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $root 'data\mars.db'))) {
    Write-Host "Note: no local data yet. The app will tell you to run: cd backend; uv run mars-ingest seed" -ForegroundColor Yellow
}

function Test-Url($url) {
    try { Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}

if (Test-Url 'http://127.0.0.1:8000/api/health') {
    Write-Host 'Backend already running on port 8000.'
} else {
    Write-Host 'Starting backend  -> http://127.0.0.1:8000  (API docs: /docs)'
    Start-Process powershell -WorkingDirectory $backend -ArgumentList @(
        '-NoExit', '-Command',
        "`$Host.UI.RawUI.WindowTitle = 'Mars Explorer - backend'; uv run uvicorn mars_explorer.api.app:app --reload --port 8000"
    )
}

if (Test-Url 'http://localhost:5173/') {
    Write-Host 'Frontend already running on port 5173.'
} else {
    Write-Host 'Starting frontend -> http://localhost:5173'
    Start-Process powershell -WorkingDirectory $frontend -ArgumentList @(
        '-NoExit', '-Command',
        "`$Host.UI.RawUI.WindowTitle = 'Mars Explorer - frontend'; npm run dev"
    )
}

Write-Host -NoNewline 'Waiting for both servers'
$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    if ((Test-Url 'http://127.0.0.1:8000/api/health') -and (Test-Url 'http://localhost:5173/')) {
        Write-Host "`nReady: http://localhost:5173" -ForegroundColor Green
        if (-not $NoBrowser) { Start-Process 'http://localhost:5173' }
        exit 0
    }
    Write-Host -NoNewline '.'
    Start-Sleep -Seconds 1
}
Write-Host "`nServers did not answer within 60 s. Check the two new terminal windows for errors." -ForegroundColor Red
exit 1
