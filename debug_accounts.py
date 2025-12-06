"""
سكريبت تشخيص مشكلة الحسابات
"""
import sqlite3
import os

# مسار قاعدة البيانات في AppData
app_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SkyWaveERP')
db_path = os.path.join(app_data_dir, "skywave_local.db")

print(f"📁 مسار قاعدة البيانات: {db_path}")
print(f"✅ موجودة: {os.path.exists(db_path)}")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # عدد الحسابات الكلي
    cursor.execute("SELECT COUNT(*) FROM accounts")
    total = cursor.fetchone()[0]
    print(f"\n📊 إجمالي الحسابات: {total}")
    
    # عدد الحسابات حسب sync_status
    cursor.execute("SELECT sync_status, COUNT(*) FROM accounts GROUP BY sync_status")
    statuses = cursor.fetchall()
    print("\n📋 حالة المزامنة:")
    for status, count in statuses:
        print(f"   - {status}: {count}")
    
    # عرض أول 10 حسابات
    cursor.execute("SELECT id, code, name, type, sync_status FROM accounts LIMIT 10")
    accounts = cursor.fetchall()
    print("\n📄 أول 10 حسابات:")
    for acc in accounts:
        print(f"   {acc}")
    
    # التحقق من الحسابات المحذوفة
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE sync_status = 'deleted'")
    deleted = cursor.fetchone()[0]
    print(f"\n🗑️ الحسابات المحذوفة: {deleted}")
    
    # التحقق من الحسابات النشطة
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE sync_status != 'deleted'")
    active = cursor.fetchone()[0]
    print(f"✅ الحسابات النشطة: {active}")
    
    conn.close()
else:
    print("❌ قاعدة البيانات غير موجودة!")
    
    # التحقق من قاعدة البيانات في مجلد البرنامج
    local_db = "skywave_local.db"
    if os.path.exists(local_db):
        print(f"\n📁 قاعدة البيانات موجودة في المجلد الحالي: {local_db}")
        conn = sqlite3.connect(local_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM accounts")
        total = cursor.fetchone()[0]
        print(f"📊 إجمالي الحسابات فيها: {total}")
        conn.close()
