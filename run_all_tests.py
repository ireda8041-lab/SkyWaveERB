"""
🧪 سكربت تشغيل جميع الاختبارات
يقوم بتشغيل كل اختبارات النظام وإنشاء تقرير شامل
"""

import subprocess
import sys
import time
from datetime import datetime


def run_command(cmd, description):
    """تشغيل أمر وإرجاع النتيجة"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print('='*60)
    
    start = time.time()
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    duration = time.time() - start
    
    if result.returncode == 0:
        print(f"✅ نجح في {duration:.2f} ثانية")
    else:
        print(f"❌ فشل في {duration:.2f} ثانية")
    
    if result.stdout:
        print(result.stdout)
    if result.stderr and result.returncode != 0:
        print(result.stderr)
    
    return result.returncode == 0, duration


def main():
    print("="*60)
    print("🧪 SKY WAVE ERP - FULL TEST SUITE")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = []
    total_start = time.time()
    
    # 1. فحص صحة قاعدة البيانات
    success, duration = run_command(
        "python core/db_doctor.py",
        "المرحلة 1: فحص صحة قاعدة البيانات (DB Health Check)"
    )
    results.append(("DB Health Check", success, duration))
    
    # 2. اختبارات الوحدة - المنطق الحرج
    success, duration = run_command(
        "python -m pytest tests/test_critical_logic.py -v --tb=short",
        "المرحلة 2: اختبارات المنطق الحرج (Critical Logic)"
    )
    results.append(("Critical Logic Tests", success, duration))
    
    # 3. اختبارات واجهة المستخدم
    success, duration = run_command(
        "python -m pytest tests/test_ui_components.py -v --tb=short",
        "المرحلة 3: اختبارات واجهة المستخدم (UI Tests)"
    )
    results.append(("UI Component Tests", success, duration))
    
    # 4. اختبارات الأمان
    success, duration = run_command(
        "python -m pytest tests/test_security.py -v --tb=short",
        "المرحلة 4: اختبارات الأمان (Security Tests)"
    )
    results.append(("Security Tests", success, duration))
    
    # 5. اختبارات الروبوت المحاسبي
    success, duration = run_command(
        "python -m pytest tests/test_accounting_service.py -v --tb=short",
        "المرحلة 5: اختبارات الروبوت المحاسبي (Accounting)"
    )
    results.append(("Accounting Service", success, duration))
    
    # 6. اختبارات محرك حل التعارضات
    success, duration = run_command(
        "python -m pytest tests/test_conflict_resolver.py -v --tb=short",
        "المرحلة 6: اختبارات محرك حل التعارضات (Conflicts)"
    )
    results.append(("Conflict Resolver", success, duration))
    
    # 7. اختبارات مدير المزامنة
    success, duration = run_command(
        "python -m pytest tests/test_sync_manager.py -v --tb=short",
        "المرحلة 7: اختبارات مدير المزامنة (Sync Manager)"
    )
    results.append(("Sync Manager", success, duration))
    
    # 8. اختبار التحمل
    success, duration = run_command(
        "python stress_test.py",
        "المرحلة 8: اختبار التحمل (Stress Test)"
    )
    results.append(("Stress Test", success, duration))
    
    # التقرير النهائي
    total_duration = time.time() - total_start
    passed = sum(1 for _, s, _ in results if s)
    failed = len(results) - passed
    
    print("\n" + "="*60)
    print("📊 التقرير النهائي")
    print("="*60)
    
    for name, success, duration in results:
        status = "✅ نجح" if success else "❌ فشل"
        print(f"  {status} | {name:<25} | {duration:.2f}s")
    
    print("-"*60)
    print(f"  📈 الإجمالي: {passed}/{len(results)} نجح")
    print(f"  ⏱️  الوقت الكلي: {total_duration:.2f} ثانية")
    print("="*60)
    
    if failed == 0:
        print("\n🎉 جميع الاختبارات نجحت! النظام جاهز للإنتاج.")
        return 0
    else:
        print(f"\n⚠️ {failed} اختبار(ات) فشلت. يرجى المراجعة.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
