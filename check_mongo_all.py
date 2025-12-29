from pymongo import MongoClient
from dotenv import load_dotenv
import os
load_dotenv()

client = MongoClient(os.getenv('MONGODB_URI'))
db = client['skywave_erp_db']

print("Collections في قاعدة البيانات:")
for coll in db.list_collection_names():
    count = db[coll].count_documents({})
    print(f"  - {coll}: {count} سجل")
