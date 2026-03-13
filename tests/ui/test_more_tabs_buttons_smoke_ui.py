from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QHeaderView, QLabel, QMessageBox

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
    monkeypatch.setattr(
        project_manager.ProjectManagerTab,
        "_refresh_currency_rates_for_projects",
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

    assert tab.add_button.text() == "➕ إضافة مشروع"
    assert tab.edit_button.text() == "✏️ تعديل المشروع"
    assert tab.payment_button.text() == "💰 تسجيل دفعة"
    assert tab.profit_button.text() == "📊 ربحية المشروع"
    assert tab.print_button.text() == "💾 حفظ الفاتورة"
    assert tab.delete_button.text() == "🗑️ حذف المشروع"
    assert tab.preview_template_button.text() == "📂 فتح الفاتورة"

    assert tab.refresh_currency_rates_button.text() == "🌐 تحديث الأسعار من الإنترنت"

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
    QTest.mouseClick(tab.refresh_currency_rates_button, Qt.MouseButton.LeftButton)


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
    dialog.project_items = [
        schemas.ProjectItem(
            service_id="svc-1",
            description="USD Service",
            quantity=1.0,
            unit_price=100.0,
            total=100.0,
        )
    ]
    dialog._selected_currency_code = "USD"
    dialog._selected_exchange_rate = 50.0
    dialog._load_currencies_catalog = lambda: {
        "USD": {"code": "USD", "rate": 50.0, "symbol": "USD"}
    }
    dialog._resolve_currency_snapshot = lambda code, fallback_rate=None: 50.0
    dialog._current_currency_code = lambda: "USD"
    dialog._current_exchange_rate = lambda: 50.0
    dialog._current_currency_suffix = lambda: "USD"
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
    assert payload["currency"] == "USD"
    assert payload["exchange_rate_snapshot"] == 50.0
    assert payload["items"][0].unit_price == 5000.0
    assert payload["items"][0].total == 5000.0


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


def test_project_editor_reload_payment_methods_does_not_duplicate_items():
    from ui.project_manager import ProjectEditorDialog

    class _SettingsService:
        def get_setting(self, key):
            assert key == "payment_methods"
            return [
                {"name": "Cash", "active": True},
                {"name": "Bank", "active": True},
                {"name": "Cash", "active": True},
                {"name": "Disabled", "active": False},
            ]

    class _Combo:
        def __init__(self):
            self.items: list[tuple[str, object]] = []
            self.current_index = -1
            self.blocked = False

        def blockSignals(self, value):
            self.blocked = bool(value)

        def clear(self):
            self.items.clear()
            self.current_index = -1

        def addItem(self, text, userData=None):
            self.items.append((text, userData))
            if self.current_index == -1:
                self.current_index = 0

        def currentData(self):
            if 0 <= self.current_index < len(self.items):
                return self.items[self.current_index][1]
            return None

        def currentText(self):
            if 0 <= self.current_index < len(self.items):
                return self.items[self.current_index][0]
            return ""

        def count(self):
            return len(self.items)

        def itemData(self, index):
            return self.items[index][1]

        def itemText(self, index):
            return self.items[index][0]

        def setCurrentIndex(self, index):
            self.current_index = index

    dialog = ProjectEditorDialog.__new__(ProjectEditorDialog)
    dialog.settings_service = _SettingsService()
    dialog.payment_method_combo = _Combo()

    dialog._load_payment_methods_for_combo()
    dialog.payment_method_combo.setCurrentIndex(2)
    dialog._load_payment_methods_for_combo()

    assert dialog.payment_method_combo.items == [
        ("تلقائي حسب الحساب", None),
        ("Cash", "Cash"),
        ("Bank", "Bank"),
    ]
    assert dialog.payment_method_combo.currentData() == "Bank"


def test_project_editor_dialog_builds_currency_controls_without_crash(qapp):
    from ui.project_manager import ProjectEditorDialog

    class _ClientService:
        def get_all_clients(self):
            return []

    class _ServiceService:
        settings_service = None

        def get_all_services(self):
            return []

    class _Repo:
        def get_all_accounts(self):
            return []

        def get_all_currencies(self):
            return [
                {
                    "code": "EGP",
                    "name": "جنيه مصري",
                    "symbol": "ج.م",
                    "rate": 1.0,
                    "is_base": True,
                    "active": True,
                },
                {
                    "code": "USD",
                    "name": "دولار أمريكي",
                    "symbol": "USD",
                    "rate": 50.0,
                    "active": True,
                },
            ]

    class _AccountingService:
        def __init__(self):
            self.repo = _Repo()

    dialog = ProjectEditorDialog(
        project_service=_NoopService(),
        client_service=_ClientService(),
        service_service=_ServiceService(),
        accounting_service=_AccountingService(),
        project_to_edit=None,
        parent=None,
    )
    qapp.processEvents()

    assert dialog.currency_label.text() == "العملة:"
    assert dialog.exchange_rate_label.text() == "السعر الفوري:"
    assert dialog.currency_combo.count() == 2
    assert dialog.currency_combo.currentData() == "EGP"
    assert "العملة الأساسية" in dialog.exchange_rate_value_label.text()
    assert dialog.add_item_button.text() == "إضافة بند"
    assert dialog.refresh_currency_rates_button.text() == "🌐 تحديث الأسعار من الإنترنت"

    dialog.close()


def test_project_editor_refresh_currency_rates_updates_snapshot_without_touching_values(
    monkeypatch, qapp
):
    from ui import project_manager
    from ui.project_manager import ProjectEditorDialog

    class _ClientService:
        def get_all_clients(self):
            return []

    class _ServiceService:
        settings_service = None

        def get_all_services(self):
            return []

    class _Repo:
        def __init__(self):
            self.current_rate = 50.0
            self.updated = False

        def get_all_accounts(self):
            return []

        def get_all_currencies(self):
            return [
                {
                    "code": "EGP",
                    "name": "جنيه مصري",
                    "symbol": "ج.م",
                    "rate": 1.0,
                    "is_base": True,
                    "active": True,
                },
                {
                    "code": "USD",
                    "name": "دولار أمريكي",
                    "symbol": "USD",
                    "rate": self.current_rate,
                    "active": True,
                },
            ]

        def update_all_exchange_rates(self):
            self.updated = True
            self.current_rate = 55.5
            return {
                "updated": 1,
                "failed": 0,
                "results": {"USD": {"success": True, "rate": 55.5}},
            }

    class _AccountingService:
        def __init__(self, repo):
            self.repo = repo

    class _ImmediateLoader:
        def load_async(self, load_function, on_success=None, on_error=None, **kwargs):
            _ = kwargs
            try:
                result = load_function()
            except Exception as exc:  # pragma: no cover - defensive
                if on_error:
                    on_error(str(exc))
                return
            if on_success:
                on_success(result)

    repo = _Repo()
    monkeypatch.setattr(
        project_manager, "get_data_loader", lambda: _ImmediateLoader(), raising=True
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None, raising=False)

    dialog = ProjectEditorDialog(
        project_service=_NoopService(),
        client_service=_ClientService(),
        service_service=_ServiceService(),
        accounting_service=_AccountingService(repo),
        project_to_edit=None,
        parent=None,
    )
    dialog.show()
    qapp.processEvents()

    dialog._refresh_currency_combo("USD", 50.0)
    dialog.item_price_input.setValue(100.0)

    dialog._refresh_currency_rates_for_editor()
    qapp.processEvents()

    assert repo.updated is True
    assert dialog._current_currency_code() == "USD"
    assert dialog.item_price_input.value() == 100.0
    assert "55.5000" in dialog.exchange_rate_value_label.text()

    dialog.close()


def test_project_editor_reset_form_restores_default_tax_rate():
    from PyQt6.QtCore import QDate

    from ui.project_manager import ProjectEditorDialog

    class _SettingsService:
        def get_setting(self, key):
            assert key == "default_tax_rate"
            return 14.0

    class _ServiceService:
        def __init__(self):
            self.settings_service = _SettingsService()

    class _LineEdit:
        def __init__(self, text="value"):
            self._text = text

        def clear(self):
            self._text = ""

    class _ComboText:
        def __init__(self):
            self.value = None

        def setCurrentText(self, value):
            self.value = value

    class _ComboIndex:
        def __init__(self):
            self.index = None

        def setCurrentIndex(self, value):
            self.index = value

    class _DateEdit:
        def __init__(self):
            self.value = None

        def setDate(self, value):
            self.value = value

    class _Table:
        def __init__(self):
            self.rows = None

        def setRowCount(self, value):
            self.rows = value

    class _Spin:
        def __init__(self, value=0.0):
            self._value = value

        def value(self):
            return self._value

        def setValue(self, value):
            self._value = value

    title_holder: list[str] = []
    flags = {"notes_reset": False, "totals_updated": False}

    dialog = ProjectEditorDialog.__new__(ProjectEditorDialog)
    dialog.service_service = _ServiceService()
    dialog.project_to_edit = object()
    dialog.is_editing = True
    dialog.project_items = [object()]
    dialog.setWindowTitle = lambda value: title_holder.append(value)
    dialog.name_input = _LineEdit("Project Name")
    dialog.status_combo = _ComboText()
    dialog.start_date_input = _DateEdit()
    dialog.end_date_input = _DateEdit()
    dialog.items_table = _Table()
    dialog.service_combo = _ComboIndex()
    dialog.item_price_input = _Spin(50.0)
    dialog.item_quantity_input = _Spin(2.0)
    dialog.discount_type_combo = _ComboIndex()
    dialog.discount_rate_input = _Spin(10.0)
    dialog.tax_rate_input = _Spin(5.0)
    dialog._reset_notes_template = lambda: flags.__setitem__("notes_reset", True)
    dialog.payment_amount_input = _Spin(99.0)
    dialog.payment_date_input = _DateEdit()
    dialog.payment_account_combo = _ComboIndex()
    dialog.update_totals = lambda: flags.__setitem__("totals_updated", True)

    dialog._reset_form()

    assert dialog.project_to_edit is None
    assert dialog.is_editing is False
    assert dialog.project_items == []
    assert title_holder[-1] == "مشروع جديد"
    assert dialog.name_input._text == ""
    assert dialog.status_combo.value == schemas.ProjectStatus.ACTIVE.value
    assert isinstance(dialog.start_date_input.value, QDate)
    assert isinstance(dialog.end_date_input.value, QDate)
    assert dialog.items_table.rows == 0
    assert dialog.service_combo.index == 0
    assert dialog.item_price_input._value == 0.0
    assert dialog.item_quantity_input._value == 1.0
    assert dialog.discount_type_combo.index == 0
    assert dialog.discount_rate_input._value == 0.0
    assert dialog.tax_rate_input._value == 14.0
    assert flags["notes_reset"] is True
    assert dialog.payment_amount_input._value == 0.0
    assert isinstance(dialog.payment_date_input.value, QDate)
    assert dialog.payment_account_combo.index == 0
    assert flags["totals_updated"] is True


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

    assert tab.add_button.text() == "➕ إضافة مصروف"
    assert tab.edit_button.text() == "✏️ تعديل المصروف"
    assert tab.delete_button.text() == "🗑️ حذف المصروف"

    QTest.mouseClick(tab.add_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.edit_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.delete_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.refresh_button, Qt.MouseButton.LeftButton)


def test_accounting_tab_buttons_click_without_crash(monkeypatch, qapp):
    from core import schemas
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

    assert tab.hero_title_label.text() == "إدارة الخزن"
    assert tab.summary_title_label.text() == "ملخص الخزن"
    assert tab.accounts_panel_title.text() == "قائمة الخزن"
    assert tab.summary_refresh_btn.text() == "🔄 تحديث الملخص"
    assert tab.accounts_count_badge.text() == "0 خزنة"
    assert tab.hero_frame.height() <= 120
    assert tab.hero_badge_label.minimumWidth() >= 158
    assert tab.hero_badge_label.height() >= 24
    assert tab.summary_panel.minimumWidth() >= 348
    assert tab.summary_refresh_btn.minimumWidth() >= 122
    assert tab.accounts_count_badge.minimumWidth() >= 68
    assert tab.assets_label.minimumHeight() >= 84
    assert tab.net_profit_summary_label.minimumHeight() >= 94
    assert tab.add_account_btn.text() == "➕ إضافة خزنة"
    assert tab.edit_account_btn.text() == "✏️ تعديل الخزنة"
    assert tab.delete_account_btn.text() == "⛔ تعطيل الخزنة"

    summary_metric_title = tab.assets_label.findChild(QLabel, "MetricTitleV2")
    assert summary_metric_title is not None
    assert summary_metric_title.width() >= 180
    assert tab.liabilities_label.y() > tab.assets_label.y()
    assert tab.equity_label.y() == tab.liabilities_label.y()
    assert tab.liabilities_label.x() != tab.equity_label.x()

    account = schemas.Account(
        name="خزنة اختبارية",
        code="111000",
        type=schemas.AccountType.CASH,
    )
    tab._render_accounts_tree({"111000": {"obj": account, "total": 100.0, "children": []}})
    qapp.processEvents()
    assert tab.hero_badge_label.text() == "مرتبطة بالتحصيل والصرف"
    assert tab.accounts_model.item(0, 0).textAlignment() == int(
        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
    )
    assert tab.accounts_model.item(0, 6).text() == "جاهزة"
    assert tab.accounts_model.item(0, 0).data(Qt.ItemDataRole.UserRole).balance == 100.0
    assert tab.assets_label.findChild(QLabel, "value_label").text() == "100.00 جنيه"
    assert tab.accounts_tree.indentation() == 0
    assert tab.accounts_tree.header().sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch

    negative_account = schemas.Account(
        name="خزنة مدينة",
        code="111199",
        type=schemas.AccountType.CASH,
    )
    tab._render_accounts_tree(
        {"111199": {"obj": negative_account, "total": -125.5, "children": []}}
    )
    qapp.processEvents()
    assert tab.accounts_model.item(0, 5).text().startswith("-")

    QTest.mouseClick(tab.add_account_btn, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.edit_account_btn, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.delete_account_btn, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.refresh_btn, Qt.MouseButton.LeftButton)


def test_accounting_cashbox_summary_uses_operational_totals():
    from ui import accounting_manager

    first = schemas.Account(
        name="خزنة أولى",
        code="111001",
        type=schemas.AccountType.CASH,
        status=schemas.AccountStatus.ACTIVE,
    )
    second = schemas.Account(
        name="خزنة ثانية",
        code="111002",
        type=schemas.AccountType.CASH,
        status=schemas.AccountStatus.ARCHIVED,
    )

    summary = accounting_manager.AccountingManagerTab._cashbox_summary(
        [
            {
                "account": first,
                "category": "محفظة إلكترونية",
                "inflow": 1500.0,
                "outflow": 300.0,
                "balance": 1200.0,
            },
            {
                "account": second,
                "category": "خزنة نقدية",
                "inflow": 200.0,
                "outflow": 450.0,
                "balance": -250.0,
            },
        ]
    )

    assert summary["total_cashboxes"] == 2
    assert summary["active_cashboxes"] == 1
    assert summary["category_count"] == 2
    assert summary["total_balance"] == 950.0
    assert summary["total_inflow"] == 1700.0
    assert summary["total_outflow"] == 750.0
    assert summary["net_flow"] == 950.0
