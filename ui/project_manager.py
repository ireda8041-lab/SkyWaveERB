import os
from datetime import datetime

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.accounting_service import AccountingService
from services.client_service import ClientService
from services.project_service import ProjectService
from services.service_service import ServiceService
from ui.auto_open_combobox import SimpleComboBox
from ui.custom_spinbox import CustomSpinBox
from ui.styles import BUTTON_STYLES


class ProjectItemDialog(QDialog):
    """نافذة اختيار بند خدمة وإضافته للمشروع."""

    def __init__(self, services_list: list[schemas.Service], parent=None):
        super().__init__(parent)
        self.services_list = services_list
        self.selected_item: schemas.ProjectItem | None = None
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

    def get_project_item(self) -> schemas.ProjectItem | None:
        return self.selected_item


class ProjectEditorDialog(QDialog):
    """
    🏢 شاشة إضافة/تعديل مشروع Enterprise Level
    نظام تبويبات متقدم مع تحليل الربحية اللحظي
    """

    def __init__(
        self,
        project_service: ProjectService,
        client_service: ClientService,
        service_service: ServiceService,
        accounting_service: AccountingService,
        project_to_edit: schemas.Project | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.project_service = project_service
        self.client_service = client_service
        self.service_service = service_service
        self.accounting_service = accounting_service
        self.project_to_edit = project_to_edit
        self.is_editing = project_to_edit is not None
        self.project_items: list[schemas.ProjectItem] = []
        self.milestones: list[schemas.ProjectMilestone] = []  # 🆕 الدفعات المرحلية

        # Get settings service for default treasury account
        self.settings_service = getattr(service_service, 'settings_service', None)

        if self.is_editing and project_to_edit is not None:
            self.setWindowTitle(f"🏢 تعديل مشروع: {project_to_edit.name}")
        else:
            self.setWindowTitle("🏢 مشروع جديد - Enterprise")

        # تفعيل زر التكبير والتصغير
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint)

        # 🆕 حجم متجاوب مع الشاشة
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_size = screen.availableGeometry()
            # النافذة تأخذ 85% من عرض الشاشة و 90% من ارتفاعها
            width = int(screen_size.width() * 0.85)
            height = int(screen_size.height() * 0.90)
            self.resize(width, height)
            # توسيط النافذة
            x = (screen_size.width() - width) // 2
            y = (screen_size.height() - height) // 2
            self.move(x, y)
        else:
            self.resize(1200, 800)

        self.setMinimumWidth(900)
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
            QTabWidget::pane {
                border: 1px solid #374151;
                border-radius: 8px;
                background-color: #1F2937;
            }
            QTabBar::tab {
                background-color: #374151;
                color: #9CA3AF;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #0A6CF1;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #4B5563;
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

        # 🆕 جلب مراكز التكلفة (حسابات المصروفات)
        self.cost_centers = [
            acc for acc in all_accounts
            if acc.type == schemas.AccountType.EXPENSE or acc.code.startswith("5") or acc.code.startswith("6")
        ]

        self.init_ui()

    def init_ui(self):
        from PyQt6.QtWidgets import QTabWidget

        main_layout = QVBoxLayout()

        # ==================== المنطقة العلوية الثابتة (Fixed Header) ====================
        header_group = QGroupBox("📋 معلومات المشروع الأساسية")
        header_layout = QVBoxLayout()

        # الصف الأول: العميل واسم المشروع
        row1 = QHBoxLayout()

        self.client_combo = SimpleComboBox()
        self.client_combo.addItem("--- اختر العميل ---", userData=None)
        for client in self.clients_list:
            self.client_combo.addItem(client.name, userData=client)
        self.client_combo.setCurrentIndex(0)
        client_names = [client.name for client in self.clients_list]
        self.client_combo.setup_completer(client_names)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("اسم المشروع (سيتم توليده تلقائياً)")

        row1.addWidget(QLabel("👤 العميل:"))
        row1.addWidget(self.client_combo, 2)
        row1.addWidget(QLabel("📝 اسم المشروع:"))
        row1.addWidget(self.name_input, 2)

        # الصف الثاني: كود المشروع (Read-only) والحالة
        row2 = QHBoxLayout()

        self.project_code_label = QLineEdit()
        self.project_code_label.setReadOnly(True)
        self.project_code_label.setPlaceholderText("سيتم توليده تلقائياً")
        self.project_code_label.setStyleSheet("background-color: #374151; color: #10B981; font-weight: bold;")

        self.status_combo = QComboBox()
        for status in schemas.ProjectStatus:
            self.status_combo.addItem(status.value, userData=status)
        self.status_combo.setCurrentText(schemas.ProjectStatus.ACTIVE.value)

        row2.addWidget(QLabel("🔢 كود المشروع:"))
        row2.addWidget(self.project_code_label, 1)
        row2.addWidget(QLabel("📊 الحالة:"))
        row2.addWidget(self.status_combo, 1)
        row2.addStretch()

        # زر الحفظ في الهيدر
        self.save_button = QPushButton("💾 حفظ المشروع")
        from ui.styles import BUTTON_STYLES
        self.save_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_button.setMinimumWidth(150)
        self.save_button.clicked.connect(self.save_project)
        row2.addWidget(self.save_button)

        header_layout.addLayout(row1)
        header_layout.addLayout(row2)
        header_group.setLayout(header_layout)
        main_layout.addWidget(header_group)

        # ==================== نظام التبويبات (Tabs) ====================
        from PyQt6.QtWidgets import QSizePolicy

        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Tab 1: التفاصيل الأساسية
        self.tabs.addTab(self._create_basic_info_tab(), "📋 التفاصيل الأساسية")

        # Tab 2: نطاق العمل والربحية
        self.tabs.addTab(self._create_scope_profit_tab(), "💰 نطاق العمل والربحية")

        # Tab 3: نظام الدفعات
        self.tabs.addTab(self._create_billing_tab(), "💳 نظام الدفعات")

        # Tab 4: الملاحظات والمرفقات
        self.tabs.addTab(self._create_notes_tab(), "📎 الملاحظات")

        main_layout.addWidget(self.tabs)

        # ==================== شريط الربحية السفلي (Profit Footer) ====================
        self._create_profit_footer(main_layout)

        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

        if self.is_editing:
            self.load_project_data()

    def _create_basic_info_tab(self):
        """Tab 1: التفاصيل الأساسية"""
        tab = QWidget()
        layout = QVBoxLayout()

        # التواريخ
        dates_group = QGroupBox("📅 التواريخ")
        dates_layout = QHBoxLayout()

        self.start_date_input = QDateEdit(QDate.currentDate())
        self.start_date_input.setCalendarPopup(True)
        self.end_date_input = QDateEdit(QDate.currentDate().addDays(30))
        self.end_date_input.setCalendarPopup(True)

        dates_layout.addWidget(QLabel("تاريخ البداية:"))
        dates_layout.addWidget(self.start_date_input)
        dates_layout.addWidget(QLabel("تاريخ الانتهاء:"))
        dates_layout.addWidget(self.end_date_input)
        dates_layout.addStretch()
        dates_group.setLayout(dates_layout)
        layout.addWidget(dates_group)

        # مدير المشروع ومركز التكلفة
        management_group = QGroupBox("👔 الإدارة والتكلفة")
        management_layout = QHBoxLayout()

        # مدير المشروع = المستخدم الحالي (تلقائياً)
        self.project_manager_label = QLabel("---")
        self.project_manager_label.setStyleSheet("""
            background-color: #374151;
            color: #10B981;
            font-weight: bold;
            padding: 8px 15px;
            border-radius: 6px;
            min-width: 150px;
        """)
        # جلب اسم المستخدم الحالي
        try:
            if self.parent() and hasattr(self.parent(), 'current_user'):
                current_user = self.parent().current_user
                if current_user:
                    self.project_manager_label.setText(f"👤 {current_user.full_name or current_user.username}")
                    self._current_user_id = current_user.username
            else:
                self.project_manager_label.setText("👤 المستخدم الحالي")
                self._current_user_id = None
        except Exception:
            self.project_manager_label.setText("👤 المستخدم الحالي")
            self._current_user_id = None

        self.cost_center_combo = SimpleComboBox()
        self.cost_center_combo.addItem("--- بدون مركز تكلفة ---", userData=None)
        for acc in self.cost_centers:
            self.cost_center_combo.addItem(f"{acc.name} ({acc.code})", userData=acc)

        management_layout.addWidget(QLabel("مدير المشروع:"))
        management_layout.addWidget(self.project_manager_label)
        management_layout.addWidget(QLabel("مركز التكلفة:"))
        management_layout.addWidget(self.cost_center_combo)
        management_layout.addStretch()
        management_group.setLayout(management_layout)
        layout.addWidget(management_group)

        # نوع العقد (مرة واحدة / اشتراك)
        contract_group = QGroupBox("📜 نوع العقد")
        contract_layout = QHBoxLayout()

        self.contract_type_combo = QComboBox()
        self.contract_type_combo.addItem("مرة واحدة", userData=schemas.ContractType.ONE_TIME)
        self.contract_type_combo.addItem("اشتراك/عقد متكرر", userData=schemas.ContractType.RETAINER)
        self.contract_type_combo.currentIndexChanged.connect(self._on_contract_type_changed)

        self.renewal_cycle_combo = QComboBox()
        self.renewal_cycle_combo.addItem("شهري", userData=schemas.RenewalCycle.MONTHLY)
        self.renewal_cycle_combo.addItem("ربع سنوي", userData=schemas.RenewalCycle.QUARTERLY)
        self.renewal_cycle_combo.addItem("سنوي", userData=schemas.RenewalCycle.YEARLY)
        self.renewal_cycle_combo.setEnabled(False)

        self.next_renewal_date = QDateEdit(QDate.currentDate().addMonths(1))
        self.next_renewal_date.setCalendarPopup(True)
        self.next_renewal_date.setEnabled(False)

        contract_layout.addWidget(QLabel("نوع العقد:"))
        contract_layout.addWidget(self.contract_type_combo)
        contract_layout.addWidget(QLabel("دورة التجديد:"))
        contract_layout.addWidget(self.renewal_cycle_combo)
        contract_layout.addWidget(QLabel("تاريخ التجديد القادم:"))
        contract_layout.addWidget(self.next_renewal_date)
        contract_layout.addStretch()
        contract_group.setLayout(contract_layout)
        layout.addWidget(contract_group)

        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _on_contract_type_changed(self, index):
        """تفعيل/تعطيل حقول الاشتراك"""
        is_retainer = self.contract_type_combo.currentData() == schemas.ContractType.RETAINER
        self.renewal_cycle_combo.setEnabled(is_retainer)
        self.next_renewal_date.setEnabled(is_retainer)

    def _create_scope_profit_tab(self):
        """Tab 2: نطاق العمل والربحية"""
        tab = QWidget()
        layout = QVBoxLayout()

        # --- بنود المشروع (الخدمات) ---
        items_group = QGroupBox("📦 بنود المشروع (الخدمات)")
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

        # 🆕 التكلفة التقديرية (للأدمن فقط)
        self.item_cost_input = CustomSpinBox(decimals=2, minimum=0, maximum=9999999999)
        self.item_cost_input.setToolTip("التكلفة التقديرية للبند (لحساب الربحية)")

        self.add_item_button = QPushButton("➕ إضافة البند")
        from ui.styles import BUTTON_STYLES
        self.add_item_button.setStyleSheet(BUTTON_STYLES["primary"])
        add_item_layout.addWidget(self.service_combo, 3)
        add_item_layout.addWidget(QLabel("الكمية:"))
        add_item_layout.addWidget(self.item_quantity_input, 1)
        add_item_layout.addWidget(QLabel("السعر:"))
        add_item_layout.addWidget(self.item_price_input, 1)
        add_item_layout.addWidget(QLabel("💰 التكلفة:"))
        add_item_layout.addWidget(self.item_cost_input, 1)
        add_item_layout.addWidget(self.add_item_button, 1)
        self.service_combo.currentIndexChanged.connect(self.on_service_selected)
        self.add_item_button.clicked.connect(lambda: self.add_item_to_table(item_to_add=None))
        items_layout.addLayout(add_item_layout)
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(7)  # 🆕 إضافة عمود التكلفة
        self.items_table.setHorizontalHeaderLabels(["البند", "الكمية", "السعر", "التكلفة", "خصم %", "الإجمالي", "حذف"])

        # تفعيل التحرير البسيط للكمية والسعر والخصم
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.SelectedClicked)
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.items_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        # تخصيص عرض الأعمدة بشكل مظبوط
        header = self.items_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # عمود الخدمة (أوسع)

            # تحديد عرض ثابت للأعمدة الرقمية
            self.items_table.setColumnWidth(1, 70)   # الكمية
            self.items_table.setColumnWidth(2, 90)   # السعر
            self.items_table.setColumnWidth(3, 90)   # التكلفة
            self.items_table.setColumnWidth(4, 70)   # الخصم
            self.items_table.setColumnWidth(5, 100)  # الإجمالي
            self.items_table.setColumnWidth(6, 45)   # الحذف

            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)

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

        # 🆕 جعل الجدول متجاوب
        from PyQt6.QtWidgets import QSizePolicy
        self.items_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.items_table.setMinimumHeight(250)
        self.items_table.verticalHeader().setDefaultSectionSize(36)
        self.items_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.items_table.verticalHeader().setVisible(True)
        self.items_table.setShowGrid(True)
        items_layout.addWidget(self.items_table, 1)  # stretch factor = 1
        items_group.setLayout(items_layout)
        layout.addWidget(items_group, 1)  # stretch factor = 1

        # --- الإجماليات ---
        totals_group = QGroupBox("📊 الإجماليات")
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
        self.total_label.setFont(QFont("Cairo", 14, QFont.Weight.Bold))
        self.total_label.setStyleSheet("color: #0A6CF1;")
        self.discount_rate_input.valueChanged.connect(self.update_totals)
        self.tax_rate_input.valueChanged.connect(self.update_totals)
        totals_form.addRow(QLabel("الخصم (%):"), self.discount_rate_input)
        totals_form.addRow(QLabel("الضريبة (%):"), self.tax_rate_input)
        totals_form.addRow(QLabel("<b>الإجمالي النهائي:</b>"), self.total_label)
        totals_group.setLayout(totals_form)
        layout.addWidget(totals_group)

        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _create_billing_tab(self):
        """Tab 3: نظام الدفعات المرحلية"""
        tab = QWidget()
        layout = QVBoxLayout()

        # الدفعة المقدمة السريعة
        quick_payment_group = QGroupBox("💵 دفعة مقدمة سريعة (اختياري)")
        payment_form = QFormLayout()
        self.payment_amount_input = CustomSpinBox(decimals=2, minimum=0, maximum=9999999)
        self.payment_amount_input.setValue(0.0)
        self.payment_amount_input.setSuffix(" EGP")
        self.payment_date_input = QDateEdit(QDate.currentDate())
        self.payment_date_input.setCalendarPopup(True)

        self.payment_account_combo = SimpleComboBox()
        self.payment_account_combo.addItem("اختر حساب البنك/الخزينة...", userData=None)
        for acc in self.cash_accounts:
            display_text = f"💰 {acc.name} ({acc.code})"
            self.payment_account_combo.addItem(display_text, userData=acc)

        account_names = [acc.name for acc in self.cash_accounts]
        self.payment_account_combo.setup_completer(account_names)
        self._auto_select_default_treasury()

        payment_form.addRow(QLabel("المبلغ:"), self.payment_amount_input)
        payment_form.addRow(QLabel("التاريخ:"), self.payment_date_input)
        payment_form.addRow(QLabel("الحساب:"), self.payment_account_combo)
        quick_payment_group.setLayout(payment_form)
        layout.addWidget(quick_payment_group)

        # جدول الدفعات المرحلية (Milestones)
        milestones_group = QGroupBox("📋 الدفعات المرحلية (Milestones)")
        milestones_layout = QVBoxLayout()

        # أزرار إضافة دفعة
        add_milestone_layout = QHBoxLayout()
        self.milestone_name_input = QLineEdit()
        self.milestone_name_input.setPlaceholderText("اسم الدفعة (مثل: دفعة التعاقد)")
        self.milestone_percent_input = CustomSpinBox(decimals=1, minimum=0, maximum=100)
        self.milestone_percent_input.setSuffix(" %")
        self.milestone_date_input = QDateEdit(QDate.currentDate())
        self.milestone_date_input.setCalendarPopup(True)

        add_milestone_btn = QPushButton("➕ إضافة دفعة")
        from ui.styles import BUTTON_STYLES
        add_milestone_btn.setStyleSheet(BUTTON_STYLES["primary"])
        add_milestone_btn.clicked.connect(self._add_milestone)

        add_milestone_layout.addWidget(self.milestone_name_input, 2)
        add_milestone_layout.addWidget(QLabel("النسبة:"))
        add_milestone_layout.addWidget(self.milestone_percent_input, 1)
        add_milestone_layout.addWidget(QLabel("الاستحقاق:"))
        add_milestone_layout.addWidget(self.milestone_date_input, 1)
        add_milestone_layout.addWidget(add_milestone_btn)
        milestones_layout.addLayout(add_milestone_layout)

        # جدول الدفعات (متجاوب)
        from PyQt6.QtWidgets import QSizePolicy
        self.milestones_table = QTableWidget()
        self.milestones_table.setColumnCount(5)
        self.milestones_table.setHorizontalHeaderLabels(["الدفعة", "النسبة %", "المبلغ", "تاريخ الاستحقاق", "حذف"])
        h_header = self.milestones_table.horizontalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.milestones_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.milestones_table.setMinimumHeight(180)
        milestones_layout.addWidget(self.milestones_table, 1)

        # تحذير مجموع النسب
        self.milestones_warning = QLabel("")
        self.milestones_warning.setStyleSheet("color: #EF4444; font-weight: bold;")
        milestones_layout.addWidget(self.milestones_warning)

        milestones_group.setLayout(milestones_layout)
        layout.addWidget(milestones_group)

        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _add_milestone(self):
        """إضافة دفعة مرحلية جديدة"""
        name = self.milestone_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "خطأ", "الرجاء إدخال اسم الدفعة")
            return

        percentage = self.milestone_percent_input.value()
        due_date = self.milestone_date_input.dateTime().toPyDateTime()

        # حساب المبلغ من النسبة
        total = self._calculate_total()
        amount = total * (percentage / 100)

        milestone = schemas.ProjectMilestone(
            name=name,
            percentage=percentage,
            amount=amount,
            due_date=due_date,
            status=schemas.MilestoneStatus.PENDING
        )
        self.milestones.append(milestone)
        self._rebuild_milestones_table()

        # مسح الحقول
        self.milestone_name_input.clear()
        self.milestone_percent_input.setValue(0)

    def _rebuild_milestones_table(self):
        """إعادة بناء جدول الدفعات المرحلية"""
        self.milestones_table.setRowCount(0)
        total_percent = 0

        for i, milestone in enumerate(self.milestones):
            self.milestones_table.insertRow(i)

            self.milestones_table.setItem(i, 0, QTableWidgetItem(milestone.name))
            self.milestones_table.setItem(i, 1, QTableWidgetItem(f"{milestone.percentage:.1f}%"))
            self.milestones_table.setItem(i, 2, QTableWidgetItem(f"{milestone.amount:,.2f}"))

            date_str = milestone.due_date.strftime("%Y-%m-%d") if milestone.due_date else ""
            self.milestones_table.setItem(i, 3, QTableWidgetItem(date_str))

            # زر الحذف
            delete_btn = QPushButton("X")
            delete_btn.setStyleSheet("background-color: #EF4444; color: white; border: none; border-radius: 3px;")
            delete_btn.clicked.connect(lambda _, idx=i: self._delete_milestone(idx))
            self.milestones_table.setCellWidget(i, 4, delete_btn)

            total_percent += milestone.percentage

        # تحديث التحذير
        if abs(total_percent - 100) > 0.1 and len(self.milestones) > 0:
            self.milestones_warning.setText(f"⚠️ مجموع النسب = {total_percent:.1f}% (يجب أن يكون 100%)")
        else:
            self.milestones_warning.setText("")

    def _delete_milestone(self, index):
        """حذف دفعة مرحلية"""
        if 0 <= index < len(self.milestones):
            del self.milestones[index]
            self._rebuild_milestones_table()

    def _create_notes_tab(self):
        """Tab 4: الملاحظات"""
        tab = QWidget()
        layout = QVBoxLayout()

        # الملاحظات
        notes_group = QGroupBox("📝 الوصف والملاحظات")
        notes_layout = QVBoxLayout()
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("أضف ملاحظات أو شروط المشروع هنا...")
        self.notes_input.setMinimumHeight(300)

        # 🆕 ملاحظات افتراضية للمشاريع الجديدة
        if not self.is_editing:
            default_notes = """1- تم تطبيق خصم _____ ج على الفاتورة.
2- يتم تسليم المشروع خلال _____ أيام عمل من تاريخ بداية التنفيذ.
3- يتم دفع 50% من إجمالي الفاتورة عند التعاقد.
4- أي طلبات إضافية خارج نطاق العمل المتفق عليه يتم تسعيرها بشكل مستقل.
5- يبدأ التنفيذ بعد استلام الدفعة الأولى واعتماد المحتوى/التفاصيل المطلوبة."""
            self.notes_input.setText(default_notes)

        notes_layout.addWidget(self.notes_input)
        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _create_profit_footer(self, main_layout):
        """إنشاء شريط الربحية السفلي"""
        profit_frame = QFrame()
        profit_frame.setStyleSheet("""
            QFrame {
                background-color: #1F2937;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        profit_layout = QHBoxLayout(profit_frame)

        # إجمالي الإيرادات
        self.revenue_label = QLabel("💰 الإيرادات: 0.00")
        self.revenue_label.setStyleSheet("color: #10B981; font-weight: bold; font-size: 13px;")
        profit_layout.addWidget(self.revenue_label)

        profit_layout.addWidget(QLabel("|"))

        # إجمالي التكلفة
        self.cost_label = QLabel("📊 التكلفة: 0.00")
        self.cost_label.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 13px;")
        profit_layout.addWidget(self.cost_label)

        profit_layout.addWidget(QLabel("|"))

        # صافي الربح
        self.profit_label = QLabel("💎 الربح: 0.00")
        self.profit_label.setStyleSheet("color: #10B981; font-weight: bold; font-size: 13px;")
        profit_layout.addWidget(self.profit_label)

        profit_layout.addWidget(QLabel("|"))

        # نسبة الهامش
        self.margin_label = QLabel("📈 الهامش: 0%")
        self.margin_label.setStyleSheet("color: #10B981; font-weight: bold; font-size: 14px;")
        profit_layout.addWidget(self.margin_label)

        profit_layout.addStretch()
        main_layout.addWidget(profit_frame)

    def _calculate_total(self):
        """حساب الإجمالي النهائي"""
        subtotal = sum(item.total for item in self.project_items)
        discount_rate = self.discount_rate_input.value() if hasattr(self, 'discount_rate_input') else 0
        discount_amount = subtotal * (discount_rate / 100)
        taxable_amount = subtotal - discount_amount
        tax_rate = self.tax_rate_input.value() if hasattr(self, 'tax_rate_input') else 0
        tax_amount = taxable_amount * (tax_rate / 100)
        return taxable_amount + tax_amount

    def _update_profit_footer(self):
        """تحديث شريط الربحية اللحظي"""
        try:
            # حساب الإيرادات
            total_revenue = self._calculate_total()

            # حساب التكلفة
            total_cost = sum(getattr(item, 'estimated_cost', 0) or 0 for item in self.project_items)

            # حساب الربح والهامش
            net_profit = total_revenue - total_cost
            margin_percent = (net_profit / total_revenue * 100) if total_revenue > 0 else 0

            # تحديث Labels
            self.revenue_label.setText(f"💰 الإيرادات: {total_revenue:,.2f}")
            self.cost_label.setText(f"📊 التكلفة: {total_cost:,.2f}")
            self.profit_label.setText(f"💎 الربح: {net_profit:,.2f}")
            self.margin_label.setText(f"📈 الهامش: {margin_percent:.1f}%")

            # تغيير اللون حسب نسبة الهامش
            if margin_percent >= 40:
                color = "#10B981"  # أخضر
            elif margin_percent >= 20:
                color = "#F59E0B"  # برتقالي
            else:
                color = "#EF4444"  # أحمر

            self.margin_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px;")
            self.profit_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px;")

        except Exception as e:
            print(f"ERROR: [ProjectEditor] فشل تحديث شريط الربحية: {e}")

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

    def add_item_to_table(self, item_to_add: schemas.ProjectItem | None = None):
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
            # 🆕 جلب التكلفة التقديرية
            estimated_cost = self.item_cost_input.value() if hasattr(self, 'item_cost_input') else 0
            item_schema = schemas.ProjectItem(
                service_id=service._mongo_id or str(service.id),
                description=service.name,
                quantity=quantity,
                unit_price=price,
                discount_rate=0.0,
                discount_amount=0.0,
                total=subtotal_item,
                estimated_cost=estimated_cost  # 🆕 التكلفة التقديرية
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

            # 🆕 عمود التكلفة التقديرية (قابل للتعديل)
            cost_value = getattr(item, 'estimated_cost', 0) or 0
            cost_item = QTableWidgetItem(str(cost_value))
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            cost_item.setToolTip("التكلفة التقديرية للبند")
            cost_item.setBackground(QColor("#1A202C"))
            cost_item.setForeground(QColor("#F59E0B"))  # لون برتقالي للتكلفة
            self.items_table.setItem(index, 3, cost_item)

            # عمود الخصم (قابل للتعديل، في الوسط)
            discount_text = str(item.discount_rate) if item.discount_rate > 0 else "0"
            discount_item = QTableWidgetItem(discount_text)
            discount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            discount_item.setToolTip("دبل كليك للتعديل (بدون %)")
            discount_item.setBackground(QColor("#1A202C"))
            self.items_table.setItem(index, 4, discount_item)

            # عمود الإجمالي (غير قابل للتعديل، في الوسط)
            total_item = QTableWidgetItem(f"{item.total:,.2f}")
            total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.items_table.setItem(index, 5, total_item)

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

            self.items_table.setCellWidget(index, 6, delete_container)

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

            elif column == 3:  # 🆕 التكلفة التقديرية
                try:
                    item.estimated_cost = float(cell_text) if cell_text else 0
                except ValueError:
                    cell_item.setText(str(getattr(item, 'estimated_cost', 0)))
                    return

            elif column == 4:  # الخصم
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
            total_item = self.items_table.item(row, 5)
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

        # 🆕 تحديث شريط الربحية اللحظي
        self._update_profit_footer()

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

    def _add_new_client(self, client_name: str) -> schemas.Client | None:
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

    def _add_new_service(self, service_name: str) -> schemas.Service | None:
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

    def check_and_add_client(self, client_name: str) -> schemas.Client | None:
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

    def check_and_add_service(self, service_name: str) -> schemas.Service | None:
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

        # 1. تجميع بيانات المشروع (مع Enterprise Features)
        project_data = {
            "name": self.name_input.text(),
            "client_id": selected_client.name,
            "status": selected_status,
            "description": "",
            "start_date": self.start_date_input.dateTime().toPyDateTime(),
            "end_date": self.end_date_input.dateTime().toPyDateTime(),
            "items": self.project_items,
            "discount_rate": self.discount_rate_input.value(),
            "tax_rate": self.tax_rate_input.value(),
            "project_notes": self.notes_input.toPlainText(),
            "currency": schemas.CurrencyCode.EGP,
            # 🆕 Enterprise Features
            "milestones": self.milestones,
        }

        # إضافة مركز التكلفة إذا تم اختياره
        if hasattr(self, 'cost_center_combo'):
            cost_center = self.cost_center_combo.currentData()
            if cost_center:
                project_data["cost_center_id"] = cost_center.code

        # إضافة نوع العقد
        if hasattr(self, 'contract_type_combo'):
            contract_type = self.contract_type_combo.currentData()
            project_data["contract_type"] = contract_type
            project_data["is_retainer"] = contract_type == schemas.ContractType.RETAINER

            if contract_type == schemas.ContractType.RETAINER:
                project_data["renewal_cycle"] = self.renewal_cycle_combo.currentData()
                project_data["next_renewal_date"] = self.next_renewal_date.dateTime().toPyDateTime()

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
        self.projects_list: list[schemas.Project] = []
        self.selected_project: schemas.Project | None = None

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
        self.print_button = QPushButton("🖨️ طباعة")
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

        self.projects_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.projects_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.projects_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        h_header = self.projects_table.horizontalHeader()
        v_header = self.projects_table.verticalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            h_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)  # ⚡ محاذاة رأس الجدول للوسط
        if v_header is not None:
            v_header.setDefaultSectionSize(45)  # ⚡ ارتفاع الصفوف
            v_header.setVisible(False)
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
        self.revenue_card = self.create_kpi_card("إجمالي العقد", "0.00", "#0A6CF1")
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
        h_header = self.preview_payments_table.horizontalHeader()
        v_header = self.preview_payments_table.verticalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if v_header is not None:
            v_header.setDefaultSectionSize(40)  # ⚡ ارتفاع الصفوف
            v_header.setVisible(False)
        self.preview_payments_table.setMaximumHeight(150)
        preview_layout.addWidget(self.preview_payments_table)

        preview_layout.addWidget(QLabel("<b>المصروفات المرتبطة:</b>"))
        self.preview_expenses_table = QTableWidget()
        self.preview_expenses_table.setColumnCount(3)
        self.preview_expenses_table.setHorizontalHeaderLabels(["التاريخ", "الوصف", "المبلغ"])
        h_header = self.preview_expenses_table.horizontalHeader()
        v_header = self.preview_expenses_table.verticalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if v_header is not None:
            v_header.setDefaultSectionSize(40)  # ⚡ ارتفاع الصفوف
            v_header.setVisible(False)
        preview_layout.addWidget(self.preview_expenses_table)

        # جدول المهام المرتبطة بالمشروع
        tasks_header_layout = QHBoxLayout()
        tasks_label = QLabel("<b>📋 المهام المرتبطة:</b>")
        tasks_header_layout.addWidget(tasks_label)
        tasks_header_layout.addStretch()

        self.add_task_btn = QPushButton("➕ مهمة جديدة")
        self.add_task_btn.setStyleSheet("""
            QPushButton {
                background-color: #8B2CF5;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
        """)
        self.add_task_btn.clicked.connect(self._on_add_task_for_project)
        tasks_header_layout.addWidget(self.add_task_btn)
        preview_layout.addLayout(tasks_header_layout)

        self.preview_tasks_table = QTableWidget()
        self.preview_tasks_table.setColumnCount(4)
        self.preview_tasks_table.setHorizontalHeaderLabels(["المهمة", "الأولوية", "الحالة", "تاريخ الاستحقاق"])
        h_header = self.preview_tasks_table.horizontalHeader()
        v_header = self.preview_tasks_table.verticalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if v_header is not None:
            v_header.setDefaultSectionSize(40)  # ⚡ ارتفاع الصفوف
            v_header.setVisible(False)
        self.preview_tasks_table.setMaximumHeight(150)
        self.preview_tasks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_tasks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        preview_layout.addWidget(self.preview_tasks_table)

        main_layout.addWidget(self.preview_groupbox, 1)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_projects_data() - يتم استدعاؤها من MainWindow
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

                        self.preview_payments_table.setItem(i, 0, QTableWidgetItem(date_str))
                        self.preview_payments_table.setItem(i, 1, QTableWidgetItem(f"{pay.amount:,.2f}"))

                        # عرض اسم الحساب بدلاً من ID
                        account_name = "نقدي"  # افتراضي
                        try:
                            # محاولة جلب الحساب بالكود أولاً
                            account = self.accounting_service.repo.get_account_by_code(pay.account_id)
                            if account:
                                account_name = account.name
                            else:
                                # محاولة جلب الحساب بالـ ID
                                account = self.accounting_service.repo.get_account_by_id(pay.account_id)
                                if account:
                                    account_name = account.name
                                else:
                                    # استخدام الـ ID كما هو
                                    account_name = str(pay.account_id)
                        except Exception as acc_err:
                            print(f"WARNING: فشل جلب اسم الحساب: {acc_err}")
                            account_name = str(pay.account_id)

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
                        except (AttributeError, ValueError, TypeError):
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

        from PyQt6.QtWidgets import QApplication

        from core.data_loader import get_data_loader

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
            from ui.todo_manager import TaskEditorDialog, TaskService

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

    def open_editor(self, project_to_edit: schemas.Project | None = None):
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
                        "تم فتح معاينة الفاتورة في المتصفح.\n\n"
                        "يمكنك طباعتها من المتصفح (Ctrl+P)"
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
