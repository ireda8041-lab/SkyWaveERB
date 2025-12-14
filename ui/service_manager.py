"""الملف: ui/service_manager.py"""


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from core.logger import get_logger
from services.service_service import ServiceService
from ui.service_editor_dialog import ServiceEditorDialog
from ui.styles import BUTTON_STYLES, TABLE_STYLE_DARK, create_centered_item

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
        self.services_list: list[schemas.Service] = []
        self.selected_service: schemas.Service | None = None

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals
        app_signals.services_changed.connect(self._on_services_changed)

        buttons_layout = QHBoxLayout()

        self.add_button = QPushButton("➕ إضافة خدمة جديدة")
        self.add_button.setStyleSheet(BUTTON_STYLES["success"])
        self.add_button.setFixedHeight(28)
        self.add_button.clicked.connect(lambda: self.open_editor(service_to_edit=None))

        self.edit_button = QPushButton("✏️ تعديل الخدمة")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.open_editor_for_selected)

        self.archive_button = QPushButton("❌ أرشفة الخدمة")
        self.archive_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.archive_button.setFixedHeight(28)
        self.archive_button.clicked.connect(self.archive_selected_service)

        self.show_archived_checkbox = QCheckBox("إظهار الخدمات المؤرشفة")
        self.show_archived_checkbox.clicked.connect(self.load_services_data)

        # زرار التحديث
        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.setFixedHeight(28)
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

        self.services_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.services_table)
        self.services_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.services_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.services_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        h_header = self.services_table.horizontalHeader()
        v_header = self.services_table.verticalHeader()
        if h_header is not None:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # الاسم - يتمدد
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # الفئة
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # السعر
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
        if v_header is not None:
            v_header.setDefaultSectionSize(32)
            v_header.setVisible(False)
        self.services_table.itemSelectionChanged.connect(self.on_service_selection_changed)

        # إضافة دبل كليك للتعديل
        self.services_table.itemDoubleClicked.connect(self.open_editor_for_selected)

        table_layout.addWidget(self.services_table)
        main_layout.addWidget(table_groupbox, 1)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_services_data() - يتم استدعاؤها من MainWindow
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
        """⚡ تحميل بيانات الخدمات في الخلفية لمنع التجميد"""
        logger.info("[ServiceManager] جاري تحميل بيانات الخدمات")

        from PyQt6.QtWidgets import QApplication

        from core.data_loader import get_data_loader

        # تحضير الجدول
        self.services_table.setUpdatesEnabled(False)
        self.services_table.blockSignals(True)
        self.services_table.setRowCount(0)
        QApplication.processEvents()

        # دالة جلب البيانات
        def fetch_services():
            try:
                if self.show_archived_checkbox.isChecked():
                    return self.service_service.get_archived_services()
                else:
                    return self.service_service.get_all_services()
            except Exception as e:
                logger.error(f"[ServiceManager] فشل جلب الخدمات: {e}")
                return []

        # دالة تحديث الواجهة
        def on_data_loaded(services):
            try:
                self.services_list = services
                batch_size = 15

                for index, service in enumerate(self.services_list):
                    self.services_table.insertRow(index)

                    self.services_table.setItem(index, 0, create_centered_item(service.name))
                    self.services_table.setItem(index, 1, create_centered_item(service.category or ""))
                    self.services_table.setItem(index, 2, create_centered_item(f"{service.default_price:,.2f}"))

                    # الحالة مع لون الخلفية
                    bg_color = QColor("#ef4444") if service.status == schemas.ServiceStatus.ARCHIVED else None
                    status_item = create_centered_item(service.status.value, bg_color)
                    if service.status == schemas.ServiceStatus.ARCHIVED:
                        status_item.setForeground(QColor("white"))
                    self.services_table.setItem(index, 3, status_item)

                    self.services_table.setRowHeight(index, 40)

                    if (index + 1) % batch_size == 0:
                        QApplication.processEvents()

                logger.info(f"[ServiceManager] ✅ تم تحميل {len(self.services_list)} خدمة")
                self.update_buttons_state(False)

            except Exception as e:
                logger.error(f"[ServiceManager] فشل تحديث الجدول: {e}", exc_info=True)
            finally:
                self.services_table.blockSignals(False)
                self.services_table.setUpdatesEnabled(True)
                QApplication.processEvents()

        def on_error(error_msg):
            logger.error(f"[ServiceManager] فشل تحميل الخدمات: {error_msg}")
            self.services_table.blockSignals(False)
            self.services_table.setUpdatesEnabled(True)

        # تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="services_list",
            load_function=fetch_services,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True
        )

    def _on_services_changed(self):
        """⚡ استجابة لإشارة تحديث الخدمات - تحديث الجدول أوتوماتيك"""
        print("INFO: [ServiceManager] ⚡ استلام إشارة تحديث الخدمات - جاري التحديث...")
        self.load_services_data()

    def open_editor(self, service_to_edit: schemas.Service | None):
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
