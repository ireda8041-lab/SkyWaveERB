# الملف: ui/service_editor_dialog.py
"""
نافذة تحرير الخدمات - تصميم محسن ومتجاوب
"""

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.service_service import ServiceService
from ui.custom_spinbox import CustomSpinBox
from ui.smart_combobox import SmartFilterComboBox


class ServiceEditorDialog(QDialog):
    """نافذة منبثقة لإضافة أو تعديل خدمة - تصميم متجاوب."""

    def __init__(
        self,
        service_service: ServiceService,
        service_to_edit: schemas.Service | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.service_service = service_service
        self.service_to_edit = service_to_edit
        self.is_editing = service_to_edit is not None

        if self.is_editing and service_to_edit is not None:
            self.setWindowTitle(f"تعديل الخدمة: {service_to_edit.name}")
        else:
            self.setWindowTitle("إضافة خدمة/باقة جديدة")

        # 📱 Responsive
        self.setMinimumWidth(420)
        self.setMinimumHeight(400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        self._init_ui()

    def _init_ui(self):
        """إعداد واجهة المستخدم"""
        from ui.styles import BUTTON_STYLES, COLORS

        # التخطيط الرئيسي
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # منطقة التمرير
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {COLORS['bg_dark']};
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['bg_medium']};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['primary']};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 14, 14, 14)

        # ستايل الحقول
        field_style = f"""
            QLineEdit {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px;
                font-size: 11px;
                min-height: 16px;
            }}
            QLineEdit:hover {{
                border-color: {COLORS['primary']};
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['primary']};
            }}
            QTextEdit {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 6px;
                font-size: 11px;
            }}
            QTextEdit:hover {{
                border-color: {COLORS['primary']};
            }}
        """

        label_style = f"color: {COLORS['text_secondary']}; font-size: 10px;"

        # === اسم الخدمة ===
        name_label = QLabel("📦 اسم الخدمة *")
        name_label.setStyleSheet(label_style)
        layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setStyleSheet(field_style)
        self.name_input.setPlaceholderText("أدخل اسم الخدمة...")
        layout.addWidget(self.name_input)

        # === صف السعر والفئة ===
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        # السعر
        price_cont = QVBoxLayout()
        price_cont.setSpacing(2)
        price_label = QLabel("💰 السعر الافتراضي *")
        price_label.setStyleSheet(label_style)
        price_cont.addWidget(price_label)
        self.price_input = CustomSpinBox(decimals=2, minimum=0, maximum=999_999)
        self.price_input.setDecimals(2)
        self.price_input.setSuffix(" ج.م")
        price_cont.addWidget(self.price_input)
        row1.addLayout(price_cont, 1)

        # الفئة (ComboBox قابل للتعديل)
        cat_cont = QVBoxLayout()
        cat_cont.setSpacing(2)
        cat_label = QLabel("📂 الفئة")
        cat_label.setStyleSheet(label_style)
        cat_cont.addWidget(cat_label)
        
        # SmartFilterComboBox مع فلترة ذكية
        self.category_input = SmartFilterComboBox()
        self.category_input.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px 7px 25px;
                font-size: 11px;
                min-height: 16px;
            }}
            QComboBox:hover {{
                border-color: {COLORS['primary']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 22px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url(assets/down-arrow.png);
                width: 10px;
                height: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                selection-background-color: {COLORS['primary']};
            }}
        """)
        
        # ⚡ تحميل الفئات الموجودة
        self._load_existing_categories()
        
        self.category_input.lineEdit().setPlaceholderText("اكتب للبحث أو أضف فئة جديدة...")
        
        cat_cont.addWidget(self.category_input)
        row1.addLayout(cat_cont, 1)

        layout.addLayout(row1)

        # === الوصف ===
        desc_label = QLabel("📝 الوصف")
        desc_label.setStyleSheet(label_style)
        layout.addWidget(desc_label)

        self.description_input = QTextEdit()
        self.description_input.setStyleSheet(field_style)
        self.description_input.setPlaceholderText("وصف الخدمة...")
        self.description_input.setMinimumHeight(120)
        layout.addWidget(self.description_input)

        # === الحالة ===
        self.status_checkbox = QCheckBox("الخدمة نشطة")
        self.status_checkbox.setChecked(True)
        self.status_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {COLORS['text_primary']};
                font-size: 11px;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid {COLORS['border']};
                background-color: {COLORS['bg_medium']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLORS['primary']};
                border-color: {COLORS['primary']};
            }}
        """)
        layout.addWidget(self.status_checkbox)

        layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        # منطقة الأزرار
        buttons_container = QWidget()
        buttons_container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_medium']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(14, 10, 14, 10)
        buttons_layout.setSpacing(8)

        buttons_layout.addStretch()

        self.save_button = QPushButton("💾 حفظ")
        self.save_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_button.setFixedHeight(28)
        self.save_button.clicked.connect(self.save_service)
        buttons_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.cancel_button.setFixedHeight(28)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)

        main_layout.addWidget(buttons_container)

        if self.is_editing:
            self.load_service_data()
            self.save_button.setText("💾 حفظ")

    def _load_existing_categories(self):
        """⚡ تحميل الفئات الموجودة من الخدمات الحالية"""
        try:
            services = self.service_service.get_all_services()
            categories = set()
            
            for service in services:
                if service.category and service.category.strip():
                    categories.add(service.category.strip())
            
            # ترتيب الفئات أبجدياً وإضافتها
            sorted_categories = sorted(categories)
            self.category_input.addItem("")  # خيار فارغ
            for cat in sorted_categories:
                self.category_input.addItem(cat)
                
        except Exception as e:
            print(f"WARNING: [ServiceEditorDialog] فشل تحميل الفئات: {e}")

    def load_service_data(self):
        self.name_input.setText(self.service_to_edit.name)
        self.description_input.setText(self.service_to_edit.description or "")
        self.price_input.setValue(self.service_to_edit.default_price)
        
        # ⚡ تعيين الفئة في ComboBox
        category = self.service_to_edit.category or ""
        index = self.category_input.findText(category)
        if index >= 0:
            self.category_input.setCurrentIndex(index)
        else:
            self.category_input.setCurrentText(category)
        
        self.status_checkbox.setChecked(
            self.service_to_edit.status == schemas.ServiceStatus.ACTIVE
        )

    def _collect_form_data(self) -> dict[str, Any]:
        status = (
            schemas.ServiceStatus.ACTIVE
            if self.status_checkbox.isChecked()
            else schemas.ServiceStatus.ARCHIVED
        )
        return {
            "name": self.name_input.text(),
            "description": self.description_input.toPlainText(),
            "default_price": self.price_input.value(),
            "category": self.category_input.currentText().strip(),  # ⚡ من ComboBox
            "status": status,
        }

    def save_service(self):
        service_data = self._collect_form_data()

        if not service_data["name"] or service_data["default_price"] <= 0:
            QMessageBox.warning(self, "خطأ", "اسم الخدمة والسعر الافتراضي مطلوبان")
            return

        try:
            if self.is_editing:
                service_id = self.service_to_edit._mongo_id or str(self.service_to_edit.id)
                self.service_service.update_service(service_id, service_data)
                QMessageBox.information(self, "تم", "تم حفظ تعديلات الخدمة بنجاح.")
            else:
                self.service_service.create_service(service_data)
                QMessageBox.information(
                    self, "تم", f"تم إضافة الخدمة '{service_data['name']}' بنجاح."
                )

            self.accept()
        except Exception as e:
            print(f"ERROR: [ServiceEditorDialog] فشل حفظ الخدمة: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")
