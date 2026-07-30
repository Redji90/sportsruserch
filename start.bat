@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === Архив ленты Sports.ru ===
echo.

call :find_python
if defined PY goto :run

echo Python не найден. Пробую установить автоматически...
echo.

call :install_python
call :refresh_path
call :find_python
if defined PY goto :run

echo.
echo Не удалось установить Python автоматически.
echo Установите вручную с https://www.python.org/downloads/
echo и отметьте галочку "Add python.exe to PATH".
echo.
pause
exit /b 1

:run
echo Использую: %PY%
echo Устанавливаю зависимости...
%PY% -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo Не удалось установить зависимости.
  pause
  exit /b 1
)

echo.
echo Запускаю сайт...
echo.
echo   На этом компьютере:  http://127.0.0.1:5000/
call :print_lan_url
echo.
echo   Телефон и ПК — в одной Wi-Fi сети.
echo   Если не открывается с телефона, разрешите порт 5000 в брандмауэре Windows.
echo   Чтобы остановить — закройте это окно или нажмите Ctrl+C.
echo.

start "" "http://127.0.0.1:5000/"
%PY% app.py

pause
exit /b 0

:print_lan_url
set "LAN_IP="
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /c:"IPv4"') do (
  for /f "tokens=* delims= " %%B in ("%%A") do (
    echo %%B | findstr /r "^192\.168\." >nul
    if not errorlevel 1 set "LAN_IP=%%B"
    if not defined LAN_IP (
      echo %%B | findstr /r "^10\." >nul
      if not errorlevel 1 set "LAN_IP=%%B"
    )
    if not defined LAN_IP (
      echo %%B | findstr /r "^172\.1[6-9]\." >nul
      if not errorlevel 1 set "LAN_IP=%%B"
      echo %%B | findstr /r "^172\.2[0-9]\." >nul
      if not errorlevel 1 set "LAN_IP=%%B"
      echo %%B | findstr /r "^172\.3[0-1]\." >nul
      if not errorlevel 1 set "LAN_IP=%%B"
    )
  )
)
if defined LAN_IP (
  echo   С телефона/планшета: http://!LAN_IP!:5000/
) else (
  echo   С телефона/планшета: узнайте IPv4 ПК через ipconfig и откройте http://IP:5000/
)
exit /b 0

:find_python
set "PY="
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import sys" >nul 2>&1
  if not errorlevel 1 (
    set "PY=py -3"
    exit /b 0
  )
)
where python >nul 2>&1
if not errorlevel 1 (
  python -c "import sys" >nul 2>&1
  if not errorlevel 1 (
    set "PY=python"
    exit /b 0
  )
)
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
  exit /b 0
)
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
  set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
  exit /b 0
)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
  set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
  exit /b 0
)
exit /b 1

:install_python
where winget >nul 2>&1
if not errorlevel 1 (
  echo Способ 1/2: установка через winget...
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  if not errorlevel 1 (
    echo Python установлен через winget.
    exit /b 0
  )
  echo winget не смог установить Python, пробую скачать установщик...
)

echo Способ 2/2: скачиваю установщик Python 3.12...
set "INSTALLER=%TEMP%\python-3.12-amd64.exe"
set "PY_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"

where curl >nul 2>&1
if not errorlevel 1 (
  curl.exe -L --fail -o "%INSTALLER%" "%PY_URL%"
) else (
  powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%INSTALLER%' -UseBasicParsing } catch { exit 1 }"
)
if errorlevel 1 (
  echo Не удалось скачать установщик Python.
  exit /b 1
)
if not exist "%INSTALLER%" (
  echo Файл установщика не найден после скачивания.
  exit /b 1
)

echo Запускаю установку Python (тихий режим, с добавлением в PATH)...
"%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1
if errorlevel 1 (
  echo Установщик Python завершился с ошибкой.
  exit /b 1
)
echo Python установлен.
exit /b 0

:refresh_path
REM Обновляем PATH в текущем окне после установки
for /f "usebackq tokens=2*" %%A in (`reg query "HKCU\Environment" /v Path 2^>nul`) do set "USER_PATH=%%B"
for /f "usebackq tokens=2*" %%A in (`reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul`) do set "SYS_PATH=%%B"
if defined USER_PATH if defined SYS_PATH set "PATH=%SYS_PATH%;%USER_PATH%"
exit /b 0
