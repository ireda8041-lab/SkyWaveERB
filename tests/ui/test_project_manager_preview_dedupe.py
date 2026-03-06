from __future__ import annotations

from datetime import datetime

from core import schemas
from ui.project_manager import ProjectManagerTab


def test_preview_expense_dedupe_keeps_distinct_account_rows(qapp):
    tab = ProjectManagerTab.__new__(ProjectManagerTab)
    expenses = [
        schemas.Expense(
            project_id="Preview Project",
            date=datetime(2026, 2, 26, 10, 0, 0),
            category="Media",
            amount=250.0,
            description="same payload",
            account_id="5001",
            payment_account_id="1101",
        ),
        schemas.Expense(
            project_id="Preview Project",
            date=datetime(2026, 2, 26, 10, 0, 0),
            category="Media",
            amount=250.0,
            description="same payload",
            account_id="5002",
            payment_account_id="1102",
        ),
    ]

    deduped = tab._dedupe_preview_expenses(expenses)

    assert len(deduped) == 2
