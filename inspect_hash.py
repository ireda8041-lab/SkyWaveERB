import sys
import os
import sqlite3

username = "reda"
db_path = r"D:\Sky Wave ERP\skywave_local.db"

if not os.path.exists(db_path):
    print(f"❌ Database not found at {db_path}")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
row = cursor.fetchone()

if row:
    ph = row[0]
    print(f"User: {username}")
    print(f"Hash Length: {len(ph)}")
    print(f"Has Colon: {':' in ph}")

    if ":" in ph:
        salt, h = ph.split(":", 1)
        print(f"Salt Length: {len(salt)}")
        print(f"Hash Part Length: {len(h)}")
    else:
        print("Format: Legacy (No Colon)")
        # Check if it looks like SHA256 (64 hex chars)
        import re

        if re.match(r"^[a-fA-F0-9]{64}$", ph):
            print("Looks like valid SHA256 hex digest")
        else:
            print("⚠️ WARNING: Does NOT look like valid SHA256 hex digest!")
            print(f"Value content sample: {ph[:10]}...")
else:
    print(f"User {username} not found")

conn.close()
