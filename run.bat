@echo off
echo ============================================
echo  Lifeline Twitch Voice Controller
echo ============================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

:: Install dependencies
echo Installing / updating dependencies...
pip install -r requirements.txt --quiet

echo.
echo Starting Lifeline Bot...
echo.
python lifeline_bot.py

pause
