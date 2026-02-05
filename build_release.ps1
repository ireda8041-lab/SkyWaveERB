# Build Sky Wave ERP v2.1.2 Release
# Script to build and prepare release

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Building Sky Wave ERP v2.1.2" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Python
Write-Host "Step 1: Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "ERROR: Python not installed" -ForegroundColor Red
    exit 1
}

# Step 2: Check PyInstaller
Write-Host ""
Write-Host "Step 2: Checking PyInstaller..." -ForegroundColor Yellow
$pyinstallerCheck = pip show pyinstaller 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: PyInstaller installed" -ForegroundColor Green
} else {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# Step 3: Clean old builds
Write-Host ""
Write-Host "Step 3: Cleaning old builds..." -ForegroundColor Yellow
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
    Write-Host "OK: Removed dist folder" -ForegroundColor Green
}
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
    Write-Host "OK: Removed build folder" -ForegroundColor Green
}

# Step 4: Build executable
Write-Host ""
Write-Host "Step 4: Building executable..." -ForegroundColor Yellow
Write-Host "This may take several minutes..." -ForegroundColor Cyan

pyinstaller SkyWaveERP.spec --clean --noconfirm

if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: Executable built successfully" -ForegroundColor Green
} else {
    Write-Host "ERROR: Build failed" -ForegroundColor Red
    exit 1
}

# Step 5: Verify executable
Write-Host ""
Write-Host "Step 5: Verifying executable..." -ForegroundColor Yellow
$exePath = "dist\SkyWaveERP\SkyWaveERP.exe"
if (Test-Path $exePath) {
    $fileSize = (Get-Item $exePath).Length / 1MB
    $fileSizeRounded = [math]::Round($fileSize, 2)
    Write-Host "OK: File exists: $exePath" -ForegroundColor Green
    Write-Host "Size: $fileSizeRounded MB" -ForegroundColor Cyan
} else {
    Write-Host "ERROR: Executable not found" -ForegroundColor Red
    exit 1
}

# Step 6: Create installer (if Inno Setup is available)
Write-Host ""
Write-Host "Step 6: Creating installer..." -ForegroundColor Yellow
$innoSetup = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $innoSetup) {
    & $innoSetup "SkyWaveERP_Setup.iss"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK: Installer created" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Installer creation failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "WARNING: Inno Setup not installed - skipping" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Build completed successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files:" -ForegroundColor Yellow
Write-Host "  - Executable: dist\SkyWaveERP\SkyWaveERP.exe" -ForegroundColor Cyan
if (Test-Path "installer_output\SkyWaveERP-Setup-2.1.2.exe") {
    Write-Host "  - Installer: installer_output\SkyWaveERP-Setup-2.1.2.exe" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "Version: v2.1.2" -ForegroundColor Yellow
$currentDate = Get-Date -Format "yyyy-MM-dd"
Write-Host "Date: $currentDate" -ForegroundColor Yellow
Write-Host ""
Write-Host "Ready for release!" -ForegroundColor Green
Write-Host ""
