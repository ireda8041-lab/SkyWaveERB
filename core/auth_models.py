"""نماذج المصادقة والمستخدمين."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class UserRole(Enum):
    """أدوار المستخدمين."""

    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    SALES = "sales"


@dataclass
class _CompatModel:
    """طبقة توافق خفيفة بدل الاعتماد على Pydantic في هذه النماذج البسيطة."""

    def model_dump(self, **kwargs):
        data = asdict(self)
        exclude = set(kwargs.get("exclude") or ())
        for key in exclude:
            data.pop(key, None)
        return data


@dataclass
class User(_CompatModel):
    """نموذج المستخدم."""

    username: str
    password_hash: str
    role: UserRole | str
    id: str | None = None
    mongo_id: str | None = None
    is_active: bool = True
    full_name: str | None = None
    email: str | None = None
    created_at: str | None = None
    last_modified: str | None = None
    last_login: str | None = None
    custom_permissions: dict[str, Any] | None = None

    def __post_init__(self):
        if isinstance(self.role, str):
            self.role = UserRole(self.role)

        if self.custom_permissions is not None and not isinstance(self.custom_permissions, dict):
            self.custom_permissions = dict(self.custom_permissions)

    @property
    def _mongo_id(self):
        return self.mongo_id

    @_mongo_id.setter
    def _mongo_id(self, value):
        self.mongo_id = value


@dataclass
class UserPermissions(_CompatModel):
    """نموذج صلاحيات المستخدم المخصصة."""

    user_id: str
    tabs: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    features: list = field(default_factory=list)
    restrictions: dict = field(default_factory=dict)


class AuthService:
    """خدمة المصادقة."""

    def __init__(self, repository):
        self.repo = repository
        self._ensure_default_admin()

    def _ensure_default_admin(self):
        """التحقق من وجود مستخدمين وإنشاء مدير افتراضي إذا لزم الأمر."""
        try:
            users = self.repo.get_all_users()
            users_count = len(users)

            if users_count == 0:
                try:
                    from core.config import Config

                    default_password = Config.get_default_admin_password()
                except ImportError:
                    import os

                    default_password = os.environ.get(
                        "DEFAULT_ADMIN_PASSWORD", "SkyWave@Admin2024!"
                    )

                safe_print(
                    "INFO: [AuthService] لا يوجد مستخدمين. جاري إنشاء مستخدم مدير افتراضي..."
                )
                success = self.create_user(
                    username="admin",
                    password=default_password,
                    role=UserRole.ADMIN,
                    full_name="مدير النظام",
                )
                if success:
                    safe_print("INFO: [AuthService] ✅ تم إنشاء مستخدم مدير افتراضي")
                    safe_print("WARNING: [AuthService] ⚠️ يرجى تغيير كلمة المرور الافتراضية فورًا!")
                else:
                    safe_print("ERROR: [AuthService] فشل إنشاء المستخدم الافتراضي")
            else:
                safe_print(f"INFO: [AuthService] يوجد {users_count} مستخدم في النظام")

        except Exception as e:
            safe_print(f"WARNING: [AuthService] فشل فحص المستخدمين: {e}")

    @staticmethod
    def hash_password(password: str) -> str:
        """تشفير كلمة المرور."""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return f"{salt}:{password_hash.hex()}"

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """التحقق من كلمة المرور."""
        try:
            if ":" in password_hash:
                salt, stored_hash = password_hash.split(":")
                password_hash_check = hashlib.pbkdf2_hmac(
                    "sha256", password.encode(), salt.encode(), 100000
                )
                return password_hash_check.hex() == stored_hash

            simple_hash = hashlib.sha256(password.encode()).hexdigest()
            return simple_hash == password_hash
        except Exception:
            return False

    def authenticate(self, username: str, password: str) -> User | None:
        """مصادقة المستخدم."""
        try:
            user = self.repo.get_user_by_username(username)
            if user and user.is_active and self.verify_password(password, user.password_hash):
                from datetime import datetime

                user.last_login = datetime.now().isoformat()
                self.repo.update_user_by_username(username, {"last_login": user.last_login})
                role_display = user.role.value if hasattr(user.role, "value") else str(user.role)
                safe_print(
                    f"INFO: [AuthService] تم تسجيل دخول المستخدم: {username} ({role_display})"
                )
                return user
            return None
        except Exception as e:
            safe_print(f"ERROR: [AuthService] فشل المصادقة: {e}")
            return None

    def create_user(
        self, username: str, password: str, role: UserRole, full_name: str | None = None
    ) -> bool:
        """إنشاء مستخدم جديد."""
        try:
            user = self.repo.get_user_by_username(username)
            if user is not None:
                return False

            user = User(
                username=username,
                password_hash=self.hash_password(password),
                role=role,
                full_name=full_name or username,
                is_active=True,
            )

            self.repo.create_user(user)
            safe_print(f"INFO: [AuthService] تم إنشاء مستخدم جديد: {username}")
            return True
        except Exception as e:
            safe_print(f"ERROR: [AuthService] فشل إنشاء المستخدم: {e}")
            return False


class PermissionManager:
    """مدير الصلاحيات المحدّث مع دعم الصلاحيات المخصصة."""

    ROLE_PERMISSIONS = {
        UserRole.ADMIN: {
            "tabs": [
                "dashboard",
                "projects",
                "quotes",
                "expenses",
                "payments",
                "clients",
                "services",
                "accounting",
                "todo",
                "settings",
            ],
            "actions": ["create", "read", "update", "delete", "export", "print"],
            "features": [
                "user_management",
                "system_settings",
                "financial_reports",
                "data_export",
                "task_management",
            ],
        },
        UserRole.ACCOUNTANT: {
            "tabs": [
                "dashboard",
                "projects",
                "quotes",
                "expenses",
                "payments",
                "clients",
                "services",
                "accounting",
                "todo",
            ],
            "actions": ["create", "read", "update", "delete", "export", "print"],
            "features": ["financial_reports", "data_export", "task_management"],
        },
        UserRole.SALES: {
            "tabs": ["dashboard", "projects", "quotes", "clients", "services", "todo"],
            "actions": ["create", "read", "update", "print"],
            "features": ["client_reports", "task_management"],
        },
    }

    ALL_TABS = [
        "dashboard",
        "projects",
        "quotes",
        "expenses",
        "payments",
        "clients",
        "services",
        "accounting",
        "todo",
        "settings",
    ]
    ALL_ACTIONS = ["create", "read", "update", "delete", "export", "print"]
    ALL_FEATURES = [
        "user_management",
        "system_settings",
        "financial_reports",
        "data_export",
        "client_reports",
        "task_management",
    ]

    @classmethod
    def can_access_tab(cls, user, tab_name: str) -> bool:
        """التحقق من إمكانية الوصول لتاب معين."""
        user_role_str = str(user.role).lower()
        if (
            user.role == UserRole.ADMIN
            or user_role_str == "admin"
            or user_role_str == "userrole.admin"
            or (hasattr(user.role, "value") and user.role.value == "admin")
        ):
            return True

        if (
            hasattr(user, "custom_permissions")
            and user.custom_permissions
            and "tabs" in user.custom_permissions
        ):
            return tab_name in user.custom_permissions["tabs"]

        permissions = cls.ROLE_PERMISSIONS.get(user.role, {})
        return tab_name in permissions.get("tabs", [])

    @classmethod
    def can_perform_action(cls, user, action: str) -> bool:
        """التحقق من إمكانية تنفيذ إجراء معين."""
        user_role_str = str(user.role).lower()
        if (
            user.role == UserRole.ADMIN
            or user_role_str == "admin"
            or user_role_str == "userrole.admin"
            or (hasattr(user.role, "value") and user.role.value == "admin")
        ):
            return True

        if (
            hasattr(user, "custom_permissions")
            and user.custom_permissions
            and "actions" in user.custom_permissions
        ):
            return action in user.custom_permissions["actions"]

        permissions = cls.ROLE_PERMISSIONS.get(user.role, {})
        return action in permissions.get("actions", [])

    @classmethod
    def has_feature(cls, user, feature: str) -> bool:
        """التحقق من توفر ميزة معينة."""
        user_role_str = str(user.role).lower()
        if (
            user.role == UserRole.ADMIN
            or user_role_str == "admin"
            or user_role_str == "userrole.admin"
            or (hasattr(user.role, "value") and user.role.value == "admin")
        ):
            return True

        if (
            hasattr(user, "custom_permissions")
            and user.custom_permissions
            and "features" in user.custom_permissions
        ):
            return feature in user.custom_permissions["features"]

        permissions = cls.ROLE_PERMISSIONS.get(user.role, {})
        return feature in permissions.get("features", [])

    @classmethod
    def get_user_permissions(cls, user) -> dict:
        """الحصول على جميع صلاحيات المستخدم."""
        user_role_str = str(user.role).lower()
        if (
            user.role == UserRole.ADMIN
            or user_role_str == "admin"
            or user_role_str == "userrole.admin"
            or (hasattr(user.role, "value") and user.role.value == "admin")
        ):
            return {"tabs": cls.ALL_TABS, "actions": cls.ALL_ACTIONS, "features": cls.ALL_FEATURES}

        if hasattr(user, "custom_permissions") and user.custom_permissions:
            result: dict[str, Any] = user.custom_permissions
            return result

        default_perms: dict[str, Any] = cls.ROLE_PERMISSIONS.get(
            user.role, {"tabs": [], "actions": [], "features": []}
        )
        return default_perms
