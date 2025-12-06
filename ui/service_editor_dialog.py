# الملف: ui/service_editor_dialog.py

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core import schemas
from services.service_service import ServiceService
from ui.custom_spinbox import CustomSpinBox


class ServiceEditorDialog(QDialog):
    """نافذة منبثقة لإضافة أو تعديل خدمة."""

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

        self.setMinimumWidth(450)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        # إزالة الإطار البرتقالي نهائياً
        self.setStyleSheet("""
            * {
                outline: none;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
            QPushButton:focus {
                border: none;
                outline: none;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        form_groupbox = QGroupBox("بيانات الخدمة")
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(80)
        self.price_input = CustomSpinBox(decimals=2, minimum=0, maximum=999_999)
        self.price_input.setDecimals(2)
        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("مثال: SEO, Web, Packages")

        self.status_checkbox = QCheckBox("الخدمة نشطة")
        self.status_checkbox.setChecked(True)
        self.status_checkbox.setStyleSheet("font-weight: bold;")

        form_layout.addRow(QLabel("اسم الخدمة:"), self.name_input)
        form_layout.addRow(QLabel("الوصف:"), self.description_input)
        form_layout.addRow(QLabel("السعر الافتراضي:"), self.price_input)
        form_layout.addRow(QLabel("الفئة:"), self.category_input)
        form_layout.addRow(QLabel("الحالة:"), self.status_checkbox)

        form_groupbox.setLayout(form_layout)
        layout.addWidget(form_groupbox)

        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("💾 حفظ")
        self.save_button.setStyleSheet(
            "background-color: #0A6CF1; color: white; padding: 10px; font-weight: bold;"
        )
        self.save_button.clicked.connect(self.save_service)
        buttons_layout.addWidget(self.save_button)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

        if self.is_editing:
            self.load_service_data()
            self.save_button.setText("💾 حفظ التعديلات")

    def load_service_data(self):
        self.name_input.setText(self.service_to_edit.name)
        self.description_input.setText(self.service_to_edit.description or "")
        self.price_input.setValue(self.service_to_edit.default_price)
        self.category_input.setText(self.service_to_edit.category or "")
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
            "category": self.category_input.text(),
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
