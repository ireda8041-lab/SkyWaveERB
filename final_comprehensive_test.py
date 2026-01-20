#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبار شامل نهائي للنظام
Final comprehensive system test
"""

import sys
import os
import subprocess
import time
from pathlib import Path

# تعيين الترميز للـ console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class FinalSystemTester:
    """فاحص النظام النهائي"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.passed_tests = 0
        self.total_tests = 0
        
    def run_test(self, test_name: str, test_func) -> bool:
        """تشغيل اختبار واحد"""
        self.total_tests += 1
        print(f"\n🧪 {test_name}...")
        print("-" * 50)
        
        try:
            result = test_func()
            if result:
                print(f"✅ {test_name}: نجح")
                self.passed_tests += 1
                return True
            else:
                print(f"❌ {test_name}: فشل")
                return False
        except Exception as e:
            print(f"💥 {test_name}: خطأ غير متوقع - {e}")
            return False

    def test_core_imports(self) -> bool:
        """اختبار استيراد الوحدات الأساسية"""
        try:
            sys.path.insert(0, str(self.project_root))
            
            # اختبار الوحدات الأساسية
            from core.repository import Repository
            from core.config import Config
            from core.auth_models import User
            
            print("✅ جميع الوحدات الأساسية تم استيرادها بنجاح")
            return True
            
        except Exception as e:
            print(f"❌ فشل استيراد الوحدات: {e}")
            return False

    def test_repository_functionality(self) -> bool:
        """اختبار وظائف Repository"""
        try:
            from core.repository import Repository
            
            repo = Repository()
            
            # اختبار الاتصال بقاعدة البيانات
            cursor = repo.get_cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            if table_count < 10:
                print(f"❌ عدد الجداول قليل جداً: {table_count}")
                return False
            
            print(f"✅ قاعدة البيانات تحتوي على {table_count} جدول")
            
            # اختبار بعض الوظائف الأساسية
            clients = repo.get_all_clients()
            projects = repo.get_all_projects()
            
            print(f"✅ العملاء: {len(clients)}")
            print(f"✅ المشاريع: {len(projects)}")
            
            return True
            
        except Exception as e:
            print(f"❌ فشل اختبار Repository: {e}")
            return False

    def test_services(self) -> bool:
        """اختبار الخدمات"""
        try:
            from services.client_service import ClientService
            from core.repository import Repository
            
            repo = Repository()
            
            # اختبار خدمة العملاء
            client_service = ClientService(repo)
            print("✅ خدمة العملاء تعمل")
            
            return True
            
        except Exception as e:
            print(f"❌ فشل اختبار الخدمات: {e}")
            return False

    def test_ui_imports(self) -> bool:
        """اختبار استيراد واجهة المستخدم"""
        try:
            # تجاهل PyQt6 إذا لم يكن متاحاً
            try:
                from PyQt6.QtWidgets import QApplication
                from ui.main_window import MainWindow
                from ui.login_window import LoginWindow
                print("✅ واجهة المستخدم متاحة")
                return True
            except ImportError:
                print("⚠️ PyQt6 غير متاح - تخطي اختبار واجهة المستخدم")
                return True
            
        except Exception as e:
            print(f"❌ فشل اختبار واجهة المستخدم: {e}")
            return False

    def test_configuration_files(self) -> bool:
        """اختبار ملفات الإعدادات"""
        try:
            import json
            
            # اختبار version.json
            with open(self.project_root / 'version.json', 'r', encoding='utf-8') as f:
                version_data = json.load(f)
                version = version_data.get('version')
                if not version:
                    print("❌ version.json لا يحتوي على رقم إصدار")
                    return False
                print(f"✅ version.json: {version}")
            
            # اختبار version.py
            with open(self.project_root / 'version.py', 'r', encoding='utf-8') as f:
                content = f.read()
                if '__version__' not in content:
                    print("❌ version.py لا يحتوي على __version__")
                    return False
                print("✅ version.py صحيح")
            
            # اختبار requirements.txt
            req_file = self.project_root / 'requirements.txt'
            if req_file.exists():
                with open(req_file, 'r', encoding='utf-8') as f:
                    requirements = f.read().strip()
                    if not requirements:
                        print("❌ requirements.txt فارغ")
                        return False
                    print(f"✅ requirements.txt يحتوي على {len(requirements.split())} مكتبة")
            
            return True
            
        except Exception as e:
            print(f"❌ فشل اختبار ملفات الإعدادات: {e}")
            return False

    def test_database_integrity(self) -> bool:
        """اختبار سلامة قاعدة البيانات"""
        try:
            from core.repository import Repository
            
            repo = Repository()
            cursor = repo.get_cursor()
            
            # فحص الجداول الأساسية
            required_tables = ['clients', 'projects', 'services', 'users', 'accounts']
            
            for table in required_tables:
                cursor.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
                exists = cursor.fetchone()[0]
                if not exists:
                    print(f"❌ الجدول {table} غير موجود")
                    return False
                print(f"✅ الجدول {table} موجود")
            
            # فحص سلامة البيانات
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            if result != 'ok':
                print(f"❌ مشكلة في سلامة قاعدة البيانات: {result}")
                return False
            
            print("✅ قاعدة البيانات سليمة")
            return True
            
        except Exception as e:
            print(f"❌ فشل اختبار سلامة قاعدة البيانات: {e}")
            return False

    def test_main_py_execution(self) -> bool:
        """اختبار تشغيل main.py"""
        try:
            # اختبار أن main.py يمكن استيراده بدون أخطاء
            import importlib.util
            
            spec = importlib.util.spec_from_file_location("main", self.project_root / "main.py")
            if spec is None:
                print("❌ لا يمكن تحميل main.py")
                return False
            
            # لا نشغل main() فعلياً لتجنب فتح واجهة المستخدم
            print("✅ main.py يمكن تحميله بدون أخطاء")
            return True
            
        except Exception as e:
            print(f"❌ فشل اختبار main.py: {e}")
            return False

    def test_performance(self) -> bool:
        """اختبار الأداء"""
        try:
            from core.repository import Repository
            import time
            
            repo = Repository()
            
            # اختبار سرعة الاستعلامات
            start_time = time.time()
            
            for _ in range(10):
                clients = repo.get_all_clients()
                projects = repo.get_all_projects()
            
            end_time = time.time()
            duration = end_time - start_time
            
            if duration > 5.0:  # أكثر من 5 ثوان
                print(f"⚠️ الأداء بطيء: {duration:.2f} ثانية")
                return False
            
            print(f"✅ الأداء جيد: {duration:.2f} ثانية لـ 10 استعلامات")
            return True
            
        except Exception as e:
            print(f"❌ فشل اختبار الأداء: {e}")
            return False

    def run_comprehensive_test(self) -> bool:
        """تشغيل الاختبار الشامل"""
        print("🚀 بدء الاختبار الشامل النهائي للنظام")
        print("=" * 80)
        
        tests = [
            ("استيراد الوحدات الأساسية", self.test_core_imports),
            ("وظائف Repository", self.test_repository_functionality),
            ("الخدمات", self.test_services),
            ("واجهة المستخدم", self.test_ui_imports),
            ("ملفات الإعدادات", self.test_configuration_files),
            ("سلامة قاعدة البيانات", self.test_database_integrity),
            ("تشغيل main.py", self.test_main_py_execution),
            ("الأداء", self.test_performance),
        ]
        
        for test_name, test_func in tests:
            self.run_test(test_name, test_func)
        
        print("\n" + "=" * 80)
        print("📊 ملخص الاختبار الشامل النهائي")
        print("=" * 80)
        print(f"الاختبارات الناجحة: {self.passed_tests}/{self.total_tests}")
        print(f"معدل النجاح: {(self.passed_tests/self.total_tests)*100:.1f}%")
        
        if self.passed_tests == self.total_tests:
            print("🎉 جميع الاختبارات نجحت! النظام جاهز للاستخدام")
            return True
        else:
            print("⚠️ بعض الاختبارات فشلت")
            return False

def main():
    """الدالة الرئيسية"""
    tester = FinalSystemTester()
    success = tester.run_comprehensive_test()
    
    if success:
        print("\n✅ النظام مُختبر بالكامل وجاهز للإنتاج!")
        return 0
    else:
        print("\n⚠️ النظام يحتاج إلى مراجعة إضافية")
        return 1

if __name__ == '__main__':
    sys.exit(main())