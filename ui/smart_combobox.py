# الملف: ui/smart_combobox.py
"""
SmartFilterComboBox - ComboBox مع فلترة تلقائية
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QComboBox


class SmartFilterComboBox(QComboBox):
    """
    ComboBox مع فلترة تلقائية عند الكتابة
    - عند الضغط: يحدد النص تلقائياً
    - عند الكتابة: تظهر قائمة منسدلة بالعناصر المطابقة
    - الكتابة تستمر بدون توقف
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(15)

        # ⚡ إعدادات لضمان عرض المحتوى بشكل صحيح
        self.setMinimumWidth(150)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

        self._all_items = []
        self._is_filtering = False
        self._popup_visible = False
        self._pending_focus_restore: tuple[str, int] | None = None

        # تايمر للفلترة المتأخرة
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(200)  # انتظر 200ms بعد آخر حرف
        self._filter_timer.timeout.connect(self._do_filter)

        # مؤقتات مملوكة للمكون نفسه لتفادي أي callbacks متأخرة بعد الإخفاء أو التدمير
        self._focus_restore_timer = QTimer(self)
        self._focus_restore_timer.setSingleShot(True)
        self._focus_restore_timer.timeout.connect(self._apply_pending_focus_restore)

        self._restore_items_timer = QTimer(self)
        self._restore_items_timer.setSingleShot(True)
        self._restore_items_timer.setInterval(50)
        self._restore_items_timer.timeout.connect(self._restore_all_items)

        self._select_all_timer = QTimer(self)
        self._select_all_timer.setSingleShot(True)
        self._select_all_timer.timeout.connect(self._select_all_text)

        # ربط تغيير النص
        self.lineEdit().textEdited.connect(self._on_text_edited)

        # ⚡ إعدادات الـ LineEdit الداخلي - محاذاة لليمين للعربية
        if self.lineEdit():
            self.lineEdit().setMinimumWidth(100)
            self.lineEdit().setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

        # إزالة الـ Completer الافتراضي
        self.setCompleter(None)

    def addItem(self, text: str, userData=None):
        """إضافة عنصر مع حفظه في القائمة الأصلية"""
        self._all_items.append((text, userData))
        super().addItem(text, userData)

    def addItems(self, texts):
        """إضافة عناصر متعددة"""
        for text in texts:
            self._all_items.append((text, None))
            super().addItem(text)

    def clear(self):
        """مسح كل العناصر"""
        self._all_items.clear()
        super().clear()

    def _on_text_edited(self, text: str):
        """عند تغيير النص بواسطة المستخدم"""
        if self._is_filtering:
            return
        # أعد تشغيل التايمر مع كل حرف
        self._filter_timer.start()

    def _do_filter(self):
        """تنفيذ الفلترة بعد توقف الكتابة"""
        if self._is_filtering:
            return

        self._is_filtering = True

        text = self.lineEdit().text()
        search = text.lower().strip()
        cursor_pos = self.lineEdit().cursorPosition()

        # مسح وإعادة بناء القائمة
        super().clear()

        matched_count = 0
        if search:
            for t, d in self._all_items:
                if search in t.lower():
                    super().addItem(t, d)
                    matched_count += 1
        else:
            for t, d in self._all_items:
                super().addItem(t, d)
                matched_count += 1

        # إعادة النص وموضع المؤشر
        self.lineEdit().setText(text)
        self.lineEdit().setCursorPosition(cursor_pos)

        self._is_filtering = False

        # فتح القائمة إذا كان هناك نتائج ونص للبحث
        if matched_count > 0 and search:
            self._show_popup_safe()

    def _show_popup_safe(self):
        """فتح القائمة بدون سرقة التركيز"""
        if self._popup_visible:
            return

        # حفظ النص والموضع قبل فتح القائمة
        text = self.lineEdit().text()
        cursor_pos = self.lineEdit().cursorPosition()

        # فتح القائمة
        self._popup_visible = True
        super().showPopup()

        # إعادة التركيز للـ LineEdit فوراً
        self._pending_focus_restore = (text, cursor_pos)
        self._focus_restore_timer.start(0)

    def _apply_pending_focus_restore(self):
        if self._pending_focus_restore is None:
            return
        text, cursor_pos = self._pending_focus_restore
        self._pending_focus_restore = None
        self._restore_focus(text, cursor_pos)

    def _restore_focus(self, text: str, cursor_pos: int):
        """إعادة التركيز والنص للـ LineEdit"""
        line_edit = self.lineEdit()
        if line_edit is None or not self.isVisible():
            return
        line_edit.setFocus()
        line_edit.setText(text)
        line_edit.setCursorPosition(cursor_pos)

    def hidePopup(self):
        """عند إغلاق القائمة"""
        self._popup_visible = False
        super().hidePopup()

        # استعادة كل العناصر بعد الإغلاق
        self._restore_items_timer.start()

    def _restore_all_items(self):
        """استعادة كل العناصر الأصلية"""
        if self._is_filtering:
            return

        self._is_filtering = True

        current_text = self.currentText()

        super().clear()
        for t, d in self._all_items:
            super().addItem(t, d)

        # محاولة إيجاد العنصر المحدد
        idx = self.findText(current_text)
        if idx >= 0:
            self.setCurrentIndex(idx)
        else:
            self.setEditText(current_text)

        self._is_filtering = False

    def focusInEvent(self, event):
        """عند الحصول على التركيز - حدد كل النص"""
        super().focusInEvent(event)
        self._schedule_select_all()

    def _select_all_text(self):
        """تحديد كل النص"""
        line_edit = self.lineEdit()
        if line_edit and self.isVisible():
            line_edit.selectAll()

    def _schedule_select_all(self):
        self._select_all_timer.start(0)

    def shutdown(self):
        """تنظيف أي حالة مؤجلة قبل إخفاء/إغلاق النافذة المالكة."""
        self._popup_visible = False
        self._pending_focus_restore = None
        self._filter_timer.stop()
        self._focus_restore_timer.stop()
        self._restore_items_timer.stop()
        self._select_all_timer.stop()
        try:
            view = self.view()
            if view is not None and view.isVisible():
                super().hidePopup()
        except RuntimeError:
            return
        line_edit = self.lineEdit()
        if line_edit:
            line_edit.clearFocus()
        self.clearFocus()

    def hideEvent(self, event):
        """إيقاف أي مؤقتات مؤجلة عند إخفاء الـ combo أو تدميره مع النافذة."""
        self.shutdown()
        super().hideEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """عند الضغط بالماوس"""
        line_edit = self.lineEdit()
        if line_edit:
            # تحقق إذا الضغط على منطقة النص وليس السهم
            arrow_width = 25  # عرض تقريبي لزر السهم
            text_area_width = self.width() - arrow_width

            # في RTL، السهم على اليسار
            if self.layoutDirection() == Qt.LayoutDirection.RightToLeft:
                is_text_area = event.pos().x() > arrow_width
            else:
                is_text_area = event.pos().x() < text_area_width

            if is_text_area:
                super().mousePressEvent(event)
                self._schedule_select_all()
                return

        super().mousePressEvent(event)


# للتوافق مع الكود القديم
FilterComboBox = SmartFilterComboBox
