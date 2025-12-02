# الملف: core/event_bus.py

from collections import defaultdict
from typing import Callable, Any, Dict, List

class EventBus:
    """
    إذاعة المدينة (Event Bus).
    مسؤولة عن توصيل "الأحداث" من "الناشر" (Publisher) 
    إلى "المستمعين" (Listeners/Subscribers).
    """
    
    def __init__(self):
        # هنستخدم dict عشان نخزن "المستمعين" لكل "حدث"
        # شكله هيكون كده:
        # {
        #   'INVOICE_CREATED': [listener1_func, listener2_func],
        #   'EXPENSE_CREATED': [listener3_func]
        # }
        self.listeners: Dict[str, List[Callable]] = defaultdict(list)
        print("INFO: إذاعة المدينة (EventBus) جاهزة للعمل.")

    def subscribe(self, event_name: str, listener_func: Callable):
        """
        الاشتراك في حدث (ظبط الراديو على محطة معينة).
        
        :param event_name: اسم الحدث (المحطة) زي 'INVOICE_CREATED'
        :param listener_func: الدالة (الوظيفة) اللي هتشتغل لما الحدث يحصل
        """
        self.listeners[event_name].append(listener_func)
        print(f"INFO: [EventBus] تم اشتراك مستمع جديد في حدث: {event_name}")

    def publish(self, event_name: str, data: Any = None):
        """
        نشر حدث (بث خبر على الراديو).
        
        :param event_name: اسم الحدث (المحطة)
        :param data: البيانات اللي عايزين نبعتها مع الخبر (زي بيانات الفاتورة)
        """
        if event_name in self.listeners:
            print(f"INFO: [EventBus] جاري نشر حدث: {event_name} مع بيانات: {data}")
            # هيلف على كل المستمعين المسجلين للحدث ده
            for listener_func in self.listeners[event_name]:
                try:
                    # وينفذ الدالة بتاعتهم ويبعتلهم الداتا
                    listener_func(data)
                except Exception as e:
                    # لو مستمع واحد فشل، الباقي يكمل عادي
                    print(f"ERROR: [EventBus] فشل المستمع {listener_func.__name__} في معالجة حدث {event_name}: {e}")


# --- كود للاختبار (اختياري) ---

# (ده مجرد مثال عشان نتأكد إن الإذاعة شغالة)
if __name__ == "__main__":
    
    # 1. تعريف "مستمعين" (وظايف عادية)
    def accountant_listener(invoice_data):
        print(f"  >> المحاسب سمع: تم إنشاء فاتورة جديدة برقم {invoice_data['number']}")
        # (هنا هيتحط كود إنشاء قيد اليومية)

    def notification_listener(invoice_data):
        print(f"  >> قسم الإشعارات سمع: جاري إرسال إيميل للعميل ببيانات الفاتورة {invoice_data['number']}")

    # 2. تشغيل الإذاعة
    bus = EventBus()
    
    # 3. الأقسام بتشترك في الإذاعة
    bus.subscribe('INVOICE_CREATED', accountant_listener)
    bus.subscribe('INVOICE_CREATED', notification_listener)
    bus.subscribe('EXPENSE_CREATED', accountant_listener) # المحاسب بيسمع الفواتير والمصروفات

    print("\n--- الاختبار: نشر فاتورة جديدة ---")
    # 4. قسم الفواتير بينشر "حدث"
    new_invoice = {"number": "INV-001", "total": 5000}
    bus.publish('INVOICE_CREATED', new_invoice)

    print("\n--- الاختبار: نشر مصروف جديد ---")
    # 5. قسم المصروفات بينشر "حدث"
    new_expense = {"category": "إعلانات", "amount": 1000}
    # (قسم الإشعارات مش هيسمع ده، لأنه مشترك في الفواتير بس)
    bus.publish('EXPENSE_CREATED', new_expense)

