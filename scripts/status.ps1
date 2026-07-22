# Skaner va MT5 holatini ko'rsatadi
$s = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
     Where-Object { $_.CommandLine -like '*scanner.py*' }
if ($s) {
    Write-Host "SKANER: ishlayapti (PID $($s.ProcessId))" -ForegroundColor Green
} else {
    Write-Host "SKANER: o'chiq" -ForegroundColor Yellow
}

$b = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
     Where-Object { $_.CommandLine -like '*telegram_bot.py*' }
if ($b) {
    Write-Host "BOT: ishlayapti (PID $($b.ProcessId))" -ForegroundColor Green
} else {
    Write-Host "BOT: o'chiq" -ForegroundColor Yellow
}

$m = Get-Process terminal64 -ErrorAction SilentlyContinue
if ($m) {
    Write-Host "MT5: ochiq" -ForegroundColor Green
} else {
    Write-Host "MT5: YOPIQ - avval oching!" -ForegroundColor Red
}
