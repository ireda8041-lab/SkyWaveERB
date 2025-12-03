# الملف: services/project_service.py

from core.repository import Repository
from core.event_bus import EventBus
from core import schemas
from core.signals import app_signals
from datetime import datetime, timedelta  # (جديد)
from typing import List, Optional, Dict

# (جديد: هنحتاج قسم المحاسبة عشان نجيب حسابات البنك)
from services.accounting_service import AccountingService

# خدمة طباعة المشاريع
try:
    from services.project_printing_service import ProjectPrintingService
    PRINTING_AVAILABLE = True
except ImportError:
    PRINTING_AVAILABLE = False
    print("WARNING: [ProjectService] Project printing service not available")


class ProjectService:
    """
    (معدل) قسم المشاريع (أصبح العقل المالي الوحيد).
    """

    def __init__(self, repository: Repository, event_bus: EventBus,
                 accounting_service: AccountingService, settings_service=None):  # (معدل)
        self.repo = repository
        self.bus = event_bus
        self.accounting_service = accounting_service  # (جديد)
        self.settings_service = settings_service

        # خدمة الطباعة
        if PRINTING_AVAILABLE:
            self.printing_service = ProjectPrintingService(settings_service)
        else:
            self.printing_service = None

        # (جديد) هنشترك في حدث تحويل عرض السعر هنا
        self.bus.subscribe('CONVERT_TO_INVOICE', self.handle_convert_to_project)

        print("INFO: قسم المشاريع (ProjectService) جاهز.")

    def get_all_projects(self) -> List[schemas.Project]:
        """ ⚡ جلب كل المشاريع (محسّن للسرعة) """
        try:
            # ⚡ استخدام SQLite مباشرة بدون MongoDB
            return self.repo.get_all_projects(exclude_status=schemas.ProjectStatus.ARCHIVED)
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل جلب المشاريع: {e}")
            return []

    def get_archived_projects(self) -> List[schemas.Project]:
        """ جلب كل المشاريع المؤرشفة """
        try:
            return self.repo.get_all_projects(status=schemas.ProjectStatus.ARCHIVED)
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل جلب المشاريع المؤرشفة: {e}")
            return []

    def create_project(self, project_data: dict, payment_data: dict) -> schemas.Project:
        """
        (معدلة) إنشاء مشروع جديد (مع الدفعة المقدمة)
        """
        print(f"INFO: [ProjectService] استلام طلب إنشاء مشروع: {project_data.get('name')}")
        try:
            # --- 1. حساب الإجماليات (زي ما هي) ---
            items_list = project_data.get("items", [])
            subtotal = 0
            processed_items = []
            for item in items_list:
                if isinstance(item, dict):
                    item_obj = schemas.ProjectItem(**item)
                else:
                    item_obj = item
                item_obj.total = item_obj.quantity * item_obj.unit_price
                subtotal += item_obj.total
                processed_items.append(item_obj)

            discount_rate = project_data.get('discount_rate', 0.0)
            discount_amount = subtotal * (discount_rate / 100)
            taxable_amount = subtotal - discount_amount
            tax_rate = project_data.get('tax_rate', 0.0)
            tax_amount = taxable_amount * (tax_rate / 100)
            total_amount = taxable_amount + tax_amount

            project_data['subtotal'] = subtotal
            project_data['discount_rate'] = discount_rate
            project_data['discount_amount'] = discount_amount
            project_data['tax_rate'] = tax_rate
            project_data['tax_amount'] = tax_amount
            project_data['total_amount'] = total_amount
            project_data['items'] = processed_items

            if 'start_date' not in project_data or not project_data['start_date']:
                project_data['start_date'] = datetime.now()

            if 'name' not in project_data or not project_data['name']:
                project_data['name'] = f"PROJ-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            new_project_schema = schemas.Project(**project_data)

            # --- 2. حفظ المشروع في الداتا بيز ---
            created_project = self.repo.create_project(new_project_schema)

            # --- 3. (الأهم) إبلاغ الروبوت المحاسبي (قيد المشروع) ---
            self.bus.publish('PROJECT_CREATED', {"project": created_project})

            # --- 4. (الجديد) تسجيل الدفعة المقدمة (لو موجودة) ---
            if payment_data and payment_data.get("amount", 0) > 0:
                print(f"INFO: [ProjectService] تسجيل دفعة مقدمة بمبلغ {payment_data['amount']}...")
                self.create_payment_for_project(
                    project=created_project,  # (بنبعت المشروع)
                    amount=payment_data["amount"],
                    date=payment_data["date"],
                    account_id=payment_data["account_id"]
                )

            # إرسال إشارة التحديث العامة
            app_signals.emit_data_changed('projects')
            
            print(f"SUCCESS: [ProjectService] تم إنشاء المشروع {created_project.name} بالكامل.")
            return created_project

        except Exception as e:
            print(f"ERROR: [ProjectService] فشل إنشاء المشروع: {e}")
            raise

    def update_project(self, project_name: str, new_data_dict: dict) -> Optional[schemas.Project]:
        print(f"INFO: [ProjectService] استلام طلب تعديل مشروع: {project_name}")
        try:
            # (نفس لوجيك الحسابات)
            items_list = new_data_dict.get("items", [])
            subtotal = 0
            processed_items = []
            for item in items_list:
                if isinstance(item, dict):
                    item_obj = schemas.ProjectItem(**item)
                else:
                    item_obj = item
                item_obj.total = item_obj.quantity * item_obj.unit_price
                subtotal += item_obj.total
                processed_items.append(item_obj)

            discount_rate = new_data_dict.get('discount_rate', 0.0)
            discount_amount = subtotal * (discount_rate / 100)
            taxable_amount = subtotal - discount_amount
            tax_rate = new_data_dict.get('tax_rate', 0.0)
            tax_amount = taxable_amount * (tax_rate / 100)
            total_amount = taxable_amount + tax_amount

            new_data_dict['subtotal'] = subtotal
            new_data_dict['discount_rate'] = discount_rate
            new_data_dict['discount_amount'] = discount_amount
            new_data_dict['tax_rate'] = tax_rate
            new_data_dict['tax_amount'] = tax_amount
            new_data_dict['total_amount'] = total_amount
            new_data_dict['items'] = processed_items

            old_project = self.repo.get_project_by_number(project_name)
            if not old_project:
                raise Exception("المشروع الأصلي غير موجود")
            updated_project_schema = old_project.model_copy(update=new_data_dict)

            saved_project = self.repo.update_project(project_name, updated_project_schema)

            # (الأهم) إبلاغ الروبوت المحاسبي بالتعديل
            self.bus.publish('PROJECT_EDITED', {"project": saved_project})

            print(f"SUCCESS: [ProjectService] تم تعديل المشروع {project_name}.")
            return saved_project
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل تعديل المشروع: {e}")
            raise

    # --- (الجديد) دوال الدفعات بقت جوه المشاريع ---
    def create_payment_for_project(self, project: schemas.Project, amount: float, date: datetime, account_id: str) -> Optional[schemas.Payment]:
        """
        (جديدة) إنشاء دفعة جديدة لمشروع.
        """
        print(f"INFO: [ProjectService] استلام طلب دفعة لـ {project.name} بمبلغ {amount}")

        try:
            payment_data = schemas.Payment(
                project_id=project.name,
                client_id=project.client_id,
                date=date,
                amount=amount,
                account_id=account_id,
            )
            created_payment = self.repo.create_payment(payment_data)

            # (نبلغ الروبوت المحاسبي)
            self.bus.publish('PAYMENT_RECEIVED', {
                "payment": created_payment,
                "project": project
            })

            print(f"SUCCESS: [ProjectService] تم تسجيل الدفعة.")
            return created_payment

        except Exception as e:
            print(f"ERROR: [ProjectService] فشل إنشاء الدفعة: {e}")
            raise

    # (الجديد: دالة تحويل عرض السعر بقت هنا)
    def handle_convert_to_project(self, quote_data_dict: dict):
        """
        (جديدة) يستقبل أمر تحويل عرض سعر وينشئ المشروع.
        """
        print("INFO: [ProjectService] استلام حدث 'CONVERT_TO_INVOICE' (تحويل لمشروع)...")
        try:
            # (بنستدعي الدالة اللي بتنشئ المشروع وبتشغل الروبوت)
            # (مفيش دفعة مقدمة في التحويل)
            self.create_project(quote_data_dict, payment_data={})
            print("INFO: [ProjectService] تم إنشاء المشروع من عرض السعر بنجاح.")
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل إنشاء المشروع من عرض السعر: {e}")

    def _auto_update_project_status(self, project_name: str):
        """⚡ تحديث حالة المشروع أوتوماتيك (محسّن للسرعة)"""
        try:
            project = self.repo.get_project_by_number(project_name)
            if not project:
                return
            
            # ⚡ استعلام SQL مباشر (أسرع)
            self.repo.sqlite_cursor.execute(
                "SELECT SUM(amount) FROM payments WHERE project_id = ?",
                (project_name,)
            )
            result = self.repo.sqlite_cursor.fetchone()
            total_paid = result[0] if result and result[0] else 0
            
            # تحديد الحالة الجديدة
            new_status = None
            if total_paid >= project.total_amount:
                new_status = schemas.ProjectStatus.COMPLETED
            elif total_paid > 0:
                new_status = schemas.ProjectStatus.ACTIVE
            else:
                new_status = schemas.ProjectStatus.PLANNING
            
            # تحديث الحالة إذا تغيرت
            if new_status and project.status != new_status:
                project.status = new_status
                self.repo.update_project(project_name, project)
                
        except Exception as e:
            print(f"WARNING: [ProjectService] فشل تحديث حالة المشروع: {e}")
    
    # --- دوال الربحية (معدلة عشان تستخدم الداتا الصح) ---
    def get_project_profitability(self, project_name: str) -> dict:
        """⚡ حساب ربحية المشروع (محسّن للسرعة)"""
        try:
            project = self.repo.get_project_by_number(project_name)
            if not project:
                return {
                    "total_revenue": 0,
                    "total_expenses": 0,
                    "net_profit": 0,
                    "total_paid": 0,
                    "balance_due": 0
                }

            total_revenue = project.total_amount

            # ⚡ استعلام SQL مباشر للمصروفات (أسرع)
            try:
                self.repo.sqlite_cursor.execute(
                    "SELECT SUM(amount) FROM expenses WHERE project_id = ?",
                    (project_name,)
                )
                result = self.repo.sqlite_cursor.fetchone()
                total_expenses = result[0] if result and result[0] else 0
            except:
                total_expenses = 0

            # ⚡ استعلام SQL مباشر للدفعات (أسرع)
            try:
                self.repo.sqlite_cursor.execute(
                    "SELECT SUM(amount) FROM payments WHERE project_id = ?",
                    (project_name,)
                )
                result = self.repo.sqlite_cursor.fetchone()
                total_paid = result[0] if result and result[0] else 0
            except:
                total_paid = 0

            net_profit = total_revenue - total_expenses
            balance_due = max(0, total_revenue - total_paid)
            
            # ⚡ تحديث حالة المشروع أوتوماتيك
            self._auto_update_project_status(project_name)

            return {
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "net_profit": net_profit,
                "total_paid": total_paid,
                "balance_due": balance_due
            }
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل حساب الربحية: {e}")
            return {
                "total_revenue": 0,
                "total_expenses": 0,
                "net_profit": 0,
                "total_paid": 0,
                "balance_due": 0
            }

    def get_payments_for_project(self, project_name: str) -> List[schemas.Payment]:  # (غيرنا الاسم)
        """ (جديدة) جلب كل الدفعات المرتبطة بمشروع """
        try:
            return self.repo.get_payments_for_project(project_name)  # (هنضيف دي للمخزن)
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل جلب دفعات المشروع: {e}")
            return []
    
    def get_project_by_id(self, project_id: str) -> Optional[schemas.Project]:
        """جلب مشروع بالـ ID أو الاسم"""
        try:
            # محاولة جلب المشروع بالاسم أولاً
            project = self.repo.get_project_by_number(project_id)
            if project:
                return project
            
            # إذا لم يتم العثور عليه، جرب البحث في كل المشاريع
            all_projects = self.repo.get_all_projects()
            for proj in all_projects:
                if proj.name == project_id or str(proj.id) == str(project_id):
                    return proj
            
            return None
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل جلب المشروع: {e}")
            return None
    
    def get_project_payments(self, project_id) -> List[schemas.Payment]:
        """جلب الدفعات بالـ ID"""
        try:
            # محاولة جلب المشروع أولاً
            project = self.get_project_by_id(project_id)
            if project:
                return self.get_payments_for_project(project.name)
            return []
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل جلب دفعات المشروع: {e}")
            return []

    def get_expenses_for_project(self, project_name: str) -> List[schemas.Expense]:
        try:
            return self.repo.get_expenses_for_project(project_name)
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل جلب مصروفات المشروع: {e}")
            return []

    # --- وظائف الطباعة الجديدة ---
    def print_project_invoice(self, project_name: str, background_image_path: str = None, auto_open: bool = True) -> Optional[str]:
        """طباعة فاتورة المشروع مع خلفية مخصصة"""
        if not self.printing_service:
            print("ERROR: [ProjectService] خدمة الطباعة غير متوفرة")
            return None
        
        try:
            # جلب بيانات المشروع
            project = self.repo.get_project_by_number(project_name)
            if not project:
                print(f"ERROR: [ProjectService] المشروع {project_name} غير موجود")
                return None
            
            # جلب بيانات العميل
            client = self.repo.get_client_by_id(project.client_id)
            client_info = {
                "name": client.name if client else "عميل غير محدد",
                "phone": client.phone if client else "",
                "address": client.address if client else ""
            }
            
            # جلب الدفعات
            payments = self.get_payments_for_project(project_name)
            payments_data = []
            for payment in payments:
                payments_data.append({
                    'date': payment.date,
                    'amount': payment.amount,
                    'account_id': payment.account_id
                })
            
            # طباعة الفاتورة
            return self.printing_service.print_project_invoice(
                project=project, 
                client_info=client_info, 
                payments=payments_data, 
                background_image_path=background_image_path, 
                auto_open=auto_open
            )
            
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل طباعة فاتورة المشروع: {e}")
            return None
    
    def generate_project_number(self, project_id: str) -> str:
        """توليد رقم المشروع بتنسيق SW-XXXX"""
        if self.printing_service:
            return self.printing_service.invoice_generator.generate_project_number(project_id)
        else:
            # نسخة مبسطة في حالة عدم توفر خدمة الطباعة
            try:
                numeric_part = ''.join(filter(str.isdigit, project_id))
                if len(numeric_part) >= 4:
                    return f"SW-{numeric_part[:4]}"
                else:
                    timestamp = datetime.now().strftime("%m%d")
                    return f"SW-{timestamp}"
            except:
                timestamp = datetime.now().strftime("%m%d")
                return f"SW-{timestamp}"
