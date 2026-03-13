from __future__ import annotations

import json
from datetime import datetime

import pytest

from core import schemas
from core.event_bus import EventBus
from services.accounting_service import AccountingService
from services.project_service import ProjectService


@pytest.fixture()
def service_bundle(tmp_path, monkeypatch):
    import core.repository as repo_mod

    db_path = tmp_path / "project_service_duplicate_names.db"
    monkeypatch.setenv("SKYWAVE_DISABLE_MONGO", "1")
    monkeypatch.setattr(repo_mod, "LOCAL_DB_FILE", str(db_path), raising=True)
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_connection", lambda self: None, raising=True
    )
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_retry_loop", lambda self: None, raising=True
    )

    repo = repo_mod.Repository()
    try:
        bus = EventBus()
        accounting = AccountingService(repo, bus)
        service = ProjectService(repo, bus, accounting)
        yield repo, service
    finally:
        repo.close()


def test_duplicate_project_names_keep_payments_profitability_and_status_scoped(service_bundle):
    repo, service = service_bundle

    c1 = repo.create_client(schemas.Client(name="Client A"))
    c2 = repo.create_client(schemas.Client(name="Client B"))
    assert c1.id is not None
    assert c2.id is not None

    p1 = repo.create_project(
        schemas.Project(
            name="Same Name",
            client_id=str(c1.id),
            total_amount=1000.0,
            status=schemas.ProjectStatus.PLANNING,
        )
    )
    p2 = repo.create_project(
        schemas.Project(
            name="Same Name",
            client_id=str(c2.id),
            total_amount=2000.0,
            status=schemas.ProjectStatus.PLANNING,
        )
    )

    created_payment = service.create_payment_for_project(
        p1,
        amount=1000.0,
        date=datetime(2026, 3, 1, 9, 0, 0),
        account_id="1010",
    )

    assert created_payment.project_id == str(p1.id)
    assert len(service.get_project_payments(str(p1.id), p1.client_id)) == 1
    assert service.get_project_payments(str(p2.id), p2.client_id) == []

    profitability_p1 = service.get_project_profitability(str(p1.id), p1.client_id)
    profitability_p2 = service.get_project_profitability(str(p2.id), p2.client_id)

    assert profitability_p1["total_paid"] == pytest.approx(1000.0)
    assert profitability_p1["balance_due"] == pytest.approx(0.0)
    assert profitability_p2["total_paid"] == pytest.approx(0.0)

    refreshed_p1 = repo.get_project_by_number(str(p1.id), p1.client_id)
    refreshed_p2 = repo.get_project_by_number(str(p2.id), p2.client_id)
    assert refreshed_p1 is not None
    assert refreshed_p2 is not None
    assert refreshed_p1.status == schemas.ProjectStatus.COMPLETED
    assert refreshed_p2.status == schemas.ProjectStatus.PLANNING


def test_create_payment_requires_stable_scope_for_duplicate_project_names(service_bundle):
    repo, service = service_bundle

    c1 = repo.create_client(schemas.Client(name="Client Duplicate Scope A"))
    c2 = repo.create_client(schemas.Client(name="Client Duplicate Scope B"))
    repo.create_project(
        schemas.Project(
            name="Duplicate Scope Project",
            client_id=str(c1.id),
            total_amount=1000.0,
        )
    )
    repo.create_project(
        schemas.Project(
            name="Duplicate Scope Project",
            client_id=str(c2.id),
            total_amount=1200.0,
        )
    )

    unresolved_project = schemas.Project(
        name="Duplicate Scope Project",
        client_id="",
        total_amount=500.0,
    )

    with pytest.raises(ValueError, match="اسم المشروع غير فريد"):
        service.create_payment_for_project(
            unresolved_project,
            amount=150.0,
            date=datetime(2026, 3, 1, 10, 0, 0),
            account_id="1101",
        )


def test_update_milestone_status_uses_stable_project_reference(service_bundle):
    repo, service = service_bundle

    c1 = repo.create_client(schemas.Client(name="Client M1"))
    c2 = repo.create_client(schemas.Client(name="Client M2"))

    p1 = repo.create_project(
        schemas.Project(
            name="Milestone Project",
            client_id=str(c1.id),
            total_amount=500.0,
            milestones=[
                schemas.ProjectMilestone(
                    id="m-1",
                    name="Contract",
                    percentage=100.0,
                    amount=500.0,
                )
            ],
        )
    )
    p2 = repo.create_project(
        schemas.Project(
            name="Milestone Project",
            client_id=str(c2.id),
            total_amount=800.0,
            milestones=[
                schemas.ProjectMilestone(
                    id="m-2",
                    name="Delivery",
                    percentage=100.0,
                    amount=800.0,
                )
            ],
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "UPDATE projects SET milestones = ? WHERE id = ?",
        (
            json.dumps(
                [
                    schemas.ProjectMilestone(
                        id="m-1",
                        name="Contract",
                        percentage=100.0,
                        amount=500.0,
                    ).model_dump(mode="json")
                ]
            ),
            p1.id,
        ),
    )
    cursor.execute(
        "UPDATE projects SET milestones = ? WHERE id = ?",
        (
            json.dumps(
                [
                    schemas.ProjectMilestone(
                        id="m-2",
                        name="Delivery",
                        percentage=100.0,
                        amount=800.0,
                    ).model_dump(mode="json")
                ]
            ),
            p2.id,
        ),
    )
    repo.sqlite_conn.commit()

    assert service.update_milestone_status(
        str(p1.id),
        "m-1",
        schemas.MilestoneStatus.PAID,
        client_id=p1.client_id,
    )

    refreshed_p1 = repo.get_project_by_number(str(p1.id), p1.client_id)
    refreshed_p2 = repo.get_project_by_number(str(p2.id), p2.client_id)
    assert refreshed_p1 is not None
    assert refreshed_p2 is not None
    assert refreshed_p1.milestones[0].status == schemas.MilestoneStatus.PAID
    assert refreshed_p2.milestones[0].status == schemas.MilestoneStatus.PENDING


def test_update_project_detects_duplicate_name_when_client_scope_comes_from_local_id(
    service_bundle,
):
    repo, service = service_bundle

    c1 = repo.create_client(schemas.Client(name="Scoped Client A"))
    c2 = repo.create_client(schemas.Client(name="Scoped Client B"))
    assert c1.id is not None
    assert c2.id is not None

    repo.sqlite_conn.execute(
        "UPDATE clients SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-scoped-client-a", int(c1.id)),
    )
    repo.sqlite_conn.execute(
        "UPDATE clients SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-scoped-client-b", int(c2.id)),
    )
    repo.sqlite_conn.commit()

    p1 = repo.create_project(
        schemas.Project(
            name="Scoped Duplicate Name",
            client_id="mongo-scoped-client-a",
            total_amount=500.0,
            status=schemas.ProjectStatus.PLANNING,
        )
    )
    repo.create_project(
        schemas.Project(
            name="Scoped Duplicate Name",
            client_id="mongo-scoped-client-b",
            total_amount=800.0,
            status=schemas.ProjectStatus.PLANNING,
        )
    )

    with pytest.raises(ValueError, match="يوجد مشروع آخر بنفس الاسم لهذا العميل"):
        service.update_project(
            str(p1.id),
            {
                "name": "Scoped Duplicate Name",
                "client_id": str(c2.id),  # UI can still submit the local client id.
                "items": [],
            },
        )


def test_update_all_projects_status_uses_stable_project_reference(service_bundle):
    repo, service = service_bundle

    c1 = repo.create_client(schemas.Client(name="Client Bulk Status A"))
    c2 = repo.create_client(schemas.Client(name="Client Bulk Status B"))

    p1 = repo.create_project(
        schemas.Project(
            name="Bulk Status Project",
            client_id=str(c1.id),
            total_amount=700.0,
            status=schemas.ProjectStatus.PLANNING,
        )
    )
    p2 = repo.create_project(
        schemas.Project(
            name="Bulk Status Project",
            client_id=str(c2.id),
            total_amount=900.0,
            status=schemas.ProjectStatus.PLANNING,
        )
    )

    repo.create_payment(
        schemas.Payment(
            project_id=str(p1.id),
            client_id=p1.client_id,
            date=datetime(2026, 3, 3, 11, 0, 0),
            amount=700.0,
            account_id="1101",
            method="Cash",
        )
    )

    service.update_all_projects_status()

    refreshed_p1 = repo.get_project_by_number(str(p1.id), p1.client_id)
    refreshed_p2 = repo.get_project_by_number(str(p2.id), p2.client_id)
    assert refreshed_p1 is not None
    assert refreshed_p2 is not None
    assert refreshed_p1.status == schemas.ProjectStatus.COMPLETED
    assert refreshed_p2.status == schemas.ProjectStatus.PLANNING


def test_delete_project_prefers_mongo_reference_when_local_id_missing(monkeypatch):
    import services.project_service as project_service_mod

    monkeypatch.setattr(project_service_mod, "PRINTING_AVAILABLE", False, raising=False)

    project = schemas.Project(
        id=None,
        _mongo_id="mongo-project-55",
        name="Shared Delete Project",
        client_id="CLIENT-55",
        total_amount=400.0,
    )

    class _Repo:
        def __init__(self):
            self.deleted_calls: list[tuple[str, str | None]] = []

        def get_project_by_number(self, project_ref, client_id=None):
            if str(project_ref or "").strip() in {"mongo-project-55", "Shared Delete Project"}:
                return project
            return None

        def get_all_projects(self):
            return [project]

        def delete_project(self, project_ref, client_id=None):
            self.deleted_calls.append((str(project_ref), client_id))
            return True

    repo = _Repo()
    service = ProjectService(repo, EventBus(), accounting_service=object())

    assert service.delete_project("mongo-project-55")
    assert repo.deleted_calls == [("mongo-project-55", "CLIENT-55")]


def test_print_project_invoice_accepts_client_scoped_duplicate_name(service_bundle):
    repo, service = service_bundle

    c1 = repo.create_client(schemas.Client(name="Client Print A"))
    c2 = repo.create_client(schemas.Client(name="Client Print B"))

    p1 = repo.create_project(
        schemas.Project(
            name="Printable Project",
            client_id=str(c1.id),
            total_amount=900.0,
        )
    )
    repo.create_project(
        schemas.Project(
            name="Printable Project",
            client_id=str(c2.id),
            total_amount=1200.0,
        )
    )
    repo.create_payment(
        schemas.Payment(
            project_id=p1.name,
            client_id=p1.client_id,
            date=datetime(2026, 3, 2, 10, 0, 0),
            amount=300.0,
            account_id="1101",
            method="Cash",
        )
    )

    captured: dict[str, object] = {}

    class _PrintingStub:
        def print_project_invoice(
            self,
            project,
            client_info,
            payments=None,
            background_image_path=None,
            auto_open=True,
        ):
            captured["project"] = project
            captured["client_info"] = client_info
            captured["payments"] = payments or []
            captured["background_image_path"] = background_image_path
            captured["auto_open"] = auto_open
            return "project-print.pdf"

    service.printing_service = _PrintingStub()

    result = service.print_project_invoice(
        p1.name,
        background_image_path="bg.png",
        auto_open=False,
        client_id=p1.client_id,
    )

    assert result == "project-print.pdf"
    assert captured["project"].id == p1.id
    assert captured["project"].client_id == p1.client_id
    assert captured["client_info"]["name"] == c1.name
    assert len(captured["payments"]) == 1
    assert captured["payments"][0]["amount"] == pytest.approx(300.0)
    assert captured["background_image_path"] == "bg.png"
    assert captured["auto_open"] is False


def test_project_service_delays_printing_service_until_needed(tmp_path, monkeypatch):
    import core.repository as repo_mod
    import services.project_service as project_service_mod

    db_path = tmp_path / "project_service_lazy_printing.db"
    monkeypatch.setenv("SKYWAVE_DISABLE_MONGO", "1")
    monkeypatch.setattr(repo_mod, "LOCAL_DB_FILE", str(db_path), raising=True)
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_connection", lambda self: None, raising=True
    )
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_retry_loop", lambda self: None, raising=True
    )

    created: list[object] = []

    class _PrintingStub:
        def __init__(self, settings_service):
            created.append(settings_service)

    monkeypatch.setattr(project_service_mod, "PRINTING_AVAILABLE", True, raising=True)
    monkeypatch.setattr(project_service_mod, "ProjectPrintingService", _PrintingStub, raising=True)

    repo = repo_mod.Repository()
    try:
        bus = EventBus()
        accounting = AccountingService(repo, bus)
        service = ProjectService(repo, bus, accounting, settings_service="settings")

        assert service.printing_service is None
        assert created == []

        loaded = service._ensure_printing_service()

        assert isinstance(loaded, _PrintingStub)
        assert service.printing_service is loaded
        assert created == ["settings"]
    finally:
        repo.close()
