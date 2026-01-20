#!/usr/bin/env python3
"""
مراقب النظام المباشر - يتابع البرنامج أثناء التشغيل
"""

import sys
import os
import time
import threading
import psutil
from datetime import datetime

def monitor_process():
    """مراقبة عملية البرنامج"""
    print("🔍 مراقبة عملية Sky Wave ERP...")
    
    try:
        # البحث عن العملية
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            if 'SkyWaveERP' in proc.info['name']:
                pid = proc.info['pid']
                print(f"✅ تم العثور على العملية: PID {pid}")
                
                # مراقبة الأداء
                process = psutil.Process(pid)
                
                for i in range(10):  # مراقبة لمدة 10 ثوانٍ
                    cpu_percent = process.cpu_percent()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    threads_count = process.num_threads()
                    
                    print(f"  [{i+1}/10] CPU: {cpu_percent:.1f}% | Memory: {memory_mb:.1f}MB | Threads: {threads_count}")
                    time.sleep(1)
                
                return True
                
    except Exception as e:
        print(f"❌ خطأ في مراقبة العملية: {e}")
        return False
    
    print("⚠️ لم يتم العثور على عملية Sky Wave ERP")
    return False

def check_log_errors():
    """فحص الأخطاء في الـ logs"""
    print("\n📋 فحص الأخطاء في الـ logs...")
    
    log_path = r"C:\Users\h REDA\AppData\Local\SkyWaveERP\logs\skywave_erp.log"
    
    try:
        if not os.path.exists(log_path):
            print("⚠️ ملف الـ log غير موجود")
            return False
        
        # قراءة آخر 100 سطر
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            recent_lines = lines[-100:] if len(lines) > 100 else lines
        
        # البحث عن الأخطاء
        errors = []
        warnings = []
        
        for line in recent_lines:
            if 'ERROR' in line or 'CRITICAL' in line or 'Exception' in line:
                errors.append(line.strip())
            elif 'WARNING' in line or 'فشل' in line:
                warnings.append(line.strip())
        
        print(f"  🔴 أخطاء: {len(errors)}")
        for error in errors[-5:]:  # آخر 5 أخطاء
            print(f"    - {error}")
        
        print(f"  🟡 تحذيرات: {len(warnings)}")
        for warning in warnings[-3:]:  # آخر 3 تحذيرات
            print(f"    - {warning}")
        
        return len(errors) == 0
        
    except Exception as e:
        print(f"❌ خطأ في قراءة الـ log: {e}")
        return False

def test_database_operations():
    """اختبار عمليات قاعدة البيانات"""
    print("\n💾 اختبار عمليات قاعدة البيانات...")
    
    try:
        sys.path.insert(0, '.')
        from core.repository import Repository
        
        repo = Repository()
        
        # اختبار جلب العملاء
        clients = repo.get_all_clients()
        print(f"  ✅ تم جلب {len(clients)} عميل")
        
        # اختبار عملاء VIP
        vip_clients = [c for c in clients if getattr(c, 'is_vip', False)]
        print(f"  ⭐ عملاء VIP: {len(vip_clients)}")
        
        # اختبار جلب المشاريع
        projects = repo.get_all_projects()
        print(f"  📁 تم جلب {len(projects)} مشروع")
        
        # اختبار جلب الخدمات
        services = repo.get_all_services()
        print(f"  🛠️ تم جلب {len(services)} خدمة")
        
        return True
        
    except Exception as e:
        print(f"  ❌ خطأ في قاعدة البيانات: {e}")
        return False

def test_threading_safety():
    """اختبار أمان الـ Threading"""
    print("\n🧵 اختبار أمان الـ Threading...")
    
    results = []
    errors = []
    
    def worker(worker_id):
        try:
            import sqlite3
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

def check_critical_issues():
    """فحص المشاكل الحرجة"""
    print("\n🚨 فحص المشاكل الحرجة...")
    
    issues = []
    
    # فحص daemon threads
    try:
        import threading
        active_threads = threading.active_count()
        print(f"  🧵 عدد الـ threads النشطة: {active_threads}")
        
        if active_threads > 10:
            issues.append(f"عدد كبير من الـ threads: {active_threads}")
    except Exception as e:
        issues.append(f"فشل فحص الـ threads: {e}")
    
    # فحص استخدام الذاكرة
    try:
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            if 'SkyWaveERP' in proc.info['name']:
                memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                print(f"  💾 استخدام الذاكرة: {memory_mb:.1f}MB")
                
                if memory_mb > 500:  # أكثر من 500MB
                    issues.append(f"استخدام ذاكرة عالي: {memory_mb:.1f}MB")
    except Exception as e:
        issues.append(f"فشل فحص الذاكرة: {e}")
    
    # فحص ملفات قاعدة البيانات
    db_files = ['skywave_local.db', 'skywave_local.db-wal', 'skywave_local.db-shm']
    for db_file in db_files:
        if os.path.exists(db_file):
            size_mb = os.path.getsize(db_file) / 1024 / 1024
            print(f"  📊 {db_file}: {size_mb:.1f}MB")
        else:
            print(f"  ⚠️ {db_file}: غير موجود")
    
    print(f"  🔍 مشاكل مكتشفة: {len(issues)}")
    for issue in issues:
        print(f"    - {issue}")
    
    return len(issues) == 0

def main():
    """الدالة الرئيسية للمراقبة"""
    print("🚀 بدء مراقبة النظام المباشرة")
    print("=" * 50)
    
    tests = [
        ("مراقبة العملية", monitor_process),
        ("فحص الـ logs", check_log_errors),
        ("عمليات قاعدة البيانات", test_database_operations),
        ("أمان الـ Threading", test_threading_safety),
        ("المشاكل الحرجة", check_critical_issues)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            print(f"\n🔧 {test_name}...")
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ فشل {test_name}: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 50)
    print("📊 ملخص المراقبة:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ سليم" if result else "❌ مشكلة"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nالنتيجة: {passed}/{total} اختبار سليم")
    
    if passed == total:
        print("🎉 النظام يعمل بشكل ممتاز!")
    elif passed >= total * 0.8:
        print("⚠️ النظام يعمل جيداً مع بعض المشاكل البسيطة")
    else:
        print("🚨 هناك مشاكل تحتاج انتباه!")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)