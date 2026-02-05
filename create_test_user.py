import hashlib
import sqlite3

# الاتصال بقاعدة البيانات
conn = sqlite3.connect("skywave_local.db")
cursor = conn.cursor()

USERNAME = "test"
PASSWORD = "test"
PASSWORD_HASH = hashlib.sha256(PASSWORD.encode()).hexdigest()

# حذف المستخدم إذا كان موجوداً
cursor.execute("DELETE FROM users WHERE username = ?", (USERNAME,))

# إضافة المستخدم الجديد
cursor.execute(
    """
    INSERT INTO users (username, password_hash, role, full_name, email, is_active, created_at, last_modified)
    VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
""",
    (USERNAME, PASSWORD_HASH, "admin", "مستخدم تجريبي", "test@test.com", 1),
)

conn.commit()

print("✅ تم إنشاء المستخدم التجريبي:")
print(f"   Username: {USERNAME}")
print(f"   Password: {PASSWORD}")
print("   Role: admin")

# عرض جميع المستخدمين
cursor.execute("SELECT username, role, is_active FROM users")
users = cursor.fetchall()

print("\n=== جميع المستخدمين ===")
for u in users:
    status_label = "✅ نشط" if u[2] else "❌ معطل"
    print(f"  - {u[0]} ({u[1]}) {status_label}")

conn.close()
