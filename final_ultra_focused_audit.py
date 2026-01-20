#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فحص نهائي فائق التركيز - Final Ultra Focused Audit
فحص الملفات الأساسية للمشروع فقط (بدون dist أو مكتبات خارجية)
"""

import sys
import os
import ast
import re
import sqlite3
import json
import traceback
import importlib.util
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

# تعيين الترميز للـ console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class FinalUltraFocusedAuditor:
    """فاحص نهائي فائق التركيز للملفات الأساسية فقط"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.critical_issues = []
        self.project_root = Path.cwd()
        self.total_files_checked = 0
        self.start_time = time.time()
        
        # المجلدات المراد فحصها فقط (الملفات الأساسية للمشروع)
        self.core_folders = ['core', 'services', 'ui', 'tests']
        self.core_files = ['main.py', 'version.py']
        
        # المجلدات المراد تجاهلها
        self.ignore_folders = [
            'dist', 'build', '__pycache__', '.venv', '.git', 
            '.pytest_cache', 'installer_output', 'exports'
        ]
        
        # أنماط الأخطاء الحقيقية فقط
        self.error_patterns = {
            'database_bool': [
                r'\bif\s+(?:self\.)?(?:repo|db|database|connection)(?:\s*[^=\s]|:)',
                r'\bif\s+not\s+(?:self\.)?(?:repo|db|database|connection)\b',
                r'\band\s+(?:self\.)?(?:repo|db|database|connection)\b',
                r'\bor\s+(?:self\.)?(?:repo|db|database|connection)\b',
            ]
        }
        
    def log_error(self, message: str, file_path: str = None, line_no: int = None, severity: str = "ERROR"):
        """تسجيل خطأ مع تفاصيل كاملة"""
        error = {
            "type": severity,
            "message": message,
            "file": file_path,
            "line": line_no,
            "timestamp": time.time()
        }
        
        if severity == "CRITICAL":
            self.critical_issues.append(error)
            print(f"🚨 CRITICAL: {message}" + (f" في {file_path}:{line_no}" if file_path and line_no else f" في {file_path}" if file_path else ""))
        elif severity == "ERROR":
            self.errors.append(error)
            print(f"❌ ERROR: {message}" + (f" في {file_path}:{line_no}" if file_path and line_no else f" في {file_path}" if file_path else ""))
        elif severity == "WARNING":
            self.warnings.append(error)
            print(f"⚠️ WARNING: {message}" + (f" في {file_path}:{line_no}" if file_path and line_no else f" في {file_path}" if file_path else ""))
        
    def log_info(self, message: str):
        """تسجيل معلومة"""
        info = {"type": "INFO", "message": message, "timestamp": time.time()}
        self.info.append(info)
        print(f"ℹ️ INFO: {message}")

    def get_project_python_files(self) -> List[Path]:
        """الحصول على ملفات Python الأساسية للمشروع فقط"""
        python_files = []
        
        # ملفات Python في الجذر
        for file_name in self.core_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                python_files.append(file_path)
        
        # ملفات Python في المجلدات الأساسية
        for folder in self.core_folders:
            folder_path = self.project_root / folder
            if folder_path.exists():
                for py_file in folder_path.rglob('*.py'):
                    # تجاهل __pycache__
                    if '__pycache__' not in str(py_file):
                        python_files.append(py_file)
        
        return python_files

    def check_project_syntax(self) -> bool:
        """فحص صحة بناء الجملة للملفات الأساسية فقط"""
        print("\n🔍 فحص صحة بناء الجملة للملفات الأساسية...")
        print("=" * 60)
        
        python_files = self.get_project_python_files()
        syntax_errors = 0
        encoding_errors = 0
        
        for py_file in python_files:
            try:
                # فحص الترميز أولاً
                with open(py_file, 'rb') as f:
                    raw_content = f.read()
                
                # فحص BOM
                if raw_content.startswith(b'\xef\xbb\xbf'):
                    self.log_error(f"ملف يحتوي على BOM", str(py_file), severity="ERROR")
                    encoding_errors += 1
                    continue
                
                # فحص الترميز
                try:
                    content = raw_content.decode('utf-8')
                except UnicodeDecodeError as e:
                    self.log_error(f"خطأ في الترميز: {e}", str(py_file), severity="ERROR")
                    encoding_errors += 1
                    continue
                
                # فحص بناء الجملة
                try:
                    ast.parse(content, filename=str(py_file))
                except SyntaxError as e:
                    self.log_error(f"خطأ في بناء الجملة: {e}", str(py_file), e.lineno, severity="ERROR")
                    syntax_errors += 1
                    continue
                
                # فحص الأنماط المشكلة
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    for pattern_type, patterns in self.error_patterns.items():
                        for pattern in patterns:
                            if re.search(pattern, line):
                                # تجاهل الحالات المُصلحة
                                if 'is not None' in line or 'is None' in line:
                                    continue
                                if line.strip().startswith('#'):
                                    continue
                                
                                self.log_error(f"نمط مشكل ({pattern_type}): {line.strip()}", str(py_file), i, severity="ERROR")
                                syntax_errors += 1
                
            except Exception as e:
                self.log_error(f"خطأ غير متوقع في فحص {py_file}: {e}", str(py_file), severity="CRITICAL")
        
        self.total_files_checked = len(python_files)
        
        if syntax_errors == 0 and encoding_errors == 0:
            self.log_info(f"✅ جميع الملفات الأساسية ({len(python_files)}) صحيحة نحوياً وترميزياً")
            return True
        else:
            self.log_error(f"وجد {syntax_errors} أخطاء نحوية و {encoding_errors} أخطاء ترميز في الملفات الأساسية")
            return False

    def test_core_imports(self) -> bool:
        """اختبار استيراد الوحدات الأساسية"""
        print("\n🧪 اختبار استيراد الوحدات الأساسية...")
        print("=" * 60)
        
        import_errors = 0
        successful_imports = 0
        
        # إضافة مسار المشروع
        sys.path.insert(0, str(self.project_root))
        
        # قائمة الوحدات الأساسية للاختبار
        core_modules = [
            'core.repository',
            'core.config',
            'core.auth_models',
            'services.client_service',
            'services.project_service',
            'version'
        ]
        
        for module_name in core_modules:
            try:
                # محاولة استيراد الوحدة
                if '.' in module_name:
                    parts = module_name.split('.')
                    module = __import__(module_name, fromlist=[parts[-1]])
                else:
                    module = __import__(module_name)
                
                self.log_info(f"✅ استيراد ناجح: {module_name}")
                successful_imports += 1
                
            except ImportError as e:
                self.log_error(f"فشل استيراد {module_name}: {e}", severity="ERROR")
                import_errors += 1
            except Exception as e:
                self.log_error(f"خطأ غير متوقع في استيراد {module_name}: {e}", severity="CRITICAL")
                import_errors += 1
        
        if import_errors == 0:
            self.log_info(f"✅ جميع الاستيرادات ({successful_imports}) نجحت")
            return True
        else:
            self.log_error(f"فشل {import_errors} استيراد من أصل {len(core_modules)}")
            return False

    def test_database_functionality(self) -> bool:
        """اختبار وظائف قاعدة البيانات"""
        print("\n🗄️ اختبار وظائف قاعدة البيانات...")
        print("=" * 60)
        
        try:
            from core.repository import Repository
            
            repo = Repository()
            cursor = repo.get_cursor()
            
            # فحص سلامة قاعدة البيانات
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            if integrity_result != 'ok':
                self.log_error(f"مشكلة في سلامة قاعدة البيانات: {integrity_result}", severity="CRITICAL")
                return False
            
            # فحص الجداول الأساسية
            required_tables = ['clients', 'projects', 'services', 'users', 'accounts']
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = []
            for table in required_tables:
                if table not in existing_tables:
                    missing_tables.append(table)
            
            if missing_tables:
                self.log_error(f"جداول مفقودة: {missing_tables}", severity="WARNING")
            
            # فحص البيانات
            clients = repo.get_all_clients()
            projects = repo.get_all_projects()
            
            self.log_info(f"✅ قاعدة البيانات تحتوي على {len(existing_tables)} جدول")
            self.log_info(f"✅ العملاء: {len(clients)}")
            self.log_info(f"✅ المشاريع: {len(projects)}")
            
            return True
            
        except Exception as e:
            self.log_error(f"فشل اختبار قاعدة البيانات: {e}", severity="ERROR")
            return False

    def test_version_consistency(self) -> bool:
        """اختبار تناسق الإصدارات"""
        print("\n🔍 اختبار تناسق الإصدارات...")
        print("=" * 60)
        
        try:
            # قراءة version.json
            with open(self.project_root / 'version.json', 'r', encoding='utf-8') as f:
                version_data = json.load(f)
                json_version = version_data.get('version')
            
            # قراءة version.py
            with open(self.project_root / 'version.py', 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
                py_version = match.group(1) if match else None
            
            if json_version and py_version and json_version == py_version:
                self.log_info(f"✅ الإصدارات متناسقة: {json_version}")
                return True
            else:
                self.log_error(f"الإصدارات غير متناسقة: JSON={json_version}, PY={py_version}", severity="ERROR")
                return False
                
        except Exception as e:
            self.log_error(f"فشل فحص الإصدارات: {e}", severity="ERROR")
            return False

    def test_main_py_functionality(self) -> bool:
        """اختبار وظائف main.py"""
        print("\n🔍 اختبار وظائف main.py...")
        print("=" * 60)
        
        main_file = self.project_root / 'main.py'
        
        if not main_file.exists():
            self.log_error("ملف main.py غير موجود", severity="CRITICAL")
            return False
        
        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # فحص الاستيرادات الأساسية
            required_imports = ['sys', 'PyQt6']
            missing_imports = []
            for imp in required_imports:
                if imp not in content:
                    missing_imports.append(imp)
            
            if missing_imports:
                self.log_error(f"استيرادات مفقودة في main.py: {missing_imports}", severity="WARNING")
            
            # فحص وجود if __name__ == '__main__'
            if "__name__ == '__main__'" in content:
                self.log_info("✅ main.py يحتوي على if __name__ == '__main__'")
            else:
                self.log_error("main.py لا يحتوي على if __name__ == '__main__'", severity="WARNING")
            
            self.log_info("✅ ملف main.py صحيح")
            return True
            
        except Exception as e:
            self.log_error(f"خطأ في main.py: {e}", severity="ERROR")
            return False

    def test_performance(self) -> bool:
        """اختبار الأداء"""
        print("\n⚡ اختبار الأداء...")
        print("=" * 60)
        
        try:
            from core.repository import Repository
            
            repo = Repository()
            
            # اختبار سرعة الاستعلامات
            start_time = time.time()
            
            for _ in range(10):
                clients = repo.get_all_clients()
                projects = repo.get_all_projects()
            
            end_time = time.time()
            duration = end_time - start_time
            
            if duration > 2.0:  # أكثر من 2 ثانية
                self.log_error(f"الأداء بطيء: {duration:.2f} ثانية", severity="WARNING")
                return False
            
            self.log_info(f"✅ الأداء جيد: {duration:.3f} ثانية لـ 10 استعلامات")
            return True
            
        except Exception as e:
            self.log_error(f"فشل اختبار الأداء: {e}", severity="ERROR")
            return False

    def generate_final_report(self):
        """إنشاء التقرير النهائي"""
        print("\n📊 إنشاء التقرير النهائي...")
        print("=" * 60)
        
        end_time = time.time()
        total_duration = end_time - self.start_time
        
        report = {
            "audit_info": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": round(total_duration, 2),
                "total_files_checked": self.total_files_checked,
                "audit_type": "Final Ultra Focused Audit"
            },
            "summary": {
                "critical_issues": len(self.critical_issues),
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "info_messages": len(self.info),
                "overall_status": "PASS" if len(self.critical_issues) == 0 and len(self.errors) == 0 else "FAIL"
            },
            "details": {
                "critical_issues": self.critical_issues,
                "errors": self.errors,
                "warnings": self.warnings,
                "info": self.info
            }
        }
        
        # حفظ التقرير
        report_file = self.project_root / "final_focused_audit_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        self.log_info(f"✅ تم حفظ التقرير في: {report_file}")
        return report

    def run_final_focused_audit(self) -> bool:
        """تشغيل الفحص النهائي المركز"""
        print("🚀 بدء الفحص النهائي فائق التركيز - Final Ultra Focused Audit")
        print("=" * 80)
        print("فحص الملفات الأساسية للمشروع فقط (بدون مكتبات خارجية)")
        print("=" * 80)
        
        # قائمة الاختبارات المركزة
        tests = [
            ("فحص صحة بناء الجملة", self.check_project_syntax),
            ("اختبار الاستيرادات الأساسية", self.test_core_imports),
            ("اختبار وظائف قاعدة البيانات", self.test_database_functionality),
            ("اختبار تناسق الإصدارات", self.test_version_consistency),
            ("اختبار main.py", self.test_main_py_functionality),
            ("اختبار الأداء", self.test_performance),
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                result = test_func()
                if result:
                    passed_tests += 1
                    print(f"✅ {test_name}: نجح")
                else:
                    print(f"❌ {test_name}: فشل")
            except Exception as e:
                print(f"💥 {test_name}: خطأ غير متوقع - {e}")
                self.log_error(f"خطأ في اختبار {test_name}: {e}", severity="CRITICAL")
        
        # إنشاء التقرير
        report = self.generate_final_report()
        
        print("\n" + "=" * 80)
        print("📊 ملخص الفحص النهائي فائق التركيز")
        print("=" * 80)
        print(f"⏱️ المدة الإجمالية: {report['audit_info']['duration_seconds']} ثانية")
        print(f"📁 الملفات المفحوصة: {report['audit_info']['total_files_checked']}")
        print(f"🧪 الاختبارات الناجحة: {passed_tests}/{total_tests}")
        print(f"🚨 المشاكل الحرجة: {report['summary']['critical_issues']}")
        print(f"❌ الأخطاء: {report['summary']['errors']}")
        print(f"⚠️ التحذيرات: {report['summary']['warnings']}")
        print(f"ℹ️ المعلومات: {report['summary']['info_messages']}")
        print(f"📊 الحالة العامة: {report['summary']['overall_status']}")
        
        # النتيجة النهائية
        is_perfect = (
            len(self.critical_issues) == 0 and 
            len(self.errors) == 0 and 
            passed_tests == total_tests
        )
        
        if is_perfect:
            print("\n🎉 الملفات الأساسية للمشروع مثالية!")
            print("✅ لا توجد أي أخطاء أو مشاكل حرجة في الكود الأساسي")
            print("🚀 جاهز للاستخدام الإنتاجي")
        else:
            print("\n⚠️ الملفات الأساسية تحتاج إلى مراجعة")
            if len(self.critical_issues) > 0:
                print(f"🚨 يوجد {len(self.critical_issues)} مشكلة حرجة تحتاج إلى إصلاح فوري")
            if len(self.errors) > 0:
                print(f"❌ يوجد {len(self.errors)} خطأ يحتاج إلى إصلاح")
        
        return is_perfect

def main():
    """الدالة الرئيسية"""
    print("🔍 Final Ultra Focused Audit - الفحص النهائي فائق التركيز")
    print("=" * 80)
    print("فحص الملفات الأساسية للمشروع فقط (بدون مكتبات خارجية)")
    print("=" * 80)
    
    auditor = FinalUltraFocusedAuditor()
    success = auditor.run_final_focused_audit()
    
    if success:
        print("\n🏆 الملفات الأساسية للمشروع اجتازت جميع الاختبارات!")
        print("✅ لا توجد أي أخطاء في الكود الأساسي")
        print("🚀 جاهز للاستخدام الإنتاجي")
        return 0
    else:
        print("\n⚠️ الملفات الأساسية تحتاج إلى مراجعة")
        print("📋 راجع التقرير المفصل في final_focused_audit_report.json")
        return 1

if __name__ == '__main__':
    sys.exit(main())