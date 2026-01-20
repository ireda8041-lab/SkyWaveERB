# ============================================
# Sky Wave ERP v2.0.0 - Complete Build Script
# سكريبت بناء كامل للمشروع
# ============================================

param(
    [switch]$SkipEXE = $false,
    [switch]$SkipSetup = $false
)

$ErrorActionPreference = "Stop"

Write-Host "`n" -NoNewline
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                            ║" -ForegroundColor Cyan
Write-Host "║       Sky Wave ERP v2.0.0 - Complete Build Script        ║" -ForegroundColor White
Write-Host "║                                                            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ==================== 1. التحقق من المتطلبات ====================
Write-Host "1. التحقق من المتطلبات..." -ForegroundColor Yellow

# Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Python: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "❌ Python غير مثبت!" -ForegroundColor Red
    exit 1
}

# PyInstaller
$pyinstallerVersion = python -m PyInstaller --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ PyInstaller: $pyinstallerVersion" -ForegroundColor Green
} else {
    Write-Host "⚠️ PyInstaller غير مثبت - جاري التثبيت..." -ForegroundColor Yellow
    pip install pyinstaller
}

Write-Host ""

# ==================== 2. تنظيف المجلدات القديمة ====================
if (-not $SkipEXE) {
    Write-Host "2. تنظيف المجلدات القديمة..." -ForegroundColor Yellow
    
    if (Test-Path "build") {
        Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue
        Write-Host "✅ تم حذف مجلد build" -ForegroundColor Green
    }
    
    if (Test-Path "dist") {
        Remove-Item -Recurse -Force "dist" -ErrorAction SilentlyContinue
        Write-Host "✅ تم حذف مجلد dist" -ForegroundColor Green
    }
    
    Write-Host ""
}


# ==================== 3. بناء EXE ====================
if (-not $SkipEXE) {
    Write-Host "3. بناء EXE باستخدام PyInstaller..." -ForegroundColor Yellow
    Write-Host "   هذه العملية قد تستغرق 5-10 دقائق..." -ForegroundColor Cyan
    Write-Host ""
    
    $buildStart = Get-Date
    python -m PyInstaller --clean SkyWaveERP.spec
    $buildEnd = Get-Date
    $buildTime = ($buildEnd - $buildStart).TotalMinutes
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ تم بناء EXE بنجاح!" -ForegroundColor Green
        Write-Host "   الوقت المستغرق: $([math]::Round($buildTime, 2)) دقيقة" -ForegroundColor Cyan
        
        # التحقق من وجود الملف
        if (Test-Path "dist\SkyWaveERP\SkyWaveERP.exe") {
            $fileSize = (Get-Item "dist\SkyWaveERP\SkyWaveERP.exe").Length / 1MB
            Write-Host "   حجم EXE: $([math]::Round($fileSize, 2)) MB" -ForegroundColor Cyan
            
            # عد الملفات
            $fileCount = (Get-ChildItem "dist\SkyWaveERP" -Recurse -File).Count
            Write-Host "   عدد الملفات: $fileCount" -ForegroundColor Cyan
        } else {
            Write-Host "❌ لم يتم العثور على EXE!" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "`n❌ فشل بناء EXE!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
}

# ==================== 4. إنشاء Setup Installer ====================
if (-not $SkipSetup) {
    Write-Host "4. التحقق من Inno Setup..." -ForegroundColor Yellow
    
    # البحث عن Inno Setup
    $innoSetupPaths = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        "C:\Program Files\Inno Setup 5\ISCC.exe"
    )
    
    $isccPath = $null
    foreach ($path in $innoSetupPaths) {
        if (Test-Path $path) {
            $isccPath = $path
            break
        }
    }
    
    if ($isccPath) {
        Write-Host "✅ Inno Setup موجود: $isccPath" -ForegroundColor Green
        Write-Host ""
        
        Write-Host "5. بناء Setup Installer..." -ForegroundColor Yellow
        
        # إنشاء مجلد الإخراج
        if (-not (Test-Path "installer_output")) {
            New-Item -ItemType Directory -Path "installer_output" | Out-Null
        }
        
        # بناء Setup
        & $isccPath "SkyWaveERP_Setup.iss"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "`n✅ تم إنشاء Setup بنجاح!" -ForegroundColor Green
            
            # البحث عن ملف Setup
            $setupFile = Get-ChildItem "installer_output" -Filter "*.exe" | Select-Object -First 1
            if ($setupFile) {
                $setupSize = $setupFile.Length / 1MB
                Write-Host "   ملف Setup: $($setupFile.Name)" -ForegroundColor Cyan
                Write-Host "   حجم Setup: $([math]::Round($setupSize, 2)) MB" -ForegroundColor Cyan
            }
        } else {
            Write-Host "`n⚠️ فشل إنشاء Setup" -ForegroundColor Yellow
        }
    } else {
        Write-Host "⚠️ Inno Setup غير مثبت" -ForegroundColor Yellow
        Write-Host "   حمّله من: https://jrsoftware.org/isdl.php" -ForegroundColor Cyan
    }
    
    Write-Host ""
}


# ==================== 7. الملخص النهائي ====================
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                                                            ║" -ForegroundColor Green
Write-Host "║              ✅ اكتمل البناء بنجاح!                      ║" -ForegroundColor White
Write-Host "║                                                            ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "📦 الملفات المبنية:" -ForegroundColor Cyan
Write-Host ""

if (Test-Path "dist\SkyWaveERP\SkyWaveERP.exe") {
    Write-Host "✅ EXE: dist\SkyWaveERP\SkyWaveERP.exe" -ForegroundColor Green
}

$setupFiles = Get-ChildItem "installer_output" -Filter "*.exe" -ErrorAction SilentlyContinue
if ($setupFiles) {
    foreach ($file in $setupFiles) {
        Write-Host "✅ Setup: installer_output\$($file.Name)" -ForegroundColor Green
    }
}


Write-Host ""
Write-Host "📋 الخطوات التالية:" -ForegroundColor Yellow
Write-Host "   1. اختبر EXE: dist\SkyWaveERP\SkyWaveERP.exe" -ForegroundColor White
Write-Host "   2. اختبر Setup من مجلد installer_output" -ForegroundColor White
Write-Host "   3. ارفع الملفات على GitHub Release" -ForegroundColor White
Write-Host ""
Write-Host "Made with ❤️ by Sky Wave Team" -ForegroundColor Magenta
Write-Host ""
