# الملف: core/unified_sync.py
"""
🔄 نظام المزامنة الموحد - MongoDB First
MongoDB هو المصدر الرئيسي، SQLite نسخة محلية للـ offline فقط

المبدأ:
- عند الاتصال: MongoDB = الحقيقة المطلقة
- عند عدم الاتصال: SQLite يحفظ التغييرات مؤقتاً
- عند استعادة الاتصال: رفع التغييرات المحلية ثم مسح وإعادة تحميل من MongoDB
"""

import json
import threading
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


class UnifiedSyncManagerV3(QObject):
    """
    مدير المزامنة الموحد - MongoDB First Architecture
    مع نظام مزامنة تلقائية احترافي
    """

    # الإشارات
    sync_started = pyqtSignal()
    sync_progress = pyqtSignal(str, int, int)  # table, current, total
    sync_completed = pyqtSignal(dict)
    sync_error = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)  # online/offline

    # الجداول المدعومة
    TABLES = [
        'accounts', 'clients', 'services', 'projects',
        'invoices', 'payments', 'expenses', 'journal_entries',
        'currencies', 'notifications', 'tasks'
    ]

    # الحقول الفريدة لكل جدول
    UNIQUE_FIELDS = {
        'clients': 'name',
        'projects': 'name',
        'services': 'name',
        'accounts': 'code',
        'invoices': 'invoice_number',
        'payments': 'id',
        'expenses': 'id',
        'journal_entries': 'id',
        'currencies': 'code',
        'users': 'username',
        'notifications': 'id',
        'tasks': 'id'
    }

    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repo = repository
        self._lock = threading.RLock()
        self._is_syncing = False
        self._max_retries = 3
        self._last_online_status = None
        
        # ⚡ إعدادات المزامنة التلقائية
        self._auto_sync_enabled = True
        self._auto_sync_interval = 10 * 60 * 1000  # 10 دقائق بدلاً من 5
        self._quick_sync_interval = 60 * 1000  # 60 ثانية بدلاً من 30
        self._connection_check_interval = 30 * 1000  # 30 ثانية بدلاً من 15
        
        # ⚡ المؤقتات
        self._auto_sync_timer = None
        self._quick_sync_timer = None
        self._connection_timer = None
        
        logger.info("✅ تم تهيئة UnifiedSyncManager - MongoDB First + Auto Sync")

    # ==========================================
    # نظام المزامنة التلقائية الاحترافي
    # ==========================================
    
    def start_auto_sync(self):
        """🚀 بدء نظام المزامنة التلقائية"""
        if not self._auto_sync_enabled:
            return
            
        logger.info("🚀 بدء نظام المزامنة التلقائية...")
        
        # 1. مؤقت فحص الاتصال (كل 15 ثانية)
        self._connection_timer = QTimer(self)
        self._connection_timer.timeout.connect(self._check_connection)
        self._connection_timer.start(self._connection_check_interval)
        
        # 2. مؤقت المزامنة السريعة للتغييرات المحلية (كل 30 ثانية)
        self._quick_sync_timer = QTimer(self)
        self._quick_sync_timer.timeout.connect(self._quick_push_changes)
        self._quick_sync_timer.start(self._quick_sync_interval)
        
        # 3. مؤقت المزامنة الكاملة (كل 5 دقائق)
        self._auto_sync_timer = QTimer(self)
        self._auto_sync_timer.timeout.connect(self._auto_full_sync)
        self._auto_sync_timer.start(self._auto_sync_interval)
        
        # 4. مزامنة أولية بعد 3 ثواني
        QTimer.singleShot(3000, self._initial_sync)
        
        logger.info(f"⏰ المزامنة التلقائية: كل {self._auto_sync_interval // 60000} دقيقة")
        logger.info(f"⏰ رفع التغييرات: كل {self._quick_sync_interval // 1000} ثانية")
    
    def stop_auto_sync(self):
        """⏹️ إيقاف نظام المزامنة التلقائية"""
        logger.info("⏹️ إيقاف نظام المزامنة التلقائية...")
        
        if self._auto_sync_timer:
            self._auto_sync_timer.stop()
            self._auto_sync_timer = None
            
        if self._quick_sync_timer:
            self._quick_sync_timer.stop()
            self._quick_sync_timer = None
            
        if self._connection_timer:
            self._connection_timer.stop()
            self._connection_timer = None
    
    def _check_connection(self):
        """🔌 فحص حالة الاتصال"""
        try:
            current_status = self.is_online
            
            # إرسال إشارة عند تغيير الحالة
            if current_status != self._last_online_status:
                self._last_online_status = current_status
                self.connection_changed.emit(current_status)
                
                if current_status:
                    logger.info("🟢 تم استعادة الاتصال - جاري المزامنة...")
                    # مزامنة فورية عند استعادة الاتصال
                    self._auto_full_sync()
                else:
                    logger.warning("🔴 انقطع الاتصال - العمل في وضع Offline")
        except Exception as e:
            logger.debug(f"خطأ في فحص الاتصال: {e}")
    
    def _initial_sync(self):
        """🚀 المزامنة الأولية عند بدء التشغيل"""
        if not self.is_online:
            logger.info("📴 لا يوجد اتصال - العمل بالبيانات المحلية")
            return
            
        logger.info("🚀 بدء المزامنة الأولية...")
        
        def sync_thread():
            try:
                result = self.full_sync_from_cloud()
                if result.get('success'):
                    logger.info(f"✅ المزامنة الأولية: {result.get('total_synced', 0)} سجل")
            except Exception as e:
                logger.error(f"❌ فشلت المزامنة الأولية: {e}")
        
        thread = threading.Thread(target=sync_thread, daemon=True)
        thread.start()
    
    def _auto_full_sync(self):
        """🔄 المزامنة الكاملة التلقائية"""
        if self._is_syncing or not self.is_online:
            return
            
        def sync_thread():
            try:
                result = self.full_sync_from_cloud()
                if result.get('success'):
                    logger.debug(f"🔄 مزامنة تلقائية: {result.get('total_synced', 0)} سجل")
            except Exception as e:
                logger.error(f"❌ فشلت المزامنة التلقائية: {e}")
        
        thread = threading.Thread(target=sync_thread, daemon=True)
        thread.start()
    
    def _quick_push_changes(self):
        """⚡ رفع التغييرات المحلية بسرعة"""
        if self._is_syncing or not self.is_online:
            return
            
        try:
            # فحص سريع للتغييرات المعلقة
            cursor = self.repo.sqlite_cursor
            has_pending = False
            
            for table in self.TABLES:
                try:
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM {table}
                        WHERE sync_status != 'synced' OR sync_status IS NULL
                    """)
                    count = cursor.fetchone()[0]
                    if count > 0:
                        has_pending = True
                        break
                except:
                    pass
            
            if has_pending:
                def push_thread():
                    try:
                        with self._lock:
                            self._push_pending_changes()
                        logger.debug("⚡ تم رفع التغييرات المحلية")
                    except Exception as e:
                        logger.error(f"❌ فشل رفع التغييرات: {e}")
                
                thread = threading.Thread(target=push_thread, daemon=True)
                thread.start()
                
        except Exception as e:
            logger.debug(f"خطأ في فحص التغييرات: {e}")
    
    def set_auto_sync_interval(self, minutes: int):
        """⏰ تغيير فترة المزامنة التلقائية"""
        self._auto_sync_interval = minutes * 60 * 1000
        if self._auto_sync_timer:
            self._auto_sync_timer.setInterval(self._auto_sync_interval)
        logger.info(f"⏰ تم تغيير فترة المزامنة إلى {minutes} دقيقة")

    @property
    def is_online(self) -> bool:
        """التحقق من الاتصال"""
        return self.repo.online if self.repo else False

    def _wait_for_connection(self, timeout: int = 10) -> bool:
        """⚡ انتظار اتصال MongoDB مع timeout"""
        import time
        waited = 0
        while not self.is_online and waited < timeout:
            time.sleep(0.5)
            waited += 0.5
        return self.is_online

    def full_sync_from_cloud(self) -> dict[str, Any]:
        """
        مزامنة كاملة من السحابة - MongoDB هو المصدر الوحيد
        يحذف البيانات المحلية غير الموجودة في السحابة
        """
        # ⚡ انتظار الاتصال أولاً
        if not self._wait_for_connection(timeout=10):
            logger.warning("غير متصل - لا يمكن المزامنة من السحابة")
            return {'success': False, 'reason': 'offline'}

        if self._is_syncing:
            return {'success': False, 'reason': 'already_syncing'}

        self._is_syncing = True
        self.sync_started.emit()

        results = {
            'success': True,
            'tables': {},
            'total_synced': 0,
            'total_deleted': 0
        }

        try:
            with self._lock:
                # 1. رفع التغييرات المحلية أولاً
                self._push_pending_changes()

                # 2. مزامنة المستخدمين
                self._sync_users_from_cloud()

                # 3. مزامنة كل جدول
                for table in self.TABLES:
                    try:
                        stats = self._sync_table_from_cloud(table)
                        results['tables'][table] = stats
                        results['total_synced'] += stats.get('synced', 0)
                        results['total_deleted'] += stats.get('deleted', 0)
                    except Exception as e:
                        logger.error(f"❌ خطأ في مزامنة {table}: {e}")
                        results['tables'][table] = {'error': str(e)}

            logger.info(f"✅ اكتملت المزامنة: {results['total_synced']} سجل")
            self.sync_completed.emit(results)
            
            # ⚡ إرسال إشارات تحديث البيانات لتحديث الواجهة
            try:
                from core.signals import app_signals
                app_signals.emit_data_changed('clients')
                app_signals.emit_data_changed('projects')
                logger.info("📢 تم إرسال إشارات تحديث الواجهة")
            except Exception as e:
                logger.warning(f"⚠️ فشل إرسال إشارات التحديث: {e}")

        except Exception as e:
            logger.error(f"❌ خطأ في المزامنة الكاملة: {e}")
            results['success'] = False
            results['error'] = str(e)
            self.sync_error.emit(str(e))

        finally:
            self._is_syncing = False

        return results

    def _sync_table_from_cloud(self, table_name: str) -> dict[str, int]:
        """
        مزامنة جدول واحد من السحابة مع منع التكرارات
        """
        stats = {'synced': 0, 'inserted': 0, 'updated': 0, 'deleted': 0, 'linked': 0}

        try:
            # جلب البيانات من السحابة
            cloud_data = list(self.repo.mongo_db[table_name].find())
            
            if not cloud_data:
                logger.info(f"لا توجد بيانات في {table_name}")
                return stats

            cursor = self.repo.sqlite_cursor
            conn = self.repo.sqlite_conn
            unique_field = self.UNIQUE_FIELDS.get(table_name, 'name')

            # الحصول على أعمدة الجدول
            cursor.execute(f"PRAGMA table_info({table_name})")
            table_columns = {row[1] for row in cursor.fetchall()}

            # جمع كل الـ mongo_ids من السحابة
            cloud_mongo_ids = set()

            for i, cloud_item in enumerate(cloud_data):
                self.sync_progress.emit(table_name, i + 1, len(cloud_data))

                mongo_id = str(cloud_item['_id'])
                cloud_mongo_ids.add(mongo_id)
                unique_value = cloud_item.get(unique_field)

                # تحضير البيانات
                item_data = self._prepare_cloud_data(cloud_item)
                item_data['_mongo_id'] = mongo_id
                item_data['sync_status'] = 'synced'

                # البحث عن السجل المحلي
                local_id = self._find_local_record(
                    cursor, table_name, mongo_id, unique_field, unique_value, table_columns
                )

                # تصفية الحقول
                filtered = {k: v for k, v in item_data.items() if k in table_columns}
                
                # ⚡ تسجيل لو logo_data موجود
                if table_name == 'clients' and 'logo_data' in item_data and item_data['logo_data']:
                    if 'logo_data' in filtered:
                        logger.info(f"📷 [{unique_value}] logo_data سيتم حفظه ({len(filtered['logo_data'])} حرف)")
                    else:
                        logger.warning(f"⚠️ [{unique_value}] logo_data تم تجاهله! (غير موجود في أعمدة الجدول)")
                        logger.warning(f"   أعمدة الجدول: {table_columns}")

                if local_id:
                    # تحديث السجل الموجود
                    self._update_record(cursor, table_name, local_id, filtered)
                    stats['updated'] += 1
                else:
                    # إدراج سجل جديد
                    self._insert_record(cursor, table_name, filtered)
                    stats['inserted'] += 1

                stats['synced'] += 1

            # حذف السجلات المحلية غير الموجودة في السحابة
            deleted = self._delete_orphan_records(cursor, table_name, cloud_mongo_ids)
            stats['deleted'] = deleted

            conn.commit()
            logger.info(f"✅ {table_name}: +{stats['inserted']} ~{stats['updated']} -{stats['deleted']}")

        except Exception as e:
            logger.error(f"❌ خطأ في مزامنة {table_name}: {e}")
            import traceback
            traceback.print_exc()

        return stats

    def _find_local_record(
        self, cursor, table_name: str, mongo_id: str,
        unique_field: str, unique_value: Any, table_columns: set
    ) -> int | None:
        """
        البحث عن السجل المحلي بعدة طرق لمنع التكرارات
        """
        # 1. البحث بـ _mongo_id
        cursor.execute(
            f"SELECT id FROM {table_name} WHERE _mongo_id = ?",
            (mongo_id,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]

        # 2. البحث بالحقل الفريد
        if unique_value and unique_field in table_columns:
            cursor.execute(
                f"SELECT id, _mongo_id FROM {table_name} WHERE {unique_field} = ?",
                (unique_value,)
            )
            row = cursor.fetchone()
            if row:
                local_id = row[0]
                existing_mongo_id = row[1]

                # إذا السجل غير مرتبط أو مرتبط بنفس الـ mongo_id
                if not existing_mongo_id or existing_mongo_id == mongo_id:
                    return local_id

        return None

    def _delete_orphan_records(
        self, cursor, table_name: str, valid_mongo_ids: set
    ) -> int:
        """
        حذف السجلات المحلية غير الموجودة في السحابة
        (السجلات التي لها _mongo_id لكنه غير موجود في السحابة)
        """
        if not valid_mongo_ids:
            return 0

        # جلب السجلات المحلية التي لها _mongo_id
        cursor.execute(
            f"SELECT id, _mongo_id FROM {table_name} WHERE _mongo_id IS NOT NULL"
        )
        local_records = cursor.fetchall()

        deleted = 0
        for row in local_records:
            local_id = row[0]
            local_mongo_id = row[1]

            if local_mongo_id and local_mongo_id not in valid_mongo_ids:
                cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (local_id,))
                deleted += 1
                logger.debug(f"حذف سجل يتيم: {table_name}/{local_id}")

        return deleted

    def _prepare_cloud_data(self, data: dict) -> dict:
        """تحضير بيانات السحابة للحفظ محلياً"""
        item = dict(data)
        item.pop('_id', None)
        item.pop('id', None)

        # ⚡ التأكد من جلب logo_data بشكل صحيح
        if 'logo_data' in data and data['logo_data']:
            item['logo_data'] = data['logo_data']
            client_name = data.get('name', 'غير معروف')
            logger.info(f"📷 [{client_name}] جلب logo_data ({len(data['logo_data'])} حرف) من السحابة")
            safe_print(f"INFO: 📷 [{client_name}] جلب logo_data ({len(data['logo_data'])} حرف) من السحابة")

        # تحويل التواريخ
        date_fields = [
            'created_at', 'last_modified', 'date', 'issue_date',
            'due_date', 'expiry_date', 'start_date', 'end_date',
            'last_attempt', 'expires_at', 'last_login'
        ]
        for field in date_fields:
            if field in item and hasattr(item[field], 'isoformat'):
                item[field] = item[field].isoformat()

        # تحويل القوائم والكائنات إلى JSON
        json_fields = ['items', 'lines', 'data', 'milestones']
        for field in json_fields:
            if field in item and isinstance(item[field], (list, dict)):
                item[field] = json.dumps(item[field], ensure_ascii=False)

        # التأكد من الحقول المطلوبة
        now = datetime.now().isoformat()
        if not item.get('created_at'):
            item['created_at'] = now
        if not item.get('last_modified'):
            item['last_modified'] = now

        return item

    def _update_record(self, cursor, table_name: str, local_id: int, data: dict):
        """تحديث سجل محلي"""
        if not data:
            return

        set_clause = ', '.join([f"{k}=?" for k in data.keys()])
        values = list(data.values()) + [local_id]
        cursor.execute(
            f"UPDATE {table_name} SET {set_clause} WHERE id=?",
            values
        )

    def _insert_record(self, cursor, table_name: str, data: dict):
        """إدراج سجل جديد مع التعامل مع التكرارات"""
        if not data:
            return

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        
        try:
            cursor.execute(
                f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        except Exception as e:
            # في حالة UNIQUE constraint - نحاول التحديث بدلاً من الإدراج
            if "UNIQUE constraint" in str(e):
                # البحث عن السجل الموجود وتحديثه
                unique_field = self.UNIQUE_FIELDS.get(table_name, 'name')
                unique_value = data.get(unique_field)
                mongo_id = data.get('_mongo_id')
                
                if unique_value:
                    try:
                        # تحديث السجل الموجود
                        cursor.execute(
                            f"SELECT id FROM {table_name} WHERE {unique_field} = ?",
                            (unique_value,)
                        )
                        row = cursor.fetchone()
                        if row:
                            self._update_record(cursor, table_name, row[0], data)
                            logger.debug(f"تم تحديث السجل المكرر: {unique_value}")
                            return
                    except Exception:
                        pass
                
                # محاولة البحث بـ mongo_id
                if mongo_id:
                    try:
                        cursor.execute(
                            f"SELECT id FROM {table_name} WHERE _mongo_id = ?",
                            (mongo_id,)
                        )
                        row = cursor.fetchone()
                        if row:
                            self._update_record(cursor, table_name, row[0], data)
                            return
                    except Exception:
                        pass
                
                # تجاهل الخطأ إذا فشل كل شيء
                logger.debug(f"تجاهل سجل مكرر في {table_name}")
            else:
                raise


    def _push_pending_changes(self):
        """
        رفع التغييرات المحلية المعلقة للسحابة قبل السحب
        """
        if not self.is_online:
            return

        logger.info("📤 جاري رفع التغييرات المحلية...")

        for table in self.TABLES:
            try:
                self._push_table_changes(table)
            except Exception as e:
                logger.error(f"❌ خطأ في رفع {table}: {e}")

    def _push_table_changes(self, table_name: str):
        """رفع تغييرات جدول واحد"""
        cursor = self.repo.sqlite_cursor
        conn = self.repo.sqlite_conn
        unique_field = self.UNIQUE_FIELDS.get(table_name, 'name')

        # جلب السجلات غير المتزامنة
        cursor.execute(f"""
            SELECT * FROM {table_name}
            WHERE sync_status != 'synced' OR sync_status IS NULL
        """)
        unsynced = cursor.fetchall()

        if not unsynced:
            return

        collection = self.repo.mongo_db[table_name]
        pushed = 0

        for row in unsynced:
            row_dict = dict(row)
            local_id = row_dict.get('id')
            mongo_id = row_dict.get('_mongo_id')
            unique_value = row_dict.get(unique_field)

            # تحضير البيانات للسحابة
            cloud_data = self._prepare_data_for_cloud(row_dict)

            try:
                if mongo_id:
                    # تحديث سجل موجود
                    from bson import ObjectId
                    collection.update_one(
                        {'_id': ObjectId(mongo_id)},
                        {'$set': cloud_data}
                    )
                else:
                    # فحص التكرار قبل الإدراج
                    existing = None
                    if unique_value:
                        existing = collection.find_one({unique_field: unique_value})

                    if existing:
                        # ربط بالسجل الموجود
                        mongo_id = str(existing['_id'])
                        collection.update_one(
                            {'_id': existing['_id']},
                            {'$set': cloud_data}
                        )
                    else:
                        # إدراج جديد
                        result = collection.insert_one(cloud_data)
                        mongo_id = str(result.inserted_id)

                # تحديث السجل المحلي
                cursor.execute(
                    f"UPDATE {table_name} SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
                    (mongo_id, local_id)
                )
                pushed += 1

            except Exception as e:
                logger.error(f"❌ فشل رفع {table_name}/{local_id}: {e}")

        conn.commit()
        if pushed > 0:
            logger.info(f"📤 {table_name}: رفع {pushed} سجل")

    def _prepare_data_for_cloud(self, data: dict) -> dict:
        """تحضير البيانات للرفع للسحابة"""
        clean = {k: v for k, v in data.items()
                 if k not in ['id', '_mongo_id', 'sync_status']}

        # ⚡ التعامل مع logo_data
        # إذا كان logo_data فارغ و logo_path فارغ = المستخدم حذف الصورة صراحة
        # إذا كان logo_data فارغ و logo_path موجود = لا نريد الكتابة فوق السحابة
        logo_data_value = clean.get('logo_data', None)
        logo_path_value = clean.get('logo_path', None)
        
        if 'logo_data' in clean:
            if logo_data_value:
                # صورة جديدة - رفعها للسحابة
                logger.info(f"📷 رفع logo_data ({len(logo_data_value)} حرف) للسحابة")
            elif not logo_path_value:
                # logo_data فارغ و logo_path فارغ = حذف صريح للصورة
                clean['logo_data'] = ""  # إرسال قيمة فارغة صريحة للحذف
                logger.info("🗑️ حذف logo_data من السحابة (حذف صريح)")
            else:
                # logo_data فارغ لكن logo_path موجود = لا نريد الكتابة فوق السحابة
                del clean['logo_data']
                logger.debug("📷 تم تجاهل logo_data الفارغ (لن يتم الكتابة فوق السحابة)")
        
        if 'logo_path' in clean and not clean['logo_path']:
            # إذا كان logo_path فارغ، نرسل قيمة فارغة صريحة
            clean['logo_path'] = ""

        # تحويل التواريخ
        for field in ['created_at', 'last_modified', 'date', 'issue_date',
                     'due_date', 'expiry_date', 'start_date', 'end_date']:
            if field in clean and clean[field]:
                try:
                    if isinstance(clean[field], str):
                        clean[field] = datetime.fromisoformat(
                            clean[field].replace('Z', '+00:00')
                        )
                except (ValueError, TypeError):
                    pass

        # تحويل JSON strings إلى objects
        for field in ['items', 'lines', 'data', 'milestones']:
            if field in clean and clean[field]:
                try:
                    if isinstance(clean[field], str):
                        clean[field] = json.loads(clean[field])
                except (json.JSONDecodeError, TypeError):
                    pass

        return clean

    def _sync_users_from_cloud(self):
        """مزامنة المستخدمين ثنائية الاتجاه (من وإلى السحابة)"""
        try:
            cursor = self.repo.sqlite_cursor
            conn = self.repo.sqlite_conn

            # === 1. رفع المستخدمين المحليين الجدد/المعدلين إلى السحابة ===
            logger.info("📤 جاري رفع المستخدمين المحليين إلى السحابة...")
            cursor.execute("""
                SELECT * FROM users 
                WHERE sync_status IN ('new_offline', 'modified_offline', 'pending')
                   OR _mongo_id IS NULL
            """)
            local_pending = cursor.fetchall()

            uploaded_count = 0
            for row in local_pending:
                user_data = dict(row)
                username = user_data.get('username')
                local_id = user_data.get('id')

                existing_cloud = self.repo.mongo_db.users.find_one({'username': username})

                if existing_cloud:
                    mongo_id = str(existing_cloud['_id'])
                    update_data = {
                        'full_name': user_data.get('full_name'),
                        'email': user_data.get('email'),
                        'role': user_data.get('role'),
                        'is_active': bool(user_data.get('is_active', 1)),
                        'last_modified': datetime.now()
                    }
                    if user_data.get('password_hash'):
                        update_data['password_hash'] = user_data['password_hash']

                    self.repo.mongo_db.users.update_one(
                        {'_id': existing_cloud['_id']},
                        {'$set': update_data}
                    )
                    cursor.execute(
                        "UPDATE users SET _mongo_id=?, sync_status='synced' WHERE id=?",
                        (mongo_id, local_id)
                    )
                    uploaded_count += 1
                else:
                    new_user = {
                        'username': username,
                        'password_hash': user_data.get('password_hash'),
                        'full_name': user_data.get('full_name'),
                        'email': user_data.get('email'),
                        'role': user_data.get('role', 'sales'),
                        'is_active': bool(user_data.get('is_active', 1)),
                        'created_at': datetime.now(),
                        'last_modified': datetime.now()
                    }
                    result = self.repo.mongo_db.users.insert_one(new_user)
                    mongo_id = str(result.inserted_id)
                    cursor.execute(
                        "UPDATE users SET _mongo_id=?, sync_status='synced' WHERE id=?",
                        (mongo_id, local_id)
                    )
                    uploaded_count += 1

            if uploaded_count > 0:
                conn.commit()
                logger.info(f"📤 تم رفع {uploaded_count} مستخدم للسحابة")

            # === 2. تنزيل المستخدمين من السحابة ===
            logger.info("📥 جاري تنزيل المستخدمين من السحابة...")
            cloud_users = list(self.repo.mongo_db.users.find())
            if not cloud_users:
                return

            downloaded_count = 0
            for u in cloud_users:
                mongo_id = str(u['_id'])
                username = u.get('username')

                for field in ['created_at', 'last_modified', 'last_login']:
                    if field in u and hasattr(u[field], 'isoformat'):
                        u[field] = u[field].isoformat()

                cursor.execute(
                    "SELECT id, sync_status FROM users WHERE _mongo_id = ? OR username = ?",
                    (mongo_id, username)
                )
                exists = cursor.fetchone()

                if exists:
                    if exists[1] not in ('modified_offline', 'new_offline'):
                        cursor.execute("""
                            UPDATE users SET
                                full_name=?, email=?, role=?, is_active=?,
                                password_hash=?, _mongo_id=?, sync_status='synced',
                                last_modified=?
                            WHERE id=?
                        """, (
                            u.get('full_name'), u.get('email'), u.get('role'),
                            u.get('is_active', 1), u.get('password_hash'),
                            mongo_id, u.get('last_modified', datetime.now().isoformat()),
                            exists[0]
                        ))
                        downloaded_count += 1
                else:
                    cursor.execute("""
                        INSERT INTO users (
                            _mongo_id, username, full_name, email, role,
                            password_hash, is_active, sync_status, created_at, last_modified
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'synced', ?, ?)
                    """, (
                        mongo_id, username, u.get('full_name'), u.get('email'),
                        u.get('role'), u.get('password_hash'), u.get('is_active', 1),
                        u.get('created_at', datetime.now().isoformat()),
                        u.get('last_modified', datetime.now().isoformat())
                    ))
                    downloaded_count += 1

            conn.commit()
            logger.info(f"✅ تم مزامنة المستخدمين (رفع: {uploaded_count}, تنزيل: {downloaded_count})")

        except Exception as e:
            logger.error(f"❌ خطأ في مزامنة المستخدمين: {e}")

    # ==========================================
    # دوال التنظيف وإزالة التكرارات
    # ==========================================

    def remove_duplicates(self, table_name: str | None = None) -> dict[str, int]:
        """
        إزالة التكرارات من الجداول
        يحتفظ بالسجل الأقدم (أقل id) ويحذف الباقي
        """
        tables = [table_name] if table_name else self.TABLES
        results = {}

        cursor = self.repo.sqlite_cursor
        conn = self.repo.sqlite_conn

        for table in tables:
            try:
                unique_field = self.UNIQUE_FIELDS.get(table, 'name')
                
                # البحث عن التكرارات
                cursor.execute(f"""
                    SELECT {unique_field}, COUNT(*) as cnt, MIN(id) as keep_id
                    FROM {table}
                    WHERE {unique_field} IS NOT NULL
                    GROUP BY {unique_field}
                    HAVING cnt > 1
                """)
                duplicates = cursor.fetchall()

                deleted = 0
                for dup in duplicates:
                    unique_value = dup[0]
                    keep_id = dup[2]

                    # حذف التكرارات (الاحتفاظ بالأقدم)
                    cursor.execute(f"""
                        DELETE FROM {table}
                        WHERE {unique_field} = ? AND id != ?
                    """, (unique_value, keep_id))
                    deleted += cursor.rowcount

                conn.commit()
                results[table] = deleted

                if deleted > 0:
                    logger.info(f"🗑️ {table}: حذف {deleted} سجل مكرر")

            except Exception as e:
                logger.error(f"❌ خطأ في إزالة تكرارات {table}: {e}")
                results[table] = 0

        return results

    def force_full_resync(self) -> dict[str, Any]:
        """
        إعادة مزامنة كاملة قسرية
        1. حذف كل البيانات المحلية
        2. إعادة تحميل من السحابة
        """
        if not self.is_online:
            return {'success': False, 'reason': 'offline'}

        logger.warning("⚠️ بدء إعادة المزامنة الكاملة القسرية...")

        cursor = self.repo.sqlite_cursor
        conn = self.repo.sqlite_conn

        # حذف البيانات المحلية (ما عدا المستخدمين)
        for table in self.TABLES:
            try:
                cursor.execute(f"DELETE FROM {table}")
                logger.info(f"🗑️ تم مسح {table}")
            except Exception as e:
                logger.error(f"❌ خطأ في مسح {table}: {e}")

        conn.commit()

        # إعادة التحميل من السحابة
        return self.full_sync_from_cloud()

    def get_sync_status(self) -> dict[str, Any]:
        """الحصول على حالة المزامنة"""
        cursor = self.repo.sqlite_cursor
        status = {
            'is_online': self.is_online,
            'is_syncing': self._is_syncing,
            'tables': {}
        }

        for table in self.TABLES:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                total = cursor.fetchone()[0]

                cursor.execute(f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE sync_status != 'synced' OR sync_status IS NULL
                """)
                pending = cursor.fetchone()[0]

                status['tables'][table] = {
                    'total': total,
                    'pending': pending,
                    'synced': total - pending
                }
            except Exception:
                status['tables'][table] = {'total': 0, 'pending': 0, 'synced': 0}

        return status


def create_unified_sync_manager(repository) -> UnifiedSyncManager:
    """إنشاء مدير مزامنة موحد"""
    return UnifiedSyncManagerV3(repository)


    def remove_cloud_duplicates(self) -> dict[str, int]:
        """
        إزالة التكرارات من MongoDB
        يحتفظ بالسجل الأقدم (بناءً على created_at)
        """
        if not self.is_online:
            return {}

        results = {}
        logger.info("🧹 جاري تنظيف التكرارات من السحابة...")

        for table in self.TABLES:
            try:
                deleted = self._remove_cloud_table_duplicates(table)
                results[table] = deleted
                if deleted > 0:
                    logger.info(f"🗑️ {table}: حذف {deleted} سجل مكرر من السحابة")
            except Exception as e:
                logger.error(f"❌ خطأ في تنظيف {table} من السحابة: {e}")
                results[table] = 0

        return results

    def _remove_cloud_table_duplicates(self, table_name: str) -> int:
        """إزالة التكرارات من جدول واحد في MongoDB"""
        unique_field = self.UNIQUE_FIELDS.get(table_name, 'name')
        collection = self.repo.mongo_db[table_name]

        # البحث عن التكرارات باستخدام aggregation
        pipeline = [
            {"$group": {
                "_id": f"${unique_field}",
                "count": {"$sum": 1},
                "docs": {"$push": {"_id": "$_id", "created_at": "$created_at"}}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]

        duplicates = list(collection.aggregate(pipeline))
        deleted = 0

        for dup in duplicates:
            docs = dup['docs']
            # ترتيب حسب created_at (الأقدم أولاً)
            docs.sort(key=lambda x: x.get('created_at') or datetime.min)

            # حذف كل السجلات ما عدا الأول
            for doc in docs[1:]:
                collection.delete_one({'_id': doc['_id']})
                deleted += 1

        return deleted

    def full_cleanup_and_sync(self) -> dict[str, Any]:
        """
        تنظيف كامل ومزامنة:
        1. تنظيف التكرارات من MongoDB
        2. تنظيف التكرارات المحلية
        3. مزامنة كاملة
        """
        results = {
            'cloud_cleanup': {},
            'local_cleanup': {},
            'sync': {}
        }

        if self.is_online:
            # تنظيف السحابة
            logger.info("☁️ جاري تنظيف السحابة...")
            results['cloud_cleanup'] = self.remove_cloud_duplicates()

        # تنظيف المحلي
        logger.info("💾 جاري تنظيف القاعدة المحلية...")
        results['local_cleanup'] = self.remove_duplicates()

        # مزامنة
        if self.is_online:
            logger.info("🔄 جاري المزامنة...")
            results['sync'] = self.full_sync_from_cloud()

        return results
