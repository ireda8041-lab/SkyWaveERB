# الملف: core/notification_bridge.py
"""
جسر الإشعارات - يربط إشارات التطبيق بنظام الإشعارات
"""

import re

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
        "paid": "تم تحصيل",
        "synced": "تمت مزامنة",
        "archived": "تم أرشفة",
        "restored": "تم استعادة",
        "printed": "تم طباعة",
        "voided": "تم إلغاء",
    }
    ACTIVITY_ACTION_NAMES = {
        "created": "إضافة",
        "updated": "تعديل",
        "deleted": "حذف",
        "paid": "تحصيل",
        "synced": "مزامنة",
        "archived": "أرشفة",
        "restored": "استعادة",
        "printed": "طباعة",
        "voided": "إلغاء",
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
        "voided": "🚫",
    }
    MONEY_PATTERN = re.compile(
        r"^\s*(?P<amount>[+-]?\d[\d,]*(?:\.\d+)?)\s*(?:ج\.?\s*م\.?|EGP)\s*(?:[-–—:]\s*(?P<label>.+))?\s*$",
        re.IGNORECASE,
    )

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

            payload = self._build_operation_payload(action, entity_type, entity_name)
            self._record_activity(payload)

            # إرسال الإشعار
            if action == "deleted":
                notify_warning(
                    payload["message"],
                    payload["title"],
                    sync=False,
                    entity_type=entity_type,
                    action=action,
                )
            else:
                notify_success(
                    payload["message"],
                    payload["title"],
                    sync=False,
                    entity_type=entity_type,
                    action=action,
                )

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

    @staticmethod
    def _clean_operation_text(value: str) -> str:
        return " ".join(str(value or "").split()).strip()

    @classmethod
    def _extract_amount_details(
        cls, entity_type: str, entity_name: str
    ) -> tuple[float | None, str]:
        match = cls.MONEY_PATTERN.match(entity_name)
        if not match:
            return None, entity_name
        amount_text = (match.group("amount") or "").replace(",", "").strip()
        try:
            amount_value = float(amount_text)
        except Exception:
            return None, entity_name
        if entity_type == "expense":
            amount_value = -abs(amount_value)
        elif entity_type == "payment":
            amount_value = abs(amount_value)
        label = cls._clean_operation_text(match.group("label") or "")
        return amount_value, label or entity_name

    @classmethod
    def _build_operation_payload(cls, action: str, entity_type: str, entity_name: str) -> dict:
        action_text = cls.ACTION_NAMES.get(action, action)
        entity_text = cls.ENTITY_NAMES.get(entity_type, entity_type)
        icon = cls.ACTION_ICONS.get(action, "📌")
        clean_name = cls._clean_operation_text(entity_name)
        amount, description = cls._extract_amount_details(entity_type, clean_name)
        return {
            "title": f"{icon} {action_text} {entity_text}",
            "message": clean_name,
            "operation_text": f"{cls.ACTIVITY_ACTION_NAMES.get(action, action)} {entity_text}".strip(),
            "description": description or clean_name or entity_text,
            "details": "",
            "amount": amount,
            "action": str(action or "").strip(),
            "entity_type": str(entity_type or "").strip(),
        }

    @staticmethod
    def _record_activity(payload: dict) -> None:
        try:
            from core.repository import Repository

            repo = Repository.get_active_instance()
            if repo is None or not hasattr(repo, "log_activity"):
                return
            repo.log_activity(
                action=payload.get("action", ""),
                entity_type=payload.get("entity_type", ""),
                operation_text=payload.get("operation_text", ""),
                entity_name=payload.get("description", ""),
                details=payload.get("details", ""),
                amount=payload.get("amount"),
            )
        except Exception as e:
            safe_print(f"WARNING: [NotificationBridge] فشل حفظ سجل العملية: {e}")


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

        payload = NotificationBridge._build_operation_payload(action, entity_type, entity_name)
        NotificationBridge._record_activity(payload)
        if action == "deleted":
            notify_warning(
                payload["message"],
                payload["title"],
                sync=False,
                entity_type=entity_type,
                action=action,
            )
        else:
            notify_success(
                payload["message"],
                payload["title"],
                sync=False,
                entity_type=entity_type,
                action=action,
            )
    except Exception as e:
        safe_print(f"ERROR: [NotificationBridge] Fallback notify failed: {e}")
