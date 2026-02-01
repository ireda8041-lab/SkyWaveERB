from unittest.mock import patch

import pytest

from core import schemas
from services.accounting_service import AccountingService


class TestAccountingService:
    @pytest.fixture
    def service(self, mock_repo, mock_event_bus):
        # Patching internal method to prevent repo calls during init
        with patch.object(AccountingService, "_ensure_default_accounts_exist"):
            return AccountingService(mock_repo, mock_event_bus)

    def test_initialization_subscribes_to_payment_events(self, mock_repo, mock_event_bus):
        """
        ⚡ نظام محاسبي مبسط: فقط أحداث الدفعات والمصروفات
        بدون قيود يومية - فقط تحديث أرصدة الحسابات النقدية
        """
        # Setup & Action
        with patch.object(AccountingService, "_ensure_default_accounts_exist"):
            service = AccountingService(mock_repo, mock_event_bus)

        # Assert - التحقق من الاشتراك في أحداث الدفعات والمصروفات فقط
        mock_event_bus.subscribe.assert_any_call("PAYMENT_RECEIVED", service.handle_new_payment)
        mock_event_bus.subscribe.assert_any_call("EXPENSE_CREATED", service.handle_new_expense)

    def test_get_account_ledger_report_includes_payments_and_expenses_sorted(
        self, service, mock_repo
    ):
        from datetime import datetime

        account = schemas.Account(
            name="الخزنة",
            code="1111",
            type=schemas.AccountType.CASH,
            balance=0.0,
        )
        mock_repo.get_account_by_id.return_value = account
        mock_repo.get_account_by_code.return_value = account

        payment = schemas.Payment(
            project_id="p1",
            client_id="c1",
            date=datetime(2026, 1, 5, 12, 0, 0),
            amount=100.0,
            account_id="1111",
            method="Cash",
        )
        expense = schemas.Expense(
            date=datetime(2026, 1, 7, 9, 0, 0),
            category="إيجار",
            amount=40.0,
            description="Rent",
            account_id="1111",
            payment_account_id=None,
            project_id=None,
        )
        entry = schemas.JournalEntry(
            date=datetime(2026, 1, 10, 10, 0, 0),
            description="قيد اختبار",
            lines=[
                schemas.JournalEntryLine(
                    account_id="1111",
                    account_code="1111",
                    debit=10.0,
                    credit=0.0,
                    description="مدين",
                )
            ],
            related_document_id="J1",
        )

        mock_repo.get_all_payments.return_value = [payment]
        mock_repo.get_all_expenses.return_value = [expense]
        mock_repo.get_all_journal_entries.return_value = [entry]
        mock_repo.sum_payments_before.return_value = 0.0
        mock_repo.sum_expenses_paid_before.return_value = 0.0
        mock_repo.sum_expenses_charged_before.return_value = 0.0
        mock_repo.get_journal_entries_before.return_value = []
        mock_repo.get_journal_entries_between.return_value = [entry]
        mock_repo.get_payments_by_account.return_value = [payment]
        mock_repo.get_expenses_paid_from_account.return_value = [expense]
        mock_repo.get_expenses_charged_to_account.return_value = []

        report = service.get_account_ledger_report(
            "1111", datetime(2026, 1, 1, 0, 0, 0), datetime(2026, 1, 31, 23, 59, 59)
        )

        movements = report["movements"]
        assert [m["date"] for m in movements] == [
            payment.date,
            expense.date,
            entry.date,
        ]
        assert report["opening_balance"] == 0.0
        assert report["total_debit"] == 110.0
        assert report["total_credit"] == 40.0
        assert report["net_movement"] == 70.0
        assert report["ending_balance"] == 70.0
