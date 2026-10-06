# PowerShell Launcher cho Dealbot Studio
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "           🚀 KHỞI ĐỘNG HỆ THỐNG DEALBOT STUDIO (BE + FE)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$CurrentDir = $PSScriptRoot
$BeDir = Join-Path $CurrentDir "dealbot"
$FeDir = Join-Path $CurrentDir "dealbot-ui"

Write-Host "[1/3] Đang khởi động Backend FastAPI (Port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$BeDir'; python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload"

Write-Host "[2/3] Đang khởi động Frontend Angular (Port 4200)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$FeDir'; npm start"

Write-Host ""
Write-Host "[3/3] Đang chờ và tự động mở trình duyệt..." -ForegroundColor Green
Start-Sleep -Seconds 5
Start-Process "http://localhost:4200"

Write-Host ""
Write-Host "✅ Đã mở 2 tiến trình độc lập và khởi chạy trình duyệt tại http://localhost:4200" -ForegroundColor Green
