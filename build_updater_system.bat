@echo off
echo ========================================
echo بناء نظام التحديث التلقائي
echo ========================================
echo.

echo [1/2] بناء updater.exe...
python -m PyInstaller --onefile --name updater --icon icon.ico updater.py
if errorlevel 1 (
    echo خطأ في بناء updater.exe
    pause
    exit /b 1
)

echo.
echo [2/2] نسخ updater.exe إلى المجلد الرئيسي...
copy dist\updater.exe .
if errorlevel 1 (
    echo خطأ في نسخ updater.exe
    pause
    exit /b 1
)

echo.
echo ========================================
echo تم بناء نظام التحديث بنجاح!
echo ========================================
echo.
echo الملفات المنشأة:
echo - updater.exe (8.3 MB)
echo.
echo يمكنك الآن استخدام auto_updater.py في برنامجك
echo.
pause
