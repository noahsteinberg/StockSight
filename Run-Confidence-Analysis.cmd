@echo off
setlocal
set "TASK_PYTHON=%TEMP%\stocksight-ml-round2-env\Scripts\python.exe"
if not exist "%TASK_PYTHON%" set "TASK_PYTHON=%~dp0ml\.venv\Scripts\python.exe"
if not exist "%TASK_PYTHON%" (
  echo The prepared Python environment is missing. Ask for setup help; nothing was run.
  pause
  exit /b 1
)
"%TASK_PYTHON%" -u "%~dp0ml\scripts\analyze-confidence.py" %*
set "TASK_RESULT=%ERRORLEVEL%"
echo.
if "%TASK_RESULT%"=="0" (
  echo Finished. If you ran the analysis, share data\confidence-analysis\summary.md and results.json.
) else (
  echo Stopped with an error. Share data\confidence-analysis\run.log if it exists.
)
pause
exit /b %TASK_RESULT%
