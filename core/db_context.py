# الملف: core/db_context.py
"""
🔒 مدير سياق قاعدة البيانات (Database Context Manager)
يوفر إدارة آمنة للـ cursors والـ transactions

المميزات:
- إغلاق تلقائي للـ cursors
- معالجة آمنة للـ transactions (commit/rollback)
- Thread-safe operations
- حماية من Memory Leaks
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from core.logger import get_logger

if TYPE_CHECKING:
    from core.repository import Repository

logger = get_logger(__name__)


class DatabaseContextManager:
    """
    مدير سياق قاعدة البيانات - يضمن إغلاق الـ cursors دائماً

    الاستخدام:
        with db_context.cursor() as cursor:
            cursor.execute("SELECT * FROM clients")
            results = cursor.fetchall()
        # الـ cursor يُغلق تلقائياً هنا

        with db_context.transaction() as cursor:
            cursor.execute("INSERT INTO clients ...")
            cursor.execute("UPDATE accounts ...")
        # يتم commit تلقائياً، أو rollback في حالة الخطأ
    """

    def __init__(self, repository: Repository):
        self.repo = repository
        self._local = threading.local()
        self._lock = threading.RLock()
        logger.debug("✅ تم تهيئة DatabaseContextManager")

    @contextmanager
    def cursor(self, row_factory: bool = True) -> Generator[sqlite3.Cursor, None, None]:
        """
        الحصول على cursor مع إغلاق تلقائي

        Args:
            row_factory: تفعيل sqlite3.Row للوصول بالاسم

        Yields:
            sqlite3.Cursor: cursor جاهز للاستخدام

        Example:
            with db_context.cursor() as cursor:
                cursor.execute("SELECT * FROM clients WHERE status = ?", ('نشط',))
                for row in cursor.fetchall():
                    print(row['name'])
        """
        cursor = None
        try:
            with self._lock:
                cursor = self.repo.sqlite_conn.cursor()
                if row_factory:
                    cursor.row_factory = sqlite3.Row
            yield cursor
        except Exception as e:
            logger.exception("❌ خطأ في cursor: %s", e)
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception as close_error:
                    logger.debug("تحذير عند إغلاق cursor: %s", close_error)

    @contextmanager
    def transaction(self, row_factory: bool = True) -> Generator[sqlite3.Cursor, None, None]:
        """
        تنفيذ transaction مع commit/rollback تلقائي

        Args:
            row_factory: تفعيل sqlite3.Row للوصول بالاسم

        Yields:
            sqlite3.Cursor: cursor داخل transaction

        Example:
            with db_context.transaction() as cursor:
                cursor.execute("INSERT INTO clients (name) VALUES (?)", ('عميل جديد',))
                cursor.execute("UPDATE accounts SET balance = balance + 1000")
            # commit تلقائي هنا

        Note:
            في حالة حدوث exception، يتم rollback تلقائياً
        """
        cursor = None
        try:
            with self._lock:
                cursor = self.repo.sqlite_conn.cursor()
                if row_factory:
                    cursor.row_factory = sqlite3.Row

            yield cursor

            # Commit إذا نجحت كل العمليات
            self.repo.sqlite_conn.commit()

        except Exception as e:
            # Rollback في حالة الخطأ
            try:
                self.repo.sqlite_conn.rollback()
                logger.warning("⚠️ تم التراجع عن transaction بسبب: %s", e)
            except Exception as rollback_error:
                logger.exception("❌ فشل التراجع: %s", rollback_error)
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception as close_error:
                    logger.debug("تحذير عند إغلاق cursor: %s", close_error)

    @contextmanager
    def read_only(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        cursor للقراءة فقط (بدون commit)

        Yields:
            sqlite3.Cursor: cursor للقراءة
        """
        cursor = None
        try:
            with self._lock:
                cursor = self.repo.sqlite_conn.cursor()
                cursor.row_factory = sqlite3.Row
            yield cursor
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def execute_query(
        self, query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = True
    ) -> Any:
        """
        تنفيذ استعلام بسيط مع إدارة تلقائية للـ cursor

        Args:
            query: استعلام SQL
            params: معاملات الاستعلام
            fetch_one: جلب صف واحد فقط
            fetch_all: جلب كل الصفوف

        Returns:
            نتيجة الاستعلام
        """
        with self.cursor() as cursor:
            cursor.execute(query, params)
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            return None

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """
        تنفيذ عملية كتابة (INSERT/UPDATE/DELETE) مع commit

        Args:
            query: استعلام SQL
            params: معاملات الاستعلام

        Returns:
            عدد الصفوف المتأثرة
        """
        with self.transaction() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    def execute_many(self, query: str, params_list: list[tuple]) -> int:
        """
        تنفيذ عدة عمليات كتابة في transaction واحد

        Args:
            query: استعلام SQL
            params_list: قائمة المعاملات

        Returns:
            عدد الصفوف المتأثرة
        """
        with self.transaction() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount


# Singleton instance - يُنشأ عند الحاجة
_db_context: DatabaseContextManager | None = None


def get_db_context(repository: Repository) -> DatabaseContextManager:
    """
    الحصول على مدير سياق قاعدة البيانات (Singleton)

    Args:
        repository: مخزن البيانات

    Returns:
        DatabaseContextManager instance
    """
    global _db_context
    if _db_context is None:
        _db_context = DatabaseContextManager(repository)
    return _db_context


def reset_db_context():
    """إعادة تعيين مدير السياق (للاختبارات)"""
    global _db_context
    _db_context = None
