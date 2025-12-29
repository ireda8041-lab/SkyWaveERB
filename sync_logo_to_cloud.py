"""
أداة رفع صور العملاء إلى MongoDB
ترفع logo_data من قاعدة البيانات المحلية إلى السحابة مباشرة
"""

import sqlite3
import os
import sys

# إضافة المسار للمشروع
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# مسار قاعدة البيانات
DB_PATH = os.path.join(os.path.expanduser("~"), ".skywave", "skywave_local.db")

if not os.path.exists(DB_PATH):
    DB_PATH = "skywave_local.db"

print(f"📂 مسار قاعدة البيانات: {DB_PATH}")
print("=" * 60)

try:
    # الاتصال بـ SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # جلب العملاء اللي عندهم logo_data
    cursor.execute("""
        SELECT id, name, logo_data, _mongo_id 
        FROM clients 
        WHERE logo_data IS NOT NULL AND logo_data != ''
    """)
    clients_with_logo = cursor.fetchall()
    
    print(f"📊 عدد العملاء اللي عندهم صور: {len(clients_with_logo)}")
    print("-" * 60)
    
    if not clients_with_logo:
        print("❌ لا يوجد عملاء لديهم صور للرفع")
        print("   جرب تشغيل fix_logo_data.py أولاً")
        conn.close()
        input("\nاضغط Enter للخروج...")
        sys.exit(0)
    
    # الاتصال بـ MongoDB
    print("🔌 جاري الاتصال بـ MongoDB...")
    
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        
        # قراءة إعدادات الاتصال من .env
        from dotenv import load_dotenv
        load_dotenv()
        mongo_uri = os.getenv('MONGO_URI', '')
        
        if not mongo_uri:
            print("❌ لم يتم العثور على MONGO_URI")
            print("   تأكد من وجود sync_config.json أو .env")
            conn.close()
            input("\nاضغط Enter للخروج...")
            sys.exit(1)
        
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # اختبار الاتصال
        client.admin.command('ping')
        
        db_name = mongo_uri.split('/')[-1].split('?')[0] or 'skywave_erp'
        db = client[db_name]
        
        print(f"✅ تم الاتصال بـ MongoDB ({db_name})")
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ فشل الاتصال بـ MongoDB: {e}")
        conn.close()
        input("\nاضغط Enter للخروج...")
        sys.exit(1)
    
    # رفع الصور
    uploaded = 0
    failed = 0
    
    for client_row in clients_with_logo:
        name = client_row['name']
        logo_data = client_row['logo_data']
        mongo_id = client_row['_mongo_id']
        
        print(f"🔄 {name}")
        print(f"   📷 حجم الصورة: {len(logo_data)} حرف")
        
        try:
            if mongo_id:
                # تحديث بـ _mongo_id
                result = db.clients.update_one(
                    {"_id": ObjectId(mongo_id)},
                    {"$set": {"logo_data": logo_data}}
                )
            else:
                # تحديث بالاسم
                result = db.clients.update_one(
                    {"name": name},
                    {"$set": {"logo_data": logo_data}}
                )
            
            if result.modified_count > 0:
                print(f"   ✅ تم الرفع بنجاح")
                uploaded += 1
                
                # تحديث sync_status محلياً
                cursor.execute(
                    "UPDATE clients SET sync_status = 'synced' WHERE id = ?",
                    (client_row['id'],)
                )
                conn.commit()
            elif result.matched_count > 0:
                print(f"   ⚠️ الصورة موجودة بالفعل في السحابة")
                uploaded += 1
            else:
                print(f"   ❌ لم يتم العثور على العميل في السحابة")
                failed += 1
                
        except Exception as e:
            print(f"   ❌ خطأ: {e}")
            failed += 1
        
        print()
    
    print("=" * 60)
    print(f"📈 الملخص:")
    print(f"   - تم الرفع: {uploaded} عميل")
    print(f"   - فشل: {failed} عميل")
    
    if uploaded > 0:
        print()
        print("✅ تم الرفع! الآن:")
        print("   1. افتح البرنامج على الجهاز الآخر")
        print("   2. اعمل مزامنة (Sync)")
        print("   3. الصور هتظهر")
    
    conn.close()
    client.close()
    
except Exception as e:
    print(f"❌ خطأ: {e}")
    import traceback
    traceback.print_exc()

input("\nاضغط Enter للخروج...")
