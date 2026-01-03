# الملف: ui/accounting_manager.py
"""
تاب المحاسبة - إدارة الحسابات بشكل شجري
"""



from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from core.signals import app_signals
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
    from ui.notification_system import notify_success, notify_error, notify_warning, notify_info
except ImportError:
    def notify_success(msg, title=None): pass
    def notify_error(msg, title=None): pass
    def notify_warning(msg, title=None): pass
    def notify_info(msg, title=None): pass

# ✨ Import Global Events for Real-time Updates
try:
    from shared.events import events
    EVENTS_AVAILABLE = True
except ImportError:
    EVENTS_AVAILABLE = False
    safe_print("WARNING: Global events not available")


class AccountingManagerTab(QWidget):
    """تاب المحاسبة الرئيسي"""

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
        
        # ⚡ حماية من التحديث المتكرر
        self._is_loading = False
        self._last_refresh_time = 0

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
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

    def _connect_realtime_signals(self):
        """⚡ ربط جميع الإشارات للتحديث الفوري التلقائي"""
        # إشارات التحديث العامة
        app_signals.data_changed.connect(self._on_any_data_changed)
        app_signals.accounts_changed.connect(self.load_accounts_data)
        app_signals.journal_entry_created.connect(self._on_journal_entry_created)
        app_signals.accounting_changed.connect(self.load_accounts_data)
        
        # ⚡ إشارات المشاريع والدفعات (للتحديث الفوري عند إنشاء مشروع أو دفعة)
        app_signals.projects_changed.connect(self._on_projects_changed)
        app_signals.payments_changed.connect(self._on_payments_changed)
        
        # ⚡ إشارات المصروفات
        app_signals.expenses_changed.connect(self._on_expenses_changed)

        # ✨ Connect to Global Events for Real-time Updates
        if EVENTS_AVAILABLE:
            events.data_changed.connect(self._on_any_data_changed)
            events.accounting_refresh.connect(self.load_accounts_data)
            safe_print("INFO: ✅ [AccManager] تم ربط الأحداث العالمية - التحديث الفوري مفعّل!")
        
        safe_print("INFO: ✅ [AccManager] تم ربط جميع إشارات Real-time Sync")

    def _on_any_data_changed(self, data_type: str = None):
        """⚡ معالج التحديث الفوري عند تغيير أي بيانات"""
        # تحديث فقط إذا كان التغيير متعلق بالمحاسبة
        relevant_types = ['accounts', 'accounting', 'projects', 'payments', 'expenses', 'journal_entries', None]
        if data_type in relevant_types:
            safe_print(f"INFO: ✅ [AccManager] تحديث فوري - نوع البيانات: {data_type}")
            self.load_accounts_data()

    def _on_journal_entry_created(self, entry_id: str = None):
        """⚡ معالج إنشاء قيد محاسبي جديد - تحديث فوري"""
        safe_print(f"INFO: ✅ [AccManager] قيد محاسبي جديد: {entry_id} - تحديث الأرصدة فوراً...")
        # إبطال الـ cache لضمان جلب البيانات الجديدة
        self.accounting_service._hierarchy_cache = None
        self.accounting_service._hierarchy_cache_time = 0
        self.load_accounts_data()

    def _on_projects_changed(self):
        """⚡ معالج تغيير المشاريع - تحديث المحاسبة فوراً"""
        safe_print("INFO: ✅ [AccManager] تغيير في المشاريع - تحديث المحاسبة...")
        # إبطال الـ cache
        self.accounting_service._hierarchy_cache = None
        self.accounting_service._hierarchy_cache_time = 0
        self.load_accounts_data()

    def _on_payments_changed(self):
        """⚡ معالج تغيير الدفعات - تحديث المحاسبة فوراً"""
        safe_print("INFO: ✅ [AccManager] تغيير في الدفعات - تحديث المحاسبة...")
        # إبطال الـ cache
        self.accounting_service._hierarchy_cache = None
        self.accounting_service._hierarchy_cache_time = 0
        self.load_accounts_data()

    def _on_expenses_changed(self):
        """⚡ معالج تغيير المصروفات - تحديث المحاسبة فوراً"""
        safe_print("INFO: ✅ [AccManager] تغيير في المصروفات - تحديث المحاسبة...")
        # إبطال الـ cache
        self.accounting_service._hierarchy_cache = None
        self.accounting_service._hierarchy_cache_time = 0
        self.load_accounts_data()

    def on_data_changed(self):
        """معالج التحديث الفوري عند تغيير البيانات (للتوافق)"""
        self._on_any_data_changed()

    def on_journal_entry_created(self, entry_id: str):
        """معالج إنشاء قيد محاسبي جديد (للتوافق)"""
        self._on_journal_entry_created(entry_id)

    def resizeEvent(self, event):
        """معالج تغيير حجم النافذة - تحويل الـ splitter حسب العرض"""
        super().resizeEvent(event)
        width = self.width()
        
        # إذا كان العرض صغير، نحول لعمودي
        if hasattr(self, 'main_splitter'):
            if width < 800:
                if self.main_splitter.orientation() != Qt.Orientation.Vertical:
                    self.main_splitter.setOrientation(Qt.Orientation.Vertical)
            else:
                if self.main_splitter.orientation() != Qt.Orientation.Horizontal:
                    self.main_splitter.setOrientation(Qt.Orientation.Horizontal)

    # ==================== تاب إدارة الحسابات ====================
    def setup_accounts_tab(self, main_layout: QVBoxLayout):
        """إعداد واجهة إدارة الحسابات"""
        layout = main_layout  # استخدام الـ layout الرئيسي مباشرة

        # === شريط الأزرار المتجاوب ===
        from ui.responsive_toolbar import ResponsiveToolbar
        self.toolbar = ResponsiveToolbar()

        self.add_account_btn = QPushButton("➕ إضافة حساب")
        self.add_account_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.add_account_btn.clicked.connect(self.open_account_editor)

        self.edit_account_btn = QPushButton("✏️ تعديل")
        self.edit_account_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_account_btn.clicked.connect(self.open_account_editor_for_selected)

        self.delete_account_btn = QPushButton("🗑️ حذف")
        self.delete_account_btn.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_account_btn.clicked.connect(self.delete_selected_account)

        self.refresh_btn = QPushButton("🔄 تحديث")
        self.refresh_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_btn.clicked.connect(self.load_accounts_data)

        # إضافة الأزرار للـ toolbar المتجاوب
        self.toolbar.addButton(self.add_account_btn)
        self.toolbar.addButton(self.edit_account_btn)
        self.toolbar.addButton(self.delete_account_btn)
        self.toolbar.addButton(self.refresh_btn)
        
        layout.addWidget(self.toolbar)

        # ✨ استخدام QSplitter للتجاوب التلقائي 100%
        from PyQt6.QtWidgets import QSplitter
        
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #334155;
                width: 3px;
                margin: 0 3px;
            }
        """)

        # --- LEFT SIDE: SUMMARY PANEL ---
        self.summary_panel = self.create_summary_panel()
        self.main_splitter.addWidget(self.summary_panel)

        # --- RIGHT SIDE: TREE CONTAINER ---
        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)

        # 1. شجرة الحسابات
        self.accounts_tree = QTreeView()
        self.accounts_model = QStandardItemModel()
        self.accounts_model.setHorizontalHeaderLabels([
            "الكود", "اسم الحساب", "النوع", "العملة", "الرصيد", "الحالة"
        ])
        self.accounts_tree.setModel(self.accounts_model)
        self.accounts_tree.setAlternatingRowColors(True)

        # ✅ تفعيل اتجاه RTL للعربية
        self.accounts_tree.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        # ✅ ستايل محسّن للجدول مع وضوح أفضل (ألوان SkyWave Brand)
        self.accounts_tree.setStyleSheet(CHART_OF_ACCOUNTS_TREE_STYLE)

        # تقليل المسافة البادئة للشجرة
        self.accounts_tree.setIndentation(25)

        # جعل الـ tree متجاوب
        self.accounts_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تكبير خط الشجرة
        font = self.accounts_tree.font()
        font.setPointSize(10)
        font.setFamily("Segoe UI")
        self.accounts_tree.setFont(font)

        # ✅ تفعيل التمرير الأفقي عند الحاجة
        self.accounts_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.accounts_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # ✅ تحديد ارتفاع الصفوف بشكل ثابت
        self.accounts_tree.setUniformRowHeights(True)

        # ✅ إعداد الأعمدة - استراتيجية "التحكم الكامل" (Fixed Widths + Stretch) 🛡️
        # حل مشكلة ResizeToContents مع RightToLeft
        header = self.accounts_tree.header()
        if header is not None:
            header.setMinimumHeight(40)
            # ⚠️ خطوة مهمة: إلغاء التمدد التلقائي لآخر عمود عشان ميبوظش الحسابات في العربي
            header.setStretchLastSection(False)
            
            # تحديد الحد الأدنى لعرض أي عمود
            header.setMinimumSectionSize(60)

            # ✅ إعداد الأعمدة - تكبير الحجم والسماح بالتحكم اليدوي (Interactive)
            # العمود 0: الكود (عرض كبير 150)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            self.accounts_tree.setColumnWidth(0, 150)

            # العمود 1: اسم الحساب (🔥 Stretch - يأخذ كل المساحة الباقية)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

            # العمود 2: النوع (130)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            self.accounts_tree.setColumnWidth(2, 130)

            # العمود 3: العملة (80)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            self.accounts_tree.setColumnWidth(3, 80)

            # العمود 4: الرصيد (كبير 200 للأرقام الكبيرة)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
            self.accounts_tree.setColumnWidth(4, 200)

            # العمود 5: الحالة (100)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
            self.accounts_tree.setColumnWidth(5, 100)

        # ✨ STEP 3: ENABLE LEDGER - Double Click for Ledger Window
        self.accounts_tree.doubleClicked.connect(self.open_ledger_window)

        tree_layout.addWidget(self.accounts_tree)

        # إضافة الشجرة للـ splitter
        self.main_splitter.addWidget(tree_container)
        
        # تعيين النسب الافتراضية (20% للملخص، 80% للشجرة)
        self.main_splitter.setStretchFactor(0, 1)  # الملخص
        self.main_splitter.setStretchFactor(1, 4)  # الشجرة

        # ⚡ إضافة الـ splitter مع stretch لملء كل المساحة
        layout.addWidget(self.main_splitter, 1)  # stretch = 1 لملء المساحة

    def _setup_tree_columns(self):
        """ضبط أعمدة الشجرة - يتم استدعاؤها عند تغيير حجم النافذة"""
        # الأعمدة تم ضبطها في setup_accounts_tab
        pass

    def _recalculate_hierarchy_tree(self, tree_map: dict):
        """
        🔥 إصلاح نهائي: دالة تقوم بإعادة حساب إجماليات الآباء بناءً على مجموع الأبناء
        لضمان اتساق الشجرة والملخص المالي بغض النظر عن الأخطاء في قاعدة البيانات.
        """

        def calculate_node_recursive(node):
            # 1. إذا لم يكن للعقدة أبناء، نعتمد رصيدها الحالي (Total) وننتهي
            children = node.get('children', [])
            if not children:
                return node.get('total', 0.0)

            # 2. إذا كان هناك أبناء، نقوم بجمع أرصدتهم (بعد إعادة حسابهم أيضاً)
            calculated_sum = 0.0
            for child in children:
                calculated_sum += calculate_node_recursive(child)

            # 3. تحديث رصيد العقدة الحالية ليساوي مجموع الأبناء تماماً
            # هذا يجبر "الأصول" أن تكون مجموع "النقدية + العملاء + ..."
            node['total'] = calculated_sum
            return calculated_sum

        # تحديد الجذور (Nodes التي ليس لها أباء داخل الـ Map) للبدء منها
        # نستخدم set للكفاءة
        all_codes = set(tree_map.keys())
        roots = []
        for code, node in tree_map.items():
            acc = node['obj']
            # محاولة معرفة الكود للأب
            parent_code = getattr(acc, 'parent_id', None) or getattr(acc, 'parent_code', None)
            # إذا لم يكن له أب، أو أبوه غير موجود في القائمة المحملة، فهو جذر
            if not parent_code or parent_code not in all_codes:
                roots.append(node)

        # بدء عملية الجمع التراكمي من الجذور
        for root in roots:
            calculate_node_recursive(root)

        return tree_map

    def load_accounts_data(self):
        """⚡ تحميل الحسابات في الخلفية لمنع التجميد (مع حماية من التحديث المتكرر)"""
        import time
        from PyQt6.QtWidgets import QApplication
        from core.data_loader import get_data_loader

        # ⚡ حماية من التحديث المتكرر (الحد الأدنى 1 ثانية بين كل تحديث)
        current_time = time.time()
        if self._is_loading:
            safe_print("WARNING: [AccManager] ⏳ تحميل جاري بالفعل - تم تجاهل الطلب")
            return
        if (current_time - self._last_refresh_time) < 1.0:
            safe_print("WARNING: [AccManager] ⏳ تحديث متكرر سريع - تم تجاهل الطلب")
            return

        self._is_loading = True
        self._last_refresh_time = current_time
        safe_print("INFO: [AccManager] جاري تحميل شجرة الحسابات...")

        QApplication.processEvents()

        # دالة جلب البيانات (مع إجبار التحديث من قاعدة البيانات)
        def fetch_accounts():
            try:
                # ⚡ إجبار التحديث من قاعدة البيانات (بدون cache)
                tree_map = self.accounting_service.get_hierarchy_with_balances(force_refresh=True)
                all_accounts = self.accounting_service.repo.get_all_accounts()
                return {'tree_map': tree_map, 'all_accounts': all_accounts}
            except Exception as e:
                safe_print(f"ERROR: [AccManager] فشل جلب الحسابات: {e}")
                return {'tree_map': {}, 'all_accounts': []}

        # دالة تحديث الواجهة
        def on_data_loaded(data):
            try:
                tree_map = data['tree_map']
                self.all_accounts_list = data['all_accounts']

                # 🔥 [تعديل هام] تطبيق الإصلاح الرياضي قبل العرض
                if tree_map:
                    # هذه الخطوة تضمن أن الأب = مجموع الأبناء دائماً
                    tree_map = self._recalculate_hierarchy_tree(tree_map)

                self._render_accounts_tree(tree_map)

                # تحديث الملخص المالي بالأرقام الجديدة الصحيحة
                self.update_summary_labels(tree_map)

                safe_print(
                    f"INFO: [AccManager] ✅ تم تحميل {len(self.all_accounts_list)} حساب وتمت موازنة الشجرة."
                )
            except Exception as e:
                safe_print(f"ERROR: [AccManager] فشل تحديث الشجرة: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # ⚡ إعادة تفعيل التحميل
                self._is_loading = False

        def on_error(error_msg):
            safe_print(f"ERROR: [AccManager] فشل تحميل الحسابات: {error_msg}")
            self._is_loading = False

        # تحميل في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="accounts_tree",
            load_function=fetch_accounts,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True
        )

    def _render_accounts_tree(self, tree_map):
        """عرض شجرة الحسابات مع ضبط المقاسات إجبارياً"""
        from PyQt6.QtWidgets import QApplication

        self.accounts_model.clear()
        # إعادة تسمية الهيدر لأن clear بتمسحه
        self.accounts_model.setHorizontalHeaderLabels([
            "الكود", "اسم الحساب", "النوع", "العملة", "الرصيد", "الحالة"
        ])

        root = self.accounts_model.invisibleRootItem()

        # دالة تكرارية لعرض العقد
        def render_node(node: dict, parent_item):
            """عرض عقدة وأبنائها بشكل تكراري"""
            acc = node['obj']
            calculated_balance = node['total']
            is_group = bool(node['children'])

            code_item = QStandardItem(acc.code or "")
            code_item.setEditable(False)
            code_item.setData(acc, Qt.ItemDataRole.UserRole)
            code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

            # إضافة أيقونة للاسم عشان الشكل الشجري يبان أحلى
            name_text = f"{'📁 ' if is_group else '📄 '}{acc.name}"
            name_item = QStandardItem(name_text)
            name_item.setEditable(False)
            # محاذاة في الوسط
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

            type_display = {
                'ASSET': 'أصول', 'CASH': 'أصول نقدية', 'LIABILITY': 'خصوم',
                'EQUITY': 'حقوق ملكية', 'REVENUE': 'إيرادات', 'EXPENSE': 'مصروفات',
                'أصول': 'أصول', 'أصول نقدية': 'أصول نقدية', 'خصوم': 'خصوم',
                'حقوق ملكية': 'حقوق ملكية', 'إيرادات': 'إيرادات', 'مصروفات': 'مصروفات'
            }
            type_text = type_display.get(acc.type.value if acc.type else acc.type, acc.type.value if acc.type else "")
            type_item = QStandardItem(type_text)
            type_item.setEditable(False)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

            currency = acc.currency.value if acc.currency else "EGP"
            currency_item = QStandardItem(currency)
            currency_item.setEditable(False)
            currency_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

            # عرض الرصيد كقيمة مطلقة (بدون علامة السالب) لسهولة القراءة
            display_balance = abs(calculated_balance)
            balance_text = f"{display_balance:,.2f}"
            balance_item = QStandardItem(balance_text)
            balance_item.setEditable(False)
            balance_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

            status_text = "✅ نشط" if acc.status == schemas.AccountStatus.ACTIVE else "❌ مؤرشف"
            status_item = QStandardItem(status_text)
            status_item.setEditable(False)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

            row = [code_item, name_item, type_item, currency_item, balance_item, status_item]

            if is_group:
                for item in row:
                    item.setFont(get_cairo_font(10, bold=True))
                    item.setBackground(QColor(COLORS['bg_light']))
                    item.setForeground(QColor(COLORS['text_primary']))
            else:
                for item in row:
                    item.setFont(get_cairo_font(9))
                    item.setBackground(QColor(COLORS['bg_medium']))
                    item.setForeground(QColor(COLORS['text_secondary']))

            # تلوين الأرصدة حسب نوع الحساب:
            # 🟢 الإيرادات (4xxxxx) = أخضر
            # 🔴 المصروفات (5xxxxx, 6xxxxx) = أحمر
            # البقية حسب القيمة الموجبة/السالبة
            account_code = acc.code or ""
            if account_code.startswith('4'):
                # إيرادات - أخضر دائماً
                balance_item.setForeground(QColor("#51cf66"))
            elif account_code.startswith('5') or account_code.startswith('6'):
                # مصروفات - أحمر دائماً
                balance_item.setForeground(QColor("#ff6b6b"))
            elif calculated_balance < 0:
                balance_item.setForeground(QColor("#ff6b6b"))
            elif calculated_balance > 0:
                balance_item.setForeground(QColor("#51cf66"))
            else:
                balance_item.setForeground(QColor("#adb5bd"))

            parent_item.appendRow(row)

            sorted_children = sorted(node['children'], key=lambda x: str(x['obj'].code or ""))
            for child in sorted_children:
                render_node(child, code_item)

        # تحديد الجذور
        roots = []
        for _code, node in tree_map.items():
            acc = node['obj']
            parent = getattr(acc, 'parent_id', None) or getattr(acc, 'parent_code', None)
            if not parent:
                roots.append(node)

        roots.sort(key=lambda x: str(x['obj'].code or ""))

        for root_node in roots:
            render_node(root_node, root)

        self.accounts_tree.expandAll()

        # 🔥 إجبار الأعمدة على التناسق بعد الرسم (لأن clear بتمسح الإعدادات)
        header = self.accounts_tree.header()
        # العمود 0: الكود (تكبير العرض لـ 180)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.accounts_tree.setColumnWidth(0, 200)
        # العمود 1: الاسم (Stretch) -> يملأ المساحة الفارغة
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        # العمود 2: النوع
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.accounts_tree.setColumnWidth(2, 120)
        # العمود 3: العملة
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.accounts_tree.setColumnWidth(3, 80)
        # العمود 4: الرصيد
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.accounts_tree.setColumnWidth(4, 150)
        # العمود 5: الحالة
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.accounts_tree.setColumnWidth(5, 100)

        safe_print(f"INFO: [AccManager] تم عرض {len(self.all_accounts_list)} حساب وضبط الأعمدة.")

        self.update_summary_labels(tree_map)
        QApplication.processEvents()

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
            parent_code = getattr(acc, 'parent_id', None) or getattr(acc, 'parent_code', None)
            if parent_code == code:
                return True
        return False

    def get_selected_account(self) -> schemas.Account | None:
        """الحصول على الحساب المحدد"""
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
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_accounts_data()

    def open_account_editor_for_selected(self):
        selected = self.get_selected_account()
        if not selected:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد حساب أولاً.")
            return
        dialog = AccountEditorDialog(
            accounting_service=self.accounting_service,
            all_accounts=self.all_accounts_list,
            account_to_edit=selected,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_accounts_data()

    def delete_selected_account(self):
        selected = self.get_selected_account()
        if not selected:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد حساب أولاً.")
            return

        reply = QMessageBox.question(
            self, "⚠️ تأكيد الحذف النهائي",
            f"هل أنت متأكد من حذف الحساب نهائياً؟\n\n"
            f"الكود: {selected.code}\n"
            f"الاسم: {selected.name}\n\n"
            f"⚠️ هذا الإجراء لا يمكن التراجع عنه!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                account_id = selected._mongo_id or str(selected.id)
                self.accounting_service.delete_account(account_id)
                notify_success(f"تم حذف الحساب '{selected.name}'", "حذف حساب")
                self.load_accounts_data()
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل الحذف: {e}")

    # ✨ STEP 1: Summary Panel Creation
    def create_summary_panel(self):
        """إنشاء لوحة الملخص المالي - تصميم احترافي متجاوب 100%"""
        from PyQt6.QtWidgets import QScrollArea
        
        # إطار خارجي مع scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {COLORS['bg_medium']};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['primary']};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)
        
        panel = QFrame()
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        panel.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_dark']};
                border: none;
            }}
        """)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(10)
        panel_layout.setContentsMargins(8, 8, 8, 8)

        # العنوان الرئيسي
        title = QLabel("📊 الملخص المالي")
        title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            font-family: 'Cairo';
            color: white;
            padding: 10px;
            background: {COLORS['primary']};
            border-radius: 8px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(title)

        # === الأصول ===
        self.assets_label = self._create_compact_item("💰", "الأصول", "0.00", "#10B981")
        panel_layout.addWidget(self.assets_label)

        # === الخصوم ===
        self.liabilities_label = self._create_compact_item("📉", "الخصوم", "0.00", COLORS['warning'])
        panel_layout.addWidget(self.liabilities_label)

        # === حقوق الملكية ===
        self.equity_label = self._create_compact_item("🏦", "حقوق الملكية", "0.00", COLORS['primary'])
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
        self.expenses_summary_label = self._create_compact_item("💸", "المصروفات", "0.00", COLORS['danger'])
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
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
                font-family: 'Cairo';
            }}
            QPushButton:hover {{
                background: {COLORS['primary_hover']};
            }}
        """)
        refresh_btn.clicked.connect(self.update_summary_labels)
        panel_layout.addWidget(refresh_btn)

        scroll.setWidget(panel)
        return scroll

    def _create_compact_item(self, icon: str, title: str, value: str, color: str) -> QFrame:
        """إنشاء عنصر ملخص مالي مضغوط"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_medium']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px;
            }}
        """)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)
        
        # الأيقونة والعنوان
        title_label = QLabel(f"{icon} {title}")
        title_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: 11px;
            font-family: 'Cairo';
            background: transparent;
        """)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # القيمة
        value_label = QLabel(f"{value} ج.م")
        value_label.setObjectName("value_label")
        value_label.setStyleSheet(f"""
            color: {color};
            font-size: 12px;
            font-weight: bold;
            font-family: 'Cairo';
            background: transparent;
        """)
        layout.addWidget(value_label)
        
        frame.setProperty("value_color", color)
        return frame

    def _create_profit_card(self, icon: str, title: str, value: str) -> QFrame:
        """إنشاء بطاقة صافي الربح"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(16, 185, 129, 0.15),
                    stop:1 rgba(16, 185, 129, 0.05));
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        
        # العنوان
        title_label = QLabel(f"{icon} {title}")
        title_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: 11px;
            font-family: 'Cairo';
            background: transparent;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # القيمة
        value_label = QLabel(f"{value} ج.م")
        value_label.setObjectName("value_label")
        value_label.setStyleSheet("""
            color: #10B981;
            font-size: 16px;
            font-weight: bold;
            font-family: 'Cairo';
            background: transparent;
        """)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        
        return frame

    def update_summary_labels(self, tree_map: dict | None = None):
        """
        ✨ تحديث إحصائيات الملخص المالي باستخدام الأرصدة المحسوبة تراكمياً

        Args:
            tree_map: قاموس الشجرة مع الأرصدة المحسوبة (من get_hierarchy_with_balances)
        """
        safe_print("INFO: [AccManager] جاري تحديث الملخص المالي...")
        try:
            # إذا لم يتم تمرير tree_map أو كان فارغاً، نجلبه من الخدمة
            if not tree_map or not isinstance(tree_map, dict) or len(tree_map) == 0:
                safe_print("DEBUG: [Summary] tree_map فارغ - جلب البيانات من الخدمة...")
                tree_map = self.accounting_service.get_hierarchy_with_balances(force_refresh=True)

            # ⚡ طريقة محسّنة: استخدام get_financial_summary للحصول على الأرقام الصحيحة
            try:
                summary = self.accounting_service.get_financial_summary()
                total_assets = summary.get('assets', 0.0)
                total_liabilities = summary.get('liabilities', 0.0)
                total_equity = summary.get('equity', 0.0)
                total_revenue = summary.get('revenue', 0.0)
                total_expenses = summary.get('expenses', 0.0)
                net_profit = summary.get('net_profit', 0.0)
                
                safe_print(f"DEBUG: [Summary] من get_financial_summary: أصول:{total_assets}, خصوم:{total_liabilities}, إيرادات:{total_revenue}, مصروفات:{total_expenses}")
            except Exception as e:
                safe_print(f"WARNING: [Summary] فشل get_financial_summary: {e} - استخدام الطريقة البديلة")
                total_assets = 0.0
                total_liabilities = 0.0
                total_equity = 0.0
                total_revenue = 0.0
                total_expenses = 0.0

            # ⚡ إذا كانت القيم صفر، نحاول من tree_map مباشرة
            if total_assets == 0 and total_liabilities == 0 and total_revenue == 0 and total_expenses == 0:
                safe_print("DEBUG: [Summary] محاولة من tree_map...")
                
                # جمع الأرصدة من كل الحسابات حسب النوع
                for code, node in tree_map.items():
                    acc = node.get('obj')
                    if not acc:
                        continue
                    
                    # الحصول على الرصيد
                    balance = node.get('total', 0.0)
                    if balance == 0:
                        balance = getattr(acc, 'balance', 0.0) or 0.0
                    
                    # تصنيف حسب نوع الحساب
                    acc_type = acc.type.value if hasattr(acc.type, 'value') else str(acc.type)
                    
                    # فقط الحسابات الفرعية (ليست مجموعات) لتجنب التكرار
                    is_group = getattr(acc, 'is_group', False) or node.get('is_group', False) or bool(node.get('children'))
                    
                    if not is_group:
                        if acc_type in ['ASSET', 'CASH', 'أصول', 'أصول نقدية']:
                            total_assets += balance
                        elif acc_type in ['LIABILITY', 'خصوم']:
                            total_liabilities += balance
                        elif acc_type in ['EQUITY', 'حقوق ملكية']:
                            total_equity += balance
                        elif acc_type in ['REVENUE', 'إيرادات']:
                            total_revenue += balance
                        elif acc_type in ['EXPENSE', 'مصروفات']:
                            total_expenses += balance

            # إذا كانت كل القيم صفر، نحاول من الحسابات الرئيسية
            if total_assets == 0 and total_liabilities == 0 and total_revenue == 0 and total_expenses == 0:
                safe_print("DEBUG: [Summary] محاولة من الحسابات الرئيسية...")
                # نظام 6 أرقام (Enterprise)
                total_assets = tree_map.get('100000', {}).get('total', 0.0) or tree_map.get('1000', {}).get('total', 0.0)
                total_liabilities = tree_map.get('200000', {}).get('total', 0.0) or tree_map.get('2000', {}).get('total', 0.0)
                total_equity = tree_map.get('300000', {}).get('total', 0.0) or tree_map.get('3000', {}).get('total', 0.0)
                total_revenue = tree_map.get('400000', {}).get('total', 0.0) or tree_map.get('4000', {}).get('total', 0.0)
                # COGS (500000) + OPEX (600000) = إجمالي المصروفات
                total_cogs = tree_map.get('500000', {}).get('total', 0.0)
                total_opex = tree_map.get('600000', {}).get('total', 0.0)
                total_expenses = total_cogs + total_opex or tree_map.get('5000', {}).get('total', 0.0)

            safe_print(f"DEBUG: [Summary] النهائي - أصول:{total_assets}, خصوم:{total_liabilities}, إيرادات:{total_revenue}, مصروفات:{total_expenses}")

            # حساب صافي الربح = الإيرادات - المصروفات
            if 'net_profit' not in locals() or net_profit == 0:
                net_profit = total_revenue - total_expenses

            # تحديث Labels باستخدام الدوال المساعدة
            self._update_summary_value(self.assets_label, total_assets)
            self._update_summary_value(self.liabilities_label, total_liabilities)
            self._update_summary_value(self.equity_label, total_equity)
            self._update_summary_value(self.revenue_summary_label, total_revenue)
            self._update_summary_value(self.expenses_summary_label, total_expenses)

            # تحديث صافي الربح مع تغيير اللون حسب القيمة
            self._update_profit_value(self.net_profit_summary_label, net_profit)

            safe_print("INFO: [AccManager] الملخص المالي:")
            safe_print(f"  - الأصول: {total_assets:,.2f}")
            safe_print(f"  - الخصوم: {total_liabilities:,.2f}")
            safe_print(f"  - الإيرادات: {total_revenue:,.2f}")
            safe_print(f"  - المصروفات: {total_expenses:,.2f}")
            safe_print(f"  - صافي الربح: {net_profit:,.2f}")

        except Exception as e:
            safe_print(f"ERROR: [AccManager] فشل تحديث الملخص المالي: {e}")
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

    def _update_profit_value(self, frame: QFrame, value: float):
        """تحديث قيمة صافي الربح مع تغيير اللون"""
        try:
            value_label = frame.findChild(QLabel, "value_label")
            if value_label:
                if value >= 0:
                    value_label.setText(f"{value:,.2f} جنيه")
                    value_label.setStyleSheet("color: #10B981; font-size: 18px; font-weight: bold; background: transparent;")
                    frame.setStyleSheet(f"""
                        QFrame {{
                            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 rgba(16, 185, 129, 0.1),
                                stop:0.5 rgba(16, 185, 129, 0.2),
                                stop:1 rgba(16, 185, 129, 0.1));
                            border: 2px solid rgba(16, 185, 129, 0.5);
                            border-radius: 10px;
                            padding: 10px;
                        }}
                    """)
                else:
                    value_label.setText(f"{abs(value):,.2f} جنيه (خسارة)")
                    value_label.setStyleSheet("color: #EF4444; font-size: 18px; font-weight: bold; background: transparent;")
                    frame.setStyleSheet(f"""
                        QFrame {{
                            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 rgba(239, 68, 68, 0.1),
                                stop:0.5 rgba(239, 68, 68, 0.2),
                                stop:1 rgba(239, 68, 68, 0.1));
                            border: 2px solid rgba(239, 68, 68, 0.5);
                            border-radius: 10px;
                            padding: 10px;
                        }}
                    """)
        except Exception as e:
            safe_print(f"WARNING: فشل تحديث صافي الربح: {e}")

        except Exception as e:
            safe_print(f"ERROR: [AccManager] فشل تحديث الملخص المالي: {e}")
            import traceback
            traceback.print_exc()

    # ✨ STEP 3: ENABLE LEDGER - Ledger Window Method
    def open_ledger_window(self, index):
        """فتح نافذة كشف الحساب عند النقر المزدوج"""
        safe_print("INFO: [AccountingManager] تم النقر المزدوج على الحساب")

        # الحصول على العنصر من الفهرس
        item = self.accounts_model.itemFromIndex(index)
        if not item:
            safe_print("WARNING: [AccountingManager] لم يتم العثور على العنصر")
            return

        # الحصول على الحساب من البيانات المخزنة
        account = item.data(Qt.ItemDataRole.UserRole)
        if not account:
            safe_print("WARNING: [AccountingManager] لم يتم العثور على بيانات الحساب")
            return

        safe_print(f"INFO: [AccountingManager] فتح كشف حساب: {account.name} ({account.code})")

        # التحقق إذا كان حساب مجموعة
        is_group = getattr(account, 'is_group', False) or self._is_group_account(account.code, self.all_accounts_list)
        if is_group:
            QMessageBox.information(
                self,
                "تنبيه",
                f"الحساب '{account.name}' هو حساب مجموعة.\n\n"
                f"لا يمكن عرض كشف حساب للمجموعات.\n"
                f"يرجى اختيار حساب فرعي."
            )
            return

        try:
            # فتح نافذة كشف الحساب
            from ui.ledger_window import LedgerWindow

            safe_print("INFO: [AccountingManager] إنشاء نافذة كشف الحساب...")
            ledger_window = LedgerWindow(
                account=account,
                accounting_service=self.accounting_service,
                parent=self
            )

            safe_print("INFO: [AccountingManager] عرض نافذة كشف الحساب...")
            ledger_window.exec()

        except ImportError as e:
            safe_print(f"ERROR: [AccountingManager] فشل استيراد LedgerWindow: {e}")
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل تحميل نافذة كشف الحساب.\n\n"
                f"الملف ui/ledger_window.py غير موجود أو به خطأ.\n\n"
                f"الخطأ: {str(e)}"
            )
        except Exception as e:
            safe_print(f"ERROR: [AccountingManager] فشل فتح كشف الحساب: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل فتح كشف الحساب:\n\n{str(e)}"
            )
