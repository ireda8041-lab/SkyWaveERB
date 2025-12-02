# الملف: ui/shortcuts_help_dialog.py

"""
نافذة مساعدة اختصارات لوحة المفاتيح
تعرض جميع الاختصارات المتاحة
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton,
    QTabWidget, QWidget, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from typing import Dict


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
        self.setMinimumSize(700, 600)
        self.setModal(True)
        
        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except:
            pass  # إذا لم يكن متوفراً
        
        layout = QVBoxLayout()
        
        # العنوان
        title_layout = QHBoxLayout()
        
        icon_label = QLabel("⌨️")
        icon_label.setStyleSheet("font-size: 32px;")
        title_layout.addWidget(icon_label)
        
        title = QLabel("اختصارات لوحة المفاتيح")
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px;")
        title_layout.addWidget(title, 1)
        
        layout.addLayout(title_layout)
        
        # الوصف
        description = QLabel(
            "استخدم هذه الاختصارات لتسريع عملك وزيادة إنتاجيتك"
        )
        description.setStyleSheet("color: #666; padding: 5px 10px; font-size: 14px;")
        layout.addWidget(description)
        
        # التابات للفئات
        tabs = QTabWidget()
        # استخدام الأنماط من ملف styles
        from ui.styles import COLORS
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid #374151;
                border-radius: 4px;
                background-color: {COLORS['background']};
            }}
            QTabBar::tab {{
                padding: 10px 20px;
                margin: 2px;
                background-color: {COLORS['surface']};
                border: 1px solid #374151;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: {COLORS['text']};
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['background']};
                border-bottom: 2px solid {COLORS['primary']};
            }}
            QTabBar::tab:hover {{
                background-color: {COLORS['hover']};
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
        
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # ملء الجدول
        for row, shortcut in enumerate(shortcuts):
            # عمود الاختصار
            key_item = QTableWidgetItem(shortcut['key'])
            key_font = QFont()
            key_font.setBold(True)
            key_font.setPointSize(12)
            key_item.setFont(key_font)
            key_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            key_item.setBackground(Qt.GlobalColor.lightGray)
            table.setItem(row, 0, key_item)
            
            # عمود الوصف
            desc_item = QTableWidgetItem(shortcut['description'])
            desc_item.setFont(QFont("Arial", 11))
            table.setItem(row, 1, desc_item)
        
        # ضبط عرض الأعمدة
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # ضبط ارتفاع الصفوف
        table.verticalHeader().setDefaultSectionSize(50)
        
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
