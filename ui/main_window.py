# الملف: ui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QTableWidget, QTabWidget, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt

# (الأقسام اللي شغالين بيها)
from services.settings_service import SettingsService
from services.accounting_service import AccountingService
from services.client_service import ClientService
from services.service_service import ServiceService
from services.expense_service import ExpenseService
from services.invoice_service import InvoiceService
from services.quotation_service import QuotationService
from services.project_service import ProjectService
# (تم مسح PaymentService لأنه بقى جوه ProjectService)

# (استيراد التابات الجديدة)
from ui.dashboard_tab import DashboardTab
from ui.project_manager import ProjectManagerTab
from ui.quotation_manager import QuotationManagerTab
from ui.client_manager import ClientManagerTab
from ui.service_manager import ServiceManagerTab
from ui.accounting_manager import AccountingManagerTab  # (التاب الجديد أبو تابات داخلية)
from ui.expense_manager import ExpenseManagerTab  # (التاب الجديد بتاع المصروفات)
from ui.payments_manager import PaymentsManagerTab  # (الجديد) تاب الدفعات
from ui.settings_tab import SettingsTab
from ui.notification_widget import NotificationWidget  # (الجديد) ويدجت الإشعارات
from ui.shortcuts_help_dialog import ShortcutsHelpDialog  # (الجديد) نافذة مساعدة الاختصارات
from ui.loading_overlay import LoadingOverlay  # (الجديد) شاشة التحميل
from core.sync_manager import SyncManager  # (الجديد) مدير المزامنة
from core.keyboard_shortcuts import KeyboardShortcutManager  # (الجديد) مدير الاختصارات
from services.notification_service import NotificationService  # (الجديد) خدمة الإشعارات
from PyQt6.QtCore import QTimer


class MainWindow(QMainWindow):
    """
    (معدلة) الشاشة الرئيسية (بتابات المحاسبة والمصروفات الجديدة)
    """

    def __init__(
        self,
        current_user,  # المستخدم الحالي
        settings_service: SettingsService,
        accounting_service: AccountingService,
        client_service: ClientService,
        service_service: ServiceService,
        expense_service: ExpenseService,
        invoice_service: InvoiceService,
        quotation_service: QuotationService,
        project_service: ProjectService,
        sync_manager: SyncManager = None,
        notification_service: NotificationService = None,
        printing_service = None,
        export_service = None,
        advanced_sync_manager = None,
    ):
        super().__init__()
        
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
        self.quotation_service = quotation_service
        self.project_service = project_service
        self.sync_manager = sync_manager
        self.notification_service = notification_service
        self.printing_service = printing_service
        self.export_service = export_service
        self.advanced_sync_manager = advanced_sync_manager

        role_display = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        self.setWindowTitle(f"Sky Wave ERP - {current_user.full_name or current_user.username} ({role_display})")
        self.setGeometry(100, 100, 1200, 800)
        
        # إنشاء شريط الأدوات (Toolbar) في الأعلى
        toolbar = self.addToolBar("الأدوات الرئيسية")
        toolbar.setMovable(False)
        
        # إضافة spacer لدفع الويدجتات إلى اليمين
        from PyQt6.QtWidgets import QWidget, QSizePolicy
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )
        toolbar.addWidget(spacer)
        
        # إضافة ويدجت الإشعارات في شريط الأدوات (أعلى)
        if self.notification_service:
            self.notification_widget = NotificationWidget(self.notification_service)
            toolbar.addWidget(self.notification_widget)
            
            # إعداد مؤقت لفحص مواعيد استحقاق المشاريع (كل 24 ساعة)
            from PyQt6.QtCore import QTimer
            self.project_check_timer = QTimer()
            self.project_check_timer.timeout.connect(
                self.notification_service.check_project_due_dates
            )
            self.project_check_timer.start(86400000)  # 24 ساعة بالميلي ثانية
            
            # فحص أولي عند بدء التطبيق
            self.notification_service.check_project_due_dates()
        
        # إعداد اختصارات لوحة المفاتيح
        self.shortcuts_manager = KeyboardShortcutManager(self)
        self.shortcuts_manager.setup_shortcuts()
        self._connect_shortcuts()

        # --- 1. إنشاء الـ Tab Widget ---
        self.tabs = QTabWidget()
        
        # تحسين شكل التابات (Dark Blue Theme - زي الصورة)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #003366;
                background-color: #001a3a;
                border-radius: 8px;
            }
            
            QTabBar::tab {
                background-color: #002040;
                color: #ffffff;
                padding: 12px 20px;
                margin: 2px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                min-width: 120px;
                border: 2px solid transparent;
            }
            
            QTabBar::tab:hover {
                background-color: #003366;
                border: 2px solid #4a90e2;
                transform: translateY(-2px);
            }
            
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a90e2, stop:1 #357abd);
                color: white;
                border: 2px solid #4a90e2;
                box-shadow: 0 4px 8px rgba(74, 144, 226, 0.3);
            }
            
            QTabBar::tab:!selected {
                margin-top: 4px;
            }
            
            QTabBar {
                qproperty-drawBase: 0;
            }
        """)

        # --- 2. إنشاء خدمة القوالب أولاً ---
        from services.template_service import TemplateService
        self.template_service = TemplateService(
            repository=self.accounting_service.repo,
            settings_service=self.settings_service
        )
        
        # تحديث template_service في printing_service إذا كان موجوداً
        if self.printing_service:
            self.printing_service.template_service = self.template_service

        # --- 3. إنشاء التابات (بالترتيب الصح) ---
        self.dashboard_tab = DashboardTab(self.accounting_service)
        self.tabs.insertTab(0, self.dashboard_tab, "🏠 الصفحة الرئيسية")

        self.projects_tab = ProjectManagerTab(
            self.project_service,
            self.client_service,
            self.service_service,
            self.accounting_service,
            self.printing_service,
            template_service=self.template_service,
        )
        self.tabs.insertTab(1, self.projects_tab, "🚀 المشاريع")

        self.quotes_tab = QuotationManagerTab(
            self.quotation_service,
            self.client_service,
            self.service_service,
            self.settings_service,
        )
        self.tabs.insertTab(2, self.quotes_tab, "📝 عروض الأسعار")

        # (الجديد) إضافة تاب المصروفات (لوحده)
        self.expense_tab = ExpenseManagerTab(
            self.expense_service,
            self.accounting_service,
            self.project_service,
        )
        self.tabs.insertTab(3, self.expense_tab, "💳 المصروفات")

        # (الجديد) إضافة تاب الدفعات (التحصيلات)
        self.payments_tab = PaymentsManagerTab(
            self.project_service,
            self.accounting_service,
            self.client_service,
            current_user=self.current_user,
        )
        self.tabs.insertTab(4, self.payments_tab, "💰 الدفعات")

        self.clients_tab = ClientManagerTab(self.client_service)
        self.tabs.insertTab(5, self.clients_tab, "👤 العملاء")

        self.services_tab = ServiceManagerTab(self.service_service)
        self.tabs.insertTab(6, self.services_tab, "🛠️ الخدمات والباقات")

        # (الجديد) إضافة تاب المحاسبة (الجديد أبو تابات داخلية)
        self.accounting_tab = AccountingManagerTab(
            self.expense_service,
            self.accounting_service,
            self.project_service,
        )
        self.tabs.insertTab(7, self.accounting_tab, "📊 المحاسبة")
        
        
        self.settings_tab = SettingsTab(self.settings_service, repository=self.accounting_service.repo)
        self.tabs.insertTab(9, self.settings_tab, "🔧 الإعدادات")

        # تطبيق الصلاحيات حسب دور المستخدم (بعد إنشاء كل التابات)
        self.apply_permissions()

        # --- 3. إضافة شريط الحالة ---
        from ui.status_bar_widget import StatusBarWidget
        self.status_bar = StatusBarWidget()
        
        # تعيين المستخدم الحالي في شريط الحالة
        self.status_bar.set_current_user(self.current_user)
        
        # ربط مدير المزامنة المتقدم بشريط الحالة
        if self.advanced_sync_manager:
            self.advanced_sync_manager.connection_status_changed.connect(
                lambda online: self.status_bar.update_sync_status("synced" if online else "offline")
            )
            self.advanced_sync_manager.sync_status_changed.connect(self.status_bar.update_sync_status)
            self.advanced_sync_manager.sync_progress.connect(self.status_bar.update_sync_progress)
            self.advanced_sync_manager.notification_ready.connect(self.status_bar.show_notification)
        
        # إضافة شريط الحالة للنافذة
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.status_bar)
        self.setCentralWidget(main_widget)
        
        # === شاشة التحميل المتراكبة (بعد تعيين central widget) ===
        self.loading_overlay = LoadingOverlay(self)
        self.loading_overlay.set_message("جاري تجهيز البيانات...")
        self.loading_overlay.setGeometry(self.rect())
        self.loading_overlay.raise_()  # رفع فوق كل العناصر
        self.loading_overlay.show()

        # --- 4. إعداد المزامنة (إذا لم يتم تمريرها) ---
        if not self.sync_manager:
            self.sync_manager = SyncManager(self.accounting_service.repo)
        
        # إعداد المزامنة التلقائية كل 10 دقائق
        self.setup_auto_sync()

        # --- 4. تحميل البيانات ---
        self.load_all_data()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # إخفاء شاشة التحميل بعد تحميل البيانات
        QTimer.singleShot(2000, self._finish_loading)

    def on_tab_changed(self, index):
        """ (معدلة) بالتابات الجديدة """
        tab_name = self.tabs.tabText(index)

        if tab_name == "🏠 الصفحة الرئيسية":
            self.dashboard_tab.refresh_data()
        elif tab_name == "🚀 المشاريع":
            self.projects_tab.service_service = self.service_service
            self.projects_tab.accounting_service = self.accounting_service
            self.projects_tab.load_projects_data()
        elif tab_name == "📝 عروض الأسعار":
            self.quotes_tab.project_service = self.project_service
            self.quotes_tab.load_quotations_data()
        elif tab_name == "💳 المصروفات":  # (جديد)
            self.expense_tab.load_expenses_data()
        elif tab_name == "💰 الدفعات":  # (جديد) تاب الدفعات
            self.payments_tab.load_payments_data()
        elif tab_name == "👤 العملاء":
            self.clients_tab.load_clients_data()
        elif tab_name == "🛠️ الخدمات والباقات":
            self.services_tab.load_services_data()
        elif tab_name == "📊 المحاسبة":  # (جديد)
            self.accounting_tab.project_service = self.project_service
            # تحديث بيانات المحاسبة
            pass
        elif tab_name == "🔧 الإعدادات":
            self.settings_tab.load_settings_data()

    def load_all_data(self):
        """
        تحمل البيانات للتاب المفتوح حالياً
        """
        self.on_tab_changed(self.tabs.currentIndex())
    
    def setup_auto_sync(self):
        """
        إعداد المزامنة التلقائية في الخلفية
        """
        from PyQt6.QtCore import QTimer
        
        # مؤقت للمزامنة التلقائية كل 10 دقائق (600000 ميلي ثانية)
        self.auto_sync_timer = QTimer(self)
        self.auto_sync_timer.timeout.connect(self.trigger_background_sync)
        self.auto_sync_timer.start(600000)  # 10 دقائق
        
        # تشغيل المزامنة فوراً عند بدء التطبيق (بعد ثانيتين)
        QTimer.singleShot(2000, self.trigger_background_sync)
        
        print("INFO: تم تفعيل المزامنة التلقائية (كل 10 دقائق)")
    
    def trigger_background_sync(self):
        """
        تشغيل المزامنة في الخلفية
        """
        try:
            if not self.sync_manager:
                print("INFO: مدير المزامنة غير متاح")
                return
            
            # التحقق من الاتصال
            if not self.sync_manager.repository.online:
                print("INFO: تخطي المزامنة التلقائية (غير متصل)")
                return
            
            print("INFO: بدء المزامنة التلقائية في الخلفية...")
            
            # تشغيل المزامنة
            self.sync_manager.start_sync()
            
        except Exception as e:
            print(f"ERROR: خطأ في المزامنة التلقائية: {e}")
    
    def on_auto_sync_completed(self, result: dict):
        """
        معالج حدث اكتمال المزامنة التلقائية
        """
        try:
            synced = result.get('synced', 0)
            failed = result.get('failed', 0)
            print(f"INFO: اكتملت المزامنة التلقائية - نجح: {synced}, فشل: {failed}")
            
            # تحديث الواجهة إذا كانت هناك تغييرات
            if synced > 0:
                self.on_sync_completed()
        except Exception as e:
            print(f"ERROR: خطأ في معالجة نتيجة المزامنة التلقائية: {e}")
    
    def on_sync_completed(self):
        """
        معالج حدث اكتمال المزامنة
        يقوم بتحديث البيانات في التاب الحالي
        """
        try:
            # تحديث البيانات في التاب الحالي
            current_index = self.tabs.currentIndex()
            self.on_tab_changed(current_index)
        except Exception as e:
            print(f"خطأ في تحديث البيانات بعد المزامنة: {e}")

    def _finish_loading(self):
        """إنهاء شاشة التحميل بعد تجهيز البيانات"""
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.fade_out()
    
    def showEvent(self, event):
        """عند ظهور النافذة - تحديث حجم شاشة التحميل"""
        super().showEvent(event)
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            # تأخير قصير للتأكد من أن النافذة ظهرت بالكامل
            QTimer.singleShot(50, self._show_loading_overlay)
    
    def _show_loading_overlay(self):
        """عرض شاشة التحميل بعد ظهور النافذة"""
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.setGeometry(self.rect())
            self.loading_overlay.raise_()
            self.loading_overlay.show()
            print(f"INFO: [MainWindow] تم عرض شاشة التحميل - الحجم: {self.loading_overlay.size()}")
    
    def resizeEvent(self, event):
        """تغيير حجم شاشة التحميل مع النافذة"""
        super().resizeEvent(event)
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.setGeometry(self.rect())

    def _connect_shortcuts(self):
        """ربط الاختصارات بالإجراءات"""
        # اختصارات الإنشاء
        self.shortcuts_manager.new_project.connect(self._on_new_project)
        self.shortcuts_manager.new_client.connect(self._on_new_client)
        self.shortcuts_manager.new_expense.connect(self._on_new_expense)
        
        # اختصارات التنقل والبحث
        self.shortcuts_manager.search_activated.connect(self._on_search_activated)
        self.shortcuts_manager.refresh_data.connect(self._on_refresh_data)
        
        # اختصارات المساعدة
        self.shortcuts_manager.show_help.connect(self._on_show_help)
    
    def _on_new_project(self):
        """معالج اختصار مشروع جديد"""
        # التبديل إلى تاب المشاريع
        self.tabs.setCurrentIndex(1)
        # محاولة فتح نافذة مشروع جديد
        if hasattr(self.projects_tab, 'on_add_project'):
            self.projects_tab.on_add_project()
    
    def _on_new_client(self):
        """معالج اختصار عميل جديد"""
        # التبديل إلى تاب العملاء
        self.tabs.setCurrentIndex(5)
        # محاولة فتح نافذة عميل جديد
        if hasattr(self.clients_tab, 'on_add_client'):
            self.clients_tab.on_add_client()
    
    def _on_new_expense(self):
        """معالج اختصار مصروف جديد"""
        # التبديل إلى تاب المصروفات
        self.tabs.setCurrentIndex(3)
        # محاولة فتح نافذة مصروف جديد
        if hasattr(self.expense_tab, 'on_add_expense'):
            self.expense_tab.on_add_expense()
    
    def _on_search_activated(self):
        """معالج اختصار تفعيل البحث"""
        # Search feature not implemented yet
        pass
    
    def _on_refresh_data(self):
        """معالج اختصار تحديث البيانات"""
        # تحديث التاب الحالي
        current_index = self.tabs.currentIndex()
        self.on_tab_changed(current_index)
    
    def _on_show_help(self):
        """معالج اختصار عرض المساعدة"""
        dialog = ShortcutsHelpDialog(self.shortcuts_manager, self)
        dialog.exec()
    
    def apply_permissions(self):
        """تطبيق الصلاحيات حسب دور المستخدم"""
        from core.auth_models import PermissionManager, UserRole
        
        user_role = self.current_user.role
        role_display = user_role.value if hasattr(user_role, 'value') else str(user_role)
        print(f"INFO: [MainWindow] تطبيق صلاحيات الدور: {role_display}")
        
        # قائمة التابات مع أسمائها الداخلية
        tab_permissions = {
            'dashboard': 0,      # الداشبورد
            'projects': 1,       # المشاريع
            'quotes': 2,         # عروض الأسعار
            'expenses': 3,       # المصروفات
            'payments': 4,       # الدفعات (جديد)
            'clients': 5,        # العملاء
            'services': 6,       # الخدمات
            'accounting': 7,     # المحاسبة
            'settings': 8        # الإعدادات
        }
        
        # إخفاء التابات غير المسموحة (باستخدام النظام الجديد)
        tabs_to_hide = []
        for tab_name, tab_index in tab_permissions.items():
            if not PermissionManager.can_access_tab(self.current_user, tab_name):
                tabs_to_hide.append((tab_index, tab_name))
        
        # إخفاء التابات من الآخر للأول لتجنب تغيير الفهارس
        for tab_index, tab_name in sorted(tabs_to_hide, reverse=True):
            if tab_index < self.tabs.count():
                removed_tab = self.tabs.widget(tab_index)
                self.tabs.removeTab(tab_index)
                print(f"INFO: [MainWindow] تم إخفاء تاب: {tab_name}")
        
        # تطبيق قيود إضافية حسب الدور
        if user_role == UserRole.SALES:
            # مندوب المبيعات: قيود إضافية
            print("INFO: [MainWindow] تطبيق قيود مندوب المبيعات")
            # يمكن إضافة قيود أخرى هنا مثل إخفاء أزرار الحذف
        
        elif user_role == UserRole.ACCOUNTANT:
            # المحاسب: قيود محدودة
            print("INFO: [MainWindow] تطبيق قيود المحاسب")
        
        elif user_role == UserRole.ADMIN:
            # المدير: لا توجد قيود
            print("INFO: [MainWindow] المدير - جميع الصلاحيات متاحة")
        
        # تحديث شريط العنوان ليعكس الصلاحيات
        role_display = {
            UserRole.ADMIN: "مدير النظام",
            UserRole.ACCOUNTANT: "محاسب", 
            UserRole.SALES: "مندوب مبيعات"
        }
        
        self.setWindowTitle(
            f"Sky Wave ERP - {self.current_user.full_name or self.current_user.username} "
            f"({role_display.get(user_role, str(user_role))})"
        )
    def setup_title_bar(self):
        """تخصيص شريط العنوان بألوان البرنامج"""
        try:
            import platform
            
            # للويندوز - تخصيص شريط العنوان
            if platform.system() == "Windows":
                try:
                    import ctypes
                    from ctypes import wintypes
                    
                    # الحصول على handle النافذة
                    hwnd = int(self.winId())
                    
                    # تعريف الألوان (BGR format)
                    # لون أزرق غامق أكثر يناسب البرنامج
                    title_bar_color = 0x291301  # لون أزرق غامق (#011329 في BGR) 
                    title_text_color = 0xffffff  # أبيض للنص
                    
                    # تطبيق لون شريط العنوان
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 35, ctypes.byref(ctypes.c_int(title_bar_color)), 4
                    )
                    
                    # تطبيق لون نص شريط العنوان
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 36, ctypes.byref(ctypes.c_int(title_text_color)), 4
                    )
                    
                except Exception as e:
                    print(f"تعذر تخصيص شريط العنوان: {e}")
            
            # تطبيق نمط عام للنافذة
            self.setStyleSheet("""
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
            """)
            
        except Exception as e:
            print(f"خطأ في تخصيص شريط العنوان: {e}")