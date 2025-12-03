@echo off
echo ================================================================================
echo Building Sky Wave ERP - EXE
echo ================================================================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

echo.
echo Building EXE...
echo This may take several minutes...
echo.

pyinstaller --name=SkyWaveERP ^
    --onedir ^
    --windowed ^
    --icon=icon.ico ^
    --add-data="assets;assets" ^
    --add-data="core;core" ^
    --add-data="services;services" ^
    --add-data="ui;ui" ^
    --add-data="logo.png;." ^
    --add-data="icon.ico;." ^
    --add-data="version.json;." ^
    --hidden-import=pymongo ^
    --hidden-import=PyQt6 ^
    --hidden-import=jinja2 ^
    --hidden-import=arabic_reshaper ^
    --hidden-import=bidi ^
    --hidden-import=PIL ^
    --hidden-import=reportlab ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --clean ^
    main.py

if errorlevel 1 (
    echo.
    echo ================================================================================
    echo ERROR: Build failed!
    echo ================================================================================
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo SUCCESS: EXE built successfully!
echo ================================================================================
echo.
echo Location: dist\SkyWaveERP\SkyWaveERP.exe
echo.

REM Copy additional files
echo Copying additional files...
copy skywave_local.db dist\SkyWaveERP\ 2>nul
copy skywave_settings.json dist\SkyWaveERP\ 2>nul
mkdir dist\SkyWaveERP\exports 2>nul
mkdir dist\SkyWaveERP\logs 2>nul

echo.
echo ================================================================================
echo Done! You can now run: dist\SkyWaveERP\SkyWaveERP.exe
echo ================================================================================
pause
