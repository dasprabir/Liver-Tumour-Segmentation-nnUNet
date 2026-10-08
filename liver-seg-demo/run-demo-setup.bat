@echo off
echo ===============================
echo LiverSeg Demo Setup
echo ===============================

cd /d "%~dp0"

echo Creating Python virtual environment...
cd backend

if exist venv (
    echo venv already exists
) else (
    py -3 -m venv venv
)

call venv\Scripts\activate

echo Installing backend requirements...
pip install --upgrade pip
pip install -r requirements.txt

echo Backend setup complete.

cd ..

echo Installing frontend dependencies...
cd frontend

npm install

cd ..

echo ===============================
echo Setup Complete
echo ===============================
pause