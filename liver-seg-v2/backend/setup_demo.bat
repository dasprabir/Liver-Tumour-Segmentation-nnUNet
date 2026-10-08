@echo off
echo.
echo ===== LiverSeg Demo Setup =====
echo.

cd /d %~dp0

:: detect python
where python >nul 2>nul
if %errorlevel%==0 (
    set PY=python
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set PY=py
    ) else (
        echo Python not found. Install Python 3.9+
        pause
        exit /b
    )
)

echo Using %PY%

%PY% -m venv venv-demo

call venv-demo\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements-demo.txt

echo.
echo Demo setup complete
pause