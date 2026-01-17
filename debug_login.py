import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

try:
    from core.repository import Repository
    from core.auth_models import User
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

print("--- Initializing Repository ---")
try:
    repo = Repository()
except Exception as e:
    print(f"Repository Init Error: {e}")
    sys.exit(1)

username = "reda"
print(f"--- Attempting to load user: {username} ---")

# Access SQLite directly to see raw data first
print("Raw SQLite Data:")
try:
    repo.sqlite_cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = repo.sqlite_cursor.fetchone()
    if row:
        row_dict = dict(row)
        print(row_dict)
    else:
        print("User not found in SQLite")
except Exception as e:
    print(f"SQLite Error: {e}")

# Try using get_user_by_username which uses Pydantic
print("\n--- Testing get_user_by_username ---")
user = repo.get_user_by_username(username)
if user:
    print(f"✅ User Loaded Successfully: {user.username}")
    print(f"   Password Hash: {user.password_hash}")
    print(f"   Is Active: {user.is_active}")
else:
    print("❌ Failed to load user via Repository method (returned None)")

# If user failed, try to manually instantiate User model to see precise error
if not user and row:
    print("\n--- Debugging Validation Error ---")
    try:
        from core.auth_models import UserRole
        import json

        user_data = dict(row)
        user_data["id"] = str(user_data["id"])
        user_data["role"] = (
            UserRole(user_data["role"]) if isinstance(user_data["role"], str) else user_data["role"]
        )
        user_data["is_active"] = bool(user_data["is_active"])

        if user_data.get("custom_permissions"):
            user_data["custom_permissions"] = json.loads(user_data["custom_permissions"])
        else:
            user_data["custom_permissions"] = None

        print("Constructing User model with data:", user_data)
        u = User(**user_data)
        print("User constructed manually OK")
    except Exception as e:
        print(f"‼️ VALIDATION ERROR: {e}")
