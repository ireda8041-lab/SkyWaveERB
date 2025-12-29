# الملف: services/service_service.py


from core import schemas
from core.event_bus import EventBus
from core.logger import get_logger
from core.repository import Repository
from core.signals import app_signals
from services.settings_service import SettingsService

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
            return self.repo.get_all_services()
        except Exception as e:
            logger.error(f"[ServiceService] فشل جلب الخدمات: {e}", exc_info=True)
            return []

    def get_archived_services(self) -> list[schemas.Service]:
        """
        جلب الخدمات المؤرشفة

        Returns:
            قائمة بجميع الخدمات المؤرشفة
        """
        try:
            return self.repo.get_archived_services()
        except Exception as e:
            logger.error(f"[ServiceService] فشل جلب الخدمات المؤرشفة: {e}", exc_info=True)
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
        logger.info(f"[ServiceService] استلام طلب إضافة خدمة: {service_data.get('name')}")
        try:
            new_service_schema = schemas.Service(**service_data)
            created_service = self.repo.create_service(new_service_schema)
            # ⚡ إرسال إشارة التحديث
            app_signals.emit_data_changed('services')
            logger.info(f"[ServiceService] تم إضافة الخدمة {created_service.name} بنجاح")
            return created_service
        except Exception as e:
            logger.error(f"[ServiceService] فشل إضافة الخدمة: {e}", exc_info=True)
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
        logger.info(f"[ServiceService] استلام طلب تعديل الخدمة ID: {service_id}")
        try:
            existing_service = self.repo.get_service_by_id(service_id)
            if not existing_service:
                raise Exception("الخدمة غير موجودة للتعديل")

            updated_service_schema = existing_service.model_copy(update=new_data)
            saved_service = self.repo.update_service(service_id, updated_service_schema)
            # ⚡ إرسال إشارة التحديث
            app_signals.emit_data_changed('services')

            if saved_service is not None:
                logger.info(f"[ServiceService] تم تعديل الخدمة {saved_service.name} بنجاح")
            return saved_service
        except Exception as e:
            logger.error(f"[ServiceService] فشل تعديل الخدمة: {e}", exc_info=True)
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
        logger.info(f"[ServiceService] استلام طلب حذف الخدمة نهائياً ID: {service_id}")
        try:
            success = self.repo.delete_service_permanently(service_id)
            if success:
                # ⚡ إرسال إشارة التحديث
                app_signals.emit_data_changed('services')
                logger.info("[ServiceService] ✅ تم حذف الخدمة نهائياً")
            return success
        except Exception as e:
            logger.error(f"[ServiceService] فشل حذف الخدمة: {e}", exc_info=True)
            raise
