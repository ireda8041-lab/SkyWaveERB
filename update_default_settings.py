"""
تحديث البيانات الافتراضية في ملف الإعدادات
✅ يحدث البيانات إلى القيم الافتراضية المطلوبة
"""

import json
import os

SETTINGS_FILE = "skywave_settings.json"


def update_default_settings():
    """تحديث البيانات الافتراضية"""
    
    # البيانات الافتراضية المطلوبة
    default_settings = {
        "company_name": "Sky Wave",
        "company_tagline": "وكالة تسويق رقمي متكاملة",
        "company_address": "القاهرة - دمياط الجديده",
        "company_phone": "01067894321 - 01021965200",
        "company_email": "skywaveads@hotmail.com",
        "company_website": "www.skywaveads.com/",
        "company_vat": "",
        "default_notes": "شكراً لثقتكم في Sky Wave. نسعد بخدمتكم دائماً.",
        "company_logo_path": "site logo.png",
        "company_logo_data": "",
        "dashboard": {
            "selected_period": "current_month"
        }
    }
    
    # قراءة الإعدادات الحالية إذا وجدت
    current_settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                current_settings = json.load(f)
            print(f"✅ تم قراءة الإعدادات الحالية من {SETTINGS_FILE}")
        except Exception as e:
            print(f"⚠️ فشل قراءة الإعدادات الحالية: {e}")
    
    # دمج الإعدادات (الحالية تأخذ الأولوية)
    updated_settings = {**default_settings, **current_settings}
    
    # التأكد من وجود قسم dashboard
    if "dashboard" not in updated_settings:
        updated_settings["dashboard"] = default_settings["dashboard"]
    
    # حفظ الإعدادات المحدثة
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(updated_settings, f, ensure_ascii=False, indent=2)
        print(f"✅ تم تحديث الإعدادات في {SETTINGS_FILE}")
        
        print("\n" + "=" * 60)
        print("📋 البيانات الافتراضية:")
        print("=" * 60)
        print(f"  اسم الشركة: {updated_settings['company_name']}")
        print(f"  الشعار: {updated_settings['company_tagline']}")
        print(f"  العنوان: {updated_settings['company_address']}")
        print(f"  الهاتف: {updated_settings['company_phone']}")
        print(f"  البريد: {updated_settings['company_email']}")
        print(f"  الموقع: {updated_settings['company_website']}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ فشل حفظ الإعدادات: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        update_default_settings()
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
