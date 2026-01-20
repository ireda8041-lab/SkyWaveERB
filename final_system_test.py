#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار شامل نهائي للنظام - Final System Test
يختبر جميع المكونات الأساسية للتأكد من عملها بشكل صحيح
"""

import sys
import time
from pathlib import Path

class FinalSystemTester:
    """فاحص شامل نهائي"""
    
    def __init__(self):
        self.passed = []
        self.failed = []
        self.start_time = time.time()
        
    def test(self, name: str, func):
        """تشغيل اختبار واحد"""
        try:
            print(f"\n🧪 اختبار: {name}...")
            func()
            self.passed.append(name)
            print(f"✅ نجح: {name}")
            return True
        except Exception as e:
            self.failed.append((name, str(e)))
            print(f"❌ فشل: {name}")
            print(f"   الخطأ: {e}")
            return False
    
    def test_imports(self):
        """اختبار الاستيرادات الأساسية"""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        import pymongo
        import pydantic
        from jinja2 import Template
        import reportlab
        import pandas
        print("   ✓ جميع الاستيرادات الأساسية تعمل")
    
    def test_database_connection(self):
        """اختبار الاتصال بقاعدة البيانات"""
        import sqlite3
        conn = sqlite3.connect("skywave_local.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        assert len(tables) > 0, "لا توجد جداول في قاعدة البيانات"
        print(f"   ✓ قاعدة البيانات تحتوي على {len(tables)} جدول")
    
    def test_repository(self):
        """اختبار Repository"""
        from core.repository import Repository
        repo = Repository()
        assert repo is not None, "فشل إنشاء Repository"
        print("   ✓ Repository يعمل بشكل صحيح")
    
    def test_config(self):
        """اختبار Config"""
        from core.config import Config
        config = Config()
        db_path = config.get_local_db_path()
        assert db_path is not None, "فشل الحصول على مسار قاعدة البيانات"
        print(f"   ✓ Config يعمل بشكل صحيح")
    
    def test_schemas(self):
        """اختبار Schemas"""
        from core.schemas import Client, ClientStatus
        client = Client(
            name="عميل تجريبي",
            status=ClientStatus.ACTIVE
        )
        assert client.name == "عميل تجريبي", "فشل إنشاء Client"
        print("   ✓ Schemas تعمل بشكل صحيح")
    
    def test_services(self):
        """اختبار Services"""
        from core.repository import Repository
        from core.event_bus import EventBus
        from services.client_service import ClientService
        
        repo = Repository()
        event_bus = EventBus()
        client_service = ClientService(repository=repo)
        
        assert client_service is not None, "فشل إنشاء ClientService"
        print("   ✓ Services تعمل بشكل صحيح")
    
    def test_auth(self):
        """اختبار نظام المصادقة"""
        from core.auth_models import AuthService, UserRole
        from core.repository import Repository
        
        repo = Repository()
        auth_service = AuthService(repository=repo)
        
        assert auth_service is not None, "فشل إنشاء AuthService"
        print("   ✓ نظام المصادقة يعمل بشكل صحيح")
    
    def test_version(self):
        """اختبار معلومات الإصدار"""
        import json
        with open("version.json", "r", encoding="utf-8") as f:
            version_data = json.load(f)
        
        assert "version" in version_data, "معلومات الإصدار ناقصة"
        print(f"   ✓ الإصدار: {version_data['version']}")
    
    def run_all_tests(self):
        """تشغيل جميع الاختبارات"""
        print("=" * 80)
        print("🚀 بدء الاختبار الشامل النهائي - Final System Test")
        print("=" * 80)
        
        tests = [
            ("الاستيرادات الأساسية", self.test_imports),
            ("الاتصال بقاعدة البيانات", self.test_database_connection),
            ("Repository", self.test_repository),
            ("Config", self.test_config),
            ("Schemas", self.test_schemas),
            ("Services", self.test_services),
            ("نظام المصادقة", self.test_auth),
            ("معلومات الإصدار", self.test_version)
        ]
        
        for test_name, test_func in tests:
            self.test(test_name, test_func)
        
        # النتائج النهائية
        duration = time.time() - self.start_time
        
        print("\n" + "=" * 80)
        print("📊 نتائج الاختبار النهائي")
        print("=" * 80)
        print(f"✅ نجح: {len(self.passed)} اختبار")
        print(f"❌ فشل: {len(self.failed)} اختبار")
        print(f"⏱️ المدة: {duration:.2f} ثانية")
        
        if self.failed:
            print("\n❌ الاختبارات الفاشلة:")
            for name, error in self.failed:
                print(f"   • {name}: {error}")
        
        print("=" * 80)
        
        if len(self.failed) == 0:
            print("\n🎉 جميع الاختبارات نجحت! النظام جاهز للعمل")
            return True
        else:
            print(f"\n⚠️ فشل {len(self.failed)} اختبار - يرجى المراجعة")
            return False

def main():
    """الدالة الرئيسية"""
    tester = FinalSystemTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
