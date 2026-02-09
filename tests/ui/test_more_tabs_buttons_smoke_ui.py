from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest


class _NoopService:
    def __init__(self):
        self.repo = object()

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            _ = (args, kwargs)
            return None

        return _noop


def test_projects_tab_buttons_click_without_crash(monkeypatch, qapp):
    from ui import project_manager

    monkeypatch.setattr(
        project_manager.ProjectManagerTab, "open_editor", lambda *args, **kwargs: None, raising=True
    )
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "open_editor_for_selected",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "open_payment_dialog",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "open_profit_dialog",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "print_invoice",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "preview_invoice_template",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "delete_selected_project",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "load_projects_data",
        lambda *args, **kwargs: None,
        raising=True,
    )

    tab = project_manager.ProjectManagerTab(
        project_service=_NoopService(),
        client_service=_NoopService(),
        service_service=_NoopService(),
        accounting_service=_NoopService(),
        expense_service=_NoopService(),
        printing_service=None,
        template_service=None,
    )
    tab.show()
    qapp.processEvents()

    for btn_name in (
        "edit_button",
        "delete_button",
        "payment_button",
        "profit_button",
        "print_button",
        "preview_template_button",
    ):
        getattr(tab, btn_name).setEnabled(True)

    QTest.mouseClick(tab.add_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.edit_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.delete_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.payment_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.profit_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.print_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.preview_template_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.refresh_button, Qt.MouseButton.LeftButton)


def test_projects_tab_splitter_orientation_is_responsive(qapp):
    from ui import project_manager

    tab = project_manager.ProjectManagerTab(
        project_service=_NoopService(),
        client_service=_NoopService(),
        service_service=_NoopService(),
        accounting_service=_NoopService(),
        expense_service=_NoopService(),
        printing_service=None,
        template_service=None,
    )
    tab.show()

    tab.resize(960, 700)
    qapp.processEvents()
    assert tab.main_splitter.orientation() == Qt.Orientation.Vertical

    tab.resize(1400, 900)
    qapp.processEvents()
    assert tab.main_splitter.orientation() == Qt.Orientation.Horizontal


def test_payments_tab_buttons_click_without_crash(monkeypatch, qapp):
    from ui import payments_manager

    monkeypatch.setattr(
        payments_manager.PaymentsManagerTab,
        "open_add_dialog",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        payments_manager.PaymentsManagerTab,
        "open_edit_dialog",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        payments_manager.PaymentsManagerTab,
        "delete_selected_payment",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        payments_manager.PaymentsManagerTab,
        "load_payments_data",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        payments_manager.PaymentsManagerTab,
        "_setup_context_menu",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        payments_manager.PaymentsManagerTab,
        "apply_permissions",
        lambda *args, **kwargs: None,
        raising=True,
    )

    tab = payments_manager.PaymentsManagerTab(
        project_service=_NoopService(),
        accounting_service=_NoopService(),
        client_service=_NoopService(),
        current_user=None,
    )
    tab.show()
    qapp.processEvents()

    QTest.mouseClick(tab.add_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.edit_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.delete_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.refresh_button, Qt.MouseButton.LeftButton)


def test_expenses_tab_buttons_click_without_crash(monkeypatch, qapp):
    from ui import expense_manager

    monkeypatch.setattr(
        expense_manager.ExpenseManagerTab,
        "open_add_dialog",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        expense_manager.ExpenseManagerTab,
        "open_edit_dialog",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        expense_manager.ExpenseManagerTab,
        "delete_selected_expense",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        expense_manager.ExpenseManagerTab,
        "load_expenses_data",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        expense_manager.ExpenseManagerTab,
        "_setup_context_menu",
        lambda *args, **kwargs: None,
        raising=True,
    )

    tab = expense_manager.ExpenseManagerTab(
        expense_service=_NoopService(),
        accounting_service=_NoopService(),
        project_service=_NoopService(),
    )
    tab.show()
    qapp.processEvents()

    QTest.mouseClick(tab.add_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.edit_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.delete_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.refresh_button, Qt.MouseButton.LeftButton)


def test_accounting_tab_buttons_click_without_crash(monkeypatch, qapp):
    from ui import accounting_manager

    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "open_account_editor",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "open_account_editor_for_selected",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "delete_selected_account",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "load_accounts_data",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "_connect_realtime_signals",
        lambda *a, **k: None,
        raising=True,
    )

    tab = accounting_manager.AccountingManagerTab(
        expense_service=_NoopService(),
        accounting_service=_NoopService(),
        project_service=_NoopService(),
    )
    tab.show()
    qapp.processEvents()

    QTest.mouseClick(tab.add_account_btn, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.edit_account_btn, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.delete_account_btn, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.refresh_btn, Qt.MouseButton.LeftButton)
