#!/usr/bin/env python3
"""
🔍 Sky Wave ERP - Project Checker
فحص شامل للمشروع قبل النشر
"""

import os
import sys
from pathlib import Path

# الألوان
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{CYAN}{'='*50}{RESET}")
    print(f"{CYAN}{text:^50}{RESET}")
    print(f"{CYAN}{'='*50}{RESET}\n")

def check_file(filepath, required=True):
    """فحص وجود ملف"""
    exists = Path(filepath).exists()
    status = f"{GREEN}✅{RESET}" if exists else f"{RED}❌{RESET}"
    req = "مطلوب" if required else "اختياري"
    print(f"{status} {filepath} ({req})")
    return exists

def check_import(module_name):
    """فحص استيراد مكتبة"""
    try:
        __import__(module_name)
        print(f"{GREEN}✅{RESET} {module_name}")
        return True
    except ImportError as e:
        print(f"{RED}❌{RESET} {module_name}: {e}")
        return False

def main():
    print_header("Sky Wave ERP - Project Checker v2.0.0")
    
    all_ok = True
    
    # 1. فحص الملفات الأساسية
    print_header("1. الملفات الأساسية")
    required_files = [
        "main.py",
        "requirements.txt",
        "pyproject.toml",
        "version.py",
        "version.json",
        "README.md",
        "LICENSE",
        ".gitignore",
    ]
    
    for file in required_files:
        if not check_file(file, required=True):
            all_ok = False
    
    # 2. فحص المجلدات
    print_header("2. المجلدات الأساسية")
    required_dirs = [
        "core",
        "services",
        "ui",
        "assets",
        "tests",
    ]
    
    for dir in required_dirs:
        if not check_file(dir, required=True):
            all_ok = False

    
    # 3. فحص المكتبات المطلوبة
    print_header("3. المكتبات المطلوبة")
    required_modules = [
        "PyQt6",
        "pymongo",
        "reportlab",
        "pandas",
        "openpyxl",
        "jinja2",
        "arabic_reshaper",
        "bidi",
        "pydantic",
        "requests",
    ]
    
    for module in required_modules:
        if not check_import(module):
            all_ok = False
    
    # 4. فحص ملفات التوثيق
    print_header("4. ملفات التوثيق")
    doc_files = [
        "CHANGELOG.md",
        "BUILD_GUIDE.md",
        "GIT_SETUP.md",
        ".env.example",
    ]
    
    for file in doc_files:
        check_file(file, required=False)
    
    # 5. فحص ملفات البناء
    print_header("5. ملفات البناء")
    build_files = [
        "SkyWaveERP.spec",
        "build_exe.ps1",
    ]
    
    for file in build_files:
        check_file(file, required=False)
    
    # 6. فحص رقم الإصدار
    print_header("6. رقم الإصدار")
    try:
        from version import CURRENT_VERSION
        print(f"{GREEN}✅{RESET} الإصدار الحالي: {CURRENT_VERSION}")
        
        # التحقق من تطابق الإصدارات
        import json
        with open("version.json", "r", encoding="utf-8") as f:
            version_data = json.load(f)
            if version_data.get("version") == CURRENT_VERSION:
                print(f"{GREEN}✅{RESET} version.json متطابق")
            else:
                print(f"{RED}❌{RESET} version.json غير متطابق!")
                all_ok = False
    except Exception as e:
        print(f"{RED}❌{RESET} خطأ في فحص الإصدار: {e}")
        all_ok = False
    
    # النتيجة النهائية
    print_header("النتيجة النهائية")
    if all_ok:
        print(f"{GREEN}✅ المشروع جاهز للنشر!{RESET}")
        return 0
    else:
        print(f"{RED}❌ يوجد مشاكل يجب حلها قبل النشر!{RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
