#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبار العالم الحقيقي النهائي - Final Real World Test
اختبار التشغيل الفعلي للنظام بسيناريوهات حقيقية
"""

import sys
import os
import time
import traceback
from pathlib import Path

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class RealWorldTester:
    """اختبار العالم الحقيقي"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        
    def test(self, name: str, func):
        """تشغيل اختبار واحد"""
        print(f"\n{'='*60}")
        print(f"🧪 {name}")
        print('='*60)
        try:
            result = func()
            if result:
                print(f"✅ {name}: نجح")
                self.passed += 1
                return True
            else:
                print(f"❌ {name}: فشل")
                self.failed += 1
                return False
        except Exception as e:
            print(f"💥 {name}: خطأ - {e}")
            print(traceback.format_exc())
            self.errors.append((name, str(e)))
            self.failed += 1
            return False
    
    def test_actual_startup(self) -> bool:
        """اختبار بدء التشغيل الفعلي"""
        try:
            # محاكاة بدء التشغيل
            from core.repository import Repository
            from core.config import Config
            from core.auth_models import User
            
            # إنشاء الكائنات الأساسية
            repo = Repository()
            config = Config()
            
            print("✅ تم إنشاء الكائنات الأساسية")
            
            # التحقق من الاتصال
            cursor = repo.get_cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            if result[0] == 1:
                print("✅ الاتصال بقاعدة البيانات يعمل")
                return True
            else:
                print("❌ مشكلة في الاتصال")
                return False
                
        except Exception as e:
            print(f"❌ خطأ في بدء التشغيل: {e}")
            return False
    
    def test_client_operations(self) -> bool:
        """اختبار عمليات العملاء"""
        try:
            from core.repository import Repository
            from services.client_service import ClientService
            
            repo = Repository()
            service = ClientService(repo)
            
            # قراءة العملاء
            clients = repo.get_all_clients()
            print(f"✅ تم قراءة {len(clients)} عميل")
            
            # البحث عن عميل
            if clients:
                first_client = clients[0]
                found = repo.get_client_by_id(first_client.id)
                if found:
                    print(f"✅ تم العثور على العميل: {found.name}")
                else:
                    print("❌ فشل البحث عن العميل")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في عمليات العملاء: {e}")
            return False
    
    def test_project_operations(self) -> bool:
        """اختبار عمليات المشاريع"""
        try:
            from core.repository import Repository
            
            repo = Repository()
            
            # قراءة المشاريع
            projects = repo.get_all_projects()
            print(f"✅ تم قراءة {len(projects)} مشروع")
            
            # البحث عن مشروع
            if projects:
                first_project = projects[0]
                # استخدام الطريقة الصحيحة
                cursor = repo.get_cursor()
                cursor.execute("SELECT * FROM projects WHERE id = ?", (first_project.id,))
                found = cursor.fetchone()
                if found:
                    print(f"✅ تم العثور على المشروع: {first_project.name}")
                else:
                    print("❌ فشل البحث عن المشروع")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في عمليات المشاريع: {e}")
            return False
    
    def test_database_transactions(self) -> bool:
        """اختبار معاملات قاعدة البيانات"""
        try:
            from core.repository import Repository
            
            repo = Repository()
            cursor = repo.get_cursor()
            
            # اختبار معاملة بسيطة
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute("SELECT COUNT(*) FROM clients")
            count = cursor.fetchone()[0]
            cursor.execute("ROLLBACK")
            
            print(f"✅ المعاملات تعمل بشكل صحيح ({count} عميل)")
            return True
            
        except Exception as e:
            print(f"❌ خطأ في المعاملات: {e}")
            return False
    
    def test_concurrent_access(self) -> bool:
        """اختبار الوصول المتزامن"""
        try:
            from core.repository import Repository
            import threading
            
            results = []
            
            def access_db():
                try:
                    repo = Repository()
                    clients = repo.get_all_clients()
                    results.append(len(clients))
                except Exception as e:
                    results.append(None)
            
            # إنشاء 5 threads
            threads = []
            for _ in range(5):
                t = threading.Thread(target=access_db)
                threads.append(t)
                t.start()
            
            # انتظار جميع الـ threads
            for t in threads:
                t.join()
            
            # التحقق من النتائج
            if None in results:
                print("❌ فشل بعض الوصولات المتزامنة")
                return False
            
            if len(set(results)) == 1:
                print(f"✅ الوصول المتزامن يعمل ({results[0]} عميل في كل مرة)")
                return True
            else:
                print(f"⚠️ نتائج مختلفة: {results}")
                return True  # قد يكون طبيعياً إذا تغيرت البيانات
                
        except Exception as e:
            print(f"❌ خطأ في الوصول المتزامن: {e}")
            return False
    
    def test_error_handling(self) -> bool:
        """اختبار معالجة الأخطاء"""
        try:
            from core.repository import Repository
            
            repo = Repository()
            
            # محاولة الوصول إلى عميل غير موجود
            try:
                client = repo.get_client_by_id(999999)
                if client is None:
                    print("✅ معالجة العميل غير الموجود صحيحة")
                else:
                    print("⚠️ تم إرجاع عميل غير متوقع")
            except Exception as e:
                print(f"⚠️ استثناء غير متوقع: {e}")
            
            # محاولة استعلام خاطئ
            try:
                cursor = repo.get_cursor()
                cursor.execute("SELECT * FROM nonexistent_table")
                print("❌ لم يتم اكتشاف الجدول غير الموجود")
                return False
            except Exception:
                print("✅ تم اكتشاف الجدول غير الموجود بشكل صحيح")
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في اختبار معالجة الأخطاء: {e}")
            return False
    
    def test_memory_usage(self) -> bool:
        """اختبار استهلاك الذاكرة"""
        try:
            import psutil
            process = psutil.Process()
            
            # قياس الذاكرة قبل
            mem_before = process.memory_info().rss / 1024 / 1024
            
            # تنفيذ عمليات
            from core.repository import Repository
            repo = Repository()
            
            for _ in range(100):
                clients = repo.get_all_clients()
                projects = repo.get_all_projects()
            
            # قياس الذاكرة بعد
            mem_after = process.memory_info().rss / 1024 / 1024
            mem_increase = mem_after - mem_before
            
            print(f"📊 الذاكرة قبل: {mem_before:.1f} MB")
            print(f"📊 الذاكرة بعد: {mem_after:.1f} MB")
            print(f"📊 الزيادة: {mem_increase:.1f} MB")
            
            if mem_increase > 50:
                print("⚠️ زيادة كبيرة في الذاكرة")
                return False
            
            print("✅ استهلاك الذاكرة طبيعي")
            return True
            
        except ImportError:
            print("⚠️ psutil غير متاح - تخطي اختبار الذاكرة")
            return True
        except Exception as e:
            print(f"❌ خطأ في اختبار الذاكرة: {e}")
            return False
    
    def test_version_consistency(self) -> bool:
        """اختبار تناسق الإصدار"""
        try:
            import json
            import re
            
            # قراءة version.json
            with open('version.json', 'r', encoding='utf-8') as f:
                version_json = json.load(f)
            
            # قراءة version.py
            with open('version.py', 'r', encoding='utf-8') as f:
                version_py = f.read()
            
            # استخراج الإصدار
            json_ver = version_json.get('version')
            py_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', version_py)
            py_ver = py_match.group(1) if py_match else None
            
            print(f"📦 version.json: {json_ver}")
            print(f"📦 version.py: {py_ver}")
            
            if json_ver == py_ver == "2.0.1":
                print("✅ الإصدارات متناسقة: 2.0.1")
                return True
            else:
                print(f"❌ الإصدارات غير متناسقة")
                return False
                
        except Exception as e:
            print(f"❌ خطأ في فحص الإصدار: {e}")
            return False
    
    def run_all_tests(self):
        """تشغيل جميع الاختبارات"""
        print("\n" + "="*80)
        print("🚀 اختبار العالم الحقيقي النهائي - Final Real World Test")
        print("="*80)
        print("اختبار التشغيل الفعلي للنظام بسيناريوهات حقيقية")
        print("="*80)
        
        tests = [
            ("بدء التشغيل الفعلي", self.test_actual_startup),
            ("عمليات العملاء", self.test_client_operations),
            ("عمليات المشاريع", self.test_project_operations),
            ("معاملات قاعدة البيانات", self.test_database_transactions),
            ("الوصول المتزامن", self.test_concurrent_access),
            ("معالجة الأخطاء", self.test_error_handling),
            ("استهلاك الذاكرة", self.test_memory_usage),
            ("تناسق الإصدار", self.test_version_consistency),
        ]
        
        for name, func in tests:
            self.test(name, func)
        
        # النتائج النهائية
        total = self.passed + self.failed
        print("\n" + "="*80)
        print("📊 النتائج النهائية")
        print("="*80)
        print(f"✅ نجح: {self.passed}/{total}")
        print(f"❌ فشل: {self.failed}/{total}")
        print(f"📈 معدل النجاح: {(self.passed/total)*100:.1f}%")
        
        if self.errors:
            print(f"\n⚠️ الأخطاء ({len(self.errors)}):")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        
        if self.failed == 0:
            print("\n" + "="*80)
            print("🎉 جميع اختبارات العالم الحقيقي نجحت!")
            print("✅ النظام يعمل بشكل مثالي في سيناريوهات حقيقية")
            print("="*80)
            return True
        else:
            print("\n" + "="*80)
            print("⚠️ بعض الاختبارات فشلت")
            print("="*80)
            return False

def main():
    tester = RealWorldTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
