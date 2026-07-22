@echo off
chcp 65001 >nul
cd /d "%~dp0"
title CRT Skaner
echo ============================================
echo   CRT SKANER ishga tushmoqda...
echo   (MT5 terminal ochiq bo'lsin!)
echo   To'xtatish: Ctrl+C yoki bu oynani yopish
echo ============================================
powershell -NoProfile -ExecutionPolicy Bypass -File "run_local.ps1"
echo.
echo Skaner to'xtadi. Yopish uchun istalgan tugmani bosing.
pause >nul
