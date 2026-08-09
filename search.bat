@echo off
rem ============================================================
rem  JobHunt OS - automated job search (Command Prompt edition)
rem  Batch-builds a tailored bundle for EVERY job in your
rem  shortlist (data\jobs.csv or samples\jobs.csv), then shows
rem  the application ledger. Double-click or run in cmd.
rem ============================================================
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo Python not found on PATH.
  echo Install it from https://www.python.org/downloads/  - tick "Add to PATH".
  pause
  exit /b 1
)

python -c "import jobhunt" 2>nul
if errorlevel 1 (
  echo First run: installing jobhunt-os...
  python -m pip install --quiet -e .
  if errorlevel 1 (
    echo Install failed - see the error above.
    pause
    exit /b 1
  )
)

echo.
echo ===== jobhunt: automated job search =====
echo Building a tailored bundle for every shortlisted job...
echo.
python -m jobhunt demo --limit 999
if errorlevel 1 (
  echo.
  echo Something failed. Run:  python -m jobhunt doctor
  pause
  exit /b 1
)

echo.
echo ===== pipeline ledger =====
python -m jobhunt track list
echo.
echo Done. Tailored resumes are in:  data\applications\
echo For the visual workspace run  start.bat  (or: python -m jobhunt serve)
pause