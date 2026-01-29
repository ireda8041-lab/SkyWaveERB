#!/usr/bin/env python3
"""
سكريبت لإصلاح كل الإشارات في repository.py
يضيف QTimer.singleShot و logging واضح
"""

import re

# قراءة الملف
with open('core/repository.py', 'r', encoding='utf-8') as f:
    content = f.read()

# النمط القديم
old_pattern = r'(\s+)# 💥 إرسال إشارة التغيير للمزامنة الفورية\s+self\.data_changed_signal\.emit\("(\w+)"\)'

# النمط الجديد
new_pattern = r'''\1# 💥 إرسال إشارة التغيير للمزامنة الفورية (في الـ main thread)
\1try:
\1    from PyQt6.QtCore import QTimer
\1    safe_print(f"🔥 [Repository] إرسال إشارة تحديث: \2")
\1    QTimer.singleShot(0, lambda: self.data_changed_signal.emit("\2"))
\1except Exception as e:
\1    safe_print(f"⚠️ [Repository] Fallback signal: \2 ({e})")
\1    self.data_changed_signal.emit("\2")'''

# استبدال
new_content = re.sub(old_pattern, new_pattern, content)

# حفظ
with open('core/repository.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ تم تعديل كل الإشارات في repository.py")
print(f"عدد التعديلات: {content.count('# 💥 إرسال إشارة التغيير للمزامنة الفورية')}")
