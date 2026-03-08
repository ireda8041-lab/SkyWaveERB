from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from bson import ObjectId

from core import schemas
from core.auth_models import AuthService, User, UserRole


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    import core.repository as repo_mod

    db_path = tmp_path / "repo_soft_delete_guards.db"
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


def _create_project(repo, name: str, client_id: str = "CL-1") -> schemas.Project:
    return repo.create_project(schemas.Project(name=name, client_id=client_id, total_amount=1000.0))


def _create_invoice(repo, project: schemas.Project, invoice_number: str) -> schemas.Invoice:
    return repo.create_invoice(
        schemas.Invoice(
            invoice_number=invoice_number,
            client_id=project.client_id,
            project_id=project.name,
            issue_date=datetime(2026, 2, 27, 10, 0, 0),
            due_date=datetime(2026, 3, 6, 10, 0, 0),
            items=[],
            subtotal=500.0,
            total_amount=500.0,
        )
    )


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


class _FakeMongoCursor(list):
    def sort(self, fields, direction=None):
        items = list(self)
        if isinstance(fields, str):
            fields = [(fields, -1 if direction is None else direction)]
        for key, sort_direction in reversed(fields):
            items.sort(key=lambda item: item.get(key), reverse=sort_direction < 0)
        return _FakeMongoCursor(items)


class _FakeMongoCollection:
    def __init__(
        self,
        documents: list[dict],
        duplicate_insert_codes: set[str] | None = None,
        duplicate_insert_names: set[str] | None = None,
    ):
        self.documents = [dict(document) for document in documents]
        self.duplicate_insert_codes = set(duplicate_insert_codes or set())
        self.duplicate_insert_names = set(duplicate_insert_names or set())

    def find(self, query: dict | None = None):
        return _FakeMongoCursor(
            [dict(document) for document in self.documents if _matches_mongo_query(document, query)]
        )

    def find_one(self, query: dict | None = None):
        for document in self.documents:
            if _matches_mongo_query(document, query):
                return dict(document)
        return None

    def insert_one(self, document: dict):
        code = str(document.get("code") or "").strip()
        name = str(document.get("name") or "").strip()
        if code and code in self.duplicate_insert_codes:
            raise RuntimeError("E11000 duplicate key error collection: accounts index: code_1")
        if name and name in self.duplicate_insert_names:
            raise RuntimeError("E11000 duplicate key error collection: services index: name_1")

        inserted = dict(document)
        inserted.setdefault("_id", f"inserted-{len(self.documents) + 1}")
        self.documents.append(inserted)
        return SimpleNamespace(inserted_id=inserted["_id"])

    def update_one(self, query: dict, update: dict, upsert: bool = False):
        for index, document in enumerate(self.documents):
            if _matches_mongo_query(document, query):
                updated_document = dict(document)
                updated_document.update(update.get("$set", {}))
                self.documents[index] = updated_document
                return SimpleNamespace(matched_count=1, modified_count=1)
        if upsert:
            inserted = dict(query)
            inserted.update(update.get("$set", {}))
            inserted.setdefault("_id", f"upserted-{len(self.documents) + 1}")
            self.documents.append(inserted)
            return SimpleNamespace(
                matched_count=0,
                modified_count=0,
                upserted_id=inserted["_id"],
            )
        return SimpleNamespace(matched_count=0, modified_count=0)


def test_soft_deleted_entity_lookups_are_hidden(repo):
    client = repo.create_client(schemas.Client(name="Soft Delete Client", phone="01010000001"))
    service = repo.create_service(schemas.Service(name="Soft Delete Service", default_price=99.0))
    project = _create_project(repo, "Soft Delete Lookup Project", client_id=str(client.id))

    payment = repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 27, 11, 0, 0),
            amount=120.0,
            account_id="1101",
            method="Cash",
        )
    )
    expense = repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 27, 12, 0, 0),
            category="Operations",
            amount=45.0,
            description="printer",
            account_id="5001",
            payment_account_id="1101",
        )
    )
    invoice = _create_invoice(repo, project, "INV-SOFT-DELETE-001")

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "UPDATE clients SET sync_status = 'deleted', is_deleted = 1 WHERE id = ?",
        (client.id,),
    )
    cursor.execute(
        "UPDATE services SET sync_status = 'deleted', is_deleted = 1 WHERE id = ?",
        (service.id,),
    )
    cursor.execute(
        "UPDATE payments SET sync_status = 'deleted', is_deleted = 1 WHERE id = ?",
        (payment.id,),
    )
    cursor.execute(
        "UPDATE expenses SET sync_status = 'deleted', is_deleted = 1 WHERE id = ?",
        (expense.id,),
    )
    cursor.execute(
        "UPDATE invoices SET sync_status = 'deleted', is_deleted = 1 WHERE invoice_number = ?",
        (invoice.invoice_number,),
    )
    repo.sqlite_conn.commit()

    assert repo.get_client_by_id(str(client.id)) is None
    assert repo.get_client_by_name(client.name) is None
    assert repo._get_client_by_phone(client.phone) is None
    assert repo.get_service_by_id(str(service.id)) is None
    assert repo.get_payment_by_id(payment.id) is None
    assert repo.get_expense_by_id(expense.id) is None
    assert repo.get_invoice_by_number(invoice.invoice_number) is None
    assert repo.get_invoice_by_id(str(invoice.id)) is None


def test_get_client_by_id_prefers_local_pending_row_over_stale_mongo_copy(repo):
    client = repo.create_client(
        schemas.Client(
            name="Merged Client",
            phone="01010000011",
            email="local-original@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE clients
        SET _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1, email = ?
        WHERE id = ?
        """,
        ("mongo-client-merge-1", "local-pending@example.com", client.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_clients = _FakeMongoCollection(
        [
            {
                "_id": "mongo-client-merge-1",
                "name": client.name,
                "phone": client.phone,
                "email": "cloud-stale@example.com",
                "status": client.status.value,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(clients=cloud_clients)

    fetched = repo.get_client_by_id("mongo-client-merge-1")

    assert fetched is not None
    assert fetched.email == "local-pending@example.com"
    assert fetched.mongo_id == "mongo-client-merge-1"


def test_get_service_by_id_prefers_local_pending_row_over_stale_mongo_copy(repo):
    service = repo.create_service(
        schemas.Service(name="Merged Service", description="local", default_price=100.0)
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE services
        SET _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1, description = ?
        WHERE id = ?
        """,
        ("mongo-service-merge-1", "local pending service description", service.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_services = _FakeMongoCollection(
        [
            {
                "_id": "mongo-service-merge-1",
                "name": service.name,
                "description": "cloud stale service description",
                "default_price": service.default_price,
                "status": service.status.value,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(services=cloud_services)

    fetched = repo.get_service_by_id("mongo-service-merge-1")

    assert fetched is not None
    assert fetched.description == "local pending service description"
    assert fetched.mongo_id == "mongo-service-merge-1"


def test_get_all_services_merges_remote_only_service_and_prefers_local_pending_row(repo):
    service = repo.create_service(
        schemas.Service(name="Merged Service List", description="local", default_price=100.0)
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE services
        SET _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1, description = ?
        WHERE id = ?
        """,
        ("mongo-service-list-merge-1", "local pending service list description", service.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_services = _FakeMongoCollection(
        [
            {
                "_id": "mongo-service-list-merge-1",
                "name": service.name,
                "description": "cloud stale service list description",
                "default_price": service.default_price,
                "status": service.status.value,
                "sync_status": "synced",
                "is_deleted": False,
            },
            {
                "_id": "mongo-service-list-merge-2",
                "name": "Cloud Only Service",
                "description": "cloud only description",
                "default_price": 250.0,
                "status": schemas.ServiceStatus.ACTIVE.value,
                "sync_status": "synced",
                "is_deleted": False,
            },
        ]
    )
    repo.mongo_db = SimpleNamespace(services=cloud_services)

    services = repo.get_all_services()
    services_by_name = {service.name: service for service in services}

    assert set(services_by_name) == {"Merged Service List", "Cloud Only Service"}
    assert (
        services_by_name["Merged Service List"].description
        == "local pending service list description"
    )
    assert services_by_name["Merged Service List"].mongo_id == "mongo-service-list-merge-1"
    assert services_by_name["Cloud Only Service"].description == "cloud only description"
    assert services_by_name["Cloud Only Service"].mongo_id == "mongo-service-list-merge-2"


def test_get_invoice_by_number_prefers_local_pending_row_over_stale_mongo_copy(repo):
    project = _create_project(repo, "Merged Lookup Invoice Project", client_id="CLIENT-INV-GET")
    invoice = _create_invoice(repo, project, "INV-GET-MERGED-001")

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE invoices
        SET _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1, notes = ?
        WHERE invoice_number = ?
        """,
        ("mongo-invoice-get-merge-1", "local pending invoice lookup note", invoice.invoice_number),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_invoices = _FakeMongoCollection(
        [
            {
                "_id": "mongo-invoice-get-merge-1",
                "invoice_number": invoice.invoice_number,
                "client_id": invoice.client_id,
                "project_id": invoice.project_id,
                "issue_date": datetime(2026, 3, 1, 9, 0, 0),
                "due_date": datetime(2026, 3, 8, 9, 0, 0),
                "items": [],
                "subtotal": invoice.subtotal,
                "total_amount": invoice.total_amount,
                "status": invoice.status.value,
                "amount_paid": invoice.amount_paid,
                "notes": "cloud stale invoice lookup note",
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(invoices=cloud_invoices)

    fetched = repo.get_invoice_by_number(invoice.invoice_number)

    assert fetched is not None
    assert fetched.notes == "local pending invoice lookup note"
    assert fetched.mongo_id == "mongo-invoice-get-merge-1"


def test_get_client_by_name_prefers_local_pending_row_over_stale_mongo_copy(repo):
    client = repo.create_client(
        schemas.Client(
            name="Merged Client By Name",
            phone="01010000012",
            email="local-name-original@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE clients
        SET _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1, email = ?
        WHERE id = ?
        """,
        ("mongo-client-name-merge-1", "local-name-pending@example.com", client.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_clients = _FakeMongoCollection(
        [
            {
                "_id": "mongo-client-name-merge-1",
                "name": client.name,
                "phone": client.phone,
                "email": "cloud-name-stale@example.com",
                "status": client.status.value,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(clients=cloud_clients)

    fetched = repo.get_client_by_name(client.name)

    assert fetched is not None
    assert fetched.email == "local-name-pending@example.com"
    assert fetched.mongo_id == "mongo-client-name-merge-1"


def test_get_client_by_phone_prefers_local_pending_row_over_stale_mongo_copy(repo):
    client = repo.create_client(
        schemas.Client(
            name="Merged Client By Phone",
            phone="0101 000 0013",
            email="local-phone-original@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE clients
        SET _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1, email = ?, phone = ?
        WHERE id = ?
        """,
        (
            "mongo-client-phone-merge-1",
            "local-phone-pending@example.com",
            "01010000013",
            client.id,
        ),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_clients = _FakeMongoCollection(
        [
            {
                "_id": "mongo-client-phone-merge-1",
                "name": client.name,
                "phone": "01010000013",
                "email": "cloud-phone-stale@example.com",
                "status": client.status.value,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(clients=cloud_clients)

    fetched = repo._get_client_by_phone("0101 000 0013")

    assert fetched is not None
    assert fetched.email == "local-phone-pending@example.com"
    assert fetched.mongo_id == "mongo-client-phone-merge-1"


def test_archived_lists_and_account_summaries_ignore_soft_deleted_rows(repo):
    active_archived_client = repo.create_client(schemas.Client(name="Archived Active Client"))
    deleted_archived_client = repo.create_client(schemas.Client(name="Archived Deleted Client"))
    active_archived_service = repo.create_service(
        schemas.Service(name="Archived Active Service", default_price=100.0)
    )
    deleted_archived_service = repo.create_service(
        schemas.Service(name="Archived Deleted Service", default_price=200.0)
    )

    project = _create_project(repo, "Soft Delete Ledger Project", client_id="CLIENT-LEDGER")

    repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 10, 9, 0, 0),
            amount=100.0,
            account_id="1101",
            method="Cash",
        )
    )
    repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 11, 9, 0, 0),
            category="Transport",
            amount=40.0,
            description="car",
            account_id="1101",
            payment_account_id=None,
        )
    )
    charged_expense = repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 12, 9, 0, 0),
            category="Supplies",
            amount=25.0,
            description="paper",
            account_id="5001",
            payment_account_id="1101",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "UPDATE clients SET status = ?, sync_status = 'synced', is_deleted = 0 WHERE id = ?",
        (schemas.ClientStatus.ARCHIVED.value, active_archived_client.id),
    )
    cursor.execute(
        "UPDATE clients SET status = ?, sync_status = 'deleted', is_deleted = 1 WHERE id = ?",
        (schemas.ClientStatus.ARCHIVED.value, deleted_archived_client.id),
    )
    cursor.execute(
        "UPDATE services SET status = ?, sync_status = 'synced', is_deleted = 0 WHERE id = ?",
        (schemas.ServiceStatus.ARCHIVED.value, active_archived_service.id),
    )
    cursor.execute(
        "UPDATE services SET status = ?, sync_status = 'deleted', is_deleted = 1 WHERE id = ?",
        (schemas.ServiceStatus.ARCHIVED.value, deleted_archived_service.id),
    )
    cursor.execute(
        """
        INSERT INTO payments (
            sync_status, created_at, last_modified, project_id, client_id,
            date, amount, account_id, method, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "deleted",
            "2026-02-13T09:00:00",
            "2026-02-13T09:00:00",
            project.name,
            project.client_id,
            "2026-02-13T09:00:00",
            900.0,
            "1101",
            "Cash",
            1,
            1,
        ),
    )
    cursor.execute(
        """
        INSERT INTO expenses (
            sync_status, created_at, last_modified, date, category, amount,
            description, account_id, payment_account_id, project_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "deleted",
            "2026-02-14T09:00:00",
            "2026-02-14T09:00:00",
            "2026-02-14T09:00:00",
            "Transport",
            400.0,
            "deleted-paid",
            "5001",
            "1101",
            project.name,
            1,
            1,
        ),
    )
    cursor.execute(
        """
        INSERT INTO expenses (
            sync_status, created_at, last_modified, date, category, amount,
            description, account_id, payment_account_id, project_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "deleted",
            "2026-02-15T09:00:00",
            "2026-02-15T09:00:00",
            "2026-02-15T09:00:00",
            "Supplies",
            250.0,
            "deleted-charged",
            "5001",
            "1101",
            project.name,
            1,
            1,
        ),
    )
    repo.sqlite_conn.commit()

    archived_clients = repo.get_archived_clients()
    archived_services = repo.get_archived_services()
    account_payments = repo.get_payments_by_account(
        "1101", "2026-02-01T00:00:00", "2026-02-20T00:00:00"
    )
    paid_expenses = repo.get_expenses_paid_from_account(
        "1101", "2026-02-01T00:00:00", "2026-02-20T00:00:00"
    )
    charged_expenses = repo.get_expenses_charged_to_account(
        "5001", "2026-02-01T00:00:00", "2026-02-20T00:00:00"
    )

    assert [client.name for client in archived_clients] == [active_archived_client.name]
    assert [service.name for service in archived_services] == [active_archived_service.name]
    assert [float(payment.amount) for payment in account_payments] == [100.0]
    assert sorted(float(expense.amount) for expense in paid_expenses) == [25.0, 40.0]
    assert [float(expense.amount) for expense in charged_expenses] == [
        float(charged_expense.amount)
    ]
    assert repo.sum_payments_before("1101", "2026-02-20T00:00:00") == pytest.approx(100.0)
    assert repo.sum_expenses_paid_before("1101", "2026-02-20T00:00:00") == pytest.approx(65.0)


def test_account_lookups_ignore_soft_deleted_rows(repo):
    repo.create_account(
        schemas.Account(
            name="Soft Deleted Cash Account",
            code="SOFT-ACC-001",
            type=schemas.AccountType.CASH,
        )
    )
    account = repo.get_account_by_code("SOFT-ACC-001")
    assert account is not None

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "UPDATE accounts SET sync_status = 'deleted', is_deleted = 1 WHERE id = ?",
        (account.id,),
    )
    repo.sqlite_conn.commit()

    assert repo.get_account_by_code(account.code) is None
    assert repo.get_account_by_id(str(account.id)) is None


def test_create_account_assigns_local_id(repo):
    account = repo.create_account(
        schemas.Account(
            name="Assigned Id Account",
            code="ASSIGN-ACC-001",
            type=schemas.AccountType.CASH,
        )
    )

    assert account.id is not None


def test_delete_account_permanently_uses_row_mongo_id_when_called_with_local_id(repo):
    repo.create_account(
        schemas.Account(
            name="Remote Delete Account",
            code="REMOTE-DEL-ACC-001",
            type=schemas.AccountType.CASH,
        )
    )
    account = repo.get_account_by_code("REMOTE-DEL-ACC-001")
    assert account is not None
    remote_id = ObjectId()

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE accounts
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (str(remote_id), account.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_accounts = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "code": account.code,
                "name": account.name,
                "type": account.type.value,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(accounts=cloud_accounts)

    assert repo.delete_account_permanently(str(account.id)) is True

    cursor.execute("SELECT COUNT(*) FROM accounts WHERE id = ?", (account.id,))
    remaining = cursor.fetchone()[0]

    assert remaining == 0
    assert cloud_accounts.documents[0]["sync_status"] == "deleted"
    assert cloud_accounts.documents[0]["is_deleted"] is True


def test_update_account_uses_row_mongo_id_when_called_with_local_id(repo, monkeypatch):
    import core.repository as repo_mod

    monkeypatch.setattr(repo_mod.QTimer, "singleShot", lambda _ms, callback: callback())

    account = repo.create_account(
        schemas.Account(
            name="Pulled Account",
            code="PULLED-ACC-001",
            type=schemas.AccountType.CASH,
            balance=100.0,
        )
    )
    assert account.id is not None
    remote_id = ObjectId()

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE accounts
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (str(remote_id), account.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_accounts = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "id": "source-device-account-1",
                "code": account.code,
                "name": account.name,
                "type": account.type.value,
                "balance": account.balance,
                "currency": schemas.CurrencyCode.EGP.value,
                "status": schemas.AccountStatus.ACTIVE.value,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(accounts=cloud_accounts)

    updated = account.model_copy(update={"name": "Pulled Account Updated", "balance": 325.0})
    updated._mongo_id = None

    result = repo.update_account(str(account.id), updated)

    cursor.execute(
        "SELECT name, balance, sync_status, dirty_flag, is_deleted FROM accounts WHERE id = ?",
        (account.id,),
    )
    row = cursor.fetchone()

    assert result is not None
    assert row["name"] == "Pulled Account Updated"
    assert float(row["balance"]) == pytest.approx(325.0)
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_accounts.documents[0]["name"] == "Pulled Account Updated"
    assert float(cloud_accounts.documents[0]["balance"]) == pytest.approx(325.0)
    assert cloud_accounts.documents[0]["sync_status"] == "synced"
    assert cloud_accounts.documents[0]["is_deleted"] is False


def test_update_user_by_username_revives_deleted_cloud_tombstone(repo):
    repo.create_user(
        User(
            username="revived-user",
            password_hash="hash-1",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Original User",
            email="old@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE username = ?
        """,
        ("revived-user",),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_users = _FakeMongoCollection(
        [
            {
                "_id": "mongo-user-revive-1",
                "username": "revived-user",
                "password_hash": "hash-1",
                "role": UserRole.ADMIN.value,
                "is_active": True,
                "full_name": "Deleted User",
                "email": "deleted@example.com",
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(users=cloud_users)

    assert repo.update_user_by_username(
        "revived-user",
        {"full_name": "Revived User", "email": "new@example.com"},
    )

    cursor.execute(
        "SELECT full_name, email, sync_status, dirty_flag, is_deleted FROM users WHERE username = ?",
        ("revived-user",),
    )
    row = cursor.fetchone()

    assert row["full_name"] == "Revived User"
    assert row["email"] == "new@example.com"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_users.documents[0]["full_name"] == "Revived User"
    assert cloud_users.documents[0]["email"] == "new@example.com"
    assert cloud_users.documents[0]["sync_status"] == "synced"
    assert cloud_users.documents[0]["is_deleted"] is False


def test_create_user_revives_deleted_local_row(repo):
    original_local_id = repo.create_user(
        User(
            username="revivable-user",
            password_hash="hash-old",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Deleted Local User",
            email="old@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET sync_status = 'deleted', dirty_flag = 0, is_deleted = 1
        WHERE username = ?
        """,
        ("revivable-user",),
    )
    repo.sqlite_conn.commit()

    recreated_id = repo.create_user(
        User(
            username="revivable-user",
            password_hash="hash-new",
            role=UserRole.ACCOUNTANT,
            is_active=True,
            full_name="Revived Local User",
            email="new@example.com",
        )
    )

    cursor.execute(
        """
        SELECT id, password_hash, role, full_name, email, sync_status, dirty_flag, is_deleted
        FROM users
        WHERE username = ?
        """,
        ("revivable-user",),
    )
    row = cursor.fetchone()

    assert recreated_id == original_local_id
    assert str(row["id"]) == original_local_id
    assert row["password_hash"] == "hash-new"
    assert row["role"] == UserRole.ACCOUNTANT.value
    assert row["full_name"] == "Revived Local User"
    assert row["email"] == "new@example.com"
    assert row["sync_status"] == "modified_offline"
    assert row["dirty_flag"] == 1
    assert row["is_deleted"] == 0


def test_create_user_revives_deleted_cloud_tombstone(repo):
    original_local_id = repo.create_user(
        User(
            username="revivable-cloud-user",
            password_hash="hash-old",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Deleted Cloud User",
            email="old@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET _mongo_id = NULL, sync_status = 'deleted', dirty_flag = 0, is_deleted = 1
        WHERE username = ?
        """,
        ("revivable-cloud-user",),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_users = _FakeMongoCollection(
        [
            {
                "_id": "mongo-user-create-revive-1",
                "username": "revivable-cloud-user",
                "password_hash": "hash-old",
                "role": UserRole.ADMIN.value,
                "is_active": True,
                "full_name": "Deleted Remote User",
                "email": "deleted@example.com",
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(users=cloud_users)

    recreated_id = repo.create_user(
        User(
            username="revivable-cloud-user",
            password_hash="hash-new",
            role=UserRole.SALES,
            is_active=True,
            full_name="Revived Cloud User",
            email="new@example.com",
        )
    )

    cursor.execute(
        """
        SELECT id, _mongo_id, password_hash, role, full_name, email, sync_status, dirty_flag, is_deleted
        FROM users
        WHERE username = ?
        """,
        ("revivable-cloud-user",),
    )
    row = cursor.fetchone()

    assert str(row["id"]) == original_local_id
    assert recreated_id == "mongo-user-create-revive-1"
    assert row["_mongo_id"] == "mongo-user-create-revive-1"
    assert row["password_hash"] == "hash-new"
    assert row["role"] == UserRole.SALES.value
    assert row["full_name"] == "Revived Cloud User"
    assert row["email"] == "new@example.com"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_users.documents[0]["password_hash"] == "hash-new"
    assert cloud_users.documents[0]["role"] == UserRole.SALES.value
    assert cloud_users.documents[0]["full_name"] == "Revived Cloud User"
    assert cloud_users.documents[0]["email"] == "new@example.com"
    assert cloud_users.documents[0]["sync_status"] == "synced"
    assert cloud_users.documents[0]["is_deleted"] is False


def test_update_user_by_username_ignores_deleted_local_row(repo):
    repo.create_user(
        User(
            username="deleted-local-update-user",
            password_hash="hash-1",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Deleted Local User",
            email="local@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET sync_status = 'deleted', dirty_flag = 0, is_deleted = 1
        WHERE username = ?
        """,
        ("deleted-local-update-user",),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_users = _FakeMongoCollection(
        [
            {
                "_id": "mongo-user-deleted-local-1",
                "username": "deleted-local-update-user",
                "password_hash": "hash-1",
                "role": UserRole.ADMIN.value,
                "is_active": True,
                "full_name": "Remote Tombstone User",
                "email": "remote@example.com",
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(users=cloud_users)

    assert (
        repo.update_user_by_username(
            "deleted-local-update-user",
            {"full_name": "Should Not Revive", "email": "should-not@example.com"},
        )
        is False
    )

    cursor.execute(
        "SELECT full_name, email, sync_status, dirty_flag, is_deleted FROM users WHERE username = ?",
        ("deleted-local-update-user",),
    )
    row = cursor.fetchone()

    assert row["full_name"] == "Deleted Local User"
    assert row["email"] == "local@example.com"
    assert row["sync_status"] == "deleted"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 1
    assert cloud_users.documents[0]["full_name"] == "Remote Tombstone User"
    assert cloud_users.documents[0]["email"] == "remote@example.com"
    assert cloud_users.documents[0]["sync_status"] == "deleted"
    assert cloud_users.documents[0]["is_deleted"] is True


def test_update_user_ignores_deleted_local_row_by_id(repo):
    local_id = repo.create_user(
        User(
            username="deleted-local-update-user-by-id",
            password_hash="hash-1",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Deleted Local User By Id",
            email="local-by-id@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET sync_status = 'deleted', dirty_flag = 0, is_deleted = 1
        WHERE id = ?
        """,
        (local_id,),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_users = _FakeMongoCollection(
        [
            {
                "_id": "mongo-user-deleted-local-2",
                "username": "deleted-local-update-user-by-id",
                "password_hash": "hash-1",
                "role": UserRole.ADMIN.value,
                "is_active": True,
                "full_name": "Remote Tombstone User By Id",
                "email": "remote-by-id@example.com",
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(users=cloud_users)

    assert repo.update_user(str(local_id), {"full_name": "Should Not Revive By Id"}) is False

    cursor.execute(
        "SELECT full_name, email, sync_status, dirty_flag, is_deleted FROM users WHERE id = ?",
        (local_id,),
    )
    row = cursor.fetchone()

    assert row["full_name"] == "Deleted Local User By Id"
    assert row["email"] == "local-by-id@example.com"
    assert row["sync_status"] == "deleted"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 1
    assert cloud_users.documents[0]["full_name"] == "Remote Tombstone User By Id"
    assert cloud_users.documents[0]["email"] == "remote-by-id@example.com"
    assert cloud_users.documents[0]["sync_status"] == "deleted"
    assert cloud_users.documents[0]["is_deleted"] is True


def test_get_user_by_username_ignores_deleted_local_row(repo):
    repo.create_user(
        User(
            username="deleted-local-user",
            password_hash="hash-deleted-local",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Deleted Local User",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET sync_status = 'deleted', dirty_flag = 0, is_deleted = 1
        WHERE username = ?
        """,
        ("deleted-local-user",),
    )
    repo.sqlite_conn.commit()

    assert repo.get_user_by_username("deleted-local-user") is None


def test_get_user_by_username_ignores_deleted_cloud_row(repo):
    repo.online = True
    cloud_users = _FakeMongoCollection(
        [
            {
                "_id": "mongo-user-deleted-lookup-1",
                "username": "deleted-cloud-user",
                "password_hash": "hash-deleted-cloud",
                "role": UserRole.ADMIN.value,
                "is_active": True,
                "full_name": "Deleted Cloud User",
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(users=cloud_users)

    assert repo.get_user_by_username("deleted-cloud-user") is None


def test_authenticate_ignores_deleted_user_lookup(repo):
    password = "DeletedUserPass123!"
    repo.create_user(
        User(
            username="deleted-auth-user",
            password_hash=AuthService.hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Deleted Auth User",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET sync_status = 'deleted', dirty_flag = 0, is_deleted = 1
        WHERE username = ?
        """,
        ("deleted-auth-user",),
    )
    repo.sqlite_conn.commit()

    auth = AuthService.__new__(AuthService)
    auth.repo = repo

    assert auth.authenticate("deleted-auth-user", password) is None


def test_sync_users_bidirectional_revives_deleted_cloud_tombstone(repo):
    local_id = repo.create_user(
        User(
            username="sync-user",
            password_hash="hash-sync",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Local Sync User",
            email="sync-local@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET _mongo_id = NULL, sync_status = 'modified_offline', dirty_flag = 1, is_deleted = 0
        WHERE id = ?
        """,
        (local_id,),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_users = _FakeMongoCollection(
        [
            {
                "_id": "mongo-user-sync-1",
                "username": "sync-user",
                "password_hash": "hash-old",
                "role": UserRole.ADMIN.value,
                "is_active": True,
                "full_name": "Deleted Sync User",
                "email": "deleted-sync@example.com",
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(users=cloud_users)

    result = repo.sync_users_bidirectional()

    cursor.execute(
        "SELECT _mongo_id, full_name, email, sync_status, dirty_flag, is_deleted FROM users WHERE id = ?",
        (local_id,),
    )
    row = cursor.fetchone()

    assert result["errors"] == []
    assert result["uploaded"] == 1
    assert row["_mongo_id"] == "mongo-user-sync-1"
    assert row["full_name"] == "Local Sync User"
    assert row["email"] == "sync-local@example.com"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_users.documents[0]["full_name"] == "Local Sync User"
    assert cloud_users.documents[0]["email"] == "sync-local@example.com"
    assert cloud_users.documents[0]["sync_status"] == "synced"
    assert cloud_users.documents[0]["is_deleted"] is False


def test_sync_users_bidirectional_pull_hides_deleted_cloud_user(repo):
    local_id = repo.create_user(
        User(
            username="deleted-sync-user",
            password_hash="hash-del",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Visible Before Pull",
            email="visible@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        ("mongo-user-deleted-pull-1", local_id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_users = _FakeMongoCollection(
        [
            {
                "_id": "mongo-user-deleted-pull-1",
                "username": "deleted-sync-user",
                "password_hash": "hash-del",
                "role": UserRole.ADMIN.value,
                "is_active": True,
                "full_name": "Deleted In Cloud",
                "email": "deleted@example.com",
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(users=cloud_users)

    result = repo.sync_users_bidirectional()

    cursor.execute(
        "SELECT sync_status, dirty_flag, is_deleted FROM users WHERE id = ?",
        (local_id,),
    )
    row = cursor.fetchone()

    assert result["errors"] == []
    assert result["downloaded"] == 1
    assert row["sync_status"] == "deleted"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 1
    assert repo.get_all_users() == []


def test_sync_users_bidirectional_skips_deleted_local_user_without_mongo_id(repo):
    local_id = repo.create_user(
        User(
            username="deleted-local-sync-user",
            password_hash="hash-del-local-sync",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Deleted Local Sync User",
            email="deleted-local-sync@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET _mongo_id = NULL, sync_status = 'deleted', dirty_flag = 0, is_deleted = 1
        WHERE id = ?
        """,
        (local_id,),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_users = _FakeMongoCollection([])
    repo.mongo_db = SimpleNamespace(users=cloud_users)

    result = repo.sync_users_bidirectional()

    cursor.execute(
        "SELECT _mongo_id, sync_status, dirty_flag, is_deleted FROM users WHERE id = ?",
        (local_id,),
    )
    row = cursor.fetchone()

    assert result["errors"] == []
    assert result["uploaded"] == 0
    assert result["downloaded"] == 0
    assert row["_mongo_id"] is None
    assert row["sync_status"] == "deleted"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 1
    assert cloud_users.documents == []


def test_get_all_users_merges_local_unsynced_user_with_mongo_results(repo):
    repo.create_user(
        User(
            username="local-pending-user",
            password_hash="hash-local-pending",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Local Pending User",
            email="local-pending@example.com",
        )
    )

    repo.online = True
    cloud_users = _FakeMongoCollection(
        [
            {
                "_id": "mongo-user-visible-1",
                "username": "cloud-visible-user",
                "password_hash": "hash-cloud-visible",
                "role": UserRole.SALES.value,
                "is_active": True,
                "full_name": "Cloud Visible User",
                "email": "cloud-visible@example.com",
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(users=cloud_users)

    users = repo.get_all_users()

    usernames = {user.username for user in users}

    assert usernames == {"local-pending-user", "cloud-visible-user"}


def test_get_all_users_prefers_local_pending_user_over_stale_mongo_copy(repo):
    local_id = repo.create_user(
        User(
            username="merged-user",
            password_hash="hash-merged-local",
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Original Local Name",
            email="original-local@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE users
        SET _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1,
            full_name = ?, email = ?
        WHERE id = ?
        """,
        (
            "mongo-user-merge-1",
            "Local Pending Name",
            "local-pending@example.com",
            local_id,
        ),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_users = _FakeMongoCollection(
        [
            {
                "_id": "mongo-user-merge-1",
                "username": "merged-user",
                "password_hash": "hash-merged-cloud",
                "role": UserRole.ADMIN.value,
                "is_active": True,
                "full_name": "Cloud Stale Name",
                "email": "cloud-stale@example.com",
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(users=cloud_users)

    users = repo.get_all_users()
    merged_user = next(user for user in users if user.username == "merged-user")

    assert len([user for user in users if user.username == "merged-user"]) == 1
    assert merged_user.id == str(local_id)
    assert merged_user.mongo_id == "mongo-user-merge-1"
    assert merged_user.full_name == "Local Pending Name"
    assert merged_user.email == "local-pending@example.com"


def test_update_account_balance_revives_deleted_cloud_tombstone(repo):
    repo.create_account(
        schemas.Account(
            name="Balance Revive Account",
            code="BAL-REVIVE-001",
            type=schemas.AccountType.CASH,
            balance=100.0,
        )
    )
    account = repo.get_account_by_code("BAL-REVIVE-001")
    assert account is not None

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE accounts
        SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE code = ?
        """,
        (account.code,),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_accounts = _FakeMongoCollection(
        [
            {
                "_id": "mongo-balance-revive-1",
                "code": account.code,
                "name": account.name,
                "type": account.type.value,
                "balance": 100.0,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(accounts=cloud_accounts)

    assert repo.update_account_balance(account.code, 275.0) is True

    cursor.execute(
        "SELECT balance, sync_status, dirty_flag, is_deleted FROM accounts WHERE code = ?",
        (account.code,),
    )
    row = cursor.fetchone()

    assert float(row["balance"]) == pytest.approx(275.0)
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert float(cloud_accounts.documents[0]["balance"]) == pytest.approx(275.0)
    assert cloud_accounts.documents[0]["sync_status"] == "synced"
    assert cloud_accounts.documents[0]["is_deleted"] is False


def test_update_journal_entry_revives_deleted_cloud_tombstone(repo):
    entry = repo.create_journal_entry(
        schemas.JournalEntry(
            date=datetime(2026, 3, 1, 10, 0, 0),
            description="Initial journal entry",
            related_document_id="JRN-UPDATE-REVIVE",
            lines=[
                schemas.JournalEntryLine(account_id="1101", debit=100.0, credit=0.0),
                schemas.JournalEntryLine(account_id="4001", debit=0.0, credit=100.0),
            ],
        )
    )
    assert entry.id is not None
    assert entry.related_document_id == "JRN-UPDATE-REVIVE"

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE journal_entries
        SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE related_document_id = ?
        """,
        ("JRN-UPDATE-REVIVE",),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_entries = _FakeMongoCollection(
        [
            {
                "_id": "mongo-journal-revive-1",
                "related_document_id": "JRN-UPDATE-REVIVE",
                "description": "Deleted cloud journal entry",
                "lines": [
                    {"account_id": "1101", "debit": 50.0, "credit": 0.0},
                    {"account_id": "4001", "debit": 0.0, "credit": 50.0},
                ],
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(journal_entries=cloud_entries)

    updated_lines = [
        schemas.JournalEntryLine(account_id="1101", debit=150.0, credit=0.0),
        schemas.JournalEntryLine(account_id="4001", debit=0.0, credit=150.0),
    ]

    assert repo.update_journal_entry_by_doc_id(
        "JRN-UPDATE-REVIVE",
        updated_lines,
        "Revived journal entry",
    )

    cursor.execute(
        """
        SELECT description, sync_status, dirty_flag, is_deleted
        FROM journal_entries
        WHERE related_document_id = ?
        """,
        ("JRN-UPDATE-REVIVE",),
    )
    row = cursor.fetchone()

    assert row["description"] == "Revived journal entry"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_entries.documents[0]["description"] == "Revived journal entry"
    assert cloud_entries.documents[0]["sync_status"] == "synced"
    assert cloud_entries.documents[0]["is_deleted"] is False
    assert cloud_entries.documents[0]["lines"][0]["debit"] == pytest.approx(150.0)


def test_account_and_currency_mongo_reads_ignore_soft_deleted_rows(repo):
    cursor = repo.sqlite_conn.cursor()
    cursor.execute("UPDATE accounts SET sync_status = 'deleted', is_deleted = 1")
    cursor.execute("UPDATE currencies SET sync_status = 'deleted', is_deleted = 1")
    repo.sqlite_conn.commit()

    repo.online = True
    repo.mongo_db = SimpleNamespace(
        accounts=_FakeMongoCollection(
            [
                {
                    "_id": "mongo-account-active-1",
                    "name": "Cash Active",
                    "code": "MONGO-1101",
                    "type": schemas.AccountType.CASH.value,
                    "balance": 0.0,
                    "currency": schemas.CurrencyCode.EGP.value,
                    "status": schemas.AccountStatus.ACTIVE.value,
                },
                {
                    "_id": "mongo-account-deleted-1",
                    "name": "Cash Deleted",
                    "code": "MONGO-9999",
                    "type": schemas.AccountType.CASH.value,
                    "balance": 0.0,
                    "currency": schemas.CurrencyCode.EGP.value,
                    "status": schemas.AccountStatus.ACTIVE.value,
                    "sync_status": "deleted",
                    "is_deleted": True,
                },
            ]
        ),
        currencies=_FakeMongoCollection(
            [
                {
                    "_id": "mongo-currency-active-1",
                    "code": "USD",
                    "name": "US Dollar",
                    "symbol": "$",
                    "rate": 50.0,
                    "is_base": False,
                    "active": True,
                },
                {
                    "_id": "mongo-currency-deleted-1",
                    "code": "SAR",
                    "name": "Saudi Riyal",
                    "symbol": "SAR",
                    "rate": 13.0,
                    "is_base": False,
                    "active": True,
                    "sync_status": "deleted",
                    "is_deleted": True,
                },
            ]
        ),
    )

    accounts = repo.get_all_accounts()
    currencies = repo.get_all_currencies()

    assert [account.code for account in accounts] == ["MONGO-1101"]
    assert repo.get_account_by_code("MONGO-1101") is not None
    assert repo.get_account_by_code("MONGO-9999") is None
    assert [currency["code"] for currency in currencies] == ["USD"]


def test_journal_entry_reads_ignore_soft_deleted_rows(repo):
    repo.create_journal_entry(
        schemas.JournalEntry(
            date=datetime(2026, 2, 18, 9, 0, 0),
            description="Soft deleted journal entry",
            related_document_id="JRN-SOFT-001",
            lines=[
                schemas.JournalEntryLine(account_id="1101", debit=100.0),
                schemas.JournalEntryLine(account_id="4001", credit=100.0),
            ],
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE journal_entries
        SET sync_status = 'deleted', is_deleted = 0
        WHERE related_document_id = ?
        """,
        ("JRN-SOFT-001",),
    )
    repo.sqlite_conn.commit()

    assert repo.get_all_journal_entries() == []
    assert repo.get_journal_entries_before("2026-02-20T00:00:00") == []
    assert repo.get_journal_entries_between("2026-02-01T00:00:00", "2026-02-20T00:00:00") == []
    assert repo.get_journal_entry_by_doc_id("JRN-SOFT-001") is None


def test_journal_entry_mongo_reads_ignore_soft_deleted_rows(repo, monkeypatch):
    cursor = repo.sqlite_conn.cursor()
    cursor.execute("UPDATE journal_entries SET sync_status = 'deleted', is_deleted = 1")
    repo.sqlite_conn.commit()

    repo.online = True
    repo.mongo_db = SimpleNamespace(
        journal_entries=_FakeMongoCollection(
            [
                {
                    "_id": "mongo-journal-active-1",
                    "date": datetime(2026, 2, 20, 9, 0, 0),
                    "description": "Active journal entry",
                    "related_document_id": "JRN-MONGO-OK",
                    "lines": [
                        {"account_id": "1101", "debit": 50.0},
                        {"account_id": "4001", "credit": 50.0},
                    ],
                },
                {
                    "_id": "mongo-journal-deleted-1",
                    "date": datetime(2026, 2, 21, 9, 0, 0),
                    "description": "Deleted journal entry",
                    "related_document_id": "JRN-MONGO-DELETED",
                    "lines": [
                        {"account_id": "1101", "debit": 75.0},
                        {"account_id": "4001", "credit": 75.0},
                    ],
                    "sync_status": "deleted",
                    "is_deleted": True,
                },
            ]
        )
    )
    monkeypatch.setattr(
        repo,
        "get_cursor",
        lambda: (_ for _ in ()).throw(RuntimeError("forced journal sqlite fallback")),
    )

    entries = repo.get_all_journal_entries()

    assert [entry.related_document_id for entry in entries] == ["JRN-MONGO-OK"]
    assert repo.get_journal_entry_by_doc_id("JRN-MONGO-OK") is not None
    assert repo.get_journal_entry_by_doc_id("JRN-MONGO-DELETED") is None


def test_archive_client_keeps_row_visible_in_archived_list(repo):
    client = repo.create_client(schemas.Client(name="Archived Client Visible"))

    assert repo.archive_client_by_id(str(client.id)) is True

    cursor = repo.sqlite_conn.cursor()
    cursor.execute("SELECT status, is_deleted FROM clients WHERE id = ?", (client.id,))
    row = cursor.fetchone()

    archived_clients = repo.get_archived_clients()

    assert row["status"] == schemas.ClientStatus.ARCHIVED.value
    assert row["is_deleted"] == 0
    assert [item.name for item in archived_clients] == [client.name]


def test_archive_client_revives_deleted_cloud_tombstone(repo):
    client = repo.create_client(schemas.Client(name="Archived Cloud Client"))
    remote_id = "mongo-archived-client-revive-1"

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE clients
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (remote_id, client.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_clients = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "name": client.name,
                "status": schemas.ClientStatus.ACTIVE.value,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(clients=cloud_clients)

    assert repo.archive_client_by_id(remote_id) is True

    cursor.execute(
        "SELECT status, sync_status, dirty_flag, is_deleted FROM clients WHERE id = ?",
        (client.id,),
    )
    row = cursor.fetchone()

    archived_clients = repo.get_archived_clients()

    assert row["status"] == schemas.ClientStatus.ARCHIVED.value
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_clients.documents[0]["status"] == schemas.ClientStatus.ARCHIVED.value
    assert cloud_clients.documents[0]["sync_status"] == "synced"
    assert cloud_clients.documents[0]["is_deleted"] is False
    assert [item.name for item in archived_clients] == [client.name]


def test_archive_client_uses_row_mongo_id_when_called_with_local_id(repo):
    client = repo.create_client(schemas.Client(name="Archived Cloud Client Local Id"))
    remote_id = ObjectId()

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE clients
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (str(remote_id), client.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_clients = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "id": "source-device-client-archive-1",
                "name": client.name,
                "status": schemas.ClientStatus.ACTIVE.value,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(clients=cloud_clients)

    assert repo.archive_client_by_id(str(client.id)) is True

    cursor.execute(
        "SELECT status, sync_status, dirty_flag, is_deleted FROM clients WHERE id = ?",
        (client.id,),
    )
    row = cursor.fetchone()

    assert row["status"] == schemas.ClientStatus.ARCHIVED.value
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_clients.documents[0]["status"] == schemas.ClientStatus.ARCHIVED.value
    assert cloud_clients.documents[0]["sync_status"] == "synced"
    assert cloud_clients.documents[0]["is_deleted"] is False


def test_archived_clients_ignore_soft_deleted_rows(repo):
    visible_client = repo.create_client(schemas.Client(name="Archived Client Visible Only"))
    hidden_client = repo.create_client(schemas.Client(name="Archived Client Hidden"))

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE clients
        SET status = ?, sync_status = 'synced', is_deleted = 0
        WHERE id = ?
        """,
        (schemas.ClientStatus.ARCHIVED.value, visible_client.id),
    )
    cursor.execute(
        """
        UPDATE clients
        SET status = ?, sync_status = 'synced', is_deleted = 1
        WHERE id = ?
        """,
        (schemas.ClientStatus.ARCHIVED.value, hidden_client.id),
    )
    repo.sqlite_conn.commit()

    archived_clients = repo.get_archived_clients()

    assert [client.name for client in archived_clients] == [visible_client.name]


def test_archived_clients_mongo_reads_ignore_soft_deleted_rows(repo):
    repo.online = True
    repo.mongo_db = SimpleNamespace(
        clients=_FakeMongoCollection(
            [
                {
                    "_id": "mongo-archived-client-active-1",
                    "name": "Mongo Archived Visible",
                    "status": schemas.ClientStatus.ARCHIVED.value,
                },
                {
                    "_id": "mongo-archived-client-deleted-1",
                    "name": "Mongo Archived Hidden",
                    "status": schemas.ClientStatus.ARCHIVED.value,
                    "is_deleted": True,
                },
            ]
        )
    )

    archived_clients = repo.get_archived_clients()

    assert [client.name for client in archived_clients] == ["Mongo Archived Visible"]


def test_create_account_revives_deleted_cloud_duplicate(repo, monkeypatch):
    import core.repository as repo_mod

    duplicate_code = "REUSE-ACC-001"
    cloud_accounts = _FakeMongoCollection(
        [
            {
                "_id": "mongo-deleted-account-1",
                "name": "Deleted Cloud Account",
                "code": duplicate_code,
                "type": schemas.AccountType.CASH.value,
                "balance": 10.0,
                "currency": schemas.CurrencyCode.EGP.value,
                "status": schemas.AccountStatus.ACTIVE.value,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ],
        duplicate_insert_codes={duplicate_code},
    )

    monkeypatch.setattr(repo_mod.QTimer, "singleShot", lambda _ms, callback: callback())

    repo.online = True
    repo.mongo_db = SimpleNamespace(accounts=cloud_accounts)

    repo.create_account(
        schemas.Account(
            name="Revived Cloud Account",
            code=duplicate_code,
            type=schemas.AccountType.CASH,
            balance=125.0,
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "SELECT _mongo_id, sync_status, dirty_flag, is_deleted FROM accounts WHERE code = ?",
        (duplicate_code,),
    )
    row = cursor.fetchone()

    assert row["_mongo_id"] == "mongo-deleted-account-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_accounts.documents[0]["is_deleted"] is False
    assert cloud_accounts.documents[0]["sync_status"] == "synced"
    assert cloud_accounts.documents[0]["name"] == "Revived Cloud Account"


def test_create_service_revives_deleted_cloud_duplicate(repo):
    deleted_name = "Deleted Cloud Service"
    cloud_services = _FakeMongoCollection(
        [
            {
                "_id": "mongo-deleted-service-1",
                "name": deleted_name,
                "description": "Old deleted service",
                "default_price": 90.0,
                "category": "General",
                "status": schemas.ServiceStatus.ACTIVE.value,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ],
        duplicate_insert_names={deleted_name},
    )

    repo.online = True
    repo.mongo_db = SimpleNamespace(services=cloud_services)

    repo.create_service(
        schemas.Service(
            name=deleted_name,
            description="Revived service",
            default_price=120.0,
            category="General",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "SELECT _mongo_id, sync_status, dirty_flag, is_deleted FROM services WHERE name = ?",
        (deleted_name,),
    )
    row = cursor.fetchone()

    assert row["_mongo_id"] == "mongo-deleted-service-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_services.documents[0]["is_deleted"] is False
    assert cloud_services.documents[0]["sync_status"] == "synced"
    assert cloud_services.documents[0]["description"] == "Revived service"
    assert cloud_services.documents[0]["default_price"] == pytest.approx(120.0)


def test_update_service_revives_deleted_cloud_tombstone(repo):
    service = repo.create_service(
        schemas.Service(name="Edited Cloud Service", description="Original", default_price=90.0)
    )
    remote_id = "mongo-edited-service-1"

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE services
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (remote_id, service.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_services = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "name": service.name,
                "description": "Deleted copy",
                "default_price": 90.0,
                "category": "General",
                "status": schemas.ServiceStatus.ACTIVE.value,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(services=cloud_services)

    updated = service.model_copy(
        update={"description": "Edited after delete", "default_price": 145.0}
    )

    result = repo.update_service(remote_id, updated)

    cursor.execute(
        "SELECT sync_status, dirty_flag, is_deleted FROM services WHERE id = ?",
        (service.id,),
    )
    row = cursor.fetchone()

    assert result is not None
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_services.documents[0]["description"] == "Edited after delete"
    assert cloud_services.documents[0]["default_price"] == pytest.approx(145.0)
    assert cloud_services.documents[0]["sync_status"] == "synced"
    assert cloud_services.documents[0]["is_deleted"] is False


def test_update_service_uses_row_mongo_id_when_called_with_local_id(repo):
    service = repo.create_service(
        schemas.Service(name="Pulled Cloud Service", description="Original", default_price=90.0)
    )
    remote_id = ObjectId()

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE services
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (str(remote_id), service.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_services = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "id": "source-device-service-1",
                "name": service.name,
                "description": "Deleted copy",
                "default_price": 90.0,
                "category": "General",
                "status": schemas.ServiceStatus.ACTIVE.value,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(services=cloud_services)

    updated = service.model_copy(
        update={"description": "Edited with local id", "default_price": 155.0}
    )
    updated._mongo_id = None

    result = repo.update_service(str(service.id), updated)

    cursor.execute(
        "SELECT description, sync_status, dirty_flag, is_deleted FROM services WHERE id = ?",
        (service.id,),
    )
    row = cursor.fetchone()

    assert result is not None
    assert row["description"] == "Edited with local id"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_services.documents[0]["description"] == "Edited with local id"
    assert cloud_services.documents[0]["default_price"] == pytest.approx(155.0)
    assert cloud_services.documents[0]["sync_status"] == "synced"
    assert cloud_services.documents[0]["is_deleted"] is False


def test_save_currency_revives_soft_deleted_local_currency(repo):
    assert repo.save_currency(
        {"code": "USD", "name": "US Dollar", "symbol": "$", "rate": 50.0, "active": True}
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE currencies
        SET sync_status = 'deleted', is_deleted = 1, dirty_flag = 1
        WHERE code = 'USD'
        """
    )
    repo.sqlite_conn.commit()

    assert repo.save_currency(
        {
            "code": "USD",
            "name": "US Dollar Revived",
            "symbol": "$",
            "rate": 51.0,
            "active": True,
        }
    )

    cursor.execute(
        "SELECT name, rate, sync_status, dirty_flag, is_deleted FROM currencies WHERE code = 'USD'"
    )
    row = cursor.fetchone()

    assert row["name"] == "US Dollar Revived"
    assert row["rate"] == pytest.approx(51.0)
    assert row["sync_status"] == "modified_offline"
    assert row["dirty_flag"] == 1
    assert row["is_deleted"] == 0
    assert [currency["code"] for currency in repo.get_all_currencies()] == ["USD"]


def test_save_currency_revives_deleted_cloud_tombstone(repo):
    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO currencies (
            code, name, symbol, rate, is_base, active, created_at, last_modified,
            sync_status, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "SAR",
            "Deleted Riyal",
            "SAR",
            13.0,
            0,
            1,
            "2026-02-20T09:00:00",
            "2026-02-20T09:00:00",
            "deleted",
            1,
            1,
        ),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_currencies = _FakeMongoCollection(
        [
            {
                "_id": "mongo-currency-deleted-2",
                "code": "SAR",
                "name": "Deleted Riyal",
                "symbol": "SAR",
                "rate": 13.0,
                "is_base": False,
                "active": True,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(currencies=cloud_currencies)

    assert repo.save_currency(
        {
            "code": "SAR",
            "name": "Saudi Riyal",
            "symbol": "SAR",
            "rate": 13.2,
            "active": True,
        }
    )

    cursor.execute(
        "SELECT name, rate, sync_status, dirty_flag, is_deleted FROM currencies WHERE code = 'SAR'"
    )
    row = cursor.fetchone()

    assert row["name"] == "Saudi Riyal"
    assert row["rate"] == pytest.approx(13.2)
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_currencies.documents[0]["name"] == "Saudi Riyal"
    assert cloud_currencies.documents[0]["rate"] == pytest.approx(13.2)
    assert cloud_currencies.documents[0]["sync_status"] == "synced"
    assert cloud_currencies.documents[0]["is_deleted"] is False


def test_deleted_client_name_and_phone_can_be_reused(repo):
    client = repo.create_client(
        schemas.Client(name="Reusable Client", phone="01020000001", email="a@example.com")
    )

    assert repo.delete_client_permanently(str(client.id)) is True

    recreated = repo.create_client(
        schemas.Client(name="Reusable Client", phone="01020000001", email="b@example.com")
    )

    assert recreated.id != client.id
    assert recreated.name == client.name
    assert recreated.phone == client.phone


def test_create_client_ignores_stale_remote_name_duplicate_when_local_client_renamed(repo):
    client = repo.create_client(
        schemas.Client(
            name="Original Remote Client",
            phone="01020000101",
            email="old@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE clients
        SET name = ?, _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1
        WHERE id = ?
        """,
        ("Renamed Local Client", "mongo-client-stale-name-1", client.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_clients = _FakeMongoCollection(
        [
            {
                "_id": "mongo-client-stale-name-1",
                "name": "Original Remote Client",
                "phone": "01020000101",
                "email": "cloud-old@example.com",
                "status": schemas.ClientStatus.ACTIVE.value,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(clients=cloud_clients)

    recreated = repo.create_client(
        schemas.Client(
            name="Original Remote Client",
            phone="01020000102",
            email="new@example.com",
        )
    )

    assert recreated.id != client.id
    assert recreated.name == "Original Remote Client"


def test_create_client_ignores_stale_remote_phone_duplicate_when_local_client_phone_changed(repo):
    client = repo.create_client(
        schemas.Client(
            name="Phone Changed Local Client",
            phone="01020000111",
            email="old-phone@example.com",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE clients
        SET phone = ?, _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1
        WHERE id = ?
        """,
        ("01020000112", "mongo-client-stale-phone-1", client.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_clients = _FakeMongoCollection(
        [
            {
                "_id": "mongo-client-stale-phone-1",
                "name": "Phone Changed Local Client",
                "phone": "01020000111",
                "email": "cloud-phone-old@example.com",
                "status": schemas.ClientStatus.ACTIVE.value,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(clients=cloud_clients)

    recreated = repo.create_client(
        schemas.Client(
            name="New Client Uses Old Phone",
            phone="01020000111",
            email="new-phone@example.com",
        )
    )

    assert recreated.id != client.id
    assert recreated.phone == "01020000111"


def test_create_client_still_rejects_real_remote_duplicate_without_local_shadow(repo):
    repo.online = True
    cloud_clients = _FakeMongoCollection(
        [
            {
                "_id": "mongo-client-real-dup-1",
                "name": "Real Remote Client",
                "phone": "01020000121",
                "email": "cloud-real@example.com",
                "status": schemas.ClientStatus.ACTIVE.value,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(clients=cloud_clients)

    with pytest.raises(ValueError, match="موجود بالفعل"):
        repo.create_client(
            schemas.Client(
                name="Real Remote Client",
                phone="01020000122",
                email="new-real@example.com",
            )
        )


def test_update_client_uses_row_mongo_id_when_called_with_local_id(repo):
    client = repo.create_client(
        schemas.Client(name="Pulled Client", phone="01020000009", email="old@example.com")
    )
    remote_id = ObjectId()

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE clients
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (str(remote_id), client.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_clients = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "id": "source-device-client-1",
                "name": client.name,
                "phone": client.phone,
                "email": client.email,
                "status": client.status.value,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(clients=cloud_clients)

    updated = client.model_copy(update={"email": "new@example.com"})
    updated._mongo_id = None

    result = repo.update_client(str(client.id), updated)

    cursor.execute(
        "SELECT email, sync_status, dirty_flag, is_deleted FROM clients WHERE id = ?",
        (client.id,),
    )
    row = cursor.fetchone()

    assert result is not None
    assert row["email"] == "new@example.com"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_clients.documents[0]["email"] == "new@example.com"
    assert cloud_clients.documents[0]["sync_status"] == "synced"
    assert cloud_clients.documents[0]["is_deleted"] is False


def test_deleted_project_name_can_be_reused_with_new_fixed_invoice_number(repo):
    original = _create_project(repo, "Reusable Project Name", client_id="CLIENT-REUSE")
    original_invoice_number = original.invoice_number

    assert repo.delete_project(original.name) is True

    recreated = repo.create_project(
        schemas.Project(
            name=original.name,
            client_id=original.client_id,
            total_amount=2000.0,
        )
    )

    assert recreated.id != original.id
    assert recreated.invoice_number
    assert recreated.invoice_number != original_invoice_number


def test_same_project_name_is_allowed_for_different_clients(repo):
    first = _create_project(repo, "Shared Project Name", client_id="CLIENT-A")
    second = _create_project(repo, "Shared Project Name", client_id="CLIENT-B")

    assert first.id != second.id
    assert first.client_id != second.client_id
    assert first.invoice_number
    assert second.invoice_number
    assert first.invoice_number != second.invoice_number
    assert repo.get_invoice_number_for_project(str(first.id)) == first.invoice_number
    assert repo.get_invoice_number_for_project(str(second.id)) == second.invoice_number
    assert repo.get_project_by_number(first.name) is None

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "SELECT project_id, project_name, invoice_number FROM invoice_numbers ORDER BY id"
    )
    rows = cursor.fetchall()
    mapping = {(str(row[0]), str(row[1])): str(row[2]) for row in rows}

    assert mapping[(str(first.id), first.name)] == first.invoice_number
    assert mapping[(str(second.id), second.name)] == second.invoice_number


def test_create_project_ignores_stale_remote_duplicate_when_local_project_renamed(repo):
    original = _create_project(repo, "Original Remote Project", client_id="CLIENT-PROJECT-DUP")

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE projects
        SET name = ?, _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1
        WHERE id = ?
        """,
        ("Renamed Local Project", "mongo-project-stale-1", original.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_projects = _FakeMongoCollection(
        [
            {
                "_id": "mongo-project-stale-1",
                "name": "Original Remote Project",
                "client_id": original.client_id,
                "status": schemas.ProjectStatus.ACTIVE.value,
                "items": [],
                "milestones": [],
                "total_amount": original.total_amount,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(projects=cloud_projects)

    recreated = repo.create_project(
        schemas.Project(
            name="Original Remote Project",
            client_id=original.client_id,
            total_amount=2000.0,
        )
    )

    assert recreated.id != original.id
    assert recreated.name == "Original Remote Project"


def test_create_project_still_rejects_real_remote_duplicate_without_local_shadow(repo):
    repo.online = True
    cloud_projects = _FakeMongoCollection(
        [
            {
                "_id": "mongo-project-real-dup-1",
                "name": "Real Remote Duplicate",
                "client_id": "CLIENT-PROJECT-REMOTE",
                "status": schemas.ProjectStatus.ACTIVE.value,
                "items": [],
                "milestones": [],
                "total_amount": 1500.0,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(projects=cloud_projects)

    with pytest.raises(ValueError, match="يوجد مشروع مشابه"):
        repo.create_project(
            schemas.Project(
                name="Real Remote Duplicate",
                client_id="CLIENT-PROJECT-REMOTE",
                total_amount=1800.0,
            )
        )


def test_get_project_by_number_can_disambiguate_same_name_with_client_id(repo):
    first = _create_project(repo, "Shared Project Lookup", client_id="CLIENT-LOOKUP-A")
    second = _create_project(repo, "Shared Project Lookup", client_id="CLIENT-LOOKUP-B")

    resolved_first = repo.get_project_by_number(first.name, first.client_id)
    resolved_second = repo.get_project_by_number(second.name, second.client_id)

    assert resolved_first is not None
    assert resolved_second is not None
    assert str(resolved_first.id) == str(first.id)
    assert str(resolved_second.id) == str(second.id)


def test_update_project_by_id_only_touches_matching_same_name_project(repo):
    first = _create_project(repo, "Shared Project Update", client_id="CLIENT-UPDATE-A")
    second = _create_project(repo, "Shared Project Update", client_id="CLIENT-UPDATE-B")

    updated_first = first.model_copy(update={"description": "updated-first"})
    saved = repo.update_project(str(first.id), updated_first)

    assert saved is not None
    assert saved.description == "updated-first"
    assert repo.get_project_by_number(first.name, first.client_id).description == "updated-first"
    assert repo.get_project_by_number(second.name, second.client_id).description in (None, "")


def test_update_project_revives_deleted_cloud_tombstone(repo):
    project = _create_project(repo, "Revived Remote Project", client_id="CLIENT-PROJECT-REVIVE")
    remote_id = ObjectId()

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE projects
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (str(remote_id), project.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_projects = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "name": project.name,
                "client_id": project.client_id,
                "status": project.status.value,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(projects=cloud_projects)

    updated = project.model_copy(update={"description": "revived project details"})
    saved = repo.update_project(str(project.id), updated)

    cursor.execute(
        "SELECT sync_status, dirty_flag, is_deleted FROM projects WHERE id = ?",
        (project.id,),
    )
    row = cursor.fetchone()

    assert saved is not None
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_projects.documents[0]["description"] == "revived project details"
    assert cloud_projects.documents[0]["sync_status"] == "synced"
    assert cloud_projects.documents[0]["is_deleted"] is False


def test_delete_project_by_id_only_removes_matching_same_name_project(repo):
    first = _create_project(repo, "Shared Project Delete", client_id="CLIENT-DELETE-A")
    second = _create_project(repo, "Shared Project Delete", client_id="CLIENT-DELETE-B")

    assert repo.delete_project(str(first.id), client_id=first.client_id) is True

    assert repo.get_project_by_number(str(first.id), first.client_id) is None
    remaining = repo.get_project_by_number(second.name, second.client_id)
    assert remaining is not None
    assert str(remaining.id) == str(second.id)


def test_deleted_payment_signature_can_be_reused(repo):
    project = _create_project(repo, "Reusable Payment Signature", client_id="CLIENT-PAY-REUSE")
    payment = repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 20, 10, 0, 0),
            amount=250.0,
            account_id="1101",
            method="Cash",
        )
    )

    assert repo.delete_payment(payment.id) is True

    recreated = repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 20, 12, 0, 0),
            amount=250.0,
            account_id="1101",
            method="Cash",
        )
    )

    assert recreated.id != payment.id
    assert repo.get_total_paid_for_project(project.name) == pytest.approx(250.0)


def test_update_payment_revives_deleted_cloud_tombstone_with_row_mongo_id_fallback(repo):
    project = _create_project(repo, "Revived Payment Project", client_id="CLIENT-PAY-REVIVE")
    payment = repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 24, 10, 0, 0),
            amount=150.0,
            account_id="1101",
            method="Cash",
        )
    )
    remote_id = ObjectId()

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE payments
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (str(remote_id), payment.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_payments = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "project_id": payment.project_id,
                "client_id": payment.client_id,
                "date": payment.date,
                "amount": payment.amount,
                "account_id": payment.account_id,
                "method": payment.method,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(payments=cloud_payments)

    payment._mongo_id = None
    payment.amount = 225.0

    assert repo.update_payment(payment.id, payment) is True

    cursor.execute(
        "SELECT amount, sync_status, dirty_flag, is_deleted FROM payments WHERE id = ?",
        (payment.id,),
    )
    row = cursor.fetchone()

    assert float(row["amount"]) == pytest.approx(225.0)
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert float(cloud_payments.documents[0]["amount"]) == pytest.approx(225.0)
    assert cloud_payments.documents[0]["sync_status"] == "synced"
    assert cloud_payments.documents[0]["is_deleted"] is False


def test_update_expense_revives_deleted_cloud_tombstone_with_row_mongo_id_fallback(repo):
    project = _create_project(repo, "Revived Expense Project", client_id="CLIENT-EXP-REVIVE")
    expense = repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 24, 12, 0, 0),
            category="Logistics",
            amount=80.0,
            description="initial expense",
            account_id="5001",
            payment_account_id="1101",
        )
    )
    remote_id = ObjectId()

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE expenses
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (str(remote_id), expense.id),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_expenses = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "project_id": expense.project_id,
                "date": expense.date,
                "category": expense.category,
                "amount": expense.amount,
                "description": expense.description,
                "account_id": expense.account_id,
                "payment_account_id": expense.payment_account_id,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(expenses=cloud_expenses)

    expense._mongo_id = None
    expense.amount = 130.0
    expense.description = "revived expense"

    assert repo.update_expense(expense.id, expense) is True

    cursor.execute(
        "SELECT amount, description, sync_status, dirty_flag, is_deleted FROM expenses WHERE id = ?",
        (expense.id,),
    )
    row = cursor.fetchone()

    assert float(row["amount"]) == pytest.approx(130.0)
    assert row["description"] == "revived expense"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert float(cloud_expenses.documents[0]["amount"]) == pytest.approx(130.0)
    assert cloud_expenses.documents[0]["description"] == "revived expense"
    assert cloud_expenses.documents[0]["sync_status"] == "synced"
    assert cloud_expenses.documents[0]["is_deleted"] is False


def test_get_all_invoices_merges_local_unsynced_invoice_with_mongo_results(repo):
    local_project = _create_project(
        repo,
        "Local Pending Invoice Project",
        client_id="CLIENT-INV-LIST-LOCAL",
    )
    local_invoice = _create_invoice(repo, local_project, "INV-LIST-LOCAL-001")

    repo.online = True
    cloud_invoices = _FakeMongoCollection(
        [
            {
                "_id": "mongo-invoice-visible-1",
                "invoice_number": "INV-LIST-CLOUD-001",
                "client_id": "CLIENT-INV-LIST-CLOUD",
                "project_id": "Cloud Invoice Project",
                "issue_date": datetime(2026, 3, 1, 10, 0, 0),
                "due_date": datetime(2026, 3, 10, 10, 0, 0),
                "items": [],
                "subtotal": 300.0,
                "total_amount": 300.0,
                "status": schemas.InvoiceStatus.DRAFT.value,
                "amount_paid": 0.0,
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(invoices=cloud_invoices)

    invoices = repo.get_all_invoices()

    invoice_numbers = {invoice.invoice_number for invoice in invoices}

    assert invoice_numbers == {local_invoice.invoice_number, "INV-LIST-CLOUD-001"}


def test_get_all_invoices_prefers_local_pending_invoice_over_stale_mongo_copy(repo):
    local_project = _create_project(
        repo,
        "Merged Invoice Project",
        client_id="CLIENT-INV-LIST-MERGED",
    )
    local_invoice = _create_invoice(repo, local_project, "INV-LIST-MERGED-001")

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE invoices
        SET _mongo_id = ?, sync_status = 'modified_offline', dirty_flag = 1, notes = ?
        WHERE invoice_number = ?
        """,
        (
            "mongo-invoice-merge-1",
            "local pending invoice note",
            local_invoice.invoice_number,
        ),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_invoices = _FakeMongoCollection(
        [
            {
                "_id": "mongo-invoice-merge-1",
                "invoice_number": local_invoice.invoice_number,
                "client_id": local_invoice.client_id,
                "project_id": local_invoice.project_id,
                "issue_date": datetime(2026, 3, 1, 11, 0, 0),
                "due_date": datetime(2026, 3, 12, 11, 0, 0),
                "items": [],
                "subtotal": 500.0,
                "total_amount": 500.0,
                "status": schemas.InvoiceStatus.DRAFT.value,
                "amount_paid": 0.0,
                "notes": "cloud stale invoice note",
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(invoices=cloud_invoices)

    invoices = repo.get_all_invoices()
    merged_invoice = next(
        invoice for invoice in invoices if invoice.invoice_number == local_invoice.invoice_number
    )

    assert (
        len(
            [
                invoice
                for invoice in invoices
                if invoice.invoice_number == local_invoice.invoice_number
            ]
        )
        == 1
    )
    assert merged_invoice.notes == "local pending invoice note"


def test_update_invoice_after_payment_revives_deleted_cloud_tombstone(repo):
    project = _create_project(
        repo, "Revived Invoice Payment Project", client_id="CLIENT-INV-REVIVE"
    )
    invoice = _create_invoice(repo, project, "INV-REVIVE-PAYMENT-001")

    repo.online = True
    cloud_invoices = _FakeMongoCollection(
        [
            {
                "_id": "mongo-invoice-payment-revive-1",
                "invoice_number": invoice.invoice_number,
                "amount_paid": 0.0,
                "status": invoice.status.value,
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(invoices=cloud_invoices)

    updated = repo.update_invoice_after_payment(invoice.invoice_number, 125.0)

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "SELECT amount_paid, status, sync_status, dirty_flag, is_deleted FROM invoices WHERE invoice_number = ?",
        (invoice.invoice_number,),
    )
    row = cursor.fetchone()

    assert updated is not None
    assert float(row["amount_paid"]) == pytest.approx(125.0)
    assert row["status"] == schemas.InvoiceStatus.PARTIAL.value
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert float(cloud_invoices.documents[0]["amount_paid"]) == pytest.approx(125.0)
    assert cloud_invoices.documents[0]["status"] == schemas.InvoiceStatus.PARTIAL.value
    assert cloud_invoices.documents[0]["sync_status"] == "synced"
    assert cloud_invoices.documents[0]["is_deleted"] is False


def test_update_invoice_revives_deleted_cloud_tombstone(repo):
    project = _create_project(repo, "Revived Invoice Project", client_id="CLIENT-INV-EDIT")
    invoice = _create_invoice(repo, project, "INV-REVIVE-EDIT-001")

    repo.online = True
    cloud_invoices = _FakeMongoCollection(
        [
            {
                "_id": "mongo-invoice-edit-revive-1",
                "invoice_number": invoice.invoice_number,
                "status": invoice.status.value,
                "sync_status": "deleted",
                "is_deleted": True,
                "notes": "",
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(invoices=cloud_invoices)

    invoice.notes = "revived invoice edit"
    updated = repo.update_invoice(invoice.invoice_number, invoice)

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "SELECT notes, sync_status, dirty_flag, is_deleted FROM invoices WHERE invoice_number = ?",
        (invoice.invoice_number,),
    )
    row = cursor.fetchone()

    assert updated is not None
    assert row["notes"] == "revived invoice edit"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_invoices.documents[0]["notes"] == "revived invoice edit"
    assert cloud_invoices.documents[0]["sync_status"] == "synced"
    assert cloud_invoices.documents[0]["is_deleted"] is False


def test_update_task_revives_deleted_cloud_tombstone_using_row_mongo_id(repo):
    created_task = repo.create_task(
        {
            "title": "Pulled task",
            "priority": "MEDIUM",
            "status": "TODO",
            "category": "GENERAL",
            "tags": [],
            "reminder": False,
            "reminder_minutes": 30,
        }
    )
    remote_id = ObjectId()

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE tasks
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (str(remote_id), created_task["id"]),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_tasks = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "id": "source-device-task-1",
                "title": created_task["title"],
                "priority": created_task["priority"],
                "status": created_task["status"],
                "category": created_task["category"],
                "tags": [],
                "sync_status": "deleted",
                "is_deleted": True,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(tasks=cloud_tasks)

    updated_task = dict(created_task)
    updated_task.pop("_mongo_id", None)
    updated_task["title"] = "Pulled task updated"

    saved = repo.update_task(created_task["id"], updated_task)

    cursor.execute(
        "SELECT title, sync_status, dirty_flag, is_deleted FROM tasks WHERE id = ?",
        (created_task["id"],),
    )
    row = cursor.fetchone()

    assert saved["title"] == "Pulled task updated"
    assert row["title"] == "Pulled task updated"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0
    assert row["is_deleted"] == 0
    assert cloud_tasks.documents[0]["title"] == "Pulled task updated"
    assert cloud_tasks.documents[0]["sync_status"] == "synced"
    assert cloud_tasks.documents[0]["is_deleted"] is False


def test_delete_task_uses_row_mongo_id_when_remote_and_local_ids_differ(repo):
    created_task = repo.create_task(
        {
            "title": "Pulled task delete",
            "priority": "MEDIUM",
            "status": "TODO",
            "category": "GENERAL",
            "tags": [],
            "reminder": False,
            "reminder_minutes": 30,
        }
    )
    remote_id = ObjectId()

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        UPDATE tasks
        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
        WHERE id = ?
        """,
        (str(remote_id), created_task["id"]),
    )
    repo.sqlite_conn.commit()

    repo.online = True
    cloud_tasks = _FakeMongoCollection(
        [
            {
                "_id": remote_id,
                "id": "source-device-task-2",
                "title": created_task["title"],
                "priority": created_task["priority"],
                "status": created_task["status"],
                "category": created_task["category"],
                "tags": [],
                "sync_status": "synced",
                "is_deleted": False,
            }
        ]
    )
    repo.mongo_db = SimpleNamespace(tasks=cloud_tasks)

    assert repo.delete_task(created_task["id"]) is True

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE id = ?", (created_task["id"],))
    remaining = cursor.fetchone()[0]

    assert remaining == 0
    assert cloud_tasks.documents[0]["sync_status"] == "deleted"
    assert cloud_tasks.documents[0]["is_deleted"] is True


def test_service_name_can_be_reused_after_archive_and_delete(repo):
    archived_service = repo.create_service(
        schemas.Service(name="Reusable Service", default_price=100.0)
    )
    archived_service.status = schemas.ServiceStatus.ARCHIVED
    updated_archived = repo.update_service(str(archived_service.id), archived_service)

    assert updated_archived is not None

    recreated_after_archive = repo.create_service(
        schemas.Service(name="Reusable Service", default_price=120.0)
    )
    assert recreated_after_archive.id != archived_service.id

    deleted_service = repo.create_service(
        schemas.Service(name="Deleted Reusable Service", default_price=90.0)
    )
    assert repo.delete_service_permanently(str(deleted_service.id)) is True

    recreated_after_delete = repo.create_service(
        schemas.Service(name="Deleted Reusable Service", default_price=110.0)
    )
    assert recreated_after_delete.id != deleted_service.id


def test_update_service_rejects_duplicate_active_name(repo):
    first = repo.create_service(schemas.Service(name="Primary Service", default_price=100.0))
    second = repo.create_service(schemas.Service(name="Secondary Service", default_price=120.0))

    second.name = first.name

    with pytest.raises(ValueError):
        repo.update_service(str(second.id), second)
