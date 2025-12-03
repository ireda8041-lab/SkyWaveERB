#!/usr/bin/env python3
"""
اختبار نظام التحديث التلقائي
"""

import sys
import os

# إضافة المجلد الحالي إلى المسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_updater import (
    check_for_updates,
    get_current_version,
    get_latest_version_info,
    CURRENT_VERSION,
    VERSION_URL
)


def test_version_info():
    """اختبار الحصول على معلومات الإصدار"""
    print("=" * 80)
    print("🧪 اختبار 1: الحصول على معلومات الإصدار")
    print("=" * 80)
    
    print(f"\n📌 الإصدار الحالي: v{get_current_version()}")
    print(f"🌐 رابط التحقق: {VERSION_URL}")
    
    print("\n⏳ جاري الاتصال بالسيرفر...")
    version_info = get_latest_version_info()
    
    print("\n📦 معلومات آخر إصدار:")
    print(f"  - الإصدار: v{version_info.get('version', 'غير معروف')}")
    print(f"  - تاريخ الإصدار: {version_info.get('release_date', 'غير معروف')}")
    print(f"  - رابط التحميل: {version_info.get('download_url', 'غير متوفر')}")
    
    changelog = version_info.get('changelog', [])
    if changelog:
        print(f"\n📋 التغييرات ({len(changelog)} تحسين):")
        for i, change in enumerate(changelog[:5], 1):
            print(f"  {i}. {change}")
        if len(changelog) > 5:
            print(f"  ... و {len(changelog) - 5} تحسين آخر")
    
    print("\n✅ اختبار 1 مكتمل")
    return True


def test_update_check():
    """اختبار التحقق من التحديثات"""
    print("\n" + "=" * 80)
    print("🧪 اختبار 2: التحقق من التحديثات")
    print("=" * 80)
    
    has_update, latest_version, download_url, changelog = check_for_updates()
    
    if has_update:
        print(f"\n🎉 يوجد تحديث جديد!")
        print(f"  - من: v{CURRENT_VERSION}")
        print(f"  - إلى: v{latest_version}")
        print(f"  - رابط التحميل: {download_url}")
    else:
        print(f"\n✅ البرنامج محدث (v{CURRENT_VERSION})")
    
    print("\n✅ اختبار 2 مكتمل")
    return True


def test_updater_exists():
    """التحقق من وجود updater.exe"""
    print("\n" + "=" * 80)
    print("🧪 اختبار 3: التحقق من وجود updater.exe")
    print("=" * 80)
    
    updater_paths = ["updater.exe", "updater.py"]
    found = False
    
    for path in updater_paths:
        if os.path.exists(path):
            size = os.path.getsize(path)
            size_mb = size / (1024 * 1024)
            print(f"\n✅ تم العثور على: {path}")
            print(f"  - الحجم: {size_mb:.2f} MB ({size:,} bytes)")
            found = True
    
    if not found:
        print("\n⚠️ تحذير: لم يتم العثور على updater.exe أو updater.py")
        print("  يرجى تشغيل: build_updater_system.bat")
        return False
    
    print("\n✅ اختبار 3 مكتمل")
    return True


def main():
    """تشغيل جميع الاختبارات"""
    print("\n" + "=" * 80)
    print("🔬 اختبار نظام التحديث التلقائي - Sky Wave ERP")
    print("=" * 80)
    
    tests = [
        ("معلومات الإصدار", test_version_info),
        ("التحقق من التحديثات", test_update_check),
        ("وجود updater.exe", test_updater_exists),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ فشل الاختبار: {test_name}")
            print(f"  الخطأ: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # النتيجة النهائية
    print("\n" + "=" * 80)
    print("📊 نتائج الاختبار")
    print("=" * 80)
    print(f"✅ نجح: {passed}/{len(tests)}")
    print(f"❌ فشل: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 جميع الاختبارات نجحت!")
    else:
        print(f"\n⚠️ فشل {failed} اختبار")
    
    print("=" * 80)
    input("\nاضغط Enter للخروج...")


if __name__ == "__main__":
    main()
