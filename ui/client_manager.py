# الملف: ui/client_manager.py

import hashlib
import os
import threading
import time
from collections import deque
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
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
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.client_service import ClientService
from ui.client_editor_dialog import ClientEditorDialog
from ui.styles import BUTTON_STYLES, TABLE_STYLE_DARK, create_centered_item, get_cairo_font

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class ClientManagerTab(QWidget):
    """
    (معدل) التاب الخاص بإدارة العملاء (مع عمود اللوجو)
    """

    def __init__(self, client_service: ClientService, parent=None):
        super().__init__(parent)

        self.client_service = client_service
        self.clients_list: list[schemas.Client] = []
        self.selected_client: schemas.Client | None = None
        self._logo_icon_cache: dict[object, QIcon | None] = {}
        self._logo_pixmap_cache: dict[object, QPixmap | None] = {}
        self._clients_cache: dict[str, dict] = {}
        self._clients_cache_ts: dict[str, float] = {}
        self._clients_cache_ttl_s = 20.0
        self._current_page = 1
        self._page_size = 100
        self._current_page_clients: list[schemas.Client] = []
        self._last_invoices_total: dict[str, float] = {}
        self._last_payments_total: dict[str, float] = {}
        self._lazy_logo_enabled = True
        self._logo_fetch_batch_limit = 10
        self._logo_fetch_queue = deque()
        self._logo_fetch_inflight: set[str] = set()
        self._logo_fetch_timer = QTimer(self)
        self._logo_fetch_timer.timeout.connect(self._drain_logo_fetch_queue)
        self._logo_fetch_timer.start(250)
        self._load_logo_sync_config()

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals

        app_signals.safe_connect(app_signals.clients_changed, self._on_clients_changed)
        app_signals.safe_connect(app_signals.payments_changed, self._invalidate_clients_cache)
        app_signals.safe_connect(app_signals.projects_changed, self._invalidate_clients_cache)
        app_signals.safe_connect(app_signals.invoices_changed, self._invalidate_clients_cache)
        app_signals.safe_connect(app_signals.client_logo_loaded, self._on_client_logo_loaded)

        # === شريط الأزرار المتجاوب ===
        from ui.responsive_toolbar import ResponsiveToolbar

        self.toolbar = ResponsiveToolbar()

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

        # إضافة الأزرار للـ toolbar المتجاوب
        self.toolbar.addButton(self.add_button)
        self.toolbar.addButton(self.edit_button)
        self.toolbar.addButton(self.delete_button)
        self.toolbar.addButton(self.export_button)
        self.toolbar.addButton(self.import_button)
        self.toolbar.addButton(self.refresh_button)
        self.toolbar.addWidget(self.show_archived_checkbox)

        main_layout.addWidget(self.toolbar)

        table_groupbox = QGroupBox("قايمة العملاء")
        table_layout = QVBoxLayout()
        table_groupbox.setLayout(table_layout)

        # استخدام الجدول العادي مع تفعيل الترتيب
        self.clients_table = QTableWidget()
        self.clients_table.setColumnCount(8)
        self.clients_table.setHorizontalHeaderLabels(
            [
                "اللوجو",
                "الاسم",
                "الشركة",
                "الهاتف",
                "الإيميل",
                "💰 إجمالي المشاريع",
                "✅ إجمالي المدفوعات",
                "الحالة",
            ]
        )

        # ⚡ تفعيل الترتيب بالضغط على رأس العمود
        self.clients_table.setSortingEnabled(True)

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar

        self.search_bar = UniversalSearchBar(
            self.clients_table, placeholder="🔍 بحث (الاسم، الشركة، الهاتف، الإيميل)..."
        )
        table_layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===

        self.clients_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl

        fix_table_rtl(self.clients_table)
        self.clients_table.setIconSize(QSize(40, 40))
        self.clients_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.clients_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.clients_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.clients_table.setAlternatingRowColors(True)
        self.clients_table.cellClicked.connect(self._on_client_cell_clicked)
        v_header = self.clients_table.verticalHeader()
        if v_header is not None:
            v_header.setDefaultSectionSize(54)
            v_header.setVisible(False)
        h_header = self.clients_table.horizontalHeader()
        if h_header is not None:
            # اللوجو ثابت، الاسم والشركة والإيميل يتمددون، الباقي بحجم المحتوى
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # اللوجو
            self.clients_table.setColumnWidth(0, 60)  # ⚡ تصغير عرض العمود ليكون اللوجو في المنتصف
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # الاسم - يتمدد
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # الشركة - يتمدد
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # الهاتف
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # الإيميل - يتمدد
            h_header.setSectionResizeMode(
                5, QHeaderView.ResizeMode.ResizeToContents
            )  # إجمالي المشاريع
            h_header.setSectionResizeMode(
                6, QHeaderView.ResizeMode.ResizeToContents
            )  # إجمالي المدفوعات
            h_header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
        self.clients_table.itemSelectionChanged.connect(self.on_client_selection_changed)

        # إضافة دبل كليك للتعديل
        self.clients_table.itemDoubleClicked.connect(self.open_editor_for_selected)

        # إضافة قائمة السياق (كليك يمين)
        self._setup_context_menu()

        table_layout.addWidget(self.clients_table)
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
        self.page_info_label.setFont(get_cairo_font(11, bold=True))
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
            on_export=self.export_clients,
        )

    def export_clients(self):
        """تصدير العملاء إلى Excel"""
        try:
            # الحصول على خدمة التصدير من النافذة الرئيسية
            main_window = self.parent()
            while main_window and not hasattr(main_window, "export_service"):
                main_window = main_window.parent()

            export_service = getattr(main_window, "export_service", None) if main_window else None

            if not export_service:
                QMessageBox.warning(
                    self,
                    "خدمة التصدير غير متوفرة",
                    "يرجى تثبيت pandas: pip install pandas openpyxl",
                )
                return

            # تصدير العملاء
            filepath = export_service.export_clients_to_excel(self.clients_list)

            if filepath:
                reply = QMessageBox.question(
                    self,
                    "تم التصدير",
                    f"تم تصدير {len(self.clients_list)} عميل بنجاح إلى:\n{filepath}\n\nهل تريد فتح الملف؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
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
            while main_window and not hasattr(main_window, "export_service"):
                main_window = main_window.parent()

            export_service = getattr(main_window, "export_service", None) if main_window else None

            if not export_service:
                QMessageBox.warning(
                    self,
                    "خدمة الاستيراد غير متوفرة",
                    "يرجى تثبيت pandas: pip install pandas openpyxl",
                )
                return

            # اختيار ملف Excel
            filepath, _ = QFileDialog.getOpenFileName(
                self, "اختر ملف Excel للاستيراد", "", "Excel Files (*.xlsx *.xls)"
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
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.No:
                    return

            if not clients_data:
                QMessageBox.warning(
                    self, "لا توجد بيانات", "لم يتم العثور على بيانات صحيحة للاستيراد"
                )
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
                    safe_print(f"ERROR: فشل استيراد عميل {client_dict.get('name')}: {e}")
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
            if 0 <= selected_index < len(self._current_page_clients):
                self.selected_client = self._current_page_clients[selected_index]
                self.update_buttons_state(True)
                return
        self.selected_client = None
        self.update_buttons_state(False)

    def load_clients_data(self, force_refresh: bool = False):
        """⚡ تحميل بيانات العملاء في الخلفية لمنع التجميد"""
        safe_print("INFO: [ClientManager] جاري تحميل بيانات العملاء...")

        from core.data_loader import get_data_loader

        # تحضير الجدول
        sorting_enabled = self.clients_table.isSortingEnabled()
        if sorting_enabled:
            self.clients_table.setSortingEnabled(False)
        self.clients_table.setUpdatesEnabled(False)
        self.clients_table.blockSignals(True)
        self.clients_table.setRowCount(0)

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
                    # ✅ استخدام ClientService بدلاً من الوصول المباشر للـ cursor
                    client_invoices_total, client_payments_total = (
                        self.client_service.get_client_financial_totals()
                    )
                except Exception as e:
                    safe_print(f"ERROR: فشل حساب الإجماليات: {e}")
                    client_invoices_total = {}
                    client_payments_total = {}

                return {
                    "clients": clients,
                    "invoices_total": client_invoices_total,
                    "payments_total": client_payments_total,
                }
            except Exception as e:
                safe_print(f"ERROR: [ClientManager] فشل جلب العملاء: {e}")
                return {"clients": [], "invoices_total": {}, "payments_total": {}}

        # دالة تحديث الواجهة
        def on_data_loaded(data):
            try:
                self.clients_list = data["clients"]
                client_invoices_total = data["invoices_total"]
                client_payments_total = data["payments_total"]

                self._last_invoices_total = client_invoices_total
                self._last_payments_total = client_payments_total
                self._render_current_page(client_invoices_total, client_payments_total)
                cache_key = "archived" if self.show_archived_checkbox.isChecked() else "active"
                self._set_cached_clients_data(cache_key, data)

            except Exception as e:
                safe_print(f"ERROR: [ClientManager] فشل تحديث الجدول: {e}")
                import traceback

                traceback.print_exc()
            finally:
                self.clients_table.blockSignals(False)
                self.clients_table.setUpdatesEnabled(True)
                if sorting_enabled:
                    self.clients_table.setSortingEnabled(True)

        def on_error(error_msg):
            safe_print(f"ERROR: [ClientManager] فشل تحميل العملاء: {error_msg}")
            self.clients_table.blockSignals(False)
            self.clients_table.setUpdatesEnabled(True)
            if sorting_enabled:
                self.clients_table.setSortingEnabled(True)

        cache_key = "archived" if self.show_archived_checkbox.isChecked() else "active"
        cached = self._get_cached_clients_data(cache_key)
        if cached is not None and not force_refresh:
            on_data_loaded(cached)
            return

        # تحميل البيانات في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="clients_list",
            load_function=fetch_clients,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _get_cached_clients_data(self, key: str) -> dict | None:
        ts = self._clients_cache_ts.get(key)
        if ts is None:
            return None
        if (time.monotonic() - ts) > self._clients_cache_ttl_s:
            self._clients_cache.pop(key, None)
            self._clients_cache_ts.pop(key, None)
            return None
        return self._clients_cache.get(key)

    def _set_cached_clients_data(self, key: str, data: dict) -> None:
        self._clients_cache[key] = data
        self._clients_cache_ts[key] = time.monotonic()

    def _invalidate_clients_cache(self):
        self._clients_cache.clear()
        self._clients_cache_ts.clear()

    def _load_logo_sync_config(self):
        try:
            import json

            cfg_path = Path("sync_config.json")
            if not cfg_path.exists():
                return
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            self._lazy_logo_enabled = bool(cfg.get("lazy_logo_enabled", True))
            self._logo_fetch_batch_limit = max(1, int(cfg.get("logo_fetch_batch_limit", 10)))
        except Exception:
            self._lazy_logo_enabled = True
            self._logo_fetch_batch_limit = 10

    @staticmethod
    def _client_identity(client: schemas.Client) -> str:
        return str(getattr(client, "_mongo_id", None) or getattr(client, "id", "") or "")

    def _queue_logo_fetch(self, client: schemas.Client):
        if not self._lazy_logo_enabled:
            return
        if not bool(getattr(client, "has_logo", False)):
            return
        if getattr(client, "logo_data", None):
            return

        identity = self._client_identity(client)
        if not identity or identity in self._logo_fetch_inflight:
            return
        if identity in self._logo_fetch_queue:
            return
        self._logo_fetch_queue.append(identity)

    def _drain_logo_fetch_queue(self):
        if not self._lazy_logo_enabled:
            return
        # حافظ على عدد طلبات متزامنة محدود جداً
        available_slots = max(0, self._logo_fetch_batch_limit - len(self._logo_fetch_inflight))
        for _ in range(available_slots):
            if not self._logo_fetch_queue:
                break
            identity = self._logo_fetch_queue.popleft()
            if identity in self._logo_fetch_inflight:
                continue
            self._logo_fetch_inflight.add(identity)
            threading.Thread(
                target=self._fetch_logo_worker,
                args=(identity,),
                daemon=True,
                name=f"client-logo-fetch-{identity}",
            ).start()

    def _fetch_logo_worker(self, client_identity: str):
        success = False
        try:
            success = bool(self.client_service.fetch_client_logo_on_demand(client_identity))
        except Exception:
            success = False

        def finalize():
            self._logo_fetch_inflight.discard(client_identity)
            if success:
                self._on_client_logo_loaded(client_identity)

        QTimer.singleShot(0, finalize)

    def _on_client_logo_loaded(self, client_identity: str):
        if not client_identity:
            return
        self._logo_icon_cache.pop(client_identity, None)
        self._logo_pixmap_cache.pop(client_identity, None)
        self._refresh_client_logo_cell(client_identity)

    def _refresh_client_logo_cell(self, client_identity: str):
        if not client_identity:
            return
        if not hasattr(self, "clients_table"):
            return
        for row_idx, client in enumerate(self._current_page_clients):
            if self._client_identity(client) != str(client_identity):
                continue
            refreshed = self.client_service.get_client_by_id(
                str(client_identity), ensure_logo=False
            )
            if refreshed:
                self._current_page_clients[row_idx] = refreshed
                client = refreshed
            icon = self._get_client_logo_icon(client)
            if not icon:
                continue
            item = self.clients_table.item(row_idx, 0)
            if item is None:
                continue
            item.setIcon(icon)
            item.setText("")
            item.setToolTip(
                "⭐ VIP • اضغط لعرض الشعار"
                if bool(getattr(client, "is_vip", False))
                else "اضغط لعرض الشعار"
            )
            self.clients_table.viewport().update()
            break

    def _get_logo_cache_dir(self) -> Path:
        cache_dir = Path("exports") / "cache" / "client_logos"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _get_logo_cache_path(self, logo_data: str | None, logo_path: str | None) -> Path | None:
        if logo_data:
            digest = hashlib.sha256(logo_data.encode("utf-8")).hexdigest()
            return self._get_logo_cache_dir() / f"data_{digest}.png"
        if logo_path:
            try:
                stat = os.stat(logo_path)
                payload = f"{logo_path}:{stat.st_mtime}:{stat.st_size}"
            except Exception:
                payload = logo_path
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            return self._get_logo_cache_dir() / f"path_{digest}.png"
        return None

    def _get_client_logo_icon(self, client: schemas.Client) -> QIcon | None:
        key = (
            getattr(client, "_mongo_id", None)
            or getattr(client, "id", None)
            or (getattr(client, "name", None) or "").strip()
        )
        if key in self._logo_icon_cache:
            return self._logo_icon_cache[key]

        pixmap = self._get_client_logo_pixmap(client)
        if pixmap is None or pixmap.isNull():
            self._logo_icon_cache[key] = None
            return None

        is_vip = bool(getattr(client, "is_vip", False))
        border_color = QColor("#fbbf24") if is_vip else None
        border_width = 2 if is_vip else 0
        circle = self._to_circle_pixmap(pixmap, 40, border_color, border_width)
        icon = QIcon(circle)
        self._logo_icon_cache[key] = icon
        return icon

    def _get_client_logo_pixmap(self, client: schemas.Client) -> QPixmap | None:
        key = (
            getattr(client, "_mongo_id", None)
            or getattr(client, "id", None)
            or (getattr(client, "name", None) or "").strip()
        )
        if key in self._logo_pixmap_cache:
            return self._logo_pixmap_cache[key]

        pixmap = None
        logo_data = getattr(client, "logo_data", None)
        logo_path = getattr(client, "logo_path", None)
        cache_path = self._get_logo_cache_path(str(logo_data) if logo_data else None, logo_path)
        if cache_path and cache_path.exists():
            pm = QPixmap(str(cache_path))
            if not pm.isNull():
                self._logo_pixmap_cache[key] = pm
                return pm

        try:
            if logo_data and str(logo_data).strip():
                import base64

                raw = str(logo_data).strip()
                if raw.startswith("data:image"):
                    raw = raw.split(",")[1]
                img_bytes = base64.b64decode(raw)
                pm = QPixmap()
                if pm.loadFromData(img_bytes) and not pm.isNull():
                    pixmap = pm
        except Exception:
            pixmap = None

        if pixmap is None:
            try:
                if logo_path and os.path.exists(logo_path):
                    pm = QPixmap(logo_path)
                    if not pm.isNull():
                        pixmap = pm
            except Exception:
                pixmap = None

        if pixmap is None or pixmap.isNull():
            self._logo_pixmap_cache[key] = None
            return None

        pixmap = pixmap.scaled(
            128,
            128,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if cache_path:
            try:
                pixmap.save(str(cache_path), "PNG")
            except Exception:
                pass

        self._logo_pixmap_cache[key] = pixmap
        return pixmap

    def _to_circle_pixmap(
        self,
        pixmap: QPixmap,
        size: int,
        border_color: QColor | None = None,
        border_width: int = 0,
    ) -> QPixmap:
        if pixmap.isNull():
            return pixmap
        canvas = QPixmap(size, size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        scaled = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(0, 0, scaled)
        if border_color and border_width > 0:
            painter.setClipping(False)
            pen = painter.pen()
            pen.setColor(border_color)
            pen.setWidth(border_width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            inset = border_width // 2
            painter.drawEllipse(inset, inset, size - border_width, size - border_width)
        painter.end()
        return canvas

    def _on_client_cell_clicked(self, row: int, column: int):
        if column != 0:
            return
        if row < 0 or row >= len(self._current_page_clients):
            return
        client = self._current_page_clients[row]
        pixmap = self._get_client_logo_pixmap(client)
        if pixmap is None or pixmap.isNull():
            return

        is_vip = bool(getattr(client, "is_vip", False))
        border_color = QColor("#fbbf24") if is_vip else None
        border_width = 3 if is_vip else 0

        dialog = QDialog(self)
        dialog.setWindowTitle("شعار العميل")
        dialog.setModal(True)
        dialog.setStyleSheet("QDialog { background: #0b1d33; }")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel(client.name or "عميل")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #E2E8F0; font-size: 14px; font-weight: bold;")

        logo_view = QLabel()
        logo_view.setFixedSize(96, 96)
        logo_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_view.setStyleSheet(
            """
            QLabel {
                background: rgba(15, 41, 66, 0.55);
                border: 1px solid rgba(90, 150, 230, 0.35);
                border-radius: 48px;
            }
        """
        )
        logo_view.setPixmap(self._to_circle_pixmap(pixmap, 96, border_color, border_width))

        layout.addWidget(title)
        layout.addWidget(logo_view, alignment=Qt.AlignmentFlag.AlignCenter)
        dialog.exec()

    def _get_total_pages(self) -> int:
        total = len(self.clients_list)
        if total == 0:
            return 1
        if self._page_size <= 0:
            return 1
        return (total + self._page_size - 1) // self._page_size

    def _render_current_page(self, client_invoices_total, client_payments_total):
        total_pages = self._get_total_pages()
        if self._current_page > total_pages:
            self._current_page = total_pages
        if self._current_page < 1:
            self._current_page = 1

        if self._page_size <= 0:
            page_clients = self.clients_list
        else:
            start_index = (self._current_page - 1) * self._page_size
            end_index = start_index + self._page_size
            page_clients = self.clients_list[start_index:end_index]

        self._current_page_clients = page_clients
        self._populate_clients_table(page_clients, client_invoices_total, client_payments_total)
        self._update_pagination_controls(total_pages)

    def _update_pagination_controls(self, total_pages: int):
        self.page_info_label.setText(f"صفحة {self._current_page} / {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

    def _on_page_size_changed(self, value: str):
        if value == "كل":
            self._page_size = max(1, len(self.clients_list))
        else:
            try:
                self._page_size = int(value)
            except Exception:
                self._page_size = 100
        self._current_page = 1
        self._render_current_page(self._last_invoices_total, self._last_payments_total)

    def _go_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._render_current_page(self._last_invoices_total, self._last_payments_total)

    def _go_next_page(self):
        if self._current_page < self._get_total_pages():
            self._current_page += 1
            self._render_current_page(self._last_invoices_total, self._last_payments_total)

    def _populate_clients_table(self, clients, client_invoices_total, client_payments_total):
        """ملء جدول العملاء بالبيانات - محسّن للسرعة مع تمييز VIP"""
        prev_sorting = self.clients_table.isSortingEnabled()
        prev_block = self.clients_table.blockSignals(True)
        self.clients_table.setSortingEnabled(False)
        self.clients_table.setUpdatesEnabled(False)
        try:
            total_clients = len(clients)
            self.clients_table.setRowCount(total_clients)

            vip_bg_color = QColor("#2d2a1a")
            vip_text_color = QColor("#fbbf24")

            for index, client in enumerate(clients):
                is_vip = getattr(client, "is_vip", False)
                logo_item = QTableWidgetItem()
                logo_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if is_vip:
                    logo_item.setBackground(vip_bg_color)
                else:
                    logo_item.setBackground(QColor("transparent"))
                icon = self._get_client_logo_icon(client)
                if icon:
                    logo_item.setIcon(icon)
                    logo_item.setToolTip(
                        "⭐ VIP • اضغط لعرض الشعار" if is_vip else "اضغط لعرض الشعار"
                    )
                else:
                    # Lazy logo loading: fetch only for visible rows when metadata says logo exists.
                    if bool(getattr(client, "has_logo", False)) and not getattr(
                        client, "logo_data", None
                    ):
                        self._queue_logo_fetch(client)
                    logo_item.setText((client.name or "?")[:1])
                    logo_item.setForeground(QColor("#9CA3AF"))
                self.clients_table.setItem(index, 0, logo_item)

                name_text = f"⭐ {client.name}" if is_vip else (client.name or "")
                name_item = create_centered_item(name_text)
                if is_vip:
                    name_item.setForeground(vip_text_color)
                    name_item.setFont(get_cairo_font(11, bold=True))
                    name_item.setBackground(vip_bg_color)
                self.clients_table.setItem(index, 1, name_item)

                company_item = create_centered_item(client.company_name or "")
                phone_item = create_centered_item(client.phone or "")
                email_item = create_centered_item(client.email or "")

                if is_vip:
                    company_item.setBackground(vip_bg_color)
                    phone_item.setBackground(vip_bg_color)
                    email_item.setBackground(vip_bg_color)

                self.clients_table.setItem(index, 2, company_item)
                self.clients_table.setItem(index, 3, phone_item)
                self.clients_table.setItem(index, 4, email_item)

                client_name = client.name
                total_invoices = client_invoices_total.get(client_name, 0.0)
                total_payments = client_payments_total.get(client_name, 0.0)

                total_item = create_centered_item(f"{total_invoices:,.0f} ج.م")
                total_item.setData(Qt.ItemDataRole.UserRole, total_invoices)
                total_item.setForeground(QColor("#2454a5"))
                total_item.setFont(get_cairo_font(10, bold=True))
                if is_vip:
                    total_item.setBackground(vip_bg_color)
                self.clients_table.setItem(index, 5, total_item)

                payment_item = create_centered_item(f"{total_payments:,.0f} ج.م")
                payment_item.setData(Qt.ItemDataRole.UserRole, total_payments)
                payment_item.setForeground(QColor("#00a876"))
                payment_item.setFont(get_cairo_font(10, bold=True))
                if is_vip:
                    payment_item.setBackground(vip_bg_color)
                self.clients_table.setItem(index, 6, payment_item)

                if is_vip:
                    status_item = create_centered_item("⭐ VIP")
                    status_item.setBackground(QColor("#f59e0b"))
                    status_item.setForeground(QColor("white"))
                    status_item.setFont(get_cairo_font(10, bold=True))
                else:
                    bg_color = (
                        QColor("#ef4444")
                        if client.status == schemas.ClientStatus.ARCHIVED
                        else QColor("#0A6CF1")
                    )
                    status_item = create_centered_item(client.status.value, bg_color)
                    status_item.setForeground(QColor("white"))
                self.clients_table.setItem(index, 7, status_item)

            safe_print(f"INFO: [ClientManager] ✅ تم تحميل {len(self.clients_list)} عميل.")

            self.selected_client = None
            self.update_buttons_state(False)
        finally:
            self.clients_table.blockSignals(prev_block)
            self.clients_table.setUpdatesEnabled(True)
            self.clients_table.setSortingEnabled(prev_sorting)

    def _on_clients_changed(self):
        """⚡ استجابة لإشارة تحديث العملاء - تحديث الجدول أوتوماتيك"""
        safe_print("INFO: [ClientManager] ⚡ استلام إشارة تحديث العملاء - جاري التحديث...")
        self._invalidate_clients_cache()
        # ⚡ إبطال الـ cache لضمان جلب البيانات الجديدة (بما فيها الصور)
        if hasattr(self.client_service, "invalidate_cache"):
            self.client_service.invalidate_cache()
        self.load_clients_data(force_refresh=True)

    def open_editor(self, client_to_edit: schemas.Client | None):
        dialog = ClientEditorDialog(
            client_service=self.client_service, client_to_edit=client_to_edit, parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_clients_data(force_refresh=True)

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
        msg.setText("هل أنت متأكد من حذف العميل؟")
        msg.setInformativeText(
            f"العميل: {self.selected_client.name}\n"
            f"الشركة: {self.selected_client.company_name or 'غير محدد'}\n\n"
            f"⚠️ تحذير: هذا الإجراء لا يمكن التراجع عنه!"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
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
                client_id = getattr(self.selected_client, "_mongo_id", None) or str(
                    self.selected_client.id
                )
                safe_print(
                    f"DEBUG: [delete_selected_client] حذف العميل: {self.selected_client.name}"
                )
                safe_print(
                    f"DEBUG: [delete_selected_client] _mongo_id: {getattr(self.selected_client, '_mongo_id', None)}"
                )
                safe_print(f"DEBUG: [delete_selected_client] id: {self.selected_client.id}")
                safe_print(f"DEBUG: [delete_selected_client] client_id المستخدم: {client_id}")

                result = self.client_service.delete_client(client_id)
                safe_print(f"DEBUG: [delete_selected_client] نتيجة الحذف: {result}")

                # رسالة نجاح
                QMessageBox.information(
                    self, "✅ تم الحذف", f"تم حذف العميل '{self.selected_client.name}' بنجاح"
                )

                # تحديث الجدول
                self._invalidate_clients_cache()
                if hasattr(self.client_service, "invalidate_cache"):
                    self.client_service.invalidate_cache()
                self.selected_client = None
                self.load_clients_data(force_refresh=True)

            except Exception as e:
                QMessageBox.critical(self, "❌ خطأ", f"فشل حذف العميل:\n{str(e)}")
