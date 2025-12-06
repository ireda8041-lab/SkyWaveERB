"""
🔄 سكريبت مزامنة البيانات من السيرفر
يجلب كل البيانات من MongoDB ويحفظها في SQLite
"""
import sqlite3
import os
from datetime import datetime

# إعدادات MongoDB
MONGO_URI = "mongodb://skywaveads:Newjoer2k24$@147.79.66.116:27017/skywave_erp_db?authSource=admin"
DB_NAME = "skywave_erp_db"

# مسار قاعدة البيانات المحلية
app_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SkyWaveERP')
LOCAL_DB = os.path.join(app_data_dir, "skywave_local.db")

print("="*60)
print("🔄 مزامنة البيانات من السيرفر")
print("="*60)

try:
    import pymongo
    print("✅ pymongo موجود")
except ImportError:
    print("❌ pymongo غير مثبت! جاري التثبيت...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'pymongo'])
    import pymongo

# الاتصال بـ MongoDB
print("\n📡 جاري الاتصال بالسيرفر...")
try:
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    db = client[DB_NAME]
    print("✅ تم الاتصال بالسيرفر بنجاح!")
except Exception as e:
    print(f"❌ فشل الاتصال بالسيرفر: {e}")
    exit(1)

# الاتصال بـ SQLite
print(f"\n📁 قاعدة البيانات المحلية: {LOCAL_DB}")
conn = sqlite3.connect(LOCAL_DB)
cursor = conn.cursor()

def sync_collection(collection_name, table_name):
    """مزامنة collection من MongoDB إلى SQLite"""
    try:
        # جلب البيانات من MongoDB
        data = list(db[collection_name].find())
        print(f"\n📥 {collection_name}: {len(data)} سجل من السيرفر")
        
        if not data:
            return 0
        
        # الحصول على أسماء الأعمدة من SQLite
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        columns = [col[1] for col in columns_info]
        
        synced = 0
        for doc in data:
            mongo_id = str(doc.pop('_id'))
            
            # التحقق من وجود السجل
            cursor.execute(f"SELECT id FROM {table_name} WHERE _mongo_id = ?", (mongo_id,))
            exists = cursor.fetchone()
            
            if exists:
                continue  # السجل موجود
            
            # تحضير البيانات للإدراج
            doc['_mongo_id'] = mongo_id
            doc['sync_status'] = 'synced'
            
            # إزالة الحقول غير الموجودة في الجدول
            insert_data = {}
            for key, value in doc.items():
                if key in columns:
                    if isinstance(value, (dict, list)):
                        import json
                        insert_data[key] = json.dumps(value, ensure_ascii=False)
                    elif isinstance(value, datetime):
                        insert_data[key] = value.isoformat()
                    else:
                        insert_data[key] = value
            
            if not insert_data:
                continue
            
            # إدراج السجل
            cols = ', '.join(insert_data.keys())
            placeholders = ', '.join(['?' for _ in insert_data])
            values = list(insert_data.values())
            
            try:
                cursor.execute(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})", values)
                synced += 1
            except Exception as e:
                print(f"   ⚠️ خطأ في إدراج سجل: {e}")
        
        conn.commit()
        print(f"   ✅ تم مزامنة {synced} سجل جديد")
        return synced
        
    except Exception as e:
        print(f"   ❌ خطأ: {e}")
        return 0

# مزامنة الجداول
collections = [
    ('clients', 'clients'),
    ('projects', 'projects'),
    ('payments', 'payments'),
    ('expenses', 'expenses'),
    ('services', 'services'),
    ('journal_entries', 'journal_entries'),
    ('quotations', 'quotations'),
]

total_synced = 0
for mongo_col, sqlite_table in collections:
    synced = sync_collection(mongo_col, sqlite_table)
    total_synced += synced

print("\n" + "="*60)
print(f"✅ تم مزامنة {total_synced} سجل جديد من السيرفر")
print("="*60)
print("\n💡 أعد تشغيل البرنامج لرؤية البيانات المحدثة")

conn.close()
client.close()
