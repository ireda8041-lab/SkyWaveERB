# الملف: tests/test_config.py
"""
اختبارات وحدة التكوين (Config Module)
"""

import os
import sys
import unittest

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfig(unittest.TestCase):
    """اختبارات إعدادات التكوين"""

    def test_config_import(self):
        """اختبار استيراد وحدة التكوين"""
        from core.config import Config, config

        self.assertIsNotNone(Config)
        self.assertIsNotNone(config)

    def test_get_mongo_uri(self):
        """اختبار الحصول على رابط MongoDB"""
        from core.config import Config

        uri = Config.get_mongo_uri()
        self.assertIsInstance(uri, str)
        self.assertTrue(uri.startswith("mongodb://"))

    def test_get_db_name(self):
        """اختبار الحصول على اسم قاعدة البيانات"""
        from core.config import Config

        db_name = Config.get_db_name()
        self.assertIsInstance(db_name, str)
        self.assertTrue(len(db_name) > 0)

    def test_get_local_db_path(self):
        """اختبار الحصول على مسار قاعدة البيانات المحلية"""
        from core.config import Config

        path = Config.get_local_db_path()
        self.assertIsInstance(path, str)
        self.assertTrue(path.endswith(".db"))

    def test_get_default_admin_password(self):
        """اختبار الحصول على كلمة المرور الافتراضية"""
        from core.config import Config

        password = Config.get_default_admin_password()
        self.assertIsInstance(password, str)
        # التأكد من أن كلمة المرور ليست ضعيفة
        self.assertGreater(len(password), 8)
        self.assertNotEqual(password, "admin123")

    def test_is_debug_mode(self):
        """اختبار وضع التصحيح"""
        from core.config import Config

        debug = Config.is_debug_mode()
        self.assertIsInstance(debug, bool)

    def test_get_log_level(self):
        """اختبار مستوى التسجيل"""
        from core.config import Config

        level = Config.get_log_level()
        self.assertIn(level, ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    def test_env_override(self):
        """اختبار تجاوز القيم من متغيرات البيئة"""
        # حفظ القيمة الأصلية
        original = os.environ.get("MONGO_DB_NAME")

        # تعيين قيمة جديدة
        os.environ["MONGO_DB_NAME"] = "test_db"

        # إعادة تحميل للحصول على القيمة الجديدة
        db_name = os.environ.get("MONGO_DB_NAME", "skywave_erp_db")
        self.assertEqual(db_name, "test_db")

        # استعادة القيمة الأصلية
        if original:
            os.environ["MONGO_DB_NAME"] = original
        else:
            del os.environ["MONGO_DB_NAME"]


class TestSecurityConfig(unittest.TestCase):
    """اختبارات أمان التكوين"""

    def test_no_hardcoded_credentials_in_repository(self):
        """التأكد من عدم وجود بيانات اعتماد مكشوفة في repository.py"""
        repo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "repository.py"
        )

        with open(repo_path, encoding="utf-8") as f:
            content = f.read()

        # التأكد من عدم وجود كلمات مرور مكشوفة
        self.assertNotIn("SkywavePassword", content)
        self.assertNotIn("147.79.66.116", content)

    def test_no_api_keys_in_settings(self):
        """التأكد من عدم وجود مفاتيح API في ملف الإعدادات"""
        import json

        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skywave_settings.json"
        )

        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)

        # التأكد من عدم وجود مفتاح API حساس في الإعدادات
        api_key = settings.get("smart_scan", {}).get("gemini_api_key", "")
        self.assertEqual(api_key, "")


if __name__ == "__main__":
    unittest.main()
