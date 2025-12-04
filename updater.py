#!/usr/bin/env python3
# الملف: updater.py
# البرنامج المستقل لتحديث التطبيق
# يتم تشغيله بعد إغلاق البرنامج الأساسي لاستبدال الملفات

import sys
import os
import time
import zipfile
import shutil
import subprocess
import json
import fileinput
from pathlib import Path


def log_message(message):
    """طباعة رسالة مع الوقت"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def wait_for_app_closure():
    """انتظار 3 ثواني للتأكد من إغلاق البرنامج الأساسي"""
    log_message("⏳ انتظار إغلاق البرنامج الأساسي...")
    time.sleep(3)


def extract_update(zip_path, target_folder):
    """
    فك ضغط ملف التحديث في المجلد المستهدف
    
    Args:
        zip_path: مسار ملف ZIP
        target_folder: المجلد المستهدف للاستخراج
    """
    try:
        log_message(f"📦 بدء فك ضغط التحديث من: {zip_path}")
        log_message(f"📂 المجلد المستهدف: {target_folder}")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # الحصول على قائمة الملفات
            file_list = zip_ref.namelist()
            total_files = len(file_list)
            log_message(f"📋 عدد الملفات: {total_files}")
            
            # استخراج كل ملف
            for index, file in enumerate(file_list, 1):
                try:
                    zip_ref.extract(file, target_folder)
                    if index % 10 == 0 or index == total_files:
                        log_message(f"⚙️ تم استخراج {index}/{total_files} ملف...")
                except Exception as e:
                    log_message(f"⚠️ تحذير: فشل استخراج {file}: {e}")
        
        log_message("✅ تم فك ضغط التحديث بنجاح")
        return True
        
    except Exception as e:
        log_message(f"❌ خطأ في فك الضغط: {e}")
        return False


def update_version_file(target_folder):
    """
    تحديث رقم الإصدار في ملف version.py بعد التثبيت
    يقرأ الرقم الجديد من version.json ويحدث CURRENT_VERSION
    
    Args:
        target_folder: مجلد البرنامج الذي يحتوي على version.py و version.json
    
    Returns:
        bool: True إذا نجح التحديث، False إذا فشل
    """
    try:
        # مسارات الملفات
        version_json_path = os.path.join(target_folder, "version.json")
        version_py_path = os.path.join(target_folder, "version.py")
        
        # التحقق من وجود الملفات
        if not os.path.exists(version_json_path):
            log_message(f"⚠️ تحذير: لم يتم العثور على {version_json_path}")
            return False
            
        if not os.path.exists(version_py_path):
            log_message(f"⚠️ تحذير: لم يتم العثور على {version_py_path}")
            return False
        
        # قراءة رقم الإصدار الجديد من version.json
        log_message(f"📖 قراءة رقم الإصدار من: {version_json_path}")
        with open(version_json_path, 'r', encoding='utf-8') as f:
            update_data = json.load(f)
            new_version = update_data.get("version")
        
        if not new_version:
            log_message("❌ خطأ: لم يتم العثور على رقم الإصدار في version.json")
            return False
        
        log_message(f"🔢 الإصدار الجديد: {new_version}")
        
        # تحديث ملف version.py
        log_message(f"✏️ تحديث ملف: {version_py_path}")
        updated = False
        
        with fileinput.FileInput(version_py_path, inplace=True, encoding='utf-8') as file:
            for line in file:
                # البحث عن السطر الذي يحتوي على CURRENT_VERSION
                if line.strip().startswith("CURRENT_VERSION"):
                    # استبدال السطر بالرقم الجديد
                    print(f'CURRENT_VERSION = "{new_version}"')
                    updated = True
                else:
                    # طباعة باقي السطور كما هي
                    print(line, end='')
        
        if updated:
            log_message(f"✅ تم تحديث version.py إلى الإصدار {new_version} بنجاح")
            return True
        else:
            log_message("⚠️ تحذير: لم يتم العثور على CURRENT_VERSION في version.py")
            return False
            
    except Exception as e:
        log_message(f"❌ خطأ في تحديث ملف الإصدار: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_zip(zip_path):
    """حذف ملف ZIP بعد الاستخراج"""
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            log_message(f"🗑️ تم حذف ملف التحديث: {zip_path}")
    except Exception as e:
        log_message(f"⚠️ تحذير: فشل حذف ملف ZIP: {e}")


def launch_application(target_folder, executable_name):
    """
    تشغيل البرنامج الأساسي بعد التحديث
    
    Args:
        target_folder: مجلد البرنامج
        executable_name: اسم الملف التنفيذي
    """
    try:
        exe_path = os.path.join(target_folder, executable_name)
        
        if not os.path.exists(exe_path):
            log_message(f"⚠️ تحذير: لم يتم العثور على {exe_path}")
            # محاولة البحث عن main.py كبديل
            main_py = os.path.join(target_folder, "main.py")
            if os.path.exists(main_py):
                log_message("🔄 تشغيل main.py بدلاً من ذلك...")
                subprocess.Popen([sys.executable, main_py], cwd=target_folder)
                return True
            return False
        
        log_message(f"🚀 تشغيل البرنامج: {exe_path}")
        
        # تشغيل البرنامج في عملية منفصلة
        if executable_name.endswith('.exe'):
            subprocess.Popen([exe_path], cwd=target_folder)
        else:
            subprocess.Popen([sys.executable, exe_path], cwd=target_folder)
        
        log_message("✅ تم تشغيل البرنامج بنجاح")
        return True
        
    except Exception as e:
        log_message(f"❌ خطأ في تشغيل البرنامج: {e}")
        return False


def main():
    """الدالة الرئيسية للمحدث"""
    log_message("="*60)
    log_message("🔄 Sky Wave ERP Updater")
    log_message("="*60)
    
    # التحقق من المعاملات
    if len(sys.argv) < 4:
        log_message("❌ خطأ: معاملات غير كافية")
        log_message("الاستخدام: updater.py <target_folder> <zip_path> <executable_name>")
        input("اضغط Enter للخروج...")
        sys.exit(1)
    
    target_folder = sys.argv[1]
    zip_path = sys.argv[2]
    executable_name = sys.argv[3]
    
    log_message(f"📁 المجلد المستهدف: {target_folder}")
    log_message(f"📦 ملف التحديث: {zip_path}")
    log_message(f"🎯 الملف التنفيذي: {executable_name}")
    
    # التحقق من وجود الملفات
    if not os.path.exists(zip_path):
        log_message(f"❌ خطأ: ملف التحديث غير موجود: {zip_path}")
        input("اضغط Enter للخروج...")
        sys.exit(1)
    
    # الخطوة 1: الانتظار
    wait_for_app_closure()
    
    # الخطوة 2: فك الضغط
    if not extract_update(zip_path, target_folder):
        log_message("❌ فشل التحديث!")
        input("اضغط Enter للخروج...")
        sys.exit(1)
    
    # الخطوة 3: تحديث رقم الإصدار في version.py
    log_message("🔄 تحديث رقم الإصدار...")
    if not update_version_file(target_folder):
        log_message("⚠️ تحذير: فشل تحديث رقم الإصدار (سيستمر التحديث)")
    
    # الخطوة 4: حذف ملف ZIP
    cleanup_zip(zip_path)
    
    # الخطوة 5: تشغيل البرنامج
    if not launch_application(target_folder, executable_name):
        log_message("⚠️ فشل تشغيل البرنامج تلقائياً")
        log_message("يرجى تشغيل البرنامج يدوياً")
        input("اضغط Enter للخروج...")
        sys.exit(1)
    
    log_message("="*60)
    log_message("✅ اكتمل التحديث بنجاح!")
    log_message("="*60)
    
    # إغلاق المحدث بعد ثانيتين
    time.sleep(2)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_message(f"❌ خطأ فادح: {e}")
        import traceback
        traceback.print_exc()
        input("اضغط Enter للخروج...")
        sys.exit(1)
