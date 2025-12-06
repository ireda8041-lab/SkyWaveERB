# الملف: ui/notification_widget.py

"""
ويدجت الإشعارات الاحترافي
يعرض الإشعارات للمستخدم بتصميم SkyWave Brand
"""

from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.schemas import Notification, NotificationType

# ألوان SkyWave Brand
NOTIFICATION_COLORS = {
    "primary": "#0A6CF1",
    "success": "#10B981",
    "warning": "#FF6636",
    "danger": "#FF4FD8",
    "info": "#8B2CF5",
    "bg_dark": "#001A3A",
    "bg_medium": "#0A2A55",
    "bg_light": "#052045",
    "text_primary": "#EAF3FF",
    "text_secondary": "#B0C4DE",
    "border": "#1E3A5F",
}


class NotificationItem(QFrame):
    """
    عنصر إشعار واحد - تصميم احترافي
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

        # تحديد اللون حسب النوع (ألوان SkyWave Brand)
        color = self._get_color_for_type(self.notification.type)

        # تحديد الخلفية حسب حالة القراءة (ألوان SkyWave Brand)
        if self.notification.is_read:
            bg_color = NOTIFICATION_COLORS["bg_medium"]
            text_color = NOTIFICATION_COLORS["text_secondary"]
            border_width = "3px"
        else:
            bg_color = NOTIFICATION_COLORS["bg_dark"]
            text_color = NOTIFICATION_COLORS["text_primary"]
            border_width = "4px"

        self.setStyleSheet(f"""
            NotificationItem {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {bg_color}, stop:1 {NOTIFICATION_COLORS['bg_light']});
                border-left: {border_width} solid {color};
                border-radius: 10px;
                padding: 14px;
                margin: 6px 4px;
            }}
            NotificationItem:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {NOTIFICATION_COLORS['bg_light']}, stop:1 {NOTIFICATION_COLORS['bg_medium']});
                border-left: 5px solid {color};
            }}
        """)

        # إضافة ظل خفيف
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        # تحديث ألوان النصوص
        self.text_color = text_color

        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # الصف الأول: الأيقونة والعنوان والوقت
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        # أيقونة النوع مع خلفية دائرية
        icon_container = QLabel(self._get_icon_for_type(self.notification.type))
        icon_container.setFixedSize(32, 32)
        icon_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_container.setStyleSheet(f"""
            QLabel {{
                background-color: {color}20;
                border-radius: 16px;
                font-size: 16px;
                padding: 4px;
            }}
        """)
        header_layout.addWidget(icon_container)

        # العنوان
        title_label = QLabel(self.notification.title)
        title_font = QFont("Segoe UI", 11)
        title_font.setBold(not self.notification.is_read)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {self.text_color}; background: transparent;")
        header_layout.addWidget(title_label, 1)

        # الوقت مع أيقونة
        time_str = self._format_time(self.notification.created_at)
        time_label = QLabel(f"🕐 {time_str}")
        time_label.setStyleSheet(f"color: {NOTIFICATION_COLORS['text_secondary']}; font-size: 10px; background: transparent;")
        header_layout.addWidget(time_label)

        layout.addLayout(header_layout)

        # الصف الثاني: الرسالة
        message_label = QLabel(self.notification.message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"color: {NOTIFICATION_COLORS['text_secondary']}; font-size: 12px; padding-right: 42px; background: transparent;")
        layout.addWidget(message_label)

        self.setLayout(layout)

    def _get_color_for_type(self, type: NotificationType) -> str:
        """الحصول على اللون حسب نوع الإشعار (ألوان SkyWave Brand)"""
        colors = {
            NotificationType.INFO: NOTIFICATION_COLORS["primary"],       # Primary Blue
            NotificationType.SUCCESS: NOTIFICATION_COLORS["success"],    # Green
            NotificationType.WARNING: NOTIFICATION_COLORS["warning"],    # Glowing Orange
            NotificationType.ERROR: NOTIFICATION_COLORS["danger"],       # Bright Pink
            NotificationType.PROJECT_DUE: NOTIFICATION_COLORS["warning"],  # Glowing Orange
            NotificationType.PAYMENT_RECEIVED: NOTIFICATION_COLORS["success"],  # Green
            NotificationType.QUOTATION_EXPIRED: NOTIFICATION_COLORS["warning"],  # Glowing Orange
            NotificationType.SYNC_FAILED: NOTIFICATION_COLORS["danger"]  # Bright Pink
        }
        return colors.get(type, NOTIFICATION_COLORS["primary"])

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
    نافذة منبثقة لعرض الإشعارات - تصميم احترافي
    """

    notification_clicked = pyqtSignal(int)
    mark_all_read_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(480, 520)  # عرض أكبر لاستيعاب النص العربي
        self.init_ui()

    def init_ui(self):
        """تهيئة الواجهة"""
        # ألوان SkyWave Brand مع تدرج
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {NOTIFICATION_COLORS['bg_dark']}, stop:1 {NOTIFICATION_COLORS['bg_medium']});
                border: 2px solid {NOTIFICATION_COLORS['primary']};
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # الرأس (ألوان SkyWave Brand) - تصميم احترافي
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {NOTIFICATION_COLORS['primary']}, stop:1 #005BC5);
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                padding: 18px;
            }}
        """)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # أيقونة الجرس مع تأثير
        bell_icon = QLabel("🔔")
        bell_icon.setStyleSheet("font-size: 24px; background: transparent;")
        header_layout.addWidget(bell_icon)

        title_label = QLabel("الإشعارات")
        title_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold; background: transparent;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        mark_all_btn = QPushButton("✓ تحديد الكل كمقروء")
        mark_all_btn.setMinimumWidth(180)  # عرض أكبر للنص الكامل
        mark_all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        mark_all_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.2);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.4);
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
                min-width: 170px;
                font-family: 'Cairo', 'Segoe UI', sans-serif;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.6);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.4);
            }
        """)
        mark_all_btn.clicked.connect(self.mark_all_read_clicked.emit)
        header_layout.addWidget(mark_all_btn)

        header.setLayout(header_layout)
        layout.addWidget(header)

        # منطقة التمرير للإشعارات (ألوان SkyWave Brand) - تصميم احترافي
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {NOTIFICATION_COLORS['bg_dark']};
            }}
            QScrollBar:vertical {{
                background-color: {NOTIFICATION_COLORS['bg_medium']};
                width: 8px;
                border-radius: 4px;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {NOTIFICATION_COLORS['primary']}, stop:1 #005BC5);
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #005BC5, stop:1 {NOTIFICATION_COLORS['primary']});
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.notifications_container = QWidget()
        self.notifications_layout = QVBoxLayout()
        self.notifications_layout.setSpacing(0)
        self.notifications_layout.setContentsMargins(8, 8, 8, 8)
        self.notifications_container.setLayout(self.notifications_layout)

        scroll_area.setWidget(self.notifications_container)
        layout.addWidget(scroll_area)

        self.setLayout(layout)

    def set_notifications(self, notifications: list[Notification]):
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
            no_notif_label = QLabel("📭\n\nلا توجد إشعارات")
            no_notif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_notif_label.setStyleSheet("color: #64748b; padding: 60px; font-size: 14px;")
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

        # زر الجرس (ألوان SkyWave Brand)
        self.bell_button = QPushButton("🔔 الإشعارات")
        self.bell_button.setMinimumWidth(100)
        self.bell_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.bell_button.setStyleSheet("""
            QPushButton {
                background-color: #0A6CF1;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005BC5;
            }
        """)
        self.bell_button.clicked.connect(self.toggle_popup)
        layout.addWidget(self.bell_button)

        # Badge (عدد الإشعارات غير المقروءة) - ألوان SkyWave Brand
        self.badge_label = QLabel("0")
        self.badge_label.setFixedSize(22, 22)
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_label.setStyleSheet("""
            QLabel {
                background-color: #FF4FD8;
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
