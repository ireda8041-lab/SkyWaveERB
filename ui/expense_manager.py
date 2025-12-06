# الملف: ui/expense_manager.py
"""
تاب إدارة المصروفات - يستخدم dialog للإضافة والتعديل
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox, QGroupBox, QDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from services.expense_service import ExpenseService
from services.accounting_service import AccountingService
from services.project_service import ProjectService
from core import schemas
from typing import List, Optional

from ui.styles import BUTTON_STYLES
from ui.expense_editor_dialog import ExpenseEditorDialog


class ExpenseManagerTab(QWidget):
    """تاب إدارة المصروفات مع جدول و dialog"""

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

        self.expenses_list: List[schemas.Expense] = []

        self.setup_ui()
        
        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals
        app_signals.expenses_changed.connect(self._on_expenses_changed)
        
        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_expenses_data() - يتم استدعاؤها من MainWindow

    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # أزرار التحكم
        buttons_layout = QHBoxLayout()
        
        self.add_button = QPushButton("➕ إضافة مصروف")
        self.add_button.setStyleSheet(BUTTON_STYLES["success"])
        self.add_button.clicked.connect(self.open_add_dialog)

        self.edit_button = QPushButton("✏️ تعديل")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.clicked.connect(self.open_edit_dialog)

        self.delete_button = QPushButton("🗑️ حذف")
        self.delete_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_button.clicked.connect(self.delete_selected_expense)

        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.clicked.connect(self.load_expenses_data)

        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.edit_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

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
        
        self.expenses_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.expenses_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.expenses_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.expenses_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.expenses_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.expenses_table.setAlternatingRowColors(True)
        self.expenses_table.verticalHeader().setDefaultSectionSize(45)  # ⚡ ارتفاع الصفوف
        self.expenses_table.verticalHeader().setVisible(False)
        self.expenses_table.itemDoubleClicked.connect(self.open_edit_dialog)
        from ui.styles import TABLE_STYLE_DARK
        self.expenses_table.setStyleSheet(TABLE_STYLE_DARK)
        layout.addWidget(self.expenses_table)

        # إجمالي المصروفات
        self.total_label = QLabel("إجمالي المصروفات: 0.00 ج.م")
        self.total_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.total_label.setStyleSheet("color: #ef4444; padding: 10px;")
        layout.addWidget(self.total_label, 0, Qt.AlignmentFlag.AlignRight)

    def load_expenses_data(self):
        """⚡ تحميل المصروفات بسرعة - مع منع التجميد"""
        print("INFO: [ExpenseManager] جاري تحميل المصروفات...")
        
        try:
            # ⚡ معالجة الأحداث لمنع التجميد
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
            
            # ⚡ تعطيل التحديثات للسرعة
            self.expenses_table.setUpdatesEnabled(False)
            self.expenses_table.blockSignals(True)  # ⚡ منع الإشارات
            
            self.expenses_list = self.expense_service.get_all_expenses()
            QApplication.processEvents()  # ⚡ منع التجميد بعد جلب البيانات
            
            self.expenses_table.setRowCount(0)

            total_sum = 0.0
            batch_size = 20  # ⚡ تحميل على دفعات
            for i, exp in enumerate(self.expenses_list):
                self.expenses_table.insertRow(i)
                
                # الرقم
                num_item = QTableWidgetItem(str(i + 1))
                num_item.setData(Qt.ItemDataRole.UserRole, exp)
                self.expenses_table.setItem(i, 0, num_item)
                
                # التاريخ
                date_str = exp.date.strftime("%Y-%m-%d") if exp.date else ""
                self.expenses_table.setItem(i, 1, QTableWidgetItem(date_str))
                
                # الفئة
                self.expenses_table.setItem(i, 2, QTableWidgetItem(exp.category or ""))
                
                # الوصف
                self.expenses_table.setItem(i, 3, QTableWidgetItem(exp.description or ""))
                
                # المشروع
                self.expenses_table.setItem(i, 4, QTableWidgetItem(exp.project_id or "---"))
                
                # المبلغ
                amount_item = QTableWidgetItem(f"{exp.amount:,.2f}")
                amount_item.setForeground(QColor("#ef4444"))
                self.expenses_table.setItem(i, 5, amount_item)
                
                total_sum += exp.amount
                
                # ⚡ معالجة الأحداث كل batch_size صف
                if (i + 1) % batch_size == 0:
                    QApplication.processEvents()

            self.total_label.setText(f"إجمالي المصروفات: {total_sum:,.2f} ج.م")
            print(f"INFO: [ExpenseManager] تم جلب {len(self.expenses_list)} مصروف.")
            
            # ⚡ إعادة تفعيل كل شيء
            self.expenses_table.blockSignals(False)
            self.expenses_table.setUpdatesEnabled(True)
            QApplication.processEvents()

        except Exception as e:
            print(f"ERROR: [ExpenseManager] فشل تحميل المصروفات: {e}")
            import traceback
            traceback.print_exc()
            self.expenses_table.blockSignals(False)
            self.expenses_table.setUpdatesEnabled(True)

    def _on_expenses_changed(self):
        """⚡ استجابة لإشارة تحديث المصروفات - تحديث الجدول أوتوماتيك"""
        print("INFO: [ExpenseManager] ⚡ استلام إشارة تحديث المصروفات - جاري التحديث...")
        self.load_expenses_data()

    def get_selected_expense(self) -> Optional[schemas.Expense]:
        """الحصول على المصروف المحدد"""
        current_row = self.expenses_table.currentRow()
        if current_row < 0:
            return None
        num_item = self.expenses_table.item(current_row, 0)
        if not num_item:
            return None
        return num_item.data(Qt.ItemDataRole.UserRole)

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
