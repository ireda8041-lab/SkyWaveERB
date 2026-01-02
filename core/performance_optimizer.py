# الملف: core/performance_optimizer.py
"""
⚡ محسّن الأداء الشامل - Sky Wave ERP
================================
يوفر تحسينات شاملة للأداء:
- Connection Pooling لـ SQLite
- Query Caching ذكي
- Lazy Loading للبيانات الثقيلة
- Batch Operations للعمليات المتعددة
- Memory Management
"""

import functools
import gc
import sqlite3
import threading
import time
import weakref
from collections import OrderedDict
from collections.abc import Callable
from contextlib import contextmanager
from queue import Queue
from typing import Any

from core.logger import get_logger

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass

logger = get_logger(__name__)


class SQLiteConnectionPool:
    """
    ⚡ Connection Pool لـ SQLite
    يوفر اتصالات جاهزة للاستخدام بدلاً من إنشاء اتصال جديد كل مرة
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, db_path: str = "skywave_local.db", pool_size: int = 5):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = threading.RLock()
        self._active_connections = 0
        
        # إنشاء الاتصالات الأولية
        for _ in range(pool_size):
            conn = self._create_connection()
            self._pool.put(conn)
        
        logger.info(f"⚡ [ConnectionPool] تم إنشاء {pool_size} اتصالات")
    
    def _create_connection(self) -> sqlite3.Connection:
        """إنشاء اتصال جديد محسّن"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0,
            isolation_level=None  # Autocommit
        )
        conn.row_factory = sqlite3.Row
        
        # تحسينات SQLite للأداء
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB
        
        return conn
    
    @contextmanager
    def get_connection(self):
        """الحصول على اتصال من الـ pool"""
        conn = None
        try:
            conn = self._pool.get(timeout=5)
            self._active_connections += 1
            yield conn
        finally:
            if conn:
                self._active_connections -= 1
                self._pool.put(conn)
    
    def get_cursor(self) -> sqlite3.Cursor:
        """الحصول على cursor منفصل"""
        with self._lock:
            conn = self._create_connection()
            return conn.cursor()
    
    def close_all(self):
        """إغلاق كل الاتصالات"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Exception:
                pass
        logger.info("⚡ [ConnectionPool] تم إغلاق كل الاتصالات")


class SmartQueryCache:
    """
    ⚡ Cache ذكي للاستعلامات
    - TTL (Time To Live) لكل استعلام
    - LRU (Least Recently Used) للتنظيف
    - Invalidation ذكي حسب الجدول
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, max_size: int = 500, default_ttl: int = 60):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: dict[str, float] = {}
        self._table_keys: dict[str, set] = {}  # table -> set of cache keys
        self._lock = threading.RLock()
        
        # إحصائيات
        self._hits = 0
        self._misses = 0
        
        logger.info(f"⚡ [QueryCache] تم إنشاء cache بحجم {max_size}")
    
    def get(self, key: str) -> Any | None:
        """جلب قيمة من الـ cache"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            # التحقق من انتهاء الصلاحية
            if time.time() - self._timestamps[key] > self.default_ttl:
                self._remove_key(key)
                self._misses += 1
                return None
            
            # نقل للنهاية (الأحدث)
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
    
    def set(self, key: str, value: Any, table: str | None = None, ttl: int | None = None):
        """تخزين قيمة في الـ cache"""
        with self._lock:
            # إزالة الأقدم إذا وصلنا للحد الأقصى
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                self._remove_key(oldest_key)
            
            self._cache[key] = value
            self._timestamps[key] = time.time()
            
            # ربط المفتاح بالجدول للـ invalidation
            if table:
                if table not in self._table_keys:
                    self._table_keys[table] = set()
                self._table_keys[table].add(key)
    
    def _remove_key(self, key: str):
        """إزالة مفتاح من الـ cache"""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
        # إزالة من table_keys
        for table_keys in self._table_keys.values():
            table_keys.discard(key)
    
    def invalidate_table(self, table: str):
        """إبطال كل الـ cache المرتبط بجدول معين"""
        with self._lock:
            if table in self._table_keys:
                for key in list(self._table_keys[table]):
                    self._remove_key(key)
                self._table_keys[table].clear()
                logger.debug(f"⚡ [QueryCache] تم إبطال cache الجدول: {table}")
    
    def invalidate_all(self):
        """إبطال كل الـ cache"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._table_keys.clear()
            logger.info("⚡ [QueryCache] تم إبطال كل الـ cache")
    
    def get_stats(self) -> dict:
        """إحصائيات الـ cache"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }


class BatchProcessor:
    """
    ⚡ معالج دفعات للعمليات المتعددة
    يجمع العمليات ويُنفذها دفعة واحدة للأداء
    """
    
    def __init__(self, batch_size: int = 100, flush_interval: float = 1.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queue: list[tuple] = []
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._callbacks: list[Callable] = []
    
    def add(self, operation: str, table: str, data: dict):
        """إضافة عملية للدفعة"""
        with self._lock:
            self._queue.append((operation, table, data))
            
            # Flush إذا وصلنا للحد الأقصى أو مر الوقت
            if len(self._queue) >= self.batch_size:
                self._flush()
            elif time.time() - self._last_flush > self.flush_interval:
                self._flush()
    
    def _flush(self):
        """تنفيذ الدفعة"""
        if not self._queue:
            return
        
        batch = self._queue.copy()
        self._queue.clear()
        self._last_flush = time.time()
        
        # تنفيذ callbacks
        for callback in self._callbacks:
            try:
                callback(batch)
            except Exception as e:
                logger.error(f"⚡ [BatchProcessor] خطأ في callback: {e}")
    
    def on_flush(self, callback: Callable):
        """إضافة callback عند الـ flush"""
        self._callbacks.append(callback)
    
    def force_flush(self):
        """إجبار الـ flush"""
        with self._lock:
            self._flush()


class MemoryManager:
    """
    ⚡ مدير الذاكرة
    يراقب استخدام الذاكرة ويُنظفها عند الحاجة
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        self._weak_refs: list[weakref.ref] = []
        self._cleanup_threshold = 100 * 1024 * 1024  # 100MB
    
    def register_disposable(self, obj):
        """تسجيل كائن قابل للتنظيف"""
        self._weak_refs.append(weakref.ref(obj))
    
    def cleanup(self, force: bool = False):
        """تنظيف الذاكرة"""
        import sys
        
        # تنظيف الـ weak refs الميتة
        self._weak_refs = [ref for ref in self._weak_refs if ref() is not None]
        
        # تشغيل garbage collector
        collected = gc.collect()
        
        if collected > 0:
            logger.debug(f"⚡ [MemoryManager] تم تنظيف {collected} كائن")
        
        return collected
    
    def get_memory_usage(self) -> dict:
        """الحصول على استخدام الذاكرة"""
        import sys
        
        return {
            "gc_objects": len(gc.get_objects()),
            "gc_garbage": len(gc.garbage),
            "weak_refs": len(self._weak_refs)
        }


# ==================== Decorators ====================

def cached_query(table: str, ttl: int = 60):
    """
    ⚡ Decorator لتخزين نتائج الاستعلامات
    
    @cached_query("projects", ttl=120)
    def get_all_projects():
        ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = SmartQueryCache()
            
            # إنشاء مفتاح فريد
            key = f"{func.__name__}:{hash(str(args))}:{hash(str(sorted(kwargs.items())))}"
            
            # محاولة جلب من الـ cache
            result = cache.get(key)
            if result is not None:
                return result
            
            # تنفيذ الدالة
            result = func(*args, **kwargs)
            
            # تخزين في الـ cache
            cache.set(key, result, table=table, ttl=ttl)
            
            return result
        
        # إضافة دالة لإبطال الـ cache
        wrapper.invalidate = lambda: SmartQueryCache().invalidate_table(table)
        return wrapper
    
    return decorator


def batch_operation(batch_size: int = 50):
    """
    ⚡ Decorator لتجميع العمليات في دفعات
    """
    def decorator(func: Callable) -> Callable:
        processor = BatchProcessor(batch_size=batch_size)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # تنفيذ مباشر للعمليات الفردية
            return func(*args, **kwargs)
        
        wrapper.batch_add = processor.add
        wrapper.batch_flush = processor.force_flush
        return wrapper
    
    return decorator


def measure_time(func: Callable) -> Callable:
    """
    ⚡ Decorator لقياس وقت التنفيذ
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        
        if elapsed > 0.5:  # تحذير إذا أكثر من 500ms
            logger.warning(f"⚠️ [Performance] {func.__name__} استغرق {elapsed:.2f}s")
        
        return result
    
    return wrapper


# ==================== Utility Functions ====================

def optimize_sqlite_connection(conn: sqlite3.Connection):
    """تطبيق تحسينات SQLite على اتصال موجود"""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")


def get_query_cache() -> SmartQueryCache:
    """الحصول على instance من QueryCache"""
    return SmartQueryCache()


def get_memory_manager() -> MemoryManager:
    """الحصول على instance من MemoryManager"""
    return MemoryManager()


def invalidate_all_caches():
    """إبطال كل الـ caches"""
    SmartQueryCache().invalidate_all()
    logger.info("⚡ تم إبطال كل الـ caches")


def print_performance_stats():
    """طباعة إحصائيات الأداء"""
    cache = SmartQueryCache()
    memory = MemoryManager()
    
    safe_print("\n" + "="*60)
    safe_print("⚡ إحصائيات الأداء - Sky Wave ERP")
    safe_print("="*60)
    safe_print(f"📊 Query Cache: {cache.get_stats()}")
    safe_print(f"💾 Memory: {memory.get_memory_usage()}")
    safe_print("="*60 + "\n")
