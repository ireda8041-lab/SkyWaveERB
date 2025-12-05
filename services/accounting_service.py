# الملف: services/accounting_service.py

from core.repository import Repository
from core.event_bus import EventBus
from core import schemas
from core.signals import app_signals
from core.logger import get_logger
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = get_logger(__name__)


class AccountingService:
    """
    الروبوت المحاسبي (Service Layer).
    يستمع للأحداث المالية (زي إنشاء فاتورة) 
    ويقوم بإنشاء قيود اليومية المحاسبية أوتوماتيكياً.
    """
    
    # تعريف أكواد الحسابات الرئيسية (وكالة التسويق الرقمي)
    ACC_RECEIVABLE_CODE = "1200"  # حساب العملاء - مستحقات (مدين)
    SERVICE_REVENUE_CODE = "4100"  # حساب إيرادات سوشيال ميديا (دائن)
    DISCOUNT_ALLOWED_CODE = "4300"  # حساب إيرادات حملات إعلانية
    VAT_PAYABLE_CODE = "2100"  # حساب ضريبة القيمة المضافة (دائن - خصوم)
    CASH_ACCOUNT_CODE = "1101"  # حساب الخزنة الرئيسية (مدين عند التحصيل)
    
    # ⚡ Cache للشجرة المحاسبية
    _hierarchy_cache = None
    _hierarchy_cache_time = 0
    _HIERARCHY_CACHE_TTL = 60  # 60 ثانية

    def __init__(self, repository: Repository, event_bus: EventBus):
        """
        تهيئة الروبوت المحاسبي
        
        Args:
            repository: مخزن البيانات الرئيسي
            event_bus: نظام الأحداث للتواصل بين الخدمات
        """
        self.repo = repository
        self.bus = event_bus
        logger.info("الروبوت المحاسبي (AccountingService) جاهز")
        
        # أهم خطوة: الروبوت بيشترك في الأحداث أول ما يشتغل
        self._subscribe_to_events()

    def _subscribe_to_events(self) -> None:
        """
        دالة داخلية للاشتراك في كل الأحداث المالية.
        """
        self.bus.subscribe('INVOICE_CREATED', self.handle_new_invoice)
        self.bus.subscribe('EXPENSE_CREATED', self.handle_new_expense)
        self.bus.subscribe('EXPENSE_UPDATED', self.handle_updated_expense)  # ✅ تعديل مصروف
        self.bus.subscribe('EXPENSE_DELETED', self.handle_deleted_expense)  # ✅ حذف مصروف
        self.bus.subscribe('PAYMENT_RECEIVED', self.handle_new_payment)
        self.bus.subscribe('PAYMENT_UPDATED', self.handle_updated_payment)  # ✅ تعديل دفعة
        self.bus.subscribe('PAYMENT_DELETED', self.handle_deleted_payment)  # ✅ حذف دفعة
        self.bus.subscribe('INVOICE_VOIDED', self.handle_voided_invoice)
        self.bus.subscribe('INVOICE_EDITED', self.handle_edited_invoice)
        self.bus.subscribe('PROJECT_CREATED', self.handle_new_project)  # ✅ المشاريع = الفواتير
        self.bus.subscribe('PROJECT_EDITED', self.handle_edited_project)  # ✅ تعديل المشروع
        logger.info("[AccountingService] تم الاشتراك في جميع الأحداث المالية")

    def get_all_journal_entries(self) -> List[schemas.JournalEntry]:
        """
        جلب كل قيود اليومية
        
        Returns:
            قائمة بجميع قيود اليومية
        """
        try:
            return self.repo.get_all_journal_entries()
        except Exception as e:
            logger.error(f"[AccountingService] فشل جلب قيود اليومية: {e}", exc_info=True)
            return []

    def get_hierarchy_with_balances(self, force_refresh: bool = False) -> Dict[str, dict]:
        """
        ⚡ جلب شجرة الحسابات مع حساب الأرصدة التراكمية للمجموعات (مع cache)
        
        Returns:
            Dict[code, {obj: Account, total: float, children: []}]
        """
        import time
        
        # ⚡ استخدام الـ cache إذا كان صالحاً
        current_time = time.time()
        if not force_refresh and AccountingService._hierarchy_cache and (current_time - AccountingService._hierarchy_cache_time) < AccountingService._HIERARCHY_CACHE_TTL:
            print("INFO: [AccountingService] استخدام cache الشجرة المحاسبية")
            return AccountingService._hierarchy_cache
        
        print("INFO: [AccountingService] جاري حساب الأرصدة التراكمية للشجرة...")
        
        try:
            accounts = self.repo.get_all_accounts()
            
            if not accounts:
                print("WARNING: [AccountingService] لا توجد حسابات")
                return {}
            
            # 1. حساب الأرصدة من القيود المحاسبية
            account_movements = {}  # {code: {'debit': 0, 'credit': 0}}
            
            # إنشاء قاموس لربط account_id بـ account_code
            account_id_to_code = {}
            for acc in accounts:
                if acc.code:
                    # ربط بالـ _mongo_id
                    if hasattr(acc, '_mongo_id') and acc._mongo_id:
                        account_id_to_code[str(acc._mongo_id)] = acc.code
                    # ربط بالـ id
                    if hasattr(acc, 'id') and acc.id:
                        account_id_to_code[str(acc.id)] = acc.code
                    # ربط بالكود نفسه
                    account_id_to_code[acc.code] = acc.code
            
            try:
                # جلب القيود بالطريقة العادية (أكثر موثوقية)
                journal_entries = self.repo.get_all_journal_entries()
                print(f"DEBUG: [AccountingService] تم جلب {len(journal_entries)} قيد محاسبي")
                
                for entry in journal_entries:
                    for line in entry.lines:
                        # محاولة الحصول على الكود من account_code أو account_id
                        code = getattr(line, 'account_code', None)
                        if not code:
                            # محاولة الحصول على الكود من account_id
                            acc_id = getattr(line, 'account_id', None)
                            if acc_id:
                                code = account_id_to_code.get(str(acc_id))
                        
                        if not code:
                            continue
                            
                        if code not in account_movements:
                            account_movements[code] = {'debit': 0.0, 'credit': 0.0}
                        account_movements[code]['debit'] += getattr(line, 'debit', 0) or 0.0
                        account_movements[code]['credit'] += getattr(line, 'credit', 0) or 0.0
                
                print(f"DEBUG: [AccountingService] تم حساب حركات {len(account_movements)} حساب")
                for code, mov in list(account_movements.items())[:5]:
                    print(f"  - {code}: مدين={mov['debit']}, دائن={mov['credit']}")
                    
            except Exception as e:
                print(f"ERROR: [AccountingService] فشل جلب القيود: {e}")
                import traceback
                traceback.print_exc()
            
            process_events()
            
            # 2. إنشاء قاموس للوصول السريع O(1)
            tree_map: Dict[str, dict] = {}
            for acc in accounts:
                if acc.code:
                    tree_map[acc.code] = {
                        'obj': acc,
                        'total': 0.0,
                        'children': [],
                        'is_group': getattr(acc, 'is_group', False)
                    }
            
            # 3. بناء هيكل الشجرة وحساب الأرصدة من القيود
            def get_parent_code_from_code(code: str) -> str:
                """استنتاج كود الأب من كود الحساب تلقائياً"""
                if not code or len(code) < 4:
                    return None
                # أمثلة: 1101 -> 1100, 1100 -> 1000, 5201 -> 5200
                if code.endswith('00'):
                    # حساب مجموعة مثل 1100 -> 1000
                    return code[0] + '000'
                else:
                    # حساب فرعي مثل 1101 -> 1100
                    return code[:2] + '00'
            
            for acc in accounts:
                if not acc.code:
                    continue
                    
                node = tree_map[acc.code]
                
                # استخدام الرصيد المخزن في الحساب مباشرة (بدون حساب من القيود)
                # لأن القيود تُنشأ عند تسجيل الدفعات وتُحدث الرصيد تلقائياً
                opening_balance = getattr(acc, 'balance', 0.0) or 0.0
                node['total'] = opening_balance
            
            # ربط الحسابات بالآباء تلقائياً بناءً على الكود
            for acc in accounts:
                if not acc.code or acc.code.endswith('000'):
                    continue  # الحسابات الجذرية (1000, 2000, ...) ليس لها أب
                
                # استنتاج الأب من الكود
                parent_code = get_parent_code_from_code(acc.code)
                
                # التحقق من وجود الأب في الشجرة
                if parent_code and parent_code in tree_map and parent_code != acc.code:
                    tree_map[parent_code]['children'].append(tree_map[acc.code])
                    print(f"DEBUG: ربط {acc.code} -> {parent_code}")
            
            # طباعة الأبناء لكل حساب رئيسي
            for code in ['1000', '1100', '2000', '3000', '4000', '5000']:
                if code in tree_map:
                    children = [c['obj'].code for c in tree_map[code]['children']]
                    print(f"DEBUG: {code} أبناؤه: {children}")
            
            process_events()
            
            # 4. حساب الأرصدة التراكمية للمجموعات (من الأوراق للجذور)
            def calculate_total(node: dict) -> float:
                """حساب إجمالي العقدة بشكل تكراري"""
                # إذا لم يكن له أبناء، أرجع رصيده الخاص (بالقيمة المطلقة للأصول)
                if not node['children']:
                    return abs(node['total'])
                
                # حساب أرصدة الأبناء (بالقيمة المطلقة)
                total = sum(abs(calculate_total(child)) for child in node['children'])
                node['total'] = total
                return total
            
            # حساب من الجذور
            for code in ['1000', '2000', '3000', '4000', '5000']:
                if code in tree_map:
                    calculate_total(tree_map[code])
            
            process_events()
            
            # طباعة ملخص للتأكد
            print(f"INFO: [AccountingService] تم حساب أرصدة {len(tree_map)} حساب")
            
            # ⚡ حفظ في الـ cache
            AccountingService._hierarchy_cache = tree_map
            AccountingService._hierarchy_cache_time = time.time()
            
            return tree_map
            
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل حساب الأرصدة التراكمية: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def get_financial_summary(self) -> Dict[str, float]:
        """
        جلب ملخص مالي سريع (الأصول، الخصوم، الإيرادات، المصروفات، صافي الربح)
        
        Returns:
            Dict مع المفاتيح: assets, liabilities, equity, revenue, expenses, net_profit
        """
        try:
            tree_map = self.get_hierarchy_with_balances()
            
            # استخراج الأرصدة من الحسابات الرئيسية
            assets = tree_map.get('1000', {}).get('total', 0.0)
            liabilities = tree_map.get('2000', {}).get('total', 0.0)
            equity = tree_map.get('3000', {}).get('total', 0.0)
            revenue = tree_map.get('4000', {}).get('total', 0.0)
            expenses = tree_map.get('5000', {}).get('total', 0.0)
            
            # صافي الربح = الإيرادات - المصروفات
            net_profit = revenue - expenses
            
            return {
                'assets': assets,
                'liabilities': liabilities,
                'equity': equity,
                'revenue': revenue,
                'expenses': expenses,
                'net_profit': net_profit
            }
            
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل جلب الملخص المالي: {e}")
            return {
                'assets': 0.0,
                'liabilities': 0.0,
                'equity': 0.0,
                'revenue': 0.0,
                'expenses': 0.0,
                'net_profit': 0.0
            }

    def handle_new_invoice(self, data: dict):
        """
        معالج إنشاء فاتورة جديدة - ينشئ قيد يومية تلقائياً
        
        القيد المحاسبي للفاتورة:
        - مدين: حساب العملاء (1140) - يزيد المستحقات
        - دائن: حساب الإيرادات (4110) - يزيد الإيرادات
        """
        invoice: schemas.Invoice = data["invoice"]
        print(f"INFO: [AccountingService] تم استقبال حدث فاتورة جديدة: {invoice.invoice_number}")

        try:
            # إنشاء معرف الفاتورة
            invoice_id = getattr(invoice, '_mongo_id', None) or str(getattr(invoice, 'id', '')) or invoice.invoice_number
            
            # إنشاء القيد المحاسبي الرئيسي (العملاء مدين، الإيرادات دائن)
            success = self.post_journal_entry(
                date=invoice.date or datetime.now(),
                description=f"فاتورة مبيعات: {invoice.invoice_number}",
                ref_type="invoice",
                ref_id=invoice_id,
                debit_account_code=self.ACC_RECEIVABLE_CODE,  # حساب العملاء (مدين)
                credit_account_code=self.SERVICE_REVENUE_CODE,  # حساب الإيرادات (دائن)
                amount=invoice.total_amount
            )
            
            if success:
                print(f"SUCCESS: [AccountingService] تم إنشاء قيد اليومية للفاتورة {invoice.invoice_number}")
            else:
                print(f"ERROR: [AccountingService] فشل إنشاء قيد اليومية للفاتورة {invoice.invoice_number}")

        except Exception as e:
            print(f"ERROR: [AccountingService] فشل معالجة الفاتورة {invoice.invoice_number}: {e}")
            import traceback
            traceback.print_exc()

    def handle_new_project(self, data: dict):
        """
        ✅ معالج إنشاء مشروع جديد (المشروع = الفاتورة في النظام)
        ينشئ قيد يومية تلقائياً عند إنشاء مشروع جديد
        
        القيد المحاسبي للمشروع:
        - مدين: حساب العملاء (1200) - يزيد المستحقات
        - دائن: حساب الإيرادات (4100) - يزيد الإيرادات
        """
        project: schemas.Project = data["project"]
        print(f"INFO: [AccountingService] تم استقبال حدث مشروع جديد: {project.name}")

        try:
            # تجاهل المشاريع بدون قيمة
            if not project.total_amount or project.total_amount <= 0:
                print(f"INFO: [AccountingService] المشروع {project.name} بدون قيمة - لن يتم إنشاء قيد")
                return
            
            # إنشاء معرف المشروع
            project_id = getattr(project, '_mongo_id', None) or str(getattr(project, 'id', '')) or project.name
            
            # إنشاء القيد المحاسبي الرئيسي (العملاء مدين، الإيرادات دائن)
            success = self.post_journal_entry(
                date=project.start_date or datetime.now(),
                description=f"مشروع/فاتورة: {project.name}",
                ref_type="project",
                ref_id=project_id,
                debit_account_code=self.ACC_RECEIVABLE_CODE,  # حساب العملاء (مدين)
                credit_account_code=self.SERVICE_REVENUE_CODE,  # حساب الإيرادات (دائن)
                amount=project.total_amount
            )
            
            if success:
                print(f"SUCCESS: [AccountingService] تم إنشاء قيد اليومية للمشروع {project.name}")
            else:
                print(f"ERROR: [AccountingService] فشل إنشاء قيد اليومية للمشروع {project.name}")

        except Exception as e:
            print(f"ERROR: [AccountingService] فشل معالجة المشروع {project.name}: {e}")
            import traceback
            traceback.print_exc()

    def handle_edited_project(self, data: dict):
        """
        ✅ معالج تعديل مشروع - يحدث القيد المحاسبي
        
        عند تعديل قيمة المشروع، يتم:
        1. البحث عن القيد الأصلي
        2. تحديث القيد بالقيمة الجديدة
        """
        project: schemas.Project = data["project"]
        print(f"INFO: [AccountingService] تم استقبال حدث تعديل مشروع: {project.name}")

        try:
            project_id = getattr(project, '_mongo_id', None) or str(getattr(project, 'id', '')) or project.name
            
            # البحث عن القيد الأصلي
            original_entry = self.repo.get_journal_entry_by_doc_id(project_id)
            
            if not original_entry:
                # لا يوجد قيد أصلي - إنشاء قيد جديد إذا كان المشروع له قيمة
                if project.total_amount and project.total_amount > 0:
                    print(f"INFO: [AccountingService] لا يوجد قيد أصلي للمشروع {project.name} - إنشاء قيد جديد")
                    self.handle_new_project(data)
                return
            
            # تحديث القيد بالقيمة الجديدة
            ar_account = self.repo.get_account_by_code(self.ACC_RECEIVABLE_CODE)
            rev_account = self.repo.get_account_by_code(self.SERVICE_REVENUE_CODE)
            
            if not ar_account or not rev_account:
                print(f"ERROR: [AccountingService] لم يتم العثور على الحسابات المطلوبة")
                return
            
            new_lines = [
                schemas.JournalEntryLine(
                    account_id=ar_account.code,
                    account_code=ar_account.code,
                    account_name=ar_account.name,
                    debit=project.total_amount,
                    credit=0.0,
                    description=f"مدين: {ar_account.name}"
                ),
                schemas.JournalEntryLine(
                    account_id=rev_account.code,
                    account_code=rev_account.code,
                    account_name=rev_account.name,
                    debit=0.0,
                    credit=project.total_amount,
                    description=f"دائن: {rev_account.name}"
                )
            ]
            
            success = self.repo.update_journal_entry_by_doc_id(
                doc_id=project_id,
                new_lines=new_lines,
                new_description=f"تعديل مشروع/فاتورة: {project.name}"
            )
            
            if success:
                print(f"SUCCESS: [AccountingService] تم تحديث القيد المحاسبي للمشروع {project.name}")
            else:
                print(f"WARNING: [AccountingService] فشل تحديث القيد للمشروع {project.name}")

        except Exception as e:
            print(f"ERROR: [AccountingService] فشل تعديل قيد المشروع {project.name}: {e}")
            import traceback
            traceback.print_exc()

    def handle_new_expense(self, data):
        """
        معالج إنشاء مصروف جديد - ينشئ قيد يومية تلقائياً
        
        القيد المحاسبي للمصروف:
        - مدين: حساب المصروف (5xxx) - يزيد المصروفات
        - دائن: حساب الدفع (11xx) - ينقص النقدية
        """
        # دعم استقبال البيانات كـ dict أو كـ Expense مباشرة
        if isinstance(data, dict):
            expense = data.get("expense", data)
            if isinstance(expense, dict):
                expense = schemas.Expense(**expense)
        else:
            expense = data
            
        print(f"INFO: [AccountingService] تم استقبال حدث مصروف جديد: {expense.category} - {expense.amount} جنيه")
        print(f"INFO: [AccountingService] حساب المصروف: {expense.account_id}, حساب الدفع: {expense.payment_account_id}")

        try:
            # التحقق من وجود الحسابات المطلوبة
            expense_account_code = getattr(expense, 'account_id', None)
            payment_account_code = getattr(expense, 'payment_account_id', None)
            
            if not expense_account_code:
                print(f"WARNING: [AccountingService] لم يتم تحديد حساب المصروف، سيتم استخدام الحساب الافتراضي 5900")
                expense_account_code = "5900"  # مصروفات متنوعة
            
            if not payment_account_code:
                print(f"WARNING: [AccountingService] لم يتم تحديد حساب الدفع، سيتم استخدام الحساب الافتراضي 1111")
                payment_account_code = self.CASH_ACCOUNT_CODE  # الخزنة الرئيسية
            
            # إنشاء معرف المصروف
            expense_id = getattr(expense, '_mongo_id', None) or str(getattr(expense, 'id', '')) or f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # إنشاء القيد المحاسبي
            success = self.post_journal_entry(
                date=expense.date or datetime.now(),
                description=f"مصروف: {expense.category} - {expense.description or ''}",
                ref_type="expense",
                ref_id=expense_id,
                debit_account_code=expense_account_code,  # حساب المصروف (مدين)
                credit_account_code=payment_account_code,  # حساب الدفع (دائن)
                amount=expense.amount
            )
            
            if success:
                print(f"SUCCESS: [AccountingService] تم إنشاء قيد اليومية للمصروف {expense.category}")
            else:
                print(f"ERROR: [AccountingService] فشل إنشاء قيد اليومية للمصروف {expense.category}")

        except Exception as e:
            print(f"ERROR: [AccountingService] فشل معالجة المصروف: {e}")
            import traceback
            traceback.print_exc()

    def handle_updated_expense(self, data):
        """
        ✅ معالج تعديل مصروف - يحدث القيد المحاسبي
        """
        try:
            if isinstance(data, dict):
                expense = data.get("expense", data)
                if isinstance(expense, dict):
                    expense = schemas.Expense(**expense)
            else:
                expense = data
            
            print(f"INFO: [AccountingService] تم استقبال حدث تعديل مصروف: {expense.category}")
            
            expense_id = getattr(expense, '_mongo_id', None) or str(getattr(expense, 'id', ''))
            
            # البحث عن القيد الأصلي
            original_entry = self.repo.get_journal_entry_by_doc_id(expense_id)
            
            if not original_entry:
                print(f"INFO: [AccountingService] لا يوجد قيد أصلي للمصروف - إنشاء قيد جديد")
                self.handle_new_expense(data)
                return
            
            # تحديث القيد بالقيمة الجديدة
            expense_account_code = getattr(expense, 'account_id', None) or "5900"
            payment_account_code = getattr(expense, 'payment_account_id', None) or self.CASH_ACCOUNT_CODE
            
            expense_account = self.repo.get_account_by_code(expense_account_code)
            payment_account = self.repo.get_account_by_code(payment_account_code)
            
            if not expense_account or not payment_account:
                print(f"ERROR: [AccountingService] لم يتم العثور على الحسابات المطلوبة")
                return
            
            new_lines = [
                schemas.JournalEntryLine(
                    account_id=expense_account.code,
                    account_code=expense_account.code,
                    account_name=expense_account.name,
                    debit=expense.amount,
                    credit=0.0,
                    description=f"مدين: {expense_account.name}"
                ),
                schemas.JournalEntryLine(
                    account_id=payment_account.code,
                    account_code=payment_account.code,
                    account_name=payment_account.name,
                    debit=0.0,
                    credit=expense.amount,
                    description=f"دائن: {payment_account.name}"
                )
            ]
            
            success = self.repo.update_journal_entry_by_doc_id(
                doc_id=expense_id,
                new_lines=new_lines,
                new_description=f"تعديل مصروف: {expense.category}"
            )
            
            if success:
                print(f"SUCCESS: [AccountingService] تم تحديث القيد المحاسبي للمصروف")
            else:
                print(f"WARNING: [AccountingService] فشل تحديث القيد للمصروف")
                
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل تعديل قيد المصروف: {e}")
            import traceback
            traceback.print_exc()

    def handle_deleted_expense(self, data: dict):
        """
        ✅ معالج حذف مصروف - يعكس القيد المحاسبي
        """
        try:
            expense_id = data.get('id')
            if not expense_id:
                print(f"WARNING: [AccountingService] لم يتم تحديد معرف المصروف المحذوف")
                return
            
            print(f"INFO: [AccountingService] تم استقبال حدث حذف مصروف: {expense_id}")
            
            # البحث عن القيد الأصلي
            original_entry = self.repo.get_journal_entry_by_doc_id(str(expense_id))
            
            if not original_entry:
                print(f"INFO: [AccountingService] لا يوجد قيد محاسبي للمصروف المحذوف")
                return
            
            # إنشاء قيد عكسي
            reversed_lines = []
            for line in original_entry.lines:
                reversed_lines.append(
                    schemas.JournalEntryLine(
                        account_id=line.account_id,
                        account_code=getattr(line, 'account_code', None),
                        account_name=getattr(line, 'account_name', None),
                        debit=line.credit,  # عكس
                        credit=line.debit,  # عكس
                        description=f"عكس قيد: {line.description}"
                    )
                )
            
            journal_entry_data = schemas.JournalEntry(
                date=datetime.now(),
                description=f"قيد عكسي لحذف مصروف",
                lines=reversed_lines,
                related_document_id=f"DEL-{expense_id}"
            )
            
            self.repo.create_journal_entry(journal_entry_data)
            print(f"SUCCESS: [AccountingService] تم إنشاء القيد العكسي للمصروف المحذوف")
            
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل إنشاء القيد العكسي للمصروف: {e}")
            import traceback
            traceback.print_exc()

    def handle_new_payment(self, data: dict):
        """
        معالج استلام دفعة جديدة - ينشئ قيد يومية تلقائياً
        
        القيد المحاسبي للدفعة (تحصيل من عميل):
        - مدين: حساب النقدية/البنك (11xx) - يزيد النقدية
        - دائن: حساب العملاء (1140) - ينقص المستحقات
        """
        payment: schemas.Payment = data["payment"]
        # دعم المشاريع والفواتير
        project = data.get("project")
        invoice = data.get("invoice")
        
        print(f"INFO: [AccountingService] تم استقبال حدث دفعة جديدة: {payment.amount} جنيه")

        try:
            # تحديد حساب الاستلام (الخزينة أو البنك)
            receiving_account_code = getattr(payment, 'account_id', None) or self.CASH_ACCOUNT_CODE
            
            # تحديد حساب العميل (المستحقات)
            client_account_code = self.ACC_RECEIVABLE_CODE  # حساب العملاء
            
            # إنشاء معرف الدفعة
            payment_id = getattr(payment, '_mongo_id', None) or str(getattr(payment, 'id', '')) or f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # وصف الدفعة
            description = f"تحصيل دفعة: {payment.amount} جنيه"
            if invoice:
                description = f"تحصيل دفعة للفاتورة {getattr(invoice, 'invoice_number', '')}: {payment.amount} جنيه"
            elif project:
                description = f"تحصيل دفعة للمشروع {getattr(project, 'name', '')}: {payment.amount} جنيه"
            
            # إنشاء القيد المحاسبي
            success = self.post_journal_entry(
                date=payment.date or datetime.now(),
                description=description,
                ref_type="payment",
                ref_id=payment_id,
                debit_account_code=receiving_account_code,  # حساب النقدية (مدين)
                credit_account_code=client_account_code,    # حساب العملاء (دائن)
                amount=payment.amount
            )
            
            if success:
                print(f"SUCCESS: [AccountingService] تم إنشاء قيد اليومية للدفعة {payment.amount} جنيه")
            else:
                print(f"ERROR: [AccountingService] فشل إنشاء قيد اليومية للدفعة")

        except Exception as e:
            print(f"ERROR: [AccountingService] فشل معالجة الدفعة: {e}")
            import traceback
            traceback.print_exc()

    def handle_updated_payment(self, data: dict):
        """
        ✅ معالج تعديل دفعة - يحدث القيد المحاسبي
        """
        try:
            payment: schemas.Payment = data["payment"]
            print(f"INFO: [AccountingService] تم استقبال حدث تعديل دفعة: {payment.amount} جنيه")
            
            payment_id = getattr(payment, '_mongo_id', None) or str(getattr(payment, 'id', ''))
            
            # البحث عن القيد الأصلي
            original_entry = self.repo.get_journal_entry_by_doc_id(payment_id)
            
            if not original_entry:
                print(f"INFO: [AccountingService] لا يوجد قيد أصلي للدفعة - إنشاء قيد جديد")
                self.handle_new_payment(data)
                return
            
            # تحديد الحسابات
            receiving_account_code = getattr(payment, 'account_id', None) or self.CASH_ACCOUNT_CODE
            client_account_code = self.ACC_RECEIVABLE_CODE
            
            receiving_account = self.repo.get_account_by_code(receiving_account_code)
            client_account = self.repo.get_account_by_code(client_account_code)
            
            if not receiving_account or not client_account:
                print(f"ERROR: [AccountingService] لم يتم العثور على الحسابات المطلوبة")
                return
            
            new_lines = [
                schemas.JournalEntryLine(
                    account_id=receiving_account.code,
                    account_code=receiving_account.code,
                    account_name=receiving_account.name,
                    debit=payment.amount,
                    credit=0.0,
                    description=f"مدين: {receiving_account.name}"
                ),
                schemas.JournalEntryLine(
                    account_id=client_account.code,
                    account_code=client_account.code,
                    account_name=client_account.name,
                    debit=0.0,
                    credit=payment.amount,
                    description=f"دائن: {client_account.name}"
                )
            ]
            
            success = self.repo.update_journal_entry_by_doc_id(
                doc_id=payment_id,
                new_lines=new_lines,
                new_description=f"تعديل دفعة: {payment.amount} جنيه"
            )
            
            if success:
                print(f"SUCCESS: [AccountingService] تم تحديث القيد المحاسبي للدفعة")
            else:
                print(f"WARNING: [AccountingService] فشل تحديث القيد للدفعة")
                
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل تعديل قيد الدفعة: {e}")
            import traceback
            traceback.print_exc()

    def handle_deleted_payment(self, data: dict):
        """
        ✅ معالج حذف دفعة - يعكس القيد المحاسبي
        """
        try:
            payment_id = data.get('payment_id')
            payment = data.get('payment')
            
            if not payment_id:
                print(f"WARNING: [AccountingService] لم يتم تحديد معرف الدفعة المحذوفة")
                return
            
            print(f"INFO: [AccountingService] تم استقبال حدث حذف دفعة: {payment_id}")
            
            # البحث عن القيد الأصلي
            original_entry = self.repo.get_journal_entry_by_doc_id(str(payment_id))
            
            if not original_entry:
                print(f"INFO: [AccountingService] لا يوجد قيد محاسبي للدفعة المحذوفة")
                return
            
            # إنشاء قيد عكسي
            reversed_lines = []
            for line in original_entry.lines:
                reversed_lines.append(
                    schemas.JournalEntryLine(
                        account_id=line.account_id,
                        account_code=getattr(line, 'account_code', None),
                        account_name=getattr(line, 'account_name', None),
                        debit=line.credit,  # عكس
                        credit=line.debit,  # عكس
                        description=f"عكس قيد: {line.description}"
                    )
                )
            
            journal_entry_data = schemas.JournalEntry(
                date=datetime.now(),
                description=f"قيد عكسي لحذف دفعة",
                lines=reversed_lines,
                related_document_id=f"DEL-PAY-{payment_id}"
            )
            
            self.repo.create_journal_entry(journal_entry_data)
            print(f"SUCCESS: [AccountingService] تم إنشاء القيد العكسي للدفعة المحذوفة")
            
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل إنشاء القيد العكسي للدفعة: {e}")
            import traceback
            traceback.print_exc()

    def _update_account_balance(self, account, amount: float, is_debit: bool):
        """تحديث رصيد الحساب"""
        try:
            # الأصول والمصروفات: المدين يزيد، الدائن ينقص
            # الخصوم والإيرادات وحقوق الملكية: الدائن يزيد، المدين ينقص
            asset_types = [schemas.AccountType.ASSET, schemas.AccountType.CASH, schemas.AccountType.EXPENSE]
            
            if account.type in asset_types:
                new_balance = account.balance + amount if is_debit else account.balance - amount
            else:
                new_balance = account.balance - amount if is_debit else account.balance + amount
            
            account_id = account._mongo_id or str(account.id)
            self.repo.update_account(account_id, account.model_copy(update={"balance": new_balance}))
            print(f"INFO: [AccountingService] تم تحديث رصيد {account.name}: {new_balance}")
        except Exception as e:
            print(f"WARNING: [AccountingService] فشل تحديث رصيد الحساب: {e}")

    def get_profit_and_loss(self, start_date: datetime, end_date: datetime) -> Dict:
        """حساب تقرير الأرباح والخسائر لفترة محددة مع التفاصيل"""
        print(f"INFO: [AccountingService] جاري حساب P&L من {start_date} إلى {end_date}")
        try:
            total_revenue = 0.0
            total_expenses = 0.0
            revenue_breakdown = {}
            expense_breakdown = {}

            all_accounts = self.repo.get_all_accounts()
            account_info = {
                str(acc._mongo_id or acc.id): {"type": acc.type, "name": acc.name, "code": acc.code}
                for acc in all_accounts
            }
            # أيضاً نضيف بالكود للبحث
            for acc in all_accounts:
                account_info[acc.code] = {"type": acc.type, "name": acc.name, "code": acc.code}

            all_entries = self.repo.get_all_journal_entries()

            for entry in all_entries:
                entry_date = entry.date
                if hasattr(entry_date, 'replace'):
                    # تأكد من أن التاريخ بدون timezone
                    pass
                
                if start_date <= entry_date <= end_date:
                    for line in entry.lines:
                        acc_id = str(line.account_id)
                        acc_data = account_info.get(acc_id)
                        
                        if not acc_data:
                            continue

                        acc_type = acc_data["type"]
                        acc_name = acc_data["name"]

                        if acc_type == schemas.AccountType.REVENUE:
                            total_revenue += line.credit
                            if acc_name not in revenue_breakdown:
                                revenue_breakdown[acc_name] = 0.0
                            revenue_breakdown[acc_name] += line.credit
                            
                        elif acc_type == schemas.AccountType.EXPENSE:
                            total_expenses += line.debit
                            if acc_name not in expense_breakdown:
                                expense_breakdown[acc_name] = 0.0
                            expense_breakdown[acc_name] += line.debit

            net_profit = total_revenue - total_expenses

            return {
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "net_profit": net_profit,
                "revenue_breakdown": revenue_breakdown,
                "expense_breakdown": expense_breakdown
            }

        except Exception as e:
            print(f"ERROR: [AccountingService] فشل حساب P&L: {e}")
            return {
                "total_revenue": 0.0,
                "total_expenses": 0.0,
                "net_profit": 0.0,
                "revenue_breakdown": {},
                "expense_breakdown": {}
            }

    def handle_voided_invoice(self, invoice: schemas.Invoice):
        """
        (جديدة) المعالج الذي يتم استدعاؤه أوتوماتيكياً عند إلغاء فاتورة.
        """
        print(f"INFO: [AccountingService] تم استقبال حدث إلغاء فاتورة: {invoice.invoice_number}")

        try:
            doc_id = invoice._mongo_id or str(invoice.id)
            original_entry = self.repo.get_journal_entry_by_doc_id(doc_id)

            if not original_entry:
                print(f"WARNING: [AccountingService] لم يتم العثور على قيد أصلي للفاتورة {invoice.invoice_number} لعكسه.")
                return

            reversed_lines = []
            for line in original_entry.lines:
                reversed_lines.append(
                    schemas.JournalEntryLine(
                        account_id=line.account_id,
                        debit=line.credit,
                        credit=line.debit,
                        description=f"عكس قيد: {line.description}"
                    )
                )

            journal_entry_data = schemas.JournalEntry(
                date=datetime.now(),
                description=f"قيد آلي لعكس أثر الفاتورة الملغاة {invoice.invoice_number}",
                lines=reversed_lines,
                related_document_id=doc_id
            )

            self.repo.create_journal_entry(journal_entry_data)
            print(f"SUCCESS: [AccountingService] تم إنشاء القيد العكسي للفاتورة {invoice.invoice_number}.")

        except Exception as e:
            print(f"ERROR: [AccountingService] فشل إنشاء القيد العكسي للفاتورة {invoice.invoice_number}: {e}")

    def handle_edited_invoice(self, data: dict):
        """
        (معدلة) تعديل القيد الأصلي للفاتورة (باللوجيك الرباعي).
        """
        invoice: schemas.Invoice = data["invoice"]
        print(f"INFO: [AccountingService] تم استقبال حدث تعديل فاتورة: {invoice.invoice_number}")

        try:
            ar_account = self.repo.get_account_by_code(self.ACC_RECEIVABLE_CODE)
            rev_account = self.repo.get_account_by_code(self.SERVICE_REVENUE_CODE)
            discount_account = self.repo.get_account_by_code(self.DISCOUNT_ALLOWED_CODE)
            vat_account = self.repo.get_account_by_code(self.VAT_PAYABLE_CODE)

            if not all([ar_account, rev_account, discount_account, vat_account]):
                print("CRITICAL_ERROR: [AccountingService] لا يمكن إيجاد كل الحسابات المحاسبية (للتعديل).")
                return

            new_lines = []
            new_lines.append(
                schemas.JournalEntryLine(
                    account_id=ar_account._mongo_id or str(ar_account.id),
                    debit=invoice.total_amount,
                    credit=0.0,
                    description=f"قيمة فاتورة {invoice.invoice_number} (معدلة)"
                )
            )

            if invoice.discount_amount > 0:
                new_lines.append(
                    schemas.JournalEntryLine(
                        account_id=discount_account._mongo_id or str(discount_account.id),
                        debit=invoice.discount_amount,
                        credit=0.0,
                        description=f"خصم على فاتورة {invoice.invoice_number} (معدلة)"
                    )
                )

            new_lines.append(
                schemas.JournalEntryLine(
                    account_id=rev_account._mongo_id or str(rev_account.id),
                    debit=0.0,
                    credit=invoice.subtotal,
                    description=f"إثبات إيراد فاتورة {invoice.invoice_number} (معدلة)"
                )
            )

            if invoice.tax_amount > 0:
                new_lines.append(
                    schemas.JournalEntryLine(
                        account_id=vat_account._mongo_id or str(vat_account.id),
                        debit=0.0,
                        credit=invoice.tax_amount,
                        description=f"ضريبة ق.م. فاتورة {invoice.invoice_number} (معدلة)"
                    )
                )

            new_description = f"تعديل آلي لقيد الفاتورة {invoice.invoice_number}"

            success = self.repo.update_journal_entry_by_doc_id(
                doc_id=invoice._mongo_id or str(invoice.id),
                new_lines=new_lines,
                new_description=new_description
            )

            if success:
                print(f"SUCCESS: [AccountingService] تم تعديل القيد المحاسبي للفاتورة {invoice.invoice_number}.")
            else:
                print(f"ERROR: [AccountingService] فشل في تحديث القيد المحاسبي للفاتورة {invoice.invoice_number}.")

        except Exception as e:
            print(f"ERROR: [AccountingService] فشل تعديل القيد للفاتورة {invoice.invoice_number}: {e}")

    def get_dashboard_kpis(self) -> dict:
        """
        (جديدة) تطلب أرقام الداشبورد الرئيسية من المخزن.
        """
        print("INFO: [AccountingService] جاري طلب أرقام الداشبورد...")
        try:
            return self.repo.get_dashboard_kpis()
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل جلب أرقام الداشبورد: {e}")
            return {
                "total_collected": 0,
                "total_outstanding": 0,
                "total_expenses": 0,
                "net_profit_cash": 0,
            }

    def create_account(self, account_data: dict) -> schemas.Account:
        """ إضافة حساب جديد مع التحقق من parent_code """
        print(f"INFO: [AccountingService] استلام طلب إضافة حساب: {account_data.get('name')}")
        try:
            # التحقق من صحة parent_code إذا كان موجوداً
            if account_data.get('parent_code'):
                parent_account = self.repo.get_account_by_code(account_data['parent_code'])
                if not parent_account:
                    raise ValueError(f"الحساب الأب '{account_data['parent_code']}' غير موجود")
            
            # إنشاء كائن الحساب
            new_account_schema = schemas.Account(**account_data)
            created_account = self.repo.create_account(new_account_schema)
            
            # تحديث علامات is_group للحسابات
            if hasattr(self.repo, 'update_is_group_flags'):
                self.repo.update_is_group_flags()
            
            # إرسال إشارة التحديث العامة
            app_signals.emit_data_changed('accounts')
            
            print(f"SUCCESS: [AccountingService] تم إنشاء الحساب '{created_account.name}' بالكود '{created_account.code}'")
            return created_account
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل إضافة الحساب: {e}")
            raise

    def update_account(self, account_id: str, new_data: dict) -> Optional[schemas.Account]:
        """ تعديل بيانات حساب مع التحقق من parent_code """
        print(f"INFO: [AccountingService] استلام طلب تعديل الحساب ID: {account_id}")
        try:
            existing_account = self.repo.get_account_by_id(account_id)
            if not existing_account:
                raise Exception("الحساب غير موجود للتعديل.")

            # التحقق من صحة parent_code الجديد إذا كان موجوداً
            if new_data.get('parent_code'):
                parent_account = self.repo.get_account_by_code(new_data['parent_code'])
                if not parent_account:
                    raise ValueError(f"الحساب الأب '{new_data['parent_code']}' غير موجود")
                
                # التأكد من عدم إنشاء حلقة مفرغة (الحساب لا يمكن أن يكون أباً لنفسه)
                if new_data['parent_code'] == existing_account.code:
                    raise ValueError("لا يمكن للحساب أن يكون أباً لنفسه")
            
            # ⚠️ حماية الرصيد: لا نسمح بتعديل الرصيد يدوياً عند التحديث
            # الرصيد يُحسب فقط من القيود المحاسبية
            if 'balance' in new_data:
                print(f"WARNING: [AccountingService] Removing 'balance' from update data to preserve calculated balance")
                new_data = {k: v for k, v in new_data.items() if k != 'balance'}
            
            # حفظ الأرصدة الحالية قبل التحديث
            current_balance = existing_account.balance
            current_debit_total = existing_account.debit_total
            current_credit_total = existing_account.credit_total

            updated_account_schema = existing_account.model_copy(update=new_data)
            
            # استعادة الأرصدة المحسوبة
            updated_account_schema.balance = current_balance
            updated_account_schema.debit_total = current_debit_total
            updated_account_schema.credit_total = current_credit_total
            
            saved_account = self.repo.update_account(account_id, updated_account_schema)
            
            # تحديث علامات is_group للحسابات
            if hasattr(self.repo, 'update_is_group_flags'):
                self.repo.update_is_group_flags()
            
            print(f"SUCCESS: [AccountingService] تم تعديل الحساب {saved_account.name} بنجاح.")
            return saved_account
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل تعديل الحساب: {e}")
            raise

    def delete_account(self, account_id: str) -> bool:
        """ حذف حساب نهائياً من قاعدة البيانات """
        print(f"INFO: [AccountingService] استلام طلب حذف الحساب ID: {account_id}")
        try:
            return self.repo.delete_account_permanently(account_id)
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل حذف الحساب: {e}")
            raise
    
    def post_transaction(
        self,
        date: datetime,
        description: str,
        amount: float,
        currency: str,
        exchange_rate: float,
        debit_account_code: str,
        credit_account_code: str,
        ref_type: str = "manual",
        ref_id: str = None
    ) -> bool:
        """
        Smart Transaction Engine - The Brain of the Financial System
        
        Features:
        - Multi-currency support with automatic conversion to base currency (EGP)
        - Stores both original and converted amounts
        - Immediate balance updates (recursive for parent accounts)
        - Real-time GL posting
        
        Args:
            date: Transaction date
            description: Transaction description
            amount: Original amount in transaction currency
            currency: Currency code (EGP, USD, SAR, AED)
            exchange_rate: Exchange rate to EGP (1.0 for EGP)
            debit_account_code: Debit account code
            credit_account_code: Credit account code
            ref_type: Reference type (expense, payment, invoice, manual)
            ref_id: Reference document ID
        
        Returns:
            True if successful
        """
        print(f"INFO: [AccountingService] Smart Transaction: {description}")
        print(f"  Amount: {amount} {currency} @ {exchange_rate} = {amount * exchange_rate} EGP")
        
        try:
            # 1. Convert to base currency (EGP)
            amount_egp = amount * exchange_rate
            
            # 2. Verify accounts exist
            debit_account = self.repo.get_account_by_code(debit_account_code)
            credit_account = self.repo.get_account_by_code(credit_account_code)
            
            if not debit_account:
                print(f"ERROR: Debit account {debit_account_code} not found!")
                return False
            
            if not credit_account:
                print(f"ERROR: Credit account {credit_account_code} not found!")
                return False
            
            # 3. Create journal entry with currency info
            journal_entry = schemas.JournalEntry(
                date=date,
                description=f"{description} ({amount:,.2f} {currency})",
                lines=[
                    schemas.JournalEntryLine(
                        account_id=debit_account.code,
                        account_code=debit_account.code,
                        account_name=debit_account.name,
                        debit=amount_egp,
                        credit=0.0,
                        description=f"مدين: {debit_account.name}"
                    ),
                    schemas.JournalEntryLine(
                        account_id=credit_account.code,
                        account_code=credit_account.code,
                        account_name=credit_account.name,
                        debit=0.0,
                        credit=amount_egp,
                        description=f"دائن: {credit_account.name}"
                    )
                ],
                related_document_id=ref_id or f"{ref_type}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            
            # 4. Save to database
            self.repo.create_journal_entry(journal_entry)
            
            # 5. Update balances immediately (with recursive parent update)
            self._update_account_balance_recursive(debit_account, amount_egp, is_debit=True)
            self._update_account_balance_recursive(credit_account, amount_egp, is_debit=False)
            
            print(f"SUCCESS: Smart transaction posted successfully!")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to post transaction: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _update_account_balance_recursive(self, account, amount: float, is_debit: bool):
        """
        Update account balance and recursively update all parent accounts
        
        This ensures the tree view shows correct aggregated balances in real-time
        """
        try:
            # Update current account
            self._update_account_balance(account, amount, is_debit)
            
            # Recursively update parent accounts
            if account.parent_code:
                parent_account = self.repo.get_account_by_code(account.parent_code)
                if parent_account:
                    self._update_account_balance_recursive(parent_account, amount, is_debit)
                    
        except Exception as e:
            print(f"WARNING: Failed to update balance recursively: {e}")
    
    def post_journal_entry(
        self,
        date: datetime,
        description: str,
        ref_type: str,
        ref_id: str,
        debit_account_code: str,
        credit_account_code: str,
        amount: float
    ) -> bool:
        """
        إنشاء قيد يومية كامل مع تحديث الأرصدة
        
        هذه الدالة الرئيسية لإنشاء القيود المحاسبية:
        1. إنشاء قيد اليومية (Journal Entry Header)
        2. إنشاء بنود القيد (Debit & Credit Lines)
        3. تحديث أرصدة الحسابات فوراً
        
        Args:
            date: تاريخ القيد
            description: وصف القيد
            ref_type: نوع المرجع (expense, payment, invoice)
            ref_id: معرف المستند المرتبط
            debit_account_code: كود الحساب المدين
            credit_account_code: كود الحساب الدائن
            amount: المبلغ
        
        Returns:
            True إذا نجحت العملية
        """
        print(f"INFO: [AccountingService] post_journal_entry: {description} - {amount} جنيه")
        print(f"INFO: [AccountingService] مدين: {debit_account_code} | دائن: {credit_account_code}")
        
        try:
            # 1. التحقق من وجود الحسابات
            debit_account = self.repo.get_account_by_code(debit_account_code)
            credit_account = self.repo.get_account_by_code(credit_account_code)
            
            if not debit_account:
                print(f"ERROR: [AccountingService] الحساب المدين {debit_account_code} غير موجود!")
                return False
            
            if not credit_account:
                print(f"ERROR: [AccountingService] الحساب الدائن {credit_account_code} غير موجود!")
                return False
            
            print(f"INFO: [AccountingService] الحسابات موجودة: {debit_account.name} | {credit_account.name}")
            
            # 2. إنشاء قيد اليومية
            journal_entry = schemas.JournalEntry(
                date=date,
                description=description,
                lines=[
                    schemas.JournalEntryLine(
                        account_id=debit_account.code,  # استخدام الكود للتتبع
                        account_code=debit_account.code,
                        account_name=debit_account.name,
                        debit=amount,
                        credit=0.0,
                        description=f"مدين: {debit_account.name}"
                    ),
                    schemas.JournalEntryLine(
                        account_id=credit_account.code,  # استخدام الكود للتتبع
                        account_code=credit_account.code,
                        account_name=credit_account.name,
                        debit=0.0,
                        credit=amount,
                        description=f"دائن: {credit_account.name}"
                    )
                ],
                related_document_id=ref_id
            )
            
            # 3. حفظ القيد في قاعدة البيانات
            created_entry = self.repo.create_journal_entry(journal_entry)
            print(f"SUCCESS: [AccountingService] تم حفظ القيد في قاعدة البيانات")
            
            # 4. تحديث أرصدة الحسابات فوراً
            self._update_account_balance(debit_account, amount, is_debit=True)
            self._update_account_balance(credit_account, amount, is_debit=False)
            
            print(f"SUCCESS: [AccountingService] تم إنشاء القيد وتحديث الأرصدة بنجاح")
            return True
            
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل إنشاء القيد: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_transaction(
        self,
        date: datetime,
        description: str,
        ref_type: str,
        ref_id: str,
        debit_account_code: str,
        credit_account_code: str,
        amount: float
    ) -> bool:
        """
        إنشاء معاملة محاسبية كاملة (قيد يومية + تحديث الأرصدة)
        
        Args:
            date: تاريخ المعاملة
            description: وصف المعاملة
            ref_type: نوع المرجع (expense, payment, invoice)
            ref_id: معرف المرجع
            debit_account_code: كود الحساب المدين
            credit_account_code: كود الحساب الدائن
            amount: المبلغ
        
        Returns:
            True إذا نجحت العملية
        """
        print(f"INFO: [AccountingService] إنشاء معاملة: {description} - {amount} جنيه")
        
        try:
            # 1. التحقق من وجود الحسابات
            debit_account = self.repo.get_account_by_code(debit_account_code)
            credit_account = self.repo.get_account_by_code(credit_account_code)
            
            if not debit_account:
                raise Exception(f"الحساب المدين {debit_account_code} غير موجود")
            
            if not credit_account:
                raise Exception(f"الحساب الدائن {credit_account_code} غير موجود")
            
            # 2. إنشاء قيد اليومية
            journal_entry = schemas.JournalEntry(
                date=date,
                description=description,
                lines=[
                    schemas.JournalEntryLine(
                        account_id=debit_account._mongo_id or str(debit_account.id),
                        debit=amount,
                        credit=0.0,
                        description=f"مدين - {description}"
                    ),
                    schemas.JournalEntryLine(
                        account_id=credit_account._mongo_id or str(credit_account.id),
                        debit=0.0,
                        credit=amount,
                        description=f"دائن - {description}"
                    )
                ],
                related_document_id=ref_id
            )
            
            # 3. حفظ القيد
            created_entry = self.repo.create_journal_entry(journal_entry)
            
            # 4. تحديث أرصدة الحسابات
            self._update_account_balance(debit_account, amount, is_debit=True)
            self._update_account_balance(credit_account, amount, is_debit=False)
            
            print(f"SUCCESS: [AccountingService] تم إنشاء المعاملة بنجاح - القيد #{created_entry.id if hasattr(created_entry, 'id') else 'N/A'}")
            return True
            
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل إنشاء المعاملة: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_account_ledger(self, account_id: str, start_date: datetime, end_date: datetime) -> List[dict]:
        """
        جلب كشف حساب (تاريخ المعاملات) لحساب معين
        
        Args:
            account_id: معرف الحساب (ID أو Code)
            start_date: تاريخ البداية
            end_date: تاريخ النهاية
        
        Returns:
            قائمة بالمعاملات مع الرصيد الجاري
        """
        print(f"INFO: [AccountingService] جلب كشف حساب {account_id} من {start_date} إلى {end_date}")
        
        try:
            # جلب الحساب
            account = self.repo.get_account_by_id(account_id)
            if not account:
                account = self.repo.get_account_by_code(account_id)
            
            if not account:
                print(f"ERROR: الحساب {account_id} غير موجود")
                return []
            
            # جلب جميع قيود اليومية في الفترة المحددة
            all_entries = self.repo.get_all_journal_entries()
            
            ledger_transactions = []
            
            for entry in all_entries:
                # التحقق من التاريخ
                entry_date = entry.date
                if not (start_date <= entry_date <= end_date):
                    continue
                
                # البحث عن الأسطر المتعلقة بهذا الحساب
                for line in entry.lines:
                    # مقارنة بالـ ID أو الكود
                    line_account_id = str(line.account_id)
                    account_match = (
                        line_account_id == str(account._mongo_id) or
                        line_account_id == str(account.id) or
                        line_account_id == account.code
                    )
                    
                    if account_match:
                        ledger_transactions.append({
                            'date': entry_date,
                            'description': line.description or entry.description,
                            'reference': entry.related_document_id or '-',
                            'debit': line.debit,
                            'credit': line.credit,
                        })
            
            # ترتيب حسب التاريخ
            ledger_transactions.sort(key=lambda x: x['date'])
            
            print(f"INFO: تم جلب {len(ledger_transactions)} معاملة للحساب {account.name}")
            return ledger_transactions
            
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل جلب كشف الحساب: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def seed_test_transactions(self) -> dict:
        """
        إنشاء معاملات اختبارية لتجربة كشف الحساب
        """
        print("=" * 60)
        print("INFO: [AccountingService] بدء إنشاء معاملات اختبارية...")
        print("=" * 60)
        
        created_count = 0
        errors = []
        
        try:
            # التحقق من وجود الحسابات المطلوبة
            accounts_needed = {
                '1111': 'الخزنة الرئيسية',
                '1121': 'البنك الأهلي',
                '1140': 'العملاء',
                '4100': 'إيرادات الخدمات',
                '5110': 'الرواتب والأجور',
                '1131': 'فودافون كاش'
            }
            
            for code, name in accounts_needed.items():
                account = self.repo.get_account_by_code(code)
                if not account:
                    print(f"WARNING: الحساب {code} - {name} غير موجود")
            
            # معاملة 1: إيداع نقدي في البنك (10000 جنيه)
            try:
                bank_account = self.repo.get_account_by_code('1121')
                cash_account = self.repo.get_account_by_code('1111')
                
                if bank_account and cash_account:
                    entry1 = schemas.JournalEntry(
                        date=datetime.now() - timedelta(days=30),
                        description="إيداع نقدي في البنك الأهلي",
                        lines=[
                            schemas.JournalEntryLine(
                                account_id=bank_account._mongo_id or str(bank_account.id),
                                debit=10000.0,
                                credit=0.0,
                                description="إيداع في البنك الأهلي"
                            ),
                            schemas.JournalEntryLine(
                                account_id=cash_account._mongo_id or str(cash_account.id),
                                debit=0.0,
                                credit=10000.0,
                                description="سحب من الخزينة الرئيسية"
                            )
                        ],
                        related_document_id="DEP-001"
                    )
                    self.repo.create_journal_entry(entry1)
                    print("✅ تم إنشاء معاملة: إيداع في البنك (10000 جنيه)")
                    created_count += 1
            except Exception as e:
                error_msg = f"فشل إنشاء معاملة الإيداع: {e}"
                print(f"❌ {error_msg}")
                errors.append(error_msg)
            
            # معاملة 2: بيع خدمة (1500 جنيه)
            try:
                receivable_account = self.repo.get_account_by_code('1140')
                revenue_account = self.repo.get_account_by_code('4100')
                
                if receivable_account and revenue_account:
                    entry2 = schemas.JournalEntry(
                        date=datetime.now() - timedelta(days=20),
                        description="بيع خدمة تطوير موقع",
                        lines=[
                            schemas.JournalEntryLine(
                                account_id=receivable_account._mongo_id or str(receivable_account.id),
                                debit=1500.0,
                                credit=0.0,
                                description="مستحق من العميل - شركة ABC"
                            ),
                            schemas.JournalEntryLine(
                                account_id=revenue_account._mongo_id or str(revenue_account.id),
                                debit=0.0,
                                credit=1500.0,
                                description="إيراد خدمة تطوير موقع"
                            )
                        ],
                        related_document_id="INV-001"
                    )
                    self.repo.create_journal_entry(entry2)
                    print("✅ تم إنشاء معاملة: بيع خدمة (1500 جنيه)")
                    created_count += 1
            except Exception as e:
                error_msg = f"فشل إنشاء معاملة بيع الخدمة: {e}"
                print(f"❌ {error_msg}")
                errors.append(error_msg)
            
            # معاملة 3: دفع راتب (2000 جنيه)
            try:
                salary_account = self.repo.get_account_by_code('5110')
                vodafone_account = self.repo.get_account_by_code('1131')
                
                if salary_account and vodafone_account:
                    entry3 = schemas.JournalEntry(
                        date=datetime.now() - timedelta(days=10),
                        description="دفع راتب شهر نوفمبر",
                        lines=[
                            schemas.JournalEntryLine(
                                account_id=salary_account._mongo_id or str(salary_account.id),
                                debit=2000.0,
                                credit=0.0,
                                description="راتب الموظف - أحمد محمد"
                            ),
                            schemas.JournalEntryLine(
                                account_id=vodafone_account._mongo_id or str(vodafone_account.id),
                                debit=0.0,
                                credit=2000.0,
                                description="دفع عبر فودافون كاش"
                            )
                        ],
                        related_document_id="SAL-001"
                    )
                    self.repo.create_journal_entry(entry3)
                    print("✅ تم إنشاء معاملة: دفع راتب (2000 جنيه)")
                    created_count += 1
            except Exception as e:
                error_msg = f"فشل إنشاء معاملة دفع الراتب: {e}"
                print(f"❌ {error_msg}")
                errors.append(error_msg)
            
            # معاملة 4: تحصيل من العميل (1500 جنيه)
            try:
                receivable_account = self.repo.get_account_by_code('1140')
                cash_account = self.repo.get_account_by_code('1111')
                
                if receivable_account and cash_account:
                    entry4 = schemas.JournalEntry(
                        date=datetime.now() - timedelta(days=5),
                        description="تحصيل من العميل - شركة ABC",
                        lines=[
                            schemas.JournalEntryLine(
                                account_id=cash_account._mongo_id or str(cash_account.id),
                                debit=1500.0,
                                credit=0.0,
                                description="تحصيل نقدي"
                            ),
                            schemas.JournalEntryLine(
                                account_id=receivable_account._mongo_id or str(receivable_account.id),
                                debit=0.0,
                                credit=1500.0,
                                description="سداد من العميل - شركة ABC"
                            )
                        ],
                        related_document_id="REC-001"
                    )
                    self.repo.create_journal_entry(entry4)
                    print("✅ تم إنشاء معاملة: تحصيل من العميل (1500 جنيه)")
                    created_count += 1
            except Exception as e:
                error_msg = f"فشل إنشاء معاملة التحصيل: {e}"
                print(f"❌ {error_msg}")
                errors.append(error_msg)
            
            print("\n" + "=" * 60)
            print(f"✅ تم إنشاء {created_count} معاملة اختبارية")
            if errors:
                print(f"❌ فشل إنشاء {len(errors)} معاملة")
            print("=" * 60)
            
            return {
                "success": True,
                "created": created_count,
                "errors": errors,
                "message": f"تم إنشاء {created_count} معاملة اختبارية"
            }
            
        except Exception as e:
            error_msg = f"فشل إنشاء المعاملات الاختبارية: {e}"
            print(f"ERROR: [AccountingService] {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "created": created_count,
                "errors": errors + [error_msg],
                "message": error_msg
            }
    
    def reset_and_seed_agency_accounts(self) -> dict:
        """
        RESET & SEED: Wipe existing accounts and create fresh Digital Marketing Agency structure
        
        WARNING: This will delete ALL existing accounts and journal entries!
        Use only for initial setup or complete reset.
        """
        print("=" * 60)
        print("⚠️  WARNING: RESETTING ALL ACCOUNTING DATA!")
        print("=" * 60)
        
        try:
            # 1. Delete all existing accounts (if method exists)
            if hasattr(self.repo, 'delete_all_accounts'):
                self.repo.delete_all_accounts()
                print("✅ Deleted all existing accounts")
            
            # 2. Seed new accounts
            result = self.seed_default_accounts()
            
            print("=" * 60)
            print("✅ RESET COMPLETE - Fresh Agency Accounts Created!")
            print("=" * 60)
            
            return result
            
        except Exception as e:
            print(f"ERROR: Failed to reset accounts: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "created": 0,
                "errors": [str(e)],
                "message": "Reset failed"
            }
    
    def seed_default_accounts(self) -> dict:
        """
        إنشاء شجرة حسابات مخصصة لوكالة التسويق الرقمي (Sky Wave)
        """
        print("=" * 60)
        print("INFO: [AccountingService] إنشاء حسابات وكالة التسويق الرقمي...")
        print("=" * 60)
        
        # شجرة حسابات مخصصة لوكالة إعلانات ديجيتال
        AD_AGENCY_ACCOUNTS = [
            # --- 1. ASSETS (الأصول) ---
            {"code": "1000", "name": "الأصول", "type": schemas.AccountType.ASSET, "parent": None, "is_group": True},
            {"code": "1100", "name": "النقدية والبنوك", "type": schemas.AccountType.CASH, "parent": "1000", "is_group": True},
            {"code": "1101", "name": "الخزنة الرئيسية", "type": schemas.AccountType.CASH, "parent": "1100", "is_group": False},
            {"code": "1102", "name": "CIB Bank", "type": schemas.AccountType.CASH, "parent": "1100", "is_group": False},
            {"code": "1103", "name": "Vodafone Cash", "type": schemas.AccountType.CASH, "parent": "1100", "is_group": False},
            {"code": "1104", "name": "Instapay", "type": schemas.AccountType.CASH, "parent": "1100", "is_group": False},
            {"code": "1200", "name": "العملاء (مدينون)", "type": schemas.AccountType.ASSET, "parent": "1000", "is_group": False},  # Control Account
            
            # --- 4. REVENUE (الإيرادات) ---
            {"code": "4000", "name": "الإيرادات", "type": schemas.AccountType.REVENUE, "parent": None, "is_group": True},
            {"code": "4100", "name": "إيرادات سوشيال ميديا", "type": schemas.AccountType.REVENUE, "parent": "4000", "is_group": False},
            {"code": "4200", "name": "إيرادات تصميم ومواقع", "type": schemas.AccountType.REVENUE, "parent": "4000", "is_group": False},
            {"code": "4300", "name": "إيرادات حملات إعلانية", "type": schemas.AccountType.REVENUE, "parent": "4000", "is_group": False},
            
            # --- 5. EXPENSES (المصروفات) ---
            {"code": "5000", "name": "المصروفات", "type": schemas.AccountType.EXPENSE, "parent": None, "is_group": True},
            
            # Direct Costs (تكاليف التشغيل)
            {"code": "5100", "name": "تكاليف الحملات (Media Buying)", "type": schemas.AccountType.EXPENSE, "parent": "5000", "is_group": True},
            {"code": "5101", "name": "شحن فيسبوك (Meta Ads)", "type": schemas.AccountType.EXPENSE, "parent": "5100", "is_group": False},
            {"code": "5102", "name": "شحن جوجل (Google Ads)", "type": schemas.AccountType.EXPENSE, "parent": "5100", "is_group": False},
            {"code": "5103", "name": "سيرفرات ودومينات", "type": schemas.AccountType.EXPENSE, "parent": "5100", "is_group": False},
            
            # Operating Expenses (مصاريف إدارية)
            {"code": "5200", "name": "مصاريف إدارية", "type": schemas.AccountType.EXPENSE, "parent": "5000", "is_group": True},
            {"code": "5201", "name": "رواتب الموظفين", "type": schemas.AccountType.EXPENSE, "parent": "5200", "is_group": False},
            {"code": "5202", "name": "فريلانسرز (Freelancers)", "type": schemas.AccountType.EXPENSE, "parent": "5200", "is_group": False},
            {"code": "5203", "name": "إيجار ومرافق", "type": schemas.AccountType.EXPENSE, "parent": "5200", "is_group": False},
            {"code": "5204", "name": "اشتراكات أدوات (Canva/Adobe)", "type": schemas.AccountType.EXPENSE, "parent": "5200", "is_group": False},
        ]
        
        DEFAULT_ACCOUNTS = AD_AGENCY_ACCOUNTS
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        try:
            # جلب الحسابات الموجودة للتحقق من التكرار
            existing_accounts = self.repo.get_all_accounts()
            existing_codes = {acc.code for acc in existing_accounts}
            
            print(f"INFO: عدد الحسابات الموجودة حالياً: {len(existing_codes)}")
            
            # إنشاء الحسابات بالترتيب (الآباء أولاً)
            for account_template in DEFAULT_ACCOUNTS:
                code = account_template["code"]
                
                # التحقق من عدم التكرار
                if code in existing_codes:
                    print(f"⏭️  تخطي: {code} - {account_template['name']} (موجود مسبقاً)")
                    skipped_count += 1
                    continue
                
                try:
                    # إنشاء بيانات الحساب
                    account_data = {
                        "code": code,
                        "name": account_template["name"],
                        "type": account_template["type"],
                        "parent_code": account_template["parent"],
                        "is_group": account_template["is_group"],
                        "balance": 0.0,
                        "currency": "EGP",
                        "status": schemas.AccountStatus.ACTIVE,
                    }
                    
                    # إنشاء الحساب
                    new_account = schemas.Account(**account_data)
                    created_account = self.repo.create_account(new_account)
                    
                    # إضافة إلى قائمة الأكواد الموجودة
                    existing_codes.add(code)
                    
                    group_indicator = "📁" if account_template["is_group"] else "📄"
                    parent_info = f" (تحت {account_template['parent']})" if account_template['parent'] else ""
                    print(f"✅ {group_indicator} {code} - {account_template['name']}{parent_info}")
                    
                    created_count += 1
                    
                except Exception as e:
                    error_msg = f"❌ فشل إنشاء {code} - {account_template['name']}: {e}"
                    print(error_msg)
                    errors.append(error_msg)
            
            print("\n" + "=" * 60)
            print(f"✅ تم إنشاء {created_count} حساب جديد")
            print(f"⏭️  تم تخطي {skipped_count} حساب (موجود مسبقاً)")
            if errors:
                print(f"❌ فشل إنشاء {len(errors)} حساب")
            print("=" * 60)
            
            return {
                "success": True,
                "created": created_count,
                "skipped": skipped_count,
                "errors": errors,
                "message": f"تم إنشاء {created_count} حساب، تخطي {skipped_count} حساب موجود"
            }
            
        except Exception as e:
            error_msg = f"فشل إنشاء الحسابات الافتراضية: {e}"
            print(f"ERROR: [AccountingService] {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "created": created_count,
                "skipped": skipped_count,
                "errors": errors + [error_msg],
                "message": error_msg
            }


    def cleanup_client_sub_accounts(self) -> dict:
        """
        تنظيف الحسابات الفرعية تحت حساب العملاء (1140)
        
        هذه الدالة تحذف أي حسابات فرعية تم إنشاؤها تحت حساب العملاء الرئيسي
        وتضمن أن حساب 1140 هو حساب معاملات (ليس مجموعة)
        
        Control Account Pattern:
        - جميع معاملات العملاء تُسجل في حساب 1140 مباشرة
        - لا يتم إنشاء حسابات فرعية لكل عميل
        - تتبع العملاء يتم عبر جدول العملاء وليس شجرة الحسابات
        """
        print("=" * 60)
        print("INFO: [AccountingService] بدء تنظيف الحسابات الفرعية للعملاء...")
        print("=" * 60)
        
        deleted_count = 0
        errors = []
        
        try:
            # جلب جميع الحسابات
            all_accounts = self.repo.get_all_accounts()
            
            # البحث عن الحسابات الفرعية تحت 1140
            sub_accounts_to_delete = []
            main_account = None
            
            for acc in all_accounts:
                # حساب العملاء الرئيسي
                if acc.code == self.ACC_RECEIVABLE_CODE:
                    main_account = acc
                    continue
                
                # الحسابات الفرعية (تبدأ بـ 1140 أو parent_code = 1140)
                if acc.code and acc.code.startswith("1140") and acc.code != "1140":
                    sub_accounts_to_delete.append(acc)
                elif acc.parent_code == self.ACC_RECEIVABLE_CODE:
                    sub_accounts_to_delete.append(acc)
            
            print(f"INFO: تم العثور على {len(sub_accounts_to_delete)} حساب فرعي للحذف")
            
            # حذف الحسابات الفرعية
            for acc in sub_accounts_to_delete:
                try:
                    account_id = acc._mongo_id or str(acc.id)
                    # أرشفة الحساب بدلاً من الحذف الكامل
                    success = self.repo.archive_account_by_id(account_id)
                    if success:
                        print(f"✅ تم أرشفة: {acc.code} - {acc.name}")
                        deleted_count += 1
                    else:
                        print(f"⚠️ فشل أرشفة: {acc.code} - {acc.name}")
                except Exception as e:
                    error_msg = f"فشل أرشفة {acc.code}: {e}"
                    print(f"❌ {error_msg}")
                    errors.append(error_msg)
            
            # التأكد من أن حساب 1140 هو حساب معاملات (ليس مجموعة)
            if main_account:
                if getattr(main_account, 'is_group', True):
                    try:
                        account_id = main_account._mongo_id or str(main_account.id)
                        updated_data = {"is_group": False}
                        self.repo.update_account(account_id, main_account.model_copy(update=updated_data))
                        print(f"✅ تم تحديث حساب العملاء (1140) ليكون حساب معاملات")
                    except Exception as e:
                        error_msg = f"فشل تحديث حساب 1140: {e}"
                        print(f"❌ {error_msg}")
                        errors.append(error_msg)
                else:
                    print(f"✅ حساب العملاء (1140) هو بالفعل حساب معاملات")
            else:
                print(f"⚠️ حساب العملاء (1140) غير موجود!")
            
            print("\n" + "=" * 60)
            print(f"✅ تم أرشفة {deleted_count} حساب فرعي")
            if errors:
                print(f"❌ فشل {len(errors)} عملية")
            print("=" * 60)
            
            return {
                "success": len(errors) == 0,
                "deleted": deleted_count,
                "errors": errors,
                "message": f"تم أرشفة {deleted_count} حساب فرعي تحت العملاء"
            }
            
        except Exception as e:
            error_msg = f"فشل تنظيف الحسابات الفرعية: {e}"
            print(f"ERROR: [AccountingService] {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "deleted": deleted_count,
                "errors": errors + [error_msg],
                "message": error_msg
            }
    
    def get_client_balance(self, client_id: str) -> float:
        """
        حساب رصيد عميل معين من قيود اليومية
        
        بما أننا نستخدم Control Account (1140) لجميع العملاء،
        نحتاج لحساب رصيد كل عميل من خلال تتبع القيود المرتبطة به
        
        Args:
            client_id: معرف العميل
        
        Returns:
            رصيد العميل (موجب = مستحق على العميل، سالب = مستحق للعميل)
        """
        try:
            # جلب جميع الفواتير للعميل
            invoices = self.repo.get_invoices_by_client(client_id) if hasattr(self.repo, 'get_invoices_by_client') else []
            
            # جلب جميع الدفعات للعميل
            payments = self.repo.get_payments_by_client(client_id) if hasattr(self.repo, 'get_payments_by_client') else []
            
            # حساب إجمالي الفواتير (مستحق على العميل)
            total_invoiced = sum(inv.total_amount for inv in invoices if hasattr(inv, 'total_amount'))
            
            # حساب إجمالي المدفوعات (مدفوع من العميل)
            total_paid = sum(pay.amount for pay in payments if hasattr(pay, 'amount'))
            
            # الرصيد = الفواتير - المدفوعات
            balance = total_invoiced - total_paid
            
            return balance
            
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل حساب رصيد العميل {client_id}: {e}")
            return 0.0
    
    def get_all_clients_balances(self) -> List[dict]:
        """
        جلب أرصدة جميع العملاء
        
        Returns:
            قائمة بأرصدة العملاء [{client_id, client_name, balance}, ...]
        """
        try:
            # جلب جميع العملاء
            clients = self.repo.get_all_clients() if hasattr(self.repo, 'get_all_clients') else []
            
            balances = []
            for client in clients:
                client_id = client._mongo_id or str(client.id) if hasattr(client, '_mongo_id') else str(client.id)
                balance = self.get_client_balance(client_id)
                
                balances.append({
                    'client_id': client_id,
                    'client_name': client.name,
                    'balance': balance,
                    'status': 'مستحق' if balance > 0 else ('مسدد' if balance == 0 else 'دائن')
                })
            
            return balances
            
        except Exception as e:
            print(f"ERROR: [AccountingService] فشل جلب أرصدة العملاء: {e}")
            return []

    def fix_accounts_parent_codes(self) -> dict:
        """
        إصلاح ربط الحسابات بالآباء الصحيحين
        
        هذه الدالة تقوم بتحديث parent_code لجميع الحسابات بناءً على
        الهيكل المنطقي لشجرة الحسابات (Sky Wave)
        
        Returns:
            dict مع نتائج الإصلاح
        """
        print("=" * 60)
        print("INFO: [AccountingService] إصلاح ربط الحسابات بالآباء...")
        print("=" * 60)
        
        # خريطة الحسابات والآباء الصحيحين
        CORRECT_PARENT_MAP = {
            # الأصول
            "1000": None,           # الأصول - جذر
            "1100": "1000",         # النقدية والبنوك -> الأصول
            "1101": "1100",         # الخزنة الرئيسية -> النقدية والبنوك
            "1102": "1100",         # CIB Bank -> النقدية والبنوك
            "1103": "1100",         # Vodafone Cash -> النقدية والبنوك
            "1104": "1100",         # Instapay -> النقدية والبنوك
            "1200": "1000",         # العملاء -> الأصول
            
            # الخصوم
            "2000": None,           # الخصوم - جذر
            "2100": "2000",         # ضريبة القيمة المضافة -> الخصوم
            "2200": "2000",         # الموردون -> الخصوم
            
            # حقوق الملكية
            "3000": None,           # حقوق الملكية - جذر
            "3100": "3000",         # رأس المال -> حقوق الملكية
            "3200": "3000",         # الأرباح المحتجزة -> حقوق الملكية
            
            # الإيرادات
            "4000": None,           # الإيرادات - جذر
            "4100": "4000",         # إيرادات سوشيال ميديا -> الإيرادات
            "4200": "4000",         # إيرادات تصميم ومواقع -> الإيرادات
            "4300": "4000",         # إيرادات حملات إعلانية -> الإيرادات
            
            # المصروفات
            "5000": None,           # المصروفات - جذر
            "5100": "5000",         # تكاليف الحملات -> المصروفات
            "5101": "5100",         # شحن فيسبوك -> تكاليف الحملات
            "5102": "5100",         # شحن جوجل -> تكاليف الحملات
            "5103": "5100",         # سيرفرات ودومينات -> تكاليف الحملات
            "5200": "5000",         # مصاريف إدارية -> المصروفات
            "5201": "5200",         # رواتب الموظفين -> مصاريف إدارية
            "5202": "5200",         # فريلانسرز -> مصاريف إدارية
            "5203": "5200",         # إيجار ومرافق -> مصاريف إدارية
            "5204": "5200",         # اشتراكات أدوات -> مصاريف إدارية
            "5900": "5000",         # مصروفات متنوعة -> المصروفات
        }
        
        updated_count = 0
        skipped_count = 0
        errors = []
        
        try:
            # جلب جميع الحسابات
            all_accounts = self.repo.get_all_accounts()
            print(f"INFO: عدد الحسابات: {len(all_accounts)}")
            
            for acc in all_accounts:
                if not acc.code:
                    continue
                
                # الحصول على الأب الصحيح
                correct_parent = CORRECT_PARENT_MAP.get(acc.code)
                # قاعدة البيانات تستخدم parent_id
                current_parent = getattr(acc, 'parent_id', None) or getattr(acc, 'parent_code', None)
                
                # إذا لم يكن الكود في الخريطة، نحاول استنتاج الأب
                if acc.code not in CORRECT_PARENT_MAP:
                    # استنتاج الأب من الكود (مثال: 1105 -> 1100)
                    if len(acc.code) == 4:
                        possible_parent = acc.code[:2] + "00"
                        if possible_parent in CORRECT_PARENT_MAP or any(a.code == possible_parent for a in all_accounts):
                            correct_parent = possible_parent
                        else:
                            possible_parent = acc.code[:1] + "000"
                            if possible_parent in CORRECT_PARENT_MAP or any(a.code == possible_parent for a in all_accounts):
                                correct_parent = possible_parent
                
                # التحقق مما إذا كان التحديث مطلوباً
                current_str = str(current_parent).strip() if current_parent else None
                correct_str = str(correct_parent).strip() if correct_parent else None
                
                if current_str != correct_str:
                    try:
                        account_id = acc._mongo_id or str(acc.id)
                        
                        # تحديث الحساب - استخدام parent_id لأن قاعدة البيانات تستخدمه
                        updated_data = acc.model_copy(update={"parent_id": correct_parent, "parent_code": correct_parent})
                        self.repo.update_account(account_id, updated_data)
                        
                        print(f"✅ تحديث {acc.code} ({acc.name}): {current_parent} -> {correct_parent}")
                        updated_count += 1
                        
                    except Exception as e:
                        error_msg = f"فشل تحديث {acc.code}: {e}"
                        print(f"❌ {error_msg}")
                        errors.append(error_msg)
                else:
                    skipped_count += 1
            
            print("\n" + "=" * 60)
            print(f"✅ تم تحديث {updated_count} حساب")
            print(f"⏭️  تم تخطي {skipped_count} حساب (صحيح بالفعل)")
            if errors:
                print(f"❌ فشل {len(errors)} عملية")
            print("=" * 60)
            
            # إرسال إشارة التحديث
            app_signals.emit_data_changed('accounts')
            
            return {
                "success": len(errors) == 0,
                "updated": updated_count,
                "skipped": skipped_count,
                "errors": errors,
                "message": f"تم تحديث {updated_count} حساب"
            }
            
        except Exception as e:
            error_msg = f"فشل إصلاح الحسابات: {e}"
            print(f"ERROR: [AccountingService] {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "updated": updated_count,
                "skipped": skipped_count,
                "errors": errors + [error_msg],
                "message": error_msg
            }

    def cleanup_all_data(self) -> dict:
        """
        تنظيف شامل للبيانات المكررة وإصلاح العلاقات
        
        يقوم بـ:
        1. تنظيف العملاء المكررين
        2. تنظيف المشاريع المكررة
        3. تنظيف الدفعات المكررة
        4. إصلاح ربط الحسابات بالآباء
        5. تنظيف الحسابات الفرعية للعملاء
        
        Returns:
            dict مع نتائج التنظيف الشامل
        """
        print("=" * 70)
        print("INFO: [AccountingService] ========== بدء التنظيف الشامل ==========")
        print("=" * 70)
        
        results = {}
        
        try:
            # 1. تنظيف التكرارات من Repository
            if hasattr(self.repo, 'cleanup_all_duplicates'):
                print("\n📋 الخطوة 1: تنظيف التكرارات...")
                results['duplicates'] = self.repo.cleanup_all_duplicates()
            
            # 2. إصلاح ربط الحسابات
            print("\n📋 الخطوة 2: إصلاح ربط الحسابات...")
            results['accounts_fix'] = self.fix_accounts_parent_codes()
            
            # 3. تنظيف الحسابات الفرعية للعملاء
            print("\n📋 الخطوة 3: تنظيف الحسابات الفرعية للعملاء...")
            results['client_accounts'] = self.cleanup_client_sub_accounts()
            
            # إرسال إشارات التحديث
            app_signals.emit_data_changed('clients')
            app_signals.emit_data_changed('projects')
            app_signals.emit_data_changed('payments')
            app_signals.emit_data_changed('accounts')
            
            print("\n" + "=" * 70)
            print("INFO: [AccountingService] ========== انتهى التنظيف الشامل ==========")
            print("=" * 70)
            
            return {
                "success": True,
                "results": results,
                "message": "تم التنظيف الشامل بنجاح"
            }
            
        except Exception as e:
            error_msg = f"فشل التنظيف الشامل: {e}"
            print(f"ERROR: [AccountingService] {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "results": results,
                "message": error_msg
            }
