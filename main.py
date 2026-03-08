# الملف: main.py
# ruff: noqa: E402
"""
⚡ Sky Wave ERP - الملف الرئيسي
محسّن للسرعة القصوى - الإصدار المحسّن
"""

import os
import signal
import sys
import traceback
import uuid

# ==================== ثوابت التوقيت (بالمللي ثانية) ====================
MAINTENANCE_INTERVAL_MS = 60 * 60 * 1000  # ⚡ ساعة - صيانة دورية (زيادة للأداء)
SETTINGS_SYNC_INTERVAL_MS = 15 * 60 * 1000  # ⚡ 15 دقيقة - مزامنة الإعدادات (زيادة للأداء)
UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000  # ⚡ 6 ساعات - فحص التحديثات (زيادة للأداء)
PROJECT_CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000  # 24 ساعة - فحص المشاريع

# ⚡ إعدادات تحسين الأداء
LAZY_LOAD_DELAY_MS = 100  # تأخير التحميل الكسول
CACHE_WARMUP_DELAY_MS = 5000  # تأخير تسخين الـ cache
SYNC_START_DELAY_MS = 15000  # ⚡ تأخير بدء المزامنة (15 ثانية)

# ⚡ تحسين الأداء على Windows
if os.name == "nt":
    os.environ["QT_QPA_PLATFORM"] = "windows:darkmode=2"
    # 🔧 إصلاح مشكلة دقة الشاشة (High DPI Scaling) - الحل الأول
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "1"
    os.environ["QT_SCREEN_SCALE_FACTORS"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"  # تعطيل التكبير التلقائي
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"  # تجنب إنشاء ملفات .pyc

# ⚡ تفعيل WebEngine قبل إنشاء QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog

# تفعيل مشاركة OpenGL context للـ WebEngine
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

from PyQt6.QtCore import QTimer

from core.error_handler import ErrorHandler

# --- 0. إعداد نظام التسجيل والأخطاء ---
from core.logger import LoggerSetup

# استيراد أدوات الموارد
from core.resource_utils import get_font_path, get_resource_path

# إعداد Logger أول شيء
logger = LoggerSetup.setup_logger()

# ⚡ طباعة معلومات الإصدار
from version import APP_NAME, CURRENT_VERSION

logger.info("⚡ %s v%s", APP_NAME, CURRENT_VERSION)

# --- 1. استيراد "القلب" ---
# Authentication
from core.auth_models import AuthService
from core.event_bus import EventBus
from core.repository import Repository

# 🔄 نظام المزامنة الموحد - المصدر الوحيد للمزامنة
from core.unified_sync import UnifiedSyncManagerV3

# --- 2. استيراد "الأقسام" (العقل) ---
from services.accounting_service import AccountingService
from services.client_service import ClientService
from services.expense_service import ExpenseService
from services.export_service import ExportService
from services.invoice_service import InvoiceService
from services.notification_service import NotificationService
from services.printing_service import PrintingService
from services.project_service import ProjectService
from services.service_service import ServiceService
from services.settings_service import SettingsService
from ui.login_window import LoginWindow

# --- 3. استيراد "الواجهة" ---
from ui.main_window import MainWindow


class SkyWaveERPApp:
    """
    ⚡ الكلاس الرئيسي - محسّن للسرعة
    """

    def __init__(self):
        self.startup_id = uuid.uuid4().hex[:8]
        logger.info("=" * 80)
        logger.info("بدء تشغيل تطبيق Sky Wave ERP | startup_id=%s", self.startup_id)
        logger.info("=" * 80)
        logger.info("[MainApp] بدء تشغيل تطبيق Sky Wave ERP...")

        # --- 1. تجهيز "القلب" ---
        self.repository = Repository()

        # ⚡ الصيانة الشهرية التلقائية (تشغيل مرة واحدة عند البدء)
        try:
            from core.db_maintenance import run_monthly_maintenance_if_needed

            run_monthly_maintenance_if_needed()
        except Exception as e:
            logger.warning("[MainApp] تحذير: فشلت الصيانة الشهرية: %s", e)

        # ✅ صيانة قاعدة البيانات التلقائية (في الخلفية لتسريع البدء)
        # سيتم إنشاء الـ timers لاحقاً بعد بدء event loop
        self.maintenance_timer = None
        self.settings_timer = None
        self.update_timer = None

        self.event_bus = EventBus()
        self.settings_service = SettingsService()
        self.settings_service.set_repository(self.repository)
        self.repository.settings_service = self.settings_service

        # 🔄 نظام المزامنة الموحد - MongoDB First (النظام الرئيسي الوحيد)
        self.unified_sync = UnifiedSyncManagerV3(self.repository)
        # ⚡ ربط مدير المزامنة بالـ repository لتتمكن واجهة الإعدادات من الوصول إليه
        self.repository.unified_sync = self.unified_sync
        self.realtime_manager = None
        self._realtime_setup_attempts = 0
        self._realtime_setup_max_attempts = 24
        self._realtime_setup_retry_ms = 15000

        # ⚡ ربط إشارة تغيير البيانات بنظام الإشارات المركزي (للمزامنة الفورية)
        from core.signals import app_signals

        # ملاحظة: الـ services تستخدم app_signals مباشرة، لا حاجة لربط Repository signal
        # ⚡ ربط مدير المزامنة بالإشارات للمزامنة الفورية
        app_signals.set_sync_manager(self.unified_sync)

        # 🔥 للتوافق مع الواجهة - نستخدم unified_sync كـ sync_manager
        self.sync_manager = self.unified_sync

        logger.info("[MainApp] تم تجهيز المخزن (Repo) والإذاعة (Bus) والإعدادات.")
        logger.info("🚀 نظام المزامنة جاهز - سيبدأ بعد فتح النافذة الرئيسية")

        # تعيين Repository لـ TaskService
        from ui.todo_manager import TaskService

        TaskService.set_repository(self.repository)

        # تعيين Repository لنظام الإشعارات
        from ui.notification_system import NotificationManager

        NotificationManager.set_repository(self.repository)

        # يتم تفعيل NotificationBridge بعد إنشاء QApplication داخل run()
        self._notification_bridge_pending = True

        # --- 2. تجهيز "الأقسام" (حقن الاعتمادية) ---
        self.accounting_service = AccountingService(
            repository=self.repository, event_bus=self.event_bus
        )

        self.client_service = ClientService(repository=self.repository)
        self.service_service = ServiceService(
            repository=self.repository,
            event_bus=self.event_bus,
            settings_service=self.settings_service,
        )
        self.expense_service = ExpenseService(repository=self.repository, event_bus=self.event_bus)

        self.invoice_service = InvoiceService(repository=self.repository, event_bus=self.event_bus)

        self.project_service = ProjectService(
            repository=self.repository,
            event_bus=self.event_bus,
            accounting_service=self.accounting_service,
            settings_service=self.settings_service,
        )

        self.notification_service = NotificationService(
            repository=self.repository, event_bus=self.event_bus
        )

        # Template Service (for invoice templates)
        from services.template_service import TemplateService

        self.template_service = TemplateService(
            repository=self.repository, settings_service=self.settings_service
        )

        self.printing_service = PrintingService(
            settings_service=self.settings_service,
            template_service=self.template_service,  # ✅ تمرير template_service
        )

        self.export_service = ExportService(repository=self.repository)

        # Authentication Service
        self.auth_service = AuthService(repository=self.repository)

        # ⚡ Live Data Watcher - Real-Time Updates System
        from core.live_watcher import LiveDataWatcher

        self.live_watcher = LiveDataWatcher(
            repository=self.repository, check_interval=30
        )  # ⚡ 30 ثانية للأداء
        self.live_router = None  # سيتم تهيئته بعد إنشاء النافذة الرئيسية
        logger.info("🔴 تم تهيئة نظام التحديثات الحية (محسّن)")

        # ⚡ الـ timers سيتم إنشاؤها لاحقاً بعد بدء event loop (في _init_background_timers)

        logger.info("[MainApp] تم تجهيز كل الأقسام (Services).")
        logger.info("تم تهيئة خدمة الإشعارات والطباعة والمصادقة")

    @staticmethod
    def _is_local_mongo_target() -> bool:
        """True only when effective Mongo URI points to localhost."""
        try:
            from core.realtime_sync import is_local_mongo_uri

            uri = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI")
            if not uri:
                from core.config import Config

                uri = Config.get_mongo_uri()
            return is_local_mongo_uri(str(uri or "").strip())
        except Exception:
            return False

    def _init_background_timers(self):
        """تهيئة الـ timers في الخلفية - يجب استدعاؤها بعد بدء event loop"""
        try:
            # مؤقت الصيانة - معطّل للاستقرار
            # if self.maintenance_timer is None:
            #     self.maintenance_timer = QTimer()
            #     self.maintenance_timer.setSingleShot(False)
            #     self.maintenance_timer.timeout.connect(self._run_maintenance_safe)
            #     self.maintenance_timer.start(MAINTENANCE_INTERVAL_MS)
            logger.info("[MainApp] مؤقت الصيانة معطّل للاستقرار")

            # مؤقت مزامنة الإعدادات - معطّل للاستقرار
            # if self.settings_timer is None:
            #     self.settings_timer = QTimer()
            #     self.settings_timer.setSingleShot(False)
            #     self.settings_timer.timeout.connect(self._sync_settings_safe)
            #     self.settings_timer.start(SETTINGS_SYNC_INTERVAL_MS)
            logger.info("[MainApp] مؤقت مزامنة الإعدادات معطّل للاستقرار")

            # مؤقت التحقق من التحديثات - معطّل للاستقرار
            # if self.update_timer is None:
            #     self.update_timer = QTimer()
            #     self.update_timer.setSingleShot(False)
            #     self.update_timer.timeout.connect(self._check_updates_safe)
            #     self.update_timer.start(UPDATE_CHECK_INTERVAL_MS)
            logger.info("[MainApp] مؤقت التحديثات معطّل للاستقرار")
        except Exception as e:
            logger.error("[MainApp] خطأ في تهيئة الـ timers: %s", e)

    def run(self):
        """
        تشغيل الواجهة الرسومية (UI) مع المصادقة.
        """
        # === منع الشاشة البيضاء على Windows ===
        if os.name == "nt":  # Windows
            os.environ["QT_QPA_PLATFORM"] = "windows:darkmode=2"

        app = QApplication(sys.argv)
        # Handle Ctrl+C gracefully when the app is launched from terminal.
        try:
            signal.signal(signal.SIGINT, lambda *_args: app.quit())
            self._sigint_pump_timer = QTimer()
            self._sigint_pump_timer.setInterval(250)
            self._sigint_pump_timer.timeout.connect(lambda: None)
            self._sigint_pump_timer.start()
        except Exception as e:
            logger.debug("[MainApp] تعذر تفعيل graceful Ctrl+C: %s", e)

        if getattr(self, "_notification_bridge_pending", False):
            try:
                from core.notification_bridge import setup_notification_bridge

                setup_notification_bridge()
                self._notification_bridge_pending = False
            except Exception as e:
                logger.debug("[MainApp] تعذر تفعيل NotificationBridge: %s", e)

        # === معالجة أخطاء Qt ===
        def qt_message_handler(mode, context, message):
            """معالج رسائل Qt لتجنب الأخطاء المزعجة"""
            # تجاهل بعض التحذيرات غير المهمة
            if "Unknown property" in message or "backdrop-filter" in message:
                return
            if "box-shadow" in message or "transform" in message:
                return
            # طباعة الرسائل المهمة فقط
            if mode == 3:  # QtCriticalMsg
                logger.error("Qt Critical: %s", message)
            elif mode == 2:  # QtWarningMsg
                logger.warning("Qt Warning: %s", message)

        from PyQt6.QtCore import qInstallMessageHandler

        qInstallMessageHandler(qt_message_handler)

        # === تعيين أيقونة التطبيق ===
        from PyQt6.QtGui import QIcon

        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        # === إخفاء كل النوافذ حتى نعرض الـ splash ===
        app.setQuitOnLastWindowClosed(False)

        # === منع الشاشة البيضاء تماماً - تطبيق لون داكن على كل شيء فوراً ===
        from PyQt6.QtGui import QColor, QPalette

        from ui.styles import COLORS

        # تطبيق palette داكن على التطبيق كله
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg_dark"]))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text_primary"]))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["bg_medium"]))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["bg_dark"]))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS["bg_dark"]))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS["text_primary"]))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text_primary"]))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["bg_medium"]))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text_primary"]))
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(COLORS["primary"]))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["primary"]))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        app.setPalette(dark_palette)

        # تطبيق stylesheet إضافي
        app.setStyleSheet(
            f"""
            * {{
                background-color: {COLORS["bg_dark"]};
                color: {COLORS["text_primary"]};
            }}
            QWidget {{
                background-color: {COLORS["bg_dark"]};
                color: {COLORS["text_primary"]};
            }}
            QDialog {{
                background-color: {COLORS["bg_dark"]};
            }}
            QMainWindow {{
                background-color: {COLORS["bg_dark"]};
            }}
        """
        )

        # معالجة الأحداث لتطبيق الستايل فوراً
        app.processEvents()

        # === عرض شاشة البداية العصرية فوراً (قبل أي حاجة تانية) ===
        from ui.modern_splash import ModernSplash

        splash = ModernSplash()

        # جعل الـ splash يملأ الشاشة كلها عشان يخفي أي شاشة بيضاء
        screen = app.primaryScreen().geometry()

        # إنشاء widget أسود يغطي الشاشة كلها
        from PyQt6.QtWidgets import QWidget

        black_screen = QWidget()
        black_screen.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        black_screen.setStyleSheet("background-color: #0a1929;")
        black_screen.setGeometry(screen)
        black_screen.show()
        app.processEvents()

        # عرض الـ splash فوق الشاشة السوداء
        splash.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        splash.show()
        splash.raise_()
        splash.activateWindow()

        # معالجة الأحداث لضمان ظهور الـ splash فوراً
        for _ in range(5):
            app.processEvents()

        # === تحميل الخط العربي Cairo ===
        from PyQt6.QtGui import QFontDatabase

        splash.show_message("📝 جاري تحميل الخطوط...")
        app.processEvents()

        font_path = get_font_path("Cairo-VariableFont_slnt,wght.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                logger.info("✅ تم تحميل الخط العربي: %s", font_families[0])
            else:
                logger.warning("⚠️ فشل في تحميل الخط العربي")
        else:
            logger.error("❌ لم يتم العثور على ملف الخط")

        # === تطبيق الأنماط العامة ===
        splash.show_message("🎨 جاري تطبيق الأنماط...")
        app.processEvents()

        from ui.styles import apply_styles

        apply_styles(app)

        # === عرض نافذة تسجيل الدخول ===
        splash.show_message("🔐 جاري تحميل نافذة تسجيل الدخول...")
        app.processEvents()

        login_window = LoginWindow(self.auth_service)
        login_window.setWindowFlags(login_window.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        # إخفاء الشاشة السوداء
        black_screen.close()

        splash.finish(login_window)  # إغلاق الشاشة عند ظهور تسجيل الدخول
        login_window.raise_()
        login_window.activateWindow()

        if login_window.exec() != QDialog.DialogCode.Accepted:
            logger.info("[MainApp] تم إلغاء تسجيل الدخول. إغلاق التطبيق.")
            sys.exit(0)

        # الحصول على المستخدم المصادق عليه
        current_user = login_window.get_authenticated_user()
        if not current_user:
            logger.error("[MainApp] فشل في الحصول على بيانات المستخدم.")
            sys.exit(1)

        role_display = (
            current_user.role.value
            if hasattr(current_user.role, "value")
            else str(current_user.role)
        )
        logger.info(
            "[MainApp] تم تسجيل دخول المستخدم: %s (%s)", current_user.username, role_display
        )

        # === عرض splash screen مرة أخرى أثناء تحميل النافذة الرئيسية ===
        splash = ModernSplash()
        splash.show()
        app.processEvents()

        # إعادة تطبيق الأنماط الكاملة مع إزالة الإطارات البرتقالية
        splash.show_message("🎨 جاري تطبيق الأنماط النهائية...")
        app.processEvents()

        from ui.styles import COMPLETE_STYLESHEET

        app.setStyleSheet(
            COMPLETE_STYLESHEET
            + """
            * {
                outline: none !important;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
            QPushButton:focus, QCheckBox:focus, QRadioButton:focus,
            QListWidget:focus, QTreeView:focus, QTableWidget:focus {
                outline: none !important;
            }
            QComboBox QAbstractItemView {
                outline: none !important;
            }
        """
        )

        # === إنشاء النافذة الرئيسية ===
        splash.show_message("🏗️ جاري بناء الواجهة الرئيسية...")
        app.processEvents()

        main_window = MainWindow(
            current_user=current_user,
            settings_service=self.settings_service,
            accounting_service=self.accounting_service,
            client_service=self.client_service,
            service_service=self.service_service,
            expense_service=self.expense_service,
            invoice_service=self.invoice_service,
            project_service=self.project_service,
            notification_service=self.notification_service,
            printing_service=self.printing_service,
            template_service=self.template_service,
            export_service=self.export_service,
            sync_manager=self.sync_manager,  # 🔥 نظام المزامنة الموحد
        )

        # === عرض النافذة الرئيسية ===
        splash.show_message("✅ جاري فتح البرنامج...")
        app.processEvents()

        main_window.show()
        app.processEvents()

        # إظهار النافذة بعد تطبيق الستايل (منع الشاشة البيضاء)
        main_window.setWindowOpacity(1.0)

        # إخفاء الشاشة السوداء (لو لسه موجودة)
        try:
            black_screen.close()
        except (AttributeError, RuntimeError):
            # الشاشة السوداء غير موجودة أو تم إغلاقها بالفعل
            pass

        # إغلاق splash بعد ظهور النافذة
        splash.finish(main_window)

        # ⚡ تطبيق التوسيط على كل الجداول (في الخلفية بعد 2 ثانية)
        def apply_styles_later():
            try:
                from ui.styles import apply_center_alignment_to_all_tables

                apply_center_alignment_to_all_tables(main_window)
            except Exception as e:
                logger.warning("فشل تطبيق التوسيط: %s", e)

        QTimer.singleShot(2000, apply_styles_later)

        # 🚀 تفعيل المزامنة عند بدء التشغيل (بعد 15 ثانية)
        def start_auto_sync_system():
            """بدء نظام المزامنة التلقائية الاحترافي"""
            try:
                logger.info("[MainApp] 🚀 بدء نظام المزامنة التلقائية...")

                # تشغيل نظام المزامنة التلقائية
                self.unified_sync.start_auto_sync()

                # لا نعمل full-tab refresh إضافي هنا لتجنب تجميد متكرر للواجهة.
                # تحديثات الواجهة تأتي بالفعل عبر إشارات الجداول المتغيرة (app_signals).

                # ملاحظة: لا نربط data_synced هنا لتجنب تحديث واجهة مزدوج.
                # تحديثات Delta/Pull تصل بالفعل عبر app_signals.emit_ui_data_changed لكل جدول متغير.
                logger.info("[MainApp] ✅ تم الاكتفاء بتحديثات الواجهة عبر إشارات الجداول المتغيرة")

                # Hybrid Realtime: Change Streams عند التوفر + Delta Sync fallback دائم
                realtime_enabled = bool(getattr(self.unified_sync, "_realtime_enabled", True))
                if realtime_enabled:
                    self._realtime_setup_attempts = 0

                    def _attempt_realtime_setup():
                        if self.realtime_manager is not None:
                            return

                        self._realtime_setup_attempts += 1
                        try:
                            from core.realtime_sync import setup_realtime_sync

                            manager = setup_realtime_sync(self.repository)
                            if manager is not None:
                                self.realtime_manager = manager
                                self.realtime_manager.data_updated.connect(
                                    self._on_realtime_data_updated
                                )
                                logger.info("[MainApp] ✅ تم تفعيل المزامنة الفورية (Hybrid)")
                                return
                        except Exception as realtime_error:
                            logger.warning(
                                "[MainApp] ⚠️ فشل تفعيل realtime - fallback إلى Delta فقط: %s",
                                realtime_error,
                            )

                        if not self._is_local_mongo_target():
                            logger.info(
                                "[MainApp] ℹ️ MONGO_URI الحالي ليس localhost؛ لذلك لن تظهر نافذة UAC. "
                                "تفعيل Change Streams يحتاج Replica Set على خادم Mongo نفسه."
                            )
                            return

                        if self._realtime_setup_attempts < self._realtime_setup_max_attempts:
                            logger.info(
                                "[MainApp] ℹ️ Change Streams غير متاحة حالياً (%s/%s) - إعادة المحاولة خلال %s ثانية",
                                self._realtime_setup_attempts,
                                self._realtime_setup_max_attempts,
                                int(self._realtime_setup_retry_ms / 1000),
                            )
                            QTimer.singleShot(
                                self._realtime_setup_retry_ms, _attempt_realtime_setup
                            )
                        else:
                            logger.info(
                                "[MainApp] ℹ️ لم تتفعّل Change Streams بعد %s محاولة - الاستمرار على Delta Sync",
                                self._realtime_setup_max_attempts,
                            )

                    _attempt_realtime_setup()
                else:
                    logger.info("[MainApp] ℹ️ المزامنة الفورية معطلة من الإعدادات")
            except Exception as e:
                logger.error("[MainApp] فشل بدء المزامنة: %s", e)

        # ⚡ تهيئة الـ timers بعد بدء event loop (معطّلة للاستقرار)
        QTimer.singleShot(100, self._init_background_timers)

        # 🚀 تفعيل نظام المزامنة الموحد فقط (تعطيل الأنظمة الأخرى للاستقرار)
        QTimer.singleShot(5000, start_auto_sync_system)
        logger.info("[MainApp] 🚀 نظام المزامنة سيبدأ بعد 5 ثوانٍ")
        logger.info("[MainApp] 🔄 وضع المزامنة: Hybrid (Realtime + Delta fallback)")

        # ⚡ تفعيل التحديث التلقائي في الخلفية
        self._setup_auto_update(main_window)

        # ⚡ صيانة دورية كل ساعة
        self._setup_periodic_maintenance()

        # ✅ تتبع سبب الإغلاق (تشخيص للإغلاق المفاجئ)
        def _trace_quit_signals():
            try:
                stack_text = "".join(traceback.format_stack(limit=20))
                logger.debug("[MainApp] aboutToQuit received. Call stack:\n%s", stack_text)
            except Exception:
                logger.debug("[MainApp] aboutToQuit received.")

        app.aboutToQuit.connect(_trace_quit_signals)
        app.lastWindowClosed.connect(lambda: logger.debug("[MainApp] lastWindowClosed emitted."))

        # ✅ ربط إشارة الإغلاق لتنظيف الموارد
        app.aboutToQuit.connect(self._cleanup_on_exit)

        # ✅ منع الإغلاق التلقائي عند إغلاق/اختفاء أي نافذة بشكل غير متوقع.
        # الإغلاق النهائي يتم فقط عبر QApplication.quit من مسار مصرح (مثل تسجيل الخروج).
        app.setQuitOnLastWindowClosed(False)

        logger.info("[MainApp] البرنامج يعمل الآن.")

        # تشغيل التطبيق
        try:
            exit_code = app.exec()
        except KeyboardInterrupt:
            logger.info("[MainApp] تم استلام Ctrl+C من الطرفية - جاري الإغلاق الآمن.")
            exit_code = 0
        logger.info("[MainApp] انتهت حلقة Qt الرئيسية. exit_code=%s", exit_code)

        # ✅ تنظيف نهائي قبل الخروج
        self._cleanup_on_exit()

        sys.exit(exit_code)

    def _on_realtime_data_updated(self, table_name: str, _payload: dict):
        """معالجة event فوري من Change Streams بدون ازدواج مع delta/full sync."""
        try:
            known_tables = set(getattr(self.unified_sync, "TABLES", []))
            if isinstance(table_name, str) and table_name in known_tables:
                # Realtime change should trigger a targeted pull only.
                # UI refresh will be emitted once from pull_remote_changes after local DB update.
                if hasattr(self.unified_sync, "request_realtime_pull"):
                    self.unified_sync.request_realtime_pull(table_name)
        except Exception as e:
            logger.debug("[MainApp] فشل معالجة realtime update: %s", e)

    def _setup_auto_update(self, main_window):
        """تفعيل نظام التحديث التلقائي - معطّل للاستقرار"""
        # ⚡ معطّل - قد يسبب تعليق البرنامج
        logger.info("[MainApp] التحديث التلقائي معطّل للاستقرار")
        # try:
        #     from services.auto_update_service import get_auto_update_service
        #
        #     self.auto_update_service = get_auto_update_service()
        #
        #     # ربط إشارة التحديث المتاح
        #     self.auto_update_service.update_available.connect(
        #         lambda v, u, c: self._on_update_available(main_window, v, u, c)
        #     )
        #
        #     # بدء خدمة التحديث التلقائي
        #     self.auto_update_service.start()
        #     logger.info("[MainApp] تم تفعيل التحديث التلقائي - الإصدار الحالي: %s", CURRENT_VERSION)
        #
        # except Exception as e:
        #     logger.warning("[MainApp] فشل تفعيل التحديث التلقائي: %s", e)

    def _setup_periodic_maintenance(self):
        """تفعيل الصيانة الدورية - معطّلة للاستقرار"""
        # ⚡ معطّلة - تسبب تجميد البرنامج
        logger.info("[MainApp] الصيانة الدورية معطّلة للاستقرار")

    def _cleanup_on_exit(self):
        """✅ تنظيف جميع الموارد عند إغلاق البرنامج"""
        # منع الاستدعاء المتكرر
        if not hasattr(self, "_cleanup_done"):
            self._cleanup_done = False
        if self._cleanup_done:
            return
        self._cleanup_done = True

        import time

        t0 = time.monotonic()
        logger.info("[MainApp] جاري تنظيف الموارد قبل الإغلاق...")

        # إيقاف جميع المؤقتات
        try:
            if hasattr(self, "maintenance_timer") and self.maintenance_timer:
                self.maintenance_timer.stop()
                logger.info("[MainApp] تم إيقاف مؤقت الصيانة")
        except Exception as e:
            logger.debug("[MainApp] تحذير عند إيقاف مؤقت الصيانة: %s", e)

        try:
            if hasattr(self, "settings_timer") and self.settings_timer:
                self.settings_timer.stop()
                logger.info("[MainApp] تم إيقاف مؤقت الإعدادات")
        except Exception as e:
            logger.debug("[MainApp] تحذير عند إيقاف مؤقت الإعدادات: %s", e)

        try:
            if hasattr(self, "update_timer") and self.update_timer:
                self.update_timer.stop()
                logger.info("[MainApp] تم إيقاف مؤقت التحديثات")
        except Exception as e:
            logger.debug("[MainApp] تحذير عند إيقاف مؤقت التحديثات: %s", e)

        # إيقاف نظام المزامنة الفورية
        try:
            if hasattr(self, "realtime_manager") and self.realtime_manager:
                self.realtime_manager.stop()
                logger.info("[MainApp] تم إيقاف نظام المزامنة الفورية")
        except Exception as e:
            logger.debug("[MainApp] تحذير عند إيقاف المزامنة الفورية: %s", e)

        # إيقاف نظام التحديثات الحية
        try:
            if hasattr(self, "live_watcher") and self.live_watcher:
                self.live_watcher.stop()
                logger.info("[MainApp] تم إيقاف نظام التحديثات الحية")
        except Exception as e:
            logger.debug("[MainApp] تحذير عند إيقاف التحديثات الحية: %s", e)

        # إيقاف نظام المزامنة الموحد
        try:
            if hasattr(self, "unified_sync") and self.unified_sync:
                self.unified_sync.stop_auto_sync()
                logger.info("[MainApp] تم إيقاف نظام المزامنة التلقائية")
        except Exception as e:
            logger.debug("[MainApp] تحذير عند إيقاف المزامنة التلقائية: %s", e)

        # إيقاف مدير المزامنة V3
        try:
            if hasattr(self, "sync_manager") and self.sync_manager:
                # self.sync_manager is عادة نفس كائن self.unified_sync
                if self.sync_manager is not getattr(self, "unified_sync", None):
                    if hasattr(self.sync_manager, "stop_auto_sync"):
                        self.sync_manager.stop_auto_sync()
                    elif hasattr(self.sync_manager, "stop"):
                        self.sync_manager.stop()
                    logger.info("[MainApp] تم إيقاف مدير المزامنة")
        except Exception as e:
            logger.debug("[MainApp] تحذير عند إيقاف مدير المزامنة: %s", e)

        # إيقاف خدمة التحديث التلقائي
        try:
            if hasattr(self, "auto_update_service") and self.auto_update_service:
                self.auto_update_service.stop()
                logger.info("[MainApp] تم إيقاف خدمة التحديث التلقائي")
        except Exception as e:
            logger.debug("[MainApp] تحذير عند إيقاف خدمة التحديث: %s", e)

        # إغلاق اتصال قاعدة البيانات
        try:
            if hasattr(self, "repository") and self.repository:
                if hasattr(self.repository, "close"):
                    self.repository.close()
                elif hasattr(self.repository, "sqlite_conn"):
                    self.repository.sqlite_conn.close()
                logger.info("[MainApp] تم إغلاق اتصال قاعدة البيانات")
        except Exception as e:
            logger.debug("[MainApp] تحذير عند إغلاق قاعدة البيانات: %s", e)

        try:
            from core.unified_system import cleanup_all_systems

            cleanup_all_systems()
        except Exception as e:
            logger.debug("[MainApp] تحذير عند تنظيف الأنظمة: %s", e)

        logger.info("[MainApp] ⏱️ زمن الإغلاق: %.2fs", time.monotonic() - t0)
        logger.info("[MainApp] ✅ تم تنظيف جميع الموارد بنجاح")

    def _on_update_available(self, main_window, version, url, changelog):
        """عند توفر تحديث جديد"""
        from PyQt6.QtWidgets import QMessageBox

        changelog_text = (
            "\n".join(f"• {item}" for item in changelog)
            if isinstance(changelog, list)
            else changelog
        )

        msg = QMessageBox(main_window)
        msg.setWindowTitle("🎉 تحديث جديد متاح!")
        msg.setText(f"الإصدار الجديد: {version}")
        msg.setInformativeText(f"التحسينات:\n{changelog_text}\n\nهل تريد التحديث الآن؟")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        msg.setIcon(QMessageBox.Icon.Information)

        if msg.exec() == QMessageBox.StandardButton.Yes:
            import webbrowser

            webbrowser.open(url)
            logger.info("[MainApp] المستخدم وافق على التحديث للإصدار %s", version)
        else:
            logger.info("[MainApp] المستخدم رفض التحديث للإصدار %s", version)

    # --- Global Exception Hook ---

    def _run_maintenance_safe(self):
        """تشغيل الصيانة بشكل آمن"""
        try:
            from core.db_maintenance import run_maintenance

            run_maintenance()
        except Exception as e:
            logger.error("خطأ في الصيانة: %s", e)

    def _sync_settings_safe(self):
        """مزامنة الإعدادات بشكل آمن"""
        try:
            if not getattr(self, "repository", None) or not getattr(self, "settings_service", None):
                return

            if not getattr(self.repository, "online", False):
                return

            def worker():
                try:
                    self.settings_service.sync_settings_from_cloud(self.repository)
                except Exception as e:
                    logger.error("خطأ في مزامنة الإعدادات: %s", e)

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            logger.error("خطأ في مزامنة الإعدادات: %s", e)

    def _check_updates_safe(self):
        """فحص التحديثات بشكل آمن"""
        try:
            from auto_updater import check_for_updates

            has_update, latest_version, download_url, changelog = check_for_updates()
            if has_update:
                logger.info("🆕 تحديث جديد متوفر: v%s", latest_version)
        except Exception as e:
            logger.error("خطأ في فحص التحديثات: %s", e)


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """معالج الأخطاء غير المتوقعة - محسّن وآمن"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # تسجيل الخطأ بشكل صحيح
    logger.error(
        "خطأ غير متوقع: %s: %s",
        exc_type.__name__,
        exc_value,
        exc_info=(exc_type, exc_value, exc_traceback),
    )

    # أخطاء Qt التي يمكن تجاهلها بأمان
    error_msg = str(exc_value).lower() if exc_value else ""
    safe_to_ignore = [
        "wrapped c/c++ object",
        "deleted",
        "destroyed",
        "qobject",
        "runtime error",
        "c/c++ object",
        "qthread",
        "qtimer",
        "connection",
        "signal",
    ]

    # تجاهل أخطاء Qt فقط
    if any(pattern in error_msg for pattern in safe_to_ignore):
        logger.debug("تجاهل خطأ Qt: %s", exc_value)
        return

    # للأخطاء الأخرى، نسجلها فقط بدون إيقاف البرنامج
    try:
        ErrorHandler.handle_exception(
            exception=exc_value,
            context="uncaught_exception",
            user_message=f"حدث خطأ غير متوقع: {exc_value}",
            show_dialog=False,  # لا نعرض dialog لتجنب التعطل
        )
    except Exception as e:
        # إذا فشل ErrorHandler، نطبع الخطأ على الأقل
        logger.debug(f"خطأ في معالج الأخطاء: {e}")


# ⚡ معالج أخطاء الـ Threads
def handle_thread_exception(args):
    """معالج أخطاء الـ Threads - محسّن وآمن"""
    try:
        exc_type = args.exc_type
        exc_value = args.exc_value
        exc_traceback = args.exc_traceback
        thread = args.thread

        # تسجيل خطأ الـ thread
        logger.error(
            "خطأ في Thread '%s': %s: %s",
            thread.name,
            exc_type.__name__,
            exc_value,
            exc_info=(exc_type, exc_value, exc_traceback),
        )

        # محاولة معالجة الخطأ
        try:
            ErrorHandler.handle_exception(
                exception=exc_value,
                context=f"thread_{thread.name}",
                user_message=f"حدث خطأ في العملية الخلفية: {exc_value}",
                show_dialog=False,
            )
        except Exception:
            print(f"خطأ في Thread {thread.name}: {exc_value}")

    except Exception as e:
        logger.error("فشل معالجة خطأ Thread: %s", e)


# تفعيل معالج الأخطاء العام
sys.excepthook = handle_uncaught_exception

# ⚡ تفعيل معالج أخطاء الـ Threads (Python 3.8+)
import threading

threading.excepthook = handle_thread_exception


def main() -> int:
    try:
        logger.info("تهيئة التطبيق...")
        app = SkyWaveERPApp()
        logger.info("بدء تشغيل الواجهة الرسومية...")
        app.run()
        return 0
    except KeyboardInterrupt:
        logger.info("تم إيقاف البرنامج بواسطة المستخدم (Ctrl+C)")
        return 0
    except Exception as e:
        logger.critical("فشل تشغيل البرنامج: %s", e, exc_info=True)
        ErrorHandler.handle_exception(
            exception=e,
            context="main_startup",
            user_message="فشل تشغيل البرنامج. يرجى التحقق من ملف الـ log للمزيد من التفاصيل.",
            show_dialog=True,
        )
        return 1
    finally:
        try:
            from ui.notification_system import NotificationManager

            NotificationManager.shutdown()
        except Exception:
            pass

        try:
            from core.realtime_sync import shutdown_realtime_sync

            shutdown_realtime_sync()
        except Exception:
            pass

        logger.info("=" * 80)
        logger.info("إغلاق التطبيق")
        logger.info("=" * 80)


if __name__ == "__main__":
    raise SystemExit(main())
