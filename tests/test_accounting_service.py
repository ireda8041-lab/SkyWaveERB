from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core import schemas
from core.event_bus import EventBus
from services.accounting_service import AccountingService


@pytest.fixture()
def sqlite_repo(tmp_path, monkeypatch):
    import core.repository as repo_mod

    db_path = tmp_path / "accounting_service.db"
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
        yield repo
    finally:
        repo.close()


class TestAccountingService:
    @pytest.fixture
    def service(self, mock_repo, mock_event_bus):
        # Patching internal method to prevent repo calls during init
        with patch.object(AccountingService, "_ensure_default_accounts_exist"):
            return AccountingService(mock_repo, mock_event_bus)

    def test_initialization_subscribes_to_payment_events(self, mock_repo, mock_event_bus):
        """
        ⚡ نظام محاسبي مبسط: فقط أحداث الدفعات والمصروفات
        بدون قيود يومية - فقط تحديث أرصدة الحسابات النقدية
        """
        # Setup & Action
        with patch.object(AccountingService, "_ensure_default_accounts_exist"):
            service = AccountingService(mock_repo, mock_event_bus)

        # Assert - التحقق من الاشتراك في أحداث الدفعات والمصروفات فقط
        mock_event_bus.subscribe.assert_any_call("PAYMENT_RECEIVED", service.handle_new_payment)
        mock_event_bus.subscribe.assert_any_call("EXPENSE_CREATED", service.handle_new_expense)

    def test_initialization_removes_disabled_internal_accounts(self, sqlite_repo):
        now = datetime.now().isoformat()
        sqlite_repo.sqlite_cursor.execute(
            """
            INSERT INTO accounts (
                sync_status, created_at, last_modified, name, code, type,
                parent_id, balance, currency, description, status, is_deleted, dirty_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "synced",
                now,
                now,
                "حساب عملاء قديم",
                "112100",
                "أصول",
                None,
                0.0,
                "EGP",
                "سجل قديم",
                "نشط",
                0,
                0,
            ),
        )
        sqlite_repo.sqlite_cursor.execute(
            """
            INSERT INTO accounts (
                sync_status, created_at, last_modified, name, code, type,
                parent_id, balance, currency, description, status, is_deleted, dirty_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "deleted",
                now,
                now,
                "دفعات محذوفة",
                "212100",
                "خصوم",
                None,
                0.0,
                "EGP",
                "سجل محذوف",
                "مؤرشف",
                1,
                0,
            ),
        )
        sqlite_repo.sqlite_cursor.execute(
            """
            INSERT INTO accounts (
                sync_status, created_at, last_modified, name, code, type,
                parent_id, balance, currency, description, status, is_deleted, dirty_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "synced",
                now,
                now,
                "خزنة رئيسية",
                "111000",
                "أصول نقدية",
                None,
                1500.0,
                "EGP",
                "خزنة تشغيلية",
                "نشط",
                0,
                0,
            ),
        )
        sqlite_repo.create_journal_entry(
            schemas.JournalEntry(
                date=datetime(2026, 1, 2, 10, 0, 0),
                description="قيد داخلي قديم",
                lines=[
                    schemas.JournalEntryLine(
                        account_id="112100",
                        account_code="112100",
                        debit=250.0,
                        credit=0.0,
                    )
                ],
            )
        )
        sqlite_repo.sqlite_conn.commit()

        with patch.object(AccountingService, "_recalculate_cash_balances"):
            AccountingService(sqlite_repo, EventBus())

        assert sqlite_repo.get_account_by_code("112100") is None
        assert sqlite_repo.get_account_by_code("212100") is None
        assert sqlite_repo.get_account_by_code("111000") is not None
        assert sqlite_repo.get_all_journal_entries() == []

    def test_initialization_does_not_create_internal_accounts_on_empty_repo(self, sqlite_repo):
        with patch.object(AccountingService, "_recalculate_cash_balances"):
            AccountingService(sqlite_repo, EventBus())

        remaining_codes = {acc.code for acc in sqlite_repo.get_all_accounts() if acc.code}
        assert remaining_codes == set()

    def test_initialization_keeps_sync_cash_recalc_under_pytest(self, sqlite_repo):
        with patch.object(AccountingService, "_recalculate_cash_balances") as recalc:
            AccountingService(sqlite_repo, EventBus())

        recalc.assert_called_once()

    def test_initialization_can_defer_startup_cash_recalc(self, sqlite_repo, monkeypatch):
        scheduled: list[tuple[str, ...]] = []
        monkeypatch.setattr(
            AccountingService,
            "_can_defer_startup_cash_recalc",
            staticmethod(lambda: True),
        )
        monkeypatch.setattr(
            AccountingService,
            "_schedule_cash_recalc",
            lambda self, emit_types=None: scheduled.append(tuple(emit_types or ())) or True,
        )

        with patch.object(AccountingService, "_recalculate_cash_balances") as recalc:
            AccountingService(sqlite_repo, EventBus())

        recalc.assert_not_called()
        assert scheduled == [("accounts", "dashboard")]

    def test_initialization_can_defer_startup_cash_recalc_without_qapplication(
        self, sqlite_repo, monkeypatch
    ):
        scheduled: list[tuple[str, ...]] = []
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "")
        monkeypatch.setattr(
            AccountingService,
            "_has_qapplication",
            staticmethod(lambda: False),
        )
        monkeypatch.setattr(
            AccountingService,
            "_schedule_cash_recalc",
            lambda self, emit_types=None: scheduled.append(tuple(emit_types or ())) or True,
        )

        with patch.object(AccountingService, "_recalculate_cash_balances") as recalc:
            AccountingService(sqlite_repo, EventBus())

        recalc.assert_not_called()
        assert scheduled == [("accounts", "dashboard")]

    def test_get_account_ledger_report_includes_payments_and_expenses_sorted(
        self, service, mock_repo
    ):
        from datetime import datetime

        account = schemas.Account(
            name="الخزنة",
            code="1111",
            type=schemas.AccountType.CASH,
            balance=0.0,
        )
        mock_repo.get_account_by_id.return_value = account
        mock_repo.get_account_by_code.return_value = account

        payment = schemas.Payment(
            project_id="p1",
            client_id="c1",
            date=datetime(2026, 1, 5, 12, 0, 0),
            amount=100.0,
            account_id="1111",
            method="Cash",
        )
        expense = schemas.Expense(
            date=datetime(2026, 1, 7, 9, 0, 0),
            category="إيجار",
            amount=40.0,
            description="Rent",
            account_id="1111",
            payment_account_id=None,
            project_id=None,
        )
        entry = schemas.JournalEntry(
            date=datetime(2026, 1, 10, 10, 0, 0),
            description="قيد اختبار",
            lines=[
                schemas.JournalEntryLine(
                    account_id="1111",
                    account_code="1111",
                    debit=10.0,
                    credit=0.0,
                    description="مدين",
                )
            ],
            related_document_id="J1",
        )

        mock_repo.get_all_payments.return_value = [payment]
        mock_repo.get_all_expenses.return_value = [expense]
        mock_repo.get_all_journal_entries.return_value = [entry]
        mock_repo.sum_payments_before.return_value = 0.0
        mock_repo.sum_expenses_paid_before.return_value = 0.0
        mock_repo.sum_expenses_charged_before.return_value = 0.0
        mock_repo.get_journal_entries_before.return_value = []
        mock_repo.get_journal_entries_between.return_value = [entry]
        mock_repo.get_payments_by_account.return_value = [payment]
        mock_repo.get_expenses_paid_from_account.return_value = [expense]
        mock_repo.get_expenses_charged_to_account.return_value = []

        report = service.get_account_ledger_report(
            "1111", datetime(2026, 1, 1, 0, 0, 0), datetime(2026, 1, 31, 23, 59, 59)
        )

        movements = report["movements"]
        assert [m["date"] for m in movements] == [
            payment.date,
            expense.date,
            entry.date,
        ]
        assert report["opening_balance"] == 0.0
        assert report["total_debit"] == 110.0
        assert report["total_credit"] == 40.0
        assert report["net_movement"] == 70.0
        assert report["ending_balance"] == 70.0

    def test_audit_cashbox_integrity_counts_legacy_expense_reference_as_repairable(
        self, service, mock_repo, monkeypatch
    ):
        cash_account = schemas.Account(
            id=69,
            name="V/F HAZEM",
            code="111001",
            type=schemas.AccountType.CASH,
            balance=0.0,
        )
        expense = schemas.Expense(
            id=18,
            date=datetime(2026, 1, 29, 0, 0, 0),
            category="تسويق وإعلان",
            amount=600.0,
            description="",
            account_id="111001",
            payment_account_id="1001",
            project_id="p1",
        )
        monkeypatch.setattr(
            service,
            "get_hierarchy_with_balances",
            lambda force_refresh=True: {"111001": {"total": 0.0}},
        )

        result = service.audit_cashbox_integrity(
            apply_fixes=False,
            preloaded_accounts=[cash_account],
            preloaded_payments=[],
            preloaded_expenses=[expense],
        )

        assert result["fixed_expense_payment_refs"] == 1
        assert result["backfilled_expense_payment_refs"] == 0
        assert result["unresolved_expense_payment_refs"] == 0

    def test_get_account_ledger_report_falls_back_from_legacy_numeric_expense_reference(
        self, service, mock_repo
    ):
        cash_account = schemas.Account(
            id=69,
            name="الخزنة",
            code="111001",
            type=schemas.AccountType.CASH,
            balance=0.0,
        )
        legacy_expense = schemas.Expense(
            date=datetime(2026, 1, 7, 9, 0, 0),
            category="إيجار",
            amount=60.0,
            description="Legacy ref",
            account_id="111001",
            payment_account_id="1001",
            project_id=None,
        )

        mock_repo.get_account_by_id.return_value = cash_account
        mock_repo.get_account_by_code.return_value = cash_account
        mock_repo.get_all_accounts.return_value = [cash_account]
        mock_repo.get_all_payments.return_value = []
        mock_repo.get_all_expenses.return_value = [legacy_expense]
        mock_repo.get_journal_entries_before.return_value = []
        mock_repo.get_journal_entries_between.return_value = []
        mock_repo.get_all_journal_entries.return_value = []

        report = service.get_account_ledger_report(
            "111001", datetime(2026, 1, 1, 0, 0, 0), datetime(2026, 1, 31, 23, 59, 59)
        )

        assert len(report["movements"]) == 1
        assert report["movements"][0]["credit"] == pytest.approx(60.0)
        assert report["total_credit"] == pytest.approx(60.0)
        assert report["ending_balance"] == pytest.approx(-60.0)

    def test_get_account_ledger_report_skips_account_map_for_direct_cash_refs(
        self, service, mock_repo
    ):
        cash_account = schemas.Account(
            id=101,
            name="Cash Box",
            code="111001",
            type=schemas.AccountType.CASH,
            balance=0.0,
        )
        payment = schemas.Payment(
            project_id="",
            client_id="CLIENT-1",
            date=datetime(2026, 1, 5, 10, 0, 0),
            amount=80.0,
            account_id="111001",
            method="Cash",
        )
        expense = schemas.Expense(
            date=datetime(2026, 1, 6, 10, 0, 0),
            category="Ops",
            amount=25.0,
            description="Office",
            account_id="5001",
            payment_account_id="111001",
            project_id=None,
        )

        mock_repo.get_account_by_id.return_value = cash_account
        mock_repo.get_account_by_code.return_value = cash_account
        mock_repo.get_all_payments.return_value = [payment]
        mock_repo.get_all_expenses.return_value = [expense]
        mock_repo.get_journal_entries_before.return_value = []
        mock_repo.get_journal_entries_between.return_value = []

        report = service.get_account_ledger_report(
            "111001", datetime(2026, 1, 1, 0, 0, 0), datetime(2026, 1, 31, 23, 59, 59)
        )

        assert report["total_debit"] == pytest.approx(80.0)
        assert report["total_credit"] == pytest.approx(25.0)
        mock_repo.get_all_accounts.assert_not_called()

    def test_get_recent_activity_resolves_payment_project_with_client_scope(
        self, service, mock_repo
    ):
        from datetime import datetime

        payment = schemas.Payment(
            project_id="Shared Name",
            client_id="CLIENT-42",
            date=datetime(2026, 1, 5, 12, 0, 0),
            amount=275.0,
            account_id="1111",
            method="Cash",
        )
        project = schemas.Project(
            name="Shared Name",
            client_id="CLIENT-42",
            total_amount=500.0,
        )

        mock_repo.get_all_payments.return_value = [payment]
        mock_repo.get_all_expenses.return_value = []
        mock_repo.get_all_projects.return_value = []
        mock_repo.get_all_clients.return_value = []
        mock_repo.get_all_invoices.return_value = []
        mock_repo.get_all_journal_entries.return_value = []
        mock_repo.get_project_by_number.return_value = project

        activity = service.get_recent_activity()

        mock_repo.get_project_by_number.assert_called_with("Shared Name", "CLIENT-42")
        assert activity[0]["operation"] == "تحصيل دفعة"
        assert activity[0]["description"] == "Shared Name"
        assert activity[0]["amount"] == pytest.approx(275.0)

    def test_get_recent_activity_prefers_recorded_activity_logs(self, service, mock_repo):
        activity_logs = [
            {
                "timestamp": datetime(2026, 3, 7, 22, 15, 0),
                "operation": "تعديل عميل",
                "description": "Katkoty kids wear",
                "details": "",
                "amount": None,
            }
        ]
        mock_repo.get_recent_activity_logs.return_value = activity_logs

        activity = service.get_recent_activity(limit=3)

        mock_repo.get_recent_activity_logs.assert_called_once_with(3)
        assert activity == activity_logs
        mock_repo.get_all_payments.assert_not_called()

    def test_get_recent_activity_prefers_synced_notification_activities(
        self, service, mock_repo, monkeypatch
    ):
        synced_activity = SimpleNamespace(
            created_at=datetime(2026, 3, 8, 9, 30, 0),
            last_modified=datetime(2026, 3, 8, 9, 30, 0),
            operation_text="تحصيل دفعة",
            message="Alpha Project",
            details="العميل: Blue Nile",
            amount=750.0,
        )
        fake_notification_service = SimpleNamespace(
            get_recent_activity_notifications=lambda limit: [synced_activity]
        )
        monkeypatch.setattr(
            "services.notification_service.NotificationService.get_active_instance",
            lambda repository=None: fake_notification_service if repository is mock_repo else None,
        )

        activity = service.get_recent_activity(limit=4)

        assert len(activity) == 1
        assert activity[0]["operation"] == "تحصيل دفعة"
        assert activity[0]["description"] == "Alpha Project"
        assert activity[0]["details"] == "العميل: Blue Nile"
        assert activity[0]["amount"] == pytest.approx(750.0)
        mock_repo.get_recent_activity_logs.assert_not_called()

    def test_get_recent_activity_does_not_fallback_to_local_logs_when_notifications_exist(
        self, service, mock_repo, monkeypatch
    ):
        mock_repo.get_recent_activity_logs.return_value = [
            {
                "timestamp": datetime(2026, 3, 9, 8, 0, 0),
                "operation": "تعديل عميل",
                "description": "Local only",
                "details": "",
                "amount": None,
            }
        ]
        fake_notification_service = SimpleNamespace(
            get_recent_activity_notifications=lambda limit: []
        )
        monkeypatch.setattr(
            "services.notification_service.NotificationService.get_active_instance",
            lambda repository=None: fake_notification_service if repository is mock_repo else None,
        )

        activity = service.get_recent_activity(limit=4)

        assert activity == []
        mock_repo.get_recent_activity_logs.assert_not_called()
        mock_repo.get_all_payments.assert_not_called()

    def test_get_recent_activity_prefers_business_activity_over_journal_fallback(
        self, service, mock_repo
    ):
        from datetime import datetime

        payment = schemas.Payment(
            project_id="P-7",
            client_id="C-7",
            date=datetime(2026, 2, 10, 10, 0, 0),
            amount=900.0,
            account_id="1111",
            method="Bank Transfer",
        )
        payment.last_modified = datetime(2026, 2, 10, 11, 0, 0)

        client = schemas.Client(name="Blue Nile")
        client.id = "C-7"
        client.created_at = datetime(2026, 2, 1, 9, 0, 0)
        client.last_modified = datetime(2026, 2, 1, 9, 0, 0)

        mock_repo.get_all_payments.return_value = [payment]
        mock_repo.get_all_expenses.return_value = []
        mock_repo.get_all_projects.return_value = []
        mock_repo.get_all_clients.return_value = [client]
        mock_repo.get_all_invoices.return_value = []
        mock_repo.get_project_by_number.return_value = None
        mock_repo.get_all_journal_entries.return_value = [
            schemas.JournalEntry(
                date=datetime(2026, 2, 10, 12, 0, 0),
                description="قيد يومية خام",
                lines=[],
            )
        ]

        activity = service.get_recent_activity(limit=5)

        assert activity
        assert len(activity) == 1
        assert activity[0]["operation"] == "تحصيل دفعة"
        assert "العميل: Blue Nile" in activity[0]["details"]
        assert activity[0]["description"] == "P-7"

    def test_get_recent_activity_reuses_name_resolution_for_duplicate_refs(
        self, service, mock_repo, monkeypatch
    ):
        payment_one = schemas.Payment(
            project_id="P-7",
            client_id="C-7",
            date=datetime(2026, 2, 10, 10, 0, 0),
            amount=900.0,
            account_id="1111",
            method="Bank Transfer",
        )
        payment_one.last_modified = datetime(2026, 2, 10, 11, 0, 0)

        payment_two = schemas.Payment(
            project_id="P-7",
            client_id="C-7",
            date=datetime(2026, 2, 11, 10, 0, 0),
            amount=500.0,
            account_id="1111",
            method="Cash",
        )
        payment_two.last_modified = datetime(2026, 2, 11, 11, 0, 0)

        client = schemas.Client(name="Blue Nile")
        client.id = "C-7"

        project = schemas.Project(name="Project Seven", client_id="C-7", total_amount=1400.0)
        project.id = "P-7"

        mock_repo.get_all_payments.return_value = [payment_one, payment_two]
        mock_repo.get_all_expenses.return_value = []
        mock_repo.get_all_clients.return_value = [client]
        mock_repo.get_all_projects.return_value = [project]
        mock_repo.get_all_invoices.return_value = []
        mock_repo.get_all_journal_entries.return_value = []
        mock_repo.get_recent_activity_logs.return_value = []
        mock_repo.get_client_by_id.return_value = None
        mock_repo.get_project_by_number.return_value = None
        mock_repo.get_project_by_id.return_value = None

        monkeypatch.setattr(
            "services.notification_service.NotificationService.get_active_instance",
            lambda repository=None: None,
        )

        activity = service.get_recent_activity(limit=8)

        assert len(activity) == 2
        mock_repo.get_client_by_id.assert_called_once_with("C-7")
        mock_repo.get_project_by_number.assert_called_once_with("P-7", "C-7")
        mock_repo.get_project_by_id.assert_called_once_with("P-7")
        mock_repo.get_all_clients.assert_called_once()
        mock_repo.get_all_projects.assert_called_once()

    def test_get_recent_activity_resolves_names_only_for_selected_limit(
        self, service, mock_repo, monkeypatch
    ):
        payment_old = schemas.Payment(
            project_id="P-1",
            client_id="C-1",
            date=datetime(2026, 2, 8, 9, 0, 0),
            amount=100.0,
            account_id="1111",
            method="Cash",
        )
        payment_old.last_modified = datetime(2026, 2, 8, 9, 5, 0)

        payment_mid = schemas.Payment(
            project_id="P-2",
            client_id="C-2",
            date=datetime(2026, 2, 9, 9, 0, 0),
            amount=200.0,
            account_id="1111",
            method="Cash",
        )
        payment_mid.last_modified = datetime(2026, 2, 9, 9, 5, 0)

        payment_latest = schemas.Payment(
            project_id="P-3",
            client_id="C-3",
            date=datetime(2026, 2, 10, 9, 0, 0),
            amount=300.0,
            account_id="1111",
            method="Bank Transfer",
        )
        payment_latest.last_modified = datetime(2026, 2, 10, 9, 5, 0)

        mock_repo.get_all_payments.return_value = [payment_old, payment_mid, payment_latest]
        mock_repo.get_all_expenses.return_value = []
        mock_repo.get_recent_activity_logs.return_value = []
        mock_repo.get_client_by_id.side_effect = lambda ref: SimpleNamespace(name=f"Client {ref}")
        mock_repo.get_project_by_number.side_effect = lambda ref, client_id=None: SimpleNamespace(
            name=f"Project {ref}"
        )
        mock_repo.get_project_by_id.return_value = None

        monkeypatch.setattr(
            "services.notification_service.NotificationService.get_active_instance",
            lambda repository=None: None,
        )

        activity = service.get_recent_activity(limit=1)

        assert len(activity) == 1
        assert activity[0]["description"] == "Project P-3"
        assert activity[0]["details"] == "العميل: Client C-3 • الطريقة: Bank Transfer"
        mock_repo.get_client_by_id.assert_called_once_with("C-3")
        mock_repo.get_project_by_number.assert_called_once_with("P-3", "C-3")
        mock_repo.get_project_by_id.assert_not_called()
        mock_repo.get_all_clients.assert_not_called()
        mock_repo.get_all_projects.assert_not_called()

    def test_get_recent_activity_ignores_metadata_only_entity_updates(self, service, mock_repo):
        from datetime import datetime

        client = schemas.Client(name="Ghost Client")
        client.company_name = "Ghost Co"
        client.phone = "01000000000"
        client.created_at = datetime(2026, 3, 7, 9, 0, 0)
        client.last_modified = datetime(2026, 3, 7, 11, 30, 0)

        project = schemas.Project(
            name="Ghost Project",
            client_id="CLIENT-GHOST",
            total_amount=13500.0,
        )
        project.created_at = datetime(2026, 3, 7, 10, 0, 0)
        project.last_modified = datetime(2026, 3, 7, 11, 45, 0)

        journal_fallback = [{"date": "2026-03-07", "description": "fallback"}]

        mock_repo.get_all_payments.return_value = []
        mock_repo.get_all_expenses.return_value = []
        mock_repo.get_all_clients.return_value = [client]
        mock_repo.get_all_projects.return_value = [project]
        mock_repo.get_all_invoices.return_value = []

        with patch.object(
            service, "get_recent_journal_entries", return_value=journal_fallback
        ) as fallback:
            activity = service.get_recent_activity(limit=8)

        fallback.assert_called_once_with(8)
        assert activity == journal_fallback

    def test_calculate_period_kpis_uses_project_payments_for_receivables(self, service, mock_repo):
        from datetime import datetime

        project = schemas.Project(
            name="Receivable Project",
            client_id="CLIENT-R1",
            total_amount=500.0,
            start_date=datetime(2026, 1, 3, 9, 0, 0),
        )
        project.id = 17

        mock_repo.get_all_journal_entries.return_value = []
        mock_repo.get_all_accounts.return_value = []
        mock_repo.get_all_payments.return_value = []
        mock_repo.get_all_projects.return_value = [project]
        mock_repo.get_total_paid_for_project.return_value = 200.0

        kpis = service._calculate_period_kpis(
            datetime(2026, 1, 1, 0, 0, 0),
            datetime(2026, 1, 31, 23, 59, 59),
        )

        mock_repo.get_total_paid_for_project.assert_called_with("17", client_id="CLIENT-R1")
        assert kpis["receivables"] == pytest.approx(300.0)

    def test_get_financial_summary_derives_operational_balances_from_business_records(
        self, service, mock_repo
    ):
        AccountingService._hierarchy_cache = None
        AccountingService._hierarchy_cache_time = 0

        accounts = [
            schemas.Account(
                name="فودافون كاش",
                code="111000",
                type=schemas.AccountType.CASH,
                balance=0.0,
            ),
            schemas.Account(
                name="V/F HAZEM",
                code="111001",
                type=schemas.AccountType.CASH,
                parent_code="111000",
                balance=0.0,
            ),
        ]
        payment = schemas.Payment(
            project_id="17",
            client_id="CLIENT-1",
            date=datetime(2026, 1, 5, 10, 0, 0),
            amount=3000.0,
            account_id="111001",
            method="Cash",
        )
        expense = schemas.Expense(
            date=datetime(2026, 1, 6, 11, 0, 0),
            category="إيجار",
            amount=700.0,
            description="Office rent",
            account_id="RENT",
            payment_account_id="111001",
        )

        mock_repo.get_all_accounts.return_value = accounts
        mock_repo.get_all_payments.return_value = [payment]
        mock_repo.get_all_expenses.return_value = [expense]
        mock_repo.get_all_projects.return_value = []

        tree_map = service.get_hierarchy_with_balances(force_refresh=True)
        summary = service.get_financial_summary()

        assert tree_map["111001"]["total"] == pytest.approx(2300.0)
        assert summary["assets"] == pytest.approx(2300.0)
        assert summary["revenue"] == pytest.approx(3000.0)
        assert summary["opex"] == pytest.approx(700.0)
        assert summary["expenses"] == pytest.approx(700.0)
        assert summary["net_profit"] == pytest.approx(2300.0)

    def test_get_financial_summary_uses_expense_rows_without_internal_accounts(
        self, service, mock_repo
    ):
        AccountingService._hierarchy_cache = None
        AccountingService._hierarchy_cache_time = 0

        accounts = [
            schemas.Account(
                name="فودافون كاش",
                code="111000",
                type=schemas.AccountType.CASH,
                balance=0.0,
            ),
            schemas.Account(
                name="V/F REDA",
                code="111002",
                type=schemas.AccountType.CASH,
                parent_code="111000",
                balance=0.0,
            ),
        ]
        payment = schemas.Payment(
            project_id="17",
            client_id="CLIENT-1",
            date=datetime(2026, 1, 5, 10, 0, 0),
            amount=3000.0,
            account_id="111002",
            method="Cash",
        )
        expense = schemas.Expense(
            date=datetime(2026, 1, 6, 11, 0, 0),
            category="إيجار",
            amount=700.0,
            description="Office rent",
            account_id="فئة حرة",
            payment_account_id="111002",
        )

        mock_repo.get_all_accounts.return_value = accounts
        mock_repo.get_all_payments.return_value = [payment]
        mock_repo.get_all_expenses.return_value = [expense]
        mock_repo.get_all_projects.return_value = []

        summary = service.get_financial_summary()

        assert summary["assets"] == pytest.approx(2300.0)
        assert summary["revenue"] == pytest.approx(3000.0)
        assert summary["opex"] == pytest.approx(700.0)
        assert summary["expenses"] == pytest.approx(700.0)
        assert summary["net_profit"] == pytest.approx(2300.0)

    def test_get_client_balance_uses_repository_client_queries(self, sqlite_repo):
        with patch.object(AccountingService, "_ensure_default_accounts_exist"):
            service = AccountingService(sqlite_repo, EventBus())

        client = sqlite_repo.create_client(schemas.Client(name="Balance Client"))
        project = sqlite_repo.create_project(
            schemas.Project(
                name="Balance Project",
                client_id=str(client.id),
                total_amount=1000.0,
            )
        )
        sqlite_repo.create_invoice(
            schemas.Invoice(
                invoice_number="INV-CLIENT-BAL-001",
                client_id=str(client.id),
                project_id=str(project.id),
                issue_date=datetime(2026, 1, 5, 10, 0, 0),
                due_date=datetime(2026, 1, 12, 10, 0, 0),
                items=[],
                subtotal=1000.0,
                total_amount=1000.0,
            )
        )
        sqlite_repo.create_payment(
            schemas.Payment(
                project_id=str(project.id),
                client_id=str(client.id),
                date=datetime(2026, 1, 6, 12, 0, 0),
                amount=250.0,
                account_id="1101",
                method="Cash",
            )
        )

        assert service.get_client_balance(str(client.id)) == pytest.approx(750.0)
        balances = service.get_all_clients_balances()
        assert len(balances) == 1
        assert balances[0]["client_name"] == "Balance Client"
        assert balances[0]["balance"] == pytest.approx(750.0)
        assert balances[0]["status"] == "مستحق"

    def test_reset_and_seed_agency_accounts_only_purges_internal_layer(self, sqlite_repo):
        with patch.object(AccountingService, "_ensure_default_accounts_exist"):
            service = AccountingService(sqlite_repo, EventBus())

        sqlite_repo.create_account(
            schemas.Account(
                name="Custom Account",
                code="999999",
                type=schemas.AccountType.EXPENSE,
                balance=0.0,
            )
        )
        sqlite_repo.create_account(
            schemas.Account(
                name="حساب داخلي قديم",
                code="112100",
                type=schemas.AccountType.ASSET,
                balance=0.0,
            )
        )
        sqlite_repo.create_journal_entry(
            schemas.JournalEntry(
                date=datetime(2026, 1, 7, 9, 0, 0),
                description="Legacy entry",
                lines=[
                    schemas.JournalEntryLine(
                        account_id="999999",
                        account_code="999999",
                        debit=100.0,
                        credit=0.0,
                    )
                ],
            )
        )

        result = service.reset_and_seed_agency_accounts()

        assert result["success"] is True
        assert result["created"] == 0
        remaining_codes = {acc.code for acc in sqlite_repo.get_all_accounts() if acc.code}
        assert remaining_codes == {"999999"}
        assert sqlite_repo.get_all_journal_entries() == []

    def test_get_dashboard_stats_reuses_repo_kpis_without_loading_financial_summary(
        self, service, mock_repo, monkeypatch
    ):
        mock_repo.get_dashboard_kpis.return_value = {
            "total_collected": 1250.0,
            "total_outstanding": 300.0,
            "total_expenses": 200.0,
            "net_profit_cash": 1050.0,
        }

        monkeypatch.setattr(
            service,
            "get_financial_summary",
            lambda: (_ for _ in ()).throw(AssertionError("should not load financial summary")),
        )

        stats = service.get_dashboard_stats()

        assert stats == {
            "total_sales": 1250.0,
            "cash_collected": 1250.0,
            "receivables": 300.0,
            "expenses": 200.0,
            "net_profit": 1050.0,
        }
