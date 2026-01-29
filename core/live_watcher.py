"""
🔴 Live Data Watcher - مراقب البيانات الحية
نظام مراقبة التغييرات الحية في البيانات للمزامنة بين الأجهزة

⚡ يعمل بطريقتين:
1. Polling: فحص دوري للتغييرات في قاعدة البيانات المحلية
2. MongoDB Change Streams: مراقبة فورية للتغييرات في السحابة (إذا كان متاحاً)
"""
import threading
import time
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.logger import get_logger

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass

logger = get_logger(__name__)


class LiveDataWatcher(QObject):
    """
    🔴 مراقب البيانات الحية - نظام احترافي للمزامنة الفورية
    ⚡ محسّن للأداء - فحص كل 30 ثانية بدلاً من 15
    
    يراقب التغييرات في:
    - قاعدة البيانات المحلية (SQLite)
    
    ويرسل إشارات لتحديث الواجهة فوراً
    """
    
    # إشارات التحديث
    data_changed = pyqtSignal(str)  # table_name
    refresh_all = pyqtSignal()
    sync_needed = pyqtSignal(str)  # table_name
    
    # الجداول المراقبة - تقليل العدد للأداء
    WATCHED_TABLES = [
        'clients', 'projects', 'payments', 
        'expenses', 'accounts'
    ]
    
    def __init__(self, repository, check_interval: int = 30):
        """
        Args:
            repository: مخزن البيانات
            check_interval: فترة الفحص (بالثواني) - افتراضي 30 ثانية
        """
        super().__init__()
        self.repository = repository
        self.check_interval = check_interval
        self._timer: QTimer = None
        self._is_running = False
        self._last_check_time = {}
        self._last_counts = {}
        self._last_modified = {}
        self._shutdown = False
        self._pending_changes = set()  # ⚡ تجميع التغييرات لتقليل الإشارات
        self._debounce_timer = None  # ⚡ مؤقت للتأخير
        
        # ⚡ تعطيل MongoDB watcher - نعتمد على RealtimeSyncManager
        self._mongo_watcher_thread = None
        self._stop_event = threading.Event()
        
        # تهيئة أوقات الفحص الأخيرة
        for table in self.WATCHED_TABLES:
            self._last_check_time[table] = datetime.now()
            self._last_counts[table] = 0
            self._last_modified[table] = None
        
        logger.info("[LiveWatcher] ✅ تم تهيئة مراقب البيانات الحية (محسّن - كل 30 ثانية)")
    
    def start(self):
        """🚀 بدء المراقبة"""
        if self._is_running:
            return
        
        self._shutdown = False
        self._stop_event.clear()
        
        # 1. بدء مراقبة SQLite (Polling) - كل 15 ثانية
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_local_changes)
        self._timer.start(self.check_interval * 1000)
        
        # ⚡ تعطيل MongoDB watcher - نعتمد على RealtimeSyncManager
        # self._start_mongo_watcher()
        
        self._is_running = True
        
        # جلب الأعداد الأولية
        self._init_counts()
        
        logger.info(f"[LiveWatcher] 🚀 بدء المراقبة كل {self.check_interval} ثواني")
        safe_print(f"INFO: [LiveWatcher] 🚀 بدء المراقبة كل {self.check_interval} ثواني")
    
    def stop(self):
        """⏹️ إيقاف المراقبة"""
        self._shutdown = True
        self._stop_event.set()
        
        if self._timer:
            try:
                self._timer.stop()
            except (RuntimeError, AttributeError):
                pass
            self._timer = None
        
        # انتظار انتهاء thread المراقبة
        if self._mongo_watcher_thread and self._mongo_watcher_thread.is_alive():
            self._mongo_watcher_thread.join(timeout=2)
        
        self._is_running = False
        logger.info("[LiveWatcher] ⏹️ تم إيقاف المراقبة")
    
    def _init_counts(self):
        """تهيئة الأعداد الأولية للجداول"""
        try:
            cursor = self.repository.get_cursor()
            try:
                for table in self.WATCHED_TABLES:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        self._last_counts[table] = cursor.fetchone()[0]
                        
                        # جلب آخر تعديل
                        cursor.execute(f"SELECT MAX(last_modified) FROM {table}")
                        result = cursor.fetchone()[0]
                        self._last_modified[table] = result
                    except Exception:
                        self._last_counts[table] = 0
                        self._last_modified[table] = None
            finally:
                cursor.close()
        except Exception as e:
            logger.debug(f"[LiveWatcher] خطأ في تهيئة الأعداد: {e}")
    
    def _check_local_changes(self):
        """🔍 فحص التغييرات في قاعدة البيانات المحلية"""
        if self._shutdown:
            return
        
        try:
            cursor = self.repository.get_cursor()
            changed_tables = []
            
            try:
                for table in self.WATCHED_TABLES:
                    try:
                        # فحص عدد السجلات
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        current_count = cursor.fetchone()[0]
                        
                        # فحص آخر تعديل
                        cursor.execute(f"SELECT MAX(last_modified) FROM {table}")
                        current_modified = cursor.fetchone()[0]
                        
                        # مقارنة مع القيم السابقة
                        if (current_count != self._last_counts.get(table, 0) or
                            current_modified != self._last_modified.get(table)):
                            
                            changed_tables.append(table)
                            self._last_counts[table] = current_count
                            self._last_modified[table] = current_modified
                            
                    except Exception:
                        pass
            finally:
                cursor.close()
            
            # ⚡ تجميع التغييرات بدلاً من إرسال إشارة لكل جدول
            if changed_tables:
                self._pending_changes.update(changed_tables)
                self._schedule_emit()
                    
        except Exception as e:
            logger.debug(f"[LiveWatcher] خطأ في فحص التغييرات: {e}")

    def _schedule_emit(self):
        """⚡ جدولة إرسال الإشارات مع تأخير لتجميع التغييرات"""
        if self._debounce_timer is None:
            self._debounce_timer = QTimer()
            self._debounce_timer.setSingleShot(True)
            self._debounce_timer.timeout.connect(self._emit_pending_changes)
        
        # إعادة تشغيل المؤقت (2000ms تأخير - زيادة للأداء)
        self._debounce_timer.start(2000)

    def _emit_pending_changes(self):
        """⚡ إرسال الإشارات المجمعة"""
        if not self._pending_changes:
            return
        
        tables = list(self._pending_changes)
        self._pending_changes.clear()
        
        # إرسال إشارة واحدة لكل جدول
        for table in tables:
            logger.debug(f"[LiveWatcher] 📢 تغيير في {table}")
            try:
                self.data_changed.emit(table)
            except RuntimeError:
                pass
        
        # إذا تغيرت عدة جداول، أرسل إشارة تحديث شامل
        if len(tables) >= 3:
            try:
                self.refresh_all.emit()
            except RuntimeError:
                pass
    
    def _start_mongo_watcher(self):
        """🔴 بدء مراقبة MongoDB Change Streams"""
        if not self.repository.online or self.repository.mongo_db is None:
            logger.info("[LiveWatcher] MongoDB غير متاح - المراقبة المحلية فقط")
            return
        
        def watch_mongo():
            """Thread لمراقبة MongoDB"""
            logger.info("[LiveWatcher] 🔴 بدء مراقبة MongoDB Change Streams")
            
            while not self._stop_event.is_set() and not self._shutdown:
                try:
                    if self.repository.mongo_db is None:
                        time.sleep(5)
                        continue
                    
                    # مراقبة كل الجداول
                    for table in self.WATCHED_TABLES:
                        if self._stop_event.is_set() or self._shutdown:
                            break
                        
                        try:
                            collection = self.repository.mongo_db[table]
                            
                            # استخدام Change Stream مع timeout قصير
                            with collection.watch(
                                full_document='updateLookup',
                                max_await_time_ms=2000
                            ) as stream:
                                for change in stream:
                                    if self._stop_event.is_set() or self._shutdown:
                                        break
                                    
                                    # تم اكتشاف تغيير!
                                    operation = change.get('operationType', 'unknown')
                                    logger.info(f"[LiveWatcher] 🔴 MongoDB: {operation} في {table}")
                                    safe_print(f"INFO: [LiveWatcher] 🔴 MongoDB: {operation} في {table}")
                                    
                                    # إرسال إشارة المزامنة
                                    try:
                                        self.sync_needed.emit(table)
                                        self.data_changed.emit(table)
                                    except RuntimeError:
                                        pass
                                    
                        except Exception as e:
                            if "Cannot use MongoClient after close" in str(e):
                                break
                            # تجاهل أخطاء timeout
                            if "timed out" not in str(e).lower():
                                logger.debug(f"[LiveWatcher] خطأ في مراقبة {table}: {e}")
                    
                    # انتظار قبل الدورة التالية
                    time.sleep(1)
                    
                except Exception as e:
                    if self._shutdown:
                        break
                    logger.debug(f"[LiveWatcher] خطأ في MongoDB watcher: {e}")
                    time.sleep(5)
            
            logger.info("[LiveWatcher] 🔴 تم إيقاف مراقبة MongoDB")
        
        # بدء Thread المراقبة
        self._mongo_watcher_thread = threading.Thread(
            target=watch_mongo,
            daemon=True,
            name="MongoWatcher"
        )
        self._mongo_watcher_thread.start()
    
    def force_check(self, table: str = None):
        """⚡ فحص فوري للتغييرات"""
        if table:
            try:
                self.data_changed.emit(table)
            except RuntimeError:
                pass
        else:
            self._check_local_changes()


class LiveUpdateRouter(QObject):
    """
    🔀 موجّه التحديثات الحية
    يوجه إشارات التحديث إلى الواجهات المناسبة
    """
    
    def __init__(self, main_window):
        """
        Args:
            main_window: النافذة الرئيسية
        """
        super().__init__()
        self.main_window = main_window
        logger.info("[LiveRouter] ✅ تم تهيئة موجّه التحديثات")
    
    def handle_data_change(self, table_name: str):
        """
        📢 معالجة تغيير البيانات
        
        Args:
            table_name: اسم الجدول المتغير
        """
        logger.debug(f"[LiveRouter] 📢 تغيير في: {table_name}")
        safe_print(f"INFO: [LiveRouter] 📢 تغيير في: {table_name}")
        
        try:
            # استخدام refresh_table من MainWindow إذا كانت موجودة
            if hasattr(self.main_window, 'refresh_table'):
                self.main_window.refresh_table(table_name)
            else:
                # fallback للطريقة القديمة
                self._refresh_table_fallback(table_name)
                
        except Exception as e:
            logger.debug(f"[LiveRouter] خطأ في توجيه التحديث: {e}")
    
    def _refresh_table_fallback(self, table_name: str):
        """طريقة بديلة لتحديث الجداول"""
        try:
            if table_name == 'clients':
                if hasattr(self.main_window, 'clients_tab'):
                    QTimer.singleShot(100, self.main_window.clients_tab.load_clients)
                    
            elif table_name == 'projects':
                if hasattr(self.main_window, 'projects_tab'):
                    QTimer.singleShot(100, self.main_window.projects_tab.load_projects)
                    
            elif table_name == 'services':
                if hasattr(self.main_window, 'services_tab'):
                    QTimer.singleShot(100, self.main_window.services_tab.load_services)
                    
            elif table_name == 'payments':
                if hasattr(self.main_window, 'payments_tab'):
                    QTimer.singleShot(100, self.main_window.payments_tab.load_payments)
                    
            elif table_name == 'expenses':
                if hasattr(self.main_window, 'expenses_tab'):
                    QTimer.singleShot(100, self.main_window.expenses_tab.load_expenses)
                    
            elif table_name == 'accounts':
                if hasattr(self.main_window, 'accounting_tab'):
                    QTimer.singleShot(100, self.main_window.accounting_tab.load_accounts)
                    
            elif table_name == 'tasks':
                if hasattr(self.main_window, 'todo_tab'):
                    QTimer.singleShot(100, self.main_window.todo_tab.load_tasks)
            
            # تحديث Dashboard
            if hasattr(self.main_window, 'dashboard_tab'):
                QTimer.singleShot(300, self.main_window.dashboard_tab.refresh_data)
                
        except Exception as e:
            logger.debug(f"[LiveRouter] خطأ في تحديث الواجهة: {e}")
    
    def handle_sync_needed(self, table_name: str):
        """
        🔄 معالجة طلب المزامنة
        
        Args:
            table_name: اسم الجدول المطلوب مزامنته
        """
        logger.info(f"[LiveRouter] 🔄 مزامنة مطلوبة: {table_name}")
        safe_print(f"INFO: [LiveRouter] 🔄 مزامنة مطلوبة: {table_name}")
        
        try:
            # طلب مزامنة من unified_sync
            if hasattr(self.main_window, 'sync_manager') and self.main_window.sync_manager:
                # مزامنة الجدول المحدد
                if hasattr(self.main_window.sync_manager, 'repo'):
                    repo = self.main_window.sync_manager.repo
                    if repo and hasattr(repo, 'unified_sync') and repo.unified_sync:
                        # مزامنة فورية للجدول
                        repo.unified_sync.instant_sync(table_name)
        except Exception as e:
            logger.debug(f"[LiveRouter] خطأ في طلب المزامنة: {e}")
    
    def refresh_all(self):
        """🔄 تحديث جميع الواجهات"""
        logger.info("[LiveRouter] 🔄 تحديث جميع الواجهات")
        safe_print("INFO: [LiveRouter] 🔄 تحديث جميع الواجهات")
        
        try:
            # تحديث كل الواجهات
            if hasattr(self.main_window, 'clients_tab'):
                QTimer.singleShot(100, self.main_window.clients_tab.load_clients)
            if hasattr(self.main_window, 'projects_tab'):
                QTimer.singleShot(200, self.main_window.projects_tab.load_projects)
            if hasattr(self.main_window, 'services_tab'):
                QTimer.singleShot(300, self.main_window.services_tab.load_services)
            if hasattr(self.main_window, 'accounting_tab'):
                QTimer.singleShot(400, self.main_window.accounting_tab.load_accounts)
            if hasattr(self.main_window, 'dashboard_tab'):
                QTimer.singleShot(500, self.main_window.dashboard_tab.refresh_data)
        except Exception as e:
            logger.debug(f"[LiveRouter] خطأ في تحديث الواجهات: {e}")
