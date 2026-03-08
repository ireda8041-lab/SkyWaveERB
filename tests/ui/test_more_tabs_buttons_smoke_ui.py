from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMessageBox

from core import schemas


class _NoopService:
    def __init__(self):
        self.repo = object()

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            _ = (args, kwargs)
            return None

        return _noop


class _RecordingProjectService(_NoopService):
    def __init__(self):
        super().__init__()
        self.deleted_refs: list[str] = []

    def delete_project(self, project_ref):
        self.deleted_refs.append(str(project_ref))
        return True


class _LookupProjectService(_NoopService):
    def __init__(self, projects: list[schemas.Project]):
        super().__init__()
        self._projects = projects

    def get_project_by_id(self, project_ref, client_id=None):
        ref_text = str(project_ref or "").strip()
        client_text = str(client_id or "").strip()
        matches = []
        for project in self._projects:
            if client_text and str(getattr(project, "client_id", "") or "") != client_text:
                continue
            if (
                str(getattr(project, "id", "") or "") == ref_text
                or str(getattr(project, "_mongo_id", "") or "") == ref_text
                or str(getattr(project, "name", "") or "") == ref_text
            ):
                matches.append(project)
        return matches[0] if len(matches) == 1 else None


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


def test_projects_tab_splitter_orientation_stays_horizontal(qapp):
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
    assert tab.main_splitter.orientation() == Qt.Orientation.Horizontal


def test_projects_tab_delete_selected_project_uses_project_id(monkeypatch, qapp):
    from ui import project_manager

    project_service = _RecordingProjectService()
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        raising=False,
    )
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "load_projects_data",
        lambda self: None,
        raising=True,
    )

    tab = project_manager.ProjectManagerTab(
        project_service=project_service,
        client_service=_NoopService(),
        service_service=_NoopService(),
        accounting_service=_NoopService(),
        expense_service=_NoopService(),
        printing_service=None,
        template_service=None,
    )
    tab.selected_project = schemas.Project(
        id=77,
        name="Shared Name",
        client_id="CLIENT-77",
        total_amount=5000.0,
    )

    tab.delete_selected_project()
    qapp.processEvents()

    assert project_service.deleted_refs == ["77"]

    tab.resize(1400, 900)
    qapp.processEvents()
    assert tab.main_splitter.orientation() == Qt.Orientation.Horizontal


def test_projects_tab_delete_selected_project_uses_mongo_id_when_local_id_missing(
    monkeypatch, qapp
):
    from ui import project_manager

    project_service = _RecordingProjectService()
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        raising=False,
    )
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "load_projects_data",
        lambda self: None,
        raising=True,
    )

    tab = project_manager.ProjectManagerTab(
        project_service=project_service,
        client_service=_NoopService(),
        service_service=_NoopService(),
        accounting_service=_NoopService(),
        expense_service=_NoopService(),
        printing_service=None,
        template_service=None,
    )
    tab.selected_project = schemas.Project(
        id=None,
        _mongo_id="mongo-project-88",
        name="Shared Name",
        client_id="CLIENT-88",
        total_amount=5000.0,
    )

    tab.delete_selected_project()
    qapp.processEvents()

    assert project_service.deleted_refs == ["mongo-project-88"]


def test_project_editor_save_uses_client_id_and_mongo_project_reference():
    from ui.project_manager import ProjectEditorDialog

    class _ProjectService:
        def __init__(self):
            self.calls: list[tuple[str, dict]] = []

        def update_project(self, project_ref, project_data):
            self.calls.append((str(project_ref), dict(project_data)))
            return None

    class _Combo:
        def __init__(self, data=None, text=""):
            self._data = data
            self._text = text

        def currentData(self):
            return self._data

        def currentText(self):
            return self._text

    class _TextInput:
        def __init__(self, text=""):
            self._text = text

        def text(self):
            return self._text

        def setText(self, value):
            self._text = value

    class _ValueInput:
        def __init__(self, value=0.0):
            self._value = value

        def value(self):
            return self._value

    class _DateInput:
        def __init__(self, value):
            self._value = value

        def dateTime(self):
            return type("_DateTime", (), {"toPyDateTime": lambda _self: self._value})()

    class _PlainText:
        def __init__(self, text=""):
            self._text = text

        def toPlainText(self):
            return self._text

    dialog = ProjectEditorDialog.__new__(ProjectEditorDialog)
    dialog.project_service = _ProjectService()
    dialog.project_to_edit = schemas.Project(
        id=None,
        _mongo_id="mongo-project-19",
        name="Edited Shared Project",
        client_id="old-client-id",
        total_amount=0.0,
    )
    dialog.is_editing = True
    selected_client = schemas.Client(name="Correct Client")
    selected_client.id = 19

    now = datetime(2026, 3, 7, 12, 0, 0)
    dialog.client_combo = _Combo(selected_client, "Correct Client")
    dialog.status_combo = _Combo(schemas.ProjectStatus.ACTIVE)
    dialog.name_input = _TextInput("Edited Shared Project")
    dialog.start_date_input = _DateInput(now)
    dialog.end_date_input = _DateInput(now)
    dialog.project_items = []
    dialog.discount_type_combo = _Combo("percentage")
    dialog.discount_rate_input = _ValueInput(0.0)
    dialog.tax_rate_input = _ValueInput(0.0)
    dialog.notes_input = _PlainText("")
    dialog.payment_amount_input = _ValueInput(0.0)
    dialog.payment_account_combo = _Combo(None)
    dialog.payment_date_input = _DateInput(now)
    dialog.accept = lambda: None

    dialog._save_project_impl(should_close=True)

    assert dialog.project_service.calls
    project_ref, payload = dialog.project_service.calls[0]
    assert project_ref == "mongo-project-19"
    assert payload["client_id"] == "19"


def test_project_editor_ignores_reentrant_save_request():
    from ui.project_manager import ProjectEditorDialog

    class _ProjectService:
        def __init__(self):
            self.called = False

        def update_project(self, project_ref, project_data):
            self.called = True

    dialog = ProjectEditorDialog.__new__(ProjectEditorDialog)
    dialog.project_service = _ProjectService()
    dialog._save_in_progress = True

    dialog._save_project_impl(should_close=True)

    assert dialog.project_service.called is False


def test_projects_table_shows_client_name_not_raw_id(monkeypatch, qapp):
    from ui import project_manager

    class _ClientLookup(_NoopService):
        def get_client_by_id(self, client_id):
            if str(client_id) == "15":
                client = schemas.Client(name="Client Table A")
                client.id = 15
                return client
            return None

    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "load_projects_data",
        lambda self: None,
        raising=True,
    )

    tab = project_manager.ProjectManagerTab(
        project_service=_NoopService(),
        client_service=_ClientLookup(),
        service_service=_NoopService(),
        accounting_service=_NoopService(),
        expense_service=_NoopService(),
        printing_service=None,
        template_service=None,
    )
    project = schemas.Project(
        id=5,
        name="Display Project",
        client_id="15",
        status=schemas.ProjectStatus.ACTIVE,
        total_amount=1000.0,
    )
    tab._populate_projects_table([project])
    qapp.processEvents()

    assert tab.projects_table.item(0, 2).text() == "Client Table A"


def test_projects_tab_selection_uses_row_identity_for_duplicate_names(monkeypatch, qapp):
    from ui import project_manager

    first = schemas.Project(id=11, name="Shared Name", client_id="CLIENT-1", total_amount=1000.0)
    second = schemas.Project(id=22, name="Shared Name", client_id="CLIENT-2", total_amount=1500.0)
    project_service = _LookupProjectService([first, second])
    preview_calls: list[int] = []

    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "load_projects_data",
        lambda self: None,
        raising=True,
    )
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "_load_preview_data_async",
        lambda self, project: preview_calls.append(int(project.id)),
        raising=True,
    )

    tab = project_manager.ProjectManagerTab(
        project_service=project_service,
        client_service=_NoopService(),
        service_service=_NoopService(),
        accounting_service=_NoopService(),
        expense_service=_NoopService(),
        printing_service=None,
        template_service=None,
    )
    tab.projects_list = [first, second]
    tab._current_page_projects = [first, second]
    tab._populate_projects_table([first, second])

    tab.projects_table.selectRow(1)
    tab.on_project_selection_changed()
    qapp.processEvents()

    assert tab.selected_project is not None
    assert tab.selected_project.id == 22
    assert preview_calls == [22]


def test_project_profit_dialog_shows_client_name(monkeypatch, qapp):
    from ui.project_profit_dialog import ProjectProfitDialog

    monkeypatch.setattr(ProjectProfitDialog, "load_profit_data", lambda self: None, raising=True)

    project = schemas.Project(
        id=31,
        name="Profit Project",
        client_id="31",
        total_amount=1000.0,
        status=schemas.ProjectStatus.ACTIVE,
    )
    client = schemas.Client(name="Profit Client")
    client.id = 31
    project_service = type(
        "_ProjectService",
        (),
        {"repo": type("_Repo", (), {"get_client_by_id": staticmethod(lambda client_id: client)})()},
    )()

    dialog = ProjectProfitDialog(project, project_service)
    dialog.show()
    qapp.processEvents()

    assert "Profit Client" in dialog.client_label.text()


def test_projects_tab_add_expense_passes_local_project_id_first(monkeypatch):
    from ui import project_manager

    captured: dict[str, object] = {}

    class _DialogStub:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        def exec(self):
            return project_manager.QDialog.DialogCode.Rejected

    monkeypatch.setattr(project_manager, "ExpenseEditorDialog", _DialogStub, raising=True)

    tab = project_manager.ProjectManagerTab.__new__(project_manager.ProjectManagerTab)
    tab.selected_project = schemas.Project(
        id=77,
        _mongo_id="mongo-77",
        name="Shared Expense Project",
        client_id="CLIENT-77",
        total_amount=2000.0,
    )
    tab.expense_service = _NoopService()
    tab.project_service = _NoopService()
    tab.accounting_service = _NoopService()

    tab._add_expense_for_project()

    assert captured["pre_selected_project_id"] == "77"
    assert captured["pre_selected_project_name"] == "Shared Expense Project"


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
