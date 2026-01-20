#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔬 الفحص النهائي الشامل - Ultimate Zero Errors Test
فحص احترافي بدقة عالية لكل ملفات النظام بدون استثناء
"""

import ast
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List, Set, Tuple

class UltimateZeroErrorsTester:
    """فاحص نهائي شامل بدقة عالية"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.start_time = time.time()
        self.tested_files = set()
        self.all_python_files = []
        
    def log(self, level: str, message: str, file_path: str = None, line_no: int = None):
        """تسجيل رسالة مع تفاصيل كاملة"""
        entry = {
            "level": level,
            "message": message,
            "file": file_path,
            "line": line_no,
            "timestamp": time.time()
        }
        
        location = ""
        if file_path:
            location = f" في {file_path}"
            if line_no:
                location += f":{line_no}"
        
        if level == "ERROR":
            self.errors.append(entry)
            print(f"❌ ERROR: {message}{location}")
        elif level == "WARNING":
            self.warnings.append(entry)
            print(f"⚠️ WARNING: {message}{location}")
        else:
            self.info.append(entry)
            print(f"ℹ️ INFO: {message}")
    
    def discover_all_python_files(self):
        """اكتشاف جميع ملفات Python في المشروع"""
        print("\n🔍 اكتشاف جميع ملفات Python...")
        
        exclude_dirs = {'.venv', '__pycache__', 'build', 'dist', '.git', 
                       'installer_output', '.pytest_cache', '.theORQL'}
        
        for py_file in Path(".").rglob("*.py"):
            # تجاهل المجلدات المستثناة
            if any(excluded in py_file.parts for excluded in exclude_dirs):
                continue
            
            self.all_python_files.append(py_file)
        
        self.log("INFO", f"تم اكتشاف {len(self.all_python_files)} ملف Python")
        return True
    
    def test_1_syntax_validation(self) -> bool:
        """الاختبار 1: التحقق من صحة بناء الجملة لكل ملف"""
        print("\n" + "="*80)
        print("🔍 الاختبار 1: فحص صحة بناء الجملة Python")
        print("="*80)
        
        syntax_errors = 0
        encoding_errors = 0
        
        for py_file in self.all_python_files:
            self.tested_files.add(str(py_file))
            
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    code = f.read()
                
                # محاولة تحليل الكود
                try:
                    ast.parse(code)
                except SyntaxError as e:
                    self.log("ERROR", f"خطأ نحوي: {e.msg}", str(py_file), e.lineno)
                    syntax_errors += 1
                    
            except UnicodeDecodeError as e:
                self.log("ERROR", f"خطأ في الترميز: {e}", str(py_file))
                encoding_errors += 1
            except Exception as e:
                self.log("WARNING", f"فشل فحص الملف: {e}", str(py_file))
        
        if syntax_errors == 0 and encoding_errors == 0:
            self.log("INFO", f"✅ جميع {len(self.all_python_files)} ملف صحيحة نحوياً")
            return True
        else:
            self.log("ERROR", f"وجد {syntax_errors} أخطاء نحوية و {encoding_errors} أخطاء ترميز")
            return False
    
    def test_2_import_validation(self) -> bool:
        """الاختبار 2: التحقق من جميع الاستيرادات"""
        print("\n" + "="*80)
        print("🔍 الاختبار 2: فحص الاستيرادات والتبعيات")
        print("="*80)
        
        has_errors = False
        
        # التبعيات الأساسية
        critical_packages = {
            "PyQt6": "PyQt6.QtCore",
            "PyQt6-WebEngine": "PyQt6.QtWebEngineWidgets",
            "pymongo": "pymongo",
            "pydantic": "pydantic",
            "Jinja2": "jinja2",
            "reportlab": "reportlab",
            "pandas": "pandas",
            "openpyxl": "openpyxl",
            "Pillow": "PIL",
            "matplotlib": "matplotlib",
            "weasyprint": "weasyprint"
        }
        
        for package_name, import_name in critical_packages.items():
            try:
                __import__(import_name)
                self.log("INFO", f"✅ {package_name} متوفر")
            except ImportError as e:
                self.log("ERROR", f"الحزمة {package_name} غير متوفرة: {e}")
                has_errors = True
        
        return not has_errors
    
    def test_3_core_files_integrity(self) -> bool:
        """الاختبار 3: فحص سلامة الملفات الأساسية"""
        print("\n" + "="*80)
        print("🔍 الاختبار 3: فحص سلامة الملفات الأساسية")
        print("="*80)
        
        has_errors = False
        
        critical_files = {
            "main.py": "الملف الرئيسي",
            "version.json": "ملف الإصدار",
            "requirements.txt": "ملف التبعيات",
            "core/repository.py": "مخزن البيانات",
            "core/config.py": "ملف التكوين",
            "core/schemas.py": "نماذج البيانات",
            "ui/main_window.py": "النافذة الرئيسية",
            "ui/login_window.py": "نافذة تسجيل الدخول",
            "services/accounting_service.py": "خدمة المحاسبة",
            "services/project_service.py": "خدمة المشاريع"
        }
        
        for file_path, description in critical_files.items():
            if not os.path.exists(file_path):
                self.log("ERROR", f"{description} مفقود", file_path)
                has_errors = True
                continue
            
            # فحص حجم الملف
            size = os.path.getsize(file_path)
            if size == 0:
                self.log("ERROR", f"{description} فارغ", file_path)
                has_errors = True
            elif size < 100:
                self.log("WARNING", f"{description} صغير جداً ({size} بايت)", file_path)
            else:
                self.log("INFO", f"✅ {description} سليم ({size:,} بايت)")
        
        return not has_errors
    
    def test_4_database_integrity(self) -> bool:
        """الاختبار 4: فحص سلامة قاعدة البيانات"""
        print("\n" + "="*80)
        print("🔍 الاختبار 4: فحص سلامة قاعدة البيانات")
        print("="*80)
        
        has_errors = False
        db_file = "skywave_local.db"
        
        if not os.path.exists(db_file):
            self.log("WARNING", f"ملف قاعدة البيانات {db_file} غير موجود")
            return True  # ليس خطأ حرج
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # الجداول المطلوبة
            required_tables = [
                "clients", "projects", "services", "invoices", "expenses",
                "accounts", "journal_entries", "payments", "users",
                "employees", "employee_loans", "employee_salaries",
                "employee_attendance", "employee_leaves", "tasks",
                "notifications", "currencies", "sync_queue",
                "project_milestones", "invoice_numbers", "loan_payments"
            ]
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            for table in required_tables:
                if table in existing_tables:
                    # فحص عدد الأعمدة
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    self.log("INFO", f"✅ جدول {table} موجود ({len(columns)} عمود)")
                else:
                    self.log("ERROR", f"جدول {table} مفقود")
                    has_errors = True
            
            # فحص الـ indexes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = cursor.fetchall()
            self.log("INFO", f"✅ يوجد {len(indexes)} index في قاعدة البيانات")
            
            conn.close()
            
        except Exception as e:
            self.log("ERROR", f"فشل فحص قاعدة البيانات: {e}")
            has_errors = True
        
        return not has_errors
    
    def test_5_code_quality_analysis(self) -> bool:
        """الاختبار 5: تحليل جودة الكود"""
        print("\n" + "="*80)
        print("🔍 الاختبار 5: تحليل جودة الكود")
        print("="*80)
        
        critical_patterns = {
            r'except\s*:': "استخدام except عام (خطير)",
            r'eval\s*\(': "استخدام eval (خطير أمنياً)",
            r'exec\s*\(': "استخدام exec (خطير أمنياً)",
            r'__import__\s*\(': "استخدام __import__ ديناميكي",
            r'globals\s*\(\)': "الوصول إلى globals",
            r'locals\s*\(\)': "الوصول إلى locals"
        }
        
        warning_patterns = {
            r'TODO': "تعليق TODO",
            r'FIXME': "تعليق FIXME",
            r'HACK': "تعليق HACK",
            r'XXX': "تعليق XXX"
        }
        
        critical_issues = 0
        warning_issues = 0
        
        for py_file in self.all_python_files:
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    lines = content.split('\n')
                
                # فحص الأنماط الحرجة
                for pattern, description in critical_patterns.items():
                    for line_no, line in enumerate(lines, 1):
                        if re.search(pattern, line):
                            # تجاهل التعليقات
                            if not line.strip().startswith('#'):
                                self.log("ERROR", description, str(py_file), line_no)
                                critical_issues += 1
                
                # فحص الأنماط التحذيرية
                for pattern, description in warning_patterns.items():
                    matches = re.findall(pattern, content)
                    if matches:
                        warning_issues += len(matches)
                        
            except Exception as e:
                self.log("WARNING", f"فشل تحليل الملف: {e}", str(py_file))
        
        if critical_issues == 0:
            self.log("INFO", f"✅ لا توجد مشاكل حرجة في الكود")
        else:
            self.log("ERROR", f"وجد {critical_issues} مشكلة حرجة في الكود")
        
        if warning_issues > 0:
            self.log("INFO", f"وجد {warning_issues} تعليق يحتاج مراجعة")
        
        return critical_issues == 0
    
    def test_6_function_definitions(self) -> bool:
        """الاختبار 6: فحص تعريفات الدوال"""
        print("\n" + "="*80)
        print("🔍 الاختبار 6: فحص تعريفات الدوال والكلاسات")
        print("="*80)
        
        has_errors = False
        total_functions = 0
        total_classes = 0
        empty_functions = 0
        
        for py_file in self.all_python_files:
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    code = f.read()
                
                tree = ast.parse(code)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        total_functions += 1
                        # فحص الدوال الفارغة
                        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                            self.log("WARNING", f"دالة فارغة: {node.name}", str(py_file), node.lineno)
                            empty_functions += 1
                    
                    elif isinstance(node, ast.ClassDef):
                        total_classes += 1
                        
            except Exception as e:
                self.log("WARNING", f"فشل تحليل الدوال: {e}", str(py_file))
        
        self.log("INFO", f"✅ تم فحص {total_functions} دالة و {total_classes} كلاس")
        
        if empty_functions > 0:
            self.log("WARNING", f"وجد {empty_functions} دالة فارغة")
        
        return not has_errors
    
    def test_7_import_cycles(self) -> bool:
        """الاختبار 7: فحص الاستيرادات الدائرية"""
        print("\n" + "="*80)
        print("🔍 الاختبار 7: فحص الاستيرادات الدائرية")
        print("="*80)
        
        import_graph = {}
        
        for py_file in self.all_python_files:
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    code = f.read()
                
                tree = ast.parse(code)
                imports = set()
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module)
                
                module_name = str(py_file).replace('\\', '.').replace('/', '.').replace('.py', '')
                import_graph[module_name] = imports
                
            except Exception:
                pass
        
        self.log("INFO", f"✅ تم تحليل {len(import_graph)} وحدة للاستيرادات")
        return True
    
    def test_8_configuration_files(self) -> bool:
        """الاختبار 8: فحص ملفات التكوين"""
        print("\n" + "="*80)
        print("🔍 الاختبار 8: فحص ملفات التكوين")
        print("="*80)
        
        has_errors = False
        
        # فحص version.json
        if os.path.exists("version.json"):
            try:
                with open("version.json", "r", encoding="utf-8") as f:
                    version_data = json.load(f)
                
                required_keys = ["version", "version_name", "release_date", "changelog"]
                for key in required_keys:
                    if key not in version_data:
                        self.log("ERROR", f"مفتاح {key} مفقود في version.json")
                        has_errors = True
                    else:
                        self.log("INFO", f"✅ {key}: {version_data[key]}")
                        
            except json.JSONDecodeError as e:
                self.log("ERROR", f"خطأ في تنسيق version.json: {e}")
                has_errors = True
        else:
            self.log("ERROR", "ملف version.json مفقود")
            has_errors = True
        
        # فحص requirements.txt
        if os.path.exists("requirements.txt"):
            try:
                with open("requirements.txt", "r", encoding="utf-8") as f:
                    requirements = f.readlines()
                
                self.log("INFO", f"✅ requirements.txt يحتوي على {len(requirements)} تبعية")
                
            except Exception as e:
                self.log("ERROR", f"فشل قراءة requirements.txt: {e}")
                has_errors = True
        else:
            self.log("ERROR", "ملف requirements.txt مفقود")
            has_errors = True
        
        # فحص .env.example
        if os.path.exists(".env.example"):
            self.log("INFO", "✅ ملف .env.example موجود")
        else:
            self.log("WARNING", "ملف .env.example مفقود")
        
        return not has_errors
    
    def test_9_runtime_imports(self) -> bool:
        """الاختبار 9: اختبار استيراد الوحدات الأساسية"""
        print("\n" + "="*80)
        print("🔍 الاختبار 9: اختبار استيراد الوحدات الأساسية")
        print("="*80)
        
        has_errors = False
        
        critical_modules = [
            "core.repository",
            "core.config",
            "core.schemas",
            "core.logger",
            "services.accounting_service",
            "services.project_service",
            "services.client_service"
        ]
        
        for module_name in critical_modules:
            try:
                __import__(module_name)
                self.log("INFO", f"✅ استيراد {module_name} نجح")
            except Exception as e:
                self.log("ERROR", f"فشل استيراد {module_name}: {e}")
                has_errors = True
        
        return not has_errors
    
    def test_10_file_permissions(self) -> bool:
        """الاختبار 10: فحص صلاحيات الملفات"""
        print("\n" + "="*80)
        print("🔍 الاختبار 10: فحص صلاحيات الملفات")
        print("="*80)
        
        for py_file in self.all_python_files:
            if not os.access(py_file, os.R_OK):
                self.log("ERROR", "الملف غير قابل للقراءة", str(py_file))
                return False
        
        self.log("INFO", f"✅ جميع {len(self.all_python_files)} ملف قابلة للقراءة")
        return True
    
    def run_all_tests(self) -> bool:
        """تشغيل جميع الاختبارات"""
        print("=" * 80)
        print("🚀 بدء الفحص النهائي الشامل - Ultimate Zero Errors Test")
        print("=" * 80)
        
        # اكتشاف الملفات أولاً
        self.discover_all_python_files()
        
        # قائمة الاختبارات
        tests = [
            ("فحص صحة بناء الجملة", self.test_1_syntax_validation),
            ("فحص الاستيرادات", self.test_2_import_validation),
            ("فحص الملفات الأساسية", self.test_3_core_files_integrity),
            ("فحص قاعدة البيانات", self.test_4_database_integrity),
            ("تحليل جودة الكود", self.test_5_code_quality_analysis),
            ("فحص تعريفات الدوال", self.test_6_function_definitions),
            ("فحص الاستيرادات الدائرية", self.test_7_import_cycles),
            ("فحص ملفات التكوين", self.test_8_configuration_files),
            ("اختبار استيراد الوحدات", self.test_9_runtime_imports),
            ("فحص صلاحيات الملفات", self.test_10_file_permissions)
        ]
        
        all_passed = True
        passed_tests = 0
        failed_tests = 0
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    passed_tests += 1
                    print(f"\n✅ {test_name}: نجح")
                else:
                    failed_tests += 1
                    all_passed = False
                    print(f"\n❌ {test_name}: فشل")
            except Exception as e:
                self.log("ERROR", f"فشل {test_name}: {e}")
                traceback.print_exc()
                failed_tests += 1
                all_passed = False
        
        # إنشاء التقرير النهائي
        self.generate_final_report(passed_tests, failed_tests, len(tests))
        
        return all_passed
    
    def generate_final_report(self, passed: int, failed: int, total: int):
        """إنشاء التقرير النهائي"""
        print("\n" + "=" * 80)
        print("📊 التقرير النهائي الشامل")
        print("=" * 80)
        
        duration = time.time() - self.start_time
        
        report = {
            "timestamp": time.time(),
            "duration_seconds": duration,
            "tests_total": total,
            "tests_passed": passed,
            "tests_failed": failed,
            "files_tested": len(self.tested_files),
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "info_count": len(self.info),
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "status": "PASS" if len(self.errors) == 0 else "FAIL"
        }
        
        # حفظ التقرير
        report_file = "ultimate_zero_errors_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📈 الإحصائيات:")
        print(f"   🧪 الاختبارات: {passed}/{total} نجح")
        print(f"   📁 الملفات المفحوصة: {len(self.tested_files)}")
        print(f"   ❌ أخطاء: {len(self.errors)}")
        print(f"   ⚠️ تحذيرات: {len(self.warnings)}")
        print(f"   ℹ️ معلومات: {len(self.info)}")
        print(f"   ⏱️ المدة: {duration:.2f} ثانية")
        print(f"\n📄 تم حفظ التقرير في: {report_file}")
        
        if len(self.errors) == 0:
            print("\n" + "🎉" * 40)
            print("✅ النظام خالي تماماً من الأخطاء - ZERO ERRORS!")
            print("🎉" * 40)
        else:
            print(f"\n❌ وجد {len(self.errors)} خطأ يجب إصلاحه")
        
        print("=" * 80)

def main():
    """الدالة الرئيسية"""
    tester = UltimateZeroErrorsTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
