from unittest.mock import MagicMock

from PyQt6.QtWidgets import QGroupBox

from core import schemas
from ui.ledger_window import LedgerWindow


def test_ledger_window_uses_cashbox_language(monkeypatch, qt_app):
    monkeypatch.setattr(LedgerWindow, "load_ledger_data", lambda self: None, raising=True)

    account = schemas.Account(
        name="V/F HAZEM",
        code="111001",
        type=schemas.AccountType.CASH,
        balance=44700.0,
    )
    window = LedgerWindow(account=account, accounting_service=MagicMock())
    window.show()
    qt_app.processEvents()

    assert "حركة الخزنة" in window.windowTitle()
    headers = [window.movements_table.horizontalHeaderItem(i).text() for i in range(6)]
    assert headers == ["التاريخ", "الوصف", "المرجع", "الوارد", "الصادر", "الرصيد"]
    assert window.total_debit_label.text().startswith("إجمالي الوارد")
    assert window.total_credit_label.text().startswith("إجمالي الصادر")

    group_titles = {group.title() for group in window.findChildren(QGroupBox)}
    assert "معلومات الخزنة" in group_titles
    assert "حركة الخزنة" in group_titles

    window.close()
