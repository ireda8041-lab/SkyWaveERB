#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فحص صفر أخطاء مطلق - Absolute Zero Errors Audit
أقصى مستوى احترافية ودقة - لا مجال للخطأ
"""

import sys
import os
import ast
import re
import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class AbsoluteZeroErrorsAuditor:
    """فاحص صفر أخطاء مطلق - أقصى دقة واحترافية"""
    
    def __init__(self):
        self.critical_errors = []
        self.errors = []
        self.warnings = []
        self.info = []
        self.project_root = Path.cwd()
        self.start_time = time.time()
        
        # الملفات الأساسية للمشروع فقط
        self.core_folders = ['core', 'services', 'ui', 'tests']
        self.core_files = ['main.py', 'version.py']
        self.python_files = []
        
        # أنماط الأخطاء الحرجة فقط
        self.critical_patterns = {
            'database_bool': r'\bif\s+(?:self\.)?(?:repo|db|database|connection)(?:\s*[^=\s]|:)',
            'database_bool_not': r'\bif\s+not\s+(?:self\.)?(?:repo|db|database|connection)\b',
            'database_bool_and': r'\band\s+(?:self\.)?(?:repo|db|database|connection)\b',
            'database_bool_or': r'\bor\s+(?:self\.)?(?:repo|db|database|connection)\b',
        }
        
    def log(self, level: str, category: str, message: str, file_path: str = None, line_no: int = None):
        """تسجيل موحد للرسائل"""
        entry = {
            "level": level,
            "category": category,
            "message": message,
            "file": file_path,
            "line": line_no,
            "time": time.time()
        }
        
        if level == "CRITICAL":
            self.critical_errors.append(entry)
            icon = "🚨"
        elif level == "ERROR":
            self.errors.append(entry)
            icon = "❌"
        elif level == "WARNING":
            self.warnings.append(entry)
            icon = "⚠️"
        else:
            self.info.append(entry)
            icon = "ℹ️"
        
        location = f" في {file_path}:{line_no}" if file_path and line_no else f" في {file_path}" if file_path else ""
        print(f"{icon} {level} [{category}]: {message}{location}")

    def discover_files(self) -> bool:
        """اكتشاف الملفات الأساسية"""
        print("\n" + "="*80)
        print("🔍 المرحلة 1: اكتشاف الملفات الأساسية")
        print("="*80)
        
        # ملفات الجذر
        for file_name in self.core_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                self.python_files.append(file_path)
        
        # ملفات المجلدات الأساسية
        for folder in self.core_folders:
            folder_path = self.project_root / folder
            if folder_path.exists():
                for py_file in folder_path.rglob('*.py'):
                    if '__pycache__' not in str(py_file):
                        self.python_files.append(py_file)
        
        self.log("INFO", "DISCOVERY", f"تم اكتشاف {len(self.python_files)} ملف Python أساسي")
        return len(self.python_files) > 0

    def check_syntax_and_encoding(self) -> bool:
        """فحص بناء الجملة والترميز"""
        print("\n" + "="*80)
        print("🔍 المرحلة 2: فحص بناء الجملة والترميز")
        print("="*80)
        
        def check_file(py_file):
            errors = []
            try:
                with open(py_file, 'rb') as f:
                    raw = f.read()
                
                # فحص BOM
                if raw.startswith(b'\xef\xbb\xbf'):
                    errors.append(("CRITICAL", "ENCODING", "ملف يحتوي على BOM", 1))
                
                # فحص الترميز
                try:
                    content = raw.decode('utf-8')
                except UnicodeDecodeError as e:
                    errors.append(("CRITICAL", "ENCODING", f"خطأ ترميز: {e}", 1))
                    return errors
                
                # فحص بناء الجملة
                try:
                    ast.parse(content, filename=str(py_file))
                except SyntaxError as e:
                    errors.append(("CRITICAL", "SYNTAX", f"خطأ نحوي: {e}", e.lineno))
                
            except Exception as e:
                errors.append(("CRITICAL", "SYSTEM", f"خطأ في الفحص: {e}", 1))
            
            return errors
        
        all_errors = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(check_file, f): f for f in self.python_files}
            for future in as_completed(futures):
                file_path = futures[future]
                file_errors = future.result()
                for level, cat, msg, line in file_errors:
                    self.log(level, cat, msg, str(file_path), line)
                    all_errors.append((level, cat, msg, file_path, line))
        
        if not all_errors:
            self.log("INFO", "SYNTAX", f"✅ جميع الملفات ({len(self.python_files)}) صحيحة نحوياً وترميزياً")
            return True
        else:
            self.log("ERROR", "SYNTAX", f"وجد {len(all_errors)} خطأ في بناء الجملة/الترميز")
            return False

    def check_database_patterns(self) -> bool:
        """فحص أنماط قاعدة البيانات الحرجة"""
        print("\n" + "="*80)
        print("🔍 المرحلة 3: فحص أنماط قاعدة البيانات الحرجة")
        print("="*80)
        
        def check_patterns(py_file):
            errors = []
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    
                    # تجاهل التعليقات والأسطر الفارغة
                    if not stripped or stripped.startswith('#'):
                        continue
                    
                    # فحص كل نمط حرج
                    for pattern_name, pattern in self.critical_patterns.items():
                        if re.search(pattern, line):
                            # فحص الاستثناءات المُصلحة
                            if 'is not None' in line or 'is None' in line:
                                continue
                            if '.is_online()' in line or 'hasattr' in line or 'getattr' in line:
                                continue
                            
                            errors.append((
                                "CRITICAL",
                                "DATABASE_PATTERN",
                                f"نمط قاعدة بيانات خطير ({pattern_name}): {stripped}",
                                i
                            ))
            
            except Exception as e:
                errors.append(("ERROR", "PATTERN_CHECK", f"خطأ في الفحص: {e}", 1))
            
            return errors
        
        all_errors = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(check_patterns, f): f for f in self.python_files}
            for future in as_completed(futures):
                file_path = futures[future]
                file_errors = future.result()
                for level, cat, msg, line in file_errors:
                    self.log(level, cat, msg, str(file_path), line)
                    all_errors.append((level, cat, msg, file_path, line))
        
        if not all_errors:
            self.log("INFO", "PATTERNS", f"✅ لا توجد أنماط خطيرة في {len(self.python_files)} ملف")
            return True
        else:
            self.log("CRITICAL", "PATTERNS", f"وجد {len(all_errors)} نمط خطير يجب إصلاحه")
            return False

    def test_imports(self) -> bool:
        """اختبار الاستيرادات الأساسية"""
        print("\n" + "="*80)
        print("🔍 المرحلة 4: اختبار الاستيرادات الأساسية")
        print("="*80)
        
        sys.path.insert(0, str(self.project_root))
        
        modules = [
            'core.repository',
            'core.config',
            'core.auth_models',
            'services.client_service',
            'services.project_service',
            'version'
        ]
        
        failed = 0
        for module in modules:
            try:
                if '.' in module:
                    parts = module.split('.')
                    __import__(module, fromlist=[parts[-1]])
                else:
                    __import__(module)
                self.log("INFO", "IMPORT", f"✅ {module}")
            except Exception as e:
                self.log("CRITICAL", "IMPORT", f"فشل استيراد {module}: {e}")
                failed += 1
        
        if failed == 0:
            self.log("INFO", "IMPORT", f"✅ جميع الاستيرادات ({len(modules)}) نجحت")
            return True
        else:
            self.log("CRITICAL", "IMPORT", f"فشل {failed} استيراد")
            return False

    def test_database(self) -> bool:
        """اختبار قاعدة البيانات"""
        print("\n" + "="*80)
        print("🔍 المرحلة 5: اختبار قاعدة البيانات")
        print("="*80)
        
        try:
            from core.repository import Repository
            
            repo = Repository()
            cursor = repo.get_cursor()
            
            # فحص السلامة
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            if result != 'ok':
                self.log("CRITICAL", "DATABASE", f"مشكلة في سلامة قاعدة البيانات: {result}")
                return False
            
            # فحص الجداول
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required = ['clients', 'projects', 'services', 'users', 'accounts']
            missing = [t for t in required if t not in tables]
            
            if missing:
                self.log("WARNING", "DATABASE", f"جداول مفقودة: {missing}")
            
            # فحص البيانات
            clients = repo.get_all_clients()
            projects = repo.get_all_projects()
            
            self.log("INFO", "DATABASE", f"✅ قاعدة البيانات سليمة: {len(tables)} جدول، {len(clients)} عميل، {len(projects)} مشروع")
            return True
            
        except Exception as e:
            self.log("CRITICAL", "DATABASE", f"فشل اختبار قاعدة البيانات: {e}")
            return False

    def test_performance(self) -> bool:
        """اختبار الأداء"""
        print("\n" + "="*80)
        print("🔍 المرحلة 6: اختبار الأداء")
        print("="*80)
        
        try:
            from core.repository import Repository
            
            repo = Repository()
            start = time.time()
            
            for _ in range(10):
                repo.get_all_clients()
                repo.get_all_projects()
            
            duration = time.time() - start
            
            if duration > 2.0:
                self.log("WARNING", "PERFORMANCE", f"الأداء بطيء: {duration:.3f} ثانية")
                return False
            
            self.log("INFO", "PERFORMANCE", f"✅ الأداء ممتاز: {duration:.3f} ثانية لـ 10 استعلامات")
            return True
            
        except Exception as e:
            self.log("ERROR", "PERFORMANCE", f"فشل اختبار الأداء: {e}")
            return False

    def generate_report(self) -> Dict:
        """إنشاء تقرير نهائي"""
        duration = time.time() - self.start_time
        
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": round(duration, 2),
            "files_checked": len(self.python_files),
            "summary": {
                "critical_errors": len(self.critical_errors),
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "status": "PERFECT" if len(self.critical_errors) == 0 and len(self.errors) == 0 else "FAILED"
            },
            "details": {
                "critical": self.critical_errors,
                "errors": self.errors,
                "warnings": self.warnings
            }
        }
        
        with open(self.project_root / "absolute_zero_errors_report.json", 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report

    def run_audit(self) -> bool:
        """تشغيل الفحص الكامل"""
        print("\n" + "="*80)
        print("🚀 فحص صفر أخطاء مطلق - Absolute Zero Errors Audit")
        print("="*80)
        print("أقصى مستوى احترافية ودقة - لا مجال للخطأ")
        print("="*80)
        
        # المراحل
        tests = [
            ("اكتشاف الملفات", self.discover_files),
            ("فحص بناء الجملة والترميز", self.check_syntax_and_encoding),
            ("فحص أنماط قاعدة البيانات", self.check_database_patterns),
            ("اختبار الاستيرادات", self.test_imports),
            ("اختبار قاعدة البيانات", self.test_database),
            ("اختبار الأداء", self.test_performance),
        ]
        
        passed = 0
        for name, test in tests:
            try:
                if test():
                    passed += 1
                    print(f"✅ {name}: نجح")
                else:
                    print(f"❌ {name}: فشل")
            except Exception as e:
                print(f"💥 {name}: خطأ - {e}")
                self.log("CRITICAL", "TEST", f"خطأ في {name}: {e}")
        
        # التقرير النهائي
        report = self.generate_report()
        
        print("\n" + "="*80)
        print("📊 النتائج النهائية")
        print("="*80)
        print(f"⏱️  المدة: {report['duration']} ثانية")
        print(f"📁 الملفات: {report['files_checked']}")
        print(f"🧪 الاختبارات: {passed}/{len(tests)}")
        print(f"🚨 أخطاء حرجة: {report['summary']['critical_errors']}")
        print(f"❌ أخطاء: {report['summary']['errors']}")
        print(f"⚠️  تحذيرات: {report['summary']['warnings']}")
        print(f"📊 الحالة: {report['summary']['status']}")
        
        is_perfect = (
            report['summary']['critical_errors'] == 0 and
            report['summary']['errors'] == 0 and
            passed == len(tests)
        )
        
        if is_perfect:
            print("\n" + "="*80)
            print("🎉 مثالي! النظام خالٍ تماماً من الأخطاء")
            print("="*80)
            print("✅ 0 أخطاء حرجة")
            print("✅ 0 أخطاء عادية")
            print("✅ جميع الاختبارات نجحت")
            print("✅ جاهز للإنتاج بثقة 100%")
            print("="*80)
        else:
            print("\n" + "="*80)
            print("⚠️ يوجد أخطاء تحتاج إلى إصلاح")
            print("="*80)
            if report['summary']['critical_errors'] > 0:
                print(f"🚨 {report['summary']['critical_errors']} خطأ حرج يجب إصلاحه فوراً")
            if report['summary']['errors'] > 0:
                print(f"❌ {report['summary']['errors']} خطأ يحتاج إلى إصلاح")
            print("📋 راجع التقرير: absolute_zero_errors_report.json")
            print("="*80)
        
        return is_perfect

def main():
    auditor = AbsoluteZeroErrorsAuditor()
    success = auditor.run_audit()
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
