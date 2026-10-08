@echo off
cd /d "%~dp0"

echo Starting LiverSeg Demo (portable)...

echo Setting up backend...
cd backend

if not exist venv (
    python -m venv venv
)

call venv\Scripts\activate
pip install -r requirements.txt > nul

echo Starting backend...
start cmd /k "cd /d %~dp0backend && call venv\Scripts\activate && python demo_server.py"

cd ..

echo Setting up frontend...
cd frontend

if not exist node_modules (
    npm install
)

echo Starting frontend...
start cmd /k "cd /d %~dp0frontend && npm run dev"

cd ..

echo.
echo Demo running at:
echo http://localhost:5174/demo
pause