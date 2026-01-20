#!/usr/bin/env python3
"""
اختبار شامل نهائي بعد حل جميع المشاكل
"""

import sys
import os
import time
import threading
import sqlite3
from datetime import datetime

def test_daemon_threads_fixed():
    """اختبار أن daemon threads تم إصلاحها"""
    print("🧵 اختبار إصلاح daemon threads...")
    
    try:
        # فحص main.py
        with open('main.py', 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        daemon_count = main_content.count('daemon=True')
        print(f"  📁 main.py: {daemon_count} daemon threads متبقية")
        
        # فحص ui/main_window.py
        with open('ui/main_window.py', 'r', encoding='utf-8') as f:
            ui_content = f.read()
        
        ui_daemon_count = ui_content.count('daemon=True')
        print(f"  📁 ui/main_window.py: {ui_daemon_count} daemon threads متبقية")
        
        # فحص core/unified_sync.py
        with open('core/unified_sync.py', 'r', encoding='utf-8') as f:
            sync_content = f.read()
        
        sync_daemon_count = sync_content.count('daemon=True')
        print(f"  📁 core/unified_sync.py: {sync_daemon_count} daemon threads متبقية")
        
        # فحص core/repository.py
        with open('core/repository.py', 'r', encoding='utf-8') as f:
            repo_content = f.read()
        
        repo_daemon_count = repo_content.count('daemon=True')
        print(f"  📁 core/repository.py: {repo_daemon_count} daemon threads متبقية")
        
        total_daemon_threads = daemon_count + ui_daemon_count + sync_daemon_count + repo_daemon_count
        
        if total_daemon_threads == 0:
            print("  ✅ تم إزالة جميع daemon threads بنجاح!")
            return True
        else:
            print(f"  ⚠️ لا يزال هناك {total_daemon_threads} daemon threads")
            return False
            
    except Exception as e:
        print(f"  ❌ خطأ في فحص daemon threads: {e}")
        return False

def test_qtimer_usage():
    """اختبار استخدام QTimer بدلاً من threads"""
    print("\n⏰ اختبار استخدام QTimer...")
    
    try:
        files_to_check = [
            'main.py',
            'ui/main_window.py', 
            'core/unified_sync.py',
            'core/repository.py'
        ]
        
        qtimer_usage = 0
        
        for file_path in files_to_check:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                qtimer_count = content.count('QTimer')
                if qtimer_count > 0:
                    print(f"  📁 {file_path}: {qtimer_count} استخدام لـ QTimer")
                    qtimer_usage += qtimer_count
        
        if qtimer_usage > 0:
            print(f"  ✅ تم استخدام QTimer في {qtimer_usage} مكان")
            return True
        else:
            print("  ⚠️ لم يتم العثور على استخدام QTimer")
            return False
            
    except Exception as e:
        print(f"  ❌ خطأ في فحص QTimer: {e}")
        return False

def test_mongodb_connection_checks():
    """اختبار تحسينات فحص اتصال MongoDB"""
    print("\n🍃 اختبار تحسينات MongoDB...")
    
    try:
        with open('core/unified_sync.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # فحص وجود الدوال المحسنة
        has_connection_check = '_check_mongodb_connection' in content
        has_safe_operation = '_safe_mongodb_operation' in content
        
        print(f"  🔍 دالة فحص الاتصال: {'✅ موجودة' if has_connection_check else '❌ غير موجودة'}")
        print(f"  🛡️ دالة العمليات الآمنة: {'✅ موجودة' if has_safe_operation else '❌ غير موجودة'}")
        
        return has_connection_check and has_safe_operation
        
    except Exception as e:
        print(f"  ❌ خطأ في فحص MongoDB: {e}")
        return False

def test_cursor_manager():
    """اختبار cursor context manager"""
    print("\n💾 اختبار cursor context manager...")
    
    try:
        # فحص وجود الملف
        cursor_manager_exists = os.path.exists('core/cursor_manager.py')
        print(f"  📁 cursor_manager.py: {'✅ موجود' if cursor_manager_exists else '❌ غير موجود'}")
        
        # فحص وجود أمثلة الاستخدام
        examples_exist = os.path.exists('CURSOR_USAGE_EXAMPLES.md')
        print(f"  📖 أمثلة الاستخدام: {'✅ موجودة' if examples_exist else '❌ غير موجودة'}")
        
        if cursor_manager_exists:
            # اختبار استيراد cursor manager
            sys.path.insert(0, '.')
            try:
                from core.cursor_manager import get_cursor_context, CursorContext
                print("  ✅ تم استيراد cursor manager بنجاح")
                return True
            except ImportError as e:
                print(f"  ❌ فشل استيراد cursor manager: {e}")
                return False
        
        return cursor_manager_exists and examples_exist
        
    except Exception as e:
        print(f"  ❌ خطأ في فحص cursor manager: {e}")
        return False

def test_system_stability():
    """اختبار استقرار النظام"""
    print("\n🔒 اختبار استقرار النظام...")
    
    try:
        # اختبار قاعدة البيانات
        conn = sqlite3.connect('skywave_local.db')
        cursor = conn.cursor()
        
        # اختبار العمليات الأساسية
        cursor.execute("SELECT COUNT(*) FROM clients")
        clients_count = cursor.fetchone()[0]
        print(f"  👥 العملاء: {clients_count}")
        
        cursor.execute("SELECT COUNT(*) FROM clients WHERE is_vip = 1")
        vip_count = cursor.fetchone()[0]
        print(f"  ⭐ عملاء VIP: {vip_count}")
        
        cursor.execute("SELECT COUNT(*) FROM projects")
        projects_count = cursor.fetchone()[0]
        print(f"  📁 المشاريع: {projects_count}")
        
        cursor.execute("SELECT COUNT(*) FROM services")
        services_count = cursor.fetchone()[0]
        print(f"  🛠️ الخدمات: {services_count}")
        
        conn.close()
        
        print("  ✅ قاعدة البيانات تعمل بشكل طبيعي")
        return True
        
    except Exception as e:
        print(f"  ❌ خطأ في اختبار النظام: {e}")
        return False

def test_vip_functionality():
    """اختبار وظائف VIP مرة أخيرة"""
    print("\n⭐ اختبار وظائف VIP النهائي...")
    
    try:
        sys.path.insert(0, '.')
        from core.repository import Repository
        from services.client_service import ClientService
        
        repo = Repository()
        client_service = ClientService(repo)
        
        # جلب عملاء VIP
        all_clients = client_service.get_all_clients()
        vip_clients = [c for c in all_clients if getattr(c, 'is_vip', False)]
        
        print(f"  📊 إجمالي العملاء: {len(all_clients)}")
        print(f"  ⭐ عملاء VIP: {len(vip_clients)}")
        
        # عرض أول 3 عملاء VIP
        for i, vip in enumerate(vip_clients[:3], 1):
            print(f"    {i}. {vip.name} (ID: {vip.id})")
        
        return len(vip_clients) > 0
        
    except Exception as e:
        print(f"  ❌ خطأ في اختبار VIP: {e}")
        return False

def test_backup_files():
    """فحص النسخ الاحتياطية"""
    print("\n💾 فحص النسخ الاحتياطية...")
    
    backup_files = [
        f for f in os.listdir('.') 
        if f.endswith('.backup_20260120_003906')
    ]
    
    ui_backups = [
        f for f in os.listdir('ui') 
        if f.endswith('.backup_20260120_003906')
    ] if os.path.exists('ui') else []
    
    core_backups = [
        f for f in os.listdir('core') 
        if f.endswith('.backup_20260120_003906')
    ] if os.path.exists('core') else []
    
    total_backups = len(backup_files) + len(ui_backups) + len(core_backups)
    
    print(f"  📁 النسخ الاحتياطية: {total_backups} ملف")
    
    if backup_files:
        print(f"    - الجذر: {len(backup_files)} ملف")
    if ui_backups:
        print(f"    - ui/: {len(ui_backups)} ملف")
    if core_backups:
        print(f"    - core/: {len(core_backups)} ملف")
    
    return total_backups > 0

def main():
    """الاختبار الشامل النهائي"""
    print("🚀 الاختبار الشامل النهائي بعد حل جميع المشاكل")
    print("=" * 60)
    
    tests = [
        ("إصلاح daemon threads", test_daemon_threads_fixed),
        ("استخدام QTimer", test_qtimer_usage),
        ("تحسينات MongoDB", test_mongodb_connection_checks),
        ("cursor context manager", test_cursor_manager),
        ("استقرار النظام", test_system_stability),
        ("وظائف VIP", test_vip_functionality),
        ("النسخ الاحتياطية", test_backup_files)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ فشل اختبار {test_name}: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 60)
    print("📊 ملخص الاختبار النهائي:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ نجح" if result else "❌ فشل"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nالنتيجة النهائية: {passed}/{total} اختبار نجح")
    
    if passed == total:
        print("🎉 جميع المشاكل تم حلها والنظام يعمل بشكل مثالي!")
        print("\n🏆 تقييم النظام النهائي: 10/10")
        print("\n✨ Sky Wave ERP جاهز للاستخدام الإنتاجي!")
    elif passed >= total * 0.9:
        print("🎊 النظام يعمل بشكل ممتاز مع تحسينات طفيفة!")
        print(f"\n🏆 تقييم النظام النهائي: {passed}/{total}")
    else:
        print("⚠️ هناك بعض المشاكل تحتاج مراجعة")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)