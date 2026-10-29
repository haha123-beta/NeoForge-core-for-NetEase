@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "F:\pythonw.exe" (
  start "" "F:\pythonw.exe" -B "%~dp0app.py"
  exit /b
)
where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw -B "%~dp0app.py"
  exit /b
)
echo 需要 Python 3.11 或更新版本。当前工具使用本机 Python，尚未打包为独立 EXE。
pause
