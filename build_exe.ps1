# Build SkyWave ERP Executable
# Clean and fast build script

Write-Host "Building SkyWave ERP..." -ForegroundColor Cyan
Write-Host ""

# 1. Clean old files
Write-Host "1. Cleaning old build folders..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
Write-Host "   Done" -ForegroundColor Green
Write-Host ""

# 2. Build EXE
Write-Host "2. Building EXE (2-3 minutes)..." -ForegroundColor Yellow
& .venv\Scripts\python.exe -m PyInstaller --clean -y SkyWaveERP.spec
if ($LASTEXITCODE -eq 0) {
    Write-Host "   Build successful" -ForegroundColor Green
} else {
    Write-Host "   Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# 3. Copy database
Write-Host "3. Copying database..." -ForegroundColor Yellow
if (Test-Path "skywave_local.db") {
    Copy-Item "skywave_local.db" "dist\SkyWaveERP\" -Force
    Write-Host "   Database copied" -ForegroundColor Green
} else {
    Write-Host "   Warning: Database not found!" -ForegroundColor Yellow
}
Write-Host ""

# 4. Summary
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Build completed successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "EXE Location:" -ForegroundColor Cyan
Write-Host "   dist\SkyWaveERP\SkyWaveERP.exe" -ForegroundColor White
Write-Host ""
Write-Host "To run:" -ForegroundColor Cyan
Write-Host '   cd "dist\SkyWaveERP"' -ForegroundColor White
Write-Host "   .\SkyWaveERP.exe" -ForegroundColor White
Write-Host ""
Write-Host "Login credentials:" -ForegroundColor Cyan
Write-Host "   Username: admin" -ForegroundColor White
Write-Host "   Password: admin123" -ForegroundColor White
Write-Host ""
