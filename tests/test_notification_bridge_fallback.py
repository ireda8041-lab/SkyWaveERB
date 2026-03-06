from __future__ import annotations

import sys
import types

from core import notification_bridge as bridge


def test_notify_operation_uses_local_fallback_when_bridge_disconnected(monkeypatch):
    emitted = {}
    shown = {}

    monkeypatch.setattr(bridge.NotificationBridge, "_connected", False, raising=False)

    class _FakeApp:
        @staticmethod
        def instance():
            return object()

    monkeypatch.setattr(bridge, "QApplication", _FakeApp, raising=True)
    monkeypatch.setattr(
        bridge.app_signals,
        "emit_operation",
        lambda action, entity_type, entity_name: emitted.update(
            {"action": action, "entity_type": entity_type, "entity_name": entity_name}
        ),
        raising=True,
    )

    fake_notif_module = types.SimpleNamespace(
        notify_success=lambda message, title=None, **kwargs: shown.update(
            {"message": message, "title": title, "kind": "success", "kwargs": kwargs}
        ),
        notify_warning=lambda message, title=None, **kwargs: shown.update(
            {"message": message, "title": title, "kind": "warning", "kwargs": kwargs}
        ),
    )
    monkeypatch.setitem(sys.modules, "ui.notification_system", fake_notif_module)

    bridge.notify_operation("updated", "project", "Proj A")

    assert emitted == {"action": "updated", "entity_type": "project", "entity_name": "Proj A"}
    assert shown["kind"] == "success"
    assert shown["message"] == "Proj A"
    assert shown["kwargs"]["sync"] is False
