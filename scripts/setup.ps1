<#
.SYNOPSIS
  One-time project setup: checks tools, installs backend and frontend dependencies,
  optionally downloads the curated real NASA dataset.

.EXAMPLE
  .\scripts\setup.ps1          # install dependencies
  .\scripts\setup.ps1 -Seed    # ...and download ~13 MB of real Perseverance data
#>
param([switch]$Seed)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "ERROR: $text" -ForegroundColor Red; exit 1 }

Step 'Checking required tools'
foreach ($tool in 'git', 'uv', 'node', 'npm') {
    $cmd = Get-Command $tool -ErrorAction SilentlyContinue
    if (-not $cmd) { Fail "'$tool' not found. Install it (see docs/SETUP.md) and open a NEW terminal." }
    $version = (& $tool --version 2>$null | Select-Object -First 1)
    Write-Host ("  {0,-5} {1}" -f $tool, $version)
}

Step 'Backend: creating Python 3.13 environment and installing dependencies (uv sync)'
Push-Location (Join-Path $root 'backend')
try {
    uv sync
    if ($LASTEXITCODE -ne 0) { Fail 'uv sync failed' }
} finally { Pop-Location }

Step 'Frontend: installing Node dependencies (npm ci)'
Push-Location (Join-Path $root 'frontend')
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { Fail 'npm ci failed' }
} finally { Pop-Location }

if (-not (Test-Path (Join-Path $root '.env'))) {
    Copy-Item (Join-Path $root '.env.example') (Join-Path $root '.env')
    Write-Host "`nCreated .env from .env.example (defaults are fine)."
}

if ($Seed) {
    Step 'Downloading the curated set of real Perseverance data (NASA/JPL-Caltech)'
    Push-Location (Join-Path $root 'backend')
    try { uv run mars-ingest seed } finally { Pop-Location }
}

Write-Host "`nSetup complete." -ForegroundColor Green
if (-not $Seed) { Write-Host "Next: download data with  cd backend; uv run mars-ingest seed" }
Write-Host "Then start everything with  .\scripts\dev.ps1"
