#!/usr/bin/env python3
"""
اختبار التحديث الفوري للواجهة بعد إصلاح Repository Signals
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.repository import Repository
from core import schemas
from core.logger import safe_print
from datetime import datetime

def test_repository_signals():
    """اختبار إرسال الإشارات من Repository"""
    safe_print("🧪 بدء اختبار إشارات Repository...")
    
    # إنشاء Repository
    repo = Repository()
    
    # التحقق من أن Repository هو QObject
    from PyQt6.QtCore import QObject
    if not isinstance(repo, QObject):
        safe_print("❌ Repository ليس QObject!")
        return False
    
    # التحقق من وجود الإشارة
    if not hasattr(repo, 'data_changed_signal'):
        safe_print("❌ Repository لا يحتوي على data_changed_signal!")
        return False
    
    safe_print("✅ Repository هو QObject ويحتوي على data_changed_signal")
    
    # متغير لتتبع الإشارات المستلمة
    received_signals = []
    
    def signal_handler(table_name):
        safe_print(f"📡 استلام إشارة: {table_name}")
        received_signals.append(table_name)
    
    # ربط معالج الإشارة
    repo.data_changed_signal.connect(signal_handler)
    safe_print("✅ تم ربط معالج الإشارة")
    
    return repo, received_signals

def test_client_update_signal():
    """اختبار إشارة تحديث العملاء"""
    safe_print("\n🧪 اختبار إشارة تحديث العملاء...")
    
    repo, received_signals = test_repository_signals()
    if not repo:
        return False
    
    # إنشاء عميل جديد للاختبار
    try:
        client_data = schemas.Client(
            name="عميل اختبار الإشارات",
            company_name="شركة الاختبار",
            email="test@signals.com",
            phone="123456789",
            address="عنوان الاختبار",
            country="مصر",
            status=schemas.ClientStatus.ACTIVE,
            client_type="شركة",
            work_field="تكنولوجيا"
        )
        
        # إضافة العميل
        created_client = repo.create_client(client_data)
        if not created_client:
            safe_print("❌ فشل إنشاء العميل")
            return False
        
        client_id = created_client.id
        safe_print(f"✅ تم إنشاء العميل بـ ID: {client_id}")
        
        # تحديث العميل (هنا يجب أن ترسل الإشارة)
        client_data.name = "عميل اختبار الإشارات - محدث"
        client_data.phone = "987654321"
        
        updated_client = repo.update_client(str(client_id), client_data)
        if not updated_client:
            safe_print("❌ فشل تحديث العميل")
            return False
        
        safe_print("✅ تم تحديث العميل")
        
        # التحقق من استلام الإشارة
        if "clients" in received_signals:
            safe_print("✅ تم استلام إشارة تحديث العملاء!")
        else:
            safe_print("❌ لم يتم استلام إشارة تحديث العملاء!")
            safe_print(f"الإشارات المستلمة: {received_signals}")
            return False
        
        # تنظيف - حذف العميل
        repo.delete_client_permanently(str(client_id))
        
        return True
        
    except Exception as e:
        safe_print(f"❌ خطأ في اختبار تحديث العميل: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_project_update_signal():
    """اختبار إشارة تحديث المشاريع"""
    safe_print("\n🧪 اختبار إشارة تحديث المشاريع...")
    
    repo, received_signals = test_repository_signals()
    if not repo:
        return False
    
    try:
        # إنشاء اسم مشروع فريد
        import random
        project_name = f"مشروع اختبار الإشارات {random.randint(1000, 9999)}"
        
        # إنشاء مشروع للاختبار
        project_data = schemas.Project(
            name=project_name,
            client_id="test_client",
            description="مشروع لاختبار الإشارات",
            status=schemas.ProjectStatus.ACTIVE,
            items=[],
            subtotal=1000.0,
            total_amount=1000.0,
            currency=schemas.CurrencyCode.EGP
        )
        
        # إضافة المشروع
        created_project = repo.create_project(project_data)
        if not created_project:
            safe_print("❌ فشل إنشاء المشروع")
            return False
        
        safe_print(f"✅ تم إنشاء المشروع: {created_project.name}")
        
        # تحديث المشروع (هنا يجب أن ترسل الإشارة)
        project_data.description = "مشروع لاختبار الإشارات - محدث"
        project_data.total_amount = 1500.0
        
        updated_project = repo.update_project(created_project.name, project_data)
        if not updated_project:
            safe_print("❌ فشل تحديث المشروع")
            return False
        
        safe_print("✅ تم تحديث المشروع")
        
        # التحقق من استلام الإشارة
        if "projects" in received_signals:
            safe_print("✅ تم استلام إشارة تحديث المشاريع!")
        else:
            safe_print("❌ لم يتم استلام إشارة تحديث المشاريع!")
            safe_print(f"الإشارات المستلمة: {received_signals}")
            return False
        
        # تنظيف - حذف المشروع
        repo.delete_project(created_project.name)
        
        return True
        
    except Exception as e:
        safe_print(f"❌ خطأ في اختبار تحديث المشروع: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """تشغيل جميع الاختبارات"""
    safe_print("🚀 بدء اختبار التحديث الفوري للواجهة...")
    
    # تهيئة PyQt6 للإشارات
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    tests_passed = 0
    total_tests = 2
    
    # اختبار إشارة تحديث العملاء
    if test_client_update_signal():
        tests_passed += 1
        safe_print("✅ اختبار إشارة العملاء نجح")
    else:
        safe_print("❌ اختبار إشارة العملاء فشل")
    
    # اختبار إشارة تحديث المشاريع
    if test_project_update_signal():
        tests_passed += 1
        safe_print("✅ اختبار إشارة المشاريع نجح")
    else:
        safe_print("❌ اختبار إشارة المشاريع فشل")
    
    # النتيجة النهائية
    safe_print(f"\n📊 النتائج: {tests_passed}/{total_tests} اختبارات نجحت")
    
    if tests_passed == total_tests:
        safe_print("🎉 جميع الاختبارات نجحت! التحديث الفوري للواجهة يعمل بشكل صحيح.")
        return True
    else:
        safe_print("⚠️ بعض الاختبارات فشلت. يحتاج إصلاح إضافي.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)