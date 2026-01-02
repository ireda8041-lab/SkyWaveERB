# الملف: ui/expense_manager.py
"""
تاب إدارة المصروفات - يستخدم dialog للإضافة والتعديل
"""


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.accounting_service import AccountingService
from services.expense_service import ExpenseService
from services.project_service import ProjectService
from ui.expense_editor_dialog import ExpenseEditorDialog
from ui.styles import BUTTON_STYLES, get_cairo_font, create_centered_item

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

        # 📱 تجاوب: سياسة التمدد الكامل
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setup_ui()

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals
        app_signals.expenses_changed.connect(self._on_expenses_changed)

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

        self.edit_button = QPushButton("✏️ تعديل")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.open_edit_dialog)

        self.delete_button = QPushButton("🗑️ حذف")
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
        self.expenses_table.setHorizontalHeaderLabels([
            "#", "التاريخ", "الفئة", "الوصف", "المشروع", "المبلغ"
        ])

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar
        self.search_bar = UniversalSearchBar(
            self.expenses_table,
            placeholder="🔍 بحث (التاريخ، الفئة، الوصف، المشروع، المبلغ)..."
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
            on_refresh=self.load_expenses_data
        )

    def load_expenses_data(self):
        """⚡ تحميل المصروفات في الخلفية لمنع التجميد"""
        safe_print("INFO: [ExpenseManager] جاري تحميل المصروفات...")

        from PyQt6.QtWidgets import QApplication

        from core.data_loader import get_data_loader

        # تحضير الجدول
        self.expenses_table.setUpdatesEnabled(False)
        self.expenses_table.blockSignals(True)
        self.expenses_table.setRowCount(0)
        QApplication.processEvents()

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
                total_sum = 0.0
                batch_size = 15

                for i, exp in enumerate(self.expenses_list):
                    self.expenses_table.insertRow(i)

                    num_item = create_centered_item(str(i + 1))
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

                    total_sum += exp.amount

                    if (i + 1) % batch_size == 0:
                        QApplication.processEvents()

                self.total_label.setText(f"إجمالي المصروفات: {total_sum:,.2f} ج.م")
                safe_print(f"INFO: [ExpenseManager] ✅ تم تحميل {len(self.expenses_list)} مصروف.")

            except Exception as e:
                safe_print(f"ERROR: [ExpenseManager] فشل تحديث الجدول: {e}")
            finally:
                self.expenses_table.blockSignals(False)
                self.expenses_table.setUpdatesEnabled(True)
                QApplication.processEvents()

        def on_error(error_msg):
            safe_print(f"ERROR: [ExpenseManager] فشل تحميل المصروفات: {error_msg}")
            self.expenses_table.blockSignals(False)
            self.expenses_table.setUpdatesEnabled(True)

        # تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="expenses_list",
            load_function=fetch_expenses,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True
        )

    def _on_expenses_changed(self):
        """⚡ استجابة لإشارة تحديث المصروفات - تحديث الجدول أوتوماتيك"""
        safe_print("INFO: [ExpenseManager] ⚡ استلام إشارة تحديث المصروفات - جاري التحديث...")
        self.load_expenses_data()

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
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_expenses_data()

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
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_expenses_data()

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
                self.load_expenses_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل حذف المصروف.")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل حذف المصروف: {e}")
