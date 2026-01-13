
import pytest
from unittest.mock import MagicMock, ANY, patch, call
from services.accounting_service import AccountingService
from core import schemas
from datetime import datetime

class TestAccountingService:
    @pytest.fixture
    def service(self, mock_repo, mock_event_bus):
        # Patching internal method to prevent repo calls during init
        with patch.object(AccountingService, '_ensure_default_accounts_exist'):
            return AccountingService(mock_repo, mock_event_bus)

    def test_handle_new_invoice_creates_journal_entry(self, service, mock_repo, sample_invoice_data):
        # Setup
        mock_repo.get_account_by_code.return_value = schemas.Account(
            name="Test Account", 
            code="112100", 
            type=schemas.AccountType.ASSET,
            _mongo_id="acc_123"
        )
        # Mock Repo create_journal_entry
        mock_repo.create_journal_entry.return_value = True
        
        # Action
        data = {"invoice": sample_invoice_data}
        service.handle_new_invoice(data)
        
        # Assert
        mock_repo.create_journal_entry.assert_called_once()
        # Verify the call arguments to ensure correct accounting logic (Debit AR, Credit Revenue)
        call_args = mock_repo.create_journal_entry.call_args[0][0]
        assert isinstance(call_args, schemas.JournalEntry)
        assert call_args.description == f"فاتورة مبيعات: {sample_invoice_data.invoice_number}"
        assert len(call_args.lines) == 2
        
        # Check Debit Line (AR)
        assert call_args.lines[0].debit == sample_invoice_data.total_amount
        assert call_args.lines[0].credit == 0.0
        
        # Check Credit Line (Revenue)
        assert call_args.lines[1].debit == 0.0
        assert call_args.lines[1].credit == sample_invoice_data.total_amount

    def test_initialization_subscribes_to_events(self, mock_repo, mock_event_bus):
        # Setup & Action
        with patch.object(AccountingService, '_ensure_default_accounts_exist'):
            service = AccountingService(mock_repo, mock_event_bus)
        
        # Assert
        mock_event_bus.subscribe.assert_any_call('INVOICE_CREATED', service.handle_new_invoice)
        mock_event_bus.subscribe.assert_any_call('PAYMENT_RECEIVED', service.handle_new_payment)
