# الملف: core/smart_sync_manager.py
"""
🔄 مدير المزامنة الذكي مع حل التعارضات
يدمج SyncManager مع ConflictResolver لتوفير:
1. Smart Field-Level Merge
2. تسجيل التعارضات الحساسة للمراجعة
3. إشعارات عند حدوث تعارضات
"""

import json
import threading
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from core.conflict_resolver import ConflictResolution, ConflictResolver
from core.logger import get_logger

logger = get_logger(__name__)


class SmartSyncManager(QObject):
    """
    🔄 مدير المزامنة الذكي
    يوفر مزامنة آمنة مع حل التعارضات الذكي
    """

    # قائمة الجداول المسموح بها (للحماية من SQL Injection)
    ALLOWED_TABLES = frozenset({
        'accounts', 'clients', 'services', 'projects', 'invoices',
        'payments', 'expenses', 'journal_entries', 'quotations',
        'currencies', 'users', 'notifications', 'tasks', 'sync_queue'
    })

    # إشارات
    conflict_detected = pyqtSignal(dict)      # عند اكتشاف تعارض
    conflict_resolved = pyqtSignal(dict)      # عند حل تعارض
    critical_conflict = pyqtSignal(dict)      # تعارض حساس يتطلب مراجعة
    sync_progress = pyqtSignal(str, int, int) # table, current, total

    def __init__(self, repository, parent=None):
        """
        تهيئة مدير المزامنة الذكي

        Args:
            repository: كائن Repository للوصول للبيانات
        """
        super().__init__(parent)
        self.repository = repository
        self.conflict_resolver = ConflictResolver(repository.sqlite_conn)
        self._lock = threading.RLock()

        # إحصائيات
        self.stats = {
            'total_synced': 0,
            'auto_merged': 0,
            'pending_review': 0,
            'conflicts_resolved': 0
        }

        logger.info("✅ تم تهيئة SmartSyncManager")

    def smart_pull_and_merge(self, collection_name: str) -> dict[str, int]:
        """
        سحب ودمج ذكي مع حل التعارضات

        Args:
            collection_name: اسم المجموعة/الجدول

        Returns:
            إحصائيات العملية
        """
        if not self.repository.online:
            logger.warning("لا يوجد اتصال - تخطي المزامنة")
            return {'synced': 0, 'conflicts': 0, 'pending': 0}

        stats = {
            'synced': 0,
            'inserted': 0,
            'updated': 0,
            'conflicts': 0,
            'auto_merged': 0,
            'pending_review': 0
        }

        try:
            with self._lock:
                # جلب البيانات من السحابة
                cloud_data = list(self.repository.mongo_db[collection_name].find())

                if not cloud_data:
                    logger.info(f"لا توجد بيانات في {collection_name}")
                    return stats

                logger.info(f"🔄 جاري مزامنة {len(cloud_data)} سجل من {collection_name}...")

                cursor = self.repository.sqlite_cursor
                conn = self.repository.sqlite_conn

                # الحصول على أعمدة الجدول
                cursor.execute(f"PRAGMA table_info({collection_name})")
                table_columns = {row[1] for row in cursor.fetchall()}

                for i, cloud_item in enumerate(cloud_data):
                    self.sync_progress.emit(collection_name, i + 1, len(cloud_data))

                    result = self._process_cloud_item(
                        collection_name, cloud_item, cursor, table_columns
                    )

                    # تحديث الإحصائيات
                    if result['action'] == 'inserted':
                        stats['inserted'] += 1
                    elif result['action'] == 'updated':
                        stats['updated'] += 1

                    if result.get('conflict'):
                        stats['conflicts'] += 1
                        if result['conflict'].resolution == ConflictResolution.AUTO_MERGED:
                            stats['auto_merged'] += 1
                        elif result['conflict'].resolution == ConflictResolution.PENDING_REVIEW:
                            stats['pending_review'] += 1
                            # إرسال إشارة للتعارض الحساس
                            self.critical_conflict.emit({
                                'table': collection_name,
                                'entity_id': result.get('entity_id'),
                                'conflict': result['conflict'].conflict_details
                            })

                conn.commit()
                stats['synced'] = stats['inserted'] + stats['updated']

                # تحديث الإحصائيات العامة
                self.stats['total_synced'] += stats['synced']
                self.stats['auto_merged'] += stats['auto_merged']
                self.stats['pending_review'] += stats['pending_review']

                logger.info(
                    f"✅ {collection_name}: مزامنة {stats['synced']} "
                    f"(جديد: {stats['inserted']}, تحديث: {stats['updated']}, "
                    f"تعارضات: {stats['conflicts']})"
                )

        except Exception as e:
            logger.error(f"❌ خطأ في مزامنة {collection_name}: {e}")
            import traceback
            traceback.print_exc()

        return stats

    def _process_cloud_item(
        self,
        collection_name: str,
        cloud_item: dict[str, Any],
        cursor,
        table_columns: set
    ) -> dict[str, Any]:
        """
        معالجة عنصر واحد من السحابة

        Returns:
            dict مع action و conflict (إن وجد)
        """
        mongo_id = str(cloud_item['_id'])
        unique_field = self._get_unique_field(collection_name)
        unique_value = cloud_item.get(unique_field)

        # 1. البحث عن السجل المحلي
        local_record = self._find_local_record(
            cursor, collection_name, mongo_id, unique_field, unique_value
        )

        if not local_record:
            # سجل جديد - إدراج مباشر
            self._insert_record(cursor, collection_name, cloud_item,
                               mongo_id, table_columns)
            return {'action': 'inserted', 'entity_id': mongo_id}

        # 2. السجل موجود - فحص التعارض
        local_id = local_record['id']
        local_dict = dict(local_record)
        cloud_dict = self._prepare_cloud_data(cloud_item)

        # 3. كشف وحل التعارض
        conflict_result = self.conflict_resolver.detect_and_resolve(
            table_name=collection_name,
            entity_id=str(local_id),
            local_record=local_dict,
            remote_record=cloud_dict
        )

        if conflict_result.has_conflict:
            # إرسال إشارة
            self.conflict_detected.emit({
                'table': collection_name,
                'entity_id': str(local_id),
                'resolution': conflict_result.resolution.value,
                'fields': conflict_result.conflicting_fields
            })

        # 4. تطبيق النتيجة
        if conflict_result.requires_review:
            # تعارض حساس - لا نحدث الحقول الحساسة
            # نحدث فقط الحقول غير الحساسة
            safe_data = self._get_safe_fields(
                conflict_result.merged_data,
                collection_name
            )
            self._update_record(cursor, collection_name, local_id,
                               safe_data, table_columns)
        else:
            # دمج تلقائي أو لا يوجد تعارض
            self._update_record(cursor, collection_name, local_id,
                               conflict_result.merged_data, table_columns)

        return {
            'action': 'updated',
            'entity_id': str(local_id),
            'conflict': conflict_result if conflict_result.has_conflict else None
        }

    def _validate_table_name(self, table_name: str) -> bool:
        """التحقق من صحة اسم الجدول للحماية من SQL Injection"""
        return table_name in self.ALLOWED_TABLES

    def _validate_column_name(self, column_name: str) -> bool:
        """التحقق من صحة اسم العمود"""
        # السماح فقط بالأحرف والأرقام والشرطة السفلية
        import re
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column_name))

    def _find_local_record(
        self,
        cursor,
        collection_name: str,
        mongo_id: str,
        unique_field: str,
        unique_value: Any
    ) -> dict[str, Any] | None:
        """البحث عن السجل المحلي"""
        # التحقق من صحة اسم الجدول
        if not self._validate_table_name(collection_name):
            logger.error(f"اسم جدول غير صالح: {collection_name}")
            return None

        # البحث بـ mongo_id أولاً
        cursor.execute(
            f"SELECT * FROM {collection_name} WHERE _mongo_id = ?",
            (mongo_id,)
        )
        row = cursor.fetchone()

        if row:
            return dict(row)

        # البحث بالحقل الفريد - مع التحقق من صحة اسم العمود
        if unique_value and self._validate_column_name(unique_field):
            cursor.execute(
                f"SELECT * FROM {collection_name} WHERE {unique_field} = ?",
                (unique_value,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)

        return None

    def _insert_record(
        self,
        cursor,
        collection_name: str,
        cloud_item: dict[str, Any],
        mongo_id: str,
        table_columns: set
    ):
        """إدراج سجل جديد"""
        # التحقق من صحة اسم الجدول
        if not self._validate_table_name(collection_name):
            logger.error(f"اسم جدول غير صالح: {collection_name}")
            return

        item = self._prepare_cloud_data(cloud_item)
        item['_mongo_id'] = mongo_id
        item['sync_status'] = 'synced'

        if 'created_at' not in item or not item['created_at']:
            item['created_at'] = datetime.now().isoformat()
        if 'last_modified' not in item or not item['last_modified']:
            item['last_modified'] = datetime.now().isoformat()

        # تصفية الأعمدة والتحقق من صحتها
        filtered = {k: v for k, v in item.items()
                   if k in table_columns and self._validate_column_name(k)}

        if filtered:
            columns = ', '.join(filtered.keys())
            placeholders = ', '.join(['?' for _ in filtered])
            cursor.execute(
                f"INSERT INTO {collection_name} ({columns}) VALUES ({placeholders})",
                list(filtered.values())
            )

    def _update_record(
        self,
        cursor,
        collection_name: str,
        local_id: int,
        data: dict[str, Any],
        table_columns: set
    ):
        """تحديث سجل موجود"""
        # التحقق من صحة اسم الجدول
        if not self._validate_table_name(collection_name):
            logger.error(f"اسم جدول غير صالح: {collection_name}")
            return

        data['sync_status'] = 'synced'
        data['last_modified'] = datetime.now().isoformat()

        # إزالة الحقول غير القابلة للتحديث
        data.pop('id', None)
        data.pop('created_at', None)

        # تصفية الأعمدة والتحقق من صحتها
        filtered = {k: v for k, v in data.items()
                   if k in table_columns and self._validate_column_name(k)}

        if filtered:
            set_clause = ', '.join([f"{k}=?" for k in filtered.keys()])
            values = list(filtered.values()) + [local_id]
            cursor.execute(
                f"UPDATE {collection_name} SET {set_clause} WHERE id=?",
                values
            )

    def _get_safe_fields(
        self,
        data: dict[str, Any],
        collection_name: str
    ) -> dict[str, Any]:
        """
        الحصول على الحقول الآمنة فقط (غير الحساسة)
        للتحديث عند وجود تعارض حساس
        """
        critical_fields = ConflictResolver.CRITICAL_FIELDS.get(collection_name, [])
        return {k: v for k, v in data.items() if k not in critical_fields}

    def _prepare_cloud_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """تحضير بيانات السحابة"""
        item = dict(data)
        item.pop('_id', None)
        item.pop('id', None)

        # تحويل التواريخ
        for field in ['created_at', 'last_modified', 'date', 'issue_date',
                     'due_date', 'expiry_date', 'start_date', 'end_date']:
            if field in item and hasattr(item[field], 'isoformat'):
                item[field] = item[field].isoformat()

        # تحويل القوائم إلى JSON
        for field in ['items', 'lines', 'data', 'milestones']:
            if field in item and isinstance(item[field], (list, dict)):
                item[field] = json.dumps(item[field], ensure_ascii=False)

        return item

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
            'users': 'username',
            'notifications': 'id'
        }
        return unique_fields.get(table_name, 'name')

    # ==========================================
    # واجهة المزامنة الكاملة
    # ==========================================

    def full_smart_sync(self) -> dict[str, Any]:
        """
        مزامنة كاملة ذكية لجميع الجداول

        Returns:
            إحصائيات المزامنة الكاملة
        """
        if not self.repository.online:
            logger.warning("لا يوجد اتصال - تخطي المزامنة الكاملة")
            return {'success': False, 'reason': 'offline'}

        logger.info("=" * 60)
        logger.info("🔄 بدء المزامنة الذكية الكاملة")
        logger.info("=" * 60)

        start_time = datetime.now()

        # ترتيب الجداول حسب الأولوية
        tables = [
            'accounts',      # الحسابات أولاً (أساسية)
            'clients',       # العملاء
            'services',      # الخدمات
            'projects',      # المشاريع
            'invoices',      # الفواتير
            'payments',      # الدفعات
            'expenses',      # المصروفات
            'journal_entries', # القيود
            'quotations',    # عروض الأسعار
            'currencies',    # العملات
            'notifications', # الإشعارات
        ]

        results = {}
        total_stats = {
            'synced': 0,
            'conflicts': 0,
            'auto_merged': 0,
            'pending_review': 0
        }

        for table in tables:
            try:
                stats = self.smart_pull_and_merge(table)
                results[table] = stats

                total_stats['synced'] += stats.get('synced', 0)
                total_stats['conflicts'] += stats.get('conflicts', 0)
                total_stats['auto_merged'] += stats.get('auto_merged', 0)
                total_stats['pending_review'] += stats.get('pending_review', 0)

            except Exception as e:
                logger.error(f"❌ فشل مزامنة {table}: {e}")
                results[table] = {'synced': 0, 'conflicts': 0, 'auto_merged': 0, 'pending_review': 0}

        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info(f"✅ اكتملت المزامنة الذكية في {elapsed:.1f} ثانية")
        logger.info(f"   📊 إجمالي: {total_stats['synced']} سجل")
        logger.info(f"   🔄 تعارضات: {total_stats['conflicts']}")
        logger.info(f"   ✅ دمج تلقائي: {total_stats['auto_merged']}")
        logger.info(f"   ⚠️ بانتظار المراجعة: {total_stats['pending_review']}")
        logger.info("=" * 60)

        return {
            'success': True,
            'elapsed_seconds': elapsed,
            'tables': results,
            'totals': total_stats
        }

    # ==========================================
    # واجهة إدارة التعارضات
    # ==========================================

    def get_pending_conflicts(self) -> list[dict[str, Any]]:
        """جلب التعارضات المعلقة للمراجعة"""
        result: list[dict[str, Any]] = self.conflict_resolver.get_pending_conflicts()
        return result

    def get_pending_conflicts_count(self) -> int:
        """عدد التعارضات المعلقة"""
        return int(self.conflict_resolver.get_pending_count())

    def resolve_conflict(
        self,
        conflict_id: int,
        chosen_version: str,
        merged_data: dict[str, Any] | None = None,
        notes: str = ""
    ) -> bool:
        """
        حل تعارض يدوياً

        Args:
            conflict_id: معرف التعارض
            chosen_version: 'local' أو 'remote' أو 'merged'
            merged_data: البيانات المدمجة (إذا كان merged)
            notes: ملاحظات
        """
        success = self.conflict_resolver.resolve_conflict_manually(
            conflict_id=conflict_id,
            chosen_version=chosen_version,
            merged_data=merged_data,
            notes=notes
        )

        if success:
            self.stats['conflicts_resolved'] += 1
            self.conflict_resolved.emit({
                'conflict_id': conflict_id,
                'chosen_version': chosen_version
            })

        return bool(success)

    def get_conflict_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """جلب سجل التعارضات"""
        result: list[dict[str, Any]] = self.conflict_resolver.get_conflict_history(limit=limit)
        return result

    def get_stats(self) -> dict[str, Any]:
        """الحصول على إحصائيات المزامنة"""
        return {
            **self.stats,
            'pending_conflicts': self.get_pending_conflicts_count()
        }

    def cleanup(self, days_old: int = 30):
        """تنظيف التعارضات القديمة"""
        self.conflict_resolver.cleanup_old_conflicts(days_old)


# ==========================================
# دالة مساعدة للإنشاء
# ==========================================

def create_smart_sync_manager(repository) -> SmartSyncManager:
    """إنشاء مدير مزامنة ذكي جديد"""
    return SmartSyncManager(repository)
