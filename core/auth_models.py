# الملف: core/auth_models.py
"""
نماذج المصادقة والمستخدمين
"""

import hashlib
import secrets
from enum import Enum
from typing import Any

from pydantic import BaseModel


class UserRole(Enum):
    """أدوار المستخدمين"""
    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    SALES = "sales"


class User(BaseModel):
    """نموذج المستخدم"""
    id: str | None = None
    mongo_id: str | None = None  # تغيير من _mongo_id لتجنب مشاكل Pydantic
    username: str
    password_hash: str
    role: UserRole
    is_active: bool = True
    full_name: str | None = None
    email: str | None = None
    created_at: str | None = None
    last_login: str | None = None
    custom_permissions: dict | None = None  # صلاحيات مخصصة

    class Config:
        use_enum_values = True

    # للتوافق مع الكود القديم
    @property
    def _mongo_id(self):
        return self.mongo_id

    @_mongo_id.setter
    def _mongo_id(self, value):
        self.mongo_id = value


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
        """التحقق من وجود مستخدمين وإنشاء مدير افتراضي إذا لزم الأمر"""
        try:
            users = self.repo.get_all_users()
            users_count = len(users)

            if users_count == 0:
                # إنشاء مستخدم مدير افتراضي
                print("INFO: [AuthService] لا يوجد مستخدمين. جاري إنشاء مستخدم مدير افتراضي...")
                success = self.create_user(
                    username="admin",
                    password="admin123",
                    role=UserRole.ADMIN,
                    full_name="مدير النظام"
                )
                if success:
                    print("INFO: [AuthService] ✅ تم إنشاء مستخدم مدير افتراضي (admin / admin123)")
                    print("WARNING: [AuthService] ⚠️ يرجى تغيير كلمة المرور الافتراضية فوراً!")
                else:
                    print("ERROR: [AuthService] فشل إنشاء المستخدم الافتراضي")
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

    def authenticate(self, username: str, password: str) -> User | None:
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
                result: User | None = user
                return result
            return None
        except Exception as e:
            print(f"ERROR: [AuthService] فشل المصادقة: {e}")
            return None

    def create_user(self, username: str, password: str, role: UserRole, full_name: str | None = None) -> bool:
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
            'tabs': ['dashboard', 'projects', 'quotes', 'expenses', 'payments', 'clients', 'services', 'accounting', 'todo', 'settings'],
            'actions': ['create', 'read', 'update', 'delete', 'export', 'print'],
            'features': ['user_management', 'system_settings', 'financial_reports', 'data_export', 'task_management']
        },
        UserRole.ACCOUNTANT: {
            'tabs': ['dashboard', 'projects', 'quotes', 'expenses', 'payments', 'clients', 'services', 'accounting', 'todo'],
            'actions': ['create', 'read', 'update', 'delete', 'export', 'print'],
            'features': ['financial_reports', 'data_export', 'task_management']
        },
        UserRole.SALES: {
            'tabs': ['dashboard', 'projects', 'quotes', 'clients', 'services', 'todo'],
            'actions': ['create', 'read', 'update', 'print'],
            'features': ['client_reports', 'task_management']
        }
    }

    # جميع الصلاحيات المتاحة
    ALL_TABS = ['dashboard', 'projects', 'quotes', 'expenses', 'payments', 'clients', 'services', 'accounting', 'todo', 'settings']
    ALL_ACTIONS = ['create', 'read', 'update', 'delete', 'export', 'print']
    ALL_FEATURES = ['user_management', 'system_settings', 'financial_reports', 'data_export', 'client_reports', 'task_management']

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
            result: dict[str, Any] = user.custom_permissions
            return result

        # استخدام صلاحيات الدور الافتراضية
        default_perms: dict[str, Any] = cls.ROLE_PERMISSIONS.get(user.role, {
            'tabs': [],
            'actions': [],
            'features': []
        })
        return default_perms
