# الملف: ui/example_responsive_dialog.py
"""
مثال على استخدام نظام التصميم الموحد لإنشاء نافذة منبثقة متجاوبة
"""

from PyQt6.QtWidgets import (
    QDialog, QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit,
    QCheckBox, QLabel, QMessageBox
)
from PyQt6.QtCore import QDate

from ui.design_system import (
    # Layout Helpers
    ResponsiveLayout, Spacing,
    # Factories
    ButtonFactory, InputFactory, ContainerFactory, DialogFactory,
    # Size Policies
    SizePolicies, ComponentSize,
    # Form Builder
    FormBuilder,
    # Colors & Typography
    Colors, Typography,
    # Responsive Helpers
    ResponsiveScrollArea, get_responsive_value
)


class ExampleResponsiveDialog(QDialog):
    """مثال على نافذة منبثقة متجاوبة باستخدام نظام التصميم"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("🎨 مثال على نظام التصميم المتجاوب")
        
        # إعداد النافذة المتجاوبة
        DialogFactory.setup_responsive_dialog(
            self,
            min_width=500,
            min_height=450,
            screen_ratio=0.6
        )
        
        self._setup_ui()
    
    def _setup_ui(self):
        """إعداد واجهة المستخدم"""
        
        # التخطيط الرئيسي
        main_layout = ResponsiveLayout.create_vbox(spacing=Spacing.NONE)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        # منطقة التمرير
        scroll_area = ResponsiveScrollArea()
        
        # محتوى التمرير
        content = ContainerFactory.create_card()
        content_layout = ResponsiveLayout.create_vbox(spacing=Spacing.LG)
        content.setLayout(content_layout)
        
        # === مجموعة البيانات الأساسية ===
        basic_group = ContainerFactory.create_groupbox("البيانات الأساسية")
        basic_layout = ResponsiveLayout.create_vbox(spacing=Spacing.MD)
        
        # حقل الاسم
        name_row = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        name_row.setContentsMargins(0, 0, 0, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("أدخل الاسم...")
        self.name_input.setStyleSheet(InputFactory.get_input_style())
        self.name_input.setSizePolicy(SizePolicies.expanding_horizontal())
        name_label = QLabel("الاسم:")
        name_label.setStyleSheet(InputFactory.get_label_style())
        name_row.addWidget(self.name_input, 1)
        name_row.addWidget(name_label, 0)
        basic_layout.addLayout(name_row)
        
        # حقل البريد
        email_row = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        email_row.setContentsMargins(0, 0, 0, 0)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("example@domain.com")
        self.email_input.setStyleSheet(InputFactory.get_input_style())
        self.email_input.setSizePolicy(SizePolicies.expanding_horizontal())
        email_label = QLabel("البريد:")
        email_label.setStyleSheet(InputFactory.get_label_style())
        email_row.addWidget(self.email_input, 1)
        email_row.addWidget(email_label, 0)
        basic_layout.addLayout(email_row)
        
        # حقل الفئة
        category_row = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        category_row.setContentsMargins(0, 0, 0, 0)
        self.category_combo = QComboBox()
        self.category_combo.addItems(["اختر الفئة", "فئة أولى", "فئة ثانية", "فئة ثالثة"])
        self.category_combo.setStyleSheet(InputFactory.get_input_style())
        self.category_combo.setSizePolicy(SizePolicies.expanding_horizontal())
        category_label = QLabel("الفئة:")
        category_label.setStyleSheet(InputFactory.get_label_style())
        category_row.addWidget(self.category_combo, 1)
        category_row.addWidget(category_label, 0)
        basic_layout.addLayout(category_row)
        
        basic_group.setLayout(basic_layout)
        content_layout.addWidget(basic_group)

        # === مجموعة التفاصيل ===
        details_group = ContainerFactory.create_groupbox("التفاصيل")
        details_layout = ResponsiveLayout.create_vbox(spacing=Spacing.MD)
        
        # صف السعر والتاريخ (عنصرين في صف واحد)
        price_date_row = ResponsiveLayout.create_hbox(spacing=Spacing.LG)
        price_date_row.setContentsMargins(0, 0, 0, 0)
        
        # السعر
        price_container = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        price_container.setContentsMargins(0, 0, 0, 0)
        self.price_spin = QSpinBox()
        self.price_spin.setRange(0, 999999)
        self.price_spin.setValue(100)
        self.price_spin.setStyleSheet(InputFactory.get_input_style())
        self.price_spin.setSizePolicy(SizePolicies.expanding_horizontal())
        price_label = QLabel("السعر:")
        price_label.setStyleSheet(InputFactory.get_label_style())
        price_container.addWidget(self.price_spin, 1)
        price_container.addWidget(price_label, 0)
        
        # التاريخ
        date_container = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        date_container.setContentsMargins(0, 0, 0, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setStyleSheet(InputFactory.get_input_style())
        self.date_edit.setSizePolicy(SizePolicies.expanding_horizontal())
        date_label = QLabel("التاريخ:")
        date_label.setStyleSheet(InputFactory.get_label_style())
        date_container.addWidget(self.date_edit, 1)
        date_container.addWidget(date_label, 0)
        
        price_date_row.addLayout(price_container, 1)
        price_date_row.addLayout(date_container, 1)
        details_layout.addLayout(price_date_row)
        
        # الوصف
        desc_row = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        desc_row.setContentsMargins(0, 0, 0, 0)
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("أدخل الوصف هنا...")
        self.description_input.setStyleSheet(InputFactory.get_input_style())
        self.description_input.setSizePolicy(SizePolicies.expanding())
        self.description_input.setMaximumHeight(100)
        desc_label = QLabel("الوصف:")
        desc_label.setStyleSheet(InputFactory.get_label_style())
        desc_row.addWidget(self.description_input, 1)
        desc_row.addWidget(desc_label, 0)
        details_layout.addLayout(desc_row)
        
        # مربع الاختيار
        self.active_checkbox = QCheckBox("نشط")
        self.active_checkbox.setChecked(True)
        self.active_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_PRIMARY};
                font-size: {Typography.get_font_size('body')}px;
                font-weight: bold;
                padding: 8px;
                spacing: 10px;
            }}
            QCheckBox::indicator {{
                width: 22px;
                height: 22px;
                border-radius: 5px;
                border: 2px solid {Colors.BORDER};
                background-color: {Colors.BG_MEDIUM};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Colors.PRIMARY};
                border-color: {Colors.PRIMARY};
            }}
        """)
        details_layout.addWidget(self.active_checkbox)
        
        details_group.setLayout(details_layout)
        content_layout.addWidget(details_group)
        
        # إضافة تمدد
        content_layout.addStretch()
        
        scroll_area.setWidget(content)
        main_layout.addWidget(scroll_area, 1)

        # === منطقة الأزرار (ثابتة في الأسفل) ===
        buttons_container = ContainerFactory.create_card()
        buttons_container.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_LIGHT};
                border-top: 1px solid {Colors.BORDER};
                border-radius: 0px;
                padding: 0px;
            }}
        """)
        buttons_layout = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        buttons_layout.setContentsMargins(
            Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD
        )
        
        buttons_layout.addStretch()
        
        # زر الإلغاء
        self.cancel_btn = ButtonFactory.create_button(
            "إلغاء",
            variant="secondary",
            size=ComponentSize.MEDIUM
        )
        self.cancel_btn.clicked.connect(self.reject)
        
        # زر الحفظ
        self.save_btn = ButtonFactory.create_button(
            "💾 حفظ",
            variant="primary",
            size=ComponentSize.MEDIUM
        )
        self.save_btn.clicked.connect(self._on_save)
        
        # زر الاختبار
        self.test_btn = ButtonFactory.create_button(
            "🧪 اختبار",
            variant="success",
            size=ComponentSize.MEDIUM
        )
        self.test_btn.clicked.connect(self._on_test)
        
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.test_btn)
        
        buttons_container.setLayout(buttons_layout)
        main_layout.addWidget(buttons_container)
    
    def _on_save(self):
        """حفظ البيانات"""
        QMessageBox.information(self, "نجح", "✅ تم حفظ البيانات بنجاح!")
        self.accept()
    
    def _on_test(self):
        """اختبار البيانات"""
        data = {
            "الاسم": self.name_input.text(),
            "البريد": self.email_input.text(),
            "الفئة": self.category_combo.currentText(),
            "السعر": self.price_spin.value(),
            "التاريخ": self.date_edit.date().toString("yyyy-MM-dd"),
            "الوصف": self.description_input.toPlainText(),
            "نشط": "نعم" if self.active_checkbox.isChecked() else "لا"
        }
        
        message = "📋 البيانات المدخلة:\n\n"
        for key, value in data.items():
            message += f"• {key}: {value}\n"
        
        QMessageBox.information(self, "بيانات الاختبار", message)


# ============================================================
# 🧪 TEST
# ============================================================

if __name__ == "__main__":
    import sys
    import os
    
    # إعدادات DPI
    if os.name == 'nt':
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        os.environ["QT_SCALE_FACTOR"] = "1"
        os.environ["QT_SCREEN_SCALE_FACTORS"] = "1"
        os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '0'
    
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # تطبيق نظام التصميم
    try:
        from ui.design_system import apply_design_system
        apply_design_system(app)
    except Exception as e:
        print(f"Warning: Could not apply design system: {e}")
    
    dialog = ExampleResponsiveDialog()
    dialog.show()
    
    sys.exit(app.exec())
