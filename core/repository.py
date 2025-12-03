# الملف: core/repository.py

import sqlite3
import pymongo
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from . import schemas # استيراد ملف الاسكيما اللي عملناه
import time  # ⚡ لحساب وقت الـ Cache

# --- إعدادات الاتصال ---
# (استخدمت بيانات اليوزر 'skywave_app' لأنها الأنسب للبرنامج)
MONGO_URI = "mongodb://skywaveads:Newjoer2k24$@147.79.66.116:27017/skywave_erp_db?authSource=admin"

LOCAL_DB_FILE = "skywave_local.db" # اسم ملف قاعدة البيانات الأوفلاين
DB_NAME = "skywave_erp_db"
LOCAL_DB_FILE = "skywave_local.db" # اسم ملف قاعدة البيانات الأوفلاين


class Repository:
    """
    ⚡ المخزن الذكي مع Caching للسرعة.
    يتعامل مع الأونلاين (Mongo) والأوفلاين (SQLite) في مكان واحد.
    """
    
    def __init__(self):
        self.online = False
        self.mongo_client = None
        self.mongo_db = None
        

        
        try:
            # 1. محاولة الاتصال بـ MongoDB (أونلاين)
            self.mongo_client = pymongo.MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=5000 # مهلة 5 ثواني
            )
            self.mongo_client.server_info() # اختبار الاتصال
            self.mongo_db = self.mongo_client[DB_NAME]
            self.online = True
            print("INFO: متصل بقاعدة البيانات الأونلاين (MongoDB).")
            
        except pymongo.errors.ServerSelectionTimeoutError:
            print("WARNING: فشل الاتصال بـ MongoDB. سيبدأ البرنامج في وضع الأوفلاين.")
            self.online = False
        
        # 2. دائماً اتصل بـ SQLite (أوفلاين)
        self.sqlite_conn = sqlite3.connect(LOCAL_DB_FILE, check_same_thread=False)
        self.sqlite_conn.row_factory = sqlite3.Row # عشان نقدر نوصل للداتا بالاسم
        self.sqlite_cursor = self.sqlite_conn.cursor()
        print(f"INFO: متصل بقاعدة البيانات الأوفلاين ({LOCAL_DB_FILE}).")
        
        # 3. بناء الجداول الأوفلاين لو مش موجودة
        self._init_local_db()

    def _init_local_db(self):
        """
        دالة داخلية تنشئ كل الجداول في ملف SQLite المحلي 
        فقط إذا لم تكن موجودة.
        """
        print("INFO: جاري فحص الجداول المحلية (SQLite)...")
        
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
        except:
            pass  # العمود موجود بالفعل
        try:
            self.sqlite_cursor.execute("ALTER TABLE accounts ADD COLUMN description TEXT")
        except:
            pass  # العمود موجود بالفعل
        try:
            self.sqlite_cursor.execute("ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'نشط'")
        except:
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
        except:
            pass  # العمود موجود بالفعل
        
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
            client_notes TEXT
        )""")
        
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
            project_notes TEXT
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

        # جدول عروض الأسعار (quotations)
        self.sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS quotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            quote_number TEXT NOT NULL UNIQUE,
            client_id TEXT NOT NULL,
            project_id TEXT,
            issue_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            items TEXT NOT NULL,
            subtotal REAL NOT NULL,
            discount_rate REAL DEFAULT 0.0,
            discount_amount REAL DEFAULT 0.0,
            tax_rate REAL DEFAULT 0.0,
            tax_amount REAL NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL,
            currency TEXT NOT NULL,
            notes TEXT
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
        except:
            pass  # العمود موجود بالفعل

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
            print("INFO: [Repository] Added 'action' column to sync_queue table")
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
        print("INFO: الجداول المحلية جاهزة.")
        
        # ⚡ إنشاء indexes لتحسين الأداء (مهم جداً للسرعة)
        self._create_sqlite_indexes()
        
        # تحسين قاعدة البيانات
        self._optimize_database()
        
        # إنشاء collection و indexes في MongoDB إذا كان متصل
        if self.online:
            self._init_mongo_indexes()

    def _create_sqlite_indexes(self):
        """
        إنشاء indexes في SQLite لتحسين الأداء
        """
        try:
            print("INFO: جاري إنشاء indexes في SQLite...")
            
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
            
            # Indexes لـ notifications
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type)")
            self.sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at)")
            
            self.sqlite_conn.commit()
            print("INFO: تم إنشاء indexes في SQLite بنجاح.")
        except Exception as e:
            print(f"WARNING: فشل إنشاء بعض indexes في SQLite: {e}")

    def _init_mongo_indexes(self):
        """
        إنشاء indexes في MongoDB لتحسين الأداء
        """
        try:
            print("INFO: جاري إنشاء indexes في MongoDB...")
            
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
            
            print("INFO: تم إنشاء indexes في MongoDB بنجاح.")
        except Exception as e:
            print(f"WARNING: فشل إنشاء بعض indexes في MongoDB: {e}")

    def is_online(self) -> bool:
        """ دالة بسيطة لمعرفة حالة الاتصال """
        return self.online

    # --- دوال التعامل مع العملاء (كمثال) ---

    def create_client(self, client_data: schemas.Client) -> schemas.Client:
        """
        إنشاء عميل جديد (بذكاء)
        1. يحفظ في SQLite دائماً (بحالة 'new_offline').
        2. يحاول الحفظ في Mongo لو فيه نت.
        """
        now = datetime.now().isoformat()
        client_data.created_at = now
        client_data.last_modified = now
        client_data.sync_status = 'new_offline'
        client_data.status = schemas.ClientStatus.ACTIVE

        # 1. الحفظ في SQLite (الأوفلاين أولاً)
        sql = """
            INSERT INTO clients (
                sync_status, created_at, last_modified, name, company_name, email,
                phone, address, country, vat_number, status,
                client_type, work_field, logo_path, client_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.sqlite_cursor.execute(sql, (
            client_data.sync_status, now, now, client_data.name, client_data.company_name,
            client_data.email, client_data.phone, client_data.address, client_data.country,
            client_data.vat_number, client_data.status.value,
            client_data.client_type, client_data.work_field,
            client_data.logo_path, client_data.client_notes
        ))
        self.sqlite_conn.commit()
        
        local_id = self.sqlite_cursor.lastrowid
        print(f"INFO: تم حفظ العميل '{client_data.name}' محلياً (ID: {local_id}).")

        # 2. محاولة الحفظ في MongoDB (الأونلاين)
        if self.online:
            try:
                # نحول الـ Pydantic model لـ dict عشان Mongo يفهمه
                client_dict = client_data.model_dump(exclude={"_mongo_id"}) 
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
                print(f"INFO: تم مزامنة العميل '{client_data.name}' أونلاين (Mongo ID: {mongo_id}).")
                
            except Exception as e:
                print(f"ERROR: فشل مزامنة العميل الجديد '{client_data.name}': {e}")
                # (سيبقى الـ status 'new_offline' ليتم مزامنته لاحقاً)
        
        return client_data

    def update_client(self, client_id: str, client_data: schemas.Client) -> Optional[schemas.Client]:
        """
        (جديدة) تحديث بيانات عميل موجود.
        """
        print(f"INFO: [Repo] جاري تحديث العميل ID: {client_id}...")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            sql = """
                UPDATE clients SET
                    name = ?, company_name = ?, email = ?, phone = ?, 
                    address = ?, country = ?, vat_number = ?, status = ?,
                    client_type = ?, work_field = ?, logo_path = ?, client_notes = ?,
                    last_modified = ?, sync_status = 'modified_offline'
                WHERE id = ? OR _mongo_id = ?
            """
            params = (
                client_data.name, client_data.company_name, client_data.email,
                client_data.phone, client_data.address, client_data.country,
                client_data.vat_number, client_data.status.value,
                client_data.client_type, client_data.work_field,
                client_data.logo_path, client_data.client_notes,
                now_iso, client_id, client_id
            )
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
        except Exception as e:
            print(f"ERROR: [Repo] فشل تحديث العميل (SQLite): {e}")
            return None

        if self.online:
            try:
                update_dict = client_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                update_dict['last_modified'] = now_dt
                update_dict['status'] = client_data.status.value

                self.mongo_db.clients.update_one(
                    {"$or": [{"_id": self._to_objectid(client_id)}, {"_mongo_id": client_id}]},
                    {"$set": update_dict}
                )

                self.sqlite_cursor.execute(
                    "UPDATE clients SET sync_status = 'synced' WHERE id = ? OR _mongo_id = ?",
                    (client_id, client_id)
                )
                self.sqlite_conn.commit()
                print(f"INFO: [Repo] تم مزامنة تحديث العميل ID: {client_id} أونلاين.")

            except Exception as e:
                print(f"ERROR: [Repo] فشل تحديث العميل (Mongo): {e}")

        return client_data

    def get_all_clients(self) -> List[schemas.Client]:
        """
        ⚡ جلب كل العملاء "النشطين" فقط (محسّن للسرعة)
        """
        active_status = schemas.ClientStatus.ACTIVE.value
        
        # ⚡ استخدام SQLite مباشرة (أسرع بكتير)
        try:
            self.sqlite_cursor.execute("SELECT * FROM clients WHERE status = ?", (active_status,))
            rows = self.sqlite_cursor.fetchall()
            clients_list = [schemas.Client(**dict(row)) for row in rows]
            return clients_list
        except Exception as e:
            print(f"ERROR: فشل جلب العملاء: {e}")
            return []


    def get_archived_clients(self) -> List[schemas.Client]:
        """ (جديدة) جلب كل العملاء "المؤرشفين" فقط (بذكاء) """
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
                print(f"ERROR: فشل جلب العملاء المؤرشفين (Mongo): {e}.")

        self.sqlite_cursor.execute("SELECT * FROM clients WHERE status = ?", (archived_status,))
        rows = self.sqlite_cursor.fetchall()
        return [schemas.Client(**dict(row)) for row in rows]

    def get_client_by_id(self, client_id: str) -> Optional[schemas.Client]:
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
                    print(f"INFO: تم جلب العميل (MongoID: {client_id}) من الأونلاين.")
                    return client
            except Exception as e:
                print(f"WARNING: فشل البحث بالـ MongoID {client_id}: {e}. جاري البحث المحلي...")

        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM clients WHERE id = ? OR _mongo_id = ? OR name = ?",
                (client_id, client_id, client_id)
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                client = schemas.Client(**dict(row))
                print(f"INFO: تم جلب العميل (ID: {client_id}) من المحلي.")
                return client
        except Exception as e:
            print(f"ERROR: فشل جلب العميل (ID: {client_id}) من المحلي: {e}.")

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

    def archive_client_by_id(self, client_id: str) -> bool:
        """
        (جديدة) أرشفة عميل (Soft Delete) عن طريق تحديث حالته.
        """
        print(f"INFO: [Repo] جاري أرشفة العميل ID: {client_id}")

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
                print(f"ERROR: [Repo] فشل أرشفة العميل (Mongo): {e}")
                return False

        return True

    def update_journal_entry_by_doc_id(self, doc_id: str, new_lines: List[schemas.JournalEntryLine], new_description: str) -> bool:
        """
        (جديدة) تحديث قيد يومية موجود (للروبوت المحاسبي).
        """
        print(f"INFO: [Repo] جاري تحديث القيد المحاسبي المرتبط بـ {doc_id}...")

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
            print(f"ERROR: [Repo] فشل تحديث القيد (SQLite): {e}")
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
                print(f"ERROR: [Repo] فشل تحديث القيد (Mongo): {e}")

        return True

    def update_quotation(self, quote_number: str, quote_data: schemas.Quotation) -> Optional[schemas.Quotation]:
        """ (جديدة) تحديث بيانات عرض سعر موجود بالكامل. """
        print(f"INFO: [Repo] جاري تحديث عرض السعر {quote_number} في قاعدة البيانات...")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        items_json = json.dumps([item.model_dump() for item in quote_data.items])

        try:
            sql = """
                UPDATE quotations SET
                    client_id = ?, issue_date = ?, expiry_date = ?, items = ?,
                    subtotal = ?, discount_rate = ?, discount_amount = ?,
                    tax_rate = ?, tax_amount = ?, total_amount = ?,
                    notes = ?, status = ?, last_modified = ?, sync_status = 'modified_offline'
                WHERE quote_number = ?
            """
            params = (
                quote_data.client_id, quote_data.issue_date.isoformat(),
                quote_data.expiry_date.isoformat(), items_json,
                quote_data.subtotal, quote_data.discount_rate,
                quote_data.discount_amount, quote_data.tax_rate,
                quote_data.tax_amount, quote_data.total_amount,
                quote_data.notes, quote_data.status.value, now_iso,
                quote_number
            )
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
        except Exception as e:
            print(f"ERROR: [Repo] فشل تحديث عرض السعر (SQLite): {e}")
            return None

        if self.online:
            try:
                update_dict = quote_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                update_dict['status'] = quote_data.status.value
                update_dict['currency'] = quote_data.currency.value
                update_dict['last_modified'] = now_dt

                self.mongo_db.quotations.update_one(
                    {"quote_number": quote_number},
                    {"$set": update_dict}
                )
                self.sqlite_cursor.execute(
                    "UPDATE quotations SET sync_status = 'synced' WHERE quote_number = ?",
                    (quote_number,)
                )
                self.sqlite_conn.commit()
            except Exception as e:
                print(f"ERROR: [Repo] فشل تحديث عرض السعر (Mongo): {e}")

        return quote_data

    def get_client_by_name(self, name: str) -> Optional[schemas.Client]:
        """ (جديدة) جلب عميل واحد بالاسم (بذكاء) """
        if self.online:
            try:
                client_data = self.mongo_db.clients.find_one({"name": name})
                if client_data:
                    mongo_id = str(client_data.pop('_id'))
                    client_data.pop('_mongo_id', None)
                    client_data.pop('mongo_id', None)
                    client = schemas.Client(**client_data, _mongo_id=mongo_id)
                    print(f"INFO: تم جلب العميل (Name: {name}) من الأونلاين.")
                    return client
            except Exception as e:
                print(f"ERROR: فشل جلب العميل بالاسم (Mongo): {e}.")

        try:
            self.sqlite_cursor.execute("SELECT * FROM clients WHERE name = ?", (name,))
            row = self.sqlite_cursor.fetchone()
            if row:
                client = schemas.Client(**dict(row))
                print(f"INFO: تم جلب العميل (Name: {name}) من المحلي.")
                return client
        except Exception as e:
            print(f"ERROR: فشل جلب العميل بالاسم (SQLite): {e}.")

        return None

    # --- دوال التعامل مع الحسابات ---

    def create_account(self, account_data: schemas.Account) -> schemas.Account:
        """ إنشاء حساب جديد (بذكاء) """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        account_data.created_at = now_dt
        account_data.last_modified = now_dt
        account_data.sync_status = 'new_offline'

        # 1. الحفظ في SQLite (الأوفلاين أولاً)
        sql = """
            INSERT INTO accounts (sync_status, created_at, last_modified, name, code, type, parent_id, balance, currency, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        currency_value = account_data.currency.value if account_data.currency else 'EGP'
        params = (
            account_data.sync_status, now_iso, now_iso, account_data.name, account_data.code,
            account_data.type.value, account_data.parent_id, account_data.balance,
            currency_value, account_data.description
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        print(f"INFO: تم حفظ الحساب '{account_data.name}' محلياً (ID: {local_id}).")

        # 2. محاولة الحفظ في MongoDB (الأونلاين)
        if self.online:
            try:
                account_dict = account_data.model_dump(exclude={"_mongo_id"})
                account_dict['type'] = account_data.type.value

                result = self.mongo_db.accounts.insert_one(account_dict)
                mongo_id = str(result.inserted_id)

                account_data._mongo_id = mongo_id
                account_data.sync_status = 'synced'

                self.sqlite_cursor.execute(
                    "UPDATE accounts SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                    (mongo_id, 'synced', local_id)
                )
                self.sqlite_conn.commit()
                print(f"INFO: تم مزامنة الحساب '{account_data.name}' أونلاين.")

            except Exception as e:
                if "E11000 duplicate key" in str(e):
                    print(f"WARNING: الحساب بكود '{account_data.code}' موجود بالفعل أونلاين.")
                    existing = self.mongo_db.accounts.find_one({"code": account_data.code})
                    if existing:
                        mongo_id = str(existing['_id'])
                        self.sqlite_cursor.execute(
                            "UPDATE accounts SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                            (mongo_id, 'synced', local_id)
                        )
                        self.sqlite_conn.commit()
                else:
                    print(f"ERROR: فشل مزامنة الحساب الجديد '{account_data.name}': {e}")

        return account_data

    def get_account_by_code(self, code: str) -> Optional[schemas.Account]:
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
                    print(f"INFO: تم جلب الحساب (Code: {code}) من الأونلاين.")
                    return account
            except Exception as e:
                print(f"ERROR: فشل جلب الحساب (Code: {code}) من Mongo: {e}.")
        
        # الجلب من SQLite في حالة الأوفلاين أو عدم وجوده أونلاين
        try:
            self.sqlite_cursor.execute("SELECT * FROM accounts WHERE code = ?", (code,))
            row = self.sqlite_cursor.fetchone()
            if row:
                account = schemas.Account(**dict(row))
                print(f"INFO: تم جلب الحساب (Code: {code}) من المحلي.")
                return account
        except Exception as e:
            print(f"ERROR: فشل جلب الحساب (Code: {code}) من المحلي: {e}.")
            
        return None # لو الحساب مش موجود خالص

    def get_all_accounts(self) -> List[schemas.Account]:
        """ جلب كل الحسابات (بذكاء) - يفضل MongoDB لكن يستخدم SQLite كـ fallback """
        accounts_list = []
        
        # محاولة الجلب من MongoDB أولاً
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
                    print(f"INFO: تم جلب {len(accounts_list)} حساب من الأونلاين (MongoDB).")
                    return accounts_list
            except Exception as e:
                print(f"ERROR: فشل جلب الحسابات من Mongo: {e}")

        # إذا MongoDB فارغة أو فشلت، جلب من SQLite
        try:
            self.sqlite_cursor.execute("SELECT * FROM accounts WHERE sync_status != 'deleted'")
            rows = self.sqlite_cursor.fetchall()
            if rows:
                accounts_list = [schemas.Account(**dict(row)) for row in rows]
                print(f"INFO: تم جلب {len(accounts_list)} حساب من المحلي (SQLite).")
        except Exception as e:
            print(f"ERROR: فشل جلب الحسابات من SQLite: {e}")
        
        return accounts_list

    def get_account_by_id(self, account_id: str) -> Optional[schemas.Account]:
        """ (جديدة) جلب حساب واحد بالـ ID """
        try:
            account_id_num = int(account_id)
        except ValueError:
            account_id_num = 0

        if self.online:
            try:
                data = self.mongo_db.accounts.find_one(
                    {"$or": [{"_id": self._to_objectid(account_id)}, {"_mongo_id": account_id}, {"id": account_id_num}]}
                )
                if data:
                    mongo_id = str(data.pop('_id'))
                    data.pop('_mongo_id', None)
                    data.pop('mongo_id', None)
                    return schemas.Account(**data, _mongo_id=mongo_id)
            except Exception as e:
                print(f"ERROR: [Repo] فشل جلب الحساب {account_id} (Mongo): {e}")

        try:
            self.sqlite_cursor.execute("SELECT * FROM accounts WHERE id = ? OR _mongo_id = ?", (account_id_num, account_id))
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Account(**dict(row))
        except Exception as e:
            print(f"ERROR: [Repo] فشل جلب الحساب {account_id} (SQLite): {e}")

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
                    
                    print(f"INFO: [Repository] تم إنشاء مستخدم: {user.username} (MongoDB + SQLite)")
                    return mongo_id
                except Exception as e:
                    print(f"WARNING: [Repository] فشل حفظ المستخدم في MongoDB: {e}")
            
            print(f"INFO: [Repository] تم إنشاء مستخدم: {user.username} (SQLite فقط)")
            return local_id
            
        except Exception as e:
            print(f"ERROR: [Repository] فشل إنشاء المستخدم: {e}")
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
                    print(f"WARNING: [Repository] فشل جلب المستخدم من MongoDB: {e}")
            
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
            print(f"ERROR: [Repository] فشل جلب المستخدم: {e}")
            return None
    
    def update_user(self, user_id: str, update_data: dict) -> bool:
        """تحديث بيانات مستخدم"""
        try:
            import json
            from datetime import datetime
            now_dt = datetime.now()
            now_iso = now_dt.isoformat()
            
            # تحديث في SQLite
            update_data['last_modified'] = now_iso
            update_data['sync_status'] = 'modified_offline'
            
            # تحويل القواميس إلى JSON strings للـ SQLite
            sqlite_data = update_data.copy()
            for key, value in sqlite_data.items():
                if isinstance(value, dict):
                    sqlite_data[key] = json.dumps(value, ensure_ascii=False)
            
            set_clause = ", ".join([f"{key} = ?" for key in sqlite_data.keys()])
            values = list(sqlite_data.values())
            values.append(user_id)  # للـ WHERE clause
            
            sql = f"UPDATE users SET {set_clause} WHERE id = ? OR _mongo_id = ?"
            values.append(user_id)  # للـ WHERE clause الثاني
            
            self.sqlite_cursor.execute(sql, values)
            self.sqlite_conn.commit()
            
            # تحديث في MongoDB
            if self.online:
                try:
                    mongo_update = update_data.copy()
                    mongo_update['last_modified'] = now_dt
                    
                    self.mongo_db.users.update_one(
                        {"$or": [{"_id": self._to_objectid(user_id)}, {"_mongo_id": user_id}]},
                        {"$set": mongo_update}
                    )
                    
                    # تحديث حالة المزامنة
                    self.sqlite_cursor.execute(
                        "UPDATE users SET sync_status = 'synced' WHERE id = ? OR _mongo_id = ?",
                        (user_id, user_id)
                    )
                    self.sqlite_conn.commit()
                    
                except Exception as e:
                    print(f"WARNING: [Repository] فشل تحديث المستخدم في MongoDB: {e}")
            
            return True
        except Exception as e:
            print(f"ERROR: [Repository] فشل تحديث المستخدم: {e}")
            return False
    
    def get_all_users(self):
        """جلب جميع المستخدمين"""
        try:
            from core.auth_models import User, UserRole
            users = []
            
            # جلب من MongoDB أولاً
            if self.online:
                try:
                    users_data = list(self.mongo_db.users.find())
                    for user_data in users_data:
                        # تحويل _id إلى string
                        user_data['id'] = str(user_data.get('_id', ''))
                        user_data['_mongo_id'] = str(user_data.pop('_id'))
                        
                        # تحويل datetime إلى string
                        if 'created_at' in user_data and hasattr(user_data['created_at'], 'isoformat'):
                            user_data['created_at'] = user_data['created_at'].isoformat()
                        if 'last_modified' in user_data and hasattr(user_data['last_modified'], 'isoformat'):
                            user_data['last_modified'] = user_data['last_modified'].isoformat()
                        if 'last_login' in user_data and hasattr(user_data['last_login'], 'isoformat'):
                            user_data['last_login'] = user_data['last_login'].isoformat()
                        
                        # تحويل role إلى enum
                        user_data['role'] = UserRole(user_data['role'])
                        users.append(User(**user_data))
                    
                    if users:
                        return users
                except Exception as e:
                    print(f"WARNING: [Repository] فشل جلب المستخدمين من MongoDB: {e}")
            
            # جلب من SQLite
            self.sqlite_cursor.execute("SELECT * FROM users")
            rows = self.sqlite_cursor.fetchall()
            for row in rows:
                user_data = dict(row)
                user_data['id'] = str(user_data.get('id', ''))
                user_data['role'] = UserRole(user_data['role'])
                user_data['is_active'] = bool(user_data['is_active'])
                
                # تحويل custom_permissions من JSON string إلى dict
                if user_data.get('custom_permissions'):
                    try:
                        import json
                        user_data['custom_permissions'] = json.loads(user_data['custom_permissions'])
                    except (json.JSONDecodeError, TypeError):
                        user_data['custom_permissions'] = None
                
                users.append(User(**user_data))
            
            return users
        except Exception as e:
            print(f"ERROR: [Repository] فشل جلب المستخدمين: {e}")
            return []

    def update_account(self, account_id: str, account_data: schemas.Account) -> Optional[schemas.Account]:
        """ (جديدة) تحديث بيانات حساب موجود. """
        print(f"INFO: [Repo] جاري تحديث الحساب ID: {account_id}")
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        account_data.last_modified = now_dt
        account_data.sync_status = 'modified_offline'

        try:
            account_id_num = int(account_id)
        except ValueError:
            account_id_num = 0

        currency_value = account_data.currency.value if account_data.currency else 'EGP'
        sql = """
            UPDATE accounts SET
                name = ?, code = ?, type = ?, parent_id = ?, status = ?,
                balance = ?, currency = ?, description = ?,
                last_modified = ?, sync_status = 'modified_offline'
            WHERE id = ? OR _mongo_id = ?
        """
        params = (
            account_data.name,
            account_data.code,
            account_data.type.value,
            account_data.parent_id,
            account_data.status.value,
            account_data.balance,
            currency_value,
            account_data.description,
            now_iso,
            account_id_num,
            account_id,
        )
        try:
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
        except Exception as e:
            print(f"ERROR: [Repo] فشل تحديث الحساب (SQLite): {e}")

        if self.online:
            try:
                update_dict = account_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                update_dict['type'] = account_data.type.value
                update_dict['status'] = account_data.status.value
                update_dict['last_modified'] = now_dt

                self.mongo_db.accounts.update_one(
                    {"$or": [
                        {"_id": self._to_objectid(account_id)},
                        {"_mongo_id": account_id},
                        {"id": account_id_num},
                    ]},
                    {"$set": update_dict},
                )
                self.sqlite_cursor.execute(
                    "UPDATE accounts SET sync_status = 'synced' WHERE id = ? OR _mongo_id = ?",
                    (account_id_num, account_id),
                )
                self.sqlite_conn.commit()
            except Exception as e:
                print(f"ERROR: [Repo] فشل تحديث الحساب (Mongo): {e}")

        return account_data

    def archive_account_by_id(self, account_id: str) -> bool:
        """ (جديدة) أرشفة حساب (Soft Delete). """
        print(f"INFO: [Repo] جاري أرشفة الحساب ID: {account_id}")
        try:
            account = self.get_account_by_id(account_id)
            if not account:
                return False

            account.status = schemas.AccountStatus.ARCHIVED
            self.update_account(account_id, account)
            return True
        except Exception as e:
            print(f"ERROR: [Repo] فشل أرشفة الحساب: {e}")
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
        print(f"INFO: تم حفظ الفاتورة '{invoice_data.invoice_number}' محلياً (ID: {local_id}).")

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
                print(f"INFO: تم مزامنة الفاتورة '{invoice_data.invoice_number}' أونلاين.")
                
            except Exception as e:
                print(f"ERROR: فشل مزامنة الفاتورة الجديدة '{invoice_data.invoice_number}': {e}")
        
        return invoice_data

    def get_all_invoices(self) -> List[schemas.Invoice]:
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
                print("INFO: تم جلب الفواتير من الأونلاين (MongoDB).")
                return invoices_list
            except Exception as e:
                print(f"ERROR: فشل جلب الفواتير من Mongo: {e}. سيتم الجلب من المحلي.")
        
        # الجلب من SQLite في حالة الأوفلاين
        self.sqlite_cursor.execute("SELECT * FROM invoices")
        rows = self.sqlite_cursor.fetchall()
        invoices_list = []
        for row in rows:
            row_dict = dict(row)
            # تحويل الـ JSON string بتاع 'items' نرجعه لـ list
            row_dict['items'] = json.loads(row_dict['items'])
            invoices_list.append(schemas.Invoice(**row_dict))
            
        print("INFO: تم جلب الفواتير من المحلي (SQLite).")
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
        print(f"INFO: تم حفظ قيد اليومية '{entry_data.description[:20]}...' محلياً (ID: {local_id}).")

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
                print(f"INFO: تم مزامنة قيد اليومية '{entry_data.description[:20]}...' أونلاين.")
                
            except Exception as e:
                print(f"ERROR: فشل مزامنة قيد اليومية الجديد: {e}")
        
        return entry_data

    def get_all_journal_entries(self) -> List[schemas.JournalEntry]:
        """ جلب كل قيود اليومية (بذكاء) """
        if self.online:
            try:
                entries_data = list(self.mongo_db.journal_entries.find().sort("date", -1))
                entries_list = []
                for entry in entries_data:
                    mongo_id = str(entry.pop('_id'))
                    entry.pop('_mongo_id', None)
                    entry.pop('mongo_id', None)
                    entries_list.append(schemas.JournalEntry(**entry, _mongo_id=mongo_id))
                print("INFO: تم جلب قيود اليومية من الأونلاين (MongoDB).")
                return entries_list
            except Exception as e:
                print(f"ERROR: فشل جلب قيود اليومية من Mongo: {e}. سيتم الجلب من المحلي.")

        self.sqlite_cursor.execute("SELECT * FROM journal_entries ORDER BY date DESC")
        rows = self.sqlite_cursor.fetchall()
        entries_list = []
        for row in rows:
            row_dict = dict(row)
            row_dict['lines'] = json.loads(row_dict['lines'])
            entries_list.append(schemas.JournalEntry(**row_dict))

        print("INFO: تم جلب قيود اليومية من المحلي (SQLite).")
        return entries_list

    def get_journal_entry_by_doc_id(self, doc_id: str) -> Optional[schemas.JournalEntry]:
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
                print(f"ERROR: [Repo] فشل جلب القيد (Mongo): {e}")

        try:
            self.sqlite_cursor.execute(
                "SELECT * FROM journal_entries WHERE related_document_id = ?",
                (doc_id,)
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                row_dict = dict(row)
                row_dict['lines'] = json.loads(row_dict['lines'])
                return schemas.JournalEntry(**row_dict)
        except Exception as e:
            print(f"ERROR: [Repo] فشل جلب القيد (SQLite): {e}")

        return None

    # --- دوال التعامل مع الدفعات ---

    def create_payment(self, payment_data: schemas.Payment) -> schemas.Payment:
        """ (معدلة) إنشاء دفعة جديدة (مربوطة بمشروع) """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
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
        print(f"INFO: تم حفظ الدفعة (للمشروع {payment_data.project_id}) محلياً (ID: {local_id}).")

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
                print(f"INFO: تم مزامنة الدفعة (Mongo ID: {mongo_id}) أونلاين.")
                
            except Exception as e:
                print(f"ERROR: فشل مزامنة الدفعة الجديدة: {e}")
        
        return payment_data

    def get_payments_for_project(self, project_name: str) -> List[schemas.Payment]:
        """ (جديدة) جلب كل الدفعات المرتبطة بمشروع (أونلاين أولاً) """
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
                print(f"ERROR: [Repo] فشل جلب دفعات المشروع (Mongo): {e}")

        try:
            self.sqlite_cursor.execute("SELECT * FROM payments WHERE project_id = ?", (project_name,))
            rows = self.sqlite_cursor.fetchall()
            return [schemas.Payment(**dict(row)) for row in rows]
        except Exception as e:
            print(f"ERROR: [Repo] فشل جلب دفعات المشروع (SQLite): {e}")
            return []

    def get_all_payments(self) -> List[schemas.Payment]:
        """ جلب كل الدفعات """
        if self.online:
            try:
                data = list(self.mongo_db.payments.find())
                payments = []
                for d in data:
                    mongo_id = str(d.pop('_id'))
                    # حذف _mongo_id و mongo_id من البيانات لتجنب التكرار
                    d.pop('_mongo_id', None)
                    d.pop('mongo_id', None)
                    payments.append(schemas.Payment(**d, _mongo_id=mongo_id))
                print(f"INFO: [Repo] تم جلب {len(payments)} دفعة من MongoDB.")
                return payments
            except Exception as e:
                print(f"ERROR: [Repo] فشل جلب الدفعات (Mongo): {e}")

        try:
            self.sqlite_cursor.execute("SELECT * FROM payments ORDER BY date DESC")
            rows = self.sqlite_cursor.fetchall()
            payments = [schemas.Payment(**dict(row)) for row in rows]
            print(f"INFO: [Repo] تم جلب {len(payments)} دفعة من SQLite.")
            return payments
        except Exception as e:
            print(f"ERROR: [Repo] فشل جلب الدفعات (SQLite): {e}")
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
            print(f"INFO: [Repo] تم تعديل الدفعة محلياً (ID: {payment_id}).")
            
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
                        print(f"INFO: [Repo] تم مزامنة تعديل الدفعة أونلاين.")
                except Exception as e:
                    print(f"ERROR: [Repo] فشل مزامنة تعديل الدفعة: {e}")
            
            return True
        except Exception as e:
            print(f"ERROR: [Repo] فشل تعديل الدفعة: {e}")
            return False

    def get_payment_by_id(self, payment_id) -> Optional[schemas.Payment]:
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
            print(f"ERROR: [Repo] فشل جلب الدفعة: {e}")
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
            print(f"INFO: [Repo] تم حذف الدفعة محلياً (ID: {payment_id}).")
            
            # حذف من MongoDB
            if self.online and mongo_id:
                try:
                    from bson import ObjectId
                    self.mongo_db.payments.delete_one({'_id': ObjectId(mongo_id)})
                    print(f"INFO: [Repo] تم حذف الدفعة من MongoDB.")
                except Exception as e:
                    print(f"ERROR: [Repo] فشل حذف الدفعة من MongoDB: {e}")
            
            return True
        except Exception as e:
            print(f"ERROR: [Repo] فشل حذف الدفعة: {e}")
            return False

    def update_invoice_after_payment(self, invoice_number: str, new_payment_amount: float) -> Optional[schemas.Invoice]:
        """
        (جديدة) تحديث المبلغ المدفوع وحالة الفاتورة بعد استلام دفعة.
        """
        print(f"INFO: [Repo] جاري تحديث الفاتورة {invoice_number} بدفعة {new_payment_amount}")

        invoice = self.get_invoice_by_number(invoice_number)
        if not invoice:
            print(f"ERROR: [Repo] لم يتم العثور على الفاتورة {invoice_number} لتحديثها.")
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
            print(f"ERROR: [Repo] فشل تحديث الفاتورة (SQLite): {e}")

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
                print(f"ERROR: [Repo] فشل تحديث الفاتورة (Mongo): {e}")

        invoice.amount_paid = new_amount_paid
        invoice.status = new_status
        invoice.last_modified = now_dt
        invoice.sync_status = 'synced' if self.online else 'modified_offline'
        return invoice

    def update_invoice(self, invoice_number: str, invoice_data: schemas.Invoice) -> Optional[schemas.Invoice]:
        """
        (جديدة) تحديث بيانات فاتورة موجودة بالكامل.
        """
        print(f"INFO: [Repo] جاري تحديث الفاتورة {invoice_number} في قاعدة البيانات...")

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
            print(f"ERROR: [Repo] فشل تحديث الفاتورة (SQLite): {e}")
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
                print(f"INFO: [Repo] تم مزامنة تحديث الفاتورة {invoice_number} أونلاين.")

            except Exception as e:
                print(f"ERROR: [Repo] فشل تحديث الفاتورة (Mongo): {e}")

        return invoice_data

    def get_invoice_by_number(self, invoice_number: str) -> Optional[schemas.Invoice]:
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
                print(f"ERROR: [Repo] فشل جلب الفاتورة {invoice_number} (Mongo): {e}")

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
            print(f"ERROR: [Repo] فشل جلب الفاتورة {invoice_number} (SQLite): {e}")

        return None

    def void_invoice_by_number(self, invoice_number: str) -> Optional[schemas.Invoice]:
        """
        (جديدة) إلغاء فاتورة: تحديث الحالة إلى "ملغاة".
        """
        print(f"INFO: [Repo] جاري إلغاء الفاتورة {invoice_number}")

        invoice = self.get_invoice_by_number(invoice_number)
        if not invoice:
            print(f"ERROR: [Repo] لم يتم العثور على الفاتورة {invoice_number} لإلغائها.")
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
            print(f"ERROR: [Repo] فشل إلغاء الفاتورة (SQLite): {e}")

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
                print(f"ERROR: [Repo] فشل إلغاء الفاتورة (Mongo): {e}")

        invoice.status = new_status
        invoice.last_modified = now_dt
        invoice.sync_status = 'synced' if self.online else 'modified_offline'
        return invoice

    # --- دوال التعامل مع الخدمات ---

    def create_service(self, service_data: schemas.Service) -> schemas.Service:
        """ (معدلة) إنشاء خدمة جديدة (بإصلاح حفظ الحالة في مونجو) """
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
        print(f"INFO: تم حفظ الخدمة '{service_data.name}' محلياً (ID: {local_id}).")

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
                print(f"INFO: تم مزامنة الخدمة '{service_data.name}' أونلاين.")

            except Exception as e:
                if "E11000 duplicate key" in str(e):
                    print(f"WARNING: الخدمة '{service_data.name}' موجودة بالفعل أونلاين.")
                else:
                    print(f"ERROR: فشل مزامنة الخدمة الجديدة '{service_data.name}': {e}")

        return service_data

    def get_all_services(self) -> List[schemas.Service]:
        """ (معدلة) جلب كل الخدمات "النشطة" فقط (بذكاء) """
        active_status = schemas.ServiceStatus.ACTIVE.value
        if self.online:
            try:
                services_data = list(self.mongo_db.services.find({"status": active_status}))
                services_list = []
                for s in services_data:
                    mongo_id = str(s.pop('_id'))
                    s.pop('_mongo_id', None)
                    s.pop('mongo_id', None)
                    services_list.append(schemas.Service(**s, _mongo_id=mongo_id))
                print(f"INFO: تم جلب {len(services_list)} خدمة 'نشطة' من الأونلاين.")
                return services_list
            except Exception as e:
                print(f"ERROR: فشل جلب الخدمات من Mongo: {e}. سيتم الجلب من المحلي.")

        self.sqlite_cursor.execute("SELECT * FROM services WHERE status = ?", (active_status,))
        rows = self.sqlite_cursor.fetchall()
        services_list = [schemas.Service(**dict(row)) for row in rows]
        print(f"INFO: تم جلب {len(services_list)} خدمة 'نشطة' من المحلي.")
        return services_list

    def get_service_by_id(self, service_id: str) -> Optional[schemas.Service]:
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
                print(f"ERROR: [Repo] فشل جلب الخدمة {service_id} (Mongo): {e}")

        try:
            self.sqlite_cursor.execute("SELECT * FROM services WHERE id = ? OR _mongo_id = ?", (service_id_num, service_id))
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Service(**dict(row))
        except Exception as e:
            print(f"ERROR: [Repo] فشل جلب الخدمة {service_id} (SQLite): {e}")

        return None

    def update_service(self, service_id: str, service_data: schemas.Service) -> Optional[schemas.Service]:
        """
        (جديدة) تحديث بيانات خدمة موجودة.
        """
        print(f"INFO: [Repo] جاري تحديث الخدمة ID: {service_id}")
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
            print(f"ERROR: [Repo] فشل تحديث الخدمة (SQLite): {e}")
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
                print(f"ERROR: [Repo] فشل تحديث الخدمة (Mongo): {e}")

        return service_data

    def archive_service_by_id(self, service_id: str) -> bool:
        """
        (جديدة) أرشفة خدمة (Soft Delete).
        """
        print(f"INFO: [Repo] جاري أرشفة الخدمة ID: {service_id}")
        try:
            service = self.get_service_by_id(service_id)
            if not service:
                return False

            service.status = schemas.ServiceStatus.ARCHIVED
            self.update_service(service_id, service)
            return True
        except Exception as e:
            print(f"ERROR: [Repo] فشل أرشفة الخدمة: {e}")
            return False

    def get_archived_services(self) -> List[schemas.Service]:
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
                print(f"ERROR: فشل جلب الخدمات المؤرشفة (Mongo): {e}.")

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
        print(f"INFO: تم حفظ المصروف '{expense_data.category}' محلياً (ID: {local_id}).")

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
                print(f"INFO: تم مزامنة المصروف '{expense_data.category}' أونلاين.")

            except Exception as e:
                print(f"ERROR: فشل مزامنة المصروف الجديد '{expense_data.category}': {e}")

        return expense_data

    def get_all_expenses(self) -> List[schemas.Expense]:
        """ جلب كل المصروفات (بذكاء) """
        if self.online:
            try:
                expenses_data = list(self.mongo_db.expenses.find())
                expenses_list = []
                for exp in expenses_data:
                    mongo_id = str(exp.pop('_id'))
                    exp.pop('_mongo_id', None)
                    exp.pop('mongo_id', None)
                    expenses_list.append(schemas.Expense(**exp, _mongo_id=mongo_id))
                print("INFO: تم جلب المصروفات من الأونلاين (MongoDB).")
                return expenses_list
            except Exception as e:
                print(f"ERROR: فشل جلب المصروفات من Mongo: {e}. سيتم الجلب من المحلي.")

        self.sqlite_cursor.execute("SELECT * FROM expenses")
        rows = self.sqlite_cursor.fetchall()
        expenses_list = [schemas.Expense(**dict(row)) for row in rows]
        print("INFO: تم جلب المصروفات من المحلي (SQLite).")
        return expenses_list

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
            print(f"INFO: تم تعديل المصروف محلياً (ID: {expense_id}).")
            
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
                        print(f"INFO: تم مزامنة تعديل المصروف أونلاين.")
                except Exception as e:
                    print(f"ERROR: فشل مزامنة تعديل المصروف: {e}")
            
            return True
        except Exception as e:
            print(f"ERROR: فشل تعديل المصروف: {e}")
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
            print(f"INFO: تم حذف المصروف محلياً (ID: {expense_id}).")
            
            # حذف من MongoDB
            if self.online and mongo_id:
                try:
                    from bson import ObjectId
                    self.mongo_db.expenses.delete_one({'_id': ObjectId(mongo_id)})
                    print(f"INFO: تم حذف المصروف من الأونلاين.")
                except Exception as e:
                    print(f"ERROR: فشل حذف المصروف من Mongo: {e}")
            
            return True
        except Exception as e:
            print(f"ERROR: فشل حذف المصروف: {e}")
            return False

    # --- دوال التعامل مع عروض الأسعار ---

    def create_quotation(self, quote_data: schemas.Quotation) -> schemas.Quotation:
        """ إنشاء عرض سعر جديد (بذكاء) """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        quote_data.created_at = now_dt
        quote_data.last_modified = now_dt
        quote_data.sync_status = 'new_offline'

        items_json = json.dumps([item.model_dump() for item in quote_data.items])

        sql = """
            INSERT INTO quotations (
                sync_status, created_at, last_modified, quote_number, client_id,
                project_id, issue_date, expiry_date, items, subtotal,
                discount_rate, discount_amount, tax_rate, tax_amount,
                total_amount, status, currency, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            quote_data.sync_status, now_iso, now_iso, quote_data.quote_number,
            quote_data.client_id, quote_data.project_id,
            quote_data.issue_date.isoformat(), quote_data.expiry_date.isoformat(),
            items_json, quote_data.subtotal, quote_data.discount_rate,
            quote_data.discount_amount, quote_data.tax_rate, quote_data.tax_amount,
            quote_data.total_amount, quote_data.status.value,
            quote_data.currency.value, quote_data.notes
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        quote_data.id = local_id
        print(f"INFO: تم حفظ عرض السعر '{quote_data.quote_number}' محلياً (ID: {local_id}).")

        if self.online:
            try:
                quote_dict = quote_data.model_dump(exclude={"_mongo_id", "id"})
                quote_dict['status'] = quote_data.status.value
                quote_dict['currency'] = quote_data.currency.value
                quote_dict['issue_date'] = quote_data.issue_date
                quote_dict['expiry_date'] = quote_data.expiry_date

                result = self.mongo_db.quotations.insert_one(quote_dict)
                mongo_id = str(result.inserted_id)

                quote_data._mongo_id = mongo_id
                quote_data.sync_status = 'synced'

                self.sqlite_cursor.execute(
                    "UPDATE quotations SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                    (mongo_id, 'synced', local_id)
                )
                self.sqlite_conn.commit()
                print(f"INFO: تم مزامنة عرض السعر '{quote_data.quote_number}' أونلاين.")

            except Exception as e:
                print(f"ERROR: فشل مزامنة عرض السعر الجديد: {e}")

        return quote_data

    def get_all_quotations(self) -> List[schemas.Quotation]:
        """ جلب كل عروض الأسعار (بذكاء) """
        if self.online:
            try:
                data = list(self.mongo_db.quotations.find().sort("issue_date", -1))
                data_list = []
                for d in data:
                    mongo_id = str(d.pop('_id'))
                    # حذف _mongo_id و mongo_id من البيانات لتجنب التكرار
                    d.pop('_mongo_id', None)
                    d.pop('mongo_id', None)
                    data_list.append(schemas.Quotation(**d, _mongo_id=mongo_id))
                print("INFO: تم جلب عروض الأسعار من الأونلاين (MongoDB).")
                return data_list
            except Exception as e:
                print(f"ERROR: فشل جلب عروض الأسعار من Mongo: {e}. سيتم الجلب من المحلي.")

        self.sqlite_cursor.execute("SELECT * FROM quotations ORDER BY issue_date DESC")
        rows = self.sqlite_cursor.fetchall()
        data_list = []
        for row in rows:
            row_dict = dict(row)
            row_dict['items'] = json.loads(row_dict['items'])
            data_list.append(schemas.Quotation(**row_dict))

        print("INFO: تم جلب عروض الأسعار من المحلي (SQLite).")
        return data_list

    def get_quotation_by_number(self, quote_number: str) -> Optional[schemas.Quotation]:
        """ (جديدة) جلب عرض سعر واحد برقمه """
        if self.online:
            try:
                data = self.mongo_db.quotations.find_one({"quote_number": quote_number})
                if data:
                    mongo_id = str(data.pop('_id'))
                    data.pop('_mongo_id', None)
                    data.pop('mongo_id', None)
                    return schemas.Quotation(**data, _mongo_id=mongo_id)
            except Exception as e:
                print(f"ERROR: [Repo] فشل جلب عرض السعر {quote_number} (Mongo): {e}")

        try:
            self.sqlite_cursor.execute("SELECT * FROM quotations WHERE quote_number = ?", (quote_number,))
            row = self.sqlite_cursor.fetchone()
            if row:
                row_dict = dict(row)
                row_dict['items'] = json.loads(row_dict['items'])
                return schemas.Quotation(**row_dict)
        except Exception as e:
            print(f"ERROR: [Repo] فشل جلب عرض السعر {quote_number} (SQLite): {e}")

        return None

    def update_quotation_status(self, quote_number: str, new_status: schemas.QuotationStatus) -> bool:
        """ (جديدة) تحديث حالة عرض السعر (مثلاً: إلى "مقبول"). """
        print(f"INFO: [Repo] جاري تحديث حالة عرض السعر {quote_number} إلى {new_status.value}")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            self.sqlite_cursor.execute(
                "UPDATE quotations SET status = ?, last_modified = ?, sync_status = 'modified_offline' WHERE quote_number = ?",
                (new_status.value, now_iso, quote_number)
            )
            self.sqlite_conn.commit()
        except Exception as e:
            print(f"ERROR: [Repo] فشل تحديث حالة عرض السعر (SQLite): {e}")
            return False

        if self.online:
            try:
                self.mongo_db.quotations.update_one(
                    {"quote_number": quote_number},
                    {"$set": {"status": new_status.value, "last_modified": now_dt}}
                )
                self.sqlite_cursor.execute(
                    "UPDATE quotations SET sync_status = 'synced' WHERE quote_number = ?",
                    (quote_number,)
                )
                self.sqlite_conn.commit()
            except Exception as e:
                print(f"ERROR: [Repo] فشل تحديث حالة عرض السعر (Mongo): {e}")

        return True

    # --- دوال التعامل مع المشاريع ---

    def create_project(self, project_data: schemas.Project) -> schemas.Project:
        """ (معدلة) إنشاء مشروع جديد (بالحقول المالية) """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        project_data.created_at = now_dt
        project_data.last_modified = now_dt
        project_data.sync_status = 'new_offline'

        items_json = json.dumps([item.model_dump() for item in project_data.items])

        sql = """
            INSERT INTO projects (
                sync_status, created_at, last_modified, name, client_id,
                status, description, start_date, end_date,
                items, subtotal, discount_rate, discount_amount, tax_rate,
                tax_amount, total_amount, currency, project_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            project_data.sync_status, now_iso, now_iso,
            project_data.name, project_data.client_id,
            project_data.status.value, project_data.description,
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
        print(f"INFO: تم حفظ المشروع '{project_data.name}' محلياً (ID: {local_id}).")

        if self.online:
            try:
                project_dict = project_data.model_dump(exclude={"_mongo_id", "id"})
                project_dict['status'] = project_data.status.value
                project_dict['start_date'] = project_data.start_date
                project_dict['end_date'] = project_data.end_date
                project_dict['currency'] = project_data.currency.value

                result = self.mongo_db.projects.insert_one(project_dict)
                mongo_id = str(result.inserted_id)
                
                project_data._mongo_id = mongo_id
                project_data.sync_status = 'synced'
                
                self.sqlite_cursor.execute(
                    "UPDATE projects SET _mongo_id = ?, sync_status = ? WHERE id = ?",
                    (mongo_id, 'synced', local_id)
                )
                self.sqlite_conn.commit()
                print(f"INFO: تم مزامنة المشروع '{project_data.name}' أونلاين.")
                
            except Exception as e:
                if "E11000 duplicate key" in str(e):
                    print(f"WARNING: المشروع باسم '{project_data.name}' موجود بالفعل أونلاين.")
                else:
                    print(f"ERROR: فشل مزامنة المشروع الجديد: {e}")
        
        return project_data

    def get_all_projects(
        self,
        status: Optional[schemas.ProjectStatus] = None,
        exclude_status: Optional[schemas.ProjectStatus] = None,
    ) -> List[schemas.Project]:
        """
        (معدلة) جلب كل المشاريع (مع فلترة اختيارية بالحالة أو استثناء حالة)
        """
        query_filter: Dict[str, Any] = {}
        sql_query = "SELECT * FROM projects"
        sql_params: List[Any] = []

        if status:
            query_filter = {"status": status.value}
            sql_query += " WHERE status = ?"
            sql_params.append(status.value)
        elif exclude_status:
            query_filter = {"status": {"$ne": exclude_status.value}}
            sql_query += " WHERE status != ?"
            sql_params.append(exclude_status.value)

        sql_query += " ORDER BY created_at DESC"

        if self.online:
            try:
                data = list(self.mongo_db.projects.find(query_filter).sort("created_at", -1))
                data_list = []
                for d in data:
                    try:
                        mongo_id = str(d.pop('_id'))
                        # تأكد من وجود الحقول المطلوبة مع قيم افتراضية
                        if 'client_id' not in d or not d['client_id']:
                            d['client_id'] = 'unknown'
                        if 'name' not in d or not d['name']:
                            continue  # تخطي المشاريع بدون اسم
                        # تحويل items إذا كان string أو None
                        if 'items' not in d or d['items'] is None:
                            d['items'] = []
                        elif isinstance(d['items'], str):
                            try:
                                d['items'] = json.loads(d['items'])
                            except:
                                d['items'] = []
                        # إضافة currency افتراضي إذا غير موجود
                        if 'currency' not in d or d['currency'] is None:
                            d['currency'] = 'EGP'
                        # إضافة status افتراضي
                        if 'status' not in d or d['status'] is None:
                            d['status'] = 'نشط'
                        # حذف _mongo_id من البيانات إذا كان موجوداً لتجنب التكرار
                        d.pop('_mongo_id', None)
                        d.pop('mongo_id', None)
                        data_list.append(schemas.Project(**d, _mongo_id=mongo_id))
                    except Exception as item_err:
                        print(f"WARNING: تخطي مشروع بسبب خطأ: {item_err}")
                        continue
                print(f"INFO: تم جلب {len(data_list)} مشروع من الأونلاين.")
                return data_list
            except Exception as e:
                print(f"ERROR: فشل جلب المشاريع من Mongo: {e}. سيتم الجلب من المحلي.")

        self.sqlite_cursor.execute(sql_query, sql_params)
        rows = self.sqlite_cursor.fetchall()
        data_list: List[schemas.Project] = []
        for row in rows:
            row_dict = dict(row)
            items_value = row_dict.get("items")
            if isinstance(items_value, str):
                try:
                    row_dict["items"] = json.loads(items_value)
                except json.JSONDecodeError:
                    row_dict["items"] = []
            data_list.append(schemas.Project(**row_dict))
        print(f"INFO: تم جلب {len(data_list)} مشروع من المحلي.")
        return data_list

    def get_project_by_number(self, project_name: str) -> Optional[schemas.Project]:
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
                print(f"ERROR: [Repo] فشل جلب المشروع {project_name} (Mongo): {e}")

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
                return schemas.Project(**row_dict)
        except Exception as e:
            print(f"ERROR: [Repo] فشل جلب المشروع {project_name} (SQLite): {e}")

        return None

    def update_project(self, project_name: str, project_data: schemas.Project) -> Optional[schemas.Project]:
        """
        (جديدة) تحديث بيانات مشروع موجود بالكامل.
        """
        print(f"INFO: [Repo] جاري تحديث المشروع {project_name} في قاعدة البيانات...")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        items_json = json.dumps([item.model_dump() for item in project_data.items])

        # --- 1. تحديث SQLite ---
        try:
            sql = """
                UPDATE projects SET
                    client_id = ?, status = ?, description = ?, start_date = ?, end_date = ?,
                    items = ?, subtotal = ?, discount_rate = ?, discount_amount = ?, tax_rate = ?,
                    tax_amount = ?, total_amount = ?, currency = ?, project_notes = ?,
                    last_modified = ?, sync_status = 'modified_offline'
                WHERE name = ?
            """
            params = (
                project_data.client_id, project_data.status.value,
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
            print(f"ERROR: [Repo] فشل تحديث المشروع (SQLite): {e}")
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
                print(f"ERROR: [Repo] فشل تحديث المشروع (Mongo): {e}")

        return project_data

    def get_project_revenue(self, project_name: str) -> float:
        """ (معدلة بالطريقة البسيطة) تحسب إجمالي إيرادات مشروع """
        print(f"INFO: [Repo] جاري حساب إيرادات مشروع: {project_name}")
        total_revenue = 0.0
        try:
            invoices = self.get_invoices_for_project(project_name)
            for inv in invoices:
                total_revenue += inv.total_amount
            print(f"INFO: [Repo] إيرادات المشروع (محسوبة): {total_revenue}")
        except Exception as e:
            print(f"ERROR: [Repo] فشل حساب إيرادات المشروع: {e}")
        return total_revenue

    def get_project_expenses(self, project_name: str) -> float:
        """ (معدلة بالطريقة البسيطة) تحسب إجمالي مصروفات مشروع """
        print(f"INFO: [Repo] جاري حساب مصروفات مشروع: {project_name}")
        total_expenses = 0.0
        try:
            expenses = self.get_expenses_for_project(project_name)
            for exp in expenses:
                total_expenses += exp.amount
            print(f"INFO: [Repo] مصروفات المشروع (محسوبة): {total_expenses}")
        except Exception as e:
            print(f"ERROR: [Repo] فشل حساب مصروفات المشروع: {e}")
        return total_expenses

    def get_invoices_for_project(self, project_name: str) -> List[schemas.Invoice]:
        """ (معدلة) جلب كل الفواتير المرتبطة بمشروع (أونلاين أولاً) """
        print(f"INFO: [Repo] جلب فواتير مشروع: {project_name}")
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
                print(f"ERROR: [Repo] فشل جلب فواتير المشروع (Mongo): {e}")

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
            print(f"ERROR: [Repo] فشل جلب فواتير المشروع (SQLite): {e}")
            return []

    def get_expenses_for_project(self, project_name: str) -> List[schemas.Expense]:
        """ (معدلة) جلب كل المصروفات المرتبطة بمشروع (أونلاين أولاً) """
        print(f"INFO: [Repo] جلب مصروفات مشروع: {project_name}")
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
                print(f"ERROR: [Repo] فشل جلب مصروفات المشروع (Mongo): {e}")

        try:
            self.sqlite_cursor.execute("SELECT * FROM expenses WHERE project_id = ?", (project_name,))
            rows = self.sqlite_cursor.fetchall()
            return [schemas.Expense(**dict(row)) for row in rows]
        except Exception as e:
            print(f"ERROR: [Repo] فشل جلب مصروفات المشروع (SQLite): {e}")
            return []

    # --- دوال الداشبورد (جديدة) ---

    def get_dashboard_kpis(self) -> dict:
        """
        (معدلة) تحسب الأرقام الرئيسية للداشبورد (أونلاين أولاً).
        """
        print("INFO: [Repo] جاري حساب أرقام الداشبورد...")

        # --- (الجديد) الوضع الأونلاين ---
        if self.online:
            try:
                print("INFO: [Repo] ... (الوضع الأونلاين: جاري الحساب من MongoDB)")
                total_collected = 0.0
                # (هنستخدم الطريقة البسيطة والمضمونة: نجيبهم ونجمعهم هنا)
                payments = list(self.mongo_db.payments.find({}, {"amount": 1}))
                for p in payments:
                    total_collected += p.get("amount", 0)

                total_expenses = 0.0
                expenses = list(self.mongo_db.expenses.find({}, {"amount": 1}))
                for e in expenses:
                    total_expenses += e.get("amount", 0)

                total_outstanding = 0.0
                # (هنا بنجيب المشاريع اللي لسه مفتوحة ونحسب المتبقي لكل مشروع)
                projects = list(self.mongo_db.projects.find(
                    {"status": {"$in": [schemas.ProjectStatus.ACTIVE.value, schemas.ProjectStatus.PLANNING.value, schemas.ProjectStatus.ON_HOLD.value]}},
                    {"name": 1, "total_amount": 1}
                ))

                # حساب المتبقي لكل مشروع على حدة
                for project in projects:
                    project_name = project.get("name")
                    project_total = project.get("total_amount", 0)
                    
                    # جلب الدفعات الخاصة بهذا المشروع فقط
                    project_payments = list(self.mongo_db.payments.find(
                        {"project_id": project_name},
                        {"amount": 1}
                    ))
                    project_paid = sum([p.get("amount", 0) for p in project_payments])
                    
                    # المتبقي = الإجمالي - المدفوع
                    project_remaining = project_total - project_paid
                    if project_remaining > 0:
                        total_outstanding += project_remaining

                net_profit_cash = total_collected - total_expenses

                print(f"INFO: [Repo] (Online) Collected: {total_collected}, Expenses: {total_expenses}, Outstanding: {total_outstanding}")

                return {
                    "total_collected": total_collected,
                    "total_outstanding": total_outstanding,
                    "total_expenses": total_expenses,
                    "net_profit_cash": net_profit_cash
                }
            except Exception as e:
                print(f"ERROR: [Repo] فشل الحساب من MongoDB: {e}. سيتم محاولة الأوفلاين.")

        # --- (القديم) الوضع الأوفلاين (لو النت فاصل) ---
        print("INFO: [Repo] ... (الوضع الأوفلاين: جاري الحساب من SQLite)")
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

            print(f"INFO: [Repo] (Offline) Collected: {total_collected}, Expenses: {total_expenses}, Outstanding: {total_outstanding}")

        except Exception as e:
            print(f"ERROR: [Repo] فشل حساب أرقام الداشبورد (SQLite): {e}")

        return {
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
            "total_expenses": total_expenses,
            "net_profit_cash": net_profit_cash
        }

    # --- دوال العملات (جديدة) ---

    def get_all_currencies(self) -> List[dict]:
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
                    print(f"INFO: [Repo] تم جلب {len(currencies)} عملة من الأونلاين")
                    return currencies
            except Exception as e:
                print(f"WARNING: [Repo] فشل جلب العملات من MongoDB: {e}")
        
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
            print(f"ERROR: [Repo] فشل جلب العملات: {e}")
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
            print(f"INFO: [Repo] تم حفظ العملة {code} محلياً")
            
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
                    print(f"INFO: [Repo] تم مزامنة العملة {code} أونلاين")
                    
                except Exception as e:
                    print(f"WARNING: [Repo] فشل مزامنة العملة {code} أونلاين: {e}")
            
            return True
            
        except Exception as e:
            print(f"ERROR: [Repo] فشل حفظ العملة {code}: {e}")
            return False

    def delete_currency(self, code: str) -> bool:
        """حذف عملة (مع مزامنة)"""
        try:
            if code.upper() == 'EGP':
                print("WARNING: [Repo] لا يمكن حذف العملة الأساسية")
                return False
            
            # حذف من SQLite
            self.sqlite_cursor.execute("DELETE FROM currencies WHERE code = ?", (code.upper(),))
            self.sqlite_conn.commit()
            
            # حذف من MongoDB
            if self.online:
                try:
                    self.mongo_db.currencies.delete_one({'code': code.upper()})
                    print(f"INFO: [Repo] تم حذف العملة {code} من الأونلاين")
                except Exception as e:
                    print(f"WARNING: [Repo] فشل حذف العملة من MongoDB: {e}")
            
            print(f"INFO: [Repo] تم حذف العملة {code}")
            return True
        except Exception as e:
            print(f"ERROR: [Repo] فشل حذف العملة {code}: {e}")
            return False

    def fetch_live_exchange_rate(self, currency_code: str) -> Optional[float]:
        """جلب سعر الصرف الحقيقي من الإنترنت"""
        import urllib.request
        
        currency_code = currency_code.upper()
        if currency_code == 'EGP':
            return 1.0
        
        try:
            # API 1: Open Exchange Rates
            url = "https://open.er-api.com/v6/latest/USD"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                if data.get('result') == 'success' and 'rates' in data:
                    rates = data['rates']
                    egp_rate = rates.get('EGP', 0)
                    currency_rate = rates.get(currency_code, 0)
                    
                    if egp_rate > 0 and currency_rate > 0:
                        rate = egp_rate / currency_rate
                        print(f"INFO: [Repo] سعر {currency_code} = {rate:.4f} EGP (من API)")
                        return round(rate, 4)
        except Exception as e:
            print(f"WARNING: [Repo] فشل جلب السعر من API 1: {e}")
        
        try:
            # API 2: ExchangeRate-API
            url = f"https://api.exchangerate-api.com/v4/latest/{currency_code}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                if 'rates' in data:
                    egp_rate = data['rates'].get('EGP', 0)
                    if egp_rate > 0:
                        print(f"INFO: [Repo] سعر {currency_code} = {egp_rate:.4f} EGP (من API 2)")
                        return round(egp_rate, 4)
        except Exception as e:
            print(f"WARNING: [Repo] فشل جلب السعر من API 2: {e}")
        
        return None

    def init_default_currencies(self):
        """إنشاء العملات الافتراضية مع جلب الأسعار الحقيقية من الإنترنت"""
        default_currencies = [
            {'code': 'EGP', 'name': 'جنيه مصري', 'symbol': 'ج.م', 'rate': 1.0, 'is_base': True},
            {'code': 'USD', 'name': 'دولار أمريكي', 'symbol': 'دولار'},
            {'code': 'SAR', 'name': 'ريال سعودي', 'symbol': 'ر.س', 'rate': 12.65},
            {'code': 'AED', 'name': 'درهم إماراتي', 'symbol': 'د.إ', 'rate': 12.92},
        ]
        
        print("INFO: [Repo] جاري إنشاء العملات الافتراضية وجلب الأسعار من الإنترنت...")

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
                    print(f"WARNING: [Repo] استخدام سعر احتياطي لـ {code}: {curr['rate']}")

            self.save_currency(curr)

        print("INFO: [Repo] تم إنشاء العملات الافتراضية بنجاح")

    def update_all_exchange_rates(self) -> dict:
        """تحديث جميع أسعار الصرف من الإنترنت"""
        print("INFO: [Repo] جاري تحديث جميع أسعار الصرف...")

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
                print(f"INFO: [Repo] تم تحديث {code}: {live_rate}")
            else:
                failed += 1
                results[code] = {'success': False, 'rate': curr['rate']}
                print(f"WARNING: [Repo] فشل تحديث {code}")

        print(f"INFO: [Repo] تم تحديث {updated} عملة، فشل {failed}")
        return {'updated': updated, 'failed': failed, 'results': results}


# --- كود للاختبار (اختياري) ---
if __name__ == "__main__":
    print("--- بدء اختبار الـ Repository ---")
    repo = Repository()
    
    print(f"\nحالة الاتصال: {'أونلاين' if repo.is_online() else 'أوفلاين'}")
    
    # اختبار إضافة عميل جديد
    print("\n--- اختبار إضافة عميل ---")
    new_client = schemas.Client(
        name="Test Client " + str(datetime.now().second),
        company_name="Test Co.",
        email="test@example.com",
        phone="123456789"
    )
    repo.create_client(new_client)
    
    # اختبار جلب كل العملاء
    print("\n--- اختبار جلب العملاء ---")
    all_clients = repo.get_all_clients()
    for client in all_clients:
        print(f"- {client.name} (Status: {client.sync_status}, MongoID: {client._mongo_id})")
    
    print("\n--- انتهاء الاختبار ---")
