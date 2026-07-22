# Ishlayotgan skaner (va botni) to'xtatadi
$found = $false
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*scanner.py*' } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
        Write-Host "Skaner to'xtatildi (PID $($_.ProcessId))" -ForegroundColor Green
        $found = $true
    }
if (-not $found) {
    Write-Host "Skaner allaqachon o'chiq" -ForegroundColor Yellow
}
