# الملف: ui/notification_widget.py
"""
نظام الإشعارات - Sky Wave ERP
تصميم بسيط ومودرن
"""

from datetime import datetime
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QCursor, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame, QGraphicsDropShadowEffect
)

from core.schemas import Notification, NotificationType
from ui.styles import COLORS


class NotificationCard(QFrame):
    """بطاقة إشعار واحدة"""
    
    clicked = pyqtSignal(int)
    deleted = pyqtSignal(int)
    
    ICONS = {
        NotificationType.INFO: ("ℹ", "#3B82F6"),
        NotificationType.SUCCESS: ("✓", "#10B981"),
        NotificationType.WARNING: ("!", "#F59E0B"),
        NotificationType.ERROR: ("✕", "#EF4444"),
        NotificationType.PROJECT_DUE: ("📋", "#8B5CF6"),
        NotificationType.PAYMENT_RECEIVED: ("$", "#10B981"),
        NotificationType.QUOTATION_EXPIRED: ("⏰", "#F59E0B"),
        NotificationType.SYNC_FAILED: ("↻", "#EF4444"),
    }
    
    def __init__(self, notification: Notification, parent=None):
        super().__init__(parent)
        self.notification = notification
        self._build()
    
    def _build(self):
        self.setFixedHeight(70)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # الخلفية
        is_unread = not self.notification.is_read
        bg = "#0D3B66" if is_unread else "#0A2647"
        
        self.setStyleSheet(f"""
            NotificationCard {{
                background-color: {bg};
                border-radius: 8px;
                margin: 3px 6px;
            }}
            NotificationCard:hover {{
                background-color: #144272;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(12)
        
        # دائرة الأيقونة
        icon_data = self.ICONS.get(self.notification.type, ("🔔", COLORS['primary']))
        icon_char, icon_color = icon_data
        
        icon_frame = QFrame()
        icon_frame.setFixedSize(36, 36)
        icon_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {icon_color};
                border-radius: 18px;
            }}
        """)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(icon_char)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: transparent;")
        icon_layout.addWidget(icon_label)
        layout.addWidget(icon_frame)
        
        # المحتوى
        content = QVBoxLayout()
        content.setSpacing(4)
        content.setContentsMargins(0, 0, 0, 0)
        
        # العنوان
        title = QLabel(self.notification.title)
        title.setStyleSheet(f"""
            color: {'#FFFFFF' if is_unread else '#B0C4DE'}; 
            font-size: 12px; 
            font-weight: {'bold' if is_unread else 'normal'};
            background: transparent;
        """)
        content.addWidget(title)
        
        # الرسالة
        msg_text = self.notification.message
        if len(msg_text) > 55:
            msg_text = msg_text[:55] + "..."
        msg = QLabel(msg_text)
        msg.setStyleSheet(f"color: #8899AA; font-size: 10px; background: transparent;")
        msg.setWordWrap(True)
        content.addWidget(msg)
        
        layout.addLayout(content, 1)
        
        # العمود الأيمن (الوقت + الحذف)
        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        right_col.setContentsMargins(0, 0, 0, 0)
        
        # الوقت
        time_text = self._format_time()
        time_lbl = QLabel(time_text)
        time_lbl.setStyleSheet("color: #667788; font-size: 9px; background: transparent;")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(time_lbl)
        
        right_col.addStretch()
        
        # زر الحذف
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(20, 20)
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #556677;
                border: none;
                font-size: 12px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: #EF4444;
                color: white;
            }
        """)
        del_btn.clicked.connect(lambda: self.deleted.emit(self.notification.id))
        right_col.addWidget(del_btn, 0, Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(right_col)
    
    def _format_time(self) -> str:
        diff = datetime.now() - self.notification.created_at
        secs = diff.total_seconds()
        if secs < 60:
            return "الآن"
        elif secs < 3600:
            return f"منذ {int(secs // 60)} د"
        elif secs < 86400:
            return f"منذ {int(secs // 3600)} س"
        elif diff.days == 1:
            return "أمس"
        else:
            return f"منذ {diff.days} يوم"
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.notification.id)
        super().mousePressEvent(event)


class NotificationPanel(QFrame):
    """لوحة الإشعارات المنبثقة"""
    
    on_notification_click = pyqtSignal(int)
    on_notification_delete = pyqtSignal(int)
    on_mark_all_read = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(360, 420)
        self._build()
    
    def _build(self):
        self.setStyleSheet(f"""
            NotificationPanel {{
                background-color: #0A1929;
                border: 1px solid #1E3A5F;
                border-radius: 12px;
            }}
        """)
        
        # الظل
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === الهيدر ===
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #0A6CF1, stop:1 #2563EB);
                border-top-left-radius: 11px;
                border-top-right-radius: 11px;
            }
        """)
        
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 12, 0)
        
        # أيقونة + عنوان
        title_lbl = QLabel("🔔  الإشعارات")
        title_lbl.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: transparent;")
        h_layout.addWidget(title_lbl)
        
        # عداد
        self.count_badge = QLabel("0")
        self.count_badge.setFixedSize(26, 26)
        self.count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_badge.setStyleSheet("""
            background: rgba(255,255,255,0.2);
            color: white;
            border-radius: 13px;
            font-size: 11px;
            font-weight: bold;
        """)
        h_layout.addWidget(self.count_badge)
        
        h_layout.addStretch()
        
        # زر قراءة الكل
        mark_all_btn = QPushButton("قراءة الكل ✓")
        mark_all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        mark_all_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.15);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.25);
            }
        """)
        mark_all_btn.clicked.connect(self.on_mark_all_read.emit)
        h_layout.addWidget(mark_all_btn)
        
        main_layout.addWidget(header)
        
        # === منطقة المحتوى ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: #0A1929;
                border: none;
            }}
            QScrollBar:vertical {{
                background: #0D2137;
                width: 8px;
                margin: 4px 2px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #1E4976;
                border-radius: 4px;
                min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #2563EB;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: #0A1929;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(6, 10, 6, 10)
        self.content_layout.setSpacing(6)
        
        scroll.setWidget(self.content_widget)
        main_layout.addWidget(scroll)
    
    def set_notifications(self, notifications: list):
        """تحميل الإشعارات"""
        # تحديث العداد
        unread = sum(1 for n in notifications if not n.is_read)
        self.count_badge.setText(str(unread) if unread > 0 else str(len(notifications)))
        
        # مسح المحتوى القديم
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if notifications:
            for notif in notifications[:20]:
                card = NotificationCard(notif)
                card.clicked.connect(self.on_notification_click.emit)
                card.deleted.connect(self.on_notification_delete.emit)
                self.content_layout.addWidget(card)
        else:
            # رسالة فارغة
            empty_widget = QWidget()
            empty_layout = QVBoxLayout(empty_widget)
            empty_layout.setContentsMargins(20, 60, 20, 60)
            
            empty_icon = QLabel("📭")
            empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_icon.setStyleSheet("font-size: 48px; background: transparent;")
            empty_layout.addWidget(empty_icon)
            
            empty_text = QLabel("لا توجد إشعارات")
            empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_text.setStyleSheet(f"color: #667788; font-size: 14px; background: transparent;")
            empty_layout.addWidget(empty_text)
            
            self.content_layout.addWidget(empty_widget)
        
        self.content_layout.addStretch()


class NotificationWidget(QWidget):
    """مدير نظام الإشعارات"""
    
    def __init__(self, notification_service, parent=None):
        super().__init__(parent)
        self.service = notification_service
        self.panel = None
        self.unread_count = 0
        
        # تحديث دوري
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_count)
        self.timer.start(30000)
        self._update_count()
    
    def _update_count(self):
        try:
            self.unread_count = self.service.get_unread_count()
        except:
            self.unread_count = 0
    
    def show_popup_at(self, pos: QPoint, btn_width: int = 38):
        """إظهار لوحة الإشعارات"""
        try:
            # Toggle
            if self.panel and self.panel.isVisible():
                self.panel.hide()
                return
            
            # إنشاء اللوحة
            if not self.panel:
                self.panel = NotificationPanel()
                self.panel.on_notification_click.connect(self._handle_click)
                self.panel.on_notification_delete.connect(self._handle_delete)
                self.panel.on_mark_all_read.connect(self._handle_mark_all)
            
            # تحميل البيانات
            try:
                notifications = self.service.get_all_notifications(limit=20)
            except:
                notifications = []
            
            self.panel.set_notifications(notifications)
            
            # === حساب الموضع ===
            panel_w = self.panel.width()
            panel_h = self.panel.height()
            
            # نريد اللوحة تظهر أسفل الزر
            x = pos.x()  # يسار الزر
            y = pos.y() + 8  # أسفل الزر
            
            # تعديل لتكون محاذية لليمين مع الزر
            x = x + btn_width - panel_w
            
            # حدود الشاشة
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                
                # لا تخرج من اليسار
                if x < geo.left() + 10:
                    x = geo.left() + 10
                
                # لا تخرج من اليمين
                if x + panel_w > geo.right() - 10:
                    x = geo.right() - panel_w - 10
                
                # لا تخرج من الأسفل
                if y + panel_h > geo.bottom() - 10:
                    y = pos.y() - panel_h - 50
            
            self.panel.move(x, y)
            self.panel.show()
            
        except Exception as e:
            print(f"[Notifications] Error: {e}")
    
    def _handle_click(self, nid: int):
        try:
            self.service.mark_as_read(nid)
            self._refresh_panel()
        except:
            pass
    
    def _handle_delete(self, nid: int):
        try:
            self.service.delete_notification(nid)
            self._refresh_panel()
        except:
            pass
    
    def _handle_mark_all(self):
        try:
            self.service.mark_all_as_read()
            self._refresh_panel()
        except:
            pass
    
    def _refresh_panel(self):
        self._update_count()
        if self.panel and self.panel.isVisible():
            try:
                notifications = self.service.get_all_notifications(limit=20)
                self.panel.set_notifications(notifications)
            except:
                pass
