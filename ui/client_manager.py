# الملف: ui/client_manager.py

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox, QGroupBox, QCheckBox,
    QApplication, QDialog
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QFont
from services.client_service import ClientService
from core import schemas
from typing import List, Optional

from ui.client_editor_dialog import ClientEditorDialog
from ui.styles import BUTTON_STYLES, TABLE_STYLE
import os





class ClientManagerTab(QWidget):
    """
    (معدل) التاب الخاص بإدارة العملاء (مع عمود اللوجو)
    """

    def __init__(self, client_service: ClientService, parent=None):
        super().__init__(parent)

        self.client_service = client_service
        self.clients_list: List[schemas.Client] = []
        self.selected_client: Optional[schemas.Client] = None

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
        self.add_button.clicked.connect(lambda: self.open_editor(client_to_edit=None))

        self.edit_button = QPushButton("✏️ تعديل العميل")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.clicked.connect(self.open_editor_for_selected)

        # زر التصدير
        self.export_button = QPushButton("📊 تصدير Excel")
        self.export_button.setStyleSheet(BUTTON_STYLES["success"])
        self.export_button.clicked.connect(self.export_clients)

        # زر الاستيراد
        self.import_button = QPushButton("📥 استيراد Excel")
        self.import_button.setStyleSheet(BUTTON_STYLES["info"])
        self.import_button.clicked.connect(self.import_clients)

        # زرار التحديث
        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.clicked.connect(self.load_clients_data)

        self.show_archived_checkbox = QCheckBox("إظهار العملاء المؤرشفين")
        self.show_archived_checkbox.clicked.connect(self.load_clients_data)

        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.edit_button)
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
        
        self.clients_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.clients_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.clients_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.clients_table.setAlternatingRowColors(True)
        self.clients_table.verticalHeader().setDefaultSectionSize(70)  # ⚡ ارتفاع الصفوف (تم تكبيره)
        self.clients_table.verticalHeader().setVisible(False)
        self.clients_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.clients_table.setColumnWidth(0, 70)
        self.clients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.clients_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.clients_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.clients_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.clients_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.clients_table.setColumnWidth(5, 150)
        self.clients_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.clients_table.setColumnWidth(6, 150)
        self.clients_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.clients_table.itemSelectionChanged.connect(self.on_client_selection_changed)
        
        # إضافة دبل كليك للتعديل
        self.clients_table.itemDoubleClicked.connect(self.open_editor_for_selected)

        table_layout.addWidget(self.clients_table)
        main_layout.addWidget(table_groupbox, 1)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_clients_data() - يتم استدعاؤها من MainWindow
        self.update_buttons_state(False)
    
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

    def on_client_selection_changed(self):
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
        """⚡ تحميل بيانات العملاء بشكل محسّن للسرعة"""
        print("INFO: [ClientManager] جاري تحميل بيانات العملاء...")
        
        # ⚡ منع التجميد - معالجة الأحداث
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            if self.show_archived_checkbox.isChecked():
                self.clients_list = self.client_service.get_archived_clients()
            else:
                self.clients_list = self.client_service.get_all_clients()

            # ⚡ تعطيل الترتيب مؤقتاً أثناء التحميل (للسرعة)
            self.clients_table.setSortingEnabled(False)
            self.clients_table.setRowCount(0)

            # ⚡ حساب الإجماليات بدون جلب كل الفواتير (استعلام SQL مباشر محسّن)
            client_invoices_total = {}
            client_payments_total = {}
            
            try:
                # ⚡ استعلام لحساب إجمالي المشاريع (total_amount) لكل عميل
                # نأخذ أحدث قيمة لكل مشروع بناءً على last_modified
                self.client_service.repo.sqlite_cursor.execute("""
                    SELECT client_id, SUM(total_amount) as total_projects
                    FROM (
                        SELECT p1._mongo_id, p1.client_id, p1.total_amount
                        FROM projects p1
                        INNER JOIN (
                            SELECT _mongo_id, MAX(last_modified) as max_date
                            FROM projects
                            WHERE _mongo_id IS NOT NULL AND _mongo_id != ''
                            GROUP BY _mongo_id
                        ) p2 ON p1._mongo_id = p2._mongo_id AND p1.last_modified = p2.max_date
                        WHERE p1.status != 'مؤرشف' AND p1.status != 'ملغي'
                        GROUP BY p1._mongo_id
                    )
                    GROUP BY client_id
                """)
                client_projects_total = {str(row[0]): float(row[1]) if row[1] else 0.0 
                                        for row in self.client_service.repo.sqlite_cursor.fetchall()}
                
                # ⚡ استعلام لحساب إجمالي المدفوعات لكل عميل من جدول الدفعات
                # نأخذ أحدث قيمة لكل دفعة بناءً على last_modified
                self.client_service.repo.sqlite_cursor.execute("""
                    SELECT client_id, SUM(amount) as total_paid
                    FROM (
                        SELECT p1._mongo_id, p1.client_id, p1.amount
                        FROM payments p1
                        INNER JOIN (
                            SELECT _mongo_id, MAX(last_modified) as max_date
                            FROM payments
                            WHERE _mongo_id IS NOT NULL AND _mongo_id != ''
                            GROUP BY _mongo_id
                        ) p2 ON p1._mongo_id = p2._mongo_id AND p1.last_modified = p2.max_date
                        WHERE p1.client_id IS NOT NULL AND p1.client_id != ''
                        GROUP BY p1._mongo_id
                    )
                    GROUP BY client_id
                """)
                client_payments_total = {str(row[0]): float(row[1]) if row[1] else 0.0 
                                        for row in self.client_service.repo.sqlite_cursor.fetchall()}
                
                # استخدام client_projects_total
                client_invoices_total = client_projects_total
                
                print(f"INFO: [ClientManager] === إجماليات العملاء ===")
                print(f"INFO: [ClientManager] مشاريع: {len(client_invoices_total)} عميل")
                print(f"INFO: [ClientManager] مدفوعات: {len(client_payments_total)} عميل")
                for name, total in client_invoices_total.items():
                    print(f"  📄 {name}: مشاريع={total:,.0f}, مدفوعات={client_payments_total.get(name, 0):,.0f}")
            except Exception as e:
                print(f"ERROR: فشل حساب الإجماليات: {e}")
                import traceback
                traceback.print_exc()

            for index, client in enumerate(self.clients_list):
                self.clients_table.insertRow(index)

                logo_label = QLabel()
                logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if client.logo_path and os.path.exists(client.logo_path):
                    pixmap = QPixmap(client.logo_path)
                    scaled_pixmap = pixmap.scaled(
                        QSize(50, 50),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    logo_label.setPixmap(scaled_pixmap)
                else:
                    logo_label.setText("🚫")
                    logo_label.setStyleSheet("font-size: 20px; color: #888;")

                self.clients_table.setCellWidget(index, 0, logo_label)

                self.clients_table.setItem(index, 1, QTableWidgetItem(client.name or ""))
                self.clients_table.setItem(index, 2, QTableWidgetItem(client.company_name or ""))
                self.clients_table.setItem(index, 3, QTableWidgetItem(client.phone or ""))
                self.clients_table.setItem(index, 4, QTableWidgetItem(client.email or ""))

                # ⚡ جلب إجماليات العميل - client_id في المشاريع = اسم العميل
                client_name = client.name
                
                # البحث بالاسم أولاً (الطريقة الأساسية)
                total_invoices = client_invoices_total.get(client_name, 0.0)
                total_payments = client_payments_total.get(client_name, 0.0)
                
                # عرض إجمالي الفواتير (المبلغ الإجمالي)
                total_item = QTableWidgetItem(f"{total_invoices:,.0f} ج.م")
                total_item.setData(Qt.ItemDataRole.UserRole, total_invoices)  # ⚡ للترتيب الرقمي
                total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                total_item.setForeground(QColor("#2454a5"))
                total_item.setFont(QFont("Cairo", 10, QFont.Weight.Bold))
                self.clients_table.setItem(index, 5, total_item)

                # عرض إجمالي المدفوعات
                payment_item = QTableWidgetItem(f"{total_payments:,.0f} ج.م")
                payment_item.setData(Qt.ItemDataRole.UserRole, total_payments)  # ⚡ للترتيب الرقمي
                payment_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                payment_item.setForeground(QColor("#00a876"))
                payment_item.setFont(QFont("Cairo", 10, QFont.Weight.Bold))
                self.clients_table.setItem(index, 6, payment_item)

                status_item = QTableWidgetItem(client.status.value)
                try:
                    if client.status == schemas.ClientStatus.ARCHIVED:
                        status_item.setBackground(QColor("#ef4444"))
                        status_item.setForeground(QColor("white"))
                    else:
                        status_item.setBackground(QColor("#0A6CF1"))
                        status_item.setForeground(QColor("white"))
                except Exception as e:
                    print(f"WARNING: فشل تعيين لون الخلفية: {e}")
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.clients_table.setItem(index, 7, status_item)

            print(f"INFO: [ClientManager] تم جلب {len(self.clients_list)} عميل.")
            
            # ⚡ إعادة تفعيل الترتيب بعد التحميل
            self.clients_table.setSortingEnabled(True)
            
            self.selected_client = None
            self.update_buttons_state(False)

        except Exception as e:
            print(f"ERROR: [ClientManager] فشل تحميل العملاء: {e}")
            # ⚡ إعادة تفعيل الترتيب حتى في حالة الخطأ
            self.clients_table.setSortingEnabled(True)

    def _on_clients_changed(self):
        """⚡ استجابة لإشارة تحديث العملاء - تحديث الجدول أوتوماتيك"""
        print("INFO: [ClientManager] ⚡ استلام إشارة تحديث العملاء - جاري التحديث...")
        self.load_clients_data()

    def open_editor(self, client_to_edit: Optional[schemas.Client]):
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
