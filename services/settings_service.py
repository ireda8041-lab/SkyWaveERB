import base64
import json
import os
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


# استخدام مجلد AppData للمستخدم بدلاً من مجلد البرنامج (لتجنب مشاكل الصلاحيات في Program Files)
_APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SkyWaveERP")
os.makedirs(_APP_DATA_DIR, exist_ok=True)

# ملف الإعدادات المحلي في مجلد المشروع
_LOCAL_SETTINGS_FILE = "skywave_settings.json"


class SettingsService:
    """قسم الإعدادات المسؤول عن حفظ وقراءة إعدادات التطبيق."""

    SETTINGS_FILE = os.path.join(_APP_DATA_DIR, "skywave_settings.json")

    DEFAULT_SETTINGS = {
        "company_name": "Sky Wave",
        "company_tagline": "وكالة تسويق رقمي متكاملة",
        "company_address": "القاهرة، مصر",
        "company_phone": "+20 10 123 4567",
        "company_email": "info@skywave.agency",
        "bank_name": "البنك الأهلي المصري",
        "bank_account": "XXXX-XXXX-XXXX-XXXX",
        "vodafone_cash": "010-XXXX-XXXX",
        "default_tax_rate": 0.0,
        "default_notes": "شكراً لثقتكم في Sky Wave. نسعد بخدمتكم دائماً.",
        "company_logo_path": "",
        "company_logo_data": "",  # ⚡ اللوجو كـ Base64 للمزامنة بين الأجهزة
    }

    def __init__(self):
        self.settings = self.load_settings()
        self._merge_local_settings()
        safe_print("INFO: قسم الإعدادات (SettingsService) جاهز.")

    def _merge_local_settings(self):
        """⚡ دمج الإعدادات من الملف المحلي (يحدث القيم الموجودة)"""
        try:
            if os.path.exists(_LOCAL_SETTINGS_FILE):
                safe_print(
                    f"INFO: [SettingsService] جاري تحميل الإعدادات من {_LOCAL_SETTINGS_FILE}"
                )
                with open(_LOCAL_SETTINGS_FILE, encoding="utf-8") as f:
                    local_settings = json.load(f)

                # ⚡ تحديث كل القيم من الملف المحلي (له الأولوية)
                updated_count = 0
                for key, value in local_settings.items():
                    if key not in self.settings or self.settings[key] != value:
                        self.settings[key] = value
                        updated_count += 1

                if updated_count > 0:
                    safe_print(
                        f"INFO: [SettingsService] ✅ تم تحديث {updated_count} إعداد من الملف المحلي"
                    )
                    # حفظ الإعدادات المدمجة
                    self.save_settings(self.settings)
        except Exception as e:
            safe_print(f"WARNING: [SettingsService] فشل قراءة الملف المحلي: {e}")

    def load_settings(self) -> dict[str, Any]:
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, encoding="utf-8") as f:
                    settings = json.load(f)
                for key, value in self.DEFAULT_SETTINGS.items():
                    if key not in settings:
                        settings[key] = value
                return dict(settings)
            except Exception as e:
                safe_print(
                    f"ERROR: [SettingsService] فشل تحميل ملف الإعدادات: {e}. سيتم استخدام الافتراضي."
                )
                return dict(self.DEFAULT_SETTINGS)
        else:
            safe_print("INFO: [SettingsService] ملف الإعدادات غير موجود. سيتم إنشاؤه.")
            self.save_settings(self.DEFAULT_SETTINGS)
            return dict(self.DEFAULT_SETTINGS)

    def save_settings(self, settings_data: dict[str, Any]):
        try:
            with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, ensure_ascii=False, indent=4)
            self.settings = settings_data
            safe_print("INFO: [SettingsService] تم حفظ الإعدادات بنجاح.")
        except Exception as e:
            safe_print(f"ERROR: [SettingsService] فشل حفظ الإعدادات: {e}")
            raise

    def get_settings(self) -> dict[str, Any]:
        return dict(self.settings)

    def get_setting(self, key: str) -> Any:
        return self.settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def update_setting(self, key: str, value: Any):
        """تحديث إعداد معين وحفظه"""
        self.settings[key] = value
        self.save_settings(self.settings)

    # ==========================================
    # ⚡ دوال اللوجو - للمزامنة بين الأجهزة
    # ==========================================

    def save_logo_from_file(self, file_path: str) -> bool:
        """
        حفظ اللوجو من ملف كـ Base64
        يتم تخزينه في الإعدادات للمزامنة بين الأجهزة
        """
        try:
            if not file_path or not os.path.exists(file_path):
                return False

            with open(file_path, "rb") as f:
                logo_bytes = f.read()

            # تحويل لـ Base64
            logo_base64 = base64.b64encode(logo_bytes).decode("utf-8")

            # حفظ في الإعدادات
            self.settings["company_logo_data"] = logo_base64
            self.settings["company_logo_path"] = file_path  # للعرض المحلي
            self.save_settings(self.settings)

            safe_print(f"INFO: [SettingsService] تم حفظ اللوجو ({len(logo_base64)} حرف)")
            return True

        except Exception as e:
            safe_print(f"ERROR: [SettingsService] فشل حفظ اللوجو: {e}")
            return False

    def get_logo_as_pixmap(self):
        """
        الحصول على اللوجو كـ QPixmap
        يحاول أولاً من Base64، ثم من المسار المحلي
        """
        try:
            from PyQt6.QtCore import QByteArray
            from PyQt6.QtGui import QPixmap

            # أولاً: محاولة تحميل من Base64 (للمزامنة)
            logo_data = self.settings.get("company_logo_data", "")
            if logo_data:
                try:
                    logo_bytes = base64.b64decode(logo_data)
                    pixmap = QPixmap()
                    pixmap.loadFromData(QByteArray(logo_bytes))
                    if not pixmap.isNull():
                        return pixmap
                except Exception as e:
                    safe_print(f"WARNING: [SettingsService] فشل تحميل اللوجو من Base64: {e}")

            # ثانياً: محاولة تحميل من المسار المحلي
            logo_path = self.settings.get("company_logo_path", "")
            if logo_path and os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    return pixmap

            return None

        except Exception as e:
            safe_print(f"ERROR: [SettingsService] فشل تحميل اللوجو: {e}")
            return None

    def clear_logo(self):
        """مسح اللوجو"""
        self.settings["company_logo_data"] = ""
        self.settings["company_logo_path"] = ""
        self.save_settings(self.settings)
        safe_print("INFO: [SettingsService] تم مسح اللوجو")

    # ==========================================
    # ⚡ مزامنة الإعدادات مع MongoDB
    # ==========================================

    def sync_settings_to_cloud(self, repository) -> bool:
        """رفع الإعدادات للسحابة"""
        try:
            if not repository or not repository.online or repository.mongo_db is None:
                return False

            # حفظ الإعدادات في مجموعة system_settings
            collection = repository.mongo_db["system_settings"]

            # استخدام upsert لتحديث أو إنشاء
            collection.update_one({"_id": "company_settings"}, {"$set": self.settings}, upsert=True)

            safe_print("INFO: [SettingsService] ✅ تم رفع الإعدادات للسحابة")
            return True

        except Exception as e:
            safe_print(f"ERROR: [SettingsService] فشل رفع الإعدادات للسحابة: {e}")
            return False

    def sync_settings_from_cloud(self, repository) -> bool:
        """تحميل الإعدادات من السحابة"""
        try:
            if not repository or not repository.online or repository.mongo_db is None:
                return False

            collection = repository.mongo_db["system_settings"]
            cloud_settings = collection.find_one({"_id": "company_settings"})

            if cloud_settings:
                # إزالة _id من الإعدادات
                cloud_settings.pop("_id", None)

                # دمج الإعدادات (السحابة تأخذ الأولوية)
                for key, value in cloud_settings.items():
                    self.settings[key] = value

                # حفظ محلياً
                self.save_settings(self.settings)

                safe_print("INFO: [SettingsService] ✅ تم تحميل الإعدادات من السحابة")
                return True

            return False

        except Exception as e:
            safe_print(f"ERROR: [SettingsService] فشل تحميل الإعدادات من السحابة: {e}")
            return False
