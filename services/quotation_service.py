from datetime import datetime, timedelta

from core import schemas
from core.event_bus import EventBus
from core.logger import get_logger
from core.repository import Repository
from core.signals import app_signals

# (جديد) هنحتاج قسم المشاريع
from services.project_service import ProjectService

logger = get_logger(__name__)


class QuotationService:
    """
    ⚡ قسم عروض الأسعار - محسّن للأداء
    يتعامل مع إنشاء وإدارة عروض الأسعار وتحويلها لمشاريع
    """

    def __init__(
        self,
        repository: Repository,
        event_bus: EventBus,
        project_service: ProjectService,
    ):
        """
        تهيئة خدمة عروض الأسعار

        Args:
            repository: مخزن البيانات الرئيسي
            event_bus: نظام الأحداث للتواصل بين الخدمات
            project_service: خدمة المشاريع لتحويل العروض
        """
        self.repo = repository
        self.bus = event_bus
        self.project_service = project_service
        
        # ⚡ Cache لعروض الأسعار
        self._cache_time: float = 0
        self._cached_quotations: list[schemas.Quotation] | None = None
        self._cache_ttl = 30  # 30 ثانية
        
        logger.info("⚡ قسم عروض الأسعار (QuotationService) جاهز")

    def invalidate_cache(self):
        """⚡ إبطال الـ cache"""
        self._cached_quotations = None
        self._cache_time = 0

    def get_all_quotations(self) -> list[schemas.Quotation]:
        """
        ⚡ جلب كل عروض الأسعار (مع cache)

        Returns:
            قائمة بجميع عروض الأسعار
        """
        import time
        try:
            # ⚡ استخدام الـ cache
            now = time.time()
            if self._cached_quotations and (now - self._cache_time) < self._cache_ttl:
                return self._cached_quotations

            # جلب من قاعدة البيانات
            quotations = self.repo.get_all_quotations()

            # تحديث الـ cache
            self._cached_quotations = quotations
            self._cache_time = now

            return quotations
        except Exception as e:
            logger.error(f"[QuotationService] فشل جلب عروض الأسعار: {e}", exc_info=True)
            return []

    def create_new_quotation(self, new_data_dict: dict) -> schemas.Quotation:
        """
        إنشاء عرض سعر جديد

        Args:
            new_data_dict: بيانات عرض السعر الجديد

        Returns:
            عرض السعر المُنشأ

        Raises:
            Exception: في حالة فشل إنشاء عرض السعر
        """
        logger.info("[QuotationService] استلام طلب إنشاء عرض سعر جديد")
        try:
            items_list = new_data_dict.get("items", [])
            subtotal = 0.0
            normalized_items: list[schemas.QuotationItem] = []

            for item in items_list:
                if isinstance(item, dict):
                    item_obj = schemas.QuotationItem(**item)
                else:
                    item_obj = item
                item_obj.total = item_obj.quantity * item_obj.unit_price
                subtotal += item_obj.total
                normalized_items.append(item_obj)

            discount_rate = new_data_dict.get('discount_rate', 0.0)
            discount_amount = subtotal * (discount_rate / 100)
            taxable_amount = subtotal - discount_amount

            tax_rate = new_data_dict.get('tax_rate', 0.0)
            tax_amount = taxable_amount * (tax_rate / 100)
            total_amount = taxable_amount + tax_amount

            new_data_dict['subtotal'] = subtotal
            new_data_dict['discount_rate'] = discount_rate
            new_data_dict['discount_amount'] = discount_amount
            new_data_dict['tax_rate'] = tax_rate
            new_data_dict['tax_amount'] = tax_amount
            new_data_dict['total_amount'] = total_amount
            new_data_dict['items'] = normalized_items

            if 'quote_number' not in new_data_dict:
                new_data_dict['quote_number'] = f"QUOTE-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            new_quote_schema = schemas.Quotation(**new_data_dict)
            created_quote = self.repo.create_quotation(new_quote_schema)
            # ⚡ إرسال إشارة التحديث
            app_signals.emit_data_changed('quotations')

            print(f"INFO: [QuotationService] تم حفظ عرض السعر بنجاح برقم: {created_quote.quote_number}")
            return created_quote

        except Exception as e:
            print(f"ERROR: [QuotationService] فشل إنشاء عرض السعر: {e}")
            raise

    def convert_quotation_to_invoice(self, quote: schemas.Quotation):
        """
        (معدلة) "الزرار السحري"
        يحول عرض السعر المقبول إلى "مشروع" جديد.
        """
        print(f"INFO: [QuotationService] جاري تحويل عرض السعر {quote.quote_number} إلى مشروع...")

        # 1. تجهيز بيانات المشروع من عرض السعر
        project_items = []
        for item in quote.items:
            project_items.append(schemas.ProjectItem(
                service_id=item.service_id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=item.total
            ))

        project_data_dict = {
            "client_id": quote.client_id,
            "name": f"مشروع - {quote.quote_number}",
            "status": schemas.ProjectStatus.ACTIVE,
            "start_date": datetime.now(),
            "end_date": datetime.now() + timedelta(days=30),
            "discount_rate": quote.discount_rate,
            "tax_rate": quote.tax_rate,
            "currency": quote.currency,
            "items": project_items,
            "project_notes": f"تم الإنشاء بناءً على عرض السعر رقم: {quote.quote_number}\n{quote.notes or ''}"
        }

        # 2. (الجديد) إرسال الأمر لـ "قسم المشاريع" مباشرة
        try:
            self.project_service.create_project(project_data_dict, payment_data={})
            print("INFO: [QuotationService] تم إرسال طلب إنشاء المشروع.")

            # 3. تحديث حالة عرض السعر
            self.repo.update_quotation_status(quote.quote_number, schemas.QuotationStatus.ACCEPTED)
            print(f"INFO: [QuotationService] تم تحديث حالة عرض السعر {quote.quote_number} إلى 'مقبول'.")

            return True
        except Exception as e:
            print(f"ERROR: [QuotationService] فشل تحويل عرض السعر لمشروع: {e}")
            raise

    def update_quotation(self, quote_number: str, new_data_dict: dict) -> schemas.Quotation | None:
        print(f"INFO: [QuotationService] استلام طلب تعديل عرض سعر: {quote_number}")

        try:
            items_list = new_data_dict.get("items", [])
            subtotal = 0.0
            for index, item in enumerate(items_list):
                if isinstance(item, dict):
                    item_obj = schemas.QuotationItem(**item)
                else:
                    item_obj = item
                item_obj.total = item_obj.quantity * item_obj.unit_price
                items_list[index] = item_obj
                subtotal += item_obj.total

            discount_rate = new_data_dict.get('discount_rate', 0.0)
            discount_amount = subtotal * (discount_rate / 100)
            taxable_amount = subtotal - discount_amount

            tax_rate = new_data_dict.get('tax_rate', 0.0)
            tax_amount = taxable_amount * (tax_rate / 100)
            total_amount = taxable_amount + tax_amount

            new_data_dict['subtotal'] = subtotal
            new_data_dict['discount_rate'] = discount_rate
            new_data_dict['discount_amount'] = discount_amount
            new_data_dict['tax_rate'] = tax_rate
            new_data_dict['tax_amount'] = tax_amount
            new_data_dict['total_amount'] = total_amount
            new_data_dict['items'] = items_list

            old_quote = self.repo.get_quotation_by_number(quote_number)
            if not old_quote:
                raise Exception("عرض السعر الأصلي غير موجود")

            updated_quote_schema = old_quote.model_copy(update=new_data_dict)
            saved_quote = self.repo.update_quotation(quote_number, updated_quote_schema)
            # ⚡ إرسال إشارة التحديث
            app_signals.emit_data_changed('quotations')

            print(f"SUCCESS: [QuotationService] تم تعديل عرض السعر {quote_number}.")
            return saved_quote

        except Exception as e:
            print(f"ERROR: [QuotationService] فشل تعديل عرض السعر: {e}")
            raise
