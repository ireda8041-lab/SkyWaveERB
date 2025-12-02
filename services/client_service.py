# الملف: services/client_service.py

from core.repository import Repository
from core import schemas
from typing import List, Optional


class ClientService:
    """
    قسم العملاء (Service Layer).
    يحتوي على منطق العمل (Business Logic) الخاص بالعملاء.
    """

    def __init__(self, repository: Repository):
        self.repo = repository
        print("INFO: قسم العملاء (ClientService) جاهز.")

    def get_all_clients(self) -> List[schemas.Client]:
        """ جلب كل العملاء (بيطلبها من المخزن) """
        try:
            return self.repo.get_all_clients()
        except Exception as e:
            print(f"ERROR: [ClientService] فشل جلب العملاء: {e}")
            return []

    def create_client(self, client_data: schemas.Client) -> schemas.Client:
        """ إضافة عميل جديد """
        print(f"INFO: [ClientService] استلام طلب إضافة عميل: {client_data.name}")
        try:
            created_client = self.repo.create_client(client_data)
            return created_client
        except Exception as e:
            print(f"ERROR: [ClientService] فشل إضافة العميل: {e}")
            raise

    def update_client(self, client_id: str, new_data: dict) -> Optional[schemas.Client]:
        """
        (جديدة) تعديل بيانات عميل.
        """
        print(f"INFO: [ClientService] استلام طلب تعديل العميل ID: {client_id}")

        try:
            existing_client = self.repo.get_client_by_id(client_id)
            if not existing_client:
                raise Exception("العميل غير موجود للتعديل.")

            updated_client_schema = existing_client.model_copy(update=new_data)

            saved_client = self.repo.update_client(client_id, updated_client_schema)

            print(f"SUCCESS: [ClientService] تم تعديل العميل {updated_client_schema.name} بنجاح.")
            return saved_client

        except Exception as e:
            print(f"ERROR: [ClientService] فشل تعديل العميل: {e}")
            raise

    def get_client_by_id(self, client_id: str) -> Optional[schemas.Client]:
        """ جلب عميل واحد بالـ ID """
        try:
            return self.repo.get_client_by_id(client_id)
        except Exception as e:
            print(f"ERROR: [ClientService] فشل جلب العميل {client_id}: {e}")
            return None

    def get_client_by_name(self, name: str) -> Optional[schemas.Client]:
        """ (جديدة) جلب عميل واحد بالاسم """
        try:
            return self.repo.get_client_by_name(name)
        except Exception as e:
            print(f"ERROR: [ClientService] فشل جلب العميل بالاسم {name}: {e}")
            return None

    def delete_client(self, client_id: str) -> bool:
        """
        (جديدة) أرشفة (Soft Delete) لعميل.
        """
        print(f"INFO: [ClientService] استلام طلب أرشفة العميل ID: {client_id}")

        try:
            success = self.repo.archive_client_by_id(client_id)
            if success:
                print("SUCCESS: [ClientService] تم أرشفة العميل بنجاح.")
            return success
        except Exception as e:
            print(f"ERROR: [ClientService] فشل أرشفة العميل: {e}")
            raise

    def get_archived_clients(self) -> List[schemas.Client]:
        """ (جديدة) جلب العملاء المؤرشفين """
        try:
            return self.repo.get_archived_clients()
        except Exception as e:
            print(f"ERROR: [ClientService] فشل جلب العملاء المؤرشفين: {e}")
            return []
