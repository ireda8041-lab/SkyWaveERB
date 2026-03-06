from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from core import schemas
from services.expense_service import ExpenseService
from services.invoice_service import InvoiceService
from services.project_service import ProjectService


def _linked_expense(project_id: str = "Project Signals") -> schemas.Expense:
    return schemas.Expense(
        date=datetime(2026, 2, 28, 10, 0, 0),
        category="Operations",
        amount=150.0,
        description="Office expense",
        account_id="5001",
        payment_account_id="1101",
        project_id=project_id,
    )


def _project_invoice(project_id: str = "Project Signals") -> schemas.Invoice:
    return schemas.Invoice(
        invoice_number="INV-SIGNAL-001",
        client_id="CLIENT-1",
        project_id=project_id,
        issue_date=datetime(2026, 2, 28, 10, 0, 0),
        due_date=datetime(2026, 3, 7, 10, 0, 0),
        items=[],
        subtotal=1000.0,
        total_amount=1000.0,
    )


def test_expense_service_create_emits_accounting_and_projects(
    mock_repo, mock_event_bus, monkeypatch
):
    expense = _linked_expense()
    mock_repo.create_expense.return_value = expense
    service = ExpenseService(mock_repo, mock_event_bus)
    seen: list[str] = []
    monkeypatch.setattr(
        "services.expense_service.app_signals.emit_data_changed",
        lambda data_type: seen.append(data_type),
    )

    service.create_expense(expense)

    assert seen == ["expenses", "accounting", "projects"]


def test_expense_service_update_emits_accounting_and_projects(
    mock_repo, mock_event_bus, monkeypatch
):
    existing = _linked_expense(project_id="Old Project")
    updated = _linked_expense(project_id="New Project")
    mock_repo.get_expense_by_id.return_value = existing
    mock_repo.update_expense.return_value = True
    service = ExpenseService(mock_repo, mock_event_bus)
    seen: list[str] = []
    monkeypatch.setattr(
        "services.expense_service.app_signals.emit_data_changed",
        lambda data_type: seen.append(data_type),
    )

    assert service.update_expense("1", updated) is True

    assert seen == ["expenses", "accounting", "projects"]


def test_expense_service_delete_emits_accounting_and_projects(
    mock_repo, mock_event_bus, monkeypatch
):
    expense = _linked_expense()
    mock_repo.get_expense_by_id.return_value = expense
    mock_repo.delete_expense.return_value = True
    service = ExpenseService(mock_repo, mock_event_bus)
    seen: list[str] = []
    monkeypatch.setattr(
        "services.expense_service.app_signals.emit_data_changed",
        lambda data_type: seen.append(data_type),
    )

    assert service.delete_expense("1") is True

    assert seen == ["expenses", "accounting", "projects"]


def test_invoice_service_create_emits_project_refresh(mock_repo, mock_event_bus, monkeypatch):
    invoice = _project_invoice()
    mock_repo.create_invoice.return_value = invoice
    service = InvoiceService(mock_repo, mock_event_bus)
    seen: list[str] = []
    monkeypatch.setattr(
        "services.invoice_service.app_signals.emit_data_changed",
        lambda data_type: seen.append(data_type),
    )

    service.create_invoice(invoice)

    assert seen == ["invoices", "projects"]


def test_invoice_service_update_emits_project_refresh(mock_repo, mock_event_bus, monkeypatch):
    invoice = _project_invoice()
    mock_repo.update_invoice.return_value = invoice
    service = InvoiceService(mock_repo, mock_event_bus)
    seen: list[str] = []
    monkeypatch.setattr(
        "services.invoice_service.app_signals.emit_data_changed",
        lambda data_type: seen.append(data_type),
    )

    updated = service.update_invoice(invoice.invoice_number, invoice)

    assert updated == invoice
    assert seen == ["invoices", "projects"]
    mock_event_bus.publish.assert_any_call("INVOICE_UPDATED", {"invoice": invoice})


def test_invoice_service_void_emits_project_refresh(mock_repo, mock_event_bus, monkeypatch):
    invoice = _project_invoice()
    mock_repo.get_invoice_by_id.return_value = invoice
    mock_repo.update_invoice.return_value = invoice
    service = InvoiceService(mock_repo, mock_event_bus)
    seen: list[str] = []
    monkeypatch.setattr(
        "services.invoice_service.app_signals.emit_data_changed",
        lambda data_type: seen.append(data_type),
    )

    assert service.void_invoice(invoice.invoice_number) is True

    assert seen == ["invoices", "projects"]


def test_project_service_update_stops_when_repository_save_fails(
    mock_repo, mock_event_bus, monkeypatch
):
    old_project = schemas.Project(
        name="Project A",
        client_id="CLIENT-1",
        status=schemas.ProjectStatus.ACTIVE,
        total_amount=1000.0,
        currency=schemas.CurrencyCode.EGP,
    )
    old_project.id = 1

    mock_repo.get_project_by_number.side_effect = [old_project, None]
    mock_repo.update_project.return_value = None

    signal_events: list[str] = []
    notify_mock = MagicMock()
    monkeypatch.setattr(
        "services.project_service.app_signals.emit_data_changed",
        lambda data_type: signal_events.append(data_type),
    )
    monkeypatch.setattr("services.project_service.notify_operation", notify_mock)

    service = ProjectService(mock_repo, mock_event_bus, MagicMock())

    with pytest.raises(ValueError, match="تعذر حفظ تعديلات المشروع"):
        service.update_project(
            "1",
            {
                "name": "Project B",
                "client_id": old_project.client_id,
                "status": old_project.status,
                "items": [],
                "currency": old_project.currency,
            },
        )

    mock_repo.update_project.assert_called_once()
    mock_event_bus.publish.assert_not_called()
    notify_mock.assert_not_called()
    assert signal_events == []
