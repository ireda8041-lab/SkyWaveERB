from __future__ import annotations

import time

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget


class _NoopService:
    def __init__(self):
        self.repo = object()

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            _ = (name, args, kwargs)
            return None

        return _noop


def test_accounting_summary_section_keeps_subtitle_below_header(monkeypatch, qapp):
    from ui import accounting_manager

    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "load_accounts_data",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "_connect_realtime_signals",
        lambda *args, **kwargs: None,
        raising=True,
    )

    tab = accounting_manager.AccountingManagerTab(
        expense_service=_NoopService(),
        accounting_service=_NoopService(),
        project_service=_NoopService(),
    )

    section, _ = tab._create_section_card(
        "الوضع الحالي",
        "الرصيد المتاح الآن وعدد الخزن الجاهزة والأنواع المستخدمة.",
        "#1d4ed8",
        "تشغيلي",
    )

    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.addWidget(section)
    host.resize(440, 220)
    host.show()
    qapp.processEvents()

    title_label = section.findChild(QLabel, "AccountingSummarySectionTitle")
    subtitle_label = section.findChild(QLabel, "AccountingSummarySectionSubtitle")
    badge_label = section.findChild(QLabel, "AccountingSummarySectionBadge")

    assert title_label is not None
    assert subtitle_label is not None
    assert badge_label is not None
    assert subtitle_label.y() >= title_label.geometry().bottom() - 1
    assert badge_label.y() >= subtitle_label.geometry().bottom() - 1


def test_accounting_summary_panel_is_scrollable_and_splitter_is_responsive(monkeypatch, qapp):
    from ui import accounting_manager

    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "load_accounts_data",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "_connect_realtime_signals",
        lambda *args, **kwargs: None,
        raising=True,
    )

    tab = accounting_manager.AccountingManagerTab(
        expense_service=_NoopService(),
        accounting_service=_NoopService(),
        project_service=_NoopService(),
    )
    tab.resize(760, 920)
    tab.show()
    qapp.processEvents()

    assert isinstance(tab.summary_panel, QScrollArea)
    assert tab.summary_panel.widgetResizable() is True
    assert tab.summary_panel.widget() is tab.summary_content_widget
    assert tab.summary_panel.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert tab.summary_panel.verticalScrollBar().maximum() > 0
    assert tab.main_splitter.orientation() == Qt.Orientation.Vertical

    tab.resize(1320, 920)
    qapp.processEvents()

    assert tab.summary_panel.verticalScrollBar().maximum() == 0
    assert tab.main_splitter.orientation() == Qt.Orientation.Horizontal


def test_accounting_manager_fast_refresh_is_deferred_instead_of_dropped():
    from ui import accounting_manager

    scheduled: list[tuple[bool, int]] = []

    fake_tab = type(
        "_FakeAccountingTab",
        (),
        {
            "_is_loading": False,
            "_last_refresh_time": time.time(),
            "_force_next_refresh": False,
            "_pending_reload": False,
            "_pending_force_reload": False,
            "invalidate_cache": lambda self: None,
            "_schedule_refresh_retry": lambda self, force_refresh=False, delay_ms=220: scheduled.append(
                (force_refresh, delay_ms)
            ),
        },
    )()

    accounting_manager.AccountingManagerTab.load_accounts_data(fake_tab, force_refresh=False)

    assert scheduled
    assert scheduled[0][0] is False
    assert scheduled[0][1] >= 180


def test_accounting_manager_search_filters_tree_and_escape_clears_filter(monkeypatch, qapp):
    from core import schemas
    from ui import accounting_manager

    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "load_accounts_data",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "_connect_realtime_signals",
        lambda *args, **kwargs: None,
        raising=True,
    )

    tab = accounting_manager.AccountingManagerTab(
        expense_service=_NoopService(),
        accounting_service=_NoopService(),
        project_service=_NoopService(),
    )
    tab.show()
    qapp.processEvents()

    vf_account = schemas.Account(
        name="VF Cash - Hazem",
        code="111001",
        type=schemas.AccountType.CASH,
    )
    cash_account = schemas.Account(
        name="Cash",
        code="111006",
        type=schemas.AccountType.CASH,
    )
    tab.cashbox_rows = [
        {
            "account": vf_account,
            "category": "محفظة إلكترونية",
            "currency": "EGP",
            "inflow": 0.0,
            "outflow": 0.0,
            "balance": 0.0,
        },
        {
            "account": cash_account,
            "category": "خزنة نقدية",
            "currency": "EGP",
            "inflow": 0.0,
            "outflow": 0.0,
            "balance": 0.0,
        },
    ]
    tab._apply_cashbox_filter()

    assert tab.accounts_model.rowCount() == 2

    tab.focus_search()
    QTest.keyClicks(tab.search_bar, "vf")
    qapp.processEvents()

    assert tab.accounts_model.rowCount() == 1
    assert tab.accounts_model.item(0, 0).text() == "VF Cash - Hazem"

    tab.handle_escape()
    qapp.processEvents()

    assert tab.search_bar.text() == ""
    assert tab.accounts_model.rowCount() == 2


def test_accounting_manager_keyboard_shortcuts_and_copy_support(monkeypatch, qapp):
    from core import schemas
    from ui import accounting_manager

    events: list[str] = []

    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "load_accounts_data",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "_connect_realtime_signals",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "open_account_editor",
        lambda self: events.append("add"),
        raising=True,
    )
    monkeypatch.setattr(
        accounting_manager.AccountingManagerTab,
        "open_account_editor_for_selected",
        lambda self: events.append("edit"),
        raising=True,
    )

    tab = accounting_manager.AccountingManagerTab(
        expense_service=_NoopService(),
        accounting_service=_NoopService(),
        project_service=_NoopService(),
    )
    tab.show()
    qapp.processEvents()

    account = schemas.Account(
        name="VF Cash - Hazem",
        code="111001",
        type=schemas.AccountType.CASH,
    )
    tab.cashbox_rows = [
        {
            "account": account,
            "category": "محفظة إلكترونية",
            "currency": "EGP",
            "inflow": 1500.0,
            "outflow": 200.0,
            "balance": 1300.0,
        },
    ]
    tab._apply_cashbox_filter()
    tab._focus_first_visible_cashbox()
    qapp.processEvents()

    QTest.keyClick(tab, Qt.Key.Key_Insert)
    QTest.keyClick(tab, Qt.Key.Key_F2)
    qapp.processEvents()

    assert events == ["add", "edit"]

    assert tab.copy_selected() is True
    clipboard_text = qapp.clipboard().text()
    assert "VF Cash - Hazem" in clipboard_text
    assert "محفظة إلكترونية" in clipboard_text
