# الملف: services/service_service.py

from core.repository import Repository
from core.event_bus import EventBus
from core import schemas
from typing import List, Optional

from services.settings_service import SettingsService


class ServiceService:
    """
    (معدل) قسم الخدمات (Service Layer).
    """

    def __init__(
        self,
        repository: Repository,
        event_bus: EventBus,
        settings_service: SettingsService,
    ):
        self.repo = repository
        self.bus = event_bus
        self.settings_service = settings_service
        self.repo.settings_service = settings_service
        print("INFO: قسم الخدمات (ServiceService) جاهز.")

    def get_all_services(self) -> List[schemas.Service]:
        """ جلب كل الخدمات (النشطة) """
        try:
            return self.repo.get_all_services()
        except Exception as e:
            print(f"ERROR: [ServiceService] فشل جلب الخدمات: {e}")
            return []

    def get_archived_services(self) -> List[schemas.Service]:
        """ (جديدة) جلب الخدمات المؤرشفة """
        try:
            return self.repo.get_archived_services()
        except Exception as e:
            print(f"ERROR: [ServiceService] فشل جلب الخدمات المؤرشفة: {e}")
            return []

    def create_service(self, service_data: dict) -> schemas.Service:
        """
        إضافة خدمة جديدة
        """
        print(f"INFO: [ServiceService] استلام طلب إضافة خدمة: {service_data.get('name')}")
        try:
            new_service_schema = schemas.Service(**service_data)
            created_service = self.repo.create_service(new_service_schema)
            return created_service
        except Exception as e:
            print(f"ERROR: [ServiceService] فشل إضافة الخدمة: {e}")
            raise

    def update_service(self, service_id: str, new_data: dict) -> Optional[schemas.Service]:
        """
        (جديدة) تعديل بيانات خدمة.
        """
        print(f"INFO: [ServiceService] استلام طلب تعديل الخدمة ID: {service_id}")
        try:
            existing_service = self.repo.get_service_by_id(service_id)
            if not existing_service:
                raise Exception("الخدمة غير موجودة للتعديل.")

            updated_service_schema = existing_service.model_copy(update=new_data)
            saved_service = self.repo.update_service(service_id, updated_service_schema)

            print(f"SUCCESS: [ServiceService] تم تعديل الخدمة {saved_service.name} بنجاح.")
            return saved_service
        except Exception as e:
            print(f"ERROR: [ServiceService] فشل تعديل الخدمة: {e}")
            raise

    def delete_service(self, service_id: str) -> bool:
        """
        (جديدة) أرشفة (Soft Delete) لخدمة.
        """
        print(f"INFO: [ServiceService] استلام طلب أرشفة الخدمة ID: {service_id}")
        try:
            return self.repo.archive_service_by_id(service_id)
        except Exception as e:
            print(f"ERROR: [ServiceService] فشل أرشفة الخدمة: {e}")
            raise
