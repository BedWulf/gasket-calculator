@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 goto :failed

echo === GasketCalculator Windows build ===
if not exist "main.py" goto :missing_files
if not exist "requirements.txt" goto :missing_files
if not exist "gasket.spec" goto :missing_files

set "BOOTSTRAP=py -3"
where py >nul 2>&1
if errorlevel 1 goto :try_python
py -3 --version >nul 2>&1
if errorlevel 1 goto :try_python
goto :python_found

:try_python
set "BOOTSTRAP=python"
where python >nul 2>&1
if errorlevel 1 goto :no_python
python --version >nul 2>&1
if errorlevel 1 goto :no_python

:python_found
echo [1/4] Creating Python environment...
if not exist ".venv\Scripts\python.exe" (
    %BOOTSTRAP% -m venv ".venv"
    if errorlevel 1 goto :failed
)
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" goto :failed

echo [2/4] Installing build requirements...
"%PYTHON_EXE%" -m pip install -r "requirements.txt" pyinstaller pillow
if errorlevel 1 goto :failed

echo [3/4] Running tests...
"%PYTHON_EXE%" -m unittest discover -s tests -v
if errorlevel 1 goto :failed

echo [4/4] Building GasketCalculator.exe...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean "gasket.spec"
if errorlevel 1 goto :failed
if not exist "dist\GasketCalculator.exe" goto :failed

echo.
echo SUCCESS: "dist\GasketCalculator.exe"
echo Test the executable on Windows before production use.
pause
exit /b 0

:missing_files
echo ERROR: Project files are missing. Extract the entire ZIP first.
pause
exit /b 1

:no_python
echo ERROR: Python 3 is not installed or is not available in PATH.
echo Install Python 3.10 or newer, then run this file again.
pause
exit /b 1

:failed
echo.
echo ERROR: Build failed. Read the error messages above.
pause
exit /b 1
