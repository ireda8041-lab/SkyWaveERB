# Prepare GitHub Release for Sky Wave ERP v2.0.1

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Preparing GitHub Release v2.0.1" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Git
Write-Host "Step 1: Checking Git..." -ForegroundColor Yellow
$gitVersion = git --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: $gitVersion" -ForegroundColor Green
} else {
    Write-Host "ERROR: Git not installed" -ForegroundColor Red
    exit 1
}

# Step 2: Check Git status
Write-Host ""
Write-Host "Step 2: Checking Git status..." -ForegroundColor Yellow
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "Found uncommitted changes:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Cyan
} else {
    Write-Host "OK: Working directory clean" -ForegroundColor Green
}

# Step 3: Add all files
Write-Host ""
Write-Host "Step 3: Adding files to Git..." -ForegroundColor Yellow
git add .
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: Files added" -ForegroundColor Green
} else {
    Write-Host "ERROR: Failed to add files" -ForegroundColor Red
    exit 1
}

# Step 4: Commit changes
Write-Host ""
Write-Host "Step 4: Committing changes..." -ForegroundColor Yellow
$commitMessage = "Release v2.0.1 - Zero Errors Certification"
git commit -m $commitMessage
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: Changes committed" -ForegroundColor Green
} else {
    Write-Host "WARNING: Nothing to commit or commit failed" -ForegroundColor Yellow
}

# Step 5: Create tag
Write-Host ""
Write-Host "Step 5: Creating tag v2.0.1..." -ForegroundColor Yellow
git tag -a v2.0.1 -m "Sky Wave ERP v2.0.1 - Zero Errors Release"
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: Tag created" -ForegroundColor Green
} else {
    Write-Host "WARNING: Tag already exists or creation failed" -ForegroundColor Yellow
}

# Step 6: Push to GitHub
Write-Host ""
Write-Host "Step 6: Pushing to GitHub..." -ForegroundColor Yellow
Write-Host "Pushing commits..." -ForegroundColor Cyan
git push origin main
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: Commits pushed" -ForegroundColor Green
} else {
    Write-Host "ERROR: Failed to push commits" -ForegroundColor Red
}

Write-Host "Pushing tags..." -ForegroundColor Cyan
git push origin v2.0.1
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: Tag pushed" -ForegroundColor Green
} else {
    Write-Host "ERROR: Failed to push tag" -ForegroundColor Red
}

# Summary
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "GitHub Release Preparation Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Go to GitHub repository" -ForegroundColor Cyan
Write-Host "2. Click on 'Releases' tab" -ForegroundColor Cyan
Write-Host "3. Click 'Draft a new release'" -ForegroundColor Cyan
Write-Host "4. Select tag: v2.0.1" -ForegroundColor Cyan
Write-Host "5. Upload installer: installer_output\SkyWaveERP-Setup-2.0.1.exe" -ForegroundColor Cyan
Write-Host "6. Add release notes from RELEASE_NOTES_v2.0.1.md" -ForegroundColor Cyan
Write-Host "7. Publish release" -ForegroundColor Cyan
Write-Host ""
Write-Host "Repository URL: https://github.com/ireda8041-lab/SkyWaveERB" -ForegroundColor Green
Write-Host ""
