# الملف: core/startup_sync.py
"""
🚀 نظام المزامنة عند بدء التشغيل
================================
- يعتمد على MongoDB كمصدر رئيسي للبيانات
- يستخدم SQLite للتسريع والعمل أوفلاين
- مزامنة تلقائية عند فتح البرنامج
- رفع التغييرات المحلية للسيرفر
"""

import json
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from core.logger import get_logger

logger = get_logger(__name__)


class StartupSync:
    """
    🚀 نظام المزامنة الاحترافي عند بدء التشغيل
    
    الاستراتيجية:
    1. عرض البيانات المحلية فوراً (للسرعة)
    2. جلب البيانات من MongoDB في الخلفية
    3. رفع أي تغييرات محلية معلقة
    4. تحديث الواجهة بعد اكتمال المزامنة
    """
    
    # الجداول المدعومة للمزامنة (مطابقة تماماً لـ MongoDB Collections)
    # ترتيب المزامنة مهم: الجداول الأساسية أولاً ثم المعتمدة عليها
    SYNC_TABLES = [
        # 1. الجداول الأساسية (لا تعتمد على غيرها)
        'accounts',          # الحسابات المحاسبية
        'currencies',        # العملات
        'clients',           # العملاء
        'services',          # الخدمات
        'employees',         # الموظفين
        
        # 2. الجداول المعتمدة على الأساسية
        'projects',          # المشاريع (تعتمد على clients)
        'quotations',        # عروض الأسعار (تعتمد على clients, projects)
        'invoices',          # الفواتير (تعتمد على clients, projects)
        'payments',          # الدفعات (تعتمد على projects, clients, accounts)
        'expenses',          # المصروفات (تعتمد على accounts, projects)
        'journal_entries',   # قيود اليومية (تعتمد على accounts)
        
        # 3. الجداول الإضافية
        'tasks',             # المهام (تعتمد على projects, clients)
        'notifications',     # الإشعارات
    ]
    
    # الجداول المحمية (لا تُحذف ولا تُمسح - بيانات حساسة)
    PROTECTED_TABLES = ['users', 'settings', 'invoice_numbers', 'sync_queue']
    
    def __init__(self, repository):
        self.repo = repository
        self._is_syncing = False
        self._sync_lock = threading.RLock()
        self._callbacks: List[Callable] = []
        self._sync_stats = {
            'pulled': 0,
            'pushed': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def add_completion_callback(self, callback: Callable):
        """إضافة callback يتم استدعاؤه عند اكتمال المزامنة"""
        self._callbacks.append(callback)
    
    def start_background_sync(self, delay_seconds: int = 2):
        """
        🚀 بدء المزامنة في الخلفية
        
        Args:
            delay_seconds: التأخير قبل البدء (للسماح للواجهة بالظهور)
        """
        def sync_worker():
            try:
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
                self._perform_full_sync()
            except Exception as e:
                logger.error(f"❌ [StartupSync] خطأ في المزامنة: {e}")
        
        thread = threading.Thread(
            target=sync_worker,
            daemon=True,
            name="StartupSyncThread"
        )
        thread.start()
        logger.info(f"🚀 [StartupSync] بدء المزامنة في الخلفية")
    
    def _perform_full_sync(self):
        """تنفيذ المزامنة الكاملة - محسّن للسرعة"""
        if self._is_syncing:
            logger.warning("[StartupSync] المزامنة جارية بالفعل")
            return
        
        with self._sync_lock:
            self._is_syncing = True
            self._sync_stats['start_time'] = datetime.now()
            self._sync_stats['pulled'] = 0
            self._sync_stats['pushed'] = 0
            self._sync_stats['errors'] = 0
        
        try:
            # ⚡ انتظار اتصال MongoDB (timeout أقصر للسرعة)
            if not self._wait_for_connection(timeout=5):
                logger.warning("[StartupSync] لا يوجد اتصال - العمل بالبيانات المحلية")
                # ⚡ استدعاء callbacks حتى لو offline
                for callback in self._callbacks:
                    try:
                        callback()
                    except Exception:
                        pass
                return
            
            logger.info("=" * 60)
            logger.info("🚀 [StartupSync] بدء المزامنة الكاملة...")
            logger.info("=" * 60)
            
            # 1. رفع التغييرات المحلية أولاً (لحماية البيانات)
            logger.info("📤 [Step 1] رفع التغييرات المحلية للسيرفر...")
            pushed = self._push_local_changes()
            self._sync_stats['pushed'] = pushed
            
            # 2. جلب البيانات من السيرفر
            logger.info("📥 [Step 2] جلب البيانات من السيرفر...")
            pulled = self._pull_from_server()
            self._sync_stats['pulled'] = pulled
            
            # 3. تنظيف التكرارات
            logger.info("🧹 [Step 3] تنظيف التكرارات...")
            self._cleanup_duplicates()
            
            self._sync_stats['end_time'] = datetime.now()
            elapsed = (self._sync_stats['end_time'] - self._sync_stats['start_time']).total_seconds()
            
            logger.info("=" * 60)
            logger.info(f"✅ [StartupSync] اكتملت المزامنة في {elapsed:.1f} ثانية")
            logger.info(f"   📤 رفع: {pushed} سجل")
            logger.info(f"   📥 جلب: {pulled} سجل")
            logger.info("=" * 60)
            
            # 📊 طباعة تقرير المطابقة
            self.print_sync_report()
            
            # استدعاء callbacks
            for callback in self._callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"خطأ في callback: {e}")
        
        except Exception as e:
            logger.error(f"❌ [StartupSync] فشلت المزامنة: {e}")
            import traceback
            traceback.print_exc()
            self._sync_stats['errors'] += 1
        
        finally:
            self._is_syncing = False
    
    def _wait_for_connection(self, timeout: int = 15) -> bool:
        """انتظار اتصال MongoDB"""
        waited = 0
        while not self.repo.online and waited < timeout:
            time.sleep(0.5)
            waited += 0.5
        return self.repo.online
    
    def _push_local_changes(self) -> int:
        """رفع التغييرات المحلية للسيرفر"""
        total_pushed = 0
        
        try:
            cursor = self.repo.sqlite_cursor
            
            for table in self.SYNC_TABLES:
                try:
                    # التحقق من وجود الجدول
                    cursor.execute(f"PRAGMA table_info({table})")
                    if not cursor.fetchall():
                        continue  # الجدول غير موجود
                    
                    # جلب السجلات المعلقة
                    cursor.execute(f"""
                        SELECT * FROM {table} 
                        WHERE sync_status = 'pending' OR sync_status IS NULL
                    """)
                    pending_rows = cursor.fetchall()
                    
                    if not pending_rows:
                        continue
                    
                    # جلب أسماء الأعمدة
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in cursor.fetchall()]
                    
                    collection = self.repo.mongo_db[table]
                    
                    for row in pending_rows:
                        try:
                            row_dict = dict(zip(columns, row))
                            mongo_id = row_dict.get('_mongo_id')
                            local_id = row_dict.get('id')
                            
                            # تحضير البيانات للرفع
                            doc = self._prepare_for_mongo(row_dict)
                            
                            if mongo_id:
                                # تحديث سجل موجود
                                from bson import ObjectId
                                collection.update_one(
                                    {'_id': ObjectId(mongo_id)},
                                    {'$set': doc},
                                    upsert=True
                                )
                            else:
                                # إدراج سجل جديد
                                result = collection.insert_one(doc)
                                new_mongo_id = str(result.inserted_id)
                                
                                # تحديث _mongo_id محلياً
                                cursor.execute(f"""
                                    UPDATE {table} 
                                    SET _mongo_id = ?, sync_status = 'synced'
                                    WHERE id = ?
                                """, (new_mongo_id, local_id))
                            
                            # تحديث حالة المزامنة
                            cursor.execute(f"""
                                UPDATE {table} 
                                SET sync_status = 'synced', last_modified = ?
                                WHERE id = ?
                            """, (datetime.now().isoformat(), local_id))
                            
                            total_pushed += 1
                        
                        except Exception as e:
                            logger.error(f"خطأ في رفع سجل من {table}: {e}")
                    
                    self.repo.sqlite_conn.commit()
                    
                    if pending_rows:
                        logger.info(f"  ✅ {table}: رفع {len(pending_rows)} سجل")
                
                except Exception as e:
                    logger.error(f"خطأ في رفع {table}: {e}")
        
        except Exception as e:
            logger.error(f"خطأ في رفع التغييرات: {e}")
        
        return total_pushed
    
    def _pull_from_server(self) -> int:
        """جلب البيانات من السيرفر"""
        total_pulled = 0
        
        for table in self.SYNC_TABLES:
            try:
                pulled, skipped = self._pull_table(table)
                total_pulled += pulled
                if pulled > 0:
                    msg = f"  ✅ {table}: جلب {pulled} سجل"
                    if skipped > 0:
                        msg += f" (تخطي {skipped} مكرر)"
                    logger.info(msg)
            except Exception as e:
                logger.error(f"خطأ في جلب {table}: {e}")
        
        return total_pulled

    def _pull_table(self, table_name: str) -> tuple:
        """
        جلب جدول واحد من السيرفر
        
        Returns:
            tuple: (عدد السجلات المجلوبة, عدد السجلات المتخطاة)
        """
        count = 0
        skipped = 0
        
        try:
            cursor = self.repo.sqlite_cursor
            
            # التحقق من وجود الجدول في SQLite
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            if not columns_info:
                logger.warning(f"⚠️ الجدول {table_name} غير موجود في SQLite - تخطي")
                return 0, 0
            
            local_columns = [col[1] for col in columns_info]
            
            # التحقق من وجود الـ collection في MongoDB
            collection = self.repo.mongo_db[table_name]
            
            # جلب كل البيانات من MongoDB
            try:
                mongo_docs = list(collection.find())
            except Exception as e:
                logger.warning(f"⚠️ الـ collection {table_name} غير موجود في MongoDB: {e}")
                return 0, 0
            
            if not mongo_docs:
                return 0, 0
            
            for doc in mongo_docs:
                try:
                    mongo_id = str(doc['_id'])
                    
                    # تحضير البيانات للحفظ محلياً
                    local_data = self._prepare_for_sqlite(doc, local_columns)
                    local_data['_mongo_id'] = mongo_id
                    local_data['sync_status'] = 'synced'
                    
                    # التحقق من وجود السجل
                    cursor.execute(f"""
                        SELECT id FROM {table_name} WHERE _mongo_id = ?
                    """, (mongo_id,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # تحديث السجل الموجود
                        update_data = {k: v for k, v in local_data.items() if k != 'id'}
                        if update_data:
                            set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
                            values = list(update_data.values()) + [existing[0]]
                            cursor.execute(f"""
                                UPDATE {table_name} SET {set_clause} WHERE id = ?
                            """, values)
                    else:
                        # إدراج سجل جديد (بدون id لأنه auto-increment)
                        insert_data = {k: v for k, v in local_data.items() if k != 'id'}
                        if insert_data:
                            cols = ', '.join(insert_data.keys())
                            placeholders = ', '.join(['?' for _ in insert_data])
                            try:
                                cursor.execute(f"""
                                    INSERT INTO {table_name} ({cols}) VALUES ({placeholders})
                                """, list(insert_data.values()))
                            except sqlite3.IntegrityError as ie:
                                # محاولة التحديث بدلاً من الإدراج (للسجلات المكررة)
                                if 'UNIQUE constraint' in str(ie):
                                    # البحث عن السجل بالاسم وتحديثه
                                    name_field = insert_data.get('name', '')
                                    if name_field and table_name in ['projects', 'clients', 'services']:
                                        cursor.execute(f"""
                                            UPDATE {table_name} SET _mongo_id = ?, sync_status = 'synced'
                                            WHERE name = ?
                                        """, (mongo_id, name_field))
                                        logger.debug(f"  🔄 تحديث {table_name}: {name_field}")
                                        skipped += 1
                                else:
                                    logger.warning(f"⚠️ تخطي سجل مكرر في {table_name}: {ie}")
                                    skipped += 1
                                    continue
                    
                    count += 1
                
                except Exception as e:
                    logger.warning(f"⚠️ خطأ في معالجة سجل من {table_name}: {e}")
                    skipped += 1
            
            self.repo.sqlite_conn.commit()
        
        except Exception as e:
            logger.error(f"خطأ في جلب {table_name}: {e}")
        
        return count, skipped
    
    def _prepare_for_mongo(self, data: Dict) -> Dict:
        """تحضير البيانات للرفع إلى MongoDB"""
        doc = {}
        
        for key, value in data.items():
            # تجاهل الحقول المحلية
            if key in ['id', '_mongo_id', 'sync_status']:
                continue
            
            # تحويل JSON strings
            if key in ['items', 'lines'] and isinstance(value, str):
                try:
                    doc[key] = json.loads(value)
                except:
                    doc[key] = value
            else:
                doc[key] = value
        
        # إضافة timestamp
        doc['last_modified'] = datetime.now().isoformat()
        
        return doc
    
    def _prepare_for_sqlite(self, doc: Dict, columns: List[str]) -> Dict:
        """تحضير البيانات للحفظ في SQLite"""
        data = {}
        
        for key, value in doc.items():
            # تجاهل _id (سيتم حفظه كـ _mongo_id)
            if key == '_id':
                continue
            
            # التحقق من أن العمود موجود
            if key not in columns:
                continue
            
            # تحويل datetime
            if hasattr(value, 'isoformat'):
                data[key] = value.isoformat()
            # تحويل lists/dicts إلى JSON
            elif isinstance(value, (list, dict)):
                data[key] = json.dumps(value, ensure_ascii=False)
            else:
                data[key] = value
        
        return data
    
    def _cleanup_duplicates(self):
        """تنظيف التكرارات"""
        try:
            cursor = self.repo.sqlite_cursor
            
            # قائمة الجداول للتنظيف
            tables_to_clean = [
                ('clients', 'name'),
                ('services', 'name'),
                ('projects', 'name')
            ]
            
            for table, unique_field in tables_to_clean:
                try:
                    # التحقق من وجود الجدول
                    cursor.execute(f"PRAGMA table_info({table})")
                    if not cursor.fetchall():
                        continue
                    
                    cursor.execute(f"""
                        DELETE FROM {table} WHERE id NOT IN (
                            SELECT MIN(id) FROM {table} GROUP BY {unique_field}
                        )
                    """)
                except Exception as e:
                    logger.warning(f"تخطي تنظيف {table}: {e}")
            
            self.repo.sqlite_conn.commit()
            logger.info("  ✅ تم تنظيف التكرارات")
        
        except Exception as e:
            logger.error(f"خطأ في تنظيف التكرارات: {e}")
    
    def force_sync_now(self, progress_callback: Callable = None) -> Dict[str, Any]:
        """
        🔄 مزامنة فورية (تُستدعى من زر المزامنة)
        
        Returns:
            نتيجة المزامنة
        """
        if self._is_syncing:
            return {'success': False, 'error': 'المزامنة جارية بالفعل', 'reason': 'already_syncing'}
        
        if not self.repo.online:
            return {'success': False, 'error': 'لا يوجد اتصال', 'reason': 'offline'}
        
        with self._sync_lock:
            self._is_syncing = True
        
        try:
            start_time = time.time()
            
            if progress_callback:
                progress_callback("رفع التغييرات المحلية...", 1, 3)
            
            # 1. رفع التغييرات المحلية
            pushed = self._push_local_changes()
            
            if progress_callback:
                progress_callback("جلب البيانات من السيرفر...", 2, 3)
            
            # 2. جلب من السيرفر
            pulled = self._pull_from_server()
            
            if progress_callback:
                progress_callback("تنظيف التكرارات...", 3, 3)
            
            # 3. تنظيف
            self._cleanup_duplicates()
            
            elapsed = time.time() - start_time
            
            return {
                'success': True,
                'total_synced': pushed + pulled,
                'pushed': pushed,
                'pulled': pulled,
                'elapsed': elapsed
            }
        
        except Exception as e:
            logger.error(f"خطأ في المزامنة الفورية: {e}")
            return {'success': False, 'error': str(e)}
        
        finally:
            self._is_syncing = False
    
    @property
    def is_syncing(self) -> bool:
        return self._is_syncing
    
    @property
    def is_online(self) -> bool:
        return self.repo.online if self.repo else False
    
    def get_sync_comparison(self) -> Dict[str, Any]:
        """
        📊 مقارنة احترافية بين MongoDB و SQLite
        
        Returns:
            تقرير مفصل بالفروقات
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'online': self.repo.online,
            'tables': {},
            'summary': {
                'total_mongo': 0,
                'total_sqlite': 0,
                'synced_tables': 0,
                'missing_in_sqlite': 0,
                'extra_in_sqlite': 0
            }
        }
        
        if not self.repo.online:
            report['error'] = 'لا يوجد اتصال بـ MongoDB'
            return report
        
        cursor = self.repo.sqlite_cursor
        
        for table in self.SYNC_TABLES:
            table_report = {
                'mongo_count': 0,
                'sqlite_count': 0,
                'difference': 0,
                'status': 'unknown'
            }
            
            try:
                # عدد السجلات في MongoDB
                collection = self.repo.mongo_db[table]
                mongo_count = collection.count_documents({})
                table_report['mongo_count'] = mongo_count
                report['summary']['total_mongo'] += mongo_count
                
                # عدد السجلات في SQLite
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                sqlite_count = cursor.fetchone()[0]
                table_report['sqlite_count'] = sqlite_count
                report['summary']['total_sqlite'] += sqlite_count
                
                # حساب الفرق
                diff = mongo_count - sqlite_count
                table_report['difference'] = diff
                
                if diff == 0:
                    table_report['status'] = '✅ متطابق'
                    report['summary']['synced_tables'] += 1
                elif diff > 0:
                    table_report['status'] = f'⚠️ ناقص {diff} في SQLite'
                    report['summary']['missing_in_sqlite'] += diff
                else:
                    table_report['status'] = f'📤 زيادة {abs(diff)} في SQLite'
                    report['summary']['extra_in_sqlite'] += abs(diff)
                    
            except Exception as e:
                table_report['error'] = str(e)
                table_report['status'] = '❌ خطأ'
            
            report['tables'][table] = table_report
        
        return report
    
    def print_sync_report(self):
        """طباعة تقرير المزامنة"""
        report = self.get_sync_comparison()
        
        logger.info("=" * 70)
        logger.info("📊 تقرير المطابقة بين MongoDB و SQLite")
        logger.info("=" * 70)
        
        if 'error' in report:
            logger.warning(f"⚠️ {report['error']}")
            return report
        
        logger.info(f"{'الجدول':<20} {'MongoDB':<12} {'SQLite':<12} {'الحالة':<20}")
        logger.info("-" * 70)
        
        for table, data in report['tables'].items():
            logger.info(
                f"{table:<20} {data['mongo_count']:<12} "
                f"{data['sqlite_count']:<12} {data['status']:<20}"
            )
        
        logger.info("-" * 70)
        summary = report['summary']
        logger.info(f"📈 الإجمالي: MongoDB={summary['total_mongo']} | SQLite={summary['total_sqlite']}")
        logger.info(f"✅ جداول متطابقة: {summary['synced_tables']}/{len(self.SYNC_TABLES)}")
        
        if summary['missing_in_sqlite'] > 0:
            logger.warning(f"⚠️ سجلات ناقصة في SQLite: {summary['missing_in_sqlite']}")
        if summary['extra_in_sqlite'] > 0:
            logger.info(f"📤 سجلات إضافية في SQLite: {summary['extra_in_sqlite']}")
        
        logger.info("=" * 70)
        
        return report


# Singleton instance
_startup_sync_instance: Optional[StartupSync] = None


def get_startup_sync(repository=None) -> Optional[StartupSync]:
    """الحصول على instance من StartupSync"""
    global _startup_sync_instance
    
    if _startup_sync_instance is None and repository is not None:
        _startup_sync_instance = StartupSync(repository)
    
    return _startup_sync_instance
