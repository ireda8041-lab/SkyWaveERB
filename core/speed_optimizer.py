"""
⚡ محسّن السرعة - Sky Wave ERP
يوفر أدوات لتسريع البرنامج بشكل كبير
"""

import functools
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any


class LRUCache:
    """
    ⚡ Cache ذكي مع حد أقصى للحجم وانتهاء صلاحية
    """

    def __init__(self, maxsize: int = 1000, ttl_seconds: int = 300):
        """
        Args:
            maxsize: الحد الأقصى للعناصر
            ttl_seconds: مدة صلاحية العنصر بالثواني (افتراضي 5 دقائق)
        """
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: dict[str, float] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """جلب قيمة من الـ cache"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            # التحقق من انتهاء الصلاحية
            if time.time() - self._timestamps[key] > self.ttl:
                del self._cache[key]
                del self._timestamps[key]
                self._misses += 1
                return None

            # نقل العنصر للنهاية (الأحدث)
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """تخزين قيمة في الـ cache"""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.maxsize:
                    # حذف الأقدم
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                    del self._timestamps[oldest]

            self._cache[key] = value
            self._timestamps[key] = time.time()

    def invalidate(self, key: str | None = None) -> None:
        """إبطال cache (كله أو عنصر محدد)"""
        with self._lock:
            if key:
                self._cache.pop(key, None)
                self._timestamps.pop(key, None)
            else:
                self._cache.clear()
                self._timestamps.clear()

    def get_stats(self) -> dict[str, Any]:
        """إحصائيات الـ cache"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "maxsize": self.maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }


# ⚡ Cache عام للبيانات
_data_cache = LRUCache(maxsize=500, ttl_seconds=60)  # 1 دقيقة
_query_cache = LRUCache(maxsize=200, ttl_seconds=30)  # 30 ثانية


def cached(cache_key: str | None = None, ttl: int = 60):
    """
    ⚡ Decorator لتخزين نتائج الدوال في الـ cache

    الاستخدام:
    @cached("clients_list", ttl=120)
    def get_all_clients():
        return db.query(...)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # إنشاء مفتاح فريد
            key = cache_key or f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # محاولة جلب من الـ cache
            result = _data_cache.get(key)
            if result is not None:
                return result

            # تنفيذ الدالة وتخزين النتيجة
            result = func(*args, **kwargs)
            _data_cache.set(key, result)
            return result

        # إضافة دالة لإبطال الـ cache
        wrapper.invalidate_cache = lambda: _data_cache.invalidate(cache_key)  # type: ignore[attr-defined]
        return wrapper

    return decorator


def invalidate_cache(pattern: str | None = None):
    """إبطال الـ cache (كله أو بنمط معين)"""
    _data_cache.invalidate()
    _query_cache.invalidate()


class LazyLoader:
    """
    ⚡ تحميل كسول للبيانات الثقيلة
    """

    def __init__(self, loader_func: Callable):
        self._loader = loader_func
        self._data = None
        self._loaded = False
        self._lock = threading.Lock()

    @property
    def data(self) -> Any:
        if not self._loaded:
            with self._lock:
                if not self._loaded:
                    self._data = self._loader()
                    self._loaded = True
        return self._data

    def reload(self) -> None:
        """إعادة تحميل البيانات"""
        with self._lock:
            self._data = self._loader()
            self._loaded = True

    def invalidate(self) -> None:
        """إبطال البيانات المحملة"""
        with self._lock:
            self._data = None
            self._loaded = False


class BatchProcessor:
    """
    ⚡ معالج دفعات للعمليات الكثيرة
    """

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self._queue: list[Any] = []
        self._lock = threading.Lock()

    def add(self, item: Any) -> None:
        """إضافة عنصر للدفعة"""
        with self._lock:
            self._queue.append(item)

    def process(self, processor_func: Callable) -> list:
        """معالجة الدفعة"""
        results = []
        with self._lock:
            while self._queue:
                batch = self._queue[:self.batch_size]
                self._queue = self._queue[self.batch_size:]

                # معالجة الدفعة
                batch_results = processor_func(batch)
                results.extend(batch_results)

        return results


def run_in_background(func: Callable) -> Callable:
    """
    ⚡ Decorator لتشغيل الدالة في الخلفية
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(
            target=func,
            args=args,
            kwargs=kwargs,
            daemon=True
        )
        thread.start()
        return thread

    return wrapper


def debounce(wait_seconds: float = 0.3):
    """
    ⚡ Decorator لتأخير تنفيذ الدالة (مفيد للبحث)
    """
    def decorator(func: Callable) -> Callable:
        timer = [None]

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def call_func():
                func(*args, **kwargs)

            # إلغاء المؤقت السابق
            if timer[0]:
                timer[0].cancel()

            # إنشاء مؤقت جديد
            timer[0] = threading.Timer(wait_seconds, call_func)
            timer[0].start()

        return wrapper

    return decorator


def throttle(min_interval: float = 1.0):
    """
    ⚡ Decorator لتحديد الحد الأقصى لتكرار الدالة
    """
    def decorator(func: Callable) -> Callable:
        last_call = [0.0]

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            if now - last_call[0] >= min_interval:
                last_call[0] = now
                return func(*args, **kwargs)
            return None

        return wrapper

    return decorator


# ⚡ إحصائيات الأداء
def get_cache_stats() -> dict[str, Any]:
    """جلب إحصائيات الـ cache"""
    return {
        "data_cache": _data_cache.get_stats(),
        "query_cache": _query_cache.get_stats()
    }


def print_cache_stats():
    """طباعة إحصائيات الـ cache"""
    stats = get_cache_stats()
    print("\n⚡ إحصائيات الـ Cache:")
    print(f"  Data Cache: {stats['data_cache']}")
    print(f"  Query Cache: {stats['query_cache']}")
