@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Skaner va bot to'xtatilmoqda ===
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop_bot.ps1"
echo.
echo === Yakuniy holat ===
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\status.ps1"
echo.
pause
