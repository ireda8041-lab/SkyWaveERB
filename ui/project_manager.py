from typing import List, Optional
from datetime import datetime, timedelta
import os
from functools import partial

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QMessageBox,
    QGroupBox,
    QCheckBox,
    QTextEdit,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
)
from ui.custom_spinbox import CustomSpinBox

from core import schemas
from services.client_service import ClientService
from services.project_service import ProjectService
from services.service_service import ServiceService
from services.accounting_service import AccountingService
from ui.styles import BUTTON_STYLES, TABLE_STYLE, GROUPBOX_STYLE
from ui.auto_open_combobox import SimpleComboBox


class ProjectItemDialog(QDialog):
    """نافذة اختيار بند خدمة وإضافته للمشروع."""

    def __init__(self, services_list: List[schemas.Service], parent=None):
        super().__init__(parent)
        self.services_list = services_list
        self.selected_item: Optional[schemas.ProjectItem] = None
        self.setWindowTitle("إضافة بند جديد")
        self.setMinimumWidth(350)
        
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

        form = QFormLayout()
        self.service_combo = SimpleComboBox()
        for service in services_list:
            self.service_combo.addItem(service.name, userData=service)

        self.quantity_input = CustomSpinBox(decimals=2, minimum=0.01, maximum=1000)
        self.quantity_input.setValue(1.0)

        self.unit_price_input = CustomSpinBox(decimals=2, minimum=0.0, maximum=1_000_000)
        if services_list:
            self.unit_price_input.setValue(services_list[0].default_price)

        form.addRow("الخدمة:", self.service_combo)
        form.addRow("الكمية:", self.quantity_input)
        form.addRow("السعر:", self.unit_price_input)
        layout.addLayout(form)

        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("إضافة")
        save_btn.clicked.connect(self._handle_save)
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def _handle_save(self):
        service = self.service_combo.currentData()
        if not service:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار خدمة من القائمة")
            return

        quantity = self.quantity_input.value()
        unit_price = self.unit_price_input.value()
        total = quantity * unit_price

        self.selected_item = schemas.ProjectItem(
            service_id=service._mongo_id or str(service.id),
            description=service.name,
            quantity=quantity,
            unit_price=unit_price,
            total=total,
        )
        self.accept()

    def get_project_item(self) -> Optional[schemas.ProjectItem]:
        return self.selected_item


class ProjectEditorDialog(QDialog):
    """
    (معدلة بالكامل) شاشة إضافة/تعديل مشروع (مع الدفعة المقدمة)
    """

    def __init__(
        self,
        project_service: ProjectService,
        client_service: ClientService,
        service_service: ServiceService,
        accounting_service: AccountingService,
        project_to_edit: Optional[schemas.Project] = None,
        parent=None,
    ):
        super().__init__(parent)

        self.project_service = project_service
        self.client_service = client_service
        self.service_service = service_service
        self.accounting_service = accounting_service
        self.project_to_edit = project_to_edit
        self.is_editing = project_to_edit is not None
        self.project_items: List[schemas.ProjectItem] = []
        
        # Get settings service for default treasury account
        self.settings_service = getattr(service_service, 'settings_service', None)

        if self.is_editing:
            self.setWindowTitle(f"تعديل مشروع: {project_to_edit.name}")
        else:
            self.setWindowTitle("مشروع جديد")

        # تفعيل زر التكبير والتصغير
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
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
            QPushButton:focus, QCheckBox:focus {
                border: none;
                outline: none;
            }
        """)

        self.clients_list = self.client_service.get_all_clients()
        self.services_list = self.service_service.get_all_services()
        
        # فلترة الحسابات النقدية فقط (الخزينة والبنوك والمحافظ الإلكترونية)
        all_accounts = self.accounting_service.repo.get_all_accounts()
        self.cash_accounts = [
            acc for acc in all_accounts
            if acc.type == schemas.AccountType.CASH or 
               (acc.code and acc.code.startswith("111")) or  # الخزينة 111x
               (acc.code and acc.code.startswith("12"))      # المحافظ الإلكترونية 12xx
        ]

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # === التخطيط الأفقي الرئيسي: اليسار واليمين ===
        main_horizontal_layout = QHBoxLayout()
        
        # === الجانب الأيسر: البيانات الأساسية + بنود المشروع + الإجماليات ===
        left_side = QVBoxLayout()
        
        # --- 1. البيانات الأساسية ---
        basic_group = QGroupBox("البيانات الأساسية للمشروع")
        basic_layout = QVBoxLayout()  # استخدام VBoxLayout بدل FormLayout

        # استخدام SimpleComboBox - بسيط وآمن
        self.client_combo = SimpleComboBox()
        self.client_combo.addItem("--- اختر العميل ---", userData=None)
        for client in self.clients_list:
            self.client_combo.addItem(client.name, userData=client)
        self.client_combo.setCurrentIndex(0)
        
        # إعداد البحث السريع
        client_names = [client.name for client in self.clients_list]
        self.client_combo.setup_completer(client_names)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("مثال: باقة SEO - العميل س")

        self.status_combo = QComboBox()  # QComboBox عادي للحالة
        for status in schemas.ProjectStatus:
            self.status_combo.addItem(status.value, userData=status)
        self.status_combo.setCurrentText(schemas.ProjectStatus.ACTIVE.value)

        self.start_date_input = QDateEdit(QDate.currentDate())
        self.start_date_input.setCalendarPopup(True)
        self.end_date_input = QDateEdit(QDate.currentDate().addDays(30))
        self.end_date_input.setCalendarPopup(True)

        # ترتيب الحقول في صفوف أفقية (2 في كل صف)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("العميل:"))
        row1.addWidget(self.client_combo, 2)
        row1.addWidget(QLabel("اسم المشروع:"))
        row1.addWidget(self.name_input, 2)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("الحالة:"))
        row2.addWidget(self.status_combo, 1)
        row2.addWidget(QLabel("تاريخ الإصدار:"))
        row2.addWidget(self.start_date_input, 1)
        row2.addWidget(QLabel("تاريخ الاستحقاق:"))
        row2.addWidget(self.end_date_input, 1)
        
        basic_layout.addLayout(row1)
        basic_layout.addLayout(row2)
        basic_group.setLayout(basic_layout)
        left_side.addWidget(basic_group)

        # --- 2. بنود المشروع (الخدمات) ---
        items_group = QGroupBox("بنود المشروع (الخدمات)")
        items_layout = QVBoxLayout()
        add_item_layout = QHBoxLayout()
        # استخدام SimpleComboBox - بسيط وآمن
        self.service_combo = SimpleComboBox()
        self.service_combo.addItem("اختر الخدمة أو الباقة...", userData=None)
        for service in self.services_list:
            self.service_combo.addItem(f"{service.name} ({service.default_price})", userData=service)
        self.service_combo.setCurrentIndex(0)
        
        # إعداد البحث السريع
        service_names = [service.name for service in self.services_list]
        self.service_combo.setup_completer(service_names)
        self.item_price_input = CustomSpinBox(decimals=2, minimum=0, maximum=9999999999)
        self.item_quantity_input = CustomSpinBox(decimals=2, minimum=0.1, maximum=100)
        self.item_quantity_input.setValue(1.0)
        self.add_item_button = QPushButton("➕ إضافة البند")
        from ui.styles import BUTTON_STYLES
        self.add_item_button.setStyleSheet(BUTTON_STYLES["primary"])
        add_item_layout.addWidget(self.service_combo, 3)
        add_item_layout.addWidget(QLabel("الكمية:"))
        add_item_layout.addWidget(self.item_quantity_input, 1)
        add_item_layout.addWidget(QLabel("السعر:"))
        add_item_layout.addWidget(self.item_price_input, 1)
        add_item_layout.addWidget(self.add_item_button, 1)
        self.service_combo.currentIndexChanged.connect(self.on_service_selected)
        self.add_item_button.clicked.connect(lambda: self.add_item_to_table(item_to_add=None))
        items_layout.addLayout(add_item_layout)
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels(["البند", "الكمية", "السعر", "خصم %", "الإجمالي", "حذف"])
        
        # تفعيل التحرير البسيط للكمية والسعر والخصم
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.SelectedClicked)
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.items_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        # تخصيص عرض الأعمدة بشكل مظبوط
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # عمود الخدمة (أوسع)
        
        # تحديد عرض ثابت للأعمدة الرقمية
        self.items_table.setColumnWidth(1, 80)   # الكمية
        self.items_table.setColumnWidth(2, 100)  # السعر
        self.items_table.setColumnWidth(3, 80)   # الخصم
        self.items_table.setColumnWidth(4, 110)  # الإجمالي
        self.items_table.setColumnWidth(5, 50)   # الحذف
        
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        
        # ستايل الجدول مع editor مظبوط
        self.items_table.setStyleSheet("""
            QTableWidget {
                selection-background-color: rgba(10, 108, 241, 0.3);
                gridline-color: #374151;
            }
            QTableWidget::item:selected {
                background-color: rgba(10, 108, 241, 0.3);
            }
            QTableWidget QLineEdit {
                background-color: #1A202C;
                border: 2px solid #0A6CF1;
                border-radius: 0px;
                padding: 2px 4px;
                margin: 0px;
                color: #F8FAFC;
                font-size: 13px;
            }
        """)
        
        self.items_table.setMinimumHeight(200)
        self.items_table.verticalHeader().setDefaultSectionSize(36)  # ارتفاع الصفوف ثابت
        self.items_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.items_table.verticalHeader().setVisible(True)
        self.items_table.setShowGrid(True)
        items_layout.addWidget(self.items_table)
        items_group.setLayout(items_layout)
        left_side.addWidget(items_group)
        
        # --- 3. الإجماليات ---
        totals_group = QGroupBox("الإجماليات")
        
        totals_group = QGroupBox("الإجماليات")
        totals_form = QFormLayout()
        self.discount_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.discount_rate_input.setSuffix(" %")
        self.tax_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.tax_rate_input.setSuffix(" %")
        if self.service_service and getattr(self.service_service, "settings_service", None):
            try:
                default_tax = self.service_service.settings_service.get_setting("default_tax_rate")
                self.tax_rate_input.setValue(default_tax or 0.0)
            except Exception:
                pass
        self.total_label = QLabel("0.00 ج.م")
        self.total_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.total_label.setStyleSheet("color: #0A6CF1;")
        self.discount_rate_input.valueChanged.connect(self.update_totals)
        self.tax_rate_input.valueChanged.connect(self.update_totals)
        totals_form.addRow(QLabel("الخصم (%):"), self.discount_rate_input)
        totals_form.addRow(QLabel("الضريبة (%):"), self.tax_rate_input)
        totals_form.addRow(QLabel("<b>الإجمالي النهائي:</b>"), self.total_label)
        totals_group.setLayout(totals_form)
        left_side.addWidget(totals_group)
        
        # === الجانب الأيمن: الوصف والدفعة المقدمة ===
        right_side = QVBoxLayout()
        
        # الوصف والملاحظات
        notes_group = QGroupBox("الوصف والملاحظات")
        notes_layout = QVBoxLayout()
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("أضف ملاحظات أو شروط المشروع هنا...")
        self.notes_input.setMinimumHeight(200)
        notes_layout.addWidget(self.notes_input)
        notes_group.setLayout(notes_layout)
        right_side.addWidget(notes_group)

        # الدفعة المقدمة
        payment_group = QGroupBox("تسجيل دفعة مقدمة (اختياري)")
        payment_form = QFormLayout()
        self.payment_amount_input = CustomSpinBox(decimals=2, minimum=0, maximum=9999999)
        self.payment_amount_input.setValue(0.0)
        self.payment_amount_input.setSuffix(" EGP")
        self.payment_date_input = QDateEdit(QDate.currentDate())
        self.payment_date_input.setCalendarPopup(True)
        # استخدام SimpleComboBox - بسيط وآمن
        self.payment_account_combo = SimpleComboBox()
        self.payment_account_combo.addItem("اختر حساب البنك/الخزينة...", userData=None)
        for acc in self.cash_accounts:
            display_text = f"💰 {acc.name} ({acc.code})"
            self.payment_account_combo.addItem(display_text, userData=acc)
        
        # إعداد البحث السريع
        account_names = [acc.name for acc in self.cash_accounts]
        self.payment_account_combo.setup_completer(account_names)
        
        # Auto-select default treasury account from settings
        self._auto_select_default_treasury()
        payment_form.addRow(QLabel("المبلغ المدفوع مقدماً:"), self.payment_amount_input)
        payment_form.addRow(QLabel("تاريخ الدفع:"), self.payment_date_input)
        payment_form.addRow(QLabel("الحساب المستلم:"), self.payment_account_combo)
        payment_group.setLayout(payment_form)
        right_side.addWidget(payment_group)
        
        # إضافة الجانبين للتخطيط الأفقي الرئيسي
        main_horizontal_layout.addLayout(left_side, 3)  # البيانات والبنود على اليسار (أوسع)
        main_horizontal_layout.addLayout(right_side, 2)  # الوصف والدفعة على اليمين
        main_layout.addLayout(main_horizontal_layout)

        # --- 5. أزرار التحكم ---
        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("💾 حفظ المشروع")
        from ui.styles import BUTTON_STYLES
        self.save_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_button.clicked.connect(self.save_project)
        buttons_layout.addWidget(self.save_button)
        main_layout.addLayout(buttons_layout)

        self.setLayout(main_layout)
        self.on_service_selected(0)

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

        if self.is_editing:
            self.load_project_data()
            payment_group.setVisible(False)
    
    def _auto_select_default_treasury(self):
        """Auto-select default treasury account from settings"""
        if not self.settings_service:
            return
            
        try:
            default_treasury_code = self.settings_service.get_setting("default_treasury_account")
            if default_treasury_code:
                # Find the account in the combo box
                for i in range(self.payment_account_combo.count()):
                    account_data = self.payment_account_combo.itemData(i)
                    if account_data and account_data.code == default_treasury_code:
                        self.payment_account_combo.setCurrentIndex(i)
                        print(f"INFO: [ProjectDialog] Auto-selected default treasury: {account_data.name} ({default_treasury_code})")
                        break
        except Exception as e:
            print(f"WARNING: [ProjectDialog] Failed to auto-select default treasury: {e}")

    def load_project_data(self):
        self.name_input.setText(self.project_to_edit.name)
        client_index = -1
        project_client_ref = (self.project_to_edit.client_id or "").strip()
        for i in range(self.client_combo.count()):
            client_data = self.client_combo.itemData(i)
            if not client_data:
                continue
            client_mongo_id = getattr(client_data, "_mongo_id", None)
            client_local_id = getattr(client_data, "id", None)
            client_name = getattr(client_data, "name", "").strip()

            if (
                (client_mongo_id and client_mongo_id.strip() == project_client_ref)
                or (client_local_id is not None and str(client_local_id).strip() == project_client_ref)
                or client_name == project_client_ref
            ):
                client_index = i
                break
        if client_index != -1:
            self.client_combo.setCurrentIndex(client_index)
        status_index = self.status_combo.findText(self.project_to_edit.status.value)
        if status_index != -1:
            self.status_combo.setCurrentIndex(status_index)
        # الوصف في notes_input دلوقتي
        self.notes_input.setText(self.project_to_edit.project_notes or "")
        start_value = self.project_to_edit.start_date or datetime.datetime.now()
        end_value = self.project_to_edit.end_date or datetime.datetime.now()
        self.start_date_input.setDate(QDate(start_value.year, start_value.month, start_value.day))
        self.end_date_input.setDate(QDate(end_value.year, end_value.month, end_value.day))
        self.discount_rate_input.setValue(self.project_to_edit.discount_rate)
        self.tax_rate_input.setValue(self.project_to_edit.tax_rate)
        self.items_table.setRowCount(0)
        self.project_items.clear()
        for item in self.project_to_edit.items:
            self.add_item_to_table(item_to_add=item)
        self.update_totals()

    def on_service_selected(self, index):
        service = self.service_combo.currentData()
        if service:
            self.item_price_input.setValue(service.default_price)

    def add_item_to_table(self, item_to_add: Optional[schemas.ProjectItem] = None):
        if item_to_add is None:
            service = self.service_combo.currentData()
            quantity = self.item_quantity_input.value()
            price = self.item_price_input.value()
            
            # إذا لم يتم اختيار خدمة، تحقق من النص المكتوب
            if not service:
                service_text = self.service_combo.currentText().strip()
                if service_text:
                    # محاولة إضافة الخدمة الجديدة
                    new_service = self.check_and_add_service(service_text)
                    if new_service:
                        service = new_service
                        price = new_service.default_price
                        self.item_price_input.setValue(price)
                    else:
                        return  # المستخدم رفض الإضافة
                else:
                    QMessageBox.warning(self, "خطأ", "الرجاء اختيار خدمة")
                    return
            
            if quantity <= 0:
                QMessageBox.warning(self, "خطأ", "الرجاء إدخال كمية صحيحة")
                return
            # حساب الإجمالي بدون خصم أولاً
            subtotal_item = quantity * price
            item_schema = schemas.ProjectItem(
                service_id=service._mongo_id or str(service.id),
                description=service.name,
                quantity=quantity,
                unit_price=price,
                discount_rate=0.0,
                discount_amount=0.0,
                total=subtotal_item
            )
        else:
            item_schema = item_to_add
        self.project_items.append(item_schema)
        self._rebuild_items_table()
        self.update_totals()

    def delete_item(self, row_index: int):
        try:
            del self.project_items[row_index]
            self._rebuild_items_table()
            self.update_totals()
        except Exception as e:
            print(f"ERROR: [ProjectEditor] فشل حذف البند: {e}")

    def _rebuild_items_table(self):
        # فصل الإشارة مؤقتاً لتجنب التكرار
        try:
            self.items_table.cellChanged.disconnect(self.on_item_changed_simple)
        except:
            pass
        
        self.items_table.setRowCount(0)
        for index, item in enumerate(self.project_items):
            self.items_table.insertRow(index)
            
            # عمود الوصف (غير قابل للتعديل، في الوسط)
            desc_item = QTableWidgetItem(item.description)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            desc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.items_table.setItem(index, 0, desc_item)
            
            # عمود الكمية (قابل للتعديل، في الوسط)
            qty_item = QTableWidgetItem(str(item.quantity))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            qty_item.setToolTip("دبل كليك للتعديل")
            qty_item.setBackground(QColor("#1A202C"))
            self.items_table.setItem(index, 1, qty_item)
            
            # عمود السعر (قابل للتعديل، في الوسط)
            price_item = QTableWidgetItem(str(item.unit_price))
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            price_item.setToolTip("دبل كليك للتعديل")
            price_item.setBackground(QColor("#1A202C"))
            self.items_table.setItem(index, 2, price_item)
            
            # عمود الخصم (قابل للتعديل، في الوسط)
            discount_text = str(item.discount_rate) if item.discount_rate > 0 else "0"
            discount_item = QTableWidgetItem(discount_text)
            discount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            discount_item.setToolTip("دبل كليك للتعديل (بدون %)")
            discount_item.setBackground(QColor("#1A202C"))
            self.items_table.setItem(index, 3, discount_item)
            
            # عمود الإجمالي (غير قابل للتعديل، في الوسط)
            total_item = QTableWidgetItem(f"{item.total:,.2f}")
            total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.items_table.setItem(index, 4, total_item)
            
            # زرار الحذف (صغير ومظبوط)
            delete_container = QWidget()
            delete_container.setStyleSheet("background-color: transparent;")
            delete_layout = QHBoxLayout(delete_container)
            delete_layout.setContentsMargins(0, 0, 0, 0)
            delete_layout.setSpacing(0)
            delete_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            delete_btn = QPushButton("X")
            delete_btn.setFixedSize(26, 24)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
            """)
            delete_btn.clicked.connect(lambda _, r=index: self.delete_item(r))
            delete_layout.addWidget(delete_btn)
            
            self.items_table.setCellWidget(index, 5, delete_container)
        
        # إعادة ربط الإشارة
        self.items_table.cellChanged.connect(self.on_item_changed_simple)

    def on_quantity_changed(self, row: int, value: float):
        """تحديث الكمية وإعادة حساب الإجمالي"""
        try:
            self.project_items[row].quantity = value
            self._recalculate_item_total(row)
        except Exception as e:
            print(f"ERROR: [ProjectEditor] on_quantity_changed: {e}")
    
    def on_price_changed(self, row: int, value: float):
        """تحديث السعر وإعادة حساب الإجمالي"""
        try:
            self.project_items[row].unit_price = value
            self._recalculate_item_total(row)
        except Exception as e:
            print(f"ERROR: [ProjectEditor] on_price_changed: {e}")
    
    def on_discount_changed(self, row: int, value: float):
        """تحديث الخصم وإعادة حساب الإجمالي"""
        try:
            self.project_items[row].discount_rate = value
            self._recalculate_item_total(row)
        except Exception as e:
            print(f"ERROR: [ProjectEditor] on_discount_changed: {e}")
    
    def on_item_changed_simple(self, row: int, column: int):
        """دالة بسيطة للتعامل مع تغيير الخلايا"""
        if row >= len(self.project_items):
            return
        
        try:
            item = self.project_items[row]
            cell_item = self.items_table.item(row, column)
            if not cell_item:
                return
                
            cell_text = cell_item.text().strip()
            
            if column == 1:  # الكمية
                try:
                    item.quantity = float(cell_text) if cell_text else item.quantity
                except ValueError:
                    cell_item.setText(str(item.quantity))
                    return
                    
            elif column == 2:  # السعر
                try:
                    item.unit_price = float(cell_text) if cell_text else item.unit_price
                except ValueError:
                    cell_item.setText(str(item.unit_price))
                    return
                    
            elif column == 3:  # الخصم
                try:
                    discount_text = cell_text.replace('%', '').strip()
                    item.discount_rate = float(discount_text) if discount_text else 0
                except ValueError:
                    cell_item.setText(str(item.discount_rate))
                    return
            
            # إعادة حساب الإجمالي
            subtotal = item.quantity * item.unit_price
            discount_amount = subtotal * (item.discount_rate / 100)
            item.discount_amount = discount_amount
            item.total = subtotal - discount_amount
            
            # تحديث عمود الإجمالي
            total_item = self.items_table.item(row, 4)
            if total_item:
                total_item.setText(f"{item.total:,.2f}")
            
            # تحديث الإجماليات الكلية
            self.update_totals()
            
        except Exception as e:
            print(f"ERROR: خطأ في تحديث البند: {e}")
    
    def _recalculate_item_total(self, row: int):
        """إعادة حساب إجمالي البند"""
        item = self.project_items[row]
        subtotal = item.quantity * item.unit_price
        discount_amount = subtotal * (item.discount_rate / 100)
        item.discount_amount = discount_amount
        item.total = subtotal - discount_amount
        
        # تحديث عمود الإجمالي في الجدول
        total_item = self.items_table.item(row, 4)
        if total_item:
            total_item.setText(f"{item.total:,.2f}")
        
        # تحديث الإجماليات الكلية
        self.update_totals()

    def update_totals(self):
        subtotal = sum(item.total for item in self.project_items)
        discount_rate = self.discount_rate_input.value()
        discount_amount = subtotal * (discount_rate / 100)
        taxable_amount = subtotal - discount_amount
        tax_rate = self.tax_rate_input.value()
        tax_amount = taxable_amount * (tax_rate / 100)
        total_amount = taxable_amount + tax_amount
        self.total_label.setText(f"{total_amount:,.2f} ج.م")

    def on_client_text_changed(self, text: str):
        """التحقق من العميل عند تغيير النص"""
        if not text or len(text) < 2:
            return
        
        # البحث عن العميل في القائمة
        found = False
        for i in range(self.client_combo.count()):
            if self.client_combo.itemText(i).lower() == text.lower():
                found = True
                break
        
        # إذا لم يتم العثور على العميل
        if not found and text.strip():
            # تأخير السؤال قليلاً لتجنب الإزعاج أثناء الكتابة
            pass  # سيتم السؤال عند الضغط على Enter أو فقدان التركيز
    
    def on_service_text_changed(self, text: str):
        """التحقق من الخدمة عند تغيير النص"""
        if not text or len(text) < 2:
            return
        
        # البحث عن الخدمة في القائمة
        found = False
        for i in range(self.service_combo.count()):
            item_text = self.service_combo.itemText(i)
            # استخراج اسم الخدمة فقط (قبل القوس)
            service_name = item_text.split('(')[0].strip()
            if service_name.lower() == text.lower():
                found = True
                break
        
        if not found and text.strip():
            pass  # سيتم السؤال عند محاولة الإضافة
    
    def _add_new_client(self, client_name: str) -> Optional[schemas.Client]:
        """دالة إضافة عميل جديد للـ ProfessionalComboBox"""
        try:
            # فتح نافذة إضافة عميل جديد
            from ui.client_editor_dialog import ClientEditorDialog
            dialog = ClientEditorDialog(self.client_service, parent=self)
            dialog.name_input.setText(client_name)  # ملء الاسم مسبقاً
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # تحديث قائمة العملاء
                self.clients_list = self.client_service.get_all_clients()
                
                # العثور على العميل الجديد
                new_client = None
                for client in self.clients_list:
                    if client.name.lower() == client_name.lower():
                        new_client = client
                        break
                
                if new_client:
                    QMessageBox.information(self, "نجح", f"تم إضافة العميل '{new_client.name}' بنجاح!")
                    return new_client
            
            return None
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في إضافة العميل: {e}")
            return None
    
    def _add_new_service(self, service_name: str) -> Optional[schemas.Service]:
        """دالة إضافة خدمة جديدة للـ ProfessionalComboBox"""
        try:
            # فتح نافذة إضافة خدمة جديدة
            from ui.service_editor_dialog import ServiceEditorDialog
            dialog = ServiceEditorDialog(self.service_service, parent=self)
            dialog.name_input.setText(service_name)  # ملء الاسم مسبقاً
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # تحديث قائمة الخدمات
                self.services_list = self.service_service.get_all_services()
                
                # العثور على الخدمة الجديدة
                new_service = None
                for service in self.services_list:
                    if service.name.lower() == service_name.lower():
                        new_service = service
                        break
                
                if new_service:
                    QMessageBox.information(self, "نجح", f"تم إضافة الخدمة '{new_service.name}' بنجاح!")
                    return new_service
            
            return None
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في إضافة الخدمة: {e}")
            return None

    def check_and_add_client(self, client_name: str) -> Optional[schemas.Client]:
        """التحقق من العميل وإضافته إذا لم يكن موجوداً"""
        # البحث عن العميل
        for client in self.clients_list:
            if client.name.lower() == client_name.lower():
                return client
        
        # العميل غير موجود - السؤال عن الإضافة
        reply = QMessageBox.question(
            self,
            "عميل جديد",
            f"العميل '{client_name}' غير موجود.\nهل تريد إضافته كعميل جديد؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            return self._add_new_client(client_name)
        
        return None
    
    def check_and_add_service(self, service_name: str) -> Optional[schemas.Service]:
        """التحقق من الخدمة وإضافتها إذا لم تكن موجودة"""
        # البحث عن الخدمة
        for service in self.services_list:
            if service.name.lower() == service_name.lower():
                return service
        
        # الخدمة غير موجودة - السؤال عن الإضافة
        reply = QMessageBox.question(
            self,
            "خدمة جديدة",
            f"الخدمة '{service_name}' غير موجودة.\nهل تريد إضافتها كخدمة جديدة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # فتح نافذة إضافة خدمة جديدة
            from ui.service_editor_dialog import ServiceEditorDialog
            dialog = ServiceEditorDialog(self.service_service, parent=self)
            dialog.name_input.setText(service_name)  # ملء الاسم مسبقاً
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # تحديث قائمة الخدمات
                self.services_list = self.service_service.get_all_services()
                
                # إضافة الخدمة الجديدة للـ ComboBox
                new_service = self.services_list[-1]  # آخر خدمة مضافة
                self.service_combo.addItem(f"{new_service.name} ({new_service.default_price})", userData=new_service)
                self.service_combo.setCurrentText(new_service.name)
                
                QMessageBox.information(self, "نجح", f"تم إضافة الخدمة '{new_service.name}' بنجاح!")
                return new_service
        
        return None

    def save_project(self):
        """
        (معدلة) تحفظ المشروع + الدفعة المقدمة
        """
        selected_client = self.client_combo.currentData()
        selected_status = self.status_combo.currentData()

        # التحقق من اسم المشروع
        if not self.name_input.text():
            QMessageBox.warning(self, "خطأ", "اسم المشروع مطلوب")
            return
        
        # التحقق من العميل - إذا كان مكتوباً ولكن غير محدد
        if not selected_client:
            client_text = self.client_combo.currentText().strip()
            if client_text:
                # محاولة إضافة العميل الجديد
                new_client = self.check_and_add_client(client_text)
                if new_client:
                    selected_client = new_client
                else:
                    return  # المستخدم رفض الإضافة
            else:
                QMessageBox.warning(self, "خطأ", "العميل مطلوب")
                return

        # 1. تجميع بيانات المشروع
        project_data = {
            "name": self.name_input.text(),
            "client_id": selected_client.name,
            "status": selected_status,
            "description": "",  # الوصف في notes_input دلوقتي
            "start_date": self.start_date_input.dateTime().toPyDateTime(),
            "end_date": self.end_date_input.dateTime().toPyDateTime(),
            "items": self.project_items,
            "discount_rate": self.discount_rate_input.value(),
            "tax_rate": self.tax_rate_input.value(),
            "project_notes": self.notes_input.toPlainText(),
            "currency": schemas.CurrencyCode.EGP
        }

        # 2. (الجديد) تجميع بيانات الدفعة المقدمة
        payment_data = {}
        payment_amount = self.payment_amount_input.value()
        selected_account = self.payment_account_combo.currentData()

        if payment_amount > 0 and not selected_account:
            QMessageBox.warning(self, "خطأ", "الرجاء اختيار الحساب المستلم للدفعة المقدمة.")
            return

        if payment_amount > 0 and selected_account:
            payment_data = {
                "amount": payment_amount,
                "date": self.payment_date_input.dateTime().toPyDateTime(),
                "account_id": selected_account.code
            }

        # حساب إجمالي المشروع للتحقق من نسبة الدفعة المقدمة
        subtotal = sum(item.total for item in self.project_items)
        discount_rate = self.discount_rate_input.value()
        discount_amount = subtotal * (discount_rate / 100)
        taxable_amount = subtotal - discount_amount
        tax_rate = self.tax_rate_input.value()
        tax_amount = taxable_amount * (tax_rate / 100)
        total_amount = taxable_amount + tax_amount

        # تحذير إذا كانت الدفعة المقدمة أقل من 70% (فقط للمشاريع الجديدة)
        if not self.is_editing and total_amount > 0:
            min_payment = total_amount * 0.70  # 70%
            if payment_amount < min_payment:
                payment_percent = (payment_amount / total_amount * 100) if total_amount > 0 else 0
                reply = QMessageBox.warning(
                    self,
                    "⚠️ تحذير - دفعة مقدمة منخفضة",
                    f"الدفعة المقدمة ({payment_amount:,.2f}) تمثل فقط {payment_percent:.1f}% من إجمالي المشروع ({total_amount:,.2f}).\n\n"
                    f"الحد الأدنى الموصى به: 70% ({min_payment:,.2f})\n\n"
                    f"هل تريد المتابعة على أي حال؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

        try:
            if self.is_editing:
                self.project_service.update_project(self.project_to_edit.name, project_data)
                QMessageBox.information(self, "تم", "تم حفظ التعديلات بنجاح.")
            else:
                self.project_service.create_project(project_data, payment_data)
                QMessageBox.information(self, "تم", "تم إضافة المشروع والدفعة المقدمة (إن وجدت) بنجاح.")

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}\n\n(تلميح: قد يكون اسم المشروع مكرر)")


class ProjectManagerTab(QWidget):
    def __init__(
        self,
        project_service: ProjectService,
        client_service: ClientService,
        service_service: ServiceService,
        accounting_service: AccountingService,
        printing_service=None,
        template_service=None,
        parent=None,
    ):
        super().__init__(parent)

        self.project_service = project_service
        self.client_service = client_service
        self.service_service = service_service
        self.accounting_service = accounting_service
        self.printing_service = printing_service
        self.template_service = template_service
        self.projects_list: List[schemas.Project] = []
        self.selected_project: Optional[schemas.Project] = None

        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # --- 1. الجزء الأيسر (الجدول والأزرار) ---
        left_panel = QVBoxLayout()
        buttons_layout = QHBoxLayout()
        
        self.add_button = QPushButton("➕ إضافة مشروع جديد")
        self.add_button.setStyleSheet(BUTTON_STYLES["success"])
        self.add_button.clicked.connect(lambda: self.open_editor(project_to_edit=None))

        self.edit_button = QPushButton("✏️ تعديل المشروع")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.clicked.connect(self.open_editor_for_selected)
        self.edit_button.setEnabled(False)

        # زرار تسجيل دفعة جديدة
        self.payment_button = QPushButton("💰 تسجيل دفعة")
        self.payment_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.payment_button.clicked.connect(self.open_payment_dialog)
        self.payment_button.setEnabled(False)

        # زرار عرض الربحية
        self.profit_button = QPushButton("📊 الربحية")
        self.profit_button.setStyleSheet(BUTTON_STYLES["info"])
        self.profit_button.clicked.connect(self.open_profit_dialog)
        self.profit_button.setEnabled(False)

        # زرار طباعة الفاتورة
        self.print_button = QPushButton("🖨️ طباعة فاتورة")
        self.print_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.print_button.clicked.connect(self.print_invoice)
        self.print_button.setEnabled(False)

        # WhatsApp button removed - feature disabled

        # أزرار قوالب الفواتير
        
        self.preview_template_button = QPushButton("👁️ معاينة الفاتورة")
        self.preview_template_button.setStyleSheet(BUTTON_STYLES["info"])
        self.preview_template_button.clicked.connect(self.preview_invoice_template)
        self.preview_template_button.setEnabled(False)



        # زرار التحديث
        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.clicked.connect(self.load_projects_data)

        self.show_archived_checkbox = QCheckBox("إظهار المشاريع المؤرشفة")
        self.show_archived_checkbox.clicked.connect(self.load_projects_data)

        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.edit_button)
        buttons_layout.addWidget(self.payment_button)
        buttons_layout.addWidget(self.profit_button)
        buttons_layout.addWidget(self.print_button)
        buttons_layout.addWidget(self.preview_template_button)
        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.show_archived_checkbox)
        left_panel.addLayout(buttons_layout)

        table_groupbox = QGroupBox("قايمة المشاريع")
        table_layout = QVBoxLayout()
        table_groupbox.setLayout(table_layout)
        
        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar
        self.projects_table = QTableWidget()
        self.projects_table.setColumnCount(4)
        self.projects_table.setHorizontalHeaderLabels(["اسم المشروع", "العميل", "الحالة", "تاريخ البدء"])
        
        self.search_bar = UniversalSearchBar(
            self.projects_table,
            placeholder="🔍 بحث (اسم المشروع، العميل، الحالة، التاريخ)..."
        )
        table_layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===
        
        self.projects_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.projects_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.projects_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.projects_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.projects_table.itemSelectionChanged.connect(self.on_project_selection_changed)
        

        # إضافة دبل كليك للتعديل
        self.projects_table.itemDoubleClicked.connect(self.open_editor_for_selected)
        table_layout.addWidget(self.projects_table)
        left_panel.addWidget(table_groupbox, 1)
        main_layout.addLayout(left_panel, 3)

        # --- 2. (معدل) الجزء الأيمن (لوحة معاينة الربحية) ---
        self.preview_groupbox = QGroupBox("معاينة ربحية المشروع")
        self.preview_groupbox.setMinimumWidth(400)
        preview_layout = QVBoxLayout()
        self.preview_groupbox.setLayout(preview_layout)

        kpi_layout = QHBoxLayout()
        self.revenue_card = self.create_kpi_card("إجمالي العقد", "0.00", "#10b981")
        self.paid_card = self.create_kpi_card("إجمالي المدفوع", "0.00", "#3b82f6")
        self.due_card = self.create_kpi_card("الرصيد المتبقي", "0.00", "#f59e0b")
        kpi_layout.addWidget(self.revenue_card)
        kpi_layout.addWidget(self.paid_card)
        kpi_layout.addWidget(self.due_card)
        preview_layout.addLayout(kpi_layout)

        preview_layout.addWidget(QLabel("<b>الدفعات المسجلة:</b>"))
        self.preview_payments_table = QTableWidget()
        self.preview_payments_table.setColumnCount(3)
        self.preview_payments_table.setHorizontalHeaderLabels(["التاريخ", "المبلغ", "الحساب"])
        self.preview_payments_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.preview_payments_table.setMaximumHeight(150)
        preview_layout.addWidget(self.preview_payments_table)

        preview_layout.addWidget(QLabel("<b>المصروفات المرتبطة:</b>"))
        self.preview_expenses_table = QTableWidget()
        self.preview_expenses_table.setColumnCount(3)
        self.preview_expenses_table.setHorizontalHeaderLabels(["التاريخ", "الوصف", "المبلغ"])
        self.preview_expenses_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        preview_layout.addWidget(self.preview_expenses_table)

        main_layout.addWidget(self.preview_groupbox, 1)

        self.load_projects_data()
        self.on_project_selection_changed()

    def create_kpi_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background-color: {color}; border-radius: 8px; }}")
        card_layout = QVBoxLayout(card)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
        value_label = QLabel(value)
        value_label.setStyleSheet("color: white; font-weight: bold; font-size: 16px;")
        obj_name = f"val_{title}"
        value_label.setObjectName(obj_name)
        card.setProperty("value_label_name", obj_name)
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        return card

    def update_card_value(self, card: QFrame, value: float):
        try:
            obj_name = card.property("value_label_name")
            value_label = card.findChild(QLabel, obj_name)
            if value_label:
                value_label.setText(f"{value:,.2f} EGP")
                if "المتبقي" in obj_name and value > 0:
                    card.setStyleSheet("background-color: #ef4444; border-radius: 8px;")
                elif "المتبقي" in obj_name:
                    card.setStyleSheet("background-color: #f59e0b; border-radius: 8px;")
        except Exception as e:
            print(f"ERROR: [ProjectManager] فشل تحديث الكارت: {e}")

    def on_project_selection_changed(self):
        """ (معدلة) تملى لوحة المعاينة بكل التفاصيل """
        selected_rows = self.projects_table.selectedIndexes()
        if selected_rows:
            selected_index = selected_rows[0].row()
            if selected_index < len(self.projects_list):
                self.selected_project = self.projects_list[selected_index]
                self.edit_button.setEnabled(True)
                self.profit_button.setEnabled(True)
                self.payment_button.setEnabled(True)
                self.print_button.setEnabled(True)
                self.preview_template_button.setEnabled(True)  # ✅ تفعيل زرار المعاينة
                self.preview_groupbox.setVisible(True)

                project_name = self.selected_project.name

                # (1. جلب الأرقام الرئيسية)
                profit_data = self.project_service.get_project_profitability(project_name)
                self.update_card_value(self.revenue_card, profit_data.get("total_revenue", 0))
                self.update_card_value(self.paid_card, profit_data.get("total_paid", 0))
                self.update_card_value(self.due_card, profit_data.get("balance_due", 0))

                # (2. جلب الدفعات المرتبطة)
                try:
                    payments = self.project_service.get_payments_for_project(project_name)
                    self.preview_payments_table.setRowCount(0)
                    
                    if payments and len(payments) > 0:
                        for i, pay in enumerate(payments):
                            self.preview_payments_table.insertRow(i)
                            # معالجة التاريخ بأمان
                            try:
                                if hasattr(pay.date, 'strftime'):
                                    date_str = pay.date.strftime("%Y-%m-%d")
                                else:
                                    date_str = str(pay.date)[:10]
                            except:
                                date_str = "N/A"
                            
                            self.preview_payments_table.setItem(i, 0, QTableWidgetItem(date_str))
                            self.preview_payments_table.setItem(i, 1, QTableWidgetItem(f"{pay.amount:,.2f}"))
                            
                            # عرض اسم الحساب بدلاً من ID
                            account_name = str(pay.account_id)
                            try:
                                account = self.accounting_service.repo.get_account_by_code(pay.account_id)
                                if account:
                                    account_name = account.name
                            except:
                                pass
                            
                            self.preview_payments_table.setItem(i, 2, QTableWidgetItem(account_name))
                    else:
                        # إضافة صف يوضح عدم وجود دفعات
                        self.preview_payments_table.insertRow(0)
                        no_data_item = QTableWidgetItem("لا توجد دفعات مسجلة")
                        no_data_item.setForeground(QColor("gray"))
                        self.preview_payments_table.setItem(0, 0, no_data_item)
                        self.preview_payments_table.setSpan(0, 0, 1, 3)
                        
                except Exception as e:
                    print(f"ERROR: [ProjectManager] فشل تحميل الدفعات: {e}")
                    import traceback
                    traceback.print_exc()

                # (3. جلب المصروفات المرتبطة)
                try:
                    expenses = self.project_service.get_expenses_for_project(project_name)
                    self.preview_expenses_table.setRowCount(0)
                    
                    if expenses and len(expenses) > 0:
                        for i, exp in enumerate(expenses):
                            self.preview_expenses_table.insertRow(i)
                            # معالجة التاريخ بأمان
                            try:
                                if hasattr(exp.date, 'strftime'):
                                    date_str = exp.date.strftime("%Y-%m-%d")
                                else:
                                    date_str = str(exp.date)[:10]
                            except:
                                date_str = "N/A"
                            
                            self.preview_expenses_table.setItem(i, 0, QTableWidgetItem(date_str))
                            self.preview_expenses_table.setItem(i, 1, QTableWidgetItem(exp.description or exp.category))
                            self.preview_expenses_table.setItem(i, 2, QTableWidgetItem(f"{exp.amount:,.2f}"))
                    else:
                        # إضافة صف يوضح عدم وجود مصروفات
                        self.preview_expenses_table.insertRow(0)
                        no_data_item = QTableWidgetItem("لا توجد مصروفات مسجلة")
                        no_data_item.setForeground(QColor("gray"))
                        self.preview_expenses_table.setItem(0, 0, no_data_item)
                        self.preview_expenses_table.setSpan(0, 0, 1, 3)
                        
                except Exception as e:
                    print(f"ERROR: [ProjectManager] فشل تحميل المصروفات: {e}")
                    import traceback
                    traceback.print_exc()
                return

        self.selected_project = None
        self.edit_button.setEnabled(False)
        self.profit_button.setEnabled(False)
        self.payment_button.setEnabled(False)
        self.print_button.setEnabled(False)
        self.preview_template_button.setEnabled(False)  # ✅ تعطيل زرار المعاينة
        self.preview_groupbox.setVisible(False)

    def load_projects_data(self):
        print("INFO: [ProjectManager] جاري تحميل بيانات المشاريع...")
        try:
            if self.show_archived_checkbox.isChecked():
                self.projects_list = self.project_service.get_archived_projects()
            else:
                self.projects_list = self.project_service.get_all_projects()

            self.projects_table.setRowCount(0)
            for row, project in enumerate(self.projects_list):
                self.projects_table.insertRow(row)
                self.projects_table.setItem(row, 0, QTableWidgetItem(project.name))
                self.projects_table.setItem(row, 1, QTableWidgetItem(project.client_id))
                self.projects_table.setItem(row, 2, QTableWidgetItem(project.status.value))
                self.projects_table.setItem(row, 3, QTableWidgetItem(self._format_date(project.start_date)))

            self.on_project_selection_changed()
        except Exception as e:
            print(f"ERROR: [ProjectManager] فشل تحميل المشاريع: {e}")

    def _format_date(self, value) -> str:
        if not value:
            return "-"
        if isinstance(value, datetime.datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, datetime.date):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, str):
            try:
                parsed = datetime.datetime.fromisoformat(value)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                return value
        return str(value)

    def open_editor(self, project_to_edit: Optional[schemas.Project] = None):
        """ (معدلة) يفتح نافذة الحوار ويمرر "قسم المحاسبة" """
        dialog = ProjectEditorDialog(
            project_service=self.project_service,
            client_service=self.client_service,
            service_service=self.service_service,
            accounting_service=self.accounting_service,
            project_to_edit=project_to_edit,
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_projects_data()

    def open_editor_for_selected(self):
        if not self.selected_project:
            QMessageBox.information(self, "تنبيه", "الرجاء اختيار مشروع أولاً")
            return
        self.open_editor(self.selected_project)

    def open_payment_dialog(self):
        """فتح نافذة تسجيل دفعة جديدة للمشروع المحدد"""
        if not self.selected_project:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مشروع أولاً.")
            return

        print(f"INFO: [ProjectManager] فتح شاشة تسجيل دفعة لـ: {self.selected_project.name}")

        from ui.payment_dialog import PaymentDialog

        # جلب حسابات البنك/الخزينة فقط (الخزينة والمحافظ الإلكترونية)
        all_accounts = self.accounting_service.repo.get_all_accounts()
        cash_accounts = [
            acc for acc in all_accounts
            if acc.type == schemas.AccountType.CASH or 
               (acc.code and acc.code.startswith("111")) or  # الخزينة 111x
               (acc.code and acc.code.startswith("12"))      # المحافظ الإلكترونية 12xx
        ]

        if not cash_accounts:
            QMessageBox.critical(
                self, 
                "خطأ إعداد", 
                "لم يتم العثور على حسابات بنك أو خزينة.\n\n"
                "يرجى إضافة حسابات نقدية (كود يبدأ بـ 11 أو 12) أولاً."
            )
            return

        dialog = PaymentDialog(
            project=self.selected_project,
            accounts=cash_accounts,
            project_service=self.project_service,
            parent=self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            print("INFO: [ProjectManager] تم تسجيل الدفعة بنجاح. جاري تحديث البيانات...")
            self.on_project_selection_changed()  # تحديث لوحة المعاينة

    def open_profit_dialog(self):
        """
        عرض تقرير ربحية المشروع بالتفصيل (إيرادات، مصروفات، صافي الربح)
        """
        if not self.selected_project:
            QMessageBox.warning(self, "خطأ", "يرجى تحديد مشروع أولاً.")
            return

        print(f"INFO: [ProjectManager] فتح تقرير ربحية المشروع: {self.selected_project.name}")

        from ui.project_profit_dialog import ProjectProfitDialog

        dialog = ProjectProfitDialog(
            project=self.selected_project,
            project_service=self.project_service,
            parent=self
        )
        dialog.exec()
    
    def print_invoice(self):
        """طباعة فاتورة المشروع المحدد"""
        if not self.selected_project:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مشروع أولاً")
            return
        
        try:
            # جلب معلومات العميل
            client = self.client_service.get_client_by_id(self.selected_project.client_id)
            if not client:
                QMessageBox.warning(self, "خطأ", "لم يتم العثور على معلومات العميل")
                return
            
            client_info = {
                "name": client.name,
                "phone": client.phone or "",
                "address": client.address or "",
                "email": getattr(client, 'email', '') or ""
            }
            
            # جلب الدفعات مع اسم الحساب
            payments_data = []
            try:
                payments = self.project_service.get_payments_for_project(self.selected_project.name)
                for payment in payments:
                    account_name = "نقدي"
                    try:
                        account = self.accounting_service.repo.get_account_by_code(payment.account_id)
                        if account:
                            account_name = account.name
                    except:
                        pass
                    payments_data.append({
                        'date': payment.date,
                        'amount': payment.amount,
                        'method': account_name,
                        'account_name': account_name
                    })
            except Exception as e:
                print(f"WARNING: فشل في جلب الدفعات: {e}")

            # إنشاء PDF باستخدام PrintingService
            if self.printing_service:
                print("INFO: [ProjectManager] Using template service for printing")
                pdf_path = self.printing_service.print_project_invoice(
                    project=self.selected_project,
                    client_info=client_info,
                    payments=payments_data,
                    auto_open=True
                )
                
                if pdf_path and os.path.exists(pdf_path):
                    # تحقق من نوع الملف
                    if pdf_path.endswith('.pdf'):
                        QMessageBox.information(
                            self,
                            "✅ تم إنشاء الفاتورة",
                            f"تم إنشاء فاتورة PDF بنجاح!\n\n📄 {os.path.basename(pdf_path)}"
                        )
                    else:
                        # تم حفظ HTML بدلاً من PDF
                        QMessageBox.warning(
                            self,
                            "⚠️ تم حفظ HTML",
                            f"تم حفظ الفاتورة كملف HTML.\n\n"
                            f"📄 {os.path.basename(pdf_path)}\n\n"
                            f"💡 لإنشاء PDF، قم بتثبيت:\n"
                            f"   • wkhtmltopdf أو\n"
                            f"   • Google Chrome/Edge"
                        )
                else:
                    QMessageBox.critical(self, "خطأ", "فشل في إنشاء الفاتورة")
            else:
                QMessageBox.warning(self, "خطأ", "خدمة الطباعة غير متوفرة")
                
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في طباعة الفاتورة:\n{str(e)}")
            import traceback
            traceback.print_exc()


    

    def preview_invoice_template(self):
        """معاينة قالب الفاتورة للمشروع المحدد"""
        if not self.selected_project:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مشروع أولاً")
            return
        
        if not self.template_service:
            QMessageBox.warning(self, "خطأ", "خدمة القوالب غير متوفرة")
            return
        
        try:
            # جلب معلومات العميل
            client = self.client_service.get_client_by_id(self.selected_project.client_id)
            if not client:
                QMessageBox.warning(self, "خطأ", "لم يتم العثور على معلومات العميل")
                return
            
            # تحضير معلومات العميل
            client_info = {
                'name': client.name,
                'phone': client.phone or '',
                'email': client.email or '',
                'address': client.address or ''
            }
            
            # جلب الدفعات مع اسم الحساب
            payments = []
            try:
                # استخدام اسم المشروع بدلاً من ID
                project_payments = self.project_service.get_payments_for_project(self.selected_project.name)
                print(f"INFO: [ProjectManager] تم جلب {len(project_payments)} دفعة للمشروع: {self.selected_project.name}")
                for payment in project_payments:
                    # جلب اسم الحساب
                    account_name = "نقدي"
                    try:
                        account = self.accounting_service.repo.get_account_by_code(payment.account_id)
                        if account:
                            account_name = account.name
                    except:
                        pass
                    payments.append({
                        'date': payment.date,
                        'amount': payment.amount,
                        'method': account_name,
                        'account_name': account_name
                    })
                    print(f"  - دفعة: تاريخ={payment.date}, مبلغ={payment.amount}, حساب={account_name}")
            except Exception as e:
                print(f"WARNING: فشل في جلب الدفعات: {e}")
            
            print(f"INFO: [ProjectManager] إرسال {len(payments)} دفعة للمعاينة")
            
            # معاينة القالب
            success = self.template_service.preview_template(
                self.selected_project, client_info, payments=payments
            )
            
            if not success:
                QMessageBox.warning(self, "خطأ", "فشل في معاينة قالب الفاتورة")
        
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء معاينة القالب:\n{str(e)}")

    # WhatsApp function removed - feature disabled