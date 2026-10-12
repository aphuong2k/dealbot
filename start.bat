@echo off
chcp 65001 >nul
title Dealbot Studio Launcher

echo ======================================================================
echo           KHOI DONG HE THONG DEALBOT STUDIO (BE + FE)
echo ======================================================================
echo.

echo [1/3] Dang khoi dong Backend FastAPI (Port 8000)...
cd /d "%~dp0dealbot"
start "Dealbot Backend API" cmd /k python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload

echo [2/3] Dang khoi dong Frontend Angular (Port 4200)...
cd /d "%~dp0dealbot-ui"
start "Dealbot Frontend UI" cmd /k npm start

cd /d "%~dp0"

echo.
echo [3/3] Dang cho he thong san sang de mo trinh duyet...
ping 127.0.0.1 -n 6 >nul
start http://localhost:4200

echo.
echo ======================================================================
echo  He thong da duoc khoi chay thanh cong!
echo  - Frontend UI : http://localhost:4200
echo  - Backend API : http://127.0.0.1:8000
echo  - Swagger API : http://127.0.0.1:8000/docs
echo ======================================================================
echo.
pause
