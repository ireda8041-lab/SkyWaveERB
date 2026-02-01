# الملف: core/cache_manager.py
"""
🚀 مدير الـ Cache المحسّن (Cache Manager)
يوفر نظام cache مركزي وذكي مع:
- TTL قابل للتخصيص
- إبطال ذكي
- Thread-safe operations
- إحصائيات الأداء
"""

from __future__ import annotations

import fnmatch
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CacheEntry(Generic[T]):
    """إدخال في الـ cache"""

    def __init__(self, value: T, ttl_seconds: float):
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.access_count = 0
        self.last_access = self.created_at

    def is_expired(self) -> bool:
        """التحقق من انتهاء الصلاحية"""
        return time.time() - self.created_at > self.ttl_seconds

    def access(self) -> T:
        """الوصول للقيمة مع تحديث الإحصائيات"""
        self.access_count += 1
        self.last_access = time.time()
        return self.value

    def remaining_ttl(self) -> float:
        """الوقت المتبقي قبل انتهاء الصلاحية"""
        remaining = self.ttl_seconds - (time.time() - self.created_at)
        return max(0, remaining)


class SmartCache(Generic[T]):
    """
    Cache ذكي مع LRU eviction و TTL

    المميزات:
    - حد أقصى للحجم (maxsize)
    - انتهاء صلاحية تلقائي (TTL)
    - إزالة الأقل استخداماً (LRU)
    - Thread-safe
    - إحصائيات مفصلة

    الاستخدام:
        cache = SmartCache[list](maxsize=100, ttl_seconds=300)

        # تخزين
        cache.set('clients', client_list)

        # جلب
        clients = cache.get('clients')

        # جلب مع دالة تحميل
        clients = cache.get_or_load('clients', load_clients_from_db)
    """

    def __init__(self, maxsize: int = 100, ttl_seconds: float = 300, name: str = ""):
        self.maxsize = maxsize
        self.default_ttl = ttl_seconds
        self.name = name or f"cache_{id(self)}"

        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = threading.RLock()

        # إحصائيات
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        logger.debug(
            "✅ تم إنشاء SmartCache: %s (maxsize=%s, ttl=%ss)", self.name, maxsize, ttl_seconds
        )

    def get(self, key: str) -> T | None:
        """
        جلب قيمة من الـ cache

        Args:
            key: مفتاح القيمة

        Returns:
            القيمة أو None إذا غير موجودة/منتهية
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            # نقل للنهاية (LRU)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.access()

    def set(self, key: str, value: T, ttl_seconds: float | None = None) -> None:
        """
        تخزين قيمة في الـ cache

        Args:
            key: مفتاح القيمة
            value: القيمة
            ttl_seconds: وقت الصلاحية (اختياري)
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        with self._lock:
            # إزالة القديم إذا موجود
            if key in self._cache:
                del self._cache[key]

            # إزالة الأقدم إذا وصلنا للحد الأقصى
            while len(self._cache) >= self.maxsize:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._evictions += 1

            # إضافة الجديد
            self._cache[key] = CacheEntry(value, ttl)

    def get_or_load(self, key: str, loader: Callable[[], T], ttl_seconds: float | None = None) -> T:
        """
        جلب من الـ cache أو تحميل إذا غير موجود

        Args:
            key: مفتاح القيمة
            loader: دالة التحميل
            ttl_seconds: وقت الصلاحية (اختياري)

        Returns:
            القيمة (من الـ cache أو محملة)
        """
        value = self.get(key)
        if value is not None:
            return value

        # تحميل وتخزين
        value = loader()
        self.set(key, value, ttl_seconds)
        return value

    def invalidate(self, key: str) -> bool:
        """
        إبطال قيمة معينة

        Args:
            key: مفتاح القيمة

        Returns:
            True إذا تم الإبطال
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """
        إبطال كل القيم التي تطابق نمط معين

        Args:
            pattern: نمط البحث (يدعم * كـ wildcard)

        Returns:
            عدد القيم التي تم إبطالها
        """

        invalidated = 0
        with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_remove:
                del self._cache[key]
                invalidated += 1

        return invalidated

    def clear(self) -> int:
        """
        مسح كل الـ cache

        Returns:
            عدد العناصر التي تم مسحها
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def cleanup_expired(self) -> int:
        """
        تنظيف العناصر المنتهية الصلاحية

        Returns:
            عدد العناصر التي تم تنظيفها
        """
        cleaned = 0
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]
                cleaned += 1

        return cleaned

    def get_stats(self) -> dict[str, Any]:
        """
        الحصول على إحصائيات الـ cache

        Returns:
            dict مع الإحصائيات
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "name": self.name,
                "size": len(self._cache),
                "maxsize": self.maxsize,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.1f}%",
                "evictions": self._evictions,
                "default_ttl": self.default_ttl,
            }

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            return entry is not None and not entry.is_expired()


class CacheManager:
    """
    مدير الـ Cache المركزي

    يدير عدة caches ويوفر:
    - إنشاء caches مسماة
    - إبطال عبر الـ caches
    - إحصائيات مجمعة
    - تنظيف دوري

    الاستخدام:
        # الحصول على cache
        clients_cache = cache_manager.get_cache('clients', ttl=300)

        # إبطال عبر كل الـ caches
        cache_manager.invalidate_all('clients')

        # إحصائيات
        stats = cache_manager.get_all_stats()
    """

    _instance: CacheManager | None = None
    _lock = threading.Lock()
    _initialized = False

    # إعدادات TTL الافتراضية لكل نوع بيانات - محسّنة للسرعة
    DEFAULT_TTL = {
        "clients": 600,  # ⚡ 10 دقائق
        "projects": 600,  # ⚡ 10 دقائق
        "services": 900,  # ⚡ 15 دقيقة
        "accounts": 900,  # ⚡ 15 دقيقة
        "settings": 3600,  # ⚡ ساعة
        "currencies": 7200,  # ⚡ ساعتين
        "expenses": 300,  # ⚡ 5 دقائق
        "payments": 300,  # ⚡ 5 دقائق
        "default": 600,  # ⚡ 10 دقائق
    }

    def __new__(cls) -> CacheManager:
        """Singleton pattern"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._caches: dict[str, SmartCache] = {}
        self._caches_lock = threading.RLock()
        self._initialized = True

        logger.info("✅ تم تهيئة CacheManager")

    def get_cache(
        self, name: str, maxsize: int = 500, ttl_seconds: float | None = None
    ) -> SmartCache:
        """
        الحصول على cache بالاسم (أو إنشاؤه)

        Args:
            name: اسم الـ cache
            maxsize: الحد الأقصى للحجم
            ttl_seconds: وقت الصلاحية

        Returns:
            SmartCache instance
        """
        with self._caches_lock:
            if name not in self._caches:
                ttl = ttl_seconds or self.DEFAULT_TTL.get(name, self.DEFAULT_TTL["default"])
                self._caches[name] = SmartCache(maxsize=maxsize, ttl_seconds=ttl, name=name)
            return self._caches[name]

    def invalidate(self, cache_name: str, key: str) -> bool:
        """
        إبطال قيمة في cache معين

        Args:
            cache_name: اسم الـ cache
            key: مفتاح القيمة

        Returns:
            True إذا تم الإبطال
        """
        with self._caches_lock:
            cache = self._caches.get(cache_name)
            if cache:
                return cache.invalidate(key)
            return False

    def invalidate_all(self, key: str) -> int:
        """
        إبطال قيمة في كل الـ caches

        Args:
            key: مفتاح القيمة

        Returns:
            عدد الـ caches التي تم الإبطال فيها
        """
        invalidated = 0
        with self._caches_lock:
            for cache in self._caches.values():
                if cache.invalidate(key):
                    invalidated += 1
        return invalidated

    def clear_cache(self, name: str) -> int:
        """
        مسح cache معين

        Args:
            name: اسم الـ cache

        Returns:
            عدد العناصر التي تم مسحها
        """
        with self._caches_lock:
            cache = self._caches.get(name)
            if cache:
                return cache.clear()
            return 0

    def clear_all(self) -> int:
        """
        مسح كل الـ caches

        Returns:
            عدد العناصر التي تم مسحها
        """
        total = 0
        with self._caches_lock:
            for cache in self._caches.values():
                total += cache.clear()

        logger.info("🗑️ تم مسح %s عنصر من كل الـ caches", total)
        return total

    def cleanup_expired(self) -> int:
        """
        تنظيف العناصر المنتهية في كل الـ caches

        Returns:
            عدد العناصر التي تم تنظيفها
        """
        total = 0
        with self._caches_lock:
            for cache in self._caches.values():
                total += cache.cleanup_expired()

        if total > 0:
            logger.debug("🧹 تم تنظيف %s عنصر منتهي الصلاحية", total)

        return total

    def get_stats(self, name: str) -> dict[str, Any] | None:
        """
        الحصول على إحصائيات cache معين

        Args:
            name: اسم الـ cache

        Returns:
            dict مع الإحصائيات أو None
        """
        with self._caches_lock:
            cache = self._caches.get(name)
            if cache:
                return cache.get_stats()
            return None

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """
        الحصول على إحصائيات كل الـ caches

        Returns:
            dict مع إحصائيات كل cache
        """
        with self._caches_lock:
            return {name: cache.get_stats() for name, cache in self._caches.items()}

    def get_summary(self) -> dict[str, Any]:
        """
        الحصول على ملخص إحصائيات

        Returns:
            dict مع الملخص
        """
        with self._caches_lock:
            total_size = sum(len(c) for c in self._caches.values())
            total_hits = sum(c._hits for c in self._caches.values())
            total_misses = sum(c._misses for c in self._caches.values())
            total_requests = total_hits + total_misses

            return {
                "cache_count": len(self._caches),
                "total_entries": total_size,
                "total_hits": total_hits,
                "total_misses": total_misses,
                "overall_hit_rate": (
                    f"{(total_hits / total_requests * 100):.1f}%" if total_requests > 0 else "N/A"
                ),
            }


# Singleton instance
cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """الحصول على مدير الـ Cache"""
    return cache_manager


def get_cache(name: str, **kwargs) -> SmartCache:
    """الحصول على cache بالاسم"""
    return cache_manager.get_cache(name, **kwargs)


def invalidate_cache(name: str, key: str | None = None) -> int:
    """
    إبطال cache

    Args:
        name: اسم الـ cache
        key: مفتاح معين (اختياري - إذا لم يُحدد يتم مسح كل الـ cache)

    Returns:
        عدد العناصر التي تم إبطالها
    """
    if key:
        return 1 if cache_manager.invalidate(name, key) else 0
    return cache_manager.clear_cache(name)
