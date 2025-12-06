# الملف: ui/custom_widgets.py
# Widgets مخصصة مع أسهم حقيقية

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QCompleter, QDateEdit, QDoubleSpinBox


class ArrowComboBox(QComboBox):
    """
    ComboBox مع سهم Unicode حقيقي
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(15)

        # إضافة السهم كـ suffix في الـ LineEdit
        self._setup_arrow()

    def _setup_arrow(self):
        """إعداد السهم"""
        # استخدام stylesheet مع padding للسهم
        self.setStyleSheet("""
            QComboBox {
                background-color: #0F1419;
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 6px 25px 6px 10px;
                min-height: 28px;
                color: #F8FAFC;
                font-size: 13px;
            }
            QComboBox:focus {
                border: 1px solid #0A6CF1;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;
            }
            QComboBox QAbstractItemView {
                background-color: #0F1419;
                color: #F8FAFC;
                selection-background-color: #0A6CF1;
                border: 1px solid #374151;
            }
        """)

    def paintEvent(self, event):
        """رسم السهم يدوياً"""
        super().paintEvent(event)

        # رسم السهم باستخدام QPainter
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # حساب موقع السهم
        arrow_x = self.width() - 18
        arrow_y = self.height() // 2

        # رسم السهم
        painter.setPen(QPen(QColor("#F8FAFC"), 2))
        painter.setBrush(QColor("#F8FAFC"))

        # مثلث السهم
        points = QPolygon([
            QPoint(arrow_x - 4, arrow_y - 2),
            QPoint(arrow_x + 4, arrow_y - 2),
            QPoint(arrow_x, arrow_y + 3)
        ])
        painter.drawPolygon(points)
        painter.end()

    def mousePressEvent(self, event):
        """فتح القائمة عند الضغط"""
        super().mousePressEvent(event)
        if not self.view().isVisible():
            self.showPopup()

    def setup_completer(self, items_list):
        """إعداد البحث السريع"""
        if not items_list:
            return
        completer = QCompleter(items_list, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)


class ArrowSpinBox(QDoubleSpinBox):
    """
    SpinBox مع أسهم Unicode حقيقية
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()

    def _setup_style(self):
        self.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #0F1419;
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 6px 22px 6px 10px;
                min-height: 28px;
                color: #F8FAFC;
                font-size: 13px;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #0A6CF1;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 18px;
                background: transparent;
                border: none;
            }
            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {
                image: none;
            }
        """)

    def paintEvent(self, event):
        """رسم الأسهم يدوياً"""
        super().paintEvent(event)

        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        arrow_x = self.width() - 12
        mid_y = self.height() // 2

        painter.setPen(QPen(QColor("#F8FAFC"), 1.5))
        painter.setBrush(QColor("#F8FAFC"))

        # سهم لأعلى
        up_points = QPolygon([
            QPoint(arrow_x - 3, mid_y - 3),
            QPoint(arrow_x + 3, mid_y - 3),
            QPoint(arrow_x, mid_y - 7)
        ])
        painter.drawPolygon(up_points)

        # سهم لأسفل
        down_points = QPolygon([
            QPoint(arrow_x - 3, mid_y + 3),
            QPoint(arrow_x + 3, mid_y + 3),
            QPoint(arrow_x, mid_y + 7)
        ])
        painter.drawPolygon(down_points)
        painter.end()


class ArrowDateEdit(QDateEdit):
    """
    DateEdit مع سهم Unicode حقيقي
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCalendarPopup(True)
        self._setup_style()

    def _setup_style(self):
        self.setStyleSheet("""
            QDateEdit {
                background-color: #0F1419;
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 6px 25px 6px 10px;
                min-height: 28px;
                color: #F8FAFC;
                font-size: 13px;
            }
            QDateEdit:focus {
                border: 1px solid #0A6CF1;
            }
            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
                background: transparent;
            }
            QDateEdit::down-arrow {
                image: none;
            }
        """)

    def paintEvent(self, event):
        """رسم السهم يدوياً"""
        super().paintEvent(event)

        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        arrow_x = self.width() - 18
        arrow_y = self.height() // 2

        painter.setPen(QPen(QColor("#F8FAFC"), 2))
        painter.setBrush(QColor("#F8FAFC"))

        points = QPolygon([
            QPoint(arrow_x - 4, arrow_y - 2),
            QPoint(arrow_x + 4, arrow_y - 2),
            QPoint(arrow_x, arrow_y + 3)
        ])
        painter.drawPolygon(points)
        painter.end()
