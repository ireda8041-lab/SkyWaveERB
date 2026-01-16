# الملف: ui/modern_splash.py
"""
شاشة بداية عصرية وخفيفة
"""

import time

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBitmap,
    QColor,
    QConicalGradient,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
)
from PyQt6.QtWidgets import QSplashScreen

from core.resource_utils import get_resource_path
from ui.styles import get_cairo_font


class ModernSplash(QSplashScreen):
    """شاشة بداية عصرية مع دائرة تحميل"""

    def __init__(self):
        # إنشاء خلفية
        pixmap = QPixmap(600, 400)
        pixmap.fill(QColor("#0a1929"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # رسم شكل بزوايا منحنية
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, 600, 400), 40, 40)

        # خلفية متدرجة
        gradient = QLinearGradient(0, 0, 0, 400)
        gradient.setColorAt(0, QColor("#0a1929"))
        gradient.setColorAt(1, QColor("#1a2332"))
        painter.fillPath(path, gradient)

        # إطار مع زوايا منحنية
        painter.setPen(QPen(QColor("#00d4ff"), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.end()

        super().__init__(
            pixmap,
            Qt.WindowType.SplashScreen |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowOpacity(1.0)

        # تطبيق mask للزوايا المنحنية
        mask = QBitmap(600, 400)
        mask.fill(Qt.GlobalColor.color0)
        mask_painter = QPainter(mask)
        mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        mask_painter.setBrush(Qt.GlobalColor.color1)
        mask_painter.setPen(Qt.PenStyle.NoPen)
        mask_path = QPainterPath()
        mask_path.addRoundedRect(QRectF(0, 0, 600, 400), 40, 40)
        mask_painter.drawPath(mask_path)
        mask_painter.end()
        self.setMask(QRegion(mask))

        self.title_font = get_cairo_font(16, bold=True)
        self.start_time = time.time()

        # تحميل اللوجو
        logo_path = get_resource_path("logo.png")
        self.logo_pixmap = QPixmap(logo_path)
        if not self.logo_pixmap.isNull():
            self.logo_pixmap = self.logo_pixmap.scaled(
                180, 180,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

        # توسيط الشاشة
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 600) // 2
        y = (screen.height() - 400) // 2
        self.move(x, y)

        # Timer لتحديث الدائرة - محسّن للأداء
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.repaint)
        self.timer.start(50)  # ⚡ 50ms بدلاً من 30ms للأداء

        self.show()

    def show_message(self, message: str):
        """تحديث الشاشة - محسّن للسرعة"""
        # ⚡ لا نستخدم processEvents هنا - الرسم يتم تلقائياً
        pass

    def drawContents(self, painter):
        """رسم المحتويات"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # رسم إطار نيون متحرك
        elapsed = time.time() - self.start_time
        self._draw_neon_border(painter, elapsed)

        # العنوان في الأعلى
        painter.setFont(self.title_font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            QRectF(0, 25, 600, 50),
            Qt.AlignmentFlag.AlignHCenter,
            "Sky Wave ERP"
        )

        # اللوجو في المنتصف تماماً
        if not self.logo_pixmap.isNull():
            x = (600 - self.logo_pixmap.width()) // 2
            y = (400 - self.logo_pixmap.height()) // 2 - 10
            painter.drawPixmap(x, y, self.logo_pixmap)

        # دائرة التحميل الديناميكية في الأسفل
        center_x = 300
        center_y = 340
        radius = 25

        # خلفية الدائرة
        pen = QPen(QColor("#1e293b"))
        pen.setWidth(5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        # دائرة التحميل المتحركة
        start_angle = int(elapsed * 300) % 360

        pen = QPen(QColor("#00d4ff"))
        pen.setWidth(5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        arc_rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.drawArc(arc_rect, start_angle * 16, 270 * 16)

    def _draw_neon_border(self, painter, elapsed):
        """رسم إطار نيون متحرك حول الشاشة"""
        # حساب زاوية الدوران (سرعة متوسطة)
        angle = (elapsed * 60) % 360  # 60 درجة في الثانية

        # إنشاء تدرج دائري متحرك
        gradient = QConicalGradient(300, 200, angle)
        gradient.setColorAt(0.0, QColor("#00d4ff"))
        gradient.setColorAt(0.25, QColor("#0088ff"))
        gradient.setColorAt(0.5, QColor("#00d4ff"))
        gradient.setColorAt(0.75, QColor("#00ffff"))
        gradient.setColorAt(1.0, QColor("#00d4ff"))

        # رسم الإطار الخارجي المتوهج (glow effect)
        for i in range(3):
            pen = QPen(gradient, 4 - i)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            offset = i * 2
            path = QPainterPath()
            path.addRoundedRect(QRectF(3 + offset, 3 + offset, 594 - offset * 2, 394 - offset * 2), 38, 38)
            painter.setOpacity(1.0 - i * 0.3)
            painter.drawPath(path)

        painter.setOpacity(1.0)
