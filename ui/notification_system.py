# الملف: ui/notification_system.py
"""
نظام الإشعارات العام للبرنامج
- إشعارات Toast تظهر في زاوية الشاشة
- مزامنة الإشعارات بين الأجهزة عبر MongoDB
"""

import json
import uuid
import hashlib
import platform
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
    QGraphicsDropShadowEffect,
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


def _get_stable_device_id() -> str:
    """إنشاء معرف ثابت للجهاز"""
    try:
        machine_info = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
        device_hash = hashlib.md5(machine_info.encode()).hexdigest()[:8]
        return device_hash
    except Exception:
        import os
        device_file = os.path.join(os.path.expanduser("~"), ".skywave_device_id")
        if os.path.exists(device_file):
            with open(device_file, 'r') as f:
                return f.read().strip()
        else:
            new_id = str(uuid.uuid4())[:8]
            try:
                with open(device_file, 'w') as f:
                    f.write(new_id)
            except:
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
        container.setStyleSheet(f"""
            QWidget#notif_container {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['bg_dark']}, stop:1 {COLORS['bg_medium']});
                border: 1px solid {accent}50;
                border-radius: 12px;
            }}
        """)
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(0)
        
        # شريط اللون الجانبي
        color_bar = QWidget()
        color_bar.setFixedWidth(5)
        color_bar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {accent}, stop:1 {dark_accent});
            border-radius: 12px 0 0 12px;
        """)
        layout.addWidget(color_bar)
        
        # منطقة المحتوى
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(14, 12, 10, 12)
        content_layout.setSpacing(12)
        
        # أيقونة دائرية
        icon_container = QWidget()
        icon_container.setFixedSize(40, 40)
        icon_container.setStyleSheet(f"""
            background: {accent}25;
            border-radius: 20px;
        """)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            font-size: 18px;
            color: {accent};
            background: transparent;
            font-weight: bold;
        """)
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
            title_label.setStyleSheet(f"""
                color: {COLORS['text_primary']};
                font-size: 13px;
                font-weight: bold;
                font-family: 'Cairo';
                background: transparent;
            """)
            text_layout.addWidget(title_label)
        
        msg_label = QLabel(self.message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: 11px;
            font-family: 'Cairo';
            background: transparent;
        """)
        text_layout.addWidget(msg_label)
        
        content_layout.addLayout(text_layout, 1)
        
        # زر الإغلاق
        close_btn = QPushButton("×")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
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
        """)
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
    
    def mousePressEvent(self, event):
        self.close_notification()


class NotificationSyncWorker(QThread):
    """عامل مزامنة الإشعارات من MongoDB"""
    
    new_notification = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = True
        self.repo = None
        self._seen_ids = set()
    
    def set_repository(self, repo):
        self.repo = repo
        safe_print(f"INFO: [NotificationSync] Repository set, online={getattr(repo, 'online', False)}")
    
    def run(self):
        safe_print(f"INFO: [NotificationSync] Worker started for device {DEVICE_ID}")
        while self.is_running:
            try:
                if self.repo and getattr(self.repo, 'online', False) and getattr(self.repo, 'mongo_db', None):
                    self._check_new_notifications()
            except Exception as e:
                safe_print(f"ERROR: [NotificationSync] {e}")
            
            self.msleep(2000)
    
    def _check_new_notifications(self):
        try:
            if not self.repo or not self.repo.mongo_db:
                return
                
            collection = self.repo.mongo_db.notifications
            from datetime import timedelta
            check_time = (datetime.now() - timedelta(seconds=30)).isoformat()
            
            try:
                notifications = list(collection.find({
                    "created_at": {"$gt": check_time},
                    "device_id": {"$ne": DEVICE_ID}
                }).sort("created_at", -1).limit(10))
            except Exception as e:
                safe_print(f"ERROR: [NotificationSync] MongoDB query failed: {e}")
                return
            
            for notif in notifications:
                try:
                    notif_id = str(notif.get("_id", ""))
                    if notif_id in self._seen_ids:
                        continue
                    
                    self._seen_ids.add(notif_id)
                    if len(self._seen_ids) > 100:
                        self._seen_ids = set(list(self._seen_ids)[-50:])
                    
                    safe_print(f"INFO: [NotificationSync] Received from {notif.get('device_id')}: {notif.get('title')}")
                    
                    self.new_notification.emit({
                        "message": notif.get("message", ""),
                        "type": notif.get("type", "info"),
                        "title": notif.get("title"),
                        "device_id": notif.get("device_id")
                    })
                except Exception as e:
                    safe_print(f"ERROR: [NotificationSync] فشل معالجة إشعار واحد: {e}")
                    continue  # تجاهل الإشعار المعطوب والمتابعة
            
            # تنظيف الإشعارات القديمة (مع معالجة الأخطاء)
            import time
            if not hasattr(self, '_last_cleanup') or time.time() - self._last_cleanup > 60:
                try:
                    old_time = (datetime.now() - timedelta(hours=1)).isoformat()
                    result = collection.delete_many({"created_at": {"$lt": old_time}})
                    if result.deleted_count > 0:
                        safe_print(f"INFO: [NotificationSync] تم حذف {result.deleted_count} إشعار قديم")
                except Exception as e:
                    safe_print(f"WARNING: [NotificationSync] فشل تنظيف الإشعارات القديمة: {e}")
                self._last_cleanup = time.time()
            
        except Exception as e:
            safe_print(f"ERROR: [NotificationSync] Check failed: {e}")
            # لا نوقف الـ worker، فقط نسجل الخطأ ونتابع
    
    def stop(self):
        self.is_running = False
        self.quit()
        self.wait(1000)  # انتظر ثانية واحدة فقط


class NotificationManager(QObject):
    """مدير الإشعارات - Singleton"""
    
    _instance = None
    _notifications: list = []
    _max_visible = 4
    _spacing = 10
    _margin = 20
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
