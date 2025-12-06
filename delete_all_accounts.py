"""
🗑️ مسح كل الحسابات من قاعدة البيانات
"""
import sqlite3
import os

# إعدادات MongoDB
MONGO_URI = "mongodb://skywaveads:Newjoer2k24$@147.79.66.116:27017/skywave_erp_db?authSource=admin"
DB_NAME = "skywave_erp_db"

# مسار قاعدة البيانات المحلية
app_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SkyWaveERP')
LOCAL_DB = os.path.join(app_data_dir, "skywave_local.db")

print("="*60)
print("🗑️ مسح كل الحسابات")
print("="*60)

# 1. مسح من SQLite المحلي
print("\n📁 مسح من قاعدة البيانات المحلية...")
conn = sqlite3.connect(LOCAL_DB)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM accounts")
count_before = cursor.fetchone()[0]
print(f"   عدد الحسابات قبل المسح: {count_before}")

cursor.execute("DELETE FROM accounts")
conn.commit()

cursor.execute("SELECT COUNT(*) FROM accounts")
count_after = cursor.fetchone()[0]
print(f"   عدد الحسابات بعد المسح: {count_after}")
print("   ✅ تم مسح الحسابات من SQLite")

# مسح القيود المحاسبية أيضاً
cursor.execute("DELETE FROM journal_entries")
conn.commit()
print("   ✅ تم مسح القيود المحاسبية من SQLite")

conn.close()

# 2. مسح من MongoDB
print("\n📡 مسح من السيرفر (MongoDB)...")
try:
    import pymongo
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    db = client[DB_NAME]
    
    # مسح الحسابات
    result = db.accounts.delete_many({})
    print(f"   ✅ تم مسح {result.deleted_count} حساب من السيرفر")
    
    # مسح القيود
    result = db.journal_entries.delete_many({})
    print(f"   ✅ تم مسح {result.deleted_count} قيد من السيرفر")
    
    client.close()
except Exception as e:
    print(f"   ⚠️ فشل الاتصال بالسيرفر: {e}")

print("\n" + "="*60)
print("✅ تم مسح كل الحسابات والقيود بنجاح!")
print("="*60)
print("\n💡 الآن يمكنك إضافة الحسابات يدوياً من البرنامج")
