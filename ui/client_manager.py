# الملف: ui/client_manager.py

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox, QGroupBox, QCheckBox,
    QApplication, QDialog
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QColor
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

        # زرار التحديث
        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.clicked.connect(self.load_clients_data)

        self.show_archived_checkbox = QCheckBox("إظهار العملاء المؤرشفين")
        self.show_archived_checkbox.clicked.connect(self.load_clients_data)

        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.edit_button)
        buttons_layout.addWidget(self.export_button)
        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.show_archived_checkbox)

        main_layout.addLayout(buttons_layout)

        table_groupbox = QGroupBox("قايمة العملاء")
        table_layout = QVBoxLayout()
        table_groupbox.setLayout(table_layout)

        # استخدام الجدول العادي (مؤقتاً حتى يتم حل مشكلة LazyTableWidget)
        self.clients_table = QTableWidget()
        self.clients_table.setColumnCount(6)
        self.clients_table.setHorizontalHeaderLabels(["اللوجو", "الاسم", "الشركة", "الهاتف", "الإيميل", "الحالة"])
        
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
        self.clients_table.verticalHeader().setDefaultSectionSize(60)
        self.clients_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.clients_table.setColumnWidth(0, 70)
        self.clients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.clients_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.clients_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.clients_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.clients_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.clients_table.itemSelectionChanged.connect(self.on_client_selection_changed)
        
        # إضافة دبل كليك للتعديل
        self.clients_table.itemDoubleClicked.connect(self.open_editor_for_selected)

        table_layout.addWidget(self.clients_table)
        main_layout.addWidget(table_groupbox, 1)

        self.load_clients_data()
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
        print("INFO: [ClientManager] جاري تحميل بيانات العملاء...")
        try:
            if self.show_archived_checkbox.isChecked():
                self.clients_list = self.client_service.get_archived_clients()
            else:
                self.clients_list = self.client_service.get_all_clients()

            self.clients_table.setRowCount(0)

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

                status_item = QTableWidgetItem(client.status.value)
                if client.status == schemas.ClientStatus.ARCHIVED:
                    status_item.setBackground(QColor("#ef4444"))
                    status_item.setForeground(QColor("white"))
                else:
                    status_item.setBackground(QColor("#10b981"))
                    status_item.setForeground(QColor("white"))
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.clients_table.setItem(index, 5, status_item)

            print(f"INFO: [ClientManager] تم جلب {len(self.clients_list)} عميل.")
            self.selected_client = None
            self.update_buttons_state(False)

        except Exception as e:
            print(f"ERROR: [ClientManager] فشل تحميل العملاء: {e}")

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
