# الملف: tests/test_security.py
"""
اختبارات الأمان - Sky Wave ERP
"""

import os
import sys
import unittest
import hashlib

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPasswordSecurity(unittest.TestCase):
    """اختبارات أمان كلمات المرور"""

    def test_password_hashing(self):
        """اختبار تشفير كلمات المرور"""
        from core.auth_models import AuthService
        
        password = "TestPassword123!"
        hashed = AuthService.hash_password(password)
        
        # التأكد من أن الهاش يحتوي على salt
        self.assertIn(':', hashed)
        
        # التأكد من أن الهاش مختلف عن كلمة المرور
        self.assertNotEqual(password, hashed)

    def test_password_verification(self):
        """اختبار التحقق من كلمات المرور"""
        from core.auth_models import AuthService
        
        password = "TestPassword123!"
        hashed = AuthService.hash_password(password)
        
        # التحقق من كلمة المرور الصحيحة
        self.assertTrue(AuthService.verify_password(password, hashed))
        
        # التحقق من كلمة مرور خاطئة
        self.assertFalse(AuthService.verify_password("WrongPassword", hashed))

    def test_unique_salt_per_hash(self):
        """اختبار أن كل هاش له salt فريد"""
        from core.auth_models import AuthService
        
        password = "SamePassword123!"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)
        
        # التأكد من أن الهاشين مختلفين (بسبب salt مختلف)
        self.assertNotEqual(hash1, hash2)
        
        # لكن كلاهما يتحقق من نفس كلمة المرور
        self.assertTrue(AuthService.verify_password(password, hash1))
        self.assertTrue(AuthService.verify_password(password, hash2))


class TestFileSecurityPatterns(unittest.TestCase):
    """اختبارات أنماط الأمان في الملفات"""

    def setUp(self):
        """إعداد مسار المشروع"""
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_env_in_gitignore(self):
        """التأكد من أن .env في .gitignore"""
        gitignore_path = os.path.join(self.project_root, '.gitignore')
        
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn('.env', content)

    def test_db_files_in_gitignore(self):
        """التأكد من أن ملفات قاعدة البيانات في .gitignore"""
        gitignore_path = os.path.join(self.project_root, '.gitignore')
        
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn('*.db', content)

    def test_env_example_exists(self):
        """التأكد من وجود ملف .env.example"""
        env_example_path = os.path.join(self.project_root, '.env.example')
        self.assertTrue(os.path.exists(env_example_path))

    def test_env_example_has_no_real_credentials(self):
        """التأكد من أن .env.example لا يحتوي على بيانات حقيقية"""
        env_example_path = os.path.join(self.project_root, '.env.example')
        
        with open(env_example_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # التأكد من عدم وجود بيانات حقيقية
        self.assertNotIn('SkywavePassword', content)
        self.assertNotIn('147.79.66.116', content)
        self.assertNotIn('AIzaSy', content)


class TestUserRoles(unittest.TestCase):
    """اختبارات أدوار المستخدمين"""

    def test_user_roles_defined(self):
        """التأكد من تعريف أدوار المستخدمين"""
        from core.auth_models import UserRole
        
        self.assertTrue(hasattr(UserRole, 'ADMIN'))
        self.assertTrue(hasattr(UserRole, 'ACCOUNTANT'))
        self.assertTrue(hasattr(UserRole, 'SALES'))

    def test_permission_manager_exists(self):
        """التأكد من وجود مدير الصلاحيات"""
        from core.auth_models import PermissionManager
        
        self.assertTrue(hasattr(PermissionManager, 'can_access_tab'))
        self.assertTrue(hasattr(PermissionManager, 'can_perform_action'))
        self.assertTrue(hasattr(PermissionManager, 'has_feature'))


if __name__ == '__main__':
    unittest.main()
