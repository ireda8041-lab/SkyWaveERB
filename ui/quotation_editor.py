import datetime

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
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.client_service import ClientService
from services.quotation_service import QuotationService
from services.service_service import ServiceService
from services.settings_service import SettingsService
from ui.custom_spinbox import CustomSpinBox
from ui.styles import TABLE_STYLE_DARK, create_centered_item


class QuotationEditorWindow(QDialog):
    """نافذة لإنشاء أو تعديل عرض سعر - تصميم متجاوب."""

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

        # 📱 Responsive: الحد الأدنى فقط
        self.setMinimumWidth(650)
        self.setMinimumHeight(550)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تطبيق شريط العنوان المخصص
        from ui.styles import COLORS, setup_custom_title_bar
        setup_custom_title_bar(self)
        
        # تنسيق عام للنافذة - بسيط ونظيف
        self.setStyleSheet("""
            QLabel {
                font-size: 11px;
            }
            QComboBox, QDateEdit, QLineEdit {
                font-size: 11px;
                padding: 4px 6px;
                min-height: 24px;
            }
        """)

        self.clients_list = self.client_service.get_all_clients()
        self.services_list = self.service_service.get_all_services()

        # 📱 التخطيط الرئيسي
        outer_layout = QVBoxLayout(self)
        outer_layout.setSpacing(0)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # 📱 منطقة التمرير
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['bg_medium']};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['primary']};
                border-radius: 5px;
                min-height: 30px;
            }}
        """)

        content_widget = QWidget()
        self.main_layout = QVBoxLayout(content_widget)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(15, 15, 15, 15)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area, 1)

        # === بيانات عرض السعر - تصميم بسيط ===
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(0, 0, 0, 0)

        # العميل
        self.client_combo = QComboBox()
        self.client_combo.addItem("--- اختر العميل ---", userData=None)
        for client in self.clients_list:
            self.client_combo.addItem(client.name, userData=client)
        form_layout.addRow("العميل:", self.client_combo)

        # التواريخ
        dates_layout = QHBoxLayout()
        self.issue_date_input = QDateEdit(QDate.currentDate())
        self.issue_date_input.setCalendarPopup(True)
        self.expiry_date_input = QDateEdit(QDate.currentDate().addDays(14))
        self.expiry_date_input.setCalendarPopup(True)
        dates_layout.addWidget(QLabel("من:"))
        dates_layout.addWidget(self.issue_date_input)
        dates_layout.addWidget(QLabel("إلى:"))
        dates_layout.addWidget(self.expiry_date_input)
        dates_layout.addStretch()
        form_layout.addRow("التاريخ:", dates_layout)

        # العملة
        self.currency_combo = QComboBox()
        self.currency_combo.addItem("جنيه مصري (EGP)", userData=schemas.CurrencyCode.EGP)
        self.currency_combo.addItem("دولار أمريكي (USD)", userData=schemas.CurrencyCode.USD)
        self.currency_combo.addItem("ريال سعودي (SAR)", userData=schemas.CurrencyCode.SAR)
        self.currency_combo.addItem("درهم إماراتي (AED)", userData=schemas.CurrencyCode.AED)
        form_layout.addRow("العملة:", self.currency_combo)

        # الخصم والضريبة
        finance_layout = QHBoxLayout()
        self.discount_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.discount_rate_input.setValue(0.0)
        self.discount_rate_input.setSuffix(" %")
        self.tax_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.default_tax_rate = float(self.settings_service.get_setting("default_tax_rate") or 0.0)
        self.tax_rate_input.setValue(self.default_tax_rate)
        self.tax_rate_input.setSuffix(" %")
        finance_layout.addWidget(QLabel("الخصم:"))
        finance_layout.addWidget(self.discount_rate_input)
        finance_layout.addSpacing(20)
        finance_layout.addWidget(QLabel("الضريبة:"))
        finance_layout.addWidget(self.tax_rate_input)
        finance_layout.addStretch()
        form_layout.addRow("", finance_layout)

        # الملاحظات
        base_notes = self.settings_service.get_setting("default_notes") or "شكراً لثقتكم في Sky Wave. نسعد بخدمتكم دائماً."
        self.default_notes = base_notes.replace("الفاتورة", "عرض السعر")
        self.notes_input = QLineEdit(self.default_notes)
        form_layout.addRow("الملاحظات:", self.notes_input)

        self.main_layout.addLayout(form_layout)

        # فاصل
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #374151;")
        divider.setFixedHeight(1)
        self.main_layout.addWidget(divider)

        # عنوان البنود
        items_header = QLabel("بنود عرض السعر")
        items_header.setStyleSheet("font-size: 12px; font-weight: bold; color: #60A5FA; margin: 8px 0;")
        self.main_layout.addWidget(items_header)
        
        add_item_layout = QHBoxLayout()
        add_item_layout.setSpacing(6)
        
        self.service_combo = QComboBox()
        self.service_combo.addItem("اختر الخدمة...", userData=None)
        for service in self.services_list:
            self.service_combo.addItem(f"{service.name} ({service.default_price})", userData=service)

        self.item_quantity_input = CustomSpinBox(decimals=2, minimum=0.1, maximum=100)
        self.item_quantity_input.setValue(1.0)
        
        self.item_price_input = CustomSpinBox(decimals=2, minimum=0, maximum=999999)
        
        self.add_item_button = QPushButton("➕ إضافة")
        self.add_item_button.setFixedHeight(26)

        add_item_layout.addWidget(self.service_combo, 3)
        add_item_layout.addWidget(QLabel("الكمية:"))
        add_item_layout.addWidget(self.item_quantity_input, 1)
        add_item_layout.addWidget(QLabel("السعر:"))
        add_item_layout.addWidget(self.item_price_input, 1)
        add_item_layout.addWidget(self.add_item_button)
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

        # تحسين عرض الأعمدة
        header = self.items_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # الخدمة - يتمدد
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)    # الكمية
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)    # السعر
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)    # الخصم
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)    # الإجمالي
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)    # حذف
            
        self.items_table.setColumnWidth(1, 70)   # الكمية
        self.items_table.setColumnWidth(2, 90)   # السعر
        self.items_table.setColumnWidth(3, 60)   # الخصم
        self.items_table.setColumnWidth(4, 90)   # الإجمالي
        self.items_table.setColumnWidth(5, 45)   # حذف
        
        # تنسيق الجدول
        self.items_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.items_table)
        self.items_table.verticalHeader().setDefaultSectionSize(35)
        self.items_table.setMinimumHeight(150)

        # تفعيل cellChanged لحساب الإجمالي عند التعديل
        self.items_table.cellChanged.connect(self.on_item_cell_changed)
        self.main_layout.addWidget(self.items_table)

        self.on_service_selected(0)

        # 📱 منطقة الأزرار (ثابتة في الأسفل خارج منطقة التمرير)
        from ui.styles import BUTTON_STYLES

        buttons_container = QWidget()
        buttons_container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_light']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(15, 12, 15, 12)
        buttons_layout.setSpacing(10)

        buttons_layout.addStretch()

        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton()
        self.save_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_button.clicked.connect(self.save_quotation)

        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.save_button)

        outer_layout.addWidget(buttons_container)

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
        
        # تحميل العملة
        if hasattr(self, 'currency_combo') and self.quote_to_edit.currency:
            currency = self.quote_to_edit.currency
            for i in range(self.currency_combo.count()):
                if self.currency_combo.itemData(i) == currency:
                    self.currency_combo.setCurrentIndex(i)
                    break

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

        desc_item = create_centered_item(item_schema.description)
        desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.items_table.setItem(row, 0, desc_item)
        self.items_table.setItem(row, 1, create_centered_item(f"{item_schema.quantity:.2f}"))
        self.items_table.setItem(row, 2, create_centered_item(f"{item_schema.unit_price:.2f}"))
        self.items_table.setItem(row, 3, create_centered_item(f"{item_schema.discount_rate:.2f}"))

        total_item = create_centered_item(f"{item_schema.total:.2f}")
        total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.items_table.setItem(row, 4, total_item)

        delete_btn = QPushButton("✕")
        delete_btn.setFixedSize(35, 26)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
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
                "currency": self.currency_combo.currentData() if hasattr(self, 'currency_combo') else schemas.CurrencyCode.EGP,
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

