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
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
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
    QHBoxLayout,
    QLabel,
    QMainWindow,
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


@dataclass(slots=True)
class NotificationToastPayload:
    message: str
    notification_type: NotificationType = NotificationType.INFO
    title: str | None = None
    duration: int | None = None
    sync: bool = True
    entity_type: str | None = None
    action: str | None = None
    source_device: str | None = None
    transport_only: bool = False
    silent: bool = False
    persistent: bool = False

    @property
    def is_remote(self) -> bool:
        return bool(self.source_device and self.source_device != DEVICE_ID)


class ToastNotification(QWidget):
    """إشعار Toast منبثق - تصميم عصري وجميل"""

    closed = pyqtSignal()

    def __init__(
        self,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        title: str = None,
        duration: int = 12000,
        entity_type: str | None = None,
        action: str | None = None,
        source_device: str = None,
        persistent: bool = False,
        owner_window=None,
        parent=None,
    ):
        super().__init__(parent)
        self.message = message
        self.notification_type = notification_type
        self.title = title
        self.entity_type = str(entity_type or "").strip() or None
        self.action = str(action or "").strip() or None
        self._persistent = bool(persistent)
        try:
            normalized_duration = int(duration)
        except (TypeError, ValueError):
            normalized_duration = 6500

        # 0 = لا يغلق تلقائياً. أي قيمة موجبة صغيرة جدًا تتحول لحد أدنى مقروء.
        if normalized_duration == 0:
            self.duration = 0
        else:
            self.duration = max(10000, normalized_duration)
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
        self._owner_window = owner_window
        if owner_window is not None:
            try:
                owner_window.destroyed.connect(self._clear_owner_window)
            except Exception:
                self._owner_window = None

        self._setup_ui()
        self._setup_animation()

    def _clear_owner_window(self, *_args):
        self._owner_window = None

    def owner_window(self):
        owner = getattr(self, "_owner_window", None)
        if owner is None:
            return None
        try:
            owner.isVisible()
        except RuntimeError:
            self._owner_window = None
            return None
        return owner

    def _is_prominent_notification(self) -> bool:
        return self._persistent or self.notification_type in (
            NotificationType.WARNING,
            NotificationType.ERROR,
        )

    @staticmethod
    def _format_display_time(value: datetime | None = None) -> str:
        display_dt = value or datetime.now()
        hour_text = display_dt.strftime("%I").lstrip("0") or "12"
        minute_text = display_dt.strftime("%M")
        meridiem = "ص" if display_dt.hour < 12 else "م"
        return f"{hour_text}:{minute_text} {meridiem}"

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

    @staticmethod
    def _normalized_key(value: str | None) -> str:
        return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

    @classmethod
    def _entity_display_name(cls, entity_type: str | None) -> str | None:
        normalized = cls._normalized_key(entity_type)
        if not normalized:
            return None
        labels = {
            "client": "عميل",
            "clients": "عميل",
            "project": "مشروع",
            "projects": "مشروع",
            "invoice": "فاتورة",
            "invoices": "فاتورة",
            "payment": "دفعة",
            "payments": "دفعة",
            "expense": "مصروف",
            "expenses": "مصروف",
            "service": "خدمة",
            "services": "خدمة",
            "quotation": "عرض سعر",
            "quotations": "عرض سعر",
            "task": "مهمة",
            "tasks": "مهمة",
            "todo": "مهمة",
            "account": "حساب",
            "accounts": "حساب",
            "user": "مستخدم",
            "users": "مستخدم",
            "notification": "إشعار",
            "notifications": "إشعار",
            "currency": "عملة",
            "currencies": "عملة",
            "settings": "إعدادات",
            "system_settings": "إعدادات",
        }
        return labels.get(normalized) or normalized.replace("_", " ")

    @classmethod
    def _entity_subject_name(cls, entity_type: str | None) -> str | None:
        normalized = cls._normalized_key(entity_type)
        if not normalized:
            return None
        labels = {
            "client": "العميل",
            "clients": "العميل",
            "project": "المشروع",
            "projects": "المشروع",
            "invoice": "الفاتورة",
            "invoices": "الفاتورة",
            "payment": "الدفعة",
            "payments": "الدفعة",
            "expense": "المصروف",
            "expenses": "المصروف",
            "service": "الخدمة",
            "services": "الخدمة",
            "quotation": "عرض السعر",
            "quotations": "عرض السعر",
            "task": "المهمة",
            "tasks": "المهمة",
            "todo": "المهمة",
            "account": "الحساب",
            "accounts": "الحساب",
            "user": "المستخدم",
            "users": "المستخدم",
            "notification": "الإشعار",
            "notifications": "الإشعار",
            "currency": "العملة",
            "currencies": "العملة",
            "settings": "الإعدادات",
            "system_settings": "الإعدادات",
        }
        return labels.get(normalized) or cls._entity_display_name(entity_type)

    @classmethod
    def _action_display_name(cls, action: str | None) -> str | None:
        normalized = cls._normalized_key(action)
        if not normalized:
            return None
        labels = {
            "create": "إنشاء",
            "created": "إنشاء",
            "add": "إضافة",
            "added": "إضافة",
            "update": "تعديل",
            "updated": "تعديل",
            "edit": "تعديل",
            "edited": "تعديل",
            "modify": "تعديل",
            "modified": "تعديل",
            "save": "حفظ",
            "saved": "حفظ",
            "delete": "حذف",
            "deleted": "حذف",
            "remove": "حذف",
            "removed": "حذف",
            "archive": "أرشفة",
            "archived": "أرشفة",
            "restore": "استعادة",
            "restored": "استعادة",
            "sync": "مزامنة",
            "synced": "مزامنة",
            "send": "إرسال",
            "sent": "إرسال",
            "pay": "تحصيل",
            "paid": "تحصيل",
            "complete": "إكمال",
            "completed": "إكمال",
            "approve": "اعتماد",
            "approved": "اعتماد",
            "reject": "رفض",
            "rejected": "رفض",
            "due": "استحقاق",
            "overdue": "استحقاق",
        }
        return labels.get(normalized) or normalized.replace("_", " ")

    def _build_operation_sentence(self) -> str | None:
        action_key = self._normalized_key(self.action)
        entity_subject = self._entity_subject_name(self.entity_type)
        if action_key and entity_subject:
            templates = {
                "create": "تم إنشاء {entity} بنجاح",
                "created": "تم إنشاء {entity} بنجاح",
                "add": "تمت إضافة {entity} بنجاح",
                "added": "تمت إضافة {entity} بنجاح",
                "update": "تم تعديل بيانات {entity} بنجاح",
                "updated": "تم تعديل بيانات {entity} بنجاح",
                "edit": "تم تعديل بيانات {entity} بنجاح",
                "edited": "تم تعديل بيانات {entity} بنجاح",
                "modify": "تم تعديل بيانات {entity} بنجاح",
                "modified": "تم تعديل بيانات {entity} بنجاح",
                "save": "تم حفظ {entity} بنجاح",
                "saved": "تم حفظ {entity} بنجاح",
                "delete": "تم حذف {entity}",
                "deleted": "تم حذف {entity}",
                "remove": "تم حذف {entity}",
                "removed": "تم حذف {entity}",
                "archive": "تمت أرشفة {entity}",
                "archived": "تمت أرشفة {entity}",
                "restore": "تمت استعادة {entity}",
                "restored": "تمت استعادة {entity}",
                "sync": "تمت مزامنة {entity}",
                "synced": "تمت مزامنة {entity}",
                "send": "تم إرسال {entity}",
                "sent": "تم إرسال {entity}",
                "pay": "تم تحصيل {entity}",
                "paid": "تم تحصيل {entity}",
                "complete": "تم إكمال {entity}",
                "completed": "تم إكمال {entity}",
                "approve": "تم اعتماد {entity}",
                "approved": "تم اعتماد {entity}",
                "reject": "تم رفض {entity}",
                "rejected": "تم رفض {entity}",
                "due": "تم تسجيل استحقاق {entity}",
                "overdue": "تم تسجيل استحقاق {entity}",
            }
            template = templates.get(action_key)
            if template:
                return template.format(entity=entity_subject)

        action_text = self._action_display_name(self.action)
        if action_text and entity_subject:
            return f"تم تنفيذ إجراء {action_text} على {entity_subject}"
        if action_text:
            return f"تم تنفيذ الإجراء: {action_text}"
        if entity_subject:
            return f"تم تحديث بيانات {entity_subject}"
        return None

    def _build_operation_details(self) -> str | None:
        return self._build_operation_sentence()

    def _setup_enterprise_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        theme = self._theme()
        accent = theme["accent"]
        accent_dark = theme["accent_dark"]
        prominent = self._is_prominent_notification()
        surface_palette = {
            NotificationType.SUCCESS: ("#122635", "#0c1825", "تم"),
            NotificationType.ERROR: ("#291522", "#111827", "خطأ"),
            NotificationType.WARNING: ("#2b2012", "#111827", "تحذير"),
            NotificationType.INFO: ("#10243b", "#0c1726", "معلومة"),
        }
        surface_start, surface_end, type_label_text = surface_palette.get(
            self.notification_type,
            surface_palette[NotificationType.INFO],
        )
        toast_width = 432 if prominent else 404
        icon_size = 36 if prominent else 32
        icon_radius = icon_size // 2
        title_font_size = 15 if prominent else 14
        message_font_size = 12 if prominent else 11
        progress_height = 3 if prominent else 2
        accent_width = 4 if prominent else 3
        bottom_margin = 14 if prominent else 12
        self.setFixedWidth(toast_width)

        self._container = QWidget()
        self._container.setObjectName("notif_container")
        self._container.setStyleSheet(
            f"""
            QWidget#notif_container {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {surface_start}, stop:0.58 #101c2d, stop:1 {surface_end});
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 18px;
            }}
        """
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 145))
        self._container.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._container)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        color_bar = QWidget()
        color_bar.setFixedWidth(accent_width)
        color_bar.setStyleSheet(
            f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {accent}, stop:1 {accent_dark});
            border-top-right-radius: 18px;
            border-bottom-right-radius: 18px;
        """
        )
        body_layout.addWidget(color_bar)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(18, 16, 16, bottom_margin)
        content_layout.setSpacing(14)

        icon_container = QWidget()
        icon_container.setObjectName("notif_icon_shell")
        icon_container.setFixedSize(icon_size, icon_size)
        icon_container.setStyleSheet(
            f"""
            QWidget#notif_icon_shell {{
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: {icon_radius}px;
            }}
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
            font-size: {15 if prominent else 14}px;
            font-weight: 700;
            font-family: 'Cairo';
        """
        )
        icon_layout.addWidget(icon_label)
        content_layout.addWidget(
            icon_container,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_text = (self.title or theme["title_fallback"]).strip()
        if self.source_device and self.source_device != DEVICE_ID:
            title_text += " (جهاز آخر)"

        utility_widget = QWidget()
        utility_widget.setStyleSheet("background: transparent;")
        utility_widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        utility_row = QHBoxLayout(utility_widget)
        utility_row.setContentsMargins(0, 0, 0, 0)
        utility_row.setSpacing(6)

        type_badge = QLabel(type_label_text)
        type_badge.setObjectName("notif_type_badge")
        type_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        type_badge.setStyleSheet(
            f"""
            color: {accent};
            background: transparent;
            border: none;
            padding: 0;
            font-size: {10 if prominent else 9}px;
            font-weight: 700;
            font-family: 'Cairo';
        """
        )
        utility_row.addWidget(type_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        separator_label = QLabel("\u2022")
        separator_label.setObjectName("notif_meta_separator")
        separator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        separator_label.setStyleSheet(
            """
            color: rgba(255, 255, 255, 0.35);
            background: transparent;
            border: none;
            font-size: 8px;
            font-weight: 700;
        """
        )
        utility_row.addWidget(separator_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        time_label = QLabel(self._format_display_time())
        time_label.setObjectName("notif_time_label")
        time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_label.setStyleSheet(
            f"""
            color: {COLORS['text_secondary']};
            background: transparent;
            border: none;
            padding: 0;
            font-size: 9px;
            font-weight: 700;
            font-family: 'Cairo';
        """
        )
        utility_row.addWidget(time_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        utility_row.addStretch(1)
        text_layout.addWidget(utility_widget)

        title_label = QLabel(title_text)
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(
            f"""
            color: {COLORS['text_primary']};
            background: transparent;
            font-size: {title_font_size}px;
            font-weight: 700;
            font-family: 'Cairo';
            line-height: 1.15;
        """
        )
        text_layout.addWidget(title_label)

        operation_details = self._build_operation_details()
        if operation_details:
            details_label = QLabel(operation_details)
            details_label.setObjectName("notif_operation_details")
            details_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            details_label.setWordWrap(True)
            details_label.setStyleSheet(
                """
                color: rgba(255, 255, 255, 0.62);
                background: transparent;
                font-size: 10px;
                font-weight: 600;
                font-family: 'Cairo';
            """
            )
            text_layout.addWidget(details_label)

        msg_label = QLabel((self.message or "").strip())
        msg_label.setObjectName("notif_message_label")
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        msg_label.setStyleSheet(
            f"""
            color: rgba(255, 255, 255, 0.82);
            background: transparent;
            font-size: {message_font_size}px;
            font-family: 'Cairo';
        """
        )
        text_layout.addWidget(msg_label)
        content_layout.addLayout(text_layout, 1)

        body_layout.addLayout(content_layout, 1)
        card_layout.addLayout(body_layout)

        self._progress_track = QWidget()
        self._progress_track.setFixedHeight(progress_height)
        self._progress_track.setStyleSheet(
            """
            background: rgba(255, 255, 255, 0.08);
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
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.addWidget(self._container)

    def _setup_ui(self):
        self._setup_enterprise_ui()
        return
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setFixedWidth(408)

        theme = self._theme()
        accent = theme["accent"]
        accent_dark = theme["accent_dark"]
        prominent = self._is_prominent_notification()
        surface_palette = {
            NotificationType.SUCCESS: ("#0d2f24", "#091f19", "تم"),
            NotificationType.ERROR: ("#34111a", "#220c13", "خطأ"),
            NotificationType.WARNING: ("#3a2208", "#261606", "تحذير"),
            NotificationType.INFO: ("#0d2f5f", "#091a34", "معلومة"),
        }
        surface_start, surface_end, type_label_text = surface_palette.get(
            self.notification_type,
            surface_palette[NotificationType.INFO],
        )
        toast_width = 420 if prominent else 392
        icon_size = 40 if prominent else 34
        icon_radius = icon_size // 2
        title_font_size = 15 if prominent else 13
        message_font_size = 12 if prominent else 11
        progress_height = 3 if prominent else 2
        bottom_margin = 12 if prominent else 10
        self.setFixedWidth(toast_width)

        self._container = QWidget()
        self._container.setObjectName("notif_container")
        self._container.setStyleSheet(
            f"""
            QWidget#notif_container {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {surface_start}, stop:0.52 #0b2446, stop:1 {surface_end});
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
            }}
        """
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 150))
        self._container.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._container)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        color_bar = QWidget()
        color_bar.setFixedWidth(4)
        color_bar.setStyleSheet(
            f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {accent}, stop:1 {accent_dark});
            border-radius: 16px 0 0 16px;
        """
        )
        body_layout.addWidget(color_bar)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(16, 14, 14, bottom_margin)
        content_layout.setSpacing(12)

        icon_container = QWidget()
        icon_container.setFixedSize(icon_size, icon_size)
        icon_container.setStyleSheet(
            f"""
            background: qradialgradient(cx:0.5, cy:0.45, radius:0.9,
                stop:0 rgba(255, 255, 255, 0.10), stop:1 {accent_dark}22);
            border: 1px solid {accent}3A;
            border-radius: {icon_radius}px;
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
            font-size: {16 if prominent else 15}px;
            font-weight: 700;
            font-family: 'Cairo';
        """
        )
        icon_layout.addWidget(icon_label)
        content_layout.addWidget(
            icon_container,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_text = (self.title or theme["title_fallback"]).strip()
        if self.source_device and self.source_device != DEVICE_ID:
            title_text += " (جهاز آخر)"

        header_widget = QWidget()
        header_widget.setStyleSheet("background: transparent;")
        header_widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        header_row = QHBoxLayout(header_widget)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title_label = QLabel(title_text)
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(
            f"""
            color: {COLORS['text_primary']};
            background: transparent;
            font-size: {title_font_size}px;
            font-weight: 700;
            font-family: 'Cairo';
            line-height: 1.15;
        """
        )
        header_row.addWidget(title_label, 1)

        close_btn = QPushButton("\u00D7")
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: none;
                font-size: 14px;
                font-weight: 700;
                padding: 0;
            }}
            QPushButton:hover {{
                background: transparent;
                color: {COLORS['text_primary']};
            }}
        """
        )
        close_btn.clicked.connect(lambda: self._request_close("button"))
        header_row.addWidget(
            close_btn,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )
        text_layout.addWidget(header_widget)

        meta_widget = QWidget()
        meta_widget.setStyleSheet("background: transparent;")
        meta_widget.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        meta_row = QHBoxLayout(meta_widget)
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(6)

        type_badge = QLabel(type_label_text)
        type_badge.setObjectName("notif_type_badge")
        type_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        type_badge.setStyleSheet(
            f"""
            color: {accent};
            background: transparent;
            border: none;
            padding: 0;
            font-size: 10px;
            font-weight: 700;
            font-family: 'Cairo';
        """
        )
        meta_row.addWidget(type_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        separator_label = QLabel("\u2022")
        separator_label.setObjectName("notif_meta_separator")
        separator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        separator_label.setStyleSheet(
            """
            color: rgba(255, 255, 255, 0.35);
            background: transparent;
            border: none;
            font-size: 8px;
            font-weight: 700;
        """
        )
        meta_row.addWidget(separator_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        time_label = QLabel(self._format_display_time())
        time_label.setObjectName("notif_time_label")
        time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_label.setStyleSheet(
            f"""
            color: {COLORS['text_secondary']};
            background: transparent;
            border: none;
            padding: 0;
            font-size: 10px;
            font-weight: 700;
            font-family: 'Cairo';
        """
        )
        meta_row.addWidget(
            time_label,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        meta_row.addStretch(1)
        text_layout.addWidget(meta_widget)

        msg_label = QLabel((self.message or "").strip())
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        msg_label.setStyleSheet(
            f"""
            color: rgba(255, 255, 255, 0.90);
            background: transparent;
            font-size: {message_font_size}px;
            font-family: 'Cairo';
        """
        )
        text_layout.addWidget(msg_label)
        content_layout.addLayout(text_layout, 1)

        body_layout.addLayout(content_layout, 1)
        card_layout.addLayout(body_layout)

        self._progress_track = QWidget()
        self._progress_track.setFixedHeight(progress_height)
        self._progress_track.setStyleSheet(
            """
            background: rgba(255, 255, 255, 0.08);
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
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.addWidget(self._container)

    def _setup_animation(self):
        self.slide_in = QPropertyAnimation(self, b"pos")
        self.slide_in.setDuration(220)
        self.slide_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.slide_out = QPropertyAnimation(self, b"pos")
        self.slide_out.setDuration(180)
        self.slide_out.setEasingCurve(QEasingCurve.Type.InQuad)
        self.slide_out.finished.connect(self._on_close_animation_finished)

        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(lambda: self._request_close("timer"))

        self._visibility_guard_timer = QTimer(self)
        self._visibility_guard_timer.setInterval(250)
        self._visibility_guard_timer.timeout.connect(self._guard_visibility)

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

        self.slide_in.stop()
        self.slide_in.setStartValue(start_pos)
        self.slide_in.setEndValue(target_pos)
        self.slide_in.start()
        self._visibility_guard_timer.start()
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

    def _guard_visibility(self):
        if self._is_closing:
            self._visibility_guard_timer.stop()
            return
        if not self.isVisible():
            self._restore_visibility()
            return
        self._raise_safely()

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
        self._visibility_guard_timer.stop()
        self.close_timer.stop()
        if self._progress_animation:
            self._progress_animation.stop()

        current_pos = QPoint(self.pos())
        out_pos = QPoint(current_pos.x() + 18, current_pos.y())
        self.slide_out.stop()
        self.slide_out.setStartValue(current_pos)
        self.slide_out.setEndValue(out_pos)
        self.slide_out.start()

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

    def _on_close_animation_finished(self):
        self._visibility_guard_timer.stop()
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
        self._session_started_at = datetime.now()
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

    @staticmethod
    def _transport_cleanup_query(cutoff_iso: str, cutoff_dt: datetime) -> dict:
        return {
            "$and": [
                {
                    "$or": [
                        {"created_at": {"$lt": cutoff_iso}},
                        {"created_at": {"$lt": cutoff_dt}},
                    ]
                },
                {
                    "$or": [
                        {"transport_only": True},
                        {"action": "sync_ping"},
                        {"silent": True},
                    ]
                },
            ]
        }

    @staticmethod
    def _is_active_remote_notification(notification: dict) -> bool:
        if bool(notification.get("is_deleted")):
            return False
        sync_status = str(notification.get("sync_status") or "").strip().lower()
        return sync_status != "deleted"

    @staticmethod
    def _notification_created_at(notification: dict) -> datetime | None:
        raw_value = notification.get("created_at")
        if isinstance(raw_value, datetime):
            created_at = raw_value
        else:
            text = str(raw_value or "").strip()
            if not text:
                return None
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            try:
                created_at = datetime.fromisoformat(text)
            except Exception:
                return None

        if created_at.tzinfo is not None:
            try:
                created_at = created_at.astimezone().replace(tzinfo=None)
            except Exception:
                created_at = created_at.replace(tzinfo=None)
        return created_at

    @staticmethod
    def _notification_entity_type(notification: dict) -> str | None:
        return notification.get("entity_type") or notification.get("related_entity_type") or None

    @staticmethod
    def _is_transport_only_notification(notification: dict) -> bool:
        if bool(notification.get("transport_only")):
            return True
        action_value = str(notification.get("action") or "").strip().lower()
        return action_value == "sync_ping" or bool(notification.get("silent"))

    @classmethod
    def _is_persistent_remote_notification(cls, notification: dict) -> bool:
        entity_key = str(cls._notification_entity_type(notification) or "").strip().lower()
        if entity_key == "notifications":
            return True
        if cls._is_transport_only_notification(notification):
            return False
        persistent_fields = (
            "priority",
            "last_modified",
            "related_entity_type",
            "related_entity_id",
            "expires_at",
            "is_read",
            "action_url",
        )
        return any(notification.get(field) is not None for field in persistent_fields)

    @classmethod
    def _notification_poll_query(cls, check_iso: str, check_dt: datetime) -> dict:
        return {
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
                {
                    "$or": [
                        {"sync_status": {"$exists": False}},
                        {"sync_status": {"$ne": "deleted"}},
                    ]
                },
                {
                    "$or": [
                        {"is_deleted": {"$exists": False}},
                        {"is_deleted": {"$ne": True}},
                    ]
                },
            ]
        }

    def set_repository(self, repo):
        self.repo = repo
        self._session_started_at = datetime.now()
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
                query = self._notification_poll_query(check_iso, check_dt)
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
                    if self._is_active_remote_notification(n)
                    and (n.get("device_id") is None or n.get("device_id") != DEVICE_ID)
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
                    created_at = self._notification_created_at(notif)
                    if created_at is not None and created_at < self._session_started_at:
                        continue

                    saw_new = True

                    safe_print(
                        f"INFO: [NotificationSync] Received from {notif.get('device_id')}: {notif.get('title')}"
                    )

                    entity_type = self._notification_entity_type(notif)
                    entity_key = str(entity_type).strip().lower() if entity_type else ""
                    action_value = str(notif.get("action") or "").strip().lower()
                    title_text = str(notif.get("title") or "").strip()
                    message_text = str(notif.get("message") or "").strip()
                    silent = bool(notif.get("silent")) or action_value == "sync_ping"
                    persistent_notification = self._is_persistent_remote_notification(notif)
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

                    if persistent_notification and entity_key not in {
                        "system_settings",
                        "settings",
                    }:
                        trigger_tables.add("notifications")
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
                    if hasattr(collection, "delete_many"):
                        old_dt = datetime.now() - timedelta(hours=1)
                        old_time = old_dt.isoformat()
                        result = collection.delete_many(
                            self._transport_cleanup_query(old_time, old_dt)
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
    _min_duration_ms = 10000
    _default_duration_ms = 10000
    _warning_duration_ms = 10000
    _error_duration_ms = 10000
    _remote_duration_ms = 10000
    _dedupe_window_seconds = 8.0
    _max_recent_fingerprints = 400

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
        self._recent_fingerprints: dict[str, float] = {}

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
            try:
                app.installEventFilter(self)
            except Exception:
                pass

    @staticmethod
    def _find_toast_owner(widget) -> QMainWindow | None:
        current = widget
        visited = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            if isinstance(current, QMainWindow):
                return current
            parent_getter = getattr(current, "parentWidget", None)
            current = parent_getter() if callable(parent_getter) else None
        return None

    def _resolve_toast_owner(self) -> QMainWindow | None:
        app = QApplication.instance()
        if app is None:
            return None

        candidates = [
            app.activePopupWidget(),
            app.activeModalWidget(),
            app.activeWindow(),
            app.focusWidget(),
        ]
        for candidate in candidates:
            owner = self._find_toast_owner(candidate)
            if owner is not None:
                return owner

        try:
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QMainWindow) and widget.isVisible():
                    return widget
        except Exception:
            return None
        return None

    def _restack_visible_notifications(self) -> None:
        if self._app_is_quitting:
            return
        self._prune_notifications()
        self._update_positions()
        for notification in list(self._notifications):
            try:
                if notification.isVisible() and not bool(
                    getattr(notification, "_is_closing", False)
                ):
                    notification._raise_safely()
            except RuntimeError:
                continue

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        if self._app_is_quitting or event is None or not self._notifications:
            return False

        event_type = event.type()
        watched_is_top_level = False
        try:
            watched_is_top_level = bool(
                isinstance(watched, QWidget)
                and watched.isWindow()
                and not isinstance(watched, ToastNotification)
            )
        except RuntimeError:
            watched_is_top_level = False

        if watched_is_top_level and event_type in {
            QEvent.Type.Show,
            QEvent.Type.Hide,
            QEvent.Type.Close,
            QEvent.Type.WindowActivate,
            QEvent.Type.WindowStateChange,
        }:
            delay_ms = 0 if event_type in {QEvent.Type.Show, QEvent.Type.WindowActivate} else 120
            QTimer.singleShot(delay_ms, self._restack_visible_notifications)
        return False

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

        return max(self._min_duration_ms, base)

    @staticmethod
    def _normalize_text(value: object) -> str:
        return " ".join(str(value or "").strip().split())

    @staticmethod
    def _notification_type_from_value(raw_value) -> NotificationType:
        if isinstance(raw_value, NotificationType):
            return raw_value
        normalized = str(raw_value or "").strip().lower()
        type_map = {
            "success": NotificationType.SUCCESS,
            "error": NotificationType.ERROR,
            "warning": NotificationType.WARNING,
            "info": NotificationType.INFO,
        }
        return type_map.get(normalized, NotificationType.INFO)

    def _build_payload(
        self,
        *,
        message: str,
        notification_type: NotificationType | str = NotificationType.INFO,
        title: str | None = None,
        duration: int | None = None,
        sync: bool = True,
        entity_type: str | None = None,
        action: str | None = None,
        source_device: str | None = None,
        transport_only: bool = False,
        silent: bool = False,
        persistent: bool = False,
    ) -> NotificationToastPayload:
        try:
            safe_duration = None if duration is None else int(duration)
        except (TypeError, ValueError):
            safe_duration = None
        return NotificationToastPayload(
            message=str(message or "").strip(),
            notification_type=self._notification_type_from_value(notification_type),
            title=str(title or "").strip() or None,
            duration=safe_duration,
            sync=bool(sync),
            entity_type=str(entity_type or "").strip() or None,
            action=str(action or "").strip() or None,
            source_device=str(source_device or "").strip() or None,
            transport_only=bool(transport_only),
            silent=bool(silent),
            persistent=bool(persistent),
        )

    def _recent_fingerprint_cache(self) -> dict[str, float]:
        cache = self.__dict__.get("_recent_fingerprints")
        if cache is None:
            cache = {}
            self.__dict__["_recent_fingerprints"] = cache
        return cache

    def _prune_recent_fingerprints(self, now_mono: float | None = None) -> None:
        cache = self._recent_fingerprint_cache()
        if not cache:
            return
        now_value = time.monotonic() if now_mono is None else now_mono
        cutoff = now_value - self._dedupe_window_seconds
        expired = [key for key, seen_at in cache.items() if seen_at < cutoff]
        for key in expired:
            cache.pop(key, None)

        if len(cache) <= self._max_recent_fingerprints:
            return
        for key, _seen_at in sorted(cache.items(), key=lambda item: item[1])[
            : len(cache) - self._max_recent_fingerprints
        ]:
            cache.pop(key, None)

    def _payload_fingerprint(self, payload: NotificationToastPayload) -> str:
        title_text = self._normalize_text(payload.title)
        message_text = self._normalize_text(payload.message)
        if not title_text and not message_text:
            return ""
        return "|".join(
            [
                payload.notification_type.value,
                title_text,
                message_text,
                self._normalize_text(payload.entity_type),
                self._normalize_text(payload.action),
                "remote" if payload.is_remote else "local",
                "persistent" if payload.persistent else "transient",
            ]
        )

    def _should_skip_payload(self, payload: NotificationToastPayload) -> bool:
        if payload.silent:
            return True
        if not self._normalize_text(payload.message):
            return True

        fingerprint = self._payload_fingerprint(payload)
        if not fingerprint:
            return False

        now_mono = time.monotonic()
        self._prune_recent_fingerprints(now_mono)
        cache = self._recent_fingerprint_cache()
        last_seen = cache.get(fingerprint)
        if last_seen is not None and (now_mono - last_seen) < self._dedupe_window_seconds:
            return True
        cache[fingerprint] = now_mono
        return False

    def _present_payload(self, payload: NotificationToastPayload) -> bool:
        if self._should_skip_payload(payload):
            return False

        owner = self._resolve_toast_owner()
        notification = ToastNotification(
            message=payload.message,
            notification_type=payload.notification_type,
            title=payload.title,
            duration=self._resolve_duration(
                payload.duration,
                payload.notification_type,
                payload.message,
                remote=payload.is_remote,
            ),
            entity_type=payload.entity_type,
            action=payload.action,
            source_device=payload.source_device or DEVICE_ID,
            persistent=payload.persistent,
            owner_window=owner,
        )
        notification.closed.connect(lambda: self._on_notification_closed(notification))
        self._queue_or_show_notification(notification)

        if payload.sync and self._repo is not None and getattr(self._repo, "online", False):
            self._enqueue_sync_payload(
                {
                    "message": payload.message,
                    "type": payload.notification_type.value,
                    "title": payload.title,
                    "device_id": DEVICE_ID,
                    "created_at": datetime.now().isoformat(),
                    "entity_type": payload.entity_type,
                    "action": payload.action,
                    "transport_only": True,
                }
            )
        return True

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
            payload = manager._build_payload(
                message=data.get("message", ""),
                notification_type=data.get("type"),
                title=data.get("title"),
                duration=None,
                sync=False,
                entity_type=data.get("entity_type"),
                action=data.get("action"),
                source_device=data.get("device_id"),
            )
            manager._present_payload(payload)
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
        persistent: bool = False,
    ):
        manager = cls()
        try:
            duration, sync = manager._coerce_legacy_duration_sync(duration, sync)
            payload = manager._build_payload(
                message=message,
                notification_type=notification_type,
                title=title,
                duration=duration,
                sync=sync,
                entity_type=entity_type,
                action=action,
                source_device=DEVICE_ID,
                persistent=persistent,
            )
            manager._present_payload(payload)
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
            QTimer.singleShot(0, self._restack_visible_notifications)
            QTimer.singleShot(180, self._restack_visible_notifications)
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
            QTimer.singleShot(0, self._restack_visible_notifications)
            QTimer.singleShot(180, self._restack_visible_notifications)

    def _update_positions(self):
        self._prune_notifications()
        screen = None
        for notification in reversed(self._notifications):
            owner_getter = getattr(notification, "owner_window", None)
            owner = owner_getter() if callable(owner_getter) else None
            try:
                if owner is not None and owner.screen() is not None:
                    screen = owner.screen()
                    break
            except RuntimeError:
                continue
        cursor_pos = QCursor.pos()
        if screen is None and cursor_pos is not None:
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
            try:
                app.removeEventFilter(manager)
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
        manager._recent_fingerprints = {}
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
