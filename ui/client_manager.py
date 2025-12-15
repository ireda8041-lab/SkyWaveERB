# الملف: ui/client_manager.py

import os

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
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
    QWidget,
)

from core import schemas
from services.client_service import ClientService
from ui.client_editor_dialog import ClientEditorDialog
from ui.styles import BUTTON_STYLES, get_cairo_font, TABLE_STYLE_DARK, create_centered_item


class ClientManagerTab(QWidget):
    """
    (معدل) التاب الخاص بإدارة العملاء (مع عمود اللوجو)
    """

    def __init__(self, client_service: ClientService, parent=None):
        super().__init__(parent)

        self.client_service = client_service
        self.clients_list: list[schemas.Client] = []
        self.selected_client: schemas.Client | None = None

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals
        app_signals.clients_changed.connect(self._on_clients_changed)


        buttons_layout = QHBoxLayout()

        self.add_button = QPushButton("➕ إضافة عميل جديد")
        self.add_button.setStyleSheet(BUTTON_STYLES["success"])
        self.add_button.setFixedHeight(28)
        self.add_button.clicked.connect(lambda: self.open_editor(client_to_edit=None))

        self.edit_button = QPushButton("✏️ تعديل العميل")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.open_editor_for_selected)

        # زر الحذف الاحترافي
        self.delete_button = QPushButton("🗑️ حذف العميل")
        self.delete_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_button.setFixedHeight(28)
        self.delete_button.clicked.connect(self.delete_selected_client)
        self.delete_button.setEnabled(False)  # معطل حتى يتم اختيار عميل

        # زر التصدير
        self.export_button = QPushButton("📊 تصدير Excel")
        self.export_button.setStyleSheet(BUTTON_STYLES["success"])
        self.export_button.setFixedHeight(28)
        self.export_button.clicked.connect(self.export_clients)

        # زر الاستيراد
        self.import_button = QPushButton("📥 استيراد Excel")
        self.import_button.setStyleSheet(BUTTON_STYLES["info"])
        self.import_button.setFixedHeight(28)
        self.import_button.clicked.connect(self.import_clients)

        # زرار التحديث
        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.setFixedHeight(28)
        self.refresh_button.clicked.connect(self.load_clients_data)

        self.show_archived_checkbox = QCheckBox("إظهار العملاء المؤرشفين")
        self.show_archived_checkbox.clicked.connect(self.load_clients_data)

        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.edit_button)
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addWidget(self.export_button)
        buttons_layout.addWidget(self.import_button)
        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.show_archived_checkbox)

        main_layout.addLayout(buttons_layout)

        table_groupbox = QGroupBox("قايمة العملاء")
        table_layout = QVBoxLayout()
        table_groupbox.setLayout(table_layout)

        # استخدام الجدول العادي مع تفعيل الترتيب
        self.clients_table = QTableWidget()
        self.clients_table.setColumnCount(8)
        self.clients_table.setHorizontalHeaderLabels(["اللوجو", "الاسم", "الشركة", "الهاتف", "الإيميل", "💰 إجمالي المشاريع", "✅ إجمالي المدفوعات", "الحالة"])

        # ⚡ تفعيل الترتيب بالضغط على رأس العمود
        self.clients_table.setSortingEnabled(True)

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar
        self.search_bar = UniversalSearchBar(
            self.clients_table,
            placeholder="🔍 بحث (الاسم، الشركة، الهاتف، الإيميل)..."
        )
        table_layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===

        self.clients_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.clients_table)
        self.clients_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.clients_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.clients_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.clients_table.setAlternatingRowColors(True)
        v_header = self.clients_table.verticalHeader()
        if v_header is not None:
            v_header.setDefaultSectionSize(50)
            v_header.setVisible(False)
        h_header = self.clients_table.horizontalHeader()
        if h_header is not None:
            # اللوجو ثابت، الاسم والشركة والإيميل يتمددون، الباقي بحجم المحتوى
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # اللوجو
            self.clients_table.setColumnWidth(0, 70)
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # الاسم - يتمدد
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # الشركة - يتمدد
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # الهاتف
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # الإيميل - يتمدد
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # إجمالي المشاريع
            h_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # إجمالي المدفوعات
            h_header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
        self.clients_table.itemSelectionChanged.connect(self.on_client_selection_changed)

        # إضافة دبل كليك للتعديل
        self.clients_table.itemDoubleClicked.connect(self.open_editor_for_selected)
        
        # إضافة قائمة السياق (كليك يمين)
        self._setup_context_menu()

        table_layout.addWidget(self.clients_table)
        main_layout.addWidget(table_groupbox, 1)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_clients_data() - يتم استدعاؤها من MainWindow
        self.update_buttons_state(False)

    def _setup_context_menu(self):
        """إعداد قائمة السياق (كليك يمين) للجدول"""
        from core.context_menu import ContextMenuManager
        
        ContextMenuManager.setup_table_context_menu(
            table=self.clients_table,
            on_view=self.open_editor_for_selected,
            on_edit=self.open_editor_for_selected,
            on_delete=self.delete_selected_client,
            on_refresh=self.load_clients_data,
            on_export=self.export_clients
        )

    def export_clients(self):
        """تصدير العملاء إلى Excel"""
        try:
            # الحصول على خدمة التصدير من النافذة الرئيسية
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'export_service'):
                main_window = main_window.parent()

            export_service = getattr(main_window, 'export_service', None) if main_window else None

            if not export_service:
                QMessageBox.warning(self, "خدمة التصدير غير متوفرة", "يرجى تثبيت pandas: pip install pandas openpyxl")
                return

            # تصدير العملاء
            filepath = export_service.export_clients_to_excel(self.clients_list)

            if filepath:
                reply = QMessageBox.question(
                    self,
                    "تم التصدير",
                    f"تم تصدير {len(self.clients_list)} عميل بنجاح إلى:\n{filepath}\n\nهل تريد فتح الملف؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    export_service.open_file(filepath)
            else:
                QMessageBox.warning(self, "خطأ", "فشل في تصدير البيانات")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في التصدير:\n{str(e)}")

    def import_clients(self):
        """استيراد العملاء من ملف Excel"""
        try:
            from PyQt6.QtWidgets import QFileDialog

            # الحصول على خدمة التصدير من النافذة الرئيسية
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'export_service'):
                main_window = main_window.parent()

            export_service = getattr(main_window, 'export_service', None) if main_window else None

            if not export_service:
                QMessageBox.warning(self, "خدمة الاستيراد غير متوفرة", "يرجى تثبيت pandas: pip install pandas openpyxl")
                return

            # اختيار ملف Excel
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "اختر ملف Excel للاستيراد",
                "",
                "Excel Files (*.xlsx *.xls)"
            )

            if not filepath:
                return

            # استيراد البيانات
            clients_data, errors = export_service.import_clients_from_excel(filepath)

            if errors:
                error_msg = "\n".join(errors[:10])  # عرض أول 10 أخطاء
                if len(errors) > 10:
                    error_msg += f"\n... و {len(errors) - 10} خطأ آخر"

                reply = QMessageBox.question(
                    self,
                    "تحذير",
                    f"تم العثور على {len(errors)} خطأ:\n\n{error_msg}\n\nهل تريد المتابعة باستيراد البيانات الصحيحة ({len(clients_data)} عميل)؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.No:
                    return

            if not clients_data:
                QMessageBox.warning(self, "لا توجد بيانات", "لم يتم العثور على بيانات صحيحة للاستيراد")
                return

            # استيراد العملاء
            success_count = 0
            failed_count = 0

            for client_dict in clients_data:
                try:
                    # إنشاء عميل جديد
                    client = schemas.Client(**client_dict)
                    self.client_service.create_client(client)
                    success_count += 1
                except Exception as e:
                    print(f"ERROR: فشل استيراد عميل {client_dict.get('name')}: {e}")
                    failed_count += 1

            # تحديث الجدول
            self.load_clients_data()

            # عرض النتيجة
            result_msg = f"✅ تم استيراد {success_count} عميل بنجاح"
            if failed_count > 0:
                result_msg += f"\n❌ فشل استيراد {failed_count} عميل"

            QMessageBox.information(self, "نتيجة الاستيراد", result_msg)

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في الاستيراد:\n{str(e)}")

    def update_buttons_state(self, has_selection: bool):
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def on_client_selection_changed(self):
        # ⚡ تجاهل التحديث إذا كان الكليك يمين
        from core.context_menu import is_right_click_active
        if is_right_click_active():
            return
        
        selected_rows = self.clients_table.selectedIndexes()
        if selected_rows:
            selected_index = selected_rows[0].row()
            if 0 <= selected_index < len(self.clients_list):
                self.selected_client = self.clients_list[selected_index]
                self.update_buttons_state(True)
                return
        self.selected_client = None
        self.update_buttons_state(False)

    def load_clients_data(self):
        """⚡ تحميل بيانات العملاء في الخلفية لمنع التجميد"""
        print("INFO: [ClientManager] جاري تحميل بيانات العملاء...")

        from core.data_loader import get_data_loader

        # تحضير الجدول
        self.clients_table.setSortingEnabled(False)
        self.clients_table.setUpdatesEnabled(False)
        self.clients_table.blockSignals(True)
        self.clients_table.setRowCount(0)
        QApplication.processEvents()

        # دالة جلب البيانات (تعمل في الخلفية)
        def fetch_clients():
            try:
                # جلب العملاء
                if self.show_archived_checkbox.isChecked():
                    clients = self.client_service.get_archived_clients()
                else:
                    clients = self.client_service.get_all_clients()

                # جلب الإجماليات
                client_invoices_total = {}
                client_payments_total = {}

                try:
                    # ⚡ استخدام cursor منفصل لتجنب مشكلة Recursive cursor
                    cursor = self.client_service.repo.get_cursor()
                    try:
                        cursor.execute("""
                            SELECT client_id, SUM(total_amount) as total_projects
                            FROM projects
                            WHERE status != 'مؤرشف' AND status != 'ملغي'
                            GROUP BY client_id
                        """)
                        client_invoices_total = {str(row[0]): float(row[1]) if row[1] else 0.0
                                                for row in cursor.fetchall()}

                        cursor.execute("""
                            SELECT client_id, SUM(amount) as total_paid
                            FROM payments
                            WHERE client_id IS NOT NULL AND client_id != ''
                            GROUP BY client_id
                        """)
                        client_payments_total = {str(row[0]): float(row[1]) if row[1] else 0.0
                                                for row in cursor.fetchall()}
                    finally:
                        cursor.close()
                except Exception as e:
                    print(f"ERROR: فشل حساب الإجماليات: {e}")

                return {
                    'clients': clients,
                    'invoices_total': client_invoices_total,
                    'payments_total': client_payments_total
                }
            except Exception as e:
                print(f"ERROR: [ClientManager] فشل جلب العملاء: {e}")
                return {'clients': [], 'invoices_total': {}, 'payments_total': {}}

        # دالة تحديث الواجهة
        def on_data_loaded(data):
            try:
                self.clients_list = data['clients']
                client_invoices_total = data['invoices_total']
                client_payments_total = data['payments_total']

                self._populate_clients_table(client_invoices_total, client_payments_total)

            except Exception as e:
                print(f"ERROR: [ClientManager] فشل تحديث الجدول: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.clients_table.blockSignals(False)
                self.clients_table.setUpdatesEnabled(True)
                self.clients_table.setSortingEnabled(True)

        def on_error(error_msg):
            print(f"ERROR: [ClientManager] فشل تحميل العملاء: {error_msg}")
            self.clients_table.blockSignals(False)
            self.clients_table.setUpdatesEnabled(True)
            self.clients_table.setSortingEnabled(True)

        # تحميل البيانات في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="clients_list",
            load_function=fetch_clients,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True
        )

    def _populate_clients_table(self, client_invoices_total, client_payments_total):
        """ملء جدول العملاء بالبيانات"""

        # ⚡ تحميل البيانات على دفعات لمنع التجميد
        batch_size = 15
        for index, client in enumerate(self.clients_list):
            self.clients_table.insertRow(index)

            logo_label = QLabel()
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pixmap = None

            # أولاً: محاولة تحميل الصورة من base64 (للمزامنة بين الأجهزة)
            if hasattr(client, 'logo_data') and client.logo_data:
                try:
                    import base64
                    # إزالة prefix إذا وجد
                    logo_data = client.logo_data
                    if ',' in logo_data:
                        logo_data = logo_data.split(',')[1]

                    img_bytes = base64.b64decode(logo_data)
                    pixmap = QPixmap()
                    pixmap.loadFromData(img_bytes)
                except Exception:
                    # ⚡ تجاهل الخطأ بصمت لتجنب البطء
                    pixmap = None

            # ثانياً: محاولة تحميل الصورة من المسار المحلي (للتوافق القديم)
            if not pixmap or pixmap.isNull():
                if client.logo_path and os.path.exists(client.logo_path):
                    pixmap = QPixmap(client.logo_path)

            # عرض الصورة أو أيقونة افتراضية
            if pixmap and not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    QSize(50, 50),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                logo_label.setPixmap(scaled_pixmap)
            else:
                logo_label.setText("👤")
                logo_label.setStyleSheet("font-size: 24px; color: #0A6CF1;")

            self.clients_table.setCellWidget(index, 0, logo_label)

            # ⚡ معالجة الأحداث كل batch_size صف
            if (index + 1) % batch_size == 0:
                QApplication.processEvents()  # noqa: F823

            self.clients_table.setItem(index, 1, create_centered_item(client.name or ""))
            self.clients_table.setItem(index, 2, create_centered_item(client.company_name or ""))
            self.clients_table.setItem(index, 3, create_centered_item(client.phone or ""))
            self.clients_table.setItem(index, 4, create_centered_item(client.email or ""))

            # ⚡ جلب إجماليات العميل
            client_name = client.name
            total_invoices = client_invoices_total.get(client_name, 0.0)
            total_payments = client_payments_total.get(client_name, 0.0)

            # عرض إجمالي الفواتير
            total_item = create_centered_item(f"{total_invoices:,.0f} ج.م")
            total_item.setData(Qt.ItemDataRole.UserRole, total_invoices)
            total_item.setForeground(QColor("#2454a5"))
            total_item.setFont(get_cairo_font(10, bold=True))
            self.clients_table.setItem(index, 5, total_item)

            # عرض إجمالي المدفوعات
            payment_item = create_centered_item(f"{total_payments:,.0f} ج.م")
            payment_item.setData(Qt.ItemDataRole.UserRole, total_payments)
            payment_item.setForeground(QColor("#00a876"))
            payment_item.setFont(get_cairo_font(10, bold=True))
            self.clients_table.setItem(index, 6, payment_item)

            # الحالة مع لون الخلفية
            bg_color = QColor("#ef4444") if client.status == schemas.ClientStatus.ARCHIVED else QColor("#0A6CF1")
            status_item = create_centered_item(client.status.value, bg_color)
            status_item.setForeground(QColor("white"))
            self.clients_table.setItem(index, 7, status_item)

        print(f"INFO: [ClientManager] ✅ تم تحميل {len(self.clients_list)} عميل.")

        # QApplication مستورد في أعلى الملف
        QApplication.processEvents()

        self.selected_client = None
        self.update_buttons_state(False)

    def _on_clients_changed(self):
        """⚡ استجابة لإشارة تحديث العملاء - تحديث الجدول أوتوماتيك"""
        print("INFO: [ClientManager] ⚡ استلام إشارة تحديث العملاء - جاري التحديث...")
        self.load_clients_data()

    def open_editor(self, client_to_edit: schemas.Client | None):
        dialog = ClientEditorDialog(
            client_service=self.client_service,
            client_to_edit=client_to_edit,
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_clients_data()

    def open_editor_for_selected(self):
        if not self.selected_client:
            QMessageBox.warning(self, "تحذير", "يرجى تحديد عميل من الجدول أولاً.")
            return
        self.open_editor(self.selected_client)

    def delete_selected_client(self):
        """حذف العميل المحدد بشكل احترافي"""
        if not self.selected_client:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار عميل للحذف")
            return

        # رسالة تأكيد احترافية
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("⚠️ تأكيد الحذف")
        msg.setText(f"هل أنت متأكد من حذف العميل؟")
        msg.setInformativeText(
            f"العميل: {self.selected_client.name}\n"
            f"الشركة: {self.selected_client.company_name or 'غير محدد'}\n\n"
            f"⚠️ تحذير: هذا الإجراء لا يمكن التراجع عنه!"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        
        # تخصيص الأزرار
        yes_button = msg.button(QMessageBox.StandardButton.Yes)
        yes_button.setText("نعم، احذف")
        no_button = msg.button(QMessageBox.StandardButton.No)
        no_button.setText("إلغاء")

        reply = msg.exec()

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # ⚡ استخدام المعرف الصحيح (_mongo_id أو id)
                client_id = getattr(self.selected_client, '_mongo_id', None) or str(self.selected_client.id)
                self.client_service.delete_client(client_id)
                
                # رسالة نجاح
                QMessageBox.information(
                    self,
                    "✅ تم الحذف",
                    f"تم حذف العميل '{self.selected_client.name}' بنجاح"
                )
                
                # تحديث الجدول
                self.selected_client = None
                self.load_clients_data()
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "❌ خطأ",
                    f"فشل حذف العميل:\n{str(e)}"
                )

    def _on_clients_changed(self):
        """تحديث الجدول عند تغيير البيانات"""
        self.load_clients_data()
