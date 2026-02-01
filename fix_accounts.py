"""إصلاح الحسابات في MongoDB"""

import time

from core.repository import Repository

repo = Repository()
time.sleep(3)

print("=== Fixing MongoDB Accounts ===")

if repo.mongo_db is not None:
    # 2. تصفير رصيد حساب العملاء
    print("Resetting 112100 balance to 0...")
    repo.mongo_db["accounts"].update_one({"code": "112100"}, {"$set": {"balance": 0.0}})

    # 3. تصفير رصيد حساب الإيرادات
    print("Resetting 410100 balance to 0...")
    repo.mongo_db["accounts"].update_one({"code": "410100"}, {"$set": {"balance": 0.0}})

    print("Done!")

    # Verify
    print()
    print("=== Verifying MongoDB ===")
    for acc in repo.mongo_db["accounts"].find():
        print(f"{acc.get('code')}: {acc.get('name')} = {acc.get('balance')}")

# Now sync to local
print()
print("=== Syncing to Local ===")
cursor = repo.get_cursor()

# Add V/F REDA locally if not exists
cursor.execute("SELECT id FROM accounts WHERE code = '111002'")
if not cursor.fetchone():
    print("Adding V/F REDA locally...")
    cursor.execute(
        """
        INSERT INTO accounts (code, name, type, parent_id, balance, currency, description, status, created_at, last_modified, sync_status)
        VALUES ('111002', 'V/F REDA', 'أصول نقدية', '111000', 0.0, 'EGP', 'محفظة فودافون كاش - رضا', 'نشط', datetime('now'), datetime('now'), 'synced')
    """
    )
    repo.sqlite_conn.commit()
    print("V/F REDA added locally!")

# Update local balances
print("Updating local balances...")
cursor.execute("UPDATE accounts SET balance = 0.0 WHERE code = '112100'")
cursor.execute("UPDATE accounts SET balance = 0.0 WHERE code = '410100'")
repo.sqlite_conn.commit()

cursor.close()

# Verify local
print()
print("=== Verifying Local ===")
cursor = repo.get_cursor()
cursor.execute("SELECT code, name, balance FROM accounts ORDER BY code")
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]} = {row[2]}")
cursor.close()

repo.close()
print()
print("=== All Done! ===")
