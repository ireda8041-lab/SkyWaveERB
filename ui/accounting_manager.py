# الملف: ui/accounting_manager.py
"""
تاب المحاسبة - إدارة الحسابات بشكل شجري
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QHeaderView, QPushButton, QLabel, QMessageBox, QGroupBox,
    QTreeView, QDialog, QFrame, QSizePolicy
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont
from PyQt6.QtCore import Qt

from services.expense_service import ExpenseService
from services.accounting_service import AccountingService
from services.project_service import ProjectService
from core import schemas
from typing import List, Optional, Dict

from ui.account_editor_dialog import AccountEditorDialog
from ui.styles import BUTTON_STYLES, TREE_STYLE_DARK, COLORS, CHART_OF_ACCOUNTS_TREE_STYLE
from core.signals import app_signals

# ✨ Import Global Events for Real-time Updates
try:
    from shared.events import events
    EVENTS_AVAILABLE = True
except ImportError:
    EVENTS_AVAILABLE = False
    print("WARNING: Global events not available")


# قوالب الحسابات الافتراضية - شجرة الحسابات الكاملة
DEFAULT_ACCOUNT_TEMPLATES = [
    # ==================== الأصول (1000) ====================
    {"name": "الأصول", "code": "1000", "type": schemas.AccountType.ASSET, "parent_code": None},
    {"name": "الأصول المتداولة", "code": "1100", "type": schemas.AccountType.ASSET, "parent_code": "1000"},
    {"name": "النقدية والخزائن", "code": "1110", "type": schemas.AccountType.CASH, "parent_code": "1100"},
    {"name": "الخزنة الرئيسية", "code": "1111", "type": schemas.AccountType.CASH, "parent_code": "1110"},
    {"name": "البنوك", "code": "1120", "type": schemas.AccountType.CASH, "parent_code": "1100"},
    {"name": "البنك الأهلي", "code": "1121", "type": schemas.AccountType.CASH, "parent_code": "1120"},
    {"name": "المحافظ الإلكترونية", "code": "1130", "type": schemas.AccountType.CASH, "parent_code": "1100"},
    {"name": "فودافون كاش", "code": "1131", "type": schemas.AccountType.CASH, "parent_code": "1130"},
    {"name": "العملاء", "code": "1140", "type": schemas.AccountType.ASSET, "parent_code": "1100"},
    
    # ==================== الخصوم (2000) ====================
    {"name": "الخصوم", "code": "2000", "type": schemas.AccountType.LIABILITY, "parent_code": None},
    {"name": "ضريبة القيمة المضافة", "code": "2100", "type": schemas.AccountType.LIABILITY, "parent_code": "2000"},
    {"name": "الموردون", "code": "2200", "type": schemas.AccountType.LIABILITY, "parent_code": "2000"},
    
    # ==================== حقوق الملكية (3000) ====================
    {"name": "حقوق الملكية", "code": "3000", "type": schemas.AccountType.EQUITY, "parent_code": None},
    {"name": "رأس المال", "code": "3100", "type": schemas.AccountType.EQUITY, "parent_code": "3000"},
    {"name": "الأرباح المحتجزة", "code": "3200", "type": schemas.AccountType.EQUITY, "parent_code": "3000"},
    
    # ==================== الإيرادات (4000) ====================
    {"name": "الإيرادات", "code": "4000", "type": schemas.AccountType.REVENUE, "parent_code": None},
    {"name": "إيرادات الخدمات", "code": "4100", "type": schemas.AccountType.REVENUE, "parent_code": "4000"},
    {"name": "إيرادات المشاريع", "code": "4110", "type": schemas.AccountType.REVENUE, "parent_code": "4100"},
    {"name": "إيرادات الاستشارات", "code": "4120", "type": schemas.AccountType.REVENUE, "parent_code": "4100"},
    {"name": "الخصومات المسموحة", "code": "4200", "type": schemas.AccountType.REVENUE, "parent_code": "4000"},
    
    # ==================== المصروفات (5000) ====================
    {"name": "المصروفات", "code": "5000", "type": schemas.AccountType.EXPENSE, "parent_code": None},
    {"name": "المصروفات التشغيلية", "code": "5100", "type": schemas.AccountType.EXPENSE, "parent_code": "5000"},
    {"name": "الرواتب والأجور", "code": "5110", "type": schemas.AccountType.EXPENSE, "parent_code": "5100"},
    {"name": "مصروفات الإعلانات", "code": "5120", "type": schemas.AccountType.EXPENSE, "parent_code": "5100"},
    {"name": "مصروفات إدارية", "code": "5130", "type": schemas.AccountType.EXPENSE, "parent_code": "5100"},
    {"name": "مصروفات الإيجار", "code": "5140", "type": schemas.AccountType.EXPENSE, "parent_code": "5100"},
    {"name": "مصروفات المرافق", "code": "5150", "type": schemas.AccountType.EXPENSE, "parent_code": "5100"},
    {"name": "مصروفات الاشتراكات", "code": "5160", "type": schemas.AccountType.EXPENSE, "parent_code": "5100"},
    {"name": "مصروفات متنوعة", "code": "5900", "type": schemas.AccountType.EXPENSE, "parent_code": "5000"},
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
        self.all_accounts_list: List[schemas.Account] = []

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

        buttons_layout.addWidget(self.add_account_btn)
        buttons_layout.addWidget(self.edit_account_btn)
        buttons_layout.addWidget(self.delete_account_btn)
        buttons_layout.addWidget(self.refresh_btn)
        buttons_layout.addWidget(self.create_defaults_btn)
        buttons_layout.addWidget(self.fix_parents_btn)
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
        
        # ✅ إعداد الأعمدة بشكل صحيح
        header = self.accounts_tree.header()
        header.setMinimumHeight(40)
        header.setDefaultSectionSize(100)
        header.setStretchLastSection(False)
        
        # ✅ ضبط أوضاع الأعمدة
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)      # الكود
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)    # اسم الحساب - يتمدد
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)      # النوع
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)      # العملة
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)      # الرصيد
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)      # الحالة
        
        # ✅ تحديد عرض الأعمدة
        self.accounts_tree.setColumnWidth(0, 50)      # الكود
        self.accounts_tree.setColumnWidth(2, 80)      # النوع
        self.accounts_tree.setColumnWidth(3, 45)      # العملة
        self.accounts_tree.setColumnWidth(4, 90)      # الرصيد
        self.accounts_tree.setColumnWidth(5, 50)      # الحالة
        
        # ✨ STEP 3: ENABLE LEDGER - Double Click for Ledger Window
        self.accounts_tree.doubleClicked.connect(self.open_ledger_window)
        
        tree_layout.addWidget(self.accounts_tree)

        # --- LEFT SIDE: SUMMARY PANEL (25%) ---
        self.summary_panel = self.create_summary_panel()

        # --- ADD TO MAIN LAYOUT ---
        # في واجهة RTL: الجدول على اليمين، الملخص على اليسار
        main_h_layout.addWidget(self.summary_panel, 0)  # Stretch factor 0 - حجم ثابت
        main_h_layout.addWidget(tree_container, 1)      # Stretch factor 1 - يأخذ باقي المساحة

        layout.addLayout(main_h_layout)

    def _setup_tree_columns(self):
        """ضبط أعمدة الشجرة - يتم استدعاؤها عند تغيير حجم النافذة"""
        # الأعمدة تم ضبطها في setup_accounts_tab
        pass
    
    def load_accounts_data(self):
        """
        تحميل الحسابات في شكل شجري متداخل مع حساب الأرصدة التراكمية
        
        يستخدم get_hierarchy_with_balances() لحساب أرصدة المجموعات
        عن طريق جمع أرصدة الحسابات الفرعية بشكل تكراري
        """
        print("INFO: [AccManager] جاري تحميل شجرة الحسابات مع الأرصدة التراكمية...")
        
        # ⚡ منع التجميد - معالجة الأحداث
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            # ✨ استخدام الدالة الجديدة للحصول على الأرصدة المحسوبة
            tree_map = self.accounting_service.get_hierarchy_with_balances()
            
            # تحديث قائمة الحسابات للاستخدام في أماكن أخرى
            self.all_accounts_list = self.accounting_service.repo.get_all_accounts()
            
            self.accounts_model.clear()
            self.accounts_model.setHorizontalHeaderLabels([
                "الكود", "اسم الحساب", "النوع", "العملة", "الرصيد", "الحالة"
            ])

            root = self.accounts_model.invisibleRootItem()
            
            # دالة تكرارية لعرض العقد
            def render_node(node: dict, parent_item):
                """عرض عقدة وأبنائها بشكل تكراري"""
                acc = node['obj']
                calculated_balance = node['total']  # الرصيد المحسوب (تراكمي للمجموعات)
                is_group = bool(node['children'])  # مجموعة إذا كان لها أبناء
                
                # إنشاء عناصر الصف
                code_item = QStandardItem(acc.code or "")
                code_item.setEditable(False)
                code_item.setData(acc, Qt.ItemDataRole.UserRole)  # تخزين الحساب في عمود الكود
                code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                
                name_item = QStandardItem(f"{'📁 ' if is_group else '📄 '}{acc.name}")
                name_item.setEditable(False)
                name_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                # ✅ عرض النوع بشكل واضح ومقروء
                type_display = {
                    'ASSET': 'أصول',
                    'CASH': 'أصول نقدية',
                    'LIABILITY': 'خصوم',
                    'EQUITY': 'حقوق ملكية',
                    'REVENUE': 'إيرادات',
                    'EXPENSE': 'مصروفات',
                    'أصول': 'أصول',
                    'أصول نقدية': 'أصول نقدية',
                    'خصوم': 'خصوم',
                    'حقوق ملكية': 'حقوق ملكية',
                    'إيرادات': 'إيرادات',
                    'مصروفات': 'مصروفات'
                }
                type_text = type_display.get(acc.type.value if acc.type else acc.type, acc.type.value if acc.type else "")
                type_item = QStandardItem(type_text)
                type_item.setEditable(False)
                type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                
                currency = acc.currency.value if acc.currency else "EGP"
                currency_item = QStandardItem(currency)
                currency_item.setEditable(False)
                currency_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                
                # ✨ استخدام الرصيد المحسوب (التراكمي للمجموعات) مع تنسيق واضح
                balance_text = f"{abs(calculated_balance):,.2f}"
                balance_item = QStandardItem(balance_text)
                balance_item.setEditable(False)
                balance_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                
                status_text = "✅ نشط" if acc.status == schemas.AccountStatus.ACTIVE else "❌ مؤرشف"
                status_item = QStandardItem(status_text)
                status_item.setEditable(False)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                
                row = [code_item, name_item, type_item, currency_item, balance_item, status_item]
                
                # تطبيق التنسيق حسب النوع (مجموعة أم حساب فرعي)
                if is_group:
                    # حساب مجموعة - خط عريض، خلفية داكنة (ألوان SkyWave Brand)
                    for item in row:
                        item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                        item.setBackground(QColor(COLORS['bg_light']))
                        item.setForeground(QColor(COLORS['text_primary']))
                else:
                    # حساب فرعي - خط عادي (ألوان SkyWave Brand)
                    for item in row:
                        item.setFont(QFont("Segoe UI", 9))
                        item.setBackground(QColor(COLORS['bg_medium']))
                        item.setForeground(QColor(COLORS['text_secondary']))
                
                # ✨ تلوين الرصيد حسب القيمة - ألوان واضحة
                if calculated_balance < 0:
                    balance_item.setForeground(QColor("#ff6b6b"))  # أحمر فاتح للسالب
                elif calculated_balance > 0:
                    balance_item.setForeground(QColor("#51cf66"))  # أخضر فاتح للموجب
                else:
                    balance_item.setForeground(QColor("#adb5bd"))  # رمادي فاتح للصفر
                
                # إضافة الصف للأب
                parent_item.appendRow(row)
                
                # ترتيب الأبناء حسب الكود ثم عرضهم
                sorted_children = sorted(node['children'], key=lambda x: str(x['obj'].code or ""))
                for child in sorted_children:
                    render_node(child, code_item)
            
            # تحديد الجذور (الحسابات بدون أب)
            roots = []
            for code, node in tree_map.items():
                acc = node['obj']
                # استخدام parent_id أو parent_code
                parent = getattr(acc, 'parent_id', None) or getattr(acc, 'parent_code', None)
                if not parent:
                    roots.append(node)
            
            # ترتيب الجذور حسب الكود
            roots.sort(key=lambda x: str(x['obj'].code or ""))
            
            # عرض الشجرة من الجذور
            for root_node in roots:
                render_node(root_node, root)

            # توسيع جميع المجموعات
            self.accounts_tree.expandAll()
            
            print(f"INFO: [AccManager] تم عرض {len(self.all_accounts_list)} حساب مع الأرصدة التراكمية.")
            print(f"DEBUG: [AccManager] tree_map keys: {list(tree_map.keys())[:10]}")
            
            # ✨ تحديث لوحة الملخص باستخدام الأرصدة المحسوبة
            self.update_summary_labels(tree_map)
            
        except Exception as e:
            print(f"ERROR: [AccManager] فشل تحميل الحسابات: {e}")
            import traceback
            traceback.print_exc()
    
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

    def get_selected_account(self) -> Optional[schemas.Account]:
        """الحصول على الحساب المحدد"""
        indexes = self.accounts_tree.selectedIndexes()
        if not indexes:
            return None
        item = self.accounts_model.itemFromIndex(indexes[0])
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
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
            self, "تأكيد الحذف",
            f"هل أنت متأكد من أرشفة الحساب:\n{selected.name}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                account_id = selected._mongo_id or str(selected.id)
                self.accounting_service.delete_account(account_id)
                QMessageBox.information(self, "تم", "تم أرشفة الحساب بنجاح.")
                self.load_accounts_data()
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل الأرشفة: {e}")

    def create_default_accounts(self):
        """إنشاء الحسابات الافتراضية مع نافذة تقدم جميلة"""
        reply = QMessageBox.question(
            self, "⚙️ إنشاء الحسابات الافتراضية",
            "سيتم إنشاء شجرة الحسابات الافتراضية للنظام المحاسبي.\n\n"
            "تشمل:\n"
            "• حسابات الأصول (النقدية، العملاء، البنوك)\n"
            "• حسابات الخصوم (الموردون، الضرائب)\n"
            "• حسابات حقوق الملكية\n"
            "• حسابات الإيرادات\n"
            "• حسابات المصروفات\n\n"
            "هل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        # إنشاء نافذة التقدم
        from PyQt6.QtWidgets import QProgressDialog
        progress = QProgressDialog("جاري إنشاء الحسابات الافتراضية...", None, 0, len(DEFAULT_ACCOUNT_TEMPLATES), self)
        progress.setWindowTitle("⚙️ إنشاء الحسابات")
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

        # إعادة تحميل الحسابات للتأكد من القائمة محدثة
        try:
            self.all_accounts_list = self.accounting_service.repo.get_all_accounts()
        except (AttributeError, TypeError) as e:
            print(f"WARNING: [AccountingManager] فشل جلب الحسابات: {e}")
            self.all_accounts_list = []

        created, skipped, errors = 0, 0, 0
        existing_codes = {acc.code for acc in self.all_accounts_list}
        
        print(f"INFO: [AccManager] بدء إنشاء الحسابات الافتراضية...")
        print(f"INFO: [AccManager] الحسابات الموجودة: {len(existing_codes)}")
        
        # إنشاء قاموس للحسابات المنشأة للربط بالـ parent
        created_accounts = {}
        
        # ✨ STEP 2: Use Smart Seeding from Service (4-Level Hierarchy)
        try:
            progress.setLabelText("استخدام البذر الذكي من الخدمة...")
            progress.setValue(50)
            
            # استخدام دالة البذر الذكية من الخدمة
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
            print(f"ERROR: فشل استخدام البذر الذكي: {e}")
            # Fallback to old method if service fails
            QMessageBox.critical(
                self,
                "خطأ",
                f"فشل إنشاء الحسابات الافتراضية:\n{str(e)}"
            )
            return
                
        self.load_accounts_data()
        
        # رسالة النتيجة بتصميم جميل
        if created > 0 or skipped > 0:
            result_icon = "✅" if errors == 0 else "⚠️"
            result_title = "تم بنجاح" if errors == 0 else "تم مع بعض الأخطاء"
            
            msg = f"{result_icon} {result_title}\n\n"
            
            if created > 0:
                msg += f"📊 تم إنشاء {created} حساب جديد\n"
            if skipped > 0:
                msg += f"⏭️ تم تجاوز {skipped} حساب (موجود مسبقاً)\n"
            if errors > 0:
                msg += f"❌ فشل إنشاء {errors} حساب\n"
            
            msg += f"\n📁 إجمالي الحسابات الآن: {len(self.all_accounts_list) + created}"
            
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
        # ✨ FORCE MINIMUM WIDTH for visibility
        panel.setMinimumWidth(250)
        panel.setMaximumWidth(320)
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_light']};
                border-left: 3px solid {COLORS['primary']};
                border-radius: 10px;
                padding: 10px;
                min-width: 250px;
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

    def update_summary_labels(self, tree_map: Dict = None):
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
            
            # استخراج الأرصدة من الحسابات الرئيسية (الجذور)
            total_assets = tree_map.get('1000', {}).get('total', 0.0)
            total_liabilities = tree_map.get('2000', {}).get('total', 0.0)
            total_equity = tree_map.get('3000', {}).get('total', 0.0)
            total_revenue = tree_map.get('4000', {}).get('total', 0.0)
            total_expenses = tree_map.get('5000', {}).get('total', 0.0)
            
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
            
            print(f"INFO: [AccManager] الملخص المالي:")
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

    # ✨ STEP 3: ENABLE LEDGER - Ledger Window Method
    def open_ledger_window(self, index):
        """فتح نافذة كشف الحساب عند النقر المزدوج"""
        print(f"INFO: [AccountingManager] تم النقر المزدوج على الحساب")
        
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
            
            print(f"INFO: [AccountingManager] إنشاء نافذة كشف الحساب...")
            ledger_window = LedgerWindow(
                account=account,
                accounting_service=self.accounting_service,
                parent=self
            )
            
            print(f"INFO: [AccountingManager] عرض نافذة كشف الحساب...")
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
