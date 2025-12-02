@echo off
echo ====================================
echo    تثبيت متطلبات الواتساب
echo ====================================
echo.
echo جاري تثبيت المكتبات المطلوبة...
echo.

pip install selenium>=4.15.0
pip install webdriver-manager>=4.0.0

echo.
echo ====================================
echo    تم التثبيت بنجاح!
echo ====================================
echo.
echo الخطوات التالية:
echo 1. شغل البرنامج: run.bat
echo 2. اختر مشروع
echo 3. اضغط "إرسال للواتساب"
echo 4. سجل دخول WhatsApp Web (أول مرة فقط)
echo.
pause