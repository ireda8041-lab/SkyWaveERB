# الملف: ui/payments_manager.py
from __future__ import annotations

"""
تاب إدارة الدفعات - عرض وتعديل جميع الدفعات (تحصيلات العملاء)
⚡ محسّن: إضافة دفعة جديدة، تصفية، تصدير، تكامل محاسبي كامل
"""

import time
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from PyQt6.QtCore import QDate, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.account_filters import filter_operational_cashboxes, infer_payment_method_from_account
from ui.custom_spinbox import CustomSpinBox
from ui.smart_combobox import SmartFilterComboBox
from ui.styles import BUTTON_STYLES, TABLE_STYLE_DARK, create_centered_item, get_cairo_font

if TYPE_CHECKING:
    from services.accounting_service import AccountingService
    from services.client_service import ClientService
    from services.project_service import ProjectService

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


_SCHEMAS_MODULE = None


def _get_schemas_module():
    global _SCHEMAS_MODULE
    if _SCHEMAS_MODULE is None:
        from core import schemas as schemas_module

        _SCHEMAS_MODULE = schemas_module
    return _SCHEMAS_MODULE


class _SchemasProxy:
    def __getattr__(self, name: str):
        return getattr(_get_schemas_module(), name)


schemas = _SchemasProxy()


def to_decimal(value) -> Decimal:
    """تحويل آمن للقيم المالية إلى Decimal"""
    if value is None:
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _format_currency(value, placeholder: str = "0.00 ج.م") -> str:
    if value is None:
        return placeholder
    try:
        return f"{float(value):,.2f} ج.م"
    except Exception:
        return placeholder


def _payment_dialog_stylesheet() -> str:
    from ui.styles import COLORS, get_arrow_url

    return f"""
        * {{
            outline: none;
            font-family: 'Cairo';
        }}
        QDialog {{
            background-color: {COLORS['bg_dark']};
            color: {COLORS['text_primary']};
        }}
        QWidget#dialogContent {{
            background-color: {COLORS['bg_dark']};
        }}
        QFrame#sectionCard {{
            background-color: rgba(5, 32, 69, 0.94);
            border: 1px solid rgba(59, 130, 246, 0.2);
            border-radius: 16px;
        }}
        QFrame#detailsCard {{
            background-color: transparent;
            border: 1px solid rgba(59, 130, 246, 0.18);
            border-radius: 16px;
        }}
        QWidget#dialogFooter {{
            background-color: rgba(5, 32, 69, 0.96);
            border-top: 1px solid rgba(59, 130, 246, 0.16);
        }}
        QLabel#sectionBadge {{
            color: #dbeafe;
            background-color: rgba(37, 99, 235, 0.18);
            border: 1px solid rgba(96, 165, 250, 0.28);
            border-radius: 12px;
            padding: 5px 12px;
            font-size: 11px;
            font-weight: 700;
        }}
        QLabel#sectionHeading {{
            color: {COLORS['text_primary']};
            font-size: 12px;
            font-weight: 700;
        }}
        QLabel#projectHeadline {{
            color: #f8fafc;
            font-size: 14px;
            font-weight: 700;
        }}
        QLabel#fieldLabel,
        QLabel#surfaceCaption,
        QLabel#statCaption {{
            color: #cbd5e1;
            font-size: 11px;
            font-weight: 600;
        }}
        QLabel#hintLabel {{
            color: #93c5fd;
            font-size: 10px;
            font-weight: 500;
        }}
        QFrame#surfaceCard,
        QFrame#statCard,
        QFrame#pickerFrame {{
            background-color: rgba(15, 23, 42, 0.48);
            border: 1px solid rgba(96, 165, 250, 0.16);
            border-radius: 12px;
        }}
        QFrame#sectionDivider {{
            background-color: rgba(148, 163, 184, 0.18);
            border: none;
            min-height: 1px;
            max-height: 1px;
        }}
        QLabel#surfaceValue {{
            color: #f8fafc;
            font-size: 12px;
            font-weight: 700;
        }}
        QLabel#statValue {{
            color: #f8fafc;
            font-size: 12px;
            font-weight: 700;
        }}
        QLabel#valueBadge {{
            color: #f8fafc;
            background-color: rgba(14, 165, 233, 0.14);
            border: 1px solid rgba(14, 165, 233, 0.26);
            border-radius: 10px;
            padding: 5px 10px;
            font-size: 12px;
            font-weight: 700;
        }}
        QComboBox, QDateEdit, QLineEdit {{
            background-color: {COLORS['bg_medium']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
            padding: 8px 10px;
            font-size: 12px;
            min-height: 20px;
        }}
        QComboBox:hover, QDateEdit:hover, QLineEdit:hover {{
            border-color: rgba(96, 165, 250, 0.55);
        }}
        QComboBox:focus, QDateEdit:focus, QLineEdit:focus {{
            border: 1px solid {COLORS['primary']};
        }}
        QComboBox::drop-down, QDateEdit::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox::down-arrow, QDateEdit::down-arrow {{
            image: url({get_arrow_url("down")});
            width: 10px;
            height: 10px;
        }}
        QComboBox QLineEdit, QDateEdit QLineEdit {{
            background: transparent;
            border: none;
            padding: 0;
            min-height: 0;
            color: {COLORS['text_primary']};
        }}
        QComboBox QAbstractItemView {{
            background-color: {COLORS['bg_medium']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            selection-background-color: {COLORS['primary']};
        }}
        QPushButton#ghostButton {{
            background-color: rgba(37, 99, 235, 0.14);
            color: #dbeafe;
            border: 1px solid rgba(96, 165, 250, 0.2);
            border-radius: 10px;
            padding: 0 14px;
            min-height: 30px;
            min-width: 112px;
            font-size: 11px;
            font-weight: 700;
        }}
        QPushButton#ghostButton:hover {{
            background-color: rgba(37, 99, 235, 0.24);
        }}
        QPushButton#dialogPrimaryButton {{
            background-color: {COLORS['primary']};
            color: white;
            border: none;
            border-radius: 10px;
            padding: 0 18px;
            min-height: 32px;
            font-size: 12px;
            font-weight: 700;
        }}
        QPushButton#dialogPrimaryButton:hover {{
            background-color: {COLORS['primary_hover']};
        }}
        QPushButton#dialogPrimaryButton:disabled {{
            background-color: rgba(51, 65, 85, 0.95);
            color: #94a3b8;
        }}
        QPushButton#dialogSecondaryButton {{
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(57, 86, 123, 0.98),
                stop:1 rgba(29, 55, 87, 0.98)
            );
            color: #f8fafc;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 0 18px;
            min-height: 32px;
            font-size: 12px;
            font-weight: 700;
        }}
        QPushButton#dialogSecondaryButton:hover {{
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(67, 98, 137, 0.99),
                stop:1 rgba(36, 64, 99, 0.99)
            );
            border: 1px solid rgba(255, 255, 255, 0.14);
        }}
        QPushButton#dialogSecondaryButton:pressed {{
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(24, 46, 73, 0.99),
                stop:1 rgba(18, 35, 58, 0.99)
            );
        }}
    """


def _style_payment_amount_input(amount_input: CustomSpinBox):
    from ui.styles import COLORS

    amount_input.setFixedHeight(38)
    amount_input.spinbox.setStyleSheet(
        f"""
        QDoubleSpinBox {{
            background-color: {COLORS['bg_medium']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-right: none;
            border-top-left-radius: 10px;
            border-bottom-left-radius: 10px;
            border-top-right-radius: 0;
            border-bottom-right-radius: 0;
            padding: 8px 12px;
            min-height: 20px;
            font-size: 12px;
            font-weight: 700;
        }}
        QDoubleSpinBox:focus {{
            border: 1px solid {COLORS['primary']};
            border-right: none;
        }}
        """
    )
    amount_input.btn_plus.setStyleSheet(
        f"""
        QPushButton {{
            background-color: rgba(15, 23, 42, 0.92);
            color: {COLORS['text_secondary']};
            border: 1px solid {COLORS['border']};
            border-top-right-radius: 10px;
            border-bottom: none;
            min-width: 24px;
            max-width: 24px;
            min-height: 19px;
            max-height: 19px;
            font-size: 8px;
            font-weight: 700;
            padding: 0;
        }}
        QPushButton:hover {{
            background-color: {COLORS['primary']};
            color: white;
        }}
        QPushButton:pressed {{
            background-color: {COLORS['primary_dark']};
        }}
        """
    )
    amount_input.btn_minus.setStyleSheet(
        f"""
        QPushButton {{
            background-color: rgba(15, 23, 42, 0.92);
            color: {COLORS['text_secondary']};
            border: 1px solid {COLORS['border']};
            border-top: none;
            border-bottom-right-radius: 10px;
            min-width: 24px;
            max-width: 24px;
            min-height: 19px;
            max-height: 19px;
            font-size: 8px;
            font-weight: 700;
            padding: 0;
        }}
        QPushButton:hover {{
            background-color: {COLORS['primary']};
            color: white;
        }}
        QPushButton:pressed {{
            background-color: {COLORS['primary_dark']};
        }}
        """
    )


class NewPaymentDialog(QDialog):
    """
    ⚡ نافذة إضافة دفعة جديدة من التاب الرئيسية
    تدعم: اختيار المشروع، التحقق من المبلغ، التكامل المحاسبي
    """

    payment_created = pyqtSignal(object)  # إشارة عند إنشاء دفعة جديدة

    def __init__(
        self,
        project_service: ProjectService,
        accounting_service: AccountingService,
        client_service: ClientService,
        parent=None,
    ):
        super().__init__(parent)
        self.project_service = project_service
        self.accounting_service = accounting_service
        self.client_service = client_service
        self.selected_project: schemas.Project | None = None
        self.current_payment_method = "سيحدد تلقائيًا"
        self._client_name_cache: dict[str, str] = {}
        self._project_invoice_cache: dict[str, str] = {}

        self.setWindowTitle("إضافة دفعة جديدة")
        self.setMinimumWidth(680)
        self.setMinimumHeight(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        from ui.styles import apply_arrows_to_all_widgets, setup_custom_title_bar

        setup_custom_title_bar(self)
        self._apply_dialog_style()
        self._setup_ui()
        self._load_data()
        self._refresh_project_summary()
        self._update_payment_method()
        self._finalize_dialog_size()
        apply_arrows_to_all_widgets(self)

    def _apply_dialog_style(self):
        self.setStyleSheet(_payment_dialog_stylesheet())

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        content_widget = QWidget()
        content_widget.setObjectName("dialogContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(12, 12, 12, 6)

        self.project_frame = self._create_section_card()
        project_layout = QVBoxLayout(self.project_frame)
        project_layout.setContentsMargins(12, 12, 12, 12)
        project_layout.setSpacing(6)

        badge = QLabel("المشروع المرتبط")
        badge.setObjectName("sectionBadge")
        badge.setFont(get_cairo_font(11, bold=True))
        project_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignRight)

        heading = QLabel("اختر المشروع الذي سيتم تسجيل الدفعة عليه")
        heading.setObjectName("sectionHeading")
        heading.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        project_layout.addWidget(heading)

        self.project_combo = SmartFilterComboBox()
        self.project_combo.setFixedHeight(38)
        self.project_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.project_combo.setMinimumContentsLength(22)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        if self.project_combo.lineEdit():
            self.project_combo.lineEdit().setPlaceholderText(
                "ابحث باسم المشروع أو العميل أو رقم الفاتورة"
            )
        project_layout.addWidget(self._create_field_block("المشروع", self.project_combo))

        self.project_search_hint = QLabel(
            "يمكنك البحث باسم المشروع أو العميل أو رقم الفاتورة للوصول إليه سريعًا."
        )
        self.project_search_hint.setObjectName("hintLabel")
        self.project_search_hint.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        self.project_search_hint.setWordWrap(True)
        project_layout.addWidget(self.project_search_hint)

        self.project_name_label = QLabel("اختر مشروعًا للبدء")
        self.project_name_label.setObjectName("projectHeadline")
        self.project_name_label.setFont(get_cairo_font(13, bold=True))
        self.project_name_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        self.project_name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        self.project_name_label.setWordWrap(True)
        project_layout.addWidget(self.project_name_label)

        project_meta_layout = QGridLayout()
        project_meta_layout.setHorizontalSpacing(8)
        project_meta_layout.setVerticalSpacing(8)
        project_meta_layout.addWidget(
            self._create_meta_surface("العميل المرتبط", "project_meta_label"), 0, 0
        )
        project_meta_layout.addWidget(
            self._create_meta_surface("رقم الفاتورة", "project_invoice_label"), 0, 1
        )
        project_meta_layout.setColumnStretch(0, 1)
        project_meta_layout.setColumnStretch(1, 1)
        project_layout.addLayout(project_meta_layout)

        project_stats_layout = QGridLayout()
        project_stats_layout.setHorizontalSpacing(8)
        project_stats_layout.setVerticalSpacing(8)
        project_stats_layout.addWidget(
            self._create_stat_surface("إجمالي المشروع", "project_total_value_label", "#38bdf8"),
            0,
            0,
        )
        project_stats_layout.addWidget(
            self._create_stat_surface("المدفوع", "project_paid_value_label", "#22c55e"),
            0,
            1,
        )
        project_stats_layout.addWidget(
            self._create_stat_surface("المتبقي", "project_remaining_value_label", "#f97316"),
            0,
            2,
        )
        for column in range(3):
            project_stats_layout.setColumnStretch(column, 1)
        project_layout.addLayout(project_stats_layout)
        content_layout.addWidget(self.project_frame)

        details_frame = self._create_section_card("detailsCard")
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(6)

        details_title = QLabel("تفاصيل الدفعة")
        details_title.setObjectName("sectionHeading")
        details_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        details_layout.addWidget(details_title)

        self.account_combo = SmartFilterComboBox()
        self.account_combo.setFixedHeight(38)
        self.account_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.account_combo.setMinimumContentsLength(20)
        self.account_combo.currentIndexChanged.connect(self._update_payment_method)
        if self.account_combo.lineEdit():
            self.account_combo.lineEdit().setPlaceholderText("ابحث عن الحساب المستلم")
        details_layout.addWidget(self._create_field_block("الحساب المستلم", self.account_combo))

        amount_date_row = QHBoxLayout()
        amount_date_row.setSpacing(8)

        self.amount_input = CustomSpinBox(decimals=2, minimum=0.0, maximum=100_000_000)
        self.amount_input.setSuffix(" ج.م")
        self.amount_input.valueChanged.connect(self._validate_payment)
        self._style_amount_input()
        amount_date_row.addWidget(self._create_field_block("المبلغ", self.amount_input), 1)

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setFixedHeight(38)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        amount_date_row.addWidget(self._create_field_block("التاريخ", self.date_input), 1)
        details_layout.addLayout(amount_date_row)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(8)

        self.method_value_label = self._build_value_badge("method_value_label")
        self.method_label = self.method_value_label
        footer_row.addWidget(self._create_field_block("طريقة الدفع", self.method_value_label), 1)

        self._build_value_badge("invoice_value_label")
        footer_row.addWidget(self._create_field_block("رقم الفاتورة", self.invoice_value_label), 1)
        details_layout.addLayout(footer_row)
        content_layout.addWidget(details_frame)

        main_layout.addWidget(content_widget)

        buttons_container = QWidget()
        buttons_container.setObjectName("dialogFooter")
        buttons_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(12, 8, 12, 8)
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()

        self.save_btn = QPushButton("حفظ الدفعة")
        self.save_btn.setObjectName("dialogPrimaryButton")
        self.save_btn.setFixedSize(118, 34)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_payment)
        buttons_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.setObjectName("dialogSecondaryButton")
        self.cancel_btn.setFixedSize(118, 34)
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        main_layout.addWidget(buttons_container)

    def _create_section_card(self, object_name: str = "sectionCard") -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        return card

    def _create_meta_surface(self, title: str, label_attr: str) -> QFrame:
        surface = QFrame()
        surface.setObjectName("surfaceCard")
        surface.setMinimumHeight(50)
        surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(10, 6, 10, 6)
        surface_layout.setSpacing(2)

        caption = QLabel(title)
        caption.setObjectName("surfaceCaption")
        surface_layout.addWidget(caption)

        value_label = QLabel("")
        value_label.setObjectName("surfaceValue")
        value_label.setWordWrap(True)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        surface_layout.addWidget(value_label)
        setattr(self, label_attr, value_label)
        return surface

    def _create_stat_surface(self, title: str, label_attr: str, accent_color: str) -> QFrame:
        surface = QFrame()
        surface.setObjectName("statCard")
        surface.setMinimumHeight(48)
        surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(10, 6, 10, 6)
        surface_layout.setSpacing(2)

        caption = QLabel(title)
        caption.setObjectName("statCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        surface_layout.addWidget(caption)

        value_label = QLabel("--")
        value_label.setObjectName("statValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet(f"color: {accent_color};")
        surface_layout.addWidget(value_label)
        setattr(self, label_attr, value_label)
        return surface

    def _build_value_badge(self, label_attr: str) -> QLabel:
        badge = QLabel("")
        badge.setObjectName("valueBadge")
        badge.setFixedHeight(38)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setattr(self, label_attr, badge)
        return badge

    def _create_field_block(self, label_text: str, widget: QWidget) -> QWidget:
        block = QWidget()
        block.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(3)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        block_layout.addWidget(label)
        block_layout.addWidget(widget)
        return block

    def _style_amount_input(self):
        _style_payment_amount_input(self.amount_input)

    def _finalize_dialog_size(self):
        self.layout().activate()
        self.adjustSize()
        width = max(680, self.sizeHint().width())
        height = max(468, self.sizeHint().height())
        self.setFixedSize(width, height)

    def _load_data(self):
        self.project_combo.clear()
        self.project_combo.addItem("اختر المشروع المرتبط", userData=None)
        try:
            repo = getattr(self.project_service, "repo", None)
            if repo is not None and hasattr(repo, "get_all_clients"):
                for client in repo.get_all_clients() or []:
                    client_name = str(getattr(client, "name", "") or "").strip()
                    if not client_name:
                        continue
                    client_id = str(getattr(client, "id", "") or "").strip()
                    mongo_id = str(getattr(client, "_mongo_id", "") or "").strip()
                    if client_id:
                        self._client_name_cache[client_id] = client_name
                    if mongo_id:
                        self._client_name_cache[mongo_id] = client_name
            if repo is not None and hasattr(repo, "get_all_invoice_numbers"):
                self._project_invoice_cache.update(repo.get_all_invoice_numbers() or {})

            projects = sorted(
                self.project_service.get_all_projects() or [],
                key=lambda project: (
                    str(getattr(project, "name", "") or "").strip().lower(),
                    str(getattr(project, "invoice_number", "") or "").strip().lower(),
                ),
            )
            for project in projects:
                self.project_combo.addItem(self._project_display_text(project), userData=project)
        except Exception as e:
            safe_print(f"ERROR: [NewPaymentDialog] فشل تحميل المشاريع: {e}")

        self.account_combo.clear()
        self.account_combo.addItem("اختر الحساب المستلم", userData=None)
        try:
            for account in self._get_cash_accounts():
                self.account_combo.addItem(
                    f"💰 {account.name} ({account.code})",
                    userData=account,
                )
        except Exception as e:
            safe_print(f"ERROR: [NewPaymentDialog] فشل تحميل الحسابات: {e}")

        self.project_combo.setCurrentIndex(0)
        self.account_combo.setCurrentIndex(0)
        self._validate_payment()

    def _get_cash_accounts(self) -> list[schemas.Account]:
        """جلب حسابات النقدية والبنوك"""
        try:
            all_accounts = self.accounting_service.repo.get_all_accounts()
            return filter_operational_cashboxes(all_accounts)
        except Exception:
            return []

    def _on_project_selected(self, index: int):
        self.selected_project = self.project_combo.currentData() if index > 0 else None
        remaining = self._refresh_project_summary()
        if self.selected_project and remaining is not None and self.amount_input.value() <= 0:
            self.amount_input.setValue(max(float(remaining), 0.0))
        self._validate_payment()

    def _update_payment_method(self):
        """تحديث طريقة الدفع حسب الحساب"""
        account = self.account_combo.currentData()
        if not account:
            self.current_payment_method = "سيحدد تلقائيًا"
            self.method_label.setText(self.current_payment_method)
            self._validate_payment()
            return

        self.current_payment_method = self._get_payment_method_from_account(account)
        self.method_label.setText(self.current_payment_method)
        self._validate_payment()

    def _get_payment_method_from_account(self, account: schemas.Account | None) -> str:
        """⚡ تحديد طريقة الدفع من الحساب - يدعم نظام 4 و 6 أرقام"""
        if not account:
            return "Other"
        return infer_payment_method_from_account(account)

    def _project_ref(self, project: schemas.Project | None, fallback: str = "") -> str:
        if project is None:
            return str(fallback or "").strip()
        if self.project_service and hasattr(self.project_service, "_project_ref"):
            return str(
                self.project_service._project_ref(project, fallback or project.name) or ""
            ).strip()
        return str(
            getattr(project, "id", None)
            or getattr(project, "_mongo_id", None)
            or getattr(project, "name", fallback)
            or ""
        ).strip()

    def _get_client_name(self, client_id: str) -> str:
        client_ref = str(client_id or "").strip()
        if not client_ref:
            return ""
        if client_ref in self._client_name_cache:
            return self._client_name_cache[client_ref]
        try:
            client = self.client_service.get_client_by_id(client_ref)
            client_name = str(getattr(client, "name", "") or client_ref).strip()
            self._client_name_cache[client_ref] = client_name
            return client_name
        except Exception:
            return client_ref

    def _resolve_invoice_number_for_project(
        self, project: schemas.Project | None, *, ensure: bool = False
    ) -> str:
        if project is None:
            return ""
        project_ref = self._project_ref(project, getattr(project, "name", ""))
        if project_ref in self._project_invoice_cache:
            return self._project_invoice_cache[project_ref]

        invoice_number = str(getattr(project, "invoice_number", "") or "").strip()
        if invoice_number:
            self._project_invoice_cache[project_ref] = invoice_number
            return invoice_number

        repo = getattr(self.project_service, "repo", None)
        if repo is not None and hasattr(repo, "get_invoice_number_for_project"):
            try:
                invoice_number = str(
                    repo.get_invoice_number_for_project(
                        project_ref,
                        getattr(project, "client_id", None),
                    )
                    or ""
                ).strip()
                if invoice_number:
                    self._project_invoice_cache[project_ref] = invoice_number
                    return invoice_number
            except Exception as exc:
                safe_print(
                    f"WARNING: [Payments] تعذر جلب رقم فاتورة المشروع '{project_ref}': {exc}"
                )

        if ensure and repo is not None and hasattr(repo, "ensure_invoice_number"):
            try:
                invoice_number = str(
                    repo.ensure_invoice_number(
                        project_ref,
                        getattr(project, "client_id", None),
                    )
                    or ""
                ).strip()
                if invoice_number:
                    self._project_invoice_cache[project_ref] = invoice_number
                return invoice_number
            except Exception as exc:
                safe_print(
                    f"WARNING: [Payments] تعذر توليد رقم فاتورة للمشروع '{project_ref}': {exc}"
                )
                return ""
        return ""

    def _project_display_text(self, project: schemas.Project) -> str:
        project_name = str(getattr(project, "name", "") or "").strip() or "بدون اسم"
        client_name = self._get_client_name(getattr(project, "client_id", "") or "")
        invoice_number = self._resolve_invoice_number_for_project(project)
        extra_parts = []
        if invoice_number:
            extra_parts.append(f"فاتورة: {invoice_number}")
        if client_name:
            extra_parts.append(f"عميل: {client_name}")
        suffix = f" - {' - '.join(extra_parts)}" if extra_parts else ""
        return f"📁 {project_name}{suffix}"

    def _refresh_project_summary(self):
        project = self.selected_project
        if not project:
            self.project_name_label.setText("اختر مشروعًا للبدء")
            self.project_meta_label.setText("سيظهر العميل هنا")
            self.project_invoice_label.setText("سيظهر رقم الفاتورة هنا")
            self.invoice_value_label.setText("غير محدد")
            self.project_total_value_label.setText("--")
            self.project_paid_value_label.setText("--")
            self.project_remaining_value_label.setText("--")
            self.setWindowTitle("إضافة دفعة جديدة")
            return None

        project_name = str(getattr(project, "name", "") or "").strip() or "غير محدد"
        client_name = self._get_client_name(getattr(project, "client_id", "") or "")
        invoice_number = self._resolve_invoice_number_for_project(project, ensure=True)

        self.project_name_label.setText(project_name)
        self.project_meta_label.setText(client_name or "غير محدد")
        self.project_invoice_label.setText(invoice_number or "سيُنشأ تلقائيًا")
        self.invoice_value_label.setText(invoice_number or "سيُنشأ تلقائيًا")
        self.setWindowTitle(f"إضافة دفعة - {project_name}")

        remaining = None
        try:
            project_ref = self._project_ref(project, project_name)
            profit_data = self.project_service.get_project_profitability(
                project_ref,
                client_id=getattr(project, "client_id", None),
            )
            total = profit_data.get("total_revenue", 0)
            paid = profit_data.get("total_paid", 0)
            remaining = profit_data.get("balance_due", 0)
            self.project_total_value_label.setText(_format_currency(total, "--"))
            self.project_paid_value_label.setText(_format_currency(paid, "--"))
            self.project_remaining_value_label.setText(_format_currency(remaining, "--"))
        except Exception as e:
            safe_print(f"ERROR: [NewPaymentDialog] فشل جلب بيانات المشروع: {e}")
            self.project_total_value_label.setText("--")
            self.project_paid_value_label.setText("--")
            self.project_remaining_value_label.setText("--")
        return remaining

    def _validate_payment(self):
        """التحقق من صحة البيانات"""
        is_valid = True

        if not self.selected_project:
            is_valid = False

        if not self.account_combo.currentData():
            is_valid = False

        if self.amount_input.value() <= 0:
            is_valid = False

        self.save_btn.setEnabled(is_valid)

    def _cleanup_smart_combos(self):
        for combo in self.findChildren(SmartFilterComboBox):
            combo.shutdown()

    def reject(self):
        self._cleanup_smart_combos()
        super().reject()

    def done(self, result: int):
        self._cleanup_smart_combos()
        super().done(result)

    def _save_payment(self):
        """حفظ الدفعة"""
        # ⚡ منع الضغط المزدوج - تعطيل الزر فوراً
        if not self.save_btn.isEnabled():
            return
        self.save_btn.setEnabled(False)
        self.save_btn.setText("جارٍ الحفظ")

        if not self.selected_project:
            QMessageBox.warning(self, "تنبيه", "يرجى اختيار المشروع أولاً.")
            self.save_btn.setEnabled(True)
            self.save_btn.setText("حفظ الدفعة")
            return

        account = self.account_combo.currentData()
        if not account:
            QMessageBox.warning(self, "تنبيه", "يرجى اختيار حساب الاستلام.")
            self.save_btn.setEnabled(True)
            self.save_btn.setText("حفظ الدفعة")
            return

        amount = self.amount_input.value()
        if amount <= 0:
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال مبلغ صحيح.")
            self.save_btn.setEnabled(True)
            self.save_btn.setText("حفظ الدفعة")
            return

        # تحذير إذا كان المبلغ أكبر من المتبقي
        try:
            project_ref = str(
                getattr(self.selected_project, "id", None)
                or getattr(self.selected_project, "_mongo_id", None)
                or self.selected_project.name
            )
            profit_data = self.project_service.get_project_profitability(
                project_ref,
                client_id=getattr(self.selected_project, "client_id", None),
            )
            remaining = profit_data.get("balance_due", 0)
            if amount > remaining > 0:
                reply = QMessageBox.question(
                    self,
                    "تأكيد",
                    f"المبلغ المدخل ({amount:,.2f}) أكبر من المتبقي ({remaining:,.2f}).\n\nهل تريد المتابعة؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    self.save_btn.setEnabled(True)
                    self.save_btn.setText("حفظ الدفعة")
                    return
        except Exception as exc:
            safe_print(f"WARNING: [Payments] تعذر التحقق من تجاوز المتبقي قبل تسجيل الدفعة: {exc}")

        try:
            # إنشاء الدفعة
            payment = self.project_service.create_payment_for_project(
                project=self.selected_project,
                amount=amount,
                date=self.date_input.dateTime().toPyDateTime(),
                account_id=account.code,
                method=self.current_payment_method if account else None,
            )

            if payment:
                self.payment_created.emit(payment)
                QMessageBox.information(self, "تم", "تم تسجيل الدفعة بنجاح.")
                self.accept()
            else:
                QMessageBox.warning(self, "خطأ", "فشل تسجيل الدفعة.")
                self.save_btn.setEnabled(True)
                self.save_btn.setText("حفظ الدفعة")

        except Exception as e:
            error_msg = str(e)
            if "مكررة" in error_msg or "duplicate" in error_msg.lower():
                QMessageBox.warning(self, "دفعة مكررة", f"يوجد دفعة بنفس البيانات:\n{error_msg}")
            else:
                QMessageBox.critical(self, "خطأ", f"فشل تسجيل الدفعة: {e}")
            self.save_btn.setEnabled(True)
            self.save_btn.setText("حفظ الدفعة")


class PaymentEditorDialog(QDialog):
    """نافذة تعديل دفعة موجودة"""

    def __init__(
        self,
        *,
        payment: schemas.Payment,
        accounts: list[schemas.Account],
        accounting_service: AccountingService,
        project_service: ProjectService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.payment = payment
        self.accounts = accounts
        self.accounting_service = accounting_service
        self.project_service = project_service
        self.original_amount = to_decimal(payment.amount)
        self.original_account_id = payment.account_id
        self.current_payment_method = str(getattr(payment, "method", "") or "Other")
        self.selected_project: schemas.Project | None = None
        self._projects_loaded = False
        self._client_name_cache: dict[str, str] = {}
        self._project_invoice_cache: dict[str, str] = {}
        self._resize_sync_timer = QTimer(self)
        self._resize_sync_timer.setSingleShot(True)
        self._resize_sync_timer.timeout.connect(self._sync_dialog_size)
        self._project_stats_timer = QTimer(self)
        self._project_stats_timer.setSingleShot(True)
        self._project_stats_timer.timeout.connect(self._refresh_project_stats)
        self.setWindowTitle(f"تعديل دفعة - {payment.project_id}")
        self.setMinimumWidth(680)
        self.setMinimumHeight(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        from ui.styles import apply_arrows_to_all_widgets, setup_custom_title_bar

        setup_custom_title_bar(self)
        self._apply_dialog_style()
        self._setup_ui()
        self._refresh_project_summary()
        apply_arrows_to_all_widgets(self)

    def _apply_dialog_style(self):
        self.setStyleSheet(_payment_dialog_stylesheet())

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        content_widget = QWidget()
        content_widget.setObjectName("dialogContent")
        self._content_widget = content_widget
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(12, 12, 12, 6)

        self.project_frame = self._create_section_card()
        project_layout = QVBoxLayout(self.project_frame)
        project_layout.setContentsMargins(12, 12, 12, 12)
        project_layout.setSpacing(6)

        project_header = QHBoxLayout()
        project_header.setSpacing(8)

        self.project_section_title = QLabel("المشروع المرتبط")
        self.project_section_title.setObjectName("sectionBadge")
        self.project_section_title.setFont(get_cairo_font(11, bold=True))
        project_header.addWidget(self.project_section_title, 0, Qt.AlignmentFlag.AlignRight)

        project_header.addStretch()

        self.change_project_btn = QPushButton("تغيير المشروع")
        self.change_project_btn.setObjectName("ghostButton")
        self.change_project_btn.clicked.connect(self._toggle_project_picker)
        project_header.addWidget(self.change_project_btn)
        project_layout.addLayout(project_header)

        current_project_label = QLabel("البيانات الحالية")
        current_project_label.setObjectName("sectionHeading")
        current_project_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        project_layout.addWidget(current_project_label)

        self.project_name_label = QLabel("")
        self.project_name_label.setObjectName("projectHeadline")
        self.project_name_label.setFont(get_cairo_font(13, bold=True))
        self.project_name_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        self.project_name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        self.project_name_label.setWordWrap(True)
        project_layout.addWidget(self.project_name_label)

        project_meta_layout = QGridLayout()
        project_meta_layout.setHorizontalSpacing(8)
        project_meta_layout.setVerticalSpacing(8)
        project_meta_layout.addWidget(
            self._create_meta_surface("العميل المرتبط", "project_meta_label"), 0, 0
        )
        project_meta_layout.addWidget(
            self._create_meta_surface("رقم الفاتورة", "project_invoice_label"), 0, 1
        )
        project_meta_layout.setColumnStretch(0, 1)
        project_meta_layout.setColumnStretch(1, 1)
        project_layout.addLayout(project_meta_layout)

        project_stats_layout = QGridLayout()
        project_stats_layout.setHorizontalSpacing(8)
        project_stats_layout.setVerticalSpacing(8)
        project_stats_layout.addWidget(
            self._create_stat_surface("إجمالي المشروع", "project_total_value_label", "#38bdf8"),
            0,
            0,
        )
        project_stats_layout.addWidget(
            self._create_stat_surface("المدفوع", "project_paid_value_label", "#22c55e"),
            0,
            1,
        )
        project_stats_layout.addWidget(
            self._create_stat_surface("المتبقي", "project_remaining_value_label", "#f97316"),
            0,
            2,
        )
        for column in range(3):
            project_stats_layout.setColumnStretch(column, 1)
        project_layout.addLayout(project_stats_layout)

        divider = QFrame()
        divider.setObjectName("sectionDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        project_layout.addWidget(divider)

        self.project_picker_frame = QFrame()
        self.project_picker_frame.setObjectName("pickerFrame")
        picker_layout = QVBoxLayout(self.project_picker_frame)
        picker_layout.setContentsMargins(10, 10, 10, 10)
        picker_layout.setSpacing(6)

        self.project_search_hint = QLabel(
            "ابحث باسم المشروع أو العميل أو رقم الفاتورة ثم اختر النتيجة المناسبة."
        )
        self.project_search_hint.setObjectName("hintLabel")
        self.project_search_hint.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        self.project_search_hint.setWordWrap(True)
        picker_layout.addWidget(self.project_search_hint)

        self.project_combo = SmartFilterComboBox()
        self.project_combo.setMinimumWidth(0)
        self.project_combo.setFixedHeight(38)
        self.project_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.project_combo.setMinimumContentsLength(20)
        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        if self.project_combo.lineEdit():
            self.project_combo.lineEdit().setPlaceholderText(
                "ابحث باسم المشروع أو العميل أو رقم الفاتورة"
            )
        picker_layout.addWidget(self.project_combo)

        project_layout.addWidget(self.project_picker_frame)
        content_layout.addWidget(self.project_frame)

        details_frame = self._create_section_card("detailsCard")
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(6)

        details_title = QLabel("تفاصيل الدفعة")
        details_title.setObjectName("sectionHeading")
        details_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        details_layout.addWidget(details_title)

        self.account_combo = SmartFilterComboBox()
        self.account_combo.setFixedHeight(38)
        self.account_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.account_combo.setMinimumContentsLength(18)
        if self.account_combo.lineEdit():
            self.account_combo.lineEdit().setPlaceholderText("ابحث عن الحساب المستلم")

        selected_index = 0
        for i, acc in enumerate(self.accounts):
            display_text = f"💰 {acc.name} ({acc.code})"
            self.account_combo.addItem(display_text, userData=acc)
            if acc.code == self.payment.account_id:
                selected_index = i
        self.account_combo.setCurrentIndex(selected_index)
        self.account_combo.currentIndexChanged.connect(self._update_payment_method_from_account)
        details_layout.addWidget(self._create_field_block("الحساب المستلم", self.account_combo))

        details_row = QHBoxLayout()
        details_row.setSpacing(8)

        self.amount_input = CustomSpinBox(decimals=2, minimum=0.01, maximum=100_000_000)
        self.amount_input.setSuffix(" ج.م")
        self.amount_input.setValue(self.payment.amount)
        self._style_amount_input()
        details_row.addWidget(self._create_field_block("المبلغ", self.amount_input), 1)

        self.date_input = QDateEdit()
        self.date_input.setFixedHeight(38)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        if self.payment.date:
            self.date_input.setDate(
                QDate(self.payment.date.year, self.payment.date.month, self.payment.date.day)
            )
        else:
            self.date_input.setDate(QDate.currentDate())
        details_row.addWidget(self._create_field_block("التاريخ", self.date_input), 1)

        details_layout.addLayout(details_row)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(8)

        self.method_value_label = self._build_value_badge("method_value_label")
        self.method_value_label.setText(self.current_payment_method)
        self._update_payment_method_from_account()
        footer_row.addWidget(self._create_field_block("طريقة الدفع", self.method_value_label), 1)

        footer_row.addWidget(
            self._create_field_block(
                "رقم الفاتورة", self._build_value_badge("invoice_value_label")
            ),
            1,
        )
        details_layout.addLayout(footer_row)

        content_layout.addWidget(details_frame)
        main_layout.addWidget(content_widget)

        buttons_container = QWidget()
        buttons_container.setObjectName("dialogFooter")
        buttons_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(12, 8, 12, 8)
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()

        self.save_btn = QPushButton("حفظ الدفعة")
        self.save_btn.setObjectName("dialogPrimaryButton")
        self.save_btn.setFixedSize(118, 34)
        self.save_btn.clicked.connect(self.save_changes)
        buttons_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.setObjectName("dialogSecondaryButton")
        self.cancel_btn.setFixedSize(118, 34)
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        main_layout.addWidget(buttons_container)
        self._set_project_picker_visible(False)
        self._apply_initial_dialog_size()

    def _create_section_card(self, object_name: str = "sectionCard") -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        return card

    def _create_meta_surface(self, title: str, label_attr: str) -> QFrame:
        surface = QFrame()
        surface.setObjectName("surfaceCard")
        surface.setMinimumHeight(50)
        surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(10, 6, 10, 6)
        surface_layout.setSpacing(2)

        caption = QLabel(title)
        caption.setObjectName("surfaceCaption")
        surface_layout.addWidget(caption)

        value_label = QLabel("")
        value_label.setObjectName("surfaceValue")
        value_label.setWordWrap(True)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        surface_layout.addWidget(value_label)
        setattr(self, label_attr, value_label)
        return surface

    def _create_stat_surface(self, title: str, label_attr: str, accent_color: str) -> QFrame:
        surface = QFrame()
        surface.setObjectName("statCard")
        surface.setMinimumHeight(48)
        surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(10, 6, 10, 6)
        surface_layout.setSpacing(2)

        caption = QLabel(title)
        caption.setObjectName("statCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        surface_layout.addWidget(caption)

        value_label = QLabel("--")
        value_label.setObjectName("statValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet(f"color: {accent_color};")
        surface_layout.addWidget(value_label)
        setattr(self, label_attr, value_label)
        return surface

    def _create_field_block(self, label_text: str, widget: QWidget) -> QWidget:
        block = QWidget()
        block.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(3)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        block_layout.addWidget(label)
        block_layout.addWidget(widget)
        return block

    def _style_amount_input(self):
        _style_payment_amount_input(self.amount_input)

    def _build_value_badge(self, label_attr: str) -> QLabel:
        badge = QLabel("")
        badge.setObjectName("valueBadge")
        badge.setFixedHeight(38)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setattr(self, label_attr, badge)
        return badge

    def _project_ref(self, project: schemas.Project | None, fallback: str = "") -> str:
        if project is None:
            return str(fallback or "").strip()
        if self.project_service and hasattr(self.project_service, "_project_ref"):
            return str(
                self.project_service._project_ref(project, fallback or project.name) or ""
            ).strip()
        return str(
            getattr(project, "id", None)
            or getattr(project, "_mongo_id", None)
            or getattr(project, "name", fallback)
            or ""
        ).strip()

    def _get_client_name(self, client_id: str) -> str:
        client_ref = str(client_id or "").strip()
        if not client_ref:
            return ""
        if client_ref in self._client_name_cache:
            return self._client_name_cache[client_ref]
        if not self.project_service:
            return client_ref
        repo = getattr(self.project_service, "repo", None)
        if repo is None or not hasattr(repo, "get_client_by_id"):
            return client_ref
        try:
            client = repo.get_client_by_id(client_ref)
            client_name = str(getattr(client, "name", "") or client_ref).strip()
            self._client_name_cache[client_ref] = client_name
            return client_name
        except Exception:
            return client_ref

    def _resolve_invoice_number_for_project(
        self, project: schemas.Project | None, *, ensure: bool = False
    ) -> str:
        if project is None:
            return str(getattr(self.payment, "invoice_number", "") or "").strip()
        project_ref = self._project_ref(project, project.name)
        if project_ref in self._project_invoice_cache:
            return self._project_invoice_cache[project_ref]
        invoice_number = str(getattr(project, "invoice_number", "") or "").strip()
        if invoice_number:
            self._project_invoice_cache[project_ref] = invoice_number
            return invoice_number
        repo = getattr(self.project_service, "repo", None) if self.project_service else None
        if repo is not None and hasattr(repo, "get_invoice_number_for_project"):
            try:
                invoice_number = str(
                    repo.get_invoice_number_for_project(
                        project_ref,
                        getattr(project, "client_id", None),
                    )
                    or ""
                ).strip()
                if invoice_number:
                    self._project_invoice_cache[project_ref] = invoice_number
                return invoice_number
            except Exception as exc:
                safe_print(
                    f"WARNING: [Payments] تعذر جلب رقم فاتورة المشروع '{project_ref}' أثناء التعديل: {exc}"
                )
        if ensure and repo is not None and hasattr(repo, "ensure_invoice_number"):
            try:
                invoice_number = str(
                    repo.ensure_invoice_number(
                        project_ref,
                        getattr(project, "client_id", None),
                    )
                    or ""
                ).strip()
                if invoice_number:
                    self._project_invoice_cache[project_ref] = invoice_number
                return invoice_number
            except Exception as exc:
                safe_print(
                    f"WARNING: [Payments] تعذر توليد رقم فاتورة للمشروع '{project_ref}' أثناء التعديل: {exc}"
                )
                return ""
        return ""

    def _project_display_text(self, project: schemas.Project) -> str:
        project_name = str(getattr(project, "name", "") or "").strip() or "بدون اسم"
        client_name = self._get_client_name(getattr(project, "client_id", "") or "")
        invoice_number = self._resolve_invoice_number_for_project(project)
        extra_parts = []
        if invoice_number:
            extra_parts.append(f"فاتورة: {invoice_number}")
        if client_name:
            extra_parts.append(f"عميل: {client_name}")
        suffix = f" - {' - '.join(extra_parts)}" if extra_parts else ""
        return f"📁 {project_name}{suffix}"

    def _project_matches_payment(self, project: schemas.Project) -> bool:
        payment_project_ref = str(getattr(self.payment, "project_id", "") or "").strip()
        payment_invoice_number = str(getattr(self.payment, "invoice_number", "") or "").strip()
        candidates = {
            self._project_ref(project, getattr(project, "name", "")),
            str(getattr(project, "id", "") or "").strip(),
            str(getattr(project, "_mongo_id", "") or "").strip(),
            str(getattr(project, "name", "") or "").strip(),
            str(getattr(project, "invoice_number", "") or "").strip(),
        }
        candidates = {candidate for candidate in candidates if candidate}
        return payment_project_ref in candidates or (
            payment_invoice_number and payment_invoice_number in candidates
        )

    def _load_project_options(self):
        if not self.project_service or self._projects_loaded:
            if not self.project_service:
                self.change_project_btn.setEnabled(False)
                self.change_project_btn.setToolTip("خدمة المشاريع غير متاحة في هذا السياق.")
            return
        self._projects_loaded = True
        self.project_combo.clear()
        try:
            repo = getattr(self.project_service, "repo", None)
            if repo is not None and hasattr(repo, "get_all_clients"):
                for client in repo.get_all_clients() or []:
                    client_name = str(getattr(client, "name", "") or "").strip()
                    if not client_name:
                        continue
                    client_id = str(getattr(client, "id", "") or "").strip()
                    mongo_id = str(getattr(client, "_mongo_id", "") or "").strip()
                    if client_id:
                        self._client_name_cache[client_id] = client_name
                    if mongo_id:
                        self._client_name_cache[mongo_id] = client_name
            if repo is not None and hasattr(repo, "get_all_invoice_numbers"):
                self._project_invoice_cache.update(repo.get_all_invoice_numbers() or {})
            projects = self.project_service.get_all_projects() or []
            projects = sorted(
                projects,
                key=lambda project: (
                    str(getattr(project, "name", "") or "").strip().lower(),
                    str(getattr(project, "invoice_number", "") or "").strip().lower(),
                ),
            )
            selected_index = -1
            for index, project in enumerate(projects):
                self.project_combo.addItem(self._project_display_text(project), userData=project)
                if selected_index < 0 and self._project_matches_payment(project):
                    selected_index = index
                    self.selected_project = project
            self.project_combo.lineEdit().setPlaceholderText(
                "اكتب اسم المشروع أو رقم الفاتورة أو العميل..."
            )
            if selected_index >= 0:
                self.project_combo.setCurrentIndex(selected_index)
            elif projects:
                self.selected_project = None
        except Exception as exc:
            safe_print(f"ERROR: [PaymentEditorDialog] فشل تحميل المشاريع: {exc}")
            self.change_project_btn.setEnabled(False)
            self.project_search_hint.setText("تعذر تحميل المشاريع حاليًا.")

    def _toggle_project_picker(self):
        if not self.project_service:
            return
        visible = not self.project_picker_frame.isVisible()
        if visible:
            self._load_project_options()
        if not visible:
            self._prepare_project_picker_for_hide()
        self._set_project_picker_visible(visible)
        if visible and self.project_combo.lineEdit():
            self.project_combo.lineEdit().setFocus()
            self.project_combo.lineEdit().selectAll()

    def _prepare_project_picker_for_hide(self):
        combo = getattr(self, "project_combo", None)
        if combo is None:
            return
        combo.shutdown()
        line_edit = combo.lineEdit()
        if line_edit:
            line_edit.clearFocus()

    def _set_project_picker_visible(self, visible: bool):
        self.project_picker_frame.setVisible(visible)
        self.project_picker_frame.setMinimumHeight(0)
        self.project_picker_frame.setMaximumHeight(16777215 if visible else 0)
        self.change_project_btn.setText("إخفاء البحث" if visible else "تغيير المشروع")
        if self.project_frame.layout():
            self.project_frame.layout().invalidate()
        if getattr(self, "_content_widget", None) and self._content_widget.layout():
            self._content_widget.layout().invalidate()
        if self.layout():
            self.layout().invalidate()
        self._resize_sync_timer.stop()
        self._resize_sync_timer.start(0)

    def _apply_initial_dialog_size(self):
        self.layout().activate()
        hint = self.sizeHint()
        self.setFixedSize(max(680, hint.width()), max(468, hint.height()))

    def _sync_dialog_size(self):
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        if getattr(self, "_content_widget", None):
            self._content_widget.adjustSize()
        self.layout().activate()
        self.adjustSize()
        width = max(680, self.sizeHint().width())
        height = max(468, self.sizeHint().height())
        self.setFixedSize(width, height)

    def _on_project_selected(self, index: int):
        if index < 0:
            return
        selected_project = self.project_combo.currentData()
        if not selected_project:
            return
        self.selected_project = selected_project
        self._refresh_project_summary()

    def _queue_project_stats_refresh(self) -> None:
        self.project_total_value_label.setText("--")
        self.project_paid_value_label.setText("--")
        self.project_remaining_value_label.setText("--")
        if not self.project_service:
            return
        self._project_stats_timer.stop()
        self._project_stats_timer.start(16)

    def _refresh_project_stats(self) -> None:
        try:
            summary_project = self.selected_project
            if summary_project is None and self.project_service:
                summary_project = self.project_service.get_project_by_id(
                    getattr(self.payment, "project_id", ""),
                    getattr(self.payment, "client_id", None),
                )
            if summary_project is not None and self.project_service:
                project_ref = self._project_ref(
                    summary_project, getattr(summary_project, "name", "")
                )
                profitability = self.project_service.get_project_profitability(
                    project_ref,
                    client_id=getattr(summary_project, "client_id", None),
                )
                self.project_total_value_label.setText(
                    _format_currency(profitability.get("total_revenue", 0), "--")
                )
                self.project_paid_value_label.setText(
                    _format_currency(profitability.get("total_paid", 0), "--")
                )
                self.project_remaining_value_label.setText(
                    _format_currency(profitability.get("balance_due", 0), "--")
                )
                return
        except Exception as exc:
            safe_print(f"WARNING: [Payments] تعذر تحديث إحصاءات المشروع في نافذة التعديل: {exc}")
        self.project_total_value_label.setText("--")
        self.project_paid_value_label.setText("--")
        self.project_remaining_value_label.setText("--")

    def _refresh_project_summary(self):
        project = self.selected_project
        project_name = str(getattr(self.payment, "project_id", "") or "").strip() or "غير محدد"
        client_name = self._get_client_name(getattr(self.payment, "client_id", "") or "")
        invoice_number = str(getattr(self.payment, "invoice_number", "") or "").strip()
        if project is not None:
            project_name = str(getattr(project, "name", project_name) or project_name).strip()
            client_name = self._get_client_name(getattr(project, "client_id", "") or "")
            invoice_number = self._resolve_invoice_number_for_project(project, ensure=False)
        self.project_name_label.setText(project_name or "غير محدد")
        self.project_meta_label.setText(client_name or "غير محدد")
        self.project_invoice_label.setText(invoice_number or "غير محدد حتى الآن")
        self.invoice_value_label.setText(invoice_number or "غير محدد")
        self.setWindowTitle(f"تعديل دفعة - {project_name}")
        self._queue_project_stats_refresh()

    def _update_payment_method_from_account(self):
        """⚡ تحديث طريقة الدفع تلقائياً حسب الحساب المختار - يدعم نظام 4 و 6 أرقام"""
        selected_account = self.account_combo.currentData()
        if not selected_account:
            return

        self.current_payment_method = infer_payment_method_from_account(selected_account)
        self.method_value_label.setText(self.current_payment_method)

    def _cleanup_smart_combos(self):
        self._resize_sync_timer.stop()
        self._project_stats_timer.stop()
        for combo in self.findChildren(SmartFilterComboBox):
            combo.shutdown()

    def reject(self):
        self._cleanup_smart_combos()
        super().reject()

    def done(self, result: int):
        self._cleanup_smart_combos()
        super().done(result)

    def save_changes(self):
        selected_account = self.account_combo.currentData()
        new_amount = to_decimal(self.amount_input.value())

        if not selected_account or new_amount <= 0:
            QMessageBox.warning(self, "⚠️ تحقق", "يرجى اختيار الحساب وإدخال مبلغ صحيح.")
            return

        try:
            new_account_id = selected_account.code

            # تحديث بيانات الدفعة
            self.payment.amount = float(new_amount)
            self.payment.account_id = new_account_id
            self.payment.date = self.date_input.dateTime().toPyDateTime()
            self.payment.method = self.current_payment_method
            if self.selected_project is not None:
                self.payment.project_id = self._project_ref(
                    self.selected_project,
                    str(getattr(self.payment, "project_id", "") or ""),
                )
                self.payment.client_id = str(
                    getattr(self.selected_project, "client_id", "") or self.payment.client_id or ""
                ).strip()
                self.payment.invoice_number = self._resolve_invoice_number_for_project(
                    self.selected_project, ensure=True
                )
            elif self.project_service and not getattr(self.payment, "invoice_number", None):
                repo = getattr(self.project_service, "repo", None)
                if repo is not None and hasattr(repo, "ensure_invoice_number"):
                    self.payment.invoice_number = repo.ensure_invoice_number(
                        self.payment.project_id,
                        self.payment.client_id or None,
                    )

            payment_id = self.payment.id or self.payment._mongo_id

            if self.project_service:
                result = self.project_service.update_payment_for_project(payment_id, self.payment)
            else:
                result = self.accounting_service.repo.update_payment(payment_id, self.payment)

            if result:
                # ⚡ إعادة حساب أرصدة الحسابات المتأثرة فوراً
                if self.accounting_service:
                    self.accounting_service._schedule_cash_recalc()

                # ⚡ إرسال إشارات التحديث
                from core.signals import app_signals

                app_signals.emit_data_changed("payments")
                app_signals.emit_data_changed("accounting")

                QMessageBox.information(self, "تم", "تم تعديل الدفعة بنجاح")
                self.accept()
            else:
                QMessageBox.warning(self, "خطأ", "فشل حفظ التعديلات.")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل تعديل الدفعة: {e}")

    # ⚡ تم إزالة _reverse_and_repost_journal_entry - القيود تُدار عبر EventBus


class PaymentsManagerTab(QWidget):
    """تاب إدارة الدفعات - عرض جميع التحصيلات مع إمكانية التعديل"""

    def __init__(
        self,
        *,
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

        self.payments_list: list[schemas.Payment] = []
        self.clients_cache: dict[str, str] = {}  # cache للعملاء
        self._lookups_cache: dict[str, dict] = {}
        self._lookups_cache_ts: dict[str, float] = {}
        self._lookups_cache_ttl_s = 30.0
        self._current_page = 1
        self._page_size = 100
        self._page_accounts_cache: dict = {}
        self._page_projects_cache: dict = {}
        self._page_clients_cache: dict = {}
        self._total_payments_sum = 0.0

        # 📱 تجاوب: سياسة التمدد الكامل
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setup_ui()
        self.apply_permissions()

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals

        app_signals.safe_connect(app_signals.payments_changed, self._on_payments_changed)
        app_signals.safe_connect(app_signals.clients_changed, self._invalidate_lookup_cache)
        app_signals.safe_connect(app_signals.projects_changed, self._invalidate_lookup_cache)
        app_signals.safe_connect(app_signals.accounts_changed, self._invalidate_lookup_cache)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_payments_data() - يتم استدعاؤها من MainWindow

    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # === شريط الأزرار المتجاوب ===
        from ui.responsive_toolbar import ResponsiveToolbar

        self.toolbar = ResponsiveToolbar()

        # ⚡ زر إضافة دفعة جديدة
        self.add_button = QPushButton("➕ إضافة دفعة")
        self.add_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.add_button.setFixedHeight(28)
        self.add_button.clicked.connect(self.open_add_dialog)

        self.edit_button = QPushButton("✏️ تعديل الدفعة")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.open_edit_dialog)

        self.delete_button = QPushButton("🗑️ حذف الدفعة")
        self.delete_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_button.setFixedHeight(28)
        self.delete_button.clicked.connect(self.delete_selected_payment)

        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.setFixedHeight(28)
        self.refresh_button.clicked.connect(self.load_payments_data)

        # إضافة الأزرار للـ toolbar المتجاوب
        self.toolbar.addButton(self.add_button)
        self.toolbar.addButton(self.edit_button)
        self.toolbar.addButton(self.delete_button)
        self.toolbar.addButton(self.refresh_button)

        layout.addWidget(self.toolbar)

        # جدول الدفعات
        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(8)
        self.payments_table.setHorizontalHeaderLabels(
            [
                "#",
                "التاريخ",
                "النوع",
                "العميل/المشروع",
                "رقم الفاتورة",
                "المبلغ",
                "طريقة الدفع",
                "الحساب",
            ]
        )

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar

        self.search_bar = UniversalSearchBar(
            self.payments_table,
            placeholder="🔍 بحث (التاريخ، العميل، المشروع، رقم الفاتورة، المبلغ، الحساب)...",
        )
        layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===

        h_header = self.payments_table.horizontalHeader()
        v_header = self.payments_table.verticalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # #
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # التاريخ
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # النوع
            h_header.setSectionResizeMode(
                3, QHeaderView.ResizeMode.Stretch
            )  # العميل/المشروع - يتمدد
            h_header.setSectionResizeMode(
                4, QHeaderView.ResizeMode.ResizeToContents
            )  # رقم الفاتورة
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # المبلغ
            h_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # طريقة الدفع
            h_header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # الحساب - يتمدد
        self.payments_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.payments_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.payments_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.payments_table.setAlternatingRowColors(True)
        if v_header is not None:
            v_header.setDefaultSectionSize(45)  # ⚡ ارتفاع الصفوف
            v_header.setVisible(False)

        # ربط الدبل كليك
        self.payments_table.itemDoubleClicked.connect(self.open_edit_dialog)

        # إضافة قائمة السياق (كليك يمين)
        self._setup_context_menu()

        self.payments_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl

        fix_table_rtl(self.payments_table)
        layout.addWidget(self.payments_table)

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 6, 0, 0)
        pagination_layout.setSpacing(8)

        self.prev_page_button = QPushButton("◀ السابق")
        self.prev_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.prev_page_button.setFixedHeight(26)
        self.prev_page_button.clicked.connect(self._go_prev_page)

        self.next_page_button = QPushButton("التالي ▶")
        self.next_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.next_page_button.setFixedHeight(26)
        self.next_page_button.clicked.connect(self._go_next_page)

        self.page_info_label = QLabel("صفحة 1 / 1")
        self.page_info_label.setFont(get_cairo_font(11, bold=True))
        self.page_info_label.setStyleSheet("color: #94a3b8;")

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["50", "100", "200", "كل"])
        self.page_size_combo.setCurrentText("100")
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)

        pagination_layout.addWidget(self.prev_page_button)
        pagination_layout.addWidget(self.next_page_button)
        pagination_layout.addStretch(1)
        pagination_layout.addWidget(QLabel("حجم الصفحة:"))
        pagination_layout.addWidget(self.page_size_combo)
        pagination_layout.addWidget(self.page_info_label)
        layout.addLayout(pagination_layout)

        # إجمالي الدفعات
        self.total_label = QLabel("إجمالي التحصيلات: 0.00 ج.م")
        self.total_label.setFont(get_cairo_font(14, bold=True))
        self.total_label.setStyleSheet("color: #0A6CF1; padding: 10px;")
        layout.addWidget(self.total_label, 0, Qt.AlignmentFlag.AlignRight)

    def _setup_context_menu(self):
        """إعداد قائمة السياق (كليك يمين) للجدول"""
        from core.context_menu import ContextMenuManager

        ContextMenuManager.setup_table_context_menu(
            table=self.payments_table,
            on_view=self.open_edit_dialog,
            on_edit=self.open_edit_dialog,
            on_delete=self.delete_selected_payment,
            on_refresh=self.load_payments_data,
        )

    def load_payments_data(self, force_refresh: bool = False):
        """⚡ تحميل الدفعات في الخلفية لمنع التجميد"""
        safe_print("INFO: [PaymentsManager] جاري تحميل الدفعات...")

        from core.data_loader import get_data_loader

        # تحضير الجدول
        sorting_enabled = self.payments_table.isSortingEnabled()
        if sorting_enabled:
            self.payments_table.setSortingEnabled(False)
        self.payments_table.setUpdatesEnabled(False)
        self.payments_table.blockSignals(True)
        self.payments_table.setRowCount(0)

        # دالة جلب البيانات
        def fetch_payments():
            try:
                payments = self.accounting_service.repo.get_all_payments()

                accounts_cache = self._get_cached_lookup("accounts")
                if accounts_cache is None:
                    if hasattr(self.accounting_service, "get_all_accounts_cached"):
                        all_accounts = self.accounting_service.get_all_accounts_cached()
                    else:
                        all_accounts = self.accounting_service.repo.get_all_accounts()
                    accounts_cache = {}
                    for acc in all_accounts:
                        code = getattr(acc, "code", None)
                        if code is not None and code != "":
                            accounts_cache[code] = acc
                            accounts_cache[str(code)] = acc
                        acc_id = getattr(acc, "id", None)
                        if acc_id is not None:
                            accounts_cache[acc_id] = acc
                            accounts_cache[str(acc_id)] = acc
                    self._set_cached_lookup("accounts", accounts_cache)

                projects_cache = self._get_cached_lookup("projects")
                if projects_cache is None:
                    all_projects = self.project_service.get_all_projects()
                    projects_cache = {}
                    for proj in all_projects or []:
                        try:
                            proj_name = (getattr(proj, "name", None) or "").strip()
                            if proj_name:
                                projects_cache[proj_name] = proj
                            proj_id = getattr(proj, "id", None)
                            if proj_id is not None:
                                projects_cache[str(proj_id)] = proj
                                projects_cache[proj_id] = proj
                            proj_mongo_id = getattr(proj, "_mongo_id", None)
                            if proj_mongo_id:
                                projects_cache[str(proj_mongo_id)] = proj
                                projects_cache[proj_mongo_id] = proj
                            proj_code = (getattr(proj, "project_code", None) or "").strip()
                            if proj_code:
                                projects_cache[proj_code] = proj
                            invoice_number = (getattr(proj, "invoice_number", None) or "").strip()
                            if invoice_number:
                                projects_cache[invoice_number] = proj
                        except Exception:
                            continue
                    self._set_cached_lookup("projects", projects_cache)

                clients_cache = self._get_cached_lookup("clients")
                if clients_cache is None:
                    clients = self.client_service.get_all_clients()
                    clients_cache = {}
                    for c in clients:
                        clients_cache[c.name] = c
                        if c._mongo_id:
                            clients_cache[c._mongo_id] = c
                            clients_cache[str(c._mongo_id)] = c
                        if c.id:
                            clients_cache[str(c.id)] = c
                            clients_cache[int(c.id)] = c
                        if c.name:
                            clients_cache[c.name.strip()] = c
                    self._set_cached_lookup("clients", clients_cache)

                return {
                    "payments": payments,
                    "accounts_cache": accounts_cache,
                    "projects_cache": projects_cache,
                    "clients_cache": clients_cache,
                }
            except Exception as e:
                safe_print(f"ERROR: [PaymentsManager] فشل جلب الدفعات: {e}")
                import traceback

                traceback.print_exc()
                return {
                    "payments": [],
                    "accounts_cache": {},
                    "projects_cache": {},
                    "clients_cache": {},
                }

        # دالة تحديث الواجهة
        def on_data_loaded(data):
            try:
                self.payments_list = data["payments"]
                self._page_accounts_cache = data["accounts_cache"]
                self._page_projects_cache = data["projects_cache"]
                self._page_clients_cache = data["clients_cache"]
                self._total_payments_sum = sum(p.amount for p in self.payments_list)
                self.total_label.setText(f"إجمالي التحصيلات: {self._total_payments_sum:,.2f} ج.م")
                if self._current_page < 1:
                    self._current_page = 1
                self._render_current_page()
                safe_print(f"INFO: [PaymentsManager] ✅ تم تحميل {len(self.payments_list)} دفعة.")

            except Exception as e:
                safe_print(f"ERROR: [PaymentsManager] فشل تحديث الجدول: {e}")
                import traceback

                traceback.print_exc()
            finally:
                self.payments_table.blockSignals(False)
                self.payments_table.setUpdatesEnabled(True)
                if sorting_enabled:
                    self.payments_table.setSortingEnabled(True)

        def on_error(error_msg):
            safe_print(f"ERROR: [PaymentsManager] فشل تحميل الدفعات: {error_msg}")
            self.payments_table.blockSignals(False)
            self.payments_table.setUpdatesEnabled(True)

        if force_refresh:
            self._invalidate_lookup_cache()
            if hasattr(self.project_service, "invalidate_cache"):
                self.project_service.invalidate_cache()
            if hasattr(self.client_service, "invalidate_cache"):
                self.client_service.invalidate_cache()

        # تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="payments_list",
            load_function=fetch_payments,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _get_total_pages(self) -> int:
        total = len(self.payments_list)
        if total == 0:
            return 1
        if self._page_size <= 0:
            return 1
        return (total + self._page_size - 1) // self._page_size

    def _render_current_page(self):
        total_pages = self._get_total_pages()
        if self._current_page > total_pages:
            self._current_page = total_pages
        if self._current_page < 1:
            self._current_page = 1

        if self._page_size <= 0:
            page_items = self.payments_list
            start_index = 0
        else:
            start_index = (self._current_page - 1) * self._page_size
            end_index = start_index + self._page_size
            page_items = self.payments_list[start_index:end_index]

        self._populate_payments_table(page_items, start_index)
        self._update_pagination_controls(total_pages)

    def _populate_payments_table(self, payments: list[schemas.Payment], start_index: int):
        accounts_cache = self._page_accounts_cache
        projects_cache = self._page_projects_cache
        clients_cache = self._page_clients_cache

        self.payments_table.setRowCount(len(payments))
        for i, payment in enumerate(payments):
            row_number = start_index + i + 1
            num_item = create_centered_item(str(row_number))
            num_item.setData(Qt.ItemDataRole.UserRole, payment)
            self.payments_table.setItem(i, 0, num_item)

            date_str = payment.date.strftime("%Y-%m-%d") if payment.date else ""
            self.payments_table.setItem(i, 1, create_centered_item(date_str))

            type_item = create_centered_item("💰 وارد")
            type_item.setForeground(QColor("#0A6CF1"))
            self.payments_table.setItem(i, 2, type_item)

            client_name = "عميل غير محدد"
            project_name = payment.project_id or "مشروع غير محدد"

            if payment.project_id:
                proj_key = str(payment.project_id).strip()
                project = projects_cache.get(payment.project_id) or projects_cache.get(proj_key)
                if project:
                    project_name = getattr(project, "name", proj_key) or proj_key
                    client_id = (getattr(project, "client_id", "") or "").strip()
                    if client_id:
                        client = clients_cache.get(client_id) or clients_cache.get(str(client_id))
                        client_name = client.name if client else client_id

            if client_name == "عميل غير محدد" and payment.client_id and payment.client_id.strip():
                client_id = payment.client_id.strip()
                if client_id in clients_cache:
                    client = clients_cache[client_id]
                    client_name = client.name
                else:
                    client_name = client_id

            self.payments_table.setItem(
                i, 3, create_centered_item(f"{client_name} - {project_name}")
            )

            invoice_number = str(getattr(payment, "invoice_number", "") or "").strip()
            if not invoice_number and payment.project_id:
                proj_key = str(payment.project_id).strip()
                project = projects_cache.get(payment.project_id) or projects_cache.get(proj_key)
                if project:
                    invoice_number = str(getattr(project, "invoice_number", "") or "").strip()
            self.payments_table.setItem(i, 4, create_centered_item(invoice_number or "—"))

            amount_item = create_centered_item(f"{payment.amount:,.2f}")
            amount_item.setForeground(QColor("#0A6CF1"))
            self.payments_table.setItem(i, 5, amount_item)

            payment_method = self._get_payment_method_from_account(
                payment.account_id, accounts_cache
            )
            self.payments_table.setItem(i, 6, create_centered_item(payment_method))

            account_display = "---"
            if payment.account_id and payment.account_id in accounts_cache:
                account = accounts_cache[payment.account_id]
                account_display = f"{account.name} ({account.code})"
            elif payment.account_id:
                account_display = payment.account_id

            self.payments_table.setItem(i, 7, create_centered_item(account_display))
            self.payments_table.setRowHeight(i, 40)

    def _update_pagination_controls(self, total_pages: int):
        self.page_info_label.setText(f"صفحة {self._current_page} / {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

    def _on_page_size_changed(self, value: str):
        if value == "كل":
            self._page_size = max(1, len(self.payments_list))
        else:
            try:
                self._page_size = int(value)
            except Exception:
                self._page_size = 100
        self._current_page = 1
        self._render_current_page()

    def _go_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._render_current_page()

    def _go_next_page(self):
        if self._current_page < self._get_total_pages():
            self._current_page += 1
            self._render_current_page()

    def _on_payments_changed(self):
        """⚡ استجابة لإشارة تحديث الدفعات - تحديث الجدول أوتوماتيك"""
        # ⚡ إبطال الـ cache أولاً لضمان جلب البيانات الجديدة من السيرفر
        if hasattr(self.project_service, "invalidate_cache"):
            self.project_service.invalidate_cache()
        if not self.isVisible():
            return
        self.load_payments_data(force_refresh=True)

    def get_selected_payment(self) -> schemas.Payment | None:
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
        if isinstance(payment, schemas.Payment):
            return payment

        # fallback: استخدام الفهرس مباشرة
        if 0 <= current_row < len(self.payments_list):
            p = self.payments_list[current_row]
            if isinstance(p, schemas.Payment):
                return p

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
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_payments_data(force_refresh=True)

    def _get_cash_accounts(self) -> list[schemas.Account]:
        """جلب حسابات النقدية والبنوك"""
        try:
            all_accounts = self.accounting_service.repo.get_all_accounts()
            return filter_operational_cashboxes(all_accounts)
        except Exception as e:
            safe_print(f"ERROR: [PaymentsManager] فشل جلب حسابات النقدية: {e}")
            return []

    def _get_payment_method_from_account(self, account_code: str, accounts_cache: dict) -> str:
        """⚡ تحديد طريقة الدفع من كود الحساب - يدعم نظام 4 و 6 أرقام"""
        if not account_code or account_code not in accounts_cache:
            return "---"

        account = accounts_cache[account_code]
        return infer_payment_method_from_account(account)

    def _get_cached_lookup(self, key: str) -> dict | None:
        ts = self._lookups_cache_ts.get(key)
        if ts is None:
            return None
        if (time.monotonic() - ts) > self._lookups_cache_ttl_s:
            self._lookups_cache.pop(key, None)
            self._lookups_cache_ts.pop(key, None)
            return None
        return self._lookups_cache.get(key)

    def _set_cached_lookup(self, key: str, value: dict) -> None:
        self._lookups_cache[key] = value
        self._lookups_cache_ts[key] = time.monotonic()

    def _invalidate_lookup_cache(self):
        self._lookups_cache.clear()
        self._lookups_cache_ts.clear()

    def open_add_dialog(self):
        """⚡ فتح نافذة إضافة دفعة جديدة"""
        dialog = NewPaymentDialog(
            project_service=self.project_service,
            accounting_service=self.accounting_service,
            client_service=self.client_service,
            parent=self,
        )
        dialog.payment_created.connect(self._on_payment_created)
        dialog.exec()

    def _on_payment_created(self, payment):
        """⚡ استجابة لإنشاء دفعة جديدة"""
        safe_print(f"INFO: [PaymentsManager] تم إنشاء دفعة جديدة: {payment.amount}")
        self.load_payments_data(force_refresh=True)

    def apply_permissions(self):
        """تطبيق الصلاحيات حسب دور المستخدم"""
        if not self.current_user:
            return

        from core.auth_models import UserRole

        user_role = self.current_user.role
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role)
            except ValueError:
                user_role = UserRole.SALES

        # المحاسب والمدير لهم صلاحيات كاملة
        if user_role in [UserRole.ADMIN, UserRole.ACCOUNTANT]:
            self.add_button.setEnabled(True)
            self.edit_button.setEnabled(True)
            self.delete_button.setEnabled(True)
        else:
            # مندوب المبيعات: قراءة فقط
            self.add_button.setEnabled(False)
            self.edit_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.add_button.setToolTip("ليس لديك صلاحية إضافة الدفعات")
            self.edit_button.setToolTip("ليس لديك صلاحية تعديل الدفعات")
            self.delete_button.setToolTip("ليس لديك صلاحية حذف الدفعات")

    def delete_selected_payment(self):
        """حذف الدفعة المحددة مع عكس القيد المحاسبي وتحديث حالة المشروع"""
        selected_payment = self.get_selected_payment()
        if not selected_payment:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد دفعة أولاً.")
            return

        amount = to_decimal(selected_payment.amount)
        date_str = (
            selected_payment.date.strftime("%Y-%m-%d") if selected_payment.date else "غير محدد"
        )

        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف الدفعة؟\n\n"
            f"المشروع: {selected_payment.project_id}\n"
            f"المبلغ: {amount:,.2f} ج.م\n"
            f"التاريخ: {date_str}\n\n"
            f"⚠️ سيتم عكس القيد المحاسبي المرتبط بهذه الدفعة.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            # ⚡ حذف الدفعة - القيد العكسي يتم تلقائياً عبر EventBus (PAYMENT_DELETED)
            payment_id = selected_payment.id or selected_payment._mongo_id
            project_name = selected_payment.project_id
            result = self.project_service.delete_payment_for_project(payment_id, project_name)

            if result:
                QMessageBox.information(
                    self, "تم الحذف", "تم حذف الدفعة وعكس القيد المحاسبي وتحديث حالة المشروع بنجاح."
                )
                self.load_payments_data(force_refresh=True)
            else:
                QMessageBox.warning(self, "خطأ", "فشل حذف الدفعة.")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل حذف الدفعة: {e}")
            safe_print(f"ERROR: [PaymentsManager] فشل حذف الدفعة: {e}")
