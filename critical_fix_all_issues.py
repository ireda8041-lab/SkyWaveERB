#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إصلاح شامل وحرج لجميع المشاكل المكتشفة
Critical comprehensive fix for all detected issues
"""

import sys
import os
import re
from pathlib import Path
import codecs

# تعيين الترميز للـ console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class CriticalSystemFixer:
    """مصلح النظام الحرج"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.fixed_files = 0
        self.errors = 0
        
    def remove_bom_from_file(self, file_path: Path) -> bool:
        """إزالة BOM من ملف"""
        try:
            # قراءة الملف
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # فحص وجود BOM
            if content.startswith(codecs.BOM_UTF8):
                print(f"🔧 إزالة BOM من: {file_path}")
                # إزالة BOM
                content = content[len(codecs.BOM_UTF8):]
                
                # كتابة الملف بدون BOM
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                self.fixed_files += 1
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ خطأ في إزالة BOM من {file_path}: {e}")
            self.errors += 1
            return False
    
    def fix_database_patterns_in_file(self, file_path: Path) -> bool:
        """إصلاح أنماط قاعدة البيانات في ملف"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # الأنماط المشكلة والحلول
            patterns = [
                # الأنماط الأساسية
                (r'\bif\s+(self\.repo)(?!\s*is\s+not\s+None)(?!\s*is\s+None):', r'if \1 is not None:'),
                (r'\bif\s+(repo)(?!\s*is\s+not\s+None)(?!\s*is\s+None)(?!\w):', r'if \1 is not None:'),
                (r'\bif\s+(self\.db)(?!\s*is\s+not\s+None)(?!\s*is\s+None):', r'if \1 is not None:'),
                (r'\bif\s+(database)(?!\s*is\s+not\s+None)(?!\s*is\s+None)(?!\w):', r'if \1 is not None:'),
                (r'\bif\s+(connection)(?!\s*is\s+not\s+None)(?!\s*is\s+None)(?!\w):', r'if \1 is not None:'),
                
                # الأنماط المنفية
                (r'\bif\s+not\s+(self\.repo)\b(?!\s*is\s+None)', r'if \1 is None'),
                (r'\bif\s+not\s+(repo)\b(?!\s*is\s+None)(?!\w)', r'if \1 is None'),
                (r'\bif\s+not\s+(self\.db)\b(?!\s*is\s+None)', r'if \1 is None'),
                (r'\bif\s+not\s+(database)\b(?!\s*is\s+None)(?!\w)', r'if \1 is None'),
                (r'\bif\s+not\s+(connection)\b(?!\s*is\s+None)(?!\w)', r'if \1 is None'),
                
                # أنماط and
                (r'\band\s+(self\.repo)\b(?!\s*is\s+not\s+None)(?!\s*is\s+None)', r'and \1 is not None'),
                (r'\band\s+(repo)\b(?!\s*is\s+not\s+None)(?!\s*is\s+None)(?!\w)', r'and \1 is not None'),
                (r'\band\s+(self\.db)\b(?!\s*is\s+not\s+None)(?!\s*is\s+None)', r'and \1 is not None'),
                (r'\band\s+(database)\b(?!\s*is\s+not\s+None)(?!\s*is\s+None)(?!\w)', r'and \1 is not None'),
                (r'\band\s+(connection)\b(?!\s*is\s+not\s+None)(?!\s*is\s+None)(?!\w)', r'and \1 is not None'),
                
                # أنماط or
                (r'\bor\s+(self\.repo)\b(?!\s*is\s+not\s+None)(?!\s*is\s+None)', r'or \1 is not None'),
                (r'\bor\s+(repo)\b(?!\s*is\s+not\s+None)(?!\s*is\s+None)(?!\w)', r'or \1 is not None'),
                (r'\bor\s+(self\.db)\b(?!\s*is\s+not\s+None)(?!\s*is\s+None)', r'or \1 is not None'),
                (r'\bor\s+(database)\b(?!\s*is\s+not\s+None)(?!\s*is\s+None)(?!\w)', r'or \1 is not None'),
                (r'\bor\s+(connection)\b(?!\s*is\s+not\s+None)(?!\s*is\s+None)(?!\w)', r'or \1 is not None'),
                
                # أنماط خاصة
                (r'return\s+(self\.repo)\.online\s+if\s+(self\.repo)\s+else\s+False', r'return \1.online if \2 is not None else False'),
                (r'return\s+(repo)\.online\s+if\s+(repo)\s+else\s+False', r'return \1.online if \2 is not None else False'),
            ]
            
            # تطبيق الإصلاحات
            for pattern, replacement in patterns:
                content = re.sub(pattern, replacement, content)
            
            # حفظ الملف إذا تم التعديل
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"🔧 إصلاح أنماط قاعدة البيانات في: {file_path}")
                self.fixed_files += 1
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ خطأ في إصلاح الأنماط في {file_path}: {e}")
            self.errors += 1
            return False
    
    def fix_main_py(self):
        """إصلاح ملف main.py"""
        main_file = self.project_root / 'main.py'
        
        if not main_file.exists():
            return
        
        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # إضافة if __name__ == '__main__' إذا لم يكن موجوداً
            if "__name__ == '__main__'" not in content:
                # البحث عن آخر سطر في الملف
                lines = content.split('\n')
                
                # إضافة الحماية
                if lines and lines[-1].strip():
                    lines.append('')
                
                lines.append("if __name__ == '__main__':")
                lines.append("    main()")
                
                content = '\n'.join(lines)
                
                with open(main_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"🔧 إضافة if __name__ == '__main__' إلى: {main_file}")
                self.fixed_files += 1
                
        except Exception as e:
            print(f"❌ خطأ في إصلاح main.py: {e}")
            self.errors += 1
    
    def fix_all_python_files(self):
        """إصلاح جميع ملفات Python"""
        print("🔧 بدء الإصلاح الشامل...")
        print("=" * 60)
        
        # الحصول على ملفات Python الأساسية فقط (تجاهل .venv و dist)
        python_files = []
        for folder in ['core', 'services', 'ui', '.']:
            folder_path = self.project_root / folder
            if folder_path.exists():
                if folder == '.':
                    # ملفات Python في الجذر
                    python_files.extend([f for f in folder_path.glob('*.py')])
                else:
                    # ملفات Python في المجلدات الفرعية
                    python_files.extend(list(folder_path.rglob('*.py')))
        
        # إزالة الملفات المكررة
        python_files = list(set(python_files))
        
        print(f"📁 وجد {len(python_files)} ملف Python للإصلاح")
        
        for py_file in python_files:
            # تجاهل ملفات معينة
            if any(skip in str(py_file) for skip in ['.venv', 'dist', '__pycache__', '.git']):
                continue
            
            # إزالة BOM
            self.remove_bom_from_file(py_file)
            
            # إصلاح أنماط قاعدة البيانات
            self.fix_database_patterns_in_file(py_file)
        
        # إصلاح main.py خصيصاً
        self.fix_main_py()
    
    def run_critical_fix(self):
        """تشغيل الإصلاح الحرج"""
        print("🚨 بدء الإصلاح الحرج للنظام...")
        print("=" * 80)
        
        self.fix_all_python_files()
        
        print("\n" + "=" * 80)
        print("📊 ملخص الإصلاح الحرج")
        print("=" * 80)
        print(f"الملفات المُصلحة: {self.fixed_files}")
        print(f"الأخطاء: {self.errors}")
        
        if self.errors == 0:
            print("✅ تم الإصلاح الحرج بنجاح!")
            return True
        else:
            print("⚠️ تم الإصلاح مع بعض الأخطاء")
            return False

def main():
    """الدالة الرئيسية"""
    fixer = CriticalSystemFixer()
    success = fixer.run_critical_fix()
    
    if success:
        print("\n🎉 النظام مُصلح ومستعد للاختبار!")
        return 0
    else:
        print("\n⚠️ تم الإصلاح مع بعض المشاكل")
        return 1

if __name__ == '__main__':
    sys.exit(main())