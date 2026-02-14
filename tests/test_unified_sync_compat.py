import sqlite3
import time
from datetime import datetime
from pathlib import Path

import core.realtime_sync as realtime_mod
from core.realtime_sync import RealtimeSyncManager, ensure_replica_set_uri, is_local_mongo_uri
from core.unified_sync import UnifiedSyncManagerV3


class _FakeAdmin:
    def command(self, *_args, **_kwargs):
        return {"ok": 1}


class _FakeMongoClient:
    def __init__(self):
        self.admin = _FakeAdmin()


class _FakeRepo:
    def __init__(self, online: bool = True):
        self.mongo_client = _FakeMongoClient() if online else None
        self.mongo_db = object() if online else None
        self.online = online


class _FakeCollection:
    def __init__(self, records: list[dict] | None = None):
        self._records = records or []
        self.inserted: list[dict] = []
        self.updated: list[tuple[dict, dict, bool]] = []
        self.deleted: list[dict] = []
        self._seq = 0

    def find(self, _query=None):
        return list(self._records)

    def insert_one(self, data: dict):
        self._seq += 1
        doc = dict(data)
        doc_id = f"fake-{self._seq}"
        doc["_id"] = doc_id
        self._records.append(doc)
        self.inserted.append(doc)

        class _Result:
            inserted_id = doc_id

        return _Result()

    def update_one(self, filter_doc: dict, update_doc: dict, upsert: bool = False):
        self.updated.append((dict(filter_doc), dict(update_doc), bool(upsert)))

    def delete_one(self, filter_doc: dict):
        self.deleted.append(dict(filter_doc))


class _FakeMongoDB(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = _FakeCollection([])
        return super().__getitem__(key)


class _FakeRepoWithSqlite:
    def __init__(self, db_path, remote_clients: list[dict]):
        self.online = True
        self.mongo_client = _FakeMongoClient()
        self.sqlite_conn = sqlite3.connect(str(db_path))
        self.sqlite_conn.row_factory = sqlite3.Row
        self.mongo_db = _FakeMongoDB()
        self.mongo_db["clients"] = _FakeCollection(remote_clients)
        self._create_tables()

    def _create_tables(self):
        cur = self.sqlite_conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                _mongo_id TEXT,
                name TEXT,
                created_at TEXT,
                last_modified TEXT,
                sync_status TEXT,
                dirty_flag INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0
            )
            """
        )
        self.sqlite_conn.commit()

    def get_cursor(self):
        return self.sqlite_conn.cursor()


def test_sync_now_compat_success_updates_metrics():
    manager = UnifiedSyncManagerV3(_FakeRepo(online=True))

    manager.push_local_changes = lambda: {
        "success": True,
        "pushed": 2,
        "deleted": 1,
        "errors": 0,
    }
    manager.pull_remote_changes = lambda: {
        "success": True,
        "pulled": 3,
        "deleted": 1,
        "errors": 0,
    }

    result = manager.sync_now()
    metrics = manager.get_sync_metrics()

    assert result["success"] is True
    assert result["pushed"] == 2
    assert result["pulled"] == 3
    assert result["deleted"] == 2
    assert result["errors"] == 0

    assert metrics["total_syncs"] == 1
    assert metrics["successful_syncs"] == 1
    assert metrics["failed_syncs"] == 0
    assert metrics["total_records_synced"] == 5
    assert metrics["last_sync_time"] is not None


def test_sync_now_compat_offline_tracks_failure():
    manager = UnifiedSyncManagerV3(_FakeRepo(online=False))

    result = manager.sync_now()
    metrics = manager.get_sync_metrics()

    assert result["success"] is False
    assert result["reason"] == "offline"
    assert metrics["total_syncs"] == 1
    assert metrics["failed_syncs"] == 1


def test_build_last_modified_query_supports_string_and_datetime_thresholds():
    manager = UnifiedSyncManagerV3(_FakeRepo(online=True))
    query = manager._build_last_modified_query("2026-02-01T10:20:30")

    assert "$or" in query
    assert len(query["$or"]) == 2
    date_branch = query["$or"][0]["$and"]
    string_branch = query["$or"][1]["$and"]

    assert date_branch[0]["last_modified"]["$type"] == "date"
    assert string_branch[0]["last_modified"]["$type"] == "string"
    assert string_branch[1]["last_modified"]["$gt"] == "2026-02-01T10:20:30"


def test_pull_remote_changes_handles_datetime_last_modified_and_persists_watermark(tmp_path):
    ts = datetime(2026, 2, 9, 12, 30, 45)
    repo = _FakeRepoWithSqlite(
        db_path=tmp_path / "sync_test.db",
        remote_clients=[
            {
                "_id": "mongo-client-1",
                "name": "ACME",
                "created_at": ts,
                "last_modified": ts,
                "is_deleted": False,
            }
        ],
    )
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["clients"]

    result = manager.pull_remote_changes()

    assert result["success"] is True
    assert result["pulled"] == 1

    cursor = repo.sqlite_conn.cursor()
    cursor.execute("SELECT name, _mongo_id, last_modified, sync_status FROM clients")
    row = cursor.fetchone()

    assert row is not None
    assert row["name"] == "ACME"
    assert row["_mongo_id"] == "mongo-client-1"
    assert row["last_modified"] == ts.isoformat()
    assert row["sync_status"] == "synced"

    assert manager._watermarks.get("clients") == ts.isoformat()
    assert (tmp_path / "sync_watermarks.json").exists()


def test_pull_remote_changes_emits_ui_table_signal_for_changed_tables(tmp_path, monkeypatch):
    ts = datetime(2026, 2, 9, 12, 45, 0)
    repo = _FakeRepoWithSqlite(
        db_path=tmp_path / "sync_signal_test.db",
        remote_clients=[
            {
                "_id": "mongo-client-2",
                "name": "Signal Co",
                "created_at": ts,
                "last_modified": ts,
                "is_deleted": False,
            }
        ],
    )
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["clients"]

    from core.signals import app_signals

    seen = []
    monkeypatch.setattr(
        app_signals,
        "emit_ui_data_changed",
        lambda table: seen.append(table),
        raising=True,
    )

    result = manager.pull_remote_changes()

    assert result["success"] is True
    assert "clients" in seen


def test_push_local_changes_includes_modified_offline_without_dirty_flag(tmp_path):
    repo = _FakeRepoWithSqlite(db_path=tmp_path / "sync_push_modified.db", remote_clients=[])
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["clients"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (_mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            "Local Modified",
            "2026-02-09T10:00:00",
            "2026-02-09T10:05:00",
            "modified_offline",
            0,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    result = manager.push_local_changes()

    assert result["success"] is True
    assert result["pushed"] == 1
    assert result["errors"] == 0

    local = repo.sqlite_conn.cursor()
    local.execute(
        "SELECT _mongo_id, sync_status, dirty_flag FROM clients WHERE name = ?", ("Local Modified",)
    )
    row = local.fetchone()
    assert row is not None
    assert row["_mongo_id"] == "fake-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert len(repo.mongo_db["clients"].inserted) == 1


def test_push_local_changes_handles_deleted_status_without_dirty_flag(tmp_path):
    repo = _FakeRepoWithSqlite(db_path=tmp_path / "sync_push_deleted.db", remote_clients=[])
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["clients"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (_mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-client-9",
            "To Delete",
            "2026-02-09T10:00:00",
            "2026-02-09T10:05:00",
            "deleted",
            0,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    result = manager.push_local_changes()

    assert result["success"] is True
    assert result["deleted"] == 1
    assert result["errors"] == 0
    assert len(repo.mongo_db["clients"].updated) >= 1

    local = repo.sqlite_conn.cursor()
    local.execute("SELECT COUNT(*) FROM clients WHERE name = ?", ("To Delete",))
    assert local.fetchone()[0] == 0


def test_request_realtime_pull_deduplicates_fast_events():
    manager = UnifiedSyncManagerV3(_FakeRepo(online=True))
    calls = []

    manager.force_pull = lambda table=None: calls.append(table)

    first = manager.request_realtime_pull("clients")
    second = manager.request_realtime_pull("clients")

    assert first is True
    assert second is False
    assert calls == ["clients"]


def test_realtime_events_are_queued_during_full_sync_then_flushed():
    manager = UnifiedSyncManagerV3(_FakeRepo(online=True))
    calls = []
    manager.force_pull = lambda table=None: calls.append(table)

    manager._is_syncing = True
    scheduled = manager.request_realtime_pull("clients")
    assert scheduled is False
    assert "__all__" not in manager._queued_realtime_tables
    assert "clients" in manager._queued_realtime_tables

    manager._is_syncing = False
    manager._flush_realtime_pull_queue()

    assert calls == [None]
    assert not manager._queued_realtime_tables


def test_ensure_replica_set_uri_for_local_connection():
    uri = "mongodb://localhost:27017/skywave_erp_db"
    normalized = ensure_replica_set_uri(uri, "rs0")

    assert "replicaSet=rs0" in normalized
    assert "directConnection=false" in normalized


def test_ensure_replica_set_uri_updates_existing_query_values():
    uri = "mongodb://mongo.example.com:27017/skywave_erp_db?replicaSet=oldRs&directConnection=true"
    normalized = ensure_replica_set_uri(uri, "rs0")

    assert "replicaSet=rs0" in normalized
    assert "directConnection=false" in normalized


def test_is_local_mongo_uri_detects_remote_hosts():
    assert is_local_mongo_uri("mongodb://localhost:27017") is True
    assert is_local_mongo_uri("mongodb://127.0.0.1:27017") is True
    assert is_local_mongo_uri("mongodb://mongo.internal:27017") is False
    assert is_local_mongo_uri("mongodb+srv://cluster.example.com/test") is False


def test_realtime_manager_rechecks_after_local_bootstrap(monkeypatch):
    repo = _FakeRepo(online=True)
    manager = RealtimeSyncManager(repo)
    detect_calls = {"count": 0}

    def _fake_detect():
        detect_calls["count"] += 1
        return detect_calls["count"] >= 2

    monkeypatch.setattr(manager, "_detect_change_stream_support", _fake_detect)
    monkeypatch.setattr(manager, "_try_enable_change_streams_locally", lambda: True)
    monkeypatch.setattr(manager, "_start_unified_watcher", lambda: None)

    manager._realtime_auto_detect = True
    manager._realtime_enabled = True

    started = manager.start()

    assert started is True
    assert manager.is_running is True
    assert detect_calls["count"] == 2


def test_realtime_manager_fallback_when_change_stream_not_supported(monkeypatch):
    repo = _FakeRepo(online=True)
    manager = RealtimeSyncManager(repo)

    monkeypatch.setattr(manager, "_detect_change_stream_support", lambda: False)
    monkeypatch.setattr(manager, "_try_enable_change_streams_locally", lambda: False)
    manager._realtime_auto_detect = True
    manager._realtime_enabled = True

    started = manager.start()

    assert started is False
    assert manager.is_running is False


def test_schedule_instant_sync_batches_rapid_requests(monkeypatch):
    manager = UnifiedSyncManagerV3(_FakeRepo(online=True))
    calls = []

    def _fake_delta_cycle():
        calls.append("delta")
        return {"success": True}

    monkeypatch.setattr(manager, "_run_delta_cycle", _fake_delta_cycle)

    first = manager.schedule_instant_sync("clients")
    second = manager.schedule_instant_sync("clients")

    assert first is True
    assert second is False  # deduped burst

    deadline = time.monotonic() + 1.5
    while manager._instant_sync_worker_running and time.monotonic() < deadline:
        time.sleep(0.01)

    assert calls == ["delta"]


def test_force_pull_single_table_prefers_targeted_reconcile(monkeypatch):
    manager = UnifiedSyncManagerV3(_FakeRepo(online=True))
    calls = []

    monkeypatch.setattr(
        manager,
        "_run_table_reconcile_cycle",
        lambda table: calls.append(("table", table)) or {"success": True},
    )
    monkeypatch.setattr(
        manager,
        "_run_delta_cycle",
        lambda: calls.append(("delta", None)) or {"success": True},
    )

    manager.force_pull("clients")

    deadline = time.monotonic() + 1.0
    while not calls and time.monotonic() < deadline:
        time.sleep(0.01)

    assert calls == [("table", "clients")]


def test_sync_pings_skip_notifications_table():
    repo = _FakeRepo(online=True)
    repo.mongo_db = _FakeMongoDB()
    manager = UnifiedSyncManagerV3(repo)

    manager._emit_sync_pings({"notifications", "clients"})

    inserted = repo.mongo_db["notifications"].inserted
    assert len(inserted) == 1
    assert inserted[0]["entity_type"] == "clients"


def test_realtime_queue_change_dedupes_burst(monkeypatch):
    manager = RealtimeSyncManager(_FakeRepo(online=True))
    scheduled = []

    monkeypatch.setattr(manager, "_schedule_emit_changes", lambda: scheduled.append("emit"))
    manager._event_dedupe_ms = 1000

    manager._queue_collection_change("clients")
    manager._queue_collection_change("clients")

    assert scheduled == ["emit"]
    with manager._pending_changes_lock:
        assert "clients" in manager._pending_changes
        assert manager._emit_dispatch_queued is True


def test_realtime_emit_slot_clears_pending_state():
    manager = RealtimeSyncManager(_FakeRepo(online=True))
    with manager._pending_changes_lock:
        manager._pending_changes.add("clients")
        manager._emit_dispatch_queued = True

    manager._emit_pending_changes_slot()

    with manager._pending_changes_lock:
        assert not manager._pending_changes
        assert manager._emit_dispatch_queued is False


def test_realtime_manager_attempts_service_fix_when_direct_bootstrap_fails(monkeypatch):
    repo = _FakeRepo(online=True)
    manager = RealtimeSyncManager(repo)
    manager._local_rs_bootstrap_enabled = True
    manager._local_service_replset_fix_enabled = True
    manager._local_rs_bootstrap_attempted = False
    manager._local_service_replset_fix_attempted = False
    service_fix_calls = []

    monkeypatch.setattr(
        realtime_mod,
        "try_bootstrap_local_replica_set",
        lambda *_args, **_kwargs: (False, "not running with --replset"),
    )
    monkeypatch.setattr(manager, "_get_current_mongo_uri", lambda: "mongodb://localhost:27017")
    monkeypatch.setattr(manager, "_is_windows_platform", lambda: True)
    monkeypatch.setattr(
        manager,
        "_start_local_service_replset_fix_background",
        lambda: service_fix_calls.append("started") or True,
    )

    assert manager._try_enable_change_streams_locally() is True
    assert service_fix_calls == ["started"]


def test_realtime_script_uses_configured_mongo_service_name(monkeypatch):
    manager = RealtimeSyncManager(_FakeRepo(online=True))
    manager._local_mongo_service_name = "MongoDB-7.0"
    manager._local_rs_name = "rs0"
    captured = {"cmd": None}

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(manager, "_is_windows_platform", lambda: True)
    monkeypatch.setattr(
        manager,
        "_resolve_local_replset_enabler_script",
        lambda: Path("tools/enable_local_replset.ps1"),
    )
    monkeypatch.setattr(
        realtime_mod.subprocess,
        "run",
        lambda cmd, **_kwargs: captured.update({"cmd": cmd}) or _Proc(),
    )

    assert manager._run_local_replset_enabler_script() is True
    assert captured["cmd"] is not None
    assert "-MongoServiceName" in captured["cmd"]
    assert "MongoDB-7.0" in captured["cmd"]


def test_realtime_service_fix_respects_cooldown(monkeypatch):
    repo = _FakeRepo(online=True)
    manager = RealtimeSyncManager(repo)
    manager._local_rs_bootstrap_enabled = False
    manager._local_service_replset_fix_enabled = True
    manager._local_service_replset_fix_cooldown_seconds = 3600
    manager._last_local_service_replset_fix_attempt_at = time.time()
    started = []

    monkeypatch.setattr(manager, "_get_current_mongo_uri", lambda: "mongodb://localhost:27017")
    monkeypatch.setattr(manager, "_is_windows_platform", lambda: True)
    monkeypatch.setattr(
        manager,
        "_start_local_service_replset_fix_background",
        lambda: started.append("started") or True,
    )

    assert manager._try_enable_change_streams_locally() is False
    assert started == []


def test_remote_replica_set_uri_auto_normalization(monkeypatch):
    repo = _FakeRepo(online=True)
    manager = RealtimeSyncManager(repo)
    persisted = []
    reconnected = []

    monkeypatch.setattr(
        manager,
        "_get_current_mongo_uri",
        lambda: "mongodb://mongo.example.com:27017/skywave_erp_db?authSource=skywave_erp_db",
    )
    monkeypatch.setattr(
        repo.mongo_client.admin,
        "command",
        lambda *_args, **_kwargs: {"ok": 1, "setName": "rs0"},
    )
    monkeypatch.setattr(manager, "_persist_runtime_mongo_uri", lambda uri: persisted.append(uri))
    monkeypatch.setattr(
        manager,
        "_reconnect_repository_client",
        lambda uri: reconnected.append(uri) or True,
    )

    assert manager._try_enable_change_streams_for_remote_replica_set() is True
    assert len(persisted) == 1
    assert "replicaSet=rs0" in persisted[0]
    assert "directConnection=false" in persisted[0]
    assert reconnected == persisted


def test_realtime_manager_rechecks_after_remote_uri_fix(monkeypatch):
    repo = _FakeRepo(online=True)
    manager = RealtimeSyncManager(repo)
    detect_calls = {"count": 0}

    def _fake_detect():
        detect_calls["count"] += 1
        return detect_calls["count"] >= 2

    monkeypatch.setattr(manager, "_detect_change_stream_support", _fake_detect)
    monkeypatch.setattr(manager, "_try_enable_change_streams_locally", lambda: False)
    monkeypatch.setattr(manager, "_try_enable_change_streams_for_remote_replica_set", lambda: True)
    monkeypatch.setattr(manager, "_start_unified_watcher", lambda: None)

    manager._realtime_auto_detect = True
    manager._realtime_enabled = True

    started = manager.start()

    assert started is True
    assert manager.is_running is True
    assert detect_calls["count"] == 2
