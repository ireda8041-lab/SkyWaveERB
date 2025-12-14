# الملف: services/project_printing_service.py
"""
خدمة طباعة المشاريع مع خلفية مخصصة
يدعم النصوص العربية والتصميم الاحترافي مع خلفية الفاتورة
"""

import io
import os
from datetime import datetime
from typing import Any

from PIL import Image
from PIL.Image import Image as PILImage

try:
    # Arabic text support
    import arabic_reshaper  # noqa: F401
    from bidi.algorithm import get_display  # noqa: F401
    from reportlab.lib import colors  # noqa: F401
    from reportlab.lib.pagesizes import A4  # noqa: F401
    from reportlab.lib.units import cm, inch, mm  # noqa: F401
    from reportlab.lib.utils import ImageReader  # noqa: F401
    from reportlab.pdfgen import canvas  # noqa: F401
    from reportlab.platypus import SimpleDocTemplate, Spacer  # noqa: F401

    PDF_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: [ProjectPrintingService] PDF libraries not available: {e}")
    PDF_AVAILABLE = False

from core import schemas
from core.resource_utils import get_resource_path


class ProjectInvoiceGenerator:
    """مولد فواتير المشاريع مع خلفية مخصصة"""

    def __init__(self, settings_service=None):
        self.settings_service = settings_service
        self.company_info = self._get_company_info()

        if not PDF_AVAILABLE:
            raise ImportError("PDF libraries not installed. Run: pip install reportlab arabic-reshaper python-bidi Pillow")

    def _get_company_info(self) -> dict[str, str]:
        """جلب معلومات الشركة من الإعدادات"""
        if not self.settings_service:
            return {
                "name": "Sky Wave",
                "tagline": "وكالة تسويق رقمي متكاملة",
                "address": "القاهرة، مصر",
                "phone": "+20 10 123 4567",
                "email": "info@skywave.agency"
            }

        return {
            "name": self.settings_service.get_setting("company_name") or "Sky Wave",
            "tagline": self.settings_service.get_setting("company_tagline") or "وكالة تسويق رقمي متكاملة",
            "address": self.settings_service.get_setting("company_address") or "القاهرة، مصر",
            "phone": self.settings_service.get_setting("company_phone") or "+20 10 123 4567",
            "email": self.settings_service.get_setting("company_email") or "info@skywave.agency"
        }

    @staticmethod
    def fix_arabic_text(text: str) -> str:
        """إصلاح النص العربي للعرض الصحيح"""
        if not text or not PDF_AVAILABLE:
            return str(text) if text else ""

        try:
            reshaped_text = arabic_reshaper.reshape(str(text))
            return str(get_display(reshaped_text))
        except Exception as e:
            print(f"WARNING: [ProjectInvoiceGenerator] Arabic text fix failed: {e}")
            return str(text)

    def generate_project_number(self, project_id: str) -> str:
        """توليد رقم المشروع بتنسيق SW-XXXX"""
        try:
            # محاولة استخراج رقم من ID
            numeric_part = ''.join(filter(str.isdigit, project_id))
            if len(numeric_part) >= 4:
                return f"SW-{numeric_part[:4]}"
            else:
                # استخدام timestamp كبديل
                timestamp = datetime.now().strftime("%m%d")
                return f"SW-{timestamp}"
        except (AttributeError, ValueError, TypeError):
            # في حالة الفشل، استخدم timestamp
            timestamp = datetime.now().strftime("%m%d")
            return f"SW-{timestamp}"

    def generate_project_invoice_with_background(
        self,
        project: schemas.Project,
        client_info: dict[str, str],
        payments: list[dict[str, Any]] | None = None,
        background_image_path: str | None = None,
        output_path: str | None = None
    ) -> str:
        """
        إنتاج فاتورة مشروع مع خلفية مخصصة

        Args:
            project: بيانات المشروع
            client_info: معلومات العميل
            payments: قائمة الدفعات (اختياري)
            background_image_path: مسار صورة الخلفية
            output_path: مسار الحفظ (اختياري)

        Returns:
            مسار الملف المُنتج
        """
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_number = self.generate_project_number(str(project.id))
            output_path = f"project_invoice_{project_number}_{timestamp}.pdf"

        # استخدام الصورة المرفوعة أو الافتراضية
        if not background_image_path:
            background_image_path = get_resource_path("default_background.jpg")

        # إنشاء المستند
        c = canvas.Canvas(output_path, pagesize=A4)
        width, height = A4

        # إضافة صورة الخلفية
        self._add_background_image(c, background_image_path, width, height)

        # إضافة البيانات على الخلفية
        self._add_project_data_overlay(c, project, client_info, payments or [], width, height)

        # حفظ المستند
        c.save()

        print(f"INFO: [ProjectInvoiceGenerator] Project invoice PDF created: {output_path}")
        return output_path

    def _add_background_image(self, canvas_obj, image_path: str, width: float, height: float):
        """إضافة صورة الخلفية"""
        try:
            if os.path.exists(image_path):
                # تحميل الصورة وتعديل حجمها
                img: PILImage = Image.open(image_path)

                # تحويل إلى RGB إذا كانت RGBA
                if img.mode == 'RGBA':
                    img = img.convert('RGB')

                # تعديل الحجم ليناسب A4
                img = img.resize((int(width), int(height)), Image.Resampling.LANCZOS)

                # حفظ في buffer
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='JPEG', quality=85)
                img_buffer.seek(0)

                # إضافة للـ PDF
                canvas_obj.drawImage(ImageReader(img_buffer), 0, 0, width, height)
                print("✅ تم إضافة صورة الخلفية بنجاح")
            else:
                print(f"⚠️ لم يتم العثور على صورة الخلفية: {image_path}")
                # إضافة خلفية بيضاء بسيطة
                canvas_obj.setFillColor(colors.white)
                canvas_obj.rect(0, 0, width, height, fill=1)
        except Exception as e:
            print(f"ERROR: فشل في إضافة صورة الخلفية: {e}")
            # إضافة خلفية بيضاء في حالة الفشل
            canvas_obj.setFillColor(colors.white)
            canvas_obj.rect(0, 0, width, height, fill=1)

    def _add_project_data_overlay(self, canvas_obj, project: schemas.Project,
                                client_info: dict[str, str], payments: list[dict[str, Any]],
                                width: float, height: float):
        """إضافة بيانات المشروع على الخلفية"""

        # إعداد الخطوط
        try:
            # محاولة استخدام خط عربي
            canvas_obj.setFont("Helvetica", 12)
        except (AttributeError, RuntimeError):
            canvas_obj.setFont("Helvetica", 12)

        # رقم المشروع (أعلى يمين)
        project_number = self.generate_project_number(str(project.id))
        canvas_obj.setFillColor(colors.darkblue)
        canvas_obj.setFont("Helvetica-Bold", 16)
        # تحسين الموضع ليكون أكثر وضوحاً
        canvas_obj.drawRightString(width - 80, height - 80, f"Project: {project_number}")

        # تاريخ المشروع (أعلى يمين تحت رقم المشروع)
        if project.start_date:
            project_date = project.start_date.strftime("%Y-%m-%d") if hasattr(project.start_date, 'strftime') else str(project.start_date)[:10]
        else:
            project_date = datetime.now().strftime("%Y-%m-%d")
        canvas_obj.setFont("Helvetica", 12)
        canvas_obj.setFillColor(colors.black)
        canvas_obj.drawRightString(width - 80, height - 105, f"Date: {project_date}")

        # معلومات العميل (منتصف الصفحة يسار)
        client_y_start = height - 180

        # عنوان "Bill To"
        canvas_obj.setFont("Helvetica-Bold", 14)
        canvas_obj.setFillColor(colors.darkblue)
        canvas_obj.drawString(50, client_y_start, "Bill To:")

        # بيانات العميل
        canvas_obj.setFont("Helvetica", 12)
        canvas_obj.setFillColor(colors.black)

        # اسم العميل
        client_name = self.fix_arabic_text(client_info.get("name", ""))
        if client_name:
            canvas_obj.drawString(50, client_y_start - 25, client_name)

        # هاتف العميل
        client_phone = client_info.get("phone", "")
        if client_phone:
            canvas_obj.drawString(50, client_y_start - 45, client_phone)

        # عنوان العميل
        client_address = self.fix_arabic_text(client_info.get("address", ""))
        if client_address:
            canvas_obj.drawString(50, client_y_start - 65, client_address)

        # جدول الخدمات (منتصف الصفحة)
        self._add_services_table(canvas_obj, project, width, height)

        # الإجماليات (أسفل يمين)
        self._add_totals_section(canvas_obj, project, width, height)

        # الدفعات (أسفل يسار)
        if payments:
            self._add_payments_section(canvas_obj, payments, width, height)

    def _add_services_table(self, canvas_obj, project: schemas.Project, width: float, height: float):
        """إضافة جدول الخدمات"""
        table_start_y = height - 320
        row_height = 30

        # خلفية رأس الجدول
        canvas_obj.setFillColor(colors.Color(0.23, 0.32, 0.52))  # أزرق داكن
        canvas_obj.rect(50, table_start_y - 5, width - 100, 25, fill=1)

        # رأس الجدول
        canvas_obj.setFont("Helvetica-Bold", 11)
        canvas_obj.setFillColor(colors.white)

        # عناوين الأعمدة
        canvas_obj.drawString(60, table_start_y, "Service")
        canvas_obj.drawString(280, table_start_y, "Qty")
        canvas_obj.drawString(330, table_start_y, "Unit Price")
        canvas_obj.drawString(420, table_start_y, "Discount")
        canvas_obj.drawString(490, table_start_y, "Total")

        # بيانات الخدمات
        canvas_obj.setFont("Helvetica", 10)
        canvas_obj.setFillColor(colors.black)
        current_y = table_start_y - row_height

        for i, item in enumerate(project.items):
            if current_y < 150:  # تجنب الكتابة في أسفل الصفحة
                break

            # خلفية متناوبة للصفوف
            if i % 2 == 0:
                canvas_obj.setFillColor(colors.Color(0.95, 0.95, 0.95))
                canvas_obj.rect(50, current_y - 5, width - 100, 25, fill=1)

            canvas_obj.setFillColor(colors.black)

            # اسم الخدمة
            service_name = self.fix_arabic_text(item.description)
            canvas_obj.drawString(60, current_y, service_name[:25])  # قطع النص الطويل

            # الكمية
            canvas_obj.drawString(285, current_y, f"{item.quantity:.1f}")

            # السعر
            canvas_obj.drawString(335, current_y, f"{item.unit_price:,.0f}")

            # الخصم
            canvas_obj.drawString(425, current_y, f"{item.discount_rate:.1f}%")

            # الإجمالي
            canvas_obj.drawString(495, current_y, f"{item.total:,.0f}")

            current_y -= row_height

    def _add_totals_section(self, canvas_obj, project: schemas.Project, width: float, height: float):
        """إضافة قسم الإجماليات"""
        totals_start_y = 220

        # حساب الإجماليات
        subtotal = sum(item.total for item in project.items)
        discount_amount = subtotal * (project.discount_rate / 100)
        taxable_amount = subtotal - discount_amount
        tax_amount = taxable_amount * (project.tax_rate / 100)
        total_amount = taxable_amount + tax_amount

        # حفظ المجموع للاستخدام في حساب المتبقي
        self._current_project_total = total_amount

        # إطار للإجماليات
        canvas_obj.setFillColor(colors.Color(0.9, 0.9, 0.9))
        canvas_obj.rect(width - 250, totals_start_y - 80, 200, 90, fill=1)

        canvas_obj.setFont("Helvetica", 11)
        canvas_obj.setFillColor(colors.black)

        # المجموع الفرعي
        canvas_obj.drawRightString(width - 60, totals_start_y, "Subtotal:")
        canvas_obj.drawRightString(width - 60, totals_start_y - 15, f"{subtotal:,.2f} EGP")

        # الخصم
        if project.discount_rate > 0:
            canvas_obj.drawRightString(width - 60, totals_start_y - 35,
                                     f"Discount ({project.discount_rate:.1f}%):")
            canvas_obj.drawRightString(width - 60, totals_start_y - 50,
                                     f"-{discount_amount:,.2f} EGP")

        # الضريبة
        if project.tax_rate > 0:
            y_pos = totals_start_y - 70 if project.discount_rate > 0 else totals_start_y - 35
            canvas_obj.drawRightString(width - 60, y_pos,
                                     f"Tax ({project.tax_rate:.1f}%):")
            canvas_obj.drawRightString(width - 60, y_pos - 15,
                                     f"{tax_amount:,.2f} EGP")

        # الإجمالي النهائي
        canvas_obj.setFont("Helvetica-Bold", 14)
        canvas_obj.setFillColor(colors.Color(0.06, 0.72, 0.51))  # أخضر
        final_y = totals_start_y - 90 if project.tax_rate > 0 or project.discount_rate > 0 else totals_start_y - 50
        canvas_obj.drawRightString(width - 60, final_y, f"TOTAL: {total_amount:,.2f} EGP")

    def _add_payments_section(self, canvas_obj, payments: list[dict[str, Any]], width: float, height: float):
        """إضافة قسم الدفعات"""
        payments_start_y = 220

        # عنوان قسم الدفعات
        canvas_obj.setFont("Helvetica-Bold", 12)
        canvas_obj.setFillColor(colors.Color(0.23, 0.32, 0.52))  # أزرق داكن
        canvas_obj.drawString(50, payments_start_y, "Payments Received:")

        # إطار للدفعات
        canvas_obj.setFillColor(colors.Color(0.95, 0.95, 0.95))
        canvas_obj.rect(50, payments_start_y - 80, 200, 90, fill=1)

        canvas_obj.setFont("Helvetica", 10)
        canvas_obj.setFillColor(colors.black)

        current_y = payments_start_y - 20
        total_paid = 0

        # عرض الدفعات
        for _i, payment in enumerate(payments[:4]):  # أقصى 4 دفعات
            if current_y < payments_start_y - 70:
                break

            # تاريخ الدفعة
            payment_date = payment.get('date', '')
            if hasattr(payment_date, 'strftime'):
                date_str = payment_date.strftime('%Y-%m-%d')
            else:
                date_str = str(payment_date)[:10]

            # مبلغ الدفعة
            amount = payment.get('amount', 0)
            total_paid += amount

            # عرض الدفعة
            canvas_obj.drawString(60, current_y, f"{date_str}")
            canvas_obj.drawRightString(240, current_y, f"{amount:,.2f} EGP")

            current_y -= 15

        # إجمالي المدفوع
        canvas_obj.setFont("Helvetica-Bold", 11)
        canvas_obj.setFillColor(colors.Color(0.06, 0.72, 0.51))  # أخضر
        canvas_obj.drawString(60, payments_start_y - 75, "Total Paid:")
        canvas_obj.drawRightString(240, payments_start_y - 75, f"{total_paid:,.2f} EGP")

        # المتبقي
        project_total = getattr(self, '_current_project_total', 0)

        remaining = project_total - total_paid
        if remaining > 0:
            canvas_obj.setFillColor(colors.red)
            canvas_obj.drawString(60, payments_start_y - 90, "Balance Due:")
            canvas_obj.drawRightString(240, payments_start_y - 90, f"{remaining:,.2f} EGP")


class ProjectPrintingService:
    """خدمة طباعة المشاريع الرئيسية"""

    def __init__(self, settings_service=None):
        self.settings_service = settings_service

        if PDF_AVAILABLE:
            self.invoice_generator = ProjectInvoiceGenerator(settings_service)
            print("INFO: [ProjectPrintingService] Project printing service initialized")
        else:
            self.invoice_generator = None
            print("WARNING: [ProjectPrintingService] PDF libraries not available")

    def is_available(self) -> bool:
        """التحقق من توفر خدمة الطباعة"""
        return PDF_AVAILABLE and self.invoice_generator is not None

    def print_project_invoice(
        self,
        project: schemas.Project,
        client_info: dict[str, str],
        payments: list[dict[str, Any]] | None = None,
        background_image_path: str | None = None,
        auto_open: bool = True
    ) -> str | None:
        """طباعة فاتورة مشروع مع خلفية مخصصة"""
        if not self.is_available():
            print("ERROR: [ProjectPrintingService] PDF libraries not installed")
            return None

        try:
            pdf_path = self.invoice_generator.generate_project_invoice_with_background(
                project, client_info, payments, background_image_path
            )

            if auto_open:
                self._open_pdf(pdf_path)

            return str(pdf_path) if pdf_path else None
        except Exception as e:
            print(f"ERROR: [ProjectPrintingService] Failed to print project invoice: {e}")
            return None

    @staticmethod
    def _open_pdf(file_path: str):
        """فتح ملف PDF في العارض الافتراضي"""
        try:
            import platform
            import subprocess

            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', file_path])

            print(f"INFO: [ProjectPrintingService] Opened PDF: {file_path}")
        except Exception as e:
            print(f"ERROR: [ProjectPrintingService] Failed to open PDF: {e}")


# الكلاس القديم للتوافق مع الكود الموجود
class ProjectPrinter:
    def __init__(self, output_path="project_contract.pdf"):
        self.output_path = output_path
        self.width, self.height = A4

        # تسجيل خط Cairo العربي
        import sys
        import os
        
        # تحديد مسار خط Cairo
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        font_path = os.path.join(base_path, "assets", "font", "Cairo-VariableFont_slnt,wght.ttf")
        
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            pdfmetrics.registerFont(TTFont('CairoFont', font_path))
            self.font_name = 'CairoFont'
            print(f"✅ [PDFGenerator] تم تحميل خط Cairo: {font_path}")
        except (FileNotFoundError, OSError, RuntimeError) as e:
            print(f"⚠️ لم يتم العثور على خط Cairo: {e}")
            self.font_name = 'Helvetica'

    def fix_text(self, text):
        """تصحيح الحروف العربية المقطعة والمعكوسة"""
        if not text:
            return ""
        try:
            reshaped_text = arabic_reshaper.reshape(str(text))
            bidi_text = get_display(reshaped_text)
            return bidi_text
        except (AttributeError, TypeError, ValueError):
            return str(text)

    def create_pdf(self, data, background_image_path):
        """إنشاء PDF مع خلفية"""
        from reportlab.lib.colors import black
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(self.output_path, pagesize=A4)

        # رسم الخلفية
        if os.path.exists(background_image_path):
            c.drawImage(background_image_path, 0, 0, width=self.width, height=self.height)
        else:
            print("❌ صورة الخلفية غير موجودة!")

        # إعدادات الخط
        c.setFont(self.font_name, 14)
        c.setFillColor(black)

        # رقم المشروع
        project_id = f"SW-{data.get('id', '000')}"
        c.setFont(self.font_name, 16)
        c.drawRightString(550, 750, self.fix_text(f"رقم المشروع: {project_id}"))

        # بيانات العميل والمشروع
        c.setFont(self.font_name, 14)
        c.drawRightString(500, 680, self.fix_text(f"العميل: {data.get('client_name')}"))
        c.drawRightString(500, 650, self.fix_text(f"المشروع: {data.get('project_title')}"))
        c.drawRightString(200, 680, self.fix_text(f"تاريخ البدء: {data.get('start_date')}"))
        c.drawRightString(200, 650, self.fix_text(f"تاريخ التسليم: {data.get('end_date')}"))

        # جدول البنود
        y_position = 550
        c.setFont(self.font_name, 12)

        items = data.get('services', [])
        for item in items:
            c.drawRightString(520, y_position, self.fix_text(item['name']))
            c.drawCentredString(300, y_position, str(item['qty']))
            c.drawString(100, y_position, f"{item['price']:,.2f}")
            y_position -= 30

        # الإجماليات
        c.setFont(self.font_name, 16)
        c.drawRightString(200, 150, self.fix_text(f"الإجمالي: {data.get('total_amount', 0):,.2f} ج.م"))

        c.save()
        print(f"✅ تم إنشاء ملف المشروع: {self.output_path}")

        # فتح الملف تلقائياً
        try:
            os.startfile(self.output_path)
        except (OSError, AttributeError):
            # الملف غير موجود أو النظام لا يدعم startfile
            pass
