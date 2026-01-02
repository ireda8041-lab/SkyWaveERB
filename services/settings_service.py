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
_APP_DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SkyWaveERP')
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
    }

    def __init__(self):
        self.settings = self.load_settings()
        # دمج الإعدادات من الملف المحلي (مثل smart_scan)
        self._merge_local_settings()
        safe_print("INFO: قسم الإعدادات (SettingsService) جاهز.")
    
    def _merge_local_settings(self):
        """دمج الإعدادات من ملف المشروع المحلي (مثل smart_scan)"""
        try:
            if os.path.exists(_LOCAL_SETTINGS_FILE):
                with open(_LOCAL_SETTINGS_FILE, encoding="utf-8") as f:
                    local_settings = json.load(f)
                
                # دمج smart_scan إذا لم يكن موجوداً في الإعدادات الرئيسية
                if "smart_scan" in local_settings and "smart_scan" not in self.settings:
                    self.settings["smart_scan"] = local_settings["smart_scan"]
                    safe_print("INFO: [SettingsService] تم دمج إعدادات smart_scan من الملف المحلي")
                
                # دمج أي إعدادات أخرى غير موجودة
                for key, value in local_settings.items():
                    if key not in self.settings:
                        self.settings[key] = value
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
                safe_print(f"ERROR: [SettingsService] فشل تحميل ملف الإعدادات: {e}. سيتم استخدام الافتراضي.")
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
