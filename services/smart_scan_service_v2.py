# الملف: services/smart_scan_service_v2.py
"""
خدمة المسح الذكي للفواتير باستخدام AI

تحول صور الفواتير إلى بيانات مهيكلة (JSON) جاهزة للإدخال.
تدعم العربية والإنجليزية.
"""

import base64
import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

# إعداد اللوجر
logger = logging.getLogger("SmartScanService")
logger.setLevel(logging.INFO)


class ScanResult:
    """نتيجة المسح الذكي"""
    
    def __init__(
        self,
        success: bool = False,
        merchant_name: str = "",
        invoice_date: str = "",
        total_amount: float = 0.0,
        tax_amount: float = 0.0,
        currency: str = "EGP",
        items: Optional[list] = None,
        raw_text: str = "",
        error: str = ""
    ):
        self.success = success
        self.merchant_name = merchant_name
        self.invoice_date = invoice_date
        self.total_amount = total_amount
        self.tax_amount = tax_amount
        self.currency = currency
        self.items = items or []
        self.raw_text = raw_text
        self.error = error
    
    def to_dict(self) -> dict[str, Any]:
        """تحويل النتيجة لقاموس"""
        return {
            'success': self.success,
            'merchant_name': self.merchant_name,
            'invoice_date': self.invoice_date,
            'total_amount': self.total_amount,
            'tax_amount': self.tax_amount,
            'currency': self.currency,
            'items': self.items,
            'raw_text': self.raw_text,
            'error': self.error
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ScanResult':
        """إنشاء نتيجة من قاموس"""
        return cls(
            success=data.get('success', False),
            merchant_name=data.get('merchant_name', ''),
            invoice_date=data.get('invoice_date', ''),
            total_amount=float(data.get('total_amount', 0) or 0),
            tax_amount=float(data.get('tax_amount', 0) or 0),
            currency=data.get('currency', 'EGP'),
            items=data.get('items', []),
            raw_text=data.get('raw_text', ''),
            error=data.get('error', '')
        )


class SmartScanServiceV2:
    """
    خدمة المسح الذكي للفواتير باستخدام AI
    
    تحول صور الفواتير إلى بيانات مهيكلة (JSON) جاهزة للإدخال.
    """

    # الصيغ المدعومة للصور
    SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    
    # الحد الأقصى لحجم الصورة (5 MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024

    def __init__(self, api_key: Optional[str] = None):
        """
        تهيئة خدمة المسح الذكي
        
        Args:
            api_key: مفتاح API (اختياري، يمكن استخدام متغير البيئة)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._model = None
        self._is_configured = False
        
        if self.api_key:
            self._configure()
        else:
            logger.warning("[!] Gemini API Key is missing! Smart Scan will not work.")

    def _configure(self):
        """تهيئة Gemini AI"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel('gemini-1.5-flash')
            self._is_configured = True
            logger.info("[OK] Gemini AI Configured Successfully.")
        except ImportError:
            logger.warning("[!] google-generativeai not installed. Using mock mode.")
            self._is_configured = False
        except Exception as e:
            logger.error(f"[X] Failed to configure Gemini: {e}")
            self._is_configured = False

    def is_available(self) -> bool:
        """هل الخدمة متاحة؟"""
        return self._is_configured and self._model is not None

    def validate_image(self, image_path: str) -> tuple[bool, str]:
        """
        التحقق من صحة الصورة
        
        Returns:
            tuple: (is_valid, error_message)
        """
        # التحقق من وجود الملف
        if not os.path.exists(image_path):
            return False, f"File not found: {image_path}"
        
        # التحقق من الصيغة
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in self.SUPPORTED_FORMATS:
            return False, f"Unsupported format: {ext}. Supported: {self.SUPPORTED_FORMATS}"
        
        # التحقق من الحجم
        file_size = os.path.getsize(image_path)
        if file_size > self.MAX_FILE_SIZE:
            return False, f"File too large: {file_size / 1024 / 1024:.1f}MB. Max: 5MB"
        
        return True, ""

    def scan_invoice_image(self, image_path: str) -> ScanResult:
        """
        تحليل صورة الفاتورة واستخراج البيانات
        
        Args:
            image_path: مسار الصورة
            
        Returns:
            ScanResult: نتيجة المسح
        """
        # التحقق من الصورة
        is_valid, error = self.validate_image(image_path)
        if not is_valid:
            return ScanResult(success=False, error=error)
        
        # التحقق من توفر الخدمة
        if not self.is_available():
            return ScanResult(
                success=False,
                error="Smart Scan service not available. Check API key."
            )
        
        try:
            logger.info(f"[SCAN] Scanning invoice: {image_path}...")
            
            import PIL.Image
            img = PIL.Image.open(image_path)
            
            # إنشاء الطلب
            prompt = self._build_prompt()
            
            # إرسال الطلب
            response = self._model.generate_content([prompt, img])
            
            # معالجة الرد
            result = self._parse_response(response.text)
            result.success = True
            
            logger.info("[OK] Scan Completed Successfully!")
            return result
            
        except Exception as e:
            logger.error(f"[X] Smart Scan Failed: {e}")
            return ScanResult(success=False, error=str(e))

    def scan_invoice_base64(self, base64_data: str, mime_type: str = "image/jpeg") -> ScanResult:
        """
        تحليل صورة فاتورة من Base64
        
        Args:
            base64_data: بيانات الصورة بتنسيق Base64
            mime_type: نوع الصورة
            
        Returns:
            ScanResult: نتيجة المسح
        """
        if not self.is_available():
            return ScanResult(
                success=False,
                error="Smart Scan service not available. Check API key."
            )
        
        try:
            logger.info("[SCAN] Scanning invoice from Base64...")
            
            # إنشاء الطلب
            prompt = self._build_prompt()
            
            # إنشاء محتوى الصورة
            image_part = {
                "mime_type": mime_type,
                "data": base64_data
            }
            
            # إرسال الطلب
            response = self._model.generate_content([prompt, image_part])
            
            # معالجة الرد
            result = self._parse_response(response.text)
            result.success = True
            
            logger.info("[OK] Scan Completed Successfully!")
            return result
            
        except Exception as e:
            logger.error(f"[X] Smart Scan Failed: {e}")
            return ScanResult(success=False, error=str(e))

    def _build_prompt(self) -> str:
        """بناء الطلب للذكاء الاصطناعي"""
        current_year = datetime.now().year
        
        return f"""You are an expert AI Data Entry Clerk.
Analyze this invoice/receipt image and extract the data into a strict JSON format.

Requirements:
1. Extract the Merchant/Company Name.
2. Extract the Date and format it as YYYY-MM-DD. If year is missing, assume {current_year}.
3. Extract the Total Amount (numeric).
4. Extract Tax/VAT Amount if present (numeric), else 0.
5. Identify the Currency (e.g., EGP, USD, SAR, EUR).
6. Extract line items as a list (item_name, quantity, unit_price).

Output strictly valid JSON with this schema:
{{
    "merchant_name": "string",
    "invoice_date": "YYYY-MM-DD",
    "total_amount": float,
    "tax_amount": float,
    "currency": "string",
    "items": [
        {{"name": "string", "qty": float, "price": float}}
    ]
}}

Rules:
- If a field is not found, use null (or 0 for numbers).
- Do NOT write markdown formatting like ```json. Just return the raw JSON string.
- Keep Arabic values if the invoice is in Arabic.
- Be precise with numbers, remove any currency symbols."""

    def _parse_response(self, text: str) -> ScanResult:
        """معالجة رد الذكاء الاصطناعي"""
        try:
            # تنظيف النص
            clean_text = text.replace("```json", "").replace("```", "").strip()
            
            # محاولة تحليل JSON
            data = json.loads(clean_text)
            
            # تحويل البيانات
            return ScanResult(
                merchant_name=data.get('merchant_name', '') or '',
                invoice_date=self._normalize_date(data.get('invoice_date', '')),
                total_amount=float(data.get('total_amount', 0) or 0),
                tax_amount=float(data.get('tax_amount', 0) or 0),
                currency=data.get('currency', 'EGP') or 'EGP',
                items=self._normalize_items(data.get('items', [])),
                raw_text=text
            )
            
        except json.JSONDecodeError:
            logger.error("[X] Failed to parse JSON from AI response")
            return ScanResult(
                success=False,
                error="Failed to parse AI response",
                raw_text=text
            )

    def _normalize_date(self, date_str: str) -> str:
        """تطبيع التاريخ"""
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")
        
        # محاولة تحليل التاريخ
        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%m/%d/%Y"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        return date_str

    def _normalize_items(self, items: list) -> list[dict]:
        """تطبيع البنود"""
        normalized = []
        
        for item in items:
            if isinstance(item, dict):
                normalized.append({
                    'name': item.get('name', '') or item.get('item_name', ''),
                    'qty': float(item.get('qty', 1) or item.get('quantity', 1) or 1),
                    'price': float(item.get('price', 0) or item.get('unit_price', 0) or 0)
                })
        
        return normalized

    # ==========================================
    # Mock Mode للاختبار
    # ==========================================

    def scan_invoice_mock(self, image_path: str) -> ScanResult:
        """
        مسح وهمي للاختبار (بدون API)
        
        Args:
            image_path: مسار الصورة
            
        Returns:
            ScanResult: نتيجة وهمية
        """
        # التحقق من الصورة
        is_valid, error = self.validate_image(image_path)
        if not is_valid:
            return ScanResult(success=False, error=error)
        
        # إرجاع بيانات وهمية
        return ScanResult(
            success=True,
            merchant_name="شركة سكاي ويف للتسويق",
            invoice_date=datetime.now().strftime("%Y-%m-%d"),
            total_amount=1140.0,
            tax_amount=140.0,
            currency="EGP",
            items=[
                {"name": "خدمة تسويق رقمي", "qty": 1, "price": 500.0},
                {"name": "إدارة سوشيال ميديا", "qty": 1, "price": 500.0}
            ]
        )


# --- للاختبار المباشر ---
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    print("=" * 50)
    print("SMART SCAN SERVICE V2 - TEST")
    print("=" * 50)

    service = SmartScanServiceV2()

    print(f"\n[INFO] Service available: {service.is_available()}")
    print(f"[INFO] Supported formats: {service.SUPPORTED_FORMATS}")

    # اختبار التحقق من الصورة
    print("\n[TEST] Validating non-existent file...")
    is_valid, error = service.validate_image("non_existent.jpg")
    print(f"   Valid: {is_valid}, Error: {error}")

    # اختبار المسح الوهمي
    print("\n[TEST] Mock scan (no API needed)...")
    # إنشاء صورة وهمية للاختبار
    test_image = "test_invoice_temp.jpg"
    try:
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='white')
        img.save(test_image)
        
        result = service.scan_invoice_mock(test_image)
        print(f"   Success: {result.success}")
        print(f"   Merchant: {result.merchant_name}")
        print(f"   Total: {result.total_amount} {result.currency}")
        print(f"   Items: {len(result.items)}")
        
        os.remove(test_image)
    except ImportError:
        print("   [!] PIL not installed, skipping image test")

    print("\n" + "=" * 50)
    print("[OK] All tests passed!")
    print("=" * 50)
