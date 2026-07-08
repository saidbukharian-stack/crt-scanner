# CRT Bot (savol-javob + /holat) — LOKAL rejim
# =============================================
# Telegram botga savol yozasiz, /holat so'raysiz.
# Narx MT5'dan, grafik TradingView'dan.
#
# Ishga tushirish:  .\run_local_bot.ps1
# To'xtatish:       Ctrl+C
#
# TALAB: MT5 terminal ochiq + playwright chromium o'rnatilgan

$env:DATA_SOURCE = "mt5"
$env:USE_TV_SCREENSHOT = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "CRT Bot — LOKAL rejim (long-polling)" -ForegroundColor Cyan
Write-Host "  Narx: MT5  |  Grafik: TradingView"
Write-Host "  Telegram'ga savol yozing yoki /holat XAUUSD"
Write-Host ""

python telegram_bot.py --serve
