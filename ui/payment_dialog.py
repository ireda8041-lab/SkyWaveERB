
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core import schemas
from ui.custom_spinbox import CustomSpinBox
from ui.smart_scan_dropzone import SmartScanDropzone


class PaymentDialog(QDialog):
    """نافذة تسجيل دفعة لمشروع - مع عرض المبلغ المتبقي."""

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

        # --- قسم المسح الذكي ---
        self.smart_scan = SmartScanDropzone(self)
        self.smart_scan.scan_completed.connect(self._on_scan_completed)
        self.smart_scan.scan_failed.connect(self._on_scan_failed)

        # إخفاء الـ widget إذا الخدمة غير متاحة
        if not self.smart_scan.is_available():
            self.smart_scan.setVisible(False)
        else:
            layout.addWidget(self.smart_scan)

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

        # حقل الرقم المرجعي (للمسح الذكي)
        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("رقم العملية / المرجع (اختياري)")

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات الدفع (اختياري)...")
        self.notes_input.setMaximumHeight(80)

        form.addRow("الحساب المستلم:", self.account_combo)
        form.addRow("المبلغ:", self.amount_input)
        form.addRow("التاريخ:", self.date_input)
        form.addRow("رقم المرجع:", self.reference_input)
        form.addRow("ملاحظات:", self.notes_input)

        # === زر إرفاق صورة الدفعة ===
        attachment_layout = QHBoxLayout()
        self.upload_btn = QPushButton("📎 إرفاق صورة الدفعة")
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50;
                color: white;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #34495e; }
        """)
        self.upload_btn.clicked.connect(self.select_receipt_image)
        attachment_layout.addWidget(self.upload_btn)

        self.file_label = QLabel("")
        self.file_label.setStyleSheet("color: #aaa; font-size: 11px;")
        attachment_layout.addWidget(self.file_label)
        attachment_layout.addStretch()

        self.selected_image_path = None
        form.addRow("المرفقات:", attachment_layout)

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
            self.file_label.setStyleSheet("color: #2ecc71; font-size: 11px;")
        else:
            self.file_label.setText("")
            self.selected_image_path = None

    def _on_scan_completed(self, data: dict):
        """Auto-fill form fields with extracted data from smart scan."""
        # ملء حقل المبلغ
        if data.get('amount'):
            self.amount_input.setValue(data['amount'])

        # ملء حقل التاريخ
        if data.get('date'):
            date = QDate.fromString(data['date'], 'yyyy-MM-dd')
            if date.isValid():
                self.date_input.setDate(date)

        # ملء حقل الرقم المرجعي
        if data.get('reference_number'):
            self.reference_input.setText(data['reference_number'])

        # ملاحظة: لا نختار الحساب تلقائياً - المستخدم يختار بنفسه
        # لأن أسماء المنصات قد لا تتطابق مع أسماء الحسابات

        # إضافة اسم المرسل للملاحظات
        if data.get('sender_name'):
            current_notes = self.notes_input.toPlainText()
            sender_note = f"المرسل: {data['sender_name']}"
            if current_notes:
                self.notes_input.setText(f"{current_notes}\n{sender_note}")
            else:
                self.notes_input.setText(sender_note)

        # تحديث التحقق
        self._validate_payment()

    def _on_scan_failed(self, error_message: str):
        """Handle scan failure - just log, error is shown in dropzone."""
        print(f"INFO: [PaymentDialog] فشل المسح الذكي: {error_message}")

    def _select_account_by_platform(self, platform: str):
        """Try to select the matching account based on platform name.

        يختار الحساب تلقائياً لو موجود، ويسيبه فاضي لو مش موجود.
        """
        if not platform:
            return

        # لو مفيش حسابات، ما نعملش حاجة
        if self.account_combo.count() == 0:
            return

        platform_lower = platform.lower()

        # قائمة الكلمات المفتاحية لكل منصة
        platform_keywords = {
            'vodafone': ['vodafone', 'فودافون', 'vf', 'فودا'],
            'instapay': ['instapay', 'انستا', 'insta'],
            'orange': ['orange', 'اورنج'],
            'etisalat': ['etisalat', 'اتصالات', 'we'],
            'cib': ['cib', 'سي اي بي'],
            'nbe': ['nbe', 'الأهلي', 'اهلي'],
            'qnb': ['qnb', 'قطر'],
            'bank': ['bank', 'بنك'],
        }

        best_match_index = -1
        best_match_score = 0

        # البحث عن أفضل حساب مطابق من الحسابات الحقيقية فقط
        for i in range(self.account_combo.count()):
            account = self.account_combo.itemData(i)

            # تخطي العناصر بدون بيانات حساب حقيقية
            if account is None:
                continue

            # التحقق من أن الحساب له اسم
            if not hasattr(account, 'name') or not account.name:
                continue

            # التحقق من أن الحساب موجود في قائمة الحسابات الأصلية
            account_exists = any(
                acc.code == account.code for acc in self.accounts
            ) if hasattr(account, 'code') else False

            if not account_exists:
                continue

            account_name_lower = account.name.lower()
            current_score = 0

            # التحقق من كل منصة
            for _platform_key, keywords in platform_keywords.items():
                platform_matches = any(kw in platform_lower for kw in keywords)
                account_matches = any(kw in account_name_lower for kw in keywords)

                if platform_matches and account_matches:
                    current_score = sum(1 for kw in keywords if kw in account_name_lower)
                    break

            # مطابقة مباشرة
            if platform_lower in account_name_lower:
                current_score += 10

            if current_score > best_match_score:
                best_match_score = current_score
                best_match_index = i

        # فقط غيّر الحساب لو لقينا مطابقة حقيقية مع حساب موجود
        if best_match_index >= 0 and best_match_score > 0:
            self.account_combo.setCurrentIndex(best_match_index)
            print(f"INFO: [PaymentDialog] تم اختيار الحساب تلقائياً: {self.account_combo.currentText()}")
        else:
            # لو مفيش مطابقة، نسيب الـ ComboBox على الـ placeholder
            self.account_combo.setCurrentIndex(-1)
            print(f"INFO: [PaymentDialog] لم يتم العثور على حساب مطابق للمنصة: {platform}")
