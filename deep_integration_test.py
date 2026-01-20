#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔬 اختبار التكامل العميق - Deep Integration Test
اختبار فعلي لجميع مكونات النظام
"""

import json
import os
import sqlite3
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

class DeepIntegrationTester:
    """فاحص التكامل العميق"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []
        self.start_time = time.time()
        
    def log(self, level: str, test_name: str, message: str, details: str = None):
        """تسجيل نتيجة الاختبار"""
        entry = {
            "level": level,
            "test": test_name,
            "message": message,
            "details": details,
            "timestamp": time.time()
        }
        
        if level == "ERROR":
            self.errors.append(entry)
            print(f"❌ FAIL: {test_name} - {message}")
            if details:
                print(f"   Details: {details}")
        elif level == "WARNING":
            self.warnings.append(entry)
            print(f"⚠️ WARN: {test_name} - {message}")
        else:
            self.passed.append(entry)
            print(f"✅ PASS: {test_name}")
    
    def test_database_operations(self) -> bool:
        """اختبار عمليات قاعدة البيانات الفعلية"""
        print("\n" + "="*80)
        print("🔍 اختبار عمليات قاعدة البيانات")
        print("="*80)
        
        db_file = "skywave_local.db"
        if not os.path.exists(db_file):
            self.log("WARNING", "Database File", "ملف قاعدة البيانات غير موجود")
            return True
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # اختبار 1: قراءة من جدول clients
            try:
                cursor.execute("SELECT COUNT(*) FROM clients")
                count = cursor.fetchone()[0]
                self.log("PASS", "DB Read - Clients", f"تم قراءة {count} عميل")
            except Exception as e:
                self.log("ERROR", "DB Read - Clients", "فشل قراءة جدول العملاء", str(e))
            
            # اختبار 2: قراءة من جدول projects
            try:
                cursor.execute("SELECT COUNT(*) FROM projects")
                count = cursor.fetchone()[0]
                self.log("PASS", "DB Read - Projects", f"تم قراءة {count} مشروع")
            except Exception as e:
                self.log("ERROR", "DB Read - Projects", "فشل قراءة جدول المشاريع", str(e))
            
            # اختبار 3: قراءة من جدول users
            try:
                cursor.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()[0]
                self.log("PASS", "DB Read - Users", f"تم قراءة {count} مستخدم")
            except Exception as e:
                self.log("ERROR", "DB Read - Users", "فشل قراءة جدول المستخدمين", str(e))
            
            # اختبار 4: فحص الـ indexes
            try:
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
                count = cursor.fetchone()[0]
                if count >= 50:
                    self.log("PASS", "DB Indexes", f"يوجد {count} index")
                else:
                    self.log("WARNING", "DB Indexes", f"عدد الـ indexes قليل: {count}")
            except Exception as e:
                self.log("ERROR", "DB Indexes", "فشل فحص الـ indexes", str(e))
            
            # اختبار 5: فحص سلامة البيانات
            try:
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
                if result == "ok":
                    self.log("PASS", "DB Integrity", "قاعدة البيانات سليمة")
                else:
                    self.log("ERROR", "DB Integrity", "مشكلة في سلامة قاعدة البيانات", result)
            except Exception as e:
                self.log("ERROR", "DB Integrity", "فشل فحص السلامة", str(e))
            
            conn.close()
            return len(self.errors) == 0
            
        except Exception as e:
            self.log("ERROR", "Database Connection", "فشل الاتصال بقاعدة البيانات", str(e))
            return False
    
    def test_core_modules_import(self) -> bool:
        """اختبار استيراد جميع الوحدات الأساسية"""
        print("\n" + "="*80)
        print("🔍 اختبار استيراد الوحدات الأساسية")
        print("="*80)
        
        core_modules = [
            "core.repository",
            "core.config",
            "core.schemas",
            "core.logger",
            "core.auth_models",
            "core.event_bus",
            "core.error_handler",
            "core.safe_print",
            "core.speed_optimizer",
            "core.performance_optimizer",
            "core.unified_sync",
            "core.sync_manager_v3",
            "core.advanced_sync_manager"
        ]
        
        for module_name in core_modules:
            try:
                __import__(module_name)
                self.log("PASS", f"Import {module_name}", "نجح الاستيراد")
            except Exception as e:
                self.log("ERROR", f"Import {module_name}", "فشل الاستيراد", str(e))
        
        return len(self.errors) == 0
    
    def test_services_import(self) -> bool:
        """اختبار استيراد جميع الخدمات"""
        print("\n" + "="*80)
        print("🔍 اختبار استيراد الخدمات")
        print("="*80)
        
        services = [
            "services.accounting_service",
            "services.client_service",
            "services.expense_service",
            "services.export_service",
            "services.invoice_service",
            "services.project_service",
            "services.service_service",
            "services.settings_service",
            "services.printing_service",
            "services.template_service",
            "services.notification_service"
        ]
        
        for service_name in services:
            try:
                __import__(service_name)
                self.log("PASS", f"Import {service_name}", "نجح الاستيراد")
            except Exception as e:
                self.log("ERROR", f"Import {service_name}", "فشل الاستيراد", str(e))
        
        return len(self.errors) == 0
    
    def test_ui_modules_import(self) -> bool:
        """اختبار استيراد وحدات الواجهة"""
        print("\n" + "="*80)
        print("🔍 اختبار استيراد وحدات الواجهة")
        print("="*80)
        
        ui_modules = [
            "ui.styles",
            "ui.login_window",
            "ui.main_window",
            "ui.dashboard_tab",
            "ui.settings_tab",
            "ui.client_manager",
            "ui.project_manager",
            "ui.accounting_manager",
            "ui.expense_manager",
            "ui.payments_manager",
            "ui.service_manager",
            "ui.unified_hr_manager",
            "ui.todo_manager",
            "ui.notification_system"
        ]
        
        for module_name in ui_modules:
            try:
                __import__(module_name)
                self.log("PASS", f"Import {module_name}", "نجح الاستيراد")
            except Exception as e:
                self.log("ERROR", f"Import {module_name}", "فشل الاستيراد", str(e))
        
        return len(self.errors) == 0
    
    def test_repository_instantiation(self) -> bool:
        """اختبار إنشاء Repository"""
        print("\n" + "="*80)
        print("🔍 اختبار إنشاء Repository")
        print("="*80)
        
        try:
            from core.repository import Repository
            repo = Repository()
            self.log("PASS", "Repository Creation", "تم إنشاء Repository بنجاح")
            
            # اختبار الاتصال بـ SQLite
            if repo.sqlite_conn:
                self.log("PASS", "SQLite Connection", "الاتصال بـ SQLite نشط")
            else:
                self.log("ERROR", "SQLite Connection", "فشل الاتصال بـ SQLite")
            
            # اختبار حالة MongoDB
            if repo.online:
                self.log("PASS", "MongoDB Connection", "متصل بـ MongoDB")
            else:
                self.log("WARNING", "MongoDB Connection", "غير متصل بـ MongoDB (وضع أوفلاين)")
            
            return True
            
        except Exception as e:
            self.log("ERROR", "Repository Creation", "فشل إنشاء Repository", str(e))
            traceback.print_exc()
            return False
    
    def test_schemas_validation(self) -> bool:
        """اختبار نماذج البيانات (Schemas)"""
        print("\n" + "="*80)
        print("🔍 اختبار نماذج البيانات")
        print("="*80)
        
        try:
            from core import schemas
            from datetime import datetime
            
            # اختبار Client schema
            try:
                client = schemas.Client(
                    name="عميل تجريبي",
                    status=schemas.ClientStatus.ACTIVE,
                    created_at=datetime.now(),
                    last_modified=datetime.now()
                )
                self.log("PASS", "Client Schema", "نموذج العميل يعمل")
            except Exception as e:
                self.log("ERROR", "Client Schema", "فشل نموذج العميل", str(e))
            
            # اختبار Project schema
            try:
                project = schemas.Project(
                    name="مشروع تجريبي",
                    client_id="test",
                    status="نشط",
                    created_at=datetime.now(),
                    last_modified=datetime.now()
                )
                self.log("PASS", "Project Schema", "نموذج المشروع يعمل")
            except Exception as e:
                self.log("ERROR", "Project Schema", "فشل نموذج المشروع", str(e))
            
            # اختبار Account schema
            try:
                account = schemas.Account(
                    name="حساب تجريبي",
                    code="1000",
                    type=schemas.AccountType.ASSET,
                    created_at=datetime.now(),
                    last_modified=datetime.now()
                )
                self.log("PASS", "Account Schema", "نموذج الحساب يعمل")
            except Exception as e:
                self.log("ERROR", "Account Schema", "فشل نموذج الحساب", str(e))
            
            return True
            
        except Exception as e:
            self.log("ERROR", "Schemas Import", "فشل استيراد Schemas", str(e))
            return False
    
    def test_config_loading(self) -> bool:
        """اختبار تحميل التكوين"""
        print("\n" + "="*80)
        print("🔍 اختبار تحميل التكوين")
        print("="*80)
        
        try:
            from core.config import Config
            
            # اختبار الحصول على إعدادات MongoDB
            try:
                mongo_uri = Config.get_mongo_uri()
                if mongo_uri:
                    self.log("PASS", "Config - MongoDB URI", "تم تحميل MongoDB URI")
                else:
                    self.log("WARNING", "Config - MongoDB URI", "MongoDB URI فارغ")
            except Exception as e:
                self.log("ERROR", "Config - MongoDB URI", "فشل تحميل MongoDB URI", str(e))
            
            # اختبار الحصول على مسار قاعدة البيانات المحلية
            try:
                db_path = Config.get_local_db_path()
                if db_path and os.path.exists(db_path):
                    self.log("PASS", "Config - Local DB Path", f"مسار قاعدة البيانات: {db_path}")
                else:
                    self.log("WARNING", "Config - Local DB Path", "ملف قاعدة البيانات غير موجود")
            except Exception as e:
                self.log("ERROR", "Config - Local DB Path", "فشل تحميل مسار قاعدة البيانات", str(e))
            
            return True
            
        except Exception as e:
            self.log("ERROR", "Config Loading", "فشل تحميل التكوين", str(e))
            return False
    
    def test_logger_functionality(self) -> bool:
        """اختبار نظام التسجيل"""
        print("\n" + "="*80)
        print("🔍 اختبار نظام التسجيل")
        print("="*80)
        
        try:
            from core.logger import LoggerSetup
            
            # إنشاء logger
            logger = LoggerSetup.setup_logger()
            
            if logger:
                self.log("PASS", "Logger Creation", "تم إنشاء Logger بنجاح")
                
                # اختبار الكتابة
                try:
                    logger.info("اختبار نظام التسجيل")
                    self.log("PASS", "Logger Write", "تم الكتابة إلى Logger")
                except Exception as e:
                    self.log("ERROR", "Logger Write", "فشل الكتابة إلى Logger", str(e))
            else:
                self.log("ERROR", "Logger Creation", "فشل إنشاء Logger")
            
            return True
            
        except Exception as e:
            self.log("ERROR", "Logger Import", "فشل استيراد Logger", str(e))
            return False
    
    def test_version_info(self) -> bool:
        """اختبار معلومات الإصدار"""
        print("\n" + "="*80)
        print("🔍 اختبار معلومات الإصدار")
        print("="*80)
        
        # فحص version.json
        if os.path.exists("version.json"):
            try:
                with open("version.json", "r", encoding="utf-8") as f:
                    version_data = json.load(f)
                
                version = version_data.get("version")
                if version:
                    self.log("PASS", "Version Info", f"الإصدار: {version}")
                else:
                    self.log("ERROR", "Version Info", "رقم الإصدار مفقود")
                
            except Exception as e:
                self.log("ERROR", "Version File", "فشل قراءة version.json", str(e))
        else:
            self.log("ERROR", "Version File", "ملف version.json مفقود")
        
        # فحص version.py
        try:
            from version import CURRENT_VERSION, APP_NAME
            self.log("PASS", "Version Module", f"{APP_NAME} v{CURRENT_VERSION}")
        except Exception as e:
            self.log("ERROR", "Version Module", "فشل استيراد version.py", str(e))
        
        return True
    
    def test_file_structure(self) -> bool:
        """اختبار بنية الملفات"""
        print("\n" + "="*80)
        print("🔍 اختبار بنية الملفات")
        print("="*80)
        
        required_dirs = ["core", "services", "ui", "assets", "tests"]
        required_files = ["main.py", "requirements.txt", "version.json", ".env.example"]
        
        # فحص المجلدات
        for dir_name in required_dirs:
            if os.path.isdir(dir_name):
                self.log("PASS", f"Directory - {dir_name}", "المجلد موجود")
            else:
                self.log("ERROR", f"Directory - {dir_name}", "المجلد مفقود")
        
        # فحص الملفات
        for file_name in required_files:
            if os.path.isfile(file_name):
                self.log("PASS", f"File - {file_name}", "الملف موجود")
            else:
                self.log("ERROR", f"File - {file_name}", "الملف مفقود")
        
        return True
    
    def run_all_tests(self) -> bool:
        """تشغيل جميع الاختبارات"""
        print("=" * 80)
        print("🚀 بدء اختبار التكامل العميق - Deep Integration Test")
        print("=" * 80)
        
        tests = [
            ("بنية الملفات", self.test_file_structure),
            ("معلومات الإصدار", self.test_version_info),
            ("تحميل التكوين", self.test_config_loading),
            ("نظام التسجيل", self.test_logger_functionality),
            ("نماذج البيانات", self.test_schemas_validation),
            ("استيراد الوحدات الأساسية", self.test_core_modules_import),
            ("استيراد الخدمات", self.test_services_import),
            ("استيراد وحدات الواجهة", self.test_ui_modules_import),
            ("إنشاء Repository", self.test_repository_instantiation),
            ("عمليات قاعدة البيانات", self.test_database_operations)
        ]
        
        all_passed = True
        
        for test_name, test_func in tests:
            try:
                print(f"\n▶️ {test_name}...")
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                self.log("ERROR", test_name, "فشل الاختبار", str(e))
                traceback.print_exc()
                all_passed = False
        
        # إنشاء التقرير
        self.generate_report()
        
        return all_passed
    
    def generate_report(self):
        """إنشاء تقرير الاختبار"""
        print("\n" + "=" * 80)
        print("📊 تقرير اختبار التكامل العميق")
        print("=" * 80)
        
        duration = time.time() - self.start_time
        
        report = {
            "timestamp": time.time(),
            "duration_seconds": duration,
            "passed_count": len(self.passed),
            "warnings_count": len(self.warnings),
            "errors_count": len(self.errors),
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "status": "PASS" if len(self.errors) == 0 else "FAIL"
        }
        
        # حفظ التقرير
        report_file = "deep_integration_test_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📈 الإحصائيات:")
        print(f"   ✅ نجح: {len(self.passed)}")
        print(f"   ⚠️ تحذيرات: {len(self.warnings)}")
        print(f"   ❌ أخطاء: {len(self.errors)}")
        print(f"   ⏱️ المدة: {duration:.2f} ثانية")
        print(f"\n📄 تم حفظ التقرير في: {report_file}")
        
        if len(self.errors) == 0:
            print("\n" + "🎉" * 40)
            print("✅ جميع اختبارات التكامل نجحت!")
            print("🎉" * 40)
        else:
            print(f"\n❌ وجد {len(self.errors)} خطأ في اختبارات التكامل")
        
        print("=" * 80)

def main():
    """الدالة الرئيسية"""
    tester = DeepIntegrationTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
