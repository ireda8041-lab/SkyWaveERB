# الملف: ui/professional_splash.py
"""
شاشة البداية الاحترافية مع لوجو ودائرة تحميل
"""

import time

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBitmap,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
)
from PyQt6.QtWidgets import QSplashScreen

from core.resource_utils import get_resource_path


class ProfessionalSplash(QSplashScreen):
    """شاشة بداية احترافية مع لوجو ودائرة تحميل"""

    def __init__(self):
        # إنشاء خلفية متدرجة احترافية
        pixmap = QPixmap(800, 500)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # رسم شكل بزوايا منحنية (curved) باستخدام QPainterPath
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, 800, 500), 40, 40)

        # رسم خلفية متدرجة
        gradient = QLinearGradient(0, 0, 0, 500)
        gradient.setColorAt(0, QColor("#001a3a"))
        gradient.setColorAt(0.3, QColor("#002855"))
        gradient.setColorAt(0.7, QColor("#003366"))
        gradient.setColorAt(1, QColor("#001a3a"))
        painter.fillPath(path, gradient)

        # رسم إطار خارجي مزدوج (curved)
        painter.setPen(QColor("#00d4ff"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inner_path = QPainterPath()
        inner_path.addRoundedRect(QRectF(8, 8, 784, 484), 40, 40)
        painter.drawPath(inner_path)

        painter.setPen(QColor("#0088cc"))
        inner_path2 = QPainterPath()
        inner_path2.addRoundedRect(QRectF(12, 12, 776, 476), 38, 38)
        painter.drawPath(inner_path2)

        painter.end()

        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)

        # تطبيق mask للزوايا المنحنية على النافذة نفسها
        mask = QBitmap(800, 500)
        mask.fill(Qt.GlobalColor.color0)
        mask_painter = QPainter(mask)
        mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        mask_painter.setBrush(Qt.GlobalColor.color1)
        mask_painter.setPen(Qt.PenStyle.NoPen)
        mask_path = QPainterPath()
        mask_path.addRoundedRect(QRectF(0, 0, 800, 500), 40, 40)
        mask_painter.drawPath(mask_path)
        mask_painter.end()
        self.setMask(QRegion(mask))

        # إعداد الخطوط
        self.title_font = QFont("Cairo", 22, QFont.Weight.Bold)
        self.percent_font = QFont("Cairo", 14, QFont.Weight.Bold)

        # متغيرات التحميل
        self.progress = 0
        self.start_time = time.time()

        # تحميل اللوجو
        logo_path = get_resource_path("logo.png")
        self.logo_pixmap = QPixmap(logo_path)
        if not self.logo_pixmap.isNull():
            self.logo_pixmap = self.logo_pixmap.scaled(
                280, 280,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

        # عرض الشاشة مع شفافية
        self.setWindowOpacity(1.0)

        # توسيط الشاشة
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 800) // 2
        y = (screen.height() - 500) // 2
        self.move(x, y)

        # Timer لتحديث الدائرة باستمرار
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.repaint)
        self.timer.start(30)  # تحديث كل 30ms للسلاسة

        self.show()
        self.raise_()

    def show_message(self, message: str):
        """تحديث نسبة التحميل"""
        # زيادة النسبة تدريجياً
        self.progress = min(self.progress + 15, 95)
        self.repaint()

        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

    def drawContents(self, painter):
        """رسم محتويات الشاشة"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # رسم اسم البرنامج في الأعلى
        painter.setFont(self.title_font)
        painter.setPen(QColor("#ffffff"))

        title_rect = self.rect()
        title_rect.setTop(30)
        title_rect.setBottom(70)
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "Sky Wave ERP"
        )

        # رسم اللوجو في المنتصف
        if not self.logo_pixmap.isNull():
            x = (800 - self.logo_pixmap.width()) // 2
            y = (500 - self.logo_pixmap.height()) // 2 - 20
            painter.drawPixmap(x, y, self.logo_pixmap)

        # رسم دائرة التحميل في الأسفل
        center_x = 400
        center_y = 420
        radius = 30

        # خلفية الدائرة
        pen = QPen(QColor("#003366"))
        pen.setWidth(6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        # دائرة التحميل المتحركة
        elapsed = time.time() - self.start_time
        start_angle = int(elapsed * 300) % 360  # دوران مستمر

        # تدرج لوني للدائرة
        pen = QPen(QColor("#00d4ff"))
        pen.setWidth(6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        # رسم قوس متحرك
        arc_rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.drawArc(arc_rect, start_angle * 16, 270 * 16)

        # رسم نسبة التحميل بجانب الدائرة
        painter.setFont(self.percent_font)
        painter.setPen(QColor("#00d4ff"))
        painter.drawText(
            center_x + radius + 15, center_y + 6,
            f"{self.progress}%"
        )
