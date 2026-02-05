from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from core import schemas


def test_get_project_by_number_is_thread_safe(tmp_path, monkeypatch):
    import core.repository as repo_mod

    db_path = tmp_path / "repo_concurrency.db"
    monkeypatch.setattr(repo_mod, "LOCAL_DB_FILE", str(db_path), raising=True)

    repo = repo_mod.Repository()
    try:
        client = repo.create_client(schemas.Client(name="C1"))
        repo.create_project(
            schemas.Project(name="P1", client_id=str(client.id), total_amount=1000.0)
        )

        def _read():
            return repo.get_project_by_number("P1")

        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(lambda _: _read(), range(80)))

        assert all(r is not None for r in results)
        assert all(r.name == "P1" for r in results)
    finally:
        repo.close()
