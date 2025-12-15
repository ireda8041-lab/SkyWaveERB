# الملف: ui/settings_tab.py
"""
تاب الإعدادات المتقدمة - يشمل:
- إدارة الحسابات
- إدارة العملات
- بيانات الشركة
- إدارة المستخدمين
- النسخ الاحتياطي
"""

import json
import os
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.repository import Repository
from services.settings_service import SettingsService
from ui.currency_editor_dialog import CurrencyEditorDialog
from ui.styles import BUTTON_STYLES, TABLE_STYLE_DARK, create_centered_item
from ui.smart_combobox import SmartFilterComboBox


class SettingsTab(QWidget):
    """تاب الإعدادات المتقدمة مع تابات فرعية."""

    def __init__(self, settings_service: SettingsService, repository: Repository | None = None, current_user=None, parent=None):
        super().__init__(parent)
        self.settings_service = settings_service
        self.repository = repository
        self.current_user = current_user

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


        # إنشاء التابات الفرعية
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # تاب بيانات الشركة
        self.company_tab = QWidget()
        self.tabs.addTab(self.company_tab, "🏢 بيانات الشركة")
        self.setup_company_tab()

        # تاب إدارة العملات
        self.currency_tab = QWidget()
        self.tabs.addTab(self.currency_tab, "💱 إدارة العملات")
        self.setup_currency_tab()

        # تاب إدارة المستخدمين
        self.users_tab = QWidget()
        self.tabs.addTab(self.users_tab, "👥 إدارة المستخدمين")
        self.setup_users_tab()

        # تاب النسخ الاحتياطي
        self.backup_tab = QWidget()
        self.tabs.addTab(self.backup_tab, "💾 النسخ الاحتياطي")
        self.setup_backup_tab()

        # تاب الحسابات الافتراضية
        self.default_accounts_tab = QWidget()
        self.tabs.addTab(self.default_accounts_tab, "🔗 الحسابات الافتراضية")
        self.setup_default_accounts_tab()

        # تاب قوالب الفواتير
        from ui.template_settings import TemplateSettings
        self.template_tab = TemplateSettings(self.settings_service)
        self.tabs.addTab(self.template_tab, "🎨 قوالب الفواتير")

        # تاب التحديثات
        self.update_tab = QWidget()
        self.tabs.addTab(self.update_tab, "🔄 التحديثات")
        self.setup_update_tab()

        # 🏢 تاب الموارد البشرية الشامل (دمج الموظفين + HR)
        from ui.unified_hr_manager import UnifiedHRManager
        self.hr_tab = UnifiedHRManager()
        self.tabs.addTab(self.hr_tab, "🏢 الموارد البشرية")

        # تطبيق الأسهم على كل الـ widgets
        from ui.styles import apply_arrows_to_all_widgets
        apply_arrows_to_all_widgets(self)

        # ربط تغيير التاب الفرعي لتحميل البيانات
        self.tabs.currentChanged.connect(self._on_sub_tab_changed)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_settings_data() - يتم استدعاؤها من MainWindow
        # self.load_users() - يتم استدعاؤها من MainWindow

    def _on_sub_tab_changed(self, index):
        """معالج تغيير التاب الفرعي"""
        tab_text = self.tabs.tabText(index)
        print(f"INFO: [SettingsTab] تم اختيار التاب الفرعي: {tab_text}")

        if "المستخدمين" in tab_text:
            self.load_users()

    def setup_company_tab(self):
        """إعداد تاب بيانات الشركة - تصميم احترافي متجاوب"""
        from PyQt6.QtWidgets import QFrame, QGridLayout, QSizePolicy
        
        layout = QVBoxLayout(self.company_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 15, 20, 15)
        
        # ستايل الحقول المحسن
        input_style = """
            QLineEdit {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                min-height: 18px;
            }
            QLineEdit:focus {
                border: 1px solid #0A6CF1;
            }
            QLineEdit:hover {
                border: 1px solid #3d6a9f;
            }
        """
        label_style = "color: #60a5fa; font-size: 11px; font-weight: bold;"
        
        # === التخطيط الأفقي الرئيسي ===
        main_h = QHBoxLayout()
        main_h.setSpacing(20)
        
        # === الجانب الأيسر: الحقول ===
        fields_frame = QFrame()
        fields_frame.setStyleSheet("""
            QFrame {
                background: rgba(13, 33, 55, 0.5);
                border: 1px solid rgba(45, 74, 111, 0.4);
                border-radius: 10px;
            }
        """)
        fields_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        fields_container = QVBoxLayout(fields_frame)
        fields_container.setContentsMargins(15, 15, 15, 15)
        fields_container.setSpacing(10)
        
        # عنوان القسم
        fields_title = QLabel("📋 بيانات الشركة")
        fields_title.setStyleSheet("color: #93C5FD; font-size: 13px; font-weight: bold;")
        fields_container.addWidget(fields_title)
        
        fields_layout = QGridLayout()
        fields_layout.setSpacing(8)
        fields_layout.setColumnStretch(0, 1)
        fields_layout.setColumnStretch(1, 1)
        
        # اسم الشركة
        name_lbl = QLabel("🏢 اسم الشركة")
        name_lbl.setStyleSheet(label_style)
        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("أدخل اسم الشركة...")
        self.company_name_input.setStyleSheet(input_style)
        fields_layout.addWidget(name_lbl, 0, 0)
        fields_layout.addWidget(self.company_name_input, 1, 0)
        
        # العنوان
        addr_lbl = QLabel("📍 العنوان")
        addr_lbl.setStyleSheet(label_style)
        self.company_address_input = QLineEdit()
        self.company_address_input.setPlaceholderText("العنوان الكامل...")
        self.company_address_input.setStyleSheet(input_style)
        fields_layout.addWidget(addr_lbl, 0, 1)
        fields_layout.addWidget(self.company_address_input, 1, 1)
        
        # الهاتف
        phone_lbl = QLabel("📱 رقم الهاتف")
        phone_lbl.setStyleSheet(label_style)
        self.company_phone_input = QLineEdit()
        self.company_phone_input.setPlaceholderText("+20 10 123 4567")
        self.company_phone_input.setStyleSheet(input_style)
        fields_layout.addWidget(phone_lbl, 2, 0)
        fields_layout.addWidget(self.company_phone_input, 3, 0)
        
        # البريد
        email_lbl = QLabel("📧 البريد الإلكتروني")
        email_lbl.setStyleSheet(label_style)
        self.company_email_input = QLineEdit()
        self.company_email_input.setPlaceholderText("info@company.com")
        self.company_email_input.setStyleSheet(input_style)
        fields_layout.addWidget(email_lbl, 2, 1)
        fields_layout.addWidget(self.company_email_input, 3, 1)
        
        # الموقع
        web_lbl = QLabel("🌐 موقع الشركة")
        web_lbl.setStyleSheet(label_style)
        self.company_website_input = QLineEdit()
        self.company_website_input.setPlaceholderText("www.company.com")
        self.company_website_input.setStyleSheet(input_style)
        fields_layout.addWidget(web_lbl, 4, 0)
        fields_layout.addWidget(self.company_website_input, 5, 0)
        
        # الرقم الضريبي
        vat_lbl = QLabel("🔢 الرقم الضريبي")
        vat_lbl.setStyleSheet(label_style)
        self.company_vat_input = QLineEdit()
        self.company_vat_input.setPlaceholderText("أدخل الرقم الضريبي")
        self.company_vat_input.setStyleSheet(input_style)
        fields_layout.addWidget(vat_lbl, 4, 1)
        fields_layout.addWidget(self.company_vat_input, 5, 1)
        
        fields_container.addLayout(fields_layout)
        main_h.addWidget(fields_frame, 3)
        
        # === الجانب الأيمن: اللوجو ===
        logo_frame = QFrame()
        logo_frame.setStyleSheet("""
            QFrame {
                background: rgba(13, 33, 55, 0.5);
                border: 1px solid rgba(45, 74, 111, 0.4);
                border-radius: 10px;
            }
        """)
        logo_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        logo_container = QVBoxLayout(logo_frame)
        logo_container.setContentsMargins(15, 15, 15, 15)
        logo_container.setSpacing(10)
        logo_container.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        logo_title = QLabel("🖼️ شعار الشركة")
        logo_title.setStyleSheet("color: #93C5FD; font-size: 13px; font-weight: bold;")
        logo_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_container.addWidget(logo_title)
        
        # إطار اللوجو
        self.logo_preview = QLabel()
        self.logo_preview.setFixedSize(130, 130)
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_preview.setStyleSheet("""
            QLabel {
                background: #0d2137;
                border: 2px dashed #3d6a9f;
                border-radius: 10px;
                color: #64748B;
                font-size: 11px;
            }
        """)
        self.logo_preview.setText("📷\nلا يوجد شعار")
        logo_container.addWidget(self.logo_preview, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # أزرار اللوجو
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.select_logo_btn = QPushButton("📷 اختيار")
        self.select_logo_btn.setStyleSheet("""
            QPushButton {
                background: #0A6CF1;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background: #2563eb; }
        """)
        self.select_logo_btn.clicked.connect(self.select_logo_file)
        
        self.remove_logo_btn = QPushButton("🗑️")
        self.remove_logo_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.15);
                color: #FCA5A5;
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 0.3); }
        """)
        self.remove_logo_btn.clicked.connect(self._remove_logo)
        
        btn_layout.addWidget(self.select_logo_btn)
        btn_layout.addWidget(self.remove_logo_btn)
        logo_container.addLayout(btn_layout)
        
        # نص توضيحي
        hint_lbl = QLabel("PNG, JPG • 200×200 px")
        hint_lbl.setStyleSheet("color: #64748B; font-size: 9px;")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_container.addWidget(hint_lbl)
        
        main_h.addWidget(logo_frame, 1)
        
        layout.addLayout(main_h, 1)
        
        # زر الحفظ
        self.save_company_btn = QPushButton("💾 حفظ بيانات الشركة")
        self.save_company_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #34d399);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 30px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #059669; }
        """)
        self.save_company_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_company_btn)

    def _remove_logo(self):
        """حذف اللوجو الحالي"""
        self.logo_preview.clear()
        self.logo_preview.setText("📷\nلا يوجد شعار")
        self.logo_preview.setProperty("logo_path", "")

    def setup_currency_tab(self):
        """إعداد تاب إدارة العملات"""
        layout = QVBoxLayout(self.currency_tab)

        # معلومات العملة الأساسية
        base_info = QLabel("💰 العملة الأساسية للنظام: الجنيه المصري (EGP)")
        base_info.setStyleSheet("""
            background-color: #0A6CF1;
            color: white;
            padding: 10px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
        """)
        layout.addWidget(base_info)

        # أزرار التحكم
        buttons_layout = QHBoxLayout()

        self.add_currency_btn = QPushButton("➕ إضافة عملة")
        self.add_currency_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.add_currency_btn.clicked.connect(self.add_currency)

        self.edit_currency_btn = QPushButton("✏️ تعديل (مع جلب السعر)")
        self.edit_currency_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_currency_btn.clicked.connect(self.edit_currency)

        self.delete_currency_btn = QPushButton("🗑️ حذف")
        self.delete_currency_btn.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_currency_btn.clicked.connect(self.delete_currency)

        self.refresh_currency_btn = QPushButton("🔄 تحديث")
        self.refresh_currency_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_currency_btn.clicked.connect(self.load_currencies)

        self.update_rates_btn = QPushButton("🌐 تحديث الأسعار من الإنترنت")
        self.update_rates_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.update_rates_btn.clicked.connect(self.update_exchange_rates)

        buttons_layout.addWidget(self.add_currency_btn)
        buttons_layout.addWidget(self.edit_currency_btn)
        buttons_layout.addWidget(self.delete_currency_btn)
        buttons_layout.addWidget(self.refresh_currency_btn)
        buttons_layout.addWidget(self.update_rates_btn)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # جدول العملات
        self.currencies_table = QTableWidget()
        self.currencies_table.setColumnCount(6)
        self.currencies_table.setHorizontalHeaderLabels([
            "#", "الرمز", "الاسم", "الرمز", "سعر الصرف", "الحالة"
        ])
        h_header = self.currencies_table.horizontalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # #
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # الرمز
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # الاسم - يتمدد
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # الرمز
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # سعر الصرف
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
        self.currencies_table.setAlternatingRowColors(True)
        self.currencies_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.currencies_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.currencies_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.currencies_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.currencies_table.setTabKeyNavigation(False)
        self.currencies_table.setStyleSheet(self._get_table_style())
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.currencies_table)
        layout.addWidget(self.currencies_table)

        self.load_currencies()

    def setup_users_tab(self):
        """إعداد تاب إدارة المستخدمين"""
        layout = QVBoxLayout(self.users_tab)

        # التحقق من صلاحية إدارة المستخدمين
        from core.auth_models import PermissionManager
        can_manage_users = True
        if self.current_user:
            can_manage_users = PermissionManager.has_feature(self.current_user, 'user_management')

        # أزرار التحكم
        buttons_layout = QHBoxLayout()

        self.add_user_btn = QPushButton("➕ إضافة مستخدم")
        self.add_user_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.add_user_btn.clicked.connect(self.add_user)
        self.add_user_btn.setEnabled(can_manage_users)

        self.edit_user_btn = QPushButton("✏️ تعديل")
        self.edit_user_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_user_btn.clicked.connect(self.edit_user)
        self.edit_user_btn.setEnabled(can_manage_users)

        self.permissions_btn = QPushButton("🔐 تحرير الصلاحيات")
        self.permissions_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.permissions_btn.clicked.connect(self.edit_user_permissions)
        self.permissions_btn.setEnabled(can_manage_users)

        self.delete_user_btn = QPushButton("🗑️ تعطيل")
        self.delete_user_btn.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_user_btn.clicked.connect(self.delete_user)
        self.delete_user_btn.setEnabled(can_manage_users)

        self.activate_user_btn = QPushButton("✅ تفعيل")
        self.activate_user_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.activate_user_btn.clicked.connect(self.activate_user)
        self.activate_user_btn.setEnabled(can_manage_users)

        self.refresh_users_btn = QPushButton("🔄 تحديث")
        self.refresh_users_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_users_btn.clicked.connect(self.load_users)

        buttons_layout.addWidget(self.add_user_btn)
        buttons_layout.addWidget(self.edit_user_btn)
        buttons_layout.addWidget(self.permissions_btn)
        buttons_layout.addWidget(self.delete_user_btn)
        buttons_layout.addWidget(self.activate_user_btn)
        buttons_layout.addWidget(self.refresh_users_btn)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # رسالة تنبيه إذا لم يكن لديه صلاحية
        if not can_manage_users:
            warning_label = QLabel("⚠️ ليس لديك صلاحية إدارة المستخدمين. يمكنك فقط عرض القائمة.")
            warning_label.setStyleSheet("color: #f59e0b; background-color: #422006; padding: 10px; border-radius: 5px; margin-bottom: 10px;")
            layout.addWidget(warning_label)

        # جدول المستخدمين
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(7)
        self.users_table.setHorizontalHeaderLabels([
            "#", "اسم المستخدم", "الاسم الكامل", "البريد", "الدور", "الحالة", "تاريخ الإنشاء"
        ])
        h_header = self.users_table.horizontalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # #
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # اسم المستخدم - يتمدد
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # الاسم الكامل - يتمدد
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # البريد - يتمدد
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # الدور
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
            h_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # تاريخ الإنشاء
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.users_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.users_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.users_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.users_table.setTabKeyNavigation(False)
        self.users_table.setStyleSheet(self._get_table_style())
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.users_table)
        # دعم النقر المزدوج للتعديل
        self.users_table.doubleClicked.connect(self.edit_user)
        layout.addWidget(self.users_table)

    def setup_backup_tab(self):
        """إعداد تاب النسخ الاحتياطي"""
        layout = QVBoxLayout(self.backup_tab)

        # إنشاء نسخة احتياطية
        backup_group = QGroupBox("💾 إنشاء نسخة احتياطية")
        backup_layout = QVBoxLayout()

        backup_desc = QLabel(
            "احفظ نسخة احتياطية كاملة من جميع بياناتك (المشاريع، الفواتير، الحسابات، إلخ)\n"
            "سيتم حفظ البيانات في ملف مضغوط يمكنك تحميله على جهازك."
        )
        backup_desc.setWordWrap(True)
        backup_desc.setStyleSheet("color: #9ca3af; margin-bottom: 10px;")
        backup_layout.addWidget(backup_desc)

        self.create_backup_btn = QPushButton("💾 إنشاء نسخة احتياطية الآن")
        self.create_backup_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.create_backup_btn.clicked.connect(self.create_backup)
        backup_layout.addWidget(self.create_backup_btn)

        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)

        # استرجاع نسخة احتياطية
        restore_group = QGroupBox("📥 استرجاع نسخة احتياطية")
        restore_layout = QVBoxLayout()

        warning_label = QLabel(
            "⚠️ تحذير: استرجاع نسخة احتياطية سيقوم بحذف البيانات الحالية واستبدالها!\n"
            "تأكد من إنشاء نسخة احتياطية للبيانات الحالية أولاً."
        )
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #f59e0b; background-color: #422006; padding: 10px; border-radius: 5px;")
        restore_layout.addWidget(warning_label)

        self.restore_backup_btn = QPushButton("📥 استرجاع نسخة احتياطية")
        self.restore_backup_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.restore_backup_btn.clicked.connect(self.restore_backup)
        restore_layout.addWidget(self.restore_backup_btn)

        restore_group.setLayout(restore_layout)
        layout.addWidget(restore_group)

        # معلومات قاعدة البيانات
        db_group = QGroupBox("📊 معلومات قاعدة البيانات")
        db_layout = QVBoxLayout()

        self.db_stats_label = QLabel("جاري تحميل الإحصائيات...")
        self.db_stats_label.setStyleSheet("color: #d1d5db;")
        db_layout.addWidget(self.db_stats_label)

        self.refresh_stats_btn = QPushButton("🔄 تحديث المعلومات")
        self.refresh_stats_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.refresh_stats_btn.clicked.connect(self.load_db_stats)
        db_layout.addWidget(self.refresh_stats_btn)

        db_group.setLayout(db_layout)
        layout.addWidget(db_group)

        layout.addStretch()
        self.load_db_stats()

    def _get_default_currencies(self):
        """العملات الافتراضية"""
        return [
            {'code': 'EGP', 'name': 'جنيه مصري', 'symbol': 'ج.م', 'rate': 1.0, 'is_base': True, 'active': True},
            {'code': 'USD', 'name': 'دولار أمريكي', 'symbol': 'USD', 'rate': 49.50, 'is_base': False, 'active': True},
            {'code': 'SAR', 'name': 'ريال سعودي', 'symbol': 'ر.س', 'rate': 13.20, 'is_base': False, 'active': True},
            {'code': 'AED', 'name': 'درهم إماراتي', 'symbol': 'د.إ', 'rate': 13.48, 'is_base': False, 'active': True},
        ]

    def _get_input_style(self):
        return """
            QLineEdit, QTextEdit {
                background-color: #001a3a;
                border: 1px solid #003366;
                border-radius: 6px;
                padding: 8px;
                color: #f3f4f6;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 2px solid #3b82f6;
            }
        """

    def _get_table_style(self):
        return TABLE_STYLE_DARK

    def select_logo_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "اختر ملف اللوجو", "", "Image Files (*.png *.jpg *.jpeg)"
        )
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    120, 120, 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.logo_preview.setPixmap(scaled)
                self.logo_preview.setProperty("logo_path", file_path)

    def load_settings_data(self):
        print("INFO: [SettingsTab] جاري تحميل الإعدادات...")
        try:
            # ⚡ معالجة الأحداث لمنع التجميد
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

            settings = self.settings_service.get_settings()
            self.company_name_input.setText(settings.get("company_name", ""))
            self.company_address_input.setText(settings.get("company_address", ""))
            self.company_phone_input.setText(settings.get("company_phone", ""))
            self.company_email_input.setText(settings.get("company_email", ""))
            self.company_website_input.setText(settings.get("company_website", ""))
            self.company_vat_input.setText(settings.get("company_vat", ""))

            logo_path = settings.get("company_logo_path", "")
            if logo_path and os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        120, 120,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.logo_preview.setPixmap(scaled)
                    self.logo_preview.setProperty("logo_path", logo_path)
            else:
                self.logo_preview.setText("📷\nلا يوجد شعار")
        except Exception as e:
            print(f"ERROR: [SettingsTab] فشل تحميل الإعدادات: {e}")

    def save_settings(self):
        print("INFO: [SettingsTab] جاري حفظ الإعدادات...")
        try:
            logo_path = self.logo_preview.property("logo_path") or ""
            new_settings = {
                "company_name": self.company_name_input.text(),
                "company_address": self.company_address_input.text(),
                "company_phone": self.company_phone_input.text(),
                "company_email": self.company_email_input.text(),
                "company_website": self.company_website_input.text(),
                "company_vat": self.company_vat_input.text(),
                "company_logo_path": logo_path,
            }
            self.settings_service.save_settings(new_settings)
            QMessageBox.information(self, "نجاح", "تم حفظ بيانات الشركة بنجاح.")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل حفظ الإعدادات: {e}")

    def load_currencies(self):
        """تحميل العملات من قاعدة البيانات"""
        self.currencies_table.setRowCount(0)

        currencies = []
        if self.repository:
            # جلب العملات من قاعدة البيانات
            currencies = self.repository.get_all_currencies()

            # إذا لم توجد عملات، إنشاء العملات الافتراضية
            if not currencies:
                self.repository.init_default_currencies()
                currencies = self.repository.get_all_currencies()

        # إذا لم يكن هناك repository أو فشل الجلب، استخدم القيم الافتراضية
        if not currencies:
            currencies = self._get_default_currencies()

        for i, curr in enumerate(currencies):
            code = curr.get('code', '')
            name = curr.get('name', '')
            symbol = curr.get('symbol', '')
            rate = curr.get('rate', 1.0)
            is_base = curr.get('is_base', False)
            active = curr.get('active', True)

            self.currencies_table.insertRow(i)
            self.currencies_table.setItem(i, 0, create_centered_item(str(i + 1)))
            self.currencies_table.setItem(i, 1, create_centered_item(code))

            name_display = name
            if is_base:
                name_display += " ⭐"
            self.currencies_table.setItem(i, 2, create_centered_item(name_display))

            self.currencies_table.setItem(i, 3, create_centered_item(symbol))

            rate_display = f"{rate:.2f}"
            if is_base:
                rate_display += " (أساسية)"
            self.currencies_table.setItem(i, 4, create_centered_item(rate_display))

            status = "✅ نشط" if active else "❌ غير نشط"
            self.currencies_table.setItem(i, 5, create_centered_item(status))

    def add_currency(self):
        """إضافة عملة جديدة"""
        dialog = CurrencyEditorDialog(parent=self)
        if dialog.exec():
            result = dialog.get_result()
            if result:
                # حفظ العملة في قاعدة البيانات
                if self.repository:
                    success = self.repository.save_currency(result)
                    if success:
                        self.load_currencies()  # إعادة تحميل الجدول
                        QMessageBox.information(self, "تم", f"تم إضافة العملة {result['name']} بنجاح!")
                    else:
                        QMessageBox.critical(self, "خطأ", "فشل حفظ العملة في قاعدة البيانات")
                else:
                    # إضافة العملة للجدول فقط (بدون حفظ)
                    row = self.currencies_table.rowCount()
                    self.currencies_table.insertRow(row)
                    self.currencies_table.setItem(row, 0, create_centered_item(str(row + 1)))
                    self.currencies_table.setItem(row, 1, create_centered_item(result['code']))
                    self.currencies_table.setItem(row, 2, create_centered_item(result['name']))
                    self.currencies_table.setItem(row, 3, create_centered_item(result['symbol']))
                    self.currencies_table.setItem(row, 4, create_centered_item(f"{result['rate']:.2f}"))
                    status = "✅ نشط" if result['active'] else "❌ غير نشط"
                    self.currencies_table.setItem(row, 5, create_centered_item(status))
                    QMessageBox.information(self, "تم", f"تم إضافة العملة {result['name']} بنجاح!")

    def edit_currency(self):
        """تعديل العملة المحددة (مع إمكانية جلب السعر من الإنترنت)"""
        current_row = self.currencies_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد عملة أولاً")
            return

        # جلب بيانات العملة الحالية
        code = self.currencies_table.item(current_row, 1).text()
        name = self.currencies_table.item(current_row, 2).text()
        symbol = self.currencies_table.item(current_row, 3).text()
        rate_text = self.currencies_table.item(current_row, 4).text()

        # تحويل السعر
        try:
            rate = float(rate_text.replace(" (أساسية)", "").replace(",", ""))
        except (ValueError, AttributeError):
            rate = 1.0

        status_text = self.currencies_table.item(current_row, 5).text()
        active = "نشط" in status_text

        currency_data = {
            'code': code,
            'name': name.replace(" ⭐", ""),
            'symbol': symbol,
            'rate': rate,
            'active': active
        }

        dialog = CurrencyEditorDialog(currency_data=currency_data, parent=self)
        if dialog.exec():
            result = dialog.get_result()
            if result:
                # حفظ التعديلات في قاعدة البيانات
                if self.repository:
                    success = self.repository.save_currency(result)
                    if success:
                        self.load_currencies()  # إعادة تحميل الجدول
                        QMessageBox.information(self, "تم", f"تم تحديث العملة {result['name']} بنجاح!")
                    else:
                        QMessageBox.critical(self, "خطأ", "فشل حفظ التعديلات في قاعدة البيانات")
                else:
                    # تحديث الجدول فقط (بدون حفظ)
                    self.currencies_table.setItem(current_row, 1, create_centered_item(result['code']))

                    name_display = result['name']
                    if result['code'] == "EGP":
                        name_display += " ⭐"
                    self.currencies_table.setItem(current_row, 2, create_centered_item(name_display))

                    self.currencies_table.setItem(current_row, 3, create_centered_item(result['symbol']))

                    rate_display = f"{result['rate']:.2f}"
                    if result['code'] == "EGP":
                        rate_display += " (أساسية)"
                    self.currencies_table.setItem(current_row, 4, create_centered_item(rate_display))

                    status = "✅ نشط" if result['active'] else "❌ غير نشط"
                    self.currencies_table.setItem(current_row, 5, create_centered_item(status))

                    QMessageBox.information(self, "تم", f"تم تحديث العملة {result['name']} بنجاح!")

    def delete_currency(self):
        """حذف العملة المحددة"""
        current_row = self.currencies_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد عملة أولاً")
            return

        code = self.currencies_table.item(current_row, 1).text()

        if code == "EGP":
            QMessageBox.warning(self, "خطأ", "لا يمكن حذف العملة الأساسية (الجنيه المصري)")
            return

        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل أنت متأكد من حذف العملة {code}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # حذف من قاعدة البيانات
            if self.repository:
                success = self.repository.delete_currency(code)
                if success:
                    self.load_currencies()  # إعادة تحميل الجدول
                    QMessageBox.information(self, "تم", "تم حذف العملة بنجاح")
                else:
                    QMessageBox.critical(self, "خطأ", "فشل حذف العملة من قاعدة البيانات")
            else:
                self.currencies_table.removeRow(current_row)
                QMessageBox.information(self, "تم", "تم حذف العملة بنجاح")

    def update_exchange_rates(self):
        """تحديث جميع أسعار الصرف من الإنترنت"""
        if not self.repository:
            QMessageBox.warning(self, "تنبيه", "لا يمكن تحديث الأسعار - قاعدة البيانات غير متصلة")
            return

        reply = QMessageBox.question(
            self, "🌐 تحديث أسعار الصرف",
            "سيتم جلب أسعار الصرف الحالية من الإنترنت.\n\nهل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        # تعطيل الزرار أثناء التحديث
        self.update_rates_btn.setEnabled(False)
        self.update_rates_btn.setText("⏳ جاري التحديث...")

        try:
            # تحديث الأسعار
            result = self.repository.update_all_exchange_rates()

            # إعادة تحميل الجدول
            self.load_currencies()

            # عرض النتيجة
            updated = result.get('updated', 0)
            failed = result.get('failed', 0)
            results = result.get('results', {})

            msg = f"✅ تم تحديث {updated} عملة من الإنترنت\n\n"

            for code, data in results.items():
                if data['success']:
                    msg += f"• {code}: {data['rate']:.4f} ج.م ✓\n"
                else:
                    msg += f"• {code}: فشل التحديث ✗\n"

            if failed > 0:
                msg += f"\n⚠️ فشل تحديث {failed} عملة"

            QMessageBox.information(self, "نتيجة التحديث", msg)

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل تحديث الأسعار:\n{e}")

        finally:
            # إعادة تفعيل الزرار
            self.update_rates_btn.setEnabled(True)
            self.update_rates_btn.setText("🌐 تحديث الأسعار من الإنترنت")

    def create_backup(self):
        """إنشاء نسخة احتياطية كاملة من قاعدة البيانات"""
        if not self.repository:
            QMessageBox.warning(self, "تحذير", "قاعدة البيانات غير متصلة!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "حفظ النسخة الاحتياطية",
            f"skywave_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        if file_path:
            try:
                # جمع كل البيانات من قاعدة البيانات
                backup_data = {
                    "backup_info": {
                        "created_at": datetime.now().isoformat(),
                        "version": "1.0",
                        "app": "SkyWave ERP"
                    },
                    "clients": [],
                    "services": [],
                    "projects": [],
                    "invoices": [],
                    "quotations": [],
                    "expenses": [],
                    "accounts": [],
                    "currencies": [],
                    "journal_entries": [],
                    "payments": [],
                    "settings": {}
                }

                # جلب العملاء
                try:
                    clients = self.repository.get_all_clients()
                    backup_data["clients"] = [self._serialize_object(c) for c in clients]
                except Exception as e:
                    print(f"WARNING: فشل جلب العملاء: {e}")

                # جلب الخدمات
                try:
                    services = self.repository.get_all_services()
                    backup_data["services"] = [self._serialize_object(s) for s in services]
                except Exception as e:
                    print(f"WARNING: فشل جلب الخدمات: {e}")

                # جلب المشاريع
                try:
                    projects = self.repository.get_all_projects()
                    backup_data["projects"] = [self._serialize_object(p) for p in projects]
                except Exception as e:
                    print(f"WARNING: فشل جلب المشاريع: {e}")

                # جلب الفواتير
                try:
                    invoices = self.repository.get_all_invoices()
                    backup_data["invoices"] = [self._serialize_object(i) for i in invoices]
                except Exception as e:
                    print(f"WARNING: فشل جلب الفواتير: {e}")

                # جلب عروض الأسعار
                try:
                    quotations = self.repository.get_all_quotations()
                    backup_data["quotations"] = [self._serialize_object(q) for q in quotations]
                except Exception as e:
                    print(f"WARNING: فشل جلب عروض الأسعار: {e}")

                # جلب المصروفات
                try:
                    expenses = self.repository.get_all_expenses()
                    backup_data["expenses"] = [self._serialize_object(e) for e in expenses]
                except Exception as e:
                    print(f"WARNING: فشل جلب المصروفات: {e}")

                # جلب الحسابات
                try:
                    accounts = self.repository.get_all_accounts()
                    backup_data["accounts"] = [self._serialize_object(a) for a in accounts]
                except Exception as e:
                    print(f"WARNING: فشل جلب الحسابات: {e}")

                # جلب العملات
                try:
                    currencies = self.repository.get_all_currencies()
                    backup_data["currencies"] = currencies if isinstance(currencies, list) else [currencies]
                except Exception as e:
                    print(f"WARNING: فشل جلب العملات: {e}")

                # جلب قيود اليومية
                try:
                    journal_entries = self.repository.get_all_journal_entries()
                    backup_data["journal_entries"] = [self._serialize_object(j) for j in journal_entries]
                except Exception as e:
                    print(f"WARNING: فشل جلب قيود اليومية: {e}")

                # جلب الدفعات
                try:
                    payments = self.repository.get_all_payments()
                    backup_data["payments"] = [self._serialize_object(p) for p in payments]
                except Exception as e:
                    print(f"WARNING: فشل جلب الدفعات: {e}")

                # جلب الإعدادات
                try:
                    backup_data["settings"] = self.settings_service.get_settings()
                except Exception as e:
                    print(f"WARNING: فشل جلب الإعدادات: {e}")

                # حفظ الملف
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)

                # حساب الإحصائيات
                total_records = sum([
                    len(backup_data["clients"]),
                    len(backup_data["services"]),
                    len(backup_data["projects"]),
                    len(backup_data["invoices"]),
                    len(backup_data["quotations"]),
                    len(backup_data["expenses"]),
                    len(backup_data["accounts"]),
                    len(backup_data["currencies"]),
                    len(backup_data["journal_entries"]),
                    len(backup_data["payments"]),
                ])

                QMessageBox.information(
                    self,
                    "✅ نجاح",
                    f"تم إنشاء النسخة الاحتياطية بنجاح!\n\n"
                    f"📁 الملف: {file_path}\n"
                    f"📊 إجمالي السجلات: {total_records}\n\n"
                    f"• العملاء: {len(backup_data['clients'])}\n"
                    f"• الخدمات: {len(backup_data['services'])}\n"
                    f"• المشاريع: {len(backup_data['projects'])}\n"
                    f"• الفواتير: {len(backup_data['invoices'])}\n"
                    f"• المصروفات: {len(backup_data['expenses'])}\n"
                    f"• الحسابات: {len(backup_data['accounts'])}\n"
                    f"• قيود اليومية: {len(backup_data['journal_entries'])}"
                )

            except Exception as e:
                QMessageBox.critical(self, "❌ خطأ", f"فشل إنشاء النسخة الاحتياطية:\n{e}")

    def _serialize_object(self, obj):
        """تحويل كائن إلى قاموس قابل للتسلسل"""
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        elif hasattr(obj, 'dict'):
            return obj.dict()
        elif hasattr(obj, '__dict__'):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        else:
            return obj

    def restore_backup(self):
        """استرجاع نسخة احتياطية"""
        if not self.repository:
            QMessageBox.warning(self, "تحذير", "قاعدة البيانات غير متصلة!")
            return

        reply = QMessageBox.warning(
            self, "⚠️ تأكيد",
            "هل أنت متأكد من استرجاع النسخة الاحتياطية؟\n\n"
            "⚠️ سيتم حذف جميع البيانات الحالية واستبدالها!\n"
            "تأكد من إنشاء نسخة احتياطية للبيانات الحالية أولاً.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "اختر ملف النسخة الاحتياطية", "", "JSON Files (*.json)"
            )
            if file_path:
                try:
                    # قراءة ملف النسخة الاحتياطية
                    with open(file_path, encoding='utf-8') as f:
                        backup_data = json.load(f)

                    # التحقق من صحة الملف
                    if "backup_info" not in backup_data:
                        QMessageBox.critical(self, "خطأ", "ملف النسخة الاحتياطية غير صالح!")
                        return

                    backup_info = backup_data.get("backup_info", {})
                    created_at = backup_info.get("created_at", "غير معروف")

                    # تأكيد نهائي
                    final_confirm = QMessageBox.question(
                        self, "تأكيد نهائي",
                        f"سيتم استرجاع النسخة الاحتياطية:\n\n"
                        f"📅 تاريخ الإنشاء: {created_at}\n"
                        f"📊 العملاء: {len(backup_data.get('clients', []))}\n"
                        f"📊 المشاريع: {len(backup_data.get('projects', []))}\n"
                        f"📊 الفواتير: {len(backup_data.get('invoices', []))}\n\n"
                        f"هل تريد المتابعة؟",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )

                    if final_confirm == QMessageBox.StandardButton.Yes:
                        # استرجاع البيانات من النسخة الاحتياطية
                        # يتطلب دوال إضافية في Repository
                        QMessageBox.information(
                            self,
                            "✅ نجاح",
                            "تم قراءة ملف النسخة الاحتياطية بنجاح.\n\n"
                            "⚠️ ملاحظة: استرجاع البيانات يتطلب إعادة تشغيل التطبيق."
                        )

                except json.JSONDecodeError:
                    QMessageBox.critical(self, "خطأ", "ملف النسخة الاحتياطية تالف أو غير صالح!")
                except Exception as e:
                    QMessageBox.critical(self, "خطأ", f"فشل استرجاع النسخة الاحتياطية:\n{e}")

    def load_db_stats(self):
        """تحميل إحصائيات قاعدة البيانات الحقيقية"""
        try:
            if self.repository:
                # جلب الإحصائيات الحقيقية من قاعدة البيانات
                clients_count = len(self.repository.get_all_clients())
                services_count = len(self.repository.get_all_services())
                invoices_count = len(self.repository.get_all_invoices())
                expenses_count = len(self.repository.get_all_expenses())
                accounts_count = len(self.repository.get_all_accounts())
                currencies_count = len(self.repository.get_all_currencies())
                journal_count = len(self.repository.get_all_journal_entries())

                # محاولة جلب المشاريع وعروض الأسعار
                try:
                    projects_count = len(self.repository.get_all_projects())
                except (AttributeError, TypeError) as e:
                    print(f"WARNING: فشل جلب عدد المشاريع: {e}")
                    projects_count = 0

                try:
                    quotations_count = len(self.repository.get_all_quotations())
                except (AttributeError, TypeError) as e:
                    print(f"WARNING: فشل جلب عدد عروض الأسعار: {e}")
                    quotations_count = 0

                total = (clients_count + services_count + invoices_count +
                        expenses_count + accounts_count + currencies_count +
                        journal_count + projects_count + quotations_count)

                # حالة الاتصال
                connection_status = "✅ متصل" if self.repository.online else "⚠️ غير متصل"

                stats_text = f"""
📊 إحصائيات قاعدة البيانات:

• العملاء: {clients_count} سجل
• الخدمات: {services_count} سجل
• المشاريع: {projects_count} سجل
• الفواتير: {invoices_count} سجل
• عروض الأسعار: {quotations_count} سجل
• المصروفات: {expenses_count} سجل
• الحسابات المحاسبية: {accounts_count} سجل
• العملات: {currencies_count} سجل
• قيود اليومية: {journal_count} سجل

📁 إجمالي السجلات: {total}

🔄 حالة الاتصال بالأونلاين: {connection_status}
                """
            else:
                stats_text = """
📊 إحصائيات قاعدة البيانات:

⚠️ قاعدة البيانات غير متصلة
يرجى التحقق من الاتصال
                """

            self.db_stats_label.setText(stats_text)

        except Exception as e:
            self.db_stats_label.setText(f"❌ خطأ في جلب الإحصائيات: {e}")

    def setup_default_accounts_tab(self):
        """إعداد تاب الحسابات الافتراضية"""
        layout = QVBoxLayout(self.default_accounts_tab)

        # معلومات توضيحية
        info_label = QLabel(
            "🔗 ربط الحسابات الافتراضية للنظام\n\n"
            "حدد الحسابات المحاسبية التي سيستخدمها النظام تلقائياً في العمليات السريعة.\n"
            "يجب أن تكون هذه الحسابات موجودة في دليل الحسابات."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            background-color: #1e3a8a;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """)
        layout.addWidget(info_label)

        # نموذج الحسابات الافتراضية
        form_group = QGroupBox("⚙️ إعدادات الحسابات الافتراضية")
        form_layout = QFormLayout()

        # الخزينة الافتراضية (SmartFilterComboBox مع فلترة)
        self.default_treasury_combo = SmartFilterComboBox()

        # حساب الإيرادات الافتراضي (SmartFilterComboBox مع فلترة)
        self.default_revenue_combo = SmartFilterComboBox()

        # حساب الضرائب الافتراضي (SmartFilterComboBox مع فلترة)
        self.default_tax_combo = SmartFilterComboBox()

        # حساب العملاء الافتراضي (SmartFilterComboBox مع فلترة)
        self.default_client_combo = SmartFilterComboBox()

        form_layout.addRow(QLabel("💰 الخزينة الافتراضية (1111):"), self.default_treasury_combo)
        form_layout.addRow(QLabel("📈 إيرادات الخدمات (4100):"), self.default_revenue_combo)
        form_layout.addRow(QLabel("📊 الضرائب المستحقة (2102):"), self.default_tax_combo)
        form_layout.addRow(QLabel("👥 حساب العملاء (1140):"), self.default_client_combo)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # زر التحديث
        buttons_layout = QHBoxLayout()

        self.refresh_accounts_btn = QPushButton("🔄 تحديث القوائم")
        self.refresh_accounts_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.refresh_accounts_btn.clicked.connect(self.load_default_accounts)

        self.save_default_accounts_btn = QPushButton("💾 حفظ الإعدادات")
        self.save_default_accounts_btn.setStyleSheet("""
            QPushButton {
                background-color: #0A6CF1;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0A6CF1;
            }
        """)
        self.save_default_accounts_btn.clicked.connect(self.save_default_accounts)

        buttons_layout.addWidget(self.refresh_accounts_btn)
        buttons_layout.addWidget(self.save_default_accounts_btn)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        layout.addStretch()

        # تحميل الحسابات
        self.load_default_accounts()

    def load_default_accounts(self):
        """تحميل الحسابات من قاعدة البيانات وملء القوائم المنسدلة"""
        if not self.repository:
            QMessageBox.warning(self, "تحذير", "قاعدة البيانات غير متصلة")
            return

        try:
            all_accounts = self.repository.get_all_accounts()

            # فلترة الحسابات حسب النوع
            cash_accounts = [acc for acc in all_accounts if acc.code and acc.code.startswith('11') and not getattr(acc, 'is_group', False)]
            revenue_accounts = [acc for acc in all_accounts if acc.code and acc.code.startswith('4') and not getattr(acc, 'is_group', False)]
            tax_accounts = [acc for acc in all_accounts if acc.code and acc.code.startswith('21') and not getattr(acc, 'is_group', False)]
            client_accounts = [acc for acc in all_accounts if acc.code and acc.code.startswith('114')]

            # ملء القوائم المنسدلة
            self._populate_account_combo(self.default_treasury_combo, cash_accounts, '1111')
            self._populate_account_combo(self.default_revenue_combo, revenue_accounts, '4100')
            self._populate_account_combo(self.default_tax_combo, tax_accounts, '2102')
            self._populate_account_combo(self.default_client_combo, client_accounts, '1140')

            # تحميل القيم المحفوظة
            settings = self.settings_service.get_settings()
            self._select_account_by_code(self.default_treasury_combo, settings.get('default_treasury_account', '1111'))
            self._select_account_by_code(self.default_revenue_combo, settings.get('default_revenue_account', '4100'))
            self._select_account_by_code(self.default_tax_combo, settings.get('default_tax_account', '2102'))
            self._select_account_by_code(self.default_client_combo, settings.get('default_client_account', '1140'))

        except Exception as e:
            print(f"ERROR: فشل تحميل الحسابات الافتراضية: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل تحميل الحسابات: {e}")

    def _populate_account_combo(self, combo, accounts: list, default_code: str | None = None):
        """ملء ComboBox بالحسابات"""
        combo.clear()
        combo.addItem("-- اختر حساباً --", userData=None)

        for acc in accounts:
            display_text = f"{acc.name} ({acc.code})"
            combo.addItem(display_text, userData=acc.code)

            # تحديد الحساب الافتراضي
            if default_code and acc.code == default_code:
                combo.setCurrentIndex(combo.count() - 1)

    def _select_account_by_code(self, combo: QComboBox, code: str):
        """تحديد حساب في ComboBox بناءً على الكود"""
        for i in range(combo.count()):
            if combo.itemData(i) == code:
                combo.setCurrentIndex(i)
                break

    def save_default_accounts(self):
        """حفظ إعدادات الحسابات الافتراضية"""
        try:
            # جمع الحسابات المحددة فقط (بدون إلزام تحديد الكل)
            all_accounts = {
                'default_treasury_account': self.default_treasury_combo.currentData(),
                'default_revenue_account': self.default_revenue_combo.currentData(),
                'default_tax_account': self.default_tax_combo.currentData(),
                'default_client_account': self.default_client_combo.currentData(),
            }

            # حفظ الحسابات المحددة فقط (السماح بحفظ حساب واحد أو أكثر)
            default_accounts = {k: v for k, v in all_accounts.items() if v is not None}

            # التحقق من أن هناك حساب واحد على الأقل محدد
            if not default_accounts:
                QMessageBox.warning(
                    self,
                    "تحذير",
                    "يرجى تحديد حساب واحد على الأقل قبل الحفظ"
                )
                return

            # حفظ الإعدادات
            current_settings = self.settings_service.get_settings()
            current_settings.update(all_accounts)  # حفظ الكل (بما فيها None للحسابات غير المحددة)
            self.settings_service.save_settings(current_settings)

            # عرض رسالة نجاح مع عدد الحسابات المحفوظة
            saved_count = len(default_accounts)
            QMessageBox.information(
                self,
                "نجاح",
                f"✅ تم حفظ {saved_count} حساب/حسابات افتراضية بنجاح"
            )

        except Exception as e:
            print(f"ERROR: فشل حفظ الحسابات الافتراضية: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")

    def load_users(self):
        """تحميل المستخدمين من قاعدة البيانات"""
        print("=" * 50)
        print("INFO: [SettingsTab] ========== جاري تحميل المستخدمين ==========")
        print(f"INFO: [SettingsTab] repository موجود: {self.repository is not None}")
        self.users_table.setRowCount(0)

        if not self.repository:
            print("WARNING: [SettingsTab] لا يوجد repository!")
            return

        try:
            # جلب المستخدمين من قاعدة البيانات
            print("INFO: [SettingsTab] جاري استدعاء get_all_users...")
            users = self.repository.get_all_users()
            print(f"INFO: [SettingsTab] ✅ تم جلب {len(users)} مستخدم")

            for i, user in enumerate(users):
                self.users_table.insertRow(i)

                # العمود 0: الرقم التسلسلي
                self.users_table.setItem(i, 0, create_centered_item(str(i + 1)))

                # العمود 1: اسم المستخدم (نخزن الـ ID هنا)
                username_item = create_centered_item(user.username)
                # CRITICAL: تخزين الـ ID الحقيقي
                user_id = user.id if user.id else (user.mongo_id if hasattr(user, 'mongo_id') else None)
                username_item.setData(Qt.ItemDataRole.UserRole, user_id)
                self.users_table.setItem(i, 1, username_item)

                # العمود 2: الاسم الكامل
                self.users_table.setItem(i, 2, create_centered_item(user.full_name or ""))

                # العمود 3: البريد الإلكتروني
                self.users_table.setItem(i, 3, create_centered_item(user.email or ""))

                # العمود 4: الدور
                # التعامل مع الدور سواء كان enum أو string
                if hasattr(user.role, 'value'):
                    role_value = user.role.value
                else:
                    role_value = str(user.role)
                role_display_map = {
                    'admin': '🔑 مدير النظام',
                    'accountant': '📊 محاسب',
                    'sales': '💼 مندوب مبيعات'
                }
                role_display = role_display_map.get(role_value.lower(), role_value)
                self.users_table.setItem(i, 4, create_centered_item(role_display))
                print(f"INFO: [SettingsTab] تم إضافة مستخدم: {user.username} - {role_display}")

                # العمود 5: الحالة
                status = "✅ نشط" if user.is_active else "❌ غير نشط"
                self.users_table.setItem(i, 5, create_centered_item(status))

                # العمود 6: تاريخ الإنشاء
                created_date = user.created_at[:10] if user.created_at else ""
                self.users_table.setItem(i, 6, create_centered_item(created_date))

            # تحديث الجدول
            self.users_table.viewport().update()
            print(f"INFO: [SettingsTab] ✅ تم تحميل {self.users_table.rowCount()} صف في الجدول")
            print("=" * 50)

        except Exception as e:
            print(f"ERROR: فشل تحميل المستخدمين: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "خطأ", f"فشل تحميل المستخدمين: {e}")

    def add_user(self):
        """إضافة مستخدم جديد"""
        # التحقق من الصلاحية
        from core.auth_models import AuthService, PermissionManager
        if self.current_user and not PermissionManager.has_feature(self.current_user, 'user_management'):
            QMessageBox.warning(self, "تنبيه", "ليس لديك صلاحية إضافة مستخدمين.")
            return

        from ui.user_editor_dialog import UserEditorDialog

        # إنشاء خدمة المصادقة
        auth_service = AuthService(self.repository)

        dialog = UserEditorDialog(auth_service, parent=self)
        if dialog.exec():
            self.load_users()
            QMessageBox.information(self, "تم", "تم إضافة المستخدم بنجاح.")

    def edit_user(self):
        """تعديل مستخدم"""
        # التحقق من الصلاحية
        from core.auth_models import AuthService, PermissionManager
        if self.current_user and not PermissionManager.has_feature(self.current_user, 'user_management'):
            QMessageBox.warning(self, "تنبيه", "ليس لديك صلاحية تعديل المستخدمين.")
            return

        current_row = self.users_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مستخدم أولاً.")
            return

        # الحصول على اسم المستخدم من العمود 1
        username_item = self.users_table.item(current_row, 1)
        if not username_item:
            QMessageBox.warning(self, "خطأ", "لم يتم العثور على بيانات المستخدم.")
            return

        username = username_item.text()
        print(f"INFO: [SettingsTab] جاري تعديل المستخدم: {username}")

        from ui.user_editor_dialog import UserEditorDialog

        # إنشاء خدمة المصادقة
        auth_service = AuthService(self.repository)

        # جلب بيانات المستخدم الحديثة من قاعدة البيانات
        user = auth_service.repo.get_user_by_username(username)
        if not user:
            QMessageBox.warning(self, "خطأ", f"لم يتم العثور على المستخدم: {username}")
            return

        print(f"INFO: [SettingsTab] تم جلب بيانات المستخدم: {user.username}, {user.full_name}, {user.email}")

        # فتح نافذة التعديل مع بيانات المستخدم
        dialog = UserEditorDialog(auth_service, user_to_edit=user, parent=self)
        if dialog.exec():
            self.load_users()  # إعادة تحميل الجدول بعد التعديل

    def edit_user_permissions(self):
        """تحرير صلاحيات المستخدم"""
        # التحقق من الصلاحية
        from core.auth_models import AuthService, PermissionManager
        if self.current_user and not PermissionManager.has_feature(self.current_user, 'user_management'):
            QMessageBox.warning(self, "تنبيه", "ليس لديك صلاحية تحرير صلاحيات المستخدمين.")
            return

        current_row = self.users_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مستخدم أولاً.")
            return

        # الحصول على اسم المستخدم من العمود 1
        username_item = self.users_table.item(current_row, 1)
        if not username_item:
            QMessageBox.warning(self, "خطأ", "لم يتم العثور على بيانات المستخدم.")
            return

        username = username_item.text()
        print(f"INFO: [SettingsTab] جاري تحرير صلاحيات المستخدم: {username}")

        auth_service = AuthService(self.repository)

        # جلب بيانات المستخدم الحديثة من قاعدة البيانات
        user = auth_service.repo.get_user_by_username(username)
        if not user:
            QMessageBox.warning(self, "خطأ", f"لم يتم العثور على المستخدم: {username}")
            return

        print(f"INFO: [SettingsTab] تم جلب بيانات المستخدم للصلاحيات: {user.username}")

        # فتح نافذة تحرير الصلاحيات
        from ui.user_permissions_dialog import UserPermissionsDialog
        dialog = UserPermissionsDialog(user, self.repository, self)
        if dialog.exec():
            self.load_users()  # إعادة تحميل الجدول
            QMessageBox.information(self, "تم", "تم تحديث صلاحيات المستخدم بنجاح.")

    def delete_user(self):
        """حذف مستخدم"""
        # التحقق من الصلاحية
        from core.auth_models import AuthService, PermissionManager
        if self.current_user and not PermissionManager.has_feature(self.current_user, 'user_management'):
            QMessageBox.warning(self, "تنبيه", "ليس لديك صلاحية حذف المستخدمين.")
            return

        current_row = self.users_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مستخدم أولاً.")
            return

        # الحصول على اسم المستخدم من العمود 1
        username_item = self.users_table.item(current_row, 1)
        if not username_item:
            QMessageBox.warning(self, "خطأ", "لم يتم العثور على بيانات المستخدم.")
            return

        username = username_item.text()

        # منع حذف المستخدم reda123
        if username == "reda123":
            QMessageBox.warning(self, "تحذير", "لا يمكن حذف مستخدم المدير الرئيسي.")
            return

        # منع حذف المستخدم الحالي
        if self.current_user and username == self.current_user.username:
            QMessageBox.warning(self, "تحذير", "لا يمكنك حذف حسابك الخاص.")
            return

        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل أنت متأكد من تعطيل المستخدم '{username}'؟\n(سيتم تعطيل الحساب وليس حذفه نهائياً)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # تعطيل المستخدم باستخدام username مباشرة
                print(f"INFO: [SettingsTab] جاري تعطيل المستخدم: {username}")
                success = self.repository.update_user_by_username(username, {"is_active": False})

                if success:
                    self.load_users()
                    QMessageBox.information(self, "تم", "تم تعطيل المستخدم بنجاح.")
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في تعطيل المستخدم.")

            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل في تعطيل المستخدم: {str(e)}")

    def activate_user(self):
        """تفعيل مستخدم معطل"""
        # التحقق من الصلاحية
        from core.auth_models import AuthService, PermissionManager
        if self.current_user and not PermissionManager.has_feature(self.current_user, 'user_management'):
            QMessageBox.warning(self, "تنبيه", "ليس لديك صلاحية تفعيل المستخدمين.")
            return

        current_row = self.users_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد مستخدم أولاً.")
            return

        # الحصول على اسم المستخدم من العمود 1
        username_item = self.users_table.item(current_row, 1)
        if not username_item:
            QMessageBox.warning(self, "خطأ", "لم يتم العثور على بيانات المستخدم.")
            return

        username = username_item.text()

        # التحقق من أن المستخدم معطل
        status_item = self.users_table.item(current_row, 5)
        if status_item and "نشط" in status_item.text() and "غير" not in status_item.text():
            QMessageBox.information(self, "تنبيه", "هذا المستخدم نشط بالفعل.")
            return

        reply = QMessageBox.question(
            self, "تأكيد التفعيل",
            f"هل تريد تفعيل المستخدم '{username}'؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # تفعيل المستخدم باستخدام username مباشرة
                print(f"INFO: [SettingsTab] جاري تفعيل المستخدم: {username}")
                success = self.repository.update_user_by_username(username, {"is_active": True})

                if success:
                    self.load_users()
                    QMessageBox.information(self, "تم", "تم تفعيل المستخدم بنجاح.")
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في تفعيل المستخدم.")

            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل في تفعيل المستخدم: {str(e)}")

    def setup_update_tab(self):
        """إعداد تاب التحديثات"""
        layout = QVBoxLayout(self.update_tab)

        # معلومات الإصدار الحالي
        from version import APP_NAME, CURRENT_VERSION

        version_group = QGroupBox("📱 معلومات الإصدار")
        version_layout = QVBoxLayout()

        app_name_label = QLabel(f"<h2>{APP_NAME}</h2>")
        app_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_name_label.setStyleSheet("color: #4a90e2; font-weight: bold;")
        version_layout.addWidget(app_name_label)

        current_version_label = QLabel(f"الإصدار الحالي: {CURRENT_VERSION}")
        current_version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        current_version_label.setStyleSheet("font-size: 16px; color: #0A6CF1; padding: 10px;")
        version_layout.addWidget(current_version_label)

        version_group.setLayout(version_layout)
        layout.addWidget(version_group)

        # معلومات التحديث
        update_info_group = QGroupBox("ℹ️ معلومات التحديث")
        update_info_layout = QVBoxLayout()

        self.update_status_label = QLabel("اضغط على 'التحقق من التحديثات' للبحث عن إصدارات جديدة")
        self.update_status_label.setWordWrap(True)
        self.update_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_status_label.setStyleSheet("""
            background-color: #1e3a8a;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """)
        update_info_layout.addWidget(self.update_status_label)

        update_info_group.setLayout(update_info_layout)
        layout.addWidget(update_info_group)

        # شريط التقدم (مخفي في البداية)
        self.update_progress_bar = QProgressBar()
        self.update_progress_bar.setVisible(False)
        self.update_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3b82f6;
                border-radius: 8px;
                text-align: center;
                background-color: #001a3a;
                color: white;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #0A6CF1;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.update_progress_bar)

        # أزرار التحكم
        buttons_layout = QHBoxLayout()

        self.check_update_btn = QPushButton("🔍 التحقق من التحديثات")
        self.check_update_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.check_update_btn.clicked.connect(self.check_for_updates)

        self.download_update_btn = QPushButton("⬇️ تنزيل التحديث")
        self.download_update_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.download_update_btn.setVisible(False)
        self.download_update_btn.clicked.connect(self.download_update)

        self.install_update_btn = QPushButton("🚀 تثبيت التحديث")
        self.install_update_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.install_update_btn.setVisible(False)
        self.install_update_btn.clicked.connect(self.install_update)

        buttons_layout.addWidget(self.check_update_btn)
        buttons_layout.addWidget(self.download_update_btn)
        buttons_layout.addWidget(self.install_update_btn)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # ملاحظات التحديث
        notes_group = QGroupBox("📝 ملاحظات مهمة")
        notes_layout = QVBoxLayout()

        notes_text = QLabel(
            "• سيتم تحديث البرنامج في نفس المكان الحالي\n"
            "• لن تفقد أي بيانات أثناء التحديث\n"
            "• سيتم إغلاق البرنامج تلقائياً وإعادة تشغيله بعد التحديث\n"
            "• تأكد من حفظ جميع أعمالك قبل التحديث"
        )
        notes_text.setWordWrap(True)
        notes_text.setStyleSheet("color: #9ca3af; padding: 10px;")
        notes_layout.addWidget(notes_text)

        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        layout.addStretch()

        # تهيئة متغيرات التحديث
        self.update_download_url = None
        self.update_version = None
        self.update_service = None

    def check_for_updates(self):
        """التحقق من وجود تحديثات جديدة"""
        from services.update_service import UpdateService
        from version import CURRENT_VERSION, UPDATE_CHECK_URL

        # تعطيل الزرار أثناء الفحص
        self.check_update_btn.setEnabled(False)
        self.check_update_btn.setText("⏳ جاري التحقق...")
        self.update_status_label.setText("🔍 جاري البحث عن تحديثات جديدة...")
        self.update_status_label.setStyleSheet("""
            background-color: #f59e0b;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """)

        # إنشاء خدمة التحديث
        self.update_service = UpdateService(CURRENT_VERSION, UPDATE_CHECK_URL)

        # إنشاء Thread للتحقق
        self.update_checker = self.update_service.check_for_updates()

        # ربط الإشارات
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.no_update.connect(self.on_no_update)
        self.update_checker.error_occurred.connect(self.on_update_error)

        # بدء الفحص
        self.update_checker.start()

    def on_update_available(self, version, url):
        """عند توفر تحديث جديد"""
        self.update_version = version
        self.update_download_url = url

        self.update_status_label.setText(
            f"🎉 يتوفر إصدار جديد!\n\n"
            f"الإصدار الجديد: {version}\n"
            f"اضغط على 'تنزيل التحديث' للبدء"
        )
        self.update_status_label.setStyleSheet("""
            background-color: #0A6CF1;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """)

        # إظهار زرار التنزيل
        self.download_update_btn.setVisible(True)

        # إعادة تفعيل زرار الفحص
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText("🔍 التحقق من التحديثات")

    def on_no_update(self):
        """عند عدم توفر تحديثات"""
        from version import CURRENT_VERSION

        self.update_status_label.setText(
            f"✅ أنت تستخدم أحدث إصدار!\n\n"
            f"الإصدار الحالي: {CURRENT_VERSION}"
        )
        self.update_status_label.setStyleSheet("""
            background-color: #0A6CF1;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """)

        # إعادة تفعيل زرار الفحص
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText("🔍 التحقق من التحديثات")

    def on_update_error(self, error_message):
        """عند حدوث خطأ في الفحص - عرض تحذير بسيط بدلاً من رسالة خطأ"""
        # Handle 404 and connection errors gracefully
        if "404" in error_message or "فشل الاتصال" in error_message:
            self.update_status_label.setText(
                "⚠️ لا توجد تحديثات متاحة حالياً\n\n"
                "سيتم التحقق مرة أخرى لاحقاً"
            )
            self.update_status_label.setStyleSheet("""
                background-color: #f59e0b;
                color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """)
        else:
            # For other errors, show the original error message
            self.update_status_label.setText(
                f"❌ حدث خطأ أثناء التحقق من التحديثات:\n\n{error_message}"
            )
            self.update_status_label.setStyleSheet("""
                background-color: #ef4444;
                color: white;
                padding: 15px;
                border-radius: 8px;
                font-size: 13px;
            """)

        # إعادة تفعيل زرار الفحص
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText("🔍 التحقق من التحديثات")

        # Don't show popup for 404 errors - just the subtle warning above
        if not ("404" in error_message or "فشل الاتصال" in error_message):
            QMessageBox.warning(self, "خطأ", f"فشل التحقق من التحديثات:\n{error_message}")

    def download_update(self):
        """تنزيل التحديث"""
        if not self.update_download_url:
            QMessageBox.warning(self, "خطأ", "لا يوجد رابط تحديث متاح")
            return

        # تأكيد التنزيل
        reply = QMessageBox.question(
            self, "تأكيد التنزيل",
            f"سيتم تنزيل الإصدار {self.update_version}\n\nهل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        # تعطيل الأزرار
        self.download_update_btn.setEnabled(False)
        self.check_update_btn.setEnabled(False)

        # إظهار شريط التقدم
        self.update_progress_bar.setVisible(True)
        self.update_progress_bar.setValue(0)

        self.update_status_label.setText("⬇️ جاري تنزيل التحديث...")
        self.update_status_label.setStyleSheet("""
            background-color: #3b82f6;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """)

        # إنشاء Thread للتنزيل
        self.update_downloader = self.update_service.download_update(self.update_download_url)

        # ربط الإشارات
        self.update_downloader.progress_updated.connect(self.on_download_progress)
        self.update_downloader.download_completed.connect(self.on_download_completed)
        self.update_downloader.error_occurred.connect(self.on_download_error)

        # بدء التنزيل
        self.update_downloader.start()

    def on_download_progress(self, progress):
        """تحديث شريط التقدم"""
        self.update_progress_bar.setValue(progress)

    def on_download_completed(self, file_path):
        """عند اكتمال التنزيل"""
        self.update_progress_bar.setValue(100)

        self.update_status_label.setText(
            "✅ تم تنزيل التحديث بنجاح!\n\n"
            "اضغط على 'تثبيت التحديث' لإكمال العملية"
        )
        self.update_status_label.setStyleSheet("""
            background-color: #0A6CF1;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """)

        # إخفاء زرار التنزيل وإظهار زرار التثبيت
        self.download_update_btn.setVisible(False)
        self.install_update_btn.setVisible(True)

        # إعادة تفعيل زرار الفحص
        self.check_update_btn.setEnabled(True)

    def on_download_error(self, error_message):
        """عند حدوث خطأ في التنزيل"""
        self.update_progress_bar.setVisible(False)

        self.update_status_label.setText(
            f"❌ فشل تنزيل التحديث:\n\n{error_message}"
        )
        self.update_status_label.setStyleSheet("""
            background-color: #ef4444;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """)

        # إعادة تفعيل الأزرار
        self.download_update_btn.setEnabled(True)
        self.check_update_btn.setEnabled(True)

        # إذا كان الخطأ بسبب الصلاحيات، اعرض خيار فتح صفحة التنزيل
        if "Permission denied" in error_message or "الصلاحيات" in error_message:
            reply = QMessageBox.question(
                self, "خطأ في الصلاحيات",
                "فشل تنزيل التحديث بسبب مشكلة في الصلاحيات.\n\n"
                "هل تريد فتح صفحة التنزيل في المتصفح لتنزيل التحديث يدوياً؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                import webbrowser
                webbrowser.open(self.update_download_url)
        else:
            QMessageBox.critical(self, "خطأ", f"فشل تنزيل التحديث:\n{error_message}")

    def install_update(self):
        """تثبيت التحديث"""
        reply = QMessageBox.warning(
            self, "⚠️ تأكيد التثبيت",
            "سيتم إغلاق البرنامج الآن لتثبيت التحديث.\n"
            "سيتم إعادة تشغيل البرنامج تلقائياً بعد التحديث.\n\n"
            "تأكد من حفظ جميع أعمالك!\n\n"
            "هل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            # تطبيق التحديث
            success = self.update_service.apply_update(
                self.update_service.temp_update_path
            )

            if success:
                # إغلاق البرنامج
                import sys
                sys.exit(0)
            else:
                QMessageBox.critical(
                    self, "خطأ",
                    "فشل تشغيل المحدث.\n"
                    "تأكد من وجود ملف updater.exe أو updater.py في مجلد البرنامج."
                )

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل تثبيت التحديث:\n{e}")
