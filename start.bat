@echo off
chcp 65001 >nul
title Khởi Động Dealbot Studio

echo ======================================================================
echo           🚀 KHỞI ĐỘNG HỆ THỐNG DEALBOT STUDIO (BE + FE)
echo ======================================================================
echo.
echo [1/3] Đang khởi động Backend FastAPI (Port 8000)...
start "Dealbot Backend API (Port 8000)" cmd /k "cd /d %~dp0dealbot && python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload"

echo [2/3] Đang khởi động Frontend Angular (Port 4200)...
start "Dealbot Frontend UI (Port 4200)" cmd /k "cd /d %~dp0dealbot-ui && npm start"

echo.
echo [3/3] Đang chờ dịch vụ sẵn sàng và tự động mở trình duyệt...
timeout /t 6 >nul
start http://localhost:4200

echo.
echo ======================================================================
echo  ✅ Hệ thống đã được khởi chạy thành công!
echo  - Frontend UI : http://localhost:4200
echo  - Backend API : http://127.0.0.1:8000
echo  - Swagger API : http://127.0.0.1:8000/docs
echo ======================================================================
echo.
pause
