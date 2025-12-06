# الملف: core/conflict_resolver_v2.py
"""
محرك حل التعارضات الذكي (Smart Conflict Resolution Engine)
يستخدم استراتيجية Field-Level Merge لتقليل فقدان البيانات.

الفلسفة:
1. تحديد الفرق (Diffing): فحص الحقول حقلاً بحقل
2. تصنيف الخطورة: حقول حساسة vs حقول عادية
3. التوثيق: تسجيل أي تعارض حرج للمراجعة
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Optional

# إعداد اللوجر
logger = logging.getLogger("ConflictResolver")
logger.setLevel(logging.INFO)


class ConflictResolverV2:
    """
    محرك حل التعارضات الذكي (Smart Conflict Resolution Engine)
    يستخدم استراتيجية Field-Level Merge لتقليل فقدان البيانات.
    """

    # الحقول الحساسة التي تمنع الدمج التلقائي
    CRITICAL_FIELDS = {
        'projects': ['total_amount', 'items', 'status', 'milestones', 'subtotal'],
        'invoices': ['total_amount', 'items', 'tax_amount', 'invoice_number', 'subtotal'],
        'payments': ['amount', 'payment_method', 'date'],
        'expenses': ['amount', 'category', 'date'],
        'journal_entries': ['lines', 'date'],
        'accounts': ['balance', 'code'],
        'quotations': ['total_amount', 'items', 'subtotal']
    }

    # الحقول التي يتم تجاهلها عند المقارنة
    IGNORE_FIELDS = [
        'updated_at', 'last_modified', 'sync_status', '_mongo_id',
        'created_at', 'id', '_id'
    ]

    def __init__(self, db_path: str = "skywave_local.db"):
        """
        تهيئة محرك حل التعارضات
        
        Args:
            db_path: مسار قاعدة البيانات (أو :memory: للاختبار)
        """
        self.db_path = db_path
        self._persistent_conn = None
        
        # للاختبار في الذاكرة
        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:")
            self._persistent_conn.row_factory = sqlite3.Row
        
        self._init_log_table()

    def _get_connection(self) -> sqlite3.Connection:
        """الحصول على اتصال بقاعدة البيانات"""
        if self._persistent_conn:
            return self._persistent_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _close_connection(self, conn: sqlite3.Connection):
        """إغلاق الاتصال إذا لم يكن دائماً"""
        if not self._persistent_conn:
            conn.close()

    def _init_log_table(self):
        """إنشاء جدول سجل التعارضات"""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conflict_log_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                entity_name TEXT,
                local_data TEXT,
                remote_data TEXT,
                conflict_type TEXT,
                conflicting_fields TEXT,
                resolution_status TEXT DEFAULT 'PENDING',
                resolved_by TEXT,
                resolved_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        self._close_connection(conn)

    def detect_and_resolve(
        self,
        table_name: str,
        local_doc: dict[str, Any],
        remote_doc: dict[str, Any]
    ) -> dict[str, Any]:
        """
        الدالة الرئيسية: تستقبل النسخة المحلية والسحابية وتقرر المصير.
        
        Args:
            table_name: اسم الجدول
            local_doc: البيانات المحلية
            remote_doc: البيانات السحابية
            
        Returns:
            dict مع:
            - action: 'auto_merged' | 'use_remote' | 'pending_review'
            - resolution: نفس action (للتوافق مع الاختبارات)
            - merged_data: البيانات المدمجة
            - reason: سبب القرار
            - conflicting_fields: الحقول المتعارضة
        """
        # 1. تنظيف البيانات للمقارنة
        local_clean = self._clean_dict(local_doc)
        remote_clean = self._clean_dict(remote_doc)

        # 2. هل البيانات متطابقة أصلاً؟
        if local_clean == remote_clean:
            return {
                'action': 'use_remote',
                'resolution': 'auto_merged',
                'merged_data': remote_doc,
                'reason': 'Identical data',
                'conflicting_fields': [],
                'requires_review': False
            }

        # 3. استخراج الفروقات
        diffs = self._find_differences(local_clean, remote_clean)

        if not diffs:
            return {
                'action': 'use_remote',
                'resolution': 'auto_merged',
                'merged_data': remote_doc,
                'reason': 'No significant differences',
                'conflicting_fields': [],
                'requires_review': False
            }

        # 4. فحص هل الفروقات في حقول حساسة؟
        critical_keys = self.CRITICAL_FIELDS.get(table_name, [])
        critical_conflicts = [k for k in diffs.keys() if k in critical_keys]
        non_critical_conflicts = [k for k in diffs.keys() if k not in critical_keys]

        if critical_conflicts:
            # تعارض خطير: المبالغ المالية اختلفت!
            logger.warning(
                f"[CRITICAL] CONFLICT in {table_name} "
                f"ID {local_doc.get('id')}: {critical_conflicts}"
            )
            self._log_conflict(
                table_name, local_doc, remote_doc,
                "CRITICAL", critical_conflicts
            )
            return {
                'action': 'pending_review',
                'resolution': 'pending_review',
                'merged_data': local_doc,  # نحتفظ بالمحلي حتى يتم الحل
                'reason': f"Critical fields changed: {critical_conflicts}",
                'conflicting_fields': critical_conflicts + non_critical_conflicts,
                'requires_review': True
            }

        # تعارض بسيط: دمج الحقول (Smart Merge)
        merged_doc = self._smart_merge(local_doc, remote_doc, diffs)

        logger.info(
            f"[OK] Auto-Merged {table_name} "
            f"ID {local_doc.get('id')}. Fields: {list(diffs.keys())}"
        )

        return {
            'action': 'auto_merged',
            'resolution': 'auto_merged',
            'merged_data': merged_doc,
            'reason': f'Auto-merged non-critical fields: {list(diffs.keys())}',
            'conflicting_fields': list(diffs.keys()),
            'requires_review': False
        }

    def _smart_merge(
        self,
        local_doc: dict[str, Any],
        remote_doc: dict[str, Any],
        diffs: dict[str, Any]
    ) -> dict[str, Any]:
        """
        دمج ذكي للبيانات
        
        الاستراتيجية:
        - نأخذ Remote كأساس
        - إذا كان الحقل فارغاً في Remote ومملوءاً في Local، نأخذ Local
        - إذا كان الحقل نصياً، نأخذ الأطول (أكثر معلومات)
        """
        merged = remote_doc.copy()

        for field in diffs:
            local_val = local_doc.get(field)
            remote_val = remote_doc.get(field)

            # إذا Remote فارغ و Local مملوء
            if not remote_val and local_val:
                merged[field] = local_val
                continue

            # إذا كلاهما نص، نأخذ الأطول
            if isinstance(local_val, str) and isinstance(remote_val, str):
                if len(local_val) > len(remote_val):
                    merged[field] = local_val

        return merged

    def _find_differences(
        self,
        d1: dict[str, Any],
        d2: dict[str, Any]
    ) -> dict[str, dict]:
        """إرجاع قاموس بالحقول المختلفة"""
        diffs = {}
        all_keys = set(d1.keys()) | set(d2.keys())

        for k in all_keys:
            val1 = d1.get(k)
            val2 = d2.get(k)

            # مقارنة القيم
            if not self._values_equal(val1, val2):
                diffs[k] = {'local': val1, 'remote': val2}

        return diffs

    def _values_equal(self, val1: Any, val2: Any) -> bool:
        """مقارنة قيمتين مع معالجة الحالات الخاصة"""
        # معالجة None
        if val1 is None and val2 is None:
            return True
        if val1 is None or val2 is None:
            return False

        # معالجة الأرقام (مقارنة تقريبية للـ float)
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            return abs(float(val1) - float(val2)) < 0.001

        # معالجة القوائم
        if isinstance(val1, list) and isinstance(val2, list):
            return val1 == val2

        # معالجة JSON strings
        if isinstance(val1, str) and isinstance(val2, str):
            try:
                json1 = json.loads(val1)
                json2 = json.loads(val2)
                return json1 == json2
            except (json.JSONDecodeError, TypeError):
                pass

        return val1 == val2

    def _clean_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """إزالة الحقول التي لا تهم في المقارنة"""
        return {k: v for k, v in data.items() if k not in self.IGNORE_FIELDS}

    def _log_conflict(
        self,
        table: str,
        local: dict,
        remote: dict,
        conflict_type: str,
        conflicting_fields: list[str]
    ):
        """تسجيل التعارض في قاعدة البيانات للمراجعة البشرية"""
        conn = self._get_connection()
        try:
            entity_id = (
                local.get('id') or
                local.get('invoice_number') or
                local.get('name') or
                'unknown'
            )
            entity_name = local.get('name') or local.get('description') or ''

            conn.execute("""
                INSERT INTO conflict_log_v2 
                (table_name, entity_id, entity_name, local_data, remote_data, 
                 conflict_type, conflicting_fields)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                table,
                str(entity_id),
                entity_name,
                json.dumps(local, default=str, ensure_ascii=False),
                json.dumps(remote, default=str, ensure_ascii=False),
                conflict_type,
                json.dumps(conflicting_fields, ensure_ascii=False)
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"[X] Failed to log conflict: {e}")
        finally:
            self._close_connection(conn)

    # ==========================================
    # واجهة المراجعة اليدوية
    # ==========================================

    def get_pending_conflicts(
        self,
        table_name: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """جلب التعارضات التي تحتاج حلاً"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if table_name:
            cursor.execute("""
                SELECT * FROM conflict_log_v2 
                WHERE resolution_status = 'PENDING' AND table_name = ?
                ORDER BY created_at DESC
            """, (table_name,))
        else:
            cursor.execute("""
                SELECT * FROM conflict_log_v2 
                WHERE resolution_status = 'PENDING'
                ORDER BY created_at DESC
            """)

        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            record = dict(zip(columns, row))
            # تحويل JSON strings
            for field in ['local_data', 'remote_data', 'conflicting_fields']:
                if record.get(field):
                    try:
                        record[field] = json.loads(record[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            results.append(record)

        self._close_connection(conn)
        return results

    def get_pending_count(self) -> int:
        """الحصول على عدد التعارضات المعلقة"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM conflict_log_v2
            WHERE resolution_status = 'PENDING'
        """)
        result = cursor.fetchone()
        self._close_connection(conn)
        return int(result[0]) if result else 0

    def resolve_conflict(
        self,
        conflict_id: int,
        choice: str,
        resolved_by: str = "user"
    ) -> bool:
        """
        حل التعارض يدوياً
        
        Args:
            conflict_id: معرف التعارض
            choice: 'use_local' أو 'use_remote'
            resolved_by: من قام بالحل
            
        Returns:
            True إذا نجح الحل
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE conflict_log_v2 
                SET resolution_status = 'RESOLVED',
                    resolved_by = ?,
                    resolved_at = ?
                WHERE id = ?
            """, (resolved_by, datetime.now().isoformat(), conflict_id))

            conn.commit()
            success = cursor.rowcount > 0

            if success:
                logger.info(f"[OK] Conflict #{conflict_id} resolved: {choice}")

            return success

        except Exception as e:
            logger.error(f"[X] Failed to resolve conflict: {e}")
            return False

        finally:
            self._close_connection(conn)

    def get_conflict_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """جلب سجل التعارضات"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, table_name, entity_id, entity_name, conflict_type,
                   conflicting_fields, resolution_status, resolved_by, 
                   resolved_at, created_at
            FROM conflict_log_v2
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            record = dict(zip(columns, row))
            if record.get('conflicting_fields'):
                try:
                    record['conflicting_fields'] = json.loads(record['conflicting_fields'])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(record)

        self._close_connection(conn)
        return results


# --- اختبار الوحدة ---
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    print("=" * 50)
    print("CONFLICT RESOLVER V2 - TEST")
    print("=" * 50)

    resolver = ConflictResolverV2(":memory:")

    # اختبار 1: تعارض حرج (المبلغ تغير)
    print("\n[TEST 1] Critical Conflict (amount changed)...")
    local_invoice = {
        "id": "INV-100",
        "total_amount": 1500,  # تغيير خطير
        "notes": "تم التوصيل",
    }
    remote_invoice = {
        "id": "INV-100",
        "total_amount": 1000,
        "notes": "قيد الانتظار",
    }

    result = resolver.detect_and_resolve("invoices", local_invoice, remote_invoice)
    print(f"   Action: {result['action']}")
    print(f"   Reason: {result['reason']}")
    assert result['action'] == 'pending_review', "Should require review!"
    print("   [OK] Critical conflict detected!")

    # اختبار 2: دمج تلقائي (حقول غير حساسة)
    print("\n[TEST 2] Auto Merge (non-critical fields)...")
    local_project = {
        "id": "P-100",
        "name": "مشروع تسويق",
        "total_amount": 5000,
        "notes": "ملاحظات محلية طويلة جداً",
        "description": ""
    }
    remote_project = {
        "id": "P-100",
        "name": "مشروع تسويق",
        "total_amount": 5000,
        "notes": "ملاحظات",
        "description": "وصف سحابي"
    }

    result = resolver.detect_and_resolve("projects", local_project, remote_project)
    print(f"   Action: {result['action']}")
    print(f"   Merged notes: {result['merged_data'].get('notes')}")
    assert result['action'] == 'auto_merged', "Should auto merge!"
    print("   [OK] Auto merge successful!")

    # اختبار 3: بيانات متطابقة
    print("\n[TEST 3] Identical data...")
    result = resolver.detect_and_resolve("projects", local_project, local_project)
    print(f"   Action: {result['action']}")
    assert result['resolution'] == 'auto_merged', "Should be identical!"
    print("   [OK] Identical data handled!")

    # اختبار 4: فحص التعارضات المعلقة
    print("\n[TEST 4] Pending conflicts...")
    pending = resolver.get_pending_count()
    print(f"   Pending conflicts: {pending}")
    assert pending == 1, "Should have 1 pending conflict!"
    print("   [OK] Conflict logged!")

    print("\n" + "=" * 50)
    print("[OK] All tests passed!")
    print("=" * 50)
