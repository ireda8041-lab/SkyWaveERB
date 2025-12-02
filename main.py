# الملف: main.py
# (ده ملف التشغيل الرئيسي للبرنامج كله)

import sys
import os
import time
from PyQt6.QtWidgets import QApplication, QDialog, QSplashScreen
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

# استيراد أدوات الموارد
from core.resource_utils import get_resource_path, get_font_path

# --- 0. إعداد نظام التسجيل والأخطاء (جديد) ---
from core.logger import LoggerSetup
from core.error_handler import ErrorHandler

# إعداد Logger أول شيء
logger = LoggerSetup.setup_logger()

# --- 1. استيراد "القلب" ---
from core.repository import Repository
from core.event_bus import EventBus
from core.sync_manager import SyncManager

# --- 2. استيراد "الأقسام" (العقل) ---
from services.accounting_service import AccountingService
from services.client_service import ClientService
from services.service_service import ServiceService
from services.expense_service import ExpenseService
from services.invoice_service import InvoiceService
from services.quotation_service import QuotationService
from services.project_service import ProjectService
from services.settings_service import SettingsService
from services.notification_service import NotificationService
from services.printing_service import PrintingService
from services.export_service import ExportService

# Authentication
from core.auth_models import AuthService, PermissionManager
from ui.login_window import LoginWindow

# Advanced Sync
from core.advanced_sync_manager import AdvancedSyncManager

# --- 3. استيراد "الواجهة" (الجسم) ---
# (هنعمل الملف ده في الخطوة الجاية)
from ui.main_window import MainWindow 


class SkyWaveERPApp:
    """
    (معدل) الكلاس الرئيسي (مع نظام معالجة الأخطاء).
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
        
        # تهيئة مدير المزامنة
        self.sync_manager = SyncManager(self.repository)
        self.sync_manager.load_pending_items()  # تحميل العمليات المعلقة
        
        # === المزامنة الذكية ثنائية الاتجاه ===
        # تأجيل المزامنة لبعد فتح البرنامج لتجنب التجميد
        # سيتم تشغيلها تلقائياً بعد 5 ثواني من فتح البرنامج
        
        logger.info("[MainApp] تم تجهيز المخزن (Repo) والإذاعة (Bus) والإعدادات.")
        logger.info("تم تهيئة مدير المزامنة (المزامنة التلقائية مفعلة)")

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

        logger.info("[MainApp] تم تجهيز كل الأقسام (Services).")
        logger.info("تم تهيئة خدمة الإشعارات والطباعة والمصادقة")

    def run(self):
        """
        تشغيل الواجهة الرسومية (UI) مع المصادقة.
        """
        app = QApplication(sys.argv)
        
        # === تحميل الخط العربي Cairo ===
        from PyQt6.QtGui import QFontDatabase
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
        from ui.styles import apply_styles
        apply_styles(app)
        
        # === عرض شاشة البداية (Splash Screen) ===
        logo_path = get_resource_path("logo.png")
        splash_pixmap = QPixmap(logo_path)
        if not splash_pixmap.isNull():
            # تكبير الصورة قليلاً للشاشة
            splash_pixmap = splash_pixmap.scaled(
                500, 500,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        
        splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint)
        splash.setWindowOpacity(0.90)
        splash.showMessage(
            "SkyWave ERP...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            Qt.GlobalColor.white
        )
        splash.show()
        app.processEvents()
        
        # محاكاة التحميل (2 ثانية)
        time.sleep(0.7)
        
        # عرض نافذة تسجيل الدخول أولاً
        login_window = LoginWindow(self.auth_service)
        splash.finish(login_window)  # إغلاق الشاشة عند ظهور تسجيل الدخول
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
        
        # إعادة تطبيق الأنماط الكاملة مع إزالة الإطارات البرتقالية
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
        
        main_window = MainWindow(
            current_user=current_user,  # إضافة المستخدم الحالي
            settings_service=self.settings_service,
            accounting_service=self.accounting_service,
            client_service=self.client_service,
            service_service=self.service_service,
            expense_service=self.expense_service,
            invoice_service=self.invoice_service,
            quotation_service=self.quotation_service,
            project_service=self.project_service,  # (المشاريع مسؤولة الآن عن الفوترة والدفعات)
            sync_manager=self.sync_manager,  # إضافة مدير المزامنة
            notification_service=self.notification_service,  # إضافة خدمة الإشعارات
            printing_service=self.printing_service,  # إضافة خدمة الطباعة
            export_service=self.export_service,  # إضافة خدمة التصدير
            advanced_sync_manager=self.advanced_sync_manager  # إضافة مدير المزامنة المتقدم
        )
        main_window.show()
        
        # تطبيق التوسيط على كل الجداول
        from ui.styles import apply_center_alignment_to_all_tables
        apply_center_alignment_to_all_tables(main_window)
        
        logger.info("[MainApp] البرنامج يعمل الآن.")
        sys.exit(app.exec())


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
