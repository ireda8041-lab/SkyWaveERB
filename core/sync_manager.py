# الملف: core/sync_manager.py

"""
نظام إدارة المزامنة المحسّن
يدير عمليات المزامنة بين SQLite و MongoDB بكفاءة عالية
"""

import threading
import time
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from queue import PriorityQueue
from .schemas import SyncQueueItem, SyncOperation, SyncPriority, SyncStatus
from .logger import get_logger
from .error_handler import ErrorHandler

logger = get_logger(__name__)
error_handler = ErrorHandler()


class SyncManager:
    """
    مدير المزامنة الذكي
    - يدير قائمة انتظار المزامنة
    - يعيد المحاولة عند الفشل
    - يدعم الأولويات
    """
    
    def __init__(self, repository):
        """
        تهيئة مدير المزامنة
        
        Args:
            repository: كائن Repository للوصول للبيانات
        """
        self.repository = repository
        self.sync_queue = PriorityQueue()
        self.is_syncing = False
        self.sync_thread = None
        self.stop_flag = False
        self.stats = {
            'total_synced': 0,
            'total_failed': 0,
            'last_sync_time': None
        }
        
        logger.info("تم تهيئة SyncManager")
    
    def add_to_queue(self, entity_type: str, entity_id: str, 
                     operation: SyncOperation, 
                     priority: SyncPriority = SyncPriority.MEDIUM,
                     data: Optional[Dict[str, Any]] = None):
        """
        إضافة عملية للمزامنة في قائمة الانتظار
        
        Args:
            entity_type: نوع الكيان (clients, projects, etc.)
            entity_id: معرف الكيان
            operation: نوع العملية (create, update, delete)
            priority: أولوية المزامنة
            data: البيانات المراد مزامنتها
        """
        try:
            # إنشاء عنصر قائمة الانتظار
            sync_item = SyncQueueItem(
                entity_type=entity_type,
                entity_id=entity_id,
                operation=operation,
                priority=priority,
                data=data
            )
            
            # حفظ في قاعدة البيانات المحلية
            self._save_sync_item(sync_item)
            
            # إضافة للقائمة (الأولوية: HIGH=0, MEDIUM=1, LOW=2)
            priority_value = {'high': 0, 'medium': 1, 'low': 2}[priority.value]
            self.sync_queue.put((priority_value, sync_item))
            
            logger.debug(f"تمت إضافة عملية مزامنة: {entity_type}/{entity_id} - {operation.value}")
            
        except Exception as e:
            error_handler.handle_exception(e, f"فشل إضافة عملية المزامنة: {entity_type}/{entity_id}")
    
    def _save_sync_item(self, item: SyncQueueItem):
        """حفظ عنصر المزامنة في قاعدة البيانات المحلية"""
        try:
            cursor = self.repository.sqlite_cursor
            
            cursor.execute("""
                INSERT INTO sync_queue (
                    entity_type, entity_id, operation, priority, status,
                    retry_count, max_retries, data, created_at, last_modified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.entity_type,
                item.entity_id,
                item.operation.value,
                item.priority.value,
                item.status.value,
                item.retry_count,
                item.max_retries,
                str(item.data) if item.data else None,
                item.created_at.isoformat(),
                item.last_modified.isoformat()
            ))
            
            self.repository.sqlite_conn.commit()
            
        except Exception as e:
            logger.error(f"فشل حفظ عنصر المزامنة: {str(e)}")
    
    def start_sync(self):
        """بدء عملية المزامنة في خيط منفصل"""
        if self.is_syncing:
            logger.warning("المزامنة قيد التشغيل بالفعل")
            return
        
        self.stop_flag = False
        self.sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
        self.sync_thread.start()
        logger.info("تم بدء عملية المزامنة")
    
    def stop_sync(self):
        """إيقاف عملية المزامنة"""
        self.stop_flag = True
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
        logger.info("تم إيقاف عملية المزامنة")
    
    def _sync_worker(self):
        """
        العامل الذي يقوم بالمزامنة الفعلية
        يعمل في خيط منفصل
        """
        self.is_syncing = True
        
        try:
            # التحقق من الاتصال بالإنترنت
            if not self.repository.online:
                logger.warning("لا يوجد اتصال بالإنترنت")
                return
            
            # معالجة جميع العناصر في قائمة الانتظار مرة واحدة
            while not self.sync_queue.empty() and not self.stop_flag:
                priority, sync_item = self.sync_queue.get()
                self._process_sync_item(sync_item)
            
            logger.info("اكتملت عملية المزامنة")
        
        except Exception as e:
            error_handler.handle_exception(e, "خطأ في عملية المزامنة")
        
        finally:
            self.is_syncing = False
    
    def _process_sync_item(self, item: SyncQueueItem):
        """
        معالجة عنصر مزامنة واحد
        
        Args:
            item: عنصر المزامنة
        """
        try:
            logger.info(f"مزامنة: {item.entity_type}/{item.entity_id} - {item.operation.value}")
            
            # تحديث حالة العنصر
            item.status = SyncStatus.IN_PROGRESS
            item.last_attempt = datetime.now()
            self._update_sync_item(item)
            
            # تنفيذ العملية حسب النوع
            success = False
            
            if item.operation == SyncOperation.CREATE:
                success = self._sync_create(item)
            elif item.operation == SyncOperation.UPDATE:
                success = self._sync_update(item)
            elif item.operation == SyncOperation.DELETE:
                success = self._sync_delete(item)
            
            if success:
                # نجحت المزامنة
                item.status = SyncStatus.COMPLETED
                self._update_sync_item(item)
                self._delete_sync_item(item)
                self.stats['total_synced'] += 1
                self.stats['last_sync_time'] = datetime.now()
                logger.info(f"تمت المزامنة بنجاح: {item.entity_type}/{item.entity_id}")
            else:
                # فشلت المزامنة
                self._handle_sync_failure(item)
        
        except Exception as e:
            error_handler.handle_exception(e, f"فشل معالجة عنصر المزامنة: {item.entity_type}/{item.entity_id}")
            self._handle_sync_failure(item)
    
    def _sync_create(self, item: SyncQueueItem) -> bool:
        """مزامنة عملية إنشاء"""
        try:
            # الحصول على البيانات من SQLite
            data = self._get_entity_data(item.entity_type, item.entity_id)
            if not data:
                logger.error(f"لم يتم العثور على البيانات: {item.entity_type}/{item.entity_id}")
                return False
            
            # إنشاء في MongoDB
            collection = self.repository.mongo_db[item.entity_type]
            result = collection.insert_one(data)
            
            # تحديث _mongo_id في SQLite
            self._update_mongo_id(item.entity_type, item.entity_id, str(result.inserted_id))
            
            return True
        
        except Exception as e:
            logger.error(f"فشل مزامنة الإنشاء: {str(e)}")
            return False
    
    def _sync_update(self, item: SyncQueueItem) -> bool:
        """مزامنة عملية تحديث"""
        try:
            # الحصول على البيانات من SQLite
            data = self._get_entity_data(item.entity_type, item.entity_id)
            if not data:
                return False
            
            # التحديث في MongoDB
            collection = self.repository.mongo_db[item.entity_type]
            mongo_id = data.get('_mongo_id')
            
            if not mongo_id:
                logger.error(f"لا يوجد _mongo_id للكيان: {item.entity_type}/{item.entity_id}")
                return False
            
            from bson import ObjectId
            collection.update_one(
                {'_id': ObjectId(mongo_id)},
                {'$set': data}
            )
            
            return True
        
        except Exception as e:
            logger.error(f"فشل مزامنة التحديث: {str(e)}")
            return False
    
    def _sync_delete(self, item: SyncQueueItem) -> bool:
        """مزامنة عملية حذف"""
        try:
            # الحصول على _mongo_id
            mongo_id = self._get_mongo_id(item.entity_type, item.entity_id)
            if not mongo_id:
                return True  # لا يوجد في MongoDB، اعتبرها ناجحة
            
            # الحذف من MongoDB
            collection = self.repository.mongo_db[item.entity_type]
            from bson import ObjectId
            collection.delete_one({'_id': ObjectId(mongo_id)})
            
            return True
        
        except Exception as e:
            logger.error(f"فشل مزامنة الحذف: {str(e)}")
            return False
    
    def _handle_sync_failure(self, item: SyncQueueItem):
        """معالجة فشل المزامنة"""
        item.retry_count += 1
        
        if item.retry_count >= item.max_retries:
            # وصلنا للحد الأقصى من المحاولات
            item.status = SyncStatus.FAILED
            self.stats['total_failed'] += 1
            logger.error(f"فشلت المزامنة بعد {item.max_retries} محاولات: {item.entity_type}/{item.entity_id}")
        else:
            # إعادة المحاولة
            item.status = SyncStatus.PENDING
            priority_value = {'high': 0, 'medium': 1, 'low': 2}[item.priority.value]
            self.sync_queue.put((priority_value, item))
            logger.warning(f"إعادة محاولة المزامنة ({item.retry_count}/{item.max_retries}): {item.entity_type}/{item.entity_id}")
        
        self._update_sync_item(item)
    
    def _get_entity_data(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """الحصول على بيانات الكيان من SQLite"""
        try:
            cursor = self.repository.sqlite_cursor
            cursor.execute(f"SELECT * FROM {entity_type} WHERE id = ?", (entity_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
        
        except Exception as e:
            logger.error(f"فشل الحصول على بيانات الكيان: {str(e)}")
            return None
    
    def _get_mongo_id(self, entity_type: str, entity_id: str) -> Optional[str]:
        """الحصول على _mongo_id من SQLite"""
        try:
            cursor = self.repository.sqlite_cursor
            cursor.execute(f"SELECT _mongo_id FROM {entity_type} WHERE id = ?", (entity_id,))
            row = cursor.fetchone()
            
            if row:
                return row['_mongo_id']
            return None
        
        except Exception as e:
            logger.error(f"فشل الحصول على _mongo_id: {str(e)}")
            return None
    
    def _update_mongo_id(self, entity_type: str, entity_id: str, mongo_id: str):
        """تحديث _mongo_id في SQLite"""
        try:
            cursor = self.repository.sqlite_cursor
            cursor.execute(
                f"UPDATE {entity_type} SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
                (mongo_id, entity_id)
            )
            self.repository.sqlite_conn.commit()
        
        except Exception as e:
            logger.error(f"فشل تحديث _mongo_id: {str(e)}")
    
    def _update_sync_item(self, item: SyncQueueItem):
        """تحديث عنصر المزامنة في قاعدة البيانات"""
        try:
            cursor = self.repository.sqlite_cursor
            cursor.execute("""
                UPDATE sync_queue 
                SET status = ?, retry_count = ?, last_attempt = ?, last_modified = ?
                WHERE entity_type = ? AND entity_id = ?
            """, (
                item.status.value,
                item.retry_count,
                item.last_attempt.isoformat() if item.last_attempt else None,
                datetime.now().isoformat(),
                item.entity_type,
                item.entity_id
            ))
            self.repository.sqlite_conn.commit()
        
        except Exception as e:
            logger.error(f"فشل تحديث عنصر المزامنة: {str(e)}")
    
    def _delete_sync_item(self, item: SyncQueueItem):
        """حذف عنصر المزامنة من قاعدة البيانات"""
        try:
            cursor = self.repository.sqlite_cursor
            cursor.execute("""
                DELETE FROM sync_queue 
                WHERE entity_type = ? AND entity_id = ?
            """, (item.entity_type, item.entity_id))
            self.repository.sqlite_conn.commit()
        
        except Exception as e:
            logger.error(f"فشل حذف عنصر المزامنة: {str(e)}")
    
    def get_pending_count(self) -> int:
        """الحصول على عدد العمليات المعلقة"""
        try:
            cursor = self.repository.sqlite_cursor
            cursor.execute("SELECT COUNT(*) FROM sync_queue WHERE status = 'pending'")
            result = cursor.fetchone()
            return result[0] if result else 0
        
        except Exception as e:
            logger.error(f"فشل الحصول على عدد العمليات المعلقة: {str(e)}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """الحصول على إحصائيات المزامنة"""
        return {
            'is_syncing': self.is_syncing,
            'pending_count': self.get_pending_count(),
            'total_synced': self.stats['total_synced'],
            'total_failed': self.stats['total_failed'],
            'last_sync_time': self.stats['last_sync_time']
        }
    
    def load_pending_items(self):
        """تحميل العناصر المعلقة من قاعدة البيانات عند بدء التطبيق"""
        try:
            cursor = self.repository.sqlite_cursor
            cursor.execute("""
                SELECT * FROM sync_queue 
                WHERE status IN ('pending', 'failed')
                ORDER BY priority, created_at
            """)
            
            rows = cursor.fetchall()
            for row in rows:
                sync_item = SyncQueueItem(
                    entity_type=row['entity_type'],
                    entity_id=row['entity_id'],
                    operation=SyncOperation(row['operation']),
                    priority=SyncPriority(row['priority']),
                    status=SyncStatus(row['status']),
                    retry_count=row['retry_count'],
                    max_retries=row['max_retries']
                )
                
                priority_value = {'high': 0, 'medium': 1, 'low': 2}[sync_item.priority.value]
                self.sync_queue.put((priority_value, sync_item))
            
            logger.info(f"تم تحميل {len(rows)} عملية مزامنة معلقة")
        
        except Exception as e:
            logger.error(f"فشل تحميل العمليات المعلقة: {str(e)}")
    
    def pull_and_merge_all_data(self):
        """
        سحب ودمج جميع البيانات من MongoDB إلى SQLite
        يتم استدعاؤها عند بدء التطبيق لضمان تزامن البيانات
        """
        if not self.repository.online:
            logger.warning("لا يوجد اتصال بالإنترنت - تخطي سحب البيانات")
            return
        
        try:
            logger.info("بدء سحب ودمج البيانات من السحابة...")
            
            # سحب المستخدمين
            self._pull_and_merge_users()
            
            # سحب العملاء
            self._pull_and_merge_collection('clients')
            
            # سحب الحسابات
            self._pull_and_merge_collection('accounts')
            
            # سحب الخدمات
            self._pull_and_merge_collection('services')
            
            # سحب المشاريع
            self._pull_and_merge_collection('projects')
            
            # سحب الفواتير
            self._pull_and_merge_collection('invoices')
            
            # سحب المصروفات
            self._pull_and_merge_collection('expenses')
            
            # سحب قيود اليومية
            self._pull_and_merge_collection('journal_entries')
            
            # سحب الدفعات
            self._pull_and_merge_collection('payments')
            
            # سحب عروض الأسعار
            self._pull_and_merge_collection('quotations')
            
            # سحب العملات
            self._pull_and_merge_collection('currencies')
            
            logger.info("✅ اكتمل سحب ودمج جميع البيانات بنجاح")
            
        except Exception as e:
            error_handler.handle_exception(e, "فشل سحب ودمج البيانات من السحابة")
    
    def _pull_and_merge_users(self):
        """سحب ودمج المستخدمين من MongoDB"""
        try:
            print("INFO: [SyncManager] جاري سحب المستخدمين من MongoDB...")
            cloud_users = list(self.repository.mongo_db.users.find())
            print(f"INFO: [SyncManager] تم العثور على {len(cloud_users)} مستخدم في السحابة")
            conn = self.repository.sqlite_conn
            cursor = conn.cursor()
            
            for u in cloud_users:
                mongo_id = str(u['_id'])
                username = u.get('username')
                
                # تحويل datetime إلى string
                created_at = u.get('created_at')
                if hasattr(created_at, 'isoformat'):
                    created_at = created_at.isoformat()
                elif created_at is None:
                    created_at = datetime.now().isoformat()
                
                last_modified = u.get('last_modified')
                if hasattr(last_modified, 'isoformat'):
                    last_modified = last_modified.isoformat()
                elif last_modified is None:
                    last_modified = datetime.now().isoformat()
                
                last_login = u.get('last_login')
                if last_login and hasattr(last_login, 'isoformat'):
                    last_login = last_login.isoformat()
                
                # التحقق من وجود المستخدم محلياً
                cursor.execute(
                    "SELECT id FROM users WHERE _mongo_id = ? OR username = ?",
                    (mongo_id, username)
                )
                exists = cursor.fetchone()
                
                if exists:
                    # تحديث السجل الموجود
                    cursor.execute("""
                        UPDATE users SET
                            full_name=?, email=?, role=?, is_active=?, 
                            password_hash=?, _mongo_id=?, sync_status='synced',
                            last_modified=?
                        WHERE id=?
                    """, (
                        u.get('full_name'), u.get('email'), u.get('role'),
                        u.get('is_active', 1), u.get('password_hash'),
                        mongo_id, last_modified, exists[0]
                    ))
                else:
                    # إدراج سجل جديد
                    cursor.execute("""
                        INSERT INTO users (
                            _mongo_id, username, full_name, email, role,
                            password_hash, is_active, sync_status, created_at, last_modified, last_login
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'synced', ?, ?, ?)
                    """, (
                        mongo_id, username, u.get('full_name'), u.get('email'),
                        u.get('role'), u.get('password_hash'), u.get('is_active', 1),
                        created_at, last_modified, last_login
                    ))
            
            conn.commit()
            print(f"INFO: [SyncManager] ✅ تم مزامنة {len(cloud_users)} مستخدم من السحابة")
            logger.info(f"✅ تم مزامنة {len(cloud_users)} مستخدم من السحابة")
            
        except Exception as e:
            print(f"ERROR: [SyncManager] ❌ فشل مزامنة المستخدمين: {e}")
            logger.error(f"❌ فشل مزامنة المستخدمين: {e}")
    
    def _pull_and_merge_collection(self, collection_name: str):
        """سحب ودمج مجموعة من MongoDB إلى SQLite"""
        try:
            cloud_data = list(self.repository.mongo_db[collection_name].find())
            if not cloud_data:
                print(f"INFO: [SyncManager] لا توجد بيانات في {collection_name}")
                return
            
            print(f"INFO: [SyncManager] جاري مزامنة {len(cloud_data)} سجل من {collection_name}...")
            
            conn = self.repository.sqlite_conn
            cursor = conn.cursor()
            
            for item in cloud_data:
                mongo_id = str(item['_id'])
                
                # تحويل datetime إلى string
                for field in ['created_at', 'last_modified', 'date', 'issue_date', 'due_date', 
                             'expiry_date', 'start_date', 'end_date', 'last_attempt', 'expires_at']:
                    if field in item and hasattr(item[field], 'isoformat'):
                        item[field] = item[field].isoformat()
                
                # تحويل القوائم والكائنات إلى JSON
                for field in ['items', 'lines', 'data']:
                    if field in item and isinstance(item[field], (list, dict)):
                        item[field] = json.dumps(item[field])
                
                # التحقق من وجود السجل
                cursor.execute(
                    f"SELECT id FROM {collection_name} WHERE _mongo_id = ?",
                    (mongo_id,)
                )
                exists = cursor.fetchone()
                
                # إزالة الحقول غير المطلوبة
                item.pop('_id', None)
                item.pop('id', None)  # إزالة id إذا كان موجوداً
                item.pop('mongo_id', None)  # إزالة mongo_id القديم
                
                # التأكد من وجود الحقول المطلوبة
                if 'created_at' not in item or item['created_at'] is None:
                    item['created_at'] = datetime.now().isoformat()
                if 'last_modified' not in item or item['last_modified'] is None:
                    item['last_modified'] = datetime.now().isoformat()
                
                item['_mongo_id'] = mongo_id
                item['sync_status'] = 'synced'
                
                # الحصول على أعمدة الجدول الفعلية
                cursor.execute(f"PRAGMA table_info({collection_name})")
                table_columns = {row[1] for row in cursor.fetchall()}
                
                # تصفية الحقول لتشمل فقط الأعمدة الموجودة
                filtered_item = {k: v for k, v in item.items() if k in table_columns}
                
                if exists:
                    # تحديث السجل الموجود
                    set_clause = ', '.join([f"{k}=?" for k in filtered_item.keys()])
                    values = list(filtered_item.values()) + [exists[0]]
                    cursor.execute(
                        f"UPDATE {collection_name} SET {set_clause} WHERE id=?",
                        values
                    )
                else:
                    # إدراج سجل جديد
                    columns = ', '.join(filtered_item.keys())
                    placeholders = ', '.join(['?' for _ in filtered_item])
                    cursor.execute(
                        f"INSERT INTO {collection_name} ({columns}) VALUES ({placeholders})",
                        list(filtered_item.values())
                    )
            
            conn.commit()
            print(f"INFO: [SyncManager] ✅ تم مزامنة {len(cloud_data)} سجل من {collection_name}")
            logger.info(f"✅ تم مزامنة {len(cloud_data)} سجل من {collection_name}")
            
        except Exception as e:
            print(f"ERROR: [SyncManager] ❌ فشل مزامنة {collection_name}: {e}")
            logger.error(f"❌ فشل مزامنة {collection_name}: {e}")


    # ==========================================
    # نظام المزامنة الذكي ثنائي الاتجاه
    # ==========================================
    
    def start_background_sync(self):
        """
        بدء المزامنة التلقائية في الخلفية
        تعمل في thread منفصل لعدم تجميد الواجهة
        """
        if not self.repository.online:
            print("INFO: [SyncManager] غير متصل - تخطي المزامنة التلقائية")
            return
        
        print("🔄 [SyncManager] بدء المزامنة التلقائية في الخلفية...")
        thread = threading.Thread(target=self._perform_full_sync, daemon=True)
        thread.start()
    
    def _perform_full_sync(self):
        """
        تنفيذ المزامنة الكاملة ثنائية الاتجاه
        1. رفع التغييرات المحلية للسحابة (Push)
        2. سحب التغييرات من السحابة (Pull)
        """
        try:
            print("🔄 [SyncManager] === بدء المزامنة الكاملة ===")
            
            # 1. رفع التغييرات المحلية أولاً
            self._push_local_changes()
            
            # 2. سحب التغييرات من السحابة
            self.pull_and_merge_all_data()
            
            print("✅ [SyncManager] === اكتملت المزامنة الكاملة ===")
            self.stats['last_sync_time'] = datetime.now()
            
        except Exception as e:
            print(f"❌ [SyncManager] خطأ في المزامنة: {e}")
            logger.error(f"خطأ في المزامنة الكاملة: {e}")
    
    def _push_local_changes(self):
        """
        رفع التغييرات المحلية غير المتزامنة للسحابة
        يبحث عن السجلات التي sync_status != 'synced'
        """
        if not self.repository.online:
            return
        
        print("📤 [SyncManager] جاري رفع التغييرات المحلية...")
        
        tables = ['clients', 'projects', 'services', 'accounts', 
                  'expenses', 'invoices', 'payments', 'journal_entries', 
                  'quotations', 'currencies']
        
        total_pushed = 0
        for table in tables:
            pushed = self._push_table_changes(table)
            total_pushed += pushed
        
        print(f"📤 [SyncManager] تم رفع {total_pushed} سجل للسحابة")
    
    def _push_table_changes(self, table_name: str) -> int:
        """
        رفع تغييرات جدول معين للسحابة مع منع التكرارات
        """
        try:
            cursor = self.repository.sqlite_cursor
            conn = self.repository.sqlite_conn
            
            # جلب السجلات غير المتزامنة
            cursor.execute(f"""
                SELECT * FROM {table_name} 
                WHERE sync_status != 'synced' OR sync_status IS NULL
            """)
            unsynced = cursor.fetchall()
            
            if not unsynced:
                return 0
            
            collection = self.repository.mongo_db[table_name]
            pushed = 0
            
            # الحصول على الحقل الفريد للجدول
            unique_field = self._get_unique_field(table_name)
            
            for row in unsynced:
                row_dict = dict(row)
                local_id = row_dict.get('id')
                mongo_id = row_dict.get('_mongo_id')
                
                # تنظيف البيانات قبل الرفع
                clean_data = self._prepare_data_for_cloud(row_dict, table_name)
                
                if mongo_id:
                    # السجل موجود في السحابة - تحديث
                    try:
                        from bson import ObjectId
                        collection.update_one(
                            {'_id': ObjectId(mongo_id)},
                            {'$set': clean_data}
                        )
                        cursor.execute(
                            f"UPDATE {table_name} SET sync_status = 'synced' WHERE id = ?",
                            (local_id,)
                        )
                        pushed += 1
                    except Exception as e:
                        print(f"    ⚠️ فشل تحديث {table_name}/{local_id}: {e}")
                else:
                    # سجل جديد - فحص التكرار أولاً
                    unique_value = row_dict.get(unique_field)
                    existing = None
                    
                    if unique_value:
                        existing = collection.find_one({unique_field: unique_value})
                    
                    if existing:
                        # السجل موجود بالفعل - ربط فقط
                        new_mongo_id = str(existing['_id'])
                        cursor.execute(
                            f"UPDATE {table_name} SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
                            (new_mongo_id, local_id)
                        )
                    else:
                        # سجل جديد فعلاً - إدراج
                        try:
                            result = collection.insert_one(clean_data)
                            new_mongo_id = str(result.inserted_id)
                            cursor.execute(
                                f"UPDATE {table_name} SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
                                (new_mongo_id, local_id)
                            )
                            pushed += 1
                        except Exception as e:
                            print(f"    ⚠️ فشل إدراج {table_name}/{local_id}: {e}")
            
            conn.commit()
            if pushed > 0:
                print(f"  📤 {table_name}: رفع {pushed} سجل")
            return pushed
            
        except Exception as e:
            print(f"  ❌ خطأ في رفع {table_name}: {e}")
            return 0
    
    def _get_unique_field(self, table_name: str) -> str:
        """الحصول على الحقل الفريد لكل جدول"""
        unique_fields = {
            'clients': 'name',
            'projects': 'name',
            'services': 'name',
            'accounts': 'code',
            'expenses': 'id',
            'invoices': 'invoice_number',
            'payments': 'id',
            'journal_entries': 'id',
            'quotations': 'quote_number',
            'currencies': 'code',
            'users': 'username'
        }
        return unique_fields.get(table_name, 'name')
    
    def _prepare_data_for_cloud(self, data: dict, table_name: str) -> dict:
        """تحضير البيانات للرفع للسحابة"""
        # إزالة الحقول المحلية
        clean = {k: v for k, v in data.items() 
                 if k not in ['id', '_mongo_id', 'sync_status']}
        
        # تحويل التواريخ
        for field in ['created_at', 'last_modified', 'date', 'issue_date', 
                     'due_date', 'expiry_date', 'start_date', 'end_date']:
            if field in clean and clean[field]:
                try:
                    if isinstance(clean[field], str):
                        clean[field] = datetime.fromisoformat(
                            clean[field].replace('Z', '+00:00')
                        )
                except:
                    pass
        
        # تحويل JSON strings إلى objects
        for field in ['items', 'lines', 'data']:
            if field in clean and clean[field]:
                try:
                    if isinstance(clean[field], str):
                        clean[field] = json.loads(clean[field])
                except:
                    pass
        
        return clean
    
    def smart_merge_collection(self, collection_name: str):
        """
        دمج ذكي لمجموعة معينة مع منع التكرارات
        يبحث بـ: 1. mongo_id  2. الحقل الفريد (name/code)
        """
        if not self.repository.online:
            return
        
        try:
            cloud_data = list(self.repository.mongo_db[collection_name].find())
            if not cloud_data:
                return
            
            cursor = self.repository.sqlite_cursor
            conn = self.repository.sqlite_conn
            unique_field = self._get_unique_field(collection_name)
            
            # الحصول على أعمدة الجدول
            cursor.execute(f"PRAGMA table_info({collection_name})")
            table_columns = {row[1] for row in cursor.fetchall()}
            
            merged = 0
            inserted = 0
            
            for item in cloud_data:
                mongo_id = str(item['_id'])
                unique_value = item.get(unique_field)
                
                # 1. البحث بـ mongo_id
                cursor.execute(
                    f"SELECT id FROM {collection_name} WHERE _mongo_id = ?",
                    (mongo_id,)
                )
                exists_by_id = cursor.fetchone()
                
                if exists_by_id:
                    # تحديث السجل الموجود
                    self._update_local_record(cursor, collection_name, 
                                             exists_by_id[0], item, table_columns)
                    merged += 1
                    continue
                
                # 2. البحث بالحقل الفريد
                if unique_value:
                    cursor.execute(
                        f"SELECT id FROM {collection_name} WHERE {unique_field} = ?",
                        (unique_value,)
                    )
                    exists_by_unique = cursor.fetchone()
                    
                    if exists_by_unique:
                        # ربط السجل المحلي بالسحابة
                        cursor.execute(
                            f"UPDATE {collection_name} SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
                            (mongo_id, exists_by_unique[0])
                        )
                        merged += 1
                        continue
                
                # 3. سجل جديد - إدراج
                self._insert_local_record(cursor, collection_name, item, 
                                         mongo_id, table_columns)
                inserted += 1
            
            conn.commit()
            if merged > 0 or inserted > 0:
                print(f"  🔄 {collection_name}: دمج {merged}، إدراج {inserted}")
                
        except Exception as e:
            print(f"  ❌ خطأ في دمج {collection_name}: {e}")
    
    def _update_local_record(self, cursor, table_name: str, local_id: int, 
                            cloud_data: dict, table_columns: set):
        """تحديث سجل محلي من بيانات السحابة"""
        # تحضير البيانات
        item = self._prepare_cloud_data_for_local(cloud_data)
        item['_mongo_id'] = str(cloud_data['_id'])
        item['sync_status'] = 'synced'
        
        # تصفية الحقول
        filtered = {k: v for k, v in item.items() if k in table_columns}
        
        if filtered:
            set_clause = ', '.join([f"{k}=?" for k in filtered.keys()])
            values = list(filtered.values()) + [local_id]
            cursor.execute(
                f"UPDATE {table_name} SET {set_clause} WHERE id=?",
                values
            )
    
    def _insert_local_record(self, cursor, table_name: str, cloud_data: dict,
                            mongo_id: str, table_columns: set):
        """إدراج سجل جديد من السحابة"""
        item = self._prepare_cloud_data_for_local(cloud_data)
        item['_mongo_id'] = mongo_id
        item['sync_status'] = 'synced'
        
        # التأكد من الحقول المطلوبة
        if 'created_at' not in item or not item['created_at']:
            item['created_at'] = datetime.now().isoformat()
        if 'last_modified' not in item or not item['last_modified']:
            item['last_modified'] = datetime.now().isoformat()
        
        # تصفية الحقول
        filtered = {k: v for k, v in item.items() if k in table_columns}
        
        if filtered:
            columns = ', '.join(filtered.keys())
            placeholders = ', '.join(['?' for _ in filtered])
            cursor.execute(
                f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
                list(filtered.values())
            )
    
    def _prepare_cloud_data_for_local(self, data: dict) -> dict:
        """تحضير بيانات السحابة للحفظ محلياً"""
        item = dict(data)
        
        # إزالة _id
        item.pop('_id', None)
        item.pop('id', None)
        
        # تحويل التواريخ
        for field in ['created_at', 'last_modified', 'date', 'issue_date', 
                     'due_date', 'expiry_date', 'start_date', 'end_date',
                     'last_attempt', 'expires_at', 'last_login']:
            if field in item and hasattr(item[field], 'isoformat'):
                item[field] = item[field].isoformat()
        
        # تحويل القوائم والكائنات إلى JSON
        for field in ['items', 'lines', 'data']:
            if field in item and isinstance(item[field], (list, dict)):
                item[field] = json.dumps(item[field])
        
        return item


# core/sync_manager.py loaded
