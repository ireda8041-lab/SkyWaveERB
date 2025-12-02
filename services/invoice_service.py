# الملف: services/invoice_service.py

from core.repository import Repository
from core.event_bus import EventBus
from core import schemas
from typing import List, Optional

class InvoiceService:
    """خدمة الفواتير - تتعامل مع إنشاء وإدارة الفواتير"""

    def __init__(self, repository: Repository, event_bus: EventBus):
        self.repo = repository
        self.bus = event_bus
        print("INFO: [InvoiceService] خدمة الفواتير جاهزة.")

    def get_all_invoices(self) -> List[schemas.Invoice]:
        """جلب كل الفواتير"""
        try:
            return self.repo.get_all_invoices()
        except Exception as e:
            print(f"ERROR: [InvoiceService] فشل جلب الفواتير: {e}")
            return []

    def create_invoice(self, invoice_data: schemas.Invoice) -> schemas.Invoice:
        """إنشاء فاتورة جديدة مع إرسال الحدث للمحاسبة"""
        print(f"INFO: [InvoiceService] استلام طلب إنشاء فاتورة: {invoice_data.invoice_number}")
        try:
            created_invoice = self.repo.create_invoice(invoice_data)
            # إرسال الحدث للروبوت المحاسبي
            self.bus.publish('INVOICE_CREATED', {'invoice': created_invoice})
            print(f"SUCCESS: [InvoiceService] تم إنشاء الفاتورة {created_invoice.invoice_number}")
            return created_invoice
        except Exception as e:
            print(f"ERROR: [InvoiceService] فشل إنشاء الفاتورة: {e}")
            raise

    def update_invoice(self, invoice_id: str, invoice_data: schemas.Invoice) -> Optional[schemas.Invoice]:
        """تعديل فاتورة موجودة"""
        print(f"INFO: [InvoiceService] استلام طلب تعديل فاتورة: {invoice_data.invoice_number}")
        try:
            updated_invoice = self.repo.update_invoice(invoice_id, invoice_data)
            if updated_invoice:
                # إرسال الحدث للروبوت المحاسبي
                self.bus.publish('INVOICE_EDITED', {'invoice': updated_invoice})
                print(f"SUCCESS: [InvoiceService] تم تعديل الفاتورة {updated_invoice.invoice_number}")
            return updated_invoice
        except Exception as e:
            print(f"ERROR: [InvoiceService] فشل تعديل الفاتورة: {e}")
            raise

    def void_invoice(self, invoice_id: str) -> bool:
        """إلغاء فاتورة"""
        print(f"INFO: [InvoiceService] استلام طلب إلغاء فاتورة: {invoice_id}")
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
                print(f"SUCCESS: [InvoiceService] تم إلغاء الفاتورة {updated_invoice.invoice_number}")
                return True
            return False
        except Exception as e:
            print(f"ERROR: [InvoiceService] فشل إلغاء الفاتورة: {e}")
            raise

    def get_invoice_by_id(self, invoice_id: str) -> Optional[schemas.Invoice]:
        """جلب فاتورة بالمعرف"""
        try:
            return self.repo.get_invoice_by_id(invoice_id)
        except Exception as e:
            print(f"ERROR: [InvoiceService] فشل جلب الفاتورة: {e}")
            return None