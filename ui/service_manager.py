"""الملف: ui/service_manager.py"""

import time

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from core.logger import get_logger
from services.service_service import ServiceService
from ui.service_editor_dialog import ServiceEditorDialog
from ui.styles import BUTTON_STYLES, TABLE_STYLE_DARK, create_centered_item

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


logger = get_logger(__name__)


class ServiceManagerTab(QWidget):
    """
    تاب إدارة الخدمات باستخدام محرر منبثق وحالة أرشيف.
    """

    _services_loaded_signal = pyqtSignal(object, bool)
    _services_load_error_signal = pyqtSignal(str, bool)

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
        self._services_cache: dict[str, list[schemas.Service]] = {}
        self._services_cache_ts: dict[str, float] = {}
        self._services_cache_ttl_s = 20.0
        self._current_page = 1
        self._page_size = 100
        self._current_page_services: list[schemas.Service] = []
        self._load_in_progress = False
        self._queued_reload_force = False
        self._last_load_started_at = 0.0
        self._min_reload_interval_s = 1.2
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._flush_queued_reload)
        self._services_loaded_signal.connect(self._on_services_loaded_ui)
        self._services_load_error_signal.connect(self._on_services_load_error_ui)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals

        app_signals.safe_connect(app_signals.services_changed, self._on_services_changed)

        # === شريط الأزرار المتجاوب ===
        from ui.responsive_toolbar import ResponsiveToolbar

        self.toolbar = ResponsiveToolbar()

        self.add_button = QPushButton("➕ إضافة خدمة")
        self.add_button.setStyleSheet(BUTTON_STYLES["success"])
        self.add_button.setFixedHeight(28)
        self.add_button.clicked.connect(lambda: self.open_editor(service_to_edit=None))

        self.edit_button = QPushButton("✏️ تعديل الخدمة")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.open_editor_for_selected)

        self.archive_button = QPushButton("📦 أرشفة الخدمة")
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

        # إضافة الأزرار للـ toolbar المتجاوب
        self.toolbar.addButton(self.add_button)
        self.toolbar.addButton(self.edit_button)
        self.toolbar.addButton(self.archive_button)
        self.toolbar.addButton(self.refresh_button)
        self.toolbar.addWidget(self.show_archived_checkbox)

        main_layout.addWidget(self.toolbar)

        table_groupbox = QGroupBox("قايمة الخدمات والباقات")
        table_layout = QVBoxLayout()
        table_groupbox.setLayout(table_layout)

        self.services_table = QTableWidget()
        self.services_table.setColumnCount(5)
        self.services_table.setHorizontalHeaderLabels(
            ["الاسم", "الوصف", "الفئة", "السعر الافتراضي", "الحالة"]
        )

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar

        self.search_bar = UniversalSearchBar(
            self.services_table, placeholder="🔍 بحث (الاسم، الفئة، السعر، الحالة)..."
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
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # الاسم
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # الوصف - يتمدد
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # الفئة
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # السعر
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
        if v_header is not None:
            v_header.setDefaultSectionSize(32)
            v_header.setVisible(False)
        self.services_table.itemSelectionChanged.connect(self.on_service_selection_changed)

        # إضافة دبل كليك للتعديل
        self.services_table.itemDoubleClicked.connect(self.open_editor_for_selected)

        # ⚡ إضافة قائمة السياق (كليك يمين)
        self._setup_context_menu()

        table_layout.addWidget(self.services_table)
        main_layout.addWidget(table_groupbox, 1)

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
        self.page_info_label.setStyleSheet("color: #94a3b8;")

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
        main_layout.addLayout(pagination_layout)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_services_data() - يتم استدعاؤها من MainWindow
        self.update_buttons_state(False)

        # ⚡ تطبيق محاذاة النص لليمين على كل الحقول
        from ui.styles import apply_rtl_alignment_to_all_fields

        apply_rtl_alignment_to_all_fields(self)

    def _setup_context_menu(self):
        """إعداد قائمة السياق (كليك يمين) للجدول"""
        from core.context_menu import ContextMenuManager

        ContextMenuManager.setup_table_context_menu(
            table=self.services_table,
            on_view=self.open_editor_for_selected,
            on_edit=self.open_editor_for_selected,
            on_refresh=self.load_services_data,
        )

    def update_buttons_state(self, has_selection: bool):
        self.edit_button.setEnabled(has_selection)
        self.archive_button.setEnabled(has_selection)

    def on_service_selection_changed(self):
        # ⚡ تجاهل التحديث إذا كان الكليك يمين
        from core.context_menu import is_right_click_active

        if is_right_click_active():
            return

        selected_rows = self.services_table.selectedIndexes()
        if selected_rows:
            selected_index = selected_rows[0].row()
            if 0 <= selected_index < len(self._current_page_services):
                self.selected_service = self._current_page_services[selected_index]
                self.update_buttons_state(True)
                return
        self.selected_service = None
        self.update_buttons_state(False)

    def load_services_data(self, force_refresh: bool = False) -> None:
        """⚡ تحميل بيانات الخدمات في الخلفية لمنع التجميد"""
        force_refresh = bool(force_refresh)
        now = time.monotonic()

        if self._load_in_progress:
            self._queued_reload_force = self._queued_reload_force or force_refresh
            self._schedule_reload(350)
            return

        elapsed = now - self._last_load_started_at
        if elapsed < self._min_reload_interval_s:
            self._queued_reload_force = self._queued_reload_force or force_refresh
            remaining_ms = int((self._min_reload_interval_s - elapsed) * 1000) + 80
            self._schedule_reload(max(120, remaining_ms))
            return

        self._load_in_progress = True
        self._last_load_started_at = now
        logger.debug("[ServiceManager] تحميل بيانات الخدمات...")

        from core.data_loader import get_data_loader

        # تحضير الجدول
        sorting_enabled = self.services_table.isSortingEnabled()
        if sorting_enabled:
            self.services_table.setSortingEnabled(False)
        self.services_table.setUpdatesEnabled(False)
        self.services_table.blockSignals(True)
        self.services_table.setRowCount(0)

        # دالة جلب البيانات
        def fetch_services():
            try:
                if self.show_archived_checkbox.isChecked():
                    return self.service_service.get_archived_services()
                else:
                    return self.service_service.get_all_services()
            except Exception as e:
                logger.error("[ServiceManager] فشل جلب الخدمات: %s", e)
                return []

        # دالة تحديث الواجهة
        def on_data_loaded(services):
            self._services_loaded_signal.emit(services, sorting_enabled)

        def on_error(error_msg):
            self._services_load_error_signal.emit(str(error_msg), sorting_enabled)

        if force_refresh:
            self._services_cache.clear()
            self._services_cache_ts.clear()
            if hasattr(self.service_service, "invalidate_cache"):
                self.service_service.invalidate_cache()

        cache_key = "archived" if self.show_archived_checkbox.isChecked() else "active"
        cached = self._get_cached_services(cache_key)
        if cached is not None and not force_refresh:
            on_data_loaded(cached)
            return

        # تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="services_list",
            load_function=fetch_services,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _schedule_reload(self, delay_ms: int = 250) -> None:
        if self._reload_timer.isActive():
            return
        self._reload_timer.start(max(100, int(delay_ms)))

    def _flush_queued_reload(self) -> None:
        if self._load_in_progress:
            self._schedule_reload(250)
            return
        force_refresh = bool(self._queued_reload_force)
        self._queued_reload_force = False
        self.load_services_data(force_refresh=force_refresh)

    def _complete_load_cycle(self) -> None:
        self._load_in_progress = False
        if self._queued_reload_force:
            self._schedule_reload(120)
        elif self._reload_timer.isActive():
            self._reload_timer.stop()

    def _on_services_loaded_ui(self, services, sorting_enabled: bool) -> None:
        try:
            self.services_list = services or []
            self._render_current_page()
            logger.debug("[ServiceManager] ✅ تم تحميل %s خدمة", len(self.services_list))
            self.update_buttons_state(False)
            cache_key = "archived" if self.show_archived_checkbox.isChecked() else "active"
            self._set_cached_services(cache_key, self.services_list)
        except Exception as e:
            logger.error("[ServiceManager] فشل تحديث الجدول: %s", e, exc_info=True)
        finally:
            self.services_table.blockSignals(False)
            self.services_table.setUpdatesEnabled(True)
            if sorting_enabled:
                self.services_table.setSortingEnabled(True)
            self._complete_load_cycle()

    def _on_services_load_error_ui(self, error_msg: str, sorting_enabled: bool) -> None:
        try:
            logger.error("[ServiceManager] فشل تحميل الخدمات: %s", error_msg)
        finally:
            self.services_table.blockSignals(False)
            self.services_table.setUpdatesEnabled(True)
            if sorting_enabled:
                self.services_table.setSortingEnabled(True)
            self._complete_load_cycle()

    def _get_total_pages(self) -> int:
        total = len(self.services_list)
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
            page_services = self.services_list
        else:
            start_index = (self._current_page - 1) * self._page_size
            end_index = start_index + self._page_size
            page_services = self.services_list[start_index:end_index]

        self._current_page_services = page_services
        self._populate_services_table(page_services)
        self._update_pagination_controls(total_pages)

    def _populate_services_table(self, services: list[schemas.Service]):
        self.services_table.setRowCount(len(services))
        for index, service in enumerate(services):
            self.services_table.setItem(index, 0, create_centered_item(service.name))

            description = service.description or ""
            description = description.strip()
            if description:
                display_desc = description[:50] + "..." if len(description) > 50 else description
                desc_item = create_centered_item(display_desc)
                desc_item.setToolTip(description)
            else:
                desc_item = create_centered_item("-")
                desc_item.setForeground(QColor("#666666"))
            self.services_table.setItem(index, 1, desc_item)

            self.services_table.setItem(index, 2, create_centered_item(service.category or ""))
            self.services_table.setItem(
                index, 3, create_centered_item(f"{service.default_price:,.2f}")
            )

            bg_color = (
                QColor("#ef4444") if service.status == schemas.ServiceStatus.ARCHIVED else None
            )
            status_item = create_centered_item(service.status.value, bg_color)
            if service.status == schemas.ServiceStatus.ARCHIVED:
                status_item.setForeground(QColor("white"))
            self.services_table.setItem(index, 4, status_item)
            self.services_table.setRowHeight(index, 40)

    def _update_pagination_controls(self, total_pages: int):
        self.page_info_label.setText(f"صفحة {self._current_page} / {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

    def _on_page_size_changed(self, value: str):
        if value == "كل":
            self._page_size = max(1, len(self.services_list))
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

    def _on_services_changed(self):
        """⚡ استجابة لإشارة تحديث الخدمات - تحديث الجدول أوتوماتيك"""
        if not self.isVisible():
            if hasattr(self.service_service, "invalidate_cache"):
                self.service_service.invalidate_cache()
            return
        root_window = self.window()
        if root_window is not None and hasattr(root_window, "refresh_table"):
            # MainWindow handles this signal centrally; avoid duplicate tab refresh storms.
            return
        self.load_services_data(force_refresh=True)

    def _get_cached_services(self, key: str) -> list[schemas.Service] | None:
        ts = self._services_cache_ts.get(key)
        if ts is None:
            return None
        if (time.monotonic() - ts) > self._services_cache_ttl_s:
            self._services_cache.pop(key, None)
            self._services_cache_ts.pop(key, None)
            return None
        return self._services_cache.get(key)

    def _set_cached_services(self, key: str, services: list[schemas.Service]) -> None:
        self._services_cache[key] = services
        self._services_cache_ts[key] = time.monotonic()

    def open_editor(self, service_to_edit: schemas.Service | None):
        dialog = ServiceEditorDialog(
            service_service=self.service_service,
            service_to_edit=service_to_edit,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_services_data(force_refresh=True)

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
            logger.info("[ServiceManager] تم أرشفة الخدمة: %s", self.selected_service.name)
            self.load_services_data(force_refresh=True)
        except Exception as e:
            logger.error("[ServiceManager] فشل أرشفة الخدمة: %s", e, exc_info=True)
            QMessageBox.critical(self, "خطأ", f"فشل الأرشفة: {e}")
