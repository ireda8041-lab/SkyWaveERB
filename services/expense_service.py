# الملف: services/expense_service.py
"""
خدمة المصروفات (Expense Service)

توفر واجهة موحدة لإدارة المصروفات في النظام:
- إنشاء مصروفات جديدة
- تحديث المصروفات
- حذف المصروفات
- ربط المصروفات بالمشاريع
- إنشاء قيود محاسبية تلقائية

المؤلف: Sky Wave Team
الإصدار: 2.0.0
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from core import schemas
from core.logger import get_logger
from core.signals import app_signals

if TYPE_CHECKING:
    from core.event_bus import EventBus
    from core.repository import Repository

# استيراد دالة الإشعارات
try:
    from core.notification_bridge import notify_operation
except ImportError:

    def notify_operation(action, entity_type, entity_name):
        pass


logger = get_logger(__name__)


class ExpenseService:
    """
    ⚡ قسم المصروفات (Service Layer) - محسّن للأداء
    يحتوي على منطق العمل الخاص بإدارة المصروفات.
    """

    def __init__(self, repository: Repository, event_bus: EventBus):
        """
        تهيئة خدمة المصروفات

        Args:
            repository: مخزن البيانات الرئيسي
            event_bus: نظام الأحداث للتواصل بين الخدمات
        """
        self.repo = repository
        self.bus = event_bus

        # ⚡ Cache للمصروفات
        self._cache_time: float = 0
        self._cached_expenses: list[schemas.Expense] | None = None
        self._cache_ttl = 120  # ⚡ دقيقتين للتوازن بين الأداء والتحديث

        logger.info("⚡ قسم المصروفات (ExpenseService) جاهز")

    def invalidate_cache(self):
        """⚡ إبطال الـ cache"""
        self._cached_expenses = None
        self._cache_time = 0

    def get_all_expenses(self) -> list[schemas.Expense]:
        """
        ⚡ جلب كل المصروفات (مع cache)

        Returns:
            قائمة بجميع المصروفات
        """
        import time

        try:
            # ⚡ استخدام الـ cache
            now = time.time()
            if self._cached_expenses and (now - self._cache_time) < self._cache_ttl:
                return self._cached_expenses

            # جلب من قاعدة البيانات
            expenses = self.repo.get_all_expenses()

            # تحديث الـ cache
            self._cached_expenses = expenses
            self._cache_time = now

            return expenses
        except Exception as e:
            logger.error("[ExpenseService] فشل جلب المصروفات: %s", e, exc_info=True)
            return []

    def create_expense(self, expense_data: schemas.Expense) -> schemas.Expense:
        """
        إضافة مصروف جديد مع إنشاء قيد محاسبي تلقائي

        Args:
            expense_data: بيانات المصروف الجديد، يجب أن يحتوي على:
                - account_id: كود حساب المصروف (مثل 5110 للرواتب)
                - payment_account_id: كود حساب الدفع (مثل 1111 للخزينة)
                - amount: المبلغ
                - category: الفئة
                - date: التاريخ

        Returns:
            المصروف المُنشأ

        Raises:
            ValueError: إذا لم يتم تحديد الحسابات المطلوبة
            Exception: في حالة فشل إضافة المصروف
        """
        logger.info("[ExpenseService] استلام طلب إضافة مصروف: %s", expense_data.category)

        # التحقق من وجود الحسابات المطلوبة
        if not hasattr(expense_data, "account_id") or not expense_data.account_id:
            raise ValueError("يجب تحديد حساب المصروف (account_id)")

        if not hasattr(expense_data, "payment_account_id") or not expense_data.payment_account_id:
            raise ValueError("يجب تحديد حساب الدفع (payment_account_id)")

        try:
            # حفظ المصروف
            created_expense = self.repo.create_expense(expense_data)

            # ⚡ إبطال الـ cache
            self.invalidate_cache()

            # نشر الحدث للمحاسبة (سيتم التعامل معه في accounting_service)
            self.bus.publish("EXPENSE_CREATED", {"expense": created_expense})

            # إرسال إشارة التحديث العامة
            app_signals.emit_data_changed("expenses")

            # 🔔 إشعار
            notify_operation(
                "created", "expense", f"{expense_data.amount:,.0f} ج.م - {expense_data.category}"
            )

            logger.info("[ExpenseService] تم إضافة المصروف وإنشاء القيد المحاسبي")
            return created_expense

        except Exception as e:
            logger.error("[ExpenseService] فشل إضافة المصروف: %s", e, exc_info=True)
            raise

    def update_expense(self, expense_id: str, expense_data: schemas.Expense) -> bool:
        """
        تعديل مصروف موجود

        Args:
            expense_id: معرف المصروف
            expense_data: البيانات الجديدة للمصروف

        Returns:
            True في حالة النجاح، False في حالة الفشل

        Raises:
            Exception: في حالة فشل التحديث
        """
        logger.info("[ExpenseService] استلام طلب تعديل مصروف: %s", expense_data.category)
        try:
            result = self.repo.update_expense(expense_id, expense_data)
            if result:
                # ⚡ إبطال الـ cache
                self.invalidate_cache()
                # ⚡ إرسال البيانات بالشكل الصحيح
                self.bus.publish("EXPENSE_UPDATED", {"expense": expense_data})
                # ⚡ إرسال إشارة التحديث
                app_signals.emit_data_changed("expenses")
                # 🔔 إشعار
                notify_operation(
                    "updated",
                    "expense",
                    f"{expense_data.amount:,.0f} ج.م - {expense_data.category}",
                )
                logger.info("[ExpenseService] تم تعديل المصروف بنجاح")
            return result
        except Exception as e:
            logger.error("[ExpenseService] فشل تعديل المصروف: %s", e, exc_info=True)
            raise

    def delete_expense(self, expense_id: str) -> bool:
        """
        حذف مصروف

        Args:
            expense_id: معرف المصروف المراد حذفه

        Returns:
            True في حالة النجاح، False في حالة الفشل

        Raises:
            Exception: في حالة فشل الحذف
        """
        logger.info("[ExpenseService] استلام طلب حذف مصروف: %s", expense_id)
        try:
            # ⚡ جلب بيانات المصروف قبل الحذف لمعرفة الحساب
            expense = self.repo.get_expense_by_id(expense_id)

            result = self.repo.delete_expense(expense_id)
            if result:
                # ⚡ إبطال الـ cache
                self.invalidate_cache()
                # ⚡ إرسال البيانات مع المصروف المحذوف
                self.bus.publish("EXPENSE_DELETED", {"id": expense_id, "expense": expense})
                # ⚡ إرسال إشارة التحديث
                app_signals.emit_data_changed("expenses")
                # 🔔 إشعار - تحويل expense_id لـ string
                notify_operation("deleted", "expense", str(expense_id))
                logger.info("[ExpenseService] تم حذف المصروف بنجاح")
            return result
        except Exception as e:
            logger.error("[ExpenseService] فشل حذف المصروف: %s", e, exc_info=True)
            raise

    def get_expenses_by_category(self, category: str) -> list[schemas.Expense]:
        """
        جلب المصروفات حسب الفئة

        Args:
            category: فئة المصروف

        Returns:
            قائمة المصروفات في هذه الفئة
        """
        try:
            all_expenses = self.repo.get_all_expenses()
            return [e for e in all_expenses if e.category == category]
        except Exception as e:
            logger.error("[ExpenseService] فشل جلب المصروفات بالفئة: %s", e, exc_info=True)
            return []

    def get_expenses_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[schemas.Expense]:
        """
        جلب المصروفات في فترة زمنية محددة

        Args:
            start_date: تاريخ البداية
            end_date: تاريخ النهاية

        Returns:
            قائمة المصروفات في الفترة المحددة
        """
        try:
            all_expenses = self.repo.get_all_expenses()
            return [e for e in all_expenses if start_date <= e.date <= end_date]
        except Exception as e:
            logger.error("[ExpenseService] فشل جلب المصروفات بالفترة: %s", e, exc_info=True)
            return []

    def get_expense_statistics(
        self, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> dict[str, Any]:
        """
        جلب إحصائيات المصروفات

        Args:
            start_date: تاريخ البداية (اختياري)
            end_date: تاريخ النهاية (اختياري)

        Returns:
            Dict مع إحصائيات المصروفات
        """
        try:
            # تحديد الفترة الافتراضية (الشهر الحالي)
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date.replace(day=1)

            expenses = self.get_expenses_by_date_range(start_date, end_date)

            # حساب الإجمالي
            total_amount = sum(e.amount for e in expenses)

            # تصنيف حسب الفئة
            by_category: dict[str, float] = {}
            for expense in expenses:
                category = expense.category or "غير مصنف"
                by_category[category] = by_category.get(category, 0) + expense.amount

            # تصنيف حسب المشروع
            by_project: dict[str, float] = {}
            for expense in expenses:
                project_id = expense.project_id or "بدون مشروع"
                by_project[project_id] = by_project.get(project_id, 0) + expense.amount

            stats = {
                "total_amount": total_amount,
                "count": len(expenses),
                "average": total_amount / len(expenses) if expenses else 0,
                "by_category": by_category,
                "by_project": by_project,
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            }

            logger.info(
                "[ExpenseService] إحصائيات المصروفات: %s مصروف بإجمالي %s",
                stats["count"],
                stats["total_amount"],
            )
            return stats

        except Exception as e:
            logger.error("[ExpenseService] فشل جلب إحصائيات المصروفات: %s", e, exc_info=True)
            return {
                "total_amount": 0,
                "count": 0,
                "average": 0,
                "by_category": {},
                "by_project": {},
                "period": {},
            }

    def get_expense_categories(self) -> list[str]:
        """
        جلب قائمة فئات المصروفات المستخدمة

        Returns:
            قائمة الفئات الفريدة
        """
        try:
            all_expenses = self.repo.get_all_expenses()
            categories = {e.category for e in all_expenses if e.category}
            return sorted(categories)
        except Exception as e:
            logger.error("[ExpenseService] فشل جلب فئات المصروفات: %s", e, exc_info=True)
            return []
