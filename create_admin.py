"""
إنشاء مستخدم admin افتراضي
✅ FIXED: Now uses AuthService for proper password hashing
"""

import sqlite3

from core.auth_models import AuthService
from core.repository import Repository

DB_PATH = "skywave_local.db"


def create_admin():
    """إنشاء مستخدم admin"""
    # Initialize Repository and AuthService
    repo = Repository()
    auth_service = AuthService(repo)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # التحقق من وجود مستخدمين
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    print(f"عدد المستخدمين الحاليين: {count}")

    # التحقق من وجود admin
    cursor.execute("SELECT username FROM users WHERE username = 'admin'")
    admin_exists = cursor.fetchone()

    if admin_exists:
        print("⚠️ المستخدم admin موجود بالفعل!")
        print("كلمة المرور الافتراضية: admin123")
    else:
        # إنشاء admin جديد باستخدام AuthService
        from datetime import datetime

        # Use AuthService.hash_password() for correct format
        password_hash = auth_service.hash_password("admin123")

        admin_data = {
            "username": "admin",
            "password_hash": password_hash,
            "role": "admin",
            "full_name": "المدير العام",
            "email": "admin@skywave.com",
            "is_active": 1,
            "created_at": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "sync_status": "new_offline",
        }

        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role, full_name, email,
                             is_active, created_at, last_modified, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                admin_data["username"],
                admin_data["password_hash"],
                admin_data["role"],
                admin_data["full_name"],
                admin_data["email"],
                admin_data["is_active"],
                admin_data["created_at"],
                admin_data["last_modified"],
                admin_data["sync_status"],
            ),
        )

        conn.commit()
        print("✅ تم إنشاء المستخدم admin بنجاح!")
        print("=" * 50)
        print("بيانات الدخول:")
        print("  اسم المستخدم: admin")
        print("  كلمة المرور: admin123")
        print("=" * 50)

    # عرض كل المستخدمين
    cursor.execute("SELECT username, role, full_name FROM users")
    users = cursor.fetchall()
    print("\nالمستخدمين المتاحين:")
    for user in users:
        print(f"  - {user[0]} ({user[1]}) - {user[2]}")

    conn.close()


if __name__ == "__main__":
    try:
        create_admin()
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback

        traceback.print_exc()
