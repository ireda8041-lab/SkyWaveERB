from pymongo import MongoClient
from dotenv import load_dotenv
import os
load_dotenv()

client = MongoClient(os.getenv('MONGODB_URI'))
db = client['skywave_erp_db']

# التحقق من السجلات المحذوفة
deleted = list(db.deleted_records.find({'record_type': 'client'}))
print(f'عدد العملاء المحذوفين في MongoDB: {len(deleted)}')
for d in deleted[:10]:
    rid = d.get('record_id', '?')
    print(f'  - ID: {rid}')

# عدد العملاء الحاليين
clients_count = db.clients.count_documents({})
print(f'\nعدد العملاء الحاليين في MongoDB: {clients_count}')
