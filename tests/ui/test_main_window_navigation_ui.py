from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

from core.auth_models import User, UserRole


class _FakeRepo:
    pass


class _FakeAccountingService:
    def __init__(self):
        self.repo = _FakeRepo()


class _FakeService:
    def __init__(self, repo):
        self.repo = repo


def test_main_window_builds_tabs_and_switches(monkeypatch, qapp):
    from ui import main_window as mw

    class _FakeStatusBarWidget(QWidget):
        logout_requested = pyqtSignal()
        full_sync_requested = pyqtSignal()

        def set_current_user(self, user):
            self._user = user

        def update_sync_status(self, status):
            self._status = status

        def update_sync_progress(self, progress):
            self._progress = progress

    monkeypatch.setattr(mw, "StatusBarWidget", _FakeStatusBarWidget, raising=True)

    expected_tabs = [
        "🏠 الصفحة الرئيسية",
        "🚀 المشاريع",
        "💳 المصروفات",
        "💰 الدفعات",
        "👤 العملاء",
        "🛠️ الخدمات والباقات",
        "🗃️ الخزن",
        "📋 المهام",
        "🔧 الإعدادات",
    ]

    def _create_fake_tabs(self):
        for tab_name in expected_tabs:
            self.tabs.addTab(QWidget(), tab_name)
            self._tab_data_loaded[tab_name] = True

    monkeypatch.setattr(mw.MainWindow, "_create_all_tabs", _create_fake_tabs, raising=True)
    monkeypatch.setattr(mw.MainWindow, "apply_permissions", lambda self: None, raising=True)
    monkeypatch.setattr(mw.MainWindow, "setup_title_bar", lambda self: None, raising=True)
    monkeypatch.setattr(mw.MainWindow, "setup_auto_sync", lambda self: None, raising=True)
    monkeypatch.setattr(mw.MainWindow, "_load_initial_data_safely", lambda self: None, raising=True)
    monkeypatch.setattr(
        mw.MainWindow, "_update_initial_connection_status", lambda self: None, raising=True
    )
    monkeypatch.setattr(mw.MainWindow, "_connect_shortcuts", lambda self: None, raising=True)
    monkeypatch.setattr(
        mw.MainWindow, "_check_project_due_dates_background", lambda self: None, raising=True
    )

    def _mark_sync_clicked(self):
        self._test_sync_clicked = True

    monkeypatch.setattr(mw.MainWindow, "_on_full_sync_clicked", _mark_sync_clicked, raising=True)

    repo = _FakeRepo()
    accounting_service = _FakeAccountingService()
    settings_service = _FakeService(repo)
    client_service = _FakeService(repo)
    service_service = _FakeService(repo)
    expense_service = _FakeService(repo)
    invoice_service = _FakeService(repo)
    project_service = _FakeService(repo)

    current_user = User(
        id="u1",
        username="admin",
        password_hash="x",
        role=UserRole.ADMIN,
        full_name="Admin",
        is_active=True,
    )

    window = mw.MainWindow(
        current_user=current_user,
        settings_service=settings_service,
        accounting_service=accounting_service,
        client_service=client_service,
        service_service=service_service,
        expense_service=expense_service,
        invoice_service=invoice_service,
        project_service=project_service,
        notification_service=None,
        printing_service=None,
        export_service=None,
        smart_scan_service=None,
        sync_manager=object(),
    )
    window.show()

    assert window.tabs.count() == len(expected_tabs)

    for index in range(window.tabs.count()):
        window.tabs.setCurrentIndex(index)
        qapp.processEvents()

    assert not getattr(window, "_test_sync_clicked", False)
    window.status_bar.full_sync_requested.emit()
    qapp.processEvents()
    assert getattr(window, "_test_sync_clicked", False)


def test_main_window_settings_refresh_uses_active_subtab_loader():
    from ui import main_window as mw

    calls: list[bool] = []

    class _FakeSettingsTab:
        def load_active_subtab_data(self, force_reload: bool = False):
            calls.append(force_reload)

    fake_window = type("_FakeWindow", (), {"settings_tab": _FakeSettingsTab()})()

    mw.MainWindow._update_tab_ui(fake_window, "🔧 الإعدادات", {"type": "settings"})

    assert calls == [False]


def test_main_window_uses_cashboxes_label_for_accounting_loader(monkeypatch):
    from ui import main_window as mw

    events: list[str] = []

    monkeypatch.setattr(
        mw.QTimer,
        "singleShot",
        staticmethod(lambda _delay, callback: callback()),
        raising=False,
    )

    class _FakeAccountingTab:
        def __init__(self):
            self.project_service = None

        def load_accounts_data(self):
            events.append("load_accounts")

    fake_window = type(
        "_FakeWindow",
        (),
        {
            "_refresh_in_progress": {},
            "pending_refreshes": {},
            "_tab_data_loaded": {},
            "accounting_tab": _FakeAccountingTab(),
            "project_service": object(),
        },
    )()

    mw.MainWindow._do_load_tab_data_safe(fake_window, mw.ACCOUNTING_TAB_LABEL)
    mw.MainWindow._do_load_tab_data_safe(fake_window, mw.LEGACY_ACCOUNTING_TAB_LABEL)

    assert events == ["load_accounts", "load_accounts"]
    assert fake_window._tab_data_loaded[mw.ACCOUNTING_TAB_LABEL] is True
    assert fake_window._tab_data_loaded[mw.LEGACY_ACCOUNTING_TAB_LABEL] is True
    assert fake_window._refresh_in_progress[f"tab_{mw.ACCOUNTING_TAB_LABEL}"] is False
    assert fake_window._refresh_in_progress[f"tab_{mw.LEGACY_ACCOUNTING_TAB_LABEL}"] is False


def test_main_window_attach_deferred_services_starts_due_date_checks():
    from ui import main_window as mw

    events: list[tuple[str, int | None]] = []

    class _FakeTimer:
        def __init__(self):
            self.active = False

        def isActive(self):
            return self.active

        def start(self, interval=None):
            self.active = True
            events.append(("start", interval))

    fake_window = type(
        "_FakeWindow",
        (),
        {
            "notification_service": None,
            "template_service": None,
            "printing_service": None,
            "export_service": None,
            "project_check_timer": _FakeTimer(),
            "_project_due_dates_bootstrap_timer": _FakeTimer(),
            "_project_due_dates_initial_run_done": False,
            "projects_tab": None,
        },
    )()

    mw.MainWindow.attach_deferred_services(fake_window, notification_service=object())

    assert fake_window.notification_service is not None
    assert events == [
        ("start", None),
        ("start", mw.PROJECT_DUE_DATE_INITIAL_DELAY_MS),
    ]


def test_main_window_escape_shortcut_closes_active_modal(monkeypatch):
    from ui import main_window as mw

    events: list[str] = []

    class _FakeModal:
        def reject(self):
            events.append("reject")

    fake_window = type("_FakeWindow", (), {"tabs": None})()

    monkeypatch.setattr(
        mw,
        "QApplication",
        type(
            "_FakeApp",
            (),
            {
                "activePopupWidget": staticmethod(lambda: None),
                "activeModalWidget": staticmethod(lambda: _FakeModal()),
                "focusWidget": staticmethod(lambda: None),
            },
        ),
        raising=True,
    )

    mw.MainWindow._on_close_dialog(fake_window)

    assert events == ["reject"]


def test_main_window_escape_shortcut_clears_focus_without_modal(monkeypatch):
    from ui import main_window as mw

    events: list[str] = []

    class _FakeFocus:
        def deselect(self):
            events.append("deselect")

        def clearFocus(self):
            events.append("clearFocus")

    class _FakeTab:
        @staticmethod
        def findChildren(_cls):
            return []

    class _FakeTabs:
        @staticmethod
        def currentWidget():
            return _FakeTab()

    fake_window = type("_FakeWindow", (), {"tabs": _FakeTabs()})()

    monkeypatch.setattr(
        mw,
        "QApplication",
        type(
            "_FakeApp",
            (),
            {
                "activePopupWidget": staticmethod(lambda: None),
                "activeModalWidget": staticmethod(lambda: None),
                "focusWidget": staticmethod(lambda: _FakeFocus()),
            },
        ),
        raising=True,
    )

    mw.MainWindow._on_close_dialog(fake_window)

    assert events == ["deselect", "clearFocus"]


def test_main_window_search_shortcut_prefers_active_modal(monkeypatch):
    from ui import main_window as mw

    events: list[str] = []

    class _FakeModal:
        def focus_search(self):
            events.append("modal_search")

    class _FakeTab:
        def focus_search(self):
            events.append("tab_search")

    fake_window = type(
        "_FakeWindow",
        (),
        {
            "_keyboard_target_chain": lambda self: [_FakeModal(), _FakeTab()],
        },
    )()

    mw.MainWindow._on_search_activated(fake_window)

    assert events == ["modal_search"]


def test_main_window_copy_shortcut_prefers_active_modal(monkeypatch):
    from ui import main_window as mw

    events: list[str] = []

    class _FakeModal:
        def copy_selected(self):
            events.append("modal_copy")
            return True

    class _FakeTab:
        def copy_selected(self):
            events.append("tab_copy")
            return True

    fake_window = type(
        "_FakeWindow",
        (),
        {
            "_keyboard_target_chain": lambda self: [_FakeModal(), _FakeTab()],
        },
    )()

    monkeypatch.setattr(
        mw,
        "QApplication",
        type(
            "_FakeApp",
            (),
            {
                "focusWidget": staticmethod(lambda: None),
            },
        ),
        raising=True,
    )

    mw.MainWindow._on_copy_selected(fake_window)

    assert events == ["modal_copy"]


def test_main_window_confirmation_dialog_uses_arabic_action_labels(monkeypatch, qapp):
    from ui import main_window as mw

    class _FakeStatusBarWidget(QWidget):
        logout_requested = pyqtSignal()
        full_sync_requested = pyqtSignal()

        def set_current_user(self, user):
            self._user = user

        def update_sync_status(self, status):
            self._status = status

        def update_sync_progress(self, progress):
            self._progress = progress

    monkeypatch.setattr(mw, "StatusBarWidget", _FakeStatusBarWidget, raising=True)
    monkeypatch.setattr(mw.MainWindow, "_create_all_tabs", lambda self: None, raising=True)
    monkeypatch.setattr(mw.MainWindow, "apply_permissions", lambda self: None, raising=True)
    monkeypatch.setattr(mw.MainWindow, "setup_title_bar", lambda self: None, raising=True)
    monkeypatch.setattr(mw.MainWindow, "setup_auto_sync", lambda self: None, raising=True)
    monkeypatch.setattr(mw.MainWindow, "_load_initial_data_safely", lambda self: None, raising=True)
    monkeypatch.setattr(
        mw.MainWindow, "_update_initial_connection_status", lambda self: None, raising=True
    )
    monkeypatch.setattr(mw.MainWindow, "_connect_shortcuts", lambda self: None, raising=True)
    monkeypatch.setattr(
        mw.MainWindow, "_check_project_due_dates_background", lambda self: None, raising=True
    )

    repo = _FakeRepo()
    accounting_service = _FakeAccountingService()
    settings_service = _FakeService(repo)
    client_service = _FakeService(repo)
    service_service = _FakeService(repo)
    expense_service = _FakeService(repo)
    invoice_service = _FakeService(repo)
    project_service = _FakeService(repo)

    current_user = User(
        id="u1",
        username="admin",
        password_hash="x",
        role=UserRole.ADMIN,
        full_name="Admin",
        is_active=True,
    )

    window = mw.MainWindow(
        current_user=current_user,
        settings_service=settings_service,
        accounting_service=accounting_service,
        client_service=client_service,
        service_service=service_service,
        expense_service=expense_service,
        invoice_service=invoice_service,
        project_service=project_service,
        notification_service=None,
        printing_service=None,
        export_service=None,
        smart_scan_service=None,
        sync_manager=object(),
    )
    window.show()
    qapp.processEvents()

    dialog = window._build_confirmation_dialog(
        "تأكيد الإغلاق",
        "هل تريد إغلاق البرنامج الآن؟\n\nسيتم إيقاف المزامنة والخدمات بشكل آمن.",
    )

    button_texts = {button.text() for button in dialog.buttons()}
    assert "إغلاق الآن" in button_texts
    assert "البقاء في البرنامج" in button_texts
    assert dialog.isModal() is True
    assert dialog.windowModality() == mw.Qt.WindowModality.ApplicationModal
    assert dialog.windowFlags() & mw.Qt.WindowType.WindowStaysOnTopHint


def test_main_window_close_event_defers_confirmation_then_retriggers_close(monkeypatch):
    from ui import main_window as mw

    events: list[str] = []

    class _FakeEvent:
        def __init__(self):
            self.accepted = False
            self.ignored = False

        @staticmethod
        def spontaneous():
            return True

        def accept(self):
            self.accepted = True

        def ignore(self):
            self.ignored = True

    fake_window = type(
        "_FakeWindow",
        (),
        {
            "_last_close_event_log_ts": 0.0,
            "_last_close_request_ts": 0.0,
            "_allow_close": False,
            "_closing_in_progress": False,
            "_close_confirmation_pending": False,
            "_exit_confirmation_open": False,
            "_confirm_exit": lambda self, title, message: True,
            "_handle_deferred_close_confirmation": lambda self: mw.MainWindow._handle_deferred_close_confirmation(
                self
            ),
            "close": lambda self: events.append("close"),
            "isMinimized": lambda self: False,
            "raise_": lambda self: events.append("raise"),
            "activateWindow": lambda self: events.append("activate"),
        },
    )()

    monkeypatch.setattr(
        mw.QTimer,
        "singleShot",
        staticmethod(lambda _delay, callback: callback()),
        raising=False,
    )

    event = _FakeEvent()
    mw.MainWindow.closeEvent(fake_window, event)

    assert fake_window._allow_close is True
    assert fake_window._closing_in_progress is False
    assert fake_window._close_confirmation_pending is False
    assert event.ignored is True
    assert event.accepted is False
    assert events == ["raise", "activate", "close"]


def test_main_window_close_event_accepts_after_confirmation():
    from ui import main_window as mw

    events: list[str] = []

    class _FakeEvent:
        def __init__(self):
            self.accepted = False
            self.ignored = False

        @staticmethod
        def spontaneous():
            return False

        def accept(self):
            self.accepted = True

        def ignore(self):
            self.ignored = True

    fake_window = type(
        "_FakeWindow",
        (),
        {
            "_last_close_event_log_ts": 0.0,
            "_last_close_request_ts": 0.0,
            "_allow_close": True,
            "_closing_in_progress": False,
            "_close_confirmation_pending": False,
            "_exit_confirmation_open": False,
            "_stop_close_related_ui_timers": lambda self: events.append("stop"),
            "_request_application_quit": lambda self: events.append("quit"),
        },
    )()

    event = _FakeEvent()
    mw.MainWindow.closeEvent(fake_window, event)

    assert fake_window._closing_in_progress is True
    assert event.ignored is False
    assert event.accepted is True
    assert events == ["stop", "quit"]
