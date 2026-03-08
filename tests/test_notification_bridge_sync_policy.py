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


def test_operation_bridge_records_activity_log_in_repository(monkeypatch, tmp_path):
    import core.repository as repo_mod

    db_path = tmp_path / "notification_bridge_activity.db"
    monkeypatch.setenv("SKYWAVE_DISABLE_MONGO", "1")
    monkeypatch.setattr(repo_mod, "LOCAL_DB_FILE", str(db_path), raising=True)
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_connection", lambda self: None, raising=True
    )
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_retry_loop", lambda self: None, raising=True
    )

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

    repo = repo_mod.Repository()
    try:
        bridge = NotificationBridge()
        bridge._on_operation(  # pylint: disable=protected-access
            "paid",
            "payment",
            "2,000 ج.م - Vet Icon",
        )

        logs = repo.get_recent_activity_logs(1)

        assert captured["kind"] == "success"
        assert logs
        assert logs[0]["operation"] == "تحصيل دفعة"
        assert logs[0]["description"] == "Vet Icon"
        assert logs[0]["amount"] == 2000.0
    finally:
        repo.close()
