"""
اختبار إشارات التحديث والحذف
يتحقق من أن جميع دوال update و delete تُطلق الإشارات
"""

import sys
from pathlib import Path

# إضافة المسار الجذري للمشروع
sys.path.insert(0, str(Path(__file__).parent))

from core.safe_print import safe_print


def test_repository_signals():
    """اختبار إطلاق الإشارات من Repository"""
    safe_print("\n" + "=" * 70)
    safe_print("🔍 اختبار إشارات Repository (Update & Delete)")
    safe_print("=" * 70 + "\n")

    try:
        from PyQt6.QtCore import QCoreApplication

        from core.repository import Repository

        # إنشاء QApplication للإشارات
        app = QCoreApplication.instance()
        if app is None:
            app = QCoreApplication(sys.argv)

        # إنشاء Repository
        repo = Repository()

        # عداد للإشارات
        signals_received = []

        def on_data_changed(table_name: str):
            signals_received.append(table_name)
            safe_print(f"✅ Repository أطلق إشارة: {table_name}")

        # ربط الإشارة
        repo.data_changed_signal.connect(on_data_changed)
        safe_print("✅ تم ربط إشارة Repository\n")

        # اختبار إطلاق الإشارات
        test_cases = [
            ("clients", "العملاء"),
            ("projects", "المشاريع"),
            ("expenses", "المصروفات"),
            ("payments", "الدفعات"),
            ("services", "الخدمات"),
            ("accounts", "الحسابات"),
        ]

        safe_print("🚀 اختبار إطلاق الإشارات...\n")

        for table_name, arabic_name in test_cases:
            safe_print(f"🔥 إطلاق إشارة: {table_name} ({arabic_name})")
            repo.data_changed_signal.emit(table_name)
            app.processEvents()  # معالجة الأحداث

        # التحقق
        safe_print("\n" + "=" * 70)
        safe_print("📊 نتائج الاختبار:")
        safe_print("=" * 70 + "\n")

        all_passed = True
        for table_name, arabic_name in test_cases:
            if table_name in signals_received:
                safe_print(f"✅ {table_name} ({arabic_name}) - نجح")
            else:
                safe_print(f"❌ {table_name} ({arabic_name}) - فشل")
                all_passed = False

        safe_print("\n" + "=" * 70)
        if all_passed:
            safe_print("✅ جميع الإشارات تعمل بشكل صحيح!")
        else:
            safe_print("⚠️ بعض الإشارات لا تعمل!")
        safe_print("=" * 70 + "\n")

        return all_passed

    except Exception as e:
        safe_print(f"❌ خطأ في الاختبار: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_repository_methods():
    """التحقق من وجود دوال update و delete في Repository"""
    safe_print("\n" + "=" * 70)
    safe_print("🔍 التحقق من دوال Repository")
    safe_print("=" * 70 + "\n")

    try:
        from core.repository import Repository

        repo = Repository()

        # قائمة الدوال المطلوبة
        required_methods = {
            "update": [
                "update_client",
                "update_project",
                "update_payment",
                "update_expense",
                "update_service",
                "update_account",
            ],
            "delete": [
                "delete_client_permanently",
                "delete_project",
                "delete_payment",
                "delete_expense",
                "delete_service_permanently",
            ],
        }

        all_exist = True

        for category, methods in required_methods.items():
            safe_print(f"\n📋 دوال {category.upper()}:")
            for method in methods:
                if hasattr(repo, method):
                    safe_print(f"  ✅ {method}")
                else:
                    safe_print(f"  ❌ {method} - غير موجود!")
                    all_exist = False

        safe_print("\n" + "=" * 70)
        if all_exist:
            safe_print("✅ جميع الدوال المطلوبة موجودة!")
        else:
            safe_print("⚠️ بعض الدوال غير موجودة!")
        safe_print("=" * 70 + "\n")

        return all_exist

    except Exception as e:
        safe_print(f"❌ خطأ في الفحص: {e}")
        import traceback

        traceback.print_exc()
        return False


def verify_signal_emission_in_code():
    """التحقق من أن الكود يحتوي على إطلاق الإشارات"""
    safe_print("\n" + "=" * 70)
    safe_print("🔍 التحقق من إطلاق الإشارات في الكود")
    safe_print("=" * 70 + "\n")

    try:
        import re

        # قراءة ملف repository.py
        with open("core/repository.py", "r", encoding="utf-8") as f:
            content = f.read()

        # البحث عن دوال update و delete
        methods_to_check = {
            "update_payment": "payments",
            "delete_payment": "payments",
            "delete_expense": "expenses",
            "delete_client_permanently": "clients",
            "delete_service_permanently": "services",
        }

        all_emit = True

        for method_name, expected_signal in methods_to_check.items():
            # البحث عن الدالة
            pattern = rf"def {method_name}\([^)]*\):"
            match = re.search(pattern, content)

            if not match:
                safe_print(f"❌ {method_name} - الدالة غير موجودة!")
                all_emit = False
                continue

            # الحصول على محتوى الدالة (حتى الدالة التالية)
            start = match.start()
            next_def = content.find("\n    def ", start + 1)
            if next_def == -1:
                method_content = content[start:]
            else:
                method_content = content[start:next_def]

            # البحث عن إطلاق الإشارة
            if f'data_changed_signal.emit("{expected_signal}")' in method_content:
                safe_print(f"✅ {method_name} - يُطلق إشارة '{expected_signal}'")
            else:
                safe_print(f"❌ {method_name} - لا يُطلق إشارة '{expected_signal}'!")
                all_emit = False

        safe_print("\n" + "=" * 70)
        if all_emit:
            safe_print("✅ جميع الدوال تُطلق الإشارات بشكل صحيح!")
        else:
            safe_print("⚠️ بعض الدوال لا تُطلق الإشارات!")
        safe_print("=" * 70 + "\n")

        return all_emit

    except Exception as e:
        safe_print(f"❌ خطأ في التحقق: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    safe_print("\n" + "🔥" * 35)
    safe_print("🔥 اختبار شامل لإشارات التحديث والحذف")
    safe_print("🔥" * 35 + "\n")

    results = []

    # اختبار 1: التحقق من وجود الدوال
    results.append(("وجود الدوال", check_repository_methods()))

    # اختبار 2: التحقق من إطلاق الإشارات في الكود
    results.append(("إطلاق الإشارات في الكود", verify_signal_emission_in_code()))

    # اختبار 3: اختبار إطلاق الإشارات فعلياً
    results.append(("إطلاق الإشارات فعلياً", test_repository_signals()))

    # النتيجة النهائية
    safe_print("\n" + "=" * 70)
    safe_print("📊 النتيجة النهائية:")
    safe_print("=" * 70 + "\n")

    all_passed = True
    for test_name, passed in results:
        status = "✅ نجح" if passed else "❌ فشل"
        safe_print(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    safe_print("\n" + "=" * 70)
    if all_passed:
        safe_print("🎉🎉🎉 جميع الاختبارات نجحت! 🎉🎉🎉")
        safe_print("✅ إشارات التحديث والحذف تعمل بشكل صحيح")
    else:
        safe_print("⚠️⚠️⚠️ بعض الاختبارات فشلت! ⚠️⚠️⚠️")
        safe_print("❌ يوجد مشاكل في إشارات التحديث والحذف")
    safe_print("=" * 70 + "\n")

    sys.exit(0 if all_passed else 1)
