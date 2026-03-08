from __future__ import annotations

from services.template_service import TemplateService


class _RepoStub:
    def __init__(self):
        self.calls: list[tuple[str, str | None]] = []

    def ensure_invoice_number(self, project_ref: str, client_id: str | None = None) -> str:
        self.calls.append((project_ref, client_id))
        return "SW-99001"


def test_resolve_project_invoice_number_uses_repository_ensure_and_updates_project():
    service = object.__new__(TemplateService)
    service.repo = _RepoStub()

    project = {
        "id": 41,
        "client_id": "CLIENT-41",
        "name": "Template Invoice Project",
        "invoice_number": "",
    }

    invoice_number = TemplateService._resolve_project_invoice_number(service, project)

    assert invoice_number == "SW-99001"
    assert project["invoice_number"] == "SW-99001"
    assert service.repo.calls == [("41", "CLIENT-41")]


def test_resolve_project_invoice_number_falls_back_to_deterministic_local_id():
    service = object.__new__(TemplateService)
    service.repo = None

    project = {"id": "5", "name": "Fallback Project", "invoice_number": ""}

    invoice_number = TemplateService._resolve_project_invoice_number(service, project)

    assert invoice_number == "SW-97166"
    assert project["invoice_number"] == "SW-97166"
