"""
سكريبت لحذف logo_data من عميل معين في MongoDB
"""
import pymongo

MONGO_URI = "mongodb://skywave_app:SkywavePassword2025@147.79.66.116:27017/skywave_erp_db?authSource=skywave_erp_db"
DB_NAME = "skywave_erp_db"

def delete_logo(client_name: str):
    """حذف logo_data من عميل معين"""
    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        
        # البحث عن العميل
        found = db.clients.find_one({"name": {"$regex": client_name, "$options": "i"}})
        
        if not found:
            print(f"❌ العميل '{client_name}' غير موجود")
            return
        
        print(f"✅ تم العثور على العميل: {found.get('name')}")
        print(f"   _id: {found.get('_id')}")
        print(f"   logo_path: {found.get('logo_path', 'N/A')}")
        logo_data = found.get('logo_data', '')
        print(f"   logo_data: {'موجود (' + str(len(logo_data)) + ' حرف)' if logo_data else 'فارغ'}")
        
        if not logo_data:
            print("ℹ️ العميل ليس لديه صورة أصلاً")
            return
        
        # تأكيد الحذف
        confirm = input("\n⚠️ هل تريد حذف الصورة؟ (y/n): ")
        if confirm.lower() != 'y':
            print("❌ تم الإلغاء")
            return
        
        # حذف الصورة
        result = db.clients.update_one(
            {"_id": found["_id"]},
            {"$set": {"logo_data": "", "logo_path": ""}}
        )
        
        if result.modified_count > 0:
            print("✅ تم حذف الصورة بنجاح!")
        else:
            print("⚠️ لم يتم تعديل أي شيء")
        
        client.close()
        
    except Exception as e:
        print(f"❌ خطأ: {e}")

if __name__ == "__main__":
    # العميل من الصورة
    client_name = "أبو علي للأقمشة الرقية والسواريه"
    delete_logo(client_name)
