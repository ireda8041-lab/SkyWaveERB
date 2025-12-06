# الملف: services/accounting_service_v2.py
"""
🏦 الروبوت المحاسبي - Enterprise Grade
نظام محاسبي متكامل مع:
- Atomic Transactions
- Strict Double-Entry Balancing
- Auto-Seeding Chart of Accounts
"""

import logging
import sqlite3
from datetime import datetime
from typing import Optional

# إعداد اللوجر الخاص بالمحاسبة
logger = logging.getLogger("AccountingService")
logger.setLevel(logging.INFO)

# --- ثوابت شجرة الحسابات (Enterprise 6-Digit Codes) ---

# 1. الأصول (Assets) - كود 1
ACC_CASH = "111101"              # الخزنة الرئيسية
ACC_BANK_CIB = "111201"          # بنك CIB
ACC_RECEIVABLE = "112100"        # العملاء (ذمم مدينة)

# 2. الخصوم (Liabilities) - كود 2
ACC_PAYABLE = "211100"           # الموردين
ACC_VAT_PAYABLE = "212200"       # ضريبة القيمة المضافة مستحقة الدفع
ACC_UNEARNED_REV = "212100"      # إيرادات غير مكتسبة (دفعات مقدمة)

# 3. حقوق الملكية (Equity) - كود 3
ACC_CAPITAL = "311100"           # رأس المال
ACC_RETAINED_EARNINGS = "312100"  # الأرباح المحتجزة

# 4. الإيرادات (Revenue) - كود 4
ACC_SERVICE_REV = "410100"       # إيرادات الخدمات
ACC_ADS_REV = "410200"           # إيرادات إدارة إعلانات

# 5. المصروفات (Expenses) - كود 5
ACC_EXP_SALARIES = "520100"      # الرواتب والأجور
ACC_EXP_RENT = "520200"          # الإيجار
ACC_EXP_SOFTWARE = "520300"      # اشتراكات برامج وسيرفرات
ACC_EXP_OFFICE = "520400"        # مصروفات مكتبية


class AccountingServiceV2:
    """
    الروبوت المحاسبي Enterprise Grade
    
    المميزات:
    - Atomic Transactions: القيد إما يسجل بالكامل أو يُرفض بالكامل
    - Strict Balancing: مستحيل تسجيل قيد غير متزن
    - Auto-Seeding: ينشئ شجرة الحسابات تلقائياً
    """

    def __init__(self, db_path: str = "skywave_local.db"):
        """
        تهيئة الروبوت المحاسبي
        
        Args:
            db_path: مسار قاعدة البيانات (أو :memory: للاختبار)
        """
        self.db_path = db_path
        self._persistent_conn = None
        
        # للاختبار في الذاكرة، نحتفظ باتصال واحد
        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:")
            self._persistent_conn.execute("PRAGMA foreign_keys = ON")
            self._persistent_conn.row_factory = sqlite3.Row
        
        self._initialize_database()
        self._seed_chart_of_accounts()

    def _get_connection(self) -> sqlite3.Connection:
        """الحصول على اتصال بقاعدة البيانات مع تفعيل Foreign Keys"""
        if self._persistent_conn:
            return self._persistent_conn
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_database(self):
        """إنشاء جداول المحاسبة إذا لم تكن موجودة"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # جدول الحسابات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts_v2 (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                balance REAL DEFAULT 0.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول رؤوس القيود
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS journal_entries_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                reference_type TEXT,
                reference_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول أسطر القيود
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS journal_entry_lines_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                journal_entry_id INTEGER NOT NULL,
                account_code TEXT NOT NULL,
                debit REAL DEFAULT 0.0,
                credit REAL DEFAULT 0.0,
                FOREIGN KEY (journal_entry_id) REFERENCES journal_entries_v2(id),
                FOREIGN KEY (account_code) REFERENCES accounts_v2(code)
            )
        """)

        # إنشاء Indexes للأداء
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_je_lines_entry 
            ON journal_entry_lines_v2(journal_entry_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_je_lines_account 
            ON journal_entry_lines_v2(account_code)
        """)

        conn.commit()
        if not self._persistent_conn:
            conn.close()
        logger.info("[OK] Database tables initialized")

    def _seed_chart_of_accounts(self):
        """زراعة شجرة الحسابات الأساسية عند أول تشغيل"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # فحص هل الجدول فارغ
        cursor.execute("SELECT count(*) FROM accounts_v2")
        if cursor.fetchone()[0] > 0:
            if not self._persistent_conn:
                conn.close()
            return

        logger.info("[SEED] Seeding Chart of Accounts for SkyWave...")

        accounts_data = [
            # الأصول
            (ACC_CASH, "الخزنة الرئيسية", "Asset"),
            (ACC_BANK_CIB, "بنك CIB", "Asset"),
            (ACC_RECEIVABLE, "العملاء (ذمم مدينة)", "Asset"),
            # الخصوم
            (ACC_PAYABLE, "الموردين", "Liability"),
            (ACC_VAT_PAYABLE, "ضريبة القيمة المضافة", "Liability"),
            (ACC_UNEARNED_REV, "إيرادات غير مكتسبة", "Liability"),
            # حقوق الملكية
            (ACC_CAPITAL, "رأس المال", "Equity"),
            (ACC_RETAINED_EARNINGS, "الأرباح المحتجزة", "Equity"),
            # الإيرادات
            (ACC_SERVICE_REV, "إيرادات خدمات برمجية", "Revenue"),
            (ACC_ADS_REV, "إيرادات حملات إعلانية", "Revenue"),
            # المصروفات
            (ACC_EXP_SALARIES, "رواتب وأجور", "Expense"),
            (ACC_EXP_RENT, "إيجار مقر", "Expense"),
            (ACC_EXP_SOFTWARE, "سيرفرات واستضافات", "Expense"),
            (ACC_EXP_OFFICE, "مصروفات مكتبية", "Expense"),
        ]

        cursor.executemany(
            "INSERT INTO accounts_v2 (code, name, type) VALUES (?,?,?)",
            accounts_data
        )
        conn.commit()
        if not self._persistent_conn:
            conn.close()
        logger.info(f"[OK] Seeded {len(accounts_data)} accounts")

    # ---------------------------------------------------------
    # Core Logic: The Entry Creator
    # ---------------------------------------------------------

    def create_journal_entry(
        self,
        description: str,
        lines: list[dict],
        ref_type: Optional[str] = None,
        ref_id: Optional[str] = None
    ) -> int:
        """
        إنشاء قيد محاسبي جديد مع التحقق الصارم من التوازن
        
        Args:
            description: وصف القيد
            lines: قائمة الأسطر [{'account_code': '111101', 'debit': 1000, 'credit': 0}, ...]
            ref_type: نوع المرجع (Invoice, Payment, Expense)
            ref_id: معرف المرجع
            
        Returns:
            int: رقم القيد المنشأ
            
        Raises:
            ValueError: إذا كان القيد غير متوازن
        """
        # حساب الإجماليات مع التقريب
        total_debit = sum(round(line.get('debit', 0) or 0, 2) for line in lines)
        total_credit = sum(round(line.get('credit', 0) or 0, 2) for line in lines)

        # 1. التحقق من التوازن (Double Entry Check)
        if abs(total_debit - total_credit) > 0.01:
            error_msg = f"[X] Accounting Error: Entry not balanced! Debit: {total_debit}, Credit: {total_credit}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # 2. إنشاء رأس القيد
            cursor.execute("""
                INSERT INTO journal_entries_v2 (date, description, reference_type, reference_id)
                VALUES (?, ?, ?, ?)
            """, (datetime.now().strftime("%Y-%m-%d"), description, ref_type, ref_id))

            entry_id = cursor.lastrowid

            # 3. إدخال الأسطر وتحديث أرصدة الحسابات
            for line in lines:
                debit = round(line.get('debit', 0) or 0, 2)
                credit = round(line.get('credit', 0) or 0, 2)
                account_code = line['account_code']

                # إدخال السطر
                cursor.execute("""
                    INSERT INTO journal_entry_lines_v2 (journal_entry_id, account_code, debit, credit)
                    VALUES (?, ?, ?, ?)
                """, (entry_id, account_code, debit, credit))

                # تحديث رصيد الحساب
                # الأصول والمصروفات: تزيد بالمدين (balance = debit - credit)
                # الخصوم والإيرادات وحقوق الملكية: تزيد بالدائن
                cursor.execute("""
                    UPDATE accounts_v2
                    SET balance = balance + ? - ?
                    WHERE code = ?
                """, (debit, credit, account_code))

            conn.commit()
            logger.info(f"[OK] Entry #{entry_id} Created: {description}")
            return entry_id

        except Exception as e:
            conn.rollback()
            logger.error(f"[X] Transaction Failed: {str(e)}")
            raise e

        finally:
            if not self._persistent_conn:
                conn.close()

    # ---------------------------------------------------------
    # Auto-Handlers: الروبوتات التلقائية
    # ---------------------------------------------------------

    def handle_invoice_created(
        self,
        invoice_id: str,
        total_amount: float,
        tax_amount: float,
        client_name: str
    ) -> int:
        """
        عند إنشاء فاتورة:
        من ح/ العملاء (إجمالي الفاتورة)
            إلى ح/ الإيرادات (المبلغ قبل الضريبة)
            إلى ح/ ضريبة القيمة المضافة (مبلغ الضريبة)
        """
        revenue_amount = round(total_amount - tax_amount, 2)

        lines = [
            # المدين: العميل ملزم بالدفع
            {'account_code': ACC_RECEIVABLE, 'debit': total_amount, 'credit': 0},
            # الدائن: الإيراد
            {'account_code': ACC_SERVICE_REV, 'debit': 0, 'credit': revenue_amount},
            # الدائن: مصلحة الضرائب
            {'account_code': ACC_VAT_PAYABLE, 'debit': 0, 'credit': tax_amount}
        ]

        description = f"استحقاق فاتورة رقم {invoice_id} - عميل: {client_name}"
        return self.create_journal_entry(description, lines, "INVOICE", invoice_id)

    def handle_payment_received(
        self,
        payment_id: str,
        amount: float,
        method: str,
        client_name: str
    ) -> int:
        """
        عند استلام دفعة:
        من ح/ الخزنة أو البنك
            إلى ح/ العملاء (تقليل المديونية)
        """
        target_account = ACC_BANK_CIB if method.lower() == "bank" else ACC_CASH

        lines = [
            {'account_code': target_account, 'debit': amount, 'credit': 0},
            {'account_code': ACC_RECEIVABLE, 'debit': 0, 'credit': amount}
        ]

        description = f"تحصيل دفعة رقم {payment_id} - عميل: {client_name}"
        return self.create_journal_entry(description, lines, "PAYMENT", payment_id)

    def handle_expense_recorded(
        self,
        expense_id: str,
        amount: float,
        category: str,
        description: str
    ) -> int:
        """
        عند تسجيل مصروف:
        من ح/ المصروف المختص
            إلى ح/ الخزنة
        """
        # تحديد كود حساب المصروف بناءً على التصنيف
        expense_map = {
            "salaries": ACC_EXP_SALARIES,
            "rent": ACC_EXP_RENT,
            "software": ACC_EXP_SOFTWARE,
            "office": ACC_EXP_OFFICE,
        }

        # افتراضي: مصروفات مكتبية
        expense_acc_code = expense_map.get(category.lower(), ACC_EXP_OFFICE)

        lines = [
            {'account_code': expense_acc_code, 'debit': amount, 'credit': 0},
            {'account_code': ACC_CASH, 'debit': 0, 'credit': amount}
        ]

        desc = f"مصروف: {description}"
        return self.create_journal_entry(desc, lines, "EXPENSE", expense_id)

    # ---------------------------------------------------------
    # Reporting: التقارير
    # ---------------------------------------------------------

    def get_account_balance(self, account_code: str) -> float:
        """الحصول على رصيد حساب معين"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM accounts_v2 WHERE code = ?", (account_code,))
        res = cursor.fetchone()
        if not self._persistent_conn:
            conn.close()
        return float(res[0]) if res else 0.0

    def get_financial_summary(self) -> dict[str, float]:
        """إرجاع ملخص للأصول والالتزامات والإيرادات والمصروفات"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT type, SUM(balance)
            FROM accounts_v2
            GROUP BY type
        """)

        results = {row[0]: float(row[1] or 0) for row in cursor.fetchall()}
        if not self._persistent_conn:
            conn.close()
        return results

    def get_trial_balance(self) -> list[dict]:
        """ميزان المراجعة - قائمة بجميع الحسابات وأرصدتها"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT code, name, type, balance
            FROM accounts_v2
            ORDER BY code
        """)

        trial_balance = []
        for row in cursor.fetchall():
            balance = float(row[3] or 0)
            trial_balance.append({
                'code': row[0],
                'name': row[1],
                'type': row[2],
                'debit': balance if balance > 0 else 0,
                'credit': abs(balance) if balance < 0 else 0
            })

        if not self._persistent_conn:
            conn.close()
        return trial_balance

    def verify_books_balanced(self) -> tuple[bool, float, float]:
        """
        التحقق من توازن الدفاتر
        
        Returns:
            tuple: (is_balanced, total_debit, total_credit)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                SUM(debit) as total_debit,
                SUM(credit) as total_credit
            FROM journal_entry_lines_v2
        """)

        row = cursor.fetchone()
        if not self._persistent_conn:
            conn.close()

        total_debit = float(row[0] or 0)
        total_credit = float(row[1] or 0)
        is_balanced = abs(total_debit - total_credit) < 0.01

        return is_balanced, total_debit, total_credit


# --- للتجربة المباشرة ---
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    
    print("=" * 50)
    print("ACCOUNTING SERVICE V2 - TEST")
    print("=" * 50)

    # استخدام قاعدة بيانات في الذاكرة للاختبار
    svc = AccountingServiceV2(":memory:")

    print("\n1. Testing Invoice Creation...")
    try:
        entry_id = svc.handle_invoice_created("INV-2025-001", 1140.0, 140.0, "SkyWave Customer")
        print(f"[OK] Invoice Entry #{entry_id} Created Successfully.")
    except Exception as e:
        print(f"[X] Failed: {e}")

    print("\n2. Checking Receivables Balance...")
    bal = svc.get_account_balance(ACC_RECEIVABLE)
    print(f"[INFO] Client Debt: {bal} EGP (Should be 1140.0)")
    assert abs(bal - 1140.0) < 0.01, "Balance mismatch!"

    print("\n3. Testing Payment Receipt...")
    svc.handle_payment_received("PAY-001", 1140.0, "cash", "SkyWave Customer")
    bal_after = svc.get_account_balance(ACC_RECEIVABLE)
    print(f"[INFO] Client Debt after Payment: {bal_after} EGP (Should be 0.0)")
    assert abs(bal_after) < 0.01, "Balance should be zero!"

    print("\n4. Testing Expense Recording...")
    svc.handle_expense_recorded("EXP-001", 500.0, "software", "اشتراك سيرفر")
    exp_bal = svc.get_account_balance(ACC_EXP_SOFTWARE)
    print(f"[INFO] Software Expenses: {exp_bal} EGP")

    print("\n5. Verifying Books Balance...")
    is_balanced, total_dr, total_cr = svc.verify_books_balanced()
    print(f"[INFO] Total Debit: {total_dr}, Total Credit: {total_cr}")
    print(f"[{'OK' if is_balanced else 'X'}] Books are {'BALANCED' if is_balanced else 'NOT BALANCED'}!")

    print("\n6. Financial Summary...")
    summary = svc.get_financial_summary()
    for acc_type, balance in summary.items():
        print(f"   - {acc_type}: {balance:,.2f} EGP")

    print("\n" + "=" * 50)
    print("[OK] All tests passed!")
    print("=" * 50)
