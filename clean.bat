@echo off
echo ====================================
echo    Sky Wave ERP - تنظيف سريع
echo ====================================

echo 🧹 تنظيف الملفات المؤقتة...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul

echo 🏗️ تنظيف ملفات البناء...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo 📄 تنظيف ملفات السجل...
echo. > logs/skywave_erp.log

echo ✅ تم التنظيف بنجاح!
echo 🚀 المشروع جاهز للتشغيل
