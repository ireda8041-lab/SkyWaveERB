
import pytest
from unittest.mock import MagicMock
from core.repository import Repository
from core.event_bus import EventBus
from core import schemas

@pytest.fixture
def mock_repo():
    """Mock Repository for testing services"""
    repo = MagicMock(spec=Repository)
    return repo

@pytest.fixture
def mock_event_bus():
    """Mock EventBus for testing services"""
    bus = MagicMock(spec=EventBus)
    return bus

@pytest.fixture
def sample_client_data():
    return schemas.Client(
        name="Test Client",
        email="test@example.com",
        phone="01000000000",
        country="Egypt"
    )

@pytest.fixture
def sample_invoice_data():
    return schemas.Invoice(
        invoice_number="INV-001",
        client_id="client_123",
        issue_date="2024-01-01T10:00:00",
        due_date="2024-01-15T10:00:00",
        items=[
            schemas.InvoiceItem(
                service_id="serv_1",
                description="Test Service",
                quantity=1,
                unit_price=1000,
                total=1000
            )
        ],
        subtotal=1000,
        total_amount=1000,
        status=schemas.InvoiceStatus.SENT,
        currency=schemas.CurrencyCode.EGP
    )
