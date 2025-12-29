# الملف: ui/unified_hr_manager.py
"""
🏢 نظام الموارد البشرية الموحد - Production Grade
=================================================
تاب واحد شامل يجمع:
- إدارة الموظفين (إضافة، تعديل، حذف)
- السلف والقروض (مع ربط محاسبي)
- المرتبات والحوافز (مع ربط محاسبي)
- الحضور والإجازات
- التقارير الشاملة
"""

from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox,
    QTextEdit, QDialog, QFormLayout, QMessageBox, QHeaderView,
    QGroupBox, QGridLayout, QLineEdit, QTimeEdit
)

from ui.styles import BUTTON_STYLES, get_cairo_font, TABLE_STYLE_DARK, create_centered_item
from services.hr_service import HRService


class UnifiedHRManager(QWidget):
    """نظام الموارد البشرية الموحد - كل شيء في مكان واحد"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hr_service = HRService()
        self.employees = []
        self.current_employee = None
        
        # 📱 تصميم متجاوب
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.init_ui()
        self.load_employees()
    
    def init_ui(self):
        """إنشاء واجهة المستخدم الموحدة"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)
        
        # عنوان النظام
        title = QLabel("🏢 نظام الموارد البشرية الشامل")
        title.setFont(get_cairo_font(16, bold=True))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #4a90e2; padding: 10px; font-size: 18px;")
        layout.addWidget(title)
        
        # التابات الرئيسية
        self.tabs = QTabWidget()
        
        # ⚡ جعل التابات تتمدد لتملأ العرض تلقائياً
        self.tabs.tabBar().setExpanding(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)  # عدم اقتطاع النص
        
        layout.addWidget(self.tabs)
        
        # تاب إدارة الموظفين
        self.employees_tab = self._create_employees_tab()
        self.tabs.addTab(self.employees_tab, "👥 إدارة الموظفين")
        
        # تاب السلف والقروض
        self.loans_tab = self._create_loans_tab()
        self.tabs.addTab(self.loans_tab, "💰 السلف والقروض")
        
        # تاب المرتبات
        self.salaries_tab = self._create_salaries_tab()
        self.tabs.addTab(self.salaries_tab, "💵 المرتبات")
        
        # تاب الحضور والإجازات
        self.attendance_tab = self._create_attendance_tab()
        self.tabs.addTab(self.attendance_tab, "⏰ الحضور والإجازات")
        
        # تاب التقارير
        self.reports_tab = self._create_reports_tab()
        self.tabs.addTab(self.reports_tab, "📊 التقارير")
    
    def _get_table_style(self):
        """ستايل موحد للجداول"""
        return TABLE_STYLE_DARK
    
    # ==================== تاب الموظفين ====================
    
    def _create_employees_tab(self):
        """إنشاء تاب إدارة الموظفين"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # أزرار التحكم
        buttons = QHBoxLayout()
        
        self.add_emp_btn = QPushButton("➕ إضافة موظف")
        self.add_emp_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.add_emp_btn.setFixedHeight(28)
        self.add_emp_btn.clicked.connect(self.add_employee)
        
        self.edit_emp_btn = QPushButton("✏️ تعديل")
        self.edit_emp_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_emp_btn.setFixedHeight(28)
        self.edit_emp_btn.clicked.connect(self.edit_employee)
        
        self.delete_emp_btn = QPushButton("🗑️ حذف")
        self.delete_emp_btn.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_emp_btn.setFixedHeight(28)
        self.delete_emp_btn.clicked.connect(self.delete_employee)
        
        self.refresh_emp_btn = QPushButton("🔄 تحديث")
        self.refresh_emp_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_emp_btn.setFixedHeight(28)
        self.refresh_emp_btn.clicked.connect(self.load_employees)
        
        buttons.addWidget(self.add_emp_btn)
        buttons.addWidget(self.edit_emp_btn)
        buttons.addWidget(self.delete_emp_btn)
        buttons.addWidget(self.refresh_emp_btn)
        buttons.addStretch()
        layout.addLayout(buttons)
        
        # جدول الموظفين
        self.employees_table = QTableWidget()
        self.employees_table.setColumnCount(10)
        self.employees_table.setHorizontalHeaderLabels([
            "ID", "رقم الموظف", "الاسم", "الوظيفة", "القسم",
            "الراتب", "الهاتف", "البريد", "تاريخ التوظيف", "الحالة"
        ])
        # تخصيص عرض الأعمدة: النصية تتمدد، الصغيرة بحجم محتواها
        header = self.employees_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # رقم الموظف
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # الاسم - يتمدد
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # الوظيفة - يتمدد
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # القسم
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # الراتب
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # الهاتف
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # البريد - يتمدد
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # تاريخ التوظيف
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
        self.employees_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.employees_table.setAlternatingRowColors(True)
        self.employees_table.itemSelectionChanged.connect(self._on_employee_selected)
        self.employees_table.setStyleSheet(self._get_table_style())
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.employees_table)
        
        # ⚡ إضافة قائمة السياق (كليك يمين)
        from core.context_menu import ContextMenuManager
        ContextMenuManager.setup_table_context_menu(
            table=self.employees_table,
            on_view=self.edit_employee,
            on_edit=self.edit_employee,
            on_refresh=self.load_employees
        )
        
        layout.addWidget(self.employees_table)
        
        # معلومات الموظف المحدد
        self.emp_info_label = QLabel("اختر موظفاً لعرض معلوماته")
        self.emp_info_label.setStyleSheet("background-color: #1e3a8a; color: white; padding: 10px; border-radius: 6px; font-weight: bold;")
        layout.addWidget(self.emp_info_label)
        
        return widget
    
    def load_employees(self):
        """تحميل قائمة الموظفين"""
        try:
            self.employees = self.hr_service.get_all_employees()
            self._update_employees_table()
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في تحميل الموظفين:\n{e}")
    
    def _update_employees_table(self):
        """تحديث جدول الموظفين"""
        self.employees_table.setRowCount(len(self.employees))
        
        for row, emp in enumerate(self.employees):
            self.employees_table.setItem(row, 0, create_centered_item(emp.get('id', '')))
            self.employees_table.setItem(row, 1, create_centered_item(emp.get('employee_id', '')))
            self.employees_table.setItem(row, 2, create_centered_item(emp.get('name', '')))
            self.employees_table.setItem(row, 3, create_centered_item(emp.get('position', '')))
            self.employees_table.setItem(row, 4, create_centered_item(emp.get('department', '')))
            self.employees_table.setItem(row, 5, create_centered_item(f"{emp.get('salary', 0):.2f}"))
            self.employees_table.setItem(row, 6, create_centered_item(emp.get('phone', '')))
            self.employees_table.setItem(row, 7, create_centered_item(emp.get('email', '')))
            self.employees_table.setItem(row, 8, create_centered_item(emp.get('hire_date', '')))
            
            # الحالة مع لون الخلفية
            status = emp.get('status', '')
            bg_color = None
            if status == 'نشط':
                bg_color = Qt.GlobalColor.darkGreen
            elif status == 'غير نشط':
                bg_color = Qt.GlobalColor.darkRed
            self.employees_table.setItem(row, 9, create_centered_item(status, bg_color))
    
    def _on_employee_selected(self):
        """عند اختيار موظف"""
        # ⚡ تجاهل التحديث إذا كان الكليك يمين
        from core.context_menu import is_right_click_active
        if is_right_click_active():
            return
        
        row = self.employees_table.currentRow()
        if 0 <= row < len(self.employees):
            self.current_employee = self.employees[row]
            info = f"الموظف: {self.current_employee['name']} ({self.current_employee.get('employee_id', '')}) - {self.current_employee.get('position', '')} - راتب: {self.current_employee.get('salary', 0):.2f} ج.م"
            self.emp_info_label.setText(info)
            self.loans_emp_info.setText(info)
            self._load_employee_loans()
    
    def add_employee(self):
        """إضافة موظف جديد"""
        from ui.smart_employee_dialog import SmartEmployeeDialog
        dialog = SmartEmployeeDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_employee_data()
            success, msg = self.hr_service.save_employee(data)
            if success:
                self.load_employees()
                QMessageBox.information(self, "✅ نجح", msg)
            else:
                QMessageBox.critical(self, "❌ خطأ", msg)
    
    def edit_employee(self):
        """تعديل موظف"""
        if not self.current_employee:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار موظف أولاً")
            return
        
        from ui.smart_employee_dialog import SmartEmployeeDialog
        dialog = SmartEmployeeDialog(employee_data=self.current_employee, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_employee_data()
            data['id'] = self.current_employee['id']
            success, msg = self.hr_service.save_employee(data)
            if success:
                self.load_employees()
                QMessageBox.information(self, "✅ نجح", msg)
            else:
                QMessageBox.critical(self, "❌ خطأ", msg)
    
    def delete_employee(self):
        """حذف موظف"""
        if not self.current_employee:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار موظف أولاً")
            return
        
        reply = QMessageBox.question(
            self, "⚠️ تأكيد الحذف",
            f"هل أنت متأكد من حذف الموظف '{self.current_employee['name']}'؟\n\n"
            "⚠️ سيتم حذف جميع البيانات المرتبطة به",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success, msg = self.hr_service.delete_employee(self.current_employee['id'])
            if success:
                self.load_employees()
                self.current_employee = None
                self.emp_info_label.setText("اختر موظفاً لعرض معلوماته")
                QMessageBox.information(self, "✅ نجح", msg)
            else:
                QMessageBox.critical(self, "❌ خطأ", msg)

    # ==================== تاب السلف ====================
    
    def _create_loans_tab(self):
        """إنشاء تاب السلف والقروض"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # معلومات الموظف
        self.loans_emp_info = QLabel("اختر موظفاً من تاب الموظفين لعرض سلفه")
        self.loans_emp_info.setStyleSheet("font-weight: bold; color: #4a90e2; padding: 10px; background-color: #002040; border-radius: 6px;")
        layout.addWidget(self.loans_emp_info)
        
        # أزرار السلف
        buttons = QHBoxLayout()
        
        self.add_loan_btn = QPushButton("💰 إضافة سلفة")
        self.add_loan_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.add_loan_btn.setFixedHeight(28)
        self.add_loan_btn.clicked.connect(self.add_loan)
        
        self.pay_loan_btn = QPushButton("💳 دفع قسط")
        self.pay_loan_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.pay_loan_btn.setFixedHeight(28)
        self.pay_loan_btn.clicked.connect(self.pay_loan_installment)
        
        self.view_loan_btn = QPushButton("👁️ تفاصيل السلفة")
        self.view_loan_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.view_loan_btn.setFixedHeight(28)
        self.view_loan_btn.clicked.connect(self.view_loan_details)
        
        self.close_loan_btn = QPushButton("✅ إغلاق سلفة")
        self.close_loan_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.close_loan_btn.setFixedHeight(28)
        self.close_loan_btn.clicked.connect(self.close_loan)
        
        self.all_loans_btn = QPushButton("📋 جميع السلف")
        self.all_loans_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.all_loans_btn.setFixedHeight(28)
        self.all_loans_btn.clicked.connect(self._load_all_loans)
        
        buttons.addWidget(self.add_loan_btn)
        buttons.addWidget(self.pay_loan_btn)
        buttons.addWidget(self.view_loan_btn)
        buttons.addWidget(self.close_loan_btn)
        buttons.addWidget(self.all_loans_btn)
        buttons.addStretch()
        layout.addLayout(buttons)
        
        # جدول السلف
        self.loans_table = QTableWidget()
        self.loans_table.setColumnCount(10)
        self.loans_table.setHorizontalHeaderLabels([
            "ID", "الموظف", "نوع السلفة", "المبلغ الأصلي", "المبلغ المتبقي",
            "القسط الشهري", "الأقساط المدفوعة", "تاريخ البداية", "الحالة", "السبب"
        ])
        header = self.loans_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # الموظف - يتمدد
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # نوع السلفة
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # المبلغ الأصلي
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # المبلغ المتبقي
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # القسط الشهري
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # الأقساط المدفوعة
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # تاريخ البداية
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)  # السبب - يتمدد
        self.loans_table.setAlternatingRowColors(True)
        self.loans_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.loans_table.doubleClicked.connect(self.view_loan_details)
        self.loans_table.setStyleSheet(self._get_table_style())
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.loans_table)
        layout.addWidget(self.loans_table)
        
        # ملخص السلف
        self.loans_summary_label = QLabel("")
        self.loans_summary_label.setStyleSheet("background-color: #1e3a8a; color: white; padding: 10px; border-radius: 6px;")
        layout.addWidget(self.loans_summary_label)
        
        return widget
    
    def view_loan_details(self):
        """عرض تفاصيل السلفة وأقساطها"""
        row = self.loans_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار سلفة")
            return
        
        loan_id = int(self.loans_table.item(row, 0).text())
        dialog = LoanDetailsDialog(loan_id, self.hr_service, parent=self)
        dialog.exec()
    
    def _load_employee_loans(self):
        """تحميل سلف الموظف المحدد"""
        if not self.current_employee:
            return
        
        loans = self.hr_service.get_employee_loans(self.current_employee['id'])
        self._update_loans_table(loans)
    
    def _load_all_loans(self):
        """تحميل جميع السلف"""
        loans = self.hr_service.get_all_active_loans()
        self._update_loans_table(loans)
    
    def _update_loans_table(self, loans):
        """تحديث جدول السلف"""
        self.loans_table.setRowCount(len(loans))
        
        total_amount = 0
        total_remaining = 0
        active_count = 0
        
        for row, loan in enumerate(loans):
            self.loans_table.setItem(row, 0, create_centered_item(loan.get('id', '')))
            self.loans_table.setItem(row, 1, create_centered_item(loan.get('employee_name', '')))
            self.loans_table.setItem(row, 2, create_centered_item(loan.get('loan_type', '')))
            self.loans_table.setItem(row, 3, create_centered_item(f"{loan.get('amount', 0):.2f}"))
            self.loans_table.setItem(row, 4, create_centered_item(f"{loan.get('remaining_amount', 0):.2f}"))
            self.loans_table.setItem(row, 5, create_centered_item(f"{loan.get('monthly_deduction', 0):.2f}"))
            
            # حساب عدد الأقساط المدفوعة
            amount = loan.get('amount', 0) or 0
            remaining = loan.get('remaining_amount', 0) or 0
            monthly = loan.get('monthly_deduction', 0) or 1
            paid_installments = int((amount - remaining) / monthly) if monthly > 0 else 0
            total_installments = int(amount / monthly) if monthly > 0 else 0
            self.loans_table.setItem(row, 6, create_centered_item(f"{paid_installments}/{total_installments}"))
            
            self.loans_table.setItem(row, 7, create_centered_item(loan.get('start_date', '')))
            
            # الحالة مع لون الخلفية
            status = loan.get('status', '')
            bg_color = None
            if status == 'نشط':
                bg_color = Qt.GlobalColor.darkGreen
                active_count += 1
                total_remaining += remaining
            elif status == 'مكتمل':
                bg_color = Qt.GlobalColor.darkBlue
            elif status == 'ملغي':
                bg_color = Qt.GlobalColor.darkGray
            self.loans_table.setItem(row, 8, create_centered_item(status, bg_color))
            
            self.loans_table.setItem(row, 9, create_centered_item(loan.get('reason', '')))
            
            total_amount += amount
        
        # تحديث ملخص السلف
        self.loans_summary_label.setText(
            f"📊 إجمالي السلف: {len(loans)} | النشطة: {active_count} | "
            f"إجمالي المبالغ: {total_amount:,.2f} ج.م | المتبقي: {total_remaining:,.2f} ج.م"
        )
    
    def add_loan(self):
        """إضافة سلفة جديدة"""
        if not self.current_employee:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار موظف أولاً")
            return
        
        dialog = LoanDialog(self.current_employee, self.hr_service, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_employee_loans()
    
    def pay_loan_installment(self):
        """دفع قسط من السلفة"""
        row = self.loans_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار سلفة")
            return
        
        loan_id = int(self.loans_table.item(row, 0).text())
        remaining = float(self.loans_table.item(row, 4).text())
        monthly = float(self.loans_table.item(row, 5).text())
        
        dialog = PayLoanDialog(loan_id, remaining, monthly, self.hr_service, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_employee_loans()
    
    def close_loan(self):
        """إغلاق سلفة"""
        row = self.loans_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار سلفة")
            return
        
        loan_id = int(self.loans_table.item(row, 0).text())
        
        reply = QMessageBox.question(
            self, "تأكيد",
            "هل أنت متأكد من إغلاق هذه السلفة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success, msg = self.hr_service.close_loan(loan_id)
            if success:
                self._load_employee_loans()
                QMessageBox.information(self, "✅ نجح", msg)
            else:
                QMessageBox.critical(self, "❌ خطأ", msg)
    
    # ==================== تاب المرتبات ====================
    
    def _create_salaries_tab(self):
        """إنشاء تاب المرتبات"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # شريط التحكم
        control = QHBoxLayout()
        
        control.addWidget(QLabel("الشهر:"))
        self.month_combo = QComboBox()
        months = [(datetime.now().replace(day=1) - timedelta(days=30*i)).strftime('%Y-%m') for i in range(12)]
        self.month_combo.addItems(months)
        self.month_combo.currentTextChanged.connect(self._load_salaries)
        control.addWidget(self.month_combo)
        
        self.calc_salaries_btn = QPushButton("🧮 حساب المرتبات")
        self.calc_salaries_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.calc_salaries_btn.setFixedHeight(28)
        self.calc_salaries_btn.clicked.connect(self.calculate_salaries)
        
        self.edit_salary_btn = QPushButton("✏️ تعديل راتب")
        self.edit_salary_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_salary_btn.setFixedHeight(28)
        self.edit_salary_btn.clicked.connect(self.edit_salary)
        
        self.pay_salary_btn = QPushButton("💳 دفع راتب")
        self.pay_salary_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.pay_salary_btn.setFixedHeight(28)
        self.pay_salary_btn.clicked.connect(self.pay_single_salary)
        
        self.pay_all_btn = QPushButton("💰 دفع الكل")
        self.pay_all_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.pay_all_btn.setFixedHeight(28)
        self.pay_all_btn.clicked.connect(self.pay_all_salaries)
        
        self.salary_report_btn = QPushButton("📊 تقرير")
        self.salary_report_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.salary_report_btn.setFixedHeight(28)
        self.salary_report_btn.clicked.connect(self.show_salary_report)
        
        control.addWidget(self.calc_salaries_btn)
        control.addWidget(self.edit_salary_btn)
        control.addWidget(self.pay_salary_btn)
        control.addWidget(self.pay_all_btn)
        control.addWidget(self.salary_report_btn)
        control.addStretch()
        layout.addLayout(control)
        
        # جدول المرتبات
        self.salaries_table = QTableWidget()
        self.salaries_table.setColumnCount(12)
        self.salaries_table.setHorizontalHeaderLabels([
            "ID", "الموظف", "الراتب الأساسي", "البدلات", "الحوافز", "الإضافي",
            "خصم السلف", "خصم التأمين", "خصم الضرائب", "إجمالي الخصومات", "الصافي", "الحالة"
        ])
        header = self.salaries_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # الموظف - يتمدد
        for i in range(2, 12):  # باقي الأعمدة الرقمية
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.salaries_table.setAlternatingRowColors(True)
        self.salaries_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.salaries_table.doubleClicked.connect(self.edit_salary)
        self.salaries_table.setStyleSheet(self._get_table_style())
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.salaries_table)
        layout.addWidget(self.salaries_table)
        
        # ملخص المرتبات
        self.salaries_summary_label = QLabel("")
        self.salaries_summary_label.setStyleSheet("background-color: #1e3a8a; color: white; padding: 10px; border-radius: 6px;")
        layout.addWidget(self.salaries_summary_label)
        
        return widget
    
    def edit_salary(self):
        """تعديل راتب موظف"""
        row = self.salaries_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار راتب للتعديل")
            return
        
        employee_id = int(self.salaries_table.item(row, 0).text())
        month = self.month_combo.currentText()
        
        dialog = EditSalaryDialog(employee_id, month, self.hr_service, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_salaries()
    
    def pay_single_salary(self):
        """دفع راتب موظف واحد"""
        row = self.salaries_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار راتب للدفع")
            return
        
        employee_id = int(self.salaries_table.item(row, 0).text())
        employee_name = self.salaries_table.item(row, 1).text()
        status = self.salaries_table.item(row, 11).text()
        
        if status == 'مدفوع':
            QMessageBox.information(self, "معلومات", f"راتب {employee_name} مدفوع بالفعل")
            return
        
        month = self.month_combo.currentText()
        
        reply = QMessageBox.question(
            self, "تأكيد",
            f"هل تريد دفع راتب {employee_name} لشهر {month}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success, msg = self.hr_service.pay_salary(employee_id, month)
            if success:
                self._load_salaries()
                QMessageBox.information(self, "✅ نجح", msg)
            else:
                QMessageBox.critical(self, "❌ خطأ", msg)
    
    def _load_salaries(self):
        """تحميل مرتبات الشهر المحدد"""
        month = self.month_combo.currentText()
        salaries = self.hr_service.get_salaries(month)
        
        self.salaries_table.setRowCount(len(salaries))
        
        total_net = 0
        paid_count = 0
        pending_count = 0
        
        for row, sal in enumerate(salaries):
            self.salaries_table.setItem(row, 0, create_centered_item(sal.get('employee_id', '')))
            self.salaries_table.setItem(row, 1, create_centered_item(sal.get('employee_name', '')))
            self.salaries_table.setItem(row, 2, create_centered_item(f"{sal.get('basic_salary', 0):.2f}"))
            self.salaries_table.setItem(row, 3, create_centered_item(f"{sal.get('allowances', 0):.2f}"))
            self.salaries_table.setItem(row, 4, create_centered_item(f"{sal.get('bonuses', 0):.2f}"))
            self.salaries_table.setItem(row, 5, create_centered_item(f"{sal.get('overtime_amount', 0):.2f}"))
            self.salaries_table.setItem(row, 6, create_centered_item(f"{sal.get('loan_deductions', 0):.2f}"))
            self.salaries_table.setItem(row, 7, create_centered_item(f"{sal.get('insurance_deduction', 0):.2f}"))
            self.salaries_table.setItem(row, 8, create_centered_item(f"{sal.get('tax_deduction', 0):.2f}"))
            
            total_ded = sal.get('loan_deductions', 0) + sal.get('insurance_deduction', 0) + sal.get('tax_deduction', 0) + sal.get('other_deductions', 0)
            self.salaries_table.setItem(row, 9, create_centered_item(f"{total_ded:.2f}"))
            
            net = sal.get('net_salary', 0) or 0
            self.salaries_table.setItem(row, 10, create_centered_item(f"{net:.2f}"))
            total_net += net
            
            # الحالة مع لون الخلفية
            status = sal.get('payment_status', '')
            bg_color = None
            if status == 'مدفوع':
                bg_color = Qt.GlobalColor.darkGreen
                paid_count += 1
            elif status == 'معلق':
                bg_color = Qt.GlobalColor.darkYellow
                pending_count += 1
            self.salaries_table.setItem(row, 11, create_centered_item(status, bg_color))
        
        # تحديث ملخص المرتبات
        self.salaries_summary_label.setText(
            f"📊 إجمالي الموظفين: {len(salaries)} | مدفوع: {paid_count} | معلق: {pending_count} | "
            f"إجمالي الصافي: {total_net:,.2f} ج.م"
        )
    
    def calculate_salaries(self):
        """حساب مرتبات الشهر"""
        month = self.month_combo.currentText()
        success, msg, count = self.hr_service.calculate_all_salaries(month)
        
        if success:
            self._load_salaries()
            QMessageBox.information(self, "✅ نجح", msg)
        else:
            QMessageBox.critical(self, "❌ خطأ", msg)
    
    def pay_all_salaries(self):
        """دفع جميع المرتبات"""
        month = self.month_combo.currentText()
        
        reply = QMessageBox.question(
            self, "تأكيد",
            f"هل أنت متأكد من دفع جميع مرتبات شهر {month}؟\n\n"
            "سيتم إنشاء قيود محاسبية وخصم أقساط السلف تلقائياً",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success, msg, count = self.hr_service.pay_all_salaries(month)
            if success:
                self._load_salaries()
                QMessageBox.information(self, "✅ نجح", msg)
            else:
                QMessageBox.critical(self, "❌ خطأ", msg)
    
    def show_salary_report(self):
        """عرض تقرير المرتبات"""
        month = self.month_combo.currentText()
        summary = self.hr_service.get_payroll_summary(month)
        
        report = f"""
📊 تقرير مرتبات شهر {month}
{'='*40}

📈 الإحصائيات:
• إجمالي الموظفين: {summary['total']}
• المرتبات المدفوعة: {summary['paid']}
• المرتبات المعلقة: {summary['pending']}

💰 المبالغ:
• إجمالي الرواتب الأساسية: {summary['total_basic']:.2f} ج.م
• إجمالي البدلات: {summary['total_allowances']:.2f} ج.م
• إجمالي الحوافز: {summary['total_bonuses']:.2f} ج.م

📉 الخصومات:
• خصم السلف: {summary['total_loan_deductions']:.2f} ج.م
• خصم التأمين: {summary['total_insurance']:.2f} ج.م
• خصم الضرائب: {summary['total_tax']:.2f} ج.م

💵 صافي المرتبات: {summary['total_net']:.2f} ج.م
"""
        
        QMessageBox.information(self, "📊 تقرير المرتبات", report)

    # ==================== تاب الحضور والإجازات ====================
    
    def _create_attendance_tab(self):
        """إنشاء تاب الحضور والإجازات"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # تابات فرعية
        sub_tabs = QTabWidget()
        
        # ⚡ جعل التابات الفرعية تتمدد
        sub_tabs.tabBar().setExpanding(True)
        sub_tabs.setElideMode(Qt.TextElideMode.ElideNone)
        
        # تاب الحضور
        attendance_widget = QWidget()
        att_layout = QVBoxLayout()
        attendance_widget.setLayout(att_layout)
        
        # شريط التاريخ
        date_bar = QHBoxLayout()
        date_bar.addWidget(QLabel("من:"))
        self.att_date_from = QDateEdit()
        self.att_date_from.setDate(QDate.currentDate().addDays(-7))
        self.att_date_from.setCalendarPopup(True)
        date_bar.addWidget(self.att_date_from)
        
        date_bar.addWidget(QLabel("إلى:"))
        self.att_date_to = QDateEdit()
        self.att_date_to.setDate(QDate.currentDate())
        self.att_date_to.setCalendarPopup(True)
        date_bar.addWidget(self.att_date_to)
        
        self.filter_att_btn = QPushButton("🔍 بحث")
        self.filter_att_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.filter_att_btn.setFixedHeight(28)
        self.filter_att_btn.clicked.connect(self._filter_attendance)
        date_bar.addWidget(self.filter_att_btn)
        date_bar.addStretch()
        att_layout.addLayout(date_bar)
        
        # أزرار الحضور
        att_buttons = QHBoxLayout()
        
        self.check_in_btn = QPushButton("✅ تسجيل حضور")
        self.check_in_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.check_in_btn.setFixedHeight(28)
        self.check_in_btn.clicked.connect(self.check_in)
        
        self.check_out_btn = QPushButton("🚪 تسجيل انصراف")
        self.check_out_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.check_out_btn.setFixedHeight(28)
        self.check_out_btn.clicked.connect(self.check_out)
        
        self.manual_att_btn = QPushButton("📝 تسجيل يدوي")
        self.manual_att_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.manual_att_btn.setFixedHeight(28)
        self.manual_att_btn.clicked.connect(self.manual_attendance)
        
        self.today_att_btn = QPushButton("📋 حضور اليوم")
        self.today_att_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.today_att_btn.setFixedHeight(28)
        self.today_att_btn.clicked.connect(self._load_today_attendance)
        
        att_buttons.addWidget(self.check_in_btn)
        att_buttons.addWidget(self.check_out_btn)
        att_buttons.addWidget(self.manual_att_btn)
        att_buttons.addWidget(self.today_att_btn)
        att_buttons.addStretch()
        att_layout.addLayout(att_buttons)
        
        # جدول الحضور
        self.attendance_table = QTableWidget()
        self.attendance_table.setColumnCount(8)
        self.attendance_table.setHorizontalHeaderLabels([
            "التاريخ", "الموظف", "القسم", "وقت الحضور", "وقت الانصراف",
            "ساعات العمل", "الإضافي", "الحالة"
        ])
        header = self.attendance_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # التاريخ
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # الموظف - يتمدد
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # القسم
        for i in range(3, 8):  # باقي الأعمدة
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.attendance_table.setAlternatingRowColors(True)
        self.attendance_table.setStyleSheet(self._get_table_style())
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.attendance_table)
        att_layout.addWidget(self.attendance_table)
        
        sub_tabs.addTab(attendance_widget, "⏰ الحضور")
        
        # تاب الإجازات
        leaves_widget = QWidget()
        leaves_layout = QVBoxLayout()
        leaves_widget.setLayout(leaves_layout)
        
        # أزرار الإجازات
        leaves_buttons = QHBoxLayout()
        
        self.request_leave_btn = QPushButton("🏖️ طلب إجازة")
        self.request_leave_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.request_leave_btn.setFixedHeight(28)
        self.request_leave_btn.clicked.connect(self.request_leave)
        
        self.approve_leave_btn = QPushButton("✅ موافقة")
        self.approve_leave_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.approve_leave_btn.setFixedHeight(28)
        self.approve_leave_btn.clicked.connect(self.approve_leave)
        
        self.reject_leave_btn = QPushButton("❌ رفض")
        self.reject_leave_btn.setStyleSheet(BUTTON_STYLES["danger"])
        self.reject_leave_btn.setFixedHeight(28)
        self.reject_leave_btn.clicked.connect(self.reject_leave)
        
        self.pending_leaves_btn = QPushButton("📋 الإجازات المعلقة")
        self.pending_leaves_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.pending_leaves_btn.setFixedHeight(28)
        self.pending_leaves_btn.clicked.connect(self._load_pending_leaves)
        
        leaves_buttons.addWidget(self.request_leave_btn)
        leaves_buttons.addWidget(self.approve_leave_btn)
        leaves_buttons.addWidget(self.reject_leave_btn)
        leaves_buttons.addWidget(self.pending_leaves_btn)
        leaves_buttons.addStretch()
        leaves_layout.addLayout(leaves_buttons)
        
        # جدول الإجازات
        self.leaves_table = QTableWidget()
        self.leaves_table.setColumnCount(8)
        self.leaves_table.setHorizontalHeaderLabels([
            "ID", "الموظف", "نوع الإجازة", "من تاريخ", "إلى تاريخ",
            "عدد الأيام", "الحالة", "السبب"
        ])
        header = self.leaves_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # الموظف - يتمدد
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # نوع الإجازة
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # من تاريخ
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # إلى تاريخ
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # عدد الأيام
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # السبب - يتمدد
        self.leaves_table.setAlternatingRowColors(True)
        self.leaves_table.setStyleSheet(self._get_table_style())
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.leaves_table)
        leaves_layout.addWidget(self.leaves_table)
        
        sub_tabs.addTab(leaves_widget, "🏖️ الإجازات")
        
        layout.addWidget(sub_tabs)
        return widget
    
    def _load_today_attendance(self):
        """تحميل حضور اليوم"""
        attendance = self.hr_service.get_today_attendance()
        self._update_attendance_table(attendance)
    
    def _filter_attendance(self):
        """فلترة الحضور بالتاريخ"""
        date_from = self.att_date_from.date().toString("yyyy-MM-dd")
        date_to = self.att_date_to.date().toString("yyyy-MM-dd")
        
        # فلترة بالموظف المحدد إذا وجد
        employee_id = self.current_employee['id'] if self.current_employee else None
        attendance = self.hr_service.get_attendance(employee_id, date_from, date_to)
        self._update_attendance_table(attendance)
    
    def _update_attendance_table(self, attendance):
        """تحديث جدول الحضور"""
        self.attendance_table.setRowCount(len(attendance))
        
        for row, att in enumerate(attendance):
            self.attendance_table.setItem(row, 0, create_centered_item(att.get('date', '')))
            self.attendance_table.setItem(row, 1, create_centered_item(att.get('employee_name', '')))
            self.attendance_table.setItem(row, 2, create_centered_item(att.get('department', '')))
            self.attendance_table.setItem(row, 3, create_centered_item(att.get('check_in_time', '')))
            self.attendance_table.setItem(row, 4, create_centered_item(att.get('check_out_time', '')))
            self.attendance_table.setItem(row, 5, create_centered_item(f"{att.get('work_hours', 0):.1f}"))
            self.attendance_table.setItem(row, 6, create_centered_item(f"{att.get('overtime_hours', 0):.1f}"))
            
            # الحالة مع لون الخلفية
            status = att.get('status', '')
            bg_color = None
            if status == 'حاضر':
                bg_color = Qt.GlobalColor.darkGreen
            elif status == 'غائب':
                bg_color = Qt.GlobalColor.darkRed
            elif status == 'متأخر':
                bg_color = Qt.GlobalColor.darkYellow
            self.attendance_table.setItem(row, 7, create_centered_item(status, bg_color))
    
    def check_in(self):
        """تسجيل حضور"""
        if not self.current_employee:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار موظف أولاً")
            return
        
        success, msg = self.hr_service.check_in_employee(self.current_employee['id'])
        if success:
            self._load_today_attendance()
            QMessageBox.information(self, "✅ نجح", f"تم تسجيل حضور {self.current_employee['name']}")
        else:
            QMessageBox.critical(self, "❌ خطأ", msg)
    
    def check_out(self):
        """تسجيل انصراف"""
        if not self.current_employee:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار موظف أولاً")
            return
        
        success, msg = self.hr_service.check_out_employee(self.current_employee['id'])
        if success:
            self._load_today_attendance()
            QMessageBox.information(self, "✅ نجح", f"تم تسجيل انصراف {self.current_employee['name']}")
        else:
            QMessageBox.critical(self, "❌ خطأ", msg)
    
    def manual_attendance(self):
        """تسجيل حضور يدوي"""
        if not self.current_employee:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار موظف أولاً")
            return
        
        dialog = ManualAttendanceDialog(self.current_employee, self.hr_service, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_today_attendance()
    
    def _load_pending_leaves(self):
        """تحميل الإجازات المعلقة"""
        leaves = self.hr_service.get_pending_leaves()
        self._update_leaves_table(leaves)
    
    def _update_leaves_table(self, leaves):
        """تحديث جدول الإجازات"""
        self.leaves_table.setRowCount(len(leaves))
        
        for row, leave in enumerate(leaves):
            self.leaves_table.setItem(row, 0, create_centered_item(leave.get('id', '')))
            self.leaves_table.setItem(row, 1, create_centered_item(leave.get('employee_name', '')))
            self.leaves_table.setItem(row, 2, create_centered_item(leave.get('leave_type', '')))
            self.leaves_table.setItem(row, 3, create_centered_item(leave.get('start_date', '')))
            self.leaves_table.setItem(row, 4, create_centered_item(leave.get('end_date', '')))
            self.leaves_table.setItem(row, 5, create_centered_item(leave.get('days_count', '')))
            
            # الحالة مع لون الخلفية
            status = leave.get('status', '')
            bg_color = None
            if status == 'موافق عليها':
                bg_color = Qt.GlobalColor.darkGreen
            elif status == 'مرفوضة':
                bg_color = Qt.GlobalColor.darkRed
            elif status == 'قيد المراجعة':
                bg_color = Qt.GlobalColor.darkYellow
            self.leaves_table.setItem(row, 6, create_centered_item(status, bg_color))
            
            self.leaves_table.setItem(row, 7, create_centered_item(leave.get('reason', '')))
    
    def request_leave(self):
        """طلب إجازة"""
        if not self.current_employee:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار موظف أولاً")
            return
        
        dialog = LeaveRequestDialog(self.current_employee, self.hr_service, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_pending_leaves()
    
    def approve_leave(self):
        """الموافقة على إجازة"""
        row = self.leaves_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار إجازة")
            return
        
        leave_id = int(self.leaves_table.item(row, 0).text())
        success, msg = self.hr_service.approve_leave(leave_id, "المدير")
        
        if success:
            self._load_pending_leaves()
            QMessageBox.information(self, "✅ نجح", msg)
        else:
            QMessageBox.critical(self, "❌ خطأ", msg)
    
    def reject_leave(self):
        """رفض إجازة"""
        row = self.leaves_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار إجازة")
            return
        
        leave_id = int(self.leaves_table.item(row, 0).text())
        success, msg = self.hr_service.reject_leave(leave_id, "المدير", "")
        
        if success:
            self._load_pending_leaves()
            QMessageBox.information(self, "✅ نجح", msg)
        else:
            QMessageBox.critical(self, "❌ خطأ", msg)

    # ==================== تاب التقارير ====================
    
    def _create_reports_tab(self):
        """إنشاء تاب التقارير"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # عنوان
        title = QLabel("📊 تقارير الموارد البشرية")
        title.setFont(get_cairo_font(14, bold=True))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #4a90e2; padding: 15px;")
        layout.addWidget(title)
        
        # أزرار التقارير
        reports_grid = QGridLayout()
        
        self.emp_report_btn = QPushButton("👥 تقرير الموظفين")
        self.emp_report_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.emp_report_btn.setFixedHeight(28)
        self.emp_report_btn.clicked.connect(self.show_employees_report)
        
        self.loans_report_btn = QPushButton("💰 ملخص السلف")
        self.loans_report_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.loans_report_btn.setFixedHeight(28)
        self.loans_report_btn.clicked.connect(self.show_loans_summary)
        
        self.payroll_report_btn = QPushButton("💵 ملخص المرتبات")
        self.payroll_report_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.payroll_report_btn.setFixedHeight(28)
        self.payroll_report_btn.clicked.connect(self.show_payroll_summary)
        
        self.att_report_btn = QPushButton("⏰ ملخص الحضور")
        self.att_report_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.att_report_btn.setFixedHeight(28)
        self.att_report_btn.clicked.connect(self.show_attendance_summary)
        
        reports_grid.addWidget(self.emp_report_btn, 0, 0)
        reports_grid.addWidget(self.loans_report_btn, 0, 1)
        reports_grid.addWidget(self.payroll_report_btn, 1, 0)
        reports_grid.addWidget(self.att_report_btn, 1, 1)
        
        layout.addLayout(reports_grid)
        
        # منطقة عرض التقارير
        self.reports_display = QTextEdit()
        self.reports_display.setReadOnly(True)
        self.reports_display.setStyleSheet("""
            QTextEdit {
                background-color: #001a3a;
                color: #ffffff;
                border: 1px solid #003366;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.reports_display)
        
        return widget
    
    def show_employees_report(self):
        """تقرير الموظفين"""
        summary = self.hr_service.get_employees_summary()
        
        report = f"""
📊 تقرير الموظفين
{'='*50}

📈 الإحصائيات العامة:
• إجمالي الموظفين: {summary['total']}
• الموظفين النشطين: {summary['active']}
• الموظفين غير النشطين: {summary['inactive']}

💰 الرواتب:
• متوسط الراتب: {summary['avg_salary']:.2f} ج.م
• أعلى راتب: {summary['max_salary']:.2f} ج.م
• أقل راتب: {summary['min_salary']:.2f} ج.م
• إجمالي الرواتب: {summary['total_salaries']:.2f} ج.م

🏢 التوزيع حسب الأقسام:
"""
        for dept in summary['departments']:
            report += f"• {dept['department'] or 'غير محدد'}: {dept['count']} موظف\n"
        
        report += f"\n📅 تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.reports_display.setText(report)
    
    def show_loans_summary(self):
        """ملخص السلف"""
        summary = self.hr_service.get_loans_summary()
        
        report = f"""
💰 ملخص السلف والقروض
{'='*50}

📊 الإحصائيات العامة:
• إجمالي السلف: {summary['total']}
• السلف النشطة: {summary['active']}
• السلف المكتملة: {summary['completed']}

💵 المبالغ:
• إجمالي المبالغ: {summary['total_amount']:.2f} ج.م
• إجمالي المتبقي: {summary['total_remaining']:.2f} ج.م
• إجمالي الأقساط الشهرية: {summary['monthly_deductions']:.2f} ج.م

📋 التوزيع حسب النوع:
"""
        for t in summary['types']:
            report += f"• {t['loan_type']}: {t['count']} سلفة (متبقي: {t['remaining']:.2f} ج.م)\n"
        
        report += f"\n📅 تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.reports_display.setText(report)
    
    def show_payroll_summary(self):
        """ملخص المرتبات"""
        month = self.month_combo.currentText()
        summary = self.hr_service.get_payroll_summary(month)
        
        report = f"""
💵 ملخص مرتبات شهر {month}
{'='*50}

📊 الإحصائيات:
• إجمالي الموظفين: {summary['total']}
• المرتبات المدفوعة: {summary['paid']}
• المرتبات المعلقة: {summary['pending']}

💰 المبالغ:
• إجمالي الرواتب الأساسية: {summary['total_basic']:.2f} ج.م
• إجمالي البدلات: {summary['total_allowances']:.2f} ج.م
• إجمالي الحوافز: {summary['total_bonuses']:.2f} ج.م

📉 الخصومات:
• خصم السلف: {summary['total_loan_deductions']:.2f} ج.م
• خصم التأمين: {summary['total_insurance']:.2f} ج.م
• خصم الضرائب: {summary['total_tax']:.2f} ج.م

💵 صافي المرتبات: {summary['total_net']:.2f} ج.م

📅 تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.reports_display.setText(report)
    
    def show_attendance_summary(self):
        """ملخص الحضور"""
        summary = self.hr_service.get_attendance_summary()
        
        report = f"""
⏰ ملخص الحضور
{'='*50}

📅 الفترة: من {summary['date_from']} إلى {summary['date_to']}

📊 الإحصائيات:
• إجمالي السجلات: {summary['total_records']}
• أيام الحضور: {summary['present']}
• أيام الغياب: {summary['absent']}
• أيام التأخير: {summary['late']}

⏱️ ساعات العمل:
• إجمالي ساعات العمل: {summary['total_work_hours']:.1f} ساعة
• إجمالي ساعات الإضافي: {summary['total_overtime']:.1f} ساعة

📅 تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.reports_display.setText(report)


# ==================== نوافذ الحوار ====================

class LoanDialog(QDialog):
    """نافذة إضافة سلفة"""
    
    def __init__(self, employee, hr_service, parent=None):
        super().__init__(parent)
        self.employee = employee
        self.hr_service = hr_service
        self.setWindowTitle(f"💰 إضافة سلفة - {employee['name']}")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMinimumHeight(450)
        
        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # ستايل داكن
        self.setStyleSheet("""
            QDialog { background-color: #001a3a; color: #ffffff; }
            QLabel { color: #ffffff; }
            QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit {
                background-color: #002040; color: #ffffff;
                border: 2px solid #003366; border-radius: 6px; padding: 8px;
            }
        """)
        
        # معلومات الموظف
        emp_info = QLabel(f"👤 الموظف: {self.employee['name']} - راتب: {self.employee.get('salary', 0):.2f} ج.م")
        emp_info.setStyleSheet("font-weight: bold; color: #4a90e2; padding: 10px; background-color: #002040; border-radius: 6px;")
        layout.addWidget(emp_info)
        
        # نموذج البيانات
        form = QFormLayout()
        
        self.loan_type = QComboBox()
        self.loan_type.addItems(["سلفة شخصية", "قرض إسكان", "مقدم راتب", "سلفة طوارئ", "قرض سيارة", "أخرى"])
        form.addRow("نوع السلفة:", self.loan_type)
        
        self.amount = QDoubleSpinBox()
        self.amount.setRange(100, 500000)
        self.amount.setSuffix(" ج.م")
        self.amount.setValue(5000)
        form.addRow("مبلغ السلفة:", self.amount)
        
        self.monthly = QDoubleSpinBox()
        self.monthly.setRange(50, 50000)
        self.monthly.setSuffix(" ج.م")
        self.monthly.setValue(500)
        form.addRow("القسط الشهري:", self.monthly)
        
        self.payment_method = QComboBox()
        self.payment_method.addItems(["نقدي (كاش)", "تحويل بنكي"])
        form.addRow("طريقة الصرف:", self.payment_method)
        
        self.reason = QTextEdit()
        self.reason.setMaximumHeight(60)
        self.reason.setPlaceholderText("سبب طلب السلفة...")
        form.addRow("السبب:", self.reason)
        
        layout.addLayout(form)
        
        # ملاحظة
        note = QLabel("💡 سيتم إنشاء قيد محاسبي تلقائياً وخصم القسط من الراتب شهرياً")
        note.setStyleSheet("background-color: #1e3a8a; color: white; padding: 8px; border-radius: 4px; font-size: 11px;")
        layout.addWidget(note)
        
        # أزرار
        buttons = QHBoxLayout()
        
        save_btn = QPushButton("💾 حفظ السلفة")
        save_btn.setStyleSheet(BUTTON_STYLES["success"])
        save_btn.clicked.connect(self._save)
        
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
    
    def _save(self):
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال مبلغ صحيح")
            return
        
        if self.monthly.value() > self.amount.value():
            QMessageBox.warning(self, "خطأ", "القسط الشهري لا يمكن أن يكون أكبر من المبلغ")
            return
        
        # تحذير إذا القسط أكبر من 50% من الراتب
        salary = self.employee.get('salary', 0) or 0
        if salary > 0 and self.monthly.value() > (salary * 0.5):
            reply = QMessageBox.question(
                self, "تحذير",
                f"القسط الشهري ({self.monthly.value():.0f} ج.م) يتجاوز 50% من الراتب.\nهل تريد المتابعة؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        loan_data = {
            'employee_id': self.employee['id'],
            'loan_type': self.loan_type.currentText(),
            'amount': self.amount.value(),
            'monthly_deduction': self.monthly.value(),
            'payment_method': 'cash' if 'نقدي' in self.payment_method.currentText() else 'bank',
            'reason': self.reason.toPlainText()
        }
        
        success, msg, loan_id = self.hr_service.add_loan(loan_data)
        
        if success:
            installments = int(self.amount.value() / self.monthly.value())
            QMessageBox.information(
                self, "✅ نجح",
                f"تم إضافة السلفة بنجاح!\n\n"
                f"المبلغ: {self.amount.value():.0f} ج.م\n"
                f"القسط الشهري: {self.monthly.value():.0f} ج.م\n"
                f"عدد الأقساط المتوقع: {installments} شهر\n\n"
                f"✅ تم إنشاء قيد محاسبي تلقائياً"
            )
            self.accept()
        else:
            QMessageBox.critical(self, "❌ خطأ", msg)


class PayLoanDialog(QDialog):
    """نافذة دفع قسط سلفة"""
    
    def __init__(self, loan_id, remaining, monthly, hr_service, parent=None):
        super().__init__(parent)
        self.loan_id = loan_id
        self.remaining = remaining
        self.monthly = monthly
        self.hr_service = hr_service
        self.setWindowTitle("💳 دفع قسط سلفة")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        
        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: #001a3a; color: #ffffff; }}
            QLabel {{ color: #ffffff; }}
            QDoubleSpinBox, QComboBox {{
                background-color: #002040; color: #ffffff;
                border: 2px solid #003366; border-radius: 6px; padding: 8px 10px 8px 28px;
            }}
            QDoubleSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top left;
                width: 20px; height: 14px;
                background: #003366; border: none;
                border-top-left-radius: 4px;
            }}
            QDoubleSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom left;
                width: 20px; height: 14px;
                background: #003366; border: none;
                border-bottom-left-radius: 4px;
            }}
            QDoubleSpinBox::up-arrow {{
                image: url(assets/up-arrow.png);
                width: 10px; height: 10px;
            }}
            QDoubleSpinBox::down-arrow {{
                image: url(assets/down-arrow.png);
                width: 10px; height: 10px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 22px; border: none;
            }}
            QComboBox::down-arrow {{
                image: url(assets/down-arrow.png);
                width: 10px; height: 10px;
            }}
        """)
        
        info = QLabel(f"المبلغ المتبقي: {self.remaining:.2f} ج.م\nالقسط الشهري: {self.monthly:.2f} ج.م")
        info.setStyleSheet("font-weight: bold; color: #4a90e2; padding: 10px; background-color: #002040; border-radius: 6px;")
        layout.addWidget(info)
        
        form = QFormLayout()
        
        self.amount = QDoubleSpinBox()
        self.amount.setRange(1, self.remaining)
        self.amount.setSuffix(" ج.م")
        self.amount.setValue(min(self.monthly, self.remaining))
        form.addRow("مبلغ الدفع:", self.amount)
        
        self.method = QComboBox()
        self.method.addItems(["خصم من الراتب", "نقدي (كاش)", "تحويل بنكي"])
        form.addRow("طريقة الدفع:", self.method)
        
        layout.addLayout(form)
        
        buttons = QHBoxLayout()
        
        pay_btn = QPushButton("💳 دفع")
        pay_btn.setStyleSheet(BUTTON_STYLES["success"])
        pay_btn.clicked.connect(self._pay)
        
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(pay_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
    
    def _pay(self):
        method_map = {"خصم من الراتب": "salary_deduction", "نقدي (كاش)": "cash", "تحويل بنكي": "bank"}
        method = method_map.get(self.method.currentText(), "salary_deduction")
        
        success, msg = self.hr_service.pay_loan_installment(self.loan_id, self.amount.value(), method)
        
        if success:
            QMessageBox.information(self, "✅ نجح", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "❌ خطأ", msg)


class ManualAttendanceDialog(QDialog):
    """نافذة تسجيل حضور يدوي"""
    
    def __init__(self, employee, hr_service, parent=None):
        super().__init__(parent)
        self.employee = employee
        self.hr_service = hr_service
        self.setWindowTitle(f"📝 تسجيل حضور - {employee['name']}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(350)
        
        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: #001a3a; color: #ffffff; }}
            QLabel {{ color: #ffffff; }}
            QDateEdit, QTimeEdit, QComboBox {{
                background-color: #002040; color: #ffffff;
                border: 2px solid #003366; border-radius: 6px; padding: 8px 10px 8px 28px;
            }}
            QDateEdit::up-button, QTimeEdit::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top left;
                width: 20px; height: 14px;
                background: #003366; border: none;
                border-top-left-radius: 4px;
            }}
            QDateEdit::down-button, QTimeEdit::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom left;
                width: 20px; height: 14px;
                background: #003366; border: none;
                border-bottom-left-radius: 4px;
            }}
            QDateEdit::up-arrow, QTimeEdit::up-arrow {{
                image: url(assets/up-arrow.png);
                width: 10px; height: 10px;
            }}
            QDateEdit::down-arrow, QTimeEdit::down-arrow {{
                image: url(assets/down-arrow.png);
                width: 10px; height: 10px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 22px; border: none;
            }}
            QComboBox::down-arrow {{
                image: url(assets/down-arrow.png);
                width: 10px; height: 10px;
            }}
        """)
        
        form = QFormLayout()
        
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        form.addRow("التاريخ:", self.date_input)
        
        self.check_in = QTimeEdit()
        self.check_in.setTime(datetime.now().time())
        form.addRow("وقت الحضور:", self.check_in)
        
        self.check_out = QTimeEdit()
        self.check_out.setTime(datetime.now().time())
        form.addRow("وقت الانصراف:", self.check_out)
        
        self.status = QComboBox()
        self.status.addItems(["حاضر", "متأخر", "غائب", "إجازة"])
        form.addRow("الحالة:", self.status)
        
        layout.addLayout(form)
        
        buttons = QHBoxLayout()
        
        save_btn = QPushButton("💾 حفظ")
        save_btn.setStyleSheet(BUTTON_STYLES["success"])
        save_btn.clicked.connect(self._save)
        
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
    
    def _save(self):
        success, msg = self.hr_service.record_attendance(
            self.employee['id'],
            self.date_input.date().toString("yyyy-MM-dd"),
            self.check_in.time().toString("HH:mm"),
            self.check_out.time().toString("HH:mm"),
            self.status.currentText()
        )
        
        if success:
            QMessageBox.information(self, "✅ نجح", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "❌ خطأ", msg)


class LeaveRequestDialog(QDialog):
    """نافذة طلب إجازة"""
    
    def __init__(self, employee, hr_service, parent=None):
        super().__init__(parent)
        self.employee = employee
        self.hr_service = hr_service
        self.setWindowTitle(f"🏖️ طلب إجازة - {employee['name']}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(400)
        
        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: #001a3a; color: #ffffff; }}
            QLabel {{ color: #ffffff; }}
            QDateEdit, QComboBox, QTextEdit {{
                background-color: #002040; color: #ffffff;
                border: 2px solid #003366; border-radius: 6px; padding: 8px 10px 8px 28px;
            }}
            QDateEdit::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top left;
                width: 20px; height: 14px;
                background: #003366; border: none;
                border-top-left-radius: 4px;
            }}
            QDateEdit::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom left;
                width: 20px; height: 14px;
                background: #003366; border: none;
                border-bottom-left-radius: 4px;
            }}
            QDateEdit::up-arrow {{
                image: url(assets/up-arrow.png);
                width: 10px; height: 10px;
            }}
            QDateEdit::down-arrow {{
                image: url(assets/down-arrow.png);
                width: 10px; height: 10px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 22px; border: none;
            }}
            QComboBox::down-arrow {{
                image: url(assets/down-arrow.png);
                width: 10px; height: 10px;
            }}
        """)
        
        form = QFormLayout()
        
        self.leave_type = QComboBox()
        self.leave_type.addItems(["إجازة سنوية", "إجازة مرضية", "إجازة طارئة", "إجازة بدون راتب", "إجازة زواج", "إجازة وفاة"])
        form.addRow("نوع الإجازة:", self.leave_type)
        
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        form.addRow("من تاريخ:", self.start_date)
        
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        form.addRow("إلى تاريخ:", self.end_date)
        
        self.reason = QTextEdit()
        self.reason.setMaximumHeight(60)
        self.reason.setPlaceholderText("سبب الإجازة...")
        form.addRow("السبب:", self.reason)
        
        layout.addLayout(form)
        
        buttons = QHBoxLayout()
        
        save_btn = QPushButton("📤 تقديم الطلب")
        save_btn.setStyleSheet(BUTTON_STYLES["success"])
        save_btn.clicked.connect(self._save)
        
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
    
    def _save(self):
        if self.end_date.date() < self.start_date.date():
            QMessageBox.warning(self, "خطأ", "تاريخ النهاية يجب أن يكون بعد تاريخ البداية")
            return
        
        success, msg = self.hr_service.request_leave(
            self.employee['id'],
            self.leave_type.currentText(),
            self.start_date.date().toString("yyyy-MM-dd"),
            self.end_date.date().toString("yyyy-MM-dd"),
            self.reason.toPlainText()
        )
        
        if success:
            QMessageBox.information(self, "✅ نجح", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "❌ خطأ", msg)


class LoanDetailsDialog(QDialog):
    """نافذة تفاصيل السلفة وأقساطها"""
    
    def __init__(self, loan_id, hr_service, parent=None):
        super().__init__(parent)
        self.loan_id = loan_id
        self.hr_service = hr_service
        self.setWindowTitle("📋 تفاصيل السلفة")
        self.setModal(True)
        self.setMinimumSize(600, 500)
        
        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass
        
        self._init_ui()
        self._load_data()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.setStyleSheet("""
            QDialog { background-color: #001a3a; color: #ffffff; }
            QLabel { color: #ffffff; }
            QGroupBox {
                background-color: #002040;
                border: 2px solid #003366;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: #4a90e2;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """ + TABLE_STYLE_DARK + """
        """)
        
        # معلومات السلفة
        self.info_group = QGroupBox("💰 معلومات السلفة")
        info_layout = QGridLayout()
        self.info_group.setLayout(info_layout)
        
        self.emp_label = QLabel("الموظف: -")
        self.type_label = QLabel("النوع: -")
        self.amount_label = QLabel("المبلغ: -")
        self.remaining_label = QLabel("المتبقي: -")
        self.monthly_label = QLabel("القسط: -")
        self.status_label = QLabel("الحالة: -")
        self.start_label = QLabel("تاريخ البداية: -")
        self.reason_label = QLabel("السبب: -")
        
        info_layout.addWidget(self.emp_label, 0, 0)
        info_layout.addWidget(self.type_label, 0, 1)
        info_layout.addWidget(self.amount_label, 1, 0)
        info_layout.addWidget(self.remaining_label, 1, 1)
        info_layout.addWidget(self.monthly_label, 2, 0)
        info_layout.addWidget(self.status_label, 2, 1)
        info_layout.addWidget(self.start_label, 3, 0)
        info_layout.addWidget(self.reason_label, 3, 1)
        
        layout.addWidget(self.info_group)
        
        # شريط التقدم
        self.progress_label = QLabel("التقدم: 0%")
        self.progress_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4a90e2; padding: 10px;")
        layout.addWidget(self.progress_label)
        
        # جدول الأقساط
        payments_group = QGroupBox("💳 سجل الأقساط المدفوعة")
        payments_layout = QVBoxLayout()
        payments_group.setLayout(payments_layout)
        
        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(4)
        self.payments_table.setHorizontalHeaderLabels(["التاريخ", "المبلغ", "طريقة الدفع", "ملاحظات"])
        header = self.payments_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # التاريخ
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # المبلغ
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # طريقة الدفع
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # ملاحظات - يتمدد
        self.payments_table.setAlternatingRowColors(True)
        payments_layout.addWidget(self.payments_table)
        
        layout.addWidget(payments_group)
        
        # أزرار
        buttons = QHBoxLayout()
        
        close_btn = QPushButton("✅ إغلاق")
        close_btn.setStyleSheet(BUTTON_STYLES["primary"])
        close_btn.clicked.connect(self.accept)
        
        buttons.addStretch()
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)
    
    def _load_data(self):
        """تحميل بيانات السلفة"""
        # جلب بيانات السلفة
        loans = self.hr_service.get_employee_loans()
        loan = None
        for l in loans:
            if l.get('id') == self.loan_id:
                loan = l
                break
        
        if not loan:
            return
        
        # تحديث المعلومات
        self.emp_label.setText(f"👤 الموظف: {loan.get('employee_name', '-')}")
        self.type_label.setText(f"📋 النوع: {loan.get('loan_type', '-')}")
        self.amount_label.setText(f"💵 المبلغ: {loan.get('amount', 0):,.2f} ج.م")
        self.remaining_label.setText(f"📉 المتبقي: {loan.get('remaining_amount', 0):,.2f} ج.م")
        self.monthly_label.setText(f"📅 القسط: {loan.get('monthly_deduction', 0):,.2f} ج.م")
        self.status_label.setText(f"🔄 الحالة: {loan.get('status', '-')}")
        self.start_label.setText(f"📆 البداية: {loan.get('start_date', '-')}")
        self.reason_label.setText(f"📝 السبب: {loan.get('reason', '-')[:30]}...")
        
        # حساب التقدم
        amount = loan.get('amount', 0) or 1
        remaining = loan.get('remaining_amount', 0) or 0
        progress = ((amount - remaining) / amount) * 100
        self.progress_label.setText(f"📊 التقدم: {progress:.1f}% ({amount - remaining:,.2f} من {amount:,.2f} ج.م)")
        
        # تحميل الأقساط
        payments = self.hr_service.get_loan_payments(self.loan_id)
        self.payments_table.setRowCount(len(payments))
        
        for row, payment in enumerate(payments):
            self.payments_table.setItem(row, 0, create_centered_item(payment.get('payment_date', '')))
            self.payments_table.setItem(row, 1, create_centered_item(f"{payment.get('amount', 0):,.2f} ج.م"))
            
            method = payment.get('payment_method', '')
            method_text = {'salary_deduction': 'خصم من الراتب', 'cash': 'نقدي', 'bank': 'تحويل بنكي'}.get(method, method)
            self.payments_table.setItem(row, 2, create_centered_item(method_text))
            self.payments_table.setItem(row, 3, create_centered_item(payment.get('notes', '')))



class EditSalaryDialog(QDialog):
    """نافذة تعديل راتب موظف"""
    
    def __init__(self, employee_id, month, hr_service, parent=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.month = month
        self.hr_service = hr_service
        self.setWindowTitle(f"✏️ تعديل راتب شهر {month}")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(500)
        
        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass
        
        self._init_ui()
        self._load_data()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: #001a3a; color: #ffffff; }}
            QLabel {{ color: #ffffff; }}
            QDoubleSpinBox, QComboBox {{
                background-color: #002040; color: #ffffff;
                border: 2px solid #003366; border-radius: 6px; padding: 8px 10px 8px 28px;
            }}
            QDoubleSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top left;
                width: 20px; height: 14px;
                background: #003366; border: none;
                border-top-left-radius: 4px;
            }}
            QDoubleSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom left;
                width: 20px; height: 14px;
                background: #003366; border: none;
                border-bottom-left-radius: 4px;
            }}
            QDoubleSpinBox::up-arrow {{
                image: url(assets/up-arrow.png);
                width: 10px; height: 10px;
            }}
            QDoubleSpinBox::down-arrow {{
                image: url(assets/down-arrow.png);
                width: 10px; height: 10px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 22px; border: none;
            }}
            QComboBox::down-arrow {{
                image: url(assets/down-arrow.png);
                width: 10px; height: 10px;
            }}
            QGroupBox {{
                background-color: #002040;
                border: 2px solid #003366;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: #4a90e2;
            }}
        """)
        
        # معلومات الموظف
        self.emp_info = QLabel("جاري التحميل...")
        self.emp_info.setStyleSheet("font-weight: bold; color: #4a90e2; padding: 10px; background-color: #002040; border-radius: 6px;")
        layout.addWidget(self.emp_info)
        
        # الإضافات
        additions_group = QGroupBox("➕ الإضافات")
        additions_layout = QFormLayout()
        additions_group.setLayout(additions_layout)
        
        self.allowances_input = QDoubleSpinBox()
        self.allowances_input.setRange(0, 100000)
        self.allowances_input.setSuffix(" ج.م")
        self.allowances_input.valueChanged.connect(self._calculate_net)
        additions_layout.addRow("البدلات:", self.allowances_input)
        
        self.bonuses_input = QDoubleSpinBox()
        self.bonuses_input.setRange(0, 100000)
        self.bonuses_input.setSuffix(" ج.م")
        self.bonuses_input.valueChanged.connect(self._calculate_net)
        additions_layout.addRow("الحوافز:", self.bonuses_input)
        
        self.overtime_hours_input = QDoubleSpinBox()
        self.overtime_hours_input.setRange(0, 200)
        self.overtime_hours_input.setSuffix(" ساعة")
        self.overtime_hours_input.valueChanged.connect(self._calculate_net)
        additions_layout.addRow("ساعات الإضافي:", self.overtime_hours_input)
        
        self.overtime_rate_input = QDoubleSpinBox()
        self.overtime_rate_input.setRange(0, 500)
        self.overtime_rate_input.setSuffix(" ج.م/ساعة")
        self.overtime_rate_input.valueChanged.connect(self._calculate_net)
        additions_layout.addRow("سعر الساعة:", self.overtime_rate_input)
        
        layout.addWidget(additions_group)
        
        # الخصومات
        deductions_group = QGroupBox("➖ الخصومات الإضافية")
        deductions_layout = QFormLayout()
        deductions_group.setLayout(deductions_layout)
        
        self.other_deductions_input = QDoubleSpinBox()
        self.other_deductions_input.setRange(0, 100000)
        self.other_deductions_input.setSuffix(" ج.م")
        self.other_deductions_input.valueChanged.connect(self._calculate_net)
        deductions_layout.addRow("خصومات أخرى:", self.other_deductions_input)
        
        layout.addWidget(deductions_group)
        
        # الملخص
        self.summary_label = QLabel("الصافي: 0.00 ج.م")
        self.summary_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #22c55e; padding: 15px; background-color: #002040; border-radius: 6px; text-align: center;")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary_label)
        
        # أزرار
        buttons = QHBoxLayout()
        
        save_btn = QPushButton("💾 حفظ التعديلات")
        save_btn.setStyleSheet(BUTTON_STYLES["success"])
        save_btn.clicked.connect(self._save)
        
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
    
    def _load_data(self):
        """تحميل بيانات الراتب"""
        # جلب بيانات الموظف
        employee = self.hr_service.get_employee_by_id(self.employee_id)
        if employee:
            self.basic_salary = employee.get('salary', 0) or 0
            self.emp_info.setText(f"👤 {employee['name']} | الراتب الأساسي: {self.basic_salary:,.2f} ج.م")
        else:
            self.basic_salary = 0
        
        # جلب بيانات الراتب الحالي
        salaries = self.hr_service.get_salaries(self.month)
        for sal in salaries:
            if sal.get('employee_id') == self.employee_id:
                self.allowances_input.setValue(sal.get('allowances', 0) or 0)
                self.bonuses_input.setValue(sal.get('bonuses', 0) or 0)
                self.overtime_hours_input.setValue(sal.get('overtime_hours', 0) or 0)
                self.overtime_rate_input.setValue(sal.get('overtime_rate', 0) or 0)
                self.other_deductions_input.setValue(sal.get('other_deductions', 0) or 0)
                break
        
        self._calculate_net()
    
    def _calculate_net(self):
        """حساب الصافي"""
        allowances = self.allowances_input.value()
        bonuses = self.bonuses_input.value()
        overtime = self.overtime_hours_input.value() * self.overtime_rate_input.value()
        other_ded = self.other_deductions_input.value()
        
        # الخصومات الثابتة (تقريبية)
        insurance = self.basic_salary * 0.05
        tax = self.basic_salary * 0.10 if self.basic_salary > 5000 else 0
        
        gross = self.basic_salary + allowances + bonuses + overtime
        net = gross - insurance - tax - other_ded
        
        self.summary_label.setText(
            f"💵 الإجمالي: {gross:,.2f} ج.م | الخصومات: {insurance + tax + other_ded:,.2f} ج.م | الصافي: {net:,.2f} ج.م"
        )
    
    def _save(self):
        """حفظ التعديلات"""
        success, msg, _ = self.hr_service.calculate_salary(
            self.employee_id,
            self.month,
            allowances=self.allowances_input.value(),
            bonuses=self.bonuses_input.value(),
            overtime_hours=self.overtime_hours_input.value(),
            overtime_rate=self.overtime_rate_input.value(),
            other_deductions=self.other_deductions_input.value()
        )
        
        if success:
            QMessageBox.information(self, "✅ نجح", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "❌ خطأ", msg)
