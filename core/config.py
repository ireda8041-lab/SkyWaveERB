# الملف: core/config.py
"""
⚙️ إدارة الإعدادات والتكوين - Sky Wave ERP
يقرأ الإعدادات من متغيرات البيئة بشكل آمن
"""

import os
import sys
from pathlib import Path

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


def _get_project_root() -> Path:
    """الحصول على مسار المشروع الجذري"""
    if getattr(sys, "frozen", False):
        # التطبيق يعمل كـ EXE
        return Path(sys.executable).parent
    else:
        # التطبيق يعمل كـ Python script
        return Path(__file__).parent.parent


def _load_env_file():
    """تحميل ملف .env إذا كان موجوداً"""
    env_path = _get_project_root() / ".env"

    if not env_path.exists():
        # محاولة البحث في المجلد الحالي
        env_path = Path(".env")

    if env_path.exists():
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # تجاهل التعليقات والأسطر الفارغة
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        # لا نكتب فوق المتغيرات الموجودة
                        if key not in os.environ:
                            os.environ[key] = value
            safe_print("INFO: [Config] ✅ تم تحميل ملف .env")
        except Exception as e:
            safe_print(f"WARNING: [Config] فشل تحميل .env: {e}")


# تحميل ملف .env عند استيراد الوحدة
_load_env_file()


class Config:
    """إعدادات التطبيق المركزية"""

    # === إعدادات قاعدة البيانات ===
    @staticmethod
    def get_mongo_uri() -> str:
        """الحصول على رابط MongoDB من متغيرات البيئة"""
        uri = os.environ.get("MONGO_URI")
        if not uri:
            safe_print("WARNING: [Config] MONGO_URI غير محدد - استخدام القيمة الافتراضية")
            # قيمة افتراضية للتطوير المحلي فقط
            uri = "mongodb://localhost:27017/skywave_erp_db"
        return uri

    @staticmethod
    def get_db_name() -> str:
        """الحصول على اسم قاعدة البيانات"""
        return os.environ.get("MONGO_DB_NAME", "skywave_erp_db")

    @staticmethod
    def get_local_db_path() -> str:
        """الحصول على مسار قاعدة البيانات المحلية"""
        if getattr(sys, "frozen", False):
            # عند التشغيل كـ EXE، استخدم مجلد البرنامج دائماً لضمان عدم استخدام النسخة المضمنة في _internal
            exe_dir = Path(sys.executable).parent
            return str(exe_dir / "skywave_local.db")
        else:
            # عند التطوير، استخدم مجلد المشروع
            project_dir = _get_project_root()
            return str(project_dir / "skywave_local.db")

    # === إعدادات الأمان ===
    @staticmethod
    def get_default_admin_password() -> str:
        """الحصول على كلمة المرور الافتراضية للمدير"""
        password = os.environ.get("DEFAULT_ADMIN_PASSWORD")
        if not password:
            # توليد كلمة مرور عشوائية آمنة إذا لم تكن محددة
            import secrets
            import string
            chars = string.ascii_letters + string.digits + "!@#$%^&*"
            password = ''.join(secrets.choice(chars) for _ in range(16))
            safe_print("WARNING: [Config] ⚠️ تم توليد كلمة مرور عشوائية - يرجى تعيين DEFAULT_ADMIN_PASSWORD في .env!")
        return password

    @staticmethod
    def get_secret_key() -> str:
        """الحصول على المفتاح السري"""
        import secrets

        key = os.environ.get("SECRET_KEY")
        if not key:
            # توليد مفتاح عشوائي إذا لم يكن محدداً
            key = secrets.token_hex(32)
        return key

    # === إعدادات Smart Scan ===
    @staticmethod
    def get_gemini_api_key() -> str | None:
        """الحصول على مفتاح Gemini API"""
        return os.environ.get("GEMINI_API_KEY")

    # === إعدادات التطبيق ===
    @staticmethod
    def is_debug_mode() -> bool:
        """هل وضع التصحيح مفعّل؟"""
        return os.environ.get("DEBUG_MODE", "False").lower() in ("true", "1", "yes")

    @staticmethod
    def get_log_level() -> str:
        """الحصول على مستوى التسجيل"""
        return os.environ.get("LOG_LEVEL", "INFO")

    @staticmethod
    def get_project_root() -> Path:
        """الحصول على مسار المشروع"""
        return _get_project_root()


# إنشاء instance واحد للاستخدام العام
config = Config()
