"""
Context Manager للـ Database Cursors
يضمن إغلاق الـ cursors بشكل صحيح
"""


class CursorContext:
    """Context manager لإدارة cursors بشكل آمن"""

    def __init__(self, repo):
        self.repo = repo
        self.cursor = None

    def __enter__(self):
        """فتح cursor جديد"""
        try:
            self.cursor = self.repo.get_cursor()
            return self.cursor
        except Exception as e:
            if self.cursor:
                try:
                    self.cursor.close()
                except Exception:
                    pass
            raise e

    def __exit__(self, exc_type, exc_val, exc_tb):
        """إغلاق الـ cursor تلقائياً"""
        if self.cursor:
            try:
                self.cursor.close()
            except Exception as e:
                # تسجيل الخطأ لكن لا نرفع استثناء
                try:
                    from core.logger import logger

                    logger.warning(f"فشل إغلاق cursor: {e}")
                except Exception:
                    pass  # تجاهل أخطاء الطباعة

        # لا نمنع انتشار الاستثناءات الأصلية
        return False


def get_cursor_context(repo):
    """دالة مساعدة لإنشاء cursor context"""
    return CursorContext(repo)


# مثال على الاستخدام:
# with get_cursor_context(self.repo) as cursor:
#     cursor.execute("SELECT * FROM clients")
#     results = cursor.fetchall()
# # يتم إغلاق الـ cursor تلقائياً
