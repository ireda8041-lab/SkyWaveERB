from __future__ import annotations

import sys
import types

from core.notification_bridge import NotificationBridge


def test_operation_toasts_are_local_only_sync_false(monkeypatch):
    captured = {}

    fake_notif_module = types.SimpleNamespace(
        notify_success=lambda message, title=None, **kwargs: captured.update(
            {"kind": "success", "message": message, "title": title, "kwargs": kwargs}
        ),
        notify_warning=lambda message, title=None, **kwargs: captured.update(
            {"kind": "warning", "message": message, "title": title, "kwargs": kwargs}
        ),
    )
    monkeypatch.setitem(sys.modules, "ui.notification_system", fake_notif_module)

    bridge = NotificationBridge()
    bridge._on_operation("updated", "project", "P1")  # pylint: disable=protected-access

    assert captured["kind"] == "success"
    assert captured["message"] == "P1"
    assert captured["kwargs"]["sync"] is False
