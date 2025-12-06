# الملف: services/smart_scan_service.py
"""
خدمة المسح الذكي للفواتير باستخدام Google Gemini AI 🧠

تحول صور الفواتير إلى بيانات مهيكلة (JSON) جاهزة للإدخال.
- سريع جداً: يستخدم gemini-1.5-flash
- منظم: يعيد JSON مطابق لما يحتاجه البرنامج
- يدعم العربية والإنجليزية
"""

import os
import json
import logging
import PIL.Image
import google.generativeai as genai
from typing import Dict, Any
from datetime import datetime

# إعداد اللوجر
logger = logging.getLogger("SmartScanService")
logger.setLevel(logging.INFO)


class SmartScanService:
    """
    خدمة المسح الذكي للفواتير باستخدام Google Gemini AI 🧠
    
    تحول صور الفواتير إلى بيانات مهيكلة (JSON) جاهزة للإدخال.
    """

    def __init__(self, api_key: str = None):
        """
        تهيئة الخدمة
        
        Args:
            api_key: مفتاح Gemini API (اختياري، يمكن استخدام متغير البيئة)
        """
        # يفضل وضع المفتاح في متغيرات البيئة، أو تمريره هنا
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = None
        
        if not self.api_key:
            logger.warning("⚠️ Gemini API Key is missing! Smart Scan will not work.")
        else:
            self._configure_genai()

    def _configure_genai(self):
        """تهيئة Gemini AI"""
        try:
            genai.configure(api_key=self.api_key)
            # نستخدم gemini-2.0-flash (الأحدث والأسرع)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            logger.info("✅ Gemini AI Configured Successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to configure Gemini: {e}")

    def is_available(self) -> bool:
        """هل الخدمة متاحة؟"""
        return self.model is not None

    # الصيغ المدعومة
    SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    SUPPORTED_PDF_FORMAT = '.pdf'

    def scan_invoice_image(self, image_path: str) -> Dict[str, Any]:
        """
        تحليل صورة أو PDF الفاتورة واستخراج البيانات.
        
        Args:
            image_path: مسار صورة أو PDF الفاتورة
            
        Returns:
            Dictionary containing:
            - merchant_name (str)
            - invoice_date (YYYY-MM-DD)
            - total_amount (float)
            - tax_amount (float)
            - currency (str)
            - items (List[Dict])
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"File not found: {image_path}")

        if not self.is_available():
            raise RuntimeError("Gemini AI not configured. Check API key.")

        try:
            logger.info(f"🔍 Scanning invoice: {image_path}...")
            
            # تحديد نوع الملف
            file_ext = os.path.splitext(image_path)[1].lower()
            
            # بناء الطلب
            prompt = self._build_prompt()
            
            if file_ext == self.SUPPORTED_PDF_FORMAT:
                # معالجة PDF
                content = self._process_pdf(image_path, prompt)
            elif file_ext in self.SUPPORTED_IMAGE_FORMATS:
                # معالجة الصورة
                img = PIL.Image.open(image_path)
                content = [prompt, img]
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")

            # إرسال الطلب
            response = self.model.generate_content(content)

            # تنظيف ومعالجة الرد
            cleaned_json = self._clean_json_response(response.text)
            logger.info("✨ Scan Completed Successfully!")
            return cleaned_json

        except Exception as e:
            logger.error(f"❌ Smart Scan Failed: {e}")
            raise e

    def _build_prompt(self) -> str:
        """بناء الطلب للذكاء الاصطناعي"""
        current_year = datetime.now().year
        
        return f"""You are an expert AI Data Entry Clerk.
Analyze this invoice/receipt document and extract the data into a strict JSON format.

Requirements:
1. Extract the Merchant/Company Name.
2. Extract the Date and format it as YYYY-MM-DD. If year is missing, assume {current_year}.
3. Extract the Total Amount (numeric).
4. Extract Tax/VAT Amount if present (numeric), else 0.
5. Identify the Currency (e.g., EGP, USD, SAR).
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

If a field is not found, use null (or 0 for numbers).
Do NOT write markdown formatting like ```json. Just return the raw JSON string.
Translate any Arabic text to English keys but keep Arabic values if needed."""

    def _process_pdf(self, pdf_path: str, prompt: str) -> list:
        """معالجة ملف PDF وإرساله لـ Gemini"""
        import base64
        
        # قراءة الملف كـ bytes
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # تحويل لـ base64
        pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
        
        # إنشاء محتوى الملف لـ Gemini
        pdf_part = {
            "mime_type": "application/pdf",
            "data": pdf_base64
        }
        
        return [prompt, pdf_part]

    def _clean_json_response(self, text: str) -> Dict:
        """تنظيف الرد من أي شوائب (مثل علامات Markdown)"""
        try:
            # إزالة علامات الكود إذا وجدت
            clean_text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from AI response")
            # في حالة الفشل، نرجع نص الخطأ للمراجعة
            return {"error": "Parsing Failed", "raw_text": text}


# --- اختبار الخدمة (للتجربة المباشرة) ---
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    
    # ⚠️ استبدل هذا بمفتاحك الحقيقي للتجربة
    TEST_API_KEY = os.getenv("GEMINI_API_KEY", "ضع_مفتاح_API_هنا")

    # تأكد من وجود صورة للتجربة بجانب الملف باسم test_invoice.jpg
    service = SmartScanService(TEST_API_KEY)

    # مسار وهمي للصورة (غيره لمسار حقيقي عندك للتجربة)
    test_img = "test_invoice.jpg"

    if os.path.exists(test_img):
        print("🚀 Sending image to Gemini...")
        result = service.scan_invoice_image(test_img)
        print("\n🧾 Extracted Data:")
        print(json.dumps(result, indent=4, ensure_ascii=False))
    else:
        print(f"⚠️ Please place an image named '{test_img}' to test.")
        print(f"\n📋 Service Status:")
        print(f"   - Available: {service.is_available()}")
        print(f"   - API Key Set: {bool(service.api_key)}")
