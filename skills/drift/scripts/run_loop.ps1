# run_loop.ps1 — Drift full coverage feedback loop (Windows/PowerShell).
#
# Runs `drift verify --failed` repeatedly until all tests pass, then runs
# check_coverage.py to verify every operation and response code is covered.
# Exits with code 0 only when both gates pass.
#
# Usage:
#   .\run_loop.ps1 --spec openapi.yaml --test-files drift.yaml --server-url http://localhost:4010
#   .\run_loop.ps1 --spec openapi.yaml --test-files "tests/*.yaml" --server-url https://api.example.com
#
# Options:
#   --spec           Path to OpenAPI spec (required for coverage check)
#   --test-files     Drift test file(s) or glob pattern (required)
#   --server-url     URL of the API under test (required)
#   --max-rounds     Max number of drift verify retries (default: 20)
#   --full           Run full suite each round instead of --failed only
#   --skip-coverage  Skip the coverage check at the end (just get tests passing)
#
# Environment:
#   Any env vars drift verify needs (API_TOKEN, etc.) must be set before running.
#   e.g. $env:API_TOKEN = "your-token"

param(
    [string]$spec = "",
    [string]$testFiles = "",
    [string]$serverUrl = "",
    [int]$maxRounds = 20,
    [switch]$full,
    [switch]$skipCoverage
)

# Support --kebab-case aliases passed as raw args
foreach ($arg in $args) {
    switch -Regex ($arg) {
        "^--spec$"           { $spec       = $args[$args.IndexOf($arg) + 1] }
        "^--test-files$"     { $testFiles  = $args[$args.IndexOf($arg) + 1] }
        "^--server-url$"     { $serverUrl  = $args[$args.IndexOf($arg) + 1] }
        "^--max-rounds$"     { $maxRounds  = [int]$args[$args.IndexOf($arg) + 1] }
        "^--full$"           { $full       = $true }
        "^--skip-coverage$"  { $skipCoverage = $true }
    }
}

if (-not $testFiles -or -not $serverUrl) {
    Write-Error "Usage: .\run_loop.ps1 --spec openapi.yaml --test-files drift.yaml --server-url http://localhost:4010"
    exit 1
}

$useFailedFlag = if ($full) { "" } else { "--failed" }

# ── Locate check_coverage.py ──────────────────────────────────────────────────
$scriptDir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$coverageScript = Join-Path $scriptDir "check_coverage.py"

# ── Run drift in a loop ───────────────────────────────────────────────────────
Write-Host ("=" * 60)
Write-Host "  Drift Coverage Feedback Loop"
Write-Host "  Test files:  $testFiles"
Write-Host "  Server URL:  $serverUrl"
Write-Host "  Max rounds:  $maxRounds"
Write-Host ("=" * 60)
Write-Host ""

# First run — always full (no --failed on round 1)
Write-Host "-- Round 1 / $maxRounds -- full run --"
drift verify --test-files $testFiles --server-url $serverUrl
$driftPassed = ($LASTEXITCODE -eq 0)

if ($driftPassed) {
    Write-Host "`nAll tests passed on first run."
} else {
    $round = 2
    while ($round -le $maxRounds) {
        Write-Host "`n-- Round $round / $maxRounds --"
        if ($useFailedFlag) {
            drift verify --test-files $testFiles --server-url $serverUrl $useFailedFlag
        } else {
            drift verify --test-files $testFiles --server-url $serverUrl
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Host "`nAll tests passed (round $round)."
            $driftPassed = $true
            break
        }
        $round++
    }
}

if (-not $driftPassed) {
    Write-Host "`nTests still failing after $maxRounds rounds. Fix the remaining failures manually."
    exit 1
}

# ── Coverage check ────────────────────────────────────────────────────────────
if ($skipCoverage) {
    Write-Host "`nCoverage check skipped (--skip-coverage)."
    exit 0
}

if (-not $spec) {
    Write-Host "`nNote: --spec not provided, skipping coverage check."
    Write-Host "To verify full coverage run:"
    Write-Host "  uv run $coverageScript --spec openapi.yaml --test-files $testFiles"
    exit 0
}

Write-Host ""
Write-Host ("=" * 60)
Write-Host "  Coverage Check"
Write-Host ("=" * 60)

& uv run $coverageScript --spec $spec --test-files $testFiles
if ($LASTEXITCODE -eq 0) {
    Write-Host "`nComplete: all tests pass AND full coverage verified."
    exit 0
} else {
    Write-Host "`nTests pass but coverage is incomplete. Add tests for the missing operations/codes above."
    exit 1
}
