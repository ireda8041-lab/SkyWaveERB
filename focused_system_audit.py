#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فحص محدود للملفات الأساسية فقط
Focused audit for core files only
"""

import sys
import os
import ast
import re
import sqlite3
import json
import traceback
from pathlib import Path
from typing import List, Dict, Any, Tuple
import importlib.util

# تعيين الترميز للـ console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class FocusedAuditor:
    """فاحص محدود للملفات الأساسية"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.project_root = Path.cwd()
        
        # الملفات والمجلدات المراد فحصها فقط
        self.core_folders = ['core', 'services', 'ui']
        self.core_files = ['main.py', 'version.py', 'version.json']
        
    def log_error(self, message: str, file_path: str = None):
        """تسجيل خطأ"""
        error = {"type": "ERROR", "message": message, "file": file_path}
        self.errors.append(error)
        print(f"❌ ERROR: {message}" + (f" في {file_path}" if file_path else ""))
        
    def log_warning(self, message: str, file_path: str = None):
        """تسجيل تحذير"""
        warning = {"type": "WARNING", "message": message, "file": file_path}
        self.warnings.append(warning)
        print(f"⚠️ WARNING: {message}" + (f" في {file_path}" if file_path else ""))
        
    def log_info(self, message: str):
        """تسجيل معلومة"""
        info = {"type": "INFO", "message": message}
        self.info.append(info)
        print(f"ℹ️ INFO: {message}")

    def get_core_python_files(self) -> List[Path]:
        """الحصول على ملفات Python الأساسية فقط"""
        python_files = []
        
        # ملفات Python في الجذر
        for file_name in self.core_files:
            if file_name.endswith('.py'):
                file_path = self.project_root / file_name
                if file_path.exists():
                    python_files.append(file_path)
        
        # ملفات Python في المجلدات الأساسية
        for folder in self.core_folders:
            folder_path = self.project_root / folder
            if folder_path.exists():
                python_files.extend(list(folder_path.glob('*.py')))
        
        return python_files

    def check_python_syntax(self) -> bool:
        """فحص صحة بناء الجملة Python للملفات الأساسية"""
        print("\n🔍 فحص صحة بناء الجملة Python (الملفات الأساسية)...")
        print("=" * 60)
        
        python_files = self.get_core_python_files()
        syntax_errors = 0
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # فحص بناء الجملة
                ast.parse(content)
                
            except SyntaxError as e:
                self.log_error(f"خطأ في بناء الجملة: {e}", str(py_file))
                syntax_errors += 1
            except UnicodeDecodeError as e:
                self.log_error(f"خطأ في الترميز: {e}", str(py_file))
                syntax_errors += 1
            except Exception as e:
                self.log_error(f"خطأ غير متوقع: {e}", str(py_file))
                syntax_errors += 1
        
        if syntax_errors == 0:
            self.log_info(f"✅ جميع الملفات الأساسية ({len(python_files)}) صحيحة نحوياً")
            return True
        else:
            self.log_error(f"وجد {syntax_errors} أخطاء نحوية في الملفات الأساسية")
            return False

    def check_database_patterns(self) -> bool:
        """فحص أنماط قاعدة البيانات المشكلة في الملفات الأساسية"""
        print("\n🔍 فحص أنماط قاعدة البيانات (الملفات الأساسية)...")
        print("=" * 60)
        
        python_files = self.get_core_python_files()
        pattern_errors = 0
        
        # الأنماط المشكلة
        problematic_patterns = [
            r'\bif\s+(?:self\.)?(?:repo|db|database|connection)(?:\s*[^=\s]|:)',
            r'\bif\s+not\s+(?:self\.)?(?:repo|db|database|connection)\b',
            r'\band\s+(?:self\.)?(?:repo|db|database|connection)\b',
            r'\bor\s+(?:self\.)?(?:repo|db|database|connection)\b',
        ]
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for i, line in enumerate(content.split('\n'), 1):
                    for pattern in problematic_patterns:
                        if re.search(pattern, line):
                            # تجاهل الحالات المُصلحة
                            if 'is not None' in line or 'is None' in line:
                                continue
                            
                            # تجاهل التعليقات
                            if line.strip().startswith('#'):
                                continue
                            
                            # تجاهل الأنماط الآمنة
                            if any(safe in line for safe in ['.online', '.get_', 'hasattr', 'getattr', '.is_online()', 'if repo.is_online()']):
                                continue
                            
                            self.log_error(
                                f"نمط مشكل في السطر {i}: {line.strip()}", 
                                str(py_file)
                            )
                            pattern_errors += 1
                            
            except Exception as e:
                self.log_error(f"خطأ في فحص الأنماط: {e}", str(py_file))
                pattern_errors += 1
        
        if pattern_errors == 0:
            self.log_info("✅ لا توجد أنماط مشكلة في الملفات الأساسية")
            return True
        else:
            self.log_error(f"وجد {pattern_errors} أنماط مشكلة في الملفات الأساسية")
            return False

    def test_core_functionality(self) -> bool:
        """اختبار الوظائف الأساسية"""
        print("\n🧪 اختبار الوظائف الأساسية...")
        print("=" * 60)
        
        try:
            # محاولة استيراد الوحدات الأساسية
            sys.path.insert(0, str(self.project_root))
            
            from core.repository import Repository
            from core.config import Config
            
            # اختبار Repository
            repo = Repository()
            self.log_info("✅ Repository يعمل بشكل صحيح")
            
            # اختبار Config
            config = Config()
            self.log_info("✅ Config يعمل بشكل صحيح")
            
            # اختبار الاتصال بقاعدة البيانات
            cursor = repo.get_cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            self.log_info(f"✅ قاعدة البيانات تحتوي على {table_count} جدول")
            
            return True
            
        except Exception as e:
            self.log_error(f"فشل اختبار الوظائف الأساسية: {e}")
            self.log_error(f"تفاصيل الخطأ: {traceback.format_exc()}")
            return False

    def check_main_py(self) -> bool:
        """فحص ملف main.py"""
        print("\n🔍 فحص ملف main.py...")
        print("=" * 60)
        
        main_file = self.project_root / 'main.py'
        
        if not main_file.exists():
            self.log_error("ملف main.py غير موجود")
            return False
        
        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # فحص الاستيرادات الأساسية
            required_imports = ['sys', 'PyQt6']
            for imp in required_imports:
                if imp not in content:
                    self.log_warning(f"استيراد مفقود في main.py: {imp}")
            
            # فحص وجود if __name__ == '__main__'
            if "__name__ == '__main__'" in content:
                self.log_info("✅ main.py يحتوي على if __name__ == '__main__'")
            else:
                self.log_warning("main.py لا يحتوي على if __name__ == '__main__'")
            
            self.log_info("✅ ملف main.py صحيح")
            return True
            
        except Exception as e:
            self.log_error(f"خطأ في main.py: {e}")
            return False

    def check_version_files(self) -> bool:
        """فحص ملفات الإصدار"""
        print("\n🔍 فحص ملفات الإصدار...")
        print("=" * 60)
        
        version_files = {
            'version.json': None,
            'version.py': None
        }
        
        # قراءة version.json
        try:
            with open(self.project_root / 'version.json', 'r', encoding='utf-8') as f:
                version_data = json.load(f)
                version_files['version.json'] = version_data.get('version')
                self.log_info(f"✅ version.json: {version_files['version.json']}")
        except Exception as e:
            self.log_error(f"خطأ في قراءة version.json: {e}")
            return False
        
        # قراءة version.py
        try:
            with open(self.project_root / 'version.py', 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    version_files['version.py'] = match.group(1)
                    self.log_info(f"✅ version.py: {version_files['version.py']}")
        except Exception as e:
            self.log_error(f"خطأ في قراءة version.py: {e}")
            return False
        
        # مقارنة الإصدارات
        versions = list(version_files.values())
        if len(set(versions)) == 1:
            self.log_info(f"✅ الإصدارات متناسقة: {versions[0]}")
            return True
        else:
            self.log_error(f"الإصدارات غير متناسقة: {version_files}")
            return False

    def run_focused_audit(self) -> bool:
        """تشغيل الفحص المحدود"""
        print("🔍 بدء الفحص المحدود للملفات الأساسية...")
        print("=" * 80)
        
        tests = [
            ("فحص بناء الجملة Python", self.check_python_syntax),
            ("فحص أنماط قاعدة البيانات", self.check_database_patterns),
            ("فحص ملف main.py", self.check_main_py),
            ("فحص ملفات الإصدار", self.check_version_files),
            ("اختبار الوظائف الأساسية", self.test_core_functionality),
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    passed_tests += 1
                    print(f"✅ {test_name}: نجح")
                else:
                    print(f"❌ {test_name}: فشل")
            except Exception as e:
                print(f"💥 {test_name}: خطأ غير متوقع - {e}")
                self.log_error(f"خطأ في اختبار {test_name}: {e}")
        
        print("\n" + "=" * 80)
        print("📊 ملخص الفحص المحدود")
        print("=" * 80)
        print(f"الاختبارات الناجحة: {passed_tests}/{total_tests}")
        print(f"الأخطاء: {len(self.errors)}")
        print(f"التحذيرات: {len(self.warnings)}")
        print(f"المعلومات: {len(self.info)}")
        print(f"الحالة العامة: {'✅ نجح' if len(self.errors) == 0 else '❌ فشل'}")
        
        return len(self.errors) == 0

def main():
    """الدالة الرئيسية"""
    auditor = FocusedAuditor()
    success = auditor.run_focused_audit()
    
    if success:
        print("\n🎉 الملفات الأساسية سليمة ولا توجد أخطاء!")
        return 0
    else:
        print("\n⚠️ وجدت أخطاء في الملفات الأساسية تحتاج إلى إصلاح!")
        return 1

if __name__ == '__main__':
    sys.exit(main())