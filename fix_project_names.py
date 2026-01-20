#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 إصلاح أسماء المشاريع في قاعدة البيانات
يوحد أسماء المشاريع بين جدول projects وجدول payments
"""

import sqlite3
import sys
from datetime import datetime

try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


def fix_project_names():
    """توحيد أسماء المشاريع في قاعدة البيانات"""
    safe_print("\n" + "="*60)
    safe_print("🔧 بدء إصلاح أسماء المشاريع")
    safe_print("="*60)
    
    db_path = "skywave_local.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. جلب كل أسماء المشاريع من جدول projects
        cursor.execute("SELECT DISTINCT name FROM projects")
        project_names = [row[0] for row in cursor.fetchall()]
        
        safe_print(f"\n📊 عدد المشاريع: {len(project_names)}")
        
        # 2. جلب كل أسماء المشاريع من جدول payments
        cursor.execute("SELECT DISTINCT project_id FROM payments")
        payment_project_names = [row[0] for row in cursor.fetchall()]
        
        safe_print(f"📊 عدد المشاريع في الدفعات: {len(payment_project_names)}")
        
        # 3. إيجاد المشاريع اللي أسماؤها مختلفة
        mismatches = []
        for payment_name in payment_project_names:
            # البحث عن مشروع مشابه
            found = False
            for project_name in project_names:
                if payment_name == project_name:
                    found = True
                    break
                # البحث المرن
                clean_payment = payment_name.strip().replace('  ', ' ')
                clean_project = project_name.strip().replace('  ', ' ')
                
                # إزالة الرموز الخاصة للمقارنة
                payment_normalized = clean_payment.replace('/', '').replace('-', '').replace('_', '')
                project_normalized = clean_project.replace('/', '').replace('-', '').replace('_', '')
                
                if payment_normalized == project_normalized:
                    mismatches.append((payment_name, project_name))
                    found = True
                    break
            
            if not found:
                safe_print(f"⚠️ دفعات لمشروع غير موجود: [{payment_name}]")
        
        # 4. إصلاح الأسماء المختلفة
        if mismatches:
            safe_print(f"\n🔧 تم العثور على {len(mismatches)} اختلاف في الأسماء:")
            
            for payment_name, correct_name in mismatches:
                safe_print(f"\n  📝 إصلاح:")
                safe_print(f"    من: [{payment_name}]")
                safe_print(f"    إلى: [{correct_name}]")
                
                # تحديث اسم المشروع في جدول payments
                cursor.execute(
                    "UPDATE payments SET project_id = ? WHERE project_id = ?",
                    (correct_name, payment_name)
                )
                updated = cursor.rowcount
                safe_print(f"    ✅ تم تحديث {updated} دفعة")
            
            conn.commit()
            safe_print(f"\n✅ تم إصلاح {len(mismatches)} اختلاف بنجاح")
        else:
            safe_print("\n✅ جميع أسماء المشاريع متطابقة")
        
        # 5. التحقق النهائي
        safe_print("\n" + "="*60)
        safe_print("📊 التحقق النهائي")
        safe_print("="*60)
        
        cursor.execute("""
            SELECT p.name, COUNT(pay.id) as payment_count
            FROM projects p
            LEFT JOIN payments pay ON p.name = pay.project_id
            GROUP BY p.name
            ORDER BY payment_count DESC
            LIMIT 10
        """)
        
        safe_print("\n🏆 أكثر 10 مشاريع لديها دفعات:")
        for row in cursor.fetchall():
            project_name, payment_count = row
            safe_print(f"  • {project_name}: {payment_count} دفعة")
        
        conn.close()
        
        safe_print("\n" + "="*60)
        safe_print("✅ اكتمل الإصلاح بنجاح")
        safe_print("="*60)
        
        return True
        
    except Exception as e:
        safe_print(f"\n❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = fix_project_names()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        safe_print("\n⚠️ تم إيقاف الإصلاح")
        sys.exit(1)
    except Exception as e:
        safe_print(f"\n❌ خطأ غير متوقع: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
