"""
🧪 اختبارات الروبوت المحاسبي (AccountingService)
اختبارات شاملة للتأكد من:
- توازن القيود المحاسبية
- صحة العمليات المالية
- Atomic Transactions
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.accounting_service_v2 import (
    ACC_CASH,
    ACC_EXP_OFFICE,
    ACC_EXP_SALARIES,
    ACC_EXP_SOFTWARE,
    ACC_RECEIVABLE,
    ACC_SERVICE_REV,
    ACC_VAT_PAYABLE,
    AccountingServiceV2,
)


@pytest.fixture
def accounting_service():
    """إنشاء خدمة محاسبية في الذاكرة للاختبار"""
    return AccountingServiceV2(":memory:")


class TestJournalEntryCreation:
    """اختبارات إنشاء القيود المحاسبية"""

    def test_balanced_entry_succeeds(self, accounting_service):
        """اختبار: القيد المتوازن ينجح"""
        lines = [
            {'account_code': ACC_CASH, 'debit': 1000, 'credit': 0},
            {'account_code': ACC_SERVICE_REV, 'debit': 0, 'credit': 1000}
        ]

        entry_id = accounting_service.create_journal_entry(
            description="قيد اختباري",
            lines=lines
        )

        assert entry_id > 0, "يجب أن يُنشأ القيد بنجاح"
        print(f"\n[OK] Created balanced entry #{entry_id}")

    def test_unbalanced_entry_fails(self, accounting_service):
        """اختبار: القيد غير المتوازن يفشل"""
        lines = [
            {'account_code': ACC_CASH, 'debit': 1000, 'credit': 0},
            {'account_code': ACC_SERVICE_REV, 'debit': 0, 'credit': 900}  # ناقص 100!
        ]

        with pytest.raises(ValueError) as exc_info:
            accounting_service.create_journal_entry(
                description="قيد غير متوازن",
                lines=lines
            )

        assert "not balanced" in str(exc_info.value).lower()
        print("\n[OK] Unbalanced entry correctly rejected")

    def test_entry_with_multiple_lines(self, accounting_service):
        """اختبار: قيد متعدد الأسطر"""
        # فاتورة مع ضريبة
        lines = [
            {'account_code': ACC_RECEIVABLE, 'debit': 1140, 'credit': 0},
            {'account_code': ACC_SERVICE_REV, 'debit': 0, 'credit': 1000},
            {'account_code': ACC_VAT_PAYABLE, 'debit': 0, 'credit': 140}
        ]

        entry_id = accounting_service.create_journal_entry(
            description="فاتورة مع ضريبة",
            lines=lines,
            ref_type="INVOICE",
            ref_id="INV-001"
        )

        assert entry_id > 0
        print(f"\n[OK] Multi-line entry #{entry_id} created")

    def test_decimal_precision(self, accounting_service):
        """اختبار: دقة الكسور العشرية"""
        # 1.1 + 2.2 في Python قد تساوي 3.3000000000000003
        lines = [
            {'account_code': ACC_CASH, 'debit': 1.1, 'credit': 0},
            {'account_code': ACC_CASH, 'debit': 2.2, 'credit': 0},
            {'account_code': ACC_SERVICE_REV, 'debit': 0, 'credit': 3.3}
        ]

        # يجب أن ينجح بفضل التقريب
        entry_id = accounting_service.create_journal_entry(
            description="اختبار الكسور",
            lines=lines
        )

        assert entry_id > 0
        print("\n[OK] Decimal precision handled correctly")


class TestInvoiceHandling:
    """اختبارات معالجة الفواتير"""

    def test_invoice_creates_correct_entry(self, accounting_service):
        """اختبار: الفاتورة تنشئ القيد الصحيح"""
        entry_id = accounting_service.handle_invoice_created(
            invoice_id="INV-2025-001",
            total_amount=1140.0,
            tax_amount=140.0,
            client_name="عميل اختباري"
        )

        assert entry_id > 0

        # التحقق من الأرصدة
        receivable = accounting_service.get_account_balance(ACC_RECEIVABLE)
        revenue = accounting_service.get_account_balance(ACC_SERVICE_REV)
        vat = accounting_service.get_account_balance(ACC_VAT_PAYABLE)

        assert abs(receivable - 1140.0) < 0.01, "رصيد العملاء خاطئ"
        assert abs(revenue - (-1000.0)) < 0.01, "رصيد الإيرادات خاطئ"
        assert abs(vat - (-140.0)) < 0.01, "رصيد الضريبة خاطئ"

        print("\n[OK] Invoice entry created with correct balances")

    def test_invoice_without_tax(self, accounting_service):
        """اختبار: فاتورة بدون ضريبة"""
        entry_id = accounting_service.handle_invoice_created(
            invoice_id="INV-2025-002",
            total_amount=1000.0,
            tax_amount=0.0,
            client_name="عميل معفي"
        )

        assert entry_id > 0

        receivable = accounting_service.get_account_balance(ACC_RECEIVABLE)
        assert abs(receivable - 1000.0) < 0.01

        print("\n[OK] Tax-free invoice handled correctly")


class TestPaymentHandling:
    """اختبارات معالجة الدفعات"""

    def test_cash_payment_reduces_receivable(self, accounting_service):
        """اختبار: الدفعة النقدية تقلل المديونية"""
        # إنشاء فاتورة أولاً
        accounting_service.handle_invoice_created(
            "INV-001", 1000.0, 0.0, "عميل"
        )

        initial_receivable = accounting_service.get_account_balance(ACC_RECEIVABLE)

        # استلام دفعة
        accounting_service.handle_payment_received(
            payment_id="PAY-001",
            amount=500.0,
            method="cash",
            client_name="عميل"
        )

        final_receivable = accounting_service.get_account_balance(ACC_RECEIVABLE)
        cash_balance = accounting_service.get_account_balance(ACC_CASH)

        assert abs(final_receivable - 500.0) < 0.01, "المديونية لم تنقص بشكل صحيح"
        assert abs(cash_balance - 500.0) < 0.01, "رصيد الخزنة خاطئ"

        print("\n[OK] Cash payment correctly reduces receivable")

    def test_full_payment_zeros_receivable(self, accounting_service):
        """اختبار: الدفع الكامل يصفّر المديونية"""
        # إنشاء فاتورة
        accounting_service.handle_invoice_created(
            "INV-002", 1000.0, 0.0, "عميل"
        )

        # دفع كامل
        accounting_service.handle_payment_received(
            "PAY-002", 1000.0, "cash", "عميل"
        )

        receivable = accounting_service.get_account_balance(ACC_RECEIVABLE)
        assert abs(receivable) < 0.01, "المديونية يجب أن تكون صفر"

        print("\n[OK] Full payment zeros receivable")


class TestExpenseHandling:
    """اختبارات معالجة المصروفات"""

    def test_expense_reduces_cash(self, accounting_service):
        """اختبار: المصروف يقلل الخزنة"""
        # إضافة رصيد للخزنة أولاً
        accounting_service.create_journal_entry(
            description="رأس مال",
            lines=[
                {'account_code': ACC_CASH, 'debit': 10000, 'credit': 0},
                {'account_code': '311100', 'debit': 0, 'credit': 10000}
            ]
        )

        initial_cash = accounting_service.get_account_balance(ACC_CASH)

        # تسجيل مصروف
        accounting_service.handle_expense_recorded(
            expense_id="EXP-001",
            amount=500.0,
            category="software",
            description="اشتراك سيرفر"
        )

        final_cash = accounting_service.get_account_balance(ACC_CASH)
        expense_balance = accounting_service.get_account_balance(ACC_EXP_SOFTWARE)

        assert abs(final_cash - 9500.0) < 0.01, "رصيد الخزنة خاطئ"
        assert abs(expense_balance - 500.0) < 0.01, "رصيد المصروف خاطئ"

        print("\n[OK] Expense correctly reduces cash")

    def test_expense_category_mapping(self, accounting_service):
        """اختبار: تصنيف المصروفات"""
        # إضافة رصيد
        accounting_service.create_journal_entry(
            description="رأس مال",
            lines=[
                {'account_code': ACC_CASH, 'debit': 50000, 'credit': 0},
                {'account_code': '311100', 'debit': 0, 'credit': 50000}
            ]
        )

        # مصروفات مختلفة
        accounting_service.handle_expense_recorded("E1", 1000, "salaries", "رواتب")
        accounting_service.handle_expense_recorded("E2", 2000, "rent", "إيجار")
        accounting_service.handle_expense_recorded("E3", 500, "software", "برامج")
        accounting_service.handle_expense_recorded("E4", 300, "unknown", "متنوع")

        assert abs(accounting_service.get_account_balance(ACC_EXP_SALARIES) - 1000) < 0.01
        assert abs(accounting_service.get_account_balance("520200") - 2000) < 0.01
        assert abs(accounting_service.get_account_balance(ACC_EXP_SOFTWARE) - 500) < 0.01
        assert abs(accounting_service.get_account_balance(ACC_EXP_OFFICE) - 300) < 0.01

        print("\n[OK] Expense categories mapped correctly")


class TestBooksBalance:
    """اختبارات توازن الدفاتر"""

    def test_books_always_balanced(self, accounting_service):
        """اختبار: الدفاتر دائماً متوازنة"""
        # سلسلة من العمليات
        accounting_service.handle_invoice_created("INV-1", 5000, 500, "عميل 1")
        accounting_service.handle_invoice_created("INV-2", 3000, 300, "عميل 2")
        accounting_service.handle_payment_received("PAY-1", 2000, "cash", "عميل 1")

        # التحقق من التوازن
        is_balanced, total_dr, total_cr = accounting_service.verify_books_balanced()

        assert is_balanced, f"الدفاتر غير متوازنة! Dr={total_dr}, Cr={total_cr}"
        assert abs(total_dr - total_cr) < 0.01

        print(f"\n[OK] Books balanced: Debit={total_dr}, Credit={total_cr}")

    def test_financial_summary(self, accounting_service):
        """اختبار: الملخص المالي"""
        # إنشاء بعض العمليات
        accounting_service.handle_invoice_created("INV-1", 1140, 140, "عميل")
        accounting_service.handle_payment_received("PAY-1", 1140, "cash", "عميل")

        summary = accounting_service.get_financial_summary()

        assert 'Asset' in summary or 'Revenue' in summary
        print(f"\n[OK] Financial summary: {summary}")


class TestEdgeCases:
    """اختبارات الحالات الحدية"""

    def test_zero_amount_entry(self, accounting_service):
        """اختبار: قيد بمبلغ صفر"""
        lines = [
            {'account_code': ACC_CASH, 'debit': 0, 'credit': 0},
            {'account_code': ACC_SERVICE_REV, 'debit': 0, 'credit': 0}
        ]

        entry_id = accounting_service.create_journal_entry(
            description="قيد صفري",
            lines=lines
        )

        assert entry_id > 0
        print("\n[OK] Zero amount entry handled")

    def test_very_small_amounts(self, accounting_service):
        """اختبار: مبالغ صغيرة جداً"""
        lines = [
            {'account_code': ACC_CASH, 'debit': 0.01, 'credit': 0},
            {'account_code': ACC_SERVICE_REV, 'debit': 0, 'credit': 0.01}
        ]

        entry_id = accounting_service.create_journal_entry(
            description="مبلغ صغير",
            lines=lines
        )

        assert entry_id > 0
        print("\n[OK] Very small amounts handled")

    def test_large_amounts(self, accounting_service):
        """اختبار: مبالغ كبيرة"""
        lines = [
            {'account_code': ACC_CASH, 'debit': 999999999.99, 'credit': 0},
            {'account_code': ACC_SERVICE_REV, 'debit': 0, 'credit': 999999999.99}
        ]

        entry_id = accounting_service.create_journal_entry(
            description="مبلغ كبير",
            lines=lines
        )

        assert entry_id > 0
        print("\n[OK] Large amounts handled")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
