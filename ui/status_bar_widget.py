# الملف: ui/status_bar_widget.py
"""
شريط الحالة مع مؤشر المزامنة والإشعارات
"""

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTime, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.styles import COLORS, get_cairo_font
from version import CURRENT_VERSION

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class SyncButton(QWidget):
    """
    زرار مزامنة احترافي مصغّر مع مؤشر حالة
    """

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = "idle"  # idle, syncing, success, error, offline
        self._progress = 0
        self._animation_timer = None
        self._animation_frame = 0
        self.init_ui()

    def init_ui(self):
        """إنشاء واجهة الزرار"""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)  # ⚡ إضافة margin سفلي لرفع الزرار للمنتصف
        layout.setSpacing(0)

        # الزرار الرئيسي - مصغّر
        self.button = QPushButton()
        self.button.setFont(get_cairo_font(9))
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setFixedHeight(26)
        self.button.setFixedWidth(85)
        self.button.clicked.connect(self._on_click)
        layout.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignVCenter)

        # تحديث المظهر
        self._update_appearance()

        # مؤقت للأنيميشن
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate)

    def _on_click(self):
        """معالج النقر"""
        if self._status not in ("syncing",):
            self.clicked.emit()

    def _update_appearance(self):
        """تحديث مظهر الزرار حسب الحالة"""
        base_style = """
            QPushButton {{
                background: {bg};
                color: white;
                border: none;
                border-radius: 13px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background: {hover};
            }}
            QPushButton:pressed {{
                background: {pressed};
            }}
        """

        if self._status == "idle":
            self.button.setText("☁ مزامنة")
            self.button.setStyleSheet(
                base_style.format(
                    bg="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A6CF1, stop:1 #0550B8)",
                    hover="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1E7EFF, stop:1 #0A6CF1)",
                    pressed="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0550B8, stop:1 #043D8C)",
                )
            )
            self.button.setEnabled(True)

        elif self._status == "syncing":
            frames = ["◐", "◓", "◑", "◒"]
            icon = frames[self._animation_frame % len(frames)]
            self.button.setText(f"{icon} جاري...")
            self.button.setStyleSheet(
                base_style.format(
                    bg="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F59E0B, stop:1 #D97706)",
                    hover="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F59E0B, stop:1 #D97706)",
                    pressed="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #D97706, stop:1 #B45309)",
                )
            )
            self.button.setEnabled(False)

        elif self._status == "success":
            self.button.setText("✓ تم")
            self.button.setStyleSheet(
                base_style.format(
                    bg="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #10B981, stop:1 #059669)",
                    hover="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #34D399, stop:1 #10B981)",
                    pressed="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #059669, stop:1 #047857)",
                )
            )
            self.button.setEnabled(True)

        elif self._status == "error":
            self.button.setText("✗ فشل")
            self.button.setStyleSheet(
                base_style.format(
                    bg="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #EF4444, stop:1 #DC2626)",
                    hover="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F87171, stop:1 #EF4444)",
                    pressed="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #DC2626, stop:1 #B91C1C)",
                )
            )
            self.button.setEnabled(True)

        elif self._status == "offline":
            self.button.setText("◌ غير متصل")
            self.button.setStyleSheet(
                base_style.format(
                    bg="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6B7280, stop:1 #4B5563)",
                    hover="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9CA3AF, stop:1 #6B7280)",
                    pressed="qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4B5563, stop:1 #374151)",
                )
            )
            self.button.setEnabled(True)

    def _animate(self):
        """تحريك الأيقونة أثناء المزامنة"""
        self._animation_frame += 1
        self._update_appearance()

    def set_status(self, status: str):
        """تعيين حالة الزرار"""
        self._status = status

        if status == "syncing":
            self._animation_frame = 0
            self._animation_timer.start(200)
        else:
            self._animation_timer.stop()

            if status == "success":
                QTimer.singleShot(
                    2000, lambda: self.set_status("idle") if self._status == "success" else None
                )
            elif status == "error":
                QTimer.singleShot(
                    3000, lambda: self.set_status("idle") if self._status == "error" else None
                )

        self._update_appearance()

    def set_progress(self, current: int, total: int):
        """تحديث التقدم"""
        try:
            current = int(current)
            total = int(total)
            if total > 0:
                self._progress = int((current / total) * 100)
                if self._status == "syncing":
                    self.button.setText(f"◐ {self._progress}%")
        except (ValueError, TypeError):
            pass


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
        self.status_text.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent; border: none;"
        )
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
        """تحديث التقدم"""
        try:
            current = int(current)
            total = int(total)
            if total > 0:
                percent = int((current / total) * 100)
                self.status_text.setText(f"مزامنة {percent}%")
        except (ValueError, TypeError):
            pass


class ToastNotification(QWidget):
    """إشعار منبثق (Toast)"""

    DEFAULT_DURATION_MS = 9000
    MIN_DURATION_MS = 8000

    def __init__(self, title: str, message: str, duration: int = DEFAULT_DURATION_MS, parent=None):
        super().__init__(parent)
        try:
            duration_ms = int(duration)
        except (TypeError, ValueError):
            duration_ms = self.DEFAULT_DURATION_MS
        if duration_ms <= 0:
            duration_ms = self.DEFAULT_DURATION_MS
        self.duration = max(self.MIN_DURATION_MS, duration_ms)
        self.init_ui(title, message)
        self.setup_animation()

    def init_ui(self, title: str, message: str):
        """إنشاء واجهة الإشعار"""

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # الحاوية الرئيسية
        main_frame = QFrame()
        main_frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLORS["bg_medium"]};
                border-radius: 8px;
                border: 1px solid {COLORS["border"]};
            }}
        """
        )

        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # العنوان
        title_label = QLabel(title)
        title_label.setFont(get_cairo_font(10, bold=True))
        title_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; background-color: transparent;"
        )
        layout.addWidget(title_label)

        # الرسالة
        message_label = QLabel(message)
        message_label.setFont(get_cairo_font(9))
        message_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background-color: transparent;"
        )
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
    DEFAULT_NOTIFICATION_DURATION_MS = 9000
    MIN_NOTIFICATION_DURATION_MS = 8000

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

        # 1. LEFT SIDE - مؤشر المزامنة وزرار المزامنة الجديد
        self.sync_indicator = SyncIndicator()
        layout.addWidget(self.sync_indicator)

        # زرار المزامنة الاحترافي الجديد
        self.sync_button = SyncButton()
        self.sync_button.clicked.connect(self._on_sync_clicked)
        self.sync_button.setToolTip("مزامنة البيانات مع السيرفر (Ctrl+Shift+S)")
        layout.addWidget(self.sync_button)

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
        self.user_label.setStyleSheet(
            f"""
            color: {COLORS["primary"]};
            background-color: transparent;
            padding: 2px 6px;
        """
        )
        user_layout.addWidget(self.user_label)

        user_container.setStyleSheet(
            """
            QWidget {
                background-color: transparent;
                border: none;
            }
        """
        )
        layout.addWidget(user_container)

        # الوقت الحالي
        self.time_label = QLabel()
        self.time_label.setFont(get_cairo_font(12, bold=True))
        self.time_label.setStyleSheet(
            f"""
            color: {COLORS["text_primary"]};
            background-color: transparent;
        """
        )
        layout.addWidget(self.time_label)

        # تحديث الوقت كل ثانية
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        self.update_time()

        # 4. SPACER
        layout.addStretch()

        # 6. معلومات النظام

        self.system_info = QLabel(f"Sky Wave ERP v{CURRENT_VERSION}")
        self.system_info.setFont(get_cairo_font(9))
        self.system_info.setStyleSheet(
            f"""
            color: {COLORS["text_secondary"]};
            background-color: transparent;
        """
        )
        layout.addWidget(self.system_info)

        self.setLayout(layout)

    def _create_separator(self):
        """إنشاء فاصل احترافي"""

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFixedHeight(18)
        separator.setStyleSheet(
            f"""
            QFrame {{
                color: {COLORS["border"]};
                background-color: rgba(255, 255, 255, 0.1);
                max-width: 1px;
            }}
        """
        )
        return separator

    def update_time(self):
        """تحديث الوقت بصيغة 12 ساعة مع AM/PM"""
        try:
            current_time = QTime.currentTime()
            if self.time_label and not self.time_label.isHidden():
                self.time_label.setText(current_time.toString("hh:mm:ss AP"))
        except (RuntimeError, AttributeError):
            # الويدجت تم حذفه أو البرنامج بيقفل
            if hasattr(self, "time_timer") and self.time_timer:
                self.time_timer.stop()
        except Exception:
            pass  # تجاهل أي أخطاء أخرى

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """إيقاف الـ timer عند إغلاق الويدجت"""
        try:
            if hasattr(self, "time_timer") and self.time_timer:
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
        if hasattr(self, "sync_indicator"):
            self.sync_indicator.update_status(status, pending_count)

        # تحديث حالة زرار المزامنة الجديد
        if hasattr(self, "sync_button"):
            if status == "syncing":
                self.sync_button.set_status("syncing")
            elif status == "synced":
                self.sync_button.set_status("success")
            elif status == "error":
                self.sync_button.set_status("error")
            elif status == "offline":
                self.sync_button.set_status("offline")
            else:
                self.sync_button.set_status("idle")

    def update_sync_progress(self, current: int, total: int):
        """تحديث تقدم المزامنة"""
        self.update_progress(current, total)

    def update_progress(self, current, total):
        """
        Safe update progress method
        Rewritten to safely cast inputs and avoid crashes
        """
        try:
            # 1. Safe Cast
            current_int = int(current) if current is not None else 0
            total_int = int(total) if total is not None else 0

            # 2. Update Sync Button (if exists)
            if hasattr(self, "sync_button"):
                # Handle both set_progress (existing) and update_progress (requested)
                if hasattr(self.sync_button, "set_progress"):
                    self.sync_button.set_progress(current_int, total_int)
                elif hasattr(self.sync_button, "update_progress"):
                    self.sync_button.update_progress(current_int, total_int)

            # Update Sync Indicator (Preserve existing functionality)
            if hasattr(self, "sync_indicator"):
                self.sync_indicator.update_progress(current_int, total_int)

            # 3. Calculate Percentage safely
            if total_int > 0:
                percentage = int((current_int / total_int) * 100)
            else:
                percentage = 0

            # 4. Update UI Elements
            if hasattr(self, "progress_bar"):
                self.progress_bar.setValue(percentage)
                self.progress_bar.setVisible(total_int > 0)

        except Exception:
            # Silent fail to prevent crash loop
            pass

    def _on_sync_clicked(self):
        """معالج النقر على زرار المزامنة"""
        safe_print("INFO: [StatusBar] تم النقر على زرار المزامنة")
        self.full_sync_requested.emit()

    def set_realtime_sync_status(self, is_active: bool):
        """تحديث حالة المزامنة الفورية"""
        try:
            if is_active:
                # إضافة مؤشر المزامنة الفورية
                if not hasattr(self, "realtime_indicator"):
                    self.realtime_indicator = QLabel("🔄 مزامنة فورية")
                    self.realtime_indicator.setFont(get_cairo_font(10))
                    self.realtime_indicator.setStyleSheet(
                        """
                        QLabel {
                            color: #10B981;
                            background: rgba(16, 185, 129, 0.1);
                            border: 1px solid rgba(16, 185, 129, 0.3);
                            border-radius: 12px;
                            padding: 4px 8px;
                            font-weight: bold;
                        }
                    """
                    )
                    self.realtime_indicator.setToolTip(
                        "المزامنة الفورية نشطة - التحديثات تظهر فوراً على جميع الأجهزة"
                    )

                    # إضافة المؤشر بجانب مؤشر المزامنة العادي
                    layout = self.layout()
                    layout.insertWidget(2, self.realtime_indicator)

                self.realtime_indicator.setVisible(True)
            else:
                # إخفاء مؤشر المزامنة الفورية
                if hasattr(self, "realtime_indicator"):
                    self.realtime_indicator.setVisible(False)
        except Exception as e:
            safe_print(f"ERROR: [StatusBarWidget] فشل تحديث مؤشر المزامنة الفورية: {e}")

    def show_notification(
        self,
        title: str,
        message: str,
        duration: int = DEFAULT_NOTIFICATION_DURATION_MS,
    ):
        """عرض إشعار منبثق"""
        try:
            duration_ms = int(duration)
        except (TypeError, ValueError):
            duration_ms = self.DEFAULT_NOTIFICATION_DURATION_MS
        if duration_ms <= 0:
            duration_ms = self.DEFAULT_NOTIFICATION_DURATION_MS
        duration_ms = max(self.MIN_NOTIFICATION_DURATION_MS, duration_ms)
        notification = ToastNotification(title, message, duration_ms, self)
        notification.show_notification()
        self.notifications.append(notification)

        # تنظيف الإشعارات القديمة
        self.notifications = [n for n in self.notifications if n.isVisible()]

    def get_sync_indicator(self):
        """الحصول على مؤشر المزامنة"""
        return self.sync_indicator if hasattr(self, "sync_indicator") else None
