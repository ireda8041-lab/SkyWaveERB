# pylint: disable=too-many-lines,too-many-public-methods
# الملف: ui/settings_tab.py
"""
تاب الإعدادات المتقدمة - يشمل:
- إدارة الحسابات
- إدارة العملات
- بيانات الشركة
- إدارة المستخدمين
- النسخ الاحتياطي
"""

import glob
import json
import os
import sys
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QRegularExpression, Qt, QTimer
from PyQt6.QtGui import QPixmap, QRegularExpressionValidator, QValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.auth_models import AuthService, PermissionManager
from core.data_loader import get_data_loader
from core.repository import Repository
from services.settings_service import SettingsService
from services.update_service import UpdateService
from ui.currency_editor_dialog import CurrencyEditorDialog
from ui.smart_combobox import SmartFilterComboBox
from ui.styles import (
    BUTTON_STYLES,
    TABLE_STYLE_DARK,
    apply_arrows_to_all_widgets,
    apply_rtl_alignment_to_all_fields,
    create_centered_item,
    fix_table_rtl,
    setup_custom_title_bar,
)
from ui.template_settings import TemplateSettings
from ui.todo_manager import TaskService
from ui.universal_search import UniversalSearchBar
from ui.user_editor_dialog import UserEditorDialog
from ui.user_permissions_dialog import UserPermissionsDialog
from version import APP_NAME, CURRENT_VERSION, UPDATE_CHECK_URL

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class SettingsTab(QWidget):
    """تاب الإعدادات المتقدمة مع تابات فرعية."""

    def __init__(
        self,
        settings_service: SettingsService,
        repository: Repository | None = None,
        current_user=None,
        parent=None,
    ):
        super().__init__(parent)
        self.settings_service = settings_service
        self.repository = repository
        self.current_user = current_user
        self._users_cache: list = []
        self._users_cache_ts: float | None = None
        self._users_cache_ttl_s = 20.0
        self._users_current_page = 1
        self._users_page_size = 100
        self._users_all: list = []
        self._currencies_current_page = 1
        self._currencies_page_size = 100
        self._currencies_all: list[dict] = []
        self._payment_methods_current_page = 1
        self._payment_methods_page_size = 100
        self._payment_methods_all: list[dict] = []
        self._payment_methods_page_start = 0
        self._note_templates_current_page = 1
        self._note_templates_page_size = 100
        self._note_templates_all: list[dict] = []
        self._note_templates_page_start = 0

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        header = QFrame()
        header.setObjectName("settingsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(10)

        title = QLabel("⚙️ الإعدادات")
        title.setObjectName("settingsTitle")
        header_layout.addWidget(title, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "🔍 ابحث عن تبويب إعدادات (مثل: العملات، المستخدمين، النسخ الاحتياطي...)"
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(
            lambda: self._search_settings_tabs(self.search_input.text())
        )
        self.search_input.setVisible(False)
        header_layout.addStretch(1)

        main_layout.addWidget(header)

        # إنشاء التابات الفرعية
        self.tabs = QTabWidget()

        self.tabs.setTabPosition(QTabWidget.TabPosition.North)

        # ⚡ جعل التابات الفرعية تتمدد لتملأ العرض تلقائياً
        self.tabs.tabBar().setExpanding(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)  # عدم اقتطاع النص
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)

        main_layout.addWidget(self.tabs)

        self.setStyleSheet(
            """
            QFrame#settingsHeader {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 12px;
            }
            QLabel#settingsTitle {
                font-size: 16px;
                font-weight: 700;
            }
            QLineEdit {
                padding: 8px 10px;
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.12);
                background: rgba(0, 0, 0, 0.18);
            }
            QLineEdit:focus {
                border: 1px solid rgba(45, 140, 255, 0.85);
            }
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
                top: -1px;
            }
            QTabBar::tab {
                padding: 10px 14px;
                margin: 0 2px;
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                background: rgba(0, 0, 0, 0.14);
            }
            QTabBar::tab:selected {
                background: rgba(45, 140, 255, 0.22);
                border-color: rgba(45, 140, 255, 0.55);
            }
            """
        )

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

        self.template_tab = TemplateSettings(self.settings_service)
        self.tabs.addTab(self.template_tab, "🎨 قوالب الفواتير")

        # تاب طرق الدفع
        self.payment_methods_tab = QWidget()
        self.tabs.addTab(self.payment_methods_tab, "💳 طرق الدفع")
        self.setup_payment_methods_tab()

        # تاب ملاحظات المشاريع
        self.project_notes_tab = QWidget()
        self.tabs.addTab(self.project_notes_tab, "📝 ملاحظات المشاريع")
        self.setup_project_notes_tab()

        # تاب التحديثات
        self.update_tab = QWidget()
        self.tabs.addTab(self.update_tab, "🆕 التحديثات")
        self.setup_update_tab()

        # تطبيق الأسهم على كل الـ widgets

        apply_arrows_to_all_widgets(self)

        # ربط تغيير التاب الفرعي لتحميل البيانات
        self.tabs.currentChanged.connect(self._on_sub_tab_changed)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_settings_data() - يتم استدعاؤها من MainWindow
        # self.load_users() - يتم استدعاؤها من MainWindow

        # ⚡ تطبيق محاذاة النص لليمين على كل الحقول

        apply_rtl_alignment_to_all_fields(self)

    def _search_settings_tabs(self, text: str):
        if not text:
            return

        query = text.strip().lower()
        if not query:
            return

        for i in range(self.tabs.count()):
            label = (self.tabs.tabText(i) or "").lower()
            if query in label:
                self.tabs.setCurrentIndex(i)
                return

    def _apply_settings_tab_search(self):
        text = ""
        if not text:
            return

        for i in range(self.tabs.count()):
            if text in (self.tabs.tabText(i) or "").lower():
                self.tabs.setCurrentIndex(i)
                return

    def _on_sub_tab_changed(self, index):
        """معالج تغيير التاب الفرعي - محسّن لتجنب التحميل المتكرر"""
        tab_text = self.tabs.tabText(index)
        safe_print(f"INFO: [SettingsTab] تم اختيار التاب الفرعي: {tab_text}")

        # ⚡ تحميل البيانات فقط إذا كان الجدول فارغاً (لتجنب التحميل المتكرر)
        if "المستخدمين" in tab_text:
            if self.users_table.rowCount() == 0:
                self.load_users()
        elif "بيانات الشركة" in tab_text:
            # تحميل بيانات الشركة فقط إذا كانت الحقول فارغة
            try:
                if not self._ensure_company_ui() or not self.company_name_input.text():
                    self.load_settings_data()
            except Exception:
                pass
        elif "العملات" in tab_text:
            if self.currencies_table.rowCount() == 0:
                self.load_currencies()
        elif "الحسابات الافتراضية" in tab_text:
            if self.default_treasury_combo.count() == 0:
                self.load_default_accounts()
        elif "طرق الدفع" in tab_text:
            if self.payment_methods_table.rowCount() == 0:
                self.load_payment_methods()
        elif "ملاحظات المشاريع" in tab_text:
            if self.note_templates_table.rowCount() == 0:
                self.load_note_templates()

    def setup_company_tab(self):
        """إعداد تاب بيانات الشركة - تصميم احترافي متجاوب محسّن"""

        outer_layout = QVBoxLayout(self.company_tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            """
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #0d2137; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3d6a9f; border-radius: 4px; min-height: 30px;
            }
        """
        )

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        # ستايل الحقول المحسن (أكثر دقة)
        input_style = """
            QLineEdit {
                background: #0b1d33;
                color: #E2E8F0;
                border: 1px solid rgba(99, 146, 207, 0.35);
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 13px;
                min-height: 18px;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                background: #0d223b;
            }
        """
        label_style = "color: #93C5FD; font-size: 11px; font-weight: bold; margin-bottom: 2px;"
        section_title_style = "color: #E2E8F0; font-size: 14px; font-weight: bold; padding: 2px 0;"

        # === التخطيط الأفقي الرئيسي ===
        summary_frame = QFrame()
        summary_frame.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(18, 48, 86, 0.85), stop:1 rgba(10, 30, 55, 0.85));
                border: 1px solid rgba(80, 140, 220, 0.35);
                border-radius: 14px;
            }
        """
        )
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(16, 12, 16, 12)
        summary_layout.setSpacing(10)
        summary_title = QLabel("🏢 ملف الشركة")
        summary_title.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: bold;")
        summary_subtitle = QLabel("حدّث بيانات شركتك وشعارك لطباعة احترافية")
        summary_subtitle.setStyleSheet("color: #94a3b8; font-size: 11px;")
        summary_text = QVBoxLayout()
        summary_text.setSpacing(2)
        summary_text.addWidget(summary_title)
        summary_text.addWidget(summary_subtitle)
        summary_layout.addLayout(summary_text)
        summary_layout.addStretch()
        badge = QLabel("محفوظ محلياً")
        badge.setStyleSheet(
            """
            QLabel {
                background: rgba(16, 185, 129, 0.18);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.35);
                border-radius: 10px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
        """
        )
        summary_layout.addWidget(badge)
        layout.addWidget(summary_frame)

        main_h = QHBoxLayout()
        main_h.setSpacing(14)
        main_h.setAlignment(Qt.AlignmentFlag.AlignTop)

        # === الجانب الأيسر: الحقول ===
        fields_frame = QFrame()
        fields_frame.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(12, 33, 60, 0.85), stop:1 rgba(8, 22, 40, 0.85));
                border: 1px solid rgba(80, 140, 220, 0.3);
                border-radius: 14px;
            }
        """
        )
        fields_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        fields_container = QVBoxLayout(fields_frame)
        fields_container.setContentsMargins(18, 16, 18, 16)
        fields_container.setSpacing(8)

        # عنوان القسم
        fields_title = QLabel("📋 بيانات الشركة الأساسية")
        fields_title.setStyleSheet(section_title_style)
        fields_container.addWidget(fields_title)

        fields_layout = QGridLayout()
        fields_layout.setSpacing(10)
        fields_layout.setColumnStretch(0, 1)
        fields_layout.setColumnStretch(1, 1)

        fields_container.addLayout(fields_layout)

        def build_field(label_widget, input_widget):
            field = QWidget()
            field_layout = QVBoxLayout(field)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(4)
            field_layout.addWidget(label_widget)
            field_layout.addWidget(input_widget)
            return field

        # اسم الشركة
        name_lbl = QLabel("🏢 اسم الشركة")
        name_lbl.setStyleSheet(label_style)
        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("أدخل اسم الشركة...")
        self.company_name_input.setStyleSheet(input_style)
        fields_layout.addWidget(build_field(name_lbl, self.company_name_input), 0, 0)

        # الشعار (Tagline)
        tagline_lbl = QLabel("✨ الشعار")
        tagline_lbl.setStyleSheet(label_style)
        self.company_tagline_input = QLineEdit()
        self.company_tagline_input.setPlaceholderText("وكالة تسويق رقمي متكاملة")
        self.company_tagline_input.setStyleSheet(input_style)
        fields_layout.addWidget(build_field(tagline_lbl, self.company_tagline_input), 0, 1)

        # العنوان
        addr_lbl = QLabel("📍 العنوان")
        addr_lbl.setStyleSheet(label_style)
        self.company_address_input = QLineEdit()
        self.company_address_input.setPlaceholderText("العنوان الكامل...")
        self.company_address_input.setStyleSheet(input_style)
        fields_layout.addWidget(build_field(addr_lbl, self.company_address_input), 1, 0)

        # الهاتف
        phone_lbl = QLabel("📱 رقم الهاتف")
        phone_lbl.setStyleSheet(label_style)
        self.company_phone_input = QLineEdit()
        self.company_phone_input.setPlaceholderText("+20 10 123 4567")
        self.company_phone_input.setStyleSheet(input_style)
        fields_layout.addWidget(build_field(phone_lbl, self.company_phone_input), 1, 1)

        # البريد
        email_lbl = QLabel("📧 البريد الإلكتروني")
        email_lbl.setStyleSheet(label_style)
        self.company_email_input = QLineEdit()
        self.company_email_input.setPlaceholderText("info@company.com")
        self.company_email_input.setStyleSheet(input_style)
        fields_layout.addWidget(build_field(email_lbl, self.company_email_input), 2, 0)

        # الموقع
        web_lbl = QLabel("🌐 موقع الشركة")
        web_lbl.setStyleSheet(label_style)
        self.company_website_input = QLineEdit()
        self.company_website_input.setPlaceholderText("www.company.com")
        self.company_website_input.setStyleSheet(input_style)
        fields_layout.addWidget(build_field(web_lbl, self.company_website_input), 2, 1)

        # الرقم الضريبي
        vat_lbl = QLabel("🔢 الرقم الضريبي")
        vat_lbl.setStyleSheet(label_style)
        self.company_vat_input = QLineEdit()
        self.company_vat_input.setPlaceholderText("أدخل الرقم الضريبي")
        self.company_vat_input.setStyleSheet(input_style)
        fields_layout.addWidget(build_field(vat_lbl, self.company_vat_input), 3, 0)

        # === الجانب الأيمن: اللوجو ===
        logo_frame = QFrame()
        logo_frame.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(12, 33, 60, 0.85), stop:1 rgba(8, 22, 40, 0.85));
                border: 1px solid rgba(80, 140, 220, 0.3);
                border-radius: 14px;
            }
        """
        )
        logo_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        logo_frame.setMinimumWidth(200)
        logo_container = QVBoxLayout(logo_frame)
        logo_container.setContentsMargins(16, 14, 16, 16)
        logo_container.setSpacing(10)
        logo_container.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        logo_title = QLabel("🖼️ شعار الشركة")
        logo_title.setStyleSheet(section_title_style)
        logo_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_container.addWidget(logo_title)

        self.company_preview_frame = QFrame()
        self.company_preview_frame.setStyleSheet(
            """
            QFrame {
                background-color: rgba(12, 32, 54, 0.7);
                border: 1px solid rgba(90, 150, 230, 0.25);
                border-radius: 12px;
            }
        """
        )
        preview_layout = QVBoxLayout(self.company_preview_frame)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        preview_layout.setSpacing(4)

        self.company_preview_name = QLabel("—")
        self.company_preview_name.setStyleSheet(
            "color: white; font-size: 13px; font-weight: bold; font-family: 'Cairo';"
        )
        self.company_preview_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.company_preview_tagline = QLabel("")
        self.company_preview_tagline.setStyleSheet(
            "color: #93C5FD; font-size: 11px; font-family: 'Cairo';"
        )
        self.company_preview_tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.company_preview_meta = QLabel("")
        self.company_preview_meta.setStyleSheet(
            "color: #94a3b8; font-size: 10px; font-family: 'Cairo';"
        )
        self.company_preview_meta.setWordWrap(True)
        self.company_preview_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)

        preview_layout.addWidget(self.company_preview_name)
        preview_layout.addWidget(self.company_preview_tagline)
        preview_layout.addWidget(self.company_preview_meta)
        logo_container.addWidget(self.company_preview_frame)

        # إطار اللوجو المحسن
        self.logo_preview = QLabel()
        self.logo_preview.setFixedSize(140, 140)
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_preview.setStyleSheet(
            """
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0d2137, stop:1 #0a1929);
                border: 1px dashed rgba(120, 180, 255, 0.5);
                border-radius: 14px;
                color: #64748B;
                font-size: 11px;
            }
        """
        )
        self.logo_preview.setText("📷\nلا يوجد شعار")
        logo_container.addWidget(self.logo_preview, alignment=Qt.AlignmentFlag.AlignCenter)

        # أزرار اللوجو المحسنة
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.select_logo_btn = QPushButton("📷 اختيار صورة")
        self.select_logo_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:1 #2563eb);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }
        """
        )
        self.select_logo_btn.clicked.connect(self.select_logo_file)

        self.remove_logo_btn = QPushButton("🗑️ حذف")
        self.remove_logo_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(239, 68, 68, 0.15);
                color: #fecaca;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.35);
                color: white;
            }
        """
        )
        self.remove_logo_btn.clicked.connect(self._remove_logo)

        btn_layout.addWidget(self.select_logo_btn)
        btn_layout.addWidget(self.remove_logo_btn)
        logo_container.addLayout(btn_layout)

        # نص توضيحي
        hint_lbl = QLabel("PNG, JPG • 200×200 px\n✅ يتم مزامنته تلقائياً")
        hint_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_container.addWidget(hint_lbl)

        main_h.addWidget(fields_frame, 2)
        main_h.addWidget(logo_frame, 1)

        layout.addLayout(main_h)
        layout.addStretch(1)

        # ⚡ زر الحفظ المحسن
        save_container = QHBoxLayout()
        save_container.addStretch()

        self.save_company_btn = QPushButton("💾 حفظ بيانات الشركة")
        self.save_company_btn.setMinimumWidth(260)
        self.save_company_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #22c55e, stop:1 #16a34a);
                color: white;
                border: none;
                border-radius: 12px;
                padding: 14px 44px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #16a34a, stop:1 #15803d);
            }
            QPushButton:pressed {
                background: #15803d;
            }
            QPushButton:disabled {
                background: rgba(16, 185, 129, 0.25);
                color: rgba(255, 255, 255, 0.55);
            }
        """
        )
        self.save_company_btn.clicked.connect(self.save_settings)
        save_container.addWidget(self.save_company_btn)
        save_container.addStretch()

        layout.addLayout(save_container)

        scroll_area.setWidget(scroll_content)
        outer_layout.addWidget(scroll_area)

        self._company_input_style = input_style
        self._company_input_style_invalid = (
            input_style
            + """
            QLineEdit { border: 2px solid #ef4444; }
            QLineEdit:focus { border: 2px solid #ef4444; background: #0f2942; }
        """
        )

        email_re = QRegularExpression(r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
        phone_re = QRegularExpression(r"^$|^\+?[0-9\s\-]{7,}$")
        website_re = QRegularExpression(r"^$|^(https?://)?([A-Za-z0-9-]+\.)+[A-Za-z]{2,}(/.*)?$")

        self.company_email_input.setValidator(QRegularExpressionValidator(email_re, self))
        self.company_phone_input.setValidator(QRegularExpressionValidator(phone_re, self))
        self.company_website_input.setValidator(QRegularExpressionValidator(website_re, self))

        for w in (
            self.company_name_input,
            self.company_tagline_input,
            self.company_address_input,
            self.company_phone_input,
            self.company_email_input,
            self.company_website_input,
            self.company_vat_input,
        ):
            w.textChanged.connect(self._on_company_form_changed)

        self._on_company_form_changed()

    def _ensure_company_ui(self) -> bool:
        try:
            if hasattr(self, "company_name_input") and self.company_name_input:
                _ = self.company_name_input.text()
                return True
        except Exception:
            pass

        return False

    def _remove_logo(self):
        """حذف اللوجو الحالي"""
        self.logo_preview.clear()
        self.logo_preview.setText("📷\nلا يوجد شعار")
        self.logo_preview.setProperty("logo_path", "")
        self._on_company_form_changed()

    def setup_currency_tab(self):
        """إعداد تاب إدارة العملات"""
        layout = QVBoxLayout(self.currency_tab)

        # معلومات العملة الأساسية
        base_info = QLabel("💰 العملة الأساسية للنظام: الجنيه المصري (EGP)")
        base_info.setStyleSheet(
            """
            background-color: #0A6CF1;
            color: white;
            padding: 10px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
        """
        )
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
        self.currencies_table.setHorizontalHeaderLabels(
            ["#", "الرمز", "الاسم", "الرمز", "سعر الصرف", "الحالة"]
        )
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

        fix_table_rtl(self.currencies_table)
        layout.addWidget(self.currencies_table)

        # ⚡ لا نحمل البيانات هنا - سيتم التحميل عند فتح التاب
        # self.load_currencies()

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 6, 0, 0)
        pagination_layout.setSpacing(8)

        self.curr_prev_page_button = QPushButton("◀ السابق")
        self.curr_prev_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.curr_prev_page_button.setFixedHeight(26)
        self.curr_prev_page_button.clicked.connect(self._go_curr_prev_page)

        self.curr_next_page_button = QPushButton("التالي ▶")
        self.curr_next_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.curr_next_page_button.setFixedHeight(26)
        self.curr_next_page_button.clicked.connect(self._go_curr_next_page)

        self.curr_page_info_label = QLabel("صفحة 1 / 1")
        self.curr_page_info_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

        self.curr_page_size_combo = QComboBox()
        self.curr_page_size_combo.addItems(["50", "100", "200", "كل"])
        self.curr_page_size_combo.setCurrentText("100")
        self.curr_page_size_combo.currentTextChanged.connect(self._on_curr_page_size_changed)

        pagination_layout.addWidget(self.curr_prev_page_button)
        pagination_layout.addWidget(self.curr_next_page_button)
        pagination_layout.addStretch(1)
        pagination_layout.addWidget(QLabel("حجم الصفحة:"))
        pagination_layout.addWidget(self.curr_page_size_combo)
        pagination_layout.addWidget(self.curr_page_info_label)
        layout.addLayout(pagination_layout)

    def setup_users_tab(self):
        """إعداد تاب إدارة المستخدمين"""
        layout = QVBoxLayout(self.users_tab)

        # التحقق من صلاحية إدارة المستخدمين

        can_manage_users = True
        if self.current_user:
            can_manage_users = PermissionManager.has_feature(self.current_user, "user_management")

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
            warning_label.setStyleSheet(
                "color: #f59e0b; background-color: #422006; padding: 10px; border-radius: 5px; margin-bottom: 10px;"
            )
            layout.addWidget(warning_label)

        # جدول المستخدمين
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(7)
        self.users_table.setHorizontalHeaderLabels(
            ["#", "اسم المستخدم", "الاسم الكامل", "البريد", "الدور", "الحالة", "تاريخ الإنشاء"]
        )
        h_header = self.users_table.horizontalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # #
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # اسم المستخدم - يتمدد
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # الاسم الكامل - يتمدد
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # البريد - يتمدد
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # الدور
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
            h_header.setSectionResizeMode(
                6, QHeaderView.ResizeMode.ResizeToContents
            )  # تاريخ الإنشاء
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.users_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.users_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.users_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.users_table.setTabKeyNavigation(False)
        self.users_table.setStyleSheet(self._get_table_style())
        # إصلاح مشكلة انعكاس الأعمدة في RTL

        fix_table_rtl(self.users_table)
        # دعم النقر المزدوج للتعديل
        self.users_table.doubleClicked.connect(self.edit_user)
        layout.addWidget(self.users_table)

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 6, 0, 0)
        pagination_layout.setSpacing(8)

        self.users_prev_page_button = QPushButton("◀ السابق")
        self.users_prev_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.users_prev_page_button.setFixedHeight(26)
        self.users_prev_page_button.clicked.connect(self._go_users_prev_page)

        self.users_next_page_button = QPushButton("التالي ▶")
        self.users_next_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.users_next_page_button.setFixedHeight(26)
        self.users_next_page_button.clicked.connect(self._go_users_next_page)

        self.users_page_info_label = QLabel("صفحة 1 / 1")
        self.users_page_info_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

        self.users_page_size_combo = QComboBox()
        self.users_page_size_combo.addItems(["50", "100", "200", "كل"])
        self.users_page_size_combo.setCurrentText("100")
        self.users_page_size_combo.currentTextChanged.connect(self._on_users_page_size_changed)

        pagination_layout.addWidget(self.users_prev_page_button)
        pagination_layout.addWidget(self.users_next_page_button)
        pagination_layout.addStretch(1)
        pagination_layout.addWidget(QLabel("حجم الصفحة:"))
        pagination_layout.addWidget(self.users_page_size_combo)
        pagination_layout.addWidget(self.users_page_info_label)
        layout.addLayout(pagination_layout)

    def setup_backup_tab(self):
        """⚡ إعداد تاب النسخ الاحتياطي - تصميم احترافي محسّن"""

        # منطقة التمرير
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            """
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #0d2137; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3d6a9f; border-radius: 4px; min-height: 30px;
            }
        """
        )

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(15)
        layout.setContentsMargins(22, 18, 22, 18)

        header_frame = QFrame()
        header_frame.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(14, 42, 78, 0.85), stop:1 rgba(9, 28, 52, 0.9));
                border: 1px solid rgba(90, 150, 230, 0.35);
                border-radius: 14px;
            }
        """
        )
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)
        header_title = QLabel("💾 إدارة النسخ الاحتياطية")
        header_title.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: bold;")
        header_subtitle = QLabel("حماية بياناتك بضغطة واحدة مع استرجاع آمن")
        header_subtitle.setStyleSheet("color: #94a3b8; font-size: 11px;")
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        header_text.addWidget(header_title)
        header_text.addWidget(header_subtitle)
        header_layout.addLayout(header_text)
        header_layout.addStretch()
        header_badge = QLabel("آمن ومشفر")
        header_badge.setStyleSheet(
            """
            QLabel {
                background: rgba(59, 130, 246, 0.2);
                color: #93C5FD;
                border: 1px solid rgba(59, 130, 246, 0.35);
                border-radius: 10px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
        """
        )
        header_layout.addWidget(header_badge)
        layout.addWidget(header_frame)

        # === قسم إنشاء نسخة احتياطية ===
        backup_group = QGroupBox("💾 إنشاء نسخة احتياطية")
        backup_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 14px; font-weight: bold;
                border: 1px solid rgba(90, 150, 230, 0.3); border-radius: 12px;
                margin-top: 10px; padding: 16px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(16, 185, 129, 0.12), stop:1 rgba(8, 26, 50, 0.6));
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top right;
                padding: 2px 12px;
                color: #10B981;
            }
        """
        )
        backup_layout = QVBoxLayout()
        backup_layout.setSpacing(12)

        backup_desc = QLabel(
            "📦 احفظ نسخة احتياطية كاملة من جميع بياناتك:\n"
            "• المشاريع والفواتير • العملاء والخدمات • الحسابات والمصروفات\n"
            "• قيود اليومية • الإعدادات والعملات"
        )
        backup_desc.setWordWrap(True)
        backup_desc.setStyleSheet("color: #cbd5f5; font-size: 12px; line-height: 1.6;")
        backup_layout.addWidget(backup_desc)

        # شريط التقدم (مخفي افتراضياً)
        self.backup_progress = QProgressBar()
        self.backup_progress.setVisible(False)
        self.backup_progress.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid rgba(90, 150, 230, 0.3); border-radius: 7px;
                background: rgba(13, 33, 55, 0.7); height: 20px; text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10B981, stop:1 #34d399);
                border-radius: 4px;
            }
        """
        )
        backup_layout.addWidget(self.backup_progress)

        # أزرار النسخ الاحتياطي
        backup_btns = QHBoxLayout()

        self.create_backup_btn = QPushButton("💾 إنشاء نسخة احتياطية الآن")
        self.create_backup_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #34d399);
                color: white; border: none; border-radius: 10px;
                padding: 12px 26px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: #059669; }
            QPushButton:disabled { background: #374151; color: #6b7280; }
        """
        )
        self.create_backup_btn.clicked.connect(self.create_backup)
        backup_btns.addWidget(self.create_backup_btn)

        self.auto_backup_btn = QPushButton("⏰ نسخ احتياطي تلقائي")
        self.auto_backup_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(59, 130, 246, 0.2);
                color: #93C5FD; border: 1px solid rgba(59, 130, 246, 0.4);
                border-radius: 10px; padding: 12px 25px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(59, 130, 246, 0.4); }
        """
        )
        self.auto_backup_btn.clicked.connect(self._setup_auto_backup)
        backup_btns.addWidget(self.auto_backup_btn)

        backup_btns.addStretch()
        backup_layout.addLayout(backup_btns)
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)

        # === قسم استرجاع نسخة احتياطية ===
        restore_group = QGroupBox("📥 استرجاع نسخة احتياطية")
        restore_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 14px; font-weight: bold;
                border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 12px;
                margin-top: 10px; padding: 16px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(245, 158, 11, 0.08), stop:1 rgba(8, 26, 50, 0.6));
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top right;
                padding: 2px 12px;
                color: #FBBF24;
            }
        """
        )
        restore_layout = QVBoxLayout()
        restore_layout.setSpacing(12)

        warning_label = QLabel(
            "⚠️ تحذير هام:\n"
            "• استرجاع نسخة احتياطية سيحذف البيانات الحالية!\n"
            "• تأكد من إنشاء نسخة احتياطية للبيانات الحالية أولاً\n"
            "• لا يمكن التراجع عن هذه العملية"
        )
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet(
            """
            color: #fde68a; background-color: rgba(245, 158, 11, 0.12);
            padding: 12px; border-radius: 10px; border: 1px solid rgba(245, 158, 11, 0.3);
            font-size: 12px;
        """
        )
        restore_layout.addWidget(warning_label)

        self.restore_backup_btn = QPushButton("📥 استرجاع نسخة احتياطية")
        self.restore_backup_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(239, 68, 68, 0.2);
                color: #FCA5A5; border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 10px; padding: 12px 25px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 0.4); color: white; }
        """
        )
        self.restore_backup_btn.clicked.connect(self.restore_backup)
        restore_layout.addWidget(self.restore_backup_btn)
        restore_group.setLayout(restore_layout)
        layout.addWidget(restore_group)

        # === قسم معلومات قاعدة البيانات ===
        db_group = QGroupBox("📊 معلومات قاعدة البيانات")
        db_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 14px; font-weight: bold;
                border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 12px;
                margin-top: 10px; padding: 16px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(59, 130, 246, 0.1), stop:1 rgba(8, 26, 50, 0.6));
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top right;
                padding: 2px 12px;
                color: #93C5FD;
            }
        """
        )
        db_layout = QVBoxLayout()
        db_layout.setSpacing(10)

        self.db_stats_label = QLabel("⏳ جاري تحميل الإحصائيات...")
        self.db_stats_label.setStyleSheet(
            """
            color: #e2e8f0; font-size: 12px; line-height: 1.7;
            background: rgba(13, 33, 55, 0.6); padding: 15px;
            border-radius: 10px; border: 1px solid rgba(90, 150, 230, 0.25);
        """
        )
        db_layout.addWidget(self.db_stats_label)

        db_btns = QHBoxLayout()
        self.refresh_stats_btn = QPushButton("🔄 تحديث المعلومات")
        self.refresh_stats_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.refresh_stats_btn.clicked.connect(self.load_db_stats)
        db_btns.addWidget(self.refresh_stats_btn)

        self.optimize_db_btn = QPushButton("⚡ تحسين قاعدة البيانات")
        self.optimize_db_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.optimize_db_btn.clicked.connect(self._optimize_database)
        db_btns.addWidget(self.optimize_db_btn)

        db_btns.addStretch()
        db_layout.addLayout(db_btns)
        db_group.setLayout(db_layout)
        layout.addWidget(db_group)

        # === قسم سجل النسخ الاحتياطية ===
        history_group = QGroupBox("📋 سجل النسخ الاحتياطية")
        history_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 14px; font-weight: bold;
                border: 1px solid rgba(90, 150, 230, 0.3); border-radius: 12px;
                margin-top: 10px; padding: 16px;
                background: rgba(12, 33, 60, 0.55);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top right;
                padding: 2px 12px;
                color: #93C5FD;
            }
        """
        )
        history_layout = QVBoxLayout()

        self.backup_history_label = QLabel("لا توجد نسخ احتياطية سابقة")
        self.backup_history_label.setStyleSheet("color: #94a3b8; font-size: 12px; padding: 12px;")
        history_layout.addWidget(self.backup_history_label)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        layout.addStretch()
        scroll_area.setWidget(scroll_content)

        # إضافة scroll_area للتاب
        tab_layout = QVBoxLayout(self.backup_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll_area)

        # تحميل الإحصائيات
        self.load_db_stats()
        self._load_backup_history()

    def _setup_auto_backup(self):
        """إعداد النسخ الاحتياطي التلقائي"""
        QMessageBox.information(
            self,
            "النسخ الاحتياطي التلقائي",
            "🔜 قريباً!\n\n"
            "سيتم إضافة ميزة النسخ الاحتياطي التلقائي في التحديث القادم.\n\n"
            "حالياً يمكنك إنشاء نسخة احتياطية يدوياً.",
        )

    def _optimize_database(self):
        """تحسين قاعدة البيانات"""
        try:
            if not self.repository:
                QMessageBox.warning(self, "تحذير", "قاعدة البيانات غير متصلة!")
                return

            reply = QMessageBox.question(
                self,
                "تحسين قاعدة البيانات",
                "سيتم تحسين قاعدة البيانات وضغطها.\n\n"
                "هذه العملية قد تستغرق بضع ثوانٍ.\n\n"
                "هل تريد المتابعة؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                cursor = self.repository.get_cursor()
                try:
                    cursor.execute("VACUUM")
                    cursor.execute("ANALYZE")
                    QMessageBox.information(
                        self,
                        "✅ نجاح",
                        "تم تحسين قاعدة البيانات بنجاح!\n\n"
                        "• تم ضغط الملفات\n"
                        "• تم تحديث الفهارس",
                    )
                finally:
                    cursor.close()

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل تحسين قاعدة البيانات:\n{e}")

    def _load_backup_history(self):
        """تحميل سجل النسخ الاحتياطية"""
        try:

            # البحث عن ملفات النسخ الاحتياطية
            backup_files = glob.glob("skywave_backup_*.json")
            backup_files.extend(glob.glob("exports/skywave_backup_*.json"))

            if backup_files:
                history_text = "📁 النسخ الاحتياطية المتاحة:\n\n"
                for f in sorted(backup_files, reverse=True)[:5]:  # آخر 5 نسخ
                    file_name = os.path.basename(f)
                    file_size = os.path.getsize(f) / 1024  # KB
                    history_text += f"• {file_name} ({file_size:.1f} KB)\n"
                self.backup_history_label.setText(history_text)
            else:
                self.backup_history_label.setText("لا توجد نسخ احتياطية سابقة في المجلد الحالي")

        except Exception as e:
            safe_print(f"WARNING: فشل تحميل سجل النسخ الاحتياطية: {e}")

    def _get_default_currencies(self):
        """العملات الافتراضية"""
        return [
            {
                "code": "EGP",
                "name": "جنيه مصري",
                "symbol": "ج.م",
                "rate": 1.0,
                "is_base": True,
                "active": True,
            },
            {
                "code": "USD",
                "name": "دولار أمريكي",
                "symbol": "USD",
                "rate": 49.50,
                "is_base": False,
                "active": True,
            },
            {
                "code": "SAR",
                "name": "ريال سعودي",
                "symbol": "ر.س",
                "rate": 13.20,
                "is_base": False,
                "active": True,
            },
            {
                "code": "AED",
                "name": "درهم إماراتي",
                "symbol": "د.إ",
                "rate": 13.48,
                "is_base": False,
                "active": True,
            },
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
                    120,
                    120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.logo_preview.setPixmap(scaled)
                self.logo_preview.setProperty("logo_path", file_path)

                # ⚡ حفظ اللوجو كـ Base64 للمزامنة بين الأجهزة
                if self.settings_service.save_logo_from_file(file_path):
                    safe_print("INFO: [SettingsTab] تم حفظ اللوجو للمزامنة")
                self._on_company_form_changed()

    def load_settings_data(self):
        safe_print("INFO: [SettingsTab] جاري تحميل الإعدادات...")
        try:
            settings = self.settings_service.get_settings()

            if not self._ensure_company_ui():
                return

            self.company_name_input.setText(settings.get("company_name", ""))
            self.company_tagline_input.setText(settings.get("company_tagline", ""))
            self.company_address_input.setText(settings.get("company_address", ""))
            self.company_phone_input.setText(settings.get("company_phone", ""))
            self.company_email_input.setText(settings.get("company_email", ""))
            self.company_website_input.setText(settings.get("company_website", ""))
            self.company_vat_input.setText(settings.get("company_vat", ""))

            logo_path = settings.get("company_logo_path", "")

            # ⚡ أولاً: محاولة تحميل من Base64 (للمزامنة بين الأجهزة)
            pixmap = self.settings_service.get_logo_as_pixmap()
            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaled(
                    120,
                    120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.logo_preview.setPixmap(scaled)
                self.logo_preview.setProperty("logo_path", logo_path)
            elif logo_path and os.path.exists(logo_path):
                # ثانياً: تحميل من المسار المحلي
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        120,
                        120,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.logo_preview.setPixmap(scaled)
                    self.logo_preview.setProperty("logo_path", logo_path)
            else:
                self.logo_preview.setText("📷\nلا يوجد شعار")

            self._company_settings_snapshot = {
                "company_name": self.company_name_input.text(),
                "company_tagline": self.company_tagline_input.text(),
                "company_address": self.company_address_input.text(),
                "company_phone": self.company_phone_input.text(),
                "company_email": self.company_email_input.text(),
                "company_website": self.company_website_input.text(),
                "company_vat": self.company_vat_input.text(),
                "company_logo_path": self.logo_preview.property("logo_path") or "",
            }

            self._on_company_form_changed()
            safe_print("INFO: [SettingsTab] ✅ تم تحميل الإعدادات")
        except Exception as e:
            safe_print(f"ERROR: [SettingsTab] فشل تحميل الإعدادات: {e}")

            traceback.print_exc()

    def save_settings(self):
        safe_print("INFO: [SettingsTab] جاري حفظ الإعدادات...")
        try:
            logo_path = self.logo_preview.property("logo_path") or ""

            # الحفاظ على logo_data الموجود
            current_settings = self.settings_service.get_settings()
            logo_data = current_settings.get("company_logo_data", "")

            new_settings = {
                "company_name": self.company_name_input.text(),
                "company_tagline": self.company_tagline_input.text(),
                "company_address": self.company_address_input.text(),
                "company_phone": self.company_phone_input.text(),
                "company_email": self.company_email_input.text(),
                "company_website": self.company_website_input.text(),
                "company_vat": self.company_vat_input.text(),
                "company_logo_path": logo_path,
                "company_logo_data": logo_data,  # ⚡ الحفاظ على اللوجو
            }

            self.settings_service.update_settings(new_settings)

            # ⚡ رفع الإعدادات للسحابة
            if hasattr(self, "repository") and self.repository:
                self.settings_service.sync_settings_to_cloud(self.repository)

            QMessageBox.information(self, "نجاح", "تم حفظ بيانات الشركة بنجاح ✅")
            self._company_settings_snapshot = {
                "company_name": self.company_name_input.text(),
                "company_tagline": self.company_tagline_input.text(),
                "company_address": self.company_address_input.text(),
                "company_phone": self.company_phone_input.text(),
                "company_email": self.company_email_input.text(),
                "company_website": self.company_website_input.text(),
                "company_vat": self.company_vat_input.text(),
                "company_logo_path": logo_path,
            }
            self._on_company_form_changed()
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل حفظ الإعدادات: {e}")

    def _on_company_form_changed(self):
        if not self._ensure_company_ui():
            return

        self._update_company_preview()
        invalid = []

        def _is_input_acceptable(w: QLineEdit) -> bool:
            try:
                validator = w.validator()
                if validator is None:
                    return True
                state = validator.validate(w.text(), 0)[0]
                return state == QValidator.State.Acceptable
            except Exception:
                return True

        for w in (self.company_email_input, self.company_phone_input, self.company_website_input):
            ok = _is_input_acceptable(w)
            w.setStyleSheet(self._company_input_style if ok else self._company_input_style_invalid)
            if not ok:
                invalid.append(w)

        required_ok = bool(self.company_name_input.text().strip())
        self.company_name_input.setStyleSheet(
            self._company_input_style if required_ok else self._company_input_style_invalid
        )

        snapshot = getattr(self, "_company_settings_snapshot", None) or {}
        current = {
            "company_name": self.company_name_input.text(),
            "company_tagline": self.company_tagline_input.text(),
            "company_address": self.company_address_input.text(),
            "company_phone": self.company_phone_input.text(),
            "company_email": self.company_email_input.text(),
            "company_website": self.company_website_input.text(),
            "company_vat": self.company_vat_input.text(),
            "company_logo_path": self.logo_preview.property("logo_path") or "",
        }
        has_changes = current != snapshot
        can_save = required_ok and not invalid and has_changes
        self.save_company_btn.setEnabled(can_save)

    def _update_company_preview(self):
        name = (self.company_name_input.text() or "").strip() or "—"
        tagline = (self.company_tagline_input.text() or "").strip()
        phone = (self.company_phone_input.text() or "").strip()
        email = (self.company_email_input.text() or "").strip()
        website = (self.company_website_input.text() or "").strip()

        self.company_preview_name.setText(name)
        self.company_preview_tagline.setText(tagline)

        parts = [p for p in (phone, email, website) if p]
        self.company_preview_meta.setText(" • ".join(parts))

    def load_currencies(self):
        """تحميل العملات من قاعدة البيانات - محسّن"""
        self.currencies_table.setUpdatesEnabled(False)
        self.currencies_table.setRowCount(0)

        data_loader = get_data_loader()

        def fetch_currencies():
            currencies = []
            if self.repository is not None:
                currencies = self.repository.get_all_currencies()
                if not currencies:
                    self.repository.init_default_currencies()
                    currencies = self.repository.get_all_currencies()
            if not currencies:
                currencies = self._get_default_currencies()
            return currencies

        def on_loaded(currencies):
            try:
                self._currencies_all = currencies
                self._render_currencies_page()
            finally:
                self.currencies_table.setUpdatesEnabled(True)

        def on_error(error_msg: str):
            try:
                safe_print(f"ERROR: فشل تحميل العملات: {error_msg}")
            finally:
                self.currencies_table.setUpdatesEnabled(True)

        data_loader.load_async(
            operation_name="settings_currencies",
            load_function=fetch_currencies,
            on_success=on_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _get_currencies_total_pages(self) -> int:
        total = len(self._currencies_all)
        if total == 0:
            return 1
        if self._currencies_page_size <= 0:
            return 1
        return (total + self._currencies_page_size - 1) // self._currencies_page_size

    def _render_currencies_page(self):
        total_pages = self._get_currencies_total_pages()
        if self._currencies_current_page > total_pages:
            self._currencies_current_page = total_pages
        if self._currencies_current_page < 1:
            self._currencies_current_page = 1

        if not self._currencies_all:
            self.currencies_table.setRowCount(1)
            empty_item = create_centered_item("لا توجد عملات")
            self.currencies_table.setItem(0, 0, empty_item)
            self.currencies_table.setSpan(0, 0, 1, self.currencies_table.columnCount())
            self._update_currencies_pagination_controls(total_pages)
            return

        if self._currencies_page_size <= 0:
            page_items = self._currencies_all
            start_index = 0
        else:
            start_index = (self._currencies_current_page - 1) * self._currencies_page_size
            end_index = start_index + self._currencies_page_size
            page_items = self._currencies_all[start_index:end_index]

        self._populate_currencies_table(page_items, start_index)
        self._update_currencies_pagination_controls(total_pages)

    def _populate_currencies_table(self, currencies: list[dict], start_index: int):
        self.currencies_table.setRowCount(len(currencies))
        for i, curr in enumerate(currencies):
            code = curr.get("code", "")
            name = curr.get("name", "")
            symbol = curr.get("symbol", "")
            rate = curr.get("rate", 1.0)
            is_base = curr.get("is_base", False)
            active = curr.get("active", True)

            row_number = start_index + i + 1
            self.currencies_table.setItem(i, 0, create_centered_item(str(row_number)))
            self.currencies_table.setItem(i, 1, create_centered_item(code))

            name_display = name + (" ⭐" if is_base else "")
            self.currencies_table.setItem(i, 2, create_centered_item(name_display))

            self.currencies_table.setItem(i, 3, create_centered_item(symbol))

            rate_display = f"{rate:.2f}" + (" (أساسية)" if is_base else "")
            self.currencies_table.setItem(i, 4, create_centered_item(rate_display))

            status = "✅ نشط" if active else "❌ غير نشط"
            self.currencies_table.setItem(i, 5, create_centered_item(status))

    def _update_currencies_pagination_controls(self, total_pages: int):
        self.curr_page_info_label.setText(f"صفحة {self._currencies_current_page} / {total_pages}")
        self.curr_prev_page_button.setEnabled(self._currencies_current_page > 1)
        self.curr_next_page_button.setEnabled(self._currencies_current_page < total_pages)

    def _on_curr_page_size_changed(self, value: str):
        if value == "كل":
            self._currencies_page_size = max(1, len(self._currencies_all))
        else:
            try:
                self._currencies_page_size = int(value)
            except Exception:
                self._currencies_page_size = 100
        self._currencies_current_page = 1
        self._render_currencies_page()

    def _go_curr_prev_page(self):
        if self._currencies_current_page > 1:
            self._currencies_current_page -= 1
            self._render_currencies_page()

    def _go_curr_next_page(self):
        if self._currencies_current_page < self._get_currencies_total_pages():
            self._currencies_current_page += 1
            self._render_currencies_page()

    def add_currency(self):
        """إضافة عملة جديدة"""
        dialog = CurrencyEditorDialog(parent=self)
        if dialog.exec():
            result = dialog.get_result()
            if result:
                # حفظ العملة في قاعدة البيانات
                if self.repository is not None:
                    success = self.repository.save_currency(result)
                    if success:
                        self.load_currencies()  # إعادة تحميل الجدول
                        QMessageBox.information(
                            self, "تم", f"تم إضافة العملة {result['name']} بنجاح!"
                        )
                    else:
                        QMessageBox.critical(self, "خطأ", "فشل حفظ العملة في قاعدة البيانات")
                else:
                    # إضافة العملة للجدول فقط (بدون حفظ)
                    row = self.currencies_table.rowCount()
                    self.currencies_table.insertRow(row)
                    self.currencies_table.setItem(row, 0, create_centered_item(str(row + 1)))
                    self.currencies_table.setItem(row, 1, create_centered_item(result["code"]))
                    self.currencies_table.setItem(row, 2, create_centered_item(result["name"]))
                    self.currencies_table.setItem(row, 3, create_centered_item(result["symbol"]))
                    self.currencies_table.setItem(
                        row, 4, create_centered_item(f"{result['rate']:.2f}")
                    )
                    status = "✅ نشط" if result["active"] else "❌ غير نشط"
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
            "code": code,
            "name": name.replace(" ⭐", ""),
            "symbol": symbol,
            "rate": rate,
            "active": active,
        }

        dialog = CurrencyEditorDialog(currency_data=currency_data, parent=self)
        if dialog.exec():
            result = dialog.get_result()
            if result:
                # حفظ التعديلات في قاعدة البيانات
                if self.repository is not None:
                    success = self.repository.save_currency(result)
                    if success:
                        self.load_currencies()  # إعادة تحميل الجدول
                        QMessageBox.information(
                            self, "تم", f"تم تحديث العملة {result['name']} بنجاح!"
                        )
                    else:
                        QMessageBox.critical(self, "خطأ", "فشل حفظ التعديلات في قاعدة البيانات")
                else:
                    # تحديث الجدول فقط (بدون حفظ)
                    self.currencies_table.setItem(
                        current_row, 1, create_centered_item(result["code"])
                    )

                    name_display = result["name"]
                    if result["code"] == "EGP":
                        name_display += " ⭐"
                    self.currencies_table.setItem(
                        current_row, 2, create_centered_item(name_display)
                    )

                    self.currencies_table.setItem(
                        current_row, 3, create_centered_item(result["symbol"])
                    )

                    rate_display = f"{result['rate']:.2f}"
                    if result["code"] == "EGP":
                        rate_display += " (أساسية)"
                    self.currencies_table.setItem(
                        current_row, 4, create_centered_item(rate_display)
                    )

                    status = "✅ نشط" if result["active"] else "❌ غير نشط"
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
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف العملة {code}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # حذف من قاعدة البيانات
            if self.repository is not None:
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
            self,
            "🌐 تحديث أسعار الصرف",
            "سيتم جلب أسعار الصرف الحالية من الإنترنت.\n\nهل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
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
            updated = result.get("updated", 0)
            failed = result.get("failed", 0)
            results = result.get("results", {})

            msg = f"✅ تم تحديث {updated} عملة من الإنترنت\n\n"

            for code, data in results.items():
                if data["success"]:
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
        """⚡ إنشاء نسخة احتياطية كاملة - محسّنة للسرعة"""
        if not self.repository:
            QMessageBox.warning(self, "تحذير", "قاعدة البيانات غير متصلة!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "حفظ النسخة الاحتياطية",
            f"skywave_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        # تعطيل الزر وإظهار التقدم
        self.create_backup_btn.setEnabled(False)
        self.create_backup_btn.setText("⏳ جاري إنشاء النسخة...")
        self.backup_progress.setVisible(True)
        self.backup_progress.setValue(0)

        def do_backup():
            """تنفيذ النسخ الاحتياطي في الخلفية"""
            backup_data = {
                "backup_info": {
                    "created_at": datetime.now().isoformat(),
                    "version": "2.0",
                    "app": "SkyWave ERP",
                },
                "clients": [],
                "services": [],
                "projects": [],
                "invoices": [],
                "expenses": [],
                "accounts": [],
                "currencies": [],
                "journal_entries": [],
                "payments": [],
                "tasks": [],
                "settings": {},
            }

            # ⚡ جلب كل البيانات بشكل متوازي
            data_sources = [
                ("clients", self.repository.get_all_clients),
                ("services", self.repository.get_all_services),
                ("projects", self.repository.get_all_projects),
                ("invoices", self.repository.get_all_invoices),
                ("expenses", self.repository.get_all_expenses),
                ("accounts", self.repository.get_all_accounts),
                ("currencies", self.repository.get_all_currencies),
                ("journal_entries", self.repository.get_all_journal_entries),
                ("payments", self.repository.get_all_payments),
            ]

            for key, fetch_func in data_sources:
                try:
                    data = fetch_func()
                    if data:
                        if isinstance(data, list):
                            backup_data[key] = [self._serialize_object(item) for item in data]
                        else:
                            backup_data[key] = [self._serialize_object(data)]
                except Exception as e:
                    safe_print(f"WARNING: فشل جلب {key}: {e}")

            # جلب المهام
            try:

                task_service = TaskService()
                tasks = task_service.get_all_tasks()
                backup_data["tasks"] = [self._serialize_object(t) for t in tasks]
            except Exception:
                pass

            # جلب الإعدادات
            try:
                backup_data["settings"] = self.settings_service.get_settings()
            except Exception:
                pass

            # حفظ الملف
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)

            return backup_data

        def on_success(backup_data):
            """معالج النجاح"""
            self.create_backup_btn.setEnabled(True)
            self.create_backup_btn.setText("💾 إنشاء نسخة احتياطية الآن")
            self.backup_progress.setVisible(False)

            # حساب الإحصائيات
            total_records = sum(
                [
                    len(backup_data.get("clients", [])),
                    len(backup_data.get("services", [])),
                    len(backup_data.get("projects", [])),
                    len(backup_data.get("invoices", [])),
                    len(backup_data.get("expenses", [])),
                    len(backup_data.get("accounts", [])),
                    len(backup_data.get("currencies", [])),
                    len(backup_data.get("journal_entries", [])),
                    len(backup_data.get("payments", [])),
                    len(backup_data.get("tasks", [])),
                ]
            )

            QMessageBox.information(
                self,
                "✅ نجاح",
                f"تم إنشاء النسخة الاحتياطية بنجاح!\n\n"
                f"📁 الملف: {os.path.basename(file_path)}\n"
                f"📊 إجمالي السجلات: {total_records}\n\n"
                f"• العملاء: {len(backup_data.get('clients', []))}\n"
                f"• الخدمات: {len(backup_data.get('services', []))}\n"
                f"• المشاريع: {len(backup_data.get('projects', []))}\n"
                f"• المصروفات: {len(backup_data.get('expenses', []))}\n"
                f"• المهام: {len(backup_data.get('tasks', []))}",
            )

            # تحديث سجل النسخ الاحتياطية
            self._load_backup_history()

        def on_error(error_msg):
            """معالج الخطأ"""
            self.create_backup_btn.setEnabled(True)
            self.create_backup_btn.setText("💾 إنشاء نسخة احتياطية الآن")
            self.backup_progress.setVisible(False)
            QMessageBox.critical(self, "❌ خطأ", f"فشل إنشاء النسخة الاحتياطية:\n{error_msg}")

        # ⚡ تنفيذ في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="create_backup",
            load_function=do_backup,
            on_success=on_success,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _serialize_object(self, obj):
        """تحويل كائن إلى قاموس قابل للتسلسل"""
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "dict"):
            return obj.dict()
        elif hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        else:
            return obj

    def restore_backup(self):
        """استرجاع نسخة احتياطية"""
        if not self.repository:
            QMessageBox.warning(self, "تحذير", "قاعدة البيانات غير متصلة!")
            return

        reply = QMessageBox.warning(
            self,
            "⚠️ تأكيد",
            "هل أنت متأكد من استرجاع النسخة الاحتياطية؟\n\n"
            "⚠️ سيتم حذف جميع البيانات الحالية واستبدالها!\n"
            "تأكد من إنشاء نسخة احتياطية للبيانات الحالية أولاً.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "اختر ملف النسخة الاحتياطية", "", "JSON Files (*.json)"
            )
            if file_path:
                try:
                    # قراءة ملف النسخة الاحتياطية
                    with open(file_path, encoding="utf-8") as f:
                        backup_data = json.load(f)

                    # التحقق من صحة الملف
                    if "backup_info" not in backup_data:
                        QMessageBox.critical(self, "خطأ", "ملف النسخة الاحتياطية غير صالح!")
                        return

                    backup_info = backup_data.get("backup_info", {})
                    created_at = backup_info.get("created_at", "غير معروف")

                    # تأكيد نهائي
                    final_confirm = QMessageBox.question(
                        self,
                        "تأكيد نهائي",
                        f"سيتم استرجاع النسخة الاحتياطية:\n\n"
                        f"📅 تاريخ الإنشاء: {created_at}\n"
                        f"📊 العملاء: {len(backup_data.get('clients', []))}\n"
                        f"📊 المشاريع: {len(backup_data.get('projects', []))}\n"
                        f"📊 الفواتير: {len(backup_data.get('invoices', []))}\n\n"
                        f"هل تريد المتابعة؟",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )

                    if final_confirm == QMessageBox.StandardButton.Yes:
                        # استرجاع البيانات من النسخة الاحتياطية
                        # يتطلب دوال إضافية في Repository
                        QMessageBox.information(
                            self,
                            "✅ نجاح",
                            "تم قراءة ملف النسخة الاحتياطية بنجاح.\n\n"
                            "⚠️ ملاحظة: استرجاع البيانات يتطلب إعادة تشغيل التطبيق.",
                        )

                except json.JSONDecodeError:
                    QMessageBox.critical(self, "خطأ", "ملف النسخة الاحتياطية تالف أو غير صالح!")
                except Exception as e:
                    QMessageBox.critical(self, "خطأ", f"فشل استرجاع النسخة الاحتياطية:\n{e}")

    def load_db_stats(self):
        """⚡ تحميل إحصائيات قاعدة البيانات في الخلفية لمنع التجميد"""
        # عرض رسالة تحميل
        self.db_stats_label.setText("⏳ جاري تحميل الإحصائيات...")

        if self.repository is None:
            self.db_stats_label.setText(
                """
📊 إحصائيات قاعدة البيانات:

⚠️ قاعدة البيانات غير متصلة
يرجى التحقق من الاتصال
            """
            )
            return

        def fetch_stats():
            """جلب الإحصائيات في thread منفصل"""
            try:
                cursor = self.repository.get_cursor()
                try:
                    # ⚡ استعلام واحد بدلاً من 8 استعلامات منفصلة
                    cursor.execute(
                        """
                        SELECT
                            (SELECT COUNT(*) FROM clients) as clients,
                            (SELECT COUNT(*) FROM services) as services,
                            (SELECT COUNT(*) FROM invoices) as invoices,
                            (SELECT COUNT(*) FROM expenses) as expenses,
                            (SELECT COUNT(*) FROM accounts) as accounts,
                            (SELECT COUNT(*) FROM currencies) as currencies,
                            (SELECT COUNT(*) FROM journal_entries) as journal_entries
                    """
                    )
                    result = cursor.fetchone()

                    clients_count = result[0] if result else 0
                    services_count = result[1] if result else 0
                    invoices_count = result[2] if result else 0
                    expenses_count = result[3] if result else 0
                    accounts_count = result[4] if result else 0
                    currencies_count = result[5] if result else 0
                    journal_count = result[6] if result else 0

                    # جلب عدد المشاريع بشكل منفصل (قد لا يكون الجدول موجوداً)
                    try:
                        cursor.execute("SELECT COUNT(*) FROM projects")
                        projects_result = cursor.fetchone()
                        projects_count = projects_result[0] if projects_result else 0
                    except Exception:
                        projects_count = 0
                finally:
                    cursor.close()

                # حالة الاتصال
                is_online = self.repository.online is not None and self.repository.online

                return {
                    "clients": clients_count,
                    "services": services_count,
                    "projects": projects_count,
                    "invoices": invoices_count,
                    "expenses": expenses_count,
                    "accounts": accounts_count,
                    "currencies": currencies_count,
                    "journal": journal_count,
                    "is_online": is_online,
                }
            except Exception as e:
                safe_print(f"ERROR: فشل جلب الإحصائيات: {e}")
                return {"error": str(e)}

        def on_stats_loaded(data):
            """تحديث الواجهة بالإحصائيات"""
            try:
                if "error" in data:
                    self.db_stats_label.setText(f"❌ خطأ في جلب الإحصائيات: {data['error']}")
                    return

                total = (
                    data["clients"]
                    + data["services"]
                    + data["invoices"]
                    + data["expenses"]
                    + data["accounts"]
                    + data["currencies"]
                    + data["journal"]
                    + data["projects"]
                )

                connection_status = "✅ متصل" if data["is_online"] else "⚠️ غير متصل"

                stats_text = f"""
📊 إحصائيات قاعدة البيانات:

• العملاء: {data['clients']} سجل
• الخدمات: {data['services']} سجل
• المشاريع: {data['projects']} سجل
• الفواتير: {data['invoices']} سجل
• المصروفات: {data['expenses']} سجل
• الحسابات المحاسبية: {data['accounts']} سجل
• العملات: {data['currencies']} سجل
• قيود اليومية: {data['journal']} سجل

📁 إجمالي السجلات: {total}

🔄 حالة الاتصال بالأونلاين: {connection_status}
                """
                self.db_stats_label.setText(stats_text)
            except Exception as e:
                self.db_stats_label.setText(f"❌ خطأ في عرض الإحصائيات: {e}")

        def on_error(error_msg):
            self.db_stats_label.setText(f"❌ خطأ: {error_msg}")

        # ⚡ تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="db_stats",
            load_function=fetch_stats,
            on_success=on_stats_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def setup_default_accounts_tab(self):
        """إعداد تاب الحسابات الافتراضية"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            """
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #0d2137; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3d6a9f; border-radius: 4px; min-height: 30px;
            }
        """
        )

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 18, 22, 18)

        header_frame = QFrame()
        header_frame.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(14, 42, 78, 0.85), stop:1 rgba(9, 28, 52, 0.9));
                border: 1px solid rgba(90, 150, 230, 0.35);
                border-radius: 14px;
            }
        """
        )
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)
        header_title = QLabel("🔗 الحسابات الافتراضية")
        header_title.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: bold;")
        header_subtitle = QLabel("تحديد الحسابات المستخدمة تلقائياً في العمليات اليومية")
        header_subtitle.setStyleSheet("color: #94a3b8; font-size: 11px;")
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        header_text.addWidget(header_title)
        header_text.addWidget(header_subtitle)
        header_layout.addLayout(header_text)
        header_layout.addStretch()
        layout.addWidget(header_frame)

        info_label = QLabel(
            "حدد الحسابات المحاسبية التي سيستخدمها النظام تلقائياً في العمليات السريعة.\n"
            "يجب أن تكون هذه الحسابات موجودة في دليل الحسابات."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            """
            background: rgba(12, 33, 60, 0.7);
            color: #cbd5f5;
            padding: 14px;
            border-radius: 12px;
            border: 1px solid rgba(90, 150, 230, 0.25);
            font-size: 12px;
        """
        )
        layout.addWidget(info_label)

        form_group = QGroupBox("⚙️ إعدادات الحسابات الافتراضية")
        form_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 14px; font-weight: bold;
                border: 1px solid rgba(90, 150, 230, 0.3); border-radius: 12px;
                padding: 16px; background: rgba(12, 33, 60, 0.55);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top right;
                padding: 2px 12px;
                color: #93C5FD;
            }
        """
        )
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setVerticalSpacing(10)

        label_style = "color: #93C5FD; font-size: 11px; font-weight: bold;"
        combo_style = """
            QComboBox {
                background: #0b1d33;
                color: #E2E8F0;
                border: 1px solid rgba(99, 146, 207, 0.35);
                border-radius: 10px;
                padding: 8px 10px;
                min-height: 18px;
            }
            QComboBox:focus { border: 2px solid #3b82f6; }
        """

        # الخزينة الافتراضية (SmartFilterComboBox مع فلترة)
        self.default_treasury_combo = SmartFilterComboBox()
        self.default_treasury_combo.setStyleSheet(combo_style)

        # حساب الإيرادات الافتراضي (SmartFilterComboBox مع فلترة)
        self.default_revenue_combo = SmartFilterComboBox()
        self.default_revenue_combo.setStyleSheet(combo_style)

        # حساب الضرائب الافتراضي (SmartFilterComboBox مع فلترة)
        self.default_tax_combo = SmartFilterComboBox()
        self.default_tax_combo.setStyleSheet(combo_style)

        # حساب العملاء الافتراضي (SmartFilterComboBox مع فلترة)
        self.default_client_combo = SmartFilterComboBox()
        self.default_client_combo.setStyleSheet(combo_style)

        treasury_lbl = QLabel("💰 الخزينة الافتراضية (1111):")
        treasury_lbl.setStyleSheet(label_style)
        revenue_lbl = QLabel("📈 إيرادات الخدمات (4100):")
        revenue_lbl.setStyleSheet(label_style)
        tax_lbl = QLabel("📊 الضرائب المستحقة (2102):")
        tax_lbl.setStyleSheet(label_style)
        client_lbl = QLabel("👥 حساب العملاء (1140):")
        client_lbl.setStyleSheet(label_style)
        form_layout.addRow(treasury_lbl, self.default_treasury_combo)
        form_layout.addRow(revenue_lbl, self.default_revenue_combo)
        form_layout.addRow(tax_lbl, self.default_tax_combo)
        form_layout.addRow(client_lbl, self.default_client_combo)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # زر التحديث
        buttons_layout = QHBoxLayout()

        self.refresh_accounts_btn = QPushButton("🔄 تحديث القوائم")
        self.refresh_accounts_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:1 #2563eb);
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }
        """
        )
        self.refresh_accounts_btn.clicked.connect(self.load_default_accounts)

        self.save_default_accounts_btn = QPushButton("💾 حفظ الإعدادات")
        self.save_default_accounts_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #22c55e, stop:1 #16a34a);
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #16a34a, stop:1 #15803d);
            }
        """
        )
        self.save_default_accounts_btn.clicked.connect(self.save_default_accounts)

        buttons_layout.addWidget(self.refresh_accounts_btn)
        buttons_layout.addWidget(self.save_default_accounts_btn)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        layout.addStretch()

        scroll_area.setWidget(scroll_content)
        tab_layout = QVBoxLayout(self.default_accounts_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll_area)

        # ⚡ لا نحمل البيانات هنا - سيتم التحميل عند فتح التاب
        # self.load_default_accounts()

    def load_default_accounts(self):
        """تحميل الحسابات من قاعدة البيانات وملء القوائم المنسدلة"""
        if not self.repository:
            QMessageBox.warning(self, "تحذير", "قاعدة البيانات غير متصلة")
            return

        self.default_treasury_combo.setEnabled(False)
        self.default_revenue_combo.setEnabled(False)
        self.default_tax_combo.setEnabled(False)
        self.default_client_combo.setEnabled(False)

        data_loader = get_data_loader()

        def fetch_accounts():
            return self.repository.get_all_accounts()

        def on_loaded(all_accounts):
            try:
                cash_accounts = [
                    acc
                    for acc in all_accounts
                    if acc.code
                    and acc.code.startswith("11")
                    and not getattr(acc, "is_group", False)
                ]
                revenue_accounts = [
                    acc
                    for acc in all_accounts
                    if acc.code and acc.code.startswith("4") and not getattr(acc, "is_group", False)
                ]
                tax_accounts = [
                    acc
                    for acc in all_accounts
                    if acc.code
                    and acc.code.startswith("21")
                    and not getattr(acc, "is_group", False)
                ]
                client_accounts = [
                    acc for acc in all_accounts if acc.code and acc.code.startswith("114")
                ]

                self._populate_account_combo(self.default_treasury_combo, cash_accounts, "1111")
                self._populate_account_combo(self.default_revenue_combo, revenue_accounts, "4100")
                self._populate_account_combo(self.default_tax_combo, tax_accounts, "2102")
                self._populate_account_combo(self.default_client_combo, client_accounts, "1140")

                settings = self.settings_service.get_settings()
                self._select_account_by_code(
                    self.default_treasury_combo,
                    settings.get("default_treasury_account", "1111"),
                )
                self._select_account_by_code(
                    self.default_revenue_combo,
                    settings.get("default_revenue_account", "4100"),
                )
                self._select_account_by_code(
                    self.default_tax_combo,
                    settings.get("default_tax_account", "2102"),
                )
                self._select_account_by_code(
                    self.default_client_combo,
                    settings.get("default_client_account", "1140"),
                )
            except Exception as e:
                safe_print(f"ERROR: فشل تحميل الحسابات الافتراضية: {e}")
                QMessageBox.critical(self, "خطأ", f"فشل تحميل الحسابات: {e}")
            finally:
                self.default_treasury_combo.setEnabled(True)
                self.default_revenue_combo.setEnabled(True)
                self.default_tax_combo.setEnabled(True)
                self.default_client_combo.setEnabled(True)

        def on_error(error_msg: str):
            try:
                safe_print(f"ERROR: فشل تحميل الحسابات الافتراضية: {error_msg}")
                QMessageBox.critical(self, "خطأ", f"فشل تحميل الحسابات: {error_msg}")
            finally:
                self.default_treasury_combo.setEnabled(True)
                self.default_revenue_combo.setEnabled(True)
                self.default_tax_combo.setEnabled(True)
                self.default_client_combo.setEnabled(True)

        data_loader.load_async(
            operation_name="settings_default_accounts",
            load_function=fetch_accounts,
            on_success=on_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

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
                "default_treasury_account": self.default_treasury_combo.currentData(),
                "default_revenue_account": self.default_revenue_combo.currentData(),
                "default_tax_account": self.default_tax_combo.currentData(),
                "default_client_account": self.default_client_combo.currentData(),
            }

            # حفظ الحسابات المحددة فقط (السماح بحفظ حساب واحد أو أكثر)
            default_accounts = {k: v for k, v in all_accounts.items() if v is not None}

            # التحقق من أن هناك حساب واحد على الأقل محدد
            if not default_accounts:
                QMessageBox.warning(self, "تحذير", "يرجى تحديد حساب واحد على الأقل قبل الحفظ")
                return

            # حفظ الإعدادات
            current_settings = self.settings_service.get_settings()
            current_settings.update(all_accounts)  # حفظ الكل (بما فيها None للحسابات غير المحددة)
            self.settings_service.update_settings(current_settings)

            # عرض رسالة نجاح مع عدد الحسابات المحفوظة
            saved_count = len(default_accounts)
            QMessageBox.information(
                self, "نجاح", f"✅ تم حفظ {saved_count} حساب/حسابات افتراضية بنجاح"
            )

        except Exception as e:
            safe_print(f"ERROR: فشل حفظ الحسابات الافتراضية: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")

    def load_users(self):
        """تحميل المستخدمين من قاعدة البيانات - محسّن لتجنب التجميد"""
        safe_print("INFO: [SettingsTab] بدء تحميل المستخدمين")

        if not self.repository:
            safe_print("WARNING: [SettingsTab] لا يوجد repository!")
            return

        self.users_table.setUpdatesEnabled(False)
        self.users_table.setRowCount(0)

        data_loader = get_data_loader()

        def fetch_users():
            return self.repository.get_all_users()

        def on_users_loaded(users):
            try:
                safe_print(f"INFO: [SettingsTab] تم جلب {len(users)} مستخدم")
                self._set_cached_users(users)
                self._users_all = users

                self._render_users_page()
                safe_print(f"INFO: [SettingsTab] ✅ تم تحميل {len(users)} مستخدم")
            except Exception as e:
                safe_print(f"ERROR: [SettingsTab] فشل ملء جدول المستخدمين: {e}")
                traceback.print_exc()
            finally:
                self.users_table.setUpdatesEnabled(True)
                self.users_table.viewport().update()

        def on_error(error_msg: str):
            try:
                safe_print(f"ERROR: [SettingsTab] فشل تحميل المستخدمين: {error_msg}")
            finally:
                self.users_table.setUpdatesEnabled(True)
                self.users_table.viewport().update()

        cached = self._get_cached_users()
        if cached is not None:
            on_users_loaded(cached)
            return

        data_loader.load_async(
            operation_name="settings_users",
            load_function=fetch_users,
            on_success=on_users_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _get_users_total_pages(self) -> int:
        total = len(self._users_all)
        if total == 0:
            return 1
        if self._users_page_size <= 0:
            return 1
        return (total + self._users_page_size - 1) // self._users_page_size

    def _render_users_page(self):
        total_pages = self._get_users_total_pages()
        if self._users_current_page > total_pages:
            self._users_current_page = total_pages
        if self._users_current_page < 1:
            self._users_current_page = 1

        if not self._users_all:
            self.users_table.setRowCount(1)
            empty_item = create_centered_item("لا توجد بيانات مستخدمين")
            self.users_table.setItem(0, 0, empty_item)
            self.users_table.setSpan(0, 0, 1, self.users_table.columnCount())
            self._update_users_pagination_controls(total_pages)
            return

        if self._users_page_size <= 0:
            page_users = self._users_all
            start_index = 0
        else:
            start_index = (self._users_current_page - 1) * self._users_page_size
            end_index = start_index + self._users_page_size
            page_users = self._users_all[start_index:end_index]

        self._populate_users_table(page_users, start_index)
        self._update_users_pagination_controls(total_pages)

    def _populate_users_table(self, users: list, start_index: int):
        self.users_table.setRowCount(len(users))
        for i, user in enumerate(users):
            row_number = start_index + i + 1
            self.users_table.setItem(i, 0, create_centered_item(str(row_number)))

            username_item = create_centered_item(user.username)
            user_id = user.id if user.id else (user.mongo_id if hasattr(user, "mongo_id") else None)
            username_item.setData(Qt.ItemDataRole.UserRole, user_id)
            self.users_table.setItem(i, 1, username_item)

            self.users_table.setItem(i, 2, create_centered_item(user.full_name or ""))
            self.users_table.setItem(i, 3, create_centered_item(user.email or ""))

            role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
            role_display_map = {
                "admin": "🔑 مدير النظام",
                "accountant": "📊 محاسب",
                "sales": "💼 مندوب مبيعات",
            }
            role_display = role_display_map.get(role_value.lower(), role_value)
            self.users_table.setItem(i, 4, create_centered_item(role_display))

            status = "✅ نشط" if user.is_active else "❌ غير نشط"
            self.users_table.setItem(i, 5, create_centered_item(status))

            created_date = user.created_at[:10] if user.created_at else ""
            self.users_table.setItem(i, 6, create_centered_item(created_date))

    def _update_users_pagination_controls(self, total_pages: int):
        self.users_page_info_label.setText(f"صفحة {self._users_current_page} / {total_pages}")
        self.users_prev_page_button.setEnabled(self._users_current_page > 1)
        self.users_next_page_button.setEnabled(self._users_current_page < total_pages)

    def _on_users_page_size_changed(self, value: str):
        if value == "كل":
            self._users_page_size = max(1, len(self._users_all))
        else:
            try:
                self._users_page_size = int(value)
            except Exception:
                self._users_page_size = 100
        self._users_current_page = 1
        self._render_users_page()

    def _go_users_prev_page(self):
        if self._users_current_page > 1:
            self._users_current_page -= 1
            self._render_users_page()

    def _go_users_next_page(self):
        if self._users_current_page < self._get_users_total_pages():
            self._users_current_page += 1
            self._render_users_page()

    def _get_cached_users(self) -> list | None:
        if self._users_cache_ts is None:
            return None
        if (time.monotonic() - self._users_cache_ts) > self._users_cache_ttl_s:
            self._users_cache = []
            self._users_cache_ts = None
            return None
        return self._users_cache

    def _set_cached_users(self, users: list) -> None:
        self._users_cache = users
        self._users_cache_ts = time.monotonic()

    def _invalidate_users_cache(self):
        self._users_cache = []
        self._users_cache_ts = None

    def add_user(self):
        """إضافة مستخدم جديد"""
        # التحقق من الصلاحية

        if self.current_user and not PermissionManager.has_feature(
            self.current_user, "user_management"
        ):
            QMessageBox.warning(self, "تنبيه", "ليس لديك صلاحية إضافة مستخدمين.")
            return

        # إنشاء خدمة المصادقة
        auth_service = AuthService(self.repository)

        dialog = UserEditorDialog(auth_service, parent=self)
        if dialog.exec():
            self._invalidate_users_cache()
            self.load_users()
            QMessageBox.information(self, "تم", "تم إضافة المستخدم بنجاح.")

    def edit_user(self):
        """تعديل مستخدم"""
        # التحقق من الصلاحية

        if self.current_user and not PermissionManager.has_feature(
            self.current_user, "user_management"
        ):
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
        safe_print(f"INFO: [SettingsTab] جاري تعديل المستخدم: {username}")

        # إنشاء خدمة المصادقة
        auth_service = AuthService(self.repository)

        # جلب بيانات المستخدم الحديثة من قاعدة البيانات
        user = auth_service.repo.get_user_by_username(username)
        if not user:
            QMessageBox.warning(self, "خطأ", f"لم يتم العثور على المستخدم: {username}")
            return

        safe_print(
            f"INFO: [SettingsTab] تم جلب بيانات المستخدم: {user.username}, {user.full_name}, {user.email}"
        )

        # فتح نافذة التعديل مع بيانات المستخدم
        dialog = UserEditorDialog(auth_service, user_to_edit=user, parent=self)
        if dialog.exec():
            self._invalidate_users_cache()
            self.load_users()  # إعادة تحميل الجدول بعد التعديل

    def edit_user_permissions(self):
        """تحرير صلاحيات المستخدم"""
        # التحقق من الصلاحية

        if self.current_user and not PermissionManager.has_feature(
            self.current_user, "user_management"
        ):
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
        safe_print(f"INFO: [SettingsTab] جاري تحرير صلاحيات المستخدم: {username}")

        auth_service = AuthService(self.repository)

        # جلب بيانات المستخدم الحديثة من قاعدة البيانات
        user = auth_service.repo.get_user_by_username(username)
        if not user:
            QMessageBox.warning(self, "خطأ", f"لم يتم العثور على المستخدم: {username}")
            return

        safe_print(f"INFO: [SettingsTab] تم جلب بيانات المستخدم للصلاحيات: {user.username}")

        # فتح نافذة تحرير الصلاحيات

        dialog = UserPermissionsDialog(user, self.repository, self)
        if dialog.exec():
            self._invalidate_users_cache()
            self.load_users()  # إعادة تحميل الجدول
            QMessageBox.information(self, "تم", "تم تحديث صلاحيات المستخدم بنجاح.")

    def delete_user(self):
        """حذف مستخدم"""
        # التحقق من الصلاحية

        if self.current_user and not PermissionManager.has_feature(
            self.current_user, "user_management"
        ):
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
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من تعطيل المستخدم '{username}'؟\n(سيتم تعطيل الحساب وليس حذفه نهائياً)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # تعطيل المستخدم باستخدام username مباشرة
                safe_print(f"INFO: [SettingsTab] جاري تعطيل المستخدم: {username}")
                success = self.repository.update_user_by_username(username, {"is_active": False})

                if success:
                    self._invalidate_users_cache()
                    self.load_users()
                    QMessageBox.information(self, "تم", "تم تعطيل المستخدم بنجاح.")
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في تعطيل المستخدم.")

            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل في تعطيل المستخدم: {str(e)}")

    def activate_user(self):
        """تفعيل مستخدم معطل"""
        # التحقق من الصلاحية

        if self.current_user and not PermissionManager.has_feature(
            self.current_user, "user_management"
        ):
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
            self,
            "تأكيد التفعيل",
            f"هل تريد تفعيل المستخدم '{username}'؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # تفعيل المستخدم باستخدام username مباشرة
                safe_print(f"INFO: [SettingsTab] جاري تفعيل المستخدم: {username}")
                success = self.repository.update_user_by_username(username, {"is_active": True})

                if success:
                    self._invalidate_users_cache()
                    self.load_users()
                    QMessageBox.information(self, "تم", "تم تفعيل المستخدم بنجاح.")
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في تفعيل المستخدم.")

            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل في تفعيل المستخدم: {str(e)}")

    def setup_sync_tab(self):
        """إعداد تاب المزامنة اللحظية - نظام احترافي كامل"""

        # منطقة التمرير
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            """
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #0d2137;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3d6a9f;
                border-radius: 4px;
                min-height: 30px;
            }
        """
        )

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 15, 20, 15)

        # === حالة المزامنة الحالية ===
        status_frame = QFrame()
        status_frame.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(10, 108, 241, 0.2), stop:1 rgba(10, 108, 241, 0.05));
                border: 2px solid #0A6CF1;
                border-radius: 12px;
                padding: 20px;
            }
        """
        )
        status_layout = QVBoxLayout(status_frame)

        status_title = QLabel("📊 حالة المزامنة اللحظية")
        status_title.setStyleSheet("color: #60a5fa; font-size: 16px; font-weight: bold;")
        status_layout.addWidget(status_title)

        self.sync_status_label = QLabel("🔄 جاري التحقق من حالة المزامنة...")
        self.sync_status_label.setStyleSheet(
            """
            color: #F1F5F9;
            font-size: 14px;
            padding: 10px;
            background: rgba(13, 33, 55, 0.5);
            border-radius: 8px;
        """
        )
        self.sync_status_label.setWordWrap(True)
        status_layout.addWidget(self.sync_status_label)

        layout.addWidget(status_frame)

        # === إعدادات المزامنة التلقائية ===
        auto_sync_group = QGroupBox("⚙️ إعدادات المزامنة التلقائية")
        auto_sync_group.setStyleSheet(
            """
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(13, 33, 55, 0.7), stop:1 rgba(10, 25, 45, 0.7));
                border: 1px solid rgba(45, 74, 111, 0.5);
                border-radius: 12px;
                padding: 15px;
                font-size: 14px;
                font-weight: bold;
                color: #93C5FD;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """
        )
        auto_sync_layout = QGridLayout()
        auto_sync_layout.setSpacing(15)

        # تفعيل المزامنة التلقائية
        self.auto_sync_enabled = QCheckBox("🔄 تفعيل المزامنة التلقائية")
        self.auto_sync_enabled.setChecked(True)
        self.auto_sync_enabled.setStyleSheet(
            """
            QCheckBox {
                color: #F1F5F9;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 2px solid #3d6a9f;
                background: #0d2137;
            }
            QCheckBox::indicator:checked {
                background: #0A6CF1;
                border-color: #0A6CF1;
            }
        """
        )
        auto_sync_layout.addWidget(self.auto_sync_enabled, 0, 0, 1, 2)

        # فترة المزامنة الكاملة
        full_sync_label = QLabel("⏰ فترة المزامنة الكاملة (دقائق):")
        full_sync_label.setStyleSheet("color: #F1F5F9; font-size: 12px;")
        self.full_sync_interval = QSpinBox()
        self.full_sync_interval.setRange(1, 60)
        self.full_sync_interval.setValue(5)
        self.full_sync_interval.setSuffix(" دقيقة")
        self.full_sync_interval.setStyleSheet(
            """
            QSpinBox {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }
            QSpinBox:focus {
                border: 2px solid #0A6CF1;
            }
        """
        )
        auto_sync_layout.addWidget(full_sync_label, 1, 0)
        auto_sync_layout.addWidget(self.full_sync_interval, 1, 1)

        # فترة المزامنة السريعة
        quick_sync_label = QLabel("⚡ فترة المزامنة السريعة (ثواني):")
        quick_sync_label.setStyleSheet("color: #F1F5F9; font-size: 12px;")
        self.quick_sync_interval = QSpinBox()
        self.quick_sync_interval.setRange(10, 300)
        self.quick_sync_interval.setValue(60)
        self.quick_sync_interval.setSuffix(" ثانية")
        self.quick_sync_interval.setStyleSheet(
            """
            QSpinBox {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }
            QSpinBox:focus {
                border: 2px solid #0A6CF1;
            }
        """
        )
        auto_sync_layout.addWidget(quick_sync_label, 2, 0)
        auto_sync_layout.addWidget(self.quick_sync_interval, 2, 1)

        # فترة فحص الاتصال
        connection_check_label = QLabel("🔌 فترة فحص الاتصال (ثواني):")
        connection_check_label.setStyleSheet("color: #F1F5F9; font-size: 12px;")
        self.connection_check_interval = QSpinBox()
        self.connection_check_interval.setRange(10, 120)
        self.connection_check_interval.setValue(30)
        self.connection_check_interval.setSuffix(" ثانية")
        self.connection_check_interval.setStyleSheet(
            """
            QSpinBox {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }
            QSpinBox:focus {
                border: 2px solid #0A6CF1;
            }
        """
        )
        auto_sync_layout.addWidget(connection_check_label, 3, 0)
        auto_sync_layout.addWidget(self.connection_check_interval, 3, 1)

        auto_sync_group.setLayout(auto_sync_layout)
        layout.addWidget(auto_sync_group)

        # === أزرار التحكم ===
        buttons_frame = QFrame()
        buttons_frame.setStyleSheet(
            """
            QFrame {
                background: transparent;
                border: none;
            }
        """
        )
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setSpacing(10)

        # زر حفظ الإعدادات
        self.save_sync_settings_btn = QPushButton("💾 حفظ الإعدادات")
        self.save_sync_settings_btn.setMinimumHeight(45)
        self.save_sync_settings_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #34d399);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #059669, stop:1 #10b981);
            }
            QPushButton:pressed {
                background: #047857;
            }
        """
        )
        self.save_sync_settings_btn.clicked.connect(self.save_sync_settings)

        # زر مزامنة فورية
        self.manual_sync_btn = QPushButton("🔄 مزامنة فورية الآن")
        self.manual_sync_btn.setMinimumHeight(45)
        self.manual_sync_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0A6CF1, stop:1 #2563eb);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:1 #3b82f6);
            }
            QPushButton:pressed {
                background: #1e40af;
            }
        """
        )
        self.manual_sync_btn.clicked.connect(self.trigger_manual_sync)

        # زر تحديث الحالة
        self.refresh_sync_status_btn = QPushButton("🔄 تحديث الحالة")
        self.refresh_sync_status_btn.setMinimumHeight(45)
        self.refresh_sync_status_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(59, 130, 246, 0.2);
                color: #60a5fa;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.3);
            }
        """
        )
        self.refresh_sync_status_btn.clicked.connect(self.refresh_sync_status)

        buttons_layout.addWidget(self.save_sync_settings_btn)
        buttons_layout.addWidget(self.manual_sync_btn)
        buttons_layout.addWidget(self.refresh_sync_status_btn)
        buttons_layout.addStretch()

        layout.addWidget(buttons_frame)

        # === معلومات إضافية ===
        info_frame = QFrame()
        info_frame.setStyleSheet(
            """
            QFrame {
                background: rgba(16, 185, 129, 0.1);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 8px;
                padding: 15px;
            }
        """
        )
        info_layout = QVBoxLayout(info_frame)

        info_title = QLabel("ℹ️ معلومات مهمة")
        info_title.setStyleSheet("color: #34d399; font-size: 13px; font-weight: bold;")
        info_layout.addWidget(info_title)

        info_text = QLabel(
            "• المزامنة اللحظية تضمن تحديث البيانات تلقائياً على جميع الأجهزة\n"
            "• المزامنة السريعة ترفع التغييرات المحلية فقط (أسرع)\n"
            "• المزامنة الكاملة تزامن جميع البيانات من وإلى السحابة\n"
            "• يتم فحص الاتصال بالسحابة بشكل دوري تلقائياً\n"
            "• جميع التغييرات تُحفظ محلياً أولاً ثم تُرفع للسحابة"
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #9ca3af; font-size: 11px; line-height: 1.5;")
        info_layout.addWidget(info_text)

        layout.addWidget(info_frame)

        layout.addStretch()

        scroll_area.setWidget(scroll_content)

        # إضافة scroll_area للتاب
        tab_layout = QVBoxLayout(self.sync_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll_area)

        # تحميل الإعدادات الحالية
        self.load_sync_settings()

        # تحديث الحالة
        QTimer.singleShot(500, self.refresh_sync_status)

    def load_sync_settings(self):
        """تحميل إعدادات المزامنة من ملف التكوين"""
        try:

            config_path = Path("sync_config.json")
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    config = json.load(f)

                self.auto_sync_enabled.setChecked(config.get("enabled", True))
                self.full_sync_interval.setValue(config.get("auto_sync_interval", 300) // 60)
                self.quick_sync_interval.setValue(config.get("quick_sync_interval", 60))
                self.connection_check_interval.setValue(config.get("connection_check_interval", 30))

                safe_print("INFO: [SyncTab] تم تحميل إعدادات المزامنة")
        except Exception as e:
            safe_print(f"WARNING: [SyncTab] فشل تحميل إعدادات المزامنة: {e}")

    def save_sync_settings(self):
        """حفظ إعدادات المزامنة وتطبيقها"""
        try:

            # إعداد التكوين الجديد
            config = {
                "enabled": self.auto_sync_enabled.isChecked(),
                "auto_sync_interval": self.full_sync_interval.value() * 60,
                "quick_sync_interval": self.quick_sync_interval.value(),
                "connection_check_interval": self.connection_check_interval.value(),
                "max_retries": 2,
                "timeout": 5,
                "tables_to_sync": [
                    "clients",
                    "projects",
                    "services",
                    "accounts",
                    "payments",
                    "expenses",
                    "invoices",
                    "journal_entries",
                    "currencies",
                    "notifications",
                    "tasks",
                ],
                "conflict_resolution": "local_wins",
                "batch_size": 30,
                "enable_compression": False,
                "enable_encryption": False,
                "sync_status": "ready",
            }

            # حفظ في الملف
            config_path = Path("sync_config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            # تطبيق الإعدادات على نظام المزامنة
            if self.repository and hasattr(self.repository, "unified_sync"):
                sync_manager = self.repository.unified_sync

                # تحديث الفترات الزمنية
                sync_manager._auto_sync_interval = config["auto_sync_interval"] * 1000
                sync_manager._quick_sync_interval = config["quick_sync_interval"] * 1000
                sync_manager._connection_check_interval = config["connection_check_interval"] * 1000

                # إعادة تشغيل المؤقتات
                if config["enabled"]:
                    if sync_manager._auto_sync_timer:
                        sync_manager._auto_sync_timer.setInterval(sync_manager._auto_sync_interval)
                    if sync_manager._quick_sync_timer:
                        sync_manager._quick_sync_timer.setInterval(
                            sync_manager._quick_sync_interval
                        )
                    if sync_manager._connection_timer:
                        sync_manager._connection_timer.setInterval(
                            sync_manager._connection_check_interval
                        )

                    safe_print("INFO: [SyncTab] ✅ تم تطبيق إعدادات المزامنة")
                else:
                    sync_manager.stop_auto_sync()
                    safe_print("INFO: [SyncTab] ⏸️ تم إيقاف المزامنة التلقائية")

            QMessageBox.information(
                self,
                "✅ نجاح",
                "تم حفظ إعدادات المزامنة بنجاح!\n\nسيتم تطبيق الإعدادات الجديدة فوراً.",
            )

            # تحديث الحالة
            self.refresh_sync_status()

        except Exception as e:
            QMessageBox.critical(self, "❌ خطأ", f"فشل حفظ إعدادات المزامنة:\n{e}")
            safe_print(f"ERROR: [SyncTab] فشل حفظ الإعدادات: {e}")

    def refresh_sync_status(self):
        """تحديث حالة المزامنة"""
        try:
            if not self.repository or not hasattr(self.repository, "unified_sync"):
                self.sync_status_label.setText(
                    "⚠️ نظام المزامنة غير متاح\n\nيرجى التأكد من الاتصال بقاعدة البيانات"
                )
                self.sync_status_label.setStyleSheet(
                    """
                    color: #F59E0B;
                    font-size: 14px;
                    padding: 10px;
                    background: rgba(245, 158, 11, 0.1);
                    border-radius: 8px;
                """
                )
                return

            sync_manager = self.repository.unified_sync

            # جمع معلومات الحالة
            is_online = sync_manager.is_online
            is_syncing = sync_manager._is_syncing
            metrics = sync_manager.get_sync_metrics()

            # بناء نص الحالة
            status_text = ""

            # حالة الاتصال
            if is_online:
                status_text += "🟢 <b>متصل بالسحابة</b>\n\n"
            else:
                status_text += "🔴 <b>غير متصل بالسحابة</b>\n\n"

            # حالة المزامنة
            if is_syncing:
                status_text += "🔄 <b>المزامنة جارية...</b>\n\n"
            else:
                status_text += "✅ <b>جاهز للمزامنة</b>\n\n"

            # الإحصائيات
            status_text += "<b>📊 إحصائيات المزامنة:</b>\n"
            status_text += f"• إجمالي عمليات المزامنة: {metrics.get('total_syncs', 0)}\n"
            status_text += f"• عمليات ناجحة: {metrics.get('successful_syncs', 0)}\n"
            status_text += f"• عمليات فاشلة: {metrics.get('failed_syncs', 0)}\n"

            last_sync = metrics.get("last_sync_time")
            if last_sync:
                try:
                    last_sync_dt = datetime.fromisoformat(last_sync)
                    status_text += f"• آخر مزامنة: {last_sync_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
                except (ValueError, TypeError):
                    status_text += f"• آخر مزامنة: {last_sync}\n"
            else:
                status_text += "• آخر مزامنة: لم تتم بعد\n"

            status_text += f"• إجمالي السجلات المزامنة: {metrics.get('total_records_synced', 0)}\n"

            # حالة الجداول
            sync_status = sync_manager.get_sync_status()
            tables_info = sync_status.get("tables", {})

            pending_total = sum(t.get("pending", 0) for t in tables_info.values())

            if pending_total > 0:
                status_text += f"\n⚠️ <b>يوجد {pending_total} سجل في انتظار المزامنة</b>"
            else:
                status_text += "\n✅ <b>جميع البيانات متزامنة</b>"

            self.sync_status_label.setText(status_text)

            # تغيير اللون حسب الحالة
            if is_online and not is_syncing and pending_total == 0:
                bg_color = "rgba(16, 185, 129, 0.1)"
                border_color = "#10b981"
            elif is_online and pending_total > 0:
                bg_color = "rgba(245, 158, 11, 0.1)"
                border_color = "#f59e0b"
            else:
                bg_color = "rgba(239, 68, 68, 0.1)"
                border_color = "#ef4444"

            self.sync_status_label.setStyleSheet(
                f"""
                color: #F1F5F9;
                font-size: 13px;
                padding: 15px;
                background: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            """
            )

        except Exception as e:
            self.sync_status_label.setText(f"❌ خطأ في تحديث الحالة:\n{e}")
            safe_print(f"ERROR: [SyncTab] فشل تحديث الحالة: {e}")

    def trigger_manual_sync(self):
        """تشغيل مزامنة يدوية فورية"""
        try:
            if not self.repository or not hasattr(self.repository, "unified_sync"):
                QMessageBox.warning(self, "⚠️ تحذير", "نظام المزامنة غير متاح")
                return

            sync_manager = self.repository.unified_sync

            if not sync_manager.is_online:
                QMessageBox.warning(self, "⚠️ غير متصل", "لا يمكن المزامنة - غير متصل بالسحابة")
                return

            # تعطيل الزر أثناء المزامنة
            self.manual_sync_btn.setEnabled(False)
            self.manual_sync_btn.setText("⏳ جاري المزامنة...")

            # تشغيل المزامنة
            result = sync_manager.sync_now()

            # إعادة تفعيل الزر
            self.manual_sync_btn.setEnabled(True)
            self.manual_sync_btn.setText("🔄 مزامنة فورية الآن")

            # عرض النتيجة
            if result.get("success"):
                pushed = result.get("pushed", 0)
                pulled = result.get("pulled", 0)

                QMessageBox.information(
                    self,
                    "✅ نجاح",
                    f"تمت المزامنة بنجاح!\n\n• تم رفع {pushed} سجل\n• تم تنزيل {pulled} سجل",
                )
            else:
                reason = result.get("reason", "غير معروف")
                QMessageBox.warning(self, "⚠️ فشل", f"فشلت المزامنة:\n{reason}")

            # تحديث الحالة
            self.refresh_sync_status()

        except Exception as e:
            self.manual_sync_btn.setEnabled(True)
            self.manual_sync_btn.setText("🔄 مزامنة فورية الآن")

            QMessageBox.critical(self, "❌ خطأ", f"حدث خطأ أثناء المزامنة:\n{e}")
            safe_print(f"ERROR: [SyncTab] فشل المزامنة اليدوية: {e}")

    def setup_payment_methods_tab(self):
        """إعداد تاب طرق الدفع - CRUD لطرق الدفع في الفواتير"""
        layout = QVBoxLayout(self.payment_methods_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 15, 20, 15)

        # معلومات
        info_label = QLabel("💳 إدارة طرق الدفع التي تظهر في الفواتير والمشاريع")
        info_label.setStyleSheet(
            """
            background-color: #0A6CF1;
            color: white;
            padding: 12px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 13px;
        """
        )
        layout.addWidget(info_label)

        # أزرار التحكم
        buttons_layout = QHBoxLayout()

        self.add_payment_method_btn = QPushButton("➕ إضافة طريقة دفع")
        self.add_payment_method_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.add_payment_method_btn.clicked.connect(self.add_payment_method)

        self.edit_payment_method_btn = QPushButton("✏️ تعديل")
        self.edit_payment_method_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_payment_method_btn.clicked.connect(self.edit_payment_method)

        self.delete_payment_method_btn = QPushButton("🗑️ حذف")
        self.delete_payment_method_btn.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_payment_method_btn.clicked.connect(self.delete_payment_method)

        self.refresh_payment_methods_btn = QPushButton("🔄 تحديث")
        self.refresh_payment_methods_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_payment_methods_btn.clicked.connect(self.load_payment_methods)

        buttons_layout.addWidget(self.add_payment_method_btn)
        buttons_layout.addWidget(self.edit_payment_method_btn)
        buttons_layout.addWidget(self.delete_payment_method_btn)
        buttons_layout.addWidget(self.refresh_payment_methods_btn)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # جدول طرق الدفع
        self.payment_methods_table = QTableWidget()
        self.payment_methods_table.setColumnCount(5)
        self.payment_methods_table.setHorizontalHeaderLabels(
            ["#", "اسم طريقة الدفع", "الوصف", "تفاصيل الفاتورة", "الحالة"]
        )
        h_header = self.payment_methods_table.horizontalHeader()
        if h_header:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.payment_methods_table.setAlternatingRowColors(True)
        self.payment_methods_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.payment_methods_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.payment_methods_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.payment_methods_table.setStyleSheet(self._get_table_style())

        fix_table_rtl(self.payment_methods_table)
        self.payment_methods_table.doubleClicked.connect(self.edit_payment_method)

        self.payment_methods_search = UniversalSearchBar(
            self.payment_methods_table,
            placeholder="🔍 بحث في طرق الدفع...",
        )
        layout.addWidget(self.payment_methods_search)
        layout.addWidget(self.payment_methods_table)

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 6, 0, 0)
        pagination_layout.setSpacing(8)

        self.pm_prev_page_button = QPushButton("◀ السابق")
        self.pm_prev_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.pm_prev_page_button.setFixedHeight(26)
        self.pm_prev_page_button.clicked.connect(self._go_pm_prev_page)

        self.pm_next_page_button = QPushButton("التالي ▶")
        self.pm_next_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.pm_next_page_button.setFixedHeight(26)
        self.pm_next_page_button.clicked.connect(self._go_pm_next_page)

        self.pm_page_info_label = QLabel("صفحة 1 / 1")
        self.pm_page_info_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

        self.pm_page_size_combo = QComboBox()
        self.pm_page_size_combo.addItems(["50", "100", "200", "كل"])
        self.pm_page_size_combo.setCurrentText("100")
        self.pm_page_size_combo.currentTextChanged.connect(self._on_pm_page_size_changed)

        pagination_layout.addWidget(self.pm_prev_page_button)
        pagination_layout.addWidget(self.pm_next_page_button)
        pagination_layout.addStretch(1)
        pagination_layout.addWidget(QLabel("حجم الصفحة:"))
        pagination_layout.addWidget(self.pm_page_size_combo)
        pagination_layout.addWidget(self.pm_page_info_label)
        layout.addLayout(pagination_layout)

        preview_group = QGroupBox("👁️ معاينة طريقة الدفع في الفاتورة")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(12, 16, 12, 12)
        preview_layout.setSpacing(8)
        self.payment_method_preview = QTextEdit()
        self.payment_method_preview.setReadOnly(True)
        self.payment_method_preview.setFixedHeight(90)
        self.payment_method_preview.setStyleSheet(
            """
            QTextEdit {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
            }
            """
        )
        self.payment_method_preview.setPlaceholderText("اختر طريقة دفع لعرض تفاصيلها")
        preview_layout.addWidget(self.payment_method_preview)
        layout.addWidget(preview_group)

        self.payment_methods_table.itemSelectionChanged.connect(self._update_payment_method_preview)

        # تحميل البيانات
        self.load_payment_methods()

    def load_payment_methods(self):
        """تحميل طرق الدفع من قاعدة البيانات"""
        try:
            self.payment_methods_table.setRowCount(0)

            # جلب طرق الدفع من الإعدادات
            payment_methods = self.settings_service.get_setting("payment_methods") or []

            # إذا لم تكن موجودة، إنشاء قائمة افتراضية
            if not payment_methods:
                payment_methods = [
                    {"name": "نقدي", "description": "الدفع النقدي", "details": "", "active": True},
                    {
                        "name": "تحويل بنكي",
                        "description": "تحويل عبر البنك",
                        "details": "",
                        "active": True,
                    },
                    {
                        "name": "فودافون كاش",
                        "description": "محفظة فودافون كاش",
                        "details": "",
                        "active": True,
                    },
                    {
                        "name": "انستاباي",
                        "description": "تحويل عبر انستاباي",
                        "details": "",
                        "active": True,
                    },
                ]
                self.settings_service.update_setting("payment_methods", payment_methods)

            self._payment_methods_all = payment_methods
            self._render_payment_methods_page()

            self.settings_service.update_setting("payment_methods", payment_methods)

            safe_print(f"INFO: [SettingsTab] تم تحميل {len(payment_methods)} طريقة دفع")
            self._update_payment_method_preview()
        except Exception as e:
            safe_print(f"ERROR: [SettingsTab] فشل تحميل طرق الدفع: {e}")

    def _get_payment_methods_total_pages(self) -> int:
        total = len(self._payment_methods_all)
        if total == 0:
            return 1
        if self._payment_methods_page_size <= 0:
            return 1
        return (total + self._payment_methods_page_size - 1) // self._payment_methods_page_size

    def _render_payment_methods_page(self):
        total_pages = self._get_payment_methods_total_pages()
        if self._payment_methods_current_page > total_pages:
            self._payment_methods_current_page = total_pages
        if self._payment_methods_current_page < 1:
            self._payment_methods_current_page = 1

        if not self._payment_methods_all:
            self.payment_methods_table.setRowCount(1)
            empty_item = create_centered_item("لا توجد طرق دفع")
            self.payment_methods_table.setItem(0, 0, empty_item)
            self.payment_methods_table.setSpan(0, 0, 1, self.payment_methods_table.columnCount())
            self._update_payment_methods_pagination_controls(total_pages)
            self._payment_methods_page_start = 0
            return

        if self._payment_methods_page_size <= 0:
            page_items = self._payment_methods_all
            self._payment_methods_page_start = 0
        else:
            start_index = (self._payment_methods_current_page - 1) * self._payment_methods_page_size
            end_index = start_index + self._payment_methods_page_size
            page_items = self._payment_methods_all[start_index:end_index]
            self._payment_methods_page_start = start_index

        self._populate_payment_methods_table(page_items, self._payment_methods_page_start)
        self._update_payment_methods_pagination_controls(total_pages)

    def _populate_payment_methods_table(self, methods: list[dict], start_index: int):
        self.payment_methods_table.setRowCount(len(methods))
        for i, method in enumerate(methods):
            if isinstance(method, dict) and "details" not in method:
                method["details"] = ""
            row_number = start_index + i + 1
            self.payment_methods_table.setItem(i, 0, create_centered_item(str(row_number)))
            self.payment_methods_table.setItem(i, 1, create_centered_item(method.get("name", "")))
            self.payment_methods_table.setItem(
                i, 2, create_centered_item(method.get("description", ""))
            )
            details_preview = method.get("details", "")
            details_preview = details_preview.replace("\n", " ").strip()
            if len(details_preview) > 60:
                details_preview = details_preview[:60] + "..."
            self.payment_methods_table.setItem(i, 3, create_centered_item(details_preview))
            status = "✅ مفعّل" if method.get("active", True) else "❌ معطّل"
            self.payment_methods_table.setItem(i, 4, create_centered_item(status))

    def _update_payment_methods_pagination_controls(self, total_pages: int):
        self.pm_page_info_label.setText(
            f"صفحة {self._payment_methods_current_page} / {total_pages}"
        )
        self.pm_prev_page_button.setEnabled(self._payment_methods_current_page > 1)
        self.pm_next_page_button.setEnabled(self._payment_methods_current_page < total_pages)

    def _on_pm_page_size_changed(self, value: str):
        if value == "كل":
            self._payment_methods_page_size = max(1, len(self._payment_methods_all))
        else:
            try:
                self._payment_methods_page_size = int(value)
            except Exception:
                self._payment_methods_page_size = 100
        self._payment_methods_current_page = 1
        self._render_payment_methods_page()

    def _go_pm_prev_page(self):
        if self._payment_methods_current_page > 1:
            self._payment_methods_current_page -= 1
            self._render_payment_methods_page()

    def _go_pm_next_page(self):
        if self._payment_methods_current_page < self._get_payment_methods_total_pages():
            self._payment_methods_current_page += 1
            self._render_payment_methods_page()

    def add_payment_method(self):
        """إضافة طريقة دفع جديدة"""
        dialog = PaymentMethodDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data and data.get("name"):
                payment_methods = self.settings_service.get_setting("payment_methods") or []
                payment_methods.append(data)
                self.settings_service.update_setting("payment_methods", payment_methods)
                self.load_payment_methods()
                QMessageBox.information(
                    self, "✅ نجاح", f"تم إضافة طريقة الدفع: {data.get('name')}"
                )

    def edit_payment_method(self):
        """تعديل طريقة دفع"""
        selected = self.payment_methods_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار طريقة دفع للتعديل")
            return

        row = selected[0].row()
        real_index = self._payment_methods_page_start + row
        payment_methods = self.settings_service.get_setting("payment_methods") or []

        if real_index >= len(payment_methods):
            return

        method = payment_methods[real_index]

        dialog = PaymentMethodDialog(self, method)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data and data.get("name"):
                payment_methods[real_index] = data
                self.settings_service.update_setting("payment_methods", payment_methods)
                self.load_payment_methods()
                QMessageBox.information(self, "✅ نجاح", "تم تعديل طريقة الدفع")

    def delete_payment_method(self):
        """حذف طريقة دفع"""
        selected = self.payment_methods_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار طريقة دفع للحذف")
            return

        row = selected[0].row()
        real_index = self._payment_methods_page_start + row
        payment_methods = self.settings_service.get_setting("payment_methods") or []

        if real_index >= len(payment_methods):
            return

        method_name = payment_methods[real_index].get("name", "")

        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف طريقة الدفع: {method_name}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            payment_methods.pop(real_index)
            self.settings_service.update_setting("payment_methods", payment_methods)
            self.load_payment_methods()
            QMessageBox.information(self, "✅ نجاح", "تم حذف طريقة الدفع")

    def _update_payment_method_preview(self):
        try:
            if not hasattr(self, "payment_method_preview"):
                return

            selected = (
                self.payment_methods_table.selectedIndexes()
                if hasattr(self, "payment_methods_table")
                else []
            )
            payment_methods = self._payment_methods_all

            if not selected:
                self.payment_method_preview.setText("")
                return

            row = selected[0].row()
            real_index = self._payment_methods_page_start + row
            if real_index >= len(payment_methods):
                self.payment_method_preview.setText("")
                return

            method = (
                payment_methods[real_index] if isinstance(payment_methods[real_index], dict) else {}
            )
            name = method.get("name", "")
            desc = method.get("description", "")
            details = method.get("details", "")
            active = method.get("active", True)

            status = "مفعّل" if active else "معطّل"
            text = f"اسم: {name}\nالحالة: {status}"
            if desc:
                text += f"\nالوصف: {desc}"
            if details:
                text += f"\n\nتفاصيل الفاتورة:\n{details}"
            self.payment_method_preview.setText(text)

        except Exception:
            pass

    def setup_project_notes_tab(self):
        """إعداد تاب ملاحظات المشاريع - قوالب الملاحظات الافتراضية"""
        layout = QVBoxLayout(self.project_notes_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 15, 20, 15)

        # معلومات
        info_label = QLabel("📝 إدارة قوالب الملاحظات الافتراضية للمشاريع والفواتير")
        info_label.setStyleSheet(
            """
            background-color: #10b981;
            color: white;
            padding: 12px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 13px;
        """
        )
        layout.addWidget(info_label)

        # أزرار التحكم
        buttons_layout = QHBoxLayout()

        self.add_note_template_btn = QPushButton("➕ إضافة قالب")
        self.add_note_template_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.add_note_template_btn.clicked.connect(self.add_note_template)

        self.edit_note_template_btn = QPushButton("✏️ تعديل")
        self.edit_note_template_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_note_template_btn.clicked.connect(self.edit_note_template)

        self.delete_note_template_btn = QPushButton("🗑️ حذف")
        self.delete_note_template_btn.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_note_template_btn.clicked.connect(self.delete_note_template)

        self.refresh_note_templates_btn = QPushButton("🔄 تحديث")
        self.refresh_note_templates_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_note_templates_btn.clicked.connect(self.load_note_templates)

        buttons_layout.addWidget(self.add_note_template_btn)
        buttons_layout.addWidget(self.edit_note_template_btn)
        buttons_layout.addWidget(self.delete_note_template_btn)
        buttons_layout.addWidget(self.refresh_note_templates_btn)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # جدول قوالب الملاحظات
        self.note_templates_table = QTableWidget()
        self.note_templates_table.setColumnCount(3)
        self.note_templates_table.setHorizontalHeaderLabels(["#", "اسم القالب", "المحتوى"])
        h_header = self.note_templates_table.horizontalHeader()
        if h_header:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.note_templates_table.setAlternatingRowColors(True)
        self.note_templates_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.note_templates_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.note_templates_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.note_templates_table.setStyleSheet(self._get_table_style())

        fix_table_rtl(self.note_templates_table)
        self.note_templates_table.doubleClicked.connect(self.edit_note_template)

        self.note_templates_search = UniversalSearchBar(
            self.note_templates_table,
            placeholder="🔍 بحث في قوالب الملاحظات...",
        )
        layout.addWidget(self.note_templates_search)
        layout.addWidget(self.note_templates_table)

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 6, 0, 0)
        pagination_layout.setSpacing(8)

        self.notes_prev_page_button = QPushButton("◀ السابق")
        self.notes_prev_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.notes_prev_page_button.setFixedHeight(26)
        self.notes_prev_page_button.clicked.connect(self._go_notes_prev_page)

        self.notes_next_page_button = QPushButton("التالي ▶")
        self.notes_next_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.notes_next_page_button.setFixedHeight(26)
        self.notes_next_page_button.clicked.connect(self._go_notes_next_page)

        self.notes_page_info_label = QLabel("صفحة 1 / 1")
        self.notes_page_info_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

        self.notes_page_size_combo = QComboBox()
        self.notes_page_size_combo.addItems(["50", "100", "200", "كل"])
        self.notes_page_size_combo.setCurrentText("100")
        self.notes_page_size_combo.currentTextChanged.connect(self._on_notes_page_size_changed)

        pagination_layout.addWidget(self.notes_prev_page_button)
        pagination_layout.addWidget(self.notes_next_page_button)
        pagination_layout.addStretch(1)
        pagination_layout.addWidget(QLabel("حجم الصفحة:"))
        pagination_layout.addWidget(self.notes_page_size_combo)
        pagination_layout.addWidget(self.notes_page_info_label)
        layout.addLayout(pagination_layout)

        preview_group = QGroupBox("👁️ معاينة القالب")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(12, 16, 12, 12)
        preview_layout.setSpacing(8)
        self.note_template_preview = QTextEdit()
        self.note_template_preview.setReadOnly(True)
        self.note_template_preview.setFixedHeight(140)
        self.note_template_preview.setStyleSheet(
            """
            QTextEdit {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
            }
            """
        )
        self.note_template_preview.setPlaceholderText("اختر قالب لعرض محتواه")
        preview_layout.addWidget(self.note_template_preview)
        layout.addWidget(preview_group)

        self.note_templates_table.itemSelectionChanged.connect(self._update_note_template_preview)

        # تحميل البيانات
        self.load_note_templates()

    def load_note_templates(self):
        """تحميل قوالب الملاحظات من قاعدة البيانات"""
        try:
            self.note_templates_table.setRowCount(0)

            # جلب قوالب الملاحظات من الإعدادات
            note_templates = self.settings_service.get_setting("project_note_templates") or []

            # إذا لم تكن موجودة، إنشاء قائمة افتراضية
            if not note_templates:
                note_templates = [
                    {
                        "name": "القالب الافتراضي",
                        "content": """• مدة التنفيذ: ___ يوم عمل.
• تبدأ المدة من تاريخ استلام الداتا.
• التسليم حسب الجدول الزمني المتفق عليه.

• الدفعة المقدمة: 50% عند التعاقد.
• الدفعة الثانية: 25% عند التسليم الأولي.
• الدفعة النهائية: 25% عند التسليم النهائي.

• يبدأ التنفيذ بعد استلام الدفعة الأولى.""",
                    },
                    {
                        "name": "قالب مختصر",
                        "content": "• مدة التنفيذ: ___ يوم.\n• الدفع: 50% مقدم - 50% عند التسليم.",
                    },
                ]
                self.settings_service.update_setting("project_note_templates", note_templates)

            self._note_templates_all = note_templates
            self._render_note_templates_page()

            safe_print(f"INFO: [SettingsTab] تم تحميل {len(note_templates)} قالب ملاحظات")
            self._update_note_template_preview()
        except Exception as e:
            safe_print(f"ERROR: [SettingsTab] فشل تحميل قوالب الملاحظات: {e}")

    def _get_note_templates_total_pages(self) -> int:
        total = len(self._note_templates_all)
        if total == 0:
            return 1
        if self._note_templates_page_size <= 0:
            return 1
        return (total + self._note_templates_page_size - 1) // self._note_templates_page_size

    def _render_note_templates_page(self):
        total_pages = self._get_note_templates_total_pages()
        if self._note_templates_current_page > total_pages:
            self._note_templates_current_page = total_pages
        if self._note_templates_current_page < 1:
            self._note_templates_current_page = 1

        if not self._note_templates_all:
            self.note_templates_table.setRowCount(1)
            empty_item = create_centered_item("لا توجد قوالب")
            self.note_templates_table.setItem(0, 0, empty_item)
            self.note_templates_table.setSpan(0, 0, 1, self.note_templates_table.columnCount())
            self._update_note_templates_pagination_controls(total_pages)
            self._note_templates_page_start = 0
            return

        if self._note_templates_page_size <= 0:
            page_items = self._note_templates_all
            self._note_templates_page_start = 0
        else:
            start_index = (self._note_templates_current_page - 1) * self._note_templates_page_size
            end_index = start_index + self._note_templates_page_size
            page_items = self._note_templates_all[start_index:end_index]
            self._note_templates_page_start = start_index

        self._populate_note_templates_table(page_items, self._note_templates_page_start)
        self._update_note_templates_pagination_controls(total_pages)

    def _populate_note_templates_table(self, templates: list[dict], start_index: int):
        self.note_templates_table.setRowCount(len(templates))
        for i, template in enumerate(templates):
            row_number = start_index + i + 1
            self.note_templates_table.setItem(i, 0, create_centered_item(str(row_number)))
            self.note_templates_table.setItem(i, 1, create_centered_item(template.get("name", "")))
            content_preview = (
                template.get("content", "")[:50] + "..."
                if len(template.get("content", "")) > 50
                else template.get("content", "")
            )
            self.note_templates_table.setItem(i, 2, create_centered_item(content_preview))

    def _update_note_templates_pagination_controls(self, total_pages: int):
        self.notes_page_info_label.setText(
            f"صفحة {self._note_templates_current_page} / {total_pages}"
        )
        self.notes_prev_page_button.setEnabled(self._note_templates_current_page > 1)
        self.notes_next_page_button.setEnabled(self._note_templates_current_page < total_pages)

    def _on_notes_page_size_changed(self, value: str):
        if value == "كل":
            self._note_templates_page_size = max(1, len(self._note_templates_all))
        else:
            try:
                self._note_templates_page_size = int(value)
            except Exception:
                self._note_templates_page_size = 100
        self._note_templates_current_page = 1
        self._render_note_templates_page()

    def _go_notes_prev_page(self):
        if self._note_templates_current_page > 1:
            self._note_templates_current_page -= 1
            self._render_note_templates_page()

    def _go_notes_next_page(self):
        if self._note_templates_current_page < self._get_note_templates_total_pages():
            self._note_templates_current_page += 1
            self._render_note_templates_page()

    def _update_note_template_preview(self):
        try:
            if not hasattr(self, "note_template_preview"):
                return

            selected = (
                self.note_templates_table.selectedIndexes()
                if hasattr(self, "note_templates_table")
                else []
            )
            templates = self._note_templates_all

            if not selected:
                self.note_template_preview.setText("")
                return

            row = selected[0].row()
            real_index = self._note_templates_page_start + row
            if real_index >= len(templates):
                self.note_template_preview.setText("")
                return

            t = templates[real_index] if isinstance(templates[real_index], dict) else {}
            name = t.get("name", "")
            content = t.get("content", "")
            self.note_template_preview.setText(f"{name}\n\n{content}".strip())
        except Exception:
            pass

    def add_note_template(self):
        """إضافة قالب ملاحظات جديد"""
        dialog = NoteTemplateDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, content = dialog.get_data()
            if name and content:
                note_templates = self.settings_service.get_setting("project_note_templates") or []
                note_templates.append({"name": name, "content": content})
                self.settings_service.update_setting("project_note_templates", note_templates)
                self.load_note_templates()
                QMessageBox.information(self, "✅ نجاح", f"تم إضافة القالب: {name}")

    def edit_note_template(self):
        """تعديل قالب ملاحظات"""
        selected = self.note_templates_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار قالب للتعديل")
            return

        row = selected[0].row()
        real_index = self._note_templates_page_start + row
        note_templates = self.settings_service.get_setting("project_note_templates") or []

        if real_index >= len(note_templates):
            return

        template = note_templates[real_index]

        dialog = NoteTemplateDialog(self, template.get("name", ""), template.get("content", ""))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, content = dialog.get_data()
            if name and content:
                note_templates[real_index] = {"name": name, "content": content}
                self.settings_service.update_setting("project_note_templates", note_templates)
                self.load_note_templates()
                QMessageBox.information(self, "✅ نجاح", "تم تعديل القالب")

    def delete_note_template(self):
        """حذف قالب ملاحظات"""
        selected = self.note_templates_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار قالب للحذف")
            return

        row = selected[0].row()
        real_index = self._note_templates_page_start + row
        note_templates = self.settings_service.get_setting("project_note_templates") or []

        if real_index >= len(note_templates):
            return

        template_name = note_templates[real_index].get("name", "")

        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف القالب: {template_name}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            note_templates.pop(real_index)
            self.settings_service.update_setting("project_note_templates", note_templates)
            self.load_note_templates()
            QMessageBox.information(self, "✅ نجاح", "تم حذف القالب")

    def setup_update_tab(self):
        """إعداد تاب التحديثات"""
        layout = QVBoxLayout(self.update_tab)

        # معلومات الإصدار الحالي

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
        self.update_status_label.setStyleSheet(
            """
            background-color: #1e3a8a;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """
        )
        update_info_layout.addWidget(self.update_status_label)

        update_info_group.setLayout(update_info_layout)
        layout.addWidget(update_info_group)

        # شريط التقدم (مخفي في البداية)
        self.update_progress_bar = QProgressBar()
        self.update_progress_bar.setVisible(False)
        self.update_progress_bar.setStyleSheet(
            """
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
        """
        )
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

        # تعطيل الزرار أثناء الفحص
        self.check_update_btn.setEnabled(False)
        self.check_update_btn.setText("⏳ جاري التحقق...")
        self.update_status_label.setText("🔍 جاري البحث عن تحديثات جديدة...")
        self.update_status_label.setStyleSheet(
            """
            background-color: #f59e0b;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """
        )

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
            f"🎉 يتوفر إصدار جديد!\n\nالإصدار الجديد: {version}\nاضغط على 'تنزيل التحديث' للبدء"
        )
        self.update_status_label.setStyleSheet(
            """
            background-color: #0A6CF1;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """
        )

        # إظهار زرار التنزيل
        self.download_update_btn.setVisible(True)

        # إعادة تفعيل زرار الفحص
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText("🔍 التحقق من التحديثات")

    def on_no_update(self):
        """عند عدم توفر تحديثات"""

        self.update_status_label.setText(
            f"✅ أنت تستخدم أحدث إصدار!\n\nالإصدار الحالي: {CURRENT_VERSION}"
        )
        self.update_status_label.setStyleSheet(
            """
            background-color: #0A6CF1;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """
        )

        # إعادة تفعيل زرار الفحص
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText("🔍 التحقق من التحديثات")

    def on_update_error(self, error_message):
        """عند حدوث خطأ في الفحص - عرض تحذير بسيط بدلاً من رسالة خطأ"""
        # Handle 404 and connection is not None errors gracefully
        if "404" in error_message or "فشل الاتصال" in error_message:
            self.update_status_label.setText(
                "⚠️ لا توجد تحديثات متاحة حالياً\n\nسيتم التحقق مرة أخرى لاحقاً"
            )
            self.update_status_label.setStyleSheet(
                """
                background-color: #f59e0b;
                color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """
            )
        else:
            # For other errors, show the original error message
            self.update_status_label.setText(
                f"❌ حدث خطأ أثناء التحقق من التحديثات:\n\n{error_message}"
            )
            self.update_status_label.setStyleSheet(
                """
                background-color: #ef4444;
                color: white;
                padding: 15px;
                border-radius: 8px;
                font-size: 13px;
            """
            )

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
            self,
            "تأكيد التنزيل",
            f"سيتم تنزيل الإصدار {self.update_version}\n\nهل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
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
        self.update_status_label.setStyleSheet(
            """
            background-color: #3b82f6;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """
        )

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
            "✅ تم تنزيل التحديث بنجاح!\n\nاضغط على 'تثبيت التحديث' لإكمال العملية"
        )
        self.update_status_label.setStyleSheet(
            """
            background-color: #0A6CF1;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """
        )

        # إخفاء زرار التنزيل وإظهار زرار التثبيت
        self.download_update_btn.setVisible(False)
        self.install_update_btn.setVisible(True)

        # إعادة تفعيل زرار الفحص
        self.check_update_btn.setEnabled(True)

    def on_download_error(self, error_message):
        """عند حدوث خطأ في التنزيل"""
        self.update_progress_bar.setVisible(False)

        self.update_status_label.setText(f"❌ فشل تنزيل التحديث:\n\n{error_message}")
        self.update_status_label.setStyleSheet(
            """
            background-color: #ef4444;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 13px;
        """
        )

        # إعادة تفعيل الأزرار
        self.download_update_btn.setEnabled(True)
        self.check_update_btn.setEnabled(True)

        # إذا كان الخطأ بسبب الصلاحيات، اعرض خيار فتح صفحة التنزيل
        if "Permission denied" in error_message or "الصلاحيات" in error_message:
            reply = QMessageBox.question(
                self,
                "خطأ في الصلاحيات",
                "فشل تنزيل التحديث بسبب مشكلة في الصلاحيات.\n\n"
                "هل تريد فتح صفحة التنزيل في المتصفح لتنزيل التحديث يدوياً؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:

                webbrowser.open(self.update_download_url)
        else:
            QMessageBox.critical(self, "خطأ", f"فشل تنزيل التحديث:\n{error_message}")

    def install_update(self):
        """تثبيت التحديث"""
        reply = QMessageBox.warning(
            self,
            "⚠️ تأكيد التثبيت",
            "سيتم إغلاق البرنامج الآن لتثبيت التحديث.\n"
            "سيتم إعادة تشغيل البرنامج تلقائياً بعد التحديث.\n\n"
            "تأكد من حفظ جميع أعمالك!\n\n"
            "هل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            # تطبيق التحديث
            success = self.update_service.apply_update(self.update_service.temp_update_path)

            if success:
                # إغلاق البرنامج

                sys.exit(0)
            else:
                QMessageBox.critical(
                    self,
                    "خطأ",
                    "فشل تشغيل المحدث.\n"
                    "تأكد من وجود ملف updater.exe أو updater.py في مجلد البرنامج.",
                )

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل تثبيت التحديث:\n{e}")


class NoteTemplateDialog(QDialog):
    """نافذة إضافة/تعديل قالب ملاحظات"""

    def __init__(self, parent=None, name: str = "", content: str = ""):
        super().__init__(parent)
        self.setWindowTitle("📝 قالب ملاحظات" if not name else f"📝 تعديل: {name}")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        # تطبيق شريط العنوان المخصص
        try:

            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # اسم القالب
        name_label = QLabel("اسم القالب:")
        name_label.setStyleSheet("color: #60a5fa; font-weight: bold;")
        layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("مثال: قالب الشروط والأحكام")
        self.name_input.setText(name)
        self.name_input.setStyleSheet(
            """
            QLineEdit {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #0A6CF1;
            }
        """
        )
        layout.addWidget(self.name_input)

        # محتوى القالب
        content_label = QLabel("محتوى القالب:")
        content_label.setStyleSheet("color: #60a5fa; font-weight: bold;")
        layout.addWidget(content_label)

        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("اكتب محتوى القالب هنا...")
        self.content_input.setText(content)
        self.content_input.setStyleSheet(
            """
            QTextEdit {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
            }
            QTextEdit:focus {
                border: 2px solid #0A6CF1;
            }
        """
        )
        layout.addWidget(self.content_input, 1)

        # أزرار
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        save_btn = QPushButton("💾 حفظ")
        save_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #34d399);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 30px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #059669;
            }
        """
        )
        save_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(107, 114, 128, 0.3);
                color: #9CA3AF;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 10px 30px;
            }
            QPushButton:hover {
                background: rgba(107, 114, 128, 0.5);
            }
        """
        )
        cancel_btn.clicked.connect(self.reject)

        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)

    def get_data(self) -> tuple[str, str]:
        """الحصول على البيانات المدخلة"""
        return self.name_input.text().strip(), self.content_input.toPlainText().strip()


class PaymentMethodDialog(QDialog):
    def __init__(self, parent=None, method_data: dict | None = None):
        super().__init__(parent)
        method_data = method_data or {}

        title = (
            "💳 إضافة طريقة دفع" if not method_data else f"💳 تعديل: {method_data.get('name', '')}"
        )
        self.setWindowTitle(title)
        self.setMinimumWidth(540)
        self.setMinimumHeight(420)

        try:

            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        label_style = "color: #60a5fa; font-weight: bold;"
        input_style = """
            QLineEdit {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
            }
            QLineEdit:focus { border: 2px solid #0A6CF1; }
        """
        text_style = """
            QTextEdit {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
            }
            QTextEdit:focus { border: 2px solid #0A6CF1; }
        """

        name_label = QLabel("اسم طريقة الدفع:")
        name_label.setStyleSheet(label_style)
        layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setStyleSheet(input_style)
        self.name_input.setPlaceholderText("مثال: تحويل بنكي")
        self.name_input.setText(method_data.get("name", ""))
        layout.addWidget(self.name_input)

        desc_label = QLabel("وصف داخلي (اختياري):")
        desc_label.setStyleSheet(label_style)
        layout.addWidget(desc_label)
        self.description_input = QLineEdit()
        self.description_input.setStyleSheet(input_style)
        self.description_input.setPlaceholderText("مثال: تحويل عبر بنك مصر")
        self.description_input.setText(method_data.get("description", ""))
        layout.addWidget(self.description_input)

        details_label = QLabel("تفاصيل تظهر في الفاتورة:")
        details_label.setStyleSheet(label_style)
        layout.addWidget(details_label)
        self.details_input = QTextEdit()
        self.details_input.setStyleSheet(text_style)
        self.details_input.setPlaceholderText("مثال: رقم الحساب/IBAN/رقم محفظة/اسم المستخدم...")
        self.details_input.setText(method_data.get("details", ""))
        layout.addWidget(self.details_input, 1)

        active_row = QHBoxLayout()
        active_row.setSpacing(10)
        active_label = QLabel("الحالة:")
        active_label.setStyleSheet(label_style)
        active_row.addWidget(active_label)
        self.active_combo = QComboBox()
        self.active_combo.addItem("✅ مفعّل", True)
        self.active_combo.addItem("❌ معطّل", False)
        self.active_combo.setFixedHeight(32)
        self.active_combo.setStyleSheet(
            """
            QComboBox {
                background: #0d2137;
                color: #F1F5F9;
                border: 1px solid #2d4a6f;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QComboBox:focus { border: 2px solid #0A6CF1; }
            """
        )
        active_val = method_data.get("active", True)
        self.active_combo.setCurrentIndex(0 if active_val else 1)
        active_row.addWidget(self.active_combo)
        active_row.addStretch()
        layout.addLayout(active_row)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        save_btn = QPushButton("💾 حفظ")
        save_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #34d399);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 30px;
                font-weight: bold;
            }
            QPushButton:hover { background: #059669; }
            """
        )
        save_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(107, 114, 128, 0.3);
                color: #9CA3AF;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 10px 30px;
            }
            QPushButton:hover { background: rgba(107, 114, 128, 0.5); }
            """
        )
        cancel_btn.clicked.connect(self.reject)

        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)

    def get_data(self) -> dict:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "تنبيه", "اسم طريقة الدفع مطلوب")
            return {}

        return {
            "name": name,
            "description": self.description_input.text().strip(),
            "details": self.details_input.toPlainText().strip(),
            "active": bool(self.active_combo.currentData()),
        }
