# الملف: services/client_service.py
"""
خدمة العملاء (Client Service)

توفر واجهة موحدة لإدارة العملاء في النظام:
- إنشاء عملاء جدد
- تحديث بيانات العملاء
- أرشفة العملاء
- البحث والاستعلام

المؤلف: Sky Wave Team
الإصدار: 2.0.0
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from core import schemas
from core.logger import get_logger
from core.repository import Repository
from core.signals import app_signals

if TYPE_CHECKING:
    from core.repository import Repository

# ⚡ استيراد محسّن السرعة
try:
    from core.speed_optimizer import LRUCache, cached  # noqa: F401
    CACHE_ENABLED = True
except ImportError:
    CACHE_ENABLED = False

# استيراد دالة الإشعارات
try:
    from core.notification_bridge import notify_operation
except ImportError:
    def notify_operation(action, entity_type, entity_name): pass

logger = get_logger(__name__)


class ClientService:
    """
    ⚡ قسم العملاء - محسّن للسرعة
    """

    def __init__(self, repository: Repository):
        """
        تهيئة خدمة العملاء

        Args:
            repository: مخزن البيانات الرئيسي
        """
        self.repo = repository
        self._cache_time: float = 0
        self._cached_clients: list[schemas.Client] | None = None
        self._cache_ttl = 30  # ⚡ 30 ثانية
        logger.info("⚡ قسم العملاء (ClientService) جاهز")

    def get_all_clients(self) -> list[schemas.Client]:
        """
        ⚡ جلب كل العملاء النشطين (مع cache)
        """
        try:
            # ⚡ استخدام الـ cache
            now = time.time()
            if self._cached_clients and (now - self._cache_time) < self._cache_ttl:
                return self._cached_clients

            # جلب من قاعدة البيانات
            clients = self.repo.get_all_clients()

            # تحديث الـ cache
            self._cached_clients = clients
            self._cache_time = now

            return clients
        except Exception as e:
            logger.error(f"[ClientService] فشل جلب العملاء: {e}", exc_info=True)
            return []

    def invalidate_cache(self):
        """⚡ إبطال الـ cache"""
        self._cached_clients = None
        self._cache_time = 0

    def create_client(self, client_data: schemas.Client) -> schemas.Client:
        """
        ⚡ إضافة عميل جديد (مع إبطال الـ cache)
        """
        logger.info(f"[ClientService] إضافة عميل: {client_data.name}")
        try:
            created_client = self.repo.create_client(client_data)
            self.invalidate_cache()  # ⚡ إبطال الـ cache
            # ⚡ إرسال إشارة التحديث
            app_signals.emit_data_changed('clients')

            # 🔔 إشعار مخصص (يُرسل لجميع الأجهزة)
            if hasattr(client_data, 'logo_data') and client_data.logo_data:
                from ui.notification_system import notify_success
                notify_success(
                    f"تم إضافة العميل '{created_client.name}' مع الصورة 🖼️",
                    "👥 عميل جديد",
                    sync=True  # ⚡ إرسال لجميع الأجهزة
                )
            else:
                notify_operation('created', 'client', created_client.name)

            logger.info(f"[ClientService] ✅ تم إضافة العميل {created_client.name}")
            return created_client
        except Exception as e:
            logger.error(f"[ClientService] فشل إضافة العميل: {e}", exc_info=True)
            raise

    def update_client(self, client_id: str, new_data: dict) -> schemas.Client | None:
        """
        تعديل بيانات عميل موجود

        Args:
            client_id: معرف العميل
            new_data: البيانات الجديدة للتحديث

        Returns:
            العميل المُحدث أو None في حالة الفشل

        Raises:
            Exception: في حالة عدم وجود العميل أو فشل التحديث
        """
        logger.info(f"[ClientService] تعديل العميل ID: {client_id}")

        try:
            existing_client = self.repo.get_client_by_id(client_id)
            if not existing_client:
                raise Exception("العميل غير موجود للتعديل")

            # ⚡ التعامل الذكي مع logo_data
            if 'logo_data' in new_data:
                if new_data['logo_data'] == "__DELETE__":
                    # المستخدم يريد حذف الصورة صراحة
                    new_data['logo_data'] = ""
                    new_data['logo_path'] = ""
                    logger.info("[ClientService] 🗑️ حذف logo_data")
                elif new_data['logo_data']:
                    # صورة جديدة
                    logger.info(f"[ClientService] 📷 تحديث logo_data ({len(new_data['logo_data'])} حرف)")
                else:
                    # logo_data فارغ - الاحتفاظ بالقديم
                    if existing_client.logo_data:
                        new_data['logo_data'] = existing_client.logo_data
                        logger.info(f"[ClientService] 📷 الاحتفاظ بـ logo_data القديم ({len(existing_client.logo_data)} حرف)")
            else:
                # logo_data غير موجود في new_data - الاحتفاظ بالقديم
                if existing_client.logo_data:
                    new_data['logo_data'] = existing_client.logo_data
                    logger.info(f"[ClientService] 📷 الاحتفاظ بـ logo_data القديم ({len(existing_client.logo_data)} حرف)")

            updated_client_schema = existing_client.model_copy(update=new_data)
            saved_client = self.repo.update_client(client_id, updated_client_schema)
            self.invalidate_cache()  # ⚡ إبطال الـ cache
            # ⚡ إرسال إشارة التحديث
            app_signals.emit_data_changed('clients')

            # 🔔 إشعار مخصص حسب نوع التحديث (يُرسل لجميع الأجهزة)
            if 'logo_data' in new_data and new_data.get('logo_data') and new_data['logo_data'] != "__DELETE__":
                # تم تحديث الصورة
                from ui.notification_system import notify_success
                notify_success(
                    f"تم تحديث صورة العميل '{updated_client_schema.name}'",
                    "تحديث صورة",
                    sync=True  # ⚡ إرسال لجميع الأجهزة
                )
            elif 'logo_data' in new_data and (not new_data.get('logo_data') or new_data['logo_data'] == ""):
                # تم حذف الصورة
                from ui.notification_system import notify_info
                notify_info(
                    f"تم حذف صورة العميل '{updated_client_schema.name}'",
                    "حذف صورة",
                    sync=True  # ⚡ إرسال لجميع الأجهزة
                )
            else:
                # تحديث عادي
                notify_operation('updated', 'client', updated_client_schema.name)

            logger.info(f"[ClientService] ✅ تم تعديل العميل {updated_client_schema.name}")
            return saved_client

        except Exception as e:
            logger.error(f"[ClientService] فشل تعديل العميل: {e}", exc_info=True)
            raise

    def get_client_by_id(self, client_id: str) -> schemas.Client | None:
        """
        جلب عميل واحد بالمعرف

        Args:
            client_id: معرف العميل

        Returns:
            بيانات العميل أو None إذا لم يُعثر عليه
        """
        try:
            return self.repo.get_client_by_id(client_id)
        except Exception as e:
            logger.error(f"[ClientService] فشل جلب العميل {client_id}: {e}", exc_info=True)
            return None

    def get_client_by_name(self, name: str) -> schemas.Client | None:
        """
        جلب عميل واحد بالاسم

        Args:
            name: اسم العميل

        Returns:
            بيانات العميل أو None إذا لم يُعثر عليه
        """
        try:
            return self.repo.get_client_by_name(name)
        except Exception as e:
            logger.error(f"[ClientService] فشل جلب العميل بالاسم {name}: {e}", exc_info=True)
            return None

    def delete_client(self, client_id: str) -> bool:
        """
        حذف عميل نهائياً (Hard Delete)

        Args:
            client_id: معرف العميل المراد حذفه

        Returns:
            True في حالة النجاح، False في حالة الفشل

        Raises:
            Exception: في حالة فشل عملية الحذف
        """
        logger.info(f"[ClientService] استلام طلب حذف العميل نهائياً ID: {client_id}")

        try:
            success = self.repo.delete_client_permanently(client_id)
            if success:
                self.invalidate_cache()  # ⚡ إبطال الـ cache
                # ⚡ إرسال إشارة التحديث
                app_signals.emit_data_changed('clients')
                # 🔔 إشعار - تحويل client_id لـ string
                notify_operation('deleted', 'client', str(client_id))
                logger.info("[ClientService] ✅ تم حذف العميل نهائياً")
            return success
        except Exception as e:
            logger.error(f"[ClientService] فشل حذف العميل: {e}", exc_info=True)
            raise

    def get_archived_clients(self) -> list[schemas.Client]:
        """
        جلب العملاء المؤرشفين

        Returns:
            قائمة بجميع العملاء المؤرشفين
        """
        try:
            return self.repo.get_archived_clients()
        except Exception as e:
            logger.error(f"[ClientService] فشل جلب العملاء المؤرشفين: {e}", exc_info=True)
            return []

    def search_clients(
        self,
        query: str,
        fields: list[str] | None = None,
        limit: int = 20
    ) -> list[schemas.Client]:
        """
        البحث في العملاء

        Args:
            query: نص البحث
            fields: الحقول للبحث فيها (افتراضي: name, company_name, phone)
            limit: الحد الأقصى للنتائج

        Returns:
            قائمة العملاء المطابقين
        """
        if not query:
            return []

        search_fields = fields or ["name", "company_name", "phone", "email"]
        query_lower = query.lower()

        try:
            all_clients = self.repo.get_all_clients()
            results = []

            for client in all_clients:
                for field in search_fields:
                    value = getattr(client, field, None)
                    if value and query_lower in str(value).lower():
                        results.append(client)
                        break

                if len(results) >= limit:
                    break

            logger.debug(f"[ClientService] تم العثور على {len(results)} عميل للبحث: {query}")
            return results

        except Exception as e:
            logger.error(f"[ClientService] فشل البحث في العملاء: {e}", exc_info=True)
            return []

    def get_client_statistics(self) -> dict[str, Any]:
        """
        جلب إحصائيات العملاء

        Returns:
            Dict مع إحصائيات العملاء
        """
        try:
            active_clients = self.repo.get_all_clients()
            archived_clients = self.repo.get_archived_clients()

            # تصنيف حسب النوع
            client_types: dict[str, int] = {}
            for client in active_clients:
                client_type = client.client_type or "غير محدد"
                client_types[client_type] = client_types.get(client_type, 0) + 1

            # تصنيف حسب الدولة
            countries: dict[str, int] = {}
            for client in active_clients:
                country = client.country or "غير محدد"
                countries[country] = countries.get(country, 0) + 1

            stats = {
                "total_active": len(active_clients),
                "total_archived": len(archived_clients),
                "total": len(active_clients) + len(archived_clients),
                "by_type": client_types,
                "by_country": countries
            }

            logger.info(f"[ClientService] إحصائيات العملاء: {stats['total_active']} نشط، {stats['total_archived']} مؤرشف")
            return stats

        except Exception as e:
            logger.error(f"[ClientService] فشل جلب إحصائيات العملاء: {e}", exc_info=True)
            return {
                "total_active": 0,
                "total_archived": 0,
                "total": 0,
                "by_type": {},
                "by_country": {}
            }
