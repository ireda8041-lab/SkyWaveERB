# الملف: core/conflict_resolver.py
"""
🔄 نظام حل التعارضات الذكي - Smart Field-Level Merge
يدعم:
1. دمج التعديلات في حقول مختلفة تلقائياً
2. تسجيل التعارضات في الحقول الحساسة للمراجعة اليدوية
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)


class ConflictResolution(Enum):
    """أنواع حل التعارضات"""
    AUTO_MERGED = "auto_merged"           # تم الدمج تلقائياً (حقول مختلفة)
    PENDING_REVIEW = "pending_review"     # بانتظار المراجعة (حقل حساس)
    LOCAL_WINS = "local_wins"             # الإصدار المحلي فاز
    REMOTE_WINS = "remote_wins"           # الإصدار السحابي فاز
    MANUAL_RESOLVED = "manual_resolved"   # تم الحل يدوياً


class ConflictSeverity(Enum):
    """مستوى خطورة التعارض"""
    LOW = "low"           # حقول غير حساسة (ملاحظات، وصف)
    MEDIUM = "medium"     # حقول متوسطة (تاريخ، حالة)
    HIGH = "high"         # حقول حساسة (مبلغ، كمية)
    CRITICAL = "critical" # حقول حرجة (حذف vs تعديل)


@dataclass
class ConflictResult:
    """نتيجة حل التعارض"""
    has_conflict: bool
    resolution: ConflictResolution
    merged_data: dict[str, Any]
    conflicting_fields: list[str]
    severity: ConflictSeverity
    requires_review: bool
    conflict_details: dict[str, Any] | None = None


class ConflictResolver:
    """
    🔄 محلل التعارضات الذكي

    استراتيجية Smart Field-Level Merge:
    1. مقارنة الحقول المعدلة في كلا الإصدارين
    2. إذا كانت التعديلات في حقول مختلفة → دمج تلقائي
    3. إذا كان التعارض في حقل حساس → تسجيل للمراجعة اليدوية
    """

    # الحقول الحساسة لكل جدول (تتطلب مراجعة يدوية عند التعارض)
    CRITICAL_FIELDS = {
        'projects': [
            'total_amount', 'subtotal', 'discount_amount', 'tax_amount',
            'items', 'milestones', 'total_estimated_cost'
        ],
        'invoices': [
            'total_amount', 'subtotal', 'discount_amount', 'tax_amount',
            'items', 'amount_paid'
        ],
        'payments': [
            'amount', 'date', 'account_id'
        ],
        'expenses': [
            'amount', 'date', 'account_id'
        ],
        'journal_entries': [
            'lines', 'date'
        ],
        'quotations': [
            'total_amount', 'subtotal', 'items', 'discount_amount', 'tax_amount'
        ],
        'accounts': [
            'balance', 'code'
        ],
        'clients': [],  # لا توجد حقول حساسة للعملاء
        'services': [
            'default_price'
        ]
    }

    # الحقول التي يتم تجاهلها في المقارنة
    IGNORED_FIELDS = [
        'id', '_id', '_mongo_id', 'sync_status', 'created_at',
        'last_modified', 'last_attempt'
    ]

    def __init__(self, sqlite_conn: sqlite3.Connection):
        """
        تهيئة محلل التعارضات

        Args:
            sqlite_conn: اتصال SQLite لتسجيل التعارضات
        """
        self.sqlite_conn = sqlite_conn
        self._ensure_conflict_log_table()
        logger.info("✅ تم تهيئة ConflictResolver")

    def _ensure_conflict_log_table(self):
        """إنشاء جدول سجل التعارضات إذا لم يكن موجوداً"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflict_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                entity_name TEXT,
                local_data TEXT,
                remote_data TEXT,
                base_data TEXT,
                conflicting_fields TEXT NOT NULL,
                resolution TEXT NOT NULL,
                severity TEXT NOT NULL,
                winner TEXT,
                merged_data TEXT,
                resolved_by TEXT,
                resolved_at TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # إنشاء index للبحث السريع
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conflict_log_status
            ON conflict_log(resolution)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conflict_log_table
            ON conflict_log(table_name, entity_id)
        """)

        self.sqlite_conn.commit()
        logger.info("✅ جدول conflict_log جاهز")

    def detect_and_resolve(
        self,
        table_name: str,
        entity_id: str,
        local_record: dict[str, Any],
        remote_record: dict[str, Any],
        base_record: dict[str, Any] | None = None
    ) -> ConflictResult:
        """
        كشف وحل التعارضات بين السجل المحلي والسحابي

        Args:
            table_name: اسم الجدول
            entity_id: معرف السجل
            local_record: السجل المحلي
            remote_record: السجل السحابي
            base_record: السجل الأصلي (قبل التعديلات) - اختياري

        Returns:
            ConflictResult: نتيجة حل التعارض
        """
        # 1. كشف الحقول المختلفة
        changed_fields = self._find_changed_fields(local_record, remote_record)

        if not changed_fields:
            # لا يوجد تعارض - السجلات متطابقة
            return ConflictResult(
                has_conflict=False,
                resolution=ConflictResolution.AUTO_MERGED,
                merged_data=remote_record,
                conflicting_fields=[],
                severity=ConflictSeverity.LOW,
                requires_review=False
            )

        # 2. تصنيف الحقول المتعارضة
        critical_conflicts = []
        non_critical_conflicts = []
        critical_fields = self.CRITICAL_FIELDS.get(table_name, [])

        for field in changed_fields:
            if field in critical_fields:
                critical_conflicts.append(field)
            else:
                non_critical_conflicts.append(field)

        # 3. تحديد مستوى الخطورة
        if critical_conflicts:
            severity = ConflictSeverity.HIGH
        elif non_critical_conflicts:
            severity = ConflictSeverity.LOW
        else:
            severity = ConflictSeverity.LOW

        # 4. تطبيق استراتيجية الحل
        if critical_conflicts:
            # تعارض في حقول حساسة → تسجيل للمراجعة
            return self._handle_critical_conflict(
                table_name, entity_id, local_record, remote_record,
                critical_conflicts, non_critical_conflicts, severity
            )
        else:
            # تعارض في حقول غير حساسة → دمج تلقائي
            return self._auto_merge(
                table_name, entity_id, local_record, remote_record,
                non_critical_conflicts, severity
            )

    def _find_changed_fields(
        self,
        local: dict[str, Any],
        remote: dict[str, Any]
    ) -> list[str]:
        """
        إيجاد الحقول المختلفة بين السجلين

        Returns:
            قائمة بأسماء الحقول المختلفة
        """
        changed = []
        all_keys = set(local.keys()) | set(remote.keys())

        for key in all_keys:
            if key in self.IGNORED_FIELDS:
                continue

            local_val = local.get(key)
            remote_val = remote.get(key)

            # مقارنة القيم (مع معالجة JSON)
            if not self._values_equal(local_val, remote_val):
                changed.append(key)

        return changed

    def _values_equal(self, val1: Any, val2: Any) -> bool:
        """مقارنة قيمتين مع معالجة الحالات الخاصة"""
        # معالجة None
        if val1 is None and val2 is None:
            return True
        if val1 is None or val2 is None:
            return False

        # معالجة JSON strings
        if isinstance(val1, str) and isinstance(val2, str):
            try:
                json1 = json.loads(val1)
                json2 = json.loads(val2)
                return bool(json1 == json2)
            except (json.JSONDecodeError, TypeError):
                pass

        # معالجة الأرقام (مقارنة تقريبية للـ float)
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            return bool(abs(float(val1) - float(val2)) < 0.001)

        return bool(val1 == val2)

    def _auto_merge(
        self,
        table_name: str,
        entity_id: str,
        local: dict[str, Any],
        remote: dict[str, Any],
        changed_fields: list[str],
        severity: ConflictSeverity
    ) -> ConflictResult:
        """
        دمج تلقائي للتعديلات في حقول غير حساسة
        استراتيجية: Last-Write-Wins للحقول غير الحساسة
        """
        # تحديد الأحدث بناءً على last_modified
        local_time = self._parse_datetime(local.get('last_modified'))
        remote_time = self._parse_datetime(remote.get('last_modified'))

        if local_time and remote_time:
            if local_time > remote_time:
                # المحلي أحدث
                merged = remote.copy()
                for field in changed_fields:
                    merged[field] = local.get(field)
                winner = 'local'
            else:
                # السحابي أحدث
                merged = local.copy()
                for field in changed_fields:
                    merged[field] = remote.get(field)
                winner = 'remote'
        else:
            # لا يمكن تحديد الأحدث - استخدم السحابي
            merged = remote.copy()
            winner = 'remote'

        # تسجيل الدمج التلقائي (للمراجعة لاحقاً إذا لزم)
        self._log_conflict(
            table_name=table_name,
            entity_id=entity_id,
            entity_name=local.get('name') or remote.get('name'),
            local_data=local,
            remote_data=remote,
            conflicting_fields=changed_fields,
            resolution=ConflictResolution.AUTO_MERGED,
            severity=severity,
            winner=winner,
            merged_data=merged
        )

        logger.info(f"✅ دمج تلقائي: {table_name}/{entity_id} - الحقول: {changed_fields}")

        return ConflictResult(
            has_conflict=True,
            resolution=ConflictResolution.AUTO_MERGED,
            merged_data=merged,
            conflicting_fields=changed_fields,
            severity=severity,
            requires_review=False,
            conflict_details={
                'winner': winner,
                'auto_merged_fields': changed_fields
            }
        )

    def _handle_critical_conflict(
        self,
        table_name: str,
        entity_id: str,
        local: dict[str, Any],
        remote: dict[str, Any],
        critical_fields: list[str],
        non_critical_fields: list[str],
        severity: ConflictSeverity
    ) -> ConflictResult:
        """
        معالجة التعارض في الحقول الحساسة
        لا يتم استبدال القيمة تلقائياً - يتم تسجيلها للمراجعة
        """
        # دمج الحقول غير الحساسة فقط (LWW)
        local_time = self._parse_datetime(local.get('last_modified'))
        remote_time = self._parse_datetime(remote.get('last_modified'))

        # نبدأ بالسجل المحلي ونحافظ على قيمه للحقول الحساسة
        merged = local.copy()

        # دمج الحقول غير الحساسة من الأحدث
        if remote_time and local_time and remote_time > local_time:
            for field in non_critical_fields:
                merged[field] = remote.get(field)

        # الحقول الحساسة تبقى كما هي محلياً (لا تُستبدل)
        # سيتم إشعار المستخدم للمراجعة

        # تسجيل التعارض للمراجعة اليدوية
        conflict_id = self._log_conflict(
            table_name=table_name,
            entity_id=entity_id,
            entity_name=local.get('name') or remote.get('name'),
            local_data=local,
            remote_data=remote,
            conflicting_fields=critical_fields + non_critical_fields,
            resolution=ConflictResolution.PENDING_REVIEW,
            severity=ConflictSeverity.HIGH,
            winner=None,
            merged_data=merged
        )

        logger.warning(
            f"⚠️ تعارض حساس يتطلب مراجعة: {table_name}/{entity_id} - "
            f"الحقول الحساسة: {critical_fields}"
        )

        return ConflictResult(
            has_conflict=True,
            resolution=ConflictResolution.PENDING_REVIEW,
            merged_data=merged,
            conflicting_fields=critical_fields + non_critical_fields,
            severity=ConflictSeverity.HIGH,
            requires_review=True,
            conflict_details={
                'conflict_id': conflict_id,
                'critical_fields': critical_fields,
                'non_critical_fields': non_critical_fields,
                'local_values': {f: local.get(f) for f in critical_fields},
                'remote_values': {f: remote.get(f) for f in critical_fields}
            }
        )

    def _log_conflict(
        self,
        table_name: str,
        entity_id: str,
        entity_name: str | None,
        local_data: dict[str, Any],
        remote_data: dict[str, Any],
        conflicting_fields: list[str],
        resolution: ConflictResolution,
        severity: ConflictSeverity,
        winner: str | None,
        merged_data: dict[str, Any]
    ) -> int:
        """تسجيل التعارض في قاعدة البيانات"""
        cursor = self.sqlite_conn.cursor()

        cursor.execute("""
            INSERT INTO conflict_log (
                table_name, entity_id, entity_name, local_data, remote_data,
                conflicting_fields, resolution, severity, winner, merged_data,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            table_name,
            entity_id,
            entity_name,
            json.dumps(local_data, ensure_ascii=False, default=str),
            json.dumps(remote_data, ensure_ascii=False, default=str),
            json.dumps(conflicting_fields, ensure_ascii=False),
            resolution.value,
            severity.value,
            winner,
            json.dumps(merged_data, ensure_ascii=False, default=str),
            datetime.now().isoformat()
        ))

        self.sqlite_conn.commit()
        return cursor.lastrowid or 0

    def _parse_datetime(self, dt_str: Any) -> datetime | None:
        """تحويل نص التاريخ إلى datetime"""
        if dt_str is None:
            return None
        if isinstance(dt_str, datetime):
            return dt_str

        try:
            # محاولة عدة صيغ
            for fmt in [
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d'
            ]:
                try:
                    return datetime.strptime(str(dt_str), fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    # ==========================================
    # واجهة المراجعة اليدوية
    # ==========================================

    def get_pending_conflicts(self, table_name: str | None = None) -> list[dict[str, Any]]:
        """
        جلب التعارضات المعلقة للمراجعة

        Args:
            table_name: تصفية حسب الجدول (اختياري)

        Returns:
            قائمة بالتعارضات المعلقة
        """
        cursor = self.sqlite_conn.cursor()

        if table_name:
            cursor.execute("""
                SELECT * FROM conflict_log
                WHERE resolution = 'pending_review' AND table_name = ?
                ORDER BY created_at DESC
            """, (table_name,))
        else:
            cursor.execute("""
                SELECT * FROM conflict_log
                WHERE resolution = 'pending_review'
                ORDER BY created_at DESC
            """)

        rows = cursor.fetchall()
        conflicts = []

        for row in rows:
            conflict = dict(row)
            # تحويل JSON strings إلى objects
            for field in ['local_data', 'remote_data', 'merged_data', 'conflicting_fields']:
                if conflict.get(field):
                    try:
                        conflict[field] = json.loads(conflict[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            conflicts.append(conflict)

        return conflicts

    def get_pending_count(self) -> int:
        """الحصول على عدد التعارضات المعلقة"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM conflict_log
            WHERE resolution = 'pending_review'
        """)
        result = cursor.fetchone()
        return int(result[0]) if result else 0

    def resolve_conflict_manually(
        self,
        conflict_id: int,
        chosen_version: str,  # 'local' or 'remote' or 'merged'
        merged_data: dict[str, Any] | None = None,
        resolved_by: str = "user",
        notes: str = ""
    ) -> bool:
        """
        حل التعارض يدوياً

        Args:
            conflict_id: معرف التعارض
            chosen_version: الإصدار المختار ('local', 'remote', 'merged')
            merged_data: البيانات المدمجة (إذا كان chosen_version = 'merged')
            resolved_by: من قام بالحل
            notes: ملاحظات

        Returns:
            True إذا نجح الحل
        """
        cursor = self.sqlite_conn.cursor()

        # جلب التعارض
        cursor.execute("SELECT * FROM conflict_log WHERE id = ?", (conflict_id,))
        row = cursor.fetchone()

        if not row:
            logger.error(f"التعارض غير موجود: {conflict_id}")
            return False

        conflict = dict(row)

        # تحديد البيانات النهائية
        if chosen_version == 'local':
            final_data = json.loads(conflict['local_data'])
            resolution = ConflictResolution.LOCAL_WINS
        elif chosen_version == 'remote':
            final_data = json.loads(conflict['remote_data'])
            resolution = ConflictResolution.REMOTE_WINS
        elif chosen_version == 'merged' and merged_data:
            final_data = merged_data
            resolution = ConflictResolution.MANUAL_RESOLVED
        else:
            logger.error(f"إصدار غير صالح: {chosen_version}")
            return False

        # تحديث سجل التعارض
        cursor.execute("""
            UPDATE conflict_log SET
                resolution = ?,
                winner = ?,
                merged_data = ?,
                resolved_by = ?,
                resolved_at = ?,
                notes = ?
            WHERE id = ?
        """, (
            resolution.value,
            chosen_version,
            json.dumps(final_data, ensure_ascii=False, default=str),
            resolved_by,
            datetime.now().isoformat(),
            notes,
            conflict_id
        ))

        self.sqlite_conn.commit()

        logger.info(f"✅ تم حل التعارض {conflict_id} - الإصدار المختار: {chosen_version}")

        return True

    def get_conflict_history(
        self,
        table_name: str | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        جلب سجل التعارضات (للمراجعة والتدقيق)

        Args:
            table_name: تصفية حسب الجدول (اختياري)
            limit: الحد الأقصى للنتائج

        Returns:
            قائمة بسجل التعارضات
        """
        cursor = self.sqlite_conn.cursor()

        if table_name:
            cursor.execute("""
                SELECT id, table_name, entity_id, entity_name, conflicting_fields,
                       resolution, severity, winner, resolved_by, resolved_at, created_at
                FROM conflict_log
                WHERE table_name = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (table_name, limit))
        else:
            cursor.execute("""
                SELECT id, table_name, entity_id, entity_name, conflicting_fields,
                       resolution, severity, winner, resolved_by, resolved_at, created_at
                FROM conflict_log
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        history = []

        for row in rows:
            record = dict(row)
            if record.get('conflicting_fields'):
                try:
                    record['conflicting_fields'] = json.loads(record['conflicting_fields'])
                except (json.JSONDecodeError, TypeError):
                    pass
            history.append(record)

        return history

    def cleanup_old_conflicts(self, days_old: int = 30) -> int:
        """
        تنظيف التعارضات القديمة المحلولة

        Args:
            days_old: عمر التعارضات بالأيام

        Returns:
            عدد السجلات المحذوفة
        """
        cursor = self.sqlite_conn.cursor()

        cursor.execute("""
            DELETE FROM conflict_log
            WHERE resolution != 'pending_review'
            AND created_at < datetime('now', '-' || ? || ' days')
        """, (days_old,))

        deleted = cursor.rowcount
        self.sqlite_conn.commit()

        if deleted > 0:
            logger.info(f"🗑️ تم حذف {deleted} تعارض قديم")

        return deleted


# ==========================================
# دوال مساعدة للاستخدام السريع
# ==========================================

def create_conflict_resolver(sqlite_conn: sqlite3.Connection) -> ConflictResolver:
    """إنشاء محلل تعارضات جديد"""
    return ConflictResolver(sqlite_conn)
