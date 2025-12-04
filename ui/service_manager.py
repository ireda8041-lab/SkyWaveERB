"""الملف: ui/service_manager.py"""

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QMessageBox,
    QGroupBox,
    QCheckBox,
    QDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from services.service_service import ServiceService
from core import schemas
from core.logger import get_logger
from typing import List, Optional

from ui.service_editor_dialog import ServiceEditorDialog
from ui.styles import BUTTON_STYLES, TABLE_STYLE

logger = get_logger(__name__)


class ServiceManagerTab(QWidget):
    """
    تاب إدارة الخدمات باستخدام محرر منبثق وحالة أرشيف.
    """

    def __init__(self, service_service: ServiceService, parent=None):
        """
        تهيئة تاب إدارة الخدمات
        
        Args:
            service_service: خدمة الخدمات للتعامل مع البيانات
            parent: الويدجت الأب
        """
        super().__init__(parent)

        self.service_service = service_service
        self.services_list: List[schemas.Service] = []
        self.selected_service: Optional[schemas.Service] = None

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


        buttons_layout = QHBoxLayout()

        self.add_button = QPushButton("➕ إضافة خدمة جديدة")
        self.add_button.setStyleSheet(BUTTON_STYLES["success"])
        self.add_button.clicked.connect(lambda: self.open_editor(service_to_edit=None))

        self.edit_button = QPushButton("✏️ تعديل الخدمة")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.clicked.connect(self.open_editor_for_selected)

        self.archive_button = QPushButton("❌ أرشفة الخدمة")
        self.archive_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.archive_button.clicked.connect(self.archive_selected_service)

        self.show_archived_checkbox = QCheckBox("إظهار الخدمات المؤرشفة")
        self.show_archived_checkbox.clicked.connect(self.load_services_data)

        # زرار التحديث
        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.clicked.connect(self.load_services_data)

        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.edit_button)
        buttons_layout.addWidget(self.archive_button)
        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.show_archived_checkbox)

        main_layout.addLayout(buttons_layout)

        table_groupbox = QGroupBox("قايمة الخدمات والباقات")
        table_layout = QVBoxLayout()
        table_groupbox.setLayout(table_layout)

        self.services_table = QTableWidget()
        self.services_table.setColumnCount(4)
        self.services_table.setHorizontalHeaderLabels(
            ["الاسم", "الفئة", "السعر الافتراضي", "الحالة"]
        )
        
        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar
        self.search_bar = UniversalSearchBar(
            self.services_table,
            placeholder="🔍 بحث (الاسم، الفئة، السعر، الحالة)..."
        )
        table_layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===
        
        self.services_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.services_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.services_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.services_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.services_table.itemSelectionChanged.connect(self.on_service_selection_changed)
        
        # إضافة دبل كليك للتعديل
        self.services_table.itemDoubleClicked.connect(self.open_editor_for_selected)

        table_layout.addWidget(self.services_table)
        main_layout.addWidget(table_groupbox, 1)

        self.load_services_data()
        self.update_buttons_state(False)

    def update_buttons_state(self, has_selection: bool):
        self.edit_button.setEnabled(has_selection)
        self.archive_button.setEnabled(has_selection)

    def on_service_selection_changed(self):
        selected_rows = self.services_table.selectedIndexes()
        if selected_rows:
            selected_index = selected_rows[0].row()
            if 0 <= selected_index < len(self.services_list):
                self.selected_service = self.services_list[selected_index]
                self.update_buttons_state(True)
                return
        self.selected_service = None
        self.update_buttons_state(False)

    def load_services_data(self) -> None:
        """
        تحميل بيانات الخدمات من قاعدة البيانات وعرضها في الجدول
        """
        logger.info("[ServiceManager] جاري تحميل بيانات الخدمات")
        try:
            if self.show_archived_checkbox.isChecked():
                self.services_list = self.service_service.get_archived_services()
            else:
                self.services_list = self.service_service.get_all_services()

            self.services_table.setRowCount(0)
            for index, service in enumerate(self.services_list):
                self.services_table.insertRow(index)
                
                # Name item - centered
                name_item = QTableWidgetItem(service.name)
                name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.services_table.setItem(index, 0, name_item)
                
                # Category item - centered
                category_item = QTableWidgetItem(service.category or "")
                category_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.services_table.setItem(index, 1, category_item)
                
                # Price item - centered
                price_item = QTableWidgetItem(f"{service.default_price:,.2f}")
                price_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.services_table.setItem(index, 2, price_item)

                # Status item - centered
                status_item = QTableWidgetItem(service.status.value)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if service.status == schemas.ServiceStatus.ARCHIVED:
                    status_item.setBackground(QColor("#ef4444"))
                    status_item.setForeground(QColor("white"))
                self.services_table.setItem(index, 3, status_item)
                
                # Set row height for breathing room
                self.services_table.setRowHeight(index, 40)

            logger.info(f"[ServiceManager] تم جلب {len(self.services_list)} خدمة")
            self.update_buttons_state(False)
        except Exception as e:
            logger.error(f"[ServiceManager] فشل تحميل الخدمات: {e}", exc_info=True)

    def open_editor(self, service_to_edit: Optional[schemas.Service]):
        dialog = ServiceEditorDialog(
            service_service=self.service_service,
            service_to_edit=service_to_edit,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_services_data()

    def open_editor_for_selected(self):
        if self.selected_service:
            self.open_editor(self.selected_service)
        else:
            QMessageBox.warning(self, "تنبيه", "يرجى اختيار خدمة أولاً")

    def archive_selected_service(self) -> None:
        """
        أرشفة الخدمة المحددة
        """
        if not self.selected_service:
            QMessageBox.warning(self, "تنبيه", "يرجى اختيار خدمة لأرشفتها")
            return

        reply = QMessageBox.question(
            self,
            "تأكيد الأرشفة",
            f"هل تريد أرشفة الخدمة:\n{self.selected_service.name}?\n\nستختفي من قوايم الإنشاء.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            service_id = self.selected_service._mongo_id or str(self.selected_service.id)
            self.service_service.delete_service(service_id)
            QMessageBox.information(self, "تم", "تمت الأرشفة بنجاح")
            logger.info(f"[ServiceManager] تم أرشفة الخدمة: {self.selected_service.name}")
            self.load_services_data()
        except Exception as e:
            logger.error(f"[ServiceManager] فشل أرشفة الخدمة: {e}", exc_info=True)
            QMessageBox.critical(self, "خطأ", f"فشل الأرشفة: {e}")
