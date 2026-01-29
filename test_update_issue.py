#!/usr/bin/env python3
"""
اختبار مشكلة عدم حفظ التعديلات
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.repository import Repository
from services.client_service import ClientService
from core import schemas
from datetime import datetime
import random

def test_update_flow():
    """اختبار تدفق التحديث الكامل"""
    print("🔍 اختبار تدفق التحديث الكامل...")
    
    # إنشاء Repository و ClientService
    repo = Repository()
    client_service = ClientService(repo)
    
    # 1. إنشاء عميل جديد
    print("\n📝 الخطوة 1: إنشاء عميل جديد...")
    random_phone = f"123{random.randint(1000000, 9999999)}"
    test_client = schemas.Client(
        name=f"عميل اختبار {datetime.now().strftime('%H:%M:%S')}",
        email=f"test{random.randint(1000, 9999)}@example.com",
        phone=random_phone,
        company_name="شركة اختبار"
    )
    
    try:
        created_client = client_service.create_client(test_client)
        print(f"✅ تم إنشاء العميل: {created_client.name}")
        print(f"   ID: {created_client.id}")
        print(f"   Phone: {created_client.phone}")
        print(f"   Company: {created_client.company_name}")
    except Exception as e:
        print(f"❌ فشل إنشاء العميل: {e}")
        return False
    
    # 2. قراءة العميل من قاعدة البيانات للتأكد
    print(f"\n📖 الخطوة 2: قراءة العميل من قاعدة البيانات...")
    fetched_client = client_service.get_client_by_id(str(created_client.id))
    if fetched_client:
        print(f"✅ تم جلب العميل من قاعدة البيانات")
        print(f"   Name: {fetched_client.name}")
        print(f"   Phone: {fetched_client.phone}")
        print(f"   Company: {fetched_client.company_name}")
    else:
        print("❌ فشل جلب العميل من قاعدة البيانات!")
        return False
    
    # 3. تعديل العميل باستخدام ClientService (كما تفعل الواجهة)
    print(f"\n✏️ الخطوة 3: تعديل العميل...")
    new_data = {
        "phone": "999888777",
        "company_name": "شركة محدثة",
        "email": "updated@example.com"
    }
    
    try:
        updated_client = client_service.update_client(str(created_client.id), new_data)
        if updated_client:
            print(f"✅ ClientService.update_client نجح")
            print(f"   Phone: {updated_client.phone}")
            print(f"   Company: {updated_client.company_name}")
            print(f"   Email: {updated_client.email}")
        else:
            print("❌ ClientService.update_client أرجع None!")
            return False
    except Exception as e:
        print(f"❌ فشل تعديل العميل: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. قراءة العميل مرة أخرى للتأكد من حفظ التعديلات
    print(f"\n🔍 الخطوة 4: التحقق من حفظ التعديلات في قاعدة البيانات...")
    fetched_after_update = client_service.get_client_by_id(str(created_client.id))
    
    if fetched_after_update:
        print(f"✅ تم جلب العميل بعد التعديل")
        print(f"   Phone: {fetched_after_update.phone}")
        print(f"   Company: {fetched_after_update.company_name}")
        print(f"   Email: {fetched_after_update.email}")
        
        # التحقق من التعديلات
        if fetched_after_update.phone == "999888777":
            print("✅ تم حفظ تعديل الهاتف بنجاح!")
        else:
            print(f"❌ الهاتف لم يتم تحديثه! القيمة: {fetched_after_update.phone}")
            return False
            
        if fetched_after_update.company_name == "شركة محدثة":
            print("✅ تم حفظ تعديل اسم الشركة بنجاح!")
        else:
            print(f"❌ اسم الشركة لم يتم تحديثه! القيمة: {fetched_after_update.company_name}")
            return False
            
        if fetched_after_update.email == "updated@example.com":
            print("✅ تم حفظ تعديل البريد الإلكتروني بنجاح!")
        else:
            print(f"❌ البريد الإلكتروني لم يتم تحديثه! القيمة: {fetched_after_update.email}")
            return False
    else:
        print("❌ فشل جلب العميل بعد التعديل!")
        return False
    
    # 5. حذف العميل للتنظيف
    print(f"\n🗑️ الخطوة 5: حذف العميل...")
    try:
        success = client_service.delete_client(str(created_client.id))
        if success:
            print("✅ تم حذف العميل بنجاح")
        else:
            print("⚠️ فشل حذف العميل")
    except Exception as e:
        print(f"⚠️ خطأ في حذف العميل: {e}")
    
    return True

if __name__ == "__main__":
    print("🚀 بدء اختبار مشكلة عدم حفظ التعديلات...")
    print("="*60)
    
    success = test_update_flow()
    
    print("\n" + "="*60)
    if success:
        print("🎉 جميع الاختبارات نجحت! التعديلات تُحفظ بشكل صحيح.")
    else:
        print("❌ فشل الاختبار! التعديلات لا تُحفظ بشكل صحيح.")
