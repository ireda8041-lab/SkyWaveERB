"""
أداة فحص صور العملاء في MongoDB
تتحقق من وجود logo_data في السحابة
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔍 فحص صور العملاء في MongoDB")
print("=" * 60)

try:
    from pymongo import MongoClient
    import json
    
    # قراءة إعدادات الاتصال من .env
    from dotenv import load_dotenv
    load_dotenv()
    mongo_uri = os.getenv('MONGO_URI', '')
    
    if not mongo_uri:
        print("❌ لم يتم العثور على MONGO_URI")
        input("\nاضغط Enter للخروج...")
        sys.exit(1)
    
    print("🔌 جاري الاتصال بـ MongoDB...")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    
    db_name = mongo_uri.split('/')[-1].split('?')[0] or 'skywave_erp'
    db = client[db_name]
    
    print(f"✅ تم الاتصال ({db_name})")
    print("-" * 60)
    
    # جلب كل العملاء
    clients = list(db.clients.find())
    
    print(f"📊 عدد العملاء في MongoDB: {len(clients)}")
    print("-" * 60)
    
    with_logo = 0
    without_logo = 0
    
    for c in clients:
        name = c.get('name', 'بدون اسم')
        logo_data = c.get('logo_data', '')
        logo_path = c.get('logo_path', '')
        
        if logo_data:
            print(f"✅ {name}")
            print(f"   📷 logo_data: {len(logo_data)} حرف")
            with_logo += 1
        else:
            status = "❌"
            extra = ""
            if logo_path:
                extra = f" (logo_path: {logo_path})"
            print(f"{status} {name}{extra}")
            without_logo += 1
    
    print("=" * 60)
    print(f"📈 الملخص:")
    print(f"   - عملاء لديهم صور: {with_logo}")
    print(f"   - عملاء بدون صور: {without_logo}")
    
    client.close()
    
except Exception as e:
    print(f"❌ خطأ: {e}")
    import traceback
    traceback.print_exc()

input("\nاضغط Enter للخروج...")
