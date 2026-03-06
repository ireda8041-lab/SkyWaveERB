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

    assert created.project_id == project.name
    assert created.client_id == project.client_id


def test_update_payment_keeps_canonical_project_reference(repo):
    project = _create_project(repo, "مشروع تحديث مرجعي", client_id="CLIENT-22")

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
    assert refreshed.project_id == project.name
    assert refreshed.client_id == project.client_id


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
    assert refreshed.project_id == project.name
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
    repo.sqlite_conn.commit()

    updated_project = project.model_copy(update={"name": "Project New"})
    saved = repo.update_project(project.name, updated_project)

    assert saved is not None
    assert saved.name == "Project New"
    assert repo.get_total_paid_for_project("Project New") == pytest.approx(320.0)
    assert repo.get_total_expenses_for_project("Project New") == pytest.approx(70.0)
    assert repo.get_invoice_number_for_project("Project New") == fixed_invoice_number
    assert len(repo.get_invoices_for_project("Project New")) == 1

    cursor.execute("SELECT project_id FROM payments")
    assert {row[0] for row in cursor.fetchall()} == {"Project New"}
    cursor.execute("SELECT project_id FROM expenses")
    assert {row[0] for row in cursor.fetchall()} == {"Project New"}
    cursor.execute("SELECT project_id FROM invoices WHERE invoice_number = ?", ("RENAME-INV-001",))
    assert cursor.fetchone()[0] == "Project New"
    cursor.execute(
        "SELECT project_name FROM invoice_numbers WHERE invoice_number = ?",
        (fixed_invoice_number,),
    )
    assert cursor.fetchone()[0] == "Project New"


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
        "SELECT sync_status, is_deleted FROM payments WHERE project_id = ?", (project.name,)
    )
    assert tuple(cursor.fetchone()) == ("deleted", 1)
    cursor.execute(
        "SELECT sync_status, is_deleted FROM expenses WHERE project_id = ?", (project.name,)
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
    assert cursor.fetchone()[0] == project.name

    created_task["title"] = "Canonical task updated"
    created_task["related_project_id"] = fixed_invoice_number
    repo.update_task(created_task["id"], created_task)

    cursor.execute("SELECT related_project_id FROM tasks WHERE id = ?", (created_task["id"],))
    assert cursor.fetchone()[0] == project.name

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
