@echo off
echo.
echo  Starting LiverSeg...
echo.

start "LiverSeg Backend" cmd /k "conda activate liver2 && cd /d %~dp0backend && uvicorn main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 600"

timeout /t 6 /nobreak >nul

start "LiverSeg Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 5 /nobreak >nul
start http://localhost:5173

echo  App running at http://localhost:5173
echo  API status:   http://localhost:8000/health
echo  Fold status:  http://localhost:8000/model/info
