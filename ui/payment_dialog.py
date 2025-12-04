from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QDateEdit,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QLabel,
    QFrame,
    QGroupBox,
)
from ui.custom_spinbox import CustomSpinBox
from PyQt6.QtCore import QDate
from PyQt6.QtGui import QFont
from typing import List

from core import schemas


class PaymentDialog(QDialog):
    """نافذة تسجيل دفعة لمشروع - مع عرض المبلغ المتبقي."""

    def __init__(
        self,
        project: schemas.Project,
        accounts: List[schemas.Account],
        project_service,
        parent=None,
    ):
        super().__init__(parent)
        self.project = project
        self.accounts = accounts
        self.project_service = project_service

        # حساب المبلغ المتبقي
        self.total_amount = project.total_amount or 0
        self.total_paid = 0
        self.remaining_amount = self.total_amount

        if project_service:
            try:
                profit_data = project_service.get_project_profitability(project.name)
                self.total_paid = profit_data.get("total_paid", 0)
                self.remaining_amount = profit_data.get("balance_due", self.total_amount)
            except Exception as e:
                print(f"WARNING: [PaymentDialog] فشل جلب بيانات الربحية: {e}")

        self.setWindowTitle(f"تسجيل دفعة - {project.name}")
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

        layout = QVBoxLayout()

        # --- قسم ملخص المشروع المالي ---
        summary_group = QGroupBox("ملخص المشروع المالي")
        summary_layout = QHBoxLayout()

        # كارت إجمالي العقد
        total_card = self._create_info_card("إجمالي العقد", f"{self.total_amount:,.2f}", "#3b82f6")
        summary_layout.addWidget(total_card)

        # كارت المدفوع
        paid_card = self._create_info_card("المدفوع", f"{self.total_paid:,.2f}", "#0A6CF1")
        summary_layout.addWidget(paid_card)

        # كارت المتبقي (بلون أحمر لو في متبقي)
        remaining_color = "#ef4444" if self.remaining_amount > 0 else "#0A6CF1"
        remaining_card = self._create_info_card("المتبقي", f"{self.remaining_amount:,.2f}", remaining_color)
        summary_layout.addWidget(remaining_card)

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # --- قسم بيانات الدفعة ---
        form = QFormLayout()

        self.account_combo = QComboBox()
        self.account_combo.setPlaceholderText("اختر حساب البنك/الخزينة...")
        for acc in accounts:
            # عرض الاسم والكود بشكل واضح
            display_text = f"💰 {acc.name} ({acc.code})"
            self.account_combo.addItem(display_text, userData=acc)

        self.amount_input = CustomSpinBox(decimals=2, minimum=0, maximum=100_000_000)
        # Smart Default: القيمة الافتراضية هي المبلغ المتبقي
        self.amount_input.setValue(self.remaining_amount if self.remaining_amount > 0 else 0)
        self.amount_input.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.amount_input.valueChanged.connect(self._validate_payment)

        # Smart Default: Today's date
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات الدفع (اختياري)...")
        self.notes_input.setMaximumHeight(80)

        form.addRow("الحساب المستلم:", self.account_combo)
        form.addRow("المبلغ:", self.amount_input)
        form.addRow("التاريخ:", self.date_input)
        form.addRow("ملاحظات:", self.notes_input)
        layout.addLayout(form)

        buttons_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 تسجيل الدفعة")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0A6CF1;
                color: white;
                padding: 10px;
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
        self.save_btn.clicked.connect(self.save_payment)
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
        
        # Initial validation
        self._validate_payment()

    def _create_info_card(self, title: str, value: str, color: str) -> QFrame:
        """إنشاء كارت معلومات صغير"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-size: 11px;")

        value_label = QLabel(value)
        value_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)

        return card

    def _validate_payment(self):
        """Real-time payment validation"""
        amount = self.amount_input.value()
        selected_account = self.account_combo.currentData()
        
        is_valid = True
        
        if amount <= 0:
            is_valid = False
        
        if not selected_account:
            is_valid = False
        
        self.save_btn.setEnabled(is_valid)
    
    def save_payment(self):
        selected_account = self.account_combo.currentData()
        amount = self.amount_input.value()

        if not selected_account or amount <= 0:
            QMessageBox.warning(self, "⚠️ تحقق من البيانات", "يرجى اختيار الحساب وإدخال مبلغ صحيح.")
            return

        # تحذير إذا كان المبلغ أكبر من المتبقي
        if amount > self.remaining_amount and self.remaining_amount > 0:
            reply = QMessageBox.question(
                self,
                "تأكيد",
                f"المبلغ المدخل ({amount:,.2f}) أكبر من المتبقي ({self.remaining_amount:,.2f}).\n\nهل تريد المتابعة؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        try:
            self.project_service.create_payment_for_project(
                project=self.project,
                amount=amount,
                date=self.date_input.dateTime().toPyDateTime(),
                account_id=selected_account.code,
            )
            QMessageBox.information(self, "تم", "تم تسجيل الدفعة بنجاح.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "خطأ", f"فشل تسجيل الدفعة: {exc}")
