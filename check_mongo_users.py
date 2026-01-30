from pymongo import MongoClient
client = MongoClient('mongodb://skywave_app:SkywavePassword2025@147.79.66.116:27017/skywave_erp_db?authSource=skywave_erp_db', serverSelectionTimeoutMS=5000)
db = client['skywave_erp_db']
users = list(db.users.find())
print(f"Found {len(users)} users in MongoDB:")
for u in users:
    print(f"  ID: {u.get('_id')}")
    print(f"  Username: {u.get('username')}")
    print(f"  Full Name: {u.get('full_name')}")
    print(f"  Role: {u.get('role')}")
    print(f"  Email: {u.get('email')}")
    print("  ---")
