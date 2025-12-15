# الملف: ui/smart_employee_dialog.py
"""
🧠 نافذة إضافة/تعديل موظف ذكية - Production Grade
==================================================
ميزات ذكية:
- اقتراحات تلقائية للوظائف والأقسام
- حساب تلقائي للراتب حسب الوظيفة
- التحقق من صحة البيانات
- حفظ سريع بضغطة Enter
- دعم الرقم القومي والحساب البنكي
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox,
    QTextEdit, QPushButton, QLabel, QGroupBox, QCompleter,
    QTabWidget, QWidget, QScrollArea, QFrame
)
from datetime import datetime
import re

from ui.styles import BUTTON_STYLES
from ui.smart_combobox import SmartFilterComboBox


class SmartEmployeeDialog(QDialog):
    """نافذة ذكية لإضافة/تعديل موظف - Production Grade"""
    
    # قوائم ذكية للاقتراحات
    COMMON_POSITIONS = [
        "مدير عام", "مدير مبيعات", "مدير تسويق", "مدير محاسبة",
        "محاسب", "مندوب مبيعات", "موظف خدمة عملاء", "مهندس",
        "مبرمج", "مصمم جرافيك", "كاتب محتوى", "سكرتير",
        "موظف استقبال", "فني صيانة", "سائق", "عامل",
        "مدير موارد بشرية", "مدير مشاريع", "محلل بيانات"
    ]
    
    DEPARTMENTS = [
        "الإدارة", "المبيعات", "التسويق", "المحاسبة",
        "الموارد البشرية", "تكنولوجيا المعلومات", "خدمة العملاء",
        "الإنتاج", "الصيانة", "المشتريات", "المخازن", "الجودة"
    ]
    
    # رواتب تقريبية حسب الوظيفة (يمكن تعديلها)
    SALARY_SUGGESTIONS = {
        "مدير عام": 15000,
        "مدير مبيعات": 10000,
        "مدير تسويق": 9000,
        "مدير محاسبة": 8000,
        "مدير موارد بشرية": 8000,
        "مدير مشاريع": 9000,
        "محاسب": 5000,
        "مندوب مبيعات": 4000,
        "موظف خدمة عملاء": 3500,
        "مهندس": 7000,
        "مبرمج": 8000,
        "مصمم جرافيك": 5000,
        "محلل بيانات": 6000,
        "سكرتير": 3000,
        "موظف استقبال": 2500,
    }
    
    # البنوك المصرية
    BANKS = [
        "البنك الأهلي المصري", "بنك مصر", "بنك القاهرة",
        "البنك التجاري الدولي CIB", "بنك الإسكندرية",
        "بنك QNB الأهلي", "بنك HSBC", "البنك العربي الأفريقي",
        "بنك فيصل الإسلامي", "بنك الاستثمار العربي"
    ]
    
    def __init__(self, employee_data=None, parent=None):
        super().__init__(parent)
        self.employee_data = employee_data
        self.setWindowTitle("✏️ تعديل موظف" if employee_data else "➕ إضافة موظف جديد")
        self.setModal(True)
        
        # تصميم متجاوب - حد أدنى فقط
        self.setMinimumSize(750, 550)
        
        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass
        
        self.init_ui()
        
        if employee_data:
            self.load_employee_data()
        
        # تطبيق الستايل الداكن
        self.setStyleSheet("""
            QDialog {
                background-color: #001a3a;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QTextEdit {
                background-color: #002040;
                color: #ffffff;
                border: 2px solid #003366;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, 
            QDoubleSpinBox:focus, QTextEdit:focus {
                border: 2px solid #4a90e2;
            }
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
            QTabWidget::pane {
                border: 1px solid #003366;
                background-color: #001a3a;
            }
            QTabBar::tab {
                background-color: #002040;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #4a90e2;
            }
        """)
    
    def init_ui(self):
        """إنشاء واجهة المستخدم الذكية مع تابات"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # عنوان النافذة
        title = QLabel("📝 بيانات الموظف")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #4a90e2; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # تابات لتنظيم البيانات
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # تاب المعلومات الأساسية
        basic_tab = self._create_basic_tab()
        self.tabs.addTab(basic_tab, "📋 أساسية")
        
        # تاب معلومات الاتصال
        contact_tab = self._create_contact_tab()
        self.tabs.addTab(contact_tab, "📞 اتصال")
        
        # تاب المعلومات المالية
        financial_tab = self._create_financial_tab()
        self.tabs.addTab(financial_tab, "💰 مالية")
        
        # أزرار الحفظ والإلغاء
        buttons_layout = QHBoxLayout()
        
        self.save_button = QPushButton("💾 حفظ (Enter)")
        self.save_button.setStyleSheet(BUTTON_STYLES["success"])
        self.save_button.clicked.connect(self.accept)
        self.save_button.setDefault(True)
        
        self.cancel_button = QPushButton("❌ إلغاء (Esc)")
        self.cancel_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        
        layout.addLayout(buttons_layout)
        
        # تركيز على حقل الاسم
        self.name_input.setFocus()
    
    def _create_basic_tab(self):
        """تاب المعلومات الأساسية"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # معلومات أساسية
        basic_group = QGroupBox("📋 المعلومات الأساسية")
        basic_layout = QFormLayout()
        basic_group.setLayout(basic_layout)
        
        # الاسم
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("اسم الموظف الكامل (رباعي)")
        self.name_input.returnPressed.connect(self.accept)
        basic_layout.addRow("الاسم الكامل *:", self.name_input)
        
        # رقم الموظف (توليد تلقائي)
        self.employee_id_input = QLineEdit()
        self.employee_id_input.setPlaceholderText("سيتم التوليد تلقائياً")
        if not self.employee_data:
            self.employee_id_input.setText(self._generate_employee_id())
        basic_layout.addRow("رقم الموظف *:", self.employee_id_input)
        
        # الرقم القومي
        self.national_id_input = QLineEdit()
        self.national_id_input.setPlaceholderText("الرقم القومي (14 رقم)")
        self.national_id_input.setMaxLength(14)
        self.national_id_input.textChanged.connect(self._validate_national_id)
        basic_layout.addRow("الرقم القومي:", self.national_id_input)
        
        # الوظيفة (SmartFilterComboBox مع فلترة)
        self.position_input = SmartFilterComboBox()
        for pos in [""] + self.COMMON_POSITIONS:
            self.position_input.addItem(pos)
        self.position_input.setCurrentText("")
        self.position_input.currentTextChanged.connect(self._on_position_changed)
        basic_layout.addRow("الوظيفة *:", self.position_input)
        
        # القسم (SmartFilterComboBox مع فلترة)
        self.department_input = SmartFilterComboBox()
        for dept in [""] + self.DEPARTMENTS:
            self.department_input.addItem(dept)
        self.department_input.setCurrentText("")
        basic_layout.addRow("القسم:", self.department_input)
        
        # تاريخ التعيين
        self.hire_date_input = QDateEdit()
        self.hire_date_input.setDate(datetime.now().date())
        self.hire_date_input.setCalendarPopup(True)
        self.hire_date_input.setDisplayFormat("yyyy-MM-dd")
        basic_layout.addRow("تاريخ التعيين:", self.hire_date_input)
        
        # الحالة
        self.status_input = QComboBox()
        self.status_input.addItems(["نشط", "غير نشط", "إجازة", "مستقيل", "تحت التجربة"])
        basic_layout.addRow("الحالة:", self.status_input)
        
        layout.addWidget(basic_group)
        
        # ملاحظات
        notes_group = QGroupBox("📝 ملاحظات")
        notes_layout = QVBoxLayout()
        notes_group.setLayout(notes_layout)
        
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات إضافية عن الموظف...")
        self.notes_input.setMaximumHeight(100)
        notes_layout.addWidget(self.notes_input)
        
        layout.addWidget(notes_group)
        layout.addStretch()
        
        return widget
    
    def _create_contact_tab(self):
        """تاب معلومات الاتصال"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # معلومات الاتصال
        contact_group = QGroupBox("📞 معلومات الاتصال")
        contact_layout = QFormLayout()
        contact_group.setLayout(contact_layout)
        
        # الهاتف
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("01XXXXXXXXX")
        self.phone_input.setMaxLength(11)
        self.phone_input.textChanged.connect(self._validate_phone)
        contact_layout.addRow("الهاتف:", self.phone_input)
        
        # هاتف احتياطي
        self.phone2_input = QLineEdit()
        self.phone2_input.setPlaceholderText("رقم هاتف احتياطي (اختياري)")
        self.phone2_input.setMaxLength(11)
        contact_layout.addRow("هاتف احتياطي:", self.phone2_input)
        
        # البريد الإلكتروني
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("employee@company.com")
        self.email_input.textChanged.connect(self._validate_email)
        contact_layout.addRow("البريد الإلكتروني:", self.email_input)
        
        layout.addWidget(contact_group)
        
        # العنوان
        address_group = QGroupBox("🏠 العنوان")
        address_layout = QVBoxLayout()
        address_group.setLayout(address_layout)
        
        self.address_input = QTextEdit()
        self.address_input.setPlaceholderText("العنوان الكامل (الشارع، المنطقة، المدينة، المحافظة)")
        self.address_input.setMaximumHeight(80)
        address_layout.addWidget(self.address_input)
        
        layout.addWidget(address_group)
        layout.addStretch()
        
        return widget
    
    def _create_financial_tab(self):
        """تاب المعلومات المالية"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # معلومات الراتب
        salary_group = QGroupBox("💵 الراتب")
        salary_layout = QFormLayout()
        salary_group.setLayout(salary_layout)
        
        # الراتب (مع اقتراح تلقائي)
        salary_row = QHBoxLayout()
        self.salary_input = QDoubleSpinBox()
        self.salary_input.setRange(0, 1000000)
        self.salary_input.setSuffix(" جنيه")
        self.salary_input.setDecimals(2)
        salary_row.addWidget(self.salary_input)
        
        self.suggest_salary_btn = QPushButton("💡 اقتراح")
        self.suggest_salary_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.suggest_salary_btn.setMaximumWidth(100)
        self.suggest_salary_btn.clicked.connect(self._suggest_salary)
        salary_row.addWidget(self.suggest_salary_btn)
        
        salary_layout.addRow("الراتب الأساسي:", salary_row)
        
        layout.addWidget(salary_group)
        
        # معلومات البنك
        bank_group = QGroupBox("🏦 الحساب البنكي")
        bank_layout = QFormLayout()
        bank_group.setLayout(bank_layout)
        
        # البنك (SmartFilterComboBox مع فلترة)
        self.bank_name_input = SmartFilterComboBox()
        for bank in [""] + self.BANKS:
            self.bank_name_input.addItem(bank)
        self.bank_name_input.setCurrentText("")
        bank_layout.addRow("اسم البنك:", self.bank_name_input)
        
        # رقم الحساب
        self.bank_account_input = QLineEdit()
        self.bank_account_input.setPlaceholderText("رقم الحساب البنكي")
        bank_layout.addRow("رقم الحساب:", self.bank_account_input)
        
        # ملاحظة
        bank_note = QLabel("💡 يُستخدم لتحويل الراتب الشهري")
        bank_note.setStyleSheet("color: #888; font-size: 11px; padding: 5px;")
        bank_layout.addRow("", bank_note)
        
        layout.addWidget(bank_group)
        layout.addStretch()
        
        return widget
    
    def _validate_national_id(self, text):
        """التحقق من صحة الرقم القومي"""
        if text and len(text) == 14 and text.isdigit():
            self.national_id_input.setStyleSheet("border: 2px solid #22c55e;")
        elif text:
            self.national_id_input.setStyleSheet("border: 2px solid #ef4444;")
        else:
            self.national_id_input.setStyleSheet("")
    
    def _validate_phone(self, text):
        """التحقق من صحة رقم الهاتف"""
        if text and re.match(r'^01[0125]\d{8}$', text):
            self.phone_input.setStyleSheet("border: 2px solid #22c55e;")
        elif text:
            self.phone_input.setStyleSheet("border: 2px solid #ef4444;")
        else:
            self.phone_input.setStyleSheet("")
    
    def _validate_email(self, text):
        """التحقق من صحة البريد الإلكتروني"""
        if text and re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', text):
            self.email_input.setStyleSheet("border: 2px solid #22c55e;")
        elif text:
            self.email_input.setStyleSheet("border: 2px solid #ef4444;")
        else:
            self.email_input.setStyleSheet("")
    
    def _generate_employee_id(self):
        """توليد رقم موظف تلقائي"""
        import sqlite3
        try:
            conn = sqlite3.connect('skywave_local.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM employees")
            count = cursor.fetchone()[0]
            conn.close()
            return f"EMP{count + 1:04d}"
        except:
            return f"EMP{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    def _on_position_changed(self, position):
        """عند تغيير الوظيفة - اقتراح راتب تلقائي"""
        if position in self.SALARY_SUGGESTIONS:
            suggested_salary = self.SALARY_SUGGESTIONS[position]
            # عرض اقتراح بدون تغيير القيمة الحالية
            self.suggest_salary_btn.setToolTip(f"الراتب المقترح: {suggested_salary} جنيه")
    
    def _suggest_salary(self):
        """اقتراح راتب حسب الوظيفة"""
        position = self.position_input.currentText()
        if position in self.SALARY_SUGGESTIONS:
            self.salary_input.setValue(self.SALARY_SUGGESTIONS[position])
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "معلومات",
                "لا يوجد اقتراح راتب لهذه الوظيفة.\nيمكنك إدخال الراتب يدوياً."
            )
    
    def load_employee_data(self):
        """تحميل بيانات الموظف للتعديل"""
        if not self.employee_data:
            return
        
        # المعلومات الأساسية
        self.name_input.setText(self.employee_data.get("name", ""))
        self.employee_id_input.setText(self.employee_data.get("employee_id", ""))
        self.national_id_input.setText(self.employee_data.get("national_id", ""))
        self.position_input.setCurrentText(self.employee_data.get("position", ""))
        self.department_input.setCurrentText(self.employee_data.get("department", ""))
        self.status_input.setCurrentText(self.employee_data.get("status", "نشط"))
        self.notes_input.setPlainText(self.employee_data.get("notes", ""))
        
        # معلومات الاتصال
        self.phone_input.setText(self.employee_data.get("phone", ""))
        self.email_input.setText(self.employee_data.get("email", ""))
        self.address_input.setPlainText(self.employee_data.get("address", ""))
        
        # المعلومات المالية
        self.salary_input.setValue(float(self.employee_data.get("salary", 0) or 0))
        
        # الحساب البنكي
        bank_account = self.employee_data.get("bank_account", "")
        if bank_account:
            # محاولة فصل اسم البنك عن رقم الحساب
            if " - " in bank_account:
                parts = bank_account.split(" - ", 1)
                self.bank_name_input.setCurrentText(parts[0])
                self.bank_account_input.setText(parts[1] if len(parts) > 1 else "")
            else:
                self.bank_account_input.setText(bank_account)
        
        # تحميل تاريخ التعيين
        hire_date = self.employee_data.get("hire_date")
        if hire_date:
            try:
                from PyQt6.QtCore import QDate
                date_obj = datetime.strptime(hire_date, "%Y-%m-%d")
                self.hire_date_input.setDate(QDate(date_obj.year, date_obj.month, date_obj.day))
            except:
                pass
    
    def get_employee_data(self):
        """الحصول على بيانات الموظف"""
        # تجميع معلومات البنك
        bank_name = self.bank_name_input.currentText().strip()
        bank_account = self.bank_account_input.text().strip()
        full_bank_info = f"{bank_name} - {bank_account}" if bank_name and bank_account else bank_account
        
        return {
            "name": self.name_input.text().strip(),
            "employee_id": self.employee_id_input.text().strip(),
            "national_id": self.national_id_input.text().strip(),
            "position": self.position_input.currentText().strip(),
            "department": self.department_input.currentText().strip(),
            "phone": self.phone_input.text().strip(),
            "email": self.email_input.text().strip(),
            "address": self.address_input.toPlainText().strip(),
            "hire_date": self.hire_date_input.date().toString("yyyy-MM-dd"),
            "salary": self.salary_input.value(),
            "status": self.status_input.currentText(),
            "bank_account": full_bank_info,
            "notes": self.notes_input.toPlainText().strip(),
        }
    
    def accept(self):
        """التحقق من البيانات قبل الحفظ"""
        from PyQt6.QtWidgets import QMessageBox
        
        # التحقق من الاسم
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "تحذير", "يرجى إدخال اسم الموظف")
            self.tabs.setCurrentIndex(0)
            self.name_input.setFocus()
            return
        
        # التحقق من رقم الموظف
        if not self.employee_id_input.text().strip():
            QMessageBox.warning(self, "تحذير", "يرجى إدخال رقم الموظف")
            self.tabs.setCurrentIndex(0)
            self.employee_id_input.setFocus()
            return
        
        # التحقق من الوظيفة
        if not self.position_input.currentText().strip():
            QMessageBox.warning(self, "تحذير", "يرجى إدخال الوظيفة")
            self.tabs.setCurrentIndex(0)
            self.position_input.setFocus()
            return
        
        # التحقق من الرقم القومي (إذا تم إدخاله)
        national_id = self.national_id_input.text().strip()
        if national_id and (len(national_id) != 14 or not national_id.isdigit()):
            QMessageBox.warning(self, "تحذير", "الرقم القومي يجب أن يكون 14 رقم")
            self.tabs.setCurrentIndex(0)
            self.national_id_input.setFocus()
            return
        
        # التحقق من رقم الهاتف (إذا تم إدخاله)
        phone = self.phone_input.text().strip()
        if phone and not re.match(r'^01[0125]\d{8}$', phone):
            QMessageBox.warning(self, "تحذير", "رقم الهاتف غير صحيح (يجب أن يبدأ بـ 01)")
            self.tabs.setCurrentIndex(1)
            self.phone_input.setFocus()
            return
        
        # التحقق من البريد الإلكتروني (إذا تم إدخاله)
        email = self.email_input.text().strip()
        if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            QMessageBox.warning(self, "تحذير", "البريد الإلكتروني غير صحيح")
            self.tabs.setCurrentIndex(1)
            self.email_input.setFocus()
            return
        
        # التحقق من الراتب
        if self.salary_input.value() <= 0:
            reply = QMessageBox.question(
                self, "تأكيد",
                "الراتب صفر أو غير محدد. هل تريد المتابعة؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                self.tabs.setCurrentIndex(2)
                self.salary_input.setFocus()
                return
        
        super().accept()
