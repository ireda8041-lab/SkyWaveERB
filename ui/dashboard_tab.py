# الملف: ui/dashboard_tab.py
"""
لوحة التحكم الاحترافية - الحل النهائي
مصدر بيانات موحد + دعم كامل للعربية
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QSizePolicy, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

# مكتبات الرسم البياني
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# مكتبات معالجة النص العربي
import arabic_reshaper
from bidi.algorithm import get_display

from services.accounting_service import AccountingService


def fix_text(text: str) -> str:
    """دالة لإصلاح النص العربي في الرسوم البيانية"""
    if not text:
        return ""
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)
    except Exception:
        return text


class StatCard(QFrame):
    """تصميم الكارت الاحترافي - بدون أقواس مكسورة"""

    def __init__(self, title: str, value: str, icon: str, color_hex: str):
        super().__init__()
        self.color_hex = color_hex
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(100)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1e293b;
                border-radius: 15px;
                border-right: 8px solid {color_hex};
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
            QLabel#Title {{
                color: #94a3b8;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI', 'Cairo', sans-serif;
            }}
            QLabel#Value {{
                color: white;
                font-weight: bold;
                font-size: 24px;
                font-family: 'Segoe UI', 'Cairo', sans-serif;
            }}
            QLabel#Icon {{
                font-size: 32px;
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(18, 12, 18, 12)

        # النصوص (يمين)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)

        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("Title")

        self.lbl_value = QLabel(value)
        self.lbl_value.setObjectName("Value")

        text_layout.addWidget(self.lbl_title)
        text_layout.addWidget(self.lbl_value)

        # الأيقونة (يسار)
        lbl_icon = QLabel(icon)
        lbl_icon.setObjectName("Icon")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addWidget(lbl_icon)
        self.setLayout(layout)

    def set_value(self, value: float):
        """تحديث قيمة الكارت"""
        self.lbl_value.setText(f"{value:,.2f} EGP")


class FinancialChart(FigureCanvas):
    """رسم بياني يدعم العربية بالكامل"""

    def __init__(self, parent=None, width: int = 5, height: int = 4, dpi: int = 100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.fig.patch.set_facecolor('#1e293b')

    def plot_data(self, sales: float, expenses: float, profit: float):
        """رسم البيانات مع دعم العربية"""
        self.axes.clear()

        # البيانات مع إصلاح النص العربي
        categories = [fix_text('المبيعات'), fix_text('المصروفات'), fix_text('صافي الربح')]
        values = [sales, expenses, profit]
        colors = ['#3b82f6', '#ef4444', '#10b981']  # أزرق، أحمر، أخضر

        # الرسم
        bars = self.axes.bar(categories, values, color=colors, width=0.5)

        # تنسيق المحاور والألوان (Dark Mode)
        self.axes.set_facecolor('#1e293b')
        self.axes.tick_params(axis='x', colors='white', labelsize=11)
        self.axes.tick_params(axis='y', colors='white', labelsize=10)
        self.axes.spines['bottom'].set_color('#475569')
        self.axes.spines['left'].set_color('#475569')
        self.axes.spines['top'].set_visible(False)
        self.axes.spines['right'].set_visible(False)

        # خطوط الشبكة
        self.axes.grid(axis='y', linestyle='--', alpha=0.2, color='#475569')
        self.axes.set_axisbelow(True)

        # زيادة سقف الرسم
        if values and max(values) > 0:
            self.axes.set_ylim(0, max(values) * 1.25)

        # إضافة القيم فوق الأعمدة
        for bar in bars:
            height = bar.get_height()
            self.axes.text(
                bar.get_x() + bar.get_width() / 2., height,
                f'{height:,.0f}',
                ha='center', va='bottom',
                color='white', fontweight='bold', fontsize=10
            )

        self.fig.tight_layout(pad=1.5)
        self.draw()


class DashboardTab(QWidget):
    """لوحة التحكم الرئيسية - مصدر بيانات موحد"""

    def __init__(self, accounting_service: AccountingService, parent=None):
        super().__init__(parent)
        self.accounting_service = accounting_service
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تفعيل الاتجاه من اليمين لليسار
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(main_layout)

        # === 1. العنوان مع زر التحديث ===
        header_layout = QHBoxLayout()

        header = QLabel("📊 لوحة القيادة والمؤشرات المالية")
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")

        self.refresh_btn = QPushButton("🔄 تحديث")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 8px;
                font-size: 13px;
                font-family: 'Segoe UI', 'Cairo', sans-serif;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.refresh_btn.clicked.connect(self.refresh_data)

        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(self.refresh_btn)
        main_layout.addLayout(header_layout)

        # === 2. الكروت الإحصائية (4 كروت) ===
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)

        self.card_sales = StatCard("إجمالي المبيعات", "0.00 EGP", "💼", "#3b82f6")
        self.card_collected = StatCard("النقدية المحصلة", "0.00 EGP", "💰", "#10b981")
        self.card_receivables = StatCard("مستحقات آجلة", "0.00 EGP", "📝", "#f59e0b")
        self.card_expenses = StatCard("المصروفات", "0.00 EGP", "💸", "#ef4444")

        cards_layout.addWidget(self.card_sales)
        cards_layout.addWidget(self.card_collected)
        cards_layout.addWidget(self.card_receivables)
        cards_layout.addWidget(self.card_expenses)
        main_layout.addLayout(cards_layout)

        # === 3. القسم السفلي (الرسم البياني + الجدول) ===
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(15)

        # أ) الرسم البياني
        chart_container = QFrame()
        chart_container.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 15px;
                border: 1px solid #334155;
            }
        """)
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(15, 15, 15, 15)

        lbl_chart = QLabel("📈 الملخص المالي")
        lbl_chart.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 14px;
            border: none;
            background: transparent;
            font-family: 'Segoe UI', 'Cairo', sans-serif;
        """)
        chart_layout.addWidget(lbl_chart)

        self.chart = FinancialChart(self, width=5, height=3.5)
        chart_layout.addWidget(self.chart)
        bottom_layout.addWidget(chart_container, stretch=3)

        # ب) جدول آخر العمليات
        table_container = QFrame()
        table_container.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 15px;
                border: 1px solid #334155;
            }
        """)
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(15, 15, 15, 15)

        lbl_table = QLabel("📝 آخر العمليات المسجلة")
        lbl_table.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 14px;
            border: none;
            background: transparent;
            font-family: 'Segoe UI', 'Cairo', sans-serif;
        """)
        table_layout.addWidget(lbl_table)

        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(3)
        self.recent_table.setHorizontalHeaderLabels(["التاريخ", "الوصف", "المبلغ"])
        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.recent_table.setStyleSheet("""
            QTableWidget {
                background-color: #0f172a;
                border: none;
                color: #e2e8f0;
                gridline-color: #334155;
                border-radius: 8px;
                font-family: 'Segoe UI', 'Cairo', sans-serif;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                border: none;
                padding: 8px;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        table_layout.addWidget(self.recent_table)
        bottom_layout.addWidget(table_container, stretch=2)

        main_layout.addLayout(bottom_layout)
        main_layout.addStretch()

    def refresh_data(self):
        """تحديث البيانات من المصدر الموحد"""
        print("INFO: [Dashboard] جاري تحديث أرقام الداشبورد...")

        from PyQt6.QtWidgets import QApplication
        from core.data_loader import get_data_loader

        QApplication.processEvents()

        def fetch_data():
            try:
                # استخدام الدالة الموحدة الجديدة
                stats = self.accounting_service.get_dashboard_stats()
                recent = self.accounting_service.get_recent_journal_entries(8)
                return {'stats': stats, 'recent': recent}
            except Exception as e:
                print(f"ERROR: [Dashboard] فشل جلب البيانات: {e}")
                return {}

        def on_data_loaded(data):
            try:
                stats = data.get('stats', {})
                recent = data.get('recent', [])

                # استخراج القيم من المصدر الموحد
                sales = stats.get("total_sales", 0)
                collected = stats.get("cash_collected", 0)
                receivables = stats.get("receivables", 0)
                expenses = stats.get("expenses", 0)
                net_profit = stats.get("net_profit", 0)

                # تحديث الكروت
                self.card_sales.set_value(sales)
                self.card_collected.set_value(collected)
                self.card_receivables.set_value(receivables)
                self.card_expenses.set_value(expenses)

                # تحديث الرسم البياني (نفس البيانات بالضبط)
                self.chart.plot_data(sales, expenses, net_profit)

                # تحديث جدول آخر العمليات
                self.recent_table.setRowCount(len(recent))
                for i, entry in enumerate(recent):
                    if isinstance(entry, dict):
                        date_val = entry.get('date', '')
                        desc_val = entry.get('description', '')
                        amount_val = entry.get('amount', 0)
                    else:
                        # tuple format
                        date_val = str(entry[0]) if len(entry) > 0 else ''
                        desc_val = str(entry[1]) if len(entry) > 1 else ''
                        amount_val = entry[2] if len(entry) > 2 else 0

                    date_item = QTableWidgetItem(date_val)
                    date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.recent_table.setItem(i, 0, date_item)

                    desc_item = QTableWidgetItem(desc_val)
                    self.recent_table.setItem(i, 1, desc_item)

                    amount_item = QTableWidgetItem(f"{amount_val:,.2f}")
                    amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.recent_table.setItem(i, 2, amount_item)

                print("INFO: [Dashboard] ✅ تم تحديث الداشبورد بنجاح")
            except Exception as e:
                print(f"ERROR: [Dashboard] فشل تحديث الواجهة: {e}")
                import traceback
                traceback.print_exc()

        def on_error(error_msg):
            print(f"ERROR: [Dashboard] {error_msg}")

        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="dashboard_data",
            load_function=fetch_data,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True
        )
