# Sky Wave ERP Release Builder
# Builds executable + installer using the version declared in version.json

$ErrorActionPreference = 'Stop'

function Write-Step([string]$msg) {
    Write-Host "`n=== $msg ===" -ForegroundColor Yellow
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Sky Wave ERP - Release Build" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

Write-Step "Loading version metadata"
if (-not (Test-Path "version.json")) {
    throw "version.json not found"
}
$versionMeta = Get-Content "version.json" -Raw | ConvertFrom-Json
$version = [string]$versionMeta.version
if ([string]::IsNullOrWhiteSpace($version)) {
    throw "version.json does not contain a valid 'version'"
}
Write-Host "Version: v$version" -ForegroundColor Cyan

Write-Step "Checking Python"
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Python is not available"
}
Write-Host "OK: $pythonVersion" -ForegroundColor Green

Write-Step "Checking PyInstaller"
python -m pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    python -m pip install pyinstaller
}
Write-Host "OK: PyInstaller is available" -ForegroundColor Green

Write-Step "Cleaning previous build artifacts"
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
Write-Host "OK: Cleaned dist/build" -ForegroundColor Green

Write-Step "Building executable"
if (-not (Test-Path "SkyWaveERP.spec")) {
    throw "SkyWaveERP.spec not found"
}
python -m PyInstaller SkyWaveERP.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed"
}

$exePath = "dist\SkyWaveERP\SkyWaveERP.exe"
if (-not (Test-Path $exePath)) {
    throw "Executable not found at $exePath"
}
$exeSizeMb = [math]::Round(((Get-Item $exePath).Length / 1MB), 2)
Write-Host "OK: Built $exePath ($exeSizeMb MB)" -ForegroundColor Green

Write-Step "Building installer (Inno Setup)"
$installerBuilt = $false
$isccPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($null -ne $iscc) {
    if (-not (Test-Path "SkyWaveERP_Setup.iss")) {
        throw "SkyWaveERP_Setup.iss not found"
    }
    & $iscc "SkyWaveERP_Setup.iss"
    if ($LASTEXITCODE -eq 0) {
        $installerBuilt = $true
        Write-Host "OK: Installer compiled successfully" -ForegroundColor Green
    }
    else {
        Write-Host "WARNING: Installer compilation failed" -ForegroundColor Yellow
    }
}
else {
    Write-Host "WARNING: Inno Setup not found. Skipping installer build." -ForegroundColor Yellow
}

$installerPath = "installer_output\SkyWaveERP-Setup-$version.exe"

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Build finished" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Executable: $exePath" -ForegroundColor Cyan
if ($installerBuilt -and (Test-Path $installerPath)) {
    Write-Host "Installer:  $installerPath" -ForegroundColor Cyan
}
elseif ($installerBuilt) {
    Write-Host "Installer compiled but expected path not found: $installerPath" -ForegroundColor Yellow
}
Write-Host "Version:    v$version" -ForegroundColor Cyan
Write-Host "Date:       $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
