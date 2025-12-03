import requests
import os
import sys
import subprocess
from packaging import version  # تحتاج تثبيت: pip install packaging

# إعدادات ثابتة
CURRENT_VERSION = "1.0.1"
VERSION_URL = "https://raw.githubusercontent.com/imhzm/SkyWaveERB/main/version.json"  # رابط ملف الجيسون الخام
UPDATER_EXE = "updater.exe"  # أو updater.py لو بتشغله كسكربت


def check_and_update():
    try:
        print("جاري التحقق من التحديثات...")
        
        # 1. جلب معلومات الإصدار
        response = requests.get(VERSION_URL)
        data = response.json()
        latest_version = data["version"]
        download_url = data["url"]
        
        # 2. مقارنة الإصدارات
        if version.parse(latest_version) > version.parse(CURRENT_VERSION):
            print(f"يوجد تحديث جديد: {latest_version}")
            
            # 3. تحميل ملف التحديث (ZIP)
            print("جاري تحميل التحديث...")
            zip_path = "update_temp.zip"
            r = requests.get(download_url, stream=True)
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            
            # 4. تشغيل برنامج التحديث وإغلاق الحالي
            print("تشغيل المحدث...")
            # هنا بنبعت: مسار البرنامج الحالي، مسار ملف الزيب، واسم ملف التشغيل
            subprocess.Popen([sys.executable, "updater.py", os.getcwd(), zip_path, "SkyWaveERP.exe"])
            
            # إغلاق البرنامج فوراً
            sys.exit()
        else:
            print("البرنامج محدث لآخر إصدار.")
            
    except Exception as e:
        print(f"حدث خطأ أثناء التحديث: {e}")


# استدعاء الدالة (مثلاً عند ضغط زر تحديث)
if __name__ == "__main__":
    check_and_update()


# لبناء ملف exe للمحدث:
# pyinstaller --onefile updater.py
