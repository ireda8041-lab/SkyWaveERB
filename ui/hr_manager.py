# الملف: ui/hr_manager.py
"""
🏢 تاب إدارة الموارد البشرية - Production Grade
================================================
نظام متكامل لإدارة:
- الموظفين
- الحضور والانصراف
- الإجازات
- السلف
- المرتبات
"""

from datetime import datetime
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QLineEdit, QComboBox,
    QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QMessageBox,
    QHeaderView, QGroupBox, QFormLayout, QDialog, QSizePolicy,
    QFrame, QGridLayout, QAbstractItemView
)
from PyQt6.QtGui import QColor

from services.hr_service import HRService
from ui.styles import BUTTON_STYLES

try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class HRManagerTab(QWidget):
    """تاب إدارة الموارد البشرية"""

    def __init__(self, hr_service: HRService, current_user=None):
        super().__init__()
        self.hr_service = hr_service
        self.current_user = current_user
        self.init_ui()
        self.load_data()

    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # عنوان
        title = QLabel("🏢 إدارة الموارد البشرية")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a90e2; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # إحصائيات سريعة
        self.stats_frame = self._create_stats_frame()
        layout.addWidget(self.stats_frame)

        # التابات الداخلية
        self.tabs = QTabWidget()
        self.tabs.tabBar().setExpanding(True)
        layout.addWidget(self.tabs)

        # تاب الموظفين
        self.employees_tab = self._create_employees_tab()
        self.tabs.addTab(self.employees_tab, "👥 الموظفين")

        # تاب الحضور
        self.attendance_tab = self._create_attendance_tab()
        self.tabs.addTab(self.attendance_tab, "📅 الحضور")

        # تاب الإجازات
        self.leaves_tab = self._create_leaves_tab()
        self.tabs.addTab(self.leaves_tab, "🏖️ الإجازات")

        # تاب السلف
        self.loans_tab = self._create_loans_tab()
        self.tabs.addTab(self.loans_tab, "💳 السلف")

        # تاب المرتبات
        self.salaries_tab = self._create_salaries_tab()
        self.tabs.addTab(self.salaries_tab, "💰 المرتبات")

        # تطبيق الستايل
        self._apply_styles()

    def _create_stats_frame(self) -> QFrame:
        """إنشاء إطار الإحصائيات"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #002040;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        layout = QHBoxLayout()
        frame.setLayout(layout)

        # إحصائيات
        self.stat_employees = self._create_stat_card("👥 الموظفين", "0")
        self.stat_salaries = self._create_stat_card("💰 إجمالي الرواتب", "0 ج.م")
        self.stat_loans = self._create_stat_card("💳 السلف النشطة", "0")
        self.stat_leaves = self._create_stat_card("🏖️ طلبات معلقة", "0")

        layout.addWidget(self.stat_employees)
        layout.addWidget(self.stat_salaries)
        layout.addWidget(self.stat_loans)
        layout.addWidget(self.stat_leaves)

        return frame

    def _create_stat_card(self, title: str, value: str) -> QFrame:
        """إنشاء بطاقة إحصائية"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #003366;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout()
        card.setLayout(layout)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #888; font-size: 12px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet("color: #4a90e2; font-size: 20px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        return card


    def _create_employees_tab(self) -> QWidget:
        """تاب الموظفين"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # شريط الأدوات
        toolbar = QHBoxLayout()

        self.emp_search = QLineEdit()
        self.emp_search.setPlaceholderText("🔍 بحث عن موظف...")
        self.emp_search.textChanged.connect(self._filter_employees)
        toolbar.addWidget(self.emp_search)

        add_btn = QPushButton("➕ إضافة موظف")
        add_btn.setStyleSheet(BUTTON_STYLES["success"])
        add_btn.clicked.connect(self._add_employee)
        toolbar.addWidget(add_btn)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setStyleSheet(BUTTON_STYLES["info"])
        refresh_btn.clicked.connect(self._load_employees)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)

        # جدول الموظفين
        self.employees_table = QTableWidget()
        self.employees_table.setColumnCount(8)
        self.employees_table.setHorizontalHeaderLabels([
            "الاسم", "رقم الموظف", "الوظيفة", "القسم", "الراتب", "الحالة", "تعديل", "حذف"
        ])
        self.employees_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.employees_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.employees_table.setAlternatingRowColors(True)
        layout.addWidget(self.employees_table)

        return widget

    def _create_attendance_tab(self) -> QWidget:
        """تاب الحضور"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # شريط الأدوات
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("التاريخ:"))
        self.attendance_date = QDateEdit()
        self.attendance_date.setDate(QDate.currentDate())
        self.attendance_date.setCalendarPopup(True)
        self.attendance_date.dateChanged.connect(self._load_attendance)
        toolbar.addWidget(self.attendance_date)

        toolbar.addStretch()

        check_in_btn = QPushButton("✅ تسجيل حضور")
        check_in_btn.setStyleSheet(BUTTON_STYLES["success"])
        check_in_btn.clicked.connect(self._record_check_in)
        toolbar.addWidget(check_in_btn)

        check_out_btn = QPushButton("🚪 تسجيل انصراف")
        check_out_btn.setStyleSheet(BUTTON_STYLES["warning"])
        check_out_btn.clicked.connect(self._record_check_out)
        toolbar.addWidget(check_out_btn)

        layout.addLayout(toolbar)

        # جدول الحضور
        self.attendance_table = QTableWidget()
        self.attendance_table.setColumnCount(7)
        self.attendance_table.setHorizontalHeaderLabels([
            "الموظف", "القسم", "الحضور", "الانصراف", "ساعات العمل", "إضافي", "الحالة"
        ])
        self.attendance_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.attendance_table.setAlternatingRowColors(True)
        layout.addWidget(self.attendance_table)

        return widget

    def _create_leaves_tab(self) -> QWidget:
        """تاب الإجازات"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # شريط الأدوات
        toolbar = QHBoxLayout()

        self.leave_filter = QComboBox()
        self.leave_filter.addItems(["الكل", "معلق", "موافق عليه", "مرفوض"])
        self.leave_filter.currentTextChanged.connect(self._filter_leaves)
        toolbar.addWidget(self.leave_filter)

        toolbar.addStretch()

        add_leave_btn = QPushButton("➕ طلب إجازة")
        add_leave_btn.setStyleSheet(BUTTON_STYLES["success"])
        add_leave_btn.clicked.connect(self._add_leave_request)
        toolbar.addWidget(add_leave_btn)

        layout.addLayout(toolbar)

        # جدول الإجازات
        self.leaves_table = QTableWidget()
        self.leaves_table.setColumnCount(8)
        self.leaves_table.setHorizontalHeaderLabels([
            "الموظف", "النوع", "من", "إلى", "الأيام", "الحالة", "موافقة", "رفض"
        ])
        self.leaves_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.leaves_table.setAlternatingRowColors(True)
        layout.addWidget(self.leaves_table)

        return widget


    def _create_loans_tab(self) -> QWidget:
        """تاب السلف"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # شريط الأدوات
        toolbar = QHBoxLayout()

        self.loan_filter = QComboBox()
        self.loan_filter.addItems(["الكل", "نشط", "مسدد"])
        self.loan_filter.currentTextChanged.connect(self._filter_loans)
        toolbar.addWidget(self.loan_filter)

        toolbar.addStretch()

        add_loan_btn = QPushButton("➕ سلفة جديدة")
        add_loan_btn.setStyleSheet(BUTTON_STYLES["success"])
        add_loan_btn.clicked.connect(self._add_loan)
        toolbar.addWidget(add_loan_btn)

        layout.addLayout(toolbar)

        # جدول السلف
        self.loans_table = QTableWidget()
        self.loans_table.setColumnCount(7)
        self.loans_table.setHorizontalHeaderLabels([
            "الموظف", "المبلغ", "المتبقي", "القسط الشهري", "الحالة", "سداد", "تفاصيل"
        ])
        self.loans_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.loans_table.setAlternatingRowColors(True)
        layout.addWidget(self.loans_table)

        return widget

    def _create_salaries_tab(self) -> QWidget:
        """تاب المرتبات"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # شريط الأدوات
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("الشهر:"))
        self.salary_month = QComboBox()
        # إضافة آخر 12 شهر
        now = datetime.now()
        for i in range(12):
            month = now.replace(day=1) - __import__('datetime').timedelta(days=i*30)
            self.salary_month.addItem(month.strftime("%Y-%m"))
        self.salary_month.currentTextChanged.connect(self._load_salaries)
        toolbar.addWidget(self.salary_month)

        toolbar.addStretch()

        calc_btn = QPushButton("🧮 حساب المرتبات")
        calc_btn.setStyleSheet(BUTTON_STYLES["info"])
        calc_btn.clicked.connect(self._calculate_salaries)
        toolbar.addWidget(calc_btn)

        pay_all_btn = QPushButton("💰 صرف الكل")
        pay_all_btn.setStyleSheet(BUTTON_STYLES["success"])
        pay_all_btn.clicked.connect(self._pay_all_salaries)
        toolbar.addWidget(pay_all_btn)

        layout.addLayout(toolbar)

        # ملخص المرتبات
        summary_frame = QFrame()
        summary_frame.setStyleSheet("background-color: #002040; border-radius: 8px; padding: 10px;")
        summary_layout = QHBoxLayout()
        summary_frame.setLayout(summary_layout)

        self.salary_total_gross = QLabel("إجمالي: 0 ج.م")
        self.salary_total_gross.setStyleSheet("color: #4a90e2; font-size: 14px;")
        summary_layout.addWidget(self.salary_total_gross)

        self.salary_total_deductions = QLabel("خصومات: 0 ج.م")
        self.salary_total_deductions.setStyleSheet("color: #ef4444; font-size: 14px;")
        summary_layout.addWidget(self.salary_total_deductions)

        self.salary_total_net = QLabel("صافي: 0 ج.م")
        self.salary_total_net.setStyleSheet("color: #22c55e; font-size: 14px; font-weight: bold;")
        summary_layout.addWidget(self.salary_total_net)

        layout.addWidget(summary_frame)

        # جدول المرتبات
        self.salaries_table = QTableWidget()
        self.salaries_table.setColumnCount(9)
        self.salaries_table.setHorizontalHeaderLabels([
            "الموظف", "الأساسي", "البدلات", "إضافي", "خصومات", "إجمالي", "صافي", "الحالة", "صرف"
        ])
        self.salaries_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.salaries_table.setAlternatingRowColors(True)
        layout.addWidget(self.salaries_table)

        return widget


    def _apply_styles(self):
        """تطبيق الستايلات"""
        self.setStyleSheet("""
            QWidget {
                background-color: #001a3a;
                color: #ffffff;
            }
            QTableWidget {
                background-color: #002040;
                alternate-background-color: #002855;
                gridline-color: #003366;
                border: 1px solid #003366;
                border-radius: 8px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #4a90e2;
            }
            QHeaderView::section {
                background-color: #003366;
                color: #ffffff;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
                background-color: #002040;
                color: #ffffff;
                border: 2px solid #003366;
                border-radius: 6px;
                padding: 8px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
                border: 2px solid #4a90e2;
            }
            QTabWidget::pane {
                border: 1px solid #003366;
                background-color: #001a3a;
            }
            QTabBar::tab {
                background-color: #002040;
                color: #ffffff;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #4a90e2;
            }
        """)

    # ==================== تحميل البيانات ====================
    def load_data(self):
        """تحميل جميع البيانات"""
        self._load_statistics()
        self._load_employees()
        self._load_attendance()
        self._load_leaves()
        self._load_loans()
        self._load_salaries()

    def _load_statistics(self):
        """تحميل الإحصائيات"""
        try:
            stats = self.hr_service.get_statistics()
            
            self.stat_employees.findChild(QLabel, "value").setText(str(stats.get("active_employees", 0)))
            self.stat_salaries.findChild(QLabel, "value").setText(f"{stats.get('total_salaries', 0):,.0f} ج.م")
            self.stat_loans.findChild(QLabel, "value").setText(str(stats.get("active_loans_count", 0)))
            self.stat_leaves.findChild(QLabel, "value").setText(str(stats.get("pending_leaves", 0)))
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل الإحصائيات: {e}")

    def _load_employees(self):
        """تحميل الموظفين"""
        try:
            employees = self.hr_service.get_all_employees()
            self.employees_table.setRowCount(len(employees))
            
            for row, emp in enumerate(employees):
                self.employees_table.setItem(row, 0, QTableWidgetItem(emp.get("name", "")))
                self.employees_table.setItem(row, 1, QTableWidgetItem(emp.get("employee_id", "")))
                self.employees_table.setItem(row, 2, QTableWidgetItem(emp.get("position", "")))
                self.employees_table.setItem(row, 3, QTableWidgetItem(emp.get("department", "")))
                self.employees_table.setItem(row, 4, QTableWidgetItem(f"{emp.get('salary', 0):,.0f}"))
                
                status_item = QTableWidgetItem(emp.get("status", ""))
                if emp.get("status") == "نشط":
                    status_item.setForeground(QColor("#22c55e"))
                else:
                    status_item.setForeground(QColor("#ef4444"))
                self.employees_table.setItem(row, 5, status_item)
                
                # زر التعديل
                edit_btn = QPushButton("✏️")
                edit_btn.setStyleSheet(BUTTON_STYLES["info"])
                edit_btn.clicked.connect(lambda checked, e=emp: self._edit_employee(e))
                self.employees_table.setCellWidget(row, 6, edit_btn)
                
                # زر الحذف
                del_btn = QPushButton("🗑️")
                del_btn.setStyleSheet(BUTTON_STYLES["danger"])
                del_btn.clicked.connect(lambda checked, e=emp: self._delete_employee(e))
                self.employees_table.setCellWidget(row, 7, del_btn)
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل الموظفين: {e}")


    def _load_attendance(self):
        """تحميل الحضور"""
        try:
            date = self.attendance_date.date().toString("yyyy-MM-dd")
            attendance = self.hr_service.get_attendance_for_date(date)
            
            # إذا لم يكن هناك سجلات، أظهر جميع الموظفين
            if not attendance:
                employees = self.hr_service.get_active_employees()
                self.attendance_table.setRowCount(len(employees))
                for row, emp in enumerate(employees):
                    self.attendance_table.setItem(row, 0, QTableWidgetItem(emp.get("name", "")))
                    self.attendance_table.setItem(row, 1, QTableWidgetItem(emp.get("department", "")))
                    self.attendance_table.setItem(row, 2, QTableWidgetItem("-"))
                    self.attendance_table.setItem(row, 3, QTableWidgetItem("-"))
                    self.attendance_table.setItem(row, 4, QTableWidgetItem("-"))
                    self.attendance_table.setItem(row, 5, QTableWidgetItem("-"))
                    self.attendance_table.setItem(row, 6, QTableWidgetItem("لم يسجل"))
            else:
                self.attendance_table.setRowCount(len(attendance))
                for row, att in enumerate(attendance):
                    self.attendance_table.setItem(row, 0, QTableWidgetItem(att.get("employee_name", "")))
                    self.attendance_table.setItem(row, 1, QTableWidgetItem(att.get("department", "")))
                    self.attendance_table.setItem(row, 2, QTableWidgetItem(att.get("check_in_time", "-")))
                    self.attendance_table.setItem(row, 3, QTableWidgetItem(att.get("check_out_time", "-")))
                    self.attendance_table.setItem(row, 4, QTableWidgetItem(f"{att.get('work_hours', 0):.1f}"))
                    self.attendance_table.setItem(row, 5, QTableWidgetItem(f"{att.get('overtime_hours', 0):.1f}"))
                    
                    status_item = QTableWidgetItem(att.get("status", ""))
                    if att.get("status") == "حاضر":
                        status_item.setForeground(QColor("#22c55e"))
                    elif att.get("status") in ["متأخر", "انصراف مبكر"]:
                        status_item.setForeground(QColor("#f59e0b"))
                    elif att.get("status") == "غائب":
                        status_item.setForeground(QColor("#ef4444"))
                    self.attendance_table.setItem(row, 6, status_item)
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل الحضور: {e}")

    def _load_leaves(self):
        """تحميل الإجازات"""
        try:
            filter_status = self.leave_filter.currentText()
            status = None if filter_status == "الكل" else filter_status
            leaves = self.hr_service.get_all_leaves(status=status)
            
            self.leaves_table.setRowCount(len(leaves))
            for row, leave in enumerate(leaves):
                self.leaves_table.setItem(row, 0, QTableWidgetItem(leave.get("employee_name", "")))
                self.leaves_table.setItem(row, 1, QTableWidgetItem(leave.get("leave_type", "")))
                self.leaves_table.setItem(row, 2, QTableWidgetItem(leave.get("start_date", "")[:10] if leave.get("start_date") else ""))
                self.leaves_table.setItem(row, 3, QTableWidgetItem(leave.get("end_date", "")[:10] if leave.get("end_date") else ""))
                self.leaves_table.setItem(row, 4, QTableWidgetItem(str(leave.get("days_count", 0))))
                
                status_item = QTableWidgetItem(leave.get("status", ""))
                if leave.get("status") == "موافق عليه":
                    status_item.setForeground(QColor("#22c55e"))
                elif leave.get("status") == "مرفوض":
                    status_item.setForeground(QColor("#ef4444"))
                else:
                    status_item.setForeground(QColor("#f59e0b"))
                self.leaves_table.setItem(row, 5, status_item)
                
                # أزرار الموافقة والرفض
                if leave.get("status") == "معلق":
                    approve_btn = QPushButton("✅")
                    approve_btn.setStyleSheet(BUTTON_STYLES["success"])
                    approve_btn.clicked.connect(lambda checked, l=leave: self._approve_leave(l))
                    self.leaves_table.setCellWidget(row, 6, approve_btn)
                    
                    reject_btn = QPushButton("❌")
                    reject_btn.setStyleSheet(BUTTON_STYLES["danger"])
                    reject_btn.clicked.connect(lambda checked, l=leave: self._reject_leave(l))
                    self.leaves_table.setCellWidget(row, 7, reject_btn)
                else:
                    self.leaves_table.setItem(row, 6, QTableWidgetItem("-"))
                    self.leaves_table.setItem(row, 7, QTableWidgetItem("-"))
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل الإجازات: {e}")

    def _load_loans(self):
        """تحميل السلف"""
        try:
            filter_status = self.loan_filter.currentText()
            status = None if filter_status == "الكل" else filter_status
            loans = self.hr_service.get_all_loans(status=status)
            
            self.loans_table.setRowCount(len(loans))
            for row, loan in enumerate(loans):
                self.loans_table.setItem(row, 0, QTableWidgetItem(loan.get("employee_name", "")))
                self.loans_table.setItem(row, 1, QTableWidgetItem(f"{loan.get('amount', 0):,.0f}"))
                self.loans_table.setItem(row, 2, QTableWidgetItem(f"{loan.get('remaining_amount', 0):,.0f}"))
                self.loans_table.setItem(row, 3, QTableWidgetItem(f"{loan.get('monthly_deduction', 0):,.0f}"))
                
                status_item = QTableWidgetItem(loan.get("status", ""))
                if loan.get("status") == "مسدد":
                    status_item.setForeground(QColor("#22c55e"))
                else:
                    status_item.setForeground(QColor("#f59e0b"))
                self.loans_table.setItem(row, 4, status_item)
                
                # زر السداد
                if loan.get("status") == "نشط":
                    pay_btn = QPushButton("💰")
                    pay_btn.setStyleSheet(BUTTON_STYLES["success"])
                    pay_btn.clicked.connect(lambda checked, l=loan: self._pay_loan_installment(l))
                    self.loans_table.setCellWidget(row, 5, pay_btn)
                else:
                    self.loans_table.setItem(row, 5, QTableWidgetItem("-"))
                
                self.loans_table.setItem(row, 6, QTableWidgetItem(loan.get("reason", "") or "-"))
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل السلف: {e}")


    def _load_salaries(self):
        """تحميل المرتبات"""
        try:
            month = self.salary_month.currentText()
            salaries = self.hr_service.get_salaries(month=month)
            
            self.salaries_table.setRowCount(len(salaries))
            total_gross = 0
            total_deductions = 0
            total_net = 0
            
            for row, sal in enumerate(salaries):
                self.salaries_table.setItem(row, 0, QTableWidgetItem(sal.get("employee_name", "")))
                self.salaries_table.setItem(row, 1, QTableWidgetItem(f"{sal.get('basic_salary', 0):,.0f}"))
                self.salaries_table.setItem(row, 2, QTableWidgetItem(f"{sal.get('allowances', 0):,.0f}"))
                self.salaries_table.setItem(row, 3, QTableWidgetItem(f"{sal.get('overtime_amount', 0):,.0f}"))
                
                deductions = (sal.get('loan_deductions', 0) + sal.get('insurance_deduction', 0) + 
                             sal.get('tax_deduction', 0) + sal.get('other_deductions', 0))
                self.salaries_table.setItem(row, 4, QTableWidgetItem(f"{deductions:,.0f}"))
                self.salaries_table.setItem(row, 5, QTableWidgetItem(f"{sal.get('gross_salary', 0):,.0f}"))
                self.salaries_table.setItem(row, 6, QTableWidgetItem(f"{sal.get('net_salary', 0):,.0f}"))
                
                status_item = QTableWidgetItem(sal.get("payment_status", ""))
                if sal.get("payment_status") == "مدفوع":
                    status_item.setForeground(QColor("#22c55e"))
                else:
                    status_item.setForeground(QColor("#f59e0b"))
                self.salaries_table.setItem(row, 7, status_item)
                
                # زر الصرف
                if sal.get("payment_status") != "مدفوع":
                    pay_btn = QPushButton("💰")
                    pay_btn.setStyleSheet(BUTTON_STYLES["success"])
                    pay_btn.clicked.connect(lambda checked, s=sal: self._pay_salary(s))
                    self.salaries_table.setCellWidget(row, 8, pay_btn)
                else:
                    self.salaries_table.setItem(row, 8, QTableWidgetItem("✅"))
                
                total_gross += sal.get('gross_salary', 0)
                total_deductions += deductions
                total_net += sal.get('net_salary', 0)
            
            # تحديث الملخص
            self.salary_total_gross.setText(f"إجمالي: {total_gross:,.0f} ج.م")
            self.salary_total_deductions.setText(f"خصومات: {total_deductions:,.0f} ج.م")
            self.salary_total_net.setText(f"صافي: {total_net:,.0f} ج.م")
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل المرتبات: {e}")

    # ==================== الفلاتر ====================
    def _filter_employees(self, text: str):
        """فلترة الموظفين"""
        for row in range(self.employees_table.rowCount()):
            match = False
            for col in range(4):  # البحث في أول 4 أعمدة
                item = self.employees_table.item(row, col)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.employees_table.setRowHidden(row, not match)

    def _filter_leaves(self, status: str):
        """فلترة الإجازات"""
        self._load_leaves()

    def _filter_loans(self, status: str):
        """فلترة السلف"""
        self._load_loans()

    # ==================== إجراءات الموظفين ====================
    def _add_employee(self):
        """إضافة موظف جديد"""
        from ui.smart_employee_dialog import SmartEmployeeDialog
        dialog = SmartEmployeeDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_employee_data()
            result = self.hr_service.create_employee(data)
            if result:
                QMessageBox.information(self, "نجاح", "تم إضافة الموظف بنجاح")
                self.load_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل إضافة الموظف")

    def _edit_employee(self, employee: dict):
        """تعديل موظف"""
        from ui.smart_employee_dialog import SmartEmployeeDialog
        dialog = SmartEmployeeDialog(employee_data=employee, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_employee_data()
            result = self.hr_service.update_employee(employee["id"], data)
            if result:
                QMessageBox.information(self, "نجاح", "تم تحديث بيانات الموظف")
                self.load_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل تحديث بيانات الموظف")

    def _delete_employee(self, employee: dict):
        """حذف موظف"""
        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل أنت متأكد من حذف الموظف: {employee.get('name')}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.hr_service.delete_employee(employee["id"]):
                QMessageBox.information(self, "نجاح", "تم حذف الموظف")
                self.load_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل حذف الموظف")


    # ==================== إجراءات الحضور ====================
    def _record_check_in(self):
        """تسجيل حضور"""
        employees = self.hr_service.get_active_employees()
        if not employees:
            QMessageBox.warning(self, "تنبيه", "لا يوجد موظفين نشطين")
            return
        
        dialog = EmployeeSelectDialog(employees, "تسجيل حضور", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            employee_id = dialog.get_selected_employee_id()
            if employee_id:
                result = self.hr_service.check_in(employee_id)
                if result:
                    QMessageBox.information(self, "نجاح", "تم تسجيل الحضور")
                    self._load_attendance()
                else:
                    QMessageBox.warning(self, "خطأ", "فشل تسجيل الحضور")

    def _record_check_out(self):
        """تسجيل انصراف"""
        employees = self.hr_service.get_active_employees()
        if not employees:
            QMessageBox.warning(self, "تنبيه", "لا يوجد موظفين نشطين")
            return
        
        dialog = EmployeeSelectDialog(employees, "تسجيل انصراف", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            employee_id = dialog.get_selected_employee_id()
            if employee_id:
                result = self.hr_service.check_out(employee_id)
                if result:
                    QMessageBox.information(self, "نجاح", "تم تسجيل الانصراف")
                    self._load_attendance()
                else:
                    QMessageBox.warning(self, "خطأ", "فشل تسجيل الانصراف")

    # ==================== إجراءات الإجازات ====================
    def _add_leave_request(self):
        """طلب إجازة جديدة"""
        employees = self.hr_service.get_active_employees()
        if not employees:
            QMessageBox.warning(self, "تنبيه", "لا يوجد موظفين نشطين")
            return
        
        dialog = LeaveRequestDialog(employees, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            result = self.hr_service.request_leave(data)
            if result:
                QMessageBox.information(self, "نجاح", "تم تقديم طلب الإجازة")
                self.load_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل تقديم طلب الإجازة")

    def _approve_leave(self, leave: dict):
        """الموافقة على إجازة"""
        approver = self.current_user.username if self.current_user else "admin"
        if self.hr_service.approve_leave(leave["id"], approver):
            QMessageBox.information(self, "نجاح", "تمت الموافقة على الإجازة")
            self._load_leaves()
        else:
            QMessageBox.warning(self, "خطأ", "فشل الموافقة على الإجازة")

    def _reject_leave(self, leave: dict):
        """رفض إجازة"""
        approver = self.current_user.username if self.current_user else "admin"
        if self.hr_service.reject_leave(leave["id"], approver):
            QMessageBox.information(self, "نجاح", "تم رفض الإجازة")
            self._load_leaves()
        else:
            QMessageBox.warning(self, "خطأ", "فشل رفض الإجازة")

    # ==================== إجراءات السلف ====================
    def _add_loan(self):
        """إضافة سلفة جديدة"""
        employees = self.hr_service.get_active_employees()
        if not employees:
            QMessageBox.warning(self, "تنبيه", "لا يوجد موظفين نشطين")
            return
        
        dialog = LoanDialog(employees, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            result = self.hr_service.create_loan(data)
            if result:
                QMessageBox.information(self, "نجاح", "تم إنشاء السلفة")
                self.load_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل إنشاء السلفة")

    def _pay_loan_installment(self, loan: dict):
        """سداد قسط من السلفة"""
        amount, ok = self._get_amount_input("سداد قسط", "أدخل مبلغ السداد:", loan.get("monthly_deduction", 0))
        if ok and amount > 0:
            if self.hr_service.pay_loan_installment(loan["id"], amount):
                QMessageBox.information(self, "نجاح", "تم سداد القسط")
                self._load_loans()
            else:
                QMessageBox.warning(self, "خطأ", "فشل سداد القسط")

    def _get_amount_input(self, title: str, label: str, default: float = 0) -> tuple:
        """نافذة إدخال مبلغ"""
        from PyQt6.QtWidgets import QInputDialog
        amount, ok = QInputDialog.getDouble(self, title, label, default, 0, 1000000, 2)
        return amount, ok

    # ==================== إجراءات المرتبات ====================
    def _calculate_salaries(self):
        """حساب مرتبات الشهر"""
        month = self.salary_month.currentText()
        reply = QMessageBox.question(
            self, "تأكيد",
            f"هل تريد حساب مرتبات شهر {month}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            results = self.hr_service.calculate_all_salaries(month)
            QMessageBox.information(self, "نجاح", f"تم حساب {len(results)} راتب")
            self._load_salaries()

    def _pay_salary(self, salary: dict):
        """صرف راتب"""
        if self.hr_service.pay_salary(salary["id"]):
            QMessageBox.information(self, "نجاح", "تم صرف الراتب")
            self._load_salaries()
        else:
            QMessageBox.warning(self, "خطأ", "فشل صرف الراتب")

    def _pay_all_salaries(self):
        """صرف جميع المرتبات"""
        month = self.salary_month.currentText()
        salaries = self.hr_service.get_salaries(month=month)
        pending = [s for s in salaries if s.get("payment_status") != "مدفوع"]
        
        if not pending:
            QMessageBox.information(self, "معلومات", "جميع المرتبات مصروفة")
            return
        
        reply = QMessageBox.question(
            self, "تأكيد",
            f"هل تريد صرف {len(pending)} راتب؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = 0
            for sal in pending:
                if self.hr_service.pay_salary(sal["id"]):
                    count += 1
            QMessageBox.information(self, "نجاح", f"تم صرف {count} راتب")
            self._load_salaries()


# ==================== نوافذ مساعدة ====================

class EmployeeSelectDialog(QDialog):
    """نافذة اختيار موظف"""
    
    def __init__(self, employees: list, title: str, parent=None):
        super().__init__(parent)
        self.employees = employees
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)
        self.init_ui()
        self._apply_style()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QLabel("اختر الموظف:"))
        
        self.employee_combo = QComboBox()
        for emp in self.employees:
            self.employee_combo.addItem(f"{emp['name']} ({emp.get('employee_id', '')})", emp['id'])
        layout.addWidget(self.employee_combo)

        # أزرار
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ تأكيد")
        ok_btn.setStyleSheet(BUTTON_STYLES["success"])
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["danger"])
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog { background-color: #001a3a; color: #ffffff; }
            QLabel { color: #ffffff; font-size: 14px; }
            QComboBox { background-color: #002040; color: #ffffff; border: 2px solid #003366; 
                       border-radius: 6px; padding: 8px; }
        """)

    def get_selected_employee_id(self) -> int:
        return self.employee_combo.currentData()


class LeaveRequestDialog(QDialog):
    """نافذة طلب إجازة"""
    
    LEAVE_TYPES = ["سنوية", "مرضية", "طارئة", "بدون راتب", "أمومة", "أبوة", "حج", "زواج", "وفاة"]
    
    def __init__(self, employees: list, parent=None):
        super().__init__(parent)
        self.employees = employees
        self.setWindowTitle("طلب إجازة")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.init_ui()
        self._apply_style()

    def init_ui(self):
        layout = QFormLayout()
        self.setLayout(layout)

        # الموظف
        self.employee_combo = QComboBox()
        for emp in self.employees:
            self.employee_combo.addItem(f"{emp['name']}", emp['id'])
        layout.addRow("الموظف:", self.employee_combo)

        # نوع الإجازة
        self.leave_type = QComboBox()
        self.leave_type.addItems(self.LEAVE_TYPES)
        layout.addRow("نوع الإجازة:", self.leave_type)

        # من تاريخ
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        layout.addRow("من:", self.start_date)

        # إلى تاريخ
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        layout.addRow("إلى:", self.end_date)

        # السبب
        self.reason = QTextEdit()
        self.reason.setMaximumHeight(80)
        self.reason.setPlaceholderText("سبب الإجازة...")
        layout.addRow("السبب:", self.reason)

        # أزرار
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ تقديم")
        ok_btn.setStyleSheet(BUTTON_STYLES["success"])
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["danger"])
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow("", btn_layout)

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog { background-color: #001a3a; color: #ffffff; }
            QLabel { color: #ffffff; }
            QComboBox, QDateEdit, QTextEdit { 
                background-color: #002040; color: #ffffff; 
                border: 2px solid #003366; border-radius: 6px; padding: 6px; 
            }
        """)

    def get_data(self) -> dict:
        return {
            "employee_id": self.employee_combo.currentData(),
            "leave_type": self.leave_type.currentText(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date.date().toString("yyyy-MM-dd"),
            "reason": self.reason.toPlainText()
        }


class LoanDialog(QDialog):
    """نافذة إنشاء سلفة"""
    
    def __init__(self, employees: list, parent=None):
        super().__init__(parent)
        self.employees = employees
        self.setWindowTitle("سلفة جديدة")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.init_ui()
        self._apply_style()

    def init_ui(self):
        layout = QFormLayout()
        self.setLayout(layout)

        # الموظف
        self.employee_combo = QComboBox()
        for emp in self.employees:
            self.employee_combo.addItem(f"{emp['name']}", emp['id'])
        layout.addRow("الموظف:", self.employee_combo)

        # المبلغ
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 1000000)
        self.amount.setSuffix(" ج.م")
        layout.addRow("المبلغ:", self.amount)

        # القسط الشهري
        self.monthly = QDoubleSpinBox()
        self.monthly.setRange(0, 100000)
        self.monthly.setSuffix(" ج.م")
        layout.addRow("القسط الشهري:", self.monthly)

        # السبب
        self.reason = QTextEdit()
        self.reason.setMaximumHeight(80)
        self.reason.setPlaceholderText("سبب السلفة...")
        layout.addRow("السبب:", self.reason)

        # أزرار
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ إنشاء")
        ok_btn.setStyleSheet(BUTTON_STYLES["success"])
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["danger"])
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow("", btn_layout)

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog { background-color: #001a3a; color: #ffffff; }
            QLabel { color: #ffffff; }
            QComboBox, QDoubleSpinBox, QTextEdit { 
                background-color: #002040; color: #ffffff; 
                border: 2px solid #003366; border-radius: 6px; padding: 6px; 
            }
        """)

    def get_data(self) -> dict:
        return {
            "employee_id": self.employee_combo.currentData(),
            "amount": self.amount.value(),
            "monthly_deduction": self.monthly.value(),
            "reason": self.reason.toPlainText(),
            "start_date": datetime.now().strftime("%Y-%m-%d")
        }
