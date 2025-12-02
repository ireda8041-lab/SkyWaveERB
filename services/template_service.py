# الملف: services/template_service.py
"""
خدمة قوالب الفواتير - إدارة وإنتاج قوالب HTML للفواتير
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from jinja2 import Environment, FileSystemLoader, Template
import webbrowser
import tempfile

from core.base_service import BaseService
from core import schemas


class TemplateService(BaseService):
    """خدمة إدارة قوالب الفواتير"""
    
    @property
    def entity_name(self) -> str:
        return "invoice_templates"
    
    def __init__(self, repository, settings_service=None):
        super().__init__(repository)
        self.settings_service = settings_service
        
        # إعداد مجلد القوالب - المسار الصحيح
        self.templates_dir = os.path.join("assets", "templates", "invoices")
        if not os.path.exists(self.templates_dir):
            # إنشاء المجلد إذا لم يكن موجوداً
            os.makedirs(self.templates_dir, exist_ok=True)
        
        # إعداد Jinja2
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True
        )
        
        print(f"INFO: [TemplateService] Templates directory: {self.templates_dir}")
        
        # إنشاء جدول القوالب
        self._create_templates_table()
    
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
            self.repo.sqlite_cursor.execute(create_table_sql)
            self.repo.sqlite_conn.commit()
            
            # إضافة القالب الافتراضي إذا لم يكن موجوداً
            self._add_default_template()
            
        except Exception as e:
            print(f"ERROR: خطأ في إنشاء جدول القوالب: {e}")
    
    def _add_default_template(self):
        """إضافة القالب الافتراضي"""
        try:
            # التحقق من وجود أي قالب افتراضي
            check_sql = "SELECT COUNT(*) FROM invoice_templates WHERE is_default = 1"
            self.repo.sqlite_cursor.execute(check_sql)
            count = self.repo.sqlite_cursor.fetchone()[0]
            
            if count == 0:
                # التحقق من وجود القالب في المجلد
                template_file = "skywave_ads_invoice_template.html"
                template_path = os.path.join(self.templates_dir, template_file)
                
                if not os.path.exists(template_path):
                    # جرب القوالب الأخرى
                    for alt_template in ["skywave_ads_invoice_template.html"]:
                        alt_path = os.path.join(self.templates_dir, alt_template)
                        if os.path.exists(alt_path):
                            template_file = alt_template
                            break
                
                insert_sql = """
                INSERT INTO invoice_templates (name, description, template_file, is_default)
                VALUES (?, ?, ?, ?)
                """
                self.repo.sqlite_cursor.execute(insert_sql, (
                    "Sky Wave Professional",
                    "القالب الاحترافي لفواتير Sky Wave",
                    template_file,
                    1
                ))
                self.repo.sqlite_conn.commit()
                print(f"INFO: تم إضافة القالب الافتراضي: {template_file}")
        
        except Exception as e:
            print(f"ERROR: خطأ في إضافة القالب الافتراضي: {e}")
    
    def get_all_templates(self) -> List[Dict[str, Any]]:
        """جلب جميع القوالب"""
        try:
            select_sql = """
            SELECT id, name, description, template_file, is_default, created_at
            FROM invoice_templates
            ORDER BY is_default DESC, name ASC
            """
            
            self.repo.sqlite_cursor.execute(select_sql)
            rows = self.repo.sqlite_cursor.fetchall()
            
            templates = []
            for row in rows:
                templates.append({
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'template_file': row[3],
                    'is_default': bool(row[4]),
                    'created_at': row[5]
                })
            
            return templates
        
        except Exception as e:
            print(f"ERROR: خطأ في جلب القوالب: {e}")
            return []
    
    def get_template_by_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        """جلب قالب بالمعرف"""
        try:
            select_sql = """
            SELECT id, name, description, template_file, is_default, created_at
            FROM invoice_templates
            WHERE id = ?
            """
            
            self.repo.sqlite_cursor.execute(select_sql, (template_id,))
            row = self.repo.sqlite_cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'template_file': row[3],
                    'is_default': bool(row[4]),
                    'created_at': row[5]
                }
            
            return None
        
        except Exception as e:
            print(f"ERROR: خطأ في جلب القالب: {e}")
            return None
    
    def get_default_template(self) -> Optional[Dict[str, Any]]:
        """جلب القالب الافتراضي"""
        try:
            select_sql = """
            SELECT id, name, description, template_file, is_default, created_at
            FROM invoice_templates
            WHERE is_default = 1
            LIMIT 1
            """
            
            self.repo.sqlite_cursor.execute(select_sql)
            row = self.repo.sqlite_cursor.fetchone()
            
            if row:
                template_file = row[3]
                # التحقق من وجود الملف فعلياً
                template_path = os.path.join(self.templates_dir, template_file)
                if not os.path.exists(template_path):
                    print(f"WARNING: [TemplateService] Template file not found: {template_file}")
                    # البحث عن قالب بديل
                    for alt_template in ["skywave_ads_invoice_template.html"]:
                        alt_path = os.path.join(self.templates_dir, alt_template)
                        if os.path.exists(alt_path):
                            print(f"INFO: [TemplateService] Using alternative template: {alt_template}")
                            template_file = alt_template
                            # تحديث قاعدة البيانات
                            update_sql = "UPDATE invoice_templates SET template_file = ? WHERE id = ?"
                            self.repo.sqlite_cursor.execute(update_sql, (template_file, row[0]))
                            self.repo.sqlite_conn.commit()
                            break
                
                return {
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'template_file': template_file,
                    'is_default': bool(row[4]),
                    'created_at': row[5]
                }
            
            # إذا لم يوجد قالب افتراضي، إرجاع الأول
            templates = self.get_all_templates()
            return templates[0] if templates else None
        
        except Exception as e:
            print(f"ERROR: خطأ في جلب القالب الافتراضي: {e}")
            return None
    
    def generate_invoice_html(
        self, 
        project: schemas.Project, 
        client_info: Dict[str, str],
        template_id: Optional[int] = None,
        payments: List[Dict[str, Any]] = None
    ) -> str:
        """إنتاج HTML للفاتورة باستخدام القالب"""
        try:
            # جلب القالب
            if template_id:
                template_info = self.get_template_by_id(template_id)
            else:
                template_info = self.get_default_template()
            
            if not template_info:
                raise Exception("لم يتم العثور على قالب مناسب")
            
            # تحميل القالب
            template_file = template_info['template_file']
            print(f"INFO: [TemplateService] Loading template: {template_file}")
            template = self.jinja_env.get_template(template_file)
            print(f"INFO: [TemplateService] Template loaded successfully: {template_file}")
            
            # تحضير البيانات
            template_data = self._prepare_template_data(project, client_info, payments)
            
            # إنتاج HTML
            print(f"INFO: [TemplateService] Rendering template with data keys: {list(template_data.keys())}")
            html_content = template.render(**template_data)
            print(f"INFO: [TemplateService] Template rendered successfully, HTML size: {len(html_content)} chars")
            
            # التحقق من وجود العلامة المميزة
            if "SKYWAVE_CUSTOM_TEMPLATE_2025" in html_content:
                print("✅ [TemplateService] Custom template is being used correctly!")
            else:
                print("❌ [TemplateService] WARNING: Custom template marker not found!")
            
            return html_content
        
        except Exception as e:
            print(f"ERROR: خطأ في إنتاج HTML للفاتورة: {e}")
            import traceback
            traceback.print_exc()
            return f"<html><body><h1>خطأ في إنتاج الفاتورة: {e}</h1></body></html>"
    
    def _prepare_template_data(self, project: schemas.Project, client_info: Dict[str, str], payments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """تحضير بيانات القالب"""
        try:
            # التأكد من أن project هو كائن صحيح وليس dict
            if isinstance(project, dict):
                print("WARNING: [TemplateService] project is a dict, converting to object-like access")
                # تحويل dict إلى object للوصول للخصائص
                class DictToObj:
                    def __init__(self, d):
                        for key, value in d.items():
                            setattr(self, key, value)
                project = DictToObj(project)
            
            # التحقق من وجود الخصائص الأساسية وإضافتها إذا لزم الأمر
            if not hasattr(project, 'name'):
                print("WARNING: [TemplateService] Project object missing 'name' attribute, adding default")
                # إضافة قيمة افتراضية بدلاً من رفع خطأ
                setattr(project, 'name', 'مشروع')
            
            # التحقق من الخصائص الأخرى المطلوبة
            if not hasattr(project, 'id'):
                setattr(project, 'id', None)
            if not hasattr(project, 'items'):
                setattr(project, 'items', [])
            if not hasattr(project, 'total_amount'):
                setattr(project, 'total_amount', 0)
            if not hasattr(project, 'discount_rate'):
                setattr(project, 'discount_rate', 0)
            if not hasattr(project, 'tax_rate'):
                setattr(project, 'tax_rate', 0)
            
            # حساب الإجماليات - استخدم total_amount من المشروع مباشرة
            # لأن المشروع يحتوي على الحسابات الصحيحة بالفعل
            grand_total = float(getattr(project, 'total_amount', 0) or 0)
            subtotal = float(getattr(project, 'subtotal', 0) or 0)
            discount_amount = float(getattr(project, 'discount_amount', 0) or 0)
            tax_amount = float(getattr(project, 'tax_amount', 0) or 0)
            
            # إذا كان الإجمالي صفر، حاول الحساب من البنود
            if grand_total == 0 and hasattr(project, 'items') and project.items and len(project.items) > 0:
                items_subtotal = sum(item.total for item in project.items)
                items_discount = items_subtotal * (project.discount_rate / 100)
                items_taxable = items_subtotal - items_discount
                items_tax = items_taxable * (project.tax_rate / 100)
                grand_total = items_taxable + items_tax
                subtotal = items_subtotal
                discount_amount = items_discount
                tax_amount = items_tax
                print(f"INFO: [TemplateService] تم حساب الإجمالي من البنود: {grand_total}")
            
            # إذا لا يزال صفر، استخدم مجموع الدفعات
            if grand_total == 0 and payments:
                total_paid_temp = sum(float(p.get('amount', 0)) for p in payments)
                if total_paid_temp > 0:
                    grand_total = total_paid_temp
                    subtotal = grand_total
                    print(f"WARNING: [TemplateService] المشروع بدون إجمالي، تم استخدام مجموع الدفعات: {grand_total}")
            
            # تحضير بنود الخدمات
            items = []
            if hasattr(project, 'items') and project.items and len(project.items) > 0:
                for item in project.items:
                    # التعامل مع item سواء كان object أو dict
                    if isinstance(item, dict):
                        items.append({
                            'name': item.get('description', 'خدمة'),
                            'qty': f"{item.get('quantity', 1):.1f}",
                            'price': f"{item.get('unit_price', 0):,.0f}",
                            'discount': f"{item.get('discount_rate', 0):.1f}",
                            'total': f"{item.get('total', 0):,.0f}"
                        })
                    else:
                        items.append({
                            'name': getattr(item, 'description', 'خدمة'),
                            'qty': f"{getattr(item, 'quantity', 1):.1f}",
                            'price': f"{getattr(item, 'unit_price', 0):,.0f}",
                            'discount': f"{getattr(item, 'discount_rate', 0):.1f}",
                            'total': f"{getattr(item, 'total', 0):,.0f}"
                        })
            else:
                # إذا لم تكن هناك بنود، أنشئ بند واحد للمشروع
                project_name = getattr(project, 'name', None) or project.get('name', 'مشروع') if isinstance(project, dict) else 'مشروع'
                items.append({
                    'name': project_name,
                    'qty': "1.0",
                    'price': f"{grand_total:,.0f}",
                    'discount': "0.0",
                    'total': f"{grand_total:,.0f}"
                })
            
            # إنتاج رقم الفاتورة
            try:
                project_id = getattr(project, 'id', None) or (project.get('id') if isinstance(project, dict) else None)
                if project_id:
                    invoice_id = f"SW-{int(project_id):04d}"
                else:
                    invoice_id = f"SW-{datetime.now().strftime('%Y%m%d%H%M')}"
            except:
                invoice_id = f"SW-{datetime.now().strftime('%Y%m%d%H%M')}"
            
            # تاريخ اليوم
            today = datetime.now().strftime("%Y-%m-%d")
            
            # معالجة الدفعات
            payments_list = []
            total_paid = 0.0
            
            print(f"INFO: [TemplateService] معالجة الدفعات - عدد الدفعات: {len(payments) if payments else 0}")
            
            if payments:
                for payment in payments:
                    # معالجة التاريخ - يمكن أن يكون object أو dict
                    if isinstance(payment, dict):
                        payment_date = payment.get('date', '')
                        amount_value = payment.get('amount', 0)
                        method_value = payment.get('method', 'نقدي')
                    else:
                        payment_date = getattr(payment, 'date', '')
                        amount_value = getattr(payment, 'amount', 0)
                        method_value = getattr(payment, 'method', None) or 'نقدي'
                    
                    # تحويل التاريخ لنص
                    if hasattr(payment_date, 'strftime'):
                        date_str = payment_date.strftime('%Y-%m-%d')
                    else:
                        date_str = str(payment_date)[:10] if payment_date else ''
                    
                    # تحويل المبلغ لرقم بأمان
                    try:
                        amount = float(amount_value)
                    except (ValueError, TypeError):
                        amount = 0.0
                    
                    total_paid += amount
                    
                    # جلب اسم الحساب إذا كان متوفراً
                    account_name = method_value
                    if isinstance(payment, dict):
                        account_name = payment.get('account_name', '') or payment.get('method', 'نقدي')
                    
                    payment_entry = {
                        'date': date_str,
                        'amount': f"{amount:,.0f}",
                        'method': method_value,
                        'account_name': account_name
                    }
                    payments_list.append(payment_entry)
                    print(f"  - دفعة: {payment_entry}")
            
            # حساب المتبقي - إصلاح المشكلة المحاسبية
            remaining = grand_total - total_paid

            print(f"  - المتبقي: {remaining}")
            
            # إضافة معلومات الشركة من الإعدادات
            import base64
            
            # تحميل اللوجو تلقائياً من site logo.png
            logo_base64 = ""
            site_logo_path = "site logo.png"
            if os.path.exists(site_logo_path):
                try:
                    with open(site_logo_path, 'rb') as f:
                        logo_data = f.read()
                        logo_base64 = f"data:image/png;base64,{base64.b64encode(logo_data).decode()}"
                    print(f"INFO: [TemplateService] تم تحميل اللوجو تلقائياً من: {site_logo_path}")
                except Exception as e:
                    print(f"WARNING: [TemplateService] فشل تحميل اللوجو: {e}")
            
            company_data = {}
            if self.settings_service:
                company_data = {
                    'company_name': self.settings_service.get_setting("company_name") or "SkyWave ERP",
                    'company_tagline': self.settings_service.get_setting("company_tagline") or "نظام إدارة المشاريع الذكي",
                    'company_phone': self.settings_service.get_setting("company_phone") or "01000000000",
                    'company_email': self.settings_service.get_setting("company_email") or "info@skywave.com",
                    'company_website': self.settings_service.get_setting("company_website") or "www.skywaveads.com",
                    'company_address': self.settings_service.get_setting("company_address") or "القاهرة، مصر",
                    'logo_path': logo_base64 if logo_base64 else "logo.png",
                }
            else:
                company_data = {
                    'company_name': "SkyWave ERP",
                    'company_tagline': "نظام إدارة المشاريع الذكي",
                    'company_phone': "01000000000",
                    'company_email': "info@skywave.com",
                    'company_website': "www.skywaveads.com",
                    'company_address': "القاهرة، مصر",
                    'logo_path': logo_base64 if logo_base64 else "logo.png",
                }
            
            # إضافة معلومات المشروع
            project_name = getattr(project, 'name', None) or (project.get('name', 'مشروع') if isinstance(project, dict) else 'مشروع')
            project_data = {
                'project_name': project_name,
                'project_status': getattr(project, 'status', None) or (project.get('status', 'نشط') if isinstance(project, dict) else 'نشط'),
                'project_duration': f"{getattr(project, 'duration_days', 0)} يوم" if getattr(project, 'duration_days', None) else "غير محدد",
            }
            
            return {
                # معلومات الفاتورة
                'invoice_id': invoice_id,
                'invoice_number': invoice_id,  # إضافة للتوافق مع القالب
                'invoice_date': today,
                'date': today,
                'due_date': getattr(project, 'end_date', None).strftime("%Y-%m-%d") if hasattr(project, 'end_date') and project.end_date else "غير محدد",
                
                # معلومات العميل
                'client_name': client_info.get('name', '') or 'غير محدد',
                'client_phone': client_info.get('phone', '') or '',
                'client_email': client_info.get('email', '') or '',
                'client_address': client_info.get('address', '') or '',
                
                # البنود
                'items': items,
                
                # الحسابات
                'subtotal': f"{subtotal:,.0f}",
                'discount_amount': f"{discount_amount:,.0f}" if discount_amount > 0 else "0",
                'tax_amount': f"{tax_amount:,.0f}" if tax_amount > 0 else "0",
                'grand_total': f"{grand_total:,.0f}",
                'total_amount': f"{grand_total:,.0f}",  # للتوافق
                
                # الدفعات
                'payments': payments_list,
                'total_paid': f"{total_paid:,.0f}",
                'amount_paid': f"{total_paid:,.0f}",  # للتوافق
                'remaining_amount': f"{remaining:,.0f}",
                
                # معلومات الشركة
                **company_data,
                
                # معلومات المشروع
                **project_data,
                
                # متغيرات للتحقق
                'debug_grand_total': grand_total,
                'debug_total_paid': total_paid,
                'debug_remaining': remaining
            }
        
        except Exception as e:
            print(f"ERROR: خطأ في تحضير بيانات القالب: {e}")
            return {}
    
    def preview_template(
        self, 
        project: schemas.Project, 
        client_info: Dict[str, str],
        template_id: Optional[int] = None,
        payments: List[Dict[str, Any]] = None
    ) -> bool:
        """معاينة القالب في المتصفح"""
        try:
            # إنتاج HTML
            html_content = self.generate_invoice_html(project, client_info, template_id, payments)
            
            # حفظ في ملف مؤقت
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                temp_file = f.name
            
            # فتح في المتصفح
            webbrowser.open(f'file://{temp_file}')
            
            print(f"INFO: تم فتح معاينة القالب: {temp_file}")
            return True
        
        except Exception as e:
            print(f"ERROR: خطأ في معاينة القالب: {e}")
            return False
    
    def save_invoice_html(
        self, 
        project: schemas.Project, 
        client_info: Dict[str, str],
        output_path: str,
        template_id: Optional[int] = None,
        payments: List[Dict[str, Any]] = None
    ) -> bool:
        """حفظ فاتورة HTML في ملف"""
        try:
            # إنتاج HTML
            html_content = self.generate_invoice_html(project, client_info, template_id, payments)
            
            # حفظ في الملف
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"INFO: تم حفظ فاتورة HTML: {output_path}")
            return True
        
        except Exception as e:
            print(f"ERROR: خطأ في حفظ فاتورة HTML: {e}")
            return False
    
    def add_template(self, name: str, description: str, template_content: str) -> bool:
        """إضافة قالب جديد"""
        try:
            # حفظ ملف القالب
            template_filename = f"{name.replace(' ', '_').lower()}.html"
            template_path = os.path.join(self.templates_dir, template_filename)
            
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            
            # إضافة إلى قاعدة البيانات
            insert_sql = """
            INSERT INTO invoice_templates (name, description, template_file)
            VALUES (?, ?, ?)
            """
            
            self.repo.sqlite_cursor.execute(insert_sql, (name, description, template_filename))
            self.repo.sqlite_conn.commit()
            
            print(f"INFO: تم إضافة قالب جديد: {name}")
            return True
        
        except Exception as e:
            print(f"ERROR: خطأ في إضافة القالب: {e}")
            return False
    
    def update_template(self, template_id: int, name: str, description: str, template_content: str) -> bool:
        """تحديث قالب موجود"""
        try:
            # جلب معلومات القالب الحالي
            template = self.get_template_by_id(template_id)
            if not template:
                print(f"ERROR: القالب {template_id} غير موجود")
                return False
            
            # تحديث ملف القالب
            old_filename = template['template_file']
            new_filename = f"{name.replace(' ', '_').lower()}.html"
            
            # حفظ المحتوى الجديد
            template_path = os.path.join(self.templates_dir, new_filename)
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            
            # حذف الملف القديم إذا كان الاسم مختلف
            if old_filename != new_filename:
                old_path = os.path.join(self.templates_dir, old_filename)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            # تحديث قاعدة البيانات
            update_sql = """
            UPDATE invoice_templates 
            SET name = ?, description = ?, template_file = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """
            
            self.repo.sqlite_cursor.execute(update_sql, (name, description, new_filename, template_id))
            self.repo.sqlite_conn.commit()
            
            print(f"INFO: تم تحديث القالب: {name}")
            return True
        
        except Exception as e:
            print(f"ERROR: خطأ في تحديث القالب: {e}")
            return False
    
    def set_default_template(self, template_id: int) -> bool:
        """تعيين قالب كافتراضي"""
        try:
            # إزالة الافتراضي من جميع القوالب
            update_sql = "UPDATE invoice_templates SET is_default = 0"
            self.repo.sqlite_cursor.execute(update_sql)
            
            # تعيين القالب الجديد كافتراضي
            update_sql = "UPDATE invoice_templates SET is_default = 1 WHERE id = ?"
            self.repo.sqlite_cursor.execute(update_sql, (template_id,))
            
            self.repo.sqlite_conn.commit()
            
            print(f"INFO: تم تعيين القالب {template_id} كافتراضي")
            return True
        
        except Exception as e:
            print(f"ERROR: خطأ في تعيين القالب الافتراضي: {e}")
            return False
    
    def delete_template(self, template_id: int) -> bool:
        """حذف قالب"""
        try:
            # جلب معلومات القالب
            template_info = self.get_template_by_id(template_id)
            if not template_info:
                return False
            
            # منع حذف القالب الافتراضي إذا كان الوحيد
            templates = self.get_all_templates()
            if template_info['is_default'] and len(templates) == 1:
                print("ERROR: لا يمكن حذف القالب الافتراضي الوحيد")
                return False
            
            # حذف ملف القالب
            template_path = os.path.join(self.templates_dir, template_info['template_file'])
            if os.path.exists(template_path):
                os.remove(template_path)
            
            # حذف من قاعدة البيانات
            delete_sql = "DELETE FROM invoice_templates WHERE id = ?"
            self.repo.sqlite_cursor.execute(delete_sql, (template_id,))
            self.repo.sqlite_conn.commit()
            
            # إذا كان القالب المحذوف افتراضياً، تعيين آخر كافتراضي
            if template_info['is_default']:
                remaining_templates = self.get_all_templates()
                if remaining_templates:
                    self.set_default_template(remaining_templates[0]['id'])
            
            print(f"INFO: تم حذف القالب: {template_info['name']}")
            return True
        
        except Exception as e:
            print(f"ERROR: خطأ في حذف القالب: {e}")
            return False