"""
اختبار تدفق الإشارات (Signals Flow Test)
يتحقق من أن الإشارات تُطلق وتُستقبل بشكل صحيح
"""

import sys
from pathlib import Path

# إضافة المسار الجذري للمشروع
sys.path.insert(0, str(Path(__file__).parent))

from core.safe_print import safe_print


def test_signals_connection():
    """اختبار اتصال الإشارات"""
    safe_print("\n" + "=" * 70)
    safe_print("🔍 اختبار اتصال الإشارات (Signals Connection Test)")
    safe_print("=" * 70 + "\n")

    try:
        from core.signals import app_signals

        # عداد للإشارات المستلمة
        signals_received = {
            "clients": False,
            "projects": False,
            "expenses": False,
            "payments": False,
            "services": False,
            "accounting": False,
            "hr": False,
        }

        # دوال الاستقبال
        def on_clients_changed():
            signals_received["clients"] = True
            safe_print("✅ استلام إشارة: clients_changed")

        def on_projects_changed():
            signals_received["projects"] = True
            safe_print("✅ استلام إشارة: projects_changed")

        def on_expenses_changed():
            signals_received["expenses"] = True
            safe_print("✅ استلام إشارة: expenses_changed")

        def on_payments_changed():
            signals_received["payments"] = True
            safe_print("✅ استلام إشارة: payments_changed")

        def on_services_changed():
            signals_received["services"] = True
            safe_print("✅ استلام إشارة: services_changed")

        def on_accounting_changed():
            signals_received["accounting"] = True
            safe_print("✅ استلام إشارة: accounting_changed")

        def on_hr_changed():
            signals_received["hr"] = True
            safe_print("✅ استلام إشارة: hr_changed")

        # ربط الإشارات
        safe_print("📡 ربط الإشارات...")
        app_signals.clients_changed.connect(on_clients_changed)
        app_signals.projects_changed.connect(on_projects_changed)
        app_signals.expenses_changed.connect(on_expenses_changed)
        app_signals.payments_changed.connect(on_payments_changed)
        app_signals.services_changed.connect(on_services_changed)
        app_signals.accounting_changed.connect(on_accounting_changed)
        app_signals.hr_changed.connect(on_hr_changed)
        safe_print("✅ تم ربط جميع الإشارات\n")

        # اختبار إطلاق الإشارات
        safe_print("🚀 اختبار إطلاق الإشارات...\n")

        test_cases = [
            ("clients", "العملاء"),
            ("projects", "المشاريع"),
            ("expenses", "المصروفات"),
            ("payments", "الدفعات"),
            ("services", "الخدمات"),
            ("accounts", "المحاسبة"),
            ("hr", "الموارد البشرية"),
        ]

        for data_type, arabic_name in test_cases:
            safe_print(f"🔥 إطلاق إشارة: {data_type} ({arabic_name})")
            app_signals.emit_data_changed(data_type)

        # التحقق من النتائج
        safe_print("\n" + "=" * 70)
        safe_print("📊 نتائج الاختبار:")
        safe_print("=" * 70 + "\n")

        all_passed = True
        for signal_name, received in signals_received.items():
            status = "✅ نجح" if received else "❌ فشل"
            safe_print(f"{status} - {signal_name}")
            if not received:
                all_passed = False

        safe_print("\n" + "=" * 70)
        if all_passed:
            safe_print("🎉 جميع الاختبارات نجحت!")
        else:
            safe_print("⚠️ بعض الاختبارات فشلت!")
        safe_print("=" * 70 + "\n")

        return all_passed

    except Exception as e:
        safe_print(f"❌ خطأ في الاختبار: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_repository_signals():
    """اختبار إشارات Repository"""
    safe_print("\n" + "=" * 70)
    safe_print("🔍 اختبار إشارات Repository")
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

        # اختبار إطلاق الإشارة
        safe_print("🚀 اختبار إطلاق إشارة Repository...")
        repo.data_changed_signal.emit("test_table")

        # معالجة الأحداث
        app.processEvents()

        # التحقق
        safe_print("\n" + "=" * 70)
        if "test_table" in signals_received:
            safe_print("✅ إشارة Repository تعمل بشكل صحيح!")
        else:
            safe_print("❌ إشارة Repository لا تعمل!")
        safe_print("=" * 70 + "\n")

        return "test_table" in signals_received

    except Exception as e:
        safe_print(f"❌ خطأ في اختبار Repository: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_mainwindow_handlers():
    """اختبار معالجات MainWindow"""
    safe_print("\n" + "=" * 70)
    safe_print("🔍 اختبار معالجات MainWindow")
    safe_print("=" * 70 + "\n")

    try:
        from ui.main_window import MainWindow

        # التحقق من وجود الدوال
        handlers = [
            "handle_data_change",
            "_refresh_clients_tab",
            "_refresh_projects_tab",
            "_refresh_expenses_tab",
            "_refresh_payments_tab",
            "_refresh_services_tab",
            "_refresh_accounting_tab",
        ]

        all_exist = True
        for handler in handlers:
            if hasattr(MainWindow, handler):
                safe_print(f"✅ {handler} موجود")
            else:
                safe_print(f"❌ {handler} غير موجود")
                all_exist = False

        safe_print("\n" + "=" * 70)
        if all_exist:
            safe_print("✅ جميع معالجات MainWindow موجودة!")
        else:
            safe_print("⚠️ بعض المعالجات غير موجودة!")
        safe_print("=" * 70 + "\n")

        return all_exist

    except Exception as e:
        safe_print(f"❌ خطأ في اختبار MainWindow: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    safe_print("\n" + "🔥" * 35)
    safe_print("🔥 اختبار شامل لنظام الإشارات - Sky Wave ERP")
    safe_print("🔥" * 35 + "\n")

    results = []

    # اختبار 1: اتصال الإشارات
    results.append(("اتصال الإشارات", test_signals_connection()))

    # اختبار 2: إشارات Repository
    results.append(("إشارات Repository", test_repository_signals()))

    # اختبار 3: معالجات MainWindow
    results.append(("معالجات MainWindow", test_mainwindow_handlers()))

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
        safe_print("✅ نظام الإشارات يعمل بشكل صحيح")
    else:
        safe_print("⚠️⚠️⚠️ بعض الاختبارات فشلت! ⚠️⚠️⚠️")
        safe_print("❌ يوجد مشاكل في نظام الإشارات")
    safe_print("=" * 70 + "\n")

    sys.exit(0 if all_passed else 1)
