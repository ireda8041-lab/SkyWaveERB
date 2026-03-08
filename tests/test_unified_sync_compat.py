import sqlite3
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.realtime_sync as realtime_mod
import core.unified_sync as unified_sync_mod
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


def _matches_mongo_query(document: dict, query: dict | None) -> bool:
    if not query:
        return True
    if "$and" in query:
        return all(_matches_mongo_query(document, clause) for clause in query["$and"])
    if "$or" in query:
        return any(_matches_mongo_query(document, clause) for clause in query["$or"])

    for key, expected in query.items():
        if isinstance(expected, dict):
            if "$exists" in expected:
                exists = key in document
                if exists != bool(expected["$exists"]):
                    return False
            if "$ne" in expected and document.get(key) == expected["$ne"]:
                return False
            continue

        if document.get(key) != expected:
            return False

    return True


class _FakeUsersCollection:
    def __init__(self, records: list[dict] | None = None):
        self.documents = [dict(record) for record in (records or [])]
        self.inserted: list[dict] = []
        self.updated: list[tuple[dict, dict]] = []
        self._seq = len(self.documents)

    def find(self, query: dict | None = None):
        return [
            dict(document) for document in self.documents if _matches_mongo_query(document, query)
        ]

    def find_one(self, query: dict | None = None):
        for document in self.documents:
            if _matches_mongo_query(document, query):
                return dict(document)
        return None

    def insert_one(self, data: dict):
        self._seq += 1
        doc = dict(data)
        doc_id = str(doc.get("_id") or f"user-{self._seq}")
        doc["_id"] = doc_id
        self.documents.append(doc)
        self.inserted.append(dict(doc))
        return SimpleNamespace(inserted_id=doc_id)

    def update_one(self, filter_doc: dict, update_doc: dict, upsert: bool = False):
        self.updated.append((dict(filter_doc), dict(update_doc)))
        for index, document in enumerate(self.documents):
            if _matches_mongo_query(document, filter_doc):
                updated = dict(document)
                updated.update(update_doc.get("$set", {}))
                self.documents[index] = updated
                return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)

        if upsert:
            doc = dict(filter_doc)
            doc.update(update_doc.get("$set", {}))
            self._seq += 1
            doc_id = str(doc.get("_id") or f"user-{self._seq}")
            doc["_id"] = doc_id
            self.documents.append(doc)
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=doc_id)

        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)


class _FakeUserRepoWithSqlite:
    def __init__(self, db_path, remote_users: list[dict] | None = None):
        self.online = True
        self.mongo_client = _FakeMongoClient()
        self.sqlite_conn = sqlite3.connect(str(db_path))
        self.sqlite_conn.row_factory = sqlite3.Row
        self.mongo_db = SimpleNamespace(users=_FakeUsersCollection(remote_users or []))
        self._create_tables()

    def _create_tables(self):
        cur = self.sqlite_conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                _mongo_id TEXT,
                username TEXT,
                full_name TEXT,
                email TEXT,
                role TEXT,
                password_hash TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                last_login TEXT,
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


class _FakeNotificationRepoWithSqlite:
    def __init__(self, db_path):
        self.online = True
        self.mongo_client = _FakeMongoClient()
        self.sqlite_conn = sqlite3.connect(str(db_path))
        self.sqlite_conn.row_factory = sqlite3.Row
        self.mongo_db = _FakeMongoDB()
        self.mongo_db["notifications"] = _FakeCollection([])
        self._create_tables()

    def _create_tables(self):
        cur = self.sqlite_conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                _mongo_id TEXT,
                title TEXT,
                message TEXT,
                type TEXT,
                priority TEXT,
                is_read INTEGER DEFAULT 0,
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


class _FakeProjectPaymentRepoWithSqlite:
    def __init__(self, db_path):
        self.online = True
        self.mongo_client = _FakeMongoClient()
        self.sqlite_conn = sqlite3.connect(str(db_path))
        self.sqlite_conn.row_factory = sqlite3.Row
        self.mongo_db = _FakeMongoDB()
        self.mongo_db["payments"] = _FakeCollection([])
        self._create_tables()

    def _create_tables(self):
        cur = self.sqlite_conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                _mongo_id TEXT,
                name TEXT,
                client_id TEXT,
                created_at TEXT,
                last_modified TEXT,
                sync_status TEXT,
                dirty_flag INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                _mongo_id TEXT,
                project_id TEXT,
                client_id TEXT,
                date TEXT,
                amount REAL,
                account_id TEXT,
                method TEXT,
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

    def _resolve_project_target_row(self, project_ref, client_id: str = ""):
        reference = str(project_ref or "").strip()
        if not reference:
            return None

        rows = [
            dict(row)
            for row in self.sqlite_conn.execute(
                """
                SELECT id, _mongo_id, name, client_id
                FROM projects
                WHERE (is_deleted = 0 OR is_deleted IS NULL)
                """
            ).fetchall()
        ]
        for row in rows:
            if client_id and str(row.get("client_id") or "").strip() != str(client_id).strip():
                continue
            if reference in {
                str(row.get("id") or "").strip(),
                str(row.get("_mongo_id") or "").strip(),
                str(row.get("name") or "").strip(),
            }:
                return row
        return None

    @staticmethod
    def _stable_project_reference(project_row, fallback: str = "") -> str:
        if project_row:
            for field in ("_mongo_id", "id", "name"):
                value = str(project_row.get(field) or "").strip()
                if value:
                    return value
        return str(fallback or "").strip()


class _FakeTaskRepoWithSqlite:
    def __init__(self, db_path, remote_tasks: list[dict] | None = None):
        self.online = True
        self.mongo_client = _FakeMongoClient()
        self.sqlite_conn = sqlite3.connect(str(db_path))
        self.sqlite_conn.row_factory = sqlite3.Row
        self.mongo_db = _FakeMongoDB()
        self.mongo_db["tasks"] = _FakeCollection(remote_tasks or [])
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                _mongo_id TEXT,
                name TEXT,
                client_id TEXT,
                created_at TEXT,
                last_modified TEXT,
                sync_status TEXT,
                dirty_flag INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                _mongo_id TEXT,
                title TEXT,
                description TEXT,
                priority TEXT DEFAULT 'MEDIUM',
                status TEXT DEFAULT 'TODO',
                category TEXT DEFAULT 'GENERAL',
                due_date TEXT,
                due_time TEXT,
                completed_at TEXT,
                related_project_id TEXT,
                related_client_id TEXT,
                tags TEXT,
                reminder INTEGER DEFAULT 0,
                reminder_minutes INTEGER DEFAULT 30,
                assigned_to TEXT,
                is_archived INTEGER DEFAULT 0,
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

    def _client_aliases(self, client_ref: str) -> set[str]:
        reference = str(client_ref or "").strip()
        if not reference:
            return set()
        row = self.sqlite_conn.execute(
            """
            SELECT id, _mongo_id, name
            FROM clients
            WHERE (is_deleted = 0 OR is_deleted IS NULL)
              AND (id = ? OR _mongo_id = ? OR name = ?)
            """,
            (reference, reference, reference),
        ).fetchone()
        aliases = {reference}
        if row:
            aliases.update(
                {
                    str(row["id"] or "").strip(),
                    str(row["_mongo_id"] or "").strip(),
                    str(row["name"] or "").strip(),
                }
            )
        return {alias for alias in aliases if alias}

    def _resolve_project_target_row(self, project_ref, client_id: str = ""):
        reference = str(project_ref or "").strip()
        if not reference:
            return None

        client_aliases = self._client_aliases(client_id)
        rows = [
            dict(row)
            for row in self.sqlite_conn.execute(
                """
                SELECT id, _mongo_id, name, client_id
                FROM projects
                WHERE (is_deleted = 0 OR is_deleted IS NULL)
                """
            ).fetchall()
        ]
        for row in rows:
            if client_aliases and str(row.get("client_id") or "").strip() not in client_aliases:
                continue
            if reference in {
                str(row.get("id") or "").strip(),
                str(row.get("_mongo_id") or "").strip(),
                str(row.get("name") or "").strip(),
            }:
                return row
        return None

    @staticmethod
    def _stable_project_reference(project_row, fallback: str = "") -> str:
        if project_row:
            for field in ("_mongo_id", "id", "name"):
                value = str(project_row.get(field) or "").strip()
                if value:
                    return value
        return str(fallback or "").strip()

    def _normalize_client_reference(self, client_ref: str) -> str:
        reference = str(client_ref or "").strip()
        if not reference:
            return ""
        row = self.sqlite_conn.execute(
            """
            SELECT id, _mongo_id, name
            FROM clients
            WHERE (is_deleted = 0 OR is_deleted IS NULL)
              AND (id = ? OR _mongo_id = ? OR name = ?)
            LIMIT 1
            """,
            (reference, reference, reference),
        ).fetchone()
        if row:
            return (
                str(row["_mongo_id"] or "").strip()
                or str(row["id"] or "").strip()
                or str(row["name"] or "").strip()
            )
        return reference

    def _normalize_related_client_ref(self, client_ref: str) -> str | None:
        reference = str(client_ref or "").strip()
        if not reference:
            return None
        row = self.sqlite_conn.execute(
            """
            SELECT id
            FROM clients
            WHERE (is_deleted = 0 OR is_deleted IS NULL)
              AND (id = ? OR _mongo_id = ? OR name = ?)
            LIMIT 1
            """,
            (reference, reference, reference),
        ).fetchone()
        if not row:
            return None
        return str(row["id"] or "").strip() or None


class _FakeQuotationRepoWithSqlite:
    def __init__(self, db_path, remote_quotations: list[dict] | None = None):
        self.online = True
        self.mongo_client = _FakeMongoClient()
        self.sqlite_conn = sqlite3.connect(str(db_path))
        self.sqlite_conn.row_factory = sqlite3.Row
        self.mongo_db = _FakeMongoDB()
        self.mongo_db["quotations"] = _FakeCollection(remote_quotations or [])
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS quotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                _mongo_id TEXT,
                quotation_number TEXT,
                client_id TEXT NOT NULL,
                client_name TEXT,
                issue_date TEXT,
                valid_until TEXT,
                title TEXT,
                description TEXT,
                scope_of_work TEXT,
                items TEXT,
                subtotal REAL DEFAULT 0.0,
                discount_rate REAL DEFAULT 0.0,
                discount_amount REAL DEFAULT 0.0,
                tax_rate REAL DEFAULT 0.0,
                tax_amount REAL DEFAULT 0.0,
                total_amount REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'EGP',
                status TEXT DEFAULT 'مسودة',
                terms_and_conditions TEXT,
                payment_terms TEXT,
                delivery_time TEXT,
                warranty TEXT,
                notes TEXT,
                internal_notes TEXT,
                converted_to_project_id TEXT,
                conversion_date TEXT,
                sent_date TEXT,
                viewed_date TEXT,
                response_date TEXT,
                created_at TEXT,
                last_modified TEXT,
                sync_status TEXT,
                dirty_flag INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                _mongo_id TEXT,
                name TEXT,
                client_id TEXT,
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

    def _normalize_client_reference(self, client_ref: str) -> str:
        reference = str(client_ref or "").strip()
        if not reference:
            return ""
        row = self.sqlite_conn.execute(
            """
            SELECT id, _mongo_id, name
            FROM clients
            WHERE (is_deleted = 0 OR is_deleted IS NULL)
              AND (id = ? OR _mongo_id = ? OR name = ?)
            LIMIT 1
            """,
            (reference, reference, reference),
        ).fetchone()
        if row:
            return (
                str(row["_mongo_id"] or "").strip()
                or str(row["id"] or "").strip()
                or str(row["name"] or "").strip()
            )
        return reference

    def _normalize_local_client_reference(self, client_ref: str) -> str | None:
        reference = str(client_ref or "").strip()
        if not reference:
            return None
        row = self.sqlite_conn.execute(
            """
            SELECT id
            FROM clients
            WHERE (is_deleted = 0 OR is_deleted IS NULL)
              AND (id = ? OR _mongo_id = ? OR name = ?)
            LIMIT 1
            """,
            (reference, reference, reference),
        ).fetchone()
        if not row:
            return None
        return str(row["id"] or "").strip() or None

    def _client_aliases(self, client_ref: str) -> set[str]:
        reference = str(client_ref or "").strip()
        if not reference:
            return set()
        row = self.sqlite_conn.execute(
            """
            SELECT id, _mongo_id, name
            FROM clients
            WHERE (is_deleted = 0 OR is_deleted IS NULL)
              AND (id = ? OR _mongo_id = ? OR name = ?)
            LIMIT 1
            """,
            (reference, reference, reference),
        ).fetchone()
        aliases = {reference}
        if row:
            aliases.update(
                {
                    str(row["id"] or "").strip(),
                    str(row["_mongo_id"] or "").strip(),
                    str(row["name"] or "").strip(),
                }
            )
        return {alias for alias in aliases if alias}

    def _resolve_project_target_row(self, project_ref, client_id: str = ""):
        reference = str(project_ref or "").strip()
        if not reference:
            return None
        client_aliases = self._client_aliases(client_id)
        rows = [
            dict(row)
            for row in self.sqlite_conn.execute(
                """
                SELECT id, _mongo_id, name, client_id
                FROM projects
                WHERE (is_deleted = 0 OR is_deleted IS NULL)
                """
            ).fetchall()
        ]
        for row in rows:
            if client_aliases and str(row.get("client_id") or "").strip() not in client_aliases:
                continue
            if reference in {
                str(row.get("id") or "").strip(),
                str(row.get("_mongo_id") or "").strip(),
                str(row.get("name") or "").strip(),
            }:
                return row
        return None

    @staticmethod
    def _stable_project_reference(project_row, fallback: str = "") -> str:
        if project_row:
            for field in ("_mongo_id", "id", "name"):
                value = str(project_row.get(field) or "").strip()
                if value:
                    return value
        return str(fallback or "").strip()


def test_sqlite_identifier_guards_block_invalid_table_and_column_names(tmp_path):
    repo = _FakeRepoWithSqlite(db_path=tmp_path / "guarded_sync.db", remote_clients=[])
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["clients"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (name, created_at, last_modified, sync_status, dirty_flag, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("Guarded Client", "2026-02-09T10:00:00", "2026-02-09T10:05:00", "synced", 0, 0),
    )
    repo.sqlite_conn.commit()

    with pytest.raises(ValueError):
        manager._sqlite_table_columns(cursor, 'clients"; DROP TABLE clients; --')

    with pytest.raises(ValueError):
        manager._should_update_local_record(
            cursor,
            "clients",
            1,
            {"name": "Guarded Client", 'name"; DROP TABLE clients; --': "boom"},
        )


def test_get_sync_status_counts_rows_for_validated_tables(tmp_path):
    repo = _FakeRepoWithSqlite(db_path=tmp_path / "sync_status.db", remote_clients=[])
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["clients"]

    cursor = repo.sqlite_conn.cursor()
    cursor.executemany(
        """
        INSERT INTO clients (name, created_at, last_modified, sync_status, dirty_flag, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("Synced Client", "2026-02-09T10:00:00", "2026-02-09T10:05:00", "synced", 0, 0),
            ("Pending Client", "2026-02-09T10:10:00", "2026-02-09T10:15:00", "pending", 1, 0),
        ],
    )
    repo.sqlite_conn.commit()

    status = manager.get_sync_status()

    assert status["tables"]["clients"] == {"total": 2, "pending": 1, "synced": 1}


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


def test_run_full_sync_async_deduplicates_in_flight_workers(monkeypatch):
    manager = UnifiedSyncManagerV3(_FakeRepo(online=True))
    sync_calls = []
    started_targets = []

    class _FakeThread:
        def __init__(self, target=None, **_kwargs):
            self._target = target

        def start(self):
            started_targets.append(self._target)

    monkeypatch.setattr(unified_sync_mod.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        manager,
        "full_sync_from_cloud",
        lambda: sync_calls.append("sync") or {"success": True},
    )

    assert manager._run_full_sync_async(source="initial") is True
    assert manager._run_full_sync_async(source="initial") is False
    assert sync_calls == []
    assert len(started_targets) == 1

    started_targets[0]()

    assert sync_calls == ["sync"]
    assert manager._full_sync_thread_in_flight is False
    assert manager._run_full_sync_async(source="initial") is True
    assert len(started_targets) == 2


def test_initial_sync_delegates_to_dispatcher(monkeypatch):
    manager = UnifiedSyncManagerV3(_FakeRepo(online=True))
    requested_sources = []

    monkeypatch.setattr(
        manager,
        "_run_full_sync_async",
        lambda source="background": requested_sources.append(source) or False,
    )

    manager._initial_sync()

    assert requested_sources == ["initial"]


def test_sync_users_from_cloud_revives_deleted_remote_tombstone_on_upload(tmp_path):
    repo = _FakeUserRepoWithSqlite(
        tmp_path / "users_sync_upload.db",
        remote_users=[
            {
                "_id": "mongo-user-sync-1",
                "username": "sync-user",
                "password_hash": "hash-old",
                "role": "admin",
                "is_active": True,
                "full_name": "Deleted Cloud User",
                "email": "deleted@example.com",
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ],
    )
    manager = UnifiedSyncManagerV3(repo)

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (
            _mongo_id, username, full_name, email, role, password_hash,
            is_active, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            "sync-user",
            "Local Sync User",
            "local@example.com",
            "admin",
            "hash-local",
            1,
            "2026-03-07T09:00:00",
            "2026-03-07T09:05:00",
            "modified_offline",
            1,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    manager._sync_users_from_cloud()

    row = repo.sqlite_conn.execute(
        "SELECT _mongo_id, sync_status, dirty_flag, is_deleted FROM users WHERE username = ?",
        ("sync-user",),
    ).fetchone()
    remote = repo.mongo_db.users.documents[0]

    assert row is not None
    assert row["_mongo_id"] == "mongo-user-sync-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert remote["full_name"] == "Local Sync User"
    assert remote["email"] == "local@example.com"
    assert remote["sync_status"] == "synced"
    assert remote["is_deleted"] is False


def test_sync_users_from_cloud_marks_deleted_remote_user_locally(tmp_path):
    repo = _FakeUserRepoWithSqlite(
        tmp_path / "users_sync_pull_deleted.db",
        remote_users=[
            {
                "_id": "mongo-user-deleted-1",
                "username": "deleted-user",
                "password_hash": "hash-remote",
                "role": "admin",
                "is_active": True,
                "full_name": "Deleted In Cloud",
                "email": "deleted@example.com",
                "sync_status": "deleted",
                "is_deleted": True,
                "last_modified": datetime(2026, 3, 7, 10, 15, 0),
            }
        ],
    )
    manager = UnifiedSyncManagerV3(repo)

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (
            _mongo_id, username, full_name, email, role, password_hash,
            is_active, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-user-deleted-1",
            "deleted-user",
            "Visible Before Sync",
            "visible@example.com",
            "admin",
            "hash-local",
            1,
            "2026-03-07T09:00:00",
            "2026-03-07T09:05:00",
            "synced",
            0,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    manager._sync_users_from_cloud()

    row = repo.sqlite_conn.execute(
        "SELECT sync_status, dirty_flag, is_deleted, last_modified FROM users WHERE username = ?",
        ("deleted-user",),
    ).fetchone()

    assert row is not None
    assert row["sync_status"] == "deleted"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 1
    assert row["last_modified"] == "2026-03-07T10:15:00"


def test_sync_users_from_cloud_skips_when_users_collection_missing(tmp_path):
    repo = _FakeUserRepoWithSqlite(tmp_path / "users_sync_missing_collection.db", remote_users=[])
    repo.mongo_db = None
    manager = UnifiedSyncManagerV3(repo)

    manager._sync_users_from_cloud()

    row = repo.sqlite_conn.execute("SELECT COUNT(*) FROM users").fetchone()
    assert row[0] == 0


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


def test_pull_remote_changes_does_not_resurrect_locally_deleted_rows(tmp_path):
    ts = datetime(2026, 2, 9, 12, 50, 0)
    repo = _FakeRepoWithSqlite(
        db_path=tmp_path / "sync_pull_deleted_local.db",
        remote_clients=[
            {
                "_id": "mongo-client-deleted-local",
                "name": "Deleted Local",
                "created_at": ts,
                "last_modified": ts,
                "is_deleted": False,
            }
        ],
    )
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["clients"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (_mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-client-deleted-local",
            "Deleted Local",
            "2026-02-09T10:00:00",
            "2026-02-09T10:05:00",
            "deleted",
            1,
            1,
        ),
    )
    repo.sqlite_conn.commit()

    result = manager.pull_remote_changes()

    assert result["success"] is True
    assert result["pulled"] == 0

    cursor.execute(
        "SELECT sync_status, dirty_flag, is_deleted FROM clients WHERE _mongo_id = ?",
        ("mongo-client-deleted-local",),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["sync_status"] == "deleted"
    assert row["dirty_flag"] == 1
    assert row["is_deleted"] == 1


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


def test_sync_single_table_to_cloud_removes_local_deleted_rows(tmp_path):
    repo = _FakeRepoWithSqlite(db_path=tmp_path / "sync_realtime_deleted.db", remote_clients=[])
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["clients"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (_mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-client-rt-delete",
            "Realtime Delete",
            "2026-02-09T10:00:00",
            "2026-02-09T10:05:00",
            "deleted",
            1,
            1,
        ),
    )
    repo.sqlite_conn.commit()

    manager._sync_single_table_to_cloud("clients")

    local = repo.sqlite_conn.cursor()
    local.execute("SELECT COUNT(*) FROM clients WHERE name = ?", ("Realtime Delete",))
    assert local.fetchone()[0] == 0
    assert len(repo.mongo_db["clients"].updated) >= 1


def test_sync_table_from_cloud_does_not_resurrect_locally_deleted_rows(tmp_path):
    ts = datetime(2026, 2, 9, 12, 55, 0)
    repo = _FakeRepoWithSqlite(
        db_path=tmp_path / "sync_full_deleted_local.db",
        remote_clients=[
            {
                "_id": "mongo-client-full-sync-deleted-local",
                "name": "Deleted In Full Sync",
                "created_at": ts,
                "last_modified": ts,
                "is_deleted": False,
            }
        ],
    )
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["clients"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (_mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-client-full-sync-deleted-local",
            "Deleted In Full Sync",
            "2026-02-09T10:00:00",
            "2026-02-09T10:05:00",
            "deleted",
            1,
            1,
        ),
    )
    repo.sqlite_conn.commit()

    stats = manager._sync_table_from_cloud("clients")

    assert stats["updated"] == 0

    cursor.execute(
        "SELECT sync_status, dirty_flag, is_deleted FROM clients WHERE _mongo_id = ?",
        ("mongo-client-full-sync-deleted-local",),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["sync_status"] == "deleted"
    assert row["dirty_flag"] == 1
    assert row["is_deleted"] == 1


def test_push_pending_changes_uses_main_push_logic(tmp_path):
    repo = _FakeRepoWithSqlite(db_path=tmp_path / "sync_pending_deleted.db", remote_clients=[])
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["clients"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (_mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-client-pending-delete",
            "Pending Delete",
            "2026-02-09T10:00:00",
            "2026-02-09T10:05:00",
            "deleted",
            1,
            1,
        ),
    )
    repo.sqlite_conn.commit()

    manager._push_pending_changes()

    local = repo.sqlite_conn.cursor()
    local.execute("SELECT COUNT(*) FROM clients WHERE name = ?", ("Pending Delete",))
    assert local.fetchone()[0] == 0
    assert len(repo.mongo_db["clients"].updated) >= 1


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


def test_notification_sync_filter_excludes_transport_only_and_legacy_toasts():
    query = UnifiedSyncManagerV3._merge_query_with_notification_filter({})

    assert {
        "$or": [{"transport_only": {"$exists": False}}, {"transport_only": {"$ne": True}}]
    } in query["$and"]
    assert {
        "$or": [
            {"device_id": {"$exists": False}},
            {"last_modified": {"$exists": True}},
            {"priority": {"$exists": True}},
        ]
    } in query["$and"]


def test_push_local_notification_changes_include_device_id(tmp_path):
    repo = _FakeNotificationRepoWithSqlite(tmp_path / "notifications_push.db")
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["notifications"]
    manager._device_id = "DEVICE-LOCAL"

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO notifications (
            _mongo_id, title, message, type, priority, is_read,
            created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            "Offline Notification",
            "Created while offline",
            "معلومة",
            "متوسطة",
            0,
            "2026-03-07T10:00:00",
            "2026-03-07T10:05:00",
            "new_offline",
            1,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    result = manager.push_local_changes()

    row = repo.sqlite_conn.execute(
        "SELECT _mongo_id, sync_status, dirty_flag FROM notifications"
    ).fetchone()
    inserted = repo.mongo_db["notifications"].inserted

    assert result["success"] is True
    assert result["pushed"] == 1
    assert inserted[0]["device_id"] == "DEVICE-LOCAL"
    assert row["_mongo_id"] == "fake-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0


def test_push_local_payment_changes_normalize_project_reference_to_mongo_id(tmp_path):
    repo = _FakeProjectPaymentRepoWithSqlite(tmp_path / "payments_push.db")
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["payments"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO projects (
            _mongo_id, name, client_id, created_at, last_modified,
            sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-project-1",
            "Cross Device Project",
            "CLIENT-100",
            "2026-03-07T09:00:00",
            "2026-03-07T09:05:00",
            "synced",
            0,
            0,
        ),
    )
    project_local_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO payments (
            _mongo_id, project_id, client_id, date, amount, account_id, method,
            created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            str(project_local_id),
            "CLIENT-100",
            "2026-03-07T10:00:00",
            850.0,
            "1101",
            "Cash",
            "2026-03-07T10:00:00",
            "2026-03-07T10:05:00",
            "modified_offline",
            1,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    result = manager.push_local_changes()

    row = repo.sqlite_conn.execute(
        "SELECT project_id, _mongo_id, sync_status, dirty_flag FROM payments"
    ).fetchone()
    inserted = repo.mongo_db["payments"].inserted

    assert result["success"] is True
    assert result["pushed"] == 1
    assert inserted[0]["project_id"] == "mongo-project-1"
    assert row["project_id"] == "mongo-project-1"
    assert row["_mongo_id"] == "fake-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0


def test_push_local_task_changes_normalize_client_reference_only_for_cloud(tmp_path):
    repo = _FakeTaskRepoWithSqlite(tmp_path / "tasks_push.db")
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["tasks"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (
            _mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-client-1",
            "Task Sync Client",
            "2026-03-07T09:00:00",
            "2026-03-07T09:05:00",
            "synced",
            0,
            0,
        ),
    )
    client_local_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO projects (
            _mongo_id, name, client_id, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-project-1",
            "Task Sync Project",
            "mongo-client-1",
            "2026-03-07T09:10:00",
            "2026-03-07T09:15:00",
            "synced",
            0,
            0,
        ),
    )
    project_local_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO tasks (
            _mongo_id, title, priority, status, category, related_project_id, related_client_id,
            tags, reminder, reminder_minutes, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            "Offline Task Link",
            "MEDIUM",
            "TODO",
            "GENERAL",
            str(project_local_id),
            str(client_local_id),
            "[]",
            0,
            30,
            "2026-03-07T10:00:00",
            "2026-03-07T10:05:00",
            "modified_offline",
            1,
            0,
        ),
    )
    task_local_id = cursor.lastrowid
    repo.sqlite_conn.commit()

    result = manager.push_local_changes()

    row = repo.sqlite_conn.execute(
        "SELECT related_project_id, related_client_id, _mongo_id, sync_status, dirty_flag FROM tasks WHERE id = ?",
        (task_local_id,),
    ).fetchone()
    inserted = repo.mongo_db["tasks"].inserted

    assert result["success"] is True
    assert result["pushed"] == 1
    assert inserted[0]["related_project_id"] == "mongo-project-1"
    assert inserted[0]["related_client_id"] == "mongo-client-1"
    assert row["related_project_id"] == "mongo-project-1"
    assert row["related_client_id"] == str(client_local_id)
    assert row["_mongo_id"] == "fake-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0


def test_pull_remote_task_changes_restore_local_client_fk(tmp_path):
    ts = datetime(2026, 3, 7, 11, 30, 0)
    repo = _FakeTaskRepoWithSqlite(
        tmp_path / "tasks_pull.db",
        remote_tasks=[
            {
                "_id": "mongo-task-1",
                "title": "Remote Task Link",
                "description": None,
                "priority": "MEDIUM",
                "status": "TODO",
                "category": "GENERAL",
                "related_project_id": "mongo-project-1",
                "related_client_id": "mongo-client-1",
                "tags": [],
                "reminder": 0,
                "reminder_minutes": 30,
                "created_at": ts,
                "last_modified": ts,
                "is_deleted": False,
            }
        ],
    )
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["tasks"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (
            _mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-client-1",
            "Task Pull Client",
            "2026-03-07T09:00:00",
            "2026-03-07T09:05:00",
            "synced",
            0,
            0,
        ),
    )
    client_local_id = cursor.lastrowid
    repo.sqlite_conn.commit()

    result = manager.pull_remote_changes()

    row = repo.sqlite_conn.execute(
        "SELECT _mongo_id, related_client_id, sync_status, dirty_flag FROM tasks"
    ).fetchone()

    assert result["success"] is True
    assert result["pulled"] == 1
    assert row["_mongo_id"] == "mongo-task-1"
    assert row["related_client_id"] == str(client_local_id)
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0


def test_push_local_quotation_changes_normalize_client_reference_only_for_cloud(tmp_path):
    repo = _FakeQuotationRepoWithSqlite(tmp_path / "quotations_push.db")
    manager = UnifiedSyncManagerV3(repo)

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (
            _mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-quotation-client-1",
            "Quotation Sync Client",
            "2026-03-07T09:00:00",
            "2026-03-07T09:05:00",
            "synced",
            0,
            0,
        ),
    )
    client_local_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO quotations (
            _mongo_id, quotation_number, client_id, client_name, issue_date, valid_until,
            title, description, scope_of_work, items, subtotal, total_amount, currency,
            status, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            "QT-2026-PUSH-0001",
            str(client_local_id),
            "Quotation Sync Client",
            "2026-03-07T10:00:00",
            "2026-03-14T10:00:00",
            "Offline quotation",
            "",
            "",
            "[]",
            500.0,
            500.0,
            "EGP",
            "مسودة",
            "2026-03-07T10:00:00",
            "2026-03-07T10:05:00",
            "modified_offline",
            1,
            0,
        ),
    )
    quotation_local_id = cursor.lastrowid
    repo.sqlite_conn.commit()

    result = manager.push_local_changes()

    row = repo.sqlite_conn.execute(
        "SELECT client_id, _mongo_id, sync_status, dirty_flag FROM quotations WHERE id = ?",
        (quotation_local_id,),
    ).fetchone()
    inserted = repo.mongo_db["quotations"].inserted

    assert result["success"] is True
    assert result["pushed"] == 1
    assert inserted[0]["client_id"] == "mongo-quotation-client-1"
    assert row["client_id"] == str(client_local_id)
    assert row["_mongo_id"] == "fake-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0


def test_pull_remote_quotation_changes_restore_local_client_fk_and_dates(tmp_path):
    issue_ts = datetime(2026, 3, 7, 12, 0, 0)
    valid_until_ts = datetime(2026, 3, 14, 12, 0, 0)
    repo = _FakeQuotationRepoWithSqlite(
        tmp_path / "quotations_pull.db",
        remote_quotations=[
            {
                "_id": "mongo-quotation-1",
                "quotation_number": "QT-2026-PULL-0001",
                "client_id": "mongo-quotation-client-1",
                "client_name": "Quotation Pull Client",
                "issue_date": issue_ts,
                "valid_until": valid_until_ts,
                "title": "Remote quotation",
                "description": "",
                "scope_of_work": "",
                "items": [],
                "subtotal": 700.0,
                "discount_rate": 0.0,
                "discount_amount": 0.0,
                "tax_rate": 0.0,
                "tax_amount": 0.0,
                "total_amount": 700.0,
                "currency": "EGP",
                "status": "مسودة",
                "created_at": issue_ts,
                "last_modified": issue_ts,
                "is_deleted": False,
            }
        ],
    )
    manager = UnifiedSyncManagerV3(repo)

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (
            _mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-quotation-client-1",
            "Quotation Pull Client",
            "2026-03-07T09:00:00",
            "2026-03-07T09:05:00",
            "synced",
            0,
            0,
        ),
    )
    client_local_id = cursor.lastrowid
    repo.sqlite_conn.commit()

    result = manager.pull_remote_changes()

    row = repo.sqlite_conn.execute(
        "SELECT _mongo_id, client_id, issue_date, valid_until, items, sync_status, dirty_flag FROM quotations"
    ).fetchone()

    assert result["success"] is True
    assert result["pulled"] == 1
    assert row["_mongo_id"] == "mongo-quotation-1"
    assert row["client_id"] == str(client_local_id)
    assert row["issue_date"] == issue_ts.isoformat()
    assert row["valid_until"] == valid_until_ts.isoformat()
    assert row["items"] == "[]"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0


def test_push_local_quotation_conversion_normalizes_project_reference(tmp_path):
    repo = _FakeQuotationRepoWithSqlite(tmp_path / "quotations_project_push.db")
    manager = UnifiedSyncManagerV3(repo)

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (
            _mongo_id, name, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-quotation-client-2",
            "Quotation Project Client",
            "2026-03-07T09:00:00",
            "2026-03-07T09:05:00",
            "synced",
            0,
            0,
        ),
    )
    client_local_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO projects (
            _mongo_id, name, client_id, created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-quotation-project-2",
            "Quotation Project",
            "mongo-quotation-client-2",
            "2026-03-07T09:10:00",
            "2026-03-07T09:15:00",
            "synced",
            0,
            0,
        ),
    )
    project_local_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO quotations (
            _mongo_id, quotation_number, client_id, client_name, issue_date, valid_until,
            title, description, scope_of_work, items, subtotal, total_amount, currency,
            status, converted_to_project_id, conversion_date,
            created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            "QT-2026-PUSH-0002",
            str(client_local_id),
            "Quotation Project Client",
            "2026-03-07T10:00:00",
            "2026-03-14T10:00:00",
            "Converted quotation",
            "",
            "",
            "[]",
            500.0,
            500.0,
            "EGP",
            "تم التحويل لمشروع",
            str(project_local_id),
            "2026-03-07T10:30:00",
            "2026-03-07T10:00:00",
            "2026-03-07T10:35:00",
            "modified_offline",
            1,
            0,
        ),
    )
    quotation_local_id = cursor.lastrowid
    repo.sqlite_conn.commit()

    result = manager.push_local_changes()

    row = repo.sqlite_conn.execute(
        "SELECT client_id, converted_to_project_id, _mongo_id, sync_status, dirty_flag FROM quotations WHERE id = ?",
        (quotation_local_id,),
    ).fetchone()
    inserted = repo.mongo_db["quotations"].inserted

    assert result["success"] is True
    assert result["pushed"] == 1
    assert inserted[0]["client_id"] == "mongo-quotation-client-2"
    assert inserted[0]["converted_to_project_id"] == "mongo-quotation-project-2"
    assert row["client_id"] == str(client_local_id)
    assert row["converted_to_project_id"] == "mongo-quotation-project-2"
    assert row["_mongo_id"] == "fake-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0


def test_find_local_record_for_notifications_ignores_local_id_collisions(tmp_path):
    repo = _FakeNotificationRepoWithSqlite(tmp_path / "notifications_pull.db")
    manager = UnifiedSyncManagerV3(repo)
    manager.TABLES = ["notifications"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO notifications (
            title, message, type, priority, is_read,
            created_at, last_modified, sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Local Notification",
            "Existing row",
            "معلومة",
            "متوسطة",
            0,
            "2026-03-07T11:00:00",
            "2026-03-07T11:05:00",
            "synced",
            0,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    table_columns = manager._sqlite_table_columns(cursor, "notifications")
    local_id = manager._find_local_record(
        cursor,
        "notifications",
        "mongo-remote-1",
        "id",
        1,
        table_columns,
    )

    assert local_id is None


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
