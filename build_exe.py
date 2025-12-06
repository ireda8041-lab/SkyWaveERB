"""
🚀 سكريبت بناء SkyWave ERP كملف EXE
يقوم بإنشاء ملف تنفيذي يحتوي على كل الملفات الضرورية
"""

import os
import subprocess
import sys

def build_exe():
    print("="*60)
    print("🚀 بدء عملية بناء SkyWave ERP")
    print("="*60)
    
    # التأكد من تثبيت PyInstaller
    try:
        import PyInstaller
        print("✅ PyInstaller موجود")
    except ImportError:
        print("⚠️ PyInstaller غير مثبت. جاري التثبيت...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ تم تثبيت PyInstaller")
    
    # أمر PyInstaller المحسّن
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",  # مجلد واحد يحتوي على EXE والملفات
        "--windowed",  # بدون console
        "--name", "SkyWaveERP",
        "--icon", "icon.ico",
        
        # ===== إضافة المجلدات الأساسية =====
        "--add-data", "ui;ui",
        "--add-data", "services;services",
        "--add-data", "core;core",
        "--add-data", "assets;assets",
        
        # ===== ملفات الإعدادات والإصدار =====
        "--add-data", "skywave_settings.json;.",
        "--add-data", "version.json;.",
        "--add-data", "version.py;.",
        
        # ===== ملفات التحديث =====
        "--add-data", "updater.py;.",
        "--add-data", "update_settings.json;.",
        
        # ===== الصور والأيقونات =====
        "--add-data", "icon.ico;.",
        "--add-data", "logo.png;.",
    ]
    
    # إضافة site logo إذا كان موجود
    if os.path.exists("site logo.png"):
        cmd.extend(["--add-data", "site logo.png;."])
    
    # إضافة updater.exe إذا كان موجود
    if os.path.exists("updater.exe"):
        cmd.extend(["--add-binary", "updater.exe;."])
    
    # إضافة قاعدة البيانات إذا كانت موجودة
    if os.path.exists("skywave_local.db"):
        cmd.extend(["--add-data", "skywave_local.db;."])
    
    # ===== Hidden imports للمكتبات المهمة =====
    hidden_imports = [
        "pymongo",
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "reportlab",
        "reportlab.pdfgen",
        "reportlab.lib",
        "reportlab.platypus",
        "PIL",
        "PIL.Image",
        "openpyxl",
        "google.generativeai",
        "requests",
        "urllib3",
        "sqlite3",
        "json",
        "threading",
        "queue",
    ]
    
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])
    
    # ===== جمع كل ملفات المكتبات =====
    cmd.extend([
        "--collect-all", "reportlab",
        "--collect-all", "PIL",
    ])
    
    # ===== الملف الرئيسي =====
    cmd.append("main.py")
    
    print("\n📦 جاري بناء الملف التنفيذي...")
    print("⏳ هذا قد يستغرق عدة دقائق...\n")
    
    try:
        # تنفيذ الأمر
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        
        print("\n" + "="*60)
        print("✅ تم بناء البرنامج بنجاح!")
        print("="*60)
        print("\n📁 الملفات موجودة في:")
        print("   - dist/SkyWaveERP/SkyWaveERP.exe")
        print("\n💡 ملاحظات:")
        print("   1. المجلد dist/SkyWaveERP يحتوي على البرنامج كاملاً")
        print("   2. يجب نسخ المجلد كاملاً عند التوزيع")
        print("   3. لا تنسخ ملف EXE لوحده!")
        print("\n🎉 جاهز للاستخدام!")
        
    except subprocess.CalledProcessError as e:
        print("\n❌ فشل بناء البرنامج!")
        print(f"الخطأ: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ حدث خطأ: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()
