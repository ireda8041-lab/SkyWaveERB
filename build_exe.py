#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت بناء EXE لبرنامج Sky Wave ERP
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

print("=" * 80)
print("🔨 بناء Sky Wave ERP - EXE")
print("=" * 80)

# التحقق من PyInstaller
try:
    import PyInstaller
    print("✅ PyInstaller متوفر")
except ImportError:
    print("❌ PyInstaller غير متوفر")
    print("📦 جاري التثبيت...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
    print("✅ تم تثبيت PyInstaller")

# تنظيف المجلدات القديمة
print("\n🧹 تنظيف المجلدات القديمة...")
for folder in ['build', 'dist']:
    if os.path.exists(folder):
        shutil.rmtree(folder)
        print(f"  ✅ تم حذف {folder}")

# إنشاء ملف spec
spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('core', 'core'),
        ('services', 'services'),
        ('ui', 'ui'),
        ('logo.png', '.'),
        ('icon.ico', '.'),
        ('version.json', '.'),
    ],
    hiddenimports=[
        'pymongo',
        'sqlite3',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'jinja2',
        'arabic_reshaper',
        'bidi',
        'PIL',
        'reportlab',
        'pandas',
        'openpyxl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SkyWaveERP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # True لعرض الكونسول للتتبع
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SkyWaveERP',
)
"""

print("\n📝 إنشاء ملف spec...")
with open('SkyWaveERP.spec', 'w', encoding='utf-8') as f:
    f.write(spec_content)
print("  ✅ تم إنشاء SkyWaveERP.spec")

# بناء EXE
print("\n🔨 بناء EXE...")
print("⏳ هذا قد يستغرق عدة دقائق...")
print("-" * 80)

result = subprocess.run([
    'pyinstaller',
    '--clean',
    'SkyWaveERP.spec'
], capture_output=False)

if result.returncode == 0:
    print("-" * 80)
    print("\n✅ تم بناء EXE بنجاح!")
    
    # التحقق من الملف
    exe_path = Path('dist/SkyWaveERP/SkyWaveERP.exe')
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n📦 معلومات الملف:")
        print(f"  📍 المسار: {exe_path}")
        print(f"  📏 الحجم: {size_mb:.2f} MB")
        
        # نسخ الملفات الإضافية
        print("\n📋 نسخ الملفات الإضافية...")
        dist_folder = Path('dist/SkyWaveERP')
        
        # نسخ قاعدة البيانات
        if Path('skywave_local.db').exists():
            shutil.copy('skywave_local.db', dist_folder / 'skywave_local.db')
            print("  ✅ تم نسخ skywave_local.db")
        
        # نسخ الإعدادات
        if Path('skywave_settings.json').exists():
            shutil.copy('skywave_settings.json', dist_folder / 'skywave_settings.json')
            print("  ✅ تم نسخ skywave_settings.json")
        
        # إنشاء مجلد exports
        exports_folder = dist_folder / 'exports'
        exports_folder.mkdir(exist_ok=True)
        print("  ✅ تم إنشاء مجلد exports")
        
        # إنشاء مجلد logs
        logs_folder = dist_folder / 'logs'
        logs_folder.mkdir(exist_ok=True)
        print("  ✅ تم إنشاء مجلد logs")
        
        # إنشاء ملف README
        readme_content = """
# Sky Wave ERP

## التشغيل
1. افتح SkyWaveERP.exe
2. سجل الدخول بحسابك
3. استمتع بالبرنامج!

## المجلدات
- exports/ - الفواتير والتقارير المصدرة
- logs/ - سجلات البرنامج
- assets/ - الموارد (الخطوط، القوالب، الصور)

## الدعم
للدعم الفني، تواصل مع فريق Sky Wave

## الإصدار
Version 1.0.1 - 2025-12-01

## الميزات
✅ إدارة العملاء والفواتير
✅ نظام المدفوعات والحسابات
✅ التقارير والإحصائيات
✅ المزامنة مع MongoDB
✅ طباعة الفواتير بصيغة PDF

---
© 2025 Sky Wave - All Rights Reserved
"""
        
        with open(dist_folder / 'README.txt', 'w', encoding='utf-8') as f:
            f.write(readme_content)
        print("  ✅ تم إنشاء README.txt")
        
        print("\n" + "=" * 80)
        print("🎉 البرنامج جاهز!")
        print("=" * 80)
        print(f"\n📂 المجلد: dist/SkyWaveERP/")
        print(f"🚀 الملف: SkyWaveERP.exe")
        print(f"\n💡 لتشغيل البرنامج:")
        print(f"   cd dist/SkyWaveERP")
        print(f"   SkyWaveERP.exe")
        print("\n" + "=" * 80)
        
    else:
        print("\n❌ لم يتم العثور على الملف التنفيذي")
else:
    print("\n❌ فشل بناء EXE")
    print("⚠️ راجع الأخطاء أعلاه")
