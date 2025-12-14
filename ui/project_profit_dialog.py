# الملف: ui/project_profit_dialog.py
"""
تقرير ربحية مشروع - تصميم محسن واحترافي
"""

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.project_service import ProjectService


class ProjectProfitDialog(QDialog):
    """شاشة تقرير ربحية مشروع - تصميم احترافي ومتجاوب"""

    def __init__(self, project: schemas.Project, project_service: ProjectService, parent=None):
        super().__init__(parent)

        self.project = project
        self.project_service = project_service

        self.setWindowTitle(f"📊 تقرير ربحية مشروع: {project.name}")
        self.resize(900, 600)
        self.setMinimumSize(800, 550)

        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        self._init_ui()
        self.load_profit_data()

    def _init_ui(self):
        from ui.styles import BUTTON_STYLES, COLORS, TABLE_STYLE_DARK, create_centered_item

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # منطقة التمرير
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {COLORS['bg_dark']};
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['bg_medium']};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['primary']};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)

        # === معلومات المشروع ===
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_medium']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(20)

        # المشروع
        self.project_label = QLabel(f"📌 <b>المشروع:</b> <span style='color:{COLORS['primary']};'>{self.project.name}</span>")
        self.project_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px;")

        # العميل
        client_display = self.project.client_id or "غير محدد"
        self.client_label = QLabel(f"👤 <b>العميل:</b> {client_display}")
        self.client_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px;")

        # الحالة
        status_text = self.project.status.value if hasattr(self.project.status, 'value') else str(self.project.status)
        status_color = "#10b981" if status_text == "نشط" else COLORS['text_secondary']
        self.status_label = QLabel(f"🏷️ <b>الحالة:</b> <span style='color:{status_color};'>{status_text}</span>")
        self.status_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px;")

        info_layout.addWidget(self.project_label)
        info_layout.addStretch()
        info_layout.addWidget(self.client_label)
        info_layout.addStretch()
        info_layout.addWidget(self.status_label)

        layout.addWidget(info_frame)

        # === كروت الأرقام (KPIs) ===
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(8)

        self.revenue_card = self._create_kpi_card("إجمالي العقد", "revenue", "#3b82f6", "💰")
        self.paid_card = self._create_kpi_card("المدفوع", "paid", "#10b981", "✅")
        self.due_card = self._create_kpi_card("المتبقي", "due", "#f59e0b", "⏳")
        self.expenses_card = self._create_kpi_card("المصروفات", "expenses", "#ef4444", "📉")
        self.profit_card = self._create_kpi_card("صافي الربح", "profit", "#8b5cf6", "📈")

        kpi_layout.addWidget(self.revenue_card)
        kpi_layout.addWidget(self.paid_card)
        kpi_layout.addWidget(self.due_card)
        kpi_layout.addWidget(self.expenses_card)
        kpi_layout.addWidget(self.profit_card)

        layout.addLayout(kpi_layout)

        # === شريط التقدم ===
        progress_frame = QFrame()
        progress_frame.setStyleSheet(f"background-color: transparent;")
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(0, 5, 0, 5)
        progress_layout.setSpacing(4)

        self.collection_label = QLabel("جاري التحميل...")
        self.collection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.collection_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")

        self.collection_progress = QProgressBar()
        self.collection_progress.setFixedHeight(12)
        self.collection_progress.setTextVisible(False)
        self.collection_progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 6px;
                background-color: {COLORS['bg_medium']};
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
                border-radius: 6px;
            }}
        """)

        progress_layout.addWidget(self.collection_label)
        progress_layout.addWidget(self.collection_progress)
        layout.addWidget(progress_frame)

        # === الجداول ===
        tables_splitter = QSplitter(Qt.Orientation.Horizontal)
        tables_splitter.setHandleWidth(6)
        tables_splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {COLORS['border']}; }}")

        # جدول الدفعات
        payments_frame = QFrame()
        payments_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_medium']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        pay_layout = QVBoxLayout(payments_frame)
        pay_layout.setContentsMargins(10, 10, 10, 10)
        pay_layout.setSpacing(8)

        pay_title = QLabel("💳 سجل الدفعات (الوارد)")
        pay_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px; font-weight: bold;")
        pay_layout.addWidget(pay_title)

        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(4)
        self.payments_table.setHorizontalHeaderLabels(["التاريخ", "المبلغ", "الحساب", "ملاحظات"])
        self.payments_table.setStyleSheet(TABLE_STYLE_DARK)
        self._setup_table(self.payments_table)
        pay_layout.addWidget(self.payments_table)

        # جدول المصروفات
        expenses_frame = QFrame()
        expenses_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_medium']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        exp_layout = QVBoxLayout(expenses_frame)
        exp_layout.setContentsMargins(10, 10, 10, 10)
        exp_layout.setSpacing(8)

        exp_title = QLabel("💸 سجل المصروفات (الصادر)")
        exp_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px; font-weight: bold;")
        exp_layout.addWidget(exp_title)

        self.expenses_table = QTableWidget()
        self.expenses_table.setColumnCount(4)
        self.expenses_table.setHorizontalHeaderLabels(["التاريخ", "الفئة", "الوصف", "المبلغ"])
        self.expenses_table.setStyleSheet(TABLE_STYLE_DARK)
        self._setup_table(self.expenses_table)
        exp_layout.addWidget(self.expenses_table)

        tables_splitter.addWidget(payments_frame)
        tables_splitter.addWidget(expenses_frame)
        tables_splitter.setSizes([450, 450])

        layout.addWidget(tables_splitter, 1)

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        # === منطقة الأزرار ===
        buttons_container = QWidget()
        buttons_container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_medium']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(14, 10, 14, 10)
        buttons_layout.setSpacing(8)

        self.refresh_btn = QPushButton("🔄 تحديث البيانات")
        self.refresh_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_btn.setFixedHeight(28)
        self.refresh_btn.clicked.connect(self.load_profit_data)
        buttons_layout.addWidget(self.refresh_btn)

        buttons_layout.addStretch()

        self.close_btn = QPushButton("إغلاق")
        self.close_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.close_btn.setFixedHeight(28)
        self.close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.close_btn)

        main_layout.addWidget(buttons_container)

    def _create_kpi_card(self, title: str, key: str, color: str, icon: str) -> QFrame:
        """إنشاء كارت KPI"""
        card = QFrame()
        card.setObjectName("KpiCard")
        card.setProperty("card_key", key)
        card.setProperty("base_color", color)
        card.setStyleSheet(f"""
            QFrame#KpiCard {{
                background-color: {color};
                border-radius: 8px;
            }}
        """)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(3)

        # العنوان مع الأيقونة
        header = QHBoxLayout()
        header.setSpacing(4)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 12px; background: transparent;")
        header.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 10px; background: transparent;")
        header.addWidget(title_lbl)
        header.addStretch()

        card_layout.addLayout(header)

        value_lbl = QLabel("0.00")
        value_lbl.setObjectName(f"val_{key}")
        value_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 14px; background: transparent;")
        card_layout.addWidget(value_lbl)

        return card

    def _setup_table(self, table: QTableWidget):
        """إعداد الجدول"""
        from ui.styles import fix_table_rtl
        
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        fix_table_rtl(table)
        
        header = table.horizontalHeader()
        if header:
            # تخصيص الأعمدة حسب نوع الجدول
            col_count = table.columnCount()
            if col_count == 4:
                # جدول الدفعات: التاريخ، المبلغ، الحساب، ملاحظات
                # جدول المصروفات: التاريخ، الفئة، الوصف، المبلغ
                header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # التاريخ/الفئة
                header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # المبلغ/الفئة
                header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # الحساب/الوصف - يتمدد
                header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # ملاحظات/المبلغ
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

    def _update_card(self, card: QFrame, key: str, value: float):
        """تحديث قيمة الكارت"""
        value_label = card.findChild(QLabel, f"val_{key}")
        if value_label:
            value_label.setText(f"{value:,.2f}")

        # تغيير اللون حسب القيمة
        base_color = card.property("base_color")
        final_color = base_color

        if key == "profit":
            final_color = "#10b981" if value >= 0 else "#ef4444"
        elif key == "due":
            final_color = "#f59e0b" if value > 0 else "#10b981"

        card.setStyleSheet(f"""
            QFrame#KpiCard {{
                background-color: {final_color};
                border-radius: 8px;
            }}
        """)

    def load_profit_data(self):
        """تحميل بيانات الربحية"""
        try:
            profit_data = self.project_service.get_project_profitability(self.project.name)

            total_revenue = profit_data.get("total_revenue", 0.0)
            total_paid = profit_data.get("total_paid", 0.0)
            balance_due = profit_data.get("balance_due", 0.0)
            total_expenses = profit_data.get("total_expenses", 0.0)
            net_profit = profit_data.get("net_profit", 0.0)

            # تحديث الكروت
            self._update_card(self.revenue_card, "revenue", total_revenue)
            self._update_card(self.paid_card, "paid", total_paid)
            self._update_card(self.due_card, "due", balance_due)
            self._update_card(self.expenses_card, "expenses", total_expenses)
            self._update_card(self.profit_card, "profit", net_profit)

            # تحديث شريط التقدم
            if total_revenue > 0:
                percent = int((total_paid / total_revenue) * 100)
                self.collection_progress.setValue(min(percent, 100))
                self.collection_label.setText(f"تم تحصيل {percent}% ({total_paid:,.2f} من {total_revenue:,.2f})")
            else:
                self.collection_progress.setValue(0)
                self.collection_label.setText("لا توجد قيمة للعقد")

            # تحديث جدول الدفعات
            from ui.styles import create_centered_item
            payments = self.project_service.get_payments_for_project(self.project.name)
            self.payments_table.setRowCount(0)
            for i, pay in enumerate(payments):
                self.payments_table.insertRow(i)
                date_str = pay.date.strftime("%Y-%m-%d") if isinstance(pay.date, datetime) else str(pay.date)
                self.payments_table.setItem(i, 0, create_centered_item(date_str))

                amount_item = create_centered_item(f"{pay.amount:,.2f}")
                amount_item.setForeground(QColor("#10b981"))
                amount_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                self.payments_table.setItem(i, 1, amount_item)

                account_name = self._get_account_name(pay)
                self.payments_table.setItem(i, 2, create_centered_item(account_name))
                self.payments_table.setItem(i, 3, create_centered_item(getattr(pay, 'notes', '') or "-"))

            # تحديث جدول المصروفات
            expenses = self.project_service.get_expenses_for_project(self.project.name)
            self.expenses_table.setRowCount(0)
            for i, exp in enumerate(expenses):
                self.expenses_table.insertRow(i)
                date_str = exp.date.strftime("%Y-%m-%d") if isinstance(exp.date, datetime) else str(exp.date)
                self.expenses_table.setItem(i, 0, create_centered_item(date_str))
                self.expenses_table.setItem(i, 1, create_centered_item(exp.category or "-"))
                self.expenses_table.setItem(i, 2, create_centered_item(exp.description or "-"))

                amount_item = create_centered_item(f"{exp.amount:,.2f}")
                amount_item.setForeground(QColor("#ef4444"))
                amount_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                self.expenses_table.setItem(i, 3, amount_item)

        except Exception as e:
            print(f"ERROR: [ProjectProfitDialog] {e}")
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء تحميل البيانات: {e}")

    def _get_account_name(self, payment) -> str:
        """جلب اسم الحساب"""
        if not hasattr(payment, 'account_id') or not payment.account_id:
            return "-"
        try:
            if hasattr(self.project_service, 'accounting_service'):
                account = self.project_service.accounting_service.repo.get_account_by_code(payment.account_id)
                if account:
                    return account.name
                account = self.project_service.accounting_service.repo.get_account_by_id(payment.account_id)
                return account.name if account else str(payment.account_id)
            return str(payment.account_id)
        except Exception:
            return str(payment.account_id)
