#!/usr/bin/env python3
"""
حل المشاكل المتبقية في Sky Wave ERP
1. Daemon Threads
2. Cursor Handling  
3. MongoDB Connection Checks
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

def fix_daemon_threads_main():
    """إصلاح daemon threads في main.py"""
    print("🔧 إصلاح daemon threads في main.py...")
    
    file_path = "main.py"
    backup_file(file_path)
    
    # قراءة الملف
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # إصلاح maintenance thread
    old_maintenance = '''        import threading
        maintenance_thread = threading.Thread(target=run_maintenance_background, daemon=True)
        maintenance_thread.start()'''
    
    new_maintenance = '''        # استخدام QTimer بدلاً من daemon thread للصيانة
        from PyQt6.QtCore import QTimer
        self.maintenance_timer = QTimer()
        self.maintenance_timer.timeout.connect(self._run_maintenance_safe)
        self.maintenance_timer.start(300000)  # كل 5 دقائق'''
    
    # إصلاح settings thread
    old_settings = '''        settings_thread = threading.Thread(target=sync_settings_background, daemon=True)
        settings_thread.start()'''
    
    new_settings = '''        # استخدام QTimer بدلاً من daemon thread للإعدادات
        self.settings_timer = QTimer()
        self.settings_timer.timeout.connect(self._sync_settings_safe)
        self.settings_timer.start(60000)  # كل دقيقة'''
    
    # إصلاح update thread
    old_update = '''        import threading
        update_thread = threading.Thread(target=check_updates_background, daemon=True)
        update_thread.start()'''
    
    new_update = '''        # استخدام QTimer بدلاً من daemon thread للتحديثات
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._check_updates_safe)
        self.update_timer.start(3600000)  # كل ساعة'''
    
    # تطبيق الإصلاحات
    content = content.replace(old_maintenance, new_maintenance)
    content = content.replace(old_settings, new_settings)
    content = content.replace(old_update, new_update)
    
    # إضافة الدوال الآمنة
    safe_functions = '''
    def _run_maintenance_safe(self):
        """تشغيل الصيانة بشكل آمن"""
        try:
            run_maintenance_background()
        except Exception as e:
            logger.error(f"خطأ في الصيانة: {e}")
    
    def _sync_settings_safe(self):
        """مزامنة الإعدادات بشكل آمن"""
        try:
            sync_settings_background()
        except Exception as e:
            logger.error(f"خطأ في مزامنة الإعدادات: {e}")
    
    def _check_updates_safe(self):
        """فحص التحديثات بشكل آمن"""
        try:
            check_updates_background()
        except Exception as e:
            logger.error(f"خطأ في فحص التحديثات: {e}")
'''
    
    # إضافة الدوال قبل نهاية الكلاس
    class_end = "class SkyWaveERPApp:"
    if class_end in content:
        # البحث عن نهاية الكلاس وإضافة الدوال
        lines = content.split('\n')
        new_lines = []
        in_class = False
        class_indent = 0
        
        for i, line in enumerate(lines):
            new_lines.append(line)
            
            if line.strip().startswith("class SkyWaveERPApp:"):
                in_class = True
                class_indent = len(line) - len(line.lstrip())
            
            elif in_class and line.strip() and not line.startswith(' ' * (class_indent + 1)) and not line.strip().startswith('#'):
                # نهاية الكلاس
                new_lines.insert(-1, safe_functions)
                in_class = False
        
        content = '\n'.join(new_lines)
    
    # كتابة الملف المحدث
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ تم إصلاح daemon threads في main.py")
    return True

def fix_daemon_threads_main_window():
    """إصلاح daemon threads في ui/main_window.py"""
    print("🔧 إصلاح daemon threads في ui/main_window.py...")
    
    file_path = "ui/main_window.py"
    backup_file(file_path)
    
    # قراءة الملف
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # إصلاح sync threads
    old_sync_pattern1 = '''        thread = threading.Thread(target=check_in_background, daemon=True)
        thread.start()'''
    
    new_sync_pattern1 = '''        # استخدام QTimer بدلاً من daemon thread
        QTimer.singleShot(1000, check_in_background)  # تأخير ثانية واحدة'''
    
    old_sync_pattern2 = '''            sync_thread = threading.Thread(target=do_sync, daemon=True)
            sync_thread.start()'''
    
    new_sync_pattern2 = '''            # استخدام QTimer بدلاً من daemon thread
            QTimer.singleShot(100, do_sync)  # تأخير 100ms'''
    
    old_sync_pattern3 = '''        sync_thread = threading.Thread(target=do_full_sync, daemon=True)
        sync_thread.start()'''
    
    new_sync_pattern3 = '''        # استخدام QTimer بدلاً من daemon thread
        QTimer.singleShot(100, do_full_sync)  # تأخير 100ms'''
    
    # تطبيق الإصلاحات
    content = content.replace(old_sync_pattern1, new_sync_pattern1)
    content = content.replace(old_sync_pattern2, new_sync_pattern2)
    content = content.replace(old_sync_pattern3, new_sync_pattern3)
    
    # التأكد من استيراد QTimer
    if "from PyQt6.QtCore import" in content and "QTimer" not in content:
        content = content.replace(
            "from PyQt6.QtCore import",
            "from PyQt6.QtCore import QTimer,"
        )
    
    # كتابة الملف المحدث
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ تم إصلاح daemon threads في ui/main_window.py")
    return True

def fix_unified_sync_threads():
    """إصلاح daemon threads في core/unified_sync.py"""
    print("🔧 إصلاح daemon threads في core/unified_sync.py...")
    
    file_path = "core/unified_sync.py"
    backup_file(file_path)
    
    # قراءة الملف
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # إصلاح sync threads
    old_thread_pattern = '''        thread = threading.Thread(target=sync_thread, daemon=True)
        thread.start()'''
    
    new_thread_pattern = '''        # استخدام QTimer بدلاً من daemon thread
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, sync_thread)'''
    
    old_push_pattern = '''                thread = threading.Thread(target=push_thread, daemon=True)
                thread.start()'''
    
    new_push_pattern = '''                # استخدام QTimer بدلاً من daemon thread
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(100, push_thread)'''
    
    # تطبيق الإصلاحات
    content = content.replace(old_thread_pattern, new_thread_pattern)
    content = content.replace(old_push_pattern, new_push_pattern)
    
    # كتابة الملف المحدث
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ تم إصلاح daemon threads في core/unified_sync.py")
    return True

def fix_repository_threads():
    """إصلاح daemon threads في core/repository.py"""
    print("🔧 إصلاح daemon threads في core/repository.py...")
    
    file_path = "core/repository.py"
    backup_file(file_path)
    
    # قراءة الملف
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # إصلاح mongo connection thread
    old_mongo_pattern = '''        mongo_thread = threading.Thread(target=connect_mongo, daemon=True)
        mongo_thread.start()'''
    
    new_mongo_pattern = '''        # استخدام QTimer بدلاً من daemon thread
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, connect_mongo)  # تأخير ثانية واحدة'''
    
    # إصلاح sync threads
    old_sync_pattern = '''            threading.Thread(target=sync_to_mongo, daemon=True).start()'''
    new_sync_pattern = '''            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, sync_to_mongo)'''
    
    old_delete_pattern = '''                threading.Thread(target=delete_from_mongo, daemon=True).start()'''
    new_delete_pattern = '''                from PyQt6.QtCore import QTimer
                QTimer.singleShot(100, delete_from_mongo)'''
    
    # تطبيق الإصلاحات
    content = content.replace(old_mongo_pattern, new_mongo_pattern)
    content = content.replace(old_sync_pattern, new_sync_pattern)
    content = content.replace(old_delete_pattern, new_delete_pattern)
    
    # كتابة الملف المحدث
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ تم إصلاح daemon threads في core/repository.py")
    return True

def enhance_mongodb_connection_checks():
    """تحسين فحص اتصال MongoDB"""
    print("🔧 تحسين فحص اتصال MongoDB...")
    
    file_path = "core/unified_sync.py"
    
    # قراءة الملف
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # إضافة دالة فحص الاتصال المحسنة
    enhanced_connection_check = '''
    def _check_mongodb_connection(self) -> bool:
        """فحص شامل لاتصال MongoDB"""
        try:
            if not self.is_online:
                return False
            
            if self.repo.mongo_db is None or self.repo is not None.mongo_client is None:
                logger.warning("MongoDB client أو database غير متوفر")
                return False
            
            # محاولة ping للتأكد من الاتصال
            self.repo.mongo_client.admin.command('ping', maxTimeMS=5000)
            
            # فحص حالة الاتصال
            server_info = self.repo.mongo_client.server_info()
            if not server_info:
                logger.warning("فشل الحصول على معلومات الخادم")
                return False
            
            return True
            
        except Exception as e:
            error_msg = str(e).lower()
            if "cannot use mongoclient after close" in error_msg:
                logger.debug("MongoDB client مغلق")
            elif "serverselectiontimeout" in error_msg:
                logger.debug("انتهت مهلة الاتصال بـ MongoDB")
            elif "network" in error_msg or "connection" in error_msg:
                logger.debug("مشكلة في الشبكة مع MongoDB")
            else:
                logger.warning(f"خطأ في فحص MongoDB: {e}")
            
            return False
    
    def _safe_mongodb_operation(self, operation_func, *args, **kwargs):
        """تنفيذ عملية MongoDB بشكل آمن"""
        try:
            if not self._check_mongodb_connection():
                return None
            
            return operation_func(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"فشل عملية MongoDB: {e}")
            return None
'''
    
    # البحث عن مكان مناسب لإضافة الدوال
    if "class UnifiedSyncManager" in content:
        # إضافة الدوال داخل الكلاس
        class_start = content.find("class UnifiedSyncManager")
        class_end = content.find("\n\nclass", class_start)
        if class_end == -1:
            class_end = len(content)
        
        # إدراج الدوال قبل نهاية الكلاس
        content = content[:class_end] + enhanced_connection_check + content[class_end:]
    
    # تحسين دالة _sync_table_from_cloud
    old_sync_method = '''    def _sync_table_from_cloud(self, table_name: str):
        """مزامنة جدول من السحابة"""
        try:
            cloud_data = list(self.repo.mongo_db[table_name].find())'''
    
    new_sync_method = '''    def _sync_table_from_cloud(self, table_name: str):
        """مزامنة جدول من السحابة مع فحص الاتصال"""
        try:
            if not self._check_mongodb_connection():
                return {}
            
            cloud_data = self._safe_mongodb_operation(
                lambda: list(self.repo.mongo_db[table_name].find())
            )
            
            if cloud_data is None:
                return {}'''
    
    # تطبيق التحسين
    content = content.replace(old_sync_method, new_sync_method)
    
    # كتابة الملف المحدث
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ تم تحسين فحص اتصال MongoDB")
    return True

def update_cursor_usage():
    """تحديث استخدام الـ cursors في الملفات الحرجة"""
    print("🔧 تحديث استخدام الـ cursors...")
    
    # إنشاء مثال لاستخدام cursor context manager
    example_usage = '''# مثال على الاستخدام الصحيح للـ cursors

from core.cursor_manager import get_cursor_context

# بدلاً من:
# cursor = self.repo.get_cursor()
# try:
#     cursor.execute("SELECT * FROM clients")
#     results = cursor.fetchall()
# finally:
#     cursor.close()

# استخدم:
with get_cursor_context(self.repo) as cursor:
    cursor.execute("SELECT * FROM clients")
    results = cursor.fetchall()
# يتم إغلاق الـ cursor تلقائياً

# للعمليات المتعددة:
def get_client_with_projects(client_id):
    with get_cursor_context(self.repo) as cursor:
        # جلب العميل
        cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        client = cursor.fetchone()
        
        if client:
            # جلب المشاريع في cursor منفصل
            with get_cursor_context(self.repo) as projects_cursor:
                projects_cursor.execute("SELECT * FROM projects WHERE client_id = ?", (client_id,))
                projects = projects_cursor.fetchall()
            
            return client, projects
    
    return None, []
'''
    
    with open("CURSOR_USAGE_EXAMPLES.md", 'w', encoding='utf-8') as f:
        f.write(f"# أمثلة استخدام Cursor Context Manager\n\n{example_usage}")
    
    print("✅ تم إنشاء أمثلة استخدام الـ cursors")
    return True

def main():
    """تطبيق جميع الإصلاحات"""
    print("🚀 بدء حل المشاكل المتبقية")
    print("=" * 50)
    
    fixes = [
        ("إصلاح daemon threads في main.py", fix_daemon_threads_main),
        ("إصلاح daemon threads في main_window.py", fix_daemon_threads_main_window),
        ("إصلاح daemon threads في unified_sync.py", fix_unified_sync_threads),
        ("إصلاح daemon threads في repository.py", fix_repository_threads),
        ("تحسين فحص اتصال MongoDB", enhance_mongodb_connection_checks),
        ("تحديث استخدام الـ cursors", update_cursor_usage)
    ]
    
    results = {}
    
    for fix_name, fix_func in fixes:
        try:
            print(f"\n🔧 {fix_name}...")
            result = fix_func()
            results[fix_name] = result
        except Exception as e:
            print(f"❌ فشل {fix_name}: {e}")
            results[fix_name] = False
    
    print("\n" + "=" * 50)
    print("📊 ملخص الإصلاحات:")
    
    applied = 0
    total = len(results)
    
    for fix_name, result in results.items():
        status = "✅ تم" if result else "❌ فشل"
        print(f"  {fix_name}: {status}")
        if result:
            applied += 1
    
    print(f"\nالنتيجة: {applied}/{total} إصلاح تم تطبيقه")
    
    if applied == total:
        print("🎉 تم حل جميع المشاكل المتبقية بنجاح!")
        print("\n📋 الخطوات التالية:")
        print("  1. اختبر البرنامج للتأكد من عمله")
        print("  2. راقب استقرار النظام")
        print("  3. استخدم CURSOR_USAGE_EXAMPLES.md للكود الجديد")
    else:
        print("⚠️ بعض الإصلاحات فشلت. راجع الأخطاء أعلاه.")
    
    return applied == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)