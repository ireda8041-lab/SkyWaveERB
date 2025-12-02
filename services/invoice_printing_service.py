# الملف: services/invoice_printing_service.py
# خدمة طباعة الفواتير باستخدام القالب الحديث (Modern Blue Design)

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape


class InvoicePrintingService:
    """
    خدمة طباعة الفواتير - تحويل البيانات إلى PDF جاهز للطباعة
    """
    
    def __init__(self, settings_service=None):
        """
        تهيئة خدمة الطباعة
        
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
        self.exports_dir = base_path / "exports"
        
        # إنشاء مجلد الصادرات إذا لم يكن موجوداً
        self.exports_dir.mkdir(exist_ok=True)
        
        # تهيئة Jinja2
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        print(f"INFO: [InvoicePrintingService] Templates directory: {self.templates_dir}")
        print(f"INFO: [InvoicePrintingService] Exports directory: {self.exports_dir}")
    
    def print_invoice(self, invoice_data: Dict[str, Any]) -> Optional[str]:
        """
        طباعة الفاتورة - توليد PDF وفتحه تلقائياً
        
        Args:
            invoice_data: بيانات الفاتورة (رقم الفاتورة، العميل، البنود، الإجماليات)
        
        Returns:
            مسار ملف PDF إذا نجح، None إذا فشل
        """
        try:
            print(f"INFO: [InvoicePrintingService] بدء طباعة الفاتورة: {invoice_data.get('invoice_number', 'N/A')}")
            
            # Step 1: تحضير البيانات الكاملة
            context = self._prepare_context(invoice_data)
            
            # Step 2: رندر HTML من القالب
            template = self.env.get_template("final_invoice.html")
            html_content = template.render(**context)
            
            # Step 3: توليد اسم الملف
            safe_client_name = self._sanitize_filename(invoice_data.get('client_name', 'client'))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"invoice_{safe_client_name}_{timestamp}"
            
            # Step 4: توليد PDF
            pdf_path = self._generate_pdf(html_content, filename)
            
            if pdf_path and os.path.exists(pdf_path):
                # Step 5: فتح PDF تلقائياً
                self._open_file(pdf_path)
                print(f"✅ [InvoicePrintingService] تم إنشاء الفاتورة بنجاح: {pdf_path}")
                return pdf_path
            else:
                print(f"ERROR: [InvoicePrintingService] فشل إنشاء PDF")
                return None
                
        except Exception as e:
            print(f"ERROR: [InvoicePrintingService] خطأ في طباعة الفاتورة: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _prepare_context(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        تجهيز البيانات الكاملة للقالب (مع بيانات الشركة)
        
        Args:
            invoice_data: البيانات الأساسية
        
        Returns:
            البيانات الكاملة مع بيانات الشركة والقيم الافتراضية
        """
        context = invoice_data.copy()
        
        # تحديد مسارات الموارد (Logo & Font)
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
        else:
            # استخدام المجلد الحالي بدلاً من parent.parent
            base_path = Path.cwd()
        
        default_logo = str(base_path / "site logo.png")
        default_font = str(base_path / "assets" / "font" / "Cairo-VariableFont_slnt,wght.ttf")
        
        print(f"DEBUG: [InvoicePrintingService] base_path: {base_path}")
        print(f"DEBUG: [InvoicePrintingService] default_logo: {default_logo}")
        
        # إضافة بيانات الشركة من الإعدادات
        if self.settings_service:
            try:
                settings = self.settings_service.get_settings()
                context.setdefault('company_name', settings.get('company_name', 'Sky Wave'))
                context.setdefault('company_tagline', settings.get('company_tagline', 'حلول تسويقية متكاملة'))
                context.setdefault('company_address', settings.get('company_address', 'القاهرة - مصر'))
                context.setdefault('company_phone', settings.get('company_phone', '+20 XXX XXX XXXX'))
                # لا نستخدم logo_path من الإعدادات، نستخدم default_logo دائماً
            except Exception as e:
                print(f"WARNING: [InvoicePrintingService] فشل تحميل إعدادات الشركة: {e}")
        
        # قيم افتراضية
        context.setdefault('company_name', 'Sky Wave')
        context.setdefault('company_tagline', 'حلول تسويقية متكاملة')
        context.setdefault('company_address', 'القاهرة - مصر')
        context.setdefault('company_phone', '+20 XXX XXX XXXX')
        # استخدام default_logo دائماً
        logo_path_for_conversion = default_logo
        context.setdefault('font_path', default_font)
        context.setdefault('invoice_number', 'INV-0000')
        context.setdefault('client_name', '---')
        context.setdefault('client_phone', '---')
        context.setdefault('client_address', '---')
        context.setdefault('project_name', '---')
        context.setdefault('date', datetime.now().strftime('%Y-%m-%d'))
        context.setdefault('items', [])
        context.setdefault('grand_total', '0.00')
        context.setdefault('total_paid', '0.00')
        context.setdefault('remaining', '0.00')
        
        # تحويل اللوجو إلى base64 للاستخدام في HTML
        logo_base64 = ""
        
        print(f"INFO: [InvoicePrintingService] محاولة تحميل اللوجو من: {logo_path_for_conversion}")
        
        if os.path.exists(logo_path_for_conversion):
            try:
                import base64
                with open(logo_path_for_conversion, 'rb') as f:
                    logo_data = f.read()
                    logo_base64 = f"data:image/png;base64,{base64.b64encode(logo_data).decode()}"
                context['logo_path'] = logo_base64
                print(f"✅ [InvoicePrintingService] تم تحميل اللوجو بنجاح ({len(logo_data)} بايت)")
            except Exception as e:
                print(f"WARNING: [InvoicePrintingService] فشل تحميل اللوجو: {e}")
                context['logo_path'] = ""
        else:
            print(f"WARNING: [InvoicePrintingService] ملف اللوجو غير موجود: {logo_path_for_conversion}")
            context['logo_path'] = ""
        
        # تحويل مسار الخط إلى مسار مطلق
        if os.path.exists(context['font_path']):
            context['font_path'] = os.path.abspath(context['font_path']).replace('\\', '/')
        
        # إضافة الحقول المطلوبة للقالب الجديد
        context.setdefault('invoice_date', context.get('date'))
        context.setdefault('due_date', context.get('date'))
        context.setdefault('company_website', 'www.skywaveads.com')
        context.setdefault('subtotal', context.get('grand_total', '0'))
        context.setdefault('remaining_amount', context.get('remaining', '0'))
        context.setdefault('payments', [])
        
        return context
    
    def _generate_pdf(self, html_content: str, filename: str) -> Optional[str]:
        """
        توليد PDF من HTML
        
        Args:
            html_content: محتوى HTML
            filename: اسم الملف (بدون امتداد)
        
        Returns:
            مسار ملف PDF أو HTML إذا نجح، None إذا فشل
        """
        pdf_path = str(self.exports_dir / f"{filename}.pdf")
        
        # محاولة 1: استخدام WeasyPrint (الأفضل)
        try:
            from weasyprint import HTML, CSS
            
            print(f"INFO: [InvoicePrintingService] استخدام WeasyPrint لتوليد PDF...")
            HTML(string=html_content, base_url=str(self.templates_dir)).write_pdf(
                pdf_path,
                stylesheets=[CSS(string='@page { size: A4; margin: 0; }')]
            )
            
            print(f"✅ [InvoicePrintingService] تم إنشاء PDF باستخدام WeasyPrint")
            return pdf_path
            
        except ImportError:
            print(f"WARNING: [InvoicePrintingService] WeasyPrint غير متوفر، جاري المحاولة بطريقة بديلة...")
        except Exception as e:
            print(f"WARNING: [InvoicePrintingService] فشل WeasyPrint: {e}")
        
        # محاولة 2: استخدام Chrome Headless
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            import base64
            
            print(f"INFO: [InvoicePrintingService] استخدام Chrome Headless لتوليد PDF...")
            
            # حفظ HTML مؤقتاً
            temp_html = str(self.exports_dir / f"{filename}_temp.html")
            with open(temp_html, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # إعداد Chrome
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
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
            with open(pdf_path, 'wb') as f:
                f.write(base64.b64decode(pdf_data['data']))
            
            driver.quit()
            
            # حذف HTML المؤقت
            try:
                os.remove(temp_html)
            except:
                pass
            
            print(f"✅ [InvoicePrintingService] تم إنشاء PDF باستخدام Chrome")
            return pdf_path
            
        except Exception as e:
            print(f"WARNING: [InvoicePrintingService] فشل Chrome Headless: {e}")
        
        # الحل الأخير: حفظ HTML فقط
        html_path = str(self.exports_dir / f"{filename}.html")
        try:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"INFO: [InvoicePrintingService] تم حفظ HTML بدلاً من PDF: {html_path}")
            return html_path
            
        except Exception as e:
            print(f"ERROR: [InvoicePrintingService] فشل حفظ HTML: {e}")
            return None
    
    def _open_file(self, file_path: str) -> bool:
        """
        فتح الملف في البرنامج الافتراضي
        
        Args:
            file_path: مسار الملف
        
        Returns:
            True إذا نجح، False إذا فشل
        """
        try:
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                os.system(f'open "{file_path}"')
            else:  # Linux
                os.system(f'xdg-open "{file_path}"')
            
            print(f"✅ [InvoicePrintingService] تم فتح الملف: {file_path}")
            return True
            
        except Exception as e:
            print(f"WARNING: [InvoicePrintingService] فشل فتح الملف: {e}")
            return False
    
    def _sanitize_filename(self, name: str) -> str:
        """
        تنظيف اسم الملف من الأحرف غير المسموحة
        
        Args:
            name: الاسم الأصلي
        
        Returns:
            اسم آمن للملف
        """
        # إزالة الأحرف الخاصة والمسافات الزائدة
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()
        # استبدال المسافات بـ underscore
        safe_name = safe_name.replace(' ', '_')
        # الحد الأقصى 50 حرف
        return safe_name[:50] if safe_name else 'invoice'
