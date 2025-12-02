# الملف: core/auth_models.py
"""
نماذج المصادقة والمستخدمين
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel
import hashlib
import secrets


class UserRole(Enum):
    """أدوار المستخدمين"""
    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    SALES = "sales"


class User(BaseModel):
    """نموذج المستخدم"""
    id: Optional[str] = None
    _mongo_id: Optional[str] = None
    username: str
    password_hash: str
    role: UserRole
    is_active: bool = True
    full_name: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[str] = None
    last_login: Optional[str] = None
    custom_permissions: Optional[dict] = None  # صلاحيات مخصصة

    class Config:
        use_enum_values = True


class UserPermissions(BaseModel):
    """نموذج صلاحيات المستخدم المخصصة"""
    user_id: str
    tabs: list = []  # التابات المسموحة
    actions: list = []  # الإجراءات المسموحة
    features: list = []  # الميزات المسموحة
    restrictions: dict = {}  # قيود إضافية


class AuthService:
    """خدمة المصادقة"""
    
    def __init__(self, repository):
        self.repo = repository
        self._ensure_default_admin()
    
    def _ensure_default_admin(self):
        """التحقق من وجود مستخدمين - تم تعطيل إنشاء المستخدمين الافتراضيين"""
        try:
            # تم تعطيل إنشاء المستخدمين الافتراضيين
            # يجب إنشاء المستخدمين يدوياً أو عبر سكريبت منفصل
            users_count = len(self.repo.get_all_users())
            if users_count == 0:
                print("WARNING: [AuthService] لا يوجد مستخدمين في النظام. يرجى إنشاء مستخدم مدير.")
            else:
                print(f"INFO: [AuthService] يوجد {users_count} مستخدم في النظام")
                
        except Exception as e:
            print(f"WARNING: [AuthService] فشل فحص المستخدمين: {e}")
    
    @staticmethod
    def hash_password(password: str) -> str:
        """تشفير كلمة المرور"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}:{password_hash.hex()}"
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """التحقق من كلمة المرور"""
        try:
            # التحقق من التشفير الجديد (PBKDF2 مع salt)
            if ':' in password_hash:
                salt, stored_hash = password_hash.split(':')
                password_hash_check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
                return password_hash_check.hex() == stored_hash
            else:
                # التوافق مع التشفير القديم (SHA256 بسيط)
                simple_hash = hashlib.sha256(password.encode()).hexdigest()
                return simple_hash == password_hash
        except Exception:
            return False
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """مصادقة المستخدم"""
        try:
            user = self.repo.get_user_by_username(username)
            if user and user.is_active and self.verify_password(password, user.password_hash):
                # تحديث آخر تسجيل دخول
                from datetime import datetime
                user.last_login = datetime.now().isoformat()
                self.repo.update_user(user.id or user._mongo_id, {"last_login": user.last_login})
                role_display = user.role.value if hasattr(user.role, 'value') else str(user.role)
                print(f"INFO: [AuthService] تم تسجيل دخول المستخدم: {username} ({role_display})")
                return user
            return None
        except Exception as e:
            print(f"ERROR: [AuthService] فشل المصادقة: {e}")
            return None
    
    def create_user(self, username: str, password: str, role: UserRole, full_name: str = None) -> bool:
        """إنشاء مستخدم جديد"""
        try:
            # التحقق من عدم وجود المستخدم
            if self.repo.get_user_by_username(username):
                return False
            
            user = User(
                username=username,
                password_hash=self.hash_password(password),
                role=role,
                full_name=full_name or username,
                is_active=True
            )
            
            self.repo.create_user(user)
            print(f"INFO: [AuthService] تم إنشاء مستخدم جديد: {username}")
            return True
        except Exception as e:
            print(f"ERROR: [AuthService] فشل إنشاء المستخدم: {e}")
            return False


class PermissionManager:
    """مدير الصلاحيات المحدث مع دعم الصلاحيات المخصصة"""
    
    # تعريف الصلاحيات الافتراضية لكل دور
    ROLE_PERMISSIONS = {
        UserRole.ADMIN: {
            'tabs': ['dashboard', 'projects', 'quotes', 'expenses', 'payments', 'clients', 'services', 'accounting', 'settings'],
            'actions': ['create', 'read', 'update', 'delete', 'export', 'print'],
            'features': ['user_management', 'system_settings', 'financial_reports', 'data_export']
        },
        UserRole.ACCOUNTANT: {
            'tabs': ['dashboard', 'projects', 'quotes', 'expenses', 'payments', 'clients', 'services', 'accounting'],
            'actions': ['create', 'read', 'update', 'delete', 'export', 'print'],
            'features': ['financial_reports', 'data_export']
        },
        UserRole.SALES: {
            'tabs': ['dashboard', 'projects', 'quotes', 'clients', 'services'],
            'actions': ['create', 'read', 'update', 'print'],
            'features': ['client_reports']
        }
    }
    
    # جميع الصلاحيات المتاحة
    ALL_TABS = ['dashboard', 'projects', 'quotes', 'expenses', 'payments', 'clients', 'services', 'accounting', 'settings']
    ALL_ACTIONS = ['create', 'read', 'update', 'delete', 'export', 'print']
    ALL_FEATURES = ['user_management', 'system_settings', 'financial_reports', 'data_export', 'client_reports']
    
    @classmethod
    def can_access_tab(cls, user, tab_name: str) -> bool:
        """التحقق من إمكانية الوصول لتاب معين (مع دعم الصلاحيات المخصصة)"""
        # إذا كان المستخدم مدير، له صلاحية كاملة (فحص شامل)
        user_role_str = str(user.role).lower()
        if (user.role == UserRole.ADMIN or 
            user_role_str == "admin" or 
            user_role_str == "userrole.admin" or
            (hasattr(user.role, 'value') and user.role.value == "admin")):
            return True
        
        # التحقق من الصلاحيات المخصصة أولاً
        if hasattr(user, 'custom_permissions') and user.custom_permissions and 'tabs' in user.custom_permissions:
            return tab_name in user.custom_permissions['tabs']
        
        # استخدام صلاحيات الدور الافتراضية
        permissions = cls.ROLE_PERMISSIONS.get(user.role, {})
        return tab_name in permissions.get('tabs', [])
    
    @classmethod
    def can_perform_action(cls, user, action: str) -> bool:
        """التحقق من إمكانية تنفيذ إجراء معين"""
        # إذا كان المستخدم مدير، له صلاحية كاملة (فحص شامل)
        user_role_str = str(user.role).lower()
        if (user.role == UserRole.ADMIN or 
            user_role_str == "admin" or 
            user_role_str == "userrole.admin" or
            (hasattr(user.role, 'value') and user.role.value == "admin")):
            return True
        
        # التحقق من الصلاحيات المخصصة أولاً
        if hasattr(user, 'custom_permissions') and user.custom_permissions and 'actions' in user.custom_permissions:
            return action in user.custom_permissions['actions']
        
        # استخدام صلاحيات الدور الافتراضية
        permissions = cls.ROLE_PERMISSIONS.get(user.role, {})
        return action in permissions.get('actions', [])
    
    @classmethod
    def has_feature(cls, user, feature: str) -> bool:
        """التحقق من توفر ميزة معينة"""
        # إذا كان المستخدم مدير، له صلاحية كاملة (فحص شامل)
        user_role_str = str(user.role).lower()
        if (user.role == UserRole.ADMIN or 
            user_role_str == "admin" or 
            user_role_str == "userrole.admin" or
            (hasattr(user.role, 'value') and user.role.value == "admin")):
            return True
        
        # التحقق من الصلاحيات المخصصة أولاً
        if hasattr(user, 'custom_permissions') and user.custom_permissions and 'features' in user.custom_permissions:
            return feature in user.custom_permissions['features']
        
        # استخدام صلاحيات الدور الافتراضية
        permissions = cls.ROLE_PERMISSIONS.get(user.role, {})
        return feature in permissions.get('features', [])
    
    @classmethod
    def get_user_permissions(cls, user) -> dict:
        """الحصول على جميع صلاحيات المستخدم"""
        # إذا كان المستخدم مدير، له صلاحية كاملة (فحص شامل)
        user_role_str = str(user.role).lower()
        if (user.role == UserRole.ADMIN or 
            user_role_str == "admin" or 
            user_role_str == "userrole.admin" or
            (hasattr(user.role, 'value') and user.role.value == "admin")):
            return {
                'tabs': cls.ALL_TABS,
                'actions': cls.ALL_ACTIONS,
                'features': cls.ALL_FEATURES
            }
        
        # إذا كان لديه صلاحيات مخصصة
        if hasattr(user, 'custom_permissions') and user.custom_permissions:
            return user.custom_permissions
        
        # استخدام صلاحيات الدور الافتراضية
        return cls.ROLE_PERMISSIONS.get(user.role, {
            'tabs': [],
            'actions': [],
            'features': []
        })