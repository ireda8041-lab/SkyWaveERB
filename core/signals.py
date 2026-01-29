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

    # ⚡ مرجع لمدير المزامنة (يُعيّن من main.py)
    _sync_manager = None

    @classmethod
    def set_sync_manager(cls, sync_manager):
        """تعيين مدير المزامنة للمزامنة الفورية"""
        cls._sync_manager = sync_manager

    def emit_data_changed(self, data_type: str):
        """إرسال إشارة تحديث البيانات - محسّن للسرعة"""
        # ⚡ إرسال الإشارة العامة
        self.data_changed.emit(data_type)
        
        # ⚡ إرسال الإشارة المحددة أيضاً للتوافق
        if data_type == "clients":
            self.clients_changed.emit()
        elif data_type == "projects":
            self.projects_changed.emit()
        elif data_type == "expenses":
            self.expenses_changed.emit()
        elif data_type == "payments":
            self.payments_changed.emit()
        elif data_type == "services":
            self.services_changed.emit()
        elif data_type == "accounts" or data_type == "accounting":
            self.accounts_changed.emit()
            self.accounting_changed.emit()
        elif data_type == "tasks":
            self.tasks_changed.emit()
        elif data_type == "invoices":
            self.invoices_changed.emit()

        # ⚡ المزامنة الفورية معطّلة للسرعة
        # المزامنة تتم كل 5 دقائق تلقائياً

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
