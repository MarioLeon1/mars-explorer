<#
.SYNOPSIS
  Run every quality gate: backend lint + tests, frontend lint + type-check + tests + build.
  Exit code 0 only if everything passes.

.EXAMPLE
  .\scripts\check.ps1         # offline checks
  .\scripts\check.ps1 -Live   # also run the tests that hit the real NASA endpoints
  .\scripts\check.ps1 -E2E    # also run the browser end-to-end + accessibility tests
                              # (Microsoft Edge, isolated offline data, ports 8100/5180)
#>
param([switch]$Live, [switch]$E2E)

$root = Split-Path -Parent $PSScriptRoot
$failed = @()

function Run($name, $dir, [scriptblock]$block) {
    Write-Host "`n==> $name" -ForegroundColor Cyan
    Push-Location (Join-Path $root $dir)
    try {
        & $block
        if ($LASTEXITCODE -ne 0) { $script:failed += $name }
    } finally { Pop-Location }
}

Run 'backend: ruff lint'      'backend'  { uv run ruff check . }
Run 'backend: ruff format'    'backend'  { uv run ruff format --check . }
Run 'backend: pytest'         'backend'  { uv run pytest }
if ($Live) { Run 'backend: live NASA tests' 'backend' { uv run pytest -m live } }
Run 'frontend: lint'          'frontend' { npm run lint }
Run 'frontend: type-check'    'frontend' { npm run typecheck }
Run 'frontend: tests'         'frontend' { npm test }
Run 'frontend: build'         'frontend' { npm run build }
if ($E2E) { Run 'e2e: Playwright (Edge)' 'frontend' { npm run e2e } }

if ($failed.Count -gt 0) {
    Write-Host "`nFAILED: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "`nAll checks passed." -ForegroundColor Green
