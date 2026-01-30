# الملف: services/quotation_service.py
"""
📋 خدمة عروض الأسعار (Quotation Service) - Production Grade
============================================================
نظام متكامل لإدارة عروض الأسعار:
- إنشاء عروض احترافية
- تتبع حالة العروض
- تحويل العروض لمشاريع
- تصدير PDF
"""

from datetime import datetime, timedelta
from typing import Any

from core.event_bus import EventBus
from core.logger import get_logger
from core.repository import Repository

try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass

logger = get_logger(__name__)


class QuotationService:
    """خدمة عروض الأسعار"""

    # شروط وأحكام افتراضية
    DEFAULT_TERMS = """
1. هذا العرض صالح لمدة 30 يوماً من تاريخ الإصدار.
2. الأسعار المذكورة لا تشمل ضريبة القيمة المضافة ما لم يُذكر خلاف ذلك.
3. يتم البدء في العمل بعد استلام الدفعة المقدمة المتفق عليها.
4. أي تعديلات على نطاق العمل قد تؤثر على السعر النهائي.
5. جميع حقوق الملكية الفكرية تنتقل للعميل بعد السداد الكامل.
"""

    DEFAULT_PAYMENT_TERMS = """
- 50% دفعة مقدمة عند التعاقد
- 50% عند التسليم النهائي
"""

    def __init__(self, repository: Repository, event_bus: EventBus = None):
        self.repo = repository
        self.bus = event_bus
        logger.info("[QuotationService] ✅ خدمة عروض الأسعار جاهزة")

    # ==================== العروض ====================
    def get_all_quotations(self) -> list[dict]:
        """جلب جميع عروض الأسعار"""
        return self.repo.get_all_quotations()

    def get_quotation(self, quotation_id: int) -> dict | None:
        """جلب عرض سعر بالمعرف"""
        return self.repo.get_quotation_by_id(quotation_id)

    def get_client_quotations(self, client_id: str) -> list[dict]:
        """جلب عروض أسعار عميل"""
        return self.repo.get_quotations_by_client(client_id)

    def get_quotations_by_status(self, status: str) -> list[dict]:
        """جلب العروض حسب الحالة"""
        return self.repo.get_quotations_by_status(status)

    def get_pending_quotations(self) -> list[dict]:
        """جلب العروض المعلقة (مسودة + مرسل)"""
        drafts = self.repo.get_quotations_by_status("مسودة")
        sent = self.repo.get_quotations_by_status("مرسل")
        return drafts + sent

    def get_expiring_quotations(self, days: int = 7) -> list[dict]:
        """جلب العروض التي ستنتهي قريباً"""
        all_quotes = self.repo.get_all_quotations()
        expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        return [
            q for q in all_quotes 
            if q.get("status") in ["مسودة", "مرسل", "تم الاطلاع"]
            and q.get("valid_until", "") <= expiry_date
            and q.get("valid_until", "") >= today
        ]

    def create_quotation(self, data: dict) -> dict | None:
        """إنشاء عرض سعر جديد"""
        # توليد رقم العرض إذا لم يكن موجوداً
        if not data.get("quotation_number"):
            data["quotation_number"] = self.repo.generate_quotation_number()
        
        # تاريخ الإصدار
        if not data.get("issue_date"):
            data["issue_date"] = datetime.now().strftime("%Y-%m-%d")
        
        # صالح حتى (30 يوم افتراضياً)
        if not data.get("valid_until"):
            valid_date = datetime.now() + timedelta(days=30)
            data["valid_until"] = valid_date.strftime("%Y-%m-%d")
        
        # الشروط الافتراضية
        if not data.get("terms_and_conditions"):
            data["terms_and_conditions"] = self.DEFAULT_TERMS
        if not data.get("payment_terms"):
            data["payment_terms"] = self.DEFAULT_PAYMENT_TERMS
        
        # حساب الإجماليات
        data = self._calculate_totals(data)
        
        result = self.repo.create_quotation(data)
        if result and self.bus:
            self.bus.publish("QUOTATION_CREATED", {"quotation": result})
        return result

    def update_quotation(self, quotation_id: int, data: dict) -> dict | None:
        """تحديث عرض سعر"""
        # حساب الإجماليات
        data = self._calculate_totals(data)
        
        result = self.repo.update_quotation(quotation_id, data)
        if result and self.bus:
            self.bus.publish("QUOTATION_UPDATED", {"quotation": result})
        return result

    def delete_quotation(self, quotation_id: int) -> bool:
        """حذف عرض سعر"""
        result = self.repo.delete_quotation(quotation_id)
        if result and self.bus:
            self.bus.publish("QUOTATION_DELETED", {"quotation_id": quotation_id})
        return result

    def duplicate_quotation(self, quotation_id: int) -> dict | None:
        """نسخ عرض سعر"""
        original = self.repo.get_quotation_by_id(quotation_id)
        if not original:
            return None
        
        # إنشاء نسخة جديدة
        new_data = {
            "client_id": original["client_id"],
            "client_name": original["client_name"],
            "title": f"{original['title']} (نسخة)",
            "description": original["description"],
            "scope_of_work": original["scope_of_work"],
            "items": original["items"],
            "discount_rate": original["discount_rate"],
            "tax_rate": original["tax_rate"],
            "currency": original["currency"],
            "terms_and_conditions": original["terms_and_conditions"],
            "payment_terms": original["payment_terms"],
            "delivery_time": original["delivery_time"],
            "warranty": original["warranty"],
            "notes": original["notes"],
            "status": "مسودة"
        }
        
        return self.create_quotation(new_data)

    # ==================== تغيير الحالة ====================
    def mark_as_sent(self, quotation_id: int) -> bool:
        """تحديد العرض كمرسل"""
        result = self.repo.update_quotation_status(quotation_id, "مرسل")
        if result and self.bus:
            self.bus.publish("QUOTATION_SENT", {"quotation_id": quotation_id})
        return result

    def mark_as_viewed(self, quotation_id: int) -> bool:
        """تحديد العرض كتم الاطلاع"""
        return self.repo.update_quotation_status(quotation_id, "تم الاطلاع")

    def accept_quotation(self, quotation_id: int) -> bool:
        """قبول العرض"""
        result = self.repo.update_quotation_status(quotation_id, "مقبول")
        if result and self.bus:
            self.bus.publish("QUOTATION_ACCEPTED", {"quotation_id": quotation_id})
        return result

    def reject_quotation(self, quotation_id: int) -> bool:
        """رفض العرض"""
        result = self.repo.update_quotation_status(quotation_id, "مرفوض")
        if result and self.bus:
            self.bus.publish("QUOTATION_REJECTED", {"quotation_id": quotation_id})
        return result

    def mark_as_expired(self, quotation_id: int) -> bool:
        """تحديد العرض كمنتهي"""
        return self.repo.update_quotation_status(quotation_id, "منتهي")

    # ==================== التحويل لمشروع ====================
    def convert_to_project(self, quotation_id: int, project_service) -> dict | None:
        """تحويل عرض سعر إلى مشروع"""
        quotation = self.repo.get_quotation_by_id(quotation_id)
        if not quotation:
            safe_print(f"ERROR: [QuotationService] عرض السعر غير موجود: {quotation_id}")
            return None
        
        # إنشاء بيانات المشروع من العرض
        project_data = {
            "name": quotation["title"],
            "client_id": quotation["client_id"],
            "description": quotation["description"] or quotation["scope_of_work"],
            "items": quotation["items"],
            "subtotal": quotation["subtotal"],
            "discount_rate": quotation["discount_rate"],
            "discount_amount": quotation["discount_amount"],
            "tax_rate": quotation["tax_rate"],
            "tax_amount": quotation["tax_amount"],
            "total_amount": quotation["total_amount"],
            "currency": quotation["currency"],
            "project_notes": f"تم التحويل من عرض سعر رقم: {quotation['quotation_number']}",
            "status": "نشط"
        }
        
        # إنشاء المشروع
        project = project_service.create_project(project_data)
        if project:
            # تحديث العرض
            project_id = project.get("id") or project.get("_mongo_id") or project.get("name")
            self.repo.convert_quotation_to_project(quotation_id, str(project_id))
            
            if self.bus:
                self.bus.publish("QUOTATION_CONVERTED", {
                    "quotation_id": quotation_id,
                    "project": project
                })
            
            safe_print(f"SUCCESS: [QuotationService] ✅ تم تحويل العرض لمشروع: {project_id}")
            return project
        
        return None

    # ==================== الحسابات ====================
    def _calculate_totals(self, data: dict) -> dict:
        """حساب الإجماليات"""
        items = data.get("items", [])
        
        # حساب إجمالي البنود
        subtotal = 0
        for item in items:
            qty = float(item.get("quantity", 1))
            price = float(item.get("unit_price", 0))
            item_discount = float(item.get("discount_amount", 0))
            item_total = (qty * price) - item_discount
            item["total"] = item_total
            subtotal += item_total
        
        data["subtotal"] = subtotal
        
        # حساب الخصم الإجمالي
        discount_rate = float(data.get("discount_rate", 0))
        if discount_rate > 0:
            data["discount_amount"] = subtotal * (discount_rate / 100)
        else:
            data["discount_amount"] = float(data.get("discount_amount", 0))
        
        after_discount = subtotal - data["discount_amount"]
        
        # حساب الضريبة
        tax_rate = float(data.get("tax_rate", 0))
        if tax_rate > 0:
            data["tax_amount"] = after_discount * (tax_rate / 100)
        else:
            data["tax_amount"] = 0
        
        # الإجمالي النهائي
        data["total_amount"] = after_discount + data["tax_amount"]
        
        return data

    # ==================== الإحصائيات ====================
    def get_statistics(self) -> dict:
        """جلب إحصائيات عروض الأسعار"""
        return self.repo.get_quotation_statistics()

    def get_conversion_rate(self) -> float:
        """حساب معدل التحويل (العروض المقبولة / إجمالي العروض)"""
        stats = self.get_statistics()
        return stats.get("acceptance_rate", 0)
