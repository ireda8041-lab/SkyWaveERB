#!/usr/bin/env python3
"""
نافذة كشف الحساب - عرض جميع الحركات المحاسبية لحساب معين
"""

from datetime import datetime

from PyQt6.QtCore import QDate
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from core import schemas
from ui.styles import BUTTON_STYLES, COLORS, TABLE_STYLE_DARK, create_centered_item, get_cairo_font

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class LedgerWindow(QDialog):
    """
    نافذة كشف الحساب - تعرض جميع الحركات المحاسبية لحساب معين
    متجاوبة مع حجم الشاشة
    """

    def __init__(self, account: schemas.Account, accounting_service, parent=None):
        super().__init__(parent)

        self.account = account
        self.accounting_service = accounting_service
        self._current_page = 1
        self._page_size = 100
        self._movements: list = []

        self.setWindowTitle(f"كشف حساب: {account.name} ({account.code})")

        # 📱 تجاوب: حجم متجاوب مع الشاشة
        from PyQt6.QtWidgets import QApplication, QSizePolicy

        self.setMinimumWidth(800)
        self.setMinimumHeight(500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # حجم متجاوب مع الشاشة
        screen = QApplication.primaryScreen()
        if screen:
            screen_size = screen.availableGeometry()
            width = int(screen_size.width() * 0.75)
            height = int(screen_size.height() * 0.75)
            self.resize(min(width, 1200), min(height, 800))
            # توسيط النافذة
            x = (screen_size.width() - self.width()) // 2
            y = (screen_size.height() - self.height()) // 2
            self.move(x, y)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar

        setup_custom_title_bar(self)

        self.init_ui()
        self.load_ledger_data()

    def init_ui(self):
        """إعداد واجهة النافذة"""
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # === 1. معلومات الحساب ===
        info_group = QGroupBox("معلومات الحساب")
        info_group.setStyleSheet(
            f"""
            QGroupBox {{
                font-weight: bold;
                color: {COLORS['text_primary']};
                border: 2px solid {COLORS['primary']};
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                background-color: {COLORS['bg_light']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 5px 10px;
                background-color: {COLORS['primary']};
                color: white;
                border-radius: 4px;
            }}
        """
        )

        info_layout = QHBoxLayout()

        # الكود
        code_label = QLabel(f"الكود: {self.account.code}")
        code_label.setStyleSheet(
            f"font-size: 14px; color: {COLORS['text_primary']}; font-weight: bold;"
        )
        info_layout.addWidget(code_label)

        # النوع
        type_text = self.account.type.value if self.account.type else "N/A"
        type_label = QLabel(f"النوع: {type_text}")
        type_label.setStyleSheet(f"font-size: 14px; color: {COLORS['info']};")
        info_layout.addWidget(type_label)

        # الرصيد
        balance_label = QLabel(f"الرصيد الحالي: {self.account.balance:,.2f} جنيه")
        balance_label.setStyleSheet(
            f"font-size: 16px; color: {COLORS['success']}; font-weight: bold;"
        )
        info_layout.addWidget(balance_label)

        info_layout.addStretch()
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # === 2. فلتر التاريخ ===
        filter_group = QGroupBox("فلتر الفترة")
        filter_group.setStyleSheet(
            f"""
            QGroupBox {{
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                margin-top: 8px;
                padding: 10px;
                background-color: {COLORS['bg_dark']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 2px 8px;
            }}
        """
        )

        filter_layout = QHBoxLayout()

        # من تاريخ
        filter_layout.addWidget(QLabel("من:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.start_date.setStyleSheet(
            f"""
            QDateEdit {{
                background-color: {COLORS['bg_light']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 5px;
            }}
        """
        )
        filter_layout.addWidget(self.start_date)

        # إلى تاريخ
        filter_layout.addWidget(QLabel("إلى:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setStyleSheet(
            f"""
            QDateEdit {{
                background-color: {COLORS['bg_light']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 5px;
            }}
        """
        )
        filter_layout.addWidget(self.end_date)

        # زر التطبيق
        apply_btn = QPushButton("🔍 تطبيق")
        apply_btn.setStyleSheet(BUTTON_STYLES["primary"])
        apply_btn.clicked.connect(self.load_ledger_data)
        filter_layout.addWidget(apply_btn)

        # زر إعادة تعيين
        reset_btn = QPushButton("🔄 إعادة تعيين")
        reset_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        reset_btn.clicked.connect(self.reset_filter)
        filter_layout.addWidget(reset_btn)

        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # === 3. جدول الحركات ===
        movements_group = QGroupBox("الحركات المحاسبية")
        movements_group.setStyleSheet(
            f"""
            QGroupBox {{
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                margin-top: 8px;
                padding: 10px;
                background-color: {COLORS['bg_dark']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 2px 8px;
                font-weight: bold;
            }}
        """
        )

        movements_layout = QVBoxLayout()

        self.movements_table = QTableWidget()
        self.movements_table.setColumnCount(6)
        self.movements_table.setHorizontalHeaderLabels(
            ["التاريخ", "الوصف", "المرجع", "مدين", "دائن", "الرصيد"]
        )

        # ستايل الجدول
        self.movements_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl

        fix_table_rtl(self.movements_table)

        # إعدادات الجدول
        self.movements_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.movements_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.movements_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.movements_table.setAlternatingRowColors(True)

        # ضبط الأعمدة
        header = self.movements_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # التاريخ
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # الوصف
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)  # المرجع
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # مدين
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # دائن
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)  # الرصيد

            header.resizeSection(0, 120)  # التاريخ
            header.resizeSection(2, 150)  # المرجع
            header.resizeSection(3, 120)  # مدين
            header.resizeSection(4, 120)  # دائن
            header.resizeSection(5, 120)  # الرصيد

        movements_layout.addWidget(self.movements_table)
        movements_group.setLayout(movements_layout)
        layout.addWidget(movements_group)

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 6, 0, 0)
        pagination_layout.setSpacing(8)

        self.prev_page_button = QPushButton("◀ السابق")
        self.prev_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.prev_page_button.setFixedHeight(26)
        self.prev_page_button.clicked.connect(self._go_prev_page)

        self.next_page_button = QPushButton("التالي ▶")
        self.next_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.next_page_button.setFixedHeight(26)
        self.next_page_button.clicked.connect(self._go_next_page)

        self.page_info_label = QLabel("صفحة 1 / 1")
        self.page_info_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["50", "100", "200", "كل"])
        self.page_size_combo.setCurrentText("100")
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)

        pagination_layout.addWidget(self.prev_page_button)
        pagination_layout.addWidget(self.next_page_button)
        pagination_layout.addStretch(1)
        pagination_layout.addWidget(QLabel("حجم الصفحة:"))
        pagination_layout.addWidget(self.page_size_combo)
        pagination_layout.addWidget(self.page_info_label)
        layout.addLayout(pagination_layout)

        # === 4. الملخص ===
        summary_layout = QHBoxLayout()

        self.total_debit_label = QLabel("إجمالي المدين: 0.00 جنيه")
        self.total_debit_label.setStyleSheet(
            f"font-size: 14px; color: {COLORS['success']}; font-weight: bold;"
        )
        summary_layout.addWidget(self.total_debit_label)

        self.total_credit_label = QLabel("إجمالي الدائن: 0.00 جنيه")
        self.total_credit_label.setStyleSheet(
            f"font-size: 14px; color: {COLORS['danger']}; font-weight: bold;"
        )
        summary_layout.addWidget(self.total_credit_label)

        self.net_movement_label = QLabel("صافي الحركة: 0.00 جنيه")
        self.net_movement_label.setStyleSheet(
            f"font-size: 14px; color: {COLORS['info']}; font-weight: bold;"
        )
        summary_layout.addWidget(self.net_movement_label)

        self.opening_balance_label = QLabel("الرصيد الافتتاحي: 0.00 جنيه")
        self.opening_balance_label.setStyleSheet(
            f"font-size: 14px; color: {COLORS['text_secondary']}; font-weight: bold;"
        )
        summary_layout.addWidget(self.opening_balance_label)

        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        # === 5. أزرار التحكم ===
        buttons_layout = QHBoxLayout()

        export_btn = QPushButton("📄 تصدير Excel")
        export_btn.setStyleSheet(BUTTON_STYLES["success"])
        export_btn.clicked.connect(self.export_to_excel)
        buttons_layout.addWidget(export_btn)

        print_btn = QPushButton("🖨️ طباعة")
        print_btn.setStyleSheet(BUTTON_STYLES["info"])
        print_btn.clicked.connect(self.print_ledger)
        buttons_layout.addWidget(print_btn)

        buttons_layout.addStretch()

        close_btn = QPushButton("إغلاق")
        close_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        close_btn.clicked.connect(self.close)
        buttons_layout.addWidget(close_btn)

        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def load_ledger_data(self):
        """⚡ تحميل بيانات كشف الحساب في الخلفية لمنع التجميد"""
        safe_print(f"INFO: [LedgerWindow] جاري تحميل كشف حساب: {self.account.name}")

        # عرض رسالة تحميل
        self.movements_table.setRowCount(0)
        self.total_debit_label.setText("إجمالي المدين: ⏳ جاري التحميل...")
        self.total_credit_label.setText("إجمالي الدائن: ⏳ جاري التحميل...")
        self.net_movement_label.setText("صافي الحركة: ⏳ جاري التحميل...")
        self.opening_balance_label.setText("الرصيد الافتتاحي: ⏳ جاري التحميل...")

        from core.data_loader import get_data_loader

        # حفظ الفترة المحددة
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        account_code = self.account.code

        def fetch_ledger_data():
            """جلب بيانات كشف الحساب في thread منفصل"""
            try:
                # تحويل إلى datetime
                start_datetime = datetime.combine(start_date, datetime.min.time())
                end_datetime = datetime.combine(end_date, datetime.max.time())
                report = self.accounting_service.get_account_ledger_report(
                    account_code, start_datetime, end_datetime
                )

                return {
                    "movements": report.get("movements", []),
                    "opening_balance": report.get("opening_balance", 0.0),
                    "total_debit": report.get("total_debit", 0.0),
                    "total_credit": report.get("total_credit", 0.0),
                    "net_movement": report.get("net_movement", 0.0),
                    "error": None,
                }

            except Exception as e:
                safe_print(f"ERROR: [LedgerWindow] فشل تحميل كشف الحساب: {e}")
                import traceback

                traceback.print_exc()
                return {"movements": [], "opening_balance": 0.0, "error": str(e)}

        def on_data_loaded(data):
            """تحديث الواجهة بالبيانات"""
            try:
                if data.get("error"):
                    QMessageBox.critical(self, "خطأ", f"فشل تحميل كشف الحساب:\n{data['error']}")
                    return

                movements = data["movements"]
                opening_balance = float(data.get("opening_balance", 0.0) or 0.0)
                self._movements = movements

                total_debit = float(data.get("total_debit", 0.0) or 0.0)
                total_credit = float(data.get("total_credit", 0.0) or 0.0)
                net_movement = float(data.get("net_movement", 0.0) or 0.0)

                self._render_current_page()

                # تحديث الملخص
                self.total_debit_label.setText(f"إجمالي المدين: {total_debit:,.2f} جنيه")
                self.total_credit_label.setText(f"إجمالي الدائن: {total_credit:,.2f} جنيه")
                self.net_movement_label.setText(f"صافي الحركة: {net_movement:,.2f} جنيه")
                self.opening_balance_label.setText(f"الرصيد الافتتاحي: {opening_balance:,.2f} جنيه")

                safe_print(f"INFO: [LedgerWindow] تم تحميل {len(movements)} حركة")

            except Exception as e:
                safe_print(f"ERROR: [LedgerWindow] فشل تحديث الواجهة: {e}")
                import traceback

                traceback.print_exc()

        def on_error(error_msg):
            safe_print(f"ERROR: [LedgerWindow] {error_msg}")
            QMessageBox.critical(self, "خطأ", f"فشل تحميل كشف الحساب:\n{error_msg}")

        # ⚡ تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="ledger_data",
            load_function=fetch_ledger_data,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _get_total_pages(self) -> int:
        total = len(self._movements)
        if total == 0:
            return 1
        if self._page_size <= 0:
            return 1
        return (total + self._page_size - 1) // self._page_size

    def _render_current_page(self):
        total_pages = self._get_total_pages()
        if self._current_page > total_pages:
            self._current_page = total_pages
        if self._current_page < 1:
            self._current_page = 1

        if self._page_size <= 0:
            page_items = self._movements
        else:
            start_index = (self._current_page - 1) * self._page_size
            end_index = start_index + self._page_size
            page_items = self._movements[start_index:end_index]

        self._populate_movements_table(page_items)
        self._update_pagination_controls(total_pages)

    def _populate_movements_table(self, movements: list):
        self.movements_table.setRowCount(len(movements))
        for i, movement in enumerate(movements):
            date_val = movement.get("date") if isinstance(movement, dict) else None
            date_str = (
                date_val.strftime("%Y-%m-%d")
                if hasattr(date_val, "strftime")
                else str(date_val or "")[:10]
            )
            self.movements_table.setItem(i, 0, create_centered_item(date_str))

            desc_text = str(movement.get("description") or "") if isinstance(movement, dict) else ""
            self.movements_table.setItem(i, 1, create_centered_item(desc_text))

            ref_raw = str(movement.get("reference") or "") if isinstance(movement, dict) else ""
            ref_text = ref_raw[:20] if len(ref_raw) > 20 else ref_raw
            self.movements_table.setItem(i, 2, create_centered_item(ref_text))

            debit_val = float(movement.get("debit") or 0) if isinstance(movement, dict) else 0.0
            debit_text = f"{debit_val:,.2f}" if debit_val > 0 else "-"
            debit_item = create_centered_item(debit_text)
            if debit_val > 0:
                debit_item.setForeground(QColor(COLORS["success"]))
            self.movements_table.setItem(i, 3, debit_item)

            credit_val = float(movement.get("credit") or 0) if isinstance(movement, dict) else 0.0
            credit_text = f"{credit_val:,.2f}" if credit_val > 0 else "-"
            credit_item = create_centered_item(credit_text)
            if credit_val > 0:
                credit_item.setForeground(QColor(COLORS["danger"]))
            self.movements_table.setItem(i, 4, credit_item)

            balance_val = float(movement.get("balance") or 0) if isinstance(movement, dict) else 0.0
            balance_item = create_centered_item(f"{balance_val:,.2f}")
            balance_item.setFont(get_cairo_font(10, bold=True))
            if balance_val > 0:
                balance_item.setForeground(QColor(COLORS["success"]))
            elif balance_val < 0:
                balance_item.setForeground(QColor(COLORS["danger"]))
            self.movements_table.setItem(i, 5, balance_item)

    def _update_pagination_controls(self, total_pages: int):
        self.page_info_label.setText(f"صفحة {self._current_page} / {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

    def _on_page_size_changed(self, value: str):
        if value == "كل":
            self._page_size = max(1, len(self._movements))
        else:
            try:
                self._page_size = int(value)
            except Exception:
                self._page_size = 100
        self._current_page = 1
        self._render_current_page()

    def _go_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._render_current_page()

    def _go_next_page(self):
        if self._current_page < self._get_total_pages():
            self._current_page += 1
            self._render_current_page()

    def reset_filter(self):
        """إعادة تعيين الفلتر"""
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.end_date.setDate(QDate.currentDate())
        self.load_ledger_data()

    def export_to_excel(self):
        """تصدير كشف الحساب إلى CSV"""
        try:
            import csv

            from PyQt6.QtWidgets import QFileDialog

            # اختيار مكان الحفظ
            default_filename = (
                f"كشف_حساب_{self.account.code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            file_path, _ = QFileDialog.getSaveFileName(
                self, "حفظ كشف الحساب", default_filename, "CSV Files (*.csv);;All Files (*)"
            )

            if not file_path:
                return

            # جمع البيانات من الجدول
            rows = self.movements_table.rowCount()
            cols = self.movements_table.columnCount()

            # كتابة البيانات
            with open(file_path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)

                # كتابة معلومات الحساب
                writer.writerow(["كشف حساب"])
                writer.writerow(["الحساب:", self.account.name])
                writer.writerow(["الكود:", self.account.code])
                writer.writerow(["الرصيد الحالي:", f"{self.account.balance:,.2f} جنيه"])
                writer.writerow(
                    [
                        "الفترة:",
                        f"من {self.start_date.date().toString('yyyy-MM-dd')} إلى {self.end_date.date().toString('yyyy-MM-dd')}",
                    ]
                )
                writer.writerow([])  # سطر فارغ

                # كتابة رؤوس الأعمدة
                headers = []
                for col in range(cols):
                    headers.append(self.movements_table.horizontalHeaderItem(col).text())
                writer.writerow(headers)

                # كتابة البيانات
                for row in range(rows):
                    row_data = []
                    for col in range(cols):
                        item = self.movements_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)

                # كتابة الملخص
                writer.writerow([])  # سطر فارغ
                writer.writerow(["الملخص"])
                writer.writerow([self.total_debit_label.text()])
                writer.writerow([self.total_credit_label.text()])
                writer.writerow([self.net_movement_label.text()])

            QMessageBox.information(
                self, "✅ تم التصدير", f"تم تصدير كشف الحساب بنجاح!\n\n📄 {file_path}"
            )

        except Exception as e:
            safe_print(f"ERROR: [LedgerWindow] فشل التصدير: {e}")
            import traceback

            traceback.print_exc()
            QMessageBox.critical(self, "خطأ", f"فشل تصدير كشف الحساب:\n{str(e)}")

    def print_ledger(self):
        """طباعة كشف الحساب"""
        try:
            from PyQt6.QtCore import QRect, Qt
            from PyQt6.QtGui import QPageLayout, QPainter
            from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

            # إنشاء الطابعة
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            # PyQt6 يستخدم QPageLayout بدلاً من PageOrientation
            page_layout = printer.pageLayout()
            page_layout.setOrientation(QPageLayout.Orientation.Portrait)
            printer.setPageLayout(page_layout)

            # فتح نافذة الطباعة
            dialog = QPrintDialog(printer, self)
            if dialog.exec() != QPrintDialog.DialogCode.Accepted:
                return

            # الرسم على الطابعة
            painter = QPainter(printer)

            try:
                # إعدادات الخطوط
                title_font = get_cairo_font(16, bold=True)
                header_font = get_cairo_font(12, bold=True)
                normal_font = get_cairo_font(10)

                # الهوامش
                margin = 50
                y = margin
                page_width = printer.width() - 2 * margin

                # العنوان
                painter.setFont(title_font)
                painter.drawText(
                    QRect(margin, y, page_width, 50), Qt.AlignmentFlag.AlignCenter, "كشف حساب"
                )
                y += 60

                # معلومات الحساب
                painter.setFont(header_font)
                painter.drawText(margin, y, f"الحساب: {self.account.name}")
                y += 30
                painter.drawText(margin, y, f"الكود: {self.account.code}")
                y += 30
                painter.drawText(margin, y, f"الرصيد الحالي: {self.account.balance:,.2f} جنيه")
                y += 30
                painter.drawText(
                    margin,
                    y,
                    f"الفترة: من {self.start_date.date().toString('yyyy-MM-dd')} إلى {self.end_date.date().toString('yyyy-MM-dd')}",
                )
                y += 50

                # خط فاصل
                painter.drawLine(margin, y, printer.width() - margin, y)
                y += 20

                # رؤوس الأعمدة
                painter.setFont(header_font)
                col_widths = [150, 300, 200, 150, 150, 150]
                x = margin
                headers = ["التاريخ", "الوصف", "المرجع", "مدين", "دائن", "الرصيد"]
                for i, header in enumerate(headers):
                    painter.drawText(x, y, header)
                    x += col_widths[i]
                y += 30

                # خط فاصل
                painter.drawLine(margin, y, printer.width() - margin, y)
                y += 20

                # البيانات
                painter.setFont(normal_font)
                rows = self.movements_table.rowCount()

                for row in range(rows):
                    if y > printer.height() - 100:  # صفحة جديدة
                        printer.newPage()
                        y = margin

                    x = margin
                    for col in range(6):
                        item = self.movements_table.item(row, col)
                        text = item.text() if item else ""
                        painter.drawText(
                            QRect(x, y, col_widths[col] - 10, 30), Qt.AlignmentFlag.AlignLeft, text
                        )
                        x += col_widths[col]
                    y += 25

                # خط فاصل
                y += 10
                painter.drawLine(margin, y, printer.width() - margin, y)
                y += 30

                # الملخص
                painter.setFont(header_font)
                painter.drawText(margin, y, self.total_debit_label.text())
                y += 30
                painter.drawText(margin, y, self.total_credit_label.text())
                y += 30
                painter.drawText(margin, y, self.net_movement_label.text())

                painter.end()

                QMessageBox.information(
                    self, "✅ تمت الطباعة", "تم إرسال كشف الحساب إلى الطابعة بنجاح!"
                )

            except Exception as e:
                painter.end()
                raise e

        except Exception as e:
            safe_print(f"ERROR: [LedgerWindow] فشل الطباعة: {e}")
            import traceback

            traceback.print_exc()
            QMessageBox.critical(self, "خطأ", f"فشل طباعة كشف الحساب:\n{str(e)}")
