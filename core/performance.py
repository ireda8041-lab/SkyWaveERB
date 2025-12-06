# الملف: core/performance.py
"""
أدوات قياس الأداء (Performance Profiling)
توفر أدوات لقياس وتحليل أداء التطبيق
"""

import functools
import statistics
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Optional

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetric:
    """
    مقياس أداء واحد

    Attributes:
        name: اسم العملية
        duration: مدة التنفيذ بالثواني
        timestamp: وقت التنفيذ
        success: هل نجحت العملية؟
        metadata: بيانات إضافية
    """
    name: str
    duration: float
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceStats:
    """
    إحصائيات الأداء

    Attributes:
        name: اسم العملية
        count: عدد التنفيذات
        total_time: إجمالي الوقت
        min_time: أقل وقت
        max_time: أعلى وقت
        avg_time: متوسط الوقت
        std_dev: الانحراف المعياري
        success_rate: نسبة النجاح
    """
    name: str
    count: int
    total_time: float
    min_time: float
    max_time: float
    avg_time: float
    std_dev: float
    success_rate: float


class PerformanceProfiler:
    """
    أداة قياس الأداء الرئيسية

    توفر:
    - قياس وقت تنفيذ الدوال
    - تجميع الإحصائيات
    - تقارير الأداء
    - تنبيهات الأداء البطيء
    """

    _instance: Optional['PerformanceProfiler'] = None
    _lock = Lock()

    def __new__(cls) -> 'PerformanceProfiler':
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._metrics: dict[str, list[PerformanceMetric]] = {}
        self._slow_threshold: float = 1.0  # ثانية واحدة
        self._enabled: bool = True
        self._max_metrics_per_operation: int = 1000
        self._lock = Lock()
        self._initialized = True

        logger.info("تم تهيئة PerformanceProfiler")

    @property
    def enabled(self) -> bool:
        """هل القياس مُفعّل؟"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """تفعيل/تعطيل القياس"""
        self._enabled = value
        logger.info(f"تم {'تفعيل' if value else 'تعطيل'} قياس الأداء")

    @property
    def slow_threshold(self) -> float:
        """عتبة الأداء البطيء بالثواني"""
        return self._slow_threshold

    @slow_threshold.setter
    def slow_threshold(self, value: float) -> None:
        """تعيين عتبة الأداء البطيء"""
        self._slow_threshold = value

    def record_metric(self, metric: PerformanceMetric) -> None:
        """
        تسجيل مقياس أداء

        Args:
            metric: مقياس الأداء
        """
        if not self._enabled:
            return

        with self._lock:
            if metric.name not in self._metrics:
                self._metrics[metric.name] = []

            # الحفاظ على حد أقصى للمقاييس
            if len(self._metrics[metric.name]) >= self._max_metrics_per_operation:
                self._metrics[metric.name] = self._metrics[metric.name][-500:]

            self._metrics[metric.name].append(metric)

        # تنبيه إذا كان الأداء بطيئاً
        if metric.duration > self._slow_threshold:
            logger.warning(
                f"⚠️ أداء بطيء: {metric.name} استغرق {metric.duration:.3f} ثانية"
            )

    @contextmanager
    def measure(self, operation_name: str, **metadata):
        """
        Context manager لقياس وقت التنفيذ

        الاستخدام:
        with profiler.measure("create_project"):
            # الكود هنا

        Args:
            operation_name: اسم العملية
            **metadata: بيانات إضافية
        """
        if not self._enabled:
            yield
            return

        start_time = time.perf_counter()
        success = True

        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration = time.perf_counter() - start_time

            metric = PerformanceMetric(
                name=operation_name,
                duration=duration,
                success=success,
                metadata=metadata
            )

            self.record_metric(metric)

    def get_stats(self, operation_name: str) -> PerformanceStats | None:
        """
        الحصول على إحصائيات عملية معينة

        Args:
            operation_name: اسم العملية

        Returns:
            إحصائيات الأداء أو None
        """
        with self._lock:
            metrics = self._metrics.get(operation_name, [])

        if not metrics:
            return None

        durations = [m.duration for m in metrics]
        success_count = sum(1 for m in metrics if m.success)

        return PerformanceStats(
            name=operation_name,
            count=len(metrics),
            total_time=sum(durations),
            min_time=min(durations),
            max_time=max(durations),
            avg_time=statistics.mean(durations),
            std_dev=statistics.stdev(durations) if len(durations) > 1 else 0.0,
            success_rate=success_count / len(metrics) * 100
        )

    def get_all_stats(self) -> dict[str, PerformanceStats]:
        """
        الحصول على إحصائيات جميع العمليات

        Returns:
            قاموس بإحصائيات كل عملية
        """
        with self._lock:
            operation_names = list(self._metrics.keys())

        stats = {}
        for name in operation_names:
            stat = self.get_stats(name)
            if stat:
                stats[name] = stat

        return stats

    def get_slowest_operations(self, limit: int = 10) -> list[PerformanceStats]:
        """
        الحصول على أبطأ العمليات

        Args:
            limit: عدد العمليات

        Returns:
            قائمة بأبطأ العمليات
        """
        all_stats = self.get_all_stats()
        sorted_stats = sorted(
            all_stats.values(),
            key=lambda s: s.avg_time,
            reverse=True
        )
        return sorted_stats[:limit]

    def get_report(self) -> str:
        """
        إنشاء تقرير أداء نصي

        Returns:
            تقرير الأداء
        """
        all_stats = self.get_all_stats()

        if not all_stats:
            return "لا توجد بيانات أداء مسجلة"

        lines = [
            "=" * 80,
            "تقرير الأداء - Sky Wave ERP",
            f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 80,
            "",
            f"{'العملية':<30} {'العدد':>8} {'المتوسط':>10} {'الأدنى':>10} {'الأعلى':>10} {'النجاح':>8}",
            "-" * 80
        ]

        for name, stats in sorted(all_stats.items(), key=lambda x: x[1].avg_time, reverse=True):
            lines.append(
                f"{name:<30} {stats.count:>8} {stats.avg_time:>10.3f}s {stats.min_time:>10.3f}s {stats.max_time:>10.3f}s {stats.success_rate:>7.1f}%"
            )

        lines.extend([
            "-" * 80,
            f"إجمالي العمليات: {sum(s.count for s in all_stats.values())}",
            f"إجمالي الوقت: {sum(s.total_time for s in all_stats.values()):.2f} ثانية",
            "=" * 80
        ])

        return "\n".join(lines)

    def clear(self) -> None:
        """مسح جميع المقاييس"""
        with self._lock:
            self._metrics.clear()
        logger.info("تم مسح بيانات الأداء")

    def export_to_dict(self) -> dict[str, Any]:
        """
        تصدير البيانات كـ dictionary

        Returns:
            بيانات الأداء
        """
        all_stats = self.get_all_stats()

        return {
            "timestamp": datetime.now().isoformat(),
            "operations": {
                name: {
                    "count": stats.count,
                    "total_time": stats.total_time,
                    "min_time": stats.min_time,
                    "max_time": stats.max_time,
                    "avg_time": stats.avg_time,
                    "std_dev": stats.std_dev,
                    "success_rate": stats.success_rate
                }
                for name, stats in all_stats.items()
            }
        }


# --- Decorators ---

def profile(operation_name: str | None = None):
    """
    Decorator لقياس أداء الدوال

    الاستخدام:
    @profile("create_project")
    def create_project(self, data):
        # الكود هنا

    أو:
    @profile()  # سيستخدم اسم الدالة
    def create_project(self, data):
        # الكود هنا

    Args:
        operation_name: اسم العملية (اختياري)
    """
    def decorator(func: Callable) -> Callable:
        name = operation_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profiler = PerformanceProfiler()

            with profiler.measure(name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def profile_async(operation_name: str | None = None):
    """
    Decorator لقياس أداء الدوال غير المتزامنة

    Args:
        operation_name: اسم العملية (اختياري)
    """
    def decorator(func: Callable) -> Callable:
        name = operation_name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            profiler = PerformanceProfiler()

            start_time = time.perf_counter()
            success = True

            try:
                return await func(*args, **kwargs)
            except Exception:
                success = False
                raise
            finally:
                duration = time.perf_counter() - start_time

                metric = PerformanceMetric(
                    name=name,
                    duration=duration,
                    success=success
                )

                profiler.record_metric(metric)

        return wrapper

    return decorator


# --- دوال مساعدة ---

def get_profiler() -> PerformanceProfiler:
    """الحصول على instance من PerformanceProfiler"""
    return PerformanceProfiler()


def measure_time(operation_name: str, **metadata):
    """
    Context manager مختصر لقياس الوقت

    الاستخدام:
    with measure_time("my_operation"):
        # الكود هنا
    """
    return get_profiler().measure(operation_name, **metadata)


def print_performance_report() -> None:
    """طباعة تقرير الأداء"""
    profiler = get_profiler()
    print(profiler.get_report())


# --- اختبار ---
if __name__ == "__main__":
    print("--- اختبار أدوات قياس الأداء ---\n")

    profiler = get_profiler()

    # اختبار Context Manager
    with profiler.measure("test_operation"):
        time.sleep(0.1)

    # اختبار Decorator
    @profile("decorated_function")
    def slow_function():
        time.sleep(0.2)
        return "done"

    for _ in range(5):
        slow_function()

    # اختبار عملية سريعة
    @profile()
    def fast_function():
        return sum(range(1000))

    for _ in range(100):
        fast_function()

    # طباعة التقرير
    print_performance_report()

    # تصدير البيانات
    data = profiler.export_to_dict()
    print(f"\nعدد العمليات المسجلة: {len(data['operations'])}")

    print("\n--- انتهى الاختبار ---")
