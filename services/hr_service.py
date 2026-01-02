# الملف: services/hr_service.py
"""
🏢 خدمة الموارد البشرية المتكاملة - Production Grade
====================================================
تدير جميع عمليات HR مع ربط كامل بالمحاسبة:
- إدارة الموظفين
- السلف والقروض (مع قيود محاسبية)
- المرتبات (مع قيود محاسبية)
- الحضور والإجازات
"""

import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from core.logger import get_logger

# إشعارات العمليات
try:
    from core.notification_bridge import notify_operation
except ImportError:
    def notify_operation(action, entity_type, entity_name): pass

logger = get_logger(__name__)


class HRService:
    """خدمة الموارد البشرية المتكاملة مع المحاسبة"""
    
    # أكواد الحسابات المحاسبية للموارد البشرية (نظام 6 أرقام)
    ACC_EMPLOYEE_LOANS = "113100"        # سلف الموظفين (أصل - مدين)
    ACC_CASH = "111101"                  # الخزنة الرئيسية
    ACC_BANK = "111201"                  # البنك
    ACC_SALARIES_EXPENSE = "620001"      # مصروف الرواتب
    ACC_SALARIES_PAYABLE = "212300"      # رواتب مستحقة (التزام)
    ACC_INSURANCE_PAYABLE = "212400"     # تأمينات مستحقة
    ACC_TAX_PAYABLE = "212200"           # ضرائب مستحقة
    ACC_ALLOWANCES_EXPENSE = "620002"    # مصروف البدلات
    ACC_BONUSES_EXPENSE = "620003"       # مصروف الحوافز
    
    def __init__(self, db_path: str = 'skywave_local.db'):
        """تهيئة خدمة الموارد البشرية"""
        self.db_path = db_path
        self._ensure_tables()
        self._ensure_hr_accounts()
        logger.info("✅ خدمة الموارد البشرية جاهزة")
    
    def _get_connection(self) -> sqlite3.Connection:
        """الحصول على اتصال بقاعدة البيانات"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_tables(self):
        """التأكد من وجود جداول الموارد البشرية"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # إضافة الأعمدة المفقودة لجدول القيود المحاسبية
        try:
            cursor.execute("ALTER TABLE journal_entries ADD COLUMN reference_type TEXT")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE journal_entries ADD COLUMN reference_id TEXT")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE journal_entries ADD COLUMN total_debit REAL DEFAULT 0")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE journal_entries ADD COLUMN total_credit REAL DEFAULT 0")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE journal_entries ADD COLUMN is_balanced INTEGER DEFAULT 1")
        except:
            pass
        
        # جدول الموظفين
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE,
                name TEXT NOT NULL,
                position TEXT,
                department TEXT,
                salary REAL DEFAULT 0,
                phone TEXT,
                email TEXT,
                address TEXT,
                national_id TEXT,
                bank_account TEXT,
                hire_date TEXT,
                status TEXT DEFAULT 'نشط',
                notes TEXT,
                created_at TEXT,
                last_modified TEXT,
                sync_status TEXT DEFAULT 'pending',
                mongo_id TEXT
            )
        """)
        
        # جدول السلف
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                loan_type TEXT DEFAULT 'سلفة',
                amount REAL NOT NULL,
                remaining_amount REAL NOT NULL,
                monthly_deduction REAL DEFAULT 0,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'نشط',
                reason TEXT,
                approved_by TEXT,
                payment_method TEXT DEFAULT 'cash',
                journal_entry_id TEXT,
                notes TEXT,
                created_at TEXT,
                last_modified TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
        """)
        
        # جدول أقساط السلف
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loan_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payment_date TEXT,
                payment_method TEXT DEFAULT 'salary_deduction',
                journal_entry_id TEXT,
                notes TEXT,
                created_at TEXT,
                FOREIGN KEY (loan_id) REFERENCES employee_loans(id),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
        """)
        
        # جدول المرتبات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_salaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                basic_salary REAL DEFAULT 0,
                allowances REAL DEFAULT 0,
                bonuses REAL DEFAULT 0,
                overtime_hours REAL DEFAULT 0,
                overtime_rate REAL DEFAULT 0,
                overtime_amount REAL DEFAULT 0,
                loan_deductions REAL DEFAULT 0,
                insurance_deduction REAL DEFAULT 0,
                tax_deduction REAL DEFAULT 0,
                other_deductions REAL DEFAULT 0,
                gross_salary REAL DEFAULT 0,
                net_salary REAL DEFAULT 0,
                payment_status TEXT DEFAULT 'معلق',
                payment_date TEXT,
                payment_method TEXT,
                journal_entry_id TEXT,
                notes TEXT,
                created_at TEXT,
                last_modified TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                UNIQUE(employee_id, month)
            )
        """)
        
        # جدول الحضور
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                check_in_time TEXT,
                check_out_time TEXT,
                work_hours REAL DEFAULT 0,
                overtime_hours REAL DEFAULT 0,
                status TEXT DEFAULT 'حاضر',
                notes TEXT,
                created_at TEXT,
                last_modified TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                UNIQUE(employee_id, date)
            )
        """)
        
        # جدول الإجازات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_leaves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                leave_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                days_count INTEGER DEFAULT 1,
                reason TEXT,
                status TEXT DEFAULT 'قيد المراجعة',
                approved_by TEXT,
                approval_date TEXT,
                notes TEXT,
                created_at TEXT,
                last_modified TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ تم التأكد من وجود جداول الموارد البشرية")
    
    def _ensure_hr_accounts(self):
        """التأكد من وجود الحسابات المحاسبية للموارد البشرية - معطلة مؤقتاً"""
        # ⚡ تم تعطيل الإنشاء التلقائي للحسابات - سيتم إضافتها يدوياً لاحقاً
        pass
    
    # ==================== إدارة الموظفين ====================
    
    def get_all_employees(self, status_filter: str = None) -> List[Dict]:
        """جلب جميع الموظفين"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT id, employee_id, name, position, department, salary,
                   phone, email, hire_date, status, address, national_id,
                   bank_account, notes, created_at
            FROM employees
        """
        
        if status_filter:
            query += " WHERE status = ? ORDER BY name"
            cursor.execute(query, (status_filter,))
        else:
            cursor.execute(query + " ORDER BY name")
        
        employees = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return employees
    
    def get_employee_by_id(self, employee_id: int) -> Optional[Dict]:
        """جلب موظف بالـ ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM employees WHERE id = ?
        """, (employee_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def save_employee(self, employee_data: Dict) -> Tuple[bool, str]:
        """حفظ أو تحديث موظف"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            if employee_data.get('id'):
                cursor.execute("""
                    UPDATE employees SET
                        name=?, employee_id=?, position=?, department=?,
                        phone=?, email=?, address=?, salary=?, status=?,
                        hire_date=?, national_id=?, bank_account=?, notes=?,
                        last_modified=?, sync_status='pending'
                    WHERE id=?
                """, (
                    employee_data['name'], employee_data.get('employee_id'),
                    employee_data.get('position'), employee_data.get('department'),
                    employee_data.get('phone'), employee_data.get('email'),
                    employee_data.get('address'), employee_data.get('salary', 0),
                    employee_data.get('status', 'نشط'), employee_data.get('hire_date'),
                    employee_data.get('national_id'), employee_data.get('bank_account'),
                    employee_data.get('notes'), now, employee_data['id']
                ))
                msg = f"تم تحديث الموظف: {employee_data['name']}"
                action = 'updated'
            else:
                cursor.execute("""
                    INSERT INTO employees (
                        name, employee_id, position, department, phone, email,
                        address, salary, status, hire_date, national_id, bank_account,
                        notes, created_at, last_modified, sync_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    employee_data['name'], employee_data.get('employee_id'),
                    employee_data.get('position'), employee_data.get('department'),
                    employee_data.get('phone'), employee_data.get('email'),
                    employee_data.get('address'), employee_data.get('salary', 0),
                    employee_data.get('status', 'نشط'), employee_data.get('hire_date'),
                    employee_data.get('national_id'), employee_data.get('bank_account'),
                    employee_data.get('notes'), now, now, 'pending'
                ))
                employee_data['id'] = cursor.lastrowid
                msg = f"تم إضافة الموظف: {employee_data['name']}"
                action = 'created'
            
            conn.commit()
            conn.close()
            # 🔔 إشعار
            notify_operation(action, 'employee', employee_data['name'])
            logger.info(f"✅ {msg}")
            return True, msg
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في حفظ الموظف: {e}")
            return False, str(e)
    
    def delete_employee(self, employee_id: int) -> Tuple[bool, str]:
        """حذف موظف"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # جلب اسم الموظف قبل الحذف
        employee = self.get_employee_by_id(employee_id)
        employee_name = employee['name'] if employee else f"موظف #{employee_id}"
        
        # التحقق من عدم وجود سلف نشطة
        cursor.execute("""
            SELECT COUNT(*) FROM employee_loans 
            WHERE employee_id = ? AND status = 'نشط'
        """, (employee_id,))
        
        active_loans = cursor.fetchone()[0]
        if active_loans > 0:
            conn.close()
            return False, f"لا يمكن حذف الموظف - لديه {active_loans} سلفة نشطة"
        
        try:
            # حذف البيانات المرتبطة
            cursor.execute("DELETE FROM employee_loans WHERE employee_id = ?", (employee_id,))
            cursor.execute("DELETE FROM employee_salaries WHERE employee_id = ?", (employee_id,))
            cursor.execute("DELETE FROM employee_attendance WHERE employee_id = ?", (employee_id,))
            cursor.execute("DELETE FROM employee_leaves WHERE employee_id = ?", (employee_id,))
            cursor.execute("DELETE FROM loan_payments WHERE employee_id = ?", (employee_id,))
            cursor.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
            
            conn.commit()
            conn.close()
            # 🔔 إشعار
            notify_operation('deleted', 'employee', employee_name)
            logger.info(f"✅ تم حذف الموظف: {employee_id}")
            return True, "تم حذف الموظف بنجاح"
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في حذف الموظف: {e}")
            return False, str(e)
    
    # ==================== إدارة السلف ====================
    
    def get_employee_loans(self, employee_id: int = None, status: str = None) -> List[Dict]:
        """جلب السلف"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT l.*, e.name as employee_name
            FROM employee_loans l
            JOIN employees e ON l.employee_id = e.id
            WHERE 1=1
        """
        params = []
        
        if employee_id:
            query += " AND l.employee_id = ?"
            params.append(employee_id)
        
        if status:
            query += " AND l.status = ?"
            params.append(status)
        
        query += " ORDER BY l.created_at DESC"
        
        cursor.execute(query, params)
        loans = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return loans
    
    def get_all_active_loans(self) -> List[Dict]:
        """جلب جميع السلف النشطة"""
        return self.get_employee_loans(status='نشط')

    def add_loan(self, loan_data: Dict, create_journal_entry: bool = True) -> Tuple[bool, str, int]:
        """
        إضافة سلفة جديدة مع إنشاء قيد محاسبي
        
        القيد المحاسبي:
        - مدين: سلف الموظفين (أصل يزيد)
        - دائن: الخزنة/البنك (أصل ينقص)
        
        Returns:
            Tuple[success, message, loan_id]
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        start_date = loan_data.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        
        try:
            # حفظ السلفة
            cursor.execute("""
                INSERT INTO employee_loans (
                    employee_id, loan_type, amount, remaining_amount,
                    monthly_deduction, start_date, status, reason,
                    approved_by, payment_method, notes, created_at, last_modified, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                loan_data['employee_id'],
                loan_data.get('loan_type', 'سلفة'),
                loan_data['amount'],
                loan_data['amount'],
                loan_data.get('monthly_deduction', 0),
                start_date,
                'نشط',
                loan_data.get('reason', ''),
                loan_data.get('approved_by', ''),
                loan_data.get('payment_method', 'cash'),
                loan_data.get('notes', ''),
                now, now, 'pending'
            ))
            
            loan_id = cursor.lastrowid
            conn.commit()
            
            # إنشاء القيد المحاسبي
            if create_journal_entry:
                journal_id = self._create_loan_journal_entry(
                    conn, cursor, loan_id,
                    loan_data['employee_id'],
                    loan_data['amount'],
                    loan_data.get('loan_type', 'سلفة'),
                    loan_data.get('payment_method', 'cash')
                )
                
                # تحديث السلفة برقم القيد
                cursor.execute("""
                    UPDATE employee_loans SET journal_entry_id = ? WHERE id = ?
                """, (journal_id, loan_id))
                conn.commit()
            
            conn.close()
            
            employee = self.get_employee_by_id(loan_data['employee_id'])
            employee_name = employee['name'] if employee else f"موظف #{loan_data['employee_id']}"
            
            # 🔔 إشعار
            notify_operation('created', 'loan', f"سلفة {loan_data['amount']} ج.م - {employee_name}")
            logger.info(f"✅ تم إضافة سلفة بمبلغ {loan_data['amount']} للموظف {employee_name}")
            return True, f"تم إضافة السلفة بنجاح للموظف {employee_name}", loan_id
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في إضافة السلفة: {e}")
            return False, str(e), 0
    
    def _create_loan_journal_entry(self, conn, cursor, loan_id: int, employee_id: int, 
                                    amount: float, loan_type: str, payment_method: str = 'cash') -> str:
        """إنشاء قيد محاسبي للسلفة"""
        employee = self.get_employee_by_id(employee_id)
        employee_name = employee['name'] if employee else f"موظف #{employee_id}"
        
        payment_account = self.ACC_CASH if payment_method == 'cash' else self.ACC_BANK
        now = datetime.now().isoformat()
        
        # إنشاء قيد اليومية
        import json
        lines = [
            {"account_code": self.ACC_EMPLOYEE_LOANS, "account_name": "سلف الموظفين", "debit": amount, "credit": 0},
            {"account_code": payment_account, "account_name": "الخزنة" if payment_method == 'cash' else "البنك", "debit": 0, "credit": amount}
        ]
        
        cursor.execute("""
            INSERT INTO journal_entries (
                date, description, lines, reference_type, reference_id,
                total_debit, total_credit, is_balanced,
                created_at, last_modified, sync_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime('%Y-%m-%d'),
            f"سلفة {loan_type} للموظف: {employee_name}",
            json.dumps(lines, ensure_ascii=False),
            "loan",
            f"LOAN-{loan_id}",
            amount, amount, 1,
            now, now, 'pending'
        ))
        
        journal_id = f"JE-{cursor.lastrowid}"
        
        # تحديث أرصدة الحسابات
        self._update_account_balance(cursor, self.ACC_EMPLOYEE_LOANS, amount, 0)
        self._update_account_balance(cursor, payment_account, 0, amount)
        
        logger.info(f"✅ تم إنشاء قيد محاسبي للسلفة #{loan_id}")
        return journal_id
    
    def _update_account_balance(self, cursor, account_code: str, debit: float, credit: float):
        """تحديث رصيد حساب"""
        # جلب نوع الحساب والرصيد الحالي
        cursor.execute("SELECT type, balance FROM accounts WHERE code = ?", (account_code,))
        row = cursor.fetchone()
        
        if not row:
            logger.warning(f"الحساب {account_code} غير موجود")
            return
        
        acc_type = row[0]
        current_balance = row[1] or 0
        
        # حساب الرصيد الجديد حسب طبيعة الحساب (القيم بالعربية)
        # الأصول والمصروفات: مدين بطبيعته (الرصيد = مدين - دائن)
        # الخصوم والإيرادات: دائن بطبيعته (الرصيد = دائن - مدين)
        debit_types = ('أصول', 'أصول نقدية', 'مصروفات', 'ASSET', 'CASH', 'EXPENSE')
        if acc_type in debit_types:
            new_balance = current_balance + debit - credit
        else:
            new_balance = current_balance + credit - debit
        
        cursor.execute("""
            UPDATE accounts SET balance = ?, last_modified = ? WHERE code = ?
        """, (new_balance, datetime.now().isoformat(), account_code))
    
    def pay_loan_installment(self, loan_id: int, amount: float, payment_method: str = 'salary_deduction') -> Tuple[bool, str]:
        """
        دفع قسط من السلفة
        
        القيد المحاسبي:
        - مدين: الخزنة/البنك (أصل يزيد)
        - دائن: سلف الموظفين (أصل ينقص)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # جلب بيانات السلفة
        cursor.execute("SELECT * FROM employee_loans WHERE id = ?", (loan_id,))
        loan = cursor.fetchone()
        
        if not loan:
            conn.close()
            return False, "السلفة غير موجودة"
        
        loan = dict(loan)
        
        if loan['status'] != 'نشط':
            conn.close()
            return False, "السلفة غير نشطة"
        
        if amount > loan['remaining_amount']:
            conn.close()
            return False, f"المبلغ أكبر من المتبقي ({loan['remaining_amount']})"
        
        now = datetime.now().isoformat()
        
        try:
            # تسجيل الدفعة
            cursor.execute("""
                INSERT INTO loan_payments (
                    loan_id, employee_id, amount, payment_date, payment_method, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (loan_id, loan['employee_id'], amount, datetime.now().strftime('%Y-%m-%d'), payment_method, now))
            
            # تحديث المبلغ المتبقي
            new_remaining = loan['remaining_amount'] - amount
            new_status = 'مكتمل' if new_remaining <= 0 else 'نشط'
            
            cursor.execute("""
                UPDATE employee_loans SET 
                    remaining_amount = ?, status = ?, last_modified = ?
                WHERE id = ?
            """, (new_remaining, new_status, now, loan_id))
            
            # إنشاء قيد محاسبي عكسي
            import json
            payment_account = self.ACC_CASH if payment_method == 'cash' else self.ACC_BANK
            
            employee = self.get_employee_by_id(loan['employee_id'])
            employee_name = employee['name'] if employee else f"موظف #{loan['employee_id']}"
            
            lines = [
                {"account_code": payment_account, "account_name": "الخزنة" if payment_method == 'cash' else "البنك", "debit": amount, "credit": 0},
                {"account_code": self.ACC_EMPLOYEE_LOANS, "account_name": "سلف الموظفين", "debit": 0, "credit": amount}
            ]
            
            cursor.execute("""
                INSERT INTO journal_entries (
                    date, description, lines, reference_type, reference_id,
                    total_debit, total_credit, is_balanced,
                    created_at, last_modified, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime('%Y-%m-%d'),
                f"سداد قسط سلفة للموظف: {employee_name}",
                json.dumps(lines, ensure_ascii=False),
                "loan_payment",
                f"LOAN-PAY-{loan_id}",
                amount, amount, 1,
                now, now, 'pending'
            ))
            
            # تحديث أرصدة الحسابات
            self._update_account_balance(cursor, payment_account, amount, 0)
            self._update_account_balance(cursor, self.ACC_EMPLOYEE_LOANS, 0, amount)
            
            conn.commit()
            conn.close()
            
            msg = f"تم سداد {amount} ج.م من السلفة. المتبقي: {new_remaining} ج.م"
            if new_status == 'مكتمل':
                msg += " - تم إغلاق السلفة"
            
            logger.info(f"✅ {msg}")
            return True, msg
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في سداد القسط: {e}")
            return False, str(e)
    
    def close_loan(self, loan_id: int, reason: str = "إغلاق يدوي") -> Tuple[bool, str]:
        """إغلاق سلفة"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE employee_loans SET 
                status = 'ملغي', notes = COALESCE(notes, '') || ' | ' || ?, last_modified = ?
            WHERE id = ?
        """, (reason, datetime.now().isoformat(), loan_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ تم إغلاق السلفة #{loan_id}")
        return True, "تم إغلاق السلفة بنجاح"
    
    def get_loan_payments(self, loan_id: int) -> List[Dict]:
        """جلب أقساط سلفة معينة"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM loan_payments WHERE loan_id = ? ORDER BY payment_date DESC
        """, (loan_id,))
        
        payments = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return payments

    # ==================== إدارة المرتبات ====================
    
    def calculate_salary(self, employee_id: int, month: str, 
                         allowances: float = 0, bonuses: float = 0,
                         overtime_hours: float = 0, overtime_rate: float = 0,
                         other_deductions: float = 0) -> Tuple[bool, str, Dict]:
        """
        حساب راتب موظف لشهر معين
        
        Returns:
            Tuple[success, message, salary_data]
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # جلب بيانات الموظف
        employee = self.get_employee_by_id(employee_id)
        if not employee:
            conn.close()
            return False, "الموظف غير موجود", {}
        
        basic_salary = employee.get('salary', 0) or 0
        
        # فحص إذا كان الراتب محسوب بالفعل
        cursor.execute("""
            SELECT id FROM employee_salaries WHERE employee_id = ? AND month = ?
        """, (employee_id, month))
        
        existing = cursor.fetchone()
        
        # حساب خصم السلف
        cursor.execute("""
            SELECT COALESCE(SUM(monthly_deduction), 0)
            FROM employee_loans
            WHERE employee_id = ? AND status = 'نشط'
        """, (employee_id,))
        loan_deductions = cursor.fetchone()[0]
        
        # حساب البدلات (افتراضي 10% إذا لم يتم تحديدها)
        if allowances == 0:
            allowances = basic_salary * 0.10
        
        # حساب الإضافي
        overtime_amount = overtime_hours * overtime_rate
        
        # حساب التأمين (5% من الراتب الأساسي)
        insurance_deduction = basic_salary * 0.05
        
        # حساب الضرائب (10% إذا الراتب أكبر من 5000)
        tax_deduction = basic_salary * 0.10 if basic_salary > 5000 else 0
        
        # حساب الإجمالي والصافي
        gross_salary = basic_salary + allowances + bonuses + overtime_amount
        total_deductions = loan_deductions + insurance_deduction + tax_deduction + other_deductions
        net_salary = gross_salary - total_deductions
        
        now = datetime.now().isoformat()
        
        try:
            if existing:
                # تحديث الراتب الموجود
                cursor.execute("""
                    UPDATE employee_salaries SET
                        basic_salary=?, allowances=?, bonuses=?,
                        overtime_hours=?, overtime_rate=?, overtime_amount=?,
                        loan_deductions=?, insurance_deduction=?, tax_deduction=?,
                        other_deductions=?, gross_salary=?, net_salary=?,
                        last_modified=?, sync_status='pending'
                    WHERE employee_id=? AND month=?
                """, (
                    basic_salary, allowances, bonuses,
                    overtime_hours, overtime_rate, overtime_amount,
                    loan_deductions, insurance_deduction, tax_deduction,
                    other_deductions, gross_salary, net_salary,
                    now, employee_id, month
                ))
            else:
                # إدراج راتب جديد
                cursor.execute("""
                    INSERT INTO employee_salaries (
                        employee_id, month, basic_salary, allowances, bonuses,
                        overtime_hours, overtime_rate, overtime_amount,
                        loan_deductions, insurance_deduction, tax_deduction,
                        other_deductions, gross_salary, net_salary,
                        payment_status, created_at, last_modified, sync_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    employee_id, month, basic_salary, allowances, bonuses,
                    overtime_hours, overtime_rate, overtime_amount,
                    loan_deductions, insurance_deduction, tax_deduction,
                    other_deductions, gross_salary, net_salary,
                    'معلق', now, now, 'pending'
                ))
            
            conn.commit()
            conn.close()
            
            salary_data = {
                'employee_id': employee_id,
                'employee_name': employee['name'],
                'month': month,
                'basic_salary': basic_salary,
                'allowances': allowances,
                'bonuses': bonuses,
                'overtime_amount': overtime_amount,
                'loan_deductions': loan_deductions,
                'insurance_deduction': insurance_deduction,
                'tax_deduction': tax_deduction,
                'other_deductions': other_deductions,
                'gross_salary': gross_salary,
                'net_salary': net_salary
            }
            
            logger.info(f"✅ تم حساب راتب {employee['name']} لشهر {month}: {net_salary} ج.م")
            return True, f"تم حساب الراتب بنجاح. الصافي: {net_salary:.2f} ج.م", salary_data
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في حساب الراتب: {e}")
            return False, str(e), {}
    
    def calculate_all_salaries(self, month: str) -> Tuple[bool, str, int]:
        """حساب مرتبات جميع الموظفين النشطين لشهر معين"""
        employees = self.get_all_employees(status_filter='نشط')
        
        calculated_count = 0
        errors = []
        
        for emp in employees:
            success, msg, _ = self.calculate_salary(emp['id'], month)
            if success:
                calculated_count += 1
            else:
                errors.append(f"{emp['name']}: {msg}")
        
        if errors:
            return True, f"تم حساب {calculated_count} راتب. أخطاء: {len(errors)}", calculated_count
        
        return True, f"تم حساب مرتبات {calculated_count} موظف بنجاح", calculated_count
    
    def get_salaries(self, month: str) -> List[Dict]:
        """جلب مرتبات شهر معين"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.*, e.name as employee_name, e.position, e.department
            FROM employee_salaries s
            JOIN employees e ON s.employee_id = e.id
            WHERE s.month = ?
            ORDER BY e.name
        """, (month,))
        
        salaries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return salaries
    
    def pay_salary(self, employee_id: int, month: str, payment_method: str = 'bank') -> Tuple[bool, str]:
        """
        دفع راتب موظف مع إنشاء قيد محاسبي
        
        القيد المحاسبي:
        - مدين: مصروف الرواتب
        - دائن: الخزنة/البنك
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # جلب بيانات الراتب
        cursor.execute("""
            SELECT s.*, e.name as employee_name
            FROM employee_salaries s
            JOIN employees e ON s.employee_id = e.id
            WHERE s.employee_id = ? AND s.month = ?
        """, (employee_id, month))
        
        salary = cursor.fetchone()
        
        if not salary:
            conn.close()
            return False, "الراتب غير موجود"
        
        salary = dict(salary)
        
        if salary['payment_status'] == 'مدفوع':
            conn.close()
            return False, "الراتب مدفوع بالفعل"
        
        now = datetime.now().isoformat()
        
        try:
            # تحديث حالة الراتب
            cursor.execute("""
                UPDATE employee_salaries SET 
                    payment_status = 'مدفوع', payment_date = ?, payment_method = ?, last_modified = ?
                WHERE employee_id = ? AND month = ?
            """, (datetime.now().strftime('%Y-%m-%d'), payment_method, now, employee_id, month))
            
            # سداد أقساط السلف تلقائياً
            if salary['loan_deductions'] > 0:
                cursor.execute("""
                    SELECT id, remaining_amount, monthly_deduction
                    FROM employee_loans
                    WHERE employee_id = ? AND status = 'نشط'
                    ORDER BY start_date
                """, (employee_id,))
                
                active_loans = cursor.fetchall()
                remaining_deduction = salary['loan_deductions']
                
                for loan in active_loans:
                    if remaining_deduction <= 0:
                        break
                    
                    loan = dict(loan)
                    deduction = min(loan['monthly_deduction'], remaining_deduction, loan['remaining_amount'])
                    
                    if deduction > 0:
                        # تسجيل الدفعة
                        cursor.execute("""
                            INSERT INTO loan_payments (
                                loan_id, employee_id, amount, payment_date, payment_method, created_at
                            ) VALUES (?, ?, ?, ?, 'salary_deduction', ?)
                        """, (loan['id'], employee_id, deduction, datetime.now().strftime('%Y-%m-%d'), now))
                        
                        # تحديث السلفة
                        new_remaining = loan['remaining_amount'] - deduction
                        new_status = 'مكتمل' if new_remaining <= 0 else 'نشط'
                        
                        cursor.execute("""
                            UPDATE employee_loans SET remaining_amount = ?, status = ?, last_modified = ?
                            WHERE id = ?
                        """, (new_remaining, new_status, now, loan['id']))
                        
                        remaining_deduction -= deduction
            
            # إنشاء قيد محاسبي
            import json
            payment_account = self.ACC_CASH if payment_method == 'cash' else self.ACC_BANK
            
            lines = [
                {"account_code": self.ACC_SALARIES_EXPENSE, "account_name": "مصروف الرواتب", "debit": salary['net_salary'], "credit": 0},
                {"account_code": payment_account, "account_name": "الخزنة" if payment_method == 'cash' else "البنك", "debit": 0, "credit": salary['net_salary']}
            ]
            
            cursor.execute("""
                INSERT INTO journal_entries (
                    date, description, lines, reference_type, reference_id,
                    total_debit, total_credit, is_balanced,
                    created_at, last_modified, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime('%Y-%m-%d'),
                f"راتب شهر {month} للموظف: {salary['employee_name']}",
                json.dumps(lines, ensure_ascii=False),
                "salary",
                f"SAL-{employee_id}-{month}",
                salary['net_salary'], salary['net_salary'], 1,
                now, now, 'pending'
            ))
            
            # تحديث أرصدة الحسابات
            self._update_account_balance(cursor, self.ACC_SALARIES_EXPENSE, salary['net_salary'], 0)
            self._update_account_balance(cursor, payment_account, 0, salary['net_salary'])
            
            conn.commit()
            conn.close()
            
            # 🔔 إشعار
            notify_operation('paid', 'salary', f"راتب {salary['employee_name']} - {month}")
            logger.info(f"✅ تم دفع راتب {salary['employee_name']} لشهر {month}")
            return True, f"تم دفع الراتب بنجاح: {salary['net_salary']:.2f} ج.م"
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في دفع الراتب: {e}")
            return False, str(e)
    
    def pay_all_salaries(self, month: str, payment_method: str = 'bank') -> Tuple[bool, str, int]:
        """دفع جميع مرتبات شهر معين"""
        salaries = self.get_salaries(month)
        
        paid_count = 0
        errors = []
        
        for sal in salaries:
            if sal['payment_status'] != 'مدفوع':
                success, msg = self.pay_salary(sal['employee_id'], month, payment_method)
                if success:
                    paid_count += 1
                else:
                    errors.append(f"{sal['employee_name']}: {msg}")
        
        if errors:
            return True, f"تم دفع {paid_count} راتب. أخطاء: {len(errors)}", paid_count
        
        return True, f"تم دفع {paid_count} راتب بنجاح", paid_count

    # ==================== إدارة الحضور ====================
    
    def record_attendance(self, employee_id: int, date: str = None, 
                          check_in: str = None, check_out: str = None,
                          status: str = 'حاضر', notes: str = '') -> Tuple[bool, str]:
        """تسجيل حضور موظف"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        now = datetime.now().isoformat()
        
        # حساب ساعات العمل
        work_hours = 0
        overtime_hours = 0
        
        if check_in and check_out:
            try:
                in_time = datetime.strptime(check_in, '%H:%M')
                out_time = datetime.strptime(check_out, '%H:%M')
                diff = (out_time - in_time).seconds / 3600
                work_hours = min(diff, 8)  # الحد الأقصى 8 ساعات عمل عادية
                overtime_hours = max(0, diff - 8)
            except:
                pass
        
        try:
            # فحص إذا كان هناك سجل موجود
            cursor.execute("""
                SELECT id FROM employee_attendance WHERE employee_id = ? AND date = ?
            """, (employee_id, date))
            
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE employee_attendance SET
                        check_in_time=?, check_out_time=?, work_hours=?,
                        overtime_hours=?, status=?, notes=?, last_modified=?
                    WHERE employee_id=? AND date=?
                """, (check_in, check_out, work_hours, overtime_hours, status, notes, now, employee_id, date))
            else:
                cursor.execute("""
                    INSERT INTO employee_attendance (
                        employee_id, date, check_in_time, check_out_time,
                        work_hours, overtime_hours, status, notes,
                        created_at, last_modified, sync_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (employee_id, date, check_in, check_out, work_hours, overtime_hours, status, notes, now, now, 'pending'))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ تم تسجيل حضور الموظف #{employee_id} ليوم {date}")
            return True, "تم تسجيل الحضور بنجاح"
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في تسجيل الحضور: {e}")
            return False, str(e)
    
    def check_in_employee(self, employee_id: int) -> Tuple[bool, str]:
        """تسجيل حضور موظف (الآن)"""
        date = datetime.now().strftime('%Y-%m-%d')
        check_in = datetime.now().strftime('%H:%M')
        return self.record_attendance(employee_id, date, check_in=check_in, status='حاضر')
    
    def check_out_employee(self, employee_id: int) -> Tuple[bool, str]:
        """تسجيل انصراف موظف (الآن)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        date = datetime.now().strftime('%Y-%m-%d')
        check_out = datetime.now().strftime('%H:%M')
        
        # جلب وقت الحضور
        cursor.execute("""
            SELECT check_in_time FROM employee_attendance WHERE employee_id = ? AND date = ?
        """, (employee_id, date))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return False, "لم يتم تسجيل حضور لهذا اليوم"
        
        check_in = row[0]
        return self.record_attendance(employee_id, date, check_in=check_in, check_out=check_out, status='حاضر')
    
    def get_attendance(self, employee_id: int = None, date_from: str = None, date_to: str = None) -> List[Dict]:
        """جلب سجلات الحضور"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT a.*, e.name as employee_name, e.department
            FROM employee_attendance a
            JOIN employees e ON a.employee_id = e.id
            WHERE 1=1
        """
        params = []
        
        if employee_id:
            query += " AND a.employee_id = ?"
            params.append(employee_id)
        
        if date_from:
            query += " AND a.date >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND a.date <= ?"
            params.append(date_to)
        
        query += " ORDER BY a.date DESC, e.name"
        
        cursor.execute(query, params)
        attendance = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return attendance
    
    def get_today_attendance(self) -> List[Dict]:
        """جلب حضور اليوم"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.get_attendance(date_from=today, date_to=today)
    
    # ==================== إدارة الإجازات ====================
    
    def request_leave(self, employee_id: int, leave_type: str, 
                      start_date: str, end_date: str, reason: str = '') -> Tuple[bool, str]:
        """طلب إجازة"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # حساب عدد الأيام
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            days_count = (end - start).days + 1
        except:
            days_count = 1
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO employee_leaves (
                    employee_id, leave_type, start_date, end_date, days_count,
                    reason, status, created_at, last_modified, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (employee_id, leave_type, start_date, end_date, days_count, reason, 'قيد المراجعة', now, now, 'pending'))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ تم تقديم طلب إجازة للموظف #{employee_id}")
            return True, f"تم تقديم طلب الإجازة بنجاح ({days_count} يوم)"
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في طلب الإجازة: {e}")
            return False, str(e)
    
    def approve_leave(self, leave_id: int, approved_by: str) -> Tuple[bool, str]:
        """الموافقة على إجازة"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute("""
                UPDATE employee_leaves SET 
                    status = 'موافق عليها', approved_by = ?, approval_date = ?, last_modified = ?
                WHERE id = ?
            """, (approved_by, datetime.now().strftime('%Y-%m-%d'), now, leave_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ تمت الموافقة على الإجازة #{leave_id}")
            return True, "تمت الموافقة على الإجازة"
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في الموافقة على الإجازة: {e}")
            return False, str(e)
    
    def reject_leave(self, leave_id: int, rejected_by: str, reason: str = '') -> Tuple[bool, str]:
        """رفض إجازة"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute("""
                UPDATE employee_leaves SET 
                    status = 'مرفوضة', approved_by = ?, approval_date = ?, 
                    notes = COALESCE(notes, '') || ' | سبب الرفض: ' || ?, last_modified = ?
                WHERE id = ?
            """, (rejected_by, datetime.now().strftime('%Y-%m-%d'), reason, now, leave_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ تم رفض الإجازة #{leave_id}")
            return True, "تم رفض الإجازة"
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في رفض الإجازة: {e}")
            return False, str(e)
    
    def get_leaves(self, employee_id: int = None, status: str = None) -> List[Dict]:
        """جلب الإجازات"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT l.*, e.name as employee_name, e.department
            FROM employee_leaves l
            JOIN employees e ON l.employee_id = e.id
            WHERE 1=1
        """
        params = []
        
        if employee_id:
            query += " AND l.employee_id = ?"
            params.append(employee_id)
        
        if status:
            query += " AND l.status = ?"
            params.append(status)
        
        query += " ORDER BY l.created_at DESC"
        
        cursor.execute(query, params)
        leaves = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return leaves
    
    def get_pending_leaves(self) -> List[Dict]:
        """جلب الإجازات المعلقة"""
        return self.get_leaves(status='قيد المراجعة')
    
    # ==================== التقارير ====================
    
    def get_employees_summary(self) -> Dict:
        """ملخص الموظفين"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'نشط' THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status = 'غير نشط' THEN 1 ELSE 0 END) as inactive,
                AVG(salary) as avg_salary,
                MAX(salary) as max_salary,
                MIN(salary) as min_salary,
                SUM(salary) as total_salaries
            FROM employees
        """)
        
        row = cursor.fetchone()
        
        cursor.execute("""
            SELECT department, COUNT(*) as count
            FROM employees WHERE status = 'نشط'
            GROUP BY department ORDER BY count DESC
        """)
        
        departments = [dict(r) for r in cursor.fetchall()]
        conn.close()
        
        return {
            'total': row[0] or 0,
            'active': row[1] or 0,
            'inactive': row[2] or 0,
            'avg_salary': row[3] or 0,
            'max_salary': row[4] or 0,
            'min_salary': row[5] or 0,
            'total_salaries': row[6] or 0,
            'departments': departments
        }
    
    def get_loans_summary(self) -> Dict:
        """ملخص السلف"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'نشط' THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status = 'مكتمل' THEN 1 ELSE 0 END) as completed,
                SUM(amount) as total_amount,
                SUM(remaining_amount) as total_remaining,
                SUM(CASE WHEN status = 'نشط' THEN monthly_deduction ELSE 0 END) as monthly_deductions
            FROM employee_loans
        """)
        
        row = cursor.fetchone()
        
        cursor.execute("""
            SELECT loan_type, COUNT(*) as count, SUM(remaining_amount) as remaining
            FROM employee_loans WHERE status = 'نشط'
            GROUP BY loan_type ORDER BY count DESC
        """)
        
        types = [dict(r) for r in cursor.fetchall()]
        conn.close()
        
        return {
            'total': row[0] or 0,
            'active': row[1] or 0,
            'completed': row[2] or 0,
            'total_amount': row[3] or 0,
            'total_remaining': row[4] or 0,
            'monthly_deductions': row[5] or 0,
            'types': types
        }
    
    def get_payroll_summary(self, month: str) -> Dict:
        """ملخص المرتبات لشهر معين"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN payment_status = 'مدفوع' THEN 1 ELSE 0 END) as paid,
                SUM(CASE WHEN payment_status = 'معلق' THEN 1 ELSE 0 END) as pending,
                SUM(basic_salary) as total_basic,
                SUM(allowances) as total_allowances,
                SUM(bonuses) as total_bonuses,
                SUM(loan_deductions) as total_loan_deductions,
                SUM(insurance_deduction) as total_insurance,
                SUM(tax_deduction) as total_tax,
                SUM(net_salary) as total_net
            FROM employee_salaries
            WHERE month = ?
        """, (month,))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            'month': month,
            'total': row[0] or 0,
            'paid': row[1] or 0,
            'pending': row[2] or 0,
            'total_basic': row[3] or 0,
            'total_allowances': row[4] or 0,
            'total_bonuses': row[5] or 0,
            'total_loan_deductions': row[6] or 0,
            'total_insurance': row[7] or 0,
            'total_tax': row[8] or 0,
            'total_net': row[9] or 0
        }
    
    def get_attendance_summary(self, date_from: str = None, date_to: str = None) -> Dict:
        """ملخص الحضور"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if not date_from:
            date_from = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN status = 'حاضر' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN status = 'غائب' THEN 1 ELSE 0 END) as absent,
                SUM(CASE WHEN status = 'متأخر' THEN 1 ELSE 0 END) as late,
                SUM(work_hours) as total_work_hours,
                SUM(overtime_hours) as total_overtime
            FROM employee_attendance
            WHERE date BETWEEN ? AND ?
        """, (date_from, date_to))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            'date_from': date_from,
            'date_to': date_to,
            'total_records': row[0] or 0,
            'present': row[1] or 0,
            'absent': row[2] or 0,
            'late': row[3] or 0,
            'total_work_hours': row[4] or 0,
            'total_overtime': row[5] or 0
        }


    def update_loan(self, loan_id: int, loan_data: Dict) -> Tuple[bool, str]:
        """تحديث بيانات سلفة"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute("""
                UPDATE employee_loans SET
                    loan_type=?, monthly_deduction=?, reason=?, notes=?,
                    last_modified=?, sync_status='pending'
                WHERE id=?
            """, (
                loan_data.get('loan_type'),
                loan_data.get('monthly_deduction', 0),
                loan_data.get('reason', ''),
                loan_data.get('notes', ''),
                now, loan_id
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ تم تحديث السلفة #{loan_id}")
            return True, "تم تحديث السلفة بنجاح"
            
        except Exception as e:
            conn.close()
            logger.error(f"❌ خطأ في تحديث السلفة: {e}")
            return False, str(e)
    
    def get_loan_by_id(self, loan_id: int) -> Optional[Dict]:
        """جلب سلفة بالـ ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT l.*, e.name as employee_name
            FROM employee_loans l
            JOIN employees e ON l.employee_id = e.id
            WHERE l.id = ?
        """, (loan_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_employee_attendance_report(self, employee_id: int, month: str = None) -> Dict:
        """تقرير حضور موظف لشهر معين"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if not month:
            month = datetime.now().strftime('%Y-%m')
        
        date_from = f"{month}-01"
        # حساب آخر يوم في الشهر
        year, mon = map(int, month.split('-'))
        if mon == 12:
            date_to = f"{year + 1}-01-01"
        else:
            date_to = f"{year}-{mon + 1:02d}-01"
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_days,
                SUM(CASE WHEN status = 'حاضر' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN status = 'غائب' THEN 1 ELSE 0 END) as absent,
                SUM(CASE WHEN status = 'متأخر' THEN 1 ELSE 0 END) as late,
                SUM(CASE WHEN status = 'إجازة' THEN 1 ELSE 0 END) as leave,
                SUM(work_hours) as total_work_hours,
                SUM(overtime_hours) as total_overtime
            FROM employee_attendance
            WHERE employee_id = ? AND date >= ? AND date < ?
        """, (employee_id, date_from, date_to))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            'employee_id': employee_id,
            'month': month,
            'total_days': row[0] or 0,
            'present': row[1] or 0,
            'absent': row[2] or 0,
            'late': row[3] or 0,
            'leave': row[4] or 0,
            'total_work_hours': row[5] or 0,
            'total_overtime': row[6] or 0
        }
    
    def get_employee_salary_history(self, employee_id: int, limit: int = 12) -> List[Dict]:
        """جلب سجل رواتب موظف"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM employee_salaries
            WHERE employee_id = ?
            ORDER BY month DESC
            LIMIT ?
        """, (employee_id, limit))
        
        salaries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return salaries


# إنشاء instance عام للخدمة
hr_service = HRService()
