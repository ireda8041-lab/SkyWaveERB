from __future__ import annotations

import sys
import types
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from core import schemas
from services.expense_service import ExpenseService
from services.invoice_service import InvoiceService
from services.notification_service import NotificationService
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


def test_notification_service_payment_recorded_reads_nested_payload(mock_repo, mock_event_bus):
    payment = schemas.Payment(
        project_id="PRJ-77",
        client_id="CLIENT-77",
        date=datetime(2026, 2, 28, 11, 0, 0),
        amount=125.0,
        account_id="1101",
        method="Cash",
    )
    payment.id = 77
    project = schemas.Project(
        name="Signal Project",
        client_id="CLIENT-77",
        total_amount=500.0,
    )

    service = NotificationService(mock_repo, mock_event_bus)
    service.create_notification = MagicMock()

    service._on_payment_recorded({"payment": payment, "project": project})

    service.create_notification.assert_called_once_with(
        title="تم تسجيل دفعة جديدة",
        message="تم تسجيل دفعة بمبلغ 125.00 جنيه للمشروع 'Signal Project'",
        type=schemas.NotificationType.SUCCESS,
        priority=schemas.NotificationPriority.MEDIUM,
        related_entity_type="payments",
        related_entity_id="77",
    )


def test_notification_service_payment_recorded_prefers_mongo_reference(mock_repo, mock_event_bus):
    payment = schemas.Payment(
        project_id="PRJ-77",
        client_id="CLIENT-77",
        date=datetime(2026, 2, 28, 11, 0, 0),
        amount=125.0,
        account_id="1101",
        method="Cash",
    )
    payment.id = 77
    payment._mongo_id = "mongo-payment-77"
    project = schemas.Project(
        name="Signal Project",
        client_id="CLIENT-77",
        total_amount=500.0,
    )

    service = NotificationService(mock_repo, mock_event_bus)
    service.create_notification = MagicMock()

    service._on_payment_recorded({"payment": payment, "project": project})

    service.create_notification.assert_called_once_with(
        title="تم تسجيل دفعة جديدة",
        message="تم تسجيل دفعة بمبلغ 125.00 جنيه للمشروع 'Signal Project'",
        type=schemas.NotificationType.SUCCESS,
        priority=schemas.NotificationPriority.MEDIUM,
        related_entity_type="payments",
        related_entity_id="mongo-payment-77",
    )


def test_notification_service_project_created_uses_stable_project_reference(
    mock_repo, mock_event_bus
):
    project = schemas.Project(
        name="Shared Notification Project",
        client_id="CLIENT-88",
        total_amount=900.0,
    )
    project.id = 88
    project._mongo_id = "mongo-project-88"

    service = NotificationService(mock_repo, mock_event_bus)
    service.create_notification = MagicMock()

    service._on_project_created({"project": project})

    service.create_notification.assert_called_once_with(
        title="🚀 مشروع جديد",
        message="تم إنشاء المشروع: Shared Notification Project",
        type=schemas.NotificationType.SUCCESS,
        priority=schemas.NotificationPriority.MEDIUM,
        related_entity_type="project",
        related_entity_id="mongo-project-88",
    )


def test_notification_service_create_notification_shows_local_toast_without_transport_sync(
    mock_repo, mock_event_bus, monkeypatch
):
    captured = {}

    class _FakeUiNotificationType:
        SUCCESS = "success"
        WARNING = "warning"
        ERROR = "error"
        INFO = "info"

    fake_notif_module = types.SimpleNamespace(
        NotificationType=_FakeUiNotificationType,
        NotificationManager=types.SimpleNamespace(
            show=lambda message, notification_type, title=None, duration=None, sync=True, entity_type=None, action=None: captured.update(
                {
                    "kind": notification_type,
                    "message": message,
                    "title": title,
                    "duration": duration,
                    "sync": sync,
                    "entity_type": entity_type,
                    "action": action,
                }
            )
        ),
    )
    monkeypatch.setitem(sys.modules, "ui.notification_system", fake_notif_module)
    monkeypatch.setattr(
        "services.notification_service.QApplication",
        types.SimpleNamespace(instance=lambda: object()),
    )

    service = NotificationService(mock_repo, mock_event_bus)
    saved = schemas.Notification(
        title="Toast title",
        message="Toast body",
        type=schemas.NotificationType.SUCCESS,
        priority=schemas.NotificationPriority.MEDIUM,
        related_entity_type="project",
        related_entity_id="42",
    )
    saved.id = 42
    monkeypatch.setattr(service, "_save_notification", lambda notification: saved)
    monkeypatch.setattr(service, "_emit_notifications_changed", lambda: None)

    created = service.create_notification(
        title="Toast title",
        message="Toast body",
        type=schemas.NotificationType.SUCCESS,
        priority=schemas.NotificationPriority.MEDIUM,
        related_entity_type="project",
        related_entity_id="42",
    )

    assert created == saved
    assert captured["kind"] == "success"
    assert captured["message"] == "Toast body"
    assert captured["title"] == "Toast title"
    assert captured["sync"] is False
    assert captured["entity_type"] == "project"
