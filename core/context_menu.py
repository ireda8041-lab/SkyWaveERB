# الملف: core/context_menu.py

"""
نظام قوائم السياق (Right-Click Menu) الاحترافي
يوفر قوائم سياقية للجداول والعناصر المختلفة
"""

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QTableWidget

from core.logger import get_logger
from ui.styles import COLORS

logger = get_logger(__name__)


def is_right_click_active() -> bool:
    """
    ⚡ التحقق إذا كان الكليك يمين مضغوط حالياً
    يتحقق من زر الماوس المضغوط أو من الـ flag
    """
    # التحقق من زر الماوس المضغوط حالياً
    buttons = QApplication.mouseButtons()
    if buttons & Qt.MouseButton.RightButton:
        return True
    # التحقق من الـ flag (للحالات اللي الزر اترفع فيها)
    return RightClickBlocker.is_right_clicking


class RightClickBlocker(QObject):
    """
    ⚡ فلتر لتتبع الكليك يمين
    """

    is_right_clicking = False

    def __init__(self, table: QTableWidget = None, parent=None):
        super().__init__(parent)
        self.table = table

    def eventFilter(self, obj, event):
        # ⚡ التحقق من وجود الـ table قبل الوصول له
        try:
            if self.table and not self.table.isVisible():
                return False

            if self.table and obj == self.table.viewport():
                if event.type() == QEvent.Type.MouseButtonPress:
                    if event.button() == Qt.MouseButton.RightButton:
                        RightClickBlocker.is_right_clicking = True
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    if event.button() == Qt.MouseButton.RightButton:
                        # تأخير إعادة التعيين
                        from PyQt6.QtCore import QTimer

                        QTimer.singleShot(200, self._reset_flag)
        except RuntimeError:
            # الـ table تم حذفه - تجاهل الخطأ
            return False
        return False

    @staticmethod
    def _reset_flag():
        RightClickBlocker.is_right_clicking = False


class ContextMenuManager:
    """
    مدير قوائم السياق - يضيف قوائم كليك يمين احترافية للجداول
    """

    # ستايل القائمة
    MENU_STYLE = f"""
        QMenu {{
            background-color: {COLORS['bg_medium']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 5px;
        }}
        QMenu::item {{
            background-color: transparent;
            color: {COLORS['text_primary']};
            padding: 8px 25px 8px 15px;
            border-radius: 4px;
            margin: 2px 5px;
        }}
        QMenu::item:selected {{
            background-color: {COLORS['primary']};
            color: white;
        }}
        QMenu::item:disabled {{
            color: {COLORS['text_secondary']};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {COLORS['border']};
            margin: 5px 10px;
        }}
    """

    @staticmethod
    def setup_table_context_menu(
        table: QTableWidget,
        on_view=None,
        on_edit=None,
        on_delete=None,
        on_copy=None,
        on_refresh=None,
        on_export=None,
        on_print=None,
        custom_actions: list = None,
    ):
        """
        إعداد قائمة سياق لجدول

        Args:
            table: الجدول
            on_view: دالة العرض
            on_edit: دالة التعديل
            on_delete: دالة الحذف
            on_copy: دالة النسخ
            on_refresh: دالة التحديث
            on_export: دالة التصدير
            on_print: دالة الطباعة
            custom_actions: قائمة بإجراءات مخصصة [(name, icon, callback), ...]
        """
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # ⚡ تثبيت فلتر لتحديد flag الكليك يمين
        right_click_blocker = RightClickBlocker(table, table)
        table.viewport().installEventFilter(right_click_blocker)
        table._right_click_blocker = right_click_blocker

        def show_context_menu(position):
            # تحديد الصف تحت الماوس
            item = table.itemAt(position)
            if item:
                row = item.row()
                table.selectRow(row)

            menu = QMenu(table)
            menu.setStyleSheet(ContextMenuManager.MENU_STYLE)

            # التحقق من وجود صف محدد
            selected_rows = table.selectionModel().selectedRows()
            has_selection = len(selected_rows) > 0

            # إجراءات العرض والتعديل
            if on_view:
                view_action = QAction("👁️ عرض التفاصيل", table)
                view_action.triggered.connect(on_view)
                view_action.setEnabled(has_selection)
                menu.addAction(view_action)

            if on_edit:
                edit_action = QAction("✏️ تعديل", table)
                edit_action.triggered.connect(on_edit)
                edit_action.setEnabled(has_selection)
                menu.addAction(edit_action)

            if on_view or on_edit:
                menu.addSeparator()

            # إجراءات النسخ
            if on_copy:
                copy_action = QAction("📋 نسخ", table)
                copy_action.triggered.connect(on_copy)
                copy_action.setEnabled(has_selection)
                menu.addAction(copy_action)

            # إجراءات مخصصة
            if custom_actions:
                menu.addSeparator()
                for action_def in custom_actions:
                    if len(action_def) >= 3:
                        name, icon, callback = action_def[:3]
                        enabled = action_def[3] if len(action_def) > 3 else has_selection
                        action = QAction(f"{icon} {name}", table)
                        action.triggered.connect(callback)
                        action.setEnabled(enabled)
                        menu.addAction(action)

            menu.addSeparator()

            # إجراءات التحديث والتصدير
            if on_refresh:
                refresh_action = QAction("🔄 تحديث", table)
                refresh_action.triggered.connect(on_refresh)
                menu.addAction(refresh_action)

            if on_export:
                export_action = QAction("📥 تصدير Excel", table)
                export_action.triggered.connect(on_export)
                menu.addAction(export_action)

            if on_print:
                print_action = QAction("🖨️ طباعة", table)
                print_action.triggered.connect(on_print)
                menu.addAction(print_action)

            # إجراء الحذف (في النهاية)
            if on_delete:
                menu.addSeparator()
                delete_action = QAction("🗑️ حذف", table)
                delete_action.triggered.connect(on_delete)
                delete_action.setEnabled(has_selection)
                menu.addAction(delete_action)

            # عرض القائمة
            menu.exec(table.viewport().mapToGlobal(position))

        table.customContextMenuRequested.connect(show_context_menu)
        logger.debug("تم إعداد قائمة السياق للجدول")


class DoubleClickHandler:
    """
    معالج النقر المزدوج على الجداول
    """

    @staticmethod
    def setup_double_click(table: QTableWidget, on_double_click):
        """
        إعداد معالج النقر المزدوج

        Args:
            table: الجدول
            on_double_click: دالة تنفذ عند النقر المزدوج
        """
        table.doubleClicked.connect(lambda: on_double_click())
        logger.debug("تم إعداد معالج النقر المزدوج")
