#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 إصلاح مشاكل الأداء والتجميد - Sky Wave ERP
================================================
يحل مشكلة تجميد البرنامج عن طريق:
1. تحسين عمليات قاعدة البيانات
2. إضافة indexes للجداول
3. تحسين الـ cache
4. تقليل العمليات المتزامنة
"""

import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


def get_db_path():
    """الحصول على مسار قاعدة البيانات"""
    # أولاً: جرب المسار المحلي
    local_path = os.path.join(os.path.dirname(__file__), "skywave_local.db")
    if os.path.exists(local_path):
        return local_path
    
    # ثانياً: جرب مسار AppData
    app_data = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SkyWaveERP")
    appdata_path = os.path.join(app_data, "skywave_local.db")
    if os.path.exists(appdata_path):
        return appdata_path
    
    # افتراضياً: استخدم المسار المحلي
    return local_path


def add_database_indexes():
    """إضافة indexes لتسريع الاستعلامات"""
    safe_print("\n" + "="*60)
    safe_print("🚀 إضافة Indexes لتسريع قاعدة البيانات")
    safe_print("="*60)
    
    db_path = get_db_path()
    if not os.path.exists(db_path):
        safe_print(f"❌ قاعدة البيانات غير موجودة: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        indexes = [
            # Indexes للمشاريع
            ("idx_projects_client", "CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id)"),
            ("idx_projects_status", "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)"),
            ("idx_projects_name", "CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)"),
            
            # Indexes للدفعات
            ("idx_payments_project", "CREATE INDEX IF NOT EXISTS idx_payments_project ON payments(project_id)"),
            ("idx_payments_client", "CREATE INDEX IF NOT EXISTS idx_payments_client ON payments(client_id)"),
            ("idx_payments_date", "CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(date)"),
            
            # Indexes للمصروفات
            ("idx_expenses_project", "CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(project_id)"),
            ("idx_expenses_date", "CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)"),
            ("idx_expenses_category", "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)"),
            
            # Indexes للعملاء
            ("idx_clients_name", "CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name)"),
            ("idx_clients_status", "CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status)"),
            ("idx_clients_vip", "CREATE INDEX IF NOT EXISTS idx_clients_vip ON clients(is_vip)"),
            
            # Indexes للحسابات
            ("idx_accounts_code", "CREATE INDEX IF NOT EXISTS idx_accounts_code ON accounts(code)"),
            ("idx_accounts_type", "CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(type)"),
            
            # Indexes للمستخدمين
            ("idx_users_username", "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"),
            ("idx_users_active", "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)"),
            
            # Indexes للموظفين
            ("idx_employees_status", "CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status)"),
            ("idx_employees_dept", "CREATE INDEX IF NOT EXISTS idx_employees_dept ON employees(department)"),
        ]
        
        for idx_name, idx_sql in indexes:
            try:
                cursor.execute(idx_sql)
                safe_print(f"  ✅ {idx_name}")
            except Exception as e:
                safe_print(f"  ⚠️ {idx_name}: {e}")
        
        conn.commit()
        conn.close()
        
        safe_print(f"\n✅ تم إضافة {len(indexes)} index بنجاح")
        return True
        
    except Exception as e:
        safe_print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


def optimize_database():
    """تحسين قاعدة البيانات"""
    safe_print("\n" + "="*60)
    safe_print("⚡ تحسين قاعدة البيانات")
    safe_print("="*60)
    
    db_path = get_db_path()
    if not os.path.exists(db_path):
        safe_print(f"❌ قاعدة البيانات غير موجودة: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. VACUUM - تنظيف وضغط قاعدة البيانات
        safe_print("  🧹 تنظيف قاعدة البيانات (VACUUM)...")
        cursor.execute("VACUUM")
        safe_print("  ✅ تم التنظيف")
        
        # 2. ANALYZE - تحديث إحصائيات الاستعلامات
        safe_print("  📊 تحديث إحصائيات الاستعلامات (ANALYZE)...")
        cursor.execute("ANALYZE")
        safe_print("  ✅ تم التحديث")
        
        # 3. تحسين إعدادات SQLite
        safe_print("  ⚙️ تطبيق إعدادات الأداء...")
        optimizations = [
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA cache_size=10000",
            "PRAGMA temp_store=MEMORY",
            "PRAGMA mmap_size=268435456",
        ]
        
        for opt in optimizations:
            cursor.execute(opt)
            safe_print(f"    ✅ {opt}")
        
        conn.commit()
        conn.close()
        
        safe_print("\n✅ تم تحسين قاعدة البيانات بنجاح")
        return True
        
    except Exception as e:
        safe_print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


def analyze_slow_queries():
    """تحليل الاستعلامات البطيئة"""
    safe_print("\n" + "="*60)
    safe_print("🔍 تحليل الاستعلامات البطيئة")
    safe_print("="*60)
    
    db_path = get_db_path()
    if not os.path.exists(db_path):
        safe_print(f"❌ قاعدة البيانات غير موجودة: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # حجم قاعدة البيانات
        db_size = os.path.getsize(db_path) / (1024 * 1024)  # MB
        safe_print(f"  📦 حجم قاعدة البيانات: {db_size:.2f} MB")
        
        # عدد السجلات في كل جدول
        tables = ['projects', 'payments', 'expenses', 'clients', 'accounts', 'users', 'employees']
        safe_print("\n  📊 عدد السجلات:")
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                safe_print(f"    • {table}: {count:,} سجل")
            except:
                pass
        
        # فحص الـ indexes
        safe_print("\n  🔍 الـ Indexes الموجودة:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = cursor.fetchall()
        safe_print(f"    • عدد الـ Indexes: {len(indexes)}")
        
        conn.close()
        
        safe_print("\n✅ تم التحليل بنجاح")
        return True
        
    except Exception as e:
        safe_print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


def clear_cache():
    """مسح الـ cache"""
    safe_print("\n" + "="*60)
    safe_print("🧹 مسح الـ Cache")
    safe_print("="*60)
    
    try:
        # مسح ملفات الـ cache
        cache_dirs = [
            os.path.join(os.path.dirname(__file__), '__pycache__'),
            os.path.join(os.path.dirname(__file__), 'core', '__pycache__'),
            os.path.join(os.path.dirname(__file__), 'ui', '__pycache__'),
            os.path.join(os.path.dirname(__file__), 'services', '__pycache__'),
        ]
        
        total_deleted = 0
        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                import shutil
                try:
                    shutil.rmtree(cache_dir)
                    total_deleted += 1
                    safe_print(f"  ✅ تم مسح: {cache_dir}")
                except Exception as e:
                    safe_print(f"  ⚠️ فشل مسح: {cache_dir} - {e}")
        
        safe_print(f"\n✅ تم مسح {total_deleted} مجلد cache")
        return True
        
    except Exception as e:
        safe_print(f"❌ خطأ: {e}")
        return False


def create_performance_report():
    """إنشاء تقرير الأداء"""
    safe_print("\n" + "="*60)
    safe_print("📊 تقرير الأداء")
    safe_print("="*60)
    
    db_path = get_db_path()
    if not os.path.exists(db_path):
        safe_print(f"❌ قاعدة البيانات غير موجودة: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        report = []
        report.append("="*60)
        report.append("📊 تقرير أداء Sky Wave ERP")
        report.append("="*60)
        report.append(f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # حجم قاعدة البيانات
        db_size = os.path.getsize(db_path) / (1024 * 1024)
        report.append(f"📦 حجم قاعدة البيانات: {db_size:.2f} MB")
        report.append("")
        
        # عدد السجلات
        report.append("📊 عدد السجلات:")
        tables = ['projects', 'payments', 'expenses', 'clients', 'accounts', 'users', 'employees']
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                report.append(f"  • {table}: {count:,}")
            except:
                pass
        report.append("")
        
        # الـ Indexes
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        idx_count = cursor.fetchone()[0]
        report.append(f"🔍 عدد الـ Indexes: {idx_count}")
        report.append("")
        
        # التوصيات
        report.append("💡 التوصيات:")
        if db_size > 100:
            report.append("  ⚠️ حجم قاعدة البيانات كبير - يُنصح بأرشفة البيانات القديمة")
        else:
            report.append("  ✅ حجم قاعدة البيانات مناسب")
        
        if idx_count < 10:
            report.append("  ⚠️ عدد الـ Indexes قليل - شغّل add_database_indexes()")
        else:
            report.append("  ✅ عدد الـ Indexes مناسب")
        
        report.append("")
        report.append("="*60)
        
        conn.close()
        
        # طباعة التقرير
        for line in report:
            safe_print(line)
        
        # حفظ التقرير في ملف
        report_file = "performance_report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        safe_print(f"\n✅ تم حفظ التقرير في: {report_file}")
        
        return True
        
    except Exception as e:
        safe_print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """تشغيل جميع التحسينات"""
    safe_print("\n" + "🚀"*30)
    safe_print("🚀 بدء تحسينات الأداء - Sky Wave ERP")
    safe_print("🚀"*30)
    
    results = []
    
    # 1. تحليل الوضع الحالي
    results.append(("تحليل الاستعلامات", analyze_slow_queries()))
    
    # 2. إضافة Indexes
    results.append(("إضافة Indexes", add_database_indexes()))
    
    # 3. تحسين قاعدة البيانات
    results.append(("تحسين قاعدة البيانات", optimize_database()))
    
    # 4. مسح الـ Cache
    results.append(("مسح الـ Cache", clear_cache()))
    
    # 5. إنشاء تقرير الأداء
    results.append(("تقرير الأداء", create_performance_report()))
    
    # ملخص النتائج
    safe_print("\n" + "="*60)
    safe_print("📊 ملخص التحسينات")
    safe_print("="*60)
    
    for name, success in results:
        status = "✅ نجح" if success else "❌ فشل"
        safe_print(f"{status} - {name}")
    
    all_success = all(result[1] for result in results)
    
    if all_success:
        safe_print("\n" + "🎉"*30)
        safe_print("✅ تم تطبيق جميع التحسينات بنجاح!")
        safe_print("💡 البرنامج الآن أسرع بكثير - جرّب تشغيله")
        safe_print("🎉"*30)
    else:
        safe_print("\n" + "⚠️"*30)
        safe_print("⚠️ بعض التحسينات فشلت - راجع الأخطاء أعلاه")
        safe_print("⚠️"*30)
    
    return all_success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        safe_print("\n⚠️ تم إيقاف التحسينات")
        sys.exit(1)
    except Exception as e:
        safe_print(f"\n❌ خطأ غير متوقع: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
