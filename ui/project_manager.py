# pylint: disable=too-many-lines,too-many-nested-blocks,too-many-positional-arguments
import os
import traceback
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QDate, Qt, QTimer
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from core.account_filters import filter_operational_cashboxes
from core.color_utils import clamp01, color_for_ratio
from core.context_menu import RightClickBlocker, is_right_click_active
from core.data_loader import get_data_loader
from core.project_currency import (
    amount_between_currencies,
    amount_from_egp,
    amount_to_egp,
    currency_suffix,
    normalize_currency_code,
    normalize_exchange_rate,
    project_currency_code,
    project_exchange_rate,
)
from core.signals import app_signals
from core.text_utils import normalize_user_text
from services.accounting_service import AccountingService
from services.client_service import ClientService
from services.expense_service import ExpenseService
from services.invoice_printing_service import InvoicePrintingService
from services.project_service import ProjectService
from services.service_service import ServiceService
from ui.client_editor_dialog import ClientEditorDialog
from ui.custom_spinbox import CustomSpinBox
from ui.expense_editor_dialog import ExpenseEditorDialog
from ui.payment_dialog import PaymentDialog
from ui.project_profit_dialog import ProjectProfitDialog
from ui.responsive_toolbar import ResponsiveToolbar
from ui.service_editor_dialog import ServiceEditorDialog
from ui.smart_combobox import SmartFilterComboBox
from ui.styles import (
    BUTTON_STYLES,
    COLORS,
    TABLE_STYLE_DARK,
    apply_arrows_to_all_widgets,
    fix_table_rtl,
    get_cairo_font,
    setup_custom_title_bar,
)
from ui.todo_manager import TaskEditorDialog, TaskService
from ui.universal_search import UniversalSearchBar

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


def _build_currency_update_summary(
    result: dict[str, Any] | None,
    *,
    current_code: Any = None,
    current_rate: Any = None,
) -> str:
    payload = result or {}
    updated = int(payload.get("updated", 0) or 0)
    failed = int(payload.get("failed", 0) or 0)
    results = payload.get("results", {}) or {}
    lines = [f"✅ تم تحديث {updated} عملة من الإنترنت"]

    normalized_code = normalize_currency_code(current_code) if current_code else ""
    if normalized_code:
        if normalized_code == "EGP":
            lines.append("العملة الحالية للمشروع: EGP (السعر الأساسي 1.00 ج.م)")
        else:
            normalized_rate = normalize_exchange_rate(current_rate, normalized_code)
            lines.append(f"السعر المستخدم الآن: 1 {normalized_code} = {normalized_rate:,.4f} ج.م")

    if results:
        lines.append("")
        for code, data in sorted(results.items()):
            normalized_result_code = normalize_currency_code(code)
            if bool(data.get("success")):
                lines.append(
                    f"• {normalized_result_code}: "
                    f"{normalize_exchange_rate(data.get('rate', 1.0), normalized_result_code):,.4f} ج.م"
                )
            else:
                lines.append(f"• {normalized_result_code}: فشل التحديث")

    if failed > 0:
        lines.append("")
        lines.append(f"⚠️ فشل تحديث {failed} عملة")

    return "\n".join(lines)


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
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # تطبيق شريط العنوان المخصص

        setup_custom_title_bar(self)

        # إزالة الإطار البرتقالي نهائياً
        self.setStyleSheet(
            """
            * {
                outline: none;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
            QPushButton:focus {
                border: none;
                outline: none;
            }
        """
        )

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
        save_btn = QPushButton("إضافة البند")
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
        self._save_in_progress = False
        self._save_button_default_text = "💾 حفظ المشروع"
        self._save_new_button_default_text = "💾 حفظ وفتح جديد"

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

        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            width = max(920, int(screen_geo.width() * 0.92))
            height = max(620, int(screen_geo.height() * 0.92))
            width = min(width, screen_geo.width())
            height = min(height, screen_geo.height())
            min_width = min(920, max(640, screen_geo.width() - 120))
            min_height = min(620, max(420, screen_geo.height() - 160))
            self.setMinimumSize(min_width, min_height)
            x = screen_geo.x() + max(0, (screen_geo.width() - width) // 2)
            y = screen_geo.y() + max(0, (screen_geo.height() - height) // 2)
            self.setGeometry(x, y, width, height)
        else:
            self.resize(1100, 750)
            self.setMinimumSize(760, 520)

        # 📱 سياسة التمدد الكامل
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تطبيق شريط العنوان المخصص

        setup_custom_title_bar(self)

        # تصغير العناصر وإزالة الإطار البرتقالي
        self.setStyleSheet(
            """
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
        """
        )

        self.clients_list = self.client_service.get_all_clients()
        self.services_list = self.service_service.get_all_services()

        # فلترة الحسابات النقدية فقط (الخزينة والبنوك والمحافظ الإلكترونية)
        all_accounts = self.accounting_service.repo.get_all_accounts()
        self.cash_accounts = filter_operational_cashboxes(all_accounts)
        self._currencies_by_code: dict[str, dict[str, Any]] = {}
        self._selected_currency_code = "EGP"
        self._selected_exchange_rate = 1.0
        self._currency_change_in_progress = False
        self._load_currencies_catalog()

        self.init_ui()

        app_signals.safe_connect(app_signals.clients_changed, self._on_clients_changed)

    @staticmethod
    def _entity_ref(entity: Any, *fields: str) -> str:
        for field in fields:
            value = getattr(entity, field, None)
            text = str(value or "").strip()
            if text:
                return text
        return ""

    def _load_currencies_catalog(self) -> dict[str, dict[str, Any]]:
        repo = getattr(getattr(self, "accounting_service", None), "repo", None)
        currencies: list[dict[str, Any]] = []
        if repo is not None and hasattr(repo, "get_all_currencies"):
            try:
                currencies = repo.get_all_currencies() or []
            except Exception as exc:
                safe_print(f"WARNING: [ProjectEditor] Failed to load currencies: {exc}")
        catalog: dict[str, dict[str, Any]] = {}
        for currency in currencies:
            if not isinstance(currency, dict):
                continue
            code = normalize_currency_code(currency.get("code"))
            if not code:
                continue
            if not bool(currency.get("active", True)) and code != "EGP":
                continue
            catalog[code] = {
                "code": code,
                "name": str(currency.get("name") or code).strip() or code,
                "symbol": str(currency.get("symbol") or currency_suffix(code)).strip()
                or currency_suffix(code),
                "rate": normalize_exchange_rate(currency.get("rate", 1.0), code),
                "is_base": bool(currency.get("is_base", code == "EGP")),
                "active": bool(currency.get("active", True)),
            }
        if "EGP" not in catalog:
            catalog["EGP"] = {
                "code": "EGP",
                "name": "جنيه مصري",
                "symbol": currency_suffix("EGP"),
                "rate": 1.0,
                "is_base": True,
                "active": True,
            }
        self._currencies_by_code = catalog
        return catalog

    def _resolve_currency_snapshot(self, currency_code: Any, fallback_rate: Any = None) -> float:
        code = normalize_currency_code(currency_code)
        catalog = getattr(self, "_currencies_by_code", {}) or {}
        rate_source = (
            fallback_rate
            if fallback_rate is not None
            else catalog.get(code, {}).get(
                "rate",
                getattr(self, "_selected_exchange_rate", 1.0),
            )
        )
        return normalize_exchange_rate(rate_source, code)

    def _refresh_currency_combo(
        self, preferred_code: Any = None, preferred_rate: Any = None
    ) -> None:
        self._load_currencies_catalog()
        code = normalize_currency_code(
            preferred_code or getattr(self, "_selected_currency_code", None)
        )
        rate = self._resolve_currency_snapshot(code, preferred_rate)
        if code not in self._currencies_by_code:
            self._currencies_by_code[code] = {
                "code": code,
                "name": code,
                "symbol": currency_suffix(code),
                "rate": rate,
                "is_base": code == "EGP",
                "active": True,
            }
        self._selected_currency_code = code
        self._selected_exchange_rate = rate
        combo = getattr(self, "currency_combo", None)
        if combo is None:
            return
        ordered = sorted(
            self._currencies_by_code.values(),
            key=lambda item: (0 if item.get("is_base") else 1, item.get("code", "")),
        )
        combo.blockSignals(True)
        combo.clear()
        for currency in ordered:
            combo.addItem(f'{currency["name"]} ({currency["code"]})', currency["code"])
        target_index = combo.findData(code)
        if target_index < 0:
            target_index = 0
        if target_index >= 0:
            combo.setCurrentIndex(target_index)
        combo.blockSignals(False)
        self._update_exchange_rate_display()
        self._update_currency_decorations()

    def _current_currency_code(self) -> str:
        combo = getattr(self, "currency_combo", None)
        if combo is not None:
            try:
                data = combo.currentData()
                if data:
                    return normalize_currency_code(data)
            except Exception:
                pass
        return normalize_currency_code(getattr(self, "_selected_currency_code", None))

    def _current_exchange_rate(self) -> float:
        return self._resolve_currency_snapshot(
            self._current_currency_code(),
            getattr(self, "_selected_exchange_rate", 1.0),
        )

    def _current_currency_suffix(self) -> str:
        code = self._current_currency_code()
        currency_meta = (getattr(self, "_currencies_by_code", {}) or {}).get(code, {})
        symbol = str(currency_meta.get("symbol") or "").strip()
        return symbol or currency_suffix(code)

    def _update_exchange_rate_display(self) -> None:
        label = getattr(self, "exchange_rate_value_label", None)
        if label is None:
            return
        code = self._current_currency_code()
        rate = self._current_exchange_rate()
        self._selected_currency_code = code
        self._selected_exchange_rate = rate
        if code == "EGP":
            label.setText("العملة الأساسية - 1.00 ج.م")
        else:
            label.setText(f"1 {code} = {rate:,.4f} ج.م")
        label.setToolTip(label.text())

    def _update_currency_decorations(self) -> None:
        suffix_text = f" {self._current_currency_suffix()}"
        if hasattr(self, "item_price_input"):
            self.item_price_input.setSuffix(suffix_text)
        if hasattr(self, "payment_amount_input"):
            self.payment_amount_input.setSuffix(suffix_text)
        if hasattr(self, "discount_rate_input") and hasattr(self, "discount_type_combo"):
            if self.discount_type_combo.currentData() == "amount":
                self.discount_rate_input.setSuffix(suffix_text)
        if hasattr(self, "currency_status_label"):
            code = self._current_currency_code()
            self.currency_status_label.setText(f"{code} - {self._current_exchange_rate():,.4f} ج.م")

    def _project_item_to_display_currency(
        self,
        item: schemas.ProjectItem | dict[str, Any],
        currency_code: Any,
        exchange_rate: Any,
    ) -> schemas.ProjectItem:
        item_obj = item if isinstance(item, schemas.ProjectItem) else schemas.ProjectItem(**item)
        converted = item_obj.model_copy(
            update={
                "unit_price": amount_from_egp(item_obj.unit_price, currency_code, exchange_rate),
                "discount_amount": amount_from_egp(
                    getattr(item_obj, "discount_amount", 0.0), currency_code, exchange_rate
                ),
                "total": amount_from_egp(item_obj.total, currency_code, exchange_rate),
            }
        )
        full_desc = getattr(item_obj, "_service_full_desc", None)
        if full_desc:
            converted._service_full_desc = full_desc
        return converted

    def _project_item_to_storage_currency(
        self,
        item: schemas.ProjectItem | dict[str, Any],
        currency_code: Any,
        exchange_rate: Any,
    ) -> schemas.ProjectItem:
        item_obj = item if isinstance(item, schemas.ProjectItem) else schemas.ProjectItem(**item)
        unit_price_egp = amount_to_egp(item_obj.unit_price, currency_code, exchange_rate)
        discount_amount_egp = amount_to_egp(
            getattr(item_obj, "discount_amount", 0.0), currency_code, exchange_rate
        )
        subtotal_egp = float(item_obj.quantity) * unit_price_egp
        discount_amount_egp = min(discount_amount_egp, subtotal_egp)
        discount_rate_egp = (discount_amount_egp / subtotal_egp * 100) if subtotal_egp > 0 else 0.0
        converted = item_obj.model_copy(
            update={
                "unit_price": unit_price_egp,
                "discount_amount": discount_amount_egp,
                "discount_rate": discount_rate_egp,
                "total": subtotal_egp - discount_amount_egp,
            }
        )
        full_desc = getattr(item_obj, "_service_full_desc", None)
        if full_desc:
            converted._service_full_desc = full_desc
        return converted

    def _convert_editor_amounts(
        self,
        old_currency_code: Any,
        old_exchange_rate: Any,
        new_currency_code: Any,
        new_exchange_rate: Any,
    ) -> None:
        old_code = normalize_currency_code(old_currency_code)
        new_code = normalize_currency_code(new_currency_code)
        old_rate = normalize_exchange_rate(old_exchange_rate, old_code)
        new_rate = normalize_exchange_rate(new_exchange_rate, new_code)
        if old_code == new_code and abs(old_rate - new_rate) < 1e-9:
            return
        self._currency_change_in_progress = True
        try:
            if hasattr(self, "item_price_input"):
                self.item_price_input.setValue(
                    amount_between_currencies(
                        self.item_price_input.value(),
                        old_code,
                        old_rate,
                        new_code,
                        new_rate,
                    )
                )
            if hasattr(self, "payment_amount_input"):
                self.payment_amount_input.setValue(
                    amount_between_currencies(
                        self.payment_amount_input.value(),
                        old_code,
                        old_rate,
                        new_code,
                        new_rate,
                    )
                )
            if (
                hasattr(self, "discount_type_combo")
                and hasattr(self, "discount_rate_input")
                and self.discount_type_combo.currentData() == "amount"
            ):
                self.discount_rate_input.setValue(
                    amount_between_currencies(
                        self.discount_rate_input.value(),
                        old_code,
                        old_rate,
                        new_code,
                        new_rate,
                    )
                )
            for item in getattr(self, "project_items", []):
                item.unit_price = amount_between_currencies(
                    item.unit_price,
                    old_code,
                    old_rate,
                    new_code,
                    new_rate,
                )
                item.discount_amount = amount_between_currencies(
                    getattr(item, "discount_amount", 0.0),
                    old_code,
                    old_rate,
                    new_code,
                    new_rate,
                )
                subtotal = float(item.quantity) * float(item.unit_price)
                item.discount_amount = min(float(item.discount_amount), subtotal)
                item.total = subtotal - item.discount_amount
                item.discount_rate = (
                    (item.discount_amount / subtotal * 100) if subtotal > 0 else 0.0
                )
            if hasattr(self, "items_table") and hasattr(self, "_rebuild_items_table"):
                self._rebuild_items_table()
        finally:
            self._currency_change_in_progress = False

    def _on_currency_changed(self, _index: int) -> None:
        new_code = self._current_currency_code()
        new_rate = self._resolve_currency_snapshot(new_code)
        old_code = normalize_currency_code(getattr(self, "_selected_currency_code", None))
        old_rate = normalize_exchange_rate(getattr(self, "_selected_exchange_rate", 1.0), old_code)
        self._selected_currency_code = new_code
        self._selected_exchange_rate = new_rate
        self._convert_editor_amounts(old_code, old_rate, new_code, new_rate)
        self._update_exchange_rate_display()
        self._update_currency_decorations()
        if hasattr(self, "update_totals"):
            self.update_totals()

    def _refresh_currency_rates_for_editor(self) -> None:
        repo = getattr(getattr(self, "accounting_service", None), "repo", None)
        if repo is None or not hasattr(repo, "update_all_exchange_rates"):
            QMessageBox.warning(self, "تعذر التحديث", "خدمة العملات غير متاحة حاليًا.")
            return

        button = getattr(self, "refresh_currency_rates_button", None)
        default_text = "🌐 تحديث الأسعار من الإنترنت"
        current_code = self._current_currency_code()

        if button is not None:
            button.setEnabled(False)
            button.setText("⏳ جاري تحديث الأسعار...")

        def restore_button() -> None:
            if button is not None:
                button.setEnabled(True)
                button.setText(default_text)

        def refresh_rates() -> dict[str, Any]:
            return repo.update_all_exchange_rates() or {}

        def on_success(result: dict[str, Any]) -> None:
            try:
                self._load_currencies_catalog()
                refreshed_rate = self._resolve_currency_snapshot(current_code)
                self._selected_currency_code = current_code
                self._selected_exchange_rate = refreshed_rate
                self._refresh_currency_combo(current_code, refreshed_rate)
                QMessageBox.information(
                    self,
                    "نتيجة تحديث العملات",
                    _build_currency_update_summary(
                        result,
                        current_code=current_code,
                        current_rate=refreshed_rate,
                    ),
                )
            finally:
                restore_button()

        def on_error(error_msg: str) -> None:
            restore_button()
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل تحديث أسعار العملات من الإنترنت:\n{error_msg}",
            )

        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="project_editor_currency_rates",
            load_function=refresh_rates,
            on_success=on_success,
            on_error=on_error,
            use_thread_pool=True,
        )

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)  # ⚡ زيادة المسافات قليلاً
        main_layout.setContentsMargins(10, 10, 10, 10)  # ⚡ زيادة الهوامش
        self._editor_main_layout = main_layout

        # === التخطيط الأفقي الرئيسي: اليسار واليمين ===
        main_horizontal_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        main_horizontal_layout.setSpacing(8)
        self._main_horizontal_layout = main_horizontal_layout

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
        self.currency_combo = QComboBox()
        self.currency_combo.setPlaceholderText("اختر العملة")
        self.currency_combo.currentIndexChanged.connect(self._on_currency_changed)
        self.exchange_rate_value_label = QLabel("")
        self.exchange_rate_value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.exchange_rate_value_label.setStyleSheet(
            """
            QLabel {
                color: #BFDBFE;
                background: rgba(10, 108, 241, 0.08);
                border: 1px solid rgba(10, 108, 241, 0.18);
                border-radius: 6px;
                padding: 4px 8px;
                min-height: 24px;
            }
            """
        )
        self.currency_status_label = QLabel("")
        self.currency_status_label.setWordWrap(True)
        self.currency_status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.currency_status_label.setStyleSheet(
            """
            QLabel {
                color: #93C5FD;
                font-size: 10px;
                padding: 2px 4px;
            }
            """
        )
        self.refresh_currency_rates_button = QPushButton("🌐 تحديث الأسعار من الإنترنت")
        self.refresh_currency_rates_button.setStyleSheet(BUTTON_STYLES["info"])
        self.refresh_currency_rates_button.setFixedHeight(24)
        self.refresh_currency_rates_button.setToolTip(
            "تحديث أسعار العملات الحالية ثم استخدام السعر الجديد عند حفظ المشروع"
        )
        self.refresh_currency_rates_button.clicked.connect(self._refresh_currency_rates_for_editor)

        self.client_label = QLabel("العميل:")
        self.name_label = QLabel("اسم المشروع:")
        self.status_label = QLabel("الحالة:")
        self.start_date_label = QLabel("تاريخ الإصدار:")
        self.end_date_label = QLabel("تاريخ الاستحقاق:")
        self.currency_label = QLabel("العملة:")
        self.exchange_rate_label = QLabel("السعر الفوري:")
        for label in [
            self.client_label,
            self.name_label,
            self.status_label,
            self.start_date_label,
            self.end_date_label,
            self.currency_label,
            self.exchange_rate_label,
        ]:
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._basic_grid = QGridLayout()
        self._basic_grid.setHorizontalSpacing(6)
        self._basic_grid.setVerticalSpacing(4)
        basic_layout.addLayout(self._basic_grid)
        currency_actions_row = QHBoxLayout()
        currency_actions_row.setSpacing(6)
        currency_actions_row.addWidget(self.refresh_currency_rates_button, 0)
        currency_actions_row.addWidget(self.currency_status_label, 1)
        basic_layout.addLayout(currency_actions_row)
        basic_group.setLayout(basic_layout)
        self._basic_group = basic_group
        left_side.addWidget(basic_group)
        self._refresh_currency_combo("EGP", 1.0)

        # --- 2. بنود المشروع (الخدمات) ---
        items_group = QGroupBox("بنود المشروع (الخدمات)")
        items_layout = QVBoxLayout()
        items_layout.setSpacing(4)
        items_layout.setContentsMargins(6, 12, 6, 6)
        self._items_add_grid = QGridLayout()
        self._items_add_grid.setHorizontalSpacing(4)
        self._items_add_grid.setVerticalSpacing(4)
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
        self.add_item_button = QPushButton("إضافة بند")
        self.add_item_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.add_item_button.setToolTip("إضافة البند المحدد إلى عناصر المشروع")
        self.item_quantity_label = QLabel("الكمية:")
        self.item_price_label = QLabel("السعر:")
        self.item_quantity_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.item_price_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.service_combo.currentIndexChanged.connect(self.on_service_selected)
        self.add_item_button.clicked.connect(self._on_add_item_clicked)
        items_layout.addLayout(self._items_add_grid)

        # ⚡ إضافة label لعرض وصف الخدمة بشكل واضح
        self.service_description_label = QLabel("")
        self.service_description_label.setWordWrap(True)
        self.service_description_label.setTextFormat(Qt.TextFormat.PlainText)
        self.service_description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.service_description_label.setStyleSheet(
            f"""
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
        """
        )
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

        self.items_table.setMinimumHeight(140)
        self.items_table.verticalHeader().setDefaultSectionSize(30)  # ⚡ ارتفاع الصفوف أكبر قليلاً
        self.items_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.items_table.verticalHeader().setVisible(True)
        self.items_table.setShowGrid(True)
        items_layout.addWidget(self.items_table, 1)  # ⚡ stretch factor للتمدد
        items_group.setLayout(items_layout)
        self._items_group = items_group
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
        self.discount_type_combo.setMinimumWidth(70)
        self.discount_type_combo.currentIndexChanged.connect(self._on_discount_type_changed)

        self.discount_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.discount_rate_input.setSuffix(" %")
        discount_layout.addWidget(self.discount_type_combo)
        discount_layout.addWidget(self.discount_rate_input)

        self.tax_rate_input = CustomSpinBox(decimals=2, minimum=0, maximum=100)
        self.tax_rate_input.setSuffix(" %")
        self.tax_rate_input.setValue(self._get_default_tax_rate())
        self.total_label = QLabel("0.00 ج.م")
        self.total_label.setFont(get_cairo_font(12, bold=True))
        self.total_label.setStyleSheet("color: #0A6CF1;")
        self.discount_rate_input.valueChanged.connect(self.update_totals)
        self.tax_rate_input.valueChanged.connect(self.update_totals)
        totals_form.addRow(QLabel("الخصم:"), discount_layout)
        totals_form.addRow(QLabel("الضريبة (%):"), self.tax_rate_input)
        totals_form.addRow(QLabel("<b>الإجمالي النهائي:</b>"), self.total_label)
        totals_group.setLayout(totals_form)
        self._totals_group = totals_group
        left_side.addWidget(totals_group)

        # === الجانب الأيمن: الوصف والدفعة المقدمة ===
        right_side = QVBoxLayout()
        right_side.setSpacing(8)

        # الشروط والملاحظات - تصميم احترافي
        notes_group = QGroupBox("الشروط والملاحظات")
        notes_layout = QVBoxLayout()
        notes_layout.setContentsMargins(8, 8, 8, 8)
        notes_layout.setSpacing(6)

        # شريط أدوات مرن (صفّين) لمنع التداخل على الشاشات الصغيرة
        toolbar_layout = QVBoxLayout()
        toolbar_layout.setSpacing(4)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_top_row = QHBoxLayout()
        toolbar_top_row.setSpacing(4)
        toolbar_bottom_row = QHBoxLayout()
        toolbar_bottom_row.setSpacing(6)

        reset_btn = QPushButton("إعادة القالب")
        reset_btn.setFixedHeight(22)
        reset_btn.setMinimumWidth(110)
        reset_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(239, 68, 68, 0.2);
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 3px;
                color: #FCA5A5;
                font-size: 9px;
                padding: 2px 8px;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 0.4); }
        """
        )
        reset_btn.clicked.connect(self._reset_notes_template)

        clear_btn = QPushButton("مسح الكل")
        clear_btn.setFixedHeight(22)
        clear_btn.setMinimumWidth(90)
        clear_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(107, 114, 128, 0.2);
                border: 1px solid rgba(107, 114, 128, 0.4);
                border-radius: 3px;
                color: #9CA3AF;
                font-size: 9px;
                padding: 2px 8px;
            }
            QPushButton:hover { background: rgba(107, 114, 128, 0.4); }
        """
        )
        clear_btn.clicked.connect(self._clear_notes_input)

        toolbar_top_row.addWidget(reset_btn)
        toolbar_top_row.addWidget(clear_btn)
        toolbar_top_row.addStretch(1)

        self.notes_template_combo = SmartFilterComboBox()
        self.notes_template_combo.setFixedHeight(24)
        self.notes_template_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.notes_template_combo.setStyleSheet(
            """
            QComboBox {
                background: rgba(10, 42, 85, 0.35);
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 3px 8px;
                color: #F8FAFC;
                font-size: 10px;
                min-height: 18px;
            }
            QComboBox:hover { border: 1px solid #0A6CF1; }
            """
        )
        self.notes_template_combo.addItem("اختر قالب ملاحظات...", userData=None)

        apply_template_btn = QPushButton("تطبيق القالب")
        apply_template_btn.setFixedHeight(24)
        apply_template_btn.setMinimumWidth(82)
        apply_template_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(10, 108, 241, 0.25);
                border: 1px solid rgba(10, 108, 241, 0.45);
                border-radius: 6px;
                color: #BFDBFE;
                font-size: 10px;
                padding: 3px 10px;
            }
            QPushButton:hover { background: rgba(10, 108, 241, 0.35); }
            """
        )
        apply_template_btn.clicked.connect(self._apply_selected_notes_template)

        refresh_templates_btn = QPushButton("تحديث القوالب")
        refresh_templates_btn.setFixedHeight(24)
        refresh_templates_btn.setMinimumWidth(82)
        refresh_templates_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(107, 114, 128, 0.2);
                border: 1px solid rgba(107, 114, 128, 0.4);
                border-radius: 6px;
                color: #CBD5E1;
                font-size: 10px;
                padding: 3px 10px;
            }
            QPushButton:hover { background: rgba(107, 114, 128, 0.35); }
            """
        )
        refresh_templates_btn.clicked.connect(self._load_note_templates)

        toolbar_bottom_row.addWidget(self.notes_template_combo, 1)
        toolbar_bottom_row.addWidget(apply_template_btn, 0, Qt.AlignmentFlag.AlignTop)
        toolbar_bottom_row.addWidget(refresh_templates_btn, 0, Qt.AlignmentFlag.AlignTop)

        toolbar_layout.addLayout(toolbar_top_row)
        toolbar_layout.addLayout(toolbar_bottom_row)

        notes_layout.addLayout(toolbar_layout)

        self.notes_input = QTextEdit()
        self.notes_input.setStyleSheet(
            """
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
        """
        )
        self.notes_input.setMinimumHeight(130)

        # تعيين القالب الافتراضي للمشاريع الجديدة
        if not self.is_editing:
            self._reset_notes_template()

        self._load_note_templates()

        notes_layout.addWidget(self.notes_input, 1)

        notes_group.setLayout(notes_layout)
        notes_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._notes_group = notes_group
        right_side.addWidget(notes_group, 3)

        payment_methods_group = QGroupBox("💳 طرق الدفع (تظهر في الفاتورة)")
        payment_methods_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #374151;
                border-radius: 6px;
                margin-top: 8px;
                padding: 12px 8px 8px 8px;
                background: rgba(10, 42, 85, 0.2);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 2px 12px;
                color: #93C5FD;
            }
            """
        )
        pm_layout = QVBoxLayout()
        pm_layout.setContentsMargins(8, 12, 8, 8)
        pm_layout.setSpacing(6)

        self.payment_methods_preview = QTextEdit()
        self.payment_methods_preview.setReadOnly(True)
        self.payment_methods_preview.setMinimumHeight(64)
        self.payment_methods_preview.setStyleSheet(
            """
            QTextEdit {
                background: rgba(10, 42, 85, 0.35);
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px;
                color: #F8FAFC;
                font-size: 11px;
            }
            """
        )
        pm_layout.addWidget(self.payment_methods_preview)
        payment_methods_group.setLayout(pm_layout)
        payment_methods_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._payment_methods_group = payment_methods_group
        right_side.addWidget(payment_methods_group, 2)

        # الدفعة المقدمة - تصميم احترافي
        payment_group = QGroupBox("💳 تسجيل دفعة مقدمة")
        payment_group.setStyleSheet(
            """
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
        """
        )
        payment_layout = QVBoxLayout()
        payment_layout.setContentsMargins(8, 15, 8, 8)
        payment_layout.setSpacing(8)

        # المبلغ
        amount_row = QHBoxLayout()
        amount_label = QLabel("💰 المبلغ:")
        amount_label.setMinimumWidth(96)
        amount_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.payment_amount_input = CustomSpinBox(decimals=2, minimum=0, maximum=9999999)
        self.payment_amount_input.setValue(0.0)
        self.payment_amount_input.setSuffix(" ج.م")
        amount_row.addWidget(amount_label)
        amount_row.addWidget(self.payment_amount_input, 1)
        payment_layout.addLayout(amount_row)

        # التاريخ
        date_row = QHBoxLayout()
        date_label = QLabel("📅 التاريخ:")
        date_label.setMinimumWidth(96)
        date_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.payment_date_input = QDateEdit(QDate.currentDate())
        self.payment_date_input.setCalendarPopup(True)
        date_row.addWidget(date_label)
        date_row.addWidget(self.payment_date_input, 1)
        payment_layout.addLayout(date_row)

        # الحساب
        account_row = QHBoxLayout()
        account_label = QLabel("🏦 الحساب:")
        account_label.setMinimumWidth(96)
        account_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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

        method_row = QHBoxLayout()
        method_label = QLabel("💳 الطريقة:")
        method_label.setMinimumWidth(96)
        method_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.payment_method_combo = SmartFilterComboBox()
        self.payment_method_combo.addItem("تلقائي حسب الحساب", userData=None)
        self._load_payment_methods_for_combo()
        method_row.addWidget(method_label)
        method_row.addWidget(self.payment_method_combo, 1)
        payment_layout.addLayout(method_row)

        payment_group.setLayout(payment_layout)
        payment_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._payment_group = payment_group
        right_side.addWidget(payment_group, 2)

        # إضافة الجانبين للتخطيط الأفقي الرئيسي
        main_horizontal_layout.addLayout(left_side, 3)  # البيانات والبنود على اليسار (أوسع)
        main_horizontal_layout.addLayout(right_side, 2)  # الوصف والدفعة على اليمين
        main_layout.addLayout(main_horizontal_layout, 1)  # ⚡ stretch factor للتمدد

        # --- 5. أزرار التحكم ---
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()

        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.cancel_button.setFixedHeight(28)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)

        if not self.is_editing:
            self.save_new_button = QPushButton("💾 حفظ وفتح جديد")
            self.save_new_button.setStyleSheet(BUTTON_STYLES["success"])
            self.save_new_button.setFixedHeight(28)
            self.save_new_button.clicked.connect(self.save_project_and_new)
            buttons_layout.addWidget(self.save_new_button)

        self.save_button = QPushButton("💾 حفظ المشروع")
        self.save_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_button.setFixedHeight(28)
        self.save_button.clicked.connect(self.save_project)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.setContentsMargins(0, 5, 0, 5)
        main_layout.addLayout(buttons_layout)

        content_widget = QWidget()
        content_widget.setLayout(main_layout)

        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setFrameShape(QFrame.Shape.NoFrame)
        editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor_scroll.setWidget(content_widget)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(editor_scroll)
        self._editor_scroll = editor_scroll
        self._editor_layout_mode = None

        # جعل التاب متجاوب مع حجم الشاشة
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_responsive_editor_layout()
        QTimer.singleShot(0, self._apply_responsive_editor_layout)

        self.on_service_selected(0)

        # تطبيق الأسهم على كل الـ widgets

        apply_arrows_to_all_widgets(self)

        if self.is_editing:
            self.load_project_data()
            payment_group.setVisible(False)
        self._refresh_payment_methods_preview()

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._apply_responsive_editor_layout()

    def showEvent(self, event):  # pylint: disable=invalid-name
        super().showEvent(event)
        self._editor_layout_mode = None
        QTimer.singleShot(0, self._apply_responsive_editor_layout)
        QTimer.singleShot(80, self._apply_responsive_editor_layout)

    def _set_save_busy(self, is_busy: bool) -> None:
        self._save_in_progress = bool(is_busy)

        save_button = self.__dict__.get("save_button")
        if save_button is not None:
            save_button.setEnabled(not is_busy)
            save_button.setText("⏳ جاري الحفظ..." if is_busy else self._save_button_default_text)
        save_new_button = self.__dict__.get("save_new_button")
        if save_new_button is not None:
            save_new_button.setEnabled(not is_busy)
            save_new_button.setText(
                "⏳ جاري الحفظ..." if is_busy else self._save_new_button_default_text
            )
        cancel_button = self.__dict__.get("cancel_button")
        if cancel_button is not None:
            cancel_button.setEnabled(not is_busy)

    def _clear_layout_items(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout_items(child_layout)

    def _relayout_basic_fields(self, compact: bool, very_compact: bool):
        if not hasattr(self, "_basic_grid"):
            return

        self._clear_layout_items(self._basic_grid)

        label_min = 66 if very_compact else 78
        field_min = 112 if very_compact else (128 if compact else 150)
        pairs_per_row = 1 if very_compact else (2 if compact else 3)

        labels = [
            self.client_label,
            self.name_label,
            self.status_label,
            self.start_date_label,
            self.end_date_label,
            self.currency_label,
            self.exchange_rate_label,
        ]
        for label in labels:
            label.setMinimumWidth(label_min)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        fields = [
            (self.client_label, self.client_combo),
            (self.name_label, self.name_input),
            (self.status_label, self.status_combo),
            (self.start_date_label, self.start_date_input),
            (self.end_date_label, self.end_date_input),
            (self.currency_label, self.currency_combo),
            (self.exchange_rate_label, self.exchange_rate_value_label),
        ]
        for _label, widget in fields:
            widget.setMinimumWidth(field_min)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = 0
        pair_index = 0
        for label, widget in fields:
            col = pair_index * 2
            self._basic_grid.addWidget(label, row, col)
            self._basic_grid.addWidget(widget, row, col + 1)
            pair_index += 1
            if pair_index >= pairs_per_row:
                pair_index = 0
                row += 1

        max_cols = pairs_per_row * 2
        for col in range(max_cols):
            self._basic_grid.setColumnStretch(col, 1 if col % 2 == 1 else 0)
        self._basic_grid.setHorizontalSpacing(4 if very_compact else 6)
        self._basic_grid.setVerticalSpacing(3 if very_compact else 4)

    def _relayout_item_add_row(self, compact: bool, very_compact: bool):
        if not hasattr(self, "_items_add_grid"):
            return

        self._clear_layout_items(self._items_add_grid)

        self.service_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.service_combo.setMinimumWidth(150 if very_compact else 180)
        self.item_quantity_label.setMinimumWidth(48 if very_compact else 56)
        self.item_price_label.setMinimumWidth(48 if very_compact else 56)
        self.item_quantity_input.setMaximumWidth(88 if very_compact else 98)
        self.item_price_input.setMaximumWidth(110 if very_compact else 126)
        self.add_item_button.setMinimumWidth(112 if very_compact else 126)

        if very_compact:
            self._items_add_grid.addWidget(self.service_combo, 0, 0, 1, 4)
            self._items_add_grid.addWidget(self.add_item_button, 0, 4, 1, 2)
            self._items_add_grid.addWidget(self.item_quantity_label, 1, 0)
            self._items_add_grid.addWidget(self.item_quantity_input, 1, 1)
            self._items_add_grid.addWidget(self.item_price_label, 1, 2)
            self._items_add_grid.addWidget(self.item_price_input, 1, 3)
            self._items_add_grid.setColumnStretch(0, 1)
            self._items_add_grid.setColumnStretch(1, 0)
            self._items_add_grid.setColumnStretch(2, 0)
            self._items_add_grid.setColumnStretch(3, 0)
            self._items_add_grid.setColumnStretch(4, 0)
            self._items_add_grid.setColumnStretch(5, 0)
        elif compact:
            self._items_add_grid.addWidget(self.service_combo, 0, 0, 1, 5)
            self._items_add_grid.addWidget(self.add_item_button, 0, 5)
            self._items_add_grid.addWidget(self.item_quantity_label, 1, 0)
            self._items_add_grid.addWidget(self.item_quantity_input, 1, 1)
            self._items_add_grid.addWidget(self.item_price_label, 1, 2)
            self._items_add_grid.addWidget(self.item_price_input, 1, 3)
            self._items_add_grid.setColumnStretch(0, 1)
            self._items_add_grid.setColumnStretch(1, 0)
            self._items_add_grid.setColumnStretch(2, 0)
            self._items_add_grid.setColumnStretch(3, 0)
            self._items_add_grid.setColumnStretch(4, 1)
            self._items_add_grid.setColumnStretch(5, 0)
        else:
            self._items_add_grid.addWidget(self.service_combo, 0, 0, 1, 3)
            self._items_add_grid.addWidget(self.item_quantity_label, 0, 3)
            self._items_add_grid.addWidget(self.item_quantity_input, 0, 4)
            self._items_add_grid.addWidget(self.item_price_label, 0, 5)
            self._items_add_grid.addWidget(self.item_price_input, 0, 6)
            self._items_add_grid.addWidget(self.add_item_button, 0, 7)
            self._items_add_grid.setColumnStretch(0, 1)
            self._items_add_grid.setColumnStretch(1, 1)
            self._items_add_grid.setColumnStretch(2, 1)
            self._items_add_grid.setColumnStretch(3, 0)
            self._items_add_grid.setColumnStretch(4, 0)
            self._items_add_grid.setColumnStretch(5, 0)
            self._items_add_grid.setColumnStretch(6, 0)
            self._items_add_grid.setColumnStretch(7, 0)

        self._items_add_grid.setHorizontalSpacing(4 if very_compact else 6)
        self._items_add_grid.setVerticalSpacing(3 if very_compact else 4)

    def _apply_responsive_editor_layout(self):
        if not hasattr(self, "_main_horizontal_layout"):
            return

        available_width = self.width()
        available_height = self.height()
        editor_scroll = getattr(self, "_editor_scroll", None)
        if editor_scroll is not None:
            viewport = editor_scroll.viewport()
            if viewport is not None:
                if viewport.width() > 0:
                    available_width = max(available_width, viewport.width())
                if viewport.height() > 0:
                    available_height = max(available_height, viewport.height())

        stacked = False
        compact = available_width < 1280 or available_height < 760
        very_compact = available_width < 1100 or available_height < 680

        target_direction = QBoxLayout.Direction.LeftToRight
        if self._main_horizontal_layout.direction() != target_direction:
            self._main_horizontal_layout.setDirection(target_direction)

        layout_mode = (compact, very_compact)
        if self._editor_layout_mode != layout_mode:
            self._relayout_basic_fields(compact, very_compact)
            self._relayout_item_add_row(compact, very_compact)
            self._editor_layout_mode = layout_mode

        if stacked:
            self._main_horizontal_layout.setStretch(0, 9)
            self._main_horizontal_layout.setStretch(1, 8)
        elif compact:
            self._main_horizontal_layout.setStretch(0, 6)
            self._main_horizontal_layout.setStretch(1, 5)
        else:
            self._main_horizontal_layout.setStretch(0, 3)
            self._main_horizontal_layout.setStretch(1, 2)

        if hasattr(self, "items_table"):
            if very_compact:
                self.items_table.setMinimumHeight(98)
                self.items_table.verticalHeader().setDefaultSectionSize(24)
            elif compact:
                self.items_table.setMinimumHeight(118)
                self.items_table.verticalHeader().setDefaultSectionSize(26)
            else:
                self.items_table.setMinimumHeight(140)
                self.items_table.verticalHeader().setDefaultSectionSize(30)

        if hasattr(self, "notes_input"):
            if very_compact:
                self.notes_input.setMinimumHeight(110)
            elif compact:
                self.notes_input.setMinimumHeight(145)
            else:
                self.notes_input.setMinimumHeight(170)

        if hasattr(self, "payment_methods_preview"):
            self.payment_methods_preview.setMinimumHeight(52 if very_compact else 64)

        if hasattr(self, "service_description_label"):
            if very_compact:
                self.service_description_label.setMaximumHeight(86)
            elif compact:
                self.service_description_label.setMaximumHeight(120)
            else:
                self.service_description_label.setMaximumHeight(16777215)

        if hasattr(self, "_payment_methods_group"):
            self._payment_methods_group.setMaximumHeight(16777215)
        if hasattr(self, "_payment_group"):
            self._payment_group.setMaximumHeight(16777215)

        if hasattr(self, "_editor_main_layout"):
            if very_compact:
                self._editor_main_layout.setSpacing(4)
                self._editor_main_layout.setContentsMargins(6, 6, 6, 6)
            elif compact:
                self._editor_main_layout.setSpacing(6)
                self._editor_main_layout.setContentsMargins(8, 8, 8, 8)
            else:
                self._editor_main_layout.setSpacing(8)
                self._editor_main_layout.setContentsMargins(10, 10, 10, 10)

        return

    def _load_payment_methods_for_combo(self):
        combo = getattr(self, "payment_method_combo", None)
        if not combo:
            return

        try:
            current_data = combo.currentData() if hasattr(combo, "currentData") else None
            current_text = combo.currentText() if hasattr(combo, "currentText") else ""
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("تلقائي حسب الحساب", userData=None)

            settings_service = getattr(self, "settings_service", None)
            if not settings_service:
                return

            methods = settings_service.get_setting("payment_methods") or []
            seen_names = set()
            for m in methods:
                if isinstance(m, dict) and m.get("active", True):
                    name = (m.get("name") or "").strip()
                    if name and name not in seen_names:
                        combo.addItem(name, userData=name)
                        seen_names.add(name)

            restored_index = 0
            for index in range(combo.count()):
                item_data = combo.itemData(index)
                item_text = combo.itemText(index)
                if current_data is not None and item_data == current_data:
                    restored_index = index
                    break
                if current_data is None and current_text and item_text == current_text:
                    restored_index = index
                    break
            combo.setCurrentIndex(restored_index)
        except Exception as e:
            safe_print(f"WARNING: [ProjectEditor] Failed to load payment methods: {e}")
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                pass

    def _get_default_tax_rate(self) -> float:
        settings_service = getattr(getattr(self, "service_service", None), "settings_service", None)
        if not settings_service:
            return 0.0
        try:
            default_tax = settings_service.get_setting("default_tax_rate")
            return float(default_tax or 0.0)
        except Exception as e:
            safe_print(f"WARNING: [ProjectEditor] Failed to load default tax rate: {e}")
            return 0.0

    def _refresh_payment_methods_preview(self):
        try:
            if not hasattr(self, "payment_methods_preview") or not self.payment_methods_preview:
                return

            lines = []
            if self.settings_service:
                methods = self.settings_service.get_setting("payment_methods") or []
                for m in methods:
                    if not isinstance(m, dict):
                        continue
                    if not m.get("active", True):
                        continue
                    name = (m.get("name") or "").strip()
                    if not name:
                        continue
                    details = (m.get("details") or "").strip()
                    desc = (m.get("description") or "").strip()
                    extra = details or desc
                    if extra:
                        lines.append(f"• {name}: {extra}")
                    else:
                        lines.append(f"• {name}")

            self.payment_methods_preview.setText(
                "\n".join(lines) if lines else "لا توجد طرق دفع مفعّلة"
            )
        except Exception:
            pass

    def _reset_notes_template(self):
        """إعادة تعيين القالب الافتراضي للملاحظات"""
        template_text = None
        try:
            if self.settings_service:
                templates = self.settings_service.get_setting("project_note_templates") or []
                if isinstance(templates, list) and templates:
                    for t in templates:
                        if isinstance(t, dict) and "افتراضي" in (t.get("name") or ""):
                            template_text = t.get("content")
                            break
                    if not template_text:
                        first = templates[0]
                        if isinstance(first, dict):
                            template_text = first.get("content")
        except Exception:
            template_text = None

        if not template_text:
            template_text = """• مدة التنفيذ: ___ يوم عمل.
• تبدأ المدة من تاريخ استلام الداتا.
• التسليم حسب الجدول الزمني المتفق عليه.
• لا تشمل المدة أيام المراجعة والتعديلات.

• الدفعة المقدمة: 50% عند التعاقد.
• الدفعة الثانية: 25% عند التسليم الأولي.
• الدفعة النهائية: 25% عند التسليم النهائي.

• يبدأ التنفيذ بعد استلام الدفعة الأولى واعتماد المحتوى/التفاصيل المطلوبة.
• أي طلبات إضافية خارج نطاق العمل المتفق عليه يتم تسعيرها بشكل مستقل.
• تم تطبيق خصم ......... ج على الفاتورة."""

        self.notes_input.setText(template_text)

    def _clear_notes_input(self, _checked: bool = False):
        if hasattr(self, "notes_input") and self.notes_input:
            self.notes_input.clear()

    def _load_note_templates(self):
        try:
            if not hasattr(self, "notes_template_combo") or not self.notes_template_combo:
                return

            current_name = self.notes_template_combo.currentText()
            self.notes_template_combo.blockSignals(True)
            self.notes_template_combo.clear()
            self.notes_template_combo.addItem("اختر قالب ملاحظات...", userData=None)

            templates = []
            if self.settings_service:
                templates = self.settings_service.get_setting("project_note_templates") or []

            for t in templates:
                if isinstance(t, dict):
                    name = t.get("name") or ""
                    content = t.get("content") or ""
                    if name.strip():
                        self.notes_template_combo.addItem(name.strip(), userData=content)

            if current_name:
                for i in range(self.notes_template_combo.count()):
                    if self.notes_template_combo.itemText(i) == current_name:
                        self.notes_template_combo.setCurrentIndex(i)
                        break

        except Exception:
            pass
        finally:
            try:
                self.notes_template_combo.blockSignals(False)
            except Exception:
                pass

    def _apply_selected_notes_template(self):
        try:
            content = self.notes_template_combo.currentData()
            if not content:
                QMessageBox.warning(self, "تنبيه", "اختر قالب ملاحظات أولاً")
                return

            existing = self.notes_input.toPlainText().strip()
            if existing:
                reply = QMessageBox.question(
                    self,
                    "تأكيد",
                    "سيتم استبدال الملاحظات الحالية بالقالب المختار. هل تريد المتابعة؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            self.notes_input.setText(str(content))
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل تطبيق القالب:\n{e}")

    def _reset_form(self):
        try:
            self.project_to_edit = None
            self.is_editing = False
            self.project_items = []

            self.setWindowTitle("مشروع جديد")

            self.name_input.clear()
            self.status_combo.setCurrentText(schemas.ProjectStatus.ACTIVE.value)
            self.start_date_input.setDate(QDate.currentDate())
            self.end_date_input.setDate(QDate.currentDate().addDays(30))

            try:
                self.items_table.setRowCount(0)
            except Exception:
                pass

            self.service_combo.setCurrentIndex(0)
            self.item_price_input.setValue(0.0)
            self.item_quantity_input.setValue(1.0)
            if "currency_combo" in self.__dict__:
                try:
                    self._refresh_currency_combo("EGP", 1.0)
                except Exception as exc:
                    safe_print(f"WARNING: [ProjectEditor] Failed to reset currency snapshot: {exc}")

            self.discount_type_combo.setCurrentIndex(0)
            self.discount_rate_input.setValue(0.0)
            self.tax_rate_input.setValue(self._get_default_tax_rate())

            self._reset_notes_template()

            self.payment_amount_input.setValue(0.0)
            self.payment_date_input.setDate(QDate.currentDate())
            self.payment_account_combo.setCurrentIndex(0)

            self.update_totals()
        except Exception:
            pass

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
        project_currency = project_currency_code(self.project_to_edit)
        project_rate = project_exchange_rate(self.project_to_edit)
        self._refresh_currency_combo(project_currency, project_rate)
        self.items_table.setRowCount(0)
        self.project_items.clear()
        for item in self.project_to_edit.items:
            display_item = self._project_item_to_display_currency(
                item, project_currency, project_rate
            )
            self.add_item_to_table(item_to_add=display_item)
        self.update_totals()

    def on_service_selected(self, index):
        service = self.service_combo.currentData()
        if service:
            self.item_price_input.setValue(
                amount_from_egp(
                    service.default_price,
                    self._current_currency_code(),
                    self._current_exchange_rate(),
                )
            )
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

    def _on_add_item_clicked(self):
        self.add_item_to_table(item_to_add=None)

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
                        price = amount_from_egp(
                            new_service.default_price,
                            self._current_currency_code(),
                            self._current_exchange_rate(),
                        )
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
            delete_btn.setStyleSheet(
                """
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
            """
            )
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
                    discount_text = cell_text.replace(self._current_currency_suffix(), "").strip()
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
            self.discount_rate_input.setSuffix(f" {self._current_currency_suffix()}")
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
        self.total_label.setText(f"{total_amount:,.2f} {self._current_currency_suffix()}")

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
                    self._reload_clients_combo(new_client)
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

    def _reload_clients_combo(self, select_client: schemas.Client | None = None):
        current = select_client or self.client_combo.currentData()
        current_id = getattr(current, "_mongo_id", None) or getattr(current, "id", None)
        current_name = getattr(current, "name", None)
        self.clients_list = self.client_service.get_all_clients()
        self.client_combo.blockSignals(True)
        try:
            self.client_combo.clear()
            self.client_combo.addItem("--- اختر العميل ---", userData=None)
            for client in self.clients_list:
                self.client_combo.addItem(client.name, userData=client)
            if current_id or current_name:
                for i in range(self.client_combo.count()):
                    data = self.client_combo.itemData(i)
                    if not data:
                        continue
                    data_id = getattr(data, "_mongo_id", None) or getattr(data, "id", None)
                    data_name = getattr(data, "name", None)
                    if current_id is not None and str(data_id) == str(current_id):
                        self.client_combo.setCurrentIndex(i)
                        break
                    if current_name and data_name == current_name:
                        self.client_combo.setCurrentIndex(i)
                        break
        finally:
            self.client_combo.blockSignals(False)

    def _on_clients_changed(self):
        self._reload_clients_combo()

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
        self._save_project_impl(should_close=True)

    def save_project_and_new(self):
        self._save_project_impl(should_close=False)

    def _save_project_impl(self, should_close: bool):
        if self.__dict__.get("_save_in_progress", False):
            return

        selected_client = self.client_combo.currentData()
        selected_status = self.status_combo.currentData()
        normalized_project_name = normalize_user_text(self.name_input.text())

        if not normalized_project_name:
            QMessageBox.warning(self, "خطأ", "اسم المشروع مطلوب")
            return
        if normalized_project_name != self.name_input.text():
            self.name_input.setText(normalized_project_name)

        if not selected_client:
            client_text = self.client_combo.currentText().strip()
            if client_text:
                new_client = self.check_and_add_client(client_text)
                if new_client:
                    selected_client = new_client
                else:
                    return
            else:
                QMessageBox.warning(self, "خطأ", "العميل مطلوب")
                return

        self._load_currencies_catalog()
        currency_code = self._current_currency_code()
        exchange_rate_snapshot = self._resolve_currency_snapshot(currency_code)
        self._selected_currency_code = currency_code
        self._selected_exchange_rate = exchange_rate_snapshot
        storage_items = [
            self._project_item_to_storage_currency(item, currency_code, exchange_rate_snapshot)
            for item in self.project_items
        ]

        discount_type = self.discount_type_combo.currentData()
        discount_value = self.discount_rate_input.value()
        subtotal = sum(float(item.total) for item in self.project_items)

        if discount_type == "amount" and discount_value > 0 and subtotal > 0:
            discount_rate = (discount_value / subtotal) * 100
        else:
            discount_rate = discount_value

        project_data = {
            "name": normalized_project_name,
            "client_id": self._entity_ref(selected_client, "id", "_mongo_id", "name"),
            "status": selected_status,
            "description": "",
            "start_date": self.start_date_input.dateTime().toPyDateTime(),
            "end_date": self.end_date_input.dateTime().toPyDateTime(),
            "items": storage_items,
            "discount_rate": discount_rate,
            "tax_rate": self.tax_rate_input.value(),
            "project_notes": self.notes_input.toPlainText(),
            "currency": currency_code,
            "exchange_rate_snapshot": exchange_rate_snapshot,
        }

        payment_data = {}
        payment_amount = self.payment_amount_input.value()
        selected_account = self.payment_account_combo.currentData()

        if payment_amount > 0 and not selected_account:
            QMessageBox.warning(self, "خطأ", "الرجاء اختيار الحساب المستلم للدفعة المقدمة.")
            return

        if payment_amount > 0 and selected_account:
            payment_data = {
                "amount": amount_to_egp(payment_amount, currency_code, exchange_rate_snapshot),
                "date": self.payment_date_input.dateTime().toPyDateTime(),
                "account_id": selected_account.code,
            }
            try:
                if hasattr(self, "payment_method_combo"):
                    chosen_method = self.payment_method_combo.currentData()
                    if chosen_method:
                        payment_data["method"] = chosen_method
            except Exception:
                pass

        if discount_type == "amount":
            discount_amount_calc = min(discount_value, subtotal)
        else:
            discount_amount_calc = subtotal * (discount_rate / 100)
        taxable_amount = subtotal - discount_amount_calc
        tax_rate = self.tax_rate_input.value()
        tax_amount = taxable_amount * (tax_rate / 100)
        total_amount = taxable_amount + tax_amount

        if not self.is_editing and total_amount > 0:
            min_payment = total_amount * 0.70
            if payment_amount < min_payment:
                payment_percent = (payment_amount / total_amount * 100) if total_amount > 0 else 0
                suffix_text = self._current_currency_suffix()
                warning_message = (
                    f"الدفعة المقدمة ({payment_amount:,.2f} {suffix_text}) تمثل فقط {payment_percent:.1f}% من إجمالي المشروع ({total_amount:,.2f} {suffix_text})."
                    "\n\n"
                    f"الحد الأدنى الموصى به: 70% ({min_payment:,.2f} {suffix_text})"
                    "\n\n"
                    "هل تريد المتابعة على أي حال؟"
                )
                reply = QMessageBox.warning(
                    self,
                    "⚠️ تحذير - دفعة مقدمة منخفضة",
                    warning_message,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    return

        self._set_save_busy(True)
        try:
            if self.is_editing:
                project_ref = self._entity_ref(self.project_to_edit, "id", "_mongo_id", "name")
                self.project_service.update_project(project_ref, project_data)
            else:
                self.project_service.create_project(project_data, payment_data)

            if should_close or self.is_editing:
                self.accept()
            else:
                QMessageBox.information(self, "✅ تم الحفظ", "تم حفظ المشروع بنجاح")
                self._reset_form()
        except Exception as e:
            notify_error(f"فشل الحفظ: {e}", "خطأ")
        finally:
            self._set_save_busy(False)

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """⚡ معالجة إغلاق النافذة - تنظيف الموارد"""
        try:
            # فصل الإشارات لمنع memory leaks
            try:
                self.items_table.cellChanged.disconnect()
            except (TypeError, RuntimeError):
                pass

            # تنظيف أي موارد أخرى
            self.project_items.clear()

        except Exception:
            pass  # تجاهل الأخطاء عند الإغلاق

        event.accept()


class ProjectManagerTab(QWidget):
    def __init__(
        self,
        project_service: ProjectService,
        client_service: ClientService,
        service_service: ServiceService,
        accounting_service: AccountingService,
        expense_service: ExpenseService,
        printing_service=None,
        template_service=None,
        parent=None,
    ):
        super().__init__(parent)

        self.project_service = project_service
        self.client_service = client_service
        self.service_service = service_service
        self.accounting_service = accounting_service
        self.expense_service = expense_service
        self.printing_service = printing_service
        self.template_service = template_service
        self.projects_list: list[schemas.Project] = []
        self.selected_project: schemas.Project | None = None
        self._current_page = 1
        self._page_size = 100
        self._current_page_projects: list[schemas.Project] = []

        # === استخدام Splitter للتجاوب التلقائي ===

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(outer_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Splitter رئيسي يتحول من أفقي لعمودي حسب الحجم
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStyleSheet(
            """
            QSplitter::handle {
                background-color: #334155;
                width: 3px;
                margin: 0 3px;
            }
        """
        )
        outer_layout.addWidget(self.main_splitter)

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)

        app_signals.safe_connect(app_signals.projects_changed, self._on_projects_changed)
        app_signals.safe_connect(app_signals.payments_changed, self._on_projects_changed)

        # --- 1. الجزء الأيسر (الجدول والأزرار) ---
        left_widget = QWidget()
        left_panel = QVBoxLayout(left_widget)
        left_panel.setContentsMargins(5, 5, 5, 5)

        # === شريط الأزرار المتجاوب ===

        self.toolbar = ResponsiveToolbar()

        self.add_button = QPushButton("➕ إضافة مشروع")
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
        self.profit_button = QPushButton("📊 ربحية المشروع")
        self.profit_button.setStyleSheet(BUTTON_STYLES["info"])
        self.profit_button.setFixedHeight(28)
        self.profit_button.clicked.connect(self.open_profit_dialog)
        self.profit_button.setEnabled(False)

        # زرار حفظ الفاتورة
        self.print_button = QPushButton("💾 حفظ الفاتورة")
        self.print_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.print_button.setFixedHeight(28)
        self.print_button.clicked.connect(self.print_invoice)
        self.print_button.setEnabled(False)

        # 🗑️ زرار حذف المشروع
        self.delete_button = QPushButton("🗑️ حذف المشروع")
        self.delete_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_button.setFixedHeight(28)
        self.delete_button.clicked.connect(self.delete_selected_project)
        self.delete_button.setEnabled(False)

        # أزرار قوالب الفواتير
        self.preview_template_button = QPushButton("📂 فتح الفاتورة")
        self.preview_template_button.setStyleSheet(BUTTON_STYLES["info"])
        self.preview_template_button.setFixedHeight(28)
        self.preview_template_button.clicked.connect(self.preview_invoice_template)
        self.preview_template_button.setEnabled(False)

        # زرار التحديث
        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.setFixedHeight(28)
        self.refresh_button.clicked.connect(self.load_projects_data)
        self.refresh_currency_rates_button = QPushButton("🌐 تحديث الأسعار من الإنترنت")
        self.refresh_currency_rates_button.setStyleSheet(BUTTON_STYLES["info"])
        self.refresh_currency_rates_button.setFixedHeight(28)
        self.refresh_currency_rates_button.clicked.connect(
            self._refresh_currency_rates_for_projects
        )

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
        self.toolbar.addButton(self.refresh_currency_rates_button)
        self.toolbar.addWidget(self.show_archived_checkbox)

        left_panel.addWidget(self.toolbar)

        table_groupbox = QGroupBox("قايمة المشاريع")
        table_layout = QVBoxLayout()
        table_groupbox.setLayout(table_layout)

        # === UNIVERSAL SEARCH BAR ===

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
        self._preview_debounce_timer = None
        self.projects_table.itemSelectionChanged.connect(
            self.on_project_selection_changed_debounced
        )
        self.projects_table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        # إضافة دبل كليك للتعديل
        self.projects_table.itemDoubleClicked.connect(self.open_editor_for_selected)

        # إضافة قائمة السياق (كليك يمين)
        self._setup_context_menu()

        table_layout.addWidget(self.projects_table)

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
        table_layout.addLayout(pagination_layout)

        # === إضافة شريط ملخص الفواتير ===
        summary_frame = QFrame()
        summary_frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLORS["bg_medium"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
                padding: 8px;
            }}
        """
        )
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
        self.preview_groupbox.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.preview_groupbox.setStyleSheet(
            """
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(6, 28, 58, 0.96),
                    stop:1 rgba(6, 33, 72, 0.98));
                border: 1px solid rgba(10, 108, 241, 0.22);
                border-radius: 14px;
                margin: 0px;
                padding: 0px;
            }
        """
        )
        preview_layout = QVBoxLayout()
        preview_layout.setSpacing(6)
        preview_layout.setContentsMargins(6, 6, 6, 6)
        self.preview_groupbox.setLayout(preview_layout)

        header_frame = QFrame()
        header_frame.setObjectName("preview_header_frame")
        header_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_frame.setMaximumHeight(64)
        header_frame.setStyleSheet(
            """
            QFrame#preview_header_frame {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 12px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """
        )
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(6, 5, 6, 5)
        header_layout.setSpacing(8)

        header_left = QVBoxLayout()
        header_left.setSpacing(2)
        self.preview_project_title_label = QLabel("📊 لوحة ربحية المشروع")
        self.preview_project_title_label.setStyleSheet(
            "color: #E5E7EB; font-size: 12px; font-weight: bold; background: transparent; border: none;"
        )
        self.preview_project_meta_label = QLabel("—")
        self.preview_project_meta_label.setStyleSheet(
            "color: rgba(255,255,255,0.70); font-size: 9px; background: transparent; border: none;"
        )
        header_left.addWidget(self.preview_project_title_label)
        header_left.addWidget(self.preview_project_meta_label)

        header_layout.addLayout(header_left, 1)

        self.preview_project_status_chip = QLabel("جاهز")
        self.preview_project_status_chip.setStyleSheet(
            """
            QLabel {
                padding: 4px 10px;
                border-radius: 10px;
                background: rgba(16, 185, 129, 0.16);
                border: 1px solid rgba(16, 185, 129, 0.35);
                color: #D1FAE5;
                font-size: 10px;
                font-weight: bold;
            }
        """
        )
        self.preview_project_status_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.preview_project_status_chip, 0, Qt.AlignmentFlag.AlignRight)

        preview_layout.addWidget(header_frame)

        kpi_container = QWidget()
        kpi_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        kpi_container.setMaximumHeight(145)
        kpi_grid = QGridLayout(kpi_container)
        kpi_grid.setHorizontalSpacing(8)
        kpi_grid.setVerticalSpacing(6)
        kpi_grid.setContentsMargins(0, 0, 0, 0)

        self.revenue_card = self.create_kpi_card(
            "إجمالي العقد", "0.00", "#0A6CF1", "💰", variant="revenue"
        )
        self.paid_card = self.create_kpi_card("المدفوع", "0.00", "#10b981", "✅", variant="paid")
        self.expenses_card = self.create_kpi_card(
            "إجمالي المصروفات", "0.00", "#ef4444", "💸", variant="expenses"
        )
        self.due_card = self.create_kpi_card("المتبقي", "0.00", "#ef4444", "⏳", variant="due")
        self.net_profit_card = self.create_kpi_card(
            "صافي الربح", "0.00", "#8B2CF5", "📈", variant="net"
        )
        self.collection_card = self.create_kpi_card(
            "نسبة التحصيل", "0", "#F59E0B", "🎯", value_is_percent=True, variant="collection"
        )

        kpi_grid.addWidget(self.revenue_card, 0, 0)
        kpi_grid.addWidget(self.paid_card, 0, 1)
        kpi_grid.addWidget(self.due_card, 0, 2)
        kpi_grid.addWidget(self.expenses_card, 1, 0)
        kpi_grid.addWidget(self.net_profit_card, 1, 1)
        kpi_grid.addWidget(self.collection_card, 1, 2)

        kpi_grid.setColumnStretch(0, 1)
        kpi_grid.setColumnStretch(1, 1)
        kpi_grid.setColumnStretch(2, 1)
        preview_layout.addWidget(kpi_container)

        self.preview_tabs = QTabWidget()
        self.preview_tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 12px;
                top: -1px;
                background: rgba(255,255,255,0.02);
            }
            QTabBar::tab {
                padding: 6px 10px;
                margin: 0 2px;
                border: 1px solid rgba(255,255,255,0.08);
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                background: rgba(0,0,0,0.16);
                color: rgba(255,255,255,0.78);
                font-size: 10pt;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: rgba(10, 108, 241, 0.22);
                border-color: rgba(10, 108, 241, 0.35);
                color: white;
            }
            """
        )

        payments_tab = QWidget()
        payments_layout = QVBoxLayout(payments_tab)
        payments_layout.setContentsMargins(8, 8, 8, 8)
        payments_layout.setSpacing(8)
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
        self.preview_payments_meta = payments_section["meta"]
        payments_layout.addWidget(payments_section["frame"], 1)
        self.preview_tabs.addTab(payments_tab, "💳 الدفعات")

        expenses_tab = QWidget()
        expenses_layout = QVBoxLayout(expenses_tab)
        expenses_layout.setContentsMargins(8, 8, 8, 8)
        expenses_layout.setSpacing(8)
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
        self.preview_expenses_meta = expenses_section["meta"]
        expenses_layout.addWidget(expenses_section["frame"], 1)
        self.preview_tabs.addTab(expenses_tab, "💸 المصروفات")

        tasks_tab = QWidget()
        tasks_layout = QVBoxLayout(tasks_tab)
        tasks_layout.setContentsMargins(8, 8, 8, 8)
        tasks_layout.setSpacing(8)
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
        self.preview_tasks_meta = tasks_section["meta"]
        self.add_task_btn = tasks_section.get("add_btn")
        if self.add_task_btn:
            self.add_task_btn.clicked.connect(self._on_add_task_for_project)
        tasks_layout.addWidget(tasks_section["frame"], 1)
        self.preview_tabs.addTab(tasks_tab, "📋 المهام")

        self.preview_tabs.setDocumentMode(True)
        self.preview_tabs.setUsesScrollButtons(True)
        self.preview_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.preview_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_tabs.setMinimumHeight(220)
        preview_layout.addWidget(self.preview_tabs, 1)

        preview_scroll.setWidget(self.preview_groupbox)
        self.main_splitter.addWidget(preview_scroll)
        self._preview_scroll = preview_scroll

        # تعيين النسب الافتراضية للـ splitter (70% للجدول، 30% للمعاينة)
        self.main_splitter.setStretchFactor(0, 8)
        self.main_splitter.setStretchFactor(1, 2)

        # تعيين الحد الأدنى للعرض - زيادة عرض المعاينة
        preview_scroll.setMinimumWidth(220)
        self._apply_preview_splitter_sizes()

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_projects_data() - يتم استدعاؤها من MainWindow
        self.on_project_selection_changed()

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        """الحفاظ على المعاينة بجانب الجدول مع ضبط النسب حسب العرض."""
        super().resizeEvent(event)
        if self.main_splitter.orientation() != Qt.Orientation.Horizontal:
            self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
        self._apply_preview_splitter_sizes()

    def _apply_preview_splitter_sizes(self):
        if not hasattr(self, "main_splitter") or not self.main_splitter:
            return
        if self.main_splitter.orientation() != Qt.Orientation.Horizontal:
            return
        total = self.width()
        if total <= 0:
            return
        preview_min = 220
        preview_w = int(total * (0.30 if total < 1200 else 0.26))
        preview_w = max(preview_min, min(preview_w, max(preview_min, total - 360)))
        left_w = max(300, total - preview_w)
        try:
            self.main_splitter.setSizes([left_w, preview_w])
        except Exception:
            pass

    def create_kpi_card(
        self,
        title: str,
        value: str,
        accent: str,
        icon: str,
        variant: str = "",
        value_is_percent: bool = False,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName(f"kpi_card_{variant}")
        card.setProperty("value_label_name", "value_label")
        card.setProperty("base_accent", accent)
        card.setProperty("variant", variant)
        card.setProperty("value_is_percent", bool(value_is_percent))
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setMinimumHeight(48)
        card.setMaximumHeight(66)

        # ⚡ استخدام سلكتور محدد لمنع ظهور المربعات حول الـ Labels
        card.setStyleSheet(
            f"""
            QFrame#kpi_card_{variant} {{
                background: rgba(255, 255, 255, 0.035);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
            """
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        title_label = QLabel(f"{icon} {title}")
        title_label.setStyleSheet(
            "color: rgba(255,255,255,0.78); font-size: 9pt; font-weight: bold; border: none; background: transparent;"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(title_label, 1)

        layout.addLayout(top_row)

        value_label = QLabel(value)
        value_label.setObjectName("value_label")
        value_label.setStyleSheet(
            "color: white; font-weight: 800; font-size: 11pt; border: none; background: transparent;"
        )
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(value_label)

        return card

    def update_card_value(self, card: QFrame, value: float):
        try:
            obj_name = card.property("value_label_name") or "value_label"
            value_label = card.findChild(QLabel, obj_name)
            if value_label:
                variant = (card.property("variant") or "").strip().lower()
                value_is_percent = bool(card.property("value_is_percent"))

                if value_is_percent:
                    value_label.setText(f"{value:.0f}%")
                else:
                    value_label.setText(f"{value:,.2f} EGP")

                if variant == "collection":
                    ratio = clamp01((float(value) if value is not None else 0.0) / 100.0)
                    self._apply_kpi_ratio_style(card, ratio)
        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل تحديث الكارت: {e}")

    def _apply_kpi_ratio_style(self, card: QFrame, ratio: float):
        r = clamp01(ratio)
        accent = color_for_ratio(r)
        variant = (card.property("variant") or "").strip()
        obj_name = card.objectName() or f"kpi_card_{variant}"

        card.setStyleSheet(
            f"""
            QFrame#{obj_name} {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {accent}33,
                    stop:1 rgba(255, 255, 255, 0.04));
                border: 1px solid {accent}44;
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
            """
        )

    def _apply_profit_kpi_ratios(self, profit_data: dict):
        try:
            revenue = float(profit_data.get("total_revenue", 0) or 0.0)
            paid = float(profit_data.get("total_paid", 0) or 0.0)
            expenses = float(profit_data.get("total_expenses", 0) or 0.0)
            net = float(profit_data.get("net_profit", 0) or 0.0)
            due = float(profit_data.get("balance_due", 0) or 0.0)

            paid_ratio = (paid / revenue) if revenue > 0 else 0.0
            due_ratio_good = 1.0 - (due / revenue) if revenue > 0 else 0.0
            expenses_ratio_good = 1.0 - (expenses / revenue) if revenue > 0 else 0.0
            net_ratio = ((net / revenue) + 1.0) / 2.0 if revenue > 0 else 0.5

            if hasattr(self, "revenue_card"):
                self._apply_kpi_ratio_style(self.revenue_card, 0.5)
            if hasattr(self, "paid_card"):
                self._apply_kpi_ratio_style(self.paid_card, paid_ratio)
            if hasattr(self, "due_card"):
                self._apply_kpi_ratio_style(self.due_card, due_ratio_good)
            if hasattr(self, "expenses_card"):
                self._apply_kpi_ratio_style(self.expenses_card, expenses_ratio_good)
            if hasattr(self, "net_profit_card"):
                self._apply_kpi_ratio_style(self.net_profit_card, net_ratio)
            if hasattr(self, "collection_card"):
                self._apply_kpi_ratio_style(self.collection_card, paid_ratio)
        except Exception:
            pass

    def _create_preview_section(
        self, title: str, headers: list, resize_modes: list, show_add_btn: bool = False
    ) -> dict:
        frame = QFrame()
        frame.setObjectName("preview_section_frame")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame.setStyleSheet(
            """
            QFrame#preview_section_frame {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 12px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(7, 5, 7, 6)
        layout.setSpacing(5)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "color: #93C5FD; font-size: 10pt; font-weight: bold; background: transparent;"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(title_label, 1)

        meta_label = QLabel("—")
        meta_label.setStyleSheet(
            "color: rgba(255,255,255,0.70); font-size: 9pt; background: transparent;"
        )
        meta_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(meta_label)

        add_btn = None
        if show_add_btn:
            add_btn = QPushButton("➕ إضافة مهمة")
            add_btn.setMinimumSize(80, 26)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setStyleSheet(
                """
                QPushButton {
                    background: rgba(139, 44, 245, 0.90);
                    color: white;
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 10px;
                    font-size: 9pt;
                    font-weight: bold;
                    padding: 4px 10px;
                }
                QPushButton:hover { background: rgba(147, 51, 234, 0.95); }
                QPushButton:pressed { background: rgba(124, 58, 237, 0.95); }
            """
            )
            header_row.addWidget(add_btn)

        layout.addLayout(header_row)

        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.setShowGrid(False)
        table.setStyleSheet(
            """
            QTableWidget {
                background-color: rgba(0, 0, 0, 0.18);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                gridline-color: rgba(255,255,255,0.06);
                font-size: 9pt;
                alternate-background-color: rgba(255,255,255,0.03);
            }
            QTableWidget::item {
                padding: 3px 5px;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            QTableWidget::item:selected {
                background-color: rgba(10, 108, 241, 0.45);
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(10, 108, 241, 0.85),
                    stop:1 rgba(29, 78, 216, 0.85));
                color: white;
                padding: 4px;
                border: none;
                border-right: 1px solid rgba(255,255,255,0.14);
                font-size: 8pt;
                font-weight: bold;
            }
        """
        )

        fix_table_rtl(table)

        header = table.horizontalHeader()
        for i, mode in enumerate(resize_modes):
            header.setSectionResizeMode(i, mode)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFixedHeight(30)

        table.verticalHeader().setDefaultSectionSize(26)
        table.verticalHeader().setVisible(False)
        table.setWordWrap(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setMinimumHeight(140)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(table, 1)

        result = {"frame": frame, "table": table, "meta": meta_label}
        if add_btn:
            result["add_btn"] = add_btn
        return result

    def _setup_context_menu(self):
        """إعداد قائمة السياق (كليك يمين) للجدول"""

        # ⚡ تثبيت فلتر لتحديد flag الكليك يمين
        self._right_click_blocker = RightClickBlocker(self.projects_table, self.projects_table)
        self.projects_table.viewport().installEventFilter(self._right_click_blocker)

        self.projects_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.projects_table.customContextMenuRequested.connect(self._show_custom_context_menu)

    def _show_custom_context_menu(self, position):
        """⚡ عرض قائمة السياق"""

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
        project = self._project_from_row(row)
        if project:
            self.selected_project = project

        # إنشاء القائمة
        menu = QMenu(self.projects_table)
        menu.setStyleSheet(
            f"""
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
        """
        )

        # إضافة الإجراءات
        view_action = QAction("👁️ عرض التفاصيل", self.projects_table)
        view_action.triggered.connect(self.open_editor_for_selected)
        menu.addAction(view_action)

        edit_action = QAction("✏️ تعديل المشروع", self.projects_table)
        edit_action.triggered.connect(self.open_editor_for_selected)
        menu.addAction(edit_action)

        menu.addSeparator()

        payment_action = QAction("💰 تسجيل دفعة", self.projects_table)
        payment_action.triggered.connect(self.open_payment_dialog)
        menu.addAction(payment_action)

        expense_action = QAction("💸 إضافة مصروف", self.projects_table)
        expense_action.triggered.connect(self._add_expense_for_project)
        menu.addAction(expense_action)

        profit_action = QAction("📊 ربحية المشروع", self.projects_table)
        profit_action.triggered.connect(self._show_profit_dialog)
        menu.addAction(profit_action)

        print_action = QAction("💾 حفظ الفاتورة", self.projects_table)
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
            project = self._project_from_row(row)
            if project:

                dialog = ProjectProfitDialog(project, self.project_service, self)
                dialog.exec()

    def _print_invoice(self):
        """طباعة فاتورة المشروع"""
        selected = self.projects_table.selectedIndexes()
        if selected:
            row = selected[0].row()
            project = self._project_from_row(row)
            if project:
                self.selected_project = project
                self.print_invoice()

    def _add_expense_for_project(self):
        """إضافة مصروف للمشروع المحدد"""
        if not self.selected_project:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار مشروع أولاً")
            return

        try:

            # استخدام نفس المرجع الثابت المعتمد في بقية المسارات لتجنب
            # السقوط إلى الاسم عند وجود id و _mongo_id معًا.
            project_id = self._project_ref(self.selected_project, self.selected_project.name)
            project_name = self.selected_project.name

            # فتح نافذة إضافة مصروف مع تعبئة المشروع تلقائياً
            dialog = ExpenseEditorDialog(
                expense_service=self.expense_service,
                project_service=self.project_service,
                accounting_service=self.accounting_service,
                parent=self,
                pre_selected_project_id=project_id,
                pre_selected_project_name=project_name,
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # تحديث البيانات
                self.load_projects_data()
                # تحديث المعاينة
                if self.selected_project:
                    self.on_project_selection_changed()

                notify_success(f"تم إضافة مصروف للمشروع: {project_name}")

        except ImportError:
            QMessageBox.warning(self, "خطأ", "لم يتم العثور على نافذة إضافة المصروفات")
        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل إضافة مصروف: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل إضافة المصروف:\n{e}")

    def on_project_selection_changed(self):
        """(معدلة) تملى لوحة المعاينة بكل التفاصيل - ⚡ محسّنة للسرعة"""
        # ⚡ تجاهل التحديث إذا كان الكليك يمين (لمنع التحميل المتكرر)

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
            try:
                if hasattr(self, "preview_project_title_label"):
                    self.preview_project_title_label.setText(
                        f"📊 لوحة ربحية المشروع: {project_name}"
                    )
                if hasattr(self, "preview_project_meta_label"):
                    self.preview_project_meta_label.setText("جاري تحميل البيانات…")
                if hasattr(self, "preview_project_status_chip"):
                    self.preview_project_status_chip.setText("⏳ تحميل")
                    self.preview_project_status_chip.setStyleSheet(
                        """
                        QLabel {
                            padding: 4px 10px;
                            border-radius: 10px;
                            background: rgba(245, 158, 11, 0.16);
                            border: 1px solid rgba(245, 158, 11, 0.35);
                            color: #FDE68A;
                            font-size: 10px;
                            font-weight: bold;
                        }
                        """
                    )
            except Exception:
                pass

            self.selected_project = self._project_from_row(selected_row)

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
            # ⚡ تحميل البيانات في الخلفية لمنع التجميد
            self._load_preview_data_async(self.selected_project)

            return

        self.selected_project = None
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.profit_button.setEnabled(False)
        self.payment_button.setEnabled(False)
        self.print_button.setEnabled(False)
        self.preview_template_button.setEnabled(False)  # ✅ تعطيل زرار المعاينة
        self.preview_groupbox.setVisible(False)

    def _get_total_pages(self) -> int:
        total = len(self.projects_list)
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
            page_projects = self.projects_list
        else:
            start_index = (self._current_page - 1) * self._page_size
            end_index = start_index + self._page_size
            page_projects = self.projects_list[start_index:end_index]

        self._current_page_projects = page_projects
        self._populate_projects_table(page_projects)
        self._update_pagination_controls(total_pages)

    def _populate_projects_table(self, projects: list[schemas.Project]):
        def create_centered_item(text):
            item = QTableWidgetItem(str(text) if text else "")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            return item

        self.projects_table.setRowCount(len(projects))
        for row, project in enumerate(projects):
            invoice_number = getattr(project, "invoice_number", None) or ""
            project_ref = self._project_ref(project, project.name)
            project_client_id = str(getattr(project, "client_id", "") or "")
            client_display = self._client_display_name(project_client_id)

            row_items = [
                create_centered_item(invoice_number),
                create_centered_item(project.name),
                create_centered_item(client_display),
                create_centered_item(project.status.value),
                create_centered_item(self._format_date(project.start_date)),
            ]
            for column, item in enumerate(row_items):
                item.setData(Qt.ItemDataRole.UserRole, project_ref)
                item.setData(Qt.ItemDataRole.UserRole + 1, project_client_id)
                self.projects_table.setItem(row, column, item)

        self.projects_table.blockSignals(False)
        self.projects_table.setUpdatesEnabled(True)
        self.projects_table.setSortingEnabled(True)

    def _update_pagination_controls(self, total_pages: int):
        self.page_info_label.setText(f"صفحة {self._current_page} / {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

    def _on_page_size_changed(self, value: str):
        if value == "كل":
            self._page_size = max(1, len(self.projects_list))
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

    def on_project_selection_changed_debounced(self):
        if is_right_click_active():
            return
        if not hasattr(self, "_preview_debounce_timer") or self._preview_debounce_timer is None:
            self._preview_debounce_timer = QTimer(self)
            self._preview_debounce_timer.setSingleShot(True)
            self._preview_debounce_timer.timeout.connect(self.on_project_selection_changed)
        self._preview_debounce_timer.start(120)

    @staticmethod
    def _preview_text_key(value) -> str:
        return normalize_user_text(str(value or "")).strip().casefold()

    def _project_ref(self, project: schemas.Project | None, fallback: str | None = None) -> str:
        if project is not None:
            for field in ("id", "_mongo_id", "name"):
                value = getattr(project, field, None)
                text = str(value or "").strip()
                if text:
                    return text
        return str(fallback or "").strip()

    def _client_display_name(self, client_ref: str | None) -> str:
        client_text = str(client_ref or "").strip()
        if not client_text:
            return ""

        try:
            client = self.client_service.get_client_by_id(client_text)
            if client and getattr(client, "name", None):
                return str(client.name)
        except Exception:
            pass

        return client_text

    def _project_cache_key(self, project_ref: str, client_id: str | None = None) -> str:
        return f"{self._preview_text_key(client_id)}::{self._preview_text_key(project_ref)}"

    def _project_identity(self, project: schemas.Project | None) -> str:
        if project is None:
            return ""
        return self._project_cache_key(
            self._project_ref(project, getattr(project, "name", "")),
            str(getattr(project, "client_id", "") or ""),
        )

    def _project_from_row(self, row: int) -> schemas.Project | None:
        project_ref = ""
        client_id = ""
        for column in range(self.projects_table.columnCount()):
            item = self.projects_table.item(row, column)
            if not item:
                continue
            project_ref = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
            client_id = str(item.data(Qt.ItemDataRole.UserRole + 1) or "").strip()
            if project_ref:
                break

        if project_ref:
            project = self.project_service.get_project_by_id(project_ref, client_id or None)
            if project:
                return project

        project_name_item = self.projects_table.item(row, 1)
        project_name = project_name_item.text().strip() if project_name_item else ""
        if not project_name:
            return None

        matches = [
            proj
            for proj in getattr(self, "_current_page_projects", []) or []
            if (getattr(proj, "name", "") or "").strip() == project_name
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def _payment_preview_key(self, payment) -> tuple:
        date_short = str(getattr(payment, "date", "") or "")[:10]
        try:
            amount = round(float(getattr(payment, "amount", 0.0) or 0.0), 2)
        except (TypeError, ValueError):
            amount = 0.0

        return (
            "sig",
            self._preview_text_key(getattr(payment, "project_id", "")),
            date_short,
            amount,
            self._preview_text_key(getattr(payment, "client_id", "")),
            self._preview_text_key(getattr(payment, "account_id", "")),
            self._preview_text_key(getattr(payment, "method", "")),
        )

    def _dedupe_preview_payments(self, payments: list) -> list:
        deduped: dict[tuple, Any] = {}
        for payment in payments:
            key = self._payment_preview_key(payment)
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = payment
                continue

            existing_has_mongo = bool(str(getattr(existing, "_mongo_id", "") or "").strip())
            current_has_mongo = bool(str(getattr(payment, "_mongo_id", "") or "").strip())
            if current_has_mongo and not existing_has_mongo:
                deduped[key] = payment

        return list(deduped.values())

    def _expense_preview_key(self, expense) -> tuple:
        date_short = str(getattr(expense, "date", "") or "")[:10]
        try:
            amount = round(float(getattr(expense, "amount", 0.0) or 0.0), 2)
        except (TypeError, ValueError):
            amount = 0.0
        account_id = self._preview_text_key(getattr(expense, "account_id", ""))
        payment_account_id = self._preview_text_key(getattr(expense, "payment_account_id", ""))
        effective_payment_account = payment_account_id or account_id

        return (
            "sig",
            self._preview_text_key(getattr(expense, "project_id", "")),
            date_short,
            amount,
            self._preview_text_key(getattr(expense, "category", "")),
            self._preview_text_key(getattr(expense, "description", "")),
            account_id,
            effective_payment_account,
        )

    def _dedupe_preview_expenses(self, expenses: list) -> list:
        deduped: dict[tuple, Any] = {}
        for expense in expenses:
            key = self._expense_preview_key(expense)
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = expense
                continue

            existing_has_mongo = bool(str(getattr(existing, "_mongo_id", "") or "").strip())
            current_has_mongo = bool(str(getattr(expense, "_mongo_id", "") or "").strip())
            if current_has_mongo and not existing_has_mongo:
                deduped[key] = expense

        return list(deduped.values())

    def _load_preview_data_async(self, project: schemas.Project):
        """⚡⚡ تحميل بيانات المعاينة - محسّن للسرعة القصوى مع بيانات حديثة"""

        project_name = getattr(project, "name", "") or ""
        project_ref = self._project_ref(project, project_name)
        project_client_id = str(getattr(project, "client_id", "") or "")
        project_id_for_tasks = project_ref
        cache_key = self._project_cache_key(project_ref, project_client_id)
        expected_identity = self._project_identity(project)

        # ⚡ مسح محتويات الجداول فوراً عند بدء التحميل لمنع ظهور بيانات المشروع السابق
        self._populate_payments_table_fast([])
        self._populate_expenses_table_fast([])
        self._populate_tasks_table_fast([])

        if not hasattr(self, "_preview_cache"):
            self._preview_cache = {}
            self._preview_cache_ttl_s = 20.0

        if not hasattr(self, "_preview_cache_connected"):

            def _invalidate(_data_type: str):
                table_name = str(_data_type or "").strip().lower()
                if table_name and table_name not in {
                    "projects",
                    "payments",
                    "expenses",
                    "tasks",
                    "invoices",
                    "clients",
                }:
                    return
                if hasattr(self, "_preview_cache"):
                    self._preview_cache.clear()

            app_signals.data_changed.connect(_invalidate)
            self._preview_cache_connected = True

        cache_entry = self._preview_cache.get(cache_key)
        if cache_entry:
            import time

            if (time.monotonic() - cache_entry["ts"]) <= self._preview_cache_ttl_s:
                data = cache_entry["data"]
                profit_data = data.get("profit", {})
                self.update_card_value(self.revenue_card, profit_data.get("total_revenue", 0))
                self.update_card_value(self.paid_card, profit_data.get("total_paid", 0))
                self.update_card_value(self.expenses_card, profit_data.get("total_expenses", 0))
                self.update_card_value(self.net_profit_card, profit_data.get("net_profit", 0))
                self.update_card_value(self.due_card, profit_data.get("balance_due", 0))
                revenue = float(profit_data.get("total_revenue", 0) or 0.0)
                paid = float(profit_data.get("total_paid", 0) or 0.0)
                ratio = (paid / revenue * 100.0) if revenue > 0 else 0.0
                self.update_card_value(self.collection_card, ratio)
                self._apply_profit_kpi_ratios(profit_data)
                try:
                    if hasattr(self, "preview_project_meta_label"):
                        self.preview_project_meta_label.setText("تم التحديث من الذاكرة المؤقتة")
                    if hasattr(self, "preview_project_status_chip"):
                        self.preview_project_status_chip.setText("✅ جاهز")
                        self.preview_project_status_chip.setStyleSheet(
                            """
                            QLabel {
                                padding: 4px 10px;
                                border-radius: 10px;
                                background: rgba(16, 185, 129, 0.16);
                                border: 1px solid rgba(16, 185, 129, 0.35);
                                color: #D1FAE5;
                                font-size: 10px;
                                font-weight: bold;
                            }
                            """
                        )
                except Exception:
                    pass

                payments = data.get("payments", [])
                expenses = data.get("expenses", [])
                tasks = data.get("tasks", [])

                unique_payments = self._dedupe_preview_payments(payments)
                unique_expenses = self._dedupe_preview_expenses(expenses)
                unique_tasks = list({(getattr(t, "id", None) or id(t)): t for t in tasks}.values())

                self._populate_payments_table_fast(unique_payments)
                self._populate_expenses_table_fast(unique_expenses)
                self._populate_tasks_table_fast(unique_tasks)
                return

        data_loader = get_data_loader()

        def fetch_all_data():
            try:
                raw_payments = (
                    self.project_service.get_payments_for_project(
                        project_ref,
                        client_id=project_client_id or None,
                    )
                    or []
                )
                raw_expenses = (
                    self.project_service.get_expenses_for_project(
                        project_ref,
                        client_id=project_client_id or None,
                    )
                    or []
                )
                payments = self._dedupe_preview_payments(raw_payments)
                expenses = self._dedupe_preview_expenses(raw_expenses)
                project_details = (
                    self.project_service.get_project_by_id(
                        project_ref,
                        project_client_id or None,
                    )
                    or project
                )

                total_revenue = (
                    float(project_details.total_amount or 0.0) if project_details else 0.0
                )
                total_paid = sum(float(getattr(p, "amount", 0.0) or 0.0) for p in payments)
                total_expenses = sum(float(getattr(e, "amount", 0.0) or 0.0) for e in expenses)
                net_profit = total_revenue - total_expenses
                balance_due = max(0.0, total_revenue - total_paid)

                profit_data = {
                    "total_revenue": total_revenue,
                    "total_expenses": total_expenses,
                    "net_profit": net_profit,
                    "total_paid": total_paid,
                    "balance_due": balance_due,
                }

                tasks = []
                try:
                    ts = TaskService()
                    tasks = ts.get_tasks_by_project(str(project_id_for_tasks)) or []
                except Exception as e:
                    safe_print(f"DEBUG: [ProjectManager] فشل جلب المهام في الخلفية: {e}")

                return {
                    "profit": profit_data,
                    "payments": payments,
                    "expenses": expenses,
                    "tasks": tasks,
                }
            except Exception as e:
                safe_print(f"CRITICAL ERROR in fetch_all_data: {e}")
                raise e

        def on_all_data_loaded(data):
            if self._project_identity(self.selected_project) != expected_identity:
                return

            import time

            self._preview_cache[cache_key] = {"ts": time.monotonic(), "data": data}

            profit_data = data.get("profit", {})
            self.update_card_value(self.revenue_card, profit_data.get("total_revenue", 0))
            self.update_card_value(self.paid_card, profit_data.get("total_paid", 0))
            self.update_card_value(self.expenses_card, profit_data.get("total_expenses", 0))
            self.update_card_value(self.net_profit_card, profit_data.get("net_profit", 0))
            self.update_card_value(self.due_card, profit_data.get("balance_due", 0))
            revenue = float(profit_data.get("total_revenue", 0) or 0.0)
            paid = float(profit_data.get("total_paid", 0) or 0.0)
            ratio = (paid / revenue * 100.0) if revenue > 0 else 0.0
            self.update_card_value(self.collection_card, ratio)
            self._apply_profit_kpi_ratios(profit_data)
            try:
                if hasattr(self, "preview_project_meta_label"):
                    self.preview_project_meta_label.setText(
                        f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    )
                if hasattr(self, "preview_project_status_chip"):
                    self.preview_project_status_chip.setText("✅ جاهز")
                    self.preview_project_status_chip.setStyleSheet(
                        """
                        QLabel {
                            padding: 4px 10px;
                            border-radius: 10px;
                            background: rgba(16, 185, 129, 0.16);
                            border: 1px solid rgba(16, 185, 129, 0.35);
                            color: #D1FAE5;
                            font-size: 10px;
                            font-weight: bold;
                        }
                        """
                    )
            except Exception:
                pass

            payments = data.get("payments", [])
            expenses = data.get("expenses", [])
            tasks = data.get("tasks", [])

            unique_payments = self._dedupe_preview_payments(payments)
            unique_expenses = self._dedupe_preview_expenses(expenses)
            unique_tasks = list({(getattr(t, "id", None) or id(t)): t for t in tasks}.values())

            self._populate_payments_table_fast(unique_payments)
            self._populate_expenses_table_fast(unique_expenses)
            self._populate_tasks_table_fast(unique_tasks)

        def on_error(error_msg: str):
            if self._project_identity(self.selected_project) != expected_identity:
                return
            safe_print(f"ERROR: فشل تحميل معاينة المشروع '{project_name}': {error_msg}")
            self.update_card_value(self.revenue_card, 0)
            self.update_card_value(self.paid_card, 0)
            self.update_card_value(self.expenses_card, 0)
            self.update_card_value(self.net_profit_card, 0)
            self.update_card_value(self.due_card, 0)
            self.update_card_value(self.collection_card, 0)
            try:
                if hasattr(self, "preview_project_meta_label"):
                    self.preview_project_meta_label.setText(f"تعذر تحميل البيانات: {error_msg}")
                if hasattr(self, "preview_project_status_chip"):
                    self.preview_project_status_chip.setText("❌ خطأ")
                    self.preview_project_status_chip.setStyleSheet(
                        """
                        QLabel {
                            padding: 4px 10px;
                            border-radius: 10px;
                            background: rgba(239, 68, 68, 0.16);
                            border: 1px solid rgba(239, 68, 68, 0.35);
                            color: #FECACA;
                            font-size: 10px;
                            font-weight: bold;
                        }
                        """
                    )
            except Exception:
                pass
            self._populate_payments_table_fast([])
            self._populate_expenses_table_fast([])
            self._populate_tasks_table_fast([])

        data_loader.load_async(
            operation_name="project_preview",
            load_function=fetch_all_data,
            on_success=on_all_data_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _populate_payments_table_fast(self, payments):
        """⚡⚡ ملء جدول الدفعات - نسخة فائقة السرعة"""
        table = None
        prev_block = False
        prev_sorting = False
        try:
            table = self.preview_payments_table
            prev_block = table.blockSignals(True)
            prev_sorting = table.isSortingEnabled()
            table.setSortingEnabled(False)
            table.setUpdatesEnabled(False)
            table.clearContents()
            table.setRowCount(0)

            if payments and len(payments) > 0:
                table.setRowCount(len(payments))

                # ⚡ تخزين الحسابات مؤقتاً
                accounts_cache = {}
                total_amount = 0.0

                for i, pay in enumerate(payments):
                    # معالجة التاريخ
                    try:
                        date_str = (
                            pay.date.strftime("%Y-%m-%d")
                            if hasattr(pay.date, "strftime")
                            else str(pay.date)[:10]
                        )
                    except:
                        date_str = "N/A"

                    # اسم الحساب
                    account_name = "Cash"
                    if pay.account_id:
                        if pay.account_id in accounts_cache:
                            account_name = accounts_cache[pay.account_id]
                        else:
                            try:
                                account = self.accounting_service.repo.get_account_by_code(
                                    pay.account_id
                                )
                                account_name = account.name if account else str(pay.account_id)
                                accounts_cache[pay.account_id] = account_name
                            except:
                                account_name = str(pay.account_id)
                    account_name = normalize_user_text(account_name) or "—"

                    # إنشاء العناصر
                    account_item = QTableWidgetItem(account_name)
                    account_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    account_item.setToolTip(account_name)

                    amount_item = QTableWidgetItem(f"{pay.amount:,.2f} ج.م")
                    amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    amount_item.setForeground(QColor("#10b981"))
                    try:
                        total_amount += float(getattr(pay, "amount", 0.0) or 0.0)
                    except Exception:
                        pass

                    date_item = QTableWidgetItem(date_str)
                    date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                    table.setItem(i, 0, account_item)
                    table.setItem(i, 1, amount_item)
                    table.setItem(i, 2, date_item)
                    try:
                        table.setRowHeight(i, 20)
                    except Exception:
                        pass
                try:
                    if hasattr(self, "preview_payments_meta") and self.preview_payments_meta:
                        self.preview_payments_meta.setText(
                            f"{len(payments)} دفعة • الإجمالي {total_amount:,.2f} ج.م"
                        )
                except Exception:
                    pass
            else:
                table.setRowCount(1)
                no_data = QTableWidgetItem("لا توجد دفعات مسجلة")
                no_data.setForeground(QColor("gray"))
                no_data.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(0, 0, no_data)
                table.setSpan(0, 0, 1, 3)
                try:
                    table.setRowHeight(0, 20)
                except Exception:
                    pass
                try:
                    if hasattr(self, "preview_payments_meta") and self.preview_payments_meta:
                        self.preview_payments_meta.setText("0 دفعة")
                except Exception:
                    pass
        except Exception as e:
            safe_print(f"ERROR: فشل ملء جدول الدفعات: {e}")
        finally:
            if table is not None:
                table.setUpdatesEnabled(True)
                table.setSortingEnabled(prev_sorting)
                table.blockSignals(prev_block)

    def _populate_expenses_table_fast(self, expenses):
        """⚡⚡ ملء جدول المصروفات - نسخة فائقة السرعة"""
        table = None
        prev_block = False
        prev_sorting = False
        try:
            table = self.preview_expenses_table
            prev_block = table.blockSignals(True)
            prev_sorting = table.isSortingEnabled()
            table.setSortingEnabled(False)
            table.setUpdatesEnabled(False)
            table.clearContents()
            table.setRowCount(0)

            if expenses and len(expenses) > 0:
                table.setRowCount(len(expenses))
                total_amount = 0.0

                for i, exp in enumerate(expenses):
                    try:
                        date_str = (
                            exp.date.strftime("%Y-%m-%d")
                            if hasattr(exp.date, "strftime")
                            else str(exp.date)[:10]
                        )
                    except:
                        date_str = "N/A"

                    amount_item = QTableWidgetItem(f"{exp.amount:,.2f} ج.م")
                    amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    amount_item.setForeground(QColor("#ef4444"))
                    try:
                        total_amount += float(getattr(exp, "amount", 0.0) or 0.0)
                    except Exception:
                        pass

                    raw_desc = exp.description or exp.category or "—"
                    desc_text = normalize_user_text(raw_desc) or "—"
                    desc_item = QTableWidgetItem(desc_text)
                    desc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    desc_item.setToolTip(desc_text)

                    date_item = QTableWidgetItem(date_str)
                    date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                    table.setItem(i, 0, amount_item)
                    table.setItem(i, 1, desc_item)
                    table.setItem(i, 2, date_item)
                    try:
                        table.setRowHeight(i, 20)
                    except Exception:
                        pass
                try:
                    if hasattr(self, "preview_expenses_meta") and self.preview_expenses_meta:
                        self.preview_expenses_meta.setText(
                            f"{len(expenses)} مصروف • الإجمالي {total_amount:,.2f} ج.م"
                        )
                except Exception:
                    pass
            else:
                table.setRowCount(1)
                no_data = QTableWidgetItem("لا توجد مصروفات مسجلة")
                no_data.setForeground(QColor("gray"))
                no_data.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(0, 0, no_data)
                table.setSpan(0, 0, 1, 3)
                try:
                    table.setRowHeight(0, 20)
                except Exception:
                    pass
                try:
                    if hasattr(self, "preview_expenses_meta") and self.preview_expenses_meta:
                        self.preview_expenses_meta.setText("0 مصروف")
                except Exception:
                    pass
        except Exception as e:
            safe_print(f"ERROR: فشل ملء جدول المصروفات: {e}")
        finally:
            if table is not None:
                table.setUpdatesEnabled(True)
                table.setSortingEnabled(prev_sorting)
                table.blockSignals(prev_block)

    def _populate_tasks_table_fast(self, tasks):
        """⚡⚡ ملء جدول المهام - نسخة فائقة السرعة"""
        table = None
        prev_block = False
        prev_sorting = False
        try:
            table = self.preview_tasks_table
            prev_block = table.blockSignals(True)
            prev_sorting = table.isSortingEnabled()
            table.setSortingEnabled(False)
            table.setUpdatesEnabled(False)
            table.clearContents()
            table.setRowCount(0)

            if tasks and len(tasks) > 0:
                table.setRowCount(len(tasks))

                priority_colors = {
                    "منخفضة": "#10B981",
                    "متوسطة": "#0A6CF1",
                    "عالية": "#FF6636",
                    "عاجلة": "#FF4FD8",
                }
                status_colors = {
                    "قيد الانتظار": "#B0C4DE",
                    "قيد التنفيذ": "#FF6636",
                    "مكتملة": "#10B981",
                    "ملغاة": "#FF4FD8",
                }

                for i, task in enumerate(tasks):
                    title_text = normalize_user_text(getattr(task, "title", "")) or "—"
                    title_item = QTableWidgetItem(title_text)
                    title_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    title_item.setToolTip(title_text)
                    table.setItem(i, 0, title_item)

                    priority_item = QTableWidgetItem(task.priority.value)
                    priority_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    priority_item.setForeground(
                        QColor(priority_colors.get(task.priority.value, "white"))
                    )
                    table.setItem(i, 1, priority_item)

                    status_item = QTableWidgetItem(task.status.value)
                    status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    status_item.setForeground(QColor(status_colors.get(task.status.value, "white")))
                    table.setItem(i, 2, status_item)

                    due_str = task.due_date.strftime("%Y-%m-%d") if task.due_date else "-"
                    if getattr(task, "due_time", None) and task.due_date:
                        due_str = f"{due_str} {task.due_time}"
                    due_item = QTableWidgetItem(due_str)
                    due_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    try:
                        if (
                            hasattr(task, "is_overdue")
                            and callable(task.is_overdue)
                            and task.is_overdue()
                        ):
                            due_item.setForeground(QColor("#ef4444"))
                    except Exception:
                        pass
                    table.setItem(i, 3, due_item)
                    try:
                        table.setRowHeight(i, 20)
                    except Exception:
                        pass
                try:
                    if hasattr(self, "preview_tasks_meta") and self.preview_tasks_meta:
                        self.preview_tasks_meta.setText(f"{len(tasks)} مهمة")
                except Exception:
                    pass
            else:
                table.setRowCount(1)
                no_data = QTableWidgetItem("لا توجد مهام مرتبطة")
                no_data.setForeground(QColor("gray"))
                table.setItem(0, 0, no_data)
                table.setSpan(0, 0, 1, 4)
                try:
                    table.setRowHeight(0, 20)
                except Exception:
                    pass
                try:
                    if hasattr(self, "preview_tasks_meta") and self.preview_tasks_meta:
                        self.preview_tasks_meta.setText("0 مهمة")
                except Exception:
                    pass
        except Exception as e:
            safe_print(f"ERROR: فشل ملء جدول المهام: {e}")
        finally:
            if table is not None:
                table.setUpdatesEnabled(True)
                table.setSortingEnabled(prev_sorting)
                table.blockSignals(prev_block)

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
                    account_name = "Cash"
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

    def _refresh_currency_rates_for_projects(self):
        repo = getattr(getattr(self, "accounting_service", None), "repo", None)
        if repo is None or not hasattr(repo, "update_all_exchange_rates"):
            QMessageBox.warning(self, "تعذر التحديث", "خدمة العملات غير متاحة حاليًا.")
            return

        button = getattr(self, "refresh_currency_rates_button", None)
        default_text = "🌐 تحديث الأسعار من الإنترنت"
        if button is not None:
            button.setEnabled(False)
            button.setText("⏳ جاري تحديث الأسعار...")

        def restore_button():
            if button is not None:
                button.setEnabled(True)
                button.setText(default_text)

        def refresh_rates():
            return repo.update_all_exchange_rates() or {}

        def on_success(result):
            try:
                notify_success("تم تحديث أسعار العملات بنجاح", title="العملات")
                QMessageBox.information(
                    self,
                    "نتيجة تحديث العملات",
                    _build_currency_update_summary(result),
                )
            finally:
                restore_button()

        def on_error(error_msg):
            restore_button()
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل تحديث أسعار العملات من الإنترنت:\n{error_msg}",
            )

        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="projects_currency_rates",
            load_function=refresh_rates,
            on_success=on_success,
            on_error=on_error,
            use_thread_pool=True,
        )

    def load_projects_data(self):
        """⚡ تحميل بيانات المشاريع في الخلفية لمنع التجميد"""
        safe_print("INFO: [ProjectManager] جاري تحميل بيانات المشاريع...")

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

                self._render_current_page()
                self.on_project_selection_changed()

                # ⚡ تحديث ملخص الفواتير
                self._update_invoices_summary()

                safe_print(f"INFO: [ProjectManager] ✅ تم تحميل {len(projects)} مشروع")

            except Exception as e:
                safe_print(f"ERROR: [ProjectManager] فشل تحديث الجدول: {e}")

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
        # ⚡ إبطال الـ cache أولاً لضمان جلب البيانات الجديدة من السيرفر
        if hasattr(self.project_service, "invalidate_cache"):
            self.project_service.invalidate_cache()
        if not self.isVisible():
            return
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
        """(معدلة) يفتح نافذة الحوار - غير مشروطة للمشاريع الجديدة"""
        dialog = ProjectEditorDialog(
            project_service=self.project_service,
            client_service=self.client_service,
            service_service=self.service_service,
            accounting_service=self.accounting_service,
            project_to_edit=project_to_edit,
            parent=None,  # ⚡ بدون parent لجعلها نافذة مستقلة
        )

        # ⚡ جعل النافذة غير مشروطة (Non-Modal) للمشاريع الجديدة
        if project_to_edit is None:
            # نافذة مستقلة يمكن تصغيرها
            dialog.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.WindowMinimizeButtonHint
                | Qt.WindowType.WindowMaximizeButtonHint
                | Qt.WindowType.WindowCloseButtonHint
            )
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

            # ربط إشارة الإغلاق بتحديث البيانات
            dialog.finished.connect(
                lambda result: (
                    self.load_projects_data() if result == QDialog.DialogCode.Accepted else None
                )
            )

            # عرض النافذة بدون انتظار (Non-Modal)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()

            # حفظ مرجع للنافذة لمنع garbage collection
            if not hasattr(self, "_open_dialogs"):
                self._open_dialogs = []
            self._open_dialogs.append(dialog)
            dialog.destroyed.connect(
                lambda: self._open_dialogs.remove(dialog) if dialog in self._open_dialogs else None
            )
        else:
            # للتعديل: نافذة مشروطة (Modal) كالمعتاد
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
            project_ref = self._project_ref(self.selected_project, project_name)
            success = self.project_service.delete_project(project_ref)

            if success:
                self.selected_project = None
                self.load_projects_data()
            else:
                notify_error("فشل حذف المشروع", "خطأ")

        except Exception as e:
            safe_print(f"ERROR: [ProjectManager] فشل حذف المشروع: {e}")

            traceback.print_exc()
            notify_error(f"فشل حذف المشروع: {e}", "خطأ")

    def open_payment_dialog(self):
        """فتح نافذة تسجيل دفعة جديدة للمشروع المحدد"""
        if not self.selected_project:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مشروع أولاً.")
            return

        safe_print(f"INFO: [ProjectManager] فتح شاشة تسجيل دفعة لـ: {self.selected_project.name}")

        # جلب حسابات البنك/الخزينة فقط (الخزينة والمحافظ الإلكترونية)
        all_accounts = self.accounting_service.repo.get_all_accounts()
        cash_accounts = filter_operational_cashboxes(all_accounts)

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
            payments_list = self._get_payments_list(project)
            safe_print(f"INFO: [ProjectManager] الدفعات المرسلة للطباعة: {payments_list}")

            # تجهيز معلومات العميل
            client_info = {
                "name": client.name,
                "company_name": getattr(client, "company_name", "") or "",
                "phone": client.phone or "---",
                "email": client.email or "",
                "address": client.address or "---",
                "logo_path": getattr(client, "logo_path", "") or "",
                "logo_data": getattr(client, "logo_data", "") or "",
            }

            # ⚡ استخدام template_service
            if self.template_service:
                safe_print("INFO: [ProjectManager] استخدام template_service للطباعة")
                exported_path = self.template_service.export_invoice_document(
                    project=project,
                    client_info=client_info,
                    payments=payments_list,
                    use_pdf=True,
                    open_file=False,
                )
                if exported_path:
                    if str(exported_path).lower().endswith(".pdf"):
                        QMessageBox.information(
                            self,
                            "✅ تم حفظ الفاتورة",
                            f"تم حفظ فاتورة PDF بنجاح.\n\n📄 {os.path.basename(exported_path)}",
                        )
                    else:
                        QMessageBox.warning(
                            self,
                            "⚠️ تم حفظ HTML",
                            f"تم حفظ الفاتورة كملف HTML.\n\n"
                            f"📄 {os.path.basename(exported_path)}\n\n"
                            f"💡 لإنشاء PDF، قم بتثبيت:\n"
                            f"   pip install weasyprint\n"
                            f"أو استخدم Google Chrome/Edge",
                        )
                else:
                    QMessageBox.critical(self, "خطأ", "فشل في حفظ الفاتورة")
                return

            # Fallback: استخدام InvoicePrintingService
            profit_data = self.project_service.get_project_profitability(
                self._project_ref(project, project.name),
                client_id=getattr(project, "client_id", None),
            )

            # Get settings service for company data
            settings_service = None
            if self.service_service and hasattr(self.service_service, "settings_service"):
                settings_service = self.service_service.settings_service

            # Fallback: استخدام InvoicePrintingService
            # Step D: Prepare the complete data dictionary
            # ⚡ استخدم رقم الفاتورة المحفوظ أولاً، وإلا ولّد رقم جديد
            invoice_number = str(getattr(project, "invoice_number", None) or "").strip()
            if not invoice_number:
                repo = getattr(self.project_service, "repo", None)
                if repo is not None and hasattr(repo, "ensure_invoice_number"):
                    try:
                        invoice_number = str(
                            repo.ensure_invoice_number(
                                self._project_ref(project, project.name),
                                getattr(project, "client_id", None),
                            )
                            or ""
                        ).strip()
                        if invoice_number:
                            project.invoice_number = invoice_number
                    except Exception as invoice_err:
                        safe_print(
                            f"WARNING: [ProjectManager] فشل مزامنة رقم الفاتورة من المستودع: {invoice_err}"
                        )

            if not invoice_number:
                local_id = getattr(project, "id", None) or 1
                invoice_number = f"SW-{97161 + int(local_id)}"

            project_currency = project_currency_code(project)
            project_rate = project_exchange_rate(project)
            currency_suffix_text = currency_suffix(project_currency)
            try:
                repo = getattr(getattr(self, "accounting_service", None), "repo", None)
                if repo is not None and hasattr(repo, "get_all_currencies"):
                    for current_currency in repo.get_all_currencies() or []:
                        if (
                            normalize_currency_code(current_currency.get("code"))
                            == project_currency
                        ):
                            currency_suffix_text = (
                                str(current_currency.get("symbol") or "").strip()
                                or currency_suffix_text
                            )
                            break
            except Exception:
                pass

            invoice_data = {
                "invoice_number": invoice_number,
                "invoice_date": (
                    project.start_date.strftime("%Y-%m-%d")
                    if hasattr(project, "start_date") and project.start_date
                    else datetime.now().strftime("%Y-%m-%d")
                ),
                "due_date": (
                    project.end_date.strftime("%Y-%m-%d")
                    if hasattr(project, "end_date") and project.end_date
                    else datetime.now().strftime("%Y-%m-%d")
                ),
                "client_name": client.name,
                "client_phone": client.phone or "---",
                "client_address": client.address or "---",
                "project_name": project.name,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "project_notes": getattr(project, "project_notes", "") or "",
                "currency_code": project_currency,
                "currency_suffix": currency_suffix_text,
                "items": [
                    {
                        "name": item.description,
                        "qty": float(item.quantity),
                        "price": amount_from_egp(
                            float(item.unit_price), project_currency, project_rate
                        ),
                        "discount": float(item.discount_rate),
                        "total": amount_from_egp(float(item.total), project_currency, project_rate),
                    }
                    for item in project.items
                ],
                "subtotal": amount_from_egp(
                    sum(float(item.total) for item in project.items),
                    project_currency,
                    project_rate,
                ),
                "grand_total": amount_from_egp(
                    float(project.total_amount), project_currency, project_rate
                ),
                "total_paid": amount_from_egp(
                    float(profit_data.get("total_paid", 0)),
                    project_currency,
                    project_rate,
                ),
                "remaining_amount": amount_from_egp(
                    float(profit_data.get("balance_due", 0)),
                    project_currency,
                    project_rate,
                ),
                "remaining": amount_from_egp(
                    float(profit_data.get("balance_due", 0)),
                    project_currency,
                    project_rate,
                ),
                "total_amount": amount_from_egp(
                    float(project.total_amount), project_currency, project_rate
                ),
                "payments": [
                    {
                        **payment,
                        "amount": amount_from_egp(
                            float(payment.get("amount", 0.0) or 0.0),
                            project_currency,
                            project_rate,
                        ),
                    }
                    for payment in payments_list
                ],
                "client_info": client_info,
                "client_logo_path": client_info.get("logo_path", ""),
                "client_logo_data": client_info.get("logo_data", ""),
            }

            if settings_service:
                try:
                    invoice_data["payment_methods"] = (
                        settings_service.get_setting("payment_methods") or []
                    )
                except Exception:
                    invoice_data["payment_methods"] = []

            # Step E: Use InvoicePrintingService to generate and open PDF

            # Initialize printing service
            printing_service = InvoicePrintingService(settings_service=settings_service)

            # Print invoice (generates PDF and opens it automatically)
            pdf_path = printing_service.print_invoice(invoice_data, auto_open=False)

            if pdf_path:
                if pdf_path.endswith(".pdf"):
                    QMessageBox.information(
                        self,
                        "✅ تم حفظ الفاتورة",
                        f"تم حفظ فاتورة PDF بنجاح.\n\n📄 {os.path.basename(pdf_path)}",
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
            QMessageBox.critical(self, "خطأ", f"فشل في حفظ الفاتورة:\n{str(e)}")

            traceback.print_exc()

    def _get_payments_list(self, project: schemas.Project | str) -> list:
        """جلب قائمة الدفعات للمشروع - محسّن للسرعة"""
        payments_list = []
        try:
            project_obj = project if isinstance(project, schemas.Project) else None
            project_ref = (
                self._project_ref(project_obj, str(project))
                if project_obj is not None
                else str(project or "")
            )
            client_id = getattr(project_obj, "client_id", None) if project_obj is not None else None
            payments = self.project_service.get_payments_for_project(
                project_ref, client_id=client_id
            )
            if not payments:
                return []

            # ⚡ تخزين الحسابات مؤقتاً لتجنب الاستعلامات المتكررة
            accounts_cache = {}

            for payment in payments:
                account_name = "Cash"
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
            payments_list = self._get_payments_list(project)
            safe_print(f"INFO: [ProjectManager] الدفعات المرسلة للقالب: {payments_list}")

            # تجهيز معلومات العميل
            client_info = {
                "name": client.name,
                "company_name": getattr(client, "company_name", "") or "",
                "phone": client.phone or "---",
                "email": client.email or "",
                "address": client.address or "---",
                "logo_path": getattr(client, "logo_path", "") or "",
                "logo_data": getattr(client, "logo_data", "") or "",
            }

            # استخدام template_service للمعاينة
            if self.template_service:
                preview_ok = self.template_service.preview_template(
                    project=project, client_info=client_info, payments=payments_list
                )
                if not preview_ok:
                    QMessageBox.warning(self, "خطأ", "تعذر فتح الفاتورة مباشرة")
            else:
                QMessageBox.warning(self, "خطأ", "خدمة القوالب غير متوفرة")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في فتح الفاتورة:\n{str(e)}")

            traceback.print_exc()
