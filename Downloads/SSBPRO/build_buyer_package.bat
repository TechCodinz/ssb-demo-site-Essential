@echo off
REM Sol Sniper Bot PRO - Build Buyer Package Script
REM Run this to create the final ZIP for buyers

echo.
echo ============================================
echo   Sol Sniper Bot PRO - Package Builder
echo ============================================
echo.

REM Create package directory
set PKG_DIR=SolSniperBotPRO_Package
if exist "%PKG_DIR%" rmdir /s /q "%PKG_DIR%"
mkdir "%PKG_DIR%"

echo [1/5] Copying core bot...
copy "dist\ssb_core.exe" "%PKG_DIR%\" >nul

echo [2/5] Copying GUI...
mkdir "%PKG_DIR%\gui_main"
xcopy "dist\gui_main\*" "%PKG_DIR%\gui_main\" /E /I /Y >nul

echo [3/5] Copying config template...
copy "config.sample.json" "%PKG_DIR%\config.sample.json" >nul

echo [4/5] Copying documentation...
copy "buyer_package\README.md" "%PKG_DIR%\README.md" >nul
copy "buyer_package\LICENSE.txt" "%PKG_DIR%\LICENSE.txt" >nul

echo [5/5] Creating ZIP archive...
powershell -Command "Compress-Archive -Path '%PKG_DIR%\*' -DestinationPath 'SolSniperBotPRO.zip' -Force"

echo.
echo ============================================
echo   Package created: SolSniperBotPRO.zip
echo ============================================
echo.
echo Contents:
echo   - ssb_core.exe (Core trading engine)
echo   - gui_main/ (Premium GUI)
echo   - config.sample.json (Configuration template)
echo   - README.md (Installation guide)
echo   - LICENSE.txt (License agreement)
echo.
echo Next steps:
echo   1. Generate a license for the buyer
echo   2. Add the .ssb license file to the ZIP
echo   3. Send to buyer via Telegram
echo.

REM Cleanup
rmdir /s /q "%PKG_DIR%"

pause
