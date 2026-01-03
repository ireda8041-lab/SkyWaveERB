# الملف: core/signals.py
"""
نظام الإشارات (Signals) للتحديث الفوري للواجهة
يستخدم لإرسال إشارات التحديث بين المكونات المختلفة
"""

from PyQt6.QtCore import QObject, pyqtSignal


class AppSignals(QObject):
    """
    كلاس الإشارات العامة للتطبيق - محسّن لجميع أقسام البرنامج
    يستخدم لإرسال إشارات التحديث بين الخدمات والواجهة
    """

    # إشارة عامة لتحديث البيانات
    data_changed = pyqtSignal(str)  # يرسل نوع البيانات المتغيرة

    # إشارات الأقسام الرئيسية
    accounts_changed = pyqtSignal()
    projects_changed = pyqtSignal()
    expenses_changed = pyqtSignal()
    clients_changed = pyqtSignal()
    services_changed = pyqtSignal()
    payments_changed = pyqtSignal()
    tasks_changed = pyqtSignal()
    
    # إشارات جديدة لجميع الأقسام
    invoices_changed = pyqtSignal()
    quotes_changed = pyqtSignal()
    contracts_changed = pyqtSignal()
    hr_changed = pyqtSignal()  # الموارد البشرية
    inventory_changed = pyqtSignal()  # المخزون
    reports_changed = pyqtSignal()  # التقارير
    system_changed = pyqtSignal()  # النظام والإعدادات
    files_changed = pyqtSignal()  # الملفات والمرفقات
    notifications_changed = pyqtSignal()  # الإشعارات
    
    # إشارات محددة
    journal_entry_created = pyqtSignal(str)
    accounting_changed = pyqtSignal()

    # ⚡ إشارات المزامنة
    sync_completed = pyqtSignal(dict)
    sync_failed = pyqtSignal(str)
    realtime_sync_status = pyqtSignal(bool)  # حالة المزامنة الفورية
    
    # 🔔 إشارات الإشعارات التفصيلية
    operation_completed = pyqtSignal(str, str, str)  # (action, entity_type, entity_name)

    def emit_data_changed(self, data_type: str):
        """إرسال إشارة تحديث البيانات - محسّن لجميع الأقسام"""
        self.data_changed.emit(data_type)

        # إرسال إشارات محددة حسب نوع البيانات
        signal_map = {
            'accounts': [self.accounts_changed, self.accounting_changed],
            'accounting': [self.accounting_changed],
            'projects': [self.projects_changed],
            'expenses': [self.expenses_changed, self.accounting_changed],
            'clients': [self.clients_changed],
            'services': [self.services_changed],
            'payments': [self.payments_changed, self.accounting_changed],
            'tasks': [self.tasks_changed],
            'invoices': [self.invoices_changed, self.accounting_changed],
            'quotes': [self.quotes_changed],
            'contracts': [self.contracts_changed],
            'hr': [self.hr_changed],
            'inventory': [self.inventory_changed],
            'reports': [self.reports_changed],
            'system': [self.system_changed],
            'files': [self.files_changed],
            'notifications': [self.notifications_changed]
        }
        
        signals_to_emit = signal_map.get(data_type, [])
        for signal in signals_to_emit:
            signal.emit()

    def emit_journal_entry_created(self, entry_id: str):
        """إرسال إشارة إنشاء قيد محاسبي"""
        self.journal_entry_created.emit(entry_id)
    
    def emit_operation(self, action: str, entity_type: str, entity_name: str):
        """
        إرسال إشارة عملية مكتملة
        action: created, updated, deleted, paid, synced
        entity_type: project, client, expense, payment, account, service, task, etc.
        entity_name: اسم العنصر
        """
        self.operation_completed.emit(action, entity_type, entity_name)
    
    def emit_realtime_sync_status(self, is_connected: bool):
        """إرسال إشارة حالة المزامنة الفورية"""
        self.realtime_sync_status.emit(is_connected)


# إنشاء نسخة واحدة من الإشارات (Singleton)
app_signals = AppSignals()
