# الملف: ui/user_permissions_dialog.py
"""
نافذة تحرير صلاحيات المستخدم المخصصة
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QCheckBox, QGroupBox, QScrollArea, QWidget,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.auth_models import PermissionManager, UserRole
from ui.styles import BUTTON_STYLES, COLORS


class UserPermissionsDialog(QDialog):
    """نافذة تحرير صلاحيات المستخدم"""
    
    def __init__(self, user, repository, parent=None):
        super().__init__(parent)
        self.user = user
        self.repository = repository
        self.permissions = {}
        
        self.setWindowTitle(f"صلاحيات المستخدم: {user.username}")
        self.setModal(True)
        self.resize(600, 700)
        
        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)
        
        self.init_ui()
        self.load_current_permissions()
    
    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # معلومات المستخدم
        user_info = QLabel(f"👤 المستخدم: {self.user.full_name or self.user.username}")
        user_info.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        user_info.setStyleSheet(f"color: {COLORS['primary']}; padding: 10px;")
        layout.addWidget(user_info)
        
        role_display = self.user.role.value if hasattr(self.user.role, 'value') else str(self.user.role)
        role_info = QLabel(f"🎭 الدور: {role_display}")
        role_info.setStyleSheet(f"color: {COLORS['text_secondary']}; padding: 5px 10px;")
        layout.addWidget(role_info)
        
        # فاصل
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(separator)
        
        # منطقة التمرير
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # مجموعة التابات
        self.setup_tabs_group(scroll_layout)
        
        # مجموعة الإجراءات
        self.setup_actions_group(scroll_layout)
        
        # مجموعة الميزات
        self.setup_features_group(scroll_layout)
        
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        # أزرار التحكم
        buttons_layout = QHBoxLayout()
        
        # زر إعادة تعيين للافتراضي
        self.reset_btn = QPushButton("🔄 إعادة للافتراضي")
        self.reset_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.reset_btn.clicked.connect(self.reset_to_default)
        buttons_layout.addWidget(self.reset_btn)
        
        buttons_layout.addStretch()
        
        # زر الإلغاء
        self.cancel_btn = QPushButton("❌ إلغاء")
        self.cancel_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)
        
        # زر الحفظ
        self.save_btn = QPushButton("💾 حفظ الصلاحيات")
        self.save_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.save_btn.clicked.connect(self.save_permissions)
        buttons_layout.addWidget(self.save_btn)
        
        layout.addLayout(buttons_layout)
    
    def setup_tabs_group(self, layout):
        """إعداد مجموعة التابات"""
        tabs_group = QGroupBox("📑 التابات المسموحة")
        tabs_layout = QVBoxLayout()
        
        self.tab_checkboxes = {}
        tab_names = {
            'dashboard': '🏠 الصفحة الرئيسية',
            'projects': '🚀 المشاريع',
            'quotes': '📝 عروض الأسعار',
            'expenses': '💳 المصروفات',
            'payments': '💰 الدفعات',
            'clients': '👤 العملاء',
            'services': '🛠️ الخدمات والباقات',
            'accounting': '📊 المحاسبة',
            'settings': '🔧 الإعدادات'
        }
        
        for tab_key, tab_display in tab_names.items():
            checkbox = QCheckBox(tab_display)
            checkbox.setStyleSheet(f"color: {COLORS['text_primary']}; padding: 5px;")
            self.tab_checkboxes[tab_key] = checkbox
            tabs_layout.addWidget(checkbox)
        
        tabs_group.setLayout(tabs_layout)
        layout.addWidget(tabs_group)
    
    def setup_actions_group(self, layout):
        """إعداد مجموعة الإجراءات"""
        actions_group = QGroupBox("⚡ الإجراءات المسموحة")
        actions_layout = QVBoxLayout()
        
        self.action_checkboxes = {}
        action_names = {
            'create': '➕ إنشاء',
            'read': '👁️ عرض',
            'update': '✏️ تعديل',
            'delete': '🗑️ حذف',
            'export': '📤 تصدير',
            'print': '🖨️ طباعة'
        }
        
        for action_key, action_display in action_names.items():
            checkbox = QCheckBox(action_display)
            checkbox.setStyleSheet(f"color: {COLORS['text_primary']}; padding: 5px;")
            self.action_checkboxes[action_key] = checkbox
            actions_layout.addWidget(checkbox)
        
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
    
    def setup_features_group(self, layout):
        """إعداد مجموعة الميزات"""
        features_group = QGroupBox("🎯 الميزات الخاصة")
        features_layout = QVBoxLayout()
        
        self.feature_checkboxes = {}
        feature_names = {
            'user_management': '👥 إدارة المستخدمين',
            'system_settings': '⚙️ إعدادات النظام',
            'financial_reports': '📊 التقارير المالية',
            'data_export': '💾 تصدير البيانات',
            'client_reports': '👤 تقارير العملاء'
        }
        
        for feature_key, feature_display in feature_names.items():
            checkbox = QCheckBox(feature_display)
            checkbox.setStyleSheet(f"color: {COLORS['text_primary']}; padding: 5px;")
            self.feature_checkboxes[feature_key] = checkbox
            features_layout.addWidget(checkbox)
        
        features_group.setLayout(features_layout)
        layout.addWidget(features_group)
    
    def load_current_permissions(self):
        """تحميل الصلاحيات الحالية للمستخدم"""
        # إذا كان المستخدم مدير، حدد كل شيء
        user_role_str = str(self.user.role).lower()
        if (self.user.role == UserRole.ADMIN or 
            user_role_str == "admin" or 
            user_role_str == "userrole.admin" or
            (hasattr(self.user.role, 'value') and self.user.role.value == "admin")):
            # المدير له صلاحية كاملة
            for checkbox in self.tab_checkboxes.values():
                checkbox.setChecked(True)
            for checkbox in self.action_checkboxes.values():
                checkbox.setChecked(True)
            for checkbox in self.feature_checkboxes.values():
                checkbox.setChecked(True)
            return
        
        # للمستخدمين العاديين، استخدم الصلاحيات المخصصة أو الافتراضية
        current_permissions = PermissionManager.get_user_permissions(self.user)
        
        # تحديد التابات
        for tab_key, checkbox in self.tab_checkboxes.items():
            checkbox.setChecked(tab_key in current_permissions.get('tabs', []))
        
        # تحديد الإجراءات
        for action_key, checkbox in self.action_checkboxes.items():
            checkbox.setChecked(action_key in current_permissions.get('actions', []))
        
        # تحديد الميزات
        for feature_key, checkbox in self.feature_checkboxes.items():
            checkbox.setChecked(feature_key in current_permissions.get('features', []))
    
    def reset_to_default(self):
        """إعادة تعيين الصلاحيات للافتراضي حسب الدور"""
        reply = QMessageBox.question(
            self, "تأكيد",
            "هل تريد إعادة تعيين الصلاحيات للقيم الافتراضية حسب الدور؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # تحويل الدور إلى UserRole enum إذا كان string
            from core.auth_models import UserRole
            user_role = self.user.role
            if isinstance(user_role, str):
                try:
                    user_role = UserRole(user_role)
                except ValueError:
                    # إذا فشل التحويل، استخدم القيمة كما هي
                    pass
            
            # الحصول على الصلاحيات الافتراضية للدور
            default_permissions = PermissionManager.ROLE_PERMISSIONS.get(user_role, {})
            
            # إعادة تعيين التابات
            for tab_key, checkbox in self.tab_checkboxes.items():
                checkbox.setChecked(tab_key in default_permissions.get('tabs', []))
            
            # إعادة تعيين الإجراءات
            for action_key, checkbox in self.action_checkboxes.items():
                checkbox.setChecked(action_key in default_permissions.get('actions', []))
            
            # إعادة تعيين الميزات
            for feature_key, checkbox in self.feature_checkboxes.items():
                checkbox.setChecked(feature_key in default_permissions.get('features', []))
    
    def save_permissions(self):
        """حفظ الصلاحيات المخصصة"""
        try:
            # جمع الصلاحيات المحددة
            selected_tabs = [key for key, checkbox in self.tab_checkboxes.items() if checkbox.isChecked()]
            selected_actions = [key for key, checkbox in self.action_checkboxes.items() if checkbox.isChecked()]
            selected_features = [key for key, checkbox in self.feature_checkboxes.items() if checkbox.isChecked()]
            
            # إنشاء كائن الصلاحيات المخصصة
            custom_permissions = {
                'tabs': selected_tabs,
                'actions': selected_actions,
                'features': selected_features
            }
            
            # حفظ في قاعدة البيانات
            user_id = self.user.id if hasattr(self.user, 'id') and self.user.id else self.user._mongo_id
            success = self.repository.update_user(user_id, {
                'custom_permissions': custom_permissions
            })
            
            if success:
                QMessageBox.information(
                    self, "نجاح",
                    f"تم حفظ صلاحيات المستخدم {self.user.username} بنجاح!\n\n"
                    f"التابات: {len(selected_tabs)}\n"
                    f"الإجراءات: {len(selected_actions)}\n"
                    f"الميزات: {len(selected_features)}"
                )
                self.accept()
            else:
                QMessageBox.critical(self, "خطأ", "فشل حفظ الصلاحيات في قاعدة البيانات!")
                
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء حفظ الصلاحيات:\n{e}")