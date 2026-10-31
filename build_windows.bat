@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 goto :failed

echo === GasketCalculator Windows build ===
if not exist "main.py" goto :missing_files
if not exist "requirements.txt" goto :missing_files
if not exist "gasket.spec" goto :missing_files

rem Use a short venv path outside the extracted ZIP directory.
rem PyQt6 contains deeply nested folders that can exceed MAX_PATH in Downloads.
if not defined LOCALAPPDATA goto :no_localappdata
set "BUILD_HOME=%LOCALAPPDATA%\GasketCalculator"
set "VENV_DIR=%BUILD_HOME%\build-venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

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
echo Python packages will be installed in:
echo "%VENV_DIR%"
if exist ".venv\Scripts\python.exe" (
    echo Note: The old project .venv will not be used.
)
echo.
echo [1/4] Preparing short-path Python environment...
if not exist "%PYTHON_EXE%" (
    %BOOTSTRAP% -m venv "%VENV_DIR%"
    if errorlevel 1 goto :failed
)
if not exist "%PYTHON_EXE%" goto :failed

echo [2/4] Installing required packages...
"%PYTHON_EXE%" -m pip install -r "requirements.txt" pyinstaller pillow
if errorlevel 1 goto :failed

echo [3/4] Running unit tests...
"%PYTHON_EXE%" -m unittest discover -s tests -v
if errorlevel 1 goto :failed

echo [4/4] Building GasketCalculator.exe...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --workpath "%BUILD_HOME%\pyinstaller-work" "gasket.spec"
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

:no_localappdata
echo ERROR: LOCALAPPDATA is not defined in this Windows session.
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
