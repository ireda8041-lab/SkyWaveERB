# الملف: core/safe_print.py
"""
دالة طباعة آمنة للتعامل مع مشاكل الترميز في Windows
"""

import re

# ⚡ التحكم في مستوى الطباعة للسرعة
# False = طباعة الأخطاء فقط (سريع)
# True = طباعة كل شيء (بطيء)
VERBOSE_MODE = False


def safe_print(msg: str) -> None:
    """
    طباعة آمنة تتعامل مع مشاكل الترميز في Windows Console.
    تزيل الـ emoji والحروف غير المدعومة إذا فشلت الطباعة.
    """
    # ⚡ تخطي رسائل INFO و DEBUG في الوضع السريع
    if not VERBOSE_MODE:
        if msg.startswith('INFO:') or msg.startswith('DEBUG:') or msg.startswith('DEBUG '):
            return
        # تخطي أي رسالة تحتوي على INFO: أو DEBUG: في أول 30 حرف
        first_part = msg[:30].upper()
        if 'INFO:' in first_part or 'DEBUG:' in first_part or 'INFO ' in first_part or 'DEBUG ' in first_part:
            return

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
__all__ = ['safe_print', 'VERBOSE_MODE']
