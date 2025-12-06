# الملف: ui/loading_overlay.py
"""
شاشة التحميل المتراكبة - Loading Overlay
تظهر أثناء تحميل البيانات مع تأثير بصري احترافي
"""

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

from core.resource_utils import get_resource_path


class SpinnerWidget(QWidget):
    """دائرة التحميل المتحركة"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self.angle = 0

        # مؤقت للتحريك
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(50)

    def rotate(self):
        self.angle = (self.angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # رسم الدائرة
        painter.translate(30, 30)
        painter.rotate(self.angle)

        # رسم أقواس متدرجة
        for i in range(8):
            opacity = (i + 1) / 8.0
            color = QColor(77, 166, 255)
            color.setAlphaF(opacity)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(-25, -5, 10, 10)
            painter.rotate(45)

    def stop(self):
        self.timer.stop()


class LoadingOverlay(QWidget):
    """
    شاشة التحميل المتراكبة
    تغطي النافذة بالكامل مع شعار ورسالة تحميل
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loadingOverlay")

        # ✅ جعل الخلفية شفافة تماماً
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)

        # إعداد الشفافية
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self.opacity_effect)

        self.init_ui()
        self.setup_animation()

        print("INFO: [LoadingOverlay] تم إنشاء شاشة التحميل")

    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        # التخطيط الرئيسي
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        # الشعار
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pixmap = QPixmap(get_resource_path("logo.png"))
        if not logo_pixmap.isNull():
            self.logo_label.setPixmap(logo_pixmap.scaled(
                150, 150,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        layout.addWidget(self.logo_label)

        # دائرة التحميل
        self.spinner = SpinnerWidget()
        spinner_container = QWidget()
        spinner_layout = QVBoxLayout(spinner_container)
        spinner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner_layout.addWidget(self.spinner)
        layout.addWidget(spinner_container)

        # رسالة التحميل
        self.message_label = QLabel("جاري تجهيز البيانات...")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setFont(QFont("Segoe UI", 14))
        self.message_label.setStyleSheet("color: #e0e3f0;")
        layout.addWidget(self.message_label)

        # ✅ التنسيق - خلفية شفافة تماماً
        self.setStyleSheet("""
            #loadingOverlay {
                background-color: transparent;
            }
        """)

    def setup_animation(self):
        """إعداد حركة الاختفاء"""
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_animation.finished.connect(self._on_fade_finished)

    def set_message(self, message: str):
        """تغيير رسالة التحميل"""
        self.message_label.setText(message)

    def fade_out(self):
        """بدء حركة الاختفاء"""
        print("INFO: [LoadingOverlay] بدء إخفاء شاشة التحميل...")
        self.fade_animation.start()

    def _on_fade_finished(self):
        """عند انتهاء الاختفاء"""
        self.spinner.stop()
        self.hide()

    def resizeEvent(self, event):
        """تغيير الحجم مع النافذة الأم"""
        super().resizeEvent(event)
        if self.parent():
            # ✅ تغطية الأب فقط (التابات) وليس النافذة الرئيسية
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())

    def showEvent(self, event):
        """عند الظهور"""
        super().showEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())
            self.raise_()  # رفع فوق كل العناصر
        print(f"INFO: [LoadingOverlay] تم عرض شاشة التحميل - الحجم: {self.size()}")
