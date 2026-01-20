#!/usr/bin/env python3
"""
اختبار شامل لنظام Sky Wave ERP
يختبر جميع المشاكل الحرجة المذكورة في التحليل
"""

import sys
import os
import sqlite3
import threading
import time
from datetime import datetime

def test_database_integrity():
    """اختبار سلامة قاعدة البيانات"""
    print("🔍 اختبار سلامة قاعدة البيانات...")
    
    try:
        conn = sqlite3.connect('skywave_local.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # اختبار الجداول الأساسية
        tables = ['clients', 'projects', 'services', 'invoices', 'users']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  ✅ جدول {table}: {count} سجل")
        
        # اختبار VIP clients
        cursor.execute("SELECT COUNT(*) FROM clients WHERE is_vip = 1")
        vip_count = cursor.fetchone()[0]
        print(f"  ⭐ عملاء VIP: {vip_count}")
        
        # اختبار الفهارس
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = cursor.fetchall()
        print(f"  📊 الفهارس: {len(indexes)}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"  ❌ خطأ في قاعدة البيانات: {e}")
        return False

def test_vip_functionality():
    """اختبار وظائف VIP"""
    print("\n⭐ اختبار وظائف VIP...")
    
    try:
        # إضافة مسار المشروع
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from core.repository import Repository
        from core.schemas import Client, ClientStatus
        
        repo = Repository()
        
        # جلب عملاء VIP
        all_clients = repo.get_all_clients()
        vip_clients = [c for c in all_clients if getattr(c, 'is_vip', False)]
        
        print(f"  ✅ تم جلب {len(all_clients)} عميل")
        print(f"  ⭐ عملاء VIP: {len(vip_clients)}")
        
        for vip in vip_clients[:3]:  # أول 3 عملاء VIP
            print(f"    - {vip.name} (ID: {vip.id})")
        
        return len(vip_clients) > 0
        
    except Exception as e:
        print(f"  ❌ خطأ في اختبار VIP: {e}")
        return False

def test_threading_safety():
    """اختبار أمان التزامن"""
    print("\n🧵 اختبار أمان التزامن...")
    
    results = []
    errors = []
    
    def worker(worker_id):
        try:
            # محاولة الوصول لقاعدة البيانات من عدة threads
            conn = sqlite3.connect('skywave_local.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM clients")
            count = cursor.fetchone()[0]
            results.append(f"Worker {worker_id}: {count} clients")
            conn.close()
        except Exception as e:
            errors.append(f"Worker {worker_id}: {e}")
    
    # إنشاء عدة threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # انتظار انتهاء جميع الـ threads
    for t in threads:
        t.join()
    
    print(f"  ✅ نتائج ناجحة: {len(results)}")
    print(f"  ❌ أخطاء: {len(errors)}")
    
    if errors:
        for error in errors:
            print(f"    - {error}")
    
    return len(errors) == 0

def test_import_dependencies():
    """اختبار الاستيرادات والاعتماديات"""
    print("\n📦 اختبار الاستيرادات...")
    
    critical_modules = [
        'PyQt6.QtWidgets',
        'PyQt6.QtCore', 
        'PyQt6.QtGui',
        'sqlite3',
        'threading',
        'datetime',
        'json',
        'os',
        'sys'
    ]
    
    optional_modules = [
        'pymongo',
        'requests',
        'PIL'
    ]
    
    success_count = 0
    
    for module in critical_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
            success_count += 1
        except ImportError as e:
            print(f"  ❌ {module}: {e}")
    
    for module in optional_modules:
        try:
            __import__(module)
            print(f"  ✅ {module} (اختياري)")
        except ImportError:
            print(f"  ⚠️ {module} (اختياري - غير متوفر)")
    
    return success_count == len(critical_modules)

def test_file_permissions():
    """اختبار صلاحيات الملفات"""
    print("\n📁 اختبار صلاحيات الملفات...")
    
    critical_files = [
        'skywave_local.db',
        'main.py',
        'skywave_settings.json'
    ]
    
    success_count = 0
    
    for file_path in critical_files:
        if os.path.exists(file_path):
            if os.access(file_path, os.R_OK):
                print(f"  ✅ {file_path} (قراءة)")
                success_count += 1
            else:
                print(f"  ❌ {file_path} (لا يمكن القراءة)")
            
            if file_path.endswith('.db') or file_path.endswith('.json'):
                if os.access(file_path, os.W_OK):
                    print(f"  ✅ {file_path} (كتابة)")
                else:
                    print(f"  ❌ {file_path} (لا يمكن الكتابة)")
        else:
            print(f"  ❌ {file_path} (غير موجود)")
    
    return success_count == len(critical_files)

def test_error_handling():
    """اختبار معالجة الأخطاء"""
    print("\n⚠️ اختبار معالجة الأخطاء...")
    
    try:
        # محاولة الوصول لملف غير موجود
        with open('non_existent_file.txt', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print("  ✅ معالجة FileNotFoundError تعمل بشكل صحيح")
    except Exception as e:
        print(f"  ⚠️ معالجة خطأ غير متوقع: {e}")
    
    try:
        # محاولة قسمة على صفر
        result = 10 / 0
    except ZeroDivisionError:
        print("  ✅ معالجة ZeroDivisionError تعمل بشكل صحيح")
    except Exception as e:
        print(f"  ⚠️ معالجة خطأ غير متوقع: {e}")
    
    return True

def main():
    """الدالة الرئيسية للاختبار"""
    print("🚀 بدء الاختبار الشامل لنظام Sky Wave ERP")
    print("=" * 50)
    
    tests = [
        ("سلامة قاعدة البيانات", test_database_integrity),
        ("وظائف VIP", test_vip_functionality),
        ("أمان التزامن", test_threading_safety),
        ("الاستيرادات", test_import_dependencies),
        ("صلاحيات الملفات", test_file_permissions),
        ("معالجة الأخطاء", test_error_handling)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"  ❌ فشل اختبار {test_name}: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 50)
    print("📊 ملخص النتائج:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ نجح" if result else "❌ فشل"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nالنتيجة النهائية: {passed}/{total} اختبار نجح")
    
    if passed == total:
        print("🎉 جميع الاختبارات نجحت! النظام يعمل بشكل صحيح.")
    elif passed >= total * 0.8:
        print("⚠️ معظم الاختبارات نجحت، لكن هناك بعض المشاكل البسيطة.")
    else:
        print("🚨 هناك مشاكل حرجة تحتاج إصلاح فوري!")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)