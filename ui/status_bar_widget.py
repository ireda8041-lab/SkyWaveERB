# الملف: ui/status_bar_widget.py
"""
شريط الحالة مع مؤشر المزامنة والإشعارات
"""

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.styles import get_cairo_font


class SyncIndicator(QWidget):
    """مؤشر حالة الاتصال - تصميم بسيط ونظيف"""

    sync_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sync_status = "offline"
        self.pending_count = 0
        self._is_syncing = False
        self.init_ui()

    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        from ui.styles import COLORS
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # نقطة الحالة فقط (دائرة صغيرة)
        self.status_dot = QLabel("●")
        self.status_dot.setFont(get_cairo_font(10))
        self.status_dot.setStyleSheet("color: #6B7280; background: transparent; border: none;")
        layout.addWidget(self.status_dot)

        # نص الحالة
        self.status_text = QLabel("غير متصل")
        self.status_text.setFont(get_cairo_font(10))
        self.status_text.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent; border: none;")
        layout.addWidget(self.status_text)
        
        self.setStyleSheet("background: transparent; border: none;")
        self.setMaximumHeight(26)

    def update_status(self, status: str, pending_count: int = 0):
        """تحديث حالة الاتصال"""
        self.sync_status = status
        self.pending_count = pending_count

        if status == "synced":
            self.status_dot.setStyleSheet("color: #10B981; background: transparent; border: none;")
            self.status_text.setText("متصل")
            self.status_text.setStyleSheet("color: #10B981; background: transparent; border: none;")
            self._is_syncing = False

        elif status == "syncing":
            self.status_dot.setStyleSheet("color: #F59E0B; background: transparent; border: none;")
            self.status_text.setText("مزامنة...")
            self.status_text.setStyleSheet("color: #F59E0B; background: transparent; border: none;")
            self._is_syncing = True

        elif status == "offline":
            self.status_dot.setStyleSheet("color: #6B7280; background: transparent; border: none;")
            self.status_text.setText("غير متصل")
            self.status_text.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")
            self._is_syncing = False

        elif status == "error":
            self.status_dot.setStyleSheet("color: #ef4444; background: transparent; border: none;")
            self.status_text.setText("خطأ")
            self.status_text.setStyleSheet("color: #ef4444; background: transparent; border: none;")
            self._is_syncing = False

    def update_progress(self, current: int, total: int):
        """تحديث التقدم - لا شيء حالياً"""
        pass


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
        title_label.setFont(get_cairo_font(10, bold=True))
        title_label.setStyleSheet(f"color: {COLORS['text_primary']}; background-color: transparent;")
        layout.addWidget(title_label)

        # الرسالة
        message_label = QLabel(message)
        message_label.setFont(get_cairo_font(9))
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

    # إشارة تسجيل الخروج
    logout_requested = pyqtSignal()
    # إشارة المزامنة الكاملة
    full_sync_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notifications = []
        self.current_user = None
        self.init_ui()

    def init_ui(self):
        """إنشاء واجهة المستخدم - تصميم احترافي"""
        layout = QHBoxLayout()
        layout.setContentsMargins(20, 4, 20, 4)
        layout.setSpacing(12)

        # التأكد من أن الويدجت مرئي دائمًا
        self.setVisible(True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)

        from ui.styles import COLORS

        # 1. LEFT SIDE - مؤشر المزامنة (احترافي)
        self.sync_indicator = SyncIndicator()
        layout.addWidget(self.sync_indicator)
        
        # زر المزامنة الكاملة
        self.full_sync_btn = QPushButton("🔄 مزامنة")
        self.full_sync_btn.setFixedSize(80, 26)
        self.full_sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.full_sync_btn.setToolTip("مزامنة كاملة مع السيرفر")
        self.full_sync_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                padding: 2px 8px;
                min-height: 26px;
                max-height: 26px;
            }}
            QPushButton:hover {{ background-color: #2563eb; }}
            QPushButton:pressed {{ background-color: #1d4ed8; }}
        """)
        self.full_sync_btn.clicked.connect(self.full_sync_requested.emit)
        layout.addWidget(self.full_sync_btn)

        # 2. SPACER
        layout.addStretch()

        # 3. CENTER - معلومات المستخدم (تصميم نظيف)
        user_container = QWidget()
        user_layout = QHBoxLayout(user_container)
        user_layout.setContentsMargins(8, 2, 8, 2)
        user_layout.setSpacing(7)
        
        # اسم المستخدم بدون أيقونة
        self.user_label = QLabel("مستخدم")
        self.user_label.setFont(get_cairo_font(12, bold=True))
        self.user_label.setStyleSheet(f"""
            color: {COLORS['primary']};
            background-color: transparent;
            padding: 2px 6px;
        """)
        user_layout.addWidget(self.user_label)
        
        user_container.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
                border: none;
            }}
        """)
        layout.addWidget(user_container)

        # الوقت الحالي
        self.time_label = QLabel()
        self.time_label.setFont(get_cairo_font(12, bold=True))
        self.time_label.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            background-color: transparent;
        """)
        layout.addWidget(self.time_label)

        # تحديث الوقت كل ثانية
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        self.update_time()

        # 4. SPACER
        layout.addStretch()

        # 6. معلومات النظام
        from version import CURRENT_VERSION
        self.system_info = QLabel(f"Sky Wave ERP v{CURRENT_VERSION}")
        self.system_info.setFont(get_cairo_font(9))
        self.system_info.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            background-color: transparent;
        """)
        layout.addWidget(self.system_info)

        self.setLayout(layout)
    
    def _create_separator(self):
        """إنشاء فاصل احترافي"""
        from ui.styles import COLORS
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFixedHeight(18)
        separator.setStyleSheet(f"""
            QFrame {{
                color: {COLORS['border']};
                background-color: rgba(255, 255, 255, 0.1);
                max-width: 1px;
            }}
        """)
        return separator

        # ربط زر تسجيل الخروج - معطل لأن الزرار مخفي
        # self.logout_btn.clicked.connect(self.logout_requested.emit)

        # ✅ إعدادات الحجم الثابت
        self.setMinimumHeight(32)
        self.setMaximumHeight(32)
        self.setMinimumWidth(0)  # لا حد أدنى للعرض

        # ✅ سياسة الحجم - ثابت عمودياً، متمدد أفقياً
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        # ✅ منع الإخفاء والحذف
        self.setVisible(True)
        
        # ✅ إزالة الحواف لجعل البار يملأ العرض كاملاً
        self.setContentsMargins(0, 0, 0, 0)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)

        # استخدام الألوان من ملف styles.py - تصميم نظيف بدون borders
        from ui.styles import COLORS
        self.setStyleSheet(f"""
            StatusBarWidget {{
                background-color: {COLORS['bg_dark']};
                border: none;
                min-height: 32px;
                max-height: 32px;
                min-width: 100%;
            }}
            QWidget {{
                background-color: transparent;
                border: none;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
                color: {COLORS['text_secondary']};
                padding: 0px;
                margin: 0px;
            }}
            QFrame {{
                background-color: transparent;
                border: none;
            }}
        """)

        # ✅ التأكد من أن الويدجت مرئي دائماً
        self.setVisible(True)

    def update_time(self):
        """تحديث الوقت بصيغة 12 ساعة مع AM/PM"""
        try:
            from PyQt6.QtCore import QTime
            current_time = QTime.currentTime()
            if self.time_label and not self.time_label.isHidden():
                self.time_label.setText(current_time.toString("hh:mm:ss AP"))
        except (RuntimeError, AttributeError):
            # الويدجت تم حذفه أو البرنامج بيقفل
            if hasattr(self, 'time_timer') and self.time_timer:
                self.time_timer.stop()
        except Exception:
            pass  # تجاهل أي أخطاء أخرى

    def closeEvent(self, event):
        """إيقاف الـ timer عند إغلاق الويدجت"""
        try:
            if hasattr(self, 'time_timer') and self.time_timer:
                self.time_timer.stop()
                self.time_timer.deleteLater()
        except (AttributeError, RuntimeError):
            # Timer غير موجود أو تم حذفه بالفعل
            pass
        super().closeEvent(event)

    def set_current_user(self, user):
        """تعيين المستخدم الحالي"""
        self.current_user = user
        if user:
            username = user.full_name or user.username
            self.user_label.setText(username)

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

    def get_sync_indicator(self) -> "SyncIndicator":
        """الحصول على مؤشر المزامنة"""
        indicator: SyncIndicator = self.sync_indicator
        return indicator
