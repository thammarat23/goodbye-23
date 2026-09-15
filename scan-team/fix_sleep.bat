@echo off
chcp 65001 >nul
title ScanTeam - stop the PC sleeping at night
echo.
echo ================================================
echo   ScanTeam : keep this PC awake while scanning
echo ================================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo [!] Need Administrator.
  echo     Right-click this file  ^>  Run as administrator
  echo.
  pause
  exit /b 1
)

echo [1/3] Why did it wake / what keeps it awake now
echo ------------------------------------------------
powercfg /lastwake
echo.
powercfg /requests
echo.

echo [2/3] Applying: never sleep while plugged in
echo ------------------------------------------------
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change disk-timeout-ac 0
powercfg /change monitor-timeout-ac 20
echo   standby-timeout-ac   = 0   (never sleep)
echo   hibernate-timeout-ac = 0   (never hibernate)
echo   disk-timeout-ac      = 0   (disk never parks)
echo   monitor-timeout-ac   = 20  (screen off after 20 min - this is fine)
echo.

echo [3/3] Verify
echo ------------------------------------------------
powercfg /query SCHEME_CURRENT SUB_SLEEP | findstr /i "Index Setting"
echo.
echo Done. Leave the PC plugged in.
echo Check tomorrow morning: the gap in _watch.log should be gone.
echo.
pause
