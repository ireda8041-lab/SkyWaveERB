# الملف: ui/status_bar_widget.py
"""
شريط الحالة مع مؤشر المزامنة والإشعارات
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QFrame, QVBoxLayout
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QFont, QMovie, QPalette, QColor
from datetime import datetime


class SyncIndicator(QWidget):
    """مؤشر حالة المزامنة"""
    
    sync_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sync_status = "offline"
        self.pending_count = 0
        self.init_ui()
    
    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(8)
        
        # أيقونة الحالة
        self.status_icon = QLabel("🔴")
        self.status_icon.setFont(QFont("Segoe UI Emoji", 12))
        self.status_icon.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(self.status_icon)
        
        # نص الحالة
        self.status_text = QLabel("غير متصل")
        self.status_text.setFont(QFont("Segoe UI", 9))
        self.status_text.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(self.status_text)
        
        # عداد العمليات المعلقة
        from ui.styles import COLORS
        self.pending_label = QLabel("")
        self.pending_label.setFont(QFont("Segoe UI", 8))
        self.pending_label.setStyleSheet(f"color: {COLORS['warning']}; font-weight: bold; background-color: transparent; border: none;")
        layout.addWidget(self.pending_label)
        
        # شريط التقدم (مخفي افتراضياً)
        from ui.styles import COLORS
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: {COLORS['bg_medium']};
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['primary']};
                border-radius: 2px;
            }}
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
        self.setMaximumHeight(30)
        self.setStyleSheet("background-color: transparent;")
    
    def update_status(self, status: str, pending_count: int = 0):
        """تحديث حالة المزامنة"""
        from ui.styles import COLORS
        self.sync_status = status
        self.pending_count = pending_count
        
        # تحديث الأيقونة والنص
        if status == "synced":
            self.status_icon.setText("🟢")
            self.status_text.setText("متزامن")
            self.status_text.setStyleSheet(f"color: {COLORS['success']}; background-color: transparent; border: none;")
            
        elif status == "syncing":
            self.status_icon.setText("🟡")
            self.status_text.setText("جاري المزامنة...")
            self.status_text.setStyleSheet(f"color: {COLORS['warning']}; background-color: transparent; border: none;")
            
        elif status == "offline":
            self.status_icon.setText("🔴")
            self.status_text.setText("غير متصل")
            self.status_text.setStyleSheet(f"color: {COLORS['danger']}; background-color: transparent; border: none;")
            
        elif status == "error":
            self.status_icon.setText("❌")
            self.status_text.setText("خطأ في المزامنة")
            self.status_text.setStyleSheet(f"color: {COLORS['danger']}; background-color: transparent; border: none;")
        
        # تحديث عداد العمليات المعلقة
        if pending_count > 0:
            self.pending_label.setText(f"({pending_count} معلق)")
            self.pending_label.setVisible(True)
        else:
            self.pending_label.setVisible(False)
    
    def update_progress(self, current: int, total: int):
        """تحديث شريط التقدم"""
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)


class ToastNotification(QWidget):
    """إشعار منبثق (Toast)"""
    
    def __init__(self, title: str, message: str, duration: int = 3000, parent=None):
        super().__init__(parent)
        self.duration = duration
        self.init_ui(title, message)
        self.setup_animation()
    
    def init_ui(self, title: str, message: str):
        """إنشاء واجهة الإشعار"""
        from ui.styles import COLORS
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # الحاوية الرئيسية
        main_frame = QFrame()
        main_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_medium']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        
        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        # العنوان
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {COLORS['text_primary']}; background-color: transparent;")
        layout.addWidget(title_label)
        
        # الرسالة
        message_label = QLabel(message)
        message_label.setFont(QFont("Segoe UI", 9))
        message_label.setStyleSheet(f"color: {COLORS['text_secondary']}; background-color: transparent;")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        
        # التخطيط الرئيسي
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_frame)
        self.setLayout(main_layout)
        
        self.setFixedSize(300, 80)
    
    def setup_animation(self):
        """إعداد الحركة"""
        # حركة الظهور
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in_animation.setDuration(300)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # حركة الاختفاء
        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_animation.setDuration(300)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_out_animation.finished.connect(self.close)
        
        # مؤقت الإخفاء
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.start_fade_out)
    
    def show_notification(self):
        """عرض الإشعار"""
        # تحديد الموقع (أسفل يمين الشاشة)
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 20
        y = screen.height() - self.height() - 60
        self.move(x, y)
        
        # عرض النافذة وبدء الحركة
        self.show()
        self.fade_in_animation.start()
        self.hide_timer.start(self.duration)
    
    def start_fade_out(self):
        """بدء حركة الاختفاء"""
        self.fade_out_animation.start()


class StatusBarWidget(QWidget):
    """شريط الحالة الرئيسي"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.notifications = []
        self.current_user = None
        self.init_ui()
    
    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(15)
        
        # 1. LEFT SIDE - مؤشر المزامنة
        self.sync_indicator = SyncIndicator()
        layout.addWidget(self.sync_indicator)
        
        # فاصل
        from ui.styles import COLORS
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.VLine)
        separator1.setStyleSheet(f"color: {COLORS['border']}; background-color: transparent;")
        layout.addWidget(separator1)
        
        # 2. SPACER - دفع العناصر التالية للوسط
        layout.addStretch()
        
        # 3. CENTER - اسم المستخدم والساعة
        self.user_label = QLabel("👤 مستخدم")
        self.user_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.user_label.setStyleSheet(f"color: #00d4ff; background-color: transparent; border: none;")
        layout.addWidget(self.user_label)
        
        # فاصل بين المستخدم والساعة
        separator_center = QLabel(" | ")
        separator_center.setFont(QFont("Segoe UI", 10))
        separator_center.setStyleSheet(f"color: {COLORS['text_secondary']}; background-color: transparent; border: none;")
        layout.addWidget(separator_center)
        
        # الوقت الحالي
        self.time_label = QLabel()
        self.time_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.time_label.setStyleSheet(f"color: #ffffff; background-color: transparent; border: none;")
        layout.addWidget(self.time_label)
        
        # تحديث الوقت كل ثانية
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        self.update_time()
        
        # 4. SPACER - دفع العناصر للوسط
        layout.addStretch()
        
        # فاصل
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.VLine)
        separator2.setStyleSheet(f"color: {COLORS['border']}; background-color: transparent;")
        layout.addWidget(separator2)
        
        # 5. RIGHT SIDE - معلومات النظام
        self.system_info = QLabel("Sky Wave ERP v1.0")
        self.system_info.setFont(QFont("Segoe UI", 9))
        self.system_info.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(self.system_info)
        
        self.setLayout(layout)
        self.setMaximumHeight(32)
        # استخدام الألوان من ملف styles.py
        from ui.styles import COLORS
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_dark']};
                border-top: 1px solid {COLORS['border']};
            }}
            QLabel {{
                background-color: transparent;
                border: none;
                color: {COLORS['text_secondary']};
            }}
            QFrame {{
                background-color: transparent;
            }}
        """)
    
    def update_time(self):
        """تحديث الوقت بصيغة 12 ساعة مع AM/PM"""
        from PyQt6.QtCore import QTime
        current_time = QTime.currentTime()
        self.time_label.setText(current_time.toString("hh:mm:ss AP"))
    
    def set_current_user(self, user):
        """تعيين المستخدم الحالي"""
        self.current_user = user
        if user:
            username = user.full_name or user.username
            self.user_label.setText(f"👤 {username}")
    
    def update_sync_status(self, status: str, pending_count: int = 0):
        """تحديث حالة المزامنة"""
        self.sync_indicator.update_status(status, pending_count)
    
    def update_sync_progress(self, current: int, total: int):
        """تحديث تقدم المزامنة"""
        self.sync_indicator.update_progress(current, total)
    
    def show_notification(self, title: str, message: str, duration: int = 3000):
        """عرض إشعار منبثق"""
        notification = ToastNotification(title, message, duration, self)
        notification.show_notification()
        self.notifications.append(notification)
        
        # تنظيف الإشعارات القديمة
        self.notifications = [n for n in self.notifications if n.isVisible()]
    
    def get_sync_indicator(self) -> SyncIndicator:
        """الحصول على مؤشر المزامنة"""
        return self.sync_indicator