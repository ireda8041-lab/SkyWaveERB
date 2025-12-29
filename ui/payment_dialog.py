"""
نافذة تسجيل دفعة لمشروع - مع عرض المبلغ المتبقي
⚡ محسّن: دقة مالية، تحقق من البيانات، تكامل محاسبي
📱 تصميم متجاوب (Responsive)
"""

from decimal import Decimal, ROUND_HALF_UP

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
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
from ui.custom_spinbox import CustomSpinBox
from ui.smart_combobox import SmartFilterComboBox


def to_decimal(value) -> Decimal:
    """تحويل آمن للقيم المالية إلى Decimal"""
    if value is None:
        return Decimal('0.00')
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal('0.00')


class PaymentDialog(QDialog):
    """نافذة تسجيل دفعة لمشروع - تصميم متجاوب."""

    def __init__(
        self,
        project: schemas.Project,
        accounts: list[schemas.Account],
        project_service,
        parent=None,
    ):
        super().__init__(parent)
        self.project = project
        self.accounts = accounts
        self.project_service = project_service

        # ⚡ استخدام Decimal للدقة المالية
        self.total_amount = to_decimal(project.total_amount or 0)
        self.total_paid = Decimal('0.00')
        self.remaining_amount = self.total_amount

        if project_service:
            try:
                profit_data = project_service.get_project_profitability(project.name)
                self.total_paid = to_decimal(profit_data.get("total_paid", 0))
                self.remaining_amount = to_decimal(profit_data.get("balance_due", float(self.total_amount)))
            except Exception as e:
                print(f"WARNING: [PaymentDialog] فشل جلب بيانات الربحية: {e}")

        self.setWindowTitle(f"تسجيل دفعة - {project.name}")
        self.setMinimumWidth(450)
        self.setMinimumHeight(480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        self._init_ui()

    def _init_ui(self):
        from ui.styles import BUTTON_STYLES, COLORS, get_arrow_url

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
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ستايل الحقول
        field_style = f"""
            QComboBox, QDateEdit, QLineEdit {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px;
                font-size: 11px;
                min-height: 16px;
            }}
            QComboBox:hover, QDateEdit:hover, QLineEdit:hover {{
                border-color: {COLORS['primary']};
            }}
            QComboBox:focus, QDateEdit:focus, QLineEdit:focus {{
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
        """

        label_style = f"color: {COLORS['text_secondary']}; font-size: 10px;"

        # === ملخص المشروع المالي ===
        summary_label = QLabel("ملخص المشروع المالي")
        summary_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px; font-weight: bold;")
        layout.addWidget(summary_label)

        # كروت الملخص
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(8)

        total_card = self._create_info_card("إجمالي العقد", f"{float(self.total_amount):,.2f}", "#3b82f6", "📋")
        paid_card = self._create_info_card("المدفوع", f"{float(self.total_paid):,.2f}", "#10b981", "✅")
        remaining_color = "#ef4444" if self.remaining_amount > 0 else "#10b981"
        remaining_card = self._create_info_card("المتبقي", f"{float(self.remaining_amount):,.2f}", remaining_color, "⏳")

        cards_layout.addWidget(total_card)
        cards_layout.addWidget(paid_card)
        cards_layout.addWidget(remaining_card)
        layout.addLayout(cards_layout)

        # === الحساب المستلم ===
        acc_label = QLabel("💳 الحساب المستلم")
        acc_label.setStyleSheet(label_style)
        layout.addWidget(acc_label)

        # SmartFilterComboBox مع فلترة ذكية
        self.account_combo = SmartFilterComboBox()
        self.account_combo.setStyleSheet(field_style)
        for acc in self.accounts:
            display_text = f"💰 {acc.name} ({acc.code})"
            self.account_combo.addItem(display_text, userData=acc)
        self.account_combo.lineEdit().setPlaceholderText("اكتب للبحث عن الحساب...")
        layout.addWidget(self.account_combo)

        # === صف المبلغ والتاريخ ===
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        # المبلغ
        amount_cont = QVBoxLayout()
        amount_cont.setSpacing(2)
        amount_label = QLabel("💰 المبلغ")
        amount_label.setStyleSheet(label_style)
        amount_cont.addWidget(amount_label)
        self.amount_input = CustomSpinBox(decimals=2, minimum=0.01, maximum=100_000_000)
        self.amount_input.setSuffix(" ج.م")
        default_amount = float(self.remaining_amount) if self.remaining_amount > 0 else 0.01
        self.amount_input.setValue(default_amount)
        self.amount_input.valueChanged.connect(self._validate_payment)
        amount_cont.addWidget(self.amount_input)
        row1.addLayout(amount_cont, 1)

        # التاريخ
        date_cont = QVBoxLayout()
        date_cont.setSpacing(2)
        date_label = QLabel("📅 التاريخ")
        date_label.setStyleSheet(label_style)
        date_cont.addWidget(date_label)
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setStyleSheet(field_style)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        date_cont.addWidget(self.date_input)
        row1.addLayout(date_cont, 1)

        layout.addLayout(row1)

        # === رقم المرجع ===
        ref_label = QLabel("🔢 رقم المرجع")
        ref_label.setStyleSheet(label_style)
        layout.addWidget(ref_label)

        self.reference_input = QLineEdit()
        self.reference_input.setStyleSheet(field_style)
        self.reference_input.setPlaceholderText("رقم العملية / المرجع (اختياري)")
        layout.addWidget(self.reference_input)

        # === الملاحظات ===
        notes_label = QLabel("📝 ملاحظات")
        notes_label.setStyleSheet(label_style)
        layout.addWidget(notes_label)

        self.notes_input = QTextEdit()
        self.notes_input.setStyleSheet(field_style)
        self.notes_input.setPlaceholderText("ملاحظات الدفع (اختياري)...")
        self.notes_input.setFixedHeight(55)
        layout.addWidget(self.notes_input)

        # === المرفقات ===
        attach_label = QLabel("📎 المرفقات")
        attach_label.setStyleSheet(label_style)
        layout.addWidget(attach_label)

        attach_layout = QHBoxLayout()
        attach_layout.setSpacing(8)

        self.upload_btn = QPushButton("📎 إرفاق صورة الدفعة")
        self.upload_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
            }}
        """)
        self.upload_btn.clicked.connect(self.select_receipt_image)
        attach_layout.addWidget(self.upload_btn)

        self.file_label = QLabel("")
        self.file_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
        attach_layout.addWidget(self.file_label, 1)

        self.selected_image_path = None
        layout.addLayout(attach_layout)

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

        self.save_btn = QPushButton("💾 تسجيل الدفعة")
        self.save_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_btn.setFixedHeight(28)
        self.save_btn.clicked.connect(self.save_payment)
        buttons_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.cancel_btn.setFixedHeight(28)
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        main_layout.addWidget(buttons_container)

        self._validate_payment()

    def _create_info_card(self, title: str, value: str, color: str, icon: str) -> QFrame:
        """إنشاء كارت معلومات مالية"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(3)

        # صف العنوان
        header = QHBoxLayout()
        header.setSpacing(4)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 12px; background: transparent;")
        header.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 10px; background: transparent;")
        header.addWidget(title_lbl)
        header.addStretch()

        card_layout.addLayout(header)

        value_lbl = QLabel(value)
        value_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px; background: transparent;")
        card_layout.addWidget(value_lbl)

        return card

    def _validate_payment(self):
        """التحقق من صحة البيانات"""
        amount = self.amount_input.value()
        selected_account = self.account_combo.currentData()
        is_valid = amount > 0 and selected_account is not None
        self.save_btn.setEnabled(is_valid)

    def save_payment(self):
        selected_account = self.account_combo.currentData()
        amount = to_decimal(self.amount_input.value())

        if not selected_account or amount <= 0:
            QMessageBox.warning(self, "⚠️ تحقق من البيانات", "يرجى اختيار الحساب وإدخال مبلغ صحيح.")
            return

        # تحذير إذا كان المبلغ أكبر من المتبقي
        if amount > self.remaining_amount and self.remaining_amount > 0:
            reply = QMessageBox.question(
                self,
                "تأكيد",
                f"المبلغ المدخل ({float(amount):,.2f}) أكبر من المتبقي ({float(self.remaining_amount):,.2f}).\n\nهل تريد المتابعة؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        try:
            payment = self.project_service.create_payment_for_project(
                project=self.project,
                amount=float(amount),
                date=self.date_input.dateTime().toPyDateTime(),
                account_id=selected_account.code,
            )

            if payment:
                QMessageBox.information(self, "✅ تم", "تم تسجيل الدفعة بنجاح وإنشاء القيد المحاسبي.")
                self.accept()
            else:
                QMessageBox.warning(self, "خطأ", "فشل تسجيل الدفعة.")

        except Exception as exc:
            error_msg = str(exc)
            if "مكررة" in error_msg or "duplicate" in error_msg.lower():
                QMessageBox.warning(self, "⚠️ دفعة مكررة", f"يوجد دفعة بنفس البيانات:\n{error_msg}")
            else:
                QMessageBox.critical(self, "خطأ", f"فشل تسجيل الدفعة: {exc}")

    def select_receipt_image(self):
        """فتح نافذة اختيار ملف صورة الإيصال"""
        from PyQt6.QtWidgets import QFileDialog
        import os

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "اختر صورة الإيصال/الدفعة",
            "",
            "Images (*.png *.jpg *.jpeg);;PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            self.selected_image_path = file_path
            file_name = os.path.basename(file_path)
            self.file_label.setText(f"✅ {file_name}")
            self.file_label.setStyleSheet("color: #10b981; font-size: 10px;")
        else:
            self.file_label.setText("")
            self.selected_image_path = None
