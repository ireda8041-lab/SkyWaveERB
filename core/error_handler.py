# الملف: core/error_handler.py
# نظام معالجة الأخطاء المركزي

import logging
import traceback
from datetime import datetime

from PyQt6.QtWidgets import QMessageBox

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class ErrorHandler:
    """
    معالج مركزي للأخطاء في نظام Sky Wave ERP.
    يوفر معالجة موحدة للأخطاء مع رسائل عربية واضحة.
    """

    # قاموس رسائل الأخطاء المترجمة
    ERROR_MESSAGES: dict[str, str] = {
        # أخطاء الاتصال
        "ConnectionError": "فشل الاتصال بالإنترنت. يرجى التحقق من الاتصال والمحاولة مرة أخرى.",
        "ServerSelectionTimeoutError": "تعذر الاتصال بقاعدة البيانات. يرجى التحقق من الاتصال بالإنترنت.",
        "NetworkTimeout": "انتهت مهلة الاتصال. يرجى المحاولة مرة أخرى.",

        # أخطاء البيانات
        "ValidationError": "البيانات المدخلة غير صحيحة. يرجى مراجعة المدخلات والمحاولة مرة أخرى.",
        "DuplicateKeyError": "هذا السجل موجود بالفعل. يرجى استخدام قيم مختلفة.",
        "E11000": "هذا السجل موجود بالفعل في قاعدة البيانات.",
        "IntegrityError": "تعارض في البيانات. يرجى التحقق من صحة المدخلات.",

        # أخطاء الصلاحيات
        "PermissionError": "ليس لديك صلاحية لتنفيذ هذا الإجراء.",
        "AuthenticationError": "فشل التحقق من الهوية. يرجى تسجيل الدخول مرة أخرى.",

        # أخطاء الملفات
        "FileNotFoundError": "الملف المطلوب غير موجود.",
        "IOError": "خطأ في قراءة أو كتابة الملف.",

        # أخطاء عامة
        "ValueError": "قيمة غير صالحة. يرجى التحقق من المدخلات.",
        "TypeError": "نوع بيانات غير صحيح.",
        "KeyError": "البيانات المطلوبة غير موجودة.",
        "AttributeError": "خطأ في الوصول للبيانات.",
    }

    # الأخطاء الحرجة التي تحتاج إشعار المطور
    CRITICAL_ERRORS = [
        "DatabaseError",
        "SystemError",
        "MemoryError",
        "RuntimeError",
    ]

    @staticmethod
    def handle_exception(
        exception: Exception,
        context: str,
        user_message: str | None = None,
        show_dialog: bool = True,
        log_level: str = "ERROR"
    ) -> None:
        """
        معالجة الأخطاء بشكل موحد.

        Args:
            exception: الخطأ الذي حدث
            context: السياق (مثل: "create_project", "save_client")
            user_message: رسالة مخصصة للمستخدم (اختياري)
            show_dialog: هل نعرض نافذة منبثقة؟
            log_level: مستوى التسجيل (ERROR, WARNING, INFO)
        """
        # 1. تسجيل الخطأ في الـ Log
        ErrorHandler._log_error(exception, context, log_level)

        # 2. إرسال إشعار للمطور (للأخطاء الحرجة)
        if ErrorHandler._is_critical(exception):
            ErrorHandler._notify_developer(exception, context)

        # 3. عرض رسالة للمستخدم
        if show_dialog:
            ErrorHandler._show_user_dialog(exception, user_message, context)

    @staticmethod
    def _log_error(exception: Exception, context: str, log_level: str = "ERROR") -> None:
        """تسجيل الخطأ في ملف الـ Log"""
        logger = logging.getLogger("SkyWaveERP")

        error_details = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "traceback": traceback.format_exc()
        }

        log_message = (
            f"\n{'='*80}\n"
            f"Context: {error_details['context']}\n"
            f"Exception: {error_details['exception_type']}\n"
            f"Message: {error_details['exception_message']}\n"
            f"Timestamp: {error_details['timestamp']}\n"
            f"Traceback:\n{error_details['traceback']}"
            f"{'='*80}\n"
        )

        if log_level == "ERROR":
            logger.error(log_message)
        elif log_level == "WARNING":
            logger.warning(log_message)
        else:
            logger.info(log_message)

    @staticmethod
    def _is_critical(exception: Exception) -> bool:
        """التحقق من أن الخطأ حرج"""
        exception_type = type(exception).__name__
        return exception_type in ErrorHandler.CRITICAL_ERRORS

    @staticmethod
    def _notify_developer(exception: Exception, context: str) -> None:
        """إرسال إشعار للمطور (للأخطاء الحرجة)"""
        # إرسال إشعار للمطور (يمكن إضافة إيميل أو Slack لاحقاً)
        logger = logging.getLogger("SkyWaveERP")
        logger.critical(
            f"CRITICAL ERROR in {context}: {type(exception).__name__} - {str(exception)}"
        )
        safe_print(f"⚠️ CRITICAL ERROR: {type(exception).__name__} in {context}")

    @staticmethod
    def _show_user_dialog(
        exception: Exception,
        user_message: str | None,
        context: str
    ) -> None:
        """عرض نافذة منبثقة للمستخدم"""
        try:
            # الحصول على الرسالة المناسبة
            if user_message:
                message = user_message
            else:
                message = ErrorHandler._get_user_friendly_message(exception)

            # إضافة معلومات إضافية للمطورين (في وضع Debug)

            # عرض النافذة
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("خطأ")
            msg_box.setText(message)
            msg_box.setDetailedText(
                f"Context: {context}\n"
                f"Exception: {type(exception).__name__}\n"
                f"Details: {str(exception)}"
            )
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()

        except Exception as e:
            # في حالة فشل عرض النافذة، نطبع في الكونسول
            safe_print(f"ERROR: فشل عرض رسالة الخطأ: {e}")
            safe_print(f"Original Error: {exception}")

    @staticmethod
    def _get_user_friendly_message(exception: Exception) -> str:
        """تحويل الأخطاء التقنية لرسائل مفهومة"""
        exception_type = type(exception).__name__
        exception_message = str(exception)

        # البحث عن رسالة مطابقة في القاموس
        for key, message in ErrorHandler.ERROR_MESSAGES.items():
            if key in exception_type or key in exception_message:
                return message

        # رسالة افتراضية
        return (
            "حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.\n"
            "إذا استمرت المشكلة، يرجى التواصل مع الدعم الفني."
        )

    @staticmethod
    def handle_warning(
        message: str,
        context: str,
        show_dialog: bool = True
    ) -> None:
        """
        معالجة التحذيرات (Warnings).

        Args:
            message: رسالة التحذير
            context: السياق
            show_dialog: هل نعرض نافذة منبثقة؟
        """
        logger = logging.getLogger("SkyWaveERP")
        logger.warning(f"[{context}] {message}")

        if show_dialog:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("تحذير")
            msg_box.setText(message)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()

    @staticmethod
    def handle_info(
        message: str,
        context: str,
        show_dialog: bool = False
    ) -> None:
        """
        معالجة الرسائل المعلوماتية (Info).

        Args:
            message: الرسالة المعلوماتية
            context: السياق
            show_dialog: هل نعرض نافذة منبثقة؟
        """
        logger = logging.getLogger("SkyWaveERP")
        logger.info(f"[{context}] {message}")

        if show_dialog:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setWindowTitle("معلومة")
            msg_box.setText(message)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()


# --- Decorator للاستخدام السهل ---
def handle_errors(context: str, show_dialog: bool = True):
    """
    Decorator لمعالجة الأخطاء تلقائياً.

    الاستخدام:
    @handle_errors("create_project")
    def create_project(self, data):
        # الكود هنا
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                ErrorHandler.handle_exception(
                    exception=e,
                    context=context,
                    show_dialog=show_dialog
                )
                return None
        return wrapper
    return decorator


# --- اختبار ---
if __name__ == "__main__":
    # إعداد Logger للاختبار
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    safe_print("--- اختبار ErrorHandler ---\n")

    # اختبار 1: خطأ اتصال
    try:
        raise ConnectionError("Failed to connect to database")
    except Exception as e:
        ErrorHandler.handle_exception(e, "test_connection", show_dialog=False)

    # اختبار 2: خطأ بيانات مكررة
    try:
        raise ValueError("E11000 duplicate key error")
    except Exception as e:
        ErrorHandler.handle_exception(e, "test_duplicate", show_dialog=False)

    # اختبار 3: خطأ حرج
    try:
        raise RuntimeError("Critical system error")
    except Exception as e:
        ErrorHandler.handle_exception(e, "test_critical", show_dialog=False)

    safe_print("\n--- انتهى الاختبار ---")
