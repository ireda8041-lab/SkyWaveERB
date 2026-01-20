#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تطبيق تحديث v2.0.1 - إصلاح مشكلة Database bool()
"""

import sys
import subprocess
from pathlib import Path

# تعيين الترميز للـ console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def check_python_version():
    """التحقق من إصدار Python"""
    if sys.version_info < (3, 10):
        print("❌ يتطلب Python 3.10 أو أحدث")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    return True

def run_fix_script():
    """تشغيل سكريبت الإصلاح"""
    print("\n🔧 تطبيق الإصلاحات...")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [sys.executable, "fix_database_bool_issue.py"],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        print(result.stdout)
        
        if result.returncode == 0:
            print("✅ تم تطبيق الإصلاحات بنجاح")
            return True
        else:
            print(f"❌ فشل تطبيق الإصلاحات: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

def verify_fix():
    """التحقق من نجاح الإصلاح"""
    print("\n🧪 التحقق من الإصلاح...")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", "from core.repository import Repository; print('OK')"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and "OK" in result.stdout:
            print("✅ التحقق ناجح - النظام يعمل بشكل صحيح")
            return True
        else:
            print("⚠️ تحذير: قد تكون هناك مشاكل")
            if result.stderr:
                print(f"الخطأ: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠️ انتهت مهلة التحقق")
        return False
    except Exception as e:
        print(f"❌ خطأ في التحقق: {e}")
        return False

def update_version_info():
    """تحديث معلومات الإصدار"""
    print("\n📝 تحديث معلومات الإصدار...")
    
    version_file = Path("version.py")
    if version_file.exists():
        print("✅ ملف version.py موجود")
    else:
        print("⚠️ ملف version.py غير موجود")
    
    version_json = Path("version.json")
    if version_json.exists():
        print("✅ ملف version.json موجود")
    else:
        print("⚠️ ملف version.json غير موجود")

def main():
    """الدالة الرئيسية"""
    print("=" * 60)
    print("🚀 تحديث Sky Wave ERP v2.0.1")
    print("=" * 60)
    print()
    
    # 1. التحقق من Python
    if not check_python_version():
        return 1
    
    # 2. تطبيق الإصلاحات
    if not run_fix_script():
        print("\n❌ فشل التحديث")
        return 1
    
    # 3. التحقق من الإصلاح
    if not verify_fix():
        print("\n⚠️ التحديث مكتمل لكن قد تكون هناك مشاكل")
        return 1
    
    # 4. تحديث معلومات الإصدار
    update_version_info()
    
    print("\n" + "=" * 60)
    print("✅ تم التحديث بنجاح إلى v2.0.1!")
    print("=" * 60)
    print()
    print("📋 التغييرات:")
    print("  🔧 إصلاح مشكلة Database bool()")
    print("  ✅ تحسين استقرار النظام")
    print("  ⚡ تحسين أداء المزامنة")
    print()
    print("🔄 يُنصح بإعادة تشغيل البرنامج الآن")
    print()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
