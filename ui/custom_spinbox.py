# الملف: ui/custom_spinbox.py
# SpinBox مخصص مع علامات + و -

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget


class CustomSpinBox(QWidget):
    """
    SpinBox مخصص مع أزرار + و - عمودية
    الأزرار على اليمين والقيمة على اليسار (للعربية)
    """
    valueChanged = pyqtSignal(float)

    def __init__(self, parent=None, decimals=2, minimum=0.0, maximum=999999999.99):
        super().__init__(parent)

        # ⚡ إجبار الـ widget على LTR لضمان ترتيب ثابت
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        # إنشاء Layout أفقي رئيسي
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # إنشاء SpinBox بدون أزرار
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setDecimals(decimals)
        self.spinbox.setMinimum(minimum)
        self.spinbox.setMaximum(maximum)
        self.spinbox.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.spinbox.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.spinbox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # ⚡ إجبار الـ SpinBox على LTR
        self.spinbox.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        # منع التحديد التلقائي عند الكتابة
        self.spinbox.lineEdit().setSelection(0, 0)
        self.spinbox.lineEdit().deselect()

        # إنشاء Layout عمودي للأزرار
        buttons_layout = QVBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(0)

        # إنشاء أزرار الأسهم (فوق وتحت)
        self.btn_plus = QPushButton("▲")
        self.btn_minus = QPushButton("▼")

        # تنسيق الأزرار - أسهم فوق وتحت
        button_style_up = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e3a5f,
                    stop:1 #0f2744);
                border: 1px solid #374151;
                border-radius: 0px;
                border-top-right-radius: 3px;
                color: #94a3b8;
                font-size: 7px;
                font-weight: normal;
                min-width: 18px;
                max-width: 18px;
                min-height: 12px;
                max-height: 12px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background: #0A6CF1;
                color: white;
            }
            QPushButton:pressed {
                background: #0958d9;
            }
        """

        button_style_down = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e3a5f,
                    stop:1 #0f2744);
                border: 1px solid #374151;
                border-top: none;
                border-radius: 0px;
                border-bottom-right-radius: 3px;
                color: #94a3b8;
                font-size: 7px;
                font-weight: normal;
                min-width: 18px;
                max-width: 18px;
                min-height: 12px;
                max-height: 12px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background: #0A6CF1;
                color: white;
            }
            QPushButton:pressed {
                background: #0958d9;
            }
        """

        self.btn_plus.setStyleSheet(button_style_up)
        self.btn_minus.setStyleSheet(button_style_down)

        # تنسيق SpinBox - مع عرض كافي للقيمة
        spinbox_style = """
            QDoubleSpinBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0A2A55,
                    stop:1 #052045);
                border: 1px solid #374151;
                border-radius: 3px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-right: none;
                padding: 4px 6px;
                min-height: 24px;
                min-width: 80px;
                color: #F8FAFC;
                font-size: 12px;
                font-weight: normal;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #0A6CF1;
                border-right: none;
            }
        """
        self.spinbox.setStyleSheet(spinbox_style)

        # إضافة الأزرار للـ Layout العمودي
        buttons_layout.addWidget(self.btn_plus)
        buttons_layout.addWidget(self.btn_minus)

        # ⚡ ترتيب: SpinBox أولاً ثم الأزرار (LTR)
        main_layout.addWidget(self.spinbox, 1)  # stretch=1 للتمدد
        main_layout.addLayout(buttons_layout)

        # ربط الإشارات
        self.btn_plus.clicked.connect(self._increment)
        self.btn_minus.clicked.connect(self._decrement)
        self.spinbox.valueChanged.connect(self.valueChanged.emit)

    def _increment(self):
        """زيادة القيمة"""
        self.spinbox.stepUp()
        # إلغاء أي تحديد بعد الزيادة
        self.spinbox.lineEdit().deselect()

    def _decrement(self):
        """تقليل القيمة"""
        self.spinbox.stepDown()
        # إلغاء أي تحديد بعد النقصان
        self.spinbox.lineEdit().deselect()

    def value(self):
        """الحصول على القيمة"""
        return self.spinbox.value()

    def setValue(self, value):
        """تعيين القيمة"""
        self.spinbox.setValue(value)
        # إلغاء أي تحديد بعد التعيين
        self.spinbox.lineEdit().deselect()

    def setDecimals(self, decimals):
        """تعيين عدد الخانات العشرية"""
        self.spinbox.setDecimals(decimals)

    def setMinimum(self, minimum):
        """تعيين الحد الأدنى"""
        self.spinbox.setMinimum(minimum)

    def setMaximum(self, maximum):
        """تعيين الحد الأقصى"""
        self.spinbox.setMaximum(maximum)

    def setSingleStep(self, step):
        """تعيين خطوة الزيادة/النقصان"""
        self.spinbox.setSingleStep(step)

    def setSuffix(self, suffix):
        """تعيين لاحقة النص (مثل %)"""
        self.spinbox.setSuffix(suffix)

    def setPrefix(self, prefix):
        """تعيين بادئة النص"""
        self.spinbox.setPrefix(prefix)

    def focusInEvent(self, event):
        """عند التركيز - نمرر التركيز للـ SpinBox"""
        super().focusInEvent(event)
        self.spinbox.setFocus()
        # إلغاء أي تحديد
        self.spinbox.lineEdit().deselect()
