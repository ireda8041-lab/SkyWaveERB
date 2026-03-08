from __future__ import annotations

from datetime import datetime

import pytest

from core import schemas
from core.event_bus import EventBus
from services.expense_service import ExpenseService


@pytest.fixture()
def sqlite_repo(tmp_path, monkeypatch):
    import core.repository as repo_mod

    db_path = tmp_path / "expense_service_stats.db"
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
        yield repo
    finally:
        repo.close()


def test_expense_statistics_merge_legacy_name_and_stable_project_reference(sqlite_repo):
    client = sqlite_repo.create_client(schemas.Client(name="Expense Stats Client"))
    project = sqlite_repo.create_project(
        schemas.Project(
            name="Expense Stats Project",
            client_id=str(client.id),
            total_amount=900.0,
        )
    )

    sqlite_repo.create_expense(
        schemas.Expense(
            project_id=str(project.id),
            date=datetime(2026, 1, 10, 11, 0, 0),
            category="Ops",
            amount=40.0,
            description="stable expense",
            account_id="5001",
            payment_account_id="1101",
        )
    )

    cursor = sqlite_repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO expenses (
            sync_status, created_at, last_modified, date, category, amount,
            description, account_id, payment_account_id, project_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-01-11T12:00:00",
            "2026-01-11T12:00:00",
            "2026-01-11T12:00:00",
            "Ops",
            60.0,
            "legacy expense",
            "5001",
            "1101",
            project.name,
            1,
            0,
        ),
    )
    sqlite_repo.sqlite_conn.commit()

    service = ExpenseService(sqlite_repo, EventBus())
    stats = service.get_expense_statistics(
        start_date=datetime(2026, 1, 1, 0, 0, 0),
        end_date=datetime(2026, 1, 31, 23, 59, 59),
    )

    assert stats["total_amount"] == pytest.approx(100.0)
    assert stats["by_project"] == {str(project.id): pytest.approx(100.0)}


def test_expense_statistics_do_not_merge_ambiguous_legacy_duplicate_project_names(sqlite_repo):
    client_a = sqlite_repo.create_client(schemas.Client(name="Stats Duplicate Client A"))
    client_b = sqlite_repo.create_client(schemas.Client(name="Stats Duplicate Client B"))
    sqlite_repo.create_project(
        schemas.Project(name="Shared Stats Project", client_id=str(client_a.id), total_amount=600.0)
    )
    sqlite_repo.create_project(
        schemas.Project(name="Shared Stats Project", client_id=str(client_b.id), total_amount=700.0)
    )

    cursor = sqlite_repo.sqlite_conn.cursor()
    expense_rows = [
        (40.0, "legacy expense a", "2026-01-11T12:00:00"),
        (60.0, "legacy expense b", "2026-01-12T12:00:00"),
    ]
    for amount, description, created_at in expense_rows:
        cursor.execute(
            """
            INSERT INTO expenses (
                sync_status, created_at, last_modified, date, category, amount,
                description, account_id, payment_account_id, project_id, dirty_flag, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "new_offline",
                created_at,
                created_at,
                created_at,
                "Ops",
                amount,
                description,
                "5001",
                "1101",
                "Shared Stats Project",
                1,
                0,
            ),
        )
    sqlite_repo.sqlite_conn.commit()

    service = ExpenseService(sqlite_repo, EventBus())
    stats = service.get_expense_statistics(
        start_date=datetime(2026, 1, 1, 0, 0, 0),
        end_date=datetime(2026, 1, 31, 23, 59, 59),
    )

    assert stats["total_amount"] == pytest.approx(100.0)
    assert len(stats["by_project"]) == 2
    assert sorted(stats["by_project"].values()) == [pytest.approx(40.0), pytest.approx(60.0)]
    assert all(key.startswith("Shared Stats Project [ambiguous:") for key in stats["by_project"])
