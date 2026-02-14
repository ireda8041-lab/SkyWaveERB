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

    def notify_operation(action, entity_type, entity_name):
        pass


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
        self._cache_ttl = 120  # ⚡ دقيقتين للتوازن بين الأداء والتحديث
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
            logger.error("[ClientService] فشل جلب العملاء: %s", e, exc_info=True)
            return []

    def invalidate_cache(self):
        """⚡ إبطال الـ cache"""
        self._cached_clients = None
        self._cache_time = 0

    def create_client(self, client_data: schemas.Client) -> schemas.Client:
        """
        ⚡ إضافة عميل جديد (مع إبطال الـ cache)
        """
        logger.info("[ClientService] إضافة عميل: %s", client_data.name)
        try:
            created_client = self.repo.create_client(client_data)
            self.invalidate_cache()  # ⚡ إبطال الـ cache
            # ⚡ إرسال إشارة التحديث
            app_signals.emit_data_changed("clients")

            # إشعار آمن بدون استيراد واجهة المستخدم مباشرة (أفضل للاختبارات والخدمات headless)
            notify_operation("created", "client", created_client.name)

            logger.info("[ClientService] ✅ تم إضافة العميل %s", created_client.name)
            return created_client
        except Exception as e:
            logger.error("[ClientService] فشل إضافة العميل: %s", e, exc_info=True)
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
        logger.info("[ClientService] تعديل العميل ID: %s", client_id)

        try:
            existing_client = self.repo.get_client_by_id(client_id)
            if not existing_client:
                raise LookupError("العميل غير موجود للتعديل")

            # ⚡ سياسات الشعار: keep / replace / delete
            logo_requested = "logo_data" in new_data
            incoming_logo = new_data.get("logo_data")
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
            logo_action = "none"

            if logo_requested and incoming_logo == "__DELETE__":
                # delete logo
                new_data["logo_data"] = ""
                new_data["logo_path"] = ""
                new_data["has_logo"] = False
                new_data["logo_last_synced"] = now_iso
                logo_action = "delete"
                logger.info("[ClientService] 🗑️ حذف logo_data")
            elif logo_requested and incoming_logo:
                # replace logo
                new_data["has_logo"] = True
                new_data["logo_last_synced"] = now_iso
                logo_action = "replace"
                logger.info("[ClientService] 📷 تحديث logo_data (%s حرف)", len(str(incoming_logo)))
            else:
                # keep logo as-is (do not delete implicitly)
                if existing_client.logo_data:
                    new_data["logo_data"] = existing_client.logo_data
                new_data["logo_path"] = new_data.get("logo_path", existing_client.logo_path)
                new_data["has_logo"] = bool(
                    getattr(existing_client, "has_logo", False) or existing_client.logo_data
                )
                new_data["logo_last_synced"] = getattr(existing_client, "logo_last_synced", None)
                if existing_client.logo_data:
                    logger.info(
                        "[ClientService] 📷 الاحتفاظ بـ logo_data القديم (%s حرف)",
                        len(existing_client.logo_data),
                    )

            updated_client_schema = existing_client.model_copy(update=new_data)
            saved_client = self.repo.update_client(client_id, updated_client_schema)
            self.invalidate_cache()  # ⚡ إبطال الـ cache
            # ⚡ إرسال إشارة التحديث
            app_signals.emit_data_changed("clients")

            # إشعار آمن بدون استيراد واجهة المستخدم مباشرة
            if logo_action in {"replace", "delete", "none"}:
                notify_operation("updated", "client", updated_client_schema.name)

            logger.info("[ClientService] ✅ تم تعديل العميل %s", updated_client_schema.name)
            return saved_client

        except Exception as e:
            logger.error("[ClientService] فشل تعديل العميل: %s", e, exc_info=True)
            raise

    def get_client_by_id(self, client_id: str, ensure_logo: bool = False) -> schemas.Client | None:
        """
        جلب عميل واحد بالمعرف

        Args:
            client_id: معرف العميل

        Returns:
            بيانات العميل أو None إذا لم يُعثر عليه
        """
        try:
            client = self.repo.get_client_by_id(client_id)
            if not client:
                return None
            if ensure_logo and bool(getattr(client, "has_logo", False)) and not client.logo_data:
                self.fetch_client_logo_on_demand(client_id)
                client = self.repo.get_client_by_id(client_id)
            return client
        except Exception as e:
            logger.error("[ClientService] فشل جلب العميل %s: %s", client_id, e, exc_info=True)
            return None

    def fetch_client_logo_on_demand(self, client_id: str) -> bool:
        """جلب شعار العميل عند الطلب وتحديث الواجهة دون إعادة تحميل كاملة."""
        try:
            result = bool(self.repo.fetch_client_logo_on_demand(client_id))
            if result:
                self.invalidate_cache()
                app_signals.emit_client_logo_loaded(str(client_id))
            return result
        except Exception as e:
            logger.error("[ClientService] فشل جلب شعار العميل عند الطلب %s: %s", client_id, e)
            return False

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
            logger.error("[ClientService] فشل جلب العميل بالاسم %s: %s", name, e, exc_info=True)
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
        logger.info("[ClientService] استلام طلب حذف العميل نهائياً ID: %s", client_id)

        try:
            success = self.repo.delete_client_permanently(client_id)
            if success:
                self.invalidate_cache()  # ⚡ إبطال الـ cache
                # ⚡ إرسال إشارة التحديث
                app_signals.emit_data_changed("clients")
                # 🔔 إشعار - تحويل client_id لـ string
                notify_operation("deleted", "client", str(client_id))
                logger.info("[ClientService] ✅ تم حذف العميل نهائياً")
            return success
        except Exception as e:
            logger.error("[ClientService] فشل حذف العميل: %s", e, exc_info=True)
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
            logger.error("[ClientService] فشل جلب العملاء المؤرشفين: %s", e, exc_info=True)
            return []

    def search_clients(
        self, query: str, fields: list[str] | None = None, limit: int = 20
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

            logger.debug("[ClientService] تم العثور على %s عميل للبحث: %s", len(results), query)
            return results

        except Exception as e:
            logger.error("[ClientService] فشل البحث في العملاء: %s", e, exc_info=True)
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
                "by_country": countries,
            }

            logger.info(
                "[ClientService] إحصائيات العملاء: %s نشط، %s مؤرشف",
                stats["total_active"],
                stats["total_archived"],
            )
            return stats

        except Exception as e:
            logger.error("[ClientService] فشل جلب إحصائيات العملاء: %s", e, exc_info=True)
            return {
                "total_active": 0,
                "total_archived": 0,
                "total": 0,
                "by_type": {},
                "by_country": {},
            }

    def get_client_financial_totals(self) -> tuple[dict, dict]:
        """
        ✅ جلب الإجماليات المالية للعملاء (المشاريع والمدفوعات)

        Returns:
            tuple: (client_projects_total, client_payments_total)
                - client_projects_total: {client_id: total_amount}
                - client_payments_total: {client_id: total_paid}
        """
        try:
            cursor = self.repo.get_cursor()
            try:
                # إجمالي المشاريع لكل عميل
                cursor.execute(
                    """
                    SELECT client_id, SUM(total_amount) as total_projects
                    FROM projects
                    WHERE status != 'مؤرشف' AND status != 'ملغي'
                    GROUP BY client_id
                """
                )
                projects_result = cursor.fetchall()

                client_projects_total = {
                    str(row[0]): float(row[1]) if row[1] else 0.0 for row in projects_result
                }

                # إجمالي المدفوعات لكل عميل
                cursor.execute(
                    """
                    SELECT client_id, SUM(amount) as total_paid
                    FROM payments
                    WHERE client_id IS NOT NULL AND client_id != ''
                    GROUP BY client_id
                """
                )
                payments_result = cursor.fetchall()

                client_payments_total = {
                    str(row[0]): float(row[1]) if row[1] else 0.0 for row in payments_result
                }

                return client_projects_total, client_payments_total
            finally:
                cursor.close()

        except Exception as e:
            # During app shutdown, repository may already be closed.
            if "sqlite_closed" in str(e).lower():
                logger.debug(
                    "[ClientService] تم تجاهل جلب الإجماليات: قاعدة البيانات مغلقة أثناء الإغلاق"
                )
            else:
                logger.error("[ClientService] فشل جلب الإجماليات المالية: %s", e, exc_info=True)
            return {}, {}
