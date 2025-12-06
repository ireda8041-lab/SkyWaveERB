"""
سكريبت تشخيص القيود المحاسبية
"""
import sqlite3
import os

# مسار قاعدة البيانات في AppData
app_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SkyWaveERP')
db_path = os.path.join(app_data_dir, "skywave_local.db")

print(f"📁 مسار قاعدة البيانات: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# التحقق من وجود جدول القيود
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print(f"\n📋 الجداول الموجودة: {tables}")

# عدد القيود
if 'journal_entries' in tables:
    cursor.execute("SELECT COUNT(*) FROM journal_entries")
    total = cursor.fetchone()[0]
    print(f"\n📊 إجمالي القيود المحاسبية: {total}")
    
    if total > 0:
        cursor.execute("SELECT * FROM journal_entries LIMIT 5")
        entries = cursor.fetchall()
        print("\n📄 أول 5 قيود:")
        for e in entries:
            print(f"   {e}")
else:
    print("\n❌ جدول journal_entries غير موجود!")

# عدد المشاريع
if 'projects' in tables:
    cursor.execute("SELECT COUNT(*) FROM projects")
    total = cursor.fetchone()[0]
    print(f"\n📊 إجمالي المشاريع: {total}")

# عدد العملاء
if 'clients' in tables:
    cursor.execute("SELECT COUNT(*) FROM clients")
    total = cursor.fetchone()[0]
    print(f"\n📊 إجمالي العملاء: {total}")

# عدد الدفعات
if 'payments' in tables:
    cursor.execute("SELECT COUNT(*) FROM payments")
    total = cursor.fetchone()[0]
    print(f"\n📊 إجمالي الدفعات: {total}")

# عدد المصروفات
if 'expenses' in tables:
    cursor.execute("SELECT COUNT(*) FROM expenses")
    total = cursor.fetchone()[0]
    print(f"\n📊 إجمالي المصروفات: {total}")

conn.close()
