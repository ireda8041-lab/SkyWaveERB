# pylint: disable=too-many-positional-arguments
# الملف: ui/notification_system.py
"""
نظام الإشعارات العام للبرنامج
- إشعارات Toast تظهر في زاوية الشاشة
- مزامنة الإشعارات بين الأجهزة عبر MongoDB
"""

import json
import queue
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.device_identity import get_stable_device_id
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


DEVICE_ID = get_stable_device_id()
safe_print(f"INFO: [NotificationSystem] Device ID: {DEVICE_ID}")


class ToastNotification(QWidget):
    """إشعار Toast منبثق - تصميم عصري وجميل"""

    closed = pyqtSignal()

    def __init__(
        self,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        title: str = None,
        duration: int = 12000,
        source_device: str = None,
        parent=None,
    ):
        super().__init__(parent)
        self.message = message
        self.notification_type = notification_type
        self.title = title
        try:
            normalized_duration = int(duration)
        except (TypeError, ValueError):
            normalized_duration = 6500

        # 0 = لا يغلق تلقائياً. أي قيمة موجبة صغيرة جدًا تتحول لحد أدنى مقروء.
        if normalized_duration == 0:
            self.duration = 0
        else:
            self.duration = max(9000, normalized_duration)
        self.source_device = source_device
        self._remaining_duration_ms = self.duration
        self._is_closing = False
        self._move_animation = None
        self._progress_animation = None
        self._shown_at_mono = 0.0
        self._min_visible_before_timer_close_ms = 1200
        self._restoring_visibility = False
        self._last_restore_attempt_mono = 0.0
        self._logged_external_close_once = False
        self._logged_external_hide_once = False

        self._setup_ui()
        self._setup_animation()

    def _theme(self) -> dict:
        themes = {
            NotificationType.SUCCESS: {
                "accent": "#22c55e",
                "accent_dark": "#166534",
                "icon": "✓",
                "title_fallback": "تمت العملية",
            },
            NotificationType.ERROR: {
                "accent": "#ef4444",
                "accent_dark": "#991b1b",
                "icon": "✕",
                "title_fallback": "خطأ",
            },
            NotificationType.WARNING: {
                "accent": "#f59e0b",
                "accent_dark": "#92400e",
                "icon": "!",
                "title_fallback": "تنبيه",
            },
            NotificationType.INFO: {
                "accent": "#3b82f6",
                "accent_dark": "#1d4ed8",
                "icon": "i",
                "title_fallback": "معلومة",
            },
        }
        return themes.get(self.notification_type, themes[NotificationType.INFO])

    def _setup_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setFixedWidth(380)

        theme = self._theme()
        accent = theme["accent"]
        accent_dark = theme["accent_dark"]

        self._container = QWidget()
        self._container.setObjectName("notif_container")
        self._container.setStyleSheet(
            f"""
            QWidget#notif_container {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {COLORS['bg_medium']}, stop:1 {COLORS['bg_dark']});
                border: 1px solid {accent}88;
                border-radius: 14px;
            }}
        """
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 170))
        self._container.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._container)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 10, 0)
        body_layout.setSpacing(0)

        color_bar = QWidget()
        color_bar.setFixedWidth(6)
        color_bar.setStyleSheet(
            f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {accent}, stop:1 {accent_dark});
            border-radius: 14px 0 0 14px;
        """
        )
        body_layout.addWidget(color_bar)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(12, 10, 10, 8)
        content_layout.setSpacing(10)

        icon_container = QWidget()
        icon_container.setFixedSize(36, 36)
        icon_container.setStyleSheet(
            f"""
            background: {accent}2B;
            border: 1px solid {accent}66;
            border-radius: 18px;
        """
        )
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(theme["icon"])
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            f"""
            color: {accent};
            background: transparent;
            font-size: 16px;
            font-weight: 700;
            font-family: 'Cairo';
        """
        )
        icon_layout.addWidget(icon_label)
        content_layout.addWidget(icon_container)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_text = (self.title or theme["title_fallback"]).strip()
        if self.source_device and self.source_device != DEVICE_ID:
            title_text += " (جهاز آخر)"

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title_label = QLabel(title_text)
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        title_label.setStyleSheet(
            f"""
            color: {COLORS['text_primary']};
            background: transparent;
            font-size: 12px;
            font-weight: 700;
            font-family: 'Cairo';
        """
        )
        header_row.addWidget(title_label, 1)

        time_label = QLabel(datetime.now().strftime("%H:%M"))
        time_label.setStyleSheet(
            f"""
            color: {COLORS['text_secondary']};
            background: transparent;
            font-size: 10px;
            font-family: 'Cairo';
        """
        )
        header_row.addWidget(time_label, alignment=Qt.AlignmentFlag.AlignLeft)
        text_layout.addLayout(header_row)

        msg_label = QLabel((self.message or "").strip())
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        msg_label.setStyleSheet(
            f"""
            color: {COLORS['text_secondary']};
            background: transparent;
            font-size: 11px;
            font-family: 'Cairo';
        """
        )
        text_layout.addWidget(msg_label)
        content_layout.addLayout(text_layout, 1)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: none;
                border-radius: 12px;
                font-size: 18px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_light']}88;
                color: {COLORS['text_primary']};
            }}
        """
        )
        close_btn.clicked.connect(lambda: self._request_close("button"))
        content_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)

        body_layout.addLayout(content_layout, 1)
        card_layout.addLayout(body_layout)

        self._progress_track = QWidget()
        self._progress_track.setFixedHeight(3)
        self._progress_track.setStyleSheet(
            f"""
            background: {accent}1F;
            border-radius: 2px;
        """
        )
        self._progress_fill = QWidget(self._progress_track)
        self._progress_fill.setStyleSheet(
            f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {accent}, stop:1 {accent_dark});
            border-radius: 2px;
        """
        )
        card_layout.addWidget(self._progress_track)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.addWidget(self._container)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)

    def _setup_animation(self):
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(220)
        self.fade_in.setStartValue(0)
        self.fade_in.setEndValue(1)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.slide_in = QPropertyAnimation(self, b"pos")
        self.slide_in.setDuration(220)
        self.slide_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(180)
        self.fade_out.setStartValue(1)
        self.fade_out.setEndValue(0)
        self.fade_out.setEasingCurve(QEasingCurve.Type.InQuad)
        self.fade_out.finished.connect(self._on_fade_out_finished)

        self.slide_out = QPropertyAnimation(self, b"pos")
        self.slide_out.setDuration(180)
        self.slide_out.setEasingCurve(QEasingCurve.Type.InQuad)

        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(lambda: self._request_close("timer"))

    def show_notification(self):
        if self._is_closing:
            return
        self._last_restore_attempt_mono = 0.0
        self.show()
        self._shown_at_mono = time.monotonic()
        self._raise_safely()
        target_pos = QPoint(self.pos())
        start_pos = QPoint(target_pos.x() + 28, target_pos.y())
        self.move(start_pos)
        self.opacity_effect.setOpacity(0)

        self.slide_in.stop()
        self.slide_in.setStartValue(start_pos)
        self.slide_in.setEndValue(target_pos)
        self.slide_in.start()

        self.fade_in.stop()
        self.fade_in.start()
        if self.duration > 0:
            self._remaining_duration_ms = self.duration
            self.close_timer.start(self.duration)
            # نؤجل بدء الأنيميشن لحين اكتمال layout لتفادي عرض = 0.
            QTimer.singleShot(0, lambda d=self.duration: self._start_progress_animation(d))
        else:
            self._progress_track.hide()
        # Keep toast visible across dialog close/focus transitions.
        QTimer.singleShot(120, self._raise_safely)

    def _raise_safely(self):
        if self._is_closing or not self.isVisible():
            return
        try:
            self.raise_()
        except RuntimeError:
            return

    def _request_close(self, reason: str = "manual"):
        if self._is_closing:
            return
        if reason == "timer" and self.duration > 0 and self._shown_at_mono > 0:
            elapsed_ms = int((time.monotonic() - self._shown_at_mono) * 1000)
            if elapsed_ms < self._min_visible_before_timer_close_ms:
                remaining = self._min_visible_before_timer_close_ms - elapsed_ms
                self.close_timer.start(max(250, remaining))
                return
        if reason == "timer" and self._shown_at_mono > 0:
            elapsed_ms = int((time.monotonic() - self._shown_at_mono) * 1000)
            if elapsed_ms < 5000:
                safe_print(
                    f"WARNING: [NotificationSystem] Timer-close very early ({elapsed_ms}ms) for title={self.title!r}"
                )
        self.close_notification(reason=reason)

    def close_notification(self, reason: str = "manual"):
        if self._is_closing:
            return
        self._is_closing = True
        self.close_timer.stop()
        if self._progress_animation:
            self._progress_animation.stop()

        current_pos = QPoint(self.pos())
        out_pos = QPoint(current_pos.x() + 18, current_pos.y())
        self.slide_out.stop()
        self.slide_out.setStartValue(current_pos)
        self.slide_out.setEndValue(out_pos)
        self.slide_out.start()

        self.fade_out.stop()
        self.fade_out.start()

    def _restore_visibility(self):
        if self._is_closing:
            return
        if self._restoring_visibility:
            return
        self._restoring_visibility = True
        try:
            if not self.isVisible():
                self.show()
            self._raise_safely()
            if (
                self.duration > 0
                and self._remaining_duration_ms > 0
                and not self.close_timer.isActive()
                and not self.underMouse()
            ):
                self.close_timer.start(self._remaining_duration_ms)
                if (
                    self._progress_animation
                    and self._progress_animation.state() == QPropertyAnimation.State.Paused
                ):
                    self._progress_animation.resume()
        except RuntimeError:
            return
        finally:
            self._restoring_visibility = False

    def _on_fade_out_finished(self):
        self.closed.emit()
        self.deleteLater()

    def _start_progress_animation(self, duration_ms: int) -> None:
        if duration_ms <= 0:
            return
        track_rect = self._progress_track.contentsRect()
        if track_rect.width() <= 0:
            QTimer.singleShot(16, lambda d=duration_ms: self._start_progress_animation(d))
            return

        start_rect = QRect(0, 0, track_rect.width(), track_rect.height())
        end_rect = QRect(track_rect.width(), 0, 0, track_rect.height())
        self._progress_fill.setGeometry(start_rect)

        if self._progress_animation:
            self._progress_animation.stop()

        self._progress_animation = QPropertyAnimation(self._progress_fill, b"geometry", self)
        self._progress_animation.setDuration(duration_ms)
        self._progress_animation.setStartValue(start_rect)
        self._progress_animation.setEndValue(end_rect)
        self._progress_animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._progress_animation.start()

    def animate_move_to(self, x: int, y: int) -> None:
        target = QPoint(int(x), int(y))
        if not self.isVisible() or self._is_closing:
            self.move(target)
            return

        if (
            self._move_animation
            and self._move_animation.state() == QPropertyAnimation.State.Running
        ):
            self._move_animation.stop()

        self._move_animation = QPropertyAnimation(self, b"pos", self)
        self._move_animation.setDuration(170)
        self._move_animation.setStartValue(self.pos())
        self._move_animation.setEndValue(target)
        self._move_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._move_animation.start()

    def enterEvent(self, event):  # pylint: disable=invalid-name
        if not self._is_closing and self.duration > 0:
            remaining = self.close_timer.remainingTime()
            if remaining > 0:
                self._remaining_duration_ms = remaining
            self.close_timer.stop()
            if (
                self._progress_animation
                and self._progress_animation.state() == QPropertyAnimation.State.Running
            ):
                self._progress_animation.pause()
        super().enterEvent(event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        if (
            not self._is_closing
            and self.duration > 0
            and self._remaining_duration_ms > 0
            and not self.close_timer.isActive()
        ):
            self.close_timer.start(self._remaining_duration_ms)
            if (
                self._progress_animation
                and self._progress_animation.state() == QPropertyAnimation.State.Paused
            ):
                self._progress_animation.resume()
        super().leaveEvent(event)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        if (
            not self._progress_animation
            or self._progress_animation.state() == QPropertyAnimation.State.Stopped
        ):
            track_rect = self._progress_track.contentsRect()
            self._progress_fill.setGeometry(0, 0, track_rect.width(), track_rect.height())

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        # لا نغلق الإشعار عند الضغط عليه لتجنب الإغلاق السريع غير المقصود.
        super().mousePressEvent(event)

    @staticmethod
    def _is_app_quitting() -> bool:
        manager_quitting = False
        try:
            manager_quitting = bool(getattr(NotificationManager, "_app_is_quitting", False))
        except Exception:
            manager_quitting = False
        app = QApplication.instance()
        return bool(
            app
            and (app.closingDown() or bool(app.property("_skywave_force_quit")) or manager_quitting)
        )

    def closeEvent(self, event):  # pylint: disable=invalid-name
        # Guard against external close requests (dialog lifecycle/focus transitions).
        if self._is_app_quitting():
            super().closeEvent(event)
            return
        if not self._is_closing:
            # Always ignore external close attempts; log once for diagnostics.
            # Some dialog/focus transitions emit closeEvent on top-level tool windows.
            event.ignore()
            if not self._logged_external_close_once:
                safe_print(
                    f"WARNING: [NotificationSystem] External closeEvent detected for title={self.title!r}"
                )
                self._logged_external_close_once = True
            QTimer.singleShot(0, self._restore_visibility)
            return
        super().closeEvent(event)

    def hideEvent(self, event):  # pylint: disable=invalid-name
        super().hideEvent(event)
        if self._is_app_quitting():
            return
        if self._is_closing or self._restoring_visibility:
            return

        # Preserve remaining TTL when hidden externally, then restore visibility.
        if self.duration > 0 and self.close_timer.isActive():
            remaining = self.close_timer.remainingTime()
            if remaining > 0:
                self._remaining_duration_ms = remaining
            self.close_timer.stop()
            if (
                self._progress_animation
                and self._progress_animation.state() == QPropertyAnimation.State.Running
            ):
                self._progress_animation.pause()

        now_mono = time.monotonic()
        if (now_mono - self._last_restore_attempt_mono) < 0.15:
            return

        self._last_restore_attempt_mono = now_mono
        if not self._logged_external_hide_once:
            safe_print(
                f"WARNING: [NotificationSystem] External hideEvent detected for title={self.title!r}; restoring"
            )
            self._logged_external_hide_once = True
        QTimer.singleShot(0, self._restore_visibility)


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
        idle_streak = 0
        while self.is_running:
            had_activity = False
            try:
                if (
                    self.repo is not None
                    and getattr(self.repo, "online", False)
                    and getattr(self.repo, "mongo_db", None) is not None
                ):
                    had_activity = bool(self._check_new_notifications())
            except Exception as e:
                safe_print(f"WARNING: [NotificationSync] {e}")
            if had_activity:
                idle_streak = 0
            else:
                idle_streak = min(8, idle_streak + 1)

            # Adaptive idle backoff to reduce background load and UI event pressure.
            backoff_factor = 1 + min(4, idle_streak // 2)
            sleep_ms = int(self._check_interval * backoff_factor)
            self.msleep(max(300, min(5000, sleep_ms)))

    def _check_new_notifications(self):
        try:
            if self.repo is None or self.repo.mongo_db is None:
                return False

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
                    return False

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

            return bool(saw_new or settings_triggered)

        except Exception as e:
            safe_print(f"ERROR: [NotificationSync] Check failed: {e}")
            # لا نوقف الـ worker، فقط نسجل الخطأ ونتابع
            return False

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
    _pending_notifications: deque = deque()
    _max_visible = 4
    _max_pending = 60
    _spacing = 10
    _margin = 20
    _repo = None
    _sync_worker = None
    _sync_write_queue = None
    _sync_write_thread = None
    _sync_write_running = False
    _app_is_quitting = False
    _initialized = False
    _min_duration_ms = 45000
    _default_duration_ms = 60000
    _warning_duration_ms = 75000
    _error_duration_ms = 90000
    _remote_duration_ms = 60000

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
        self._pending_notifications = deque()

        self._sync_worker = NotificationSyncWorker()
        self._sync_worker.new_notification.connect(self._on_remote_notification)
        self._sync_worker.start()

        # Async writer for cloud notification documents to keep UI saves responsive.
        self._sync_write_queue = queue.Queue(maxsize=300)
        self._sync_write_running = True
        self._sync_write_thread = threading.Thread(
            target=self._run_sync_write_worker,
            daemon=True,
            name="notification-sync-writer",
        )
        self._sync_write_thread.start()

        app = QApplication.instance()
        if app is not None:
            try:
                app.aboutToQuit.connect(self._on_app_about_to_quit)
            except Exception:
                pass

    @classmethod
    def _on_app_about_to_quit(cls):
        cls._app_is_quitting = True
        app = QApplication.instance()
        if app is not None:
            try:
                app.setProperty("_skywave_force_quit", True)
            except Exception:
                pass

    @staticmethod
    def _coerce_legacy_duration_sync(duration, sync: bool) -> tuple[int | None, bool]:
        """
        Backward-compat:
        Older calls may pass third positional arg as sync flag.
        """
        if isinstance(duration, bool) and isinstance(sync, bool) and sync is True:
            return None, duration
        if duration is None:
            return None, sync
        try:
            return int(duration), sync
        except (TypeError, ValueError):
            return None, sync

    def _resolve_duration(
        self,
        duration: int | None,
        notification_type: NotificationType,
        message: str,
        *,
        remote: bool = False,
    ) -> int:
        if duration is None:
            if remote:
                base = self._remote_duration_ms
            elif notification_type == NotificationType.ERROR:
                base = self._error_duration_ms
            elif notification_type == NotificationType.WARNING:
                base = self._warning_duration_ms
            else:
                base = self._default_duration_ms
        else:
            base = int(duration)

        if base == 0:
            return 0

        # Dynamic readability time for longer messages.
        msg_len = len((message or "").strip())
        extra_ms = max(0, msg_len - 48) * 90
        if remote:
            extra_ms += 1200

        return max(self._min_duration_ms, base + min(extra_ms, 12000))

    @classmethod
    def set_repository(cls, repo):
        manager = cls()
        manager._repo = repo
        if manager._sync_worker:
            manager._sync_worker.set_repository(repo)

    def _run_sync_write_worker(self) -> None:
        while self._sync_write_running:
            try:
                item = self._sync_write_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if item is None:
                break

            repo_ref, payload = item
            try:
                if repo_ref is None or not getattr(repo_ref, "online", False):
                    continue
                mongo_db = getattr(repo_ref, "mongo_db", None)
                if mongo_db is None:
                    continue
                mongo_db.notifications.insert_one(payload)
            except Exception as e:
                safe_print(f"ERROR: [NotificationManager] Async sync failed: {e}")
            finally:
                try:
                    self._sync_write_queue.task_done()
                except Exception:
                    pass

    def _enqueue_sync_payload(self, payload: dict) -> None:
        repo_ref = self._repo
        if repo_ref is None or not getattr(repo_ref, "online", False):
            return
        if self._sync_write_queue is None:
            return

        item = (repo_ref, payload)
        try:
            self._sync_write_queue.put_nowait(item)
            return
        except queue.Full:
            pass

        # Drop oldest queued write to prioritize recent user actions.
        try:
            _ = self._sync_write_queue.get_nowait()
            self._sync_write_queue.task_done()
        except Exception:
            pass

        try:
            self._sync_write_queue.put_nowait(item)
        except queue.Full:
            # Best-effort: skip when queue is saturated.
            pass

    @classmethod
    def _on_remote_notification(cls, data: dict):
        manager = cls()

        try:
            type_map = {
                "success": NotificationType.SUCCESS,
                "error": NotificationType.ERROR,
                "warning": NotificationType.WARNING,
                "info": NotificationType.INFO,
            }
            notification_type = type_map.get(data.get("type"), NotificationType.INFO)
            message = data.get("message", "")
            title = data.get("title")
            source_device = data.get("device_id")

            notification = ToastNotification(
                message=message,
                notification_type=notification_type,
                title=title,
                duration=manager._resolve_duration(
                    None,
                    notification_type,
                    message,
                    remote=True,
                ),
                source_device=source_device,
            )
            notification.closed.connect(lambda: manager._on_notification_closed(notification))
            manager._queue_or_show_notification(notification)
        except Exception as e:
            safe_print(f"ERROR: [NotificationManager] Remote notification failed: {e}")

    @classmethod
    def show(
        cls,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        title: str = None,
        duration: int | None = None,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        manager = cls()
        try:
            duration, sync = manager._coerce_legacy_duration_sync(duration, sync)
            duration = manager._resolve_duration(duration, notification_type, message, remote=False)

            notification = ToastNotification(
                message=message,
                notification_type=notification_type,
                title=title,
                duration=duration,
                source_device=DEVICE_ID,
            )
            notification.closed.connect(lambda: manager._on_notification_closed(notification))
            manager._queue_or_show_notification(notification)

            if sync and manager._repo is not None and manager._repo.online:
                manager._enqueue_sync_payload(
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
            safe_print(f"ERROR: [NotificationManager] Show failed: {e}")

    @classmethod
    def success(
        cls,
        message: str,
        title: str = None,
        duration: int | None = None,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        duration, sync = cls._coerce_legacy_duration_sync(duration, sync)
        cls.show(
            message,
            NotificationType.SUCCESS,
            title,
            duration,
            sync,
            entity_type,
            action,
        )

    @classmethod
    def error(
        cls,
        message: str,
        title: str = None,
        duration: int | None = None,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        duration, sync = cls._coerce_legacy_duration_sync(duration, sync)
        cls.show(
            message,
            NotificationType.ERROR,
            title,
            duration,
            sync,
            entity_type,
            action,
        )

    @classmethod
    def warning(
        cls,
        message: str,
        title: str = None,
        duration: int | None = None,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        duration, sync = cls._coerce_legacy_duration_sync(duration, sync)
        cls.show(
            message,
            NotificationType.WARNING,
            title,
            duration,
            sync,
            entity_type,
            action,
        )

    @classmethod
    def info(
        cls,
        message: str,
        title: str = None,
        duration: int | None = None,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
    ):
        duration, sync = cls._coerce_legacy_duration_sync(duration, sync)
        cls.show(
            message,
            NotificationType.INFO,
            title,
            duration,
            sync,
            entity_type,
            action,
        )

    def _on_notification_closed(self, notification):
        self._prune_notifications()
        if notification in self._notifications:
            self._notifications.remove(notification)
        self._drain_pending_notifications()
        self._update_positions()

    def _prune_notifications(self):
        alive = []
        for notification in self._notifications:
            try:
                shown_once = getattr(notification, "_shown_at_mono", 0.0) > 0
                visible_now = notification.isVisible()
                is_closing = bool(getattr(notification, "_is_closing", False))
                timer_active = bool(
                    hasattr(notification, "close_timer") and notification.close_timer.isActive()
                )
                if shown_once and not visible_now:
                    if is_closing and not timer_active:
                        continue
                    if not is_closing and hasattr(notification, "_restore_visibility"):
                        try:
                            if not bool(getattr(notification, "_restoring_visibility", False)):
                                QTimer.singleShot(0, notification._restore_visibility)
                        except Exception:
                            pass
                alive.append(notification)
            except RuntimeError:
                continue
        self._notifications = alive

    def _queue_or_show_notification(self, notification: ToastNotification):
        self._prune_notifications()
        if len(self._notifications) < self._max_visible:
            self._notifications.append(notification)
            self._update_positions()
            notification.show_notification()
            return

        self._pending_notifications.append(notification)
        while len(self._pending_notifications) > self._max_pending:
            self._pending_notifications.popleft()

    def _drain_pending_notifications(self):
        self._prune_notifications()
        while self._pending_notifications and len(self._notifications) < self._max_visible:
            nxt = self._pending_notifications.popleft()
            self._notifications.append(nxt)
            self._update_positions()
            nxt.show_notification()

    def _update_positions(self):
        self._prune_notifications()
        screen = None
        cursor_pos = QCursor.pos()
        if cursor_pos is not None:
            screen = QApplication.screenAt(cursor_pos)
        active_window = QApplication.activeWindow()
        if screen is None and active_window and active_window.screen():
            screen = active_window.screen()
        if screen is None:
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
            if hasattr(notification, "animate_move_to"):
                notification.animate_move_to(x, y)
            else:
                notification.move(x, y)

            y -= self._spacing

    @classmethod
    def shutdown(cls):
        manager = cls()
        cls._app_is_quitting = True
        app = QApplication.instance()
        if app is not None:
            try:
                app.setProperty("_skywave_force_quit", True)
            except Exception:
                pass
        if manager._sync_worker:
            manager._sync_worker.stop()
        manager._sync_write_running = False
        if manager._sync_write_queue is not None:
            try:
                manager._sync_write_queue.put_nowait(None)
            except queue.Full:
                try:
                    _ = manager._sync_write_queue.get_nowait()
                    manager._sync_write_queue.task_done()
                    manager._sync_write_queue.put_nowait(None)
                except Exception:
                    pass
        if manager._sync_write_thread and manager._sync_write_thread.is_alive():
            manager._sync_write_thread.join(timeout=1.0)
        for notification in list(manager._notifications):
            try:
                notification.close_notification(reason="shutdown")
            except Exception:
                pass
        manager._notifications.clear()
        manager._pending_notifications.clear()


def notify_success(
    message: str,
    title: str = None,
    duration: int | bool | None = None,
    sync: bool = True,
    entity_type: str | None = None,
    action: str | None = None,
):
    NotificationManager.success(
        message,
        title,
        duration=duration,
        sync=sync,
        entity_type=entity_type,
        action=action,
    )


def notify_error(
    message: str,
    title: str = None,
    duration: int | bool | None = None,
    sync: bool = True,
    entity_type: str | None = None,
    action: str | None = None,
):
    NotificationManager.error(
        message,
        title,
        duration=duration,
        sync=sync,
        entity_type=entity_type,
        action=action,
    )


def notify_warning(
    message: str,
    title: str = None,
    duration: int | bool | None = None,
    sync: bool = True,
    entity_type: str | None = None,
    action: str | None = None,
):
    NotificationManager.warning(
        message,
        title,
        duration=duration,
        sync=sync,
        entity_type=entity_type,
        action=action,
    )


def notify_info(
    message: str,
    title: str = None,
    duration: int | bool | None = None,
    sync: bool = True,
    entity_type: str | None = None,
    action: str | None = None,
):
    NotificationManager.info(
        message,
        title,
        duration=duration,
        sync=sync,
        entity_type=entity_type,
        action=action,
    )
