#!/usr/bin/env python3
"""
واجهة البحث المتقدم الاحترافية - Sky Wave ERP
تدعم البحث الذكي في جميع أقسام النظام مع فلاتر متقدمة
"""

import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QLabel, QFrame, QScrollArea, QGroupBox,
    QDateEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QTabWidget, QTextEdit,
    QSplitter, QProgressBar, QMenu, QApplication, QMessageBox, QDialog,
    QGridLayout, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QDate, QSize
from PyQt6.QtGui import QIcon, QFont, QPixmap, QPalette, QColor, QAction

from services.search_service import SmartSearchService, SearchScope, SearchType, SearchFilter, SearchResult
from core.repository import Repository


class SearchResultWidget(QFrame):
    """ويدجت عرض نتيجة بحث واحدة"""
    
    clicked = pyqtSignal(str, str)  # item_type, item_id
    
    def __init__(self, result: SearchResult):
        super().__init__()
        self.result = result
        self.setup_ui()
        
    def setup_ui(self):
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            SearchResultWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin: 2px;
            }
            SearchResultWidget:hover {
                background-color: #f5f5f5;
                border-color: #4a90e2;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # العنوان الرئيسي
        title_label = QLabel(self.result.title)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #1a237e;")
        layout.addWidget(title_label)
        
        # العنوان الفرعي
        if self.result.subtitle:
            subtitle_label = QLabel(self.result.subtitle)
            subtitle_label.setStyleSheet("color: #666; font-size: 10px;")
            layout.addWidget(subtitle_label)
        
        # الوصف
        if self.result.description:
            desc_label = QLabel(self.result.description)
            desc_label.setStyleSheet("color: #888; font-size: 9px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # معلومات إضافية
        info_layout = QHBoxLayout()
        
        # درجة الصلة
        relevance_label = QLabel(f"الصلة: {self.result.relevance_score:.0f}%")
        relevance_label.setStyleSheet("color: #4a90e2; font-size: 8px; font-weight: bold;")
        info_layout.addWidget(relevance_label)
        
        info_layout.addStretch()
        
        # التاريخ
        if self.result.created_date:
            date_str = self.result.created_date.strftime("%Y-%m-%d")
            date_label = QLabel(f"📅 {date_str}")
            date_label.setStyleSheet("color: #999; font-size: 8px;")
            info_layout.addWidget(date_label)
        
        # المبلغ
        if self.result.amount:
            amount_label = QLabel(f"💰 {self.result.amount:,.0f}")
            amount_label.setStyleSheet("color: #10b981; font-size: 8px; font-weight: bold;")
            info_layout.addWidget(amount_label)
        
        layout.addLayout(info_layout)
        
        # الحقول المطابقة
        if self.result.matched_fields:
            matched_text = "المطابقة في: " + ", ".join(self.result.matched_fields)
            matched_label = QLabel(matched_text)
            matched_label.setStyleSheet("color: #ff9800; font-size: 8px; font-style: italic;")
            layout.addWidget(matched_label)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.result.item_type, self.result.item_id)
        super().mousePressEvent(event)


class SearchThread(QThread):
    """خيط البحث المنفصل لتجنب تجميد الواجهة"""
    
    results_ready = pyqtSignal(list)
    progress_update = pyqtSignal(int)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, search_service: SmartSearchService, query: str, scope: SearchScope, 
                 search_type: SearchType, filters: Optional[SearchFilter], limit: int):
        super().__init__()
        self.search_service = search_service
        self.query = query
        self.scope = scope
        self.search_type = search_type
        self.filters = filters
        self.limit = limit
    
    def run(self):
        try:
            self.progress_update.emit(10)
            results = self.search_service.search(
                self.query, self.scope, self.search_type, self.filters, self.limit
            )
            self.progress_update.emit(100)
            self.results_ready.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))


class AdvancedSearchWidget(QWidget):
    """
    واجهة البحث المتقدم الاحترافية
    تدعم البحث الذكي مع فلاتر متقدمة وعرض النتائج بطريقة احترافية
    """
    
    result_selected = pyqtSignal(str, str)  # item_type, item_id
    
    def __init__(self, repository: Repository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.search_service = SmartSearchService(repository)
        self.search_thread = None
        self.current_results = []
        
        self.setup_ui()
        self.setup_connections()
        self.load_search_statistics()
        
    def setup_ui(self):
        """إعداد واجهة المستخدم"""
        self.setWindowTitle("البحث المتقدم - Sky Wave ERP")
        self.setMinimumSize(1000, 700)
        
        # التخطيط الرئيسي
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # شريط البحث العلوي
        self.setup_search_bar(main_layout)
        
        # المحتوى الرئيسي (فلاتر + نتائج)
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(content_splitter)
        
        # لوحة الفلاتر
        self.setup_filters_panel(content_splitter)
        
        # لوحة النتائج
        self.setup_results_panel(content_splitter)
        
        # تعيين نسب التقسيم
        content_splitter.setSizes([300, 700])
        
        # شريط الحالة
        self.setup_status_bar(main_layout)
        
        # تطبيق الأنماط
        self.apply_styles()
    
    def setup_search_bar(self, parent_layout):
        """إعداد شريط البحث العلوي"""
        search_frame = QFrame()
        search_frame.setFrameStyle(QFrame.Shape.Box)
        search_frame.setStyleSheet("""
            QFrame {
                background-color: #f8faff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        search_layout = QHBoxLayout(search_frame)
        
        # أيقونة البحث
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 18px;")
        search_layout.addWidget(search_icon)
        
        # مربع البحث الرئيسي
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ابحث في جميع أقسام النظام... (العملاء، المشاريع، الفواتير، إلخ)")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #4a90e2;
            }
        """)
        search_layout.addWidget(self.search_input)
        
        # زر البحث
        self.search_button = QPushButton("بحث")
        self.search_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2968a3;
            }
        """)
        search_layout.addWidget(self.search_button)
        
        # زر البحث المتقدم
        self.advanced_button = QPushButton("متقدم")
        self.advanced_button.setCheckable(True)
        self.advanced_button.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0d9668;
            }
            QPushButton:checked {
                background-color: #0a7c5a;
            }
        """)
        search_layout.addWidget(self.advanced_button)
        
        parent_layout.addWidget(search_frame)
    
    def setup_filters_panel(self, parent_splitter):
        """إعداد لوحة الفلاتر"""
        filters_widget = QWidget()
        filters_layout = QVBoxLayout(filters_widget)
        
        # عنوان الفلاتر
        filters_title = QLabel("🎛️ فلاتر البحث")
        filters_title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #1a237e;
                padding: 10px;
                background-color: #f0f4ff;
                border-radius: 6px;
                margin-bottom: 10px;
            }
        """)
        filters_layout.addWidget(filters_title)
        
        # منطقة التمرير للفلاتر
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        filters_content = QWidget()
        filters_content_layout = QVBoxLayout(filters_content)
        
        # نطاق البحث
        self.setup_scope_filter(filters_content_layout)
        
        # نوع البحث
        self.setup_search_type_filter(filters_content_layout)
        
        # فلاتر التاريخ
        self.setup_date_filters(filters_content_layout)
        
        # فلاتر المبلغ
        self.setup_amount_filters(filters_content_layout)
        
        # فلاتر الحالة
        self.setup_status_filters(filters_content_layout)
        
        # فلاتر العميل والمشروع
        self.setup_entity_filters(filters_content_layout)
        
        # أزرار الفلاتر
        self.setup_filter_buttons(filters_content_layout)
        
        filters_content_layout.addStretch()
        
        scroll_area.setWidget(filters_content)
        filters_layout.addWidget(scroll_area)
        
        parent_splitter.addWidget(filters_widget)
    
    def setup_scope_filter(self, parent_layout):
        """إعداد فلتر نطاق البحث"""
        group = QGroupBox("📂 نطاق البحث")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(group)
        
        self.scope_combo = QComboBox()
        self.scope_combo.addItems([
            "🌐 جميع الأقسام",
            "👥 العملاء فقط", 
            "📁 المشاريع فقط",
            "🧾 الفواتير فقط",
            "📋 عروض الأسعار فقط",
            "💸 المصروفات فقط",
            "💳 المدفوعات فقط",
            "🛠️ الخدمات فقط",
            "📊 المحاسبة فقط"
        ])
        self.scope_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
            }
        """)
        layout.addWidget(self.scope_combo)
        
        parent_layout.addWidget(group)
    
    def setup_search_type_filter(self, parent_layout):
        """إعداد فلتر نوع البحث"""
        group = QGroupBox("🔍 نوع البحث")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        
        layout = QVBoxLayout(group)
        
        self.search_type_group = QButtonGroup()
        
        # البحث الجزئي (افتراضي)
        self.partial_radio = QRadioButton("🔤 بحث جزئي (افتراضي)")
        self.partial_radio.setChecked(True)
        self.search_type_group.addButton(self.partial_radio, 0)
        layout.addWidget(self.partial_radio)
        
        # البحث الدقيق
        self.exact_radio = QRadioButton("🎯 بحث دقيق")
        self.search_type_group.addButton(self.exact_radio, 1)
        layout.addWidget(self.exact_radio)
        
        # البحث الضبابي
        self.fuzzy_radio = QRadioButton("🌫️ بحث ضبابي")
        self.search_type_group.addButton(self.fuzzy_radio, 2)
        layout.addWidget(self.fuzzy_radio)
        
        parent_layout.addWidget(group)
    
    def setup_date_filters(self, parent_layout):
        """إعداد فلاتر التاريخ"""
        group = QGroupBox("📅 فلتر التاريخ")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        
        layout = QGridLayout(group)
        
        # تفعيل فلتر التاريخ
        self.date_filter_enabled = QCheckBox("تفعيل فلتر التاريخ")
        layout.addWidget(self.date_filter_enabled, 0, 0, 1, 2)
        
        # من تاريخ
        layout.addWidget(QLabel("من:"), 1, 0)
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        self.date_from.setEnabled(False)
        layout.addWidget(self.date_from, 1, 1)
        
        # إلى تاريخ
        layout.addWidget(QLabel("إلى:"), 2, 0)
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setEnabled(False)
        layout.addWidget(self.date_to, 2, 1)
        
        # ربط تفعيل الفلتر
        self.date_filter_enabled.toggled.connect(self.date_from.setEnabled)
        self.date_filter_enabled.toggled.connect(self.date_to.setEnabled)
        
        parent_layout.addWidget(group)
    
    def setup_amount_filters(self, parent_layout):
        """إعداد فلاتر المبلغ"""
        group = QGroupBox("💰 فلتر المبلغ")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        
        layout = QGridLayout(group)
        
        # تفعيل فلتر المبلغ
        self.amount_filter_enabled = QCheckBox("تفعيل فلتر المبلغ")
        layout.addWidget(self.amount_filter_enabled, 0, 0, 1, 2)
        
        # الحد الأدنى
        layout.addWidget(QLabel("من:"), 1, 0)
        self.amount_min = QDoubleSpinBox()
        self.amount_min.setRange(0, 999999999)
        self.amount_min.setSuffix(" ج.م")
        self.amount_min.setEnabled(False)
        layout.addWidget(self.amount_min, 1, 1)
        
        # الحد الأقصى
        layout.addWidget(QLabel("إلى:"), 2, 0)
        self.amount_max = QDoubleSpinBox()
        self.amount_max.setRange(0, 999999999)
        self.amount_max.setValue(100000)
        self.amount_max.setSuffix(" ج.م")
        self.amount_max.setEnabled(False)
        layout.addWidget(self.amount_max, 2, 1)
        
        # ربط تفعيل الفلتر
        self.amount_filter_enabled.toggled.connect(self.amount_min.setEnabled)
        self.amount_filter_enabled.toggled.connect(self.amount_max.setEnabled)
        
        parent_layout.addWidget(group)
    
    def setup_status_filters(self, parent_layout):
        """إعداد فلاتر الحالة"""
        group = QGroupBox("📊 فلتر الحالة")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        
        layout = QVBoxLayout(group)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems([
            "جميع الحالات",
            "نشط",
            "مكتمل", 
            "معلق",
            "ملغي",
            "مؤرشف"
        ])
        layout.addWidget(self.status_combo)
        
        parent_layout.addWidget(group)
    
    def setup_entity_filters(self, parent_layout):
        """إعداد فلاتر العميل والمشروع"""
        group = QGroupBox("🏷️ فلاتر إضافية")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        
        layout = QVBoxLayout(group)
        
        # فلتر العميل
        layout.addWidget(QLabel("العميل:"))
        self.client_combo = QComboBox()
        self.client_combo.addItem("جميع العملاء")
        self.load_clients_for_filter()
        layout.addWidget(self.client_combo)
        
        # فلتر المشروع
        layout.addWidget(QLabel("المشروع:"))
        self.project_combo = QComboBox()
        self.project_combo.addItem("جميع المشاريع")
        self.load_projects_for_filter()
        layout.addWidget(self.project_combo)
        
        parent_layout.addWidget(group)
    
    def setup_filter_buttons(self, parent_layout):
        """إعداد أزرار الفلاتر"""
        buttons_layout = QHBoxLayout()
        
        # زر تطبيق الفلاتر
        apply_button = QPushButton("تطبيق")
        apply_button.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0d9668;
            }
        """)
        apply_button.clicked.connect(self.apply_filters)
        buttons_layout.addWidget(apply_button)
        
        # زر إعادة تعيين
        reset_button = QPushButton("إعادة تعيين")
        reset_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        reset_button.clicked.connect(self.reset_filters)
        buttons_layout.addWidget(reset_button)
        
        parent_layout.addLayout(buttons_layout)
    
    def setup_results_panel(self, parent_splitter):
        """إعداد لوحة النتائج"""
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        
        # شريط معلومات النتائج
        results_info_layout = QHBoxLayout()
        
        self.results_count_label = QLabel("0 نتيجة")
        self.results_count_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #1a237e;
                padding: 5px;
            }
        """)
        results_info_layout.addWidget(self.results_count_label)
        
        results_info_layout.addStretch()
        
        # شريط التقدم
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4a90e2;
                border-radius: 3px;
            }
        """)
        results_info_layout.addWidget(self.progress_bar)
        
        # أزرار التصدير والطباعة
        export_button = QPushButton("تصدير")
        export_button.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        export_button.clicked.connect(self.export_results)
        results_info_layout.addWidget(export_button)
        
        results_layout.addLayout(results_info_layout)
        
        # منطقة عرض النتائج
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.results_scroll.setWidget(self.results_container)
        results_layout.addWidget(self.results_scroll)
        
        # رسالة عدم وجود نتائج
        self.no_results_label = QLabel("🔍 ابدأ البحث للعثور على النتائج")
        self.no_results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_results_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #999;
                padding: 50px;
                background-color: #f9f9f9;
                border-radius: 8px;
                margin: 20px;
            }
        """)
        results_layout.addWidget(self.no_results_label)
        
        parent_splitter.addWidget(results_widget)
    
    def setup_status_bar(self, parent_layout):
        """إعداد شريط الحالة"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.Box)
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #f8faff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 5px;
            }
        """)
        
        status_layout = QHBoxLayout(status_frame)
        
        self.status_label = QLabel("جاهز للبحث")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # إحصائيات سريعة
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #4a90e2; font-size: 12px; font-weight: bold;")
        status_layout.addWidget(self.stats_label)
        
        parent_layout.addWidget(status_frame)
    
    def apply_styles(self):
        """تطبيق الأنماط العامة"""
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
            }
            QGroupBox {
                font-size: 12px;
            }
            QLabel {
                font-size: 12px;
            }
            QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 4px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {
                border-color: #4a90e2;
            }
        """)
    
    def setup_connections(self):
        """إعداد الاتصالات والإشارات"""
        # البحث عند الضغط على Enter أو زر البحث
        self.search_input.returnPressed.connect(self.perform_search)
        self.search_button.clicked.connect(self.perform_search)
        
        # البحث التلقائي أثناء الكتابة (مع تأخير)
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        
        # تبديل عرض الفلاتر المتقدمة
        self.advanced_button.toggled.connect(self.toggle_advanced_filters)
    
    def on_search_text_changed(self):
        """معالج تغيير نص البحث"""
        # إعادة تشغيل المؤقت للبحث التلقائي
        self.search_timer.stop()
        if len(self.search_input.text().strip()) >= 2:
            self.search_timer.start(500)  # البحث بعد 500ms من التوقف عن الكتابة
    
    def toggle_advanced_filters(self, checked):
        """تبديل عرض الفلاتر المتقدمة"""
        # يمكن إضافة منطق لإخفاء/إظهار الفلاتر المتقدمة
        if checked:
            self.status_label.setText("الفلاتر المتقدمة مفعلة")
        else:
            self.status_label.setText("الفلاتر المتقدمة معطلة")
    
    def get_search_scope(self) -> SearchScope:
        """الحصول على نطاق البحث المحدد"""
        scope_map = {
            0: SearchScope.ALL,
            1: SearchScope.CLIENTS,
            2: SearchScope.PROJECTS,
            3: SearchScope.INVOICES,
            4: SearchScope.QUOTATIONS,
            5: SearchScope.EXPENSES,
            6: SearchScope.PAYMENTS,
            7: SearchScope.SERVICES,
            8: SearchScope.ACCOUNTING
        }
        return scope_map.get(self.scope_combo.currentIndex(), SearchScope.ALL)
    
    def get_search_type(self) -> SearchType:
        """الحصول على نوع البحث المحدد"""
        if self.exact_radio.isChecked():
            return SearchType.EXACT
        elif self.fuzzy_radio.isChecked():
            return SearchType.FUZZY
        else:
            return SearchType.PARTIAL
    
    def get_search_filters(self) -> Optional[SearchFilter]:
        """الحصول على فلاتر البحث"""
        filters = SearchFilter()
        
        # فلتر التاريخ
        if self.date_filter_enabled.isChecked():
            filters.date_from = self.date_from.date().toPython()
            filters.date_to = self.date_to.date().toPython()
        
        # فلتر المبلغ
        if self.amount_filter_enabled.isChecked():
            filters.amount_min = self.amount_min.value()
            filters.amount_max = self.amount_max.value()
        
        # فلتر الحالة
        if self.status_combo.currentIndex() > 0:
            filters.status = self.status_combo.currentText()
        
        # فلتر العميل
        if self.client_combo.currentIndex() > 0:
            filters.client_id = self.client_combo.currentData()
        
        # فلتر المشروع
        if self.project_combo.currentIndex() > 0:
            filters.project_id = self.project_combo.currentData()
        
        return filters
    
    def perform_search(self):
        """تنفيذ البحث"""
        query = self.search_input.text().strip()
        
        if not query:
            self.clear_results()
            self.status_label.setText("أدخل نص البحث")
            return
        
        if len(query) < 2:
            self.status_label.setText("أدخل على الأقل حرفين للبحث")
            return
        
        # إظهار شريط التقدم
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"جاري البحث عن: {query}")
        
        # تعطيل زر البحث مؤقتاً
        self.search_button.setEnabled(False)
        self.search_button.setText("جاري البحث...")
        
        # إنشاء خيط البحث
        scope = self.get_search_scope()
        search_type = self.get_search_type()
        filters = self.get_search_filters()
        
        self.search_thread = SearchThread(
            self.search_service, query, scope, search_type, filters, 100
        )
        
        # ربط الإشارات
        self.search_thread.results_ready.connect(self.display_results)
        self.search_thread.progress_update.connect(self.progress_bar.setValue)
        self.search_thread.error_occurred.connect(self.handle_search_error)
        self.search_thread.finished.connect(self.search_finished)
        
        # بدء البحث
        self.search_thread.start()
    
    def display_results(self, results: List[SearchResult]):
        """عرض نتائج البحث"""
        self.current_results = results
        
        # مسح النتائج السابقة
        self.clear_results_widgets()
        
        if not results:
            self.no_results_label.setText("🚫 لم يتم العثور على نتائج")
            self.no_results_label.setVisible(True)
            self.results_count_label.setText("0 نتيجة")
            return
        
        # إخفاء رسالة عدم وجود نتائج
        self.no_results_label.setVisible(False)
        
        # عرض النتائج
        for result in results:
            result_widget = SearchResultWidget(result)
            result_widget.clicked.connect(self.result_selected.emit)
            self.results_layout.addWidget(result_widget)
        
        # تحديث عداد النتائج
        self.results_count_label.setText(f"{len(results)} نتيجة")
        
        # تحديث شريط الحالة
        self.status_label.setText(f"تم العثور على {len(results)} نتيجة")
    
    def clear_results_widgets(self):
        """مسح ويدجت النتائج"""
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def clear_results(self):
        """مسح جميع النتائج"""
        self.clear_results_widgets()
        self.no_results_label.setText("🔍 ابدأ البحث للعثور على النتائج")
        self.no_results_label.setVisible(True)
        self.results_count_label.setText("0 نتيجة")
        self.current_results = []
    
    def handle_search_error(self, error_message: str):
        """معالجة أخطاء البحث"""
        self.status_label.setText(f"خطأ في البحث: {error_message}")
        QMessageBox.warning(self, "خطأ في البحث", f"حدث خطأ أثناء البحث:\n{error_message}")
    
    def search_finished(self):
        """معالج انتهاء البحث"""
        # إخفاء شريط التقدم
        self.progress_bar.setVisible(False)
        
        # إعادة تفعيل زر البحث
        self.search_button.setEnabled(True)
        self.search_button.setText("بحث")
    
    def apply_filters(self):
        """تطبيق الفلاتر وإعادة البحث"""
        if self.search_input.text().strip():
            self.perform_search()
    
    def reset_filters(self):
        """إعادة تعيين جميع الفلاتر"""
        self.scope_combo.setCurrentIndex(0)
        self.partial_radio.setChecked(True)
        self.date_filter_enabled.setChecked(False)
        self.amount_filter_enabled.setChecked(False)
        self.status_combo.setCurrentIndex(0)
        self.client_combo.setCurrentIndex(0)
        self.project_combo.setCurrentIndex(0)
        
        self.status_label.setText("تم إعادة تعيين الفلاتر")
    
    def load_clients_for_filter(self):
        """تحميل العملاء لفلتر العميل"""
        try:
            clients = self.repository.get_all_clients()
            for client in clients[:50]:  # أول 50 عميل فقط
                self.client_combo.addItem(client.name, str(client.id))
        except Exception as e:
            print(f"ERROR: Failed to load clients for filter: {e}")
    
    def load_projects_for_filter(self):
        """تحميل المشاريع لفلتر المشروع"""
        try:
            projects = self.repository.get_all_projects()
            for project in projects[:50]:  # أول 50 مشروع فقط
                self.project_combo.addItem(project.name, str(project.id))
        except Exception as e:
            print(f"ERROR: Failed to load projects for filter: {e}")
    
    def load_search_statistics(self):
        """تحميل إحصائيات البحث"""
        try:
            stats = self.search_service.get_search_statistics()
            stats_text = f"العملاء: {stats.get('total_clients', 0)} | "
            stats_text += f"المشاريع: {stats.get('total_projects', 0)} | "
            stats_text += f"الفواتير: {stats.get('total_invoices', 0)}"
            self.stats_label.setText(stats_text)
        except Exception as e:
            print(f"ERROR: Failed to load search statistics: {e}")
    
    def export_results(self):
        """تصدير النتائج"""
        if not self.current_results:
            QMessageBox.information(self, "تصدير النتائج", "لا توجد نتائج للتصدير")
            return
        
        try:
            # يمكن إضافة منطق التصدير هنا (Excel, PDF, إلخ)
            QMessageBox.information(
                self, 
                "تصدير النتائج", 
                f"سيتم تصدير {len(self.current_results)} نتيجة\n(هذه الميزة قيد التطوير)"
            )
        except Exception as e:
            QMessageBox.warning(self, "خطأ في التصدير", f"فشل في تصدير النتائج:\n{str(e)}")


# دالة لاختبار الواجهة
def test_search_widget():
    """اختبار واجهة البحث"""
    app = QApplication(sys.argv)
    
    # إنشاء repository وهمي للاختبار
    # في التطبيق الحقيقي، استخدم repository حقيقي
    from core.repository import Repository
    
    try:
        # repository = Repository()  # استخدم repository حقيقي
        # widget = AdvancedSearchWidget(repository)
        # widget.show()
        
        print("⚠️ لاختبار واجهة البحث، يرجى توفير repository صحيح")
        print("مثال:")
        print("repository = Repository()")
        print("widget = AdvancedSearchWidget(repository)")
        print("widget.show()")
        
    except Exception as e:
        print(f"ERROR: {e}")
    
    # app.exec()


if __name__ == "__main__":
    test_search_widget()