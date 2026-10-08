@echo off
REM ================================================================
REM  setup_full.bat
REM  Run this ONCE on any new machine to install all dependencies.
REM  No Conda or Anaconda required.
REM
REM  Before running this script, install these two things manually:
REM
REM  1. Python 3.11
REM     https://www.python.org/downloads/release/python-3119/
REM     On the installer's first screen, TICK "Add Python to PATH"
REM
REM  2. Node.js LTS
REM     https://nodejs.org
REM     Click through with all default settings
REM
REM  Everything else is handled automatically by this script.
REM ================================================================

setlocal EnableDelayedExpansion
echo.
echo  ================================================================
echo   Liver Tumour Segmentation -- One-Time Setup
echo   Estimated time: 15-25 minutes (mostly downloading PyTorch)
echo  ================================================================
echo.

REM -- Verify we are in the right folder --
if not exist "%~dp0backend\config.py" (
    echo  ERROR: This script must be run from the liver-seg folder.
    echo         Please double-click setup_full.bat from inside liver-seg.
    pause
    exit /b 1
)

REM ================================================================
REM  STEP 1 of 6 -- Check Python
REM ================================================================
echo  [Step 1 of 6]  Checking Python...
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python was not found.
    echo.
    echo  Please install Python 3.11 from:
    echo    https://www.python.org/downloads/release/python-3119/
    echo.
    echo  On the first screen of the installer, look for a checkbox
    echo  at the bottom that says:
    echo    "Add Python.exe to PATH"
    echo  Make sure it is TICKED before you click Install Now.
    echo.
    echo  After installing Python, close this window and
    echo  double-click setup_full.bat again.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Python !PYVER! found.
echo.

REM ================================================================
REM  STEP 2 of 6 -- Check Node.js
REM ================================================================
echo  [Step 2 of 6]  Checking Node.js...
echo.
node --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Node.js was not found.
    echo.
    echo  Please install Node.js from:
    echo    https://nodejs.org
    echo.
    echo  Click the large green "LTS" button to download.
    echo  Run the installer with all default settings.
    echo.
    echo  After installing Node.js, close this window and
    echo  double-click setup_full.bat again.
    pause
    exit /b 1
)
for /f %%v in ('node --version') do set NODEVER=%%v
echo  Node.js !NODEVER! found.
echo.

REM ================================================================
REM  STEP 3 of 6 -- Create Python virtual environment
REM ================================================================
echo  [Step 3 of 6]  Creating Python virtual environment...
echo.
if exist "%~dp0venv\Scripts\activate.bat" (
    echo  Virtual environment already exists. Skipping.
) else (
    python -m venv "%~dp0venv"
    if errorlevel 1 (
        echo  ERROR: Could not create virtual environment.
        echo  Make sure Python 3.11 is correctly installed with PATH enabled.
        pause
        exit /b 1
    )
    echo  Virtual environment created at: %~dp0venv
)
call "%~dp0venv\Scripts\activate.bat"
echo  Virtual environment activated.
echo.

REM ================================================================
REM  STEP 4 of 6 -- Install PyTorch with CUDA
REM ================================================================
echo  [Step 4 of 6]  Installing PyTorch...
echo.
echo  This downloads ~2.5 GB. It will take 10-15 minutes.
echo  Do not close this window.
echo.
python -c "import torch" >nul 2>&1
if not errorlevel 1 (
    echo  PyTorch is already installed. Skipping.
) else (
    echo  Trying GPU version (CUDA 12.1)...
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
    if errorlevel 1 (
        echo.
        echo  GPU version failed. Installing CPU-only version...
        echo  WARNING: Without a GPU, each scan will take 10-15 minutes to process.
        echo.
        pip install torch torchvision
        if errorlevel 1 (
            echo  ERROR: PyTorch could not be installed.
            echo  Check your internet connection and try again.
            pause
            exit /b 1
        )
    )
)
echo  PyTorch ready.
echo.

REM ================================================================
REM  STEP 5 of 6 -- Install nnUNetv2 and web framework
REM ================================================================
echo  [Step 5 of 6]  Installing nnUNetv2 and web framework...
echo.
python -c "import nnunetv2" >nul 2>&1
if not errorlevel 1 (
    echo  nnUNetv2 already installed. Skipping.
) else (
    echo  Installing nnUNetv2 (this may take a few minutes)...
    pip install nnunetv2
    if errorlevel 1 (
        echo  ERROR: nnUNetv2 install failed.
        echo  Check your internet connection and try again.
        pause
        exit /b 1
    )
)
echo  Installing web framework...
pip install -r "%~dp0backend\requirements.txt"
if errorlevel 1 (
    echo  ERROR: Web framework install failed.
    pause
    exit /b 1
)
echo  nnUNetv2 and web framework ready.
echo.

REM ================================================================
REM  STEP 6 of 6 -- Install frontend (npm)
REM ================================================================
echo  [Step 6 of 6]  Installing frontend dependencies...
echo.
cd /d "%~dp0frontend"
call npm install
if errorlevel 1 (
    echo  ERROR: npm install failed.
    echo  Make sure Node.js is installed correctly.
    pause
    exit /b 1
)
cd /d "%~dp0"
echo  Frontend dependencies ready.
echo.

REM ================================================================
REM  Set the nnunet_data path
REM ================================================================
echo  ================================================================
echo   Almost done! The app needs to know where your data is stored.
echo  ================================================================
echo.
echo  Where is your nnunet_data folder?
echo.
echo  This is the folder that contains these subfolders:
echo    nnUNet_results\
echo    nnUNet_preprocessed\
echo    nnUNet_raw\
echo.
echo  If your data is on Google Drive it looks something like:
echo    G:\My Drive\08-3D-Liver-Tumor-Segmentation\nnunet_data
echo.
echo  Not sure where it is?
echo    1. Open File Explorer
echo    2. Navigate into your nnunet_data folder
echo    3. Click on the address bar at the top of File Explorer
echo    4. The full path appears -- copy and paste it below
echo.
set /p USER_PATH="  Paste the path and press Enter (or just press Enter to skip): "

if "!USER_PATH!"=="" (
    echo.
    echo  Skipped. You can set the path later:
    echo    Option A: Edit backend\config.py and change NNUNET_BASE_FALLBACK
    echo    Option B: Open Command Prompt and run:
    echo              setx NNUNET_BASE "your\full\path\here"
) else (
    setx NNUNET_BASE "!USER_PATH!"
    if exist "!USER_PATH!" (
        echo.
        echo  Path found and saved.
    ) else (
        echo.
        echo  Path saved (folder not visible yet).
        echo  If using Google Drive, make sure the folder is fully
        echo  synced (green checkmarks on files) before running the app.
    )
)

REM ================================================================
REM  Done
REM ================================================================
echo.
echo  ================================================================
echo   Setup complete!
echo.
echo   To start the app:
echo     Double-click run.bat
echo.
echo   The app will open in your browser at:
echo     http://localhost:5173
echo  ================================================================
echo.
pause
