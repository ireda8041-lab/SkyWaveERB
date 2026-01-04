# الملف: core/repository.py
"""
⚡ المخزن الذكي - Sky Wave ERP
محسّن للسرعة القصوى مع نظام Cache ذكي
"""

import json
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime
from typing import Any

import pymongo

from . import schemas

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    import re
    def safe_print(msg: str):
        """طباعة آمنة تتعامل مع مشاكل الترميز في Windows"""
        try:
            print(msg)
        except UnicodeEncodeError:
            # إزالة الـ emoji وطباعة النص فقط
            clean_msg = re.sub(r'[^\x00-\x7F\u0600-\u06FF]+', '', msg)
            try:
                print(clean_msg)
            except Exception:
                pass  # تجاهل أي خطأ في الطباعة


# ⚡ استيراد محسّن السرعة
try:
    from .speed_optimizer import LRUCache, cached, invalidate_cache  # noqa: F401
    CACHE_ENABLED = True
except ImportError:
    CACHE_ENABLED = False
    safe_print("WARNING: speed_optimizer غير متوفر - الـ cache معطل")

# ⚡ استيراد محسّن الأداء الجديد
try:
    from .performance_optimizer import (
        SmartQueryCache,
        optimize_sqlite_connection,
        get_query_cache,
    )
    PERFORMANCE_OPTIMIZER_ENABLED = True
except ImportError:
    PERFORMANCE_OPTIMIZER_ENABLED = False
    safe_print(f"WARNING: performance_optimizer غير متوفر")

# --- إعدادات الاتصال ---
MONGO_URI = "mongodb://skywave_app:SkywavePassword2025@147.79.66.116:27017/skywave_erp_db?authSource=skywave_erp_db"
DB_NAME = "skywave_erp_db"

# ✅ استخدام مجلد المشروع الحالي لقاعدة البيانات المحلية
_PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))
LOCAL_DB_FILE = os.path.join(_PROJECT_DIR, "skywave_local.db")

# ⚡ نسخ قاعدة البيانات من مجلد البرنامج لو مش موجودة في AppData
def _copy_initial_db():
    """نسخ قاعدة البيانات الأولية من مجلد البرنامج إذا لم تكن موجودة"""
    import shutil
    import sys
    
    if os.path.exists(LOCAL_DB_FILE):
        return  # قاعدة البيانات موجودة بالفعل
    
    # البحث عن قاعدة البيانات في مجلد البرنامج
    possible_paths = []
    
    if getattr(sys, 'frozen', False):
        # التطبيق يعمل كـ EXE
        exe_dir = os.path.dirname(sys.executable)
        possible_paths = [
            os.path.join(exe_dir, "_internal", "skywave_local.db"),
            os.path.join(exe_dir, "skywave_local.db"),
        ]
        if hasattr(sys, '_MEIPASS'):
            possible_paths.insert(0, os.path.join(sys._MEIPASS, "skywave_local.db"))
    else:
        # التطبيق يعمل كـ Python script
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "skywave_local.db"),
            "skywave_local.db",
        ]
    
    for src_path in possible_paths:
        if os.path.exists(src_path):
            try:
                shutil.copy2(src_path, LOCAL_DB_FILE)
                safe_print(f"INFO: ✅ تم نسخ قاعدة البيانات من {src_path} إلى {LOCAL_DB_FILE}")
                return
            except Exception as e:
                safe_print(f"WARNING: فشل نسخ قاعدة البيانات: {e}")
    
    safe_print(f"INFO: لم يتم العثور على قاعدة بيانات أولية - سيتم إنشاء قاعدة جديدة")

# تنفيذ النسخ عند تحميل الموديول
_copy_initial_db()


class Repository:
    """
    ⚡ المخزن الذكي مع Caching للسرعة القصوى.
    - Cache ذكي للبيانات المتكررة
    - SQLite محسّن للأداء
    - MongoDB للمزامنة (في background)
    """

    def __init__(self):
        self.online = False
        self.mongo_client = None
        self.mongo_db = None
        self._lock = threading.RLock()
        self._mongo_connecting = False

        # ⚡ Cache للبيانات المتكررة
        if CACHE_ENABLED:
            self._clients_cache = LRUCache(maxsize=500, ttl_seconds=60)
            self._projects_cache = LRUCache(maxsize=500, ttl_seconds=60)
            self._services_cache = LRUCache(maxsize=200, ttl_seconds=120)

        # ⚡ 1. SQLite أولاً (سريع جداً) - لا ننتظر MongoDB
        self.sqlite_conn = sqlite3.connect(
            LOCAL_DB_FILE,
            check_same_thread=False,
            timeout=30.0,
            isolation_level=None  # ⚡ Autocommit للسرعة
        )
        self.sqlite_conn.row_factory = sqlite3.Row
        self.sqlite_cursor = self.sqlite_conn.cursor()
        
        # ⚡ تطبيق تحسينات SQLite للأداء
        self._apply_sqlite_optimizations()
        
        safe_print(f"INFO: ✅ متصل بقاعدة البيانات الأوفلاين ({LOCAL_DB_FILE}).")

        # 2. بناء الجداول الأوفلاين لو مش موجودة
        self._init_local_db()

        # ⚡ 3. الاتصال بـ MongoDB في Background Thread (لا يعطل البرنامج)
        self._start_mongo_connection()

    def get_cursor(self):
        """
        ⚡ الحصول على cursor منفصل لتجنب مشكلة Recursive cursor
        يجب إغلاق الـ cursor بعد الاستخدام: cursor.close()
        """
        with self._lock:
            cursor = self.sqlite_conn.cursor()
            return cursor
    
    def _apply_sqlite_optimizations(self):
        """⚡ تطبيق تحسينات SQLite للأداء الأقصى"""
        try:
            # WAL mode للقراءة والكتابة المتزامنة
            self.sqlite_cursor.execute("PRAGMA journal_mode=WAL")
            # تقليل الـ sync للسرعة (آمن مع WAL)
            self.sqlite_cursor.execute("PRAGMA synchronous=NORMAL")
            # زيادة حجم الـ cache (10000 صفحة = ~40MB)
            self.sqlite_cursor.execute("PRAGMA cache_size=10000")
            # تخزين الجداول المؤقتة في الذاكرة
            self.sqlite_cursor.execute("PRAGMA temp_store=MEMORY")
            # تفعيل memory-mapped I/O (256MB)
            self.sqlite_cursor.execute("PRAGMA mmap_size=268435456")
            # تفعيل الـ foreign keys
            self.sqlite_cursor.execute("PRAGMA foreign_keys=ON")
            safe_print(f"INFO: ⚡ تم تطبيق تحسينات SQLite للأداء")
        except Exception as e:
            safe_print(f"WARNING: فشل تطبيق تحسينات SQLite: {e}")

    def _start_mongo_connection(self):
        """⚡ الاتصال بـ MongoDB في Background Thread"""
        if self._mongo_connecting:
            return
        self._mongo_connecting = True

        def connect_mongo():
            try:
                self.mongo_client = pymongo.MongoClient(
                    MONGO_URI,
                    serverSelectionTimeoutMS=5000,  # ⚡ 5 ثواني للاتصال - أسرع
                    connectTimeoutMS=5000,
                    socketTimeoutMS=10000,  # ⚡ 10 ثواني للعمليات
                    retryWrites=True,
                    retryReads=True,
                    maxPoolSize=10,  # ⚡ تقليل عدد الاتصالات
                    minPoolSize=1
                )
                self.mongo_client.server_info()
                self.mongo_db = self.mongo_client[DB_NAME]
                self.online = True
                safe_print(f"INFO: ✅ متصل بـ MongoDB (Background)")
            except pymongo.errors.ServerSelectionTimeoutError:
                safe_print(f"WARNING: ⚠️ وضع أوفلاين - MongoDB غير متاح")
                self.online = False
            except Exception as e:
                safe_print(f"WARNING: ⚠️ خطأ في الاتصال بـ MongoDB: {e}")
                self.online = False
            finally:
                self._mongo_connecting = False

        # تشغيل الاتصال في thread منفصل
        mongo_thread = threading.Thread(target=connect_mongo, daemon=True)
        mongo_thread.start()

    def _init_local_db(self):
        """دالة داخلية تنشئ كل الجداول في ملف SQLite المحلي فقط إذا لم تكن موجودة."""
        safe_print(f"INFO: جاري فحص الجداول المحلية (SQLite)...")

        # جدول الحسابات (accounts)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
            parent_id TEXT,
            balance REAL DEFAULT 0.0,
            currency TEXT DEFAULT 'EGP',
            description TEXT
        )""")

        # Migration: إضافة الأعمدة الناقصة للجداول القديمة
        try:
            self.sqlite_cursor.execute("ALTER TABLE accounts ADD COLUMN currency TEXT DEFAULT 'EGP'")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل
        try:
            self.sqlite_cursor.execute("ALTER TABLE accounts ADD COLUMN description TEXT")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل
        try:
            self.sqlite_cursor.execute("ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'نشط'")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل

        # جدول المصروفات (expenses)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            account_id TEXT NOT NULL,
            payment_account_id TEXT,
            project_id TEXT
        )""")

        # Migration: إضافة عمود payment_account_id للجداول القديمة
        try:
            self.sqlite_cursor.execute("ALTER TABLE expenses ADD COLUMN payment_account_id TEXT")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل

        # Migration: إضافة عمود status_manually_set للمشاريع
        try:
            self.sqlite_cursor.execute("ALTER TABLE projects ADD COLUMN status_manually_set INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل

        # Migration: إضافة عمود invoice_number للمشاريع (رقم الفاتورة الثابت)
        try:
            self.sqlite_cursor.execute("ALTER TABLE projects ADD COLUMN invoice_number TEXT")
            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repository] تم إضافة عمود invoice_number لجدول المشاريع")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل

        # ==================== Enterprise Migrations ====================
        # Migration: إضافة أعمدة Enterprise للمشاريع
        enterprise_columns = [
            ("project_code", "TEXT"),           # كود المشروع الذكي
            ("sequence_number", "INTEGER DEFAULT 0"),  # الرقم التسلسلي
            ("cost_center_id", "TEXT"),         # مركز التكلفة
            ("contract_type", "TEXT DEFAULT 'مرة واحدة'"),  # نوع العقد
            ("is_retainer", "INTEGER DEFAULT 0"),  # هل عقد متكرر
            ("renewal_cycle", "TEXT"),          # دورة التجديد
            ("next_renewal_date", "TEXT"),      # تاريخ التجديد القادم
            ("milestones", "TEXT"),             # الدفعات المرحلية (JSON)
            ("total_estimated_cost", "REAL DEFAULT 0.0"),  # التكلفة التقديرية
            ("estimated_profit", "REAL DEFAULT 0.0"),  # الربح المتوقع
            ("profit_margin", "REAL DEFAULT 0.0"),  # هامش الربح
            ("project_manager_id", "TEXT"),     # مدير المشروع
        ]

        for col_name, col_type in enterprise_columns:
            try:
                self.sqlite_cursor.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")
                safe_print(f"INFO: [Repository] ✅ تم إضافة عمود {col_name} لجدول المشاريع")
            except sqlite3.OperationalError:
                pass  # العمود موجود بالفعل

        self.sqlite_conn.commit()

        # ⚡ جدول الدفعات المرحلية (project_milestones)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            percentage REAL DEFAULT 0.0,
            amount REAL DEFAULT 0.0,
            due_date TEXT,
            status TEXT DEFAULT 'قيد الانتظار',
            invoice_id TEXT,
            paid_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(name)
        )
        """)
        self.sqlite_conn.commit()
        safe_print(f"INFO: [Repository] ✅ جدول الدفعات المرحلية جاهز")

        # ⚡ جدول أرقام الفواتير الثابتة (مرتبط باسم المشروع وليس الـ ID)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL UNIQUE,
            invoice_number TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
        """)
        self.sqlite_conn.commit()

        # ⚡ Migration: توليد أرقام فواتير للمشاريع القديمة اللي مش عندها invoice_number
        try:
            # جلب المشاريع اللي مش عندها رقم فاتورة
            self.sqlite_cursor.execute("""
                SELECT p.id, p.name FROM projects p
                WHERE p.invoice_number IS NULL OR p.invoice_number = ''
            """)
            projects_without_invoice = self.sqlite_cursor.fetchall()

            if projects_without_invoice:
                safe_print(f"INFO: [Repository] توليد أرقام فواتير لـ {len(projects_without_invoice)} مشروع...")

                for row in projects_without_invoice:
                    project_id = row[0]
                    project_name = row[1]

                    # أولاً: تحقق من وجود رقم محفوظ مسبقاً لهذا المشروع
                    self.sqlite_cursor.execute(
                        "SELECT invoice_number FROM invoice_numbers WHERE project_name = ?",
                        (project_name,)
                    )
                    existing = self.sqlite_cursor.fetchone()

                    if existing:
                        # استخدم الرقم المحفوظ
                        invoice_number = existing[0]
                        safe_print(f"  ✓ استخدام رقم محفوظ: {project_name} -> {invoice_number}")
                    else:
                        # ولّد رقم جديد
                        self.sqlite_cursor.execute("SELECT MAX(id) FROM invoice_numbers")
                        max_id = self.sqlite_cursor.fetchone()[0] or 0
                        new_seq = max_id + 1
                        invoice_number = f"SW-{97161 + new_seq}"

                        # احفظ الرقم الجديد
                        self.sqlite_cursor.execute(
                            "INSERT INTO invoice_numbers (project_name, invoice_number, created_at) VALUES (?, ?, ?)",
                            (project_name, invoice_number, datetime.now().isoformat())
                        )
                        safe_print(f"  + رقم جديد: {project_name} -> {invoice_number}")

                    # حدّث المشروع
                    self.sqlite_cursor.execute(
                        "UPDATE projects SET invoice_number = ? WHERE id = ?",
                        (invoice_number, project_id)
                    )

                self.sqlite_conn.commit()
                safe_print(f"INFO: [Repository] ✅ تم توليد أرقام فواتير لـ {len(projects_without_invoice)} مشروع")
        except Exception as e:
            safe_print(f"WARNING: [Repository] فشل توليد أرقام الفواتير: {e}")
            import traceback
            traceback.print_exc()

        # جدول العملاء (clients)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            name TEXT NOT NULL,
            company_name TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            country TEXT,
            vat_number TEXT,
            status TEXT NOT NULL DEFAULT 'نشط',
            client_type TEXT,
            work_field TEXT,
            logo_path TEXT,
            logo_data TEXT,
            client_notes TEXT
        )""")

        # إضافة عمود logo_data إذا لم يكن موجوداً (للتوافق مع قواعد البيانات القديمة)
        try:
            self.sqlite_cursor.execute("ALTER TABLE clients ADD COLUMN logo_data TEXT")
            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repository] تم إضافة عمود logo_data لجدول العملاء")
        except Exception:
            pass  # العمود موجود بالفعل

        # جدول الخدمات (services)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            default_price REAL NOT NULL,
            category TEXT,
            status TEXT NOT NULL DEFAULT 'نشط'
        )""")

        # جدول الفواتير (invoices)
        # (البنود 'items' هتتخزن كـ JSON text)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            invoice_number TEXT NOT NULL UNIQUE,
            client_id TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            items TEXT NOT NULL, -- (JSON List of InvoiceItem)
            subtotal REAL NOT NULL,
            discount_rate REAL DEFAULT 0.0,
            discount_amount REAL DEFAULT 0.0,
            tax_rate REAL DEFAULT 0.0,
            tax_amount REAL DEFAULT 0.0,
            total_amount REAL NOT NULL,
            amount_paid REAL DEFAULT 0.0,
            status TEXT NOT NULL,
            currency TEXT NOT NULL,
            notes TEXT,
            project_id TEXT
        )""")

        # جدول المشاريع (projects) (معدل بالكامل)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            name TEXT NOT NULL UNIQUE,
            client_id TEXT NOT NULL,
            status TEXT NOT NULL,
            status_manually_set INTEGER DEFAULT 0,
            description TEXT,
            start_date TEXT,
            end_date TEXT,

            items TEXT,
            subtotal REAL DEFAULT 0.0,
            discount_rate REAL DEFAULT 0.0,
            discount_amount REAL DEFAULT 0.0,
            tax_rate REAL DEFAULT 0.0,
            tax_amount REAL DEFAULT 0.0,
            total_amount REAL DEFAULT 0.0,
            currency TEXT,
            project_notes TEXT,
            invoice_number TEXT,

            -- Enterprise Features
            project_code TEXT,
            sequence_number INTEGER DEFAULT 0,
            cost_center_id TEXT,
            contract_type TEXT DEFAULT 'مرة واحدة',
            is_retainer INTEGER DEFAULT 0,
            renewal_cycle TEXT,
            next_renewal_date TEXT,
            milestones TEXT,
            total_estimated_cost REAL DEFAULT 0.0,
            estimated_profit REAL DEFAULT 0.0,
            profit_margin REAL DEFAULT 0.0,
            project_manager_id TEXT
        )""")

        # جدول قيود اليومية (journal_entries)
        # (البنود 'lines' هتتخزن كـ JSON text)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            lines TEXT NOT NULL, -- (JSON List of JournalEntryLine)
            related_document_id TEXT
        )""")

        # جدول الدفعات (payments)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            project_id TEXT NOT NULL,
            client_id TEXT NOT NULL,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            account_id TEXT NOT NULL,
            method TEXT
        )""")

        # جدول العملات (currencies)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS currencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            rate REAL NOT NULL DEFAULT 1.0,
            is_base INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )""")

        # جدول الإشعارات (notifications)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'متوسطة',
            is_read INTEGER DEFAULT 0,
            related_entity_type TEXT,
            related_entity_id TEXT,
            action_url TEXT,
            expires_at TEXT
        )""")

        # جدول المستخدمين (users)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT,
            email TEXT,
            is_active INTEGER DEFAULT 1,
            last_login TEXT,
            custom_permissions TEXT
        )""")

        # Migration: إضافة عمود custom_permissions للجداول القديمة
        try:
            self.sqlite_cursor.execute("ALTER TABLE users ADD COLUMN custom_permissions TEXT")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل

        # جدول الموظفين (employees) - نظام الموارد البشرية
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            employee_id TEXT UNIQUE,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            department TEXT,
            position TEXT,
            hire_date TEXT,
            salary REAL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'نشط',
            address TEXT,
            national_id TEXT,
            bank_account TEXT,
            notes TEXT
        )""")
        self.sqlite_conn.commit()
        safe_print(f"INFO: [Repository] ✅ جدول الموظفين جاهز")

        # جدول سلف الموظفين (employee_loans)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            employee_id INTEGER NOT NULL,
            loan_type TEXT NOT NULL DEFAULT 'سلفة',
            amount REAL NOT NULL DEFAULT 0.0,
            remaining_amount REAL NOT NULL DEFAULT 0.0,
            monthly_deduction REAL NOT NULL DEFAULT 0.0,
            start_date TEXT,
            end_date TEXT,
            status TEXT NOT NULL DEFAULT 'نشط',
            reason TEXT,
            approved_by TEXT,
            notes TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )""")
        self.sqlite_conn.commit()
        safe_print(f"INFO: [Repository] ✅ جدول سلف الموظفين جاهز")

        # جدول مرتبات الموظفين (employee_salaries)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_salaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            employee_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            basic_salary REAL NOT NULL DEFAULT 0.0,
            allowances REAL DEFAULT 0.0,
            bonuses REAL DEFAULT 0.0,
            overtime_hours REAL DEFAULT 0.0,
            overtime_rate REAL DEFAULT 0.0,
            overtime_amount REAL DEFAULT 0.0,
            loan_deductions REAL DEFAULT 0.0,
            insurance_deduction REAL DEFAULT 0.0,
            tax_deduction REAL DEFAULT 0.0,
            other_deductions REAL DEFAULT 0.0,
            gross_salary REAL DEFAULT 0.0,
            net_salary REAL DEFAULT 0.0,
            payment_status TEXT NOT NULL DEFAULT 'معلق',
            payment_date TEXT,
            payment_method TEXT,
            notes TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            UNIQUE(employee_id, month)
        )""")
        self.sqlite_conn.commit()
        safe_print(f"INFO: [Repository] ✅ جدول مرتبات الموظفين جاهز")

        # جدول حضور الموظفين (employee_attendance)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            check_in_time TEXT,
            check_out_time TEXT,
            work_hours REAL DEFAULT 0.0,
            overtime_hours REAL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'حاضر',
            notes TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            UNIQUE(employee_id, date)
        )""")
        self.sqlite_conn.commit()
        safe_print(f"INFO: [Repository] ✅ جدول حضور الموظفين جاهز")

        # جدول إجازات الموظفين (employee_leaves)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            employee_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL DEFAULT 'سنوية',
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            days_count INTEGER NOT NULL DEFAULT 1,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'معلق',
            approved_by TEXT,
            approval_date TEXT,
            notes TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )""")
        self.sqlite_conn.commit()
        safe_print(f"INFO: [Repository] ✅ جدول إجازات الموظفين جاهز")

        # جدول أقساط السلف (loan_payments)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS loan_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            loan_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            payment_method TEXT DEFAULT 'خصم من الراتب',
            notes TEXT,
            FOREIGN KEY (loan_id) REFERENCES employee_loans(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )""")
        self.sqlite_conn.commit()
        safe_print(f"INFO: [Repository] ✅ جدول أقساط السلف جاهز")

        # جدول المهام (tasks) - نظام TODO
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT NOT NULL DEFAULT 'MEDIUM',
            status TEXT NOT NULL DEFAULT 'TODO',
            category TEXT NOT NULL DEFAULT 'GENERAL',
            due_date TEXT,
            due_time TEXT,
            completed_at TEXT,
            related_project_id TEXT,
            related_client_id TEXT,
            tags TEXT,
            reminder INTEGER DEFAULT 0,
            reminder_minutes INTEGER DEFAULT 30,
            assigned_to TEXT,
            is_archived INTEGER DEFAULT 0,
            FOREIGN KEY (related_project_id) REFERENCES projects(name),
            FOREIGN KEY (related_client_id) REFERENCES clients(id)
        )""")

        # إضافة حقل is_archived إذا لم يكن موجوداً (للتوافق مع قواعد البيانات القديمة)
        try:
            self.sqlite_cursor.execute("ALTER TABLE tasks ADD COLUMN is_archived INTEGER DEFAULT 0")
        except Exception:
            pass  # الحقل موجود بالفعل

        # جدول قائمة انتظار المزامنة (sync_queue)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            action TEXT,
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            data TEXT,
            error_message TEXT,
            last_attempt TEXT
        )""")

        # إضافة عمود action إذا لم يكن موجوداً (للتوافق مع الإصدارات القديمة)
        try:
            self.sqlite_cursor.execute("ALTER TABLE sync_queue ADD COLUMN action TEXT")
            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repository] Added 'action' column to sync_queue table")
        except Exception:
            # العمود موجود بالفعل أو خطأ آخر
            pass

        # إنشاء indexes لتحسين أداء sync_queue
        self.sqlite_cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sync_queue_status
        ON sync_queue(status)
        """)

        self.sqlite_cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sync_queue_priority
        ON sync_queue(priority, status)
        """)

        self.sqlite_cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sync_queue_entity
        ON sync_queue(entity_type, entity_id)
        """)

        self.sqlite_conn.commit()
        safe_print(f"INFO: الجداول المحلية جاهزة.")

        # ⚡ إنشاء indexes لتحسين الأداء (مهم جداً للسرعة)
        self._create_sqlite_indexes()

        # ⚡ تحسين قاعدة البيانات للأداء
        self._optimize_sqlite_performance()

        # إنشاء collection و indexes في MongoDB إذا كان متصل
        if self.online:
            self._init_mongo_indexes()

    def _create_sqlite_indexes(self):
        """
        إنشاء indexes في SQLite لتحسين الأداء
        """
        try:
            safe_print(f"INFO: جاري إنشاء indexes في SQLite...")

            # Indexes لـ clients
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status)")

            # Indexes لـ projects
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_start_date ON projects(start_date)")

            # Indexes لـ journal_entries
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(date)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_related ON journal_entries(related_document_id)")

            # Indexes لـ expenses
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(project_id)")

            # Indexes لـ invoices
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status)")

            # Indexes لـ payments
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_project ON payments(project_id)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(date)")

            # ⚡ Unique indexes لمنع التكرار
            # منع تكرار العملاء بنفس الاسم (case insensitive)
            try:
                self.sqlite_cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_name_unique ON clients(LOWER(name)) WHERE status != 'مؤرشف'")
            except Exception:
                pass  # قد يفشل إذا كان هناك تكرارات موجودة

            # منع تكرار المشاريع بنفس الاسم لنفس العميل
            try:
                self.sqlite_cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_name_client_unique ON projects(LOWER(name), client_id) WHERE status != 'مؤرشف'")
            except Exception:
                pass  # قد يفشل إذا كان هناك تكرارات موجودة

            # منع تكرار الدفعات (نفس المشروع + نفس التاريخ + نفس المبلغ)
            try:
                self.sqlite_cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_unique ON payments(project_id, date, amount)")
            except Exception:
                pass  # قد يفشل إذا كان هناك تكرارات موجودة

            # Indexes لـ notifications
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at)")

            self.sqlite_conn.commit()
            safe_print(f"INFO: تم إنشاء indexes في SQLite بنجاح.")
        except Exception as e:
            safe_print(f"WARNING: فشل إنشاء بعض indexes في SQLite: {e}")

    def _optimize_sqlite_performance(self):
        """
        ⚡ تحسين أداء SQLite للسرعة القصوى
        """
        try:
            safe_print(f"INFO: جاري تحسين أداء قاعدة البيانات...")

            # تفعيل WAL mode للأداء الأفضل
            self.sqlite_cursor.execute("PRAGMA journal_mode=WAL")

            # زيادة حجم الـ cache
            self.sqlite_cursor.execute("PRAGMA cache_size=10000")

            # تفعيل memory-mapped I/O
            self.sqlite_cursor.execute("PRAGMA mmap_size=268435456")  # 256MB

            # تحسين synchronous mode
            self.sqlite_cursor.execute("PRAGMA synchronous=NORMAL")

            # تفعيل temp store في الذاكرة
            self.sqlite_cursor.execute("PRAGMA temp_store=MEMORY")

            self.sqlite_conn.commit()
            safe_print(f"INFO: تم تحسين أداء قاعدة البيانات بنجاح.")
        except Exception as e:
            safe_print(f"WARNING: فشل تحسين أداء قاعدة البيانات: {e}")

    def _init_mongo_indexes(self):
        """
        إنشاء indexes في MongoDB لتحسين الأداء
        """
        try:
            safe_print(f"INFO: جاري إنشاء indexes في MongoDB...")

            # Indexes لـ sync_queue
            self.mongo_db.sync_queue.create_index([("status", 1)])
            self.mongo_db.sync_queue.create_index([("priority", 1), ("status", 1)])
            self.mongo_db.sync_queue.create_index([("entity_type", 1), ("entity_id", 1)])

            # Indexes لـ projects
            self.mongo_db.projects.create_index([("client_id", 1)])
            self.mongo_db.projects.create_index([("status", 1)])
            self.mongo_db.projects.create_index([("start_date", -1)])

            # Indexes لـ clients
            self.mongo_db.clients.create_index([("name", 1)])
            self.mongo_db.clients.create_index([("status", 1)])

            # Indexes لـ journal_entries
            self.mongo_db.journal_entries.create_index([("date", -1)])
            self.mongo_db.journal_entries.create_index([("related_document_id", 1)])

            # Indexes لـ expenses
            self.mongo_db.expenses.create_index([("date", -1)])
            self.mongo_db.expenses.create_index([("project_id", 1)])

            # Indexes لـ notifications
            self.mongo_db.notifications.create_index([("is_read", 1)])
            self.mongo_db.notifications.create_index([("type", 1)])
            self.mongo_db.notifications.create_index([("created_at", -1)])
            self.mongo_db.notifications.create_index([("expires_at", 1)])

            safe_print(f"INFO: تم إنشاء indexes في MongoDB بنجاح.")
        except Exception as e:
            safe_print(f"WARNING: فشل إنشاء بعض indexes في MongoDB: {e}")

    def is_online(self) -> bool:
        """ دالة بسيطة لمعرفة حالة الاتصال """
        return bool(self.online)

    # --- دوال التعامل مع العملاء (كمثال) ---

    def create_client(self, client_data: schemas.Client) -> schemas.Client:
        """
        إنشاء عميل جديد (بذكاء)
        1. يحفظ في SQLite دائماً (بحالة 'new_offline').
        2. يحاول الحفظ في Mongo لو فيه نت.
        """
        # ✅ فحص التكرار قبل الإضافة (بالاسم - exact match)
        existing_client = self.get_client_by_name(client_data.name)
        if existing_client:
            safe_print(f"WARNING: العميل '{client_data.name}' موجود بالفعل!")
            raise Exception(f"العميل '{client_data.name}' موجود بالفعل في النظام")

        # ✅ فحص التكرار بالاسم (case insensitive)
        similar_client = self._get_similar_client(client_data.name)
        if similar_client:
            safe_print(f"WARNING: يوجد عميل مشابه '{similar_client.name}'!")
            raise Exception(f"يوجد عميل مشابه بالاسم '{similar_client.name}'")

        # ✅ فحص التكرار بالهاتف أيضاً
        if client_data.phone:
            existing_by_phone = self._get_client_by_phone(client_data.phone)
            if existing_by_phone:
                safe_print(f"WARNING: العميل برقم الهاتف '{client_data.phone}' موجود بالفعل!")
                raise Exception(f"يوجد عميل آخر بنفس رقم الهاتف '{client_data.phone}'")

        now = datetime.now()
        client_data.created_at = now
        client_data.last_modified = now
        client_data.sync_status = 'new_offline'
        client_data.status = schemas.ClientStatus.ACTIVE

        # 1. الحفظ في SQLite (الأوفلاين أولاً)
        sql = """
            INSERT INTO clients (
                sync_status, created_at, last_modified, name, company_name, email,
                phone, address, country, vat_number, status,
                client_type, work_field, logo_path, logo_data, client_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.sqlite_cursor.execute(sql, (
            client_data.sync_status, now, now, client_data.name, client_data.company_name,
            client_data.email, client_data.phone, client_data.address, client_data.country,
            client_data.vat_number, client_data.status.value,
            client_data.client_type, client_data.work_field,
            client_data.logo_path, client_data.logo_data, client_data.client_notes
        ))
        self.sqlite_conn.commit()

        local_id = self.sqlite_cursor.lastrowid
        safe_print(f"INFO: تم حفظ العميل '{client_data.name}' محلياً (ID: {local_id}).")

        # 2. محاولة الحفظ في MongoDB (الأونلاين)
        if self.online:
            try:
                # نحول الـ Pydantic model لـ dict عشان Mongo يفهمه
                client_dict = client_data.model_dump(exclude={"_mongo_id"})
                
                # ⚡ التأكد من حفظ logo_data بشكل صحيح
                if client_data.logo_data:
                    client_dict['logo_data'] = client_data.logo_data
                    safe_print(f"INFO: [Repo] حفظ logo_data ({len(client_data.logo_data)} حرف) في MongoDB")
                
                result = self.mongo_db.clients.insert_one(client_dict)
                mongo_id = str(result.inserted_id)

                # تحديث الـ SQLite بالـ Mongo ID وتغيير الحالة لـ 'synced'
                client_data._mongo_id = mongo_id
                client_data.sync_status = 'synced'

                self.sqlite_cursor.execute(
                    "UPDATE clients SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                    (mongo_id, 'synced', local_id)
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة العميل '{client_data.name}' أونلاين (Mongo ID: {mongo_id}).")

            except Exception as e:
                safe_print(f"ERROR: فشل مزامنة العميل الجديد '{client_data.name}': {e}")
                # (سيبقى الـ status 'new_offline' ليتم مزامنته لاحقاً)

        return client_data

    def update_client(self, client_id: str, client_data: schemas.Client) -> schemas.Client | None:
        """
        (جديدة) تحديث بيانات عميل موجود.
        """
        safe_print(f"INFO: [Repo] جاري تحديث العميل ID: {client_id}...")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            sql = """
                UPDATE clients SET
                    name = ?, company_name = ?, email = ?, phone = ?,
                    address = ?, country = ?, vat_number = ?, status = ?,
                    client_type = ?, work_field = ?, logo_path = ?, logo_data = ?, client_notes = ?,
                    last_modified = ?, sync_status = 'modified_offline'
                WHERE id = ? OR _mongo_id = ?
            """
            params = (
                client_data.name, client_data.company_name, client_data.email,
                client_data.phone, client_data.address, client_data.country,
                client_data.vat_number, client_data.status.value,
                client_data.client_type, client_data.work_field,
                client_data.logo_path, client_data.logo_data, client_data.client_notes,
                now_iso, client_id, client_id
            )
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث العميل (SQLite): {e}")
            return None

        if self.online:
            try:
                update_dict = client_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                update_dict['last_modified'] = now_dt
                update_dict['status'] = client_data.status.value
                
                # ⚡ التعامل الذكي مع logo_data
                logo_data_value = client_data.logo_data
                logo_path_value = client_data.logo_path
                
                if logo_data_value:
                    # صورة جديدة - رفعها للسحابة
                    update_dict['logo_data'] = logo_data_value
                    safe_print(f"INFO: [Repo] 📷 حفظ logo_data ({len(logo_data_value)} حرف) في MongoDB")
                elif not logo_path_value:
                    # logo_data فارغ و logo_path فارغ = حذف صريح للصورة
                    update_dict['logo_data'] = ""
                    update_dict['logo_path'] = ""
                    safe_print(f"INFO: [Repo] 🗑️ حذف logo_data من MongoDB (حذف صريح)")
                else:
                    # logo_data فارغ لكن logo_path موجود = الاحتفاظ بالقديم
                    try:
                        existing = self.mongo_db.clients.find_one(
                            {"$or": [{"_id": self._to_objectid(client_id)}, {"_mongo_id": client_id}]},
                            {"logo_data": 1}
                        )
                        if existing and existing.get('logo_data'):
                            del update_dict['logo_data']
                            safe_print(f"INFO: [Repo] 📷 الاحتفاظ بـ logo_data الموجود في MongoDB")
                    except Exception:
                        pass

                self.mongo_db.clients.update_one(
                    {"$or": [{"_id": self._to_objectid(client_id)}, {"_mongo_id": client_id}]},
                    {"$set": update_dict}
                )

                self.sqlite_cursor.execute(
                    "UPDATE clients SET sync_status = 'synced' WHERE id = ? OR _mongo_id = ?",
                    (client_id, client_id)
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: [Repo] تم مزامنة تحديث العميل ID: {client_id} أونلاين.")

            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل تحديث العميل (Mongo): {e}")

        return client_data

    def get_all_clients(self) -> list[schemas.Client]:
        """
        ⚡ جلب كل العملاء النشطين (SQLite أولاً للسرعة)
        """
        active_status = schemas.ClientStatus.ACTIVE.value

        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            self.sqlite_cursor.execute("SELECT * FROM clients WHERE status = ?", (active_status,))
            rows = self.sqlite_cursor.fetchall()
            clients_list = [schemas.Client(**dict(row)) for row in rows]
            
            # ⚡ تسجيل عدد العملاء اللي عندهم صور
            clients_with_logo = sum(1 for c in clients_list if c.logo_data)
            safe_print(f"INFO: تم جلب {len(clients_list)} عميل نشط من المحلي ({clients_with_logo} عميل لديه صورة)")
            
            return clients_list
        except Exception as e:
            safe_print(f"ERROR: فشل جلب العملاء من SQLite: {e}")

        # Fallback إلى MongoDB إذا فشل SQLite
        if self.online:
            try:
                clients_data = list(self.mongo_db.clients.find({"status": active_status}))
                clients_list = []
                for c in clients_data:
                    try:
                        mongo_id = str(c.pop('_id'))
                        c.pop('_mongo_id', None)
                        c.pop('mongo_id', None)
                        clients_list.append(schemas.Client(**c, _mongo_id=mongo_id))
                    except Exception:
                        continue
                safe_print(f"INFO: تم جلب {len(clients_list)} عميل نشط من الأونلاين.")
                return clients_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب العملاء من MongoDB: {e}")

        return []


    def get_archived_clients(self) -> list[schemas.Client]:
        """ جلب كل العملاء المؤرشفين فقط """
        archived_status = schemas.ClientStatus.ARCHIVED.value
        if self.online:
            try:
                clients_data = list(self.mongo_db.clients.find({"status": archived_status}))
                clients_list = []
                for c in clients_data:
                    mongo_id = str(c.pop('_id'))
                    c.pop('_mongo_id', None)
                    c.pop('mongo_id', None)
                    clients_list.append(schemas.Client(**c, _mongo_id=mongo_id))
                return clients_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب العملاء المؤرشفين (Mongo): {e}.")

        self.sqlite_cursor.execute("SELECT * FROM clients WHERE status = ?", (archived_status,))
        rows = self.sqlite_cursor.fetchall()
        return [schemas.Client(**dict(row)) for row in rows]

    def get_client_by_id(self, client_id: str) -> schemas.Client | None:
        """ جلب عميل واحد بالـ ID (بذكاء) """
        if self.online:
            try:
                lookup_id = self._to_objectid(client_id)
                client_data = self.mongo_db.clients.find_one({"_id": lookup_id})
                if client_data:
                    mongo_id = str(client_data.pop('_id'))
                    client_data.pop('_mongo_id', None)
                    client_data.pop('mongo_id', None)
                    client = schemas.Client(**client_data, _mongo_id=mongo_id)
                    safe_print(f"INFO: تم جلب العميل (MongoID: {client_id}) من الأونلاين.")
                    return client
            except Exception as e:
                safe_print(f"WARNING: فشل البحث بالـ MongoID {client_id}: {e}. جاري البحث المحلي...")

        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM clients WHERE id = ? OR _mongo_id = ? OR name = ?",
                (client_id, client_id, client_id)
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                client = schemas.Client(**dict(row))
                safe_print(f"INFO: تم جلب العميل (ID: {client_id}) من المحلي.")
                return client
        except Exception as e:
            safe_print(f"ERROR: فشل جلب العميل (ID: {client_id}) من المحلي: {e}.")

        return None

    def _to_objectid(self, item_id: str):
        """محاولة تحويل النص إلى ObjectId صالح لتجنب أخطاء InvalidId."""
        try:
            from bson import ObjectId
            if isinstance(item_id, str) and len(item_id) == 24:
                return ObjectId(item_id)
        except Exception:
            pass
        return item_id

    def _get_client_by_phone(self, phone: str) -> schemas.Client | None:
        """البحث عن عميل برقم الهاتف"""
        if not phone:
            return None

        # تنظيف رقم الهاتف
        clean_phone = phone.strip().replace(" ", "").replace("-", "")

        if self.online:
            try:
                # البحث بالرقم الأصلي أو المنظف
                client_data = self.mongo_db.clients.find_one({
                    "$or": [
                        {"phone": phone},
                        {"phone": clean_phone}
                    ],
                    "status": {"$ne": schemas.ClientStatus.ARCHIVED.value}
                })
                if client_data:
                    mongo_id = str(client_data.pop('_id'))
                    client_data.pop('_mongo_id', None)
                    client_data.pop('mongo_id', None)
                    return schemas.Client(**client_data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"WARNING: فشل البحث بالهاتف (Mongo): {e}")

        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM clients WHERE (phone = ? OR phone = ?) AND status != ?",
                (phone, clean_phone, schemas.ClientStatus.ARCHIVED.value)
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Client(**dict(row))
        except Exception as e:
            safe_print(f"WARNING: فشل البحث بالهاتف (SQLite): {e}")

        return None

    def _get_similar_project(self, name: str, client_id: str) -> schemas.Project | None:
        """البحث عن مشروع مشابه لنفس العميل (case insensitive)"""
        if not name or not client_id:
            return None

        name_lower = name.strip().lower()

        if self.online:
            try:
                # البحث case insensitive في MongoDB
                project_data = self.mongo_db.projects.find_one({
                    "client_id": client_id,
                    "name": {"$regex": f"^{name_lower}$", "$options": "i"},
                    "status": {"$ne": "مؤرشف"}
                })
                if project_data:
                    mongo_id = str(project_data.pop('_id'))
                    project_data.pop('_mongo_id', None)
                    project_data.pop('mongo_id', None)
                    if 'items' not in project_data or project_data['items'] is None:
                        project_data['items'] = []
                    elif isinstance(project_data['items'], str):
                        try:
                            project_data['items'] = json.loads(project_data['items'])
                        except (json.JSONDecodeError, TypeError):
                            project_data['items'] = []
                    if 'currency' not in project_data or project_data['currency'] is None:
                        project_data['currency'] = 'EGP'
                    return schemas.Project(**project_data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"WARNING: فشل البحث عن مشروع مشابه (Mongo): {e}")

        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM projects WHERE client_id = ? AND LOWER(name) = ? AND status != ?",
                (client_id, name_lower, "مؤرشف")
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                row_dict = dict(row)
                if isinstance(row_dict.get('items'), str):
                    try:
                        row_dict['items'] = json.loads(row_dict['items'])
                    except (json.JSONDecodeError, TypeError):
                        row_dict['items'] = []
                # ⚡ معالجة milestones (JSON string -> list)
                if isinstance(row_dict.get('milestones'), str):
                    try:
                        row_dict['milestones'] = json.loads(row_dict['milestones'])
                    except (json.JSONDecodeError, TypeError):
                        row_dict['milestones'] = []
                return schemas.Project(**row_dict)
        except Exception as e:
            safe_print(f"WARNING: فشل البحث عن مشروع مشابه (SQLite): {e}")

        return None

    def _get_duplicate_payment(self, project_id: str, date, amount: float) -> schemas.Payment | None:
        """البحث عن دفعة مكررة (نفس المشروع + نفس التاريخ + نفس المبلغ)"""
        if not project_id:
            return None

        date_str = date.isoformat() if hasattr(date, 'isoformat') else str(date)
        date_str_short = date_str[:10]  # YYYY-MM-DD فقط

        if self.online:
            try:
                # البحث في MongoDB
                payment_data = self.mongo_db.payments.find_one({
                    "project_id": project_id,
                    "amount": amount,
                    "$or": [
                        {"date": {"$regex": f"^{date_str_short}"}},
                        {"date": date}
                    ]
                })
                if payment_data:
                    mongo_id = str(payment_data.pop('_id'))
                    payment_data.pop('_mongo_id', None)
                    payment_data.pop('mongo_id', None)
                    return schemas.Payment(**payment_data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"WARNING: فشل البحث عن دفعة مكررة (Mongo): {e}")

        try:
            self.sqlite_cursor.execute(
                """SELECT * FROM payments
                   WHERE project_id = ? AND amount = ? AND date LIKE ?""",
                (project_id, amount, f"{date_str_short}%")
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Payment(**dict(row))
        except Exception as e:
            safe_print(f"WARNING: فشل البحث عن دفعة مكررة (SQLite): {e}")

        return None

    def _get_similar_client(self, name: str) -> schemas.Client | None:
        """البحث عن عميل مشابه (case insensitive + تشابه جزئي)"""
        if not name:
            return None

        name_lower = name.strip().lower()

        if self.online:
            try:
                # البحث case insensitive في MongoDB
                client_data = self.mongo_db.clients.find_one({
                    "name": {"$regex": f"^{name_lower}$", "$options": "i"},
                    "status": {"$ne": schemas.ClientStatus.ARCHIVED.value}
                })
                if client_data:
                    mongo_id = str(client_data.pop('_id'))
                    client_data.pop('_mongo_id', None)
                    client_data.pop('mongo_id', None)
                    return schemas.Client(**client_data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"WARNING: فشل البحث عن عميل مشابه (Mongo): {e}")

        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM clients WHERE LOWER(name) = ? AND status != ?",
                (name_lower, schemas.ClientStatus.ARCHIVED.value)
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Client(**dict(row))
        except Exception as e:
            safe_print(f"WARNING: فشل البحث عن عميل مشابه (SQLite): {e}")

        return None

    def archive_client_by_id(self, client_id: str) -> bool:
        """
        (جديدة) أرشفة عميل (Soft Delete) عن طريق تحديث حالته.
        """
        safe_print(f"INFO: [Repo] جاري أرشفة العميل ID: {client_id}")

        archive_status = schemas.ClientStatus.ARCHIVED.value
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            client_id_num = int(client_id)
        except ValueError:
            client_id_num = 0

        self.sqlite_cursor.execute(
            "UPDATE clients SET status = ?, last_modified = ?, sync_status = 'modified_offline' WHERE id = ? OR _mongo_id = ?",
            (archive_status, now_iso, client_id_num, client_id)
        )
        self.sqlite_conn.commit()

        if self.online:
            try:
                self.mongo_db.clients.update_one(
                    {"$or": [{"_id": self._to_objectid(client_id)}, {"_mongo_id": client_id}, {"id": client_id_num}]},
                    {"$set": {"status": archive_status, "last_modified": now_dt}}
                )
                self.sqlite_cursor.execute(
                    "UPDATE clients SET sync_status = 'synced' WHERE id = ? OR _mongo_id = ?",
                    (client_id_num, client_id)
                )
                self.sqlite_conn.commit()
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل أرشفة العميل (Mongo): {e}")
                return False

        return True

    def delete_client_permanently(self, client_id: str) -> bool:
        """
        حذف عميل نهائياً من قاعدة البيانات (Hard Delete)
        """
        safe_print(f"INFO: [Repo] جاري حذف العميل نهائياً ID: {client_id}")

        try:
            client_id_num = int(client_id)
        except ValueError:
            client_id_num = 0

        # جلب _mongo_id قبل الحذف
        self.sqlite_cursor.execute(
            "SELECT id, _mongo_id, name FROM clients WHERE id = ? OR _mongo_id = ?",
            (client_id_num, client_id)
        )
        row = self.sqlite_cursor.fetchone()
        
        if row:
            local_id = row[0]
            mongo_id = row[1] if row[1] else client_id
            client_name = row[2]
            safe_print(f"INFO: [Repo] العميل المراد حذفه: {client_name} (local_id={local_id}, mongo_id={mongo_id})")
        else:
            safe_print(f"WARNING: [Repo] العميل غير موجود في SQLite! client_id={client_id}")
            mongo_id = client_id
            local_id = client_id_num

        # حذف من SQLite
        self.sqlite_cursor.execute(
            "DELETE FROM clients WHERE id = ? OR _mongo_id = ?",
            (local_id, client_id)
        )
        deleted_rows = self.sqlite_cursor.rowcount
        self.sqlite_conn.commit()
        
        if deleted_rows > 0:
            safe_print(f"INFO: [Repo] ✅ تم حذف {deleted_rows} سجل من SQLite")
        else:
            safe_print(f"WARNING: [Repo] ❌ لم يتم حذف أي سجل من SQLite!")

        # حذف من MongoDB
        if self.online:
            try:
                result = self.mongo_db.clients.delete_one(
                    {"$or": [
                        {"_id": self._to_objectid(mongo_id)},
                        {"_id": self._to_objectid(client_id)}
                    ]}
                )
                if result.deleted_count > 0:
                    safe_print(f"INFO: [Repo] ✅ تم حذف العميل من MongoDB")
                else:
                    safe_print(f"WARNING: [Repo] العميل غير موجود في MongoDB")
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل حذف العميل من MongoDB: {e}")

        return deleted_rows > 0

    def update_journal_entry_by_doc_id(self, doc_id: str, new_lines: list[schemas.JournalEntryLine], new_description: str) -> bool:
        """
        (جديدة) تحديث قيد يومية موجود (للروبوت المحاسبي).
        """
        safe_print(f"INFO: [Repo] جاري تحديث القيد المحاسبي المرتبط بـ {doc_id}...")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        lines_json = json.dumps([line.model_dump() for line in new_lines])

        try:
            sql = """
                UPDATE journal_entries SET
                    lines = ?, description = ?, last_modified = ?, sync_status = 'modified_offline'
                WHERE related_document_id = ?
            """
            params = (lines_json, new_description, now_iso, doc_id)
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث القيد (SQLite): {e}")
            return False

        if self.online:
            try:
                self.mongo_db.journal_entries.update_one(
                    {"related_document_id": doc_id},
                    {
                        "$set": {
                            "lines": [line.model_dump() for line in new_lines],
                            "description": new_description,
                            "last_modified": now_dt
                        }
                    }
                )
                self.sqlite_cursor.execute(
                    "UPDATE journal_entries SET sync_status = 'synced' WHERE related_document_id = ?",
                    (doc_id,)
                )
                self.sqlite_conn.commit()
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل تحديث القيد (Mongo): {e}")

        return True

    def get_client_by_name(self, name: str) -> schemas.Client | None:
        """ (جديدة) جلب عميل واحد بالاسم (بذكاء) """
        if self.online:
            try:
                client_data = self.mongo_db.clients.find_one({"name": name})
                if client_data:
                    mongo_id = str(client_data.pop('_id'))
                    client_data.pop('_mongo_id', None)
                    client_data.pop('mongo_id', None)
                    client = schemas.Client(**client_data, _mongo_id=mongo_id)
                    safe_print(f"INFO: تم جلب العميل (Name: {name}) من الأونلاين.")
                    return client
            except Exception as e:
                safe_print(f"ERROR: فشل جلب العميل بالاسم (Mongo): {e}.")

        try:
            self.sqlite_cursor.execute("SELECT * FROM clients WHERE name = ?", (name,))
            row = self.sqlite_cursor.fetchone()
            if row:
                client = schemas.Client(**dict(row))
                safe_print(f"INFO: تم جلب العميل (Name: {name}) من المحلي.")
                return client
        except Exception as e:
            safe_print(f"ERROR: فشل جلب العميل بالاسم (SQLite): {e}.")

        return None

    # --- دوال التعامل مع الحسابات ---

    def create_account(self, account_data: schemas.Account) -> schemas.Account:
        """ ⚡ إنشاء حساب جديد - محلي أولاً ثم مزامنة في الخلفية """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        account_data.created_at = now_dt
        account_data.last_modified = now_dt
        account_data.sync_status = 'new_offline'

        # ⚡ 1. الحفظ في SQLite فوراً (سريع جداً)
        sql = """
            INSERT INTO accounts (sync_status, created_at, last_modified, name, code, type, parent_id, balance, currency, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        currency_value = account_data.currency.value if account_data.currency else 'EGP'
        parent_value = account_data.parent_code or account_data.parent_id
        params = (
            account_data.sync_status, now_iso, now_iso, account_data.name, account_data.code,
            account_data.type.value, parent_value, account_data.balance,
            currency_value, account_data.description
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        safe_print(f"INFO: ✅ تم حفظ الحساب '{account_data.name}' محلياً (ID: {local_id}).")

        # ⚡ 2. مزامنة مع MongoDB في الخلفية (لا يعطل الواجهة)
        if self.online:
            def sync_to_mongo():
                try:
                    account_dict = account_data.model_dump(exclude={"_mongo_id"})
                    account_dict['type'] = account_data.type.value

                    result = self.mongo_db.accounts.insert_one(account_dict)
                    mongo_id = str(result.inserted_id)

                    self.sqlite_cursor.execute(
                        "UPDATE accounts SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                        (mongo_id, 'synced', local_id)
                    )
                    self.sqlite_conn.commit()
                    safe_print(f"INFO: ✅ تم مزامنة الحساب '{account_data.name}' مع السيرفر (خلفية)")

                except Exception as e:
                    if "E11000 duplicate key" in str(e):
                        safe_print(f"WARNING: الحساب بكود '{account_data.code}' موجود بالفعل أونلاين.")
                        try:
                            existing = self.mongo_db.accounts.find_one({"code": account_data.code})
                            if existing:
                                mongo_id = str(existing['_id'])
                                self.sqlite_cursor.execute(
                                    "UPDATE accounts SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                                    (mongo_id, 'synced', local_id)
                                )
                                self.sqlite_conn.commit()
                        except Exception:
                            pass
                    else:
                        safe_print(f"WARNING: فشل مزامنة الحساب '{account_data.name}': {e}")
            
            import threading
            threading.Thread(target=sync_to_mongo, daemon=True).start()

        return account_data

    def get_account_by_code(self, code: str) -> schemas.Account | None:
        """
        جلب حساب معين عن طريق الكود (بذكاء).
        ده ضروري جداً للروبوت المحاسبي.
        """
        if self.online:
            try:
                account_data = self.mongo_db.accounts.find_one({"code": code})
                if account_data:
                    mongo_id = str(account_data.pop('_id'))
                    account_data.pop('_mongo_id', None)
                    account_data.pop('mongo_id', None)
                    account = schemas.Account(**account_data, _mongo_id=mongo_id)
                    safe_print(f"INFO: تم جلب الحساب (Code: {code}) من الأونلاين.")
                    return account
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الحساب (Code: {code}) من Mongo: {e}.")

        # الجلب من SQLite في حالة الأوفلاين أو عدم وجوده أونلاين
        try:
            self.sqlite_cursor.execute("SELECT * FROM accounts WHERE code = ?", (code,))
            row = self.sqlite_cursor.fetchone()
            if row:
                account = schemas.Account(**dict(row))
                safe_print(f"INFO: تم جلب الحساب (Code: {code}) من المحلي.")
                return account
        except Exception as e:
            safe_print(f"ERROR: فشل جلب الحساب (Code: {code}) من المحلي: {e}.")

        return None # لو الحساب مش موجود خالص

    def get_all_accounts(self) -> list[schemas.Account]:
        """ ⚡ جلب كل الحسابات (SQLite أولاً للسرعة) - يستخدم cursor منفصل """
        # ⚡ جلب من SQLite أولاً (سريع جداً) - cursor منفصل لتجنب Recursive cursor
        try:
            with self._lock:
                temp_cursor = self.sqlite_conn.cursor()
                temp_cursor.execute("SELECT * FROM accounts WHERE sync_status != 'deleted'")
                rows = temp_cursor.fetchall()
                temp_cursor.close()
            if rows:
                accounts_list = [schemas.Account(**dict(row)) for row in rows]
                safe_print(f"INFO: تم جلب {len(accounts_list)} حساب من المحلي (SQLite).")
                return accounts_list
        except Exception as e:
            safe_print(f"ERROR: فشل جلب الحسابات من SQLite: {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                accounts_data = list(self.mongo_db.accounts.find())
                if accounts_data:
                    accounts_list = []
                    for acc in accounts_data:
                        mongo_id = str(acc.pop('_id'))
                        acc.pop('_mongo_id', None)
                        acc.pop('mongo_id', None)
                        accounts_list.append(schemas.Account(**acc, _mongo_id=mongo_id))
                    safe_print(f"INFO: تم جلب {len(accounts_list)} حساب من الأونلاين (MongoDB).")
                    return accounts_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الحسابات من Mongo: {e}")

        return []

    def get_account_by_id(self, account_id: str) -> schemas.Account | None:
        """ ⚡ جلب حساب واحد بالـ ID - SQLite أولاً للسرعة """
        try:
            account_id_num = int(account_id)
        except ValueError:
            account_id_num = 0

        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            self.sqlite_cursor.execute("SELECT * FROM accounts WHERE id = ? OR _mongo_id = ?", (account_id_num, account_id))
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Account(**dict(row))
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الحساب {account_id} (SQLite): {e}")

        return None

    # --- User Management Methods ---

    def create_user(self, user) -> str:
        """إنشاء مستخدم جديد"""
        try:
            from datetime import datetime
            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            # حفظ في SQLite أولاً
            sql = """
                INSERT INTO users (username, password_hash, role, full_name, email, is_active, created_at, last_modified, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new_offline')
            """
            # التأكد من تحويل الـ role بشكل صحيح
            role_value = user.role.value if hasattr(user.role, 'value') else str(user.role)

            params = (
                user.username,
                user.password_hash,
                role_value,
                user.full_name,
                user.email,
                1 if user.is_active else 0,
                now_iso,
                now_iso
            )

            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
            local_id = str(self.sqlite_cursor.lastrowid)

            # محاولة الحفظ في MongoDB
            if self.online:
                try:
                    # تحويل User object إلى dict
                    user_dict = {
                        'username': user.username,
                        'password_hash': user.password_hash,
                        'role': role_value,
                        'full_name': user.full_name,
                        'email': user.email,
                        'is_active': user.is_active,
                        'created_at': now_dt,
                        'last_modified': now_dt
                    }
                    result = self.mongo_db.users.insert_one(user_dict)
                    mongo_id = str(result.inserted_id)

                    # تحديث الـ mongo_id في SQLite
                    self.sqlite_cursor.execute(
                        "UPDATE users SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
                        (mongo_id, local_id)
                    )
                    self.sqlite_conn.commit()

                    safe_print(f"INFO: [Repository] تم إنشاء مستخدم: {user.username} (MongoDB + SQLite)")
                    return mongo_id
                except Exception as e:
                    safe_print(f"WARNING: [Repository] فشل حفظ المستخدم في MongoDB: {e}")

            safe_print(f"INFO: [Repository] تم إنشاء مستخدم: {user.username} (SQLite فقط)")
            return local_id

        except Exception as e:
            safe_print(f"ERROR: [Repository] فشل إنشاء المستخدم: {e}")
            raise

    def get_user_by_username(self, username: str):
        """جلب مستخدم بالاسم"""
        try:
            from core.auth_models import User, UserRole

            # البحث في MongoDB أولاً
            if self.online:
                try:
                    user_data = self.mongo_db.users.find_one({"username": username})
                    if user_data:
                        user_data['_mongo_id'] = str(user_data['_id'])
                        user_data['role'] = UserRole(user_data['role'])
                        # تحويل datetime إلى string
                        if 'created_at' in user_data and hasattr(user_data['created_at'], 'isoformat'):
                            user_data['created_at'] = user_data['created_at'].isoformat()
                        if 'last_login' in user_data and hasattr(user_data['last_login'], 'isoformat'):
                            user_data['last_login'] = user_data['last_login'].isoformat()
                        return User(**user_data)
                except Exception as e:
                    safe_print(f"WARNING: [Repository] فشل جلب المستخدم من MongoDB: {e}")

            # البحث في SQLite
            self.sqlite_cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = self.sqlite_cursor.fetchone()
            if row:
                user_data = dict(row)
                user_data['id'] = str(user_data['id'])  # تحويل ID إلى string
                user_data['role'] = UserRole(user_data['role'])
                user_data['is_active'] = bool(user_data['is_active'])

                # تحويل custom_permissions من JSON string إلى dict
                if user_data.get('custom_permissions'):
                    try:
                        import json
                        user_data['custom_permissions'] = json.loads(user_data['custom_permissions'])
                    except (json.JSONDecodeError, TypeError):
                        user_data['custom_permissions'] = None

                return User(**user_data)

            return None
        except Exception as e:
            safe_print(f"ERROR: [Repository] فشل جلب المستخدم: {e}")
            return None

    def update_user_by_username(self, username: str, update_data: dict) -> bool:
        """تحديث بيانات مستخدم باستخدام اسم المستخدم (أكثر أماناً)"""
        try:
            import json
            from datetime import datetime
            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            safe_print(f"INFO: [Repository] جاري تحديث المستخدم: {username}")
            safe_print(f"INFO: [Repository] البيانات المراد تحديثها: {update_data}")

            # تحديث في SQLite
            update_data_copy = update_data.copy()
            update_data_copy['last_modified'] = now_iso
            update_data_copy['sync_status'] = 'modified_offline'

            # تحويل القواميس إلى JSON strings للـ SQLite
            sqlite_data = update_data_copy.copy()
            for key, value in sqlite_data.items():
                if isinstance(value, dict):
                    sqlite_data[key] = json.dumps(value, ensure_ascii=False)

            # التحقق من صحة أسماء الأعمدة للحماية من SQL Injection
            import re
            valid_columns = {k for k in sqlite_data.keys() if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', k)}
            filtered_data = {k: v for k, v in sqlite_data.items() if k in valid_columns}

            set_clause = ", ".join([f"{key} = ?" for key in filtered_data.keys()])
            values = list(filtered_data.values())
            values.append(username)  # للـ WHERE clause

            sql = f"UPDATE users SET {set_clause} WHERE username = ?"

            safe_print(f"INFO: [Repository] SQL: {sql}")
            safe_print(f"INFO: [Repository] Values: {values}")

            self.sqlite_cursor.execute(sql, values)
            self.sqlite_conn.commit()

            rows_affected = self.sqlite_cursor.rowcount
            safe_print(f"INFO: [Repository] تم تحديث {rows_affected} صف في SQLite")

            # تحديث في MongoDB
            if self.online and self.mongo_db is not None:
                try:
                    mongo_update = update_data.copy()
                    mongo_update['last_modified'] = now_dt

                    result = self.mongo_db.users.update_one(
                        {"username": username},
                        {"$set": mongo_update}
                    )
                    safe_print(f"INFO: [Repository] تم تحديث {result.modified_count} مستخدم في MongoDB")

                    # تحديث حالة المزامنة
                    self.sqlite_cursor.execute(
                        "UPDATE users SET sync_status = 'synced' WHERE username = ?",
                        (username,)
                    )
                    self.sqlite_conn.commit()

                except Exception as e:
                    safe_print(f"WARNING: [Repository] فشل تحديث المستخدم في MongoDB: {e}")

            return rows_affected > 0
        except Exception as e:
            safe_print(f"ERROR: [Repository] فشل تحديث المستخدم: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_user(self, user_id: str, update_data: dict) -> bool:
        """تحديث بيانات مستخدم باستخدام ID - يستخدم update_user_by_username داخلياً"""
        try:
            safe_print(f"INFO: [Repository] جاري تحديث المستخدم بـ ID: {user_id}")
            safe_print(f"INFO: [Repository] البيانات المراد تحديثها: {update_data}")

            # أولاً: التحقق من وجود المستخدم وجلب username
            username = None
            self.sqlite_cursor.execute(
                "SELECT username FROM users WHERE id = ? OR _mongo_id = ?",
                (user_id, user_id)
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                username = row[0]
                safe_print(f"INFO: [Repository] تم العثور على المستخدم في SQLite: {username}")
            else:
                # محاولة البحث في MongoDB
                if self.online and self.mongo_db is not None:
                    try:
                        mongo_user = self.mongo_db.users.find_one({"_id": self._to_objectid(user_id)})
                        if mongo_user:
                            username = mongo_user.get('username')
                            safe_print(f"INFO: [Repository] تم العثور على المستخدم في MongoDB: {username}")
                    except Exception as e:
                        safe_print(f"WARNING: [Repository] فشل البحث في MongoDB: {e}")

            if not username:
                safe_print(f"ERROR: [Repository] المستخدم غير موجود بـ ID: {user_id}")
                return False

            # استخدام الدالة الجديدة للتحديث باستخدام username
            return self.update_user_by_username(username, update_data)

        except Exception as e:
            safe_print(f"ERROR: [Repository] فشل تحديث المستخدم: {e}")
            return False

    def get_all_users(self):
        """جلب جميع المستخدمين من MongoDB أو SQLite"""
        safe_print(f"INFO: [Repository] جاري جلب المستخدمين...")
        try:
            from core.auth_models import User, UserRole
            users = []

            # انتظار اكتمال الاتصال بـ MongoDB إذا كان جاري
            import time
            wait_count = 0
            while self._mongo_connecting and wait_count < 10:
                safe_print(f"INFO: [Repository] انتظار اتصال MongoDB... ({wait_count + 1}/10)")
                time.sleep(0.5)
                wait_count += 1

            safe_print(f"INFO: [Repository] حالة الاتصال: online={self.online}, mongo_db={self.mongo_db is not None}")

            # جلب من MongoDB أولاً
            if self.online and self.mongo_db is not None:
                try:
                    users_data = list(self.mongo_db.users.find())
                    safe_print(f"INFO: [Repository] وجدت {len(users_data)} مستخدم في MongoDB")
                    for user_data in users_data:
                        try:
                            # استخراج _id من MongoDB
                            mongo_id = str(user_data.pop('_id', ''))

                            # تحويل datetime إلى string
                            created_at = user_data.get('created_at')
                            if created_at and hasattr(created_at, 'isoformat'):
                                created_at = created_at.isoformat()
                            else:
                                created_at = str(created_at) if created_at else None

                            last_modified = user_data.get('last_modified')
                            if last_modified and hasattr(last_modified, 'isoformat'):
                                last_modified = last_modified.isoformat()

                            last_login = user_data.get('last_login')
                            if last_login and hasattr(last_login, 'isoformat'):
                                last_login = last_login.isoformat()

                            # تحويل role إلى enum
                            role_value = user_data.get('role', 'sales')
                            if isinstance(role_value, str):
                                role_enum = UserRole(role_value)
                            else:
                                role_enum = role_value

                            # إنشاء كائن User
                            user = User(
                                id=mongo_id,
                                mongo_id=mongo_id,
                                username=user_data.get('username', ''),
                                password_hash=user_data.get('password_hash', ''),
                                role=role_enum,
                                is_active=bool(user_data.get('is_active', True)),
                                full_name=user_data.get('full_name'),
                                email=user_data.get('email'),
                                created_at=created_at,
                                last_login=last_login,
                                custom_permissions=user_data.get('custom_permissions')
                            )
                            users.append(user)
                            safe_print(f"INFO: [Repository] تم تحويل مستخدم من MongoDB: {user.username}")
                        except Exception as e:
                            safe_print(f"WARNING: [Repository] فشل تحويل مستخدم من MongoDB: {e}")
                            import traceback
                            traceback.print_exc()
                            continue

                    if users:
                        safe_print(f"INFO: [Repository] تم جلب {len(users)} مستخدم من MongoDB")
                        return users
                except Exception as e:
                    safe_print(f"WARNING: [Repository] فشل جلب المستخدمين من MongoDB: {e}")
                    import traceback
                    traceback.print_exc()

            # جلب من SQLite
            safe_print(f"INFO: [Repository] جاري جلب المستخدمين من SQLite...")
            self.sqlite_cursor.execute("SELECT * FROM users")
            rows = self.sqlite_cursor.fetchall()
            safe_print(f"INFO: [Repository] وجدت {len(rows)} مستخدم في SQLite")

            for row in rows:
                try:
                    row_dict = dict(row)

                    # تحويل role إلى enum
                    role_value = row_dict.get('role', 'sales')
                    if isinstance(role_value, str):
                        role_enum = UserRole(role_value)
                    else:
                        role_enum = role_value

                    # تحويل custom_permissions من JSON string إلى dict
                    custom_perms = None
                    if row_dict.get('custom_permissions'):
                        try:
                            import json
                            custom_perms = json.loads(row_dict['custom_permissions'])
                        except (json.JSONDecodeError, TypeError):
                            custom_perms = None

                    # إنشاء كائن User مع الحقول المطلوبة فقط
                    user = User(
                        id=str(row_dict.get('id', '')),
                        mongo_id=row_dict.get('_mongo_id'),
                        username=row_dict.get('username', ''),
                        password_hash=row_dict.get('password_hash', ''),
                        role=role_enum,
                        is_active=bool(row_dict.get('is_active', 1)),
                        full_name=row_dict.get('full_name'),
                        email=row_dict.get('email'),
                        created_at=row_dict.get('created_at'),
                        last_login=row_dict.get('last_login'),
                        custom_permissions=custom_perms
                    )

                    users.append(user)
                    safe_print(f"INFO: [Repository] تم تحويل مستخدم: {user.username}")
                except Exception as e:
                    safe_print(f"WARNING: [Repository] فشل تحويل مستخدم من SQLite: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            safe_print(f"INFO: [Repository] تم جلب {len(users)} مستخدم إجمالاً")
            return users
        except Exception as e:
            safe_print(f"ERROR: [Repository] فشل جلب المستخدمين: {e}")
            import traceback
            traceback.print_exc()
            return []

    def sync_users_bidirectional(self) -> dict:
        """مزامنة المستخدمين ثنائية الاتجاه (من وإلى السحابة)"""
        result = {'uploaded': 0, 'downloaded': 0, 'errors': []}

        if not self.online or self.mongo_db is None:
            result['errors'].append("غير متصل بـ MongoDB")
            return result

        try:
            from datetime import datetime

            # === 1. رفع المستخدمين المحليين الجدد/المعدلين إلى السحابة ===
            safe_print(f"INFO: [Repository] 📤 جاري رفع المستخدمين المحليين إلى السحابة...")
            self.sqlite_cursor.execute("""
                SELECT * FROM users 
                WHERE sync_status IN ('new_offline', 'modified_offline', 'pending')
                   OR _mongo_id IS NULL
            """)
            local_pending = self.sqlite_cursor.fetchall()

            for row in local_pending:
                try:
                    user_data = dict(row)
                    username = user_data.get('username')
                    local_id = user_data.get('id')

                    existing_cloud = self.mongo_db.users.find_one({'username': username})

                    if existing_cloud:
                        mongo_id = str(existing_cloud['_id'])
                        update_data = {
                            'full_name': user_data.get('full_name'),
                            'email': user_data.get('email'),
                            'role': user_data.get('role'),
                            'is_active': bool(user_data.get('is_active', 1)),
                            'last_modified': datetime.now()
                        }
                        if user_data.get('password_hash'):
                            update_data['password_hash'] = user_data['password_hash']

                        self.mongo_db.users.update_one(
                            {'_id': existing_cloud['_id']},
                            {'$set': update_data}
                        )
                        self.sqlite_cursor.execute(
                            "UPDATE users SET _mongo_id=?, sync_status='synced' WHERE id=?",
                            (mongo_id, local_id)
                        )
                        result['uploaded'] += 1
                        safe_print(f"INFO: [Repository]   ✅ تم تحديث المستخدم في السحابة: {username}")
                    else:
                        new_user = {
                            'username': username,
                            'password_hash': user_data.get('password_hash'),
                            'full_name': user_data.get('full_name'),
                            'email': user_data.get('email'),
                            'role': user_data.get('role', 'sales'),
                            'is_active': bool(user_data.get('is_active', 1)),
                            'created_at': datetime.now(),
                            'last_modified': datetime.now()
                        }
                        insert_result = self.mongo_db.users.insert_one(new_user)
                        mongo_id = str(insert_result.inserted_id)
                        self.sqlite_cursor.execute(
                            "UPDATE users SET _mongo_id=?, sync_status='synced' WHERE id=?",
                            (mongo_id, local_id)
                        )
                        result['uploaded'] += 1
                        safe_print(f"INFO: [Repository]   ✅ تم رفع مستخدم جديد للسحابة: {username}")
                except Exception as e:
                    result['errors'].append(f"خطأ في رفع {username}: {e}")

            if result['uploaded'] > 0:
                self.sqlite_conn.commit()

            # === 2. تنزيل المستخدمين من السحابة ===
            safe_print(f"INFO: [Repository] 📥 جاري تنزيل المستخدمين من السحابة...")
            cloud_users = list(self.mongo_db.users.find())

            for u in cloud_users:
                try:
                    mongo_id = str(u['_id'])
                    username = u.get('username')

                    for field in ['created_at', 'last_modified', 'last_login']:
                        if field in u and hasattr(u[field], 'isoformat'):
                            u[field] = u[field].isoformat()

                    self.sqlite_cursor.execute(
                        "SELECT id, sync_status FROM users WHERE _mongo_id = ? OR username = ?",
                        (mongo_id, username)
                    )
                    exists = self.sqlite_cursor.fetchone()

                    if exists:
                        if exists[1] not in ('modified_offline', 'new_offline'):
                            self.sqlite_cursor.execute("""
                                UPDATE users SET
                                    full_name=?, email=?, role=?, is_active=?,
                                    password_hash=?, _mongo_id=?, sync_status='synced',
                                    last_modified=?
                                WHERE id=?
                            """, (
                                u.get('full_name'), u.get('email'), u.get('role'),
                                u.get('is_active', 1), u.get('password_hash'),
                                mongo_id, u.get('last_modified', datetime.now().isoformat()),
                                exists[0]
                            ))
                            result['downloaded'] += 1
                    else:
                        self.sqlite_cursor.execute("""
                            INSERT INTO users (
                                _mongo_id, username, full_name, email, role,
                                password_hash, is_active, sync_status, created_at, last_modified
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'synced', ?, ?)
                        """, (
                            mongo_id, username, u.get('full_name'), u.get('email'),
                            u.get('role'), u.get('password_hash'), u.get('is_active', 1),
                            u.get('created_at', datetime.now().isoformat()),
                            u.get('last_modified', datetime.now().isoformat())
                        ))
                        result['downloaded'] += 1
                        safe_print(f"INFO: [Repository]   ✅ تم تنزيل مستخدم جديد: {username}")
                except Exception as e:
                    result['errors'].append(f"خطأ في تنزيل {username}: {e}")

            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repository] ✅ تم مزامنة المستخدمين (رفع: {result['uploaded']}, تنزيل: {result['downloaded']})")

        except Exception as e:
            result['errors'].append(str(e))
            safe_print(f"ERROR: [Repository] فشل مزامنة المستخدمين: {e}")

        return result

    def update_account(self, account_id: str, account_data: schemas.Account) -> schemas.Account | None:
        """ ⚡ تحديث بيانات حساب - محلي أولاً ثم مزامنة في الخلفية """
        safe_print(f"INFO: [Repo] جاري تحديث الحساب ID: {account_id}")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        account_data.last_modified = now_dt
        account_data.sync_status = 'modified_offline'

        try:
            account_id_num = int(account_id)
        except ValueError:
            account_id_num = 0

        currency_value = account_data.currency.value if account_data.currency else 'EGP'
        parent_value = account_data.parent_id or account_data.parent_code

        # ⚡ إصلاح: دعم البحث بالـ code أيضاً
        sql = """
            UPDATE accounts SET
                name = ?, code = ?, type = ?, parent_id = ?, status = ?,
                balance = ?, currency = ?, description = ?,
                last_modified = ?, sync_status = 'modified_offline'
            WHERE id = ? OR _mongo_id = ? OR code = ?
        """
        params = (
            account_data.name,
            account_data.code,
            account_data.type.value,
            parent_value,
            account_data.status.value,
            account_data.balance,
            currency_value,
            account_data.description,
            now_iso,
            account_id_num,
            account_id,
            account_id,  # البحث بالـ code أيضاً
        )
        try:
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repo] ✅ تم تحديث الحساب محلياً")
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث الحساب (SQLite): {e}")

        # ⚡ مزامنة مع MongoDB في الخلفية (لا يعطل الواجهة)
        if self.online:
            def sync_to_mongo():
                try:
                    update_dict = account_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                    update_dict['type'] = account_data.type.value
                    update_dict['status'] = account_data.status.value
                    update_dict['last_modified'] = now_dt

                    # ⚡ إصلاح: دعم البحث بالـ code أيضاً
                    self.mongo_db.accounts.update_one(
                        {"$or": [
                            {"_id": self._to_objectid(account_id)},
                            {"_mongo_id": account_id},
                            {"id": account_id_num},
                            {"code": account_id},  # البحث بالـ code
                        ]},
                        {"$set": update_dict},
                    )
                    self.sqlite_cursor.execute(
                        "UPDATE accounts SET sync_status = 'synced' WHERE id = ? OR _mongo_id = ? OR code = ?",
                        (account_id_num, account_id, account_id),
                    )
                    self.sqlite_conn.commit()
                    safe_print(f"INFO: [Repo] ✅ تم مزامنة الحساب مع السيرفر (خلفية)")
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل مزامنة الحساب مع السيرفر: {e}")
            
            import threading
            threading.Thread(target=sync_to_mongo, daemon=True).start()

        return account_data

    def archive_account_by_id(self, account_id: str) -> bool:
        """ (جديدة) أرشفة حساب (Soft Delete). """
        safe_print(f"INFO: [Repo] جاري أرشفة الحساب ID: {account_id}")
        try:
            account = self.get_account_by_id(account_id)
            if not account:
                return False

            account.status = schemas.AccountStatus.ARCHIVED
            self.update_account(account_id, account)
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل أرشفة الحساب: {e}")
            return False

    def delete_account_permanently(self, account_id: str) -> bool:
        """ ⚡ حذف حساب نهائياً - محلي أولاً ثم مزامنة في الخلفية """
        safe_print(f"INFO: [Repo] جاري حذف الحساب نهائياً ID: {account_id}")
        try:
            # محاولة تحويل account_id إلى رقم
            try:
                account_id_num = int(account_id)
            except (ValueError, TypeError):
                account_id_num = -1

            # ⚡ حذف من SQLite فوراً (سريع جداً)
            self.sqlite_cursor.execute(
                "DELETE FROM accounts WHERE id = ? OR _mongo_id = ? OR code = ?",
                (account_id_num, account_id, account_id)
            )
            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repo] ✅ تم حذف الحساب من المحلي")

            # ⚡ حذف من MongoDB في الخلفية (لا يعطل الواجهة)
            if self.online:
                def delete_from_mongo():
                    try:
                        from bson import ObjectId
                        try:
                            self.mongo_db.accounts.delete_one({"_id": ObjectId(account_id)})
                        except Exception:
                            self.mongo_db.accounts.delete_one({"code": account_id})
                        safe_print(f"INFO: [Repo] ✅ تم حذف الحساب من MongoDB (خلفية)")
                    except Exception as e:
                        safe_print(f"WARNING: [Repo] فشل حذف الحساب من MongoDB: {e}")
                
                import threading
                threading.Thread(target=delete_from_mongo, daemon=True).start()

            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف الحساب: {e}")
            return False

    # --- دوال التعامل مع الفواتير ---

    def create_invoice(self, invoice_data: schemas.Invoice) -> schemas.Invoice:
        """ إنشاء فاتورة جديدة (بذكاء) """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        invoice_data.created_at = now_dt
        invoice_data.last_modified = now_dt
        invoice_data.sync_status = 'new_offline'

        items_json = json.dumps([item.model_dump() for item in invoice_data.items])

        sql = """
            INSERT INTO invoices (
                _mongo_id, sync_status, created_at, last_modified, invoice_number,
                client_id, project_id, issue_date, due_date, items,
                subtotal, discount_rate, discount_amount, tax_rate, tax_amount,
                total_amount, amount_paid, status, currency, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            None, invoice_data.sync_status, now_iso, now_iso, invoice_data.invoice_number,
            invoice_data.client_id, invoice_data.project_id,
            invoice_data.issue_date.isoformat(), invoice_data.due_date.isoformat(), items_json,
            invoice_data.subtotal, invoice_data.discount_rate, invoice_data.discount_amount,
            invoice_data.tax_rate, invoice_data.tax_amount, invoice_data.total_amount,
            invoice_data.amount_paid, invoice_data.status.value,
            invoice_data.currency.value, invoice_data.notes
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        invoice_data.id = local_id
        safe_print(f"INFO: تم حفظ الفاتورة '{invoice_data.invoice_number}' محلياً (ID: {local_id}).")

        if self.online:
            try:
                invoice_dict = invoice_data.model_dump(exclude={"_mongo_id", "id"})
                invoice_dict['status'] = invoice_data.status.value
                invoice_dict['currency'] = invoice_data.currency.value
                invoice_dict['issue_date'] = invoice_data.issue_date
                invoice_dict['due_date'] = invoice_data.due_date
                invoice_dict['notes'] = invoice_data.notes
                invoice_dict['project_id'] = invoice_data.project_id

                result = self.mongo_db.invoices.insert_one(invoice_dict)
                mongo_id = str(result.inserted_id)

                invoice_data._mongo_id = mongo_id
                invoice_data.sync_status = 'synced'

                self.sqlite_cursor.execute(
                    "UPDATE invoices SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                    (mongo_id, 'synced', local_id)
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة الفاتورة '{invoice_data.invoice_number}' أونلاين.")

            except Exception as e:
                safe_print(f"ERROR: فشل مزامنة الفاتورة الجديدة '{invoice_data.invoice_number}': {e}")

        return invoice_data

    def get_all_invoices(self) -> list[schemas.Invoice]:
        """ جلب كل الفواتير (بذكاء) """
        if self.online:
            try:
                invoices_data = list(self.mongo_db.invoices.find())
                invoices_list = []
                for inv in invoices_data:
                    mongo_id = str(inv.pop('_id'))
                    inv.pop('_mongo_id', None)
                    inv.pop('mongo_id', None)
                    invoices_list.append(schemas.Invoice(**inv, _mongo_id=mongo_id))
                safe_print(f"INFO: تم جلب الفواتير من الأونلاين (MongoDB).")
                return invoices_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الفواتير من Mongo: {e}. سيتم الجلب من المحلي.")

        # الجلب من SQLite في حالة الأوفلاين
        self.sqlite_cursor.execute("SELECT * FROM invoices")
        rows = self.sqlite_cursor.fetchall()
        invoices_list = []
        for row in rows:
            row_dict = dict(row)
            # تحويل الـ JSON string بتاع 'items' نرجعه لـ list
            row_dict['items'] = json.loads(row_dict['items'])
            invoices_list.append(schemas.Invoice(**row_dict))

        safe_print(f"INFO: تم جلب الفواتير من المحلي (SQLite).")
        return invoices_list

    # --- دوال التعامل مع قيود اليومية ---

    def create_journal_entry(self, entry_data: schemas.JournalEntry) -> schemas.JournalEntry:
        """ إنشاء قيد يومية جديد (بذكاء) """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        entry_data.created_at = now_dt
        entry_data.last_modified = now_dt
        entry_data.sync_status = 'new_offline'

        # 1. الحفظ في SQLite (الأوفلاين أولاً)
        lines_json = json.dumps([line.model_dump() for line in entry_data.lines])

        sql = """
            INSERT INTO journal_entries (
                _mongo_id, sync_status, created_at, last_modified, date,
                description, lines, related_document_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            None, entry_data.sync_status, now_iso, now_iso, entry_data.date.isoformat(),
            entry_data.description, lines_json, entry_data.related_document_id
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        safe_print(f"INFO: تم حفظ قيد اليومية '{entry_data.description[:20]}...' محلياً (ID: {local_id}).")

        # 2. محاولة الحفظ في MongoDB (الأونلاين)
        if self.online:
            try:
                entry_dict = entry_data.model_dump(exclude={"_mongo_id"})
                entry_dict['date'] = entry_data.date # ضمان إرسال التاريخ كـ datetime

                result = self.mongo_db.journal_entries.insert_one(entry_dict)
                mongo_id = str(result.inserted_id)

                entry_data._mongo_id = mongo_id
                entry_data.sync_status = 'synced'

                self.sqlite_cursor.execute(
                    "UPDATE journal_entries SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                    (mongo_id, 'synced', local_id)
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة قيد اليومية '{entry_data.description[:20]}...' أونلاين.")

            except Exception as e:
                safe_print(f"ERROR: فشل مزامنة قيد اليومية الجديد: {e}")

        return entry_data

    def get_all_journal_entries(self) -> list[schemas.JournalEntry]:
        """ ⚡ جلب كل قيود اليومية (SQLite أولاً للسرعة) """
        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            self.sqlite_cursor.execute("SELECT * FROM journal_entries ORDER BY date DESC")
            rows = self.sqlite_cursor.fetchall()
            entries_list = []
            for row in rows:
                row_dict = dict(row)
                lines_value = row_dict.get("lines")
                if isinstance(lines_value, str):
                    try:
                        row_dict["lines"] = json.loads(lines_value)
                    except json.JSONDecodeError:
                        row_dict["lines"] = []
                
                # ⚡ إصلاح البيانات القديمة: إضافة account_id إذا كان مفقوداً
                fixed_lines = []
                for line in row_dict.get("lines", []):
                    if isinstance(line, dict):
                        # إذا كان account_id مفقوداً، استخدم account_code أو قيمة افتراضية
                        if "account_id" not in line or not line.get("account_id"):
                            line["account_id"] = line.get("account_code", "") or line.get("account_name", "") or "unknown"
                        fixed_lines.append(line)
                row_dict["lines"] = fixed_lines
                
                try:
                    entries_list.append(schemas.JournalEntry(**row_dict))
                except Exception as entry_error:
                    safe_print(f"WARNING: تخطي قيد فاسد: {entry_error}")
                    continue
                    
            safe_print(f"INFO: تم جلب {len(entries_list)} قيد من المحلي.")
            return entries_list
        except Exception as e:
            safe_print(f"ERROR: فشل جلب القيود من SQLite: {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                entries_data = list(self.mongo_db.journal_entries.find().sort("date", -1))
                entries_list = []
                for entry in entries_data:
                    mongo_id = str(entry.pop('_id'))
                    entry.pop('_mongo_id', None)
                    entry.pop('mongo_id', None)
                    entries_list.append(schemas.JournalEntry(**entry, _mongo_id=mongo_id))
                safe_print(f"INFO: تم جلب قيود اليومية من الأونلاين (MongoDB).")
                return entries_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب قيود اليومية من Mongo: {e}")

        return []

    def get_journal_entry_by_doc_id(self, doc_id: str) -> schemas.JournalEntry | None:
        """ (جديدة) جلب قيد يومية عن طريق ID الفاتورة/المصروف المرتبط به """
        if self.online:
            try:
                data = self.mongo_db.journal_entries.find_one({"related_document_id": doc_id})
                if data:
                    mongo_id = str(data.pop('_id'))
                    data.pop('_mongo_id', None)
                    data.pop('mongo_id', None)
                    return schemas.JournalEntry(**data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب القيد (Mongo): {e}")

        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM journal_entries WHERE related_document_id = ?",
                (doc_id,)
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                row_dict = dict(row)
                row_dict['lines'] = json.loads(row_dict['lines'])
                
                # ⚡ إصلاح البيانات القديمة: إضافة account_id إذا كان مفقوداً
                fixed_lines = []
                for line in row_dict.get("lines", []):
                    if isinstance(line, dict):
                        if "account_id" not in line or not line.get("account_id"):
                            line["account_id"] = line.get("account_code", "") or line.get("account_name", "") or "unknown"
                        fixed_lines.append(line)
                row_dict["lines"] = fixed_lines
                
                return schemas.JournalEntry(**row_dict)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب القيد (SQLite): {e}")

        return None

    # --- دوال التعامل مع الدفعات ---

    def create_payment(self, payment_data: schemas.Payment) -> schemas.Payment:
        """ (معدلة) إنشاء دفعة جديدة (مربوطة بمشروع) مع فحص التكرار """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        # ✅ فحص التكرار قبل الإضافة (نفس المشروع + نفس التاريخ + نفس المبلغ)
        existing_payment = self._get_duplicate_payment(
            payment_data.project_id,
            payment_data.date,
            payment_data.amount
        )
        if existing_payment:
            safe_print(f"WARNING: دفعة مكررة! (المشروع: {payment_data.project_id}, التاريخ: {payment_data.date}, المبلغ: {payment_data.amount})")
            raise Exception(f"يوجد دفعة بنفس البيانات (المبلغ: {payment_data.amount} - التاريخ: {payment_data.date})")

        payment_data.created_at = now_dt
        payment_data.last_modified = now_dt
        payment_data.sync_status = 'new_offline'

        # 1. الحفظ في SQLite (الأوفلاين أولاً)
        sql = """
            INSERT INTO payments (
                sync_status, created_at, last_modified, project_id, client_id,
                date, amount, account_id, method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            payment_data.sync_status, now_iso, now_iso,
            payment_data.project_id, payment_data.client_id,
            payment_data.date.isoformat(), payment_data.amount,
            payment_data.account_id, payment_data.method
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        payment_data.id = local_id
        safe_print(f"INFO: تم حفظ الدفعة (للمشروع {payment_data.project_id}) محلياً (ID: {local_id}).")

        # 2. محاولة الحفظ في MongoDB (الأونلاين)
        if self.online:
            try:
                payment_dict = payment_data.model_dump(exclude={"_mongo_id", "id"})
                payment_dict['date'] = payment_data.date

                result = self.mongo_db.payments.insert_one(payment_dict)
                mongo_id = str(result.inserted_id)

                payment_data._mongo_id = mongo_id
                payment_data.sync_status = 'synced'

                self.sqlite_cursor.execute(
                    "UPDATE payments SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                    (mongo_id, 'synced', local_id)
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة الدفعة (Mongo ID: {mongo_id}) أونلاين.")

            except Exception as e:
                safe_print(f"ERROR: فشل مزامنة الدفعة الجديدة: {e}")

        return payment_data

    def get_payments_for_project(self, project_name: str) -> list[schemas.Payment]:
        """
        (جديدة) جلب كل الدفعات المرتبطة بمشروع (أونلاين أولاً)
        ⚡ يستخدم cursor منفصل لتجنب مشكلة Recursive cursor
        """
        query_filter = {"project_id": project_name}
        if self.online:
            try:
                data = list(self.mongo_db.payments.find(query_filter))
                payments_list = []
                for d in data:
                    mongo_id = str(d.pop('_id'))
                    # حذف _mongo_id و mongo_id من البيانات لتجنب التكرار
                    d.pop('_mongo_id', None)
                    d.pop('mongo_id', None)
                    payments_list.append(schemas.Payment(**d, _mongo_id=mongo_id))
                return payments_list
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب دفعات المشروع (Mongo): {e}")

        # ⚡ استخدام cursor منفصل لتجنب Recursive cursor error
        try:
            with self._lock:
                temp_cursor = self.sqlite_conn.cursor()
                temp_cursor.execute("SELECT * FROM payments WHERE project_id = ?", (project_name,))
                rows = temp_cursor.fetchall()
                temp_cursor.close()
            return [schemas.Payment(**dict(row)) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب دفعات المشروع (SQLite): {e}")
            return []

    def get_all_payments(self) -> list[schemas.Payment]:
        """ ⚡ جلب كل الدفعات (SQLite أولاً للسرعة) """
        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            self.sqlite_cursor.execute("SELECT * FROM payments ORDER BY date DESC")
            rows = self.sqlite_cursor.fetchall()
            payments = [schemas.Payment(**dict(row)) for row in rows]
            safe_print(f"INFO: [Repo] تم جلب {len(payments)} دفعة من SQLite.")
            return payments
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الدفعات (SQLite): {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                data = list(self.mongo_db.payments.find())
                payments = []
                for d in data:
                    mongo_id = str(d.pop('_id'))
                    d.pop('_mongo_id', None)
                    d.pop('mongo_id', None)
                    payments.append(schemas.Payment(**d, _mongo_id=mongo_id))
                safe_print(f"INFO: [Repo] تم جلب {len(payments)} دفعة من MongoDB.")
                return payments
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب الدفعات (Mongo): {e}")

        return []

    def update_payment(self, payment_id, payment_data: schemas.Payment) -> bool:
        """ تعديل دفعة موجودة """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            sql = """
                UPDATE payments SET
                    last_modified = ?, date = ?, amount = ?,
                    account_id = ?, method = ?, sync_status = ?
                WHERE id = ? OR _mongo_id = ?
            """
            params = (
                now_iso, payment_data.date.isoformat(), payment_data.amount,
                payment_data.account_id, payment_data.method, 'modified',
                payment_id, str(payment_id)
            )
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repo] تم تعديل الدفعة محلياً (ID: {payment_id}).")

            if self.online:
                try:
                    from bson import ObjectId
                    payment_dict = {
                        'last_modified': now_dt,
                        'date': payment_data.date,
                        'amount': payment_data.amount,
                        'account_id': payment_data.account_id,
                        'method': payment_data.method,
                        'sync_status': 'synced'
                    }

                    result = None
                    if payment_data._mongo_id:
                        result = self.mongo_db.payments.update_one(
                            {'_id': ObjectId(payment_data._mongo_id)},
                            {'$set': payment_dict}
                        )

                    if result and result.modified_count > 0:
                        self.sqlite_cursor.execute(
                            "UPDATE payments SET sync_status = ? WHERE id = ? OR _mongo_id = ?",
                            ('synced', payment_id, str(payment_id))
                        )
                        self.sqlite_conn.commit()
                        safe_print(f"INFO: [Repo] تم مزامنة تعديل الدفعة أونلاين.")
                except Exception as e:
                    safe_print(f"ERROR: [Repo] فشل مزامنة تعديل الدفعة: {e}")

            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تعديل الدفعة: {e}")
            return False

    def get_payment_by_id(self, payment_id) -> schemas.Payment | None:
        """ جلب دفعة بالـ ID """
        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM payments WHERE id = ? OR _mongo_id = ?",
                (payment_id, str(payment_id))
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Payment(**dict(row))
            return None
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الدفعة: {e}")
            return None

    def delete_payment(self, payment_id) -> bool:
        """ حذف دفعة """
        try:
            # جلب بيانات الدفعة أولاً للحصول على _mongo_id
            self.sqlite_cursor.execute(
                "SELECT _mongo_id FROM payments WHERE id = ? OR _mongo_id = ?",
                (payment_id, str(payment_id))
            )
            row = self.sqlite_cursor.fetchone()
            mongo_id = row['_mongo_id'] if row else None

            # حذف من SQLite
            self.sqlite_cursor.execute(
                "DELETE FROM payments WHERE id = ? OR _mongo_id = ?",
                (payment_id, str(payment_id))
            )
            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repo] تم حذف الدفعة محلياً (ID: {payment_id}).")

            # حذف من MongoDB
            if self.online and mongo_id:
                try:
                    from bson import ObjectId
                    self.mongo_db.payments.delete_one({'_id': ObjectId(mongo_id)})
                    safe_print(f"INFO: [Repo] تم حذف الدفعة من MongoDB.")
                except Exception as e:
                    safe_print(f"ERROR: [Repo] فشل حذف الدفعة من MongoDB: {e}")

            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف الدفعة: {e}")
            return False

    def update_invoice_after_payment(self, invoice_number: str, new_payment_amount: float) -> schemas.Invoice | None:
        """
        (جديدة) تحديث المبلغ المدفوع وحالة الفاتورة بعد استلام دفعة.
        """
        safe_print(f"INFO: [Repo] جاري تحديث الفاتورة {invoice_number} بدفعة {new_payment_amount}")

        invoice = self.get_invoice_by_number(invoice_number)
        if not invoice:
            safe_print(f"ERROR: [Repo] لم يتم العثور على الفاتورة {invoice_number} لتحديثها.")
            return None

        new_amount_paid = invoice.amount_paid + new_payment_amount
        new_status = invoice.status

        if new_amount_paid >= invoice.total_amount:
            new_status = schemas.InvoiceStatus.PAID
        elif new_amount_paid > 0:
            new_status = schemas.InvoiceStatus.PARTIAL

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            self.sqlite_cursor.execute(
                "UPDATE invoices SET amount_paid = ?, status = ?, last_modified = ?, sync_status = 'modified_offline' WHERE invoice_number = ?",
                (new_amount_paid, new_status.value, now_iso, invoice_number)
            )
            self.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث الفاتورة (SQLite): {e}")

        if self.online:
            try:
                self.mongo_db.invoices.update_one(
                    {"invoice_number": invoice_number},
                    {
                        "$set": {
                            "amount_paid": new_amount_paid,
                            "status": new_status.value,
                            "last_modified": now_dt
                        }
                    }
                )
                self.sqlite_cursor.execute(
                    "UPDATE invoices SET sync_status = 'synced' WHERE invoice_number = ?",
                    (invoice_number,)
                )
                self.sqlite_conn.commit()
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل تحديث الفاتورة (Mongo): {e}")

        invoice.amount_paid = new_amount_paid
        invoice.status = new_status
        invoice.last_modified = now_dt
        invoice.sync_status = 'synced' if self.online else 'modified_offline'
        return invoice

    def update_invoice(self, invoice_number: str, invoice_data: schemas.Invoice) -> schemas.Invoice | None:
        """
        (جديدة) تحديث بيانات فاتورة موجودة بالكامل.
        """
        safe_print(f"INFO: [Repo] جاري تحديث الفاتورة {invoice_number} في قاعدة البيانات...")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        items_json = json.dumps([item.model_dump() for item in invoice_data.items])

        try:
            sql = """
                UPDATE invoices SET
                    client_id = ?, issue_date = ?, due_date = ?, items = ?,
                    subtotal = ?, discount_rate = ?, discount_amount = ?,
                    tax_rate = ?, tax_amount = ?, total_amount = ?,
                    notes = ?, status = ?, project_id = ?, last_modified = ?, sync_status = 'modified_offline'
                WHERE invoice_number = ?
            """
            params = (
                invoice_data.client_id,
                invoice_data.issue_date.isoformat(),
                invoice_data.due_date.isoformat(),
                items_json,
                invoice_data.subtotal,
                invoice_data.discount_rate,
                invoice_data.discount_amount,
                invoice_data.tax_rate,
                invoice_data.tax_amount,
                invoice_data.total_amount,
                invoice_data.notes,
                invoice_data.status.value,
                invoice_data.project_id,
                now_iso,
                invoice_number,
            )
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث الفاتورة (SQLite): {e}")
            return None

        if self.online:
            try:
                update_dict = invoice_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                update_dict['status'] = invoice_data.status.value
                update_dict['currency'] = invoice_data.currency.value
                update_dict['last_modified'] = now_dt
                update_dict['discount_rate'] = invoice_data.discount_rate
                update_dict['discount_amount'] = invoice_data.discount_amount

                self.mongo_db.invoices.update_one(
                    {"invoice_number": invoice_number},
                    {"$set": update_dict}
                )

                self.sqlite_cursor.execute(
                    "UPDATE invoices SET sync_status = 'synced' WHERE invoice_number = ?",
                    (invoice_number,)
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: [Repo] تم مزامنة تحديث الفاتورة {invoice_number} أونلاين.")

            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل تحديث الفاتورة (Mongo): {e}")

        return invoice_data

    def get_invoice_by_number(self, invoice_number: str) -> schemas.Invoice | None:
        """ (جديدة) جلب فاتورة واحدة برقمها """
        if self.online:
            try:
                data = self.mongo_db.invoices.find_one({"invoice_number": invoice_number})
                if data:
                    mongo_id = str(data.pop('_id'))
                    data.pop('_mongo_id', None)
                    data.pop('mongo_id', None)
                    return schemas.Invoice(**data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب الفاتورة {invoice_number} (Mongo): {e}")

        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM invoices WHERE invoice_number = ?",
                (invoice_number,)
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                row_dict = dict(row)
                row_dict['items'] = json.loads(row_dict['items'])
                return schemas.Invoice(**row_dict)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الفاتورة {invoice_number} (SQLite): {e}")

        return None

    def get_invoice_by_id(self, invoice_id: str) -> schemas.Invoice | None:
        """جلب فاتورة بالمعرف (ID أو _mongo_id أو invoice_number)"""
        # محاولة البحث بـ _mongo_id أولاً
        if self.online:
            try:
                from bson import ObjectId
                data = self.mongo_db.invoices.find_one({"_id": ObjectId(invoice_id)})
                if data:
                    mongo_id = str(data.pop('_id'))
                    data.pop('_mongo_id', None)
                    return schemas.Invoice(**data, _mongo_id=mongo_id)
            except Exception:
                pass

        # محاولة البحث بـ id في SQLite
        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM invoices WHERE id = ?",
                (invoice_id,)
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                row_dict = dict(row)
                row_dict['items'] = json.loads(row_dict['items'])
                return schemas.Invoice(**row_dict)
        except Exception:
            pass

        # محاولة البحث برقم الفاتورة
        return self.get_invoice_by_number(invoice_id)

    def void_invoice_by_number(self, invoice_number: str) -> schemas.Invoice | None:
        """
        (جديدة) إلغاء فاتورة: تحديث الحالة إلى "ملغاة".
        """
        safe_print(f"INFO: [Repo] جاري إلغاء الفاتورة {invoice_number}")

        invoice = self.get_invoice_by_number(invoice_number)
        if not invoice:
            safe_print(f"ERROR: [Repo] لم يتم العثور على الفاتورة {invoice_number} لإلغائها.")
            return None

        new_status = schemas.InvoiceStatus.VOID
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            self.sqlite_cursor.execute(
                "UPDATE invoices SET status = ?, last_modified = ?, sync_status = 'modified_offline' WHERE invoice_number = ?",
                (new_status.value, now_iso, invoice_number)
            )
            self.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل إلغاء الفاتورة (SQLite): {e}")

        if self.online:
            try:
                self.mongo_db.invoices.update_one(
                    {"invoice_number": invoice_number},
                    {
                        "$set": {
                            "status": new_status.value,
                            "last_modified": now_dt
                        }
                    }
                )
                self.sqlite_cursor.execute(
                    "UPDATE invoices SET sync_status = 'synced' WHERE invoice_number = ?",
                    (invoice_number,)
                )
                self.sqlite_conn.commit()
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل إلغاء الفاتورة (Mongo): {e}")

        invoice.status = new_status
        invoice.last_modified = now_dt
        invoice.sync_status = 'synced' if self.online else 'modified_offline'
        return invoice

    # --- دوال التعامل مع الخدمات ---

    def create_service(self, service_data: schemas.Service) -> schemas.Service:
        """ (معدلة) إنشاء خدمة جديدة (بإصلاح حفظ الحالة في مونجو) """
        # ⚡ فحص التكرار قبل الإضافة
        self.sqlite_cursor.execute("SELECT id FROM services WHERE name = ?", (service_data.name,))
        existing = self.sqlite_cursor.fetchone()
        if existing:
            safe_print(f"WARNING: الخدمة '{service_data.name}' موجودة بالفعل!")
            raise Exception(f"الخدمة '{service_data.name}' موجودة بالفعل في النظام")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        service_data.created_at = now_dt
        service_data.last_modified = now_dt
        service_data.status = schemas.ServiceStatus.ACTIVE

        sql = """
            INSERT INTO services (sync_status, created_at, last_modified, name,
            description, default_price, category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            service_data.sync_status, now_iso, now_iso, service_data.name,
            service_data.description, service_data.default_price,
            service_data.category, service_data.status.value
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        service_data.id = local_id
        safe_print(f"INFO: تم حفظ الخدمة '{service_data.name}' محلياً (ID: {local_id}).")

        if self.online:
            try:
                service_dict = service_data.model_dump(exclude={"_mongo_id", "id"})
                service_dict['status'] = service_data.status.value

                result = self.mongo_db.services.insert_one(service_dict)
                mongo_id = str(result.inserted_id)

                service_data._mongo_id = mongo_id
                service_data.sync_status = 'synced'

                self.sqlite_cursor.execute(
                    "UPDATE services SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                    (mongo_id, 'synced', local_id)
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة الخدمة '{service_data.name}' أونلاين.")

            except Exception as e:
                if "E11000 duplicate key" in str(e):
                    safe_print(f"WARNING: الخدمة '{service_data.name}' موجودة بالفعل أونلاين.")
                else:
                    safe_print(f"ERROR: فشل مزامنة الخدمة الجديدة '{service_data.name}': {e}")

        return service_data

    def get_all_services(self) -> list[schemas.Service]:
        """ ⚡ جلب كل الخدمات "النشطة" فقط (SQLite أولاً للسرعة) """
        active_status = schemas.ServiceStatus.ACTIVE.value

        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            self.sqlite_cursor.execute("SELECT * FROM services WHERE status = ?", (active_status,))
            rows = self.sqlite_cursor.fetchall()
            services_list = [schemas.Service(**dict(row)) for row in rows]
            safe_print(f"INFO: تم جلب {len(services_list)} خدمة 'نشطة' من المحلي.")
            return services_list
        except Exception as e:
            safe_print(f"ERROR: فشل جلب الخدمات من SQLite: {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                services_data = list(self.mongo_db.services.find({"status": active_status}))
                services_list = []
                for s in services_data:
                    mongo_id = str(s.pop('_id'))
                    s.pop('_mongo_id', None)
                    s.pop('mongo_id', None)
                    services_list.append(schemas.Service(**s, _mongo_id=mongo_id))
                safe_print(f"INFO: تم جلب {len(services_list)} خدمة 'نشطة' من الأونلاين.")
                return services_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الخدمات من Mongo: {e}")

        return []

    def get_service_by_id(self, service_id: str) -> schemas.Service | None:
        """ (جديدة) جلب خدمة واحدة بالـ ID """
        try:
            service_id_num = int(service_id)
        except ValueError:
            service_id_num = 0

        if self.online:
            try:
                data = self.mongo_db.services.find_one({"$or": [{"_id": self._to_objectid(service_id)}, {"_mongo_id": service_id}]})
                if data:
                    mongo_id = str(data.pop('_id'))
                    data.pop('_mongo_id', None)
                    data.pop('mongo_id', None)
                    return schemas.Service(**data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب الخدمة {service_id} (Mongo): {e}")

        try:
            self.sqlite_cursor.execute("SELECT * FROM services WHERE id = ? OR _mongo_id = ?", (service_id_num, service_id))
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Service(**dict(row))
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الخدمة {service_id} (SQLite): {e}")

        return None

    def update_service(self, service_id: str, service_data: schemas.Service) -> schemas.Service | None:
        """
        (جديدة) تحديث بيانات خدمة موجودة.
        """
        safe_print(f"INFO: [Repo] جاري تحديث الخدمة ID: {service_id}")
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            service_id_num = int(service_id)
        except ValueError:
            service_id_num = 0

        sql = """
            UPDATE services SET
                name = ?, description = ?, default_price = ?, category = ?, status = ?,
                last_modified = ?, sync_status = 'modified_offline'
            WHERE id = ? OR _mongo_id = ?
        """
        params = (
            service_data.name, service_data.description, service_data.default_price,
            service_data.category, service_data.status.value,
            now_iso, service_id_num, service_id
        )
        try:
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث الخدمة (SQLite): {e}")
            return None

        if self.online:
            try:
                update_dict = service_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                update_dict['status'] = service_data.status.value
                update_dict['last_modified'] = now_dt

                self.mongo_db.services.update_one(
                    {"$or": [{"_id": self._to_objectid(service_id)}, {"_mongo_id": service_id}]},
                    {"$set": update_dict}
                )
                self.sqlite_cursor.execute(
                    "UPDATE services SET sync_status = 'synced' WHERE id = ? OR _mongo_id = ?",
                    (service_id_num, service_id)
                )
                self.sqlite_conn.commit()
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل تحديث الخدمة (Mongo): {e}")

        return service_data

    def archive_service_by_id(self, service_id: str) -> bool:
        """
        (جديدة) أرشفة خدمة (Soft Delete).
        """
        safe_print(f"INFO: [Repo] جاري أرشفة الخدمة ID: {service_id}")
        try:
            service = self.get_service_by_id(service_id)
            if not service:
                return False

            service.status = schemas.ServiceStatus.ARCHIVED
            self.update_service(service_id, service)
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل أرشفة الخدمة: {e}")
            return False

    def delete_service_permanently(self, service_id: str) -> bool:
        """
        حذف خدمة نهائياً من قاعدة البيانات (Hard Delete)
        """
        safe_print(f"INFO: [Repo] جاري حذف الخدمة نهائياً ID: {service_id}")

        try:
            service_id_num = int(service_id)
        except ValueError:
            service_id_num = 0

        # جلب _mongo_id قبل الحذف
        self.sqlite_cursor.execute(
            "SELECT _mongo_id FROM services WHERE id = ? OR _mongo_id = ?",
            (service_id_num, service_id)
        )
        row = self.sqlite_cursor.fetchone()
        mongo_id = row[0] if row else service_id

        # حذف من SQLite
        self.sqlite_cursor.execute(
            "DELETE FROM services WHERE id = ? OR _mongo_id = ?",
            (service_id_num, service_id)
        )
        self.sqlite_conn.commit()
        safe_print(f"INFO: [Repo] ✅ تم حذف الخدمة من SQLite")

        # حذف من MongoDB
        if self.online:
            try:
                result = self.mongo_db.services.delete_one(
                    {"$or": [
                        {"_id": self._to_objectid(mongo_id)},
                        {"_id": self._to_objectid(service_id)}
                    ]}
                )
                if result.deleted_count > 0:
                    safe_print(f"INFO: [Repo] ✅ تم حذف الخدمة من MongoDB")
                else:
                    safe_print(f"WARNING: [Repo] الخدمة غير موجودة في MongoDB")
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل حذف الخدمة من MongoDB: {e}")

        return True

    def get_archived_services(self) -> list[schemas.Service]:
        """ (جديدة) جلب كل الخدمات "المؤرشفة" فقط """
        archived_status = schemas.ServiceStatus.ARCHIVED.value
        if self.online:
            try:
                services_data = list(self.mongo_db.services.find({"status": archived_status}))
                services_list = []
                for s in services_data:
                    mongo_id = str(s.pop('_id'))
                    s.pop('_mongo_id', None)
                    s.pop('mongo_id', None)
                    services_list.append(schemas.Service(**s, _mongo_id=mongo_id))
                return services_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الخدمات المؤرشفة (Mongo): {e}.")

        self.sqlite_cursor.execute("SELECT * FROM services WHERE status = ?", (archived_status,))
        rows = self.sqlite_cursor.fetchall()
        return [schemas.Service(**dict(row)) for row in rows]

    # --- دوال التعامل مع المصروفات ---

    def create_expense(self, expense_data: schemas.Expense) -> schemas.Expense:
        """ إنشاء مصروف جديد (بذكاء) """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        expense_data.created_at = now_dt
        expense_data.last_modified = now_dt
        expense_data.sync_status = 'new_offline'

        sql = """
            INSERT INTO expenses (sync_status, created_at, last_modified, date, category, amount, description, account_id, payment_account_id, project_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            expense_data.sync_status, now_iso, now_iso, expense_data.date.isoformat(),
            expense_data.category, expense_data.amount, expense_data.description, expense_data.account_id,
            expense_data.payment_account_id, expense_data.project_id
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        expense_data.id = local_id
        safe_print(f"INFO: تم حفظ المصروف '{expense_data.category}' محلياً (ID: {local_id}).")

        if self.online:
            try:
                expense_dict = expense_data.model_dump(exclude={"_mongo_id", "id"})
                expense_dict['date'] = expense_data.date

                result = self.mongo_db.expenses.insert_one(expense_dict)
                mongo_id = str(result.inserted_id)

                expense_data._mongo_id = mongo_id
                expense_data.sync_status = 'synced'

                self.sqlite_cursor.execute(
                    "UPDATE expenses SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                    (mongo_id, 'synced', local_id)
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة المصروف '{expense_data.category}' أونلاين.")

            except Exception as e:
                safe_print(f"ERROR: فشل مزامنة المصروف الجديد '{expense_data.category}': {e}")

        return expense_data

    def get_all_expenses(self) -> list[schemas.Expense]:
        """ ⚡ جلب كل المصروفات (SQLite أولاً للسرعة) """
        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            self.sqlite_cursor.execute("SELECT * FROM expenses ORDER BY date DESC")
            rows = self.sqlite_cursor.fetchall()
            expenses_list = [schemas.Expense(**dict(row)) for row in rows]
            safe_print(f"INFO: تم جلب {len(expenses_list)} مصروف من المحلي (SQLite).")
            return expenses_list
        except Exception as e:
            safe_print(f"ERROR: فشل جلب المصروفات من SQLite: {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                expenses_data = list(self.mongo_db.expenses.find())
                expenses_list = []
                for exp in expenses_data:
                    mongo_id = str(exp.pop('_id'))
                    exp.pop('_mongo_id', None)
                    exp.pop('mongo_id', None)
                    expenses_list.append(schemas.Expense(**exp, _mongo_id=mongo_id))
                safe_print(f"INFO: تم جلب المصروفات من الأونلاين (MongoDB).")
                return expenses_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب المصروفات من Mongo: {e}")

        return []

    def update_expense(self, expense_id, expense_data: schemas.Expense) -> bool:
        """ تعديل مصروف موجود """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            # تحديث في SQLite
            sql = """
                UPDATE expenses SET
                    last_modified = ?, date = ?, category = ?, amount = ?,
                    description = ?, account_id = ?, project_id = ?, sync_status = ?
                WHERE id = ? OR _mongo_id = ?
            """
            params = (
                now_iso, expense_data.date.isoformat(), expense_data.category,
                expense_data.amount, expense_data.description, expense_data.account_id,
                expense_data.project_id, 'modified', expense_id, str(expense_id)
            )
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
            safe_print(f"INFO: تم تعديل المصروف محلياً (ID: {expense_id}).")

            # تحديث في MongoDB
            if self.online:
                try:
                    from bson import ObjectId
                    expense_dict = {
                        'last_modified': now_dt,
                        'date': expense_data.date,
                        'category': expense_data.category,
                        'amount': expense_data.amount,
                        'description': expense_data.description,
                        'account_id': expense_data.account_id,
                        'project_id': expense_data.project_id,
                        'sync_status': 'synced'
                    }

                    # محاولة التحديث بـ _mongo_id أو id
                    result = None
                    if expense_data._mongo_id:
                        result = self.mongo_db.expenses.update_one(
                            {'_id': ObjectId(expense_data._mongo_id)},
                            {'$set': expense_dict}
                        )

                    if result and result.modified_count > 0:
                        self.sqlite_cursor.execute(
                            "UPDATE expenses SET sync_status = ? WHERE id = ? OR _mongo_id = ?",
                            ('synced', expense_id, str(expense_id))
                        )
                        self.sqlite_conn.commit()
                        safe_print(f"INFO: تم مزامنة تعديل المصروف أونلاين.")
                except Exception as e:
                    safe_print(f"ERROR: فشل مزامنة تعديل المصروف: {e}")

            return True
        except Exception as e:
            safe_print(f"ERROR: فشل تعديل المصروف: {e}")
            return False

    def delete_expense(self, expense_id) -> bool:
        """ حذف مصروف """
        try:
            # جلب بيانات المصروف أولاً للحصول على _mongo_id
            self.sqlite_cursor.execute(
                "SELECT _mongo_id FROM expenses WHERE id = ? OR _mongo_id = ?",
                (expense_id, str(expense_id))
            )
            row = self.sqlite_cursor.fetchone()
            mongo_id = row['_mongo_id'] if row else None

            # حذف من SQLite
            self.sqlite_cursor.execute(
                "DELETE FROM expenses WHERE id = ? OR _mongo_id = ?",
                (expense_id, str(expense_id))
            )
            self.sqlite_conn.commit()
            safe_print(f"INFO: تم حذف المصروف محلياً (ID: {expense_id}).")

            # حذف من MongoDB
            if self.online and mongo_id:
                try:
                    from bson import ObjectId
                    self.mongo_db.expenses.delete_one({'_id': ObjectId(mongo_id)})
                    safe_print(f"INFO: تم حذف المصروف من الأونلاين.")
                except Exception as e:
                    safe_print(f"ERROR: فشل حذف المصروف من Mongo: {e}")

            return True
        except Exception as e:
            safe_print(f"ERROR: فشل حذف المصروف: {e}")
            return False

    # --- دوال التعامل مع المشاريع ---

    def create_project(self, project_data: schemas.Project) -> schemas.Project:
        """ (معدلة) إنشاء مشروع جديد (بالحقول المالية) مع فحص التكرار """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        # ✅ فحص التكرار قبل الإضافة
        existing_project = self.get_project_by_number(project_data.name)
        if existing_project:
            safe_print(f"WARNING: المشروع '{project_data.name}' موجود بالفعل!")
            raise Exception(f"المشروع '{project_data.name}' موجود بالفعل في النظام")

        # ✅ فحص تكرار بنفس العميل ونفس الاسم (case insensitive)
        similar_project = self._get_similar_project(project_data.name, project_data.client_id)
        if similar_project:
            safe_print(f"WARNING: يوجد مشروع مشابه '{similar_project.name}' لنفس العميل!")
            raise Exception(f"يوجد مشروع مشابه '{similar_project.name}' لنفس العميل")

        project_data.created_at = now_dt
        project_data.last_modified = now_dt
        project_data.sync_status = 'new_offline'

        items_json = json.dumps([item.model_dump() for item in project_data.items])

        # ⚡ جلب قيمة status_manually_set
        status_manually_set = 1 if getattr(project_data, 'status_manually_set', False) else 0

        sql = """
            INSERT INTO projects (
                sync_status, created_at, last_modified, name, client_id,
                status, status_manually_set, description, start_date, end_date,
                items, subtotal, discount_rate, discount_amount, tax_rate,
                tax_amount, total_amount, currency, project_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            project_data.sync_status, now_iso, now_iso,
            project_data.name, project_data.client_id,
            project_data.status.value, status_manually_set, project_data.description,
            project_data.start_date.isoformat() if project_data.start_date else None,
            project_data.end_date.isoformat() if project_data.end_date else None,

            items_json, project_data.subtotal, project_data.discount_rate,
            project_data.discount_amount, project_data.tax_rate,
            project_data.tax_amount, project_data.total_amount,
            project_data.currency.value, project_data.project_notes
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        project_data.id = local_id

        # ⚡ توليد وحفظ رقم الفاتورة الثابت فوراً (في جدول منفصل للثبات)
        try:
            # تحقق من وجود رقم محفوظ مسبقاً لهذا المشروع
            self.sqlite_cursor.execute(
                "SELECT invoice_number FROM invoice_numbers WHERE project_name = ?",
                (project_data.name,)
            )
            existing = self.sqlite_cursor.fetchone()

            if existing:
                invoice_number = existing[0]
            else:
                # ⚡ جلب أعلى رقم فاتورة من كلا الجدولين لتجنب التكرار
                max_num = 97161  # الرقم الأساسي
                
                # من جدول invoice_numbers
                self.sqlite_cursor.execute(
                    "SELECT invoice_number FROM invoice_numbers WHERE invoice_number LIKE 'SW-%' ORDER BY invoice_number DESC LIMIT 1"
                )
                result1 = self.sqlite_cursor.fetchone()
                if result1 and result1[0]:
                    try:
                        num1 = int(result1[0].replace('SW-', ''))
                        max_num = max(max_num, num1)
                    except ValueError:
                        pass
                
                # من جدول projects
                self.sqlite_cursor.execute(
                    "SELECT invoice_number FROM projects WHERE invoice_number LIKE 'SW-%' ORDER BY invoice_number DESC LIMIT 1"
                )
                result2 = self.sqlite_cursor.fetchone()
                if result2 and result2[0]:
                    try:
                        num2 = int(result2[0].replace('SW-', ''))
                        max_num = max(max_num, num2)
                    except ValueError:
                        pass
                
                # توليد الرقم الجديد
                invoice_number = f"SW-{max_num + 1}"
                
                # ⚡ التحقق من عدم وجود تكرار
                while True:
                    self.sqlite_cursor.execute(
                        "SELECT COUNT(*) FROM projects WHERE invoice_number = ?",
                        (invoice_number,)
                    )
                    if self.sqlite_cursor.fetchone()[0] == 0:
                        break
                    # إذا كان موجوداً، زد الرقم
                    max_num += 1
                    invoice_number = f"SW-{max_num + 1}"

                # احفظ الرقم الجديد في جدول الأرقام الثابتة
                self.sqlite_cursor.execute(
                    "INSERT INTO invoice_numbers (project_name, invoice_number, created_at) VALUES (?, ?, ?)",
                    (project_data.name, invoice_number, datetime.now().isoformat())
                )

            # حدّث المشروع
            self.sqlite_cursor.execute(
                "UPDATE projects SET invoice_number = ? WHERE id = ?",
                (invoice_number, local_id)
            )
            self.sqlite_conn.commit()
            project_data.invoice_number = invoice_number
        except Exception as e:
            safe_print(f"WARNING: خطأ في توليد رقم الفاتورة: {e}")
            # fallback: استخدم أعلى رقم + 1
            self.sqlite_cursor.execute(
                "SELECT invoice_number FROM projects WHERE invoice_number LIKE 'SW-%' ORDER BY invoice_number DESC LIMIT 1"
            )
            result = self.sqlite_cursor.fetchone()
            if result and result[0]:
                try:
                    last_num = int(result[0].replace('SW-', ''))
                    invoice_number = f"SW-{last_num + 1}"
                except ValueError:
                    invoice_number = f"SW-{97161 + int(local_id)}"
            else:
                invoice_number = f"SW-{97161 + int(local_id)}"
            
            self.sqlite_cursor.execute(
                "UPDATE projects SET invoice_number = ? WHERE id = ?",
                (invoice_number, local_id)
            )
            self.sqlite_conn.commit()
            project_data.invoice_number = invoice_number

        safe_print(f"INFO: تم حفظ المشروع '{project_data.name}' محلياً (ID: {local_id}, Invoice: {invoice_number}).")

        if self.online:
            try:
                project_dict = project_data.model_dump(exclude={"_mongo_id", "id"})
                project_dict['status'] = project_data.status.value
                project_dict['status_manually_set'] = getattr(project_data, 'status_manually_set', False)
                project_dict['start_date'] = project_data.start_date
                project_dict['end_date'] = project_data.end_date
                project_dict['currency'] = project_data.currency.value
                # ✅ تأكد من حفظ رقم الفاتورة
                project_dict['invoice_number'] = invoice_number

                result = self.mongo_db.projects.insert_one(project_dict)
                mongo_id = str(result.inserted_id)

                project_data._mongo_id = mongo_id
                project_data.sync_status = 'synced'

                self.sqlite_cursor.execute(
                    "UPDATE projects SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                    (mongo_id, 'synced', local_id)
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة المشروع '{project_data.name}' أونلاين.")

            except Exception as e:
                if "E11000 duplicate key" in str(e):
                    safe_print(f"WARNING: المشروع باسم '{project_data.name}' موجود بالفعل أونلاين.")
                else:
                    safe_print(f"ERROR: فشل مزامنة المشروع الجديد: {e}")

        return project_data

    def get_all_projects(
        self,
        status: schemas.ProjectStatus | None = None,
        exclude_status: schemas.ProjectStatus | None = None,
    ) -> list[schemas.Project]:
        """
        ⚡ جلب كل المشاريع (SQLite أولاً للسرعة)
        """
        sql_query = "SELECT * FROM projects"
        sql_params: list[Any] = []

        if status:
            sql_query += " WHERE status = ?"
            sql_params.append(status.value)
        elif exclude_status:
            sql_query += " WHERE status != ?"
            sql_params.append(exclude_status.value)

        sql_query += " ORDER BY created_at DESC"

        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            self.sqlite_cursor.execute(sql_query, sql_params)
            rows = self.sqlite_cursor.fetchall()
            data_list: list[schemas.Project] = []
            for row in rows:
                row_dict = dict(row)
                items_value = row_dict.get("items")
                if isinstance(items_value, str):
                    try:
                        row_dict["items"] = json.loads(items_value)
                    except json.JSONDecodeError:
                        row_dict["items"] = []
                # ⚡ معالجة milestones (JSON string -> list)
                milestones_value = row_dict.get("milestones")
                if isinstance(milestones_value, str):
                    try:
                        row_dict["milestones"] = json.loads(milestones_value)
                    except json.JSONDecodeError:
                        row_dict["milestones"] = []
                data_list.append(schemas.Project(**row_dict))
            safe_print(f"INFO: تم جلب {len(data_list)} مشروع من المحلي.")
            return data_list
        except Exception as e:
            safe_print(f"ERROR: فشل جلب المشاريع من SQLite: {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                query_filter: dict[str, Any] = {}
                if status:
                    query_filter = {"status": status.value}
                elif exclude_status:
                    query_filter = {"status": {"$ne": exclude_status.value}}

                data = list(self.mongo_db.projects.find(query_filter).sort("created_at", -1))
                data_list = []
                for d in data:
                    try:
                        mongo_id = str(d.pop('_id'))
                        if 'client_id' not in d or not d['client_id']:
                            d['client_id'] = 'unknown'
                        if 'name' not in d or not d['name']:
                            continue
                        if 'items' not in d or d['items'] is None:
                            d['items'] = []
                        elif isinstance(d['items'], str):
                            try:
                                d['items'] = json.loads(d['items'])
                            except (json.JSONDecodeError, TypeError, ValueError):
                                d['items'] = []
                        if 'currency' not in d or d['currency'] is None:
                            d['currency'] = 'EGP'
                        if 'status' not in d or d['status'] is None:
                            d['status'] = 'نشط'
                        d.pop('_mongo_id', None)
                        d.pop('mongo_id', None)
                        data_list.append(schemas.Project(**d, _mongo_id=mongo_id))
                    except Exception:
                        continue
                safe_print(f"INFO: تم جلب {len(data_list)} مشروع من الأونلاين.")
                return data_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب المشاريع من Mongo: {e}")

        return []

    def get_project_by_number(self, project_name: str) -> schemas.Project | None:
        """ (جديدة) جلب مشروع واحد باسمه """
        if self.online:
            try:
                data = self.mongo_db.projects.find_one({"name": project_name})
                if data:
                    mongo_id = str(data.pop('_id'))
                    data.pop('_mongo_id', None)
                    data.pop('mongo_id', None)
                    return schemas.Project(**data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب المشروع {project_name} (Mongo): {e}")

        try:
            self.sqlite_cursor.execute("SELECT * FROM projects WHERE name = ?", (project_name,))
            row = self.sqlite_cursor.fetchone()
            if row:
                row_dict = dict(row)
                items_value = row_dict.get("items")
                if isinstance(items_value, str):
                    try:
                        row_dict["items"] = json.loads(items_value)
                    except json.JSONDecodeError:
                        row_dict["items"] = []
                # ⚡ معالجة milestones (JSON string -> list)
                milestones_value = row_dict.get("milestones")
                if isinstance(milestones_value, str):
                    try:
                        row_dict["milestones"] = json.loads(milestones_value)
                    except json.JSONDecodeError:
                        row_dict["milestones"] = []
                return schemas.Project(**row_dict)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب المشروع {project_name} (SQLite): {e}")

        return None

    def update_project(self, project_name: str, project_data: schemas.Project) -> schemas.Project | None:
        """
        (جديدة) تحديث بيانات مشروع موجود بالكامل.
        """
        safe_print(f"INFO: [Repo] جاري تحديث المشروع {project_name} في قاعدة البيانات...")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        items_json = json.dumps([item.model_dump() for item in project_data.items])

        # --- 1. تحديث SQLite ---
        try:
            # ⚡ جلب قيمة status_manually_set
            status_manually_set = 1 if getattr(project_data, 'status_manually_set', False) else 0

            sql = """
                UPDATE projects SET
                    client_id = ?, status = ?, status_manually_set = ?, description = ?, start_date = ?, end_date = ?,
                    items = ?, subtotal = ?, discount_rate = ?, discount_amount = ?, tax_rate = ?,
                    tax_amount = ?, total_amount = ?, currency = ?, project_notes = ?,
                    last_modified = ?, sync_status = 'modified_offline'
                WHERE name = ?
            """
            params = (
                project_data.client_id, project_data.status.value, status_manually_set,
                project_data.description,
                project_data.start_date.isoformat() if project_data.start_date else None,
                project_data.end_date.isoformat() if project_data.end_date else None,
                items_json, project_data.subtotal, project_data.discount_rate,
                project_data.discount_amount, project_data.tax_rate,
                project_data.tax_amount, project_data.total_amount,
                project_data.currency.value, project_data.project_notes,
                now_iso, project_name
            )
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث المشروع (SQLite): {e}")
            return None

        # --- 2. تحديث MongoDB ---
        if self.online:
            try:
                update_dict = project_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                update_dict['status'] = project_data.status.value
                update_dict['start_date'] = project_data.start_date
                update_dict['end_date'] = project_data.end_date
                update_dict['currency'] = project_data.currency.value
                update_dict['last_modified'] = now_dt

                self.mongo_db.projects.update_one(
                    {"name": project_name},
                    {"$set": update_dict}
                )
                self.sqlite_cursor.execute("UPDATE projects SET sync_status = 'synced' WHERE name = ?", (project_name,))
                self.sqlite_conn.commit()
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل تحديث المشروع (Mongo): {e}")

        return project_data

    def delete_project(self, project_id: str) -> bool:
        """🗑️ حذف مشروع نهائياً من قاعدة البيانات"""
        safe_print(f"INFO: [Repo] 🗑️ جاري حذف المشروع: {project_id}")
        
        try:
            # البحث عن المشروع بالاسم (get_project_by_number تبحث بالاسم)
            project = self.get_project_by_number(project_id)
            
            if not project:
                safe_print(f"WARNING: [Repo] المشروع غير موجود: {project_id}")
                return False
            
            project_name = project.name
            mongo_id = getattr(project, '_mongo_id', None)
            local_id = getattr(project, 'id', None)
            
            safe_print(f"INFO: [Repo] وجدنا المشروع: {project_name}, mongo_id={mongo_id}, local_id={local_id}")
            
            # 1. حذف من SQLite
            self.sqlite_cursor.execute("DELETE FROM projects WHERE name = ?", (project_name,))
            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repo] تم حذف المشروع من SQLite")
            
            # 2. حذف من MongoDB
            if self.online and mongo_id:
                try:
                    from bson import ObjectId
                    self.mongo_db.projects.delete_one({"_id": ObjectId(mongo_id)})
                    safe_print(f"INFO: [Repo] تم حذف المشروع من MongoDB")
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل حذف المشروع من MongoDB: {e}")
            
            # 3. حذف الدفعات المرتبطة
            try:
                self.sqlite_cursor.execute("DELETE FROM payments WHERE project_id = ?", (project_name,))
                self.sqlite_conn.commit()
                safe_print(f"INFO: [Repo] تم حذف الدفعات المرتبطة")
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل حذف الدفعات المرتبطة: {e}")
            
            safe_print(f"SUCCESS: [Repo] ✅ تم حذف المشروع {project_name} بنجاح")
            return True
            
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف المشروع: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_project_revenue(self, project_name: str) -> float:
        """ (معدلة بالطريقة البسيطة) تحسب إجمالي إيرادات مشروع """
        safe_print(f"INFO: [Repo] جاري حساب إيرادات مشروع: {project_name}")
        total_revenue = 0.0
        try:
            invoices = self.get_invoices_for_project(project_name)
            for inv in invoices:
                total_revenue += inv.total_amount
            safe_print(f"INFO: [Repo] إيرادات المشروع (محسوبة): {total_revenue}")
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب إيرادات المشروع: {e}")
        return total_revenue

    def get_project_expenses(self, project_name: str) -> float:
        """ (معدلة بالطريقة البسيطة) تحسب إجمالي مصروفات مشروع """
        safe_print(f"INFO: [Repo] جاري حساب مصروفات مشروع: {project_name}")
        total_expenses = 0.0
        try:
            expenses = self.get_expenses_for_project(project_name)
            for exp in expenses:
                total_expenses += exp.amount
            safe_print(f"INFO: [Repo] مصروفات المشروع (محسوبة): {total_expenses}")
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب مصروفات المشروع: {e}")
        return total_expenses

    def get_invoices_for_project(self, project_name: str) -> list[schemas.Invoice]:
        """ (معدلة) جلب كل الفواتير المرتبطة بمشروع (أونلاين أولاً) """
        safe_print(f"INFO: [Repo] جلب فواتير مشروع: {project_name}")
        query_filter = {
            "project_id": project_name,
            "status": {"$ne": schemas.InvoiceStatus.VOID.value}
        }

        if self.online:
            try:
                data = list(self.mongo_db.invoices.find(query_filter))
                invoices_list = []
                for d in data:
                    mongo_id = str(d.pop('_id'))
                    # حذف _mongo_id و mongo_id من البيانات لتجنب التكرار
                    d.pop('_mongo_id', None)
                    d.pop('mongo_id', None)
                    invoices_list.append(schemas.Invoice(**d, _mongo_id=mongo_id))
                return invoices_list
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب فواتير المشروع (Mongo): {e}")

        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM invoices WHERE project_id = ? AND status != ?",
                (project_name, schemas.InvoiceStatus.VOID.value)
            )
            rows = self.sqlite_cursor.fetchall()
            data_list = []
            for row in rows:
                row_dict = dict(row)
                row_dict['items'] = json.loads(row_dict['items'])
                data_list.append(schemas.Invoice(**row_dict))
            return data_list
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب فواتير المشروع (SQLite): {e}")
            return []

    def get_expenses_for_project(self, project_name: str) -> list[schemas.Expense]:
        """ (معدلة) جلب كل المصروفات المرتبطة بمشروع (أونلاين أولاً) """
        safe_print(f"INFO: [Repo] جلب مصروفات مشروع: {project_name}")
        query_filter = {"project_id": project_name}

        if self.online:
            try:
                data = list(self.mongo_db.expenses.find(query_filter))
                expenses_list = []
                for d in data:
                    mongo_id = str(d.pop('_id'))
                    # حذف _mongo_id و mongo_id من البيانات لتجنب التكرار
                    d.pop('_mongo_id', None)
                    d.pop('mongo_id', None)
                    expenses_list.append(schemas.Expense(**d, _mongo_id=mongo_id))
                return expenses_list
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب مصروفات المشروع (Mongo): {e}")

        try:
            self.sqlite_cursor.execute("SELECT * FROM expenses WHERE project_id = ?", (project_name,))
            rows = self.sqlite_cursor.fetchall()
            return [schemas.Expense(**dict(row)) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب مصروفات المشروع (SQLite): {e}")
            return []

    # --- دوال الداشبورد (جديدة) ---

    # ⚡ Cache للـ Dashboard KPIs
    _dashboard_cache = None
    _dashboard_cache_time = 0
    _DASHBOARD_CACHE_TTL = 30  # 30 ثانية

    def get_dashboard_kpis(self, force_refresh: bool = False) -> dict:
        """
        ⚡ (محسّنة للسرعة) تحسب الأرقام الرئيسية للداشبورد.
        SQLite أولاً (سريع جداً) - مع caching لتحسين الأداء.
        """
        # ⚡ استخدام الـ cache إذا كان صالحاً
        current_time = time.time()
        if not force_refresh and Repository._dashboard_cache and (current_time - Repository._dashboard_cache_time) < Repository._DASHBOARD_CACHE_TTL:
            safe_print(f"INFO: [Repo] استخدام cache الداشبورد")
            return Repository._dashboard_cache

        safe_print(f"INFO: [Repo] ⚡ جاري حساب أرقام الداشبورد (SQLite - سريع)...")
        total_collected = 0.0
        total_outstanding = 0.0
        total_expenses = 0.0

        try:
            self.sqlite_cursor.execute("SELECT SUM(amount) FROM payments")
            result = self.sqlite_cursor.fetchone()
            total_collected = result[0] if result and result[0] else 0.0

            self.sqlite_cursor.execute("SELECT SUM(amount) FROM expenses")
            result = self.sqlite_cursor.fetchone()
            total_expenses = result[0] if result and result[0] else 0.0

            # حساب المتبقي لكل مشروع على حدة
            self.sqlite_cursor.execute(
                "SELECT name, total_amount FROM projects WHERE status IN (?, ?, ?)",
                (schemas.ProjectStatus.ACTIVE.value, schemas.ProjectStatus.PLANNING.value, schemas.ProjectStatus.ON_HOLD.value)
            )
            projects = self.sqlite_cursor.fetchall()

            for project in projects:
                project_name = project[0]
                project_total = project[1] or 0.0

                # جلب الدفعات الخاصة بهذا المشروع فقط
                self.sqlite_cursor.execute(
                    "SELECT SUM(amount) FROM payments WHERE project_id = ?",
                    (project_name,)
                )
                paid_result = self.sqlite_cursor.fetchone()
                project_paid = paid_result[0] if paid_result and paid_result[0] else 0.0

                # المتبقي = الإجمالي - المدفوع
                project_remaining = project_total - project_paid
                if project_remaining > 0:
                    total_outstanding += project_remaining

            net_profit_cash = total_collected - total_expenses

            safe_print(f"INFO: [Repo] (Offline) Collected: {total_collected}, Expenses: {total_expenses}, Outstanding: {total_outstanding}")

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب أرقام الداشبورد (SQLite): {e}")

        result = {
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
            "total_expenses": total_expenses,
            "net_profit_cash": net_profit_cash
        }
        # ⚡ حفظ في الـ cache
        Repository._dashboard_cache = result
        Repository._dashboard_cache_time = int(time.time())
        return result

    # --- دوال العملات (جديدة) ---

    def get_all_currencies(self) -> list[dict]:
        """جلب كل العملات من قاعدة البيانات (أونلاين أولاً ثم أوفلاين)"""
        # محاولة الجلب من MongoDB أولاً
        if self.online:
            try:
                currencies_data = list(self.mongo_db.currencies.find().sort([("is_base", -1), ("code", 1)]))
                if currencies_data:
                    currencies = []
                    for c in currencies_data:
                        currencies.append({
                            'id': str(c.get('_id', '')),
                            'code': c.get('code', ''),
                            'name': c.get('name', ''),
                            'symbol': c.get('symbol', ''),
                            'rate': c.get('rate', 1.0),
                            'is_base': bool(c.get('is_base', False)),
                            'active': bool(c.get('active', True))
                        })
                    safe_print(f"INFO: [Repo] تم جلب {len(currencies)} عملة من الأونلاين")
                    return currencies
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل جلب العملات من MongoDB: {e}")

        # الجلب من SQLite
        try:
            self.sqlite_cursor.execute("SELECT * FROM currencies ORDER BY is_base DESC, code ASC")
            rows = self.sqlite_cursor.fetchall()
            currencies = []
            for row in rows:
                currencies.append({
                    'id': row['id'],
                    'code': row['code'],
                    'name': row['name'],
                    'symbol': row['symbol'],
                    'rate': row['rate'],
                    'is_base': bool(row['is_base']),
                    'active': bool(row['active'])
                })
            return currencies
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب العملات: {e}")
            return []

    def save_currency(self, currency_data: dict) -> bool:
        """حفظ أو تحديث عملة (مع مزامنة أونلاين وأوفلاين)"""
        now = datetime.now()
        now_iso = now.isoformat()
        code = currency_data.get('code', '').upper()

        try:
            # 1. الحفظ في SQLite أولاً
            self.sqlite_cursor.execute("SELECT id FROM currencies WHERE code = ?", (code,))
            existing = self.sqlite_cursor.fetchone()

            if existing:
                sql = """
                    UPDATE currencies SET
                        name = ?, symbol = ?, rate = ?, active = ?, last_modified = ?, sync_status = ?
                    WHERE code = ?
                """
                self.sqlite_cursor.execute(sql, (
                    currency_data.get('name', code),
                    currency_data.get('symbol', code),
                    currency_data.get('rate', 1.0),
                    1 if currency_data.get('active', True) else 0,
                    now_iso,
                    'modified_offline',
                    code
                ))
            else:
                sql = """
                    INSERT INTO currencies (code, name, symbol, rate, is_base, active, created_at, last_modified, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new_offline')
                """
                is_base = 1 if code == 'EGP' else 0
                self.sqlite_cursor.execute(sql, (
                    code,
                    currency_data.get('name', code),
                    currency_data.get('symbol', code),
                    currency_data.get('rate', 1.0),
                    is_base,
                    1 if currency_data.get('active', True) else 0,
                    now_iso,
                    now_iso
                ))

            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repo] تم حفظ العملة {code} محلياً")

            # 2. المزامنة مع MongoDB
            if self.online:
                try:
                    mongo_data = {
                        'code': code,
                        'name': currency_data.get('name', code),
                        'symbol': currency_data.get('symbol', code),
                        'rate': currency_data.get('rate', 1.0),
                        'is_base': code == 'EGP',
                        'active': currency_data.get('active', True),
                        'last_modified': now
                    }

                    # استخدام upsert للتحديث أو الإضافة
                    self.mongo_db.currencies.update_one(
                        {'code': code},
                        {'$set': mongo_data},
                        upsert=True
                    )

                    # تحديث حالة المزامنة
                    self.sqlite_cursor.execute(
                        "UPDATE currencies SET sync_status = 'synced' WHERE code = ?",
                        (code,)
                    )
                    self.sqlite_conn.commit()
                    safe_print(f"INFO: [Repo] تم مزامنة العملة {code} أونلاين")

                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل مزامنة العملة {code} أونلاين: {e}")

            return True

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حفظ العملة {code}: {e}")
            return False

    def delete_currency(self, code: str) -> bool:
        """حذف عملة (مع مزامنة)"""
        try:
            if code.upper() == 'EGP':
                safe_print(f"WARNING: [Repo] لا يمكن حذف العملة الأساسية")
                return False

            # حذف من SQLite
            self.sqlite_cursor.execute("DELETE FROM currencies WHERE code = ?", (code.upper(),))
            self.sqlite_conn.commit()

            # حذف من MongoDB
            if self.online:
                try:
                    self.mongo_db.currencies.delete_one({'code': code.upper()})
                    safe_print(f"INFO: [Repo] تم حذف العملة {code} من الأونلاين")
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل حذف العملة من MongoDB: {e}")

            safe_print(f"INFO: [Repo] تم حذف العملة {code}")
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف العملة {code}: {e}")
            return False

    def fetch_live_exchange_rate(self, currency_code: str) -> float | None:
        """جلب سعر الصرف الحقيقي من الإنترنت"""
        import urllib.request

        currency_code = currency_code.upper()
        if currency_code == 'EGP':
            return 1.0

        try:
            # API 1: Open Exchange Rates
            url = "https://open.er-api.com/v6/latest/USD"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310 - URL is hardcoded HTTPS
                data = json.loads(response.read().decode())
                if data.get('result') == 'success' and 'rates' in data:
                    rates = data['rates']
                    egp_rate = rates.get('EGP', 0)
                    currency_rate = rates.get(currency_code, 0)

                    if egp_rate > 0 and currency_rate > 0:
                        rate = egp_rate / currency_rate
                        safe_print(f"INFO: [Repo] سعر {currency_code} = {rate:.4f} EGP (من API)")
                        return float(round(rate, 4))
        except Exception as e:
            safe_print(f"WARNING: [Repo] فشل جلب السعر من API 1: {e}")

        try:
            # API 2: ExchangeRate-API
            url = f"https://api.exchangerate-api.com/v4/latest/{currency_code}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310 - URL is hardcoded HTTPS
                data = json.loads(response.read().decode())
                if 'rates' in data:
                    egp_rate = data['rates'].get('EGP', 0)
                    if egp_rate > 0:
                        safe_print(f"INFO: [Repo] سعر {currency_code} = {egp_rate:.4f} EGP (من API 2)")
                        return float(round(egp_rate, 4))
        except Exception as e:
            safe_print(f"WARNING: [Repo] فشل جلب السعر من API 2: {e}")

        return None

    def init_default_currencies(self):
        """إنشاء العملات الافتراضية مع جلب الأسعار الحقيقية من الإنترنت"""
        default_currencies = [
            {'code': 'EGP', 'name': 'جنيه مصري', 'symbol': 'ج.م', 'rate': 1.0, 'is_base': True},
            {'code': 'USD', 'name': 'دولار أمريكي', 'symbol': 'دولار'},
            {'code': 'SAR', 'name': 'ريال سعودي', 'symbol': 'ر.س', 'rate': 12.65},
            {'code': 'AED', 'name': 'درهم إماراتي', 'symbol': 'د.إ', 'rate': 12.92},
        ]

        safe_print(f"INFO: [Repo] جاري إنشاء العملات الافتراضية وجلب الأسعار من الإنترنت...")

        for curr in default_currencies:
            code = curr['code']

            # جلب السعر الحقيقي من الإنترنت
            if code == 'EGP':
                curr['rate'] = 1.0
            else:
                live_rate = self.fetch_live_exchange_rate(code)
                if live_rate:
                    curr['rate'] = live_rate
                else:
                    # أسعار احتياطية في حالة فشل الاتصال
                    fallback_rates = {'USD': 49.50, 'SAR': 13.20, 'AED': 13.48}
                    curr['rate'] = fallback_rates.get(code, 1.0)
                    safe_print(f"WARNING: [Repo] استخدام سعر احتياطي لـ {code}: {curr['rate']}")

            self.save_currency(curr)

        safe_print(f"INFO: [Repo] تم إنشاء العملات الافتراضية بنجاح")

    def update_all_exchange_rates(self) -> dict:
        """تحديث جميع أسعار الصرف من الإنترنت"""
        safe_print(f"INFO: [Repo] جاري تحديث جميع أسعار الصرف...")

        currencies = self.get_all_currencies()
        updated = 0
        failed = 0
        results = {}

        for curr in currencies:
            code = curr['code']
            if code == 'EGP':
                continue

            live_rate = self.fetch_live_exchange_rate(code)
            if live_rate:
                curr['rate'] = live_rate
                self.save_currency(curr)
                updated += 1
                results[code] = {'success': True, 'rate': live_rate}
                safe_print(f"INFO: [Repo] تم تحديث {code}: {live_rate}")
            else:
                failed += 1
                results[code] = {'success': False, 'rate': curr['rate']}
                safe_print(f"WARNING: [Repo] فشل تحديث {code}")

        safe_print(f"INFO: [Repo] تم تحديث {updated} عملة، فشل {failed}")
        return {'updated': updated, 'failed': failed, 'results': results}

    # ============================================
    # دوال تنظيف التكرارات وإصلاح البيانات
    # ============================================

    def cleanup_duplicate_clients(self) -> dict:
        """
        تنظيف العملاء المكررين (يحتفظ بالأقدم ويحذف الأحدث)
        Returns: dict with counts of duplicates found and removed
        """
        safe_print(f"INFO: [Repo] جاري البحث عن العملاء المكررين...")
        result: dict[str, Any] = {"found": 0, "removed": 0, "details": []}

        try:
            # جلب كل العملاء مرتبين بتاريخ الإنشاء
            self.sqlite_cursor.execute("""
                SELECT id, _mongo_id, name, phone, created_at
                FROM clients
                WHERE status != 'مؤرشف'
                ORDER BY created_at ASC
            """)
            rows = self.sqlite_cursor.fetchall()

            seen_names = {}  # {name_lower: first_id}
            seen_phones = {}  # {phone_clean: first_id}
            duplicates_to_archive = []

            for row in rows:
                row_dict = dict(row)
                client_id = row_dict['id']
                name = row_dict.get('name', '').strip().lower()
                phone = row_dict.get('phone', '')
                phone_clean = phone.strip().replace(" ", "").replace("-", "") if phone else None

                is_duplicate = False
                reason = ""

                # فحص تكرار الاسم
                if name and name in seen_names:
                    is_duplicate = True
                    reason = f"اسم مكرر: {row_dict.get('name')}"
                elif name:
                    seen_names[name] = client_id

                # فحص تكرار الهاتف
                if not is_duplicate and phone_clean and phone_clean in seen_phones:
                    is_duplicate = True
                    reason = f"هاتف مكرر: {phone}"
                elif phone_clean:
                    seen_phones[phone_clean] = client_id

                if is_duplicate:
                    duplicates_to_archive.append((client_id, row_dict.get('_mongo_id'), reason))
                    result["found"] += 1

            # أرشفة المكررين
            for client_id, _mongo_id, reason in duplicates_to_archive:
                try:
                    self.sqlite_cursor.execute(
                        "UPDATE clients SET status = 'مؤرشف', sync_status = 'modified_offline' WHERE id = ?",
                        (client_id,)
                    )
                    result["removed"] += 1
                    result["details"].append({"id": client_id, "reason": reason})
                    safe_print(f"INFO: [Repo] تم أرشفة العميل المكرر ID: {client_id} - {reason}")
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل أرشفة العميل {client_id}: {e}")

            self.sqlite_conn.commit()

            # مزامنة مع MongoDB
            if self.online and duplicates_to_archive:
                try:
                    for _client_id, mongo_id, _ in duplicates_to_archive:
                        if mongo_id:
                            self.mongo_db.clients.update_one(
                                {"_id": self._to_objectid(mongo_id)},
                                {"$set": {"status": "مؤرشف"}}
                            )
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل مزامنة أرشفة العملاء المكررين: {e}")

            safe_print(f"INFO: [Repo] تم العثور على {result['found']} عميل مكرر، تم أرشفة {result['removed']}")

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تنظيف العملاء المكررين: {e}")

        return result

    def cleanup_duplicate_projects(self) -> dict:
        """
        تنظيف المشاريع المكررة (نفس الاسم لنفس العميل)
        """
        safe_print(f"INFO: [Repo] جاري البحث عن المشاريع المكررة...")
        result: dict[str, Any] = {"found": 0, "removed": 0, "details": []}

        try:
            self.sqlite_cursor.execute("""
                SELECT id, _mongo_id, name, client_id, created_at
                FROM projects
                WHERE status != 'مؤرشف'
                ORDER BY created_at ASC
            """)
            rows = self.sqlite_cursor.fetchall()

            seen_projects = {}  # {(name_lower, client_id): first_id}
            duplicates_to_archive = []

            for row in rows:
                row_dict = dict(row)
                project_id = row_dict['id']
                name = row_dict.get('name', '').strip().lower()
                client_id = row_dict.get('client_id', '')
                key = (name, client_id)

                if key in seen_projects:
                    duplicates_to_archive.append((project_id, row_dict.get('_mongo_id'), f"مشروع مكرر: {row_dict.get('name')}"))
                    result["found"] += 1
                else:
                    seen_projects[key] = project_id

            for project_id, _mongo_id, reason in duplicates_to_archive:
                try:
                    self.sqlite_cursor.execute(
                        "UPDATE projects SET status = 'مؤرشف', sync_status = 'modified_offline' WHERE id = ?",
                        (project_id,)
                    )
                    result["removed"] += 1
                    result["details"].append({"id": project_id, "reason": reason})
                    safe_print(f"INFO: [Repo] تم أرشفة المشروع المكرر ID: {project_id} - {reason}")
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل أرشفة المشروع {project_id}: {e}")

            self.sqlite_conn.commit()

            if self.online and duplicates_to_archive:
                try:
                    for _project_id, mongo_id, _ in duplicates_to_archive:
                        if mongo_id:
                            self.mongo_db.projects.update_one(
                                {"_id": self._to_objectid(mongo_id)},
                                {"$set": {"status": "مؤرشف"}}
                            )
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل مزامنة أرشفة المشاريع المكررة: {e}")

            safe_print(f"INFO: [Repo] تم العثور على {result['found']} مشروع مكرر، تم أرشفة {result['removed']}")

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تنظيف المشاريع المكررة: {e}")

        return result

    def cleanup_duplicate_payments(self) -> dict:
        """
        تنظيف الدفعات المكررة (نفس المشروع + نفس التاريخ + نفس المبلغ)
        """
        safe_print(f"INFO: [Repo] جاري البحث عن الدفعات المكررة...")
        result: dict[str, Any] = {"found": 0, "removed": 0, "details": []}

        try:
            self.sqlite_cursor.execute("""
                SELECT id, _mongo_id, project_id, date, amount, created_at
                FROM payments
                ORDER BY created_at ASC
            """)
            rows = self.sqlite_cursor.fetchall()

            seen_payments = {}  # {(project_id, date_short, amount): first_id}
            duplicates_to_delete = []

            for row in rows:
                row_dict = dict(row)
                payment_id = row_dict['id']
                project_id = row_dict.get('project_id', '')
                date_str = str(row_dict.get('date', ''))[:10]  # YYYY-MM-DD
                amount = row_dict.get('amount', 0)
                key = (project_id, date_str, amount)

                if key in seen_payments:
                    duplicates_to_delete.append((payment_id, row_dict.get('_mongo_id'), f"دفعة مكررة: {amount} في {date_str}"))
                    result["found"] += 1
                else:
                    seen_payments[key] = payment_id

            for payment_id, _mongo_id, reason in duplicates_to_delete:
                try:
                    self.sqlite_cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
                    result["removed"] += 1
                    result["details"].append({"id": payment_id, "reason": reason})
                    safe_print(f"INFO: [Repo] تم حذف الدفعة المكررة ID: {payment_id} - {reason}")
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل حذف الدفعة {payment_id}: {e}")

            self.sqlite_conn.commit()

            if self.online and duplicates_to_delete:
                try:
                    for _payment_id, mongo_id, _ in duplicates_to_delete:
                        if mongo_id:
                            self.mongo_db.payments.delete_one({"_id": self._to_objectid(mongo_id)})
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل حذف الدفعات المكررة من MongoDB: {e}")

            safe_print(f"INFO: [Repo] تم العثور على {result['found']} دفعة مكررة، تم حذف {result['removed']}")

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تنظيف الدفعات المكررة: {e}")

        return result

    def fix_account_hierarchy(self) -> dict:
        """
        إصلاح العلاقات الهرمية للحسابات (ربط parent_code بشكل صحيح)
        """
        safe_print(f"INFO: [Repo] جاري إصلاح العلاقات الهرمية للحسابات...")
        result: dict[str, Any] = {"fixed": 0, "errors": 0, "details": []}

        try:
            # جلب كل الحسابات
            self.sqlite_cursor.execute("SELECT * FROM accounts ORDER BY code")
            rows = self.sqlite_cursor.fetchall()

            accounts_by_code = {}
            for row in rows:
                row_dict = dict(row)
                accounts_by_code[row_dict['code']] = row_dict

            for code, account in accounts_by_code.items():
                # تحديد الحساب الأب بناءً على الكود
                # مثال: 1100 -> parent = 1000, 1110 -> parent = 1100
                if len(code) > 4:
                    parent_code = code[:-1] + '0'  # 11100 -> 11100 -> 1110
                    if parent_code not in accounts_by_code:
                        parent_code = code[:-2] + '00'  # 1110 -> 1100
                    if parent_code not in accounts_by_code:
                        parent_code = code[:-3] + '000'  # 1100 -> 1000
                elif len(code) == 4:
                    parent_code = code[0] + '000'  # 1100 -> 1000
                else:
                    parent_code = None

                current_parent = account.get('parent_id') or account.get('parent_code')

                # تحديث إذا كان الـ parent مختلف
                if parent_code and parent_code in accounts_by_code and parent_code != code:
                    if current_parent != parent_code:
                        try:
                            self.sqlite_cursor.execute(
                                "UPDATE accounts SET parent_id = ?, sync_status = 'modified_offline' WHERE code = ?",
                                (parent_code, code)
                            )
                            result["fixed"] += 1
                            result["details"].append({"code": code, "new_parent": parent_code})
                            safe_print(f"INFO: [Repo] تم ربط الحساب {code} بالحساب الأب {parent_code}")
                        except Exception as e:
                            result["errors"] += 1
                            safe_print(f"WARNING: [Repo] فشل ربط الحساب {code}: {e}")

            self.sqlite_conn.commit()

            # تحديث is_group للحسابات التي لها أطفال
            self.update_is_group_flags()

            # مزامنة مع MongoDB
            if self.online:
                try:
                    for detail in result["details"]:
                        self.mongo_db.accounts.update_one(
                            {"code": detail["code"]},
                            {"$set": {"parent_id": detail["new_parent"], "parent_code": detail["new_parent"]}}
                        )
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل مزامنة إصلاح الحسابات: {e}")

            safe_print(f"INFO: [Repo] تم إصلاح {result['fixed']} حساب، أخطاء: {result['errors']}")

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل إصلاح العلاقات الهرمية: {e}")

        return result

    def update_is_group_flags(self):
        """
        تحديث علامة is_group للحسابات (الحسابات التي لها أطفال)
        """
        try:
            # أولاً: تعيين كل الحسابات كـ is_group = False
            self.sqlite_cursor.execute("UPDATE accounts SET is_group = 0")

            # ثانياً: تحديد الحسابات التي لها أطفال
            self.sqlite_cursor.execute("""
                UPDATE accounts SET is_group = 1
                WHERE code IN (
                    SELECT DISTINCT parent_id FROM accounts WHERE parent_id IS NOT NULL AND parent_id != ''
                )
            """)

            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repo] تم تحديث علامات is_group للحسابات")

        except Exception as e:
            safe_print(f"WARNING: [Repo] فشل تحديث علامات is_group: {e}")

    def cleanup_all_duplicates(self) -> dict:
        """
        تنظيف شامل لكل التكرارات (عملاء + مشاريع + دفعات)
        """
        safe_print(f"INFO: [Repo] ========== بدء التنظيف الشامل ==========")

        results = {
            "clients": self.cleanup_duplicate_clients(),
            "projects": self.cleanup_duplicate_projects(),
            "payments": self.cleanup_duplicate_payments(),
            "accounts": self.fix_account_hierarchy()
        }

        total_found = sum(r.get("found", 0) for r in results.values())
        total_fixed = sum(r.get("removed", 0) + r.get("fixed", 0) for r in results.values())

        safe_print(f"INFO: [Repo] ========== انتهى التنظيف الشامل ==========")
        safe_print(f"INFO: [Repo] إجمالي المشاكل: {total_found}, تم إصلاح: {total_fixed}")

        return results

    # ==================== دوال التعامل مع المهام (Tasks) ====================

    def create_task(self, task_data: dict) -> dict:
        """
        إنشاء مهمة جديدة
        """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        # تحضير البيانات
        task_data.get('id') or self._generate_task_id()

        sql = """
            INSERT INTO tasks (
                sync_status, created_at, last_modified,
                title, description, priority, status, category,
                due_date, due_time, completed_at,
                related_project_id, related_client_id, tags,
                reminder, reminder_minutes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        tags_json = json.dumps(task_data.get('tags', []), ensure_ascii=False)
        
        # تحويل القيم الفارغة إلى None لتجنب مشاكل FOREIGN KEY
        related_project = task_data.get('related_project_id')
        related_client = task_data.get('related_client_id')
        if related_project == '':
            related_project = None
        if related_client == '':
            related_client = None

        self.sqlite_cursor.execute(sql, (
            'new_offline', now_iso, now_iso,
            task_data.get('title', ''),
            task_data.get('description') or None,
            task_data.get('priority', 'MEDIUM'),
            task_data.get('status', 'TODO'),
            task_data.get('category', 'GENERAL'),
            task_data.get('due_date'),
            task_data.get('due_time'),
            task_data.get('completed_at'),
            related_project,
            related_client,
            tags_json,
            1 if task_data.get('reminder', False) else 0,
            task_data.get('reminder_minutes', 30)
        ))
        self.sqlite_conn.commit()

        local_id = self.sqlite_cursor.lastrowid
        task_data['id'] = str(local_id)
        task_data['created_at'] = now_iso
        task_data['last_modified'] = now_iso

        safe_print(f"INFO: [Repo] تم إنشاء مهمة: {task_data.get('title')} (ID: {local_id})")

        # مزامنة مع MongoDB
        if self.online:
            try:
                mongo_data = task_data.copy()
                mongo_data['created_at'] = now_dt
                mongo_data['last_modified'] = now_dt
                if mongo_data.get('due_date'):
                    mongo_data['due_date'] = datetime.fromisoformat(mongo_data['due_date']) if isinstance(mongo_data['due_date'], str) else mongo_data['due_date']
                if mongo_data.get('completed_at'):
                    mongo_data['completed_at'] = datetime.fromisoformat(mongo_data['completed_at']) if isinstance(mongo_data['completed_at'], str) else mongo_data['completed_at']

                result = self.mongo_db.tasks.insert_one(mongo_data)
                mongo_id = str(result.inserted_id)

                self.sqlite_cursor.execute(
                    "UPDATE tasks SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
                    (mongo_id, local_id)
                )
                self.sqlite_conn.commit()
                task_data['_mongo_id'] = mongo_id
                safe_print(f"INFO: [Repo] تم مزامنة المهمة أونلاين (Mongo ID: {mongo_id})")
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل مزامنة المهمة: {e}")

        return task_data

    def update_task(self, task_id: str, task_data: dict) -> dict:
        """
        تحديث مهمة موجودة
        """
        now_iso = datetime.now().isoformat()

        tags_json = json.dumps(task_data.get('tags', []), ensure_ascii=False)
        
        # تحويل القيم الفارغة إلى None لتجنب مشاكل FOREIGN KEY
        related_project = task_data.get('related_project_id')
        related_client = task_data.get('related_client_id')
        if related_project == '':
            related_project = None
        if related_client == '':
            related_client = None

        sql = """
            UPDATE tasks SET
                title = ?, description = ?, priority = ?, status = ?, category = ?,
                due_date = ?, due_time = ?, completed_at = ?,
                related_project_id = ?, related_client_id = ?, tags = ?,
                reminder = ?, reminder_minutes = ?, is_archived = ?,
                last_modified = ?, sync_status = 'modified_offline'
            WHERE id = ? OR _mongo_id = ?
        """

        self.sqlite_cursor.execute(sql, (
            task_data.get('title', ''),
            task_data.get('description') or None,
            task_data.get('priority', 'MEDIUM'),
            task_data.get('status', 'TODO'),
            task_data.get('category', 'GENERAL'),
            task_data.get('due_date'),
            task_data.get('due_time'),
            task_data.get('completed_at'),
            related_project,
            related_client,
            tags_json,
            1 if task_data.get('reminder', False) else 0,
            task_data.get('reminder_minutes', 30),
            1 if task_data.get('is_archived', False) else 0,
            now_iso,
            task_id, task_id
        ))
        self.sqlite_conn.commit()

        safe_print(f"INFO: [Repo] تم تحديث مهمة: {task_data.get('title')}")

        # مزامنة مع MongoDB
        if self.online:
            try:
                update_data = task_data.copy()
                update_data['last_modified'] = datetime.now()
                if update_data.get('due_date') and isinstance(update_data['due_date'], str):
                    update_data['due_date'] = datetime.fromisoformat(update_data['due_date'])
                if update_data.get('completed_at') and isinstance(update_data['completed_at'], str):
                    update_data['completed_at'] = datetime.fromisoformat(update_data['completed_at'])

                self.mongo_db.tasks.update_one(
                    {"$or": [{"_id": self._to_objectid(task_id)}, {"id": task_id}]},
                    {"$set": update_data}
                )

                self.sqlite_cursor.execute(
                    "UPDATE tasks SET sync_status = 'synced' WHERE id = ? OR _mongo_id = ?",
                    (task_id, task_id)
                )
                self.sqlite_conn.commit()
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل مزامنة تحديث المهمة: {e}")

        return task_data

    def delete_task(self, task_id: str) -> bool:
        """
        حذف مهمة
        """
        try:
            # حذف من SQLite
            self.sqlite_cursor.execute(
                "DELETE FROM tasks WHERE id = ? OR _mongo_id = ?",
                (task_id, task_id)
            )
            self.sqlite_conn.commit()

            safe_print(f"INFO: [Repo] تم حذف مهمة (ID: {task_id})")

            # حذف من MongoDB
            if self.online:
                try:
                    self.mongo_db.tasks.delete_one(
                        {"$or": [{"_id": self._to_objectid(task_id)}, {"id": task_id}]}
                    )
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل حذف المهمة من MongoDB: {e}")

            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف المهمة: {e}")
            return False

    def get_task_by_id(self, task_id: str) -> dict | None:
        """
        جلب مهمة بالـ ID
        """
        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM tasks WHERE id = ? OR _mongo_id = ?",
                (task_id, task_id)
            )
            row = self.sqlite_cursor.fetchone()

            if row:
                return dict(self._row_to_task_dict(row))
            return None
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب المهمة: {e}")
            return None

    def get_all_tasks(self) -> list[dict]:
        """
        جلب جميع المهام
        """
        try:
            self.sqlite_cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            rows = self.sqlite_cursor.fetchall()

            tasks = [self._row_to_task_dict(row) for row in rows]
            safe_print(f"INFO: [Repo] تم جلب {len(tasks)} مهمة")
            return tasks
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب المهام: {e}")
            return []

    def get_tasks_by_status(self, status: str) -> list[dict]:
        """
        جلب المهام حسب الحالة
        """
        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                (status,)
            )
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_task_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب المهام بالحالة: {e}")
            return []

    def get_tasks_by_project(self, project_id: str) -> list[dict]:
        """
        جلب المهام المرتبطة بمشروع
        """
        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM tasks WHERE related_project_id = ? ORDER BY created_at DESC",
                (project_id,)
            )
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_task_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب مهام المشروع: {e}")
            return []

    def get_tasks_by_client(self, client_id: str) -> list[dict]:
        """
        جلب المهام المرتبطة بعميل
        """
        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM tasks WHERE related_client_id = ? ORDER BY created_at DESC",
                (client_id,)
            )
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_task_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب مهام العميل: {e}")
            return []

    def get_overdue_tasks(self) -> list[dict]:
        """
        جلب المهام المتأخرة
        """
        try:
            now_iso = datetime.now().isoformat()
            self.sqlite_cursor.execute(
                """SELECT * FROM tasks
                   WHERE due_date < ? AND status NOT IN ('COMPLETED', 'CANCELLED')
                   ORDER BY due_date ASC""",
                (now_iso,)
            )
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_task_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب المهام المتأخرة: {e}")
            return []

    def get_today_tasks(self) -> list[dict]:
        """
        جلب مهام اليوم
        """
        try:
            today = datetime.now().date().isoformat()
            self.sqlite_cursor.execute(
                """SELECT * FROM tasks
                   WHERE date(due_date) = date(?)
                   ORDER BY due_time ASC""",
                (today,)
            )
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_task_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب مهام اليوم: {e}")
            return []

    def _row_to_task_dict(self, row) -> dict:
        """
        تحويل صف قاعدة البيانات إلى dict
        """
        task = {
            'id': str(row['id']),
            '_mongo_id': row['_mongo_id'],
            'sync_status': row['sync_status'],
            'created_at': row['created_at'],
            'last_modified': row['last_modified'],
            'title': row['title'],
            'description': row['description'],
            'priority': row['priority'],
            'status': row['status'],
            'category': row['category'],
            'due_date': row['due_date'],
            'due_time': row['due_time'],
            'completed_at': row['completed_at'],
            'related_project_id': row['related_project_id'],
            'related_client_id': row['related_client_id'],
            'tags': json.loads(row['tags']) if row['tags'] else [],
            'reminder': bool(row['reminder']),
            'reminder_minutes': row['reminder_minutes'] or 30,
            'assigned_to': row['assigned_to'],
            'is_archived': bool(row['is_archived']) if 'is_archived' in row.keys() else False
        }
        return task

    def _generate_task_id(self) -> str:
        """
        توليد ID فريد للمهمة
        """
        import uuid
        return str(uuid.uuid4())[:8]

    # ⚡ دوال أرقام الفواتير الثابتة
    def get_invoice_number_for_project(self, project_name: str) -> str:
        """
        جلب رقم الفاتورة الثابت للمشروع من جدول invoice_numbers
        """
        try:
            self.sqlite_cursor.execute(
                "SELECT invoice_number FROM invoice_numbers WHERE project_name = ?",
                (project_name,)
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return str(row[0])
            return ""
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب رقم الفاتورة: {e}")
            return ""

    def get_all_invoice_numbers(self) -> dict:
        """
        جلب كل أرقام الفواتير كـ dict {project_name: invoice_number}
        """
        try:
            self.sqlite_cursor.execute("SELECT project_name, invoice_number FROM invoice_numbers")
            rows = self.sqlite_cursor.fetchall()
            return {row[0]: row[1] for row in rows}
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب أرقام الفواتير: {e}")
            return {}

    def ensure_invoice_number(self, project_name: str) -> str:
        """
        التأكد من وجود رقم فاتورة للمشروع، وإنشاء واحد جديد إذا لم يكن موجوداً
        """
        try:
            # تحقق من وجود رقم محفوظ
            existing = self.get_invoice_number_for_project(project_name)
            if existing:
                return str(existing)

            # ولّد رقم جديد
            self.sqlite_cursor.execute("SELECT MAX(id) FROM invoice_numbers")
            max_id = self.sqlite_cursor.fetchone()[0] or 0
            new_seq = max_id + 1
            invoice_number = f"SW-{97161 + new_seq}"

            # احفظ الرقم الجديد
            self.sqlite_cursor.execute(
                "INSERT INTO invoice_numbers (project_name, invoice_number, created_at) VALUES (?, ?, ?)",
                (project_name, invoice_number, datetime.now().isoformat())
            )
            self.sqlite_conn.commit()

            safe_print(f"INFO: [Repo] تم إنشاء رقم فاتورة جديد: {project_name} -> {invoice_number}")
            return str(invoice_number)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل إنشاء رقم الفاتورة: {e}")
            return ""

    def restore_all_invoice_numbers(self):
        """
        ✅ استعادة كل أرقام الفواتير من جدول invoice_numbers إلى جدول projects
        يُستدعى بعد كل sync للتأكد من عدم فقدان الأرقام
        """
        try:
            # تحديث كل المشاريع بأرقام الفواتير المحفوظة
            self.sqlite_cursor.execute("""
                UPDATE projects SET invoice_number = (
                    SELECT inv.invoice_number FROM invoice_numbers inv
                    WHERE inv.project_name = projects.name
                )
                WHERE EXISTS (
                    SELECT 1 FROM invoice_numbers inv WHERE inv.project_name = projects.name
                )
            """)
            updated = self.sqlite_cursor.rowcount
            self.sqlite_conn.commit()

            # إنشاء أرقام للمشاريع الجديدة اللي مش عندها رقم
            self.sqlite_cursor.execute("""
                SELECT id, name FROM projects
                WHERE invoice_number IS NULL OR invoice_number = ''
            """)
            new_projects = self.sqlite_cursor.fetchall()

            for row in new_projects:
                project_id = row[0]
                project_name = row[1]
                invoice_number = self.ensure_invoice_number(project_name)
                if invoice_number:
                    self.sqlite_cursor.execute(
                        "UPDATE projects SET invoice_number = ? WHERE id = ?",
                        (invoice_number, project_id)
                    )

            if new_projects:
                self.sqlite_conn.commit()

            safe_print(f"INFO: [Repo] ✅ تم استعادة أرقام الفواتير ({updated} محدث, {len(new_projects)} جديد)")
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل استعادة أرقام الفواتير: {e}")
            return False



# --- كود للاختبار (اختياري) ---
if __name__ == "__main__":
    safe_print(f"--- بدء اختبار الـ Repository ---")
    repo = Repository()
    safe_print(f"حالة الاتصال: {'أونلاين' if repo.is_online() else 'أوفلاين'}")
    safe_print(f"--- انتهاء الاختبار ---")
