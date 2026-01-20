"""
تغيير كلمة مرور مستخدم
✅ FIXED: Now uses AuthService for proper password hashing
"""

import sqlite3

from core.auth_models import AuthService
from core.repository import Repository

DB_PATH = "skywave_local.db"


def reset_password(username: str, new_password: str):
    """تغيير كلمة مرور مستخدم"""
    # Initialize Repository and AuthService
    repo = Repository()
    auth_service = AuthService(repo)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # التحقق من وجود المستخدم
    cursor.execute("SELECT username, full_name FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    if not user:
        print(f"❌ المستخدم '{username}' غير موجود!")
        conn.close()
        return False

    # تحديث كلمة المرور باستخدام AuthService
    new_hash = auth_service.hash_password(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, username))

    conn.commit()
    conn.close()

    print("=" * 50)
    print(f"✅ تم تغيير كلمة مرور المستخدم: {user[0]}")
    print("=" * 50)
    print(f"الاسم الكامل: {user[1]}")
    print(f"اسم المستخدم: {username}")
    print(f"كلمة المرور الجديدة: {new_password}")
    print("=" * 50)
    return True


if __name__ == "__main__":
    print("أدخل بيانات المستخدم:")
    print()
    username = input("اسم المستخدم: ").strip()
    new_password = input("كلمة المرور الجديدة: ").strip()

    if not username or not new_password:
        print("❌ يجب إدخال اسم المستخدم وكلمة المرور!")
    else:
        reset_password(username, new_password)
