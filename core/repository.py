# pylint: disable=R0801,duplicate-code,too-many-lines,too-many-nested-blocks,too-many-public-methods
# الملف: core/repository.py
"""
⚡ المخزن الذكي - Sky Wave ERP
محسّن للسرعة القصوى مع نظام Cache ذكي
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
import traceback
import urllib.request
import uuid
from datetime import datetime
from typing import Any

from .project_currency import normalize_currency_code, normalize_exchange_rate
from .sqlite_identifiers import quote_identifier
from .text_utils import normalize_user_text

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg: str):
        """طباعة آمنة تتعامل مع مشاكل الترميز في Windows"""
        try:
            print(msg)
        except UnicodeEncodeError:
            # إزالة الـ emoji وطباعة النص فقط
            clean_msg = re.sub(r"[^\x00-\x7F\u0600-\u06FF]+", "", msg)
            try:
                print(clean_msg)
            except Exception:
                pass  # تجاهل أي خطأ في الطباعة


_PYMONGO_MODULE = None
_PYMONGO_CHECKED = False
_OBJECT_ID_CLASS = None
_OBJECT_ID_CHECKED = False
_AUTH_MODELS = None
_AUTH_MODELS_CHECKED = False
_SCHEMAS_MODULE = None
_SCHEMAS_CHECKED = False


def _get_pymongo_module():
    global _PYMONGO_MODULE, _PYMONGO_CHECKED
    if _PYMONGO_CHECKED:
        return _PYMONGO_MODULE
    _PYMONGO_CHECKED = True
    try:
        import pymongo as pymongo_module

        _PYMONGO_MODULE = pymongo_module
    except ImportError:
        _PYMONGO_MODULE = None
    return _PYMONGO_MODULE


def _get_object_id_class():
    global _OBJECT_ID_CLASS, _OBJECT_ID_CHECKED
    if _OBJECT_ID_CHECKED:
        return _OBJECT_ID_CLASS
    _OBJECT_ID_CHECKED = True
    try:
        from bson import ObjectId as object_id_class

        _OBJECT_ID_CLASS = object_id_class
    except ImportError:
        _OBJECT_ID_CLASS = None
    return _OBJECT_ID_CLASS


def _get_auth_models():
    global _AUTH_MODELS, _AUTH_MODELS_CHECKED
    if _AUTH_MODELS_CHECKED:
        return _AUTH_MODELS
    _AUTH_MODELS_CHECKED = True
    try:
        from core.auth_models import User as user_class
        from core.auth_models import UserRole as user_role_class

        _AUTH_MODELS = (user_class, user_role_class)
    except ImportError:
        _AUTH_MODELS = (None, None)
    return _AUTH_MODELS


def _get_schemas_module():
    global _SCHEMAS_MODULE, _SCHEMAS_CHECKED
    if _SCHEMAS_CHECKED:
        return _SCHEMAS_MODULE
    _SCHEMAS_CHECKED = True
    from . import schemas as schemas_module

    _SCHEMAS_MODULE = schemas_module
    return _SCHEMAS_MODULE


class _LazySchemasProxy:
    def __getattr__(self, item: str):
        return getattr(_get_schemas_module(), item)


schemas = _LazySchemasProxy()


def _schedule_delayed_callback(delay_ms: int, callback) -> None:
    try:
        from PyQt6.QtCore import QTimer as qt_timer

        qt_timer.singleShot(delay_ms, callback)
    except Exception:
        timer = threading.Timer(max(delay_ms, 0) / 1000.0, callback)
        timer.daemon = True
        timer.start()


class QTimer:
    """طبقة توافق خفيفة للاختبارات والكود القديم بدون import بارد لـ PyQt."""

    @staticmethod
    def singleShot(delay_ms: int, callback) -> None:
        _schedule_delayed_callback(delay_ms, callback)


# ⚡ استيراد محسّن السرعة
try:
    from .speed_optimizer import LRUCache, cached, invalidate_cache  # noqa: F401

    CACHE_ENABLED = True
except ImportError:
    CACHE_ENABLED = False
    safe_print("WARNING: speed_optimizer غير متوفر - الـ cache معطل")

# ⚡ لا نحمّل performance_optimizer عند الاستيراد لأنه غير مستخدم runtime هنا.
PERFORMANCE_OPTIMIZER_ENABLED = False

# ⚡ استيراد إعدادات التكوين الآمنة
try:
    from .config import Config

    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False
    safe_print("WARNING: config module غير متوفر - استخدام القيم الافتراضية")

# --- إعدادات الاتصال (من متغيرات البيئة) ---
if CONFIG_LOADED:
    MONGO_URI = Config.get_mongo_uri()
    DB_NAME = Config.get_db_name()
    LOCAL_DB_FILE = Config.get_local_db_path()
else:
    # قيم احتياطية للتوافق
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/skywave_erp_db")
    DB_NAME = os.environ.get("MONGO_DB_NAME", "skywave_erp_db")
    _PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))
    LOCAL_DB_FILE = os.path.join(_PROJECT_DIR, "skywave_local.db")


_SQLITE_BOOTSTRAP_VERSION = 1


# ⚡ نسخ قاعدة البيانات من مجلد البرنامج لو مش موجودة في AppData
def _copy_initial_db():
    """نسخ قاعدة البيانات الأولية من مجلد البرنامج إذا لم تكن موجودة"""

    if os.path.exists(LOCAL_DB_FILE):
        return  # قاعدة البيانات موجودة بالفعل

    # البحث عن قاعدة البيانات في مجلد البرنامج
    possible_paths = []

    if getattr(sys, "frozen", False):
        # التطبيق يعمل كـ EXE
        exe_dir = os.path.dirname(sys.executable)
        possible_paths = [
            os.path.join(
                exe_dir, "skywave_local.db"
            ),  # الأولوية للملف الموجود بجانب الملف التنفيذي
            os.path.join(exe_dir, "_internal", "skywave_local.db"),
        ]
        if hasattr(sys, "_MEIPASS"):
            possible_paths.append(os.path.join(sys._MEIPASS, "skywave_local.db"))
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

    safe_print("INFO: لم يتم العثور على قاعدة بيانات أولية - سيتم إنشاء قاعدة جديدة")


# تنفيذ النسخ عند تحميل الموديول
_copy_initial_db()


class CursorContextManager:
    """
    ⚡ Context Manager للـ cursor لضمان إغلاقه تلقائياً

    الاستخدام:
        with repo.get_cursor() as cursor:
            cursor.execute("SELECT * FROM table")
            rows = cursor.fetchall()
        # الـ cursor يُغلق تلقائياً هنا
    """

    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self._cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._cursor.close()
        except Exception:
            pass
        return False  # لا نبتلع الاستثناءات

    # تمرير كل الدوال للـ cursor الأصلي
    def execute(self, *args, **kwargs):
        return self._cursor.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._cursor.executemany(*args, **kwargs)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return self._cursor.fetchmany(size)

    def close(self):
        return self._cursor.close()

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid


class Repository:
    """
    ⚡ المخزن الذكي مع Caching للسرعة القصوى.
    - Cache ذكي للبيانات المتكررة
    - SQLite محسّن للأداء
    - MongoDB للمزامنة (في background)
    """

    _PROJECT_KEY_TRANSLATION = str.maketrans(
        {
            "أ": "ا",
            "إ": "ا",
            "آ": "ا",
            "ى": "ي",
            "ؤ": "و",
            "ئ": "ي",
        }
    )
    _active_instance = None

    def __init__(self):
        self.online = False
        self.mongo_client = None
        self.mongo_db = None
        self._closed = False
        self._lock = threading.RLock()
        self._mongo_stop_event = threading.Event()
        self._mongo_connecting = False
        self._mongo_retry_thread_started = False
        self._mongo_connection_thread = None
        self._mongo_retry_thread = None
        self._mongo_indexes_initialized = False
        self._mongo_retry_interval_seconds = self._safe_int_env(
            "SKYWAVE_MONGO_RETRY_INTERVAL_SEC",
            default=10,
            minimum=5,
            maximum=120,
        )
        self._sqlite_table_columns_cache: dict[str, set[str]] = {}

        # ⚡ Cache للبيانات المتكررة - TTL محسّن للسرعة
        if CACHE_ENABLED:
            self._clients_cache = LRUCache(maxsize=1000, ttl_seconds=300)  # ⚡ 5 دقائق
            self._projects_cache = LRUCache(maxsize=1000, ttl_seconds=300)  # ⚡ 5 دقائق
            self._services_cache = LRUCache(maxsize=500, ttl_seconds=600)  # ⚡ 10 دقائق
            self._accounts_cache = LRUCache(maxsize=500, ttl_seconds=600)  # ⚡ 10 دقائق
            self._payments_cache = LRUCache(maxsize=500, ttl_seconds=180)  # ⚡ 3 دقائق
            self._expenses_cache = LRUCache(maxsize=500, ttl_seconds=180)  # ⚡ 3 دقائق

        # ⚡ 1. SQLite أولاً (سريع جداً) - لا ننتظر MongoDB
        self.sqlite_conn = sqlite3.connect(
            LOCAL_DB_FILE,
            check_same_thread=False,
            timeout=30.0,
            isolation_level="DEFERRED",  # ⚡ معاملات آمنة مع أداء جيد
        )
        self.sqlite_conn.row_factory = sqlite3.Row
        self.sqlite_cursor = self.sqlite_conn.cursor()

        # ⚡ تطبيق تحسينات SQLite للأداء
        self._apply_sqlite_optimizations()

        safe_print(f"INFO: ✅ متصل بقاعدة البيانات الأوفلاين ({LOCAL_DB_FILE}).")

        # 2. بناء الجداول الأوفلاين لو مش موجودة
        self._init_local_db()
        Repository._active_instance = self

        # ⚡ 3. الاتصال بـ MongoDB في Background Thread (لا يعطل البرنامج)
        self._start_mongo_connection()
        self._start_mongo_retry_loop()

    @classmethod
    def get_active_instance(cls):
        return cls._active_instance

    @staticmethod
    def _is_sqlite_closed_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return ("sqlite_closed" in text) or ("nonetype" in text and "cursor" in text)

    @staticmethod
    def _safe_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(str(os.environ.get(name, default)).strip())
        except Exception:
            value = int(default)
        if value < minimum:
            value = minimum
        if value > maximum:
            value = maximum
        return value

    def _mongo_client_options(self) -> dict[str, Any]:
        max_pool = self._safe_int_env(
            "SKYWAVE_MONGO_MAX_POOL_SIZE",
            default=20,
            minimum=4,
            maximum=200,
        )
        min_pool = self._safe_int_env(
            "SKYWAVE_MONGO_MIN_POOL_SIZE",
            default=2,
            minimum=0,
            maximum=max_pool,
        )
        return {
            "retryWrites": True,
            "retryReads": True,
            "maxPoolSize": max_pool,
            "minPoolSize": min_pool,
            "maxIdleTimeMS": self._safe_int_env(
                "SKYWAVE_MONGO_MAX_IDLE_MS",
                default=120000,
                minimum=30000,
                maximum=600000,
            ),
            "waitQueueTimeoutMS": self._safe_int_env(
                "SKYWAVE_MONGO_WAIT_QUEUE_TIMEOUT_MS",
                default=10000,
                minimum=1000,
                maximum=120000,
            ),
            "appname": "SkyWaveERP",
        }

    def _ensure_mongo_indexes_ready(self) -> None:
        with self._lock:
            if (
                self._closed
                or not self.online
                or self.mongo_db is None
                or self._mongo_indexes_initialized
            ):
                return
        if self._init_mongo_indexes():
            with self._lock:
                if not self._closed:
                    self._mongo_indexes_initialized = True

    def get_cursor(self):
        """
        ⚡ الحصول على cursor منفصل لتجنب مشكلة Recursive cursor
        يجب إغلاق الـ cursor بعد الاستخدام: cursor.close()

        يمكن استخدامه كـ context manager:
            with self.get_cursor() as cursor:
                cursor.execute(...)
        """
        with self._lock:
            if self.sqlite_conn is None:
                raise RuntimeError("sqlite_closed")
            try:
                cursor = self.sqlite_conn.cursor()
                cursor.row_factory = sqlite3.Row  # تأكد من تطبيق row_factory
                return CursorContextManager(cursor)
            except Exception as e:
                if "sqlite_closed" not in str(e).lower():
                    safe_print(f"ERROR: [Repository] فشل إنشاء cursor: {e}")
                raise

    def _account_has_children(self, account_code: str) -> bool:
        if not account_code:
            return False
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT 1 FROM accounts
                    WHERE parent_id = ?
                    AND (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    LIMIT 1
                    """,
                    (account_code,),
                )
                return cursor.fetchone() is not None
            finally:
                cursor.close()
        except Exception:
            return False

    def _account_group_codes_from_rows(self, rows) -> set[str]:
        group_codes: set[str] = set()
        for row in rows or []:
            row_dict = dict(row)
            parent_code = str(
                row_dict.get("parent_id") or row_dict.get("parent_code") or ""
            ).strip()
            if parent_code:
                group_codes.add(parent_code)
        return group_codes

    def _account_from_row(self, row, *, group_codes: set[str] | None = None) -> schemas.Account:
        data = dict(row)
        if "is_group" not in data:
            code = str(data.get("code") or "").strip()
            data["is_group"] = (
                code in group_codes if group_codes is not None else self._account_has_children(code)
            )
        return schemas.Account(**data)

    def _table_exists(self, table_name: str) -> bool:
        if not table_name or self.sqlite_conn is None:
            return False
        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
                        (table_name,),
                    )
                    return cursor.fetchone() is not None
                finally:
                    cursor.close()
        except Exception:
            return False

    def _table_sql(self, table_name: str) -> str:
        if not table_name or self.sqlite_conn is None:
            return ""
        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
                        (table_name,),
                    )
                    row = cursor.fetchone()
                    return str(row[0] or "") if row else ""
                finally:
                    cursor.close()
        except Exception:
            return ""

    def _table_columns(self, table_name: str) -> set[str]:
        if not table_name or self.sqlite_conn is None:
            return set()

        cached = self._sqlite_table_columns_cache.get(table_name)
        if cached is not None:
            return set(cached)

        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"PRAGMA table_info({self._quote_sqlite_identifier(table_name)})"
                    )
                    columns = {str(row[1] or "").strip() for row in cursor.fetchall() if row}
                finally:
                    cursor.close()
        except Exception:
            columns = set()

        self._sqlite_table_columns_cache[table_name] = set(columns)
        return columns

    def _table_has_column(self, table_name: str, column_name: str) -> bool:
        return bool(column_name and column_name in self._table_columns(table_name))

    @staticmethod
    def _sync_aware_tables() -> list[str]:
        return [
            "accounts",
            "expenses",
            "clients",
            "services",
            "invoices",
            "projects",
            "journal_entries",
            "payments",
            "currencies",
            "notifications",
            "users",
            "employees",
            "employee_loans",
            "employee_salaries",
            "employee_attendance",
            "employee_leaves",
            "loan_payments",
            "quotations",
            "tasks",
        ]

    def _get_sqlite_user_version(self) -> int:
        if self.sqlite_conn is None:
            return 0
        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute("PRAGMA user_version")
                    row = cursor.fetchone()
                finally:
                    cursor.close()
            return int(row[0]) if row else 0
        except Exception:
            return 0

    def _set_sqlite_user_version(self, version: int) -> None:
        if self.sqlite_conn is None:
            return
        try:
            with self._lock:
                self.sqlite_cursor.execute(f"PRAGMA user_version = {int(version)}")
                self.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"WARNING: [Repository] فشل تحديث SQLite user_version: {e}")

    def _sqlite_bootstrap_required(self) -> bool:
        if self._get_sqlite_user_version() < _SQLITE_BOOTSTRAP_VERSION:
            return True
        required_tables = (
            "accounts",
            "clients",
            "services",
            "projects",
            "invoices",
            "payments",
            "expenses",
            "journal_entries",
            "currencies",
            "notifications",
            "tasks",
            "users",
            "sync_queue",
        )
        return any(not self._table_exists(table) for table in required_tables)

    def _run_sync_state_maintenance(self, sync_tables: list[str]) -> None:
        safe_print("INFO: [Repository] 🔄 جاري تنشيط البيانات القديمة للمزامنة...")
        allowed_sync_tables = {str(table).strip() for table in sync_tables}

        for table in sync_tables:
            try:
                table_ref = self._quote_sqlite_identifier(table, allowed=allowed_sync_tables)
                update_dirty_sql = f"""
                    UPDATE {table_ref}
                    SET dirty_flag = 1
                    WHERE dirty_flag IS NULL
                       OR (
                            dirty_flag = 0
                            AND (
                                is_deleted = 1
                                OR _mongo_id IS NULL
                                OR sync_status IS NULL
                                OR TRIM(sync_status) = ''
                                OR sync_status IN ('new_offline', 'modified_offline', 'pending', 'deleted')
                            )
                        )
                """  # nosec B608
                self.sqlite_cursor.execute(update_dirty_sql)
                updated_count = self.sqlite_cursor.rowcount
                if updated_count > 0:
                    safe_print(
                        f"INFO: [Repository] ⚡ تم تنشيط {updated_count} سجل في {table} للمزامنة"
                    )

                clear_false_dirty_sql = f"""
                    UPDATE {table_ref}
                    SET dirty_flag = 0
                    WHERE dirty_flag = 1
                      AND (_mongo_id IS NOT NULL AND TRIM(_mongo_id) != '')
                      AND COALESCE(sync_status, '') = 'synced'
                      AND COALESCE(is_deleted, 0) = 0
                """  # nosec B608
                self.sqlite_cursor.execute(clear_false_dirty_sql)
                cleaned_count = self.sqlite_cursor.rowcount
                if cleaned_count > 0:
                    safe_print(
                        f"INFO: [Repository] 🧯 تم تنظيف {cleaned_count} سجل متزامن في {table}"
                    )
            except sqlite3.OperationalError as e:
                safe_print(f"WARNING: [Repository] فشل تنشيط {table}: {e}")

        self.sqlite_conn.commit()

        safe_print("INFO: [Repository] 🧹 جاري تنظيف القيم الفارغة...")
        now_iso = datetime.now().isoformat()
        for table in sync_tables:
            try:
                table_ref = self._quote_sqlite_identifier(table, allowed=allowed_sync_tables)
                self.sqlite_cursor.execute(
                    f"""
                    UPDATE {table_ref}
                    SET is_deleted = COALESCE(is_deleted, 0),
                        sync_status = CASE
                            WHEN sync_status IS NULL THEN 'pending'
                            ELSE sync_status
                        END,
                        last_modified = COALESCE(last_modified, ?)
                    WHERE is_deleted IS NULL
                       OR sync_status IS NULL
                       OR last_modified IS NULL
                    """,  # nosec B608
                    (now_iso,),
                )
            except sqlite3.OperationalError as e:
                safe_print(f"WARNING: [Repository] فشل تنظيف {table}: {e}")

        self.sqlite_conn.commit()

    @staticmethod
    def _quote_sqlite_identifier(identifier: str, *, allowed: set[str] | None = None) -> str:
        return quote_identifier(identifier, allowed=allowed)

    def _migrate_projects_table_remove_global_name_unique(self) -> None:
        table_sql = self._table_sql("projects").lower()
        if "name text not null unique" not in table_sql:
            return

        safe_print("INFO: [Repository] إصلاح قيد UNIQUE القديم على projects.name ...")
        self.sqlite_cursor.execute("PRAGMA foreign_keys=OFF")
        try:
            self.sqlite_cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS projects_migrated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    _mongo_id TEXT,
                    sync_status TEXT NOT NULL DEFAULT 'new_offline',
                    created_at TEXT NOT NULL,
                    last_modified TEXT NOT NULL,
                    name TEXT NOT NULL,
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
                    exchange_rate_snapshot REAL DEFAULT 1.0,
                    project_notes TEXT,
                    invoice_number TEXT,
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
                )
                """
            )
            self.sqlite_cursor.execute(
                """
                INSERT INTO projects_migrated (
                    id, _mongo_id, sync_status, created_at, last_modified, name, client_id,
                    status, status_manually_set, description, start_date, end_date, items,
                    subtotal, discount_rate, discount_amount, tax_rate, tax_amount,
                    total_amount, currency, exchange_rate_snapshot, project_notes, invoice_number, project_code,
                    sequence_number, cost_center_id, contract_type, is_retainer,
                    renewal_cycle, next_renewal_date, milestones, total_estimated_cost,
                    estimated_profit, profit_margin, project_manager_id
                )
                SELECT
                    id, _mongo_id, sync_status, created_at, last_modified, name, client_id,
                    status, status_manually_set, description, start_date, end_date, items,
                    subtotal, discount_rate, discount_amount, tax_rate, tax_amount,
                    total_amount, currency, 1.0 AS exchange_rate_snapshot, project_notes, invoice_number, project_code,
                    sequence_number, cost_center_id, contract_type, is_retainer,
                    renewal_cycle, next_renewal_date, milestones, total_estimated_cost,
                    estimated_profit, profit_margin, project_manager_id
                FROM projects
                """
            )
            self.sqlite_cursor.execute("DROP TABLE projects")
            self.sqlite_cursor.execute("ALTER TABLE projects_migrated RENAME TO projects")
            self.sqlite_conn.commit()
        finally:
            self.sqlite_cursor.execute("PRAGMA foreign_keys=ON")

    def _migrate_project_reference_tables_remove_name_foreign_keys(self) -> None:
        tasks_sql = self._table_sql("tasks").lower()
        milestones_sql = self._table_sql("project_milestones").lower()

        needs_tasks_migration = "references projects(name)" in tasks_sql
        needs_milestones_migration = "references projects(name)" in milestones_sql

        if not needs_tasks_migration and not needs_milestones_migration:
            return

        safe_print("INFO: [Repository] إصلاح Foreign Keys القديمة المرتبطة بـ projects(name) ...")
        self.sqlite_cursor.execute("PRAGMA foreign_keys=OFF")
        try:
            if needs_tasks_migration:
                self.sqlite_cursor.execute("DROP TABLE IF EXISTS tasks_migrated")
                self.sqlite_cursor.execute(
                    """
                    CREATE TABLE tasks_migrated (
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
                        is_deleted INTEGER DEFAULT 0,
                        dirty_flag INTEGER DEFAULT 0,
                        FOREIGN KEY (related_client_id) REFERENCES clients(id)
                    )
                    """
                )
                self.sqlite_cursor.execute(
                    """
                    INSERT INTO tasks_migrated (
                        id, _mongo_id, sync_status, created_at, last_modified,
                        title, description, priority, status, category,
                        due_date, due_time, completed_at, related_project_id,
                        related_client_id, tags, reminder, reminder_minutes,
                        assigned_to, is_archived, is_deleted, dirty_flag
                    )
                    SELECT
                        id, _mongo_id, sync_status, created_at, last_modified,
                        title, description, priority, status, category,
                        due_date, due_time, completed_at, related_project_id,
                        related_client_id, tags, reminder, reminder_minutes,
                        assigned_to, is_archived, is_deleted, dirty_flag
                    FROM tasks
                    """
                )
                self.sqlite_cursor.execute("DROP TABLE tasks")
                self.sqlite_cursor.execute("ALTER TABLE tasks_migrated RENAME TO tasks")

            if needs_milestones_migration:
                self.sqlite_cursor.execute("DROP TABLE IF EXISTS project_milestones_migrated")
                self.sqlite_cursor.execute(
                    """
                    CREATE TABLE project_milestones_migrated (
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
                        created_at TEXT NOT NULL
                    )
                    """
                )
                self.sqlite_cursor.execute(
                    """
                    INSERT INTO project_milestones_migrated (
                        id, project_id, name, percentage, amount, due_date,
                        status, invoice_id, paid_date, notes, created_at
                    )
                    SELECT
                        id, project_id, name, percentage, amount, due_date,
                        status, invoice_id, paid_date, notes, created_at
                    FROM project_milestones
                    """
                )
                self.sqlite_cursor.execute("DROP TABLE project_milestones")
                self.sqlite_cursor.execute(
                    "ALTER TABLE project_milestones_migrated RENAME TO project_milestones"
                )

            self.sqlite_conn.commit()
        finally:
            self.sqlite_cursor.execute("PRAGMA foreign_keys=ON")

    def _migrate_invoice_numbers_table_use_project_ids(self) -> None:
        table_sql = self._table_sql("invoice_numbers").lower()
        if not table_sql:
            return

        has_project_id = "project_id" in table_sql
        uses_legacy_name_unique = "project_name text not null unique" in table_sql
        if has_project_id and not uses_legacy_name_unique:
            return

        safe_print("INFO: [Repository] إصلاح جدول invoice_numbers ليرتبط بـ project_id ...")
        self.sqlite_cursor.execute("PRAGMA foreign_keys=OFF")
        try:
            self.sqlite_cursor.execute("DROP TABLE IF EXISTS invoice_numbers_migrated")
            self.sqlite_cursor.execute(
                """
                CREATE TABLE invoice_numbers_migrated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT UNIQUE,
                    project_name TEXT NOT NULL,
                    invoice_number TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
                """
            )

            self.sqlite_cursor.execute(
                "SELECT id, project_name, invoice_number, created_at FROM invoice_numbers ORDER BY id"
            )
            legacy_rows = self.sqlite_cursor.fetchall()

            for row in legacy_rows:
                legacy_id = row[0]
                project_name = str(row[1] or "").strip()
                invoice_number = str(row[2] or "").strip()
                created_at = str(row[3] or datetime.now().isoformat())
                resolved_project_id = None
                resolved_project_name = project_name

                self.sqlite_cursor.execute(
                    "SELECT id, name FROM projects WHERE invoice_number = ? ORDER BY id LIMIT 1",
                    (invoice_number,),
                )
                matched_project = self.sqlite_cursor.fetchone()
                if not matched_project and project_name:
                    self.sqlite_cursor.execute(
                        "SELECT id, name FROM projects WHERE name = ? ORDER BY id LIMIT 1",
                        (project_name,),
                    )
                    matched_project = self.sqlite_cursor.fetchone()

                if matched_project:
                    resolved_project_id = str(matched_project[0])
                    resolved_project_name = str(matched_project[1] or project_name)

                self.sqlite_cursor.execute(
                    """
                    INSERT INTO invoice_numbers_migrated (
                        id, project_id, project_name, invoice_number, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        legacy_id,
                        resolved_project_id,
                        resolved_project_name,
                        invoice_number,
                        created_at,
                    ),
                )

            self.sqlite_cursor.execute(
                """
                SELECT invoice_number
                FROM projects
                WHERE invoice_number IS NOT NULL AND invoice_number != ''
                GROUP BY invoice_number
                HAVING COUNT(*) > 1
                """
            )
            duplicate_invoice_rows = self.sqlite_cursor.fetchall()
            for duplicate_row in duplicate_invoice_rows:
                duplicate_invoice = str(duplicate_row[0] or "").strip()
                if not duplicate_invoice:
                    continue
                self.sqlite_cursor.execute(
                    "SELECT id FROM projects WHERE invoice_number = ? ORDER BY id",
                    (duplicate_invoice,),
                )
                duplicate_project_rows = self.sqlite_cursor.fetchall()
                for duplicate_project in duplicate_project_rows[1:]:
                    self.sqlite_cursor.execute(
                        "UPDATE projects SET invoice_number = '' WHERE id = ?",
                        (duplicate_project[0],),
                    )

            self.sqlite_cursor.execute(
                """
                SELECT id, name, invoice_number, created_at
                FROM projects
                WHERE invoice_number IS NOT NULL AND invoice_number != ''
                ORDER BY id
                """
            )
            project_rows = self.sqlite_cursor.fetchall()
            for project_row in project_rows:
                project_id = str(project_row[0])
                project_name = str(project_row[1] or "").strip()
                invoice_number = str(project_row[2] or "").strip()
                created_at = str(project_row[3] or datetime.now().isoformat())
                if not invoice_number:
                    continue

                self.sqlite_cursor.execute(
                    "SELECT invoice_number FROM invoice_numbers_migrated WHERE project_id = ?",
                    (project_id,),
                )
                existing_by_project = self.sqlite_cursor.fetchone()
                if existing_by_project:
                    self.sqlite_cursor.execute(
                        """
                        UPDATE invoice_numbers_migrated
                        SET project_name = ?, invoice_number = ?
                        WHERE project_id = ?
                        """,
                        (project_name, invoice_number, project_id),
                    )
                    continue

                self.sqlite_cursor.execute(
                    "SELECT project_id FROM invoice_numbers_migrated WHERE invoice_number = ?",
                    (invoice_number,),
                )
                existing_by_invoice = self.sqlite_cursor.fetchone()
                if existing_by_invoice:
                    continue

                self.sqlite_cursor.execute(
                    """
                    INSERT INTO invoice_numbers_migrated (
                        project_id, project_name, invoice_number, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (project_id, project_name, invoice_number, created_at),
                )

            self.sqlite_cursor.execute("DROP TABLE invoice_numbers")
            self.sqlite_cursor.execute(
                "ALTER TABLE invoice_numbers_migrated RENAME TO invoice_numbers"
            )
            self.sqlite_conn.commit()
        finally:
            self.sqlite_cursor.execute("PRAGMA foreign_keys=ON")

    def invalidate_table_cache(self, table_name: str | None = None) -> None:
        """Invalidate repository caches for one table (or all tables when not provided)."""
        cache_map = {
            "clients": "_clients_cache",
            "projects": "_projects_cache",
            "services": "_services_cache",
            "accounts": "_accounts_cache",
            "payments": "_payments_cache",
            "expenses": "_expenses_cache",
        }

        normalized = (table_name or "").strip().lower()
        keys = list(cache_map.keys()) if not normalized else [normalized]

        if CACHE_ENABLED:
            for key in keys:
                attr_name = cache_map.get(key)
                if not attr_name or not hasattr(self, attr_name):
                    continue
                try:
                    getattr(self, attr_name).invalidate()
                except Exception:
                    pass

        # Dashboard depends on accounting/projects/payments/expenses totals.
        if not normalized or normalized in {
            "projects",
            "payments",
            "expenses",
            "accounts",
            "journal_entries",
            "invoices",
        }:
            Repository._dashboard_cache = None
            Repository._dashboard_cache_time = 0

    def close(self):
        """⚡ إغلاق اتصالات قاعدة البيانات"""
        connection_thread = None
        retry_thread = None
        try:
            with self._lock:
                self._closed = True
                self._mongo_stop_event.set()
                connection_thread = self._mongo_connection_thread
                retry_thread = self._mongo_retry_thread

                try:
                    if self.sqlite_cursor is not None:
                        self.sqlite_cursor.close()
                except Exception:
                    pass
                finally:
                    self.sqlite_cursor = None

                try:
                    if self.sqlite_conn is not None:
                        self.sqlite_conn.close()
                except Exception:
                    pass
                finally:
                    self.sqlite_conn = None

                try:
                    if self.mongo_client is not None:
                        self.mongo_client.close()
                except Exception:
                    pass
                finally:
                    self.mongo_client = None
                    self.mongo_db = None
                    self.online = False
                    self._mongo_connecting = False
                    self._mongo_indexes_initialized = False
                    if Repository._active_instance is self:
                        Repository._active_instance = None
                    try:
                        from services.notification_service import NotificationService

                        active_notification_service = getattr(
                            NotificationService, "_active_instance", None
                        )
                        if getattr(active_notification_service, "repo", None) is self:
                            NotificationService._active_instance = None
                    except Exception:
                        pass
            safe_print("INFO: [Repository] تم إغلاق اتصالات قاعدة البيانات")
        except Exception as e:
            safe_print(f"WARNING: [Repository] خطأ عند إغلاق الاتصالات: {e}")
        finally:
            current_thread = threading.current_thread()
            for thread in (connection_thread, retry_thread):
                if thread is None or thread is current_thread:
                    continue
                try:
                    if thread.is_alive():
                        thread.join(timeout=1.0)
                except Exception:
                    pass
            self._mongo_connection_thread = None
            self._mongo_retry_thread = None

    @staticmethod
    def _parse_activity_log_timestamp(value):
        if isinstance(value, datetime):
            return value
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except Exception:
            return None

    @staticmethod
    def _activity_log_row_to_dict(row) -> dict[str, Any]:
        timestamp = Repository._parse_activity_log_timestamp(row["created_at"])
        amount = row["amount"]
        return {
            "id": row["id"],
            "timestamp": timestamp,
            "date": timestamp.strftime("%Y-%m-%d") if isinstance(timestamp, datetime) else "",
            "action": str(row["action"] or "").strip(),
            "entity_type": str(row["entity_type"] or "").strip(),
            "operation": str(row["operation_text"] or "").strip(),
            "description": str(row["entity_name"] or "").strip(),
            "details": str(row["details"] or "").strip(),
            "amount": float(amount) if amount not in (None, "") else None,
        }

    def log_activity(
        self,
        *,
        action: str,
        entity_type: str,
        operation_text: str,
        entity_name: str,
        details: str = "",
        amount=None,
    ) -> int | None:
        with self._lock:
            if self.sqlite_conn is None:
                return None
            now_iso = datetime.now().isoformat(timespec="seconds")
            try:
                with self.get_cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO activity_logs (
                            created_at,
                            action,
                            entity_type,
                            operation_text,
                            entity_name,
                            details,
                            amount
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            now_iso,
                            str(action or "").strip(),
                            str(entity_type or "").strip(),
                            str(operation_text or "").strip(),
                            str(entity_name or "").strip(),
                            str(details or "").strip(),
                            float(amount) if amount not in (None, "") else None,
                        ),
                    )
                    activity_id = cursor.lastrowid
                self.sqlite_conn.commit()
                return activity_id
            except Exception as e:
                safe_print(f"WARNING: [Repository] فشل حفظ سجل النشاط: {e}")
                return None

    def get_recent_activity_logs(self, limit: int = 8) -> list[dict[str, Any]]:
        with self._lock:
            if self.sqlite_conn is None:
                return []
            try:
                safe_limit = max(1, int(limit or 8))
            except Exception:
                safe_limit = 8
            try:
                with self.get_cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, created_at, action, entity_type, operation_text, entity_name, details, amount
                        FROM activity_logs
                        ORDER BY datetime(created_at) DESC, id DESC
                        LIMIT ?
                        """,
                        (safe_limit,),
                    )
                    rows = cursor.fetchall() or []
                return [self._activity_log_row_to_dict(row) for row in rows]
            except Exception as e:
                safe_print(f"WARNING: [Repository] فشل جلب سجل النشاط: {e}")
                return []

    def _apply_sqlite_optimizations(self):
        """⚡ تحسينات SQLite للسرعة مع الحفاظ على الأمان"""
        try:
            # WAL mode للقراءة والكتابة المتزامنة
            self.sqlite_cursor.execute("PRAGMA journal_mode=WAL")
            # NORMAL sync للتوازن بين السرعة والأمان (بدلاً من OFF)
            self.sqlite_cursor.execute("PRAGMA synchronous=NORMAL")
            # زيادة حجم الـ cache (20000 صفحة = ~80MB)
            self.sqlite_cursor.execute("PRAGMA cache_size=20000")
            # تخزين الجداول المؤقتة في الذاكرة
            self.sqlite_cursor.execute("PRAGMA temp_store=MEMORY")
            # تفعيل memory-mapped I/O (512MB)
            self.sqlite_cursor.execute("PRAGMA mmap_size=536870912")
            # تفعيل الـ foreign keys
            self.sqlite_cursor.execute("PRAGMA foreign_keys=ON")
            # تحسين الـ locking
            self.sqlite_cursor.execute("PRAGMA locking_mode=NORMAL")
            # تحسين الـ page size
            self.sqlite_cursor.execute("PRAGMA page_size=4096")
            # ⚡ تفعيل busy_timeout لتجنب أخطاء القفل
            self.sqlite_cursor.execute("PRAGMA busy_timeout=30000")
            self.sqlite_cursor.execute("PRAGMA wal_autocheckpoint=1000")
            self.sqlite_cursor.execute("PRAGMA automatic_index=ON")
            self.sqlite_cursor.execute("PRAGMA optimize")
            safe_print("INFO: ⚡ تم تطبيق تحسينات SQLite للسرعة والأمان")
        except Exception as e:
            safe_print(f"WARNING: فشل تطبيق تحسينات SQLite: {e}")

    def _start_mongo_connection(self):
        """⚡ الاتصال بـ MongoDB في Background Thread - محسّن ومحاول"""
        if self._closed or self._mongo_stop_event.is_set():
            self.online = False
            return

        if os.environ.get("SKYWAVE_DISABLE_MONGO") == "1" or os.environ.get("PYTEST_CURRENT_TEST"):
            safe_print("INFO: MongoDB معطل في بيئة الاختبار")
            self.online = False
            return

        with self._lock:
            if self._closed or self._mongo_connecting:
                return
            self._mongo_connecting = True

        def connect_mongo():
            global MONGO_URI, DB_NAME

            max_retries = 3
            retry_delay = 2  # ثانيتين بين كل محاولة

            try:
                if CONFIG_LOADED:
                    mongo_uri = Config.get_mongo_uri()
                    db_name = Config.get_db_name()
                else:
                    mongo_uri = os.environ.get("MONGO_URI", MONGO_URI)
                    db_name = os.environ.get("MONGO_DB_NAME", DB_NAME)
                MONGO_URI = mongo_uri
                DB_NAME = db_name
            except Exception:
                mongo_uri = MONGO_URI
                db_name = DB_NAME

            pymongo_module = _get_pymongo_module()
            if pymongo_module is None:
                safe_print("INFO: pymongo غير متاح - العمل بالبيانات المحلية فقط")
                with self._lock:
                    self.online = False
                    self._mongo_connecting = False
                return

            for attempt in range(max_retries):
                if self._closed or self._mongo_stop_event.is_set():
                    break
                try:
                    safe_print(f"INFO: محاولة الاتصال بـ MongoDB ({attempt + 1}/{max_retries})...")

                    mongo_client = pymongo_module.MongoClient(
                        mongo_uri,
                        serverSelectionTimeoutMS=5000,  # ⚡ 5 ثواني للاتصال
                        connectTimeoutMS=5000,
                        socketTimeoutMS=30000,  # ⚡ 30 ثانية للعمليات (زيادة لتجنب timeout)
                        **self._mongo_client_options(),
                    )

                    # اختبار الاتصال
                    mongo_client.server_info()
                    mongo_db = mongo_client[db_name]
                    with self._lock:
                        if self._closed:
                            try:
                                mongo_client.close()
                            except Exception:
                                pass
                            break
                        self.mongo_client = mongo_client
                        self.mongo_db = mongo_db
                        self.online = True
                        self._mongo_indexes_initialized = False
                    self._ensure_mongo_indexes_ready()
                    if self._closed:
                        break
                    safe_print("INFO: ✅ متصل بـ MongoDB بنجاح!")
                    break  # نجح الاتصال

                except Exception as e:
                    safe_print(f"WARNING: فشلت محاولة {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        if self._closed:
                            break
                        safe_print(f"INFO: إعادة المحاولة بعد {retry_delay} ثانية...")
                        if self._mongo_stop_event.wait(retry_delay):
                            break
                    else:
                        safe_print("WARNING: فشل الاتصال بـ MongoDB - العمل بالبيانات المحلية")
                        with self._lock:
                            self.online = False

            with self._lock:
                self._mongo_connecting = False

        # تشغيل الاتصال في thread منفصل
        thread = threading.Thread(
            target=connect_mongo,
            daemon=True,
            name="repository-mongo-connect",
        )
        self._mongo_connection_thread = thread
        thread.start()

    def _start_mongo_retry_loop(self):
        if os.environ.get("SKYWAVE_DISABLE_MONGO") == "1" or os.environ.get("PYTEST_CURRENT_TEST"):
            return
        if self._mongo_retry_thread_started:
            return
        self._mongo_retry_thread_started = True

        def retry_loop():
            while not self._mongo_stop_event.wait(self._mongo_retry_interval_seconds):
                if self._closed:
                    return
                if self.online:
                    continue
                if self._mongo_connecting:
                    continue
                try:
                    self._start_mongo_connection()
                except Exception:
                    pass

        thread = threading.Thread(
            target=retry_loop,
            daemon=True,
            name="repository-mongo-retry",
        )
        self._mongo_retry_thread = thread
        thread.start()

    def _init_local_db(self):
        """دالة داخلية تنشئ كل الجداول في ملف SQLite المحلي فقط إذا لم تكن موجودة."""
        safe_print("INFO: جاري فحص الجداول المحلية (SQLite)...")
        sync_tables = self._sync_aware_tables()

        if not self._sqlite_bootstrap_required():
            safe_print(
                "INFO: [Repository] SQLite bootstrap up-to-date - skipping heavy schema work."
            )
            self._run_sync_state_maintenance(sync_tables)
            safe_print("INFO: الجداول المحلية جاهزة.")
            if self.online:
                self._ensure_mongo_indexes_ready()
            return

        # جدول الحسابات (accounts)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )

        # Migration: إضافة الأعمدة الناقصة للجداول القديمة
        try:
            self.sqlite_cursor.execute(
                "ALTER TABLE accounts ADD COLUMN currency TEXT DEFAULT 'EGP'"
            )
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
        self.sqlite_cursor.execute(
            """
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
        )"""
        )

        # Migration: إضافة عمود payment_account_id للجداول القديمة
        try:
            self.sqlite_cursor.execute("ALTER TABLE expenses ADD COLUMN payment_account_id TEXT")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل

        # Migration: إضافة عمود status_manually_set للمشاريع
        try:
            self.sqlite_cursor.execute(
                "ALTER TABLE projects ADD COLUMN status_manually_set INTEGER DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل

        # Migration: إضافة عمود invoice_number للمشاريع (رقم الفاتورة الثابت)
        try:
            self.sqlite_cursor.execute("ALTER TABLE projects ADD COLUMN invoice_number TEXT")
            self.sqlite_conn.commit()
            safe_print("INFO: [Repository] تم إضافة عمود invoice_number لجدول المشاريع")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل

        # ==================== Enterprise Migrations ====================
        # Migration: إضافة أعمدة Enterprise للمشاريع
        enterprise_columns = [
            ("project_code", "TEXT"),  # كود المشروع الذكي
            ("sequence_number", "INTEGER DEFAULT 0"),  # الرقم التسلسلي
            ("cost_center_id", "TEXT"),  # مركز التكلفة
            ("contract_type", "TEXT DEFAULT 'مرة واحدة'"),  # نوع العقد
            ("is_retainer", "INTEGER DEFAULT 0"),  # هل عقد متكرر
            ("renewal_cycle", "TEXT"),  # دورة التجديد
            ("next_renewal_date", "TEXT"),  # تاريخ التجديد القادم
            ("milestones", "TEXT"),  # الدفعات المرحلية (JSON)
            ("total_estimated_cost", "REAL DEFAULT 0.0"),  # التكلفة التقديرية
            ("estimated_profit", "REAL DEFAULT 0.0"),  # الربح المتوقع
            ("profit_margin", "REAL DEFAULT 0.0"),  # هامش الربح
            ("project_manager_id", "TEXT"),  # مدير المشروع
        ]

        for col_name, col_type in enterprise_columns:
            try:
                self.sqlite_cursor.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")
                safe_print(f"INFO: [Repository] ✅ تم إضافة عمود {col_name} لجدول المشاريع")
            except sqlite3.OperationalError:
                pass  # العمود موجود بالفعل

        self.sqlite_conn.commit()

        # ⚡ جدول الدفعات المرحلية (project_milestones)
        self.sqlite_cursor.execute(
            """
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
            created_at TEXT NOT NULL
        )
        """
        )
        self.sqlite_conn.commit()
        safe_print("INFO: [Repository] ✅ جدول الدفعات المرحلية جاهز")

        # ⚡ جدول أرقام الفواتير الثابتة (مرتبط باسم المشروع وليس الـ ID)
        self.sqlite_cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS invoice_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT UNIQUE,
            project_name TEXT NOT NULL,
            invoice_number TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
        """
        )
        self.sqlite_conn.commit()
        self._migrate_invoice_numbers_table_use_project_ids()

        # ⚡ Migration: توليد أرقام فواتير للمشاريع القديمة اللي مش عندها invoice_number
        if self._table_exists("projects") and self._table_exists("invoice_numbers"):
            try:
                # جلب المشاريع اللي مش عندها رقم فاتورة
                self.sqlite_cursor.execute(
                    """
                    SELECT p.id, p.name FROM projects p
                    WHERE p.invoice_number IS NULL OR p.invoice_number = ''
                """
                )
                projects_without_invoice = self.sqlite_cursor.fetchall()

                if projects_without_invoice:
                    safe_print(
                        f"INFO: [Repository] توليد أرقام فواتير لـ {len(projects_without_invoice)} مشروع..."
                    )

                    for row in projects_without_invoice:
                        project_id = row[0]
                        project_name = row[1]
                        invoice_number = self.ensure_invoice_number(str(project_id))
                        if invoice_number:
                            safe_print(
                                f"  ✓ تم تثبيت رقم فاتورة: {project_name} -> {invoice_number}"
                            )

                    self.sqlite_conn.commit()
                    safe_print(
                        f"INFO: [Repository] ✅ تم توليد أرقام فواتير لـ {len(projects_without_invoice)} مشروع"
                    )
            except Exception as e:
                safe_print(f"WARNING: [Repository] فشل توليد أرقام الفواتير: {e}")

        # جدول العملاء (clients)
        self.sqlite_cursor.execute(
            """
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
            has_logo INTEGER NOT NULL DEFAULT 0,
            logo_last_synced TEXT,
            client_notes TEXT,
            is_vip INTEGER DEFAULT 0
        )"""
        )

        # إضافة عمود logo_data إذا لم يكن موجوداً (للتوافق مع قواعد البيانات القديمة)
        try:
            self.sqlite_cursor.execute("ALTER TABLE clients ADD COLUMN logo_data TEXT")
            self.sqlite_conn.commit()
            safe_print("INFO: [Repository] تم إضافة عمود logo_data لجدول العملاء")
        except Exception:
            pass  # العمود موجود بالفعل

        # ⚡ إضافة أعمدة metadata للشعار (دعم Lazy Logo Sync)
        try:
            self.sqlite_cursor.execute(
                "ALTER TABLE clients ADD COLUMN has_logo INTEGER NOT NULL DEFAULT 0"
            )
            self.sqlite_conn.commit()
            safe_print("INFO: [Repository] تم إضافة عمود has_logo لجدول العملاء")
        except Exception:
            pass  # العمود موجود بالفعل

        try:
            self.sqlite_cursor.execute("ALTER TABLE clients ADD COLUMN logo_last_synced TEXT")
            self.sqlite_conn.commit()
            safe_print("INFO: [Repository] تم إضافة عمود logo_last_synced لجدول العملاء")
        except Exception:
            pass  # العمود موجود بالفعل

        # ⚡ إضافة عمود is_vip للعملاء المميزين
        try:
            self.sqlite_cursor.execute("ALTER TABLE clients ADD COLUMN is_vip INTEGER DEFAULT 0")
            self.sqlite_conn.commit()
            safe_print("INFO: [Repository] تم إضافة عمود is_vip لجدول العملاء")
        except Exception:
            pass  # العمود موجود بالفعل

        # جدول الخدمات (services)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )

        # جدول الفواتير (invoices)
        # (البنود 'items' هتتخزن كـ JSON text)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )

        # جدول المشاريع (projects) (معدل بالكامل)
        self.sqlite_cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            name TEXT NOT NULL,
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
            exchange_rate_snapshot REAL DEFAULT 1.0,
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
        )"""
        )
        self._migrate_projects_table_remove_global_name_unique()
        if not self._table_has_column("projects", "exchange_rate_snapshot"):
            self.sqlite_cursor.execute(
                "ALTER TABLE projects ADD COLUMN exchange_rate_snapshot REAL DEFAULT 1.0"
            )
            self.sqlite_conn.commit()
            self._sqlite_table_columns_cache.pop("projects", None)

        # جدول قيود اليومية (journal_entries)
        # (البنود 'lines' هتتخزن كـ JSON text)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )

        # جدول الدفعات (payments)
        self.sqlite_cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            project_id TEXT NOT NULL,
            client_id TEXT NOT NULL,
            invoice_number TEXT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            account_id TEXT NOT NULL,
            method TEXT
        )"""
        )

        try:
            self.sqlite_cursor.execute("ALTER TABLE payments ADD COLUMN invoice_number TEXT")
        except sqlite3.OperationalError:
            pass

        # جدول العملات (currencies)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )

        # جدول الإشعارات (notifications)
        self.sqlite_cursor.execute(
            """
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
            expires_at TEXT,
            action TEXT,
            operation_text TEXT,
            details TEXT DEFAULT '',
            amount REAL,
            is_activity INTEGER DEFAULT 0
        )"""
        )
        try:
            self.sqlite_cursor.execute("ALTER TABLE notifications ADD COLUMN action TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.sqlite_cursor.execute("ALTER TABLE notifications ADD COLUMN operation_text TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.sqlite_cursor.execute(
                "ALTER TABLE notifications ADD COLUMN details TEXT DEFAULT ''"
            )
        except sqlite3.OperationalError:
            pass
        try:
            self.sqlite_cursor.execute("ALTER TABLE notifications ADD COLUMN amount REAL")
        except sqlite3.OperationalError:
            pass
        try:
            self.sqlite_cursor.execute(
                "ALTER TABLE notifications ADD COLUMN is_activity INTEGER DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass

        # جدول سجل النشاطات (activity_logs)
        self.sqlite_cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            operation_text TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            details TEXT DEFAULT '',
            amount REAL
        )"""
        )

        # جدول المستخدمين (users)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )

        # Migration: إضافة عمود custom_permissions للجداول القديمة
        try:
            self.sqlite_cursor.execute("ALTER TABLE users ADD COLUMN custom_permissions TEXT")
        except sqlite3.OperationalError:
            pass  # العمود موجود بالفعل

        # جدول الموظفين (employees) - نظام الموارد البشرية
        self.sqlite_cursor.execute(
            """
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
        )"""
        )
        self.sqlite_conn.commit()
        safe_print("INFO: [Repository] ✅ جدول الموظفين جاهز")

        # جدول سلف الموظفين (employee_loans)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )
        self.sqlite_conn.commit()
        safe_print("INFO: [Repository] ✅ جدول سلف الموظفين جاهز")

        # جدول مرتبات الموظفين (employee_salaries)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )
        self.sqlite_conn.commit()
        safe_print("INFO: [Repository] ✅ جدول مرتبات الموظفين جاهز")

        # جدول حضور الموظفين (employee_attendance)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )
        self.sqlite_conn.commit()
        safe_print("INFO: [Repository] ✅ جدول حضور الموظفين جاهز")

        # جدول إجازات الموظفين (employee_leaves)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )
        self.sqlite_conn.commit()
        safe_print("INFO: [Repository] ✅ جدول إجازات الموظفين جاهز")

        # جدول أقساط السلف (loan_payments)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )
        self.sqlite_conn.commit()
        safe_print("INFO: [Repository] ✅ جدول أقساط السلف جاهز")

        # جدول عروض الأسعار (quotations) - نظام العروض
        self.sqlite_cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS quotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            quotation_number TEXT UNIQUE NOT NULL,
            client_id TEXT NOT NULL,
            client_name TEXT,
            issue_date TEXT NOT NULL,
            valid_until TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            scope_of_work TEXT,
            items TEXT,
            subtotal REAL DEFAULT 0.0,
            discount_rate REAL DEFAULT 0.0,
            discount_amount REAL DEFAULT 0.0,
            tax_rate REAL DEFAULT 0.0,
            tax_amount REAL DEFAULT 0.0,
            total_amount REAL DEFAULT 0.0,
            currency TEXT DEFAULT 'EGP',
            status TEXT DEFAULT 'مسودة',
            terms_and_conditions TEXT,
            payment_terms TEXT,
            delivery_time TEXT,
            warranty TEXT,
            notes TEXT,
            internal_notes TEXT,
            converted_to_project_id TEXT,
            conversion_date TEXT,
            sent_date TEXT,
            viewed_date TEXT,
            response_date TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )"""
        )
        try:
            self.sqlite_cursor.execute(
                "ALTER TABLE quotations ADD COLUMN dirty_flag INTEGER DEFAULT 0"
            )
        except Exception:
            pass
        try:
            self.sqlite_cursor.execute(
                "ALTER TABLE quotations ADD COLUMN is_deleted INTEGER DEFAULT 0"
            )
        except Exception:
            pass
        self.sqlite_conn.commit()
        safe_print("INFO: [Repository] ✅ جدول عروض الأسعار جاهز")

        # جدول المهام (tasks) - نظام TODO
        self.sqlite_cursor.execute(
            """
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
            FOREIGN KEY (related_client_id) REFERENCES clients(id)
        )"""
        )

        # إضافة حقل is_archived إذا لم يكن موجوداً (للتوافق مع قواعد البيانات القديمة)
        try:
            self.sqlite_cursor.execute("ALTER TABLE tasks ADD COLUMN is_archived INTEGER DEFAULT 0")
        except Exception:
            pass  # الحقل موجود بالفعل

        # جدول قائمة انتظار المزامنة (sync_queue)
        self.sqlite_cursor.execute(
            """
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
        )"""
        )

        # إضافة عمود action إذا لم يكن موجوداً (للتوافق مع الإصدارات القديمة)
        try:
            self.sqlite_cursor.execute("ALTER TABLE sync_queue ADD COLUMN action TEXT")
            self.sqlite_conn.commit()
            safe_print("INFO: [Repository] Added 'action' column to sync_queue table")
        except Exception:
            # العمود موجود بالفعل أو خطأ آخر
            pass

        # إنشاء indexes لتحسين أداء sync_queue
        self.sqlite_cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_sync_queue_status
        ON sync_queue(status)
        """
        )

        self.sqlite_cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_sync_queue_priority
        ON sync_queue(priority, status)
        """
        )

        self.sqlite_cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_sync_queue_entity
        ON sync_queue(entity_type, entity_id)
        """
        )

        self.sqlite_conn.commit()

        # ==================== Smart Migration & Sanitation ====================
        # إضافة أعمدة المزامنة لجميع الجداول الرئيسية مع تنظيف البيانات القديمة
        # is_deleted: للحذف الناعم (Soft Delete)
        # dirty_flag: لتعقب التغييرات المحلية غير المتزامنة
        # last_modified: آخر تعديل للمزامنة
        # _mongo_id: معرف MongoDB
        sync_tables = self._sync_aware_tables()

        for table in sync_tables:
            # 1. إضافة عمود is_deleted (للحذف الناعم)
            try:
                self.sqlite_cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN is_deleted INTEGER DEFAULT 0"
                )
                safe_print(f"INFO: [Repository] ✅ تم إضافة عمود is_deleted لجدول {table}")
            except sqlite3.OperationalError:
                pass  # العمود موجود بالفعل

            # 2. إضافة عمود dirty_flag (لتعقب التغييرات المحلية)
            try:
                self.sqlite_cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN dirty_flag INTEGER DEFAULT 0"
                )
                safe_print(f"INFO: [Repository] ✅ تم إضافة عمود dirty_flag لجدول {table}")
            except sqlite3.OperationalError:
                pass  # العمود موجود بالفعل

            # 3. إضافة عمود last_modified إذا لم يكن موجوداً
            try:
                self.sqlite_cursor.execute(f"ALTER TABLE {table} ADD COLUMN last_modified TEXT")
                safe_print(f"INFO: [Repository] ✅ تم إضافة عمود last_modified لجدول {table}")
            except sqlite3.OperationalError:
                pass  # العمود موجود بالفعل

            # 4. إضافة عمود _mongo_id إذا لم يكن موجوداً
            try:
                self.sqlite_cursor.execute(f"ALTER TABLE {table} ADD COLUMN _mongo_id TEXT")
                safe_print(f"INFO: [Repository] ✅ تم إضافة عمود _mongo_id لجدول {table}")
            except sqlite3.OperationalError:
                pass  # العمود موجود بالفعل

            # 5. إضافة عمود sync_status إذا لم يكن موجوداً
            try:
                self.sqlite_cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN sync_status TEXT DEFAULT 'pending'"
                )
                safe_print(f"INFO: [Repository] ✅ تم إضافة عمود sync_status لجدول {table}")
            except sqlite3.OperationalError:
                pass  # العمود موجود بالفعل

        self.sqlite_conn.commit()

        # ==================== Legacy Data Wake-Up (CRITICAL) ====================
        # تنشيط البيانات القديمة: نضع dirty_flag = 1 لكل الصفوف الموجودة
        # هذا يجبر محرك المزامنة على رفعها إلى MongoDB
        safe_print("INFO: [Repository] 🔄 جاري تنشيط البيانات القديمة للمزامنة...")

        allowed_sync_tables = {str(table).strip() for table in sync_tables}
        for table in sync_tables:
            try:
                table_ref = self._quote_sqlite_identifier(table, allowed=allowed_sync_tables)
                # أي صف متزامن فعليًا لا يجب إيقاظه من جديد وإلا سيُعاد رفعه إلى Mongo.
                update_dirty_sql = f"""
                    UPDATE {table_ref}
                    SET dirty_flag = 1
                    WHERE dirty_flag IS NULL
                       OR (
                            dirty_flag = 0
                            AND (
                                is_deleted = 1
                                OR _mongo_id IS NULL
                                OR sync_status IS NULL
                                OR TRIM(sync_status) = ''
                                OR sync_status IN ('new_offline', 'modified_offline', 'pending', 'deleted')
                            )
                        )
                """  # nosec B608
                self.sqlite_cursor.execute(update_dirty_sql)
                updated_count = self.sqlite_cursor.rowcount
                if updated_count > 0:
                    safe_print(
                        f"INFO: [Repository] ⚡ تم تنشيط {updated_count} سجل في {table} للمزامنة"
                    )

                # تنظيف dirty_flag الخاطئ الذي كانت تتركه wake-up القديمة على الصفوف المتزامنة.
                clear_false_dirty_sql = f"""
                    UPDATE {table_ref}
                    SET dirty_flag = 0
                    WHERE dirty_flag = 1
                      AND (_mongo_id IS NOT NULL AND TRIM(_mongo_id) != '')
                      AND COALESCE(sync_status, '') = 'synced'
                      AND COALESCE(is_deleted, 0) = 0
                """  # nosec B608
                self.sqlite_cursor.execute(clear_false_dirty_sql)
                cleaned_count = self.sqlite_cursor.rowcount
                if cleaned_count > 0:
                    safe_print(
                        f"INFO: [Repository] 🧯 تم تنظيف {cleaned_count} سجل متزامن في {table}"
                    )
            except sqlite3.OperationalError as e:
                safe_print(f"WARNING: [Repository] فشل تنشيط {table}: {e}")

        self.sqlite_conn.commit()

        # ==================== Sanitize Defaults ====================
        # تنظيف القيم الفارغة: وضع قيم افتراضية للحقول NULL
        safe_print("INFO: [Repository] 🧹 جاري تنظيف القيم الفارغة...")

        for table in sync_tables:
            try:
                table_ref = self._quote_sqlite_identifier(table, allowed=allowed_sync_tables)
                # تنظيف is_deleted: وضع 0 بدلاً من NULL
                reset_delete_flag_sql = (
                    f"UPDATE {table_ref} SET is_deleted = 0 WHERE is_deleted IS NULL"  # nosec B608
                )
                self.sqlite_cursor.execute(reset_delete_flag_sql)

                # تنظيف sync_status: وضع 'pending' بدلاً من NULL
                reset_sync_status_sql = f"UPDATE {table_ref} SET sync_status = 'pending' WHERE sync_status IS NULL"  # nosec B608
                self.sqlite_cursor.execute(reset_sync_status_sql)

                # تنظيف last_modified: وضع التاريخ الحالي بدلاً من NULL
                now_iso = datetime.now().isoformat()
                reset_last_modified_sql = f"UPDATE {table_ref} SET last_modified = ? WHERE last_modified IS NULL"  # nosec B608
                self.sqlite_cursor.execute(reset_last_modified_sql, (now_iso,))
            except sqlite3.OperationalError as e:
                safe_print(f"WARNING: [Repository] فشل تنظيف {table}: {e}")

        self._migrate_project_reference_tables_remove_name_foreign_keys()
        self.sqlite_conn.commit()
        safe_print("INFO: [Repository] ✅ Smart Migration & Sanitation complete!")
        # ==================== End Smart Migration ====================

        safe_print("INFO: الجداول المحلية جاهزة.")

        # ⚡ إنشاء indexes لتحسين الأداء (مهم جداً للسرعة)
        self._create_sqlite_indexes()

        # ⚡ تحسين قاعدة البيانات للأداء
        self._optimize_sqlite_performance()
        self._set_sqlite_user_version(_SQLITE_BOOTSTRAP_VERSION)

        # إنشاء collection و indexes في MongoDB إذا كان متصل
        if self.online:
            self._ensure_mongo_indexes_ready()

    def _create_sqlite_indexes(self):
        """
        إنشاء indexes في SQLite لتحسين الأداء
        """
        try:
            safe_print("INFO: جاري إنشاء indexes في SQLite...")

            # Indexes لـ clients
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status)"
            )

            # Indexes لـ projects
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_projects_start_date ON projects(start_date)"
            )

            # Indexes لـ journal_entries
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(date)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_journal_related ON journal_entries(related_document_id)"
            )

            # Indexes لـ expenses
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(project_id)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_account ON expenses(account_id)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_payment_account ON expenses(payment_account_id)"
            )

            # Indexes لـ invoices
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status)"
            )

            # Indexes لـ payments
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_payments_project ON payments(project_id)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(date)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_payments_account ON payments(account_id)"
            )

            # إعادة بناء unique indexes بصيغة تستبعد الصفوف المحذوفة/المؤرشفة.
            for index_name in (
                "idx_clients_name_unique",
                "idx_projects_name",
                "idx_projects_name_client_unique",
                "idx_clients_name",
                "idx_services_name",
                "idx_services_name_unique",
                "idx_payments_unique",
            ):
                try:
                    self.sqlite_cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
                except Exception:
                    pass

            try:
                self.sqlite_cursor.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_name_unique
                    ON clients(LOWER(name))
                    WHERE status != 'مؤرشف'
                    AND (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    """
                )
            except Exception:
                pass

            try:
                self.sqlite_cursor.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_name_client_unique
                    ON projects(LOWER(name), client_id)
                    WHERE status != 'مؤرشف'
                    AND (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    """
                )
            except Exception:
                pass

            try:
                self.sqlite_cursor.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_services_name_unique
                    ON services(LOWER(name))
                    WHERE status != 'مؤرشف'
                    AND (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    """
                )
            except Exception:
                pass

            try:
                self.sqlite_cursor.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_unique
                    ON payments(project_id, substr(date, 1, 10), ROUND(amount, 2))
                    WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    """
                )
            except Exception:
                pass

            # Indexes لـ notifications
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_notifications_activity_created ON notifications(is_activity, created_at)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_logs_created ON activity_logs(created_at)"
            )
            self.sqlite_cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_logs_entity ON activity_logs(entity_type, action)"
            )

            sync_tables = [
                "accounts",
                "clients",
                "services",
                "projects",
                "invoices",
                "payments",
                "expenses",
                "journal_entries",
                "currencies",
                "notifications",
                "tasks",
                "users",
            ]
            for table in sync_tables:
                try:
                    self.sqlite_cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{table}_sync_status ON {table}(sync_status)"
                    )
                except Exception:
                    pass
                try:
                    self.sqlite_cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{table}_dirty_flag ON {table}(dirty_flag)"
                    )
                except Exception:
                    pass
                try:
                    self.sqlite_cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{table}_mongo_ref ON {table}(_mongo_id)"
                    )
                except Exception:
                    pass
                try:
                    self.sqlite_cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{table}_last_modified ON {table}(last_modified)"
                    )
                except Exception:
                    pass
                try:
                    self.sqlite_cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{table}_sync_scan "
                        f"ON {table}(sync_status, dirty_flag, _mongo_id, last_modified)"
                    )
                except Exception:
                    pass

            self.sqlite_cursor.execute("PRAGMA optimize")
            self.sqlite_conn.commit()
            safe_print("INFO: تم إنشاء indexes في SQLite بنجاح.")
        except Exception as e:
            safe_print(f"WARNING: فشل إنشاء بعض indexes في SQLite: {e}")

    def _optimize_sqlite_performance(self):
        """
        ⚡ تحسين أداء SQLite للسرعة القصوى
        """
        try:
            safe_print("INFO: جاري تحسين أداء قاعدة البيانات...")

            # تفعيل WAL mode للأداء الأفضل
            self.sqlite_cursor.execute("PRAGMA journal_mode=WAL")

            # زيادة حجم الـ cache
            self.sqlite_cursor.execute("PRAGMA cache_size=20000")

            # تفعيل memory-mapped I/O
            self.sqlite_cursor.execute("PRAGMA mmap_size=536870912")  # 512MB

            # تحسين synchronous mode
            self.sqlite_cursor.execute("PRAGMA synchronous=NORMAL")

            # تفعيل temp store في الذاكرة
            self.sqlite_cursor.execute("PRAGMA temp_store=MEMORY")
            self.sqlite_cursor.execute("PRAGMA wal_autocheckpoint=1000")
            self.sqlite_cursor.execute("PRAGMA optimize")

            self.sqlite_conn.commit()
            safe_print("INFO: تم تحسين أداء قاعدة البيانات بنجاح.")
        except Exception as e:
            safe_print(f"WARNING: فشل تحسين أداء قاعدة البيانات: {e}")

    def _init_mongo_indexes(self) -> bool:
        """
        إنشاء indexes في MongoDB لتحسين الأداء
        """
        with self._lock:
            if self._closed or self.mongo_db is None:
                return False
            mongo_db = self.mongo_db

        try:
            safe_print("INFO: جاري إنشاء indexes في MongoDB...")

            # sync_queue
            mongo_db.sync_queue.create_index([("status", 1)])
            mongo_db.sync_queue.create_index([("priority", 1), ("status", 1)])
            mongo_db.sync_queue.create_index([("entity_type", 1), ("entity_id", 1)])
            mongo_db.sync_queue.create_index([("created_at", -1)])
            mongo_db.sync_queue.create_index([("updated_at", -1)])

            # projects / clients
            mongo_db.projects.create_index([("client_id", 1)])
            mongo_db.projects.create_index([("status", 1)])
            mongo_db.projects.create_index([("start_date", -1)])
            mongo_db.projects.create_index([("last_modified", -1)])
            mongo_db.clients.create_index([("name", 1)])
            mongo_db.clients.create_index([("status", 1)])
            mongo_db.clients.create_index([("phone", 1)])
            mongo_db.clients.create_index([("last_modified", -1)])

            # accounting collections
            mongo_db.accounts.create_index([("code", 1)])
            mongo_db.accounts.create_index([("type", 1)])
            mongo_db.accounts.create_index([("last_modified", -1)])
            mongo_db.invoices.create_index([("invoice_number", 1)])
            mongo_db.invoices.create_index([("client_id", 1)])
            mongo_db.invoices.create_index([("status", 1)])
            mongo_db.invoices.create_index([("issue_date", -1)])
            mongo_db.invoices.create_index([("last_modified", -1)])
            mongo_db.payments.create_index([("project_id", 1)])
            mongo_db.payments.create_index([("client_id", 1)])
            mongo_db.payments.create_index([("invoice_number", 1)])
            mongo_db.payments.create_index([("date", -1)])
            mongo_db.payments.create_index([("account_id", 1)])
            mongo_db.payments.create_index([("last_modified", -1)])
            mongo_db.journal_entries.create_index([("date", -1)])
            mongo_db.journal_entries.create_index([("related_document_id", 1)])
            mongo_db.journal_entries.create_index([("last_modified", -1)])
            mongo_db.expenses.create_index([("date", -1)])
            mongo_db.expenses.create_index([("project_id", 1)])
            mongo_db.expenses.create_index([("account_id", 1)])
            mongo_db.expenses.create_index([("payment_account_id", 1)])
            mongo_db.expenses.create_index([("last_modified", -1)])

            # ui-driven collections
            mongo_db.notifications.create_index([("is_read", 1)])
            mongo_db.notifications.create_index([("type", 1)])
            mongo_db.notifications.create_index([("created_at", -1)])
            mongo_db.notifications.create_index([("expires_at", 1)])
            mongo_db.notifications.create_index([("entity_type", 1), ("created_at", -1)])
            mongo_db.tasks.create_index([("status", 1)])
            mongo_db.tasks.create_index([("due_date", 1)])
            mongo_db.tasks.create_index([("last_modified", -1)])
            mongo_db.users.create_index([("username", 1)])
            mongo_db.users.create_index([("last_modified", -1)])
            mongo_db.currencies.create_index([("code", 1)])
            mongo_db.currencies.create_index([("active", 1)])

            safe_print("INFO: تم إنشاء indexes في MongoDB بنجاح.")
            return True
        except Exception as e:
            safe_print(f"WARNING: فشل إنشاء بعض indexes في MongoDB: {e}")
            return False

    def is_online(self) -> bool:
        """دالة بسيطة لمعرفة حالة الاتصال"""
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
            raise ValueError(f"العميل '{client_data.name}' موجود بالفعل في النظام")

        # ✅ فحص التكرار بالاسم (case insensitive)
        similar_client = self._get_similar_client(client_data.name)
        if similar_client:
            safe_print(f"WARNING: يوجد عميل مشابه '{similar_client.name}'!")
            raise ValueError(f"يوجد عميل مشابه بالاسم '{similar_client.name}'")

        # ✅ فحص التكرار بالهاتف أيضاً
        if client_data.phone:
            existing_by_phone = self._get_client_by_phone(client_data.phone)
            if existing_by_phone:
                safe_print(f"WARNING: العميل برقم الهاتف '{client_data.phone}' موجود بالفعل!")
                raise ValueError(f"يوجد عميل آخر بنفس رقم الهاتف '{client_data.phone}'")

        now = datetime.now()
        client_data.created_at = now
        client_data.last_modified = now
        client_data.sync_status = "new_offline"
        client_data.status = schemas.ClientStatus.ACTIVE
        has_logo = bool(getattr(client_data, "has_logo", False) or client_data.logo_data)
        client_data.has_logo = has_logo
        if has_logo and not getattr(client_data, "logo_last_synced", None):
            client_data.logo_last_synced = now.isoformat()

        # 1. الحفظ في SQLite (الأوفلاين أولاً)
        sql = """
            INSERT INTO clients (
                sync_status, created_at, last_modified, name, company_name, email,
                phone, address, country, vat_number, status,
                client_type, work_field, logo_path, logo_data, has_logo, logo_last_synced,
                client_notes, is_vip, dirty_flag, is_deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
        """
        # ⚡ تحويل is_vip إلى 0 أو 1 لـ SQLite
        is_vip_value = 1 if getattr(client_data, "is_vip", False) else 0
        has_logo_value = 1 if has_logo else 0
        self.sqlite_cursor.execute(
            sql,
            (
                client_data.sync_status,
                now,
                now,
                client_data.name,
                client_data.company_name,
                client_data.email,
                client_data.phone,
                client_data.address,
                client_data.country,
                client_data.vat_number,
                client_data.status.value,
                client_data.client_type,
                client_data.work_field,
                client_data.logo_path,
                client_data.logo_data,
                has_logo_value,
                client_data.logo_last_synced,
                client_data.client_notes,
                is_vip_value,
            ),
        )
        self.sqlite_conn.commit()

        local_id = self.sqlite_cursor.lastrowid
        client_data.id = local_id  # ⚡ تعيين الـ ID للعميل المُنشأ
        safe_print(f"INFO: تم حفظ العميل '{client_data.name}' محلياً (ID: {local_id}).")

        # 2. محاولة الحفظ في MongoDB (الأونلاين)
        if self.online:
            try:
                # نحول الـ Pydantic model لـ dict عشان Mongo يفهمه
                client_dict = client_data.model_dump(exclude={"_mongo_id"})

                # ⚡ التأكد من حفظ logo_data بشكل صحيح
                if client_data.logo_data:
                    client_dict["logo_data"] = client_data.logo_data
                    safe_print(
                        f"INFO: [Repo] حفظ logo_data ({len(client_data.logo_data)} حرف) في MongoDB"
                    )

                result = self.mongo_db.clients.insert_one(client_dict)
                mongo_id = str(result.inserted_id)

                # تحديث الـ SQLite بالـ Mongo ID وتغيير الحالة لـ 'synced'
                client_data._mongo_id = mongo_id
                client_data.sync_status = "synced"

                self.sqlite_cursor.execute(
                    "UPDATE clients SET _mongo_id = ?, sync_status = ?, dirty_flag = 0 WHERE id = ?",
                    (mongo_id, "synced", local_id),
                )
                self.sqlite_conn.commit()
                safe_print(
                    f"INFO: تم مزامنة العميل '{client_data.name}' أونلاين (Mongo ID: {mongo_id})."
                )

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
                    has_logo = ?, logo_last_synced = ?, is_vip = ?, last_modified = ?, sync_status = 'modified_offline',
                    dirty_flag = 1
                WHERE id = ? OR _mongo_id = ?
            """
            # ⚡ تحويل is_vip إلى 0 أو 1 لـ SQLite
            is_vip_value = 1 if getattr(client_data, "is_vip", False) else 0
            has_logo_value = (
                1 if bool(getattr(client_data, "has_logo", False) or client_data.logo_data) else 0
            )
            params = (
                client_data.name,
                client_data.company_name,
                client_data.email,
                client_data.phone,
                client_data.address,
                client_data.country,
                client_data.vat_number,
                client_data.status.value,
                client_data.client_type,
                client_data.work_field,
                client_data.logo_path,
                client_data.logo_data,
                client_data.client_notes,
                has_logo_value,
                client_data.logo_last_synced,
                is_vip_value,
                now_iso,
                client_id,
                client_id,
            )
            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
            safe_print(f"DEBUG: [Repo] تم تحديث is_vip = {is_vip_value} للعميل {client_id}")

            # ⚡ إبطال الـ cache بعد التحديث
            if CACHE_ENABLED and hasattr(self, "_clients_cache"):
                self._clients_cache.invalidate()
                safe_print("INFO: ⚡ تم إبطال cache العملاء بعد التحديث")

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث العميل (SQLite): {e}")
            return None

        if self.online:
            try:
                update_dict = client_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                update_dict["last_modified"] = now_dt
                update_dict["status"] = client_data.status.value
                self.sqlite_cursor.execute(
                    "SELECT id, _mongo_id FROM clients WHERE id = ? OR _mongo_id = ?",
                    (client_id, client_id),
                )
                row = self.sqlite_cursor.fetchone()
                local_client_id = row["id"] if row else client_id
                mongo_client_id = str(
                    (
                        row["_mongo_id"]
                        if row and row["_mongo_id"]
                        else getattr(client_data, "_mongo_id", None) or client_id
                    )
                    or ""
                ).strip()

                # ⚡ التعامل الذكي مع logo_data
                logo_data_value = client_data.logo_data
                logo_path_value = client_data.logo_path

                if logo_data_value:
                    # صورة جديدة - رفعها للسحابة
                    update_dict["logo_data"] = logo_data_value
                    update_dict["has_logo"] = True
                    update_dict["logo_last_synced"] = now_iso
                    safe_print(
                        f"INFO: [Repo] � حفظ logo_data ({len(logo_data_value)} حرف) في MongoDB"
                    )
                elif not logo_path_value:
                    # logo_data فارغ و logo_path فارغ = حذف صريح للصورة
                    update_dict["logo_data"] = ""
                    update_dict["logo_path"] = ""
                    update_dict["has_logo"] = False
                    update_dict["logo_last_synced"] = now_iso
                    safe_print("INFO: [Repo] 🗑️ حذف logo_data من MongoDB (حذف صريح)")
                else:
                    # logo_data فارغ لكن logo_path موجود = الاحتفاظ بالقديم
                    try:
                        existing = self.mongo_db.clients.find_one(
                            {
                                "$or": [
                                    {"_id": self._to_objectid(mongo_client_id)},
                                    {"_id": self._to_objectid(client_id)},
                                    {"_mongo_id": mongo_client_id},
                                    {"_mongo_id": client_id},
                                    {"id": local_client_id},
                                ]
                            },
                            {"logo_data": 1},
                        )
                        if existing and existing.get("logo_data"):
                            del update_dict["logo_data"]
                            update_dict["has_logo"] = True
                            safe_print("INFO: [Repo] 📷 الاحتفاظ بـ logo_data الموجود في MongoDB")
                        else:
                            update_dict["has_logo"] = bool(client_data.has_logo)
                    except Exception:
                        pass

                # Revive a deleted remote document when the local edit wins.
                update_dict["sync_status"] = "synced"
                update_dict["is_deleted"] = False

                result = self.mongo_db.clients.update_one(
                    {
                        "$or": [
                            {"_id": self._to_objectid(mongo_client_id)},
                            {"_id": self._to_objectid(client_id)},
                            {"_mongo_id": mongo_client_id},
                            {"_mongo_id": client_id},
                            {"id": local_client_id},
                        ]
                    },
                    {"$set": update_dict},
                )

                if result and (
                    getattr(result, "matched_count", 0) > 0
                    or getattr(result, "modified_count", 0) > 0
                ):
                    self.sqlite_cursor.execute(
                        """
                        UPDATE clients
                        SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
                        WHERE id = ? OR _mongo_id = ?
                        """,
                        (local_client_id, mongo_client_id),
                    )
                    self.sqlite_conn.commit()
                    safe_print(f"INFO: [Repo] تم مزامنة تحديث العميل ID: {client_id} أونلاين.")

            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل تحديث العميل (Mongo): {e}")

        return client_data

    def get_all_clients(self) -> list[schemas.Client]:
        """
        ⚡ جلب كل العملاء النشطين (SQLite أولاً للسرعة) - مع Cache ذكي
        """
        # ⚡ استخدام الـ cache إذا كان متاحاً
        if CACHE_ENABLED and hasattr(self, "_clients_cache"):
            cached_result = self._clients_cache.get("all_clients")
            if cached_result is not None:
                safe_print(f"INFO: ⚡ تم جلب {len(cached_result)} عميل من الـ Cache")
                return cached_result

        active_status = schemas.ClientStatus.ACTIVE.value

        # ⚡ جلب من SQLite أولاً (سريع جداً) - استخدام cursor جديد لتجنب التعارض
        try:
            with self._lock:
                cursor = self.get_cursor()
                try:
                    cursor.execute(
                        """
                        SELECT * FROM clients
                        WHERE status = ?
                        AND (sync_status != 'deleted' OR sync_status IS NULL)
                        AND (is_deleted = 0 OR is_deleted IS NULL)
                        """,
                        (active_status,),
                    )
                    rows = cursor.fetchall()
                    clients_list = [schemas.Client(**dict(row)) for row in rows]
                finally:
                    cursor.close()

            # ⚡ حفظ في الـ cache
            if CACHE_ENABLED and hasattr(self, "_clients_cache"):
                self._clients_cache.set("all_clients", clients_list)

            # ⚡ تسجيل عدد العملاء اللي عندهم شعارات (metadata + data)
            clients_with_logo = sum(
                1 for c in clients_list if bool(getattr(c, "has_logo", False) or c.logo_data)
            )
            safe_print(
                f"INFO: تم جلب {len(clients_list)} عميل نشط من المحلي ({clients_with_logo} عميل لديه صورة)"
            )

            return clients_list
        except Exception as e:
            safe_print(f"ERROR: فشل جلب العملاء من SQLite: {e}")

        # Fallback إلى MongoDB إذا فشل SQLite
        if self.online:
            try:
                clients_data = list(
                    self.mongo_db.clients.find(
                        self._merge_active_filter_mongo({"status": active_status})
                    )
                )
                clients_list = []
                for c in clients_data:
                    try:
                        mongo_id = str(c.pop("_id"))
                        if "has_logo" not in c:
                            c["has_logo"] = bool(c.get("logo_data"))
                        c.pop("_mongo_id", None)
                        c.pop("mongo_id", None)
                        clients_list.append(schemas.Client(**c, _mongo_id=mongo_id))
                    except Exception:
                        continue

                # ⚡ حفظ في الـ cache
                if CACHE_ENABLED and hasattr(self, "_clients_cache"):
                    self._clients_cache.set("all_clients", clients_list)

                safe_print(f"INFO: تم جلب {len(clients_list)} عميل نشط من الأونلاين.")
                return clients_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب العملاء من MongoDB: {e}")

        return []

    def get_archived_clients(self) -> list[schemas.Client]:
        """جلب كل العملاء المؤرشفين فقط"""
        archived_status = schemas.ClientStatus.ARCHIVED.value
        if self.online:
            try:
                clients_data = list(
                    self.mongo_db.clients.find(
                        self._merge_active_filter_mongo({"status": archived_status})
                    )
                )
                clients_list = []
                for c in clients_data:
                    mongo_id = str(c.pop("_id"))
                    if "has_logo" not in c:
                        c["has_logo"] = bool(c.get("logo_data"))
                    c.pop("_mongo_id", None)
                    c.pop("mongo_id", None)
                    clients_list.append(schemas.Client(**c, _mongo_id=mongo_id))
                return clients_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب العملاء المؤرشفين (Mongo): {e}.")

        self.sqlite_cursor.execute(
            f"""
            SELECT * {self._is_active_filter_sql('clients')}
            AND status = ?
            """,
            (archived_status,),
        )
        rows = self.sqlite_cursor.fetchall()
        return [schemas.Client(**dict(row)) for row in rows]

    def get_client_by_id(self, client_id: str) -> schemas.Client | None:
        """جلب عميل واحد بالـ ID (بذكاء)"""
        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"SELECT * {self._is_active_filter_sql('clients')} AND (id = ? OR _mongo_id = ? OR name = ?)",
                        (client_id, client_id, client_id),
                    )
                    row = cursor.fetchone()
                finally:
                    cursor.close()
            if row:
                client = schemas.Client(**dict(row))
                safe_print(f"INFO: تم جلب العميل (ID: {client_id}) من المحلي.")
                return client
        except Exception as e:
            safe_print(f"ERROR: فشل جلب العميل (ID: {client_id}) من المحلي: {e}.")

        if self.online:
            try:
                lookup_id = self._to_objectid(client_id)
                client_data = self.mongo_db.clients.find_one(
                    self._merge_active_filter_mongo({"_id": lookup_id})
                )
                if client_data:
                    mongo_id = str(client_data.pop("_id"))
                    if "has_logo" not in client_data:
                        client_data["has_logo"] = bool(client_data.get("logo_data"))
                    client_data.pop("_mongo_id", None)
                    client_data.pop("mongo_id", None)
                    client = schemas.Client(**client_data, _mongo_id=mongo_id)
                    safe_print(f"INFO: تم جلب العميل (MongoID: {client_id}) من الأونلاين.")
                    return client
            except Exception as e:
                safe_print(
                    f"WARNING: فشل البحث بالـ MongoID {client_id}: {e}. جاري البحث الأونلاين..."
                )

        return None

    def fetch_client_logo_on_demand(self, client_id_or_mongo_id: str) -> bool:
        """
        جلب شعار عميل واحد من MongoDB عند الطلب وتخزينه محلياً.
        يعيد True إذا تم جلب شعار فعلياً، False إذا لا يوجد شعار أو فشل العملية.
        """
        if not client_id_or_mongo_id:
            return False

        if not self.online or self.mongo_db is None or self.mongo_client is None:
            return False

        local_id = None
        mongo_id = None

        try:
            with self._lock:
                cursor = self.get_cursor()
                try:
                    cursor.execute(
                        "SELECT id, _mongo_id FROM clients WHERE id = ? OR _mongo_id = ?",
                        (client_id_or_mongo_id, client_id_or_mongo_id),
                    )
                    row = cursor.fetchone()
                    if row:
                        row_dict = dict(row)
                        local_id = row_dict.get("id")
                        mongo_id = row_dict.get("_mongo_id")
                finally:
                    cursor.close()
        except Exception:
            return False

        target_id = mongo_id or client_id_or_mongo_id
        selectors = []
        if target_id:
            selectors.append({"_id": self._to_objectid(target_id)})
            selectors.append({"_mongo_id": target_id})

        if not selectors:
            return False

        try:
            remote = self.mongo_db.clients.find_one(
                self._merge_active_filter_mongo({"$or": selectors}),
                {"logo_data": 1, "has_logo": 1, "logo_last_synced": 1, "last_modified": 1},
            )
            if not remote:
                return False

            logo_data = remote.get("logo_data") or ""
            has_logo = bool(remote.get("has_logo", False) or logo_data)
            logo_last_synced = remote.get("logo_last_synced") or remote.get("last_modified")
            if hasattr(logo_last_synced, "isoformat"):
                logo_last_synced = logo_last_synced.isoformat()
            elif logo_last_synced is not None:
                logo_last_synced = str(logo_last_synced)
            else:
                logo_last_synced = datetime.now().isoformat()

            # توحيد metadata في السحابة إذا كان السجل قديماً
            if has_logo and "has_logo" not in remote:
                try:
                    self.mongo_db.clients.update_one(
                        {"_id": remote.get("_id")},
                        {"$set": {"has_logo": True, "logo_last_synced": logo_last_synced}},
                    )
                except Exception:
                    pass

            if local_id is None:
                # لا يوجد صف محلي لتحديثه
                return bool(logo_data)

            with self._lock:
                cursor = self.get_cursor()
                try:
                    cursor.execute(
                        """
                        UPDATE clients
                        SET logo_data = ?, has_logo = ?, logo_last_synced = ?, sync_status = 'synced', dirty_flag = 0
                        WHERE id = ?
                        """,
                        (
                            logo_data if logo_data else None,
                            1 if has_logo else 0,
                            logo_last_synced,
                            local_id,
                        ),
                    )
                    self.sqlite_conn.commit()
                finally:
                    cursor.close()

            if CACHE_ENABLED and hasattr(self, "_clients_cache"):
                self._clients_cache.invalidate()

            return bool(logo_data)

        except Exception as e:
            safe_print(f"WARNING: [Repository] فشل جلب شعار العميل عند الطلب: {e}")
            return False

    def _to_objectid(self, item_id: str):
        """محاولة تحويل النص إلى ObjectId صالح لتجنب أخطاء InvalidId."""
        try:
            object_id_class = _get_object_id_class()
            if object_id_class is not None and isinstance(item_id, str) and len(item_id) == 24:
                return object_id_class(item_id)
        except Exception:
            pass
        return item_id

    @staticmethod
    def _client_phone_key(phone: Any) -> str:
        return str(phone or "").strip().replace(" ", "").replace("-", "")

    def _get_local_client_shadow_by_mongo_id(self, mongo_id: Any) -> dict[str, Any] | None:
        mongo_ref = str(mongo_id or "").strip()
        if not mongo_ref:
            return None
        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"SELECT * {self._is_active_filter_sql('clients')} AND _mongo_id = ?",
                        (mongo_ref,),
                    )
                    row = cursor.fetchone()
                finally:
                    cursor.close()
            return dict(row) if row else None
        except Exception:
            return None

    def _get_client_by_phone(self, phone: str) -> schemas.Client | None:
        """البحث عن عميل برقم الهاتف"""
        if not phone:
            return None

        # تنظيف رقم الهاتف
        clean_phone = self._client_phone_key(phone)

        try:
            self.sqlite_cursor.execute(
                f"SELECT * {self._is_active_filter_sql('clients')} AND (phone = ? OR phone = ?) AND status != ?",
                (phone, clean_phone, schemas.ClientStatus.ARCHIVED.value),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Client(**dict(row))
        except Exception as e:
            safe_print(f"WARNING: فشل البحث بالهاتف (SQLite): {e}")

        if self.online:
            try:
                # البحث بالرقم الأصلي أو المنظف
                client_data = self.mongo_db.clients.find_one(
                    self._merge_active_filter_mongo(
                        {
                            "$or": [{"phone": phone}, {"phone": clean_phone}],
                            "status": {"$ne": schemas.ClientStatus.ARCHIVED.value},
                        }
                    )
                )
                if client_data:
                    mongo_id = str(client_data.pop("_id"))
                    local_shadow = self._get_local_client_shadow_by_mongo_id(mongo_id)
                    if local_shadow is not None:
                        local_phone_key = self._client_phone_key(local_shadow.get("phone"))
                        if local_phone_key != clean_phone:
                            return None
                        return schemas.Client(**local_shadow)
                    if "has_logo" not in client_data:
                        client_data["has_logo"] = bool(client_data.get("logo_data"))
                    client_data.pop("_mongo_id", None)
                    client_data.pop("mongo_id", None)
                    return schemas.Client(**client_data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"WARNING: فشل البحث بالهاتف (Mongo): {e}")

        return None

    def _get_similar_project(self, name: str, client_id: str) -> schemas.Project | None:
        """البحث عن مشروع مشابه لنفس العميل (case insensitive)"""
        if not name or not client_id:
            return None

        name_key = self._project_text_key(name)
        client_keys = {
            self._project_text_key(reference)
            for reference in self._client_reference_values(client_id)
            if self._project_text_key(reference)
        }
        if not client_keys:
            client_key = self._project_text_key(client_id)
            if client_key:
                client_keys = {client_key}

        local_rows = self._get_active_project_rows()

        def _hydrate_local_project(local_id: Any) -> schemas.Project | None:
            try:
                self.sqlite_cursor.execute(
                    f"SELECT * {self._is_active_filter_sql('projects')} AND id = ?",
                    (local_id,),
                )
                row = self.sqlite_cursor.fetchone()
                if not row:
                    return None
                row_dict = dict(row)
                if isinstance(row_dict.get("items"), str):
                    try:
                        row_dict["items"] = json.loads(row_dict["items"])
                    except (json.JSONDecodeError, TypeError):
                        row_dict["items"] = []
                if isinstance(row_dict.get("milestones"), str):
                    try:
                        row_dict["milestones"] = json.loads(row_dict["milestones"])
                    except (json.JSONDecodeError, TypeError):
                        row_dict["milestones"] = []
                return schemas.Project(**row_dict)
            except Exception as e:
                safe_print(f"WARNING: فشل تحميل المشروع المحلي أثناء فحص التكرار: {e}")
                return None

        for row in local_rows:
            if self._project_text_key(row.get("name")) != name_key:
                continue
            if client_keys and self._project_text_key(row.get("client_id")) not in client_keys:
                continue
            hydrated = _hydrate_local_project(row.get("id"))
            if hydrated is not None:
                return hydrated

        if self.online:
            try:
                remote_projects = list(
                    self.mongo_db.projects.find(
                        self._merge_active_filter_mongo(
                            {
                                "name": {"$regex": f"^{re.escape(name.strip())}$", "$options": "i"},
                                "status": {"$ne": schemas.ProjectStatus.ARCHIVED.value},
                            }
                        )
                    )
                )
                for project_data in remote_projects:
                    if (
                        client_keys
                        and self._project_text_key(project_data.get("client_id")) not in client_keys
                    ):
                        continue

                    mongo_id = str(project_data.get("_id") or "").strip()
                    local_shadow = next(
                        (
                            row
                            for row in local_rows
                            if str(row.get("_mongo_id") or "").strip() == mongo_id
                        ),
                        None,
                    )
                    if local_shadow is not None:
                        local_shadow_name_key = self._project_text_key(local_shadow.get("name"))
                        local_shadow_client_key = self._project_text_key(
                            local_shadow.get("client_id")
                        )
                        if (
                            not client_keys or local_shadow_client_key in client_keys
                        ) and local_shadow_name_key != name_key:
                            continue

                    mongo_id = str(project_data.pop("_id"))
                    project_data.pop("_mongo_id", None)
                    project_data.pop("mongo_id", None)
                    if "items" not in project_data or project_data["items"] is None:
                        project_data["items"] = []
                    elif isinstance(project_data["items"], str):
                        try:
                            project_data["items"] = json.loads(project_data["items"])
                        except (json.JSONDecodeError, TypeError):
                            project_data["items"] = []
                    if "currency" not in project_data or project_data["currency"] is None:
                        project_data["currency"] = "EGP"
                    return schemas.Project(**project_data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"WARNING: فشل البحث عن مشروع مشابه (Mongo): {e}")

        try:
            self.sqlite_cursor.execute(
                f"SELECT * {self._is_active_filter_sql('projects')} AND client_id = ? AND LOWER(name) = ? AND status != ?",
                (client_id, name.strip().lower(), schemas.ProjectStatus.ARCHIVED.value),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                row_dict = dict(row)
                if isinstance(row_dict.get("items"), str):
                    try:
                        row_dict["items"] = json.loads(row_dict["items"])
                    except (json.JSONDecodeError, TypeError):
                        row_dict["items"] = []
                # ⚡ معالجة milestones (JSON string -> list)
                if isinstance(row_dict.get("milestones"), str):
                    try:
                        row_dict["milestones"] = json.loads(row_dict["milestones"])
                    except (json.JSONDecodeError, TypeError):
                        row_dict["milestones"] = []
                return schemas.Project(**row_dict)
        except Exception as e:
            safe_print(f"WARNING: فشل البحث عن مشروع مشابه (SQLite): {e}")

        return None

    @staticmethod
    def _normalized_key(value: Any) -> str:
        return normalize_user_text(str(value or "")).strip().casefold()

    def _project_text_key(self, value: Any) -> str:
        normalized = (
            normalize_user_text(str(value or "")).strip().translate(self._PROJECT_KEY_TRANSLATION)
        )
        return normalized.casefold()

    @staticmethod
    def _date_key(value: Any) -> str:
        text = str(value or "")
        return text[:10] if text else ""

    @staticmethod
    def _amount_key(value: Any) -> float:
        try:
            return round(float(value or 0.0), 2)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _is_active_filter_sql(table_name: str) -> str:
        # جميع الجداول المحاسبية الأساسية عندنا فيها sync_status و is_deleted
        return (
            f"FROM {table_name} "
            "WHERE (sync_status != 'deleted' OR sync_status IS NULL) "
            "AND (is_deleted = 0 OR is_deleted IS NULL)"
        )

    @staticmethod
    def _active_filter_mongo() -> dict[str, Any]:
        return {
            "$and": [
                {
                    "$or": [
                        {"sync_status": {"$exists": False}},
                        {"sync_status": {"$ne": "deleted"}},
                    ]
                },
                {
                    "$or": [
                        {"is_deleted": {"$exists": False}},
                        {"is_deleted": {"$ne": True}},
                    ]
                },
            ]
        }

    def _merge_active_filter_mongo(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        active_filter = self._active_filter_mongo()
        active_clauses = list(active_filter["$and"])
        if not query:
            return active_filter
        if "$and" in query and len(query) == 1:
            return {"$and": [*query["$and"], *active_clauses]}
        return {"$and": [query, *active_clauses]}

    def _get_active_project_rows(self) -> list[dict[str, Any]]:
        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        """
                        SELECT id, name, COALESCE(client_id, '') AS client_id,
                               COALESCE(_mongo_id, '') AS _mongo_id,
                               COALESCE(project_code, '') AS project_code,
                               COALESCE(invoice_number, '') AS invoice_number
                        FROM projects
                        WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                        AND (is_deleted = 0 OR is_deleted IS NULL)
                        """
                    )
                    return [dict(row) for row in cursor.fetchall()]
                finally:
                    cursor.close()
        except Exception:
            return []

    def _has_ambiguous_project_name_reference(self, project_ref: Any) -> bool:
        reference = normalize_user_text(project_ref)
        if not reference:
            return False

        rows = self._get_active_project_rows()
        if not rows:
            return False

        reference_key = self._project_text_key(reference)
        matches = [
            row
            for row in rows
            if str(row.get("name") or "").strip() == reference
            or self._project_text_key(row.get("name")) == reference_key
        ]
        return len(matches) > 1

    def _resolve_project_row(self, project_ref: str, client_id: str = "") -> dict[str, Any] | None:
        reference = normalize_user_text(project_ref)
        if not reference:
            return None

        rows = self._get_active_project_rows()
        if not rows:
            return None

        client_keys = {
            self._project_text_key(reference)
            for reference in self._client_reference_values(client_id)
            if self._project_text_key(reference)
        }
        if not client_keys:
            client_key = self._project_text_key(client_id)
            if client_key:
                client_keys = {client_key}
        ref_key = self._project_text_key(reference)

        def _pick(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
            if not candidates:
                return None
            if len(candidates) == 1:
                return candidates[0]
            if client_keys:
                by_client = [
                    row
                    for row in candidates
                    if self._project_text_key(row.get("client_id")) in client_keys
                ]
                if len(by_client) == 1:
                    return by_client[0]
            return None

        # 1) Exact name
        chosen = _pick([row for row in rows if str(row.get("name") or "") == reference])
        if chosen:
            return chosen

        # 2) Numeric local ID
        if reference.isdigit():
            chosen = _pick([row for row in rows if str(row.get("id") or "") == reference])
            if chosen:
                return chosen

        # 3) Mongo ID
        chosen = _pick(
            [row for row in rows if str(row.get("_mongo_id") or "").strip() == reference]
        )
        if chosen:
            return chosen

        # 4) Unique project code / invoice number
        for field in ("project_code", "invoice_number"):
            matches = [
                row
                for row in rows
                if self._project_text_key(row.get(field, "")) == ref_key
                and str(row.get(field) or "").strip()
            ]
            chosen = _pick(matches)
            if chosen:
                return chosen

        # 5) Normalized name (whitespace/ar variants)
        return _pick([row for row in rows if self._project_text_key(row.get("name")) == ref_key])

    def _resolve_project_target_row(
        self,
        project_ref: Any,
        client_id: str | None = "",
        *,
        local_id: Any = None,
        mongo_id: Any = None,
    ) -> dict[str, Any] | None:
        """Resolve a project row from the most specific references first."""
        seen: set[str] = set()
        candidates: list[str] = []

        for raw_value in (local_id, mongo_id, project_ref):
            text = normalize_user_text(raw_value)
            if text and text not in seen:
                seen.add(text)
                candidates.append(text)

        for candidate in candidates:
            resolved = self._resolve_project_row(candidate, client_id or "")
            if resolved:
                return resolved
        return None

    def resolve_project_name(self, project_ref: str | None, client_id: str | None = None) -> str:
        """Resolve any project reference (name/id/mongo_id/normalized text) to canonical name."""
        reference = normalize_user_text(project_ref)
        if not reference:
            return ""

        resolved = self._resolve_project_target_row(reference, client_id or "")
        if resolved:
            return str(resolved.get("name") or "")
        return ""

    @staticmethod
    def _stable_project_reference(project_row: dict[str, Any] | None, fallback: Any = "") -> str:
        if project_row:
            # Prefer the cloud id when available so cross-device links stay stable.
            for field in ("_mongo_id", "id", "name"):
                value = str(project_row.get(field) or "").strip()
                if value:
                    return value
        normalized_fallback = normalize_user_text(fallback)
        if normalized_fallback:
            return normalized_fallback
        return str(fallback or "").strip()

    @staticmethod
    def _project_scope_key(
        project_ref: Any = "",
        client_id: Any = "",
        *,
        project_row: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        if project_row:
            reference = Repository._stable_project_reference(project_row, project_ref)
            client_value = str(project_row.get("client_id") or client_id or "").strip()
            return client_value, reference

        reference = normalize_user_text(project_ref)
        client_value = normalize_user_text(client_id)
        return client_value, reference

    def _resolve_project_context(
        self, project_ref: Any, client_id: str | None = None
    ) -> tuple[dict[str, Any] | None, str, set[str], str]:
        reference = normalize_user_text(project_ref)
        if not reference:
            return None, "", set(), ""

        resolved = self._resolve_project_target_row(reference, client_id or "")
        if not resolved:
            return None, "", set(), ""

        canonical_project_name = str(resolved.get("name") or "").strip()
        aliases = self._project_reference_values(resolved)
        target_client_id = str(resolved.get("client_id") or client_id or "").strip()
        return resolved, canonical_project_name, aliases, target_client_id

    @staticmethod
    def _project_reference_values(project_row: dict[str, Any] | None) -> set[str]:
        aliases: set[str] = set()
        if not project_row:
            return aliases

        for field in ("name", "id", "_mongo_id", "project_code", "invoice_number"):
            value = str(project_row.get(field) or "").strip()
            if value:
                aliases.add(value)
        return aliases

    def _project_aliases(
        self, canonical_project_name: str, client_id: str | None = None
    ) -> set[str]:
        aliases: set[str] = set()
        if canonical_project_name:
            aliases.add(str(canonical_project_name).strip())

        row = self._resolve_project_target_row(canonical_project_name, client_id or "")
        if row:
            aliases.update(self._project_reference_values(row))

        # Remove empty members
        return {item for item in aliases if item}

    def _row_matches_project(
        self, raw_project_ref: Any, canonical_project_name: str, aliases: set[str]
    ) -> bool:
        raw_text = str(raw_project_ref or "").strip()
        if not raw_text:
            return False
        if raw_text in aliases:
            return True
        raw_key = self._project_text_key(raw_text)
        if raw_key == self._project_text_key(canonical_project_name):
            return True
        return raw_key in {self._project_text_key(alias) for alias in aliases if alias}

    def _row_matches_project_scope(
        self,
        raw_project_ref: Any,
        canonical_project_name: str,
        aliases: set[str],
        *,
        target_client_id: str | None = None,
        row_client_id: Any = None,
    ) -> bool:
        if not self._row_matches_project(raw_project_ref, canonical_project_name, aliases):
            return False

        target_client_key = self._project_text_key(target_client_id)
        if not target_client_key:
            return True

        row_client_key = self._project_text_key(row_client_id)
        return not row_client_key or row_client_key == target_client_key

    def _is_ambiguous_name_only_project_link(
        self, raw_project_ref: Any, canonical_project_name: str, aliases: set[str]
    ) -> bool:
        raw_text = str(raw_project_ref or "").strip()
        if not raw_text:
            return False

        raw_key = self._project_text_key(raw_text)
        canonical_key = self._project_text_key(canonical_project_name)
        if raw_key != canonical_key:
            return False

        stable_alias_keys = {
            self._project_text_key(alias)
            for alias in aliases
            if alias and self._project_text_key(alias) != canonical_key
        }
        return raw_key not in stable_alias_keys

    def _cascade_project_rename_sqlite(
        self,
        old_project_name: str,
        new_project_name: str,
        now_iso: str,
        project_aliases: set[str],
        project_record_id: str | int | None = None,
        stable_project_ref: str | None = None,
        cursor=None,
    ) -> None:
        old_name = str(old_project_name or "").strip()
        new_name = str(new_project_name or "").strip()
        if not old_name or not new_name or old_name == new_name:
            return

        replacement_ref = (
            normalize_user_text(stable_project_ref)
            or str(stable_project_ref or "").strip()
            or new_name
        )

        reference_values = sorted(
            {
                str(value).strip()
                for value in (set(project_aliases) | {old_name})
                if str(value).strip() and str(value).strip() != new_name
            }
        )
        if not reference_values:
            return

        active_cursor = cursor or self.sqlite_cursor

        placeholders = ", ".join("?" for _ in reference_values)
        tracked_tables = (
            ("payments", "project_id"),
            ("expenses", "project_id"),
            ("invoices", "project_id"),
            ("tasks", "related_project_id"),
        )
        allowed_tables = {table_name for table_name, _ in tracked_tables}

        for table_name, column_name in tracked_tables:
            if not self._table_exists(table_name):
                continue
            table_ref = self._quote_sqlite_identifier(table_name, allowed=allowed_tables)
            column_ref = self._quote_sqlite_identifier(column_name)
            cascade_sql = f"UPDATE {table_ref} SET {column_ref} = ?, last_modified = ?, sync_status = 'modified_offline', dirty_flag = 1 WHERE {column_ref} IN ({placeholders})"  # nosec B608
            active_cursor.execute(cascade_sql, (replacement_ref, now_iso, *reference_values))

        if self._table_exists("project_milestones"):
            milestones_ref = self._quote_sqlite_identifier("project_milestones")
            project_id_ref = self._quote_sqlite_identifier("project_id")
            milestones_sql = f"UPDATE {milestones_ref} SET {project_id_ref} = ? WHERE {project_id_ref} IN ({placeholders})"  # nosec B608
            active_cursor.execute(milestones_sql, (replacement_ref, *reference_values))

        if self._table_exists("invoice_numbers"):
            project_row_id = str(project_record_id or "").strip()
            invoice_project_ref = (
                normalize_user_text(project_row_id) or project_row_id or replacement_ref or new_name
            )
            invoice_params = reference_values + [old_name]
            invoice_placeholders = ", ".join("?" for _ in invoice_params)
            if invoice_project_ref:
                active_cursor.execute(
                    f"""
                    UPDATE invoice_numbers
                    SET project_id = ?, project_name = ?
                    WHERE project_id IN ({invoice_placeholders})
                       OR (project_id IS NULL AND project_name = ?)
                    """,
                    (invoice_project_ref, new_name, *invoice_params, old_name),
                )
            else:
                active_cursor.execute(
                    """
                    UPDATE invoice_numbers
                    SET project_name = ?
                    WHERE project_name = ?
                    """,
                    (new_name, old_name),
                )

    def _cascade_project_rename_mongo(
        self,
        old_project_name: str,
        new_project_name: str,
        now_dt: datetime,
        project_aliases: set[str],
        stable_project_ref: str | None = None,
    ) -> None:
        if not self.online or self.mongo_db is None:
            return

        old_name = str(old_project_name or "").strip()
        new_name = str(new_project_name or "").strip()
        if not old_name or not new_name or old_name == new_name:
            return

        replacement_ref = (
            normalize_user_text(stable_project_ref)
            or str(stable_project_ref or "").strip()
            or new_name
        )

        reference_values = sorted(
            {
                str(value).strip()
                for value in (set(project_aliases) | {old_name})
                if str(value).strip() and str(value).strip() != new_name
            }
        )
        if not reference_values:
            return

        self.mongo_db.payments.update_many(
            {"project_id": {"$in": reference_values}},
            {"$set": {"project_id": replacement_ref, "last_modified": now_dt}},
        )
        self.mongo_db.expenses.update_many(
            {"project_id": {"$in": reference_values}},
            {"$set": {"project_id": replacement_ref, "last_modified": now_dt}},
        )
        self.mongo_db.invoices.update_many(
            {"project_id": {"$in": reference_values}},
            {"$set": {"project_id": replacement_ref, "last_modified": now_dt}},
        )
        self.mongo_db.tasks.update_many(
            {"related_project_id": {"$in": reference_values}},
            {"$set": {"related_project_id": replacement_ref, "last_modified": now_dt}},
        )

    def _delete_project_related_rows_sqlite(
        self,
        project_name: str,
        now_iso: str,
        project_aliases: set[str],
        hard_delete: bool,
        project_record_id: str | int | None = None,
    ) -> None:
        project_name = str(project_name or "").strip()
        reference_values = sorted(
            {
                str(value).strip()
                for value in (set(project_aliases) | {project_name})
                if str(value).strip()
            }
        )
        if not reference_values:
            return

        placeholders = ", ".join("?" for _ in reference_values)
        tracked_tables = (
            ("payments", "project_id"),
            ("expenses", "project_id"),
            ("invoices", "project_id"),
            ("tasks", "related_project_id"),
        )
        allowed_tables = {table_name for table_name, _ in tracked_tables}

        for table_name, column_name in tracked_tables:
            if not self._table_exists(table_name):
                continue
            table_ref = self._quote_sqlite_identifier(table_name, allowed=allowed_tables)
            column_ref = self._quote_sqlite_identifier(column_name)
            if hard_delete:
                delete_related_sql = (
                    f"DELETE FROM {table_ref} WHERE {column_ref} IN ({placeholders})"  # nosec B608
                )
                self.sqlite_cursor.execute(delete_related_sql, tuple(reference_values))
            else:
                soft_delete_related_sql = f"UPDATE {table_ref} SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1 WHERE {column_ref} IN ({placeholders})"  # nosec B608
                self.sqlite_cursor.execute(soft_delete_related_sql, (now_iso, *reference_values))

        if self._table_exists("project_milestones"):
            milestones_ref = self._quote_sqlite_identifier("project_milestones")
            project_id_ref = self._quote_sqlite_identifier("project_id")
            delete_milestones_sql = f"DELETE FROM {milestones_ref} WHERE {project_id_ref} IN ({placeholders})"  # nosec B608
            self.sqlite_cursor.execute(delete_milestones_sql, tuple(reference_values))

        if self._table_exists("invoice_numbers"):
            project_row_id = str(project_record_id or "").strip()
            if project_row_id:
                self.sqlite_cursor.execute(
                    "DELETE FROM invoice_numbers WHERE project_id = ? OR (project_id IS NULL AND project_name = ?)",
                    (project_row_id, project_name),
                )
            else:
                self.sqlite_cursor.execute(
                    "DELETE FROM invoice_numbers WHERE project_name = ?",
                    (project_name,),
                )

    def _delete_project_related_rows_mongo(
        self, project_name: str, now_dt: datetime, project_aliases: set[str]
    ) -> None:
        if not self.online or self.mongo_db is None:
            return

        project_name = str(project_name or "").strip()
        reference_values = sorted(
            {
                str(value).strip()
                for value in (set(project_aliases) | {project_name})
                if str(value).strip()
            }
        )
        if not reference_values:
            return

        update_doc = {
            "$set": {
                "is_deleted": True,
                "sync_status": "deleted",
                "last_modified": now_dt,
            }
        }
        self.mongo_db.payments.update_many({"project_id": {"$in": reference_values}}, update_doc)
        self.mongo_db.expenses.update_many({"project_id": {"$in": reference_values}}, update_doc)
        self.mongo_db.invoices.update_many({"project_id": {"$in": reference_values}}, update_doc)
        self.mongo_db.tasks.update_many(
            {"related_project_id": {"$in": reference_values}}, update_doc
        )

    def _payment_signature(self, row: dict[str, Any]) -> tuple[Any, ...]:
        project_ref = self._stable_project_reference(
            self._resolve_project_target_row(
                row.get("project_id"),
                str(row.get("client_id") or ""),
            ),
            row.get("project_id"),
        )
        return (
            self._project_text_key(project_ref),
            self._date_key(row.get("date")),
            self._amount_key(row.get("amount")),
            self._normalized_key(row.get("client_id")),
            self._normalized_key(row.get("account_id")),
            self._normalized_key(row.get("method")),
        )

    def _expense_signature(self, row: dict[str, Any]) -> tuple[Any, ...]:
        account_id = normalize_user_text(str(row.get("account_id") or "")).strip()
        payment_account = normalize_user_text(str(row.get("payment_account_id") or "")).strip()
        effective_payment_account = payment_account or account_id
        project_ref = self._stable_project_reference(
            self._resolve_project_target_row(row.get("project_id")),
            row.get("project_id"),
        )
        return (
            self._project_text_key(project_ref),
            self._date_key(row.get("date")),
            self._amount_key(row.get("amount")),
            self._normalized_key(row.get("category")),
            self._normalized_key(row.get("description")),
            self._normalized_key(account_id),
            self._normalized_key(effective_payment_account),
        )

    @staticmethod
    def _prefer_row(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        def _score(row: dict[str, Any]) -> tuple[int, int, str, int]:
            mongo_weight = 0 if str(row.get("_mongo_id") or "").strip() else 1
            synced_weight = (
                0 if str(row.get("sync_status") or "").strip().lower() == "synced" else 1
            )
            created_at = str(row.get("created_at") or "")
            row_id = int(row.get("id") or 0)
            return (mongo_weight, synced_weight, created_at, row_id)

        return candidate if _score(candidate) < _score(existing) else existing

    def _dedupe_rows_by_signature(
        self,
        rows: list[dict[str, Any]],
        signature_fn,
    ) -> list[dict[str, Any]]:
        deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
        order: list[tuple[Any, ...]] = []

        for row in rows:
            key = signature_fn(row)
            if key not in deduped:
                deduped[key] = row
                order.append(key)
                continue
            deduped[key] = self._prefer_row(deduped[key], row)

        return [deduped[key] for key in order]

    def _get_duplicate_payment(
        self,
        project_id: str,
        date,
        amount: float,
        exclude_id: int = None,
        client_id: str | None = None,
    ) -> schemas.Payment | None:
        """البحث عن دفعة مكررة (نفس المشروع + نفس التاريخ + نفس المبلغ) - محسّن"""
        normalized_project_ref = normalize_user_text(project_id) or str(project_id or "").strip()
        if not normalized_project_ref:
            return None

        resolved_project, canonical_project_name, _aliases, _target_client_id = (
            self._resolve_project_context(normalized_project_ref, client_id)
        )
        if resolved_project and canonical_project_name:
            try:
                existing_for_project = self.get_payments_for_project(
                    normalized_project_ref,
                    client_id=client_id,
                )
                target_date_short = self._date_key(
                    date.isoformat() if hasattr(date, "isoformat") else date
                )
                target_amount = self._amount_key(amount)
                for existing in existing_for_project:
                    existing_id = getattr(existing, "id", None)
                    if exclude_id and existing_id and int(existing_id) == int(exclude_id):
                        continue
                    existing_date = self._date_key(getattr(existing, "date", ""))
                    existing_amount = self._amount_key(getattr(existing, "amount", 0.0))
                    if (
                        existing_date == target_date_short
                        and abs(existing_amount - target_amount) <= 0.01
                    ):
                        return existing
                # الفحص scoped هنا هو المرجع؛ لا نرجع إلى fallback الخام
                # حتى لا نعامل النسخ الظلية لنفس الدفعة كأنها دفعة أخرى.
                return None
            except Exception:
                pass

        try:
            existing_for_project = self.get_payments_for_project(
                normalized_project_ref,
                client_id=client_id,
            )
            target_date_short = self._date_key(
                date.isoformat() if hasattr(date, "isoformat") else date
            )
            target_amount = self._amount_key(amount)
            for existing in existing_for_project:
                existing_id = getattr(existing, "id", None)
                if exclude_id and existing_id and int(existing_id) == int(exclude_id):
                    continue
                existing_date = self._date_key(getattr(existing, "date", ""))
                existing_amount = self._amount_key(getattr(existing, "amount", 0.0))
                if (
                    existing_date == target_date_short
                    and abs(existing_amount - target_amount) <= 0.01
                ):
                    return existing
        except Exception:
            pass

        date_str = date.isoformat() if hasattr(date, "isoformat") else str(date)
        date_str_short = date_str[:10]
        amount_rounded = round(float(amount), 2)
        amount_min = amount_rounded - 0.01
        amount_max = amount_rounded + 0.01
        target_client_key = self._project_text_key(client_id)

        try:
            with self._lock:
                temp_cursor = self.sqlite_conn.cursor()
                try:
                    sql = """
                        SELECT * FROM payments
                        WHERE project_id = ?
                        AND (sync_status != 'deleted' OR sync_status IS NULL)
                        AND (is_deleted = 0 OR is_deleted IS NULL)
                        AND amount >= ? AND amount <= ?
                        AND date LIKE ?
                    """
                    params: tuple[Any, ...]
                    if target_client_key:
                        sql += " AND (client_id = ? OR client_id IS NULL OR client_id = '')"
                    if exclude_id:
                        sql += " AND id != ?"
                        if target_client_key:
                            params = (
                                normalized_project_ref,
                                amount_min,
                                amount_max,
                                f"{date_str_short}%",
                                client_id,
                                exclude_id,
                            )
                        else:
                            params = (
                                normalized_project_ref,
                                amount_min,
                                amount_max,
                                f"{date_str_short}%",
                                exclude_id,
                            )
                    else:
                        if target_client_key:
                            params = (
                                normalized_project_ref,
                                amount_min,
                                amount_max,
                                f"{date_str_short}%",
                                client_id,
                            )
                        else:
                            params = (
                                normalized_project_ref,
                                amount_min,
                                amount_max,
                                f"{date_str_short}%",
                            )
                    temp_cursor.execute(f"{sql} LIMIT 1", params)
                    row = temp_cursor.fetchone()
                    if row:
                        safe_print(
                            f"DEBUG: [_get_duplicate_payment] وجدت دفعة مكررة محلياً: {dict(row)}"
                        )
                        return schemas.Payment(**dict(row))
                finally:
                    temp_cursor.close()
        except Exception as e:
            safe_print(f"WARNING: فشل البحث عن دفعة مكررة (SQLite): {e}")

        if self.online:
            try:
                payment_data = self.mongo_db.payments.find_one(
                    self._merge_active_filter_mongo(
                        {
                            "project_id": normalized_project_ref,
                            "amount": {
                                "$gte": amount_rounded - 0.01,
                                "$lte": amount_rounded + 0.01,
                            },
                            "date": {"$regex": f"^{date_str_short}"},
                            **({"client_id": client_id} if target_client_key else {}),
                        }
                    )
                )
                if payment_data:
                    mongo_id = str(payment_data.pop("_id"))
                    payment_data.pop("_mongo_id", None)
                    payment_data.pop("mongo_id", None)
                    safe_print("DEBUG: [_get_duplicate_payment] وجدت دفعة مكررة في السحابة")
                    return schemas.Payment(**payment_data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"WARNING: فشل البحث عن دفعة مكررة (Mongo): {e}")

        return None

    def _cleanup_shadow_payment_duplicates(
        self,
        current_id: int,
        project_id: str,
        date,
        amount: float,
        *,
        client_id: str | None = None,
        account_id: str | None = None,
        method: str | None = None,
    ) -> int:
        try:
            resolved_project = self._resolve_project_target_row(project_id, client_id)
            signature_seed = {
                "project_id": self._stable_project_reference(resolved_project, project_id),
                "date": date.isoformat() if hasattr(date, "isoformat") else str(date),
                "amount": amount,
                "client_id": client_id or "",
                "account_id": account_id or "",
                "method": method or "",
            }
            target_signature = self._payment_signature(signature_seed)

            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(f"SELECT * {self._is_active_filter_sql('payments')}")
                    rows = [dict(row) for row in cursor.fetchall()]
                finally:
                    cursor.close()

            matching_rows = [
                row for row in rows if self._payment_signature(row) == target_signature
            ]
            if len(matching_rows) < 2:
                return 0

            current_row = next(
                (row for row in matching_rows if int(row.get("id") or 0) == int(current_id)),
                None,
            )
            if current_row is None:
                return 0

            preferred_row = current_row
            for row in matching_rows:
                if int(row.get("id") or 0) == int(current_id):
                    continue
                preferred_row = self._prefer_row(preferred_row, row)
            if int(preferred_row.get("id") or 0) != int(current_id):
                return 0

            stale_ids = [
                int(row["id"])
                for row in matching_rows
                if int(row.get("id") or 0) != int(current_id)
            ]
            if not stale_ids:
                return 0

            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    placeholders = ", ".join("?" for _ in stale_ids)
                    cursor.execute(
                        f"DELETE FROM payments WHERE id IN ({placeholders})",
                        stale_ids,
                    )
                    deleted_count = int(cursor.rowcount or 0)
                    self.sqlite_conn.commit()
                finally:
                    cursor.close()

            if deleted_count > 0:
                safe_print(
                    f"INFO: [Repo] تم تنظيف {deleted_count} نسخة ظل مكررة لنفس الدفعة قبل التحديث"
                )
            return deleted_count
        except Exception:
            return 0

    def _get_similar_client(self, name: str) -> schemas.Client | None:
        """البحث عن عميل مشابه (case insensitive + تشابه جزئي)"""
        if not name:
            return None

        name_key = self._normalized_key(name)

        try:
            self.sqlite_cursor.execute(
                f"SELECT * {self._is_active_filter_sql('clients')} AND LOWER(name) = ? AND status != ?",
                (name.strip().lower(), schemas.ClientStatus.ARCHIVED.value),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Client(**dict(row))
        except Exception as e:
            safe_print(f"WARNING: فشل البحث عن عميل مشابه (SQLite): {e}")

        if self.online:
            try:
                # البحث case insensitive في MongoDB
                client_data = self.mongo_db.clients.find_one(
                    self._merge_active_filter_mongo(
                        {
                            "name": {"$regex": f"^{re.escape(name.strip())}$", "$options": "i"},
                            "status": {"$ne": schemas.ClientStatus.ARCHIVED.value},
                        }
                    )
                )
                if client_data:
                    mongo_id = str(client_data.pop("_id"))
                    local_shadow = self._get_local_client_shadow_by_mongo_id(mongo_id)
                    if local_shadow is not None:
                        if self._normalized_key(local_shadow.get("name")) != name_key:
                            return None
                        return schemas.Client(**local_shadow)
                    if "has_logo" not in client_data:
                        client_data["has_logo"] = bool(client_data.get("logo_data"))
                    client_data.pop("_mongo_id", None)
                    client_data.pop("mongo_id", None)
                    return schemas.Client(**client_data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"WARNING: فشل البحث عن عميل مشابه (Mongo): {e}")

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
            "SELECT id, _mongo_id FROM clients WHERE id = ? OR _mongo_id = ?",
            (client_id_num, client_id),
        )
        row = self.sqlite_cursor.fetchone()
        local_client_id = row["id"] if row else client_id_num
        mongo_client_id = str(
            (row["_mongo_id"] if row and row["_mongo_id"] else client_id) or ""
        ).strip()

        self.sqlite_cursor.execute(
            "UPDATE clients SET status = ?, last_modified = ?, sync_status = 'modified_offline', is_deleted = 0, dirty_flag = 1 WHERE id = ? OR _mongo_id = ?",
            (archive_status, now_iso, local_client_id, mongo_client_id),
        )
        self.sqlite_conn.commit()

        if self.online:
            try:
                result = self.mongo_db.clients.update_one(
                    {
                        "$or": [
                            {"_id": self._to_objectid(mongo_client_id)},
                            {"_id": self._to_objectid(client_id)},
                            {"_mongo_id": mongo_client_id},
                            {"_mongo_id": client_id},
                            {"id": local_client_id},
                        ]
                    },
                    {
                        "$set": {
                            "status": archive_status,
                            "sync_status": "synced",
                            "is_deleted": False,
                            "last_modified": now_dt,
                        }
                    },
                )
                if result and (
                    getattr(result, "matched_count", 0) > 0
                    or getattr(result, "modified_count", 0) > 0
                ):
                    self.sqlite_cursor.execute(
                        """
                        UPDATE clients
                        SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
                        WHERE id = ? OR _mongo_id = ?
                        """,
                        (local_client_id, mongo_client_id),
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
            (client_id_num, client_id),
        )
        row = self.sqlite_cursor.fetchone()

        if row:
            local_id = row[0]
            mongo_id = row[1] if row[1] else client_id
            client_name = row[2]
            safe_print(
                f"INFO: [Repo] العميل المراد حذفه: {client_name} (local_id={local_id}, mongo_id={mongo_id})"
            )
        else:
            safe_print(f"WARNING: [Repo] العميل غير موجود في SQLite! client_id={client_id}")
            mongo_id = client_id
            local_id = client_id_num

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        if self.online:
            try:
                result = self.mongo_db.clients.update_one(
                    {
                        "$or": [
                            {"_id": self._to_objectid(mongo_id)},
                            {"_id": self._to_objectid(client_id)},
                            {"_mongo_id": mongo_id},
                            {"_mongo_id": client_id},
                            {"id": local_id},
                        ]
                    },
                    {
                        "$set": {
                            "is_deleted": True,
                            "sync_status": "deleted",
                            "last_modified": now_dt,
                        }
                    },
                )
                if getattr(result, "matched_count", 0) > 0:
                    self.sqlite_cursor.execute(
                        "DELETE FROM clients WHERE id = ? OR _mongo_id = ?",
                        (local_id, client_id),
                    )
                    deleted_rows = self.sqlite_cursor.rowcount
                    self.sqlite_conn.commit()
                    if deleted_rows > 0:
                        safe_print("INFO: [Repo] ✅ تم تعليم حذف العميل ثم حذفه محلياً")
                    return deleted_rows > 0
                safe_print("WARNING: [Repo] العميل غير موجود في MongoDB")
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل تعليم حذف العميل في MongoDB: {e}")

        self.sqlite_cursor.execute(
            """
            UPDATE clients
            SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
            WHERE id = ? OR _mongo_id = ?
            """,
            (now_iso, local_id, client_id),
        )
        self.sqlite_conn.commit()
        return True

    def update_journal_entry_by_doc_id(
        self, doc_id: str, new_lines: list[schemas.JournalEntryLine], new_description: str
    ) -> bool:
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
                result = self.mongo_db.journal_entries.update_one(
                    {"related_document_id": doc_id},
                    {
                        "$set": {
                            "lines": [line.model_dump() for line in new_lines],
                            "description": new_description,
                            "last_modified": now_dt,
                            "sync_status": "synced",
                            "is_deleted": False,
                        }
                    },
                )
                if result and (
                    getattr(result, "matched_count", 0) > 0
                    or getattr(result, "modified_count", 0) > 0
                ):
                    self.sqlite_cursor.execute(
                        """
                        UPDATE journal_entries
                        SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
                        WHERE related_document_id = ?
                        """,
                        (doc_id,),
                    )
                    self.sqlite_conn.commit()
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل تحديث القيد (Mongo): {e}")

        return True

    def get_client_by_name(self, name: str) -> schemas.Client | None:
        """(جديدة) جلب عميل واحد بالاسم (بذكاء)"""
        try:
            self.sqlite_cursor.execute(
                f"SELECT * {self._is_active_filter_sql('clients')} AND name = ?",
                (name,),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                client = schemas.Client(**dict(row))
                safe_print(f"INFO: تم جلب العميل (Name: {name}) من المحلي.")
                return client
        except Exception as e:
            safe_print(f"ERROR: فشل جلب العميل بالاسم (SQLite): {e}.")

        if self.online:
            try:
                client_data = self.mongo_db.clients.find_one(
                    self._merge_active_filter_mongo({"name": name})
                )
                if client_data:
                    mongo_id = str(client_data.pop("_id"))
                    local_shadow = self._get_local_client_shadow_by_mongo_id(mongo_id)
                    if local_shadow is not None:
                        if self._normalized_key(local_shadow.get("name")) != self._normalized_key(
                            name
                        ):
                            return None
                        return schemas.Client(**local_shadow)
                    if "has_logo" not in client_data:
                        client_data["has_logo"] = bool(client_data.get("logo_data"))
                    client_data.pop("_mongo_id", None)
                    client_data.pop("mongo_id", None)
                    client = schemas.Client(**client_data, _mongo_id=mongo_id)
                    safe_print(f"INFO: تم جلب العميل (Name: {name}) من الأونلاين.")
                    return client
            except Exception as e:
                safe_print(f"ERROR: فشل جلب العميل بالاسم (Mongo): {e}.")

        return None

    def _find_active_service_by_name(
        self, service_name: str, exclude_id: str | int | None = None
    ) -> schemas.Service | None:
        normalized_name = normalize_user_text(service_name)
        if not normalized_name:
            return None

        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    f"SELECT * {self._is_active_filter_sql('services')} AND LOWER(name) = ? AND status != ?",
                    (normalized_name.lower(), schemas.ServiceStatus.ARCHIVED.value),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        except Exception as e:
            safe_print(f"WARNING: [Repo] فشل البحث عن خدمة مكررة: {e}")
            return None

        exclude_key = str(exclude_id) if exclude_id is not None else ""
        for row in rows:
            row_dict = dict(row)
            row_local_id = str(row_dict.get("id") or "")
            row_mongo_id = str(row_dict.get("_mongo_id") or "")
            if exclude_key and exclude_key in {row_local_id, row_mongo_id}:
                continue
            return schemas.Service(**row_dict)

        return None

    # --- دوال التعامل مع الحسابات ---

    def create_account(self, account_data: schemas.Account) -> schemas.Account:
        """⚡ إنشاء حساب جديد - محلي أولاً ثم مزامنة في الخلفية"""
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        account_data.created_at = now_dt
        account_data.last_modified = now_dt
        account_data.sync_status = "new_offline"

        # ⚡ 1. الحفظ في SQLite فوراً (سريع جداً)
        sql = """
            INSERT INTO accounts (sync_status, created_at, last_modified, name, code, type, parent_id, balance, currency, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        currency_value = account_data.currency.value if account_data.currency else "EGP"
        parent_value = account_data.parent_code or account_data.parent_id
        params = (
            account_data.sync_status,
            now_iso,
            now_iso,
            account_data.name,
            account_data.code,
            account_data.type.value,
            parent_value,
            account_data.balance,
            currency_value,
            account_data.description,
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        account_data.id = local_id
        safe_print(f"INFO: ✅ تم حفظ الحساب '{account_data.name}' محلياً (ID: {local_id}).")

        # ⚡ 2. مزامنة مع MongoDB في الخلفية (لا يعطل الواجهة)
        if self.online:

            def sync_to_mongo():
                try:
                    account_dict = account_data.model_dump(exclude={"_mongo_id"})
                    account_dict["type"] = account_data.type.value

                    result = self.mongo_db.accounts.insert_one(account_dict)
                    mongo_id = str(result.inserted_id)

                    self.sqlite_cursor.execute(
                        "UPDATE accounts SET _mongo_id = ?, sync_status = ?, dirty_flag = 0 WHERE id = ?",
                        (mongo_id, "synced", local_id),
                    )
                    self.sqlite_conn.commit()
                    safe_print(
                        f"INFO: ✅ تم مزامنة الحساب '{account_data.name}' مع السيرفر (خلفية)"
                    )

                except Exception as e:
                    if "E11000 duplicate key" in str(e):
                        safe_print(
                            f"WARNING: الحساب بكود '{account_data.code}' موجود بالفعل أونلاين."
                        )
                        try:
                            active_existing = self.mongo_db.accounts.find_one(
                                self._merge_active_filter_mongo({"code": account_data.code})
                            )
                            existing = active_existing or self.mongo_db.accounts.find_one(
                                {"code": account_data.code}
                            )
                            if existing:
                                mongo_id = str(existing["_id"])
                                existing_sync_status = str(
                                    existing.get("sync_status") or ""
                                ).lower()
                                existing_is_deleted = bool(existing.get("is_deleted", False)) or (
                                    existing_sync_status == "deleted"
                                )

                                if existing_is_deleted:
                                    revived_account = account_dict.copy()
                                    revived_account["last_modified"] = now_dt
                                    revived_account["sync_status"] = "synced"
                                    revived_account["is_deleted"] = False
                                    self.mongo_db.accounts.update_one(
                                        {"_id": existing["_id"]},
                                        {"$set": revived_account},
                                    )

                                self.sqlite_cursor.execute(
                                    """
                                    UPDATE accounts
                                    SET _mongo_id = ?, sync_status = ?, dirty_flag = 0, is_deleted = 0
                                    WHERE id = ?
                                    """,
                                    (mongo_id, "synced", local_id),
                                )
                                self.sqlite_conn.commit()
                        except Exception:
                            pass
                    else:
                        safe_print(f"WARNING: فشل مزامنة الحساب '{account_data.name}': {e}")

            QTimer.singleShot(100, sync_to_mongo)

        self.invalidate_table_cache("accounts")
        return account_data

    def get_account_by_code(self, code: str) -> schemas.Account | None:
        """
        جلب حساب معين عن طريق الكود (بذكاء).
        ده ضروري جداً للروبوت المحاسبي.
        """
        if self.online:
            try:
                account_data = self.mongo_db.accounts.find_one(
                    self._merge_active_filter_mongo({"code": code})
                )
                if account_data:
                    mongo_id = str(account_data.pop("_id"))
                    account_data.pop("_mongo_id", None)
                    account_data.pop("mongo_id", None)
                    account = schemas.Account(**account_data, _mongo_id=mongo_id)
                    safe_print(f"INFO: تم جلب الحساب (Code: {code}) من الأونلاين.")
                    return account
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الحساب (Code: {code}) من Mongo: {e}.")

        # الجلب من SQLite في حالة الأوفلاين أو عدم وجوده أونلاين
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT * FROM accounts
                    WHERE code = ?
                    AND (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    """,
                    (code,),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
            if row:
                account = self._account_from_row(row)
                safe_print(f"INFO: تم جلب الحساب (Code: {code}) من المحلي.")
                return account
        except Exception as e:
            safe_print(f"ERROR: فشل جلب الحساب (Code: {code}) من المحلي: {e}.")

        return None  # لو الحساب مش موجود خالص

    def get_all_accounts(self) -> list[schemas.Account]:
        """⚡ جلب كل الحسابات (SQLite أولاً للسرعة) - مع cache ذكي"""
        if CACHE_ENABLED and hasattr(self, "_accounts_cache"):
            cached_result = self._accounts_cache.get("all_accounts")
            if cached_result is not None:
                safe_print(f"INFO: ⚡ تم جلب {len(cached_result)} حساب من الـ Cache")
                return cached_result

        # ⚡ جلب من SQLite أولاً (سريع جداً) - cursor منفصل لتجنب Recursive cursor
        try:
            with self._lock:
                cursor = self.get_cursor()
                try:
                    cursor.execute(
                        """
                        SELECT * FROM accounts
                        WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                        AND (is_deleted = 0 OR is_deleted IS NULL)
                        """
                    )
                    rows = cursor.fetchall()
                finally:
                    cursor.close()
            if rows:
                group_codes = self._account_group_codes_from_rows(rows)
                accounts_list = [
                    self._account_from_row(row, group_codes=group_codes) for row in rows
                ]
                if CACHE_ENABLED and hasattr(self, "_accounts_cache"):
                    self._accounts_cache.set("all_accounts", accounts_list)
                safe_print(f"INFO: تم جلب {len(accounts_list)} حساب من المحلي (SQLite).")
                return accounts_list
        except Exception as e:
            if self._is_sqlite_closed_error(e):
                return []
            safe_print(f"ERROR: فشل جلب الحسابات من SQLite: {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                accounts_data = list(self.mongo_db.accounts.find(self._merge_active_filter_mongo()))
                if accounts_data:
                    accounts_list = []
                    for acc in accounts_data:
                        mongo_id = str(acc.pop("_id"))
                        acc.pop("_mongo_id", None)
                        acc.pop("mongo_id", None)
                        accounts_list.append(schemas.Account(**acc, _mongo_id=mongo_id))
                    if CACHE_ENABLED and hasattr(self, "_accounts_cache"):
                        self._accounts_cache.set("all_accounts", accounts_list)
                    safe_print(f"INFO: تم جلب {len(accounts_list)} حساب من الأونلاين (MongoDB).")
                    return accounts_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الحسابات من Mongo: {e}")

        return []

    def get_account_by_id(self, account_id: str) -> schemas.Account | None:
        """⚡ جلب حساب واحد بالـ ID - SQLite أولاً للسرعة"""
        try:
            account_id_num = int(account_id)
        except ValueError:
            account_id_num = 0

        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT * FROM accounts
                    WHERE (id = ? OR _mongo_id = ?)
                    AND (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    """,
                    (account_id_num, account_id),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
            if row:
                return self._account_from_row(row)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الحساب {account_id} (SQLite): {e}")

        return None

    # --- User Management Methods ---

    def create_user(self, user) -> str:
        """إنشاء مستخدم جديد"""
        try:
            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            # حفظ في SQLite أولاً
            sql = """
                INSERT INTO users (username, password_hash, role, full_name, email, is_active, created_at, last_modified, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new_offline')
            """
            # التأكد من تحويل الـ role بشكل صحيح
            role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
            revived_local_row = False

            self.sqlite_cursor.execute(
                """
                SELECT id, _mongo_id, sync_status, is_deleted
                FROM users
                WHERE username = ?
                """,
                (user.username,),
            )
            existing_row = self.sqlite_cursor.fetchone()
            existing_is_deleted = False
            if existing_row:
                existing_is_deleted = bool(existing_row["is_deleted"]) or (
                    str(existing_row["sync_status"] or "").lower() == "deleted"
                )

            if existing_row and existing_is_deleted:
                self.sqlite_cursor.execute(
                    """
                    UPDATE users
                    SET password_hash = ?, role = ?, full_name = ?, email = ?, is_active = ?,
                        last_modified = ?, sync_status = 'modified_offline', dirty_flag = 1,
                        is_deleted = 0
                    WHERE id = ?
                    """,
                    (
                        user.password_hash,
                        role_value,
                        user.full_name,
                        user.email,
                        1 if user.is_active else 0,
                        now_iso,
                        existing_row["id"],
                    ),
                )
                self.sqlite_conn.commit()
                local_id = str(existing_row["id"])
                revived_local_row = True
            else:
                params = (
                    user.username,
                    user.password_hash,
                    role_value,
                    user.full_name,
                    user.email,
                    1 if user.is_active else 0,
                    now_iso,
                    now_iso,
                )

                self.sqlite_cursor.execute(sql, params)
                self.sqlite_conn.commit()
                local_id = str(self.sqlite_cursor.lastrowid)

            # محاولة الحفظ في MongoDB
            if self.online:
                try:
                    # تحويل User object إلى dict
                    user_dict = {
                        "username": user.username,
                        "password_hash": user.password_hash,
                        "role": role_value,
                        "full_name": user.full_name,
                        "email": user.email,
                        "is_active": user.is_active,
                        "created_at": now_dt,
                        "last_modified": now_dt,
                        "sync_status": "synced",
                        "is_deleted": False,
                    }
                    active_existing = self.mongo_db.users.find_one(
                        self._merge_active_filter_mongo({"username": user.username})
                    )
                    existing_cloud = active_existing or self.mongo_db.users.find_one(
                        {"username": user.username}
                    )
                    if existing_cloud:
                        mongo_id = str(existing_cloud["_id"])
                        update_result = self.mongo_db.users.update_one(
                            {"_id": existing_cloud["_id"]},
                            {"$set": user_dict},
                        )
                        if not (
                            update_result
                            and (
                                getattr(update_result, "matched_count", 0) > 0
                                or getattr(update_result, "modified_count", 0) > 0
                            )
                        ):
                            raise RuntimeError(f"Failed to sync cloud user: {user.username}")
                    else:
                        result = self.mongo_db.users.insert_one(user_dict)
                        mongo_id = str(result.inserted_id)

                    # تحديث الـ mongo_id في SQLite
                    self.sqlite_cursor.execute(
                        """
                        UPDATE users
                        SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0, is_deleted = 0
                        WHERE id = ?
                        """,
                        (mongo_id, local_id),
                    )
                    self.sqlite_conn.commit()

                    safe_print(
                        f"INFO: [Repository] تم إنشاء مستخدم: {user.username} (MongoDB + SQLite)"
                    )
                    return mongo_id
                except Exception as e:
                    safe_print(f"WARNING: [Repository] فشل حفظ المستخدم في MongoDB: {e}")

            safe_print(f"INFO: [Repository] تم إنشاء مستخدم: {user.username} (SQLite فقط)")
            if revived_local_row:
                self.sqlite_cursor.execute(
                    """
                    UPDATE users
                    SET sync_status = 'modified_offline', dirty_flag = 1, is_deleted = 0
                    WHERE id = ?
                    """,
                    (local_id,),
                )
                self.sqlite_conn.commit()
                safe_print(
                    f"INFO: [Repository] ØªÙ… Ø¥Ø¹Ø§Ø¯Ø© Ø¥Ø­ÙŠØ§Ø¡ Ù…Ø³ØªØ®Ø¯Ù…: {user.username} (SQLite ÙÙ‚Ø·)"
                )
            else:
                safe_print(
                    f"INFO: [Repository] ØªÙ… Ø¥Ù†Ø´Ø§Ø¡ Ù…Ø³ØªØ®Ø¯Ù…: {user.username} (SQLite ÙÙ‚Ø·)"
                )
            return local_id

        except Exception as e:
            safe_print(f"ERROR: [Repository] فشل إنشاء المستخدم: {e}")
            raise

    def _build_user_model(self, raw_user_data: dict[str, Any], default_id: str | None = None):
        user_class, user_role_class = _get_auth_models()
        if user_class is None or user_role_class is None:
            return None

        from dataclasses import fields as dataclass_fields

        user_data = dict(raw_user_data or {})
        mongo_object_id = user_data.pop("_id", None)
        mongo_id = user_data.pop("mongo_id", None)
        legacy_mongo_id = user_data.pop("_mongo_id", None)
        if mongo_object_id not in (None, ""):
            mongo_id = str(mongo_object_id)
        elif mongo_id not in (None, ""):
            mongo_id = str(mongo_id)
        elif legacy_mongo_id not in (None, ""):
            mongo_id = str(legacy_mongo_id)
        else:
            mongo_id = None

        if default_id is None:
            default_id = user_data.get("id")
        if default_id not in (None, ""):
            default_id = str(default_id)
        elif mongo_id:
            default_id = mongo_id
        else:
            default_id = None

        role_value = user_data.get("role", "sales")
        if isinstance(role_value, str):
            user_data["role"] = user_role_class(role_value)

        for field_name in ("created_at", "last_modified", "last_login"):
            field_value = user_data.get(field_name)
            if field_value and hasattr(field_value, "isoformat"):
                user_data[field_name] = field_value.isoformat()
            elif field_value is not None and not isinstance(field_value, str):
                user_data[field_name] = str(field_value)

        custom_permissions = user_data.get("custom_permissions")
        if isinstance(custom_permissions, str) and custom_permissions.strip():
            try:
                user_data["custom_permissions"] = json.loads(custom_permissions)
            except (json.JSONDecodeError, TypeError):
                user_data["custom_permissions"] = None

        user_data["id"] = default_id
        user_data["mongo_id"] = mongo_id
        if "is_active" in user_data:
            user_data["is_active"] = bool(user_data["is_active"])

        allowed_fields = {field.name for field in dataclass_fields(user_class)}
        filtered_data = {key: value for key, value in user_data.items() if key in allowed_fields}
        return user_class(**filtered_data)

    def get_user_by_username(self, username: str):
        """جلب مستخدم بالاسم"""
        try:
            user_class, user_role_class = _get_auth_models()
            if user_class is None or user_role_class is None:
                safe_print("ERROR: [Repository] auth_models غير متوفرة")
                return None
            # البحث في MongoDB أولاً
            if self.online:
                try:
                    user_data = self.mongo_db.users.find_one(
                        self._merge_active_filter_mongo({"username": username})
                    )
                    if user_data:
                        return self._build_user_model(user_data)
                except Exception as e:
                    safe_print(f"WARNING: [Repository] فشل جلب المستخدم من MongoDB: {e}")

            # البحث في SQLite
            self.sqlite_cursor.execute(
                f"SELECT * {self._is_active_filter_sql('users')} AND username = ?",
                (username,),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return self._build_user_model(dict(row), default_id=str(row["id"]))

            return None
        except Exception as e:
            safe_print(f"ERROR: [Repository] فشل جلب المستخدم: {e}")
            return None

    def update_user_by_username(self, username: str, update_data: dict) -> bool:
        """تحديث بيانات مستخدم باستخدام اسم المستخدم (أكثر أماناً)"""
        try:
            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            safe_print(f"INFO: [Repository] جاري تحديث المستخدم: {username}")
            safe_print(f"INFO: [Repository] البيانات المراد تحديثها: {update_data}")

            # تحديث في SQLite
            active_user_filter = (
                "username = ? "
                "AND (sync_status != 'deleted' OR sync_status IS NULL) "
                "AND (is_deleted = 0 OR is_deleted IS NULL)"
            )
            update_data_copy = update_data.copy()
            update_data_copy["last_modified"] = now_iso
            update_data_copy["sync_status"] = "modified_offline"

            # تحويل القواميس إلى JSON strings للـ SQLite
            sqlite_data = update_data_copy.copy()
            for key, value in sqlite_data.items():
                if isinstance(value, dict):
                    sqlite_data[key] = json.dumps(value, ensure_ascii=False)

            # التحقق من صحة أسماء الأعمدة للحماية من SQL Injection

            valid_columns = {
                k for k in sqlite_data.keys() if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", k)
            }
            filtered_data = {k: v for k, v in sqlite_data.items() if k in valid_columns}

            set_clause = ", ".join([f"{key} = ?" for key in filtered_data.keys()])
            values = list(filtered_data.values())
            values.append(username)  # للـ WHERE clause

            sql = f"UPDATE users SET {set_clause} WHERE {active_user_filter}"

            safe_print(f"INFO: [Repository] SQL: {sql}")
            safe_print(f"INFO: [Repository] Values: {values}")

            self.sqlite_cursor.execute(sql, values)
            rows_affected = self.sqlite_cursor.rowcount
            if rows_affected <= 0:
                safe_print(f"WARNING: [Repository] المستخدم غير نشط أو محذوف منطقيًا: {username}")
                self.sqlite_conn.rollback()
                return False
            self.sqlite_cursor.execute(
                f"UPDATE users SET dirty_flag = 1, is_deleted = 0 WHERE {active_user_filter}",
                (username,),
            )
            self.sqlite_conn.commit()

            safe_print(f"INFO: [Repository] تم تحديث {rows_affected} صف في SQLite")

            # تحديث في MongoDB
            if self.online and self.mongo_db is not None:
                try:
                    mongo_update = update_data.copy()
                    mongo_update["last_modified"] = now_dt
                    mongo_update["sync_status"] = "synced"
                    mongo_update["is_deleted"] = False

                    result = self.mongo_db.users.update_one(
                        {"username": username}, {"$set": mongo_update}
                    )
                    safe_print(
                        f"INFO: [Repository] تم تحديث {result.modified_count} مستخدم في MongoDB"
                    )

                    if result and (
                        getattr(result, "matched_count", 0) > 0
                        or getattr(result, "modified_count", 0) > 0
                    ):
                        # تحديث حالة المزامنة
                        self.sqlite_cursor.execute(
                            """
                            UPDATE users
                            SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
                            WHERE username = ?
                            """,
                            (username,),
                        )
                        self.sqlite_conn.commit()

                except Exception as e:
                    safe_print(f"WARNING: [Repository] فشل تحديث المستخدم في MongoDB: {e}")

            return rows_affected > 0
        except Exception as e:
            safe_print(f"ERROR: [Repository] فشل تحديث المستخدم: {e}")

            traceback.print_exc()
            return False

    def update_user(self, user_id: str | None, update_data: dict) -> bool:
        """تحديث بيانات مستخدم باستخدام ID - يستخدم update_user_by_username داخلياً"""
        try:
            # التحقق من صحة user_id
            if not user_id:
                safe_print("WARNING: [Repository] تم تمرير user_id فارغ - تجاهل التحديث")
                return False

            safe_print(f"INFO: [Repository] جاري تحديث المستخدم بـ ID: {user_id}")
            safe_print(f"INFO: [Repository] البيانات المراد تحديثها: {update_data}")

            # أولاً: التحقق من وجود المستخدم وجلب username
            username = None
            self.sqlite_cursor.execute(
                """
                SELECT username FROM users
                WHERE (id = ? OR _mongo_id = ?)
                  AND (sync_status != 'deleted' OR sync_status IS NULL)
                  AND (is_deleted = 0 OR is_deleted IS NULL)
                """,
                (user_id, user_id),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                username = row[0]
                safe_print(f"INFO: [Repository] تم العثور على المستخدم في SQLite: {username}")
            else:
                # محاولة البحث في MongoDB
                if self.online and self.mongo_db is not None:
                    try:
                        mongo_user = self.mongo_db.users.find_one(
                            self._merge_active_filter_mongo({"_id": self._to_objectid(user_id)})
                        )
                        if mongo_user:
                            username = mongo_user.get("username")
                            safe_print(
                                f"INFO: [Repository] تم العثور على المستخدم في MongoDB: {username}"
                            )
                    except Exception as e:
                        safe_print(f"WARNING: [Repository] فشل البحث في MongoDB: {e}")

            if not username:
                safe_print(
                    f"WARNING: [Repository] المستخدم غير موجود بـ ID: {user_id} - تجاهل التحديث"
                )
                return False

            # استخدام الدالة الجديدة للتحديث باستخدام username
            return self.update_user_by_username(username, update_data)

        except Exception as e:
            safe_print(f"ERROR: [Repository] فشل تحديث المستخدم: {e}")
            return False

    def get_all_users(self):
        """جلب جميع المستخدمين من MongoDB أو SQLite - محسّن للأداء"""
        try:
            user_class, user_role_class = _get_auth_models()
            if user_class is None or user_role_class is None:
                safe_print("ERROR: [Repository] auth_models غير متوفرة")
                return []

            users = []
            users_by_key = {}

            # ⚡ تخطي الانتظار - استخدام SQLite مباشرة إذا كان MongoDB غير متصل
            # لا ننتظر اتصال MongoDB لتجنب التجميد

            # جلب من MongoDB أولاً (فقط إذا كان متصل بالفعل)
            if self.online and self.mongo_db is not None and not self._mongo_connecting:
                try:
                    users_data = list(self.mongo_db.users.find(self._merge_active_filter_mongo()))
                    for user_data in users_data:
                        try:
                            user = self._build_user_model(user_data)
                            if user is None:
                                continue
                            user_key = str(user.mongo_id or "").strip() or user.username
                            users_by_key[user_key] = user
                        except Exception as e:
                            safe_print(f"WARNING: [Repository] فشل تحويل مستخدم من MongoDB: {e}")
                            continue

                    if users_by_key:
                        safe_print(
                            f"INFO: [Repository] تم جلب {len(users_by_key)} مستخدم من MongoDB"
                        )
                except Exception as e:
                    safe_print(f"WARNING: [Repository] فشل جلب المستخدمين من MongoDB: {e}")

            # جلب من SQLite
            self.sqlite_cursor.execute(f"SELECT * {self._is_active_filter_sql('users')}")
            rows = self.sqlite_cursor.fetchall()

            for row in rows:
                try:
                    row_dict = dict(row)
                    user = self._build_user_model(row_dict, default_id=str(row_dict.get("id", "")))
                    if user is None:
                        continue
                    user_key = str(row_dict.get("_mongo_id") or "").strip() or user.username
                    users_by_key[user_key] = user
                except Exception as e:
                    safe_print(f"WARNING: [Repository] فشل تحويل مستخدم من SQLite: {e}")
                    continue

            users = list(users_by_key.values())
            safe_print(f"INFO: [Repository] ✅ تم جلب {len(users)} مستخدم")
            return users
        except Exception as e:
            safe_print(f"ERROR: [Repository] فشل جلب المستخدمين: {e}")

            traceback.print_exc()
            return []

    def sync_users_bidirectional(self) -> dict:
        """مزامنة المستخدمين ثنائية الاتجاه (من وإلى السحابة)"""
        result = {"uploaded": 0, "downloaded": 0, "errors": []}

        if not self.online or self.mongo_db is None:
            result["errors"].append("غير متصل بـ MongoDB")
            return result

        try:
            # === 1. رفع المستخدمين المحليين الجدد/المعدلين إلى السحابة ===
            safe_print("INFO: [Repository] 📤 جاري رفع المستخدمين المحليين إلى السحابة...")
            self.sqlite_cursor.execute(
                """
                SELECT * FROM users
                WHERE (
                        sync_status IN ('new_offline', 'modified_offline', 'pending')
                        OR _mongo_id IS NULL
                      )
                  AND (sync_status != 'deleted' OR sync_status IS NULL)
                  AND (is_deleted = 0 OR is_deleted IS NULL)
            """
            )
            local_pending = self.sqlite_cursor.fetchall()

            for row in local_pending:
                try:
                    user_data = dict(row)
                    username = user_data.get("username")
                    local_id = user_data.get("id")
                    local_sync_status = str(user_data.get("sync_status") or "").lower()
                    local_is_deleted = bool(user_data.get("is_deleted", 0))

                    if local_is_deleted or local_sync_status == "deleted":
                        continue

                    existing_cloud = self.mongo_db.users.find_one({"username": username})

                    if existing_cloud:
                        mongo_id = str(existing_cloud["_id"])
                        update_data = {
                            "full_name": user_data.get("full_name"),
                            "email": user_data.get("email"),
                            "role": user_data.get("role"),
                            "is_active": bool(user_data.get("is_active", 1)),
                            "last_modified": datetime.now(),
                            "sync_status": "synced",
                            "is_deleted": False,
                        }
                        if user_data.get("password_hash"):
                            update_data["password_hash"] = user_data["password_hash"]

                        update_result = self.mongo_db.users.update_one(
                            {"_id": existing_cloud["_id"]}, {"$set": update_data}
                        )
                        if update_result and (
                            getattr(update_result, "matched_count", 0) > 0
                            or getattr(update_result, "modified_count", 0) > 0
                        ):
                            self.sqlite_cursor.execute(
                                """
                                UPDATE users
                                SET _mongo_id=?, sync_status='synced', dirty_flag = 0, is_deleted = 0
                                WHERE id=?
                                """,
                                (mongo_id, local_id),
                            )
                            result["uploaded"] += 1
                            safe_print(
                                f"INFO: [Repository]   ✅ تم تحديث المستخدم في السحابة: {username}"
                            )
                    else:
                        new_user = {
                            "username": username,
                            "password_hash": user_data.get("password_hash"),
                            "full_name": user_data.get("full_name"),
                            "email": user_data.get("email"),
                            "role": user_data.get("role", "sales"),
                            "is_active": bool(user_data.get("is_active", 1)),
                            "created_at": datetime.now(),
                            "last_modified": datetime.now(),
                            "sync_status": "synced",
                            "is_deleted": False,
                        }
                        insert_result = self.mongo_db.users.insert_one(new_user)
                        mongo_id = str(insert_result.inserted_id)
                        self.sqlite_cursor.execute(
                            """
                            UPDATE users
                            SET _mongo_id=?, sync_status='synced', dirty_flag = 0, is_deleted = 0
                            WHERE id=?
                            """,
                            (mongo_id, local_id),
                        )
                        result["uploaded"] += 1
                        safe_print(
                            f"INFO: [Repository]   ✅ تم رفع مستخدم جديد للسحابة: {username}"
                        )
                except Exception as e:
                    result["errors"].append(f"خطأ في رفع {username}: {e}")

            if result["uploaded"] > 0:
                self.sqlite_conn.commit()

            # === 2. تنزيل المستخدمين من السحابة ===
            safe_print("INFO: [Repository] 📥 جاري تنزيل المستخدمين من السحابة...")
            cloud_users = list(self.mongo_db.users.find())

            for u in cloud_users:
                try:
                    mongo_id = str(u["_id"])
                    username = u.get("username")
                    remote_sync_status = str(u.get("sync_status") or "").lower()
                    remote_is_deleted = bool(u.get("is_deleted", False)) or (
                        remote_sync_status == "deleted"
                    )

                    for field in ["created_at", "last_modified", "last_login"]:
                        if field in u and hasattr(u[field], "isoformat"):
                            u[field] = u[field].isoformat()

                    self.sqlite_cursor.execute(
                        "SELECT id, sync_status FROM users WHERE _mongo_id = ? OR username = ?",
                        (mongo_id, username),
                    )
                    exists = self.sqlite_cursor.fetchone()

                    if remote_is_deleted:
                        if exists and exists[1] not in ("modified_offline", "new_offline"):
                            self.sqlite_cursor.execute(
                                """
                                UPDATE users SET
                                    _mongo_id=?, sync_status='deleted', dirty_flag = 0,
                                    is_deleted = 1, last_modified=?
                                WHERE id=?
                                """,
                                (
                                    mongo_id,
                                    u.get("last_modified", datetime.now().isoformat()),
                                    exists[0],
                                ),
                            )
                            result["downloaded"] += 1
                        continue

                    if exists:
                        if exists[1] not in ("modified_offline", "new_offline"):
                            self.sqlite_cursor.execute(
                                """
                                UPDATE users SET
                                    full_name=?, email=?, role=?, is_active=?,
                                    password_hash=?, _mongo_id=?, sync_status='synced',
                                    dirty_flag = 0, is_deleted = 0, last_modified=?
                                WHERE id=?
                            """,
                                (
                                    u.get("full_name"),
                                    u.get("email"),
                                    u.get("role"),
                                    u.get("is_active", 1),
                                    u.get("password_hash"),
                                    mongo_id,
                                    u.get("last_modified", datetime.now().isoformat()),
                                    exists[0],
                                ),
                            )
                            result["downloaded"] += 1
                    else:
                        self.sqlite_cursor.execute(
                            """
                            INSERT INTO users (
                                _mongo_id, username, full_name, email, role,
                                password_hash, is_active, sync_status, created_at, last_modified,
                                dirty_flag, is_deleted
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'synced', ?, ?, 0, 0)
                        """,
                            (
                                mongo_id,
                                username,
                                u.get("full_name"),
                                u.get("email"),
                                u.get("role"),
                                u.get("password_hash"),
                                u.get("is_active", 1),
                                u.get("created_at", datetime.now().isoformat()),
                                u.get("last_modified", datetime.now().isoformat()),
                            ),
                        )
                        result["downloaded"] += 1
                        safe_print(f"INFO: [Repository]   ✅ تم تنزيل مستخدم جديد: {username}")
                except Exception as e:
                    result["errors"].append(f"خطأ في تنزيل {username}: {e}")

            self.sqlite_conn.commit()
            safe_print(
                f"INFO: [Repository] ✅ تم مزامنة المستخدمين (رفع: {result['uploaded']}, تنزيل: {result['downloaded']})"
            )

        except Exception as e:
            result["errors"].append(str(e))
            safe_print(f"ERROR: [Repository] فشل مزامنة المستخدمين: {e}")

        return result

    def update_account(
        self, account_id: str, account_data: schemas.Account
    ) -> schemas.Account | None:
        """⚡ تحديث بيانات حساب - محلي أولاً ثم مزامنة في الخلفية"""
        safe_print(f"INFO: [Repo] جاري تحديث الحساب ID: {account_id}")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        account_data.last_modified = now_dt
        account_data.sync_status = "modified_offline"

        try:
            account_id_num = int(account_id)
        except ValueError:
            account_id_num = 0

        currency_value = account_data.currency.value if account_data.currency else "EGP"
        parent_value = account_data.parent_id or account_data.parent_code

        # ⚡ إصلاح: دعم البحث بالـ code أيضاً
        sql = """
            UPDATE accounts SET
                name = ?, code = ?, type = ?, parent_id = ?, status = ?,
                balance = ?, currency = ?, description = ?,
                last_modified = ?, sync_status = 'modified_offline',
                is_deleted = 0, dirty_flag = 1
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
            safe_print("INFO: [Repo] ✅ تم تحديث الحساب محلياً")
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث الحساب (SQLite): {e}")

        self.sqlite_cursor.execute(
            "SELECT id, _mongo_id, code FROM accounts WHERE id = ? OR _mongo_id = ? OR code = ?",
            (account_id_num, account_id, account_id),
        )
        row = self.sqlite_cursor.fetchone()
        local_account_id = row["id"] if row else account_id_num
        mongo_account_id = str(
            (
                row["_mongo_id"]
                if row and row["_mongo_id"]
                else getattr(account_data, "_mongo_id", None) or account_id
            )
            or ""
        ).strip()
        resolved_account_code = str(
            (row["code"] if row and row["code"] else account_data.code or account_id) or ""
        ).strip()
        account_data.id = local_account_id

        # ⚡ مزامنة مع MongoDB في الخلفية (لا يعطل الواجهة)
        if self.online:

            def sync_to_mongo():
                try:
                    update_dict = account_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                    update_dict["type"] = account_data.type.value
                    update_dict["status"] = account_data.status.value
                    update_dict["last_modified"] = now_dt
                    update_dict["sync_status"] = "synced"
                    update_dict["is_deleted"] = False

                    # ⚡ إصلاح: دعم البحث بالـ code أيضاً
                    result = self.mongo_db.accounts.update_one(
                        {
                            "$or": [
                                {"_id": self._to_objectid(mongo_account_id)},
                                {"_id": self._to_objectid(account_id)},
                                {"_mongo_id": mongo_account_id},
                                {"_mongo_id": account_id},
                                {"id": local_account_id},
                                {"code": resolved_account_code},
                                {"code": account_data.code},
                                {"code": account_id},
                            ]
                        },
                        {"$set": update_dict},
                    )
                    if result and (
                        getattr(result, "matched_count", 0) > 0
                        or getattr(result, "modified_count", 0) > 0
                    ):
                        self.sqlite_cursor.execute(
                            """
                            UPDATE accounts
                            SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
                            WHERE id = ? OR _mongo_id = ? OR code = ?
                            """,
                            (local_account_id, mongo_account_id, resolved_account_code),
                        )
                        self.sqlite_conn.commit()
                        safe_print("INFO: [Repo] ✅ تم مزامنة الحساب مع السيرفر (خلفية)")
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل مزامنة الحساب مع السيرفر: {e}")

            QTimer.singleShot(100, sync_to_mongo)

        self.invalidate_table_cache("accounts")
        return account_data

    def archive_account_by_id(self, account_id: str) -> bool:
        """(جديدة) أرشفة حساب (Soft Delete)."""
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

    def update_account_balance(self, account_code: str, new_balance: float) -> bool:
        """⚡ تحديث رصيد حساب بالكود - سريع ومباشر"""
        safe_print(f"INFO: [Repo] تحديث رصيد الحساب {account_code}: {new_balance}")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        """
                        UPDATE accounts SET balance = ?, last_modified = ?, sync_status = 'modified_offline'
                        WHERE code = ?
                    """,
                        (new_balance, now_iso, account_code),
                    )
                    self.sqlite_conn.commit()
                finally:
                    cursor.close()

            # مزامنة مع MongoDB
            if self.online and self.mongo_db is not None:
                try:
                    accounts_collection = self.mongo_db.accounts
                    update_payload = {
                        "$set": {
                            "balance": new_balance,
                            "last_modified": now_dt,
                            "sync_status": "synced",
                            "is_deleted": False,
                        }
                    }
                    if hasattr(accounts_collection, "update_many"):
                        result = accounts_collection.update_many(
                            {"code": account_code},
                            update_payload,
                        )
                    else:
                        result = accounts_collection.update_one(
                            {"code": account_code},
                            update_payload,
                        )
                    if result and (
                        getattr(result, "matched_count", 0) > 0
                        or getattr(result, "modified_count", 0) > 0
                    ):
                        with self._lock:
                            cursor = self.sqlite_conn.cursor()
                            try:
                                cursor.execute(
                                    """
                                    UPDATE accounts
                                    SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
                                    WHERE code = ?
                                    """,
                                    (account_code,),
                                )
                                self.sqlite_conn.commit()
                            finally:
                                cursor.close()
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل مزامنة الرصيد مع MongoDB: {e}")

            self.invalidate_table_cache("accounts")
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث رصيد الحساب: {e}")
            return False

    def delete_account_permanently(self, account_id: str) -> bool:
        """⚡ حذف حساب نهائياً - محلي أولاً ثم مزامنة في الخلفية"""
        safe_print(f"INFO: [Repo] جاري حذف الحساب نهائياً ID: {account_id}")
        try:
            # محاولة تحويل account_id إلى رقم
            try:
                account_id_num = int(account_id)
            except (ValueError, TypeError):
                account_id_num = -1

            self.sqlite_cursor.execute(
                "SELECT id, _mongo_id, code FROM accounts WHERE id = ? OR _mongo_id = ? OR code = ?",
                (account_id_num, account_id, account_id),
            )
            row = self.sqlite_cursor.fetchone()
            local_id = row[0] if row else account_id_num
            mongo_id = row[1] if row and row[1] else account_id
            account_code = row[2] if row and row[2] else account_id

            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            if self.online:
                try:
                    result = self.mongo_db.accounts.update_one(
                        {
                            "$or": [
                                {"_id": self._to_objectid(mongo_id)},
                                {"_id": self._to_objectid(account_id)},
                                {"_mongo_id": mongo_id},
                                {"_mongo_id": account_id},
                                {"id": local_id},
                                {"code": account_code},
                                {"code": account_id},
                            ]
                        },
                        {
                            "$set": {
                                "is_deleted": True,
                                "sync_status": "deleted",
                                "last_modified": now_dt,
                            }
                        },
                    )

                    if getattr(result, "matched_count", 0) > 0:
                        self.sqlite_cursor.execute(
                            "DELETE FROM accounts WHERE id = ? OR _mongo_id = ? OR code = ?",
                            (local_id, mongo_id, account_code),
                        )
                        self.sqlite_conn.commit()
                        self.invalidate_table_cache("accounts")
                        safe_print("INFO: [Repo] ✅ تم تعليم حذف الحساب ثم حذفه محلياً")
                        return True
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل تعليم حذف الحساب في MongoDB: {e}")

            self.sqlite_cursor.execute(
                """
                UPDATE accounts
                SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                WHERE id = ? OR _mongo_id = ? OR code = ?
                """,
                (now_iso, local_id, mongo_id, account_code),
            )
            self.sqlite_conn.commit()
            self.invalidate_table_cache("accounts")
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف الحساب: {e}")
            return False

    def delete_all_accounts(self) -> bool:
        """حذف جميع الحسابات وقيود اليومية نهائياً لاستخدام مسارات reset المقصودة."""
        safe_print("INFO: [Repo] جاري حذف جميع الحسابات وقيود اليومية...")
        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute("DELETE FROM journal_entries")
                    cursor.execute("DELETE FROM accounts")
                    self.sqlite_conn.commit()
                finally:
                    cursor.close()

            if self.online and self.mongo_db is not None:
                try:
                    self.mongo_db.journal_entries.delete_many({})
                    self.mongo_db.accounts.delete_many({})
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل حذف الحسابات/القيود من MongoDB: {e}")

            self.invalidate_table_cache("accounts")
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف جميع الحسابات: {e}")
            return False

    # --- دوال التعامل مع الفواتير ---

    def create_invoice(self, invoice_data: schemas.Invoice) -> schemas.Invoice:
        """إنشاء فاتورة جديدة (بذكاء)"""
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        invoice_data.created_at = now_dt
        invoice_data.last_modified = now_dt
        invoice_data.sync_status = "new_offline"
        self._normalize_invoice_write_fields(invoice_data)

        items_json = json.dumps([item.model_dump() for item in invoice_data.items])

        sql = """
            INSERT INTO invoices (
                _mongo_id, sync_status, created_at, last_modified, invoice_number,
                client_id, project_id, issue_date, due_date, items,
                subtotal, discount_rate, discount_amount, tax_rate, tax_amount,
                total_amount, amount_paid, status, currency, notes,
                dirty_flag, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
        """
        params = (
            None,
            invoice_data.sync_status,
            now_iso,
            now_iso,
            invoice_data.invoice_number,
            invoice_data.client_id,
            invoice_data.project_id,
            invoice_data.issue_date.isoformat(),
            invoice_data.due_date.isoformat(),
            items_json,
            invoice_data.subtotal,
            invoice_data.discount_rate,
            invoice_data.discount_amount,
            invoice_data.tax_rate,
            invoice_data.tax_amount,
            invoice_data.total_amount,
            invoice_data.amount_paid,
            invoice_data.status.value,
            invoice_data.currency.value,
            invoice_data.notes,
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        invoice_data.id = local_id
        safe_print(f"INFO: تم حفظ الفاتورة '{invoice_data.invoice_number}' محلياً (ID: {local_id}).")

        if self.online:
            try:
                invoice_dict = invoice_data.model_dump(exclude={"_mongo_id", "id"})
                invoice_dict["status"] = invoice_data.status.value
                invoice_dict["currency"] = invoice_data.currency.value
                invoice_dict["issue_date"] = invoice_data.issue_date
                invoice_dict["due_date"] = invoice_data.due_date
                invoice_dict["notes"] = invoice_data.notes
                invoice_dict["project_id"] = invoice_data.project_id

                result = self.mongo_db.invoices.insert_one(invoice_dict)
                mongo_id = str(result.inserted_id)

                invoice_data._mongo_id = mongo_id
                invoice_data.sync_status = "synced"

                self.sqlite_cursor.execute(
                    "UPDATE invoices SET _mongo_id = ?, sync_status = ?, dirty_flag = 0 WHERE id = ?",
                    (mongo_id, "synced", local_id),
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة الفاتورة '{invoice_data.invoice_number}' أونلاين.")

            except Exception as e:
                safe_print(
                    f"ERROR: فشل مزامنة الفاتورة الجديدة '{invoice_data.invoice_number}': {e}"
                )

        return invoice_data

    def get_all_invoices(self) -> list[schemas.Invoice]:
        """جلب كل الفواتير (بذكاء)"""
        invoices_by_key: dict[str, schemas.Invoice] = {}

        if self.online and self.mongo_db is not None:
            try:
                invoices_data = list(self.mongo_db.invoices.find(self._merge_active_filter_mongo()))
                for inv in invoices_data:
                    mongo_id = str(inv.pop("_id"))
                    inv.pop("_mongo_id", None)
                    inv.pop("mongo_id", None)
                    if isinstance(inv.get("items"), str):
                        inv["items"] = json.loads(inv["items"])
                    invoice = schemas.Invoice(**inv, _mongo_id=mongo_id)
                    invoice_key = str(inv.get("invoice_number") or mongo_id or "").strip()
                    if invoice_key:
                        invoices_by_key[invoice_key] = invoice
                if invoices_by_key:
                    safe_print(
                        f"INFO: تم جلب {len(invoices_by_key)} فاتورة من الأونلاين (MongoDB)."
                    )
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الفواتير من Mongo: {e}. سيتم الدمج مع المحلي فقط.")

        self.sqlite_cursor.execute(
            "SELECT * FROM invoices WHERE (sync_status != 'deleted' OR sync_status IS NULL) AND (is_deleted = 0 OR is_deleted IS NULL)"
        )
        rows = self.sqlite_cursor.fetchall()
        for row in rows:
            row_dict = dict(row)
            if isinstance(row_dict.get("items"), str):
                row_dict["items"] = json.loads(row_dict["items"])
            invoice = schemas.Invoice(**row_dict)
            invoice_key = str(
                row_dict.get("invoice_number") or row_dict.get("_mongo_id") or ""
            ).strip()
            if invoice_key:
                invoices_by_key[invoice_key] = invoice

        invoices_list = list(invoices_by_key.values())
        safe_print(f"INFO: تم جلب {len(invoices_list)} فاتورة.")
        return invoices_list

    def _resolve_local_client_row(self, client_ref: Any) -> dict[str, Any] | None:
        reference = normalize_user_text(client_ref)
        if not reference:
            return None

        with self._lock:
            cursor = self.sqlite_conn.cursor()
            try:
                cursor.execute(
                    f"SELECT * {self._is_active_filter_sql('clients')} AND (id = ? OR _mongo_id = ? OR name = ?)",
                    (reference, reference, reference),
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

                reference_key = self._normalized_key(reference)
                cursor.execute(f"SELECT * {self._is_active_filter_sql('clients')}")
                rows = cursor.fetchall()
            finally:
                cursor.close()

        for row in rows:
            row_dict = dict(row)
            if self._normalized_key(row_dict.get("name")) == reference_key:
                return row_dict
        return None

    def _client_reference_values(self, client_ref: Any) -> set[str]:
        references: set[str] = set()
        normalized_ref = normalize_user_text(client_ref)
        if not normalized_ref:
            return references

        references.add(normalized_ref)

        local_client = self._resolve_local_client_row(normalized_ref)
        if local_client is not None:
            for field in ("id", "_mongo_id", "name"):
                value = str(local_client.get(field) or "").strip()
                if value:
                    references.add(value)

        if local_client is None:
            try:
                client = self.get_client_by_id(normalized_ref)
            except Exception:
                client = None

            if client is not None:
                for field in ("id", "_mongo_id", "name"):
                    value = str(getattr(client, field, None) or "").strip()
                    if value:
                        references.add(value)

        return {str(value).strip() for value in references if str(value).strip()}

    @staticmethod
    def _stable_client_reference(
        client: schemas.Client | dict[str, Any] | None, fallback: Any = ""
    ) -> str:
        if client is not None:
            for field in ("_mongo_id", "id", "name"):
                if isinstance(client, dict):
                    value = str(client.get(field) or "").strip()
                else:
                    value = str(getattr(client, field, None) or "").strip()
                if value:
                    return value
        normalized_fallback = normalize_user_text(fallback)
        if normalized_fallback:
            return normalized_fallback
        return str(fallback or "").strip()

    def _normalize_client_reference(self, client_ref: Any) -> str:
        reference = normalize_user_text(client_ref)
        if not reference:
            return ""

        try:
            client = self.get_client_by_id(reference)
        except Exception:
            client = None

        return self._stable_client_reference(client, reference)

    def _normalize_local_client_reference(self, client_ref: Any) -> str | None:
        reference = normalize_user_text(client_ref)
        if not reference:
            return None

        client_row = self._resolve_local_client_row(reference)
        if not client_row:
            return None

        local_id = str(client_row.get("id") or "").strip()
        return local_id or None

    def get_invoices_by_client(self, client_id: str) -> list[schemas.Invoice]:
        """جلب فواتير عميل مع دعم local id / mongo id / الاسم."""
        client_references = self._client_reference_values(client_id)
        if not client_references:
            return []

        normalized_references = {
            normalize_user_text(reference)
            for reference in client_references
            if normalize_user_text(reference)
        }

        return [
            invoice
            for invoice in self.get_all_invoices()
            if normalize_user_text(getattr(invoice, "client_id", "")) in normalized_references
        ]

    # --- دوال التعامل مع قيود اليومية ---

    def create_journal_entry(self, entry_data: schemas.JournalEntry) -> schemas.JournalEntry:
        """إنشاء قيد يومية جديد (بذكاء)"""
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        entry_data.created_at = now_dt
        entry_data.last_modified = now_dt
        entry_data.sync_status = "new_offline"

        # 1. الحفظ في SQLite (الأوفلاين أولاً)
        lines_json = json.dumps([line.model_dump() for line in entry_data.lines])

        sql = """
            INSERT INTO journal_entries (
                _mongo_id, sync_status, created_at, last_modified, date,
                description, lines, related_document_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            None,
            entry_data.sync_status,
            now_iso,
            now_iso,
            entry_data.date.isoformat(),
            entry_data.description,
            lines_json,
            entry_data.related_document_id,
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        entry_data.id = local_id
        safe_print(
            f"INFO: تم حفظ قيد اليومية '{entry_data.description[:20]}...' محلياً (ID: {local_id})."
        )

        # 2. محاولة الحفظ في MongoDB (الأونلاين)
        if self.online:
            try:
                entry_dict = entry_data.model_dump(exclude={"_mongo_id"})
                entry_dict["date"] = entry_data.date  # ضمان إرسال التاريخ كـ datetime

                result = self.mongo_db.journal_entries.insert_one(entry_dict)
                mongo_id = str(result.inserted_id)

                entry_data._mongo_id = mongo_id
                entry_data.sync_status = "synced"

                self.sqlite_cursor.execute(
                    "UPDATE journal_entries SET _mongo_id = ?, sync_status = ?, dirty_flag = 0 WHERE id = ?",
                    (mongo_id, "synced", local_id),
                )
                self.sqlite_conn.commit()
                safe_print(
                    f"INFO: تم مزامنة قيد اليومية '{entry_data.description[:20]}...' أونلاين."
                )

            except Exception as e:
                safe_print(f"ERROR: فشل مزامنة قيد اليومية الجديد: {e}")

        return entry_data

    def _row_to_journal_entry(self, row: Any) -> schemas.JournalEntry | None:
        row_dict = dict(row)
        lines_value = row_dict.get("lines")
        if isinstance(lines_value, str):
            try:
                row_dict["lines"] = json.loads(lines_value)
            except json.JSONDecodeError:
                row_dict["lines"] = []
        elif lines_value is None:
            row_dict["lines"] = []
        elif not isinstance(lines_value, list):
            row_dict["lines"] = list(lines_value)

        # إصلاح البيانات القديمة: بعض الأسطر كانت تُخزن بدون account_id.
        fixed_lines = []
        for line in row_dict.get("lines", []):
            if isinstance(line, dict):
                if "account_id" not in line or not line.get("account_id"):
                    line["account_id"] = (
                        line.get("account_code", "") or line.get("account_name", "") or "unknown"
                    )
                fixed_lines.append(line)
        row_dict["lines"] = fixed_lines

        try:
            return schemas.JournalEntry(**row_dict)
        except Exception as entry_error:
            safe_print(f"WARNING: تخطي قيد فاسد: {entry_error}")
            return None

    def get_all_journal_entries(self) -> list[schemas.JournalEntry]:
        """⚡ جلب كل قيود اليومية (SQLite أولاً للسرعة)"""
        # ⚡ جلب من SQLite أولاً (سريع جداً) - استخدام cursor منفصل
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    f"SELECT * {self._is_active_filter_sql('journal_entries')} ORDER BY date DESC"
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()

            entries_list = []
            for row in rows:
                entry = self._row_to_journal_entry(row)
                if entry is not None:
                    entries_list.append(entry)

            safe_print(f"INFO: تم جلب {len(entries_list)} قيد من المحلي.")
            return entries_list
        except Exception as e:
            safe_print(f"ERROR: فشل جلب القيود من SQLite: {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                entries_data = list(
                    self.mongo_db.journal_entries.find(self._merge_active_filter_mongo()).sort(
                        "date", -1
                    )
                )
                entries_list = []
                for entry in entries_data:
                    mongo_id = str(entry.pop("_id"))
                    entry.pop("_mongo_id", None)
                    entry.pop("mongo_id", None)
                    normalized_entry = self._row_to_journal_entry({**entry, "_mongo_id": mongo_id})
                    if normalized_entry is not None:
                        entries_list.append(normalized_entry)
                safe_print("INFO: تم جلب قيود اليومية من الأونلاين (MongoDB).")
                return entries_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب قيود اليومية من Mongo: {e}")

        return []

    def get_journal_entries_before(self, before_iso: str) -> list[schemas.JournalEntry]:
        """⚡ جلب قيود اليومية قبل تاريخ محدد (SQLite أولاً للسرعة)"""
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    f"""
                    SELECT * {self._is_active_filter_sql('journal_entries')}
                    AND date < ?
                    ORDER BY date ASC
                    """,
                    (before_iso,),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()

            entries_list: list[schemas.JournalEntry] = []
            for row in rows:
                entry = self._row_to_journal_entry(row)
                if entry is not None:
                    entries_list.append(entry)

            return entries_list
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب قيود اليومية قبل تاريخ (SQLite): {e}")
            return []

    def get_journal_entries_between(
        self, start_iso: str, end_iso: str
    ) -> list[schemas.JournalEntry]:
        """⚡ جلب قيود اليومية في فترة زمنية (SQLite أولاً للسرعة)"""
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT * FROM journal_entries
                    WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    AND date >= ? AND date <= ?
                    ORDER BY date ASC
                """,
                    (start_iso, end_iso),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()

            entries_list: list[schemas.JournalEntry] = []
            for row in rows:
                entry = self._row_to_journal_entry(row)
                if entry is not None:
                    entries_list.append(entry)

            return entries_list
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب قيود اليومية في فترة (SQLite): {e}")
            return []

    def get_journal_entry_by_doc_id(self, doc_id: str) -> schemas.JournalEntry | None:
        """(جديدة) جلب قيد يومية عن طريق ID الفاتورة/المصروف المرتبط به"""
        if self.online:
            try:
                data = self.mongo_db.journal_entries.find_one(
                    self._merge_active_filter_mongo({"related_document_id": doc_id})
                )
                if data:
                    mongo_id = str(data.pop("_id"))
                    data.pop("_mongo_id", None)
                    data.pop("mongo_id", None)
                    return self._row_to_journal_entry({**data, "_mongo_id": mongo_id})
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب القيد (Mongo): {e}")

        try:
            self.sqlite_cursor.execute(
                """
                SELECT * FROM journal_entries
                WHERE related_document_id = ?
                AND (sync_status != 'deleted' OR sync_status IS NULL)
                AND (is_deleted = 0 OR is_deleted IS NULL)
                """,
                (doc_id,),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return self._row_to_journal_entry(row)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب القيد (SQLite): {e}")

        return None

    # --- دوال التعامل مع الدفعات ---

    def create_payment(self, payment_data: schemas.Payment) -> schemas.Payment:
        """(معدلة) إنشاء دفعة جديدة (مربوطة بمشروع) مع فحص التكرار وقفل المعاملة"""
        # ⚡ قفل المعاملة لمنع التكرار من الضغط المزدوج
        with self._lock:
            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            # توحيد مرجع المشروع إلى مرجع ثابت لتجنب خلط الأسماء المكررة.
            requested_project_ref = str(getattr(payment_data, "project_id", "") or "")
            requested_client_id = str(getattr(payment_data, "client_id", "") or "")
            resolved_project = self._resolve_project_row(requested_project_ref, requested_client_id)
            if resolved_project:
                payment_data.project_id = self._stable_project_reference(
                    resolved_project,
                    requested_project_ref,
                )
                if not requested_client_id:
                    payment_data.client_id = str(resolved_project.get("client_id") or "")
            else:
                normalized_ref = normalize_user_text(requested_project_ref)
                if self._has_ambiguous_project_name_reference(normalized_ref):
                    raise ValueError(
                        "اسم المشروع غير فريد؛ استخدم معرف المشروع أو client_id الصحيح"
                    )
                if normalized_ref:
                    payment_data.project_id = normalized_ref

            payment_data.invoice_number = (
                self.ensure_invoice_number(payment_data.project_id, payment_data.client_id)
                or str(getattr(payment_data, "invoice_number", "") or "").strip()
            )

            # ✅ فحص التكرار قبل الإضافة (نفس المشروع + نفس التاريخ + نفس المبلغ)
            existing_payment = self._get_duplicate_payment(
                payment_data.project_id,
                payment_data.date,
                payment_data.amount,
                client_id=payment_data.client_id,
            )
            if existing_payment:
                safe_print(
                    f"WARNING: دفعة مكررة! (المشروع: {payment_data.project_id}, التاريخ: {payment_data.date}, المبلغ: {payment_data.amount})"
                )
                raise ValueError(
                    f"يوجد دفعة بنفس البيانات (المبلغ: {payment_data.amount} - التاريخ: {payment_data.date})"
                )

            payment_data.created_at = now_dt
            payment_data.last_modified = now_dt
            payment_data.sync_status = "new_offline"

            # 1. الحفظ في SQLite (الأوفلاين أولاً) - داخل transaction
            try:
                # ⚡ بدء transaction صريح
                self.sqlite_cursor.execute("BEGIN IMMEDIATE")

                sql = """
                    INSERT INTO payments (
                        sync_status, created_at, last_modified, project_id, client_id,
                        invoice_number, date, amount, account_id, method, dirty_flag, is_deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
                """
                params = (
                    payment_data.sync_status,
                    now_iso,
                    now_iso,
                    payment_data.project_id,
                    payment_data.client_id,
                    payment_data.invoice_number,
                    payment_data.date.isoformat(),
                    payment_data.amount,
                    payment_data.account_id,
                    payment_data.method,
                )

                self.sqlite_cursor.execute(sql, params)
                local_id = self.sqlite_cursor.lastrowid

                # ⚡ تأكيد المعاملة
                self.sqlite_cursor.execute("COMMIT")

                payment_data.id = local_id
                safe_print(
                    f"INFO: تم حفظ الدفعة (للمشروع {payment_data.project_id}) محلياً (ID: {local_id})."
                )
            except Exception as e:
                # ⚡ التراجع في حالة الخطأ
                try:
                    self.sqlite_cursor.execute("ROLLBACK")
                except Exception:
                    # فشل الـ rollback
                    pass
                raise e

        # 2. محاولة الحفظ في MongoDB (الأونلاين)
        if self.online:
            try:
                payment_dict = payment_data.model_dump(exclude={"_mongo_id", "id"})
                payment_dict["date"] = payment_data.date

                result = self.mongo_db.payments.insert_one(payment_dict)
                mongo_id = str(result.inserted_id)

                payment_data._mongo_id = mongo_id
                payment_data.sync_status = "synced"

                self.sqlite_cursor.execute(
                    "UPDATE payments SET _mongo_id = ?, sync_status = ?, dirty_flag = 0 WHERE id = ?",
                    (mongo_id, "synced", payment_data.id),
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة الدفعة (Mongo ID: {mongo_id}) أونلاين.")

            except Exception as e:
                safe_print(f"ERROR: فشل مزامنة الدفعة الجديدة: {e}")

        self.invalidate_table_cache("payments")

        return payment_data

    def get_payments_for_project(
        self, project_name: str, client_id: str | None = None
    ) -> list[schemas.Payment]:
        """
        جلب كل الدفعات المرتبطة بمشروع مع دعم الربط القديم
        (اسم مشروع / local id / mongo id / فروقات مسافات).
        """
        requested = normalize_user_text(project_name)
        if not requested:
            return []

        resolved_project, canonical_project_name, aliases, target_client_id = (
            self._resolve_project_context(requested, client_id)
        )
        if not resolved_project or not canonical_project_name:
            # مرجع غير معروف أو غامض (مثلاً project_code مكرر) -> لا نغامر بربط خاطئ.
            return []

        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(f"SELECT * {self._is_active_filter_sql('payments')}")
                    rows = [dict(row) for row in cursor.fetchall()]
                finally:
                    cursor.close()

            matching_rows = [
                row
                for row in rows
                if self._row_matches_project_scope(
                    row.get("project_id"),
                    canonical_project_name,
                    aliases,
                    target_client_id=target_client_id,
                    row_client_id=row.get("client_id"),
                )
            ]
            deduped_rows = self._dedupe_rows_by_signature(matching_rows, self._payment_signature)
            deduped_rows.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
            return [schemas.Payment(**row) for row in deduped_rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب دفعات المشروع (SQLite): {e}")

        if self.online:
            try:
                query_filter = (
                    {"project_id": {"$in": list(aliases)}}
                    if aliases
                    else {"project_id": canonical_project_name}
                )
                data = list(
                    self.mongo_db.payments.find(self._merge_active_filter_mongo(query_filter))
                )
                rows = []
                for item in data:
                    mongo_id = str(item.pop("_id"))
                    item.pop("_mongo_id", None)
                    item.pop("mongo_id", None)
                    item["_mongo_id"] = mongo_id
                    rows.append(item)
                rows = [
                    row
                    for row in rows
                    if self._row_matches_project_scope(
                        row.get("project_id"),
                        canonical_project_name,
                        aliases,
                        target_client_id=target_client_id,
                        row_client_id=row.get("client_id"),
                    )
                ]
                deduped_rows = self._dedupe_rows_by_signature(rows, self._payment_signature)
                deduped_rows.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
                return [schemas.Payment(**row) for row in deduped_rows]
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب دفعات المشروع (Mongo): {e}")

        return []

    def get_all_payments(self) -> list[schemas.Payment]:
        """⚡ جلب كل الدفعات (SQLite أولاً للسرعة) - مع cache ذكي"""
        if CACHE_ENABLED and hasattr(self, "_payments_cache"):
            cached_result = self._payments_cache.get("all_payments")
            if cached_result is not None:
                safe_print(f"INFO: ⚡ تم جلب {len(cached_result)} دفعة من الـ Cache")
                return cached_result

        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT * FROM payments
                    WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    ORDER BY date DESC
                    """
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
            deduped_rows = self._dedupe_rows_by_signature(
                [dict(row) for row in rows],
                self._payment_signature,
            )
            deduped_rows.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
            payments = [schemas.Payment(**row) for row in deduped_rows]
            if CACHE_ENABLED and hasattr(self, "_payments_cache"):
                self._payments_cache.set("all_payments", payments)
            safe_print(f"INFO: [Repo] تم جلب {len(payments)} دفعة من SQLite.")
            return payments
        except Exception as e:
            if self._is_sqlite_closed_error(e):
                return []
            safe_print(f"ERROR: [Repo] فشل جلب الدفعات (SQLite): {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                data = list(self.mongo_db.payments.find(self._merge_active_filter_mongo()))
                rows = []
                for d in data:
                    mongo_id = str(d.pop("_id"))
                    d.pop("_mongo_id", None)
                    d.pop("mongo_id", None)
                    d["_mongo_id"] = mongo_id
                    rows.append(d)
                deduped_rows = self._dedupe_rows_by_signature(rows, self._payment_signature)
                deduped_rows.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
                payments = [schemas.Payment(**row) for row in deduped_rows]
                if CACHE_ENABLED and hasattr(self, "_payments_cache"):
                    self._payments_cache.set("all_payments", payments)
                safe_print(f"INFO: [Repo] تم جلب {len(payments)} دفعة من MongoDB.")
                return payments
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب الدفعات (Mongo): {e}")

        return []

    def get_payments_by_client(self, client_id: str) -> list[schemas.Payment]:
        """جلب دفعات عميل مع دعم local id / mongo id / الاسم."""
        client_references = self._client_reference_values(client_id)
        if not client_references:
            return []

        normalized_references = {
            normalize_user_text(reference)
            for reference in client_references
            if normalize_user_text(reference)
        }

        return [
            payment
            for payment in self.get_all_payments()
            if normalize_user_text(getattr(payment, "client_id", "")) in normalized_references
        ]

    def get_total_paid_for_project(self, project_name: str, client_id: str | None = None) -> float:
        """إجمالي المدفوعات لمشروع بعد التطبيع وإزالة التكرار."""
        try:
            payments = self.get_payments_for_project(project_name, client_id=client_id)
            return float(sum(float(getattr(payment, "amount", 0.0) or 0.0) for payment in payments))
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب إجمالي الدفعات للمشروع: {e}")
            return 0.0

    def get_payments_by_account(
        self, account_code: str, start_iso: str, end_iso: str
    ) -> list[schemas.Payment]:
        """⚡ جلب دفعات حساب معين في فترة زمنية (SQLite أولاً للسرعة)"""
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    f"""
                    SELECT * {self._is_active_filter_sql('payments')}
                    AND account_id = ? AND date >= ? AND date <= ?
                    ORDER BY date ASC
                """,
                    (account_code, start_iso, end_iso),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()

            return [schemas.Payment(**dict(row)) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب دفعات الحساب (SQLite): {e}")
            return []

    def sum_payments_before(self, account_code: str, before_iso: str) -> float:
        """⚡ إجمالي الدفعات قبل تاريخ محدد"""
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0) FROM payments
                    WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    AND account_id = ? AND date < ?
                    """,
                    (account_code, before_iso),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
            return float(row[0] if row else 0.0)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب إجمالي الدفعات: {e}")
            return 0.0

    def update_payment(self, payment_id, payment_data: schemas.Payment) -> bool:
        """تعديل دفعة موجودة"""
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            # ⚡ تحديد نوع الـ ID والبحث المناسب
            if isinstance(payment_id, int) or (
                isinstance(payment_id, str) and payment_id.isdigit()
            ):
                where_clause = "WHERE id = ?"
                where_params = (int(payment_id),)
            else:
                where_clause = "WHERE _mongo_id = ?"
                where_params = (str(payment_id),)

            # ⚡ جلب الحقول بأمان
            client_id = getattr(payment_data, "client_id", "") or ""
            project_id = getattr(payment_data, "project_id", "") or ""
            existing_payment = self.get_payment_by_id(payment_id)
            if existing_payment is not None and not client_id:
                client_id = str(getattr(existing_payment, "client_id", "") or "")

            resolved_project = self._resolve_project_row(project_id, client_id)
            if resolved_project:
                project_id = self._stable_project_reference(resolved_project, project_id)
                if not client_id:
                    client_id = str(resolved_project.get("client_id") or "")
            else:
                normalized_project = normalize_user_text(project_id)
                if self._has_ambiguous_project_name_reference(normalized_project):
                    raise ValueError(
                        "اسم المشروع غير فريد؛ استخدم معرف المشروع أو client_id الصحيح"
                    )
                if normalized_project:
                    project_id = normalized_project
            payment_data.project_id = project_id
            payment_data.client_id = client_id
            payment_data.invoice_number = (
                self.ensure_invoice_number(project_id, client_id)
                or str(getattr(payment_data, "invoice_number", "") or "").strip()
            )

            existing_local_id = None
            if existing_payment is not None:
                try:
                    existing_local_id = int(getattr(existing_payment, "id", 0) or 0) or None
                except (TypeError, ValueError):
                    existing_local_id = None

            if existing_local_id:
                self._cleanup_shadow_payment_duplicates(
                    existing_local_id,
                    project_id,
                    payment_data.date,
                    payment_data.amount,
                    client_id=client_id,
                    account_id=payment_data.account_id,
                    method=payment_data.method or "",
                )

            duplicate_payment = self._get_duplicate_payment(
                project_id,
                payment_data.date,
                payment_data.amount,
                exclude_id=existing_local_id,
                client_id=client_id,
            )
            if duplicate_payment is not None:
                raise ValueError(
                    f"يوجد دفعة بنفس البيانات (المبلغ: {payment_data.amount} - التاريخ: {payment_data.date})"
                )

            sql = f"""
                UPDATE payments SET
                    last_modified = ?, date = ?, amount = ?,
                    account_id = ?, method = ?,
                    client_id = ?, project_id = ?, invoice_number = ?, sync_status = ?
                {where_clause}
            """
            params = (
                now_iso,
                payment_data.date.isoformat(),
                payment_data.amount,
                payment_data.account_id,
                payment_data.method or "",
                client_id,
                project_id,
                payment_data.invoice_number,
                "modified_offline",
            ) + where_params

            self.sqlite_cursor.execute(sql, params)
            rows_affected = self.sqlite_cursor.rowcount
            self.sqlite_conn.commit()

            if rows_affected == 0:
                return False

            if self.online:
                try:
                    payment_dict = {
                        "last_modified": now_dt,
                        "date": payment_data.date,
                        "amount": payment_data.amount,
                        "account_id": payment_data.account_id,
                        "method": payment_data.method or "",
                        "client_id": client_id,
                        "project_id": project_id,
                        "invoice_number": payment_data.invoice_number,
                        "sync_status": "synced",
                        "is_deleted": False,
                    }

                    result = None
                    mongo_id = getattr(payment_data, "_mongo_id", None) or getattr(
                        existing_payment, "_mongo_id", None
                    )
                    if mongo_id:
                        result = self.mongo_db.payments.update_one(
                            {
                                "$or": [
                                    {"_id": self._to_objectid(str(mongo_id))},
                                    {"_mongo_id": str(mongo_id)},
                                ]
                            },
                            {"$set": payment_dict},
                        )

                    if result and (
                        getattr(result, "matched_count", 0) > 0
                        or getattr(result, "modified_count", 0) > 0
                    ):
                        sync_update_sql = f"UPDATE payments SET sync_status = ?, dirty_flag = 0, is_deleted = 0 {where_clause}"  # nosec B608
                        self.sqlite_cursor.execute(sync_update_sql, ("synced",) + where_params)
                        self.sqlite_conn.commit()
                except Exception:
                    pass  # Ignore sync errors

            self.invalidate_table_cache("payments")

            return True
        except ValueError:
            raise
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تعديل الدفعة: {e}")

            traceback.print_exc()
            return False

    def get_payment_by_id(self, payment_id) -> schemas.Payment | None:
        """جلب دفعة بالـ ID"""
        try:
            self.sqlite_cursor.execute(
                f"SELECT * {self._is_active_filter_sql('payments')} AND (id = ? OR _mongo_id = ?)",
                (payment_id, str(payment_id)),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Payment(**dict(row))
            return None
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الدفعة: {e}")
            return None

    def delete_payment(self, payment_id) -> bool:
        """حذف دفعة"""
        try:
            # جلب بيانات الدفعة أولاً للحصول على _mongo_id
            self.sqlite_cursor.execute(
                "SELECT _mongo_id FROM payments WHERE id = ? OR _mongo_id = ?",
                (payment_id, str(payment_id)),
            )
            row = self.sqlite_cursor.fetchone()
            mongo_id = row["_mongo_id"] if row else None

            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            if self.online and mongo_id:
                try:
                    result = self.mongo_db.payments.update_one(
                        {"_id": self._to_objectid(mongo_id)},
                        {
                            "$set": {
                                "is_deleted": True,
                                "sync_status": "deleted",
                                "last_modified": now_dt,
                            }
                        },
                    )
                    if getattr(result, "matched_count", 0) > 0:
                        self.sqlite_cursor.execute(
                            "DELETE FROM payments WHERE id = ? OR _mongo_id = ?",
                            (payment_id, str(payment_id)),
                        )
                        self.sqlite_conn.commit()
                        safe_print("INFO: [Repo] تم تعليم حذف الدفعة ثم حذفها محلياً.")
                    else:
                        self.sqlite_cursor.execute(
                            """
                            UPDATE payments
                            SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                            WHERE id = ? OR _mongo_id = ?
                            """,
                            (now_iso, payment_id, str(payment_id)),
                        )
                        self.sqlite_conn.commit()
                except Exception as e:
                    safe_print(f"ERROR: [Repo] فشل تعليم حذف الدفعة في MongoDB: {e}")
                    self.sqlite_cursor.execute(
                        """
                        UPDATE payments
                        SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                        WHERE id = ? OR _mongo_id = ?
                        """,
                        (now_iso, payment_id, str(payment_id)),
                    )
                    self.sqlite_conn.commit()
            else:
                self.sqlite_cursor.execute(
                    """
                    UPDATE payments
                    SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                    WHERE id = ? OR _mongo_id = ?
                    """,
                    (now_iso, payment_id, str(payment_id)),
                )
                self.sqlite_conn.commit()

            self.invalidate_table_cache("payments")

            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف الدفعة: {e}")
            return False

    def update_invoice_after_payment(
        self, invoice_number: str, new_payment_amount: float
    ) -> schemas.Invoice | None:
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
                (new_amount_paid, new_status.value, now_iso, invoice_number),
            )
            self.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث الفاتورة (SQLite): {e}")

        invoice_synced = False
        if self.online:
            try:
                result = self.mongo_db.invoices.update_one(
                    {"invoice_number": invoice_number},
                    {
                        "$set": {
                            "amount_paid": new_amount_paid,
                            "status": new_status.value,
                            "last_modified": now_dt,
                            "sync_status": "synced",
                            "is_deleted": False,
                        }
                    },
                )
                if result and (
                    getattr(result, "matched_count", 0) > 0
                    or getattr(result, "modified_count", 0) > 0
                ):
                    self.sqlite_cursor.execute(
                        "UPDATE invoices SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0 WHERE invoice_number = ?",
                        (invoice_number,),
                    )
                    self.sqlite_conn.commit()
                    invoice_synced = True
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل تحديث الفاتورة (Mongo): {e}")

        invoice.amount_paid = new_amount_paid
        invoice.status = new_status
        invoice.last_modified = now_dt
        invoice.sync_status = "synced" if invoice_synced else "modified_offline"
        return invoice

    def update_invoice(
        self, invoice_number: str, invoice_data: schemas.Invoice
    ) -> schemas.Invoice | None:
        """
        (جديدة) تحديث بيانات فاتورة موجودة بالكامل.
        """
        safe_print(f"INFO: [Repo] جاري تحديث الفاتورة {invoice_number} في قاعدة البيانات...")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        self._normalize_invoice_write_fields(invoice_data)
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
                update_dict["status"] = invoice_data.status.value
                update_dict["currency"] = invoice_data.currency.value
                update_dict["last_modified"] = now_dt
                update_dict["discount_rate"] = invoice_data.discount_rate
                update_dict["discount_amount"] = invoice_data.discount_amount
                update_dict["sync_status"] = "synced"
                update_dict["is_deleted"] = False

                result = self.mongo_db.invoices.update_one(
                    {"invoice_number": invoice_number}, {"$set": update_dict}
                )

                if result and (
                    getattr(result, "matched_count", 0) > 0
                    or getattr(result, "modified_count", 0) > 0
                ):
                    self.sqlite_cursor.execute(
                        "UPDATE invoices SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0 WHERE invoice_number = ?",
                        (invoice_number,),
                    )
                    self.sqlite_conn.commit()
                    safe_print(f"INFO: [Repo] تم مزامنة تحديث الفاتورة {invoice_number} أونلاين.")

            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل تحديث الفاتورة (Mongo): {e}")

        return invoice_data

    def get_invoice_by_number(self, invoice_number: str) -> schemas.Invoice | None:
        """(جديدة) جلب فاتورة واحدة برقمها"""
        try:
            self.sqlite_cursor.execute(
                f"SELECT * {self._is_active_filter_sql('invoices')} AND invoice_number = ?",
                (invoice_number,),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                row_dict = dict(row)
                row_dict["items"] = json.loads(row_dict["items"])
                return schemas.Invoice(**row_dict)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الفاتورة {invoice_number} (SQLite): {e}")

        if self.online:
            try:
                data = self.mongo_db.invoices.find_one(
                    self._merge_active_filter_mongo({"invoice_number": invoice_number})
                )
                if data:
                    mongo_id = str(data.pop("_id"))
                    data.pop("_mongo_id", None)
                    data.pop("mongo_id", None)
                    return schemas.Invoice(**data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب الفاتورة {invoice_number} (Mongo): {e}")

        return None

    def get_invoice_by_id(self, invoice_id: str) -> schemas.Invoice | None:
        """جلب فاتورة بالمعرف (ID أو _mongo_id أو invoice_number)"""
        # محاولة البحث بـ _mongo_id أولاً
        if self.online:
            try:
                data = self.mongo_db.invoices.find_one(
                    self._merge_active_filter_mongo({"_id": self._to_objectid(invoice_id)})
                )
                if data:
                    mongo_id = str(data.pop("_id"))
                    data.pop("_mongo_id", None)
                    return schemas.Invoice(**data, _mongo_id=mongo_id)
            except Exception:
                pass

        # محاولة البحث بـ id في SQLite
        try:
            self.sqlite_cursor.execute(
                f"SELECT * {self._is_active_filter_sql('invoices')} AND id = ?",
                (invoice_id,),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                row_dict = dict(row)
                row_dict["items"] = json.loads(row_dict["items"])
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
                (new_status.value, now_iso, invoice_number),
            )
            self.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل إلغاء الفاتورة (SQLite): {e}")

        if self.online:
            try:
                self.mongo_db.invoices.update_one(
                    {"invoice_number": invoice_number},
                    {"$set": {"status": new_status.value, "last_modified": now_dt}},
                )
                self.sqlite_cursor.execute(
                    "UPDATE invoices SET sync_status = 'synced', dirty_flag = 0 WHERE invoice_number = ?",
                    (invoice_number,),
                )
                self.sqlite_conn.commit()
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل إلغاء الفاتورة (Mongo): {e}")

        invoice.status = new_status
        invoice.last_modified = now_dt
        invoice.sync_status = "synced" if self.online else "modified_offline"
        return invoice

    # --- دوال التعامل مع الخدمات ---

    def create_service(self, service_data: schemas.Service) -> schemas.Service:
        """(معدلة) إنشاء خدمة جديدة (بإصلاح حفظ الحالة في مونجو)"""
        existing = self._find_active_service_by_name(service_data.name)
        if existing is not None:
            safe_print(f"WARNING: الخدمة '{service_data.name}' موجودة بالفعل!")
            raise ValueError(f"الخدمة '{service_data.name}' موجودة بالفعل في النظام")

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
            service_data.sync_status,
            now_iso,
            now_iso,
            service_data.name,
            service_data.description,
            service_data.default_price,
            service_data.category,
            service_data.status.value,
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        service_data.id = local_id
        safe_print(f"INFO: تم حفظ الخدمة '{service_data.name}' محلياً (ID: {local_id}).")

        if self.online:
            try:
                service_dict = service_data.model_dump(exclude={"_mongo_id", "id"})
                service_dict["status"] = service_data.status.value
                service_dict["sync_status"] = "synced"
                service_dict["is_deleted"] = False

                result = self.mongo_db.services.insert_one(service_dict)
                mongo_id = str(result.inserted_id)

                service_data._mongo_id = mongo_id
                service_data.sync_status = "synced"

                self.sqlite_cursor.execute(
                    "UPDATE services SET _mongo_id = ?, sync_status = ?, dirty_flag = 0 WHERE id = ?",
                    (mongo_id, "synced", local_id),
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة الخدمة '{service_data.name}' أونلاين.")

            except Exception as e:
                if "E11000 duplicate key" in str(e):
                    safe_print(f"WARNING: الخدمة '{service_data.name}' موجودة بالفعل أونلاين.")
                    try:
                        existing = self.mongo_db.services.find_one({"name": service_data.name})
                        if existing:
                            existing_sync_status = str(existing.get("sync_status") or "").lower()
                            existing_is_deleted = bool(existing.get("is_deleted", False)) or (
                                existing_sync_status == "deleted"
                            )
                            if existing_is_deleted:
                                mongo_id = str(existing["_id"])
                                revived_service = service_dict.copy()
                                revived_service["last_modified"] = now_dt
                                revived_service["sync_status"] = "synced"
                                revived_service["is_deleted"] = False
                                self.mongo_db.services.update_one(
                                    {"_id": existing["_id"]},
                                    {"$set": revived_service},
                                )

                                service_data._mongo_id = mongo_id
                                service_data.sync_status = "synced"
                                self.sqlite_cursor.execute(
                                    """
                                    UPDATE services
                                    SET _mongo_id = ?, sync_status = ?, dirty_flag = 0, is_deleted = 0
                                    WHERE id = ?
                                    """,
                                    (mongo_id, "synced", local_id),
                                )
                                self.sqlite_conn.commit()
                            else:
                                mongo_id = str(existing["_id"])
                                self.sqlite_cursor.execute(
                                    f"SELECT * {self._is_active_filter_sql('services')} AND _mongo_id = ?",
                                    (mongo_id,),
                                )
                                local_shadow = self.sqlite_cursor.fetchone()
                                if local_shadow:
                                    local_shadow_dict = dict(local_shadow)
                                    local_shadow_name_key = self._normalized_key(
                                        local_shadow_dict.get("name")
                                    )
                                    requested_name_key = self._normalized_key(service_data.name)
                                    if (
                                        local_shadow_name_key
                                        and local_shadow_name_key != requested_name_key
                                    ):
                                        shadow_update = {
                                            "name": local_shadow_dict.get("name"),
                                            "description": local_shadow_dict.get("description"),
                                            "default_price": local_shadow_dict.get("default_price"),
                                            "category": local_shadow_dict.get("category"),
                                            "status": local_shadow_dict.get("status")
                                            or schemas.ServiceStatus.ACTIVE.value,
                                            "last_modified": now_dt,
                                            "sync_status": "synced",
                                            "is_deleted": False,
                                        }
                                        self.mongo_db.services.update_one(
                                            {"_id": existing["_id"]},
                                            {"$set": shadow_update},
                                        )
                                        self.sqlite_cursor.execute(
                                            """
                                            UPDATE services
                                            SET sync_status = ?, dirty_flag = 0, is_deleted = 0
                                            WHERE id = ?
                                            """,
                                            ("synced", local_shadow_dict["id"]),
                                        )

                                        retry_result = self.mongo_db.services.insert_one(
                                            service_dict
                                        )
                                        retry_mongo_id = str(retry_result.inserted_id)
                                        service_data._mongo_id = retry_mongo_id
                                        service_data.sync_status = "synced"
                                        self.sqlite_cursor.execute(
                                            """
                                            UPDATE services
                                            SET _mongo_id = ?, sync_status = ?, dirty_flag = 0, is_deleted = 0
                                            WHERE id = ?
                                            """,
                                            (retry_mongo_id, "synced", local_id),
                                        )
                                        self.sqlite_conn.commit()
                    except Exception:
                        pass
                else:
                    safe_print(f"ERROR: فشل مزامنة الخدمة الجديدة '{service_data.name}': {e}")

        return service_data

    def get_all_services(self) -> list[schemas.Service]:
        """⚡ جلب كل الخدمات "النشطة" فقط مع دمج المحلي والسحابي"""
        active_status = schemas.ServiceStatus.ACTIVE.value
        services_by_key: dict[str, schemas.Service] = {}

        if self.online:
            try:
                services_data = list(
                    self.mongo_db.services.find(
                        self._merge_active_filter_mongo({"status": active_status})
                    )
                )
                for service_data in services_data:
                    mongo_id = str(service_data.pop("_id"))
                    service_data.pop("_mongo_id", None)
                    service_data.pop("mongo_id", None)
                    service = schemas.Service(**service_data, _mongo_id=mongo_id)
                    service_key = str(mongo_id or "").strip() or self._normalized_key(
                        service_data.get("name")
                    )
                    if service_key:
                        services_by_key[service_key] = service
                if services_by_key:
                    safe_print(
                        f"INFO: تم جلب {len(services_by_key)} خدمة 'نشطة' من الأونلاين (MongoDB)."
                    )
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الخدمات من Mongo: {e}")

        try:
            self.sqlite_cursor.execute(
                """
                SELECT * FROM services
                WHERE status = ?
                AND (sync_status != 'deleted' OR sync_status IS NULL)
                AND (is_deleted = 0 OR is_deleted IS NULL)
                """,
                (active_status,),
            )
            rows = self.sqlite_cursor.fetchall()
            for row in rows:
                row_dict = dict(row)
                service = schemas.Service(**row_dict)
                service_key = str(row_dict.get("_mongo_id") or "").strip() or self._normalized_key(
                    row_dict.get("name")
                )
                if not service_key:
                    service_key = str(row_dict.get("id") or "").strip()
                if service_key:
                    services_by_key[service_key] = service
            services_list = list(services_by_key.values())
            safe_print(f"INFO: تم جلب {len(services_list)} خدمة 'نشطة' من المحلي.")
            return services_list
        except Exception as e:
            safe_print(f"ERROR: فشل جلب الخدمات من SQLite: {e}")
        return list(services_by_key.values())

    def get_service_by_id(self, service_id: str) -> schemas.Service | None:
        """(جديدة) جلب خدمة واحدة بالـ ID"""
        try:
            service_id_num = int(service_id)
        except ValueError:
            service_id_num = 0

        try:
            self.sqlite_cursor.execute(
                f"SELECT * {self._is_active_filter_sql('services')} AND (id = ? OR _mongo_id = ?)",
                (service_id_num, service_id),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                return schemas.Service(**dict(row))
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الخدمة {service_id} (SQLite): {e}")

        if self.online:
            try:
                data = self.mongo_db.services.find_one(
                    self._merge_active_filter_mongo(
                        {"$or": [{"_id": self._to_objectid(service_id)}, {"_mongo_id": service_id}]}
                    )
                )
                if data:
                    mongo_id = str(data.pop("_id"))
                    data.pop("_mongo_id", None)
                    data.pop("mongo_id", None)
                    return schemas.Service(**data, _mongo_id=mongo_id)
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب الخدمة {service_id} (Mongo): {e}")

        return None

    def update_service(
        self, service_id: str, service_data: schemas.Service
    ) -> schemas.Service | None:
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

        duplicate_service = self._find_active_service_by_name(
            service_data.name, exclude_id=service_id
        )
        if duplicate_service is not None:
            raise ValueError(f"الخدمة '{service_data.name}' موجودة بالفعل في النظام")

        sql = """
            UPDATE services SET
                name = ?, description = ?, default_price = ?, category = ?, status = ?,
                last_modified = ?, sync_status = 'modified_offline'
            WHERE id = ? OR _mongo_id = ?
        """
        params = (
            service_data.name,
            service_data.description,
            service_data.default_price,
            service_data.category,
            service_data.status.value,
            now_iso,
            service_id_num,
            service_id,
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
                update_dict["status"] = service_data.status.value
                update_dict["last_modified"] = now_dt
                update_dict["sync_status"] = "synced"
                update_dict["is_deleted"] = False
                self.sqlite_cursor.execute(
                    "SELECT id, _mongo_id FROM services WHERE id = ? OR _mongo_id = ?",
                    (service_id_num, service_id),
                )
                row = self.sqlite_cursor.fetchone()
                local_service_id = row["id"] if row else service_id_num
                mongo_service_id = str(
                    (
                        row["_mongo_id"]
                        if row and row["_mongo_id"]
                        else getattr(service_data, "_mongo_id", None) or service_id
                    )
                    or ""
                ).strip()

                result = self.mongo_db.services.update_one(
                    {
                        "$or": [
                            {"_id": self._to_objectid(mongo_service_id)},
                            {"_id": self._to_objectid(service_id)},
                            {"_mongo_id": mongo_service_id},
                            {"_mongo_id": service_id},
                            {"id": local_service_id},
                        ]
                    },
                    {"$set": update_dict},
                )
                if result and (
                    getattr(result, "matched_count", 0) > 0
                    or getattr(result, "modified_count", 0) > 0
                ):
                    self.sqlite_cursor.execute(
                        """
                        UPDATE services
                        SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
                        WHERE id = ? OR _mongo_id = ?
                        """,
                        (local_service_id, mongo_service_id),
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
            (service_id_num, service_id),
        )
        row = self.sqlite_cursor.fetchone()
        mongo_id = row[0] if row else service_id

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        if self.online:
            try:
                result = self.mongo_db.services.update_one(
                    {
                        "$or": [
                            {"_id": self._to_objectid(mongo_id)},
                            {"_id": self._to_objectid(service_id)},
                            {"_mongo_id": mongo_id},
                            {"_mongo_id": service_id},
                            {"id": service_id_num},
                        ]
                    },
                    {
                        "$set": {
                            "is_deleted": True,
                            "sync_status": "deleted",
                            "last_modified": now_dt,
                        }
                    },
                )
                if getattr(result, "matched_count", 0) > 0:
                    self.sqlite_cursor.execute(
                        "DELETE FROM services WHERE id = ? OR _mongo_id = ?",
                        (service_id_num, service_id),
                    )
                    self.sqlite_conn.commit()
                    safe_print("INFO: [Repo] ✅ تم تعليم حذف الخدمة ثم حذفها محلياً")
                    return True
                safe_print("WARNING: [Repo] الخدمة غير موجودة في MongoDB")
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل تعليم حذف الخدمة في MongoDB: {e}")

        self.sqlite_cursor.execute(
            """
            UPDATE services
            SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
            WHERE id = ? OR _mongo_id = ?
            """,
            (now_iso, service_id_num, service_id),
        )
        self.sqlite_conn.commit()
        return True

    def get_archived_services(self) -> list[schemas.Service]:
        """(جديدة) جلب كل الخدمات "المؤرشفة" فقط"""
        archived_status = schemas.ServiceStatus.ARCHIVED.value
        if self.online:
            try:
                services_data = list(
                    self.mongo_db.services.find(
                        self._merge_active_filter_mongo({"status": archived_status})
                    )
                )
                services_list = []
                for s in services_data:
                    mongo_id = str(s.pop("_id"))
                    s.pop("_mongo_id", None)
                    s.pop("mongo_id", None)
                    services_list.append(schemas.Service(**s, _mongo_id=mongo_id))
                return services_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الخدمات المؤرشفة (Mongo): {e}.")

        self.sqlite_cursor.execute(
            """
            SELECT * FROM services
            WHERE status = ?
            AND (sync_status != 'deleted' OR sync_status IS NULL)
            AND (is_deleted = 0 OR is_deleted IS NULL)
            """,
            (archived_status,),
        )
        rows = self.sqlite_cursor.fetchall()
        return [schemas.Service(**dict(row)) for row in rows]

    # --- دوال التعامل مع المصروفات ---

    def create_expense(self, expense_data: schemas.Expense) -> schemas.Expense:
        """إنشاء مصروف جديد مع توحيد مرجع المشروع ومنع التكرار."""
        with self._lock:
            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            self._normalize_expense_write_fields(expense_data)
            if self._find_duplicate_expense(expense_data) is not None:
                raise ValueError("يوجد مصروف بنفس البيانات لهذا المشروع")

            expense_data.created_at = now_dt
            expense_data.last_modified = now_dt
            expense_data.sync_status = "new_offline"

            sql = """
                INSERT INTO expenses (
                    sync_status, created_at, last_modified, date, category, amount,
                    description, account_id, payment_account_id, project_id, dirty_flag, is_deleted
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
            """
            params = (
                expense_data.sync_status,
                now_iso,
                now_iso,
                expense_data.date.isoformat(),
                expense_data.category,
                expense_data.amount,
                expense_data.description,
                expense_data.account_id,
                expense_data.payment_account_id,
                expense_data.project_id,
            )

            self.sqlite_cursor.execute(sql, params)
            self.sqlite_conn.commit()
            local_id = self.sqlite_cursor.lastrowid
            expense_data.id = local_id
            safe_print(f"INFO: تم حفظ المصروف '{expense_data.category}' محلياً (ID: {local_id}).")

        if self.online:
            try:
                expense_dict = expense_data.model_dump(exclude={"_mongo_id", "id"})
                expense_dict["date"] = expense_data.date

                result = self.mongo_db.expenses.insert_one(expense_dict)
                mongo_id = str(result.inserted_id)

                expense_data._mongo_id = mongo_id
                expense_data.sync_status = "synced"

                self.sqlite_cursor.execute(
                    "UPDATE expenses SET _mongo_id = ?, sync_status = ?, dirty_flag = 0 WHERE id = ?",
                    (mongo_id, "synced", local_id),
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة المصروف '{expense_data.category}' أونلاين.")

            except Exception as e:
                safe_print(f"ERROR: فشل مزامنة المصروف الجديد '{expense_data.category}': {e}")

        self.invalidate_table_cache("expenses")

        return expense_data

    def _normalize_expense_write_fields(self, expense_data: schemas.Expense) -> None:
        requested_project_ref = str(getattr(expense_data, "project_id", "") or "")
        resolved_project = self._resolve_project_row(requested_project_ref)
        if resolved_project:
            expense_data.project_id = self._stable_project_reference(
                resolved_project,
                requested_project_ref,
            )
        elif self._has_ambiguous_project_name_reference(requested_project_ref):
            raise ValueError("اسم المشروع غير فريد؛ استخدم معرف المشروع بدلاً من الاسم")
        else:
            normalized_project = normalize_user_text(requested_project_ref)
            expense_data.project_id = normalized_project if normalized_project else None

        normalized_payment_account = normalize_user_text(
            str(getattr(expense_data, "payment_account_id", "") or "")
        )
        if not normalized_payment_account:
            normalized_payment_account = normalize_user_text(
                str(getattr(expense_data, "account_id", "") or "")
            )
        expense_data.payment_account_id = normalized_payment_account or None

    def _normalize_invoice_write_fields(self, invoice_data: schemas.Invoice) -> None:
        requested_project_ref = str(getattr(invoice_data, "project_id", "") or "")
        normalized_project_ref = normalize_user_text(requested_project_ref)
        if not normalized_project_ref:
            invoice_data.project_id = None
            return

        client_id = str(getattr(invoice_data, "client_id", "") or "")
        resolved_project = self._resolve_project_row(normalized_project_ref, client_id)
        if resolved_project:
            invoice_data.project_id = self._stable_project_reference(
                resolved_project,
                normalized_project_ref,
            )
            return

        if self._has_ambiguous_project_name_reference(normalized_project_ref):
            raise ValueError("اسم المشروع غير فريد؛ استخدم معرف المشروع أو client_id الصحيح")

        invoice_data.project_id = normalized_project_ref

    def _find_duplicate_expense(
        self, expense_data: schemas.Expense, exclude_id: int | None = None
    ) -> schemas.Expense | None:
        project_ref = str(getattr(expense_data, "project_id", "") or "")
        if not project_ref:
            return None

        new_signature = self._expense_signature(
            {
                "project_id": getattr(expense_data, "project_id", ""),
                "date": (
                    expense_data.date.isoformat() if getattr(expense_data, "date", None) else ""
                ),
                "amount": getattr(expense_data, "amount", 0.0),
                "category": getattr(expense_data, "category", ""),
                "description": getattr(expense_data, "description", ""),
                "account_id": getattr(expense_data, "account_id", ""),
                "payment_account_id": getattr(expense_data, "payment_account_id", ""),
            }
        )

        for existing in self.get_expenses_for_project(project_ref):
            existing_id = getattr(existing, "id", None)
            if exclude_id and existing_id and int(existing_id) == int(exclude_id):
                continue

            existing_signature = self._expense_signature(
                {
                    "project_id": getattr(existing, "project_id", ""),
                    "date": getattr(existing, "date", ""),
                    "amount": getattr(existing, "amount", 0.0),
                    "category": getattr(existing, "category", ""),
                    "description": getattr(existing, "description", ""),
                    "account_id": getattr(existing, "account_id", ""),
                    "payment_account_id": getattr(existing, "payment_account_id", ""),
                }
            )
            if existing_signature == new_signature:
                return existing

        return None

    def get_all_expenses(self) -> list[schemas.Expense]:
        """⚡ جلب كل المصروفات (SQLite أولاً للسرعة) - مع cache ذكي"""
        if CACHE_ENABLED and hasattr(self, "_expenses_cache"):
            cached_result = self._expenses_cache.get("all_expenses")
            if cached_result is not None:
                safe_print(f"INFO: ⚡ تم جلب {len(cached_result)} مصروف من الـ Cache")
                return cached_result

        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    ORDER BY date DESC
                    """
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
            deduped_rows = self._dedupe_rows_by_signature(
                [dict(row) for row in rows],
                self._expense_signature,
            )
            deduped_rows.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
            expenses_list = [schemas.Expense(**row) for row in deduped_rows]
            if CACHE_ENABLED and hasattr(self, "_expenses_cache"):
                self._expenses_cache.set("all_expenses", expenses_list)
            safe_print(f"INFO: تم جلب {len(expenses_list)} مصروف من المحلي (SQLite).")
            return expenses_list
        except Exception as e:
            safe_print(f"ERROR: فشل جلب المصروفات من SQLite: {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                expenses_data = list(self.mongo_db.expenses.find(self._merge_active_filter_mongo()))
                rows = []
                for exp in expenses_data:
                    mongo_id = str(exp.pop("_id"))
                    exp.pop("_mongo_id", None)
                    exp.pop("mongo_id", None)
                    exp["_mongo_id"] = mongo_id
                    rows.append(exp)
                deduped_rows = self._dedupe_rows_by_signature(rows, self._expense_signature)
                deduped_rows.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
                expenses_list = [schemas.Expense(**row) for row in deduped_rows]
                if CACHE_ENABLED and hasattr(self, "_expenses_cache"):
                    self._expenses_cache.set("all_expenses", expenses_list)
                safe_print("INFO: تم جلب المصروفات من الأونلاين (MongoDB).")
                return expenses_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب المصروفات من Mongo: {e}")

        return []

    def get_expenses_paid_from_account(
        self, account_code: str, start_iso: str, end_iso: str
    ) -> list[schemas.Expense]:
        """⚡ جلب المصروفات المدفوعة من حساب نقدي (يدعم البيانات القديمة)"""
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    AND date >= ? AND date <= ?
                    AND (
                        payment_account_id = ?
                        OR (payment_account_id IS NULL AND account_id = ?)
                    )
                    ORDER BY date ASC
                """,
                    (start_iso, end_iso, account_code, account_code),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
            return [schemas.Expense(**dict(row)) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب مصروفات حساب الدفع (SQLite): {e}")
            return []

    def sum_expenses_paid_before(self, account_code: str, before_iso: str) -> float:
        """⚡ إجمالي المصروفات المدفوعة من حساب نقدي قبل تاريخ محدد"""
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0) FROM expenses
                    WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    AND date < ?
                    AND (
                        payment_account_id = ?
                        OR (payment_account_id IS NULL AND account_id = ?)
                    )
                """,
                    (before_iso, account_code, account_code),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
            return float(row[0] if row else 0.0)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب إجمالي مصروفات الدفع: {e}")
            return 0.0

    def get_expenses_charged_to_account(
        self, account_code: str, start_iso: str, end_iso: str
    ) -> list[schemas.Expense]:
        """⚡ جلب المصروفات المحمّلة على حساب مصروفات (عند وجود حساب دفع منفصل)"""
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    AND date >= ? AND date <= ?
                    AND account_id = ?
                    AND payment_account_id IS NOT NULL
                    AND payment_account_id != ?
                    ORDER BY date ASC
                """,
                    (start_iso, end_iso, account_code, account_code),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
            return [schemas.Expense(**dict(row)) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب مصروفات حساب المصروف (SQLite): {e}")
            return []

    def sum_expenses_charged_before(self, account_code: str, before_iso: str) -> float:
        """⚡ إجمالي المصروفات المحمّلة على حساب قبل تاريخ محدد"""
        try:
            cursor = self.get_cursor()
            try:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0) FROM expenses
                    WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                    AND (is_deleted = 0 OR is_deleted IS NULL)
                    AND date < ?
                    AND account_id = ?
                    AND payment_account_id IS NOT NULL
                    AND payment_account_id != ?
                """,
                    (before_iso, account_code, account_code),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
            return float(row[0] if row else 0.0)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب إجمالي مصروفات الحساب: {e}")
            return 0.0

    def get_expense_by_id(self, expense_id) -> schemas.Expense | None:
        """⚡ جلب مصروف واحد بالـ ID"""
        try:
            # ⚡ تحديد نوع الـ ID والبحث المناسب
            if isinstance(expense_id, int) or (
                isinstance(expense_id, str) and expense_id.isdigit()
            ):
                where_clause = "WHERE id = ?"
                where_params = (int(expense_id),)
            else:
                where_clause = "WHERE _mongo_id = ?"
                where_params = (str(expense_id),)

            cursor = self.get_cursor()
            try:
                cursor.execute(
                    f"SELECT * {self._is_active_filter_sql('expenses')} AND {where_clause[6:]}",
                    where_params,
                )
                row = cursor.fetchone()
                if row:
                    return schemas.Expense(**dict(row))
            finally:
                cursor.close()
        except Exception as e:
            safe_print(f"ERROR: فشل جلب المصروف (ID: {expense_id}): {e}")
        return None

    def update_expense(self, expense_id, expense_data: schemas.Expense) -> bool:
        """تعديل مصروف موجود"""
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        try:
            # ⚡ تحديد نوع الـ ID والبحث المناسب
            if isinstance(expense_id, int) or (
                isinstance(expense_id, str) and expense_id.isdigit()
            ):
                where_clause = "WHERE id = ?"
                where_params = (int(expense_id),)
            else:
                where_clause = "WHERE _mongo_id = ?"
                where_params = (str(expense_id),)

            existing_expense = self.get_expense_by_id(expense_id)

            # ⚡ جلب الحقول بأمان
            category = getattr(expense_data, "category", "") or ""
            description = getattr(expense_data, "description", "") or ""
            self._normalize_expense_write_fields(expense_data)
            project_id = getattr(expense_data, "project_id", "") or ""
            payment_account_id = getattr(expense_data, "payment_account_id", None)

            existing_local_id = None
            if existing_expense is not None:
                try:
                    existing_local_id = int(getattr(existing_expense, "id", 0) or 0) or None
                except (TypeError, ValueError):
                    existing_local_id = None

            if self._find_duplicate_expense(expense_data, exclude_id=existing_local_id) is not None:
                raise ValueError("يوجد مصروف بنفس البيانات لهذا المشروع")

            sql = f"""
                UPDATE expenses SET
                    last_modified = ?, date = ?, category = ?, amount = ?,
                    description = ?, account_id = ?, payment_account_id = ?, project_id = ?, sync_status = ?
                {where_clause}
            """
            params = (
                now_iso,
                expense_data.date.isoformat(),
                category,
                expense_data.amount,
                description,
                expense_data.account_id,
                payment_account_id,
                project_id,
                "modified_offline",
            ) + where_params

            self.sqlite_cursor.execute(sql, params)
            rows_affected = self.sqlite_cursor.rowcount
            self.sqlite_conn.commit()

            if rows_affected == 0:
                return False

            # تحديث في MongoDB
            if self.online:
                try:
                    expense_dict = {
                        "last_modified": now_dt,
                        "date": expense_data.date,
                        "category": category,
                        "amount": expense_data.amount,
                        "description": description,
                        "account_id": expense_data.account_id,
                        "payment_account_id": payment_account_id,
                        "project_id": project_id,
                        "sync_status": "synced",
                        "is_deleted": False,
                    }

                    result = None
                    mongo_id = getattr(expense_data, "_mongo_id", None) or getattr(
                        existing_expense, "_mongo_id", None
                    )
                    if mongo_id:
                        result = self.mongo_db.expenses.update_one(
                            {
                                "$or": [
                                    {"_id": self._to_objectid(str(mongo_id))},
                                    {"_mongo_id": str(mongo_id)},
                                ]
                            },
                            {"$set": expense_dict},
                        )

                    if result and (
                        getattr(result, "matched_count", 0) > 0
                        or getattr(result, "modified_count", 0) > 0
                    ):
                        sync_update_sql = f"UPDATE expenses SET sync_status = ?, dirty_flag = 0, is_deleted = 0 {where_clause}"  # nosec B608
                        self.sqlite_cursor.execute(sync_update_sql, ("synced",) + where_params)
                        self.sqlite_conn.commit()
                except Exception:
                    pass  # Ignore sync errors

            self.invalidate_table_cache("expenses")

            return True
        except ValueError:
            raise
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تعديل المصروف: {e}")
            return False

    def delete_expense(self, expense_id) -> bool:
        """حذف مصروف"""
        try:
            # جلب بيانات المصروف أولاً للحصول على _mongo_id
            self.sqlite_cursor.execute(
                "SELECT _mongo_id FROM expenses WHERE id = ? OR _mongo_id = ?",
                (expense_id, str(expense_id)),
            )
            row = self.sqlite_cursor.fetchone()
            mongo_id = row["_mongo_id"] if row else None

            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            if self.online and mongo_id:
                try:
                    result = self.mongo_db.expenses.update_one(
                        {"_id": self._to_objectid(mongo_id)},
                        {
                            "$set": {
                                "is_deleted": True,
                                "sync_status": "deleted",
                                "last_modified": now_dt,
                            }
                        },
                    )
                    if getattr(result, "matched_count", 0) > 0:
                        self.sqlite_cursor.execute(
                            "DELETE FROM expenses WHERE id = ? OR _mongo_id = ?",
                            (expense_id, str(expense_id)),
                        )
                        self.sqlite_conn.commit()
                        safe_print("INFO: تم تعليم حذف المصروف ثم حذفه محلياً.")
                    else:
                        self.sqlite_cursor.execute(
                            """
                            UPDATE expenses
                            SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                            WHERE id = ? OR _mongo_id = ?
                            """,
                            (now_iso, expense_id, str(expense_id)),
                        )
                        self.sqlite_conn.commit()
                except Exception as e:
                    safe_print(f"ERROR: فشل تعليم حذف المصروف في Mongo: {e}")
                    self.sqlite_cursor.execute(
                        """
                        UPDATE expenses
                        SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                        WHERE id = ? OR _mongo_id = ?
                        """,
                        (now_iso, expense_id, str(expense_id)),
                    )
                    self.sqlite_conn.commit()
            else:
                self.sqlite_cursor.execute(
                    """
                    UPDATE expenses
                    SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                    WHERE id = ? OR _mongo_id = ?
                    """,
                    (now_iso, expense_id, str(expense_id)),
                )
                self.sqlite_conn.commit()

            self.invalidate_table_cache("expenses")

            return True
        except Exception as e:
            safe_print(f"ERROR: فشل حذف المصروف: {e}")
            return False

    # --- دوال التعامل مع المشاريع ---

    def _generate_unique_project_invoice_number(self) -> str:
        max_num = 97161

        self.sqlite_cursor.execute(
            "SELECT invoice_number FROM invoice_numbers WHERE invoice_number LIKE 'SW-%' ORDER BY invoice_number DESC LIMIT 1"
        )
        result1 = self.sqlite_cursor.fetchone()
        if result1 and result1[0]:
            try:
                max_num = max(max_num, int(str(result1[0]).replace("SW-", "")))
            except ValueError:
                pass

        self.sqlite_cursor.execute(
            "SELECT invoice_number FROM projects WHERE invoice_number LIKE 'SW-%' ORDER BY invoice_number DESC LIMIT 1"
        )
        result2 = self.sqlite_cursor.fetchone()
        if result2 and result2[0]:
            try:
                max_num = max(max_num, int(str(result2[0]).replace("SW-", "")))
            except ValueError:
                pass

        invoice_number = f"SW-{max_num + 1}"
        for _ in range(100):
            self.sqlite_cursor.execute(
                "SELECT COUNT(*) FROM invoice_numbers WHERE invoice_number = ?",
                (invoice_number,),
            )
            used_in_table = self.sqlite_cursor.fetchone()[0] or 0
            self.sqlite_cursor.execute(
                "SELECT COUNT(*) FROM projects WHERE invoice_number = ?",
                (invoice_number,),
            )
            used_in_projects = self.sqlite_cursor.fetchone()[0] or 0
            if used_in_table == 0 and used_in_projects == 0:
                return invoice_number
            max_num += 1
            invoice_number = f"SW-{max_num + 1}"

        raise RuntimeError("invoice_number_generation_exhausted")

    def create_project(self, project_data: schemas.Project) -> schemas.Project:
        """(معدلة) إنشاء مشروع جديد (بالحقول المالية) مع فحص التكرار"""
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        normalized_client_id = self._normalize_client_reference(
            getattr(project_data, "client_id", "")
        )
        if normalized_client_id:
            project_data.client_id = normalized_client_id

        # ✅ فحص التكرار بنفس العميل ونفس الاسم (case insensitive)
        similar_project = self._get_similar_project(project_data.name, project_data.client_id)
        if similar_project:
            safe_print(f"WARNING: يوجد مشروع مشابه '{similar_project.name}' لنفس العميل!")
            raise ValueError(f"يوجد مشروع مشابه '{similar_project.name}' لنفس العميل")

        project_data.created_at = now_dt
        project_data.last_modified = now_dt
        project_data.sync_status = "new_offline"

        items_json = json.dumps([item.model_dump() for item in project_data.items])
        milestones_json = json.dumps(
            [milestone.model_dump(mode="json") for milestone in project_data.milestones],
            ensure_ascii=False,
        )

        # ⚡ جلب قيمة status_manually_set
        status_manually_set = 1 if getattr(project_data, "status_manually_set", False) else 0
        currency_code = normalize_currency_code(getattr(project_data, "currency", None))
        exchange_rate_snapshot = normalize_exchange_rate(
            getattr(project_data, "exchange_rate_snapshot", 1.0),
            currency_code,
        )
        project_data.currency = currency_code
        project_data.exchange_rate_snapshot = exchange_rate_snapshot

        sql = """
            INSERT INTO projects (
                sync_status, created_at, last_modified, name, client_id,
                status, status_manually_set, description, start_date, end_date,
                items, milestones, subtotal, discount_rate, discount_amount, tax_rate,
                tax_amount, total_amount, currency, exchange_rate_snapshot, project_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            project_data.sync_status,
            now_iso,
            now_iso,
            project_data.name,
            project_data.client_id,
            project_data.status.value,
            status_manually_set,
            project_data.description,
            project_data.start_date.isoformat() if project_data.start_date else None,
            project_data.end_date.isoformat() if project_data.end_date else None,
            items_json,
            milestones_json,
            project_data.subtotal,
            project_data.discount_rate,
            project_data.discount_amount,
            project_data.tax_rate,
            project_data.tax_amount,
            project_data.total_amount,
            currency_code,
            exchange_rate_snapshot,
            project_data.project_notes,
        )

        self.sqlite_cursor.execute(sql, params)
        self.sqlite_conn.commit()
        local_id = self.sqlite_cursor.lastrowid
        project_data.id = local_id

        # ⚡ توليد وحفظ رقم الفاتورة الثابت فوراً وربطه بهوية المشروع
        try:
            invoice_number = self._generate_unique_project_invoice_number()
            self.sqlite_cursor.execute(
                """
                INSERT INTO invoice_numbers (project_id, project_name, invoice_number, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(local_id), project_data.name, invoice_number, datetime.now().isoformat()),
            )
            self.sqlite_cursor.execute(
                "UPDATE projects SET invoice_number = ? WHERE id = ?",
                (invoice_number, local_id),
            )
            self.sqlite_conn.commit()
            project_data.invoice_number = invoice_number
        except Exception as e:
            safe_print(f"WARNING: خطأ في توليد رقم الفاتورة: {e}")
            invoice_number = f"SW-{97161 + int(local_id)}"
            self.sqlite_cursor.execute(
                "UPDATE projects SET invoice_number = ? WHERE id = ?",
                (invoice_number, local_id),
            )
            self.sqlite_cursor.execute(
                """
                INSERT OR IGNORE INTO invoice_numbers (project_id, project_name, invoice_number, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(local_id), project_data.name, invoice_number, datetime.now().isoformat()),
            )
            self.sqlite_conn.commit()
            project_data.invoice_number = invoice_number

        safe_print(
            f"INFO: تم حفظ المشروع '{project_data.name}' محلياً (ID: {local_id}, Invoice: {invoice_number})."
        )

        if self.online:
            try:
                project_dict = project_data.model_dump(exclude={"_mongo_id", "id"})
                project_dict["status"] = project_data.status.value
                project_dict["status_manually_set"] = getattr(
                    project_data, "status_manually_set", False
                )
                project_dict["start_date"] = project_data.start_date
                project_dict["end_date"] = project_data.end_date
                project_dict["currency"] = currency_code
                project_dict["exchange_rate_snapshot"] = exchange_rate_snapshot
                # ✅ تأكد من حفظ رقم الفاتورة
                project_dict["invoice_number"] = invoice_number

                result = self.mongo_db.projects.insert_one(project_dict)
                mongo_id = str(result.inserted_id)

                project_data._mongo_id = mongo_id
                project_data.sync_status = "synced"

                self.sqlite_cursor.execute(
                    "UPDATE projects SET _mongo_id = ?, sync_status = ?, dirty_flag = 0 WHERE id = ?",
                    (mongo_id, "synced", local_id),
                )
                self.sqlite_conn.commit()
                safe_print(f"INFO: تم مزامنة المشروع '{project_data.name}' أونلاين.")

            except Exception as e:
                if "E11000 duplicate key" in str(e):
                    safe_print(f"WARNING: المشروع باسم '{project_data.name}' موجود بالفعل أونلاين.")
                else:
                    safe_print(f"ERROR: فشل مزامنة المشروع الجديد: {e}")

        # ⚡ إبطال الـ cache بعد إضافة مشروع جديد
        if CACHE_ENABLED and hasattr(self, "_projects_cache"):
            self._projects_cache.invalidate()
            safe_print("INFO: ⚡ تم إبطال cache المشاريع بعد الإضافة")

        # ⚡ إبطال cache الداشبورد لأن الأرقام تغيرت
        Repository._dashboard_cache = None
        Repository._dashboard_cache_time = 0

        return project_data

    def get_all_projects(
        self,
        status: schemas.ProjectStatus | None = None,
        exclude_status: schemas.ProjectStatus | None = None,
    ) -> list[schemas.Project]:
        """
        ⚡ جلب كل المشاريع (SQLite أولاً للسرعة) - مع Cache ذكي
        """
        # ⚡ استخدام الـ cache إذا كان متاحاً
        if CACHE_ENABLED and hasattr(self, "_projects_cache"):
            cache_key = f"all_projects_{status}_{exclude_status}"
            cached_result = self._projects_cache.get(cache_key)
            if cached_result is not None:
                safe_print(f"INFO: ⚡ تم جلب {len(cached_result)} مشروع من الـ Cache")
                return cached_result

        allowed_statuses = {s.value for s in schemas.ProjectStatus}
        now_iso = datetime.now().isoformat()

        def _safe_float(value: Any, default: float = 0.0) -> float:
            if value is None or value == "":
                return float(default)
            try:
                return float(value)
            except (TypeError, ValueError):
                return float(default)

        def _safe_int(value: Any, default: int = 0) -> int:
            if value is None or value == "":
                return int(default)
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return int(default)

        def _safe_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, int | float):
                return int(value) != 0
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "yes", "on"}:
                    return True
                if normalized in {"0", "false", "no", "off", ""}:
                    return False
            return False

        def _normalize_project_payload(raw: dict[str, Any]) -> dict[str, Any] | None:
            payload = dict(raw)

            name = str(payload.get("name") or "").strip()
            client_id = str(payload.get("client_id") or "").strip()
            if not name or not client_id:
                return None
            payload["name"] = name
            payload["client_id"] = client_id

            status_value = str(payload.get("status") or schemas.ProjectStatus.ACTIVE.value)
            if status_value not in allowed_statuses:
                status_value = schemas.ProjectStatus.ACTIVE.value
            payload["status"] = status_value

            currency_value = normalize_currency_code(
                payload.get("currency"),
                schemas.CurrencyCode.EGP.value,
            )
            payload["currency"] = currency_value
            payload["exchange_rate_snapshot"] = normalize_exchange_rate(
                payload.get("exchange_rate_snapshot", 1.0),
                currency_value,
            )

            payload["created_at"] = str(payload.get("created_at") or now_iso)
            payload["last_modified"] = str(payload.get("last_modified") or now_iso)
            payload["status_manually_set"] = _safe_bool(payload.get("status_manually_set"))
            payload["is_retainer"] = _safe_bool(payload.get("is_retainer"))
            payload["sequence_number"] = _safe_int(payload.get("sequence_number"), 0)

            for numeric_field in [
                "subtotal",
                "discount_rate",
                "discount_amount",
                "tax_rate",
                "tax_amount",
                "total_amount",
                "total_estimated_cost",
                "estimated_profit",
                "profit_margin",
                "exchange_rate_snapshot",
            ]:
                payload[numeric_field] = _safe_float(payload.get(numeric_field), 0.0)

            for list_field in ["items", "milestones"]:
                value = payload.get(list_field)
                if isinstance(value, str):
                    try:
                        payload[list_field] = json.loads(value)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        payload[list_field] = []
                elif value is None:
                    payload[list_field] = []

            return payload

        sql_query = "SELECT * FROM projects WHERE (sync_status != 'deleted' OR sync_status IS NULL) AND (is_deleted = 0 OR is_deleted IS NULL)"
        sql_params: list[Any] = []

        if status:
            sql_query += " AND status = ?"
            sql_params.append(status.value)
        elif exclude_status:
            sql_query += " AND status != ?"
            sql_params.append(exclude_status.value)

        sql_query += " ORDER BY created_at DESC"

        # ⚡ جلب من SQLite أولاً (سريع جداً)
        try:
            with self._lock:
                cursor = self.get_cursor()
                try:
                    cursor.execute(sql_query, sql_params)
                    rows = cursor.fetchall()
                    data_list: list[schemas.Project] = []
                    for row in rows:
                        try:
                            row_dict = _normalize_project_payload(dict(row))
                            if not row_dict:
                                continue
                            data_list.append(schemas.Project(**row_dict))
                        except Exception:
                            continue

                    # ⚡ حفظ في الـ cache
                    if CACHE_ENABLED and hasattr(self, "_projects_cache"):
                        cache_key = f"all_projects_{status}_{exclude_status}"
                        self._projects_cache.set(cache_key, data_list)

                    safe_print(f"INFO: تم جلب {len(data_list)} مشروع من المحلي.")
                    return data_list
                finally:
                    cursor.close()
        except Exception as e:
            if self._is_sqlite_closed_error(e):
                return []
            safe_print(f"ERROR: فشل جلب المشاريع من SQLite: {e}")

        # Fallback إلى MongoDB
        if self.online:
            try:
                query_filter: dict[str, Any] = {}
                if status:
                    query_filter = {"status": status.value}
                elif exclude_status:
                    query_filter = {"status": {"$ne": exclude_status.value}}

                data = list(
                    self.mongo_db.projects.find(self._merge_active_filter_mongo(query_filter)).sort(
                        "created_at", -1
                    )
                )
                data_list = []
                for d in data:
                    try:
                        mongo_id = str(d.pop("_id"))
                        d.pop("_mongo_id", None)
                        d.pop("mongo_id", None)
                        normalized = _normalize_project_payload(d)
                        if not normalized:
                            continue
                        data_list.append(schemas.Project(**normalized, _mongo_id=mongo_id))
                    except Exception:
                        continue

                # ⚡ حفظ في الـ cache
                if CACHE_ENABLED and hasattr(self, "_projects_cache"):
                    cache_key = f"all_projects_{status}_{exclude_status}"
                    self._projects_cache.set(cache_key, data_list)

                safe_print(f"INFO: تم جلب {len(data_list)} مشروع من الأونلاين.")
                return data_list
            except Exception as e:
                safe_print(f"ERROR: فشل جلب المشاريع من Mongo: {e}")

        return []

    def get_project_by_number(
        self, project_name: str, client_id: str | None = None
    ) -> schemas.Project | None:
        """(جديدة) جلب مشروع واحد باسمه"""
        project_name = normalize_user_text(project_name)
        if not project_name:
            return None
        resolved = self._resolve_project_target_row(project_name, client_id or "")
        if not resolved:
            return None

        row_dict = dict(resolved)
        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"SELECT * {self._is_active_filter_sql('projects')} AND id = ?",
                        (row_dict["id"],),
                    )
                    row = cursor.fetchone()
                finally:
                    cursor.close()
            if not row:
                return None
            row_dict = dict(row)
            row_dict["currency"] = normalize_currency_code(row_dict.get("currency"))
            row_dict["exchange_rate_snapshot"] = normalize_exchange_rate(
                row_dict.get("exchange_rate_snapshot", 1.0),
                row_dict.get("currency"),
            )
            items_value = row_dict.get("items")
            if isinstance(items_value, str):
                try:
                    row_dict["items"] = json.loads(items_value)
                except json.JSONDecodeError:
                    row_dict["items"] = []
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

    def update_project(
        self, project_name: str, project_data: schemas.Project
    ) -> schemas.Project | None:
        """
        (جديدة) تحديث بيانات مشروع موجود بالكامل.
        """
        safe_print(f"INFO: [Repo] جاري تحديث المشروع {project_name} في قاعدة البيانات...")

        now_dt = datetime.now()
        now_iso = now_dt.isoformat()
        normalized_client_id = self._normalize_client_reference(
            getattr(project_data, "client_id", "")
        )
        if normalized_client_id:
            project_data.client_id = normalized_client_id
        currency_code = normalize_currency_code(getattr(project_data, "currency", None))
        exchange_rate_snapshot = normalize_exchange_rate(
            getattr(project_data, "exchange_rate_snapshot", 1.0),
            currency_code,
        )
        project_data.currency = currency_code
        project_data.exchange_rate_snapshot = exchange_rate_snapshot
        items_json = json.dumps([item.model_dump() for item in project_data.items])
        milestones_json = json.dumps(
            [milestone.model_dump(mode="json") for milestone in project_data.milestones],
            ensure_ascii=False,
        )
        target_row = self._resolve_project_target_row(
            project_name,
            getattr(project_data, "client_id", ""),
            local_id=getattr(project_data, "id", None),
            mongo_id=getattr(project_data, "_mongo_id", None),
        )
        if not target_row:
            return None

        target_local_id = int(target_row["id"])
        current_name = str(target_row.get("name") or project_name or "").strip()
        current_client_id = str(
            target_row.get("client_id") or getattr(project_data, "client_id", "") or ""
        ).strip()
        current_mongo_id = str(
            target_row.get("_mongo_id") or getattr(project_data, "_mongo_id", None) or ""
        ).strip()
        stable_project_ref = self._stable_project_reference(target_row, project_name)

        project_data.id = target_local_id
        if current_mongo_id:
            project_data._mongo_id = current_mongo_id
        if current_client_id and not getattr(project_data, "client_id", ""):
            project_data.client_id = current_client_id

        project_renamed = str(project_data.name or "").strip() != current_name
        rename_aliases = self._project_reference_values(target_row) if project_renamed else set()

        # --- 1. تحديث SQLite ---
        try:
            # ⚡ جلب قيمة status_manually_set
            status_manually_set = 1 if getattr(project_data, "status_manually_set", False) else 0

            sql = """
                UPDATE projects SET
                    name = ?, client_id = ?, status = ?, status_manually_set = ?, description = ?, start_date = ?, end_date = ?,
                    items = ?, milestones = ?, subtotal = ?, discount_rate = ?, discount_amount = ?, tax_rate = ?,
                    tax_amount = ?, total_amount = ?, currency = ?, exchange_rate_snapshot = ?, project_notes = ?,
                    last_modified = ?, sync_status = 'modified_offline'
                WHERE id = ?
            """
            params = (
                project_data.name,  # ✅ تحديث الاسم الجديد
                project_data.client_id,
                project_data.status.value,
                status_manually_set,
                project_data.description,
                project_data.start_date.isoformat() if project_data.start_date else None,
                project_data.end_date.isoformat() if project_data.end_date else None,
                items_json,
                milestones_json,
                project_data.subtotal,
                project_data.discount_rate,
                project_data.discount_amount,
                project_data.tax_rate,
                project_data.tax_amount,
                project_data.total_amount,
                currency_code,
                exchange_rate_snapshot,
                project_data.project_notes,
                now_iso,
                target_local_id,
            )
            with self._lock:
                local_cursor = self.sqlite_conn.cursor()
                had_outer_transaction = bool(self.sqlite_conn.in_transaction)
                savepoint_name = "sp_update_project_write"
                if had_outer_transaction:
                    local_cursor.execute(f"SAVEPOINT {savepoint_name}")
                else:
                    local_cursor.execute("BEGIN IMMEDIATE")
                try:
                    local_cursor.execute(sql, params)
                    if local_cursor.rowcount == 0:
                        if had_outer_transaction:
                            local_cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                            local_cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                        else:
                            self.sqlite_conn.rollback()
                        return None

                    if project_renamed:
                        self._cascade_project_rename_sqlite(
                            current_name,
                            project_data.name,
                            now_iso,
                            rename_aliases,
                            target_local_id,
                            stable_project_ref,
                            cursor=local_cursor,
                        )

                    if had_outer_transaction:
                        local_cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                    else:
                        self.sqlite_conn.commit()
                except Exception:
                    if had_outer_transaction:
                        local_cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                        local_cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                    else:
                        self.sqlite_conn.rollback()
                    raise
                finally:
                    local_cursor.close()
            safe_print("SUCCESS: [Repo] ✅ تم تحديث المشروع في SQLite")
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث المشروع (SQLite): {e}")

            traceback.print_exc()
            return None

        # --- 2. تحديث MongoDB (اختياري - لا يعطل البرنامج) ---
        if self.online and self.mongo_db is not None:
            try:
                update_dict = project_data.model_dump(exclude={"_mongo_id", "id", "created_at"})
                update_dict["status"] = project_data.status.value
                update_dict["start_date"] = project_data.start_date
                update_dict["end_date"] = project_data.end_date
                update_dict["currency"] = currency_code
                update_dict["exchange_rate_snapshot"] = exchange_rate_snapshot
                update_dict["last_modified"] = now_dt
                update_dict["sync_status"] = "synced"
                update_dict["is_deleted"] = False

                if current_mongo_id:
                    try:
                        project_filter: dict[str, Any] = {
                            "_id": self._to_objectid(current_mongo_id)
                        }
                    except Exception:
                        project_filter = {"_mongo_id": current_mongo_id}
                else:
                    project_filter = {"name": current_name, "client_id": current_client_id}

                result = self.mongo_db.projects.update_one(project_filter, {"$set": update_dict})
                if result and (
                    getattr(result, "matched_count", 0) > 0
                    or getattr(result, "modified_count", 0) > 0
                ):
                    if project_renamed:
                        self._cascade_project_rename_mongo(
                            current_name,
                            project_data.name,
                            now_dt,
                            rename_aliases,
                            stable_project_ref,
                        )
                    with self._lock:
                        sync_cursor = self.sqlite_conn.cursor()
                        sync_had_outer_transaction = bool(self.sqlite_conn.in_transaction)
                        sync_savepoint_name = "sp_update_project_sync"
                        if sync_had_outer_transaction:
                            sync_cursor.execute(f"SAVEPOINT {sync_savepoint_name}")
                        else:
                            sync_cursor.execute("BEGIN IMMEDIATE")
                        try:
                            sync_cursor.execute(
                                "UPDATE projects SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0 WHERE id = ?",
                                (target_local_id,),
                            )
                            if sync_had_outer_transaction:
                                sync_cursor.execute(f"RELEASE SAVEPOINT {sync_savepoint_name}")
                            else:
                                self.sqlite_conn.commit()
                        except Exception:
                            if sync_had_outer_transaction:
                                sync_cursor.execute(f"ROLLBACK TO SAVEPOINT {sync_savepoint_name}")
                                sync_cursor.execute(f"RELEASE SAVEPOINT {sync_savepoint_name}")
                            else:
                                self.sqlite_conn.rollback()
                            raise
                        finally:
                            sync_cursor.close()
            except Exception as e:
                safe_print(f"WARNING: [Repo] تخطي تحديث MongoDB: {e}")

        # ⚡ إبطال الـ cache بعد تحديث المشروع
        if CACHE_ENABLED and hasattr(self, "_projects_cache"):
            self._projects_cache.invalidate()
            safe_print("INFO: ⚡ تم إبطال cache المشاريع بعد التحديث")

        # ⚡ إبطال cache الداشبورد لأن الأرقام تغيرت
        Repository._dashboard_cache = None
        Repository._dashboard_cache_time = 0

        return project_data

    def delete_project(self, project_id: str, client_id: str | None = None) -> bool:
        """🗑️ حذف مشروع نهائياً من قاعدة البيانات"""
        safe_print(f"INFO: [Repo] 🗑️ جاري حذف المشروع: {project_id}")

        try:
            target_row = self._resolve_project_target_row(project_id, client_id or "")
            if not target_row:
                safe_print(f"WARNING: [Repo] المشروع غير موجود: {project_id}")
                return False

            project = self.get_project_by_number(
                str(target_row.get("id") or project_id),
                str(target_row.get("client_id") or client_id or ""),
            )

            if not project:
                safe_print(f"WARNING: [Repo] المشروع غير موجود: {project_id}")
                return False

            project_name = project.name
            mongo_id = getattr(project, "_mongo_id", None)
            local_id = getattr(project, "id", None)
            project_aliases = self._project_reference_values(target_row)

            safe_print(
                f"INFO: [Repo] وجدنا المشروع: {project_name}, mongo_id={mongo_id}, local_id={local_id}"
            )

            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            if self.online and mongo_id and self.mongo_db is not None:
                try:
                    result = self.mongo_db.projects.update_one(
                        {
                            "$or": [
                                {"_id": self._to_objectid(mongo_id)},
                                {"_mongo_id": mongo_id},
                                {"name": project_name},
                            ]
                        },
                        {
                            "$set": {
                                "is_deleted": True,
                                "sync_status": "deleted",
                                "last_modified": now_dt,
                            }
                        },
                    )
                    self._delete_project_related_rows_mongo(project_name, now_dt, project_aliases)

                    if getattr(result, "matched_count", 0) > 0:
                        self.sqlite_cursor.execute("DELETE FROM projects WHERE id = ?", (local_id,))
                        self._delete_project_related_rows_sqlite(
                            project_name,
                            now_iso,
                            project_aliases,
                            hard_delete=True,
                            project_record_id=project.id,
                        )
                        self.sqlite_conn.commit()
                        safe_print("INFO: [Repo] تم تعليم حذف المشروع والدفعات ثم حذفها محلياً")
                    else:
                        self.sqlite_cursor.execute(
                            """
                            UPDATE projects
                            SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                            WHERE id = ?
                            """,
                            (now_iso, local_id),
                        )
                        self._delete_project_related_rows_sqlite(
                            project_name,
                            now_iso,
                            project_aliases,
                            hard_delete=False,
                            project_record_id=project.id,
                        )
                        self.sqlite_conn.commit()
                except Exception as e:
                    safe_print(f"WARNING: [Repo] تخطي تعليم حذف MongoDB: {e}")
                    self.sqlite_cursor.execute(
                        """
                        UPDATE projects
                        SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                        WHERE id = ?
                        """,
                        (now_iso, local_id),
                    )
                    self._delete_project_related_rows_sqlite(
                        project_name,
                        now_iso,
                        project_aliases,
                        hard_delete=False,
                        project_record_id=project.id,
                    )
                    self.sqlite_conn.commit()
            else:
                self.sqlite_cursor.execute(
                    """
                    UPDATE projects
                    SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                    WHERE id = ?
                    """,
                    (now_iso, local_id),
                )
                self._delete_project_related_rows_sqlite(
                    project_name,
                    now_iso,
                    project_aliases,
                    hard_delete=False,
                    project_record_id=project.id,
                )
                self.sqlite_conn.commit()

            safe_print(f"SUCCESS: [Repo] ✅ تم حذف المشروع {project_name} بنجاح")

            # ⚡ إبطال الـ cache بعد حذف المشروع
            if CACHE_ENABLED and hasattr(self, "_projects_cache"):
                self._projects_cache.invalidate()
                safe_print("INFO: ⚡ تم إبطال cache المشاريع بعد الحذف")

            # ⚡ إبطال cache الداشبورد لأن الأرقام تغيرت
            Repository._dashboard_cache = None
            Repository._dashboard_cache_time = 0

            return True

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف المشروع: {e}")

            traceback.print_exc()
            return False

    def get_project_revenue(self, project_name: str, client_id: str | None = None) -> float:
        """(معدلة بالطريقة البسيطة) تحسب إجمالي إيرادات مشروع"""
        safe_print(f"INFO: [Repo] جاري حساب إيرادات مشروع: {project_name}")
        total_revenue = 0.0
        try:
            invoices = self.get_invoices_for_project(project_name, client_id=client_id)
            for inv in invoices:
                total_revenue += inv.total_amount
            safe_print(f"INFO: [Repo] إيرادات المشروع (محسوبة): {total_revenue}")
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب إيرادات المشروع: {e}")
        return total_revenue

    def get_project_expenses(self, project_name: str, client_id: str | None = None) -> float:
        """(معدلة بالطريقة البسيطة) تحسب إجمالي مصروفات مشروع"""
        safe_print(f"INFO: [Repo] جاري حساب مصروفات مشروع: {project_name}")
        total_expenses = 0.0
        try:
            expenses = self.get_expenses_for_project(project_name, client_id=client_id)
            for exp in expenses:
                total_expenses += exp.amount
            safe_print(f"INFO: [Repo] مصروفات المشروع (محسوبة): {total_expenses}")
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب مصروفات المشروع: {e}")
        return total_expenses

    def get_invoices_for_project(
        self, project_name: str, client_id: str | None = None
    ) -> list[schemas.Invoice]:
        """جلب كل الفواتير المرتبطة بمشروع مع دعم aliases واستبعاد الصفوف المحذوفة."""
        requested = normalize_user_text(project_name)
        if not requested:
            return []

        resolved_project, canonical_project_name, aliases, target_client_id = (
            self._resolve_project_context(requested, client_id)
        )
        if not resolved_project or not canonical_project_name:
            return []
        safe_print(f"INFO: [Repo] جلب فواتير مشروع: {canonical_project_name}")

        if self.online:
            try:
                query_filter = {
                    "project_id": {"$in": list(aliases)} if aliases else canonical_project_name,
                    "status": {"$ne": schemas.InvoiceStatus.VOID.value},
                }
                data = list(
                    self.mongo_db.invoices.find(self._merge_active_filter_mongo(query_filter))
                )
                invoices_list = []
                for d in data:
                    mongo_id = str(d.pop("_id"))
                    # حذف _mongo_id و mongo_id من البيانات لتجنب التكرار
                    d.pop("_mongo_id", None)
                    d.pop("mongo_id", None)
                    if not self._row_matches_project_scope(
                        d.get("project_id"),
                        canonical_project_name,
                        aliases,
                        target_client_id=target_client_id,
                        row_client_id=d.get("client_id"),
                    ):
                        continue
                    invoices_list.append(schemas.Invoice(**d, _mongo_id=mongo_id))
                return invoices_list
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب فواتير المشروع (Mongo): {e}")

        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"SELECT * {self._is_active_filter_sql('invoices')} AND status != ?",
                        (schemas.InvoiceStatus.VOID.value,),
                    )
                    rows = [dict(row) for row in cursor.fetchall()]
                finally:
                    cursor.close()

            matching_rows = [
                row
                for row in rows
                if self._row_matches_project_scope(
                    row.get("project_id"),
                    canonical_project_name,
                    aliases,
                    target_client_id=target_client_id,
                    row_client_id=row.get("client_id"),
                )
            ]
            data_list = []
            for row_dict in matching_rows:
                row_dict["items"] = json.loads(row_dict["items"])
                data_list.append(schemas.Invoice(**row_dict))
            return data_list
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب فواتير المشروع (SQLite): {e}")
            return []

    def get_expenses_for_project(
        self, project_name: str, client_id: str | None = None
    ) -> list[schemas.Expense]:
        """جلب مصروفات مشروع مع توحيد المراجع وإزالة الصفوف المكررة."""
        requested = normalize_user_text(project_name)
        if not requested:
            return []

        resolved_project, canonical_project_name, aliases, _ = self._resolve_project_context(
            requested,
            client_id,
        )
        if not resolved_project or not canonical_project_name:
            return []
        name_is_ambiguous = self._has_ambiguous_project_name_reference(canonical_project_name)

        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(f"SELECT * {self._is_active_filter_sql('expenses')}")
                    rows = [dict(row) for row in cursor.fetchall()]
                finally:
                    cursor.close()

            matching_rows = [
                row
                for row in rows
                if self._row_matches_project(row.get("project_id"), canonical_project_name, aliases)
            ]
            if name_is_ambiguous:
                matching_rows = [
                    row
                    for row in matching_rows
                    if not self._is_ambiguous_name_only_project_link(
                        row.get("project_id"),
                        canonical_project_name,
                        aliases,
                    )
                ]
            deduped_rows = self._dedupe_rows_by_signature(matching_rows, self._expense_signature)
            deduped_rows.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
            return [schemas.Expense(**row) for row in deduped_rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب مصروفات المشروع (SQLite): {e}")

        if self.online:
            try:
                query_filter = (
                    {"project_id": {"$in": list(aliases)}}
                    if aliases
                    else {"project_id": canonical_project_name}
                )
                data = list(
                    self.mongo_db.expenses.find(self._merge_active_filter_mongo(query_filter))
                )
                rows = []
                for item in data:
                    mongo_id = str(item.pop("_id"))
                    item.pop("_mongo_id", None)
                    item.pop("mongo_id", None)
                    item["_mongo_id"] = mongo_id
                    rows.append(item)
                if name_is_ambiguous:
                    rows = [
                        row
                        for row in rows
                        if not self._is_ambiguous_name_only_project_link(
                            row.get("project_id"),
                            canonical_project_name,
                            aliases,
                        )
                    ]
                deduped_rows = self._dedupe_rows_by_signature(rows, self._expense_signature)
                deduped_rows.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
                return [schemas.Expense(**row) for row in deduped_rows]
            except Exception as e:
                safe_print(f"ERROR: [Repo] فشل جلب مصروفات المشروع (Mongo): {e}")

        return []

    def get_total_expenses_for_project(
        self, project_name: str, client_id: str | None = None
    ) -> float:
        """إجمالي المصروفات لمشروع بعد التطبيع وإزالة التكرار."""
        try:
            expenses = self.get_expenses_for_project(project_name, client_id=client_id)
            return float(sum(float(getattr(expense, "amount", 0.0) or 0.0) for expense in expenses))
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب إجمالي المصروفات للمشروع: {e}")
            return 0.0

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
        if (
            not force_refresh
            and Repository._dashboard_cache
            and (current_time - Repository._dashboard_cache_time) < Repository._DASHBOARD_CACHE_TTL
        ):
            safe_print("INFO: [Repo] استخدام cache الداشبورد")
            return Repository._dashboard_cache

        safe_print("INFO: [Repo] ⚡ جاري حساب أرقام الداشبورد (SQLite - سريع)...")
        total_collected = 0.0
        total_outstanding = 0.0
        total_expenses = 0.0
        net_profit_cash = 0.0  # ⚡ تهيئة المتغير هنا لتجنب الخطأ

        try:
            payments = self.get_all_payments()
            expenses = self.get_all_expenses()
            projects = self.get_all_projects()
            total_collected = sum(
                float(getattr(payment, "amount", 0.0) or 0.0) for payment in payments
            )
            total_expenses = sum(
                float(getattr(expense, "amount", 0.0) or 0.0) for expense in expenses
            )

            project_rows: list[dict[str, Any]] = []
            exact_name_matches: dict[str, list[dict[str, Any]]] = {}
            local_id_matches: dict[str, list[dict[str, Any]]] = {}
            mongo_id_matches: dict[str, list[dict[str, Any]]] = {}
            project_code_matches: dict[str, list[dict[str, Any]]] = {}
            invoice_number_matches: dict[str, list[dict[str, Any]]] = {}
            normalized_name_matches: dict[str, list[dict[str, Any]]] = {}

            def _append_match(
                index: dict[str, list[dict[str, Any]]], key: str, row: dict[str, Any]
            ) -> None:
                if not key:
                    return
                index.setdefault(key, []).append(row)

            for project in projects:
                row = {
                    "id": str(getattr(project, "id", None) or "").strip(),
                    "name": str(getattr(project, "name", "") or "").strip(),
                    "client_id": str(getattr(project, "client_id", "") or "").strip(),
                    "_mongo_id": str(getattr(project, "_mongo_id", None) or "").strip(),
                    "project_code": str(getattr(project, "project_code", "") or "").strip(),
                    "invoice_number": str(getattr(project, "invoice_number", "") or "").strip(),
                    "status": getattr(project, "status", None),
                    "total_amount": float(getattr(project, "total_amount", 0.0) or 0.0),
                }
                row["scope_key"] = self._project_scope_key(
                    row["_mongo_id"] or row["id"] or row["name"],
                    row["client_id"],
                    project_row=row,
                )
                project_rows.append(row)
                _append_match(exact_name_matches, row["name"], row)
                _append_match(local_id_matches, row["id"], row)
                _append_match(mongo_id_matches, row["_mongo_id"], row)
                _append_match(
                    project_code_matches, self._project_text_key(row["project_code"]), row
                )
                _append_match(
                    invoice_number_matches, self._project_text_key(row["invoice_number"]), row
                )
                _append_match(normalized_name_matches, self._project_text_key(row["name"]), row)

            client_keys_cache: dict[str, set[str]] = {}
            project_resolution_cache: dict[tuple[str, str], dict[str, Any] | None] = {}

            def _client_keys(client_id: Any) -> set[str]:
                cache_key = normalize_user_text(client_id)
                cached_keys = client_keys_cache.get(cache_key)
                if cached_keys is not None:
                    return cached_keys

                client_keys = {
                    self._project_text_key(reference)
                    for reference in self._client_reference_values(client_id)
                    if self._project_text_key(reference)
                }
                if not client_keys:
                    normalized_client_key = self._project_text_key(client_id)
                    if normalized_client_key:
                        client_keys = {normalized_client_key}
                client_keys_cache[cache_key] = client_keys
                return client_keys

            def _pick_project(
                candidates: list[dict[str, Any]], client_id: Any
            ) -> dict[str, Any] | None:
                if not candidates:
                    return None
                if len(candidates) == 1:
                    return candidates[0]

                client_keys = _client_keys(client_id)
                if client_keys:
                    by_client = [
                        row
                        for row in candidates
                        if self._project_text_key(row.get("client_id")) in client_keys
                    ]
                    if len(by_client) == 1:
                        return by_client[0]
                return None

            def _resolve_project_row_fast(
                project_ref: Any, client_id: Any
            ) -> dict[str, Any] | None:
                normalized_reference = normalize_user_text(project_ref)
                normalized_client = normalize_user_text(client_id)
                cache_key = (normalized_client, normalized_reference)
                if cache_key in project_resolution_cache:
                    return project_resolution_cache[cache_key]

                if not normalized_reference:
                    project_resolution_cache[cache_key] = None
                    return None

                reference_key = self._project_text_key(normalized_reference)
                chosen = _pick_project(exact_name_matches.get(normalized_reference, []), client_id)
                if chosen is None and normalized_reference.isdigit():
                    chosen = _pick_project(
                        local_id_matches.get(normalized_reference, []), client_id
                    )
                if chosen is None:
                    chosen = _pick_project(
                        mongo_id_matches.get(normalized_reference, []), client_id
                    )
                if chosen is None:
                    for alias_index in (project_code_matches, invoice_number_matches):
                        chosen = _pick_project(alias_index.get(reference_key, []), client_id)
                        if chosen is not None:
                            break
                if chosen is None:
                    chosen = _pick_project(
                        normalized_name_matches.get(reference_key, []), client_id
                    )

                project_resolution_cache[cache_key] = chosen
                return chosen

            paid_by_project: dict[tuple[str, str], float] = {}
            for payment in payments:
                payment_project_id = getattr(payment, "project_id", "")
                payment_client_id = getattr(payment, "client_id", "")
                resolved_project = _resolve_project_row_fast(payment_project_id, payment_client_id)
                if resolved_project is not None:
                    project_key = resolved_project["scope_key"]
                else:
                    project_key = self._project_scope_key(payment_project_id, payment_client_id)
                if not project_key[1]:
                    continue
                paid_by_project[project_key] = paid_by_project.get(project_key, 0.0) + float(
                    getattr(payment, "amount", 0.0) or 0.0
                )

            active_statuses = {
                schemas.ProjectStatus.ACTIVE,
                schemas.ProjectStatus.PLANNING,
                schemas.ProjectStatus.ON_HOLD,
            }
            for project_row in project_rows:
                if project_row["status"] not in active_statuses:
                    continue
                project_key = project_row["scope_key"]
                project_total = project_row["total_amount"]
                project_paid = float(paid_by_project.get(project_key, 0.0))
                project_remaining = project_total - project_paid
                if project_remaining > 0:
                    total_outstanding += project_remaining

            net_profit_cash = total_collected - total_expenses

            safe_print(
                f"INFO: [Repo] (Offline) Collected: {total_collected}, Expenses: {total_expenses}, Outstanding: {total_outstanding}"
            )

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حساب أرقام الداشبورد (SQLite): {e}")

        result = {
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
            "total_expenses": total_expenses,
            "net_profit_cash": net_profit_cash,
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
                currencies_data = list(
                    self.mongo_db.currencies.find(self._merge_active_filter_mongo()).sort(
                        [("is_base", -1), ("code", 1)]
                    )
                )
                if currencies_data:
                    currencies = []
                    for c in currencies_data:
                        currencies.append(
                            {
                                "id": str(c.get("_id", "")),
                                "code": c.get("code", ""),
                                "name": c.get("name", ""),
                                "symbol": c.get("symbol", ""),
                                "rate": c.get("rate", 1.0),
                                "is_base": bool(c.get("is_base", False)),
                                "active": bool(c.get("active", True)),
                            }
                        )
                    safe_print(f"INFO: [Repo] تم جلب {len(currencies)} عملة من الأونلاين")
                    return currencies
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل جلب العملات من MongoDB: {e}")

        # الجلب من SQLite
        try:
            self.sqlite_cursor.execute(
                """
                SELECT * FROM currencies
                WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                AND (is_deleted = 0 OR is_deleted IS NULL)
                ORDER BY is_base DESC, code ASC
                """
            )
            rows = self.sqlite_cursor.fetchall()
            currencies = []
            for row in rows:
                currencies.append(
                    {
                        "id": row["id"],
                        "code": row["code"],
                        "name": row["name"],
                        "symbol": row["symbol"],
                        "rate": row["rate"],
                        "is_base": bool(row["is_base"]),
                        "active": bool(row["active"]),
                    }
                )
            return currencies
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب العملات: {e}")
            return []

    def save_currency(self, currency_data: dict) -> bool:
        """حفظ أو تحديث عملة (مع مزامنة أونلاين وأوفلاين)"""
        now = datetime.now()
        now_iso = now.isoformat()
        code = currency_data.get("code", "").upper()

        try:
            # 1. الحفظ في SQLite أولاً
            self.sqlite_cursor.execute("SELECT id FROM currencies WHERE code = ?", (code,))
            existing = self.sqlite_cursor.fetchone()

            if existing:
                sql = """
                    UPDATE currencies SET
                        name = ?, symbol = ?, rate = ?, active = ?, last_modified = ?,
                        sync_status = ?, dirty_flag = 1, is_deleted = 0
                    WHERE code = ?
                """
                self.sqlite_cursor.execute(
                    sql,
                    (
                        currency_data.get("name", code),
                        currency_data.get("symbol", code),
                        currency_data.get("rate", 1.0),
                        1 if currency_data.get("active", True) else 0,
                        now_iso,
                        "modified_offline",
                        code,
                    ),
                )
            else:
                sql = """
                    INSERT INTO currencies (
                        code, name, symbol, rate, is_base, active,
                        created_at, last_modified, sync_status, dirty_flag, is_deleted
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new_offline', 1, 0)
                """
                is_base = 1 if code == "EGP" else 0
                self.sqlite_cursor.execute(
                    sql,
                    (
                        code,
                        currency_data.get("name", code),
                        currency_data.get("symbol", code),
                        currency_data.get("rate", 1.0),
                        is_base,
                        1 if currency_data.get("active", True) else 0,
                        now_iso,
                        now_iso,
                    ),
                )

            self.sqlite_conn.commit()
            safe_print(f"INFO: [Repo] تم حفظ العملة {code} محلياً")
            try:
                from core.signals import app_signals

                app_signals.emit_data_changed("currencies")
            except Exception:
                pass

            # 2. المزامنة مع MongoDB
            if self.online:
                try:
                    mongo_data = {
                        "code": code,
                        "name": currency_data.get("name", code),
                        "symbol": currency_data.get("symbol", code),
                        "rate": currency_data.get("rate", 1.0),
                        "is_base": code == "EGP",
                        "active": currency_data.get("active", True),
                        "last_modified": now,
                        "sync_status": "synced",
                        "is_deleted": False,
                    }

                    # استخدام upsert للتحديث أو الإضافة
                    self.mongo_db.currencies.update_one(
                        {"code": code}, {"$set": mongo_data}, upsert=True
                    )

                    # تحديث حالة المزامنة
                    self.sqlite_cursor.execute(
                        """
                        UPDATE currencies
                        SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0
                        WHERE code = ?
                        """,
                        (code,),
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
            if code.upper() == "EGP":
                safe_print("WARNING: [Repo] لا يمكن حذف العملة الأساسية")
                return False

            now_dt = datetime.now()
            now_iso = now_dt.isoformat()

            if self.online:
                try:
                    result = self.mongo_db.currencies.update_one(
                        {"code": code.upper()},
                        {
                            "$set": {
                                "is_deleted": True,
                                "sync_status": "deleted",
                                "last_modified": now_dt,
                            }
                        },
                    )
                    if getattr(result, "matched_count", 0) > 0:
                        self.sqlite_cursor.execute(
                            "DELETE FROM currencies WHERE code = ?", (code.upper(),)
                        )
                        self.sqlite_conn.commit()
                        safe_print(f"INFO: [Repo] تم تعليم حذف العملة {code} ثم حذفها محلياً")
                    else:
                        self.sqlite_cursor.execute(
                            """
                            UPDATE currencies
                            SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                            WHERE code = ?
                            """,
                            (now_iso, code.upper()),
                        )
                        self.sqlite_conn.commit()
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل تعليم حذف العملة في MongoDB: {e}")
                    self.sqlite_cursor.execute(
                        """
                        UPDATE currencies
                        SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                        WHERE code = ?
                        """,
                        (now_iso, code.upper()),
                    )
                    self.sqlite_conn.commit()
            else:
                self.sqlite_cursor.execute(
                    """
                    UPDATE currencies
                    SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                    WHERE code = ?
                    """,
                    (now_iso, code.upper()),
                )
                self.sqlite_conn.commit()
            safe_print(f"INFO: [Repo] تم حذف العملة {code}")
            try:
                from core.signals import app_signals

                app_signals.emit_data_changed("currencies")
            except Exception:
                pass
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف العملة {code}: {e}")
            return False

    def fetch_live_exchange_rate(self, currency_code: str) -> float | None:
        """جلب سعر الصرف الحقيقي من الإنترنت"""

        currency_code = normalize_currency_code(currency_code)
        if currency_code == "EGP":
            return 1.0

        try:
            # API 1: Open Exchange Rates
            url = "https://open.er-api.com/v6/latest/USD"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(
                req, timeout=10
            ) as response:  # nosec B310 - URL is hardcoded HTTPS
                data = json.loads(response.read().decode())
                if data.get("result") == "success" and "rates" in data:
                    rates = data["rates"]
                    egp_rate = rates.get("EGP", 0)
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
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(
                req, timeout=10
            ) as response:  # nosec B310 - URL is hardcoded HTTPS
                data = json.loads(response.read().decode())
                if "rates" in data:
                    egp_rate = data["rates"].get("EGP", 0)
                    if egp_rate > 0:
                        safe_print(
                            f"INFO: [Repo] سعر {currency_code} = {egp_rate:.4f} EGP (من API 2)"
                        )
                        return float(round(egp_rate, 4))
        except Exception as e:
            safe_print(f"WARNING: [Repo] فشل جلب السعر من API 2: {e}")

        return None

    def init_default_currencies(self):
        """إنشاء العملات الافتراضية مع جلب الأسعار الحقيقية من الإنترنت"""
        default_currencies = [
            {"code": "EGP", "name": "جنيه مصري", "symbol": "ج.م", "rate": 1.0, "is_base": True},
            {"code": "USD", "name": "دولار أمريكي", "symbol": "دولار"},
            {"code": "SAR", "name": "ريال سعودي", "symbol": "ر.س", "rate": 12.65},
            {"code": "AED", "name": "درهم إماراتي", "symbol": "د.إ", "rate": 12.92},
        ]

        safe_print("INFO: [Repo] جاري إنشاء العملات الافتراضية وجلب الأسعار من الإنترنت...")

        for curr in default_currencies:
            code = curr["code"]

            # جلب السعر الحقيقي من الإنترنت
            if code == "EGP":
                curr["rate"] = 1.0
            else:
                live_rate = self.fetch_live_exchange_rate(code)
                if live_rate:
                    curr["rate"] = live_rate
                else:
                    # أسعار احتياطية في حالة فشل الاتصال
                    fallback_rates = {"USD": 49.50, "SAR": 13.20, "AED": 13.48}
                    curr["rate"] = fallback_rates.get(code, 1.0)
                    safe_print(f"WARNING: [Repo] استخدام سعر احتياطي لـ {code}: {curr['rate']}")

            self.save_currency(curr)

        safe_print("INFO: [Repo] تم إنشاء العملات الافتراضية بنجاح")

    def update_all_exchange_rates(self) -> dict:
        """تحديث جميع أسعار الصرف من الإنترنت"""
        safe_print("INFO: [Repo] جاري تحديث جميع أسعار الصرف...")

        currencies = self.get_all_currencies()
        updated = 0
        failed = 0
        results = {}

        for curr in currencies:
            code = str(curr.get("code") or "").upper()
            normalized_code = normalize_currency_code(code)
            if normalized_code == "EGP":
                continue

            live_rate = self.fetch_live_exchange_rate(normalized_code)
            if live_rate:
                curr["rate"] = live_rate
                self.save_currency(curr)
                updated += 1
                results[code] = {"success": True, "rate": live_rate}
                safe_print(f"INFO: [Repo] تم تحديث {code}: {live_rate}")
            else:
                failed += 1
                results[code] = {"success": False, "rate": curr["rate"]}
                safe_print(f"WARNING: [Repo] فشل تحديث {code}")

        safe_print(f"INFO: [Repo] تم تحديث {updated} عملة، فشل {failed}")
        return {"updated": updated, "failed": failed, "results": results}

    # ============================================
    # دوال تنظيف التكرارات وإصلاح البيانات
    # ============================================

    def cleanup_duplicate_clients(self) -> dict:
        """
        تنظيف العملاء المكررين (يحتفظ بالأقدم ويحذف الأحدث)
        Returns: dict with counts of duplicates found and removed
        """
        safe_print("INFO: [Repo] جاري البحث عن العملاء المكررين...")
        result: dict[str, Any] = {"found": 0, "removed": 0, "details": []}

        try:
            # جلب كل العملاء مرتبين بتاريخ الإنشاء
            self.sqlite_cursor.execute(
                """
                SELECT id, _mongo_id, name, phone, created_at
                FROM clients
                WHERE status != 'مؤرشف'
                ORDER BY created_at ASC
            """
            )
            rows = self.sqlite_cursor.fetchall()

            seen_names = {}  # {name_lower: first_id}
            seen_phones = {}  # {phone_clean: first_id}
            duplicates_to_archive = []

            for row in rows:
                row_dict = dict(row)
                client_id = row_dict["id"]
                name = row_dict.get("name", "").strip().lower()
                phone = row_dict.get("phone", "")
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
                    duplicates_to_archive.append((client_id, row_dict.get("_mongo_id"), reason))
                    result["found"] += 1

            # أرشفة المكررين
            for client_id, _mongo_id, reason in duplicates_to_archive:
                try:
                    self.sqlite_cursor.execute(
                        "UPDATE clients SET status = 'مؤرشف', sync_status = 'modified_offline' WHERE id = ?",
                        (client_id,),
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
                                {"_id": self._to_objectid(mongo_id)}, {"$set": {"status": "مؤرشف"}}
                            )
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل مزامنة أرشفة العملاء المكررين: {e}")

            safe_print(
                f"INFO: [Repo] تم العثور على {result['found']} عميل مكرر، تم أرشفة {result['removed']}"
            )

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تنظيف العملاء المكررين: {e}")

        return result

    def cleanup_duplicate_projects(self) -> dict:
        """
        تنظيف المشاريع المكررة (نفس الاسم لنفس العميل)
        """
        safe_print("INFO: [Repo] جاري البحث عن المشاريع المكررة...")
        result: dict[str, Any] = {"found": 0, "removed": 0, "details": []}

        try:
            self.sqlite_cursor.execute(
                """
                SELECT id, _mongo_id, name, client_id, created_at
                FROM projects
                WHERE status != 'مؤرشف'
                ORDER BY created_at ASC
            """
            )
            rows = self.sqlite_cursor.fetchall()

            seen_projects = {}  # {(name_lower, client_id): first_id}
            duplicates_to_archive = []

            for row in rows:
                row_dict = dict(row)
                project_id = row_dict["id"]
                name = row_dict.get("name", "").strip().lower()
                client_id = row_dict.get("client_id", "")
                key = (name, client_id)

                if key in seen_projects:
                    duplicates_to_archive.append(
                        (
                            project_id,
                            row_dict.get("_mongo_id"),
                            f"مشروع مكرر: {row_dict.get('name')}",
                        )
                    )
                    result["found"] += 1
                else:
                    seen_projects[key] = project_id

            for project_id, _mongo_id, reason in duplicates_to_archive:
                try:
                    self.sqlite_cursor.execute(
                        "UPDATE projects SET status = 'مؤرشف', sync_status = 'modified_offline' WHERE id = ?",
                        (project_id,),
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
                                {"_id": self._to_objectid(mongo_id)}, {"$set": {"status": "مؤرشف"}}
                            )
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل مزامنة أرشفة المشاريع المكررة: {e}")

            safe_print(
                f"INFO: [Repo] تم العثور على {result['found']} مشروع مكرر، تم أرشفة {result['removed']}"
            )

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تنظيف المشاريع المكررة: {e}")

        return result

    def cleanup_duplicate_payments(self) -> dict:
        """
        تنظيف الدفعات المكررة (نفس المشروع + نفس التاريخ + نفس المبلغ)
        """
        safe_print("INFO: [Repo] جاري البحث عن الدفعات المكررة...")
        result: dict[str, Any] = {"found": 0, "removed": 0, "details": []}

        try:
            self.sqlite_cursor.execute(
                """
                SELECT id, _mongo_id, project_id, date, amount, created_at
                FROM payments
                ORDER BY created_at ASC
            """
            )
            rows = self.sqlite_cursor.fetchall()

            seen_payments = {}  # {(project_id, date_short, amount): first_id}
            duplicates_to_delete = []

            for row in rows:
                row_dict = dict(row)
                payment_id = row_dict["id"]
                project_id = row_dict.get("project_id", "")
                date_str = str(row_dict.get("date", ""))[:10]  # YYYY-MM-DD
                amount = row_dict.get("amount", 0)
                key = (project_id, date_str, amount)

                if key in seen_payments:
                    duplicates_to_delete.append(
                        (
                            payment_id,
                            row_dict.get("_mongo_id"),
                            f"دفعة مكررة: {amount} في {date_str}",
                        )
                    )
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

            safe_print(
                f"INFO: [Repo] تم العثور على {result['found']} دفعة مكررة، تم حذف {result['removed']}"
            )

        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تنظيف الدفعات المكررة: {e}")

        return result

    def fix_account_hierarchy(self) -> dict:
        """
        إصلاح العلاقات الهرمية للحسابات (ربط parent_code بشكل صحيح)
        """
        safe_print("INFO: [Repo] جاري إصلاح العلاقات الهرمية للحسابات...")
        result: dict[str, Any] = {"fixed": 0, "errors": 0, "details": []}

        try:
            # جلب كل الحسابات
            self.sqlite_cursor.execute("SELECT * FROM accounts ORDER BY code")
            rows = self.sqlite_cursor.fetchall()

            accounts_by_code = {}
            for row in rows:
                row_dict = dict(row)
                accounts_by_code[row_dict["code"]] = row_dict

            for code, account in accounts_by_code.items():
                # تحديد الحساب الأب بناءً على الكود
                # مثال: 1100 -> parent = 1000, 1110 -> parent = 1100
                if len(code) > 4:
                    parent_code = code[:-1] + "0"  # 11100 -> 11100 -> 1110
                    if parent_code not in accounts_by_code:
                        parent_code = code[:-2] + "00"  # 1110 -> 1100
                    if parent_code not in accounts_by_code:
                        parent_code = code[:-3] + "000"  # 1100 -> 1000
                elif len(code) == 4:
                    parent_code = code[0] + "000"  # 1100 -> 1000
                else:
                    parent_code = None

                current_parent = account.get("parent_id") or account.get("parent_code")

                # تحديث إذا كان الـ parent مختلف
                if parent_code and parent_code in accounts_by_code and parent_code != code:
                    if current_parent != parent_code:
                        try:
                            self.sqlite_cursor.execute(
                                "UPDATE accounts SET parent_id = ?, sync_status = 'modified_offline' WHERE code = ?",
                                (parent_code, code),
                            )
                            result["fixed"] += 1
                            result["details"].append({"code": code, "new_parent": parent_code})
                            safe_print(
                                f"INFO: [Repo] تم ربط الحساب {code} بالحساب الأب {parent_code}"
                            )
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
                            {
                                "$set": {
                                    "parent_id": detail["new_parent"],
                                    "parent_code": detail["new_parent"],
                                }
                            },
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
            if not self._table_has_column("accounts", "is_group"):
                safe_print(
                    "INFO: [Repo] تم تخطي تحديث is_group لأن العمود غير موجود في SQLite الحالية"
                )
                return

            # أولاً: تعيين كل الحسابات كـ is_group = False
            self.sqlite_cursor.execute("UPDATE accounts SET is_group = 0")

            # ثانياً: تحديد الحسابات التي لها أطفال
            self.sqlite_cursor.execute(
                """
                UPDATE accounts SET is_group = 1
                WHERE code IN (
                    SELECT DISTINCT parent_id FROM accounts WHERE parent_id IS NOT NULL AND parent_id != ''
                )
            """
            )

            self.sqlite_conn.commit()
            safe_print("INFO: [Repo] تم تحديث علامات is_group للحسابات")

        except Exception as e:
            safe_print(f"WARNING: [Repo] فشل تحديث علامات is_group: {e}")

    def cleanup_all_duplicates(self) -> dict:
        """
        تنظيف شامل لكل التكرارات (عملاء + مشاريع + دفعات)
        """
        safe_print("INFO: [Repo] ========== بدء التنظيف الشامل ==========")

        results = {
            "clients": self.cleanup_duplicate_clients(),
            "projects": self.cleanup_duplicate_projects(),
            "payments": self.cleanup_duplicate_payments(),
            "accounts": self.fix_account_hierarchy(),
        }

        total_found = sum(r.get("found", 0) for r in results.values())
        total_fixed = sum(r.get("removed", 0) + r.get("fixed", 0) for r in results.values())

        safe_print("INFO: [Repo] ========== انتهى التنظيف الشامل ==========")
        safe_print(f"INFO: [Repo] إجمالي المشاكل: {total_found}, تم إصلاح: {total_fixed}")

        return results

    # ==================== دوال التعامل مع المهام (Tasks) ====================

    def _normalize_related_project_ref(
        self, project_ref: Any, client_ref: Any = None
    ) -> str | None:
        """Normalize task/project links to a stable project reference when possible."""
        raw_ref = str(project_ref or "").strip()
        if not raw_ref:
            return None

        resolved_project = self._resolve_project_row(raw_ref, str(client_ref or "").strip())
        if resolved_project:
            return self._stable_project_reference(resolved_project, raw_ref)

        normalized = normalize_user_text(raw_ref)
        return normalized or raw_ref

    def _normalize_related_client_ref(self, client_ref: Any) -> str | None:
        raw_ref = str(client_ref or "").strip()
        if not raw_ref:
            return None

        client_row = self._resolve_local_client_row(raw_ref)
        if not client_row:
            return None

        local_id = str(client_row.get("id") or "").strip()
        return local_id or None

    def create_task(self, task_data: dict) -> dict:
        """
        إنشاء مهمة جديدة
        """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        # تحضير البيانات

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

        tags_json = json.dumps(task_data.get("tags", []), ensure_ascii=False)

        # related_client_id محلياً يجب أن يبقى local client id بسبب قيد FOREIGN KEY في SQLite.
        raw_related_client = task_data.get("related_client_id")
        related_client = self._normalize_related_client_ref(raw_related_client)
        related_project = self._normalize_related_project_ref(
            task_data.get("related_project_id"),
            raw_related_client,
        )
        if not related_client and related_project:
            resolved_project = self._resolve_project_row(
                task_data.get("related_project_id"),
                str(raw_related_client or "").strip(),
            )
            if resolved_project:
                related_client = self._normalize_related_client_ref(
                    resolved_project.get("client_id")
                )

        with self._lock:
            cursor = self.sqlite_conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        "new_offline",
                        now_iso,
                        now_iso,
                        task_data.get("title", ""),
                        task_data.get("description") or None,
                        task_data.get("priority", "MEDIUM"),
                        task_data.get("status", "TODO"),
                        task_data.get("category", "GENERAL"),
                        task_data.get("due_date"),
                        task_data.get("due_time"),
                        task_data.get("completed_at"),
                        related_project,
                        related_client,
                        tags_json,
                        1 if task_data.get("reminder", False) else 0,
                        task_data.get("reminder_minutes", 30),
                    ),
                )
                self.sqlite_conn.commit()
                local_id = cursor.lastrowid
            finally:
                cursor.close()
        task_data["id"] = str(local_id)
        task_data["created_at"] = now_iso
        task_data["last_modified"] = now_iso

        safe_print(f"INFO: [Repo] تم إنشاء مهمة: {task_data.get('title')} (ID: {local_id})")

        # مزامنة مع MongoDB
        if self.online:
            try:
                mongo_data = task_data.copy()
                mongo_data["created_at"] = now_dt
                mongo_data["last_modified"] = now_dt
                if mongo_data.get("due_date"):
                    mongo_data["due_date"] = (
                        datetime.fromisoformat(mongo_data["due_date"])
                        if isinstance(mongo_data["due_date"], str)
                        else mongo_data["due_date"]
                    )
                if mongo_data.get("completed_at"):
                    mongo_data["completed_at"] = (
                        datetime.fromisoformat(mongo_data["completed_at"])
                        if isinstance(mongo_data["completed_at"], str)
                        else mongo_data["completed_at"]
                    )

                result = self.mongo_db.tasks.insert_one(mongo_data)
                mongo_id = str(result.inserted_id)

                self.sqlite_cursor.execute(
                    "UPDATE tasks SET _mongo_id = ?, sync_status = 'synced', dirty_flag = 0 WHERE id = ?",
                    (mongo_id, local_id),
                )
                self.sqlite_conn.commit()
                task_data["_mongo_id"] = mongo_id
                safe_print(f"INFO: [Repo] تم مزامنة المهمة أونلاين (Mongo ID: {mongo_id})")
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل مزامنة المهمة: {e}")

        return task_data

    def update_task(self, task_id: str, task_data: dict) -> dict:
        """
        تحديث مهمة موجودة
        """
        now_dt = datetime.now()
        now_iso = now_dt.isoformat()

        tags_json = json.dumps(task_data.get("tags", []), ensure_ascii=False)

        # related_client_id محلياً يجب أن يبقى local client id بسبب قيد FOREIGN KEY في SQLite.
        raw_related_client = task_data.get("related_client_id")
        related_client = self._normalize_related_client_ref(raw_related_client)
        related_project = self._normalize_related_project_ref(
            task_data.get("related_project_id"),
            raw_related_client,
        )
        if not related_client and related_project:
            resolved_project = self._resolve_project_row(
                task_data.get("related_project_id"),
                str(raw_related_client or "").strip(),
            )
            if resolved_project:
                related_client = self._normalize_related_client_ref(
                    resolved_project.get("client_id")
                )

        sql = """
            UPDATE tasks SET
                title = ?, description = ?, priority = ?, status = ?, category = ?,
                due_date = ?, due_time = ?, completed_at = ?,
                related_project_id = ?, related_client_id = ?, tags = ?,
                reminder = ?, reminder_minutes = ?, is_archived = ?,
                last_modified = ?, sync_status = 'modified_offline'
            WHERE id = ? OR _mongo_id = ?
        """

        with self._lock:
            cursor = self.sqlite_conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        task_data.get("title", ""),
                        task_data.get("description") or None,
                        task_data.get("priority", "MEDIUM"),
                        task_data.get("status", "TODO"),
                        task_data.get("category", "GENERAL"),
                        task_data.get("due_date"),
                        task_data.get("due_time"),
                        task_data.get("completed_at"),
                        related_project,
                        related_client,
                        tags_json,
                        1 if task_data.get("reminder", False) else 0,
                        task_data.get("reminder_minutes", 30),
                        1 if task_data.get("is_archived", False) else 0,
                        now_iso,
                        task_id,
                        task_id,
                    ),
                )
                self.sqlite_conn.commit()
            finally:
                cursor.close()

        safe_print(f"INFO: [Repo] تم تحديث مهمة: {task_data.get('title')}")

        # مزامنة مع MongoDB
        if self.online:
            try:
                with self._lock:
                    cursor = self.sqlite_conn.cursor()
                    try:
                        cursor.execute(
                            "SELECT id, _mongo_id FROM tasks WHERE id = ? OR _mongo_id = ?",
                            (task_id, task_id),
                        )
                        row = cursor.fetchone()
                    finally:
                        cursor.close()

                local_id = str((row["id"] if row else "") or "").strip()
                mongo_id = str(
                    task_data.get("_mongo_id") or (row["_mongo_id"] if row else "") or ""
                ).strip()
                update_data = task_data.copy()
                update_data["last_modified"] = now_dt
                update_data["sync_status"] = "synced"
                update_data["is_deleted"] = False
                if update_data.get("due_date") and isinstance(update_data["due_date"], str):
                    update_data["due_date"] = datetime.fromisoformat(update_data["due_date"])
                if update_data.get("completed_at") and isinstance(update_data["completed_at"], str):
                    update_data["completed_at"] = datetime.fromisoformat(
                        update_data["completed_at"]
                    )

                task_query = {
                    "$or": [
                        {"id": task_id},
                        {"id": local_id},
                    ]
                }
                if mongo_id:
                    task_query["$or"].extend(
                        [
                            {"_id": self._to_objectid(mongo_id)},
                            {"_mongo_id": mongo_id},
                        ]
                    )

                result = self.mongo_db.tasks.update_one(
                    task_query,
                    {"$set": update_data},
                )

                if result and (
                    getattr(result, "matched_count", 0) > 0
                    or getattr(result, "modified_count", 0) > 0
                ):
                    with self._lock:
                        cursor = self.sqlite_conn.cursor()
                        try:
                            cursor.execute(
                                "UPDATE tasks SET sync_status = 'synced', dirty_flag = 0, is_deleted = 0 WHERE id = ? OR _mongo_id = ?",
                                (task_id, task_id),
                            )
                            self.sqlite_conn.commit()
                        finally:
                            cursor.close()
            except Exception as e:
                safe_print(f"WARNING: [Repo] فشل مزامنة تحديث المهمة: {e}")

        return task_data

    def delete_task(self, task_id: str) -> bool:
        """
        حذف مهمة
        """
        try:
            now_dt = datetime.now()
            now_iso = now_dt.isoformat()
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        "SELECT id, _mongo_id FROM tasks WHERE id = ? OR _mongo_id = ?",
                        (task_id, task_id),
                    )
                    row = cursor.fetchone()
                finally:
                    cursor.close()

            local_id = str((row["id"] if row else "") or "").strip()
            mongo_id = str((row["_mongo_id"] if row else "") or "").strip()

            if self.online:
                try:
                    task_query = {
                        "$or": [
                            {"id": task_id},
                            {"id": local_id},
                        ]
                    }
                    if mongo_id:
                        task_query["$or"].extend(
                            [
                                {"_id": self._to_objectid(mongo_id)},
                                {"_mongo_id": mongo_id},
                            ]
                        )

                    result = self.mongo_db.tasks.update_one(
                        task_query,
                        {
                            "$set": {
                                "is_deleted": True,
                                "sync_status": "deleted",
                                "last_modified": now_dt,
                            }
                        },
                    )
                    if getattr(result, "matched_count", 0) > 0:
                        with self._lock:
                            cursor = self.sqlite_conn.cursor()
                            try:
                                cursor.execute(
                                    "DELETE FROM tasks WHERE id = ? OR _mongo_id = ?",
                                    (task_id, task_id),
                                )
                                self.sqlite_conn.commit()
                            finally:
                                cursor.close()
                        safe_print(
                            f"INFO: [Repo] تم تعليم حذف المهمة ثم حذفها محلياً (ID: {task_id})"
                        )
                    else:
                        with self._lock:
                            cursor = self.sqlite_conn.cursor()
                            try:
                                cursor.execute(
                                    """
                                    UPDATE tasks
                                    SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                                    WHERE id = ? OR _mongo_id = ?
                                    """,
                                    (now_iso, task_id, task_id),
                                )
                                self.sqlite_conn.commit()
                            finally:
                                cursor.close()
                except Exception as e:
                    safe_print(f"WARNING: [Repo] فشل تعليم حذف المهمة في MongoDB: {e}")
                    with self._lock:
                        cursor = self.sqlite_conn.cursor()
                        try:
                            cursor.execute(
                                """
                                UPDATE tasks
                                SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                                WHERE id = ? OR _mongo_id = ?
                                """,
                                (now_iso, task_id, task_id),
                            )
                            self.sqlite_conn.commit()
                        finally:
                            cursor.close()
            else:
                with self._lock:
                    cursor = self.sqlite_conn.cursor()
                    try:
                        cursor.execute(
                            """
                            UPDATE tasks
                            SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                            WHERE id = ? OR _mongo_id = ?
                            """,
                            (now_iso, task_id, task_id),
                        )
                        self.sqlite_conn.commit()
                    finally:
                        cursor.close()

            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف المهمة: {e}")
            return False

    def get_task_by_id(self, task_id: str) -> dict | None:
        """
        جلب مهمة بالـ ID
        """
        try:
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"SELECT * {self._is_active_filter_sql('tasks')} AND (id = ? OR _mongo_id = ?)",
                        (task_id, task_id),
                    )
                    row = cursor.fetchone()
                finally:
                    cursor.close()

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
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"SELECT * {self._is_active_filter_sql('tasks')} ORDER BY created_at DESC"
                    )
                    rows = cursor.fetchall()
                finally:
                    cursor.close()

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
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"SELECT * {self._is_active_filter_sql('tasks')} AND status = ? ORDER BY created_at DESC",
                        (status,),
                    )
                    rows = cursor.fetchall()
                finally:
                    cursor.close()
            return [self._row_to_task_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب المهام بالحالة: {e}")
            return []

    def get_tasks_by_project(self, project_id: str) -> list[dict]:
        """
        جلب المهام المرتبطة بمشروع
        """
        try:
            requested_ref = str(project_id or "").strip()
            if not requested_ref:
                return []

            resolved_project, canonical_project_name, aliases, target_client_id = (
                self._resolve_project_context(requested_ref)
            )
            if not resolved_project or not canonical_project_name:
                return []
            aliases.add(requested_ref)
            normalized_ref = normalize_user_text(requested_ref)
            if normalized_ref:
                aliases.add(normalized_ref)
            name_is_ambiguous = self._has_ambiguous_project_name_reference(canonical_project_name)

            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"SELECT * {self._is_active_filter_sql('tasks')} ORDER BY created_at DESC"
                    )
                    rows = [dict(row) for row in cursor.fetchall()]
                finally:
                    cursor.close()

            matching_rows = [
                row
                for row in rows
                if self._row_matches_project_scope(
                    row.get("related_project_id"),
                    canonical_project_name,
                    aliases,
                    target_client_id=target_client_id,
                    row_client_id=row.get("related_client_id"),
                )
            ]
            if name_is_ambiguous:
                matching_rows = [
                    row
                    for row in matching_rows
                    if self._project_text_key(row.get("related_client_id"))
                    or not self._is_ambiguous_name_only_project_link(
                        row.get("related_project_id"),
                        canonical_project_name,
                        aliases,
                    )
                ]
            return [self._row_to_task_dict(row) for row in matching_rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب مهام المشروع: {e}")
            return []

    def get_tasks_by_client(self, client_id: str) -> list[dict]:
        """
        جلب المهام المرتبطة بعميل
        """
        try:
            client_references = self._client_reference_values(client_id)
            if not client_references:
                return []
            normalized_references = {
                self._normalized_key(reference) for reference in client_references
            }

            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"SELECT * {self._is_active_filter_sql('tasks')} ORDER BY created_at DESC"
                    )
                    rows = [dict(row) for row in cursor.fetchall()]
                finally:
                    cursor.close()
            matching_rows = [
                row
                for row in rows
                if self._normalized_key(row.get("related_client_id")) in normalized_references
            ]
            return [self._row_to_task_dict(row) for row in matching_rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب مهام العميل: {e}")
            return []

    def get_overdue_tasks(self) -> list[dict]:
        """
        جلب المهام المتأخرة
        """
        try:
            now_iso = datetime.now().isoformat()
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"""SELECT * {self._is_active_filter_sql('tasks')}
                           AND due_date < ? AND status NOT IN ('COMPLETED', 'CANCELLED')
                           ORDER BY due_date ASC""",
                        (now_iso,),
                    )
                    rows = cursor.fetchall()
                finally:
                    cursor.close()
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
            with self._lock:
                cursor = self.sqlite_conn.cursor()
                try:
                    cursor.execute(
                        f"""SELECT * {self._is_active_filter_sql('tasks')}
                           AND date(due_date) = date(?)
                           ORDER BY due_time ASC""",
                        (today,),
                    )
                    rows = cursor.fetchall()
                finally:
                    cursor.close()
            return [self._row_to_task_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب مهام اليوم: {e}")
            return []

    def _row_to_task_dict(self, row) -> dict:
        """
        تحويل صف قاعدة البيانات إلى dict
        """
        related_client = row["related_client_id"]
        if related_client:
            client_row = self._resolve_local_client_row(related_client)
            if client_row:
                related_client = self._stable_client_reference(client_row, related_client)

        task = {
            "id": str(row["id"]),
            "_mongo_id": row["_mongo_id"],
            "sync_status": row["sync_status"],
            "created_at": row["created_at"],
            "last_modified": row["last_modified"],
            "title": row["title"],
            "description": row["description"],
            "priority": row["priority"],
            "status": row["status"],
            "category": row["category"],
            "due_date": row["due_date"],
            "due_time": row["due_time"],
            "completed_at": row["completed_at"],
            "related_project_id": row["related_project_id"],
            "related_client_id": related_client,
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "reminder": bool(row["reminder"]),
            "reminder_minutes": row["reminder_minutes"] or 30,
            "assigned_to": row["assigned_to"],
            "is_archived": bool(row["is_archived"]) if "is_archived" in row.keys() else False,
        }
        return task

    def _generate_task_id(self) -> str:
        """
        توليد ID فريد للمهمة
        """

        return str(uuid.uuid4())[:8]

    # ⚡ دوال أرقام الفواتير الثابتة
    def get_invoice_number_for_project(
        self, project_name: str, client_id: str | None = None
    ) -> str:
        """
        جلب رقم الفاتورة الثابت للمشروع من جدول invoice_numbers
        """
        try:
            project_row = self._resolve_project_row(project_name, client_id or "")
            if project_row:
                inline_invoice_number = str(project_row.get("invoice_number") or "").strip()
                if inline_invoice_number:
                    return inline_invoice_number

                project_row_id = str(project_row.get("id") or "").strip()
                if project_row_id:
                    self.sqlite_cursor.execute(
                        "SELECT invoice_number FROM invoice_numbers WHERE project_id = ?",
                        (project_row_id,),
                    )
                    row = self.sqlite_cursor.fetchone()
                    if row:
                        return str(row[0])

                canonical_project_name = str(project_row.get("name") or "").strip()
            else:
                canonical_project_name = self.resolve_project_name(
                    project_name, client_id
                ) or normalize_user_text(project_name)
            if not canonical_project_name:
                return ""
            self.sqlite_cursor.execute(
                "SELECT invoice_number FROM invoice_numbers WHERE project_name = ? ORDER BY id LIMIT 2",
                (canonical_project_name,),
            )
            rows = self.sqlite_cursor.fetchall()
            if len(rows) == 1:
                return str(rows[0][0])
            return ""
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب رقم الفاتورة: {e}")
            return ""

    def get_all_invoice_numbers(self) -> dict:
        """
        جلب كل أرقام الفواتير كـ dict keyed by stable project reference.
        يفضّل رقم المشروع المحلي، ثم _mongo_id، ثم الاسم كحل legacy.
        """
        try:
            self.sqlite_cursor.execute(
                "SELECT project_id, project_name, invoice_number FROM invoice_numbers"
            )
            rows = self.sqlite_cursor.fetchall()
            result: dict[str, str] = {}
            for row in rows:
                project_key = str(row[0] or "").strip() or str(row[1] or "").strip()
                invoice_number = str(row[2] or "").strip()
                if project_key and invoice_number:
                    result[project_key] = invoice_number
            return result
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب أرقام الفواتير: {e}")
            return {}

    def ensure_invoice_number(self, project_name: str, client_id: str | None = None) -> str:
        """
        التأكد من وجود رقم فاتورة للمشروع، وإنشاء واحد جديد إذا لم يكن موجوداً
        """
        try:
            project_row = self._resolve_project_row(project_name, client_id or "")
            if not project_row:
                return ""

            project_row_id = str(project_row.get("id") or "").strip()
            canonical_project_name = str(project_row.get("name") or "").strip()
            if not project_row_id or not canonical_project_name:
                return ""

            existing = str(project_row.get("invoice_number") or "").strip()
            if not existing:
                self.sqlite_cursor.execute(
                    "SELECT invoice_number FROM invoice_numbers WHERE project_id = ?",
                    (project_row_id,),
                )
                row = self.sqlite_cursor.fetchone()
                existing = str(row[0]).strip() if row and row[0] else ""

            if not existing:
                existing = self._generate_unique_project_invoice_number()

            self.sqlite_cursor.execute(
                "SELECT id FROM invoice_numbers WHERE project_id = ?",
                (project_row_id,),
            )
            existing_row = self.sqlite_cursor.fetchone()
            if existing_row:
                self.sqlite_cursor.execute(
                    """
                    UPDATE invoice_numbers
                    SET project_name = ?, invoice_number = ?
                    WHERE project_id = ?
                    """,
                    (canonical_project_name, existing, project_row_id),
                )
            else:
                self.sqlite_cursor.execute(
                    "SELECT id FROM invoice_numbers WHERE invoice_number = ?",
                    (existing,),
                )
                invoice_match = self.sqlite_cursor.fetchone()
                if invoice_match:
                    self.sqlite_cursor.execute(
                        """
                        UPDATE invoice_numbers
                        SET project_id = ?, project_name = ?
                        WHERE invoice_number = ?
                        """,
                        (project_row_id, canonical_project_name, existing),
                    )
                else:
                    self.sqlite_cursor.execute(
                        """
                        INSERT INTO invoice_numbers (project_id, project_name, invoice_number, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            project_row_id,
                            canonical_project_name,
                            existing,
                            datetime.now().isoformat(),
                        ),
                    )

            self.sqlite_cursor.execute(
                "UPDATE projects SET invoice_number = ? WHERE id = ?",
                (existing, project_row_id),
            )
            self.sqlite_conn.commit()

            safe_print(
                f"INFO: [Repo] تم تثبيت رقم الفاتورة: {canonical_project_name} -> {existing}"
            )
            return str(existing)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل إنشاء رقم الفاتورة: {e}")
            return ""

    def restore_all_invoice_numbers(self):
        """
        ✅ استعادة كل أرقام الفواتير من جدول invoice_numbers إلى جدول projects
        يُستدعى بعد كل sync للتأكد من عدم فقدان الأرقام
        """
        try:
            self.sqlite_cursor.execute(
                """
                UPDATE invoice_numbers
                SET project_name = (
                    SELECT projects.name FROM projects
                    WHERE CAST(projects.id AS TEXT) = invoice_numbers.project_id
                )
                WHERE EXISTS (
                    SELECT 1 FROM projects
                    WHERE CAST(projects.id AS TEXT) = invoice_numbers.project_id
                )
                """
            )
            self.sqlite_cursor.execute(
                """
                UPDATE projects SET invoice_number = (
                    SELECT inv.invoice_number FROM invoice_numbers inv
                    WHERE inv.project_id = CAST(projects.id AS TEXT)
                )
                WHERE EXISTS (
                    SELECT 1 FROM invoice_numbers inv
                    WHERE inv.project_id = CAST(projects.id AS TEXT)
                )
                """
            )
            updated = self.sqlite_cursor.rowcount
            self.sqlite_conn.commit()

            self.sqlite_cursor.execute(
                """
                SELECT id FROM projects
                WHERE invoice_number IS NULL OR invoice_number = ''
                """
            )
            new_projects = self.sqlite_cursor.fetchall()

            for row in new_projects:
                if self.ensure_invoice_number(str(row[0])):
                    updated += 1

            safe_print(
                f"INFO: [Repo] ✅ تم استعادة أرقام الفواتير ({updated} محدث, {len(new_projects)} جديد)"
            )
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل استعادة أرقام الفواتير: {e}")
            return False

    # ==================== نظام عروض الأسعار (Quotations System) ====================

    def get_all_quotations(self) -> list[dict]:
        """جلب جميع عروض الأسعار"""
        try:
            self.sqlite_cursor.execute(
                """
                SELECT q.*, c.name as client_display_name, c.company_name
                FROM quotations q
                LEFT JOIN clients c ON q.client_id = c.id OR q.client_id = c._mongo_id
                WHERE (q.sync_status != 'deleted' OR q.sync_status IS NULL)
                  AND (q.is_deleted = 0 OR q.is_deleted IS NULL)
                ORDER BY q.created_at DESC
            """
            )
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_quotation_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب عروض الأسعار: {e}")
            return []

    def get_quotation_by_id(self, quotation_id: int) -> dict | None:
        """جلب عرض سعر بالمعرف"""
        try:
            self.sqlite_cursor.execute(
                """
                SELECT q.*, c.name as client_display_name, c.company_name
                FROM quotations q
                LEFT JOIN clients c ON q.client_id = c.id OR q.client_id = c._mongo_id
                WHERE q.id = ?
                  AND (q.sync_status != 'deleted' OR q.sync_status IS NULL)
                  AND (q.is_deleted = 0 OR q.is_deleted IS NULL)
            """,
                (quotation_id,),
            )
            row = self.sqlite_cursor.fetchone()
            return self._row_to_quotation_dict(row) if row else None
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب عرض السعر: {e}")
            return None

    def get_quotations_by_client(self, client_id: str) -> list[dict]:
        """جلب عروض أسعار عميل"""
        try:
            client_references = self._client_reference_values(client_id)
            if not client_references:
                return []
            normalized_references = {
                self._normalized_key(reference)
                for reference in client_references
                if self._normalized_key(reference)
            }

            self.sqlite_cursor.execute(
                """
                SELECT * FROM quotations
                WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                  AND (is_deleted = 0 OR is_deleted IS NULL)
                ORDER BY created_at DESC
            """
            )
            rows = self.sqlite_cursor.fetchall()
            matching_rows = [
                row
                for row in rows
                if self._normalized_key(row["client_id"]) in normalized_references
            ]
            return [self._row_to_quotation_dict(row) for row in matching_rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب عروض العميل: {e}")
            return []

    def get_quotations_by_status(self, status: str) -> list[dict]:
        """جلب عروض الأسعار حسب الحالة"""
        try:
            self.sqlite_cursor.execute(
                """
                SELECT q.*, c.name as client_display_name, c.company_name
                FROM quotations q
                LEFT JOIN clients c ON q.client_id = c.id OR q.client_id = c._mongo_id
                WHERE q.status = ?
                  AND (q.sync_status != 'deleted' OR q.sync_status IS NULL)
                  AND (q.is_deleted = 0 OR q.is_deleted IS NULL)
                ORDER BY q.created_at DESC
            """,
                (status,),
            )
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_quotation_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب العروض: {e}")
            return []

    def create_quotation(self, data: dict) -> dict | None:
        """إنشاء عرض سعر جديد"""
        try:
            now = datetime.now().isoformat()
            items_json = json.dumps(data.get("items", []), ensure_ascii=False)
            local_client_id = self._normalize_local_client_reference(data.get("client_id"))
            if not local_client_id:
                raise ValueError("العميل المحدد غير موجود محلياً")

            self.sqlite_cursor.execute(
                """
                INSERT INTO quotations (
                    quotation_number, client_id, client_name, issue_date, valid_until,
                    title, description, scope_of_work, items,
                    subtotal, discount_rate, discount_amount, tax_rate, tax_amount, total_amount,
                    currency, status, terms_and_conditions, payment_terms, delivery_time,
                    warranty, notes, internal_notes,
                    created_at, last_modified, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new_offline')
            """,
                (
                    data.get("quotation_number"),
                    local_client_id,
                    data.get("client_name"),
                    data.get("issue_date"),
                    data.get("valid_until"),
                    data.get("title"),
                    data.get("description"),
                    data.get("scope_of_work"),
                    items_json,
                    data.get("subtotal", 0),
                    data.get("discount_rate", 0),
                    data.get("discount_amount", 0),
                    data.get("tax_rate", 0),
                    data.get("tax_amount", 0),
                    data.get("total_amount", 0),
                    data.get("currency", "EGP"),
                    data.get("status", "مسودة"),
                    data.get("terms_and_conditions"),
                    data.get("payment_terms"),
                    data.get("delivery_time"),
                    data.get("warranty"),
                    data.get("notes"),
                    data.get("internal_notes"),
                    now,
                    now,
                ),
            )
            self.sqlite_conn.commit()
            quotation_id = self.sqlite_cursor.lastrowid
            safe_print(f"SUCCESS: [Repo] ✅ تم إنشاء عرض سعر: {data.get('quotation_number')}")
            return self.get_quotation_by_id(quotation_id)
        except ValueError:
            raise
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل إنشاء عرض السعر: {e}")
            return None

    def update_quotation(self, quotation_id: int, data: dict) -> dict | None:
        """تحديث عرض سعر"""
        try:
            now = datetime.now().isoformat()
            items_json = json.dumps(data.get("items", []), ensure_ascii=False)
            local_client_id = self._normalize_local_client_reference(data.get("client_id"))
            if not local_client_id:
                raise ValueError("العميل المحدد غير موجود محلياً")

            self.sqlite_cursor.execute(
                """
                UPDATE quotations SET
                    client_id = ?, client_name = ?, issue_date = ?, valid_until = ?,
                    title = ?, description = ?, scope_of_work = ?, items = ?,
                    subtotal = ?, discount_rate = ?, discount_amount = ?,
                    tax_rate = ?, tax_amount = ?, total_amount = ?,
                    currency = ?, status = ?, terms_and_conditions = ?,
                    payment_terms = ?, delivery_time = ?, warranty = ?,
                    notes = ?, internal_notes = ?,
                    last_modified = ?, sync_status = 'modified_offline', dirty_flag = 1
                WHERE id = ?
            """,
                (
                    local_client_id,
                    data.get("client_name"),
                    data.get("issue_date"),
                    data.get("valid_until"),
                    data.get("title"),
                    data.get("description"),
                    data.get("scope_of_work"),
                    items_json,
                    data.get("subtotal", 0),
                    data.get("discount_rate", 0),
                    data.get("discount_amount", 0),
                    data.get("tax_rate", 0),
                    data.get("tax_amount", 0),
                    data.get("total_amount", 0),
                    data.get("currency", "EGP"),
                    data.get("status"),
                    data.get("terms_and_conditions"),
                    data.get("payment_terms"),
                    data.get("delivery_time"),
                    data.get("warranty"),
                    data.get("notes"),
                    data.get("internal_notes"),
                    now,
                    quotation_id,
                ),
            )
            self.sqlite_conn.commit()
            safe_print(f"SUCCESS: [Repo] ✅ تم تحديث عرض السعر: {quotation_id}")
            return self.get_quotation_by_id(quotation_id)
        except ValueError:
            raise
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث عرض السعر: {e}")
            return None

    def update_quotation_status(
        self, quotation_id: int, status: str, extra_data: dict = None
    ) -> bool:
        """تحديث حالة عرض السعر"""
        try:
            now = datetime.now().isoformat()
            extra = extra_data or {}

            # تحديث الحقول الإضافية حسب الحالة
            sent_date = extra.get("sent_date") or (now if status == "مرسل" else None)
            viewed_date = extra.get("viewed_date") or (now if status == "تم الاطلاع" else None)
            response_date = extra.get("response_date") or (
                now if status in ["مقبول", "مرفوض"] else None
            )

            self.sqlite_cursor.execute(
                """
                UPDATE quotations SET
                    status = ?,
                    sent_date = COALESCE(?, sent_date),
                    viewed_date = COALESCE(?, viewed_date),
                    response_date = COALESCE(?, response_date),
                    last_modified = ?, sync_status = 'modified_offline', dirty_flag = 1
                WHERE id = ?
            """,
                (status, sent_date, viewed_date, response_date, now, quotation_id),
            )
            self.sqlite_conn.commit()
            safe_print(f"SUCCESS: [Repo] ✅ تم تحديث حالة العرض: {status}")
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث حالة العرض: {e}")
            return False

    def convert_quotation_to_project(self, quotation_id: int, project_id: str) -> bool:
        """تحويل عرض سعر إلى مشروع"""
        try:
            now = datetime.now().isoformat()
            normalized_project_id = str(project_id or "").strip()
            quotation_client_id = ""
            self.sqlite_cursor.execute(
                "SELECT client_id FROM quotations WHERE id = ?",
                (quotation_id,),
            )
            row = self.sqlite_cursor.fetchone()
            if row:
                quotation_client_id = str(row["client_id"] or "").strip()

            resolved_project = self._resolve_project_target_row(
                normalized_project_id,
                quotation_client_id,
            )
            if resolved_project:
                normalized_project_id = self._stable_project_reference(
                    resolved_project,
                    normalized_project_id,
                )

            self.sqlite_cursor.execute(
                """
                UPDATE quotations SET
                    status = 'تم التحويل لمشروع',
                    converted_to_project_id = ?,
                    conversion_date = ?,
                    last_modified = ?, sync_status = 'modified_offline', dirty_flag = 1
                WHERE id = ?
            """,
                (normalized_project_id, now, now, quotation_id),
            )
            self.sqlite_conn.commit()
            safe_print(f"SUCCESS: [Repo] ✅ تم تحويل العرض لمشروع: {normalized_project_id}")
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحويل العرض: {e}")
            return False

    def delete_quotation(self, quotation_id: int) -> bool:
        """حذف عرض سعر"""
        try:
            now = datetime.now().isoformat()
            self.sqlite_cursor.execute(
                """
                UPDATE quotations
                SET sync_status = 'deleted', last_modified = ?, is_deleted = 1, dirty_flag = 1
                WHERE id = ?
                """,
                (now, quotation_id),
            )
            self.sqlite_conn.commit()
            safe_print(f"SUCCESS: [Repo] ✅ تم حذف عرض السعر: {quotation_id}")
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف عرض السعر: {e}")
            return False

    def generate_quotation_number(self) -> str:
        """توليد رقم عرض سعر جديد"""
        try:
            year = datetime.now().strftime("%Y")
            self.sqlite_cursor.execute(
                """
                SELECT COUNT(*) FROM quotations WHERE quotation_number LIKE ?
            """,
                (f"QT-{year}-%",),
            )
            count = self.sqlite_cursor.fetchone()[0]
            return f"QT-{year}-{count + 1:04d}"
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل توليد رقم العرض: {e}")
            return f"QT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def get_quotation_statistics(self) -> dict:
        """جلب إحصائيات عروض الأسعار"""
        try:
            stats = {}

            # إجمالي العروض
            self.sqlite_cursor.execute(
                """
                SELECT COUNT(*) FROM quotations
                WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                  AND (is_deleted = 0 OR is_deleted IS NULL)
                """
            )
            stats["total"] = self.sqlite_cursor.fetchone()[0]

            # حسب الحالة
            self.sqlite_cursor.execute(
                """
                SELECT status, COUNT(*), COALESCE(SUM(total_amount), 0)
                FROM quotations
                WHERE (sync_status != 'deleted' OR sync_status IS NULL)
                  AND (is_deleted = 0 OR is_deleted IS NULL)
                GROUP BY status
            """
            )
            stats["by_status"] = {
                row[0]: {"count": row[1], "amount": row[2]} for row in self.sqlite_cursor.fetchall()
            }

            # العروض المقبولة هذا الشهر
            month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
            self.sqlite_cursor.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM quotations
                WHERE status = 'مقبول'
                  AND response_date >= ?
                  AND (sync_status != 'deleted' OR sync_status IS NULL)
                  AND (is_deleted = 0 OR is_deleted IS NULL)
            """,
                (month_start,),
            )
            row = self.sqlite_cursor.fetchone()
            stats["accepted_this_month"] = {"count": row[0], "amount": row[1]}

            # معدل القبول
            self.sqlite_cursor.execute(
                """
                SELECT COUNT(*) FROM quotations
                WHERE status IN ('مقبول', 'مرفوض')
                  AND (sync_status != 'deleted' OR sync_status IS NULL)
                  AND (is_deleted = 0 OR is_deleted IS NULL)
                """
            )
            responded = self.sqlite_cursor.fetchone()[0]
            self.sqlite_cursor.execute(
                """
                SELECT COUNT(*) FROM quotations
                WHERE status = 'مقبول'
                  AND (sync_status != 'deleted' OR sync_status IS NULL)
                  AND (is_deleted = 0 OR is_deleted IS NULL)
                """
            )
            accepted = self.sqlite_cursor.fetchone()[0]
            stats["acceptance_rate"] = (accepted / responded * 100) if responded > 0 else 0

            return stats
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب إحصائيات العروض: {e}")
            return {}

    def _row_to_quotation_dict(self, row) -> dict:
        """تحويل صف عرض السعر إلى dict"""
        items = []
        try:
            items_str = row["items"]
            if items_str:
                items = json.loads(items_str)
        except (json.JSONDecodeError, TypeError):
            pass

        client_id = row["client_id"]
        if client_id:
            client_row = self._resolve_local_client_row(client_id)
            if client_row:
                client_id = self._stable_client_reference(client_row, client_id)

        converted_project_id = row["converted_to_project_id"]
        if converted_project_id:
            resolved_project = self._resolve_project_target_row(
                converted_project_id,
                row["client_id"],
            )
            if resolved_project:
                converted_project_id = self._stable_project_reference(
                    resolved_project,
                    converted_project_id,
                )

        result = {
            "id": row["id"],
            "_mongo_id": row["_mongo_id"],
            "quotation_number": row["quotation_number"],
            "client_id": client_id,
            "client_name": row["client_name"],
            "issue_date": row["issue_date"],
            "valid_until": row["valid_until"],
            "title": row["title"],
            "description": row["description"],
            "scope_of_work": row["scope_of_work"],
            "items": items,
            "subtotal": row["subtotal"] or 0,
            "discount_rate": row["discount_rate"] or 0,
            "discount_amount": row["discount_amount"] or 0,
            "tax_rate": row["tax_rate"] or 0,
            "tax_amount": row["tax_amount"] or 0,
            "total_amount": row["total_amount"] or 0,
            "currency": row["currency"],
            "status": row["status"],
            "terms_and_conditions": row["terms_and_conditions"],
            "payment_terms": row["payment_terms"],
            "delivery_time": row["delivery_time"],
            "warranty": row["warranty"],
            "notes": row["notes"],
            "internal_notes": row["internal_notes"],
            "converted_to_project_id": converted_project_id,
            "conversion_date": row["conversion_date"],
            "sent_date": row["sent_date"],
            "viewed_date": row["viewed_date"],
            "response_date": row["response_date"],
            "created_at": row["created_at"],
            "last_modified": row["last_modified"],
            "sync_status": row["sync_status"],
        }

        # إضافة اسم العميل من الجدول المرتبط
        if "client_display_name" in row.keys():
            result["client_display_name"] = row["client_display_name"]
        if "company_name" in row.keys():
            result["company_name"] = row["company_name"]

        return result

    # ==================== نظام الموارد البشرية (HR System) ====================

    # --- الموظفين (Employees) ---
    def get_all_employees(self) -> list[dict]:
        """جلب جميع الموظفين"""
        try:
            self.sqlite_cursor.execute("SELECT * FROM employees ORDER BY name")
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_employee_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الموظفين: {e}")
            return []

    def get_employee_by_id(self, employee_id: int) -> dict | None:
        """جلب موظف بالمعرف"""
        try:
            self.sqlite_cursor.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
            row = self.sqlite_cursor.fetchone()
            return self._row_to_employee_dict(row) if row else None
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الموظف: {e}")
            return None

    def get_active_employees(self) -> list[dict]:
        """جلب الموظفين النشطين فقط"""
        try:
            self.sqlite_cursor.execute("SELECT * FROM employees WHERE status = 'نشط' ORDER BY name")
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_employee_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الموظفين النشطين: {e}")
            return []

    def create_employee(self, data: dict) -> dict | None:
        """إنشاء موظف جديد"""
        try:
            now = datetime.now().isoformat()
            self.sqlite_cursor.execute(
                """
                INSERT INTO employees (
                    employee_id, name, national_id, email, phone, department, position,
                    hire_date, salary, status, address, bank_account, notes,
                    created_at, last_modified, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new_offline')
            """,
                (
                    data.get("employee_id"),
                    data.get("name"),
                    data.get("national_id"),
                    data.get("email"),
                    data.get("phone"),
                    data.get("department"),
                    data.get("position"),
                    data.get("hire_date"),
                    data.get("salary", 0),
                    data.get("status", "نشط"),
                    data.get("address"),
                    data.get("bank_account"),
                    data.get("notes"),
                    now,
                    now,
                ),
            )
            self.sqlite_conn.commit()
            employee_id = self.sqlite_cursor.lastrowid
            safe_print(f"SUCCESS: [Repo] ✅ تم إنشاء موظف: {data.get('name')}")
            return self.get_employee_by_id(employee_id)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل إنشاء الموظف: {e}")
            return None

    def update_employee(self, employee_id: int, data: dict) -> dict | None:
        """تحديث بيانات موظف"""
        try:
            now = datetime.now().isoformat()
            self.sqlite_cursor.execute(
                """
                UPDATE employees SET
                    employee_id = ?, name = ?, national_id = ?, email = ?, phone = ?,
                    department = ?, position = ?, hire_date = ?, salary = ?, status = ?,
                    address = ?, bank_account = ?, notes = ?,
                    last_modified = ?, sync_status = 'modified_offline'
                WHERE id = ?
            """,
                (
                    data.get("employee_id"),
                    data.get("name"),
                    data.get("national_id"),
                    data.get("email"),
                    data.get("phone"),
                    data.get("department"),
                    data.get("position"),
                    data.get("hire_date"),
                    data.get("salary", 0),
                    data.get("status", "نشط"),
                    data.get("address"),
                    data.get("bank_account"),
                    data.get("notes"),
                    now,
                    employee_id,
                ),
            )
            self.sqlite_conn.commit()
            safe_print(f"SUCCESS: [Repo] ✅ تم تحديث موظف: {data.get('name')}")
            return self.get_employee_by_id(employee_id)
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث الموظف: {e}")
            return None

    def delete_employee(self, employee_id: int) -> bool:
        """حذف موظف"""
        try:
            self.sqlite_cursor.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
            self.sqlite_conn.commit()
            safe_print(f"SUCCESS: [Repo] ✅ تم حذف موظف: {employee_id}")
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حذف الموظف: {e}")
            return False

    def _row_to_employee_dict(self, row) -> dict:
        """تحويل صف قاعدة البيانات إلى dict"""
        return {
            "id": row["id"],
            "_mongo_id": row["_mongo_id"],
            "employee_id": row["employee_id"],
            "name": row["name"],
            "national_id": row["national_id"],
            "email": row["email"],
            "phone": row["phone"],
            "department": row["department"],
            "position": row["position"],
            "hire_date": row["hire_date"],
            "salary": row["salary"] or 0,
            "status": row["status"],
            "address": row["address"],
            "bank_account": row["bank_account"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "last_modified": row["last_modified"],
            "sync_status": row["sync_status"],
        }

    # --- الحضور والانصراف (Attendance) ---
    def get_employee_attendance(self, employee_id: int, month: str = None) -> list[dict]:
        """جلب سجل حضور موظف"""
        try:
            if month:
                self.sqlite_cursor.execute(
                    """
                    SELECT * FROM employee_attendance
                    WHERE employee_id = ? AND date LIKE ?
                    ORDER BY date DESC
                """,
                    (employee_id, f"{month}%"),
                )
            else:
                self.sqlite_cursor.execute(
                    """
                    SELECT * FROM employee_attendance
                    WHERE employee_id = ?
                    ORDER BY date DESC LIMIT 31
                """,
                    (employee_id,),
                )
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_attendance_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب سجل الحضور: {e}")
            return []

    def get_all_attendance_for_date(self, date: str) -> list[dict]:
        """جلب حضور جميع الموظفين ليوم معين"""
        try:
            self.sqlite_cursor.execute(
                """
                SELECT a.*, e.name as employee_name, e.department
                FROM employee_attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE date(a.date) = date(?)
                ORDER BY e.name
            """,
                (date,),
            )
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_attendance_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب حضور اليوم: {e}")
            return []

    def record_attendance(self, data: dict) -> dict | None:
        """تسجيل حضور موظف"""
        try:
            now = datetime.now().isoformat()
            # تحقق من وجود سجل لنفس اليوم
            self.sqlite_cursor.execute(
                """
                SELECT id FROM employee_attendance
                WHERE employee_id = ? AND date(date) = date(?)
            """,
                (data.get("employee_id"), data.get("date")),
            )
            existing = self.sqlite_cursor.fetchone()

            if existing:
                # تحديث السجل الموجود
                self.sqlite_cursor.execute(
                    """
                    UPDATE employee_attendance SET
                        check_in_time = COALESCE(?, check_in_time),
                        check_out_time = COALESCE(?, check_out_time),
                        work_hours = ?, overtime_hours = ?, status = ?, notes = ?,
                        last_modified = ?, sync_status = 'modified_offline'
                    WHERE id = ?
                """,
                    (
                        data.get("check_in_time"),
                        data.get("check_out_time"),
                        data.get("work_hours", 0),
                        data.get("overtime_hours", 0),
                        data.get("status", "حاضر"),
                        data.get("notes"),
                        now,
                        existing["id"],
                    ),
                )
            else:
                # إنشاء سجل جديد
                self.sqlite_cursor.execute(
                    """
                    INSERT INTO employee_attendance (
                        employee_id, date, check_in_time, check_out_time,
                        work_hours, overtime_hours, status, notes,
                        created_at, last_modified, sync_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new_offline')
                """,
                    (
                        data.get("employee_id"),
                        data.get("date"),
                        data.get("check_in_time"),
                        data.get("check_out_time"),
                        data.get("work_hours", 0),
                        data.get("overtime_hours", 0),
                        data.get("status", "حاضر"),
                        data.get("notes"),
                        now,
                        now,
                    ),
                )
            self.sqlite_conn.commit()
            safe_print("SUCCESS: [Repo] ✅ تم تسجيل الحضور")
            return data
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تسجيل الحضور: {e}")
            return None

    def _row_to_attendance_dict(self, row) -> dict:
        """تحويل صف الحضور إلى dict"""
        result = {
            "id": row["id"],
            "employee_id": row["employee_id"],
            "date": row["date"],
            "check_in_time": row["check_in_time"],
            "check_out_time": row["check_out_time"],
            "work_hours": row["work_hours"] or 0,
            "overtime_hours": row["overtime_hours"] or 0,
            "status": row["status"],
            "notes": row["notes"],
        }
        # إضافة اسم الموظف إذا كان موجوداً
        if "employee_name" in row.keys():
            result["employee_name"] = row["employee_name"]
        if "department" in row.keys():
            result["department"] = row["department"]
        return result

    # --- الإجازات (Leaves) ---
    def get_employee_leaves(self, employee_id: int = None, status: str = None) -> list[dict]:
        """جلب طلبات الإجازات"""
        try:
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

            self.sqlite_cursor.execute(query, params)
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_leave_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب الإجازات: {e}")
            return []

    def create_leave_request(self, data: dict) -> dict | None:
        """إنشاء طلب إجازة"""
        try:
            now = datetime.now().isoformat()
            self.sqlite_cursor.execute(
                """
                INSERT INTO employee_leaves (
                    employee_id, leave_type, start_date, end_date, days_count,
                    reason, status, notes, created_at, last_modified, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, 'معلق', ?, ?, ?, 'new_offline')
            """,
                (
                    data.get("employee_id"),
                    data.get("leave_type", "سنوية"),
                    data.get("start_date"),
                    data.get("end_date"),
                    data.get("days_count", 1),
                    data.get("reason"),
                    data.get("notes"),
                    now,
                    now,
                ),
            )
            self.sqlite_conn.commit()
            leave_id = self.sqlite_cursor.lastrowid
            safe_print("SUCCESS: [Repo] ✅ تم إنشاء طلب إجازة")
            return {"id": leave_id, **data}
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل إنشاء طلب الإجازة: {e}")
            return None

    def update_leave_status(self, leave_id: int, status: str, approved_by: str = None) -> bool:
        """تحديث حالة طلب إجازة"""
        try:
            now = datetime.now().isoformat()
            self.sqlite_cursor.execute(
                """
                UPDATE employee_leaves SET
                    status = ?, approved_by = ?, approval_date = ?,
                    last_modified = ?, sync_status = 'modified_offline'
                WHERE id = ?
            """,
                (
                    status,
                    approved_by,
                    now if status in ["موافق عليه", "مرفوض"] else None,
                    now,
                    leave_id,
                ),
            )
            self.sqlite_conn.commit()
            safe_print(f"SUCCESS: [Repo] ✅ تم تحديث حالة الإجازة: {status}")
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث حالة الإجازة: {e}")
            return False

    def _row_to_leave_dict(self, row) -> dict:
        """تحويل صف الإجازة إلى dict"""
        result = {
            "id": row["id"],
            "employee_id": row["employee_id"],
            "leave_type": row["leave_type"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "days_count": row["days_count"],
            "reason": row["reason"],
            "status": row["status"],
            "approved_by": row["approved_by"],
            "approval_date": row["approval_date"],
            "notes": row["notes"],
        }
        if "employee_name" in row.keys():
            result["employee_name"] = row["employee_name"]
        if "department" in row.keys():
            result["department"] = row["department"]
        return result

    # --- السلف (Loans) ---
    def get_employee_loans(self, employee_id: int = None, status: str = None) -> list[dict]:
        """جلب سلف الموظفين"""
        try:
            query = """
                SELECT l.*, e.name as employee_name, e.department
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

            self.sqlite_cursor.execute(query, params)
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_loan_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب السلف: {e}")
            return []

    def create_loan(self, data: dict) -> dict | None:
        """إنشاء سلفة جديدة"""
        try:
            now = datetime.now().isoformat()
            amount = data.get("amount", 0)
            self.sqlite_cursor.execute(
                """
                INSERT INTO employee_loans (
                    employee_id, loan_type, amount, remaining_amount, monthly_deduction,
                    start_date, end_date, status, reason, approved_by, notes,
                    created_at, last_modified, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'نشط', ?, ?, ?, ?, ?, 'new_offline')
            """,
                (
                    data.get("employee_id"),
                    data.get("loan_type", "سلفة"),
                    amount,
                    amount,  # remaining = amount initially
                    data.get("monthly_deduction", 0),
                    data.get("start_date"),
                    data.get("end_date"),
                    data.get("reason"),
                    data.get("approved_by"),
                    data.get("notes"),
                    now,
                    now,
                ),
            )
            self.sqlite_conn.commit()
            loan_id = self.sqlite_cursor.lastrowid
            safe_print(f"SUCCESS: [Repo] ✅ تم إنشاء سلفة: {amount}")
            return {"id": loan_id, **data}
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل إنشاء السلفة: {e}")
            return None

    def update_loan(self, loan_id: int, data: dict) -> bool:
        """تحديث سلفة"""
        try:
            now = datetime.now().isoformat()
            self.sqlite_cursor.execute(
                """
                UPDATE employee_loans SET
                    remaining_amount = ?, monthly_deduction = ?, status = ?, notes = ?,
                    last_modified = ?, sync_status = 'modified_offline'
                WHERE id = ?
            """,
                (
                    data.get("remaining_amount"),
                    data.get("monthly_deduction"),
                    data.get("status"),
                    data.get("notes"),
                    now,
                    loan_id,
                ),
            )
            self.sqlite_conn.commit()
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث السلفة: {e}")
            return False

    def _row_to_loan_dict(self, row) -> dict:
        """تحويل صف السلفة إلى dict"""
        result = {
            "id": row["id"],
            "employee_id": row["employee_id"],
            "loan_type": row["loan_type"],
            "amount": row["amount"] or 0,
            "remaining_amount": row["remaining_amount"] or 0,
            "monthly_deduction": row["monthly_deduction"] or 0,
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "status": row["status"],
            "reason": row["reason"],
            "approved_by": row["approved_by"],
            "notes": row["notes"],
        }
        if "employee_name" in row.keys():
            result["employee_name"] = row["employee_name"]
        if "department" in row.keys():
            result["department"] = row["department"]
        return result

    # --- المرتبات (Salaries) ---
    def get_employee_salaries(self, employee_id: int = None, month: str = None) -> list[dict]:
        """جلب مرتبات الموظفين"""
        try:
            query = """
                SELECT s.*, e.name as employee_name, e.department, e.position
                FROM employee_salaries s
                JOIN employees e ON s.employee_id = e.id
                WHERE 1=1
            """
            params = []
            if employee_id:
                query += " AND s.employee_id = ?"
                params.append(employee_id)
            if month:
                query += " AND s.month = ?"
                params.append(month)
            query += " ORDER BY s.month DESC, e.name"

            self.sqlite_cursor.execute(query, params)
            rows = self.sqlite_cursor.fetchall()
            return [self._row_to_salary_dict(row) for row in rows]
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب المرتبات: {e}")
            return []

    def create_or_update_salary(self, data: dict) -> dict | None:
        """إنشاء أو تحديث راتب شهري"""
        try:
            now = datetime.now().isoformat()
            employee_id = data.get("employee_id")
            month = data.get("month")

            # تحقق من وجود راتب لنفس الشهر
            self.sqlite_cursor.execute(
                """
                SELECT id FROM employee_salaries WHERE employee_id = ? AND month = ?
            """,
                (employee_id, month),
            )
            existing = self.sqlite_cursor.fetchone()

            # حساب الإجماليات
            basic = data.get("basic_salary", 0)
            allowances = data.get("allowances", 0)
            bonuses = data.get("bonuses", 0)
            overtime = data.get("overtime_amount", 0)
            gross = basic + allowances + bonuses + overtime

            loan_ded = data.get("loan_deductions", 0)
            insurance = data.get("insurance_deduction", 0)
            tax = data.get("tax_deduction", 0)
            other_ded = data.get("other_deductions", 0)
            total_deductions = loan_ded + insurance + tax + other_ded

            net = gross - total_deductions

            if existing:
                self.sqlite_cursor.execute(
                    """
                    UPDATE employee_salaries SET
                        basic_salary = ?, allowances = ?, bonuses = ?,
                        overtime_hours = ?, overtime_rate = ?, overtime_amount = ?,
                        loan_deductions = ?, insurance_deduction = ?, tax_deduction = ?,
                        other_deductions = ?, gross_salary = ?, net_salary = ?,
                        payment_status = ?, payment_date = ?, payment_method = ?, notes = ?,
                        last_modified = ?, sync_status = 'modified_offline'
                    WHERE id = ?
                """,
                    (
                        basic,
                        allowances,
                        bonuses,
                        data.get("overtime_hours", 0),
                        data.get("overtime_rate", 0),
                        overtime,
                        loan_ded,
                        insurance,
                        tax,
                        other_ded,
                        gross,
                        net,
                        data.get("payment_status", "معلق"),
                        data.get("payment_date"),
                        data.get("payment_method"),
                        data.get("notes"),
                        now,
                        existing["id"],
                    ),
                )
            else:
                self.sqlite_cursor.execute(
                    """
                    INSERT INTO employee_salaries (
                        employee_id, month, basic_salary, allowances, bonuses,
                        overtime_hours, overtime_rate, overtime_amount,
                        loan_deductions, insurance_deduction, tax_deduction, other_deductions,
                        gross_salary, net_salary, payment_status, payment_date, payment_method, notes,
                        created_at, last_modified, sync_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new_offline')
                """,
                    (
                        employee_id,
                        month,
                        basic,
                        allowances,
                        bonuses,
                        data.get("overtime_hours", 0),
                        data.get("overtime_rate", 0),
                        overtime,
                        loan_ded,
                        insurance,
                        tax,
                        other_ded,
                        gross,
                        net,
                        data.get("payment_status", "معلق"),
                        data.get("payment_date"),
                        data.get("payment_method"),
                        data.get("notes"),
                        now,
                        now,
                    ),
                )
            self.sqlite_conn.commit()
            safe_print(f"SUCCESS: [Repo] ✅ تم حفظ راتب شهر {month}")
            return data
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل حفظ الراتب: {e}")
            return None

    def update_salary_status(
        self, salary_id: int, status: str, payment_date: str = None, payment_method: str = None
    ) -> bool:
        """تحديث حالة الراتب"""
        try:
            now = datetime.now().isoformat()
            self.sqlite_cursor.execute(
                """
                UPDATE employee_salaries SET
                    payment_status = ?, payment_date = ?, payment_method = ?,
                    last_modified = ?, sync_status = 'modified_offline'
                WHERE id = ?
            """,
                (status, payment_date, payment_method, now, salary_id),
            )
            self.sqlite_conn.commit()
            return True
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل تحديث حالة الراتب: {e}")
            return False

    def _row_to_salary_dict(self, row) -> dict:
        """تحويل صف الراتب إلى dict"""
        result = {
            "id": row["id"],
            "employee_id": row["employee_id"],
            "month": row["month"],
            "basic_salary": row["basic_salary"] or 0,
            "allowances": row["allowances"] or 0,
            "bonuses": row["bonuses"] or 0,
            "overtime_hours": row["overtime_hours"] or 0,
            "overtime_rate": row["overtime_rate"] or 0,
            "overtime_amount": row["overtime_amount"] or 0,
            "loan_deductions": row["loan_deductions"] or 0,
            "insurance_deduction": row["insurance_deduction"] or 0,
            "tax_deduction": row["tax_deduction"] or 0,
            "other_deductions": row["other_deductions"] or 0,
            "gross_salary": row["gross_salary"] or 0,
            "net_salary": row["net_salary"] or 0,
            "payment_status": row["payment_status"],
            "payment_date": row["payment_date"],
            "payment_method": row["payment_method"],
            "notes": row["notes"],
        }
        if "employee_name" in row.keys():
            result["employee_name"] = row["employee_name"]
        if "department" in row.keys():
            result["department"] = row["department"]
        if "position" in row.keys():
            result["position"] = row["position"]
        return result

    # --- إحصائيات HR ---
    def get_hr_statistics(self) -> dict:
        """جلب إحصائيات الموارد البشرية"""
        try:
            stats = {}

            # عدد الموظفين
            self.sqlite_cursor.execute("SELECT COUNT(*) FROM employees")
            stats["total_employees"] = self.sqlite_cursor.fetchone()[0]

            self.sqlite_cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'نشط'")
            stats["active_employees"] = self.sqlite_cursor.fetchone()[0]

            # إجمالي الرواتب
            self.sqlite_cursor.execute(
                "SELECT COALESCE(SUM(salary), 0) FROM employees WHERE status = 'نشط'"
            )
            stats["total_salaries"] = self.sqlite_cursor.fetchone()[0]

            # السلف النشطة
            self.sqlite_cursor.execute(
                "SELECT COUNT(*), COALESCE(SUM(remaining_amount), 0) FROM employee_loans WHERE status = 'نشط'"
            )
            row = self.sqlite_cursor.fetchone()
            stats["active_loans_count"] = row[0]
            stats["active_loans_amount"] = row[1]

            # طلبات الإجازات المعلقة
            self.sqlite_cursor.execute("SELECT COUNT(*) FROM employee_leaves WHERE status = 'معلق'")
            stats["pending_leaves"] = self.sqlite_cursor.fetchone()[0]

            # الموظفين حسب القسم
            self.sqlite_cursor.execute(
                """
                SELECT department, COUNT(*) FROM employees
                WHERE status = 'نشط' AND department IS NOT NULL
                GROUP BY department
            """
            )
            stats["by_department"] = {row[0]: row[1] for row in self.sqlite_cursor.fetchall()}

            return stats
        except Exception as e:
            safe_print(f"ERROR: [Repo] فشل جلب إحصائيات HR: {e}")
            return {}


# --- كود للاختبار (اختياري) ---
if __name__ == "__main__":
    safe_print("--- بدء اختبار الـ Repository ---")
    repo = Repository()
    safe_print(
        f"حالة الاتصال: {'أونلاين' if repo.is_online() is not None and repo.is_online() else 'أوفلاين'}"
    )
    safe_print("--- انتهاء الاختبار ---")
