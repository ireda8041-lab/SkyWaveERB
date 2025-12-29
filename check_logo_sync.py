"""
أداة تشخيص مشكلة مزامنة صور العملاء
شغل الملف ده عشان تشوف إيه اللي بيحصل
"""

import sqlite3
import os

# مسار قاعدة البيانات
DB_PATH = os.path.join(os.path.expanduser("~"), ".skywave", "skywave_local.db")

if not os.path.exists(DB_PATH):
    DB_PATH = "skywave_local.db"

print(f"📂 مسار قاعدة البيانات: {DB_PATH}")
print("=" * 60)

try:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # جلب كل العملاء
    cursor.execute("SELECT id, name, logo_path, logo_data, _mongo_id FROM clients")
    clients = cursor.fetchall()
    
    print(f"📊 عدد العملاء: {len(clients)}")
    print("-" * 60)
    
    clients_with_logo = 0
    clients_without_logo = 0
    
    for client in clients:
        name = client['name']
        logo_path = client['logo_path']
        logo_data = client['logo_data']
        mongo_id = client['_mongo_id']
        
        has_logo_data = bool(logo_data and len(logo_data) > 100)
        has_logo_path = bool(logo_path)
        
        if has_logo_data:
            clients_with_logo += 1
            print(f"✅ {name}")
            print(f"   - logo_data: {len(logo_data)} حرف")
            print(f"   - logo_path: {logo_path or 'لا يوجد'}")
            print(f"   - mongo_id: {mongo_id or 'غير متزامن'}")
        else:
            clients_without_logo += 1
            print(f"❌ {name}")
            print(f"   - logo_data: {'فارغ' if not logo_data else f'{len(logo_data)} حرف'}")
            print(f"   - logo_path: {logo_path or 'لا يوجد'}")
            print(f"   - mongo_id: {mongo_id or 'غير متزامن'}")
        print()
    
    print("=" * 60)
    print(f"📈 الملخص:")
    print(f"   - عملاء لديهم صور: {clients_with_logo}")
    print(f"   - عملاء بدون صور: {clients_without_logo}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ خطأ: {e}")
    import traceback
    traceback.print_exc()

input("\nاضغط Enter للخروج...")
