@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0local_env.cmd" call "%~dp0local_env.cmd"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -B "%~dp0run_neocore.py" gui %*
) else (
  python -B "%~dp0run_neocore.py" gui %*
)
