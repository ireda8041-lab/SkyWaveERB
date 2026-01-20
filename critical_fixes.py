#!/usr/bin/env python3
"""
إصلاحات حرجة لنظام Sky Wave ERP
يصلح المشاكل الأكثر خطورة المذكورة في التحليل
"""

import os
import sys
import shutil
from datetime import datetime

def backup_file(file_path):
    """إنشاء نسخة احتياطية من الملف"""
    if os.path.exists(file_path):
        backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(file_path, backup_path)
        print(f"✅ تم إنشاء نسخة احتياطية: {backup_path}")
        return backup_path
    return None

def fix_error_handler():
    """إصلاح معالج الأخطاء في main.py"""
    print("🔧 إصلاح معالج الأخطاء...")
    
    file_path = "main.py"
    backup_backup_file(file_path)
    
    # قراءة الملف الحالي
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # البحث عن معالج الأخطاء القديم
    old_handler = '''def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """معالج الأخطاء غير المتوقعة - محسّن لمنع الإغلاق المفاجئ"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # تجاهل كل الأخطاء غير الحرجة - لا نريد إغلاق البرنامج أبداً
    error_msg = str(exc_value).lower() if exc_value else ""

    # قائمة الأخطاء التي يجب تجاهلها
    ignore_patterns = [
        "deleted", "c/c++ object", "wrapped c/c++", "runtime", "qobject", "destroyed", "invalid",
        "connection", "timeout", "network", "socket", "pymongo", "mongo", "serverselection", "autoreconnect",
        "thread", "daemon", "join", "queue", "lock", "semaphore",
        "database is locked", "disk i/o error", "busy", "closed database", "closed cursor",
        "truth value", "bool()", "nonetype", "attributeerror"
    ]

    if any(x in error_msg for x in ignore_patterns):
        logger.debug(f"تجاهل خطأ: {exc_value}")
        return

    logger.warning(f"خطأ غير متوقع (تم تجاهله): {exc_value}")
    # لا نُغلق البرنامج أبداً'''
    
    # المعالج الجديد المحسّن
    new_handler = '''def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """معالج الأخطاء غير المتوقعة - محسّن وآمن"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # تسجيل الخطأ بشكل صحيح
    logger.error(f"خطأ غير متوقع: {exc_type.__name__}: {exc_value}", 
                 exc_info=(exc_type, exc_value, exc_traceback))
    
    # أخطاء Qt التي يمكن تجاهلها بأمان
    error_msg = str(exc_value).lower() if exc_value else ""
    safe_to_ignore = [
        "wrapped c/c++ object", "deleted", "destroyed", 
        "qobject", "runtime error", "c/c++ object"
    ]
    
    # تجاهل أخطاء Qt فقط
    if any(pattern in error_msg for pattern in safe_to_ignore):
        logger.debug(f"تجاهل خطأ Qt: {exc_value}")
        return
    
    # للأخطاء الأخرى، نسجلها ونعرضها للمستخدم
    try:
        from core.error_handler import ErrorHandler
        ErrorHandler.handle_exception(
            exception=exc_value,
            context="uncaught_exception",
            user_message=f"حدث خطأ غير متوقع: {exc_value}",
            show_dialog=False  # لا نعرض dialog لتجنب التعطل
        )
    except Exception:
        # إذا فشل ErrorHandler، نطبع الخطأ على الأقل
        print(f"خطأ حرج: {exc_value}")'''
    
    # استبدال المعالج القديم
    if old_handler in content:
        content = content.replace(old_handler, new_handler)
        
        # كتابة الملف المحدث
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ تم إصلاح معالج الأخطاء")
        return True
    else:
        print("⚠️ لم يتم العثور على معالج الأخطاء القديم")
        return False

def fix_thread_handler():
    """إصلاح معالج أخطاء الـ Threads"""
    print("🔧 إصلاح معالج أخطاء الـ Threads...")
    
    file_path = "main.py"
    
    # قراءة الملف الحالي
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # البحث عن معالج الـ threads القديم
    old_thread_handler = '''def handle_thread_exception(args):
    """معالج أخطاء الـ Threads - يمنع إغلاق البرنامج"""
    # تجاهل كل أخطاء الـ threads - لا نريد إغلاق البرنامج أبداً
    pass'''
    
    # المعالج الجديد المحسّن
    new_thread_handler = '''def handle_thread_exception(args):
    """معالج أخطاء الـ Threads - محسّن وآمن"""
    try:
        exc_type = args.exc_type
        exc_value = args.exc_value
        exc_traceback = args.exc_traceback
        thread = args.thread
        
        # تسجيل خطأ الـ thread
        logger.error(f"خطأ في Thread '{thread.name}': {exc_type.__name__}: {exc_value}",
                     exc_info=(exc_type, exc_value, exc_traceback))
        
        # محاولة معالجة الخطأ
        try:
            from core.error_handler import ErrorHandler
            ErrorHandler.handle_exception(
                exception=exc_value,
                context=f"thread_{thread.name}",
                user_message=f"حدث خطأ في العملية الخلفية: {exc_value}",
                show_dialog=False
            )
        except Exception:
            print(f"خطأ في Thread {thread.name}: {exc_value}")
            
    except Exception as e:
        logger.error(f"فشل معالجة خطأ Thread: {e}")'''
    
    # استبدال المعالج القديم
    if old_thread_handler in content:
        content = content.replace(old_thread_handler, new_thread_handler)
        
        # كتابة الملف المحدث
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ تم إصلاح معالج أخطاء الـ Threads")
        return True
    else:
        print("⚠️ لم يتم العثور على معالج أخطاء الـ Threads القديم")
        return False

def create_cursor_context_manager():
    """إنشاء context manager للـ cursors"""
    print("🔧 إنشاء context manager للـ cursors...")
    
    cursor_manager_code = '''"""
Context Manager للـ Database Cursors
يضمن إغلاق الـ cursors بشكل صحيح
"""

class CursorContext:
    """Context manager لإدارة cursors بشكل آمن"""
    
    def __init__(self, repo):
        self.repo = repo
        self.cursor = None
    
    def __enter__(self):
        """فتح cursor جديد"""
        try:
            self.cursor = self.repo.get_cursor()
            return self.cursor
        except Exception as e:
            if self.cursor:
                try:
                    self.cursor.close()
                except Exception:
                    pass
            raise e
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """إغلاق الـ cursor تلقائياً"""
        if self.cursor:
            try:
                self.cursor.close()
            except Exception as e:
                # تسجيل الخطأ لكن لا نرفع استثناء
                try:
                    from core.logger import logger
                    logger.warning(f"فشل إغلاق cursor: {e}")
                except Exception:
                    print(f"فشل إغلاق cursor: {e}")
        
        # لا نمنع انتشار الاستثناءات الأصلية
        return False

def get_cursor_context(repo):
    """دالة مساعدة لإنشاء cursor context"""
    return CursorContext(repo)

# مثال على الاستخدام:
# with get_cursor_context(self.repo) as cursor:
#     cursor.execute("SELECT * FROM clients")
#     results = cursor.fetchall()
# # يتم إغلاق الـ cursor تلقائياً
'''
    
    # كتابة الملف
    with open("core/cursor_manager.py", 'w', encoding='utf-8') as f:
        f.write(cursor_manager_code)
    
    print("✅ تم إنشاء cursor context manager")
    return True

def create_thread_safety_guide():
    """إنشاء دليل أمان الـ Threads"""
    print("🔧 إنشاء دليل أمان الـ Threads...")
    
    guide_content = '''# دليل أمان الـ Threads في Sky Wave ERP

## المشاكل الحالية

### 1. Daemon Threads بدون انتظار
```python
# ❌ خطأ - قد تُقطع في منتصف العملية
thread = threading.Thread(target=some_function, daemon=True)
thread.start()  # لا ننتظر انتهاء العملية!
```

### 2. الحل الصحيح - استخدام QThread
```python
# ✅ صحيح - استخدام QThread
from PyQt6.QtCore import QThread, QObject, pyqtSignal

class Worker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def run(self):
        try:
            # تنفيذ العملية
            some_function()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

# الاستخدام:
worker = Worker()
thread = QThread()
worker.moveToThread(thread)

# ربط الإشارات
thread.started.connect(worker.run)
worker.finished.connect(thread.quit)
worker.finished.connect(worker.deleteLater)
thread.finished.connect(thread.deleteLater)

# بدء التشغيل
thread.start()
```

### 3. للعمليات الدورية - استخدام QTimer
```python
# ✅ صحيح - للعمليات الدورية
from PyQt6.QtCore import QTimer

def setup_periodic_task():
    timer = QTimer()
    timer.timeout.connect(some_periodic_function)
    timer.start(60000)  # كل دقيقة
    return timer
```

## قائمة الملفات التي تحتاج إصلاح:

1. **main.py** - daemon threads للصيانة والتحديثات
2. **ui/main_window.py** - daemon threads للمزامنة
3. **core/unified_sync.py** - daemon threads للمزامنة التلقائية
4. **core/repository.py** - daemon threads لـ MongoDB
5. **updater.py** - daemon thread للتحديث

## خطة الإصلاح:

### المرحلة 1: إصلاح الـ Threads الحرجة
- [ ] main.py - maintenance_thread
- [ ] main.py - settings_thread  
- [ ] main.py - update_thread
- [ ] ui/main_window.py - sync threads

### المرحلة 2: إصلاح باقي الـ Threads
- [ ] core/unified_sync.py
- [ ] core/repository.py
- [ ] updater.py

### المرحلة 3: اختبار الإصلاحات
- [ ] اختبار عدم تعطل البرنامج
- [ ] اختبار إكمال العمليات
- [ ] اختبار الأداء
'''
    
    with open("THREAD_SAFETY_GUIDE.md", 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    print("✅ تم إنشاء دليل أمان الـ Threads")
    return True

def create_vip_test_script():
    """إنشاء سكريبت اختبار VIP"""
    print("🔧 إنشاء سكريبت اختبار VIP...")
    
    vip_test_code = '''#!/usr/bin/env python3
"""
اختبار شامل لوظائف VIP في Sky Wave ERP
"""

import sys
import os

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_vip_database():
    """اختبار VIP في قاعدة البيانات"""
    print("🔍 اختبار VIP في قاعدة البيانات...")
    
    try:
        from core.repository import Repository
        from core.schemas import Client, ClientStatus
        
        repo = Repository()
        
        # جلب جميع العملاء
        all_clients = repo.get_all_clients()
        print(f"  📊 إجمالي العملاء: {len(all_clients)}")
        
        # فلترة عملاء VIP
        vip_clients = [c for c in all_clients if getattr(c, 'is_vip', False)]
        print(f"  ⭐ عملاء VIP: {len(vip_clients)}")
        
        # عرض تفاصيل عملاء VIP
        for i, vip in enumerate(vip_clients[:5], 1):
            print(f"    {i}. {vip.name} (ID: {vip.id})")
        
        return len(vip_clients) > 0
        
    except Exception as e:
        print(f"  ❌ خطأ: {e}")
        return False

def test_vip_ui_logic():
    """اختبار منطق VIP في الواجهة"""
    print("\\n🎨 اختبار منطق VIP في الواجهة...")
    
    try:
        # محاكاة عميل VIP
        class MockClient:
            def __init__(self, name, is_vip=False):
                self.id = 1
                self.name = name
                self.is_vip = is_vip
                self.email = "test@example.com"
                self.company_name = "Test Company"
                self.phone = "123456789"
        
        # اختبار العميل العادي
        regular_client = MockClient("عميل عادي", False)
        is_vip_regular = getattr(regular_client, 'is_vip', False)
        print(f"  👤 عميل عادي - VIP: {is_vip_regular}")
        
        # اختبار عميل VIP
        vip_client = MockClient("عميل VIP", True)
        is_vip_premium = getattr(vip_client, 'is_vip', False)
        print(f"  ⭐ عميل VIP - VIP: {is_vip_premium}")
        
        # اختبار النص المعروض
        regular_name = f"⭐ {regular_client.name}" if is_vip_regular else regular_client.name
        vip_name = f"⭐ {vip_client.name}" if is_vip_premium else vip_client.name
        
        print(f"  📝 نص العميل العادي: '{regular_name}'")
        print(f"  📝 نص عميل VIP: '{vip_name}'")
        
        return is_vip_premium and not is_vip_regular
        
    except Exception as e:
        print(f"  ❌ خطأ: {e}")
        return False

def test_vip_creation():
    """اختبار إنشاء عميل VIP جديد"""
    print("\\n➕ اختبار إنشاء عميل VIP جديد...")
    
    try:
        from core.repository import Repository
        from core.schemas import Client, ClientStatus
        from datetime import datetime
        
        repo = Repository()
        
        # إنشاء عميل VIP جديد
        test_client = Client(
            name=f"عميل اختبار VIP {datetime.now().strftime('%H%M%S')}",
            email="vip_test@example.com",
            company_name="شركة اختبار VIP",
            phone="01234567890",
            status=ClientStatus.ACTIVE,
            is_vip=True
        )
        
        # حفظ العميل
        saved_client = repo.create_client(test_client)
        print(f"  ✅ تم إنشاء عميل VIP: {saved_client.name} (ID: {saved_client.id})")
        
        # التحقق من حفظ حالة VIP
        retrieved_client = repo.get_client_by_id(saved_client.id)
        if retrieved_client and getattr(retrieved_client, 'is_vip', False):
            print(f"  ✅ تم حفظ حالة VIP بنجاح")
            return True
        else:
            print(f"  ❌ فشل حفظ حالة VIP")
            return False
            
    except Exception as e:
        print(f"  ❌ خطأ: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    print("🚀 اختبار شامل لوظائف VIP")
    print("=" * 40)
    
    tests = [
        ("قاعدة البيانات", test_vip_database),
        ("منطق الواجهة", test_vip_ui_logic),
        ("إنشاء VIP جديد", test_vip_creation)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ فشل اختبار {test_name}: {e}")
            results[test_name] = False
    
    print("\\n" + "=" * 40)
    print("📊 ملخص النتائج:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ نجح" if result else "❌ فشل"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\\nالنتيجة: {passed}/{total} اختبار نجح")
    
    if passed == total:
        print("🎉 جميع اختبارات VIP نجحت!")
    else:
        print("⚠️ هناك مشاكل في وظائف VIP تحتاج إصلاح")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
'''
    
    with open("test_vip_functionality.py", 'w', encoding='utf-8') as f:
        f.write(vip_test_code)
    
    print("✅ تم إنشاء سكريبت اختبار VIP")
    return True

def main():
    """تطبيق جميع الإصلاحات الحرجة"""
    print("🚀 بدء تطبيق الإصلاحات الحرجة لـ Sky Wave ERP")
    print("=" * 60)
    
    fixes = [
        ("إصلاح معالج الأخطاء", fix_error_handler),
        ("إصلاح معالج أخطاء الـ Threads", fix_thread_handler),
        ("إنشاء cursor context manager", create_cursor_context_manager),
        ("إنشاء دليل أمان الـ Threads", create_thread_safety_guide),
        ("إنشاء سكريبت اختبار VIP", create_vip_test_script)
    ]
    
    results = {}
    
    for fix_name, fix_func in fixes:
        try:
            print(f"\\n🔧 {fix_name}...")
            result = fix_func()
            results[fix_name] = result
        except Exception as e:
            print(f"❌ فشل {fix_name}: {e}")
            results[fix_name] = False
    
    print("\\n" + "=" * 60)
    print("📊 ملخص الإصلاحات:")
    
    applied = 0
    total = len(results)
    
    for fix_name, result in results.items():
        status = "✅ تم" if result else "❌ فشل"
        print(f"  {fix_name}: {status}")
        if result:
            applied += 1
    
    print(f"\\nالنتيجة: {applied}/{total} إصلاح تم تطبيقه")
    
    if applied == total:
        print("🎉 تم تطبيق جميع الإصلاحات الحرجة بنجاح!")
        print("\\n📋 الخطوات التالية:")
        print("  1. اختبر البرنامج للتأكد من عمله")
        print("  2. شغل test_vip_functionality.py لاختبار VIP")
        print("  3. راجع THREAD_SAFETY_GUIDE.md لإصلاح الـ threads")
        print("  4. استخدم core/cursor_manager.py في الكود الجديد")
    else:
        print("⚠️ بعض الإصلاحات فشلت. راجع الأخطاء أعلاه.")
    
    return applied == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)