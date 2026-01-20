# بناء Sky Wave ERP v2.0.1
# Build Sky Wave ERP v2.0.1

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 بناء Sky Wave ERP v2.0.1" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. التحقق من Python
Write-Host "📋 الخطوة 1: التحقق من Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "❌ Python غير مثبت" -ForegroundColor Red
    exit 1
}

# 2. التحقق من المكتبات
Write-Host ""
Write-Host "📋 الخطوة 2: التحقق من المكتبات..." -ForegroundColor Yellow
$packages = @("PyQt6", "pymongo", "pydantic", "pyinstaller")
foreach ($package in $packages) {
    $installed = pip show $package 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ $package مثبت" -ForegroundColor Green
    } else {
        Write-Host "⚠️ $package غير مثبت - جاري التثبيت..." -ForegroundColor Yellow
        pip install $package
    }
}

# 3. تطبيق الإصلاحات
Write-Host ""
Write-Host "📋 الخطوة 3: تطبيق الإصلاحات..." -ForegroundColor Yellow
python apply_update_v2.0.1.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ تم تطبيق الإصلاحات" -ForegroundColor Green
} else {
    Write-Host "❌ فشل تطبيق الإصلاحات" -ForegroundColor Red
    exit 1
}

# 4. تنظيف الملفات القديمة
Write-Host ""
Write-Host "📋 الخطوة 4: تنظيف الملفات القديمة..." -ForegroundColor Yellow
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
    Write-Host "✅ تم حذف مجلد dist" -ForegroundColor Green
}
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
    Write-Host "✅ تم حذف مجلد build" -ForegroundColor Green
}

# 5. بناء الملف التنفيذي
Write-Host ""
Write-Host "📋 الخطوة 5: بناء الملف التنفيذي..." -ForegroundColor Yellow
Write-Host "⏳ هذا قد يستغرق عدة دقائق..." -ForegroundColor Cyan

pyinstaller SkyWaveERP.spec --clean

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ تم بناء الملف التنفيذي" -ForegroundColor Green
} else {
    Write-Host "❌ فشل بناء الملف التنفيذي" -ForegroundColor Red
    exit 1
}

# 6. التحقق من الملف التنفيذي
Write-Host ""
Write-Host "📋 الخطوة 6: التحقق من الملف التنفيذي..." -ForegroundColor Yellow
$exePath = "dist\SkyWaveERP.exe"
if (Test-Path $exePath) {
    $fileSize = (Get-Item $exePath).Length / 1MB
    Write-Host "✅ الملف موجود: $exePath" -ForegroundColor Green
    Write-Host "📊 الحجم: $([math]::Round($fileSize, 2)) MB" -ForegroundColor Cyan
} else {
    Write-Host "❌ الملف غير موجود" -ForegroundColor Red
    exit 1
}

# 7. إنشاء Setup Installer (اختياري)
Write-Host ""
Write-Host "📋 الخطوة 7: إنشاء Setup Installer..." -ForegroundColor Yellow
$innoSetup = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $innoSetup) {
    & $innoSetup "SkyWaveERP_Setup.iss"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ تم إنشاء Setup Installer" -ForegroundColor Green
    } else {
        Write-Host "⚠️ فشل إنشاء Setup Installer" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️ Inno Setup غير مثبت - تخطي هذه الخطوة" -ForegroundColor Yellow
}

# 8. الملخص النهائي
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "✅ تم البناء بنجاح!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📦 الملفات:" -ForegroundColor Yellow
Write-Host "  - الملف التنفيذي: dist\SkyWaveERP.exe" -ForegroundColor Cyan
if (Test-Path "installer_output\SkyWaveERP-Setup-2.0.1.exe") {
    Write-Host "  - Setup Installer: installer_output\SkyWaveERP-Setup-2.0.1.exe" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "📋 الإصدار: v2.0.1" -ForegroundColor Yellow
Write-Host "📅 التاريخ: $(Get-Date -Format 'yyyy-MM-dd')" -ForegroundColor Yellow
Write-Host ""
Write-Host "🎉 جاهز للنشر!" -ForegroundColor Green
Write-Host ""
