@echo off
echo ========================================
echo   Fix SkyWave ERP Database
echo ========================================
echo.

echo Step 1: Closing any running instances...
taskkill /F /IM SkyWaveERP.exe 2>nul
timeout /t 2 >nul

echo Step 2: Creating admin user...
cd /d "D:\blogs\appas\SkyWaveERB"
.venv\Scripts\python.exe create_admin.py

echo.
echo Step 3: Copying database...
copy /Y "skywave_local.db" "dist\SkyWaveERP\skywave_local.db"

echo.
echo ========================================
echo   Done!
echo ========================================
echo.
echo Now you can run: dist\SkyWaveERP\SkyWaveERP.exe
echo.
echo Login:
echo   Username: admin
echo   Password: admin123
echo.
pause
