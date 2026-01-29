#!/usr/bin/env python3
"""
اختبار تشخيص مشكلة التحديث الفوري للواجهة
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.repository import Repository
from core import schemas
from datetime import datetime

def test_signals_working():
    """اختبار عمل الإشارات"""
    print("🔍 اختبار عمل نظام الإشارات...")
    
    # إنشاء Repository
    repo = Repository()
    
    # متغير لتتبع الإشارات
    signals_received = []
    
    def signal_handler(table_name):
        signals_received.append(table_name)
        print(f"📡 تم استلام إشارة: {table_name}")
    
    # ربط الإشارة
    repo.data_changed_signal.connect(signal_handler)
    print("✅ تم ربط معالج الإشارة")
    
    # اختبار 1: إضافة عميل جديد
    print("\n🧪 اختبار 1: إضافة عميل جديد...")
    import random
    random_phone = f"123{random.randint(1000000, 9999999)}"
    test_client = schemas.Client(
        name=f"عميل اختبار {datetime.now().strftime('%H:%M:%S')}",
        email=f"test{random.randint(1000, 9999)}@example.com",
        phone=random_phone
    )
    
    try:
        created_client = repo.create_client(test_client)
        print(f"✅ تم إنشاء العميل: {created_client.name}")
    except Exception as e:
        print(f"❌ فشل إنشاء العميل: {e}")
        return False
    
    # اختبار 2: تعديل العميل
    print("\n🧪 اختبار 2: تعديل العميل...")
    try:
        # إنشاء Client object محدث
        updated_client_data = created_client.model_copy(update={"phone": "987654321"})
        updated_client = repo.update_client(created_client.id, updated_client_data)
        if updated_client:
            print(f"✅ تم تعديل العميل: {updated_client.name}")
        else:
            print("❌ فشل تعديل العميل: returned None")
            return False
    except Exception as e:
        print(f"❌ فشل تعديل العميل: {e}")
        return False
    
    # اختبار 3: حذف العميل
    print("\n🧪 اختبار 3: حذف العميل...")
    try:
        success = repo.delete_client_permanently(created_client.id)
        if success:
            print("✅ تم حذف العميل")
        else:
            print("❌ فشل حذف العميل")
            return False
    except Exception as e:
        print(f"❌ خطأ في حذف العميل: {e}")
        return False
    
    # فحص الإشارات المستلمة
    print(f"\n📊 الإشارات المستلمة: {signals_received}")
    
    expected_signals = ['clients', 'clients', 'clients']  # create, update, delete
    if len(signals_received) >= 3:
        print("✅ جميع الإشارات تعمل بشكل صحيح!")
        return True
    else:
        print(f"❌ الإشارات لا تعمل! متوقع: {expected_signals}, مستلم: {signals_received}")
        return False

def test_repository_methods():
    """اختبار طرق Repository"""
    print("\n🔍 اختبار طرق Repository...")
    
    repo = Repository()
    
    # فحص وجود الطرق المطلوبة (الأسماء الصحيحة)
    required_methods = [
        'create_client', 'update_client', 'delete_client_permanently',
        'create_project', 'update_project', 'delete_project',  # delete_project بدلاً من delete_project_permanently
        'create_payment', 'update_payment', 'delete_payment',  # delete_payment بدلاً من delete_payment_permanently
        'create_expense', 'update_expense', 'delete_expense',  # delete_expense بدلاً من delete_expense_permanently
        'create_service', 'update_service', 'delete_service_permanently'
    ]
    
    missing_methods = []
    for method_name in required_methods:
        if not hasattr(repo, method_name):
            missing_methods.append(method_name)
    
    if missing_methods:
        print(f"❌ طرق مفقودة في Repository: {missing_methods}")
        return False
    else:
        print("✅ جميع الطرق المطلوبة موجودة في Repository")
        return True

def test_signal_emission():
    """اختبار إرسال الإشارات مباشرة"""
    print("\n🔍 اختبار إرسال الإشارات مباشرة...")
    
    repo = Repository()
    
    signals_received = []
    
    def signal_handler(table_name):
        signals_received.append(table_name)
        print(f"📡 إشارة مستلمة: {table_name}")
    
    repo.data_changed_signal.connect(signal_handler)
    
    # إرسال إشارة مباشرة
    print("📤 إرسال إشارة اختبار...")
    repo.data_changed_signal.emit('test_table')
    
    if 'test_table' in signals_received:
        print("✅ إرسال الإشارات يعمل بشكل صحيح!")
        return True
    else:
        print("❌ إرسال الإشارات لا يعمل!")
        return False

if __name__ == "__main__":
    print("🚀 بدء اختبار تشخيص التحديث الفوري...")
    
    # اختبار 1: فحص طرق Repository
    test1_passed = test_repository_methods()
    
    # اختبار 2: فحص إرسال الإشارات
    test2_passed = test_signal_emission()
    
    # اختبار 3: فحص عمل الإشارات مع العمليات الفعلية
    test3_passed = test_signals_working()
    
    print("\n" + "="*50)
    print("📋 ملخص النتائج:")
    print(f"   طرق Repository: {'✅ يعمل' if test1_passed else '❌ لا يعمل'}")
    print(f"   إرسال الإشارات: {'✅ يعمل' if test2_passed else '❌ لا يعمل'}")
    print(f"   العمليات + الإشارات: {'✅ يعمل' if test3_passed else '❌ لا يعمل'}")
    
    if all([test1_passed, test2_passed, test3_passed]):
        print("\n🎉 جميع الاختبارات نجحت! النظام يعمل بشكل صحيح.")
    else:
        print("\n⚠️ هناك مشاكل في النظام تحتاج إصلاح.")