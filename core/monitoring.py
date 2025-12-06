# الملف: core/monitoring.py
"""
نظام المراقبة والتنبيهات - Monitoring & Alerting System
"""

import statistics
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """أنواع المقاييس"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertSeverity(Enum):
    """مستويات خطورة التنبيهات"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Metric:
    """مقياس أداء"""
    name: str
    type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """تنبيه"""
    name: str
    message: str
    severity: AlertSeverity
    timestamp: datetime = field(default_factory=datetime.now)
    metric_name: str | None = None
    metric_value: float | None = None
    resolved: bool = False


class MetricsCollector:
    """
    جامع المقاييس
    يجمع ويخزن مقاييس الأداء
    """

    def __init__(self, max_history: int = 1000):
        """
        تهيئة جامع المقاييس

        Args:
            max_history: الحد الأقصى لتاريخ المقاييس
        """
        self.metrics: dict[str, deque] = {}
        self.max_history = max_history
        self._lock = threading.Lock()

        logger.info("تم تهيئة MetricsCollector")

    def record(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: dict[str, str] | None = None
    ) -> None:
        """
        تسجيل مقياس

        Args:
            name: اسم المقياس
            value: القيمة
            metric_type: نوع المقياس
            labels: تسميات إضافية
        """
        metric = Metric(
            name=name,
            type=metric_type,
            value=value,
            labels=labels or {}
        )

        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = deque(maxlen=self.max_history)

            self.metrics[name].append(metric)

        logger.debug(f"تم تسجيل مقياس: {name} = {value}")

    def increment(self, name: str, amount: float = 1.0) -> None:
        """
        زيادة عداد

        Args:
            name: اسم العداد
            amount: مقدار الزيادة
        """
        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = deque(maxlen=self.max_history)

            current = self.metrics[name][-1].value if self.metrics[name] else 0

        self.record(name, current + amount, MetricType.COUNTER)

    def get_latest(self, name: str) -> Metric | None:
        """
        الحصول على آخر قيمة لمقياس

        Args:
            name: اسم المقياس

        Returns:
            آخر مقياس أو None
        """
        with self._lock:
            if name in self.metrics and self.metrics[name]:
                result: Metric = self.metrics[name][-1]
                return result
        return None

    def get_history(
        self,
        name: str,
        since: datetime | None = None
    ) -> list[Metric]:
        """
        الحصول على تاريخ مقياس

        Args:
            name: اسم المقياس
            since: من تاريخ معين

        Returns:
            قائمة المقاييس
        """
        with self._lock:
            if name not in self.metrics:
                return []

            metrics = list(self.metrics[name])

            if since:
                metrics = [m for m in metrics if m.timestamp >= since]

            return metrics

    def get_statistics(self, name: str, window_minutes: int = 5) -> dict[str, float]:
        """
        الحصول على إحصائيات مقياس

        Args:
            name: اسم المقياس
            window_minutes: نافذة الوقت بالدقائق

        Returns:
            إحصائيات المقياس
        """
        since = datetime.now() - timedelta(minutes=window_minutes)
        history = self.get_history(name, since)

        if not history:
            return {}

        values = [m.value for m in history]

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": statistics.mean(values),
            "median": statistics.median(values),
            "stddev": statistics.stdev(values) if len(values) > 1 else 0
        }

    def get_all_metrics(self) -> dict[str, Any]:
        """
        الحصول على جميع المقاييس الحالية

        Returns:
            قاموس بجميع المقاييس
        """
        result = {}

        with self._lock:
            for name, metrics in self.metrics.items():
                if metrics:
                    latest = metrics[-1]
                    result[name] = {
                        "value": latest.value,
                        "type": latest.type.value,
                        "timestamp": latest.timestamp.isoformat(),
                        "labels": latest.labels
                    }

        return result


class AlertManager:
    """
    مدير التنبيهات
    يدير إنشاء وإرسال التنبيهات
    """

    def __init__(self):
        """تهيئة مدير التنبيهات"""
        self.alerts: list[Alert] = []
        self.handlers: list[Callable[[Alert], None]] = []
        self._lock = threading.Lock()

        logger.info("تم تهيئة AlertManager")

    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """
        إضافة معالج تنبيهات

        Args:
            handler: دالة معالجة التنبيه
        """
        self.handlers.append(handler)

    def fire(
        self,
        name: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        metric_name: str | None = None,
        metric_value: float | None = None
    ) -> Alert:
        """
        إطلاق تنبيه

        Args:
            name: اسم التنبيه
            message: رسالة التنبيه
            severity: مستوى الخطورة
            metric_name: اسم المقياس المرتبط
            metric_value: قيمة المقياس

        Returns:
            التنبيه المنشأ
        """
        alert = Alert(
            name=name,
            message=message,
            severity=severity,
            metric_name=metric_name,
            metric_value=metric_value
        )

        with self._lock:
            self.alerts.append(alert)

        # تنفيذ المعالجات
        for handler in self.handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"فشل معالج التنبيه: {e}")

        logger.warning(f"تنبيه [{severity.value}]: {name} - {message}")

        return alert

    def resolve(self, alert_name: str) -> bool:
        """
        حل تنبيه

        Args:
            alert_name: اسم التنبيه

        Returns:
            True إذا تم الحل
        """
        with self._lock:
            for alert in reversed(self.alerts):
                if alert.name == alert_name and not alert.resolved:
                    alert.resolved = True
                    logger.info(f"تم حل التنبيه: {alert_name}")
                    return True
        return False

    def get_active_alerts(self) -> list[Alert]:
        """
        الحصول على التنبيهات النشطة

        Returns:
            قائمة التنبيهات غير المحلولة
        """
        with self._lock:
            return [a for a in self.alerts if not a.resolved]

    def get_alerts_by_severity(self, severity: AlertSeverity) -> list[Alert]:
        """
        الحصول على التنبيهات حسب الخطورة

        Args:
            severity: مستوى الخطورة

        Returns:
            قائمة التنبيهات
        """
        with self._lock:
            return [a for a in self.alerts if a.severity == severity]


class HealthChecker:
    """
    فاحص الصحة
    يفحص صحة مكونات النظام
    """

    def __init__(self):
        """تهيئة فاحص الصحة"""
        self.checks: dict[str, Callable[[], bool]] = {}
        self.last_results: dict[str, bool] = {}

        logger.info("تم تهيئة HealthChecker")

    def register_check(self, name: str, check_func: Callable[[], bool]) -> None:
        """
        تسجيل فحص صحة

        Args:
            name: اسم الفحص
            check_func: دالة الفحص
        """
        self.checks[name] = check_func
        logger.debug(f"تم تسجيل فحص صحة: {name}")

    def run_check(self, name: str) -> bool:
        """
        تشغيل فحص معين

        Args:
            name: اسم الفحص

        Returns:
            نتيجة الفحص
        """
        if name not in self.checks:
            logger.warning(f"فحص غير موجود: {name}")
            return False

        try:
            result = self.checks[name]()
            self.last_results[name] = result
            return result
        except Exception as e:
            logger.error(f"فشل فحص {name}: {e}")
            self.last_results[name] = False
            return False

    def run_all_checks(self) -> dict[str, bool]:
        """
        تشغيل جميع الفحوصات

        Returns:
            نتائج جميع الفحوصات
        """
        results = {}

        for name in self.checks:
            results[name] = self.run_check(name)

        return results

    def is_healthy(self) -> bool:
        """
        التحقق من صحة النظام الكلية

        Returns:
            True إذا كانت جميع الفحوصات ناجحة
        """
        results = self.run_all_checks()
        return all(results.values())

    def get_health_status(self) -> dict[str, Any]:
        """
        الحصول على حالة الصحة الكاملة

        Returns:
            حالة الصحة
        """
        results = self.run_all_checks()

        return {
            "status": "healthy" if all(results.values()) else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "checks": results
        }


class PerformanceMonitor:
    """
    مراقب الأداء
    يراقب أداء التطبيق ويطلق تنبيهات
    """

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        alert_manager: AlertManager
    ):
        """
        تهيئة مراقب الأداء

        Args:
            metrics_collector: جامع المقاييس
            alert_manager: مدير التنبيهات
        """
        self.metrics = metrics_collector
        self.alerts = alert_manager
        self.thresholds: dict[str, dict[str, float]] = {}
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None

        logger.info("تم تهيئة PerformanceMonitor")

    def set_threshold(
        self,
        metric_name: str,
        warning: float | None = None,
        critical: float | None = None
    ) -> None:
        """
        تعيين حدود التنبيه لمقياس

        Args:
            metric_name: اسم المقياس
            warning: حد التحذير
            critical: حد الخطورة
        """
        self.thresholds[metric_name] = {
            "warning": warning or 0.0,
            "critical": critical or 0.0
        }

        logger.debug(f"تم تعيين حدود لـ {metric_name}: warning={warning}, critical={critical}")

    def check_thresholds(self) -> None:
        """فحص الحدود وإطلاق التنبيهات"""
        for metric_name, thresholds in self.thresholds.items():
            latest = self.metrics.get_latest(metric_name)

            if not latest:
                continue

            value = latest.value

            # فحص الحد الحرج
            if thresholds.get("critical") and value >= thresholds["critical"]:
                self.alerts.fire(
                    name=f"{metric_name}_critical",
                    message=f"المقياس {metric_name} تجاوز الحد الحرج: {value} >= {thresholds['critical']}",
                    severity=AlertSeverity.CRITICAL,
                    metric_name=metric_name,
                    metric_value=value
                )
            # فحص حد التحذير
            elif thresholds.get("warning") and value >= thresholds["warning"]:
                self.alerts.fire(
                    name=f"{metric_name}_warning",
                    message=f"المقياس {metric_name} تجاوز حد التحذير: {value} >= {thresholds['warning']}",
                    severity=AlertSeverity.WARNING,
                    metric_name=metric_name,
                    metric_value=value
                )

    def start_monitoring(self, interval_seconds: int = 60) -> None:
        """
        بدء المراقبة الدورية

        Args:
            interval_seconds: فترة الفحص بالثواني
        """
        if self._monitoring:
            return

        self._monitoring = True

        def monitor_loop():
            while self._monitoring:
                self.check_thresholds()
                time.sleep(interval_seconds)

        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info(f"بدأت المراقبة الدورية كل {interval_seconds} ثانية")

    def stop_monitoring(self) -> None:
        """إيقاف المراقبة"""
        self._monitoring = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

        logger.info("تم إيقاف المراقبة")


# --- Singleton instances ---

_metrics_collector: MetricsCollector | None = None
_alert_manager: AlertManager | None = None
_health_checker: HealthChecker | None = None
_performance_monitor: PerformanceMonitor | None = None


def get_metrics_collector() -> MetricsCollector:
    """الحصول على جامع المقاييس"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_alert_manager() -> AlertManager:
    """الحصول على مدير التنبيهات"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def get_health_checker() -> HealthChecker:
    """الحصول على فاحص الصحة"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def get_performance_monitor() -> PerformanceMonitor:
    """الحصول على مراقب الأداء"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor(
            get_metrics_collector(),
            get_alert_manager()
        )
    return _performance_monitor


# --- Decorators ---

def timed(metric_name: str):
    """
    Decorator لقياس وقت تنفيذ الدالة

    Args:
        metric_name: اسم المقياس
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - start) * 1000  # بالميلي ثانية
                get_metrics_collector().record(
                    metric_name,
                    elapsed,
                    MetricType.TIMER
                )
        return wrapper
    return decorator


def counted(metric_name: str):
    """
    Decorator لعد استدعاءات الدالة

    Args:
        metric_name: اسم المقياس
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            get_metrics_collector().increment(metric_name)
            return func(*args, **kwargs)
        return wrapper
    return decorator
