# pylint: disable=too-many-lines,too-many-nested-blocks,too-many-positional-arguments
# الملف: services/template_service.py
"""
خدمة قوالب الفواتير - إدارة وإنتاج قوالب HTML للفواتير
"""

import base64
import os
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QEventLoop, QTimer, QUrl
from PyQt6.QtWidgets import QApplication

from core import schemas
from core.base_service import BaseService
from core.logo_utils import print_logo_png_data_url

# ⚡ استيراد مكتبات PDF الاختيارية
WEASYPRINT_AVAILABLE: bool | None = None
WEASYPRINT_IMPORT_ERROR: str | None = None
CSS = None
HTML = None


def _try_get_weasyprint():
    global CSS, HTML, WEASYPRINT_AVAILABLE, WEASYPRINT_IMPORT_ERROR

    if WEASYPRINT_AVAILABLE is True:
        return CSS, HTML
    if WEASYPRINT_AVAILABLE is False:
        return None

    try:
        probe = subprocess.run(
            [sys.executable, "-c", "import weasyprint"],
            capture_output=True,
            text=True,
            check=False,
        )
        combined = (probe.stdout or "") + (probe.stderr or "")
        if probe.returncode != 0 or "could not import some external libraries" in combined.lower():
            WEASYPRINT_AVAILABLE = False
            WEASYPRINT_IMPORT_ERROR = (combined.strip() or f"returncode={probe.returncode}")[:500]
            return None

        from weasyprint import CSS as css_type
        from weasyprint import HTML as html_type

        CSS = css_type
        HTML = html_type
        WEASYPRINT_AVAILABLE = True
        return CSS, HTML
    except Exception as e:
        WEASYPRINT_AVAILABLE = False
        WEASYPRINT_IMPORT_ERROR = str(e)
        return None


pdfkit_available = False
try:
    import pdfkit

    pdfkit_available = True
except Exception:
    pass

qwebengine_available = False
try:
    if not getattr(sys, "frozen", False):
        import importlib

        importlib.import_module("PyQt6.QtWebEngineWidgets")
        qwebengine_available = True
except Exception:
    pass

# ⚡ استيراد آمن لـ jinja2
try:
    from jinja2 import Environment, FileSystemLoader

    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    Environment = None
    FileSystemLoader = None

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


def get_base_path():
    """الحصول على المسار الأساسي للتطبيق - يعمل مع PyInstaller و Python العادي"""
    if getattr(sys, "frozen", False):
        # التطبيق يعمل كـ EXE (PyInstaller)
        return os.path.dirname(sys.executable)
    else:
        # التطبيق يعمل كـ Python script
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TemplateService(BaseService):
    """خدمة إدارة قوالب الفواتير"""

    @property
    def entity_name(self) -> str:
        return "invoice_templates"

    def __init__(self, repository, settings_service=None):
        super().__init__(repository)
        self.settings_service = settings_service

        # إعداد مجلد القوالب - المسار الصحيح للـ PyInstaller
        base_path = get_base_path()

        # جرب المسارات المختلفة
        possible_paths = [
            os.path.join(
                base_path, "_internal", "assets", "templates", "invoices"
            ),  # PyInstaller onedir
            os.path.join(
                base_path, "assets", "templates", "invoices"
            ),  # PyInstaller onefile أو dev
            os.path.join(
                os.path.dirname(sys.executable), "_internal", "assets", "templates", "invoices"
            ),
            os.path.join("assets", "templates", "invoices"),  # مسار نسبي
        ]

        self.templates_dir = None
        for path in possible_paths:
            if os.path.exists(path):
                self.templates_dir = path
                safe_print(f"INFO: [TemplateService] Found templates at: {path}")
                break

        if not self.templates_dir:
            # إنشاء المجلد الافتراضي
            self.templates_dir = os.path.join("assets", "templates", "invoices")
            os.makedirs(self.templates_dir, exist_ok=True)
            safe_print(
                f"WARNING: [TemplateService] Created templates directory: {self.templates_dir}"
            )

        if not JINJA2_AVAILABLE or Environment is None or FileSystemLoader is None:
            raise RuntimeError("Jinja2 is required for template rendering")

        self.jinja_env = Environment(loader=FileSystemLoader(self.templates_dir), autoescape=True)

        # إضافة فلاتر مخصصة
        self.jinja_env.filters["format_currency"] = self._format_currency

        safe_print(f"INFO: [TemplateService] Templates directory: {self.templates_dir}")

        # إنشاء جدول القوالب
        self._create_templates_table()

    @staticmethod
    def _sanitize_template_filename(name: str) -> str:
        if not isinstance(name, str):
            raise ValueError("Template name must be a string")
        normalized = re.sub(r"\s+", "_", name.strip().lower())
        if not normalized:
            raise ValueError("Template name must not be empty")
        if any(sep in normalized for sep in ["/", "\\", ":", "\x00"]):
            raise ValueError("Invalid characters in template name")
        if ".." in normalized:
            raise ValueError("Invalid template name")
        normalized = normalized.strip("._")
        normalized = re.sub(r"[^0-9a-z_\u0600-\u06FF-]+", "", normalized)
        normalized = normalized[:120] if len(normalized) > 120 else normalized
        if not normalized:
            raise ValueError("Invalid template name")
        return f"{normalized}.html"

    def _safe_template_path(self, filename: str) -> str:
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("Invalid template filename")
        if any(sep in filename for sep in ["/", "\\", ":", "\x00"]):
            raise ValueError("Invalid template filename")
        if ".." in filename:
            raise ValueError("Invalid template filename")
        if not filename.lower().endswith(".html"):
            raise ValueError("Template filename must end with .html")

        root = os.path.realpath(self.templates_dir)
        full = os.path.realpath(os.path.join(root, filename))
        if full == root or not full.startswith(root + os.sep):
            raise ValueError("Template path is outside templates directory")
        return full

    def _create_templates_table(self):
        """إنشاء جدول قوالب الفواتير"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS invoice_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            template_file TEXT NOT NULL,
            is_default BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """

        try:
            cursor = self.repo.get_cursor()
            try:
                cursor.execute(create_table_sql)
                self.repo.sqlite_conn.commit()
            finally:
                cursor.close()

            # إضافة القالب الافتراضي إذا لم يكن موجوداً
            self._add_default_template()

        except Exception as e:
            safe_print(f"ERROR: خطأ في إنشاء جدول القوالب: {e}")

    @staticmethod
    def _format_currency(value):
        """تنسيق الأرقام بفواصل الآلاف"""
        try:
            if isinstance(value, str):
                value = float(value.replace(",", ""))
            return f"{value:,.2f}"
        except (ValueError, AttributeError, TypeError):
            return str(value)

    def _add_default_template(self):
        """إضافة القالب الافتراضي"""
        cursor = None
        try:
            cursor = self.repo.get_cursor()
            # التحقق من وجود أي قالب افتراضي
            check_sql = "SELECT COUNT(*) FROM invoice_templates WHERE is_default = 1"
            cursor.execute(check_sql)
            count = cursor.fetchone()[0]

            if count == 0:
                # التحقق من وجود القالب في المجلد
                template_file = "final_invoice.html"
                try:
                    template_path = self._safe_template_path(template_file)
                except ValueError:
                    template_path = ""

                if not template_path or not os.path.exists(template_path):
                    # جرب القوالب الأخرى
                    for alt_template in ["final_invoice.html", "skywave_ads_invoice_template.html"]:
                        try:
                            alt_path = self._safe_template_path(alt_template)
                        except ValueError:
                            continue
                        if os.path.exists(alt_path):
                            template_file = alt_template
                            break

                insert_sql = """
                INSERT INTO invoice_templates (name, description, template_file, is_default)
                VALUES (?, ?, ?, ?)
                """
                cursor.execute(
                    insert_sql,
                    (
                        "Sky Wave Professional",
                        "القالب الاحترافي لفواتير Sky Wave",
                        template_file,
                        1,
                    ),
                )
                self.repo.sqlite_conn.commit()
                safe_print(f"INFO: تم إضافة القالب الافتراضي: {template_file}")

        except Exception as e:
            safe_print(f"ERROR: خطأ في إضافة القالب الافتراضي: {e}")
        finally:
            if cursor:
                cursor.close()

    def get_all_templates(self) -> list[dict[str, Any]]:
        """جلب جميع القوالب"""
        cursor = None
        try:
            cursor = self.repo.get_cursor()
            select_sql = """
            SELECT id, name, description, template_file, is_default, created_at
            FROM invoice_templates
            ORDER BY is_default DESC, name ASC
            """

            cursor.execute(select_sql)
            rows = cursor.fetchall()

            templates = []
            for row in rows:
                templates.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "template_file": row[3],
                        "is_default": bool(row[4]),
                        "created_at": row[5],
                    }
                )

            return templates

        except Exception as e:
            safe_print(f"ERROR: خطأ في جلب القوالب: {e}")
            return []
        finally:
            if cursor:
                cursor.close()

    def get_template_by_id(self, template_id: int) -> dict[str, Any] | None:
        """جلب قالب بالمعرف"""
        cursor = None
        try:
            cursor = self.repo.get_cursor()
            select_sql = """
            SELECT id, name, description, template_file, is_default, created_at
            FROM invoice_templates
            WHERE id = ?
            """

            cursor.execute(select_sql, (template_id,))
            row = cursor.fetchone()

            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "template_file": row[3],
                    "is_default": bool(row[4]),
                    "created_at": row[5],
                }

            return None

        except Exception as e:
            safe_print(f"ERROR: خطأ في جلب القالب: {e}")
            return None
        finally:
            if cursor:
                cursor.close()

    def get_default_template(self) -> dict[str, Any] | None:
        """جلب القالب الافتراضي"""
        cursor = None
        try:
            cursor = self.repo.get_cursor()
            select_sql = """
            SELECT id, name, description, template_file, is_default, created_at
            FROM invoice_templates
            WHERE is_default = 1
            LIMIT 1
            """

            cursor.execute(select_sql)
            row = cursor.fetchone()

            if row:
                template_file = row[3]
                # التحقق من وجود الملف فعلياً
                try:
                    template_path = self._safe_template_path(template_file)
                except ValueError:
                    template_path = ""
                if not template_path or not os.path.exists(template_path):
                    safe_print(
                        f"WARNING: [TemplateService] Template file not found: {template_file}"
                    )
                    # البحث عن قالب بديل
                    for alt_template in ["skywave_ads_invoice_template.html"]:
                        try:
                            alt_path = self._safe_template_path(alt_template)
                        except ValueError:
                            continue
                        if os.path.exists(alt_path):
                            safe_print(
                                f"INFO: [TemplateService] Using alternative template: {alt_template}"
                            )
                            template_file = alt_template
                            # تحديث قاعدة البيانات
                            update_sql = (
                                "UPDATE invoice_templates SET template_file = ? WHERE id = ?"
                            )
                            cursor.execute(update_sql, (template_file, row[0]))
                            self.repo.sqlite_conn.commit()
                            break

                return {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "template_file": template_file,
                    "is_default": bool(row[4]),
                    "created_at": row[5],
                }

            # إذا لم يوجد قالب افتراضي، إرجاع الأول
            templates = self.get_all_templates()
            return templates[0] if templates else None

        except Exception as e:
            safe_print(f"ERROR: خطأ في جلب القالب الافتراضي: {e}")
            return None
        finally:
            if cursor:
                cursor.close()

    def generate_invoice_html(
        self,
        project: schemas.Project,
        client_info: dict[str, str],
        template_id: int | None = None,
        payments: list[dict[str, Any]] | None = None,
    ) -> str:
        """إنتاج HTML للفاتورة باستخدام القالب"""
        try:
            # جلب القالب
            if template_id:
                template_info = self.get_template_by_id(template_id)
            else:
                template_info = self.get_default_template()

            if not template_info:
                raise ValueError("لم يتم العثور على قالب مناسب")

            # تحميل القالب
            template_file = template_info["template_file"]
            safe_print(f"INFO: [TemplateService] Loading template: {template_file}")
            template = self.jinja_env.get_template(template_file)
            safe_print(f"INFO: [TemplateService] Template loaded successfully: {template_file}")

            # تحضير البيانات
            template_data = self._prepare_template_data(project, client_info, payments)

            # إنتاج HTML
            safe_print(
                f"INFO: [TemplateService] Rendering template with data keys: {list(template_data.keys())}"
            )
            html_content = template.render(**template_data)
            safe_print(
                f"INFO: [TemplateService] Template rendered successfully, HTML size: {len(html_content)} chars"
            )

            if "SKYWAVE_CUSTOM_TEMPLATE_2025" in html_content:
                safe_print("✅ [TemplateService] Custom template is being used correctly!")

            return str(html_content)

        except Exception as e:
            safe_print(f"ERROR: خطأ في إنتاج HTML للفاتورة: {e}")

            traceback.print_exc()
            return f"<html><body><h1>خطأ في إنتاج الفاتورة: {e}</h1></body></html>"

    def _prepare_template_data(
        self,
        project: schemas.Project,
        client_info: dict[str, str],
        payments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """تحضير بيانات القالب"""
        try:
            # التأكد من أن project هو كائن صحيح وليس dict
            if isinstance(project, dict):
                safe_print(
                    "WARNING: [TemplateService] project is a dict, converting to object-like access"
                )

                # تحويل dict إلى object للوصول للخصائص
                class DictToObj:
                    def __init__(self, d):
                        for key, value in d.items():
                            setattr(self, key, value)

                project = DictToObj(project)

            # التحقق من وجود الخصائص الأساسية وإضافتها إذا لزم الأمر
            if not hasattr(project, "name"):
                safe_print(
                    "WARNING: [TemplateService] Project object missing 'name' attribute, adding default"
                )
                # إضافة قيمة افتراضية بدلاً من رفع خطأ
                project.name = "مشروع"

            # التحقق من الخصائص الأخرى المطلوبة
            if not hasattr(project, "id"):
                project.id = None
            if not hasattr(project, "items"):
                project.items = []
            if not hasattr(project, "total_amount"):
                project.total_amount = 0
            if not hasattr(project, "discount_rate"):
                project.discount_rate = 0
            if not hasattr(project, "tax_rate"):
                project.tax_rate = 0

            # ⚡ حساب الإجماليات بشكل صحيح:
            # - gross_total = مجموع (الكمية × السعر) قبل أي خصم (الإجمالي الكلي)
            # - grand_total = المبلغ النهائي بعد الخصم (الإجمالي الفرعي)

            # حساب الإجمالي الكلي (قبل الخصم) من البنود
            gross_total = 0.0
            items_total_after_discount = 0.0

            if hasattr(project, "items") and project.items and len(project.items) > 0:
                for item in project.items:
                    if isinstance(item, dict):
                        qty = float(item.get("quantity", 1))
                        price = float(item.get("unit_price", 0))
                        item_total = float(item.get("total", 0))
                    else:
                        qty = float(getattr(item, "quantity", 1))
                        price = float(getattr(item, "unit_price", 0))
                        item_total = float(getattr(item, "total", 0))

                    gross_total += qty * price  # قبل الخصم
                    items_total_after_discount += item_total  # بعد خصم البند

            # حساب إجمالي الخصم على البنود
            items_discount = gross_total - items_total_after_discount

            # خصم إضافي على مستوى المشروع
            project_discount_rate = float(getattr(project, "discount_rate", 0) or 0)
            project_discount = items_total_after_discount * (project_discount_rate / 100)

            # الإجمالي النهائي (بعد كل الخصومات)
            taxable = items_total_after_discount - project_discount
            tax_rate = float(getattr(project, "tax_rate", 0) or 0)
            tax_amount = taxable * (tax_rate / 100)

            # ⚡ استخدم الحسابات الجديدة دايماً (مش من المشروع)
            grand_total = taxable + tax_amount

            # إجمالي الخصم الكلي = خصم البنود + خصم المشروع
            discount_amount = items_discount + project_discount

            # إذا لم يكن هناك gross_total، استخدم subtotal من المشروع
            if gross_total == 0:
                gross_total = float(getattr(project, "subtotal", 0) or 0)
                if gross_total == 0:
                    gross_total = grand_total + discount_amount

            safe_print("INFO: [TemplateService] ====== حسابات الفاتورة ======")
            safe_print(f"INFO: [TemplateService] مجموع البنود (قبل خصم البند): {gross_total}")
            safe_print(
                f"INFO: [TemplateService] مجموع البنود (بعد خصم البند): {items_total_after_discount}"
            )
            safe_print(f"INFO: [TemplateService] خصم البنود: {items_discount}")
            safe_print(f"INFO: [TemplateService] نسبة خصم المشروع: {project_discount_rate}%")
            safe_print(f"INFO: [TemplateService] مبلغ خصم المشروع: {project_discount}")
            safe_print(f"INFO: [TemplateService] إجمالي الخصم: {discount_amount}")
            safe_print(f"INFO: [TemplateService] الإجمالي النهائي: {grand_total}")
            safe_print("INFO: [TemplateService] ==============================")

            # إذا لا يزال صفر، استخدم مجموع الدفعات
            if grand_total == 0 and payments:
                total_paid_temp = sum(float(p.get("amount", 0)) for p in payments)
                if total_paid_temp > 0:
                    grand_total = total_paid_temp
                    safe_print(
                        f"WARNING: [TemplateService] المشروع بدون إجمالي، تم استخدام مجموع الدفعات: {grand_total}"
                    )

            # تحضير بنود الخدمات
            items = []
            if hasattr(project, "items") and project.items and len(project.items) > 0:
                for item in project.items:
                    # التعامل مع item سواء كان object أو dict
                    if isinstance(item, dict):
                        items.append(
                            {
                                "name": item.get("description", "خدمة"),
                                "qty": f"{item.get('quantity', 1):.1f}",
                                "price": f"{item.get('unit_price', 0):,.0f}",
                                "discount": f"{item.get('discount_rate', 0):.1f}",
                                "total": f"{item.get('total', 0):,.0f}",
                            }
                        )
                    else:
                        items.append(
                            {
                                "name": getattr(item, "description", "خدمة"),
                                "qty": f"{getattr(item, 'quantity', 1):.1f}",
                                "price": f"{getattr(item, 'unit_price', 0):,.0f}",
                                "discount": f"{getattr(item, 'discount_rate', 0):.1f}",
                                "total": f"{getattr(item, 'total', 0):,.0f}",
                            }
                        )
            else:
                # إذا لم تكن هناك بنود، أنشئ بند واحد للمشروع
                project_name = (
                    getattr(project, "name", None) or project.get("name", "مشروع")
                    if isinstance(project, dict)
                    else "مشروع"
                )
                items.append(
                    {
                        "name": project_name,
                        "qty": "1.0",
                        "price": f"{grand_total:,.0f}",
                        "discount": "0.0",
                        "total": f"{grand_total:,.0f}",
                    }
                )

            # ⚡ إنتاج رقم الفاتورة الثابت (يُحفظ في قاعدة البيانات)
            try:
                # أولاً: تحقق من وجود رقم فاتورة محفوظ مسبقاً
                existing_invoice_number = getattr(project, "invoice_number", None)
                if isinstance(project, dict):
                    existing_invoice_number = project.get("invoice_number")

                if existing_invoice_number:
                    # استخدم الرقم المحفوظ
                    invoice_id = existing_invoice_number
                    safe_print(
                        f"INFO: [TemplateService] استخدام رقم الفاتورة المحفوظ: {invoice_id}"
                    )
                else:
                    # ولّد رقم جديد وحاول حفظه
                    local_id = getattr(project, "id", None)
                    if isinstance(project, dict):
                        local_id = project.get("id")

                    if local_id and local_id > 0:
                        # الصيغة: 97161 + local_id (يبدأ من SW-97162)
                        invoice_id = f"SW-{97161 + int(local_id)}"

                        # حاول حفظ رقم الفاتورة في قاعدة البيانات
                        try:
                            if self.repo is not None:
                                cursor = self.repo.get_cursor()
                                try:
                                    cursor.execute(
                                        "UPDATE projects SET invoice_number = ? WHERE id = ?",
                                        (invoice_id, local_id),
                                    )
                                    self.repo.sqlite_conn.commit()
                                    safe_print(
                                        f"✅ [TemplateService] تم حفظ رقم الفاتورة {invoice_id} للمشروع {local_id}"
                                    )
                                finally:
                                    cursor.close()
                        except Exception as save_error:
                            safe_print(
                                f"WARNING: [TemplateService] فشل حفظ رقم الفاتورة: {save_error}"
                            )
                    else:
                        # لا يوجد ID - استخدم رقم افتراضي
                        invoice_id = "SW-97162"
                        safe_print(
                            f"WARNING: [TemplateService] المشروع بدون ID، استخدام رقم افتراضي: {invoice_id}"
                        )
            except (AttributeError, KeyError, TypeError) as e:
                # في حالة الخطأ، استخدم رقم افتراضي
                invoice_id = "SW-97162"
                safe_print(f"ERROR: [TemplateService] خطأ في توليد رقم الفاتورة: {e}")

            # تاريخ الفاتورة = تاريخ بداية المشروع
            project_start_date = getattr(project, "start_date", None)
            if project_start_date:
                if hasattr(project_start_date, "strftime"):
                    today = project_start_date.strftime("%Y-%m-%d")
                elif isinstance(project_start_date, str):
                    today = project_start_date[:10]
                else:
                    today = str(project_start_date)[:10]
            else:
                today = datetime.now().strftime("%Y-%m-%d")

            # معالجة الدفعات
            payments_list = []
            total_paid = 0.0

            safe_print(
                f"INFO: [TemplateService] معالجة الدفعات - عدد الدفعات: {len(payments) if payments else 0}"
            )

            if payments:
                for payment in payments:
                    # معالجة التاريخ - يمكن أن يكون object أو dict
                    if isinstance(payment, dict):
                        payment_date = payment.get("date", "")
                        amount_value = payment.get("amount", 0)
                        method_value = payment.get("method", "نقدي")
                    else:
                        payment_date = getattr(payment, "date", "")
                        amount_value = getattr(payment, "amount", 0)
                        method_value = getattr(payment, "method", None) or "نقدي"

                    # تحويل التاريخ لنص
                    if hasattr(payment_date, "strftime"):
                        date_str = payment_date.strftime("%Y-%m-%d")
                    else:
                        date_str = str(payment_date)[:10] if payment_date else ""

                    # تحويل المبلغ لرقم بأمان
                    try:
                        amount = float(amount_value)
                    except (ValueError, TypeError):
                        amount = 0.0

                    total_paid += amount

                    # جلب اسم الحساب إذا كان متوفراً
                    account_name = method_value
                    if isinstance(payment, dict):
                        account_name = payment.get("account_name", "") or payment.get(
                            "method", "نقدي"
                        )

                    payment_entry = {
                        "date": date_str,
                        "amount": amount,  # ⚡ رقم مش string عشان القالب يقدر يعمل format
                        "method": method_value,
                        "account_name": account_name,
                    }
                    payments_list.append(payment_entry)
                    safe_print(f"  - دفعة: {payment_entry}")

            # حساب المتبقي - إصلاح المشكلة المحاسبية
            remaining = max(0, grand_total - total_paid)  # ⚡ لا يمكن أن يكون سالب

            safe_print(f"  - الإجمالي الكلي: {grand_total}")
            safe_print(f"  - المدفوع: {total_paid}")
            safe_print(f"  - المتبقي: {remaining}")

            # إضافة معلومات الشركة من الإعدادات

            # تحميل اللوجو تلقائياً من site logo.png - مع دعم PyInstaller
            logo_base64 = ""
            base_path = get_base_path()

            # جرب المسارات المختلفة للوجو
            logo_paths = [
                os.path.join(base_path, "_internal", "site logo.png"),
                os.path.join(base_path, "site logo.png"),
                "site logo.png",
            ]

            site_logo_path = None
            for lp in logo_paths:
                if os.path.exists(lp):
                    site_logo_path = lp
                    break

            if site_logo_path:
                try:
                    with open(site_logo_path, "rb") as f:
                        logo_data = f.read()
                        logo_base64 = (
                            f"data:image/png;base64,{base64.b64encode(logo_data).decode()}"
                        )
                    safe_print(
                        f"INFO: [TemplateService] تم تحميل اللوجو تلقائياً من: {site_logo_path}"
                    )
                except Exception as e:
                    safe_print(f"WARNING: [TemplateService] فشل تحميل اللوجو: {e}")

            company_data = {}
            if self.settings_service:
                company_data = {
                    "company_name": self.settings_service.get_setting("company_name")
                    or "SkyWave ERP",
                    "company_tagline": self.settings_service.get_setting("company_tagline")
                    or "نظام إدارة المشاريع الذكي",
                    "company_phone": self.settings_service.get_setting("company_phone")
                    or "01000000000",
                    "company_email": self.settings_service.get_setting("company_email")
                    or "info@skywave.com",
                    "company_website": self.settings_service.get_setting("company_website")
                    or "www.skywaveads.com",
                    "company_address": self.settings_service.get_setting("company_address")
                    or "القاهرة، مصر",
                    "logo_path": logo_base64 if logo_base64 else "logo.png",
                }
            else:
                company_data = {
                    "company_name": "SkyWave ERP",
                    "company_tagline": "نظام إدارة المشاريع الذكي",
                    "company_phone": "01000000000",
                    "company_email": "info@skywave.com",
                    "company_website": "www.skywaveads.com",
                    "company_address": "القاهرة، مصر",
                    "logo_path": logo_base64 if logo_base64 else "logo.png",
                }

            # إضافة معلومات المشروع
            project_name = getattr(project, "name", None) or (
                project.get("name", "مشروع") if isinstance(project, dict) else "مشروع"
            )
            project_data = {
                "project_name": project_name,
                "project_status": getattr(project, "status", None)
                or (project.get("status", "نشط") if isinstance(project, dict) else "نشط"),
                "project_duration": (
                    f"{getattr(project, 'duration_days', 0)} يوم"
                    if getattr(project, "duration_days", None)
                    else "غير محدد"
                ),
            }

            # ⚡ تحميل العلامة المائية - مع دعم PyInstaller
            watermark_base64 = ""
            watermark_paths = [
                os.path.join(base_path, "_internal", "logo.png"),
                os.path.join(base_path, "logo.png"),
                "logo.png",
            ]

            watermark_path = None
            for wp in watermark_paths:
                if os.path.exists(wp):
                    watermark_path = wp
                    break

            if watermark_path:
                try:
                    with open(watermark_path, "rb") as f:
                        watermark_data = f.read()
                        watermark_base64 = (
                            f"data:image/png;base64,{base64.b64encode(watermark_data).decode()}"
                        )
                    safe_print(
                        f"INFO: [TemplateService] تم تحميل العلامة المائية من: {watermark_path}"
                    )
                except Exception as e:
                    safe_print(f"WARNING: [TemplateService] فشل تحميل العلامة المائية: {e}")

            project_notes = getattr(project, "project_notes", None) or (
                project.get("project_notes", "") if isinstance(project, dict) else ""
            )

            payment_methods = []
            note_templates = []
            try:
                if self.settings_service:
                    payment_methods = self.settings_service.get_setting("payment_methods") or []
                    note_templates = (
                        self.settings_service.get_setting("project_note_templates") or []
                    )
            except Exception:
                payment_methods = []
                note_templates = []

            if not project_notes:
                for t in note_templates:
                    if isinstance(t, dict):
                        candidate = (t.get("content") or "").strip()
                        if candidate:
                            project_notes = candidate
                            break

            invoice_payment_methods = []
            for method in payment_methods:
                if not isinstance(method, dict):
                    continue
                if not method.get("active", True):
                    continue
                name = (method.get("name") or "").strip()
                description = (method.get("description") or "").strip()
                details = (method.get("details") or "").strip()
                if not (name or description or details):
                    continue
                invoice_payment_methods.append(
                    {
                        "name": name,
                        "description": description,
                        "details": details,
                    }
                )

            # ⚡ نسبة الخصم (تم حسابها مسبقاً في project_discount_rate)
            discount_rate = project_discount_rate

            client_logo_width_px = 120
            client_logo_max_height_px = 40
            client_logo_max_width_percent = 22
            try:
                if self.settings_service:
                    client_logo_width_px = int(
                        self.settings_service.get_setting("print_client_logo_width_px")
                        or client_logo_width_px
                    )
                    client_logo_max_height_px = int(
                        self.settings_service.get_setting("print_client_logo_max_height_px")
                        or client_logo_max_height_px
                    )
                    client_logo_max_width_percent = int(
                        self.settings_service.get_setting("print_client_logo_max_width_percent")
                        or client_logo_max_width_percent
                    )
            except Exception:
                pass

            effective_max_w_px = max(1, int(client_logo_width_px))
            try:
                effective_max_w_px = min(
                    effective_max_w_px,
                    max(1, int(800 * (int(client_logo_max_width_percent) / 100.0))),
                )
            except Exception:
                pass

            client_logo_path = print_logo_png_data_url(
                client_info.get("logo_data"),
                client_info.get("logo_path"),
                max_width_px=effective_max_w_px * 4,
                max_height_px=int(client_logo_max_height_px) * 4,
            )
            circle_px = max(20, min(200, int(client_logo_max_height_px or 40)))
            circle_px = int(round(circle_px / 4.0) * 4)
            client_logo_circle_px = circle_px
            client_logo_circle_class = f"client-logo-s{circle_px}"

            return {
                # معلومات الفاتورة
                "invoice_id": invoice_id,
                "invoice_number": invoice_id,  # إضافة للتوافق مع القالب
                "invoice_date": today,
                "date": today,
                "due_date": (
                    project.end_date.strftime("%Y-%m-%d")
                    if hasattr(project, "end_date") and project.end_date
                    else "غير محدد"
                ),
                # معلومات العميل
                "client_name": client_info.get("name", "") or "غير محدد",
                "client_phone": client_info.get("phone", "") or "",
                "client_email": client_info.get("email", "") or "",
                "client_address": client_info.get("address", "") or "",
                "client_logo_path": client_logo_path,
                "client_logo_width_px": client_logo_width_px,
                "client_logo_max_height_px": client_logo_max_height_px,
                "client_logo_max_width_percent": client_logo_max_width_percent,
                "client_logo_circle_px": client_logo_circle_px,
                "client_logo_circle_class": client_logo_circle_class,
                # البنود
                "items": items,
                # الحسابات
                # ⚡ subtotal = الإجمالي الكلي (قبل الخصم) = gross_total
                # ⚡ grand_total = الإجمالي الفرعي (بعد الخصم)
                "subtotal": f"{gross_total:,.2f}",
                "discount_rate": f"{discount_rate:.0f}",
                "discount_amount": f"{discount_amount:,.2f}" if discount_amount > 0 else "0",
                "discount_amount_raw": discount_amount,  # للمقارنة في القالب
                "tax_amount": f"{tax_amount:,.2f}" if tax_amount > 0 else "0",
                "grand_total": f"{grand_total:,.2f}",
                "total_amount": f"{grand_total:,.2f}",  # للتوافق
                # الدفعات
                "payments": payments_list,
                "total_paid": f"{total_paid:,.0f}",
                "amount_paid": f"{total_paid:,.0f}",  # للتوافق
                "remaining_amount": f"{remaining:,.0f}",
                # معلومات الشركة
                **company_data,
                # معلومات المشروع
                **project_data,
                # ⚡ ملاحظات المشروع
                "project_notes": project_notes,
                "payment_methods": invoice_payment_methods,
                # ⚡ العلامة المائية
                "watermark_path": watermark_base64,
                # متغيرات للتحقق
                "debug_grand_total": grand_total,
                "debug_total_paid": total_paid,
                "debug_remaining": remaining,
            }

        except Exception as e:
            safe_print(f"ERROR: خطأ في تحضير بيانات القالب: {e}")
            return {}

    def preview_template(
        self,
        project: schemas.Project,
        client_info: dict[str, str],
        template_id: int | None = None,
        payments: list[dict[str, Any]] | None = None,
        use_pdf: bool = True,  # ⚡ PDF افتراضي
    ) -> bool:
        """معاينة القالب - توليد PDF سريع وفتحه"""
        try:

            # تحديد مجلد الصادرات
            if getattr(sys, "frozen", False):
                install_path = Path(sys.executable).parent
            else:
                install_path = Path.cwd()

            exports_dir = install_path / "exports"
            exports_dir.mkdir(parents=True, exist_ok=True)

            # توليد اسم الملف
            company_name = client_info.get("company_name", "")
            client_name = client_info.get("name", "")
            project_name = (
                getattr(project, "name", "project")
                if not isinstance(project, dict)
                else project.get("name", "project")
            )

            display_name = company_name if company_name else client_name
            display_name = self._sanitize_filename(display_name) if display_name else "client"
            project_name_safe = self._sanitize_filename(project_name) if project_name else "project"

            filename = f"{display_name} - {project_name_safe}"

            # توليد HTML
            html_content = self.generate_invoice_html(project, client_info, template_id, payments)

            if use_pdf:
                # ⚡ توليد PDF سريع
                pdf_path = os.path.join(str(exports_dir), f"{filename}.pdf")

                # حذف الملف القديم
                if os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                    except Exception:
                        pass

                pdf_path = self._generate_pdf_fast(html_content, str(exports_dir), filename)

                if pdf_path and os.path.exists(pdf_path):
                    self._open_file(pdf_path)
                    safe_print(f"✅ [TemplateService] تم إنشاء PDF: {pdf_path}")
                    return True
                else:
                    # Fallback: فتح HTML
                    safe_print("WARNING: [TemplateService] فشل PDF، جاري فتح HTML...")
                    html_path = os.path.join(str(exports_dir), f"{filename}.html")
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    self._open_file(html_path)
                    return True
            else:
                # فتح HTML مباشرة
                html_path = os.path.join(str(exports_dir), f"{filename}.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                self._open_file(html_path)
                safe_print(f"✅ [TemplateService] تم فتح HTML: {html_path}")
                return True

        except Exception as e:
            safe_print(f"ERROR: خطأ في معاينة القالب: {e}")

            traceback.print_exc()
            return False

    def _generate_pdf_fast(self, html_content: str, exports_dir: str, filename: str) -> str | None:
        """⚡ توليد PDF سريع - يجرب عدة طرق"""
        pdf_path = os.path.join(exports_dir, f"{filename}.pdf")

        # ⚡ محاولة 1: WeasyPrint (الأسرع)
        wp = _try_get_weasyprint()
        if wp:
            css_renderer, html_renderer = wp
            try:
                safe_print("INFO: [TemplateService] ⚡ استخدام WeasyPrint...")
                html_renderer(string=html_content, base_url=self.templates_dir).write_pdf(
                    pdf_path,
                    stylesheets=[css_renderer(string="@page { size: A4; margin: 8.5mm 5mm; }")],
                )
                if os.path.exists(pdf_path):
                    safe_print("✅ [TemplateService] تم إنشاء PDF بـ WeasyPrint")
                    return pdf_path
            except Exception as e:
                safe_print(f"WARNING: [TemplateService] فشل WeasyPrint: {e}")
        else:
            if WEASYPRINT_IMPORT_ERROR:
                safe_print(
                    f"INFO: [TemplateService] WeasyPrint غير متوفر: {WEASYPRINT_IMPORT_ERROR}"
                )

        # ⚡ محاولة 2: pdfkit (wkhtmltopdf)
        if pdfkit_available:
            wkhtmltopdf_path = shutil.which("wkhtmltopdf")
            if not wkhtmltopdf_path:
                safe_print("INFO: [TemplateService] wkhtmltopdf غير متوفر - تخطي pdfkit")
            else:
                try:
                    safe_print("INFO: [TemplateService] ⚡ استخدام pdfkit...")
                    options = {
                        "page-size": "A4",
                        "margin-top": "8.5mm",
                        "margin-right": "5mm",
                        "margin-bottom": "8.5mm",
                        "margin-left": "5mm",
                        "encoding": "UTF-8",
                        "no-outline": None,
                        "quiet": "",
                    }
                    pdfkit.from_string(html_content, pdf_path, options=options)
                    if os.path.exists(pdf_path):
                        safe_print("✅ [TemplateService] تم إنشاء PDF بـ pdfkit")
                        return pdf_path
                except Exception as e:
                    safe_print(f"WARNING: [TemplateService] فشل pdfkit: {e}")
        else:
            safe_print("INFO: [TemplateService] pdfkit غير متوفر")

        try:
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            ]
            browser_path = None
            for path in chrome_paths:
                if os.path.exists(path):
                    browser_path = path
                    break

            if browser_path:
                html_path = os.path.join(exports_dir, f"{filename}.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                abs_html_path = os.path.abspath(html_path)
                abs_pdf_path = os.path.abspath(pdf_path)
                cmd = [
                    browser_path,
                    "--headless",
                    "--disable-gpu",
                    "--print-to-pdf=" + abs_pdf_path,
                    "file:///" + abs_html_path.replace("\\", "/"),
                ]
                subprocess.run(cmd, capture_output=True, timeout=30, check=False)
                if os.path.exists(pdf_path):
                    safe_print("✅ [TemplateService] تم إنشاء PDF بالمتصفح")
                    try:
                        os.remove(html_path)
                    except Exception:
                        pass
                    return pdf_path
        except Exception as e:
            safe_print(f"WARNING: [TemplateService] فشل المتصفح: {e}")

        if qwebengine_available:
            try:
                return self._generate_pdf_with_qt(html_content, pdf_path)
            except Exception as e:
                safe_print(f"WARNING: [TemplateService] فشل PyQt6: {e}")
        else:
            safe_print("INFO: [TemplateService] PyQt6 WebEngine غير متوفر")

        return None

    def _sanitize_filename(self, name: str) -> str:
        """تنظيف اسم الملف من الأحرف غير المسموحة"""
        safe_name = "".join(c for c in str(name) if c.isalnum() or c in (" ", "_", "-")).strip()
        safe_name = safe_name.replace(" ", "_")
        return safe_name[:50] if safe_name else "invoice"

    def _generate_pdf(self, html_content: str, exports_dir: str, filename: str) -> str | None:
        """توليد PDF من HTML"""
        pdf_path = os.path.join(exports_dir, f"{filename}.pdf")

        # محاولة 1: استخدام WeasyPrint
        wp = _try_get_weasyprint()
        if wp:
            css_renderer, html_renderer = wp
            try:
                safe_print("INFO: [TemplateService] استخدام WeasyPrint لتوليد PDF...")
                html_renderer(string=html_content, base_url=self.templates_dir).write_pdf(
                    pdf_path,
                    stylesheets=[css_renderer(string="@page { size: A4; margin: 0; }")],
                )
                safe_print("✅ [TemplateService] تم إنشاء PDF باستخدام WeasyPrint")
                return pdf_path
            except Exception as e:
                safe_print(f"WARNING: [TemplateService] فشل WeasyPrint: {e}")
        else:
            safe_print("WARNING: [TemplateService] WeasyPrint غير متوفر، جاري استخدام PyQt6...")

        # محاولة 2: استخدام PyQt6
        try:
            safe_print("INFO: [TemplateService] استخدام PyQt6 لتوليد PDF...")
            return self._generate_pdf_with_qt(html_content, pdf_path)
        except Exception as e:
            safe_print(f"WARNING: [TemplateService] فشل PyQt6: {e}")

        # محاولة 3: حفظ HTML كـ fallback
        html_path = os.path.join(exports_dir, f"{filename}.html")
        try:
            safe_print("INFO: [TemplateService] حفظ HTML كـ fallback...")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            safe_print(f"⚠️ [TemplateService] تم حفظ HTML: {html_path}")
            return html_path
        except Exception as e:
            safe_print(f"ERROR: [TemplateService] فشل حفظ HTML: {e}")
            return None

    def _generate_pdf_with_qt(self, html_content: str, pdf_path: str) -> str | None:
        """توليد PDF باستخدام PyQt6 - محسّن للسرعة"""
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView

            app = QApplication.instance()
            if not app:
                app = QApplication([])

            web_view = QWebEngineView()
            pdf_done = [True]
            loop = QEventLoop()

            def on_pdf_saved(file_path):
                """عند اكتمال حفظ PDF"""
                pdf_done[0] = True
                loop.quit()

            def on_load_finished(ok):
                if ok:
                    # ⚡ ربط إشارة اكتمال PDF
                    web_view.page().pdfPrintingFinished.connect(on_pdf_saved)
                    web_view.page().printToPdf(pdf_path)
                else:
                    safe_print("ERROR: [TemplateService] فشل تحميل HTML")
                    loop.quit()

            web_view.loadFinished.connect(on_load_finished)
            base_dir = os.path.abspath(self.templates_dir)
            web_view.setHtml(html_content, QUrl.fromLocalFile(base_dir + "/"))

            # ⚡ انتظار أقصى 5 ثواني (بدلاً من 3 ثواني ثابتة)
            QTimer.singleShot(5000, loop.quit)
            loop.exec()

            # تنظيف
            web_view.deleteLater()

            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                safe_print("✅ [TemplateService] تم إنشاء PDF باستخدام PyQt6")
                return pdf_path

            return None
        except ImportError as e:
            safe_print(f"WARNING: [TemplateService] PyQt6 WebEngine غير متوفر: {e}")
            return None
        except Exception as e:
            safe_print(f"ERROR: [TemplateService] خطأ في PyQt6: {e}")
            return None

    def _open_file(self, file_path: str) -> bool:
        """فتح الملف في البرنامج الافتراضي"""

        try:
            if sys.platform == "win32":
                if getattr(sys, "frozen", False):
                    subprocess.run(["explorer", "/select,", file_path], check=False)
                else:
                    os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", file_path], check=False)
            else:
                subprocess.run(["xdg-open", file_path], check=False)
            return True
        except Exception as e:
            safe_print(f"WARNING: [TemplateService] فشل فتح الملف: {e}")
            return False

    def save_invoice_html(
        self,
        project: schemas.Project,
        client_info: dict[str, str],
        output_path: str,
        template_id: int | None = None,
        payments: list[dict[str, Any]] | None = None,
    ) -> bool:
        """حفظ فاتورة HTML في ملف"""
        try:
            # إنتاج HTML
            html_content = self.generate_invoice_html(project, client_info, template_id, payments)

            # حفظ في الملف
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            safe_print(f"INFO: تم حفظ فاتورة HTML: {output_path}")
            return True

        except Exception as e:
            safe_print(f"ERROR: خطأ في حفظ فاتورة HTML: {e}")
            return False

    def add_template(self, name: str, description: str, template_content: str) -> bool:
        """إضافة قالب جديد"""
        cursor = None
        try:
            # حفظ ملف القالب
            template_filename = self._sanitize_template_filename(name)
            template_path = self._safe_template_path(template_filename)

            with open(template_path, "w", encoding="utf-8") as f:
                f.write(template_content)

            # إضافة إلى قاعدة البيانات
            cursor = self.repo.get_cursor()
            insert_sql = """
            INSERT INTO invoice_templates (name, description, template_file)
            VALUES (?, ?, ?)
            """

            cursor.execute(insert_sql, (name, description, template_filename))
            self.repo.sqlite_conn.commit()

            safe_print(f"INFO: تم إضافة قالب جديد: {name}")
            return True

        except Exception as e:
            safe_print(f"ERROR: خطأ في إضافة القالب: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def update_template(
        self, template_id: int, name: str, description: str, template_content: str
    ) -> bool:
        """تحديث قالب موجود"""
        cursor = None
        try:
            # جلب معلومات القالب الحالي
            template = self.get_template_by_id(template_id)
            if not template:
                safe_print(f"ERROR: القالب {template_id} غير موجود")
                return False

            # تحديث ملف القالب
            old_filename = template["template_file"]
            new_filename = self._sanitize_template_filename(name)

            # حفظ المحتوى الجديد
            template_path = self._safe_template_path(new_filename)
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(template_content)

            # حذف الملف القديم إذا كان الاسم مختلف
            if old_filename != new_filename:
                old_path = self._safe_template_path(old_filename)
                if os.path.exists(old_path):
                    os.remove(old_path)

            # تحديث قاعدة البيانات
            cursor = self.repo.get_cursor()
            update_sql = """
            UPDATE invoice_templates
            SET name = ?, description = ?, template_file = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """

            cursor.execute(update_sql, (name, description, new_filename, template_id))
            self.repo.sqlite_conn.commit()

            safe_print(f"INFO: تم تحديث القالب: {name}")
            return True

        except Exception as e:
            safe_print(f"ERROR: خطأ في تحديث القالب: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def set_default_template(self, template_id: int) -> bool:
        """تعيين قالب كافتراضي"""
        cursor = None
        try:
            cursor = self.repo.get_cursor()
            # إزالة الافتراضي من جميع القوالب
            update_sql = "UPDATE invoice_templates SET is_default = 0"
            cursor.execute(update_sql)

            # تعيين القالب الجديد كافتراضي
            update_sql = "UPDATE invoice_templates SET is_default = 1 WHERE id = ?"
            cursor.execute(update_sql, (template_id,))

            self.repo.sqlite_conn.commit()

            safe_print(f"INFO: تم تعيين القالب {template_id} كافتراضي")
            return True

        except Exception as e:
            safe_print(f"ERROR: خطأ في تعيين القالب الافتراضي: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def delete_template(self, template_id: int) -> bool:
        """حذف قالب"""
        cursor = None
        try:
            # جلب معلومات القالب
            template_info = self.get_template_by_id(template_id)
            if not template_info:
                return False

            # منع حذف القالب الافتراضي إذا كان الوحيد
            templates = self.get_all_templates()
            if template_info["is_default"] and len(templates) == 1:
                safe_print("ERROR: لا يمكن حذف القالب الافتراضي الوحيد")
                return False

            # حذف ملف القالب
            template_path = self._safe_template_path(template_info["template_file"])
            if os.path.exists(template_path):
                os.remove(template_path)

            # حذف من قاعدة البيانات
            cursor = self.repo.get_cursor()
            delete_sql = "DELETE FROM invoice_templates WHERE id = ?"
            cursor.execute(delete_sql, (template_id,))
            self.repo.sqlite_conn.commit()

            # إذا كان القالب المحذوف افتراضياً، تعيين آخر كافتراضي
            if template_info["is_default"]:
                remaining_templates = self.get_all_templates()
                if remaining_templates:
                    self.set_default_template(remaining_templates[0]["id"])

            safe_print(f"INFO: تم حذف القالب: {template_info['name']}")
            return True

        except Exception as e:
            safe_print(f"ERROR: خطأ في حذف القالب: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
