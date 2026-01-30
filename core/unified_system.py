# الملف: core/unified_system.py
"""
🚀 النظام الموحد المحسّن - Sky Wave ERP
=====================================
يوحّد جميع الأنظمة المتكررة في نظام واحد احترافي:
- المزامنة (Sync)
- إدارة الإشارات (Signals)
- إدارة الموارد (Resources)
- إدارة الـ Cache
- إدارة قاعدة البيانات (DB Context)

المميزات:
✅ توحيد 5 أنظمة مزامنة في نظام واحد
✅ فصل تلقائي للإشارات عند الإغلاق
✅ إدارة آمنة للـ Cursors مع context managers
✅ تنظيف تلقائي للموارد
✅ Cache ذكي مع TTL محسّن
"""

from __future__ import annotations

import atexit
import json
import sqlite3
import threading
import time
import weakref
from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Generator, TypeVar

from PyQt6.QtCore import QMetaObject, QObject, Qt, QTimer, pyqtSignal

from core.logger import get_logger

if TYPE_CHECKING:
    from core.repository import Repository

logger = get_logger(__name__)

T = TypeVar('T')


# ============================================================
# 🔒 مدير سياق قاعدة البيانات المحسّن
# ============================================================

class SafeDatabaseContext:
    """
    مدير سياق قاعدة البيانات الآمن
    يضمن إغلاق الـ cursors دائماً حتى في حالة الأخطاء
    """
    
    def __init__(self, repository: Repository):
        self.repo = repository
        self._lock = threading.RLock()
        self._active_cursors: weakref.WeakSet = weakref.WeakSet()
        logger.debug("✅ تم تهيئة SafeDatabaseContext")
    
    @contextmanager
    def cursor(self, row_factory: bool = True) -> Generator[sqlite3.Cursor, None, None]:
        """
        الحصول على cursor مع إغلاق تلقائي
        
        Usage:
            with db_context.cursor() as cursor:
                cursor.execute("SELECT * FROM clients")
                results = cursor.fetchall()
        """
        cursor = None
        try:
            with self._lock:
                cursor = self.repo.sqlite_conn.cursor()
                if row_factory:
                    cursor.row_factory = sqlite3.Row
                self._active_cursors.add(cursor)
            yield cursor
        except Exception as e:
            logger.error(f"❌ خطأ في cursor: {e}")
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
    
    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        تنفيذ transaction مع commit/rollback تلقائي
        
        Usage:
            with db_context.transaction() as cursor:
                cursor.execute("INSERT INTO clients ...")
                cursor.execute("UPDATE accounts ...")
            # commit تلقائي هنا، أو rollback في حالة الخطأ
        """
        cursor = None
        try:
            with self._lock:
                cursor = self.repo.sqlite_conn.cursor()
                cursor.row_factory = sqlite3.Row
            yield cursor
            self.repo.sqlite_conn.commit()
        except Exception as e:
            try:
                self.repo.sqlite_conn.rollback()
            except Exception:
                pass
            logger.error(f"❌ خطأ في transaction: {e}")
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
    
    def close_all_cursors(self):
        """إغلاق جميع الـ cursors النشطة"""
        for cursor in list(self._active_cursors):
            try:
                cursor.close()
            except Exception:
                pass


# ============================================================
# 🔗 مدير الإشارات المحسّن
# ============================================================

class SignalConnection:
    """تمثيل اتصال إشارة واحد"""
    
    def __init__(self, signal_name: str, sender: QObject, receiver: Callable,
                 receiver_obj: QObject | None = None):
        self.signal_name = signal_name
        self.sender_ref = weakref.ref(sender) if sender else None
        self.receiver = receiver
        self.receiver_obj_ref = weakref.ref(receiver_obj) if receiver_obj else None
        self.connected = True
    
    @property
    def sender(self) -> QObject | None:
        return self.sender_ref() if self.sender_ref else None
    
    @property
    def receiver_obj(self) -> QObject | None:
        return self.receiver_obj_ref() if self.receiver_obj_ref else None
    
    def is_valid(self) -> bool:
        """التحقق من صلاحية الاتصال"""
        if not self.connected:
            return False
        if self.sender_ref and self.sender_ref() is None:
            return False
        if self.receiver_obj_ref and self.receiver_obj_ref() is None:
            return False
        return True
    
    def disconnect(self) -> bool:
        """فصل الاتصال"""
        if not self.connected:
            return False
        try:
            sender = self.sender
            if sender is not None:
                signal = getattr(sender, self.signal_name, None)
                if signal is not None:
                    try:
                        signal.disconnect(self.receiver)
                    except (TypeError, RuntimeError):
                        pass
            self.connected = False
            return True
        except Exception:
            self.connected = False
            return False


class SafeSignalManager:
    """
    مدير الإشارات الآمن
    يتتبع جميع الاتصالات ويفصلها تلقائياً عند الإغلاق
    """
    
    _instance: SafeSignalManager | None = None
    _lock = threading.Lock()
    
    def __new__(cls) -> SafeSignalManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._connections: dict[int, list[SignalConnection]] = defaultdict(list)
        self._all_connections: list[SignalConnection] = []
        self._connection_lock = threading.RLock()
        self._initialized = True
        logger.info("✅ تم تهيئة SafeSignalManager")
    
    def connect(self, sender: QObject, signal_name: str, receiver: Callable,
                receiver_obj: QObject | None = None,
                connection_type: Qt.ConnectionType = Qt.ConnectionType.AutoConnection
                ) -> SignalConnection | None:
        """
        تسجيل اتصال إشارة مع تتبع
        
        Args:
            sender: الكائن المُرسل للإشارة
            signal_name: اسم الإشارة
            receiver: الدالة المستقبلة
            receiver_obj: الكائن المستقبل (للتتبع والفصل التلقائي)
        """
        try:
            signal = getattr(sender, signal_name, None)
            if signal is None:
                logger.warning(f"⚠️ الإشارة غير موجودة: {signal_name}")
                return None
            
            signal.connect(receiver, connection_type)
            
            connection = SignalConnection(
                signal_name=signal_name,
                sender=sender,
                receiver=receiver,
                receiver_obj=receiver_obj
            )
            
            with self._connection_lock:
                self._all_connections.append(connection)
                if receiver_obj is not None:
                    self._connections[id(receiver_obj)].append(connection)
            
            return connection
        except Exception as e:
            logger.error(f"❌ فشل تسجيل الاتصال: {e}")
            return None
    
    def disconnect_all(self, receiver_obj: QObject) -> int:
        """
        فصل جميع اتصالات كائن معين
        يجب استدعاؤها في closeEvent للنوافذ
        """
        obj_id = id(receiver_obj)
        disconnected = 0
        
        with self._connection_lock:
            connections = self._connections.pop(obj_id, [])
            for conn in connections:
                if conn.disconnect():
                    disconnected += 1
        
        if disconnected > 0:
            logger.debug(f"🔌 تم فصل {disconnected} اتصال")
        
        return disconnected
    
    def cleanup_dead_connections(self) -> int:
        """تنظيف الاتصالات الميتة"""
        cleaned = 0
        with self._connection_lock:
            valid = []
            for conn in self._all_connections:
                if conn.is_valid():
                    valid.append(conn)
                else:
                    conn.disconnect()
                    cleaned += 1
            self._all_connections = valid
        return cleaned
    
    def disconnect_all_signals(self) -> int:
        """فصل جميع الاتصالات (عند إغلاق التطبيق)"""
        disconnected = 0
        with self._connection_lock:
            for conn in self._all_connections:
                if conn.disconnect():
                    disconnected += 1
            self._all_connections.clear()
            self._connections.clear()
        logger.info(f"🔌 تم فصل {disconnected} اتصال عند الإغلاق")
        return disconnected
    
    def get_stats(self) -> dict[str, Any]:
        """إحصائيات الاتصالات"""
        with self._connection_lock:
            total = len(self._all_connections)
            valid = sum(1 for c in self._all_connections if c.is_valid())
            return {
                'total': total,
                'valid': valid,
                'dead': total - valid,
                'tracked_objects': len(self._connections)
            }


# ============================================================
# 🧹 مدير الموارد المحسّن
# ============================================================

class ManagedTimer:
    """Timer مُدار"""
    def __init__(self, timer: QTimer, name: str = ""):
        self.timer_ref = weakref.ref(timer)
        self.name = name
        self.stopped = False
    
    def stop(self) -> bool:
        if self.stopped:
            return False
        timer = self.timer_ref() if self.timer_ref else None
        if timer:
            try:
                timer.stop()
                self.stopped = True
                return True
            except (RuntimeError, AttributeError):
                self.stopped = True
        return False


class ManagedThread:
    """Thread مُدار"""
    def __init__(self, thread: threading.Thread, name: str = ""):
        self.thread = thread
        self.name = name or thread.name
        self.stop_event = threading.Event()
    
    def request_stop(self):
        self.stop_event.set()
    
    def join(self, timeout: float = 5.0) -> bool:
        self.request_stop()
        self.thread.join(timeout)
        return not self.thread.is_alive()


class SafeResourceManager:
    """
    مدير الموارد الآمن
    يتتبع ويدير جميع الموارد ويضمن تنظيفها عند الإغلاق
    """
    
    _instance: SafeResourceManager | None = None
    _lock = threading.Lock()
    
    def __new__(cls) -> SafeResourceManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._timers: list[ManagedTimer] = []
        self._threads: list[ManagedThread] = []
        self._cleanup_callbacks: list[tuple[int, Callable]] = []
        self._resources_lock = threading.RLock()
        self._cleanup_done = False
        self._initialized = True
        
        atexit.register(self._atexit_cleanup)
        logger.info("✅ تم تهيئة SafeResourceManager")
    
    def register_timer(self, timer: QTimer, name: str = "") -> ManagedTimer:
        """تسجيل QTimer للإدارة"""
        managed = ManagedTimer(timer, name)
        with self._resources_lock:
            self._timers.append(managed)
        return managed
    
    def register_thread(self, thread: threading.Thread, name: str = "") -> ManagedThread:
        """تسجيل Thread للإدارة"""
        managed = ManagedThread(thread, name)
        with self._resources_lock:
            self._threads.append(managed)
        return managed
    
    def register_cleanup(self, callback: Callable, priority: int = 0):
        """تسجيل دالة تنظيف"""
        with self._resources_lock:
            self._cleanup_callbacks.append((priority, callback))
            self._cleanup_callbacks.sort(key=lambda x: -x[0])
    
    def cleanup_all(self) -> dict[str, int]:
        """تنظيف جميع الموارد"""
        if self._cleanup_done:
            return {'already_cleaned': True}
        
        logger.info("🧹 بدء تنظيف جميع الموارد...")
        stats = {'timers': 0, 'threads': 0, 'callbacks': 0}
        
        try:
            # إيقاف الـ timers
            with self._resources_lock:
                for t in self._timers:
                    if t.stop():
                        stats['timers'] += 1
            
            # تنفيذ callbacks
            for _, callback in self._cleanup_callbacks:
                try:
                    callback()
                    stats['callbacks'] += 1
                except Exception:
                    pass
            
            # إيقاف الـ threads
            with self._resources_lock:
                for t in self._threads:
                    if t.join(2):
                        stats['threads'] += 1
            
            self._cleanup_done = True
            logger.info(f"✅ تم تنظيف الموارد: {stats}")
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف الموارد: {e}")
        
        return stats
    
    def _atexit_cleanup(self):
        if not self._cleanup_done:
            self.cleanup_all()


# ============================================================
# 🚀 مدير الـ Cache المحسّن
# ============================================================

class CacheEntry:
    """إدخال في الـ cache"""
    def __init__(self, value: Any, ttl_seconds: float):
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.access_count = 0
    
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds
    
    def access(self) -> Any:
        self.access_count += 1
        return self.value


class SmartCacheManager:
    """
    مدير الـ Cache الذكي
    يوفر cache مركزي مع TTL محسّن وإبطال ذكي
    """
    
    _instance: SmartCacheManager | None = None
    _lock = threading.Lock()
    
    # TTL الافتراضي لكل نوع (بالثواني)
    DEFAULT_TTL = {
        'clients': 300,      # 5 دقائق
        'projects': 300,
        'services': 600,     # 10 دقائق
        'accounts': 600,
        'settings': 1800,    # 30 دقيقة
        'default': 300
    }
    
    def __new__(cls) -> SmartCacheManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._caches: dict[str, OrderedDict[str, CacheEntry]] = defaultdict(OrderedDict)
        self._cache_lock = threading.RLock()
        self._max_size = 500
        self._hits = 0
        self._misses = 0
        self._initialized = True
        logger.info("✅ تم تهيئة SmartCacheManager")
    
    def get(self, cache_name: str, key: str) -> Any | None:
        """جلب قيمة من الـ cache"""
        with self._cache_lock:
            cache = self._caches.get(cache_name)
            if not cache:
                self._misses += 1
                return None
            
            entry = cache.get(key)
            if not entry:
                self._misses += 1
                return None
            
            if entry.is_expired():
                del cache[key]
                self._misses += 1
                return None
            
            cache.move_to_end(key)
            self._hits += 1
            return entry.access()
    
    def set(self, cache_name: str, key: str, value: Any, ttl: float | None = None):
        """تخزين قيمة في الـ cache"""
        if ttl is None:
            ttl = self.DEFAULT_TTL.get(cache_name, self.DEFAULT_TTL['default'])
        
        with self._cache_lock:
            cache = self._caches[cache_name]
            
            if key in cache:
                del cache[key]
            
            while len(cache) >= self._max_size:
                cache.popitem(last=False)
            
            cache[key] = CacheEntry(value, ttl)
    
    def invalidate(self, cache_name: str, key: str | None = None):
        """إبطال cache"""
        with self._cache_lock:
            if cache_name in self._caches:
                if key:
                    self._caches[cache_name].pop(key, None)
                else:
                    self._caches[cache_name].clear()
    
    def invalidate_all(self):
        """إبطال كل الـ caches"""
        with self._cache_lock:
            for cache in self._caches.values():
                cache.clear()
    
    def cleanup_expired(self) -> int:
        """تنظيف العناصر المنتهية"""
        cleaned = 0
        with self._cache_lock:
            for cache in self._caches.values():
                expired = [k for k, v in cache.items() if v.is_expired()]
                for k in expired:
                    del cache[k]
                    cleaned += 1
        return cleaned
    
    def get_stats(self) -> dict[str, Any]:
        """إحصائيات الـ cache"""
        total = self._hits + self._misses
        return {
            'caches': len(self._caches),
            'total_entries': sum(len(c) for c in self._caches.values()),
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f"{(self._hits / total * 100):.1f}%" if total > 0 else "N/A"
        }


# ============================================================
# 🌐 Singleton Instances
# ============================================================

# مدير الإشارات
signal_manager = SafeSignalManager()

# مدير الموارد
resource_manager = SafeResourceManager()

# مدير الـ Cache
cache_manager = SmartCacheManager()

# مدير قاعدة البيانات (يُنشأ عند الحاجة)
_db_context: SafeDatabaseContext | None = None


def get_db_context(repository: Repository) -> SafeDatabaseContext:
    """الحصول على مدير سياق قاعدة البيانات"""
    global _db_context
    if _db_context is None:
        _db_context = SafeDatabaseContext(repository)
    return _db_context


def get_signal_manager() -> SafeSignalManager:
    """الحصول على مدير الإشارات"""
    return signal_manager


def get_resource_manager() -> SafeResourceManager:
    """الحصول على مدير الموارد"""
    return resource_manager


def get_cache_manager() -> SmartCacheManager:
    """الحصول على مدير الـ Cache"""
    return cache_manager


# ============================================================
# 🧹 دوال التنظيف الشاملة
# ============================================================

def cleanup_all_systems():
    """
    تنظيف جميع الأنظمة عند إغلاق التطبيق
    يجب استدعاؤها في aboutToQuit أو _cleanup_on_exit
    """
    logger.info("🧹 بدء تنظيف جميع الأنظمة...")
    
    # 1. فصل جميع الإشارات
    signal_manager.disconnect_all_signals()
    
    # 2. تنظيف الموارد
    resource_manager.cleanup_all()
    
    # 3. إبطال الـ cache
    cache_manager.invalidate_all()
    
    # 4. إغلاق الـ cursors
    if _db_context:
        _db_context.close_all_cursors()
    
    logger.info("✅ تم تنظيف جميع الأنظمة")


# تسجيل التنظيف عند إغلاق Python
atexit.register(cleanup_all_systems)
