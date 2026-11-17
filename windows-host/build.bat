@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo   USB Pen Display - Windows Host Builder
echo ==========================================
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher not found.
  echo Install Python 3.11+ from https://www.python.org/downloads/windows/
  echo Enable "Add Python to PATH" during installation.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated Python environment...
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name USBPenDisplayHost main.py
if errorlevel 1 goto :error
echo SUCCESS: dist\USBPenDisplayHost.exe
pause
exit /b 0
:error
echo BUILD FAILED. Read the error above.
pause
exit /b 1
