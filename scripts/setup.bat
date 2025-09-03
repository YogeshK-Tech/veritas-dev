@echo off
echo ========================================
echo    Veritas AI Auditor - Setup Script
echo ========================================

echo.
echo Checking prerequisites...

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

:: Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 16+ from https://nodejs.org
    pause
    exit /b 1
)

echo ✓ Python and Node.js are installed

echo.
echo Setting up backend...
cd backend

:: Create virtual environment
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

:: Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

:: Install Python dependencies
echo Installing Python dependencies...
pip install -r requirements.txt

:: Create .env file if it doesn't exist
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit backend\.env and add your API keys:
    echo - GOOGLE_API_KEY=your_google_ai_api_key
    echo - SECRET_KEY=your_secret_key_for_jwt
    echo.
)

cd ..

echo.
echo Setting up frontend...
cd frontend

:: Install Node.js dependencies
echo Installing Node.js dependencies...
npm install

:: Create .env file if it doesn't exist
if not exist ".env" (
    echo Creating frontend .env file...
    copy .env.example .env
)

cd ..

echo.
echo Creating upload directory...
if not exist "backend\uploads" (
    mkdir backend\uploads
)

echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit backend\.env with your API keys
echo 2. Run 'scripts\run-dev.bat' to start development servers
echo 3. Open http://localhost:3000 in your browser
echo.

pause