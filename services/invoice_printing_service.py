# الملف: services/invoice_printing_service.py
# خدمة طباعة الفواتير باستخدام القالب الحديث (Modern Blue Design)

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


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

        # تحديد مسار القوالب ومسار التثبيت
        if getattr(sys, 'frozen', False):
            # البرنامج مجمع (EXE) - مسار التثبيت هو مجلد الـ EXE
            base_path = Path(sys._MEIPASS)
            # مسار التثبيت الفعلي (مجلد الـ EXE)
            install_path = Path(sys.executable).parent
        else:
            # البرنامج يعمل من Python
            base_path = Path(__file__).parent.parent
            install_path = base_path

        self.templates_dir = base_path / "assets" / "templates" / "invoices"

        # ⚡ حفظ الفواتير في مجلد exports داخل مسار التثبيت
        self.exports_dir = install_path / "exports"

        # إنشاء مجلد الصادرات إذا لم يكن موجوداً
        self.exports_dir.mkdir(parents=True, exist_ok=True)

        # ⚡ تهيئة Jinja2 مع caching للسرعة
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            cache_size=400,  # ⚡ تفعيل الـ cache
            auto_reload=False  # ⚡ تعطيل auto reload للسرعة
        )

        # ⚡ تحميل القالب مسبقاً (pre-compile)
        try:
            self.invoice_template = self.env.get_template("final_invoice.html")
            safe_print("✅ [InvoicePrintingService] تم تحميل القالب مسبقاً")
        except Exception as e:
            safe_print(f"WARNING: [InvoicePrintingService] فشل تحميل القالب: {e}")
            self.invoice_template = None

        safe_print(f"INFO: [InvoicePrintingService] Templates directory: {self.templates_dir}")
        safe_print(f"INFO: [InvoicePrintingService] Exports directory: {self.exports_dir}")

    def print_invoice(self, invoice_data: dict[str, Any]) -> str | None:
        """
        طباعة الفاتورة - توليد PDF وفتحه تلقائياً

        Args:
            invoice_data: بيانات الفاتورة (رقم الفاتورة، العميل، البنود، الإجماليات)

        Returns:
            مسار ملف PDF إذا نجح، None إذا فشل
        """
        try:
            safe_print(f"INFO: [InvoicePrintingService] بدء طباعة الفاتورة: {invoice_data.get('invoice_number', 'N/A')}")

            # ⚡ تصحيح البيانات قبل الطباعة
            invoice_data = self._fix_invoice_data(invoice_data)

            # Step 1: تحضير البيانات الكاملة
            context = self._prepare_context(invoice_data)

            # ⚡ Step 2: رندر HTML من القالب (استخدام القالب المحمل مسبقاً)
            template = self.invoice_template if self.invoice_template else self.env.get_template("final_invoice.html")
            html_content = template.render(**context)

            # Step 3: توليد اسم الملف (اسم العميل - اسم المشروع)
            safe_client_name = self._sanitize_filename(invoice_data.get('client_name', 'client'))
            safe_project_name = self._sanitize_filename(invoice_data.get('project_name', 'project'))
            filename = f"{safe_client_name} - {safe_project_name}"

            # Step 4: توليد PDF
            pdf_path = self._generate_pdf(html_content, filename)

            if pdf_path and os.path.exists(pdf_path):
                # Step 5: فتح PDF تلقائياً
                self._open_file(pdf_path)
                safe_print(f"✅ [InvoicePrintingService] تم إنشاء الفاتورة بنجاح: {pdf_path}")
                return pdf_path
            else:
                safe_print("ERROR: [InvoicePrintingService] فشل إنشاء PDF")
                return None

        except Exception as e:
            safe_print(f"ERROR: [InvoicePrintingService] خطأ في طباعة الفاتورة: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fix_invoice_data(self, invoice_data: dict[str, Any]) -> dict[str, Any]:
        """⚡ تصحيح البيانات المفقودة أو الخاطئة"""
        # تصحيح الأرقام
        for key in ['subtotal', 'grand_total', 'total_paid', 'remaining_amount', 'total_amount']:
            if key in invoice_data:
                try:
                    invoice_data[key] = float(invoice_data[key]) if invoice_data[key] else 0.0
                except (ValueError, TypeError, AttributeError):
                    invoice_data[key] = 0.0

        # تصحيح الدفعات
        if 'payments' in invoice_data and invoice_data['payments']:
            fixed_payments = []
            for payment in invoice_data['payments']:
                if isinstance(payment, dict):
                    # تصحيح التاريخ
                    if 'date' in payment:
                        date_val = payment['date']
                        if hasattr(date_val, 'strftime'):
                            payment['date'] = date_val.strftime('%Y-%m-%d')
                        elif isinstance(date_val, str):
                            payment['date'] = date_val[:10]

                    # تصحيح المبلغ
                    if 'amount' in payment:
                        try:
                            payment['amount'] = float(payment['amount'])
                        except (ValueError, TypeError, AttributeError):
                            payment['amount'] = 0.0

                    # تصحيح اسم الحساب
                    if 'account_name' not in payment or not payment['account_name']:
                        payment['account_name'] = payment.get('account_id', 'غير محدد')

                    fixed_payments.append(payment)

            invoice_data['payments'] = fixed_payments
        else:
            invoice_data['payments'] = []

        # تصحيح البنود
        if 'items' in invoice_data and invoice_data['items']:
            for item in invoice_data['items']:
                if isinstance(item, dict):
                    for key in ['quantity', 'unit_price', 'total', 'discount_rate']:
                        if key in item:
                            try:
                                item[key] = float(item[key]) if item[key] else 0.0
                            except (ValueError, TypeError, AttributeError):
                                item[key] = 0.0

        return invoice_data

    def _prepare_context(self, invoice_data: dict[str, Any]) -> dict[str, Any]:
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
            base_path = Path(getattr(sys, '_MEIPASS', '.'))
        else:
            # استخدام المجلد الحالي بدلاً من parent.parent
            base_path = Path.cwd()

        default_logo = str(base_path / "site logo.png")
        default_font = str(base_path / "assets" / "font" / "Cairo-VariableFont_slnt,wght.ttf")

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
                safe_print(f"WARNING: [InvoicePrintingService] فشل تحميل إعدادات الشركة: {e}")

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

        safe_print(f"INFO: [InvoicePrintingService] محاولة تحميل اللوجو من: {logo_path_for_conversion}")

        if os.path.exists(logo_path_for_conversion):
            try:
                import base64
                with open(logo_path_for_conversion, 'rb') as f:
                    logo_data = f.read()
                    logo_base64 = f"data:image/png;base64,{base64.b64encode(logo_data).decode()}"
                context['logo_path'] = logo_base64
                safe_print(f"✅ [InvoicePrintingService] تم تحميل اللوجو بنجاح ({len(logo_data)} بايت)")
            except Exception as e:
                safe_print(f"WARNING: [InvoicePrintingService] فشل تحميل اللوجو: {e}")
                context['logo_path'] = ""
        else:
            safe_print(f"WARNING: [InvoicePrintingService] ملف اللوجو غير موجود: {logo_path_for_conversion}")
            context['logo_path'] = ""

        # تحويل مسار الخط إلى مسار مطلق
        if os.path.exists(context['font_path']):
            context['font_path'] = os.path.abspath(context['font_path']).replace('\\', '/')

        # إضافة الحقول المطلوبة للقالب الجديد
        context.setdefault('invoice_date', context.get('date'))
        context.setdefault('due_date', context.get('date'))
        context.setdefault('company_website', 'www.skywaveads.com')
        context.setdefault('subtotal', context.get('grand_total', 0))
        context.setdefault('remaining_amount', context.get('remaining', 0))

        # ⚡ تصحيح الدفعات - جلب اسم الحساب
        if 'payments' in context and context['payments']:
            for payment in context['payments']:
                if isinstance(payment, dict):
                    # إذا مفيش account_name، نجيبه من account_id
                    if 'account_name' not in payment or not payment['account_name']:
                        account_id = payment.get('account_id', '')
                        if account_id:
                            try:
                                # محاولة جلب اسم الحساب من الريبوزيتوري
                                from core.repository import Repository
                                repo = Repository()
                                # محاولة جلب الحساب بالكود أولاً
                                account = repo.get_account_by_code(account_id)
                                if account:
                                    payment['account_name'] = account.name
                                else:
                                    # محاولة جلب الحساب بالـ ID
                                    account = repo.get_account_by_id(account_id)
                                    if account:
                                        payment['account_name'] = account.name
                                    else:
                                        payment['account_name'] = account_id
                            except (AttributeError, KeyError, TypeError):
                                payment['account_name'] = account_id
                        else:
                            payment['account_name'] = 'غير محدد'

        return context

    def _generate_pdf(self, html_content: str, filename: str) -> str | None:
        """
        توليد PDF من HTML

        Args:
            html_content: محتوى HTML
            filename: اسم الملف (بدون امتداد)

        Returns:
            مسار ملف PDF إذا نجح، None إذا فشل
        """
        pdf_path = str(self.exports_dir / f"{filename}.pdf")

        # محاولة 1: استخدام WeasyPrint (الأفضل)
        try:
            from weasyprint import CSS, HTML

            safe_print("INFO: [InvoicePrintingService] استخدام WeasyPrint لتوليد PDF...")
            HTML(string=html_content, base_url=str(self.templates_dir)).write_pdf(
                pdf_path,
                stylesheets=[CSS(string='@page { size: A4; margin: 0; }')]
            )

            safe_print("✅ [InvoicePrintingService] تم إنشاء PDF باستخدام WeasyPrint")
            return pdf_path

        except ImportError:
            safe_print("WARNING: [InvoicePrintingService] WeasyPrint غير متوفر، جاري استخدام PyQt6...")
        except Exception as e:
            safe_print(f"WARNING: [InvoicePrintingService] فشل WeasyPrint: {e}")

        # محاولة 2: استخدام PyQt6 لتحويل HTML إلى PDF
        try:
            safe_print("INFO: [InvoicePrintingService] استخدام PyQt6 لتوليد PDF...")
            return self._generate_pdf_with_qt(html_content, pdf_path)
        except Exception as e:
            safe_print(f"WARNING: [InvoicePrintingService] فشل PyQt6: {e}")

        # محاولة 3: حفظ HTML كـ fallback أخير
        html_path = str(self.exports_dir / f"{filename}.html")
        try:
            safe_print("INFO: [InvoicePrintingService] حفظ HTML كـ fallback...")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            safe_print(f"⚠️ [InvoicePrintingService] تم حفظ HTML: {html_path}")
            safe_print("💡 افتح الملف في المتصفح واطبع (Ctrl+P) للحصول على PDF")
            return html_path

        except Exception as e:
            safe_print(f"ERROR: [InvoicePrintingService] فشل حفظ HTML: {e}")
            return None

    def _generate_pdf_with_qt(self, html_content: str, pdf_path: str) -> str | None:
        """
        توليد PDF باستخدام PyQt6

        Args:
            html_content: محتوى HTML
            pdf_path: مسار ملف PDF المطلوب

        Returns:
            مسار ملف PDF إذا نجح، None إذا فشل
        """
        try:
            from PyQt6.QtCore import QEventLoop, QMarginsF, QTimer, QUrl
            from PyQt6.QtGui import QPageLayout, QPageSize
            from PyQt6.QtPrintSupport import QPrinter
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtWidgets import QApplication

            # التأكد من وجود QApplication
            app = QApplication.instance()
            if not app:
                app = QApplication([])

            # إنشاء WebView لعرض HTML
            web_view = QWebEngineView()

            # إعداد الطابعة للـ PDF
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(pdf_path)

            # إعداد حجم الصفحة A4
            page_layout = QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                QMarginsF(0, 0, 0, 0)
            )
            printer.setPageLayout(page_layout)

            # متغير لتتبع اكتمال الطباعة
            pdf_generated = [False]

            def on_pdf_done(success):
                pdf_generated[0] = success
                if success:
                    safe_print("✅ [InvoicePrintingService] تم إنشاء PDF باستخدام PyQt6")
                else:
                    safe_print("ERROR: [InvoicePrintingService] فشل إنشاء PDF")

            def on_load_finished(ok):
                if ok:
                    # طباعة إلى PDF بعد تحميل الصفحة
                    web_view.page().printToPdf(pdf_path)
                    pdf_generated[0] = True
                else:
                    safe_print("ERROR: [InvoicePrintingService] فشل تحميل HTML")

            # ربط الإشارة
            web_view.loadFinished.connect(on_load_finished)

            # تحميل HTML
            web_view.setHtml(html_content, QUrl.fromLocalFile(str(self.templates_dir) + "/"))

            # انتظار اكتمال التحميل والطباعة
            loop = QEventLoop()
            QTimer.singleShot(3000, loop.quit)  # انتظار 3 ثواني كحد أقصى
            loop.exec()

            # التحقق من إنشاء الملف
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                return pdf_path

            return None

        except ImportError as e:
            safe_print(f"WARNING: [InvoicePrintingService] PyQt6 WebEngine غير متوفر: {e}")
            return None
        except Exception as e:
            safe_print(f"ERROR: [InvoicePrintingService] خطأ في PyQt6: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _open_file(self, file_path: str) -> bool:
        """
        فتح الملف في البرنامج الافتراضي

        Args:
            file_path: مسار الملف

        Returns:
            True إذا نجح، False إذا فشل
        """
        import subprocess
        try:
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', file_path], check=False)
            else:  # Linux
                subprocess.run(['xdg-open', file_path], check=False)

            safe_print(f"✅ [InvoicePrintingService] تم فتح الملف: {file_path}")
            return True

        except Exception as e:
            safe_print(f"WARNING: [InvoicePrintingService] فشل فتح الملف: {e}")
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
