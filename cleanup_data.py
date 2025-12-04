"""
سكريبت تنظيف البيانات المكررة وإصلاح ربط الحسابات
Sky Wave ERP
"""

import sqlite3
import json
from datetime import datetime

LOCAL_DB_FILE = "skywave_local.db"

def cleanup_duplicate_clients(conn, cursor):
    """تنظيف العملاء المكررين"""
    print("\n👥 جاري تنظيف العملاء المكررين...")
    result = {"found": 0, "removed": 0}
    
    try:
        cursor.execute("""
            SELECT id, name, phone, created_at 
            FROM clients 
            WHERE status != 'مؤرشف'
            ORDER BY created_at ASC
        """)
        rows = cursor.fetchall()
        
        seen_names = {}
        seen_phones = {}
        duplicates = []
        
        for row in rows:
            client_id, name, phone, created_at = row
            name_lower = name.strip().lower() if name else ""
            phone_clean = phone.strip().replace(" ", "").replace("-", "") if phone else None
            
            is_duplicate = False
            reason = ""
            
            if name_lower and name_lower in seen_names:
                is_duplicate = True
                reason = f"اسم مكرر: {name}"
            elif name_lower:
                seen_names[name_lower] = client_id
            
            if not is_duplicate and phone_clean and phone_clean in seen_phones:
                is_duplicate = True
                reason = f"هاتف مكرر: {phone}"
            elif phone_clean:
                seen_phones[phone_clean] = client_id
            
            if is_duplicate:
                duplicates.append((client_id, reason))
                result["found"] += 1
        
        for client_id, reason in duplicates:
            cursor.execute(
                "UPDATE clients SET status = 'مؤرشف' WHERE id = ?",
                (client_id,)
            )
            result["removed"] += 1
            print(f"   ✅ أرشفة العميل ID: {client_id} - {reason}")
        
        conn.commit()
        print(f"   📊 تم العثور على {result['found']} مكرر، تم أرشفة {result['removed']}")
        
    except Exception as e:
        print(f"   ❌ خطأ: {e}")
    
    return result

def cleanup_duplicate_projects(conn, cursor):
    """تنظيف المشاريع المكررة"""
    print("\n📁 جاري تنظيف المشاريع المكررة...")
    result = {"found": 0, "removed": 0}
    
    try:
        cursor.execute("""
            SELECT id, name, client_id, created_at 
            FROM projects 
            WHERE status != 'مؤرشف'
            ORDER BY created_at ASC
        """)
        rows = cursor.fetchall()
        
        seen_projects = {}
        duplicates = []
        
        for row in rows:
            project_id, name, client_id, created_at = row
            key = (name.strip().lower() if name else "", client_id or "")
            
            if key in seen_projects:
                duplicates.append((project_id, f"مشروع مكرر: {name}"))
                result["found"] += 1
            else:
                seen_projects[key] = project_id
        
        for project_id, reason in duplicates:
            cursor.execute(
                "UPDATE projects SET status = 'مؤرشف' WHERE id = ?",
                (project_id,)
            )
            result["removed"] += 1
            print(f"   ✅ أرشفة المشروع ID: {project_id} - {reason}")
        
        conn.commit()
        print(f"   📊 تم العثور على {result['found']} مكرر، تم أرشفة {result['removed']}")
        
    except Exception as e:
        print(f"   ❌ خطأ: {e}")
    
    return result

def cleanup_duplicate_payments(conn, cursor):
    """تنظيف الدفعات المكررة"""
    print("\n💰 جاري تنظيف الدفعات المكررة...")
    result = {"found": 0, "removed": 0}
    
    try:
        cursor.execute("""
            SELECT id, project_id, date, amount, created_at 
            FROM payments 
            ORDER BY created_at ASC
        """)
        rows = cursor.fetchall()
        
        seen_payments = {}
        duplicates = []
        
        for row in rows:
            payment_id, project_id, date_str, amount, created_at = row
            date_short = str(date_str)[:10] if date_str else ""
            key = (project_id or "", date_short, amount or 0)
            
            if key in seen_payments:
                duplicates.append((payment_id, f"دفعة مكررة: {amount} في {date_short}"))
                result["found"] += 1
            else:
                seen_payments[key] = payment_id
        
        for payment_id, reason in duplicates:
            cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
            result["removed"] += 1
            print(f"   ✅ حذف الدفعة ID: {payment_id} - {reason}")
        
        conn.commit()
        print(f"   📊 تم العثور على {result['found']} مكررة، تم حذف {result['removed']}")
        
    except Exception as e:
        print(f"   ❌ خطأ: {e}")
    
    return result

def fix_account_hierarchy(conn, cursor):
    """إصلاح العلاقات الهرمية للحسابات"""
    print("\n📒 جاري إصلاح ربط الحسابات...")
    result = {"fixed": 0, "errors": 0}
    
    try:
        cursor.execute("SELECT id, code, name, parent_id FROM accounts ORDER BY code")
        rows = cursor.fetchall()
        
        accounts_by_code = {}
        for row in rows:
            acc_id, code, name, parent_id = row
            accounts_by_code[code] = {"id": acc_id, "name": name, "parent_id": parent_id}
        
        for code, account in accounts_by_code.items():
            if len(code) >= 4:
                # تحديد الأب المنطقي
                if len(code) == 4:
                    parent_code = code[0] + "000"
                elif len(code) == 5:
                    parent_code = code[:4]
                else:
                    parent_code = code[:4]
                
                # التحقق من وجود الأب
                if parent_code in accounts_by_code and parent_code != code:
                    current_parent = account.get("parent_id")
                    if current_parent != parent_code:
                        cursor.execute(
                            "UPDATE accounts SET parent_id = ? WHERE code = ?",
                            (parent_code, code)
                        )
                        result["fixed"] += 1
                        print(f"   ✅ ربط {code} ({account['name']}) -> {parent_code}")
        
        # تحديث is_group
        cursor.execute("UPDATE accounts SET is_group = 0")
        cursor.execute("""
            UPDATE accounts SET is_group = 1 
            WHERE code IN (
                SELECT DISTINCT parent_id FROM accounts 
                WHERE parent_id IS NOT NULL AND parent_id != ''
            )
        """)
        
        conn.commit()
        print(f"   📊 تم إصلاح {result['fixed']} حساب")
        
    except Exception as e:
        print(f"   ❌ خطأ: {e}")
        result["errors"] += 1
    
    return result

def main():
    print("=" * 70)
    print("🧹 Sky Wave ERP - تنظيف البيانات المكررة")
    print("=" * 70)
    
    # الاتصال بقاعدة البيانات
    print("\n📡 جاري الاتصال بقاعدة البيانات...")
    conn = sqlite3.connect(LOCAL_DB_FILE)
    cursor = conn.cursor()
    print(f"✅ متصل بـ {LOCAL_DB_FILE}")
    
    # تشغيل التنظيف
    results = {}
    results['clients'] = cleanup_duplicate_clients(conn, cursor)
    results['projects'] = cleanup_duplicate_projects(conn, cursor)
    results['payments'] = cleanup_duplicate_payments(conn, cursor)
    results['accounts'] = fix_account_hierarchy(conn, cursor)
    
    # إغلاق الاتصال
    conn.close()
    
    # عرض الملخص
    print("\n" + "=" * 70)
    print("📊 ملخص التنظيف:")
    print("=" * 70)
    
    total_found = (
        results['clients'].get('found', 0) + 
        results['projects'].get('found', 0) + 
        results['payments'].get('found', 0)
    )
    total_fixed = (
        results['clients'].get('removed', 0) + 
        results['projects'].get('removed', 0) + 
        results['payments'].get('removed', 0) +
        results['accounts'].get('fixed', 0)
    )
    
    print(f"\n   إجمالي التكرارات: {total_found}")
    print(f"   إجمالي الإصلاحات: {total_fixed}")
    
    print("\n" + "=" * 70)
    print("✅ انتهى التنظيف!")
    print("=" * 70)

if __name__ == "__main__":
    main()
