from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from core import schemas
from core.event_bus import EventBus
from services.client_service import ClientService
from services.expense_service import ExpenseService
from services.project_service import ProjectService
from ui.client_editor_dialog import ClientEditorDialog
from ui.expense_editor_dialog import ExpenseEditorDialog
from ui.payments_manager import NewPaymentDialog


class _AccountingStub:
    def __init__(self, repo):
        self.repo = repo


def _seed_cash_account(repo) -> None:
    repo.create_account(
        schemas.Account(
            name="خزينة",
            code="111101",
            type=schemas.AccountType.CASH,
            balance=0.0,
            currency=schemas.CurrencyCode.EGP,
            description="حساب خزينة للاختبارات",
        )
    )


def test_client_dialog_creates_client_in_sqlite(qapp, sqlite_repo):
    client_service = ClientService(sqlite_repo)

    dialog = ClientEditorDialog(client_service=client_service)
    dialog.show()
    qapp.processEvents()

    dialog.name_input.setText("عميل اختبار")
    QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert dialog.result() == dialog.DialogCode.Accepted
    assert sqlite_repo.get_client_by_name("عميل اختبار") is not None


def test_expense_dialog_creates_expense_in_sqlite(monkeypatch, qapp, sqlite_repo):
    _seed_cash_account(sqlite_repo)

    bus = EventBus()
    expense_service = ExpenseService(sqlite_repo, bus)

    class _ProjectServiceStub:
        def get_all_projects(self):
            return []

    accounting_service = _AccountingStub(sqlite_repo)
    dialog = ExpenseEditorDialog(
        expense_service=expense_service,
        accounting_service=accounting_service,
        project_service=_ProjectServiceStub(),
        expense_to_edit=None,
    )
    dialog.show()
    qapp.processEvents()

    dialog.category_combo.setCurrentIndex(0)
    dialog.account_combo.setCurrentIndex(0)
    dialog.amount_input.setValue(123.45)

    QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert dialog.result() == dialog.DialogCode.Accepted
    expenses = sqlite_repo.get_all_expenses()
    assert any(abs(e.amount - 123.45) < 0.001 for e in expenses)


def test_payment_dialog_creates_payment_in_sqlite(monkeypatch, qapp, sqlite_repo):
    _seed_cash_account(sqlite_repo)

    bus = EventBus()
    accounting_service = _AccountingStub(sqlite_repo)
    client_service = ClientService(sqlite_repo)

    monkeypatch.setattr("services.project_service.PRINTING_AVAILABLE", False, raising=False)

    project_service = ProjectService(
        repository=sqlite_repo,
        event_bus=bus,
        accounting_service=accounting_service,
        settings_service=None,
    )

    created_client = client_service.create_client(schemas.Client(name="Client P"))
    created_project = project_service.create_project(
        project_data={"name": "PRJ-PAY-1", "client_id": str(created_client.id), "items": []},
        payment_data={"amount": 0, "date": datetime.now(), "account_id": "111101"},
    )
    assert created_project is not None

    dialog = NewPaymentDialog(
        project_service=project_service,
        accounting_service=accounting_service,
        client_service=client_service,
    )
    dialog.show()
    qapp.processEvents()

    dialog.project_combo.setCurrentIndex(0)
    dialog.account_combo.setCurrentIndex(0)
    dialog.amount_input.setValue(200.0)
    qapp.processEvents()

    assert dialog.save_btn.isEnabled()
    QTest.mouseClick(dialog.save_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert dialog.result() == dialog.DialogCode.Accepted
    payments = sqlite_repo.get_all_payments()
    assert any(abs(p.amount - 200.0) < 0.001 and p.project_id == "PRJ-PAY-1" for p in payments)
