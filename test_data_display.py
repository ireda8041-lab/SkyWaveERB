#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبار عرض البيانات في الواجهة
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.repository import Repository
from services.project_service import ProjectService
from services.client_service import ClientService

try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


def test_users_display():
    """اختبار عرض المستخدمين"""
    safe_print("\n" + "="*60)
    safe_print("🧪 اختبار #1: عرض المستخدمين")
    safe_print("="*60)
    
    try:
        repo = Repository()
        users = repo.get_all_users()
        
        safe_print(f"✅ عدد المستخدمين: {len(users)}")
        
        for i, user in enumerate(users, 1):
            safe_print(f"  {i}. {user.username} - {user.full_name} - {user.email or 'بدون بريد'}")
        
        repo.close()
        return len(users) > 0
        
    except Exception as e:
        safe_print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_payments_display():
    """اختبار عرض الدفعات"""
    safe_print("\n" + "="*60)
    safe_print("🧪 اختبار #2: عرض الدفعات")
    safe_print("="*60)
    
    try:
        repo = Repository()
        
        # جلب الدفعات مباشرة من قاعدة البيانات
        cursor = repo.get_cursor()
        cursor.execute("SELECT * FROM payments LIMIT 10")
        payments = cursor.fetchall()
        
        safe_print(f"✅ عدد الدفعات: {len(payments)}")
        
        for i, payment in enumerate(payments, 1):
            safe_print(f"  {i}. {payment['amount']} ج.م - {payment['date']} - مشروع: {payment['project_id']}")
        
        cursor.close()
        repo.close()
        return len(payments) > 0
        
    except Exception as e:
        safe_print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_expenses_display():
    """اختبار عرض المصروفات"""
    safe_print("\n" + "="*60)
    safe_print("🧪 اختبار #3: عرض المصروفات")
    safe_print("="*60)
    
    try:
        repo = Repository()
        
        # جلب المصروفات مباشرة من قاعدة البيانات
        cursor = repo.get_cursor()
        cursor.execute("SELECT * FROM expenses LIMIT 10")
        expenses = cursor.fetchall()
        
        safe_print(f"✅ عدد المصروفات: {len(expenses)}")
        
        for i, expense in enumerate(expenses, 1):
            project_id = expense['project_id'] if 'project_id' in expense.keys() else 'N/A'
            safe_print(f"  {i}. {expense['amount']} ج.م - {expense['description'] or expense['category']} - مشروع: {project_id}")
        
        cursor.close()
        repo.close()
        return len(expenses) > 0
        
    except Exception as e:
        safe_print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vip_clients():
    """اختبار عرض العملاء VIP"""
    safe_print("\n" + "="*60)
    safe_print("🧪 اختبار #4: عرض العملاء VIP")
    safe_print("="*60)
    
    try:
        repo = Repository()
        client_service = ClientService(repo)
        
        # جلب كل العملاء
        clients = client_service.get_all_clients()
        safe_print(f"✅ عدد العملاء: {len(clients)}")
        
        # فلترة VIP
        vip_clients = [c for c in clients if getattr(c, 'is_vip', False)]
        safe_print(f"⭐ عدد العملاء VIP: {len(vip_clients)}")
        
        for i, client in enumerate(vip_clients, 1):
            is_vip = getattr(client, 'is_vip', False)
            safe_print(f"  {i}. {client.name} - VIP: {is_vip}")
        
        repo.close()
        return len(vip_clients) > 0
        
    except Exception as e:
        safe_print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    safe_print("\n" + "🧪"*30)
    safe_print("🧪 اختبار عرض البيانات في الواجهة")
    safe_print("🧪"*30)
    
    results = []
    
    results.append(("المستخدمين", test_users_display()))
    results.append(("الدفعات", test_payments_display()))
    results.append(("المصروفات", test_expenses_display()))
    results.append(("العملاء VIP", test_vip_clients()))
    
    safe_print("\n" + "="*60)
    safe_print("📊 ملخص الاختبارات")
    safe_print("="*60)
    
    for name, success in results:
        status = "✅ نجح" if success else "❌ فشل"
        safe_print(f"{status} - {name}")
    
    all_success = all(result[1] for result in results)
    
    if all_success:
        safe_print("\n✅ جميع البيانات موجودة وتعمل بشكل صحيح!")
        safe_print("💡 المشكلة في الواجهة فقط - تحتاج لإعادة تشغيل البرنامج")
    else:
        safe_print("\n⚠️ بعض البيانات غير موجودة")
    
    return all_success


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n⚠️ تم إيقاف الاختبار")
    except Exception as e:
        safe_print(f"\n❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
