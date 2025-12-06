import datetime
import os

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core import schemas
from services.client_service import ClientService
from services.quotation_service import QuotationService
from services.service_service import ServiceService
from services.settings_service import SettingsService
from ui.custom_spinbox import CustomSpinBox
from ui.invoice_scan_widget import InvoiceScanWidget


class QuotationEditorWindow(QDialog):
    """نافذة لإنشاء أو تعديل عرض سعر."""

    def __init__(
        self,
        quotation_service: QuotationService,
        client_service: ClientService,
        service_service: ServiceService,
        settings_service: SettingsService,
        quote_to_edit: schemas.Quotation | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.quotation_service = quotation_service
        self.client_service = client_service
        self.service_service = service_service
        self.settings_service = settings_service
        self.quote_to_edit = quote_to_edit

        self.quote_items: list[schemas.QuotationItem] = []

        if self.quote_to_edit:
            self.setWindowTitle(f"تعديل عرض سعر: {self.quote_to_edit.quote_number}")
        else:
            self.setWindowTitle("عرض سعر جديد")

        self.setMinimumWidth(700)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        self.clients_list = self.client_service.get_all_clients()
        self.services_list = self.service_service.get_all_services()

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        # === Widget المسح الذكي للفواتير ===
        gemini_api_key = self.settings_service.get_setting("gemini_api_key") or os.getenv("GEMINI_API_KEY")
        self.scan_widget = InvoiceScanWidget(api_key=gemini_api_key)
        self.scan_widget.scan_completed.connect(self._on_invoice_scanned)
        self.scan_widget.scan_failed.connect(self._on_scan_failed)
        self.main_layout.addWidget(self.scan_widget)

        form_layout = QFormLayout()

        self.client_combo = QComboBox()
        for client in self.clients_list:
            self.client_combo.addItem(client.name, userData=client)

        self.issue_date_input = QDateEdit(QDate.currentDate())
        self.issue_date_input.setCalendarPopup(True)
        self.expiry_date_input = QDateEdit(QDate.currentDate().addDays(14))
        self.expiry_date_input.setCalendarPopup(True)

        self.discount_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.discount_rate_input.setValue(0.0)
        self.discount_rate_input.setSuffix(" %")

        self.tax_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.default_tax_rate = float(self.settings_service.get_setting("default_tax_rate") or 0.0)
        self.tax_rate_input.setValue(self.default_tax_rate)
        self.tax_rate_input.setSuffix(" %")

        base_notes = self.settings_service.get_setting("default_notes") or "عرض السعر صالح لمدة 14 يوم."
        self.default_notes = base_notes.replace("الفاتورة", "عرض السعر")
        self.notes_input = QLineEdit(self.default_notes)

        form_layout.addRow(QLabel("العميل:"), self.client_combo)
        form_layout.addRow(QLabel("تاريخ الإصدار:"), self.issue_date_input)
        form_layout.addRow(QLabel("تاريخ الانتهاء:"), self.expiry_date_input)
        form_layout.addRow(QLabel("الخصم (%):"), self.discount_rate_input)
        form_layout.addRow(QLabel("الضريبة (%):"), self.tax_rate_input)
        form_layout.addRow(QLabel("الملاحظات:"), self.notes_input)

        self.main_layout.addLayout(form_layout)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        self.main_layout.addWidget(divider)

        self.main_layout.addWidget(QLabel("إضافة بنود عرض السعر:"))
        add_item_layout = QHBoxLayout()
        self.service_combo = QComboBox()
        for service in self.services_list:
            self.service_combo.addItem(f"{service.name} ({service.default_price})", userData=service)

        self.item_price_input = CustomSpinBox(decimals=2, minimum=0, maximum=999999)
        self.item_quantity_input = CustomSpinBox(decimals=2, minimum=0.1, maximum=100)
        self.item_quantity_input.setValue(1.0)
        self.add_item_button = QPushButton("➕ إضافة البند")

        add_item_layout.addWidget(self.service_combo, 3)
        add_item_layout.addWidget(QLabel("الكمية:"))
        add_item_layout.addWidget(self.item_quantity_input, 1)
        add_item_layout.addWidget(QLabel("السعر:"))
        add_item_layout.addWidget(self.item_price_input, 1)
        add_item_layout.addWidget(self.add_item_button, 1)
        self.main_layout.addLayout(add_item_layout)

        self.service_combo.currentIndexChanged.connect(self.on_service_selected)
        self.add_item_button.clicked.connect(self.add_item_to_table)

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels([
            "الخدمة/الوصف",
            "الكمية",
            "سعر الوحدة",
            "خصم %",
            "الإجمالي",
            "حذف",
        ])

        # السماح بالتحرير للكمية والسعر والخصم فقط
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.items_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        header = self.items_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        # تفعيل cellChanged لحساب الإجمالي عند التعديل
        self.items_table.cellChanged.connect(self.on_item_cell_changed)
        self.main_layout.addWidget(self.items_table)

        self.save_button = QPushButton()
        self.save_button.clicked.connect(self.save_quotation)
        self.main_layout.addWidget(self.save_button)

        self.on_service_selected(0)

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

        if self.quote_to_edit:
            self.populate_form_for_edit()
            self.save_button.setText("💾 حفظ التعديلات")
        else:
            self.save_button.setText("💾 حفظ كعرض سعر جديد")
            self.tax_rate_input.setValue(self.default_tax_rate)
            self.notes_input.setText(self.default_notes)

    def populate_form_for_edit(self):
        if not self.quote_to_edit:
            return

        client_index = self.client_combo.findText(self.quote_to_edit.client_id)
        if client_index != -1:
            self.client_combo.setCurrentIndex(client_index)

        self.issue_date_input.setDate(self._to_qdate(self.quote_to_edit.issue_date))
        self.expiry_date_input.setDate(self._to_qdate(self.quote_to_edit.expiry_date))
        self.discount_rate_input.setValue(self.quote_to_edit.discount_rate)
        self.tax_rate_input.setValue(self.quote_to_edit.tax_rate)
        self.notes_input.setText(self.quote_to_edit.notes or "")

        self.quote_items.clear()
        self.items_table.setRowCount(0)
        for item in self.quote_to_edit.items:
            self.add_item_to_table(item)

    def on_service_selected(self, index):
        service = self.service_combo.currentData()
        if service:
            self.item_price_input.setValue(service.default_price)

    def add_item_to_table(self, item_to_add: schemas.QuotationItem | None = None):
        if item_to_add:
            item_schema = item_to_add
            # إعادة حساب الإجمالي مع الخصم (في حالة تحميل عرض سعر موجود)
            subtotal = item_schema.quantity * item_schema.unit_price
            item_schema.discount_amount = subtotal * (item_schema.discount_rate / 100)
            item_schema.total = subtotal - item_schema.discount_amount
        else:
            service = self.service_combo.currentData()
            quantity = self.item_quantity_input.value()
            price = self.item_price_input.value()

            if not service or quantity <= 0:
                QMessageBox.warning(self, "خطأ", "الرجاء اختيار خدمة وكمية صحيحة")
                return

            subtotal_item = quantity * price
            item_schema = schemas.QuotationItem(
                service_id=service._mongo_id or str(service.id),
                description=service.name,
                quantity=quantity,
                unit_price=price,
                discount_rate=0.0,
                discount_amount=0.0,
                total=subtotal_item,
            )

        self.quote_items.append(item_schema)

        row = self.items_table.rowCount()
        self.items_table.insertRow(row)

        # تعطيل الإشارات مؤقتاً
        self.items_table.blockSignals(True)

        desc_item = QTableWidgetItem(item_schema.description)
        desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.items_table.setItem(row, 0, desc_item)
        self.items_table.setItem(row, 1, QTableWidgetItem(f"{item_schema.quantity:.2f}"))
        self.items_table.setItem(row, 2, QTableWidgetItem(f"{item_schema.unit_price:.2f}"))
        self.items_table.setItem(row, 3, QTableWidgetItem(f"{item_schema.discount_rate:.2f}"))

        total_item = QTableWidgetItem(f"{item_schema.total:.2f}")
        total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.items_table.setItem(row, 4, total_item)

        delete_btn = QPushButton("🗑️")
        delete_btn.setStyleSheet("background-color: #ef4444; color: white;")
        delete_btn.clicked.connect(lambda _, r=row: self.delete_item(r))
        self.items_table.setCellWidget(row, 5, delete_btn)

        # إعادة تفعيل الإشارات
        self.items_table.blockSignals(False)

    def on_item_cell_changed(self, row, column):
        """معالج تغيير خلية في جدول البنود"""
        if row >= len(self.quote_items):
            return

        try:
            self.items_table.blockSignals(True)
            item = self.quote_items[row]

            if column in [1, 2, 3]:  # الكمية، السعر، أو الخصم
                new_val_str = self.items_table.item(row, column).text()
                new_val_float = float(new_val_str.replace(",", ""))

                if column == 1:
                    item.quantity = new_val_float
                elif column == 2:
                    item.unit_price = new_val_float
                elif column == 3:
                    item.discount_rate = new_val_float

                # حساب الإجمالي مع الخصم
                subtotal_item = item.quantity * item.unit_price
                item.discount_amount = subtotal_item * (item.discount_rate / 100)
                item.total = subtotal_item - item.discount_amount

                self.items_table.item(row, 4).setText(f"{item.total:.2f}")
        except (ValueError, AttributeError) as e:
            print(f"ERROR: [QuotationEditor] خطأ في تحديث البند: {e}")
        finally:
            self.items_table.blockSignals(False)

    def delete_item(self, row_index: int):
        if row_index >= len(self.quote_items):
            return

        del self.quote_items[row_index]
        self.items_table.removeRow(row_index)
        self._rebind_delete_buttons()

    def _rebind_delete_buttons(self):
        for row in range(self.items_table.rowCount()):
            button = self.items_table.cellWidget(row, 5)
            if button is None:
                continue
            try:
                button.clicked.disconnect()
            except TypeError:
                pass
            button.clicked.connect(lambda _, r=row: self.delete_item(r))

    def save_quotation(self):
        selected_client = self.client_combo.currentData()

        if not selected_client:
            QMessageBox.warning(self, "خطأ", "الرجاء اختيار عميل")
            return
        if not self.quote_items:
            QMessageBox.warning(self, "خطأ", "الرجاء إضافة بند واحد على الأقل")
            return

        try:
            quote_data_dict = {
                "client_id": selected_client.name,
                "issue_date": self.issue_date_input.dateTime().toPyDateTime(),
                "expiry_date": self.expiry_date_input.dateTime().toPyDateTime(),
                "discount_rate": self.discount_rate_input.value(),
                "tax_rate": self.tax_rate_input.value(),
                "status": schemas.QuotationStatus.DRAFT,
                "currency": schemas.CurrencyCode.EGP,
                "items": self.quote_items,
                "notes": self.notes_input.text(),
            }

            if self.quote_to_edit:
                print("INFO: [QuoteEditor] حفظ في وضع التعديل...")
                self.quotation_service.update_quotation(
                    self.quote_to_edit.quote_number,
                    quote_data_dict,
                )
                QMessageBox.information(self, "نجاح", "تم حفظ التعديلات بنجاح.")
            else:
                print("INFO: [QuoteEditor] حفظ في وضع جديد...")
                created_quote = self.quotation_service.create_new_quotation(quote_data_dict)
                QMessageBox.information(
                    self,
                    "نجاح",
                    f"تم حفظ عرض السعر بنجاح برقم:\n{created_quote.quote_number}",
                )

            self.accept()

        except Exception as e:
            print(f"ERROR: [QuoteEditor] فشل حفظ عرض السعر: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل حفظ عرض السعر:\n{e}")

    @staticmethod
    def _to_qdate(value: datetime.datetime) -> QDate:
        return QDate(value.year, value.month, value.day)

    # === معالجة نتائج المسح الذكي ===

    def _on_invoice_scanned(self, data: dict):
        """تعبئة الحقول تلقائياً من نتيجة المسح الذكي"""
        try:
            # تعبئة التاريخ
            invoice_date = data.get('invoice_date', '')
            if invoice_date:
                date = QDate.fromString(invoice_date, 'yyyy-MM-dd')
                if date.isValid():
                    self.issue_date_input.setDate(date)
                    self.expiry_date_input.setDate(date.addDays(14))

            # تعبئة الضريبة
            tax_amount = data.get('tax_amount', 0)
            total_amount = data.get('total_amount', 0)
            if tax_amount > 0 and total_amount > 0:
                # حساب نسبة الضريبة التقريبية
                subtotal = total_amount - tax_amount
                if subtotal > 0:
                    tax_rate = (tax_amount / subtotal) * 100
                    self.tax_rate_input.setValue(round(tax_rate, 2))

            # تعبئة الملاحظات باسم التاجر
            merchant_name = data.get('merchant_name', '')
            if merchant_name:
                current_notes = self.notes_input.text()
                self.notes_input.setText(f"فاتورة من: {merchant_name}\n{current_notes}")

            # تعبئة البنود
            items = data.get('items', [])
            for item in items:
                item_name = item.get('name', 'بند')
                quantity = float(item.get('qty', 1) or 1)
                price = float(item.get('price', 0) or 0)

                if price > 0:
                    subtotal_item = quantity * price
                    item_schema = schemas.QuotationItem(
                        service_id="scanned_item",
                        description=item_name,
                        quantity=quantity,
                        unit_price=price,
                        discount_rate=0.0,
                        discount_amount=0.0,
                        total=subtotal_item,
                    )
                    self.quote_items.append(item_schema)

                    row = self.items_table.rowCount()
                    self.items_table.insertRow(row)
                    self.items_table.blockSignals(True)

                    desc_item = QTableWidgetItem(item_schema.description)
                    desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.items_table.setItem(row, 0, desc_item)
                    self.items_table.setItem(row, 1, QTableWidgetItem(f"{item_schema.quantity:.2f}"))
                    self.items_table.setItem(row, 2, QTableWidgetItem(f"{item_schema.unit_price:.2f}"))
                    self.items_table.setItem(row, 3, QTableWidgetItem(f"{item_schema.discount_rate:.2f}"))

                    total_item = QTableWidgetItem(f"{item_schema.total:.2f}")
                    total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.items_table.setItem(row, 4, total_item)

                    delete_btn = QPushButton("🗑️")
                    delete_btn.setStyleSheet("background-color: #ef4444; color: white;")
                    delete_btn.clicked.connect(lambda _, r=row: self.delete_item(r))
                    self.items_table.setCellWidget(row, 5, delete_btn)

                    self.items_table.blockSignals(False)

            # رسالة نجاح
            items_count = len(items)
            QMessageBox.information(
                self,
                "✅ تم المسح بنجاح",
                f"تم استخراج {items_count} بند من الفاتورة.\nيرجى مراجعة البيانات قبل الحفظ."
            )

        except Exception as e:
            print(f"ERROR: [QuotationEditor] خطأ في معالجة نتيجة المسح: {e}")
            QMessageBox.warning(self, "تحذير", f"تم المسح لكن حدث خطأ في التعبئة:\n{e}")

    def _on_scan_failed(self, error_msg: str):
        """معالجة فشل المسح"""
        QMessageBox.warning(
            self,
            "❌ فشل المسح",
            f"لم نتمكن من قراءة الفاتورة:\n{error_msg}\n\nيمكنك إدخال البيانات يدوياً."
        )
