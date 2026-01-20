# الملف: ui/user_editor_dialog.py
"""
نافذة إضافة/تعديل المستخدمين
"""

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.auth_models import AuthService, User, UserRole

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class UserEditorDialog(QDialog):
    """نافذة إضافة/تعديل مستخدم"""

    def __init__(self, auth_service: AuthService, user_to_edit: User | None = None, parent=None):
        super().__init__(parent)

        self.auth_service = auth_service
        self.is_editing = user_to_edit is not None

        # إنشاء نسخة مستقلة من بيانات المستخدم لتجنب الخلط
        if user_to_edit is not None:
            # حفظ البيانات الأصلية كقاموس مستقل
            self._original_user_data = {
                'id': user_to_edit.id,
                'mongo_id': user_to_edit.mongo_id,
                'username': user_to_edit.username,
                'full_name': user_to_edit.full_name,
                'email': user_to_edit.email,
                'role': user_to_edit.role,
                'is_active': user_to_edit.is_active,
                'password_hash': user_to_edit.password_hash,
            }
            self.setWindowTitle(f"تعديل مستخدم: {user_to_edit.username}")
        else:
            self._original_user_data = None
            self.setWindowTitle("إضافة مستخدم جديد")

        # تصميم متجاوب - حد أدنى وأقصى
        self.setMinimumWidth(400)
        self.setMinimumHeight(350)
        self.setMaximumHeight(550)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

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

        # ⚡ تطبيق الستايلات المتجاوبة
        from ui.styles import setup_auto_responsive_dialog
        setup_auto_responsive_dialog(self)

    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        from ui.styles import (
            BUTTON_STYLES,
            COLORS,
            RESPONSIVE_GROUPBOX_STYLE,
            get_cairo_font,
        )

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
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['bg_medium']};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['primary']};
                border-radius: 5px;
                min-height: 30px;
            }}
        """)

        # محتوى التمرير
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(15, 15, 15, 15)

        # مجموعة البيانات الأساسية
        basic_group = QGroupBox("البيانات الأساسية")
        basic_group.setStyleSheet(RESPONSIVE_GROUPBOX_STYLE)
        basic_layout = QFormLayout()
        basic_layout.setSpacing(12)

        # اسم المستخدم
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("اسم المستخدم (بالإنجليزية)")
        self.username_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if self.is_editing:
            self.username_input.setEnabled(False)  # لا يمكن تغيير اسم المستخدم
        basic_layout.addRow(QLabel("اسم المستخدم: *"), self.username_input)

        # الاسم الكامل
        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("الاسم الكامل")
        self.full_name_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        basic_layout.addRow(QLabel("الاسم الكامل:"), self.full_name_input)

        # البريد الإلكتروني
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("example@company.com")
        self.email_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        basic_layout.addRow(QLabel("البريد الإلكتروني:"), self.email_input)

        # الدور
        self.role_combo = QComboBox()
        self.role_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.role_combo.addItem("مدير النظام", UserRole.ADMIN)
        self.role_combo.addItem("محاسب", UserRole.ACCOUNTANT)
        self.role_combo.addItem("مندوب مبيعات", UserRole.SALES)
        basic_layout.addRow(QLabel("الدور: *"), self.role_combo)

        # الحالة
        self.active_checkbox = QCheckBox("المستخدم نشط")
        self.active_checkbox.setChecked(True)
        self.active_checkbox.setFont(get_cairo_font(13, bold=True))
        basic_layout.addRow(QLabel("الحالة:"), self.active_checkbox)

        basic_group.setLayout(basic_layout)
        content_layout.addWidget(basic_group)

        # مجموعة كلمة المرور
        password_group = QGroupBox("كلمة المرور")
        password_group.setStyleSheet(RESPONSIVE_GROUPBOX_STYLE)
        password_layout = QFormLayout()
        password_layout.setSpacing(12)

        # كلمة المرور
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if self.is_editing:
            self.password_input.setPlaceholderText("اتركه فارغاً لعدم التغيير")
        else:
            self.password_input.setPlaceholderText("كلمة المرور")
        password_layout.addRow(QLabel("كلمة المرور:" + ("" if self.is_editing else " *")), self.password_input)

        # تأكيد كلمة المرور
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if self.is_editing:
            self.confirm_password_input.setPlaceholderText("تأكيد كلمة المرور الجديدة")
        else:
            self.confirm_password_input.setPlaceholderText("تأكيد كلمة المرور")
        password_layout.addRow(QLabel("تأكيد كلمة المرور:" + ("" if self.is_editing else " *")), self.confirm_password_input)

        password_group.setLayout(password_layout)
        content_layout.addWidget(password_group)

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        # منطقة الأزرار (ثابتة في الأسفل)
        buttons_container = QWidget()
        buttons_container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_light']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(15, 12, 15, 12)
        buttons_layout.setSpacing(10)

        buttons_layout.addStretch()

        # زر الإلغاء
        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.cancel_button.clicked.connect(self.reject)

        # زر الحفظ
        self.save_button = QPushButton("💾 حفظ")
        self.save_button.setDefault(True)
        self.save_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_button.clicked.connect(self.save_user)

        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.save_button)

        main_layout.addWidget(buttons_container)

    def populate_fields(self):
        """تحميل بيانات المستخدم للتعديل"""
        if not self._original_user_data:
            return

        # استخدام البيانات المحفوظة بدلاً من الكائن الأصلي
        self.username_input.setText(self._original_user_data['username'])
        self.full_name_input.setText(self._original_user_data['full_name'] or "")
        self.email_input.setText(self._original_user_data['email'] or "")

        # تحديد الدور
        role_value = self._original_user_data['role']
        if isinstance(role_value, str):
            try:
                role_value = UserRole(role_value)
            except ValueError:
                role_value = UserRole.SALES  # افتراضي

        for i in range(self.role_combo.count()):
            if self.role_combo.itemData(i) == role_value:
                self.role_combo.setCurrentIndex(i)
                break

        self.active_checkbox.setChecked(self._original_user_data['is_active'])

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
            try:
                existing_user = self.auth_service.repo.get_user_by_username(username)
                if existing_user:
                    return False, f"اسم المستخدم '{username}' موجود مسبقاً"
            except Exception as e:
                safe_print(f"WARNING: [UserEditorDialog] فشل فحص تفرد اسم المستخدم: {e}")
                # نتابع بدون فحص التفرد في حالة الخطأ

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

            if self.is_editing and self._original_user_data:
                # تعديل مستخدم موجود - استخدام البيانات المحفوظة
                original_username = self._original_user_data['username']

                update_data = {
                    "full_name": full_name,
                    "email": email,
                    "role": role.value,
                    "is_active": is_active
                }

                # تحديث كلمة المرور إذا تم إدخالها
                if password:
                    update_data["password_hash"] = self.auth_service.hash_password(password)

                # استخدام username للتحديث (أكثر أماناً)
                safe_print(f"INFO: [UserEditorDialog] جاري تحديث المستخدم: {original_username}")
                safe_print(f"INFO: [UserEditorDialog] البيانات: {update_data}")

                success = self.auth_service.repo.update_user_by_username(
                    original_username,
                    update_data
                )

                if success:
                    QMessageBox.information(self, "تم", "تم تعديل المستخدم بنجاح.")
                    self.accept()
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في تعديل المستخدم.")
            else:
                # إضافة مستخدم جديد
                try:
                    success = self.auth_service.create_user(
                        username=username,
                        password=password,
                        role=role,
                        full_name=full_name
                    )

                    if success:
                        # تحديث البريد الإلكتروني إذا تم إدخاله
                        if email:
                            try:
                                self.auth_service.repo.update_user_by_username(
                                    username,
                                    {"email": email}
                                )
                            except Exception as e:
                                safe_print(f"WARNING: [UserEditorDialog] فشل تحديث البريد الإلكتروني: {e}")

                        QMessageBox.information(self, "تم", "تم إضافة المستخدم بنجاح.")
                        self.accept()
                    else:
                        QMessageBox.warning(self, "خطأ", "فشل في إضافة المستخدم.")
                except Exception as create_error:
                    safe_print(f"ERROR: [UserEditorDialog] فشل إنشاء المستخدم: {create_error}")
                    QMessageBox.critical(self, "خطأ", f"فشل في إضافة المستخدم: {create_error}")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء حفظ المستخدم:\n{str(e)}")
            safe_print(f"ERROR: [UserEditorDialog] {e}")
            import traceback
            traceback.print_exc()
