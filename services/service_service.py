# الملف: services/service_service.py


from core import schemas
from core.cache_manager import get_cache, invalidate_cache
from core.event_bus import EventBus
from core.logger import get_logger
from core.repository import Repository
from core.signals import app_signals
from services.settings_service import SettingsService

# إشعارات العمليات
try:
    from core.notification_bridge import notify_operation
except ImportError:

    def notify_operation(action, entity_type, entity_name):
        pass


logger = get_logger(__name__)


class ServiceService:
    """
    قسم الخدمات (Service Layer).
    يحتوي على منطق العمل الخاص بإدارة الخدمات المقدمة.
    """

    def __init__(
        self,
        repository: Repository,
        event_bus: EventBus,
        settings_service: SettingsService,
    ):
        """
        تهيئة خدمة الخدمات

        Args:
            repository: مخزن البيانات الرئيسي
            event_bus: نظام الأحداث للتواصل بين الخدمات
            settings_service: خدمة الإعدادات
        """
        self.repo = repository
        self.bus = event_bus
        self.settings_service = settings_service
        self.repo.settings_service = settings_service  # type: ignore[attr-defined]
        logger.info("قسم الخدمات (ServiceService) جاهز")

    def get_all_services(self) -> list[schemas.Service]:
        """
        جلب كل الخدمات النشطة

        Returns:
            قائمة بجميع الخدمات النشطة
        """
        try:
            cache = get_cache("services")
            cached = cache.get("active")
            if cached is not None:
                return cached
            services = self.repo.get_all_services()
            cache.set("active", services)
            return services
        except Exception as e:
            logger.error("[ServiceService] فشل جلب الخدمات: %s", e, exc_info=True)
            return []

    def get_archived_services(self) -> list[schemas.Service]:
        """
        جلب الخدمات المؤرشفة

        Returns:
            قائمة بجميع الخدمات المؤرشفة
        """
        try:
            cache = get_cache("services")
            cached = cache.get("archived")
            if cached is not None:
                return cached
            services = self.repo.get_archived_services()
            cache.set("archived", services)
            return services
        except Exception as e:
            logger.error("[ServiceService] فشل جلب الخدمات المؤرشفة: %s", e, exc_info=True)
            return []

    def create_service(self, service_data: dict) -> schemas.Service:
        """
        إضافة خدمة جديدة

        Args:
            service_data: بيانات الخدمة الجديدة

        Returns:
            الخدمة المُنشأة

        Raises:
            Exception: في حالة فشل إضافة الخدمة
        """
        logger.info("[ServiceService] استلام طلب إضافة خدمة: %s", service_data.get("name"))
        try:
            new_service_schema = schemas.Service(**service_data)
            created_service = self.repo.create_service(new_service_schema)
            # ⚡ إرسال إشارة التحديث
            app_signals.emit_data_changed("services")
            invalidate_cache("services")
            # 🔔 إشعار
            notify_operation("created", "service", created_service.name)
            logger.info("[ServiceService] تم إضافة الخدمة %s بنجاح", created_service.name)
            return created_service
        except Exception as e:
            logger.error("[ServiceService] فشل إضافة الخدمة: %s", e, exc_info=True)
            raise

    def update_service(self, service_id: str, new_data: dict) -> schemas.Service | None:
        """
        تعديل بيانات خدمة موجودة

        Args:
            service_id: معرف الخدمة
            new_data: البيانات الجديدة للتحديث

        Returns:
            الخدمة المُحدثة أو None في حالة الفشل

        Raises:
            Exception: في حالة عدم وجود الخدمة أو فشل التحديث
        """
        logger.info("[ServiceService] استلام طلب تعديل الخدمة ID: %s", service_id)
        try:
            existing_service = self.repo.get_service_by_id(service_id)
            if not existing_service:
                raise ValueError("الخدمة غير موجودة للتعديل")

            updated_service_schema = existing_service.model_copy(update=new_data)
            saved_service = self.repo.update_service(service_id, updated_service_schema)
            # ⚡ إرسال إشارة التحديث
            app_signals.emit_data_changed("services")
            invalidate_cache("services")

            if saved_service is not None:
                # 🔔 إشعار
                notify_operation("updated", "service", saved_service.name)
                logger.info("[ServiceService] تم تعديل الخدمة %s بنجاح", saved_service.name)
            return saved_service
        except Exception as e:
            logger.error("[ServiceService] فشل تعديل الخدمة: %s", e, exc_info=True)
            raise

    def delete_service(self, service_id: str) -> bool:
        """
        حذف خدمة نهائياً (Hard Delete)

        Args:
            service_id: معرف الخدمة المراد حذفها

        Returns:
            True في حالة النجاح، False في حالة الفشل

        Raises:
            Exception: في حالة فشل عملية الحذف
        """
        logger.info("[ServiceService] استلام طلب حذف الخدمة نهائياً ID: %s", service_id)
        try:
            # جلب اسم الخدمة قبل الحذف
            existing_service = self.repo.get_service_by_id(service_id)
            service_name = existing_service.name if existing_service else f"خدمة #{service_id}"

            success = self.repo.delete_service_permanently(service_id)
            if success:
                # ⚡ إرسال إشارة التحديث
                app_signals.emit_data_changed("services")
                invalidate_cache("services")
                # 🔔 إشعار
                notify_operation("deleted", "service", service_name)
                logger.info("[ServiceService] ✅ تم حذف الخدمة نهائياً")
            return success
        except Exception as e:
            logger.error("[ServiceService] فشل حذف الخدمة: %s", e, exc_info=True)
            raise
