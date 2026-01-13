#!/usr/bin/env python
"""
سكريبت لإعادة حساب أرصدة الحسابات من الدفعات والمصروفات
"""
import os
import sys

# إضافة المسار الحالي
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_balances():
    """إعادة حساب أرصدة الحسابات"""
    print("=" * 60)
    print("🔄 إعادة حساب أرصدة الحسابات...")
    print("=" * 60)
    
    from core.repository import Repository
    
    repo = Repository()
    
    # 1. جلب جميع الحسابات
    accounts = repo.get_all_accounts()
    print(f"📊 عدد الحسابات: {len(accounts)}")
    
    # 2. جلب جميع الدفعات
    payments = repo.get_all_payments()
    print(f"💰 عدد الدفعات: {len(payments)}")
    
    # 3. جلب جميع المصروفات
    expenses = repo.get_all_expenses()
    print(f"📤 عدد المصروفات: {len(expenses)}")
    
    # 4. حساب الأرصدة لكل حساب
    account_balances = {}
    
    # حساب الدفعات (تزيد الرصيد)
    for payment in payments:
        acc_code = payment.account_id
        if acc_code:
            if acc_code not in account_balances:
                account_balances[acc_code] = 0.0
            account_balances[acc_code] += payment.amount
            print(f"  + دفعة: {payment.amount} -> {acc_code}")
    
    # حساب المصروفات (تنقص الرصيد)
    for expense in expenses:
        acc_code = getattr(expense, 'payment_account_id', None) or getattr(expense, 'account_id', None)
        if acc_code:
            if acc_code not in account_balances:
                account_balances[acc_code] = 0.0
            account_balances[acc_code] -= expense.amount
            print(f"  - مصروف: {expense.amount} -> {acc_code}")
    
    print("\n" + "=" * 60)
    print("📊 الأرصدة المحسوبة:")
    print("=" * 60)
    
    for code, balance in account_balances.items():
        print(f"  {code}: {balance:,.2f}")
    
    # 5. تحديث الأرصدة في قاعدة البيانات
    print("\n" + "=" * 60)
    print("💾 تحديث الأرصدة في قاعدة البيانات...")
    print("=" * 60)
    
    for acc in accounts:
        if acc.code in account_balances:
            new_balance = account_balances[acc.code]
            print(f"  تحديث {acc.code} ({acc.name}): {acc.balance} -> {new_balance}")
            # تحديث مباشر في SQLite
            try:
                repo.sqlite_cursor.execute(
                    "UPDATE accounts SET balance = ? WHERE code = ?",
                    (new_balance, acc.code)
                )
                repo.sqlite_conn.commit()
                print(f"    ✅ تم التحديث في SQLite")
            except Exception as e:
                print(f"    ❌ خطأ: {e}")
    
    # 6. تحديث أرصدة الحسابات الأب
    print("\n" + "=" * 60)
    print("🔄 تحديث أرصدة الحسابات الأب...")
    print("=" * 60)
    
    # إعادة جلب الحسابات بعد التحديث
    accounts = repo.get_all_accounts()
    
    # البحث عن الحسابات الأب وتحديثها
    parent_codes = set()
    for acc in accounts:
        if acc.parent_code:
            parent_codes.add(acc.parent_code)
    
    for parent_code in parent_codes:
        parent_acc = next((a for a in accounts if a.code == parent_code), None)
        if parent_acc:
            # حساب مجموع أرصدة الأبناء
            children = [a for a in accounts if a.parent_code == parent_code]
            total = sum(a.balance or 0 for a in children)
            # إضافة الرصيد المحسوب من الدفعات
            if parent_code in account_balances:
                total = account_balances[parent_code]
            else:
                # حساب من الأبناء
                for child in children:
                    if child.code in account_balances:
                        total = account_balances.get(child.code, 0)
                        break
            
            print(f"  تحديث الأب {parent_code} ({parent_acc.name}): {parent_acc.balance} -> {total}")
            try:
                repo.sqlite_cursor.execute(
                    "UPDATE accounts SET balance = ? WHERE code = ?",
                    (total, parent_code)
                )
                repo.sqlite_conn.commit()
                print(f"    ✅ تم التحديث في SQLite")
            except Exception as e:
                print(f"    ❌ خطأ: {e}")
    
    # 7. مزامنة مع MongoDB
    print("\n" + "=" * 60)
    print("☁️ مزامنة مع MongoDB...")
    print("=" * 60)
    
    if repo.online and repo.mongo_db:
        try:
            # تحديث الحسابات في MongoDB
            accounts_collection = repo.mongo_db['accounts']
            for code, balance in account_balances.items():
                result = accounts_collection.update_one(
                    {"code": code},
                    {"$set": {"balance": balance}}
                )
                if result.modified_count > 0:
                    print(f"  ✅ تم تحديث {code} في MongoDB")
            
            # تحديث الحسابات الأب
            for parent_code in parent_codes:
                children = [a for a in accounts if a.parent_code == parent_code]
                total = sum(account_balances.get(c.code, c.balance or 0) for c in children)
                result = accounts_collection.update_one(
                    {"code": parent_code},
                    {"$set": {"balance": total}}
                )
                if result.modified_count > 0:
                    print(f"  ✅ تم تحديث الأب {parent_code} في MongoDB")
                    
            print("✅ تمت المزامنة مع MongoDB")
        except Exception as e:
            print(f"❌ خطأ في المزامنة: {e}")
    else:
        print("⚠️ غير متصل بـ MongoDB")
    
    # 7. مزامنة مع MongoDB
    print("\n" + "=" * 60)
    print("☁️ مزامنة مع MongoDB...")
    print("=" * 60)
    
    if repo.online:
        try:
            # إعادة جلب الحسابات المحدثة
            accounts = repo.get_all_accounts()
            for acc in accounts:
                if acc.code in account_balances or acc.code in parent_codes:
                    # تحديث في MongoDB
                    mongo_id = getattr(acc, '_mongo_id', None)
                    if mongo_id and repo.mongo_db:
                        repo.mongo_db.accounts.update_one(
                            {'_id': mongo_id},
                            {'$set': {'balance': acc.balance}}
                        )
                        print(f"  ☁️ تحديث MongoDB: {acc.code} = {acc.balance}")
            print("✅ تم المزامنة مع MongoDB")
        except Exception as e:
            print(f"⚠️ فشل المزامنة مع MongoDB: {e}")
    else:
        print("⚠️ غير متصل بـ MongoDB")
    
    print("\n" + "=" * 60)
    print("✅ تم إعادة حساب الأرصدة بنجاح!")
    print("=" * 60)

if __name__ == "__main__":
    fix_balances()
