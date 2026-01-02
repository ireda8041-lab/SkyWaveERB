# الملف: services/printing_service.py
"""
خدمة الطباعة وإنتاج ملفات PDF احترافية
يدعم النصوص العربية والتصميم الاحترافي
"""

import os
import platform
import subprocess
import sys
from datetime import datetime
from typing import Any

try:
    # Arabic text support
    import arabic_reshaper  # noqa: F401
    from bidi.algorithm import get_display  # noqa: F401
    from reportlab.lib import colors  # noqa: F401
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT  # noqa: F401
    from reportlab.lib.pagesizes import A4  # noqa: F401
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: F401
    from reportlab.lib.units import cm, inch  # noqa: F401
    from reportlab.pdfbase import pdfmetrics  # noqa: F401
    from reportlab.pdfbase.ttfonts import TTFont  # noqa: F401
    from reportlab.pdfgen import canvas  # noqa: F401
    from reportlab.platypus import (  # noqa: F401
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    PDF_AVAILABLE = True
except ImportError as e:
    safe_print(f"WARNING: [PrintingService] PDF libraries not available: {e}")
    safe_print("INFO: Install with: pip install reportlab arabic-reshaper python-bidi")
    PDF_AVAILABLE = False
    # تعريف قيم افتراضية لتجنب الأخطاء
    TA_CENTER = 1
    TA_RIGHT = 2
    TA_LEFT = 0

# Template support
try:
    from jinja2 import Environment, FileSystemLoader, Template  # noqa: F401
    from PyQt6.QtCore import QUrl  # noqa: F401
    from PyQt6.QtGui import QTextDocument  # noqa: F401
    from PyQt6.QtPrintSupport import QPrinter  # noqa: F401
    TEMPLATE_SUPPORT = True
except ImportError as e:
    safe_print(f"WARNING: [PrintingService] Template libraries not available: {e}")
    safe_print("INFO: Install with: pip install Jinja2 PyQt6-WebEngine")
    TEMPLATE_SUPPORT = False

from core import schemas

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class PDFGenerator:
    """مولد ملفات PDF احترافية مع دعم العربية"""

    def __init__(self, settings_service=None):
        self.settings_service = settings_service
        self.company_info = self._get_company_info()

        # Colors (Sky Wave Brand)
        self.primary_color = colors.Color(0.23, 0.32, 0.52)  # Dark Blue #3b5284
        self.secondary_color = colors.Color(0.06, 0.72, 0.51)  # Green #10b981
        self.accent_color = colors.Color(0.4, 0.4, 0.4)  # Gray

        if not PDF_AVAILABLE:
            raise ImportError("PDF libraries not installed. Run: pip install reportlab arabic-reshaper python-bidi")

        # تسجيل الخطوط العربية
        self.arabic_font_name = self._register_arabic_fonts()

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
        """إصلاح النص العربي للعرض الصحيح في PDF"""
        if not text or not PDF_AVAILABLE:
            return str(text) if text else ""

        try:
            reshaped_text = arabic_reshaper.reshape(str(text))
            return str(get_display(reshaped_text))
        except Exception as e:
            safe_print(f"WARNING: [PDFGenerator] Arabic text fix failed: {e}")
            return str(text)

    def _register_arabic_fonts(self) -> str:
        """تسجيل خط Cairo العربي"""
        try:
            import sys
            
            # تحديد مسار خط Cairo
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # مسار خط Cairo
            cairo_font_path = os.path.join(base_path, "assets", "font", "Cairo-VariableFont_slnt,wght.ttf")
            
            if os.path.exists(cairo_font_path):
                try:
                    pdfmetrics.registerFont(TTFont('CairoFont', cairo_font_path))
                    safe_print(f"✅ [PDFGenerator] تم تحميل خط Cairo: {cairo_font_path}")
                    return 'CairoFont'
                except Exception as e:
                    safe_print(f"WARNING: [PDFGenerator] فشل تحميل خط Cairo: {e}")
            else:
                safe_print(f"⚠️ [PDFGenerator] خط Cairo غير موجود: {cairo_font_path}")

            # إذا فشل تحميل الخط، استخدم الخط الافتراضي
            safe_print("⚠️ [PDFGenerator] سيتم استخدام الخط الافتراضي")
            return 'Helvetica'

        except Exception as e:
            safe_print(f"ERROR: [PDFGenerator] خطأ في تسجيل الخطوط: {e}")
            return 'Helvetica'

    def _create_arabic_paragraph_style(self, name: str, font_size: int = 12,
                                     alignment=None, color=None) -> ParagraphStyle:
        # استخدام TA_RIGHT كـ default إذا لم يتم تحديد alignment
        if alignment is None:
            from reportlab.lib.enums import TA_RIGHT
            alignment = TA_RIGHT
        """إنشاء نمط فقرة للنص العربي"""
        return ParagraphStyle(
            name,
            fontName=self.arabic_font_name,
            fontSize=font_size,
            alignment=alignment,
            textColor=color or colors.black,
            rightIndent=0,
            leftIndent=0,
            spaceAfter=6,
            spaceBefore=6
        )

    def generate_invoice_pdf(
        self,
        project: schemas.Project,
        client_info: dict[str, str],
        output_path: str | None = None
    ) -> str:
        """
        إنتاج فاتورة PDF احترافية

        Args:
            project: بيانات المشروع
            client_info: معلومات العميل
            output_path: مسار الحفظ (اختياري)

        Returns:
            مسار الملف المُنتج
        """
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"invoice_{project.name}_{timestamp}.pdf"

        # إنشاء المستند
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        story = []

        # --- HEADER SECTION ---
        story.append(self._create_invoice_header(project))
        story.append(Spacer(1, 0.5*cm))

        # --- CLIENT INFO ---
        story.append(self._create_client_info_section(client_info))
        story.append(Spacer(1, 0.5*cm))

        # --- ITEMS TABLE ---
        story.append(self._create_items_table(project))
        story.append(Spacer(1, 0.5*cm))

        # --- TOTALS SECTION ---
        story.append(self._create_totals_section(project))
        story.append(Spacer(1, 0.5*cm))

        # --- FOOTER ---
        story.append(self._create_invoice_footer())

        # بناء المستند
        doc.build(story)

        safe_print(f"INFO: [PDFGenerator] Invoice PDF created: {output_path}")
        return output_path

    def generate_ledger_pdf(
        self,
        account: schemas.Account,
        transactions: list[dict[str, Any]],
        date_range: dict[str, datetime],
        output_path: str | None = None
    ) -> str:
        """
        إنتاج تقرير كشف حساب PDF

        Args:
            account: بيانات الحساب
            transactions: قائمة المعاملات
            date_range: نطاق التاريخ
            output_path: مسار الحفظ (اختياري)

        Returns:
            مسار الملف المُنتج
        """
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = account.name.replace(" ", "_").replace("/", "_")
            output_path = f"ledger_{safe_name}_{timestamp}.pdf"

        # إنشاء المستند
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        story = []

        # --- HEADER ---
        story.append(self._create_ledger_header(account, date_range))
        story.append(Spacer(1, 0.5*cm))

        # --- TRANSACTIONS TABLE ---
        story.append(self._create_transactions_table(transactions))
        story.append(Spacer(1, 0.5*cm))

        # --- SUMMARY ---
        story.append(self._create_ledger_summary(transactions))

        # بناء المستند
        doc.build(story)

        safe_print(f"INFO: [PDFGenerator] Ledger PDF created: {output_path}")
        return output_path

    def _create_invoice_header(self, project: schemas.Project) -> Table:
        """إنشاء رأس الفاتورة"""
        # بيانات الرأس
        header_data = [
            [
                self.fix_arabic_text(self.company_info["name"]),
                "",
                f"Invoice #{project.name}"
            ],
            [
                self.fix_arabic_text(self.company_info["tagline"]),
                "",
                f"Date: {datetime.now().strftime('%Y-%m-%d')}"
            ],
            [
                self.fix_arabic_text(f"{self.company_info['phone']} | {self.company_info['email']}"),
                "",
                f"Due: {project.end_date.strftime('%Y-%m-%d') if project.end_date else 'N/A'}"
            ]
        ]

        header_table = Table(header_data, colWidths=[6*cm, 2*cm, 6*cm])
        header_table.setStyle(TableStyle([
            # Company info (left) - استخدام الخط العربي
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), self.arabic_font_name),
            ('FONTSIZE', (0, 0), (0, 0), 16),
            ('FONTSIZE', (0, 1), (0, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, 0), self.primary_color),

            # Invoice info (right)
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica'),
            ('FONTSIZE', (2, 0), (2, 0), 14),
            ('FONTSIZE', (2, 1), (2, -1), 10),
            ('TEXTCOLOR', (2, 0), (2, 0), self.secondary_color),

            # General
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        return header_table

    def _create_client_info_section(self, client_info: dict[str, str]) -> Table:
        """إنشاء قسم معلومات العميل"""
        client_data = [
            ["Bill To:", ""],
            [self.fix_arabic_text(client_info.get("name", "N/A")), ""],
            [self.fix_arabic_text(client_info.get("phone", "")), ""],
            [self.fix_arabic_text(client_info.get("address", "")), ""]
        ]

        client_table = Table(client_data, colWidths=[8*cm, 6*cm])
        client_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), self.arabic_font_name),
            ('FONTSIZE', (0, 0), (0, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, 0), self.primary_color),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))

        return client_table

    def _create_items_table(self, project: schemas.Project) -> Table:
        """إنشاء جدول البنود"""
        # رأس الجدول
        headers = ["Service", "Qty", "Unit Price", "Discount", "Total"]
        table_data = [headers]

        # البنود
        for item in project.items:
            row = [
                self.fix_arabic_text(item.description),
                f"{item.quantity:.1f}",
                f"{item.unit_price:,.2f}",
                f"{item.discount_rate:.1f}%",
                f"{item.total:,.2f}"
            ]
            table_data.append(row)

        # إنشاء الجدول
        items_table = Table(table_data, colWidths=[6*cm, 2*cm, 2.5*cm, 2*cm, 2.5*cm])

        # تنسيق الجدول
        style = [
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

            # Data rows
            ('FONTNAME', (0, 1), (0, -1), self.arabic_font_name),  # Arabic font for service names
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),          # English font for numbers
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Numbers centered
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),     # Service names left

            # Borders
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ]

        items_table.setStyle(TableStyle(style))
        return items_table

    def _create_totals_section(self, project: schemas.Project) -> Table:
        """إنشاء قسم الإجماليات"""
        # حساب الإجماليات
        subtotal = sum(item.total for item in project.items)
        discount_amount = subtotal * (project.discount_rate / 100)
        taxable_amount = subtotal - discount_amount
        tax_amount = taxable_amount * (project.tax_rate / 100)
        total_amount = taxable_amount + tax_amount

        totals_data = [
            ["", "Subtotal:", f"{subtotal:,.2f} EGP"],
            ["", f"Discount ({project.discount_rate:.1f}%):", f"-{discount_amount:,.2f} EGP"],
            ["", f"Tax ({project.tax_rate:.1f}%):", f"{tax_amount:,.2f} EGP"],
            ["", "TOTAL:", f"{total_amount:,.2f} EGP"]
        ]

        totals_table = Table(totals_data, colWidths=[8*cm, 3*cm, 3*cm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -2), 10),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            ('TEXTCOLOR', (0, -1), (-1, -1), self.secondary_color),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('TOPPADDING', (0, -1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))

        return totals_table

    def _create_invoice_footer(self) -> Paragraph:
        """إنشاء تذييل الفاتورة"""
        footer_text = self.fix_arabic_text(
            "شكراً لثقتكم في Sky Wave. نسعد بخدمتكم دائماً."
        )

        style = ParagraphStyle(
            'Footer',
            fontSize=10,
            textColor=self.accent_color,
            alignment=TA_CENTER,
            spaceAfter=12
        )

        return Paragraph(footer_text, style)

    def _create_ledger_header(self, account: schemas.Account, date_range: dict[str, datetime]) -> Table:
        """إنشاء رأس كشف الحساب"""
        start_date = date_range.get('start', datetime.now()).strftime('%Y-%m-%d')
        end_date = date_range.get('end', datetime.now()).strftime('%Y-%m-%d')

        header_data = [
            ["Account Statement", "", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            [self.fix_arabic_text(f"{account.code} - {account.name}"), "", f"Period: {start_date} to {end_date}"],
            [self.fix_arabic_text(f"Type: {account.type.value}"), "", ""]
        ]

        header_table = Table(header_data, colWidths=[6*cm, 2*cm, 6*cm])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.primary_color),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        return header_table

    def _create_transactions_table(self, transactions: list[dict[str, Any]]) -> Table:
        """إنشاء جدول المعاملات"""
        # رأس الجدول
        headers = ["Date", "Description", "Reference", "Debit", "Credit", "Balance"]
        table_data = [headers]

        # المعاملات
        for txn in transactions:
            row = [
                txn.get('date', '').strftime('%Y-%m-%d') if isinstance(txn.get('date'), datetime) else str(txn.get('date', '')),
                self.fix_arabic_text(txn.get('description', '')),
                txn.get('reference', ''),
                f"{txn.get('debit', 0):,.2f}" if txn.get('debit', 0) > 0 else "",
                f"{txn.get('credit', 0):,.2f}" if txn.get('credit', 0) > 0 else "",
                f"{txn.get('balance', 0):,.2f}"
            ]
            table_data.append(row)

        # إنشاء الجدول
        txn_table = Table(table_data, colWidths=[2*cm, 4*cm, 2*cm, 2.5*cm, 2.5*cm, 2*cm])

        # تنسيق الجدول
        style = [
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

            # Data
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Date
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # Description
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Numbers

            # Borders
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Alternating rows
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ]

        txn_table.setStyle(TableStyle(style))
        return txn_table

    def _create_ledger_summary(self, transactions: list[dict[str, Any]]) -> Table:
        """إنشاء ملخص كشف الحساب"""
        total_debit = sum(txn.get('debit', 0) for txn in transactions)
        total_credit = sum(txn.get('credit', 0) for txn in transactions)
        ending_balance = transactions[-1].get('balance', 0) if transactions else 0

        summary_data = [
            ["", "Total Debits:", f"{total_debit:,.2f} EGP"],
            ["", "Total Credits:", f"{total_credit:,.2f} EGP"],
            ["", "Ending Balance:", f"{ending_balance:,.2f} EGP"]
        ]

        summary_table = Table(summary_data, colWidths=[8*cm, 3*cm, 3*cm])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -2), 10),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            ('TEXTCOLOR', (0, -1), (-1, -1), self.secondary_color),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))

        return summary_table

    @staticmethod
    def open_pdf(file_path: str):
        """فتح ملف PDF في العارض الافتراضي"""
        try:
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', file_path])

            safe_print(f"INFO: [PDFGenerator] Opened PDF: {file_path}")
        except Exception as e:
            safe_print(f"ERROR: [PDFGenerator] Failed to open PDF: {e}")


class PrintingService:
    """خدمة الطباعة الرئيسية"""

    def __init__(self, settings_service=None, template_service=None):
        self.settings_service = settings_service
        self.template_service = template_service  # ✅ إضافة template_service

        if PDF_AVAILABLE:
            self.pdf_generator = PDFGenerator(settings_service)
            safe_print("INFO: [PrintingService] PDF printing service initialized")
        else:
            self.pdf_generator = None
            safe_print("WARNING: [PrintingService] PDF libraries not available")

    def is_available(self) -> bool:
        """التحقق من توفر خدمة الطباعة"""
        return PDF_AVAILABLE and self.pdf_generator is not None

    def print_project_invoice(
        self,
        project: schemas.Project,
        client_info: dict[str, str],
        payments: list[dict[str, Any]] | None = None,
        background_image_path: str | None = None,
        auto_open: bool = True
    ) -> str | None:
        """
        طباعة فاتورة مشروع مع الدفعات

        Args:
            project: بيانات المشروع
            client_info: معلومات العميل
            payments: قائمة الدفعات
            background_image_path: مسار صورة الخلفية (اختياري)
            auto_open: فتح الملف تلقائياً

        Returns:
            مسار ملف PDF أو None
        """
        try:
            # استخدام خدمة القوالب إذا كانت متوفرة
            return self.print_invoice_with_template(
                project=project,
                client_info=client_info,
                template_service=self.template_service,
                payments=payments,
                auto_open=auto_open
            )
        except Exception as e:
            safe_print(f"ERROR: [PrintingService] Failed to print project invoice: {e}")
            import traceback
            traceback.print_exc()
            return None

    def print_invoice(
        self,
        project: schemas.Project,
        client_info: dict[str, str],
        auto_open: bool = True
    ) -> str | None:
        """طباعة فاتورة مشروع"""
        if not self.is_available():
            safe_print("ERROR: [PrintingService] PDF libraries not installed")
            return None

        try:
            pdf_path = self.pdf_generator.generate_invoice_pdf(project, client_info)

            if auto_open:
                PDFGenerator.open_pdf(pdf_path)

            return str(pdf_path) if pdf_path else None
        except Exception as e:
            safe_print(f"ERROR: [PrintingService] Failed to print invoice: {e}")
            return None

    def print_ledger(
        self,
        account: schemas.Account,
        transactions: list[dict[str, Any]],
        date_range: dict[str, datetime],
        auto_open: bool = True
    ) -> str | None:
        """طباعة كشف حساب"""
        if not self.is_available():
            safe_print("ERROR: [PrintingService] PDF libraries not installed")
            return None

        try:
            pdf_path = self.pdf_generator.generate_ledger_pdf(account, transactions, date_range)

            if auto_open:
                PDFGenerator.open_pdf(pdf_path)

            return str(pdf_path) if pdf_path else None
        except Exception as e:
            safe_print(f"ERROR: [PrintingService] Failed to print ledger: {e}")
            return None

    def get_available_templates(self) -> list[str]:
        """الحصول على قائمة القوالب المتاحة"""
        templates_dir = "assets/templates/invoices"
        if not os.path.exists(templates_dir):
            return []

        templates = []
        for file in os.listdir(templates_dir):
            if file.endswith('.html'):
                template_name = file.replace('.html', '')
                templates.append(template_name)

        return templates

    def print_invoice_with_template(
        self,
        project: schemas.Project,
        client_info: dict[str, str],
        template_service=None,
        payments: list[dict[str, Any]] | None = None,
        auto_open: bool = True
    ) -> str | None:
        """طباعة فاتورة باستخدام قالب HTML من خدمة القوالب"""
        try:
            # استخدام خدمة القوالب الجديدة إذا كانت متوفرة
            if template_service:
                safe_print("INFO: [PrintingService] Using template service for invoice generation")
                safe_print(f"INFO: [PrintingService] عدد الدفعات المستلمة: {len(payments) if payments else 0}")
                if payments:
                    for i, p in enumerate(payments):
                        safe_print(f"  - دفعة {i+1}: {p}")

                # إنتاج HTML باستخدام خدمة القوالب مع الدفعات
                html_content = template_service.generate_invoice_html(project, client_info, payments=payments)

                if html_content and not html_content.startswith("<html><body><h1>خطأ"):
                    # حفظ HTML
                    client_phone = client_info.get('phone', '') if client_info else ''
                    html_path = self._html_to_pdf(html_content, project.name, client_phone)

                    if auto_open and html_path:
                        # فتح HTML في المتصفح
                        import webbrowser
                        webbrowser.open(f'file://{os.path.abspath(html_path)}')

                    safe_print(f"INFO: [PrintingService] Invoice created using template: {html_path}")
                    return html_path
                else:
                    safe_print("ERROR: [PrintingService] Failed to generate HTML from template service")

            # Fallback: استخدام النظام القديم
            safe_print("INFO: [PrintingService] Falling back to default PDF generation")
            return self.print_invoice(project, client_info, auto_open)

        except Exception as e:
            safe_print(f"ERROR: [PrintingService] Failed to print invoice with template: {e}")
            # Fallback to default PDF
            return self.print_invoice(project, client_info, auto_open)

    def _prepare_template_data(self, project: schemas.Project, client_info: dict[str, str]) -> dict[str, Any]:
        """تحضير البيانات للقالب"""
        # معلومات الشركة
        company_data = {
            'company_name': self.settings_service.get_setting("company_name") if self.settings_service else "SkyWave ERP",
            'company_tagline': "نظام إدارة المشاريع الذكي",
            'company_phone': self.settings_service.get_setting("company_phone") if self.settings_service else "01000000000",
            'company_email': self.settings_service.get_setting("company_email") if self.settings_service else "info@skywave.com",
            'company_website': self.settings_service.get_setting("company_website") if self.settings_service else "www.skywave.com",
            'company_address': self.settings_service.get_setting("company_address") if self.settings_service else "القاهرة، مصر",
        }

        # معلومات الفاتورة
        # ⚡ استخدم رقم الفاتورة المحفوظ أولاً، وإلا ولّد رقم جديد
        invoice_number = getattr(project, 'invoice_number', None)
        if not invoice_number:
            local_id = getattr(project, 'id', None) or 1
            invoice_number = f"SW-{97161 + int(local_id)}"
        invoice_data = {
            'invoice_number': invoice_number,
            'invoice_date': datetime.now().strftime("%Y-%m-%d"),
            'due_date': project.due_date.strftime("%Y-%m-%d") if hasattr(project, 'due_date') and project.due_date else "غير محدد",
        }

        # معلومات العميل
        client_data = {
            'client_name': client_info.get('name', 'عميل'),
            'client_phone': client_info.get('phone', 'غير محدد'),
            'client_address': client_info.get('address', 'غير محدد'),
            'client_email': client_info.get('email', 'غير محدد'),
        }

        # معلومات المشروع
        project_data = {
            'project_name': project.name,
            'project_status': getattr(project, 'status', None) or "نشط",
            'project_duration': f"{getattr(project, 'duration_days', 0)} يوم" if getattr(project, 'duration_days', None) else "غير محدد",
        }

        # بنود المشروع
        items = []
        if hasattr(project, 'items') and project.items:
            for item in project.items:
                if isinstance(item, dict):
                    # البند عبارة عن dictionary
                    items.append({
                        'name': item.get('service_name', 'خدمة'),
                        'quantity': item.get('quantity', 1),
                        'price': float(item.get('unit_price', 0)),
                        'discount': float(item.get('discount_rate', 0)),
                        'total': float(item.get('total_price', 0))
                    })
                else:
                    # البند عبارة عن object (ProjectItem)
                    items.append({
                        'name': getattr(item, 'description', 'خدمة'),
                        'quantity': getattr(item, 'quantity', 1),
                        'price': float(getattr(item, 'unit_price', 0)),
                        'discount': float(getattr(item, 'discount_rate', 0)),
                        'total': float(getattr(item, 'total', 0))
                    })
        else:
            # إذا لم تكن هناك بنود، أنشئ بند واحد للمشروع كاملاً
            items.append({
                'name': project.name,
                'quantity': 1,
                'price': float(project.total_amount),
                'discount': 0,
                'total': float(project.total_amount)
            })

        # الحسابات المالية
        subtotal = sum(float(item['total']) for item in items)
        discount_rate = 0  # يمكن إضافتها لاحقاً
        tax_rate = float(self.settings_service.get_setting("default_tax_rate") or 0) if self.settings_service else 0

        discount_amount = subtotal * (discount_rate / 100)
        tax_amount = (subtotal - discount_amount) * (tax_rate / 100)
        total_amount = subtotal - discount_amount + tax_amount

        # حساب المبالغ المدفوعة والمتبقية
        try:
            # جلب الدفعات من قاعدة البيانات
            from core.repository import Repository
            if hasattr(self, 'repo') and self.repo:
                payments = self.repo.get_payments_for_project(project.name)
                amount_paid = sum(payment.amount for payment in payments)
            else:
                # إنشاء repository مؤقت لجلب الدفعات
                temp_repo = Repository()
                payments = temp_repo.get_payments_for_project(project.name)
                amount_paid = sum(payment.amount for payment in payments)
        except Exception as e:
            safe_print(f"WARNING: [PrintingService] فشل جلب الدفعات: {e}")
            # استخدام القيمة من المشروع إذا كانت متوفرة
            amount_paid = getattr(project, 'amount_paid', 0) or 0

        financial_data = {
            'items': items,
            'subtotal': subtotal,
            'discount_rate': discount_rate,
            'discount_amount': discount_amount,
            'tax_rate': tax_rate,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            'amount_paid': amount_paid,
            'remaining_amount': total_amount - amount_paid,
        }

        # دمج كل البيانات
        template_data = {
            **company_data,
            **invoice_data,
            **client_data,
            **project_data,
            **financial_data
        }

        return template_data

    def _html_to_pdf(self, html_content: str, filename_prefix: str, client_phone: str | None = None) -> str | None:
        """تحويل HTML إلى PDF"""
        try:
            # ⚡ حفظ الفواتير في مجلد exports داخل مسار التثبيت
            if getattr(sys, 'frozen', False):
                # البرنامج مجمع (EXE) - مسار التثبيت هو مجلد الـ EXE
                install_path = os.path.dirname(sys.executable)
            else:
                # البرنامج يعمل من Python
                install_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            exports_dir = os.path.join(install_path, "exports")
            if not os.path.exists(exports_dir):
                os.makedirs(exports_dir)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = "".join(c for c in filename_prefix if c.isalnum() or c in (' ', '-', '_')).rstrip()
            pdf_path = os.path.join(exports_dir, f"invoice_{safe_filename}_{timestamp}.pdf")
            html_path = pdf_path.replace('.pdf', '.html')

            # حفظ HTML أولاً
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            # محاولة 1: استخدام pdfkit مع wkhtmltopdf
            try:
                import pdfkit
                # البحث عن wkhtmltopdf
                wkhtmltopdf_paths = [
                    r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe',
                    r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe',
                    'wkhtmltopdf'
                ]

                config = None
                for path in wkhtmltopdf_paths:
                    if os.path.exists(path) or path == 'wkhtmltopdf':
                        try:
                            config = pdfkit.configuration(wkhtmltopdf=path)
                            break
                        except OSError:
                            continue

                options = {
                    'page-size': 'A4',
                    'encoding': 'UTF-8',
                    'enable-local-file-access': None
                }

                if config:
                    pdfkit.from_file(html_path, pdf_path, configuration=config, options=options)
                else:
                    pdfkit.from_file(html_path, pdf_path, options=options)

                safe_print(f"INFO: [PrintingService] Invoice PDF created with pdfkit: {pdf_path}")
                # حذف HTML بعد إنشاء PDF
                os.remove(html_path)
                safe_print(f"🗑️ Cleaned up temp HTML file: {html_path}")

                # فتح المجلد
                self._open_exports_folder()

                return pdf_path

            except ImportError:
                safe_print("WARNING: [PrintingService] pdfkit not installed")
            except Exception as e:
                safe_print(f"WARNING: [PrintingService] pdfkit failed: {e}")

            # محاولة 2: استخدام Chrome/Edge headless
            try:
                chrome_paths = [
                    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                ]

                browser_path = None
                for path in chrome_paths:
                    if os.path.exists(path):
                        browser_path = path
                        break

                if browser_path:
                    abs_html_path = os.path.abspath(html_path)
                    abs_pdf_path = os.path.abspath(pdf_path)

                    cmd = [
                        browser_path,
                        '--headless',
                        '--disable-gpu',
                        '--print-to-pdf=' + abs_pdf_path,
                        '--no-margins',
                        'file:///' + abs_html_path.replace('\\', '/')
                    ]

                    subprocess.run(cmd, capture_output=True, timeout=30)

                    if os.path.exists(pdf_path):
                        safe_print(f"INFO: [PrintingService] Invoice PDF created with browser: {pdf_path}")
                        os.remove(html_path)
                        safe_print(f"🗑️ Cleaned up temp HTML file: {html_path}")

                        # فتح المجلد
                        self._open_exports_folder()

                        return pdf_path

            except Exception as e:
                safe_print(f"WARNING: [PrintingService] Browser PDF failed: {e}")

            # Fallback: حفظ HTML كبديل
            safe_print("WARNING: [PrintingService] Failed to create PDF. Saving as HTML instead.")
            safe_print("INFO: To generate PDF, please install one of the following:")
            safe_print("   1. wkhtmltopdf: https://wkhtmltopdf.org/downloads.html")
            safe_print("   2. Google Chrome or Microsoft Edge")

            # فتح المجلد
            self._open_exports_folder()

            return html_path

        except Exception as e:
            safe_print(f"ERROR: [PrintingService] Failed to create PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _open_exports_folder(self):
        """فتح مجلد exports تلقائياً"""
        try:
            # ⚡ فتح مجلد exports داخل مسار التثبيت
            if getattr(sys, 'frozen', False):
                install_path = os.path.dirname(sys.executable)
            else:
                install_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            exports_dir = os.path.join(install_path, "exports")

            if os.path.exists(exports_dir):
                if platform.system() == 'Windows':
                    os.startfile(exports_dir)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', exports_dir])
                else:  # Linux
                    subprocess.run(['xdg-open', exports_dir])
                safe_print(f"INFO: [PrintingService] Opened exports folder: {exports_dir}")
            else:
                safe_print(f"WARNING: [PrintingService] Exports folder not found: {exports_dir}")
        except Exception as e:
            safe_print(f"ERROR: [PrintingService] Failed to open exports folder: {e}")




class TemplateManager:
    """مدير قوالب الفواتير"""

    def __init__(self, settings_service=None):
        self.settings_service = settings_service
        self.templates_dir = "assets/templates/invoices"

    def get_available_templates(self) -> list[dict[str, str]]:
        """الحصول على قائمة القوالب المتاحة مع أسمائها"""
        templates: list[dict[str, str]] = []

        if not os.path.exists(self.templates_dir):
            return templates

        template_names = {
            'modern_blue': '🌟 أزرق عصري',
            'classic_professional': '📋 كلاسيكي احترافي',
            'skywave_ads_invoice_template': '🚀 SkyWave Ads',
        }

        for file in os.listdir(self.templates_dir):
            if file.endswith('.html'):
                template_id = file.replace('.html', '')
                template_name = template_names.get(template_id, template_id)

                templates.append({
                    'id': template_id,
                    'name': template_name,
                    'file': file
                })

        return templates

    def get_active_template(self) -> str:
        """الحصول على القالب النشط"""
        if self.settings_service:
            return self.settings_service.get_setting("invoice_template") or "modern_blue"
        return "modern_blue"

    def set_active_template(self, template_id: str) -> bool:
        """تعيين القالب النشط"""
        try:
            template_path = os.path.join(self.templates_dir, f"{template_id}.html")

            if not os.path.exists(template_path):
                safe_print(f"ERROR: [TemplateManager] Template {template_id} not found")
                return False

            if self.settings_service:
                self.settings_service.update_setting("invoice_template", template_id)
                safe_print(f"INFO: [TemplateManager] Active template set to: {template_id}")
                return True

            return False

        except Exception as e:
            safe_print(f"ERROR: [TemplateManager] Failed to set active template: {e}")
            return False

    def preview_template(self, template_id: str, sample_data: dict[str, Any] | None = None) -> str | None:
        """معاينة القالب مع بيانات تجريبية"""
        try:
            template_path = os.path.join(self.templates_dir, f"{template_id}.html")

            if not os.path.exists(template_path):
                return None

            # بيانات تجريبية
            if not sample_data:
                sample_data = {
                    'company_name': 'SkyWave ERP',
                    'company_tagline': 'نظام إدارة المشاريع الذكي',
                    'company_phone': '01000000000',
                    'company_email': 'info@skywave.com',
                    'company_website': 'www.skywave.com',
                    'company_address': 'القاهرة، مصر',
                    'invoice_number': 'INV-000001',
                    'invoice_date': '2025-12-01',
                    'due_date': '2025-12-15',
                    'client_name': 'عميل تجريبي',
                    'client_phone': '01111111111',
                    'client_address': 'عنوان العميل',
                    'client_email': 'client@example.com',
                    'project_name': 'مشروع تجريبي',
                    'project_status': 'نشط',
                    'project_duration': '30 يوم',
                    'items': [
                        {
                            'name': 'تطوير موقع إلكتروني',
                            'quantity': 1,
                            'price': 5000.00,
                            'discount': 10.0,
                            'total': 4500.00
                        },
                        {
                            'name': 'تصميم هوية بصرية',
                            'quantity': 1,
                            'price': 2000.00,
                            'discount': 0.0,
                            'total': 2000.00
                        }
                    ],
                    'subtotal': 6500.00,
                    'discount_rate': 7.69,
                    'discount_amount': 500.00,
                    'tax_rate': 14.0,
                    'tax_amount': 840.00,
                    'total_amount': 6840.00
                }

            # تحميل وتصيير القالب
            with open(template_path, encoding='utf-8') as f:
                template_content = f.read()

            template = Template(template_content)
            html_content = template.render(**sample_data)

            return html_content

        except Exception as e:
            safe_print(f"ERROR: [TemplateManager] Failed to preview template: {e}")
            return None
