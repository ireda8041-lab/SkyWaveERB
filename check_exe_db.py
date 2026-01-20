import sqlite3
import os

# Check database in dist folder
db_path = r"D:\blogs\appas\SkyWaveERB\dist\SkyWaveERP\skywave_local.db"

if not os.path.exists(db_path):
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

print(f"Database found: {db_path}")
print(f"Size: {os.path.getsize(db_path)} bytes")
print()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all users
cursor.execute("SELECT username, full_name, role, password_hash FROM users")
users = cursor.fetchall()

print("=" * 60)
print("USERS IN EXE DATABASE:")
print("=" * 60)
for username, full_name, role, pwd_hash in users:
    print(f"Username: {username}")
    print(f"Full Name: {full_name}")
    print(f"Role: {role}")
    print(f"Password Hash: {pwd_hash[:30]}...")
    print("-" * 60)

# Check admin specifically
cursor.execute("SELECT username, password_hash FROM users WHERE username='admin'")
admin = cursor.fetchone()

if admin:
    print()
    print("=" * 60)
    print("ADMIN USER CHECK:")
    print("=" * 60)
    print(f"Username: {admin[0]}")
    print(f"Password Hash: {admin[1]}")
    print()

    # Verify password hash
    import hashlib

    expected_hash = hashlib.pbkdf2_hmac(
        "sha256", "admin123".encode("utf-8"), b"skywave_salt_2024", 100000
    ).hex()

    print("Expected Hash (admin123):")
    print(expected_hash)
    print()

    if admin[1] == expected_hash:
        print("✅ PASSWORD HASH MATCHES!")
    else:
        print("❌ PASSWORD HASH DOES NOT MATCH!")
        print("This means the password is NOT 'admin123'")
else:
    print()
    print("❌ ADMIN USER NOT FOUND IN DATABASE!")

conn.close()
