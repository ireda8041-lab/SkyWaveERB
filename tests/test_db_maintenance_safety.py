from __future__ import annotations

import sqlite3

import pytest

from core import schemas
from core.db_maintenance import DatabaseMaintenance


def test_monthly_maintenance_keeps_same_project_name_for_different_clients(tmp_path, monkeypatch):
    import core.repository as repo_mod

    db_path = tmp_path / "maintenance_safety.db"
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
        client_a = repo.create_client(schemas.Client(name="Maintenance Client A"))
        client_b = repo.create_client(schemas.Client(name="Maintenance Client B"))

        repo.create_project(
            schemas.Project(name="Website", client_id=str(client_a.id), total_amount=1000.0)
        )
        repo.create_project(
            schemas.Project(name="Website", client_id=str(client_b.id), total_amount=1500.0)
        )
    finally:
        repo.close()

    maintenance = DatabaseMaintenance(db_path=str(db_path))
    assert maintenance.run_all_maintenance(auto_mode=False) is True

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name, client_id FROM projects
            WHERE (sync_status != 'deleted' OR sync_status IS NULL)
            AND (is_deleted = 0 OR is_deleted IS NULL)
            ORDER BY client_id
            """
        )
        rows = cursor.fetchall()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_projects_name_client_unique'"
        )
        index_name = cursor.fetchone()
    finally:
        conn.close()

    assert rows == [("Website", str(client_a.id)), ("Website", str(client_b.id))]
    assert index_name == ("idx_projects_name_client_unique",)


def test_monthly_maintenance_recreates_unique_indexes_after_cleaning_duplicates(
    tmp_path, monkeypatch
):
    import core.repository as repo_mod

    db_path = tmp_path / "maintenance_cleanup_indexes.db"
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
        client = repo.create_client(schemas.Client(name="Duplicate Index Client"))
        repo.sqlite_conn.execute("DROP INDEX IF EXISTS idx_clients_name_unique")
        repo.sqlite_conn.execute(
            """
            INSERT INTO clients (
                sync_status, created_at, last_modified, name, company_name, email,
                phone, address, country, vat_number, status,
                client_type, work_field, logo_path, logo_data, has_logo, logo_last_synced,
                client_notes, is_vip, dirty_flag, is_deleted
            )
            SELECT
                sync_status, created_at, last_modified, name, company_name, email,
                phone, address, country, vat_number, status,
                client_type, work_field, logo_path, logo_data, has_logo, logo_last_synced,
                client_notes, is_vip, dirty_flag, is_deleted
            FROM clients
            WHERE id = ?
            """,
            (client.id,),
        )
        repo.sqlite_conn.commit()
    finally:
        repo.close()

    maintenance = DatabaseMaintenance(db_path=str(db_path))
    assert maintenance.run_all_maintenance(auto_mode=False) is True

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM clients WHERE name = ?", ("Duplicate Index Client",))
        remaining_rows = cursor.fetchone()[0]
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_clients_name_unique'"
        )
        index_name = cursor.fetchone()
    finally:
        conn.close()

    assert remaining_rows == 1
    assert index_name == ("idx_clients_name_unique",)


def test_db_maintenance_rejects_invalid_identifier_in_table_columns(tmp_path):
    db_path = tmp_path / "maintenance_guard.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
    finally:
        conn.close()

    maintenance = DatabaseMaintenance(db_path=str(db_path))
    assert maintenance.connect() is True
    try:
        with pytest.raises(ValueError):
            maintenance._table_columns('clients"; DROP TABLE clients; --')
    finally:
        maintenance.close()
