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
from ui.smart_combobox import SmartFilterComboBox


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

        # === بيانات عرض السعر - تصميم احترافي ===
        from ui.styles import COLORS
        
        # ستايل البطاقات - بدون عنوان داخل الإطار
        card_style = f"""
            QGroupBox {{
                background-color: {COLORS['bg_medium']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                margin-top: 8px;
                padding: 15px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0;
                color: transparent;
            }}
        """
        
        # ستايل عنوان القسم
        section_title_style = f"""
            QLabel {{
                color: {COLORS['primary']};
                font-weight: bold;
                font-size: 12px;
                padding: 4px 0;
            }}
        """
        
        label_style = f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: 500;"
        
        # === بطاقة بيانات العميل ===
        from PyQt6.QtWidgets import QGroupBox, QGridLayout
        
        # عنوان القسم
        client_title = QLabel("👤 بيانات العميل")
        client_title.setStyleSheet(section_title_style)
        self.main_layout.addWidget(client_title)
        
        client_card = QGroupBox()
        client_card.setStyleSheet(card_style)
        client_layout = QGridLayout(client_card)
        client_layout.setSpacing(10)
        
        # العميل (SmartFilterComboBox مع فلترة)
        client_label = QLabel("العميل:")
        client_label.setStyleSheet(label_style)
        self.client_combo = SmartFilterComboBox()
        self.client_combo.addItem("--- اختر العميل ---", userData=None)
        for client in self.clients_list:
            self.client_combo.addItem(client.name, userData=client)
        client_layout.addWidget(client_label, 0, 0)
        client_layout.addWidget(self.client_combo, 0, 1, 1, 3)
        
        # التواريخ
        date_from_label = QLabel("من:")
        date_from_label.setStyleSheet(label_style)
        self.issue_date_input = QDateEdit(QDate.currentDate())
        self.issue_date_input.setCalendarPopup(True)
        
        date_to_label = QLabel("إلى:")
        date_to_label.setStyleSheet(label_style)
        self.expiry_date_input = QDateEdit(QDate.currentDate().addDays(14))
        self.expiry_date_input.setCalendarPopup(True)
        
        client_layout.addWidget(date_from_label, 1, 0)
        client_layout.addWidget(self.issue_date_input, 1, 1)
        client_layout.addWidget(date_to_label, 1, 2)
        client_layout.addWidget(self.expiry_date_input, 1, 3)
        
        self.main_layout.addWidget(client_card)
        
        # === بطاقة التفاصيل المالية ===
        finance_title = QLabel("💰 التفاصيل المالية")
        finance_title.setStyleSheet(section_title_style)
        self.main_layout.addWidget(finance_title)
        
        finance_card = QGroupBox()
        finance_card.setStyleSheet(card_style)
        finance_layout = QGridLayout(finance_card)
        finance_layout.setSpacing(10)
        
        # العملة
        currency_label = QLabel("العملة:")
        currency_label.setStyleSheet(label_style)
        self.currency_combo = QComboBox()
        self.currency_combo.addItem("🇪🇬 جنيه مصري (EGP)", userData=schemas.CurrencyCode.EGP)
        self.currency_combo.addItem("🇺🇸 دولار أمريكي (USD)", userData=schemas.CurrencyCode.USD)
        self.currency_combo.addItem("🇸🇦 ريال سعودي (SAR)", userData=schemas.CurrencyCode.SAR)
        self.currency_combo.addItem("🇦🇪 درهم إماراتي (AED)", userData=schemas.CurrencyCode.AED)
        finance_layout.addWidget(currency_label, 0, 0)
        finance_layout.addWidget(self.currency_combo, 0, 1, 1, 3)
        
        # الخصم (نسبة أو مبلغ)
        discount_label = QLabel("الخصم:")
        discount_label.setStyleSheet(label_style)
        
        # نوع الخصم
        self.discount_type_combo = QComboBox()
        self.discount_type_combo.addItem("نسبة %", "percent")
        self.discount_type_combo.addItem("مبلغ", "amount")
        self.discount_type_combo.setFixedWidth(80)
        self.discount_type_combo.currentIndexChanged.connect(self._on_discount_type_changed)
        
        self.discount_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.discount_rate_input.setValue(0.0)
        self.discount_rate_input.setSuffix(" %")
        
        # الضريبة
        tax_label = QLabel("الضريبة:")
        tax_label.setStyleSheet(label_style)
        self.tax_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.default_tax_rate = float(self.settings_service.get_setting("default_tax_rate") or 0.0)
        self.tax_rate_input.setValue(self.default_tax_rate)
        self.tax_rate_input.setSuffix(" %")
        
        # ترتيب الخصم: [نوع الخصم] [قيمة الخصم]
        discount_container = QHBoxLayout()
        discount_container.setSpacing(4)
        discount_container.addWidget(self.discount_type_combo)
        discount_container.addWidget(self.discount_rate_input)
        
        finance_layout.addWidget(discount_label, 1, 0)
        finance_layout.addLayout(discount_container, 1, 1)
        finance_layout.addWidget(tax_label, 1, 2)
        finance_layout.addWidget(self.tax_rate_input, 1, 3)
        
        # الملاحظات
        notes_label = QLabel("الملاحظات:")
        notes_label.setStyleSheet(label_style)
        base_notes = self.settings_service.get_setting("default_notes") or "شكراً لثقتكم في Sky Wave. نسعد بخدمتكم دائماً."
        self.default_notes = base_notes.replace("الفاتورة", "عرض السعر")
        self.notes_input = QLineEdit(self.default_notes)
        finance_layout.addWidget(notes_label, 2, 0)
        finance_layout.addWidget(self.notes_input, 2, 1, 1, 3)
        
        self.main_layout.addWidget(finance_card)

        # === بطاقة البنود ===
        items_title = QLabel("� بنبود عرض السعر")
        items_title.setStyleSheet(section_title_style)
        self.main_layout.addWidget(items_title)
        
        items_card = QGroupBox()
        items_card.setStyleSheet(card_style)
        items_layout = QVBoxLayout(items_card)
        items_layout.setSpacing(10)
        
        # صف إضافة بند جديد
        add_item_layout = QHBoxLayout()
        add_item_layout.setSpacing(8)
        
        # اختيار الخدمة (SmartFilterComboBox مع فلترة)
        service_container = QVBoxLayout()
        service_label = QLabel("الخدمة:")
        service_label.setStyleSheet(label_style)
        self.service_combo = SmartFilterComboBox()
        self.service_combo.addItem("اختر الخدمة...", userData=None)
        for service in self.services_list:
            self.service_combo.addItem(f"{service.name}", userData=service)
        service_container.addWidget(service_label)
        service_container.addWidget(self.service_combo)
        add_item_layout.addLayout(service_container, 3)
        
        # الكمية
        qty_container = QVBoxLayout()
        qty_label = QLabel("الكمية:")
        qty_label.setStyleSheet(label_style)
        self.item_quantity_input = CustomSpinBox(decimals=2, minimum=0.1, maximum=100)
        self.item_quantity_input.setValue(1.0)
        qty_container.addWidget(qty_label)
        qty_container.addWidget(self.item_quantity_input)
        add_item_layout.addLayout(qty_container, 1)
        
        # السعر
        price_container = QVBoxLayout()
        price_label = QLabel("السعر:")
        price_label.setStyleSheet(label_style)
        self.item_price_input = CustomSpinBox(decimals=2, minimum=0, maximum=999999)
        self.item_price_input.setSuffix(" ج.م")
        price_container.addWidget(price_label)
        price_container.addWidget(self.item_price_input)
        add_item_layout.addLayout(price_container, 1)
        
        # زر الإضافة
        btn_container = QVBoxLayout()
        btn_container.addWidget(QLabel(""))  # فراغ للمحاذاة
        self.add_item_button = QPushButton("➕ إضافة")
        self.add_item_button.setFixedHeight(28)
        self.add_item_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['success']};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 0 15px;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        btn_container.addWidget(self.add_item_button)
        add_item_layout.addLayout(btn_container)
        
        items_layout.addLayout(add_item_layout)

        self.service_combo.currentIndexChanged.connect(self.on_service_selected)
        self.add_item_button.clicked.connect(self.add_item_to_table)

        # جدول البنود
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels([
            "الخدمة/الوصف",
            "الكمية",
            "سعر الوحدة",
            "خصم",
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
            
        self.items_table.setColumnWidth(1, 80)   # الكمية
        self.items_table.setColumnWidth(2, 100)  # السعر
        self.items_table.setColumnWidth(3, 70)   # الخصم
        self.items_table.setColumnWidth(4, 100)  # الإجمالي
        self.items_table.setColumnWidth(5, 50)   # حذف
        
        # تنسيق الجدول
        self.items_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.items_table)
        self.items_table.verticalHeader().setDefaultSectionSize(38)
        self.items_table.setMinimumHeight(180)

        # تفعيل cellChanged لحساب الإجمالي عند التعديل
        self.items_table.cellChanged.connect(self.on_item_cell_changed)
        items_layout.addWidget(self.items_table)
        
        self.main_layout.addWidget(items_card)

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

    def _on_discount_type_changed(self, index):
        """تغيير نوع الخصم (نسبة أو مبلغ)"""
        discount_type = self.discount_type_combo.currentData()
        if discount_type == "percent":
            self.discount_rate_input.setMaximum(100)
            self.discount_rate_input.setSuffix(" %")
        else:
            self.discount_rate_input.setMaximum(999999)
            self.discount_rate_input.setSuffix(" ج.م")

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
        self.items_table.setItem(row, 3, create_centered_item(f"{item_schema.discount_amount:.2f}"))  # الخصم بالمبلغ

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
                new_val_float = float(new_val_str.replace(",", "").replace("ج.م", "").strip())

                if column == 1:
                    item.quantity = new_val_float
                elif column == 2:
                    item.unit_price = new_val_float
                elif column == 3:
                    # الخصم بالمبلغ مباشرة
                    item.discount_amount = new_val_float

                # حساب الإجمالي مع الخصم بالمبلغ
                subtotal_item = item.quantity * item.unit_price
                # الخصم لا يتجاوز الإجمالي
                item.discount_amount = min(item.discount_amount, subtotal_item)
                item.total = subtotal_item - item.discount_amount
                # حساب النسبة للحفظ
                if subtotal_item > 0:
                    item.discount_rate = (item.discount_amount / subtotal_item) * 100
                else:
                    item.discount_rate = 0

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
            # حساب الخصم حسب النوع
            discount_type = self.discount_type_combo.currentData()
            discount_value = self.discount_rate_input.value()
            
            # إذا كان الخصم بالمبلغ، نحوله لنسبة
            if discount_type == "amount" and discount_value > 0:
                subtotal = sum(item.total for item in self.quote_items)
                if subtotal > 0:
                    discount_rate = (discount_value / subtotal) * 100
                else:
                    discount_rate = 0
            else:
                discount_rate = discount_value
            
            quote_data_dict = {
                "client_id": selected_client.name,
                "issue_date": self.issue_date_input.dateTime().toPyDateTime(),
                "expiry_date": self.expiry_date_input.dateTime().toPyDateTime(),
                "discount_rate": discount_rate,
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

