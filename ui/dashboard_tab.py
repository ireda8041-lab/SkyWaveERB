from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from services.accounting_service import AccountingService
from core.signals import app_signals


class DashboardTab(QWidget):
    """
    التاب الخاص بالداشبورد (لوحة التحكم الرئيسية).
    """

    def __init__(self, accounting_service: AccountingService, parent=None):
        super().__init__(parent)

        self.accounting_service = accounting_service

        # ربط الإشارات للتحديث التلقائي (سيتم إضافة load_data لاحقاً)
        # app_signals.data_changed.connect(self.load_data)
        # app_signals.accounts_changed.connect(self.load_data)
        # app_signals.projects_changed.connect(self.load_data)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # العنوان مع زرار التحديث
        from PyQt6.QtWidgets import QHBoxLayout, QPushButton
        header_layout = QHBoxLayout()
        
        title = QLabel("لوحة التحكم الرئيسية (ملخص مالي)")
        title_font = QFont("Arial", 24, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # زرار التحديث
        self.refresh_btn = QPushButton("🔄 تحديث")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        header_layout.addStretch()
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.refresh_btn)
        
        main_layout.addLayout(header_layout)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)

        self.collected_card = self.create_kpi_card("إجمالي الإيرادات (المُحصلة)", "0.00 EGP", "#10b981")
        self.outstanding_card = self.create_kpi_card("إجمالي المستحقات (المتبقية)", "0.00 EGP", "#f59e0b")
        self.expenses_card = self.create_kpi_card("إجمالي المصروفات", "0.00 EGP", "#ef4444")
        self.net_profit_card = self.create_kpi_card("صافي الربح (نقدي)", "0.00 EGP", "#3b82f6")

        grid_layout.addWidget(self.collected_card, 0, 0)
        grid_layout.addWidget(self.outstanding_card, 0, 1)
        grid_layout.addWidget(self.expenses_card, 1, 0)
        grid_layout.addWidget(self.net_profit_card, 1, 1)

        main_layout.addLayout(grid_layout)
        main_layout.addStretch()
        
        # تحميل البيانات تلقائياً عند فتح التاب
        self.refresh_data()

    def create_kpi_card(self, title: str, value: str, color: str) -> QFrame:
        """ (جديدة) دالة لإنشاء "كارت" عرض الأرقام """
        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {color};
                border-radius: 10px;
            }}
            """
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: white;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel(value)
        value_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        value_label.setStyleSheet("color: white;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName(f"val_{title}")

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)

        return card

    def refresh_data(self):
        """
        (جديدة) تجلب الأرقام من الـ Service وتحدّث الكروت
        """
        print("INFO: [Dashboard] جاري تحديث أرقام الداشبورد...")
        try:
            kpis = self.accounting_service.get_dashboard_kpis()

            self.update_card_value(self.collected_card, kpis.get("total_collected", 0))
            self.update_card_value(self.outstanding_card, kpis.get("total_outstanding", 0))
            self.update_card_value(self.expenses_card, kpis.get("total_expenses", 0))
            self.update_card_value(self.net_profit_card, kpis.get("net_profit_cash", 0))

        except Exception as e:
            print(f"ERROR: [Dashboard] فشل تحديث الأرقام: {e}")

    def update_card_value(self, card: QFrame, value: float):
        """ (جديدة) دالة مساعدة لتحديث الرقم جوه الكارت """
        try:
            title_label = card.findChild(QLabel)
            if title_label is None:
                return

            value_label = card.findChild(QLabel, f"val_{title_label.text()}")
            if value_label is None:
                return

            value_label.setText(f"{value:,.2f} EGP")

            if "صافي الربح" in title_label.text():
                if value >= 0:
                    card.setStyleSheet("background-color: #3b82f6; border-radius: 10px;")
                else:
                    card.setStyleSheet("background-color: #ef4444; border-radius: 10px;")

        except Exception as e:
            print(f"ERROR: [Dashboard] فشل تحديث الكارت: {e}")
