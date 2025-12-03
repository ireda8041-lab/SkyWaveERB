@echo off
chcp 65001 >nul
echo ========================================
echo بناء Sky Wave ERP - ملف واحد
echo ========================================
echo.

echo [1/3] تنظيف المجلدات القديمة...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo ✅ تم التنظيف

echo.
echo [2/3] بناء البرنامج (قد يستغرق 5-10 دقائق)...
python -m PyInstaller SkyWaveERP_onefile.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ❌ فشل البناء!
    echo تحقق من الأخطاء أعلاه
    pause
    exit /b 1
)

echo.
echo [3/3] نسخ الملفات المطلوبة...
if exist dist\SkyWaveERP.exe (
    echo ✅ تم إنشاء SkyWaveERP.exe
    
    REM نسخ قاعدة البيانات والإعدادات
    if exist skywave_local.db copy skywave_local.db dist\
    if exist skywave_settings.json copy skywave_settings.json dist\
    if exist version.json copy version.json dist\
    
    REM إنشاء مجلد exports
    if not exist dist\exports mkdir dist\exports
    if not exist dist\logs mkdir dist\logs
    
    echo ✅ تم نسخ الملفات الإضافية
) else (
    echo ❌ لم يتم إنشاء الملف!
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ تم البناء بنجاح!
echo ========================================
echo.
echo 📁 الملف: dist\SkyWaveERP.exe
echo 📦 الحجم: 
dir dist\SkyWaveERP.exe | find "SkyWaveERP.exe"
echo.
echo يمكنك الآن تشغيل البرنامج من:
echo dist\SkyWaveERP.exe
echo.
pause
