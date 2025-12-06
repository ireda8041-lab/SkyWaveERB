#!/usr/bin/env python3
"""
نافذة كشف الحساب - عرض جميع الحركات المحاسبية لحساب معين
"""

from datetime import datetime

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDateEdit,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core import schemas
from ui.styles import BUTTON_STYLES, COLORS


class LedgerWindow(QDialog):
    """
    نافذة كشف الحساب - تعرض جميع الحركات المحاسبية لحساب معين
    """

    def __init__(self, account: schemas.Account, accounting_service, parent=None):
        super().__init__(parent)

        self.account = account
        self.accounting_service = accounting_service

        self.setWindowTitle(f"كشف حساب: {account.name} ({account.code})")
        self.setMinimumWidth(1000)
        self.setMinimumHeight(600)

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
        info_group.setStyleSheet(f"""
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
        """)

        info_layout = QHBoxLayout()

        # الكود
        code_label = QLabel(f"الكود: {self.account.code}")
        code_label.setStyleSheet(f"font-size: 14px; color: {COLORS['text_primary']}; font-weight: bold;")
        info_layout.addWidget(code_label)

        # النوع
        type_text = self.account.type.value if self.account.type else "N/A"
        type_label = QLabel(f"النوع: {type_text}")
        type_label.setStyleSheet(f"font-size: 14px; color: {COLORS['info']};")
        info_layout.addWidget(type_label)

        # الرصيد
        balance_label = QLabel(f"الرصيد الحالي: {self.account.balance:,.2f} جنيه")
        balance_label.setStyleSheet(f"font-size: 16px; color: {COLORS['success']}; font-weight: bold;")
        info_layout.addWidget(balance_label)

        info_layout.addStretch()
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # === 2. فلتر التاريخ ===
        filter_group = QGroupBox("فلتر الفترة")
        filter_group.setStyleSheet(f"""
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
        """)

        filter_layout = QHBoxLayout()

        # من تاريخ
        filter_layout.addWidget(QLabel("من:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.start_date.setStyleSheet(f"""
            QDateEdit {{
                background-color: {COLORS['bg_light']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 5px;
            }}
        """)
        filter_layout.addWidget(self.start_date)

        # إلى تاريخ
        filter_layout.addWidget(QLabel("إلى:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setStyleSheet(f"""
            QDateEdit {{
                background-color: {COLORS['bg_light']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 5px;
            }}
        """)
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
        movements_group.setStyleSheet(f"""
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
        """)

        movements_layout = QVBoxLayout()

        self.movements_table = QTableWidget()
        self.movements_table.setColumnCount(6)
        self.movements_table.setHorizontalHeaderLabels([
            "التاريخ", "الوصف", "المرجع", "مدين", "دائن", "الرصيد"
        ])

        # ستايل الجدول
        self.movements_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['bg_light']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                gridline-color: {COLORS['border']};
                selection-background-color: {COLORS['primary']};
                selection-color: white;
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {COLORS['border']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['text_primary']};
                padding: 10px;
                border: none;
                border-right: 1px solid {COLORS['border']};
                font-weight: bold;
            }}
        """)

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

        # === 4. الملخص ===
        summary_layout = QHBoxLayout()

        self.total_debit_label = QLabel("إجمالي المدين: 0.00 جنيه")
        self.total_debit_label.setStyleSheet(f"font-size: 14px; color: {COLORS['success']}; font-weight: bold;")
        summary_layout.addWidget(self.total_debit_label)

        self.total_credit_label = QLabel("إجمالي الدائن: 0.00 جنيه")
        self.total_credit_label.setStyleSheet(f"font-size: 14px; color: {COLORS['danger']}; font-weight: bold;")
        summary_layout.addWidget(self.total_credit_label)

        self.net_movement_label = QLabel("صافي الحركة: 0.00 جنيه")
        self.net_movement_label.setStyleSheet(f"font-size: 14px; color: {COLORS['info']}; font-weight: bold;")
        summary_layout.addWidget(self.net_movement_label)

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
        """تحميل بيانات كشف الحساب"""
        print(f"INFO: [LedgerWindow] جاري تحميل كشف حساب: {self.account.name}")

        try:
            # الحصول على الفترة
            start_date = self.start_date.date().toPyDate()
            end_date = self.end_date.date().toPyDate()

            # تحويل إلى datetime
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            # جلب جميع القيود المحاسبية
            all_entries = self.accounting_service.repo.get_all_journal_entries()

            # فلترة القيود حسب الحساب والفترة
            movements = []
            running_balance = 0.0

            for entry in all_entries:
                entry_date = entry.date

                # التحقق من الفترة
                if entry_date < start_datetime or entry_date > end_datetime:
                    continue

                # البحث عن بنود تخص هذا الحساب
                for line in entry.lines:
                    acc_code = line.account_code or line.account_id

                    if acc_code == self.account.code:
                        debit = line.debit
                        credit = line.credit

                        # حساب الرصيد الجاري
                        # الأصول والمصروفات: المدين يزيد، الدائن ينقص
                        # الخصوم والإيرادات: الدائن يزيد، المدين ينقص
                        asset_types = ['ASSET', 'CASH', 'EXPENSE', 'أصول', 'أصول نقدية', 'مصروفات']
                        acc_type = self.account.type.value if self.account.type else self.account.type

                        if acc_type in asset_types:
                            running_balance += debit - credit
                        else:
                            running_balance += credit - debit

                        movements.append({
                            'date': entry_date,
                            'description': line.description or entry.description,
                            'reference': entry.related_document_id or '',
                            'debit': debit,
                            'credit': credit,
                            'balance': running_balance
                        })

            # ترتيب الحركات حسب التاريخ
            movements.sort(key=lambda x: x['date'])

            # عرض الحركات في الجدول
            self.movements_table.setRowCount(0)

            total_debit = 0.0
            total_credit = 0.0

            for i, movement in enumerate(movements):
                self.movements_table.insertRow(i)

                # التاريخ
                date_str = movement['date'].strftime("%Y-%m-%d") if hasattr(movement['date'], 'strftime') else str(movement['date'])[:10]
                date_item = QTableWidgetItem(date_str)
                date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                self.movements_table.setItem(i, 0, date_item)

                # الوصف
                desc_item = QTableWidgetItem(movement['description'])
                desc_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.movements_table.setItem(i, 1, desc_item)

                # المرجع
                ref_item = QTableWidgetItem(movement['reference'][:20] if len(movement['reference']) > 20 else movement['reference'])
                ref_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                self.movements_table.setItem(i, 2, ref_item)

                # مدين
                debit_item = QTableWidgetItem(f"{movement['debit']:,.2f}" if movement['debit'] > 0 else "-")
                debit_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if movement['debit'] > 0:
                    debit_item.setForeground(QColor(COLORS['success']))
                self.movements_table.setItem(i, 3, debit_item)

                # دائن
                credit_item = QTableWidgetItem(f"{movement['credit']:,.2f}" if movement['credit'] > 0 else "-")
                credit_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if movement['credit'] > 0:
                    credit_item.setForeground(QColor(COLORS['danger']))
                self.movements_table.setItem(i, 4, credit_item)

                # الرصيد
                balance_item = QTableWidgetItem(f"{movement['balance']:,.2f}")
                balance_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                balance_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                if movement['balance'] > 0:
                    balance_item.setForeground(QColor(COLORS['success']))
                elif movement['balance'] < 0:
                    balance_item.setForeground(QColor(COLORS['danger']))
                self.movements_table.setItem(i, 5, balance_item)

                total_debit += movement['debit']
                total_credit += movement['credit']

            # تحديث الملخص
            self.total_debit_label.setText(f"إجمالي المدين: {total_debit:,.2f} جنيه")
            self.total_credit_label.setText(f"إجمالي الدائن: {total_credit:,.2f} جنيه")

            net_movement = total_debit - total_credit
            self.net_movement_label.setText(f"صافي الحركة: {net_movement:,.2f} جنيه")

            print(f"INFO: [LedgerWindow] تم تحميل {len(movements)} حركة")

        except Exception as e:
            print(f"ERROR: [LedgerWindow] فشل تحميل كشف الحساب: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "خطأ", f"فشل تحميل كشف الحساب:\n{str(e)}")

    def reset_filter(self):
        """إعادة تعيين الفلتر"""
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.end_date.setDate(QDate.currentDate())
        self.load_ledger_data()

    def export_to_excel(self):
        """تصدير كشف الحساب إلى Excel"""
        try:
            import csv
            from datetime import datetime

            from PyQt6.QtWidgets import QFileDialog

            # اختيار مكان الحفظ
            default_filename = f"كشف_حساب_{self.account.code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "حفظ كشف الحساب",
                default_filename,
                "CSV Files (*.csv);;All Files (*)"
            )

            if not file_path:
                return

            # جمع البيانات من الجدول
            rows = self.movements_table.rowCount()
            cols = self.movements_table.columnCount()

            # كتابة البيانات
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)

                # كتابة معلومات الحساب
                writer.writerow(['كشف حساب'])
                writer.writerow(['الحساب:', self.account.name])
                writer.writerow(['الكود:', self.account.code])
                writer.writerow(['الرصيد الحالي:', f"{self.account.balance:,.2f} جنيه"])
                writer.writerow(['الفترة:', f"من {self.start_date.date().toString('yyyy-MM-dd')} إلى {self.end_date.date().toString('yyyy-MM-dd')}"])
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
                        row_data.append(item.text() if item else '')
                    writer.writerow(row_data)

                # كتابة الملخص
                writer.writerow([])  # سطر فارغ
                writer.writerow(['الملخص'])
                writer.writerow([self.total_debit_label.text()])
                writer.writerow([self.total_credit_label.text()])
                writer.writerow([self.net_movement_label.text()])

            QMessageBox.information(
                self,
                "✅ تم التصدير",
                f"تم تصدير كشف الحساب بنجاح!\n\n📄 {file_path}"
            )

        except Exception as e:
            print(f"ERROR: [LedgerWindow] فشل التصدير: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل تصدير كشف الحساب:\n{str(e)}"
            )

    def print_ledger(self):
        """طباعة كشف الحساب"""
        try:
            from PyQt6.QtCore import QRect, Qt
            from PyQt6.QtGui import QFont, QPageLayout, QPainter
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
                title_font = QFont("Arial", 16, QFont.Weight.Bold)
                header_font = QFont("Arial", 12, QFont.Weight.Bold)
                normal_font = QFont("Arial", 10)

                # الهوامش
                margin = 50
                y = margin
                page_width = printer.width() - 2 * margin

                # العنوان
                painter.setFont(title_font)
                painter.drawText(QRect(margin, y, page_width, 50), Qt.AlignmentFlag.AlignCenter, "كشف حساب")
                y += 60

                # معلومات الحساب
                painter.setFont(header_font)
                painter.drawText(margin, y, f"الحساب: {self.account.name}")
                y += 30
                painter.drawText(margin, y, f"الكود: {self.account.code}")
                y += 30
                painter.drawText(margin, y, f"الرصيد الحالي: {self.account.balance:,.2f} جنيه")
                y += 30
                painter.drawText(margin, y, f"الفترة: من {self.start_date.date().toString('yyyy-MM-dd')} إلى {self.end_date.date().toString('yyyy-MM-dd')}")
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
                        text = item.text() if item else ''
                        painter.drawText(QRect(x, y, col_widths[col] - 10, 30), Qt.AlignmentFlag.AlignLeft, text)
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
                    self,
                    "✅ تمت الطباعة",
                    "تم إرسال كشف الحساب إلى الطابعة بنجاح!"
                )

            except Exception as e:
                painter.end()
                raise e

        except Exception as e:
            print(f"ERROR: [LedgerWindow] فشل الطباعة: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل طباعة كشف الحساب:\n{str(e)}"
            )
