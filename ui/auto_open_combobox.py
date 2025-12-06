# الملف: ui/auto_open_combobox.py
# ComboBox احترافي مع بحث ذكي

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QComboBox, QCompleter


class SimpleComboBox(QComboBox):
    """
    ComboBox احترافي مع:
    - كتابة حرة
    - بحث ذكي أثناء الكتابة
    - تحديد النص عند التركيز
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(15)

        # Timer للتأخير
        self._select_timer = QTimer()
        self._select_timer.setSingleShot(True)
        self._select_timer.timeout.connect(self._do_select_all)

        # علامة لمعرفة إذا كان أول مرة
        self._first_focus = True

    def _do_select_all(self):
        """تحديد كل النص"""
        if self.lineEdit() and self._first_focus:
            self.lineEdit().selectAll()
            self._first_focus = False

    def setup_completer(self, items_list):
        """إعداد البحث الذكي"""
        if not items_list:
            return

        # إنشاء completer احترافي
        completer = QCompleter(items_list, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)  # بحث في أي مكان في النص
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(10)

        # ربط الـ completer بالـ ComboBox
        self.setCompleter(completer)

    def showPopup(self):
        """فتح القائمة"""
        super().showPopup()

    def mousePressEvent(self, event):
        """عند الضغط بالماوس"""
        self._first_focus = True
        super().mousePressEvent(event)
        # تأخير بسيط عشان الـ selectAll يشتغل
        self._select_timer.start(10)
        self.showPopup()

    def focusInEvent(self, event):
        """عند التركيز"""
        self._first_focus = True
        super().focusInEvent(event)
        # تأخير بسيط عشان الـ selectAll يشتغل
        self._select_timer.start(10)

    def keyPressEvent(self, event):
        """عند الكتابة"""
        # بعد أول حرف، لا نحدد النص
        if event.text():
            self._first_focus = False
        super().keyPressEvent(event)
