# الملف: ui/quotation_manager.py
"""
📋 تاب إدارة عروض الأسعار - Production Grade
=============================================
نظام متكامل لإدارة عروض الأسعار:
- إنشاء عروض احترافية
- تتبع حالة العروض
- تحويل العروض لمشاريع
- تصدير PDF
"""

from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QLineEdit, QComboBox,
    QDateEdit, QDoubleSpinBox, QTextEdit, QMessageBox,
    QHeaderView, QGroupBox, QFormLayout, QDialog, QSpinBox,
    QFrame, QGridLayout, QAbstractItemView, QSplitter, QTabWidget
)
from PyQt6.QtGui import QColor

from services.quotation_service import QuotationService
from ui.styles import BUTTON_STYLES

try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class QuotationManagerTab(QWidget):
    """تاب إدارة عروض الأسعار"""

    STATUS_COLORS = {
        "مسودة": "#6b7280",
        "مرسل": "#3b82f6",
        "تم الاطلاع": "#8b5cf6",
        "مقبول": "#22c55e",
        "مرفوض": "#ef4444",
        "منتهي": "#f59e0b",
        "تم التحويل لمشروع": "#06b6d4"
    }

    def __init__(self, quotation_service: QuotationService, client_service=None, 
                 service_service=None, project_service=None):
        super().__init__()
        self.quotation_service = quotation_service
        self.client_service = client_service
        self.service_service = service_service
        self.project_service = project_service
        self.init_ui()
        self.load_data()

    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # عنوان
        title = QLabel("📋 إدارة عروض الأسعار")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a90e2; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # إحصائيات سريعة
        self.stats_frame = self._create_stats_frame()
        layout.addWidget(self.stats_frame)

        # شريط الأدوات
        toolbar = self._create_toolbar()
        layout.addLayout(toolbar)

        # جدول العروض
        self.quotations_table = self._create_table()
        layout.addWidget(self.quotations_table)

        # تطبيق الستايل
        self._apply_styles()

    def _create_stats_frame(self) -> QFrame:
        """إنشاء إطار الإحصائيات"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame { background-color: #002040; border-radius: 10px; padding: 10px; }
        """)
        layout = QHBoxLayout()
        frame.setLayout(layout)

        self.stat_total = self._create_stat_card("📋 إجمالي العروض", "0")
        self.stat_pending = self._create_stat_card("⏳ معلقة", "0")
        self.stat_accepted = self._create_stat_card("✅ مقبولة", "0")
        self.stat_rate = self._create_stat_card("📊 معدل القبول", "0%")

        layout.addWidget(self.stat_total)
        layout.addWidget(self.stat_pending)
        layout.addWidget(self.stat_accepted)
        layout.addWidget(self.stat_rate)

        return frame

    def _create_stat_card(self, title: str, value: str) -> QFrame:
        """إنشاء بطاقة إحصائية"""
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: #003366; border-radius: 8px; padding: 10px; }")
        layout = QVBoxLayout()
        card.setLayout(layout)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #888; font-size: 12px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet("color: #4a90e2; font-size: 20px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        return card

    def _create_toolbar(self) -> QHBoxLayout:
        """إنشاء شريط الأدوات"""
        toolbar = QHBoxLayout()

        # البحث
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 بحث عن عرض...")
        self.search_input.textChanged.connect(self._filter_quotations)
        toolbar.addWidget(self.search_input)

        # فلتر الحالة
        self.status_filter = QComboBox()
        self.status_filter.addItems(["الكل", "مسودة", "مرسل", "تم الاطلاع", "مقبول", "مرفوض", "منتهي"])
        self.status_filter.currentTextChanged.connect(self._filter_by_status)
        toolbar.addWidget(self.status_filter)

        toolbar.addStretch()

        # أزرار
        add_btn = QPushButton("➕ عرض جديد")
        add_btn.setStyleSheet(BUTTON_STYLES["success"])
        add_btn.clicked.connect(self._add_quotation)
        toolbar.addWidget(add_btn)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setStyleSheet(BUTTON_STYLES["info"])
        refresh_btn.clicked.connect(self.load_data)
        toolbar.addWidget(refresh_btn)

        return toolbar

    def _create_table(self) -> QTableWidget:
        """إنشاء جدول العروض"""
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            "رقم العرض", "العميل", "العنوان", "المبلغ", "الحالة",
            "صالح حتى", "تعديل", "إجراءات", "حذف"
        ])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.doubleClicked.connect(self._on_row_double_clicked)
        return table


    def _apply_styles(self):
        """تطبيق الستايلات"""
        self.setStyleSheet("""
            QWidget { background-color: #001a3a; color: #ffffff; }
            QTableWidget {
                background-color: #002040;
                alternate-background-color: #002855;
                gridline-color: #003366;
                border: 1px solid #003366;
                border-radius: 8px;
            }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background-color: #4a90e2; }
            QHeaderView::section {
                background-color: #003366;
                color: #ffffff;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            QLineEdit, QComboBox {
                background-color: #002040;
                color: #ffffff;
                border: 2px solid #003366;
                border-radius: 6px;
                padding: 8px;
            }
            QLineEdit:focus, QComboBox:focus { border: 2px solid #4a90e2; }
        """)

    # ==================== تحميل البيانات ====================
    def load_data(self):
        """تحميل البيانات"""
        self._load_statistics()
        self._load_quotations()

    def _load_statistics(self):
        """تحميل الإحصائيات"""
        try:
            stats = self.quotation_service.get_statistics()
            
            self.stat_total.findChild(QLabel, "value").setText(str(stats.get("total", 0)))
            
            pending = stats.get("by_status", {}).get("مسودة", {}).get("count", 0)
            pending += stats.get("by_status", {}).get("مرسل", {}).get("count", 0)
            self.stat_pending.findChild(QLabel, "value").setText(str(pending))
            
            accepted = stats.get("by_status", {}).get("مقبول", {}).get("count", 0)
            self.stat_accepted.findChild(QLabel, "value").setText(str(accepted))
            
            rate = stats.get("acceptance_rate", 0)
            self.stat_rate.findChild(QLabel, "value").setText(f"{rate:.1f}%")
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل الإحصائيات: {e}")

    def _load_quotations(self):
        """تحميل العروض"""
        try:
            status_filter = self.status_filter.currentText()
            if status_filter == "الكل":
                quotations = self.quotation_service.get_all_quotations()
            else:
                quotations = self.quotation_service.get_quotations_by_status(status_filter)
            
            self.quotations_table.setRowCount(len(quotations))
            
            for row, q in enumerate(quotations):
                # رقم العرض
                self.quotations_table.setItem(row, 0, QTableWidgetItem(q.get("quotation_number", "")))
                
                # العميل
                client_name = q.get("client_display_name") or q.get("client_name") or ""
                company = q.get("company_name", "")
                display_name = f"{client_name} ({company})" if company else client_name
                self.quotations_table.setItem(row, 1, QTableWidgetItem(display_name))
                
                # العنوان
                self.quotations_table.setItem(row, 2, QTableWidgetItem(q.get("title", "")))
                
                # المبلغ
                amount = q.get("total_amount", 0)
                currency = q.get("currency", "EGP")
                self.quotations_table.setItem(row, 3, QTableWidgetItem(f"{amount:,.0f} {currency}"))
                
                # الحالة
                status = q.get("status", "")
                status_item = QTableWidgetItem(status)
                color = self.STATUS_COLORS.get(status, "#ffffff")
                status_item.setForeground(QColor(color))
                self.quotations_table.setItem(row, 4, status_item)
                
                # صالح حتى
                valid_until = q.get("valid_until", "")[:10] if q.get("valid_until") else ""
                valid_item = QTableWidgetItem(valid_until)
                # تلوين إذا منتهي أو قريب من الانتهاء
                if valid_until:
                    try:
                        valid_date = datetime.strptime(valid_until, "%Y-%m-%d")
                        if valid_date < datetime.now():
                            valid_item.setForeground(QColor("#ef4444"))
                        elif valid_date < datetime.now() + timedelta(days=7):
                            valid_item.setForeground(QColor("#f59e0b"))
                    except ValueError:
                        pass
                self.quotations_table.setItem(row, 5, valid_item)
                
                # زر التعديل
                edit_btn = QPushButton("✏️")
                edit_btn.setStyleSheet(BUTTON_STYLES["info"])
                edit_btn.clicked.connect(lambda checked, qt=q: self._edit_quotation(qt))
                self.quotations_table.setCellWidget(row, 6, edit_btn)
                
                # زر الإجراءات
                action_btn = QPushButton("⚡")
                action_btn.setStyleSheet(BUTTON_STYLES["warning"])
                action_btn.clicked.connect(lambda checked, qt=q: self._show_actions_menu(qt))
                self.quotations_table.setCellWidget(row, 7, action_btn)
                
                # زر الحذف
                del_btn = QPushButton("🗑️")
                del_btn.setStyleSheet(BUTTON_STYLES["danger"])
                del_btn.clicked.connect(lambda checked, qt=q: self._delete_quotation(qt))
                self.quotations_table.setCellWidget(row, 8, del_btn)
                
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل العروض: {e}")

    # ==================== الفلاتر ====================
    def _filter_quotations(self, text: str):
        """فلترة العروض بالبحث"""
        for row in range(self.quotations_table.rowCount()):
            match = False
            for col in range(6):
                item = self.quotations_table.item(row, col)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.quotations_table.setRowHidden(row, not match)

    def _filter_by_status(self, status: str):
        """فلترة حسب الحالة"""
        self._load_quotations()

    def _on_row_double_clicked(self, index):
        """عند النقر المزدوج على صف"""
        row = index.row()
        quotation_number = self.quotations_table.item(row, 0).text()
        quotations = self.quotation_service.get_all_quotations()
        quotation = next((q for q in quotations if q.get("quotation_number") == quotation_number), None)
        if quotation:
            self._view_quotation(quotation)


    # ==================== إجراءات العروض ====================
    def _add_quotation(self):
        """إضافة عرض جديد"""
        clients = []
        services = []
        if self.client_service:
            clients = self.client_service.get_all_clients()
        if self.service_service:
            services = self.service_service.get_all_services()
        
        dialog = QuotationEditorDialog(
            clients=clients,
            services=services,
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            result = self.quotation_service.create_quotation(data)
            if result:
                QMessageBox.information(self, "نجاح", f"تم إنشاء العرض: {result.get('quotation_number')}")
                self.load_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل إنشاء العرض")

    def _edit_quotation(self, quotation: dict):
        """تعديل عرض"""
        clients = []
        services = []
        if self.client_service:
            clients = self.client_service.get_all_clients()
        if self.service_service:
            services = self.service_service.get_all_services()
        
        dialog = QuotationEditorDialog(
            quotation_data=quotation,
            clients=clients,
            services=services,
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            result = self.quotation_service.update_quotation(quotation["id"], data)
            if result:
                QMessageBox.information(self, "نجاح", "تم تحديث العرض")
                self.load_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل تحديث العرض")

    def _view_quotation(self, quotation: dict):
        """عرض تفاصيل العرض"""
        dialog = QuotationViewDialog(quotation, parent=self)
        dialog.exec()

    def _delete_quotation(self, quotation: dict):
        """حذف عرض"""
        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل أنت متأكد من حذف العرض: {quotation.get('quotation_number')}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.quotation_service.delete_quotation(quotation["id"]):
                QMessageBox.information(self, "نجاح", "تم حذف العرض")
                self.load_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل حذف العرض")

    def _show_actions_menu(self, quotation: dict):
        """عرض قائمة الإجراءات"""
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #002040; color: #ffffff; border: 1px solid #003366; }
            QMenu::item { padding: 8px 20px; }
            QMenu::item:selected { background-color: #4a90e2; }
        """)
        
        status = quotation.get("status", "")
        
        # إجراءات حسب الحالة
        if status == "مسودة":
            menu.addAction("📤 إرسال للعميل", lambda: self._send_quotation(quotation))
            menu.addAction("📋 نسخ العرض", lambda: self._duplicate_quotation(quotation))
        
        if status in ["مسودة", "مرسل", "تم الاطلاع"]:
            menu.addAction("✅ قبول", lambda: self._accept_quotation(quotation))
            menu.addAction("❌ رفض", lambda: self._reject_quotation(quotation))
        
        if status == "مقبول":
            menu.addAction("🚀 تحويل لمشروع", lambda: self._convert_to_project(quotation))
        
        menu.addSeparator()
        menu.addAction("📄 تصدير PDF", lambda: self._export_pdf(quotation))
        menu.addAction("👁️ معاينة", lambda: self._view_quotation(quotation))
        
        menu.exec(self.cursor().pos())

    def _send_quotation(self, quotation: dict):
        """إرسال العرض"""
        if self.quotation_service.mark_as_sent(quotation["id"]):
            QMessageBox.information(self, "نجاح", "تم تحديد العرض كمرسل")
            self.load_data()

    def _accept_quotation(self, quotation: dict):
        """قبول العرض"""
        if self.quotation_service.accept_quotation(quotation["id"]):
            QMessageBox.information(self, "نجاح", "تم قبول العرض")
            self.load_data()

    def _reject_quotation(self, quotation: dict):
        """رفض العرض"""
        if self.quotation_service.reject_quotation(quotation["id"]):
            QMessageBox.information(self, "نجاح", "تم رفض العرض")
            self.load_data()

    def _duplicate_quotation(self, quotation: dict):
        """نسخ العرض"""
        result = self.quotation_service.duplicate_quotation(quotation["id"])
        if result:
            QMessageBox.information(self, "نجاح", f"تم نسخ العرض: {result.get('quotation_number')}")
            self.load_data()

    def _convert_to_project(self, quotation: dict):
        """تحويل العرض لمشروع"""
        if not self.project_service:
            QMessageBox.warning(self, "خطأ", "خدمة المشاريع غير متاحة")
            return
        
        reply = QMessageBox.question(
            self, "تأكيد",
            f"هل تريد تحويل العرض '{quotation.get('title')}' إلى مشروع؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            result = self.quotation_service.convert_to_project(quotation["id"], self.project_service)
            if result:
                QMessageBox.information(self, "نجاح", "تم تحويل العرض إلى مشروع بنجاح")
                self.load_data()
            else:
                QMessageBox.warning(self, "خطأ", "فشل تحويل العرض")

    def _export_pdf(self, quotation: dict):
        """تصدير العرض كـ PDF"""
        try:
            from services.export_service import ExportService
            from PyQt6.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "حفظ PDF",
                f"عرض_سعر_{quotation.get('quotation_number', '')}.pdf",
                "PDF Files (*.pdf)"
            )
            if file_path:
                # TODO: تنفيذ تصدير PDF
                QMessageBox.information(self, "معلومات", "سيتم إضافة تصدير PDF قريباً")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل التصدير: {e}")


# ==================== نوافذ مساعدة ====================

class QuotationEditorDialog(QDialog):
    """نافذة إنشاء/تعديل عرض سعر"""
    
    def __init__(self, quotation_data=None, clients=None, services=None, parent=None):
        super().__init__(parent)
        self.quotation_data = quotation_data
        self.clients = clients or []
        self.services = services or []
        self.items = []
        
        self.setWindowTitle("✏️ تعديل عرض" if quotation_data else "➕ عرض سعر جديد")
        self.setModal(True)
        self.setMinimumSize(900, 700)
        
        self.init_ui()
        if quotation_data:
            self.load_data()
        
        self._apply_style()

    def init_ui(self):
        """إنشاء الواجهة"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # تابات
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # تاب المعلومات الأساسية
        basic_tab = self._create_basic_tab()
        tabs.addTab(basic_tab, "📋 أساسية")

        # تاب البنود
        items_tab = self._create_items_tab()
        tabs.addTab(items_tab, "📦 البنود")

        # تاب الشروط
        terms_tab = self._create_terms_tab()
        tabs.addTab(terms_tab, "📜 الشروط")

        # ملخص
        summary_frame = self._create_summary_frame()
        layout.addWidget(summary_frame)

        # أزرار
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 حفظ")
        save_btn.setStyleSheet(BUTTON_STYLES["success"])
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["danger"])
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _create_basic_tab(self) -> QWidget:
        """تاب المعلومات الأساسية"""
        widget = QWidget()
        layout = QFormLayout()
        widget.setLayout(layout)

        # العميل
        self.client_combo = QComboBox()
        self.client_combo.addItem("-- اختر العميل --", "")
        for client in self.clients:
            # دعم dict و object
            if hasattr(client, 'get'):
                name = client.get("name", "")
                company = client.get("company_name", "")
                client_id = client.get("_mongo_id") or client.get("id")
            else:
                name = getattr(client, "name", "")
                company = getattr(client, "company_name", "")
                client_id = getattr(client, "_mongo_id", None) or getattr(client, "id", None)
            display = f"{name} ({company})" if company else name
            self.client_combo.addItem(display, str(client_id))
        layout.addRow("العميل *:", self.client_combo)

        # العنوان
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("عنوان العرض (مثل: تصميم موقع إلكتروني)")
        layout.addRow("العنوان *:", self.title_input)

        # الوصف
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("وصف مختصر للعرض...")
        self.description_input.setMaximumHeight(80)
        layout.addRow("الوصف:", self.description_input)

        # نطاق العمل
        self.scope_input = QTextEdit()
        self.scope_input.setPlaceholderText("تفاصيل نطاق العمل والمخرجات المتوقعة...")
        self.scope_input.setMaximumHeight(100)
        layout.addRow("نطاق العمل:", self.scope_input)

        # التواريخ
        dates_layout = QHBoxLayout()
        
        self.issue_date = QDateEdit()
        self.issue_date.setDate(QDate.currentDate())
        self.issue_date.setCalendarPopup(True)
        dates_layout.addWidget(QLabel("تاريخ الإصدار:"))
        dates_layout.addWidget(self.issue_date)
        
        self.valid_until = QDateEdit()
        self.valid_until.setDate(QDate.currentDate().addDays(30))
        self.valid_until.setCalendarPopup(True)
        dates_layout.addWidget(QLabel("صالح حتى:"))
        dates_layout.addWidget(self.valid_until)
        
        layout.addRow("", dates_layout)

        # مدة التسليم
        self.delivery_input = QLineEdit()
        self.delivery_input.setPlaceholderText("مثل: 2-3 أسابيع")
        layout.addRow("مدة التسليم:", self.delivery_input)

        return widget

    def _create_items_tab(self) -> QWidget:
        """تاب البنود"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # شريط أدوات البنود
        toolbar = QHBoxLayout()
        
        add_item_btn = QPushButton("➕ إضافة بند")
        add_item_btn.setStyleSheet(BUTTON_STYLES["success"])
        add_item_btn.clicked.connect(self._add_item)
        toolbar.addWidget(add_item_btn)
        
        add_service_btn = QPushButton("📦 إضافة خدمة")
        add_service_btn.setStyleSheet(BUTTON_STYLES["info"])
        add_service_btn.clicked.connect(self._add_service_item)
        toolbar.addWidget(add_service_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # جدول البنود
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels([
            "الوصف", "الكمية", "السعر", "الخصم", "الإجمالي", "حذف"
        ])
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.items_table)

        return widget

    def _create_terms_tab(self) -> QWidget:
        """تاب الشروط"""
        widget = QWidget()
        layout = QFormLayout()
        widget.setLayout(layout)

        # شروط الدفع
        self.payment_terms = QTextEdit()
        self.payment_terms.setPlaceholderText("شروط الدفع...")
        self.payment_terms.setPlainText("- 50% دفعة مقدمة عند التعاقد\n- 50% عند التسليم النهائي")
        self.payment_terms.setMaximumHeight(100)
        layout.addRow("شروط الدفع:", self.payment_terms)

        # الضمان
        self.warranty_input = QLineEdit()
        self.warranty_input.setPlaceholderText("مثل: ضمان 3 أشهر على الأخطاء البرمجية")
        layout.addRow("الضمان:", self.warranty_input)

        # الشروط والأحكام
        self.terms_input = QTextEdit()
        self.terms_input.setPlaceholderText("الشروط والأحكام العامة...")
        default_terms = """1. هذا العرض صالح لمدة 30 يوماً من تاريخ الإصدار.
2. الأسعار المذكورة لا تشمل ضريبة القيمة المضافة.
3. يتم البدء في العمل بعد استلام الدفعة المقدمة.
4. أي تعديلات على نطاق العمل قد تؤثر على السعر النهائي."""
        self.terms_input.setPlainText(default_terms)
        layout.addRow("الشروط والأحكام:", self.terms_input)

        # ملاحظات
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات إضافية للعميل...")
        self.notes_input.setMaximumHeight(80)
        layout.addRow("ملاحظات:", self.notes_input)

        # ملاحظات داخلية
        self.internal_notes = QTextEdit()
        self.internal_notes.setPlaceholderText("ملاحظات داخلية (لا تظهر للعميل)...")
        self.internal_notes.setMaximumHeight(60)
        layout.addRow("ملاحظات داخلية:", self.internal_notes)

        return widget

    def _create_summary_frame(self) -> QFrame:
        """إنشاء إطار الملخص"""
        frame = QFrame()
        frame.setStyleSheet("background-color: #002040; border-radius: 8px; padding: 10px;")
        layout = QHBoxLayout()
        frame.setLayout(layout)

        # الخصم
        layout.addWidget(QLabel("خصم %:"))
        self.discount_rate = QDoubleSpinBox()
        self.discount_rate.setRange(0, 100)
        self.discount_rate.valueChanged.connect(self._update_totals)
        layout.addWidget(self.discount_rate)

        # الضريبة
        layout.addWidget(QLabel("ضريبة %:"))
        self.tax_rate = QDoubleSpinBox()
        self.tax_rate.setRange(0, 100)
        self.tax_rate.valueChanged.connect(self._update_totals)
        layout.addWidget(self.tax_rate)

        layout.addStretch()

        # الإجماليات
        self.subtotal_label = QLabel("الإجمالي: 0")
        self.subtotal_label.setStyleSheet("color: #888;")
        layout.addWidget(self.subtotal_label)

        self.total_label = QLabel("المجموع: 0 EGP")
        self.total_label.setStyleSheet("color: #4a90e2; font-size: 16px; font-weight: bold;")
        layout.addWidget(self.total_label)

        return frame


    def _add_item(self):
        """إضافة بند جديد"""
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        
        # الوصف
        desc_input = QLineEdit()
        desc_input.setPlaceholderText("وصف البند...")
        self.items_table.setCellWidget(row, 0, desc_input)
        
        # الكمية
        qty_input = QSpinBox()
        qty_input.setRange(1, 9999)
        qty_input.setValue(1)
        qty_input.valueChanged.connect(self._update_totals)
        self.items_table.setCellWidget(row, 1, qty_input)
        
        # السعر
        price_input = QDoubleSpinBox()
        price_input.setRange(0, 9999999)
        price_input.setDecimals(2)
        price_input.valueChanged.connect(self._update_totals)
        self.items_table.setCellWidget(row, 2, price_input)
        
        # الخصم
        discount_input = QDoubleSpinBox()
        discount_input.setRange(0, 9999999)
        discount_input.setDecimals(2)
        discount_input.valueChanged.connect(self._update_totals)
        self.items_table.setCellWidget(row, 3, discount_input)
        
        # الإجمالي
        total_label = QLabel("0")
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.items_table.setCellWidget(row, 4, total_label)
        
        # زر الحذف
        del_btn = QPushButton("🗑️")
        del_btn.setStyleSheet(BUTTON_STYLES["danger"])
        del_btn.clicked.connect(lambda: self._remove_item(row))
        self.items_table.setCellWidget(row, 5, del_btn)

    def _add_service_item(self):
        """إضافة خدمة من القائمة"""
        if not self.services:
            QMessageBox.information(self, "معلومات", "لا توجد خدمات متاحة")
            return
        
        dialog = ServiceSelectDialog(self.services, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            service = dialog.get_selected_service()
            if service:
                self._add_item()
                row = self.items_table.rowCount() - 1
                
                # تعبئة البيانات
                desc_widget = self.items_table.cellWidget(row, 0)
                if desc_widget:
                    # دعم dict و object
                    if hasattr(service, 'get'):
                        desc_widget.setText(service.get("name", ""))
                    else:
                        desc_widget.setText(getattr(service, "name", ""))
                
                price_widget = self.items_table.cellWidget(row, 2)
                if price_widget:
                    # دعم dict و object
                    if hasattr(service, 'get'):
                        price_widget.setValue(service.get("default_price", 0))
                    else:
                        price_widget.setValue(getattr(service, "default_price", 0))
                
                self._update_totals()

    def _remove_item(self, row: int):
        """حذف بند"""
        self.items_table.removeRow(row)
        self._update_totals()

    def _update_totals(self):
        """تحديث الإجماليات"""
        subtotal = 0
        
        for row in range(self.items_table.rowCount()):
            qty_widget = self.items_table.cellWidget(row, 1)
            price_widget = self.items_table.cellWidget(row, 2)
            discount_widget = self.items_table.cellWidget(row, 3)
            total_widget = self.items_table.cellWidget(row, 4)
            
            if qty_widget and price_widget and total_widget:
                qty = qty_widget.value()
                price = price_widget.value()
                discount = discount_widget.value() if discount_widget else 0
                item_total = (qty * price) - discount
                total_widget.setText(f"{item_total:,.0f}")
                subtotal += item_total
        
        # حساب الخصم والضريبة
        discount_rate = self.discount_rate.value()
        discount_amount = subtotal * (discount_rate / 100)
        after_discount = subtotal - discount_amount
        
        tax_rate = self.tax_rate.value()
        tax_amount = after_discount * (tax_rate / 100)
        
        total = after_discount + tax_amount
        
        self.subtotal_label.setText(f"الإجمالي: {subtotal:,.0f}")
        self.total_label.setText(f"المجموع: {total:,.0f} EGP")

    def load_data(self):
        """تحميل بيانات العرض للتعديل"""
        if not self.quotation_data:
            return
        
        q = self.quotation_data
        
        # العميل
        client_id = str(q.get("client_id", ""))
        for i in range(self.client_combo.count()):
            if self.client_combo.itemData(i) == client_id:
                self.client_combo.setCurrentIndex(i)
                break
        
        # المعلومات الأساسية
        self.title_input.setText(q.get("title", ""))
        self.description_input.setPlainText(q.get("description", ""))
        self.scope_input.setPlainText(q.get("scope_of_work", ""))
        self.delivery_input.setText(q.get("delivery_time", ""))
        
        # التواريخ
        if q.get("issue_date"):
            try:
                date = datetime.strptime(q["issue_date"][:10], "%Y-%m-%d")
                self.issue_date.setDate(QDate(date.year, date.month, date.day))
            except ValueError:
                pass
        
        if q.get("valid_until"):
            try:
                date = datetime.strptime(q["valid_until"][:10], "%Y-%m-%d")
                self.valid_until.setDate(QDate(date.year, date.month, date.day))
            except ValueError:
                pass
        
        # البنود
        for item in q.get("items", []):
            self._add_item()
            row = self.items_table.rowCount() - 1
            
            desc_widget = self.items_table.cellWidget(row, 0)
            if desc_widget:
                desc_widget.setText(item.get("description", ""))
            
            qty_widget = self.items_table.cellWidget(row, 1)
            if qty_widget:
                qty_widget.setValue(int(item.get("quantity", 1)))
            
            price_widget = self.items_table.cellWidget(row, 2)
            if price_widget:
                price_widget.setValue(float(item.get("unit_price", 0)))
            
            discount_widget = self.items_table.cellWidget(row, 3)
            if discount_widget:
                discount_widget.setValue(float(item.get("discount_amount", 0)))
        
        # الخصم والضريبة
        self.discount_rate.setValue(q.get("discount_rate", 0))
        self.tax_rate.setValue(q.get("tax_rate", 0))
        
        # الشروط
        self.payment_terms.setPlainText(q.get("payment_terms", ""))
        self.warranty_input.setText(q.get("warranty", ""))
        self.terms_input.setPlainText(q.get("terms_and_conditions", ""))
        self.notes_input.setPlainText(q.get("notes", ""))
        self.internal_notes.setPlainText(q.get("internal_notes", ""))
        
        self._update_totals()

    def get_data(self) -> dict:
        """جلب بيانات العرض"""
        # جمع البنود
        items = []
        for row in range(self.items_table.rowCount()):
            desc_widget = self.items_table.cellWidget(row, 0)
            qty_widget = self.items_table.cellWidget(row, 1)
            price_widget = self.items_table.cellWidget(row, 2)
            discount_widget = self.items_table.cellWidget(row, 3)
            
            if desc_widget and qty_widget and price_widget:
                items.append({
                    "description": desc_widget.text(),
                    "quantity": qty_widget.value(),
                    "unit_price": price_widget.value(),
                    "discount_amount": discount_widget.value() if discount_widget else 0
                })
        
        # جلب اسم العميل
        client_name = ""
        client_id = self.client_combo.currentData()
        if client_id:
            for client in self.clients:
                # دعم dict و object
                if hasattr(client, 'get'):
                    cid = client.get("_mongo_id") or client.get("id")
                    cname = client.get("name", "")
                else:
                    cid = getattr(client, "_mongo_id", None) or getattr(client, "id", None)
                    cname = getattr(client, "name", "")
                if str(cid) == str(client_id):
                    client_name = cname
                    break
        
        return {
            "client_id": client_id,
            "client_name": client_name,
            "title": self.title_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "scope_of_work": self.scope_input.toPlainText().strip(),
            "issue_date": self.issue_date.date().toString("yyyy-MM-dd"),
            "valid_until": self.valid_until.date().toString("yyyy-MM-dd"),
            "delivery_time": self.delivery_input.text().strip(),
            "items": items,
            "discount_rate": self.discount_rate.value(),
            "tax_rate": self.tax_rate.value(),
            "payment_terms": self.payment_terms.toPlainText().strip(),
            "warranty": self.warranty_input.text().strip(),
            "terms_and_conditions": self.terms_input.toPlainText().strip(),
            "notes": self.notes_input.toPlainText().strip(),
            "internal_notes": self.internal_notes.toPlainText().strip(),
            "status": self.quotation_data.get("status", "مسودة") if self.quotation_data else "مسودة"
        }

    def _apply_style(self):
        """تطبيق الستايل"""
        self.setStyleSheet("""
            QDialog { background-color: #001a3a; color: #ffffff; }
            QLabel { color: #ffffff; }
            QLineEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
                background-color: #002040; color: #ffffff;
                border: 2px solid #003366; border-radius: 6px; padding: 6px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 2px solid #4a90e2;
            }
            QTableWidget {
                background-color: #002040;
                gridline-color: #003366;
                border: 1px solid #003366;
            }
            QHeaderView::section {
                background-color: #003366;
                color: #ffffff;
                padding: 6px;
                border: none;
            }
            QTabWidget::pane { border: 1px solid #003366; background-color: #001a3a; }
            QTabBar::tab {
                background-color: #002040; color: #ffffff;
                padding: 8px 16px; margin-right: 2px;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected { background-color: #4a90e2; }
        """)

    def accept(self):
        """التحقق قبل الحفظ"""
        if not self.client_combo.currentData():
            QMessageBox.warning(self, "تحذير", "يرجى اختيار العميل")
            return
        if not self.title_input.text().strip():
            QMessageBox.warning(self, "تحذير", "يرجى إدخال عنوان العرض")
            return
        if self.items_table.rowCount() == 0:
            QMessageBox.warning(self, "تحذير", "يرجى إضافة بند واحد على الأقل")
            return
        super().accept()


class QuotationViewDialog(QDialog):
    """نافذة عرض تفاصيل العرض"""
    
    def __init__(self, quotation: dict, parent=None):
        super().__init__(parent)
        self.quotation = quotation
        self.setWindowTitle(f"عرض سعر: {quotation.get('quotation_number', '')}")
        self.setModal(True)
        self.setMinimumSize(700, 600)
        self.init_ui()
        self._apply_style()

    def init_ui(self):
        """إنشاء الواجهة"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        q = self.quotation

        # الهيدر
        header = QLabel(f"📋 {q.get('title', '')}")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a90e2; padding: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # معلومات أساسية
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #002040; border-radius: 8px; padding: 10px;")
        info_layout = QGridLayout()
        info_frame.setLayout(info_layout)

        info_layout.addWidget(QLabel("رقم العرض:"), 0, 0)
        info_layout.addWidget(QLabel(q.get("quotation_number", "")), 0, 1)
        
        info_layout.addWidget(QLabel("العميل:"), 0, 2)
        client_name = q.get("client_display_name") or q.get("client_name") or ""
        info_layout.addWidget(QLabel(client_name), 0, 3)

        info_layout.addWidget(QLabel("تاريخ الإصدار:"), 1, 0)
        info_layout.addWidget(QLabel(q.get("issue_date", "")[:10] if q.get("issue_date") else ""), 1, 1)
        
        info_layout.addWidget(QLabel("صالح حتى:"), 1, 2)
        info_layout.addWidget(QLabel(q.get("valid_until", "")[:10] if q.get("valid_until") else ""), 1, 3)

        info_layout.addWidget(QLabel("الحالة:"), 2, 0)
        status_label = QLabel(q.get("status", ""))
        status_label.setStyleSheet(f"color: {QuotationManagerTab.STATUS_COLORS.get(q.get('status', ''), '#fff')};")
        info_layout.addWidget(status_label, 2, 1)

        layout.addWidget(info_frame)

        # الوصف ونطاق العمل
        if q.get("description") or q.get("scope_of_work"):
            desc_group = QGroupBox("📝 الوصف ونطاق العمل")
            desc_layout = QVBoxLayout()
            desc_group.setLayout(desc_layout)
            
            if q.get("description"):
                desc_layout.addWidget(QLabel(q["description"]))
            if q.get("scope_of_work"):
                desc_layout.addWidget(QLabel(f"\n{q['scope_of_work']}"))
            
            layout.addWidget(desc_group)

        # البنود
        items_group = QGroupBox("📦 البنود")
        items_layout = QVBoxLayout()
        items_group.setLayout(items_layout)

        items_table = QTableWidget()
        items_table.setColumnCount(4)
        items_table.setHorizontalHeaderLabels(["الوصف", "الكمية", "السعر", "الإجمالي"])
        items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        items = q.get("items", [])
        items_table.setRowCount(len(items))
        for row, item in enumerate(items):
            items_table.setItem(row, 0, QTableWidgetItem(item.get("description", "")))
            items_table.setItem(row, 1, QTableWidgetItem(str(item.get("quantity", 1))))
            items_table.setItem(row, 2, QTableWidgetItem(f"{item.get('unit_price', 0):,.0f}"))
            items_table.setItem(row, 3, QTableWidgetItem(f"{item.get('total', 0):,.0f}"))
        
        items_layout.addWidget(items_table)
        layout.addWidget(items_group)

        # الإجماليات
        totals_frame = QFrame()
        totals_frame.setStyleSheet("background-color: #003366; border-radius: 8px; padding: 10px;")
        totals_layout = QHBoxLayout()
        totals_frame.setLayout(totals_layout)

        totals_layout.addWidget(QLabel(f"الإجمالي: {q.get('subtotal', 0):,.0f}"))
        if q.get("discount_amount", 0) > 0:
            totals_layout.addWidget(QLabel(f"الخصم: {q.get('discount_amount', 0):,.0f}"))
        if q.get("tax_amount", 0) > 0:
            totals_layout.addWidget(QLabel(f"الضريبة: {q.get('tax_amount', 0):,.0f}"))
        
        total_label = QLabel(f"المجموع: {q.get('total_amount', 0):,.0f} {q.get('currency', 'EGP')}")
        total_label.setStyleSheet("color: #4a90e2; font-size: 16px; font-weight: bold;")
        totals_layout.addWidget(total_label)

        layout.addWidget(totals_frame)

        # زر الإغلاق
        close_btn = QPushButton("إغلاق")
        close_btn.setStyleSheet(BUTTON_STYLES["info"])
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _apply_style(self):
        """تطبيق الستايل"""
        self.setStyleSheet("""
            QDialog { background-color: #001a3a; color: #ffffff; }
            QLabel { color: #ffffff; }
            QGroupBox {
                background-color: #002040; border: 1px solid #003366;
                border-radius: 8px; margin-top: 10px; padding-top: 15px;
                font-weight: bold; color: #4a90e2;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QTableWidget {
                background-color: #002040; gridline-color: #003366;
                border: 1px solid #003366;
            }
            QHeaderView::section {
                background-color: #003366; color: #ffffff;
                padding: 6px; border: none;
            }
        """)


class ServiceSelectDialog(QDialog):
    """نافذة اختيار خدمة"""
    
    def __init__(self, services: list, parent=None):
        super().__init__(parent)
        self.services = services
        self.selected_service = None
        self.setWindowTitle("اختر خدمة")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.init_ui()
        self._apply_style()

    def init_ui(self):
        """إنشاء الواجهة"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QLabel("اختر الخدمة:"))

        self.service_combo = QComboBox()
        for service in self.services:
            # دعم dict و object
            if hasattr(service, 'get'):
                name = service.get("name", "")
                price = service.get("default_price", 0)
            else:
                name = getattr(service, "name", "")
                price = getattr(service, "default_price", 0)
            self.service_combo.addItem(f"{name} ({price:,.0f} EGP)", service)
        layout.addWidget(self.service_combo)

        # أزرار
        btn_layout = QHBoxLayout()
        
        ok_btn = QPushButton("✅ اختيار")
        ok_btn.setStyleSheet(BUTTON_STYLES["success"])
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["danger"])
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_selected_service(self) -> dict:
        """جلب الخدمة المختارة"""
        return self.service_combo.currentData()

    def _apply_style(self):
        """تطبيق الستايل"""
        self.setStyleSheet("""
            QDialog { background-color: #001a3a; color: #ffffff; }
            QLabel { color: #ffffff; font-size: 14px; }
            QComboBox {
                background-color: #002040; color: #ffffff;
                border: 2px solid #003366; border-radius: 6px; padding: 8px;
            }
        """)
