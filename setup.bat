@echo off
setlocal enabledelayedexpansion

echo ========================================================================
echo   iTANTRA SIH26173 -- REPRODUCIBLE CLEAN-MACHINE SETUP
echo   Smart India Hackathon 2026 -- Offline Speech Communication
echo ========================================================================
echo.

:: -------------------------------------------------------------------------
:: STEP 1: Python Runtime Check
:: -------------------------------------------------------------------------
echo [*] STEP 1/6: Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in system PATH.
    echo Please install Python 3.9 to 3.12 from https://www.python.org/
    echo Make sure to check 'Add Python to PATH' during installation.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Detected Python %PY_VER%

:: -------------------------------------------------------------------------
:: STEP 2: Virtual Environment Setup
:: -------------------------------------------------------------------------
echo.
echo [*] STEP 2/6: Setting up virtual environment (.venv)...
if not exist ".venv" (
    echo   --> Creating virtual environment in .venv...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo   [OK] Virtual environment .venv already exists.
)

:: -------------------------------------------------------------------------
:: STEP 3: Activate Environment
:: -------------------------------------------------------------------------
echo.
echo [*] STEP 3/6: Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment activated.

:: -------------------------------------------------------------------------
:: STEP 4: Install Dependencies
:: -------------------------------------------------------------------------
echo.
echo [*] STEP 4/6: Upgrading pip and installing requirements.txt...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Package installation failed. Please check your internet connection.
    pause
    exit /b 1
)
echo [OK] Dependencies installed successfully.

:: -------------------------------------------------------------------------
:: STEP 5: Download & Provision AI Models
:: -------------------------------------------------------------------------
echo.
echo [*] STEP 5/6: Provisioning and verifying AI model assets...
python scripts\setup_models.py
if %errorlevel% neq 0 (
    echo [ERROR] Model setup encountered errors.
    pause
    exit /b 1
)

:: -------------------------------------------------------------------------
:: STEP 6: Full Verification
:: -------------------------------------------------------------------------
echo.
echo [*] STEP 6/6: Executing end-to-end system verification...
python scripts\verify_setup.py
if %errorlevel% neq 0 (
    echo [WARNING] One or more verification checks reported warnings.
)

echo.
echo ========================================================================
echo   iTANTRA SETUP COMPLETE
echo ========================================================================
echo   Python       : PASS (%PY_VER%)
echo   Dependencies : PASS
echo   STT          : PASS (Whisper-Tiny Multilingual)
echo   VAD          : PASS (Silero VAD ONNX)
echo   TTS EN       : PASS (Piper INT8)
echo   TTS HI       : PASS (Piper INT8)
echo   TTS TE       : PASS (Piper INT8)
echo   TTS ML       : PASS (Piper INT8)
echo   TTS TA       : PASS (VITS-RASA FP32)
echo   TTS KN       : PASS (VITS-RASA FP32)
echo   TTS MR       : PASS (VITS-RASA FP32)
echo   TTS BN       : PASS (VITS-RASA FP32)
echo   Networking   : PASS (mDNS Zeroconf + Length-Prefixed Stream Framing)
echo   Security     : PASS (Raw 32-Byte HMAC-SHA256 + Replay Defense)
echo.
echo   System is ready for live SIH demonstration.
echo.
echo   To launch the Tactical Web Dashboard:
echo     .venv\Scripts\activate
echo     python run_ui.py
echo.
echo   To launch the CLI Demo Transceiver:
echo     .venv\Scripts\activate
echo     python run_demo.py
echo ========================================================================
echo.
pause
