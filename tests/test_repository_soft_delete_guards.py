from __future__ import annotations

from datetime import datetime

import pytest

from core import schemas


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
    assert repo.sum_expenses_charged_before("5001", "2026-02-20T00:00:00") == pytest.approx(
        float(charged_expense.amount)
    )


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
