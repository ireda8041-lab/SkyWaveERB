# الملف: ui/expense_manager.py
"""
تاب إدارة المصروفات - يستخدم dialog للإضافة والتعديل
"""


import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.accounting_service import AccountingService
from services.expense_service import ExpenseService
from services.project_service import ProjectService
from ui.expense_editor_dialog import ExpenseEditorDialog
from ui.styles import BUTTON_STYLES, create_centered_item, get_cairo_font

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class ExpenseManagerTab(QWidget):
    """تاب إدارة المصروفات مع جدول و dialog - متجاوب"""

    def __init__(
        self,
        expense_service: ExpenseService,
        accounting_service: AccountingService,
        project_service: ProjectService,
        parent=None,
    ):
        super().__init__(parent)

        self.expense_service = expense_service
        self.accounting_service = accounting_service
        self.project_service = project_service

        self.expenses_list: list[schemas.Expense] = []
        self._expenses_cache: dict[str, list[schemas.Expense]] = {}
        self._expenses_cache_ts: dict[str, float] = {}
        self._expenses_cache_ttl_s = 20.0
        self._current_page = 1
        self._page_size = 100
        self._total_expenses_sum = 0.0

        # 📱 تجاوب: سياسة التمدد الكامل
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setup_ui()

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals

        app_signals.safe_connect(app_signals.expenses_changed, self._on_expenses_changed)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_expenses_data() - يتم استدعاؤها من MainWindow

        # ⚡ تطبيق محاذاة النص لليمين على كل الحقول
        from ui.styles import apply_rtl_alignment_to_all_fields

        apply_rtl_alignment_to_all_fields(self)

    def setup_ui(self):
        """إعداد الواجهة - متجاوب"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

        # === شريط الأزرار المتجاوب ===
        from ui.responsive_toolbar import ResponsiveToolbar

        self.toolbar = ResponsiveToolbar()

        self.add_button = QPushButton("➕ إضافة مصروف")
        self.add_button.setStyleSheet(BUTTON_STYLES["success"])
        self.add_button.setFixedHeight(28)
        self.add_button.clicked.connect(self.open_add_dialog)

        self.edit_button = QPushButton("✏️ تعديل المصروف")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.open_edit_dialog)

        self.delete_button = QPushButton("🗑️ حذف المصروف")
        self.delete_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_button.setFixedHeight(28)
        self.delete_button.clicked.connect(self.delete_selected_expense)

        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.setFixedHeight(28)
        self.refresh_button.clicked.connect(self.load_expenses_data)

        # إضافة الأزرار للـ toolbar المتجاوب
        self.toolbar.addButton(self.add_button)
        self.toolbar.addButton(self.edit_button)
        self.toolbar.addButton(self.delete_button)
        self.toolbar.addButton(self.refresh_button)

        layout.addWidget(self.toolbar)

        # جدول المصروفات
        self.expenses_table = QTableWidget()
        self.expenses_table.setColumnCount(6)
        self.expenses_table.setHorizontalHeaderLabels(
            ["#", "التاريخ", "الفئة", "الوصف", "المشروع", "المبلغ"]
        )

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar

        self.search_bar = UniversalSearchBar(
            self.expenses_table, placeholder="🔍 بحث (التاريخ، الفئة، الوصف، المشروع، المبلغ)..."
        )
        layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===

        h_header = self.expenses_table.horizontalHeader()
        v_header = self.expenses_table.verticalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # #
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # التاريخ
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # الفئة
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # الوصف - يتمدد
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # المشروع - يتمدد
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # المبلغ
        self.expenses_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.expenses_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.expenses_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.expenses_table.setAlternatingRowColors(True)
        if v_header is not None:
            v_header.setDefaultSectionSize(45)  # ⚡ ارتفاع الصفوف
            v_header.setVisible(False)
        self.expenses_table.itemDoubleClicked.connect(self.open_edit_dialog)
        from ui.styles import TABLE_STYLE_DARK, fix_table_rtl

        self.expenses_table.setStyleSheet(TABLE_STYLE_DARK)
        fix_table_rtl(self.expenses_table)

        # إضافة قائمة السياق (كليك يمين)
        self._setup_context_menu()

        layout.addWidget(self.expenses_table)

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
        layout.addLayout(pagination_layout)

        # إجمالي المصروفات
        self.total_label = QLabel("إجمالي المصروفات: 0.00 ج.م")
        self.total_label.setFont(get_cairo_font(14, bold=True))
        self.total_label.setStyleSheet("color: #ef4444; padding: 10px;")
        layout.addWidget(self.total_label, 0, Qt.AlignmentFlag.AlignRight)

    def _setup_context_menu(self):
        """إعداد قائمة السياق (كليك يمين) للجدول"""
        from core.context_menu import ContextMenuManager

        ContextMenuManager.setup_table_context_menu(
            table=self.expenses_table,
            on_view=self.open_edit_dialog,
            on_edit=self.open_edit_dialog,
            on_delete=self.delete_selected_expense,
            on_refresh=self.load_expenses_data,
        )

    def load_expenses_data(self, force_refresh: bool = False):
        """⚡ تحميل المصروفات في الخلفية لمنع التجميد"""
        safe_print("INFO: [ExpenseManager] جاري تحميل المصروفات...")

        from core.data_loader import get_data_loader

        # تحضير الجدول
        sorting_enabled = self.expenses_table.isSortingEnabled()
        if sorting_enabled:
            self.expenses_table.setSortingEnabled(False)
        self.expenses_table.setUpdatesEnabled(False)
        self.expenses_table.blockSignals(True)
        self.expenses_table.setRowCount(0)

        # دالة جلب البيانات
        def fetch_expenses():
            try:
                return self.expense_service.get_all_expenses()
            except Exception as e:
                safe_print(f"ERROR: [ExpenseManager] فشل جلب المصروفات: {e}")
                return []

        # دالة تحديث الواجهة
        def on_data_loaded(expenses):
            try:
                self.expenses_list = expenses
                self._total_expenses_sum = sum(exp.amount for exp in self.expenses_list)
                self.total_label.setText(f"إجمالي المصروفات: {self._total_expenses_sum:,.2f} ج.م")
                self._render_current_page()
                safe_print(f"INFO: [ExpenseManager] ✅ تم تحميل {len(self.expenses_list)} مصروف.")
                self._set_cached_expenses(expenses)

            except Exception as e:
                safe_print(f"ERROR: [ExpenseManager] فشل تحديث الجدول: {e}")
            finally:
                self.expenses_table.blockSignals(False)
                self.expenses_table.setUpdatesEnabled(True)
                if sorting_enabled:
                    self.expenses_table.setSortingEnabled(True)

        def on_error(error_msg):
            safe_print(f"ERROR: [ExpenseManager] فشل تحميل المصروفات: {error_msg}")
            self.expenses_table.blockSignals(False)
            self.expenses_table.setUpdatesEnabled(True)
            if sorting_enabled:
                self.expenses_table.setSortingEnabled(True)

        if force_refresh:
            self._expenses_cache.clear()
            self._expenses_cache_ts.clear()
            if hasattr(self.expense_service, "invalidate_cache"):
                self.expense_service.invalidate_cache()

        cached = self._get_cached_expenses()
        if cached is not None and not force_refresh:
            on_data_loaded(cached)
            return

        # تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="expenses_list",
            load_function=fetch_expenses,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _get_total_pages(self) -> int:
        total = len(self.expenses_list)
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
            page_items = self.expenses_list
            start_index = 0
        else:
            start_index = (self._current_page - 1) * self._page_size
            end_index = start_index + self._page_size
            page_items = self.expenses_list[start_index:end_index]

        self._populate_expenses_table(page_items, start_index)
        self._update_pagination_controls(total_pages)

    def _populate_expenses_table(self, expenses: list[schemas.Expense], start_index: int):
        self.expenses_table.setRowCount(len(expenses))
        for i, exp in enumerate(expenses):
            row_number = start_index + i + 1
            num_item = create_centered_item(str(row_number))
            num_item.setData(Qt.ItemDataRole.UserRole, exp)
            self.expenses_table.setItem(i, 0, num_item)

            date_str = exp.date.strftime("%Y-%m-%d") if exp.date else ""
            self.expenses_table.setItem(i, 1, create_centered_item(date_str))
            self.expenses_table.setItem(i, 2, create_centered_item(exp.category or ""))
            self.expenses_table.setItem(i, 3, create_centered_item(exp.description or ""))
            self.expenses_table.setItem(i, 4, create_centered_item(exp.project_id or "---"))

            amount_item = create_centered_item(f"{exp.amount:,.2f}")
            amount_item.setForeground(QColor("#ef4444"))
            self.expenses_table.setItem(i, 5, amount_item)

    def _update_pagination_controls(self, total_pages: int):
        self.page_info_label.setText(f"صفحة {self._current_page} / {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

    def _on_page_size_changed(self, value: str):
        if value == "كل":
            self._page_size = max(1, len(self.expenses_list))
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

    def _get_cached_expenses(self) -> list[schemas.Expense] | None:
        ts = self._expenses_cache_ts.get("all")
        if ts is None:
            return None
        if (time.monotonic() - ts) > self._expenses_cache_ttl_s:
            self._expenses_cache.pop("all", None)
            self._expenses_cache_ts.pop("all", None)
            return None
        return self._expenses_cache.get("all")

    def _set_cached_expenses(self, expenses: list[schemas.Expense]) -> None:
        self._expenses_cache["all"] = expenses
        self._expenses_cache_ts["all"] = time.monotonic()

    def _on_expenses_changed(self):
        """⚡ استجابة لإشارة تحديث المصروفات - تحديث الجدول أوتوماتيك"""
        if not self.isVisible():
            return
        self.load_expenses_data(force_refresh=True)

    def get_selected_expense(self) -> schemas.Expense | None:
        """الحصول على المصروف المحدد"""
        current_row = self.expenses_table.currentRow()
        if current_row < 0:
            return None
        num_item = self.expenses_table.item(current_row, 0)
        if not num_item:
            return None
        data = num_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, schemas.Expense):
            return data
        return None

    def open_add_dialog(self):
        """فتح dialog إضافة مصروف جديد"""
        dialog = ExpenseEditorDialog(
            expense_service=self.expense_service,
            accounting_service=self.accounting_service,
            project_service=self.project_service,
            expense_to_edit=None,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_expenses_data(force_refresh=True)

    def open_edit_dialog(self):
        """فتح dialog تعديل المصروف"""
        selected_expense = self.get_selected_expense()
        if not selected_expense:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مصروف أولاً.")
            return

        dialog = ExpenseEditorDialog(
            expense_service=self.expense_service,
            accounting_service=self.accounting_service,
            project_service=self.project_service,
            expense_to_edit=selected_expense,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_expenses_data(force_refresh=True)

    def delete_selected_expense(self):
        """حذف المصروف المحدد"""
        selected_expense = self.get_selected_expense()
        if not selected_expense:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مصروف أولاً.")
            return

        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف المصروف:\n{selected_expense.description or selected_expense.category}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            expense_id = selected_expense.id or selected_expense._mongo_id
            result = self.expense_service.delete_expense(expense_id)
            if result:
                QMessageBox.information(self, "تم", "تم حذف المصروف بنجاح.")
                self.load_expenses_data(force_refresh=True)
            else:
                QMessageBox.warning(self, "خطأ", "فشل حذف المصروف.")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل حذف المصروف: {e}")
