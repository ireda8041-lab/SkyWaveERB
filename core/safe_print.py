# الملف: core/safe_print.py
"""
دالة طباعة آمنة للتعامل مع مشاكل الترميز في Windows
"""

import re
import sys


def safe_print(msg: str) -> None:
    """
    طباعة آمنة تتعامل مع مشاكل الترميز في Windows Console.
    تزيل الـ emoji والحروف غير المدعومة إذا فشلت الطباعة.
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        # إزالة الـ emoji والحروف الخاصة، الاحتفاظ بالعربي والإنجليزي
        clean_msg = re.sub(r'[^\x00-\x7F\u0600-\u06FF\s\.\,\:\;\-\_\(\)\[\]\{\}]+', '', msg)
        try:
            print(clean_msg)
        except Exception:
            pass  # تجاهل أي خطأ في الطباعة


# تصدير الدالة للاستخدام المباشر
__all__ = ['safe_print']
