@echo off
chcp 65001 >nul
if exist "F:\python.exe" (
  "F:\python.exe" -B "%~dp0cli.py" %*
) else (
  python -B "%~dp0cli.py" %*
)
exit /b %errorlevel%
