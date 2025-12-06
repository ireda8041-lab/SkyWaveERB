import os
import sys

def check_file(path, description):
    if os.path.exists(path):
        print(f"✅ موجود: {description} ({path})")
        return True
    else:
        print(f"❌ مفقود: {description} ({path}) - ⚠️ البرنامج مش هيشتغل بدونه!")
        return False

print("="*50)
print("🔍 جاري فحص ملفات مشروع SkyWave ERP...")
print("="*50)

# 1. الملفات الأساسية
files_to_check = [
    ("main.py", "ملف التشغيل الرئيسي"),
    ("version.py", "ملف الإصدار"),
    ("updater.py", "ملف التحديث التلقائي"),
    ("update_settings.json", "إعدادات التحديث"),
    ("ui/accounting_manager.py", "ملف المحاسبة"),
    ("ui/main_window.py", "النافذة الرئيسية"),
    ("ui/login_window.py", "نافذة تسجيل الدخول"),
    ("services/smart_scan_service.py", "خدمة المسح الذكي (AI)"),
    ("services/accounting_service.py", "خدمة المحاسبة"),
    ("services/auto_update_service.py", "خدمة التحديث التلقائي"),
    ("core/repository.py", "مستودع البيانات"),
    ("core/auth_models.py", "نظام المصادقة"),
    ("requirements.txt", "ملف المكتبات المطلوبة"),
    ("skywave_settings.json", "ملف الإعدادات"),
    ("icon.ico", "أيقونة البرنامج"),
]

# 2. المجلدات الضرورية
folders_to_check = [
    ("ui", "مجلد الواجهات"),
    ("services", "مجلد الخدمات"),
    ("core", "مجلد الكور"),
    ("assets", "مجلد الصور والأيقونات"),
]

all_good = True

for path, desc in files_to_check:
    if not check_file(path, desc):
        all_good = False

for path, desc in folders_to_check:
    if not check_file(path, desc):
        all_good = False

print("="*50)
if all_good:
    print("🚀 كل الملفات تمام! جاهز للتحويل لـ EXE.")
else:
    print("🛑 فيه ملفات ناقصة! صلحها الأول قبل ما تكمل.")
print("="*50)
