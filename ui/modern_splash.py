# الملف: ui/modern_splash.py
"""
شاشة بداية عصرية وخفيفة
"""

from PyQt6.QtWidgets import QSplashScreen, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QRectF
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor, QLinearGradient, QPen, QPainterPath, QRegion, QBitmap
from core.resource_utils import get_resource_path
import time


class ModernSplash(QSplashScreen):
    """⚡ شاشة بداية عصرية وسريعة"""
    
    def __init__(self):
        # ⚡ إنشاء خلفية بسيطة (داكنة من البداية)
        pixmap = QPixmap(600, 400)
        pixmap.fill(QColor("#0a1929"))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # رسم شكل بزوايا منحنية (curved) باستخدام QPainterPath
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, 600, 400), 40, 40)  # زوايا منحنية جداً
        
        # خلفية متدرجة بسيطة
        gradient = QLinearGradient(0, 0, 0, 400)
        gradient.setColorAt(0, QColor("#0a1929"))
        gradient.setColorAt(1, QColor("#1a2332"))
        painter.fillPath(path, gradient)
        
        # إطار بسيط مع زوايا منحنية (curved)
        painter.setPen(QPen(QColor("#00d4ff"), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        # تحميل اللوجو
        logo_path = get_resource_path("logo.png")
        logo_pixmap = QPixmap(logo_path)
        
        if not logo_pixmap.isNull():
            logo_pixmap = logo_pixmap.scaled(
                180, 180,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (600 - logo_pixmap.width()) // 2
            y = 80
            painter.drawPixmap(x, y, logo_pixmap)
        
        painter.end()
        
        super().__init__(
            pixmap, 
            Qt.WindowType.SplashScreen | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint
        )
        
        # منع الشفافية عشان ما يظهرش أي حاجة بيضاء تحت
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowOpacity(1.0)
        
        # تطبيق mask للزوايا المنحنية على النافذة نفسها
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
        
        self.message_font = QFont("Cairo", 10, QFont.Weight.Bold)
        self.title_font = QFont("Cairo", 16, QFont.Weight.Bold)
        self.current_message = ""
        
        # توسيط الشاشة
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 600) // 2
        y = (screen.height() - 400) // 2
        self.move(x, y)
        
        # Timer لتحديث الشريط باستمرار
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.repaint)
        self.timer.start(50)  # تحديث كل 50ms
        
        self.show()
    
    def show_message(self, message: str):
        """عرض رسالة"""
        self.current_message = message
        self.showMessage(
            message,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#00d4ff")
        )
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
    
    def drawContents(self, painter):
        """رسم المحتويات"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # العنوان
        painter.setFont(self.title_font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            QRect(0, 20, 600, 50),
            Qt.AlignmentFlag.AlignHCenter,
            "Sky Wave ERP"
        )
        
        # الرسالة
        if self.current_message:
            painter.setFont(self.message_font)
            painter.setPen(QColor("#00d4ff"))
            painter.drawText(
                QRect(0, 320, 600, 40),
                Qt.AlignmentFlag.AlignHCenter,
                self.current_message
            )
        
        # شريط تقدم بسيط ثابت (لا يختفي أبداً)
        # رسم خلفية الشريط أولاً
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1e293b"))
        painter.drawRoundedRect(100, 370, 400, 6, 3, 3)
        
        # رسم الشريط المتحرك
        progress_width = int((time.time() * 150) % 400)
        if progress_width < 80:  # منع الاختفاء الكامل
            progress_width = 80
        painter.setBrush(QColor("#00d4ff"))
        painter.drawRoundedRect(100, 370, progress_width, 6, 3, 3)
