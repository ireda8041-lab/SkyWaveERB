# الملف: ui/shortcuts_help_dialog.py
"""
نافذة مساعدة اختصارات لوحة المفاتيح
تصميم احترافي متجاوب
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ShortcutsHelpDialog(QDialog):
    """نافذة مساعدة الاختصارات"""

    def __init__(self, shortcuts_manager, parent=None):
        super().__init__(parent)
        self.shortcuts_manager = shortcuts_manager
        self._setup_ui()

        # ⚡ تطبيق الستايلات المتجاوبة
        from ui.styles import setup_auto_responsive_dialog

        setup_auto_responsive_dialog(self)

    def _setup_ui(self):
        """إعداد الواجهة"""
        self.setWindowTitle("⌨️ اختصارات لوحة المفاتيح")
        self.setMinimumSize(550, 450)
        self.resize(650, 550)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setModal(True)

        # شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar

            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            # فشل تطبيق شريط العنوان المخصص
            pass

        # الخلفية
        self.setStyleSheet(
            """
            QDialog {
                background-color: #001A3A;
            }
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # الهيدر
        layout.addWidget(self._create_header())

        # المحتوى
        layout.addWidget(self._create_content(), 1)

        # الفوتر
        layout.addWidget(self._create_footer())

    def _create_header(self) -> QWidget:
        """إنشاء الهيدر"""
        header = QFrame()
        header.setFixedHeight(90)
        header.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0A6CF1, stop:1 #0550B8);
            }
        """
        )

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)

        # أيقونة
        icon = QLabel("⌨️")
        icon.setStyleSheet(
            """
            font-size: 36px;
            background: rgba(255,255,255,0.15);
            border-radius: 25px;
            padding: 8px;
        """
        )
        icon.setFixedSize(55, 55)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        # النصوص
        text_box = QVBoxLayout()
        text_box.setSpacing(4)

        title = QLabel("اختصارات لوحة المفاتيح")
        title.setStyleSheet(
            "color: white; font-size: 20px; font-weight: bold; background: transparent;"
        )
        text_box.addWidget(title)

        subtitle = QLabel("استخدم هذه الاختصارات لتسريع عملك ⚡")
        subtitle.setStyleSheet(
            "color: rgba(255,255,255,0.85); font-size: 12px; background: transparent;"
        )
        text_box.addWidget(subtitle)

        layout.addLayout(text_box, 1)
        return header

    def _create_content(self) -> QWidget:
        """إنشاء المحتوى"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            """
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #0A2A55;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #0A6CF1;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """
        )

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)

        # الحصول على الاختصارات
        categories = self.shortcuts_manager.get_shortcuts_by_category()

        icons = {
            "إنشاء": "➕",
            "تنقل وبحث": "🔍",
            "تحرير": "✏️",
            "حفظ وإغلاق": "💾",
            "مساعدة": "❓",
            "التابات": "📑",
        }

        for cat_name, shortcuts in categories.items():
            if shortcuts:
                section = self._create_section(cat_name, icons.get(cat_name, "📌"), shortcuts)
                content_layout.addWidget(section)

        content_layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _create_section(self, title: str, icon: str, shortcuts: list) -> QWidget:
        """إنشاء قسم فئة"""
        section = QFrame()
        section.setStyleSheet(
            """
            QFrame {
                background: rgba(10, 42, 85, 0.5);
                border: 1px solid rgba(10, 108, 241, 0.3);
                border-radius: 10px;
                padding: 10px;
            }
        """
        )

        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # عنوان الفئة
        header = QLabel(f"{icon} {title}")
        header.setStyleSheet(
            """
            color: #0A6CF1;
            font-size: 14px;
            font-weight: bold;
            padding-bottom: 5px;
            border-bottom: 1px solid rgba(10, 108, 241, 0.3);
            background: transparent;
        """
        )
        layout.addWidget(header)

        # الاختصارات
        for shortcut in shortcuts:
            row = self._create_shortcut_row(shortcut["key"], shortcut["description"])
            layout.addWidget(row)

        return section

    def _create_shortcut_row(self, key: str, description: str) -> QWidget:
        """إنشاء صف اختصار"""
        row = QFrame()
        row.setStyleSheet(
            """
            QFrame {
                background: rgba(5, 32, 69, 0.6);
                border-radius: 6px;
                padding: 4px;
            }
            QFrame:hover {
                background: rgba(10, 108, 241, 0.15);
            }
        """
        )
        row.setFixedHeight(40)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(12)

        # المفتاح
        key_label = QLabel(key)
        key_label.setStyleSheet(
            """
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #0A6CF1, stop:1 #0550B8);
            color: white;
            font-size: 11px;
            font-weight: bold;
            padding: 5px 12px;
            border-radius: 5px;
            min-width: 70px;
        """
        )
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(key_label)

        # الوصف
        desc_label = QLabel(description)
        desc_label.setStyleSheet(
            """
            color: #EAF3FF;
            font-size: 12px;
            background: transparent;
        """
        )
        layout.addWidget(desc_label, 1)

        return row

    def _create_footer(self) -> QWidget:
        """إنشاء الفوتر"""
        footer = QFrame()
        footer.setFixedHeight(55)
        footer.setStyleSheet(
            """
            QFrame {
                background: #0A2A55;
                border-top: 1px solid #1E3A5F;
            }
        """
        )

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(15, 10, 15, 10)

        tip = QLabel("💡 اضغط F1 في أي وقت لعرض هذه النافذة")
        tip.setStyleSheet("color: #B0C4DE; font-size: 11px; background: transparent;")
        layout.addWidget(tip)

        layout.addStretch()

        close_btn = QPushButton("إغلاق")
        close_btn.setFixedSize(90, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0A6CF1, stop:1 #0550B8);
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }
        """
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        return footer

    def keyPressEvent(self, event):
        """إغلاق بـ Escape"""
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)
