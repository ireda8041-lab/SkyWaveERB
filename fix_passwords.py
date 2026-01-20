"""
Fix password hash format for existing users
Uses the same method as AuthService
"""

import sqlite3
from core.auth_models import AuthService
from core.repository import Repository

# Initialize
repo = Repository()
auth_service = AuthService(repo)

# Get all users
conn = sqlite3.connect(
    repo.sqlite_conn.execute("SELECT name FROM sqlite_master").fetchone()[0]
    if False
    else "skywave_local.db"
)
cursor = conn.cursor()

cursor.execute("SELECT username, full_name FROM users")
users = cursor.fetchall()

print("=" * 60)
print("Fixing password hashes for all users...")
print("=" * 60)

for username, full_name in users:
    # Set same password for all (admin123)
    new_password = "admin123"
    new_hash = auth_service.hash_password(new_password)

    cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, username))

    print(f"✅ Updated: {username} ({full_name})")
    print(f"   Password: {new_password}")
    print(f"   New hash format: {new_hash[:30]}...")
    print()

conn.commit()
conn.close()

print("=" * 60)
print("Done! All users can now login with: admin123")
print("=" * 60)
