# الملف: ui/dashboard_tab.py
"""
لوحة التحكم الاحترافية - الحل النهائي
مصدر بيانات موحد + دعم كامل للعربية
"""

import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from PyQt6.QtCore import QDate, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.dashboard_models import DashboardSettings, KPIData
from core.signals import app_signals
from ui.styles import TABLE_STYLE_DARK, create_centered_item, get_cairo_font

if TYPE_CHECKING:
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


DASHBOARD_ENABLE_SOFT_SHADOWS = (
    os.environ.get("SKYWAVE_ENABLE_DASHBOARD_SHADOWS", "").strip() == "1"
)
_PLOTTING_BACKEND: tuple[object | None, object | None] | None = None
_ARABIC_TEXT_SUPPORT: tuple[object | None, object | None] | None = None


def _get_plotting_backend() -> tuple[object | None, object | None]:
    global _PLOTTING_BACKEND
    if _PLOTTING_BACKEND is None:
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as figure_canvas
            from matplotlib.figure import Figure as figure_class

            _PLOTTING_BACKEND = (figure_canvas, figure_class)
        except ImportError:
            _PLOTTING_BACKEND = (None, None)
    return _PLOTTING_BACKEND


def _get_arabic_text_support() -> tuple[object | None, object | None]:
    global _ARABIC_TEXT_SUPPORT
    if _ARABIC_TEXT_SUPPORT is None:
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display

            _ARABIC_TEXT_SUPPORT = (arabic_reshaper, get_display)
        except ImportError:
            _ARABIC_TEXT_SUPPORT = (None, None)
    return _ARABIC_TEXT_SUPPORT


def fix_text(text: str) -> str:
    """دالة لإصلاح النص العربي في الرسوم البيانية"""
    if not text:
        return ""
    arabic_reshaper, get_display = _get_arabic_text_support()
    if arabic_reshaper is None or get_display is None:
        return text
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)
    except Exception:
        return text


def rgba_css(color_hex: str, alpha: int) -> str:
    """تحويل hex color إلى rgba صالح للـ Qt stylesheets."""
    color = QColor(color_hex)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"


class StatCard(QFrame):
    """تصميم الكارت الاحترافي - متجاوب مع الشاشة"""

    def __init__(self, title: str, value: str, icon: str, color_hex: str):
        super().__init__()
        self.color_hex = color_hex
        self.setFrameShape(QFrame.Shape.StyledPanel)

        # 📱 تجاوب: حد أدنى وأقصى للحجم
        self.setMinimumHeight(76)
        self.setMinimumWidth(168)
        self.setMaximumHeight(84)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        icon_bg = rgba_css(color_hex, 28)
        icon_border = rgba_css(color_hex, 70)
        value_glow = rgba_css(color_hex, 18)

        self.setStyleSheet(
            f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #16253b, stop:0.55 #1b2b43, stop:1 #1d314a);
                border-radius: 20px;
                border: 1px solid rgba(203, 213, 225, 0.08);
                border-right: 5px solid {color_hex};
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
            QLabel#Title {{
                color: #9fb3ce;
                font-size: 11px;
                font-weight: 700;
                font-family: 'Cairo';
            }}
            QLabel#Value {{
                color: white;
                font-weight: bold;
                font-size: 17px;
                font-family: 'Cairo';
                padding: 1px 0;
            }}
            QLabel#Icon {{
                font-size: 19px;
                min-width: 38px;
                max-width: 38px;
                min-height: 38px;
                max-height: 38px;
                border-radius: 11px;
                background-color: {icon_bg};
                border: 1px solid {icon_border};
                padding: 3px;
            }}
            QLabel#ValueBadge {{
                color: rgba(255, 255, 255, 0.78);
                font-size: 10px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 999px;
                background-color: {value_glow};
                border: 1px solid rgba(255,255,255,0.06);
            }}
        """
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        # النصوص (يمين)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)

        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("Title")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.lbl_value = QLabel(value)
        self.lbl_value.setObjectName("Value")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.lbl_badge = QLabel("مؤشر مباشر")
        self.lbl_badge.setObjectName("ValueBadge")
        self.lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_badge.hide()

        text_layout.addWidget(self.lbl_title)
        text_layout.addWidget(self.lbl_value)
        text_layout.addWidget(self.lbl_badge, alignment=Qt.AlignmentFlag.AlignRight)

        # الأيقونة (يسار)
        lbl_icon = QLabel(icon)
        lbl_icon.setObjectName("Icon")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addWidget(lbl_icon)
        self.setLayout(layout)

        if DASHBOARD_ENABLE_SOFT_SHADOWS:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(28)
            shadow.setOffset(0, 10)
            shadow.setColor(QColor(2, 12, 27, 120))
            self.setGraphicsEffect(shadow)

    def set_value(self, value: float):
        """تحديث قيمة الكارت"""
        self.lbl_value.setText(f"{value:,.2f} EGP")


class EnhancedKPICard(QFrame):
    """
    بطاقة KPI محسّنة مع مؤشر الاتجاه
    تعرض القيمة الحالية مع نسبة التغير واتجاه التغير (سهم أخضر/أحمر)

    Requirements: 1.1, 1.4, 1.5, 1.6, 1.7
    """

    def __init__(self, title: str, icon: str, color_hex: str, parent: QWidget = None):
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
        self.setStyleSheet(
            f"""
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
        """
        )

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
            name=self.title, current_value=self._current_value, previous_value=self._previous_value
        )

    @property
    def current_value(self) -> float:
        """القيمة الحالية"""
        return self._current_value

    @property
    def previous_value(self) -> float | None:
        """القيمة السابقة"""
        return self._previous_value


class _LazyMatplotlibChart(QWidget):
    """غلاف QWidget يهيئ matplotlib فقط عند أول رسم فعلي."""

    def __init__(self, parent=None, width: int = 5, height: int = 4, dpi: int = 100):
        super().__init__(parent)
        self._chart_width = width
        self._chart_height = height
        self._chart_dpi = dpi
        self.fig = None
        self.axes = None
        self._canvas = None
        self.setMinimumSize(width * 80, height * 80)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

    def _ensure_canvas(self) -> bool:
        if self._canvas is not None:
            return True

        figure_canvas_class, figure_class = _get_plotting_backend()
        if figure_canvas_class is None or figure_class is None:
            return False

        self.fig = figure_class(
            figsize=(self._chart_width, self._chart_height),
            dpi=self._chart_dpi,
        )
        self.axes = self.fig.add_subplot(111)
        self.fig.patch.set_facecolor("#1e293b")
        self._canvas = figure_canvas_class(self.fig)
        self._layout.addWidget(self._canvas)
        return True

    def _draw_canvas(self) -> None:
        if self.fig is None or self._canvas is None:
            return
        self.fig.tight_layout(pad=1.5)
        self._canvas.draw()


class FinancialChart(_LazyMatplotlibChart):
    """رسم بياني يدعم العربية بالكامل"""

    def __init__(self, parent=None, width: int = 5, height: int = 4, dpi: int = 100):
        super().__init__(parent, width=width, height=height, dpi=dpi)

    def plot_data(self, sales: float, expenses: float, profit: float):
        """رسم البيانات مع دعم العربية"""
        if not self._ensure_canvas():
            return

        self.axes.clear()

        # البيانات مع إصلاح النص العربي
        categories = [fix_text("المبيعات"), fix_text("المصروفات"), fix_text("صافي الربح")]
        values = [sales, expenses, profit]
        colors = ["#3b82f6", "#ef4444", "#10b981"]  # أزرق، أحمر، أخضر

        # الرسم
        bars = self.axes.bar(categories, values, color=colors, width=0.5)

        # تنسيق المحاور والألوان (Dark Mode)
        self.axes.set_facecolor("#1e293b")
        self.axes.tick_params(axis="x", colors="white", labelsize=11)
        self.axes.tick_params(axis="y", colors="white", labelsize=10)
        self.axes.spines["bottom"].set_color("#475569")
        self.axes.spines["left"].set_color("#475569")
        self.axes.spines["top"].set_visible(False)
        self.axes.spines["right"].set_visible(False)

        # خطوط الشبكة
        self.axes.grid(axis="y", linestyle="--", alpha=0.2, color="#475569")
        self.axes.set_axisbelow(True)

        # زيادة سقف الرسم
        if values and max(values) > 0:
            self.axes.set_ylim(0, max(values) * 1.25)

        # إضافة القيم فوق الأعمدة
        for bar_rect in bars:
            height = bar_rect.get_height()
            self.axes.text(
                bar_rect.get_x() + bar_rect.get_width() / 2.0,
                height,
                f"{height:,.0f}",
                ha="center",
                va="bottom",
                color="white",
                fontweight="bold",
                fontsize=10,
            )

        self._draw_canvas()


class CashFlowChart(_LazyMatplotlibChart):
    """
    مخطط التدفق النقدي
    يعرض التدفقات الداخلة (أخضر) والخارجة (أحمر) وصافي التدفق عبر الزمن

    Requirements: 2.1, 2.4, 2.5, 2.7
    """

    def __init__(self, parent: QWidget = None, width: int = 6, height: int = 4, dpi: int = 100):
        super().__init__(parent, width=width, height=height, dpi=dpi)

        # ألوان المخطط
        self.inflow_color = "#10b981"  # أخضر للدفعات الداخلة
        self.outflow_color = "#ef4444"  # أحمر للمصروفات
        self.net_color = "#3b82f6"  # أزرق لصافي التدفق

    def plot_cash_flow(
        self,
        inflows: list[tuple[str, float]],
        outflows: list[tuple[str, float]],
        period: str = "monthly",
    ) -> None:
        """
        رسم مخطط التدفق النقدي

        Args:
            inflows: قائمة الدفعات الداخلة (التاريخ، المبلغ)
            outflows: قائمة المصروفات (التاريخ، المبلغ)
            period: الفترة الزمنية للتجميع ("daily", "weekly", "monthly")

        Requirements: 2.1, 2.4, 2.5, 2.7
        """
        if not self._ensure_canvas():
            return

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
        net_values = [
            aggregated_inflows.get(p, 0.0) - aggregated_outflows.get(p, 0.0) for p in all_periods
        ]

        # إصلاح النصوص العربية للتسميات
        x_labels = [fix_text(self._format_period_label(p, period)) for p in all_periods]
        x_positions = range(len(all_periods))

        # رسم الخطوط
        self.axes.plot(
            x_positions,
            inflow_values,
            color=self.inflow_color,
            marker="o",
            linewidth=2,
            label=fix_text("الدفعات الداخلة"),
            markersize=6,
        )
        self.axes.plot(
            x_positions,
            outflow_values,
            color=self.outflow_color,
            marker="s",
            linewidth=2,
            label=fix_text("المصروفات"),
            markersize=6,
        )
        self.axes.plot(
            x_positions,
            net_values,
            color=self.net_color,
            marker="^",
            linewidth=2,
            linestyle="--",
            label=fix_text("صافي التدفق"),
            markersize=6,
        )

        # تنسيق المحاور
        self._style_axes(x_positions, x_labels)

        # إضافة الأسطورة
        self.axes.legend(
            loc="upper left",
            facecolor="#1e293b",
            edgecolor="#475569",
            labelcolor="white",
            fontsize=9,
        )

        self._draw_canvas()

    def _aggregate_by_period(self, data: list[tuple[str, float]], period: str) -> dict[str, float]:
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
                parts = period_key.split("-")
                return f"{parts[2]}/{parts[1]}"
            except (IndexError, ValueError):
                return period_key
        elif period_type == "weekly":
            # YYYY-WXX -> أسبوع XX
            try:
                week_num = period_key.split("-W")[1]
                return f"أسبوع {week_num}"
            except (IndexError, ValueError):
                return period_key
        else:  # monthly
            # YYYY-MM -> MM/YYYY
            try:
                parts = period_key.split("-")
                months_ar = [
                    "يناير",
                    "فبراير",
                    "مارس",
                    "أبريل",
                    "مايو",
                    "يونيو",
                    "يوليو",
                    "أغسطس",
                    "سبتمبر",
                    "أكتوبر",
                    "نوفمبر",
                    "ديسمبر",
                ]
                month_idx = int(parts[1]) - 1
                if 0 <= month_idx < 12:
                    return months_ar[month_idx]
                return f"{parts[1]}/{parts[0]}"
            except (IndexError, ValueError):
                return period_key

    def _style_axes(self, x_positions, x_labels):
        """تنسيق المحاور والألوان"""
        self.axes.set_facecolor("#1e293b")
        self.axes.tick_params(axis="x", colors="white", labelsize=9, rotation=45)
        self.axes.tick_params(axis="y", colors="white", labelsize=10)
        self.axes.spines["bottom"].set_color("#475569")
        self.axes.spines["left"].set_color("#475569")
        self.axes.spines["top"].set_visible(False)
        self.axes.spines["right"].set_visible(False)

        # تسميات المحور X
        self.axes.set_xticks(list(x_positions))
        self.axes.set_xticklabels(x_labels, ha="right")

        # خطوط الشبكة
        self.axes.grid(axis="y", linestyle="--", alpha=0.2, color="#475569")
        self.axes.set_axisbelow(True)

        # خط الصفر
        self.axes.axhline(y=0, color="#475569", linestyle="-", linewidth=0.5)

    def _draw_empty_chart(self):
        """رسم مخطط فارغ عند عدم وجود بيانات"""
        if not self._ensure_canvas():
            return
        self.axes.set_facecolor("#1e293b")
        self.axes.text(
            0.5,
            0.5,
            fix_text("لا توجد بيانات"),
            ha="center",
            va="center",
            color="#94a3b8",
            fontsize=14,
            transform=self.axes.transAxes,
        )
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        for spine in self.axes.spines.values():
            spine.set_visible(False)
        self._draw_canvas()


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
        "custom": "فترة مخصصة",
    }

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._current_period = "this_month"
        self._custom_start = None
        self._custom_end = None
        data_dir = os.environ.get("SKYWAVEERP_DATA_DIR") or os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "SkyWaveERP",
        )
        os.makedirs(data_dir, exist_ok=True)
        self.settings_file = os.path.join(data_dir, "skywave_settings.json")
        if not os.path.exists(self.settings_file):
            legacy_paths = [os.path.join(os.getcwd(), "skywave_settings.json")]
            if getattr(sys, "frozen", False):
                legacy_paths.append(
                    os.path.join(os.path.dirname(sys.executable), "skywave_settings.json")
                )
            else:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                legacy_paths.append(os.path.join(project_root, "skywave_settings.json"))
            for legacy in legacy_paths:
                if (
                    legacy
                    and os.path.exists(legacy)
                    and os.path.abspath(legacy) != os.path.abspath(self.settings_file)
                ):
                    try:
                        shutil.copy2(legacy, self.settings_file)
                        break
                    except Exception as exc:
                        safe_print(
                            f"WARNING: [Dashboard] تعذر نسخ ملف الإعدادات القديم إلى AppData: {exc}"
                        )

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            """
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
        """
        )

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
                if start > end:
                    start, end = end, start
                return start, end
            start = today.replace(day=1)
            if today.month == 12:
                end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(seconds=1)
            else:
                end = today.replace(month=today.month + 1, day=1) - timedelta(seconds=1)
            return start, end

        # Default: this month
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(seconds=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(seconds=1)
        return start, end

    def save_selection(self) -> None:
        """حفظ الاختيار في ملف الإعدادات"""
        try:
            settings = {}
            if os.path.exists(self.settings_file):
                with open(self.settings_file, encoding="utf-8") as f:
                    settings = json.load(f)

            # تحديث إعدادات لوحة التحكم
            dashboard_settings = settings.get("dashboard", {})
            dashboard_settings["selected_period"] = self._current_period

            if self._current_period == "custom" and self._custom_start and self._custom_end:
                dashboard_settings["custom_start_date"] = (
                    self._custom_start.isoformat()
                    if hasattr(self._custom_start, "isoformat")
                    else str(self._custom_start)
                )
                dashboard_settings["custom_end_date"] = (
                    self._custom_end.isoformat()
                    if hasattr(self._custom_end, "isoformat")
                    else str(self._custom_end)
                )

            settings["dashboard"] = dashboard_settings

            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)

        except Exception as e:
            safe_print(f"WARNING: [PeriodSelector] فشل حفظ الإعدادات: {e}")

    def load_selection(self) -> None:
        """تحميل الاختيار المحفوظ"""
        try:
            if not os.path.exists(self.settings_file):
                return

            with open(self.settings_file, encoding="utf-8") as f:
                settings = json.load(f)

            dashboard_settings = settings.get("dashboard", {})
            saved_period = dashboard_settings.get("selected_period", "this_month")

            if saved_period in self.PERIODS:
                self._current_period = saved_period

                # تحديث الزر المحدد
                if saved_period in self.period_buttons:
                    self.period_buttons[saved_period].setChecked(True)

                # تحميل التواريخ المخصصة
                if saved_period == "custom":
                    self._toggle_custom_dates(True)

                    custom_start = dashboard_settings.get("custom_start_date")
                    custom_end = dashboard_settings.get("custom_end_date")

                    if custom_start:
                        try:
                            from datetime import date

                            if isinstance(custom_start, str):
                                self._custom_start = date.fromisoformat(custom_start)
                            self.date_from.setDate(
                                QDate(
                                    self._custom_start.year,
                                    self._custom_start.month,
                                    self._custom_start.day,
                                )
                            )
                        except (ValueError, AttributeError):
                            pass

                    if custom_end:
                        try:
                            from datetime import date

                            if isinstance(custom_end, str):
                                self._custom_end = date.fromisoformat(custom_end)
                            self.date_to.setDate(
                                QDate(
                                    self._custom_end.year,
                                    self._custom_end.month,
                                    self._custom_end.day,
                                )
                            )
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
            custom_end_date=end_date if self._current_period == "custom" else None,
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

    def add_flow_widget(self, widget):
        """إضافة widget للـ flow"""
        self._items.append(widget)


class DashboardTab(QWidget):
    """لوحة التحكم الرئيسية - تصميم تلقائي متجاوب 100%"""

    def __init__(self, accounting_service: "AccountingService", parent=None):
        super().__init__(parent)
        self.accounting_service = accounting_service

        # ⚡ حماية من التحديث المتكرر
        self._last_refresh_time = 0
        self._is_refreshing = False
        self._is_refreshing_recent_activity = False
        self._min_refresh_interval = 5  # 5 ثواني بين كل تحديث
        self._recent_current_page = 1
        self._recent_page_size = 10
        self._recent_items: list = []
        self._show_recent_activity = True
        self._load_recent_activity_data = True
        self.chart: FinancialChart | None = None
        self.chart_placeholder: QLabel | None = None
        self._last_chart_signature: tuple[float, float, float] | None = None
        self.bottom_splitter: QSplitter | None = None
        self.chart_container: QFrame | None = None
        self.table_container: QFrame | None = None
        self.recent_hint_lbl: QLabel | None = None
        self.recent_table: QTableWidget | None = None
        self.recent_pagination_widget: QWidget | None = None
        self.recent_prev_button: QPushButton | None = None
        self.recent_next_button: QPushButton | None = None
        self.recent_page_size_combo: QComboBox | None = None
        self.recent_page_info_label: QLabel | None = None
        self.recent_pagination_size_label: QLabel | None = None
        self._bottom_section_ready = False
        self._bottom_section_pending = False

        # سياسة التمدد الكامل
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تفعيل الاتجاه من اليمين لليسار
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.init_ui()
        app_signals.safe_connect(
            app_signals.notifications_changed, self._refresh_recent_activity_from_signal
        )

    @staticmethod
    def _normalize_display_datetime(value: datetime | None) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value
        try:
            return value.astimezone().replace(tzinfo=None)
        except Exception:
            return value.replace(tzinfo=None)

    @staticmethod
    def _format_twelve_hour_time(value: datetime | None) -> str:
        value = DashboardTab._normalize_display_datetime(value)
        if not isinstance(value, datetime):
            return "—"
        hour_text = value.strftime("%I").lstrip("0") or "12"
        minute_text = value.strftime("%M")
        meridiem = "ص" if value.hour < 12 else "م"
        return f"{hour_text}:{minute_text} {meridiem}"

    @classmethod
    def _format_datetime_badge(cls, value: datetime | None, prefix: str) -> str:
        value = cls._normalize_display_datetime(value)
        if not isinstance(value, datetime):
            return f"{prefix}: —"
        return f"{prefix}: {value.strftime('%d-%m-%Y')} • {cls._format_twelve_hour_time(value)}"

    @classmethod
    def _format_recent_timestamp(cls, value) -> str:
        value = cls._normalize_display_datetime(value)
        if isinstance(value, datetime):
            return f"{value.strftime('%d-%m-%Y')} • {cls._format_twelve_hour_time(value)}"
        return str(value or "—")

    @staticmethod
    def _apply_soft_shadow(widget: QWidget, *, blur: int = 34, y_offset: int = 10) -> None:
        if not DASHBOARD_ENABLE_SOFT_SHADOWS:
            return
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(blur)
        shadow.setOffset(0, y_offset)
        shadow.setColor(QColor(2, 12, 27, 110))
        widget.setGraphicsEffect(shadow)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 8)

        # === 1. الهيدر الرئيسي ===
        hero_frame = QFrame()
        self.hero_frame = hero_frame
        hero_frame.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #132b49, stop:0.48 #17375a, stop:1 #1d4268);
                border-radius: 26px;
                border: 1px solid rgba(191, 219, 254, 0.11);
            }
            QLabel {
                background: transparent;
                border: none;
                font-family: 'Cairo';
            }
            QLabel#DashEyebrow {
                color: #7dd3fc;
                font-size: 10px;
                font-weight: 800;
            }
            QLabel#DashTitle {
                color: #f8fbff;
                font-size: 20px;
                font-weight: 800;
            }
            QLabel#DashSubtitle {
                color: #bfd0e7;
                font-size: 10px;
            }
            QFrame#DashControlBox {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            """
        )
        self._apply_soft_shadow(hero_frame, blur=38, y_offset=12)
        hero_frame.setMinimumHeight(98)
        hero_frame.setMaximumHeight(104)
        hero_layout = QHBoxLayout(hero_frame)
        hero_layout.setContentsMargins(18, 12, 18, 12)
        hero_layout.setSpacing(14)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(1)

        self.header_eyebrow = QLabel("لوحة التحكم التنفيذية")
        self.header_eyebrow.setObjectName("DashEyebrow")

        header = QLabel("📊 لوحة القيادة والمؤشرات المالية")
        header.setObjectName("DashTitle")
        header.setFont(get_cairo_font(18, bold=True))

        header_subtitle = QLabel(
            "عرض تنفيذي موحد لأهم المؤشرات مع آخر تحديث مباشر من نفس مصدر البيانات."
        )
        header_subtitle.setObjectName("DashSubtitle")
        header_subtitle.setWordWrap(False)

        title_layout.addWidget(self.header_eyebrow)
        title_layout.addWidget(header)
        title_layout.addWidget(header_subtitle)

        control_box = QFrame()
        self.control_box = control_box
        control_box.setObjectName("DashControlBox")
        control_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        control_box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        control_layout = QHBoxLayout(control_box)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(10)

        self.refresh_btn = QPushButton("🔄 تحديث")
        self.refresh_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2f6eea, stop:1 #4b8cf6);
                color: white;
                padding: 0 18px;
                font-weight: 800;
                border-radius: 14px;
                border: 1px solid rgba(191, 219, 254, 0.16);
                font-size: 12px;
                font-family: 'Cairo';
                min-width: 110px;
                min-height: 46px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a7af5, stop:1 #5a98ff);
                border: 1px solid rgba(191, 219, 254, 0.22);
            }
            QPushButton:pressed {
                background: #245fd1;
            }
            QPushButton:disabled {
                background: #334155;
                color: #cbd5e1;
                border: 1px solid rgba(148, 163, 184, 0.10);
            }
        """
        )
        self.refresh_btn.setFixedHeight(48)
        self.refresh_btn.clicked.connect(self.refresh_data)

        self.last_update_lbl = QLabel(self._format_datetime_badge(None, "آخر تحديث"))
        self.last_update_lbl.setStyleSheet(
            """
            color: #e2ecff;
            background-color: rgba(20, 41, 70, 0.74);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 14px;
            padding: 0 14px;
            font-size: 10px;
            font-weight: 700;
            font-family: 'Cairo';
        """
        )
        self.last_update_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.last_update_lbl.setFixedHeight(48)
        self.last_update_lbl.setMinimumWidth(188)
        self.last_update_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        control_layout.addWidget(self.last_update_lbl)
        control_layout.addWidget(self.refresh_btn)

        hero_layout.addLayout(title_layout, 1)
        hero_layout.addWidget(control_box, 0, Qt.AlignmentFlag.AlignVCenter)
        main_layout.addWidget(hero_frame)

        # === 2. الكروت الإحصائية - Grid تلقائي ===
        self.cards_container = QWidget()
        self.cards_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setSpacing(10)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)

        self.card_sales = StatCard("إجمالي المبيعات", "0.00 EGP", "💼", "#3b82f6")
        self.card_collected = StatCard("النقدية المحصلة", "0.00 EGP", "💰", "#10b981")
        self.card_receivables = StatCard("مستحقات آجلة", "0.00 EGP", "📝", "#f59e0b")
        self.card_expenses = StatCard("المصروفات", "0.00 EGP", "💸", "#ef4444")
        self.card_net_profit = StatCard("صافي الربح", "0.00 EGP", "📈", "#22c55e")

        self.stat_cards = [
            self.card_sales,
            self.card_collected,
            self.card_receivables,
            self.card_expenses,
            self.card_net_profit,
        ]

        # ترتيب أولي (سيتم تحديثه في resizeEvent)
        for i, card in enumerate(self.stat_cards):
            self.cards_grid.addWidget(card, 0, i)

        main_layout.addWidget(self.cards_container)

        # === 3. القسم السفلي - lazy حتى أول ظهور فعلي ===
        self.bottom_section_host = QWidget()
        self.bottom_section_host_layout = QVBoxLayout(self.bottom_section_host)
        self.bottom_section_host_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_section_host_layout.setSpacing(0)
        self.bottom_section_placeholder = QLabel("جاري تجهيز الملخص المالي وسجل العمليات…")
        self.bottom_section_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bottom_section_placeholder.setStyleSheet(
            """
            color: #9fb3ce;
            font-size: 11px;
            font-family: 'Cairo';
            background: rgba(12, 25, 47, 0.22);
            border: 1px dashed rgba(148, 163, 184, 0.14);
            border-radius: 16px;
            padding: 18px;
            """
        )
        self.bottom_section_host_layout.addWidget(self.bottom_section_placeholder, 1)
        main_layout.addWidget(self.bottom_section_host, 1)
        self._rearrange_cards()

    def resizeEvent(self, event):
        """إعادة ترتيب الكروت تلقائياً حسب العرض"""
        super().resizeEvent(event)
        self._rearrange_cards()
        self._rearrange_bottom_section()

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_bottom_section_build()

    def _schedule_bottom_section_build(self) -> None:
        if self._bottom_section_ready or self._bottom_section_pending:
            return
        self._bottom_section_pending = True
        QTimer.singleShot(0, self._ensure_bottom_section)

    def _ensure_bottom_section(self) -> None:
        if self._bottom_section_ready:
            return
        self._bottom_section_pending = False
        if not hasattr(self, "bottom_section_host_layout"):
            return

        self.bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.bottom_splitter.setChildrenCollapsible(False)
        self.bottom_splitter.setHandleWidth(8)
        self.bottom_splitter.setStyleSheet(
            """
            QSplitter::handle {
                background-color: transparent;
                width: 8px;
                margin: 0 1px;
            }
            QSplitter::handle:horizontal {
                image: none;
                border-left: 1px solid rgba(148, 163, 184, 0.12);
                border-right: 1px solid rgba(15, 23, 42, 0.25);
            }
            QSplitter::handle:vertical {
                image: none;
                border-top: 1px solid rgba(148, 163, 184, 0.12);
                border-bottom: 1px solid rgba(15, 23, 42, 0.25);
            }
        """
        )

        self._build_chart_panel()
        self._build_recent_activity_panel()

        self.bottom_splitter.addWidget(self.chart_container)
        if self._show_recent_activity:
            self.bottom_splitter.addWidget(self.table_container)
            self.bottom_splitter.setStretchFactor(0, 3)
            self.bottom_splitter.setStretchFactor(1, 2)
        else:
            self.table_container.hide()
            self.bottom_splitter.setStretchFactor(0, 1)

        if getattr(self, "bottom_section_placeholder", None) is not None:
            self.bottom_section_placeholder.deleteLater()
            self.bottom_section_placeholder = None
        self.bottom_section_host_layout.addWidget(self.bottom_splitter, 1)
        self._bottom_section_ready = True
        self._rearrange_bottom_section()
        self._update_recent_controls(self._get_recent_total_pages())

    def _build_chart_panel(self) -> None:
        self.chart_container = QFrame()
        self.chart_container.setStyleSheet(
            f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #18273d, stop:0.6 #1d2d45, stop:1 #1f334f);
                border-radius: 20px;
                border: 1px solid rgba(148, 163, 184, 0.10);
                border-top: 3px solid {rgba_css("#60a5fa", 190)};
            }}
        """
        )
        self._apply_soft_shadow(self.chart_container)
        self.chart_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.chart_container.setMinimumHeight(250)
        chart_layout = QVBoxLayout(self.chart_container)
        chart_layout.setContentsMargins(12, 10, 12, 12)
        chart_layout.setSpacing(6)

        chart_header = QHBoxLayout()
        chart_header.setSpacing(8)

        lbl_chart = QLabel("📈 الملخص المالي")
        lbl_chart.setStyleSheet(
            """
            color: white;
            font-weight: 800;
            font-size: 14px;
            border: none;
            background: transparent;
            font-family: 'Cairo';
        """
        )
        lbl_chart_meta = QLabel("قراءة سريعة لأداء الفترة الحالية")
        lbl_chart_meta.setStyleSheet(
            """
            color: #9fb3ce;
            font-size: 10px;
            font-family: 'Cairo';
            background: transparent;
        """
        )
        chart_header.addWidget(lbl_chart)
        chart_header.addStretch(1)
        chart_header.addWidget(lbl_chart_meta)
        chart_layout.addLayout(chart_header)

        self.chart_content_layout = chart_layout
        self.chart_placeholder = QLabel("سيظهر الرسم البياني بعد أول تحديث للداشبورد.")
        self.chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_placeholder.setWordWrap(True)
        self.chart_placeholder.setStyleSheet(
            """
            color: #9fb3ce;
            font-size: 11px;
            font-family: 'Cairo';
            background: rgba(12, 25, 47, 0.28);
            border: 1px dashed rgba(148, 163, 184, 0.16);
            border-radius: 14px;
            padding: 18px;
            """
        )
        chart_layout.addWidget(self.chart_placeholder, 1)

    def _build_recent_activity_panel(self) -> None:
        self.table_container = QFrame()
        self.table_container.setStyleSheet(
            f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #18273d, stop:0.6 #1d2d45, stop:1 #1f334f);
                border-radius: 20px;
                border: 1px solid rgba(148, 163, 184, 0.10);
                border-top: 3px solid {rgba_css("#22c55e", 190)};
            }}
        """
        )
        self._apply_soft_shadow(self.table_container)
        self.table_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.table_container.setMinimumHeight(250)
        table_layout = QVBoxLayout(self.table_container)
        table_layout.setContentsMargins(12, 10, 12, 12)
        table_layout.setSpacing(6)

        table_header = QHBoxLayout()
        table_header.setSpacing(8)

        lbl_table = QLabel("📝 آخر العمليات المسجلة")
        lbl_table.setStyleSheet(
            """
            color: white;
            font-weight: 800;
            font-size: 14px;
            border: none;
            background: transparent;
            font-family: 'Cairo';
        """
        )
        table_meta = QLabel("سجل موثق لأحدث ما تم داخل النظام")
        table_meta.setStyleSheet(
            """
            color: #9fb3ce;
            font-size: 10px;
            font-family: 'Cairo';
            background: transparent;
        """
        )
        table_header.addWidget(lbl_table)
        table_header.addStretch(1)
        table_header.addWidget(table_meta)
        table_layout.addLayout(table_header)

        self.recent_hint_lbl = QLabel(
            "يعرض أحدث العمليات الموثقة من جميع الأقسام مثل العملاء والمشاريع والفواتير والدفعات والمصروفات، مع فولباك آمن للبيانات القديمة عند الحاجة."
        )
        self.recent_hint_lbl.setStyleSheet(
            """
            color: #9fb3ce;
            font-size: 10px;
            font-family: 'Cairo';
            padding: 8px 10px;
            border-radius: 12px;
            background-color: rgba(12, 25, 47, 0.34);
            border: 1px solid rgba(148, 163, 184, 0.10);
            """
        )
        self.recent_hint_lbl.setWordWrap(True)
        table_layout.addWidget(self.recent_hint_lbl)

        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(4)
        self.recent_table.setHorizontalHeaderLabels(["التوقيت", "العملية", "البيان", "القيمة"])
        header = self.recent_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setSortingEnabled(True)
        from ui.styles import fix_table_rtl

        fix_table_rtl(self.recent_table)
        self.recent_table.setStyleSheet(
            TABLE_STYLE_DARK
            + """
            QTableWidget::item {
                padding: 6px 6px;
            }
            QHeaderView::section {
                padding: 7px 6px;
                min-height: 18px;
                max-height: 30px;
            }
            """
        )
        self.recent_table.setShowGrid(False)
        self.recent_table.setFrameShape(QFrame.Shape.NoFrame)
        header.setFixedHeight(30)
        self.recent_table.verticalHeader().setDefaultSectionSize(32)
        table_layout.addWidget(self.recent_table, 1)

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 4, 0, 0)
        pagination_layout.setSpacing(0)

        self.recent_pagination_widget = QWidget()
        self.recent_pagination_widget.setStyleSheet("background: transparent; border: none;")
        self.recent_pagination_widget.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        pagination_center_layout = QHBoxLayout(self.recent_pagination_widget)
        pagination_center_layout.setContentsMargins(0, 0, 0, 0)
        pagination_center_layout.setSpacing(8)

        self.recent_prev_button = QPushButton("◀ السابق")
        self.recent_prev_button.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #203a63, stop:1 #274876);
                color: white;
                padding: 7px 12px;
                border-radius: 10px;
                border: 1px solid rgba(148, 163, 184, 0.12);
                font-weight: 700;
                font-family: 'Cairo';
            }
            QPushButton:hover {
                background: #31558b;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #94a3b8;
                border-color: rgba(148, 163, 184, 0.06);
            }
            """
        )
        self.recent_prev_button.setFixedHeight(32)
        self.recent_prev_button.setMinimumWidth(120)
        self.recent_prev_button.clicked.connect(self._go_recent_prev_page)

        self.recent_next_button = QPushButton("التالي ▶")
        self.recent_next_button.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #203a63, stop:1 #274876);
                color: white;
                padding: 7px 12px;
                border-radius: 10px;
                border: 1px solid rgba(148, 163, 184, 0.12);
                font-weight: 700;
                font-family: 'Cairo';
            }
            QPushButton:hover {
                background: #31558b;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #94a3b8;
                border-color: rgba(148, 163, 184, 0.06);
            }
            """
        )
        self.recent_next_button.setFixedHeight(32)
        self.recent_next_button.setMinimumWidth(120)
        self.recent_next_button.clicked.connect(self._go_recent_next_page)

        self.recent_page_info_label = QLabel("صفحة 1 / 1")
        self.recent_page_info_label.setStyleSheet(
            """
            color: #dbeafe;
            font-size: 10px;
            font-family: 'Cairo';
            padding: 6px 10px;
            border-radius: 10px;
            background-color: rgba(12, 25, 47, 0.34);
            border: 1px solid rgba(148, 163, 184, 0.10);
            """
        )
        self.recent_page_info_label.setFixedHeight(32)
        self.recent_page_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recent_page_info_label.setMinimumWidth(74)

        self.recent_page_size_combo = QComboBox()
        self.recent_page_size_combo.addItems(["5", "10", "20", "كل"])
        self.recent_page_size_combo.setCurrentText("10")
        self.recent_page_size_combo.setStyleSheet(
            """
            QComboBox {
                background-color: #102645;
                color: white;
                border: 1px solid rgba(148, 163, 184, 0.14);
                border-radius: 10px;
                padding: 6px 10px;
                min-width: 86px;
                font-family: 'Cairo';
                font-weight: 700;
            }
            QComboBox::drop-down {
                border: none;
                width: 22px;
            }
            QComboBox QAbstractItemView {
                background-color: #102645;
                color: white;
                border: 1px solid rgba(148, 163, 184, 0.18);
                selection-background-color: #2563eb;
            }
            """
        )
        self.recent_page_size_combo.setFixedHeight(32)
        self.recent_page_size_combo.currentTextChanged.connect(self._on_recent_page_size_changed)

        pagination_size_label = QLabel("حجم الصفحة:")
        pagination_size_label.setStyleSheet(
            """
            color: #dbeafe;
            font-size: 11px;
            font-weight: 700;
            font-family: 'Cairo';
            background: transparent;
            """
        )
        pagination_size_label.setFixedHeight(32)
        pagination_size_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )

        pagination_center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_center_layout.addSpacing(10)
        pagination_center_layout.addWidget(
            self.recent_prev_button, 0, Qt.AlignmentFlag.AlignVCenter
        )
        pagination_center_layout.addWidget(
            self.recent_next_button, 0, Qt.AlignmentFlag.AlignVCenter
        )
        pagination_center_layout.addSpacing(10)
        pagination_center_layout.addWidget(pagination_size_label, 0, Qt.AlignmentFlag.AlignVCenter)
        pagination_center_layout.addWidget(
            self.recent_page_size_combo, 0, Qt.AlignmentFlag.AlignVCenter
        )
        pagination_center_layout.addSpacing(10)
        pagination_center_layout.addWidget(
            self.recent_page_info_label, 0, Qt.AlignmentFlag.AlignVCenter
        )

        self.recent_pagination_size_label = pagination_size_label
        self.recent_pagination_meta_widget = None
        self.recent_pagination_balance_widget = None

        pagination_layout.addStretch(1)
        pagination_layout.addWidget(self.recent_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addStretch(1)
        table_layout.addLayout(pagination_layout)

    def _rearrange_cards(self):
        """ترتيب الكروت تلقائياً حسب المساحة المتاحة"""
        width = self.width()

        # حساب عدد الأعمدة المناسب
        if width < 560:
            cols = 1
        elif width < 900:
            cols = 2
        elif width < 1250:
            cols = 3
        elif width < 1600:
            cols = 4
        else:
            cols = 5

        # إعادة ترتيب الكروت
        for i, card in enumerate(self.stat_cards):
            row = i // cols
            col = i % cols
            self.cards_grid.addWidget(card, row, col)

        rows = (len(self.stat_cards) + cols - 1) // cols
        for col in range(5):
            self.cards_grid.setColumnStretch(col, 1 if col < cols else 0)
        for row in range(rows + 1):
            self.cards_grid.setRowStretch(row, 0)

        card_height = self.card_sales.maximumHeight()
        total_height = (rows * card_height) + max(0, rows - 1) * self.cards_grid.spacing()
        self.cards_container.setFixedHeight(total_height)

    def _rearrange_bottom_section(self):
        """تغيير اتجاه القسم السفلي حسب العرض"""
        if self.bottom_splitter is None:
            return
        width = self.width()

        if width < 760:
            self.bottom_splitter.setOrientation(Qt.Orientation.Vertical)
        else:
            self.bottom_splitter.setOrientation(Qt.Orientation.Horizontal)

    def _refresh_recent_activity_from_signal(self):
        if not self._show_recent_activity or not self._load_recent_activity_data:
            return
        if not self._bottom_section_ready:
            self._schedule_bottom_section_build()
            return
        if self._is_refreshing or self._is_refreshing_recent_activity:
            return

        self._is_refreshing_recent_activity = True

        from core.data_loader import get_data_loader

        def fetch_recent():
            try:
                return self.accounting_service.get_recent_activity(8)
            except Exception as e:
                safe_print(f"ERROR: [Dashboard] فشل جلب آخر العمليات من الإشعارات: {e}")
                return []

        def on_recent_loaded(recent):
            try:
                self._recent_items = recent or []
                self._render_recent_page()
            finally:
                self._is_refreshing_recent_activity = False

        def on_recent_error(error_msg):
            safe_print(f"ERROR: [Dashboard] {error_msg}")
            self._is_refreshing_recent_activity = False

        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="dashboard_recent_activity",
            load_function=fetch_recent,
            on_success=on_recent_loaded,
            on_error=on_recent_error,
            use_thread_pool=True,
        )

    def _ensure_chart_widget(self) -> FinancialChart:
        if not self._bottom_section_ready:
            self._ensure_bottom_section()
        if self.chart is not None:
            return self.chart

        chart = FinancialChart(self.chart_container)
        chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if self.chart_placeholder is not None:
            self.chart_placeholder.hide()
            self.chart_content_layout.removeWidget(self.chart_placeholder)
            self.chart_placeholder.deleteLater()
            self.chart_placeholder = None
        self.chart_content_layout.addWidget(chart, 1)
        self.chart = chart
        return chart

    def refresh_data(self):
        """تحديث البيانات من المصدر الموحد (مع حماية من التحديث المتكرر)"""
        import time

        if not getattr(self, "_bottom_section_ready", True):
            ensure_bottom_section = getattr(self, "_ensure_bottom_section", None)
            if callable(ensure_bottom_section):
                ensure_bottom_section()

        # ⚡ حماية من التحديث المتكرر
        current_time = time.time()
        if self._is_refreshing:
            safe_print("WARNING: [Dashboard] ⏳ تحديث جاري بالفعل - تم تجاهل الطلب")
            return
        if (current_time - self._last_refresh_time) < self._min_refresh_interval:
            safe_print("WARNING: [Dashboard] ⏳ تحديث متكرر سريع - تم تجاهل الطلب")
            return

        self._is_refreshing = True
        self._last_refresh_time = current_time
        safe_print("INFO: [Dashboard] جاري تحديث أرقام الداشبورد...")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("⏳ جاري التحديث...")

        from core.data_loader import get_data_loader

        def fetch_data():
            try:
                # استخدام الدالة الموحدة الجديدة
                stats = self.accounting_service.get_dashboard_stats()
                recent = (
                    self.accounting_service.get_recent_activity(8)
                    if self._show_recent_activity and self._load_recent_activity_data
                    else []
                )
                return {"stats": stats, "recent": recent}
            except Exception as e:
                safe_print(f"ERROR: [Dashboard] فشل جلب البيانات: {e}")
                return {}

        def on_data_loaded(data):
            try:
                stats = data.get("stats", {})
                recent = data.get("recent", [])

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
                self.card_net_profit.set_value(net_profit)

                # تحديث الرسم البياني فقط عند تغيّر بياناته لتقليل الحمل الرسومي.
                chart_signature = (
                    round(float(sales or 0.0), 4),
                    round(float(expenses or 0.0), 4),
                    round(float(net_profit or 0.0), 4),
                )
                if chart_signature != self._last_chart_signature:
                    self._ensure_chart_widget().plot_data(sales, expenses, net_profit)
                    self._last_chart_signature = chart_signature

                self._recent_items = recent
                if self._show_recent_activity:
                    self._render_recent_page()
                else:
                    self.recent_table.setRowCount(0)

                self.last_update_lbl.setText(
                    self._format_datetime_badge(datetime.now(), "آخر تحديث")
                )

                safe_print("INFO: [Dashboard] ✅ تم تحديث الداشبورد بنجاح")
            except Exception as e:
                safe_print(f"ERROR: [Dashboard] فشل تحديث الواجهة: {e}")
                import traceback

                traceback.print_exc()
            finally:
                self._is_refreshing = False
                self.refresh_btn.setEnabled(True)
                self.refresh_btn.setText("🔄 تحديث")

        def on_error(error_msg):
            safe_print(f"ERROR: [Dashboard] {error_msg}")
            self._is_refreshing = False
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("🔄 تحديث")

        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="dashboard_data",
            load_function=fetch_data,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _get_recent_total_pages(self) -> int:
        total = len(self._recent_items)
        if total == 0:
            return 1
        if self._recent_page_size <= 0:
            return 1
        return (total + self._recent_page_size - 1) // self._recent_page_size

    def _render_recent_page(self):
        if not self._bottom_section_ready:
            self._ensure_bottom_section()
        if self.recent_table is None or self.recent_hint_lbl is None:
            return
        total_pages = self._get_recent_total_pages()
        if self._recent_current_page > total_pages:
            self._recent_current_page = total_pages
        if self._recent_current_page < 1:
            self._recent_current_page = 1

        if not self._recent_items:
            if self._load_recent_activity_data:
                self.recent_hint_lbl.setText("لا توجد عمليات موثقة حديثة لعرضها حالياً.")
            else:
                self.recent_hint_lbl.setText(
                    "تم إخفاء بيانات آخر العمليات من عرض الداشبورد فقط، بدون حذف أي بيانات مالية من النظام."
                )
            self.recent_table.setRowCount(0)
            self._update_recent_controls(total_pages)
            return

        self.recent_hint_lbl.setText(
            "يعرض أحدث العمليات الموثقة من جميع الأقسام مثل العملاء والمشاريع والفواتير والدفعات والمصروفات، مع فولباك آمن للبيانات القديمة عند الحاجة."
        )
        if self._recent_page_size <= 0:
            page_items = self._recent_items
        else:
            start_index = (self._recent_current_page - 1) * self._recent_page_size
            end_index = start_index + self._recent_page_size
            page_items = self._recent_items[start_index:end_index]

        self._populate_recent_table(page_items)
        self._update_recent_controls(total_pages)

    def _populate_recent_table(self, items: list):
        if not self._bottom_section_ready:
            self._ensure_bottom_section()
        if self.recent_table is None:
            return
        prev_sorting = self.recent_table.isSortingEnabled()
        prev_block = self.recent_table.blockSignals(True)
        self.recent_table.setSortingEnabled(False)
        self.recent_table.setUpdatesEnabled(False)
        try:
            self.recent_table.setRowCount(len(items))
            for i, entry in enumerate(items):
                if isinstance(entry, dict):
                    date_val = self._format_recent_timestamp(
                        entry.get("timestamp") or entry.get("date")
                    )
                    operation_val = str(entry.get("operation", "") or "").strip()
                    desc_val = entry.get("description", "")
                    details_val = str(entry.get("details", "") or "").strip()
                    amount_val = entry.get("amount", 0)
                else:
                    date_val = str(entry[0]) if len(entry) > 0 else ""
                    operation_val = ""
                    desc_val = str(entry[1]) if len(entry) > 1 else ""
                    details_val = ""
                    amount_val = entry[2] if len(entry) > 2 else 0

                summary_val = str(desc_val or "").strip()
                if details_val:
                    summary_val = f"{summary_val} • {details_val}" if summary_val else details_val

                date_item = create_centered_item(date_val)

                operation_item = create_centered_item(operation_val or "عملية")
                op_color = "#cbd5e1"
                operation_text = str(operation_val or "")
                if "تحصيل" in operation_text:
                    op_color = "#22c55e"
                elif "مصروف" in operation_text or "حذف" in operation_text:
                    op_color = "#f97316" if "مصروف" in operation_text else "#ef4444"
                elif "إضافة" in operation_text or "إنشاء" in operation_text:
                    op_color = "#38bdf8"
                elif "تعديل" in operation_text:
                    op_color = "#eab308"
                operation_item.setForeground(QBrush(QColor(op_color)))

                summary_item = create_centered_item(summary_val)
                summary_item.setToolTip(summary_val)
                summary_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if amount_val in (None, ""):
                    amount_item = create_centered_item("—")
                    amount_item.setForeground(QBrush(QColor("#94a3b8")))
                else:
                    amount_float = float(amount_val or 0)
                    amount_item = create_centered_item(f"{amount_float:,.2f}")
                    amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    amount_item.setForeground(
                        QBrush(QColor("#22c55e" if amount_float >= 0 else "#ef4444"))
                    )

                self.recent_table.setItem(i, 0, date_item)
                self.recent_table.setItem(i, 1, operation_item)
                self.recent_table.setItem(i, 2, summary_item)
                self.recent_table.setItem(i, 3, amount_item)
        finally:
            self.recent_table.setUpdatesEnabled(True)
            self.recent_table.setSortingEnabled(prev_sorting)
            self.recent_table.blockSignals(prev_block)

    def _update_recent_controls(self, total_pages: int):
        if not self._bottom_section_ready:
            return
        self.recent_page_info_label.setText(f"صفحة {self._recent_current_page} / {total_pages}")
        self.recent_prev_button.setEnabled(self._recent_current_page > 1)
        self.recent_next_button.setEnabled(self._recent_current_page < total_pages)
        self._sync_recent_pagination_balance()

    def _sync_recent_pagination_balance(self):
        return

    def _on_recent_page_size_changed(self, value: str):
        if value == "كل":
            self._recent_page_size = max(1, len(self._recent_items))
        else:
            try:
                self._recent_page_size = int(value)
            except Exception:
                self._recent_page_size = 10
        self._recent_current_page = 1
        self._render_recent_page()

    def _go_recent_prev_page(self):
        if self._recent_current_page > 1:
            self._recent_current_page -= 1
            self._render_recent_page()

    def _go_recent_next_page(self):
        if self._recent_current_page < self._get_recent_total_pages():
            self._recent_current_page += 1
            self._render_recent_page()
