# الملف: core/notification_bridge.py
"""
جسر الإشعارات - يربط إشارات التطبيق بنظام الإشعارات
"""

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import QApplication

from core.signals import app_signals

try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            # فشل الطباعة بسبب الترميز
            pass


class NotificationBridge(QObject):
    """جسر يربط إشارات التطبيق بنظام الإشعارات"""

    _instance = None
    _connected = False

    # ترجمة أنواع العناصر
    ENTITY_NAMES = {
        "project": "مشروع",
        "client": "عميل",
        "expense": "مصروف",
        "payment": "دفعة",
        "account": "حساب",
        "service": "خدمة",
        "task": "مهمة",
        "invoice": "فاتورة",
        "journal": "قيد",
        "employee": "موظف",
        "loan": "سلفة",
        "salary": "راتب",
        "attendance": "حضور",
        "leave": "إجازة",
        "projects": "المشاريع",
        "clients": "العملاء",
        "expenses": "المصروفات",
        "payments": "الدفعات",
        "accounts": "الحسابات",
        "services": "الخدمات",
        "tasks": "المهام",
        "employees": "الموظفين",
        "loans": "السلف",
        "salaries": "المرتبات",
    }

    # ترجمة العمليات
    ACTION_NAMES = {
        "created": "تم إضافة",
        "updated": "تم تعديل",
        "deleted": "تم حذف",
        "paid": "تم دفع",
        "synced": "تمت مزامنة",
        "archived": "تم أرشفة",
        "restored": "تم استعادة",
        "printed": "تم طباعة",
    }

    # أيقونات العمليات
    ACTION_ICONS = {
        "created": "✅",
        "updated": "📝",
        "deleted": "🗑️",
        "paid": "💰",
        "synced": "🔄",
        "archived": "📦",
        "restored": "♻️",
        "printed": "🖨️",
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            QObject.__init__(cls._instance)
        return cls._instance

    @classmethod
    def connect(cls):
        """ربط الإشارات بالإشعارات"""
        if cls._connected:
            return

        bridge = cls()
        if QApplication.instance() is None:
            safe_print("WARNING: [NotificationBridge] QApplication غير مُهيأ - تخطي ربط الإشعارات")
            return

        # ربط إشارة العمليات التفصيلية
        app_signals.operation_completed.connect(
            bridge._on_operation, Qt.ConnectionType.QueuedConnection
        )

        # ربط إشارات المزامنة
        app_signals.sync_completed.connect(
            bridge._on_sync_completed, Qt.ConnectionType.QueuedConnection
        )
        app_signals.sync_failed.connect(bridge._on_sync_failed, Qt.ConnectionType.QueuedConnection)

        cls._connected = True
        safe_print("INFO: [NotificationBridge] Connected to app signals")

    def _on_operation(self, action: str, entity_type: str, entity_name: str):
        """معالجة إشارة عملية"""
        try:
            from ui.notification_system import notify_success, notify_warning

            # بناء الرسالة
            action_text = self.ACTION_NAMES.get(action, action)
            entity_text = self.ENTITY_NAMES.get(entity_type, entity_type)
            icon = self.ACTION_ICONS.get(action, "📌")

            message = f"{entity_name}"
            title = f"{icon} {action_text} {entity_text}"

            # إرسال الإشعار
            if action == "deleted":
                notify_warning(message, title, sync=False, entity_type=entity_type, action=action)
            else:
                notify_success(message, title, sync=False, entity_type=entity_type, action=action)

        except Exception as e:
            safe_print(f"ERROR: [NotificationBridge] {e}")

    def _on_sync_completed(self, results: dict):
        """معالجة اكتمال المزامنة"""
        try:
            from ui.notification_system import notify_info

            synced = results.get("synced", 0)
            if synced > 0:
                notify_info(f"تم رفع {synced} عملية", "🔄 مزامنة", sync=False)

        except Exception as e:
            safe_print(f"ERROR: [NotificationBridge] Sync notification failed: {e}")

    def _on_sync_failed(self, error: str):
        """معالجة فشل المزامنة"""
        try:
            from ui.notification_system import notify_error

            notify_error("فشل في المزامنة", "❌ خطأ", sync=False)
        except Exception as e:
            safe_print(f"ERROR: [NotificationBridge] {e}")


def setup_notification_bridge():
    """إعداد جسر الإشعارات"""
    NotificationBridge.connect()


# === دوال مساعدة للإشعارات من أي مكان ===


def notify_operation(action: str, entity_type: str, entity_name: str):
    """
    إرسال إشعار عملية

    Args:
        action: created, updated, deleted, paid, synced, archived, restored, printed
        entity_type: project, client, expense, payment, account, service, task
        entity_name: اسم العنصر

    Example:
        notify_operation('created', 'project', 'مشروع SEO - شركة ABC')
        notify_operation('paid', 'payment', '5000 ج.م')
        notify_operation('deleted', 'client', 'أحمد محمد')
    """
    # Primary path: signal-based bridge (keeps existing sync behavior).
    app_signals.emit_operation(action, entity_type, entity_name)

    # Fallback: if bridge wasn't connected for any reason, still show local toast.
    if NotificationBridge._connected:
        return

    try:
        if QApplication.instance() is None:
            return

        from ui.notification_system import notify_success, notify_warning

        action_text = NotificationBridge.ACTION_NAMES.get(action, action)
        entity_text = NotificationBridge.ENTITY_NAMES.get(entity_type, entity_type)
        icon = NotificationBridge.ACTION_ICONS.get(action, "📌")

        message = f"{entity_name}"
        title = f"{icon} {action_text} {entity_text}"
        if action == "deleted":
            notify_warning(message, title, sync=False, entity_type=entity_type, action=action)
        else:
            notify_success(message, title, sync=False, entity_type=entity_type, action=action)
    except Exception as e:
        safe_print(f"ERROR: [NotificationBridge] Fallback notify failed: {e}")
