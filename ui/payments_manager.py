# الملف: ui/payments_manager.py
"""
تاب إدارة الدفعات - عرض وتعديل جميع الدفعات (تحصيلات العملاء)
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox, QDialog,
    QFormLayout, QComboBox, QDateEdit, QTextEdit
)
from ui.custom_spinbox import CustomSpinBox
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont

from services.project_service import ProjectService
from services.accounting_service import AccountingService
from services.client_service import ClientService
from core import schemas
from typing import List, Optional

from ui.styles import BUTTON_STYLES, TABLE_STYLE_DARK


class PaymentEditorDialog(QDialog):
    """نافذة تعديل دفعة موجودة"""

    def __init__(
        self,
        payment: schemas.Payment,
        accounts: List[schemas.Account],
        accounting_service: AccountingService,
        project_service: ProjectService = None,
        parent=None,
    ):
        super().__init__(parent)
        self.payment = payment
        self.accounts = accounts
        self.accounting_service = accounting_service
        self.project_service = project_service
        self.original_amount = payment.amount
        self.original_account_id = payment.account_id

        self.setWindowTitle(f"تعديل دفعة - {payment.project_id}")
        self.setMinimumWidth(450)
        
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

        # حساب الاستلام
        self.account_combo = QComboBox()
        for acc in accounts:
            display_text = f"💰 {acc.name} ({acc.code})"
            self.account_combo.addItem(display_text, userData=acc)
            if acc.code == payment.account_id:
                self.account_combo.setCurrentIndex(self.account_combo.count() - 1)
        
        # ربط تغيير الحساب بتحديث طريقة الدفع
        self.account_combo.currentIndexChanged.connect(self._update_payment_method_from_account)

        # المبلغ
        self.amount_input = CustomSpinBox(decimals=2, minimum=0.01, maximum=100_000_000)
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
        """تحديث طريقة الدفع تلقائياً حسب الحساب المختار"""
        selected_account = self.account_combo.currentData()
        if not selected_account:
            return
        
        # تحديد طريقة الدفع حسب اسم/كود الحساب
        account_name = selected_account.name.lower()
        account_code = selected_account.code
        
        # قواعد الربط (الأكواد المحددة أولاً، ثم الأسماء)
        if account_code == "1103":
            self.method_combo.setCurrentText("Vodafone Cash")
        elif account_code == "1104":
            self.method_combo.setCurrentText("InstaPay")
        elif account_code == "1101":
            self.method_combo.setCurrentText("Cash")
        elif account_code.startswith("1102"):  # البنوك (1102, 11021, 11022, ...)
            self.method_combo.setCurrentText("Bank Transfer")
        elif "vodafone" in account_name or "فودافون" in account_name:
            self.method_combo.setCurrentText("Vodafone Cash")
        elif "instapay" in account_name or "انستاباي" in account_name:
            self.method_combo.setCurrentText("InstaPay")
        elif "كاش" in account_name or "cash" in account_name or "خزينة" in account_name:
            self.method_combo.setCurrentText("Cash")
        elif "بنك" in account_name or "bank" in account_name:
            self.method_combo.setCurrentText("Bank Transfer")
        elif "شيك" in account_name or "check" in account_name:
            self.method_combo.setCurrentText("Check")
        else:
            self.method_combo.setCurrentText("Other")

    def save_changes(self):
        selected_account = self.account_combo.currentData()
        new_amount = self.amount_input.value()

        if not selected_account or new_amount <= 0:
            QMessageBox.warning(self, "⚠️ تحقق", "يرجى اختيار الحساب وإدخال مبلغ صحيح.")
            return

        try:
            # تحديث بيانات الدفعة
            self.payment.amount = new_amount
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
                # عكس القيد القديم وإنشاء قيد جديد
                self._reverse_and_repost_journal_entry(selected_account.code, new_amount)
                QMessageBox.information(self, "تم", "تم تعديل الدفعة وتحديث القيود المحاسبية وحالة المشروع.")
                self.accept()
            else:
                QMessageBox.warning(self, "خطأ", "فشل حفظ التعديلات.")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل تعديل الدفعة: {e}")

    def _reverse_and_repost_journal_entry(self, new_account_code: str, new_amount: float):
        """عكس القيد القديم وإنشاء قيد جديد بالقيم المعدلة"""
        try:
            from datetime import datetime
            
            # 1. إنشاء قيد عكسي للقيم القديمة
            self.accounting_service.post_journal_entry(
                date=datetime.now(),
                description=f"عكس قيد دفعة معدلة - {self.payment.project_id}",
                ref_type="payment_reversal",
                ref_id=f"REV-{self.payment.id or self.payment._mongo_id}",
                debit_account_code=self.accounting_service.ACC_RECEIVABLE_CODE,  # العملاء مدين (عكس)
                credit_account_code=self.original_account_id,  # الحساب القديم دائن (عكس)
                amount=self.original_amount
            )

            # 2. إنشاء قيد جديد بالقيم المعدلة
            self.accounting_service.post_journal_entry(
                date=self.payment.date,
                description=f"دفعة معدلة - {self.payment.project_id}",
                ref_type="payment",
                ref_id=f"PAY-{self.payment.id or self.payment._mongo_id}",
                debit_account_code=new_account_code,  # الحساب الجديد مدين
                credit_account_code=self.accounting_service.ACC_RECEIVABLE_CODE,  # العملاء دائن
                amount=new_amount
            )
            
            print(f"SUCCESS: تم عكس وإعادة ترحيل قيد الدفعة.")
        except Exception as e:
            print(f"ERROR: فشل عكس/إعادة ترحيل القيد: {e}")


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

        self.payments_list: List[schemas.Payment] = []
        self.clients_cache = {}  # cache للعملاء

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

        # أزرار التحكم
        buttons_layout = QHBoxLayout()

        self.edit_button = QPushButton("✏️ تعديل الدفعة")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.clicked.connect(self.open_edit_dialog)

        self.delete_button = QPushButton("🗑️ حذف الدفعة")
        self.delete_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_button.clicked.connect(self.delete_selected_payment)

        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.clicked.connect(self.load_payments_data)

        buttons_layout.addWidget(self.edit_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

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
        
        self.payments_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.payments_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.payments_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.payments_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.payments_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.payments_table.setAlternatingRowColors(True)
        self.payments_table.verticalHeader().setDefaultSectionSize(45)  # ⚡ ارتفاع الصفوف
        self.payments_table.verticalHeader().setVisible(False)
        
        # ربط الدبل كليك
        self.payments_table.itemDoubleClicked.connect(self.open_edit_dialog)
        
        self.payments_table.setStyleSheet(TABLE_STYLE_DARK)
        layout.addWidget(self.payments_table)

        # إجمالي الدفعات
        self.total_label = QLabel("إجمالي التحصيلات: 0.00 ج.م")
        self.total_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.total_label.setStyleSheet("color: #0A6CF1; padding: 10px;")
        layout.addWidget(self.total_label, 0, Qt.AlignmentFlag.AlignRight)

    def load_payments_data(self):
        """تحميل جميع الدفعات"""
        print("INFO: [PaymentsManager] جاري تحميل الدفعات...")
        
        # ⚡ منع التجميد - معالجة الأحداث
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            # تحميل الدفعات
            self.payments_list = self.accounting_service.repo.get_all_payments()
            
            # تحميل الحسابات للـ cache (لعرض الأسماء بدل الأكواد)
            all_accounts = self.accounting_service.repo.get_all_accounts()
            accounts_cache = {acc.code: acc for acc in all_accounts}
            
            # تحميل المشاريع للـ cache (لعرض أسماء العملاء)
            all_projects = self.project_service.get_all_projects()
            projects_cache = {proj.name: proj for proj in all_projects}
            
            # تحميل العملاء للـ cache
            clients = self.client_service.get_all_clients()
            clients_cache = {}
            for c in clients:
                # إضافة العميل بكل الطرق الممكنة للبحث
                clients_cache[c.name] = c  # بالاسم
                if c._mongo_id:
                    clients_cache[c._mongo_id] = c  # بالـ mongo_id
                if c.id:
                    clients_cache[str(c.id)] = c  # بالـ id

            self.payments_table.setRowCount(0)
            total_sum = 0.0

            for i, payment in enumerate(self.payments_list):
                self.payments_table.insertRow(i)

                # الرقم
                num_item = QTableWidgetItem(str(i + 1))
                num_item.setData(Qt.ItemDataRole.UserRole, payment)
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.payments_table.setItem(i, 0, num_item)

                # التاريخ
                date_str = payment.date.strftime("%Y-%m-%d") if payment.date else ""
                date_item = QTableWidgetItem(date_str)
                date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.payments_table.setItem(i, 1, date_item)

                # النوع (دائماً تحصيل/وارد للدفعات)
                type_item = QTableWidgetItem("💰 وارد")
                type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                type_item.setForeground(QColor("#0A6CF1"))
                self.payments_table.setItem(i, 2, type_item)

                # العميل/المشروع - عرض اسم العميل الحقيقي واسم المشروع
                entity_text = "---"
                client_name = "عميل غير محدد"
                project_name = payment.project_id or "مشروع غير محدد"
                
                # البحث عن المشروع
                if payment.project_id and payment.project_id in projects_cache:
                    project = projects_cache[payment.project_id]
                    project_name = project.name  # اسم المشروع الحقيقي
                    
                    # البحث عن العميل
                    client_id = project.client_id
                    if client_id and client_id in clients_cache:
                        client_name = clients_cache[client_id].name
                    elif client_id:
                        # محاولة البحث بطرق أخرى
                        for client in clients_cache.values():
                            if (client._mongo_id == client_id or 
                                str(client.id) == client_id or 
                                client.name == client_id):
                                client_name = client.name
                                break
                
                entity_text = f"{client_name} - {project_name}"
                
                entity_item = QTableWidgetItem(entity_text)
                entity_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.payments_table.setItem(i, 3, entity_item)

                # المبلغ
                amount_item = QTableWidgetItem(f"{payment.amount:,.2f}")
                amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                amount_item.setForeground(QColor("#0A6CF1"))
                self.payments_table.setItem(i, 4, amount_item)

                # طريقة الدفع - حساب من الحساب المستلم
                payment_method = self._get_payment_method_from_account(payment.account_id, accounts_cache)
                method_item = QTableWidgetItem(payment_method)
                method_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.payments_table.setItem(i, 5, method_item)

                # الحساب - عرض الاسم بدل الكود
                account_display = "---"
                if payment.account_id and payment.account_id in accounts_cache:
                    account = accounts_cache[payment.account_id]
                    account_display = f"{account.name} ({account.code})"
                elif payment.account_id:
                    account_display = payment.account_id
                
                account_item = QTableWidgetItem(account_display)
                account_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.payments_table.setItem(i, 6, account_item)

                # ارتفاع الصف
                self.payments_table.setRowHeight(i, 40)

                total_sum += payment.amount

            self.total_label.setText(f"إجمالي التحصيلات: {total_sum:,.2f} ج.م")
            print(f"INFO: [PaymentsManager] تم جلب {len(self.payments_list)} دفعة.")

        except Exception as e:
            print(f"ERROR: [PaymentsManager] فشل تحميل الدفعات: {e}")

    def _on_payments_changed(self):
        """⚡ استجابة لإشارة تحديث الدفعات - تحديث الجدول أوتوماتيك"""
        print("INFO: [PaymentsManager] ⚡ استلام إشارة تحديث الدفعات - جاري التحديث...")
        self.load_payments_data()

    def get_selected_payment(self) -> Optional[schemas.Payment]:
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
        if payment:
            return payment
        
        # fallback: استخدام الفهرس مباشرة
        if 0 <= current_row < len(self.payments_list):
            return self.payments_list[current_row]
        
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

    def _get_cash_accounts(self) -> List[schemas.Account]:
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
            print(f"ERROR: [PaymentsManager] فشل جلب حسابات النقدية: {e}")
            return []

    def _get_payment_method_from_account(self, account_code: str, accounts_cache: dict) -> str:
        """تحديد طريقة الدفع من كود الحساب"""
        if not account_code or account_code not in accounts_cache:
            return "---"
        
        account = accounts_cache[account_code]
        account_name = account.name.lower()
        
        # قواعد الربط (نفس اللوجيك في الـ Dialog)
        if account_code == "1103":
            return "Vodafone Cash"
        elif account_code == "1104":
            return "InstaPay"
        elif account_code == "1101":
            return "Cash"
        elif account_code.startswith("1102"):  # البنوك
            return "Bank Transfer"
        elif "vodafone" in account_name or "فودافون" in account_name:
            return "Vodafone Cash"
        elif "instapay" in account_name or "انستاباي" in account_name:
            return "InstaPay"
        elif "كاش" in account_name or "cash" in account_name or "خزينة" in account_name:
            return "Cash"
        elif "بنك" in account_name or "bank" in account_name:
            return "Bank Transfer"
        elif "شيك" in account_name or "check" in account_name:
            return "Check"
        else:
            return "Other"

    def apply_permissions(self):
        """تطبيق الصلاحيات حسب دور المستخدم"""
        if not self.current_user:
            return
        
        from core.auth_models import PermissionManager, UserRole
        
        user_role = self.current_user.role
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role)
            except ValueError:
                user_role = UserRole.SALES
        
        # المحاسب والمدير لهم صلاحيات كاملة
        if user_role in [UserRole.ADMIN, UserRole.ACCOUNTANT]:
            self.edit_button.setEnabled(True)
            self.delete_button.setEnabled(True)
        else:
            # مندوب المبيعات: قراءة فقط
            self.edit_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.edit_button.setToolTip("ليس لديك صلاحية تعديل الدفعات")
            self.delete_button.setToolTip("ليس لديك صلاحية حذف الدفعات")

    def delete_selected_payment(self):
        """حذف الدفعة المحددة مع عكس القيد المحاسبي وتحديث حالة المشروع"""
        selected_payment = self.get_selected_payment()
        if not selected_payment:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد دفعة أولاً.")
            return

        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف الدفعة؟\n\n"
            f"المشروع: {selected_payment.project_id}\n"
            f"المبلغ: {selected_payment.amount:,.2f} ج.م\n"
            f"التاريخ: {selected_payment.date.strftime('%Y-%m-%d') if selected_payment.date else 'غير محدد'}\n\n"
            f"⚠️ سيتم عكس القيد المحاسبي المرتبط بهذه الدفعة.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            from datetime import datetime
            
            # 1. عكس القيد المحاسبي أولاً
            self.accounting_service.post_journal_entry(
                date=datetime.now(),
                description=f"عكس قيد دفعة محذوفة - {selected_payment.project_id}",
                ref_type="payment_deletion",
                ref_id=f"DEL-{selected_payment.id or selected_payment._mongo_id}",
                debit_account_code=self.accounting_service.ACC_RECEIVABLE_CODE,  # العملاء مدين (عكس)
                credit_account_code=selected_payment.account_id,  # الحساب دائن (عكس)
                amount=selected_payment.amount
            )
            
            # 2. حذف الدفعة مع تحديث حالة المشروع أوتوماتيك ⚡
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
            print(f"ERROR: [PaymentsManager] فشل حذف الدفعة: {e}")
