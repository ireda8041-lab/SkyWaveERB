from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core import schemas
from services.accounting_service import AccountingService
from ui.custom_spinbox import CustomSpinBox


class AccountEditorDialog(QDialog):
    """
    نافذة إضافة/تعديل حساب - Standard Form Layout
    الحقول: Code, Name, Type, Parent Account, Currency, Opening Balance, Description, Active
    """

    def __init__(
        self,
        accounting_service: AccountingService,
        all_accounts: list[schemas.Account],
        account_to_edit: schemas.Account | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.accounting_service = accounting_service
        self.all_accounts = all_accounts
        self.account_to_edit = account_to_edit
        self.is_editing = account_to_edit is not None

        if self.is_editing and account_to_edit is not None:
            self.setWindowTitle(f"تعديل حساب: {account_to_edit.name}")
        else:
            self.setWindowTitle("إضافة حساب جديد")

        self.setMinimumWidth(450)
        self.setMinimumHeight(450)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        # إزالة الإطار البرتقالي نهائياً من جميع العناصر
        self.setStyleSheet("""
            * {
                outline: none;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
            QPushButton:focus, QCheckBox:focus, QRadioButton:focus {
                border: none;
                outline: none;
            }
        """)

        self.init_ui()

    def init_ui(self):
        """إنشاء واجهة المستخدم - Standard Form Layout with Smart Features"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)

        # GroupBox للبيانات الأساسية
        form_groupbox = QGroupBox("بيانات الحساب")
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(15, 20, 15, 15)

        # 1. Code
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("مثال: 1111")
        self.code_input.setStyleSheet("QLineEdit { border: 1px solid #444; outline: none; } QLineEdit:focus { border: 1px solid #666; outline: none; }")
        self.code_input.textChanged.connect(self._validate_inputs)
        form_layout.addRow("كود الحساب: *", self.code_input)

        # 2. Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("مثال: الخزنة الرئيسية")
        self.name_input.setStyleSheet("QLineEdit { border: 1px solid #444; outline: none; } QLineEdit:focus { border: 1px solid #666; outline: none; }")
        self.name_input.textChanged.connect(self._validate_inputs)
        form_layout.addRow("اسم الحساب: *", self.name_input)

        # 3. Type - with smart defaults
        self.type_combo = QComboBox()
        account_types = [
            (schemas.AccountType.ASSET, "أصول"),
            (schemas.AccountType.CASH, "أصول نقدية"),
            (schemas.AccountType.LIABILITY, "خصوم"),
            (schemas.AccountType.EQUITY, "حقوق ملكية"),
            (schemas.AccountType.REVENUE, "إيرادات"),
            (schemas.AccountType.EXPENSE, "مصروفات"),
        ]
        for acc_type, display_name in account_types:
            self.type_combo.addItem(display_name, userData=acc_type)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form_layout.addRow("نوع الحساب:", self.type_combo)

        # 4. Parent Account (Critical) - with smart filtering
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("-- بدون أب (حساب رئيسي) --", userData=None)
        self.parent_combo.setEditable(True)  # Enable auto-complete
        self._populate_parent_accounts()
        form_layout.addRow("الحساب الأب:", self.parent_combo)

        # 5. Currency - Smart Default (EGP)
        self.currency_combo = QComboBox()
        currencies = [
            (schemas.CurrencyCode.EGP, "جنيه مصري (EGP)"),
            (schemas.CurrencyCode.USD, "دولار أمريكي (USD)"),
            (schemas.CurrencyCode.SAR, "ريال سعودي (SAR)"),
            (schemas.CurrencyCode.AED, "درهم إماراتي (AED)"),
        ]
        for currency, display_name in currencies:
            self.currency_combo.addItem(display_name, userData=currency)
        self.currency_combo.setCurrentIndex(0)  # Default to EGP
        form_layout.addRow("العملة:", self.currency_combo)

        # 6. Opening Balance
        self.balance_spinbox = CustomSpinBox(decimals=2, minimum=-999999999.99, maximum=999999999.99)
        self.balance_spinbox.setValue(0.0)
        self.balance_spinbox.setSuffix(" ج.م")
        form_layout.addRow("الرصيد الافتتاحي:", self.balance_spinbox)

        # 7. Description
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("وصف الحساب (اختياري)...")
        self.description_input.setMaximumHeight(60)
        form_layout.addRow("الوصف:", self.description_input)

        # 8. Active Checkbox - Default checked
        self.active_checkbox = QCheckBox("حساب نشط")
        self.active_checkbox.setChecked(True)
        form_layout.addRow("الحالة:", self.active_checkbox)

        form_groupbox.setLayout(form_layout)
        main_layout.addWidget(form_groupbox)

        # Validation message label (without orange border)
        from PyQt6.QtWidgets import QLabel as QLabelWidget
        self.validation_label = QLabelWidget("")
        self.validation_label.setStyleSheet("color: #ff3d00; font-weight: bold; padding: 5px; border: none; outline: none;")
        self.validation_label.setVisible(False)
        main_layout.addWidget(self.validation_label)

        # أزرار الحفظ والإلغاء
        buttons_layout = QHBoxLayout()

        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton("💾 حفظ")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save_account)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #0A6CF1;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0A6CF1;
            }
            QPushButton:disabled {
                background-color: #6b7280;
                color: #9ca3af;
            }
        """)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.save_button)

        main_layout.addLayout(buttons_layout)
        self.setLayout(main_layout)

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

        # تحميل البيانات إذا كان في وضع التعديل
        if self.is_editing:
            self.populate_fields()
        else:
            # Initial validation for new accounts
            self._validate_inputs()

    def _validate_inputs(self):
        """Real-time validation - only enable/disable save button"""
        is_valid = True
        error_messages = []

        # Validate code
        code = self.code_input.text().strip()
        if not code:
            is_valid = False
            error_messages.append("كود الحساب مطلوب")

        # Validate name
        name = self.name_input.text().strip()
        if not name:
            is_valid = False
            error_messages.append("اسم الحساب مطلوب")

        # Update validation message
        if error_messages:
            self.validation_label.setText("⚠️ " + " • ".join(error_messages))
            self.validation_label.setVisible(True)
        else:
            self.validation_label.setVisible(False)

        # Enable/disable save button
        self.save_button.setEnabled(is_valid)

        return is_valid

    def _on_type_changed(self, index):
        """Smart suggestions based on account type"""
        account_type = self.type_combo.currentData()

        # Auto-suggest parent based on type
        if account_type == schemas.AccountType.CASH:
            # Suggest under "النقدية والخزائن" (1110)
            for i in range(self.parent_combo.count()):
                if "1110" in self.parent_combo.itemText(i):
                    self.parent_combo.setCurrentIndex(i)
                    break
        elif account_type == schemas.AccountType.EXPENSE:
            # Suggest under "المصروفات التشغيلية" (5100)
            for i in range(self.parent_combo.count()):
                if "5100" in self.parent_combo.itemText(i):
                    self.parent_combo.setCurrentIndex(i)
                    break
        elif account_type == schemas.AccountType.REVENUE:
            # Suggest under "إيرادات الخدمات" (4100)
            for i in range(self.parent_combo.count()):
                if "4100" in self.parent_combo.itemText(i):
                    self.parent_combo.setCurrentIndex(i)
                    break

    def _populate_parent_accounts(self):
        """ملء قائمة الحسابات الأب - مرتبة حسب الكود"""
        # ترتيب الحسابات حسب الكود لعرض الشجرة بشكل منطقي
        sorted_accounts = sorted(self.all_accounts, key=lambda x: str(x.code or ""))

        for acc in sorted_accounts:
            if not acc.code:
                continue
            # لا يمكن للحساب أن يكون أباً لنفسه
            if self.is_editing and acc.code == self.account_to_edit.code:
                continue
            # لا يمكن للحساب أن يكون أباً لأحد أبنائه (منع الحلقات)
            if self.is_editing and self._is_descendant(acc.code, self.account_to_edit.code):
                continue

            # إضافة مسافة بادئة للحسابات الفرعية
            indent = ""
            if acc.parent_code:
                indent = "  └─ "

            display_text = f"{indent}{acc.code} - {acc.name}"
            self.parent_combo.addItem(display_text, userData=str(acc.code))

    def _is_descendant(self, potential_child_code: str, parent_code: str) -> bool:
        """التحقق مما إذا كان الحساب من أحفاد حساب آخر"""
        if not potential_child_code or not parent_code:
            return False
        # البحث في الشجرة
        for acc in self.all_accounts:
            if acc.code == potential_child_code:
                if acc.parent_code == parent_code:
                    return True
                elif acc.parent_code:
                    return self._is_descendant(acc.parent_code, parent_code)
        return False

    def populate_fields(self):
        """تحميل بيانات الحساب للتعديل - FIXED: يحدد الحساب الأب بشكل صحيح"""
        if not self.account_to_edit:
            return

        print(f"INFO: [AccountDialog] Loading account: {self.account_to_edit.name}")
        print(f"INFO: [AccountDialog] parent_code = {self.account_to_edit.parent_code}, parent_id = {self.account_to_edit.parent_id}")

        # 1. Code
        self.code_input.setText(self.account_to_edit.code or "")

        # 2. Name
        self.name_input.setText(self.account_to_edit.name or "")

        # 3. Type
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.account_to_edit.type:
                self.type_combo.setCurrentIndex(i)
                break

        # 4. Parent Account - استخدام parent_code أو parent_id (أيهما موجود)
        parent_code = self.account_to_edit.parent_code or self.account_to_edit.parent_id
        if parent_code:
            parent_code_str = str(parent_code).strip()
            print(f"DEBUG: [AccountDialog] Searching for parent: '{parent_code_str}'")

            # البحث في جميع عناصر الـ combo
            found = False
            for i in range(self.parent_combo.count()):
                item_data = self.parent_combo.itemData(i)
                if item_data and str(item_data).strip() == parent_code_str:
                    self.parent_combo.setCurrentIndex(i)
                    print(f"SUCCESS: [AccountDialog] Parent found at index {i}: {parent_code_str}")
                    found = True
                    break

            if not found:
                # إذا لم يتم العثور، نحاول إضافته يدوياً
                print(f"WARNING: [AccountDialog] Parent {parent_code_str} not found in combo")
                parent_account = next((acc for acc in self.all_accounts if str(acc.code).strip() == parent_code_str), None)
                if parent_account:
                    indent = "  └─ " if parent_account.parent_code else ""
                    display_text = f"{indent}{parent_account.code} - {parent_account.name}"
                    self.parent_combo.addItem(display_text, userData=str(parent_account.code))
                    self.parent_combo.setCurrentIndex(self.parent_combo.count() - 1)
                    print(f"SUCCESS: [AccountDialog] Added and selected parent: {parent_account.code}")
                else:
                    print(f"ERROR: [AccountDialog] Parent account {parent_code_str} not found anywhere!")
        else:
            # No parent - set to "No Parent" (index 0)
            self.parent_combo.setCurrentIndex(0)
            print("INFO: [AccountDialog] No parent_code, setting to 'No Parent'")

        # 5. Currency
        if self.account_to_edit.currency:
            for i in range(self.currency_combo.count()):
                currency_data = self.currency_combo.itemData(i)
                if currency_data == self.account_to_edit.currency:
                    self.currency_combo.setCurrentIndex(i)
                    break

        # 6. Opening Balance
        self.balance_spinbox.setValue(self.account_to_edit.balance or 0.0)

        # 7. Description
        if self.account_to_edit.description:
            self.description_input.setText(self.account_to_edit.description)

        # 8. Active Status
        is_active = self.account_to_edit.status == schemas.AccountStatus.ACTIVE
        self.active_checkbox.setChecked(is_active)

    def get_form_data(self) -> dict[str, Any]:
        """جمع البيانات من النموذج"""
        selected_parent_code = self.parent_combo.currentData()

        # التأكد من أن parent_code هو None إذا كان "بدون أب"
        if selected_parent_code is None or selected_parent_code == "":
            parent_code = None
        else:
            parent_code = str(selected_parent_code)

        data = {
            "code": self.code_input.text().strip(),
            "name": self.name_input.text().strip(),
            "type": self.type_combo.currentData(),
            "parent_code": parent_code,
            "currency": self.currency_combo.currentData(),
            "description": self.description_input.toPlainText().strip(),
            "status": schemas.AccountStatus.ACTIVE if self.active_checkbox.isChecked() else schemas.AccountStatus.ARCHIVED,
            "is_group": False,
        }

        # ⚠️ فقط أضف الرصيد الافتتاحي عند إنشاء حساب جديد
        # عند التعديل، لا نريد تغيير الرصيد المحسوب من القيود
        if not self.is_editing:
            data["balance"] = self.balance_spinbox.value()

        return data

    def validate_form(self) -> tuple[bool, str]:
        """التحقق من صحة البيانات المدخلة"""
        account_data = self.get_form_data()

        if not account_data["code"]:
            return False, "كود الحساب مطلوب"

        if not account_data["name"]:
            return False, "اسم الحساب مطلوب"

        if not account_data["type"]:
            return False, "نوع الحساب مطلوب"

        # التحقق من تفرد الكود
        existing_codes = {acc.code for acc in self.all_accounts}
        if self.is_editing and self.account_to_edit is not None:
            existing_codes.discard(self.account_to_edit.code)

        if account_data["code"] in existing_codes:
            return False, f"كود الحساب '{account_data['code']}' موجود مسبقاً"

        # التحقق من صحة الحساب الأب
        if account_data["parent_code"]:
            parent_exists = any(acc.code == account_data["parent_code"] for acc in self.all_accounts)
            if not parent_exists:
                return False, f"الحساب الأب '{account_data['parent_code']}' غير موجود"

        return True, "البيانات صحيحة"

    def save_account(self):
        """حفظ الحساب"""
        is_valid, error_message = self.validate_form()
        if not is_valid:
            QMessageBox.warning(self, "خطأ في البيانات", error_message)
            return

        account_data = self.get_form_data()

        try:
            if self.is_editing:
                # استخدام id أو _mongo_id أو code
                account_id = None
                if self.account_to_edit._mongo_id:
                    account_id = self.account_to_edit._mongo_id
                elif self.account_to_edit.id:
                    account_id = str(self.account_to_edit.id)

                # إذا لم يكن هناك id صالح، نستخدم الكود للتحديث
                if not account_id or account_id == "None":
                    self.accounting_service.update_account_by_code(self.account_to_edit.code, account_data)
                else:
                    self.accounting_service.update_account(account_id, account_data)
                QMessageBox.information(
                    self,
                    "تم التعديل",
                    f"تم حفظ تعديلات الحساب '{account_data['name']}' بنجاح."
                )
            else:
                self.accounting_service.create_account(account_data)
                QMessageBox.information(
                    self,
                    "تم الإنشاء",
                    f"تم إضافة الحساب '{account_data['name']}' بنجاح."
                )

            self.accept()

        except Exception as e:
            print(f"ERROR: [AccountEditorDialog] Failed to save account: {e}")
            import traceback
            traceback.print_exc()

            QMessageBox.critical(
                self,
                "خطأ في الحفظ",
                f"فشل في حفظ الحساب:\n{str(e)}"
            )
