# الملف: services/invoice_service.py


from core import schemas
from core.event_bus import EventBus
from core.logger import get_logger
from core.repository import Repository
from core.signals import app_signals

# إشعارات العمليات
try:
    from core.notification_bridge import notify_operation
except ImportError:

    def notify_operation(action, entity_type, entity_name):
        pass


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
            logger.error("[InvoiceService] فشل جلب الفواتير: %s", e, exc_info=True)
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
        logger.info("[InvoiceService] استلام طلب إنشاء فاتورة: %s", invoice_data.invoice_number)
        try:
            created_invoice = self.repo.create_invoice(invoice_data)
            # إرسال الحدث للروبوت المحاسبي
            self.bus.publish("INVOICE_CREATED", {"invoice": created_invoice})
            # ⚡ إرسال إشارة التحديث الفوري
            app_signals.emit_data_changed("invoices")
            # 🔔 إشعار
            notify_operation("created", "invoice", created_invoice.invoice_number)
            logger.info("[InvoiceService] تم إنشاء الفاتورة %s", created_invoice.invoice_number)
            return created_invoice
        except Exception as e:
            logger.error("[InvoiceService] فشل إنشاء الفاتورة: %s", e, exc_info=True)
            raise

    def update_invoice(
        self, invoice_id: str, invoice_data: schemas.Invoice
    ) -> schemas.Invoice | None:
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
        logger.info("[InvoiceService] استلام طلب تعديل فاتورة: %s", invoice_data.invoice_number)
        try:
            updated_invoice = self.repo.update_invoice(invoice_id, invoice_data)
            if updated_invoice:
                # إرسال الحدث للروبوت المحاسبي
                self.bus.publish("INVOICE_EDITED", {"invoice": updated_invoice})
                # ⚡ إرسال إشارة التحديث الفوري
                app_signals.emit_data_changed("invoices")
                # 🔔 إشعار
                notify_operation("updated", "invoice", updated_invoice.invoice_number)
                logger.info("[InvoiceService] تم تعديل الفاتورة %s", updated_invoice.invoice_number)
            return updated_invoice
        except Exception as e:
            logger.error("[InvoiceService] فشل تعديل الفاتورة: %s", e, exc_info=True)
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
        logger.info("[InvoiceService] استلام طلب إلغاء فاتورة: %s", invoice_id)
        try:
            invoice = self.repo.get_invoice_by_id(invoice_id)
            if not invoice:
                raise ValueError("الفاتورة غير موجودة")

            # تحديث حالة الفاتورة لملغاة
            invoice.status = schemas.InvoiceStatus.VOID
            updated_invoice = self.repo.update_invoice(invoice_id, invoice)

            if updated_invoice:
                # إرسال الحدث للروبوت المحاسبي
                self.bus.publish("INVOICE_VOIDED", updated_invoice)
                # ⚡ إرسال إشارة التحديث الفوري
                app_signals.emit_data_changed("invoices")
                # 🔔 إشعار
                notify_operation("voided", "invoice", updated_invoice.invoice_number)
                logger.info("[InvoiceService] تم إلغاء الفاتورة %s", updated_invoice.invoice_number)
                return True
            return False
        except Exception as e:
            logger.error("[InvoiceService] فشل إلغاء الفاتورة: %s", e, exc_info=True)
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
            logger.error("[InvoiceService] فشل جلب الفاتورة: %s", e, exc_info=True)
            return None
