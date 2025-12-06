# الملف: ui/accounting_manager.py
"""
تاب المحاسبة - إدارة الحسابات بشكل شجري
"""



from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QStandardItem, QStandardItemModel
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
from ui.styles import BUTTON_STYLES, CHART_OF_ACCOUNTS_TREE_STYLE, COLORS

# ✨ Import Global Events for Real-time Updates
try:
    from shared.events import events
    EVENTS_AVAILABLE = True
except ImportError:
    EVENTS_AVAILABLE = False
    print("WARNING: Global events not available")


# ==================== شجرة الحسابات Enterprise Level (6 أرقام) ====================
# ✅ نظام 6 أرقام (Scalability) - يدعم 999 حساب فرعي تحت كل بند
# ✅ فصل COGS (5xxxxx) عن OPEX (6xxxxx) لتحليل الربحية
# ✅ دفعات مقدمة من العملاء (Unearned Revenue)
DEFAULT_ACCOUNT_TEMPLATES = [
    # ==================== 1. الأصول (100000) ====================
    {"name": "الأصول", "code": "100000", "type": schemas.AccountType.ASSET, "parent_code": None},
    {"name": "الأصول المتداولة", "code": "110000", "type": schemas.AccountType.ASSET, "parent_code": "100000"},
    {"name": "النقدية وما في حكمها", "code": "111000", "type": schemas.AccountType.CASH, "parent_code": "110000"},
    {"name": "الخزائن النقدية", "code": "111100", "type": schemas.AccountType.CASH, "parent_code": "111000"},
    {"name": "الخزنة الرئيسية (المقر)", "code": "111101", "type": schemas.AccountType.CASH, "parent_code": "111100"},
    {"name": "عهد نقدية موظفين", "code": "111102", "type": schemas.AccountType.CASH, "parent_code": "111100"},
    {"name": "الحسابات البنكية", "code": "111200", "type": schemas.AccountType.CASH, "parent_code": "111000"},
    {"name": "بنك مصر - جاري", "code": "111201", "type": schemas.AccountType.CASH, "parent_code": "111200"},
    {"name": "المحافظ الإلكترونية", "code": "111300", "type": schemas.AccountType.CASH, "parent_code": "111000"},
    {"name": "فودافون كاش (الرئيسي)", "code": "111301", "type": schemas.AccountType.CASH, "parent_code": "111300"},
    {"name": "فودافون كاش (الفرعي)", "code": "111302", "type": schemas.AccountType.CASH, "parent_code": "111300"},
    {"name": "InstaPay", "code": "111303", "type": schemas.AccountType.CASH, "parent_code": "111300"},
    {"name": "العملاء وأوراق القبض", "code": "112000", "type": schemas.AccountType.ASSET, "parent_code": "110000"},
    {"name": "عملاء تجاريين (شركات)", "code": "112100", "type": schemas.AccountType.ASSET, "parent_code": "112000"},
    {"name": "عملاء أفراد", "code": "112200", "type": schemas.AccountType.ASSET, "parent_code": "112000"},
    {"name": "أرصدة مدينة أخرى", "code": "113000", "type": schemas.AccountType.ASSET, "parent_code": "110000"},
    {"name": "مصروفات مدفوعة مقدماً", "code": "113100", "type": schemas.AccountType.ASSET, "parent_code": "113000"},
    {"name": "سلف العاملين", "code": "113200", "type": schemas.AccountType.ASSET, "parent_code": "113000"},
    {"name": "الأصول غير المتداولة", "code": "120000", "type": schemas.AccountType.ASSET, "parent_code": "100000"},
    {"name": "الأصول الثابتة", "code": "121000", "type": schemas.AccountType.ASSET, "parent_code": "120000"},
    {"name": "أجهزة حاسب آلي وسيرفرات", "code": "121100", "type": schemas.AccountType.ASSET, "parent_code": "121000"},
    {"name": "أثاث وتجهيزات مكتبية", "code": "121200", "type": schemas.AccountType.ASSET, "parent_code": "121000"},

    # ==================== 2. الخصوم (200000) ====================
    {"name": "الخصوم", "code": "200000", "type": schemas.AccountType.LIABILITY, "parent_code": None},
    {"name": "الخصوم المتداولة", "code": "210000", "type": schemas.AccountType.LIABILITY, "parent_code": "200000"},
    {"name": "الموردين", "code": "211000", "type": schemas.AccountType.LIABILITY, "parent_code": "210000"},
    {"name": "موردين تشغيل (خدمات تقنية)", "code": "211100", "type": schemas.AccountType.LIABILITY, "parent_code": "211000"},
    {"name": "مستحقات مستقلين (Freelancers)", "code": "211200", "type": schemas.AccountType.LIABILITY, "parent_code": "211000"},
    {"name": "أرصدة دائنة أخرى", "code": "212000", "type": schemas.AccountType.LIABILITY, "parent_code": "210000"},
    {"name": "دفعات مقدمة من العملاء (هام)", "code": "212100", "type": schemas.AccountType.LIABILITY, "parent_code": "212000"},
    {"name": "ضريبة القيمة المضافة", "code": "212200", "type": schemas.AccountType.LIABILITY, "parent_code": "212000"},

    # ==================== 3. حقوق الملكية (300000) ====================
    {"name": "حقوق الملكية", "code": "300000", "type": schemas.AccountType.EQUITY, "parent_code": None},
    {"name": "رأس المال", "code": "310000", "type": schemas.AccountType.EQUITY, "parent_code": "300000"},
    {"name": "جاري المالك (مسحوبات)", "code": "320000", "type": schemas.AccountType.EQUITY, "parent_code": "300000"},
    {"name": "الأرباح المرحلة", "code": "330000", "type": schemas.AccountType.EQUITY, "parent_code": "300000"},

    # ==================== 4. الإيرادات (400000) ====================
    {"name": "الإيرادات", "code": "400000", "type": schemas.AccountType.REVENUE, "parent_code": None},
    {"name": "إيرادات التشغيل الرئيسية", "code": "410000", "type": schemas.AccountType.REVENUE, "parent_code": "400000"},
    {"name": "إيرادات خدمات التسويق الرقمي", "code": "410100", "type": schemas.AccountType.REVENUE, "parent_code": "410000"},
    {"name": "إيرادات تطوير المواقع والتطبيقات", "code": "410200", "type": schemas.AccountType.REVENUE, "parent_code": "410000"},
    {"name": "إيرادات الباقات والعقود السنوية", "code": "410300", "type": schemas.AccountType.REVENUE, "parent_code": "410000"},

    # ==================== 5. تكاليف الإيرادات - COGS (500000) ====================
    # ⚡ هذا القسم يخبرك كم كلفك المشروع تقنياً (Direct Costs)
    {"name": "تكاليف الإيرادات (المباشرة)", "code": "500000", "type": schemas.AccountType.EXPENSE, "parent_code": None},
    {"name": "تكاليف الحملات والتشغيل", "code": "510000", "type": schemas.AccountType.EXPENSE, "parent_code": "500000"},
    {"name": "ميزانية إعلانات (Ads Spend)", "code": "510001", "type": schemas.AccountType.EXPENSE, "parent_code": "510000"},
    {"name": "تكلفة استضافة وسيرفرات", "code": "510002", "type": schemas.AccountType.EXPENSE, "parent_code": "510000"},
    {"name": "أجور مستقلين (Outsourcing)", "code": "510003", "type": schemas.AccountType.EXPENSE, "parent_code": "510000"},

    # ==================== 6. المصروفات التشغيلية - OPEX (600000) ====================
    # ⚡ هذا القسم يخبرك كم كلفتك إدارة الشركة (Indirect Costs)
    {"name": "المصروفات التشغيلية والإدارية", "code": "600000", "type": schemas.AccountType.EXPENSE, "parent_code": None},
    {"name": "المصروفات التسويقية", "code": "610000", "type": schemas.AccountType.EXPENSE, "parent_code": "600000"},
    {"name": "دعاية وإعلان للشركة", "code": "610001", "type": schemas.AccountType.EXPENSE, "parent_code": "610000"},
    {"name": "عمولات البيع", "code": "610002", "type": schemas.AccountType.EXPENSE, "parent_code": "610000"},
    {"name": "المصروفات الإدارية والعمومية", "code": "620000", "type": schemas.AccountType.EXPENSE, "parent_code": "600000"},
    {"name": "رواتب الموظفين", "code": "620001", "type": schemas.AccountType.EXPENSE, "parent_code": "620000"},
    {"name": "إيجار ومرافق", "code": "620002", "type": schemas.AccountType.EXPENSE, "parent_code": "620000"},
    {"name": "إنترنت واتصالات", "code": "620003", "type": schemas.AccountType.EXPENSE, "parent_code": "620000"},
    {"name": "اشتراكات برمجيات (SaaS)", "code": "620004", "type": schemas.AccountType.EXPENSE, "parent_code": "620000"},
    {"name": "المصروفات المالية", "code": "630000", "type": schemas.AccountType.EXPENSE, "parent_code": "600000"},
    {"name": "رسوم بنكية وعمولات سحب", "code": "630001", "type": schemas.AccountType.EXPENSE, "parent_code": "630000"},
]


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

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تاب إدارة الحسابات (التاب الوحيد)
        self.setup_accounts_tab(main_layout)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_accounts_data() - يتم استدعاؤها عند فتح التاب

        # ربط الإشارات للتحديث التلقائي
        app_signals.data_changed.connect(self.on_data_changed)
        app_signals.accounts_changed.connect(self.load_accounts_data)
        app_signals.journal_entry_created.connect(self.on_journal_entry_created)

        # ✨ Connect to Global Events for Real-time Updates
        if EVENTS_AVAILABLE:
            events.data_changed.connect(self.on_data_changed)
            events.accounting_refresh.connect(self.load_accounts_data)
            print("INFO: ✅ تم ربط الأحداث العالمية - التحديث الفوري مفعّل!")

    def on_data_changed(self):
        """معالج التحديث الفوري عند تغيير البيانات"""
        print("INFO: ✅ تحديث فوري - إعادة تحميل البيانات...")
        self.load_accounts_data()

    def on_journal_entry_created(self, entry_id: str):
        """معالج إنشاء قيد محاسبي جديد"""
        print(f"INFO: ✅ تم إنشاء قيد محاسبي جديد: {entry_id} - تحديث الأرصدة...")
        self.load_accounts_data()

    def resizeEvent(self, event):
        """معالج تغيير حجم النافذة"""
        super().resizeEvent(event)
        # لا حاجة لإعادة ضبط الأعمدة - Stretch mode يتكفل بذلك

    # ==================== تاب إدارة الحسابات ====================
    def setup_accounts_tab(self, main_layout: QVBoxLayout):
        """إعداد واجهة إدارة الحسابات"""
        layout = main_layout  # استخدام الـ layout الرئيسي مباشرة

        # أزرار التحكم
        buttons_layout = QHBoxLayout()

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

        self.create_defaults_btn = QPushButton("⚙️ إنشاء الحسابات الافتراضية")
        self.create_defaults_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.create_defaults_btn.clicked.connect(self.create_default_accounts)

        self.fix_parents_btn = QPushButton("🔧 إصلاح الربط")
        self.fix_parents_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.fix_parents_btn.setToolTip("إصلاح ربط الحسابات بالآباء الصحيحين")
        self.fix_parents_btn.clicked.connect(self.fix_accounts_parents)

        self.recalc_balances_btn = QPushButton("🔄 إعادة حساب الأرصدة")
        self.recalc_balances_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.recalc_balances_btn.setToolTip("إعادة حساب جميع الأرصدة من القيود المحاسبية")
        self.recalc_balances_btn.clicked.connect(self.recalculate_all_balances)

        buttons_layout.addWidget(self.add_account_btn)
        buttons_layout.addWidget(self.edit_account_btn)
        buttons_layout.addWidget(self.delete_account_btn)
        buttons_layout.addWidget(self.refresh_btn)
        buttons_layout.addWidget(self.create_defaults_btn)
        buttons_layout.addWidget(self.fix_parents_btn)
        buttons_layout.addWidget(self.recalc_balances_btn)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # ✨ STEP 1: LAYOUT SPLIT - 75% Tree (Right), 25% Summary (Left)
        # Main Horizontal Layout with proper spacing
        main_h_layout = QHBoxLayout()
        main_h_layout.setSpacing(15)
        main_h_layout.setContentsMargins(0, 10, 0, 0)

        # --- RIGHT SIDE: TREE CONTAINER (75%) ---
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

        # --- LEFT SIDE: SUMMARY PANEL ---
        self.summary_panel = self.create_summary_panel()

        # --- ADD TO MAIN LAYOUT ---
        # الجدول ياخد 80% والملخص 20%
        main_h_layout.addWidget(self.summary_panel, 1)   # Stretch factor 1
        main_h_layout.addWidget(tree_container, 4)       # Stretch factor 4 (أكبر 4 مرات)

        layout.addLayout(main_h_layout)

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
        """⚡ تحميل الحسابات في الخلفية لمنع التجميد"""
        print("INFO: [AccManager] جاري تحميل شجرة الحسابات...")

        from PyQt6.QtWidgets import QApplication

        from core.data_loader import get_data_loader

        QApplication.processEvents()

        # دالة جلب البيانات
        def fetch_accounts():
            try:
                tree_map = self.accounting_service.get_hierarchy_with_balances()
                all_accounts = self.accounting_service.repo.get_all_accounts()
                return {'tree_map': tree_map, 'all_accounts': all_accounts}
            except Exception as e:
                print(f"ERROR: [AccManager] فشل جلب الحسابات: {e}")
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

                print(
                    f"INFO: [AccManager] ✅ تم تحميل {len(self.all_accounts_list)} حساب وتمت موازنة الشجرة."
                )
            except Exception as e:
                print(f"ERROR: [AccManager] فشل تحديث الشجرة: {e}")
                import traceback
                traceback.print_exc()

        def on_error(error_msg):
            print(f"ERROR: [AccManager] فشل تحميل الحسابات: {error_msg}")

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
                    item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                    item.setBackground(QColor(COLORS['bg_light']))
                    item.setForeground(QColor(COLORS['text_primary']))
            else:
                for item in row:
                    item.setFont(QFont("Segoe UI", 9))
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

        print(f"INFO: [AccManager] تم عرض {len(self.all_accounts_list)} حساب وضبط الأعمدة.")

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
                QMessageBox.information(self, "✅ تم", "تم حذف الحساب نهائياً.")
                self.load_accounts_data()
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل الحذف: {e}")

    def create_default_accounts(self):
        """
        🏢 إنشاء شجرة الحسابات Enterprise Level (6 أرقام)

        ✅ نظام 6 أرقام (Scalability) - يدعم 999 حساب فرعي تحت كل بند
        ✅ فصل COGS (5xxxxx) عن OPEX (6xxxxx) لتحليل الربحية
        ✅ دفعات مقدمة من العملاء (Unearned Revenue)
        """
        # التحقق من وجود حسابات قديمة (4 أرقام)
        try:
            self.all_accounts_list = self.accounting_service.repo.get_all_accounts()
        except (AttributeError, TypeError) as e:
            print(f"WARNING: [AccountingManager] فشل جلب الحسابات: {e}")
            self.all_accounts_list = []

        old_accounts = [acc for acc in self.all_accounts_list if acc.code and len(acc.code) <= 4]

        if old_accounts:
            # يوجد حسابات قديمة - اسأل المستخدم
            reply = QMessageBox.question(
                self, "🔄 ترقية شجرة الحسابات",
                f"⚠️ تم اكتشاف {len(old_accounts)} حساب بالنظام القديم (4 أرقام).\n\n"
                "🏢 النظام الجديد Enterprise Level (6 أرقام) يوفر:\n"
                "• فصل COGS عن OPEX لتحليل الربحية\n"
                "• دعم 999 حساب فرعي تحت كل بند\n"
                "• دفعات مقدمة من العملاء (Unearned Revenue)\n\n"
                "هل تريد:\n"
                "✅ نعم = حذف الحسابات القديمة وإنشاء الجديدة\n"
                "❌ لا = إضافة الحسابات الجديدة فقط (بدون حذف)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return

            reset_mode = (reply == QMessageBox.StandardButton.Yes)
        else:
            # لا يوجد حسابات قديمة - إنشاء مباشر
            reply = QMessageBox.question(
                self, "⚙️ إنشاء شجرة الحسابات Enterprise",
                "🏢 سيتم إنشاء شجرة الحسابات Enterprise Level (6 أرقام).\n\n"
                "تشمل:\n"
                "• الأصول (100000) - النقدية، العملاء، البنوك\n"
                "• الخصوم (200000) - الموردون، الضرائب، دفعات مقدمة\n"
                "• حقوق الملكية (300000)\n"
                "• الإيرادات (400000)\n"
                "• تكاليف الإيرادات COGS (500000)\n"
                "• المصروفات التشغيلية OPEX (600000)\n\n"
                "هل تريد المتابعة؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            reset_mode = False

        # إنشاء نافذة التقدم
        from PyQt6.QtWidgets import QProgressDialog
        progress = QProgressDialog("جاري إنشاء شجرة الحسابات Enterprise...", None, 0, 100, self)
        progress.setWindowTitle("🏢 شجرة الحسابات Enterprise")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setStyleSheet(f"""
            QProgressDialog {{
                background-color: {COLORS['bg_light']};
                color: {COLORS['text_primary']};
                border-radius: 10px;
            }}
            QProgressBar {{
                border: none;
                border-radius: 5px;
                background-color: {COLORS['bg_dark']};
                text-align: center;
                color: white;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['success']};
                border-radius: 5px;
            }}
            QLabel {{
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
        """)
        progress.setMinimumWidth(400)
        progress.show()

        created, skipped, errors, deleted = 0, 0, 0, 0

        try:
            if reset_mode:
                # حذف الحسابات القديمة أولاً
                progress.setLabelText("🗑️ جاري حذف الحسابات القديمة...")
                progress.setValue(20)

                result = self.accounting_service.reset_to_enterprise_accounts()

                progress.setValue(100)
                progress.close()

                # استخراج النتائج
                deleted = result.get("deleted", 0)
                created = result.get("created", 0)
                skipped = result.get("skipped", 0)
                errors = len(result.get("errors", []))
            else:
                # إضافة الحسابات الجديدة فقط
                progress.setLabelText("📊 جاري إنشاء الحسابات الجديدة...")
                progress.setValue(50)

                result = self.accounting_service.seed_default_accounts()

                progress.setValue(100)
                progress.close()

                # استخراج النتائج
                created = result.get("created", 0)
                skipped = result.get("skipped", 0)
                errors = len(result.get("errors", []))

        except Exception as e:
            progress.close()
            created, skipped, errors = 0, 0, 1
            print(f"ERROR: فشل إنشاء الحسابات: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل إنشاء الحسابات:\n{str(e)}"
            )
            return

        self.load_accounts_data()

        # رسالة النتيجة بتصميم جميل
        if created > 0 or skipped > 0 or deleted > 0:
            result_icon = "✅" if errors == 0 else "⚠️"
            result_title = "🏢 تم ترقية شجرة الحسابات بنجاح!" if errors == 0 else "تم مع بعض الأخطاء"

            msg = f"{result_icon} {result_title}\n\n"

            if deleted > 0:
                msg += f"�️ت تم حذف {deleted} حساب قديم (4 أرقام)\n"
            if created > 0:
                msg += f"📊 تم إنشاء {created} حساب جديد (6 أرقام)\n"
            if skipped > 0:
                msg += f"⏭️ تم تجاوز {skipped} حساب (موجود مسبقاً)\n"
            if errors > 0:
                msg += f"❌ فشل إنشاء {errors} حساب\n"

            # إعادة تحميل الحسابات للحصول على العدد الصحيح
            try:
                self.all_accounts_list = self.accounting_service.repo.get_all_accounts()
            except Exception:
                pass

            msg += f"\n📁 إجمالي الحسابات الآن: {len(self.all_accounts_list)}"
            msg += "\n\n✅ النظام الجديد يدعم:\n"
            msg += "• فصل COGS (5xxxxx) عن OPEX (6xxxxx)\n"
            msg += "• دفعات مقدمة من العملاء (212100)"

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("نتيجة إنشاء الحسابات")
            msg_box.setText(msg)
            msg_box.setIcon(QMessageBox.Icon.Information if errors == 0 else QMessageBox.Icon.Warning)
            msg_box.setStyleSheet(f"""
                QMessageBox {{
                    background-color: {COLORS['bg_light']};
                }}
                QMessageBox QLabel {{
                    color: {COLORS['text_primary']};
                    font-size: 13px;
                    min-width: 300px;
                }}
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 20px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #2563eb;
                }}
            """)
            msg_box.exec()
        else:
            QMessageBox.information(self, "معلومة", "جميع الحسابات الافتراضية موجودة بالفعل.")


    # ✨ STEP 1: Summary Panel Creation
    def create_summary_panel(self):
        """إنشاء لوحة الملخص المالي"""
        panel = QFrame()
        # ✨ عرض أصغر للـ summary panel عشان الجدول ياخد مساحة أكبر
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(250)
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_light']};
                border-left: 3px solid {COLORS['primary']};
                border-radius: 10px;
                padding: 8px;
                min-width: 200px;
            }}
        """)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(8)
        panel_layout.setContentsMargins(10, 10, 10, 10)

        # العنوان
        title = QLabel("📊 ملخص الوضع المالي")
        title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {COLORS['primary']};
            padding: 8px;
            background-color: {COLORS['bg_dark']};
            border-radius: 6px;
            border: 1px solid {COLORS['primary']};
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(title)

        # بطاقة الميزانية
        balance_sheet_card = QGroupBox("الميزانية (Balance Sheet)")
        balance_sheet_card.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                margin-top: 8px;
                padding: 8px;
                background-color: {COLORS['bg_dark']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 2px 6px;
                background-color: {COLORS['primary']};
                color: white;
                border-radius: 3px;
                font-size: 11px;
            }}
        """)
        balance_layout = QVBoxLayout()

        # الأصول
        self.assets_label = QLabel("💰 الأصول: 0.00 جنيه")
        self.assets_label.setStyleSheet(f"""
            color: {COLORS['success']};
            font-size: 12px;
            font-weight: bold;
            padding: 6px;
            background-color: rgba(16, 185, 129, 0.1);
            border-radius: 4px;
            border-left: 3px solid {COLORS['success']};
        """)
        self.assets_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        balance_layout.addWidget(self.assets_label)

        # الخصوم
        self.liabilities_label = QLabel("📉 الخصوم: 0.00 جنيه")
        self.liabilities_label.setStyleSheet(f"""
            color: {COLORS['danger']};
            font-size: 12px;
            font-weight: bold;
            padding: 6px;
            background-color: rgba(239, 68, 68, 0.1);
            border-radius: 4px;
            border-left: 3px solid {COLORS['danger']};
        """)
        self.liabilities_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        balance_layout.addWidget(self.liabilities_label)

        # حقوق الملكية
        self.equity_label = QLabel("🏦 حقوق الملكية: 0.00 جنيه")
        self.equity_label.setStyleSheet(f"""
            color: {COLORS['primary']};
            font-size: 12px;
            font-weight: bold;
            padding: 6px;
            background-color: rgba(59, 130, 246, 0.1);
            border-radius: 4px;
            border-left: 3px solid {COLORS['primary']};
        """)
        self.equity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        balance_layout.addWidget(self.equity_label)

        balance_sheet_card.setLayout(balance_layout)
        panel_layout.addWidget(balance_sheet_card)

        # بطاقة الأرباح والخسائر
        pl_card = QGroupBox("الأرباح والخسائر (P&L)")
        pl_card.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                margin-top: 8px;
                padding: 8px;
                background-color: {COLORS['bg_dark']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 2px 6px;
                background-color: {COLORS['warning']};
                color: white;
                border-radius: 3px;
                font-size: 11px;
            }}
        """)
        pl_layout = QVBoxLayout()

        # الإيرادات
        self.revenue_summary_label = QLabel("📈 الإيرادات: 0.00 جنيه")
        self.revenue_summary_label.setStyleSheet(f"""
            color: {COLORS['success']};
            font-size: 12px;
            font-weight: bold;
            padding: 6px;
            background-color: rgba(16, 185, 129, 0.1);
            border-radius: 4px;
            border-left: 3px solid {COLORS['success']};
        """)
        self.revenue_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl_layout.addWidget(self.revenue_summary_label)

        # المصروفات
        self.expenses_summary_label = QLabel("📊 المصروفات: 0.00 جنيه")
        self.expenses_summary_label.setStyleSheet(f"""
            color: {COLORS['danger']};
            font-size: 12px;
            font-weight: bold;
            padding: 6px;
            background-color: rgba(239, 68, 68, 0.1);
            border-radius: 4px;
            border-left: 3px solid {COLORS['danger']};
        """)
        self.expenses_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl_layout.addWidget(self.expenses_summary_label)

        # خط فاصل
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {COLORS['border']}; max-height: 1px;")
        pl_layout.addWidget(separator)

        # صافي الربح
        self.net_profit_summary_label = QLabel("💎 صافي الربح: 0.00 جنيه")
        self.net_profit_summary_label.setStyleSheet(f"""
            color: {COLORS['success']};
            font-size: 13px;
            font-weight: bold;
            padding: 8px;
            background-color: rgba(16, 185, 129, 0.1);
            border-radius: 6px;
            border: 1px solid {COLORS['success']};
        """)
        self.net_profit_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl_layout.addWidget(self.net_profit_summary_label)

        pl_card.setLayout(pl_layout)
        panel_layout.addWidget(pl_card)

        # مساحة فارغة في الأسفل
        panel_layout.addStretch()

        # زر تحديث الملخص
        refresh_summary_btn = QPushButton("🔄 تحديث الملخص")
        refresh_summary_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['info']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['secondary']};
            }}
        """)
        refresh_summary_btn.clicked.connect(self.update_summary_labels)
        panel_layout.addWidget(refresh_summary_btn)

        return panel

    def update_summary_labels(self, tree_map: dict | None = None):
        """
        ✨ تحديث إحصائيات الملخص المالي باستخدام الأرصدة المحسوبة تراكمياً

        Args:
            tree_map: قاموس الشجرة مع الأرصدة المحسوبة (من get_hierarchy_with_balances)
        """
        print("INFO: [AccManager] جاري تحديث الملخص المالي...")
        try:
            # إذا لم يتم تمرير tree_map أو كان فارغاً، نجلبه من الخدمة
            if not tree_map or not isinstance(tree_map, dict) or len(tree_map) == 0:
                print("DEBUG: [Summary] tree_map فارغ - جلب البيانات من الخدمة...")
                tree_map = self.accounting_service.get_hierarchy_with_balances()

            # استخراج الأرصدة من الحسابات الرئيسية (يدعم نظام 4 و 6 أرقام)
            # نظام 6 أرقام (Enterprise)
            total_assets = tree_map.get('100000', {}).get('total', 0.0) or tree_map.get('1000', {}).get('total', 0.0)
            total_liabilities = tree_map.get('200000', {}).get('total', 0.0) or tree_map.get('2000', {}).get('total', 0.0)
            total_equity = tree_map.get('300000', {}).get('total', 0.0) or tree_map.get('3000', {}).get('total', 0.0)
            total_revenue = tree_map.get('400000', {}).get('total', 0.0) or tree_map.get('4000', {}).get('total', 0.0)
            # COGS (500000) + OPEX (600000) = إجمالي المصروفات
            total_cogs = tree_map.get('500000', {}).get('total', 0.0)
            total_opex = tree_map.get('600000', {}).get('total', 0.0)
            total_expenses = total_cogs + total_opex or tree_map.get('5000', {}).get('total', 0.0)

            print(f"DEBUG: [Summary] أصول:{total_assets}, خصوم:{total_liabilities}, إيرادات:{total_revenue}, مصروفات:{total_expenses}")

            # حساب صافي الربح = الإيرادات - المصروفات
            net_profit = total_revenue - total_expenses

            # تحديث Labels
            self.assets_label.setText(f"💰 الأصول: {total_assets:,.2f} جنيه")
            self.liabilities_label.setText(f"📉 الخصوم: {total_liabilities:,.2f} جنيه")
            self.equity_label.setText(f"🏦 حقوق الملكية: {total_equity:,.2f} جنيه")
            self.revenue_summary_label.setText(f"📈 الإيرادات: {total_revenue:,.2f} جنيه")
            self.expenses_summary_label.setText(f"📊 المصروفات: {total_expenses:,.2f} جنيه")

            # تحديث صافي الربح مع تغيير اللون حسب القيمة
            if net_profit >= 0:
                self.net_profit_summary_label.setText(f"💎 صافي الربح: {net_profit:,.2f} جنيه")
                self.net_profit_summary_label.setStyleSheet(f"""
                    color: {COLORS['success']};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 8px;
                    background-color: rgba(16, 185, 129, 0.1);
                    border-radius: 6px;
                    border: 1px solid {COLORS['success']};
                """)
            else:
                self.net_profit_summary_label.setText(f"💔 صافي الخسارة: {abs(net_profit):,.2f} جنيه")
                self.net_profit_summary_label.setStyleSheet(f"""
                    color: {COLORS['danger']};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 8px;
                    background-color: rgba(239, 68, 68, 0.1);
                    border-radius: 6px;
                    border: 1px solid {COLORS['danger']};
                """)

            print("INFO: [AccManager] الملخص المالي:")
            print(f"  - الأصول: {total_assets:,.2f}")
            print(f"  - الخصوم: {total_liabilities:,.2f}")
            print(f"  - الإيرادات: {total_revenue:,.2f}")
            print(f"  - المصروفات: {total_expenses:,.2f}")
            print(f"  - صافي الربح: {net_profit:,.2f}")

        except Exception as e:
            print(f"ERROR: [AccManager] فشل تحديث الملخص المالي: {e}")
            import traceback
            traceback.print_exc()

    def fix_accounts_parents(self):
        """إصلاح ربط الحسابات بالآباء الصحيحين"""
        reply = QMessageBox.question(
            self, "🔧 إصلاح ربط الحسابات",
            "سيتم إصلاح ربط جميع الحسابات بالآباء الصحيحين.\n\n"
            "هذا سيضمن أن:\n"
            "• الحسابات الفرعية مرتبطة بالمجموعات الصحيحة\n"
            "• شجرة الحسابات تعمل بشكل صحيح\n"
            "• الأرصدة التراكمية تُحسب بشكل صحيح\n\n"
            "هل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        try:
            # استدعاء دالة الإصلاح من الخدمة
            result = self.accounting_service.fix_accounts_parent_codes()

            # إعادة تحميل البيانات
            self.load_accounts_data()

            # عرض النتيجة
            if result.get('success'):
                QMessageBox.information(
                    self,
                    "✅ تم الإصلاح",
                    f"تم إصلاح ربط الحسابات بنجاح!\n\n"
                    f"📊 تم تحديث: {result.get('updated', 0)} حساب\n"
                    f"⏭️ تم تخطي: {result.get('skipped', 0)} حساب (صحيح بالفعل)"
                )
            else:
                QMessageBox.warning(
                    self,
                    "⚠️ تم مع أخطاء",
                    f"تم الإصلاح مع بعض الأخطاء:\n\n"
                    f"📊 تم تحديث: {result.get('updated', 0)} حساب\n"
                    f"❌ أخطاء: {len(result.get('errors', []))}"
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ خطأ",
                f"فشل إصلاح الحسابات:\n\n{str(e)}"
            )

    def recalculate_all_balances(self):
        """إعادة حساب جميع الأرصدة من القيود المحاسبية"""
        reply = QMessageBox.question(
            self, "🔄 إعادة حساب الأرصدة",
            "سيتم إعادة حساب جميع أرصدة الحسابات من القيود المحاسبية.\n\n"
            "هذا مفيد في حالة:\n"
            "• عدم تطابق الأرصدة مع القيود\n"
            "• ظهور أرصدة صفرية بشكل خاطئ\n"
            "• بعد استيراد بيانات جديدة\n\n"
            "هل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        try:
            # استدعاء دالة إعادة الحساب من الخدمة
            success = self.accounting_service.recalculate_all_balances()

            # إعادة تحميل البيانات
            self.load_accounts_data()

            # عرض النتيجة
            if success:
                QMessageBox.information(
                    self,
                    "✅ تم بنجاح",
                    "تم إعادة حساب جميع الأرصدة من القيود المحاسبية بنجاح!\n\n"
                    "الأرصدة الآن تعكس القيود الفعلية."
                )
            else:
                QMessageBox.warning(
                    self,
                    "⚠️ تحذير",
                    "حدثت مشكلة أثناء إعادة حساب الأرصدة.\n"
                    "راجع سجل الأخطاء للمزيد من التفاصيل."
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ خطأ",
                f"فشل إعادة حساب الأرصدة:\n\n{str(e)}"
            )

    # ✨ STEP 3: ENABLE LEDGER - Ledger Window Method
    def open_ledger_window(self, index):
        """فتح نافذة كشف الحساب عند النقر المزدوج"""
        print("INFO: [AccountingManager] تم النقر المزدوج على الحساب")

        # الحصول على العنصر من الفهرس
        item = self.accounts_model.itemFromIndex(index)
        if not item:
            print("WARNING: [AccountingManager] لم يتم العثور على العنصر")
            return

        # الحصول على الحساب من البيانات المخزنة
        account = item.data(Qt.ItemDataRole.UserRole)
        if not account:
            print("WARNING: [AccountingManager] لم يتم العثور على بيانات الحساب")
            return

        print(f"INFO: [AccountingManager] فتح كشف حساب: {account.name} ({account.code})")

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

            print("INFO: [AccountingManager] إنشاء نافذة كشف الحساب...")
            ledger_window = LedgerWindow(
                account=account,
                accounting_service=self.accounting_service,
                parent=self
            )

            print("INFO: [AccountingManager] عرض نافذة كشف الحساب...")
            ledger_window.exec()

        except ImportError as e:
            print(f"ERROR: [AccountingManager] فشل استيراد LedgerWindow: {e}")
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل تحميل نافذة كشف الحساب.\n\n"
                f"الملف ui/ledger_window.py غير موجود أو به خطأ.\n\n"
                f"الخطأ: {str(e)}"
            )
        except Exception as e:
            print(f"ERROR: [AccountingManager] فشل فتح كشف الحساب: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل فتح كشف الحساب:\n\n{str(e)}"
            )
