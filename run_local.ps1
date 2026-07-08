# CRT Scanner — LOKAL rejim (MT5 narx + TradingView grafik)
# ==========================================================
# Signal skaneri. Narx MT5 terminalidan, grafiklar TradingView'dan.
#
# Ishga tushirish:  .\run_local.ps1
# To'xtatish:       Ctrl+C
#
# TALAB:
#   1) MT5 terminal OCHIQ va hisobga ulangan bo'lsin
#   2) pip install -r requirements.txt
#   3) python -m playwright install chromium
#   4) docs\*tradingview*cookies*.txt (sizning layout uchun, ixtiyoriy)

$env:DATA_SOURCE = "mt5"            # narx MT5 terminalidan (spot, TV bilan mos)
$env:USE_TV_SCREENSHOT = "1"        # grafiklar TradingView'dan (sizning layout)
$env:SCAN_INTERVAL_MINUTES = "2"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "CRT Scanner — LOKAL rejim" -ForegroundColor Cyan
Write-Host "  Narx manbai   : MT5 terminal (ochiq bo'lsin!)"
Write-Host "  Grafik        : TradingView screenshot"
Write-Host "  Skan oralig'i : $env:SCAN_INTERVAL_MINUTES daqiqa"
Write-Host ""

python scanner.py
