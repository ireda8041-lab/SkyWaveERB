"""
فحص العملاء اللي عندهم صور في MongoDB
"""
import pymongo

MONGO_URI = "mongodb://skywave_app:SkywavePassword2025@147.79.66.116:27017/skywave_erp_db?authSource=skywave_erp_db"

client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client['skywave_erp_db']

# البحث عن العملاء اللي عندهم logo_data
clients = list(db.clients.find({'logo_data': {'$ne': '', '$exists': True}}, {'name': 1, 'logo_data': 1, '_id': 1}))
print(f"عدد العملاء اللي عندهم صور: {len(clients)}")
for c in clients:
    logo_len = len(c.get('logo_data', ''))
    name = c.get('name', 'N/A')
    _id = str(c.get('_id'))
    print(f"  - {name}")
    print(f"    _id: {_id}")
    print(f"    logo_data: {logo_len} حرف")
    print()

client.close()
