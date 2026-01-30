# الملف: core/resource_manager.py
"""
🧹 مدير الموارد (Resource Manager)
يوفر إدارة مركزية لجميع موارد التطبيق:
- Timers
- Threads
- Database connections
- Signal connections
- Background tasks

يضمن تنظيف جميع الموارد عند إغلاق التطبيق
"""

from __future__ import annotations

import atexit
import threading
import weakref
from typing import Any, Callable

from PyQt6.QtCore import QObject, QTimer

from core.logger import get_logger

logger = get_logger(__name__)


class ManagedTimer:
    """Timer مُدار مع إيقاف تلقائي"""
    
    def __init__(self, timer: QTimer, name: str = ""):
        self.timer_ref = weakref.ref(timer)
        self.name = name
        self.stopped = False
    
    @property
    def timer(self) -> QTimer | None:
        return self.timer_ref() if self.timer_ref else None
    
    def stop(self) -> bool:
        """إيقاف الـ timer"""
        if self.stopped:
            return False
        
        timer = self.timer
        if timer is not None:
            try:
                timer.stop()
                self.stopped = True
                return True
            except (RuntimeError, AttributeError):
                self.stopped = True
                return False
        return False
    
    def is_active(self) -> bool:
        """التحقق من نشاط الـ timer"""
        timer = self.timer
        if timer is None or self.stopped:
            return False
        try:
            return timer.isActive()
        except RuntimeError:
            return False


class ManagedThread:
    """Thread مُدار مع إيقاف آمن"""
    
    def __init__(self, thread: threading.Thread, name: str = ""):
        self.thread = thread
        self.name = name or thread.name
        self.stop_event = threading.Event()
    
    def request_stop(self):
        """طلب إيقاف الـ thread"""
        self.stop_event.set()
    
    def is_alive(self) -> bool:
        """التحقق من حياة الـ thread"""
        return self.thread.is_alive()
    
    def join(self, timeout: float = 5.0) -> bool:
        """انتظار انتهاء الـ thread"""
        self.request_stop()
        self.thread.join(timeout)
        return not self.thread.is_alive()


class ResourceManager:
    """
    مدير الموارد المركزي
    
    يتتبع ويدير:
    - QTimers
    - Threads
    - Cleanup callbacks
    - Background tasks
    
    الاستخدام:
        # تسجيل timer
        timer = QTimer()
        resource_manager.register_timer(timer, "sync_timer")
        
        # تسجيل cleanup callback
        resource_manager.register_cleanup(my_cleanup_function)
        
        # عند الإغلاق
        resource_manager.cleanup_all()
    """
    
    _instance: ResourceManager | None = None
    _lock = threading.Lock()
    
    def __new__(cls) -> ResourceManager:
        """Singleton pattern"""
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
        self._cleanup_callbacks: list[Callable[[], None]] = []
        self._resources_lock = threading.RLock()
        self._cleanup_done = False
        self._initialized = True
        
        # تسجيل cleanup عند إغلاق Python
        atexit.register(self._atexit_cleanup)
        
        logger.info("✅ تم تهيئة ResourceManager")
    
    def register_timer(self, timer: QTimer, name: str = "") -> ManagedTimer:
        """
        تسجيل QTimer للإدارة
        
        Args:
            timer: الـ timer المراد تسجيله
            name: اسم وصفي (اختياري)
            
        Returns:
            ManagedTimer للتحكم
        """
        managed = ManagedTimer(timer, name)
        
        with self._resources_lock:
            self._timers.append(managed)
        
        logger.debug(f"⏰ تم تسجيل timer: {name or 'unnamed'}")
        return managed
    
    def register_thread(
        self, 
        thread: threading.Thread, 
        name: str = ""
    ) -> ManagedThread:
        """
        تسجيل Thread للإدارة
        
        Args:
            thread: الـ thread المراد تسجيله
            name: اسم وصفي (اختياري)
            
        Returns:
            ManagedThread للتحكم
        """
        managed = ManagedThread(thread, name)
        
        with self._resources_lock:
            self._threads.append(managed)
        
        logger.debug(f"🧵 تم تسجيل thread: {managed.name}")
        return managed
    
    def register_cleanup(self, callback: Callable[[], None], priority: int = 0):
        """
        تسجيل دالة تنظيف
        
        Args:
            callback: الدالة المراد استدعاؤها عند التنظيف
            priority: الأولوية (الأعلى يُنفذ أولاً)
        """
        with self._resources_lock:
            self._cleanup_callbacks.append((priority, callback))
            # ترتيب حسب الأولوية (الأعلى أولاً)
            self._cleanup_callbacks.sort(key=lambda x: -x[0])
        
        logger.debug(f"🧹 تم تسجيل cleanup callback (priority={priority})")
    
    def stop_all_timers(self) -> int:
        """
        إيقاف جميع الـ timers المسجلة
        
        Returns:
            عدد الـ timers التي تم إيقافها
        """
        stopped = 0
        
        with self._resources_lock:
            for managed in self._timers:
                if managed.stop():
                    stopped += 1
                    logger.debug(f"⏹️ تم إيقاف timer: {managed.name}")
        
        if stopped > 0:
            logger.info(f"⏹️ تم إيقاف {stopped} timer")
        
        return stopped
    
    def stop_all_threads(self, timeout: float = 5.0) -> int:
        """
        إيقاف جميع الـ threads المسجلة
        
        Args:
            timeout: وقت الانتظار لكل thread
            
        Returns:
            عدد الـ threads التي تم إيقافها
        """
        stopped = 0
        
        with self._resources_lock:
            for managed in self._threads:
                if managed.is_alive():
                    if managed.join(timeout):
                        stopped += 1
                        logger.debug(f"🛑 تم إيقاف thread: {managed.name}")
                    else:
                        logger.warning(f"⚠️ فشل إيقاف thread: {managed.name}")
        
        if stopped > 0:
            logger.info(f"🛑 تم إيقاف {stopped} thread")
        
        return stopped
    
    def run_cleanup_callbacks(self) -> int:
        """
        تنفيذ جميع دوال التنظيف
        
        Returns:
            عدد الدوال التي تم تنفيذها بنجاح
        """
        executed = 0
        
        with self._resources_lock:
            callbacks = list(self._cleanup_callbacks)
        
        for priority, callback in callbacks:
            try:
                callback()
                executed += 1
            except Exception as e:
                logger.warning(f"⚠️ خطأ في cleanup callback: {e}")
        
        if executed > 0:
            logger.info(f"🧹 تم تنفيذ {executed} cleanup callback")
        
        return executed
    
    def cleanup_all(self) -> dict[str, int]:
        """
        تنظيف جميع الموارد
        
        Returns:
            dict مع إحصائيات التنظيف
        """
        if self._cleanup_done:
            return {'already_cleaned': True}
        
        logger.info("🧹 بدء تنظيف جميع الموارد...")
        
        stats = {
            'timers_stopped': 0,
            'threads_stopped': 0,
            'callbacks_executed': 0
        }
        
        try:
            # 1. إيقاف الـ timers أولاً
            stats['timers_stopped'] = self.stop_all_timers()
            
            # 2. تنفيذ دوال التنظيف
            stats['callbacks_executed'] = self.run_cleanup_callbacks()
            
            # 3. إيقاف الـ threads
            stats['threads_stopped'] = self.stop_all_threads()
            
            self._cleanup_done = True
            logger.info(f"✅ تم تنظيف الموارد: {stats}")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف الموارد: {e}")
        
        return stats
    
    def _atexit_cleanup(self):
        """تنظيف عند إغلاق Python"""
        if not self._cleanup_done:
            logger.info("🔚 تنظيف الموارد عند إغلاق Python...")
            self.cleanup_all()
    
    def get_stats(self) -> dict[str, Any]:
        """
        الحصول على إحصائيات الموارد
        
        Returns:
            dict مع الإحصائيات
        """
        with self._resources_lock:
            active_timers = sum(1 for t in self._timers if t.is_active())
            alive_threads = sum(1 for t in self._threads if t.is_alive())
            
            return {
                'total_timers': len(self._timers),
                'active_timers': active_timers,
                'total_threads': len(self._threads),
                'alive_threads': alive_threads,
                'cleanup_callbacks': len(self._cleanup_callbacks),
                'cleanup_done': self._cleanup_done
            }
    
    def remove_dead_resources(self) -> int:
        """
        إزالة الموارد الميتة من القوائم
        
        Returns:
            عدد الموارد التي تم إزالتها
        """
        removed = 0
        
        with self._resources_lock:
            # إزالة الـ timers الميتة
            alive_timers = []
            for t in self._timers:
                if t.timer is not None and not t.stopped:
                    alive_timers.append(t)
                else:
                    removed += 1
            self._timers = alive_timers
            
            # إزالة الـ threads المنتهية
            alive_threads = []
            for t in self._threads:
                if t.is_alive():
                    alive_threads.append(t)
                else:
                    removed += 1
            self._threads = alive_threads
        
        if removed > 0:
            logger.debug(f"🗑️ تم إزالة {removed} مورد ميت")
        
        return removed


# Singleton instance
resource_manager = ResourceManager()


def get_resource_manager() -> ResourceManager:
    """الحصول على مدير الموارد"""
    return resource_manager


# دوال مساعدة للاستخدام السريع
def register_timer(timer: QTimer, name: str = "") -> ManagedTimer:
    """تسجيل timer للإدارة"""
    return resource_manager.register_timer(timer, name)


def register_cleanup(callback: Callable[[], None], priority: int = 0):
    """تسجيل دالة تنظيف"""
    resource_manager.register_cleanup(callback, priority)


def cleanup_all() -> dict[str, int]:
    """تنظيف جميع الموارد"""
    return resource_manager.cleanup_all()
