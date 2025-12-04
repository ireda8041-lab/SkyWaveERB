# الملف: ui/client_editor_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox, QGroupBox, QHBoxLayout,
    QComboBox, QTextEdit, QCheckBox, QFileDialog, QWidget
)
from PyQt6.QtCore import Qt
from services.client_service import ClientService
from core import schemas
from typing import Optional, Dict, Any


class ClientEditorDialog(QDialog):
    """
    (معدلة بالكامل لتطابق الصورة + طلباتك)
    """

    def __init__(self, client_service: ClientService, client_to_edit: Optional[schemas.Client] = None, parent=None):
        super().__init__(parent)

        self.client_service = client_service
        self.client_to_edit = client_to_edit
        self.is_editing = client_to_edit is not None

        if self.is_editing:
            self.setWindowTitle(f"تعديل العميل: {client_to_edit.name}")
        else:
            self.setWindowTitle("إضافة عميل جديد")

        self.setMinimumWidth(500)
        
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
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        form_groupbox = QGroupBox("بيانات العميل")
        client_form = QFormLayout()

        self.name_input = QLineEdit()
        self.company_input = QLineEdit()
        self.company_input.setPlaceholderText("(اختياري)")
        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()
        self.address_input = QLineEdit()
        self.country_input = QLineEdit()
        self.country_input.setPlaceholderText("مثال: EGY / KSA / UAE")

        self.client_type_combo = QComboBox()
        self.client_type_combo.addItems(["فرد", "شركة"])

        self.work_field_input = QLineEdit()
        self.work_field_input.setPlaceholderText("مثال: أثاث، تجارة إلكترونية...")

        self.vat_input = QLineEdit()
        self.vat_input.setPlaceholderText("(اختياري)")

        logo_layout = QHBoxLayout()
        self.logo_path_label = QLabel("لم يتم اختيار صورة")
        self.logo_path_label.setStyleSheet("font-style: italic; color: #888;")
        select_logo_btn = QPushButton("... اختيار صورة")
        select_logo_btn.clicked.connect(self.select_logo_file)
        logo_layout.addWidget(self.logo_path_label, 1)
        logo_layout.addWidget(select_logo_btn)
        logo_widget = QWidget()
        logo_widget.setLayout(logo_layout)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("أي ملاحظات إضافية عن العميل...")
        self.notes_input.setMinimumHeight(80)

        self.status_checkbox = QCheckBox("العميل نشط")
        self.status_checkbox.setChecked(True)
        self.status_checkbox.setStyleSheet("font-weight: bold;")

        client_form.addRow(QLabel("الاسم بالكامل:"), self.name_input)
        client_form.addRow(QLabel("الشركة:"), self.company_input)
        client_form.addRow(QLabel("رقم الهاتف:"), self.phone_input)
        client_form.addRow(QLabel("البريد الإلكتروني:"), self.email_input)
        client_form.addRow(QLabel("العنوان:"), self.address_input)
        client_form.addRow(QLabel("الدولة:"), self.country_input)
        client_form.addRow(QLabel("نوع العميل:"), self.client_type_combo)
        client_form.addRow(QLabel("مجال العمل:"), self.work_field_input)
        client_form.addRow(QLabel("الرقم الضريبي:"), self.vat_input)
        client_form.addRow(QLabel("صورة/لوجو:"), logo_widget)
        client_form.addRow(QLabel("ملاحظات:"), self.notes_input)
        client_form.addRow(QLabel("الحالة:"), self.status_checkbox)

        form_groupbox.setLayout(client_form)
        layout.addWidget(form_groupbox)

        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("💾 حفظ")
        self.cancel_button = QPushButton("✕ إلغاء")

        self.save_button.setStyleSheet("background-color: #0A6CF1; color: white; padding: 10px; font-weight: bold;")
        self.cancel_button.setStyleSheet("background-color: #ef4444; color: white; padding: 10px; font-weight: bold;")

        self.save_button.clicked.connect(self.save_client)
        self.cancel_button.clicked.connect(self.reject)

        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

        if self.is_editing:
            self.load_client_data()
            self.save_button.setText("💾 حفظ التعديلات")

    def select_logo_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "اختر صورة", "", "Image Files (*.png *.jpg *.jpeg)")
        if file_path:
            normalized = file_path.replace("/", "\\")
            self.logo_path_label.setText(normalized)
            self.logo_path_label.setStyleSheet("font-style: normal; color: #111827;")

    def load_client_data(self):
        """ يملأ الحقول ببيانات العميل القديمة """
        self.name_input.setText(self.client_to_edit.name)
        self.company_input.setText(self.client_to_edit.company_name or "")
        self.email_input.setText(self.client_to_edit.email or "")
        self.phone_input.setText(self.client_to_edit.phone or "")
        self.address_input.setText(self.client_to_edit.address or "")
        self.country_input.setText(self.client_to_edit.country or "")
        self.vat_input.setText(self.client_to_edit.vat_number or "")
        self.client_type_combo.setCurrentText(self.client_to_edit.client_type or "فرد")
        self.work_field_input.setText(self.client_to_edit.work_field or "")

        logo_path = self.client_to_edit.logo_path or ""
        if logo_path:
            self.logo_path_label.setText(logo_path)
            self.logo_path_label.setStyleSheet("font-style: normal; color: #111827;")
        else:
            self.logo_path_label.setText("لم يتم اختيار صورة")
            self.logo_path_label.setStyleSheet("font-style: italic; color: #888;")

        self.notes_input.setText(self.client_to_edit.client_notes or "")
        self.status_checkbox.setChecked(self.client_to_edit.status == schemas.ClientStatus.ACTIVE)

    def get_form_data(self) -> Dict[str, Any]:
        """ يجمع البيانات من الحقول """
        status = schemas.ClientStatus.ACTIVE if self.status_checkbox.isChecked() else schemas.ClientStatus.ARCHIVED
        logo_text = self.logo_path_label.text()
        logo_value = "" if "لم يتم" in logo_text else logo_text

        return {
            "name": self.name_input.text(),
            "company_name": self.company_input.text(),
            "email": self.email_input.text(),
            "phone": self.phone_input.text(),
            "address": self.address_input.text(),
            "country": self.country_input.text(),
            "vat_number": self.vat_input.text(),
            "status": status,
            "client_type": self.client_type_combo.currentText(),
            "work_field": self.work_field_input.text(),
            "logo_path": logo_value,
            "client_notes": self.notes_input.toPlainText(),
        }

    def save_client(self):
        """ يحفظ (أو يعدل) العميل عبر الخدمة """
        client_data = self.get_form_data()

        if not client_data["name"]:
            QMessageBox.warning(self, "خطأ", "اسم العميل مطلوب")
            return

        try:
            if self.is_editing:
                client_id = self.client_to_edit._mongo_id or str(self.client_to_edit.id)
                self.client_service.update_client(client_id, client_data)
                QMessageBox.information(self, "تم", f"تم حفظ تعديلات العميل '{client_data['name']}' بنجاح.")
            else:
                new_client_schema = schemas.Client(**client_data)
                self.client_service.create_client(new_client_schema)
                QMessageBox.information(self, "تم", f"تم إضافة العميل '{client_data['name']}' بنجاح.")

            self.accept()

        except Exception as e:
            print(f"ERROR: [ClientEditorDialog] فشل حفظ العميل: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")
