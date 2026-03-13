# الملف: core/keyboard_shortcuts.py

"""
مدير اختصارات لوحة المفاتيح
يوفر اختصارات سريعة لتحسين الإنتاجية
"""


from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QAbstractSpinBox, QApplication, QLineEdit, QPlainTextEdit, QTextEdit

from core.logger import get_logger

logger = get_logger(__name__)


class KeyboardShortcutManager(QObject):
    """
    مدير اختصارات لوحة المفاتيح
    - تعريف الاختصارات
    - ربط الاختصارات بالإجراءات
    - إدارة الاختصارات المخصصة
    """

    # إشارات للاختصارات
    new_project = pyqtSignal()
    new_client = pyqtSignal()
    new_expense = pyqtSignal()
    new_payment = pyqtSignal()
    search_activated = pyqtSignal()
    refresh_data = pyqtSignal()
    save_data = pyqtSignal()
    close_dialog = pyqtSignal()
    show_help = pyqtSignal()
    full_sync = pyqtSignal()
    delete_selected = pyqtSignal()
    select_all = pyqtSignal()
    copy_selected = pyqtSignal()
    export_excel = pyqtSignal()
    print_current = pyqtSignal()
    _TEXT_SELECTION_SHORTCUTS = {"copy_selected", "select_all"}
    _TEXT_EDITING_DELETE_SHORTCUTS = {"delete_selected"}
    _MODAL_SAFE_SHORTCUTS = {
        "search",
        "refresh",
        "save",
        "close",
        "help",
        "delete_selected",
        "select_all",
        "copy_selected",
        "export_excel",
        "print_current",
    }

    def __init__(self, main_window):
        """
        تهيئة مدير الاختصارات

        Args:
            main_window: النافذة الرئيسية للتطبيق
        """
        super().__init__()
        self.main_window = main_window
        self.shortcuts: dict[str, QShortcut] = {}
        self._sequence_map: dict[str, QKeySequence] = {}

        # تعريف الاختصارات
        self.shortcut_definitions = {
            # اختصارات الإنشاء
            "new_project": {
                "key": "Ctrl+N",
                "description": "مشروع جديد",
                "signal": self.new_project,
            },
            "new_client": {
                "key": "Ctrl+Shift+N",
                "description": "عميل جديد",
                "signal": self.new_client,
            },
            "new_expense": {
                "key": "Ctrl+E",
                "description": "مصروف جديد",
                "signal": self.new_expense,
            },
            # اختصارات التنقل والبحث
            "search": {
                "key": "Ctrl+F",
                "description": "تفعيل البحث",
                "signal": self.search_activated,
            },
            "refresh": {"key": "F5", "description": "تحديث البيانات", "signal": self.refresh_data},
            # اختصارات الحفظ والإغلاق
            "save": {"key": "Ctrl+S", "description": "حفظ", "signal": self.save_data},
            "close": {"key": "Esc", "description": "إغلاق النافذة", "signal": self.close_dialog},
            # اختصارات المساعدة
            "help": {"key": "F1", "description": "عرض المساعدة", "signal": self.show_help},
            # اختصارات التابات
            "tab_dashboard": {
                "key": "Ctrl+1",
                "description": "الانتقال إلى الداشبورد",
                "action": lambda: self._switch_tab(0),
            },
            "tab_projects": {
                "key": "Ctrl+2",
                "description": "الانتقال إلى المشاريع",
                "action": lambda: self._switch_tab(1),
            },
            "tab_expenses": {
                "key": "Ctrl+3",
                "description": "الانتقال إلى المصروفات",
                "action": lambda: self._switch_tab(2),
            },
            "tab_clients": {
                "key": "Ctrl+4",
                "description": "الانتقال إلى العملاء",
                "action": lambda: self._switch_tab(4),
            },
            "tab_services": {
                "key": "Ctrl+5",
                "description": "الانتقال إلى الخدمات",
                "action": lambda: self._switch_tab(5),
            },
            "tab_accounting": {
                "key": "Ctrl+6",
                "description": "الانتقال إلى المحاسبة",
                "action": lambda: self._switch_tab(6),
            },
            "tab_settings": {
                "key": "Ctrl+7",
                "description": "الانتقال إلى الإعدادات",
                "action": lambda: self._switch_tab(8),
            },
            # اختصارات إضافية
            "new_payment": {
                "key": "Ctrl+P",
                "description": "دفعة جديدة",
                "signal": self.new_payment,
            },
            "full_sync": {
                "key": "Ctrl+Shift+S",
                "description": "مزامنة كاملة",
                "signal": self.full_sync,
            },
            "delete_selected": {
                "key": "Delete",
                "description": "حذف العنصر المحدد",
                "signal": self.delete_selected,
            },
            "select_all": {"key": "Ctrl+A", "description": "تحديد الكل", "signal": self.select_all},
            "copy_selected": {
                "key": "Ctrl+C",
                "description": "نسخ المحدد",
                "signal": self.copy_selected,
            },
            "export_excel": {
                "key": "Ctrl+Shift+E",
                "description": "تصدير Excel",
                "signal": self.export_excel,
            },
            "print_current": {
                "key": "Ctrl+Shift+P",
                "description": "طباعة",
                "signal": self.print_current,
            },
        }

        logger.info("تم تهيئة KeyboardShortcutManager")

    def setup_shortcuts(self):
        """إعداد جميع الاختصارات"""
        for name, definition in self.shortcut_definitions.items():
            self._create_shortcut(name, definition)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        logger.info("تم إعداد %s اختصار", len(self.shortcuts))

    def _create_shortcut(self, name: str, definition: dict):
        """
        ⚡ إنشاء اختصار واحد بشكل احترافي

        Args:
            name: اسم الاختصار
            definition: تعريف الاختصار
        """
        try:
            shortcut = QShortcut(QKeySequence(definition["key"]), self.main_window)
            self._sequence_map[name] = QKeySequence(definition["key"])

            # ⚡ تفعيل الاختصار دائماً
            shortcut.setEnabled(True)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.setAutoRepeat(False)  # منع التكرار التلقائي

            shortcut.activated.connect(
                lambda _checked=False, shortcut_name=name: self._dispatch_shortcut(shortcut_name)
            )

            self.shortcuts[name] = shortcut
            logger.debug("تم إنشاء اختصار: %s (%s)", name, definition["key"])

        except Exception as e:
            logger.error("فشل إنشاء اختصار %s: %s", name, e)

    @staticmethod
    def _is_text_selection_widget(widget) -> bool:
        if widget is None:
            return False
        return isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit))

    @staticmethod
    def _is_text_editable_widget(widget) -> bool:
        if widget is None:
            return False
        if isinstance(widget, QLineEdit):
            return not widget.isReadOnly()
        if isinstance(widget, (QTextEdit, QPlainTextEdit)):
            return not widget.isReadOnly()
        if isinstance(widget, QAbstractSpinBox):
            line_edit = widget.lineEdit()
            return bool(line_edit and not line_edit.isReadOnly())
        return False

    def _should_bypass_shortcut(self, shortcut_name: str | None) -> bool:
        if not shortcut_name:
            return False

        active_window = QApplication.activeWindow()
        if active_window is not None and active_window is not self.main_window:
            return True

        focus_widget = QApplication.focusWidget()
        focus_window = focus_widget.window() if focus_widget is not None else None
        if focus_window is not None and focus_window is not self.main_window:
            return True

        active_modal = QApplication.activeModalWidget()
        if (
            active_modal is not None
            and active_modal is not self.main_window
            and shortcut_name not in self._MODAL_SAFE_SHORTCUTS
        ):
            return True

        if shortcut_name in self._TEXT_SELECTION_SHORTCUTS and self._is_text_selection_widget(
            focus_widget
        ):
            return True
        if shortcut_name in self._TEXT_EDITING_DELETE_SHORTCUTS and self._is_text_editable_widget(
            focus_widget
        ):
            return True
        return False

    def _dispatch_shortcut(self, shortcut_name: str) -> bool:
        definition = self.shortcut_definitions.get(shortcut_name)
        if not definition or self._should_bypass_shortcut(shortcut_name):
            return False

        if "signal" in definition:
            QTimer.singleShot(0, definition["signal"].emit)
            return True
        if "action" in definition:
            QTimer.singleShot(0, definition["action"])
            return True
        return False

    def _switch_tab(self, index: int):
        """
        التبديل إلى تاب معين

        Args:
            index: رقم التاب
        """
        try:
            if hasattr(self.main_window, "tabs"):
                if index < self.main_window.tabs.count():
                    self.main_window.tabs.setCurrentIndex(index)
                    logger.debug("تم التبديل إلى التاب %s", index)
        except Exception as e:
            logger.error("فشل التبديل إلى التاب %s: %s", index, e)

    def get_all_shortcuts(self) -> dict[str, dict]:
        """
        الحصول على جميع الاختصارات

        Returns:
            قاموس بجميع الاختصارات وتعريفاتها
        """
        return dict(self.shortcut_definitions)

    def get_shortcut_by_name(self, name: str) -> QShortcut | None:
        """
        الحصول على اختصار بالاسم

        Args:
            name: اسم الاختصار

        Returns:
            كائن QShortcut أو None
        """
        return self.shortcuts.get(name)

    def enable_shortcut(self, name: str):
        """
        تفعيل اختصار

        Args:
            name: اسم الاختصار
        """
        shortcut = self.shortcuts.get(name)
        if shortcut:
            shortcut.setEnabled(True)
            logger.debug("تم تفعيل الاختصار: %s", name)

    def disable_shortcut(self, name: str):
        """
        تعطيل اختصار

        Args:
            name: اسم الاختصار
        """
        shortcut = self.shortcuts.get(name)
        if shortcut:
            shortcut.setEnabled(False)
            logger.debug("تم تعطيل الاختصار: %s", name)

    def enable_all(self):
        """تفعيل جميع الاختصارات"""
        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(True)
        logger.info("تم تفعيل جميع الاختصارات")

    def disable_all(self):
        """تعطيل جميع الاختصارات"""
        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(False)
        logger.info("تم تعطيل جميع الاختصارات")

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ShortcutOverride:
            if self._match_sequence(event):
                event.accept()
                return True
            return False

        if event.type() != QEvent.Type.KeyPress:
            return False

        if event.isAutoRepeat():
            return False

        return self._trigger_sequence(event)

    def _match_sequence(self, event) -> bool:
        shortcut_name = self._shortcut_name_for_event(event)
        if self._should_bypass_shortcut(shortcut_name):
            return False
        return shortcut_name is not None

    def _shortcut_name_for_event(self, event) -> str | None:
        key = event.key()
        if key == Qt.Key.Key_unknown:
            return None

        modifiers = event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        sequence = QKeySequence(int(modifiers.value) | key)
        sequence_text = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        for name in self.shortcut_definitions:
            expected = self._sequence_map.get(name)
            if not expected:
                continue
            expected_text = expected.toString(QKeySequence.SequenceFormat.PortableText)
            if expected_text == sequence_text:
                return name
        return None

    def _trigger_sequence(self, event) -> bool:
        shortcut_name = self._shortcut_name_for_event(event)
        if shortcut_name is None:
            return False
        return self._dispatch_shortcut(shortcut_name)

    def get_shortcuts_by_category(self) -> dict[str, list]:
        """
        الحصول على الاختصارات مصنفة حسب الفئة

        Returns:
            قاموس بالاختصارات مصنفة
        """
        categories: dict[str, list[dict[str, str]]] = {
            "إنشاء": [],
            "تنقل وبحث": [],
            "تحرير": [],
            "حفظ وإغلاق": [],
            "مساعدة": [],
            "التابات": [],
        }

        for name, definition in self.shortcut_definitions.items():
            if name.startswith("new_"):
                categories["إنشاء"].append(
                    {
                        "name": name,
                        "key": definition["key"],
                        "description": definition["description"],
                    }
                )
            elif name in ["search", "refresh", "full_sync"]:
                categories["تنقل وبحث"].append(
                    {
                        "name": name,
                        "key": definition["key"],
                        "description": definition["description"],
                    }
                )
            elif name in [
                "delete_selected",
                "select_all",
                "copy_selected",
                "export_excel",
                "print_current",
            ]:
                categories["تحرير"].append(
                    {
                        "name": name,
                        "key": definition["key"],
                        "description": definition["description"],
                    }
                )
            elif name in ["save", "close"]:
                categories["حفظ وإغلاق"].append(
                    {
                        "name": name,
                        "key": definition["key"],
                        "description": definition["description"],
                    }
                )
            elif name == "help":
                categories["مساعدة"].append(
                    {
                        "name": name,
                        "key": definition["key"],
                        "description": definition["description"],
                    }
                )
            elif name.startswith("tab_"):
                categories["التابات"].append(
                    {
                        "name": name,
                        "key": definition["key"],
                        "description": definition["description"],
                    }
                )

        return categories


# core/keyboard_shortcuts.py loaded
