"""
حذف logo_data من العميل المحدد
"""
import pymongo
from bson import ObjectId

MONGO_URI = "mongodb://skywave_app:SkywavePassword2025@147.79.66.116:27017/skywave_erp_db?authSource=skywave_erp_db"

client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client['skywave_erp_db']

# العميل المطلوب حذف صورته
client_id = "691a1e5ef914d80f3ae16135"

# التحقق من وجود العميل
found = db.clients.find_one({"_id": ObjectId(client_id)})
if found:
    print(f"✅ العميل: {found.get('name')}")
    print(f"   logo_data قبل: {len(found.get('logo_data', ''))} حرف")
    
    # حذف الصورة
    result = db.clients.update_one(
        {"_id": ObjectId(client_id)},
        {"$set": {"logo_data": "", "logo_path": ""}}
    )
    
    print(f"   تم التعديل: {result.modified_count}")
    
    # التحقق بعد الحذف
    after = db.clients.find_one({"_id": ObjectId(client_id)})
    print(f"   logo_data بعد: {len(after.get('logo_data', ''))} حرف")
    print("✅ تم حذف الصورة بنجاح!")
else:
    print("❌ العميل غير موجود")

client.close()
