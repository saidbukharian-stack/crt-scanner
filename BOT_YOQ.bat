@echo off
chcp 65001 >nul
cd /d "%~dp0"
title CRT Telegram Bot
echo ============================================
echo   TELEGRAM BOT ishga tushmoqda...
echo   /holat, /zanjir, /hisob, savol-javob
echo   To'xtatish: Ctrl+C yoki bu oynani yopish
echo ============================================
powershell -NoProfile -ExecutionPolicy Bypass -File "run_local_bot.ps1"
echo.
echo Bot to'xtadi. Yopish uchun istalgan tugmani bosing.
pause >nul
