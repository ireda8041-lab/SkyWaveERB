# الملف: ui/accounting_manager.py
"""
تاب المحاسبة - واجهة تشغيلية للخزن فوق الحسابات النقدية الداخلية.
"""

from PyQt6.QtCore import QItemSelectionModel, Qt, QTimer
from PyQt6.QtGui import QColor, QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from core.account_filters import get_cashbox_treasury_type, is_operational_cashbox
from core.signals import app_signals
from core.text_utils import normalize_user_text
from services.accounting_service import AccountingService
from services.expense_service import ExpenseService
from services.project_service import ProjectService
from ui.account_editor_dialog import AccountEditorDialog
from ui.styles import BUTTON_STYLES, CHART_OF_ACCOUNTS_TREE_STYLE, COLORS, get_cairo_font

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


# استيراد نظام الإشعارات
try:
    from ui.notification_system import notify_success
except ImportError:

    def notify_success(_msg, _title=None):
        pass


def _rgba_css(color_hex: str, alpha: int) -> str:
    """تحويل اللون من hex إلى rgba للاستخدام في Qt stylesheets."""
    color = QColor(color_hex)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"


class AccountingManagerTab(QWidget):
    """تاب المحاسبة الرئيسي"""

    # ⚡ Cache للحسابات على مستوى الكلاس
    _accounts_cache = None
    _accounts_cache_time = 0
    _ACCOUNTS_CACHE_TTL = 60  # 60 ثانية

    def __init__(
        self,
        expense_service: ExpenseService,
        accounting_service: AccountingService,
        project_service: ProjectService,
        parent=None,
    ):
        super().__init__(parent)

        self.expense_service = expense_service
        self.accounting_service = accounting_service
        self.project_service = project_service
        self.all_accounts_list: list[schemas.Account] = []
        self.cashbox_rows: list[dict] = []
        self._visible_cashbox_rows: list[dict] = []
        self.cashbox_audit: dict = {}
        self._cashbox_shortcuts: list[QShortcut] = []

        # ⚡ حماية من التحديث المتكرر
        self._is_loading = False
        self._last_refresh_time = 0
        self._force_next_refresh = False  # ⚡ للتحديث الإجباري عند الحاجة
        self._pending_reload = False
        self._pending_force_reload = False
        self._reload_retry_timer = QTimer(self)
        self._reload_retry_timer.setSingleShot(True)
        self._reload_retry_timer.timeout.connect(self._run_scheduled_reload)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تاب إدارة الحسابات (التاب الوحيد)
        self.setup_accounts_tab(main_layout)

        # ⚡ ربط جميع الإشارات للتحديث التلقائي الفوري (Real-time Sync)
        self._connect_realtime_signals()

        # ⚡ تطبيق محاذاة النص لليمين على كل الحقول
        from ui.styles import apply_rtl_alignment_to_all_fields

        apply_rtl_alignment_to_all_fields(self)
        self._setup_keyboard_support()

    def _connect_realtime_signals(self):
        """⚡ ربط جميع الإشارات للتحديث الفوري التلقائي - محسّن لتجنب التكرار"""
        # ⚡ ربط إشارة accounting_changed فقط (لأن data_changed مربوطة في MainWindow)
        # هذا يمنع التحديث المزدوج
        app_signals.safe_connect(app_signals.accounting_changed, self._on_accounting_changed)

        # ⚡ إشارة القيود المحاسبية فقط (لأنها خاصة)
        app_signals.journal_entry_created.connect(self._on_journal_entry_created)

        safe_print("INFO: ✅ [AccManager] تم ربط إشارات التحديث (محسّن)")

    def _on_accounting_changed(self):
        """⚡ معالج التحديث الفوري عند تغيير بيانات المحاسبة"""
        # ⚡ إبطال الـ cache أولاً لضمان جلب البيانات الجديدة
        self.invalidate_cache()
        # ⚡ إبطال cache الـ service أيضاً
        if hasattr(self.accounting_service, "_hierarchy_cache"):
            self.accounting_service._hierarchy_cache = None
            self.accounting_service._hierarchy_cache_time = 0
        if not self.isVisible():
            return
        self.load_accounts_data(force_refresh=True)

    def _on_any_data_changed(self, _data_type: str = None):
        """⚡ معالج التحديث الفوري عند تغيير أي بيانات - معطل لتجنب التكرار"""
        # ⚡ معطل - التحديث يتم من MainWindow مباشرة
        pass

    def _on_journal_entry_created(self, _entry_id: str = None):
        """⚡ معالج إنشاء قيد محاسبي جديد - تحديث فوري"""
        # إبطال الـ cache لضمان جلب البيانات الجديدة
        self.accounting_service._hierarchy_cache = None
        self.accounting_service._hierarchy_cache_time = 0
        if not self.isVisible():
            return
        self.load_accounts_data(force_refresh=True)

    def on_data_changed(self):
        """معالج التحديث الفوري عند تغيير البيانات (للتوافق)"""
        self._on_any_data_changed()

    def on_journal_entry_created(self, entry_id: str):
        """معالج إنشاء قيد محاسبي جديد (للتوافق)"""
        self._on_journal_entry_created(entry_id)

    def resizeEvent(self, event):
        """معالج تغيير حجم النافذة مع ضبط التخطيط تلقائياً."""
        super().resizeEvent(event)
        self._apply_responsive_splitter_layout()

    def _apply_responsive_splitter_layout(self):
        """ضبط اتجاه وأحجام الـ splitter تلقائياً حسب أبعاد النافذة الحالية."""
        if not hasattr(self, "main_splitter"):
            return

        width = max(int(self.width() or 0), 0)
        target_orientation = Qt.Orientation.Vertical if width < 800 else Qt.Orientation.Horizontal
        if self.main_splitter.orientation() != target_orientation:
            self.main_splitter.setOrientation(target_orientation)

        splitter_size = self.main_splitter.size()
        if target_orientation == Qt.Orientation.Horizontal:
            available_width = max(int(splitter_size.width() or width) - 8, 0)
            summary_width = int(min(max(360, available_width * 0.29), 470))
            tree_width = max(available_width - summary_width, 420)
            self.main_splitter.setSizes([summary_width, tree_width])
            return

        available_height = max(int(splitter_size.height() or self.height()) - 8, 0)
        summary_content_height = 360
        if hasattr(self, "summary_content_widget") and self.summary_content_widget is not None:
            summary_content_height = max(
                summary_content_height,
                int(self.summary_content_widget.sizeHint().height() or 0) + 18,
            )
        summary_height = int(min(max(320, available_height * 0.42), summary_content_height))
        tree_height = max(available_height - summary_height, 280)
        self.main_splitter.setSizes([summary_height, tree_height])

    # ==================== تاب إدارة الحسابات ====================
    def setup_accounts_tab(self, main_layout: QVBoxLayout):
        """إعداد واجهة إدارة الحسابات"""
        layout = main_layout  # استخدام الـ layout الرئيسي مباشرة

        from PyQt6.QtWidgets import QSplitter

        from ui.responsive_toolbar import ResponsiveToolbar

        self.hero_frame = QFrame()
        self.hero_frame.setObjectName("AccountingHero")
        self.hero_frame.setStyleSheet(
            f"""
            QFrame#AccountingHero {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #07254d, stop:0.55 #0a2e5c, stop:1 #0c3567);
                border: 1px solid {_rgba_css(COLORS["primary"], 60)};
                border-radius: 18px;
            }}
            QLabel#AccountingHeroTitle {{
                color: {COLORS["text_primary"]};
                font-size: 17px;
                font-weight: 700;
                font-family: 'Cairo';
                background: transparent;
            }}
            QLabel#AccountingHeroSubtitle {{
                color: #9eb6d4;
                font-size: 10px;
                font-weight: 600;
                font-family: 'Cairo';
                background: transparent;
            }}
            QLabel#AccountingHeroBadge {{
                color: #c7d7eb;
                background: {_rgba_css(COLORS["primary"], 22)};
                border: 1px solid {_rgba_css(COLORS["primary"], 58)};
                border-radius: 999px;
                padding: 3px 11px;
                font-size: 9px;
                font-weight: 700;
                font-family: 'Cairo';
            }}
        """
        )
        hero_layout = QVBoxLayout(self.hero_frame)
        hero_layout.setContentsMargins(14, 11, 14, 11)
        hero_layout.setSpacing(7)

        hero_top_row = QHBoxLayout()
        hero_top_row.setContentsMargins(0, 0, 0, 0)
        hero_top_row.setSpacing(8)

        hero_text_layout = QVBoxLayout()
        hero_text_layout.setContentsMargins(0, 0, 0, 0)
        hero_text_layout.setSpacing(1)

        self.hero_title_label = QLabel("إدارة الخزن")
        self.hero_title_label.setObjectName("AccountingHeroTitle")
        self.hero_title_label.setFont(get_cairo_font(17, bold=True))
        self.hero_title_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        hero_text_layout.addWidget(self.hero_title_label)

        self.hero_subtitle_label = QLabel(
            "إدارة الخزن والمحافظ والبنوك المستخدمة فعليًا في التحصيل والصرف اليومي."
        )
        self.hero_subtitle_label.setObjectName("AccountingHeroSubtitle")
        self.hero_subtitle_label.setFont(get_cairo_font(10))
        self.hero_subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        hero_text_layout.addWidget(self.hero_subtitle_label)

        hero_top_row.addLayout(hero_text_layout, 1)

        self.hero_badge_label = QLabel("مرتبطة بالتحصيل والصرف")
        self.hero_badge_label.setObjectName("AccountingHeroBadge")
        self.hero_badge_label.setFont(get_cairo_font(9, bold=True))
        self.hero_badge_label.setMinimumWidth(158)
        self.hero_badge_label.setMinimumHeight(24)
        self.hero_badge_label.setMaximumHeight(24)
        self.hero_badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_top_row.addWidget(self.hero_badge_label, 0, Qt.AlignmentFlag.AlignLeft)
        hero_layout.addLayout(hero_top_row)

        self.toolbar = ResponsiveToolbar()

        self.add_account_btn = QPushButton("➕ إضافة خزنة")
        self.add_account_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.add_account_btn.setMinimumHeight(30)
        self.add_account_btn.clicked.connect(self.open_account_editor)

        self.edit_account_btn = QPushButton("✏️ تعديل الخزنة")
        self.edit_account_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_account_btn.setMinimumHeight(30)
        self.edit_account_btn.clicked.connect(self.open_account_editor_for_selected)

        self.delete_account_btn = QPushButton("⛔ تعطيل الخزنة")
        self.delete_account_btn.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_account_btn.setMinimumHeight(30)
        self.delete_account_btn.clicked.connect(self.delete_selected_account)

        self.refresh_btn = QPushButton("🔄 تحديث")
        self.refresh_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_btn.setMinimumHeight(30)
        self.refresh_btn.clicked.connect(self.load_accounts_data)

        self.toolbar.addButton(self.add_account_btn)
        self.toolbar.addButton(self.edit_account_btn)
        self.toolbar.addButton(self.delete_account_btn)
        self.toolbar.addButton(self.refresh_btn)
        hero_layout.addWidget(self.toolbar)
        layout.addWidget(self.hero_frame)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStyleSheet(
            """
            QSplitter::handle {
                background-color: rgba(74, 111, 168, 0.45);
                width: 6px;
                margin: 4px 6px;
                border-radius: 3px;
            }
        """
        )

        self.summary_panel = self.build_summary_panel()
        self.summary_panel.setMinimumWidth(348)
        self.main_splitter.addWidget(self.summary_panel)

        self.tree_container_frame = QFrame()
        self.tree_container_frame.setObjectName("AccountingTreeCard")
        self.tree_container_frame.setStyleSheet(
            f"""
            QFrame#AccountingTreeCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #041f45, stop:1 #082957);
                border: 1px solid {_rgba_css(COLORS["border"], 255)};
                border-radius: 18px;
            }}
            QFrame#AccountingTreeHeader {{
                background: {_rgba_css(COLORS["bg_light"], 180)};
                border: 1px solid {_rgba_css(COLORS["primary"], 40)};
                border-radius: 14px;
            }}
            QLabel#AccountingTreeTitle {{
                color: {COLORS["text_primary"]};
                font-size: 16px;
                font-weight: 700;
                font-family: 'Cairo';
                background: transparent;
            }}
            QLabel#AccountingTreeSubtitle {{
                color: #9eb6d4;
                font-size: 10px;
                font-weight: 600;
                font-family: 'Cairo';
                background: transparent;
            }}
            QLabel#AccountingTreeBadge {{
                color: #dbeafe;
                background: {_rgba_css(COLORS["primary"], 38)};
                border: 1px solid {_rgba_css(COLORS["primary"], 95)};
                border-radius: 999px;
                padding: 4px 11px;
                font-size: 9px;
                font-weight: 700;
                font-family: 'Cairo';
            }}
            QLabel#AccountingTreeMeta {{
                color: {COLORS["text_secondary"]};
                font-size: 9px;
                font-weight: 600;
                font-family: 'Cairo';
                background: transparent;
            }}
        """
        )
        tree_layout = QVBoxLayout(self.tree_container_frame)
        tree_layout.setContentsMargins(12, 12, 12, 12)
        tree_layout.setSpacing(10)

        self.tree_header_frame = QFrame()
        self.tree_header_frame.setObjectName("AccountingTreeHeader")
        tree_header_layout = QHBoxLayout(self.tree_header_frame)
        tree_header_layout.setContentsMargins(14, 12, 14, 12)
        tree_header_layout.setSpacing(10)

        tree_text_layout = QVBoxLayout()
        tree_text_layout.setContentsMargins(0, 0, 0, 0)
        tree_text_layout.setSpacing(2)

        self.accounts_panel_title = QLabel("قائمة الخزن")
        self.accounts_panel_title.setObjectName("AccountingTreeTitle")
        self.accounts_panel_title.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        tree_text_layout.addWidget(self.accounts_panel_title)

        self.accounts_panel_subtitle = QLabel(
            "اعرض الوارد والصادر والرصيد الحالي لكل خزنة تشغيلية بالنقر المزدوج."
        )
        self.accounts_panel_subtitle.setObjectName("AccountingTreeSubtitle")
        self.accounts_panel_subtitle.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        tree_text_layout.addWidget(self.accounts_panel_subtitle)
        tree_header_layout.addLayout(tree_text_layout, 1)

        tree_badges_layout = QVBoxLayout()
        tree_badges_layout.setContentsMargins(0, 0, 0, 0)
        tree_badges_layout.setSpacing(4)

        self.accounts_count_badge = QLabel("0 خزنة")
        self.accounts_count_badge.setObjectName("AccountingTreeBadge")
        self.accounts_count_badge.setMinimumWidth(68)
        self.accounts_count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tree_badges_layout.addWidget(self.accounts_count_badge, 0, Qt.AlignmentFlag.AlignLeft)

        self.accounts_meta_label = QLabel("الخزن جاهزة للعرض")
        self.accounts_meta_label.setObjectName("AccountingTreeMeta")
        self.accounts_meta_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        tree_badges_layout.addWidget(self.accounts_meta_label, 0, Qt.AlignmentFlag.AlignLeft)
        tree_header_layout.addLayout(tree_badges_layout)

        tree_layout.addWidget(self.tree_header_frame)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("بحث في الخزن أو النوع أو المرجع...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.setMinimumHeight(34)
        self.search_bar.setObjectName("AccountingCashboxSearch")
        self.search_bar.setStyleSheet(
            f"""
            QLineEdit#AccountingCashboxSearch {{
                background: {_rgba_css(COLORS["bg_light"], 210)};
                border: 1px solid {_rgba_css(COLORS["primary"], 65)};
                border-radius: 12px;
                padding: 7px 12px;
                color: {COLORS["text_primary"]};
                font-size: 11px;
                font-family: 'Cairo';
            }}
            QLineEdit#AccountingCashboxSearch:focus {{
                border: 1px solid {_rgba_css(COLORS["primary"], 180)};
                background: {_rgba_css(COLORS["bg_light"], 230)};
            }}
        """
        )
        self.search_bar.textChanged.connect(self._apply_cashbox_filter)
        self.search_bar.returnPressed.connect(self._focus_first_visible_cashbox)
        tree_layout.addWidget(self.search_bar)

        self.accounts_tree = QTreeView()
        self.accounts_model = QStandardItemModel()
        self.accounts_model.setHorizontalHeaderLabels(self._cashbox_table_headers())
        self.accounts_tree.setModel(self.accounts_model)
        self.accounts_tree.setAlternatingRowColors(True)
        self.accounts_tree.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.accounts_tree.setRootIsDecorated(False)
        self.accounts_tree.setItemsExpandable(False)
        self.accounts_tree.setIndentation(0)
        self.accounts_tree.setStyleSheet(
            CHART_OF_ACCOUNTS_TREE_STYLE
            + f"""
            QTreeView {{
                border: none;
                border-radius: 14px;
                background-color: {COLORS["bg_dark"]};
            }}
            QTreeView::item {{
                padding: 9px 8px;
                min-height: 38px;
                border-bottom: 1px solid {_rgba_css(COLORS["border"], 180)};
            }}
            QTreeView::item:selected {{
                background-color: {_rgba_css(COLORS["primary"], 215)};
            }}
            QHeaderView::section {{
                min-height: 40px;
                font-size: 12px;
                padding: 11px 8px;
            }}
        """
        )
        self.accounts_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        font = self.accounts_tree.font()
        font.setPointSize(10)
        font.setFamily("Segoe UI")
        self.accounts_tree.setFont(font)
        self.accounts_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.accounts_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.accounts_tree.setUniformRowHeights(True)
        self.accounts_tree.setAnimated(True)
        self.accounts_tree.setAllColumnsShowFocus(True)
        self.accounts_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.accounts_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.accounts_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.accounts_tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        header = self.accounts_tree.header()
        if header is not None:
            header.setMinimumHeight(44)
            header.setStretchLastSection(False)
            header.setMinimumSectionSize(60)
            header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
            self._configure_cashbox_tree_columns()

        self.accounts_tree.doubleClicked.connect(self.open_ledger_window)
        self.accounts_tree.activated.connect(self.open_ledger_window)
        tree_layout.addWidget(self.accounts_tree, 1)

        self.main_splitter.addWidget(self.tree_container_frame)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        layout.addWidget(self.main_splitter, 1)
        QTimer.singleShot(0, self._apply_responsive_splitter_layout)
        self.setTabOrder(self.add_account_btn, self.edit_account_btn)
        self.setTabOrder(self.edit_account_btn, self.delete_account_btn)
        self.setTabOrder(self.delete_account_btn, self.refresh_btn)
        self.setTabOrder(self.refresh_btn, self.summary_refresh_btn)
        self.setTabOrder(self.summary_refresh_btn, self.search_bar)
        self.setTabOrder(self.search_bar, self.accounts_tree)

    def _setup_keyboard_support(self):
        self._cashbox_shortcuts = []
        for sequence, handler in (
            ("Insert", self.open_account_editor),
            ("F2", self.open_account_editor_for_selected),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
            self._cashbox_shortcuts.append(shortcut)

    @staticmethod
    def _row_search_text(row_data: dict) -> str:
        account = row_data.get("account")
        parts = [
            str(getattr(account, "name", "") or ""),
            str(getattr(account, "code", "") or ""),
            str(row_data.get("category", "") or ""),
            str(row_data.get("currency", "") or ""),
        ]
        return normalize_user_text(" ".join(parts)).lower()

    def _get_filtered_cashbox_rows(self) -> list[dict]:
        filter_text = (
            normalize_user_text(self.search_bar.text()).lower()
            if hasattr(self, "search_bar")
            else ""
        )
        if not filter_text:
            return list(self.cashbox_rows or [])
        return [
            row_data
            for row_data in (self.cashbox_rows or [])
            if filter_text in self._row_search_text(row_data)
        ]

    def _restore_tree_selection(self, preferred_code: str = ""):
        if self.accounts_model.rowCount() <= 0:
            return

        target_row = 0
        if preferred_code:
            for row_index in range(self.accounts_model.rowCount()):
                item = self.accounts_model.item(row_index, 0)
                account = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
                if getattr(account, "code", None) == preferred_code:
                    target_row = row_index
                    break

        target_index = self.accounts_model.index(target_row, 0)
        if not target_index.isValid():
            return

        self.accounts_tree.setCurrentIndex(target_index)
        selection_model = self.accounts_tree.selectionModel()
        if selection_model is not None:
            selection_model.setCurrentIndex(
                target_index,
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows,
            )

    def _populate_accounts_model(self, visible_rows: list[dict]):
        self.accounts_model.clear()
        self.accounts_model.setHorizontalHeaderLabels(self._cashbox_table_headers())

        root = self.accounts_model.invisibleRootItem()
        for row_data in visible_rows:
            acc = row_data["account"]
            name_item = QStandardItem(str(acc.name or ""))
            category_item = QStandardItem(str(row_data.get("category", "") or ""))
            currency_item = QStandardItem(str(row_data.get("currency", "EGP") or "EGP"))
            inflow_item = QStandardItem(f"{float(row_data.get('inflow', 0.0) or 0.0):,.2f}")
            outflow_item = QStandardItem(f"{float(row_data.get('outflow', 0.0) or 0.0):,.2f}")
            balance_value = float(row_data.get("balance", 0.0) or 0.0)
            balance_item = QStandardItem(f"{balance_value:,.2f}")

            status = getattr(acc, "status", None)
            status_value = getattr(status, "value", status)
            is_active = status == schemas.AccountStatus.ACTIVE or status_value in {
                schemas.AccountStatus.ACTIVE.value,
                "ACTIVE",
            }
            status_item = QStandardItem("جاهزة" if is_active else "معطلة")

            row = [
                name_item,
                category_item,
                currency_item,
                inflow_item,
                outflow_item,
                balance_item,
                status_item,
            ]

            for item in row:
                item.setEditable(False)
                item.setData(acc, Qt.ItemDataRole.UserRole)
                item.setFont(get_cairo_font(9))
                item.setBackground(QColor(COLORS["bg_dark"]))
                item.setForeground(QColor(COLORS["text_secondary"]))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

            name_item.setFont(get_cairo_font(10, bold=True))
            name_item.setForeground(QColor(COLORS["text_primary"]))
            name_item.setToolTip(
                f"الخزنة: {acc.name}\n"
                f"المرجع: {acc.code}\n"
                f"النوع: {row_data.get('category', '')}\n"
                f"الرصيد الحالي: {balance_value:,.2f} جنيه"
            )
            inflow_item.setForeground(QColor("#51cf66"))
            outflow_item.setForeground(QColor("#ff66c4"))
            if balance_value < 0:
                balance_item.setForeground(QColor("#ff6b6b"))
            elif balance_value > 0:
                balance_item.setForeground(QColor("#20d5a2"))
            else:
                balance_item.setForeground(QColor("#adb5bd"))
            status_item.setForeground(QColor("#59d98e" if is_active else "#94a3b8"))

            root.appendRow(row)

    def _apply_cashbox_filter(self, _text: str | None = None):
        selected = self.get_selected_account()
        selected_code = str(getattr(selected, "code", "") or "")
        self._visible_cashbox_rows = self._get_filtered_cashbox_rows()
        self._populate_accounts_model(self._visible_cashbox_rows)
        self._configure_cashbox_tree_columns()
        self._refresh_accounts_meta(self._visible_cashbox_rows)
        if self.search_bar.text().strip():
            total_rows = len(self.cashbox_rows or [])
            matched_rows = len(self._visible_cashbox_rows)
            if matched_rows:
                self.accounts_meta_label.setText(
                    f"{matched_rows} من {total_rows} خزنة مطابقة للبحث"
                )
            else:
                self.accounts_meta_label.setText("لا توجد خزنة مطابقة للبحث الحالي")
        self._restore_tree_selection(selected_code)

    def _focus_first_visible_cashbox(self):
        if self.accounts_model.rowCount() <= 0:
            return
        self.accounts_tree.setFocus()
        self._restore_tree_selection()

    def focus_search(self):
        self.search_bar.setFocus()
        self.search_bar.selectAll()

    def handle_escape(self):
        if self.search_bar.text():
            self.search_bar.clear()
            self.accounts_tree.setFocus()
            return
        if (
            self.accounts_tree.selectionModel() is not None
            and self.accounts_tree.selectionModel().hasSelection()
        ):
            self.accounts_tree.clearSelection()
            return
        if self.search_bar.hasFocus():
            self.search_bar.clearFocus()
            self.accounts_tree.setFocus()

    def select_all(self):
        self.accounts_tree.setFocus()
        self.accounts_tree.selectAll()

    def copy_selected(self) -> bool:
        selection_model = self.accounts_tree.selectionModel()
        if selection_model is None or not selection_model.hasSelection():
            return False

        indexes = sorted(
            selection_model.selectedIndexes(),
            key=lambda index: (index.row(), index.column()),
        )
        rows: dict[int, dict[int, str]] = {}
        for index in indexes:
            rows.setdefault(index.row(), {})[index.column()] = str(index.data() or "")
        if not rows:
            return False

        clipboard_text = "\n".join(
            "\t".join(row_values[column] for column in sorted(row_values))
            for _row_number, row_values in sorted(rows.items())
        )
        QApplication.clipboard().setText(clipboard_text)
        return True

    def delete_selected(self):
        self.delete_selected_account()

    def _create_section_card(
        self, title: str, subtitle: str, accent_color: str, badge_text: str = "قراءة مباشرة"
    ):
        """إنشاء بطاقة قسم داخل لوحة الملخص."""
        frame = QFrame()
        frame.setObjectName("AccountingSummarySection")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        frame.setStyleSheet(
            f"""
            QFrame#AccountingSummarySection {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #062347, stop:1 #0a2d59);
                border: 1px solid {_rgba_css(accent_color, 95)};
                border-radius: 16px;
            }}
            QLabel#AccountingSummarySectionTitle {{
                color: {COLORS["text_primary"]};
                font-size: 13px;
                font-weight: 700;
                font-family: 'Cairo';
                background: transparent;
            }}
            QLabel#AccountingSummarySectionSubtitle {{
                color: #8fb2d8;
                font-size: 10px;
                font-weight: 600;
                font-family: 'Cairo';
                background: transparent;
            }}
            QLabel#AccountingSummarySectionBadge {{
                color: {accent_color};
                background: {_rgba_css(accent_color, 24)};
                border: 1px solid {_rgba_css(accent_color, 68)};
                border-radius: 999px;
                padding: 0 10px;
                font-size: 8px;
                font-weight: 700;
                font-family: 'Cairo';
            }}
        """
        )
        outer_layout = QVBoxLayout(frame)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("AccountingSummarySectionTitle")
        title_label.setFont(get_cairo_font(13, bold=True))
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        title_label.setWordWrap(True)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("AccountingSummarySectionSubtitle")
        subtitle_label.setFont(get_cairo_font(10))
        subtitle_label.setWordWrap(True)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        badge_label = QLabel(badge_text)
        badge_label.setObjectName("AccountingSummarySectionBadge")
        badge_label.setFont(get_cairo_font(9, bold=True))
        badge_label.setMinimumWidth(84)
        badge_label.setMinimumHeight(26)
        badge_label.setMaximumHeight(26)
        badge_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_label.setContentsMargins(0, 0, 0, 0)

        outer_layout.addWidget(title_label)
        outer_layout.addWidget(subtitle_label)

        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.setSpacing(0)
        badge_row.addWidget(
            badge_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        badge_row.addStretch(1)
        outer_layout.addLayout(badge_row)

        content_layout = QGridLayout()
        content_layout.setContentsMargins(0, 6, 0, 0)
        content_layout.setHorizontalSpacing(10)
        content_layout.setVerticalSpacing(12)
        outer_layout.addLayout(content_layout)

        return frame, content_layout

    @staticmethod
    def _cashbox_table_headers() -> list[str]:
        return [
            "الخزنة",
            "النوع",
            "العملة",
            "إجمالي الوارد",
            "إجمالي الصادر",
            "الرصيد الحالي",
            "التشغيل",
        ]

    @staticmethod
    def _cashbox_summary(rows: list[dict] | None) -> dict[str, float | int]:
        summary = {
            "total_cashboxes": 0,
            "active_cashboxes": 0,
            "category_count": 0,
            "total_balance": 0.0,
            "total_inflow": 0.0,
            "total_outflow": 0.0,
            "net_flow": 0.0,
        }
        if not rows:
            return summary

        categories: set[str] = set()
        for row in rows:
            account = row.get("account")
            status = getattr(account, "status", None)
            status_value = getattr(status, "value", status)
            if status == schemas.AccountStatus.ACTIVE or status_value in {
                schemas.AccountStatus.ACTIVE.value,
                "ACTIVE",
            }:
                summary["active_cashboxes"] += 1

            category = str(row.get("category", "") or "").strip()
            if category:
                categories.add(category)

            summary["total_cashboxes"] += 1
            summary["total_balance"] += float(row.get("balance", 0.0) or 0.0)
            summary["total_inflow"] += float(row.get("inflow", 0.0) or 0.0)
            summary["total_outflow"] += float(row.get("outflow", 0.0) or 0.0)

        summary["category_count"] = len(categories)
        summary["net_flow"] = float(summary["total_inflow"]) - float(summary["total_outflow"])
        return summary

    def _is_cash_account(self, account: schemas.Account) -> bool:
        return is_operational_cashbox(account)

    def _infer_cashbox_category(self, account: schemas.Account) -> str:
        treasury_type = get_cashbox_treasury_type(account).strip()
        if treasury_type:
            return treasury_type
        return "خزنة نقدية"

    def _build_cashbox_rows(
        self,
        tree_map: dict | None,
        payments: list[schemas.Payment] | None = None,
        expenses: list[schemas.Expense] | None = None,
    ) -> list[dict]:
        payments = payments or []
        expenses = expenses or []
        tree_map = tree_map or {}
        inflow_by_code: dict[str, float] = {}
        outflow_by_code: dict[str, float] = {}
        if hasattr(self.accounting_service, "_build_cash_flow_totals"):
            flow_totals = self.accounting_service._build_cash_flow_totals(
                self.all_accounts_list or [],
                payments,
                expenses,
            )
            if isinstance(flow_totals, tuple) and len(flow_totals) == 2:
                inflow_by_code, outflow_by_code = flow_totals

        rows: list[dict] = []
        for account in sorted(self.all_accounts_list or [], key=lambda acc: str(acc.code or "")):
            code = str(getattr(account, "code", "") or "")
            if not code or not self._is_cash_account(account):
                continue

            node = tree_map.get(code, {})
            has_children = bool(node.get("children")) if isinstance(node, dict) else False
            if has_children or self._is_group_account(code, self.all_accounts_list):
                continue

            balance = float(node.get("total", getattr(account, "balance", 0.0)) or 0.0)
            inflow = inflow_by_code.get(code, 0.0)
            outflow = outflow_by_code.get(code, 0.0)
            derived_account = account.model_copy(update={"balance": balance})
            rows.append(
                {
                    "account": derived_account,
                    "category": self._infer_cashbox_category(account),
                    "currency": getattr(getattr(account, "currency", None), "value", None) or "EGP",
                    "inflow": inflow,
                    "outflow": outflow,
                    "balance": balance,
                }
            )
        return rows

    def _refresh_accounts_meta(self, cashbox_rows: list[dict] | None = None):
        """تحديث بيانات هيدر الخزن بعدد الخزن والفئات النشطة."""
        rows = cashbox_rows if cashbox_rows is not None else list(self.cashbox_rows or [])
        total_cashboxes = len(rows)
        active_cashboxes = 0
        categories: set[str] = set()

        for row in rows:
            account = row.get("account")
            categories.add(str(row.get("category", "") or ""))
            status = getattr(account, "status", None)
            status_value = getattr(status, "value", status)
            if status == schemas.AccountStatus.ACTIVE or status_value in {
                schemas.AccountStatus.ACTIVE.value,
                "ACTIVE",
            }:
                active_cashboxes += 1

        if hasattr(self, "accounts_count_badge"):
            self.accounts_count_badge.setText(f"{total_cashboxes} خزنة")
        if hasattr(self, "accounts_meta_label"):
            if total_cashboxes:
                category_count = len([c for c in categories if c])
                category_label = "نوع" if category_count == 1 else "أنواع"
                audit_note = ""
                unresolved = int(self.cashbox_audit.get("unresolved_total", 0) or 0)
                repairable = int(self.cashbox_audit.get("repairable_total", 0) or 0)
                if unresolved:
                    audit_note = f" • {unresolved} مرجع يحتاج مراجعة"
                elif repairable:
                    audit_note = f" • {repairable} مرجع قديم"
                self.accounts_meta_label.setText(
                    f"{active_cashboxes} خزنة جاهزة • {category_count} {category_label}{audit_note}"
                )
            else:
                self.accounts_meta_label.setText("أضف خزنة لبدء التحصيل والصرف")

        self._apply_cashbox_audit_state()

    def _apply_cashbox_audit_state(self):
        """تحديث شارة الهيدر بحسب سلامة ربط الخزن في البيانات."""
        if not hasattr(self, "hero_badge_label"):
            return

        unresolved = int(self.cashbox_audit.get("unresolved_total", 0) or 0)
        repairable = int(self.cashbox_audit.get("repairable_total", 0) or 0)
        fixed = int(self.cashbox_audit.get("fixed_total", 0) or 0)

        if unresolved:
            badge_text = f"{unresolved} مرجع يحتاج مراجعة"
        elif repairable:
            badge_text = f"{repairable} مرجع قديم"
        elif fixed:
            badge_text = f"تم إصلاح {fixed} مرجع"
        else:
            badge_text = "مرتبطة بالتحصيل والصرف"

        self.hero_badge_label.setText(badge_text)
        self.hero_badge_label.setToolTip(
            "مراجعة ربط الخزن بالدفعات والمصروفات.\n"
            f"الدفعات غير المحلولة: {int(self.cashbox_audit.get('unresolved_payment_account_refs', 0) or 0)}\n"
            f"مراجع مصروف غير محلولة: {int(self.cashbox_audit.get('unresolved_expense_payment_refs', 0) or 0)}\n"
            f"مراجع قديمة قابلة للإصلاح: {repairable}\n"
            f"إصلاحات مطبقة: {fixed}"
        )

    def _setup_tree_columns(self):
        """ضبط أعمدة الشجرة - يتم استدعاؤها عند تغيير حجم النافذة"""
        self._configure_cashbox_tree_columns()

    def _configure_cashbox_tree_columns(self):
        """ضبط أعمدة جدول الخزن لملء المساحة بدون فراغات جانبية."""
        if not hasattr(self, "accounts_tree"):
            return
        header = self.accounts_tree.header()
        if header is None:
            return

        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)

        self.accounts_tree.setColumnWidth(1, 136)
        self.accounts_tree.setColumnWidth(2, 82)
        self.accounts_tree.setColumnWidth(3, 136)
        self.accounts_tree.setColumnWidth(4, 136)
        self.accounts_tree.setColumnWidth(5, 142)
        self.accounts_tree.setColumnWidth(6, 96)

    def _recalculate_hierarchy_tree(self, tree_map: dict):
        """
        🔥 إصلاح نهائي: دالة تقوم بإعادة حساب إجماليات الآباء بناءً على مجموع الأبناء
        لضمان اتساق الشجرة والملخص المالي بغض النظر عن الأخطاء في قاعدة البيانات.
        """

        def calculate_node_recursive(node):
            # 1. إذا لم يكن للعقدة أبناء، نعتمد رصيدها الحالي (Total) وننتهي
            children = node.get("children", [])
            if not children:
                return node.get("total", 0.0)

            # 2. إذا كان هناك أبناء، نقوم بجمع أرصدتهم (بعد إعادة حسابهم أيضاً)
            calculated_sum = 0.0
            for child in children:
                calculated_sum += calculate_node_recursive(child)

            # 3. تحديث رصيد العقدة الحالية ليساوي مجموع الأبناء تماماً
            # هذا يجبر "الأصول" أن تكون مجموع "النقدية + العملاء + ..."
            node["total"] = calculated_sum
            return calculated_sum

        # تحديد الجذور (Nodes التي ليس لها أباء داخل الـ Map) للبدء منها
        # نستخدم set للكفاءة
        all_codes = set(tree_map.keys())
        roots = []
        for _code, node in tree_map.items():
            acc = node["obj"]
            # محاولة معرفة الكود للأب
            parent_code = getattr(acc, "parent_id", None) or getattr(acc, "parent_code", None)
            # إذا لم يكن له أب، أو أبوه غير موجود في القائمة المحملة، فهو جذر
            if not parent_code or parent_code not in all_codes:
                roots.append(node)

        # بدء عملية الجمع التراكمي من الجذور
        for root in roots:
            calculate_node_recursive(root)

        return tree_map

    def _apply_cached_data(self, data):
        """⚡ تطبيق البيانات المخزنة في الـ cache على واجهة الخزن."""
        try:
            tree_map = data.get("tree_map", {})
            self.all_accounts_list = data.get("all_accounts", [])
            payments = data.get("payments", [])
            expenses = data.get("expenses", [])
            self.cashbox_audit = data.get("cashbox_audit", {})

            if tree_map:
                tree_map = self._recalculate_hierarchy_tree(tree_map)

            self.cashbox_rows = self._build_cashbox_rows(tree_map, payments, expenses)
            self._render_accounts_tree(tree_map)
            self._refresh_accounts_meta(self.cashbox_rows)
            self.update_summary_labels(tree_map)
            safe_print(
                f"INFO: [AccManager] ⚡ تم تطبيق cache الخزن ({len(self.cashbox_rows)} خزنة)"
            )
        except Exception as e:
            safe_print(f"ERROR: [AccManager] فشل تطبيق cache: {e}")

    def invalidate_cache(self):
        """⚡ إبطال الـ cache لإجبار التحديث في المرة القادمة"""
        AccountingManagerTab._accounts_cache = None
        AccountingManagerTab._accounts_cache_time = 0
        self._force_next_refresh = True
        safe_print("INFO: [AccManager] ⚡ تم إبطال cache الحسابات")

    def _schedule_refresh_retry(self, force_refresh: bool = False, delay_ms: int = 220):
        self._pending_reload = True
        self._pending_force_reload = self._pending_force_reload or force_refresh
        if self._reload_retry_timer.isActive():
            return
        self._reload_retry_timer.start(max(120, int(delay_ms)))

    def _run_scheduled_reload(self):
        if self._is_loading:
            self._schedule_refresh_retry(force_refresh=self._pending_force_reload, delay_ms=220)
            return

        pending_force = self._pending_force_reload
        self._pending_reload = False
        self._pending_force_reload = False
        self.load_accounts_data(force_refresh=pending_force)

    def load_accounts_data(self, force_refresh: bool = False):
        """⚡ تحميل الحسابات في الخلفية لمنع التجميد (مع cache ذكي)"""
        import time

        from core.data_loader import get_data_loader

        # ⚡ حماية من التحديث المتكرر (الحد الأدنى 0.5 ثانية بين كل تحديث)
        current_time = time.time()
        if force_refresh:
            self.invalidate_cache()
            self._last_refresh_time = 0
        if self._is_loading:
            self._schedule_refresh_retry(force_refresh=force_refresh, delay_ms=220)
            safe_print("INFO: [AccManager] ⏳ التحميل جارٍ - تم دمج طلب التحديث التالي")
            return
        if (current_time - self._last_refresh_time) < 0.5:
            remaining_delay_ms = int(
                max(180, ((0.5 - (current_time - self._last_refresh_time)) * 1000) + 80)
            )
            self._schedule_refresh_retry(
                force_refresh=force_refresh,
                delay_ms=remaining_delay_ms,
            )
            safe_print("INFO: [AccManager] ⏳ تم دمج التحديث السريع في إعادة تحميل مؤجلة")
            return

        # ⚡ استخدام الـ cache إذا كان صالحاً (ولم يُطلب تحديث إجباري)
        if (
            not self._force_next_refresh
            and AccountingManagerTab._accounts_cache
            and (current_time - AccountingManagerTab._accounts_cache_time)
            < AccountingManagerTab._ACCOUNTS_CACHE_TTL
        ):
            safe_print("INFO: [AccManager] ⚡ استخدام cache الحسابات (سريع)")
            self._apply_cached_data(AccountingManagerTab._accounts_cache)
            self._last_refresh_time = current_time
            return

        self._is_loading = True
        self._last_refresh_time = current_time
        self._force_next_refresh = False  # إعادة تعيين
        safe_print("INFO: [AccManager] جاري تحميل بيانات الخزن...")

        # دالة جلب البيانات (مع استخدام cache الـ service)
        def fetch_accounts():
            try:
                # ⚡ استخدام cache الـ service (بدون force_refresh)
                tree_map = self.accounting_service.get_hierarchy_with_balances(
                    force_refresh=force_refresh
                )
                all_accounts = self.accounting_service.repo.get_all_accounts()
                payments = (
                    self.accounting_service.repo.get_all_payments()
                    if hasattr(self.accounting_service.repo, "get_all_payments")
                    else []
                )
                expenses = (
                    self.accounting_service.repo.get_all_expenses()
                    if hasattr(self.accounting_service.repo, "get_all_expenses")
                    else []
                )
                cashbox_audit = self.accounting_service.audit_cashbox_integrity(
                    apply_fixes=False,
                    preloaded_accounts=all_accounts,
                    preloaded_payments=payments,
                    preloaded_expenses=expenses,
                )
                cashbox_audit["repairable_total"] = int(
                    cashbox_audit.get("fixed_expense_payment_refs", 0) or 0
                ) + int(cashbox_audit.get("backfilled_expense_payment_refs", 0) or 0)
                cashbox_audit["fixed_total"] = 0
                cashbox_audit["unresolved_total"] = int(
                    cashbox_audit.get("unresolved_payment_account_refs", 0) or 0
                ) + int(cashbox_audit.get("unresolved_expense_payment_refs", 0) or 0)
                return {
                    "tree_map": tree_map,
                    "all_accounts": all_accounts,
                    "payments": payments,
                    "expenses": expenses,
                    "cashbox_audit": cashbox_audit,
                }
            except Exception as e:
                safe_print(f"ERROR: [AccManager] فشل جلب بيانات الخزن: {e}")
                return {
                    "tree_map": {},
                    "all_accounts": [],
                    "payments": [],
                    "expenses": [],
                    "cashbox_audit": {},
                }

        # دالة تحديث الواجهة
        def on_data_loaded(data):
            import time

            try:
                tree_map = data["tree_map"]
                self.all_accounts_list = data["all_accounts"]
                payments = data.get("payments", [])
                expenses = data.get("expenses", [])
                self.cashbox_audit = data.get("cashbox_audit", {})

                # 🔥 [تعديل هام] تطبيق الإصلاح الرياضي قبل العرض
                if tree_map:
                    # هذه الخطوة تضمن أن الأب = مجموع الأبناء دائماً
                    tree_map = self._recalculate_hierarchy_tree(tree_map)

                # ⚡ حفظ في الـ cache
                AccountingManagerTab._accounts_cache = data
                AccountingManagerTab._accounts_cache_time = time.time()

                self.cashbox_rows = self._build_cashbox_rows(tree_map, payments, expenses)
                self._render_accounts_tree(tree_map)

                # تحديث الملخص المالي بالأرقام الجديدة الصحيحة
                self.update_summary_labels(tree_map)

                safe_print(
                    f"INFO: [AccManager] ✅ تم تحميل {len(self.cashbox_rows)} خزنة تشغيلية وتمت موازنة الأرصدة."
                )
            except Exception as e:
                safe_print(f"ERROR: [AccManager] فشل تحديث الشجرة: {e}")
                import traceback

                traceback.print_exc()
            finally:
                # ⚡ إعادة تفعيل التحميل
                self._is_loading = False
                if self._pending_reload:
                    pending_force = self._pending_force_reload
                    self._pending_reload = False
                    self._pending_force_reload = False
                    QTimer.singleShot(
                        180,
                        lambda force=pending_force: self.load_accounts_data(force_refresh=force),
                    )

        def on_error(error_msg):
            safe_print(f"ERROR: [AccManager] فشل تحميل الحسابات: {error_msg}")
            self._is_loading = False
            if self._pending_reload:
                pending_force = self._pending_force_reload
                self._pending_reload = False
                self._pending_force_reload = False
                QTimer.singleShot(
                    180, lambda force=pending_force: self.load_accounts_data(force_refresh=force)
                )

        # تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="accounts_tree",
            load_function=fetch_accounts,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True,
        )

    def _render_accounts_tree(self, tree_map):
        """عرض الخزن التشغيلية فوق الحسابات النقدية الداخلية."""

        if tree_map:
            incoming_accounts = [
                node.get("obj")
                for node in tree_map.values()
                if isinstance(node, dict) and node.get("obj")
            ]
            if not self.all_accounts_list:
                self.all_accounts_list = incoming_accounts
            visible_codes = {
                str(node["obj"].code or "")
                for node in tree_map.values()
                if isinstance(node, dict)
                and node.get("obj")
                and self._is_cash_account(node["obj"])
                and not bool(node.get("children"))
            }
            cached_codes = {
                str(getattr(row.get("account"), "code", "") or "")
                for row in (self.cashbox_rows or [])
            }
            if not self.cashbox_rows or visible_codes != cached_codes:
                self.all_accounts_list = incoming_accounts
                self.cashbox_rows = self._build_cashbox_rows(tree_map)

        self._apply_cashbox_filter()

        safe_print(f"INFO: [AccManager] تم عرض {len(self.cashbox_rows)} خزنة وضبط الأعمدة.")

        self.update_summary_labels(tree_map)

    def _is_group_account(self, code: str, all_accounts) -> bool:
        """Check if account is a group (has children)"""
        if not code:
            return False
        for acc in all_accounts:
            acc_code = acc.code or ""
            # Check if any account's code starts with this code (and is longer)
            if acc_code != code and acc_code.startswith(code):
                return True
            # Check parent_id attribute (قاعدة البيانات تستخدم parent_id)
            parent_code = getattr(acc, "parent_id", None) or getattr(acc, "parent_code", None)
            if parent_code == code:
                return True
        return False

    def get_selected_account(self) -> schemas.Account | None:
        """الحصول على الخزنة المحددة."""
        indexes = self.accounts_tree.selectedIndexes()
        if not indexes:
            return None
        item = self.accounts_model.itemFromIndex(indexes[0])
        if item:
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, schemas.Account):
                return data
        return None

    def open_account_editor(self):
        dialog = AccountEditorDialog(
            accounting_service=self.accounting_service,
            all_accounts=self.all_accounts_list,
            account_to_edit=None,
            cash_only=True,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_accounts_data(force_refresh=True)

    def open_account_editor_for_selected(self):
        selected = self.get_selected_account()
        if not selected:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد خزنة أولاً.")
            return
        dialog = AccountEditorDialog(
            accounting_service=self.accounting_service,
            all_accounts=self.all_accounts_list,
            account_to_edit=selected,
            cash_only=True,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_accounts_data(force_refresh=True)

    def delete_selected_account(self):
        selected = self.get_selected_account()
        if not selected:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد خزنة أولاً.")
            return

        if selected.status == schemas.AccountStatus.ARCHIVED:
            QMessageBox.information(self, "معلومة", "هذه الخزنة معطلة بالفعل.")
            return

        reply = QMessageBox.question(
            self,
            "⚠️ تأكيد تعطيل الخزنة",
            f"هل أنت متأكد من تعطيل هذه الخزنة؟\n\n"
            f"الاسم: {selected.name}\n"
            f"المرجع الداخلي: {selected.code}\n\n"
            f"يمكنك إعادة تفعيلها لاحقاً من شاشة التعديل عند الحاجة.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                account_id = selected._mongo_id or str(selected.id) or selected.code
                self.accounting_service.update_account(
                    account_id,
                    {"status": schemas.AccountStatus.ARCHIVED},
                )
                notify_success(f"تم تعطيل الخزنة '{selected.name}'", "تعطيل خزنة")
                self.load_accounts_data(force_refresh=True)
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل تعطيل الخزنة: {e}")

    # ✨ STEP 1: Summary Panel Creation
    def _legacy_create_summary_panel(self):
        """إنشاء لوحة الملخص المالي - تصميم احترافي متجاوب 100%"""
        from PyQt6.QtWidgets import QScrollArea

        # إطار خارجي مع scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {COLORS["bg_medium"]};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS["primary"]};
                border-radius: 3px;
                min-height: 20px;
            }}
        """
        )

        panel = QFrame()
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        panel.setStyleSheet(
            f"""
            QFrame {{
                background: {COLORS["bg_dark"]};
                border: none;
            }}
        """
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(10)
        panel_layout.setContentsMargins(8, 8, 8, 8)

        # العنوان الرئيسي
        title = QLabel("📊 الملخص المالي")
        title.setStyleSheet(
            f"""
            font-size: 14px;
            font-weight: bold;
            font-family: 'Cairo';
            color: white;
            padding: 10px;
            background: {COLORS["primary"]};
            border-radius: 8px;
        """
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(title)

        # === الأصول ===
        self.assets_label = self._create_compact_item("💰", "الأصول", "0.00", "#10B981")
        panel_layout.addWidget(self.assets_label)

        # === الخصوم ===
        self.liabilities_label = self._create_compact_item(
            "📉", "الخصوم", "0.00", COLORS["warning"]
        )
        panel_layout.addWidget(self.liabilities_label)

        # === حقوق الملكية ===
        self.equity_label = self._create_compact_item(
            "🏦", "حقوق الملكية", "0.00", COLORS["primary"]
        )
        panel_layout.addWidget(self.equity_label)

        # فاصل
        sep1 = QFrame()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background: {COLORS['border']};")
        panel_layout.addWidget(sep1)

        # === الإيرادات ===
        self.revenue_summary_label = self._create_compact_item("📈", "الإيرادات", "0.00", "#10B981")
        panel_layout.addWidget(self.revenue_summary_label)

        # === المصروفات ===
        self.expenses_summary_label = self._create_compact_item(
            "💸", "المصروفات", "0.00", COLORS["danger"]
        )
        panel_layout.addWidget(self.expenses_summary_label)

        # فاصل
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {COLORS['border']};")
        panel_layout.addWidget(sep2)

        # === صافي الربح ===
        self.net_profit_summary_label = self._create_profit_card("💎", "صافي الربح", "0.00")
        panel_layout.addWidget(self.net_profit_summary_label)

        panel_layout.addStretch()

        # زر تحديث
        refresh_btn = QPushButton("🔄 تحديث")
        refresh_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {COLORS["primary"]};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
                font-family: 'Cairo';
            }}
            QPushButton:hover {{
                background: {COLORS["primary_hover"]};
            }}
        """
        )
        refresh_btn.clicked.connect(self.update_summary_labels)
        panel_layout.addWidget(refresh_btn)

        scroll.setWidget(panel)
        return scroll

    def _legacy_create_compact_item(self, icon: str, title: str, value: str, color: str) -> QFrame:
        """إنشاء عنصر ملخص مالي مضغوط"""
        frame = QFrame()
        frame.setStyleSheet(
            f"""
            QFrame {{
                background: {COLORS["bg_medium"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
                padding: 6px;
            }}
        """
        )

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # الأيقونة والعنوان
        title_label = QLabel(f"{icon} {title}")
        title_label.setStyleSheet(
            f"""
            color: {COLORS["text_secondary"]};
            font-size: 11px;
            font-family: 'Cairo';
            background: transparent;
        """
        )
        layout.addWidget(title_label)

        layout.addStretch()

        # القيمة
        value_label = QLabel(f"{value} ج.م")
        value_label.setObjectName("value_label")
        value_label.setStyleSheet(
            f"""
            color: {color};
            font-size: 12px;
            font-weight: bold;
            font-family: 'Cairo';
            background: transparent;
        """
        )
        layout.addWidget(value_label)

        frame.setProperty("value_color", color)
        return frame

    def _legacy_create_profit_card(self, icon: str, title: str, value: str) -> QFrame:
        """إنشاء بطاقة صافي الربح"""
        frame = QFrame()
        frame.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(16, 185, 129, 0.15),
                    stop:1 rgba(16, 185, 129, 0.05));
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 8px;
                padding: 8px;
            }
        """
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # العنوان
        title_label = QLabel(f"{icon} {title}")
        title_label.setStyleSheet(
            f"""
            color: {COLORS["text_secondary"]};
            font-size: 11px;
            font-family: 'Cairo';
            background: transparent;
        """
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # القيمة
        value_label = QLabel(f"{value} ج.م")
        value_label.setObjectName("value_label")
        value_label.setStyleSheet(
            """
            color: #10B981;
            font-size: 16px;
            font-weight: bold;
            font-family: 'Cairo';
            background: transparent;
        """
        )
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)

        return frame

    def build_summary_panel(self):
        """إنشاء لوحة ملخص الخزن بتصميم تشغيلي واضح."""
        scroll_area = QScrollArea()
        scroll_area.setObjectName("AccountingSummaryScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll_area.setStyleSheet(
            f"""
            QScrollArea#AccountingSummaryScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea#AccountingSummaryScrollArea QScrollBar:vertical {{
                background: {_rgba_css(COLORS["bg_dark"], 190)};
                width: 10px;
                margin: 6px 0 6px 4px;
                border-radius: 5px;
            }}
            QScrollArea#AccountingSummaryScrollArea QScrollBar::handle:vertical {{
                background: {_rgba_css(COLORS["primary"], 145)};
                min-height: 28px;
                border-radius: 5px;
            }}
            QScrollArea#AccountingSummaryScrollArea QScrollBar::handle:vertical:hover {{
                background: {_rgba_css(COLORS["primary"], 185)};
            }}
            QScrollArea#AccountingSummaryScrollArea QScrollBar::add-line:vertical,
            QScrollArea#AccountingSummaryScrollArea QScrollBar::sub-line:vertical,
            QScrollArea#AccountingSummaryScrollArea QScrollBar::add-page:vertical,
            QScrollArea#AccountingSummaryScrollArea QScrollBar::sub-page:vertical {{
                background: transparent;
                height: 0;
            }}
        """
        )

        panel = QFrame()
        panel.setObjectName("AccountingSummaryPanelV2")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        panel.setStyleSheet(
            f"""
            QFrame#AccountingSummaryPanelV2 {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #041f45, stop:1 #082957);
                border: 1px solid {_rgba_css(COLORS["border"], 255)};
                border-radius: 18px;
            }}
            QFrame#AccountingSummaryHeaderV2 {{
                background: {_rgba_css(COLORS["bg_light"], 180)};
                border: 1px solid {_rgba_css(COLORS["primary"], 40)};
                border-radius: 14px;
            }}
            QLabel#AccountingSummaryTitleV2 {{
                color: {COLORS["text_primary"]};
                font-size: 16px;
                font-weight: 700;
                font-family: 'Cairo';
                background: transparent;
            }}
            QLabel#AccountingSummarySubtitleV2 {{
                color: #9eb6d4;
                font-size: 10px;
                font-weight: 600;
                font-family: 'Cairo';
                background: transparent;
            }}
            QLabel#AccountingSummaryFooterV2 {{
                color: {COLORS["text_secondary"]};
                font-size: 10px;
                font-weight: 600;
                font-family: 'Cairo';
                background: transparent;
                padding: 2px 4px;
            }}
        """
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(9)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.summary_header_frame = QFrame()
        self.summary_header_frame.setObjectName("AccountingSummaryHeaderV2")
        header_layout = QHBoxLayout(self.summary_header_frame)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(9)

        header_text_layout = QVBoxLayout()
        header_text_layout.setContentsMargins(0, 0, 0, 0)
        header_text_layout.setSpacing(1)

        self.summary_title_label = QLabel("ملخص الخزن")
        self.summary_title_label.setObjectName("AccountingSummaryTitleV2")
        self.summary_title_label.setFont(get_cairo_font(16, bold=True))
        self.summary_title_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header_text_layout.addWidget(self.summary_title_label)

        self.summary_subtitle_label = QLabel(
            "نظرة مباشرة على الرصيد الحالي وحركة التحصيل والصرف لكل الخزن."
        )
        self.summary_subtitle_label.setObjectName("AccountingSummarySubtitleV2")
        self.summary_subtitle_label.setFont(get_cairo_font(10))
        self.summary_subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header_text_layout.addWidget(self.summary_subtitle_label)
        header_layout.addLayout(header_text_layout, 1)

        self.summary_refresh_btn = QPushButton("🔄 تحديث الملخص")
        self.summary_refresh_btn.setStyleSheet(
            f"""
            QPushButton {{
                color: {COLORS["text_primary"]};
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {_rgba_css(COLORS["primary"], 86)},
                    stop:1 {_rgba_css(COLORS["primary_dark"], 132)});
                border: 1px solid {_rgba_css(COLORS["primary"], 82)};
                border-radius: 10px;
                padding: 0 14px;
                font-size: 11px;
                font-weight: 700;
                font-family: 'Cairo';
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {_rgba_css(COLORS["primary"], 102)},
                    stop:1 {_rgba_css(COLORS["primary_dark"], 146)});
                border-color: {_rgba_css(COLORS["primary"], 98)};
            }}
            QPushButton:pressed {{
                background: {_rgba_css(COLORS["primary_dark"], 168)};
            }}
            """
        )
        self.summary_refresh_btn.setMinimumWidth(122)
        self.summary_refresh_btn.setMinimumHeight(28)
        self.summary_refresh_btn.setMaximumHeight(30)
        self.summary_refresh_btn.clicked.connect(
            lambda: self.load_accounts_data(force_refresh=True)
        )
        header_layout.addWidget(self.summary_refresh_btn, 0, Qt.AlignmentFlag.AlignLeft)
        panel_layout.addWidget(self.summary_header_frame)

        balance_section, balance_layout = self._create_section_card(
            "الوضع الحالي",
            "الرصيد المتاح الآن وعدد الخزن الجاهزة والأنواع المستخدمة.",
            COLORS["primary"],
            "تشغيلي",
        )
        self.assets_label = self._build_metric_card(
            "💰",
            "إجمالي الرصيد",
            "0.00",
            "#10B981",
        )
        balance_layout.addWidget(self.assets_label, 0, 0, 1, 2)
        self.liabilities_label = self._build_metric_card(
            "✅",
            "الخزن الجاهزة",
            "0",
            COLORS["primary"],
            value_suffix="خزنة",
        )
        balance_layout.addWidget(self.liabilities_label, 1, 0)
        self.equity_label = self._build_metric_card(
            "🗂️",
            "أنواع الخزن",
            "0",
            "#46b4ff",
            value_suffix="نوع",
        )
        balance_layout.addWidget(self.equity_label, 1, 1)
        balance_layout.setColumnStretch(0, 1)
        balance_layout.setColumnStretch(1, 1)
        panel_layout.addWidget(balance_section)

        performance_section, performance_layout = self._create_section_card(
            "حركة الأموال",
            "إجمالي الوارد والصادر وصافي الحركة المسجلة على الخزن.",
            "#10B981",
            "حركة مباشرة",
        )
        self.revenue_summary_label = self._build_metric_card(
            "📈",
            "إجمالي الوارد",
            "0.00",
            "#10B981",
        )
        performance_layout.addWidget(self.revenue_summary_label, 0, 0)
        self.expenses_summary_label = self._build_metric_card(
            "💸",
            "إجمالي الصادر",
            "0.00",
            COLORS["danger"],
        )
        performance_layout.addWidget(self.expenses_summary_label, 0, 1)
        self.net_profit_summary_label = self._build_profit_card("⚖️", "صافي الحركة", "0.00")
        performance_layout.addWidget(self.net_profit_summary_label, 1, 0, 1, 2)
        performance_layout.setColumnStretch(0, 1)
        performance_layout.setColumnStretch(1, 1)
        panel_layout.addWidget(performance_section)

        self.summary_footer_label = QLabel(
            "يعرض هذا الجانب الخزن التشغيلية الفعلية فقط مع الوارد والصادر والرصيد المباشر."
        )
        self.summary_footer_label.setObjectName("AccountingSummaryFooterV2")
        self.summary_footer_label.setFont(get_cairo_font(10))
        self.summary_footer_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.summary_footer_label.setWordWrap(True)
        panel_layout.addWidget(self.summary_footer_label)
        panel_layout.addStretch(1)

        self.summary_content_widget = panel
        scroll_area.setWidget(panel)
        return scroll_area

    def _build_metric_card(
        self,
        icon: str,
        title: str,
        value: str,
        color: str,
        *,
        caption: str = "",
        value_suffix: str | None = "جنيه",
    ) -> QFrame:
        """بطاقة قيمة مختصرة لملخص الخزن."""
        frame = QFrame()
        frame.setObjectName("AccountingMetricCardV2")
        frame.setFixedHeight(84)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if caption:
            frame.setToolTip(caption)
        frame.setStyleSheet(
            f"""
            QFrame#AccountingMetricCardV2 {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {COLORS["bg_medium"]}, stop:1 #103867);
                border: 1px solid {_rgba_css(color, 90)};
                border-radius: 14px;
            }}
            QLabel#MetricTitleV2 {{
                color: {COLORS["text_primary"]};
                background: transparent;
                font-size: 11px;
                font-weight: 700;
                font-family: 'Cairo';
            }}
        """
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        title_label = QLabel(f"{title} {icon}")
        title_label.setObjectName("MetricTitleV2")
        title_label.setFont(get_cairo_font(11, bold=True))
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(title_label)

        value_text = str(value)
        if value_suffix:
            value_text = f"{value} {value_suffix}"

        value_label = QLabel(value_text)
        value_label.setObjectName("value_label")
        value_label.setFont(get_cairo_font(18, bold=True))
        value_label.setMinimumHeight(28)
        value_label.setStyleSheet(
            f"""
            color: {color};
            font-size: 18px;
            font-weight: bold;
            font-family: 'Cairo';
            background: transparent;
        """
        )
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(value_label)

        frame.setProperty("value_color", color)
        return frame

    def _build_profit_card(self, icon: str, title: str, value: str) -> QFrame:
        """بطاقة بارزة لإظهار صافي الحركة الحالية."""
        frame = QFrame()
        frame.setObjectName("AccountingProfitCard")
        frame.setMinimumHeight(94)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply_profit_card_state(frame, True)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        title_label = QLabel(f"{icon} {title}")
        title_label.setFont(get_cairo_font(12, bold=True))
        title_label.setStyleSheet(
            f"""
            color: {COLORS["text_primary"]};
            font-size: 12px;
            font-weight: 700;
            font-family: 'Cairo';
            background: transparent;
        """
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        value_label = QLabel(f"{value} جنيه")
        value_label.setObjectName("value_label")
        value_label.setFont(get_cairo_font(20, bold=True))
        value_label.setMinimumHeight(34)
        value_label.setStyleSheet(
            """
            color: #10B981;
            font-size: 20px;
            font-weight: bold;
            font-family: 'Cairo';
            background: transparent;
        """
        )
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        return frame

    def _apply_profit_card_state(self, frame: QFrame, is_positive: bool):
        """تغيير مظهر بطاقة صافي الربح حسب القيمة."""
        accent = "#10B981" if is_positive else "#EF4444"
        frame.setStyleSheet(
            f"""
            QFrame#AccountingProfitCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {_rgba_css(accent, 22)}, stop:1 {_rgba_css(accent, 10)});
                border: 1px solid {_rgba_css(accent, 105)};
                border-radius: 16px;
            }}
        """
        )

    def update_summary_labels(self, tree_map: dict | None = None):
        """
        ✨ تحديث ملخص الخزن باستخدام الرصيد الحالي وحركة الوارد والصادر

        Args:
            tree_map: قاموس الشجرة مع الأرصدة المحسوبة عند الحاجة
        """
        safe_print("INFO: [AccManager] جاري تحديث ملخص الخزن...")
        try:
            rows = list(self.cashbox_rows or [])
            if (not rows) and tree_map and isinstance(tree_map, dict):
                rows = self._build_cashbox_rows(tree_map)
            elif not rows:
                safe_print("DEBUG: [Summary] لا توجد خزن محمّلة - محاولة جلب الشجرة...")
                tree_map = self.accounting_service.get_hierarchy_with_balances(force_refresh=True)
                rows = self._build_cashbox_rows(tree_map if isinstance(tree_map, dict) else {})

            summary = self._cashbox_summary(rows)

            self._update_summary_value(self.assets_label, float(summary["total_balance"]))
            self._update_text_value(
                self.liabilities_label, f"{int(summary['active_cashboxes'])} خزنة"
            )
            self._update_text_value(self.equity_label, f"{int(summary['category_count'])} نوع")
            self._update_summary_value(self.revenue_summary_label, float(summary["total_inflow"]))
            self._update_summary_value(self.expenses_summary_label, float(summary["total_outflow"]))
            self._update_profit_value(self.net_profit_summary_label, float(summary["net_flow"]))

            # تجنب طباعة الملخص في كل تحديث لأن ذلك يسبب ضوضاء ويؤثر على الأداء.

        except Exception as e:
            safe_print(f"ERROR: [AccManager] فشل تحديث ملخص الخزن: {e}")
            import traceback

            traceback.print_exc()

    def _update_summary_value(self, frame: QFrame, value: float):
        """تحديث قيمة عنصر الملخص"""
        try:
            value_label = frame.findChild(QLabel, "value_label")
            if value_label:
                value_label.setText(f"{value:,.2f} جنيه")
        except Exception as e:
            safe_print(f"WARNING: فشل تحديث القيمة: {e}")

    def _update_text_value(self, frame: QFrame, text: str):
        """تحديث قيمة نصية داخل بطاقات الملخص."""
        try:
            value_label = frame.findChild(QLabel, "value_label")
            if value_label:
                value_label.setText(text)
        except Exception as e:
            safe_print(f"WARNING: فشل تحديث القيمة النصية: {e}")

    def _update_profit_value(self, frame: QFrame, value: float):
        """تحديث قيمة البطاقة البارزة مع تغيير اللون حسب الإشارة."""
        try:
            value_label = frame.findChild(QLabel, "value_label")
            if value_label:
                if value >= 0:
                    value_label.setText(f"{value:,.2f} جنيه")
                    value_label.setStyleSheet(
                        "color: #10B981; font-size: 20px; font-weight: bold; font-family: 'Cairo'; background: transparent;"
                    )
                    self._apply_profit_card_state(frame, True)
                else:
                    value_label.setText(f"{value:,.2f} جنيه")
                    value_label.setStyleSheet(
                        "color: #EF4444; font-size: 20px; font-weight: bold; font-family: 'Cairo'; background: transparent;"
                    )
                    self._apply_profit_card_state(frame, False)
        except Exception as e:
            safe_print(f"WARNING: فشل تحديث صافي الربح: {e}")

    # ✨ STEP 3: ENABLE LEDGER - Ledger Window Method
    def open_ledger_window(self, index):
        """فتح نافذة حركة الخزنة عند النقر المزدوج."""
        safe_print("INFO: [AccountingManager] تم النقر المزدوج على خزنة")

        # الحصول على العنصر من الفهرس
        item = self.accounts_model.itemFromIndex(index)
        if not item:
            safe_print("WARNING: [AccountingManager] لم يتم العثور على عنصر الخزنة")
            return

        # الحصول على الحساب من البيانات المخزنة
        account = item.data(Qt.ItemDataRole.UserRole)
        if not account:
            safe_print("WARNING: [AccountingManager] لم يتم العثور على بيانات الخزنة")
            return

        safe_print(f"INFO: [AccountingManager] فتح حركة خزنة: {account.name} ({account.code})")

        # التحقق إذا كان حساب مجموعة
        is_group = getattr(account, "is_group", False) or self._is_group_account(
            account.code, self.all_accounts_list
        )
        if is_group:
            QMessageBox.information(
                self,
                "تنبيه",
                f"الخزنة '{account.name}' مصنفة كمجموعة داخلية.\n\n"
                f"يرجى اختيار خزنة تشغيلية فرعية لعرض الحركة.",
            )
            return

        try:
            # فتح نافذة حركة الخزنة
            from ui.ledger_window import LedgerWindow

            safe_print("INFO: [AccountingManager] إنشاء نافذة حركة الخزنة...")
            ledger_window = LedgerWindow(
                account=account, accounting_service=self.accounting_service, parent=self
            )

            safe_print("INFO: [AccountingManager] عرض نافذة حركة الخزنة...")
            ledger_window.exec()

        except ImportError as e:
            safe_print(f"ERROR: [AccountingManager] فشل استيراد LedgerWindow: {e}")
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل تحميل نافذة حركة الخزنة.\n\n"
                f"الملف ui/ledger_window.py غير موجود أو به خطأ.\n\n"
                f"الخطأ: {str(e)}",
            )
        except Exception as e:
            safe_print(f"ERROR: [AccountingManager] فشل فتح حركة الخزنة: {e}")
            import traceback

            traceback.print_exc()
            QMessageBox.critical(self, "خطأ", f"فشل فتح حركة الخزنة:\n\n{str(e)}")
