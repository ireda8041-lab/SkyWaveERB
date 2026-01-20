"""
إنشاء المستخدمين الافتراضيين للنظام
✅ يدعم: admin و reda
"""

import sqlite3
from datetime import datetime

from core.auth_models import AuthService
from core.repository import Repository

DB_PATH = "skywave_local.db"


def create_default_users():
    """إنشاء المستخدمين الافتراضيين"""
    # Initialize Repository and AuthService
    repo = Repository()
    auth_service = AuthService(repo)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # التحقق من وجود مستخدمين
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    print(f"عدد المستخدمين الحاليين: {count}")

    # قائمة المستخدمين الافتراضيين
    default_users = [
        {
            "username": "admin",
            "password": "admin123",
            "role": "admin",
            "full_name": "المدير العام",
            "email": "admin@skywave.com"
        },
        {
            "username": "reda",
            "password": "reda123",
            "role": "admin",
            "full_name": "رضا محمد",
            "email": "reda@skywave.com"
        }
    ]

    created_count = 0
    existing_count = 0

    for user_info in default_users:
        # التحقق من وجود المستخدم
        cursor.execute("SELECT username FROM users WHERE username = ?", (user_info["username"],))
        user_exists = cursor.fetchone()

        if user_exists:
            print(f"⚠️ المستخدم {user_info['username']} موجود بالفعل!")
            existing_count += 1
        else:
            # إنشاء مستخدم جديد باستخدام AuthService
            password_hash = auth_service.hash_password(user_info["password"])

            user_data = {
                "username": user_info["username"],
                "password_hash": password_hash,
                "role": user_info["role"],
                "full_name": user_info["full_name"],
                "email": user_info["email"],
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
                    user_data["username"],
                    user_data["password_hash"],
                    user_data["role"],
                    user_data["full_name"],
                    user_data["email"],
                    user_data["is_active"],
                    user_data["created_at"],
                    user_data["last_modified"],
                    user_data["sync_status"],
                ),
            )

            conn.commit()
            print(f"✅ تم إنشاء المستخدم {user_info['username']} بنجاح!")
            print(f"   اسم المستخدم: {user_info['username']}")
            print(f"   كلمة المرور: {user_info['password']}")
            created_count += 1

    print("\n" + "=" * 60)
    print(f"📊 ملخص العملية:")
    print(f"   ✅ تم إنشاء: {created_count} مستخدم")
    print(f"   ⚠️ موجود مسبقاً: {existing_count} مستخدم")
    print("=" * 60)

    # عرض كل المستخدمين
    cursor.execute("SELECT username, role, full_name FROM users")
    users = cursor.fetchall()
    print("\n👥 المستخدمين المتاحين:")
    for user in users:
        print(f"  - {user[0]} ({user[1]}) - {user[2]}")

    print("\n" + "=" * 60)
    print("🔐 بيانات الدخول الافتراضية:")
    print("=" * 60)
    for user_info in default_users:
        print(f"  {user_info['full_name']}:")
        print(f"    اسم المستخدم: {user_info['username']}")
        print(f"    كلمة المرور: {user_info['password']}")
        print()

    conn.close()


if __name__ == "__main__":
    try:
        create_default_users()
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback

        traceback.print_exc()
