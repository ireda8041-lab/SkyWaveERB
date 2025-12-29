"""
مزامنة الصور من قاعدة البيانات المثبتة إلى MongoDB
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# قاعدة بيانات البرنامج المثبت
INSTALLED_DB = r"D:\Sky Wave ERP\_internal\skywave_local.db"

print("=" * 60)
print("مزامنة الصور من البرنامج المثبت إلى MongoDB")
print("=" * 60)

# الاتصال بـ SQLite
conn = sqlite3.connect(INSTALLED_DB)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# جلب العملاء اللي عندهم صور
cursor.execute("""
    SELECT name, logo_data, _mongo_id 
    FROM clients 
    WHERE logo_data IS NOT NULL AND logo_data != ''
""")
clients_with_logo = cursor.fetchall()

print(f"\n📊 عملاء لديهم صور: {len(clients_with_logo)}")

# الاتصال بـ MongoDB
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
load_dotenv()

mongo_uri = os.getenv('MONGO_URI')
mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
mongo_client.admin.command('ping')
db = mongo_client['skywave_erp_db']

print("✅ تم الاتصال بـ MongoDB")
print("-" * 60)

uploaded = 0
failed = 0

for client in clients_with_logo:
    name = client['name']
    logo_data = client['logo_data']
    mongo_id = client['_mongo_id']
    
    print(f"\n🔄 {name}")
    print(f"   📷 حجم الصورة: {len(logo_data)} حرف")
    
    try:
        # البحث عن العميل في MongoDB
        if mongo_id:
            result = db.clients.update_one(
                {"_id": ObjectId(mongo_id)},
                {"$set": {"logo_data": logo_data}}
            )
        else:
            result = db.clients.update_one(
                {"name": name},
                {"$set": {"logo_data": logo_data}}
            )
        
        if result.modified_count > 0:
            print(f"   ✅ تم الرفع")
            uploaded += 1
        elif result.matched_count > 0:
            print(f"   ⚠️ موجود بالفعل")
            uploaded += 1
        else:
            # العميل غير موجود - نضيفه
            print(f"   ❓ العميل غير موجود في MongoDB")
            failed += 1
            
    except Exception as e:
        print(f"   ❌ خطأ: {e}")
        failed += 1

print("\n" + "=" * 60)
print(f"📈 الملخص:")
print(f"   - تم الرفع: {uploaded}")
print(f"   - فشل: {failed}")

# التحقق
print("\n" + "-" * 60)
print("التحقق من MongoDB:")
for client in clients_with_logo[:3]:
    name = client['name']
    doc = db.clients.find_one({"name": name})
    if doc and doc.get('logo_data'):
        print(f"   ✅ {name}: {len(doc['logo_data'])} حرف")
    else:
        print(f"   ❌ {name}: لا توجد صورة")

conn.close()
mongo_client.close()

print("\n✅ انتهى!")
