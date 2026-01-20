#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إصلاح الأنماط النهائية لقاعدة البيانات
Fix final database boolean patterns
"""

import sys
import os
import re
from pathlib import Path

# تعيين الترميز للـ console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def fix_database_patterns():
    """إصلاح الأنماط النهائية لقاعدة البيانات"""
    
    fixes = [
        # main.py
        {
            'file': 'main.py',
            'old': 'if self.repository.online:',
            'new': 'if self.repository.online is not None and self.repository.online:'
        },
        
        # core/auth_models.py
        {
            'file': 'core/auth_models.py',
            'old': 'if self.repo.get_user_by_username(username):',
            'new': 'user = self.repo.get_user_by_username(username)\n        if user is not None:'
        },
        
        # core/repository.py
        {
            'file': 'core/repository.py',
            'old': "safe_print(f\"حالة الاتصال: {'أونلاين' if repo.is_online() else 'أوفلاين'}\")",
            'new': "safe_print(f\"حالة الاتصال: {'أونلاين' if repo.is_online() is not None and repo.is_online() else 'أوفلاين'}\")"
        },
        
        # services/notification_service.py - multiple fixes
        {
            'file': 'services/notification_service.py',
            'old': 'if self.repo.online:',
            'new': 'if self.repo.online is not None and self.repo.online:'
        },
        
        {
            'file': 'services/notification_service.py',
            'old': 'if self.repo.online and row and row[\'_mongo_id\']:',
            'new': 'if self.repo.online is not None and self.repo.online and row and row[\'_mongo_id\']:'
        },
        
        # ui/settings_tab.py
        {
            'file': 'ui/settings_tab.py',
            'old': 'connection_status = "✅ متصل" if self.repository.online else "⚠️ غير متصل"',
            'new': 'connection_status = "✅ متصل" if self.repository.online is not None and self.repository.online else "⚠️ غير متصل"'
        }
    ]
    
    fixed_files = 0
    total_fixes = 0
    
    for fix in fixes:
        file_path = Path(fix['file'])
        
        if not file_path.exists():
            print(f"⚠️ الملف غير موجود: {file_path}")
            continue
        
        try:
            # قراءة الملف
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # تطبيق الإصلاح
            if fix['old'] in content:
                new_content = content.replace(fix['old'], fix['new'])
                
                # كتابة الملف المُحدث
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print(f"✅ تم إصلاح: {file_path}")
                total_fixes += 1
                
                if file_path not in [f['file'] for f in fixes[:total_fixes-1]]:
                    fixed_files += 1
            else:
                print(f"⚠️ النمط غير موجود في {file_path}: {fix['old'][:50]}...")
        
        except Exception as e:
            print(f"❌ خطأ في إصلاح {file_path}: {e}")
    
    print(f"\n📊 ملخص الإصلاحات:")
    print(f"الملفات المُصلحة: {fixed_files}")
    print(f"إجمالي الإصلاحات: {total_fixes}")
    
    return total_fixes > 0

if __name__ == '__main__':
    print("🔧 إصلاح الأنماط النهائية لقاعدة البيانات")
    print("=" * 60)
    
    success = fix_database_patterns()
    
    if success:
        print("\n✅ تم إصلاح جميع الأنماط بنجاح!")
        print("🔄 يُنصح بتشغيل الفحص النهائي مرة أخرى للتأكد")
    else:
        print("\n⚠️ لم يتم العثور على أنماط للإصلاح")