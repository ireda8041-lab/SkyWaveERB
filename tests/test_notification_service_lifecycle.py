from __future__ import annotations

import logging
import types
from datetime import datetime, timedelta

import pytest

from core import schemas
from services.notification_service import NotificationService


@pytest.fixture()
def sqlite_repo(tmp_path, monkeypatch):
    import core.repository as repo_mod

    db_path = tmp_path / "notification_service.db"
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
        yield repo
    finally:
        repo.close()


def test_notification_service_crud_updates_sync_state_and_filters_deleted_rows(
    sqlite_repo, mock_event_bus, monkeypatch
):
    service = NotificationService(sqlite_repo, mock_event_bus)
    signals: list[str] = []
    monkeypatch.setattr(
        "services.notification_service.app_signals.emit_data_changed",
        lambda data_type: signals.append(data_type),
    )

    created = service.create_notification(
        title="Signal Notification",
        message="Unread notification",
        type=schemas.NotificationType.INFO,
        priority=schemas.NotificationPriority.MEDIUM,
    )

    assert created is not None
    assert signals == ["notifications"]

    row = sqlite_repo.sqlite_conn.execute(
        "SELECT is_read, sync_status, dirty_flag, is_deleted FROM notifications WHERE id = ?",
        (created.id,),
    ).fetchone()
    assert row["is_read"] == 0
    assert row["sync_status"] == "new_offline"
    assert row["dirty_flag"] == 1
    assert row["is_deleted"] == 0

    assert service.mark_as_read(created.id) is True
    row = sqlite_repo.sqlite_conn.execute(
        "SELECT is_read, sync_status, dirty_flag, is_deleted FROM notifications WHERE id = ?",
        (created.id,),
    ).fetchone()
    assert row["is_read"] == 1
    assert row["sync_status"] == "modified_offline"
    assert row["dirty_flag"] == 1
    assert row["is_deleted"] == 0
    assert signals == ["notifications", "notifications"]

    assert service.delete_notification(created.id) is True
    row = sqlite_repo.sqlite_conn.execute(
        "SELECT is_read, sync_status, dirty_flag, is_deleted FROM notifications WHERE id = ?",
        (created.id,),
    ).fetchone()
    assert row["sync_status"] == "deleted"
    assert row["dirty_flag"] == 1
    assert row["is_deleted"] == 1


def test_notification_service_notification_columns_falls_back_and_logs(
    sqlite_repo, mock_event_bus, monkeypatch, caplog
):
    service = NotificationService(sqlite_repo, mock_event_bus)

    def _boom():
        raise RuntimeError("pragma failed")

    monkeypatch.setattr(service.repo, "get_cursor", _boom)
    service._notification_columns_cache = None

    with caplog.at_level(logging.DEBUG, logger="SkyWaveERP.services.notification_service"):
        columns = service._notification_columns()

    assert "title" in columns
    assert "message" in columns
    assert any("تعذر فحص أعمدة notifications" in record.message for record in caplog.records)


def test_notification_service_mark_all_as_read_emits_signal(
    sqlite_repo, mock_event_bus, monkeypatch
):
    service = NotificationService(sqlite_repo, mock_event_bus)
    signals: list[str] = []
    monkeypatch.setattr(
        "services.notification_service.app_signals.emit_data_changed",
        lambda data_type: signals.append(data_type),
    )

    first = service.create_notification("First", "First unread")
    second = service.create_notification("Second", "Second unread")
    assert first is not None
    assert second is not None

    signals.clear()
    assert service.mark_all_as_read() is True

    rows = sqlite_repo.sqlite_conn.execute(
        """
        SELECT is_read, sync_status, dirty_flag
        FROM notifications
        WHERE id IN (?, ?)
        ORDER BY id ASC
        """,
        (first.id, second.id),
    ).fetchall()

    assert signals == ["notifications"]
    assert service.get_unread_count() == 0
    assert len(rows) == 2
    assert all(row["is_read"] == 1 for row in rows)
    assert all(row["sync_status"] == "modified_offline" for row in rows)
    assert all(row["dirty_flag"] == 1 for row in rows)


def test_notification_service_delete_old_notifications_soft_deletes_only_old_rows(
    sqlite_repo, mock_event_bus, monkeypatch
):
    service = NotificationService(sqlite_repo, mock_event_bus)
    signals: list[str] = []
    monkeypatch.setattr(
        "services.notification_service.app_signals.emit_data_changed",
        lambda data_type: signals.append(data_type),
    )

    current = service.create_notification("Current", "Keep me")
    old = service.create_notification("Old", "Archive me")
    assert current is not None
    assert old is not None

    old_stamp = (datetime.now() - timedelta(days=90)).isoformat()
    sqlite_repo.sqlite_conn.execute(
        """
        UPDATE notifications
        SET created_at = ?, last_modified = ?, is_read = 1
        WHERE id = ?
        """,
        (old_stamp, old_stamp, old.id),
    )
    sqlite_repo.sqlite_conn.commit()

    signals.clear()
    assert service.delete_old_notifications(days=30) == 1

    active_ids = [notification.id for notification in service.get_all_notifications(limit=10)]
    old_row = sqlite_repo.sqlite_conn.execute(
        "SELECT sync_status, dirty_flag, is_deleted FROM notifications WHERE id = ?",
        (old.id,),
    ).fetchone()

    assert signals == ["notifications"]
    assert current.id in active_ids
    assert old.id not in active_ids
    assert old_row["sync_status"] == "deleted"
    assert old_row["dirty_flag"] == 1
    assert old_row["is_deleted"] == 1


def test_notification_service_online_save_tags_remote_record_with_device_id(
    sqlite_repo, mock_event_bus, monkeypatch
):
    inserted: list[dict] = []

    class _FakeNotificationsCollection:
        @staticmethod
        def insert_one(payload: dict):
            inserted.append(dict(payload))

            class _Result:
                inserted_id = "mongo-notification-1"

            return _Result()

    sqlite_repo.online = True
    sqlite_repo.mongo_db = types.SimpleNamespace(notifications=_FakeNotificationsCollection())
    monkeypatch.setattr("services.notification_service.get_stable_device_id", lambda: "DEVICE-42")

    service = NotificationService(sqlite_repo, mock_event_bus)
    monkeypatch.setattr(service, "_show_local_toast", lambda notification: None)

    created = service.create_notification(
        title="Cloud Notification",
        message="Persisted remotely",
        type=schemas.NotificationType.INFO,
        priority=schemas.NotificationPriority.MEDIUM,
        related_entity_type="project",
        related_entity_id="mongo-project-1",
    )

    row = sqlite_repo.sqlite_conn.execute(
        "SELECT _mongo_id, sync_status, dirty_flag FROM notifications WHERE id = ?",
        (created.id,),
    ).fetchone()

    assert inserted[0]["device_id"] == "DEVICE-42"
    assert inserted[0]["sync_status"] == "synced"
    assert inserted[0]["is_deleted"] is False
    assert inserted[0]["entity_type"] == "project"
    assert inserted[0]["related_entity_type"] == "project"
    assert inserted[0]["related_entity_id"] == "mongo-project-1"
    assert row["_mongo_id"] == "mongo-notification-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0


def test_notification_service_online_save_avoids_bool_check_on_mongo_database(
    sqlite_repo, mock_event_bus, monkeypatch
):
    inserted: list[dict] = []

    class _FakeNotificationsCollection:
        @staticmethod
        def insert_one(payload: dict):
            inserted.append(dict(payload))
            return types.SimpleNamespace(inserted_id="mongo-notification-bool-1")

    class _MongoDatabaseProxy:
        notifications = _FakeNotificationsCollection()

        def __bool__(self):
            raise TypeError(
                "Database objects do not implement truth value testing or bool(). "
                "Please compare with None instead: database is not None"
            )

    sqlite_repo.online = True
    sqlite_repo.mongo_db = _MongoDatabaseProxy()
    monkeypatch.setattr("services.notification_service.get_stable_device_id", lambda: "DEVICE-99")

    service = NotificationService(sqlite_repo, mock_event_bus)
    monkeypatch.setattr(service, "_show_local_toast", lambda notification: None)

    created = service.create_notification(
        title="Bool Safe Notification",
        message="Should save remotely",
        type=schemas.NotificationType.INFO,
        priority=schemas.NotificationPriority.MEDIUM,
    )

    row = sqlite_repo.sqlite_conn.execute(
        "SELECT _mongo_id, sync_status, dirty_flag FROM notifications WHERE id = ?",
        (created.id,),
    ).fetchone()

    assert created is not None
    assert inserted[0]["device_id"] == "DEVICE-99"
    assert row["_mongo_id"] == "mongo-notification-bool-1"
    assert row["sync_status"] == "synced"
    assert row["dirty_flag"] == 0


def test_notification_service_activity_notifications_persist_structured_operation_fields(
    sqlite_repo, mock_event_bus, monkeypatch
):
    service = NotificationService(sqlite_repo, mock_event_bus)
    monkeypatch.setattr(service, "_show_local_toast", lambda notification: None)

    regular = service.create_notification(
        title="Reminder",
        message="General reminder",
        type=schemas.NotificationType.INFO,
        priority=schemas.NotificationPriority.MEDIUM,
    )
    activity = service.create_notification(
        title="تم تحصيل دفعة",
        message="Alpha Project",
        type=schemas.NotificationType.SUCCESS,
        priority=schemas.NotificationPriority.MEDIUM,
        related_entity_type="payment",
        action="paid",
        operation_text="تحصيل دفعة",
        details="العميل: Blue Nile",
        amount=750.0,
        is_activity=True,
        is_read=True,
    )

    assert regular is not None
    assert activity is not None

    row = sqlite_repo.sqlite_conn.execute(
        """
        SELECT action, operation_text, details, amount, is_activity, is_read
        FROM notifications
        WHERE id = ?
        """,
        (activity.id,),
    ).fetchone()

    activities = service.get_recent_activities(limit=5)

    assert row["action"] == "paid"
    assert row["operation_text"] == "تحصيل دفعة"
    assert row["details"] == "العميل: Blue Nile"
    assert row["amount"] == pytest.approx(750.0)
    assert row["is_activity"] == 1
    assert row["is_read"] == 1
    assert [notification.id for notification in activities] == [activity.id]
    assert activities[0].is_activity is True
    assert activities[0].operation_text == "تحصيل دفعة"
    assert activities[0].amount == pytest.approx(750.0)


def test_notification_service_excludes_activity_rows_from_general_notifications(
    sqlite_repo, mock_event_bus, monkeypatch
):
    service = NotificationService(sqlite_repo, mock_event_bus)
    monkeypatch.setattr(service, "_show_local_toast", lambda notification: None)

    regular = service.create_notification(
        title="Invoice Reminder",
        message="Outstanding invoice",
        type=schemas.NotificationType.INFO,
        priority=schemas.NotificationPriority.MEDIUM,
    )
    activity = service.create_notification(
        title="تم تعديل عميل",
        message="Katkoty kids wear",
        type=schemas.NotificationType.SUCCESS,
        priority=schemas.NotificationPriority.MEDIUM,
        related_entity_type="clients",
        related_entity_id="client-42",
        action="updated",
        operation_text="تعديل عميل",
        is_activity=True,
        is_read=False,
    )

    assert regular is not None
    assert activity is not None
    assert [notification.id for notification in service.get_all_notifications(limit=10)] == [
        regular.id
    ]
    assert [notification.id for notification in service.get_unread_notifications(limit=10)] == [
        regular.id
    ]
    assert service.get_unread_count() == 1
    assert {
        notification.id
        for notification in service.get_all_notifications(limit=10, include_activity=True)
    } == {regular.id, activity.id}


def test_notification_service_deduplicates_recent_identical_notifications(
    sqlite_repo, mock_event_bus, monkeypatch
):
    service = NotificationService(sqlite_repo, mock_event_bus)
    monkeypatch.setattr(service, "_show_local_toast", lambda notification: None)

    first = service.create_notification(
        title="Sync Failed",
        message="Cloud connection dropped",
        type=schemas.NotificationType.ERROR,
        priority=schemas.NotificationPriority.HIGH,
        related_entity_type="sync",
    )
    second = service.create_notification(
        title="Sync Failed",
        message="Cloud connection dropped",
        type=schemas.NotificationType.ERROR,
        priority=schemas.NotificationPriority.HIGH,
        related_entity_type="sync",
    )

    assert first is not None
    assert second is not None
    assert second.id == first.id
    row = sqlite_repo.sqlite_conn.execute("SELECT COUNT(*) FROM notifications").fetchone()
    assert row[0] == 1


def test_notification_service_local_toast_routes_through_notification_manager(
    sqlite_repo, mock_event_bus, monkeypatch
):
    from ui.notification_system import NotificationType as UiNotificationType

    captured = {}

    monkeypatch.setattr(
        "services.notification_service.QApplication.instance",
        lambda: object(),
    )
    monkeypatch.setattr(
        "ui.notification_system.NotificationManager.show",
        lambda message, notification_type, title=None, duration=None, sync=True, entity_type=None, action=None: captured.update(
            {
                "message": message,
                "notification_type": notification_type,
                "title": title,
                "duration": duration,
                "sync": sync,
                "entity_type": entity_type,
                "action": action,
            }
        ),
    )

    service = NotificationService(sqlite_repo, mock_event_bus)
    service._show_local_toast(
        schemas.Notification(
            title="Payment Saved",
            message="Persistent toast",
            type=schemas.NotificationType.PAYMENT_RECEIVED,
            priority=schemas.NotificationPriority.MEDIUM,
            related_entity_type="payments",
            related_entity_id="payment-1",
        )
    )

    assert captured == {
        "message": "Persistent toast",
        "notification_type": UiNotificationType.SUCCESS,
        "title": "Payment Saved",
        "duration": None,
        "sync": False,
        "entity_type": "payments",
        "action": None,
    }


def test_notification_service_project_due_deduplicates_by_stable_project_reference(
    sqlite_repo, mock_event_bus, monkeypatch
):
    project = sqlite_repo.create_project(
        schemas.Project(
            name="Due Notification Project",
            client_id="CLIENT-DUE-1",
            total_amount=1500.0,
            end_date=datetime.now() + timedelta(days=3),
            status=schemas.ProjectStatus.ACTIVE,
        )
    )
    assert project.id is not None

    sqlite_repo.sqlite_conn.execute(
        "UPDATE projects SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
        ("mongo-project-due-1", int(project.id)),
    )
    sqlite_repo.sqlite_conn.execute(
        """
        INSERT INTO notifications (
            sync_status, created_at, last_modified, title, message, type, priority,
            is_read, related_entity_type, related_entity_id, dirty_flag, is_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "synced",
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            "Existing due reminder",
            "Already synced from another device",
            schemas.NotificationType.PROJECT_DUE.value,
            schemas.NotificationPriority.HIGH.value,
            0,
            "projects",
            "mongo-project-due-1",
            0,
            0,
        ),
    )
    sqlite_repo.sqlite_conn.commit()

    service = NotificationService(sqlite_repo, mock_event_bus)
    service.create_notification = types.MethodType(
        lambda self, **kwargs: pytest.fail(
            f"duplicate due-date notification created for stable ref {kwargs.get('related_entity_id')}"
        ),
        service,
    )

    service.check_project_due_dates()
