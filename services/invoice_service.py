# الملف: services/invoice_service.py


from core import schemas
from core.event_bus import EventBus
from core.logger import get_logger
from core.repository import Repository

logger = get_logger(__name__)


class InvoiceService:
    """
    خدمة الفواتير - تتعامل مع إنشاء وإدارة الفواتير
    """

    def __init__(self, repository: Repository, event_bus: EventBus):
        """
        تهيئة خدمة الفواتير

        Args:
            repository: مخزن البيانات الرئيسي
            event_bus: نظام الأحداث للتواصل بين الخدمات
        """
        self.repo = repository
        self.bus = event_bus
        logger.info("[InvoiceService] خدمة الفواتير جاهزة")

    def get_all_invoices(self) -> list[schemas.Invoice]:
        """
        جلب كل الفواتير

        Returns:
            قائمة بجميع الفواتير
        """
        try:
            return self.repo.get_all_invoices()
        except Exception as e:
            logger.error(f"[InvoiceService] فشل جلب الفواتير: {e}", exc_info=True)
            return []

    def create_invoice(self, invoice_data: schemas.Invoice) -> schemas.Invoice:
        """
        إنشاء فاتورة جديدة مع إرسال الحدث للمحاسبة

        Args:
            invoice_data: بيانات الفاتورة الجديدة

        Returns:
            الفاتورة المُنشأة

        Raises:
            Exception: في حالة فشل إنشاء الفاتورة
        """
        logger.info(f"[InvoiceService] استلام طلب إنشاء فاتورة: {invoice_data.invoice_number}")
        try:
            created_invoice = self.repo.create_invoice(invoice_data)
            # إرسال الحدث للروبوت المحاسبي
            self.bus.publish('INVOICE_CREATED', {'invoice': created_invoice})
            logger.info(f"[InvoiceService] تم إنشاء الفاتورة {created_invoice.invoice_number}")
            return created_invoice
        except Exception as e:
            logger.error(f"[InvoiceService] فشل إنشاء الفاتورة: {e}", exc_info=True)
            raise

    def update_invoice(self, invoice_id: str, invoice_data: schemas.Invoice) -> schemas.Invoice | None:
        """
        تعديل فاتورة موجودة

        Args:
            invoice_id: معرف الفاتورة
            invoice_data: البيانات الجديدة للفاتورة

        Returns:
            الفاتورة المُحدثة أو None في حالة الفشل

        Raises:
            Exception: في حالة فشل التحديث
        """
        logger.info(f"[InvoiceService] استلام طلب تعديل فاتورة: {invoice_data.invoice_number}")
        try:
            updated_invoice = self.repo.update_invoice(invoice_id, invoice_data)
            if updated_invoice:
                # إرسال الحدث للروبوت المحاسبي
                self.bus.publish('INVOICE_EDITED', {'invoice': updated_invoice})
                logger.info(f"[InvoiceService] تم تعديل الفاتورة {updated_invoice.invoice_number}")
            return updated_invoice
        except Exception as e:
            logger.error(f"[InvoiceService] فشل تعديل الفاتورة: {e}", exc_info=True)
            raise

    def void_invoice(self, invoice_id: str) -> bool:
        """
        إلغاء فاتورة

        Args:
            invoice_id: معرف الفاتورة المراد إلغاؤها

        Returns:
            True في حالة النجاح، False في حالة الفشل

        Raises:
            Exception: في حالة فشل الإلغاء
        """
        logger.info(f"[InvoiceService] استلام طلب إلغاء فاتورة: {invoice_id}")
        try:
            invoice = self.repo.get_invoice_by_id(invoice_id)
            if not invoice:
                raise Exception("الفاتورة غير موجودة")

            # تحديث حالة الفاتورة لملغاة
            invoice.status = schemas.InvoiceStatus.VOID
            updated_invoice = self.repo.update_invoice(invoice_id, invoice)

            if updated_invoice:
                # إرسال الحدث للروبوت المحاسبي
                self.bus.publish('INVOICE_VOIDED', updated_invoice)
                logger.info(f"[InvoiceService] تم إلغاء الفاتورة {updated_invoice.invoice_number}")
                return True
            return False
        except Exception as e:
            logger.error(f"[InvoiceService] فشل إلغاء الفاتورة: {e}", exc_info=True)
            raise

    def get_invoice_by_id(self, invoice_id: str) -> schemas.Invoice | None:
        """
        جلب فاتورة بالمعرف

        Args:
            invoice_id: معرف الفاتورة

        Returns:
            بيانات الفاتورة أو None إذا لم تُعثر عليها
        """
        try:
            return self.repo.get_invoice_by_id(invoice_id)
        except Exception as e:
            logger.error(f"[InvoiceService] فشل جلب الفاتورة: {e}", exc_info=True)
            return None
