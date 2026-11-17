param(
    [ValidateSet("Prepare", "Pilot", "Full", "Report")]
    [string]$Stage = "Full",
    [string]$PythonPath = (Join-Path $env:TEMP "stocksight-ml-round2-env\Scripts\python.exe")
)

$ErrorActionPreference = "Stop"
$worktreeRoot = $PSScriptRoot
$courseRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $worktreeRoot))
$researchRoot = Join-Path $courseRoot "StockSight-ml-research"
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Prepared Python missing at $PythonPath. Use -PythonPath with the existing ML environment."
}
$env:STOCKSIGHT_DATA_DIR = Join-Path $researchRoot "data"
$env:STOCKSIGHT_PRIOR_NEXT_DIR = Join-Path $researchRoot "data\next-session"
$env:STOCKSIGHT_TARGET_DIR = Join-Path $worktreeRoot "data\next-session-target-round"
$script = Join-Path $worktreeRoot "ml\scripts\next-session-target-round.py"
New-Item -ItemType Directory -Path $env:STOCKSIGHT_TARGET_DIR -Force | Out-Null
$logPath = Join-Path $env:STOCKSIGHT_TARGET_DIR "run.log"

function Invoke-TargetStage([string[]]$StageArguments) {
    & $PythonPath -u $script @StageArguments 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) { throw "Target round failed ($LASTEXITCODE). See $logPath" }
}

switch ($Stage) {
    "Prepare" { Invoke-TargetStage @("prepare") }
    "Pilot" {
        Invoke-TargetStage @("prepare")
        Invoke-TargetStage @("run", "--pilot")
        Invoke-TargetStage @("report", "--pilot")
    }
    "Full" {
        Invoke-TargetStage @("prepare")
        Invoke-TargetStage @("run")
        Invoke-TargetStage @("report")
    }
    "Report" { Invoke-TargetStage @("report") }
}
