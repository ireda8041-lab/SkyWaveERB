from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest


class _NoopService:
    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return None

        return _noop


def test_clients_tab_buttons_click_without_crash(monkeypatch, qapp):
    from ui import client_manager

    monkeypatch.setattr(
        client_manager.ClientManagerTab,
        "delete_selected_client",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        client_manager.ClientManagerTab,
        "export_clients",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        client_manager.ClientManagerTab,
        "import_clients",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        client_manager.ClientManagerTab,
        "load_clients_data",
        lambda *args, **kwargs: None,
        raising=True,
    )

    tab = client_manager.ClientManagerTab(client_service=_NoopService())
    tab.show()

    monkeypatch.setattr(tab, "open_editor", lambda *args, **kwargs: None, raising=True)
    monkeypatch.setattr(tab, "open_editor_for_selected", lambda *args, **kwargs: None, raising=True)

    QTest.mouseClick(tab.add_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.edit_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.delete_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.export_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.import_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.refresh_button, Qt.MouseButton.LeftButton)


def test_services_tab_buttons_click_without_crash(monkeypatch, qapp):
    from ui import service_manager

    monkeypatch.setattr(
        service_manager.ServiceManagerTab,
        "archive_selected_service",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        service_manager.ServiceManagerTab,
        "load_services_data",
        lambda *args, **kwargs: None,
        raising=True,
    )

    tab = service_manager.ServiceManagerTab(service_service=_NoopService())
    tab.show()

    monkeypatch.setattr(tab, "open_editor", lambda *args, **kwargs: None, raising=True)
    monkeypatch.setattr(tab, "open_editor_for_selected", lambda *args, **kwargs: None, raising=True)

    QTest.mouseClick(tab.add_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.edit_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.archive_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(tab.refresh_button, Qt.MouseButton.LeftButton)
