#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 فحص شامل احترافي بدون أخطاء - Zero Errors Audit
يفحص كل جوانب النظام بدقة عالية
"""

import ast
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

class ZeroErrorsAuditor:
    """فاحص شامل بدون أخطاء"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.start_time = time.time()
        
    def log(self, level: str, message: str, file_path: str = None):
        """تسجيل رسالة"""
        entry = {
            "level": level,
            "message": message,
            "file": file_path,
            "timestamp": time.time()
        }
        
        if level == "ERROR":
            self.errors.append(entry)
            print(f"❌ ERROR: {message}" + (f" في {file_path}" if file_path else ""))
        elif level == "WARNING":
            self.warnings.append(entry)
            print(f"⚠️ WARNING: {message}" + (f" في {file_path}" if file_path else ""))
        else:
            self.info.append(entry)
            print(f"ℹ️ INFO: {message}")
    
    def check_python_syntax(self) -> bool:
        """فحص صحة بناء الجملة Python"""
        print("\n🔍 فحص صحة بناء الجملة Python...")
        has_errors = False
        
        for py_file in Path(".").rglob("*.py"):
            if any(x in str(py_file) for x in [".venv", "__pycache__", "build", "dist"]):
                continue
            
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    code = f.read()
                    ast.parse(code)
            except SyntaxError as e:
                self.log("ERROR", f"خطأ نحوي: {e}", str(py_file))
                has_errors = True
            except Exception as e:
                self.log("WARNING", f"فشل فحص الملف: {e}", str(py_file))
        
        if not has_errors:
            self.log("INFO", "✅ جميع ملفات Python صحيحة نحوياً")
        
        return not has_errors
    
    def check_imports(self) -> bool:
        """فحص الاستيرادات"""
        print("\n🔍 فحص الاستيرادات...")
        has_errors = False
        
        # فحص التبعيات الأساسية
        required_packages = {
            "PyQt6": "PyQt6.QtCore",
            "pymongo": "pymongo",
            "pydantic": "pydantic",
            "Jinja2": "jinja2",
            "reportlab": "reportlab",
            "pandas": "pandas"
        }
        
        for package_name, import_name in required_packages.items():
            try:
                __import__(import_name)
                self.log("INFO", f"✅ {package_name} متوفر")
            except ImportError:
                self.log("ERROR", f"الحزمة {package_name} غير متوفرة")
                has_errors = True
        
        return not has_errors
    
    def check_database(self) -> bool:
        """فحص قاعدة البيانات"""
        print("\n🔍 فحص قاعدة البيانات...")
        has_errors = False
        
        db_file = "skywave_local.db"
        if not os.path.exists(db_file):
            self.log("WARNING", f"ملف قاعدة البيانات {db_file} غير موجود")
            return True  # ليس خطأ حرج
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # فحص الجداول الأساسية
            required_tables = [
                "clients", "projects", "services", "invoices",
                "expenses", "accounts", "journal_entries",
                "payments", "users", "employees"
            ]
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            for table in required_tables:
                if table in existing_tables:
                    self.log("INFO", f"✅ جدول {table} موجود")
                else:
                    self.log("ERROR", f"جدول {table} مفقود")
                    has_errors = True
            
            conn.close()
        except Exception as e:
            self.log("ERROR", f"فشل فحص قاعدة البيانات: {e}")
            has_errors = True
        
        return not has_errors
    
    def check_config_files(self) -> bool:
        """فحص ملفات التكوين"""
        print("\n🔍 فحص ملفات التكوين...")
        has_errors = False
        
        config_files = {
            "requirements.txt": "ملف التبعيات",
            "version.json": "ملف الإصدار",
            ".env.example": "مثال ملف البيئة"
        }
        
        for file_path, description in config_files.items():
            if os.path.exists(file_path):
                self.log("INFO", f"✅ {description} موجود")
            else:
                self.log("WARNING", f"{description} مفقود: {file_path}")
        
        # فحص version.json
        if os.path.exists("version.json"):
            try:
                with open("version.json", "r", encoding="utf-8") as f:
                    version_data = json.load(f)
                    required_keys = ["version", "version_name", "release_date"]
                    for key in required_keys:
                        if key not in version_data:
                            self.log("ERROR", f"مفتاح {key} مفقود في version.json")
                            has_errors = True
            except Exception as e:
                self.log("ERROR", f"فشل قراءة version.json: {e}")
                has_errors = True
        
        return not has_errors
    
    def check_main_files(self) -> bool:
        """فحص الملفات الرئيسية"""
        print("\n🔍 فحص الملفات الرئيسية...")
        has_errors = False
        
        main_files = [
            "main.py",
            "core/repository.py",
            "core/config.py",
            "ui/main_window.py",
            "ui/login_window.py"
        ]
        
        for file_path in main_files:
            if os.path.exists(file_path):
                self.log("INFO", f"✅ {file_path} موجود")
                
                # فحص حجم الملف
                size = os.path.getsize(file_path)
                if size == 0:
                    self.log("ERROR", f"الملف {file_path} فارغ")
                    has_errors = True
            else:
                self.log("ERROR", f"الملف {file_path} مفقود")
                has_errors = True
        
        return not has_errors
    
    def check_code_quality(self) -> bool:
        """فحص جودة الكود"""
        print("\n🔍 فحص جودة الكود...")
        
        # فحص الأنماط السيئة
        bad_patterns = {
            r"print\(": "استخدام print بدلاً من logger",
            r"except\s*:": "استخدام except عام بدون تحديد الاستثناء",
            r"TODO|FIXME": "تعليقات TODO/FIXME"
        }
        
        issues_count = 0
        for py_file in Path(".").rglob("*.py"):
            if any(x in str(py_file) for x in [".venv", "__pycache__", "build", "dist"]):
                continue
            
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                    # فحص الأنماط
                    import re
                    for pattern, description in bad_patterns.items():
                        matches = re.findall(pattern, content)
                        if matches:
                            issues_count += len(matches)
                            self.log("WARNING", f"{description}: {len(matches)} مرة", str(py_file))
            except Exception:
                pass
        
        if issues_count == 0:
            self.log("INFO", "✅ لا توجد مشاكل في جودة الكود")
        else:
            self.log("INFO", f"وجد {issues_count} مشكلة في جودة الكود")
        
        return True  # ليست أخطاء حرجة
    
    def run_full_audit(self) -> bool:
        """تشغيل الفحص الشامل"""
        print("=" * 80)
        print("🚀 بدء الفحص الشامل - Zero Errors Audit")
        print("=" * 80)
        
        checks = [
            ("فحص بناء الجملة", self.check_python_syntax),
            ("فحص الاستيرادات", self.check_imports),
            ("فحص قاعدة البيانات", self.check_database),
            ("فحص ملفات التكوين", self.check_config_files),
            ("فحص الملفات الرئيسية", self.check_main_files),
            ("فحص جودة الكود", self.check_code_quality)
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            try:
                result = check_func()
                if not result:
                    all_passed = False
            except Exception as e:
                self.log("ERROR", f"فشل {check_name}: {e}")
                all_passed = False
        
        # إنشاء التقرير
        self.generate_report()
        
        return all_passed
    
    def generate_report(self):
        """إنشاء تقرير الفحص"""
        print("\n" + "=" * 80)
        print("📊 تقرير الفحص الشامل")
        print("=" * 80)
        
        duration = time.time() - self.start_time
        
        report = {
            "timestamp": time.time(),
            "duration_seconds": duration,
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "info_count": len(self.info),
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "status": "PASS" if len(self.errors) == 0 else "FAIL"
        }
        
        # حفظ التقرير
        report_file = "zero_errors_audit_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📈 الإحصائيات:")
        print(f"   ❌ أخطاء: {len(self.errors)}")
        print(f"   ⚠️ تحذيرات: {len(self.warnings)}")
        print(f"   ℹ️ معلومات: {len(self.info)}")
        print(f"   ⏱️ المدة: {duration:.2f} ثانية")
        print(f"\n📄 تم حفظ التقرير في: {report_file}")
        
        if len(self.errors) == 0:
            print("\n✅ النظام خالي من الأخطاء - ZERO ERRORS!")
        else:
            print(f"\n❌ وجد {len(self.errors)} خطأ يجب إصلاحه")
        
        print("=" * 80)

def main():
    """الدالة الرئيسية"""
    auditor = ZeroErrorsAuditor()
    success = auditor.run_full_audit()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
