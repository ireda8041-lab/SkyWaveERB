"""
🔄 نظام المزامنة الفورية (Real-time Sync)
مزامنة فورية بين الأجهزة عبر MongoDB Change Streams

⚡ المميزات:
- مراقبة التغييرات في MongoDB فوراً
- مزامنة البيانات بين الأجهزة في الوقت الحقيقي
- إرسال إشارات لتحديث الواجهة
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

# استيراد آمن لـ pymongo
try:
    from pymongo.errors import PyMongoError
    PYMONGO_AVAILABLE = True
except ImportError:
    PyMongoError = Exception
    PYMONGO_AVAILABLE = False

logger = get_logger(__name__)

# المتغير العام لمدير المزامنة الفورية
_realtime_manager = None


class RealtimeSyncManager(QObject):
    """
    🔄 مدير المزامنة الفورية
    يراقب التغييرات في MongoDB ويزامن البيانات فوراً
    ⚡ محسّن للأداء - يستخدم thread واحد فقط بدلاً من thread لكل collection
    """
    
    # إشارات
    data_updated = pyqtSignal(str, dict)  # (collection_name, change_data)
    connection_status_changed = pyqtSignal(bool)  # (is_connected)
    sync_completed = pyqtSignal(str)  # (collection_name)
    
    # الجداول المراقبة - تقليل العدد للأداء
    COLLECTIONS = [
        'clients', 'projects', 'payments',
        'expenses', 'accounts'
    ]
    
    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repo = repository
        self.is_running = False
        self._shutdown = False
        self._stop_event = threading.Event()
        self._watcher_thread = None  # ⚡ thread واحد فقط
        self._last_sync_time = {}
        self._pending_changes = set()  # ⚡ تجميع التغييرات
        self._debounce_timer = None
        
        # تهيئة أوقات المزامنة
        for collection in self.COLLECTIONS:
            self._last_sync_time[collection] = datetime.now()
        
        logger.info("[RealtimeSync] ✅ تم تهيئة مدير المزامنة الفورية (محسّن)")
    
    def start(self):
        """🚀 بدء المزامنة الفورية"""
        if self.is_running:
            return
        
        if not PYMONGO_AVAILABLE:
            logger.warning("[RealtimeSync] pymongo غير متاح - المزامنة الفورية معطّلة")
            return
        
        if not self.repo.online or self.repo.mongo_db is None:
            logger.warning("[RealtimeSync] MongoDB غير متاح - المزامنة الفورية معطّلة")
            return
        
        self._shutdown = False
        self._stop_event.clear()
        self.is_running = True
        
        # ⚡ بدء thread واحد فقط لمراقبة كل الـ collections
        self._start_unified_watcher()
        
        logger.info("[RealtimeSync] 🚀 بدء المزامنة الفورية (thread واحد)")
        safe_print("INFO: [RealtimeSync] 🚀 بدء المزامنة الفورية (محسّن)")
    
    def stop(self):
        """⏹️ إيقاف المزامنة الفورية"""
        if not self.is_running:
            return
        
        logger.info("[RealtimeSync] ⏹️ جاري إيقاف المزامنة الفورية...")
        self._shutdown = True
        self._stop_event.set()
        self.is_running = False
        
        # انتظار انتهاء الـ thread
        try:
            if self._watcher_thread and self._watcher_thread.is_alive():
                self._watcher_thread.join(timeout=2)
        except Exception:
            pass
        
        self._watcher_thread = None
        logger.info("[RealtimeSync] ✅ تم إيقاف المزامنة الفورية")
    
    def _start_unified_watcher(self):
        """⚡ بدء مراقبة موحدة لكل الـ collections في thread واحد"""
        def watch_all_collections():
            logger.debug("[RealtimeSync] بدء المراقبة الموحدة")
            
            while not self._stop_event.is_set() and not self._shutdown:
                try:
                    if self.repo.mongo_db is None or self.repo.mongo_client is None:
                        time.sleep(10)  # ⚡ زيادة الانتظار عند عدم الاتصال
                        continue
                    
                    # مراقبة كل collection بالتناوب
                    for collection_name in self.COLLECTIONS:
                        if self._stop_event.is_set() or self._shutdown:
                            break
                        
                        try:
                            collection = self.repo.mongo_db[collection_name]
                            
                            # مراقبة التغييرات مع timeout قصير جداً
                            with collection.watch(
                                full_document='updateLookup',
                                max_await_time_ms=500  # ⚡ تقليل الـ timeout لـ 500ms
                            ) as stream:
                                for change in stream:
                                    if self._stop_event.is_set() or self._shutdown:
                                        break
                                    
                                    # ⚡ تجميع التغييرات بدلاً من معالجتها فوراً
                                    self._pending_changes.add(collection_name)
                                    self._schedule_emit_changes()
                                    break  # ⚡ معالجة تغيير واحد فقط ثم الانتقال للـ collection التالي
                                    
                        except PyMongoError as e:
                            if self._shutdown:
                                break
                            error_msg = str(e)
                            if "Cannot use MongoClient after close" in error_msg:
                                break
                            # تجاهل أخطاء timeout
                            if "timed out" not in error_msg.lower():
                                logger.debug(f"[RealtimeSync] خطأ في مراقبة {collection_name}: {e}")
                        except Exception:
                            pass
                    
                    # ⚡ زيادة الانتظار بين الدورات لـ 5 ثواني
                    time.sleep(5)
                    
                except Exception as e:
                    if self._shutdown:
                        break
                    logger.debug(f"[RealtimeSync] خطأ في المراقبة الموحدة: {e}")
                    time.sleep(10)  # ⚡ زيادة الانتظار عند الخطأ
            
            logger.debug("[RealtimeSync] انتهاء المراقبة الموحدة")
        
        # إنشاء وبدء Thread واحد
        self._watcher_thread = threading.Thread(
            target=watch_all_collections,
            daemon=True,
            name="RealtimeSync-Unified"
        )
        self._watcher_thread.start()
    
    def _schedule_emit_changes(self):
        """⚡ جدولة إرسال التغييرات المجمعة"""
        # استخدام QTimer للتأخير (debounce)
        from PyQt6.QtCore import QTimer, QMetaObject, Qt, Q_ARG
        
        # إرسال التغييرات بعد 500ms
        try:
            QMetaObject.invokeMethod(
                self, "_emit_pending_changes_slot",
                Qt.ConnectionType.QueuedConnection
            )
        except Exception:
            pass
    
    def _emit_pending_changes_slot(self):
        """⚡ إرسال التغييرات المجمعة (يعمل على main thread)"""
        if not self._pending_changes:
            return
        
        changes = list(self._pending_changes)
        self._pending_changes.clear()
        
        for collection_name in changes:
            try:
                self.data_updated.emit(collection_name, {'operation': 'change'})
                self.sync_completed.emit(collection_name)
                self._last_sync_time[collection_name] = datetime.now()
            except RuntimeError:
                pass
    
    def _handle_change(self, collection_name: str, change: dict):
        """معالجة تغيير من MongoDB"""
        try:
            operation = change.get('operationType', 'unknown')
            document = change.get('fullDocument', {})
            document_id = change.get('documentKey', {}).get('_id')
            
            logger.info(f"[RealtimeSync] 🔄 {operation} في {collection_name}")
            safe_print(f"INFO: [RealtimeSync] 🔄 {operation} في {collection_name}")
            
            # مزامنة التغيير محلياً
            if operation in ['insert', 'update', 'replace']:
                self._sync_document_to_local(collection_name, document)
            elif operation == 'delete':
                self._delete_document_from_local(collection_name, str(document_id))
            
            # إرسال إشارة التحديث
            try:
                self.data_updated.emit(collection_name, {
                    'operation': operation,
                    'document_id': str(document_id) if document_id else None
                })
                self.sync_completed.emit(collection_name)
            except RuntimeError:
                pass
            
            # تحديث وقت المزامنة
            self._last_sync_time[collection_name] = datetime.now()
            
        except Exception as e:
            logger.debug(f"[RealtimeSync] خطأ في معالجة التغيير: {e}")
    
    def _sync_document_to_local(self, collection_name: str, document: dict):
        """مزامنة مستند من MongoDB إلى SQLite"""
        if not document:
            return
        
        try:
            mongo_id = str(document.get('_id', ''))
            if not mongo_id:
                return
            
            # تحضير البيانات
            data = self._prepare_document_for_sqlite(document)
            data['_mongo_id'] = mongo_id
            data['sync_status'] = 'synced'
            
            cursor = self.repo.get_cursor()
            try:
                # البحث عن السجل المحلي
                cursor.execute(
                    f"SELECT id FROM {collection_name} WHERE _mongo_id = ?",
                    (mongo_id,)
                )
                existing = cursor.fetchone()
                
                # الحصول على أعمدة الجدول
                cursor.execute(f"PRAGMA table_info({collection_name})")
                table_columns = {row[1] for row in cursor.fetchall()}
                
                # تصفية البيانات
                filtered_data = {k: v for k, v in data.items() if k in table_columns}
                
                if existing:
                    # تحديث
                    local_id = existing[0]
                    set_clause = ', '.join([f"{k}=?" for k in filtered_data.keys()])
                    values = list(filtered_data.values()) + [local_id]
                    cursor.execute(
                        f"UPDATE {collection_name} SET {set_clause} WHERE id=?",
                        values
                    )
                else:
                    # إدراج
                    columns = ', '.join(filtered_data.keys())
                    placeholders = ', '.join(['?' for _ in filtered_data])
                    cursor.execute(
                        f"INSERT INTO {collection_name} ({columns}) VALUES ({placeholders})",
                        list(filtered_data.values())
                    )
                
                self.repo.sqlite_conn.commit()
                logger.debug(f"[RealtimeSync] ✅ تم مزامنة {collection_name}/{mongo_id}")
                
            finally:
                cursor.close()
                
        except Exception as e:
            logger.debug(f"[RealtimeSync] خطأ في مزامنة المستند: {e}")
    
    def _delete_document_from_local(self, collection_name: str, mongo_id: str):
        """حذف مستند من SQLite"""
        if not mongo_id:
            return
        
        try:
            cursor = self.repo.get_cursor()
            try:
                cursor.execute(
                    f"DELETE FROM {collection_name} WHERE _mongo_id = ?",
                    (mongo_id,)
                )
                self.repo.sqlite_conn.commit()
                logger.debug(f"[RealtimeSync] 🗑️ تم حذف {collection_name}/{mongo_id}")
            finally:
                cursor.close()
        except Exception as e:
            logger.debug(f"[RealtimeSync] خطأ في حذف المستند: {e}")
    
    def _prepare_document_for_sqlite(self, document: dict) -> dict:
        """تحضير مستند MongoDB للحفظ في SQLite"""
        import json
        
        data = dict(document)
        data.pop('_id', None)
        data.pop('id', None)
        
        # تحويل التواريخ
        date_fields = [
            'created_at', 'last_modified', 'date', 'issue_date',
            'due_date', 'start_date', 'end_date'
        ]
        for field in date_fields:
            if field in data and hasattr(data[field], 'isoformat'):
                data[field] = data[field].isoformat()
        
        # تحويل القوائم والكائنات إلى JSON
        json_fields = ['items', 'lines', 'data', 'milestones']
        for field in json_fields:
            if field in data and isinstance(data[field], (list, dict)):
                data[field] = json.dumps(data[field], ensure_ascii=False)
        
        # التأكد من الحقول المطلوبة
        now = datetime.now().isoformat()
        if not data.get('created_at'):
            data['created_at'] = now
        if not data.get('last_modified'):
            data['last_modified'] = now
        
        return data


def setup_realtime_sync(repository) -> RealtimeSyncManager | None:
    """
    🚀 إعداد وتشغيل نظام المزامنة الفورية
    
    Args:
        repository: مخزن البيانات
        
    Returns:
        مدير المزامنة الفورية أو None إذا فشل
    """
    global _realtime_manager
    
    try:
        if _realtime_manager is not None:
            return _realtime_manager
        
        _realtime_manager = RealtimeSyncManager(repository)
        _realtime_manager.start()
        
        logger.info("[RealtimeSync] ✅ تم إعداد نظام المزامنة الفورية")
        return _realtime_manager
        
    except Exception as e:
        logger.warning(f"[RealtimeSync] فشل إعداد المزامنة الفورية: {e}")
        return None


def shutdown_realtime_sync():
    """⏹️ إيقاف نظام المزامنة الفورية"""
    global _realtime_manager
    
    try:
        if _realtime_manager is not None:
            _realtime_manager.stop()
            _realtime_manager = None
            logger.info("[RealtimeSync] ✅ تم إيقاف نظام المزامنة الفورية")
    except Exception as e:
        logger.debug(f"[RealtimeSync] خطأ في إيقاف المزامنة: {e}")


def get_realtime_manager() -> RealtimeSyncManager | None:
    """الحصول على مدير المزامنة الفورية"""
    return _realtime_manager


# للتوافق مع الكود القديم
class RealtimeSync(RealtimeSyncManager):
    """Alias للتوافق مع الكود القديم"""
    pass
