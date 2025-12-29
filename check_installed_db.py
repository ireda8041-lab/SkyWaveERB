import sqlite3

# قاعدة بيانات البرنامج المثبت
DB_PATH = r"D:\Sky Wave ERP\_internal\skywave_local.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=" * 60)
print(f"فحص قاعدة البيانات: {DB_PATH}")
print("=" * 60)

# العملاء اللي عندهم logo_data
c.execute("""
    SELECT name, length(logo_data) as logo_len 
    FROM clients 
    WHERE logo_data IS NOT NULL AND logo_data != ''
    ORDER BY logo_len DESC
    LIMIT 10
""")
with_data = c.fetchall()
print(f"\n📷 عملاء لديهم logo_data: {len(with_data)}")
for r in with_data:
    print(f"   ✅ {r['name']}: {r['logo_len']} حرف")

# إجمالي
c.execute("SELECT COUNT(*) FROM clients")
total = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM clients WHERE logo_data IS NOT NULL AND logo_data != ''")
with_logo = c.fetchone()[0]

print(f"\n📊 الإجمالي: {with_logo}/{total} عميل لديه صورة")

# فحص عميل ccc
print("\n" + "-" * 60)
c.execute("SELECT name, length(logo_data) as logo_len FROM clients WHERE name LIKE '%ccc%'")
ccc = c.fetchone()
if ccc:
    print(f"✅ عميل ccc: logo_data = {ccc['logo_len']} حرف")
else:
    print("❌ عميل ccc غير موجود")

conn.close()
