# الملف: core/optimizations.py
"""
⚡ ملف التحسينات الشامل - Sky Wave ERP
================================
يجمع كل أدوات تحسين الأداء في مكان واحد
"""

# استيراد كل أدوات التحسين
from core.speed_optimizer import (
    LRUCache,
    LazyLoader,
    BatchProcessor,
    cached,
    invalidate_cache,
    run_in_background,
    debounce,
    throttle,
    get_cache_stats,
    print_cache_stats,
)

from core.data_loader import (
    DataLoaderWorker,
    DataLoaderRunnable,
    BackgroundDataLoader,
    get_data_loader,
)

# تصدير كل الأدوات
__all__ = [
    # Speed Optimizer
    'LRUCache',
    'LazyLoader', 
    'BatchProcessor',
    'cached',
    'invalidate_cache',
    'run_in_background',
    'debounce',
    'throttle',
    'get_cache_stats',
    'print_cache_stats',
    
    # Data Loader
    'DataLoaderWorker',
    'DataLoaderRunnable',
    'BackgroundDataLoader',
    'get_data_loader',
    
    # Performance Optimizer
    'SmartQueryCache',
    'SQLiteConnectionPool',
    'MemoryManager',
    'cached_query',
    'batch_operation',
    'measure_time',
    'optimize_sqlite_connection',
    'get_query_cache',
    'get_memory_manager',
    'invalidate_all_caches',
    'print_performance_stats',
    
    # UI Optimizer
    'UIOptimizer',
    'DebouncedSignal',
    'ThrottledSignal',
    'ProgressiveLoader',
    'VirtualTableModel',
    
    # Lazy Tab Loader
    'LazyTabLoader',
    'LazyTabPlaceholder',
    'PriorityTabLoader',
]

# استيراد مشروط للأدوات الإضافية
try:
    from core.performance_optimizer import (
        SmartQueryCache,
        SQLiteConnectionPool,
        MemoryManager,
        cached_query,
        batch_operation,
        measure_time,
        optimize_sqlite_connection,
        get_query_cache,
        get_memory_manager,
        invalidate_all_caches,
        print_performance_stats,
    )
except ImportError:
    pass

try:
    from core.ui_optimizer import (
        UIOptimizer,
        DebouncedSignal,
        ThrottledSignal,
        ProgressiveLoader,
        VirtualTableModel,
    )
except ImportError:
    pass

try:
    from core.lazy_tab_loader import (
        LazyTabLoader,
        LazyTabPlaceholder,
        PriorityTabLoader,
    )
except ImportError:
    pass


def apply_all_optimizations():
    """
    ⚡ تطبيق كل التحسينات على البرنامج
    يُستدعى عند بدء التشغيل
    """
    print("⚡ جاري تطبيق تحسينات الأداء...")
    
    optimizations_applied = []
    
    # 1. تهيئة Query Cache
    try:
        cache = SmartQueryCache()
        optimizations_applied.append("Query Cache")
    except Exception:
        pass
    
    # 2. تهيئة Memory Manager
    try:
        memory = MemoryManager()
        optimizations_applied.append("Memory Manager")
    except Exception:
        pass
    
    # 3. تهيئة Data Loader
    try:
        loader = get_data_loader()
        optimizations_applied.append("Background Data Loader")
    except Exception:
        pass
    
    print(f"⚡ تم تطبيق: {', '.join(optimizations_applied)}")
    return len(optimizations_applied)


def cleanup_all():
    """
    ⚡ تنظيف كل الموارد
    يُستدعى عند إغلاق البرنامج
    """
    try:
        # تنظيف الـ caches
        invalidate_all_caches()
        
        # تنظيف الذاكرة
        memory = get_memory_manager()
        memory.cleanup(force=True)
        
        print("⚡ تم تنظيف كل الموارد")
    except Exception as e:
        print(f"⚠️ خطأ في التنظيف: {e}")
