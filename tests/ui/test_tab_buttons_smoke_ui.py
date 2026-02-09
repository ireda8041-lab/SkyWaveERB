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


def test_client_logo_cache_keys_are_normalized_to_string(qapp):
    from PyQt6.QtCore import QBuffer, QIODevice
    from PyQt6.QtGui import QColor, QPixmap

    from core import schemas
    from ui import client_manager

    class _Service:
        def __getattr__(self, name):
            def _noop(*args, **kwargs):
                _ = (name, args, kwargs)
                return None

            return _noop

    tab = client_manager.ClientManagerTab(client_service=_Service())
    tab.show()
    qapp.processEvents()

    # Generate a valid tiny PNG in-memory.
    pixmap = QPixmap(2, 2)
    pixmap.fill(QColor("#2563eb"))
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    assert pixmap.save(buf, "PNG")
    logo_b64 = bytes(buf.data().toBase64()).decode("ascii")
    client = schemas.Client(id=1, name="Client A", has_logo=True, logo_data=logo_b64)

    icon = tab._get_client_logo_icon(client)
    assert icon is not None
    assert "1" in tab._logo_icon_cache
    assert "1" in tab._logo_pixmap_cache

    tab._on_client_logo_loaded("1")
    assert "1" not in tab._logo_icon_cache


def test_clients_changed_clears_logo_caches_and_reloads(qapp, monkeypatch):
    from PyQt6.QtGui import QIcon, QPixmap

    from ui import client_manager

    class _Service:
        def invalidate_cache(self):
            return None

        def __getattr__(self, _name):
            def _noop(*args, **kwargs):
                _ = (args, kwargs)
                return None

            return _noop

    tab = client_manager.ClientManagerTab(client_service=_Service())
    tab.show()
    qapp.processEvents()

    pm = QPixmap(2, 2)
    pm.fill()
    tab._logo_icon_cache["x"] = QIcon(pm)
    tab._logo_pixmap_cache["x"] = pm
    tab._logo_state_cache["x"] = "old"

    called = []
    monkeypatch.setattr(
        tab,
        "load_clients_data",
        lambda force_refresh=False: called.append(bool(force_refresh)),
        raising=True,
    )

    tab._on_clients_changed()

    assert tab._logo_icon_cache == {}
    assert tab._logo_pixmap_cache == {}
    assert tab._logo_state_cache == {}
    assert called == [True]
