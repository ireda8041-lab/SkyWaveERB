# الملف: ui/notification_system.py
"""
نظام الإشعارات العام للبرنامج
- إشعارات Toast تظهر في زاوية الشاشة
- مزامنة الإشعارات بين الأجهزة عبر MongoDB
"""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QThread, QObject
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGraphicsOpacityEffect,
    QApplication,
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


# معرف الجهاز الحالي
DEVICE_ID = str(uuid.uuid4())[:8]


class ToastNotification(QWidget):
    """إشعار Toast منبثق"""
    
    closed = pyqtSignal()
    
    def __init__(
        self,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        title: str = None,
        duration: int = 4000,
        source_device: str = None,
        parent=None
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
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(300)
        
        colors = {
            NotificationType.SUCCESS: ("#10b981", "✅"),
            NotificationType.ERROR: ("#ef4444", "❌"),
            NotificationType.WARNING: ("#f59e0b", "⚠️"),
            NotificationType.INFO: ("#3b82f6", "ℹ️"),
        }
        accent, icon = colors.get(self.notification_type, ("#6b7280", "🔔"))
        
        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background: {COLORS['bg_dark']};
                border: 1px solid {accent};
                border-left: 4px solid {accent};
                border-radius: 6px;
            }}
        """)
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 16px; background: transparent;")
        icon_label.setFixedWidth(20)
        layout.addWidget(icon_label)
        
        content = QVBoxLayout()
        content.setSpacing(1)
        content.setContentsMargins(0, 0, 0, 0)
        
        if self.title:
            title_text = self.title
            if self.source_device and self.source_device != DEVICE_ID:
                title_text += " 🌐"
            title_label = QLabel(title_text)
            title_label.setStyleSheet(f"""
                color: {COLORS['text_primary']};
                font-size: 11px;
                font-weight: bold;
                font-family: 'Cairo';
                background: transparent;
            """)
            content.addWidget(title_label)
        
        msg_label = QLabel(self.message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: 10px;
            font-family: 'Cairo';
            background: transparent;
        """)
        content.addWidget(msg_label)
        
        layout.addLayout(content, 1)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: none;
                font-size: 14px;
            }}
            QPushButton:hover {{
                color: {COLORS['text_primary']};
            }}
        """)
        close_btn.clicked.connect(self.close_notification)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)
    
    def _setup_animation(self):
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(150)
        self.fade_in.setStartValue(0)
        self.fade_in.setEndValue(1)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(200)
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
    
    def mousePressEvent(self, event):
        self.close_notification()


class NotificationSyncWorker(QThread):
    """عامل مزامنة الإشعارات من MongoDB"""
    
    new_notification = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = True
        self.last_check = datetime.now()
        self.repo = None
    
    def set_repository(self, repo):
        self.repo = repo
    
    def run(self):
        while self.is_running:
            try:
                if self.repo and self.repo.online and self.repo.mongo_db:
                    self._check_new_notifications()
            except Exception as e:
                safe_print(f"ERROR: [NotificationSync] {e}")
            
            self.msleep(3000)  # كل 3 ثواني
    
    def _check_new_notifications(self):
        try:
            collection = self.repo.mongo_db.notifications
            
            # جلب الإشعارات الجديدة من أجهزة أخرى
            notifications = collection.find({
                "created_at": {"$gt": self.last_check.isoformat()},
                "device_id": {"$ne": DEVICE_ID}
            }).sort("created_at", 1).limit(10)
            
            for notif in notifications:
                self.new_notification.emit({
                    "message": notif.get("message", ""),
                    "type": notif.get("type", "info"),
                    "title": notif.get("title"),
                    "device_id": notif.get("device_id")
                })
            
            self.last_check = datetime.now()
            
            # تنظيف الإشعارات القديمة (أكثر من ساعة)
            from datetime import timedelta
            old_time = (datetime.now() - timedelta(hours=1)).isoformat()
            collection.delete_many({"created_at": {"$lt": old_time}})
            
        except Exception as e:
            safe_print(f"ERROR: [NotificationSync] Check failed: {e}")
    
    def stop(self):
        self.is_running = False
        self.quit()
        self.wait()


class NotificationManager(QObject):
    """مدير الإشعارات - Singleton"""
    
    _instance = None
    _notifications: list = []
    _max_visible = 4
    _spacing = 8
    _margin = 15
    _repo = None
    _sync_worker = None
    
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
        
        # بدء عامل المزامنة
        self._sync_worker = NotificationSyncWorker()
        self._sync_worker.new_notification.connect(self._on_remote_notification)
        self._sync_worker.start()
    
    @classmethod
    def set_repository(cls, repo):
        """تعيين الـ repository للمزامنة"""
        manager = cls()
        manager._repo = repo
        if manager._sync_worker:
            manager._sync_worker.set_repository(repo)
    
    @classmethod
    def _on_remote_notification(cls, data: dict):
        """معالجة إشعار من جهاز آخر"""
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
            source_device=data.get("device_id")
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
        sync: bool = True
    ):
        """عرض إشعار جديد"""
        manager = cls()
        
        notification = ToastNotification(
            message=message,
            notification_type=notification_type,
            title=title,
            duration=duration,
            source_device=DEVICE_ID
        )
        notification.closed.connect(lambda: manager._on_notification_closed(notification))
        
        manager._notifications.append(notification)
        
        while len(manager._notifications) > manager._max_visible:
            old = manager._notifications.pop(0)
            old.close_notification()
        
        manager._update_positions()
        notification.show_notification()
        
        # مزامنة مع الأجهزة الأخرى
        if sync and manager._repo and manager._repo.online:
            try:
                manager._repo.mongo_db.notifications.insert_one({
                    "message": message,
                    "type": notification_type.value,
                    "title": title,
                    "device_id": DEVICE_ID,
                    "created_at": datetime.now().isoformat()
                })
            except Exception as e:
                safe_print(f"ERROR: [NotificationManager] Sync failed: {e}")
    
    @classmethod
    def success(cls, message: str, title: str = None, duration: int = 4000, sync: bool = True):
        cls.show(message, NotificationType.SUCCESS, title, duration, sync)
    
    @classmethod
    def error(cls, message: str, title: str = None, duration: int = 5000, sync: bool = True):
        cls.show(message, NotificationType.ERROR, title, duration, sync)
    
    @classmethod
    def warning(cls, message: str, title: str = None, duration: int = 4500, sync: bool = True):
        cls.show(message, NotificationType.WARNING, title, duration, sync)
    
    @classmethod
    def info(cls, message: str, title: str = None, duration: int = 4000, sync: bool = True):
        cls.show(message, NotificationType.INFO, title, duration, sync)
    
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
        """إغلاق مدير الإشعارات"""
        manager = cls()
        if manager._sync_worker:
            manager._sync_worker.stop()


def notify_success(message: str, title: str = None, sync: bool = True):
    NotificationManager.success(message, title, sync=sync)

def notify_error(message: str, title: str = None, sync: bool = True):
    NotificationManager.error(message, title, sync=sync)

def notify_warning(message: str, title: str = None, sync: bool = True):
    NotificationManager.warning(message, title, sync=sync)

def notify_info(message: str, title: str = None, sync: bool = True):
    NotificationManager.info(message, title, sync=sync)
