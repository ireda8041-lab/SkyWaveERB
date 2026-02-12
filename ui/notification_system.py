# pylint: disable=too-many-positional-arguments
# الملف: ui/notification_system.py
"""
نظام الإشعارات العام للبرنامج
- إشعارات Toast تظهر في زاوية الشاشة
- مزامنة الإشعارات بين الأجهزة عبر MongoDB
"""

import hashlib
import json
import os
import platform
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QObject, QPropertyAnimation, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.styles import COLORS

try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class NotificationType(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


def _get_stable_device_id() -> str:
    """إنشاء معرف ثابت للجهاز"""
    try:
        machine_info = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
        try:
            digest = hashlib.md5(machine_info.encode(), usedforsecurity=False).hexdigest()
        except TypeError:
            digest = hashlib.sha256(machine_info.encode()).hexdigest()
        device_hash = digest[:8]
        return device_hash
    except Exception:

        device_file = os.path.join(os.path.expanduser("~"), ".skywave_device_id")
        if os.path.exists(device_file):
            with open(device_file, encoding="utf-8") as f:
                return f.read().strip()
        else:
            new_id = str(uuid.uuid4())[:8]
            try:
                with open(device_file, "w", encoding="utf-8") as f:
                    f.write(new_id)
            except OSError:
                # فشل حفظ Device ID
                pass
            return new_id


DEVICE_ID = _get_stable_device_id()
safe_print(f"INFO: [NotificationSystem] Device ID: {DEVICE_ID}")


class ToastNotification(QWidget):
    """إشعار Toast منبثق - تصميم عصري وجميل"""

    closed = pyqtSignal()

    def __init__(
        self,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        title: str = None,
        duration: int = 4000,
        source_device: str = None,
        parent=None,
    ):
        super().__init__(parent)
        self.message = message
        self.notification_type = notification_type
        self.title = title
        self.duration = duration
        self.source_device = source_device

        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(340)

        # ألوان وأيقونات محسنة
        colors = {
            NotificationType.SUCCESS: ("#10b981", "#065f46", "✓"),
            NotificationType.ERROR: ("#ef4444", "#7f1d1d", "✕"),
            NotificationType.WARNING: ("#f59e0b", "#78350f", "⚠"),
            NotificationType.INFO: ("#3b82f6", "#1e3a8a", "ℹ"),
        }
        accent, dark_accent, icon = colors.get(self.notification_type, ("#6b7280", "#374151", "🔔"))

        # الحاوية الرئيسية
        container = QWidget()
        container.setObjectName("notif_container")
        container.setStyleSheet(
            f"""
            QWidget#notif_container {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['bg_dark']}, stop:1 {COLORS['bg_medium']});
                border: 1px solid {accent}50;
                border-radius: 12px;
            }}
        """
        )

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(0)

        # شريط اللون الجانبي
        color_bar = QWidget()
        color_bar.setFixedWidth(5)
        color_bar.setStyleSheet(
            f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {accent}, stop:1 {dark_accent});
            border-radius: 12px 0 0 12px;
        """
        )
        layout.addWidget(color_bar)

        # منطقة المحتوى
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(14, 12, 10, 12)
        content_layout.setSpacing(12)

        # أيقونة دائرية
        icon_container = QWidget()
        icon_container.setFixedSize(40, 40)
        icon_container.setStyleSheet(
            f"""
            background: {accent}25;
            border-radius: 20px;
        """
        )
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            f"""
            font-size: 18px;
            color: {accent};
            background: transparent;
            font-weight: bold;
        """
        )
        icon_layout.addWidget(icon_label)
        content_layout.addWidget(icon_container)

        # النص
        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        text_layout.setContentsMargins(0, 0, 0, 0)

        if self.title:
            title_text = self.title
            if self.source_device and self.source_device != DEVICE_ID:
                title_text += " 🌐"
            title_label = QLabel(title_text)
            title_label.setStyleSheet(
                f"""
                color: {COLORS['text_primary']};
                font-size: 13px;
                font-weight: bold;
                font-family: 'Cairo';
                background: transparent;
            """
            )
            text_layout.addWidget(title_label)

        msg_label = QLabel(self.message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(
            f"""
            color: {COLORS['text_secondary']};
            font-size: 11px;
            font-family: 'Cairo';
            background: transparent;
        """
        )
        text_layout.addWidget(msg_label)

        content_layout.addLayout(text_layout, 1)

        # زر الإغلاق
        close_btn = QPushButton("×")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: none;
                font-size: 20px;
                font-weight: bold;
                border-radius: 13px;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_light']}50;
                color: {COLORS['text_primary']};
            }}
        """
        )
        close_btn.clicked.connect(self.close_notification)
        content_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addLayout(content_layout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(container)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)

    def _setup_animation(self):
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(200)
        self.fade_in.setStartValue(0)
        self.fade_in.setEndValue(1)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(250)
        self.fade_out.setStartValue(1)
        self.fade_out.setEndValue(0)
        self.fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_out.finished.connect(self._on_fade_out_finished)

        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.close_notification)

    def show_notification(self):
        self.show()
        self.fade_in.start()
        if self.duration > 0:
            self.close_timer.start(self.duration)

    def close_notification(self):
        self.close_timer.stop()
        self.fade_out.start()

    def _on_fade_out_finished(self):
        self.closed.emit()
        self.deleteLater()

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        self.close_notification()


class NotificationSyncWorker(QThread):
    """عامل مزامنة الإشعارات من MongoDB - محسّن للاستقرار"""

    new_notification = pyqtSignal(dict)
    _ENTITY_TABLE_MAP = {
        "client": "clients",
        "clients": "clients",
        "project": "projects",
        "projects": "projects",
        "service": "services",
        "services": "services",
        "payment": "payments",
        "payments": "payments",
        "expense": "expenses",
        "expenses": "expenses",
        "account": "accounts",
        "accounts": "accounts",
        "invoice": "invoices",
        "invoices": "invoices",
        "task": "tasks",
        "tasks": "tasks",
        "notification": "notifications",
        "notifications": "notifications",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = True
        self.repo = None
        self._seen_ids = set()
        self._seen_order = deque()
        self._max_seen_ids = 1200
        # Poll below 1s for fast cross-device fallback when Change Streams are unavailable.
        self._check_interval = 700
        self._poll_lookback_seconds = 3600
        self._last_cleanup = 0.0
        self._last_sync_trigger = 0.0
        self._sync_trigger_cooldown = 0.4
        self._last_settings_sync = 0.0
        self._settings_sync_interval = 20.0
        self._settings_sync_cooldown = 1.0
        self._load_runtime_config()

    def _load_runtime_config(self):
        try:
            config_path = Path("sync_config.json")
            if not config_path.exists():
                return
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            poll_ms = cfg.get("notification_poll_interval_ms")
            lookback_s = cfg.get("notification_poll_lookback_seconds")
            if poll_ms is not None:
                self._check_interval = max(300, min(5000, int(poll_ms)))
            if lookback_s is not None:
                self._poll_lookback_seconds = max(60, min(24 * 3600, int(lookback_s)))
        except Exception:
            # Keep safe defaults.
            pass

    def _mark_seen(self, notif_id: str) -> None:
        if not notif_id or notif_id in self._seen_ids:
            return
        self._seen_ids.add(notif_id)
        self._seen_order.append(notif_id)
        while len(self._seen_order) > self._max_seen_ids:
            old_id = self._seen_order.popleft()
            self._seen_ids.discard(old_id)

    def set_repository(self, repo):
        self.repo = repo
        safe_print(
            f"INFO: [NotificationSync] Repository set, online={getattr(repo, 'online', False)}"
        )

    def run(self):
        safe_print(f"INFO: [NotificationSync] Worker started for device {DEVICE_ID}")
        while self.is_running:
            try:
                if (
                    self.repo is not None
                    and getattr(self.repo, "online", False)
                    and getattr(self.repo, "mongo_db", None) is not None
                ):
                    self._check_new_notifications()
            except Exception as e:
                safe_print(f"WARNING: [NotificationSync] {e}")

            self.msleep(self._check_interval)

    def _check_new_notifications(self):
        try:
            if self.repo is None or self.repo.mongo_db is None:
                return

            collection = self.repo.mongo_db.notifications

            check_dt = datetime.now() - timedelta(seconds=self._poll_lookback_seconds)
            check_iso = check_dt.isoformat()

            try:
                query = {
                    "$and": [
                        {
                            "$or": [
                                {"created_at": {"$gt": check_iso}},
                                {"created_at": {"$gt": check_dt}},
                            ]
                        },
                        {
                            "$or": [
                                {"device_id": {"$exists": False}},
                                {"device_id": {"$ne": DEVICE_ID}},
                            ]
                        },
                    ]
                }
                notifications = list(collection.find(query).sort("created_at", -1).limit(30))
            except Exception as e:
                try:
                    # Fallback: ignore device filter if server rejects complex query.
                    notifications = list(
                        collection.find(
                            {
                                "$or": [
                                    {"created_at": {"$gt": check_iso}},
                                    {"created_at": {"$gt": check_dt}},
                                ]
                            }
                        )
                        .sort("created_at", -1)
                        .limit(30)
                    )
                except Exception as fallback_error:
                    safe_print(
                        f"ERROR: [NotificationSync] MongoDB query failed: {e} | {fallback_error}"
                    )
                    return

            # Main query path with explicit device filter (split to keep Mongo query syntax valid).
            try:
                notifications = [
                    n
                    for n in notifications
                    if n.get("device_id") is None or n.get("device_id") != DEVICE_ID
                ]
            except Exception:
                pass

            trigger_tables: set[str] = set()
            saw_new = False
            settings_triggered = False

            for notif in notifications:
                try:
                    notif_id = str(notif.get("_id", ""))
                    if notif_id in self._seen_ids:
                        continue

                    self._mark_seen(notif_id)
                    saw_new = True

                    safe_print(
                        f"INFO: [NotificationSync] Received from {notif.get('device_id')}: {notif.get('title')}"
                    )

                    entity_type = notif.get("entity_type")
                    entity_key = str(entity_type).strip().lower() if entity_type else ""
                    action_value = str(notif.get("action") or "").strip().lower()
                    title_text = str(notif.get("title") or "").strip()
                    message_text = str(notif.get("message") or "").strip()
                    silent = bool(notif.get("silent")) or action_value == "sync_ping"
                    if entity_key in {"system_settings", "settings"}:
                        # system_settings notifications are operational signals, not user toasts.
                        silent = True
                    elif (
                        "تم تحديث إعدادات النظام" in message_text
                        or "system settings" in message_text.lower()
                        or title_text in {"⚙️ الإعدادات", "الاعدادات"}
                        or title_text.lower() in {"settings", "system settings"}
                    ):
                        # Backward-compat: older app versions may send settings notifications
                        # without entity_type. Keep them silent to avoid noisy startup toasts.
                        silent = True
                        settings_triggered = True
                    if not silent:
                        self.new_notification.emit(
                            {
                                "message": message_text,
                                "type": notif.get("type", "info"),
                                "title": title_text,
                                "device_id": notif.get("device_id"),
                                "entity_type": entity_type,
                                "action": notif.get("action"),
                            }
                        )

                    if entity_key in {"system_settings", "settings"}:
                        settings_triggered = True
                    table_name = self._map_entity_to_table(entity_type)
                    if table_name:
                        trigger_tables.add(table_name)
                except Exception as e:
                    safe_print(f"ERROR: [NotificationSync] فشل معالجة إشعار واحد: {e}")
                    continue  # تجاهل الإشعار المعطوب والمتابعة

            if saw_new:
                self._trigger_instant_sync(trigger_tables)

            if (
                settings_triggered
                or (time.time() - self._last_settings_sync) > self._settings_sync_interval
            ):
                self._trigger_settings_sync()

            # تنظيف الإشعارات القديمة (مع معالجة الأخطاء)

            if not hasattr(self, "_last_cleanup") or time.time() - self._last_cleanup > 60:
                try:
                    old_dt = datetime.now() - timedelta(hours=1)
                    old_time = old_dt.isoformat()
                    result = collection.delete_many(
                        {
                            "$or": [
                                {"created_at": {"$lt": old_time}},
                                {"created_at": {"$lt": old_dt}},
                            ]
                        }
                    )
                    if result.deleted_count > 0:
                        safe_print(
                            f"INFO: [NotificationSync] تم حذف {result.deleted_count} إشعار قديم"
                        )
                except Exception as e:
                    safe_print(f"WARNING: [NotificationSync] فشل تنظيف الإشعارات القديمة: {e}")
                self._last_cleanup = time.time()

        except Exception as e:
            safe_print(f"ERROR: [NotificationSync] Check failed: {e}")
            # لا نوقف الـ worker، فقط نسجل الخطأ ونتابع

    def stop(self):
        """إيقاف آمن للـ worker"""
        self.is_running = False
        try:
            self.quit()
            if not self.wait(500):  # انتظر نصف ثانية فقط
                self.terminate()  # إجبار الإيقاف إذا لم يستجب
        except RuntimeError:
            # Qt object already deleted
            pass

    @classmethod
    def _map_entity_to_table(cls, entity_type: str | None) -> str | None:
        if not entity_type:
            return None
        return cls._ENTITY_TABLE_MAP.get(str(entity_type).strip().lower())

    def _trigger_settings_sync(self):
        repo = self.repo
        if repo is None or not getattr(repo, "online", False):
            return
        settings_service = getattr(repo, "settings_service", None)
        if settings_service is None:
            return
        now = time.time()
        if (now - self._last_settings_sync) < self._settings_sync_cooldown:
            return
        self._last_settings_sync = now

        def worker():
            try:
                settings_service.sync_settings_from_cloud(repo)
            except Exception as e:
                safe_print(f"WARNING: [NotificationSync] Settings sync failed: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _trigger_instant_sync(self, tables: set[str]):
        repo = self.repo
        if repo is None or not hasattr(repo, "unified_sync"):
            return
        syncer = getattr(repo, "unified_sync", None)
        if syncer is None:
            return
        now = time.time()
        if (now - self._last_sync_trigger) < self._sync_trigger_cooldown:
            return
        self._last_sync_trigger = now

        table = None
        if len(tables) == 1:
            table = next(iter(tables))
        # For single-table remote events, prefer targeted pull to avoid watermark drift issues.
        if table and hasattr(syncer, "force_pull"):
            syncer.force_pull(table)
            return
        if hasattr(syncer, "schedule_instant_sync"):
            syncer.schedule_instant_sync(table)
        else:
            syncer.instant_sync(table)


class NotificationManager(QObject):
    """مدير الإشعارات - Singleton"""

    _instance = None
    _notifications: list = []
    _max_visible = 4
    _spacing = 10
    _margin = 20
    _repo = None
    _sync_worker = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        self._notifications = []

        self._sync_worker = NotificationSyncWorker()
        self._sync_worker.new_notification.connect(self._on_remote_notification)
        self._sync_worker.start()

    @classmethod
    def set_repository(cls, repo):
        manager = cls()
        manager._repo = repo
        if manager._sync_worker:
            manager._sync_worker.set_repository(repo)

    @classmethod
    def _on_remote_notification(cls, data: dict):
        manager = cls()

        type_map = {
            "success": NotificationType.SUCCESS,
            "error": NotificationType.ERROR,
            "warning": NotificationType.WARNING,
            "info": NotificationType.INFO,
        }

        notification = ToastNotification(
            message=data.get("message", ""),
            notification_type=type_map.get(data.get("type"), NotificationType.INFO),
            title=data.get("title"),
            duration=5000,
            source_device=data.get("device_id"),
        )
        notification.closed.connect(lambda: manager._on_notification_closed(notification))

        manager._notifications.append(notification)

        while len(manager._notifications) > manager._max_visible:
            old = manager._notifications.pop(0)
            old.close_notification()

        manager._update_positions()
        notification.show_notification()

    @classmethod
    def show(
        cls,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        title: str = None,
        duration: int = 4000,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        manager = cls()

        notification = ToastNotification(
            message=message,
            notification_type=notification_type,
            title=title,
            duration=duration,
            source_device=DEVICE_ID,
        )
        notification.closed.connect(lambda: manager._on_notification_closed(notification))

        manager._notifications.append(notification)

        while len(manager._notifications) > manager._max_visible:
            old = manager._notifications.pop(0)
            old.close_notification()

        manager._update_positions()
        notification.show_notification()

        if sync and manager._repo is not None and manager._repo.online:
            try:
                manager._repo.mongo_db.notifications.insert_one(
                    {
                        "message": message,
                        "type": notification_type.value,
                        "title": title,
                        "device_id": DEVICE_ID,
                        "created_at": datetime.now().isoformat(),
                        "entity_type": entity_type,
                        "action": action,
                    }
                )
            except Exception as e:
                safe_print(f"ERROR: [NotificationManager] Sync failed: {e}")

    @classmethod
    def success(
        cls,
        message: str,
        title: str = None,
        duration: int = 4000,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        cls.show(message, NotificationType.SUCCESS, title, duration, sync, entity_type, action)

    @classmethod
    def error(
        cls,
        message: str,
        title: str = None,
        duration: int = 5000,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        cls.show(message, NotificationType.ERROR, title, duration, sync, entity_type, action)

    @classmethod
    def warning(
        cls,
        message: str,
        title: str = None,
        duration: int = 4500,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        cls.show(message, NotificationType.WARNING, title, duration, sync, entity_type, action)

    @classmethod
    def info(
        cls,
        message: str,
        title: str = None,
        duration: int = 4000,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        cls.show(message, NotificationType.INFO, title, duration, sync, entity_type, action)

    def _on_notification_closed(self, notification):
        if notification in self._notifications:
            self._notifications.remove(notification)
        self._update_positions()

    def _update_positions(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return

        screen_geo = screen.availableGeometry()
        y = screen_geo.bottom() - self._margin

        for notification in reversed(self._notifications):
            notification.adjustSize()
            height = notification.height()
            y -= height

            x = screen_geo.right() - notification.width() - self._margin
            notification.move(x, y)

            y -= self._spacing

    @classmethod
    def shutdown(cls):
        manager = cls()
        if manager._sync_worker:
            manager._sync_worker.stop()


def notify_success(
    message: str,
    title: str = None,
    sync: bool = True,
    entity_type: str | None = None,
    action: str | None = None,
):
    NotificationManager.success(message, title, sync=sync, entity_type=entity_type, action=action)


def notify_error(
    message: str,
    title: str = None,
    sync: bool = True,
    entity_type: str | None = None,
    action: str | None = None,
):
    NotificationManager.error(message, title, sync=sync, entity_type=entity_type, action=action)


def notify_warning(
    message: str,
    title: str = None,
    sync: bool = True,
    entity_type: str | None = None,
    action: str | None = None,
):
    NotificationManager.warning(message, title, sync=sync, entity_type=entity_type, action=action)


def notify_info(
    message: str,
    title: str = None,
    sync: bool = True,
    entity_type: str | None = None,
    action: str | None = None,
):
    NotificationManager.info(message, title, sync=sync, entity_type=entity_type, action=action)
