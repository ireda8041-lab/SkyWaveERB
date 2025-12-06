"""
اختبارات محرك حل التعارضات (ConflictResolver)
اختبارات شاملة للتأكد من:
- كشف التعارضات الحرجة
- الدمج التلقائي للحقول غير الحساسة
- تسجيل التعارضات للمراجعة
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.conflict_resolver_v2 import ConflictResolverV2


@pytest.fixture
def resolver():
    """إنشاء محرك حل التعارضات في الذاكرة"""
    return ConflictResolverV2(":memory:")


class TestCriticalConflicts:
    """اختبارات التعارضات الحرجة"""

    def test_invoice_amount_conflict(self, resolver):
        """اختبار: تعارض في مبلغ الفاتورة يتطلب مراجعة"""
        local = {"id": "INV-001", "total_amount": 1500, "notes": "محلي"}
        remote = {"id": "INV-001", "total_amount": 1000, "notes": "سحابي"}

        result = resolver.detect_and_resolve("invoices", local, remote)

        assert result['action'] == 'pending_review'
        assert result['requires_review'] == True
        assert 'total_amount' in result['conflicting_fields']
        print("\n[OK] Invoice amount conflict requires review")

    def test_project_items_conflict(self, resolver):
        """اختبار: تعارض في بنود المشروع"""
        local = {
            "id": "P-001",
            "items": [{"name": "خدمة 1", "price": 500}],
            "total_amount": 500
        }
        remote = {
            "id": "P-001",
            "items": [{"name": "خدمة 2", "price": 700}],
            "total_amount": 500
        }

        result = resolver.detect_and_resolve("projects", local, remote)

        assert result['action'] == 'pending_review'
        assert 'items' in result['conflicting_fields']
        print("\n[OK] Project items conflict requires review")

    def test_payment_amount_conflict(self, resolver):
        """اختبار: تعارض في مبلغ الدفعة"""
        local = {"id": "PAY-001", "amount": 500, "date": "2025-01-01"}
        remote = {"id": "PAY-001", "amount": 600, "date": "2025-01-01"}

        result = resolver.detect_and_resolve("payments", local, remote)

        assert result['action'] == 'pending_review'
        assert 'amount' in result['conflicting_fields']
        print("\n[OK] Payment amount conflict requires review")

    def test_expense_category_conflict(self, resolver):
        """اختبار: تعارض في تصنيف المصروف"""
        local = {"id": "EXP-001", "amount": 100, "category": "software"}
        remote = {"id": "EXP-001", "amount": 100, "category": "rent"}

        result = resolver.detect_and_resolve("expenses", local, remote)

        assert result['action'] == 'pending_review'
        assert 'category' in result['conflicting_fields']
        print("\n[OK] Expense category conflict requires review")


class TestAutoMerge:
    """اختبارات الدمج التلقائي"""

    def test_merge_non_critical_fields(self, resolver):
        """اختبار: دمج الحقول غير الحساسة"""
        local = {
            "id": "P-001",
            "name": "مشروع",
            "total_amount": 1000,
            "notes": "ملاحظات محلية",
            "description": ""
        }
        remote = {
            "id": "P-001",
            "name": "مشروع",
            "total_amount": 1000,
            "notes": "",
            "description": "وصف سحابي"
        }

        result = resolver.detect_and_resolve("projects", local, remote)

        assert result['action'] == 'auto_merged'
        assert result['requires_review'] == False
        # يجب أن يأخذ الملاحظات من المحلي (لأن السحابي فارغ)
        assert result['merged_data']['notes'] == "ملاحظات محلية"
        # يجب أن يأخذ الوصف من السحابي
        assert result['merged_data']['description'] == "وصف سحابي"
        print("\n[OK] Non-critical fields merged correctly")

    def test_merge_longer_text(self, resolver):
        """اختبار: أخذ النص الأطول عند الدمج"""
        local = {
            "id": "P-001",
            "total_amount": 1000,
            "notes": "ملاحظات طويلة جداً تحتوي على تفاصيل كثيرة"
        }
        remote = {
            "id": "P-001",
            "total_amount": 1000,
            "notes": "ملاحظات قصيرة"
        }

        result = resolver.detect_and_resolve("projects", local, remote)

        assert result['action'] == 'auto_merged'
        # يجب أن يأخذ النص الأطول
        assert "تفاصيل كثيرة" in result['merged_data']['notes']
        print("\n[OK] Longer text preserved in merge")

    def test_identical_data_no_conflict(self, resolver):
        """اختبار: البيانات المتطابقة لا تسبب تعارض"""
        data = {"id": "P-001", "name": "مشروع", "total_amount": 1000}

        result = resolver.detect_and_resolve("projects", data, data.copy())

        assert result['resolution'] == 'auto_merged'
        assert result['requires_review'] == False
        assert len(result['conflicting_fields']) == 0
        print("\n[OK] Identical data handled correctly")


class TestIgnoredFields:
    """اختبارات الحقول المتجاهلة"""

    def test_ignore_timestamps(self, resolver):
        """اختبار: تجاهل حقول التوقيت"""
        local = {
            "id": "P-001",
            "name": "مشروع",
            "total_amount": 1000,
            "updated_at": "2025-01-01 10:00:00",
            "last_modified": "2025-01-01 10:00:00"
        }
        remote = {
            "id": "P-001",
            "name": "مشروع",
            "total_amount": 1000,
            "updated_at": "2025-01-02 12:00:00",
            "last_modified": "2025-01-02 12:00:00"
        }

        result = resolver.detect_and_resolve("projects", local, remote)

        # يجب ألا يكون هناك تعارض (الفرق فقط في التوقيت)
        assert result['resolution'] == 'auto_merged'
        assert len(result['conflicting_fields']) == 0
        print("\n[OK] Timestamps ignored correctly")

    def test_ignore_sync_status(self, resolver):
        """اختبار: تجاهل حالة المزامنة"""
        local = {"id": "P-001", "name": "مشروع", "sync_status": "pending"}
        remote = {"id": "P-001", "name": "مشروع", "sync_status": "synced"}

        result = resolver.detect_and_resolve("projects", local, remote)

        assert result['resolution'] == 'auto_merged'
        print("\n[OK] Sync status ignored correctly")


class TestConflictLogging:
    """اختبارات تسجيل التعارضات"""

    def test_critical_conflict_logged(self, resolver):
        """اختبار: التعارض الحرج يُسجل"""
        local = {"id": "INV-001", "total_amount": 1500}
        remote = {"id": "INV-001", "total_amount": 1000}

        resolver.detect_and_resolve("invoices", local, remote)

        pending = resolver.get_pending_count()
        assert pending == 1, "Should have 1 pending conflict"
        print("\n[OK] Critical conflict logged")

    def test_get_pending_conflicts(self, resolver):
        """اختبار: جلب التعارضات المعلقة"""
        # إنشاء تعارضين
        resolver.detect_and_resolve(
            "invoices",
            {"id": "INV-001", "total_amount": 1500},
            {"id": "INV-001", "total_amount": 1000}
        )
        resolver.detect_and_resolve(
            "payments",
            {"id": "PAY-001", "amount": 500},
            {"id": "PAY-001", "amount": 600}
        )

        pending = resolver.get_pending_conflicts()

        assert len(pending) == 2
        assert any(c['table_name'] == 'invoices' for c in pending)
        assert any(c['table_name'] == 'payments' for c in pending)
        print("\n[OK] Pending conflicts retrieved")

    def test_resolve_conflict(self, resolver):
        """اختبار: حل التعارض يدوياً"""
        # إنشاء تعارض
        resolver.detect_and_resolve(
            "invoices",
            {"id": "INV-001", "total_amount": 1500},
            {"id": "INV-001", "total_amount": 1000}
        )

        # جلب التعارض
        pending = resolver.get_pending_conflicts()
        conflict_id = pending[0]['id']

        # حل التعارض
        success = resolver.resolve_conflict(conflict_id, "use_local", "admin")

        assert success == True
        assert resolver.get_pending_count() == 0
        print("\n[OK] Conflict resolved manually")


class TestEdgeCases:
    """اختبارات الحالات الحدية"""

    def test_empty_local_field(self, resolver):
        """اختبار: حقل فارغ محلياً"""
        local = {"id": "P-001", "total_amount": 1000, "notes": ""}
        remote = {"id": "P-001", "total_amount": 1000, "notes": "ملاحظات"}

        result = resolver.detect_and_resolve("projects", local, remote)

        assert result['action'] == 'auto_merged'
        assert result['merged_data']['notes'] == "ملاحظات"
        print("\n[OK] Empty local field handled")

    def test_null_values(self, resolver):
        """اختبار: قيم None"""
        local = {"id": "P-001", "total_amount": 1000, "notes": None}
        remote = {"id": "P-001", "total_amount": 1000, "notes": "ملاحظات"}

        result = resolver.detect_and_resolve("projects", local, remote)

        assert result['action'] == 'auto_merged'
        print("\n[OK] Null values handled")

    def test_float_precision(self, resolver):
        """اختبار: دقة الأرقام العشرية"""
        local = {"id": "P-001", "total_amount": 1000.001}
        remote = {"id": "P-001", "total_amount": 1000.002}

        result = resolver.detect_and_resolve("projects", local, remote)

        # الفرق أقل من 0.001، يجب أن يعتبرهما متساويين
        assert result['resolution'] == 'auto_merged'
        print("\n[OK] Float precision handled")

    def test_list_comparison(self, resolver):
        """اختبار: مقارنة القوائم"""
        local = {"id": "P-001", "total_amount": 1000, "items": [1, 2, 3]}
        remote = {"id": "P-001", "total_amount": 1000, "items": [1, 2, 3]}

        result = resolver.detect_and_resolve("projects", local, remote)

        assert result['resolution'] == 'auto_merged'
        print("\n[OK] List comparison handled")

    def test_unknown_table(self, resolver):
        """اختبار: جدول غير معروف"""
        local = {"id": "X-001", "value": 100}
        remote = {"id": "X-001", "value": 200}

        result = resolver.detect_and_resolve("unknown_table", local, remote)

        # جدول غير معروف = لا توجد حقول حساسة = دمج تلقائي
        assert result['action'] == 'auto_merged'
        print("\n[OK] Unknown table handled")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
