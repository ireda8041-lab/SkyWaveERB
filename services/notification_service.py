# الملف: services/notification_service.py

"""
خدمة الإشعارات
تدير إنشاء وعرض وحذف الإشعارات
"""

from datetime import datetime, timedelta

from PyQt6.QtWidgets import QApplication

from core.device_identity import get_stable_device_id
from core.error_handler import ErrorHandler
from core.event_bus import EventBus
from core.logger import get_logger
from core.repository import Repository
from core.schemas import Notification, NotificationPriority, NotificationType
from core.signals import app_signals

logger = get_logger(__name__)
error_handler = ErrorHandler()


class NotificationService:
    """
    خدمة إدارة الإشعارات
    - إنشاء إشعارات جديدة
    - الحصول على الإشعارات غير المقروءة
    - تحديد الإشعارات كمقروءة
    - حذف الإشعارات القديمة
    """

    def __init__(self, repository: Repository, event_bus: EventBus):
        """
        تهيئة خدمة الإشعارات

        Args:
            repository: مخزن البيانات
            event_bus: ناقل الأحداث
        """
        self.repo = repository
        self.event_bus = event_bus
        self._notification_columns_cache: set[str] | None = None

        # الاشتراك في الأحداث المهمة
        self._subscribe_to_events()

        logger.info("تم تهيئة NotificationService")

    def _subscribe_to_events(self):
        """⚡ الاشتراك في جميع الأحداث المهمة لإنشاء إشعارات تلقائية"""
        # إشعارات الدفعات
        self.event_bus.subscribe("PAYMENT_RECORDED", self._on_payment_recorded)

        # إشعارات المزامنة
        self.event_bus.subscribe("SYNC_FAILED", self._on_sync_failed)

        # ⚡ إشعارات جديدة - آخر 10 أحداث
        self.event_bus.subscribe("CLIENT_CREATED", self._on_client_created)
        self.event_bus.subscribe("PROJECT_CREATED", self._on_project_created)
        self.event_bus.subscribe("INVOICE_CREATED", self._on_invoice_created)
        self.event_bus.subscribe("EXPENSE_CREATED", self._on_expense_created)

        logger.debug("تم الاشتراك في أحداث الإشعارات")

    @staticmethod
    def _entity_reference(entity, *fields: str) -> str | None:
        for field in fields:
            value = getattr(entity, field, None)
            text = str(value or "").strip()
            if text:
                return text
        return None

    @classmethod
    def _stable_entity_reference(cls, entity, *fallback_fields: str) -> str | None:
        ordered_fields: list[str] = []
        for field in ("_mongo_id", *fallback_fields, "id"):
            if field and field not in ordered_fields:
                ordered_fields.append(field)
        return cls._entity_reference(entity, *ordered_fields)

    @staticmethod
    def _row_reference(row, *fields: str) -> str | None:
        for field in fields:
            value = None
            try:
                value = row[field]
            except Exception:
                value = getattr(row, field, None)
            text = str(value or "").strip()
            if text:
                return text
        return None

    def _notification_columns(self) -> set[str]:
        if self._notification_columns_cache is not None:
            return self._notification_columns_cache

        columns: set[str] = set()
        cursor = None
        try:
            cursor = self.repo.get_cursor()
            cursor.execute("PRAGMA table_info(notifications)")
            for row in cursor.fetchall() or []:
                try:
                    column_name = row["name"]
                except Exception:
                    try:
                        column_name = row[1]
                    except Exception:
                        column_name = None
                if column_name:
                    columns.add(str(column_name))
        except Exception:
            pass
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

        if not columns:
            columns = {
                "_mongo_id",
                "sync_status",
                "created_at",
                "last_modified",
                "title",
                "message",
                "type",
                "priority",
                "is_read",
                "related_entity_type",
                "related_entity_id",
                "action_url",
                "expires_at",
            }

        self._notification_columns_cache = columns
        return columns

    def _active_notification_where(self, *conditions: str) -> str:
        clauses = [condition for condition in conditions if condition]
        columns = self._notification_columns()
        if "sync_status" in columns:
            clauses.append("(sync_status != 'deleted' OR sync_status IS NULL)")
        if "is_deleted" in columns:
            clauses.append("(is_deleted = 0 OR is_deleted IS NULL)")
        return " AND ".join(clauses) if clauses else "1 = 1"

    def _repo_is_online(self) -> bool:
        return bool(getattr(self.repo, "online", False) and getattr(self.repo, "mongo_db", None))

    def _emit_notifications_changed(self) -> None:
        try:
            app_signals.emit_data_changed("notifications")
        except Exception as exc:
            logger.debug("تعذر بث إشارة تحديث الإشعارات: %s", exc)

    def _show_local_toast(self, notification: Notification) -> None:
        message = str(notification.message or "").strip()
        if not message:
            return
        if QApplication.instance() is None:
            return

        title = str(notification.title or "").strip() or None
        entity_type = str(notification.related_entity_type or "").strip() or None

        try:
            from ui.notification_system import NotificationManager
            from ui.notification_system import NotificationType as UiNotificationType

            if notification.type in {NotificationType.ERROR, NotificationType.SYNC_FAILED}:
                ui_notification_type = UiNotificationType.ERROR
            elif notification.type in {
                NotificationType.SUCCESS,
                NotificationType.PAYMENT_RECEIVED,
            }:
                ui_notification_type = UiNotificationType.SUCCESS
            elif notification.type in {
                NotificationType.WARNING,
                NotificationType.PROJECT_DUE,
            }:
                ui_notification_type = UiNotificationType.WARNING
            else:
                ui_notification_type = UiNotificationType.INFO

            NotificationManager.show(
                message,
                ui_notification_type,
                title=title,
                sync=False,
                entity_type=entity_type,
            )
        except Exception as exc:
            logger.debug("تعذر عرض toast محلي للإشعار %s: %s", title or message, exc)

    def _mark_local_rows_synced(self, cursor, notification_ids: list[int]) -> None:
        if not notification_ids:
            return

        columns = self._notification_columns()
        assignments: list[str] = []
        if "sync_status" in columns:
            assignments.append("sync_status = 'synced'")
        if "dirty_flag" in columns:
            assignments.append("dirty_flag = 0")

        if not assignments:
            return

        placeholders = ", ".join("?" for _ in notification_ids)
        cursor.execute(
            f"UPDATE notifications SET {', '.join(assignments)} WHERE id IN ({placeholders})",
            notification_ids,
        )

    @staticmethod
    def _mongo_primary_key(raw_id: str):
        if not raw_id:
            return None
        try:
            from bson import ObjectId

            return ObjectId(raw_id)
        except Exception:
            return raw_id

    def create_notification(
        self,
        title: str,
        message: str,
        type: NotificationType = NotificationType.INFO,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
        action_url: str | None = None,
        expires_at: datetime | None = None,
    ) -> Notification | None:
        """
        إنشاء إشعار جديد

        Args:
            title: عنوان الإشعار
            message: نص الإشعار
            type: نوع الإشعار
            priority: أولوية الإشعار
            related_entity_type: نوع الكيان المرتبط
            related_entity_id: معرف الكيان المرتبط
            action_url: رابط الإجراء
            expires_at: تاريخ انتهاء الصلاحية

        Returns:
            الإشعار المنشأ أو None في حالة الفشل
        """
        try:
            notification = Notification(
                title=title,
                message=message,
                type=type,
                priority=priority,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                action_url=action_url,
                expires_at=expires_at,
            )

            # حفظ في قاعدة البيانات
            saved_notification = self._save_notification(notification)

            if saved_notification:
                # إرسال حدث إنشاء إشعار جديد
                self.event_bus.publish(
                    "NOTIFICATION_CREATED",
                    {
                        "notification_id": saved_notification.id,
                        "type": type.value,
                        "priority": priority.value,
                    },
                )
                self._emit_notifications_changed()
                self._show_local_toast(saved_notification)

                logger.info("تم إنشاء إشعار: %s", title)
                return saved_notification

            return None

        except Exception as e:
            error_handler.handle_exception(e, f"فشل إنشاء الإشعار: {title}")
            return None

    def _save_notification(self, notification: Notification) -> Notification | None:
        """حفظ الإشعار في قاعدة البيانات - يستخدم cursor منفصل"""
        try:
            now = datetime.now().isoformat()
            now_dt = datetime.fromisoformat(now)
            columns = self._notification_columns()
            insert_data = {
                "sync_status": "new_offline",
                "created_at": now,
                "last_modified": now,
                "title": notification.title,
                "message": notification.message,
                "type": notification.type.value,
                "priority": notification.priority.value,
                "is_read": 0,
                "related_entity_type": notification.related_entity_type,
                "related_entity_id": notification.related_entity_id,
                "action_url": notification.action_url,
                "expires_at": (
                    notification.expires_at.isoformat() if notification.expires_at else None
                ),
            }
            if "dirty_flag" in columns:
                insert_data["dirty_flag"] = 1
            if "is_deleted" in columns:
                insert_data["is_deleted"] = 0

            # ⚡ استخدام cursor منفصل لتجنب Recursive cursor
            cursor = self.repo.get_cursor()
            try:
                notification.created_at = now_dt
                notification.last_modified = now_dt
                notification.sync_status = "new_offline"
                notification.is_read = False
                column_names = list(insert_data.keys())
                placeholders = ", ".join("?" for _ in column_names)
                cursor.execute(
                    f"INSERT INTO notifications ({', '.join(column_names)}) VALUES ({placeholders})",
                    [insert_data[name] for name in column_names],
                )

                self.repo.sqlite_conn.commit()
                notification.id = cursor.lastrowid

                # محاولة الحفظ في MongoDB
                if self._repo_is_online():
                    try:
                        notification_dict = notification.model_dump(exclude={"_mongo_id"})
                        notification_dict["device_id"] = get_stable_device_id()
                        notification_dict["sync_status"] = "synced"
                        notification_dict["is_deleted"] = False
                        if notification.related_entity_type and not notification_dict.get(
                            "entity_type"
                        ):
                            notification_dict["entity_type"] = notification.related_entity_type
                        result = self.repo.mongo_db.notifications.insert_one(notification_dict)

                        # تحديث _mongo_id
                        mongo_id = str(result.inserted_id)
                        update_assignments = ["_mongo_id = ?", "sync_status = 'synced'"]
                        update_params: list[object] = [mongo_id]
                        if "dirty_flag" in columns:
                            update_assignments.append("dirty_flag = 0")
                        cursor.execute(
                            f"UPDATE notifications SET {', '.join(update_assignments)} WHERE id = ?",
                            [*update_params, notification.id],
                        )
                        self.repo.sqlite_conn.commit()
                        notification._mongo_id = mongo_id
                        notification.sync_status = "synced"
                    except Exception as e:
                        logger.warning("فشل حفظ الإشعار في MongoDB: %s", e)
            finally:
                cursor.close()

            return notification

        except Exception as e:
            logger.error("فشل حفظ الإشعار: %s", e)
            return None

    def get_unread_notifications(self, limit: int = 50) -> list[Notification]:
        """
        الحصول على الإشعارات غير المقروءة
        ⚡ يستخدم cursor منفصل لتجنب Recursive cursor

        Args:
            limit: الحد الأقصى لعدد الإشعارات

        Returns:
            قائمة الإشعارات غير المقروءة
        """
        try:
            cursor = self.repo.get_cursor()
            try:
                where_sql = self._active_notification_where(
                    "is_read = 0",
                    "(expires_at IS NULL OR expires_at > ?)",
                )
                cursor.execute(
                    f"""
                    SELECT * FROM notifications
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (datetime.now().isoformat(), limit),
                )

                rows = cursor.fetchall()
            finally:
                cursor.close()

            notifications = []
            for row in rows:
                notification = self._row_to_notification(row)
                if notification:
                    notifications.append(notification)

            return notifications

        except Exception as e:
            logger.error("فشل الحصول على الإشعارات غير المقروءة: %s", e)
            return []

    def get_all_notifications(self, limit: int = 100) -> list[Notification]:
        """
        الحصول على جميع الإشعارات - يستخدم cursor منفصل

        Args:
            limit: الحد الأقصى لعدد الإشعارات

        Returns:
            قائمة جميع الإشعارات
        """
        try:
            cursor = self.repo.get_cursor()
            try:
                where_sql = self._active_notification_where(
                    "(expires_at IS NULL OR expires_at > ?)"
                )
                cursor.execute(
                    f"""
                    SELECT * FROM notifications
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (datetime.now().isoformat(), limit),
                )

                rows = cursor.fetchall()
            finally:
                cursor.close()

            notifications = []
            for row in rows:
                notification = self._row_to_notification(row)
                if notification:
                    notifications.append(notification)

            return notifications

        except Exception as e:
            logger.error("فشل الحصول على الإشعارات: %s", e)
            return []

    def get_recent_activities(self, limit: int = 10) -> list[Notification]:
        """
        ⚡ الحصول على آخر 10 أنشطة/أحداث في البرنامج - يستخدم cursor منفصل

        Args:
            limit: عدد الأنشطة (افتراضي 10)

        Returns:
            قائمة آخر الأنشطة
        """
        try:
            cursor = self.repo.get_cursor()
            try:
                where_sql = self._active_notification_where()
                cursor.execute(
                    f"""
                    SELECT * FROM notifications
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )

                rows = cursor.fetchall()
            finally:
                cursor.close()

            activities = []
            for row in rows:
                notification = self._row_to_notification(row)
                if notification:
                    activities.append(notification)

            logger.debug("تم جلب %s نشاط حديث", len(activities))
            return activities

        except Exception as e:
            logger.error("فشل الحصول على الأنشطة الحديثة: %s", e)
            return []

    def mark_as_read(self, notification_id: int) -> bool:
        """
        تحديد إشعار كمقروء - يستخدم cursor منفصل

        Args:
            notification_id: معرف الإشعار

        Returns:
            True إذا نجحت العملية
        """
        try:
            now_iso = datetime.now().isoformat()
            columns = self._notification_columns()
            cursor = self.repo.get_cursor()
            try:
                where_sql = self._active_notification_where("id = ?")
                cursor.execute(
                    f"SELECT id, _mongo_id FROM notifications WHERE {where_sql}",
                    (notification_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return False

                update_assignments = ["is_read = 1", "last_modified = ?"]
                update_params: list[object] = [now_iso]
                if "sync_status" in columns:
                    update_assignments.append("sync_status = ?")
                    update_params.append("modified_offline")
                if "dirty_flag" in columns:
                    update_assignments.append("dirty_flag = 1")

                cursor.execute(
                    f"""
                    UPDATE notifications
                    SET {', '.join(update_assignments)}
                    WHERE id = ?
                """,
                    [*update_params, notification_id],
                )

                self.repo.sqlite_conn.commit()

                # محاولة التحديث في MongoDB
                remote_synced = False
                mongo_id = str(row["_mongo_id"] or "").strip()
                if self._repo_is_online() and mongo_id:
                    try:
                        self.repo.mongo_db.notifications.update_one(
                            {"_id": self._mongo_primary_key(mongo_id)},
                            {
                                "$set": {
                                    "is_read": True,
                                    "last_modified": now_iso,
                                    "sync_status": "synced",
                                }
                            },
                        )
                        remote_synced = True
                    except Exception as e:
                        logger.warning("فشل تحديث الإشعار في MongoDB: %s", e)

                if remote_synced:
                    self._mark_local_rows_synced(cursor, [notification_id])
                    self.repo.sqlite_conn.commit()
            finally:
                cursor.close()

            self._emit_notifications_changed()
            logger.debug("تم تحديد الإشعار %s كمقروء", notification_id)
            return True

        except Exception as e:
            logger.error("فشل تحديد الإشعار كمقروء: %s", e)
            return False

    def mark_all_as_read(self) -> bool:
        """
        تحديد جميع الإشعارات كمقروءة - يستخدم cursor منفصل

        Returns:
            True إذا نجحت العملية
        """
        try:
            now_iso = datetime.now().isoformat()
            columns = self._notification_columns()
            cursor = self.repo.get_cursor()
            try:
                where_sql = self._active_notification_where("is_read = 0")
                cursor.execute(f"SELECT id, _mongo_id FROM notifications WHERE {where_sql}")
                rows = cursor.fetchall()
                notification_ids = [int(row["id"]) for row in rows]
                if not notification_ids:
                    return True

                update_assignments = ["is_read = 1", "last_modified = ?"]
                update_params: list[object] = [now_iso]
                if "sync_status" in columns:
                    update_assignments.append("sync_status = ?")
                    update_params.append("modified_offline")
                if "dirty_flag" in columns:
                    update_assignments.append("dirty_flag = 1")

                cursor.execute(
                    f"""
                    UPDATE notifications
                    SET {', '.join(update_assignments)}
                    WHERE {where_sql}
                """,
                    update_params,
                )

                self.repo.sqlite_conn.commit()

                synced_ids = [int(row["id"]) for row in rows if str(row["_mongo_id"] or "").strip()]
            finally:
                cursor.close()

            # محاولة التحديث في MongoDB
            if self._repo_is_online() and synced_ids:
                try:
                    self.repo.mongo_db.notifications.update_many(
                        {
                            "_id": {
                                "$in": [
                                    self._mongo_primary_key(str(row["_mongo_id"]))
                                    for row in rows
                                    if str(row["_mongo_id"] or "").strip()
                                ]
                            }
                        },
                        {
                            "$set": {
                                "is_read": True,
                                "last_modified": now_iso,
                                "sync_status": "synced",
                            }
                        },
                    )
                    cursor = self.repo.get_cursor()
                    try:
                        self._mark_local_rows_synced(cursor, synced_ids)
                        self.repo.sqlite_conn.commit()
                    finally:
                        cursor.close()
                except Exception as e:
                    logger.warning("فشل تحديث الإشعارات في MongoDB: %s", e)

            self._emit_notifications_changed()
            logger.info("تم تحديد جميع الإشعارات كمقروءة")
            return True

        except Exception as e:
            logger.error("فشل تحديد جميع الإشعارات كمقروءة: %s", e)
            return False

    def delete_notification(self, notification_id: int) -> bool:
        """
        حذف إشعار - يستخدم cursor منفصل

        Args:
            notification_id: معرف الإشعار

        Returns:
            True إذا نجحت العملية
        """
        try:
            now_iso = datetime.now().isoformat()
            columns = self._notification_columns()
            cursor = self.repo.get_cursor()
            try:
                where_sql = self._active_notification_where("id = ?")
                # الحصول على _mongo_id قبل الحذف
                cursor.execute(
                    f"SELECT id, _mongo_id FROM notifications WHERE {where_sql}",
                    (notification_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return False

                if "is_deleted" in columns or "dirty_flag" in columns:
                    delete_assignments = ["last_modified = ?"]
                    delete_params: list[object] = [now_iso]
                    if "sync_status" in columns:
                        delete_assignments.append("sync_status = ?")
                        delete_params.append("deleted")
                    if "is_deleted" in columns:
                        delete_assignments.append("is_deleted = 1")
                    if "dirty_flag" in columns:
                        delete_assignments.append("dirty_flag = 1")
                    cursor.execute(
                        f"UPDATE notifications SET {', '.join(delete_assignments)} WHERE id = ?",
                        [*delete_params, notification_id],
                    )
                else:
                    cursor.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
                self.repo.sqlite_conn.commit()
            finally:
                cursor.close()

            # محاولة الحذف من MongoDB
            mongo_id = str(row["_mongo_id"] or "").strip()
            remote_deleted = False
            if self._repo_is_online() and mongo_id:
                try:
                    self.repo.mongo_db.notifications.update_one(
                        {"_id": self._mongo_primary_key(mongo_id)},
                        {
                            "$set": {
                                "is_deleted": True,
                                "sync_status": "deleted",
                                "last_modified": now_iso,
                            }
                        },
                    )
                    remote_deleted = True
                except Exception as e:
                    logger.warning("فشل حذف الإشعار من MongoDB: %s", e)

            if remote_deleted and ("is_deleted" in columns or "dirty_flag" in columns):
                cursor = self.repo.get_cursor()
                try:
                    cursor.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
                    self.repo.sqlite_conn.commit()
                finally:
                    cursor.close()

            self._emit_notifications_changed()
            logger.debug("تم حذف الإشعار %s", notification_id)
            return True

        except Exception as e:
            logger.error("فشل حذف الإشعار: %s", e)
            return False

    def delete_old_notifications(self, days: int = 30) -> int:
        """
        حذف الإشعارات القديمة - يستخدم cursor منفصل

        Args:
            days: عدد الأيام (الإشعارات الأقدم من هذا سيتم حذفها)

        Returns:
            عدد الإشعارات المحذوفة
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            now_iso = datetime.now().isoformat()
            columns = self._notification_columns()

            cursor = self.repo.get_cursor()
            try:
                where_sql = self._active_notification_where("created_at < ?", "is_read = 1")
                cursor.execute(
                    f"SELECT id, _mongo_id FROM notifications WHERE {where_sql}",
                    (cutoff_date,),
                )
                rows = cursor.fetchall()
                deleted_count = len(rows)
                if deleted_count == 0:
                    return 0

                if "is_deleted" in columns or "dirty_flag" in columns:
                    delete_assignments = ["last_modified = ?"]
                    delete_params: list[object] = [now_iso]
                    if "sync_status" in columns:
                        delete_assignments.append("sync_status = ?")
                        delete_params.append("deleted")
                    if "is_deleted" in columns:
                        delete_assignments.append("is_deleted = 1")
                    if "dirty_flag" in columns:
                        delete_assignments.append("dirty_flag = 1")
                    cursor.execute(
                        f"UPDATE notifications SET {', '.join(delete_assignments)} WHERE {where_sql}",
                        [*delete_params, cutoff_date],
                    )
                else:
                    cursor.execute(
                        f"DELETE FROM notifications WHERE {where_sql}",
                        (cutoff_date,),
                    )
                self.repo.sqlite_conn.commit()
            finally:
                cursor.close()

            # محاولة الحذف من MongoDB
            if self._repo_is_online():
                try:
                    self.repo.mongo_db.notifications.update_many(
                        {
                            "created_at": {"$lt": cutoff_date},
                            "is_read": True,
                            "sync_status": {"$ne": "deleted"},
                        },
                        {
                            "$set": {
                                "is_deleted": True,
                                "sync_status": "deleted",
                                "last_modified": now_iso,
                            }
                        },
                    )
                except Exception as e:
                    logger.warning("فشل حذف الإشعارات القديمة من MongoDB: %s", e)

            self._emit_notifications_changed()
            logger.info("تم حذف %s إشعار قديم", deleted_count)
            return int(deleted_count)

        except Exception as e:
            logger.error("فشل حذف الإشعارات القديمة: %s", e)
            return 0

    def get_unread_count(self) -> int:
        """
        الحصول على عدد الإشعارات غير المقروءة
        ⚡ يستخدم cursor منفصل لتجنب Recursive cursor

        Returns:
            عدد الإشعارات غير المقروءة
        """
        try:
            cursor = self.repo.get_cursor()
            try:
                where_sql = self._active_notification_where(
                    "is_read = 0",
                    "(expires_at IS NULL OR expires_at > ?)",
                )
                cursor.execute(
                    f"""
                    SELECT COUNT(*) FROM notifications
                    WHERE {where_sql}
                """,
                    (datetime.now().isoformat(),),
                )
                result = cursor.fetchone()
            finally:
                cursor.close()
            return result[0] if result else 0

        except Exception as e:
            logger.error("فشل الحصول على عدد الإشعارات غير المقروءة: %s", e)
            return 0

    def _row_to_notification(self, row) -> Notification | None:
        """تحويل صف من قاعدة البيانات إلى كائن Notification"""
        try:
            return Notification(
                id=row["id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                last_modified=datetime.fromisoformat(row["last_modified"]),
                title=row["title"],
                message=row["message"],
                type=NotificationType(row["type"]),
                priority=NotificationPriority(row["priority"]),
                is_read=bool(row["is_read"]),
                related_entity_type=row["related_entity_type"],
                related_entity_id=row["related_entity_id"],
                action_url=row["action_url"],
                expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
                _mongo_id=row["_mongo_id"],
                sync_status=row["sync_status"],
            )
        except Exception as e:
            logger.error("فشل تحويل صف إلى Notification: %s", e)
            return None

    # --- معالجات الأحداث ---

    def _on_payment_recorded(self, data: dict):
        """معالج حدث تسجيل دفعة جديدة"""
        try:
            payment = data.get("payment")
            project = data.get("project")

            amount = float(
                getattr(payment, "amount", None)
                if payment is not None
                else data.get("amount", 0) or 0
            )
            project_name = (
                str(getattr(project, "name", "") or "").strip()
                if project is not None
                else str(data.get("project_name", "") or "").strip()
            )
            if not project_name and payment is not None:
                project_name = str(getattr(payment, "project_id", "") or "").strip()
            if not project_name:
                project_name = "غير معروف"
            payment_id = self._stable_entity_reference(payment) or data.get("payment_id", "")

            self.create_notification(
                title="تم تسجيل دفعة جديدة",
                message=f"تم تسجيل دفعة بمبلغ {amount:.2f} جنيه للمشروع '{project_name}'",
                type=NotificationType.SUCCESS,
                priority=NotificationPriority.MEDIUM,
                related_entity_type="payments",
                related_entity_id=str(payment_id or ""),
            )
        except Exception as e:
            logger.error("فشل إنشاء إشعار الدفعة: %s", e)

    def _on_sync_failed(self, data: dict):
        """معالج حدث فشل المزامنة"""
        try:
            error_message = data.get("error", "خطأ غير معروف")

            self.create_notification(
                title="فشلت عملية المزامنة",
                message=f"فشلت المزامنة مع السحابة: {error_message}",
                type=NotificationType.ERROR,
                priority=NotificationPriority.HIGH,
                related_entity_type="sync",
                related_entity_id=None,
            )
        except Exception as e:
            logger.error("فشل إنشاء إشعار فشل المزامنة: %s", e)

    # ⚡ معالجات الأحداث الجديدة - آخر 10 أحداث

    def _on_client_created(self, data: dict):
        """معالج حدث إنشاء عميل جديد"""
        try:
            client = data.get("client")
            if client:
                self.create_notification(
                    title="✅ عميل جديد",
                    message=f"تم إضافة العميل: {client.name}",
                    type=NotificationType.SUCCESS,
                    priority=NotificationPriority.LOW,
                    related_entity_type="client",
                    related_entity_id=self._stable_entity_reference(client),
                )
        except Exception as e:
            logger.error("فشل إنشاء إشعار العميل: %s", e)

    def _on_project_created(self, data: dict):
        """معالج حدث إنشاء مشروع جديد"""
        try:
            project = data.get("project")
            if project:
                self.create_notification(
                    title="🚀 مشروع جديد",
                    message=f"تم إنشاء المشروع: {project.name}",
                    type=NotificationType.SUCCESS,
                    priority=NotificationPriority.MEDIUM,
                    related_entity_type="project",
                    related_entity_id=self._stable_entity_reference(project, "name")
                    or str(getattr(project, "name", "") or "").strip()
                    or None,
                )
        except Exception as e:
            logger.error("فشل إنشاء إشعار المشروع: %s", e)

    def _on_invoice_created(self, data: dict):
        """معالج حدث إنشاء فاتورة جديدة"""
        try:
            invoice = data.get("invoice")
            if invoice:
                self.create_notification(
                    title="📄 فاتورة جديدة",
                    message=f"تم إنشاء الفاتورة: {invoice.invoice_number}",
                    type=NotificationType.INFO,
                    priority=NotificationPriority.MEDIUM,
                    related_entity_type="invoice",
                    related_entity_id=invoice.invoice_number,
                )
        except Exception as e:
            logger.error("فشل إنشاء إشعار الفاتورة: %s", e)

    def _on_expense_created(self, data: dict):
        """معالج حدث إنشاء مصروف جديد"""
        try:
            expense = data.get("expense")
            if expense:
                self.create_notification(
                    title="💸 مصروف جديد",
                    message=f"تم تسجيل مصروف: {expense.category} - {expense.amount} ج.م",
                    type=NotificationType.WARNING,
                    priority=NotificationPriority.LOW,
                    related_entity_type="expense",
                    related_entity_id=self._stable_entity_reference(expense),
                )
        except Exception as e:
            logger.error("فشل إنشاء إشعار المصروف: %s", e)

    def check_project_due_dates(self):
        """
        فحص مواعيد استحقاق المشاريع وإنشاء إشعارات - يستخدم cursor منفصل
        يجب استدعاء هذه الدالة بشكل دوري (مثلاً يومياً)
        """
        try:
            # الحصول على المشاريع النشطة
            cursor = self.repo.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT id, _mongo_id, name, end_date
                    FROM projects
                    WHERE status = 'نشط' AND end_date IS NOT NULL
                """
                )

                rows = cursor.fetchall()
                now = datetime.now()

                projects_to_notify = []
                for row in rows:
                    end_date = datetime.fromisoformat(row["end_date"])
                    days_until_due = (end_date - now).days
                    project_ref = self._row_reference(row, "_mongo_id", "id")
                    if not project_ref:
                        continue

                    # إشعار قبل 7 أيام من الموعد
                    if 0 <= days_until_due <= 7:
                        # التحقق من عدم وجود إشعار مسبق
                        cursor.execute(
                            """
                            SELECT COUNT(*) FROM notifications
                            WHERE related_entity_type = 'projects'
                            AND related_entity_id = ?
                            AND type = ?
                            AND created_at > ?
                        """,
                            (
                                project_ref,
                                NotificationType.PROJECT_DUE.value,
                                (now - timedelta(days=1)).isoformat(),
                            ),
                        )

                        if cursor.fetchone()[0] == 0:
                            projects_to_notify.append(
                                {
                                    "id": row["id"],
                                    "ref": project_ref,
                                    "name": row["name"],
                                    "days": days_until_due,
                                }
                            )
            finally:
                cursor.close()

            # إنشاء الإشعارات خارج الـ cursor
            for project in projects_to_notify:
                self.create_notification(
                    title="موعد استحقاق مشروع قريب",
                    message=f"المشروع '{project['name']}' سينتهي خلال {project['days']} يوم",
                    type=NotificationType.PROJECT_DUE,
                    priority=NotificationPriority.HIGH,
                    related_entity_type="projects",
                    related_entity_id=str(project["ref"]),
                )

            logger.debug("تم فحص مواعيد استحقاق المشاريع")

        except Exception as e:
            logger.error("فشل فحص مواعيد استحقاق المشاريع: %s", e)
