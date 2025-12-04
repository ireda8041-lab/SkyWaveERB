# الملف: ui/expense_editor_dialog.py
"""
نافذة إضافة/تعديل المصروفات
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox, QGroupBox, QHBoxLayout,
    QComboBox, QDateEdit, QTextEdit
)
from ui.custom_spinbox import CustomSpinBox
from PyQt6.QtCore import Qt, QDate
from services.expense_service import ExpenseService
from services.accounting_service import AccountingService
from services.project_service import ProjectService
from core import schemas
from typing import Optional, Dict, Any, List


class ExpenseEditorDialog(QDialog):
    """نافذة إضافة/تعديل مصروف"""

    def __init__(
        self,
        expense_service: ExpenseService,
        accounting_service: AccountingService,
        project_service: ProjectService,
        expense_to_edit: Optional[schemas.Expense] = None,
        parent=None
    ):
        super().__init__(parent)

        self.expense_service = expense_service
        self.accounting_service = accounting_service
        self.project_service = project_service
        self.expense_to_edit = expense_to_edit
        self.is_editing = expense_to_edit is not None

        if self.is_editing:
            self.setWindowTitle(f"تعديل المصروف")
        else:
            self.setWindowTitle("مصروف جديد")

        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
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
            QPushButton:focus, QCheckBox:focus {
                border: none;
                outline: none;
            }
        """)
        
        # جلب البيانات
        self.load_data()
        self.init_ui()

    def load_data(self):
        """جلب الحسابات والمشاريع من قاعدة البيانات"""
        # جلب جميع الحسابات
        all_accounts = self.accounting_service.repo.get_all_accounts()
        
        # حسابات النقدية والبنوك فقط (11xx) للدفع منها
        self.cash_accounts = [acc for acc in all_accounts if acc.code and acc.code.startswith('11')]
        
        # حسابات المصروفات فقط (5xxx) للفئة
        self.expense_accounts = [acc for acc in all_accounts if acc.code and acc.code.startswith('5')]
        
        # المشاريع
        self.projects_list = self.project_service.get_all_projects()

    def init_ui(self):
        layout = QVBoxLayout()

        form_groupbox = QGroupBox("بيانات المصروف")
        form_layout = QFormLayout()

        # المشروع
        self.project_combo = QComboBox()
        self.project_combo.addItem("-- غير مرتبط بمشروع --", userData=None)
        for project in self.projects_list:
            self.project_combo.addItem(project.name, userData=project)

        # الفئة (حساب المصروف) - استخدام الحسابات الحقيقية فقط
        self.category_combo = QComboBox()
        self.category_combo.setPlaceholderText("اختر حساب المصروف...")
        for acc in self.expense_accounts:
            self.category_combo.addItem(f"{acc.code} - {acc.name}", userData=acc.code)

        # الدفع من حساب - استخدام الحسابات النقدية الحقيقية فقط (11xx)
        self.account_combo = QComboBox()
        self.account_combo.setPlaceholderText("اختر حساب الدفع...")
        for acc in self.cash_accounts:
            self.account_combo.addItem(f"{acc.code} - {acc.name}", userData=acc.code)

        # العملة
        self.currency_combo = QComboBox()
        currencies_data = [
            ("EGP", "جنيه مصري (ج.م)", 1.00),
            ("USD", "دولار أمريكي ($)", 47.34),
            ("SAR", "ريال سعودي (ر.س)", 12.62),
            ("AED", "درهم إماراتي (د.إ)", 12.90),
        ]
        for code, name, rate in currencies_data:
            self.currency_combo.addItem(f"{name} - {rate} ج.م", userData={"code": code, "rate": rate})

        # المبلغ - with real-time validation
        self.amount_input = CustomSpinBox(decimals=2, minimum=0, maximum=9_999_999)
        self.amount_input.setSuffix(" ")
        self.amount_input.valueChanged.connect(self._validate_amount)

        # التاريخ - Smart Default (Today)
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")

        # الوصف
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("وصف المصروف...")
        self.description_input.setMaximumHeight(80)

        # إضافة الحقول للفورم
        form_layout.addRow(QLabel("📁 المشروع:"), self.project_combo)
        form_layout.addRow(QLabel("📂 الفئة:"), self.category_combo)
        form_layout.addRow(QLabel("💳 الدفع من حساب:"), self.account_combo)
        form_layout.addRow(QLabel("💱 العملة:"), self.currency_combo)
        form_layout.addRow(QLabel("💰 المبلغ:"), self.amount_input)
        form_layout.addRow(QLabel("📅 التاريخ:"), self.date_input)
        form_layout.addRow(QLabel("📝 الوصف:"), self.description_input)

        form_groupbox.setLayout(form_layout)
        layout.addWidget(form_groupbox)

        # أزرار الحفظ والإلغاء
        buttons_layout = QHBoxLayout()
        
        self.save_button = QPushButton("💾 حفظ")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #0A6CF1;
                color: white;
                padding: 12px 30px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0A6CF1;
            }
            QPushButton:disabled {
                background-color: #6b7280;
                color: #9ca3af;
            }
        """)
        self.save_button.clicked.connect(self.save_expense)
        
        # Initial validation
        self._validate_amount()

        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                padding: 12px 30px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)

        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

        # تحميل البيانات إذا كان تعديل
        if self.is_editing:
            self.load_expense_data()

    def _validate_amount(self):
        """Real-time amount validation"""
        amount = self.amount_input.value()
        if amount <= 0:
            self.save_button.setEnabled(False)
        else:
            self.save_button.setEnabled(True)
    
    def _show_validation_error(self, message: str):
        """Show validation error as a toast-like message"""
        QMessageBox.warning(self, "⚠️ تحقق من البيانات", message)
    
    def load_expense_data(self):
        """تحميل بيانات المصروف للتعديل"""
        exp = self.expense_to_edit
        
        # المشروع
        if exp.project_id:
            for i in range(self.project_combo.count()):
                project = self.project_combo.itemData(i)
                if project and hasattr(project, 'name') and project.name == exp.project_id:
                    self.project_combo.setCurrentIndex(i)
                    break
        
        # الفئة - البحث بالكود أو النص
        if hasattr(exp, 'account_id') and exp.account_id:
            # البحث بالكود
            for i in range(self.category_combo.count()):
                acc_code = self.category_combo.itemData(i)
                if acc_code == exp.account_id:
                    self.category_combo.setCurrentIndex(i)
                    break
        else:
            # البحث بالنص (للتوافق مع البيانات القديمة)
            for i in range(self.category_combo.count()):
                if exp.category in self.category_combo.itemText(i):
                    self.category_combo.setCurrentIndex(i)
                    break
        
        # حساب الدفع
        if hasattr(exp, 'payment_account_id') and exp.payment_account_id:
            for i in range(self.account_combo.count()):
                acc_code = self.account_combo.itemData(i)
                if acc_code == exp.payment_account_id:
                    self.account_combo.setCurrentIndex(i)
                    break
        
        # المبلغ
        self.amount_input.setValue(exp.amount)
        
        # التاريخ
        if exp.date:
            self.date_input.setDate(QDate(exp.date.year, exp.date.month, exp.date.day))
        
        # الوصف
        self.description_input.setText(exp.description or "")

    def save_expense(self):
        """حفظ المصروف مع التحقق الذكي من الحسابات"""
        # جلب الأكواد من userData (الحسابات الحقيقية)
        selected_category_code = self.category_combo.currentData()
        selected_payment_code = self.account_combo.currentData()
        selected_project = self.project_combo.currentData()

        # Smart validation with user-friendly messages
        if not selected_category_code:
            self._show_validation_error("⚠️ الرجاء اختيار فئة المصروف من الحسابات المحاسبية")
            return
            
        if not selected_payment_code:
            self._show_validation_error("⚠️ الرجاء اختيار حساب الدفع من الحسابات النقدية")
            return
            
        if self.amount_input.value() <= 0:
            self._show_validation_error("⚠️ الرجاء إدخال مبلغ صحيح (أكبر من صفر)")
            return

        # إنشاء المصروف باستخدام الأكواد الحقيقية
        expense_data = schemas.Expense(
            date=self.date_input.dateTime().toPyDateTime(),
            category=self.category_combo.currentText(),  # النص المعروض
            amount=self.amount_input.value(),
            description=self.description_input.toPlainText(),
            account_id=selected_category_code,  # كود حساب المصروف (5xxx)
            payment_account_id=selected_payment_code,  # كود حساب الدفع (11xx)
            project_id=selected_project.name if selected_project else None,
        )

        try:
            if self.is_editing:
                # تعديل مصروف موجود
                expense_data._mongo_id = self.expense_to_edit._mongo_id
                expense_id = self.expense_to_edit.id or self.expense_to_edit._mongo_id
                result = self.expense_service.update_expense(expense_id, expense_data)
                if result:
                    QMessageBox.information(self, "تم", "تم حفظ التعديلات بنجاح.")
                    self.accept()
                else:
                    QMessageBox.warning(self, "خطأ", "فشل حفظ التعديلات.")
            else:
                # إضافة مصروف جديد
                self.expense_service.create_expense(expense_data)
                QMessageBox.information(self, "تم", "تم حفظ المصروف بنجاح.")
                self.accept()

        except Exception as e:
            print(f"ERROR: [ExpenseEditorDialog] فشل حفظ المصروف: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")
