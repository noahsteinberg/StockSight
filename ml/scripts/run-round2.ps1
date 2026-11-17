param(
    [string]$Python = (Join-Path $PSScriptRoot '../.venv/Scripts/python.exe'),
    [ValidateSet('baseline', 'experiments', 'report')][string]$Stage = 'baseline',
    [int]$Threads = 4
)

$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    # Each model fold checkpoints to data/research_round2. Repeating this command resumes.
    if ($Stage -eq 'baseline') {
        & $Python -u -m stocksight_data.research_round2 prepare
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $Python -u -m stocksight_data.research_round2 audit
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $Python -u -m stocksight_data.research_round2 run --only hgb_raw_wide_bal --threads $Threads
    } elseif ($Stage -eq 'experiments') {
        & $Python -u -m stocksight_data.research_round2 run --threads $Threads
    } else {
        & $Python -u -m stocksight_data.research_round2 report
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
