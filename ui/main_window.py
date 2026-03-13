# pylint: disable=too-many-lines,too-many-positional-arguments
# الملف: ui/main_window.py
from __future__ import annotations

import ctypes
import os
import platform
import threading
import time
import traceback
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.resource_utils import get_resource_path
from core.signals import app_signals
from ui.styles import apply_rtl_alignment_to_all_fields

if TYPE_CHECKING:
    from core import UnifiedSyncManagerV3
    from core.auth_models import PermissionManager, UserRole
    from core.keyboard_shortcuts import KeyboardShortcutManager
    from services.accounting_service import AccountingService
    from services.client_service import ClientService
    from services.expense_service import ExpenseService
    from services.invoice_service import InvoiceService
    from services.notification_service import NotificationService
    from services.project_service import ProjectService
    from services.service_service import ServiceService
    from services.settings_service import SettingsService
    from ui.shortcuts_help_dialog import ShortcutsHelpDialog
    from ui.status_bar_widget import StatusBarWidget

UnifiedSyncManagerV3 = None
PermissionManager = None
UserRole = None
KeyboardShortcutManager = None
ShortcutsHelpDialog = None
StatusBarWidget = None

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


ACCOUNTING_TAB_LABEL = "🗃️ الخزن"
LEGACY_ACCOUNTING_TAB_LABEL = "📊 المحاسبة"
ACCOUNTING_TAB_LABELS = {
    ACCOUNTING_TAB_LABEL,
    LEGACY_ACCOUNTING_TAB_LABEL,
}
TAB_DASHBOARD_LABEL = "🏠 الصفحة الرئيسية"
TAB_PROJECTS_LABEL = "🚀 المشاريع"
TAB_EXPENSES_LABEL = "💳 المصروفات"
TAB_PAYMENTS_LABEL = "💰 الدفعات"
TAB_CLIENTS_LABEL = "👤 العملاء"
TAB_SERVICES_LABEL = "🛠️ الخدمات والباقات"
TAB_TODO_LABEL = "📋 المهام"
TAB_SETTINGS_LABEL = "🔧 الإعدادات"
PROJECT_DUE_DATE_INTERVAL_MS = 86_400_000
PROJECT_DUE_DATE_INITIAL_DELAY_MS = 45_000
DIRECT_TAB_LOAD_LABELS = {
    TAB_DASHBOARD_LABEL,
    TAB_PROJECTS_LABEL,
    TAB_EXPENSES_LABEL,
    TAB_PAYMENTS_LABEL,
    TAB_CLIENTS_LABEL,
    TAB_SERVICES_LABEL,
    TAB_TODO_LABEL,
    TAB_SETTINGS_LABEL,
    *ACCOUNTING_TAB_LABELS,
}


class _ActionConfirmationDialog(QDialog):
    def __init__(self, parent, title: str, message: str):
        super().__init__(parent)
        self._clicked_button = None
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowTitle(title)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(460)
        self.setObjectName("action_confirmation_dialog")

        primary_text, secondary_text = (
            message.split("\n\n", 1) if "\n\n" in message else (message, "")
        )
        confirm_label = "إغلاق الآن"
        cancel_label = "البقاء في البرنامج"
        badge_text = "!"
        accent_color = "#F59E0B"
        if "الخروج" in title:
            confirm_label = "تسجيل الخروج"
            cancel_label = "إلغاء"
            badge_text = "↩"
            accent_color = "#0A6CF1"

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 18, 20, 18)
        root_layout.setSpacing(16)

        card = QFrame()
        card.setObjectName("confirmation_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 18)
        card_layout.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("confirmation_title")
        text_layout.addWidget(title_label)

        primary_label = QLabel(primary_text.strip())
        primary_label.setObjectName("confirmation_primary")
        primary_label.setWordWrap(True)
        text_layout.addWidget(primary_label)

        if secondary_text.strip():
            secondary_label = QLabel(secondary_text.strip())
            secondary_label.setObjectName("confirmation_secondary")
            secondary_label.setWordWrap(True)
            text_layout.addWidget(secondary_label)

        header_layout.addLayout(text_layout, 1)

        badge_label = QLabel(badge_text)
        badge_label.setObjectName("confirmation_badge")
        badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_label.setProperty("accentColor", accent_color)
        header_layout.addWidget(badge_label, 0, Qt.AlignmentFlag.AlignTop)

        card_layout.addLayout(header_layout)

        note_frame = QFrame()
        note_frame.setObjectName("confirmation_note")
        note_layout = QHBoxLayout(note_frame)
        note_layout.setContentsMargins(14, 10, 14, 10)
        note_layout.setSpacing(8)
        note_icon = QLabel("•")
        note_icon.setObjectName("confirmation_note_icon")
        note_text = QLabel("سيتم تنفيذ العملية بشكل آمن دون فقدان البيانات الحالية.")
        note_text.setObjectName("confirmation_note_text")
        note_text.setWordWrap(True)
        note_layout.addWidget(note_icon, 0, Qt.AlignmentFlag.AlignTop)
        note_layout.addWidget(note_text, 1)
        card_layout.addWidget(note_frame)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        self.cancel_button = QPushButton(cancel_label)
        self.cancel_button.setObjectName("cancel_exit_button")
        self.cancel_button.clicked.connect(
            lambda: self._finish_with_button(self.cancel_button, False)
        )

        self.confirm_button = QPushButton(confirm_label)
        self.confirm_button.setObjectName("confirm_exit_button")
        self.confirm_button.clicked.connect(
            lambda: self._finish_with_button(self.confirm_button, True)
        )

        self.cancel_button.setAutoDefault(False)
        self.confirm_button.setDefault(True)
        self.confirm_button.setAutoDefault(True)

        buttons_layout.addWidget(self.cancel_button, 1)
        buttons_layout.addWidget(self.confirm_button, 1)
        card_layout.addLayout(buttons_layout)

        root_layout.addWidget(card)

        self.setStyleSheet(
            f"""
            QDialog#action_confirmation_dialog {{
                background-color: #052045;
            }}
            QFrame#confirmation_card {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0A2E56, stop:1 #072647);
                border: 1px solid #1B4D84;
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
                color: #FFFFFF;
            }}
            QLabel#confirmation_title {{
                font-size: 20px;
                font-weight: 800;
            }}
            QLabel#confirmation_primary {{
                font-size: 15px;
                font-weight: 700;
                color: #F8FBFF;
                line-height: 1.3em;
            }}
            QLabel#confirmation_secondary {{
                font-size: 13px;
                font-weight: 500;
                color: #A7C2E8;
                line-height: 1.35em;
            }}
            QLabel#confirmation_badge {{
                min-width: 42px;
                max-width: 42px;
                min-height: 42px;
                max-height: 42px;
                border-radius: 21px;
                background-color: {accent_color};
                color: #FFFFFF;
                font-size: 20px;
                font-weight: 900;
            }}
            QFrame#confirmation_note {{
                background-color: rgba(7, 58, 109, 0.75);
                border: 1px solid rgba(89, 149, 219, 0.35);
                border-radius: 12px;
            }}
            QLabel#confirmation_note_icon {{
                color: #5FB3FF;
                font-size: 18px;
                font-weight: 900;
            }}
            QLabel#confirmation_note_text {{
                color: #C9DBF2;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton {{
                min-height: 46px;
                border-radius: 12px;
                border: none;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 800;
            }}
            QPushButton#confirm_exit_button {{
                background-color: #0A6CF1;
                color: #FFFFFF;
            }}
            QPushButton#confirm_exit_button:hover {{
                background-color: #2D84F5;
            }}
            QPushButton#cancel_exit_button {{
                background-color: #14365F;
                color: #EAF3FF;
                border: 1px solid #2A5B95;
            }}
            QPushButton#cancel_exit_button:hover {{
                background-color: #1D497D;
            }}
            """
        )

    def _finish_with_button(self, button, accepted: bool):
        self._clicked_button = button
        if accepted:
            self.accept()
        else:
            self.reject()

    def showEvent(self, event):  # pylint: disable=invalid-name
        super().showEvent(event)
        QTimer.singleShot(0, self._ensure_frontmost)

    def _ensure_frontmost(self):
        try:
            if self.isMinimized():
                self.showNormal()
        except Exception:
            pass
        try:
            self.raise_()
        except Exception:
            pass
        try:
            self.activateWindow()
        except Exception:
            pass
        try:
            self.confirm_button.setFocus()
        except Exception:
            pass

    def buttons(self):
        return [self.cancel_button, self.confirm_button]

    def clickedButton(self):
        return self._clicked_button


class MainWindow(QMainWindow):
    """
    (معدلة) الشاشة الرئيسية (بتابات المحاسبة والمصروفات الجديدة)
    """

    # إشارات للمزامنة
    sync_completed = pyqtSignal(dict)

    def __init__(
        self,
        current_user,  # المستخدم الحالي
        settings_service: SettingsService,
        accounting_service: AccountingService,
        client_service: ClientService,
        service_service: ServiceService,
        expense_service: ExpenseService,
        invoice_service: InvoiceService,
        project_service: ProjectService,
        notification_service: NotificationService | None = None,
        printing_service=None,
        template_service=None,
        export_service=None,
        smart_scan_service=None,
        sync_manager=None,  # 🔥 نظام المزامنة الموحد
    ):
        super().__init__()

        self._connection_check_timer = None
        self._allow_close = False
        self._closing_in_progress = False
        self._close_confirmation_pending = False
        self._quit_requested = False
        self._last_close_request_ts = 0.0
        self._last_close_event_log_ts = 0.0
        self._exit_confirmation_open = False

        # إخفاء النافذة مؤقتاً لمنع الشاشة البيضاء
        self.setWindowOpacity(0.0)

        # تخصيص شريط العنوان
        self.setup_title_bar()

        # (تخزين الأقسام والمستخدم)
        self.current_user = current_user
        self.settings_service = settings_service
        self.accounting_service = accounting_service
        self.client_service = client_service
        self.service_service = service_service
        self.expense_service = expense_service
        self.invoice_service = invoice_service
        self.project_service = project_service
        self.notification_service = notification_service
        self.printing_service = printing_service
        self.template_service = template_service
        self.export_service = export_service
        self.smart_scan_service = smart_scan_service
        self.sync_manager = sync_manager  # 🔥 نظام المزامنة الموحد

        # 🔥 الحصول على Repository للاتصال المباشر
        self.repository = self.accounting_service.repo

        role_display = (
            current_user.role.value
            if hasattr(current_user.role, "value")
            else str(current_user.role)
        )
        self.setWindowTitle(
            f"Sky Wave ERP - {current_user.full_name or current_user.username} ({role_display})"
        )

        # تعيين أيقونة النافذة
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # الحصول على حجم الشاشة المتاح
        primary_screen = QApplication.primaryScreen()
        if primary_screen is None:
            raise RuntimeError("No primary screen available")
        screen_geometry = primary_screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # تعيين الحد الأدنى للنافذة بناءً على حجم الشاشة
        min_width = min(1024, max(800, screen_width - 80))
        min_height = min(600, max(500, screen_height - 80))
        self.setMinimumSize(QSize(min_width, min_height))

        # تعيين حجم النافذة بنسبة 90% من حجم الشاشة (أكثر راحة)
        window_width = int(screen_width * 0.9)
        window_height = int(screen_height * 0.9)

        # توسيط النافذة في الشاشة
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        self.setGeometry(x, y, window_width, window_height)

        # يمكن للمستخدم تكبير النافذة إذا أراد
        # self.showMaximized()  # معطل افتراضياً لراحة أكبر

        # جعل النافذة قابلة لتغيير الحجم بشكل ديناميكي
        self.setWindowFlags(Qt.WindowType.Window)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تم إزالة الهيدر - زر المزامنة موجود في الـ Status Bar

        # ربط signal اكتمال المزامنة
        self.sync_completed.connect(self._on_full_sync_completed)

        # إعداد فحص مؤجل لمواعيد استحقاق المشاريع لتخفيف حمل بدء التشغيل.
        self.project_check_timer = QTimer(self)
        self.project_check_timer.setInterval(PROJECT_DUE_DATE_INTERVAL_MS)
        self.project_check_timer.timeout.connect(self._check_project_due_dates_background)
        self._project_due_dates_bootstrap_timer = QTimer(self)
        self._project_due_dates_bootstrap_timer.setSingleShot(True)
        self._project_due_dates_bootstrap_timer.timeout.connect(
            self._run_initial_project_due_dates_check
        )
        self._project_due_dates_initial_run_done = False
        if self.notification_service is not None:
            self._start_project_due_date_checks()

        # إعداد اختصارات لوحة المفاتيح
        global KeyboardShortcutManager
        if KeyboardShortcutManager is None:
            from core.keyboard_shortcuts import KeyboardShortcutManager as _KeyboardShortcutManager

            KeyboardShortcutManager = _KeyboardShortcutManager

        self.shortcuts_manager = KeyboardShortcutManager(self)
        self.shortcuts_manager.setup_shortcuts()
        self._connect_shortcuts()

        # --- 1. إنشاء الـ Tab Widget ---
        self.tabs = QTabWidget()

        # ⚡ جعل التابات تتمدد لتملأ العرض تلقائياً
        self.tabs.tabBar().setExpanding(True)
        self.tabs.setUsesScrollButtons(False)  # إيقاف أزرار التمرير لأن التابات تتمدد
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)  # عدم اقتطاع النص
        self._tabs_compact = None

        # جعل الـ tabs متجاوبة مع حجم الشاشة بشكل كامل
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tabs.setMinimumSize(QSize(400, 300))  # حد أدنى صغير للتجاوب

        # تحسين شكل التابات - تصميم احترافي حديث متجاوب
        self.tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: none;
                background-color: #001A3A;
            }

            QTabBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0D3461, stop:1 #052045);
                qproperty-drawBase: 0;
                border-bottom: 1px solid #1E3A5F;
            }

            QTabBar::tab {
                background-color: transparent;
                color: #7A9BC5;
                padding: 12px 15px;
                margin: 0px;
                border: none;
                border-right: 1px solid rgba(30, 58, 95, 0.5);
                font-size: 12px;
                font-weight: 600;
            }

            QTabBar::tab:hover {
                color: #FFFFFF;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(10, 108, 241, 0.25), stop:1 rgba(10, 108, 241, 0.1));
            }

            QTabBar::tab:selected {
                color: #FFFFFF;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0A6CF1, stop:1 #0550B8);
                border-right: 1px solid #0A6CF1;
            }

            QTabBar::tab:first {
                border-left: none;
            }

            QTabBar::tab:last {
                border-right: none;
            }

            /* أزرار التمرير للتابات */
            QTabBar::scroller {
                width: 35px;
            }

            QTabBar QToolButton {
                background-color: #0D3461;
                border: 1px solid #1E3A5F;
                border-radius: 4px;
                color: white;
                padding: 5px;
                font-size: 14px;
            }

            QTabBar QToolButton:hover {
                background-color: #0A6CF1;
            }

            QTabBar::tab:first {
                border-left: none;
            }

            QTabBar::tab:last {
                border-right: none;
            }
        """
        )

        self._apply_tabs_responsive()

        self._init_tab_factories()

        # تحديث template_service في printing_service إذا كان موجوداً
        if self.printing_service and self.template_service:
            self.printing_service.template_service = self.template_service

        # --- 3. إنشاء كل التابات مرة واحدة (بدون Lazy Loading لتجنب التجميد) ---
        self._tabs_initialized: dict[int, bool] = {}
        self._tab_data_loaded: dict[str, bool] = {}
        # ⚡ Lazy Refresh: تتبع التابات التي تحتاج تحديث
        self.pending_refreshes: dict[str, bool] = {}
        self._deferred_refresh_timers: dict[str, QTimer] = {}
        # ⚡ تجميع طلبات تحديث الجداول لتقليل ضغط الإشارات المتكررة
        self._queued_table_refreshes: set[str] = set()
        self._table_refresh_timer = QTimer(self)
        self._table_refresh_timer.setSingleShot(True)
        self._table_refresh_timer.timeout.connect(self._flush_enqueued_table_refreshes)
        # Tables with dedicated direct signals (clients_changed, etc.).
        # Ignore duplicate handling through generic data_changed for these tables.
        self._tables_with_direct_refresh_signals = {
            "clients",
            "projects",
            "expenses",
            "payments",
            "services",
            "accounts",
            "accounting",
            "tasks",
            # Notifications are handled by dedicated notification workers/toasts.
            "notifications",
        }
        self._last_sync_ui_refresh_at = 0.0
        # Keep UI responsive under bursty sync/realtime events.
        self._sync_ui_refresh_cooldown_seconds = 2.0

        # ⚡ إنشاء هيكل التابات مع تحميل مرحلي للتبويبات الثقيلة
        self._create_all_tabs()

        # تطبيق الصلاحيات حسب دور المستخدم (بعد إنشاء كل التابات)
        self.apply_permissions()

        global StatusBarWidget
        if StatusBarWidget is None:
            from ui.status_bar_widget import StatusBarWidget as _StatusBarWidget

            StatusBarWidget = _StatusBarWidget

        self.status_bar = StatusBarWidget()

        # تعيين المستخدم الحالي في شريط الحالة
        self.status_bar.set_current_user(self.current_user)

        # ⚡ ربط sync_manager (UnifiedSyncManager) بشريط الحالة
        if self.sync_manager:
            # ربط إشارات المزامنة الموحدة
            if hasattr(self.sync_manager, "connection_changed"):
                self.sync_manager.connection_changed.connect(
                    lambda online: self.status_bar.update_sync_status(
                        "synced" if online else "offline"
                    )
                )
            if hasattr(self.sync_manager, "sync_started"):
                self.sync_manager.sync_started.connect(
                    lambda: self.status_bar.update_sync_status("syncing")
                )
            if hasattr(self.sync_manager, "sync_completed"):
                self.sync_manager.sync_completed.connect(
                    lambda result: self.status_bar.update_sync_status(
                        "synced" if result.get("success") else "error"
                    )
                )
            if hasattr(self.sync_manager, "sync_progress"):
                self.sync_manager.sync_progress.connect(self.status_bar.update_sync_progress)

        # ⚡ تحديث حالة الاتصال الأولية بعد 5 ثواني (لإعطاء MongoDB وقت للاتصال)
        QTimer.singleShot(5000, self._update_initial_connection_status)

        app_signals.safe_connect(
            app_signals.realtime_sync_status,
            self._on_realtime_sync_status_changed,
            Qt.ConnectionType.QueuedConnection,
        )

        # 🔥 ربط إشارات تحديث الواجهة الفورية (INSTANT UI REFRESH)
        app_signals.safe_connect(
            app_signals.clients_changed,
            self._refresh_clients_tab,
            Qt.ConnectionType.QueuedConnection,
        )
        app_signals.safe_connect(
            app_signals.projects_changed,
            self._refresh_projects_tab,
            Qt.ConnectionType.QueuedConnection,
        )
        app_signals.safe_connect(
            app_signals.expenses_changed,
            self._refresh_expenses_tab,
            Qt.ConnectionType.QueuedConnection,
        )
        app_signals.safe_connect(
            app_signals.payments_changed,
            self._refresh_payments_tab,
            Qt.ConnectionType.QueuedConnection,
        )
        app_signals.safe_connect(
            app_signals.services_changed,
            self._refresh_services_tab,
            Qt.ConnectionType.QueuedConnection,
        )
        app_signals.safe_connect(
            app_signals.accounting_changed,
            self._refresh_accounting_tab,
            Qt.ConnectionType.QueuedConnection,
        )
        app_signals.safe_connect(
            app_signals.tasks_changed,
            self._refresh_tasks_tab,
            Qt.ConnectionType.QueuedConnection,
        )

        # 🔥🔥🔥 الاتصال المباشر بـ app_signals (CRITICAL FIX!)
        # استخدام app_signals مباشرة لأن Repository ليس QObject
        # ⚡ ملاحظة: الإشارات المحددة (clients_changed, etc.) مربوطة أعلاه
        # لذلك نربط data_changed فقط للجداول غير المغطاة
        app_signals.safe_connect(
            app_signals.data_changed,
            self.handle_data_change,
            Qt.ConnectionType.QueuedConnection,
        )
        safe_print("✅ تم ربط app_signals.data_changed مباشرة بالواجهة!")

        # ربط زر تسجيل الخروج
        self.status_bar.logout_requested.connect(self._handle_logout)

        # ربط زرار المزامنة في شريط الحالة
        self.status_bar.full_sync_requested.connect(self._on_full_sync_clicked)

        # إنشاء container widget للـ tabs
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(5, 5, 5, 5)
        central_layout.setSpacing(0)

        # إضافة الـ tabs
        central_layout.addWidget(self.tabs, 1)

        # إضافة الـ central widget
        self.setCentralWidget(central_widget)

        # جعل الـ central widget متجاوب بشكل كامل

        central_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        central_widget.setMinimumSize(QSize(400, 300))

        # ✅ إضافة شريط الحالة في الأسفل باستخدام QStatusBar

        qt_status_bar = QStatusBar()
        qt_status_bar.setFixedHeight(60)  # تطابق مع ارتفاع StatusBarWidget
        qt_status_bar.setSizeGripEnabled(False)  # إزالة المقبض

        # إضافة StatusBarWidget بحيث يملأ العرض كاملاً
        self.status_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        qt_status_bar.addPermanentWidget(self.status_bar, 1)
        self.setStatusBar(qt_status_bar)

        # ✅ التأكد من أن الشريط السفلي دائمًا مرئي
        self.status_bar.setVisible(True)
        qt_status_bar.setVisible(True)

        # ✅ إزالة الحواف والهوامش لجعل البار كامل
        qt_status_bar.setContentsMargins(0, 0, 0, 0)
        qt_status_bar.layout().setContentsMargins(0, 0, 0, 0)
        qt_status_bar.layout().setSpacing(0)

        # === شاشة التحميل المتراكبة - معطلة لتجنب التجميد ===
        # البيانات تحمل في الخلفية بدون الحاجة لشاشة تحميل
        self.loading_overlay = None

        # --- 4. إعداد المزامنة (إذا لم يتم تمريرها) ---
        if not self.sync_manager:
            global UnifiedSyncManagerV3
            if UnifiedSyncManagerV3 is None:
                from core import UnifiedSyncManagerV3 as _UnifiedSyncManagerV3

                UnifiedSyncManagerV3 = _UnifiedSyncManagerV3

            self.sync_manager = UnifiedSyncManagerV3(self.accounting_service.repo)

        # إعداد المزامنة التلقائية كل 10 دقائق
        self.setup_auto_sync()

        # --- 4. تحميل البيانات في الخلفية ---
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # ⚡ تحميل البيانات فوراً (بدون تأخير)
        QTimer.singleShot(100, self._load_initial_data_safely)

    def _create_all_tabs(self):
        """تهيئة التبويبات بشكل مرحلي لتقليل زمن فتح الواجهة."""
        safe_print("INFO: [MainWindow] ⚡ تجهيز هيكل التبويبات بتحميل مرحلي...")

        tab_order = [
            TAB_DASHBOARD_LABEL,
            TAB_PROJECTS_LABEL,
            TAB_EXPENSES_LABEL,
            TAB_PAYMENTS_LABEL,
            TAB_CLIENTS_LABEL,
            TAB_SERVICES_LABEL,
            ACCOUNTING_TAB_LABEL,
            TAB_TODO_LABEL,
            TAB_SETTINGS_LABEL,
        ]

        for tab_name in tab_order:
            if tab_name == TAB_DASHBOARD_LABEL:
                self.tabs.addTab(self._build_real_tab(tab_name), tab_name)
                self._tab_data_loaded.setdefault(tab_name, False)
                continue

            placeholder = self._create_placeholder_tab(
                title=tab_name,
                message="يتم تجهيز هذا القسم عند أول فتح لتقليل وقت تشغيل البرنامج.",
            )
            self.tabs.addTab(placeholder, tab_name)
            self._tab_data_loaded.setdefault(tab_name, False)

        safe_print("INFO: [MainWindow] ⚡ تم تجهيز هيكل التبويبات")

    def _init_tab_factories(self):
        self._tab_attribute_names = {
            TAB_DASHBOARD_LABEL: "dashboard_tab",
            TAB_PROJECTS_LABEL: "projects_tab",
            TAB_EXPENSES_LABEL: "expense_tab",
            TAB_PAYMENTS_LABEL: "payments_tab",
            TAB_CLIENTS_LABEL: "clients_tab",
            TAB_SERVICES_LABEL: "services_tab",
            ACCOUNTING_TAB_LABEL: "accounting_tab",
            TAB_TODO_LABEL: "todo_tab",
            TAB_SETTINGS_LABEL: "settings_tab",
        }
        self._tab_factories = {
            TAB_DASHBOARD_LABEL: self._create_dashboard_tab_widget,
            TAB_PROJECTS_LABEL: self._create_projects_tab_widget,
            TAB_EXPENSES_LABEL: self._create_expenses_tab_widget,
            TAB_PAYMENTS_LABEL: self._create_payments_tab_widget,
            TAB_CLIENTS_LABEL: self._create_clients_tab_widget,
            TAB_SERVICES_LABEL: self._create_services_tab_widget,
            ACCOUNTING_TAB_LABEL: self._create_accounting_tab_widget,
            TAB_TODO_LABEL: self._create_todo_tab_widget,
            TAB_SETTINGS_LABEL: self._create_settings_tab_widget,
        }

    def _create_placeholder_tab(self, title: str, message: str) -> QWidget:
        placeholder = QWidget()
        placeholder.setProperty("_is_lazy_placeholder", True)
        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "color: #FFFFFF; font-size: 22px; font-weight: 700; background: transparent;"
        )
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(
            "color: #7FA2D4; font-size: 13px; font-weight: 500; background: transparent;"
        )

        layout.addWidget(title_label)
        layout.addWidget(message_label)
        layout.addStretch(1)
        return placeholder

    def _create_dashboard_tab_widget(self):
        from ui.dashboard_tab import DashboardTab

        return DashboardTab(self.accounting_service)

    def _create_projects_tab_widget(self):
        from ui.project_manager import ProjectManagerTab

        return ProjectManagerTab(
            self.project_service,
            self.client_service,
            self.service_service,
            self.accounting_service,
            self.expense_service,
            self.printing_service,
            template_service=self.template_service,
        )

    def _create_expenses_tab_widget(self):
        from ui.expense_manager import ExpenseManagerTab

        return ExpenseManagerTab(
            self.expense_service,
            self.accounting_service,
            self.project_service,
        )

    def _create_payments_tab_widget(self):
        from ui.payments_manager import PaymentsManagerTab

        return PaymentsManagerTab(
            project_service=self.project_service,
            accounting_service=self.accounting_service,
            client_service=self.client_service,
            current_user=self.current_user,
        )

    def _create_clients_tab_widget(self):
        from ui.client_manager import ClientManagerTab

        return ClientManagerTab(self.client_service)

    def _create_services_tab_widget(self):
        from ui.service_manager import ServiceManagerTab

        return ServiceManagerTab(self.service_service)

    def _create_accounting_tab_widget(self):
        from ui.accounting_manager import AccountingManagerTab

        return AccountingManagerTab(
            self.expense_service,
            self.accounting_service,
            self.project_service,
        )

    def _create_todo_tab_widget(self):
        from ui.todo_manager import TaskService, TodoManagerWidget

        TaskService._repository = self.accounting_service.repo
        TaskService._instance = None
        TaskService(repository=self.accounting_service.repo, load_now=False)
        return TodoManagerWidget(
            project_service=self.project_service, client_service=self.client_service
        )

    def _create_settings_tab_widget(self):
        from ui.settings_tab import SettingsTab

        return SettingsTab(
            self.settings_service,
            repository=self.accounting_service.repo,
            current_user=self.current_user,
        )

    def _find_tab_index_by_name(self, tab_name: str) -> int:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == tab_name:
                return index
        return -1

    def _build_real_tab(self, tab_name: str):
        attr_name = self._tab_attribute_names.get(tab_name)
        existing_tab = getattr(self, attr_name, None) if attr_name else None
        if existing_tab is not None:
            return existing_tab

        factory = self._tab_factories.get(tab_name)
        if factory is None:
            return None

        widget = factory()
        if attr_name:
            setattr(self, attr_name, widget)
        try:
            apply_rtl_alignment_to_all_fields(widget)
        except Exception as rtl_error:
            safe_print(f"WARNING: [MainWindow] تعذر تطبيق RTL على التاب {tab_name}: {rtl_error}")
        return widget

    def _ensure_real_tab_for_index(self, index: int):
        if index < 0 or index >= self.tabs.count():
            return None

        tab_name = self.tabs.tabText(index)
        attr_name = self._tab_attribute_names.get(tab_name)
        existing_widget = getattr(self, attr_name, None) if attr_name else None
        current_widget = self.tabs.widget(index)

        if current_widget is not None and not bool(current_widget.property("_is_lazy_placeholder")):
            if attr_name and existing_widget is None:
                setattr(self, attr_name, current_widget)
            return current_widget

        real_widget = self._build_real_tab(tab_name)
        if real_widget is None:
            return current_widget

        if current_widget is real_widget:
            return real_widget

        was_current = self.tabs.currentIndex() == index
        self.tabs.blockSignals(True)
        self.tabs.removeTab(index)
        self.tabs.insertTab(index, real_widget, tab_name)
        self.tabs.blockSignals(False)

        if current_widget is not None:
            current_widget.deleteLater()

        if was_current:
            self.tabs.setCurrentIndex(index)

        return real_widget

    def _activate_tab(self, tab_name: str):
        tab_index = self._find_tab_index_by_name(tab_name)
        if tab_index < 0:
            return None
        self._ensure_real_tab_for_index(tab_index)
        self.tabs.setCurrentIndex(tab_index)
        return self.tabs.widget(tab_index)

    def _ensure_current_tab_widget(self):
        return self._ensure_real_tab_for_index(self.tabs.currentIndex())

    def attach_deferred_services(
        self,
        *,
        notification_service=None,
        printing_service=None,
        template_service=None,
        export_service=None,
    ):
        """ربط الخدمات الثانوية بعد ظهور النافذة لتقليل زمن الفتح."""
        if notification_service is not None:
            self.notification_service = notification_service
        if template_service is not None:
            self.template_service = template_service
        if printing_service is not None:
            self.printing_service = printing_service
        if export_service is not None:
            self.export_service = export_service

        if self.printing_service and self.template_service:
            self.printing_service.template_service = self.template_service

        projects_tab = getattr(self, "projects_tab", None)
        if projects_tab is not None:
            projects_tab.printing_service = self.printing_service
            projects_tab.template_service = self.template_service

        if notification_service is not None:
            MainWindow._start_project_due_date_checks(self)

    def _start_project_due_date_checks(
        self, *, initial_delay_ms: int = PROJECT_DUE_DATE_INITIAL_DELAY_MS
    ) -> None:
        """ابدأ فحص استحقاقات المشاريع بعد استقرار الواجهة وربط الخدمات الثانوية."""
        if self.notification_service is None:
            return

        if not self.project_check_timer.isActive():
            self.project_check_timer.start()

        if self._project_due_dates_initial_run_done:
            return

        if not self._project_due_dates_bootstrap_timer.isActive():
            self._project_due_dates_bootstrap_timer.start(max(1000, int(initial_delay_ms)))

    def _run_initial_project_due_dates_check(self) -> None:
        if self._project_due_dates_initial_run_done:
            return
        self._project_due_dates_initial_run_done = True
        self._check_project_due_dates_background()

    def on_tab_changed(self, index):
        """⚡ تحميل بيانات التاب عند التنقل - محسّن للسرعة"""
        try:
            if index < 0:
                return

            self._ensure_real_tab_for_index(index)
            tab_name = self.tabs.tabText(index)

            # ⚡ تحميل البيانات إذا لم تكن محملة أو تحتاج تحديث (Lazy Refresh)
            needs_refresh = self.pending_refreshes.get(tab_name, False)
            if not self._tab_data_loaded.get(tab_name, False) or needs_refresh:
                # ⚡ إعادة تعيين علامة التحديث فوراً لمنع التكرار
                if tab_name in self.pending_refreshes:
                    del self.pending_refreshes[tab_name]

                # ⚡ إبطال cache قبل التحميل لأنه كان pending
                self._invalidate_tab_cache(tab_name)

                # ⚡ تحميل البيانات
                self._do_load_tab_data_safe(tab_name)

        except Exception as e:
            safe_print(f"ERROR: خطأ في تغيير التاب: {e}")

    # ⚡ Cache لتتبع التابات المحملة (لتجنب إعادة التحميل)
    # Note: This is a class-level cache, initialized in __init__

    def _load_tab_data_safely(self, tab_name: str, force_reload: bool = False):
        """⚡ تحميل بيانات التاب في الخلفية (لتجنب التجميد)"""
        # ⚡ تجنب إعادة التحميل إذا البيانات محملة بالفعل
        if not force_reload and self._tab_data_loaded.get(tab_name, False):
            return

        # ⚡ تحميل البيانات بعد 50ms لإعطاء الواجهة فرصة للظهور
        QTimer.singleShot(50, lambda: self._do_load_tab_data(tab_name))

    def _do_load_tab_data_safe(self, tab_name: str):
        """تحميل بيانات التاب بأخف مسار ممكن بدون تكرار تحميلات شكلية."""
        if MainWindow._supports_direct_tab_load(tab_name):
            self._refresh_in_progress[f"tab_{tab_name}"] = True
            QTimer.singleShot(0, lambda t=tab_name: MainWindow._run_direct_tab_load(self, t))
            return

        # الحصول على DataLoader
        from core.data_loader import get_data_loader

        data_loader = get_data_loader()

        # تحديد دالة التحميل حسب التاب
        def get_load_function():
            if tab_name == TAB_DASHBOARD_LABEL:
                return self._load_dashboard_data
            elif tab_name == TAB_PROJECTS_LABEL:
                return self._load_projects_data
            elif tab_name == TAB_EXPENSES_LABEL:
                return self._load_expenses_data
            elif tab_name == TAB_PAYMENTS_LABEL:
                return self._load_payments_data
            elif tab_name == TAB_CLIENTS_LABEL:
                return self._load_clients_data
            elif tab_name == TAB_SERVICES_LABEL:
                return self._load_services_data
            elif tab_name in ACCOUNTING_TAB_LABELS:
                return self._load_accounting_data
            elif tab_name == TAB_TODO_LABEL:
                return self._load_tasks_data
            elif tab_name == TAB_SETTINGS_LABEL:
                return self._load_settings_data
            return None

        load_func = get_load_function()
        if not load_func:
            return

        def on_success(data):
            """معالج النجاح - تحديث الواجهة"""
            try:
                self._update_tab_ui(tab_name, data)
                self._tab_data_loaded[tab_name] = True
            except Exception as e:
                safe_print(f"ERROR: فشل تحديث واجهة التاب {tab_name}: {e}")
            finally:
                MainWindow._finish_tab_load_cycle(self, tab_name)

        def on_error(error_msg):
            """معالج الخطأ"""
            safe_print(f"ERROR: فشل تحميل بيانات التاب {tab_name}: {error_msg}")
            MainWindow._finish_tab_load_cycle(self, tab_name)

        # تحميل البيانات في الخلفية
        self._refresh_in_progress[f"tab_{tab_name}"] = True
        data_loader.load_async(
            operation_name=f"load_{tab_name}",
            load_function=load_func,
            on_success=on_success,
            on_error=on_error,
            use_thread_pool=True,
        )

    @staticmethod
    def _supports_direct_tab_load(tab_name: str) -> bool:
        return tab_name in DIRECT_TAB_LOAD_LABELS

    def _run_direct_tab_load(self, tab_name: str) -> None:
        try:
            MainWindow._update_tab_ui(self, tab_name, {"type": "direct"})
            self._tab_data_loaded[tab_name] = True
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل التاب {tab_name} مباشرة: {e}")
        finally:
            MainWindow._finish_tab_load_cycle(self, tab_name)

    def _finish_tab_load_cycle(self, tab_name: str) -> None:
        self._refresh_in_progress[f"tab_{tab_name}"] = False
        if not self.pending_refreshes.pop(tab_name, False):
            return

        tabs = getattr(self, "tabs", None)
        if tabs is None:
            self.pending_refreshes[tab_name] = True
            return

        current_tab = tabs.tabText(tabs.currentIndex())
        if current_tab == tab_name:
            QTimer.singleShot(220, lambda t=tab_name: self._do_load_tab_data_safe(t))
        else:
            self.pending_refreshes[tab_name] = True

    # ===== دوال تحميل البيانات (تعمل في الخلفية) =====

    def _load_dashboard_data(self):
        """تحميل بيانات الداشبورد"""
        return {"type": "dashboard"}

    def _load_projects_data(self):
        """تحميل بيانات المشاريع"""
        if hasattr(self, "projects_tab"):
            self.projects_tab.service_service = self.service_service
            self.projects_tab.accounting_service = self.accounting_service
        return {"type": "projects"}

    def _load_expenses_data(self):
        """تحميل بيانات المصروفات"""
        return {"type": "expenses"}

    def _load_payments_data(self):
        """تحميل بيانات الدفعات"""
        return {"type": "payments"}

    def _load_clients_data(self):
        """تحميل بيانات العملاء"""
        return {"type": "clients"}

    def _load_services_data(self):
        """تحميل بيانات الخدمات"""
        return {"type": "services"}

    def _load_accounting_data(self):
        """تحميل بيانات المحاسبة"""
        if hasattr(self, "accounting_tab"):
            self.accounting_tab.project_service = self.project_service
        return {"type": "accounting"}

    def _load_tasks_data(self):
        """تحميل بيانات المهام"""
        return {"type": "tasks"}

    def _load_settings_data(self):
        """تحميل بيانات الإعدادات"""
        return {"type": "settings"}

    def _update_tab_ui(self, tab_name: str, data: dict):
        """تحديث واجهة التاب بعد تحميل البيانات (يعمل على main thread)"""
        try:
            if tab_name == TAB_DASHBOARD_LABEL:
                if hasattr(self, "dashboard_tab"):
                    self.dashboard_tab.refresh_data()
            elif tab_name == TAB_PROJECTS_LABEL:
                if hasattr(self, "projects_tab"):
                    self.projects_tab.service_service = self.service_service
                    self.projects_tab.accounting_service = self.accounting_service
                    self.projects_tab.load_projects_data()
            elif tab_name == TAB_EXPENSES_LABEL:
                if hasattr(self, "expense_tab"):
                    self.expense_tab.load_expenses_data()
            elif tab_name == TAB_PAYMENTS_LABEL:
                if hasattr(self, "payments_tab"):
                    self.payments_tab.load_payments_data()
            elif tab_name == TAB_CLIENTS_LABEL:
                if hasattr(self, "clients_tab"):
                    self.clients_tab.load_clients_data()
            elif tab_name == TAB_SERVICES_LABEL:
                if hasattr(self, "services_tab"):
                    self.services_tab.load_services_data()
            elif tab_name in ACCOUNTING_TAB_LABELS:
                if hasattr(self, "accounting_tab"):
                    self.accounting_tab.project_service = self.project_service
                    self.accounting_tab.load_accounts_data()
            elif tab_name == TAB_TODO_LABEL:
                if hasattr(self, "todo_tab"):
                    self.todo_tab.load_tasks()
            elif tab_name == TAB_SETTINGS_LABEL:
                if hasattr(self, "settings_tab"):
                    try:
                        self.settings_tab.load_active_subtab_data(force_reload=False)
                    except Exception as e:
                        safe_print(f"WARNING: فشل تحديث تبويب الإعدادات الحالي: {e}")

        except Exception as e:
            safe_print(f"ERROR: فشل تحديث واجهة التاب {tab_name}: {e}")
            traceback.print_exc()

    def _do_load_tab_data(self, tab_name: str):
        """⚡ دالة قديمة للتوافق - تستدعي الدالة الجديدة"""
        self._do_load_tab_data_safe(tab_name)

    def _load_initial_data_safely(self):
        """⚡ تحميل البيانات الأولية بسرعة"""
        try:
            self._activate_tab(TAB_DASHBOARD_LABEL)
            self._do_load_tab_data_safe(TAB_DASHBOARD_LABEL)
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل البيانات الأولية: {e}")

    def _check_project_due_dates_background(self):
        """⚡ فحص مواعيد المشاريع في الخلفية (لتجنب التجميد)"""

        def fetch_due_dates():
            if self.notification_service:
                self.notification_service.check_project_due_dates()
            return True

        def on_error(error_msg):
            safe_print(f"WARNING: فشل فحص مواعيد المشاريع: {error_msg}")

        from core.data_loader import get_data_loader

        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="project_due_dates",
            load_function=fetch_due_dates,
            on_success=lambda _result: None,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _load_initial_data(self):
        """تحميل البيانات الأولية بدون تجميد - deprecated"""
        self._load_initial_data_safely()

    def load_all_data(self):
        """
        تحمل البيانات للتاب المفتوح حالياً
        """
        self.on_tab_changed(self.tabs.currentIndex())

    def setup_auto_sync(self):
        """
        ⚡ إعداد المزامنة التلقائية - يتم التحكم فيها من UnifiedSyncManager
        """
        # المزامنة التلقائية تُدار الآن من unified_sync في main.py
        safe_print("INFO: ⚡ المزامنة التلقائية تُدار من UnifiedSyncManager")

    def _get_sync_repository(self):
        """Resolve repository from sync manager with legacy fallback."""
        if self.sync_manager:
            repo = getattr(self.sync_manager, "repo", None)
            if repo:
                return repo
            legacy_repo = getattr(self.sync_manager, "repository", None)
            if legacy_repo:
                return legacy_repo

        if hasattr(self, "repository") and self.repository:
            return self.repository

        return None

    def trigger_background_sync(self):
        """
        تشغيل المزامنة في الخلفية
        """
        try:
            if not self.sync_manager:
                safe_print("INFO: مدير المزامنة غير متاح")
                return

            repo = self._get_sync_repository()
            if repo is None:
                safe_print("INFO: تخطي المزامنة التلقائية (لا يوجد repository)")
                return

            # التحقق من الاتصال
            if not getattr(repo, "online", False):
                safe_print("INFO: تخطي المزامنة التلقائية (غير متصل)")
                return

            safe_print("INFO: بدء المزامنة التلقائية في الخلفية...")

            # تشغيل المزامنة باستخدام API الحديثة فقط
            if hasattr(self.sync_manager, "schedule_instant_sync"):
                self.sync_manager.schedule_instant_sync()
            elif hasattr(self.sync_manager, "instant_sync"):
                threading.Thread(target=self.sync_manager.instant_sync, daemon=True).start()
            else:
                safe_print("WARNING: مدير المزامنة غير متوافق: instant_sync غير متاحة")

        except Exception as e:
            safe_print(f"ERROR: خطأ في المزامنة التلقائية: {e}")

    def on_auto_sync_completed(self, result: dict):
        """
        معالج حدث اكتمال المزامنة التلقائية
        """
        try:
            synced = result.get("synced", 0)
            failed = result.get("failed", 0)
            safe_print(f"INFO: اكتملت المزامنة التلقائية - نجح: {synced}, فشل: {failed}")

            # تحديث الواجهة إذا كانت هناك تغييرات
            if synced > 0:
                self.on_sync_completed()
        except Exception as e:
            safe_print(f"ERROR: خطأ في معالجة نتيجة المزامنة التلقائية: {e}")

    def on_sync_completed(self):
        """
        معالج حدث اكتمال المزامنة
        يقوم بتحديث البيانات في التاب الحالي
        """
        try:
            now = time.monotonic()
            if (now - self._last_sync_ui_refresh_at) < self._sync_ui_refresh_cooldown_seconds:
                return
            self._last_sync_ui_refresh_at = now
            # تحديث البيانات في التاب الحالي
            current_index = self.tabs.currentIndex()
            self.on_tab_changed(current_index)
        except Exception as e:
            safe_print(f"خطأ في تحديث البيانات بعد المزامنة: {e}")

    def _invalidate_tab_cache(self, tab_name: str):
        """⚡ إبطال الـ cache لتاب معين لضمان جلب بيانات جديدة"""
        try:
            if tab_name == "🚀 المشاريع":
                if hasattr(self, "projects_tab") and hasattr(self.projects_tab, "project_service"):
                    if hasattr(self.projects_tab.project_service, "invalidate_cache"):
                        self.projects_tab.project_service.invalidate_cache()

            elif tab_name == "💳 المصروفات":
                if hasattr(self, "expense_tab") and hasattr(self.expense_tab, "expense_service"):
                    if hasattr(self.expense_tab.expense_service, "invalidate_cache"):
                        self.expense_tab.expense_service.invalidate_cache()

            elif tab_name == "💰 الدفعات":
                if hasattr(self, "payments_tab") and hasattr(self.payments_tab, "project_service"):
                    if hasattr(self.payments_tab.project_service, "invalidate_cache"):
                        self.payments_tab.project_service.invalidate_cache()

            elif tab_name in ACCOUNTING_TAB_LABELS:
                if hasattr(self, "accounting_tab") and hasattr(
                    self.accounting_tab, "invalidate_cache"
                ):
                    self.accounting_tab.invalidate_cache()

            elif tab_name == "🛠️ الخدمات والباقات":
                if hasattr(self, "services_tab") and hasattr(self.services_tab, "service_service"):
                    if hasattr(self.services_tab.service_service, "invalidate_cache"):
                        self.services_tab.service_service.invalidate_cache()

        except Exception as e:
            safe_print(f"WARNING: [MainWindow] فشل إبطال cache لتاب {tab_name}: {e}")

    def refresh_table(self, table_name: str):
        """
        🔄 تحديث جدول معين عند تغيير البيانات من المزامنة الفورية
        ⚡ Lazy Refresh: يتم تحديث التاب الحالي فقط، والباقي يتم تعليمه كـ pending
        """
        try:
            # 1. تحديد التابات المتأثرة
            mapping = {
                "clients": ["👤 العملاء"],
                "projects": ["🚀 المشاريع"],
                "services": ["🛠️ الخدمات والباقات"],
                "tasks": ["📋 المهام"],
                "currencies": ["🔧 الإعدادات"],
                "ids": ["🔧 الإعدادات"],  # IDs sequences
                "accounts": [ACCOUNTING_TAB_LABEL],
                "payments": ["💰 الدفعات"],
                "expenses": ["💳 المصروفات"],
                "journal_entries": [ACCOUNTING_TAB_LABEL],
            }

            target_tabs = list(mapping.get(table_name, []))
            if "🔧 الإعدادات" in target_tabs and hasattr(self, "settings_tab"):
                self.settings_tab.mark_data_changed(table_name)

            # ⚡ Dashboard يُحدث دائماً (لكن بحذر)
            dashboard_related_tables = {
                "accounts",
                "payments",
                "expenses",
                "journal_entries",
                "invoices",
                "projects",
            }
            if table_name in dashboard_related_tables and self._can_refresh(
                "dashboard", min_interval=12.0
            ):
                target_tabs.append("🏠 الصفحة الرئيسية")

            if not target_tabs:
                return

            current_tab_name = self.tabs.tabText(self.tabs.currentIndex())

            for tab_name in target_tabs:
                # ⚡ إذا كان التاب ظاهرًا: تحديث فوري
                if tab_name == current_tab_name:
                    if self._can_refresh(f"tab_{tab_name}", min_interval=2.5):
                        # ⚡ إبطال cache وتحديث
                        self._invalidate_tab_cache(tab_name)
                        self._do_load_tab_data_safe(tab_name)
                    else:
                        # لا تُسقط التحديثات السريعة: أجّلها قليلًا بدل تجاهلها.
                        self._schedule_deferred_refresh(table_name, tab_name)
                else:
                    # 💤 إذا كان مخفيًا: تعليم للتحديث لاحقًا
                    self.pending_refreshes[tab_name] = True

        except Exception as e:
            safe_print(f"ERROR: [MainWindow] خطأ في تحديث جدول {table_name}: {e}")

    def _on_instant_sync(self):
        """
        🔄 مزامنة لحظية - يتم تشغيلها عند الضغط على زرار المزامنة
        """

        try:
            safe_print("INFO: 🔄 بدء المزامنة اللحظية...")

            # تحديث حالة الشريط
            self.status_bar.update_sync_status("syncing")

            def do_sync():
                """تنفيذ المزامنة في thread منفصل"""
                try:
                    # استخدام sync_manager (UnifiedSyncManager)
                    if self.sync_manager:
                        if hasattr(self.sync_manager, "schedule_instant_sync"):
                            self.sync_manager.schedule_instant_sync()
                        elif hasattr(self.sync_manager, "instant_sync"):
                            threading.Thread(
                                target=self.sync_manager.instant_sync, daemon=True
                            ).start()
                        else:
                            safe_print("WARNING: مدير المزامنة غير متوافق: instant_sync غير متاحة")
                            QTimer.singleShot(
                                0, lambda: self.status_bar.update_sync_status("error")
                            )
                            return
                    else:
                        safe_print("WARNING: لا يوجد مدير مزامنة متاح")
                        QTimer.singleShot(0, lambda: self.status_bar.update_sync_status("error"))
                        return

                    QTimer.singleShot(0, lambda: self.status_bar.update_sync_status("synced"))
                    safe_print("INFO: ✅ اكتملت المزامنة اللحظية بنجاح")

                except Exception as e:
                    safe_print(f"ERROR: فشلت المزامنة اللحظية: {e}")
                    QTimer.singleShot(0, lambda: self.status_bar.update_sync_status("error"))

            # تشغيل المزامنة في الخلفية
            # استخدام QTimer بدلاً من daemon thread
            QTimer.singleShot(100, do_sync)  # تأخير 100ms

        except Exception as e:
            safe_print(f"ERROR: خطأ في بدء المزامنة اللحظية: {e}")
            self.status_bar.update_sync_status("error")

    def _on_full_sync_clicked(self):
        """
        🔥 مزامنة كاملة - مسح البيانات المحلية وإعادة التحميل من MongoDB
        """
        # تأكيد من المستخدم
        reply = QMessageBox.question(
            self,
            "🔄 مزامنة كاملة",
            "هذه العملية ستقوم بـ:\n\n"
            "1️⃣ رفع أي تغييرات محلية معلقة\n"
            "2️⃣ مسح قاعدة البيانات المحلية بالكامل\n"
            "3️⃣ إعادة تحميل كل البيانات من السيرفر\n\n"
            "⚠️ تأكد من وجود اتصال بالإنترنت\n\n"
            "هل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # التحقق من وجود sync_manager
        if not self.sync_manager:
            QMessageBox.warning(self, "خطأ", "نظام المزامنة غير متاح. يرجى إعادة تشغيل البرنامج.")
            return

        # التحقق من الاتصال - محاولة الاتصال أولاً
        is_online = bool(getattr(self.sync_manager, "is_online", False))
        if not is_online:
            # محاولة إعادة الاتصال
            try:
                repo = self._get_sync_repository()
                mongo_client = getattr(repo, "mongo_client", None) if repo else None
                if mongo_client is not None:
                    mongo_client.admin.command("ping")
                    repo.online = True
                    is_online = True
                    safe_print("INFO: ✅ تم استعادة الاتصال بـ MongoDB")
            except Exception:
                QMessageBox.warning(
                    self,
                    "غير متصل",
                    "لا يوجد اتصال بـ MongoDB.\n"
                    "يرجى التحقق من:\n"
                    "1. اتصال الإنترنت\n"
                    "2. إعدادات MongoDB في ملف .env\n"
                    "3. أن خادم MongoDB يعمل",
                )
                return
            if not is_online:
                QMessageBox.warning(
                    self,
                    "غير متصل",
                    "لا يوجد اتصال بـ MongoDB.\n"
                    "يرجى التحقق من:\n"
                    "1. اتصال الإنترنت\n"
                    "2. إعدادات MongoDB في ملف .env\n"
                    "3. أن خادم MongoDB يعمل",
                )
                return

        # تعطيل الزر أثناء المزامنة
        if hasattr(self, "status_bar") and hasattr(self.status_bar, "full_sync_btn"):
            self.status_bar.full_sync_btn.setEnabled(False)
            self.status_bar.full_sync_btn.setText("⏳ جاري...")

        # ⚡ تحديث حالة زرار المزامنة الجديد
        if hasattr(self, "status_bar") and hasattr(self.status_bar, "sync_button"):
            self.status_bar.sync_button.set_status("syncing")

        def do_full_sync():
            """تنفيذ المزامنة الكاملة في thread منفصل"""
            try:
                safe_print("INFO: 🔥 بدء المزامنة الكاملة...")

                result: object = {"success": False, "error": "نظام المزامنة غير متاح"}
                if self.sync_manager is not None and hasattr(
                    self.sync_manager, "full_sync_from_cloud"
                ):
                    result = self.sync_manager.full_sync_from_cloud()
                else:
                    repo = self._get_sync_repository()
                    if repo is not None:
                        global UnifiedSyncManagerV3
                        if UnifiedSyncManagerV3 is None:
                            from core import UnifiedSyncManagerV3 as _UnifiedSyncManagerV3

                            UnifiedSyncManagerV3 = _UnifiedSyncManagerV3
                        unified_sync = UnifiedSyncManagerV3(repo)
                        result = unified_sync.full_sync_from_cloud()

                if not isinstance(result, dict):
                    result = {
                        "success": bool(result),
                        "error": "" if result else "فشلت المزامنة",
                    }

                # تحديث الواجهة في الـ main thread باستخدام signal
                try:
                    self.sync_completed.emit(result)
                except Exception as signal_error:
                    safe_print(f"WARNING: فشل في إرسال signal: {signal_error}")

            except Exception as e:
                safe_print(f"ERROR: فشلت المزامنة الكاملة: {e}")
                traceback.print_exc()
                try:
                    self.sync_completed.emit({"success": False, "error": str(e)})
                except Exception:
                    # فشل إرسال إشارة الخطأ
                    pass

        # ⚡ تشغيل المزامنة في thread منفصل حقيقي (لا يجمد الواجهة)
        sync_thread = threading.Thread(target=do_full_sync, daemon=True)
        sync_thread.start()

    def _on_full_sync_completed(self, result: object):
        """
        معالج اكتمال المزامنة الكاملة
        """
        # إعادة تفعيل الزر
        if hasattr(self, "status_bar") and hasattr(self.status_bar, "full_sync_btn"):
            self.status_bar.full_sync_btn.setEnabled(True)
            self.status_bar.full_sync_btn.setText("🔄 مزامنة")

        # ⚡ تحديث حالة زرار المزامنة الجديد
        if hasattr(self, "status_bar") and hasattr(self.status_bar, "sync_button"):
            if isinstance(result, dict) and result.get("success"):
                self.status_bar.sync_button.set_status("success")
            else:
                self.status_bar.sync_button.set_status("error")

        if isinstance(result, dict):
            if result.get("success"):
                total_synced = result.get("total_synced", 0)
                QMessageBox.information(
                    self,
                    "✅ اكتملت المزامنة",
                    f"تمت المزامنة بنجاح!\n\n"
                    f"📊 إجمالي السجلات: {total_synced}\n\n"
                    "سيتم تحديث الواجهة الآن...",
                )

                # ⚡ إعادة حساب أرصدة الحسابات النقدية
                try:
                    if hasattr(self, "accounting_service") and self.accounting_service:
                        self.accounting_service._schedule_cash_recalc(["accounting"])
                        safe_print("INFO: [MainWindow] ✅ تم جدولة إعادة حساب الأرصدة بعد المزامنة")
                except Exception as e:
                    safe_print(f"WARNING: [MainWindow] فشل جدولة إعادة حساب الأرصدة: {e}")

                # تحديث الواجهة
                self.on_sync_completed()
            else:
                error = result.get("error", "خطأ غير معروف")
                reason = result.get("reason", "")

                if reason == "offline":
                    msg = "لا يوجد اتصال بالإنترنت"
                elif reason == "already_syncing":
                    msg = "المزامنة جارية بالفعل"
                else:
                    msg = f"فشلت المزامنة: {error}"

                QMessageBox.warning(self, "❌ فشلت المزامنة", msg)

    def _on_realtime_sync_status_changed(self, is_connected: bool):
        """معالج تغيير حالة المزامنة الفورية"""
        try:
            if hasattr(self, "status_bar"):
                if is_connected:
                    # إضافة مؤشر المزامنة الفورية
                    self.status_bar.set_realtime_sync_status(True)
                    safe_print("INFO: [MainWindow] ✅ مؤشر المزامنة الفورية: نشط")
                else:
                    # إزالة مؤشر المزامنة الفورية
                    self.status_bar.set_realtime_sync_status(False)
                    safe_print("INFO: [MainWindow] ❌ مؤشر المزامنة الفورية: متوقف")
        except Exception as e:
            safe_print(f"ERROR: [MainWindow] فشل تحديث مؤشر المزامنة الفورية: {e}")

    def _update_initial_connection_status(self):
        """⚡ تحديث حالة الاتصال الأولية"""
        try:
            is_online = False
            if self.sync_manager and hasattr(self.sync_manager, "repo") and self.sync_manager.repo:
                is_online = bool(getattr(self.sync_manager.repo, "online", False))
            elif hasattr(self, "repository") and self.repository:
                is_online = bool(getattr(self.repository, "online", False))

            self._apply_connection_status(is_online)
            self._trigger_async_mongo_ping()

            # ⚡ بدء مؤقت فحص الاتصال الدوري (كل 30 ثانية)
            if not hasattr(self, "_connection_check_timer") or self._connection_check_timer is None:
                self._connection_check_timer = QTimer(self)
                self._connection_check_timer.timeout.connect(self._periodic_connection_check)
                self._connection_check_timer.start(30000)  # 30 ثانية
                safe_print("INFO: [MainWindow] ⏰ تم بدء مؤقت فحص الاتصال الدوري")

        except Exception as e:
            safe_print(f"ERROR: [MainWindow] فشل تحديث حالة الاتصال: {e}")

    def _apply_connection_status(self, is_online: bool):
        try:
            if hasattr(self, "status_bar"):
                if is_online:
                    self.status_bar.update_sync_status("synced")
                else:
                    self.status_bar.update_sync_status("offline")
            self._last_connection_status = bool(is_online)
        except Exception:
            pass

    def _trigger_async_mongo_ping(self):
        try:
            if getattr(self, "_mongo_ping_in_flight", False):
                return

            repo = None
            if self.sync_manager and hasattr(self.sync_manager, "repo") and self.sync_manager.repo:
                repo = self.sync_manager.repo
            elif hasattr(self, "repository") and self.repository:
                repo = self.repository

            client = getattr(repo, "mongo_client", None) if repo else None
            if not client:
                return

            self._mongo_ping_in_flight = True

            def worker():
                ok = False
                try:
                    client.admin.command("ping", maxTimeMS=1000)
                    ok = True
                except Exception:
                    ok = False

                def apply():
                    try:
                        self._mongo_ping_in_flight = False
                        if repo:
                            repo.online = ok
                        self._apply_connection_status(ok)
                    except Exception:
                        self._mongo_ping_in_flight = False

                QTimer.singleShot(0, apply)

            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            try:
                self._mongo_ping_in_flight = False
            except Exception:
                pass

    def _periodic_connection_check(self):
        """⚡ فحص دوري لحالة الاتصال"""
        try:
            self._trigger_async_mongo_ping()
        except Exception as e:
            safe_print(f"ERROR: [MainWindow] فشل فحص الاتصال الدوري: {e}")

    def _handle_logout(self):
        """معالج تسجيل الخروج"""
        if self._confirm_exit(
            title="تأكيد تسجيل الخروج",
            message="هل أنت متأكد من تسجيل الخروج؟\n\nسيتم إغلاق البرنامج.",
        ):
            self._trigger_safe_quit("logout")

    def _build_confirmation_dialog(self, title: str, message: str):
        return _ActionConfirmationDialog(self, title, message)

    def _confirm_exit(self, title: str, message: str) -> bool:
        """عرض نافذة تأكيد موحدة ومنع تكرار النوافذ أثناء ضغطات الإغلاق المتتالية."""
        if self._exit_confirmation_open:
            return False

        self._exit_confirmation_open = True
        try:
            try:
                if self.isMinimized():
                    self.showNormal()
                self.raise_()
                self.activateWindow()
            except Exception:
                pass
            dialog = self._build_confirmation_dialog(title, message)
            result = dialog.exec()
            return result == QDialog.DialogCode.Accepted
        finally:
            self._exit_confirmation_open = False

    def _handle_deferred_close_confirmation(self):
        self._close_confirmation_pending = False
        if self._closing_in_progress or self._allow_close:
            return

        confirmed = self._confirm_exit(
            title="تأكيد الإغلاق",
            message="هل تريد إغلاق البرنامج الآن؟\n\nسيتم إيقاف المزامنة والخدمات بشكل آمن.",
        )
        if confirmed:
            self._allow_close = True
            try:
                if self.isMinimized():
                    self.showNormal()
                self.raise_()
                self.activateWindow()
            except Exception:
                pass
            self.close()

    def _trigger_safe_quit(self, source: str = "unknown"):
        """تشغيل مسار الإغلاق الرسمي بحيث يمر عبر closeEvent الآمن."""
        if self._allow_close or self._closing_in_progress:
            return

        safe_print(f"INFO: [MainWindow] طلب إغلاق آمن من المصدر: {source}")
        self._allow_close = True
        try:
            self.close()
        except Exception:
            self._closing_in_progress = True
            self._stop_close_related_ui_timers()
            self._request_application_quit()

    def _stop_close_related_ui_timers(self):
        """إيقاف مؤقتات الواجهة فقط؛ تنظيف الخدمات المركزية يتم من main.py."""
        try:
            if hasattr(self, "project_check_timer") and self.project_check_timer:
                self.project_check_timer.stop()
        except Exception:
            pass

        try:
            if (
                hasattr(self, "_project_due_dates_bootstrap_timer")
                and self._project_due_dates_bootstrap_timer
            ):
                self._project_due_dates_bootstrap_timer.stop()
        except Exception:
            pass

        try:
            if getattr(self, "_connection_check_timer", None):
                self._connection_check_timer.stop()
        except Exception:
            pass

        try:
            if getattr(self, "_table_refresh_timer", None):
                self._table_refresh_timer.stop()
        except Exception:
            pass

        try:
            for _tab_name, timer in list(self._deferred_refresh_timers.items()):
                if timer:
                    timer.stop()
                    timer.deleteLater()
            self._deferred_refresh_timers.clear()
        except Exception:
            pass

    def _request_application_quit(self):
        if self._quit_requested:
            return
        self._quit_requested = True
        app = QApplication.instance()
        if app is not None:
            try:
                app.setQuitOnLastWindowClosed(True)
            except Exception:
                pass
            QTimer.singleShot(0, lambda: app.exit(0))

    def _connect_shortcuts(self):
        """ربط الاختصارات بالإجراءات"""
        # اختصارات الإنشاء
        self.shortcuts_manager.new_project.connect(self._on_new_project)
        self.shortcuts_manager.new_client.connect(self._on_new_client)
        self.shortcuts_manager.new_expense.connect(self._on_new_expense)
        self.shortcuts_manager.new_payment.connect(self._on_new_payment)

        # اختصارات التنقل والبحث
        self.shortcuts_manager.search_activated.connect(self._on_search_activated)
        self.shortcuts_manager.refresh_data.connect(self._on_refresh_data)

        # اختصارات المساعدة
        self.shortcuts_manager.show_help.connect(self._on_show_help)

        # اختصارات إضافية
        self.shortcuts_manager.full_sync.connect(self._on_full_sync_clicked)
        self.shortcuts_manager.delete_selected.connect(self._on_delete_selected)
        self.shortcuts_manager.select_all.connect(self._on_select_all)
        self.shortcuts_manager.copy_selected.connect(self._on_copy_selected)
        self.shortcuts_manager.export_excel.connect(self._on_export_excel)
        self.shortcuts_manager.print_current.connect(self._on_print_current)
        self.shortcuts_manager.save_data.connect(self._on_save_data)
        self.shortcuts_manager.close_dialog.connect(self._on_close_dialog)

    def _keyboard_target_widget(self):
        active_modal = QApplication.activeModalWidget()
        if active_modal is not None and active_modal is not self:
            return active_modal
        return self._ensure_current_tab_widget()

    def _keyboard_target_chain(self):
        targets = []
        primary_target = self._keyboard_target_widget()
        if primary_target is not None:
            targets.append(primary_target)

        current_tab = self._ensure_current_tab_widget()
        if current_tab is not None and current_tab not in targets:
            targets.append(current_tab)

        return targets

    def _on_new_project(self):
        """معالج اختصار مشروع جديد"""
        # التبديل إلى تاب المشاريع
        self._activate_tab(TAB_PROJECTS_LABEL)
        # فتح نافذة مشروع جديد بعد تأخير بسيط

        QTimer.singleShot(100, lambda: self.projects_tab.open_editor(project_to_edit=None))

    def _on_new_client(self):
        """معالج اختصار عميل جديد"""
        # التبديل إلى تاب العملاء
        self._activate_tab(TAB_CLIENTS_LABEL)
        # فتح نافذة عميل جديد بعد تأخير بسيط

        QTimer.singleShot(100, self.clients_tab.open_editor)

    def _on_new_expense(self):
        """معالج اختصار مصروف جديد"""
        # التبديل إلى تاب المصروفات
        self._activate_tab(TAB_EXPENSES_LABEL)
        # فتح نافذة مصروف جديد بعد تأخير بسيط

        QTimer.singleShot(100, self.expense_tab.open_add_dialog)

    def _on_search_activated(self):
        """معالج اختصار تفعيل البحث"""
        for target in self._keyboard_target_chain():
            if hasattr(target, "focus_search"):
                try:
                    target.focus_search()
                    return
                except Exception:
                    pass

            if hasattr(target, "search_bar"):
                try:
                    target.search_bar.setFocus()
                    target.search_bar.selectAll()
                    return
                except Exception:
                    pass

            if hasattr(target, "findChildren"):
                search_bars = target.findChildren(QLineEdit)
                for search_bar in search_bars:
                    placeholder = search_bar.placeholderText().lower()
                    if "search" in placeholder or "بحث" in placeholder:
                        search_bar.setFocus()
                        search_bar.selectAll()
                        return

    def _on_refresh_data(self):
        """معالج اختصار تحديث البيانات"""
        active_modal = QApplication.activeModalWidget()
        if active_modal is not None and active_modal is not self:
            for method_name in ("refresh_data", "load_data", "reload_data", "on_refresh"):
                if hasattr(active_modal, method_name):
                    getattr(active_modal, method_name)()
                    return

        current_index = self.tabs.currentIndex()
        tab_name = self.tabs.tabText(current_index)

        refresh_map = {
            "🚀 المشاريع": self._refresh_projects_tab,
            "👤 العملاء": self._refresh_clients_tab,
            "💳 المصروفات": self._refresh_expenses_tab,
            "💰 الدفعات": self._refresh_payments_tab,
            "🛠️ الخدمات والباقات": self._refresh_services_tab,
            ACCOUNTING_TAB_LABEL: self._refresh_accounting_tab,
            "📋 المهام": self._refresh_tasks_tab,
        }
        refresh_action = refresh_map.get(tab_name)
        if refresh_action:
            refresh_action()
            return

        self._load_tab_data_safely(tab_name, force_reload=True)

    def _on_show_help(self):
        """معالج اختصار عرض المساعدة"""
        global ShortcutsHelpDialog
        if ShortcutsHelpDialog is None:
            from ui.shortcuts_help_dialog import ShortcutsHelpDialog as _ShortcutsHelpDialog

            ShortcutsHelpDialog = _ShortcutsHelpDialog
        dialog = ShortcutsHelpDialog(self.shortcuts_manager, self)
        dialog.exec()

    @staticmethod
    def _dismiss_escape_target(widget) -> bool:
        if widget is None:
            return False

        for method_name in ("reject", "close", "hide"):
            if hasattr(widget, method_name):
                try:
                    getattr(widget, method_name)()
                    return True
                except Exception:
                    continue
        return False

    def _on_close_dialog(self):
        """معالج اختصار Esc: يغلق العناصر المؤقتة أو ينظف التركيز الحالي."""
        active_popup = QApplication.activePopupWidget()
        if active_popup is not None and active_popup is not self:
            if MainWindow._dismiss_escape_target(active_popup):
                return

        active_modal = QApplication.activeModalWidget()
        if active_modal is not None and active_modal is not self:
            if MainWindow._dismiss_escape_target(active_modal):
                return

        current_tab = self.tabs.currentWidget() if hasattr(self, "tabs") else None
        for method_name in (
            "handle_escape",
            "on_escape",
            "cancel_edit",
            "cancel_selection",
            "close_preview",
        ):
            if current_tab is not None and hasattr(current_tab, method_name):
                try:
                    getattr(current_tab, method_name)()
                    return
                except Exception:
                    continue

        focus_widget = QApplication.focusWidget()
        if focus_widget is not None and focus_widget is not self:
            try:
                if hasattr(focus_widget, "deselect"):
                    focus_widget.deselect()
            except Exception:
                pass
            try:
                if hasattr(focus_widget, "clearFocus"):
                    focus_widget.clearFocus()
                    return
            except Exception:
                pass

        if current_tab is not None and hasattr(current_tab, "findChildren"):
            try:
                for table in current_tab.findChildren(QTableWidget):
                    if table.isVisible() and table.selectedItems():
                        table.clearSelection()
                        return
            except Exception:
                pass

    def _on_new_payment(self):
        """معالج اختصار دفعة جديدة"""
        self._activate_tab(TAB_PAYMENTS_LABEL)

        QTimer.singleShot(100, self.payments_tab.open_add_dialog)

    def _on_delete_selected(self):
        """معالج اختصار حذف العنصر المحدد"""
        for target in self._keyboard_target_chain():
            for method_name in (
                "delete_selected_payment",
                "delete_selected_expense",
                "delete_selected_client",
                "delete_selected_account",
                "delete_selected_project",
                "delete_selected_task",
                "delete_selected",
                "on_delete",
            ):
                if hasattr(target, method_name):
                    getattr(target, method_name)()
                    return

    @staticmethod
    def _visible_item_views(container) -> list[QAbstractItemView]:
        if container is None:
            return []

        item_views = [
            view for view in container.findChildren(QAbstractItemView) if view.isVisible()
        ]
        focus_widget = QApplication.focusWidget()
        item_views.sort(key=lambda view: 0 if view is focus_widget else 1)
        return item_views

    @staticmethod
    def _copy_item_view_selection(view: QAbstractItemView) -> bool:
        selection_model = view.selectionModel()
        if selection_model is None or not selection_model.hasSelection():
            return False

        indexes = sorted(
            selection_model.selectedIndexes(),
            key=lambda index: (index.row(), index.column()),
        )
        if not indexes:
            return False

        rows: dict[int, dict[int, str]] = {}
        for index in indexes:
            rows.setdefault(index.row(), {})[index.column()] = str(index.data() or "")

        line_texts: list[str] = []
        for row_number in sorted(rows):
            columns = rows[row_number]
            line_texts.append("\t".join(columns[column] for column in sorted(columns)))

        QApplication.clipboard().setText("\n".join(line_texts))
        return True

    def _on_select_all(self):
        """معالج اختصار تحديد الكل"""
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            focus_widget.selectAll()
            return

        for target in self._keyboard_target_chain():
            if hasattr(target, "select_all"):
                try:
                    target.select_all()
                    return
                except Exception:
                    pass

            for view in MainWindow._visible_item_views(target):
                view.selectAll()
                return

    def _on_copy_selected(self):
        """معالج اختصار نسخ المحدد"""
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            focus_widget.copy()
            return

        for target in self._keyboard_target_chain():
            if hasattr(target, "copy_selected"):
                try:
                    if target.copy_selected():
                        return
                except Exception:
                    pass

            for view in MainWindow._visible_item_views(target):
                if MainWindow._copy_item_view_selection(view):
                    return

    def _on_export_excel(self):
        """معالج اختصار تصدير Excel"""
        for target in self._keyboard_target_chain():
            if hasattr(target, "export_to_excel"):
                target.export_to_excel()
                return
            if hasattr(target, "on_export"):
                target.on_export()
                return

    def _on_print_current(self):
        """معالج اختصار الطباعة"""
        active_modal = QApplication.activeModalWidget()
        if active_modal:
            for method_name in ["print_ledger", "print_invoice", "print_data", "on_print"]:
                if hasattr(active_modal, method_name):
                    getattr(active_modal, method_name)()
                    return

        current_tab = self.tabs.currentWidget()
        current_tab = self._ensure_current_tab_widget() or current_tab
        for method_name in ["print_invoice", "print_data", "on_print"]:
            if hasattr(current_tab, method_name):
                getattr(current_tab, method_name)()
                return

    def _on_save_data(self):
        """معالج اختصار الحفظ"""
        active_modal = QApplication.activeModalWidget()
        if active_modal:
            save_methods = [
                "save_project",
                "save_project_and_new",
                "save_task",
                "save_expense",
                "save_payment",
                "save_client",
                "save_user",
                "save_service",
                "save_account",
                "save_currency",
                "save_template",
                "save_permissions",
                "save_settings",
            ]
            for method_name in save_methods:
                if hasattr(active_modal, method_name):
                    getattr(active_modal, method_name)()
                    return

        current_tab = self._ensure_current_tab_widget()
        for method_name in ["save_data", "on_save", "save_settings"]:
            if hasattr(current_tab, method_name):
                getattr(current_tab, method_name)()
                return

        self._on_full_sync_clicked()

    def apply_permissions(self):
        """تطبيق الصلاحيات حسب دور المستخدم"""

        user_role = self.current_user.role
        role_display = user_role.value if hasattr(user_role, "value") else str(user_role)
        safe_print(f"INFO: [MainWindow] تطبيق صلاحيات الدور: {role_display}")

        # قائمة التابات مع أسمائها الداخلية (محدثة بعد إزالة عروض الأسعار)
        tab_permissions = {
            "dashboard": 0,  # الداشبورد
            "projects": 1,  # المشاريع
            "expenses": 2,  # المصروفات
            "payments": 3,  # الدفعات
            "clients": 4,  # العملاء
            "services": 5,  # الخدمات
            "accounting": 6,  # المحاسبة
            "todo": 7,  # المهام
            "settings": 8,  # الإعدادات
        }

        # إخفاء التابات غير المسموحة (باستخدام النظام الجديد)
        global PermissionManager, UserRole
        if PermissionManager is None or UserRole is None:
            from core.auth_models import PermissionManager as _PermissionManager
            from core.auth_models import UserRole as _UserRole

            PermissionManager = _PermissionManager
            UserRole = _UserRole

        tabs_to_hide = []
        for tab_name, tab_index in tab_permissions.items():
            if not PermissionManager.can_access_tab(self.current_user, tab_name):
                tabs_to_hide.append((tab_index, tab_name))

        # إخفاء التابات من الآخر للأول لتجنب تغيير الفهارس
        for tab_index, tab_name in sorted(tabs_to_hide, reverse=True):
            if tab_index < self.tabs.count():
                self.tabs.widget(tab_index)
                self.tabs.removeTab(tab_index)
                safe_print(f"INFO: [MainWindow] تم إخفاء تاب: {tab_name}")

        # تطبيق قيود إضافية حسب الدور
        if user_role == UserRole.SALES:
            # مندوب المبيعات: قيود إضافية
            safe_print("INFO: [MainWindow] تطبيق قيود مندوب المبيعات")
            # يمكن إضافة قيود أخرى هنا مثل إخفاء أزرار الحذف

        elif user_role == UserRole.ACCOUNTANT:
            # المحاسب: قيود محدودة
            safe_print("INFO: [MainWindow] تطبيق قيود المحاسب")

        elif user_role == UserRole.ADMIN:
            # المدير: لا توجد قيود
            safe_print("INFO: [MainWindow] المدير - جميع الصلاحيات متاحة")

        # تحديث شريط العنوان ليعكس الصلاحيات
        role_display = {
            UserRole.ADMIN: "مدير النظام",
            UserRole.ACCOUNTANT: "محاسب",
            UserRole.SALES: "مندوب مبيعات",
        }

        self.setWindowTitle(
            f"Sky Wave ERP - {self.current_user.full_name or self.current_user.username} "
            f"({role_display.get(user_role, str(user_role))})"
        )

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        """معالج تغيير حجم النافذة - تحديث محسّن"""
        super().resizeEvent(event)
        self._apply_tabs_responsive()
        # إعادة ضبط جميع العناصر عند تغيير الحجم
        if hasattr(self, "tabs"):
            self.tabs.updateGeometry()
            # تحديث التاب الحالي
            current_widget = self.tabs.currentWidget()
            if current_widget:
                current_widget.updateGeometry()

        # تحديث central widget
        if self.centralWidget():
            self.centralWidget().updateGeometry()

    def _apply_tabs_responsive(self):
        if not hasattr(self, "tabs"):
            return
        compact = self.width() < 1200
        if self._tabs_compact == compact:
            return
        self._tabs_compact = compact
        tab_bar = self.tabs.tabBar()
        tab_bar.setExpanding(True)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setElideMode(
            Qt.TextElideMode.ElideRight if compact else Qt.TextElideMode.ElideNone
        )
        tab_font = tab_bar.font()
        tab_font.setPointSize(10 if compact else 11)
        tab_bar.setFont(tab_font)

    def setup_title_bar(self):
        """تخصيص شريط العنوان بألوان البرنامج"""
        try:
            # للويندوز - تخصيص شريط العنوان
            if platform.system() == "Windows":
                try:
                    # الحصول على handle النافذة
                    hwnd = int(self.winId())

                    # تعريف الألوان (BGR format)
                    # لون أزرق غامق أكثر يناسب البرنامج
                    title_bar_color = 0x291301  # لون أزرق غامق (#011329 في BGR)
                    title_text_color = 0xFFFFFF  # أبيض للنص

                    # تطبيق لون شريط العنوان
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 35, ctypes.byref(ctypes.c_int(title_bar_color)), 4
                    )

                    # تطبيق لون نص شريط العنوان
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 36, ctypes.byref(ctypes.c_int(title_text_color)), 4
                    )

                except Exception as e:
                    safe_print(f"تعذر تخصيص شريط العنوان: {e}")

            # تطبيق نمط عام للنافذة
            self.setStyleSheet(
                """
                QMainWindow {
                    background-color: #001a3a;
                    color: #ffffff;
                }
                QMenuBar {
                    background-color: #011329;
                    color: #ffffff;
                    border-bottom: 1px solid #1a1f2a;
                }
                QMenuBar::item {
                    background-color: transparent;
                    padding: 8px 12px;
                }
                QMenuBar::item:selected {
                    background-color: #3b82f6;
                }
                QToolBar {
                    background-color: #011329;
                    border: none;
                    spacing: 3px;
                }
                QStatusBar {
                    background-color: #011329;
                    color: #ffffff;
                    border-top: 1px solid #1a1f2a;
                }
            """
            )

        except Exception as e:
            safe_print(f"خطأ في تخصيص شريط العنوان: {e}")

    # 🔥🔥🔥 CRITICAL: Handler للاتصال المباشر بالـ Repository
    def handle_data_change(self, table_name: str):
        """
        معالج مباشر لإشارات تغيير البيانات من Repository
        يتم استدعاؤه فوراً عند أي حفظ/تعديل/حذف

        ⚡ IMMEDIATE REFRESH LOGIC:
        - If the changed table corresponds to the ACTIVE tab → Refresh NOW
        - Otherwise → Mark as pending for lazy loading
        """
        try:
            if table_name in self._tables_with_direct_refresh_signals:
                return

            # Notification entries include operational sync pings and should not trigger
            # generic tab refresh routing.
            if table_name == "notifications":
                return

            # Map incoming table names to UI Tab Text Names
            tab_map = {
                "clients": "👤 العملاء",
                "projects": "🚀 المشاريع",
                "invoices": "💰 الدفعات",  # Invoices map to payments tab
                "payments": "💰 الدفعات",
                "expenses": "💳 المصروفات",
                "accounting": ACCOUNTING_TAB_LABEL,
                "accounts": ACCOUNTING_TAB_LABEL,
                "journal_entries": ACCOUNTING_TAB_LABEL,
                "services": "🛠️ الخدمات والباقات",
                "tasks": "📋 المهام",
                "currencies": "🔧 الإعدادات",
                "ids": "🔧 الإعدادات",
            }

            target_tab = tab_map.get(table_name)
            if not target_tab:
                safe_print(f"⚠️ [MainWindow] جدول غير معروف: {table_name}")
                return

            if target_tab == "🔧 الإعدادات" and hasattr(self, "settings_tab"):
                self.settings_tab.mark_data_changed(table_name)

            # Get currently visible tab
            current_tab = self.tabs.tabText(self.tabs.currentIndex())

            # CRITICAL: If user is looking at this tab, refresh NOW
            if target_tab == current_tab:
                # Queue refresh to merge bursts from sync/realtime events.
                self._enqueue_table_refresh(table_name)
            else:
                # Otherwise, mark for later to prevent background lag
                self.pending_refreshes[target_tab] = True

        except Exception as e:
            safe_print(f"❌ [MainWindow] خطأ في معالجة إشارة {table_name}: {e}")

    def _enqueue_table_refresh(self, table_name: str, delay_ms: int = 260) -> None:
        """Queue table refresh requests and flush them in one batch."""
        if not isinstance(table_name, str) or not table_name.strip():
            return
        self._queued_table_refreshes.add(table_name.strip())
        if not self._table_refresh_timer.isActive():
            self._table_refresh_timer.start(max(150, int(delay_ms)))

    def _flush_enqueued_table_refreshes(self) -> None:
        """Run batched table refreshes after debounce window."""
        if not self._queued_table_refreshes:
            return
        tables = sorted(self._queued_table_refreshes)
        self._queued_table_refreshes.clear()
        for table_name in tables:
            self.refresh_table(table_name)

    # 🔥 دوال تحديث الواجهة الفورية (INSTANT UI REFRESH)
    # ⚡ حماية من التحديث المتكرر - تقليل الفترة لـ 0.5 ثانية
    _last_refresh_times = {}
    _refresh_in_progress = {}  # ⚡ حماية إضافية من التحديث المتزامن
    _deferred_refresh_timers = {}

    def _can_refresh(self, tab_name: str, min_interval: float = 0.5) -> bool:
        """⚡ فحص إذا كان يمكن تحديث التاب (حماية من التكرار)"""
        current_time = time.time()

        # ⚡ فحص إذا كان التحديث جاري بالفعل
        if self._refresh_in_progress.get(tab_name, False):
            return False

        last_time = self._last_refresh_times.get(tab_name, 0)
        if (current_time - last_time) < min_interval:
            return False
        self._last_refresh_times[tab_name] = current_time
        return True

    def _schedule_deferred_refresh(self, table_name: str, tab_name: str, delay_ms: int = 1200):
        """جدولة تحديث مؤجل للتاب بدل إسقاط التحديثات السريعة."""
        self.pending_refreshes[tab_name] = True
        if self._deferred_refresh_timers.get(tab_name):
            return

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda tn=table_name, tab=tab_name: self._run_deferred_refresh(tn, tab)
        )
        self._deferred_refresh_timers[tab_name] = timer
        timer.start(max(150, int(delay_ms)))

    def _run_deferred_refresh(self, table_name: str, tab_name: str):
        timer = self._deferred_refresh_timers.pop(tab_name, None)
        if timer:
            try:
                timer.deleteLater()
            except Exception:
                pass

        if self.tabs.tabText(self.tabs.currentIndex()) != tab_name:
            self.pending_refreshes[tab_name] = True
            return

        if not self._can_refresh(f"tab_{tab_name}", min_interval=1.2):
            self._schedule_deferred_refresh(table_name, tab_name, delay_ms=350)
            return

        self._invalidate_tab_cache(tab_name)
        self.pending_refreshes.pop(tab_name, None)
        self._do_load_tab_data_safe(tab_name)

    def _refresh_clients_tab(self):
        """تحديث تاب العملاء (موجه لنظام Lazy Refresh)"""
        self._enqueue_table_refresh("clients")

    def _refresh_projects_tab(self):
        """تحديث تاب المشاريع (موجه لنظام Lazy Refresh)"""
        self._enqueue_table_refresh("projects")

    def _refresh_expenses_tab(self):
        """تحديث تاب المصروفات (موجه لنظام Lazy Refresh)"""
        self._enqueue_table_refresh("expenses")

    def _refresh_payments_tab(self):
        """تحديث تاب الدفعات (موجه لنظام Lazy Refresh)"""
        self._enqueue_table_refresh("payments")

    def _refresh_services_tab(self):
        """تحديث تاب الخدمات (موجه لنظام Lazy Refresh)"""
        self._enqueue_table_refresh("services")

    def _refresh_accounting_tab(self):
        """تحديث تاب المحاسبة (موجه لنظام Lazy Refresh)"""
        self._enqueue_table_refresh("accounts")

    def _refresh_tasks_tab(self):
        """تحديث تاب المهام (موجه لنظام Lazy Refresh)"""
        self._enqueue_table_refresh("tasks")

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """
        🛡️ إيقاف آمن لجميع الخدمات عند إغلاق البرنامج
        يحل مشكلة التجميد والإغلاق المفاجئ
        """
        try:
            now = time.monotonic()
            if self._closing_in_progress:
                event.accept()
                return

            if (now - self._last_close_event_log_ts) > 8.0:
                self._last_close_event_log_ts = now
                safe_print(
                    f"WARNING: [MainWindow] closeEvent triggered | spontaneous={event.spontaneous()} allow_close={self._allow_close}"
                )

            if not self._allow_close:
                if self._close_confirmation_pending or self._exit_confirmation_open:
                    event.ignore()
                    return
                if (now - self._last_close_request_ts) <= 0.35:
                    event.ignore()
                    return
                self._last_close_request_ts = now
                self._close_confirmation_pending = True
                event.ignore()
                QTimer.singleShot(0, self._handle_deferred_close_confirmation)
                return

            self._closing_in_progress = True
            self._stop_close_related_ui_timers()
            safe_print("INFO: [MainWindow] تم تفويض الإغلاق الآمن إلى التطبيق الرئيسي")
            event.accept()
            self._request_application_quit()

        except Exception as e:
            safe_print(f"ERROR: خطأ أثناء الإغلاق: {e}")
            traceback.print_exc()
            # قبول الإغلاق حتى لو حدث خطأ
            event.accept()
