# Telegram botni to'xtatadi
$found = $false
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*telegram_bot.py*' } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
        Write-Host "Bot to'xtatildi (PID $($_.ProcessId))" -ForegroundColor Green
        $found = $true
    }
if (-not $found) {
    Write-Host "Bot allaqachon o'chiq" -ForegroundColor Yellow
}
