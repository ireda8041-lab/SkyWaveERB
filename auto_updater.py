# الملف: auto_updater.py
"""
نظام التحديث التلقائي لبرنامج Sky Wave ERP
"""

import requests
import os
import sys
import subprocess
from packaging import version
import json

# إعدادات ثابتة
CURRENT_VERSION = "1.0.1"
VERSION_URL = "https://raw.githubusercontent.com/imhzm/SkyWaveERB/main/version.json"
UPDATER_EXE = "updater.exe"


def check_for_updates():
    """
    التحقق من وجود تحديثات جديدة
    
    Returns:
        tuple: (has_update, latest_version, download_url, changelog)
    """
    try:
        print("🔍 جاري التحقق من التحديثات...")
        
        # 1. جلب معلومات الإصدار
        response = requests.get(VERSION_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        latest_version = data.get("version", "1.0.0")
        download_url = data.get("download_url", "")
        changelog = data.get("changelog", [])
        
        # 2. مقارنة الإصدارات
        if version.parse(latest_version) > version.parse(CURRENT_VERSION):
            print(f"✅ يوجد تحديث جديد: v{latest_version}")
            return True, latest_version, download_url, changelog
        else:
            print(f"✅ البرنامج محدث لآخر إصدار (v{CURRENT_VERSION})")
            return False, CURRENT_VERSION, "", []
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️ فشل الاتصال بالسيرفر: {e}")
        return False, CURRENT_VERSION, "", []
    except Exception as e:
        print(f"❌ حدث خطأ أثناء التحقق: {e}")
        return False, CURRENT_VERSION, "", []


def download_update(download_url, save_path="update_temp.zip"):
    """
    تحميل ملف التحديث
    
    Args:
        download_url: رابط التحميل
        save_path: مسار حفظ الملف
        
    Returns:
        bool: True إذا نجح التحميل
    """
    try:
        print(f"📥 جاري تحميل التحديث من: {download_url}")
        
        response = requests.get(download_url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # عرض التقدم
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\r📊 التقدم: {progress:.1f}%", end='')
        
        print(f"\n✅ تم تحميل التحديث: {save_path}")
        return True
        
    except Exception as e:
        print(f"\n❌ فشل تحميل التحديث: {e}")
        return False


def apply_update(zip_path, exe_name="SkyWaveERP.exe"):
    """
    تطبيق التحديث باستخدام updater.exe
    
    Args:
        zip_path: مسار ملف ZIP
        exe_name: اسم الملف التنفيذي
    """
    try:
        print("🔄 جاري تطبيق التحديث...")
        
        current_dir = os.getcwd()
        
        # التحقق من وجود updater
        if os.path.exists(UPDATER_EXE):
            # تشغيل updater.exe
            subprocess.Popen([
                UPDATER_EXE,
                current_dir,
                zip_path,
                exe_name
            ])
        elif os.path.exists("updater.py"):
            # تشغيل updater.py
            subprocess.Popen([
                sys.executable,
                "updater.py",
                current_dir,
                zip_path,
                exe_name
            ])
        else:
            print("❌ لم يتم العثور على updater.exe أو updater.py")
            return False
        
        print("✅ تم تشغيل المحدث")
        print("🔄 سيتم إغلاق البرنامج وتطبيق التحديث...")
        
        # إغلاق البرنامج الحالي
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ فشل تطبيق التحديث: {e}")
        return False


def check_and_update(auto_download=False):
    """
    التحقق من التحديثات وتطبيقها
    
    Args:
        auto_download: تحميل تلقائي بدون سؤال المستخدم
        
    Returns:
        bool: True إذا تم العثور على تحديث
    """
    try:
        # 1. التحقق من التحديثات
        has_update, latest_version, download_url, changelog = check_for_updates()
        
        if not has_update:
            return False
        
        # 2. عرض معلومات التحديث
        print("\n" + "=" * 80)
        print(f"🎉 تحديث جديد متوفر!")
        print("=" * 80)
        print(f"📦 الإصدار الحالي: v{CURRENT_VERSION}")
        print(f"🆕 الإصدار الجديد: v{latest_version}")
        
        if changelog:
            print("\n📋 التغييرات:")
            for i, change in enumerate(changelog[:5], 1):
                print(f"  {i}. {change}")
            if len(changelog) > 5:
                print(f"  ... و {len(changelog) - 5} تحسين آخر")
        
        print("=" * 80)
        
        # 3. سؤال المستخدم (إذا لم يكن تلقائي)
        if not auto_download:
            response = input("\n❓ هل تريد تحميل التحديث الآن؟ (yes/no): ")
            if response.lower() not in ['yes', 'y', 'نعم']:
                print("⏭️ تم تخطي التحديث")
                return False
        
        # 4. تحميل التحديث
        zip_path = "update_temp.zip"
        if not download_update(download_url, zip_path):
            return False
        
        # 5. تطبيق التحديث
        apply_update(zip_path)
        
        return True
        
    except Exception as e:
        print(f"❌ حدث خطأ أثناء التحديث: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_current_version():
    """الحصول على رقم الإصدار الحالي"""
    return CURRENT_VERSION


def get_latest_version_info():
    """
    الحصول على معلومات آخر إصدار
    
    Returns:
        dict: معلومات الإصدار
    """
    try:
        response = requests.get(VERSION_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except:
        return {
            "version": CURRENT_VERSION,
            "release_date": "Unknown",
            "download_url": "",
            "changelog": []
        }


# للاختبار
if __name__ == "__main__":
    print("=" * 80)
    print("🔄 نظام التحديث التلقائي - Sky Wave ERP")
    print("=" * 80)
    print()
    
    check_and_update(auto_download=False)
