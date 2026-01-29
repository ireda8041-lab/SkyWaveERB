import hashlib
import sqlite3

# الاتصال بقاعدة البيانات
conn = sqlite3.connect('skywave_local.db')
cursor = conn.cursor()

# إنشاء مستخدم تجريبي
username = "test"
password = "test"
password_hash = hashlib.sha256(password.encode()).hexdigest()

# حذف المستخدم إذا كان موجوداً
cursor.execute("DELETE FROM users WHERE username = ?", (username,))

# إضافة المستخدم الجديد
cursor.execute("""
    INSERT INTO users (username, password_hash, role, full_name, email, is_active, created_at, last_modified)
    VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
""", (username, password_hash, 'admin', 'مستخدم تجريبي', 'test@test.com', 1))

conn.commit()

print(f"✅ تم إنشاء المستخدم التجريبي:")
print(f"   Username: {username}")
print(f"   Password: {password}")
print(f"   Role: admin")

# عرض جميع المستخدمين
cursor.execute("SELECT username, role, is_active FROM users")
users = cursor.fetchall()

print("\n=== جميع المستخدمين ===")
for u in users:
    status = "✅ نشط" if u[2] else "❌ معطل"
    print(f"  - {u[0]} ({u[1]}) {status}")

conn.close()
