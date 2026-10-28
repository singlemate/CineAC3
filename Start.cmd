@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if not errorlevel 1 (
  start "" pyw -3 "%~dp0converter.py"
  exit /b
)
where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw "%~dp0converter.py"
  exit /b
)
echo Install Python 3.11 or newer with Tcl/Tk from https://www.python.org/downloads/windows/
pause
