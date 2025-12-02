# الملف: services/expense_service.py

from core.repository import Repository
from core.event_bus import EventBus
from core import schemas
from core.signals import app_signals
from typing import List


class ExpenseService:
    """
    قسم المصروفات (Service Layer).
    """

    def __init__(self, repository: Repository, event_bus: EventBus):
        self.repo = repository
        self.bus = event_bus
        print("INFO: قسم المصروفات (ExpenseService) جاهز.")

    def get_all_expenses(self) -> List[schemas.Expense]:
        """ جلب كل المصروفات """
        try:
            return self.repo.get_all_expenses()
        except Exception as e:
            print(f"ERROR: [ExpenseService] فشل جلب المصروفات: {e}")
            return []

    def create_expense(self, expense_data: schemas.Expense) -> schemas.Expense:
        """ 
        إضافة مصروف جديد مع إنشاء قيد محاسبي تلقائي
        
        يجب أن يحتوي expense_data على:
        - account_id: كود حساب المصروف (مثل 5110 للرواتب)
        - payment_account_id: كود حساب الدفع (مثل 1111 للخزينة)
        - amount: المبلغ
        - category: الفئة
        - date: التاريخ
        """
        print(f"INFO: [ExpenseService] استلام طلب إضافة مصروف: {expense_data.category}")
        
        # التحقق من وجود الحسابات المطلوبة
        if not hasattr(expense_data, 'account_id') or not expense_data.account_id:
            raise ValueError("يجب تحديد حساب المصروف (account_id)")
        
        if not hasattr(expense_data, 'payment_account_id') or not expense_data.payment_account_id:
            raise ValueError("يجب تحديد حساب الدفع (payment_account_id)")
        
        try:
            # حفظ المصروف
            created_expense = self.repo.create_expense(expense_data)
            
            # نشر الحدث للمحاسبة (سيتم التعامل معه في accounting_service)
            self.bus.publish('EXPENSE_CREATED', {'expense': created_expense})
            
            # إرسال إشارة التحديث العامة
            app_signals.emit_data_changed('expenses')
            
            print(f"SUCCESS: [ExpenseService] تم إضافة المصروف وإنشاء القيد المحاسبي")
            return created_expense
            
        except Exception as e:
            print(f"ERROR: [ExpenseService] فشل إضافة المصروف: {e}")
            raise

    def update_expense(self, expense_id, expense_data: schemas.Expense) -> bool:
        """ تعديل مصروف موجود """
        print(f"INFO: [ExpenseService] استلام طلب تعديل مصروف: {expense_data.category}")
        try:
            result = self.repo.update_expense(expense_id, expense_data)
            if result:
                self.bus.publish('EXPENSE_UPDATED', expense_data)
            return result
        except Exception as e:
            print(f"ERROR: [ExpenseService] فشل تعديل المصروف: {e}")
            raise

    def delete_expense(self, expense_id) -> bool:
        """ حذف مصروف """
        print(f"INFO: [ExpenseService] استلام طلب حذف مصروف: {expense_id}")
        try:
            result = self.repo.delete_expense(expense_id)
            if result:
                self.bus.publish('EXPENSE_DELETED', {'id': expense_id})
            return result
        except Exception as e:
            print(f"ERROR: [ExpenseService] فشل حذف المصروف: {e}")
            raise
