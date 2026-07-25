@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === Архив ленты Sports.ru ===
echo.

where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    set "PY=python"
  ) else (
    echo Python не найден.
    echo Скачайте и установите Python 3 с https://www.python.org/downloads/
    echo При установке отметьте галочку "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
  )
)

echo Устанавливаю зависимости...
%PY% -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo Не удалось установить зависимости.
  pause
  exit /b 1
)

echo.
echo Запускаю сайт...
echo Откройте в браузере: http://127.0.0.1:5000/
echo Чтобы остановить — закройте это окно или нажмите Ctrl+C.
echo.

start "" "http://127.0.0.1:5000/"
%PY% app.py

pause
