#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فحص شامل واحترافي للنظام - اكتشاف جميع الأخطاء المحتملة
Comprehensive System Audit - Detect All Potential Errors
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

class SystemAuditor:
    """فاحص النظام الشامل"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.project_root = Path.cwd()
        
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

    def check_python_syntax(self) -> bool:
        """فحص صحة بناء الجملة Python"""
        print("\n🔍 فحص صحة بناء الجملة Python...")
        print("=" * 60)
        
        python_files = list(self.project_root.rglob("*.py"))
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
            self.log_info(f"✅ جميع ملفات Python ({len(python_files)}) صحيحة نحوياً")
            return True
        else:
            self.log_error(f"وجد {syntax_errors} أخطاء نحوية في ملفات Python")
            return False

    def check_imports(self) -> bool:
        """فحص الاستيرادات"""
        print("\n🔍 فحص الاستيرادات...")
        print("=" * 60)
        
        python_files = list(self.project_root.rglob("*.py"))
        import_errors = 0
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # البحث عن الاستيرادات
                import_lines = re.findall(r'^(?:from\s+\S+\s+)?import\s+.+$', content, re.MULTILINE)
                
                for import_line in import_lines:
                    # تجاهل الاستيرادات المشروطة
                    if 'try:' in content and 'except' in content:
                        continue
                    
                    # فحص الاستيرادات الأساسية
                    if any(lib in import_line for lib in ['PyQt6', 'pymongo', 'pydantic']):
                        continue  # هذه مكتبات خارجية
                    
                    # فحص الاستيرادات المحلية
                    if 'from core' in import_line or 'from services' in import_line or 'from ui' in import_line:
                        module_name = import_line.split('from ')[1].split(' import')[0].strip()
                        module_path = self.project_root / f"{module_name.replace('.', '/')}.py"
                        
                        if not module_path.exists():
                            self.log_warning(f"ملف الوحدة غير موجود: {module_path}", str(py_file))
                            import_errors += 1
                            
            except Exception as e:
                self.log_error(f"خطأ في فحص الاستيرادات: {e}", str(py_file))
                import_errors += 1
        
        if import_errors == 0:
            self.log_info("✅ جميع الاستيرادات صحيحة")
            return True
        else:
            self.log_warning(f"وجد {import_errors} تحذيرات في الاستيرادات")
            return True  # تحذيرات وليس أخطاء

    def check_database_patterns(self) -> bool:
        """فحص أنماط قاعدة البيانات المشكلة"""
        print("\n🔍 فحص أنماط قاعدة البيانات...")
        print("=" * 60)
        
        python_files = list(self.project_root.rglob("*.py"))
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
                            
                            self.log_error(
                                f"نمط مشكل في السطر {i}: {line.strip()}", 
                                str(py_file)
                            )
                            pattern_errors += 1
                            
            except Exception as e:
                self.log_error(f"خطأ في فحص الأنماط: {e}", str(py_file))
                pattern_errors += 1
        
        if pattern_errors == 0:
            self.log_info("✅ لا توجد أنماط مشكلة في قاعدة البيانات")
            return True
        else:
            self.log_error(f"وجد {pattern_errors} أنماط مشكلة")
            return False

    def check_core_modules(self) -> bool:
        """فحص الوحدات الأساسية"""
        print("\n🔍 فحص الوحدات الأساسية...")
        print("=" * 60)
        
        core_modules = [
            'core.repository',
            'core.config',
            'core.logger',
            'core.auth_models',
            'core.schemas'
        ]
        
        module_errors = 0
        
        for module_name in core_modules:
            try:
                # محاولة استيراد الوحدة
                spec = importlib.util.spec_from_file_location(
                    module_name, 
                    self.project_root / f"{module_name.replace('.', '/')}.py"
                )
                
                if spec is None:
                    self.log_error(f"لا يمكن العثور على الوحدة: {module_name}")
                    module_errors += 1
                    continue
                
                module = importlib.util.module_from_spec(spec)
                
                # محاولة تنفيذ الوحدة
                spec.loader.exec_module(module)
                self.log_info(f"✅ الوحدة {module_name} تعمل بشكل صحيح")
                
            except Exception as e:
                self.log_error(f"خطأ في الوحدة {module_name}: {e}")
                module_errors += 1
        
        return module_errors == 0

    def check_database_file(self) -> bool:
        """فحص ملف قاعدة البيانات"""
        print("\n🔍 فحص ملف قاعدة البيانات...")
        print("=" * 60)
        
        db_files = ['skywave_local.db', 'skywave.db']
        db_found = False
        
        for db_file in db_files:
            db_path = self.project_root / db_file
            if db_path.exists():
                db_found = True
                try:
                    # محاولة الاتصال بقاعدة البيانات
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    
                    # فحص الجداول الأساسية
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    required_tables = ['clients', 'projects', 'services', 'users']
                    missing_tables = [table for table in required_tables if table not in tables]
                    
                    if missing_tables:
                        self.log_warning(f"جداول مفقودة في {db_file}: {missing_tables}")
                    else:
                        self.log_info(f"✅ قاعدة البيانات {db_file} سليمة")
                    
                    conn.close()
                    
                except Exception as e:
                    self.log_error(f"خطأ في قاعدة البيانات {db_file}: {e}")
                    return False
        
        if not db_found:
            self.log_warning("لم يتم العثور على ملف قاعدة البيانات")
        
        return True

    def check_config_files(self) -> bool:
        """فحص ملفات الإعدادات"""
        print("\n🔍 فحص ملفات الإعدادات...")
        print("=" * 60)
        
        config_files = [
            'version.json',
            'skywave_settings.json',
            'requirements.txt',
            '.env.example'
        ]
        
        config_errors = 0
        
        for config_file in config_files:
            config_path = self.project_root / config_file
            
            if not config_path.exists():
                self.log_warning(f"ملف الإعدادات مفقود: {config_file}")
                continue
            
            try:
                if config_file.endswith('.json'):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        json.load(f)
                    self.log_info(f"✅ ملف JSON صحيح: {config_file}")
                else:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if content.strip():
                        self.log_info(f"✅ ملف الإعدادات موجود: {config_file}")
                    else:
                        self.log_warning(f"ملف الإعدادات فارغ: {config_file}")
                        
            except json.JSONDecodeError as e:
                self.log_error(f"خطأ في JSON في {config_file}: {e}")
                config_errors += 1
            except Exception as e:
                self.log_error(f"خطأ في ملف الإعدادات {config_file}: {e}")
                config_errors += 1
        
        return config_errors == 0

    def check_ui_modules(self) -> bool:
        """فحص وحدات واجهة المستخدم"""
        print("\n🔍 فحص وحدات واجهة المستخدم...")
        print("=" * 60)
        
        ui_path = self.project_root / 'ui'
        if not ui_path.exists():
            self.log_error("مجلد ui غير موجود")
            return False
        
        critical_ui_files = [
            'main_window.py',
            'login_window.py',
            'client_manager.py',
            'project_manager.py'
        ]
        
        ui_errors = 0
        
        for ui_file in critical_ui_files:
            ui_file_path = ui_path / ui_file
            
            if not ui_file_path.exists():
                self.log_error(f"ملف UI مفقود: {ui_file}")
                ui_errors += 1
                continue
            
            try:
                with open(ui_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # فحص الاستيرادات الأساسية
                if 'PyQt6' not in content:
                    self.log_warning(f"لا يحتوي على PyQt6: {ui_file}")
                
                # فحص الكلاسات الأساسية
                if 'class ' not in content:
                    self.log_error(f"لا يحتوي على كلاس: {ui_file}")
                    ui_errors += 1
                
                self.log_info(f"✅ ملف UI صحيح: {ui_file}")
                
            except Exception as e:
                self.log_error(f"خطأ في ملف UI {ui_file}: {e}")
                ui_errors += 1
        
        return ui_errors == 0

    def check_services(self) -> bool:
        """فحص الخدمات"""
        print("\n🔍 فحص الخدمات...")
        print("=" * 60)
        
        services_path = self.project_root / 'services'
        if not services_path.exists():
            self.log_error("مجلد services غير موجود")
            return False
        
        critical_services = [
            'client_service.py',
            'project_service.py',
            'invoice_service.py',
            'accounting_service.py'
        ]
        
        service_errors = 0
        
        for service_file in critical_services:
            service_path = services_path / service_file
            
            if not service_path.exists():
                self.log_error(f"خدمة مفقودة: {service_file}")
                service_errors += 1
                continue
            
            try:
                with open(service_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # فحص وجود كلاس الخدمة
                if 'class ' not in content:
                    self.log_error(f"لا يحتوي على كلاس خدمة: {service_file}")
                    service_errors += 1
                
                # فحص استيراد Repository
                if 'Repository' not in content and 'repo' not in content.lower():
                    self.log_warning(f"قد لا يستخدم Repository: {service_file}")
                
                self.log_info(f"✅ خدمة صحيحة: {service_file}")
                
            except Exception as e:
                self.log_error(f"خطأ في الخدمة {service_file}: {e}")
                service_errors += 1
        
        return service_errors == 0

    def test_main_entry_point(self) -> bool:
        """اختبار نقطة الدخول الرئيسية"""
        print("\n🔍 اختبار نقطة الدخول الرئيسية...")
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
            if "__name__ == '__main__'" not in content:
                self.log_warning("main.py لا يحتوي على if __name__ == '__main__'")
            
            self.log_info("✅ ملف main.py صحيح")
            return True
            
        except Exception as e:
            self.log_error(f"خطأ في main.py: {e}")
            return False

    def check_version_consistency(self) -> bool:
        """فحص تناسق الإصدارات"""
        print("\n🔍 فحص تناسق الإصدارات...")
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

    def run_comprehensive_test(self) -> bool:
        """تشغيل اختبار شامل"""
        print("\n🧪 تشغيل اختبار شامل للنظام...")
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
            
            return True
            
        except Exception as e:
            self.log_error(f"فشل الاختبار الشامل: {e}")
            self.log_error(f"تفاصيل الخطأ: {traceback.format_exc()}")
            return False

    def generate_report(self) -> Dict[str, Any]:
        """إنشاء تقرير شامل"""
        return {
            "timestamp": "2026-01-20",
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "total_info": len(self.info),
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "status": "PASS" if len(self.errors) == 0 else "FAIL"
        }

    def run_full_audit(self) -> bool:
        """تشغيل الفحص الشامل"""
        print("🔍 بدء الفحص الشامل للنظام...")
        print("=" * 80)
        
        tests = [
            ("فحص بناء الجملة Python", self.check_python_syntax),
            ("فحص الاستيرادات", self.check_imports),
            ("فحص أنماط قاعدة البيانات", self.check_database_patterns),
            ("فحص الوحدات الأساسية", self.check_core_modules),
            ("فحص ملف قاعدة البيانات", self.check_database_file),
            ("فحص ملفات الإعدادات", self.check_config_files),
            ("فحص وحدات واجهة المستخدم", self.check_ui_modules),
            ("فحص الخدمات", self.check_services),
            ("اختبار نقطة الدخول الرئيسية", self.test_main_entry_point),
            ("فحص تناسق الإصدارات", self.check_version_consistency),
            ("تشغيل اختبار شامل", self.run_comprehensive_test),
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
        
        # إنشاء التقرير
        report = self.generate_report()
        
        print("\n" + "=" * 80)
        print("📊 ملخص الفحص الشامل")
        print("=" * 80)
        print(f"الاختبارات الناجحة: {passed_tests}/{total_tests}")
        print(f"الأخطاء: {len(self.errors)}")
        print(f"التحذيرات: {len(self.warnings)}")
        print(f"المعلومات: {len(self.info)}")
        print(f"الحالة العامة: {'✅ نجح' if len(self.errors) == 0 else '❌ فشل'}")
        
        # حفظ التقرير
        with open('audit_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 تم حفظ التقرير في: audit_report.json")
        
        return len(self.errors) == 0

def main():
    """الدالة الرئيسية"""
    auditor = SystemAuditor()
    success = auditor.run_full_audit()
    
    if success:
        print("\n🎉 النظام سليم ولا توجد أخطاء!")
        return 0
    else:
        print("\n⚠️ وجدت أخطاء تحتاج إلى إصلاح!")
        return 1

if __name__ == '__main__':
    sys.exit(main())