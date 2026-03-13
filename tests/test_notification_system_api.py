from __future__ import annotations

import types
from datetime import datetime, timedelta

import pytest

from ui import notification_system as ns


@pytest.fixture(autouse=True)
def _reset_notification_manager_state():
    ns.NotificationManager._instance = None
    ns.NotificationManager._app_is_quitting = False
    ns.NotificationManager._ui_bridge = None
    app = ns.QApplication.instance()
    if app is not None:
        try:
            app.setProperty("_skywave_force_quit", False)
        except Exception:
            pass
    yield
    instance = getattr(ns.NotificationManager, "_instance", None)
    if instance is not None and getattr(instance, "_initialized", False):
        try:
            ns.NotificationManager.shutdown()
        except Exception:
            pass
    ns.NotificationManager._instance = None
    ns.NotificationManager._app_is_quitting = False
    ns.NotificationManager._ui_bridge = None
    app = ns.QApplication.instance()
    if app is not None:
        try:
            app.setProperty("_skywave_force_quit", False)
        except Exception:
            pass


def test_coerce_legacy_duration_sync_handles_positional_sync_flag():
    duration, sync = ns.NotificationManager._coerce_legacy_duration_sync(False, True)
    assert duration is None
    assert sync is False


def test_notification_manager_defaults_to_ten_second_visibility():
    manager = ns.NotificationManager.__new__(ns.NotificationManager)
    manager._min_duration_ms = 10000
    manager._default_duration_ms = 10000
    manager._warning_duration_ms = 10000
    manager._error_duration_ms = 10000
    manager._remote_duration_ms = 10000
    assert manager._resolve_duration(None, ns.NotificationType.INFO, "short") == 10000
    assert manager._resolve_duration(None, ns.NotificationType.WARNING, "warn") == 10000
    assert manager._resolve_duration(None, ns.NotificationType.ERROR, "err") == 10000
    assert manager._resolve_duration(None, ns.NotificationType.INFO, "remote", remote=True) == 10000
    assert manager._resolve_duration(5000, ns.NotificationType.INFO, "short") == 10000
    assert manager._resolve_duration(15000, ns.NotificationType.INFO, "short") == 15000
    assert manager._resolve_duration(0, ns.NotificationType.INFO, "short") == 0


def test_toast_notification_formats_time_in_twelve_hour_clock():
    assert ns.ToastNotification._format_display_time(datetime(2026, 3, 7, 22, 23)) == "10:23 م"
    assert ns.ToastNotification._format_display_time(datetime(2026, 3, 7, 9, 5)) == "9:05 ص"


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


def test_show_sync_payload_marks_transport_only(monkeypatch):
    captured = {}

    class _Repo:
        online = True

    class _FakeSignal:
        @staticmethod
        def connect(_callback):
            return None

    class _FakeToast:
        def __init__(self, *args, **kwargs):
            self.closed = _FakeSignal()

    manager = ns.NotificationManager.__new__(ns.NotificationManager)
    manager._repo = _Repo()
    manager._resolve_duration = lambda duration, notification_type, message, remote=False: 6500
    manager._queue_or_show_notification = lambda notification: None
    manager._enqueue_sync_payload = lambda payload: captured.update(payload)

    monkeypatch.setattr(ns, "ToastNotification", _FakeToast, raising=True)
    monkeypatch.setattr(ns.NotificationManager, "_instance", manager, raising=False)
    monkeypatch.setattr(ns.NotificationManager, "__init__", lambda self: None, raising=False)

    ns.NotificationManager.show(
        "Cross-device toast",
        ns.NotificationType.INFO,
        title="Info",
        duration=1200,
        sync=True,
        entity_type="project",
        action="updated",
    )

    assert captured["transport_only"] is True
    assert captured["entity_type"] == "project"
    assert captured["action"] == "updated"


def test_show_forwards_persistent_flag_to_toast(monkeypatch):
    created = {}

    class _Repo:
        online = False

    class _FakeSignal:
        @staticmethod
        def connect(_callback):
            return None

    class _FakeToast:
        def __init__(self, *args, **kwargs):
            created.update(kwargs)
            self.closed = _FakeSignal()

    manager = ns.NotificationManager.__new__(ns.NotificationManager)
    manager._repo = _Repo()
    manager._resolve_duration = lambda duration, notification_type, message, remote=False: 10000
    manager._queue_or_show_notification = lambda notification: None

    monkeypatch.setattr(ns, "ToastNotification", _FakeToast, raising=True)
    monkeypatch.setattr(ns.NotificationManager, "_instance", manager, raising=False)
    monkeypatch.setattr(ns.NotificationManager, "__init__", lambda self: None, raising=False)

    ns.NotificationManager.show(
        "Persistent toast",
        ns.NotificationType.INFO,
        title="Pinned",
        sync=False,
        entity_type="client",
        action="updated",
        persistent=True,
    )

    assert created["persistent"] is True
    assert created["entity_type"] == "client"
    assert created["action"] == "updated"


def test_notification_sync_worker_stop_avoids_force_terminate(monkeypatch):
    worker = ns.NotificationSyncWorker()
    calls = {"request": 0, "quit": 0, "wait": [], "terminate": 0}

    monkeypatch.setattr(
        worker,
        "requestInterruption",
        lambda: calls.__setitem__("request", calls["request"] + 1),
        raising=False,
    )
    monkeypatch.setattr(
        worker,
        "quit",
        lambda: calls.__setitem__("quit", calls["quit"] + 1),
        raising=False,
    )
    monkeypatch.setattr(
        worker,
        "wait",
        lambda timeout: calls["wait"].append(timeout) or False,
        raising=False,
    )
    monkeypatch.setattr(
        worker,
        "terminate",
        lambda: calls.__setitem__("terminate", calls["terminate"] + 1),
        raising=False,
    )

    worker.stop()

    assert calls["request"] == 1
    assert calls["quit"] == 1
    assert calls["wait"] == [1500]
    assert calls["terminate"] == 0


def test_notification_manager_shutdown_does_not_create_new_instance(monkeypatch):
    ns.NotificationManager._instance = None
    monkeypatch.setattr(
        ns.NotificationManager,
        "__init__",
        lambda self: (_ for _ in ()).throw(AssertionError("should not initialize")),
        raising=False,
    )

    ns.NotificationManager.shutdown()


def test_notification_manager_skips_background_workers_during_pytest():
    manager = ns.NotificationManager()

    assert manager._sync_worker is None
    assert manager._sync_write_thread is None


def test_show_dedupes_identical_payloads_within_window(monkeypatch):
    shown = []

    class _Repo:
        online = False

    class _FakeSignal:
        @staticmethod
        def connect(_callback):
            return None

    class _FakeToast:
        def __init__(self, *args, **kwargs):
            self.closed = _FakeSignal()

    manager = ns.NotificationManager.__new__(ns.NotificationManager)
    manager._repo = _Repo()
    manager._resolve_duration = lambda duration, notification_type, message, remote=False: 6500
    manager._queue_or_show_notification = lambda notification: shown.append(notification)

    monkeypatch.setattr(ns, "ToastNotification", _FakeToast, raising=True)
    monkeypatch.setattr(ns.NotificationManager, "_instance", manager, raising=False)
    monkeypatch.setattr(ns.NotificationManager, "__init__", lambda self: None, raising=False)

    ns.NotificationManager.show(
        "Duplicate toast",
        ns.NotificationType.INFO,
        title="Info",
        sync=False,
        entity_type="project",
    )
    ns.NotificationManager.show(
        "Duplicate toast",
        ns.NotificationType.INFO,
        title="Info",
        sync=False,
        entity_type="project",
    )

    assert len(shown) == 1


def test_submit_payload_queues_when_called_off_ui_thread(monkeypatch):
    queued: list[ns.NotificationToastPayload] = []
    fake_bridge = types.SimpleNamespace(
        present_requested=types.SimpleNamespace(emit=lambda payload: queued.append(payload))
    )

    monkeypatch.setattr(
        ns,
        "QApplication",
        types.SimpleNamespace(instance=lambda: object()),
        raising=True,
    )
    monkeypatch.setattr(
        ns.NotificationManager,
        "_is_ui_thread",
        classmethod(lambda cls: False),
        raising=False,
    )
    monkeypatch.setattr(
        ns.NotificationManager,
        "_ensure_ui_bridge",
        classmethod(lambda cls: fake_bridge),
        raising=False,
    )

    payload = ns.NotificationToastPayload(
        message="Background due-project toast",
        notification_type=ns.NotificationType.WARNING,
        title="موعد استحقاق مشروع قريب",
        sync=False,
    )

    result = ns.NotificationManager._submit_payload(payload)

    assert result is True
    assert queued == [payload]


def test_notification_manager_resolves_main_window_owner_from_active_modal(qt_app, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QMainWindow

    main_window = QMainWindow()
    dialog = QDialog(main_window)

    fake_app = types.SimpleNamespace(
        activePopupWidget=lambda: None,
        activeModalWidget=lambda: dialog,
        activeWindow=lambda: dialog,
        focusWidget=lambda: dialog,
    )
    fake_qapplication = types.SimpleNamespace(
        instance=lambda: fake_app,
        topLevelWidgets=lambda: [main_window],
    )
    monkeypatch.setattr(ns, "QApplication", fake_qapplication, raising=True)
    monkeypatch.setattr(ns.NotificationManager, "_instance", None, raising=False)

    manager = ns.NotificationManager.__new__(ns.NotificationManager)

    owner = ns.NotificationManager._resolve_toast_owner(manager)

    assert owner is main_window


def test_present_payload_passes_resolved_owner_to_toast(monkeypatch):
    captured = {}

    class _FakeSignal:
        @staticmethod
        def connect(_callback):
            return None

    class _FakeToast:
        def __init__(self, *args, **kwargs):
            captured["owner_window"] = kwargs.get("owner_window")
            captured["parent"] = kwargs.get("parent")
            self.closed = _FakeSignal()

    owner = object()
    monkeypatch.setattr(ns.NotificationManager, "_instance", None, raising=False)
    manager = ns.NotificationManager.__new__(ns.NotificationManager)
    manager._repo = None
    manager._queue_or_show_notification = lambda notification: captured.update(
        {"queued": notification}
    )
    manager._resolve_toast_owner = lambda: owner

    monkeypatch.setattr(ns, "ToastNotification", _FakeToast, raising=True)

    payload = ns.NotificationToastPayload(
        message="Owned toast",
        notification_type=ns.NotificationType.INFO,
        title="Info",
        sync=False,
    )

    result = ns.NotificationManager._present_payload(manager, payload)

    assert result is True
    assert captured["owner_window"] is owner
    assert captured["parent"] is None


def test_transport_cleanup_query_targets_only_ephemeral_notification_docs():
    cutoff_dt = datetime(2026, 3, 7, 12, 0, 0)
    cutoff_iso = cutoff_dt.isoformat()

    query = ns.NotificationSyncWorker._transport_cleanup_query(cutoff_iso, cutoff_dt)

    assert {
        "$or": [
            {"created_at": {"$lt": cutoff_iso}},
            {"created_at": {"$lt": cutoff_dt}},
        ]
    } in query["$and"]
    assert {
        "$or": [
            {"transport_only": True},
            {"action": "sync_ping"},
            {"silent": True},
        ]
    } in query["$and"]


def test_check_new_notifications_ignores_deleted_remote_documents(monkeypatch):
    emitted: list[dict] = []
    sync_calls: list[set[str]] = []

    class _Cursor:
        def __init__(self, docs):
            self._docs = list(docs)

        def sort(self, *_args, **_kwargs):
            return self

        def limit(self, size):
            return self._docs[:size]

    class _Collection:
        def __init__(self, docs):
            self._docs = docs

        def find(self, _query=None):
            return _Cursor(self._docs)

    deleted_doc = {
        "_id": "deleted-1",
        "title": "Deleted",
        "message": "Should not appear",
        "type": "info",
        "entity_type": "project",
        "device_id": "DEVICE-OTHER",
        "created_at": "2999-01-01T12:00:00",
        "sync_status": "deleted",
        "is_deleted": True,
    }
    active_doc = {
        "_id": "active-1",
        "title": "Active",
        "message": "Should appear",
        "type": "info",
        "entity_type": "project",
        "device_id": "DEVICE-OTHER",
        "created_at": "2999-01-01T12:01:00",
        "sync_status": "synced",
        "is_deleted": False,
    }

    worker = ns.NotificationSyncWorker()
    worker.repo = types.SimpleNamespace(
        mongo_db=types.SimpleNamespace(notifications=_Collection([deleted_doc, active_doc]))
    )
    worker.new_notification.connect(emitted.append)
    worker._trigger_instant_sync = lambda tables: sync_calls.append(set(tables))
    worker._trigger_settings_sync = lambda: None
    monkeypatch.setattr(ns, "DEVICE_ID", "DEVICE-LOCAL", raising=True)

    result = worker._check_new_notifications()

    assert result is True
    assert emitted == [
        {
            "message": "Should appear",
            "type": "info",
            "title": "Active",
            "device_id": "DEVICE-OTHER",
            "entity_type": "project",
            "action": None,
        }
    ]
    assert sync_calls == [{"projects"}]


def test_check_new_notifications_skips_pre_session_history(monkeypatch):
    emitted: list[dict] = []
    sync_calls: list[set[str]] = []

    class _Cursor:
        def __init__(self, docs):
            self._docs = list(docs)

        def sort(self, *_args, **_kwargs):
            return self

        def limit(self, size):
            return self._docs[:size]

    class _Collection:
        def __init__(self, docs):
            self._docs = docs

        def find(self, _query=None):
            return _Cursor(self._docs)

    session_started_at = datetime(2026, 3, 7, 12, 0, 0)
    stale_doc = {
        "_id": "stale-1",
        "title": "Stale",
        "message": "Old toast",
        "type": "info",
        "entity_type": "project",
        "device_id": "DEVICE-OTHER",
        "created_at": (session_started_at - timedelta(minutes=5)).isoformat(),
        "sync_status": "synced",
        "is_deleted": False,
    }
    fresh_doc = {
        "_id": "fresh-1",
        "title": "Fresh",
        "message": "New toast",
        "type": "info",
        "entity_type": "project",
        "device_id": "DEVICE-OTHER",
        "created_at": (session_started_at + timedelta(seconds=10)).isoformat(),
        "sync_status": "synced",
        "is_deleted": False,
    }

    worker = ns.NotificationSyncWorker()
    worker.repo = types.SimpleNamespace(
        mongo_db=types.SimpleNamespace(notifications=_Collection([stale_doc, fresh_doc]))
    )
    worker._session_started_at = session_started_at
    worker.new_notification.connect(emitted.append)
    worker._trigger_instant_sync = lambda tables: sync_calls.append(set(tables))
    worker._trigger_settings_sync = lambda: None
    monkeypatch.setattr(ns, "DEVICE_ID", "DEVICE-LOCAL", raising=True)

    result = worker._check_new_notifications()

    assert result is True
    assert stale_doc["_id"] in worker._seen_ids
    assert emitted == [
        {
            "message": "New toast",
            "type": "info",
            "title": "Fresh",
            "device_id": "DEVICE-OTHER",
            "entity_type": "project",
            "action": None,
        }
    ]
    assert sync_calls == [{"projects"}]


def test_check_new_notifications_accepts_related_entity_type_fallback(monkeypatch):
    emitted: list[dict] = []
    sync_calls: list[set[str]] = []

    class _Cursor:
        def __init__(self, docs):
            self._docs = list(docs)

        def sort(self, *_args, **_kwargs):
            return self

        def limit(self, size):
            return self._docs[:size]

    class _Collection:
        def __init__(self, docs):
            self._docs = docs

        def find(self, _query=None):
            return _Cursor(self._docs)

    related_doc = {
        "_id": "related-1",
        "title": "Payment Saved",
        "message": "Remote persisted notification",
        "type": "success",
        "related_entity_type": "payments",
        "device_id": "DEVICE-OTHER",
        "created_at": "2999-01-01T12:02:00",
        "sync_status": "synced",
        "is_deleted": False,
    }

    worker = ns.NotificationSyncWorker()
    worker.repo = types.SimpleNamespace(
        mongo_db=types.SimpleNamespace(notifications=_Collection([related_doc]))
    )
    worker.new_notification.connect(emitted.append)
    worker._trigger_instant_sync = lambda tables: sync_calls.append(set(tables))
    worker._trigger_settings_sync = lambda: None
    monkeypatch.setattr(ns, "DEVICE_ID", "DEVICE-LOCAL", raising=True)

    result = worker._check_new_notifications()

    assert result is True
    assert emitted == [
        {
            "message": "Remote persisted notification",
            "type": "success",
            "title": "Payment Saved",
            "device_id": "DEVICE-OTHER",
            "entity_type": "payments",
            "action": None,
        }
    ]
    assert sync_calls == [{"notifications", "payments"}]


def test_check_new_notifications_keeps_activity_notifications_silent(monkeypatch):
    emitted: list[dict] = []
    sync_calls: list[set[str]] = []

    class _Cursor:
        def __init__(self, docs):
            self._docs = list(docs)

        def sort(self, *_args, **_kwargs):
            return self

        def limit(self, size):
            return self._docs[:size]

    class _Collection:
        def __init__(self, docs):
            self._docs = docs

        def find(self, _query=None):
            return _Cursor(self._docs)

    activity_doc = {
        "_id": "activity-1",
        "title": "تم تعديل عميل",
        "message": "Katkoty kids wear",
        "type": "success",
        "related_entity_type": "clients",
        "device_id": "DEVICE-OTHER",
        "created_at": "2999-01-01T12:03:00",
        "sync_status": "synced",
        "is_deleted": False,
        "is_activity": True,
        "operation_text": "تعديل عميل",
    }

    worker = ns.NotificationSyncWorker()
    worker.repo = types.SimpleNamespace(
        mongo_db=types.SimpleNamespace(notifications=_Collection([activity_doc]))
    )
    worker.new_notification.connect(emitted.append)
    worker._trigger_instant_sync = lambda tables: sync_calls.append(set(tables))
    worker._trigger_settings_sync = lambda: None
    monkeypatch.setattr(ns, "DEVICE_ID", "DEVICE-LOCAL", raising=True)

    result = worker._check_new_notifications()

    assert result is True
    assert emitted == []
    assert sync_calls == [{"clients", "notifications"}]
