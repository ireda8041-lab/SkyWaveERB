from __future__ import annotations

from datetime import datetime

import services.export_service as export_module
from core import schemas
from services.export_service import ExportService


class _RepoStub:
    def __init__(self):
        self.clients = {"CLIENT-1": schemas.Client(name="Export Client")}
        self.projects = {
            "77": schemas.Project(
                id=77,
                name="Export Project",
                client_id="CLIENT-1",
                total_amount=1200.0,
            )
        }

    def get_client_by_id(self, client_id: str):
        return self.clients.get(client_id)

    def get_project_by_number(self, project_ref: str, client_id: str | None = None):
        return self.projects.get(str(project_ref))


def test_export_projects_to_excel_uses_client_name(monkeypatch):
    repo = _RepoStub()
    service = ExportService(repository=repo)
    project = repo.projects["77"]
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        service,
        "export_to_excel",
        lambda data, filename, sheet_name: captured.update(
            {"data": data, "filename": filename, "sheet_name": sheet_name}
        )
        or "projects_export.xlsx",
    )

    result = service.export_projects_to_excel([project])

    assert result == "projects_export.xlsx"
    assert captured["data"] == [
        {
            "اسم المشروع": "Export Project",
            "العميل": "Export Client",
            "الحالة": project.status.value,
            "تاريخ البدء": "",
            "تاريخ الانتهاء": "",
            "المبلغ الإجمالي": 1200.0,
            "العملة": project.currency.value,
            "الوصف": "",
        }
    ]


def test_export_expenses_to_excel_uses_project_name(monkeypatch):
    repo = _RepoStub()
    service = ExportService(repository=repo)
    expense = schemas.Expense(
        project_id="77",
        date=datetime(2026, 3, 1, 10, 0, 0),
        category="Operations",
        amount=150.0,
        description="Exported expense",
        account_id="5001",
        payment_account_id="1101",
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        service,
        "export_to_excel",
        lambda data, filename, sheet_name: captured.update(
            {"data": data, "filename": filename, "sheet_name": sheet_name}
        )
        or "expenses_export.xlsx",
    )

    result = service.export_expenses_to_excel([expense])

    assert result == "expenses_export.xlsx"
    assert captured["data"] == [
        {
            "التاريخ": "2026-03-01",
            "الفئة": "Operations",
            "المبلغ": 150.0,
            "الوصف": "Exported expense",
            "المشروع": "Export Project",
            "حساب المصروف": "5001",
            "حساب الدفع": "1101",
        }
    ]


def test_export_service_falls_back_to_raw_references_and_logs(monkeypatch):
    class _BrokenRepo:
        def get_client_by_id(self, _client_id: str):
            raise RuntimeError("client lookup failed")

        def get_project_by_number(self, _project_ref: str, client_id: str | None = None):
            raise RuntimeError("project lookup failed")

    logs: list[str] = []
    monkeypatch.setattr(
        export_module, "safe_print", lambda msg: logs.append(str(msg)), raising=True
    )

    service = ExportService(repository=_BrokenRepo())

    assert service._resolve_client_display_name("CLIENT-X") == "CLIENT-X"
    assert service._resolve_project_display_name("PROJ-X") == "PROJ-X"
    assert any("CLIENT-X" in message for message in logs)
    assert any("PROJ-X" in message for message in logs)
