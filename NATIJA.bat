@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo === Natijalar tahlili ===
python analyze_results.py
echo.
echo Hisobot: results\report.md
pause
