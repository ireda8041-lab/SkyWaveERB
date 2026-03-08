from __future__ import annotations

from datetime import datetime

import pytest

from core import schemas


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    import core.repository as repo_mod

    db_path = tmp_path / "repo_payments_linking.db"
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
    project = schemas.Project(name=name, client_id=client_id, total_amount=1000.0)
    return repo.create_project(project)


def test_create_project_prefers_mongo_client_reference_for_synced_client(repo):
    client = repo.create_client(schemas.Client(name="Synced Project Client"))
    assert client.id is not None

    repo.sqlite_conn.execute(
        "UPDATE clients SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-client-project-1", int(client.id)),
    )
    repo.sqlite_conn.commit()

    project = repo.create_project(
        schemas.Project(
            name="Project Uses Stable Client Ref",
            client_id=str(client.id),
            total_amount=1200.0,
        )
    )

    assert project.client_id == "mongo-client-project-1"
    stored = repo.get_project_by_number(str(project.id), "mongo-client-project-1")
    assert stored is not None
    assert stored.client_id == "mongo-client-project-1"


def test_update_project_normalizes_legacy_local_client_reference_to_mongo_id(repo):
    client = repo.create_client(schemas.Client(name="Legacy Client Ref"))
    assert client.id is not None

    repo.sqlite_conn.execute(
        "UPDATE clients SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-client-project-2", int(client.id)),
    )
    repo.sqlite_conn.commit()

    project = repo.create_project(
        schemas.Project(
            name="Legacy Project Client Link",
            client_id="mongo-client-project-2",
            total_amount=900.0,
        )
    )
    assert project.id is not None
    assert project.invoice_number

    # Simulate a legacy local-only client link stored before the client received a mongo id.
    repo.sqlite_conn.execute(
        "UPDATE projects SET client_id = ? WHERE id = ?",
        (str(client.id), int(project.id)),
    )
    repo.sqlite_conn.commit()

    current = repo.get_project_by_number(str(project.id), str(client.id))
    assert current is not None
    current.project_notes = "normalized on update"

    saved = repo.update_project(str(project.id), current)

    assert saved is not None
    assert saved.client_id == "mongo-client-project-2"
    refreshed = repo.get_project_by_number(str(project.id), "mongo-client-project-2")
    assert refreshed is not None
    assert refreshed.client_id == "mongo-client-project-2"


def test_update_project_succeeds_inside_existing_sqlite_transaction(repo):
    project = repo.create_project(
        schemas.Project(
            name="Nested Transaction Project",
            client_id="CLIENT-NESTED-TX",
            total_amount=1500.0,
        )
    )
    assert project.id is not None

    current = repo.get_project_by_number(str(project.id), "CLIENT-NESTED-TX")
    assert current is not None
    current.project_notes = "updated inside transaction"

    repo.sqlite_conn.execute("BEGIN")
    try:
        saved = repo.update_project(str(project.id), current)
        assert saved is not None
        repo.sqlite_conn.commit()
    finally:
        if repo.sqlite_conn.in_transaction:
            repo.sqlite_conn.rollback()

    refreshed = repo.get_project_by_number(str(project.id), "CLIENT-NESTED-TX")
    assert refreshed is not None
    assert refreshed.project_notes == "updated inside transaction"


def test_create_payment_resolves_project_id_and_client_id(repo):
    project = _create_project(repo, "مشروع ربط الدفعات")
    assert project.id is not None

    payment = schemas.Payment(
        project_id=str(project.id),  # مرجع رقمي بدل الاسم
        client_id="",  # بدون عميل
        date=datetime(2026, 2, 21, 12, 0, 0),
        amount=250.0,
        account_id="1101",
        method="Cash",
    )
    created = repo.create_payment(payment)

    assert created.project_id == str(project.id)
    assert created.client_id == project.client_id
    assert created.invoice_number == project.invoice_number


def test_create_payment_prefers_mongo_id_for_synced_project(repo):
    project = _create_project(repo, "Synced Payment Project", client_id="CLIENT-SYNC-PAY")
    assert project.id is not None

    repo.sqlite_conn.execute(
        "UPDATE projects SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-project-sync-pay-1", int(project.id)),
    )
    repo.sqlite_conn.commit()

    created = repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 21, 12, 5, 0),
            amount=275.0,
            account_id="1101",
            method="Cash",
        )
    )

    assert created.project_id == "mongo-project-sync-pay-1"
    refreshed = repo.get_payment_by_id(created.id)
    assert refreshed is not None
    assert refreshed.project_id == "mongo-project-sync-pay-1"


def test_create_payment_rejects_ambiguous_duplicate_project_name_reference(repo):
    first = _create_project(repo, "Ambiguous Payment Project", client_id="CLIENT-PAY-1")
    _create_project(repo, "Ambiguous Payment Project", client_id="CLIENT-PAY-2")

    with pytest.raises(ValueError, match="اسم المشروع غير فريد"):
        repo.create_payment(
            schemas.Payment(
                project_id=first.name,
                client_id="",
                date=datetime(2026, 2, 21, 12, 30, 0),
                amount=120.0,
                account_id="1101",
                method="Cash",
            )
        )


def test_update_payment_keeps_canonical_project_reference(repo):
    project = _create_project(repo, "مشروع تحديث مرجعي", client_id="CLIENT-22")
    assert project.invoice_number

    created = repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 21, 13, 0, 0),
            amount=100.0,
            account_id="1101",
            method="Cash",
        )
    )

    created.project_id = str(project.id)  # إدخال مرجع غير قانوني عند التعديل
    created.client_id = ""
    created.amount = 175.0

    assert repo.update_payment(created.id, created) is True

    refreshed = repo.get_payment_by_id(created.id)
    assert refreshed is not None
    assert refreshed.project_id == str(project.id)
    assert refreshed.client_id == project.client_id
    assert refreshed.invoice_number == project.invoice_number


def test_update_payment_project_refreshes_invoice_number(repo):
    first_project = _create_project(repo, "Payment Invoice Source 1", client_id="CLIENT-PAY-INV-1")
    second_project = _create_project(repo, "Payment Invoice Source 2", client_id="CLIENT-PAY-INV-2")
    assert first_project.invoice_number
    assert second_project.invoice_number

    created = repo.create_payment(
        schemas.Payment(
            project_id=str(first_project.id),
            client_id=first_project.client_id,
            date=datetime(2026, 2, 21, 13, 10, 0),
            amount=190.0,
            account_id="1101",
            method="Cash",
        )
    )

    created.project_id = str(second_project.id)
    created.client_id = second_project.client_id
    created.amount = 225.0

    assert repo.update_payment(created.id, created) is True

    refreshed = repo.get_payment_by_id(created.id)
    assert refreshed is not None
    assert refreshed.project_id == str(second_project.id)
    assert refreshed.client_id == second_project.client_id
    assert refreshed.invoice_number == second_project.invoice_number


def test_update_payment_rejects_ambiguous_duplicate_project_name_reference(repo):
    first = _create_project(repo, "Ambiguous Update Payment Project", client_id="CLIENT-UP-1")
    _create_project(repo, "Ambiguous Update Payment Project", client_id="CLIENT-UP-2")

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO payments (
            sync_status, created_at, last_modified, project_id, client_id,
            date, amount, account_id, method, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-21T13:15:00",
            "2026-02-21T13:15:00",
            first.name,
            "",
            "2026-02-21T13:15:00",
            100.0,
            "1101",
            "Cash",
            1,
            0,
        ),
    )
    repo.sqlite_conn.commit()
    payment_id = cursor.lastrowid

    created = repo.get_payment_by_id(payment_id)
    assert created is not None

    with pytest.raises(ValueError, match="اسم المشروع غير فريد"):
        repo.update_payment(payment_id, created)

    refreshed = repo.get_payment_by_id(payment_id)
    assert refreshed is not None
    assert refreshed.project_id == first.name
    assert refreshed.client_id == ""


def test_update_payment_rejects_duplicate_signature(repo):
    project = _create_project(repo, "No duplicate payment update", client_id="CLIENT-22")

    first_payment = repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 21, 13, 0, 0),
            amount=50.0,
            account_id="1101",
            method="Cash",
        )
    )
    second_payment = repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 22, 14, 0, 0),
            amount=60.0,
            account_id="1101",
            method="Cash",
        )
    )

    second_payment.date = first_payment.date
    second_payment.amount = first_payment.amount

    with pytest.raises(ValueError):
        repo.update_payment(second_payment.id, second_payment)

    refreshed = repo.get_payment_by_id(second_payment.id)
    assert refreshed is not None
    assert refreshed.date == datetime(2026, 2, 22, 14, 0, 0)
    assert float(refreshed.amount) == pytest.approx(60.0)
    assert repo.get_total_paid_for_project(project.name) == pytest.approx(110.0)


def test_get_total_paid_for_project_uses_aliases(repo):
    project = _create_project(repo, "مشروع مجموع المدفوعات", client_id="CLIENT-33")

    repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 21, 14, 0, 0),
            amount=200.0,
            account_id="1101",
            method="Cash",
        )
    )
    repo.create_payment(
        schemas.Payment(
            project_id=str(project.id),  # نفس المشروع لكن مرجع رقمي
            client_id="",
            date=datetime(2026, 2, 21, 14, 30, 0),
            amount=50.0,
            account_id="1101",
            method="Cash",
        )
    )

    assert repo.get_total_paid_for_project(project.name) == pytest.approx(250.0)


def test_get_all_invoice_numbers_preserves_duplicate_project_names_by_stable_key(repo):
    first = _create_project(repo, "Shared Invoice Dictionary", client_id="CLIENT-INVOICE-1")
    second = _create_project(repo, "Shared Invoice Dictionary", client_id="CLIENT-INVOICE-2")

    first_invoice = repo.ensure_invoice_number(str(first.id), first.client_id)
    second_invoice = repo.ensure_invoice_number(str(second.id), second.client_id)

    invoice_numbers = repo.get_all_invoice_numbers()

    assert invoice_numbers[str(first.id)] == first_invoice
    assert invoice_numbers[str(second.id)] == second_invoice


def test_legacy_numeric_project_links_are_counted_for_expenses_and_payments(repo):
    project = _create_project(repo, "Legacy project links", client_id="CLIENT-44")

    # Legacy rows may keep numeric project_id values.
    repo.create_payment(
        schemas.Payment(
            project_id=str(project.id),
            client_id="",
            date=datetime(2026, 2, 21, 15, 0, 0),
            amount=120.0,
            account_id="1101",
            method="Cash",
        )
    )
    repo.create_expense(
        schemas.Expense(
            project_id=str(project.id),
            date=datetime(2026, 2, 21, 15, 30, 0),
            category="Legacy expense",
            amount=35.0,
            description="legacy",
            account_id="5001",
        )
    )

    assert repo.get_total_paid_for_project(project.name) == pytest.approx(120.0)
    assert repo.get_total_expenses_for_project(project.name) == pytest.approx(35.0)
    expenses = repo.get_expenses_for_project(project.name)
    assert sum(float(e.amount) for e in expenses) == pytest.approx(35.0)


def test_create_expense_rejects_duplicate_signature(repo):
    project = _create_project(repo, "No duplicate expense", client_id="CLIENT-55")

    repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 22, 10, 0, 0),
            category="Marketing",
            amount=2600.0,
            description="Ads campaign",
            account_id="5001",
            payment_account_id="1101",
        )
    )

    with pytest.raises(ValueError):
        repo.create_expense(
            schemas.Expense(
                project_id=project.name,
                date=datetime(2026, 2, 22, 10, 5, 0),
                category="Marketing",
                amount=2600.0,
                description="Ads campaign",
                account_id="5001",
                payment_account_id="1101",
            )
        )


def test_update_expense_rejects_duplicate_signature(repo):
    project = _create_project(repo, "No duplicate expense update", client_id="CLIENT-56")

    first_expense = repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 22, 10, 0, 0),
            category="Marketing",
            amount=2600.0,
            description="Ads campaign",
            account_id="5001",
            payment_account_id="1101",
        )
    )
    second_expense = repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 23, 10, 0, 0),
            category="Marketing",
            amount=3100.0,
            description="Second campaign",
            account_id="5001",
            payment_account_id="1101",
        )
    )

    second_expense.date = first_expense.date
    second_expense.amount = first_expense.amount
    second_expense.description = first_expense.description

    with pytest.raises(ValueError):
        repo.update_expense(second_expense.id, second_expense)

    refreshed = repo.get_expense_by_id(second_expense.id)
    assert refreshed is not None
    assert refreshed.date == datetime(2026, 2, 23, 10, 0, 0)
    assert float(refreshed.amount) == pytest.approx(3100.0)
    assert repo.get_total_expenses_for_project(project.name) == pytest.approx(5700.0)


def test_update_expense_normalizes_project_and_payment_account_and_sync_marker(repo):
    project = _create_project(repo, "Expense update canonical ref", client_id="CLIENT-57")

    created = repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 22, 11, 0, 0),
            category="Operations",
            amount=450.0,
            description="Office",
            account_id="5001",
            payment_account_id="1101",
        )
    )
    assert created.id is not None

    created.project_id = str(project.id)
    created.account_id = "5002"
    created.payment_account_id = ""
    created.amount = 500.0

    assert repo.update_expense(created.id, created) is True

    refreshed = repo.get_expense_by_id(created.id)
    assert refreshed is not None
    assert refreshed.project_id == str(project.id)
    assert refreshed.payment_account_id == "5002"
    assert refreshed.sync_status == "modified_offline"


def test_get_expenses_for_project_prefers_synced_copy_over_duplicate_local_row(repo):
    project = _create_project(repo, "Dedup expense lookup", client_id="CLIENT-66")

    created = repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 23, 11, 0, 0),
            category="Social Media",
            amount=7700.0,
            description="Ad set",
            account_id="5001",
            payment_account_id="1101",
        )
    )
    assert created.id is not None

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO expenses (
            _mongo_id, sync_status, created_at, last_modified,
            date, category, amount, description, account_id, payment_account_id, project_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-exp-shadow-1",
            "synced",
            "2026-02-23T11:00:00",
            "2026-02-23T11:00:00",
            "2026-02-23T11:00:00",
            "Social Media",
            7700.0,
            "Ad set",
            "5001",
            "1101",
            project.name,
        ),
    )
    repo.sqlite_conn.commit()

    expenses = repo.get_expenses_for_project(project.name)

    assert len(expenses) == 1
    assert float(expenses[0].amount) == pytest.approx(7700.0)
    assert expenses[0]._mongo_id == "mongo-exp-shadow-1"
    assert repo.get_total_expenses_for_project(project.name) == pytest.approx(7700.0)


def test_get_payments_for_project_matches_whitespace_variants(repo):
    project = _create_project(repo, "Project WS 2  - Client", client_id="CLIENT-77")

    repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 24, 9, 0, 0),
            amount=4500.0,
            account_id="1101",
            method="Cash",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO payments (
            _mongo_id, sync_status, created_at, last_modified,
            project_id, client_id, date, amount, account_id, method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-pay-ws-shadow-1",
            "synced",
            "2026-02-24T09:30:00",
            "2026-02-24T09:30:00",
            "Project WS 2       - Client",
            project.client_id,
            "2026-02-24T09:30:00",
            4500.0,
            "1101",
            "Cash",
        ),
    )
    repo.sqlite_conn.commit()

    payments = repo.get_payments_for_project(project.name)
    assert len(payments) == 1
    assert repo.get_total_paid_for_project(project.name) == pytest.approx(4500.0)


def test_get_payments_for_project_ignores_soft_deleted_rows(repo):
    project = _create_project(repo, "Soft deleted payment", client_id="CLIENT-78")

    repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 24, 12, 0, 0),
            amount=600.0,
            account_id="1101",
            method="Cash",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO payments (
            _mongo_id, sync_status, created_at, last_modified,
            project_id, client_id, date, amount, account_id, method, is_deleted, dirty_flag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-pay-soft-deleted-1",
            "synced",
            "2026-02-24T12:30:00",
            "2026-02-24T12:30:00",
            project.name,
            project.client_id,
            "2026-02-24T12:30:00",
            999.0,
            "1101",
            "Cash",
            1,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    payments = repo.get_payments_for_project(project.name)
    assert len(payments) == 1
    assert repo.get_total_paid_for_project(project.name) == pytest.approx(600.0)


def test_get_payments_by_account_ignores_soft_deleted_rows(repo):
    project = _create_project(repo, "Soft deleted account payment", client_id="CLIENT-78B")

    repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 24, 12, 0, 0),
            amount=600.0,
            account_id="1101",
            method="Cash",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO payments (
            _mongo_id, sync_status, created_at, last_modified,
            project_id, client_id, date, amount, account_id, method, is_deleted, dirty_flag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-pay-soft-account-1",
            "synced",
            "2026-02-24T12:30:00",
            "2026-02-24T12:30:00",
            project.name,
            project.client_id,
            "2026-02-24T12:30:00",
            999.0,
            "1101",
            "Cash",
            1,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    payments = repo.get_payments_by_account("1101", "2026-02-24T00:00:00", "2026-02-25T00:00:00")
    assert len(payments) == 1
    assert float(payments[0].amount) == pytest.approx(600.0)


def test_get_expenses_for_project_ignores_soft_deleted_rows(repo):
    project = _create_project(repo, "Soft deleted expense", client_id="CLIENT-79")

    repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 24, 13, 0, 0),
            category="Ops",
            amount=150.0,
            description="valid",
            account_id="5001",
            payment_account_id="1101",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO expenses (
            _mongo_id, sync_status, created_at, last_modified,
            date, category, amount, description, account_id, payment_account_id, project_id, is_deleted, dirty_flag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "mongo-exp-soft-deleted-1",
            "synced",
            "2026-02-24T13:30:00",
            "2026-02-24T13:30:00",
            "2026-02-24T13:30:00",
            "Ops",
            999.0,
            "stale",
            "5001",
            "1101",
            project.name,
            1,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    expenses = repo.get_expenses_for_project(project.name)
    assert len(expenses) == 1
    assert repo.get_total_expenses_for_project(project.name) == pytest.approx(150.0)


def test_update_project_cascades_related_rows_and_fixed_invoice_number(repo):
    project = _create_project(repo, "Project Old", client_id="CLIENT-80")
    fixed_invoice_number = repo.get_invoice_number_for_project(project.name)
    assert fixed_invoice_number

    repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 24, 15, 0, 0),
            amount=320.0,
            account_id="1101",
            method="Cash",
        )
    )
    repo.create_payment(
        schemas.Payment(
            project_id=str(project.id),
            client_id=project.client_id,
            date=datetime(2026, 2, 24, 15, 30, 0),
            amount=35.0,
            account_id="1101",
            method="Cash",
        )
    )
    repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 24, 16, 0, 0),
            category="Ops",
            amount=70.0,
            description="rename-sensitive",
            account_id="5001",
            payment_account_id="1101",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO payments (
            sync_status, created_at, last_modified, project_id, client_id,
            date, amount, account_id, method, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-24T15:45:00",
            "2026-02-24T15:45:00",
            project.name,
            project.client_id,
            "2026-02-24T15:45:00",
            45.0,
            "1101",
            "Cash",
            1,
            0,
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
            "new_offline",
            "2026-02-24T16:15:00",
            "2026-02-24T16:15:00",
            "2026-02-24T16:15:00",
            "Legacy Ops",
            15.0,
            "legacy-rename-sensitive",
            "5001",
            "1101",
            project.name,
            1,
            0,
        ),
    )
    cursor.execute(
        """
        INSERT INTO invoices (
            sync_status, created_at, last_modified, invoice_number, client_id,
            issue_date, due_date, items, subtotal, discount_rate, discount_amount,
            tax_rate, tax_amount, total_amount, amount_paid, status, currency, notes, project_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-24T17:00:00",
            "2026-02-24T17:00:00",
            "RENAME-INV-001",
            project.client_id,
            "2026-02-24T17:00:00",
            "2026-03-03T17:00:00",
            "[]",
            500.0,
            0.0,
            0.0,
            0.0,
            0.0,
            500.0,
            0.0,
            schemas.InvoiceStatus.DRAFT.value,
            schemas.CurrencyCode.EGP.value,
            "",
            project.name,
        ),
    )
    cursor.execute(
        """
        INSERT INTO tasks (
            sync_status, created_at, last_modified, title, priority, status, category,
            related_project_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-24T17:15:00",
            "2026-02-24T17:15:00",
            "Rename task",
            "MEDIUM",
            "TODO",
            "GENERAL",
            project.name,
            1,
            0,
        ),
    )
    cursor.execute(
        """
        INSERT INTO project_milestones (
            project_id, name, percentage, amount, due_date, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project.name,
            "Phase 1",
            25.0,
            125.0,
            "2026-03-01T00:00:00",
            "pending",
            "2026-02-24T17:20:00",
        ),
    )
    repo.sqlite_conn.commit()

    updated_project = project.model_copy(update={"name": "Project New"})
    saved = repo.update_project(str(project.id), updated_project)

    assert saved is not None
    assert saved.name == "Project New"
    assert repo.get_total_paid_for_project("Project New") == pytest.approx(400.0)
    assert repo.get_total_expenses_for_project("Project New") == pytest.approx(85.0)
    assert repo.get_invoice_number_for_project("Project New") == fixed_invoice_number
    assert len(repo.get_invoices_for_project("Project New")) == 1
    assert len(repo.get_tasks_by_project("Project New")) == 1

    cursor.execute("SELECT project_id FROM payments")
    assert {str(row[0]) for row in cursor.fetchall()} == {str(project.id)}
    cursor.execute("SELECT project_id FROM expenses")
    assert {str(row[0]) for row in cursor.fetchall()} == {str(project.id)}
    cursor.execute("SELECT project_id FROM invoices WHERE invoice_number = ?", ("RENAME-INV-001",))
    assert str(cursor.fetchone()[0]) == str(project.id)
    cursor.execute("SELECT related_project_id FROM tasks WHERE title = ?", ("Rename task",))
    assert str(cursor.fetchone()[0]) == str(project.id)
    cursor.execute("SELECT project_id FROM project_milestones WHERE name = ?", ("Phase 1",))
    assert str(cursor.fetchone()[0]) == str(project.id)
    cursor.execute(
        "SELECT project_id, project_name FROM invoice_numbers WHERE invoice_number = ?",
        (fixed_invoice_number,),
    )
    invoice_row = cursor.fetchone()
    assert invoice_row is not None
    assert str(invoice_row[0]) == str(project.id)
    assert invoice_row[1] == "Project New"


def test_delete_project_cascades_related_rows_and_fixed_invoice_number(repo):
    project = _create_project(repo, "Project Delete Cascade", client_id="CLIENT-80B")
    fixed_invoice_number = repo.get_invoice_number_for_project(project.name)
    assert fixed_invoice_number

    repo.create_payment(
        schemas.Payment(
            project_id=project.name,
            client_id=project.client_id,
            date=datetime(2026, 2, 24, 18, 0, 0),
            amount=320.0,
            account_id="1101",
            method="Cash",
        )
    )
    repo.create_expense(
        schemas.Expense(
            project_id=project.name,
            date=datetime(2026, 2, 24, 19, 0, 0),
            category="Ops",
            amount=70.0,
            description="delete-sensitive",
            account_id="5001",
            payment_account_id="1101",
        )
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO invoices (
            sync_status, created_at, last_modified, invoice_number, client_id,
            issue_date, due_date, items, subtotal, discount_rate, discount_amount,
            tax_rate, tax_amount, total_amount, amount_paid, status, currency, notes,
            project_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-24T20:00:00",
            "2026-02-24T20:00:00",
            "DELETE-INV-001",
            project.client_id,
            "2026-02-24T20:00:00",
            "2026-03-03T20:00:00",
            "[]",
            500.0,
            0.0,
            0.0,
            0.0,
            0.0,
            500.0,
            0.0,
            schemas.InvoiceStatus.DRAFT.value,
            schemas.CurrencyCode.EGP.value,
            "",
            project.name,
            1,
            0,
        ),
    )
    cursor.execute(
        """
        INSERT INTO tasks (
            sync_status, created_at, last_modified, title, priority, status, category,
            related_project_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-24T21:00:00",
            "2026-02-24T21:00:00",
            "Delete task",
            "MEDIUM",
            "TODO",
            "GENERAL",
            project.name,
            1,
            0,
        ),
    )
    cursor.execute(
        """
        INSERT INTO project_milestones (
            project_id, name, percentage, amount, due_date, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project.name,
            "Phase 1",
            50.0,
            500.0,
            "2026-03-01T00:00:00",
            "pending",
            "2026-02-24T21:05:00",
        ),
    )
    repo.sqlite_conn.commit()

    assert repo.delete_project(project.name) is True

    assert repo.get_project_by_number(project.name) is None
    assert repo.get_payments_for_project(project.name) == []
    assert repo.get_expenses_for_project(project.name) == []
    assert repo.get_invoices_for_project(project.name) == []
    assert repo.get_invoice_number_for_project(project.name) == ""

    cursor.execute(
        "SELECT sync_status, is_deleted FROM payments WHERE project_id = ?", (str(project.id),)
    )
    assert tuple(cursor.fetchone()) == ("deleted", 1)
    cursor.execute(
        "SELECT sync_status, is_deleted FROM expenses WHERE project_id = ?", (str(project.id),)
    )
    assert tuple(cursor.fetchone()) == ("deleted", 1)
    cursor.execute(
        "SELECT sync_status, is_deleted FROM invoices WHERE project_id = ?", (project.name,)
    )
    assert tuple(cursor.fetchone()) == ("deleted", 1)
    cursor.execute(
        "SELECT sync_status, is_deleted FROM tasks WHERE related_project_id = ?",
        (project.name,),
    )
    assert tuple(cursor.fetchone()) == ("deleted", 1)
    cursor.execute("SELECT COUNT(*) FROM project_milestones WHERE project_id = ?", (project.name,))
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM invoice_numbers WHERE project_name = ?", (project.name,))
    assert cursor.fetchone()[0] == 0


def test_project_code_and_invoice_number_aliases_resolve_legacy_payment_and_expense_rows(repo):
    project = _create_project(repo, "Legacy alias project", client_id="CLIENT-81")
    fixed_invoice_number = repo.get_invoice_number_for_project(project.name)
    assert fixed_invoice_number

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "UPDATE projects SET project_code = ?, invoice_number = ? WHERE id = ?",
        ("CODE-001", fixed_invoice_number, project.id),
    )
    cursor.execute(
        """
        INSERT INTO payments (
            sync_status, created_at, last_modified, project_id, client_id,
            date, amount, account_id, method, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-25T09:00:00",
            "2026-02-25T09:00:00",
            "CODE-001",
            project.client_id,
            "2026-02-25T09:00:00",
            180.0,
            "1101",
            "Cash",
            1,
            0,
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
            "new_offline",
            "2026-02-25T10:00:00",
            "2026-02-25T10:00:00",
            "2026-02-25T10:00:00",
            "Legacy",
            40.0,
            "linked by invoice number",
            "5001",
            "1101",
            fixed_invoice_number,
            1,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    payments_by_name = repo.get_payments_for_project(project.name)
    payments_by_code = repo.get_payments_for_project("CODE-001")
    expenses_by_name = repo.get_expenses_for_project(project.name)
    expenses_by_invoice_number = repo.get_expenses_for_project(fixed_invoice_number)

    assert len(payments_by_name) == 1
    assert len(payments_by_code) == 1
    assert float(payments_by_name[0].amount) == pytest.approx(180.0)
    assert repo.get_total_paid_for_project(project.name) == pytest.approx(180.0)

    assert len(expenses_by_name) == 1
    assert len(expenses_by_invoice_number) == 1
    assert float(expenses_by_name[0].amount) == pytest.approx(40.0)
    assert repo.get_total_expenses_for_project(project.name) == pytest.approx(40.0)


def test_get_invoices_for_project_supports_aliases_and_ignores_soft_deleted_rows(repo):
    project = _create_project(repo, "Legacy invoice alias project", client_id="CLIENT-82")
    fixed_invoice_number = repo.get_invoice_number_for_project(project.name)
    assert fixed_invoice_number

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "UPDATE projects SET project_code = ?, invoice_number = ? WHERE id = ?",
        ("CODE-INV-001", fixed_invoice_number, project.id),
    )
    cursor.execute(
        """
        INSERT INTO invoices (
            sync_status, created_at, last_modified, invoice_number, client_id,
            issue_date, due_date, items, subtotal, discount_rate, discount_amount,
            tax_rate, tax_amount, total_amount, amount_paid, status, currency, notes,
            project_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-25T11:00:00",
            "2026-02-25T11:00:00",
            "LEGACY-ACTIVE-INV-001",
            project.client_id,
            "2026-02-25T11:00:00",
            "2026-03-04T11:00:00",
            "[]",
            900.0,
            0.0,
            0.0,
            0.0,
            0.0,
            900.0,
            0.0,
            schemas.InvoiceStatus.DRAFT.value,
            schemas.CurrencyCode.EGP.value,
            "",
            "CODE-INV-001",
            1,
            0,
        ),
    )
    cursor.execute(
        """
        INSERT INTO invoices (
            sync_status, created_at, last_modified, invoice_number, client_id,
            issue_date, due_date, items, subtotal, discount_rate, discount_amount,
            tax_rate, tax_amount, total_amount, amount_paid, status, currency, notes,
            project_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "deleted",
            "2026-02-25T12:00:00",
            "2026-02-25T12:00:00",
            "LEGACY-DELETED-INV-001",
            project.client_id,
            "2026-02-25T12:00:00",
            "2026-03-04T12:00:00",
            "[]",
            1200.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1200.0,
            0.0,
            schemas.InvoiceStatus.DRAFT.value,
            schemas.CurrencyCode.EGP.value,
            "",
            "CODE-INV-001",
            1,
            1,
        ),
    )
    repo.sqlite_conn.commit()

    invoices_by_name = repo.get_invoices_for_project(project.name)
    invoices_by_code = repo.get_invoices_for_project("CODE-INV-001")
    invoices_by_fixed_number = repo.get_invoices_for_project(fixed_invoice_number)

    assert len(invoices_by_name) == 1
    assert len(invoices_by_code) == 1
    assert len(invoices_by_fixed_number) == 1
    assert invoices_by_name[0].invoice_number == "LEGACY-ACTIVE-INV-001"


def test_ambiguous_project_code_does_not_cross_link_payments(repo):
    p1 = _create_project(repo, "Project Code A", client_id="CLIENT-88")
    p2 = _create_project(repo, "Project Code B", client_id="CLIENT-88")

    assert p1.id is not None
    assert p2.id is not None

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "UPDATE projects SET project_code = ?, invoice_number = ? WHERE id = ?",
        ("2026-CODE-SHARED-001", "INV-A", p1.id),
    )
    cursor.execute(
        "UPDATE projects SET project_code = ?, invoice_number = ? WHERE id = ?",
        ("2026-CODE-SHARED-001", "INV-B", p2.id),
    )
    repo.sqlite_conn.commit()

    repo.create_payment(
        schemas.Payment(
            project_id=p1.name,
            client_id=p1.client_id,
            date=datetime(2026, 2, 24, 11, 0, 0),
            amount=123.0,
            account_id="1101",
            method="Cash",
        )
    )

    payments_by_code = repo.get_payments_for_project("2026-CODE-SHARED-001")
    assert payments_by_code == []


def test_tasks_project_lookup_uses_aliases_and_ignores_soft_deleted_rows(repo):
    project = _create_project(repo, "Legacy task alias project", client_id="CLIENT-89")
    fixed_invoice_number = repo.get_invoice_number_for_project(project.name)
    assert fixed_invoice_number

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "UPDATE projects SET project_code = ?, invoice_number = ? WHERE id = ?",
        ("TASK-CODE-001", fixed_invoice_number, project.id),
    )
    repo.sqlite_conn.commit()

    created_task = repo.create_task(
        {
            "title": "Canonical task",
            "priority": "MEDIUM",
            "status": "TODO",
            "category": "GENERAL",
            "related_project_id": "TASK-CODE-001",
            "tags": [],
            "reminder": False,
            "reminder_minutes": 30,
        }
    )
    assert created_task["id"]

    cursor.execute("SELECT related_project_id FROM tasks WHERE id = ?", (created_task["id"],))
    assert cursor.fetchone()[0] == str(project.id)

    created_task["title"] = "Canonical task updated"
    created_task["related_project_id"] = fixed_invoice_number
    repo.update_task(created_task["id"], created_task)

    cursor.execute("SELECT related_project_id FROM tasks WHERE id = ?", (created_task["id"],))
    assert cursor.fetchone()[0] == str(project.id)

    cursor.execute(
        """
        INSERT INTO tasks (
            sync_status, created_at, last_modified, title, priority, status, category,
            related_project_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "deleted",
            "2026-02-25T13:00:00",
            "2026-02-25T13:00:00",
            "Deleted alias task",
            "MEDIUM",
            "TODO",
            "GENERAL",
            project.name,
            1,
            1,
        ),
    )
    repo.sqlite_conn.commit()

    tasks_by_name = repo.get_tasks_by_project(project.name)
    tasks_by_code = repo.get_tasks_by_project("TASK-CODE-001")
    tasks_by_invoice_number = repo.get_tasks_by_project(fixed_invoice_number)

    assert len(tasks_by_name) == 1
    assert len(tasks_by_code) == 1
    assert len(tasks_by_invoice_number) == 1
    assert tasks_by_name[0]["title"] == "Canonical task updated"


def test_duplicate_project_names_keep_payments_and_expenses_scoped_to_stable_reference(repo):
    p1 = _create_project(repo, "Shared Name", client_id="CLIENT-A")
    p2 = _create_project(repo, "Shared Name", client_id="CLIENT-B")

    created_payment = repo.create_payment(
        schemas.Payment(
            project_id=p1.name,
            client_id=p1.client_id,
            date=datetime(2026, 2, 26, 9, 0, 0),
            amount=125.0,
            account_id="1101",
            method="Cash",
        )
    )
    created_expense = repo.create_expense(
        schemas.Expense(
            project_id=str(p2.id),
            date=datetime(2026, 2, 26, 11, 0, 0),
            category="Ops",
            amount=45.0,
            description="Shared name expense",
            account_id="5001",
            payment_account_id="1101",
        )
    )

    assert created_payment.project_id == str(p1.id)
    assert created_expense.project_id == str(p2.id)
    assert repo.get_payments_for_project(p1.name) == []
    assert len(repo.get_payments_for_project(str(p1.id), client_id=p1.client_id)) == 1
    assert repo.get_total_paid_for_project(str(p1.id), client_id=p1.client_id) == pytest.approx(
        125.0
    )
    assert repo.get_total_paid_for_project(str(p2.id), client_id=p2.client_id) == pytest.approx(0.0)
    assert len(repo.get_expenses_for_project(str(p2.id))) == 1
    assert repo.get_total_expenses_for_project(str(p2.id)) == pytest.approx(45.0)
    assert repo.get_total_expenses_for_project(str(p1.id)) == pytest.approx(0.0)


def test_create_expense_rejects_ambiguous_duplicate_project_name_reference(repo):
    p1 = _create_project(repo, "Shared Expense Name", client_id="CLIENT-E1")
    _create_project(repo, "Shared Expense Name", client_id="CLIENT-E2")

    with pytest.raises(ValueError, match="غير فريد"):
        repo.create_expense(
            schemas.Expense(
                project_id=p1.name,
                date=datetime(2026, 2, 26, 12, 0, 0),
                category="Ops",
                amount=30.0,
                description="ambiguous duplicate expense",
                account_id="5001",
                payment_account_id="1101",
            )
        )

    assert repo.get_all_expenses() == []


def test_legacy_ambiguous_expense_name_is_hidden_for_duplicate_projects(repo):
    p1 = _create_project(repo, "Legacy Shared Expense", client_id="CLIENT-LE1")
    p2 = _create_project(repo, "Legacy Shared Expense", client_id="CLIENT-LE2")

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO expenses (
            sync_status, created_at, last_modified, date, category, amount,
            description, account_id, payment_account_id, project_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-26T12:30:00",
            "2026-02-26T12:30:00",
            "2026-02-26T12:30:00",
            "Ops",
            55.0,
            "legacy ambiguous row",
            "5001",
            "1101",
            p1.name,
            1,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    assert repo.get_expenses_for_project(str(p1.id), client_id=p1.client_id) == []
    assert repo.get_expenses_for_project(str(p2.id), client_id=p2.client_id) == []
    assert repo.get_total_expenses_for_project(str(p1.id), client_id=p1.client_id) == pytest.approx(
        0.0
    )
    assert repo.get_total_expenses_for_project(str(p2.id), client_id=p2.client_id) == pytest.approx(
        0.0
    )


def test_create_invoice_normalizes_project_reference_with_client_scope(repo):
    p1 = _create_project(repo, "Shared Invoice Name", client_id="CLIENT-I1")
    p2 = _create_project(repo, "Shared Invoice Name", client_id="CLIENT-I2")

    created_invoice = repo.create_invoice(
        schemas.Invoice(
            invoice_number="INV-DUP-SCOPE-001",
            client_id=p1.client_id,
            project_id=p1.name,
            issue_date=datetime(2026, 2, 26, 13, 0, 0),
            due_date=datetime(2026, 3, 5, 13, 0, 0),
            items=[],
            subtotal=500.0,
            total_amount=500.0,
        )
    )

    assert created_invoice.project_id == str(p1.id)
    assert len(repo.get_invoices_for_project(str(p1.id), client_id=p1.client_id)) == 1
    assert repo.get_invoices_for_project(str(p2.id), client_id=p2.client_id) == []

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "SELECT project_id FROM invoices WHERE invoice_number = ?",
        ("INV-DUP-SCOPE-001",),
    )
    assert cursor.fetchone()[0] == str(p1.id)


def test_dashboard_outstanding_uses_project_identity_for_duplicate_names(repo):
    p1 = repo.create_project(
        schemas.Project(
            name="Shared Dashboard Project",
            client_id="CLIENT-D1",
            total_amount=1000.0,
            status=schemas.ProjectStatus.ACTIVE,
        )
    )
    p2 = repo.create_project(
        schemas.Project(
            name="Shared Dashboard Project",
            client_id="CLIENT-D2",
            total_amount=2000.0,
            status=schemas.ProjectStatus.ACTIVE,
        )
    )

    repo.create_payment(
        schemas.Payment(
            project_id=p1.name,
            client_id=p1.client_id,
            date=datetime(2026, 2, 26, 14, 0, 0),
            amount=100.0,
            account_id="1101",
            method="Cash",
        )
    )

    kpis = repo.get_dashboard_kpis(force_refresh=True)

    assert kpis["total_collected"] == pytest.approx(100.0)
    assert kpis["total_outstanding"] == pytest.approx(2900.0)
    assert kpis["net_profit_cash"] == pytest.approx(100.0)
    assert repo.get_total_paid_for_project(str(p1.id), client_id=p1.client_id) == pytest.approx(
        100.0
    )
    assert repo.get_total_paid_for_project(str(p2.id), client_id=p2.client_id) == pytest.approx(0.0)


def test_duplicate_project_names_keep_tasks_scoped_to_stable_reference(repo):
    p1 = _create_project(repo, "Shared Tasks", client_id="CLIENT-T1")
    p2 = _create_project(repo, "Shared Tasks", client_id="CLIENT-T2")

    first_task = repo.create_task(
        {
            "title": "Task A",
            "priority": "MEDIUM",
            "status": "TODO",
            "category": "GENERAL",
            "related_project_id": str(p1.id),
            "tags": [],
            "reminder": False,
            "reminder_minutes": 30,
        }
    )
    second_task = repo.create_task(
        {
            "title": "Task B",
            "priority": "MEDIUM",
            "status": "TODO",
            "category": "GENERAL",
            "related_project_id": str(p2.id),
            "tags": [],
            "reminder": False,
            "reminder_minutes": 30,
        }
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute("SELECT related_project_id FROM tasks WHERE id = ?", (first_task["id"],))
    assert cursor.fetchone()[0] == str(p1.id)
    cursor.execute("SELECT related_project_id FROM tasks WHERE id = ?", (second_task["id"],))
    assert cursor.fetchone()[0] == str(p2.id)

    tasks_for_p1 = repo.get_tasks_by_project(str(p1.id))
    tasks_for_p2 = repo.get_tasks_by_project(str(p2.id))

    assert [task["title"] for task in tasks_for_p1] == ["Task A"]
    assert [task["title"] for task in tasks_for_p2] == ["Task B"]


def test_legacy_ambiguous_task_name_is_hidden_without_related_client_scope(repo):
    p1 = _create_project(repo, "Legacy Shared Task", client_id="CLIENT-LT1")
    p2 = _create_project(repo, "Legacy Shared Task", client_id="CLIENT-LT2")

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (
            sync_status, created_at, last_modified, title, priority, status, category,
            related_project_id, related_client_id, tags, reminder, reminder_minutes, is_archived
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-26T15:00:00",
            "2026-02-26T15:00:00",
            "Legacy ambiguous task",
            "MEDIUM",
            "TODO",
            "GENERAL",
            p1.name,
            None,
            "[]",
            0,
            30,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    assert repo.get_tasks_by_project(str(p1.id)) == []
    assert repo.get_tasks_by_project(str(p2.id)) == []


def test_legacy_task_name_with_related_client_scope_stays_on_correct_project(repo):
    c1 = repo.create_client(schemas.Client(name="Legacy Scoped Task Client A"))
    c2 = repo.create_client(schemas.Client(name="Legacy Scoped Task Client B"))
    p1 = _create_project(repo, "Legacy Scoped Task", client_id=str(c1.id))
    p2 = _create_project(repo, "Legacy Scoped Task", client_id=str(c2.id))

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (
            sync_status, created_at, last_modified, title, priority, status, category,
            related_project_id, related_client_id, tags, reminder, reminder_minutes, is_archived
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "new_offline",
            "2026-02-26T16:00:00",
            "2026-02-26T16:00:00",
            "Legacy scoped task",
            "MEDIUM",
            "TODO",
            "GENERAL",
            p1.name,
            p1.client_id,
            "[]",
            0,
            30,
            0,
        ),
    )
    repo.sqlite_conn.commit()

    tasks_for_p1 = repo.get_tasks_by_project(str(p1.id))
    tasks_for_p2 = repo.get_tasks_by_project(str(p2.id))

    assert [task["title"] for task in tasks_for_p1] == ["Legacy scoped task"]
    assert tasks_for_p2 == []


def test_create_task_keeps_local_client_fk_and_exposes_stable_client_reference(repo):
    c1 = repo.create_client(schemas.Client(name="Task Stable Client A"))
    c2 = repo.create_client(schemas.Client(name="Task Stable Client B"))
    assert c1.id is not None
    assert c2.id is not None

    repo.sqlite_conn.execute(
        "UPDATE clients SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-task-client-a", int(c1.id)),
    )
    repo.sqlite_conn.execute(
        "UPDATE clients SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-task-client-b", int(c2.id)),
    )
    repo.sqlite_conn.commit()

    p1 = repo.create_project(
        schemas.Project(
            name="Scoped Task Stable Project",
            client_id=str(c1.id),
            total_amount=300.0,
        )
    )
    repo.create_project(
        schemas.Project(
            name="Scoped Task Stable Project",
            client_id=str(c2.id),
            total_amount=400.0,
        )
    )
    repo.sqlite_conn.execute(
        "UPDATE projects SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-task-project-a", int(p1.id)),
    )
    repo.sqlite_conn.commit()

    created_task = repo.create_task(
        {
            "title": "Scoped stable task",
            "priority": "MEDIUM",
            "status": "TODO",
            "category": "GENERAL",
            "related_project_id": p1.name,
            "related_client_id": str(c1.id),
            "tags": [],
            "reminder": False,
            "reminder_minutes": 30,
        }
    )

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        "SELECT related_project_id, related_client_id FROM tasks WHERE id = ?",
        (created_task["id"],),
    )
    row = cursor.fetchone()

    assert row["related_project_id"] == "mongo-task-project-a"
    assert row["related_client_id"] == str(c1.id)
    fetched = repo.get_task_by_id(created_task["id"])
    assert fetched is not None
    assert fetched["related_client_id"] == "mongo-task-client-a"
    assert [task["title"] for task in repo.get_tasks_by_client(str(c1.id))] == [
        "Scoped stable task"
    ]
    assert [task["title"] for task in repo.get_tasks_by_client("mongo-task-client-a")] == [
        "Scoped stable task"
    ]


def test_general_task_queries_ignore_soft_deleted_rows(repo):
    client = repo.create_client(schemas.Client(name="Task Query Client"))
    assert client.id is not None

    active_task = repo.create_task(
        {
            "title": "Visible overdue task",
            "priority": "MEDIUM",
            "status": "TODO",
            "category": "GENERAL",
            "related_client_id": str(client.id),
            "due_date": "2020-01-01T09:00:00",
            "tags": [],
            "reminder": False,
            "reminder_minutes": 30,
        }
    )
    assert active_task["id"]

    cursor = repo.sqlite_conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (
            sync_status, created_at, last_modified, title, priority, status, category,
            due_date, related_client_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "deleted",
            "2026-02-25T14:00:00",
            "2026-02-25T14:00:00",
            "Hidden overdue task",
            "MEDIUM",
            "TODO",
            "GENERAL",
            "2020-01-01T08:00:00",
            str(client.id),
            1,
            1,
        ),
    )
    deleted_task_id = cursor.lastrowid
    repo.sqlite_conn.commit()

    all_tasks = repo.get_all_tasks()
    todo_tasks = repo.get_tasks_by_status("TODO")
    client_tasks = repo.get_tasks_by_client(str(client.id))
    overdue_tasks = repo.get_overdue_tasks()

    assert [task["title"] for task in all_tasks] == ["Visible overdue task"]
    assert [task["title"] for task in todo_tasks] == ["Visible overdue task"]
    assert [task["title"] for task in client_tasks] == ["Visible overdue task"]
    assert [task["title"] for task in overdue_tasks] == ["Visible overdue task"]
    assert repo.get_task_by_id(str(deleted_task_id)) is None


def test_create_quotation_keeps_local_client_fk_and_exposes_stable_client_reference(repo):
    client = repo.create_client(schemas.Client(name="Quotation Stable Client"))
    assert client.id is not None

    repo.sqlite_conn.execute(
        "UPDATE clients SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-quotation-client-1", int(client.id)),
    )
    repo.sqlite_conn.commit()

    created = repo.create_quotation(
        {
            "quotation_number": "QT-2026-9001",
            "client_id": "mongo-quotation-client-1",
            "client_name": "Quotation Stable Client",
            "issue_date": "2026-03-07T10:00:00",
            "valid_until": "2026-03-14T10:00:00",
            "title": "Stable quotation",
            "description": "test",
            "scope_of_work": "scope",
            "items": [],
            "subtotal": 500.0,
            "discount_rate": 0.0,
            "discount_amount": 0.0,
            "tax_rate": 0.0,
            "tax_amount": 0.0,
            "total_amount": 500.0,
            "currency": "EGP",
            "status": "مسودة",
        }
    )

    assert created is not None
    row = repo.sqlite_conn.execute(
        "SELECT client_id FROM quotations WHERE id = ?",
        (created["id"],),
    ).fetchone()

    assert row["client_id"] == str(client.id)
    assert created["client_id"] == "mongo-quotation-client-1"
    assert [q["quotation_number"] for q in repo.get_quotations_by_client(str(client.id))] == [
        "QT-2026-9001"
    ]
    assert [
        q["quotation_number"] for q in repo.get_quotations_by_client("mongo-quotation-client-1")
    ] == ["QT-2026-9001"]


def test_update_quotation_accepts_stable_client_reference_and_keeps_local_fk(repo):
    client = repo.create_client(schemas.Client(name="Quotation Update Client"))
    assert client.id is not None

    repo.sqlite_conn.execute(
        "UPDATE clients SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-quotation-client-2", int(client.id)),
    )
    repo.sqlite_conn.commit()

    created = repo.create_quotation(
        {
            "quotation_number": "QT-2026-9002",
            "client_id": str(client.id),
            "client_name": "Quotation Update Client",
            "issue_date": "2026-03-07T11:00:00",
            "valid_until": "2026-03-14T11:00:00",
            "title": "Updatable quotation",
            "description": "",
            "scope_of_work": "",
            "items": [],
            "subtotal": 250.0,
            "discount_rate": 0.0,
            "discount_amount": 0.0,
            "tax_rate": 0.0,
            "tax_amount": 0.0,
            "total_amount": 250.0,
            "currency": "EGP",
            "status": "مسودة",
        }
    )
    assert created is not None

    created["client_id"] = "mongo-quotation-client-2"
    created["title"] = "Updated quotation title"
    updated = repo.update_quotation(created["id"], created)

    assert updated is not None
    row = repo.sqlite_conn.execute(
        "SELECT client_id, title FROM quotations WHERE id = ?",
        (created["id"],),
    ).fetchone()

    assert row["client_id"] == str(client.id)
    assert row["title"] == "Updated quotation title"
    assert updated["client_id"] == "mongo-quotation-client-2"


def test_quotation_soft_delete_hides_rows_and_statistics_and_preserves_sync_tombstone(repo):
    columns = {
        row["name"] for row in repo.sqlite_conn.execute("PRAGMA table_info(quotations)").fetchall()
    }
    assert {"dirty_flag", "is_deleted"} <= columns

    client = repo.create_client(schemas.Client(name="Quotation Delete Client"))
    assert client.id is not None

    created = repo.create_quotation(
        {
            "quotation_number": "QT-2026-9003",
            "client_id": str(client.id),
            "client_name": "Quotation Delete Client",
            "issue_date": "2026-03-07T12:00:00",
            "valid_until": "2026-03-14T12:00:00",
            "title": "Deletable quotation",
            "description": "",
            "scope_of_work": "",
            "items": [],
            "subtotal": 300.0,
            "discount_rate": 0.0,
            "discount_amount": 0.0,
            "tax_rate": 0.0,
            "tax_amount": 0.0,
            "total_amount": 300.0,
            "currency": "EGP",
            "status": "مسودة",
        }
    )
    assert created is not None
    assert repo.get_quotation_statistics()["total"] == 1

    assert repo.delete_quotation(created["id"]) is True

    row = repo.sqlite_conn.execute(
        "SELECT sync_status, dirty_flag, is_deleted FROM quotations WHERE id = ?",
        (created["id"],),
    ).fetchone()

    assert tuple(row) == ("deleted", 1, 1)
    assert repo.get_quotation_by_id(created["id"]) is None
    assert repo.get_all_quotations() == []
    assert repo.get_quotations_by_client(str(client.id)) == []
    assert repo.get_quotations_by_status("مسودة") == []
    assert repo.get_quotation_statistics()["total"] == 0


def test_convert_quotation_to_project_stores_stable_project_reference(repo):
    client = repo.create_client(schemas.Client(name="Quotation Conversion Client"))
    assert client.id is not None

    repo.sqlite_conn.execute(
        "UPDATE clients SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-quotation-client-3", int(client.id)),
    )
    repo.sqlite_conn.commit()

    project = repo.create_project(
        schemas.Project(
            name="Quotation Conversion Project",
            client_id=str(client.id),
            total_amount=800.0,
        )
    )
    assert project.id is not None
    repo.sqlite_conn.execute(
        "UPDATE projects SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-quotation-project-3", int(project.id)),
    )
    repo.sqlite_conn.commit()

    created = repo.create_quotation(
        {
            "quotation_number": "QT-2026-9004",
            "client_id": str(client.id),
            "client_name": "Quotation Conversion Client",
            "issue_date": "2026-03-07T13:00:00",
            "valid_until": "2026-03-14T13:00:00",
            "title": "Convertible quotation",
            "description": "",
            "scope_of_work": "",
            "items": [],
            "subtotal": 800.0,
            "discount_rate": 0.0,
            "discount_amount": 0.0,
            "tax_rate": 0.0,
            "tax_amount": 0.0,
            "total_amount": 800.0,
            "currency": "EGP",
            "status": "مسودة",
        }
    )
    assert created is not None

    assert repo.convert_quotation_to_project(created["id"], str(project.id)) is True

    row = repo.sqlite_conn.execute(
        "SELECT converted_to_project_id, sync_status, dirty_flag FROM quotations WHERE id = ?",
        (created["id"],),
    ).fetchone()
    refreshed = repo.get_quotation_by_id(created["id"])

    assert row["converted_to_project_id"] == "mongo-quotation-project-3"
    assert row["sync_status"] == "modified_offline"
    assert row["dirty_flag"] == 1
    assert refreshed is not None
    assert refreshed["converted_to_project_id"] == "mongo-quotation-project-3"
