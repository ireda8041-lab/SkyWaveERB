# الملف: core/base_service.py
"""
الخدمة الأساسية (Base Service)
توفر وظائف مشتركة لجميع الخدمات
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from core.error_handler import ErrorHandler
from core.logger import get_logger

T = TypeVar('T')


class BaseService(ABC, Generic[T]):
    """
    الخدمة الأساسية

    توفر:
    - تسجيل الأحداث (Logging)
    - معالجة الأخطاء
    - التحقق من البيانات
    - التخزين المؤقت
    - نشر الأحداث
    """

    def __init__(
        self,
        repository,
        event_bus=None,
        cache_enabled: bool = True
    ):
        self.repo = repository
        self.event_bus = event_bus
        self.cache_enabled = cache_enabled

        self.logger = get_logger(self.__class__.__name__)
        self.error_handler = ErrorHandler()
        self.cache = None  # Cache disabled for now

        self.logger.info(f"تم تهيئة {self.__class__.__name__}")

    @property
    @abstractmethod
    def entity_name(self) -> str:
        """اسم الكيان (للتسجيل والأحداث)"""
        pass

    @property
    def cache_prefix(self) -> str:
        """بادئة الكاش"""
        return f"{self.entity_name}:"

    def _get_cache_key(self, *args) -> str:
        """بناء مفتاح الكاش"""
        return f"{self.cache_prefix}{':'.join(str(a) for a in args)}"

    def _invalidate_cache(self, *args) -> None:
        """إبطال الكاش"""
        if self.cache:
            if args:
                key = self._get_cache_key(*args)
                self.cache.delete(key)
            else:
                self.cache.invalidate_pattern(f"{self.cache_prefix}*")

    def _emit_event(self, event_name: str, data: dict[str, Any]) -> None:
        """نشر حدث"""
        full_event_name = f"{self.entity_name.upper()}_{event_name.upper()}"

        # استخدام EventBus إذا كان موجوداً
        if self.event_bus:
            self.event_bus.publish(full_event_name, data)

        self.logger.debug(f"تم نشر حدث: {full_event_name}")

    def _validate(self, data: dict[str, Any], validator=None):
        """التحقق من البيانات - placeholder"""
        return True

    def _validate_or_raise(self, data: dict[str, Any], validator=None) -> None:
        """التحقق من البيانات مع رفع استثناء - placeholder"""
        pass

    def _handle_error(
        self,
        exception: Exception,
        context: str,
        user_message: str | None = None
    ) -> None:
        """معالجة الخطأ"""
        self.error_handler.handle_exception(
            exception=exception,
            context=f"{self.__class__.__name__}.{context}",
            user_message=user_message,
            show_dialog=False
        )

    def _log_operation(
        self,
        operation: str,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """تسجيل عملية"""
        message = f"{operation}"
        if entity_id:
            message += f" - ID: {entity_id}"
        if details:
            message += f" - {details}"

        self.logger.info(message)


class CRUDService(BaseService[T]):
    """
    خدمة CRUD الأساسية

    توفر عمليات:
    - Create (إنشاء)
    - Read (قراءة)
    - Update (تحديث)
    - Delete (حذف)
    """

    @property
    def validator_class(self):
        """فئة المحقق - placeholder"""
        return None

    def get_all(self, **filters) -> list[T]:
        """
        جلب جميع الكيانات

        Args:
            **filters: فلاتر اختيارية

        Returns:
            قائمة الكيانات
        """
        try:
            cache_key = self._get_cache_key("all", str(filters))

            if self.cache:
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    self.logger.debug(f"تم جلب {self.entity_name} من الكاش")
                    return cached_result

            result = self._fetch_all(**filters)

            if self.cache:
                self.cache.set(cache_key, result, ttl=300)

            self._log_operation("get_all", details={"count": len(result)})
            return result

        except Exception as e:
            self._handle_error(e, "get_all")
            return []

    @abstractmethod
    def _fetch_all(self, **filters) -> list[T]:
        """جلب جميع الكيانات من المخزن"""
        pass

    def get_by_id(self, entity_id: str) -> T | None:
        """
        جلب كيان بالمعرف

        Args:
            entity_id: معرف الكيان

        Returns:
            الكيان أو None
        """
        try:
            cache_key = self._get_cache_key("id", entity_id)

            if self.cache:
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

            result = self._fetch_by_id(entity_id)

            if result and self.cache:
                self.cache.set(cache_key, result, ttl=600)

            return result

        except Exception as e:
            self._handle_error(e, "get_by_id", f"فشل جلب {self.entity_name}")
            return None

    @abstractmethod
    def _fetch_by_id(self, entity_id: str) -> T | None:
        """جلب كيان من المخزن"""
        pass

    def create(self, data: dict[str, Any]) -> T | None:
        """
        إنشاء كيان جديد

        Args:
            data: بيانات الكيان

        Returns:
            الكيان المنشأ أو None
        """
        try:
            # التحقق من البيانات
            if self.validator_class:
                validator = self.validator_class()
                self._validate_or_raise(data, validator)

            # الإنشاء
            result = self._create(data)

            if result:
                # إبطال الكاش
                self._invalidate_cache()

                # نشر الحدث
                self._emit_event("CREATED", {self.entity_name: result})

                self._log_operation("create", details={"data": data})

            return result

        except Exception as e:
            self._handle_error(e, "create", f"فشل إنشاء {self.entity_name}")
            raise

    @abstractmethod
    def _create(self, data: dict[str, Any]) -> T | None:
        """إنشاء كيان في المخزن"""
        pass

    def update(self, entity_id: str, data: dict[str, Any]) -> T | None:
        """
        تحديث كيان

        Args:
            entity_id: معرف الكيان
            data: البيانات الجديدة

        Returns:
            الكيان المحدث أو None
        """
        try:
            # التحقق من الوجود
            existing = self.get_by_id(entity_id)
            if not existing:
                raise ValueError(f"{self.entity_name} غير موجود")

            # التحقق من البيانات
            if self.validator_class:
                validator = self.validator_class()
                self._validate_or_raise(data, validator)

            # التحديث
            result = self._update(entity_id, data)

            if result:
                # إبطال الكاش
                self._invalidate_cache()
                self._invalidate_cache("id", entity_id)

                # نشر الحدث
                self._emit_event("UPDATED", {self.entity_name: result})

                self._log_operation("update", entity_id)

            return result

        except Exception as e:
            self._handle_error(e, "update", f"فشل تحديث {self.entity_name}")
            raise

    @abstractmethod
    def _update(self, entity_id: str, data: dict[str, Any]) -> T | None:
        """تحديث كيان في المخزن"""
        pass

    def delete(self, entity_id: str) -> bool:
        """
        حذف كيان (أرشفة)

        Args:
            entity_id: معرف الكيان

        Returns:
            True إذا نجحت العملية
        """
        try:
            # التحقق من الوجود
            existing = self.get_by_id(entity_id)
            if not existing:
                raise ValueError(f"{self.entity_name} غير موجود")

            # الحذف
            result = self._delete(entity_id)

            if result:
                # إبطال الكاش
                self._invalidate_cache()
                self._invalidate_cache("id", entity_id)

                # نشر الحدث
                self._emit_event("DELETED", {"id": entity_id})

                self._log_operation("delete", entity_id)

            return result

        except Exception as e:
            self._handle_error(e, "delete", f"فشل حذف {self.entity_name}")
            return False

    @abstractmethod
    def _delete(self, entity_id: str) -> bool:
        """حذف كيان من المخزن"""
        pass


class QueryService(BaseService[T]):
    """
    خدمة الاستعلامات

    توفر استعلامات متقدمة مع:
    - الترقيم (Pagination)
    - الفرز (Sorting)
    - الفلترة (Filtering)
    """

    def query(
        self,
        filters: dict[str, Any] | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20
    ) -> dict[str, Any]:
        """
        استعلام متقدم

        Args:
            filters: الفلاتر
            sort_by: حقل الفرز
            sort_order: اتجاه الفرز (asc/desc)
            page: رقم الصفحة
            page_size: حجم الصفحة

        Returns:
            {
                'items': [...],
                'total': int,
                'page': int,
                'page_size': int,
                'total_pages': int
            }
        """
        try:
            # بناء مفتاح الكاش
            cache_key = self._get_cache_key(
                "query",
                str(filters),
                sort_by or "",
                sort_order,
                page,
                page_size
            )

            if self.cache:
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

            # تنفيذ الاستعلام
            result = self._execute_query(
                filters=filters,
                sort_by=sort_by,
                sort_order=sort_order,
                page=page,
                page_size=page_size
            )

            if self.cache:
                self.cache.set(cache_key, result, ttl=120)

            return result

        except Exception as e:
            self._handle_error(e, "query")
            return {
                'items': [],
                'total': 0,
                'page': page,
                'page_size': page_size,
                'total_pages': 0
            }

    @abstractmethod
    def _execute_query(
        self,
        filters: dict[str, Any] | None,
        sort_by: str | None,
        sort_order: str,
        page: int,
        page_size: int
    ) -> dict[str, Any]:
        """تنفيذ الاستعلام"""
        pass

    def count(self, filters: dict[str, Any] | None = None) -> int:
        """
        عد الكيانات

        Args:
            filters: الفلاتر

        Returns:
            العدد
        """
        try:
            return self._count(filters)
        except Exception as e:
            self._handle_error(e, "count")
            return 0

    @abstractmethod
    def _count(self, filters: dict[str, Any] | None) -> int:
        """عد الكيانات في المخزن"""
        pass

    def exists(self, entity_id: str) -> bool:
        """
        التحقق من وجود كيان

        Args:
            entity_id: معرف الكيان

        Returns:
            True إذا كان موجوداً
        """
        # استخدام count بدلاً من get_by_id لتجنب مشاكل الوراثة
        try:
            count = self._count({"id": entity_id})
            return count > 0
        except Exception:
            return False

    def search(
        self,
        query: str,
        fields: list[str] | None = None,
        limit: int = 20
    ) -> list[T]:
        """
        البحث في الكيانات

        Args:
            query: نص البحث
            fields: الحقول للبحث فيها
            limit: الحد الأقصى للنتائج

        Returns:
            قائمة النتائج
        """
        try:
            return self._search(query, fields, limit)
        except Exception as e:
            self._handle_error(e, "search")
            return []

    @abstractmethod
    def _search(
        self,
        query: str,
        fields: list[str] | None,
        limit: int
    ) -> list[T]:
        """البحث في المخزن"""
        pass
