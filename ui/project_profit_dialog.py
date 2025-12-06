# الملف: ui/project_profit_dialog.py

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core import schemas
from services.project_service import ProjectService


class ProjectProfitDialog(QDialog):
    """شاشة منبثقة تعرض ربحية مشروع محدد بالتفصيل."""

    def __init__(self, project: schemas.Project, project_service: ProjectService, parent=None):
        super().__init__(parent)

        self.project = project
        self.project_service = project_service

        self.setWindowTitle(f"📊 تقرير ربحية مشروع: {project.name}")
        self.setMinimumWidth(800)
        self.setMinimumHeight(650)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # --- معلومات المشروع الأساسية ---
        info_group = QGroupBox("معلومات المشروع")
        info_layout = QHBoxLayout()

        self.project_name_label = QLabel(f"<b>اسم المشروع:</b> {project.name}")
        self.client_label = QLabel(f"<b>العميل:</b> {project.client_id}")
        self.status_label = QLabel(f"<b>الحالة:</b> {project.status.value}")

        info_layout.addWidget(self.project_name_label)
        info_layout.addWidget(self.client_label)
        info_layout.addWidget(self.status_label)
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)

        # --- كروت الأرقام الرئيسية ---
        kpi_layout = QHBoxLayout()
        self.revenue_card = self.create_kpi_card("💰 إجمالي العقد", "revenue", "#3b82f6")
        self.paid_card = self.create_kpi_card("✅ المدفوع", "paid", "#0A6CF1")
        self.due_card = self.create_kpi_card("⏳ المتبقي", "due", "#f59e0b")
        self.expenses_card = self.create_kpi_card("📉 المصروفات", "expenses", "#ef4444")
        self.profit_card = self.create_kpi_card("📈 صافي الربح", "profit", "#8b5cf6")

        kpi_layout.addWidget(self.revenue_card)
        kpi_layout.addWidget(self.paid_card)
        kpi_layout.addWidget(self.due_card)
        kpi_layout.addWidget(self.expenses_card)
        kpi_layout.addWidget(self.profit_card)
        main_layout.addLayout(kpi_layout)

        # --- شريط التقدم (نسبة التحصيل) ---
        progress_group = QGroupBox("نسبة التحصيل")
        progress_layout = QVBoxLayout()
        self.collection_progress = QProgressBar()
        self.collection_progress.setMinimum(0)
        self.collection_progress.setMaximum(100)
        self.collection_progress.setValue(0)
        self.collection_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e5e7eb;
                border-radius: 5px;
                text-align: center;
                height: 25px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #0A6CF1;
                border-radius: 3px;
            }
        """)
        self.collection_label = QLabel("0% من قيمة العقد تم تحصيله")
        self.collection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.collection_progress)
        progress_layout.addWidget(self.collection_label)
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)

        # --- جدول الدفعات ---
        main_layout.addWidget(QLabel("<b>💳 الدفعات المسجلة:</b>"))
        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(4)
        self.payments_table.setHorizontalHeaderLabels(["التاريخ", "المبلغ", "الحساب", "ملاحظات"])
        h_header = self.payments_table.horizontalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.payments_table.setMaximumHeight(150)
        self.payments_table.setAlternatingRowColors(True)
        main_layout.addWidget(self.payments_table)

        # --- جدول المصروفات ---
        main_layout.addWidget(QLabel("<b>💸 المصروفات المرتبطة:</b>"))
        self.expenses_table = QTableWidget()
        self.expenses_table.setColumnCount(4)
        self.expenses_table.setHorizontalHeaderLabels(["التاريخ", "الفئة", "الوصف", "المبلغ"])
        h_header2 = self.expenses_table.horizontalHeader()
        if h_header2 is not None:
            h_header2.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.expenses_table.setMaximumHeight(150)
        self.expenses_table.setAlternatingRowColors(True)
        main_layout.addWidget(self.expenses_table)

        # --- أزرار التحكم ---
        buttons_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 تحديث")
        self.refresh_btn.clicked.connect(self.load_profit_data)
        self.close_btn = QPushButton("إغلاق")
        self.close_btn.clicked.connect(self.accept)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.refresh_btn)
        buttons_layout.addWidget(self.close_btn)
        main_layout.addLayout(buttons_layout)

        self.load_profit_data()

    def create_kpi_card(self, title: str, key: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        card.setMinimumWidth(140)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-size: 11px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel("0.00")
        value_label.setStyleSheet("color: white; font-weight: bold; font-size: 16px;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName(f"val_{key}")

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        card.setProperty("card_key", key)
        return card

    def update_card_value(self, card: QFrame, key: str, value: float):
        value_label = card.findChild(QLabel, f"val_{key}")
        if value_label:
            value_label.setText(f"{value:,.2f}")
            # تغيير لون كارت الربح حسب القيمة
            if key == "profit":
                if value >= 0:
                    card.setStyleSheet("""
                        QFrame {
                            background-color: #0A6CF1;
                            border-radius: 10px;
                            padding: 10px;
                        }
                    """)
                else:
                    card.setStyleSheet("""
                        QFrame {
                            background-color: #ef4444;
                            border-radius: 10px;
                            padding: 10px;
                        }
                    """)
            # تغيير لون كارت المتبقي
            elif key == "due":
                if value > 0:
                    card.setStyleSheet("""
                        QFrame {
                            background-color: #ef4444;
                            border-radius: 10px;
                            padding: 10px;
                        }
                    """)
                else:
                    card.setStyleSheet("""
                        QFrame {
                            background-color: #0A6CF1;
                            border-radius: 10px;
                            padding: 10px;
                        }
                    """)

    def load_profit_data(self):
        project_name = self.project.name
        try:
            # جلب بيانات الربحية
            profit_data = self.project_service.get_project_profitability(project_name)

            total_revenue = profit_data.get("total_revenue", 0.0)
            total_paid = profit_data.get("total_paid", 0.0)
            balance_due = profit_data.get("balance_due", 0.0)
            total_expenses = profit_data.get("total_expenses", 0.0)
            net_profit = profit_data.get("net_profit", 0.0)

            # تحديث الكروت
            self.update_card_value(self.revenue_card, "revenue", total_revenue)
            self.update_card_value(self.paid_card, "paid", total_paid)
            self.update_card_value(self.due_card, "due", balance_due)
            self.update_card_value(self.expenses_card, "expenses", total_expenses)
            self.update_card_value(self.profit_card, "profit", net_profit)

            # تحديث شريط التقدم
            if total_revenue > 0:
                collection_percent = int((total_paid / total_revenue) * 100)
                self.collection_progress.setValue(min(collection_percent, 100))
                self.collection_label.setText(f"{collection_percent}% من قيمة العقد تم تحصيله ({total_paid:,.2f} من {total_revenue:,.2f})")
            else:
                self.collection_progress.setValue(0)
                self.collection_label.setText("لا توجد قيمة للعقد")

            # جلب الدفعات
            payments = self.project_service.get_payments_for_project(project_name)
            self.payments_table.setRowCount(0)
            for i, pay in enumerate(payments):
                self.payments_table.insertRow(i)
                date_str = pay.date.strftime("%Y-%m-%d") if isinstance(pay.date, datetime) else str(pay.date)
                self.payments_table.setItem(i, 0, QTableWidgetItem(date_str))

                amount_item = QTableWidgetItem(f"{pay.amount:,.2f}")
                amount_item.setForeground(QColor("#0A6CF1"))
                self.payments_table.setItem(i, 1, amount_item)

                # عرض اسم الحساب بدلاً من ID
                account_name = "-"
                if hasattr(pay, 'account_id') and pay.account_id:
                    try:
                        # محاولة جلب الحساب من الخدمة
                        if hasattr(self.project_service, 'accounting_service'):
                            account = self.project_service.accounting_service.repo.get_account_by_code(pay.account_id)
                            if account:
                                account_name = account.name
                            else:
                                account = self.project_service.accounting_service.repo.get_account_by_id(pay.account_id)
                                if account:
                                    account_name = account.name
                                else:
                                    account_name = str(pay.account_id)
                        else:
                            account_name = str(pay.account_id)
                    except Exception as acc_err:
                        print(f"WARNING: فشل جلب اسم الحساب: {acc_err}")
                        account_name = str(pay.account_id)

                self.payments_table.setItem(i, 2, QTableWidgetItem(account_name))
                self.payments_table.setItem(i, 3, QTableWidgetItem(getattr(pay, 'notes', '') or "-"))

            # جلب المصروفات
            expenses = self.project_service.get_expenses_for_project(project_name)
            self.expenses_table.setRowCount(0)
            for i, exp in enumerate(expenses):
                self.expenses_table.insertRow(i)
                date_str = exp.date.strftime("%Y-%m-%d") if isinstance(exp.date, datetime) else str(exp.date)
                self.expenses_table.setItem(i, 0, QTableWidgetItem(date_str))
                self.expenses_table.setItem(i, 1, QTableWidgetItem(exp.category or "-"))
                self.expenses_table.setItem(i, 2, QTableWidgetItem(exp.description or "-"))

                amount_item = QTableWidgetItem(f"{exp.amount:,.2f}")
                amount_item.setForeground(QColor("#ef4444"))
                self.expenses_table.setItem(i, 3, amount_item)

        except Exception as e:
            print(f"ERROR: [ProjectProfitDialog] فشل تحميل بيانات الربحية: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل تحميل بيانات الربحية: {e}")
