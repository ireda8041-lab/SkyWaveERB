# الملف: ui/custom_spinbox.py
# SpinBox مخصص مع علامات + و -

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget


class CustomSpinBox(QWidget):
    """
    SpinBox مخصص مع أزرار + و - عمودية
    """
    valueChanged = pyqtSignal(float)

    def __init__(self, parent=None, decimals=2, minimum=0.0, maximum=999999999.99):
        super().__init__(parent)

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

        # منع التحديد التلقائي عند الكتابة
        self.spinbox.lineEdit().setSelection(0, 0)
        self.spinbox.lineEdit().deselect()

        # إنشاء Layout عمودي للأزرار
        buttons_layout = QVBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(1)

        # إنشاء أزرار + و -
        self.btn_plus = QPushButton("+")
        self.btn_minus = QPushButton("−")

        # تنسيق الأزرار - أفقية بجانب بعض
        button_style_plus = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(16, 185, 129, 0.5),
                    stop:1 rgba(16, 185, 129, 0.3));
                border: 1px solid rgba(16, 185, 129, 0.7);
                border-radius: 2px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                color: #F8FAFC;
                font-size: 10px;
                font-weight: bold;
                min-width: 16px;
                max-width: 16px;
                min-height: 11px;
                max-height: 11px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background: rgba(16, 185, 129, 0.7);
            }
            QPushButton:pressed {
                background: rgba(16, 185, 129, 0.9);
            }
        """
        
        button_style_minus = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(239, 68, 68, 0.5),
                    stop:1 rgba(239, 68, 68, 0.3));
                border: 1px solid rgba(239, 68, 68, 0.7);
                border-radius: 2px;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                color: #F8FAFC;
                font-size: 10px;
                font-weight: bold;
                min-width: 16px;
                max-width: 16px;
                min-height: 11px;
                max-height: 11px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.7);
            }
            QPushButton:pressed {
                background: rgba(239, 68, 68, 0.9);
            }
        """

        self.btn_plus.setStyleSheet(button_style_plus)
        self.btn_minus.setStyleSheet(button_style_minus)

        # تنسيق SpinBox - مصغر ومتناسق
        spinbox_style = """
            QDoubleSpinBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0A2A55,
                    stop:1 #052045);
                border: 1px solid #374151;
                border-radius: 3px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                padding: 2px 4px;
                min-height: 22px;
                max-height: 24px;
                color: #F8FAFC;
                font-size: 11px;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #0A6CF1;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0A2A55,
                    stop:1 #0A6CF1);
            }
        """
        self.spinbox.setStyleSheet(spinbox_style)

        # إضافة الأزرار للـ Layout العمودي
        buttons_layout.addWidget(self.btn_plus)
        buttons_layout.addWidget(self.btn_minus)

        # إضافة العناصر للـ Layout الرئيسي
        main_layout.addWidget(self.spinbox)
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
