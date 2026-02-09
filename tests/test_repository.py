from __future__ import annotations

import types

import pytest

from core import schemas


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    import core.repository as repo_mod

    db_path = tmp_path / "repo_test.db"
    monkeypatch.setenv("SKYWAVE_DISABLE_MONGO", "1")
    monkeypatch.setattr(repo_mod, "LOCAL_DB_FILE", str(db_path), raising=True)
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_connection", lambda self: None, raising=True
    )
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_retry_loop", lambda self: None, raising=True
    )

    instance = repo_mod.Repository()
    try:
        yield instance
    finally:
        instance.close()


def test_clients_table_migration_has_lazy_logo_columns(repo):
    cursor = repo.get_cursor()
    try:
        cursor.execute("PRAGMA table_info(clients)")
        cols = {row[1] for row in cursor.fetchall()}
    finally:
        cursor.close()

    assert "has_logo" in cols
    assert "logo_last_synced" in cols


def test_fetch_client_logo_on_demand_updates_sqlite(repo):
    created = repo.create_client(schemas.Client(name="Lazy Logo Client"))

    cursor = repo.get_cursor()
    try:
        cursor.execute(
            "UPDATE clients SET _mongo_id = ? WHERE id = ?",
            ("mongo-client-1", int(created.id)),
        )
        repo.sqlite_conn.commit()
    finally:
        cursor.close()

    class _FakeClientsCollection:
        def find_one(self, _query, _projection):
            return {
                "_id": "mongo-client-1",
                "logo_data": "data:image/png;base64,ZmFrZQ==",
                "last_modified": "2026-02-09T20:00:00",
            }

        def update_one(self, *_args, **_kwargs):
            return types.SimpleNamespace(modified_count=1)

    repo.online = True
    repo.mongo_client = object()
    repo.mongo_db = types.SimpleNamespace(clients=_FakeClientsCollection())

    assert repo.fetch_client_logo_on_demand(str(created.id)) is True

    verify = repo.get_cursor()
    try:
        verify.execute(
            "SELECT logo_data, has_logo, logo_last_synced FROM clients WHERE id = ?",
            (int(created.id),),
        )
        row = verify.fetchone()
    finally:
        verify.close()

    assert row is not None
    assert bool(row["logo_data"])
    assert row["has_logo"] == 1
    assert row["logo_last_synced"] is not None
