# الملف: ui/shortcuts_help_dialog.py

"""
نافذة مساعدة اختصارات لوحة المفاتيح
تعرض جميع الاختصارات المتاحة
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class ShortcutsHelpDialog(QDialog):
    """
    نافذة مساعدة الاختصارات
    - عرض جميع الاختصارات المتاحة
    - تصنيف الاختصارات حسب الفئة
    - تصميم احترافي وسهل القراءة
    """

    def __init__(self, shortcuts_manager, parent=None):
        super().__init__(parent)
        self.shortcuts_manager = shortcuts_manager
        self.init_ui()

    def init_ui(self):
        """تهيئة الواجهة"""
        self.setWindowTitle("اختصارات لوحة المفاتيح")
        self.setMinimumSize(750, 650)
        self.setModal(True)

        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            # الدالة غير متوفرة
            pass

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # العنوان مع خلفية ملونة (ألوان SkyWave Brand) - تصميم احترافي
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect

        from ui.styles import COLORS

        header_frame = QWidget()
        header_frame.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {COLORS['primary']}, stop:0.5 #005BC5, stop:1 #8B2CF5);
                border-radius: 16px;
                padding: 25px;
            }}
        """)

        # إضافة ظل للهيدر
        header_shadow = QGraphicsDropShadowEffect()
        header_shadow.setBlurRadius(20)
        header_shadow.setColor(QColor(10, 108, 241, 100))
        header_shadow.setOffset(0, 5)
        header_frame.setGraphicsEffect(header_shadow)

        title_layout = QHBoxLayout()
        title_layout.setSpacing(20)

        # أيقونة مع خلفية دائرية
        icon_container = QWidget()
        icon_container.setFixedSize(70, 70)
        icon_container.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 35px;
            }
        """)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("⌨️")
        icon_label.setStyleSheet("font-size: 36px; background: transparent;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_label)
        title_layout.addWidget(icon_container)

        title_text_layout = QVBoxLayout()
        title_text_layout.setSpacing(8)

        title = QLabel("اختصارات لوحة المفاتيح")
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: white; background: transparent;")
        title_text_layout.addWidget(title)

        # الوصف
        description = QLabel("استخدم هذه الاختصارات لتسريع عملك وزيادة إنتاجيتك ⚡")
        description.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 14px; background: transparent;")
        title_text_layout.addWidget(description)

        title_layout.addLayout(title_text_layout, 1)
        header_frame.setLayout(title_layout)

        layout.addWidget(header_frame)

        # التابات للفئات مع تصميم محسّن (ألوان SkyWave Brand) - تصميم احترافي
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 2px solid {COLORS['primary']};
                border-radius: 12px;
                background-color: {COLORS['bg_dark']};
                padding: 15px;
                margin-top: -1px;
            }}
            QTabBar::tab {{
                padding: 14px 28px;
                margin: 2px 4px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['bg_medium']}, stop:1 {COLORS['bg_light']});
                border: 1px solid {COLORS['border']};
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                color: {COLORS['text_secondary']};
                font-size: 13px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['primary']}, stop:1 #005BC5);
                color: white;
                border: 2px solid {COLORS['primary']};
                border-bottom: none;
            }}
            QTabBar::tab:hover:!selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['bg_light']}, stop:1 {COLORS['bg_medium']});
                color: white;
            }}
        """)

        # الحصول على الاختصارات مصنفة
        categories = self.shortcuts_manager.get_shortcuts_by_category()

        # إنشاء تاب لكل فئة
        for category_name, shortcuts in categories.items():
            if shortcuts:  # فقط إذا كانت الفئة تحتوي على اختصارات
                tab = self._create_category_tab(category_name, shortcuts)
                tabs.addTab(tab, category_name)

        layout.addWidget(tabs)

        # زر الإغلاق
        close_button = QPushButton("إغلاق")
        # استخدام الأنماط الموحدة
        from ui.styles import BUTTON_STYLES
        close_button.setStyleSheet(BUTTON_STYLES["primary"])
        close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_category_tab(self, category_name: str, shortcuts: list) -> QWidget:
        """
        إنشاء تاب لفئة معينة

        Args:
            category_name: اسم الفئة
            shortcuts: قائمة الاختصارات

        Returns:
            ويدجت التاب
        """
        widget = QWidget()
        layout = QVBoxLayout()

        # جدول الاختصارات
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["الاختصار", "الوصف"])
        table.setRowCount(len(shortcuts))

        # تنسيق الجدول بالأنماط الموحدة
        from ui.styles import TABLE_STYLE_DARK
        table.setStyleSheet(TABLE_STYLE_DARK)

        v_header = table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # ملء الجدول (ألوان SkyWave Brand) - تصميم احترافي
        for row, shortcut in enumerate(shortcuts):
            # عمود الاختصار مع تصميم محسّن
            key_text = shortcut['key']
            key_item = QTableWidgetItem(f"  {key_text}  ")
            key_font = QFont("Consolas", 12)
            key_font.setBold(True)
            key_item.setFont(key_font)
            key_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            from PyQt6.QtGui import QColor
            # تلوين متناوب للصفوف
            if row % 2 == 0:
                key_item.setBackground(QColor("#0A6CF1"))  # Primary Blue
            else:
                key_item.setBackground(QColor("#005BC5"))  # Darker Blue
            key_item.setForeground(QColor("white"))
            table.setItem(row, 0, key_item)

            # عمود الوصف
            desc_item = QTableWidgetItem(f"  {shortcut['description']}")
            desc_font = QFont("Segoe UI", 11)
            desc_item.setFont(desc_font)
            if row % 2 == 0:
                desc_item.setBackground(QColor("#0A2A55"))  # bg_medium
            else:
                desc_item.setBackground(QColor("#052045"))  # bg_light
            desc_item.setForeground(QColor("#EAF3FF"))  # text_primary
            table.setItem(row, 1, desc_item)

        # ضبط عرض الأعمدة
        header = table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # ضبط ارتفاع الصفوف
        v_header = table.verticalHeader()
        if v_header is not None:
            v_header.setDefaultSectionSize(50)

        layout.addWidget(table)
        widget.setLayout(layout)

        return widget

    def keyPressEvent(self, event):
        """معالج الضغط على المفاتيح"""
        # إغلاق النافذة عند الضغط على Esc
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)


# تم إنشاء الملف بنجاح
