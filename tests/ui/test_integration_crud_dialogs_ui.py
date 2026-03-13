from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QScrollArea

from core import schemas
from core.event_bus import EventBus
from services.client_service import ClientService
from services.expense_service import ExpenseService
from services.project_service import ProjectService
from ui.client_editor_dialog import ClientEditorDialog
from ui.expense_editor_dialog import ExpenseEditorDialog
from ui.payments_manager import NewPaymentDialog, PaymentEditorDialog, PaymentsManagerTab


class _AccountingStub:
    def __init__(self, repo):
        self.repo = repo

    def _schedule_cash_recalc(self):
        return None


class _ProjectServiceStub:
    def __init__(self, projects=None):
        self._projects = list(projects or [])

    def get_all_projects(self):
        return list(self._projects)


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
    dialog.account_combo.setCurrentIndex(1)
    dialog.amount_input.setValue(123.45)

    QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert dialog.result() == dialog.DialogCode.Accepted
    expenses = sqlite_repo.get_all_expenses()
    assert any(abs(e.amount - 123.45) < 0.001 for e in expenses)


def test_expense_dialog_uses_stable_project_reference_for_duplicate_names(qapp, sqlite_repo):
    _seed_cash_account(sqlite_repo)

    client_a = sqlite_repo.create_client(schemas.Client(name="Expense Client A"))
    client_b = sqlite_repo.create_client(schemas.Client(name="Expense Client B"))
    project_a = sqlite_repo.create_project(
        schemas.Project(
            name="Expense Shared Project", client_id=str(client_a.id), total_amount=1000.0
        )
    )
    project_b = sqlite_repo.create_project(
        schemas.Project(
            name="Expense Shared Project", client_id=str(client_b.id), total_amount=1500.0
        )
    )

    bus = EventBus()
    expense_service = ExpenseService(sqlite_repo, bus)
    accounting_service = _AccountingStub(sqlite_repo)
    dialog = ExpenseEditorDialog(
        expense_service=expense_service,
        accounting_service=accounting_service,
        project_service=_ProjectServiceStub([project_a, project_b]),
        expense_to_edit=None,
        pre_selected_project_id=str(project_b.id),
        pre_selected_project_name=project_b.name,
    )
    dialog.show()
    qapp.processEvents()

    dialog.category_combo.setCurrentText("مصروفات متنوعة")
    dialog.account_combo.setCurrentIndex(1)
    dialog.amount_input.setValue(75.0)
    qapp.processEvents()

    QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert dialog.result() == dialog.DialogCode.Accepted
    expenses = sqlite_repo.get_all_expenses()
    assert any(abs(e.amount - 75.0) < 0.001 and e.project_id == str(project_b.id) for e in expenses)
    assert sqlite_repo.get_total_expenses_for_project(str(project_a.id)) == 0.0
    assert sqlite_repo.get_total_expenses_for_project(str(project_b.id)) == 75.0


def test_expense_dialog_requires_explicit_account_selection(monkeypatch, qapp, sqlite_repo):
    _seed_cash_account(sqlite_repo)

    bus = EventBus()
    expense_service = ExpenseService(sqlite_repo, bus)
    accounting_service = _AccountingStub(sqlite_repo)
    dialog = ExpenseEditorDialog(
        expense_service=expense_service,
        accounting_service=accounting_service,
        project_service=_ProjectServiceStub(),
        expense_to_edit=None,
    )
    dialog.show()
    qapp.processEvents()

    messages: list[str] = []
    monkeypatch.setattr(
        "ui.expense_editor_dialog.QMessageBox.warning",
        lambda *_args, **kwargs: messages.append(str(kwargs.get("text") or _args[2])),
        raising=False,
    )

    dialog.category_combo.setCurrentIndex(0)
    dialog.amount_input.setValue(25.0)
    qapp.processEvents()

    QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert dialog.result() != dialog.DialogCode.Accepted
    assert messages
    assert any("اختيار حساب الدفع" in message for message in messages)
    assert sqlite_repo.get_all_expenses() == []


def test_expense_dialog_loads_existing_stable_project_reference(qapp, sqlite_repo):
    _seed_cash_account(sqlite_repo)

    client_a = sqlite_repo.create_client(schemas.Client(name="Expense Edit Client A"))
    client_b = sqlite_repo.create_client(schemas.Client(name="Expense Edit Client B"))
    project_a = sqlite_repo.create_project(
        schemas.Project(name="Expense Edit Project", client_id=str(client_a.id), total_amount=400.0)
    )
    project_b = sqlite_repo.create_project(
        schemas.Project(name="Expense Edit Project", client_id=str(client_b.id), total_amount=800.0)
    )
    stored_expense = sqlite_repo.create_expense(
        schemas.Expense(
            date=datetime(2026, 3, 2, 11, 0, 0),
            category="إيجار",
            amount=210.0,
            description="existing expense",
            account_id="111101",
            payment_account_id="111101",
            project_id=str(project_b.id),
        )
    )

    bus = EventBus()
    expense_service = ExpenseService(sqlite_repo, bus)
    accounting_service = _AccountingStub(sqlite_repo)
    dialog = ExpenseEditorDialog(
        expense_service=expense_service,
        accounting_service=accounting_service,
        project_service=_ProjectServiceStub([project_a, project_b]),
        expense_to_edit=stored_expense,
    )
    dialog.show()
    qapp.processEvents()

    selected_project = dialog.project_combo.currentData()
    assert selected_project is not None
    assert str(selected_project.id) == str(project_b.id)
    assert dialog.project_combo.currentText() == project_b.name


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

    assert not dialog.findChildren(QScrollArea)
    assert dialog.save_btn.height() <= 34
    assert dialog.cancel_btn.height() <= 34

    dialog.project_combo.setCurrentIndex(1)
    dialog.account_combo.setCurrentIndex(1)
    dialog.amount_input.setValue(200.0)
    qapp.processEvents()

    assert dialog.save_btn.isEnabled()
    QTest.mouseClick(dialog.save_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert dialog.result() == dialog.DialogCode.Accepted
    payments = sqlite_repo.get_all_payments()
    assert any(
        abs(p.amount - 200.0) < 0.001 and p.project_id == str(created_project.id) for p in payments
    )


def test_payment_editor_reassigns_payment_to_selected_project_and_invoice(
    monkeypatch, qapp, sqlite_repo
):
    _seed_cash_account(sqlite_repo)

    bus = EventBus()
    accounting_service = _AccountingStub(sqlite_repo)
    client_service = ClientService(sqlite_repo)

    monkeypatch.setattr("services.project_service.PRINTING_AVAILABLE", False, raising=False)
    monkeypatch.setattr(
        "ui.payments_manager.QMessageBox.information",
        lambda *args, **kwargs: None,
        raising=False,
    )
    monkeypatch.setattr(
        "ui.payments_manager.QMessageBox.warning",
        lambda *args, **kwargs: None,
        raising=False,
    )
    monkeypatch.setattr(
        "ui.payments_manager.QMessageBox.critical",
        lambda *args, **kwargs: None,
        raising=False,
    )

    project_service = ProjectService(
        repository=sqlite_repo,
        event_bus=bus,
        accounting_service=accounting_service,
        settings_service=None,
    )

    client_a = client_service.create_client(schemas.Client(name="Payment Edit Client A"))
    client_b = client_service.create_client(schemas.Client(name="Payment Edit Client B"))
    project_a = sqlite_repo.create_project(
        schemas.Project(
            name="Payment Edit Project A", client_id=str(client_a.id), total_amount=1000.0
        )
    )
    project_b = sqlite_repo.create_project(
        schemas.Project(
            name="Payment Edit Project B", client_id=str(client_b.id), total_amount=1200.0
        )
    )
    payment = sqlite_repo.create_payment(
        schemas.Payment(
            project_id=str(project_a.id),
            client_id=str(client_a.id),
            date=datetime(2026, 3, 8, 11, 0, 0),
            amount=175.0,
            account_id="111101",
            method="Cash",
        )
    )

    dialog = PaymentEditorDialog(
        payment=payment,
        accounts=sqlite_repo.get_all_accounts(),
        accounting_service=accounting_service,
        project_service=project_service,
    )
    dialog.show()
    qapp.processEvents()

    QTest.mouseClick(dialog.change_project_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    target_index = next(
        index
        for index in range(dialog.project_combo.count())
        if "Payment Edit Project B" in dialog.project_combo.itemText(index)
    )
    dialog.project_combo.setCurrentIndex(target_index)
    qapp.processEvents()

    QTest.mouseClick(dialog.save_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    refreshed = sqlite_repo.get_payment_by_id(payment.id)
    assert dialog.result() == dialog.DialogCode.Accepted
    assert refreshed is not None
    assert refreshed.project_id == str(project_b.id)
    assert refreshed.client_id == str(client_b.id)
    assert refreshed.invoice_number == project_b.invoice_number


def test_payment_editor_dialog_uses_fixed_layout_and_toggleable_project_search(
    monkeypatch, qapp, sqlite_repo
):
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

    client = client_service.create_client(schemas.Client(name="Payment Layout Client"))
    project = sqlite_repo.create_project(
        schemas.Project(
            name="Payment Layout Project",
            client_id=str(client.id),
            total_amount=800.0,
        )
    )
    payment = sqlite_repo.create_payment(
        schemas.Payment(
            project_id=str(project.id),
            client_id=str(client.id),
            date=datetime(2026, 3, 8, 9, 0, 0),
            amount=125.0,
            account_id="111101",
            method="Cash",
            invoice_number=project.invoice_number,
        )
    )

    dialog = PaymentEditorDialog(
        payment=payment,
        accounts=sqlite_repo.get_all_accounts(),
        accounting_service=accounting_service,
        project_service=project_service,
    )
    dialog.show()
    qapp.processEvents()

    assert not dialog.findChildren(QScrollArea)
    assert dialog.save_btn.height() <= 34
    assert dialog.cancel_btn.height() <= 34
    assert dialog.save_btn.text() == "حفظ الدفعة"
    assert not dialog.project_picker_frame.isVisible()
    assert dialog.project_combo.count() == 0
    assert dialog.project_meta_label.text() == client.name
    assert dialog.project_invoice_label.text() == project.invoice_number
    assert dialog.project_total_value_label.text() != ""
    collapsed_height = dialog.height()

    QTest.mouseClick(dialog.change_project_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    QTest.qWait(10)

    assert dialog.project_picker_frame.isVisible()
    assert "إخفاء" in dialog.change_project_btn.text()
    assert dialog.project_combo.count() > 0
    expanded_height = dialog.height()
    assert expanded_height >= collapsed_height

    project_line_edit = dialog.project_combo.lineEdit()
    assert project_line_edit is not None
    project_line_edit.setText("Payment Edit")
    dialog.project_combo._on_text_edited("Payment Edit")
    dialog.project_combo._show_popup_safe()
    qapp.processEvents()
    QTest.qWait(5)

    QTest.mouseClick(dialog.change_project_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    QTest.qWait(10)

    assert not dialog.project_picker_frame.isVisible()
    assert "تغيير" in dialog.change_project_btn.text()
    assert dialog.height() <= expanded_height
    assert dialog.height() <= collapsed_height + 2

    for _ in range(3):
        QTest.mouseClick(dialog.change_project_btn, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        QTest.qWait(5)
        QTest.mouseClick(dialog.change_project_btn, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        QTest.qWait(5)

    QTest.mouseClick(dialog.change_project_btn, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    QTest.qWait(5)
    project_line_edit.setText("Project")
    dialog.project_combo._on_text_edited("Project")
    dialog.project_combo._show_popup_safe()
    qapp.processEvents()
    QTest.qWait(5)

    dialog.close()
    qapp.processEvents()
    QTest.qWait(20)


def test_payments_manager_renders_invoice_number_column(qapp, sqlite_repo):
    _seed_cash_account(sqlite_repo)

    accounting_service = _AccountingStub(sqlite_repo)
    client_service = ClientService(sqlite_repo)
    bus = EventBus()
    project_service = ProjectService(
        repository=sqlite_repo,
        event_bus=bus,
        accounting_service=accounting_service,
        settings_service=None,
    )

    client = client_service.create_client(schemas.Client(name="Payment Table Client"))
    project = sqlite_repo.create_project(
        schemas.Project(name="Payment Table Project", client_id=str(client.id), total_amount=900.0)
    )
    payment = sqlite_repo.create_payment(
        schemas.Payment(
            project_id=str(project.id),
            client_id=str(client.id),
            date=datetime(2026, 3, 8, 12, 0, 0),
            amount=220.0,
            account_id="111101",
            method="Cash",
        )
    )

    tab = PaymentsManagerTab(
        project_service=project_service,
        accounting_service=accounting_service,
        client_service=client_service,
    )
    try:
        tab._page_accounts_cache = {"111101": sqlite_repo.get_account_by_code("111101")}
        tab._page_projects_cache = {
            str(project.id): project,
            project.invoice_number: project,
        }
        tab._page_clients_cache = {str(client.id): client}
        tab._populate_payments_table([payment], 0)

        assert tab.payments_table.columnCount() == 8
        assert tab.payments_table.horizontalHeaderItem(4).text() == "رقم الفاتورة"
        assert tab.payments_table.item(0, 4).text() == project.invoice_number
    finally:
        tab.close()
