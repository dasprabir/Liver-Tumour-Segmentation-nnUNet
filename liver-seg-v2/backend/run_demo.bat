@echo off
echo.
echo ===== LiverSeg Demo Mode =====
echo.

cd /d %~dp0

if not exist venv-demo\Scripts\activate.bat (
    echo Demo environment missing.
    echo Run setup_demo.bat first.
    pause
    exit /b
)

echo Starting backend...

start "Demo Backend" cmd /k ^
"cd /d %~dp0 && ^
call venv-demo\Scripts\activate && ^
python -m uvicorn main:app --host 127.0.0.1 --port 8000"

timeout /t 3 >nul

echo Starting frontend...

start "Frontend" cmd /k ^
"cd /d %~dp0..\frontend && npm run dev"

timeout /t 5 >nul

start http://localhost:5173