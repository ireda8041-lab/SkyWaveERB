"""
🔒 اختبارات الأمان (Security Testing)
اختبار الحماية من الثغرات الشائعة
"""

import hashlib
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSQLInjection:
    """اختبارات الحماية من SQL Injection"""

    @pytest.fixture
    def test_db(self):
        """قاعدة بيانات للاختبار"""
        conn = sqlite3.connect(':memory:')
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                password TEXT
            )
        """)
        conn.execute("INSERT INTO users VALUES (1, 'admin', 'hashed_password')")
        conn.commit()
        yield conn
        conn.close()

    def test_parameterized_query_safe(self, test_db):
        """اختبار: الاستعلامات المعلمة آمنة"""
        # محاولة SQL Injection
        malicious_input = "' OR '1'='1"
        
        # الطريقة الآمنة (Parameterized Query)
        cursor = test_db.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ?",
            (malicious_input,)
        )
        result = cursor.fetchall()
        
        # يجب ألا يجد أي نتائج (الإدخال الخبيث لم ينجح)
        assert len(result) == 0, "❌ SQL Injection نجح! هذا خطير!"
        print("\n✅ الحماية من SQL Injection تعمل!")

    def test_escape_special_characters(self):
        """اختبار: تنظيف الأحرف الخاصة"""
        def sanitize_input(text):
            # إزالة الأحرف الخطيرة
            dangerous_chars = ["'", '"', ";", "--", "/*", "*/", "\\"]
            for char in dangerous_chars:
                text = text.replace(char, "")
            return text
        
        malicious = "Robert'; DROP TABLE users;--"
        clean = sanitize_input(malicious)
        
        assert ";" not in clean
        assert "--" not in clean
        assert "'" not in clean
        print("\n✅ تنظيف الأحرف الخاصة يعمل!")


class TestXSSPrevention:
    """اختبارات الحماية من XSS"""

    def test_html_escape(self):
        """اختبار: تنظيف HTML"""
        import html
        
        malicious_input = "<script>alert('XSS')</script>"
        safe_output = html.escape(malicious_input)
        
        assert "<script>" not in safe_output
        assert "&lt;script&gt;" in safe_output
        print("\n✅ الحماية من XSS تعمل!")

    def test_sanitize_user_input(self):
        """اختبار: تنظيف مدخلات المستخدم"""
        def sanitize_html(text):
            import html
            # تحويل الأحرف الخاصة
            text = html.escape(text)
            # إزالة أي محاولة لإدخال JavaScript
            text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
            text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
            return text
        
        tests = [
            ("<script>alert('xss')</script>", False),
            ("javascript:alert(1)", False),
            ("onclick=alert(1)", False),
            ("نص عادي بالعربي", True),
            ("Normal text 123", True)
        ]
        
        for input_text, should_contain_original in tests:
            result = sanitize_html(input_text)
            if not should_contain_original:
                assert input_text != result, f"❌ لم يتم تنظيف: {input_text}"
        
        print("\n✅ تنظيف مدخلات المستخدم يعمل!")


class TestPasswordSecurity:
    """اختبارات أمان كلمات المرور"""

    def test_password_hashing(self):
        """اختبار: تشفير كلمات المرور"""
        def hash_password(password, salt="skywave_salt"):
            return hashlib.sha256((password + salt).encode()).hexdigest()
        
        password = "MySecurePassword123"
        hashed = hash_password(password)
        
        # التحقق من أن الهاش ليس كلمة المرور الأصلية
        assert hashed != password
        # التحقق من طول الهاش (SHA256 = 64 حرف)
        assert len(hashed) == 64
        # التحقق من أن نفس كلمة المرور تعطي نفس الهاش
        assert hash_password(password) == hashed
        
        print("\n✅ تشفير كلمات المرور يعمل!")

    def test_password_strength(self):
        """اختبار: قوة كلمة المرور"""
        def check_password_strength(password):
            errors = []
            
            if len(password) < 8:
                errors.append("يجب أن تكون 8 أحرف على الأقل")
            if not re.search(r'[A-Z]', password):
                errors.append("يجب أن تحتوي على حرف كبير")
            if not re.search(r'[a-z]', password):
                errors.append("يجب أن تحتوي على حرف صغير")
            if not re.search(r'[0-9]', password):
                errors.append("يجب أن تحتوي على رقم")
            
            return {
                'is_strong': len(errors) == 0,
                'errors': errors
            }
        
        # كلمة مرور قوية
        result = check_password_strength("MyPassword123")
        assert result['is_strong'] == True
        
        # كلمة مرور ضعيفة
        result = check_password_strength("weak")
        assert result['is_strong'] == False
        assert len(result['errors']) > 0
        
        print("\n✅ فحص قوة كلمة المرور يعمل!")

    def test_no_plaintext_passwords(self):
        """اختبار: عدم تخزين كلمات المرور كنص عادي"""
        # محاكاة تخزين المستخدم
        def create_user(username, password):
            hashed = hashlib.sha256(password.encode()).hexdigest()
            return {
                'username': username,
                'password_hash': hashed
            }
        
        user = create_user("admin", "secret123")
        
        # التأكد من عدم وجود كلمة المرور الأصلية
        assert "secret123" not in str(user)
        assert user['password_hash'] != "secret123"
        
        print("\n✅ كلمات المرور لا تُخزن كنص عادي!")


class TestInputValidation:
    """اختبارات التحقق من المدخلات"""

    def test_file_path_traversal(self):
        """اختبار: الحماية من Path Traversal"""
        def safe_filename(filename):
            # إزالة أي محاولة للوصول لمجلدات أخرى
            filename = filename.replace("..", "")
            filename = filename.replace("/", "")
            filename = filename.replace("\\", "")
            # السماح فقط بأحرف آمنة
            filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '', filename)
            return filename
        
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/etc/shadow",
            "file.txt; rm -rf /"
        ]
        
        for path in malicious_paths:
            safe = safe_filename(path)
            assert ".." not in safe
            assert "/" not in safe
            assert "\\" not in safe
            assert ";" not in safe
        
        print("\n✅ الحماية من Path Traversal تعمل!")

    def test_numeric_input_validation(self):
        """اختبار: التحقق من المدخلات الرقمية"""
        def validate_numeric(value, min_val=None, max_val=None):
            try:
                num = float(value)
                if min_val is not None and num < min_val:
                    return False, f"القيمة أقل من {min_val}"
                if max_val is not None and num > max_val:
                    return False, f"القيمة أكبر من {max_val}"
                return True, num
            except (ValueError, TypeError):
                return False, "قيمة غير رقمية"
        
        # اختبارات صحيحة
        assert validate_numeric("100", min_val=0)[0] == True
        assert validate_numeric("50", min_val=0, max_val=100)[0] == True
        
        # اختبارات خاطئة
        assert validate_numeric("abc")[0] == False
        assert validate_numeric("-10", min_val=0)[0] == False
        assert validate_numeric("200", max_val=100)[0] == False
        
        print("\n✅ التحقق من المدخلات الرقمية يعمل!")


class TestSessionSecurity:
    """اختبارات أمان الجلسات"""

    def test_session_token_generation(self):
        """اختبار: توليد رموز الجلسات"""
        import secrets
        
        def generate_session_token():
            return secrets.token_hex(32)
        
        token1 = generate_session_token()
        token2 = generate_session_token()
        
        # التأكد من أن الرموز فريدة
        assert token1 != token2
        # التأكد من طول الرمز (64 حرف hex)
        assert len(token1) == 64
        # التأكد من أن الرمز يحتوي فقط على hex
        assert all(c in '0123456789abcdef' for c in token1)
        
        print("\n✅ توليد رموز الجلسات آمن!")

    def test_session_expiry(self):
        """اختبار: انتهاء صلاحية الجلسة"""
        from datetime import datetime, timedelta
        
        def create_session(user_id, expiry_hours=24):
            return {
                'user_id': user_id,
                'created_at': datetime.now(),
                'expires_at': datetime.now() + timedelta(hours=expiry_hours)
            }
        
        def is_session_valid(session):
            return datetime.now() < session['expires_at']
        
        # جلسة صالحة
        session = create_session("user1", expiry_hours=24)
        assert is_session_valid(session) == True
        
        # جلسة منتهية
        expired_session = {
            'user_id': 'user1',
            'created_at': datetime.now() - timedelta(hours=48),
            'expires_at': datetime.now() - timedelta(hours=24)
        }
        assert is_session_valid(expired_session) == False
        
        print("\n✅ التحقق من صلاحية الجلسة يعمل!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
