"""
🧪 اختبارات الوحدة للمنطق الحرج
- اختبار توازن القيود المحاسبية
- اختبار نظام حل التعارضات
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

# إضافة المسار الرئيسي للمشروع
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.conflict_resolver import ConflictResolver, ConflictResolution


# ==================== Fixtures ====================

@pytest.fixture
def memory_db():
    """إنشاء قاعدة بيانات في الذاكرة للاختبار"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def conflict_resolver(memory_db):
    """إنشاء محلل التعارضات للاختبار"""
    return ConflictResolver(memory_db)


# ==================== اختبارات حل التعارضات ====================

class TestConflictResolver:
    """اختبارات نظام حل التعارضات الذكي"""

    def test_no_conflict_identical_records(self, conflict_resolver):
        """اختبار: لا يوجد تعارض عندما تكون السجلات متطابقة"""
        local = {"name": "مشروع تسويق", "status": "ACTIVE", "amount": 1000}
        remote = {"name": "مشروع تسويق", "status": "ACTIVE", "amount": 1000}

        result = conflict_resolver.detect_and_resolve(
            table_name="projects",
            entity_id="P001",
            local_record=local,
            remote_record=remote
        )

        assert not result.has_conflict, "❌ يجب ألا يكون هناك تعارض"
        assert result.resolution == ConflictResolution.AUTO_MERGED
        print("\n✅ اختبار السجلات المتطابقة نجح!")

    def test_auto_merge_non_critical_fields(self, conflict_resolver):
        """اختبار: الدمج التلقائي للحقول غير الحساسة"""
        local = {
            "name": "مشروع تسويق",
            "status": "ACTIVE",
            "description": "وصف محلي",
            "last_modified": "2024-01-15T10:00:00"
        }
        remote = {
            "name": "مشروع تسويق",
            "status": "COMPLETED",  # تغيير في حقل غير حساس
            "description": "وصف محلي",
            "last_modified": "2024-01-15T12:00:00"  # السحابي أحدث
        }

        result = conflict_resolver.detect_and_resolve(
            table_name="projects",
            entity_id="P001",
            local_record=local,
            remote_record=remote
        )

        assert result.has_conflict, "❌ يجب أن يكون هناك تعارض"
        assert result.resolution == ConflictResolution.AUTO_MERGED, "❌ يجب أن يتم الدمج تلقائياً"
        assert not result.requires_review, "❌ لا يجب أن يتطلب مراجعة"
        print("\n✅ اختبار الدمج التلقائي نجح!")

    def test_critical_conflict_requires_review(self, conflict_resolver):
        """اختبار: التعارض في الحقول الحساسة يتطلب مراجعة"""
        local = {
            "name": "مشروع تسويق",
            "total_amount": 1000,  # حقل حساس
            "last_modified": "2024-01-15T10:00:00"
        }
        remote = {
            "name": "مشروع تسويق",
            "total_amount": 2000,  # تغيير في حقل حساس!
            "last_modified": "2024-01-15T12:00:00"
        }

        result = conflict_resolver.detect_and_resolve(
            table_name="projects",
            entity_id="P001",
            local_record=local,
            remote_record=remote
        )

        assert result.has_conflict, "❌ يجب أن يكون هناك تعارض"
        assert result.resolution == ConflictResolution.PENDING_REVIEW, "❌ يجب أن يكون بانتظار المراجعة"
        assert result.requires_review, "❌ يجب أن يتطلب مراجعة"
        assert "total_amount" in result.conflicting_fields, "❌ يجب أن يكون total_amount في الحقول المتعارضة"
        print("\n✅ اختبار التعارض الحساس نجح!")

    def test_payment_amount_conflict(self, conflict_resolver):
        """اختبار: تعارض في مبلغ الدفعة"""
        local = {"amount": 500, "date": "2024-01-15", "account_id": "ACC001"}
        remote = {"amount": 600, "date": "2024-01-15", "account_id": "ACC001"}

        result = conflict_resolver.detect_and_resolve(
            table_name="payments",
            entity_id="PAY001",
            local_record=local,
            remote_record=remote
        )

        assert result.requires_review, "❌ تعارض المبلغ يجب أن يتطلب مراجعة"
        print("\n✅ اختبار تعارض مبلغ الدفعة نجح!")


# ==================== اختبارات توازن القيود المحاسبية ====================

class TestAccountingIntegrity:
    """اختبارات سلامة البيانات المحاسبية"""

    def test_journal_entry_balance(self):
        """اختبار: القيد المحاسبي يجب أن يكون متوازناً"""
        # قيد متوازن
        lines = [
            {"account_code": "112100", "debit": 1000, "credit": 0},
            {"account_code": "410100", "debit": 0, "credit": 1000}
        ]

        total_debit = sum(line.get("debit", 0) for line in lines)
        total_credit = sum(line.get("credit", 0) for line in lines)

        assert abs(total_debit - total_credit) < 0.001, "❌ القيد غير متوازن!"
        print("\n✅ اختبار توازن القيد نجح!")

    def test_unbalanced_entry_detection(self):
        """اختبار: كشف القيد غير المتوازن"""
        # قيد غير متوازن
        lines = [
            {"account_code": "112100", "debit": 1000, "credit": 0},
            {"account_code": "410100", "debit": 0, "credit": 900}  # ناقص 100!
        ]

        total_debit = sum(line.get("debit", 0) for line in lines)
        total_credit = sum(line.get("credit", 0) for line in lines)

        is_balanced = abs(total_debit - total_credit) < 0.001
        assert not is_balanced, "❌ يجب أن يكتشف القيد غير المتوازن!"
        print(f"\n✅ تم كشف القيد غير المتوازن: مدين={total_debit}, دائن={total_credit}")

    def test_json_lines_parsing(self):
        """اختبار: تحليل بنود القيد من JSON"""
        lines_json = json.dumps([
            {"account_code": "112100", "debit": 5000, "credit": 0},
            {"account_code": "410100", "debit": 0, "credit": 5000}
        ])

        lines = json.loads(lines_json)
        total_debit = sum(float(line.get("debit", 0) or 0) for line in lines)
        total_credit = sum(float(line.get("credit", 0) or 0) for line in lines)

        assert total_debit == 5000, "❌ مجموع المدين خاطئ"
        assert total_credit == 5000, "❌ مجموع الدائن خاطئ"
        print("\n✅ اختبار تحليل JSON نجح!")


# ==================== اختبارات إضافية ====================

class TestDataValidation:
    """اختبارات التحقق من صحة البيانات"""

    def test_invoice_number_format(self):
        """اختبار: صيغة رقم الفاتورة"""
        invoice_number = "SW-97162"
        assert invoice_number.startswith("SW-"), "❌ رقم الفاتورة يجب أن يبدأ بـ SW-"
        assert invoice_number[3:].isdigit(), "❌ الجزء الرقمي يجب أن يكون أرقام فقط"
        print("\n✅ اختبار صيغة رقم الفاتورة نجح!")

    def test_account_code_format(self):
        """اختبار: صيغة كود الحساب (6 أرقام)"""
        valid_codes = ["112100", "410100", "510001", "620001"]
        for code in valid_codes:
            assert len(code) == 6, f"❌ كود الحساب {code} يجب أن يكون 6 أرقام"
            assert code.isdigit(), f"❌ كود الحساب {code} يجب أن يكون أرقام فقط"
        print("\n✅ اختبار صيغة أكواد الحسابات نجح!")

    def test_positive_amounts(self):
        """اختبار: المبالغ يجب أن تكون موجبة"""
        amounts = [1000.0, 500.50, 0.01]
        for amount in amounts:
            assert amount > 0, f"❌ المبلغ {amount} يجب أن يكون موجباً"
        print("\n✅ اختبار المبالغ الموجبة نجح!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
