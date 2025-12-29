"""
استعادة بيانات العملاء من البرنامج المثبت إلى MongoDB
"""
import sqlite3
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

# الاتصال بقاعدة البيانات المحلية
db_path = r'D:\Sky Wave ERP\_internal\skywave_local.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# الاتصال بـ MongoDB
mongo_client = MongoClient(os.getenv('MONGODB_URI'))
db = mongo_client['skywave_erp_db']

print("=" * 60)
print("استعادة البيانات إلى MongoDB")
print("=" * 60)

# رفع العملاء
cursor.execute("SELECT * FROM clients")
clients = cursor.fetchall()
print(f"\n📊 عدد العملاء: {len(clients)}")

uploaded = 0
for client in clients:
    client_dict = dict(client)
    # تحويل id إلى _id
    if 'id' in client_dict:
        client_dict['_id'] = client_dict.pop('id')
    
    try:
        db.clients.replace_one(
            {'_id': client_dict['_id']},
            client_dict,
            upsert=True
        )
        uploaded += 1
        name = client_dict.get('name', '?')
        has_logo = '📷' if client_dict.get('logo_data') else ''
        print(f"  ✅ {name} {has_logo}")
    except Exception as e:
        print(f"  ❌ خطأ: {e}")

print(f"\n✅ تم رفع {uploaded} عميل")

# التحقق
count = db.clients.count_documents({})
print(f"📊 العملاء في MongoDB الآن: {count}")

conn.close()
print("\n✅ انتهى!")
