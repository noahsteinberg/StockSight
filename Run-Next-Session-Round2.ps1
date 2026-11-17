param(
    [ValidateSet("Prepare", "Pilot", "Full", "Report")]
    [string]$Stage = "Full"
)

$ErrorActionPreference = "Stop"
$worktreeRoot = $PSScriptRoot
$courseRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $worktreeRoot))
$researchRoot = Join-Path $courseRoot "StockSight-ml-research"
$python = Join-Path $env:TEMP "stocksight-ml-round2-env\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Prepared Python environment not found at $python"
}
if (-not (Test-Path -LiteralPath (Join-Path $researchRoot "data\clean\prices_clean.parquet"))) {
    throw "Frozen research data not found under $researchRoot"
}

$env:STOCKSIGHT_DATA_DIR = Join-Path $researchRoot "data"
$env:STOCKSIGHT_PRIOR_NEXT_DIR = Join-Path $researchRoot "data\next-session"
$env:STOCKSIGHT_EXPERIMENT_DIR = Join-Path $worktreeRoot "data\next-session-round2"
$script = Join-Path $worktreeRoot "ml\scripts\next-session-round2.py"

switch ($Stage) {
    "Prepare" { & $python -u $script prepare }
    "Pilot" { & $python -u $script run --pilot }
    "Full" {
        & $python -u $script run
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $python -u $script report
    }
    "Report" { & $python -u $script report }
}

exit $LASTEXITCODE
