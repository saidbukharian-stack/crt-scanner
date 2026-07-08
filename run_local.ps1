# CRT Scanner — LOKAL rejim (TradingView screenshot bilan)
# ==========================================================
# Bulutdagi tizim (matplotlib grafik) o'z-o'zicha ishlab turadi.
# Bu skript LOKAL kompyuterda ishlaydi va grafiklarni TradingView'dan oladi.
#
# Ishga tushirish:  .\run_local.ps1
# To'xtatish:       Ctrl+C
#
# Talab: pip install -r requirements.txt + python -m playwright install chromium

$env:DATA_SOURCE = "yahoo"          # narx manbai (mt5 = RoboForex, terminal ochiq bo'lsin)
$env:USE_TV_SCREENSHOT = "1"        # grafiklar TradingView'dan
$env:SCAN_INTERVAL_MINUTES = "2"
$env:PYTHONIOENCODING = "utf-8"

# .env fayldan token/kalitlar o'qiladi (config.py avtomatik yuklaydi)

Write-Host "CRT Scanner LOKAL rejim" -ForegroundColor Cyan
Write-Host "  Narx manbai      : $env:DATA_SOURCE"
Write-Host "  Grafik           : TradingView screenshot (lokal brauzer)"
Write-Host "  Skan oralig'i    : $env:SCAN_INTERVAL_MINUTES daqiqa"
Write-Host ""
Write-Host "MUHIM: bulutdagi skaner ham ishlab turibdi - ikki xil signal kelishi mumkin." -ForegroundColor Yellow
Write-Host "Faqat lokalni xohlasangiz, bulutdagi scan.yml workflow'ni to'xtating." -ForegroundColor Yellow
Write-Host ""

python scanner.py
