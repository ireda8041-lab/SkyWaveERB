import sqlite3
import os

# البحث عن قاعدة البيانات
paths = [
    r'D:\Sky Wave ERP\_internal\skywave_local.db',
    r'D:\Sky Wave ERP\skywave_local.db',
    os.path.expanduser(r'~\AppData\Local\SkyWaveERP\skywave_local.db'),
]

db_path = None
for p in paths:
    if os.path.exists(p):
        db_path = p
        break

if not db_path:
    print("لم يتم العثور على قاعدة البيانات!")
    exit()

print(f"قاعدة البيانات: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# عرض الجداول
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"الجداول: {[t[0] for t in tables]}")

# البحث عن جدول العملاء
for table in ['clients', 'client', 'customers', 'customer']:
    try:
        cursor.execute(f"SELECT name, LENGTH(logo_data) as logo_size FROM {table} WHERE logo_data IS NOT NULL AND logo_data != ''")
        rows = cursor.fetchall()
        print(f'\nالعملاء اللي عندهم صور:')
        for name, size in rows:
            print(f'  - {name}: {size} حرف')
        print(f'\nالمجموع: {len(rows)} عميل')
        break
    except:
        continue

conn.close()
