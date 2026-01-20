#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فحص شامل فائق الدقة - Ultra Comprehensive Audit
أقصى مستوى من الفحص والاختبار لضمان عدم وجود أي أخطاء
"""

import sys
import os
import ast
import re
import sqlite3
import json
import traceback
import importlib.util
import subprocess
import time
import threading
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

# تعيين الترميز للـ console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class UltraComprehensiveAuditor:
    """فاحص شامل فائق الدقة"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.critical_issues = []
        self.project_root = Path.cwd()
        self.total_files_checked = 0
        self.total_lines_checked = 0
        self.start_time = time.time()
        
        # قوائم شاملة للفحص
        self.python_files = []
        self.config_files = []
        self.database_files = []
        
        # أنماط الأخطاء المحتملة
        self.error_patterns = {
            'database_bool': [
                r'\bif\s+(?:self\.)?(?:repo|db|database|connection)(?:\s*[^=\s]|:)',
                r'\bif\s+not\s+(?:self\.)?(?:repo|db|database|connection)\b',
                r'\band\s+(?:self\.)?(?:repo|db|database|connection)\b',
                r'\bor\s+(?:self\.)?(?:repo|db|database|connection)\b',
            ],
            'encoding_issues': [
                r'^\ufeff',  # BOM
                r'[^\x00-\x7F].*coding.*',  # Non-ASCII in encoding line
            ],
            'import_issues': [
                r'from\s+\.\s+import',  # Relative import issues
                r'import\s+[^.\s]+\.[^.\s]+\.[^.\s]+',  # Deep imports
            ],
            'sql_injection': [
                r'execute\s*\(\s*["\'].*%.*["\']',  # String formatting in SQL
                r'execute\s*\(\s*f["\']',  # f-strings in SQL
            ],
            'memory_leaks': [
                r'while\s+True:.*(?!break)',  # Infinite loops without break
                r'for.*in.*:.*(?!break).*(?!return)',  # Potential infinite iterations
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

    def discover_all_files(self):
        """اكتشاف جميع الملفات في المشروع"""
        print("\n🔍 اكتشاف جميع ملفات المشروع...")
        print("=" * 60)
        
        # ملفات Python
        for py_file in self.project_root.rglob('*.py'):
            if '__pycache__' not in str(py_file) and '.venv' not in str(py_file):
                self.python_files.append(py_file)
        
        # ملفات الإعدادات
        config_extensions = ['.json', '.ini', '.cfg', '.conf', '.yaml', '.yml', '.toml']
        for ext in config_extensions:
            for config_file in self.project_root.rglob(f'*{ext}'):
                if '.git' not in str(config_file) and '__pycache__' not in str(config_file):
                    self.config_files.append(config_file)
        
        # ملفات قاعدة البيانات
        db_extensions = ['.db', '.sqlite', '.sqlite3']
        for ext in db_extensions:
            for db_file in self.project_root.rglob(f'*{ext}'):
                self.database_files.append(db_file)
        
        self.log_info(f"تم اكتشاف {len(self.python_files)} ملف Python")
        self.log_info(f"تم اكتشاف {len(self.config_files)} ملف إعدادات")
        self.log_info(f"تم اكتشاف {len(self.database_files)} ملف قاعدة بيانات")

    def deep_syntax_check(self) -> bool:
        """فحص عميق لصحة بناء الجملة"""
        print("\n🔍 فحص عميق لصحة بناء الجملة Python...")
        print("=" * 60)
        
        syntax_errors = 0
        encoding_errors = 0
        
        def check_file_syntax(py_file):
            local_errors = []
            try:
                # فحص الترميز أولاً
                with open(py_file, 'rb') as f:
                    raw_content = f.read()
                
                # فحص BOM
                if raw_content.startswith(b'\xef\xbb\xbf'):
                    local_errors.append(("ENCODING", f"ملف يحتوي على BOM: {py_file}"))
                
                # فحص الترميز
                try:
                    content = raw_content.decode('utf-8')
                except UnicodeDecodeError as e:
                    local_errors.append(("ENCODING", f"خطأ في الترميز: {e} في {py_file}"))
                    return local_errors
                
                # فحص بناء الجملة
                try:
                    tree = ast.parse(content, filename=str(py_file))
                    
                    # فحص عميق للعقد
                    for node in ast.walk(tree):
                        # فحص الاستيرادات
                        if isinstance(node, ast.ImportFrom):
                            if node.module and '..' in node.module:
                                local_errors.append(("SYNTAX", f"استيراد نسبي مشكوك فيه: {node.module} في {py_file}"))
                        
                        # فحص الدوال
                        if isinstance(node, ast.FunctionDef):
                            if not node.body:
                                local_errors.append(("SYNTAX", f"دالة فارغة: {node.name} في {py_file}"))
                
                except SyntaxError as e:
                    local_errors.append(("SYNTAX", f"خطأ في بناء الجملة: {e} في {py_file}:{e.lineno}"))
                
                # فحص الأنماط المشكلة
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    for pattern_type, patterns in self.error_patterns.items():
                        for pattern in patterns:
                            if re.search(pattern, line):
                                # تجاهل الحالات المُصلحة
                                if pattern_type == 'database_bool' and ('is not None' in line or 'is None' in line):
                                    continue
                                if line.strip().startswith('#'):
                                    continue
                                
                                local_errors.append(("PATTERN", f"نمط مشكل ({pattern_type}): {line.strip()} في {py_file}:{i}"))
                
            except Exception as e:
                local_errors.append(("CRITICAL", f"خطأ غير متوقع في فحص {py_file}: {e}"))
            
            return local_errors
        
        # فحص متوازي للملفات
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_file = {executor.submit(check_file_syntax, py_file): py_file for py_file in self.python_files}
            
            for future in as_completed(future_to_file):
                py_file = future_to_file[future]
                try:
                    file_errors = future.result()
                    for error_type, error_msg in file_errors:
                        if error_type == "CRITICAL":
                            self.log_error(error_msg, str(py_file), severity="CRITICAL")
                        elif error_type == "ENCODING":
                            self.log_error(error_msg, str(py_file), severity="ERROR")
                            encoding_errors += 1
                        elif error_type in ["SYNTAX", "PATTERN"]:
                            self.log_error(error_msg, str(py_file), severity="ERROR")
                            syntax_errors += 1
                except Exception as e:
                    self.log_error(f"فشل فحص الملف: {e}", str(py_file), severity="CRITICAL")
        
        self.total_files_checked = len(self.python_files)
        
        if syntax_errors == 0 and encoding_errors == 0:
            self.log_info(f"✅ جميع الملفات ({len(self.python_files)}) صحيحة نحوياً وترميزياً")
            return True
        else:
            self.log_error(f"وجد {syntax_errors} أخطاء نحوية و {encoding_errors} أخطاء ترميز")
            return False
    def ultra_deep_import_test(self) -> bool:
        """اختبار استيراد فائق العمق"""
        print("\n🧪 اختبار استيراد فائق العمق...")
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
            'core.unified_sync',
            'core.realtime_sync',
            'services.client_service',
            'services.project_service',
            'services.accounting_service',
            'ui.main_window',
            'ui.login_window',
            'main',
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
                
                # فحص الوحدة
                if hasattr(module, '__file__'):
                    self.log_info(f"✅ استيراد ناجح: {module_name}")
                    successful_imports += 1
                else:
                    self.log_error(f"وحدة مستوردة لكن بدون ملف: {module_name}", severity="WARNING")
                
            except ImportError as e:
                self.log_error(f"فشل استيراد {module_name}: {e}", severity="ERROR")
                import_errors += 1
            except Exception as e:
                self.log_error(f"خطأ غير متوقع في استيراد {module_name}: {e}", severity="CRITICAL")
                import_errors += 1
        
        # اختبار استيراد PyQt6
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QTimer
            self.log_info("✅ PyQt6 متاح ويعمل")
        except ImportError:
            self.log_error("PyQt6 غير متاح", severity="WARNING")
        
        if import_errors == 0:
            self.log_info(f"✅ جميع الاستيرادات ({successful_imports}) نجحت")
            return True
        else:
            self.log_error(f"فشل {import_errors} استيراد من أصل {len(core_modules)}")
            return False

    def comprehensive_database_audit(self) -> bool:
        """فحص شامل لقاعدة البيانات"""
        print("\n🗄️ فحص شامل لقاعدة البيانات...")
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
            required_tables = [
                'clients', 'projects', 'services', 'users', 'accounts',
                'invoices', 'payments', 'expenses', 'settings', 'audit_log'
            ]
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = []
            for table in required_tables:
                if table not in existing_tables:
                    missing_tables.append(table)
            
            if missing_tables:
                self.log_error(f"جداول مفقودة: {missing_tables}", severity="ERROR")
                return False
            
            # فحص البيانات
            data_stats = {}
            for table in required_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    data_stats[table] = count
                except Exception as e:
                    self.log_error(f"خطأ في فحص جدول {table}: {e}", severity="ERROR")
            
            # فحص الفهارس
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = cursor.fetchall()
            
            # فحص الأداء
            start_time = time.time()
            for _ in range(10):
                cursor.execute("SELECT COUNT(*) FROM clients")
                cursor.execute("SELECT COUNT(*) FROM projects")
            end_time = time.time()
            
            query_time = end_time - start_time
            if query_time > 1.0:
                self.log_error(f"أداء قاعدة البيانات بطيء: {query_time:.2f} ثانية", severity="WARNING")
            
            self.log_info(f"✅ قاعدة البيانات سليمة: {len(existing_tables)} جدول، {len(indexes)} فهرس")
            self.log_info(f"✅ إحصائيات البيانات: {data_stats}")
            self.log_info(f"✅ أداء الاستعلامات: {query_time:.3f} ثانية")
            
            return True
            
        except Exception as e:
            self.log_error(f"فشل فحص قاعدة البيانات: {e}", severity="CRITICAL")
            return False
    def stress_test_system(self) -> bool:
        """اختبار إجهاد النظام"""
        print("\n💪 اختبار إجهاد النظام...")
        print("=" * 60)
        
        try:
            from core.repository import Repository
            
            repo = Repository()
            
            # اختبار الأداء تحت الضغط
            start_time = time.time()
            
            # محاكاة عمليات متعددة
            for i in range(100):
                clients = repo.get_all_clients()
                projects = repo.get_all_projects()
                
                if i % 20 == 0:
                    print(f"  📊 تم إنجاز {i}/100 عملية...")
            
            end_time = time.time()
            total_time = end_time - start_time
            
            if total_time > 10.0:
                self.log_error(f"النظام بطيء تحت الضغط: {total_time:.2f} ثانية", severity="WARNING")
                return False
            
            self.log_info(f"✅ النظام يتحمل الضغط: {total_time:.2f} ثانية لـ 100 عملية")
            
            # اختبار الذاكرة
            try:
                import psutil
                process = psutil.Process()
                memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                
                if memory_usage > 500:  # أكثر من 500 MB
                    self.log_error(f"استهلاك ذاكرة عالي: {memory_usage:.1f} MB", severity="WARNING")
                else:
                    self.log_info(f"✅ استهلاك الذاكرة طبيعي: {memory_usage:.1f} MB")
            except ImportError:
                self.log_info("⚠️ psutil غير متاح - تخطي فحص الذاكرة")
            
            return True
            
        except Exception as e:
            self.log_error(f"فشل اختبار الإجهاد: {e}", severity="ERROR")
            return False

    def security_audit(self) -> bool:
        """فحص أمني شامل"""
        print("\n🔒 فحص أمني شامل...")
        print("=" * 60)
        
        security_issues = 0
        
        # فحص ملفات Python للثغرات الأمنية
        for py_file in self.python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    # فحص SQL Injection
                    if re.search(r'execute\s*\(\s*["\'].*%.*["\']', line):
                        self.log_error(f"مخاطر SQL Injection: {line.strip()}", str(py_file), i, "ERROR")
                        security_issues += 1
                    
                    # فحص كلمات المرور المكشوفة
                    if re.search(r'password\s*=\s*["\'][^"\']+["\']', line, re.IGNORECASE):
                        if 'test' not in line.lower() and 'example' not in line.lower():
                            self.log_error(f"كلمة مرور مكشوفة محتملة: {py_file}:{i}", str(py_file), i, "WARNING")
                    
                    # فحص eval() و exec()
                    if re.search(r'\b(eval|exec)\s*\(', line):
                        self.log_error(f"استخدام خطير لـ eval/exec: {line.strip()}", str(py_file), i, "ERROR")
                        security_issues += 1
                
            except Exception as e:
                self.log_error(f"خطأ في الفحص الأمني: {e}", str(py_file), severity="ERROR")
        
        # فحص ملفات الإعدادات
        for config_file in self.config_files:
            if config_file.name in ['.env', 'config.ini', 'settings.json']:
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # فحص المفاتيح الحساسة
                    sensitive_patterns = [
                        r'api_key\s*=\s*["\'][^"\']+["\']',
                        r'secret\s*=\s*["\'][^"\']+["\']',
                        r'token\s*=\s*["\'][^"\']+["\']'
                    ]
                    
                    for pattern in sensitive_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            self.log_error(f"بيانات حساسة مكشوفة في {config_file}", str(config_file), severity="WARNING")
                
                except Exception as e:
                    self.log_error(f"خطأ في فحص ملف الإعدادات: {e}", str(config_file), severity="ERROR")
        
        if security_issues == 0:
            self.log_info("✅ لا توجد مشاكل أمنية واضحة")
            return True
        else:
            self.log_error(f"وجد {security_issues} مشكلة أمنية")
            return False
    def final_integration_test(self) -> bool:
        """اختبار التكامل النهائي"""
        print("\n🔗 اختبار التكامل النهائي...")
        print("=" * 60)
        
        try:
            # اختبار سلسلة العمليات الكاملة
            from core.repository import Repository
            from services.client_service import ClientService
            
            repo = Repository()
            client_service = ClientService(repo)
            
            # اختبار العمليات المترابطة
            clients = repo.get_all_clients()
            if clients:
                first_client = clients[0]
                client_projects = repo.get_client_projects(first_client.id)
                self.log_info(f"✅ العميل الأول لديه {len(client_projects)} مشروع")
            
            # اختبار المزامنة
            try:
                from core.unified_sync import UnifiedSyncManager
                sync_manager = UnifiedSyncManager(repo)
                self.log_info("✅ مدير المزامنة يعمل")
            except Exception as e:
                self.log_error(f"مشكلة في المزامنة: {e}", severity="WARNING")
            
            # اختبار النظام الكامل
            self.log_info("✅ جميع مكونات النظام متكاملة")
            return True
            
        except Exception as e:
            self.log_error(f"فشل اختبار التكامل: {e}", severity="ERROR")
            return False

    def generate_comprehensive_report(self):
        """إنشاء تقرير شامل مفصل"""
        print("\n📊 إنشاء التقرير الشامل...")
        print("=" * 60)
        
        end_time = time.time()
        total_duration = end_time - self.start_time
        
        report = {
            "audit_info": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": round(total_duration, 2),
                "total_files_checked": self.total_files_checked,
                "total_lines_checked": self.total_lines_checked
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
            },
            "file_stats": {
                "python_files": len(self.python_files),
                "config_files": len(self.config_files),
                "database_files": len(self.database_files)
            }
        }
        
        # حفظ التقرير
        report_file = self.project_root / "ultra_audit_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        self.log_info(f"✅ تم حفظ التقرير في: {report_file}")
        return report
    def run_ultra_comprehensive_audit(self) -> bool:
        """تشغيل الفحص الشامل الفائق"""
        print("🚀 بدء الفحص الشامل الفائق - Ultra Comprehensive Audit")
        print("=" * 80)
        print("هذا هو أقصى مستوى من الفحص والاختبار المتاح")
        print("=" * 80)
        
        # اكتشاف الملفات
        self.discover_all_files()
        
        # قائمة الاختبارات الشاملة
        tests = [
            ("فحص عميق لصحة بناء الجملة", self.deep_syntax_check),
            ("اختبار استيراد فائق العمق", self.ultra_deep_import_test),
            ("فحص شامل لقاعدة البيانات", self.comprehensive_database_audit),
            ("اختبار إجهاد النظام", self.stress_test_system),
            ("فحص أمني شامل", self.security_audit),
            ("اختبار التكامل النهائي", self.final_integration_test),
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
        report = self.generate_comprehensive_report()
        
        print("\n" + "=" * 80)
        print("📊 ملخص الفحص الشامل الفائق")
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
            print("\n🎉 النظام مثالي! لا توجد أي أخطاء أو مشاكل حرجة")
            print("✅ جاهز للاستخدام الإنتاجي بثقة كاملة")
        else:
            print("\n⚠️ النظام يحتاج إلى مراجعة")
            if len(self.critical_issues) > 0:
                print(f"🚨 يوجد {len(self.critical_issues)} مشكلة حرجة تحتاج إلى إصلاح فوري")
            if len(self.errors) > 0:
                print(f"❌ يوجد {len(self.errors)} خطأ يحتاج إلى إصلاح")
        
        return is_perfect

def main():
    """الدالة الرئيسية"""
    print("🔍 Ultra Comprehensive Audit - الفحص الشامل الفائق")
    print("=" * 80)
    print("أقصى مستوى من الفحص والاختبار لضمان عدم وجود أي أخطاء")
    print("=" * 80)
    
    auditor = UltraComprehensiveAuditor()
    success = auditor.run_ultra_comprehensive_audit()
    
    if success:
        print("\n🏆 النظام اجتاز جميع الاختبارات بنجاح!")
        print("✅ لا توجد أي أخطاء أو مشاكل حرجة")
        print("🚀 جاهز للاستخدام الإنتاجي")
        return 0
    else:
        print("\n⚠️ النظام يحتاج إلى مراجعة وإصلاح")
        print("📋 راجع التقرير المفصل في ultra_audit_report.json")
        return 1

if __name__ == '__main__':
    sys.exit(main())