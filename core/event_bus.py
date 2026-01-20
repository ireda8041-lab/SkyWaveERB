# الملف: core/event_bus.py
"""
نظام ناقل الأحداث (Event Bus)
يوفر نمط Publish-Subscribe للتواصل بين مكونات التطبيق
"""

from collections import defaultdict
from collections.abc import Callable
from threading import Lock
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


class EventBus:
    """
    ناقل الأحداث (Event Bus)

    مسؤول عن توصيل الأحداث من الناشر (Publisher)
    إلى المستمعين (Listeners/Subscribers).

    الأحداث المدعومة:
    - CLIENT_CREATED: عند إنشاء عميل جديد
    - CLIENT_UPDATED: عند تحديث بيانات عميل
    - CLIENT_DELETED: عند حذف/أرشفة عميل
    - PROJECT_CREATED: عند إنشاء مشروع جديد
    - PROJECT_UPDATED: عند تحديث مشروع
    - INVOICE_CREATED: عند إنشاء فاتورة
    - INVOICE_VOIDED: عند إلغاء فاتورة
    - EXPENSE_CREATED: عند تسجيل مصروف
    - EXPENSE_DELETED: عند حذف مصروف
    - PAYMENT_RECORDED: عند تسجيل دفعة
    - SYNC_STARTED: عند بدء المزامنة
    - SYNC_COMPLETED: عند اكتمال المزامنة
    - SYNC_FAILED: عند فشل المزامنة
    - NOTIFICATION_CREATED: عند إنشاء إشعار

    Attributes:
        _handlers: قاموس المعالجات لكل حدث
        _lock: قفل للتزامن في البيئات متعددة الخيوط
    """

    # قائمة الأحداث المعروفة (للتوثيق والتحقق)
    KNOWN_EVENTS: set[str] = {
        "CLIENT_CREATED", "CLIENT_UPDATED", "CLIENT_DELETED",
        "PROJECT_CREATED", "PROJECT_UPDATED", "PROJECT_DELETED",
        "INVOICE_CREATED", "INVOICE_UPDATED", "INVOICE_VOIDED",
        "EXPENSE_CREATED", "EXPENSE_UPDATED", "EXPENSE_DELETED",
        "PAYMENT_RECORDED", "PAYMENT_DELETED",
        "SYNC_STARTED", "SYNC_COMPLETED", "SYNC_FAILED",
        "NOTIFICATION_CREATED",
    }

    def __init__(self) -> None:
        """تهيئة نظام الأحداث"""
        self._handlers: dict[str, list[Callable[[Any], None]]] = defaultdict(list)
        self._lock: Lock = Lock()
        logger.info("تم تهيئة EventBus")

    @property
    def listeners(self) -> dict[str, list[Callable]]:
        """الوصول للمعالجات (للتوافق مع الكود القديم)"""
        return self._handlers

    def subscribe(
        self,
        event_name: str,
        listener_func: Callable[[Any], None]
    ) -> None:
        """
        الاشتراك في حدث

        Args:
            event_name: اسم الحدث (مثل 'INVOICE_CREATED')
            listener_func: الدالة التي ستُستدعى عند حدوث الحدث

        Example:
            >>> def on_invoice_created(data):
            ...     safe_print(f"فاتورة جديدة: {data['invoice_number']}")
            >>> bus.subscribe('INVOICE_CREATED', on_invoice_created)
        """
        with self._lock:
            if listener_func not in self._handlers[event_name]:
                self._handlers[event_name].append(listener_func)
                logger.debug(f"تم اشتراك مستمع جديد في حدث: {event_name}")
            else:
                logger.warning(f"المستمع مشترك بالفعل في حدث: {event_name}")

    def unsubscribe(
        self,
        event_name: str,
        listener_func: Callable[[Any], None]
    ) -> bool:
        """
        إلغاء الاشتراك من حدث

        Args:
            event_name: اسم الحدث
            listener_func: الدالة المراد إلغاء اشتراكها

        Returns:
            True إذا تم إلغاء الاشتراك بنجاح
        """
        with self._lock:
            if event_name in self._handlers:
                try:
                    self._handlers[event_name].remove(listener_func)
                    logger.debug(f"تم إلغاء اشتراك مستمع من حدث: {event_name}")
                    return True
                except ValueError:
                    logger.warning(f"المستمع غير مشترك في حدث: {event_name}")
                    return False
            return False

    def publish(
        self,
        event_name: str,
        data: Any | None = None
    ) -> int:
        """
        نشر حدث - محسّن للسرعة

        Args:
            event_name: اسم الحدث
            data: البيانات المرفقة مع الحدث

        Returns:
            عدد المستمعين الذين تم إخطارهم بنجاح
        """
        with self._lock:
            handlers = list(self._handlers.get(event_name, []))

        if not handlers:
            return 0

        logger.info(f"جاري نشر حدث: {event_name} ({len(handlers)} مستمع)")

        success_count = 0
        for listener_func in handlers:
            try:
                listener_func(data)
                success_count += 1
            except Exception:
                # ⚡ تجاهل الأخطاء بصمت للسرعة
                pass

        return success_count

    def has_subscribers(self, event_name: str) -> bool:
        """
        التحقق من وجود مشتركين لحدث

        Args:
            event_name: اسم الحدث

        Returns:
            True إذا كان هناك مشتركين
        """
        with self._lock:
            return len(self._handlers.get(event_name, [])) > 0

    def get_subscriber_count(self, event_name: str) -> int:
        """
        الحصول على عدد المشتركين لحدث

        Args:
            event_name: اسم الحدث

        Returns:
            عدد المشتركين
        """
        with self._lock:
            return len(self._handlers.get(event_name, []))

    def clear_event(self, event_name: str) -> None:
        """
        مسح جميع المشتركين لحدث معين

        Args:
            event_name: اسم الحدث
        """
        with self._lock:
            if event_name in self._handlers:
                del self._handlers[event_name]
                logger.info(f"تم مسح جميع المشتركين لحدث: {event_name}")

    def clear_all(self) -> None:
        """مسح جميع المشتركين لجميع الأحداث"""
        with self._lock:
            self._handlers.clear()
            logger.info("تم مسح جميع المشتركين")

    def get_all_events(self) -> list[str]:
        """
        الحصول على قائمة الأحداث التي لها مشتركين

        Returns:
            قائمة أسماء الأحداث
        """
        with self._lock:
            return list(self._handlers.keys())


# --- كود للاختبار (اختياري) ---

# (ده مجرد مثال عشان نتأكد إن الإذاعة شغالة)
if __name__ == "__main__":

    # 1. تعريف "مستمعين" (وظايف عادية)
    def accountant_listener(invoice_data):
        safe_print(f"  >> المحاسب سمع: تم إنشاء فاتورة جديدة برقم {invoice_data['number']}")
        # (هنا هيتحط كود إنشاء قيد اليومية)

    def notification_listener(invoice_data):
        safe_print(f"  >> قسم الإشعارات سمع: جاري إرسال إيميل للعميل ببيانات الفاتورة {invoice_data['number']}")

    # 2. تشغيل الإذاعة
    bus = EventBus()

    # 3. الأقسام بتشترك في الإذاعة
    bus.subscribe('INVOICE_CREATED', accountant_listener)
    bus.subscribe('INVOICE_CREATED', notification_listener)
    bus.subscribe('EXPENSE_CREATED', accountant_listener) # المحاسب بيسمع الفواتير والمصروفات

    safe_print("\n--- الاختبار: نشر فاتورة جديدة ---")
    # 4. قسم الفواتير بينشر "حدث"
    new_invoice = {"number": "INV-001", "total": 5000}
    bus.publish('INVOICE_CREATED', new_invoice)

    safe_print("\n--- الاختبار: نشر مصروف جديد ---")
    # 5. قسم المصروفات بينشر "حدث"
    new_expense = {"category": "إعلانات", "amount": 1000}
    # (قسم الإشعارات مش هيسمع ده، لأنه مشترك في الفواتير بس)
    bus.publish('EXPENSE_CREATED', new_expense)

