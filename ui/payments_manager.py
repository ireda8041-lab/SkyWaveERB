# الملف: ui/payments_manager.py
"""
تاب إدارة الدفعات - عرض وتعديل جميع الدفعات (تحصيلات العملاء)
⚡ محسّن: إضافة دفعة جديدة، تصفية، تصدير، تكامل محاسبي كامل
"""

import time
from decimal import ROUND_HALF_UP, Decimal

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.accounting_service import AccountingService
from services.client_service import ClientService
from services.project_service import ProjectService
from ui.custom_spinbox import CustomSpinBox
from ui.smart_combobox import SmartFilterComboBox
from ui.styles import BUTTON_STYLES, TABLE_STYLE_DARK, create_centered_item, get_cairo_font

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
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


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
        self.setStyleSheet(
            """
            * { outline: none; }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
            QPushButton:focus { border: none; outline: none; }
        """
        )

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
        self.project_info_frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: rgba(30, 41, 59, 0.6);
                border-radius: 6px;
                border: 1px solid {COLORS['border']};
            }}
        """
        )
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
        self.save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #10b981; color: white;
                padding: 8px 16px; font-weight: bold; border-radius: 6px;
                font-size: 11px; min-width: 110px;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #4b5563; color: #9ca3af; }
        """
        )
        self.save_btn.setFixedHeight(28)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_payment)
        buttons_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #475569; color: white;
                padding: 8px 16px; border-radius: 6px;
                font-size: 11px; min-width: 80px;
            }
            QPushButton:hover { background-color: #64748b; }
        """
        )
        self.cancel_btn.setFixedHeight(28)
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        layout.addLayout(buttons_layout)

    def _create_info_label(self, title: str, value: str, color: str) -> QFrame:
        """إنشاء label معلومات مالية"""
        frame = QFrame()
        frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {color};
                border-radius: 5px;
                border: none;
            }}
        """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(1)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.8); font-size: 9px; background: transparent;"
        )
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(
            "color: white; font-weight: bold; font-size: 12px; background: transparent;"
        )
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
                acc
                for acc in all_accounts
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
            project_ref = str(
                getattr(self.selected_project, "id", None)
                or getattr(self.selected_project, "_mongo_id", None)
                or self.selected_project.name
            )
            profit_data = self.project_service.get_project_profitability(
                project_ref,
                client_id=getattr(self.selected_project, "client_id", None),
            )
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

    def _get_payment_method_from_account(self, account: schemas.Account | None) -> str:
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
        # ⚡ منع الضغط المزدوج - تعطيل الزر فوراً
        if not self.save_btn.isEnabled():
            return
        self.save_btn.setEnabled(False)
        self.save_btn.setText("جاري الحفظ...")

        if not self.selected_project:
            QMessageBox.warning(self, "⚠️ تنبيه", "يرجى اختيار المشروع أولاً.")
            self.save_btn.setEnabled(True)
            self.save_btn.setText("💾 تسجيل الدفعة")
            return

        account = self.account_combo.currentData()
        if not account:
            QMessageBox.warning(self, "⚠️ تنبيه", "يرجى اختيار حساب الاستلام.")
            self.save_btn.setEnabled(True)
            self.save_btn.setText("💾 تسجيل الدفعة")
            return

        amount = self.amount_input.value()
        if amount <= 0:
            QMessageBox.warning(self, "⚠️ تنبيه", "يرجى إدخال مبلغ صحيح.")
            self.save_btn.setEnabled(True)
            self.save_btn.setText("💾 تسجيل الدفعة")
            return

        # تحذير إذا كان المبلغ أكبر من المتبقي
        try:
            project_ref = str(
                getattr(self.selected_project, "id", None)
                or getattr(self.selected_project, "_mongo_id", None)
                or self.selected_project.name
            )
            profit_data = self.project_service.get_project_profitability(
                project_ref,
                client_id=getattr(self.selected_project, "client_id", None),
            )
            remaining = profit_data.get("balance_due", 0)
            if amount > remaining > 0:
                reply = QMessageBox.question(
                    self,
                    "تأكيد",
                    f"المبلغ المدخل ({amount:,.2f}) أكبر من المتبقي ({remaining:,.2f}).\n\nهل تريد المتابعة؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    self.save_btn.setEnabled(True)
                    self.save_btn.setText("💾 تسجيل الدفعة")
                    return
        except Exception:
            pass

        try:
            # إنشاء الدفعة
            payment = self.project_service.create_payment_for_project(
                project=self.selected_project,
                amount=amount,
                date=self.date_input.dateTime().toPyDateTime(),
                account_id=account.code,
            )

            if payment:
                self.payment_created.emit(payment)
                QMessageBox.information(self, "✅ تم", "تم تسجيل الدفعة بنجاح.")
                self.accept()
            else:
                QMessageBox.warning(self, "خطأ", "فشل تسجيل الدفعة.")
                self.save_btn.setEnabled(True)
                self.save_btn.setText("💾 تسجيل الدفعة")

        except Exception as e:
            error_msg = str(e)
            if "مكررة" in error_msg or "duplicate" in error_msg.lower():
                QMessageBox.warning(self, "⚠️ دفعة مكررة", f"يوجد دفعة بنفس البيانات:\n{error_msg}")
            else:
                QMessageBox.critical(self, "خطأ", f"فشل تسجيل الدفعة: {e}")
            self.save_btn.setEnabled(True)
            self.save_btn.setText("💾 تسجيل الدفعة")


class PaymentEditorDialog(QDialog):
    """نافذة تعديل دفعة موجودة"""

    def __init__(
        self,
        *,
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
        self.selected_project: schemas.Project | None = None
        self._projects_loaded = False
        self._client_name_cache: dict[str, str] = {}
        self._project_invoice_cache: dict[str, str] = {}

        self.setWindowTitle(f"تعديل دفعة - {payment.project_id}")
        self.setMinimumWidth(560)
        self.setMinimumHeight(500)

        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar

        setup_custom_title_bar(self)
        self.setStyleSheet(
            """
            * { outline: none; }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
            QPushButton:focus { border: none; outline: none; }
        """
        )

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        # المشروع المرتبط
        self.project_frame = QFrame()
        self.project_frame.setStyleSheet(
            """
            QFrame {
                background-color: rgba(15, 23, 42, 0.72);
                border: 1px solid rgba(59, 130, 246, 0.22);
                border-radius: 10px;
            }
            QLabel {
                background: transparent;
            }
        """
        )
        project_layout = QVBoxLayout(self.project_frame)
        project_layout.setContentsMargins(12, 12, 12, 12)
        project_layout.setSpacing(8)

        project_header = QHBoxLayout()
        project_header.setSpacing(8)
        self.project_section_title = QLabel("المشروع المرتبط")
        self.project_section_title.setFont(get_cairo_font(12, bold=True))
        self.project_section_title.setStyleSheet("color: #e2e8f0;")

        self.change_project_btn = QPushButton("تغيير المشروع المرتبط")
        self.change_project_btn.setFixedHeight(30)
        self.change_project_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.change_project_btn.clicked.connect(self._toggle_project_picker)

        project_header.addWidget(self.project_section_title)
        project_header.addStretch()
        project_header.addWidget(self.change_project_btn)
        project_layout.addLayout(project_header)

        self.project_name_label = QLabel("")
        self.project_name_label.setFont(get_cairo_font(12, bold=True))
        self.project_name_label.setStyleSheet("color: #f8fafc;")
        project_layout.addWidget(self.project_name_label)

        self.project_meta_label = QLabel("")
        self.project_meta_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        project_layout.addWidget(self.project_meta_label)

        self.project_invoice_label = QLabel("")
        self.project_invoice_label.setStyleSheet(
            "color: #38bdf8; font-size: 11px; font-weight: bold;"
        )
        project_layout.addWidget(self.project_invoice_label)

        self.project_picker_frame = QFrame()
        self.project_picker_frame.setVisible(False)
        self.project_picker_frame.setStyleSheet(
            """
            QFrame {
                background-color: transparent;
                border: none;
            }
        """
        )
        picker_layout = QVBoxLayout(self.project_picker_frame)
        picker_layout.setContentsMargins(0, 4, 0, 0)
        picker_layout.setSpacing(6)

        self.project_search_hint = QLabel(
            "ابحث باسم المشروع أو رقم الفاتورة أو اسم العميل ثم اختر النتيجة."
        )
        self.project_search_hint.setStyleSheet("color: #94a3b8; font-size: 10px;")
        picker_layout.addWidget(self.project_search_hint)

        self.project_combo = SmartFilterComboBox()
        self.project_combo.setMinimumWidth(320)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        picker_layout.addWidget(self.project_combo)

        project_layout.addWidget(self.project_picker_frame)
        layout.addWidget(self.project_frame)

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
        form.addRow("رقم الفاتورة:", self._build_invoice_badge())
        layout.addLayout(form)

        # أزرار
        buttons_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 حفظ التعديلات")
        self.save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #0A6CF1; color: white;
                padding: 10px; font-weight: bold; border-radius: 6px;
            }
            QPushButton:hover { background-color: #0A6CF1; }
        """
        )
        self.save_btn.clicked.connect(self.save_changes)

        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.cancel_btn)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

        self._load_project_options()
        self._refresh_project_summary()

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets

        apply_arrows_to_all_widgets(self)

    def _build_invoice_badge(self) -> QLabel:
        self.invoice_value_label = QLabel("")
        self.invoice_value_label.setMinimumHeight(28)
        self.invoice_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.invoice_value_label.setStyleSheet(
            """
            QLabel {
                color: #f8fafc;
                background-color: rgba(14, 165, 233, 0.16);
                border: 1px solid rgba(14, 165, 233, 0.25);
                border-radius: 8px;
                padding: 6px 10px;
                font-weight: bold;
            }
        """
        )
        return self.invoice_value_label

    def _project_ref(self, project: schemas.Project | None, fallback: str = "") -> str:
        if project is None:
            return str(fallback or "").strip()
        if self.project_service and hasattr(self.project_service, "_project_ref"):
            return str(
                self.project_service._project_ref(project, fallback or project.name) or ""
            ).strip()
        return str(
            getattr(project, "id", None)
            or getattr(project, "_mongo_id", None)
            or getattr(project, "name", fallback)
            or ""
        ).strip()

    def _get_client_name(self, client_id: str) -> str:
        client_ref = str(client_id or "").strip()
        if not client_ref:
            return ""
        if client_ref in self._client_name_cache:
            return self._client_name_cache[client_ref]
        if not self.project_service:
            return client_ref
        repo = getattr(self.project_service, "repo", None)
        if repo is None or not hasattr(repo, "get_client_by_id"):
            return client_ref
        try:
            client = repo.get_client_by_id(client_ref)
            client_name = str(getattr(client, "name", "") or client_ref).strip()
            self._client_name_cache[client_ref] = client_name
            return client_name
        except Exception:
            return client_ref

    def _resolve_invoice_number_for_project(
        self, project: schemas.Project | None, *, ensure: bool = False
    ) -> str:
        if project is None:
            return str(getattr(self.payment, "invoice_number", "") or "").strip()
        project_ref = self._project_ref(project, project.name)
        if project_ref in self._project_invoice_cache:
            return self._project_invoice_cache[project_ref]
        invoice_number = str(getattr(project, "invoice_number", "") or "").strip()
        if invoice_number:
            self._project_invoice_cache[project_ref] = invoice_number
            return invoice_number
        repo = getattr(self.project_service, "repo", None) if self.project_service else None
        if repo is not None and hasattr(repo, "get_invoice_number_for_project"):
            try:
                invoice_number = str(
                    repo.get_invoice_number_for_project(
                        project_ref,
                        getattr(project, "client_id", None),
                    )
                    or ""
                ).strip()
                if invoice_number:
                    self._project_invoice_cache[project_ref] = invoice_number
                return invoice_number
            except Exception:
                pass
        if ensure and repo is not None and hasattr(repo, "ensure_invoice_number"):
            try:
                invoice_number = str(
                    repo.ensure_invoice_number(
                        project_ref,
                        getattr(project, "client_id", None),
                    )
                    or ""
                ).strip()
                if invoice_number:
                    self._project_invoice_cache[project_ref] = invoice_number
                return invoice_number
            except Exception:
                return ""
        return ""

    def _project_display_text(self, project: schemas.Project) -> str:
        project_name = str(getattr(project, "name", "") or "").strip() or "بدون اسم"
        client_name = self._get_client_name(getattr(project, "client_id", "") or "")
        invoice_number = self._resolve_invoice_number_for_project(project)
        extra_parts = []
        if invoice_number:
            extra_parts.append(f"فاتورة: {invoice_number}")
        if client_name:
            extra_parts.append(f"عميل: {client_name}")
        suffix = f" - {' - '.join(extra_parts)}" if extra_parts else ""
        return f"📁 {project_name}{suffix}"

    def _project_matches_payment(self, project: schemas.Project) -> bool:
        payment_project_ref = str(getattr(self.payment, "project_id", "") or "").strip()
        payment_invoice_number = str(getattr(self.payment, "invoice_number", "") or "").strip()
        candidates = {
            self._project_ref(project, getattr(project, "name", "")),
            str(getattr(project, "id", "") or "").strip(),
            str(getattr(project, "_mongo_id", "") or "").strip(),
            str(getattr(project, "name", "") or "").strip(),
            str(getattr(project, "invoice_number", "") or "").strip(),
        }
        candidates = {candidate for candidate in candidates if candidate}
        return payment_project_ref in candidates or (
            payment_invoice_number and payment_invoice_number in candidates
        )

    def _load_project_options(self):
        if not self.project_service or self._projects_loaded:
            if not self.project_service:
                self.change_project_btn.setEnabled(False)
                self.change_project_btn.setToolTip("خدمة المشاريع غير متاحة في هذا السياق.")
            return
        self._projects_loaded = True
        self.project_combo.clear()
        try:
            repo = getattr(self.project_service, "repo", None)
            if repo is not None and hasattr(repo, "get_all_clients"):
                for client in repo.get_all_clients() or []:
                    client_name = str(getattr(client, "name", "") or "").strip()
                    if not client_name:
                        continue
                    client_id = str(getattr(client, "id", "") or "").strip()
                    mongo_id = str(getattr(client, "_mongo_id", "") or "").strip()
                    if client_id:
                        self._client_name_cache[client_id] = client_name
                    if mongo_id:
                        self._client_name_cache[mongo_id] = client_name
            if repo is not None and hasattr(repo, "get_all_invoice_numbers"):
                self._project_invoice_cache.update(repo.get_all_invoice_numbers() or {})
            projects = self.project_service.get_all_projects() or []
            projects = sorted(
                projects,
                key=lambda project: (
                    str(getattr(project, "name", "") or "").strip().lower(),
                    str(getattr(project, "invoice_number", "") or "").strip().lower(),
                ),
            )
            selected_index = -1
            for index, project in enumerate(projects):
                self.project_combo.addItem(self._project_display_text(project), userData=project)
                if selected_index < 0 and self._project_matches_payment(project):
                    selected_index = index
                    self.selected_project = project
            self.project_combo.lineEdit().setPlaceholderText(
                "اكتب اسم المشروع أو رقم الفاتورة أو العميل..."
            )
            if selected_index >= 0:
                self.project_combo.setCurrentIndex(selected_index)
            elif projects:
                self.selected_project = None
        except Exception as exc:
            safe_print(f"ERROR: [PaymentEditorDialog] فشل تحميل المشاريع: {exc}")
            self.change_project_btn.setEnabled(False)
            self.project_search_hint.setText("تعذر تحميل المشاريع حاليًا.")

    def _toggle_project_picker(self):
        if not self.project_service:
            return
        visible = not self.project_picker_frame.isVisible()
        self.project_picker_frame.setVisible(visible)
        self.change_project_btn.setText("إخفاء البحث" if visible else "تغيير المشروع المرتبط")
        if visible and self.project_combo.lineEdit():
            self.project_combo.lineEdit().setFocus()
            self.project_combo.lineEdit().selectAll()

    def _on_project_selected(self, index: int):
        if index < 0:
            return
        selected_project = self.project_combo.currentData()
        if not selected_project:
            return
        self.selected_project = selected_project
        self._refresh_project_summary()

    def _refresh_project_summary(self):
        project = self.selected_project
        project_name = str(getattr(self.payment, "project_id", "") or "").strip() or "غير محدد"
        client_name = self._get_client_name(getattr(self.payment, "client_id", "") or "")
        invoice_number = str(getattr(self.payment, "invoice_number", "") or "").strip()
        if project is not None:
            project_name = str(getattr(project, "name", project_name) or project_name).strip()
            client_name = self._get_client_name(getattr(project, "client_id", "") or "")
            invoice_number = self._resolve_invoice_number_for_project(project, ensure=True)
        self.project_name_label.setText(project_name)
        self.project_meta_label.setText(f"العميل المرتبط: {client_name or 'غير محدد'}")
        self.project_invoice_label.setText(
            f"رقم الفاتورة المرتبط: {invoice_number or 'غير محدد حتى الآن'}"
        )
        self.invoice_value_label.setText(invoice_number or "غير محدد")
        self.setWindowTitle(f"تعديل دفعة - {project_name}")

    def _update_payment_method_from_account(self):
        """⚡ تحديث طريقة الدفع تلقائياً حسب الحساب المختار - يدعم نظام 4 و 6 أرقام"""
        selected_account = self.account_combo.currentData()
        if not selected_account:
            return

        account_name = (selected_account.name or "").lower()
        code = selected_account.code

        # ⚡ البحث بالاسم أولاً (الأكثر دقة)
        if (
            "vodafone" in account_name
            or "فودافون" in account_name
            or "v/f" in account_name
            or "vf" in account_name
        ):
            self.method_combo.setCurrentText("Vodafone Cash")
        elif "instapay" in account_name or "انستاباي" in account_name:
            self.method_combo.setCurrentText("InstaPay")
        elif (
            "كاش" in account_name
            or "cash" in account_name
            or "خزينة" in account_name
            or "صندوق" in account_name
        ):
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
            new_account_id = selected_account.code

            # تحديث بيانات الدفعة
            self.payment.amount = float(new_amount)
            self.payment.account_id = new_account_id
            self.payment.date = self.date_input.dateTime().toPyDateTime()
            self.payment.method = self.method_combo.currentText()
            if self.selected_project is not None:
                self.payment.project_id = self._project_ref(
                    self.selected_project,
                    str(getattr(self.payment, "project_id", "") or ""),
                )
                self.payment.client_id = str(
                    getattr(self.selected_project, "client_id", "") or self.payment.client_id or ""
                ).strip()
                self.payment.invoice_number = self._resolve_invoice_number_for_project(
                    self.selected_project, ensure=True
                )
            elif self.project_service and not getattr(self.payment, "invoice_number", None):
                repo = getattr(self.project_service, "repo", None)
                if repo is not None and hasattr(repo, "ensure_invoice_number"):
                    self.payment.invoice_number = repo.ensure_invoice_number(
                        self.payment.project_id,
                        self.payment.client_id or None,
                    )

            payment_id = self.payment.id or self.payment._mongo_id

            if self.project_service:
                result = self.project_service.update_payment_for_project(payment_id, self.payment)
            else:
                result = self.accounting_service.repo.update_payment(payment_id, self.payment)

            if result:
                # ⚡ إعادة حساب أرصدة الحسابات المتأثرة فوراً
                if self.accounting_service:
                    self.accounting_service._schedule_cash_recalc()

                # ⚡ إرسال إشارات التحديث
                from core.signals import app_signals

                app_signals.emit_data_changed("payments")
                app_signals.emit_data_changed("accounting")

                QMessageBox.information(self, "تم", "تم تعديل الدفعة بنجاح")
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
        *,
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
        self._lookups_cache: dict[str, dict] = {}
        self._lookups_cache_ts: dict[str, float] = {}
        self._lookups_cache_ttl_s = 30.0
        self._current_page = 1
        self._page_size = 100
        self._page_accounts_cache: dict = {}
        self._page_projects_cache: dict = {}
        self._page_clients_cache: dict = {}
        self._total_payments_sum = 0.0

        # 📱 تجاوب: سياسة التمدد الكامل
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setup_ui()
        self.apply_permissions()

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals

        app_signals.safe_connect(app_signals.payments_changed, self._on_payments_changed)
        app_signals.safe_connect(app_signals.clients_changed, self._invalidate_lookup_cache)
        app_signals.safe_connect(app_signals.projects_changed, self._invalidate_lookup_cache)
        app_signals.safe_connect(app_signals.accounts_changed, self._invalidate_lookup_cache)

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
        self.payments_table.setColumnCount(8)
        self.payments_table.setHorizontalHeaderLabels(
            [
                "#",
                "التاريخ",
                "النوع",
                "العميل/المشروع",
                "رقم الفاتورة",
                "المبلغ",
                "طريقة الدفع",
                "الحساب",
            ]
        )

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar

        self.search_bar = UniversalSearchBar(
            self.payments_table,
            placeholder="🔍 بحث (التاريخ، العميل، المشروع، رقم الفاتورة، المبلغ، الحساب)...",
        )
        layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===

        h_header = self.payments_table.horizontalHeader()
        v_header = self.payments_table.verticalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # #
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # التاريخ
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # النوع
            h_header.setSectionResizeMode(
                3, QHeaderView.ResizeMode.Stretch
            )  # العميل/المشروع - يتمدد
            h_header.setSectionResizeMode(
                4, QHeaderView.ResizeMode.ResizeToContents
            )  # رقم الفاتورة
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # المبلغ
            h_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # طريقة الدفع
            h_header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # الحساب - يتمدد
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

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 6, 0, 0)
        pagination_layout.setSpacing(8)

        self.prev_page_button = QPushButton("◀ السابق")
        self.prev_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.prev_page_button.setFixedHeight(26)
        self.prev_page_button.clicked.connect(self._go_prev_page)

        self.next_page_button = QPushButton("التالي ▶")
        self.next_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.next_page_button.setFixedHeight(26)
        self.next_page_button.clicked.connect(self._go_next_page)

        self.page_info_label = QLabel("صفحة 1 / 1")
        self.page_info_label.setFont(get_cairo_font(11, bold=True))
        self.page_info_label.setStyleSheet("color: #94a3b8;")

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["50", "100", "200", "كل"])
        self.page_size_combo.setCurrentText("100")
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)

        pagination_layout.addWidget(self.prev_page_button)
        pagination_layout.addWidget(self.next_page_button)
        pagination_layout.addStretch(1)
        pagination_layout.addWidget(QLabel("حجم الصفحة:"))
        pagination_layout.addWidget(self.page_size_combo)
        pagination_layout.addWidget(self.page_info_label)
        layout.addLayout(pagination_layout)

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
            on_refresh=self.load_payments_data,
        )

    def load_payments_data(self, force_refresh: bool = False):
        """⚡ تحميل الدفعات في الخلفية لمنع التجميد"""
        safe_print("INFO: [PaymentsManager] جاري تحميل الدفعات...")

        from core.data_loader import get_data_loader

        # تحضير الجدول
        sorting_enabled = self.payments_table.isSortingEnabled()
        if sorting_enabled:
            self.payments_table.setSortingEnabled(False)
        self.payments_table.setUpdatesEnabled(False)
        self.payments_table.blockSignals(True)
        self.payments_table.setRowCount(0)

        # دالة جلب البيانات
        def fetch_payments():
            try:
                payments = self.accounting_service.repo.get_all_payments()

                accounts_cache = self._get_cached_lookup("accounts")
                if accounts_cache is None:
                    if hasattr(self.accounting_service, "get_all_accounts_cached"):
                        all_accounts = self.accounting_service.get_all_accounts_cached()
                    else:
                        all_accounts = self.accounting_service.repo.get_all_accounts()
                    accounts_cache = {}
                    for acc in all_accounts:
                        code = getattr(acc, "code", None)
                        if code is not None and code != "":
                            accounts_cache[code] = acc
                            accounts_cache[str(code)] = acc
                        acc_id = getattr(acc, "id", None)
                        if acc_id is not None:
                            accounts_cache[acc_id] = acc
                            accounts_cache[str(acc_id)] = acc
                    self._set_cached_lookup("accounts", accounts_cache)

                projects_cache = self._get_cached_lookup("projects")
                if projects_cache is None:
                    all_projects = self.project_service.get_all_projects()
                    projects_cache = {}
                    for proj in all_projects or []:
                        try:
                            proj_name = (getattr(proj, "name", None) or "").strip()
                            if proj_name:
                                projects_cache[proj_name] = proj
                            proj_id = getattr(proj, "id", None)
                            if proj_id is not None:
                                projects_cache[str(proj_id)] = proj
                                projects_cache[proj_id] = proj
                            proj_mongo_id = getattr(proj, "_mongo_id", None)
                            if proj_mongo_id:
                                projects_cache[str(proj_mongo_id)] = proj
                                projects_cache[proj_mongo_id] = proj
                            proj_code = (getattr(proj, "project_code", None) or "").strip()
                            if proj_code:
                                projects_cache[proj_code] = proj
                            invoice_number = (getattr(proj, "invoice_number", None) or "").strip()
                            if invoice_number:
                                projects_cache[invoice_number] = proj
                        except Exception:
                            continue
                    self._set_cached_lookup("projects", projects_cache)

                clients_cache = self._get_cached_lookup("clients")
                if clients_cache is None:
                    clients = self.client_service.get_all_clients()
                    clients_cache = {}
                    for c in clients:
                        clients_cache[c.name] = c
                        if c._mongo_id:
                            clients_cache[c._mongo_id] = c
                            clients_cache[str(c._mongo_id)] = c
                        if c.id:
                            clients_cache[str(c.id)] = c
                            clients_cache[int(c.id)] = c
                        if c.name:
                            clients_cache[c.name.strip()] = c
                    self._set_cached_lookup("clients", clients_cache)

                return {
                    "payments": payments,
                    "accounts_cache": accounts_cache,
                    "projects_cache": projects_cache,
                    "clients_cache": clients_cache,
                }
            except Exception as e:
                safe_print(f"ERROR: [PaymentsManager] فشل جلب الدفعات: {e}")
                import traceback

                traceback.print_exc()
                return {
                    "payments": [],
                    "accounts_cache": {},
                    "projects_cache": {},
                    "clients_cache": {},
                }

        # دالة تحديث الواجهة
        def on_data_loaded(data):
            try:
                self.payments_list = data["payments"]
                self._page_accounts_cache = data["accounts_cache"]
                self._page_projects_cache = data["projects_cache"]
                self._page_clients_cache = data["clients_cache"]
                self._total_payments_sum = sum(p.amount for p in self.payments_list)
                self.total_label.setText(f"إجمالي التحصيلات: {self._total_payments_sum:,.2f} ج.م")
                if self._current_page < 1:
                    self._current_page = 1
                self._render_current_page()
                safe_print(f"INFO: [PaymentsManager] ✅ تم تحميل {len(self.payments_list)} دفعة.")

            except Exception as e:
                safe_print(f"ERROR: [PaymentsManager] فشل تحديث الجدول: {e}")
                import traceback

                traceback.print_exc()
            finally:
                self.payments_table.blockSignals(False)
                self.payments_table.setUpdatesEnabled(True)
                if sorting_enabled:
                    self.payments_table.setSortingEnabled(True)

        def on_error(error_msg):
            safe_print(f"ERROR: [PaymentsManager] فشل تحميل الدفعات: {error_msg}")
            self.payments_table.blockSignals(False)
            self.payments_table.setUpdatesEnabled(True)

        if force_refresh:
            self._invalidate_lookup_cache()
            if hasattr(self.project_service, "invalidate_cache"):
                self.project_service.invalidate_cache()
            if hasattr(self.client_service, "invalidate_cache"):
                self.client_service.invalidate_cache()

        # تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="payments_list",
            load_function=fetch_payments,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _get_total_pages(self) -> int:
        total = len(self.payments_list)
        if total == 0:
            return 1
        if self._page_size <= 0:
            return 1
        return (total + self._page_size - 1) // self._page_size

    def _render_current_page(self):
        total_pages = self._get_total_pages()
        if self._current_page > total_pages:
            self._current_page = total_pages
        if self._current_page < 1:
            self._current_page = 1

        if self._page_size <= 0:
            page_items = self.payments_list
            start_index = 0
        else:
            start_index = (self._current_page - 1) * self._page_size
            end_index = start_index + self._page_size
            page_items = self.payments_list[start_index:end_index]

        self._populate_payments_table(page_items, start_index)
        self._update_pagination_controls(total_pages)

    def _populate_payments_table(self, payments: list[schemas.Payment], start_index: int):
        accounts_cache = self._page_accounts_cache
        projects_cache = self._page_projects_cache
        clients_cache = self._page_clients_cache

        self.payments_table.setRowCount(len(payments))
        for i, payment in enumerate(payments):
            row_number = start_index + i + 1
            num_item = create_centered_item(str(row_number))
            num_item.setData(Qt.ItemDataRole.UserRole, payment)
            self.payments_table.setItem(i, 0, num_item)

            date_str = payment.date.strftime("%Y-%m-%d") if payment.date else ""
            self.payments_table.setItem(i, 1, create_centered_item(date_str))

            type_item = create_centered_item("💰 وارد")
            type_item.setForeground(QColor("#0A6CF1"))
            self.payments_table.setItem(i, 2, type_item)

            client_name = "عميل غير محدد"
            project_name = payment.project_id or "مشروع غير محدد"

            if payment.project_id:
                proj_key = str(payment.project_id).strip()
                project = projects_cache.get(payment.project_id) or projects_cache.get(proj_key)
                if project:
                    project_name = getattr(project, "name", proj_key) or proj_key
                    client_id = (getattr(project, "client_id", "") or "").strip()
                    if client_id:
                        client = clients_cache.get(client_id) or clients_cache.get(str(client_id))
                        client_name = client.name if client else client_id

            if client_name == "عميل غير محدد" and payment.client_id and payment.client_id.strip():
                client_id = payment.client_id.strip()
                if client_id in clients_cache:
                    client = clients_cache[client_id]
                    client_name = client.name
                else:
                    client_name = client_id

            self.payments_table.setItem(
                i, 3, create_centered_item(f"{client_name} - {project_name}")
            )

            invoice_number = str(getattr(payment, "invoice_number", "") or "").strip()
            if not invoice_number and payment.project_id:
                proj_key = str(payment.project_id).strip()
                project = projects_cache.get(payment.project_id) or projects_cache.get(proj_key)
                if project:
                    invoice_number = str(getattr(project, "invoice_number", "") or "").strip()
            self.payments_table.setItem(i, 4, create_centered_item(invoice_number or "—"))

            amount_item = create_centered_item(f"{payment.amount:,.2f}")
            amount_item.setForeground(QColor("#0A6CF1"))
            self.payments_table.setItem(i, 5, amount_item)

            payment_method = self._get_payment_method_from_account(
                payment.account_id, accounts_cache
            )
            self.payments_table.setItem(i, 6, create_centered_item(payment_method))

            account_display = "---"
            if payment.account_id and payment.account_id in accounts_cache:
                account = accounts_cache[payment.account_id]
                account_display = f"{account.name} ({account.code})"
            elif payment.account_id:
                account_display = payment.account_id

            self.payments_table.setItem(i, 7, create_centered_item(account_display))
            self.payments_table.setRowHeight(i, 40)

    def _update_pagination_controls(self, total_pages: int):
        self.page_info_label.setText(f"صفحة {self._current_page} / {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

    def _on_page_size_changed(self, value: str):
        if value == "كل":
            self._page_size = max(1, len(self.payments_list))
        else:
            try:
                self._page_size = int(value)
            except Exception:
                self._page_size = 100
        self._current_page = 1
        self._render_current_page()

    def _go_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._render_current_page()

    def _go_next_page(self):
        if self._current_page < self._get_total_pages():
            self._current_page += 1
            self._render_current_page()

    def _on_payments_changed(self):
        """⚡ استجابة لإشارة تحديث الدفعات - تحديث الجدول أوتوماتيك"""
        # ⚡ إبطال الـ cache أولاً لضمان جلب البيانات الجديدة من السيرفر
        if hasattr(self.project_service, "invalidate_cache"):
            self.project_service.invalidate_cache()
        if not self.isVisible():
            return
        self.load_payments_data(force_refresh=True)

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
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_payments_data(force_refresh=True)

    def _get_cash_accounts(self) -> list[schemas.Account]:
        """جلب حسابات النقدية والبنوك"""
        try:
            all_accounts = self.accounting_service.repo.get_all_accounts()
            cash_accounts = [
                acc
                for acc in all_accounts
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
        account_name = (getattr(account, "name", "") or "").lower()
        code = str(account_code)

        # ⚡ البحث بالاسم أولاً (الأكثر دقة)
        if (
            "vodafone" in account_name
            or "فودافون" in account_name
            or "v/f" in account_name
            or "vf" in account_name
        ):
            return "Vodafone Cash"
        elif "instapay" in account_name or "انستاباي" in account_name:
            return "InstaPay"
        elif (
            "كاش" in account_name
            or "cash" in account_name
            or "خزينة" in account_name
            or "صندوق" in account_name
        ):
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

    def _get_cached_lookup(self, key: str) -> dict | None:
        ts = self._lookups_cache_ts.get(key)
        if ts is None:
            return None
        if (time.monotonic() - ts) > self._lookups_cache_ttl_s:
            self._lookups_cache.pop(key, None)
            self._lookups_cache_ts.pop(key, None)
            return None
        return self._lookups_cache.get(key)

    def _set_cached_lookup(self, key: str, value: dict) -> None:
        self._lookups_cache[key] = value
        self._lookups_cache_ts[key] = time.monotonic()

    def _invalidate_lookup_cache(self):
        self._lookups_cache.clear()
        self._lookups_cache_ts.clear()

    def open_add_dialog(self):
        """⚡ فتح نافذة إضافة دفعة جديدة"""
        dialog = NewPaymentDialog(
            project_service=self.project_service,
            accounting_service=self.accounting_service,
            client_service=self.client_service,
            parent=self,
        )
        dialog.payment_created.connect(self._on_payment_created)
        dialog.exec()

    def _on_payment_created(self, payment):
        """⚡ استجابة لإنشاء دفعة جديدة"""
        safe_print(f"INFO: [PaymentsManager] تم إنشاء دفعة جديدة: {payment.amount}")
        self.load_payments_data(force_refresh=True)

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
        date_str = (
            selected_payment.date.strftime("%Y-%m-%d") if selected_payment.date else "غير محدد"
        )

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
                    self, "تم الحذف", "تم حذف الدفعة وعكس القيد المحاسبي وتحديث حالة المشروع بنجاح."
                )
                self.load_payments_data(force_refresh=True)
            else:
                QMessageBox.warning(self, "خطأ", "فشل حذف الدفعة.")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل حذف الدفعة: {e}")
            safe_print(f"ERROR: [PaymentsManager] فشل حذف الدفعة: {e}")
