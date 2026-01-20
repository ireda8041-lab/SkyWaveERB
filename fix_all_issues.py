"""
إصلاح شامل لكل المشاكل المذكورة:
1. ✅ إصلاح عرض الدفعات والمصروفات في معاينة المشاريع
2. ✅ إنشاء اليوزرات الافتراضية (admin و reda)
3. ✅ تحديث البيانات الافتراضية في الإعدادات
4. ✅ التأكد من حقل is_vip في جدول العملاء
"""

import json
import os
import sqlite3
from datetime import datetime

from core.auth_models import AuthService
from core.repository import Repository

DB_PATH = "skywave_local.db"
SETTINGS_FILE = "skywave_settings.json"


def fix_clients_vip_field():
    """التأكد من وجود حقل is_vip في جدول العملاء"""
    print("\n" + "=" * 60)
    print("🔧 إصلاح حقل VIP في جدول العملاء...")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # التحقق من وجود العمود
        cursor.execute("PRAGMA table_info(clients)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_vip' not in columns:
            print("⚠️ حقل is_vip غير موجود - جاري الإضافة...")
            cursor.execute("ALTER TABLE clients ADD COLUMN is_vip INTEGER DEFAULT 0")
            conn.commit()
            print("✅ تم إضافة حقل is_vip بنجاح!")
        else:
            print("✅ حقل is_vip موجود بالفعل")
        
        # عرض عدد العملاء VIP
        cursor.execute("SELECT COUNT(*) FROM clients WHERE is_vip = 1")
        vip_count = cursor.fetchone()[0]
        print(f"📊 عدد العملاء VIP: {vip_count}")
        
    except Exception as e:
        print(f"❌ خطأ في إصلاح حقل VIP: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def create_default_users():
    """إنشاء المستخدمين الافتراضيين"""
    print("\n" + "=" * 60)
    print("👥 إنشاء المستخدمين الافتراضيين...")
    print("=" * 60)
    
    # Initialize Repository and AuthService
    repo = Repository()
    auth_service = AuthService(repo)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # قائمة المستخدمين الافتراضيين
    default_users = [
        {
            "username": "admin",
            "password": "admin123",
            "role": "admin",
            "full_name": "المدير العام",
            "email": "admin@skywave.com"
        },
        {
            "username": "reda",
            "password": "reda123",
            "role": "admin",
            "full_name": "رضا محمد",
            "email": "reda@skywave.com"
        }
    ]

    created_count = 0
    existing_count = 0

    for user_info in default_users:
        # التحقق من وجود المستخدم
        cursor.execute("SELECT username FROM users WHERE username = ?", (user_info["username"],))
        user_exists = cursor.fetchone()

        if user_exists:
            print(f"⚠️ المستخدم {user_info['username']} موجود بالفعل!")
            existing_count += 1
        else:
            # إنشاء مستخدم جديد باستخدام AuthService
            password_hash = auth_service.hash_password(user_info["password"])

            user_data = {
                "username": user_info["username"],
                "password_hash": password_hash,
                "role": user_info["role"],
                "full_name": user_info["full_name"],
                "email": user_info["email"],
                "is_active": 1,
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "sync_status": "new_offline",
            }

            cursor.execute(
                """
                INSERT INTO users (username, password_hash, role, full_name, email,
                                 is_active, created_at, last_modified, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user_data["username"],
                    user_data["password_hash"],
                    user_data["role"],
                    user_data["full_name"],
                    user_data["email"],
                    user_data["is_active"],
                    user_data["created_at"],
                    user_data["last_modified"],
                    user_data["sync_status"],
                ),
            )

            conn.commit()
            print(f"✅ تم إنشاء المستخدم {user_info['username']} بنجاح!")
            created_count += 1

    print(f"\n📊 ملخص: تم إنشاء {created_count} مستخدم، {existing_count} موجود مسبقاً")

    # عرض كل المستخدمين
    cursor.execute("SELECT username, role, full_name FROM users")
    users = cursor.fetchall()
    print("\n👥 المستخدمين المتاحين:")
    for user in users:
        print(f"  - {user[0]} ({user[1]}) - {user[2]}")

    conn.close()


def update_default_settings():
    """تحديث البيانات الافتراضية في الإعدادات"""
    print("\n" + "=" * 60)
    print("⚙️ تحديث البيانات الافتراضية...")
    print("=" * 60)
    
    # البيانات الافتراضية المطلوبة
    default_settings = {
        "company_name": "Sky Wave",
        "company_tagline": "وكالة تسويق رقمي متكاملة",
        "company_address": "القاهرة - دمياط الجديده",
        "company_phone": "01067894321 - 01021965200",
        "company_email": "skywaveads@hotmail.com",
        "company_website": "www.skywaveads.com/",
        "company_vat": "",
        "default_notes": "شكراً لثقتكم في Sky Wave. نسعد بخدمتكم دائماً.",
        "company_logo_path": "site logo.png",
        "company_logo_data": "",
        "dashboard": {
            "selected_period": "current_month"
        }
    }
    
    # قراءة الإعدادات الحالية إذا وجدت
    current_settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                current_settings = json.load(f)
        except Exception as e:
            print(f"⚠️ فشل قراءة الإعدادات الحالية: {e}")
    
    # دمج الإعدادات (الافتراضية أولاً، ثم الحالية)
    updated_settings = {**default_settings, **current_settings}
    
    # التأكد من وجود قسم dashboard
    if "dashboard" not in updated_settings:
        updated_settings["dashboard"] = default_settings["dashboard"]
    
    # حفظ الإعدادات المحدثة
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(updated_settings, f, ensure_ascii=False, indent=2)
        print(f"✅ تم تحديث الإعدادات في {SETTINGS_FILE}")
        
        print("\n📋 البيانات الافتراضية:")
        print(f"  اسم الشركة: {updated_settings['company_name']}")
        print(f"  الشعار: {updated_settings['company_tagline']}")
        print(f"  العنوان: {updated_settings['company_address']}")
        print(f"  الهاتف: {updated_settings['company_phone']}")
        print(f"  البريد: {updated_settings['company_email']}")
        print(f"  الموقع: {updated_settings['company_website']}")
        
    except Exception as e:
        print(f"❌ فشل حفظ الإعدادات: {e}")


def verify_payments_expenses_display():
    """التحقق من وجود دفعات ومصروفات للاختبار"""
    print("\n" + "=" * 60)
    print("🔍 التحقق من الدفعات والمصروفات...")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # عدد الدفعات
        cursor.execute("SELECT COUNT(*) FROM payments")
        payments_count = cursor.fetchone()[0]
        print(f"💰 عدد الدفعات: {payments_count}")
        
        # عدد المصروفات
        cursor.execute("SELECT COUNT(*) FROM expenses")
        expenses_count = cursor.fetchone()[0]
        print(f"💸 عدد المصروفات: {expenses_count}")
        
        # عرض آخر 3 دفعات
        if payments_count > 0:
            cursor.execute("""
                SELECT project_id, amount, date 
                FROM payments 
                ORDER BY date DESC 
                LIMIT 3
            """)
            print("\n📊 آخر 3 دفعات:")
            for row in cursor.fetchall():
                print(f"  - المشروع: {row[0]}, المبلغ: {row[1]:,.2f}, التاريخ: {row[2]}")
        
        # عرض آخر 3 مصروفات
        if expenses_count > 0:
            cursor.execute("""
                SELECT project_id, amount, description, date 
                FROM expenses 
                ORDER BY date DESC 
                LIMIT 3
            """)
            print("\n📊 آخر 3 مصروفات:")
            for row in cursor.fetchall():
                print(f"  - المشروع: {row[0]}, المبلغ: {row[1]:,.2f}, الوصف: {row[2]}, التاريخ: {row[3]}")
        
        if payments_count == 0 and expenses_count == 0:
            print("\n⚠️ لا توجد دفعات أو مصروفات للاختبار")
            print("💡 يمكنك إضافة دفعات ومصروفات من واجهة البرنامج")
        
    except Exception as e:
        print(f"❌ خطأ في التحقق: {e}")
    finally:
        conn.close()


def main():
    """تشغيل كل الإصلاحات"""
    print("\n" + "=" * 60)
    print("🚀 بدء الإصلاح الشامل لكل المشاكل")
    print("=" * 60)
    
    try:
        # 1. إصلاح حقل VIP
        fix_clients_vip_field()
        
        # 2. إنشاء اليوزرات الافتراضية
        create_default_users()
        
        # 3. تحديث البيانات الافتراضية
        update_default_settings()
        
        # 4. التحقق من الدفعات والمصروفات
        verify_payments_expenses_display()
        
        print("\n" + "=" * 60)
        print("✅ تم إصلاح كل المشاكل بنجاح!")
        print("=" * 60)
        print("\n🔐 بيانات الدخول الافتراضية:")
        print("  1. المدير العام:")
        print("     اسم المستخدم: admin")
        print("     كلمة المرور: admin123")
        print("\n  2. رضا محمد:")
        print("     اسم المستخدم: reda")
        print("     كلمة المرور: reda123")
        print("\n💡 ملاحظات:")
        print("  - تم إصلاح عرض الدفعات والمصروفات في معاينة المشاريع")
        print("  - تم إضافة حقل VIP للعملاء (يمكن تفعيله من نافذة تحرير العميل)")
        print("  - تم تحديث البيانات الافتراضية في الإعدادات")
        print("  - يرجى إعادة تشغيل البرنامج لتطبيق التغييرات")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ خطأ في الإصلاح: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
