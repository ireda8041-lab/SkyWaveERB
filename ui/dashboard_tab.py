# الملف: ui/dashboard_tab.py
"""
لوحة التحكم الاحترافية - الحل النهائي
مصدر بيانات موحد + دعم كامل للعربية
"""

import json
import os
from datetime import datetime, timedelta

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.styles import TABLE_STYLE_DARK, create_centered_item, get_cairo_font

# ⚡ استيراد آمن لمكتبات الرسم البياني
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    FigureCanvas = None
    Figure = None
    MATPLOTLIB_AVAILABLE = False

# ⚡ استيراد آمن لمكتبات معالجة النص العربي
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_RESHAPER_AVAILABLE = True
except ImportError:
    arabic_reshaper = None
    get_display = None
    ARABIC_RESHAPER_AVAILABLE = False

from core.schemas import DashboardSettings, KPIData
from services.accounting_service import AccountingService

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


def fix_text(text: str) -> str:
    """دالة لإصلاح النص العربي في الرسوم البيانية"""
    if not text:
        return ""
    if not ARABIC_RESHAPER_AVAILABLE:
        return text
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)
    except Exception:
        return text


class StatCard(QFrame):
    """تصميم الكارت الاحترافي - متجاوب مع الشاشة"""

    def __init__(self, title: str, value: str, icon: str, color_hex: str):
        super().__init__()
        self.color_hex = color_hex
        self.setFrameShape(QFrame.Shape.StyledPanel)

        # 📱 تجاوب: حد أدنى وأقصى للحجم
        self.setMinimumHeight(90)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

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
                font-size: 13px;
                font-weight: bold;
                font-family: 'Cairo';
            }}
            QLabel#Value {{
                color: white;
                font-weight: bold;
                font-size: 20px;
                font-family: 'Cairo';
            }}
            QLabel#Icon {{
                font-size: 28px;
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


class EnhancedKPICard(QFrame):
    """
    بطاقة KPI محسّنة مع مؤشر الاتجاه
    تعرض القيمة الحالية مع نسبة التغير واتجاه التغير (سهم أخضر/أحمر)

    Requirements: 1.1, 1.4, 1.5, 1.6, 1.7
    """

    def __init__(
        self,
        title: str,
        icon: str,
        color_hex: str,
        parent: QWidget = None
    ):
        """
        Args:
            title: عنوان المؤشر (مثل "إجمالي الإيرادات")
            icon: أيقونة emoji
            color_hex: لون الحد الجانبي
        """
        super().__init__(parent)
        self.title = title
        self.icon = icon
        self.color_hex = color_hex
        self._current_value = 0.0
        self._previous_value = None

        self.setFrameShape(QFrame.Shape.StyledPanel)

        # 📱 تجاوب: حد أدنى وأقصى للحجم
        self.setMinimumHeight(110)
        self.setMinimumWidth(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._apply_styles()
        self._init_ui()

    def _apply_styles(self):
        """تطبيق الأنماط على البطاقة"""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1e293b;
                border-radius: 15px;
                border-right: 8px solid {self.color_hex};
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
            QLabel#Title {{
                color: #94a3b8;
                font-size: 13px;
                font-weight: bold;
                font-family: 'Cairo';
            }}
            QLabel#Value {{
                color: white;
                font-weight: bold;
                font-size: 20px;
                font-family: 'Cairo';
            }}
            QLabel#Icon {{
                font-size: 28px;
            }}
            QLabel#TrendUp {{
                color: #10b981;
                font-size: 12px;
                font-weight: bold;
                font-family: 'Cairo';
            }}
            QLabel#TrendDown {{
                color: #ef4444;
                font-size: 12px;
                font-weight: bold;
                font-family: 'Cairo';
            }}
            QLabel#TrendNeutral {{
                color: #94a3b8;
                font-size: 12px;
                font-weight: bold;
                font-family: 'Cairo';
            }}
        """)

    def _init_ui(self):
        """تهيئة واجهة المستخدم"""
        layout = QHBoxLayout()
        layout.setContentsMargins(18, 12, 18, 12)

        # النصوص (يمين)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)

        self.lbl_title = QLabel(self.title)
        self.lbl_title.setObjectName("Title")

        self.lbl_value = QLabel("0.00 EGP")
        self.lbl_value.setObjectName("Value")

        # مؤشر الاتجاه
        self.lbl_trend = QLabel("")
        self.lbl_trend.setObjectName("TrendNeutral")

        text_layout.addWidget(self.lbl_title)
        text_layout.addWidget(self.lbl_value)
        text_layout.addWidget(self.lbl_trend)

        # الأيقونة (يسار)
        lbl_icon = QLabel(self.icon)
        lbl_icon.setObjectName("Icon")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addWidget(lbl_icon)
        self.setLayout(layout)

    def set_value(self, value: float, previous_value: float = None) -> None:
        """
        تحديث قيمة المؤشر مع حساب التغير

        Args:
            value: القيمة الحالية
            previous_value: القيمة السابقة لحساب نسبة التغير
        """
        self._current_value = value
        self._previous_value = previous_value

        # تحديث القيمة المعروضة
        self.lbl_value.setText(f"{value:,.2f} EGP")

        # حساب وعرض الاتجاه
        percentage, direction = self._calculate_trend(value, previous_value)
        self._update_trend_display(percentage, direction)

    def _calculate_trend(self, current: float, previous: float) -> tuple[float, str]:
        """
        حساب نسبة التغير واتجاهه

        Returns:
            (percentage_change, direction: "up" | "down" | "neutral")
        """
        if previous is None or previous == 0:
            return 0.0, "neutral"

        percentage = ((current - previous) / previous) * 100

        if current > previous:
            return percentage, "up"
        elif current < previous:
            return percentage, "down"
        return 0.0, "neutral"

    def _update_trend_display(self, percentage: float, direction: str):
        """تحديث عرض مؤشر الاتجاه"""
        if direction == "up":
            self.lbl_trend.setObjectName("TrendUp")
            self.lbl_trend.setText(f"▲ {abs(percentage):.1f}%")
        elif direction == "down":
            self.lbl_trend.setObjectName("TrendDown")
            self.lbl_trend.setText(f"▼ {abs(percentage):.1f}%")
        else:
            self.lbl_trend.setObjectName("TrendNeutral")
            self.lbl_trend.setText("━ 0.0%")

        # إعادة تطبيق الأنماط لتحديث اللون
        self._apply_styles()

    def get_kpi_data(self) -> KPIData:
        """
        الحصول على بيانات KPI كـ KPIData object

        Returns:
            KPIData object مع القيم الحالية
        """
        return KPIData(
            name=self.title,
            current_value=self._current_value,
            previous_value=self._previous_value
        )

    @property
    def current_value(self) -> float:
        """القيمة الحالية"""
        return self._current_value

    @property
    def previous_value(self) -> float | None:
        """القيمة السابقة"""
        return self._previous_value


# ⚡ إنشاء كلاس أساسي للرسوم البيانية
if MATPLOTLIB_AVAILABLE and FigureCanvas is not None:
    _ChartBase = FigureCanvas
else:
    _ChartBase = QWidget  # استخدام QWidget كبديل


class FinancialChart(_ChartBase):
    """رسم بياني يدعم العربية بالكامل"""

    def __init__(self, parent=None, width: int = 5, height: int = 4, dpi: int = 100):
        if not MATPLOTLIB_AVAILABLE:
            super().__init__(parent)
            self.setMinimumSize(width * 80, height * 80)
            return

        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.fig.patch.set_facecolor('#1e293b')

    def plot_data(self, sales: float, expenses: float, profit: float):
        """رسم البيانات مع دعم العربية"""
        if not MATPLOTLIB_AVAILABLE:
            return

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


class CashFlowChart(_ChartBase):
    """
    مخطط التدفق النقدي
    يعرض التدفقات الداخلة (أخضر) والخارجة (أحمر) وصافي التدفق عبر الزمن

    Requirements: 2.1, 2.4, 2.5, 2.7
    """

    def __init__(self, parent: QWidget = None, width: int = 6, height: int = 4, dpi: int = 100):
        if not MATPLOTLIB_AVAILABLE:
            super().__init__(parent)
            self.setMinimumSize(width * 80, height * 80)
            return

        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.fig.patch.set_facecolor('#1e293b')

        # ألوان المخطط
        self.inflow_color = '#10b981'   # أخضر للدفعات الداخلة
        self.outflow_color = '#ef4444'  # أحمر للمصروفات
        self.net_color = '#3b82f6'      # أزرق لصافي التدفق

    def plot_cash_flow(
        self,
        inflows: list[tuple[str, float]],
        outflows: list[tuple[str, float]],
        period: str = "monthly"
    ) -> None:
        """
        رسم مخطط التدفق النقدي

        Args:
            inflows: قائمة الدفعات الداخلة (التاريخ، المبلغ)
            outflows: قائمة المصروفات (التاريخ، المبلغ)
            period: الفترة الزمنية للتجميع ("daily", "weekly", "monthly")

        Requirements: 2.1, 2.4, 2.5, 2.7
        """
        self.axes.clear()

        # تجميع البيانات حسب الفترة
        aggregated_inflows = self._aggregate_by_period(inflows, period)
        aggregated_outflows = self._aggregate_by_period(outflows, period)

        # الحصول على جميع الفترات
        all_periods = sorted(set(aggregated_inflows.keys()) | set(aggregated_outflows.keys()))

        if not all_periods:
            self._draw_empty_chart()
            return

        # تحضير البيانات للرسم
        inflow_values = [aggregated_inflows.get(p, 0.0) for p in all_periods]
        outflow_values = [aggregated_outflows.get(p, 0.0) for p in all_periods]
        net_values = [aggregated_inflows.get(p, 0.0) - aggregated_outflows.get(p, 0.0) for p in all_periods]

        # إصلاح النصوص العربية للتسميات
        x_labels = [fix_text(self._format_period_label(p, period)) for p in all_periods]
        x_positions = range(len(all_periods))

        # رسم الخطوط
        self.axes.plot(x_positions, inflow_values,
                      color=self.inflow_color, marker='o', linewidth=2,
                      label=fix_text('الدفعات الداخلة'), markersize=6)
        self.axes.plot(x_positions, outflow_values,
                      color=self.outflow_color, marker='s', linewidth=2,
                      label=fix_text('المصروفات'), markersize=6)
        self.axes.plot(x_positions, net_values,
                      color=self.net_color, marker='^', linewidth=2, linestyle='--',
                      label=fix_text('صافي التدفق'), markersize=6)

        # تنسيق المحاور
        self._style_axes(x_positions, x_labels)

        # إضافة الأسطورة
        self.axes.legend(loc='upper left', facecolor='#1e293b', edgecolor='#475569',
                        labelcolor='white', fontsize=9)

        self.fig.tight_layout(pad=1.5)
        self.draw()

    def _aggregate_by_period(
        self,
        data: list[tuple[str, float]],
        period: str
    ) -> dict[str, float]:
        """
        تجميع البيانات حسب الفترة الزمنية

        Args:
            data: قائمة من (التاريخ/الفترة، المبلغ)
            period: الفترة الزمنية ("daily", "weekly", "monthly")

        Returns:
            dict مع المفتاح = الفترة والقيمة = المجموع

        Requirements: 2.2
        """
        aggregated: dict[str, float] = {}

        for period_key, amount in data:
            if period_key not in aggregated:
                aggregated[period_key] = 0.0
            aggregated[period_key] += amount

        return aggregated

    def _format_period_label(self, period_key: str, period_type: str) -> str:
        """تنسيق تسمية الفترة للعرض"""
        if period_type == "daily":
            # YYYY-MM-DD -> DD/MM
            try:
                parts = period_key.split('-')
                return f"{parts[2]}/{parts[1]}"
            except (IndexError, ValueError):
                return period_key
        elif period_type == "weekly":
            # YYYY-WXX -> أسبوع XX
            try:
                week_num = period_key.split('-W')[1]
                return f"أسبوع {week_num}"
            except (IndexError, ValueError):
                return period_key
        else:  # monthly
            # YYYY-MM -> MM/YYYY
            try:
                parts = period_key.split('-')
                months_ar = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
                            'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
                month_idx = int(parts[1]) - 1
                if 0 <= month_idx < 12:
                    return months_ar[month_idx]
                return f"{parts[1]}/{parts[0]}"
            except (IndexError, ValueError):
                return period_key

    def _style_axes(self, x_positions, x_labels):
        """تنسيق المحاور والألوان"""
        self.axes.set_facecolor('#1e293b')
        self.axes.tick_params(axis='x', colors='white', labelsize=9, rotation=45)
        self.axes.tick_params(axis='y', colors='white', labelsize=10)
        self.axes.spines['bottom'].set_color('#475569')
        self.axes.spines['left'].set_color('#475569')
        self.axes.spines['top'].set_visible(False)
        self.axes.spines['right'].set_visible(False)

        # تسميات المحور X
        self.axes.set_xticks(list(x_positions))
        self.axes.set_xticklabels(x_labels, ha='right')

        # خطوط الشبكة
        self.axes.grid(axis='y', linestyle='--', alpha=0.2, color='#475569')
        self.axes.set_axisbelow(True)

        # خط الصفر
        self.axes.axhline(y=0, color='#475569', linestyle='-', linewidth=0.5)

    def _draw_empty_chart(self):
        """رسم مخطط فارغ عند عدم وجود بيانات"""
        self.axes.set_facecolor('#1e293b')
        self.axes.text(0.5, 0.5, fix_text('لا توجد بيانات'),
                      ha='center', va='center', color='#94a3b8',
                      fontsize=14, transform=self.axes.transAxes)
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        for spine in self.axes.spines.values():
            spine.set_visible(False)
        self.fig.tight_layout(pad=1.5)
        self.draw()


class PeriodSelector(QFrame):
    """
    أداة اختيار الفترة الزمنية
    توفر أزرار لاختيار فترات محددة مسبقاً أو فترة مخصصة

    Requirements: 4.1, 4.3, 4.4
    """

    # Signal يُرسل عند تغيير الفترة
    period_changed = pyqtSignal(str, object, object)  # (period_type, start_date, end_date)

    PERIODS = {
        "today": "اليوم",
        "this_week": "هذا الأسبوع",
        "this_month": "هذا الشهر",
        "this_year": "هذا العام",
        "custom": "فترة مخصصة"
    }

    SETTINGS_FILE = "skywave_settings.json"

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._current_period = "this_month"
        self._custom_start = None
        self._custom_end = None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 10px;
                border: 1px solid #334155;
            }
            QPushButton {
                background-color: #334155;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-family: 'Cairo';
                font-size: 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            QPushButton:checked {
                background-color: #3b82f6;
            }
            QDateEdit {
                background-color: #334155;
                color: white;
                padding: 6px 10px;
                border-radius: 6px;
                font-family: 'Cairo';
                font-size: 12px;
                border: 1px solid #475569;
            }
            QDateEdit::drop-down {
                border: none;
                width: 20px;
            }
            QLabel {
                color: #94a3b8;
                font-family: 'Cairo';
                font-size: 12px;
                background: transparent;
                border: none;
            }
        """)

        self._init_ui()
        self.load_selection()

    def _init_ui(self):
        """تهيئة واجهة المستخدم"""
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # أزرار الفترات
        self.period_buttons = {}
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        for period_key, period_label in self.PERIODS.items():
            btn = QPushButton(period_label)
            btn.setCheckable(True)
            btn.setProperty("period_key", period_key)
            btn.clicked.connect(lambda checked, pk=period_key: self._on_period_clicked(pk))
            self.period_buttons[period_key] = btn
            self.button_group.addButton(btn)
            layout.addWidget(btn)

        # فاصل
        layout.addSpacing(10)

        # حقول التاريخ المخصص
        self.lbl_from = QLabel("من:")
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.dateChanged.connect(self._on_custom_date_changed)

        self.lbl_to = QLabel("إلى:")
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self._on_custom_date_changed)

        layout.addWidget(self.lbl_from)
        layout.addWidget(self.date_from)
        layout.addWidget(self.lbl_to)
        layout.addWidget(self.date_to)

        layout.addStretch()
        self.setLayout(layout)

        # إخفاء حقول التاريخ المخصص افتراضياً
        self._toggle_custom_dates(False)

        # تحديد الزر الافتراضي
        self.period_buttons["this_month"].setChecked(True)

    def _on_period_clicked(self, period_key: str):
        """معالج النقر على زر الفترة"""
        self._current_period = period_key

        # إظهار/إخفاء حقول التاريخ المخصص
        self._toggle_custom_dates(period_key == "custom")

        # حفظ الاختيار
        self.save_selection()

        # إرسال Signal بالفترة الجديدة
        start_date, end_date = self.get_date_range()
        self.period_changed.emit(period_key, start_date, end_date)

    def _on_custom_date_changed(self):
        """معالج تغيير التاريخ المخصص"""
        if self._current_period == "custom":
            self._custom_start = self.date_from.date().toPyDate()
            self._custom_end = self.date_to.date().toPyDate()

            # حفظ الاختيار
            self.save_selection()

            # إرسال Signal
            start_date, end_date = self.get_date_range()
            self.period_changed.emit("custom", start_date, end_date)

    def _toggle_custom_dates(self, show: bool):
        """إظهار/إخفاء حقول التاريخ المخصص"""
        self.lbl_from.setVisible(show)
        self.date_from.setVisible(show)
        self.lbl_to.setVisible(show)
        self.date_to.setVisible(show)

    def get_date_range(self) -> tuple[datetime, datetime]:
        """
        الحصول على نطاق التاريخ المحدد

        Returns:
            tuple من (start_date, end_date)
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if self._current_period == "today":
            return today, today.replace(hour=23, minute=59, second=59)

        elif self._current_period == "this_week":
            # بداية الأسبوع (السبت في التقويم العربي)
            days_since_saturday = (today.weekday() + 2) % 7
            start = today - timedelta(days=days_since_saturday)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            return start, end

        elif self._current_period == "this_month":
            start = today.replace(day=1)
            # نهاية الشهر
            if today.month == 12:
                end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(seconds=1)
            else:
                end = today.replace(month=today.month + 1, day=1) - timedelta(seconds=1)
            return start, end

        elif self._current_period == "this_year":
            start = today.replace(month=1, day=1)
            end = today.replace(month=12, day=31, hour=23, minute=59, second=59)
            return start, end

        elif self._current_period == "custom":
            if self._custom_start and self._custom_end:
                start = datetime.combine(self._custom_start, datetime.min.time())
                end = datetime.combine(self._custom_end, datetime.max.time())
                return start, end
            # fallback to this month
            return self.get_date_range()

        # Default: this month
        return self.get_date_range()

    def save_selection(self) -> None:
        """حفظ الاختيار في ملف الإعدادات"""
        try:
            settings = {}
            if os.path.exists(self.SETTINGS_FILE):
                with open(self.SETTINGS_FILE, encoding='utf-8') as f:
                    settings = json.load(f)

            # تحديث إعدادات لوحة التحكم
            dashboard_settings = settings.get('dashboard', {})
            dashboard_settings['selected_period'] = self._current_period

            if self._current_period == "custom" and self._custom_start and self._custom_end:
                dashboard_settings['custom_start_date'] = self._custom_start.isoformat() if hasattr(self._custom_start, 'isoformat') else str(self._custom_start)
                dashboard_settings['custom_end_date'] = self._custom_end.isoformat() if hasattr(self._custom_end, 'isoformat') else str(self._custom_end)

            settings['dashboard'] = dashboard_settings

            with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)

        except Exception as e:
            safe_print(f"WARNING: [PeriodSelector] فشل حفظ الإعدادات: {e}")

    def load_selection(self) -> None:
        """تحميل الاختيار المحفوظ"""
        try:
            if not os.path.exists(self.SETTINGS_FILE):
                return

            with open(self.SETTINGS_FILE, encoding='utf-8') as f:
                settings = json.load(f)

            dashboard_settings = settings.get('dashboard', {})
            saved_period = dashboard_settings.get('selected_period', 'this_month')

            if saved_period in self.PERIODS:
                self._current_period = saved_period

                # تحديث الزر المحدد
                if saved_period in self.period_buttons:
                    self.period_buttons[saved_period].setChecked(True)

                # تحميل التواريخ المخصصة
                if saved_period == "custom":
                    self._toggle_custom_dates(True)

                    custom_start = dashboard_settings.get('custom_start_date')
                    custom_end = dashboard_settings.get('custom_end_date')

                    if custom_start:
                        try:
                            from datetime import date
                            if isinstance(custom_start, str):
                                self._custom_start = date.fromisoformat(custom_start)
                            self.date_from.setDate(QDate(self._custom_start.year, self._custom_start.month, self._custom_start.day))
                        except (ValueError, AttributeError):
                            pass

                    if custom_end:
                        try:
                            from datetime import date
                            if isinstance(custom_end, str):
                                self._custom_end = date.fromisoformat(custom_end)
                            self.date_to.setDate(QDate(self._custom_end.year, self._custom_end.month, self._custom_end.day))
                        except (ValueError, AttributeError):
                            pass

        except Exception as e:
            safe_print(f"WARNING: [PeriodSelector] فشل تحميل الإعدادات: {e}")

    def get_settings(self) -> DashboardSettings:
        """
        الحصول على إعدادات لوحة التحكم كـ DashboardSettings object

        Returns:
            DashboardSettings object
        """
        start_date, end_date = self.get_date_range()
        return DashboardSettings(
            selected_period=self._current_period,
            custom_start_date=start_date if self._current_period == "custom" else None,
            custom_end_date=end_date if self._current_period == "custom" else None
        )

    def set_period(self, period_key: str) -> None:
        """
        تعيين الفترة برمجياً

        Args:
            period_key: مفتاح الفترة (today, this_week, this_month, this_year, custom)
        """
        if period_key in self.period_buttons:
            self.period_buttons[period_key].setChecked(True)
            self._on_period_clicked(period_key)


class FlowLayout(QVBoxLayout):
    """
    Layout تلقائي يرتب العناصر حسب المساحة المتاحة
    يتحول من صف واحد لعدة صفوف تلقائياً
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._rows = []

    def addFlowWidget(self, widget):
        """إضافة widget للـ flow"""
        self._items.append(widget)


class DashboardTab(QWidget):
    """لوحة التحكم الرئيسية - تصميم تلقائي متجاوب 100%"""

    def __init__(self, accounting_service: AccountingService, parent=None):
        super().__init__(parent)
        self.accounting_service = accounting_service

        # ⚡ حماية من التحديث المتكرر
        self._last_refresh_time = 0
        self._is_refreshing = False
        self._MIN_REFRESH_INTERVAL = 5  # 5 ثواني بين كل تحديث

        # سياسة التمدد الكامل
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تفعيل الاتجاه من اليمين لليسار
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.init_ui()

    def init_ui(self):
        # === ScrollArea للتمرير عند الحاجة ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        # الـ widget الرئيسي داخل الـ scroll
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(content_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # === 1. العنوان مع زر التحديث ===
        header_layout = QHBoxLayout()

        header = QLabel("📊 لوحة القيادة والمؤشرات المالية")
        header.setFont(get_cairo_font(18, bold=True))
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
                font-family: 'Cairo';
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.refresh_btn.clicked.connect(self.refresh_data)

        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(self.refresh_btn)
        main_layout.addLayout(header_layout)

        # === 2. الكروت الإحصائية - Grid تلقائي ===
        self.cards_container = QWidget()
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setSpacing(12)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)

        self.card_sales = StatCard("إجمالي المبيعات", "0.00 EGP", "💼", "#3b82f6")
        self.card_collected = StatCard("النقدية المحصلة", "0.00 EGP", "💰", "#10b981")
        self.card_receivables = StatCard("مستحقات آجلة", "0.00 EGP", "📝", "#f59e0b")
        self.card_expenses = StatCard("المصروفات", "0.00 EGP", "💸", "#ef4444")

        self.stat_cards = [self.card_sales, self.card_collected, self.card_receivables, self.card_expenses]

        # ترتيب أولي (سيتم تحديثه في resizeEvent)
        for i, card in enumerate(self.stat_cards):
            self.cards_grid.addWidget(card, 0, i)

        main_layout.addWidget(self.cards_container)

        # === 3. القسم السفلي - Splitter للتحكم التلقائي ===
        self.bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.bottom_splitter.setChildrenCollapsible(False)
        self.bottom_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #334155;
                width: 3px;
                margin: 0 5px;
            }
        """)

        # أ) الرسم البياني
        self.chart_container = QFrame()
        self.chart_container.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 15px;
                border: 1px solid #334155;
            }
        """)
        chart_layout = QVBoxLayout(self.chart_container)
        chart_layout.setContentsMargins(15, 15, 15, 15)

        lbl_chart = QLabel("📈 الملخص المالي")
        lbl_chart.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 14px;
            border: none;
            background: transparent;
            font-family: 'Cairo';
        """)
        chart_layout.addWidget(lbl_chart)

        self.chart = FinancialChart(self)
        self.chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart_layout.addWidget(self.chart)

        # ب) جدول آخر العمليات
        self.table_container = QFrame()
        self.table_container.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 15px;
                border: 1px solid #334155;
            }
        """)
        table_layout = QVBoxLayout(self.table_container)
        table_layout.setContentsMargins(15, 15, 15, 15)

        lbl_table = QLabel("📝 آخر العمليات المسجلة")
        lbl_table.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 14px;
            border: none;
            background: transparent;
            font-family: 'Cairo';
        """)
        table_layout.addWidget(lbl_table)

        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(3)
        self.recent_table.setHorizontalHeaderLabels(["التاريخ", "الوصف", "المبلغ"])
        header = self.recent_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.recent_table.verticalHeader().setVisible(False)
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.recent_table)
        self.recent_table.setStyleSheet(TABLE_STYLE_DARK)
        self.recent_table.verticalHeader().setDefaultSectionSize(32)
        table_layout.addWidget(self.recent_table)

        # إضافة للـ splitter
        self.bottom_splitter.addWidget(self.chart_container)
        self.bottom_splitter.addWidget(self.table_container)
        self.bottom_splitter.setStretchFactor(0, 3)
        self.bottom_splitter.setStretchFactor(1, 2)

        main_layout.addWidget(self.bottom_splitter, 1)

        scroll.setWidget(content_widget)

        # Layout الرئيسي للـ widget
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

    def resizeEvent(self, event):
        """إعادة ترتيب الكروت تلقائياً حسب العرض"""
        super().resizeEvent(event)
        self._rearrange_cards()
        self._rearrange_bottom_section()

    def _rearrange_cards(self):
        """ترتيب الكروت تلقائياً حسب المساحة المتاحة"""
        width = self.width()

        # حساب عدد الأعمدة المناسب
        if width < 500:
            cols = 1
        elif width < 800:
            cols = 2
        else:
            cols = 4

        # إعادة ترتيب الكروت
        for i, card in enumerate(self.stat_cards):
            row = i // cols
            col = i % cols
            self.cards_grid.addWidget(card, row, col)

    def _rearrange_bottom_section(self):
        """تغيير اتجاه القسم السفلي حسب العرض"""
        width = self.width()

        if width < 700:
            self.bottom_splitter.setOrientation(Qt.Orientation.Vertical)
        else:
            self.bottom_splitter.setOrientation(Qt.Orientation.Horizontal)

    def refresh_data(self):
        """تحديث البيانات من المصدر الموحد (مع حماية من التحديث المتكرر)"""
        import time

        # ⚡ حماية من التحديث المتكرر
        current_time = time.time()
        if self._is_refreshing:
            safe_print("WARNING: [Dashboard] ⏳ تحديث جاري بالفعل - تم تجاهل الطلب")
            return
        if (current_time - self._last_refresh_time) < self._MIN_REFRESH_INTERVAL:
            safe_print("WARNING: [Dashboard] ⏳ تحديث متكرر سريع - تم تجاهل الطلب")
            return

        self._is_refreshing = True
        self._last_refresh_time = current_time
        safe_print("INFO: [Dashboard] جاري تحديث أرقام الداشبورد...")

        from core.data_loader import get_data_loader

        def fetch_data():
            try:
                # استخدام الدالة الموحدة الجديدة
                stats = self.accounting_service.get_dashboard_stats()
                recent = self.accounting_service.get_recent_journal_entries(8)
                return {'stats': stats, 'recent': recent}
            except Exception as e:
                safe_print(f"ERROR: [Dashboard] فشل جلب البيانات: {e}")
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

                    self.recent_table.setItem(i, 0, create_centered_item(date_val))
                    self.recent_table.setItem(i, 1, create_centered_item(desc_val))
                    self.recent_table.setItem(i, 2, create_centered_item(f"{amount_val:,.2f}"))

                safe_print("INFO: [Dashboard] ✅ تم تحديث الداشبورد بنجاح")
            except Exception as e:
                safe_print(f"ERROR: [Dashboard] فشل تحديث الواجهة: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self._is_refreshing = False

        def on_error(error_msg):
            safe_print(f"ERROR: [Dashboard] {error_msg}")
            self._is_refreshing = False

        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="dashboard_data",
            load_function=fetch_data,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True
        )
