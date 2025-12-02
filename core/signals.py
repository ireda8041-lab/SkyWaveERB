# الملف: core/signals.py
"""
نظام الإشارات (Signals) للتحديث الفوري للواجهة
يستخدم لإرسال إشارات التحديث بين المكونات المختلفة
"""

from PyQt6.QtCore import QObject, pyqtSignal


class AppSignals(QObject):
    """
    كلاس الإشارات العامة للتطبيق
    يستخدم لإرسال إشارات التحديث بين الخدمات والواجهة
    """
    
    # إشارة عامة لتحديث البيانات
    data_changed = pyqtSignal(str)  # يرسل نوع البيانات المتغيرة (projects, expenses, accounts, etc.)
    
    # إشارات محددة
    accounts_changed = pyqtSignal()
    projects_changed = pyqtSignal()
    expenses_changed = pyqtSignal()
    clients_changed = pyqtSignal()
    services_changed = pyqtSignal()
    payments_changed = pyqtSignal()
    journal_entry_created = pyqtSignal(str)  # إشارة إنشاء قيد محاسبي
    
    def emit_data_changed(self, data_type: str):
        """إرسال إشارة تحديث البيانات"""
        self.data_changed.emit(data_type)
        
        # إرسال الإشارة المحددة أيضاً
        if data_type == 'accounts':
            self.accounts_changed.emit()
        elif data_type == 'projects':
            self.projects_changed.emit()
        elif data_type == 'expenses':
            self.expenses_changed.emit()
        elif data_type == 'clients':
            self.clients_changed.emit()
        elif data_type == 'services':
            self.services_changed.emit()
        elif data_type == 'payments':
            self.payments_changed.emit()
    
    def emit_journal_entry_created(self, entry_id: str):
        """إرسال إشارة إنشاء قيد محاسبي"""
        self.journal_entry_created.emit(entry_id)


# إنشاء نسخة واحدة من الإشارات (Singleton)
app_signals = AppSignals()
