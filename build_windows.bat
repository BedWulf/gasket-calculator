@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)
%PY% -m pip install --upgrade pip
if errorlevel 1 goto failed
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto failed
%PY% -m unittest discover -s tests -v
if errorlevel 1 goto failed
%PY% -m PyInstaller --noconfirm --clean gasket.spec
if errorlevel 1 goto failed
echo.
echo EXE: dist\GasketCalculator.exe
echo Проверьте на другом компьютере Windows перед применением в производстве.
pause
exit /b 0
:failed
echo Ошибка сборки или проверки. Посмотрите сообщения выше.
pause
exit /b 1
