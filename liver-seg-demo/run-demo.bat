@echo off
echo Starting LiverSeg Demo...

cd /d "%~dp0"

echo Starting backend...
start cmd /k "cd /d %~dp0backend && call venv\Scripts\activate && python demo_server.py"

timeout /t 2 > nul

echo Starting frontend...
start cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Demo running:
echo http://localhost:5174/demo

pause