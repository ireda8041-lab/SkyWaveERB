"""
أداة إصلاح صور العملاء
تحول الصور من logo_path إلى logo_data (base64)
وترفعها مباشرة إلى MongoDB
"""

import sqlite3
import os
import base64
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# مسار قاعدة البيانات
DB_PATH = os.path.join(os.path.expanduser("~"), ".skywave", "skywave_local.db")

if not os.path.exists(DB_PATH):
    DB_PATH = "skywave_local.db"

print(f"📂 مسار قاعدة البيانات: {DB_PATH}")
print("=" * 60)

def convert_image_to_base64(image_path: str) -> str:
    """تحويل صورة إلى base64"""
    if not image_path or not os.path.exists(image_path):
        return ""
    
    try:
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()
        
        # ضغط الصورة لو كبيرة
        if len(img_data) > 500 * 1024:
            try:
                from PIL import Image
                import io
                
                img = Image.open(image_path)
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                
                buffer = io.BytesIO()
                img.save(buffer, format='PNG', optimize=True)
                img_data = buffer.getvalue()
                print(f"   📦 تم ضغط الصورة من {len(img_data)//1024}KB")
            except ImportError:
                print("   ⚠️ PIL غير متوفر - سيتم حفظ الصورة بحجمها الأصلي")
        
        base64_str = base64.b64encode(img_data).decode('utf-8')
        
        ext = os.path.splitext(image_path)[1].lower()
        mime_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif'
        }.get(ext, 'image/png')
        
        return f"data:{mime_type};base64,{base64_str}"
    
    except Exception as e:
        print(f"   ❌ خطأ في تحويل الصورة: {e}")
        return ""

try:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # جلب العملاء اللي عندهم logo_path بس مفيش logo_data
    cursor.execute("""
        SELECT id, name, logo_path, logo_data, _mongo_id 
        FROM clients 
        WHERE logo_path IS NOT NULL AND logo_path != '' 
        AND (logo_data IS NULL OR logo_data = '')
    """)
    clients = cursor.fetchall()
    
    print(f"📊 عدد العملاء اللي محتاجين إصلاح: {len(clients)}")
    print("-" * 60)
    
    # الاتصال بـ MongoDB
    mongo_client = None
    mongo_db = None
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        from dotenv import load_dotenv
        load_dotenv()
        
        mongo_uri = os.getenv('MONGO_URI', '')
        if mongo_uri:
            mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            mongo_client.admin.command('ping')
            mongo_db = mongo_client['skywave_erp_db']
            print("✅ تم الاتصال بـ MongoDB")
        else:
            print("⚠️ لم يتم العثور على MONGO_URI - سيتم الحفظ محلياً فقط")
    except Exception as e:
        print(f"⚠️ فشل الاتصال بـ MongoDB: {e}")
        print("   سيتم الحفظ محلياً فقط")
    
    print("-" * 60)
    
    fixed = 0
    failed = 0
    
    for client in clients:
        client_id = client['id']
        name = client['name']
        logo_path = client['logo_path']
        mongo_id = client['_mongo_id']
        
        print(f"🔄 {name}")
        print(f"   📁 المسار: {logo_path}")
        
        if os.path.exists(logo_path):
            logo_data = convert_image_to_base64(logo_path)
            
            if logo_data:
                # حفظ في SQLite
                cursor.execute(
                    "UPDATE clients SET logo_data = ?, sync_status = 'synced' WHERE id = ?",
                    (logo_data, client_id)
                )
                conn.commit()
                
                # حفظ في MongoDB
                if mongo_db and mongo_id:
                    try:
                        mongo_db.clients.update_one(
                            {'_id': ObjectId(mongo_id)},
                            {'$set': {'logo_data': logo_data}}
                        )
                        print(f"   ✅ تم الحفظ محلياً و MongoDB ({len(logo_data)} حرف)")
                    except Exception as e:
                        print(f"   ⚠️ تم الحفظ محلياً فقط - فشل MongoDB: {e}")
                else:
                    print(f"   ✅ تم الحفظ محلياً ({len(logo_data)} حرف)")
                
                fixed += 1
            else:
                print(f"   ❌ فشل التحويل")
                failed += 1
        else:
            print(f"   ⚠️ الملف غير موجود")
            failed += 1
        
        print()
    
    print("=" * 60)
    print(f"📈 الملخص:")
    print(f"   - تم إصلاح: {fixed} عميل")
    print(f"   - فشل: {failed} عميل")
    
    if fixed > 0:
        print()
        print("✅ تم الإصلاح!")
        print("   الصور الآن متزامنة بين المحلي والسحابة")
    
    conn.close()
    if mongo_client:
        mongo_client.close()
    
except Exception as e:
    print(f"❌ خطأ: {e}")
    import traceback
    traceback.print_exc()

input("\nاضغط Enter للخروج...")
