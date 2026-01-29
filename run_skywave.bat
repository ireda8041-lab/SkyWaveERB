@echo off
echo ============================================================
echo Sky Wave ERP v2.0.1 - Starting Application
echo ============================================================
echo.

cd /d "%~dp0"

if exist "dist\SkyWaveERP\SkyWaveERP.exe" (
    echo Starting Sky Wave ERP...
    echo.
    start "" "dist\SkyWaveERP\SkyWaveERP.exe"
    echo Application started successfully!
) else (
    echo ERROR: SkyWaveERP.exe not found!
    echo Please make sure the application is built correctly.
    pause
)

echo.
echo ============================================================