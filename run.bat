@echo off
title Sky Wave ERP - Fast Start
echo ====================================
echo    Sky Wave ERP - Quick Launch
echo ====================================
python main.py
if %errorlevel% neq 0 (
    echo.
    echo خطأ في تشغيل البرنامج
    pause
)
