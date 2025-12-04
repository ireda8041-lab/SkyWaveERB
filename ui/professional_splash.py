# الملف: ui/professional_splash.py
"""
شاشة البداية الاحترافية مع رسائل التحميل
"""

from PyQt6.QtWidgets import QSplashScreen, QLabel, QVBoxLayout, QWidget, QProgressBar
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor, QLinearGradient, QPainterPath, QRegion, QBitmap
from core.resource_utils import get_resource_path


class ProfessionalSplash(QSplashScreen):
    """شاشة بداية احترافية مع لوجو ورسائل تحميل"""
    
    def __init__(self):
        # إنشاء خلفية متدرجة احترافية
        pixmap = QPixmap(800, 500)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # رسم شكل بزوايا منحنية (curved) باستخدام QPainterPath
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, 800, 500), 40, 40)  # زوايا منحنية جداً
        
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
        
        # تحميل ورسم اللوجو
        logo_path = get_resource_path("logo.png")
        logo_pixmap = QPixmap(logo_path)
        
        if not logo_pixmap.isNull():
            # تكبير اللوجو
            logo_pixmap = logo_pixmap.scaled(
                250, 250,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # رسم اللوجو في المنتصف
            x = (800 - logo_pixmap.width()) // 2
            y = 100
            painter.drawPixmap(x, y, logo_pixmap)
        
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
        self.message_font = QFont("Cairo", 12, QFont.Weight.Bold)
        self.title_font = QFont("Cairo", 22, QFont.Weight.Bold)
        self.version_font = QFont("Cairo", 11)
        
        self.current_message = "جاري التحميل..."
        
        # عرض الشاشة مع شفافية
        self.setWindowOpacity(1.0)
        
        # توسيط الشاشة
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 800) // 2
        y = (screen.height() - 500) // 2
        self.move(x, y)
        
        # Timer لتحديث الشريط باستمرار
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.repaint)
        self.timer.start(50)  # تحديث كل 50ms
        
        self.show()
        self.raise_()  # رفع فوق كل النوافذ
    
    def show_message(self, message: str):
        """عرض رسالة تحميل"""
        self.current_message = message
        self.showMessage(
            message,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#00d4ff")
        )
        self.repaint()
        
        # معالجة الأحداث لضمان التحديث الفوري
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
        
        # رسم رقم الإصدار
        try:
            from version import CURRENT_VERSION
            version_text = f"الإصدار {CURRENT_VERSION}"
        except (ImportError, AttributeError):
            version_text = "v1.0.3"
        
        painter.setFont(self.version_font)
        painter.setPen(QColor("#b0b0b0"))
        
        version_rect = self.rect()
        version_rect.setTop(70)
        version_rect.setBottom(95)
        painter.drawText(
            version_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            version_text
        )
        
        # رسم الرسالة في الأسفل
        painter.setFont(self.message_font)
        painter.setPen(QColor("#00d4ff"))
        
        text_rect = self.rect()
        text_rect.setTop(text_rect.height() - 100)
        text_rect.setBottom(text_rect.height() - 60)
        
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            self.current_message
        )
        
        # رسم شريط تقدم بسيط (متحرك - لا يختفي أبداً)
        progress_rect = self.rect()
        progress_rect.setTop(progress_rect.height() - 50)
        progress_rect.setBottom(progress_rect.height() - 42)
        progress_rect.setLeft(200)
        progress_rect.setRight(600)
        
        # خلفية شريط التقدم (دائماً ظاهرة)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#003366"))
        painter.drawRoundedRect(progress_rect, 4, 4)
        
        # شريط التقدم المتحرك (نبضة - لا يختفي)
        import time
        pulse = int((time.time() * 150) % 400)
        if pulse < 100:  # منع الاختفاء الكامل
            pulse = 100
        
        progress_fill = progress_rect.adjusted(0, 0, 0, 0)
        progress_fill.setRight(progress_fill.left() + pulse)
        
        # تدرج لوني للشريط
        from PyQt6.QtGui import QLinearGradient
        progress_gradient = QLinearGradient(progress_fill.left(), 0, progress_fill.right(), 0)
        progress_gradient.setColorAt(0, QColor("#0088cc"))
        progress_gradient.setColorAt(1, QColor("#00d4ff"))
        
        painter.setBrush(progress_gradient)
        painter.drawRoundedRect(progress_fill, 4, 4)
