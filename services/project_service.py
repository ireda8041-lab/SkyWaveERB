# الملف: services/project_service.py

import time
from datetime import datetime

from core import schemas
from core.event_bus import EventBus
from core.repository import Repository
from core.signals import app_signals
from services.accounting_service import AccountingService

# ⚡ استيراد محسّن السرعة
try:
    from core.speed_optimizer import LRUCache, cached  # noqa: F401
    CACHE_ENABLED = True
except ImportError:
    CACHE_ENABLED = False

# خدمة طباعة المشاريع
try:
    from services.project_printing_service import ProjectPrintingService
    PRINTING_AVAILABLE = True
except ImportError:
    PRINTING_AVAILABLE = False
    print("WARNING: [ProjectService] Project printing service not available")


class ProjectService:
    """
    🏢 قسم المشاريع Enterprise Level
    يدعم: التكويد الذكي، تحليل الربحية، مراكز التكلفة، العقود المتكررة
    """

    def __init__(self, repository: Repository, event_bus: EventBus,
                 accounting_service: AccountingService, settings_service=None):
        self.repo = repository
        self.bus = event_bus
        self.accounting_service = accounting_service
        self.settings_service = settings_service

        # ⚡ Cache للمشاريع
        self._cache_time: float = 0
        self._cached_projects: list[schemas.Project] | None = None
        self._cache_ttl = 30  # 30 ثانية

        # ⚡ Cache للأرقام التسلسلية
        self._sequence_cache: dict[str, int] = {}

        # خدمة الطباعة
        self.printing_service: ProjectPrintingService | None = None
        if PRINTING_AVAILABLE:
            self.printing_service = ProjectPrintingService(settings_service)

        self.bus.subscribe('CONVERT_TO_INVOICE', self.handle_convert_to_project)
        print("INFO: 🏢 قسم المشاريع Enterprise (ProjectService) جاهز")

    # ==================== Smart Coding Engine ====================
    def generate_smart_project_code(self, client_name: str, service_type: str | None = None) -> str:
        """
        🧠 توليد كود المشروع الذكي تلقائياً

        Format: [YEAR]-[TYPE]-[CLIENT]-[SEQ]
        Example: 2025-SEO-SKY-001

        Args:
            client_name: اسم العميل
            service_type: نوع الخدمة (اختياري)

        Returns:
            كود المشروع الذكي
        """
        try:
            # 1. السنة الحالية
            year = datetime.now().strftime("%Y")

            # 2. نوع الخدمة (أول 3 حروف)
            if service_type:
                # تنظيف وأخذ أول 3 حروف
                type_code = ''.join(c for c in service_type if c.isalnum())[:3].upper()
            else:
                type_code = "PRJ"  # افتراضي

            # 3. اسم العميل (أول 3 حروف)
            client_code = ''.join(c for c in client_name if c.isalnum())[:3].upper()
            if not client_code:
                client_code = "CLI"

            # 4. الرقم التسلسلي
            cache_key = f"{year}-{type_code}-{client_code}"

            # جلب آخر رقم تسلسلي من قاعدة البيانات - cursor منفصل
            try:
                cursor = self.repo.get_cursor()
                try:
                    cursor.execute("""
                        SELECT MAX(sequence_number) FROM projects
                        WHERE project_code LIKE ?
                    """, (f"{cache_key}-%",))
                    result = cursor.fetchone()
                    last_seq = result[0] if result and result[0] else 0
                finally:
                    cursor.close()
            except Exception:
                last_seq = self._sequence_cache.get(cache_key, 0)

            new_seq = last_seq + 1
            self._sequence_cache[cache_key] = new_seq

            # 5. تجميع الكود
            project_code = f"{year}-{type_code}-{client_code}-{new_seq:03d}"

            print(f"INFO: [ProjectService] 🧠 تم توليد كود المشروع: {project_code}")
            return project_code

        except Exception as e:
            print(f"ERROR: [ProjectService] فشل توليد كود المشروع: {e}")
            # Fallback: استخدام timestamp
            return f"PRJ-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # ==================== Profitability Analysis ====================
    def calculate_project_profitability(self, project: schemas.Project) -> dict:
        """
        💰 حساب ربحية المشروع اللحظية

        Returns:
            dict مع: total_revenue, total_cost, net_profit, margin_percent, health_status
        """
        try:
            # إجمالي الإيرادات
            total_revenue = project.total_amount or 0.0

            # إجمالي التكلفة التقديرية من البنود
            total_cost = sum(
                getattr(item, 'estimated_cost', 0.0) or 0.0
                for item in project.items
            )

            # صافي الربح
            net_profit = total_revenue - total_cost

            # نسبة هامش الربح
            margin_percent = (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0

            # تحديد حالة الصحة المالية
            if margin_percent >= 40:
                health_status = "excellent"  # أخضر
                health_color = "#10B981"
            elif margin_percent >= 20:
                health_status = "good"  # برتقالي
                health_color = "#F59E0B"
            else:
                health_status = "warning"  # أحمر
                health_color = "#EF4444"

            return {
                "total_revenue": total_revenue,
                "total_cost": total_cost,
                "net_profit": net_profit,
                "margin_percent": round(margin_percent, 2),
                "health_status": health_status,
                "health_color": health_color
            }

        except Exception as e:
            print(f"ERROR: [ProjectService] فشل حساب الربحية: {e}")
            return {
                "total_revenue": 0,
                "total_cost": 0,
                "net_profit": 0,
                "margin_percent": 0,
                "health_status": "unknown",
                "health_color": "#6B7280"
            }

    # ==================== Milestones Management ====================
    def validate_milestones(self, milestones: list[schemas.ProjectMilestone]) -> tuple:
        """
        ✅ التحقق من صحة الدفعات المرحلية

        Returns:
            (is_valid, error_message)
        """
        if not milestones:
            return True, ""

        total_percentage = sum(m.percentage for m in milestones)

        if abs(total_percentage - 100) > 0.01:
            return False, f"مجموع النسب يجب أن يساوي 100% (الحالي: {total_percentage:.2f}%)"

        return True, ""

    def update_milestone_status(self, project_name: str, milestone_id: str,
                                 new_status: schemas.MilestoneStatus,
                                 invoice_id: str | None = None) -> bool:
        """
        تحديث حالة دفعة مرحلية
        """
        try:
            project = self.repo.get_project_by_number(project_name)
            if not project:
                return False

            for milestone in project.milestones:
                if milestone.id == milestone_id:
                    milestone.status = new_status
                    if new_status == schemas.MilestoneStatus.PAID:
                        milestone.paid_date = datetime.now()
                    if invoice_id:
                        milestone.invoice_id = invoice_id
                    break

            self.repo.update_project(project_name, project)
            self.invalidate_cache()
            return True

        except Exception as e:
            print(f"ERROR: [ProjectService] فشل تحديث حالة الدفعة: {e}")
            return False

    def get_all_projects(self) -> list[schemas.Project]:
        """⚡ جلب كل المشاريع (مع cache للسرعة)"""
        try:
            # ⚡ استخدام الـ cache
            now = time.time()
            if self._cached_projects and (now - self._cache_time) < self._cache_ttl:
                return self._cached_projects

            # جلب من قاعدة البيانات
            projects = self.repo.get_all_projects(exclude_status=schemas.ProjectStatus.ARCHIVED)

            # تحديث الـ cache
            self._cached_projects = projects
            self._cache_time = now

            return projects
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل جلب المشاريع: {e}")
            return []

    def invalidate_cache(self):
        """⚡ إبطال الـ cache"""
        self._cached_projects = None
        self._cache_time = 0

    def update_all_projects_status(self):
        """⚡ تحديث حالات كل المشاريع أوتوماتيك (مع احترام التعديل اليدوي)"""
        print("INFO: [ProjectService] ===== بدء تحديث حالات المشاريع =====")
        try:
            projects = self.repo.get_all_projects()
            print(f"INFO: [ProjectService] عدد المشاريع: {len(projects)}")

            for project in projects:
                # تجاهل المشاريع المؤرشفة
                if project.status == schemas.ProjectStatus.ARCHIVED:
                    continue

                # ⚡ تجاهل المشاريع اللي حالتها معينة يدوياً
                status_manually_set = getattr(project, 'status_manually_set', False)
                if status_manually_set:
                    print(f"DEBUG: {project.name}: حالة يدوية - تم تجاهلها")
                    continue

                # جلب الدفعات
                payments = self.repo.get_payments_for_project(project.name)
                total_paid = sum(p.amount for p in payments) if payments else 0.0

                print(f"DEBUG: {project.name}: total={project.total_amount}, paid={total_paid}, status={project.status.value}")

                # تحديد الحالة الجديدة
                if project.total_amount > 0 and total_paid >= project.total_amount:
                    new_status = schemas.ProjectStatus.COMPLETED
                elif total_paid > 0:
                    new_status = schemas.ProjectStatus.ACTIVE
                else:
                    new_status = schemas.ProjectStatus.PLANNING

                # تحديث إذا تغيرت
                if project.status != new_status:
                    print(f"INFO: [ProjectService] تحديث {project.name}: {project.status.value} -> {new_status.value}")
                    project.status = new_status
                    project.status_manually_set = False  # الحالة أصبحت أوتوماتيك
                    self.repo.update_project(project.name, project)

            self.invalidate_cache()
            print("INFO: [ProjectService] ===== انتهى تحديث حالات المشاريع =====")
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل تحديث حالات المشاريع: {e}")
            import traceback
            traceback.print_exc()

    def get_archived_projects(self) -> list[schemas.Project]:
        """ جلب كل المشاريع المؤرشفة """
        try:
            return self.repo.get_all_projects(status=schemas.ProjectStatus.ARCHIVED)
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل جلب المشاريع المؤرشفة: {e}")
            return []

    def create_project(self, project_data: dict, payment_data: dict) -> schemas.Project:
        """
        🏢 إنشاء مشروع جديد Enterprise Level
        يدعم: التكويد الذكي، تحليل الربحية، الدفعات المرحلية
        """
        print(f"INFO: [ProjectService] 🏢 إنشاء مشروع: {project_data.get('name')}")
        try:
            # --- 1. حساب الإجماليات (مع خصم البند والتكلفة التقديرية) ---
            items_list = project_data.get("items", [])
            subtotal: float = 0.0
            total_estimated_cost: float = 0.0
            processed_items = []
            first_service_type = None

            for item in items_list:
                if isinstance(item, dict):
                    item_obj = schemas.ProjectItem(**item)
                else:
                    item_obj = item

                # حساب إجمالي البند مع الخصم
                item_subtotal = item_obj.quantity * item_obj.unit_price
                item_discount_rate = getattr(item_obj, 'discount_rate', 0.0)
                item_discount = item_subtotal * (item_discount_rate / 100)
                item_obj.discount_amount = item_discount
                item_obj.total = item_subtotal - item_discount

                subtotal += item_obj.total

                # ⚡ Enterprise: حساب التكلفة التقديرية
                estimated_cost = float(getattr(item_obj, 'estimated_cost', 0.0) or 0.0)
                total_estimated_cost += estimated_cost

                # حفظ نوع الخدمة الأولى للتكويد الذكي
                if not first_service_type:
                    first_service_type = getattr(item_obj, 'description', 'PRJ')

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

            # ⚡ Enterprise: حساب الربحية
            project_data['total_estimated_cost'] = total_estimated_cost
            project_data['estimated_profit'] = total_amount - total_estimated_cost
            project_data['profit_margin'] = (
                (total_amount - total_estimated_cost) / total_amount * 100
                if total_amount > 0 else 0
            )

            if 'start_date' not in project_data or not project_data['start_date']:
                project_data['start_date'] = datetime.now()

            if 'name' not in project_data or not project_data['name']:
                project_data['name'] = f"PROJ-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            # ⚡ Enterprise: توليد الكود الذكي
            client_id = project_data.get('client_id', '')
            client_name = client_id  # سيتم استبداله باسم العميل الفعلي
            try:
                client = self.repo.get_client_by_id(client_id)
                if client:
                    client_name = client.name
            except Exception:
                pass

            if not project_data.get('project_code'):
                project_data['project_code'] = self.generate_smart_project_code(
                    client_name=client_name,
                    service_type=first_service_type
                )

            # ⚡ Enterprise: التحقق من الدفعات المرحلية
            milestones = project_data.get('milestones', [])
            if milestones:
                is_valid, error_msg = self.validate_milestones(milestones)
                if not is_valid:
                    raise ValueError(f"خطأ في الدفعات المرحلية: {error_msg}")

            new_project_schema = schemas.Project(**project_data)

            # --- 2. حفظ المشروع في الداتا بيز ---
            created_project = self.repo.create_project(new_project_schema)

            # --- 3. (الأهم) إبلاغ الروبوت المحاسبي (قيد المشروع) ---
            self.bus.publish('PROJECT_CREATED', {"project": created_project})

            # --- 4. تسجيل الدفعة المقدمة (لو موجودة) ---
            if payment_data and payment_data.get("amount", 0) > 0:
                print(f"INFO: [ProjectService] تسجيل دفعة مقدمة بمبلغ {payment_data['amount']}...")
                self.create_payment_for_project(
                    project=created_project,
                    amount=payment_data["amount"],
                    date=payment_data["date"],
                    account_id=payment_data["account_id"]
                )

            # ⚡ إبطال الـ cache وإرسال إشارة التحديث
            self.invalidate_cache()
            app_signals.emit_data_changed('projects')

            print(f"SUCCESS: [ProjectService] ✅ تم إنشاء المشروع {created_project.name} (كود: {created_project.project_code})")
            return created_project

        except Exception as e:
            print(f"ERROR: [ProjectService] فشل إنشاء المشروع: {e}")
            raise

    def update_project(self, project_name: str, new_data_dict: dict) -> schemas.Project | None:
        """⚡ تعديل مشروع (مع إبطال الـ cache)"""
        print(f"INFO: [ProjectService] ⚡ تعديل مشروع: {project_name}")
        try:
            # (نفس لوجيك الحسابات - مع خصم البند)
            items_list = new_data_dict.get("items", [])
            subtotal: float = 0.0
            processed_items = []
            for item in items_list:
                if isinstance(item, dict):
                    item_obj = schemas.ProjectItem(**item)
                else:
                    item_obj = item

                # حساب إجمالي البند مع الخصم
                item_subtotal = item_obj.quantity * item_obj.unit_price
                item_discount_rate = getattr(item_obj, 'discount_rate', 0.0)
                item_discount = item_subtotal * (item_discount_rate / 100)
                item_obj.discount_amount = item_discount
                item_obj.total = item_subtotal - item_discount

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

            # ⚡ تحديد لو المستخدم غير الحالة يدوياً
            new_status = new_data_dict.get('status')
            if new_status and new_status != old_project.status:
                # المستخدم غير الحالة يدوياً
                new_data_dict['status_manually_set'] = True
                print(f"INFO: [ProjectService] المستخدم غير حالة المشروع يدوياً: {old_project.status.value} -> {new_status.value}")

            updated_project_schema = old_project.model_copy(update=new_data_dict)

            saved_project = self.repo.update_project(project_name, updated_project_schema)

            # ⚡ تحديث حالة المشروع أوتوماتيك بناءً على الدفعات (لو مش معينة يدوياً)
            if not new_data_dict.get('status_manually_set', False):
                self._auto_update_project_status(project_name, force_update=False)

            # ⚡ إبطال الـ cache وإبلاغ الروبوت المحاسبي
            self.invalidate_cache()
            self.bus.publish('PROJECT_EDITED', {"project": saved_project})
            app_signals.emit_data_changed('projects')

            print(f"SUCCESS: [ProjectService] ✅ تم تعديل المشروع {project_name}")

            # إعادة جلب المشروع بعد تحديث الحالة
            return self.repo.get_project_by_number(project_name)
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل تعديل المشروع: {e}")
            raise

    # --- (الجديد) دوال الدفعات بقت جوه المشاريع ---
    def create_payment_for_project(self, project: schemas.Project, amount: float, date: datetime, account_id: str) -> schemas.Payment | None:
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

            # ⚡ تحديث حالة المشروع أوتوماتيك بعد الدفعة
            self._auto_update_project_status(project.name, force_update=True)

            # ⚡ إرسال إشارات التحديث للـ UI
            app_signals.emit_data_changed('projects')
            app_signals.emit_data_changed('payments')

            print("SUCCESS: [ProjectService] تم تسجيل الدفعة.")
            return created_payment

        except Exception as e:
            print(f"ERROR: [ProjectService] فشل إنشاء الدفعة: {e}")
            raise

    def update_payment_for_project(self, payment_id, payment_data: schemas.Payment) -> bool:
        """⚡ تعديل دفعة مع تحديث حالة المشروع أوتوماتيك"""
        try:
            project_name = payment_data.project_id
            project = self.repo.get_project_by_number(project_name)
            result = self.repo.update_payment(payment_id, payment_data)

            if result:
                # ✅ إبلاغ الروبوت المحاسبي بتعديل الدفعة
                self.bus.publish('PAYMENT_UPDATED', {
                    "payment": payment_data,
                    "project": project
                })

                # ⚡ تحديث حالة المشروع أوتوماتيك
                self._auto_update_project_status(project_name, force_update=True)
                self.invalidate_cache()
                app_signals.emit_data_changed('projects')
                app_signals.emit_data_changed('payments')
                print("SUCCESS: [ProjectService] تم تعديل الدفعة وتحديث حالة المشروع")

            return result
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل تعديل الدفعة: {e}")
            return False

    def delete_payment_for_project(self, payment_id, project_name: str) -> bool:
        """⚡ حذف دفعة مع تحديث حالة المشروع أوتوماتيك"""
        try:
            # جلب بيانات الدفعة قبل الحذف
            payment = self.repo.get_payment_by_id(payment_id)

            result = self.repo.delete_payment(payment_id)

            if result:
                # ✅ إبلاغ الروبوت المحاسبي بحذف الدفعة
                self.bus.publish('PAYMENT_DELETED', {
                    "payment_id": payment_id,
                    "payment": payment,
                    "project_name": project_name
                })

                # ⚡ تحديث حالة المشروع أوتوماتيك
                self._auto_update_project_status(project_name, force_update=True)
                self.invalidate_cache()
                app_signals.emit_data_changed('projects')
                app_signals.emit_data_changed('payments')
                print("SUCCESS: [ProjectService] تم حذف الدفعة وتحديث حالة المشروع")

            return result
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل حذف الدفعة: {e}")
            return False

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

    def _auto_update_project_status(self, project_name: str, force_update: bool = False):
        """⚡ تحديث حالة المشروع أوتوماتيك بناءً على الدفعات (مع احترام التعديل اليدوي)"""
        try:
            project = self.repo.get_project_by_number(project_name)
            if not project:
                print(f"WARNING: [ProjectService] لم يتم العثور على المشروع: {project_name}")
                return

            # تجاهل المشاريع المؤرشفة
            if project.status == schemas.ProjectStatus.ARCHIVED:
                print(f"INFO: [ProjectService] المشروع {project_name} مؤرشف - لن يتم تحديث حالته")
                return

            # ⚡ تجاهل المشاريع اللي حالتها تم تعيينها يدوياً (إلا لو force_update)
            status_manually_set = getattr(project, 'status_manually_set', False)
            if status_manually_set and not force_update:
                print(f"INFO: [ProjectService] المشروع {project_name} حالته معينة يدوياً - لن يتم تحديثها أوتوماتيك")
                return

            # جلب الدفعات من قاعدة البيانات (Online أو Offline)
            total_paid = 0.0
            try:
                payments = self.repo.get_payments_for_project(project_name)
                total_paid = sum(p.amount for p in payments) if payments else 0.0
            except Exception as e:
                print(f"WARNING: [ProjectService] فشل جلب الدفعات: {e}")
                # محاولة من SQLite مباشرة - cursor منفصل
                try:
                    cursor = self.repo.get_cursor()
                    try:
                        cursor.execute(
                            "SELECT SUM(amount) FROM payments WHERE project_id = ?",
                            (project_name,)
                        )
                        result = cursor.fetchone()
                        total_paid = result[0] if result and result[0] else 0.0
                    finally:
                        cursor.close()
                except Exception:
                    pass  # تجاهل أخطاء جلب الدفعات

            # تحديد الحالة الجديدة بناءً على الدفعات
            new_status = None
            if project.total_amount > 0 and total_paid >= project.total_amount:
                new_status = schemas.ProjectStatus.COMPLETED
            elif total_paid > 0:
                new_status = schemas.ProjectStatus.ACTIVE
            else:
                new_status = schemas.ProjectStatus.PLANNING

            # تحديث الحالة إذا تغيرت
            if new_status and project.status != new_status:
                print(f"INFO: [ProjectService] ⚡ تحديث حالة {project_name}: {project.status.value} -> {new_status.value} (paid: {total_paid:,.2f} / total: {project.total_amount:,.2f})")
                project.status = new_status
                project.status_manually_set = False  # الحالة أصبحت أوتوماتيك
                self.repo.update_project(project_name, project)
                self.invalidate_cache()
                app_signals.emit_data_changed('projects')

        except Exception as e:
            print(f"WARNING: [ProjectService] فشل تحديث حالة المشروع {project_name}: {e}")

    def reset_project_status_to_auto(self, project_name: str) -> bool:
        """⚡ إعادة حالة المشروع للتحديث الأوتوماتيك"""
        try:
            project = self.repo.get_project_by_number(project_name)
            if not project:
                return False

            # إلغاء التعيين اليدوي
            project.status_manually_set = False
            self.repo.update_project(project_name, project)

            # تحديث الحالة أوتوماتيك
            self._auto_update_project_status(project_name, force_update=False)

            print(f"INFO: [ProjectService] ✅ تم إعادة حالة المشروع {project_name} للتحديث الأوتوماتيك")
            return True
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل إعادة حالة المشروع للأوتوماتيك: {e}")
            return False

    # --- دوال الربحية (معدلة عشان تستخدم الداتا الصح) ---
    def get_project_profitability(self, project_name: str) -> dict:
        """⚡ حساب ربحية المشروع (يدعم Online و Offline)"""
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
            total_expenses = 0
            total_paid = 0

            # ⚡ جلب البيانات من MongoDB أولاً (إذا متصل)
            if self.repo.online and self.repo.mongo_db is not None:
                try:
                    # جلب المصروفات من MongoDB
                    expenses = list(self.repo.mongo_db.expenses.find(
                        {"project_id": project_name},
                        {"amount": 1}
                    ))
                    total_expenses = sum([e.get("amount", 0) for e in expenses])
                    print(f"INFO: [Repo] جلب مصروفات مشروع: {project_name}")

                    # جلب الدفعات من MongoDB
                    payments = list(self.repo.mongo_db.payments.find(
                        {"project_id": project_name},
                        {"amount": 1}
                    ))
                    total_paid = sum([p.get("amount", 0) for p in payments])

                except Exception as e:
                    print(f"WARNING: [ProjectService] فشل جلب البيانات من MongoDB: {e}")
                    # fallback to SQLite
                    total_expenses = 0
                    total_paid = 0

            # ⚡ Fallback إلى SQLite إذا لم نحصل على بيانات - cursor منفصل
            if total_expenses == 0 and total_paid == 0:
                try:
                    cursor = self.repo.get_cursor()
                    try:
                        cursor.execute(
                            "SELECT SUM(amount) FROM expenses WHERE project_id = ?",
                            (project_name,)
                        )
                        result = cursor.fetchone()
                        total_expenses = result[0] if result and result[0] else 0

                        cursor.execute(
                            "SELECT SUM(amount) FROM payments WHERE project_id = ?",
                            (project_name,)
                        )
                        result = cursor.fetchone()
                        total_paid = result[0] if result and result[0] else 0
                    finally:
                        cursor.close()
                except Exception:
                    pass

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

    def get_payments_for_project(self, project_name: str) -> list[schemas.Payment]:  # (غيرنا الاسم)
        """ (جديدة) جلب كل الدفعات المرتبطة بمشروع """
        try:
            return self.repo.get_payments_for_project(project_name)  # (هنضيف دي للمخزن)
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل جلب دفعات المشروع: {e}")
            return []

    def get_project_by_id(self, project_id: str) -> schemas.Project | None:
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

    def get_project_payments(self, project_id) -> list[schemas.Payment]:
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

    def get_expenses_for_project(self, project_name: str) -> list[schemas.Expense]:
        try:
            return self.repo.get_expenses_for_project(project_name)
        except Exception as e:
            print(f"ERROR: [ProjectService] فشل جلب مصروفات المشروع: {e}")
            return []

    # --- وظائف الطباعة الجديدة ---
    def print_project_invoice(self, project_name: str, background_image_path: str | None = None, auto_open: bool = True) -> str | None:
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
            client_info: dict[str, str] = {
                "name": client.name if client else "عميل غير محدد",
                "phone": (client.phone or "") if client else "",
                "address": (client.address or "") if client else ""
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
            return str(self.printing_service.invoice_generator.generate_project_number(project_id))
        else:
            # نسخة مبسطة في حالة عدم توفر خدمة الطباعة
            try:
                numeric_part = ''.join(filter(str.isdigit, project_id))
                if len(numeric_part) >= 4:
                    return f"SW-{numeric_part[:4]}"
                else:
                    timestamp = datetime.now().strftime("%m%d")
                    return f"SW-{timestamp}"
            except (AttributeError, ValueError, TypeError):
                timestamp = datetime.now().strftime("%m%d")
                return f"SW-{timestamp}"
