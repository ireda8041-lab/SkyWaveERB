# ============================================
# Sky Wave ERP - Deploy Script
# سكريبت رفع المشروع على GitHub
# ============================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Sky Wave ERP - Deploy Script v2.0.0  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# التحقق من Git
Write-Host "1. التحقق من Git..." -ForegroundColor Yellow
$gitVersion = git --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Git غير مثبت! يرجى تثبيت Git أولاً." -ForegroundColor Red
    exit 1
}
Write-Host "✅ Git مثبت: $gitVersion" -ForegroundColor Green
Write-Host ""

# التحقق من الحالة
Write-Host "2. التحقق من حالة Git..." -ForegroundColor Yellow
git status
Write-Host ""

# سؤال المستخدم
$confirm = Read-Host "هل تريد المتابعة؟ (y/n)"
if ($confirm -ne "y") {
    Write-Host "تم الإلغاء." -ForegroundColor Yellow
    exit 0
}
Write-Host ""

# إضافة الملفات
Write-Host "3. إضافة الملفات..." -ForegroundColor Yellow
git add .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل في إضافة الملفات!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ تم إضافة الملفات" -ForegroundColor Green
Write-Host ""

# Commit
Write-Host "4. عمل Commit..." -ForegroundColor Yellow
$commitMessage = Read-Host "أدخل رسالة Commit (اضغط Enter للرسالة الافتراضية)"
if ([string]::IsNullOrWhiteSpace($commitMessage)) {
    $commitMessage = "Release v2.0.0 - نظام محسّن ومستقر"
}
git commit -m "$commitMessage"
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ لا توجد تغييرات للـ commit" -ForegroundColor Yellow
}
Write-Host ""

# إنشاء Tag
Write-Host "5. إنشاء Tag..." -ForegroundColor Yellow
$createTag = Read-Host "هل تريد إنشاء Tag v2.0.0؟ (y/n)"
if ($createTag -eq "y") {
    git tag -a v2.0.0 -m "Release v2.0.0"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ تم إنشاء Tag v2.0.0" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Tag موجود بالفعل أو حدث خطأ" -ForegroundColor Yellow
    }
}
Write-Host ""

# Push
Write-Host "6. رفع التغييرات..." -ForegroundColor Yellow
$push = Read-Host "هل تريد Push إلى GitHub؟ (y/n)"
if ($push -eq "y") {
    Write-Host "جاري رفع الملفات..." -ForegroundColor Cyan
    git push origin main
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ تم رفع الملفات بنجاح" -ForegroundColor Green
    } else {
        Write-Host "❌ فشل في رفع الملفات!" -ForegroundColor Red
        exit 1
    }
    
    # Push Tags
    if ($createTag -eq "y") {
        Write-Host "جاري رفع Tags..." -ForegroundColor Cyan
        git push origin v2.0.0
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ تم رفع Tag بنجاح" -ForegroundColor Green
        } else {
            Write-Host "⚠️ فشل في رفع Tag" -ForegroundColor Yellow
        }
    }
}
Write-Host ""

# النتيجة النهائية
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ اكتمل Deploy بنجاح!  " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "الخطوات التالية:" -ForegroundColor Yellow
Write-Host "1. اذهب إلى: https://github.com/ireda8041-lab/SkyWaveERB" -ForegroundColor White
Write-Host "2. اضغط على 'Releases' ثم 'Create a new release'" -ForegroundColor White
Write-Host "3. اختر Tag: v2.0.0" -ForegroundColor White
Write-Host "4. ارفع ملفات Setup" -ForegroundColor White
Write-Host "5. اضغط 'Publish release'" -ForegroundColor White
Write-Host ""
Write-Host "Made with ❤️ by Sky Wave Team" -ForegroundColor Cyan
