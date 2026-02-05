from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

from core.auth_models import User, UserRole


class _StubRepo:
    pass


class _StubAccountingService:
    def __init__(self, repo):
        self.repo = repo


class _StubService:
    def __init__(self, repo):
        self.repo = repo


def test_main_window_instantiates_real_tabs_without_loading(monkeypatch, qapp):
    from ui import main_window as mw

    class _StubTemplateService:
        def __init__(self, repository, settings_service):
            self.repository = repository
            self.settings_service = settings_service

    class _StubStatusBarWidget(QWidget):
        logout_requested = pyqtSignal()
        full_sync_requested = pyqtSignal()

        def set_current_user(self, user):
            self._user = user

        def update_sync_status(self, status):
            self._status = status

        def update_sync_progress(self, progress):
            self._progress = progress

    monkeypatch.setattr(mw, "TemplateService", _StubTemplateService, raising=True)
    monkeypatch.setattr(mw, "StatusBarWidget", _StubStatusBarWidget, raising=True)

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
    monkeypatch.setattr(mw.MainWindow, "apply_permissions", lambda self: None, raising=True)

    repo = _StubRepo()
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
        settings_service=_StubService(repo),
        accounting_service=_StubAccountingService(repo),
        client_service=_StubService(repo),
        service_service=_StubService(repo),
        expense_service=_StubService(repo),
        invoice_service=_StubService(repo),
        project_service=_StubService(repo),
        notification_service=None,
        printing_service=None,
        export_service=None,
        smart_scan_service=None,
        sync_manager=object(),
    )
    window.show()
    qapp.processEvents()

    assert window.tabs.count() >= 7
    assert window.tabs.tabText(0) == "🏠 الصفحة الرئيسية"
