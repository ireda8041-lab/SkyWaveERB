from typing import Any

from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtGui import QCloseEvent, QKeySequence, QResizeEvent, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.accounting_service import AccountingService
from ui.custom_spinbox import CustomSpinBox
from ui.smart_combobox import SmartFilterComboBox

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


MANUAL_CASHBOX_PRESET_ID = "manual"
CASHBOX_PRESETS = (
    {
        "id": MANUAL_CASHBOX_PRESET_ID,
        "label": "إعداد يدوي / مخصص",
    },
    {
        "id": "vodafone_cash_hazem",
        "label": "111001 - VF Cash - Hazem",
        "code": "111001",
        "name": "VF Cash - Hazem",
        "treasury_type": "محفظة إلكترونية",
        "details": "01067894321 - حازم اشرف",
        "notes": "خط تحصيل فودافون كاش",
    },
    {
        "id": "vodafone_cash_reda",
        "label": "111002 - VF Cash - Reda",
        "code": "111002",
        "name": "VF Cash - Reda",
        "treasury_type": "محفظة إلكترونية",
        "details": "01021965200 - رضا سامي",
        "notes": "خط تحصيل فودافون كاش",
    },
    {
        "id": "instapay",
        "label": "111003 - InstaPay",
        "code": "111003",
        "name": "InstaPay",
        "treasury_type": "إنستا باي",
        "details": "01067894321 - حازم اشرف\nskywaveads@instapay",
        "notes": "قناة تحصيل إنستا باي",
    },
    {
        "id": "bank_misr_local",
        "label": "111004 - Bank Misr Local",
        "code": "111004",
        "name": "Bank Misr Local",
        "treasury_type": "تحويل بنكي داخل مصر",
        "details": "رقم الحساب: 2630333000086626\nSWIFT CODE: BMISEGCXXXX",
        "notes": "تحويل بنكي داخل مصر - بنك مصر",
    },
    {
        "id": "bank_misr_international",
        "label": "111005 - Bank Misr Intl",
        "code": "111005",
        "name": "Bank Misr Intl",
        "treasury_type": "تحويل بنكي دولي",
        "details": "IBAN: EG020002026302630333000086626\nSWIFT CODE: BMISEGCXXXX",
        "notes": "تحويل بنكي من خارج مصر - بنك مصر",
    },
    {
        "id": "cash_payment",
        "label": "111006 - Cash",
        "code": "111006",
        "name": "Cash",
        "treasury_type": "خزنة نقدية",
        "details": "الخزنة النقدية - مقر الشركة\nالمسؤول: أمين الخزنة",
        "notes": "تحصيل نقدي مباشر داخل مقر الشركة",
    },
)


class AccountEditorDialog(QDialog):
    """
    نافذة إضافة/تعديل حساب - Standard Form Layout
    الحقول: Code, Name, Type, Parent Account, Currency, Opening Balance, Description, Active
    """

    def __init__(
        self,
        accounting_service: AccountingService,
        all_accounts: list[schemas.Account],
        account_to_edit: schemas.Account | None = None,
        cash_only: bool = False,
        parent=None,
    ):
        super().__init__(parent)

        self.accounting_service = accounting_service
        self.all_accounts = all_accounts
        self.account_to_edit = account_to_edit
        self.is_editing = account_to_edit is not None
        self.cash_only = cash_only
        self._body_layout_compact: bool | None = None
        self._applying_cashbox_preset = False
        self._initializing_ui = True
        self.cashbox_preset_buttons: dict[str, QPushButton] = {}
        self._keyboard_shortcuts: list[QShortcut] = []

        if self.is_editing and account_to_edit is not None:
            self.setWindowTitle(
                f"تعديل خزنة: {account_to_edit.name}"
                if self.cash_only
                else f"تعديل حساب: {account_to_edit.name}"
            )
        else:
            self.setWindowTitle("إضافة خزنة جديدة" if self.cash_only else "إضافة حساب جديد")

        # تصميم متجاوب - حد أدنى وأقصى
        self.setMinimumWidth(620 if self.cash_only else 540)
        self.setMinimumHeight(520)
        self.setMaximumHeight(760)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar

        setup_custom_title_bar(self)

        # إزالة الإطار البرتقالي نهائياً من جميع العناصر
        self.setStyleSheet(
            """
            * {
                outline: none;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
            QPushButton:focus, QCheckBox:focus, QRadioButton:focus {
                border: none;
                outline: none;
            }
        """
        )

        self.init_ui()

        # ⚡ تطبيق الستايلات المتجاوبة
        from ui.styles import setup_auto_responsive_dialog

        setup_auto_responsive_dialog(self)
        self._initializing_ui = False
        self._finalize_initial_state()

    def init_ui(self):
        """إنشاء واجهة المستخدم مع تحسينات خاصة بالخزن والحسابات."""
        from ui.styles import BUTTON_STYLES, COLORS, RESPONSIVE_GROUPBOX_STYLE, get_cairo_font

        entity_label = "الخزنة" if self.cash_only else "الحساب"
        entity_name_label = "اسم الخزنة" if self.cash_only else "اسم الحساب"
        entity_code_label = "رمز الخزنة" if self.cash_only else "كود الحساب"
        parent_label = "الفئة الرئيسية" if self.cash_only else "الحساب الأب"
        entity_title = "بيانات الخزنة" if self.cash_only else "بيانات الحساب"
        mode_label = "تعديل" if self.is_editing else "إضافة جديدة"
        flow_label = "خزنة تشغيلية" if self.cash_only else "عنصر في شجرة الحسابات"
        subtitle_text = (
            "أدخل تعريف الخزنة وربطها المحاسبي، واختر قالبًا جاهزًا عند الحاجة لتعبئة بيانات التحصيل الحالية بسرعة."
            if self.cash_only
            else "أدخل تعريف الحساب وموقعه في الشجرة والبيانات الأساسية المرتبطة به."
        )

        summary_card_style = """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(10, 33, 60, 0.92), stop:1 rgba(5, 20, 36, 0.95));
                border: 1px solid rgba(74, 144, 226, 0.25);
                border-radius: 14px;
            }
        """
        spotlight_card_style = """
            QFrame {
                background: rgba(15, 43, 78, 0.88);
                border: 1px solid rgba(96, 165, 250, 0.20);
                border-radius: 14px;
            }
        """
        badge_style = """
            QLabel {
                background: rgba(37, 99, 235, 0.18);
                color: #93c5fd;
                border: 1px solid rgba(59, 130, 246, 0.35);
                border-radius: 10px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
        """
        helper_style = "color: #94a3b8; font-size: 11px; line-height: 1.5;"
        row_label_style = "color: #94a3b8; font-size: 11px; font-weight: bold;"
        row_value_style = (
            "color: #f8fafc; font-size: 13px; font-weight: bold; font-family: 'Cairo';"
        )
        preset_button_style = """
            QPushButton {
                background: rgba(10, 30, 52, 0.94);
                color: #dbeafe;
                border: 1px solid rgba(59, 130, 246, 0.16);
                border-radius: 12px;
                padding: 10px 12px;
                min-height: 58px;
                text-align: right;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid rgba(96, 165, 250, 0.38);
                background: rgba(14, 50, 90, 0.96);
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(16, 86, 190, 0.98), stop:1 rgba(9, 59, 143, 0.98));
                color: white;
                border: 1px solid rgba(191, 219, 254, 0.44);
            }
        """
        metric_tile_style = """
            QFrame {
                background: rgba(13, 36, 64, 0.88);
                border: 1px solid rgba(71, 85, 105, 0.30);
                border-radius: 12px;
            }
        """
        preview_card_style = """
            QFrame {
                background: rgba(8, 25, 44, 0.95);
                border: 1px solid rgba(96, 165, 250, 0.18);
                border-radius: 12px;
            }
        """

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            f"""
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
        """
        )

        # محتوى التمرير
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(15, 15, 15, 15)

        header_frame = QFrame()
        header_frame.setStyleSheet(summary_card_style)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(10)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(3)
        header_title = QLabel("إعداد الخزنة" if self.cash_only else "إعداد الحساب")
        header_title.setStyleSheet("color: #f8fafc; font-size: 18px; font-weight: bold;")
        header_subtitle = QLabel(subtitle_text)
        header_subtitle.setStyleSheet(helper_style)
        header_subtitle.setWordWrap(True)
        title_layout.addWidget(header_title)
        title_layout.addWidget(header_subtitle)
        self.keyboard_shortcuts_hint_label = QLabel(
            "اختصارات: Esc إلغاء • Ctrl+S أو Ctrl+Enter حفظ • Ctrl+A/C/X/V/Z/Y داخل الحقول"
            + (" • Alt+0..6 لاختيار القوالب" if self.cash_only else "")
        )
        self.keyboard_shortcuts_hint_label.setStyleSheet(helper_style)
        self.keyboard_shortcuts_hint_label.setWordWrap(True)
        title_layout.addWidget(self.keyboard_shortcuts_hint_label)
        header_layout.addLayout(title_layout, 1)

        header_badges = QVBoxLayout()
        header_badges.setSpacing(8)
        self.mode_badge = QLabel(mode_label)
        self.flow_badge = QLabel(flow_label)
        self.print_context_badge = QLabel("جاهزية الطباعة")
        self.balance_policy_badge = QLabel("")
        for badge in (
            self.mode_badge,
            self.flow_badge,
            self.print_context_badge,
            self.balance_policy_badge,
        ):
            badge.setStyleSheet(badge_style)
            header_badges.addWidget(badge, 0, Qt.AlignmentFlag.AlignRight)
        header_layout.addLayout(header_badges)
        content_layout.addWidget(header_frame)

        self.body_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.body_layout.setSpacing(14)

        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        if self.cash_only:
            preset_gallery_frame = QFrame()
            preset_gallery_frame.setStyleSheet(spotlight_card_style)
            preset_gallery_layout = QVBoxLayout(preset_gallery_frame)
            preset_gallery_layout.setContentsMargins(16, 14, 16, 14)
            preset_gallery_layout.setSpacing(10)

            preset_gallery_title = QLabel("اختيار سريع لقناة التحصيل")
            preset_gallery_title.setStyleSheet(
                "color: #f8fafc; font-size: 14px; font-weight: bold;"
            )
            preset_gallery_layout.addWidget(preset_gallery_title)

            preset_gallery_hint = QLabel(
                "ابدأ من قالب جاهز لو كانت الخزنة من القنوات الحالية، أو انتقل للوضع اليدوي لإنشاء قناة جديدة بنفس المستوى المهني."
            )
            preset_gallery_hint.setStyleSheet(helper_style)
            preset_gallery_hint.setWordWrap(True)
            preset_gallery_layout.addWidget(preset_gallery_hint)

            preset_buttons_grid = QGridLayout()
            preset_buttons_grid.setHorizontalSpacing(10)
            preset_buttons_grid.setVerticalSpacing(10)

            for index, preset in enumerate(CASHBOX_PRESETS):
                button_title = (
                    "يدوي / مخصص" if preset["id"] == MANUAL_CASHBOX_PRESET_ID else preset["name"]
                )
                button_subtitle = (
                    "تحرير كامل لكل الحقول"
                    if preset["id"] == MANUAL_CASHBOX_PRESET_ID
                    else f"{preset['code']} • {preset['treasury_type']}"
                )
                button = QPushButton(f"{button_title}\n{button_subtitle}")
                button.setCheckable(True)
                button.setStyleSheet(preset_button_style)
                button.clicked.connect(
                    lambda _checked=False, preset_id=preset["id"]: self._select_cashbox_preset(
                        preset_id
                    )
                )
                preset_buttons_grid.addWidget(button, index // 2, index % 2)
                self.cashbox_preset_buttons[preset["id"]] = button

            preset_gallery_layout.addLayout(preset_buttons_grid)

            self.selected_preset_caption = QLabel("")
            self.selected_preset_caption.setStyleSheet(helper_style)
            self.selected_preset_caption.setWordWrap(True)
            preset_gallery_layout.addWidget(self.selected_preset_caption)
            left_layout.addWidget(preset_gallery_frame)

        identity_groupbox = QGroupBox("الهوية والربط المحاسبي" if self.cash_only else entity_title)
        identity_groupbox.setStyleSheet(RESPONSIVE_GROUPBOX_STYLE)
        identity_layout = QFormLayout()
        identity_layout.setSpacing(12)
        identity_layout.setContentsMargins(15, 20, 15, 15)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("مثال: 111001" if self.cash_only else "مثال: 1111")
        self.code_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.code_input.textChanged.connect(self._validate_inputs)
        identity_layout.addRow(f"{entity_code_label}: *", self.code_input)
        if self.cash_only:
            self.code_helper_label = QLabel(
                "استخدم الكود التشغيلي المعتمد للقناة حتى تظل التقارير والمزامنة والتتبع الداخلي متسقة."
            )
            self.code_helper_label.setStyleSheet(helper_style)
            self.code_helper_label.setWordWrap(True)
            identity_layout.addRow("", self.code_helper_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(
            "مثال: Bank Misr Local" if self.cash_only else "مثال: الخزنة الرئيسية"
        )
        self.name_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.name_input.textChanged.connect(self._validate_inputs)
        identity_layout.addRow(f"{entity_name_label}: *", self.name_input)
        if self.cash_only:
            self.name_usage_hint = QLabel(
                "هذا الاسم سيظهر في الفاتورة وقوائم التحصيل. اجعله قصيرًا وواضحًا ومناسبًا للطباعة."
            )
            self.name_usage_hint.setStyleSheet(helper_style)
            self.name_usage_hint.setWordWrap(True)
            identity_layout.addRow("", self.name_usage_hint)

        self.type_combo = QComboBox()
        self.type_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if self.cash_only:
            self.type_combo.addItem("خزنة / قناة مالية", userData=schemas.AccountType.CASH)
            self.type_combo.setCurrentIndex(0)
            self.type_combo.setEnabled(False)
        else:
            account_types = [
                (schemas.AccountType.ASSET, "أصول"),
                (schemas.AccountType.CASH, "أصول نقدية"),
                (schemas.AccountType.LIABILITY, "خصوم"),
                (schemas.AccountType.EQUITY, "حقوق ملكية"),
                (schemas.AccountType.REVENUE, "إيرادات"),
                (schemas.AccountType.EXPENSE, "مصروفات"),
            ]
            for acc_type, display_name in account_types:
                self.type_combo.addItem(display_name, userData=acc_type)
            self.type_combo.currentIndexChanged.connect(self._on_type_changed)
            self.type_combo.currentIndexChanged.connect(self._refresh_entity_summary)
            identity_layout.addRow("نوع الحساب:", self.type_combo)

        self.parent_combo = SmartFilterComboBox()
        self.parent_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.parent_combo.addItem(
            "-- بدون فئة رئيسية --" if self.cash_only else "-- بدون أب (حساب رئيسي) --",
            userData=None,
        )
        self._populate_parent_accounts()
        if self.cash_only and not self.is_editing and self.parent_combo.count() > 1:
            self.parent_combo.setCurrentIndex(1)
        self.parent_combo.currentIndexChanged.connect(self._refresh_entity_summary)
        identity_layout.addRow(f"{parent_label}:", self.parent_combo)
        if self.cash_only:
            self.parent_usage_hint = QLabel(
                "الفئة الرئيسية تحدد مكان الخزنة داخل شجرة التحصيل، وتؤثر على ظهورها في التقارير والربط المحاسبي."
            )
            self.parent_usage_hint.setStyleSheet(helper_style)
            self.parent_usage_hint.setWordWrap(True)
            identity_layout.addRow("", self.parent_usage_hint)

        self.currency_combo = QComboBox()
        self.currency_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        currencies = [
            (schemas.CurrencyCode.EGP, "جنيه مصري (EGP)"),
            (schemas.CurrencyCode.USD, "دولار أمريكي (USD)"),
            (schemas.CurrencyCode.SAR, "ريال سعودي (SAR)"),
            (schemas.CurrencyCode.AED, "درهم إماراتي (AED)"),
        ]
        for currency, display_name in currencies:
            self.currency_combo.addItem(display_name, userData=currency)
        self.currency_combo.setCurrentIndex(0)
        self.currency_combo.currentIndexChanged.connect(self._sync_currency_ui)
        identity_layout.addRow("العملة:", self.currency_combo)

        identity_hint = QLabel(
            "اختر الفئة المناسبة للعمل ضمن شجرة الخزن حتى تظهر الخزنة في التقارير والحركات بشكل صحيح."
            if self.cash_only
            else "حدد موقع الحساب بدقة داخل الشجرة المحاسبية لتفادي أخطاء الربط والترحيل."
        )
        identity_hint.setStyleSheet(helper_style)
        identity_hint.setWordWrap(True)

        identity_groupbox.setLayout(identity_layout)
        left_layout.addWidget(identity_groupbox)
        left_layout.addWidget(identity_hint)

        if self.cash_only:
            treasury_groupbox = QGroupBox("ملف قناة التحصيل")
            treasury_groupbox.setStyleSheet(RESPONSIVE_GROUPBOX_STYLE)
            treasury_layout = QFormLayout()
            treasury_layout.setSpacing(12)
            treasury_layout.setContentsMargins(15, 20, 15, 15)

            self.cashbox_preset_combo = QComboBox()
            self.cashbox_preset_combo.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            for preset in CASHBOX_PRESETS:
                self.cashbox_preset_combo.addItem(preset["label"], userData=preset["id"])
            self.cashbox_preset_combo.currentIndexChanged.connect(
                self._apply_selected_cashbox_preset
            )
            treasury_layout.addRow("مرجع التهيئة:", self.cashbox_preset_combo)

            self.cashbox_preset_hint_label = QLabel("")
            self.cashbox_preset_hint_label.setStyleSheet(helper_style)
            self.cashbox_preset_hint_label.setWordWrap(True)
            treasury_layout.addRow("", self.cashbox_preset_hint_label)

            self.treasury_type_combo = QComboBox()
            self.treasury_type_combo.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            for treasury_type in (
                "محفظة إلكترونية",
                "إنستا باي",
                "تحويل بنكي داخل مصر",
                "تحويل بنكي دولي",
                "خزنة نقدية",
                "أخرى",
            ):
                self.treasury_type_combo.addItem(treasury_type)
            self.treasury_type_combo.currentIndexChanged.connect(
                self._update_treasury_details_placeholder
            )
            self.treasury_type_combo.currentIndexChanged.connect(self._refresh_entity_summary)
            self.treasury_type_combo.currentIndexChanged.connect(
                self._sync_cashbox_preset_from_current_fields
            )
            self.treasury_type_label = QLabel("تصنيف القناة:")
            treasury_layout.addRow(self.treasury_type_label, self.treasury_type_combo)

            self.treasury_profile_label = QLabel("")
            self.treasury_profile_label.setStyleSheet(helper_style)
            self.treasury_profile_label.setWordWrap(True)
            treasury_layout.addRow("", self.treasury_profile_label)

            self.treasury_details_input = QTextEdit()
            self.treasury_details_input.setMaximumHeight(118)
            self.treasury_details_input.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            self.treasury_details_input.textChanged.connect(self._validate_inputs)
            self.treasury_details_input.textChanged.connect(
                self._sync_cashbox_preset_from_current_fields
            )
            self.treasury_details_title_label = QLabel("")
            self.treasury_details_title_label.setStyleSheet(
                "color: #e2e8f0; font-size: 12px; font-weight: bold;"
            )
            self.treasury_details_helper_label = QLabel("")
            self.treasury_details_helper_label.setStyleSheet(helper_style)
            self.treasury_details_helper_label.setWordWrap(True)

            treasury_details_container = QWidget()
            treasury_details_layout = QVBoxLayout(treasury_details_container)
            treasury_details_layout.setContentsMargins(0, 0, 0, 0)
            treasury_details_layout.setSpacing(6)
            treasury_details_layout.addWidget(self.treasury_details_title_label)
            treasury_details_layout.addWidget(self.treasury_details_input)
            treasury_details_layout.addWidget(self.treasury_details_helper_label)

            self.treasury_details_label = QLabel("بيانات التنفيذ:")
            treasury_layout.addRow(self.treasury_details_label, treasury_details_container)

            treasury_hint = QLabel(
                "رتّب كل رقم أو مرجع في سطر مستقل. ما تكتبه هنا هو نفسه الذي سيُستخدم في المراجعة الداخلية ويظهر في صياغة وسائل الدفع."
            )
            treasury_hint.setStyleSheet(helper_style)
            treasury_hint.setWordWrap(True)
            treasury_layout.addRow("", treasury_hint)

            treasury_groupbox.setLayout(treasury_layout)
            left_layout.addWidget(treasury_groupbox)

        operations_groupbox = QGroupBox(
            "التشغيل والرقابة" if self.cash_only else "التشغيل والمتابعة"
        )
        operations_groupbox.setStyleSheet(RESPONSIVE_GROUPBOX_STYLE)
        operations_layout = QFormLayout()
        operations_layout.setSpacing(12)
        operations_layout.setContentsMargins(15, 20, 15, 15)

        self.balance_spinbox = CustomSpinBox(
            decimals=2, minimum=-999999999.99, maximum=999999999.99
        )
        self.balance_spinbox.setValue(0.0)
        self.balance_spinbox.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.balance_spinbox.valueChanged.connect(self._refresh_entity_summary)
        balance_widget = QWidget()
        balance_layout = QVBoxLayout(balance_widget)
        balance_layout.setContentsMargins(0, 0, 0, 0)
        balance_layout.setSpacing(6)
        balance_layout.addWidget(self.balance_spinbox)
        self.balance_hint_label = QLabel("")
        self.balance_hint_label.setStyleSheet(helper_style)
        self.balance_hint_label.setWordWrap(True)
        balance_layout.addWidget(self.balance_hint_label)
        operations_layout.addRow("الرصيد الافتتاحي:", balance_widget)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "ملاحظات تشغيلية إضافية للخزنة (اختياري)..."
            if self.cash_only
            else "وصف الحساب (اختياري)..."
        )
        self.description_input.setMaximumHeight(78)
        self.description_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.description_input.textChanged.connect(self._refresh_entity_summary)
        if self.cash_only:
            self.code_input.textChanged.connect(self._sync_cashbox_preset_from_current_fields)
            self.name_input.textChanged.connect(self._sync_cashbox_preset_from_current_fields)
            self.description_input.textChanged.connect(
                self._sync_cashbox_preset_from_current_fields
            )
        operations_layout.addRow(
            "ملاحظات تشغيلية:" if self.cash_only else "الوصف:",
            self.description_input,
        )

        self.active_checkbox = QCheckBox("خزنة نشطة" if self.cash_only else "حساب نشط")
        self.active_checkbox.setChecked(True)
        self.active_checkbox.setFont(get_cairo_font(13, bold=True))
        self.active_checkbox.toggled.connect(self._refresh_entity_summary)
        operations_layout.addRow("الحالة:", self.active_checkbox)

        operations_groupbox.setLayout(operations_layout)
        left_layout.addWidget(operations_groupbox)

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet(
            """
            QLabel {
                color: #fdba74;
                background: rgba(251, 146, 60, 0.12);
                border: 1px solid rgba(251, 146, 60, 0.28);
                border-radius: 10px;
                font-weight: bold;
                padding: 8px 10px;
            }
        """
        )
        self.validation_label.setVisible(False)
        left_layout.addWidget(self.validation_label)
        left_layout.addStretch(1)

        summary_frame = QFrame()
        self.summary_frame = summary_frame
        summary_frame.setStyleSheet(summary_card_style)
        summary_frame.setMinimumWidth(270 if self.cash_only else 250)
        summary_layout = QVBoxLayout(summary_frame)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        summary_layout.setSpacing(10)

        summary_heading = QLabel("مراجعة قبل الحفظ")
        summary_heading.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: bold;")
        summary_layout.addWidget(summary_heading)

        self.summary_name_value = QLabel("—")
        self.summary_name_value.setStyleSheet(
            "color: #f8fafc; font-size: 16px; font-weight: bold; font-family: 'Cairo';"
        )
        self.summary_name_value.setWordWrap(True)
        summary_layout.addWidget(self.summary_name_value)

        self.summary_mode_note = QLabel("")
        self.summary_mode_note.setStyleSheet(helper_style)
        self.summary_mode_note.setWordWrap(True)
        summary_layout.addWidget(self.summary_mode_note)

        metrics_layout = QGridLayout()
        metrics_layout.setHorizontalSpacing(8)
        metrics_layout.setVerticalSpacing(8)

        def add_metric_card(row: int, col: int, title: str, attr_name: str) -> None:
            card = QFrame()
            card.setStyleSheet(metric_tile_style)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(4)
            title_label = QLabel(title)
            title_label.setStyleSheet(row_label_style)
            value_label = QLabel("—")
            value_label.setStyleSheet(
                "color: #f8fafc; font-size: 13px; font-weight: bold; font-family: 'Cairo';"
            )
            value_label.setWordWrap(True)
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            setattr(self, attr_name, value_label)
            metrics_layout.addWidget(card, row, col)

        add_metric_card(0, 0, "جاهزية الحفظ", "summary_readiness_value")
        add_metric_card(0, 1, "الربط المحاسبي", "summary_routing_value")
        add_metric_card(1, 0, "اسم الطباعة", "summary_invoice_value")
        add_metric_card(1, 1, "المرجع التشغيلي", "summary_reference_value")
        summary_layout.addLayout(metrics_layout)

        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(10)
        info_grid.setVerticalSpacing(10)

        def add_info_row(row: int, title: str, attr_name: str) -> None:
            label = QLabel(title)
            label.setStyleSheet(row_label_style)
            value = QLabel("—")
            value.setStyleSheet(row_value_style)
            value.setWordWrap(True)
            setattr(self, attr_name, value)
            info_grid.addWidget(label, row, 0)
            info_grid.addWidget(value, row, 1)

        add_info_row(0, entity_code_label, "summary_code_value")
        add_info_row(1, parent_label, "summary_parent_value")
        current_row = 2
        if self.cash_only:
            add_info_row(current_row, "نوع الخزنة", "summary_channel_value")
            current_row += 1
        add_info_row(current_row, "العملة", "summary_currency_value")
        add_info_row(current_row + 1, "الرصيد", "summary_balance_value")
        add_info_row(current_row + 2, "الحالة", "summary_status_value")
        summary_layout.addLayout(info_grid)

        self.summary_details_title = QLabel("بيانات الخزنة")
        self.summary_details_title.setStyleSheet(
            "color: #bfdbfe; font-size: 12px; font-weight: bold;"
        )
        self.summary_details_title.setVisible(self.cash_only)
        summary_layout.addWidget(self.summary_details_title)

        self.summary_details_value = QLabel("")
        self.summary_details_value.setStyleSheet(helper_style)
        self.summary_details_value.setWordWrap(True)
        self.summary_details_value.setVisible(self.cash_only)
        summary_layout.addWidget(self.summary_details_value)

        self.summary_description_value = QLabel("")
        self.summary_description_value.setStyleSheet(helper_style)
        self.summary_description_value.setWordWrap(True)
        summary_layout.addWidget(self.summary_description_value)

        if self.cash_only:
            invoice_preview_frame = QFrame()
            invoice_preview_frame.setStyleSheet(preview_card_style)
            invoice_preview_layout = QVBoxLayout(invoice_preview_frame)
            invoice_preview_layout.setContentsMargins(12, 12, 12, 12)
            invoice_preview_layout.setSpacing(6)

            invoice_preview_title = QLabel("معاينة الظهور في الفاتورة")
            invoice_preview_title.setStyleSheet(
                "color: #bfdbfe; font-size: 12px; font-weight: bold;"
            )
            invoice_preview_layout.addWidget(invoice_preview_title)

            self.invoice_preview_name_value = QLabel("—")
            self.invoice_preview_name_value.setStyleSheet(
                "color: #f8fafc; font-size: 15px; font-weight: bold; font-family: 'Cairo';"
            )
            self.invoice_preview_name_value.setWordWrap(True)
            invoice_preview_layout.addWidget(self.invoice_preview_name_value)

            self.invoice_preview_method_value = QLabel("")
            self.invoice_preview_method_value.setStyleSheet(
                "color: #93c5fd; font-size: 12px; font-weight: bold;"
            )
            self.invoice_preview_method_value.setWordWrap(True)
            invoice_preview_layout.addWidget(self.invoice_preview_method_value)

            self.invoice_preview_details_value = QLabel("")
            self.invoice_preview_details_value.setStyleSheet(helper_style)
            self.invoice_preview_details_value.setWordWrap(True)
            invoice_preview_layout.addWidget(self.invoice_preview_details_value)

            self.invoice_preview_caption_value = QLabel("")
            self.invoice_preview_caption_value.setStyleSheet(helper_style)
            self.invoice_preview_caption_value.setWordWrap(True)
            invoice_preview_layout.addWidget(self.invoice_preview_caption_value)
            summary_layout.addWidget(invoice_preview_frame)

        summary_hint_frame = QFrame()
        summary_hint_frame.setStyleSheet(
            """
            QFrame {
                background: rgba(37, 99, 235, 0.10);
                border: 1px solid rgba(59, 130, 246, 0.20);
                border-radius: 12px;
            }
        """
        )
        summary_hint_layout = QVBoxLayout(summary_hint_frame)
        summary_hint_layout.setContentsMargins(12, 10, 12, 10)
        summary_hint_layout.setSpacing(6)
        hint_title = QLabel("ملاحظات تشغيلية")
        hint_title.setStyleSheet("color: #bfdbfe; font-size: 12px; font-weight: bold;")
        summary_hint_layout.addWidget(hint_title)
        for text in (
            (
                "تُستخدم الخزنة في التحصيل والصرف وترحيل الحركات مباشرة."
                if self.cash_only
                else "يؤثر هذا الحساب على التقارير وربط القيود اليومية."
            ),
            "يمكن تعطيل العنصر بدل حذفه للحفاظ على السجل المحاسبي.",
            "اختيار العملة يحدد طريقة عرض الرصيد والحركات المرتبطة.",
        ):
            item = QLabel(f"• {text}")
            item.setStyleSheet(helper_style)
            item.setWordWrap(True)
            summary_hint_layout.addWidget(item)
        summary_layout.addWidget(summary_hint_frame)
        summary_layout.addStretch(1)

        self.body_layout.addWidget(left_column, 3)
        self.body_layout.addWidget(summary_frame, 2)
        content_layout.addLayout(self.body_layout)
        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        buttons_container = QWidget()
        buttons_container.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS['bg_light']};
                border-top: 1px solid {COLORS['border']};
            }}
        """
        )
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(15, 12, 15, 12)
        buttons_layout.setSpacing(10)

        buttons_layout.addStretch()

        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton(
            "💾 حفظ تعديل الخزنة"
            if self.cash_only and self.is_editing
            else ("💾 حفظ الخزنة" if self.cash_only else "💾 حفظ")
        )
        self.save_button.setDefault(True)
        self.save_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_button.clicked.connect(self.save_account)

        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.save_button)

        main_layout.addWidget(buttons_container)

        # تحميل البيانات إذا كان في وضع التعديل
        if self.is_editing:
            self.populate_fields()
        self._setup_keyboard_support()

    def _finalize_initial_state(self) -> None:
        if self.cash_only:
            self._update_treasury_details_placeholder()
            self._sync_cashbox_preset_from_current_fields()
        self._sync_currency_ui()
        self._validate_inputs()
        self._apply_balance_edit_policy()
        if self.cash_only:
            self._refresh_cashbox_preset_buttons()
        self._apply_compact_layout()
        self.code_input.setFocus()

    def _select_cashbox_preset(self, preset_id: str) -> None:
        if not self.cash_only or not hasattr(self, "cashbox_preset_combo"):
            return
        index = self.cashbox_preset_combo.findData(preset_id)
        if index < 0:
            return
        self.cashbox_preset_combo.setCurrentIndex(index)

    def _refresh_cashbox_preset_buttons(self) -> None:
        if self._initializing_ui or not self.cash_only or not self.cashbox_preset_buttons:
            return
        current_preset_id = (
            self.cashbox_preset_combo.currentData()
            if hasattr(self, "cashbox_preset_combo")
            else None
        )
        for preset_id, button in self.cashbox_preset_buttons.items():
            button.blockSignals(True)
            button.setChecked(preset_id == current_preset_id)
            button.blockSignals(False)

    def _register_shortcut(
        self, sequence: QKeySequence | QKeySequence.StandardKey | str, callback
    ) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        self._keyboard_shortcuts.append(shortcut)

    def _setup_keyboard_support(self) -> None:
        self._keyboard_shortcuts.clear()

        self._register_shortcut(
            QKeySequence.StandardKey.SelectAll,
            lambda: self._trigger_focused_edit_action("selectAll"),
        )
        self._register_shortcut(
            QKeySequence.StandardKey.Copy, lambda: self._trigger_focused_edit_action("copy")
        )
        self._register_shortcut(
            QKeySequence.StandardKey.Cut, lambda: self._trigger_focused_edit_action("cut")
        )
        self._register_shortcut(
            QKeySequence.StandardKey.Paste, lambda: self._trigger_focused_edit_action("paste")
        )
        self._register_shortcut(
            QKeySequence.StandardKey.Undo, lambda: self._trigger_focused_edit_action("undo")
        )
        self._register_shortcut(
            QKeySequence.StandardKey.Redo, lambda: self._trigger_focused_edit_action("redo")
        )
        self._register_shortcut("Ctrl+S", self._trigger_primary_action)
        self._register_shortcut("Ctrl+Return", self._trigger_primary_action)
        self._register_shortcut("Ctrl+Enter", self._trigger_primary_action)
        self._register_shortcut("Escape", self.reject)

        if self.cash_only:
            preset_sequence_map = {
                "Alt+0": MANUAL_CASHBOX_PRESET_ID,
                "Alt+1": "vodafone_cash_hazem",
                "Alt+2": "vodafone_cash_reda",
                "Alt+3": "instapay",
                "Alt+4": "bank_misr_local",
                "Alt+5": "bank_misr_international",
                "Alt+6": "cash_payment",
            }
            for sequence, preset_id in preset_sequence_map.items():
                self._register_shortcut(
                    sequence,
                    lambda preset_id=preset_id: self._select_cashbox_preset(preset_id),
                )

        self._configure_tab_order()

    def _configure_tab_order(self) -> None:
        ordered_widgets: list[QWidget] = [self.code_input, self.name_input]
        if not self.cash_only:
            ordered_widgets.append(self.type_combo)
        ordered_widgets.extend(
            [
                self.parent_combo,
                self.currency_combo,
            ]
        )
        if self.cash_only:
            ordered_widgets.extend(
                [
                    self.cashbox_preset_combo,
                    self.treasury_type_combo,
                    self.treasury_details_input,
                ]
            )
        ordered_widgets.extend(
            [
                self.balance_spinbox,
                self.description_input,
                self.active_checkbox,
                self.save_button,
                self.cancel_button,
            ]
        )
        for current_widget, next_widget in zip(ordered_widgets, ordered_widgets[1:], strict=False):
            QWidget.setTabOrder(current_widget, next_widget)

    def _resolve_edit_target(self) -> QWidget | None:
        focused_widget = QApplication.focusWidget()
        if focused_widget is None:
            return None
        if isinstance(focused_widget, QComboBox):
            line_edit = focused_widget.lineEdit()
            if line_edit is not None:
                return line_edit
        line_edit_getter = getattr(focused_widget, "lineEdit", None)
        if callable(line_edit_getter):
            try:
                line_edit = line_edit_getter()
            except Exception:
                line_edit = None
            if line_edit is not None:
                return line_edit
        return focused_widget

    def _trigger_focused_edit_action(self, action_name: str) -> bool:
        target = self._resolve_edit_target()
        if target is None:
            return False
        action = getattr(target, action_name, None)
        if callable(action):
            action()
            return True
        return False

    def _trigger_primary_action(self) -> None:
        if hasattr(self, "save_button") and self.save_button.isEnabled():
            self.save_button.click()

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        """Fallback keyboard support when tests or platform delivery target the dialog itself."""
        if event.matches(QKeySequence.StandardKey.SelectAll):
            if self._trigger_focused_edit_action("selectAll"):
                event.accept()
                return
        elif event.matches(QKeySequence.StandardKey.Copy):
            if self._trigger_focused_edit_action("copy"):
                event.accept()
                return
        elif event.matches(QKeySequence.StandardKey.Cut):
            if self._trigger_focused_edit_action("cut"):
                event.accept()
                return
        elif event.matches(QKeySequence.StandardKey.Paste):
            if self._trigger_focused_edit_action("paste"):
                event.accept()
                return
        elif event.matches(QKeySequence.StandardKey.Undo):
            if self._trigger_focused_edit_action("undo"):
                event.accept()
                return
        elif event.matches(QKeySequence.StandardKey.Redo):
            if self._trigger_focused_edit_action("redo"):
                event.accept()
                return

        modifiers = event.modifiers()
        key = event.key()

        if modifiers == Qt.KeyboardModifier.ControlModifier and key in (
            Qt.Key.Key_S,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self._trigger_primary_action()
            event.accept()
            return

        if key == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return

        if self.cash_only and modifiers == Qt.KeyboardModifier.AltModifier:
            preset_key_map = {
                Qt.Key.Key_0: MANUAL_CASHBOX_PRESET_ID,
                Qt.Key.Key_1: "vodafone_cash_hazem",
                Qt.Key.Key_2: "vodafone_cash_reda",
                Qt.Key.Key_3: "instapay",
                Qt.Key.Key_4: "bank_misr_local",
                Qt.Key.Key_5: "bank_misr_international",
                Qt.Key.Key_6: "cash_payment",
            }
            preset_id = preset_key_map.get(key)
            if preset_id is not None:
                self._select_cashbox_preset(preset_id)
                event.accept()
                return

        super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._apply_compact_layout()

    def _apply_compact_layout(self) -> None:
        if self._initializing_ui or not hasattr(self, "body_layout"):
            return
        compact = self.width() < 860
        if self._body_layout_compact == compact:
            return
        self._body_layout_compact = compact
        self.body_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        )
        if hasattr(self, "summary_frame"):
            self.summary_frame.setMinimumWidth(0 if compact else (270 if self.cash_only else 250))

    def _apply_balance_edit_policy(self) -> None:
        if not hasattr(self, "balance_hint_label"):
            return
        if self.is_editing:
            self.balance_spinbox.setEnabled(False)
            self.balance_hint_label.setText(
                "في وضع التعديل يظهر الرصيد الحالي فقط. أي تغيير فعلي يتم من خلال حركة مالية على الخزنة."
                if self.cash_only
                else "في وضع التعديل يظهر الرصيد الحالي فقط. تعديل الرصيد الفعلي يتم عبر القيود والحركات."
            )
            self.balance_policy_badge.setText("الرصيد يُدار بالحركة")
        else:
            self.balance_spinbox.setEnabled(True)
            self.balance_hint_label.setText(
                "يُستخدم هذا الرصيد مرة واحدة عند إنشاء الخزنة، ثم تُدار الزيادة والنقص من الحركات اليومية."
                if self.cash_only
                else "يُستخدم هذا الرصيد كرصيد افتتاحي عند إنشاء الحساب لأول مرة."
            )
            self.balance_policy_badge.setText("رصيد افتتاحي متاح")

    def _sync_currency_ui(self) -> None:
        currency = self.currency_combo.currentData()
        suffixes = {
            schemas.CurrencyCode.EGP: " ج.م",
            schemas.CurrencyCode.USD: " $",
            schemas.CurrencyCode.SAR: " ر.س",
            schemas.CurrencyCode.AED: " د.إ",
        }
        self.balance_spinbox.setSuffix(suffixes.get(currency, ""))
        self._refresh_entity_summary()

    def _get_cashbox_preset(self, preset_id: str | None) -> dict[str, str] | None:
        if not preset_id:
            return None
        return next((preset for preset in CASHBOX_PRESETS if preset["id"] == preset_id), None)

    def _detect_cashbox_preset_id(self) -> str:
        code = self.code_input.text().strip() if hasattr(self, "code_input") else ""
        name = self.name_input.text().strip() if hasattr(self, "name_input") else ""

        for preset in CASHBOX_PRESETS:
            if preset["id"] == MANUAL_CASHBOX_PRESET_ID:
                continue
            if code and code == preset.get("code", ""):
                return preset["id"]
        for preset in CASHBOX_PRESETS:
            if preset["id"] == MANUAL_CASHBOX_PRESET_ID:
                continue
            if name and name == preset.get("name", ""):
                return preset["id"]
        return MANUAL_CASHBOX_PRESET_ID

    def _update_cashbox_preset_hint(self) -> None:
        if not self.cash_only or not hasattr(self, "cashbox_preset_hint_label"):
            return
        preset = self._get_cashbox_preset(
            self.cashbox_preset_combo.currentData()
            if hasattr(self, "cashbox_preset_combo")
            else None
        )
        if not preset or preset["id"] == MANUAL_CASHBOX_PRESET_ID:
            self.cashbox_preset_hint_label.setText(
                "اختر أحد القوالب التشغيلية الحالية لتعبئة الكود والاسم وبيانات التحصيل تلقائيًا، أو اترك الوضع يدويًا لإنشاء خزنة مخصصة."
            )
            if hasattr(self, "selected_preset_caption"):
                self.selected_preset_caption.setText(
                    "الوضع اليدوي مناسب للخزن الجديدة أو الحالات الخاصة التي لا تريد ربطها بقالب جاهز."
                )
            return
        self.cashbox_preset_hint_label.setText(
            f"سيتم تجهيز {preset['name']} بالكود {preset['code']} وتصنيف {preset['treasury_type']}، ويمكنك تعديل أي حقل قبل الحفظ."
        )
        if hasattr(self, "selected_preset_caption"):
            self.selected_preset_caption.setText(
                f"القالب النشط الآن: {preset['name']} • {preset['treasury_type']} • {preset['code']}"
            )

    def _sync_cashbox_preset_from_current_fields(self, *_args) -> None:
        if (
            self._initializing_ui
            or not self.cash_only
            or not hasattr(self, "cashbox_preset_combo")
            or self._applying_cashbox_preset
        ):
            return

        preset_id = self._detect_cashbox_preset_id()
        preset_index = self.cashbox_preset_combo.findData(preset_id)
        if preset_index < 0:
            preset_index = 0
        if self.cashbox_preset_combo.currentIndex() != preset_index:
            blocker = QSignalBlocker(self.cashbox_preset_combo)
            self.cashbox_preset_combo.setCurrentIndex(preset_index)
            del blocker
        self._update_cashbox_preset_hint()
        self._refresh_cashbox_preset_buttons()
        if not self.description_input.toPlainText().strip():
            self._update_treasury_details_placeholder()

    def _apply_selected_cashbox_preset(self, *_args) -> None:
        if not self.cash_only or not hasattr(self, "cashbox_preset_combo"):
            return

        preset = self._get_cashbox_preset(self.cashbox_preset_combo.currentData())
        self._update_cashbox_preset_hint()
        self._refresh_cashbox_preset_buttons()
        if not preset or preset["id"] == MANUAL_CASHBOX_PRESET_ID:
            self._update_treasury_details_placeholder()
            self._refresh_entity_summary()
            return

        self._applying_cashbox_preset = True
        try:
            self.code_input.setText(preset.get("code", ""))
            self.name_input.setText(preset.get("name", ""))

            treasury_index = self.treasury_type_combo.findText(preset.get("treasury_type", ""))
            if treasury_index >= 0:
                self.treasury_type_combo.setCurrentIndex(treasury_index)

            self.treasury_details_input.setPlainText(preset.get("details", ""))
            self.description_input.setPlainText(preset.get("notes", ""))

            currency_index = self.currency_combo.findData(schemas.CurrencyCode.EGP)
            if currency_index >= 0:
                self.currency_combo.setCurrentIndex(currency_index)

            self.active_checkbox.setChecked(True)
            if (
                not self.is_editing
                and self.parent_combo.currentData() is None
                and self.parent_combo.count() > 1
            ):
                self.parent_combo.setCurrentIndex(1)
        finally:
            self._applying_cashbox_preset = False

        self._update_treasury_details_placeholder()
        self._validate_inputs()

    def _update_treasury_details_placeholder(self) -> None:
        if not self.cash_only or not hasattr(self, "treasury_details_input"):
            return

        treasury_type = self.treasury_type_combo.currentText().strip()
        placeholders = {
            "محفظة إلكترونية": "01067894321 - حازم اشرف\n01021965200 - رضا سامي",
            "إنستا باي": "01067894321 - حازم اشرف\nskywaveads@instapay",
            "تحويل بنكي داخل مصر": "رقم الحساب: 2630333000086626\nSWIFT CODE: BMISEGCXXXX",
            "تحويل بنكي دولي": "IBAN: EG020002026302630333000086626\nSWIFT CODE: BMISEGCXXXX",
            "خزنة نقدية": "الخزنة الرئيسية - مقر الشركة\nالمسؤول: اسم أمين الخزنة",
            "أخرى": "أدخل بيانات القناة المالية، كل عنصر في سطر مستقل.",
        }
        details_titles = {
            "محفظة إلكترونية": (
                "بيانات المحافظ والأرقام المستقبلة",
                "ضع كل رقم أو اسم مسؤول في سطر مستقل حتى يسهل نسخه ومراجعته داخل الفاتورة والتحصيل.",
            ),
            "إنستا باي": (
                "معرّفات InstaPay أو أرقام الربط",
                "يفضل وضع البريد أو المعرف في سطر منفصل عن رقم الهاتف حتى تكون القراءة أوضح للفريق والعميل.",
            ),
            "تحويل بنكي داخل مصر": (
                "بيانات الحساب المحلي",
                "اكتب رقم الحساب وSWIFT أو أي مرجع محلي أساسي فقط. تجنب الحشو حتى تظل الطباعة نظيفة.",
            ),
            "تحويل بنكي دولي": (
                "بيانات التحويل الدولي",
                "ضع IBAN وSWIFT في أول سطرين. أي تعليمات إضافية اكتبها في ملاحظات التشغيل أسفل الشاشة.",
            ),
            "خزنة نقدية": (
                "موقع التحصيل والمسؤول المباشر",
                "سجّل مقر الخزنة واسم المسؤول أو نقطة التسليم النقدي. لا حاجة لبيانات طويلة لأن الطباعة تحتاج صياغة مختصرة.",
            ),
            "أخرى": (
                "تفاصيل القناة المالية",
                "اكتب فقط البيانات التي يحتاجها الفريق أو العميل فعليًا عند التحصيل أو التحويل.",
            ),
        }
        self.treasury_details_input.setPlaceholderText(placeholders.get(treasury_type, ""))
        details_title, details_helper = details_titles.get(
            treasury_type,
            ("تفاصيل التشغيل", "أدخل البيانات الأساسية للقناة المالية بصياغة قصيرة وواضحة."),
        )
        if hasattr(self, "treasury_details_title_label"):
            self.treasury_details_title_label.setText(details_title)
        if hasattr(self, "treasury_details_helper_label"):
            self.treasury_details_helper_label.setText(details_helper)
        if hasattr(self, "treasury_profile_label"):
            self.treasury_profile_label.setText(
                f"سيتم تصنيف الخزنة حاليًا كـ {treasury_type}، وسيُبنى عليها اسم طريقة الدفع والربط الداخلي تلقائيًا."
            )
        if hasattr(self, "description_input") and not self.description_input.toPlainText().strip():
            preset = self._get_cashbox_preset(
                self.cashbox_preset_combo.currentData()
                if hasattr(self, "cashbox_preset_combo")
                else None
            )
            self.description_input.setPlaceholderText(
                preset.get("notes", "أضف ملاحظات تشغيلية إضافية للخزنة (اختياري)...")
                if preset
                else "أضف ملاحظات تشغيلية إضافية للخزنة (اختياري)..."
            )

    def _serialize_treasury_description(self) -> str:
        treasury_type = self.treasury_type_combo.currentText().strip()
        details = self.treasury_details_input.toPlainText().strip()
        notes = self.description_input.toPlainText().strip()

        sections: list[str] = []
        if treasury_type:
            sections.append(f"نوع الخزنة: {treasury_type}")
        if details:
            sections.append("بيانات الخزنة:\n" + details)
        if notes:
            sections.append("ملاحظات تشغيلية:\n" + notes)
        return "\n\n".join(section for section in sections if section).strip()

    def _parse_treasury_description(self, raw_description: str | None) -> dict[str, str]:
        text = (raw_description or "").replace("\r\n", "\n").strip()
        parsed = {"treasury_type": "", "details": "", "notes": ""}
        if not text:
            return parsed

        lines = text.splitlines()
        current_section = "notes"
        note_lines: list[str] = []
        details_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_section == "details":
                    details_lines.append("")
                elif current_section == "notes":
                    note_lines.append("")
                continue
            if stripped.startswith("نوع الخزنة:"):
                parsed["treasury_type"] = stripped.split(":", 1)[1].strip()
                current_section = "notes"
                continue
            if stripped == "بيانات الخزنة:":
                current_section = "details"
                continue
            if stripped == "ملاحظات تشغيلية:":
                current_section = "notes"
                continue
            if current_section == "details":
                details_lines.append(stripped)
            else:
                note_lines.append(stripped)

        parsed["details"] = "\n".join(line for line in details_lines).strip()
        parsed["notes"] = "\n".join(line for line in note_lines).strip()
        if not parsed["details"] and not parsed["treasury_type"]:
            parsed["notes"] = text
        return parsed

    def _refresh_entity_summary(self) -> None:
        if self._initializing_ui or not hasattr(self, "summary_name_value"):
            return

        name = self.name_input.text().strip() or "—"
        code = self.code_input.text().strip() or "—"
        parent_text = self.parent_combo.currentText().strip() if self.parent_combo.count() else "—"
        currency_text = self.currency_combo.currentText().strip() or "—"
        description = self.description_input.toPlainText().strip()
        status_text = "نشطة" if self.active_checkbox.isChecked() else "معطلة"
        details = (
            self.treasury_details_input.toPlainText().strip()
            if self.cash_only and hasattr(self, "treasury_details_input")
            else ""
        )
        treasury_type = self.treasury_type_combo.currentText().strip() if self.cash_only else ""
        has_required_details = (
            (not self.cash_only) or treasury_type == "خزنة نقدية" or bool(details)
        )
        is_ready = bool(
            self.code_input.text().strip()
            and self.name_input.text().strip()
            and has_required_details
        )
        trimmed_name = self.name_input.text().strip()
        is_print_ready = bool(trimmed_name) and len(trimmed_name) <= 24 and "\n" not in trimmed_name

        self.summary_name_value.setText(name)
        self.summary_code_value.setText(code)
        self.summary_parent_value.setText(parent_text)
        if self.cash_only and hasattr(self, "summary_channel_value"):
            self.summary_channel_value.setText(
                self.treasury_type_combo.currentText().strip() or "—"
            )
        self.summary_currency_value.setText(currency_text)
        balance_text = (
            self.balance_spinbox.spinbox.text()
            if hasattr(self.balance_spinbox, "spinbox")
            else str(self.balance_spinbox.value())
        )
        self.summary_balance_value.setText(balance_text)
        self.summary_status_value.setText(status_text)
        if self.cash_only and hasattr(self, "treasury_details_input"):
            self.summary_details_value.setText(
                details
                if details
                else "أضف بيانات التحصيل أو التحويل كما ستُستخدم فعليًا داخل الخزنة."
            )
        self.summary_description_value.setText(
            description
            if description
            else (
                "أضف ملاحظات تشغيلية مثل حدود الاستخدام أو اسم المسؤول أو التنبيه المطلوب للفريق."
                if self.cash_only
                else "أضف وصفًا مختصرًا لتسهيل فهم دور الحساب."
            )
        )
        self.summary_mode_note.setText(
            (
                "خزنة جديدة ستُنشأ مع تعريفها التشغيلي وبيانات التحصيل الخاصة بها."
                if not self.is_editing
                else "أنت تعدل خزنة قائمة؛ عدّل بيانات القناة نفسها بينما الرصيد للمراجعة فقط."
            )
            if self.cash_only
            else (
                "حساب جديد ضمن الدليل المحاسبي."
                if not self.is_editing
                else "أنت تعدل حسابًا قائمًا داخل الشجرة."
            )
        )
        if hasattr(self, "summary_readiness_value"):
            self.summary_readiness_value.setText("جاهزة" if is_ready else "ينقصها تعريف")
        if hasattr(self, "summary_routing_value"):
            self.summary_routing_value.setText(
                parent_text if self.parent_combo.currentData() else "بحاجة إلى فئة رئيسية"
            )
        if hasattr(self, "summary_invoice_value"):
            self.summary_invoice_value.setText(
                trimmed_name if is_print_ready else "اختصر الاسم قبل الاعتماد"
            )
        if hasattr(self, "summary_reference_value"):
            reference_value = details.splitlines()[0].strip() if details else "لا يوجد مرجع بعد"
            self.summary_reference_value.setText(reference_value)
        if hasattr(self, "flow_badge") and self.cash_only:
            self.flow_badge.setText(treasury_type or "خزنة تشغيلية")
        if hasattr(self, "print_context_badge"):
            self.print_context_badge.setText(
                "طباعة جاهزة" if is_print_ready else "راجع اسم الطباعة"
            )
        if self.cash_only and hasattr(self, "invoice_preview_name_value"):
            detail_lines = [line.strip() for line in details.splitlines() if line.strip()]
            preview_details = (
                " • ".join(detail_lines[:2])
                if detail_lines
                else "ستظهر بيانات التحصيل المختصرة هنا."
            )
            self.invoice_preview_name_value.setText(name)
            self.invoice_preview_method_value.setText(
                f"طريقة الدفع: {treasury_type or 'قناة مالية'}"
            )
            self.invoice_preview_details_value.setText(preview_details)
            self.invoice_preview_caption_value.setText(
                "هذه معاينة مبسطة لشكل الاسم والبيانات عند الاستخدام في الفاتورة أو ملخص التحصيل."
            )

    def _cleanup_smart_combos(self):
        for combo in self.findChildren(SmartFilterComboBox):
            combo.shutdown()

    def reject(self):
        self._cleanup_smart_combos()
        super().reject()

    def done(self, result: int):
        self._cleanup_smart_combos()
        super().done(result)

    def closeEvent(self, event: QCloseEvent):
        self._cleanup_smart_combos()
        super().closeEvent(event)

    def _validate_inputs(self):
        """Real-time validation - only enable/disable save button"""
        if self._initializing_ui:
            return True
        self._refresh_entity_summary()
        is_valid = True
        error_messages = []

        # Validate code
        code = self.code_input.text().strip()
        if not code:
            is_valid = False
            error_messages.append("رمز الخزنة مطلوب" if self.cash_only else "كود الحساب مطلوب")

        # Validate name
        name = self.name_input.text().strip()
        if not name:
            is_valid = False
            error_messages.append("اسم الخزنة مطلوب" if self.cash_only else "اسم الحساب مطلوب")

        if self.cash_only and hasattr(self, "treasury_details_input"):
            treasury_type = self.treasury_type_combo.currentText().strip()
            details = self.treasury_details_input.toPlainText().strip()
            if treasury_type != "خزنة نقدية" and not details:
                is_valid = False
                error_messages.append("بيانات التحصيل أو التحويل مطلوبة")

        # Update validation message
        if error_messages:
            self.validation_label.setText("⚠️ " + " • ".join(error_messages))
            self.validation_label.setVisible(True)
        else:
            self.validation_label.setVisible(False)

        # Enable/disable save button
        self.save_button.setEnabled(is_valid)

        return is_valid

    def _on_type_changed(self, index):
        """Smart suggestions based on account type"""
        if self.cash_only:
            return
        account_type = self.type_combo.currentData()

        # Auto-suggest parent based on type
        if account_type == schemas.AccountType.CASH:
            # Suggest under "النقدية والخزائن" (1110)
            for i in range(self.parent_combo.count()):
                if "1110" in self.parent_combo.itemText(i):
                    self.parent_combo.setCurrentIndex(i)
                    break
        elif account_type == schemas.AccountType.EXPENSE:
            # Suggest under "المصروفات التشغيلية" (5100)
            for i in range(self.parent_combo.count()):
                if "5100" in self.parent_combo.itemText(i):
                    self.parent_combo.setCurrentIndex(i)
                    break
        elif account_type == schemas.AccountType.REVENUE:
            # Suggest under "إيرادات الخدمات" (4100)
            for i in range(self.parent_combo.count()):
                if "4100" in self.parent_combo.itemText(i):
                    self.parent_combo.setCurrentIndex(i)
                    break

    def _populate_parent_accounts(self):
        """ملء قائمة الحسابات الأب - مرتبة حسب الكود"""
        # ترتيب الحسابات حسب الكود لعرض الشجرة بشكل منطقي
        sorted_accounts = sorted(self.all_accounts, key=lambda x: str(x.code or ""))
        child_parent_refs = {
            str(parent_ref).strip()
            for account in self.all_accounts
            for parent_ref in ((account.parent_code or account.parent_id),)
            if parent_ref not in (None, "")
        }

        for acc in sorted_accounts:
            if not acc.code:
                continue
            acc_code = str(acc.code).strip()
            if self.cash_only:
                acc_type = getattr(acc, "type", None)
                acc_type_value = getattr(acc_type, "value", acc_type)
                is_cash = (
                    acc_type == schemas.AccountType.CASH
                    or acc_type_value in {"CASH", "أصول نقدية"}
                    or acc_code.startswith("111")
                )
                has_children = acc_code in child_parent_refs
                if not is_cash or not has_children:
                    continue
            # لا يمكن للحساب أن يكون أباً لنفسه
            if self.is_editing and acc.code == self.account_to_edit.code:
                continue
            # لا يمكن للحساب أن يكون أباً لأحد أبنائه (منع الحلقات)
            if self.is_editing and self._is_descendant(acc.code, self.account_to_edit.code):
                continue

            # إضافة مسافة بادئة للحسابات الفرعية
            indent = ""
            if acc.parent_code:
                indent = "  └─ "

            display_text = f"{indent}{acc_code} - {acc.name}"
            self.parent_combo.addItem(display_text, userData=acc_code)

    def _is_descendant(
        self, potential_child_code: str, ancestor_code: str, visited: set | None = None
    ) -> bool:
        """التحقق مما إذا كان الحساب من أحفاد حساب آخر (منع الحلقات الدائرية)"""
        if not potential_child_code or not ancestor_code:
            return False

        # منع الحلقات اللانهائية
        if visited is None:
            visited = set()

        if potential_child_code in visited:
            return False  # اكتشفنا حلقة دائرية، نوقف البحث

        visited.add(potential_child_code)

        # البحث في الشجرة - هل potential_child_code هو ابن لـ ancestor_code؟
        for acc in self.all_accounts:
            if acc.code == potential_child_code:
                if acc.parent_code == ancestor_code:
                    return True  # نعم، هو ابن مباشر
                elif acc.parent_code:
                    # نتحقق من الأب - هل الأب هو حفيد لـ ancestor_code؟
                    return self._is_descendant(acc.parent_code, ancestor_code, visited)
                break  # وجدنا الحساب، لا داعي للاستمرار
        return False

    def populate_fields(self):
        """تحميل بيانات الحساب للتعديل - FIXED: يحدد الحساب الأب بشكل صحيح"""
        if not self.account_to_edit:
            return

        safe_print(f"INFO: [AccountDialog] Loading account: {self.account_to_edit.name}")
        safe_print(
            f"INFO: [AccountDialog] parent_code = {self.account_to_edit.parent_code}, parent_id = {self.account_to_edit.parent_id}"
        )

        # 1. Code
        self.code_input.setText(self.account_to_edit.code or "")

        # 2. Name
        self.name_input.setText(self.account_to_edit.name or "")

        # 3. Type
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.account_to_edit.type:
                self.type_combo.setCurrentIndex(i)
                break

        # 4. Parent Account - استخدام parent_code أو parent_id (أيهما موجود)
        parent_code = self.account_to_edit.parent_code or self.account_to_edit.parent_id
        if parent_code:
            parent_code_str = str(parent_code).strip()
            safe_print(f"DEBUG: [AccountDialog] Searching for parent: '{parent_code_str}'")

            # البحث في جميع عناصر الـ combo
            found = False
            for i in range(self.parent_combo.count()):
                item_data = self.parent_combo.itemData(i)
                if item_data and str(item_data).strip() == parent_code_str:
                    self.parent_combo.setCurrentIndex(i)
                    safe_print(
                        f"SUCCESS: [AccountDialog] Parent found at index {i}: {parent_code_str}"
                    )
                    found = True
                    break

            if not found:
                # إذا لم يتم العثور، نحاول إضافته يدوياً
                safe_print(f"WARNING: [AccountDialog] Parent {parent_code_str} not found in combo")
                parent_account = next(
                    (acc for acc in self.all_accounts if str(acc.code).strip() == parent_code_str),
                    None,
                )
                if parent_account:
                    indent = "  └─ " if parent_account.parent_code else ""
                    display_text = f"{indent}{parent_account.code} - {parent_account.name}"
                    self.parent_combo.addItem(display_text, userData=str(parent_account.code))
                    self.parent_combo.setCurrentIndex(self.parent_combo.count() - 1)
                    safe_print(
                        f"SUCCESS: [AccountDialog] Added and selected parent: {parent_account.code}"
                    )
                else:
                    safe_print(
                        f"ERROR: [AccountDialog] Parent account {parent_code_str} not found anywhere!"
                    )
        else:
            # No parent - set to "No Parent" (index 0)
            self.parent_combo.setCurrentIndex(0)
            safe_print("INFO: [AccountDialog] No parent_code, setting to 'No Parent'")

        # 5. Currency
        if self.account_to_edit.currency:
            for i in range(self.currency_combo.count()):
                currency_data = self.currency_combo.itemData(i)
                if currency_data == self.account_to_edit.currency:
                    self.currency_combo.setCurrentIndex(i)
                    break

        # 6. Opening Balance
        self.balance_spinbox.setValue(self.account_to_edit.balance or 0.0)

        # 7. Description
        if self.cash_only:
            parsed = self._parse_treasury_description(self.account_to_edit.description)
            if parsed["treasury_type"] and hasattr(self, "treasury_type_combo"):
                index = self.treasury_type_combo.findText(parsed["treasury_type"])
                if index >= 0:
                    self.treasury_type_combo.setCurrentIndex(index)
            self._update_treasury_details_placeholder()
            if hasattr(self, "treasury_details_input"):
                self.treasury_details_input.setPlainText(parsed["details"])
            self.description_input.setPlainText(parsed["notes"])
            self._sync_cashbox_preset_from_current_fields()
        elif self.account_to_edit.description:
            self.description_input.setText(self.account_to_edit.description)

        # 8. Active Status
        is_active = self.account_to_edit.status == schemas.AccountStatus.ACTIVE
        self.active_checkbox.setChecked(is_active)

    def get_form_data(self) -> dict[str, Any]:
        """جمع البيانات من النموذج"""
        selected_parent_code = self.parent_combo.currentData()

        # التأكد من أن parent_code هو None إذا كان "بدون أب"
        if selected_parent_code is None or selected_parent_code == "":
            parent_code = None
        else:
            parent_code = str(selected_parent_code)

        data = {
            "code": self.code_input.text().strip(),
            "name": self.name_input.text().strip(),
            "type": schemas.AccountType.CASH if self.cash_only else self.type_combo.currentData(),
            "parent_code": parent_code,
            "currency": self.currency_combo.currentData(),
            "description": (
                self._serialize_treasury_description()
                if self.cash_only
                else self.description_input.toPlainText().strip()
            ),
            "status": (
                schemas.AccountStatus.ACTIVE
                if self.active_checkbox.isChecked()
                else schemas.AccountStatus.ARCHIVED
            ),
            "is_group": False,
        }

        # ⚠️ فقط أضف الرصيد الافتتاحي عند إنشاء حساب جديد
        # عند التعديل، لا نريد تغيير الرصيد المحسوب من القيود
        if not self.is_editing:
            data["balance"] = self.balance_spinbox.value()

        return data

    def validate_form(self) -> tuple[bool, str]:
        """التحقق من صحة البيانات المدخلة"""
        account_data = self.get_form_data()

        if not account_data["code"]:
            return False, "رمز الخزنة مطلوب" if self.cash_only else "كود الحساب مطلوب"

        if not account_data["name"]:
            return False, "اسم الخزنة مطلوب" if self.cash_only else "اسم الحساب مطلوب"

        if not account_data["type"]:
            return False, "نوع الخزنة مطلوب" if self.cash_only else "نوع الحساب مطلوب"

        # التحقق من تفرد الكود
        existing_codes = {acc.code for acc in self.all_accounts}
        if self.is_editing and self.account_to_edit is not None:
            existing_codes.discard(self.account_to_edit.code)

        if account_data["code"] in existing_codes:
            return False, (
                f"رمز الخزنة '{account_data['code']}' موجود مسبقاً"
                if self.cash_only
                else f"كود الحساب '{account_data['code']}' موجود مسبقاً"
            )

        # التحقق من صحة الحساب الأب
        if account_data["parent_code"]:
            parent_exists = any(
                acc.code == account_data["parent_code"] for acc in self.all_accounts
            )
            if not parent_exists:
                return False, (
                    f"الفئة الرئيسية '{account_data['parent_code']}' غير موجودة"
                    if self.cash_only
                    else f"الحساب الأب '{account_data['parent_code']}' غير موجود"
                )

        return True, "البيانات صحيحة"

    def save_account(self):
        """حفظ الحساب"""
        is_valid, error_message = self.validate_form()
        if not is_valid:
            QMessageBox.warning(self, "خطأ في البيانات", error_message)
            return

        account_data = self.get_form_data()

        try:
            if self.is_editing:
                # استخدام id أو _mongo_id أو code
                account_id = None
                if self.account_to_edit._mongo_id:
                    account_id = self.account_to_edit._mongo_id
                elif self.account_to_edit.id:
                    account_id = str(self.account_to_edit.id)

                # إذا لم يكن هناك id صالح، نستخدم الكود للتحديث
                if not account_id or account_id == "None":
                    self.accounting_service.update_account_by_code(
                        self.account_to_edit.code, account_data
                    )
                else:
                    self.accounting_service.update_account(account_id, account_data)
                QMessageBox.information(
                    self,
                    "تم التعديل",
                    (
                        f"تم حفظ تعديلات الخزنة '{account_data['name']}' بنجاح."
                        if self.cash_only
                        else f"تم حفظ تعديلات الحساب '{account_data['name']}' بنجاح."
                    ),
                )
            else:
                self.accounting_service.create_account(account_data)
                QMessageBox.information(
                    self,
                    "تم الإنشاء",
                    (
                        f"تمت إضافة الخزنة '{account_data['name']}' بنجاح."
                        if self.cash_only
                        else f"تم إضافة الحساب '{account_data['name']}' بنجاح."
                    ),
                )

            self.accept()

        except Exception as e:
            safe_print(f"ERROR: [AccountEditorDialog] Failed to save account: {e}")
            import traceback

            traceback.print_exc()

            QMessageBox.critical(
                self,
                "خطأ في الحفظ",
                (
                    f"فشل في حفظ الخزنة:\n{str(e)}"
                    if self.cash_only
                    else f"فشل في حفظ الحساب:\n{str(e)}"
                ),
            )
