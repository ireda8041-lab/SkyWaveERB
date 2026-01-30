
from unittest.mock import patch

import pytest

from core import schemas
from services.accounting_service import AccountingService


class TestAccountingService:
    @pytest.fixture
    def service(self, mock_repo, mock_event_bus):
        # Patching internal method to prevent repo calls during init
        with patch.object(AccountingService, '_ensure_default_accounts_exist'):
            return AccountingService(mock_repo, mock_event_bus)

    def test_initialization_subscribes_to_payment_events(self, mock_repo, mock_event_bus):
        """
        ⚡ نظام محاسبي مبسط: فقط أحداث الدفعات والمصروفات
        بدون قيود يومية - فقط تحديث أرصدة الحسابات النقدية
        """
        # Setup & Action
        with patch.object(AccountingService, '_ensure_default_accounts_exist'):
            service = AccountingService(mock_repo, mock_event_bus)

        # Assert - التحقق من الاشتراك في أحداث الدفعات والمصروفات فقط
        mock_event_bus.subscribe.assert_any_call('PAYMENT_RECEIVED', service.handle_new_payment)
        mock_event_bus.subscribe.assert_any_call('EXPENSE_CREATED', service.handle_new_expense)
