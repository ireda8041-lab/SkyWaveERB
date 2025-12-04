import json
import os
from typing import Dict, Any

# استخدام مجلد AppData للمستخدم بدلاً من مجلد البرنامج (لتجنب مشاكل الصلاحيات في Program Files)
_APP_DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SkyWaveERP')
os.makedirs(_APP_DATA_DIR, exist_ok=True)


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
        print("INFO: قسم الإعدادات (SettingsService) جاهز.")

    def load_settings(self) -> Dict[str, Any]:
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                for key, value in self.DEFAULT_SETTINGS.items():
                    if key not in settings:
                        settings[key] = value
                return settings
            except Exception as e:
                print(f"ERROR: [SettingsService] فشل تحميل ملف الإعدادات: {e}. سيتم استخدام الافتراضي.")
                return self.DEFAULT_SETTINGS.copy()
        else:
            print("INFO: [SettingsService] ملف الإعدادات غير موجود. سيتم إنشاؤه.")
            self.save_settings(self.DEFAULT_SETTINGS)
            return self.DEFAULT_SETTINGS.copy()

    def save_settings(self, settings_data: Dict[str, Any]):
        try:
            with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, ensure_ascii=False, indent=4)
            self.settings = settings_data
            print("INFO: [SettingsService] تم حفظ الإعدادات بنجاح.")
        except Exception as e:
            print(f"ERROR: [SettingsService] فشل حفظ الإعدادات: {e}")
            raise

    def get_settings(self) -> Dict[str, Any]:
        return self.settings

    def get_setting(self, key: str) -> Any:
        return self.settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def update_setting(self, key: str, value: Any):
        """تحديث إعداد معين وحفظه"""
        self.settings[key] = value
        self.save_settings(self.settings)
