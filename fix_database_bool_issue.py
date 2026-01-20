#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إصلاح مشكلة Database objects do not implement truth value testing
استبدال جميع حالات if repo is not None: بـ if repo is not None:
"""

import os
import re
import sys
from pathlib import Path

# تعيين الترميز للـ console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def fix_file(file_path: Path) -> bool:
    """إصلاح ملف واحد"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # الأنماط التي نريد إصلاحها
        patterns = [
            # if self.repo is not None:
            (r'\bif self\.repo:', 'if self.repo is not None:'),
            # if repo is not None:
            (r'\bif repo:', 'if repo is not None:'),
            # if self.db is not None:
            (r'\bif self\.db:', 'if self.db is not None:'),
            # if database is not None:
            (r'\bif database:', 'if database is not None:'),
            # if self.repo is None
            (r'\bif not self\.repo\b', 'if self.repo is None'),
            # if repo is None
            (r'\bif not repo\b', 'if repo is None'),
            # if self.db is None
            (r'\bif not self\.db\b', 'if self.db is None'),
            # if database is None
            (r'\bif not database\b', 'if database is None'),
            # and self.repo is not None
            (r'\band self\.repo\b', 'and self.repo is not None'),
            # and repo is not None
            (r'\band repo\b(?!\w)', 'and repo is not None'),
            # or self.repo is not None
            (r'\bor self\.repo\b', 'or self.repo is not None'),
            # or repo is not None
            (r'\bor repo\b(?!\w)', 'or repo is not None'),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        # حفظ الملف إذا تم التعديل
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ تم إصلاح: {file_path}")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ خطأ في {file_path}: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    print("🔧 بدء إصلاح مشكلة Database bool()...")
    print("=" * 60)
    
    # المجلدات المراد فحصها
    folders = ['core', 'services', 'ui']
    
    fixed_count = 0
    total_files = 0
    
    for folder in folders:
        folder_path = Path(folder)
        if not folder_path.exists():
            continue
        
        print(f"\n📁 فحص مجلد: {folder}")
        
        for py_file in folder_path.rglob('*.py'):
            total_files += 1
            if fix_file(py_file):
                fixed_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ تم الانتهاء!")
    print(f"📊 الملفات المفحوصة: {total_files}")
    print(f"🔧 الملفات المصلحة: {fixed_count}")

if __name__ == '__main__':
    main()
