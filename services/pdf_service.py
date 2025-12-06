# الملف: services/pdf_service.py
# خدمة توليد PDF من قوالب Jinja2

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


class PDFService:
    """
    خدمة توليد PDF من قوالب HTML باستخدام Jinja2 و WeasyPrint
    """

    def __init__(self, settings_service=None):
        """
        تهيئة خدمة PDF

        Args:
            settings_service: خدمة الإعدادات للحصول على بيانات الشركة
        """
        self.settings_service = settings_service

        # تحديد مسار القوالب
        if getattr(sys, 'frozen', False):
            # البرنامج مجمع (EXE)
            base_path = Path(sys._MEIPASS)
        else:
            # البرنامج يعمل من Python
            base_path = Path(__file__).parent.parent

        self.templates_dir = base_path / "assets" / "templates" / "invoices"

        # تهيئة Jinja2
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )

        print(f"INFO: [PDFService] Templates directory: {self.templates_dir}")

    def generate_invoice_pdf(
        self,
        invoice_data: dict[str, Any],
        output_path: str,
        template_name: str = "final_invoice.html"
    ) -> bool:
        """
        توليد PDF للفاتورة

        Args:
            invoice_data: بيانات الفاتورة
            output_path: مسار حفظ ملف PDF
            template_name: اسم القالب المستخدم

        Returns:
            True إذا نجح التوليد، False إذا فشل
        """
        try:
            print(f"INFO: [PDFService] Generating PDF: {output_path}")
            print(f"INFO: [PDFService] Using template: {template_name}")

            # تحميل القالب
            template = self.env.get_template(template_name)

            # إضافة بيانات الشركة من الإعدادات
            context = self._prepare_context(invoice_data)

            # رندر HTML
            html_content = template.render(**context)

            # توليد PDF باستخدام WeasyPrint
            try:
                from weasyprint import CSS, HTML

                # إنشاء المجلد إذا لم يكن موجوداً
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # توليد PDF
                HTML(string=html_content, base_url=str(self.templates_dir)).write_pdf(
                    output_path,
                    stylesheets=[CSS(string='@page { size: A4; margin: 0; }')]
                )

                print(f"✅ [PDFService] PDF generated successfully: {output_path}")
                return True

            except ImportError:
                print("WARNING: [PDFService] WeasyPrint not available, trying alternative method...")
                return self._generate_pdf_alternative(html_content, output_path)

        except Exception as e:
            print(f"ERROR: [PDFService] Failed to generate PDF: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _prepare_context(self, invoice_data: dict[str, Any]) -> dict[str, Any]:
        """
        تجهيز البيانات للقالب

        Args:
            invoice_data: بيانات الفاتورة الأساسية

        Returns:
            البيانات الكاملة مع بيانات الشركة
        """
        context = invoice_data.copy()

        # إضافة بيانات الشركة من الإعدادات
        if self.settings_service:
            try:
                settings = self.settings_service.get_settings()
                context.setdefault('company_name', settings.get('company_name', 'Sky Wave'))
                context.setdefault('company_tagline', 'حلول تسويقية متكاملة')
                context.setdefault('company_address', settings.get('company_address', ''))
                context.setdefault('company_phone', settings.get('company_phone', ''))
                context.setdefault('company_website', settings.get('company_website', ''))
                context.setdefault('logo_path', settings.get('company_logo_path', ''))
            except Exception as e:
                print(f"WARNING: [PDFService] Failed to load company settings: {e}")

        # قيم افتراضية
        context.setdefault('company_name', 'Sky Wave')
        context.setdefault('company_tagline', 'حلول تسويقية متكاملة')
        context.setdefault('company_address', 'القاهرة - مصر')
        context.setdefault('company_phone', '+20 XXX XXX XXXX')
        context.setdefault('company_website', 'www.skywaveads.com')
        context.setdefault('logo_path', 'logo.png')

        # تنسيق التواريخ
        if 'date' in context and isinstance(context['date'], datetime):
            context['date'] = context['date'].strftime('%Y-%m-%d')

        if 'due_date' in context and isinstance(context['due_date'], datetime):
            context['due_date'] = context['due_date'].strftime('%Y-%m-%d')

        # تنسيق الدفعات
        if 'payments' in context:
            for payment in context['payments']:
                if 'date' in payment and isinstance(payment['date'], datetime):
                    payment['date'] = payment['date'].strftime('%Y-%m-%d')

        # تنسيق البنود
        if 'items' in context:
            for item in context['items']:
                item.setdefault('discount', 0)
                item['unit_price'] = f"{item.get('unit_price', 0):,.2f}"
                item['total'] = f"{item.get('total', 0):,.2f}"

        # تنسيق الإجماليات
        context['subtotal'] = f"{context.get('subtotal', 0):,.2f}"
        context['grand_total'] = f"{context.get('grand_total', 0):,.2f}"
        context['total_paid'] = f"{context.get('total_paid', 0):,.2f}"
        context['remaining'] = f"{context.get('remaining', 0):,.2f}"

        return context

    def _generate_pdf_alternative(self, html_content: str, output_path: str) -> bool:
        """
        طريقة بديلة لتوليد PDF (باستخدام Chrome Headless أو حفظ HTML)

        Args:
            html_content: محتوى HTML
            output_path: مسار حفظ الملف

        Returns:
            True إذا نجح، False إذا فشل
        """
        try:
            # محاولة استخدام Chrome Headless
            import base64

            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            # إعداد Chrome
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')

            # حفظ HTML مؤقتاً
            temp_html = output_path.replace('.pdf', '_temp.html')
            with open(temp_html, 'w', encoding='utf-8') as f:
                f.write(html_content)

            # تشغيل Chrome
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(f'file:///{os.path.abspath(temp_html)}')

            # طباعة PDF
            pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {
                "printBackground": True,
                "paperWidth": 8.27,  # A4 width in inches
                "paperHeight": 11.69,  # A4 height in inches
                "marginTop": 0,
                "marginBottom": 0,
                "marginLeft": 0,
                "marginRight": 0
            })

            # حفظ PDF
            with open(output_path, 'wb') as f:
                f.write(base64.b64decode(pdf_data['data']))

            driver.quit()

            # حذف HTML المؤقت
            try:
                os.remove(temp_html)
            except (OSError, FileNotFoundError):
                # الملف غير موجود أو لا يمكن حذفه
                pass

            print(f"✅ [PDFService] PDF generated using Chrome: {output_path}")
            return True

        except Exception as e:
            print(f"WARNING: [PDFService] Chrome method failed: {e}")

            # الحل الأخير: حفظ HTML فقط
            html_path = output_path.replace('.pdf', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            print(f"INFO: [PDFService] Saved as HTML instead: {html_path}")
            return False

    def open_pdf(self, pdf_path: str) -> bool:
        """
        فتح ملف PDF في البرنامج الافتراضي

        Args:
            pdf_path: مسار ملف PDF

        Returns:
            True إذا نجح الفتح، False إذا فشل
        """
        import subprocess
        try:
            if not os.path.exists(pdf_path):
                print(f"ERROR: [PDFService] PDF file not found: {pdf_path}")
                return False

            # فتح الملف في البرنامج الافتراضي
            if sys.platform == 'win32':
                os.startfile(pdf_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', pdf_path], check=False)
            else:  # Linux
                subprocess.run(['xdg-open', pdf_path], check=False)

            print(f"✅ [PDFService] PDF opened: {pdf_path}")
            return True

        except Exception as e:
            print(f"ERROR: [PDFService] Failed to open PDF: {e}")
            return False
