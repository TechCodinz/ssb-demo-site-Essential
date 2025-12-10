@echo off
cd /d "%~dp0"

echo ================================================
echo   LeanTraderBot Mini v4 - Windows Installation
echo ================================================
echo.

echo Creating Python virtual environment...
python -m venv venv

echo.
echo Activating environment...
call venv\Scripts\activate

echo.
echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Installation complete!
echo --------------------------------
echo To run demo:
echo     start_demo.bat
echo.
echo To run live trading:
echo     start_live.bat
echo --------------------------------

pause
