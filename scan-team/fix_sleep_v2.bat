@echo off
chcp 65001 >nul
title ScanTeam - stop sleeping v2 (lid close fix)
echo.
echo ==================================================
echo   ScanTeam v2 : fix lid-close sleep + re-verify
echo ==================================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo [!] Need Administrator.
  echo     Right-click this file  ^>  Run as administrator
  echo.
  pause
  exit /b 1
)

echo [1/4] What woke it / what is keeping it awake right now
echo --------------------------------------------------
powercfg /lastwake
echo.
powercfg /requests
echo.

echo [2/4] Re-applying: never sleep while plugged in
echo --------------------------------------------------
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change disk-timeout-ac 0
powercfg /change monitor-timeout-ac 20

echo [3/4] NEW: closing the lid does NOTHING while plugged in
echo --------------------------------------------------
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT
echo   lid-close action (AC power) = Do nothing
echo.
echo   NOTE: this only applies while the charger is plugged in.
echo   If it runs on battery even briefly, the lid-close action
echo   on BATTERY still applies (Windows default = Sleep).
echo   -> Keep the charger connected AND the lid open, to be safe.
echo.

echo [4/4] Verify current settings
echo --------------------------------------------------
powercfg /query SCHEME_CURRENT SUB_BUTTONS LIDACTION
echo.
powercfg /query SCHEME_CURRENT SUB_SLEEP | findstr /i "Index Setting"
echo.
echo Done. Keep charger plugged in AND keep the lid open.
echo Check again in a few hours: the gap in _watch.log should be gone.
echo.
pause
