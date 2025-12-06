
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.client_service import ClientService
from services.quotation_service import QuotationService
from services.service_service import ServiceService
from services.settings_service import SettingsService
from ui.quotation_editor import QuotationEditorWindow
from ui.styles import BUTTON_STYLES


class QuotationManagerTab(QWidget):
    """التاب الخاص بإدارة عروض الأسعار."""

    def __init__(
        self,
        quotation_service: QuotationService,
        client_service: ClientService,
        service_service: ServiceService,
        settings_service: SettingsService,
        parent=None,
    ):
        super().__init__(parent)

        self.quotation_service = quotation_service
        self.client_service = client_service
        self.service_service = service_service
        self.settings_service = settings_service

        self.quotations_list: list[schemas.Quotation] = []

        layout = QVBoxLayout()
        self.setLayout(layout)

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals
        app_signals.quotations_changed.connect(self._on_quotations_changed)

        buttons_layout = QHBoxLayout()

        self.add_quote_button = QPushButton("➕ إضافة عرض سعر جديد")
        self.add_quote_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.add_quote_button.clicked.connect(self.open_quote_editor)

        self.convert_button = QPushButton("🔄 تحويل إلى فاتورة")
        self.convert_button.setStyleSheet(BUTTON_STYLES["success"])
        self.convert_button.clicked.connect(self.convert_to_invoice)

        self.edit_quote_button = QPushButton("✏️ تعديل")
        self.edit_quote_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_quote_button.clicked.connect(self.open_quote_for_edit)

        # زرار التحديث
        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.clicked.connect(self.load_quotations_data)

        buttons_layout.addWidget(self.add_quote_button)
        buttons_layout.addWidget(self.edit_quote_button)
        buttons_layout.addWidget(self.convert_button)
        buttons_layout.addWidget(self.refresh_button)

        layout.addLayout(buttons_layout)

        layout.addWidget(QLabel("أحدث عروض الأسعار:"))
        self.quotes_table = QTableWidget()
        self.quotes_table.setColumnCount(6)
        self.quotes_table.setHorizontalHeaderLabels(
            [
                "الحالة",
                "رقم العرض",
                "اسم العميل",
                "التاريخ",
                "تاريخ الانتهاء",
                "الإجمالي",
            ]
        )

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar
        self.search_bar = UniversalSearchBar(
            self.quotes_table,
            placeholder="🔍 بحث (الحالة، رقم العرض، العميل، التاريخ، الإجمالي)..."
        )
        layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===

        self.quotes_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.quotes_table.setAlternatingRowColors(True)
        h_header = self.quotes_table.horizontalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.quotes_table)

    def load_quotations_data(self):
        """⚡ تحميل عروض الأسعار في الخلفية لمنع التجميد"""
        print("INFO: [QuoteManager] جاري تحميل عروض الأسعار...")

        from PyQt6.QtWidgets import QApplication

        from core.data_loader import get_data_loader

        # تحضير الجدول
        self.quotes_table.setUpdatesEnabled(False)
        self.quotes_table.blockSignals(True)
        self.quotes_table.setRowCount(0)
        QApplication.processEvents()

        # دالة جلب البيانات
        def fetch_quotations():
            try:
                return self.quotation_service.get_all_quotations()
            except Exception as e:
                print(f"ERROR: [QuoteManager] فشل جلب عروض الأسعار: {e}")
                return []

        # دالة تحديث الواجهة
        def on_data_loaded(quotations):
            try:
                self.quotations_list = quotations

                colors_map = {
                    schemas.QuotationStatus.ACCEPTED: QColor("#0A6CF1"),
                    schemas.QuotationStatus.SENT: QColor("#3b82f6"),
                    schemas.QuotationStatus.DRAFT: QColor("#9ca3af"),
                    schemas.QuotationStatus.REJECTED: QColor("#ef4444"),
                }

                batch_size = 15
                for index, quote in enumerate(self.quotations_list):
                    self.quotes_table.insertRow(index)

                    status_item = QTableWidgetItem(quote.status.value)
                    status_color = colors_map.get(quote.status, colors_map[schemas.QuotationStatus.DRAFT])
                    status_item.setBackground(status_color)
                    if quote.status != schemas.QuotationStatus.DRAFT:
                        status_item.setForeground(QColor("white"))

                    self.quotes_table.setItem(index, 0, status_item)
                    self.quotes_table.setItem(index, 1, QTableWidgetItem(quote.quote_number))
                    self.quotes_table.setItem(index, 2, QTableWidgetItem(quote.client_id))
                    self.quotes_table.setItem(index, 3, QTableWidgetItem(quote.issue_date.strftime("%Y-%m-%d")))
                    self.quotes_table.setItem(index, 4, QTableWidgetItem(quote.expiry_date.strftime("%Y-%m-%d")))
                    self.quotes_table.setItem(index, 5, QTableWidgetItem(f"{quote.total_amount:,.2f} {quote.currency.value}"))

                    if (index + 1) % batch_size == 0:
                        QApplication.processEvents()

                print(f"INFO: [QuoteManager] ✅ تم تحميل {len(self.quotations_list)} عرض سعر.")

            except Exception as e:
                print(f"ERROR: [QuoteManager] فشل تحديث الجدول: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.quotes_table.blockSignals(False)
                self.quotes_table.setUpdatesEnabled(True)
                QApplication.processEvents()

        def on_error(error_msg):
            print(f"ERROR: [QuoteManager] فشل تحميل عروض الأسعار: {error_msg}")
            self.quotes_table.blockSignals(False)
            self.quotes_table.setUpdatesEnabled(True)

        # تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="quotations_list",
            load_function=fetch_quotations,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True
        )

    def _on_quotations_changed(self):
        """⚡ استجابة لإشارة تحديث عروض الأسعار - تحديث الجدول أوتوماتيك"""
        print("INFO: [QuoteManager] ⚡ استلام إشارة تحديث عروض الأسعار - جاري التحديث...")
        self.load_quotations_data()

    def open_quote_editor(self):
        print("INFO: [QuoteManager] جاري فتح شاشة عرض سعر (وضع جديد)...")
        dialog = QuotationEditorWindow(
            quotation_service=self.quotation_service,
            client_service=self.client_service,
            service_service=self.service_service,
            settings_service=self.settings_service,
            quote_to_edit=None,
            parent=self,
        )
        result = dialog.exec()

        if result:
            self.load_quotations_data()

    def open_quote_for_edit(self):
        """ (جديدة) تفتح نافذة عرض السعر في وضع تعديل. """
        selected_rows = self.quotes_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "خطأ", "الرجاء تحديد عرض سعر من الجدول أولاً")
            return

        selected_index = selected_rows[0].row()
        if selected_index >= len(self.quotations_list):
            QMessageBox.warning(self, "خطأ", "الرجاء تحديث البيانات ثم المحاولة مرة أخرى")
            return

        quote_to_edit = self.quotations_list[selected_index]

        if quote_to_edit.status == schemas.QuotationStatus.ACCEPTED:
            QMessageBox.critical(self, "خطأ", "لا يمكن تعديل عرض سعر تم قبوله وتحويله لفاتورة.")
            return

        print(f"INFO: [QuoteManager] جاري فتح شاشة عرض السعر (وضع تعديل) لـ: {quote_to_edit.quote_number}")

        dialog = QuotationEditorWindow(
            quotation_service=self.quotation_service,
            client_service=self.client_service,
            service_service=self.service_service,
            settings_service=self.settings_service,
            quote_to_edit=quote_to_edit,
            parent=self,
        )
        result = dialog.exec()

        if result:
            self.load_quotations_data()

    def convert_to_invoice(self):
        selected_rows = self.quotes_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "خطأ", "الرجاء تحديد عرض سعر من الجدول أولاً")
            return

        selected_index = selected_rows[0].row()
        quote_to_convert = self.quotations_list[selected_index]

        if quote_to_convert.status == schemas.QuotationStatus.ACCEPTED:
            QMessageBox.warning(self, "خطأ", "هذا العرض تم تحويله إلى فاتورة بالفعل.")
            return
        if quote_to_convert.status == schemas.QuotationStatus.REJECTED:
            QMessageBox.warning(self, "خطأ", "لا يمكن تحويل عرض سعر 'مرفوض'.")
            return

        reply = QMessageBox.question(
            self,
            "تأكيد التحويل",
            f"هل أنت متأكد أنك تريد تحويل عرض السعر رقم:\n{quote_to_convert.quote_number}\n\nإلى فاتورة جديدة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            self.quotation_service.convert_quotation_to_invoice(quote_to_convert)
            QMessageBox.information(
                self,
                "نجاح",
                "تم تحويل عرض السعر إلى فاتورة بنجاح.\nسيتم تحديث حالة عرض السعر إلى 'مقبول'.",
            )
            self.load_quotations_data()
        except Exception as e:
            print(f"ERROR: [QuoteManager] فشل تحويل عرض السعر: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل تحويل عرض السعر:\n{e}")
