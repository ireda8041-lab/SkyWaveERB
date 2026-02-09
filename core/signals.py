# الملف: core/signals.py
"""
نظام الإشارات (Signals) للتحديث الفوري للواجهة
يستخدم لإرسال إشارات التحديث بين المكونات المختلفة

⚡ محسّن لمنع التكرارات والـ Memory Leaks
"""

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class AppSignals(QObject):
    """
    كلاس الإشارات العامة للتطبيق - محسّن لجميع أقسام البرنامج
    يستخدم لإرسال إشارات التحديث بين الخدمات والواجهة

    ⚡ ملاحظة: استخدم emit_data_changed() بدلاً من الإشارات المحددة مباشرة
    لتجنب التكرارات
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
    data_synced = pyqtSignal()  # ⚡ NEW: إشارة بعد سحب البيانات من السيرفر لتحديث الواجهة
    client_logo_loaded = pyqtSignal(str)  # client id or mongo id

    # 🔔 إشارات الإشعارات التفصيلية
    operation_completed = pyqtSignal(str, str, str)  # (action, entity_type, entity_name)

    # ⚡ مرجع لمدير المزامنة (يُعيّن من main.py)
    _sync_manager = None

    # ⚡ منع التكرارات - تتبع آخر إشارة مرسلة
    _last_emitted = {}
    _emit_cooldown_ms = 100  # الحد الأدنى بين الإشارات المتكررة

    @classmethod
    def set_sync_manager(cls, sync_manager):
        """تعيين مدير المزامنة للمزامنة الفورية"""
        cls._sync_manager = sync_manager

    def _should_emit(self, signal_name: str) -> bool:
        """
        ⚡ فحص إذا كان يجب إرسال الإشارة (منع التكرارات)
        """
        import time

        current_time = time.time() * 1000  # بالمللي ثانية

        last_time = self._last_emitted.get(signal_name, 0)
        if current_time - last_time < self._emit_cooldown_ms:
            return False

        self._last_emitted[signal_name] = current_time
        return True

    def emit_data_changed(self, data_type: str):
        """
        إرسال إشارة تحديث البيانات - محسّن لمنع التكرارات

        ⚡ هذه الدالة هي الطريقة المفضلة لإرسال إشارات التحديث
        """
        # ⚡ فحص التكرارات
        if not self._should_emit(f"data_{data_type}"):
            return

        # ⚡ إرسال الإشارة العامة فقط
        self.data_changed.emit(data_type)
        self._emit_table_specific_signals(data_type)

        if self._sync_manager:
            try:
                if hasattr(self._sync_manager, "schedule_instant_sync"):
                    self._sync_manager.schedule_instant_sync(data_type)
                elif hasattr(self._sync_manager, "instant_sync"):
                    QTimer.singleShot(0, lambda: self._sync_manager.instant_sync(data_type))
            except Exception:
                pass

    def _emit_table_specific_signals(self, data_type: str):
        """Emit table-specific UI signals without triggering sync side effects."""
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
        elif data_type == "accounts":
            self.accounts_changed.emit()
        elif data_type == "tasks":
            self.tasks_changed.emit()
        elif data_type == "invoices":
            self.invoices_changed.emit()
        elif data_type == "notifications":
            self.notifications_changed.emit()

        if data_type in ("projects", "expenses", "payments", "invoices", "accounts", "accounting"):
            if self._should_emit("accounting"):
                self.accounting_changed.emit()

    def emit_ui_data_changed(self, data_type: str):
        """
        Emit data-changed signals for UI refresh only.
        Used by pull-from-cloud paths to avoid triggering another instant sync cycle.
        """
        if not self._should_emit(f"ui_data_{data_type}"):
            return
        self.data_changed.emit(data_type)
        self._emit_table_specific_signals(data_type)

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

    def emit_client_logo_loaded(self, client_id: str):
        """إرسال إشارة اكتمال تحميل شعار عميل محدد."""
        self.client_logo_loaded.emit(str(client_id))

    def safe_connect(self, signal, slot, connection_type=None):
        """
        ⚡ ربط آمن للإشارات - يفصل أولاً ثم يربط
        يمنع التكرارات والـ Memory Leaks

        الاستخدام:
            app_signals.safe_connect(app_signals.tasks_changed, self._on_tasks_changed)
        """
        try:
            signal.disconnect(slot)
        except (TypeError, RuntimeError):
            pass  # لم يكن مربوطاً

        if connection_type:
            signal.connect(slot, connection_type)
        else:
            signal.connect(slot)


# إنشاء نسخة واحدة من الإشارات (Singleton)
app_signals = AppSignals()
