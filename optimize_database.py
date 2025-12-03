#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚡ سكريبت تحسين قاعدة البيانات
يقوم بإضافة indexes وتنظيف البيانات لتسريع البرنامج
"""

import sqlite3
import os

DB_FILE = "skywave_local.db"

def optimize_database():
    """تحسين قاعدة البيانات بإضافة indexes"""
    
    if not os.path.exists(DB_FILE):
        print(f"❌ ملف قاعدة البيانات غير موجود: {DB_FILE}")
        return False
    
    print(f"⚡ جاري تحسين قاعدة البيانات: {DB_FILE}")
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # إضافة indexes للجداول الرئيسية
        indexes = [
            # Clients
            ("idx_clients_status", "CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status)"),
            ("idx_clients_name", "CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name)"),
            
            # Projects
            ("idx_projects_client", "CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id)"),
            ("idx_projects_status", "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)"),
            ("idx_projects_name", "CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)"),
            
            # Payments
            ("idx_payments_project", "CREATE INDEX IF NOT EXISTS idx_payments_project ON payments(project_id)"),
            ("idx_payments_client", "CREATE INDEX IF NOT EXISTS idx_payments_client ON payments(client_id)"),
            ("idx_payments_date", "CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(date)"),
            
            # Invoices
            ("idx_invoices_client", "CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id)"),
            ("idx_invoices_project", "CREATE INDEX IF NOT EXISTS idx_invoices_project ON invoices(project_id)"),
            ("idx_invoices_status", "CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status)"),
            
            # Expenses
            ("idx_expenses_project", "CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(project_id)"),
            ("idx_expenses_date", "CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)"),
            
            # Journal Entries
            ("idx_journal_date", "CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(date)"),
            ("idx_journal_related", "CREATE INDEX IF NOT EXISTS idx_journal_related ON journal_entries(related_document_id)"),
        ]
        
        created_count = 0
        for index_name, sql in indexes:
            try:
                cursor.execute(sql)
                created_count += 1
                print(f"  ✅ تم إنشاء index: {index_name}")
            except Exception as e:
                print(f"  ⚠️  Index موجود بالفعل: {index_name}")
        
        # تنظيف قاعدة البيانات
        print("\n⚡ جاري تنظيف قاعدة البيانات...")
        cursor.execute("VACUUM")
        
        # تحليل الجداول لتحسين الأداء
        print("⚡ جاري تحليل الجداول...")
        cursor.execute("ANALYZE")
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ تم تحسين قاعدة البيانات بنجاح!")
        print(f"   - تم إنشاء {created_count} index")
        print(f"   - تم تنظيف وتحليل قاعدة البيانات")
        
        return True
        
    except Exception as e:
        print(f"❌ خطأ في تحسين قاعدة البيانات: {e}")
        return False

def get_database_stats():
    """عرض إحصائيات قاعدة البيانات"""
    
    if not os.path.exists(DB_FILE):
        print(f"❌ ملف قاعدة البيانات غير موجود: {DB_FILE}")
        return
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        print("\n📊 إحصائيات قاعدة البيانات:")
        print("=" * 50)
        
        tables = [
            "clients", "projects", "payments", "invoices", 
            "expenses", "services", "accounts", "journal_entries"
        ]
        
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table:20s}: {count:6d} سجل")
            except:
                pass
        
        # حجم قاعدة البيانات
        db_size = os.path.getsize(DB_FILE) / (1024 * 1024)  # MB
        print(f"\n  حجم قاعدة البيانات: {db_size:.2f} MB")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ خطأ في جلب الإحصائيات: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("⚡ أداة تحسين قاعدة بيانات Sky Wave ERP")
    print("=" * 50)
    print()
    
    # عرض الإحصائيات قبل التحسين
    get_database_stats()
    
    print()
    input("اضغط Enter للبدء في التحسين...")
    print()
    
    # تحسين قاعدة البيانات
    if optimize_database():
        print()
        # عرض الإحصائيات بعد التحسين
        get_database_stats()
    
    print()
    input("اضغط Enter للخروج...")
