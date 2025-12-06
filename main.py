# الملف: main.py
# ruff: noqa: E402
"""
⚡ Sky Wave ERP - الملف الرئيسي
محسّن للسرعة القصوى
"""

import os
import sys

# ⚡ تحسين الأداء على Windows
if os.name == 'nt':
    os.environ['QT_QPA_PLATFORM'] = 'windows:darkmode=2'
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'

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

logger.info(f"⚡ {APP_NAME} v{CURRENT_VERSION}")

# --- 1. استيراد "القلب" ---
# Advanced Sync
from core.advanced_sync_manager import AdvancedSyncManager

# Authentication
from core.auth_models import AuthService
from core.event_bus import EventBus
from core.repository import Repository
from core.sync_manager import SyncManager

# --- 2. استيراد "الأقسام" (العقل) ---
from services.accounting_service import AccountingService
from services.client_service import ClientService
from services.expense_service import ExpenseService
from services.export_service import ExportService
from services.invoice_service import InvoiceService
from services.notification_service import NotificationService
from services.printing_service import PrintingService
from services.project_service import ProjectService
from services.quotation_service import QuotationService
from services.service_service import ServiceService
from services.settings_service import SettingsService
from services.smart_scan_service import SmartScanService
from ui.login_window import LoginWindow

# --- 3. استيراد "الواجهة" ---
from ui.main_window import MainWindow


class SkyWaveERPApp:
    """
    ⚡ الكلاس الرئيسي - محسّن للسرعة
    """
    def __init__(self):
        logger.info("="*80)
        logger.info("بدء تشغيل تطبيق Sky Wave ERP")
        logger.info("="*80)
        logger.info("[MainApp] بدء تشغيل تطبيق Sky Wave ERP...")

        # --- 1. تجهيز "القلب" ---
        self.repository = Repository()
        self.event_bus = EventBus()
        self.settings_service = SettingsService()

        # ⚡ تهيئة مدير المزامنة في Background
        self.sync_manager = SyncManager(self.repository)

        def load_sync_items():
            self.sync_manager.load_pending_items()
        import threading
        sync_thread = threading.Thread(target=load_sync_items, daemon=True)
        sync_thread.start()

        # ⚡ المزامنة التلقائية (Auto Sync) - معطلة عند البدء لتجنب التجميد
        from core.auto_sync import AutoSync
        self.auto_sync = AutoSync(self.repository)
        # سيتم تشغيلها يدوياً بعد فتح النافذة الرئيسية

        logger.info("[MainApp] تم تجهيز المخزن (Repo) والإذاعة (Bus) والإعدادات.")
        logger.info("⚡ المزامنة التلقائية ستبدأ بعد فتح النافذة الرئيسية")

        # تعيين Repository لـ TaskService
        from ui.todo_manager import TaskService
        TaskService.set_repository(self.repository)

        # --- 2. تجهيز "الأقسام" (حقن الاعتمادية) ---
        self.accounting_service = AccountingService(
            repository=self.repository,
            event_bus=self.event_bus
        )

        self.client_service = ClientService(repository=self.repository)
        self.service_service = ServiceService(
            repository=self.repository,
            event_bus=self.event_bus,
            settings_service=self.settings_service
        )
        self.expense_service = ExpenseService(
            repository=self.repository,
            event_bus=self.event_bus
        )

        self.invoice_service = InvoiceService(
            repository=self.repository,
            event_bus=self.event_bus
        )

        self.project_service = ProjectService(
            repository=self.repository,
            event_bus=self.event_bus,
            accounting_service=self.accounting_service,
            settings_service=self.settings_service
        )

        self.quotation_service = QuotationService(
            repository=self.repository,
            event_bus=self.event_bus,
            project_service=self.project_service
        )

        self.notification_service = NotificationService(
            repository=self.repository, event_bus=self.event_bus
        )

        # Template Service (for invoice templates)
        from services.template_service import TemplateService
        self.template_service = TemplateService(
            repository=self.repository,
            settings_service=self.settings_service
        )

        self.printing_service = PrintingService(
            settings_service=self.settings_service,
            template_service=self.template_service  # ✅ تمرير template_service
        )

        self.export_service = ExportService()

        # Authentication Service
        self.auth_service = AuthService(repository=self.repository)

        # Advanced Sync Manager
        self.advanced_sync_manager = AdvancedSyncManager(repository=self.repository)

        # 🧠 Smart Scan Service (AI Invoice Scanner)
        smart_scan_api_key = self.settings_service.get_setting("gemini_api_key")
        if not smart_scan_api_key:
            # محاولة قراءة من ملف الإعدادات المحلي
            try:
                import json
                with open("skywave_settings.json", encoding="utf-8") as f:
                    local_settings = json.load(f)
                    smart_scan_api_key = local_settings.get("smart_scan", {}).get("gemini_api_key")
            except Exception:
                pass
        
        self.smart_scan_service = SmartScanService(api_key=smart_scan_api_key)
        if self.smart_scan_service.is_available():
            logger.info("✅ Smart Scan Service (AI) Initialized.")
        else:
            logger.warning("⚠️ Smart Scan Service not available (missing API key)")

        # ⚡ التحقق من التحديثات في Background (لا يعطل البرنامج)
        def check_updates_background():
            try:
                from auto_updater import check_for_updates
                has_update, latest_version, download_url, changelog = check_for_updates()
                if has_update:
                    logger.info(f"🆕 تحديث جديد متوفر: v{latest_version}")
            except Exception as e:
                logger.warning(f"فشل التحقق من التحديثات: {e}")

        import threading
        update_thread = threading.Thread(target=check_updates_background, daemon=True)
        update_thread.start()

        logger.info("[MainApp] تم تجهيز كل الأقسام (Services).")
        logger.info("تم تهيئة خدمة الإشعارات والطباعة والمصادقة")

    def run(self):
        """
        تشغيل الواجهة الرسومية (UI) مع المصادقة.
        """
        # === منع الشاشة البيضاء على Windows ===
        import os
        if os.name == 'nt':  # Windows
            os.environ['QT_QPA_PLATFORM'] = 'windows:darkmode=2'

        app = QApplication(sys.argv)

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
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(COLORS['bg_dark']))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS['text_primary']))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(COLORS['bg_medium']))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS['bg_dark']))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS['bg_dark']))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS['text_primary']))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(COLORS['text_primary']))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(COLORS['bg_medium']))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS['text_primary']))
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(COLORS['primary']))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS['primary']))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
        app.setPalette(dark_palette)

        # تطبيق stylesheet إضافي
        app.setStyleSheet(f"""
            * {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['text_primary']};
            }}
            QWidget {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['text_primary']};
            }}
            QDialog {{
                background-color: {COLORS['bg_dark']};
            }}
            QMainWindow {{
                background-color: {COLORS['bg_dark']};
            }}
        """)

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
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        black_screen.setStyleSheet("background-color: #0a1929;")
        black_screen.setGeometry(screen)
        black_screen.show()
        app.processEvents()

        # عرض الـ splash فوق الشاشة السوداء
        splash.setWindowFlags(
            Qt.WindowType.SplashScreen |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
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
                logger.info(f"✅ تم تحميل الخط العربي: {font_families[0]}")
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

        role_display = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        logger.info(f"[MainApp] تم تسجيل دخول المستخدم: {current_user.username} ({role_display})")

        # === عرض splash screen مرة أخرى أثناء تحميل النافذة الرئيسية ===
        splash = ModernSplash()
        splash.show()
        app.processEvents()

        # إعادة تطبيق الأنماط الكاملة مع إزالة الإطارات البرتقالية
        splash.show_message("🎨 جاري تطبيق الأنماط النهائية...")
        app.processEvents()

        from ui.styles import COMPLETE_STYLESHEET
        app.setStyleSheet(COMPLETE_STYLESHEET + """
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
        """)

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
            quotation_service=self.quotation_service,
            project_service=self.project_service,
            sync_manager=self.sync_manager,
            notification_service=self.notification_service,
            printing_service=self.printing_service,
            export_service=self.export_service,
            advanced_sync_manager=self.advanced_sync_manager,
            smart_scan_service=self.smart_scan_service
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
                logger.warning(f"فشل تطبيق التوسيط: {e}")
        QTimer.singleShot(2000, apply_styles_later)

        # ⚡ تفعيل المزامنة التلقائية لجلب البيانات من السيرفر (بعد 3 ثواني فقط)
        QTimer.singleShot(3000, lambda: self.auto_sync.start_auto_sync(delay_seconds=0))
        logger.info("[MainApp] ⚡ المزامنة التلقائية ستبدأ بعد 3 ثواني (في الخلفية)")

        # ⚡ تفعيل التحديث التلقائي في الخلفية
        self._setup_auto_update(main_window)

        # ✅ ربط إشارة الإغلاق لتنظيف الموارد
        app.aboutToQuit.connect(self._cleanup_on_exit)
        main_window.destroyed.connect(self._cleanup_on_exit)

        # ✅ تفعيل الإغلاق عند إغلاق آخر نافذة
        app.setQuitOnLastWindowClosed(True)

        logger.info("[MainApp] البرنامج يعمل الآن.")

        # تشغيل التطبيق
        exit_code = app.exec()

        # ✅ تنظيف نهائي قبل الخروج
        self._cleanup_on_exit()

        sys.exit(exit_code)


    def _setup_auto_update(self, main_window):
        """تفعيل نظام التحديث التلقائي"""
        try:
            from services.auto_update_service import get_auto_update_service
            from version import CURRENT_VERSION

            self.auto_update_service = get_auto_update_service()

            # ربط إشارة التحديث المتاح
            self.auto_update_service.update_available.connect(
                lambda v, u, c: self._on_update_available(main_window, v, u, c)
            )

            # بدء خدمة التحديث التلقائي
            self.auto_update_service.start()
            logger.info(f"[MainApp] تم تفعيل التحديث التلقائي - الإصدار الحالي: {CURRENT_VERSION}")

        except Exception as e:
            logger.warning(f"[MainApp] فشل تفعيل التحديث التلقائي: {e}")

    def _cleanup_on_exit(self):
        """✅ تنظيف جميع الموارد عند إغلاق البرنامج"""
        logger.info("[MainApp] جاري تنظيف الموارد قبل الإغلاق...")

        try:
            # إيقاف المزامنة التلقائية
            if hasattr(self, 'auto_sync') and self.auto_sync:
                try:
                    self.auto_sync.stop_auto_sync()
                    logger.info("[MainApp] تم إيقاف المزامنة التلقائية")
                except Exception as e:
                    logger.warning(f"[MainApp] فشل إيقاف المزامنة التلقائية: {e}")

            # إيقاف خدمة التحديث التلقائي
            if hasattr(self, 'auto_update_service') and self.auto_update_service:
                try:
                    self.auto_update_service.stop()
                    logger.info("[MainApp] تم إيقاف خدمة التحديث التلقائي")
                except Exception as e:
                    logger.warning(f"[MainApp] فشل إيقاف خدمة التحديث: {e}")

            # إغلاق اتصال قاعدة البيانات
            if hasattr(self, 'repository') and self.repository:
                try:
                    if hasattr(self.repository, 'close'):
                        self.repository.close()
                    elif hasattr(self.repository, 'sqlite_conn'):
                        self.repository.sqlite_conn.close()
                    logger.info("[MainApp] تم إغلاق اتصال قاعدة البيانات")
                except Exception as e:
                    logger.warning(f"[MainApp] فشل إغلاق قاعدة البيانات: {e}")

            # إيقاف مدير المزامنة المتقدم
            if hasattr(self, 'advanced_sync_manager') and self.advanced_sync_manager:
                try:
                    # التحقق من أن الكائن لم يتم حذفه بواسطة Qt
                    from PyQt6.QtCore import QObject
                    if isinstance(self.advanced_sync_manager, QObject):
                        try:
                            # محاولة الوصول لخاصية للتأكد من أن الكائن لا يزال موجوداً
                            _ = self.advanced_sync_manager.objectName()
                            if hasattr(self.advanced_sync_manager, 'stop'):
                                self.advanced_sync_manager.stop()
                            logger.info("[MainApp] تم إيقاف مدير المزامنة المتقدم")
                        except RuntimeError:
                            # الكائن تم حذفه بالفعل بواسطة Qt
                            pass
                    elif hasattr(self.advanced_sync_manager, 'stop'):
                        self.advanced_sync_manager.stop()
                        logger.info("[MainApp] تم إيقاف مدير المزامنة المتقدم")
                except Exception as e:
                    # تجاهل أخطاء الكائنات المحذوفة
                    if "deleted" not in str(e).lower():
                        logger.warning(f"[MainApp] فشل إيقاف مدير المزامنة المتقدم: {e}")

            logger.info("[MainApp] ✅ تم تنظيف جميع الموارد بنجاح")

        except Exception as e:
            logger.error(f"[MainApp] خطأ أثناء تنظيف الموارد: {e}")

    def _on_update_available(self, main_window, version, url, changelog):
        """عند توفر تحديث جديد"""
        from PyQt6.QtWidgets import QMessageBox

        changelog_text = "\n".join(f"• {item}" for item in changelog) if isinstance(changelog, list) else changelog

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
            logger.info(f"[MainApp] المستخدم وافق على التحديث للإصدار {version}")
        else:
            logger.info(f"[MainApp] المستخدم رفض التحديث للإصدار {version}")


# --- Global Exception Hook ---
def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """معالج الأخطاء غير المتوقعة"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical("خطأ غير متوقع!", exc_info=(exc_type, exc_value, exc_traceback))
    ErrorHandler.handle_exception(
        exception=exc_value,
        context="uncaught_exception",
        user_message="حدث خطأ غير متوقع. سيتم إغلاق البرنامج.",
        show_dialog=True
    )

# تفعيل معالج الأخطاء العام
sys.excepthook = handle_uncaught_exception

# --- نقطة الانطلاق ---
if __name__ == "__main__":
    try:
        logger.info("تهيئة التطبيق...")
        app = SkyWaveERPApp()
        logger.info("بدء تشغيل الواجهة الرسومية...")
        app.run()
    except KeyboardInterrupt:
        # معالجة Ctrl+C بشكل نظيف
        logger.info("تم إيقاف البرنامج بواسطة المستخدم (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        # لو حصل أي خطأ فادح أثناء التشغيل
        logger.critical(f"فشل تشغيل البرنامج: {e}", exc_info=True)
        ErrorHandler.handle_exception(
            exception=e,
            context="main_startup",
            user_message="فشل تشغيل البرنامج. يرجى التحقق من ملف الـ log للمزيد من التفاصيل.",
            show_dialog=True
        )
        sys.exit(1)
    finally:
        logger.info("="*80)
        logger.info("إغلاق التطبيق")
        logger.info("="*80)
