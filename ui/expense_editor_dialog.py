# الملف: ui/expense_editor_dialog.py
"""
نافذة إضافة/تعديل المصروفات - تصميم محسن
"""

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.accounting_service import AccountingService
from services.expense_service import ExpenseService
from services.project_service import ProjectService
from services.settings_service import SettingsService
from ui.custom_spinbox import CustomSpinBox
from ui.smart_combobox import SmartFilterComboBox

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class ExpenseEditorDialog(QDialog):
    """نافذة إضافة/تعديل مصروف - تصميم متجاوب"""

    def __init__(
        self,
        expense_service: ExpenseService,
        accounting_service: AccountingService,
        project_service: ProjectService,
        settings_service: SettingsService | None = None,
        expense_to_edit: schemas.Expense | None = None,
        parent=None
    ):
        super().__init__(parent)

        self.expense_service = expense_service
        self.accounting_service = accounting_service
        self.project_service = project_service
        self.settings_service = settings_service
        self.expense_to_edit = expense_to_edit
        self.is_editing = expense_to_edit is not None

        if self.is_editing:
            self.setWindowTitle("تعديل المصروف")
        else:
            self.setWindowTitle("مصروف جديد")

        # 📱 Responsive: حجم مناسب
        self.setMinimumWidth(420)
        self.setMinimumHeight(400)
        self.setMaximumHeight(600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        # جلب البيانات
        self.load_data()
        self.init_ui()

    def load_data(self):
        """جلب الحسابات والمشاريع والفئات من قاعدة البيانات"""
        all_accounts = self.accounting_service.repo.get_all_accounts()
        self.cash_accounts = [acc for acc in all_accounts if acc.code and acc.code.startswith('11')]
        self.projects_list = self.project_service.get_all_projects()

        # جلب فئات المصروفات من المصروفات السابقة
        self.expense_categories = self.expense_service.get_expense_categories()
        # إضافة فئات افتراضية إذا لم توجد فئات
        default_categories = [
            "رواتب وأجور",
            "إيجار",
            "كهرباء ومياه",
            "مواصلات",
            "صيانة",
            "مستلزمات مكتبية",
            "اتصالات وإنترنت",
            "تسويق وإعلان",
            "مصروفات متنوعة"
        ]
        # دمج الفئات الافتراضية مع الفئات الموجودة
        all_categories = set(self.expense_categories) | set(default_categories)
        self.expense_categories = sorted(all_categories)

    def _get_currencies_from_db(self) -> list[tuple]:
        """جلب العملات - الجنيه المصري أولاً دائماً"""
        # الجنيه المصري دائماً أولاً - ثابت ولا يتغير
        default_currencies = [
            ("EGP", "جنيه مصري", "ج.م", 1.00),
            ("USD", "دولار أمريكي", "$", 49.50),
            ("SAR", "ريال سعودي", "ر.س", 13.20),
            ("AED", "درهم إماراتي", "د.إ", 13.48),
        ]
        return default_currencies

    def init_ui(self):
        from ui.styles import BUTTON_STYLES, COLORS, get_arrow_url

        # التخطيط الرئيسي
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # منطقة التمرير للمحتوى
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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

        # المحتوى الداخلي
        content_widget = QWidget()
        content_widget.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(14, 14, 14, 14)

        # ستايل الحقول - مضغوط واحترافي
        field_style = f"""
            QComboBox, QDateEdit {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px;
                font-size: 11px;
                min-height: 16px;
            }}
            QComboBox:hover, QDateEdit:hover {{
                border-color: {COLORS['primary']};
            }}
            QComboBox:focus, QDateEdit:focus {{
                border: 1px solid {COLORS['primary']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: url({get_arrow_url("down")});
                width: 10px;
                height: 10px;
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

        # === المشروع ===
        project_label = QLabel("📁 المشروع")
        project_label.setStyleSheet(label_style)
        content_layout.addWidget(project_label)

        # SmartFilterComboBox مع فلترة ذكية
        self.project_combo = SmartFilterComboBox()
        self.project_combo.setStyleSheet(field_style)
        self.project_combo.addItem("-- بدون مشروع --", userData=None)
        for project in self.projects_list:
            self.project_combo.addItem(project.name, userData=project)
        content_layout.addWidget(self.project_combo)

        # === صف الحسابات ===
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        # من حساب
        pay_container = QVBoxLayout()
        pay_container.setSpacing(2)
        pay_label = QLabel("💳 من حساب")
        pay_label.setStyleSheet(label_style)
        pay_container.addWidget(pay_label)
        # SmartFilterComboBox مع فلترة ذكية
        self.account_combo = SmartFilterComboBox()
        self.account_combo.setStyleSheet(field_style)
        for acc in self.cash_accounts:
            self.account_combo.addItem(acc.name, userData=acc.code)
        self.account_combo.lineEdit().setPlaceholderText("اكتب للبحث...")
        pay_container.addWidget(self.account_combo)
        row1.addLayout(pay_container, 1)

        # إلى حساب (فئة)
        cat_container = QVBoxLayout()
        cat_container.setSpacing(2)
        cat_label = QLabel("📂 فئة المصروف")
        cat_label.setStyleSheet(label_style)
        cat_container.addWidget(cat_label)
        # SmartFilterComboBox مع إمكانية الكتابة الحرة
        self.category_combo = SmartFilterComboBox()
        self.category_combo.setStyleSheet(field_style)
        self.category_combo.setEditable(True)
        # إضافة الفئات من المصروفات السابقة + الافتراضية
        for category in self.expense_categories:
            self.category_combo.addItem(category, userData=category)
        self.category_combo.lineEdit().setPlaceholderText("اكتب فئة جديدة أو اختر...")
        self.category_combo.setCurrentIndex(-1)  # لا يوجد اختيار افتراضي
        cat_container.addWidget(self.category_combo)
        row1.addLayout(cat_container, 1)

        content_layout.addLayout(row1)

        # === صف المبلغ والعملة والتاريخ ===
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        # المبلغ
        amount_container = QVBoxLayout()
        amount_container.setSpacing(2)
        amount_label = QLabel("💰 المبلغ")
        amount_label.setStyleSheet(label_style)
        amount_container.addWidget(amount_label)
        self.amount_input = CustomSpinBox(decimals=2, minimum=0, maximum=9_999_999)
        self.amount_input.setSuffix(" ج.م")
        self.amount_input.valueChanged.connect(self._validate_amount)
        amount_container.addWidget(self.amount_input)
        row2.addLayout(amount_container, 2)

        # العملة
        curr_container = QVBoxLayout()
        curr_container.setSpacing(2)
        curr_label = QLabel("💱 العملة")
        curr_label.setStyleSheet(label_style)
        curr_container.addWidget(curr_label)
        self.currency_combo = QComboBox()
        self.currency_combo.setStyleSheet(field_style)
        currencies_data = self._get_currencies_from_db()
        # الجنيه المصري دائماً أولاً (index 0) بسبب _get_currencies_from_db
        for _idx, (code, name, symbol, rate) in enumerate(currencies_data):
            self.currency_combo.addItem(f"{symbol} {name}", userData={"code": code, "rate": rate})
        # تعيين الجنيه المصري كعملة افتراضية (أول عنصر)
        self.currency_combo.setCurrentIndex(0)
        curr_container.addWidget(self.currency_combo)
        row2.addLayout(curr_container, 1)

        # التاريخ
        date_container = QVBoxLayout()
        date_container.setSpacing(2)
        date_label = QLabel("📅 التاريخ")
        date_label.setStyleSheet(label_style)
        date_container.addWidget(date_label)
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setStyleSheet(field_style)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        date_container.addWidget(self.date_input)
        row2.addLayout(date_container, 1)

        content_layout.addLayout(row2)

        # === الوصف ===
        desc_label = QLabel("📝 الوصف")
        desc_label.setStyleSheet(label_style)
        content_layout.addWidget(desc_label)

        self.description_input = QTextEdit()
        self.description_input.setStyleSheet(field_style)
        self.description_input.setPlaceholderText("وصف المصروف...")
        self.description_input.setFixedHeight(60)
        content_layout.addWidget(self.description_input)

        content_layout.addStretch()

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
        self.save_button.setFixedSize(90, 30)
        self.save_button.clicked.connect(self.save_expense)
        buttons_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.cancel_button.setFixedSize(70, 30)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)

        main_layout.addWidget(buttons_container)

        # Initial validation
        self._validate_amount()

        # تحميل البيانات إذا كان تعديل
        if self.is_editing:
            self.load_expense_data()

    def _validate_amount(self):
        """Real-time amount validation"""
        amount = self.amount_input.value()
        self.save_button.setEnabled(amount > 0)

    def _show_validation_error(self, message: str):
        """Show validation error"""
        QMessageBox.warning(self, "⚠️ تحقق من البيانات", message)

    def load_expense_data(self):
        """تحميل بيانات المصروف للتعديل"""
        exp = self.expense_to_edit

        if exp.project_id:
            for i in range(self.project_combo.count()):
                project = self.project_combo.itemData(i)
                if project and hasattr(project, 'name') and project.name == exp.project_id:
                    self.project_combo.setCurrentIndex(i)
                    break

        # تحميل الفئة - البحث بالنص أو تعيينها مباشرة
        if exp.category:
            found = False
            for i in range(self.category_combo.count()):
                if self.category_combo.itemText(i) == exp.category:
                    self.category_combo.setCurrentIndex(i)
                    found = True
                    break
            if not found:
                # إذا لم توجد الفئة في القائمة، أضفها وحددها
                self.category_combo.addItem(exp.category, userData=exp.category)
                self.category_combo.setCurrentIndex(self.category_combo.count() - 1)

        if hasattr(exp, 'payment_account_id') and exp.payment_account_id:
            for i in range(self.account_combo.count()):
                acc_code = self.account_combo.itemData(i)
                if acc_code == exp.payment_account_id:
                    self.account_combo.setCurrentIndex(i)
                    break

        self.amount_input.setValue(exp.amount)

        if exp.date:
            self.date_input.setDate(QDate(exp.date.year, exp.date.month, exp.date.day))

        self.description_input.setText(exp.description or "")

    def save_expense(self):
        """حفظ المصروف"""
        # الحصول على الفئة - إما من القائمة أو مكتوبة يدوياً
        category_text = self.category_combo.currentText().strip()
        selected_payment_code = self.account_combo.currentData()
        selected_project = self.project_combo.currentData()

        if not category_text:
            self._show_validation_error("⚠️ الرجاء إدخال أو اختيار فئة المصروف")
            return

        if not selected_payment_code:
            self._show_validation_error("⚠️ الرجاء اختيار حساب الدفع")
            return

        if self.amount_input.value() <= 0:
            self._show_validation_error("⚠️ الرجاء إدخال مبلغ صحيح")
            return

        # استخدام حساب الدفع كـ account_id أيضاً (لأنه لا توجد حسابات مصروفات منفصلة)
        expense_data = schemas.Expense(
            date=self.date_input.dateTime().toPyDateTime(),
            category=category_text,
            amount=self.amount_input.value(),
            description=self.description_input.toPlainText(),
            account_id=selected_payment_code,  # نفس حساب الدفع
            payment_account_id=selected_payment_code,
            project_id=selected_project.name if selected_project else None,
        )

        try:
            if self.is_editing:
                expense_data._mongo_id = self.expense_to_edit._mongo_id
                expense_id = self.expense_to_edit.id or self.expense_to_edit._mongo_id
                result = self.expense_service.update_expense(expense_id, expense_data)
                if result:
                    QMessageBox.information(self, "تم", "تم حفظ التعديلات بنجاح.")
                    self.accept()
                else:
                    QMessageBox.warning(self, "خطأ", "فشل حفظ التعديلات.")
            else:
                self.expense_service.create_expense(expense_data)
                QMessageBox.information(self, "تم", "تم حفظ المصروف بنجاح.")
                self.accept()
        except Exception as e:
            safe_print(f"ERROR: [ExpenseEditorDialog] فشل حفظ المصروف: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")


