from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from core import schemas
from ui.project_manager import ProjectManagerTab


def test_preview_expense_dedupe_keeps_distinct_account_rows(qapp):
    tab = ProjectManagerTab.__new__(ProjectManagerTab)
    expenses = [
        schemas.Expense(
            project_id="Preview Project",
            date=datetime(2026, 2, 26, 10, 0, 0),
            category="Media",
            amount=250.0,
            description="same payload",
            account_id="5001",
            payment_account_id="1101",
        ),
        schemas.Expense(
            project_id="Preview Project",
            date=datetime(2026, 2, 26, 10, 0, 0),
            category="Media",
            amount=250.0,
            description="same payload",
            account_id="5002",
            payment_account_id="1102",
        ),
    ]

    deduped = tab._dedupe_preview_expenses(expenses)

    assert len(deduped) == 2


def test_project_identity_cache_key_distinguishes_duplicate_names(qapp):
    tab = ProjectManagerTab.__new__(ProjectManagerTab)
    first = schemas.Project(id=1, name="Shared Name", client_id="CLIENT-1", total_amount=100.0)
    second = schemas.Project(id=2, name="Shared Name", client_id="CLIENT-2", total_amount=100.0)

    assert tab._project_identity(first) != tab._project_identity(second)


def test_preview_invoice_template_uses_selected_project_identity_for_payments(qapp, monkeypatch):
    tab = ProjectManagerTab.__new__(ProjectManagerTab)
    project = schemas.Project(
        id=7, name="Shared Invoice Preview", client_id="CLIENT-7", total_amount=900.0
    )
    client = schemas.Client(
        name="Preview Client", phone="0100", email="c@example.com", address="Cairo"
    )
    client.id = 7

    captured: dict[str, object] = {}

    tab.selected_project = project
    tab.client_service = type(
        "_ClientService",
        (),
        {
            "get_client_by_id": staticmethod(
                lambda client_id: client if client_id == project.client_id else None
            )
        },
    )()
    tab.template_service = type(
        "_TemplateService",
        (),
        {
            "templates_dir": "templates",
            "generate_invoice_html": staticmethod(
                lambda *, project, client_info, payments: captured.update(
                    {"project": project, "client_info": client_info, "payments": payments}
                )
                or "<html></html>"
            ),
            "get_exports_dir": staticmethod(lambda: "exports"),
            "build_export_basename": staticmethod(lambda project, client_info: "preview-file"),
        },
    )()
    tab._get_payments_list = MagicMock(return_value=[{"amount": 250.0, "date": "2026-03-01"}])

    created_dialogs: list[dict[str, object]] = []

    class _PreviewDialog:
        def __init__(self, **kwargs):
            created_dialogs.append(kwargs)

        def exec(self):
            return None

    monkeypatch.setattr("ui.project_manager.InvoicePreviewDialog", _PreviewDialog)
    monkeypatch.setattr("ui.project_manager.QMessageBox.warning", lambda *args, **kwargs: None)

    tab.preview_invoice_template()

    tab._get_payments_list.assert_called_once_with(project)
    assert captured["project"] is project
    assert captured["payments"] == [{"amount": 250.0, "date": "2026-03-01"}]
    assert created_dialogs


def test_context_menu_print_invoice_delegates_to_full_print_flow(qapp, monkeypatch):
    tab = ProjectManagerTab.__new__(ProjectManagerTab)
    project = schemas.Project(
        id=12, name="Context Menu Project", client_id="CLIENT-12", total_amount=400.0
    )
    tab.selected_project = None
    tab.projects_table = type(
        "_Table",
        (),
        {
            "selectedIndexes": staticmethod(
                lambda: [type("_Index", (), {"row": staticmethod(lambda: 0)})()]
            )
        },
    )()
    tab._project_from_row = lambda row: project
    tab.printing_service = None
    captured: list[schemas.Project] = []
    tab.print_invoice = lambda: captured.append(tab.selected_project)

    tab._print_invoice()

    assert tab.selected_project is project
    assert captured == [project]


def test_print_invoice_fallback_uses_repository_invoice_number(qapp, monkeypatch):
    tab = ProjectManagerTab.__new__(ProjectManagerTab)
    project = schemas.Project(
        id=15, name="Fallback Print Project", client_id="CLIENT-15", total_amount=800.0
    )
    client = schemas.Client(
        name="Fallback Client", phone="010", email="fallback@example.com", address="Cairo"
    )
    client.id = 15

    class _Repo:
        def __init__(self):
            self.calls: list[tuple[str, str | None]] = []

        def ensure_invoice_number(self, project_ref, client_id=None):
            self.calls.append((str(project_ref), client_id))
            return "SW-55555"

    repo = _Repo()
    tab.selected_project = project
    tab.project_service = type(
        "_ProjectService",
        (),
        {
            "repo": repo,
            "get_project_profitability": staticmethod(
                lambda project_ref, client_id=None: {"total_paid": 200.0, "balance_due": 600.0}
            ),
        },
    )()
    tab.client_service = type(
        "_ClientService",
        (),
        {
            "get_client_by_id": staticmethod(
                lambda client_id: client if client_id == project.client_id else None
            )
        },
    )()
    tab.service_service = None
    tab.template_service = None
    tab._get_payments_list = lambda project_obj: [{"amount": 200.0, "date": "2026-03-01"}]

    captured: dict[str, object] = {}

    class _InvoicePrintingService:
        def __init__(self, settings_service=None):
            captured["settings_service"] = settings_service

        def print_invoice(self, invoice_data):
            captured["invoice_data"] = invoice_data
            return "fallback.pdf"

    monkeypatch.setattr("ui.project_manager.InvoicePrintingService", _InvoicePrintingService)
    monkeypatch.setattr("ui.project_manager.QMessageBox.information", lambda *args, **kwargs: None)
    monkeypatch.setattr("ui.project_manager.QMessageBox.warning", lambda *args, **kwargs: None)
    monkeypatch.setattr("ui.project_manager.QMessageBox.critical", lambda *args, **kwargs: None)

    tab.print_invoice()

    assert repo.calls == [("15", "CLIENT-15")]
    assert project.invoice_number == "SW-55555"
    assert captured["invoice_data"]["invoice_number"] == "SW-55555"
