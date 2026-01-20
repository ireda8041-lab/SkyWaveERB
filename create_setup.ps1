# ============================================
# Sky Wave ERP - إنشاء Setup احترافي
# ============================================

param(
    [switch]$SkipBuild,
    [switch]$OpenFolder
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "🚀 Sky Wave ERP - إنشاء Setup احترافي" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# التحقق من البيئة الافتراضية
if (-not (Test-Path ".venv")) {
    Write-Host "❌ البيئة الافتراضية غير موجودة!" -ForegroundColor Red
    Write-Host "يرجى تشغيل: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# تفعيل البيئة الافتراضية
Write-Host "🔧 تفعيل البيئة الافتراضية..." -ForegroundColor Yellow
& .venv\Scripts\activate

if (-not $SkipBuild) {
    # 1. تنظيف الملفات القديمة
    Write-Host "🧹 تنظيف الملفات القديمة..." -ForegroundColor Yellow
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "installer_output") { Remove-Item -Recurse -Force "installer_output" }
    Write-Host "   ✅ تم التنظيف" -ForegroundColor Green
    Write-Host ""

    # 2. بناء البرنامج
    Write-Host "🏗️ بناء البرنامج (قد يستغرق 3-5 دقائق)..." -ForegroundColor Yellow
    & python -m PyInstaller --clean -y SkyWaveERP.spec
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ فشل بناء البرنامج!" -ForegroundColor Red
        exit 1
    }
    Write-Host "   ✅ تم بناء البرنامج بنجاح" -ForegroundColor Green
    Write-Host ""

    # 3. نسخ قاعدة البيانات (مع معالجة الأخطاء)
    Write-Host "📁 نسخ قاعدة البيانات..." -ForegroundColor Yellow
    $maxRetries = 5
    $retryCount = 0
    $copied = $false
    
    while (-not $copied -and $retryCount -lt $maxRetries) {
        try {
            if (Test-Path "skywave_local.db") {
                # إنشاء نسخة مؤقتة
                Copy-Item "skywave_local.db" "temp_db.db" -Force
                Copy-Item "temp_db.db" "dist\SkyWaveERP\skywave_local.db" -Force
                Remove-Item "temp_db.db" -Force
                $copied = $true
                Write-Host "   ✅ تم نسخ قاعدة البيانات" -ForegroundColor Green
            } else {
                Write-Host "   ⚠️ قاعدة البيانات غير موجودة - سيتم إنشاؤها عند أول تشغيل" -ForegroundColor Yellow
                $copied = $true
            }
        } catch {
            $retryCount++
            Write-Host "   ⚠️ محاولة $retryCount من $maxRetries..." -ForegroundColor Yellow
            Start-Sleep -Seconds 2
        }
    }
    
    if (-not $copied) {
        Write-Host "   ⚠️ لم يتم نسخ قاعدة البيانات - سيتم إنشاؤها عند أول تشغيل" -ForegroundColor Yellow
    }
    Write-Host ""
}

# 4. التحقق من وجود Inno Setup
Write-Host "🔍 البحث عن Inno Setup..." -ForegroundColor Yellow
$innoPath = $null

# البحث في المسارات الشائعة
$possiblePaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\iscc.exe",
    "${env:ProgramFiles}\Inno Setup 6\iscc.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 5\iscc.exe",
    "${env:ProgramFiles}\Inno Setup 5\iscc.exe"
)

foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $innoPath = $path
        break
    }
}

# البحث في PATH
if (-not $innoPath) {
    try {
        $innoPath = (Get-Command "iscc" -ErrorAction Stop).Source
    } catch {
        # لم يتم العثور على Inno Setup
    }
}

if ($innoPath) {
    Write-Host "   ✅ تم العثور على Inno Setup: $innoPath" -ForegroundColor Green
    Write-Host ""
    
    # 5. إنشاء مجلد الإخراج
    if (-not (Test-Path "installer_output")) {
        New-Item -ItemType Directory -Path "installer_output" | Out-Null
    }
    
    # 6. إنشاء ملف التثبيت
    Write-Host "📦 إنشاء ملف التثبيت..." -ForegroundColor Yellow
    & $innoPath "SkyWaveERP_Setup.iss"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ تم إنشاء ملف التثبيت بنجاح!" -ForegroundColor Green
        Write-Host ""
        
        # عرض النتائج
        Write-Host "============================================" -ForegroundColor Green
        Write-Host "🎉 تم إنشاء Setup بنجاح!" -ForegroundColor Green
        Write-Host "============================================" -ForegroundColor Green
        Write-Host ""
        
        # البحث عن ملف Setup
        $setupFiles = Get-ChildItem "installer_output" -Filter "*.exe" | Sort-Object LastWriteTime -Descending
        if ($setupFiles) {
            $setupFile = $setupFiles[0]
            Write-Host "📁 ملف التثبيت:" -ForegroundColor Cyan
            Write-Host "   $($setupFile.FullName)" -ForegroundColor White
            Write-Host "   الحجم: $([math]::Round($setupFile.Length / 1MB, 2)) MB" -ForegroundColor White
            Write-Host ""
        }
        
        Write-Host "📂 النسخة المحمولة:" -ForegroundColor Cyan
        Write-Host "   dist\SkyWaveERP\SkyWaveERP.exe" -ForegroundColor White
        Write-Host ""
        
        Write-Host "🔐 بيانات تسجيل الدخول الافتراضية:" -ForegroundColor Cyan
        Write-Host "   اسم المستخدم: admin" -ForegroundColor White
        Write-Host "   كلمة المرور: admin123" -ForegroundColor White
        Write-Host ""
        
        if ($OpenFolder) {
            Write-Host "📂 فتح مجلد الإخراج..." -ForegroundColor Yellow
            Start-Process "installer_output"
        }
        
    } else {
        Write-Host "   ❌ فشل إنشاء ملف التثبيت!" -ForegroundColor Red
        exit 1
    }
    
} else {
    Write-Host "   ⚠️ لم يتم العثور على Inno Setup" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "📥 لإنشاء ملف التثبيت:" -ForegroundColor Cyan
    Write-Host "   1. حمّل Inno Setup من: https://jrsoftware.org/isdl.php" -ForegroundColor White
    Write-Host "   2. ثبته واعد تشغيل هذا الـ Script" -ForegroundColor White
    Write-Host ""
    Write-Host "📂 في الوقت الحالي، يمكنك استخدام النسخة المحمولة:" -ForegroundColor Cyan
    Write-Host "   dist\SkyWaveERP\SkyWaveERP.exe" -ForegroundColor White
    Write-Host ""
}

Write-Host "============================================" -ForegroundColor Green
Write-Host "✅ انتهى!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green