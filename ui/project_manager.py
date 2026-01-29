import os
from datetime import datetime

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor
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
from ui.custom_spinbox import CustomSpinBox
from ui.smart_combobox import SmartFilterComboBox
from ui.styles import (
    BUTTON_STYLES,
    COLORS,
    TABLE_STYLE_DARK,
    get_cairo_font,
)

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


# استيراد نظام الإشعارات
try:
    from ui.notification_system import notify_error, notify_info, notify_success, notify_warning
except ImportError:

    def notify_success(msg, title=None):
        pass

    def notify_error(msg, title=None):
        pass

    def notify_warning(msg, title=None):
        pass

    def notify_info(msg, title=None):
        pass


class ProjectItemDialog(QDialog):
    """نافذة اختيار بند خدمة وإضافته للمشروع."""

    def __init__(self, services_list: list[schemas.Service], parent=None):
        super().__init__(parent)
        self.services_list = services_list
        self.selected_item: schemas.ProjectItem | None = None
        self.setWindowTitle("إضافة بند جديد")
        self.setMinimumWidth(350)
        self.setMinimumHeight(250)

        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

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
        # SmartFilterComboBox للخدمة مع فلترة
        self.service_combo = SmartFilterComboBox()
        for service in services_list:
            self.service_combo.addItem(service.name, userData=service)

        self.quantity_input = CustomSpinBox(decimals=2, minimum=0.01, maximum=1000)
        self.quantity_input.setValue(1.0)

        self.unit_price_input = CustomSpinBox(decimals=2, minimum=0.0, maximum=1_000_000)
        self.unit_price_input.setSuffix(" ج.م")
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
    (معدلة بالكامل) شاشة إضافة/تعديل مشروع (مع الدفعة المقدمة)
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

        # Get settings service for default treasury account
        self.settings_service = getattr(service_service, "settings_service", None)

        if self.is_editing:
            self.setWindowTitle(f"تعديل مشروع: {project_to_edit.name}")
        else:
            self.setWindowTitle("مشروع جديد")

        # ⚡ فتح النافذة بحجم الشاشة الكامل
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        # الحصول على حجم الشاشة وفتح النافذة بحجم كبير
        from PyQt6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            # ⚡ فتح بنسبة 95% من حجم الشاشة لإظهار كل المحتوى بدون scroll
            width = int(screen_geo.width() * 0.95)
            height = int(screen_geo.height() * 0.95)
            x = (screen_geo.width() - width) // 2
            y = (screen_geo.height() - height) // 2
            self.setGeometry(x, y, width, height)

        self.setMinimumWidth(1100)  # ⚡ زيادة العرض الأدنى
        self.setMinimumHeight(750)  # ⚡ زيادة الارتفاع الأدنى

        # 📱 سياسة التمدد الكامل
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

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
            acc
            for acc in all_accounts
            if acc.type == schemas.AccountType.CASH
            or (acc.code and acc.code.startswith("111"))  # الخزينة 111x
            or (acc.code and acc.code.startswith("12"))  # المحافظ الإلكترونية 12xx
        ]

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)  # ⚡ زيادة المسافات قليلاً
        main_layout.setContentsMargins(10, 10, 10, 10)  # ⚡ زيادة الهوامش

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

        # SmartFilterComboBox للعميل مع فلترة
        self.client_combo = SmartFilterComboBox()
        self.client_combo.addItem("--- اختر العميل ---", userData=None)
        for client in self.clients_list:
            self.client_combo.addItem(client.name, userData=client)
        self.client_combo.setCurrentIndex(0)

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
        # SmartFilterComboBox للخدمة مع فلترة
        self.service_combo = SmartFilterComboBox()
        self.service_combo.addItem("اختر الخدمة أو الباقة...", userData=None)
        for service in self.services_list:
            self.service_combo.addItem(
                f"{service.name} ({service.default_price})", userData=service
            )
        self.service_combo.setCurrentIndex(0)
        self.item_price_input = CustomSpinBox(decimals=2, minimum=0, maximum=9999999999)
        self.item_price_input.setSuffix(" ج.م")
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

        # ⚡ إضافة label لعرض وصف الخدمة بشكل واضح
        from PyQt6.QtWidgets import QSizePolicy

        self.service_description_label = QLabel("")
        self.service_description_label.setWordWrap(True)
        self.service_description_label.setTextFormat(Qt.TextFormat.PlainText)
        self.service_description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.service_description_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["text_primary"]};
                font-size: 12px;
                font-family: 'Cairo';
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(59, 130, 246, 0.15),
                    stop:1 rgba(59, 130, 246, 0.05));
                border: 1px solid rgba(59, 130, 246, 0.3);
                border-radius: 8px;
                padding: 12px 15px;
                margin: 5px 0;
                line-height: 1.6;
            }}
        """)
        self.service_description_label.setVisible(False)  # مخفي افتراضياً
        items_layout.addWidget(self.service_description_label)

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels(
            ["البند", "الكمية", "السعر", "خصم", "الإجمالي", "حذف"]
        )

        # تفعيل التحرير البسيط للكمية والسعر والخصم
        self.items_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.SelectedClicked
        )
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.items_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        # تخصيص عرض الأعمدة بشكل مظبوط
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # عمود البند (يتمدد)

        # تحديد عرض ثابت للأعمدة الرقمية - مصغر
        self.items_table.setColumnWidth(1, 60)  # الكمية
        self.items_table.setColumnWidth(2, 75)  # السعر
        self.items_table.setColumnWidth(3, 55)  # الخصم
        self.items_table.setColumnWidth(4, 85)  # الإجمالي
        self.items_table.setColumnWidth(5, 35)  # الحذف

        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)

        # ستايل الجدول
        self.items_table.setStyleSheet(TABLE_STYLE_DARK)

        self.items_table.setMinimumHeight(180)  # ⚡ زيادة ارتفاع الجدول
        self.items_table.verticalHeader().setDefaultSectionSize(30)  # ⚡ ارتفاع الصفوف أكبر قليلاً
        self.items_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.items_table.verticalHeader().setVisible(True)
        self.items_table.setShowGrid(True)
        items_layout.addWidget(self.items_table, 1)  # ⚡ stretch factor للتمدد
        items_group.setLayout(items_layout)
        left_side.addWidget(items_group, 1)  # ⚡ stretch factor للتمدد

        # --- 3. الإجماليات ---
        totals_group = QGroupBox("الإجماليات")
        totals_form = QFormLayout()
        totals_form.setSpacing(4)
        totals_form.setContentsMargins(6, 12, 6, 6)

        # الخصم (نسبة أو مبلغ)
        discount_layout = QHBoxLayout()
        discount_layout.setSpacing(4)
        self.discount_type_combo = QComboBox()
        self.discount_type_combo.addItem("نسبة %", "percent")
        self.discount_type_combo.addItem("مبلغ", "amount")
        self.discount_type_combo.setFixedWidth(70)
        self.discount_type_combo.currentIndexChanged.connect(self._on_discount_type_changed)

        self.discount_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.discount_rate_input.setSuffix(" %")
        discount_layout.addWidget(self.discount_type_combo)
        discount_layout.addWidget(self.discount_rate_input)

        self.tax_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.tax_rate_input.setSuffix(" %")
        if self.service_service and getattr(self.service_service, "settings_service", None):
            try:
                default_tax = self.service_service.settings_service.get_setting("default_tax_rate")
                self.tax_rate_input.setValue(default_tax or 0.0)
            except Exception:
                pass
        self.total_label = QLabel("0.00 ج.م")
        self.total_label.setFont(get_cairo_font(12, bold=True))
        self.total_label.setStyleSheet("color: #0A6CF1;")
        self.discount_rate_input.valueChanged.connect(self.update_totals)
        self.tax_rate_input.valueChanged.connect(self.update_totals)
        totals_form.addRow(QLabel("الخصم:"), discount_layout)
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
        self.notes_input.setMinimumHeight(180)  # ⚡ زيادة ارتفاع حقل الملاحظات

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
        self.payment_amount_input.setSuffix(" ج.م")
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
        # SmartFilterComboBox للحساب مع فلترة
        self.payment_account_combo = SmartFilterComboBox()
        self.payment_account_combo.addItem("اختر الحساب...", userData=None)
        for acc in self.cash_accounts:
            display_text = f"{acc.name} ({acc.code})"
            self.payment_account_combo.addItem(display_text, userData=acc)
        self._auto_select_default_treasury()
        account_row.addWidget(account_label)
        account_row.addWidget(self.payment_account_combo, 1)
        payment_layout.addLayout(account_row)

        payment_group.setLayout(payment_layout)
        right_side.addWidget(payment_group)

        # إضافة الجانبين للتخطيط الأفقي الرئيسي
        main_horizontal_layout.addLayout(left_side, 3)  # البيانات والبنود على اليسار (أوسع)
        main_horizontal_layout.addLayout(right_side, 2)  # الوصف والدفعة على اليمين
        main_layout.addLayout(main_horizontal_layout, 1)  # ⚡ stretch factor للتمدد

        # --- 5. أزرار التحكم ---
        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("💾 حفظ المشروع")

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
                        safe_print(
                            f"INFO: [ProjectDialog] Auto-selected default treasury: {account_data.name} ({default_treasury_code})"
                        )
                        break
        except Exception as e:
            safe_print(f"WARNING: [ProjectDialog] Failed to auto-select default treasury: {e}")

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
                or (
                    client_local_id is not None
                    and str(client_local_id).strip() == project_client_ref
                )
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
        start_value = self.project_to_edit.start_date or datetime.now()
        end_value = self.project_to_edit.end_date or datetime.now()
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
            # ⚡ عرض وصف الخدمة بشكل واضح
            service_desc = getattr(service, "description", None)
            safe_print(f"DEBUG: [ProjectEditor] الخدمة: {service.name}, الوصف: {service_desc}")

            if service_desc and str(service_desc).strip():
                self.service_description_label.setText(f"📝 وصف الخدمة: {service_desc}")
                self.service_description_label.setVisible(True)
                self.service_combo.setToolTip(f"📝 {service_desc}")
            else:
                self.service_description_label.setText("📝 لا يوجد وصف لهذه الخدمة")
                self.service_description_label.setVisible(True)
                self.service_combo.setToolTip("")
        else:
            # إخفاء الوصف عند عدم اختيار خدمة
            if hasattr(self, "service_description_label"):
                self.service_description_label.setVisible(False)
            self.service_combo.setToolTip("")

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

            # إنشاء وصف يشمل اسم الخدمة ووصفها
            service_desc = service.description or ""
            item_description = service.name

            item_schema = schemas.ProjectItem(
                service_id=service._mongo_id or str(service.id),
                description=item_description,
                quantity=quantity,
                unit_price=price,
                discount_rate=0.0,
                discount_amount=0.0,
                total=subtotal_item,
            )
            # حفظ وصف الخدمة الكامل للـ tooltip
            item_schema._service_full_desc = service_desc
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
            safe_print(f"ERROR: [ProjectEditor] فشل حذف البند: {e}")

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

            # عمود الوصف (غير قابل للتعديل) - مع tooltip للوصف الكامل
            desc_item = QTableWidgetItem(item.description)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            desc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

            # إضافة tooltip بوصف الخدمة الكامل إذا وجد
            full_desc = getattr(item, "_service_full_desc", None)
            if full_desc:
                desc_item.setToolTip(f"📝 {full_desc}")
            else:
                # محاولة جلب وصف الخدمة من القائمة
                for service in self.services_list:
                    if service.name == item.description and service.description:
                        desc_item.setToolTip(f"📝 {service.description}")
                        break

            self.items_table.setItem(index, 0, desc_item)

            # عمود الكمية (قابل للتعديل، في الوسط)
            qty_item = QTableWidgetItem(str(item.quantity))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            qty_item.setToolTip("دبل كليك للتعديل")
            qty_item.setBackground(QColor("#1A202C"))
            self.items_table.setItem(index, 1, qty_item)

            # عمود السعر (قابل للتعديل، في الوسط)
            price_item = QTableWidgetItem(str(item.unit_price))
            price_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            price_item.setToolTip("دبل كليك للتعديل")
            price_item.setBackground(QColor("#1A202C"))
            self.items_table.setItem(index, 2, price_item)

            # عمود الخصم بالمبلغ (قابل للتعديل، في الوسط)
            discount_text = f"{item.discount_amount:.2f}" if item.discount_amount > 0 else "0"
            discount_item = QTableWidgetItem(discount_text)
            discount_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            discount_item.setToolTip("دبل كليك للتعديل (بالجنيه)")
            discount_item.setBackground(QColor("#1A202C"))
            self.items_table.setItem(index, 3, discount_item)

            # عمود الإجمالي (غير قابل للتعديل، في الوسط)
            total_item = QTableWidgetItem(f"{item.total:,.2f}")
            total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            total_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
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
            safe_print(f"ERROR: [ProjectEditor] on_quantity_changed: {e}")

    def on_price_changed(self, row: int, value: float):
        """تحديث السعر وإعادة حساب الإجمالي"""
        try:
            self.project_items[row].unit_price = value
            self._recalculate_item_total(row)
        except Exception as e:
            safe_print(f"ERROR: [ProjectEditor] on_price_changed: {e}")

    def on_discount_changed(self, row: int, value: float):
        """تحديث الخصم وإعادة حساب الإجمالي"""
        try:
            self.project_items[row].discount_rate = value
            self._recalculate_item_total(row)
        except Exception as e:
            safe_print(f"ERROR: [ProjectEditor] on_discount_changed: {e}")

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

            elif column == 3:  # الخصم بالمبلغ
                try:
                    discount_text = cell_text.replace("ج.م", "").strip()
                    item.discount_amount = float(discount_text) if discount_text else 0
                    # حساب النسبة من المبلغ للحفظ
                    subtotal = item.quantity * item.unit_price
                    if subtotal > 0:
                        item.discount_rate = (item.discount_amount / subtotal) * 100
                    else:
                        item.discount_rate = 0
                except ValueError:
                    cell_item.setText(f"{item.discount_amount:.2f}")
                    return

            # إعادة حساب الإجمالي
            subtotal = item.quantity * item.unit_price
            # الخصم بالمبلغ مباشرة (لا يتجاوز الإجمالي)
            item.discount_amount = min(item.discount_amount, subtotal)
            item.total = subtotal - item.discount_amount
            # تحديث النسبة
            if subtotal > 0:
                item.discount_rate = (item.discount_amount / subtotal) * 100

            # تحديث عمود الإجمالي
            total_item = self.items_table.item(row, 4)
            if total_item:
                total_item.setText(f"{item.total:,.2f}")

            # تحديث الإجماليات الكلية
            self.update_totals()

        except Exception as e:
            safe_print(f"ERROR: خطأ في تحديث البند: {e}")

    def _recalculate_item_total(self, row: int):
        """إعادة حساب إجمالي البند"""
        item = self.project_items[row]
        subtotal = item.quantity * item.unit_price
        # الخصم بالمبلغ مباشرة (لا يتجاوز الإجمالي)
        item.discount_amount = min(item.discount_amount, subtotal)
        item.total = subtotal - item.discount_amount
        # تحديث النسبة
        if subtotal > 0:
            item.discount_rate = (item.discount_amount / subtotal) * 100

        # تحديث عمود الإجمالي في الجدول
        total_item = self.items_table.item(row, 4)
        if total_item:
            total_item.setText(f"{item.total:,.2f}")

        # تحديث الإجماليات الكلية
        self.update_totals()

    def _on_discount_type_changed(self, index):
        """تغيير نوع الخصم (نسبة أو مبلغ)"""
        discount_type = self.discount_type_combo.currentData()
        if discount_type == "percent":
            self.discount_rate_input.setMaximum(100)
            self.discount_rate_input.setSuffix(" %")
        else:
            self.discount_rate_input.setMaximum(999999999)
            self.discount_rate_input.setSuffix(" ج.م")
        self.update_totals()

    def update_totals(self):
        subtotal = sum(item.total for item in self.project_items)

        # حساب الخصم حسب النوع
        discount_type = self.discount_type_combo.currentData()
        discount_value = self.discount_rate_input.value()

        if discount_type == "amount":
            # الخصم بالمبلغ مباشرة
            discount_amount = min(discount_value, subtotal)  # لا يتجاوز الإجمالي
        else:
            # الخصم بالنسبة
            discount_amount = subtotal * (discount_value / 100)

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
            service_name = item_text.split("(")[0].strip()
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
                    QMessageBox.information(
                        self, "نجح", f"تم إضافة العميل '{new_client.name}' بنجاح!"
                    )
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
                    QMessageBox.information(
                        self, "نجح", f"تم إضافة الخدمة '{new_service.name}' بنجاح!"
                    )
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
            QMessageBox.StandardButton.Yes,
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
            QMessageBox.StandardButton.Yes,
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
                    self.service_combo.addItem(
                        f"{new_service.name} ({new_service.default_price})", userData=new_service
                    )
                    self.service_combo.setCurrentText(new_service.name)
                    QMessageBox.information(
                        self, "نجح", f"تم إضافة الخدمة '{new_service.name}' بنجاح!"
                    )
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
        # حساب الخصم حسب النوع
        discount_type = self.discount_type_combo.currentData()
        discount_value = self.discount_rate_input.value()
        subtotal = sum(item.total for item in self.project_items)

        if discount_type == "amount" and discount_value > 0 and subtotal > 0:
            # تحويل المبلغ لنسبة للحفظ
            discount_rate = (discount_value / subtotal) * 100
        else:
            discount_rate = discount_value

        project_data = {
            "name": self.name_input.text(),
            "client_id": selected_client.name,
            "status": selected_status,
            "description": "",  # الوصف في notes_input دلوقتي
            "start_date": self.start_date_input.dateTime().toPyDateTime(),
            "end_date": self.end_date_input.dateTime().toPyDateTime(),
            "items": self.project_items,
            "discount_rate": discount_rate,
            "tax_rate": self.tax_rate_input.value(),
            "project_notes": self.notes_input.toPlainText(),
            "currency": schemas.CurrencyCode.EGP,
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
                "account_id": selected_account.code,
            }

        # حساب إجمالي المشروع للتحقق من نسبة الدفعة المقدمة
        # (subtotal و discount_rate تم حسابهم أعلاه)
        if discount_type == "amount":
            discount_amount_calc = min(discount_value, subtotal)
        else:
            discount_amount_calc = subtotal * (discount_rate / 100)
        taxable_amount = subtotal - discount_amount_calc
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
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    return

        try:
            if self.is_editing:
                self.project_service.update_project(self.project_to_edit.name, project_data)
            else:
                self.project_service.create_project(project_data, payment_data)

            self.accept()
        except Exception as e:
            notify_error(f"فشل الحفظ: {e}", "خطأ")


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

        # === استخدام Splitter للتجاوب التلقائي ===
        from PyQt6.QtWidgets import QScrollArea, QSizePolicy, QSplitter

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(outer_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Splitter رئيسي يتحول من أفقي لعمودي حسب الحجم
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #334155;
                width: 3px;
                margin: 0 3px;
            }
        """)
        outer_layout.addWidget(self.main_splitter)

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals

        app_signals.projects_changed.connect(self._on_projects_changed)
        app_signals.payments_changed.connect(self._on_projects_changed)

        # --- 1. الجزء الأيسر (الجدول والأزرار) ---
        left_widget = QWidget()
        left_panel = QVBoxLayout(left_widget)
        left_panel.setContentsMargins(5, 5, 5, 5)

        # === شريط الأزرار المتجاوب ===
        from ui.responsive_toolbar import ResponsiveToolbar

        self.toolbar = ResponsiveToolbar()

        self.add_button = QPushButton("➕ مشروع جديد")
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

        # 🗑️ زرار حذف المشروع
        self.delete_button = QPushButton("🗑️ حذف")
        self.delete_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_button.setFixedHeight(28)
        self.delete_button.clicked.connect(self.delete_selected_project)
        self.delete_button.setEnabled(False)

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

        # إضافة الأزرار للـ toolbar المتجاوب
        self.toolbar.addButton(self.add_button)
        self.toolbar.addButton(self.edit_button)
        self.toolbar.addButton(self.delete_button)
        self.toolbar.addButton(self.payment_button)
        self.toolbar.addButton(self.profit_button)
        self.toolbar.addButton(self.print_button)
        self.toolbar.addButton(self.preview_template_button)
        self.toolbar.addButton(self.refresh_button)
        self.toolbar.addWidget(self.show_archived_checkbox)

        left_panel.addWidget(self.toolbar)

        table_groupbox = QGroupBox("قايمة المشاريع")
        table_layout = QVBoxLayout()
        table_groupbox.setLayout(table_layout)

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar

        self.projects_table = QTableWidget()
        self.projects_table.setColumnCount(5)
        self.projects_table.setHorizontalHeaderLabels(
            ["رقم الفاتورة", "اسم المشروع", "العميل", "الحالة", "تاريخ البدء"]
        )

        # ⚡ تفعيل الترتيب بالضغط على رأس العمود
        self.projects_table.setSortingEnabled(True)

        self.search_bar = UniversalSearchBar(
            self.projects_table,
            placeholder="🔍 بحث (رقم الفاتورة، اسم المشروع، العميل، الحالة، التاريخ)...",
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

        # === إضافة شريط ملخص الفواتير ===
        summary_frame = QFrame()
        summary_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_medium"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(10, 5, 10, 5)
        summary_layout.setSpacing(20)

        # عدد الفواتير
        self.invoices_count_label = QLabel("📄 عدد الفواتير: 0")
        self.invoices_count_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: bold;"
        )
        summary_layout.addWidget(self.invoices_count_label)

        summary_layout.addStretch()

        # إجمالي مبالغ الفواتير
        self.invoices_total_label = QLabel("💰 إجمالي الفواتير: 0.00 جنيه")
        self.invoices_total_label.setStyleSheet(
            "color: #10b981; font-size: 12px; font-weight: bold;"
        )
        summary_layout.addWidget(self.invoices_total_label)

        table_layout.addWidget(summary_frame)

        left_panel.addWidget(table_groupbox, 1)

        # إضافة الجزء الأيسر للـ splitter
        self.main_splitter.addWidget(left_widget)

        # --- 2. لوحة معاينة ربحية المشروع (تصميم احترافي) ---
        # وضعها في ScrollArea للتمرير عند الحاجة
        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        preview_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.preview_groupbox = QGroupBox()
        self.preview_groupbox.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.preview_groupbox.setStyleSheet("""
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(10, 42, 85, 0.95),
                    stop:1 rgba(5, 32, 69, 0.98));
                border: 1px solid rgba(10, 108, 241, 0.3);
                border-radius: 10px;
                margin: 0px;
                padding: 0px;
            }
        """)
        preview_layout = QVBoxLayout()
        preview_layout.setSpacing(6)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        self.preview_groupbox.setLayout(preview_layout)

        # === عنوان اللوحة (بسيط) ===
        header_title = QLabel("📊 معاينة ربحية المشروع")
        header_title.setStyleSheet(
            "color: #93C5FD; font-size: 12px; font-weight: bold; background: transparent; padding: 2px 0;"
        )
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
            [
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
            ],
        )
        self.preview_payments_table = payments_section["table"]
        preview_layout.addWidget(payments_section["frame"])

        # === قسم المصروفات المرتبطة ===
        expenses_section = self._create_preview_section(
            "💸 المصروفات المرتبطة",
            ["المبلغ", "الوصف", "التاريخ"],
            [
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.ResizeToContents,
            ],
        )
        self.preview_expenses_table = expenses_section["table"]
        preview_layout.addWidget(expenses_section["frame"])

        # === قسم المهام المرتبطة ===
        tasks_section = self._create_preview_section(
            "📋 المهام المرتبطة",
            ["المهمة", "الأولوية", "الحالة", "الاستحقاق"],
            [
                QHeaderView.ResizeMode.Stretch,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
                QHeaderView.ResizeMode.ResizeToContents,
            ],
            show_add_btn=True,
        )
        self.preview_tasks_table = tasks_section["table"]
        self.add_task_btn = tasks_section.get("add_btn")
        if self.add_task_btn:
            self.add_task_btn.clicked.connect(self._on_add_task_for_project)
        preview_layout.addWidget(tasks_section["frame"])

        # إضافة مساحة مرنة في النهاية
        preview_layout.addStretch()

        preview_scroll.setWidget(self.preview_groupbox)
        self.main_splitter.addWidget(preview_scroll)

        # تعيين النسب الافتراضية للـ splitter (70% للجدول، 30% للمعاينة)
        self.main_splitter.setStretchFactor(0, 7)
        self.main_splitter.setStretchFactor(1, 3)

        # تعيين الحد الأدنى للعرض - زيادة عرض المعاينة
        preview_scroll.setMinimumWidth(280)
        preview_scroll.setMaximumWidth(450)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_projects_data() - يتم استدعاؤها من MainWindow
        self.on_project_selection_changed()

    def resizeEvent(self, event):
        """تغيير اتجاه الـ splitter حسب عرض النافذة"""
        super().resizeEvent(event)
        width = self.width()

        # إذا كان العرض صغير، نحول لعمودي
        if width < 900:
            if self.main_splitter.orientation() != Qt.Orientation.Vertical:
                self.main_splitter.setOrientation(Qt.Orientation.Vertical)
        else:
            if self.main_splitter.orientation() != Qt.Orientation.Horizontal:
                self.main_splitter.setOrientation(Qt.Orientation.Horizontal)

    def create_kpi_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background-color: {color}; border-radius: 6px; }}")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "color: rgba(255,255,255,0.85); font-size: 9px; background: transparent;"
        )
        value_label = QLabel(value)
        value_label.setStyleSheet(
            "color: white; font-weight: bold; font-size: 13px; background: transparent;"
        )
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
            safe_print(f"ERROR: [ProjectManager] فشل تحديث الكارت: {e}")

    def _create_preview_section(
        self, title: str, headers: list, resize_modes: list, show_add_btn: bool = False
    ) -> dict:
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
        title_label.setStyleSheet(
            "color: #93C5FD; font-size: 11px; font-weight: bold; background: transparent;"
        )
        header_layout.addWidget(title_label)
        layout.addLayout(header_layout)

        # الجدول
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS["bg_dark"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                gridline-color: {COLORS["border"]};
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 3px 5px;
                border-bottom: 1px solid rgba(30, 58, 95, 0.3);
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS["primary"]};
            }}
            QHeaderView::section {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS["header_bg"]}, stop:1 #1d4ed8);
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
        from core.context_menu import RightClickBlocker

        # ⚡ تثبيت فلتر لتحديد flag الكليك يمين
        self._right_click_blocker = RightClickBlocker(self.projects_table, self.projects_table)
        self.projects_table.viewport().installEventFilter(self._right_click_blocker)

        self.projects_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.projects_table.customContextMenuRequested.connect(self._show_custom_context_menu)

    def _show_custom_context_menu(self, position):
        """⚡ عرض قائمة السياق"""
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QMenu

        from ui.styles import COLORS

        # الحصول على الصف تحت الماوس
        item = self.projects_table.itemAt(position)
        if not item:
            return

        row = item.row()

        # تحديد الصف وتحديث selected_project
        current_selection = self.projects_table.selectedIndexes()
        current_row = current_selection[0].row() if current_selection else -1

        if current_row != row:
            self.projects_table.selectRow(row)

        # تحديث selected_project يدوياً
        project_name_item = self.projects_table.item(row, 1)
        if project_name_item:
            project_name = project_name_item.text()
            for proj in self.projects_list:
                if proj.name == project_name:
                    self.selected_project = proj
                    break

        # إنشاء القائمة
        menu = QMenu(self.projects_table)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS["bg_medium"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 8px;
                padding: 5px;
            }}
            QMenu::item {{
                background-color: transparent;
                color: {COLORS["text_primary"]};
                padding: 8px 25px 8px 15px;
                border-radius: 4px;
                margin: 2px 5px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS["primary"]};
                color: white;
            }}
        """)

        # إضافة الإجراءات
        view_action = QAction("👁️ عرض التفاصيل", self.projects_table)
        view_action.triggered.connect(self.open_editor_for_selected)
        menu.addAction(view_action)

        edit_action = QAction("✏️ تعديل", self.projects_table)
        edit_action.triggered.connect(self.open_editor_for_selected)
        menu.addAction(edit_action)

        menu.addSeparator()

        payment_action = QAction("💰 إضافة دفعة", self.projects_table)
        payment_action.triggered.connect(self.open_payment_dialog)
        menu.addAction(payment_action)

        profit_action = QAction("📊 عرض الربحية", self.projects_table)
        profit_action.triggered.connect(self._show_profit_dialog)
        menu.addAction(profit_action)

        print_action = QAction("🖨️ طباعة الفاتورة", self.projects_table)
        print_action.triggered.connect(self._print_invoice)
        menu.addAction(print_action)

        menu.addSeparator()

        refresh_action = QAction("🔄 تحديث", self.projects_table)
        refresh_action.triggered.connect(self.load_projects_data)
        menu.addAction(refresh_action)

        # عرض القائمة
        menu.exec(self.projects_table.viewport().mapToGlobal(position))

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
            project = self.project_service.get_project_by_id(project_name)
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
            project = self.project_service.get_project_by_id(project_name)
            if project and hasattr(self, "printing_service") and self.printing_service:
                self.printing_service.print_invoice(project)

    def on_project_selection_changed(self):
        """(معدلة) تملى لوحة المعاينة بكل التفاصيل - ⚡ محسّنة للسرعة"""
        # ⚡ تجاهل التحديث إذا كان الكليك يمين (لمنع التحميل المتكرر)
        from core.context_menu import is_right_click_active

        if is_right_click_active():
            return

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
            self.delete_button.setEnabled(True)
            self.profit_button.setEnabled(True)
            self.payment_button.setEnabled(True)
            self.print_button.setEnabled(True)
            self.preview_template_button.setEnabled(True)  # ✅ تفعيل زرار المعاينة
            self.preview_groupbox.setVisible(True)

            # حفظ ID المشروع للمهام
            project_id_for_tasks = getattr(self.selected_project, "id", None) or getattr(
                self.selected_project, "_mongo_id", project_name
            )

            # ⚡ تحميل البيانات في الخلفية لمنع التجميد
            self._load_preview_data_async(project_name, project_id_for_tasks)

            return

        self.selected_project = None
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.profit_button.setEnabled(False)
        self.payment_button.setEnabled(False)
        self.print_button.setEnabled(False)
        self.preview_template_button.setEnabled(False)  # ✅ تعطيل زرار المعاينة
        self.preview_groupbox.setVisible(False)

    def _load_preview_data_async(self, project_name: str, project_id_for_tasks: str):
        """⚡ تحميل بيانات المعاينة في الخلفية - محسّن للسرعة القصوى"""
        from core.data_loader import get_data_loader

        data_loader = get_data_loader()

        # ⚡ تحميل كل البيانات في طلب واحد (أسرع)
        def fetch_all_data():
            profit_data = self.project_service.get_project_profitability(project_name)
            payments = self.project_service.get_payments_for_project(project_name)
            expenses = self.project_service.get_expenses_for_project(project_name)

            # 🔍 Debug: طباعة عدد الدفعات
            safe_print(
                f"DEBUG: [ProjectManager] تم جلب {len(payments) if payments else 0} دفعة للمشروع {project_name}"
            )
            if payments:
                for i, pay in enumerate(payments):
                    safe_print(
                        f"  - دفعة {i + 1}: {pay.amount:,.2f} ج.م في {pay.date} (حساب: {pay.account_id})"
                    )

            # جلب المهام
            tasks = []
            try:
                from ui.todo_manager import TaskService

                task_service = TaskService()
                tasks = task_service.get_tasks_by_project(str(project_id_for_tasks))
            except Exception:
                pass

            return {
                "profit": profit_data,
                "payments": payments,
                "expenses": expenses,
                "tasks": tasks,
            }

        def on_all_data_loaded(data):
            # التحقق أن المشروع لا يزال محدداً
            if not self.selected_project or self.selected_project.name != project_name:
                return

            # تحديث الكروت
            profit_data = data.get("profit", {})
            self.update_card_value(self.revenue_card, profit_data.get("total_revenue", 0))
            self.update_card_value(self.paid_card, profit_data.get("total_paid", 0))
            self.update_card_value(self.due_card, profit_data.get("balance_due", 0))

            # تحديث الجداول
            payments_data = data.get("payments", [])
            safe_print(
                f"DEBUG: [ProjectManager] جاري عرض {len(payments_data) if payments_data else 0} دفعة في الجدول"
            )
            self._populate_payments_table(payments_data)
            self._populate_expenses_table(data.get("expenses", []))
            self._populate_tasks_table(data.get("tasks", []))

        data_loader.load_async(
            operation_name=f"preview_{project_name}",
            load_function=fetch_all_data,
            on_success=on_all_data_loaded,
            use_thread_pool=True,
        )

    def _populate_payments_table(self, payments):
        """⚡ ملء جدول الدفعات - محسّن مع عرض اسم الحساب"""
        try:
            safe_print(
                f"DEBUG: [_populate_payments_table] بدء ملء الجدول بـ {len(payments) if payments else 0} دفعة"
            )
            safe_print(
                f"DEBUG: [_populate_payments_table] عدد الأعمدة في الجدول: {self.preview_payments_table.columnCount()}"
            )
            safe_print(
                f"DEBUG: [_populate_payments_table] أسماء الأعمدة: {[self.preview_payments_table.horizontalHeaderItem(i).text() for i in range(self.preview_payments_table.columnCount())]}"
            )

            # ⚡ تعطيل التحديثات أثناء الملء للسرعة
            self.preview_payments_table.setUpdatesEnabled(False)

            # ⚡ إزالة كل الـ spans القديمة - يجب إزالتها من الخلية الأصلية فقط!
            old_row_count = self.preview_payments_table.rowCount()
            old_col_count = self.preview_payments_table.columnCount()
            processed_spans = set()

            safe_print("DEBUG: [_populate_payments_table] إزالة الـ spans القديمة...")
            for row in range(old_row_count):
                for col in range(old_col_count):
                    if (row, col) in processed_spans:
                        continue

                    row_span = self.preview_payments_table.rowSpan(row, col)
                    col_span = self.preview_payments_table.columnSpan(row, col)

                    if row_span > 1 or col_span > 1:
                        safe_print(
                            f"DEBUG: [_populate_payments_table] صف {row}, عمود {col} كان له span: {row_span}×{col_span}"
                        )
                        self.preview_payments_table.setSpan(row, col, 1, 1)

                        # نضيف كل الخلايا المتأثرة بالـ span للقائمة
                        for r in range(row, row + row_span):
                            for c in range(col, col + col_span):
                                processed_spans.add((r, c))

            # ⚡ مسح الجدول
            self.preview_payments_table.clearContents()
            self.preview_payments_table.setRowCount(0)
            safe_print("DEBUG: [_populate_payments_table] تم مسح الجدول")

            if payments and len(payments) > 0:
                # ⚡ تعيين عدد الصفوف مرة واحدة
                self.preview_payments_table.setRowCount(len(payments))
                safe_print(f"DEBUG: [_populate_payments_table] تم تعيين {len(payments)} صف")

                for i, pay in enumerate(payments):
                    safe_print(
                        f"DEBUG: [_populate_payments_table] دفعة {i + 1}: amount={pay.amount}, date={pay.date}, account={pay.account_id}"
                    )

                    # معالجة التاريخ بأمان
                    try:
                        if hasattr(pay.date, "strftime"):
                            date_str = pay.date.strftime("%Y-%m-%d")
                        else:
                            date_str = str(pay.date)[:10]
                    except (AttributeError, ValueError, TypeError):
                        date_str = "N/A"

                    # ⚡ عرض اسم الحساب الفعلي بدلاً من الكود
                    account_name = "نقدي"
                    if pay.account_id:
                        try:
                            account = self.accounting_service.repo.get_account_by_code(
                                pay.account_id
                            )
                            if account:
                                account_name = account.name
                                safe_print(
                                    f"DEBUG: [_populate_payments_table] اسم الحساب: {account_name}"
                                )
                            else:
                                account_name = str(pay.account_id)
                                safe_print(
                                    f"DEBUG: [_populate_payments_table] لم يتم العثور على الحساب، استخدام الكود: {account_name}"
                                )
                        except Exception as e:
                            account_name = str(pay.account_id)
                            safe_print(f"DEBUG: [_populate_payments_table] خطأ في جلب الحساب: {e}")

                    # ترتيب الأعمدة: [الحساب, المبلغ, التاريخ]
                    account_item = QTableWidgetItem(account_name)
                    account_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    account_item.setFont(get_cairo_font(9))  # ⚡ تصغير الخط من 11 إلى 9
                    self.preview_payments_table.setItem(i, 0, account_item)
                    safe_print(f"DEBUG: [_populate_payments_table] عمود 0 (الحساب): {account_name}")

                    amount_item = QTableWidgetItem(f"{pay.amount:,.2f} ج.م")
                    amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    amount_item.setForeground(QColor("#10b981"))
                    amount_item.setFont(get_cairo_font(9, bold=True))  # ⚡ تصغير الخط من 11 إلى 9
                    self.preview_payments_table.setItem(i, 1, amount_item)
                    safe_print(
                        f"DEBUG: [_populate_payments_table] عمود 1 (المبلغ): {pay.amount:,.2f} ج.م"
                    )

                    date_item = QTableWidgetItem(date_str)
                    date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    date_item.setFont(get_cairo_font(9))  # ⚡ تصغير الخط من 10 إلى 9
                    self.preview_payments_table.setItem(i, 2, date_item)
                    safe_print(f"DEBUG: [_populate_payments_table] عمود 2 (التاريخ): {date_str}")

                # ⚡ التحقق من البيانات بعد الملء
                safe_print("\nDEBUG: [_populate_payments_table] التحقق من البيانات بعد الملء:")
                for row in range(min(3, self.preview_payments_table.rowCount())):  # أول 3 صفوف فقط
                    safe_print(f"  صف {row}:")
                    for col in range(self.preview_payments_table.columnCount()):
                        item = self.preview_payments_table.item(row, col)
                        span = (
                            self.preview_payments_table.rowSpan(row, col),
                            self.preview_payments_table.columnSpan(row, col),
                        )
                        if item:
                            safe_print(f"    عمود {col}: '{item.text()}' | span: {span}")
                        else:
                            safe_print(f"    عمود {col}: فارغ | span: {span}")

                safe_print(
                    f"SUCCESS: [_populate_payments_table] تم عرض {len(payments)} دفعة في الجدول"
                )
            else:
                # إضافة صف يوضح عدم وجود دفعات
                self.preview_payments_table.setRowCount(1)
                no_data_item = QTableWidgetItem("لا توجد دفعات مسجلة")
                no_data_item.setForeground(QColor("#6B7280"))
                no_data_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                no_data_item.setFont(get_cairo_font(11))
                self.preview_payments_table.setItem(0, 0, no_data_item)
                self.preview_payments_table.setSpan(0, 0, 1, 3)
                safe_print("DEBUG: [_populate_payments_table] لا توجد دفعات لعرضها")

        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل ملء جدول الدفعات: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # ⚡ إعادة تفعيل التحديثات
            self.preview_payments_table.setUpdatesEnabled(True)

    def _populate_expenses_table(self, expenses):
        """⚡ ملء جدول المصروفات - محسّن"""
        try:
            # ⚡ تعطيل التحديثات أثناء الملء للسرعة
            self.preview_expenses_table.setUpdatesEnabled(False)

            # ⚡ إزالة كل الـ spans القديمة - يجب إزالتها من الخلية الأصلية فقط!
            old_row_count = self.preview_expenses_table.rowCount()
            old_col_count = self.preview_expenses_table.columnCount()
            safe_print(
                f"DEBUG: [_populate_expenses_table] الجدول القديم: {old_row_count} صف × {old_col_count} عمود"
            )

            # نتتبع الخلايا اللي تم معالجتها عشان منكررش
            processed_spans = set()

            for row in range(old_row_count):
                for col in range(old_col_count):
                    if (row, col) in processed_spans:
                        continue

                    row_span = self.preview_expenses_table.rowSpan(row, col)
                    col_span = self.preview_expenses_table.columnSpan(row, col)

                    if row_span > 1 or col_span > 1:
                        safe_print(
                            f"DEBUG: [_populate_expenses_table] إزالة span من صف {row}, عمود {col}: {row_span}×{col_span}"
                        )
                        self.preview_expenses_table.setSpan(row, col, 1, 1)

                        # نضيف كل الخلايا المتأثرة بالـ span للقائمة
                        for r in range(row, row + row_span):
                            for c in range(col, col + col_span):
                                processed_spans.add((r, c))

            # ⚡ مسح الجدول بالكامل
            self.preview_expenses_table.setRowCount(0)
            self.preview_expenses_table.clearContents()
            safe_print("DEBUG: [_populate_expenses_table] تم مسح الجدول")

            if expenses and len(expenses) > 0:
                # ⚡ تعيين عدد الصفوف مرة واحدة
                self.preview_expenses_table.setRowCount(len(expenses))

                for i, exp in enumerate(expenses):
                    # معالجة التاريخ بأمان
                    try:
                        if hasattr(exp.date, "strftime"):
                            date_str = exp.date.strftime("%Y-%m-%d")
                        else:
                            date_str = str(exp.date)[:10]
                    except (AttributeError, ValueError, TypeError):
                        date_str = "N/A"

                    # ترتيب الأعمدة: [المبلغ, الوصف, التاريخ]
                    amount_item = QTableWidgetItem(f"{exp.amount:,.2f}")
                    amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    amount_item.setForeground(QColor("#ef4444"))
                    amount_item.setFont(get_cairo_font(9))  # ⚡ إضافة خط أصغر
                    self.preview_expenses_table.setItem(i, 0, amount_item)

                    desc_item = QTableWidgetItem(exp.description or exp.category or "-")
                    desc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    desc_item.setFont(get_cairo_font(9))  # ⚡ إضافة خط أصغر
                    self.preview_expenses_table.setItem(i, 1, desc_item)

                    date_item = QTableWidgetItem(date_str)
                    date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    date_item.setFont(get_cairo_font(9))  # ⚡ إضافة خط أصغر
                    self.preview_expenses_table.setItem(i, 2, date_item)

                # ⚡ التحقق من البيانات بعد الملء
                safe_print("\nDEBUG: [_populate_expenses_table] التحقق من البيانات بعد الملء:")
                for row in range(min(3, self.preview_expenses_table.rowCount())):
                    safe_print(f"  صف {row}:")
                    for col in range(self.preview_expenses_table.columnCount()):
                        item = self.preview_expenses_table.item(row, col)
                        span = (
                            self.preview_expenses_table.rowSpan(row, col),
                            self.preview_expenses_table.columnSpan(row, col),
                        )
                        if item:
                            safe_print(f"    عمود {col}: '{item.text()}' | span: {span}")
                        else:
                            safe_print(f"    عمود {col}: فارغ | span: {span}")
                safe_print(
                    f"SUCCESS: [_populate_expenses_table] تم عرض {len(expenses)} مصروف في الجدول"
                )
            else:
                # إضافة صف يوضح عدم وجود مصروفات
                self.preview_expenses_table.setRowCount(1)
                no_data_item = QTableWidgetItem("لا توجد مصروفات مسجلة")
                no_data_item.setForeground(QColor("gray"))
                no_data_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.preview_expenses_table.setItem(0, 0, no_data_item)
                self.preview_expenses_table.setSpan(0, 0, 1, 3)

        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل ملء جدول المصروفات: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # ⚡ إعادة تفعيل التحديثات
            self.preview_expenses_table.setUpdatesEnabled(True)

    def _populate_tasks_table(self, tasks):
        """⚡ ملء جدول المهام - محسّن للسرعة"""
        try:
            # ⚡ إزالة كل الـ spans القديمة - يجب إزالتها من الخلية الأصلية فقط!
            old_row_count = self.preview_tasks_table.rowCount()
            old_col_count = self.preview_tasks_table.columnCount()
            processed_spans = set()

            for row in range(old_row_count):
                for col in range(old_col_count):
                    if (row, col) in processed_spans:
                        continue

                    row_span = self.preview_tasks_table.rowSpan(row, col)
                    col_span = self.preview_tasks_table.columnSpan(row, col)

                    if row_span > 1 or col_span > 1:
                        self.preview_tasks_table.setSpan(row, col, 1, 1)

                        # نضيف كل الخلايا المتأثرة بالـ span للقائمة
                        for r in range(row, row + row_span):
                            for c in range(col, col + col_span):
                                processed_spans.add((r, c))

            # ⚡ مسح الجدول
            self.preview_tasks_table.clearContents()
            self.preview_tasks_table.setRowCount(0)

            if tasks and len(tasks) > 0:
                # ⚡ تعيين عدد الصفوف مرة واحدة
                self.preview_tasks_table.setRowCount(len(tasks))

                for i, task in enumerate(tasks):
                    # عنوان المهمة
                    self.preview_tasks_table.setItem(i, 0, QTableWidgetItem(task.title))

                    # الأولوية
                    priority_item = QTableWidgetItem(task.priority.value)
                    priority_colors = {
                        "منخفضة": QColor("#10B981"),
                        "متوسطة": QColor("#0A6CF1"),
                        "عالية": QColor("#FF6636"),
                        "عاجلة": QColor("#FF4FD8"),
                    }
                    priority_item.setForeground(
                        priority_colors.get(task.priority.value, QColor("white"))
                    )
                    self.preview_tasks_table.setItem(i, 1, priority_item)

                    # الحالة
                    status_item = QTableWidgetItem(task.status.value)
                    status_colors = {
                        "قيد الانتظار": QColor("#B0C4DE"),
                        "قيد التنفيذ": QColor("#FF6636"),
                        "مكتملة": QColor("#10B981"),
                        "ملغاة": QColor("#FF4FD8"),
                    }
                    status_item.setForeground(status_colors.get(task.status.value, QColor("white")))
                    self.preview_tasks_table.setItem(i, 2, status_item)

                    # تاريخ الاستحقاق
                    due_str = task.due_date.strftime("%Y-%m-%d") if task.due_date else "-"
                    self.preview_tasks_table.setItem(i, 3, QTableWidgetItem(due_str))
            else:
                self.preview_tasks_table.setRowCount(1)
                no_data_item = QTableWidgetItem("لا توجد مهام مرتبطة")
                no_data_item.setForeground(QColor("gray"))
                self.preview_tasks_table.setItem(0, 0, no_data_item)
                self.preview_tasks_table.setSpan(0, 0, 1, 4)

        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل ملء جدول المهام: {e}")

    def load_projects_data(self):
        """⚡ تحميل بيانات المشاريع في الخلفية لمنع التجميد"""
        safe_print("INFO: [ProjectManager] جاري تحميل بيانات المشاريع...")

        from core.data_loader import get_data_loader

        # تحضير الجدول
        self.projects_table.setSortingEnabled(False)
        self.projects_table.setUpdatesEnabled(False)
        self.projects_table.blockSignals(True)
        self.projects_table.setRowCount(0)

        # دالة جلب البيانات (تعمل في الخلفية)
        def fetch_projects():
            try:
                if self.show_archived_checkbox.isChecked():
                    return self.project_service.get_archived_projects()
                else:
                    return self.project_service.get_all_projects()
            except Exception as e:
                safe_print(f"ERROR: [ProjectManager] فشل جلب المشاريع: {e}")
                return []

        # دالة تحديث الواجهة (تعمل على main thread)
        def on_data_loaded(projects):
            try:
                self.projects_list = projects

                # ⚡ مسح الجدول قبل إضافة البيانات الجديدة (لمنع التكرار)
                self.projects_table.setRowCount(0)

                # إنشاء العناصر مع محاذاة للوسط
                def create_centered_item(text):
                    item = QTableWidgetItem(str(text) if text else "")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    return item

                # ⚡ تحميل كل البيانات دفعة واحدة (أسرع)
                self.projects_table.setRowCount(len(self.projects_list))
                for row, project in enumerate(self.projects_list):
                    # ⚡ جلب رقم الفاتورة مباشرة من المشروع
                    invoice_number = getattr(project, "invoice_number", None) or ""

                    self.projects_table.setItem(row, 0, create_centered_item(invoice_number))
                    self.projects_table.setItem(row, 1, create_centered_item(project.name))
                    self.projects_table.setItem(row, 2, create_centered_item(project.client_id))
                    self.projects_table.setItem(row, 3, create_centered_item(project.status.value))
                    self.projects_table.setItem(
                        row, 4, create_centered_item(self._format_date(project.start_date))
                    )

                # إعادة تفعيل الجدول
                self.projects_table.blockSignals(False)
                self.projects_table.setUpdatesEnabled(True)
                self.projects_table.setSortingEnabled(True)

                self.on_project_selection_changed()

                # ⚡ تحديث ملخص الفواتير
                self._update_invoices_summary()

                safe_print(f"INFO: [ProjectManager] ✅ تم تحميل {len(projects)} مشروع")

            except Exception as e:
                safe_print(f"ERROR: [ProjectManager] فشل تحديث الجدول: {e}")
                import traceback

                traceback.print_exc()
                # إعادة تفعيل الجدول حتى في حالة الخطأ
                self.projects_table.blockSignals(False)
                self.projects_table.setUpdatesEnabled(True)
                self.projects_table.setSortingEnabled(True)

        def on_error(error_msg):
            safe_print(f"ERROR: [ProjectManager] فشل تحميل المشاريع: {error_msg}")
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
            use_thread_pool=True,
        )

    def _on_projects_changed(self):
        """⚡ استجابة لإشارة تحديث المشاريع - تحديث الجدول أوتوماتيك"""
        safe_print("INFO: [ProjectManager] ⚡ استلام إشارة تحديث المشاريع - جاري التحديث...")
        # ⚡ إبطال الـ cache أولاً لضمان جلب البيانات الجديدة من السيرفر
        if hasattr(self.project_service, "invalidate_cache"):
            self.project_service.invalidate_cache()
        self.load_projects_data()

    def _update_invoices_summary(self):
        """⚡ تحديث ملخص الفواتير (العدد والإجمالي)"""
        try:
            invoices_count = len(self.projects_list) if hasattr(self, "projects_list") else 0
            invoices_total = 0.0

            # حساب إجمالي مبالغ الفواتير من المشاريع
            for project in self.projects_list:
                invoices_total += getattr(project, "total_amount", 0) or 0

            # تحديث الـ labels
            if hasattr(self, "invoices_count_label"):
                self.invoices_count_label.setText(f"📄 عدد الفواتير: {invoices_count}")
            if hasattr(self, "invoices_total_label"):
                self.invoices_total_label.setText(f"💰 إجمالي الفواتير: {invoices_total:,.2f} جنيه")

            safe_print(
                f"INFO: [ProjectManager] ملخص الفواتير: {invoices_count} فاتورة بإجمالي {invoices_total:,.2f}"
            )
        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل تحديث ملخص الفواتير: {e}")

    def _load_project_tasks(self, project_id: str):
        """تحميل المهام المرتبطة بالمشروع (متزامن - للاستخدام بعد إضافة مهمة)"""
        try:
            from ui.todo_manager import TaskService

            task_service = TaskService()
            tasks = task_service.get_tasks_by_project(str(project_id))
            self._populate_tasks_table(tasks)
        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل تحميل المهام: {e}")
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
            project_id = getattr(self.selected_project, "id", None) or getattr(
                self.selected_project, "_mongo_id", self.selected_project.name
            )

            dialog = TaskEditorDialog(
                parent=self,
                project_service=self.project_service,
                client_service=self.client_service,
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
                    safe_print(f"INFO: [ProjectManager] تم إضافة مهمة للمشروع: {task.title}")

        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل إضافة مهمة: {e}")
            QMessageBox.warning(self, "خطأ", f"فشل إضافة المهمة: {str(e)}")

    def _format_date(self, value) -> str:
        if not value:
            return "-"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, str):
            try:
                # محاولة تحليل التاريخ من النص
                if "T" in value:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                else:
                    parsed = datetime.strptime(value[:10], "%Y-%m-%d")
                return parsed.strftime("%Y-%m-%d")
            except (ValueError, TypeError, AttributeError):
                return value[:10] if len(value) >= 10 else value
        return str(value)

    def open_editor(self, project_to_edit: schemas.Project | None = None):
        """(معدلة) يفتح نافذة الحوار ويمرر "قسم المحاسبة" """
        dialog = ProjectEditorDialog(
            project_service=self.project_service,
            client_service=self.client_service,
            service_service=self.service_service,
            accounting_service=self.accounting_service,
            project_to_edit=project_to_edit,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_projects_data()

    def open_editor_for_selected(self):
        if not self.selected_project:
            QMessageBox.information(self, "تنبيه", "الرجاء اختيار مشروع أولاً")
            return
        self.open_editor(self.selected_project)

    def delete_selected_project(self):
        """🗑️ حذف المشروع المحدد"""
        if not self.selected_project:
            QMessageBox.information(self, "تنبيه", "الرجاء اختيار مشروع أولاً")
            return

        project_name = self.selected_project.name

        # تأكيد الحذف
        reply = QMessageBox.warning(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف المشروع:\n\n{project_name}\n\n⚠️ سيتم حذف جميع البيانات المرتبطة بالمشروع!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # حذف المشروع باستخدام الاسم مباشرة
            safe_print(f"INFO: [ProjectManager] جاري حذف المشروع: {project_name}")
            success = self.project_service.delete_project(project_name)

            if success:
                self.selected_project = None
                self.load_projects_data()
            else:
                notify_error("فشل حذف المشروع", "خطأ")

        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل حذف المشروع: {e}")
            import traceback

            traceback.print_exc()
            notify_error(f"فشل حذف المشروع: {e}", "خطأ")

    def open_payment_dialog(self):
        """فتح نافذة تسجيل دفعة جديدة للمشروع المحدد"""
        if not self.selected_project:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مشروع أولاً.")
            return

        safe_print(f"INFO: [ProjectManager] فتح شاشة تسجيل دفعة لـ: {self.selected_project.name}")

        from ui.payment_dialog import PaymentDialog

        # جلب حسابات البنك/الخزينة فقط (الخزينة والمحافظ الإلكترونية)
        all_accounts = self.accounting_service.repo.get_all_accounts()
        cash_accounts = [
            acc
            for acc in all_accounts
            if acc.type == schemas.AccountType.CASH
            or (acc.code and acc.code.startswith("111"))  # الخزينة 111x
            or (acc.code and acc.code.startswith("12"))  # المحافظ الإلكترونية 12xx
        ]

        if not cash_accounts:
            QMessageBox.critical(
                self,
                "خطأ إعداد",
                "لم يتم العثور على حسابات بنك أو خزينة.\n\n"
                "يرجى إضافة حسابات نقدية (كود يبدأ بـ 11 أو 12) أولاً.",
            )
            return

        dialog = PaymentDialog(
            project=self.selected_project,
            accounts=cash_accounts,
            project_service=self.project_service,
            parent=self,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            safe_print("INFO: [ProjectManager] تم تسجيل الدفعة بنجاح. جاري تحديث البيانات...")
            self.on_project_selection_changed()  # تحديث لوحة المعاينة

    def open_profit_dialog(self):
        """
        عرض تقرير ربحية المشروع بالتفصيل (إيرادات، مصروفات، صافي الربح)
        """
        if not self.selected_project:
            QMessageBox.warning(self, "خطأ", "يرجى تحديد مشروع أولاً.")
            return

        safe_print(f"INFO: [ProjectManager] فتح تقرير ربحية المشروع: {self.selected_project.name}")

        from ui.project_profit_dialog import ProjectProfitDialog

        dialog = ProjectProfitDialog(
            project=self.selected_project, project_service=self.project_service, parent=self
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
            safe_print(f"INFO: [ProjectManager] الدفعات المرسلة للطباعة: {payments_list}")

            # تجهيز معلومات العميل
            client_info = {
                "name": client.name,
                "company_name": getattr(client, "company_name", "") or "",
                "phone": client.phone or "---",
                "email": client.email or "",
                "address": client.address or "---",
            }

            # ⚡ استخدام template_service
            if self.template_service:
                safe_print("INFO: [ProjectManager] استخدام template_service للطباعة")

                success = self.template_service.preview_template(
                    project=project, client_info=client_info, payments=payments_list
                )

                if success:
                    QMessageBox.information(
                        self,
                        "✅ تم إنشاء الفاتورة",
                        "تم فتح معاينة الفاتورة في المتصفح.\n\nيمكنك طباعتها من المتصفح (Ctrl+P)",
                    )
                else:
                    QMessageBox.critical(self, "خطأ", "فشل في إنشاء الفاتورة")
                return

            # Fallback: استخدام InvoicePrintingService
            profit_data = self.project_service.get_project_profitability(project.name)

            # Fallback: استخدام InvoicePrintingService
            # Step D: Prepare the complete data dictionary
            # ⚡ استخدم رقم الفاتورة المحفوظ أولاً، وإلا ولّد رقم جديد
            invoice_number = getattr(project, "invoice_number", None)
            if not invoice_number:
                local_id = getattr(project, "id", None) or 1
                invoice_number = f"SW-{97161 + int(local_id)}"

            invoice_data = {
                "invoice_number": invoice_number,
                "invoice_date": project.start_date.strftime("%Y-%m-%d")
                if hasattr(project, "start_date") and project.start_date
                else datetime.now().strftime("%Y-%m-%d"),
                "due_date": project.end_date.strftime("%Y-%m-%d")
                if hasattr(project, "end_date") and project.end_date
                else datetime.now().strftime("%Y-%m-%d"),
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
                        "total": float(item.total),
                    }
                    for item in project.items
                ],
                # حساب المجموع الفرعي من البنود (مع الخصومات)
                "subtotal": sum([float(item.total) for item in project.items]),
                "grand_total": float(project.total_amount),
                "total_paid": float(profit_data.get("total_paid", 0)),
                "remaining_amount": float(profit_data.get("balance_due", 0)),
                "remaining": float(profit_data.get("balance_due", 0)),
                "total_amount": float(project.total_amount),
                "payments": payments_list,
            }

            # Step E: Use InvoicePrintingService to generate and open PDF
            from services.invoice_printing_service import InvoicePrintingService

            # Get settings service for company data
            settings_service = None
            if self.service_service and hasattr(self.service_service, "settings_service"):
                settings_service = self.service_service.settings_service

            # Initialize printing service
            printing_service = InvoicePrintingService(settings_service=settings_service)

            # Print invoice (generates PDF and opens it automatically)
            pdf_path = printing_service.print_invoice(invoice_data)

            if pdf_path:
                if pdf_path.endswith(".pdf"):
                    QMessageBox.information(
                        self,
                        "✅ تم إنشاء الفاتورة",
                        f"تم إنشاء فاتورة PDF بنجاح!\n\n📄 {os.path.basename(pdf_path)}\n\n"
                        f"تم فتح الملف تلقائياً للطباعة.",
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
                        f"أو استخدم Google Chrome/Edge",
                    )
            else:
                QMessageBox.critical(self, "خطأ", "فشل في إنشاء الفاتورة")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في طباعة الفاتورة:\n{str(e)}")
            import traceback

            traceback.print_exc()

    def _get_payments_list(self, project_name: str) -> list:
        """جلب قائمة الدفعات للمشروع - محسّن للسرعة"""
        payments_list = []
        try:
            payments = self.project_service.get_payments_for_project(project_name)
            if not payments:
                return []

            # ⚡ تخزين الحسابات مؤقتاً لتجنب الاستعلامات المتكررة
            accounts_cache = {}

            for payment in payments:
                account_name = "نقدي"
                account_id = getattr(payment, "account_id", None)

                if account_id:
                    # ⚡ استخدام الكاش
                    if account_id in accounts_cache:
                        account_name = accounts_cache[account_id]
                    else:
                        try:
                            account = self.accounting_service.repo.get_account_by_code(account_id)
                            if not account:
                                account = self.accounting_service.repo.get_account_by_id(account_id)
                            account_name = account.name if account else str(account_id)
                            accounts_cache[account_id] = account_name
                        except Exception:
                            account_name = str(account_id)
                            accounts_cache[account_id] = account_name

                # تحويل التاريخ
                payment_date = payment.date
                if hasattr(payment_date, "strftime"):
                    date_str = payment_date.strftime("%Y-%m-%d")
                else:
                    date_str = str(payment_date)[:10] if payment_date else ""

                payments_list.append(
                    {
                        "date": date_str,
                        "amount": float(payment.amount) if payment.amount else 0.0,
                        "method": getattr(payment, "method", account_name),
                        "account_name": account_name,
                        "account_id": str(account_id) if account_id else "",
                    }
                )

        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل جلب الدفعات: {e}")

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
            safe_print(f"INFO: [ProjectManager] الدفعات المرسلة للقالب: {payments_list}")

            # تجهيز معلومات العميل
            client_info = {
                "name": client.name,
                "company_name": getattr(client, "company_name", "") or "",
                "phone": client.phone or "---",
                "email": client.email or "",
                "address": client.address or "---",
            }

            # استخدام template_service للمعاينة
            if self.template_service:
                success = self.template_service.preview_template(
                    project=project, client_info=client_info, payments=payments_list
                )

                if success:
                    QMessageBox.information(
                        self,
                        "✅ معاينة الفاتورة",
                        "تم فتح معاينة الفاتورة في المتصفح.\n\nيمكنك طباعتها من المتصفح (Ctrl+P)",
                    )
                else:
                    QMessageBox.critical(self, "خطأ", "فشل في معاينة الفاتورة")
            else:
                QMessageBox.warning(self, "خطأ", "خدمة القوالب غير متوفرة")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في معاينة الفاتورة:\n{str(e)}")
            import traceback

            traceback.print_exc()
