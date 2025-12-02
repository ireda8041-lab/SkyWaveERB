# الملف: ui/notification_widget.py

"""
ويدجت الإشعارات
يعرض الإشعارات للمستخدم مع أيقونة الجرس
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QScrollArea, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QCursor
from datetime import datetime
from typing import List
from core.schemas import Notification, NotificationType, NotificationPriority


class NotificationItem(QFrame):
    """
    عنصر إشعار واحد
    """
    
    clicked = pyqtSignal(int)  # إشارة عند الضغط على الإشعار
    
    def __init__(self, notification: Notification, parent=None):
        super().__init__(parent)
        self.notification = notification
        self.init_ui()
    
    def init_ui(self):
        """تهيئة الواجهة"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # تحديد اللون حسب النوع
        color = self._get_color_for_type(self.notification.type)
        
        # تحديد الخلفية حسب حالة القراءة
        if self.notification.is_read:
            bg_color = "#f5f5f5"
        else:
            bg_color = "#e3f2fd"
        
        self.setStyleSheet(f"""
            NotificationItem {{
                background-color: {bg_color};
                border-left: 4px solid {color};
                border-radius: 4px;
                padding: 8px;
                margin: 4px;
            }}
            NotificationItem:hover {{
                background-color: #e0e0e0;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(4)
        
        # الصف الأول: الأيقونة والعنوان والوقت
        header_layout = QHBoxLayout()
        
        # أيقونة النوع
        icon_label = QLabel(self._get_icon_for_type(self.notification.type))
        icon_label.setStyleSheet(f"color: {color}; font-size: 16px;")
        header_layout.addWidget(icon_label)
        
        # العنوان
        title_label = QLabel(self.notification.title)
        title_font = QFont()
        title_font.setBold(not self.notification.is_read)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #333;")
        header_layout.addWidget(title_label, 1)
        
        # الوقت
        time_str = self._format_time(self.notification.created_at)
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #999; font-size: 11px;")
        header_layout.addWidget(time_label)
        
        layout.addLayout(header_layout)
        
        # الصف الثاني: الرسالة
        message_label = QLabel(self.notification.message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(message_label)
        
        self.setLayout(layout)
    
    def _get_color_for_type(self, type: NotificationType) -> str:
        """الحصول على اللون حسب نوع الإشعار"""
        colors = {
            NotificationType.INFO: "#2196F3",
            NotificationType.SUCCESS: "#4CAF50",
            NotificationType.WARNING: "#FF9800",
            NotificationType.ERROR: "#F44336",
            NotificationType.PROJECT_DUE: "#FF9800",
            NotificationType.PAYMENT_RECEIVED: "#4CAF50",
            NotificationType.QUOTATION_EXPIRED: "#FF9800",
            NotificationType.SYNC_FAILED: "#F44336"
        }
        return colors.get(type, "#2196F3")
    
    def _get_icon_for_type(self, type: NotificationType) -> str:
        """الحصول على الأيقونة حسب نوع الإشعار"""
        icons = {
            NotificationType.INFO: "ℹ️",
            NotificationType.SUCCESS: "✅",
            NotificationType.WARNING: "⚠️",
            NotificationType.ERROR: "❌",
            NotificationType.PROJECT_DUE: "📅",
            NotificationType.PAYMENT_RECEIVED: "💰",
            NotificationType.QUOTATION_EXPIRED: "⏰",
            NotificationType.SYNC_FAILED: "🔄"
        }
        return icons.get(type, "ℹ️")
    
    def _format_time(self, dt: datetime) -> str:
        """تنسيق الوقت بشكل نسبي"""
        now = datetime.now()
        diff = now - dt
        
        if diff.seconds < 60:
            return "الآن"
        elif diff.seconds < 3600:
            minutes = diff.seconds // 60
            return f"منذ {minutes} دقيقة"
        elif diff.seconds < 86400:
            hours = diff.seconds // 3600
            return f"منذ {hours} ساعة"
        elif diff.days == 1:
            return "أمس"
        elif diff.days < 7:
            return f"منذ {diff.days} يوم"
        else:
            return dt.strftime("%Y-%m-%d")
    
    def mousePressEvent(self, event):
        """معالج الضغط على الإشعار"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.notification.id)
        super().mousePressEvent(event)


class NotificationPopup(QFrame):
    """
    نافذة منبثقة لعرض الإشعارات
    """
    
    notification_clicked = pyqtSignal(int)
    mark_all_read_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(400, 500)
        self.init_ui()
    
    def init_ui(self):
        """تهيئة الواجهة"""
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # الرأس
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #2196F3;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 12px;
            }
        """)
        header_layout = QHBoxLayout()
        
        title_label = QLabel("الإشعارات")
        title_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        mark_all_btn = QPushButton("تحديد الكل كمقروء")
        mark_all_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: 1px solid white;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        mark_all_btn.clicked.connect(self.mark_all_read_clicked.emit)
        header_layout.addWidget(mark_all_btn)
        
        header.setLayout(header_layout)
        layout.addWidget(header)
        
        # منطقة التمرير للإشعارات
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
        """)
        
        self.notifications_container = QWidget()
        self.notifications_layout = QVBoxLayout()
        self.notifications_layout.setSpacing(0)
        self.notifications_layout.setContentsMargins(8, 8, 8, 8)
        self.notifications_container.setLayout(self.notifications_layout)
        
        scroll_area.setWidget(self.notifications_container)
        layout.addWidget(scroll_area)
        
        self.setLayout(layout)
    
    def set_notifications(self, notifications: List[Notification]):
        """
        تعيين الإشعارات للعرض
        
        Args:
            notifications: قائمة الإشعارات
        """
        # مسح الإشعارات القديمة
        while self.notifications_layout.count():
            item = self.notifications_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # إضافة الإشعارات الجديدة
        if notifications:
            for notification in notifications:
                item = NotificationItem(notification)
                item.clicked.connect(self.notification_clicked.emit)
                self.notifications_layout.addWidget(item)
            
            self.notifications_layout.addStretch()
        else:
            # لا توجد إشعارات
            no_notif_label = QLabel("لا توجد إشعارات")
            no_notif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_notif_label.setStyleSheet("color: #999; padding: 40px;")
            self.notifications_layout.addWidget(no_notif_label)


class NotificationWidget(QWidget):
    """
    ويدجت الإشعارات الرئيسي
    - أيقونة الجرس مع Badge
    - نافذة منبثقة للإشعارات
    """
    
    def __init__(self, notification_service, parent=None):
        super().__init__(parent)
        self.notification_service = notification_service
        self.popup = None
        self.init_ui()
        
        # تحديث العدد كل 10 ثواني
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_badge)
        self.update_timer.start(10000)
        
        # تحديث أولي
        self.update_badge()
    
    def init_ui(self):
        """تهيئة الواجهة"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Container للجرس والـ Badge
        bell_container = QWidget()
        bell_container.setFixedSize(50, 40)
        bell_layout = QHBoxLayout(bell_container)
        bell_layout.setContentsMargins(0, 0, 0, 0)
        bell_layout.setSpacing(0)
        
        # زر الجرس
        self.bell_button = QPushButton("🔔 الإشعارات")
        self.bell_button.setMinimumWidth(100)
        self.bell_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.bell_button.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.bell_button.clicked.connect(self.toggle_popup)
        layout.addWidget(self.bell_button)
        
        # Badge (عدد الإشعارات غير المقروءة)
        self.badge_label = QLabel("0")
        self.badge_label.setFixedSize(22, 22)
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_label.setStyleSheet("""
            QLabel {
                background-color: #ef4444;
                color: white;
                border-radius: 11px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.badge_label.setVisible(False)
        layout.addWidget(self.badge_label)
        
        self.setLayout(layout)
    
    def update_badge(self):
        """تحديث عدد الإشعارات غير المقروءة"""
        try:
            count = self.notification_service.get_unread_count()
            
            if count > 0:
                self.badge_label.setText(str(count) if count < 100 else "99+")
                self.badge_label.setVisible(True)
            else:
                self.badge_label.setVisible(False)
        
        except Exception as e:
            print(f"خطأ في تحديث badge الإشعارات: {e}")
    
    def toggle_popup(self):
        """فتح/إغلاق نافذة الإشعارات"""
        if self.popup and self.popup.isVisible():
            self.popup.hide()
        else:
            self.show_popup()
    
    def show_popup(self):
        """عرض نافذة الإشعارات"""
        try:
            # إنشاء النافذة المنبثقة
            if not self.popup:
                self.popup = NotificationPopup(self)
                self.popup.notification_clicked.connect(self.on_notification_clicked)
                self.popup.mark_all_read_clicked.connect(self.on_mark_all_read)
            
            # الحصول على الإشعارات
            notifications = self.notification_service.get_all_notifications(limit=50)
            self.popup.set_notifications(notifications)
            
            # حساب موضع النافذة (أسفل الجرس)
            button_pos = self.bell_button.mapToGlobal(self.bell_button.rect().bottomLeft())
            popup_x = button_pos.x() - self.popup.width() + self.bell_button.width()
            popup_y = button_pos.y() + 5
            
            self.popup.move(popup_x, popup_y)
            self.popup.show()
        
        except Exception as e:
            print(f"خطأ في عرض نافذة الإشعارات: {e}")
    
    def on_notification_clicked(self, notification_id: int):
        """معالج الضغط على إشعار"""
        try:
            # تحديد الإشعار كمقروء
            self.notification_service.mark_as_read(notification_id)
            
            # تحديث Badge
            self.update_badge()
            
            # إعادة تحميل الإشعارات
            if self.popup and self.popup.isVisible():
                notifications = self.notification_service.get_all_notifications(limit=50)
                self.popup.set_notifications(notifications)
        
        except Exception as e:
            print(f"خطأ في معالجة الضغط على الإشعار: {e}")
    
    def on_mark_all_read(self):
        """معالج تحديد جميع الإشعارات كمقروءة"""
        try:
            self.notification_service.mark_all_as_read()
            
            # تحديث Badge
            self.update_badge()
            
            # إعادة تحميل الإشعارات
            if self.popup and self.popup.isVisible():
                notifications = self.notification_service.get_all_notifications(limit=50)
                self.popup.set_notifications(notifications)
        
        except Exception as e:
            print(f"خطأ في تحديد جميع الإشعارات كمقروءة: {e}")


print("ui/notification_widget.py تم إنشاؤه بنجاح.")
