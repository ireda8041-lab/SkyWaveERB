from __future__ import annotations

from ui import notification_system as ns


def test_coerce_legacy_duration_sync_handles_positional_sync_flag():
    duration, sync = ns.NotificationManager._coerce_legacy_duration_sync(False, True)
    assert duration is None
    assert sync is False


def test_notify_success_forwards_duration_and_sync(monkeypatch):
    captured = {}

    def fake_success(message, title=None, duration=None, sync=True, entity_type=None, action=None):
        captured["message"] = message
        captured["title"] = title
        captured["duration"] = duration
        captured["sync"] = sync
        captured["entity_type"] = entity_type
        captured["action"] = action

    monkeypatch.setattr(ns.NotificationManager, "success", fake_success, raising=True)

    ns.notify_success(
        "ok",
        "done",
        duration=22000,
        sync=False,
        entity_type="project",
        action="updated",
    )

    assert captured == {
        "message": "ok",
        "title": "done",
        "duration": 22000,
        "sync": False,
        "entity_type": "project",
        "action": "updated",
    }


def test_prune_keeps_hidden_notification_if_not_closing(monkeypatch):
    manager = ns.NotificationManager.__new__(ns.NotificationManager)
    manager._notifications = []

    restore_calls = {"count": 0}

    class _FakeTimer:
        @staticmethod
        def singleShot(_ms, callback):
            restore_calls["count"] += 1
            callback()

    class _FakeCloseTimer:
        @staticmethod
        def isActive():
            return False

    class _FakeNotification:
        _shown_at_mono = 1.0
        _is_closing = False
        _restoring_visibility = False
        close_timer = _FakeCloseTimer()

        @staticmethod
        def isVisible():
            return False

        @staticmethod
        def _restore_visibility():
            return None

    monkeypatch.setattr(ns, "QTimer", _FakeTimer, raising=True)

    notif = _FakeNotification()
    manager._notifications = [notif]
    ns.NotificationManager._prune_notifications(manager)

    assert manager._notifications == [notif]
    assert restore_calls["count"] == 1
