from __future__ import annotations

import types
from datetime import datetime

import pytest

from core import schemas
from services.notification_service import NotificationService


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


def test_fetch_client_logo_on_demand_ignores_deleted_remote_client(repo):
    created = repo.create_client(schemas.Client(name="Deleted Lazy Logo Client"))

    cursor = repo.get_cursor()
    try:
        cursor.execute(
            "UPDATE clients SET _mongo_id = ? WHERE id = ?",
            ("mongo-client-deleted-1", int(created.id)),
        )
        repo.sqlite_conn.commit()
    finally:
        cursor.close()

    class _FakeDeletedClientsCollection:
        def find_one(self, query, _projection):
            query_text = str(query)
            if "is_deleted" in query_text or "sync_status" in query_text:
                return None
            return {
                "_id": "mongo-client-deleted-1",
                "logo_data": "data:image/png;base64,REVFTEVURUQ=",
                "has_logo": True,
                "sync_status": "deleted",
                "is_deleted": True,
                "last_modified": "2026-02-09T20:00:00",
            }

        def update_one(self, *_args, **_kwargs):
            return types.SimpleNamespace(modified_count=1)

    repo.online = True
    repo.mongo_client = object()
    repo.mongo_db = types.SimpleNamespace(clients=_FakeDeletedClientsCollection())

    assert repo.fetch_client_logo_on_demand(str(created.id)) is False

    verify = repo.get_cursor()
    try:
        verify.execute(
            "SELECT logo_data, has_logo FROM clients WHERE id = ?",
            (int(created.id),),
        )
        row = verify.fetchone()
    finally:
        verify.close()

    assert row is not None
    assert row["logo_data"] in (None, "")
    assert row["has_logo"] == 0


def test_mongo_client_options_are_bounded(repo, monkeypatch):
    monkeypatch.setenv("SKYWAVE_MONGO_MAX_POOL_SIZE", "99")
    monkeypatch.setenv("SKYWAVE_MONGO_MIN_POOL_SIZE", "3")
    monkeypatch.setenv("SKYWAVE_MONGO_MAX_IDLE_MS", "90000")
    monkeypatch.setenv("SKYWAVE_MONGO_WAIT_QUEUE_TIMEOUT_MS", "15000")

    options = repo._mongo_client_options()

    assert options["maxPoolSize"] == 99
    assert options["minPoolSize"] == 3
    assert options["maxIdleTimeMS"] == 90000
    assert options["waitQueueTimeoutMS"] == 15000


def test_update_account_balance_updates_all_remote_rows_with_same_code(repo):
    created = repo.create_account(
        schemas.Account(
            name="Cashbox Hazem",
            code="111001",
            type=schemas.AccountType.CASH,
            balance=0.0,
        )
    )

    cursor = repo.get_cursor()
    try:
        cursor.execute(
            "UPDATE accounts SET _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1 WHERE id = ?",
            ("82dfff052f444eb792998ba1", int(created.id)),
        )
        repo.sqlite_conn.commit()
    finally:
        cursor.close()

    class _FakeAccountsCollection:
        def __init__(self):
            self.documents = [
                {"_id": "82dfff052f444eb792998ba1", "code": "111001", "balance": 75200.2},
                {"_id": "shadow-duplicate", "code": "111001", "balance": 75200.2},
            ]
            self.updated = []

        def update_many(self, query, update_doc):
            self.updated.append((dict(query), dict(update_doc)))
            matched = 0
            for document in self.documents:
                if document.get("code") == query.get("code"):
                    document.update(update_doc.get("$set", {}))
                    matched += 1
            return types.SimpleNamespace(matched_count=matched, modified_count=matched)

    repo.online = True
    repo.mongo_client = object()
    repo.mongo_db = types.SimpleNamespace(accounts=_FakeAccountsCollection())

    assert repo.update_account_balance("111001", 44700.0) is True
    assert all(doc["balance"] == 44700.0 for doc in repo.mongo_db.accounts.documents)

    verify = repo.get_cursor()
    try:
        verify.execute(
            "SELECT balance, sync_status, dirty_flag FROM accounts WHERE code = ?",
            ("111001",),
        )
        row = verify.fetchone()
    finally:
        verify.close()

    assert row is not None
    assert row["balance"] == 44700.0
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0


def test_accounts_infer_group_flags_without_sqlite_column(repo):
    cursor = repo.get_cursor()
    try:
        cursor.execute("PRAGMA table_info(accounts)")
        cols = {row[1] for row in cursor.fetchall()}
    finally:
        cursor.close()

    assert "is_group" not in cols

    repo.create_account(
        schemas.Account(
            name="Parent Cash Group",
            code="111000",
            type=schemas.AccountType.CASH,
        )
    )
    repo.create_account(
        schemas.Account(
            name="Leaf Cashbox",
            code="111001",
            type=schemas.AccountType.CASH,
            parent_code="111000",
        )
    )

    # Must not fail even when SQLite schema does not persist the helper flag.
    repo.update_is_group_flags()

    accounts = {account.code: account for account in repo.get_all_accounts()}
    assert accounts["111000"].is_group is True
    assert accounts["111001"].is_group is False


def test_init_mongo_indexes_returns_false_without_connection(repo):
    repo.mongo_db = None
    assert repo._init_mongo_indexes() is False


def test_init_mongo_indexes_uses_stable_snapshot_when_repo_is_closed_mid_run(repo):
    class _FakeCollection:
        def __init__(self, on_first_call=None):
            self.calls = 0
            self._on_first_call = on_first_call

        def create_index(self, _spec):
            self.calls += 1
            if self.calls == 1 and self._on_first_call is not None:
                self._on_first_call()

    class _FakeMongoDB:
        def __init__(self, on_first_call=None):
            self.sync_queue = _FakeCollection()
            self.projects = _FakeCollection()
            self.clients = _FakeCollection()
            self.accounts = _FakeCollection()
            self.invoices = _FakeCollection()
            self.payments = _FakeCollection()
            self.journal_entries = _FakeCollection()
            self.expenses = _FakeCollection()
            self.notifications = _FakeCollection()
            self.tasks = _FakeCollection()
            self.users = _FakeCollection(on_first_call=on_first_call)
            self.currencies = _FakeCollection()

    repo.online = True
    repo.mongo_db = _FakeMongoDB(on_first_call=lambda: setattr(repo, "mongo_db", None))

    assert repo._init_mongo_indexes() is True


def test_ensure_mongo_indexes_ready_skips_when_repository_is_already_closed(repo, monkeypatch):
    repo.online = True
    repo.mongo_db = object()
    repo._closed = True

    monkeypatch.setattr(
        repo, "_init_mongo_indexes", lambda: (_ for _ in ()).throw(RuntimeError("should not run"))
    )

    repo._ensure_mongo_indexes_ready()


def test_repository_close_stops_and_joins_mongo_background_threads(repo):
    joined_timeouts: list[float] = []

    class _FakeThread:
        def is_alive(self):
            return True

        def join(self, timeout=None):
            joined_timeouts.append(timeout)

    repo._mongo_connection_thread = _FakeThread()
    repo._mongo_retry_thread = _FakeThread()

    repo.close()

    assert repo._mongo_stop_event.is_set() is True
    assert joined_timeouts == [1.0, 1.0]


def test_client_reference_values_skip_empty_lookup(repo, monkeypatch):
    monkeypatch.setattr(
        repo,
        "get_client_by_id",
        lambda _client_id: (_ for _ in ()).throw(AssertionError("should not lookup empty client")),
    )

    assert repo._client_reference_values("") == set()
    assert repo._client_reference_values(None) == set()


def test_repository_wakeup_keeps_synced_notifications_clean_and_redirties_pending_ones(
    tmp_path, monkeypatch, mock_event_bus
):
    import core.repository as repo_mod

    db_path = tmp_path / "repo_sync_wakeup.db"
    monkeypatch.setenv("SKYWAVE_DISABLE_MONGO", "1")
    monkeypatch.setattr(repo_mod, "LOCAL_DB_FILE", str(db_path), raising=True)
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_connection", lambda self: None, raising=True
    )
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_retry_loop", lambda self: None, raising=True
    )

    repo = repo_mod.Repository()
    synced_id = None
    pending_id = None
    try:
        service = NotificationService(repo, mock_event_bus)
        monkeypatch.setattr(service, "_show_local_toast", lambda notification: None)

        synced = service.create_notification("Synced", "Should stay clean")
        pending = service.create_notification("Pending", "Should wake up")
        assert synced is not None
        assert pending is not None

        synced_id = synced.id
        pending_id = pending.id

        repo.sqlite_conn.execute(
            """
            UPDATE notifications
            SET sync_status = 'synced', dirty_flag = 1, _mongo_id = ?, is_deleted = 0
            WHERE id = ?
            """,
            ("mongo-notification-synced-1", synced_id),
        )
        repo.sqlite_conn.execute(
            """
            UPDATE notifications
            SET sync_status = 'pending', dirty_flag = 0, _mongo_id = NULL, is_deleted = 0
            WHERE id = ?
            """,
            (pending_id,),
        )
        repo.sqlite_conn.commit()
    finally:
        repo.close()

    reopened = repo_mod.Repository()
    try:
        rows = reopened.sqlite_conn.execute(
            """
            SELECT id, sync_status, dirty_flag, _mongo_id
            FROM notifications
            WHERE id IN (?, ?)
            ORDER BY id ASC
            """,
            (synced_id, pending_id),
        ).fetchall()
    finally:
        reopened.close()

    rows_by_id = {row["id"]: row for row in rows}

    assert rows_by_id[synced_id]["sync_status"] == "synced"
    assert rows_by_id[synced_id]["dirty_flag"] == 0
    assert rows_by_id[synced_id]["_mongo_id"] == "mongo-notification-synced-1"

    assert rows_by_id[pending_id]["sync_status"] == "pending"
    assert rows_by_id[pending_id]["dirty_flag"] == 1
    assert rows_by_id[pending_id]["_mongo_id"] is None


def test_repository_sets_sqlite_user_version_after_bootstrap(repo):
    cursor = repo.get_cursor()
    try:
        cursor.execute("PRAGMA user_version")
        row = cursor.fetchone()
    finally:
        cursor.close()

    assert row is not None
    assert row[0] == 1


def test_repository_skips_heavy_bootstrap_when_sqlite_user_version_is_current(
    tmp_path, monkeypatch
):
    import core.repository as repo_mod

    db_path = tmp_path / "repo_bootstrap_skip.db"
    monkeypatch.setenv("SKYWAVE_DISABLE_MONGO", "1")
    monkeypatch.setattr(repo_mod, "LOCAL_DB_FILE", str(db_path), raising=True)
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_connection", lambda self: None, raising=True
    )
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_retry_loop", lambda self: None, raising=True
    )

    first = repo_mod.Repository()
    try:
        user_version = first._get_sqlite_user_version()
    finally:
        first.close()

    assert user_version == repo_mod._SQLITE_BOOTSTRAP_VERSION

    monkeypatch.setattr(
        repo_mod.Repository,
        "_create_sqlite_indexes",
        lambda self: (_ for _ in ()).throw(RuntimeError("should skip index bootstrap")),
        raising=True,
    )
    monkeypatch.setattr(
        repo_mod.Repository,
        "_optimize_sqlite_performance",
        lambda self: (_ for _ in ()).throw(RuntimeError("should skip sqlite re-optimize")),
        raising=True,
    )
    monkeypatch.setattr(
        repo_mod.Repository,
        "_migrate_project_reference_tables_remove_name_foreign_keys",
        lambda self: (_ for _ in ()).throw(RuntimeError("should skip heavy migration")),
        raising=True,
    )

    reopened = repo_mod.Repository()
    try:
        assert reopened._get_sqlite_user_version() == repo_mod._SQLITE_BOOTSTRAP_VERSION
    finally:
        reopened.close()


def test_get_all_payments_uses_cache_and_reloads_after_invalidation(repo, monkeypatch):
    repo.create_payment(
        schemas.Payment(
            project_id="project-1",
            client_id="client-1",
            date=datetime(2026, 3, 12, 10, 0, 0),
            amount=1500.0,
            account_id="111001",
            method="Cash",
        )
    )

    original_get_cursor = repo.get_cursor
    call_count = {"value": 0}

    def counting_get_cursor():
        call_count["value"] += 1
        return original_get_cursor()

    monkeypatch.setattr(repo, "get_cursor", counting_get_cursor)

    first = repo.get_all_payments()
    second = repo.get_all_payments()

    assert len(first) == 1
    assert len(second) == 1
    assert call_count["value"] == 1

    repo.create_payment(
        schemas.Payment(
            project_id="project-1",
            client_id="client-1",
            date=datetime(2026, 3, 12, 11, 0, 0),
            amount=1750.0,
            account_id="111001",
            method="Cash",
        )
    )

    third = repo.get_all_payments()

    assert len(third) == 2
    assert call_count["value"] == 2


def test_invalidate_table_cache_always_clears_dashboard_cache(repo, monkeypatch):
    import core.repository as repo_mod

    repo_mod.Repository._dashboard_cache = object()
    repo_mod.Repository._dashboard_cache_time = 123.0
    monkeypatch.setattr(repo_mod, "CACHE_ENABLED", False, raising=True)

    repo.invalidate_table_cache("payments")

    assert repo_mod.Repository._dashboard_cache is None
    assert repo_mod.Repository._dashboard_cache_time == 0


def test_start_mongo_connection_defers_pymongo_import_to_background(tmp_path, monkeypatch):
    import core.repository as repo_mod

    db_path = tmp_path / "repo_mongo_threading.db"
    monkeypatch.setattr(repo_mod, "LOCAL_DB_FILE", str(db_path), raising=True)
    monkeypatch.delenv("SKYWAVE_DISABLE_MONGO", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    original_start = repo_mod.Repository._start_mongo_connection
    monkeypatch.setattr(repo_mod.Repository, "_start_mongo_connection", lambda self: None)
    monkeypatch.setattr(repo_mod.Repository, "_start_mongo_retry_loop", lambda self: None)

    class _FakeThread:
        def __init__(self, target=None, daemon=None, name=None):
            self.target = target
            self.daemon = daemon
            self.name = name
            self.started = False

        def start(self):
            self.started = True

    monkeypatch.setattr(
        repo_mod,
        "_get_pymongo_module",
        lambda: (_ for _ in ()).throw(AssertionError("pymongo import should be deferred")),
    )
    monkeypatch.setattr(repo_mod.threading, "Thread", _FakeThread)

    instance = repo_mod.Repository()
    try:
        instance._mongo_connecting = False
        instance._mongo_connection_thread = None

        original_start(instance)

        assert isinstance(instance._mongo_connection_thread, _FakeThread)
        assert instance._mongo_connection_thread.started is True
        assert instance._mongo_connecting is True
    finally:
        instance.close()


def test_project_currency_snapshot_round_trip(repo):
    created = repo.create_project(
        schemas.Project(
            name="USD Snapshot Project",
            client_id="client-1",
            currency="USD",
            exchange_rate_snapshot=50.0,
            items=[
                schemas.ProjectItem(
                    service_id="svc-1",
                    description="Landing Page",
                    quantity=1.0,
                    unit_price=5000.0,
                    total=5000.0,
                )
            ],
            total_amount=5000.0,
            start_date=datetime(2026, 3, 13),
            end_date=datetime(2026, 3, 20),
        )
    )

    fetched = next(
        (
            project
            for project in repo.get_all_projects()
            if str(project.name) == "USD Snapshot Project"
        ),
        None,
    )

    assert fetched is not None
    assert str(getattr(fetched.currency, "value", fetched.currency)) == "USD"
    assert fetched.exchange_rate_snapshot == 50.0


def test_fetch_live_exchange_rate_normalizes_egy_alias():
    import core.repository as repo_mod

    repo = repo_mod.Repository.__new__(repo_mod.Repository)

    assert repo.fetch_live_exchange_rate("EGY") == 1.0


def test_update_all_exchange_rates_skips_base_currency_alias(monkeypatch):
    import core.repository as repo_mod

    repo = repo_mod.Repository.__new__(repo_mod.Repository)
    repo.get_all_currencies = lambda: [
        {"code": "EGY", "rate": 1.0},
        {"code": "USD", "rate": 50.0},
    ]

    requested_codes: list[str] = []
    saved_codes: list[str] = []

    def fake_fetch(code):
        requested_codes.append(code)
        return 55.5 if code == "USD" else None

    repo.fetch_live_exchange_rate = fake_fetch
    repo.save_currency = lambda currency: saved_codes.append(str(currency.get("code"))) or True

    result = repo.update_all_exchange_rates()

    assert requested_codes == ["USD"]
    assert saved_codes == ["USD"]
    assert result["updated"] == 1
    assert result["failed"] == 0
    assert "EGY" not in result["results"]
