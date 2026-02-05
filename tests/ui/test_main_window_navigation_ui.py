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

    class _FakeTemplateService:
        def __init__(self, repository, settings_service):
            self.repository = repository
            self.settings_service = settings_service

    class _FakeStatusBarWidget(QWidget):
        logout_requested = pyqtSignal()
        full_sync_requested = pyqtSignal()

        def set_current_user(self, user):
            self._user = user

        def update_sync_status(self, status):
            self._status = status

        def update_sync_progress(self, progress):
            self._progress = progress

    monkeypatch.setattr(mw, "TemplateService", _FakeTemplateService, raising=True)
    monkeypatch.setattr(mw, "StatusBarWidget", _FakeStatusBarWidget, raising=True)

    expected_tabs = [
        "🏠 الصفحة الرئيسية",
        "🚀 المشاريع",
        "💳 المصروفات",
        "💰 الدفعات",
        "👤 العملاء",
        "🛠️ الخدمات والباقات",
        "📊 المحاسبة",
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
