"""
إصلاح شامل ونهائي لمشاكل:
1. أرقام الفواتير الفارغة
2. الخدمات المكررة
"""
import os
import sqlite3
from datetime import datetime

db_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'SkyWaveERP', 'skywave_local.db')
print(f"📂 قاعدة البيانات: {db_path}")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("\n" + "="*60)
print("🔧 إصلاح شامل لقاعدة البيانات")
print("="*60)

# === 1. إنشاء جدول invoice_numbers إذا لم يكن موجوداً ===
print("\n📋 1. التأكد من وجود جدول invoice_numbers...")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoice_numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT UNIQUE NOT NULL,
        invoice_number TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()
print("   ✅ الجدول موجود")

# === 2. حذف الخدمات المكررة ===
print("\n🗑️ 2. حذف الخدمات المكررة...")
cursor.execute("SELECT COUNT(*) FROM services")
before_count = cursor.fetchone()[0]

cursor.execute('''
    DELETE FROM services
    WHERE id NOT IN (
        SELECT MIN(id) FROM services GROUP BY name
    )
''')
deleted = cursor.rowcount
conn.commit()

cursor.execute("SELECT COUNT(*) FROM services")
after_count = cursor.fetchone()[0]
print(f"   قبل: {before_count} خدمة")
print(f"   بعد: {after_count} خدمة")
print(f"   ✅ تم حذف {deleted} خدمة مكررة")

# === 3. إنشاء أرقام فواتير لكل المشاريع ===
print("\n🔢 3. إنشاء أرقام فواتير ثابتة لكل المشاريع...")

# جلب كل المشاريع
cursor.execute("SELECT id, name FROM projects ORDER BY id")
projects = cursor.fetchall()

# جلب أعلى رقم تسلسلي موجود
cursor.execute("SELECT MAX(CAST(SUBSTR(invoice_number, 4) AS INTEGER)) FROM invoice_numbers")
max_num_row = cursor.fetchone()[0]
next_num = (max_num_row or 97161) + 1 if max_num_row and max_num_row > 97161 else 97162

for proj in projects:
    proj_id = proj['id']
    proj_name = proj['name']

    # تحقق من وجود رقم فاتورة محفوظ
    cursor.execute("SELECT invoice_number FROM invoice_numbers WHERE project_name = ?", (proj_name,))
    existing = cursor.fetchone()

    if existing:
        invoice_number = existing['invoice_number']
    else:
        # إنشاء رقم جديد
        invoice_number = f"SW-{next_num}"
        cursor.execute(
            "INSERT INTO invoice_numbers (project_name, invoice_number, created_at) VALUES (?, ?, ?)",
            (proj_name, invoice_number, datetime.now().isoformat())
        )
        next_num += 1

    # تحديث المشروع برقم الفاتورة
    cursor.execute("UPDATE projects SET invoice_number = ? WHERE id = ?", (invoice_number, proj_id))
    print(f"   {proj_name}: {invoice_number}")

conn.commit()

# === 4. التحقق النهائي ===
print("\n✅ 4. التحقق النهائي...")
cursor.execute("SELECT name, invoice_number FROM projects ORDER BY id")
for row in cursor.fetchall():
    status = "✅" if row['invoice_number'] else "❌"
    print(f"   {status} {row['name']}: {row['invoice_number'] or 'فارغ!'}")

cursor.execute("SELECT COUNT(*) FROM services")
print(f"\n📊 عدد الخدمات: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM projects")
print(f"📊 عدد المشاريع: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM invoice_numbers")
print(f"📊 عدد أرقام الفواتير المحفوظة: {cursor.fetchone()[0]}")

conn.close()
print("\n" + "="*60)
print("🎉 تم الإصلاح بنجاح!")
print("="*60)
