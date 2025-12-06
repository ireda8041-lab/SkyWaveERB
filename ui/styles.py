# الملف: ui/styles.py
"""
ملف الأنماط الموحدة لكل الأزرار والعناصر في التطبيق
SkyWave Brand Identity Colors
"""

import os
import sys


def _get_asset_path(filename):
    """الحصول على المسار الصحيح للـ assets"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "assets", filename).replace("\\", "/")

# مسارات الأسهم
DOWN_ARROW_PATH = _get_asset_path("down-arrow.png")
UP_ARROW_PATH = _get_asset_path("up-arrow.png")

# ألوان SkyWave Brand Identity
COLORS = {
    "primary": "#0A6CF1",      # Primary Blue
    "success": "#0A6CF1",      # Primary Blue
    "warning": "#FF6636",      # Glowing Orange
    "danger": "#FF4FD8",       # Bright Pink
    "info": "#8B2CF5",         # Electric Purple
    "secondary": "#1E3A5F",    # Dark Blue/Gray
    "bg_dark": "#001A3A",      # Deep Blue (Main Background)
    "bg_medium": "#0A2A55",    # Input Background (Glassy look)
    "bg_light": "#052045",     # Slightly lighter for Headers
    "bg_card": "#001A3A",      # Deep Blue
    "text_primary": "#EAF3FF", # Light Sky (Text)
    "text_secondary": "#B0C4DE", # Light Blue Gray
    "border": "#1E3A5F",       # Border Color
    "header_bg": "#052045",    # Dark Header
}

# أنماط الأزرار الموحدة
BUTTON_STYLES = {
    "primary": f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['primary']}, stop:1 #2563eb);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 12px 24px;
            font-weight: bold;
            font-size: 14px;
            min-height: 20px;
            min-width: 120px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);


        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1d4ed8, stop:1 #1e40af);


        }}
        QPushButton:disabled {{
            background-color: #4b5563;
            color: #9ca3af;
        }}
    """,

    "success": f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['success']}, stop:1 #0A6CF1);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 12px 24px;
            font-weight: bold;
            font-size: 14px;
            min-height: 20px;
            min-width: 120px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A6CF1, stop:1 #0A6CF1);


        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A6CF1, stop:1 #0A6CF1);


        }}
        QPushButton:disabled {{
            background-color: #4b5563;
            color: #9ca3af;
        }}
    """,

    "warning": f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['warning']}, stop:1 #d97706);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 12px 24px;
            font-weight: bold;
            font-size: 14px;
            min-height: 20px;
            min-width: 120px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #d97706, stop:1 #b45309);


        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #b45309, stop:1 #92400e);


        }}
        QPushButton:disabled {{
            background-color: #4b5563;
            color: #9ca3af;
        }}
    """,

    "danger": f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['danger']}, stop:1 #dc2626);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 12px 24px;
            font-weight: bold;
            font-size: 14px;
            min-height: 20px;

        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #dc2626, stop:1 #b91c1c);


        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #b91c1c, stop:1 #991b1b);


        }}
        QPushButton:disabled {{
            background-color: #4b5563;
            color: #9ca3af;
        }}
    """,

    "info": f"""
        QPushButton {{
            background-color: {COLORS['info']};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: #7c3aed;
        }}
        QPushButton:pressed {{
            background-color: #6d28d9;
        }}
        QPushButton:disabled {{
            background-color: #4b5563;
        }}
    """,

    "secondary": f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['secondary']}, stop:1 #4b5563);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 12px 24px;
            font-weight: bold;
            font-size: 14px;
            min-height: 20px;
            min-width: 120px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3d4f5d, stop:1 #2d3548);


        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d3548, stop:1 #1a1d29);


        }}
        QPushButton:disabled {{
            background-color: #4b5563;
            color: #9ca3af;
        }}
    """,
}

# نمط الجدول الداكن الموحد (Blue Theme)
TABLE_STYLE_DARK = f"""
    QTableWidget {{
        background-color: {COLORS['bg_dark']};
        alternate-background-color: {COLORS['bg_medium']};
        color: {COLORS['text_primary']};
        border: none;
        gridline-color: {COLORS['border']};
        selection-background-color: {COLORS['primary']};
        font-size: 14px;
    }}
    QTableWidget::item {{
        padding: 12px 8px;
        min-height: 40px;
        border-bottom: 1px solid {COLORS['border']};
        border: none;
        text-align: center;
    }}
    QTableWidget::item:selected {{
        background-color: {COLORS['primary']};
        color: white;
    }}
    QTableWidget::item:focus {{
        border: none;
        outline: none;
    }}
    QTableWidget QLineEdit {{
        display: none;
    }}
    QTableWidget QSpinBox {{
        display: none;
    }}
    QTableWidget QDoubleSpinBox {{
        display: none;
    }}
    QHeaderView::section {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['header_bg']}, stop:1 #3b82f6);
        color: white;
        padding: 14px 10px;
        border: none;
        font-weight: bold;
        font-size: 14px;
        text-align: center;
        min-height: 25px;
    }}
"""

# نمط الشجرة الداكن
TREE_STYLE_DARK = f"""
    QTreeView {{
        background-color: {COLORS['bg_dark']};
        alternate-background-color: {COLORS['bg_medium']};
        color: {COLORS['text_primary']};
        border: none;
        selection-background-color: {COLORS['primary']};
        font-size: 14px;
    }}
    QTreeView::item {{
        padding: 10px 6px;
        min-height: 35px;
        border-bottom: 1px solid {COLORS['border']};
        text-align: center;
    }}
    QTreeView::item:selected {{
        background-color: {COLORS['primary']};
        color: white;
    }}
    QTreeView::branch {{
        background-color: {COLORS['bg_dark']};
    }}
    QHeaderView::section {{
        background-color: {COLORS['header_bg']};
        color: white;
        padding: 14px 10px;
        border: none;
        font-weight: bold;
        font-size: 14px;
        text-align: center;
        min-height: 25px;
    }}
"""

# نمط QTreeWidget (شجرة الحسابات الهرمية)
TREE_WIDGET_STYLE_DARK = f"""
    QTreeWidget {{
        background-color: {COLORS['bg_dark']};
        border: none;
        color: {COLORS['text_primary']};
    }}
    QTreeWidget::item {{
        padding: 8px;
        border-bottom: 1px solid #3f3f55;
        text-align: center;
    }}
    QTreeWidget::item:selected {{
        background-color: {COLORS['primary']};
        color: white;
    }}
    QTreeWidget::item:hover {{
        background-color: #2a2a3e;
    }}
    QTreeWidget::branch {{
        background-color: {COLORS['bg_dark']};
    }}
    QTreeWidget::branch:has-children:!has-siblings:closed,
    QTreeWidget::branch:closed:has-children:has-siblings {{
        border-image: none;
        image: url(none);
    }}
    QTreeWidget::branch:open:has-children:!has-siblings,
    QTreeWidget::branch:open:has-children:has-siblings {{
        border-image: none;
        image: url(none);
    }}
    QHeaderView::section {{
        background-color: {COLORS['header_bg']};
        color: white;
        padding: 10px;
        border: none;
        font-weight: bold;
        font-size: 13px;
        text-align: center;
    }}
"""

# ✨ نمط شجرة الحسابات (Chart of Accounts) - Dark Blue Theme
CHART_OF_ACCOUNTS_TREE_STYLE = f"""
    QTreeView {{
        background-color: {COLORS['bg_dark']};
        border: 1px solid {COLORS['border']};
        color: {COLORS['text_primary']};
        font-size: 13px;
        font-family: 'Cairo', 'Segoe UI', sans-serif;
        alternate-background-color: {COLORS['bg_medium']};
        gridline-color: {COLORS['border']};
        selection-background-color: {COLORS['primary']};
    }}
    QTreeView::item {{
        padding: 8px 6px;
        border-bottom: 1px solid {COLORS['border']};
        border-right: 1px solid rgba(30, 58, 95, 0.5);
        min-height: 35px;
    }}
    QTreeView::item:selected {{
        background-color: {COLORS['primary']};
        color: white;
        font-weight: bold;
    }}
    QTreeView::item:hover {{
        background-color: rgba(10, 108, 241, 0.2);
    }}
    QTreeView::branch {{
        background-color: transparent;
    }}
    QTreeView::branch:has-children:!has-siblings:closed,
    QTreeView::branch:closed:has-children:has-siblings {{
        border-image: none;
        image: none;
    }}
    QTreeView::branch:open:has-children:!has-siblings,
    QTreeView::branch:open:has-children:has-siblings {{
        border-image: none;
        image: none;
    }}
    QHeaderView::section {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['primary']}, stop:1 #005BC5);
        color: white;
        padding: 10px 8px;
        border: none;
        border-right: 1px solid rgba(255,255,255,0.3);
        font-weight: bold;
        font-size: 13px;
        min-height: 35px;
        font-family: 'Cairo', 'Segoe UI', sans-serif;
    }}
"""

# للتوافق مع الكود القديم
TABLE_STYLE = TABLE_STYLE_DARK
TREE_STYLE = TREE_STYLE_DARK

# أنماط GroupBox
GROUPBOX_STYLE = f"""
    QGroupBox {{
        font-weight: bold;
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 10px;
        color: {COLORS['text_primary']};
        background-color: {COLORS['bg_light']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        color: {COLORS['text_primary']};
    }}
"""

# نمط شريط الحالة (Status Bar) - إصلاح الخلفية البيضاء
STATUS_BAR_STYLE = f"""
    QStatusBar {{
        background-color: {COLORS['bg_dark']};
        border-top: 1px solid {COLORS['border']};
    }}
    QStatusBar QLabel {{
        background-color: transparent;
        border: none;
        color: {COLORS['text_secondary']};
        padding: 0 10px;
        font-weight: bold;
    }}
    QStatusBar QWidget {{
        background-color: transparent;
    }}
"""

# === COMPLETE STYLESHEET للتطبيق بالكامل (SkyWave Brand) ===
COMPLETE_STYLESHEET = f"""
/* === 1. General Settings === */
QWidget {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
    font-family: 'Cairo', 'Segoe UI', 'Tahoma', 'Arial Unicode MS', sans-serif;
    font-size: 14px;
    font-weight: normal;
}}

/* === 2. Inputs (Clean & Simple) === */
QLineEdit {{
    background-color: {COLORS['bg_medium']};
    border: 1px solid #374151;
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 28px;
    color: #F8FAFC;
    font-size: 13px;
}}

QLineEdit:focus {{
    border: 1px solid {COLORS['primary']};
}}

/* ComboBox - خلفية فاتحة */
QComboBox {{
    background-color: {COLORS['bg_medium']};
    border: 1px solid #374151;
    border-radius: 4px;
    padding: 8px 12px;
    min-height: 36px;
    min-width: 150px;
    color: #F8FAFC;
    font-size: 14px;
}}

QComboBox:focus {{
    border: 1px solid {COLORS['primary']};
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_medium']};
    color: #F8FAFC;
    selection-background-color: {COLORS['primary']};
    border: 1px solid #374151;
    outline: none;
}}

QComboBox QLineEdit {{
    background-color: transparent;
    border: none;
    color: #F8FAFC;
    padding: 0px;
    selection-background-color: {COLORS['primary']};
}}

/* DateEdit - خلفية فاتحة */
QDateEdit {{
    background-color: {COLORS['bg_medium']};
    border: 1px solid #374151;
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 32px;
    color: #F8FAFC;
    font-size: 13px;
}}

QDateEdit:focus {{
    border: 1px solid {COLORS['primary']};
}}

/* SpinBox & DoubleSpinBox - مع أزرار واضحة */
QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_medium']};
    border: 1px solid #374151;
    border-radius: 4px;
    padding: 6px 30px 6px 10px;
    min-height: 32px;
    color: #F8FAFC;
    font-size: 13px;
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLORS['primary']};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 24px;
    height: 16px;
    background-color: rgba(10, 108, 241, 0.3);
    border: none;
    border-left: 1px solid #374151;
    border-top-right-radius: 4px;
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background-color: rgba(10, 108, 241, 0.5);
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 24px;
    height: 16px;
    background-color: rgba(10, 108, 241, 0.3);
    border: none;
    border-left: 1px solid #374151;
    border-bottom-right-radius: 4px;
}}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: rgba(10, 108, 241, 0.5);
}}

/* استخدام علامات + و - بدلاً من الأسهم */
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    width: 0;
    height: 0;
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
}}

QTextEdit {{
    background-color: {COLORS['bg_medium']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 8px;
    color: {COLORS['text_primary']};
}}

QTextEdit:focus {{
    border: 1px solid {COLORS['primary']};
}}

/* === 3. Labels === */
QLabel {{
    color: {COLORS['text_primary']};
    font-weight: bold;
    margin-bottom: 4px;
    background-color: transparent;
}}

/* === 4. Buttons (Brand Colors) === */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['primary']}, stop:1 #005BC5);
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    min-height: 40px;
    min-width: 120px;
    font-weight: bold;
    font-size: 14px;
    font-family: 'Cairo', 'Segoe UI', sans-serif;
}}

QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #005BC5, stop:1 #004A9F);
}}

QPushButton:pressed {{
    background-color: #004A9F;
}}

QPushButton:disabled {{
    background-color: #4b5563;
    color: #9ca3af;
}}

/* Specific Action Buttons */
QPushButton[text*="إضافة"], QPushButton[text*="جديد"], QPushButton[text*="حفظ"] {{
    background-color: {COLORS['primary']};
    border: none;
}}

QPushButton[text*="إضافة"]:hover, QPushButton[text*="جديد"]:hover, QPushButton[text*="حفظ"]:hover {{
    background-color: #005BC5;
}}

QPushButton[text*="تعديل"] {{
    background-color: {COLORS['warning']};
    color: white;
    border: none;
}}

QPushButton[text*="تعديل"]:hover {{
    background-color: #E55025;
}}

/* أزرار الحذف - لون بينك فاقع */
QPushButton[text*="حذف"], QPushButton[text*="إلغاء"], QPushButton[text*="Delete"], QPushButton[text*="مسح"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['danger']}, stop:1 #D430B0);
    color: white;
    border: none;
}}

QPushButton[text*="حذف"]:hover, QPushButton[text*="إلغاء"]:hover, QPushButton[text*="Delete"]:hover, QPushButton[text*="مسح"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #D430B0, stop:1 #B01090);
    border: 1px solid {COLORS['danger']};
}}

/* === 5. Tables (Deep Blue Theme) === */
QTableWidget {{
    background-color: {COLORS['bg_dark']};
    gridline-color: {COLORS['border']};
    border: 1px solid {COLORS['border']};
    font-size: 13px;
}}

QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['primary']}, stop:1 #005BC5);
    color: white;
    padding: 15px 10px;
    border: none;
    border-right: 1px solid rgba(255,255,255,0.3);
    font-weight: bold;
    font-size: 14px;
    min-height: 40px;
    text-align: center;
    font-family: 'Cairo', 'Segoe UI', sans-serif;
}}

QTableWidget::item {{
    padding: 12px 10px;
    border-bottom: 1px solid {COLORS['border']};
    border-right: 1px solid rgba(30, 58, 95, 0.5);
    text-align: center;
    min-height: 40px;
    font-size: 14px;
    font-family: 'Cairo', 'Segoe UI', sans-serif;
}}

QTableWidget::item:selected {{
    background-color: {COLORS['primary']};
    color: white;
    font-weight: bold;
}}

QTableWidget::item:alternate {{
    background-color: {COLORS['bg_medium']};
}}

/* إخفاء أي مؤشر أو مربع اختيار داخل الجدول */
QTableView::indicator, QTableWidget::indicator {{
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
    image: none;
}}

/* إزالة المسافة المحجوزة للأيقونة */
QTableWidget::item {{
    padding-left: 5px;
    margin: 0px;
}}

/* === Editor داخل الجدول === */
QTableWidget QLineEdit {{
    background-color: {COLORS['bg_medium']};
    border: 2px solid {COLORS['primary']};
    border-radius: 0px;
    padding: 2px 4px;
    margin: 0px;
    color: #F8FAFC;
    font-size: 13px;
    min-height: 24px;
    max-height: 30px;
}}

QTableWidget QSpinBox, QTableWidget QDoubleSpinBox {{
    background-color: {COLORS['bg_medium']};
    border: 2px solid {COLORS['primary']};
    border-radius: 0px;
    padding: 2px 4px;
    margin: 0px;
    color: #F8FAFC;
    font-size: 13px;
    min-height: 24px;
    max-height: 30px;
}}

QTableWidget QSpinBox::up-button, QTableWidget QDoubleSpinBox::up-button,
QTableWidget QSpinBox::down-button, QTableWidget QDoubleSpinBox::down-button {{
    width: 0px;
    height: 0px;
    border: none;
}}

/* === 6. Tabs === */
QTabBar::tab {{
    background-color: {COLORS['header_bg']};
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: {COLORS['text_secondary']};
}}

QTabBar::tab:selected {{
    background-color: {COLORS['primary']};
    color: white;
    font-weight: bold;
}}

/* GroupBox */
QGroupBox {{
    font-weight: bold;
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 10px;
    color: {COLORS['text_primary']};
    background-color: {COLORS['bg_dark']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: {COLORS['text_primary']};
}}

/* === تم حذف التعريفات المكررة - الأسهم محددة في القسم 2 أعلاه === */

/* ScrollBars */
QScrollBar:vertical {{
    background-color: {COLORS['bg_dark']};
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border']};
    border-radius: 6px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['primary']};
}}

/* STATUS BAR */
QStatusBar {{
    background-color: {COLORS['bg_dark']};
    border-top: 1px solid {COLORS['border']};
}}

QStatusBar QLabel {{
    background-color: transparent;
    border: none;
    color: {COLORS['text_secondary']};
    padding: 0 10px;
    font-weight: bold;
}}

QStatusBar QWidget {{
    background-color: transparent;
}}

/* CheckBox */
QCheckBox {{
    color: {COLORS['text_primary']};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid {COLORS['border']};
    background-color: {COLORS['bg_medium']};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS['primary']};
    border-color: {COLORS['primary']};
}}
"""


def apply_styles(app):
    """تطبيق الأنماط على التطبيق بالكامل"""
    # تحميل الخط العربي من الملف
    import os
    import sys

    from PyQt6.QtGui import QFont, QFontDatabase

    # تحديد المسار الصحيح للخط
    if getattr(sys, 'frozen', False):
        # البرنامج مجمع (EXE)
        base_path = sys._MEIPASS
    else:
        # البرنامج يعمل من Python
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    font_path = os.path.join(base_path, "assets", "font", "Cairo-VariableFont_slnt,wght.ttf")

    # تحميل خط Cairo من الملف (متوافق مع PyQt6 و Python 3.14)
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                cairo_font = QFont(font_families[0], 14)
                cairo_font.setWeight(QFont.Weight.Normal)
                app.setFont(cairo_font)
                print(f"✅ تم تحميل خط Cairo من: {font_path}")
            else:
                print("⚠️ فشل تحميل خط Cairo، استخدام الخط الافتراضي")
                app.setFont(QFont("Segoe UI", 14))
        else:
            print("⚠️ فشل إضافة خط Cairo، استخدام الخط الافتراضي")
            app.setFont(QFont("Segoe UI", 14))
    else:
        print(f"⚠️ ملف الخط غير موجود: {font_path}")
        # محاولة استخدام خط عربي من النظام
        app.setFont(QFont("Tahoma", 14))

    # تطبيق الأنماط
    app.setStyleSheet(COMPLETE_STYLESHEET)

def apply_center_alignment_to_all_tables(widget):
    """
    تطبيق التوسيط على كل الجداول في الـ widget وأطفاله
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTableWidget, QTreeView, QTreeWidget

    # البحث عن كل الجداول
    tables = widget.findChildren(QTableWidget)
    for table in tables:
        setup_table_with_center_alignment(table)
        center_align_table(table)

    # البحث عن كل الأشجار
    trees = widget.findChildren(QTreeWidget) + widget.findChildren(QTreeView)
    for tree in trees:
        header = tree.header()
        if header:
            header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

# نمط الحقول
INPUT_STYLE = f"""
    QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
        background-color: {COLORS['bg_medium']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 5px;
        color: {COLORS['text_primary']};
    }}
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
        border: 2px solid {COLORS['primary']};
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLORS['bg_medium']};
        color: {COLORS['text_primary']};
        selection-background-color: {COLORS['primary']};
    }}
"""

# دالة مساعدة لتطبيق الأنماط على الأزرار
def apply_button_style(button, style_name: str = "primary"):
    """تطبيق نمط موحد على زرار"""
    if style_name in BUTTON_STYLES:
        button.setStyleSheet(BUTTON_STYLES[style_name])

def configure_table_no_edit(table):
    """
    دالة مساعدة لتطبيق إعدادات منع التحرير على أي جدول
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTableWidget

    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setTabKeyNavigation(False)
    table.setStyleSheet(TABLE_STYLE_DARK)

    # توسيط كل النص في الجدول
    center_align_table(table)

def center_align_table(table):
    """
    توسيط كل النص في الجدول
    """
    from PyQt6.QtCore import Qt

    # توسيط العناوين
    header = table.horizontalHeader()
    if header:
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

    # توسيط كل الخلايا الموجودة
    for row in range(table.rowCount()):
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

def setup_table_with_center_alignment(table):
    """
    إعداد جدول مع توسيط النص
    """
    from PyQt6.QtCore import Qt

    # توسيط العناوين
    header = table.horizontalHeader()
    if header:
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

    # ربط إشارة لتوسيط أي عنصر جديد
    def on_item_changed(item):
        if item:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    table.itemChanged.connect(on_item_changed)
def setup_custom_title_bar(window):
    """
    دالة لتطبيق لون شريط العنوان المخصص على أي نافذة
    """
    try:
        import platform

        # للويندوز - تخصيص شريط العنوان
        if platform.system() == "Windows":
            try:
                import ctypes

                # الحصول على handle النافذة
                hwnd = int(window.winId())

                # تعريف الألوان (BGR format)
                title_bar_color = 0x291301  # #011329 في BGR
                title_text_color = 0xffffff  # أبيض للنص

                # تطبيق لون شريط العنوان
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 35, ctypes.byref(ctypes.c_int(title_bar_color)), 4
                )

                # تطبيق لون نص شريط العنوان
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 36, ctypes.byref(ctypes.c_int(title_text_color)), 4
                )

            except Exception as e:
                print(f"تعذر تخصيص شريط العنوان للنافذة: {e}")

    except Exception as e:
        print(f"خطأ في تخصيص شريط العنوان: {e}")

def get_dialog_style():
    """
    نمط موحد للحوارات مع شريط العنوان المخصص
    """
    return f"""
        QDialog {{
            background-color: {COLORS['bg_dark']};
            color: {COLORS['text_primary']};
        }}
        QDialog QLabel {{
            color: {COLORS['text_primary']};
        }}
        QDialog QPushButton {{
            background-color: {COLORS['primary']};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
        }}
        QDialog QPushButton:hover {{
            background-color: {COLORS['info']};
        }}
        QDialog QPushButton:pressed {{
            background-color: {COLORS['secondary']};
        }}
    """


# === دالة فارغة للتوافق مع الكود القديم ===

def apply_arrows_to_all_widgets(parent_widget):
    """
    دالة فارغة للتوافق - الأسهم الآن تأتي من صور PNG في الـ stylesheet
    """
    pass
