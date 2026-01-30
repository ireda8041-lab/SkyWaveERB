# الملف: core/error_handler_v2.py
"""
🛡️ معالج الأخطاء المحسّن (Error Handler V2)
يوفر معالجة احترافية للأخطاء مع:
- تصنيف الأخطاء
- تسجيل مفصل
- استرداد ذكي
- إشعارات للمستخدم
"""

from __future__ import annotations

import functools
import sys
import threading
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Callable, TypeVar

from core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class ErrorSeverity(Enum):
    """مستوى خطورة الخطأ"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """تصنيف الخطأ"""
    DATABASE = "database"
    NETWORK = "network"
    SYNC = "sync"
    UI = "ui"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


class AppError(Exception):
    """
    خطأ تطبيق مخصص مع معلومات إضافية
    
    Attributes:
        message: رسالة الخطأ
        category: تصنيف الخطأ
        severity: مستوى الخطورة
        details: تفاصيل إضافية
        recoverable: هل يمكن الاسترداد
    """
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
        original_error: Exception | None = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.recoverable = recoverable
        self.original_error = original_error
        self.timestamp = datetime.now()
        self.thread_name = threading.current_thread().name
    
    def to_dict(self) -> dict[str, Any]:
        """تحويل الخطأ لـ dict"""
        return {
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value,
            'details': self.details,
            'recoverable': self.recoverable,
            'timestamp': self.timestamp.isoformat(),
            'thread': self.thread_name,
            'original_error': str(self.original_error) if self.original_error else None
        }
    
    def __str__(self) -> str:
        return f"[{self.category.value}] {self.message}"


class DatabaseError(AppError):
    """خطأ قاعدة البيانات"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.DATABASE,
            **kwargs
        )


class NetworkError(AppError):
    """خطأ الشبكة"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            **kwargs
        )


class SyncError(AppError):
    """خطأ المزامنة"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.SYNC,
            **kwargs
        )


class ValidationError(AppError):
    """خطأ التحقق"""
    
    def __init__(self, message: str, field: str | None = None, **kwargs):
        details = kwargs.pop('details', {})
        if field:
            details['field'] = field
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.WARNING,
            details=details,
            **kwargs
        )


class ErrorHandlerV2:
    """
    معالج الأخطاء المركزي
    
    يوفر:
    - تسجيل مركزي للأخطاء
    - تصنيف تلقائي
    - إحصائيات الأخطاء
    - استرداد ذكي
    
    الاستخدام:
        # معالجة خطأ
        error_handler.handle(exception, context="sync_operation")
        
        # تسجيل خطأ مخصص
        error_handler.log_error(
            "فشل الاتصال بقاعدة البيانات",
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.ERROR
        )
        
        # decorator للدوال
        @error_handler.catch_errors(default_return=[])
        def get_clients():
            ...
    """
    
    _instance: ErrorHandlerV2 | None = None
    _lock = threading.Lock()
    
    # أخطاء Qt التي يمكن تجاهلها
    IGNORABLE_PATTERNS = [
        "wrapped c/c++ object",
        "deleted",
        "destroyed",
        "qobject",
        "runtime error",
        "c/c++ object",
    ]
    
    def __new__(cls) -> ErrorHandlerV2:
        """Singleton pattern"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._error_counts: dict[str, int] = {}
        self._recent_errors: list[dict] = []
        self._max_recent = 100
        self._errors_lock = threading.RLock()
        self._initialized = True
        
        logger.info("✅ تم تهيئة ErrorHandlerV2")
    
    def handle(
        self,
        error: Exception,
        context: str = "",
        reraise: bool = False,
        notify_user: bool = False
    ) -> AppError | None:
        """
        معالجة خطأ
        
        Args:
            error: الخطأ
            context: سياق الخطأ
            reraise: إعادة رفع الخطأ
            notify_user: إشعار المستخدم
            
        Returns:
            AppError مع التفاصيل
        """
        # تحويل لـ AppError إذا لم يكن
        if isinstance(error, AppError):
            app_error = error
        else:
            app_error = self._classify_error(error, context)
        
        # تسجيل الخطأ
        self._log_error(app_error, context)
        
        # إشعار المستخدم إذا مطلوب
        if notify_user and not self._is_ignorable(str(error)):
            self._notify_user(app_error)
        
        # إعادة الرفع إذا مطلوب
        if reraise:
            raise app_error
        
        return app_error
    
    def _classify_error(self, error: Exception, context: str) -> AppError:
        """تصنيف الخطأ تلقائياً"""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # تصنيف حسب نوع الخطأ
        if "sqlite" in error_str or "database" in error_str:
            return DatabaseError(
                str(error),
                original_error=error,
                details={'context': context, 'type': error_type}
            )
        
        if "connection" in error_str or "network" in error_str or "timeout" in error_str:
            return NetworkError(
                str(error),
                original_error=error,
                details={'context': context, 'type': error_type}
            )
        
        if "sync" in error_str or "mongo" in error_str:
            return SyncError(
                str(error),
                original_error=error,
                details={'context': context, 'type': error_type}
            )
        
        if "validation" in error_str or "invalid" in error_str:
            return ValidationError(
                str(error),
                original_error=error,
                details={'context': context, 'type': error_type}
            )
        
        # خطأ عام
        return AppError(
            str(error),
            original_error=error,
            details={'context': context, 'type': error_type}
        )
    
    def _log_error(self, error: AppError, context: str):
        """تسجيل الخطأ"""
        # تسجيل في الـ logger
        log_message = f"[{error.category.value}] {context}: {error.message}"
        
        if error.severity == ErrorSeverity.DEBUG:
            logger.debug(log_message)
        elif error.severity == ErrorSeverity.INFO:
            logger.info(log_message)
        elif error.severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        elif error.severity == ErrorSeverity.ERROR:
            logger.error(log_message, exc_info=error.original_error)
        elif error.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, exc_info=error.original_error)
        
        # تخزين في القائمة
        with self._errors_lock:
            # تحديث العداد
            key = f"{error.category.value}:{error.severity.value}"
            self._error_counts[key] = self._error_counts.get(key, 0) + 1
            
            # إضافة للقائمة الأخيرة
            self._recent_errors.append({
                **error.to_dict(),
                'context': context
            })
            
            # الحفاظ على الحد الأقصى
            if len(self._recent_errors) > self._max_recent:
                self._recent_errors = self._recent_errors[-self._max_recent:]
    
    def _is_ignorable(self, error_str: str) -> bool:
        """التحقق من إمكانية تجاهل الخطأ"""
        error_lower = error_str.lower()
        return any(pattern in error_lower for pattern in self.IGNORABLE_PATTERNS)
    
    def _notify_user(self, error: AppError):
        """إشعار المستخدم بالخطأ"""
        try:
            from ui.notification_system import notify_error
            notify_error(error.message, "خطأ")
        except ImportError:
            pass  # نظام الإشعارات غير متاح
    
    def log_error(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: str = "",
        details: dict | None = None
    ):
        """
        تسجيل خطأ مخصص
        
        Args:
            message: رسالة الخطأ
            category: تصنيف الخطأ
            severity: مستوى الخطورة
            context: سياق الخطأ
            details: تفاصيل إضافية
        """
        error = AppError(
            message,
            category=category,
            severity=severity,
            details=details or {}
        )
        self._log_error(error, context)
    
    def catch_errors(
        self,
        default_return: Any = None,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        reraise: bool = False,
        notify_user: bool = False
    ) -> Callable:
        """
        Decorator لالتقاط الأخطاء
        
        Args:
            default_return: القيمة الافتراضية عند الخطأ
            category: تصنيف الخطأ
            reraise: إعادة رفع الخطأ
            notify_user: إشعار المستخدم
            
        Returns:
            Decorator function
            
        Example:
            @error_handler.catch_errors(default_return=[], category=ErrorCategory.DATABASE)
            def get_clients():
                return repo.get_all_clients()
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> T:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.handle(
                        e,
                        context=func.__name__,
                        reraise=reraise,
                        notify_user=notify_user
                    )
                    return default_return
            return wrapper
        return decorator
    
    def get_error_counts(self) -> dict[str, int]:
        """الحصول على عدادات الأخطاء"""
        with self._errors_lock:
            return dict(self._error_counts)
    
    def get_recent_errors(self, limit: int = 20) -> list[dict]:
        """الحصول على الأخطاء الأخيرة"""
        with self._errors_lock:
            return list(self._recent_errors[-limit:])
    
    def get_stats(self) -> dict[str, Any]:
        """الحصول على إحصائيات الأخطاء"""
        with self._errors_lock:
            total = sum(self._error_counts.values())
            by_category: dict[str, int] = {}
            by_severity: dict[str, int] = {}
            
            for key, count in self._error_counts.items():
                cat, sev = key.split(':')
                by_category[cat] = by_category.get(cat, 0) + count
                by_severity[sev] = by_severity.get(sev, 0) + count
            
            return {
                'total_errors': total,
                'by_category': by_category,
                'by_severity': by_severity,
                'recent_count': len(self._recent_errors)
            }
    
    def clear_stats(self):
        """مسح الإحصائيات"""
        with self._errors_lock:
            self._error_counts.clear()
            self._recent_errors.clear()


# Singleton instance
error_handler = ErrorHandlerV2()


def get_error_handler() -> ErrorHandlerV2:
    """الحصول على معالج الأخطاء"""
    return error_handler


def handle_error(
    error: Exception,
    context: str = "",
    reraise: bool = False
) -> AppError | None:
    """معالجة خطأ (دالة مساعدة)"""
    return error_handler.handle(error, context, reraise)


def catch_errors(**kwargs) -> Callable:
    """Decorator لالتقاط الأخطاء"""
    return error_handler.catch_errors(**kwargs)


def setup_global_exception_handler():
    """
    إعداد معالج الأخطاء العام
    يلتقط الأخطاء غير المعالجة في التطبيق
    """
    def exception_hook(exc_type, exc_value, exc_traceback):
        """معالج الأخطاء غير المتوقعة"""
        # تجاهل KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # معالجة الخطأ
        error_handler.handle(
            exc_value,
            context="uncaught_exception",
            notify_user=True
        )
        
        # تسجيل الـ traceback الكامل
        logger.critical(
            f"خطأ غير متوقع: {exc_type.__name__}: {exc_value}",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    sys.excepthook = exception_hook
    logger.info("✅ تم إعداد معالج الأخطاء العام")
