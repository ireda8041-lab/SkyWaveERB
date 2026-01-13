# الملف: ui/payments_manager.py
"""
تاب إدارة الدفعات - عرض وتعديل جميع الدفعات (تحصيلات العملاء)
⚡ محسّن: إضافة دفعة جديدة، تصفية، تصدير، تكامل محاسبي كامل
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from core import schemas
from services.accounting_service import AccountingService
from services.client_service import ClientService
from services.project_service import ProjectService
from ui.custom_spinbox import CustomSpinBox
from ui.styles import BUTTON_STYLES, TABLE_STYLE_DARK, get_cairo_font, create_centered_item
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


def to_decimal(value) -> Decimal:
    """تحويل آمن للقيم المالية إلى Decimal"""
    if value is None:
        return Decimal('0.00')
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal('0.00')


class NewPaymentDialog(QDialog):
    """
    ⚡ نافذة إضافة دفعة جديدة من التاب الرئيسية
    تدعم: اختيار المشروع، التحقق من المبلغ، التكامل المحاسبي
    """
    payment_created = pyqtSignal(object)  # إشارة عند إنشاء دفعة جديدة

    def __init__(
        self,
        project_service: ProjectService,
        accounting_service: AccountingService,
        client_service: ClientService,
        parent=None,
    ):
        super().__init__(parent)
        self.project_service = project_service
        self.accounting_service = accounting_service
        self.client_service = client_service
        self.selected_project = None

        self.setWindowTitle("💰 إضافة دفعة جديدة")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)
        
        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)
        self.setStyleSheet("""
            * { outline: none; }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
            QPushButton:focus { border: none; outline: none; }
        """)

        self._setup_ui()
        self._load_data()

        # تطبيق الأسهم
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

    def _setup_ui(self):
        """إعداد الواجهة - تصميم احترافي"""
        from ui.styles import COLORS, get_arrow_url
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)
        self.setLayout(layout)

        # ستايل الحقول
        field_style = f"""
            QComboBox, QDateEdit {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 11px;
                min-height: 18px;
            }}
            QComboBox:hover, QDateEdit:hover {{
                border-color: {COLORS['primary']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 22px;
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
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
            }}
        """
        
        label_style = f"color: {COLORS['text_primary']}; font-size: 11px; font-weight: bold;"

        # === قسم المشروع ===
        project_label = QLabel("📁 المشروع")
        project_label.setStyleSheet(label_style)
        layout.addWidget(project_label)

        # SmartFilterComboBox مع فلترة ذكية
        self.project_combo = SmartFilterComboBox()
        self.project_combo.setStyleSheet(field_style)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        layout.addWidget(self.project_combo)

        # معلومات المشروع المالية (تظهر عند اختيار مشروع)
        self.project_info_frame = QFrame()
        self.project_info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(30, 41, 59, 0.6);
                border-radius: 6px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        info_layout = QHBoxLayout(self.project_info_frame)
        info_layout.setContentsMargins(6, 6, 6, 6)
        info_layout.setSpacing(6)

        self.total_label = self._create_info_label("الإجمالي", "0.00", "#3b82f6")
        self.paid_label = self._create_info_label("المدفوع", "0.00", "#10b981")
        self.remaining_label = self._create_info_label("المتبقي", "0.00", "#ef4444")

        info_layout.addWidget(self.total_label)
        info_layout.addWidget(self.paid_label)
        info_layout.addWidget(self.remaining_label)

        layout.addWidget(self.project_info_frame)
        self.project_info_frame.setVisible(False)

        # === قسم الحساب ===
        acc_label = QLabel("💳 الحساب المستلم")
        acc_label.setStyleSheet(label_style)
        layout.addWidget(acc_label)
        
        # SmartFilterComboBox مع فلترة ذكية
        self.account_combo = SmartFilterComboBox()
        self.account_combo.setStyleSheet(field_style)
        self.account_combo.currentIndexChanged.connect(self._update_payment_method)
        layout.addWidget(self.account_combo)

        # === صف المبلغ والتاريخ ===
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        
        # المبلغ
        amount_container = QVBoxLayout()
        amount_container.setSpacing(3)
        amount_label = QLabel("💰 المبلغ")
        amount_label.setStyleSheet(label_style)
        amount_container.addWidget(amount_label)
        self.amount_input = CustomSpinBox(decimals=2, minimum=0.01, maximum=100_000_000)
        self.amount_input.setSuffix(" ج.م")
        self.amount_input.valueChanged.connect(self._validate_payment)
        amount_container.addWidget(self.amount_input)
        row1.addLayout(amount_container, 1)
        
        # التاريخ
        date_container = QVBoxLayout()
        date_container.setSpacing(3)
        date_label = QLabel("📅 التاريخ")
        date_label.setStyleSheet(label_style)
        date_container.addWidget(date_label)
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setStyleSheet(field_style)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        date_container.addWidget(self.date_input)
        row1.addLayout(date_container, 1)
        
        layout.addLayout(row1)

        # === الملاحظات ===
        notes_label = QLabel("📝 ملاحظات")
        notes_label.setStyleSheet(label_style)
        layout.addWidget(notes_label)
        
        self.notes_input = QTextEdit()
        self.notes_input.setStyleSheet(field_style)
        self.notes_input.setPlaceholderText("ملاحظات اختيارية...")
        self.notes_input.setFixedHeight(55)
        layout.addWidget(self.notes_input)
        
        # طريقة الدفع (مخفي - للاستخدام الداخلي)
        self.method_label = QLabel("")
        self.method_label.setVisible(False)
        layout.addWidget(self.method_label)

        layout.addStretch()

        # === أزرار التحكم ===
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()

        self.save_btn = QPushButton("💾 تسجيل الدفعة")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981; color: white;
                padding: 8px 16px; font-weight: bold; border-radius: 6px;
                font-size: 11px; min-width: 110px;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #4b5563; color: #9ca3af; }
        """)
        self.save_btn.setFixedHeight(28)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_payment)
        buttons_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #475569; color: white;
                padding: 8px 16px; border-radius: 6px;
                font-size: 11px; min-width: 80px;
            }
            QPushButton:hover { background-color: #64748b; }
        """)
        self.cancel_btn.setFixedHeight(28)
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        layout.addLayout(buttons_layout)

    def _create_info_label(self, title: str, value: str, color: str) -> QFrame:
        """إنشاء label معلومات مالية"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 5px;
                border: none;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(1)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 9px; background: transparent;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 12px; background: transparent;")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_lbl.setObjectName("value_label")

        layout.addWidget(title_lbl)
        layout.addWidget(value_lbl)
        return frame

    def _load_data(self):
        """تحميل البيانات"""
        # تحميل المشاريع
        try:
            projects = self.project_service.get_all_projects()
            for proj in projects:
                # عرض اسم المشروع مع العميل
                client_name = ""
                if proj.client_id:
                    try:
                        client = self.client_service.get_client_by_id(proj.client_id)
                        if client:
                            client_name = f" ({client.name})"
                    except Exception:
                        pass
                display = f"📁 {proj.name}{client_name}"
                self.project_combo.addItem(display, userData=proj)
            self.project_combo.lineEdit().setPlaceholderText("اكتب للبحث عن المشروع...")
        except Exception as e:
            safe_print(f"ERROR: [NewPaymentDialog] فشل تحميل المشاريع: {e}")

        # تحميل الحسابات
        try:
            accounts = self._get_cash_accounts()
            for acc in accounts:
                display = f"💰 {acc.name} ({acc.code})"
                self.account_combo.addItem(display, userData=acc)
            self.account_combo.lineEdit().setPlaceholderText("اكتب للبحث عن الحساب...")
        except Exception as e:
            safe_print(f"ERROR: [NewPaymentDialog] فشل تحميل الحسابات: {e}")

    def _get_cash_accounts(self) -> list[schemas.Account]:
        """جلب حسابات النقدية والبنوك"""
        try:
            all_accounts = self.accounting_service.repo.get_all_accounts()
            return [
                acc for acc in all_accounts
                if acc.type in [schemas.AccountType.CASH, schemas.AccountType.ASSET]
                and acc.code.startswith("11")
            ]
        except Exception:
            return []

    def _on_project_selected(self, index: int):
        """عند اختيار مشروع"""
        if index < 0:
            self.selected_project = None
            self.project_info_frame.setVisible(False)
            self._validate_payment()
            return

        self.selected_project = self.project_combo.currentData()
        if not self.selected_project:
            self.project_info_frame.setVisible(False)
            self._validate_payment()
            return

        # جلب بيانات الربحية
        try:
            profit_data = self.project_service.get_project_profitability(self.selected_project.name)
            total = profit_data.get("total_revenue", 0)
            paid = profit_data.get("total_paid", 0)
            remaining = profit_data.get("balance_due", 0)

            # تحديث الـ labels
            self.total_label.findChild(QLabel, "value_label").setText(f"{total:,.2f}")
            self.paid_label.findChild(QLabel, "value_label").setText(f"{paid:,.2f}")
            self.remaining_label.findChild(QLabel, "value_label").setText(f"{remaining:,.2f}")

            # تعيين المبلغ الافتراضي للمتبقي
            if remaining > 0:
                self.amount_input.setValue(remaining)

            self.project_info_frame.setVisible(True)
        except Exception as e:
            safe_print(f"ERROR: [NewPaymentDialog] فشل جلب بيانات المشروع: {e}")
            self.project_info_frame.setVisible(False)

        self._validate_payment()

    def _update_payment_method(self):
        """تحديث طريقة الدفع حسب الحساب"""
        account = self.account_combo.currentData()
        if not account:
            self.method_label.setText("---")
            return

        method = self._get_payment_method_from_account(account)
        self.method_label.setText(method)

    def _get_payment_method_from_account(self, account: schemas.Account) -> str:
        """⚡ تحديد طريقة الدفع من الحساب - يدعم نظام 4 و 6 أرقام"""
        if not account:
            return "Other"

        code = account.code or ""
        name = (account.name or "").lower()

        # ⚡ البحث بالاسم أولاً (الأكثر دقة)
        if "vodafone" in name or "فودافون" in name or "v/f" in name or "vf" in name:
            return "Vodafone Cash"
        elif "instapay" in name or "انستاباي" in name:
            return "InstaPay"
        elif "كاش" in name or "cash" in name or "خزينة" in name or "صندوق" in name:
            return "Cash"
        elif "بنك" in name or "bank" in name:
            return "Bank Transfer"
        elif "شيك" in name or "check" in name:
            return "Check"
        
        # ⚡ البحث بالكود (يدعم نظام 4 و 6 أرقام)
        if code in ["1103", "111000"] or code.startswith("1110"):
            return "Vodafone Cash"
        elif code in ["1104"] or "instapay" in code.lower():
            return "InstaPay"
        elif code in ["1101", "111101"] or code.startswith("1111"):
            return "Cash"
        elif code.startswith("1102") or code.startswith("1112"):
            return "Bank Transfer"
            
        return "Other"

    def _validate_payment(self):
        """التحقق من صحة البيانات"""
        is_valid = True

        if not self.selected_project:
            is_valid = False

        if not self.account_combo.currentData():
            is_valid = False

        if self.amount_input.value() <= 0:
            is_valid = False

        self.save_btn.setEnabled(is_valid)

    def _save_payment(self):
        """حفظ الدفعة"""
        if not self.selected_project:
            QMessageBox.warning(self, "⚠️ تنبيه", "يرجى اختيار المشروع أولاً.")
            return

        account = self.account_combo.currentData()
        if not account:
            QMessageBox.warning(self, "⚠️ تنبيه", "يرجى اختيار حساب الاستلام.")
            return

        amount = self.amount_input.value()
        if amount <= 0:
            QMessageBox.warning(self, "⚠️ تنبيه", "يرجى إدخال مبلغ صحيح.")
            return

        # تحذير إذا كان المبلغ أكبر من المتبقي
        try:
            profit_data = self.project_service.get_project_profitability(self.selected_project.name)
            remaining = profit_data.get("balance_due", 0)
            if amount > remaining > 0:
                reply = QMessageBox.question(
                    self,
                    "تأكيد",
                    f"المبلغ المدخل ({amount:,.2f}) أكبر من المتبقي ({remaining:,.2f}).\n\nهل تريد المتابعة؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
        except Exception:
            pass

        try:
            # إنشاء الدفعة
            payment = self.project_service.create_payment_for_project(
                project=self.selected_project,
                amount=amount,
                date=self.date_input.dateTime().toPyDateTime(),
                account_id=account.code
            )

            if payment:
                self.payment_created.emit(payment)
                QMessageBox.information(self, "✅ تم", "تم تسجيل الدفعة بنجاح.")
                self.accept()
            else:
                QMessageBox.warning(self, "خطأ", "فشل تسجيل الدفعة.")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل تسجيل الدفعة: {e}")


class PaymentEditorDialog(QDialog):
    """نافذة تعديل دفعة موجودة"""

    def __init__(
        self,
        payment: schemas.Payment,
        accounts: list[schemas.Account],
        accounting_service: AccountingService,
        project_service: ProjectService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.payment = payment
        self.accounts = accounts
        self.accounting_service = accounting_service
        self.project_service = project_service
        self.original_amount = to_decimal(payment.amount)
        self.original_account_id = payment.account_id

        self.setWindowTitle(f"تعديل دفعة - {payment.project_id}")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        
        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)
        self.setStyleSheet("""
            * { outline: none; }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
            QPushButton:focus { border: none; outline: none; }
        """)

        layout = QVBoxLayout()
        form = QFormLayout()

        # حساب الاستلام (SmartFilterComboBox مع فلترة)
        self.account_combo = SmartFilterComboBox()
        selected_index = 0
        for i, acc in enumerate(accounts):
            display_text = f"💰 {acc.name} ({acc.code})"
            self.account_combo.addItem(display_text, userData=acc)
            if acc.code == payment.account_id:
                selected_index = i
        self.account_combo.setCurrentIndex(selected_index)

        # ربط تغيير الحساب بتحديث طريقة الدفع
        self.account_combo.currentIndexChanged.connect(self._update_payment_method_from_account)

        # المبلغ
        self.amount_input = CustomSpinBox(decimals=2, minimum=0.01, maximum=100_000_000)
        self.amount_input.setSuffix(" ج.م")
        self.amount_input.setValue(payment.amount)
        self.amount_input.setStyleSheet("font-size: 14px; font-weight: bold;")

        # التاريخ
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        if payment.date:
            self.date_input.setDate(QDate(payment.date.year, payment.date.month, payment.date.day))
        else:
            self.date_input.setDate(QDate.currentDate())

        # طريقة الدفع (سيتم تحديثها تلقائياً حسب الحساب)
        self.method_combo = QComboBox()
        methods = ["Bank Transfer", "Cash", "Vodafone Cash", "InstaPay", "Check", "Other"]
        self.method_combo.addItems(methods)
        self.method_combo.setEnabled(False)  # معطل - يتحدد تلقائياً من الحساب

        # تحديد طريقة الدفع الأولية
        if payment.method:
            idx = self.method_combo.findText(payment.method)
            if idx >= 0:
                self.method_combo.setCurrentIndex(idx)

        # تحديث طريقة الدفع حسب الحساب المختار
        self._update_payment_method_from_account()

        form.addRow("الحساب المستلم:", self.account_combo)
        form.addRow("المبلغ:", self.amount_input)
        form.addRow("التاريخ:", self.date_input)
        form.addRow("طريقة الدفع:", self.method_combo)
        layout.addLayout(form)

        # أزرار
        buttons_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 حفظ التعديلات")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0A6CF1; color: white;
                padding: 10px; font-weight: bold; border-radius: 6px;
            }
            QPushButton:hover { background-color: #0A6CF1; }
        """)
        self.save_btn.clicked.connect(self.save_changes)

        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.cancel_btn)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

    def _update_payment_method_from_account(self):
        """⚡ تحديث طريقة الدفع تلقائياً حسب الحساب المختار - يدعم نظام 4 و 6 أرقام"""
        selected_account = self.account_combo.currentData()
        if not selected_account:
            return

        account_name = (selected_account.name or "").lower()
        code = selected_account.code

        # ⚡ البحث بالاسم أولاً (الأكثر دقة)
        if "vodafone" in account_name or "فودافون" in account_name or "v/f" in account_name or "vf" in account_name:
            self.method_combo.setCurrentText("Vodafone Cash")
        elif "instapay" in account_name or "انستاباي" in account_name:
            self.method_combo.setCurrentText("InstaPay")
        elif "كاش" in account_name or "cash" in account_name or "خزينة" in account_name or "صندوق" in account_name:
            self.method_combo.setCurrentText("Cash")
        elif "بنك" in account_name or "bank" in account_name:
            self.method_combo.setCurrentText("Bank Transfer")
        elif "شيك" in account_name or "check" in account_name:
            self.method_combo.setCurrentText("Check")
        # ⚡ البحث بالكود (يدعم نظام 4 و 6 أرقام)
        elif code in ["1103", "111000"] or code.startswith("1110"):
            self.method_combo.setCurrentText("Vodafone Cash")
        elif code in ["1104"] or "instapay" in code.lower():
            self.method_combo.setCurrentText("InstaPay")
        elif code in ["1101", "111101"] or code.startswith("1111"):
            self.method_combo.setCurrentText("Cash")
        elif code.startswith("1102") or code.startswith("1112"):
            self.method_combo.setCurrentText("Bank Transfer")
        else:
            self.method_combo.setCurrentText("Other")

    def save_changes(self):
        selected_account = self.account_combo.currentData()
        new_amount = to_decimal(self.amount_input.value())

        if not selected_account or new_amount <= 0:
            QMessageBox.warning(self, "⚠️ تحقق", "يرجى اختيار الحساب وإدخال مبلغ صحيح.")
            return

        try:
            # تحديث بيانات الدفعة
            self.payment.amount = float(new_amount)
            self.payment.account_id = selected_account.code
            self.payment.date = self.date_input.dateTime().toPyDateTime()
            self.payment.method = self.method_combo.currentText()

            # حفظ في قاعدة البيانات مع تحديث حالة المشروع أوتوماتيك ⚡
            payment_id = self.payment.id or self.payment._mongo_id

            if self.project_service:
                result = self.project_service.update_payment_for_project(payment_id, self.payment)
            else:
                result = self.accounting_service.repo.update_payment(payment_id, self.payment)

            if result:
                # ⚡ القيد المحاسبي يتم تحديثه تلقائياً عبر EventBus (PAYMENT_UPDATED)
                # لا حاجة لعكس القيد يدوياً هنا - الـ AccountingService يتولى ذلك
                QMessageBox.information(self, "تم", "تم تعديل الدفعة وتحديث القيود المحاسبية وحالة المشروع.")
                self.accept()
            else:
                QMessageBox.warning(self, "خطأ", "فشل حفظ التعديلات.")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل تعديل الدفعة: {e}")

    # ⚡ تم إزالة _reverse_and_repost_journal_entry - القيود تُدار عبر EventBus


class PaymentsManagerTab(QWidget):
    """تاب إدارة الدفعات - عرض جميع التحصيلات مع إمكانية التعديل"""

    def __init__(
        self,
        project_service: ProjectService,
        accounting_service: AccountingService,
        client_service: ClientService,
        current_user=None,
        parent=None,
    ):
        super().__init__(parent)

        self.project_service = project_service
        self.accounting_service = accounting_service
        self.client_service = client_service
        self.current_user = current_user

        self.payments_list: list[schemas.Payment] = []
        self.clients_cache: dict[str, str] = {}  # cache للعملاء

        # 📱 تجاوب: سياسة التمدد الكامل
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setup_ui()
        self.apply_permissions()

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals
        app_signals.payments_changed.connect(self._on_payments_changed)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_payments_data() - يتم استدعاؤها من MainWindow

    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # === شريط الأزرار المتجاوب ===
        from ui.responsive_toolbar import ResponsiveToolbar
        self.toolbar = ResponsiveToolbar()

        # ⚡ زر إضافة دفعة جديدة
        self.add_button = QPushButton("➕ إضافة دفعة")
        self.add_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.add_button.setFixedHeight(28)
        self.add_button.clicked.connect(self.open_add_dialog)

        self.edit_button = QPushButton("✏️ تعديل الدفعة")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.open_edit_dialog)

        self.delete_button = QPushButton("🗑️ حذف الدفعة")
        self.delete_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_button.setFixedHeight(28)
        self.delete_button.clicked.connect(self.delete_selected_payment)

        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.setFixedHeight(28)
        self.refresh_button.clicked.connect(self.load_payments_data)

        # إضافة الأزرار للـ toolbar المتجاوب
        self.toolbar.addButton(self.add_button)
        self.toolbar.addButton(self.edit_button)
        self.toolbar.addButton(self.delete_button)
        self.toolbar.addButton(self.refresh_button)
        
        layout.addWidget(self.toolbar)

        # جدول الدفعات
        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(7)
        self.payments_table.setHorizontalHeaderLabels([
            "#", "التاريخ", "النوع", "العميل/المشروع", "المبلغ", "طريقة الدفع", "الحساب"
        ])

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar
        self.search_bar = UniversalSearchBar(
            self.payments_table,
            placeholder="🔍 بحث (التاريخ، النوع، العميل، المشروع، المبلغ، الحساب)..."
        )
        layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===

        h_header = self.payments_table.horizontalHeader()
        v_header = self.payments_table.verticalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # #
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # التاريخ
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # النوع
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # العميل/المشروع - يتمدد
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # المبلغ
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # طريقة الدفع
            h_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # الحساب - يتمدد
        self.payments_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.payments_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.payments_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.payments_table.setAlternatingRowColors(True)
        if v_header is not None:
            v_header.setDefaultSectionSize(45)  # ⚡ ارتفاع الصفوف
            v_header.setVisible(False)

        # ربط الدبل كليك
        self.payments_table.itemDoubleClicked.connect(self.open_edit_dialog)
        
        # إضافة قائمة السياق (كليك يمين)
        self._setup_context_menu()

        self.payments_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.payments_table)
        layout.addWidget(self.payments_table)

        # إجمالي الدفعات
        self.total_label = QLabel("إجمالي التحصيلات: 0.00 ج.م")
        self.total_label.setFont(get_cairo_font(14, bold=True))
        self.total_label.setStyleSheet("color: #0A6CF1; padding: 10px;")
        layout.addWidget(self.total_label, 0, Qt.AlignmentFlag.AlignRight)

    def _setup_context_menu(self):
        """إعداد قائمة السياق (كليك يمين) للجدول"""
        from core.context_menu import ContextMenuManager
        
        ContextMenuManager.setup_table_context_menu(
            table=self.payments_table,
            on_view=self.open_edit_dialog,
            on_edit=self.open_edit_dialog,
            on_delete=self.delete_selected_payment,
            on_refresh=self.load_payments_data
        )

    def load_payments_data(self):
        """⚡ تحميل الدفعات في الخلفية لمنع التجميد"""
        safe_print("INFO: [PaymentsManager] جاري تحميل الدفعات...")

        from PyQt6.QtWidgets import QApplication

        from core.data_loader import get_data_loader

        # تحضير الجدول
        self.payments_table.setUpdatesEnabled(False)
        self.payments_table.blockSignals(True)
        self.payments_table.setRowCount(0)
        QApplication.processEvents()

        # دالة جلب البيانات
        def fetch_payments():
            try:
                payments = self.accounting_service.repo.get_all_payments()
                all_accounts = self.accounting_service.repo.get_all_accounts()
                accounts_cache = {acc.code: acc for acc in all_accounts}

                all_projects = self.project_service.get_all_projects()
                projects_cache = {proj.name: proj for proj in all_projects}

                clients = self.client_service.get_all_clients()
                clients_cache = {}
                for c in clients:
                    # ⚡ إضافة العميل بكل المفاتيح الممكنة للبحث السريع
                    clients_cache[c.name] = c  # بالاسم
                    if c._mongo_id:
                        clients_cache[c._mongo_id] = c  # بالـ MongoDB ID
                        clients_cache[str(c._mongo_id)] = c  # كـ string
                    if c.id:
                        clients_cache[str(c.id)] = c  # بالـ SQLite ID
                        clients_cache[int(c.id)] = c  # كـ int
                    # ⚡ إضافة بالاسم المنظف (بدون مسافات زائدة)
                    if c.name:
                        clients_cache[c.name.strip()] = c

                safe_print(f"DEBUG: [PaymentsManager] تم تحميل {len(clients)} عميل في الـ cache")
                
                return {
                    'payments': payments,
                    'accounts_cache': accounts_cache,
                    'projects_cache': projects_cache,
                    'clients_cache': clients_cache
                }
            except Exception as e:
                safe_print(f"ERROR: [PaymentsManager] فشل جلب الدفعات: {e}")
                import traceback
                traceback.print_exc()
                return {'payments': [], 'accounts_cache': {}, 'projects_cache': {}, 'clients_cache': {}}

        # دالة تحديث الواجهة
        def on_data_loaded(data):
            try:
                self.payments_list = data['payments']
                accounts_cache = data['accounts_cache']
                projects_cache = data['projects_cache']
                clients_cache = data['clients_cache']

                total_sum = 0.0
                batch_size = 15

                for i, payment in enumerate(self.payments_list):
                    self.payments_table.insertRow(i)

                    num_item = create_centered_item(str(i + 1))
                    num_item.setData(Qt.ItemDataRole.UserRole, payment)
                    self.payments_table.setItem(i, 0, num_item)

                    date_str = payment.date.strftime("%Y-%m-%d") if payment.date else ""
                    self.payments_table.setItem(i, 1, create_centered_item(date_str))

                    type_item = create_centered_item("💰 وارد")
                    type_item.setForeground(QColor("#0A6CF1"))
                    self.payments_table.setItem(i, 2, type_item)

                    client_name = "عميل غير محدد"
                    project_name = payment.project_id or "مشروع غير محدد"

                    # ⚡ إصلاح: البحث عن العميل بطرق متعددة
                    # 1. أولاً: استخدام client_id من الدفعة مباشرة (الأولوية الأعلى)
                    if payment.client_id and payment.client_id.strip():
                        client_name = payment.client_id.strip()
                    
                    # 2. ثانياً: البحث في المشروع
                    if client_name == "عميل غير محدد" and payment.project_id:
                        if payment.project_id in projects_cache:
                            project = projects_cache[payment.project_id]
                            project_name = project.name
                            if project.client_id and project.client_id.strip():
                                client_name = project.client_id.strip()
                        else:
                            # المشروع غير موجود في الـ cache - ابحث بالاسم الجزئي
                            for proj_name, proj in projects_cache.items():
                                if payment.project_id in proj_name or proj_name in payment.project_id:
                                    project_name = proj.name
                                    if proj.client_id and proj.client_id.strip():
                                        client_name = proj.client_id.strip()
                                    break

                    self.payments_table.setItem(i, 3, create_centered_item(f"{client_name} - {project_name}"))

                    amount_item = create_centered_item(f"{payment.amount:,.2f}")
                    amount_item.setForeground(QColor("#0A6CF1"))
                    self.payments_table.setItem(i, 4, amount_item)

                    payment_method = self._get_payment_method_from_account(payment.account_id, accounts_cache)
                    self.payments_table.setItem(i, 5, create_centered_item(payment_method))

                    account_display = "---"
                    if payment.account_id and payment.account_id in accounts_cache:
                        account = accounts_cache[payment.account_id]
                        account_display = f"{account.name} ({account.code})"
                    elif payment.account_id:
                        account_display = payment.account_id

                    self.payments_table.setItem(i, 6, create_centered_item(account_display))

                    self.payments_table.setRowHeight(i, 40)
                    total_sum += payment.amount

                    if (i + 1) % batch_size == 0:
                        QApplication.processEvents()

                self.total_label.setText(f"إجمالي التحصيلات: {total_sum:,.2f} ج.م")
                safe_print(f"INFO: [PaymentsManager] ✅ تم تحميل {len(self.payments_list)} دفعة.")

            except Exception as e:
                safe_print(f"ERROR: [PaymentsManager] فشل تحديث الجدول: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.payments_table.blockSignals(False)
                self.payments_table.setUpdatesEnabled(True)
                QApplication.processEvents()

        def on_error(error_msg):
            safe_print(f"ERROR: [PaymentsManager] فشل تحميل الدفعات: {error_msg}")
            self.payments_table.blockSignals(False)
            self.payments_table.setUpdatesEnabled(True)

        # تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="payments_list",
            load_function=fetch_payments,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True
        )

    def _on_payments_changed(self):
        """⚡ استجابة لإشارة تحديث الدفعات - تحديث الجدول أوتوماتيك"""
        safe_print("INFO: [PaymentsManager] ⚡ استلام إشارة تحديث الدفعات - جاري التحديث...")
        # ⚡ إبطال الـ cache أولاً لضمان جلب البيانات الجديدة من السيرفر
        if hasattr(self.project_service, 'invalidate_cache'):
            self.project_service.invalidate_cache()
        self.load_payments_data()

    def get_selected_payment(self) -> schemas.Payment | None:
        """الحصول على الدفعة المحددة"""
        # محاولة الحصول على الصف من الخلية المحددة
        current_item = self.payments_table.currentItem()
        if current_item:
            current_row = current_item.row()
        else:
            current_row = self.payments_table.currentRow()

        if current_row < 0 or current_row >= len(self.payments_list):
            return None

        # الحصول على البيانات من العمود الأول (الرقم)
        num_item = self.payments_table.item(current_row, 0)
        if not num_item:
            return None

        payment = num_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(payment, schemas.Payment):
            return payment

        # fallback: استخدام الفهرس مباشرة
        if 0 <= current_row < len(self.payments_list):
            p = self.payments_list[current_row]
            if isinstance(p, schemas.Payment):
                return p

        return None

    def open_edit_dialog(self):
        """فتح نافذة تعديل الدفعة"""
        selected_payment = self.get_selected_payment()
        if not selected_payment:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد دفعة أولاً.")
            return

        # جلب حسابات البنك/الخزينة
        accounts = self._get_cash_accounts()

        dialog = PaymentEditorDialog(
            payment=selected_payment,
            accounts=accounts,
            accounting_service=self.accounting_service,
            project_service=self.project_service,
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_payments_data()

    def _get_cash_accounts(self) -> list[schemas.Account]:
        """جلب حسابات النقدية والبنوك"""
        try:
            all_accounts = self.accounting_service.repo.get_all_accounts()
            cash_accounts = [
                acc for acc in all_accounts
                if acc.type in [schemas.AccountType.CASH, schemas.AccountType.ASSET]
                and acc.code.startswith("11")  # حسابات النقدية تبدأ بـ 11
            ]
            return cash_accounts
        except Exception as e:
            safe_print(f"ERROR: [PaymentsManager] فشل جلب حسابات النقدية: {e}")
            return []

    def _get_payment_method_from_account(self, account_code: str, accounts_cache: dict) -> str:
        """⚡ تحديد طريقة الدفع من كود الحساب - يدعم نظام 4 و 6 أرقام"""
        if not account_code or account_code not in accounts_cache:
            return "---"

        account = accounts_cache[account_code]
        account_name = (account.name or "").lower()
        code = account_code

        # ⚡ البحث بالاسم أولاً (الأكثر دقة)
        if "vodafone" in account_name or "فودافون" in account_name or "v/f" in account_name or "vf" in account_name:
            return "Vodafone Cash"
        elif "instapay" in account_name or "انستاباي" in account_name:
            return "InstaPay"
        elif "كاش" in account_name or "cash" in account_name or "خزينة" in account_name or "صندوق" in account_name:
            return "Cash"
        elif "بنك" in account_name or "bank" in account_name:
            return "Bank Transfer"
        elif "شيك" in account_name or "check" in account_name:
            return "Check"
        
        # ⚡ البحث بالكود (يدعم نظام 4 و 6 أرقام)
        if code in ["1103", "111000"] or code.startswith("1110"):
            return "Vodafone Cash"
        elif code in ["1104"] or "instapay" in code.lower():
            return "InstaPay"
        elif code in ["1101", "111101"] or code.startswith("1111"):
            return "Cash"
        elif code.startswith("1102") or code.startswith("1112"):
            return "Bank Transfer"

        return "Other"

    def open_add_dialog(self):
        """⚡ فتح نافذة إضافة دفعة جديدة"""
        dialog = NewPaymentDialog(
            project_service=self.project_service,
            accounting_service=self.accounting_service,
            client_service=self.client_service,
            parent=self
        )
        dialog.payment_created.connect(self._on_payment_created)
        dialog.exec()

    def _on_payment_created(self, payment):
        """⚡ استجابة لإنشاء دفعة جديدة"""
        safe_print(f"INFO: [PaymentsManager] تم إنشاء دفعة جديدة: {payment.amount}")
        self.load_payments_data()

    def apply_permissions(self):
        """تطبيق الصلاحيات حسب دور المستخدم"""
        if not self.current_user:
            return

        from core.auth_models import UserRole

        user_role = self.current_user.role
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role)
            except ValueError:
                user_role = UserRole.SALES

        # المحاسب والمدير لهم صلاحيات كاملة
        if user_role in [UserRole.ADMIN, UserRole.ACCOUNTANT]:
            self.add_button.setEnabled(True)
            self.edit_button.setEnabled(True)
            self.delete_button.setEnabled(True)
        else:
            # مندوب المبيعات: قراءة فقط
            self.add_button.setEnabled(False)
            self.edit_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.add_button.setToolTip("ليس لديك صلاحية إضافة الدفعات")
            self.edit_button.setToolTip("ليس لديك صلاحية تعديل الدفعات")
            self.delete_button.setToolTip("ليس لديك صلاحية حذف الدفعات")

    def delete_selected_payment(self):
        """حذف الدفعة المحددة مع عكس القيد المحاسبي وتحديث حالة المشروع"""
        selected_payment = self.get_selected_payment()
        if not selected_payment:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد دفعة أولاً.")
            return

        amount = to_decimal(selected_payment.amount)
        date_str = selected_payment.date.strftime('%Y-%m-%d') if selected_payment.date else 'غير محدد'

        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف الدفعة؟\n\n"
            f"المشروع: {selected_payment.project_id}\n"
            f"المبلغ: {amount:,.2f} ج.م\n"
            f"التاريخ: {date_str}\n\n"
            f"⚠️ سيتم عكس القيد المحاسبي المرتبط بهذه الدفعة.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            # ⚡ حذف الدفعة - القيد العكسي يتم تلقائياً عبر EventBus (PAYMENT_DELETED)
            payment_id = selected_payment.id or selected_payment._mongo_id
            project_name = selected_payment.project_id
            result = self.project_service.delete_payment_for_project(payment_id, project_name)

            if result:
                QMessageBox.information(
                    self,
                    "تم الحذف",
                    "تم حذف الدفعة وعكس القيد المحاسبي وتحديث حالة المشروع بنجاح."
                )
                self.load_payments_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل حذف الدفعة.")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل حذف الدفعة: {e}")
            safe_print(f"ERROR: [PaymentsManager] فشل حذف الدفعة: {e}")
