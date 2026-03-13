from __future__ import annotations

import sys
import types

from core.notification_bridge import NotificationBridge
from services.notification_service import NotificationService


def test_operation_toasts_are_local_only_sync_false(monkeypatch):
    captured = {}
    monkeypatch.setattr(NotificationService, "_active_instance", None, raising=False)

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
    from core.event_bus import EventBus

    db_path = tmp_path / "notification_bridge_activity.db"
    monkeypatch.setenv("SKYWAVE_DISABLE_MONGO", "1")
    monkeypatch.setattr(repo_mod, "LOCAL_DB_FILE", str(db_path), raising=True)
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_connection", lambda self: None, raising=True
    )
    monkeypatch.setattr(
        repo_mod.Repository, "_start_mongo_retry_loop", lambda self: None, raising=True
    )

    repo = repo_mod.Repository()
    try:
        service = NotificationService(repo, EventBus())
        toasts: list[tuple[str, str]] = []
        monkeypatch.setattr(
            service,
            "_show_local_toast",
            lambda notification: toasts.append((notification.title, notification.message)),
        )

        bridge = NotificationBridge()
        bridge._on_operation(  # pylint: disable=protected-access
            "paid",
            "payment",
            "2,000 ج.م - Vet Icon",
        )

        logs = repo.get_recent_activity_logs(1)
        notification_row = repo.sqlite_conn.execute(
            """
            SELECT message, action, operation_text, amount, is_activity, is_read
            FROM notifications
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        assert logs
        assert logs[0]["operation"] == "تحصيل دفعة"
        assert logs[0]["description"] == "Vet Icon"
        assert logs[0]["amount"] == 2000.0
        assert notification_row["message"] == "Vet Icon"
        assert notification_row["action"] == "paid"
        assert notification_row["operation_text"] == "تحصيل دفعة"
        assert notification_row["amount"] == 2000.0
        assert notification_row["is_activity"] == 1
        assert notification_row["is_read"] == 1
        assert toasts == []
    finally:
        repo.close()
