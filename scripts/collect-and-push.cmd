@echo off
REM Daily token-history collection for Windows (Task Scheduler entry point).
REM Snapshots local AI-CLI usage via ccusage into data/<host>/<date>.json and
REM pushes to the fork; GitHub Actions then regenerates the charts on push.
REM Mirrors the repo's macOS launchd job (scripts/install-launchd.sh).
setlocal
set "REPO=C:\Infra\token-history"
set "PY=%REPO%\.venv\Scripts\python.exe"
REM Task Scheduler starts with a minimal PATH: add node (for npx/ccusage) and
REM the repo venv explicitly.
set "PATH=C:\Program Files\nodejs;%REPO%\.venv\Scripts;%PATH%"
set "GIT_TERMINAL_PROMPT=0"

cd /d "%REPO%" || exit /b 1
echo. >> "%REPO%\collect.log"
echo ==== %DATE% %TIME% ==== >> "%REPO%\collect.log"
"%PY%" scripts\collect.py >> "%REPO%\collect.log" 2>&1
exit /b %ERRORLEVEL%
