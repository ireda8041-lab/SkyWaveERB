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
from ui.styles import BUTTON_STYLES, TABLE_STYLE, GROUPBOX_STYLE, COLORS, TABLE_STYLE_DARK, create_centered_item
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
        
        self.setMinimumWidth(750)
        self.setMinimumHeight(500)
        
        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)
        
        # تصغير العناصر وإزالة الإطار البرتقالي
        self.setStyleSheet("""
            * {
                outline: none;
                font-size: 11px;
            }
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                padding: 18px 8px 8px 8px;
                margin-top: 8px;
                border: 1px solid #374151;
                border-radius: 6px;
                background: rgba(10, 42, 85, 0.2);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 2px 15px;
                margin-top: 2px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 transparent,
                    stop:0.1 rgba(10, 108, 241, 0.3),
                    stop:0.5 rgba(10, 108, 241, 0.5),
                    stop:0.9 rgba(10, 108, 241, 0.3),
                    stop:1 transparent);
                border-radius: 3px;
                color: #93C5FD;
            }
            QLabel {
                font-size: 11px;
            }
            QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
                font-size: 11px;
                padding: 3px 5px;
                min-height: 22px;
                max-height: 24px;
            }
            QTextEdit {
                font-size: 11px;
            }
            QPushButton {
                font-size: 11px;
                padding: 5px 10px;
                min-height: 24px;
            }
            QTableWidget {
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 2px;
            }
            QHeaderView::section {
                font-size: 10px;
                padding: 3px;
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
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # === التخطيط الأفقي الرئيسي: اليسار واليمين ===
        main_horizontal_layout = QHBoxLayout()
        main_horizontal_layout.setSpacing(8)
        
        # === الجانب الأيسر: البيانات الأساسية + بنود المشروع + الإجماليات ===
        left_side = QVBoxLayout()
        left_side.setSpacing(6)
        
        # --- 1. البيانات الأساسية ---
        basic_group = QGroupBox("البيانات الأساسية للمشروع")
        basic_layout = QVBoxLayout()  # استخدام VBoxLayout بدل FormLayout
        basic_layout.setSpacing(4)
        basic_layout.setContentsMargins(6, 12, 6, 6)

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
        items_layout.setSpacing(4)
        items_layout.setContentsMargins(6, 12, 6, 6)
        add_item_layout = QHBoxLayout()
        add_item_layout.setSpacing(4)
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
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # عمود البند (يتمدد)
        
        # تحديد عرض ثابت للأعمدة الرقمية - مصغر
        self.items_table.setColumnWidth(1, 60)   # الكمية
        self.items_table.setColumnWidth(2, 75)   # السعر
        self.items_table.setColumnWidth(3, 55)   # الخصم
        self.items_table.setColumnWidth(4, 85)   # الإجمالي
        self.items_table.setColumnWidth(5, 35)   # الحذف
        
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        
        # ستايل الجدول
        self.items_table.setStyleSheet(TABLE_STYLE_DARK)
        
        self.items_table.setMinimumHeight(140)
        self.items_table.verticalHeader().setDefaultSectionSize(28)  # ارتفاع الصفوف أصغر
        self.items_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.items_table.verticalHeader().setVisible(True)
        self.items_table.setShowGrid(True)
        items_layout.addWidget(self.items_table)
        items_group.setLayout(items_layout)
        left_side.addWidget(items_group)
        
        # --- 3. الإجماليات ---
        totals_group = QGroupBox("الإجماليات")
        totals_form = QFormLayout()
        totals_form.setSpacing(4)
        totals_form.setContentsMargins(6, 12, 6, 6)
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
        self.total_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
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
        right_side.setSpacing(8)
        
        # الشروط والملاحظات - تصميم احترافي
        notes_group = QGroupBox("الشروط والملاحظات")
        notes_layout = QVBoxLayout()
        notes_layout.setContentsMargins(8, 8, 8, 8)
        notes_layout.setSpacing(6)
        
        # شريط أدوات
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(4)
        
        reset_btn = QPushButton("إعادة القالب")
        reset_btn.setFixedHeight(20)
        reset_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.2);
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 3px;
                color: #FCA5A5;
                font-size: 9px;
                padding: 2px 8px;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 0.4); }
        """)
        reset_btn.clicked.connect(self._reset_notes_template)
        
        clear_btn = QPushButton("مسح الكل")
        clear_btn.setFixedHeight(20)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(107, 114, 128, 0.2);
                border: 1px solid rgba(107, 114, 128, 0.4);
                border-radius: 3px;
                color: #9CA3AF;
                font-size: 9px;
                padding: 2px 8px;
            }
            QPushButton:hover { background: rgba(107, 114, 128, 0.4); }
        """)
        clear_btn.clicked.connect(lambda: self.notes_input.clear())
        
        toolbar_layout.addWidget(reset_btn)
        toolbar_layout.addWidget(clear_btn)
        toolbar_layout.addStretch()
        
        notes_layout.addLayout(toolbar_layout)
        
        self.notes_input = QTextEdit()
        self.notes_input.setStyleSheet("""
            QTextEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(10, 42, 85, 0.5),
                    stop:1 rgba(5, 32, 69, 0.7));
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px;
                color: #F8FAFC;
                font-size: 11px;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: 1px solid #0A6CF1;
            }
        """)
        self.notes_input.setMinimumHeight(140)
        
        # تعيين القالب الافتراضي للمشاريع الجديدة
        if not self.is_editing:
            self._reset_notes_template()
        
        notes_layout.addWidget(self.notes_input, 1)
        
        notes_group.setLayout(notes_layout)
        right_side.addWidget(notes_group, 1)

        # الدفعة المقدمة - تصميم احترافي
        payment_group = QGroupBox("💳 تسجيل دفعة مقدمة")
        payment_group.setStyleSheet("""
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #374151;
                border-radius: 6px;
                margin-top: 14px;
                padding: 12px 8px 8px 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(16, 185, 129, 0.1),
                    stop:1 rgba(5, 32, 69, 0.5));
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 2px 12px;
                color: #10B981;
            }
        """)
        payment_layout = QVBoxLayout()
        payment_layout.setContentsMargins(8, 15, 8, 8)
        payment_layout.setSpacing(8)
        
        # المبلغ
        amount_row = QHBoxLayout()
        amount_label = QLabel("💰 المبلغ:")
        amount_label.setFixedWidth(70)
        self.payment_amount_input = CustomSpinBox(decimals=2, minimum=0, maximum=9999999)
        self.payment_amount_input.setValue(0.0)
        self.payment_amount_input.setSuffix(" EGP")
        amount_row.addWidget(amount_label)
        amount_row.addWidget(self.payment_amount_input, 1)
        payment_layout.addLayout(amount_row)
        
        # التاريخ
        date_row = QHBoxLayout()
        date_label = QLabel("📅 التاريخ:")
        date_label.setFixedWidth(70)
        self.payment_date_input = QDateEdit(QDate.currentDate())
        self.payment_date_input.setCalendarPopup(True)
        date_row.addWidget(date_label)
        date_row.addWidget(self.payment_date_input, 1)
        payment_layout.addLayout(date_row)
        
        # الحساب
        account_row = QHBoxLayout()
        account_label = QLabel("🏦 الحساب:")
        account_label.setFixedWidth(70)
        self.payment_account_combo = SimpleComboBox()
        self.payment_account_combo.addItem("اختر الحساب...", userData=None)
        for acc in self.cash_accounts:
            display_text = f"{acc.name} ({acc.code})"
            self.payment_account_combo.addItem(display_text, userData=acc)
        
        account_names = [acc.name for acc in self.cash_accounts]
        self.payment_account_combo.setup_completer(account_names)
        self._auto_select_default_treasury()
        account_row.addWidget(account_label)
        account_row.addWidget(self.payment_account_combo, 1)
        payment_layout.addLayout(account_row)
        
        payment_group.setLayout(payment_layout)
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
        self.save_button.setFixedHeight(28)
        self.save_button.clicked.connect(self.save_project)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.setContentsMargins(0, 5, 0, 5)
        main_layout.addLayout(buttons_layout)

        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.on_service_selected(0)

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

        if self.is_editing:
            self.load_project_data()
            payment_group.setVisible(False)
    
    def _reset_notes_template(self):
        """إعادة تعيين القالب الافتراضي للملاحظات"""
        default_template = """• مدة التنفيذ: ___ يوم عمل.
• تبدأ المدة من تاريخ استلام الداتا.
• التسليم حسب الجدول الزمني المتفق عليه.
• لا تشمل المدة أيام المراجعة والتعديلات.

• الدفعة المقدمة: 50% عند التعاقد.
• الدفعة الثانية: 25% عند التسليم الأولي.
• الدفعة النهائية: 25% عند التسليم النهائي.

• يبدأ التنفيذ بعد استلام الدفعة الأولى واعتماد المحتوى/التفاصيل المطلوبة.
• أي طلبات إضافية خارج نطاق العمل المتفق عليه يتم تسعيرها بشكل مستقل.
• تم تطبيق خصم ......... ج على الفاتورة."""
        self.notes_input.setText(default_template)
    
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
        except (TypeError, RuntimeError):
            # الإشارة غير متصلة بالفعل
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
                
                # ✅ البحث عن الخدمة الجديدة بالاسم (أكثر أماناً)
                new_service = None
                for service in self.services_list:
                    if service.name.lower() == service_name.lower():
                        new_service = service
                        break
                
                # ✅ إذا لم نجد الخدمة، نستخدم آخر خدمة (مع التحقق من القائمة)
                if not new_service and self.services_list:
                    new_service = self.services_list[-1]
                
                if new_service:
                    self.service_combo.addItem(f"{new_service.name} ({new_service.default_price})", userData=new_service)
                    self.service_combo.setCurrentText(new_service.name)
                    QMessageBox.information(self, "نجح", f"تم إضافة الخدمة '{new_service.name}' بنجاح!")
                    return new_service
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في العثور على الخدمة المضافة")
                    return None
        
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

        # جعل التاب متجاوب مع حجم الشاشة
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals
        app_signals.projects_changed.connect(self._on_projects_changed)
        app_signals.payments_changed.connect(self._on_projects_changed)


        # --- 1. الجزء الأيسر (الجدول والأزرار) ---
        left_panel = QVBoxLayout()
        buttons_layout = QHBoxLayout()
        
        self.add_button = QPushButton("➕ إضافة مشروع جديد")
        self.add_button.setStyleSheet(BUTTON_STYLES["success"])
        self.add_button.setFixedHeight(28)
        self.add_button.clicked.connect(lambda: self.open_editor(project_to_edit=None))

        self.edit_button = QPushButton("✏️ تعديل المشروع")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.open_editor_for_selected)
        self.edit_button.setEnabled(False)

        # زرار تسجيل دفعة جديدة
        self.payment_button = QPushButton("💰 تسجيل دفعة")
        self.payment_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.payment_button.setFixedHeight(28)
        self.payment_button.clicked.connect(self.open_payment_dialog)
        self.payment_button.setEnabled(False)

        # زرار عرض الربحية
        self.profit_button = QPushButton("📊 الربحية")
        self.profit_button.setStyleSheet(BUTTON_STYLES["info"])
        self.profit_button.setFixedHeight(28)
        self.profit_button.clicked.connect(self.open_profit_dialog)
        self.profit_button.setEnabled(False)

        # زرار طباعة الفاتورة
        self.print_button = QPushButton("🖨️ طباعة")
        self.print_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.print_button.setFixedHeight(28)
        self.print_button.clicked.connect(self.print_invoice)
        self.print_button.setEnabled(False)

        # WhatsApp button removed - feature disabled

        # أزرار قوالب الفواتير
        
        self.preview_template_button = QPushButton("👁️ معاينة الفاتورة")
        self.preview_template_button.setStyleSheet(BUTTON_STYLES["info"])
        self.preview_template_button.setFixedHeight(28)
        self.preview_template_button.clicked.connect(self.preview_invoice_template)
        self.preview_template_button.setEnabled(False)

        # زرار التحديث
        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.setFixedHeight(28)
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
        self.projects_table.setColumnCount(5)
        self.projects_table.setHorizontalHeaderLabels(["رقم الفاتورة", "اسم المشروع", "العميل", "الحالة", "تاريخ البدء"])
        
        # ⚡ تفعيل الترتيب بالضغط على رأس العمود
        self.projects_table.setSortingEnabled(True)
        
        self.search_bar = UniversalSearchBar(
            self.projects_table,
            placeholder="🔍 بحث (رقم الفاتورة، اسم المشروع، العميل، الحالة، التاريخ)..."
        )
        table_layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===
        
        self.projects_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.projects_table)
        self.projects_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.projects_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.projects_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        # تخصيص عرض الأعمدة: الأعمدة النصية تتمدد، الأعمدة الصغيرة بحجم محتواها
        header = self.projects_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # رقم الفاتورة
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # اسم المشروع - يتمدد
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # العميل - يتمدد
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # تاريخ البدء
        self.projects_table.verticalHeader().setDefaultSectionSize(32)
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.itemSelectionChanged.connect(self.on_project_selection_changed)
        self.projects_table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        

        # إضافة دبل كليك للتعديل
        self.projects_table.itemDoubleClicked.connect(self.open_editor_for_selected)
        
        # إضافة قائمة السياق (كليك يمين)
        self._setup_context_menu()
        
        table_layout.addWidget(self.projects_table)
        left_panel.addWidget(table_groupbox, 1)
        main_layout.addLayout(left_panel, 3)

        # --- 2. لوحة معاينة ربحية المشروع (تصميم احترافي) ---
        self.preview_groupbox = QGroupBox()
        self.preview_groupbox.setMinimumWidth(340)
        self.preview_groupbox.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.preview_groupbox.setStyleSheet(f"""
            QGroupBox {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(10, 42, 85, 0.95),
                    stop:1 rgba(5, 32, 69, 0.98));
                border: 1px solid rgba(10, 108, 241, 0.3);
                border-radius: 10px;
                margin: 0px;
                padding: 0px;
            }}
        """)
        preview_layout = QVBoxLayout()
        preview_layout.setSpacing(6)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        self.preview_groupbox.setLayout(preview_layout)

        # === عنوان اللوحة (بسيط) ===
        header_title = QLabel("📊 معاينة ربحية المشروع")
        header_title.setStyleSheet("color: #93C5FD; font-size: 12px; font-weight: bold; background: transparent; padding: 2px 0;")
        header_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        preview_layout.addWidget(header_title)

        # === كروت KPI ===
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(6)
        self.revenue_card = self.create_kpi_card("💰 إجمالي العقد", "0.00", "#0A6CF1")
        self.paid_card = self.create_kpi_card("✅ المدفوع", "0.00", "#10b981")
        self.due_card = self.create_kpi_card("⏳ المتبقي", "0.00", "#ef4444")
        kpi_layout.addWidget(self.revenue_card)
        kpi_layout.addWidget(self.paid_card)
        kpi_layout.addWidget(self.due_card)
        preview_layout.addLayout(kpi_layout)

        # === قسم الدفعات المسجلة ===
        payments_section = self._create_preview_section(
            "💳 الدفعات المسجلة",
            ["الحساب", "المبلغ", "التاريخ"],
            [QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.ResizeToContents]
        )
        self.preview_payments_table = payments_section["table"]
        preview_layout.addWidget(payments_section["frame"])

        # === قسم المصروفات المرتبطة ===
        expenses_section = self._create_preview_section(
            "💸 المصروفات المرتبطة",
            ["المبلغ", "الوصف", "التاريخ"],
            [QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.ResizeToContents]
        )
        self.preview_expenses_table = expenses_section["table"]
        preview_layout.addWidget(expenses_section["frame"])

        # === قسم المهام المرتبطة ===
        tasks_section = self._create_preview_section(
            "📋 المهام المرتبطة",
            ["المهمة", "الأولوية", "الحالة", "الاستحقاق"],
            [QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.ResizeToContents],
            show_add_btn=True
        )
        self.preview_tasks_table = tasks_section["table"]
        self.add_task_btn = tasks_section.get("add_btn")
        if self.add_task_btn:
            self.add_task_btn.clicked.connect(self._on_add_task_for_project)
        preview_layout.addWidget(tasks_section["frame"])

        # إضافة مساحة مرنة في النهاية
        preview_layout.addStretch()

        main_layout.addWidget(self.preview_groupbox, 1)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_projects_data() - يتم استدعاؤها من MainWindow
        self.on_project_selection_changed()

    def create_kpi_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background-color: {color}; border-radius: 6px; }}")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 9px; background: transparent;")
        value_label = QLabel(value)
        value_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px; background: transparent;")
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
                    card.setStyleSheet("QFrame { background-color: #ef4444; border-radius: 6px; }")
                elif "المتبقي" in obj_name:
                    card.setStyleSheet("QFrame { background-color: #10b981; border-radius: 6px; }")
        except Exception as e:
            print(f"ERROR: [ProjectManager] فشل تحديث الكارت: {e}")

    def _create_preview_section(self, title: str, headers: list, resize_modes: list, show_add_btn: bool = False) -> dict:
        """إنشاء قسم معاينة بسيط مع جدول"""
        # Container بدون فريم
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # شريط العنوان بسيط
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # زر الإضافة (إذا مطلوب)
        add_btn = None
        if show_add_btn:
            add_btn = QPushButton("+ مهمة")
            add_btn.setFixedSize(70, 22)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setStyleSheet("""
                QPushButton {
                    background: #8B2CF5;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                    min-width: 70px;
                    max-width: 70px;
                    min-height: 22px;
                    max-height: 22px;
                }
                QPushButton:hover { background: #9333ea; }
                QPushButton:pressed { background: #7c3aed; }
            """)
            header_layout.addWidget(add_btn)
        
        header_layout.addStretch()
        
        # عنوان بسيط بدون فريم
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #93C5FD; font-size: 11px; font-weight: bold; background: transparent;")
        header_layout.addWidget(title_label)
        layout.addLayout(header_layout)

        # الجدول
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['bg_dark']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                gridline-color: {COLORS['border']};
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 3px 5px;
                border-bottom: 1px solid rgba(30, 58, 95, 0.3);
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['primary']};
            }}
            QHeaderView::section {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['header_bg']}, stop:1 #1d4ed8);
                color: white;
                padding: 5px;
                border: none;
                border-right: 1px solid rgba(255,255,255,0.15);
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        from ui.styles import fix_table_rtl
        fix_table_rtl(table)
        
        # تطبيق أوضاع تغيير حجم الأعمدة
        header = table.horizontalHeader()
        for i, mode in enumerate(resize_modes):
            header.setSectionResizeMode(i, mode)
        
        table.verticalHeader().setDefaultSectionSize(30)
        table.verticalHeader().setVisible(False)
        table.setMinimumHeight(120)
        table.setMaximumHeight(180)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(table)

        result = {"frame": container, "table": table}
        if add_btn:
            result["add_btn"] = add_btn
        return result

    def _setup_context_menu(self):
        """إعداد قائمة السياق (كليك يمين) للجدول"""
        from core.context_menu import ContextMenuManager
        
        # إجراءات مخصصة للمشاريع
        custom_actions = [
            ("إضافة دفعة", "💰", self._add_payment_for_selected, True),
            ("عرض الربحية", "📊", self._show_profit_dialog, True),
            ("طباعة الفاتورة", "🖨️", self._print_invoice, True),
        ]
        
        ContextMenuManager.setup_table_context_menu(
            table=self.projects_table,
            on_view=self.open_editor_for_selected,
            on_edit=self.open_editor_for_selected,
            on_refresh=self.load_projects_data,
            custom_actions=custom_actions
        )
    
    def _add_payment_for_selected(self):
        """إضافة دفعة للمشروع المحدد"""
        selected = self.projects_table.selectedIndexes()
        if selected:
            self.open_editor_for_selected()
    
    def _show_profit_dialog(self):
        """عرض نافذة ربحية المشروع"""
        selected = self.projects_table.selectedIndexes()
        if selected:
            row = selected[0].row()
            project_name = self.projects_table.item(row, 1).text()
            project = self.project_service.get_project_by_name(project_name)
            if project:
                from ui.project_profit_dialog import ProjectProfitDialog
                dialog = ProjectProfitDialog(project, self.project_service, self)
                dialog.exec()
    
    def _print_invoice(self):
        """طباعة فاتورة المشروع"""
        selected = self.projects_table.selectedIndexes()
        if selected:
            row = selected[0].row()
            project_name = self.projects_table.item(row, 1).text()
            project = self.project_service.get_project_by_name(project_name)
            if project and hasattr(self, 'printing_service') and self.printing_service:
                self.printing_service.print_invoice(project)

    def on_project_selection_changed(self):
        """ (معدلة) تملى لوحة المعاينة بكل التفاصيل """
        selected_rows = self.projects_table.selectedIndexes()
        if selected_rows:
            selected_row = selected_rows[0].row()
            
            # ⚡ جلب اسم المشروع من الجدول مباشرة (يعمل مع الترتيب)
            project_name_item = self.projects_table.item(selected_row, 1)  # عمود اسم المشروع
            if not project_name_item:
                return
            
            project_name = project_name_item.text()
            
            # البحث عن المشروع في القائمة بالاسم
            self.selected_project = None
            for proj in self.projects_list:
                if proj.name == project_name:
                    self.selected_project = proj
                    break
            
            if not self.selected_project:
                return
                
            self.edit_button.setEnabled(True)
            self.profit_button.setEnabled(True)
            self.payment_button.setEnabled(True)
            self.print_button.setEnabled(True)
            self.preview_template_button.setEnabled(True)  # ✅ تفعيل زرار المعاينة
            self.preview_groupbox.setVisible(True)
            
            # حفظ ID المشروع للمهام
            project_id_for_tasks = getattr(self.selected_project, 'id', None) or getattr(self.selected_project, '_mongo_id', project_name)
            
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
                        except (AttributeError, ValueError, TypeError):
                            date_str = "N/A"
                        
                        # عرض اسم الحساب بدلاً من ID
                        account_name = "نقدي"  # افتراضي
                        try:
                            account = self.accounting_service.repo.get_account_by_code(pay.account_id)
                            if account:
                                account_name = account.name
                            else:
                                account = self.accounting_service.repo.get_account_by_id(pay.account_id)
                                if account:
                                    account_name = account.name
                                else:
                                    account_name = str(pay.account_id)
                        except Exception as acc_err:
                            print(f"WARNING: فشل جلب اسم الحساب: {acc_err}")
                            account_name = str(pay.account_id)
                        
                        # ترتيب الأعمدة: [الحساب, المبلغ, التاريخ]
                        self.preview_payments_table.setItem(i, 0, QTableWidgetItem(account_name))
                        self.preview_payments_table.setItem(i, 1, QTableWidgetItem(f"{pay.amount:,.2f}"))
                        self.preview_payments_table.setItem(i, 2, QTableWidgetItem(date_str))
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
                        except (AttributeError, ValueError, TypeError):
                            date_str = "N/A"
                        
                        # ترتيب الأعمدة: [المبلغ, الوصف, التاريخ]
                        self.preview_expenses_table.setItem(i, 0, QTableWidgetItem(f"{exp.amount:,.2f}"))
                        self.preview_expenses_table.setItem(i, 1, QTableWidgetItem(exp.description or exp.category))
                        self.preview_expenses_table.setItem(i, 2, QTableWidgetItem(date_str))
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
            
            # (4. جلب المهام المرتبطة بالمشروع)
            try:
                self._load_project_tasks(project_id_for_tasks)
            except Exception as e:
                print(f"ERROR: [ProjectManager] فشل تحميل المهام: {e}")
            
            return

        self.selected_project = None
        self.edit_button.setEnabled(False)
        self.profit_button.setEnabled(False)
        self.payment_button.setEnabled(False)
        self.print_button.setEnabled(False)
        self.preview_template_button.setEnabled(False)  # ✅ تعطيل زرار المعاينة
        self.preview_groupbox.setVisible(False)

    def load_projects_data(self):
        """⚡ تحميل بيانات المشاريع في الخلفية لمنع التجميد"""
        print("INFO: [ProjectManager] جاري تحميل بيانات المشاريع...")
        
        from core.data_loader import get_data_loader
        from PyQt6.QtWidgets import QApplication
        
        # تحضير الجدول
        self.projects_table.setSortingEnabled(False)
        self.projects_table.setUpdatesEnabled(False)
        self.projects_table.blockSignals(True)
        self.projects_table.setRowCount(0)
        QApplication.processEvents()
        
        # دالة جلب البيانات (تعمل في الخلفية)
        def fetch_projects():
            try:
                if self.show_archived_checkbox.isChecked():
                    return self.project_service.get_archived_projects()
                else:
                    return self.project_service.get_all_projects()
            except Exception as e:
                print(f"ERROR: [ProjectManager] فشل جلب المشاريع: {e}")
                return []
        
        # دالة تحديث الواجهة (تعمل على main thread)
        def on_data_loaded(projects):
            try:
                self.projects_list = projects
                
                # إنشاء العناصر مع محاذاة للوسط
                def create_centered_item(text):
                    item = QTableWidgetItem(str(text) if text else "")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    return item
                
                # تحميل البيانات على دفعات
                batch_size = 15
                for row, project in enumerate(self.projects_list):
                    self.projects_table.insertRow(row)
                    
                    # ⚡ جلب رقم الفاتورة مباشرة من المشروع
                    invoice_number = getattr(project, 'invoice_number', None) or ""
                    
                    self.projects_table.setItem(row, 0, create_centered_item(invoice_number))
                    self.projects_table.setItem(row, 1, create_centered_item(project.name))
                    self.projects_table.setItem(row, 2, create_centered_item(project.client_id))
                    self.projects_table.setItem(row, 3, create_centered_item(project.status.value))
                    self.projects_table.setItem(row, 4, create_centered_item(self._format_date(project.start_date)))
                    
                    # معالجة الأحداث كل batch_size صف
                    if (row + 1) % batch_size == 0:
                        QApplication.processEvents()
                
                # إعادة تفعيل الجدول
                self.projects_table.blockSignals(False)
                self.projects_table.setUpdatesEnabled(True)
                self.projects_table.setSortingEnabled(True)
                QApplication.processEvents()
                
                self.on_project_selection_changed()
                print(f"INFO: [ProjectManager] ✅ تم تحميل {len(projects)} مشروع")
                
            except Exception as e:
                print(f"ERROR: [ProjectManager] فشل تحديث الجدول: {e}")
                import traceback
                traceback.print_exc()
                # إعادة تفعيل الجدول حتى في حالة الخطأ
                self.projects_table.blockSignals(False)
                self.projects_table.setUpdatesEnabled(True)
                self.projects_table.setSortingEnabled(True)
        
        def on_error(error_msg):
            print(f"ERROR: [ProjectManager] فشل تحميل المشاريع: {error_msg}")
            self.projects_table.blockSignals(False)
            self.projects_table.setUpdatesEnabled(True)
            self.projects_table.setSortingEnabled(True)
        
        # تحميل البيانات في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="projects_list",
            load_function=fetch_projects,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True
        )

    def _on_projects_changed(self):
        """⚡ استجابة لإشارة تحديث المشاريع - تحديث الجدول أوتوماتيك"""
        print("INFO: [ProjectManager] ⚡ استلام إشارة تحديث المشاريع - جاري التحديث...")
        self.load_projects_data()

    def _load_project_tasks(self, project_id: str):
        """تحميل المهام المرتبطة بالمشروع"""
        try:
            from ui.todo_manager import TaskService
            task_service = TaskService()
            tasks = task_service.get_tasks_by_project(str(project_id))
            
            self.preview_tasks_table.setRowCount(0)
            
            if tasks and len(tasks) > 0:
                for i, task in enumerate(tasks):
                    self.preview_tasks_table.insertRow(i)
                    
                    # عنوان المهمة
                    self.preview_tasks_table.setItem(i, 0, QTableWidgetItem(task.title))
                    
                    # الأولوية
                    priority_item = QTableWidgetItem(task.priority.value)
                    priority_colors = {
                        "منخفضة": QColor("#10B981"),
                        "متوسطة": QColor("#0A6CF1"),
                        "عالية": QColor("#FF6636"),
                        "عاجلة": QColor("#FF4FD8")
                    }
                    priority_item.setForeground(priority_colors.get(task.priority.value, QColor("white")))
                    self.preview_tasks_table.setItem(i, 1, priority_item)
                    
                    # الحالة
                    status_item = QTableWidgetItem(task.status.value)
                    status_colors = {
                        "قيد الانتظار": QColor("#B0C4DE"),
                        "قيد التنفيذ": QColor("#FF6636"),
                        "مكتملة": QColor("#10B981"),
                        "ملغاة": QColor("#FF4FD8")
                    }
                    status_item.setForeground(status_colors.get(task.status.value, QColor("white")))
                    self.preview_tasks_table.setItem(i, 2, status_item)
                    
                    # تاريخ الاستحقاق
                    due_str = task.due_date.strftime("%Y-%m-%d") if task.due_date else "-"
                    self.preview_tasks_table.setItem(i, 3, QTableWidgetItem(due_str))
            else:
                self.preview_tasks_table.insertRow(0)
                no_data_item = QTableWidgetItem("لا توجد مهام مرتبطة")
                no_data_item.setForeground(QColor("gray"))
                self.preview_tasks_table.setItem(0, 0, no_data_item)
                self.preview_tasks_table.setSpan(0, 0, 1, 4)
                
        except Exception as e:
            print(f"ERROR: [ProjectManager] فشل تحميل المهام: {e}")
            self.preview_tasks_table.setRowCount(0)
            self.preview_tasks_table.insertRow(0)
            no_data_item = QTableWidgetItem("فشل تحميل المهام")
            no_data_item.setForeground(QColor("red"))
            self.preview_tasks_table.setItem(0, 0, no_data_item)
            self.preview_tasks_table.setSpan(0, 0, 1, 4)

    def _on_add_task_for_project(self):
        """إضافة مهمة جديدة مرتبطة بالمشروع المحدد"""
        if not self.selected_project:
            QMessageBox.information(self, "تنبيه", "الرجاء اختيار مشروع أولاً")
            return
        
        try:
            from ui.todo_manager import TaskEditorDialog, TaskService, Task
            
            # إنشاء مهمة جديدة مع ربطها بالمشروع
            project_id = getattr(self.selected_project, 'id', None) or getattr(self.selected_project, '_mongo_id', self.selected_project.name)
            
            dialog = TaskEditorDialog(
                parent=self,
                project_service=self.project_service,
                client_service=self.client_service
            )
            
            # تحديد المشروع مسبقاً
            for i in range(dialog.project_combo.count()):
                if dialog.project_combo.itemData(i) == str(project_id):
                    dialog.project_combo.setCurrentIndex(i)
                    break
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                task = dialog.get_task()
                if task:
                    task_service = TaskService()
                    task_service.add_task(task)
                    # تحديث جدول المهام
                    self._load_project_tasks(str(project_id))
                    print(f"INFO: [ProjectManager] تم إضافة مهمة للمشروع: {task.title}")
                    
        except Exception as e:
            print(f"ERROR: [ProjectManager] فشل إضافة مهمة: {e}")
            QMessageBox.warning(self, "خطأ", f"فشل إضافة المهمة: {str(e)}")

    def _format_date(self, value) -> str:
        if not value:
            return "-"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, str):
            try:
                # محاولة تحليل التاريخ من النص
                if 'T' in value:
                    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                else:
                    parsed = datetime.strptime(value[:10], "%Y-%m-%d")
                return parsed.strftime("%Y-%m-%d")
            except (ValueError, TypeError, AttributeError):
                return value[:10] if len(value) >= 10 else value
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
        """🖨️ طباعة فاتورة المشروع المحدد"""
        if not self.selected_project:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مشروع أولاً")
            return
        
        try:
            project = self.selected_project
            
            # جلب بيانات العميل
            client = self.client_service.get_client_by_id(project.client_id)
            if not client:
                QMessageBox.warning(self, "خطأ", "لم يتم العثور على معلومات العميل")
                return
            
            # جلب الدفعات
            payments_list = self._get_payments_list(project.name)
            print(f"INFO: [ProjectManager] الدفعات المرسلة للطباعة: {payments_list}")
            
            # تجهيز معلومات العميل
            client_info = {
                'name': client.name,
                'company_name': getattr(client, 'company_name', '') or '',
                'phone': client.phone or "---",
                'email': client.email or "",
                'address': client.address or "---"
            }
            
            # ⚡ استخدام template_service
            if self.template_service:
                print("INFO: [ProjectManager] استخدام template_service للطباعة")
                
                success = self.template_service.preview_template(
                    project=project,
                    client_info=client_info,
                    payments=payments_list
                )
                
                if success:
                    QMessageBox.information(
                        self,
                        "✅ تم إنشاء الفاتورة",
                        f"تم فتح معاينة الفاتورة في المتصفح.\n\n"
                        f"يمكنك طباعتها من المتصفح (Ctrl+P)"
                    )
                else:
                    QMessageBox.critical(self, "خطأ", "فشل في إنشاء الفاتورة")
                return
            
            # Fallback: استخدام InvoicePrintingService
            profit_data = self.project_service.get_project_profitability(project.name)
            
            # Fallback: استخدام InvoicePrintingService
            # Step D: Prepare the complete data dictionary
            # ⚡ استخدم رقم الفاتورة المحفوظ أولاً، وإلا ولّد رقم جديد
            invoice_number = getattr(project, 'invoice_number', None)
            if not invoice_number:
                local_id = getattr(project, 'id', None) or 1
                invoice_number = f"SW-{97161 + int(local_id)}"
            
            invoice_data = {
                "invoice_number": invoice_number,
                "invoice_date": project.start_date.strftime("%Y-%m-%d") if hasattr(project, 'start_date') and project.start_date else datetime.now().strftime("%Y-%m-%d"),
                "due_date": project.end_date.strftime("%Y-%m-%d") if hasattr(project, 'end_date') and project.end_date else datetime.now().strftime("%Y-%m-%d"),
                "client_name": client.name,
                "client_phone": client.phone or "---",
                "client_address": client.address or "---",
                "project_name": project.name,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "items": [
                    {
                        "name": item.description,
                        "qty": float(item.quantity),
                        "price": float(item.unit_price),
                        "discount": float(item.discount_rate),
                        "total": float(item.total)
                    }
                    for item in project.items
                ],
                # حساب المجموع الفرعي من البنود (مع الخصومات)
                "subtotal": sum([float(item.total) for item in project.items]),
                "grand_total": float(project.total_amount),
                "total_paid": float(profit_data.get('total_paid', 0)),
                "remaining_amount": float(profit_data.get('balance_due', 0)),
                "remaining": float(profit_data.get('balance_due', 0)),
                "total_amount": float(project.total_amount),
                "payments": payments_list
            }
            
            # Step E: Use InvoicePrintingService to generate and open PDF
            from services.invoice_printing_service import InvoicePrintingService
            
            # Get settings service for company data
            settings_service = None
            if self.service_service and hasattr(self.service_service, 'settings_service'):
                settings_service = self.service_service.settings_service
            
            # Initialize printing service
            printing_service = InvoicePrintingService(settings_service=settings_service)
            
            # Print invoice (generates PDF and opens it automatically)
            pdf_path = printing_service.print_invoice(invoice_data)
            
            if pdf_path:
                if pdf_path.endswith('.pdf'):
                    QMessageBox.information(
                        self,
                        "✅ تم إنشاء الفاتورة",
                        f"تم إنشاء فاتورة PDF بنجاح!\n\n📄 {os.path.basename(pdf_path)}\n\n"
                        f"تم فتح الملف تلقائياً للطباعة."
                    )
                else:
                    # HTML file was created instead
                    QMessageBox.warning(
                        self,
                        "⚠️ تم حفظ HTML",
                        f"تم حفظ الفاتورة كملف HTML.\n\n"
                        f"📄 {os.path.basename(pdf_path)}\n\n"
                        f"💡 لإنشاء PDF، قم بتثبيت:\n"
                        f"   pip install weasyprint\n"
                        f"أو استخدم Google Chrome/Edge"
                    )
            else:
                QMessageBox.critical(self, "خطأ", "فشل في إنشاء الفاتورة")
                
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في طباعة الفاتورة:\n{str(e)}")
            import traceback
            traceback.print_exc()


    

    def _get_payments_list(self, project_name: str) -> list:
        """جلب قائمة الدفعات للمشروع"""
        payments_list = []
        try:
            payments = self.project_service.get_payments_for_project(project_name)
            print(f"INFO: [ProjectManager] تم جلب {len(payments)} دفعة للمشروع {project_name}")
            
            for payment in payments:
                account_name = "نقدي"
                if hasattr(payment, 'account_id') and payment.account_id:
                    try:
                        account = self.accounting_service.repo.get_account_by_code(payment.account_id)
                        if account:
                            account_name = account.name
                        else:
                            account = self.accounting_service.repo.get_account_by_id(payment.account_id)
                            if account:
                                account_name = account.name
                            else:
                                account_name = str(payment.account_id)
                    except Exception:
                        account_name = str(payment.account_id)
                
                payment_date = payment.date
                if hasattr(payment_date, 'strftime'):
                    date_str = payment_date.strftime("%Y-%m-%d")
                elif isinstance(payment_date, str):
                    date_str = payment_date[:10]
                else:
                    date_str = str(payment_date)[:10]
                
                try:
                    amount_val = float(payment.amount)
                except (ValueError, TypeError, AttributeError):
                    amount_val = 0.0
                
                payments_list.append({
                    'date': date_str,
                    'amount': amount_val,
                    'method': payment.method if hasattr(payment, 'method') else account_name,
                    'account_name': account_name,
                    'account_id': str(payment.account_id) if hasattr(payment, 'account_id') else ''
                })
            
            print(f"INFO: [ProjectManager] تم تجهيز {len(payments_list)} دفعة للطباعة")
        except Exception as e:
            print(f"ERROR: [ProjectManager] فشل جلب الدفعات: {e}")
        
        return payments_list

    def preview_invoice_template(self):
        """معاينة قالب الفاتورة في المتصفح باستخدام template_service"""
        if not self.selected_project:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مشروع أولاً")
            return
        
        try:
            project = self.selected_project
            
            # جلب بيانات العميل
            client = self.client_service.get_client_by_id(project.client_id)
            if not client:
                QMessageBox.warning(self, "خطأ", "لم يتم العثور على معلومات العميل")
                return
            
            # جلب الدفعات
            payments_list = self._get_payments_list(project.name)
            print(f"INFO: [ProjectManager] الدفعات المرسلة للقالب: {payments_list}")
            
            # تجهيز معلومات العميل
            client_info = {
                'name': client.name,
                'company_name': getattr(client, 'company_name', '') or '',
                'phone': client.phone or "---",
                'email': client.email or "",
                'address': client.address or "---"
            }
            
            # استخدام template_service للمعاينة
            if self.template_service:
                success = self.template_service.preview_template(
                    project=project,
                    client_info=client_info,
                    payments=payments_list
                )
                
                if success:
                    QMessageBox.information(
                        self,
                        "✅ معاينة الفاتورة",
                        "تم فتح معاينة الفاتورة في المتصفح.\n\n"
                        "يمكنك طباعتها من المتصفح (Ctrl+P)"
                    )
                else:
                    QMessageBox.critical(self, "خطأ", "فشل في معاينة الفاتورة")
            else:
                QMessageBox.warning(self, "خطأ", "خدمة القوالب غير متوفرة")
        
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في معاينة الفاتورة:\n{str(e)}")
            import traceback
            traceback.print_exc()

    # WhatsApp function removed - feature disabled