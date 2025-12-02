# الملف: ui/user_editor_dialog.py
"""
نافذة إضافة/تعديل المستخدمين
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QPushButton, QComboBox, QCheckBox, QMessageBox,
    QHBoxLayout, QGroupBox, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from typing import Optional

from core.auth_models import User, UserRole, AuthService


class UserEditorDialog(QDialog):
    """نافذة إضافة/تعديل مستخدم"""
    
    def __init__(self, auth_service: AuthService, user_to_edit: Optional[User] = None, parent=None):
        super().__init__(parent)
        
        self.auth_service = auth_service
        self.user_to_edit = user_to_edit
        self.is_editing = user_to_edit is not None
        
        if self.is_editing:
            self.setWindowTitle(f"تعديل مستخدم: {user_to_edit.username}")
        else:
            self.setWindowTitle("إضافة مستخدم جديد")
        
        self.setMinimumWidth(400)
        self.setMinimumHeight(350)
        
        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)
        
        # إزالة الإطار البرتقالي
        self.setStyleSheet("""
            * {
                outline: none;
            }
            QLineEdit:focus, QComboBox:focus, QPushButton:focus, QCheckBox:focus {
                border: none;
                outline: none;
            }
        """)
        
        self.init_ui()
        
        if self.is_editing:
            self.populate_fields()
    
    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        
        # مجموعة البيانات الأساسية
        basic_group = QGroupBox("البيانات الأساسية")
        basic_layout = QFormLayout()
        basic_layout.setSpacing(12)
        
        # اسم المستخدم
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("اسم المستخدم (بالإنجليزية)")
        if self.is_editing:
            self.username_input.setEnabled(False)  # لا يمكن تغيير اسم المستخدم
        basic_layout.addRow(QLabel("اسم المستخدم: *"), self.username_input)
        
        # الاسم الكامل
        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("الاسم الكامل")
        basic_layout.addRow(QLabel("الاسم الكامل:"), self.full_name_input)
        
        # البريد الإلكتروني
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("example@company.com")
        basic_layout.addRow(QLabel("البريد الإلكتروني:"), self.email_input)
        
        # الدور
        self.role_combo = QComboBox()
        self.role_combo.addItem("مدير النظام", UserRole.ADMIN)
        self.role_combo.addItem("محاسب", UserRole.ACCOUNTANT)
        self.role_combo.addItem("مندوب مبيعات", UserRole.SALES)
        basic_layout.addRow(QLabel("الدور: *"), self.role_combo)
        
        # الحالة
        self.active_checkbox = QCheckBox("المستخدم نشط")
        self.active_checkbox.setChecked(True)
        basic_layout.addRow(QLabel("الحالة:"), self.active_checkbox)
        
        basic_group.setLayout(basic_layout)
        main_layout.addWidget(basic_group)
        
        # مجموعة كلمة المرور
        password_group = QGroupBox("كلمة المرور")
        password_layout = QFormLayout()
        password_layout.setSpacing(12)
        
        # كلمة المرور
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        if self.is_editing:
            self.password_input.setPlaceholderText("اتركه فارغاً لعدم التغيير")
        else:
            self.password_input.setPlaceholderText("كلمة المرور")
        password_layout.addRow(QLabel("كلمة المرور:" + ("" if self.is_editing else " *")), self.password_input)
        
        # تأكيد كلمة المرور
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        if self.is_editing:
            self.confirm_password_input.setPlaceholderText("تأكيد كلمة المرور الجديدة")
        else:
            self.confirm_password_input.setPlaceholderText("تأكيد كلمة المرور")
        password_layout.addRow(QLabel("تأكيد كلمة المرور:" + ("" if self.is_editing else " *")), self.confirm_password_input)
        
        password_group.setLayout(password_layout)
        main_layout.addWidget(password_group)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        
        # زر الحفظ
        self.save_button = QPushButton("💾 حفظ")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save_user)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        
        # زر الإلغاء
        cancel_button = QPushButton("إلغاء")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(self.save_button)
        
        main_layout.addLayout(buttons_layout)
        self.setLayout(main_layout)
    
    def populate_fields(self):
        """تحميل بيانات المستخدم للتعديل"""
        if not self.user_to_edit:
            return
        
        self.username_input.setText(self.user_to_edit.username)
        self.full_name_input.setText(self.user_to_edit.full_name or "")
        self.email_input.setText(self.user_to_edit.email or "")
        
        # تحديد الدور
        role_value = self.user_to_edit.role
        if isinstance(role_value, str):
            try:
                role_value = UserRole(role_value)
            except ValueError:
                role_value = UserRole.SALES  # افتراضي
        
        for i in range(self.role_combo.count()):
            if self.role_combo.itemData(i) == role_value:
                self.role_combo.setCurrentIndex(i)
                break
        
        self.active_checkbox.setChecked(self.user_to_edit.is_active)
    
    def validate_form(self) -> tuple[bool, str]:
        """التحقق من صحة البيانات"""
        # اسم المستخدم
        username = self.username_input.text().strip()
        if not username:
            return False, "اسم المستخدم مطلوب"
        
        if len(username) < 3:
            return False, "اسم المستخدم يجب أن يكون 3 أحرف على الأقل"
        
        # التحقق من تفرد اسم المستخدم (للمستخدمين الجدد فقط)
        if not self.is_editing:
            existing_user = self.auth_service.repo.get_user_by_username(username)
            if existing_user:
                return False, f"اسم المستخدم '{username}' موجود مسبقاً"
        
        # كلمة المرور
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        
        if not self.is_editing:
            # للمستخدمين الجدد - كلمة المرور مطلوبة
            if not password:
                return False, "كلمة المرور مطلوبة"
            
            if len(password) < 3:
                return False, "كلمة المرور يجب أن تكون 3 أحرف على الأقل"
        else:
            # للتعديل - كلمة المرور اختيارية
            if password and len(password) < 3:
                return False, "كلمة المرور يجب أن تكون 3 أحرف على الأقل"
        
        # تأكيد كلمة المرور
        if password != confirm_password:
            return False, "كلمة المرور وتأكيدها غير متطابقين"
        
        # البريد الإلكتروني (اختياري لكن يجب أن يكون صحيح)
        email = self.email_input.text().strip()
        if email and "@" not in email:
            return False, "البريد الإلكتروني غير صحيح"
        
        return True, "البيانات صحيحة"
    
    def save_user(self):
        """حفظ المستخدم"""
        # التحقق من صحة البيانات
        is_valid, error_message = self.validate_form()
        if not is_valid:
            QMessageBox.warning(self, "خطأ في البيانات", error_message)
            return
        
        try:
            username = self.username_input.text().strip()
            full_name = self.full_name_input.text().strip()
            email = self.email_input.text().strip()
            role = self.role_combo.currentData()
            is_active = self.active_checkbox.isChecked()
            password = self.password_input.text()
            
            if self.is_editing:
                # تعديل مستخدم موجود
                update_data = {
                    "full_name": full_name,
                    "email": email,
                    "role": role.value,
                    "is_active": is_active
                }
                
                # تحديث كلمة المرور إذا تم إدخالها
                if password:
                    update_data["password_hash"] = self.auth_service.hash_password(password)
                
                success = self.auth_service.repo.update_user(
                    self.user_to_edit.id or self.user_to_edit._mongo_id,
                    update_data
                )
                
                if success:
                    QMessageBox.information(self, "تم", "تم تعديل المستخدم بنجاح.")
                    self.accept()
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في تعديل المستخدم.")
            else:
                # إضافة مستخدم جديد
                success = self.auth_service.create_user(
                    username=username,
                    password=password,
                    role=role,
                    full_name=full_name
                )
                
                if success:
                    # تحديث البريد الإلكتروني إذا تم إدخاله
                    if email:
                        user = self.auth_service.repo.get_user_by_username(username)
                        if user:
                            self.auth_service.repo.update_user(
                                user.id or user._mongo_id,
                                {"email": email}
                            )
                    
                    QMessageBox.information(self, "تم", "تم إضافة المستخدم بنجاح.")
                    self.accept()
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في إضافة المستخدم.")
        
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء حفظ المستخدم:\n{str(e)}")
            print(f"ERROR: [UserEditorDialog] {e}")
            import traceback
            traceback.print_exc()