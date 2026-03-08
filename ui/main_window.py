# pylint: disable=too-many-lines,too-many-positional-arguments
# الملف: ui/main_window.py


import ctypes
import gc
import os
import platform
import threading
import time
import traceback

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import UnifiedSyncManagerV3
from core.auth_models import PermissionManager, UserRole
from core.data_loader import get_data_loader
from core.keyboard_shortcuts import KeyboardShortcutManager
from core.realtime_sync import shutdown_realtime_sync
from core.resource_utils import get_resource_path
from core.signals import app_signals
from services.accounting_service import AccountingService
from services.auto_update_service import get_auto_update_service
from services.client_service import ClientService
from services.expense_service import ExpenseService
from services.invoice_service import InvoiceService
from services.notification_service import NotificationService
from services.project_service import ProjectService
from services.service_service import ServiceService
from services.settings_service import SettingsService
from services.template_service import TemplateService
from ui.accounting_manager import AccountingManagerTab
from ui.client_manager import ClientManagerTab
from ui.dashboard_tab import DashboardTab
from ui.expense_manager import ExpenseManagerTab
from ui.notification_system import NotificationManager
from ui.payments_manager import PaymentsManagerTab
from ui.project_manager import ProjectManagerTab
from ui.service_manager import ServiceManagerTab
from ui.settings_tab import SettingsTab
from ui.shortcuts_help_dialog import ShortcutsHelpDialog
from ui.status_bar_widget import StatusBarWidget
from ui.styles import apply_rtl_alignment_to_all_fields
from ui.todo_manager import TaskService, TodoManagerWidget

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


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

        # إعداد مؤقت لفحص مواعيد استحقاق المشاريع (كل 24 ساعة)
        self.project_check_timer = QTimer()
        self.project_check_timer.timeout.connect(self._check_project_due_dates_background)
        self.project_check_timer.start(86400000)  # 24 ساعة

        # ⚡ فحص أولي في الخلفية بعد 10 ثواني
        QTimer.singleShot(10000, self._check_project_due_dates_background)

        # إعداد اختصارات لوحة المفاتيح
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

        if self.template_service is None:
            self.template_service = TemplateService(
                repository=self.accounting_service.repo, settings_service=self.settings_service
            )

        # تحديث template_service في printing_service إذا كان موجوداً
        if self.printing_service:
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

        # ⚡ إنشاء كل التابات فوراً (بدون تحميل بيانات)
        self._create_all_tabs()

        # تطبيق الصلاحيات حسب دور المستخدم (بعد إنشاء كل التابات)
        self.apply_permissions()

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
            self.sync_manager = UnifiedSyncManagerV3(self.accounting_service.repo)

        # إعداد المزامنة التلقائية كل 10 دقائق
        self.setup_auto_sync()

        # --- 4. تحميل البيانات في الخلفية ---
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # ⚡ تحميل البيانات فوراً (بدون تأخير)
        QTimer.singleShot(100, self._load_initial_data_safely)

    def _create_all_tabs(self):
        """⚡ إنشاء كل التابات مرة واحدة (بدون تحميل بيانات) - محسّن للسرعة"""
        safe_print("INFO: [MainWindow] ⚡ إنشاء كل التابات...")

        # 1. Dashboard - التاب الأول فقط يُنشأ فوراً
        self.dashboard_tab = DashboardTab(self.accounting_service)
        self.tabs.addTab(self.dashboard_tab, "🏠 الصفحة الرئيسية")

        # 2. Projects
        self.projects_tab = ProjectManagerTab(
            self.project_service,
            self.client_service,
            self.service_service,
            self.accounting_service,
            self.expense_service,
            self.printing_service,
            template_service=self.template_service,
        )
        self.tabs.addTab(self.projects_tab, "🚀 المشاريع")

        # 3. Expenses
        self.expense_tab = ExpenseManagerTab(
            self.expense_service,
            self.accounting_service,
            self.project_service,
        )
        self.tabs.addTab(self.expense_tab, "💳 المصروفات")

        # 4. Payments
        self.payments_tab = PaymentsManagerTab(
            project_service=self.project_service,
            accounting_service=self.accounting_service,
            client_service=self.client_service,
            current_user=self.current_user,
        )
        self.tabs.addTab(self.payments_tab, "💰 الدفعات")

        # 5. Clients
        self.clients_tab = ClientManagerTab(self.client_service)
        self.tabs.addTab(self.clients_tab, "👤 العملاء")

        # 6. Services
        self.services_tab = ServiceManagerTab(self.service_service)
        self.tabs.addTab(self.services_tab, "🛠️ الخدمات والباقات")

        # 7. Accounting
        self.accounting_tab = AccountingManagerTab(
            self.expense_service,
            self.accounting_service,
            self.project_service,
        )
        self.tabs.addTab(self.accounting_tab, "📊 المحاسبة")

        TaskService._repository = self.accounting_service.repo
        TaskService._instance = None
        TaskService(repository=self.accounting_service.repo, load_now=False)
        self.todo_tab = TodoManagerWidget(
            project_service=self.project_service, client_service=self.client_service
        )
        self.tabs.addTab(self.todo_tab, "📋 المهام")

        # 9. Settings
        self.settings_tab = SettingsTab(
            self.settings_service,
            repository=self.accounting_service.repo,
            current_user=self.current_user,
        )
        self.tabs.addTab(self.settings_tab, "🔧 الإعدادات")

        safe_print("INFO: [MainWindow] ⚡ تم إنشاء كل التابات")

        # ⚡ تطبيق محاذاة RTL في الخلفية بعد ثانية

        def apply_rtl_later():
            for i in range(self.tabs.count()):
                tab_widget = self.tabs.widget(i)
                if tab_widget:
                    apply_rtl_alignment_to_all_fields(tab_widget)
            safe_print("INFO: [MainWindow] ⚡ تم تطبيق محاذاة RTL على كل الحقول")

        QTimer.singleShot(1000, apply_rtl_later)

    def on_tab_changed(self, index):
        """⚡ تحميل بيانات التاب عند التنقل - محسّن للسرعة"""
        try:
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
        """⚡ تحميل البيانات في الخلفية باستخدام QThread لمنع التجميد"""

        # الحصول على DataLoader
        data_loader = get_data_loader()

        # تحديد دالة التحميل حسب التاب
        def get_load_function():
            if tab_name == "🏠 الصفحة الرئيسية":
                return self._load_dashboard_data
            elif tab_name == "🚀 المشاريع":
                return self._load_projects_data
            elif tab_name == "💳 المصروفات":
                return self._load_expenses_data
            elif tab_name == "💰 الدفعات":
                return self._load_payments_data
            elif tab_name == "👤 العملاء":
                return self._load_clients_data
            elif tab_name == "🛠️ الخدمات والباقات":
                return self._load_services_data
            elif tab_name == "📊 المحاسبة":
                return self._load_accounting_data
            elif tab_name == "📋 المهام":
                return self._load_tasks_data
            elif tab_name == "🔧 الإعدادات":
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
                self._refresh_in_progress[f"tab_{tab_name}"] = False
                if self.pending_refreshes.pop(tab_name, False):
                    current_tab = self.tabs.tabText(self.tabs.currentIndex())
                    if current_tab == tab_name:
                        QTimer.singleShot(220, lambda t=tab_name: self._do_load_tab_data_safe(t))
                    else:
                        self.pending_refreshes[tab_name] = True

        def on_error(error_msg):
            """معالج الخطأ"""
            safe_print(f"ERROR: فشل تحميل بيانات التاب {tab_name}: {error_msg}")
            self._refresh_in_progress[f"tab_{tab_name}"] = False

        # تحميل البيانات في الخلفية
        self._refresh_in_progress[f"tab_{tab_name}"] = True
        data_loader.load_async(
            operation_name=f"load_{tab_name}",
            load_function=load_func,
            on_success=on_success,
            on_error=on_error,
            use_thread_pool=True,
        )

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
            if tab_name == "🏠 الصفحة الرئيسية":
                if hasattr(self, "dashboard_tab"):
                    self.dashboard_tab.refresh_data()
            elif tab_name == "🚀 المشاريع":
                if hasattr(self, "projects_tab"):
                    self.projects_tab.load_projects_data()
            elif tab_name == "💳 المصروفات":
                if hasattr(self, "expense_tab"):
                    self.expense_tab.load_expenses_data()
            elif tab_name == "💰 الدفعات":
                if hasattr(self, "payments_tab"):
                    self.payments_tab.load_payments_data()
            elif tab_name == "👤 العملاء":
                if hasattr(self, "clients_tab"):
                    self.clients_tab.load_clients_data()
            elif tab_name == "🛠️ الخدمات والباقات":
                if hasattr(self, "services_tab"):
                    self.services_tab.load_services_data()
            elif tab_name == "📊 المحاسبة":
                if hasattr(self, "accounting_tab"):
                    self.accounting_tab.load_accounts_data()
            elif tab_name == "📋 المهام":
                if hasattr(self, "todo_tab"):
                    self.todo_tab.load_tasks()
            elif tab_name == "🔧 الإعدادات":
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
            # ⚡ تحميل بيانات الداشبورد فوراً
            if hasattr(self, "dashboard_tab"):
                self.dashboard_tab.refresh_data()
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

            elif tab_name == "📊 المحاسبة":
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
                "accounts": ["📊 المحاسبة"],
                "payments": ["💰 الدفعات"],
                "expenses": ["💳 المصروفات"],
                "journal_entries": ["📊 المحاسبة"],
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

    def _confirm_exit(self, title: str, message: str) -> bool:
        """عرض نافذة تأكيد موحدة ومنع تكرار النوافذ أثناء ضغطات الإغلاق المتتالية."""
        if self._exit_confirmation_open:
            return False

        self._exit_confirmation_open = True
        try:
            reply = QMessageBox.question(
                self,
                title,
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            return reply == QMessageBox.StandardButton.Yes
        finally:
            self._exit_confirmation_open = False

    def _trigger_safe_quit(self, source: str = "unknown"):
        """تشغيل مسار الإغلاق الرسمي بحيث يمر عبر closeEvent الآمن."""
        if self._allow_close:
            return

        safe_print(f"INFO: [MainWindow] طلب إغلاق آمن من المصدر: {source}")
        self._allow_close = True

        # نستدعي quit بشكل مؤجل لتجنب إعادة الدخول داخل closeEvent الحالي.
        QTimer.singleShot(0, QApplication.quit)

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

    def _on_new_project(self):
        """معالج اختصار مشروع جديد"""
        # التبديل إلى تاب المشاريع
        self.tabs.setCurrentIndex(1)
        # فتح نافذة مشروع جديد بعد تأخير بسيط

        QTimer.singleShot(100, lambda: self.projects_tab.open_editor(project_to_edit=None))

    def _on_new_client(self):
        """معالج اختصار عميل جديد"""
        # التبديل إلى تاب العملاء
        self.tabs.setCurrentIndex(4)
        # فتح نافذة عميل جديد بعد تأخير بسيط

        QTimer.singleShot(100, self.clients_tab.open_editor)

    def _on_new_expense(self):
        """معالج اختصار مصروف جديد"""
        # التبديل إلى تاب المصروفات
        self.tabs.setCurrentIndex(2)
        # فتح نافذة مصروف جديد بعد تأخير بسيط

        QTimer.singleShot(100, self.expense_tab.open_add_dialog)

    def _on_search_activated(self):
        """معالج اختصار تفعيل البحث"""
        # تفعيل البحث في التاب الحالي
        current_index = self.tabs.currentIndex()
        current_tab = self.tabs.widget(current_index)

        # البحث عن شريط البحث في التاب الحالي
        if hasattr(current_tab, "search_bar"):
            current_tab.search_bar.setFocus()
            current_tab.search_bar.selectAll()
        else:
            # محاولة البحث عن أي QLineEdit في التاب

            search_bars = current_tab.findChildren(QLineEdit)
            for search_bar in search_bars:
                if (
                    "search" in search_bar.placeholderText().lower()
                    or "بحث" in search_bar.placeholderText()
                ):
                    search_bar.setFocus()
                    search_bar.selectAll()
                    break

    def _on_refresh_data(self):
        """معالج اختصار تحديث البيانات"""
        current_index = self.tabs.currentIndex()
        tab_name = self.tabs.tabText(current_index)

        refresh_map = {
            "🚀 المشاريع": self._refresh_projects_tab,
            "👤 العملاء": self._refresh_clients_tab,
            "💳 المصروفات": self._refresh_expenses_tab,
            "💰 الدفعات": self._refresh_payments_tab,
            "🛠️ الخدمات والباقات": self._refresh_services_tab,
            "📊 المحاسبة": self._refresh_accounting_tab,
            "📋 المهام": self._refresh_tasks_tab,
        }
        refresh_action = refresh_map.get(tab_name)
        if refresh_action:
            refresh_action()
            return

        self._load_tab_data_safely(tab_name, force_reload=True)

    def _on_show_help(self):
        """معالج اختصار عرض المساعدة"""
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
        self.tabs.setCurrentIndex(3)

        QTimer.singleShot(100, self.payments_tab.open_add_dialog)

    def _on_delete_selected(self):
        """معالج اختصار حذف العنصر المحدد"""
        current_tab = self.tabs.currentWidget()
        # البحث عن دالة الحذف في التاب الحالي
        if hasattr(current_tab, "delete_selected_payment"):
            current_tab.delete_selected_payment()
        elif hasattr(current_tab, "delete_selected_expense"):
            current_tab.delete_selected_expense()
        elif hasattr(current_tab, "delete_selected_client"):
            current_tab.delete_selected_client()
        elif hasattr(current_tab, "delete_selected"):
            current_tab.delete_selected()
        elif hasattr(current_tab, "on_delete"):
            current_tab.on_delete()

    def _on_select_all(self):
        """معالج اختصار تحديد الكل"""
        current_tab = self.tabs.currentWidget()
        # البحث عن الجدول في التاب الحالي

        tables = current_tab.findChildren(QTableWidget)
        for table in tables:
            if table.isVisible():
                table.selectAll()
                break

    def _on_copy_selected(self):
        """معالج اختصار نسخ المحدد"""
        current_tab = self.tabs.currentWidget()

        tables = current_tab.findChildren(QTableWidget)
        for table in tables:
            if table.isVisible() and table.selectedItems():
                # نسخ البيانات المحددة
                selected = table.selectedItems()
                if selected:
                    text = "\t".join([item.text() for item in selected])
                    QApplication.clipboard().setText(text)
                break

    def _on_export_excel(self):
        """معالج اختصار تصدير Excel"""
        current_tab = self.tabs.currentWidget()
        if hasattr(current_tab, "export_to_excel"):
            current_tab.export_to_excel()
        elif hasattr(current_tab, "on_export"):
            current_tab.on_export()

    def _on_print_current(self):
        """معالج اختصار الطباعة"""
        active_modal = QApplication.activeModalWidget()
        if active_modal:
            for method_name in ["print_ledger", "print_invoice", "print_data", "on_print"]:
                if hasattr(active_modal, method_name):
                    getattr(active_modal, method_name)()
                    return

        current_tab = self.tabs.currentWidget()
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

        current_tab = self.tabs.currentWidget()
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
                "accounting": "📊 المحاسبة",
                "accounts": "📊 المحاسبة",
                "journal_entries": "📊 المحاسبة",
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
            if (now - self._last_close_event_log_ts) > 8.0:
                self._last_close_event_log_ts = now
                safe_print(
                    f"WARNING: [MainWindow] closeEvent triggered | spontaneous={event.spontaneous()} allow_close={self._allow_close}"
                )

            if not self._allow_close:
                if (now - self._last_close_request_ts) > 0.35:
                    self._last_close_request_ts = now
                    confirmed = self._confirm_exit(
                        title="تأكيد الإغلاق",
                        message="هل تريد إغلاق البرنامج الآن؟\n\nسيتم إيقاف المزامنة والخدمات بشكل آمن.",
                    )
                    if confirmed:
                        self._allow_close = True
                        # main.py disables quit-on-last-window-close; request quit explicitly.
                        app = QApplication.instance()
                        if app is not None:
                            QTimer.singleShot(0, app.quit)
                    else:
                        event.ignore()
                        return
                else:
                    event.ignore()
                    return

            safe_print("INFO: [MainWindow] بدء عملية الإغلاق الآمن...")

            # 1. إيقاف مؤقت فحص المشاريع
            if hasattr(self, "project_check_timer"):
                try:
                    self.project_check_timer.stop()
                    safe_print("✅ تم إيقاف مؤقت فحص المشاريع")
                except RuntimeError:
                    pass  # Timer تم حذفه بالفعل

            # 1.1 إيقاف أي تحديثات مؤجلة للشاشات
            try:
                for _tab_name, timer in list(self._deferred_refresh_timers.items()):
                    if timer:
                        timer.stop()
                        timer.deleteLater()
                self._deferred_refresh_timers.clear()
            except Exception:
                pass

            # 2. إيقاف خدمة التحديث التلقائي
            try:
                auto_update = get_auto_update_service()
                if auto_update:
                    auto_update.stop()
                    safe_print("✅ تم إيقاف خدمة التحديث التلقائي")
            except Exception as e:
                safe_print(f"تحذير: فشل إيقاف خدمة التحديث: {e}")

            # 3. إيقاف خدمة المزامنة
            if hasattr(self, "sync_manager") and self.sync_manager:
                try:
                    self.sync_manager.stop()
                    safe_print("✅ تم إيقاف خدمة المزامنة")
                except Exception as e:
                    safe_print(f"تحذير: فشل إيقاف المزامنة: {e}")

            # 4. إيقاف نظام المزامنة الفورية
            try:
                shutdown_realtime_sync()
                safe_print("✅ تم إيقاف المزامنة الفورية")
            except Exception as e:
                safe_print(f"تحذير: فشل إيقاف المزامنة الفورية: {e}")

            # 5. إيقاف نظام الإشعارات
            try:
                NotificationManager.shutdown()
                safe_print("✅ تم إيقاف نظام الإشعارات")
            except Exception as e:
                safe_print(f"تحذير: فشل إيقاف الإشعارات: {e}")

            # 6. إغلاق قاعدة البيانات بشكل آمن
            if hasattr(self, "accounting_service") and hasattr(self.accounting_service, "repo"):
                try:
                    self.accounting_service.repo.close()
                    safe_print("✅ تم إغلاق قاعدة البيانات")
                except Exception as e:
                    safe_print(f"تحذير: فشل إغلاق قاعدة البيانات: {e}")

            # 7. تنظيف الذاكرة
            gc.collect()
            safe_print("✅ تم تنظيف الذاكرة")

            safe_print("INFO: [MainWindow] اكتملت عملية الإغلاق الآمن بنجاح")
            event.accept()

        except Exception as e:
            safe_print(f"ERROR: خطأ أثناء الإغلاق: {e}")
            traceback.print_exc()
            # قبول الإغلاق حتى لو حدث خطأ
            event.accept()
