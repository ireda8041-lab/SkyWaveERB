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
    "primary_hover": "#2563eb", # Primary Blue Hover
    "primary_dark": "#1d4ed8",  # Primary Blue Dark
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

# أنماط الأزرار الموحدة - مصغرة واحترافية
BUTTON_STYLES = {
    "primary": f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['primary']}, stop:1 #2563eb);
            color: white;
            border: none;
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: bold;
            font-size: 11px;
            min-height: 14px;
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
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: bold;
            font-size: 11px;
            min-height: 14px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A6CF1, stop:1 #0858c8);
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0858c8, stop:1 #064a9f);
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
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: bold;
            font-size: 11px;
            min-height: 14px;
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
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: bold;
            font-size: 11px;
            min-height: 14px;
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
            padding: 6px 12px;
            font-weight: bold;
            font-size: 11px;
            min-height: 14px;
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
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: bold;
            font-size: 11px;
            min-height: 14px;
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

# نمط الجدول الداكن الموحد (Blue Theme) - محسن مع توسيط
TABLE_STYLE_DARK = f"""
    QTableWidget {{
        background-color: {COLORS['bg_dark']};
        alternate-background-color: {COLORS['bg_medium']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        gridline-color: {COLORS['border']};
        selection-background-color: {COLORS['primary']};
        font-size: 11px;
        outline: none;
    }}
    QTableWidget::item {{
        padding: 4px 6px;
        border-bottom: 1px solid {COLORS['border']};
        border: none;
        text-align: center;
    }}
    QTableWidget::item:selected {{
        background-color: {COLORS['primary']};
        color: white;
    }}
    QTableWidget::item:hover {{
        background-color: rgba(10, 108, 241, 0.1);
    }}
    QTableWidget::item:focus {{
        border: none;
        outline: none;
    }}
    QTableWidget QLineEdit {{
        background-color: {COLORS['bg_medium']};
        border: 1px solid {COLORS['primary']};
        border-radius: 3px;
        padding: 2px 4px;
        color: {COLORS['text_primary']};
        font-size: 11px;
    }}
    QTableWidget QSpinBox, QTableWidget QDoubleSpinBox {{
        background-color: {COLORS['bg_medium']};
        border: 1px solid {COLORS['primary']};
        border-radius: 3px;
        padding: 2px 4px;
        color: {COLORS['text_primary']};
        font-size: 11px;
    }}
    QTableWidget QComboBox {{
        background-color: {COLORS['bg_medium']};
        border: 1px solid {COLORS['primary']};
        border-radius: 3px;
        padding: 2px 4px;
        color: {COLORS['text_primary']};
        font-size: 11px;
    }}
    QHeaderView::section {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['header_bg']}, stop:1 #1d4ed8);
        color: white;
        padding: 5px 6px;
        border: none;
        border-right: 1px solid rgba(255,255,255,0.15);
        font-weight: 600;
        font-size: 10px;
        min-height: 14px;
        max-height: 26px;
    }}
    QHeaderView::section:last {{
        border-right: none;
    }}
    QHeaderView {{
        background-color: transparent;
    }}
    QScrollBar:vertical {{
        background-color: {COLORS['bg_medium']};
        width: 8px;
        border-radius: 4px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background-color: {COLORS['primary']};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: #2563eb;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background-color: {COLORS['bg_medium']};
        height: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {COLORS['primary']};
        border-radius: 4px;
        min-width: 30px;
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
        font-family: 'Cairo';
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
        font-family: 'Cairo';
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
    font-family: 'Cairo';
    font-size: 13px;
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
    font-size: 13px;
    font-family: 'Cairo';
}}

/* Toolbar Buttons - استثناء للأزرار في الـ Toolbar */
QToolBar QPushButton {{
    min-height: 24px;
    max-height: 28px;
    min-width: 30px;
    max-width: 100px;
    padding: 4px 8px;
    font-size: 11px;
    border-radius: 4px;
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
    font-size: 13px;
    min-height: 40px;
    text-align: center;
    font-family: 'Cairo';
}}

QTableWidget::item {{
    padding: 12px 10px;
    border-bottom: 1px solid {COLORS['border']};
    border-right: 1px solid rgba(30, 58, 95, 0.5);
    text-align: center;
    min-height: 40px;
    font-size: 13px;
    font-family: 'Cairo';
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

/* === Editor داخل الجدول - يبقى داخل حدود الخلية === */
QTableWidget QLineEdit {{
    background-color: {COLORS['bg_medium']};
    border: 1px solid {COLORS['primary']};
    border-radius: 0px;
    padding: 0px 2px;
    margin: 0px;
    color: #F8FAFC;
    font-size: 13px;
    min-height: 0px;
    max-height: none;
}}

QTableWidget QSpinBox, QTableWidget QDoubleSpinBox {{
    background-color: {COLORS['bg_medium']};
    border: 1px solid {COLORS['primary']};
    border-radius: 0px;
    padding: 0px 2px;
    margin: 0px;
    color: #F8FAFC;
    font-size: 13px;
    min-height: 0px;
    max-height: none;
}}

QTableWidget QSpinBox::up-button, QTableWidget QDoubleSpinBox::up-button,
QTableWidget QSpinBox::down-button, QTableWidget QDoubleSpinBox::down-button {{
    width: 0px;
    height: 0px;
    border: none;
}}

QTableWidget QComboBox {{
    background-color: {COLORS['bg_medium']};
    border: 1px solid {COLORS['primary']};
    border-radius: 0px;
    padding: 0px 2px;
    margin: 0px;
    color: #F8FAFC;
    font-size: 13px;
    min-height: 0px;
    max-height: none;
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
    """تطبيق الأنماط على التطبيق بالكامل مع خط Cairo فقط"""
    import os
    import sys

    from PyQt6.QtGui import QFont, QFontDatabase

    # تحديد المسار الصحيح للخط
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    font_path = os.path.join(base_path, "assets", "font", "Cairo-VariableFont_slnt,wght.ttf")

    # تحميل خط Cairo من الملف
    cairo_font_family = "Cairo"
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                cairo_font_family = font_families[0]
                cairo_font = QFont(cairo_font_family, 13)
                cairo_font.setWeight(QFont.Weight.Normal)
                app.setFont(cairo_font)
                print(f"✅ تم تحميل خط Cairo من: {font_path}")
            else:
                print("⚠️ فشل تحميل خط Cairo")
        else:
            print("⚠️ فشل إضافة خط Cairo")
    else:
        print(f"⚠️ ملف الخط غير موجود: {font_path}")

    # حفظ اسم الخط للاستخدام في الـ stylesheet
    global CAIRO_FONT_FAMILY
    CAIRO_FONT_FAMILY = cairo_font_family

    # تطبيق الأنماط مع خط Cairo
    stylesheet_with_cairo = COMPLETE_STYLESHEET.replace(
        "font-family: 'Cairo';",
        f"font-family: '{cairo_font_family}';"
    )
    app.setStyleSheet(stylesheet_with_cairo)

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


def get_cairo_font(size: int = 13, bold: bool = False):
    """
    الحصول على خط Cairo بالحجم المطلوب
    يستخدم هذه الدالة بدلاً من QFont مباشرة لضمان استخدام خط Cairo فقط
    """
    from PyQt6.QtGui import QFont
    
    font_family = getattr(sys.modules[__name__], 'CAIRO_FONT_FAMILY', 'Cairo')
    font = QFont(font_family, size)
    if bold:
        font.setWeight(QFont.Weight.Bold)
    return font


# متغير عام لحفظ اسم خط Cairo
CAIRO_FONT_FAMILY = "Cairo"


# ============================================================
# 📱 RESPONSIVE UI HELPERS
# ============================================================

def make_dialog_responsive(dialog, min_width: int = 400, min_height: int = 300):
    """
    تحويل أي Dialog إلى تصميم متجاوب (Responsive)
    
    Args:
        dialog: نافذة الحوار
        min_width: الحد الأدنى للعرض
        min_height: الحد الأدنى للارتفاع
    """
    from PyQt6.QtWidgets import QSizePolicy
    
    # إزالة أي حجم ثابت
    dialog.setMinimumWidth(min_width)
    dialog.setMinimumHeight(min_height)
    
    # السماح بالتمدد
    dialog.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    # تطبيق شريط العنوان المخصص
    setup_custom_title_bar(dialog)


def create_scrollable_form(parent=None):
    """
    إنشاء نموذج قابل للتمرير (Scrollable Form)
    
    Returns:
        tuple: (scroll_area, content_widget, content_layout)
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget
    
    # إنشاء منطقة التمرير
    scroll_area = QScrollArea(parent)
    scroll_area.setWidgetResizable(True)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll_area.setStyleSheet(f"""
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}
        QScrollBar:vertical {{
            background-color: {COLORS['bg_medium']};
            width: 10px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {COLORS['primary']};
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: #005BC5;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """)
    
    # إنشاء الـ widget الداخلي
    content_widget = QWidget()
    content_widget.setStyleSheet("background-color: transparent;")
    content_layout = QVBoxLayout(content_widget)
    content_layout.setSpacing(12)
    content_layout.setContentsMargins(15, 15, 15, 15)
    
    scroll_area.setWidget(content_widget)
    
    return scroll_area, content_widget, content_layout


def create_responsive_dialog_layout(dialog, has_scroll: bool = True):
    """
    إنشاء تخطيط متجاوب لنافذة حوار
    
    Args:
        dialog: نافذة الحوار
        has_scroll: هل يحتوي على منطقة تمرير
        
    Returns:
        dict: يحتوي على العناصر المختلفة
    """
    from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
    
    # التخطيط الرئيسي
    main_layout = QVBoxLayout(dialog)
    main_layout.setSpacing(0)
    main_layout.setContentsMargins(0, 0, 0, 0)
    
    result = {
        'main_layout': main_layout,
    }
    
    if has_scroll:
        # منطقة التمرير للمحتوى
        scroll_area, content_widget, content_layout = create_scrollable_form(dialog)
        main_layout.addWidget(scroll_area, 1)  # stretch = 1 للتمدد
        
        result['scroll_area'] = scroll_area
        result['content_widget'] = content_widget
        result['content_layout'] = content_layout
    
    # منطقة الأزرار (ثابتة في الأسفل)
    buttons_container = QWidget()
    buttons_container.setStyleSheet(f"""
        QWidget {{
            background-color: {COLORS['bg_light']};
            border-top: 1px solid {COLORS['border']};
        }}
    """)
    buttons_layout = QHBoxLayout(buttons_container)
    buttons_layout.setContentsMargins(15, 12, 15, 12)
    buttons_layout.setSpacing(10)
    
    main_layout.addWidget(buttons_container)
    
    result['buttons_container'] = buttons_container
    result['buttons_layout'] = buttons_layout
    
    return result


def set_expanding_policy(widget):
    """
    تعيين سياسة التمدد الأفقي للـ widget
    """
    from PyQt6.QtWidgets import QSizePolicy
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


def set_form_field_policies(form_layout):
    """
    تطبيق سياسات التمدد على كل حقول النموذج
    """
    from PyQt6.QtWidgets import QComboBox, QDateEdit, QLineEdit, QSizePolicy, QSpinBox, QTextEdit
    
    for i in range(form_layout.rowCount()):
        field_item = form_layout.itemAt(i, form_layout.ItemRole.FieldRole)
        if field_item and field_item.widget():
            widget = field_item.widget()
            if isinstance(widget, (QLineEdit, QComboBox, QDateEdit, QSpinBox, QTextEdit)):
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


# ============================================================
# 📐 RESPONSIVE GROUPBOX STYLE
# ============================================================

RESPONSIVE_GROUPBOX_STYLE = f"""
    QGroupBox {{
        font-family: 'Cairo', sans-serif;
        font-weight: bold;
        font-size: 13px;
        border: 1px solid {COLORS['border']};
        border-radius: 10px;
        margin-top: 15px;
        padding: 15px 10px 10px 10px;
        color: {COLORS['text_primary']};
        background-color: {COLORS['bg_light']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top right;
        right: 15px;
        padding: 0 8px;
        color: {COLORS['primary']};
        background-color: {COLORS['bg_light']};
    }}
"""


# ============================================================
# 📱 RESPONSIVE TABLE STYLES
# ============================================================

RESPONSIVE_TABLE_STYLE = f"""
    QTableWidget {{
        background-color: {COLORS['bg_dark']};
        alternate-background-color: {COLORS['bg_medium']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        gridline-color: {COLORS['border']};
        selection-background-color: {COLORS['primary']};
        font-size: 13px;
        font-family: 'Cairo';
    }}
    QTableWidget::item {{
        padding: 10px 8px;
        min-height: 38px;
        border-bottom: 1px solid {COLORS['border']};
        text-align: center;
    }}
    QTableWidget::item:selected {{
        background-color: {COLORS['primary']};
        color: white;
    }}
    QTableWidget::item:hover {{
        background-color: rgba(10, 108, 241, 0.15);
    }}
    QHeaderView::section {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['primary']}, stop:1 #005BC5);
        color: white;
        padding: 12px 8px;
        border: none;
        border-right: 1px solid rgba(255,255,255,0.2);
        font-weight: bold;
        font-size: 13px;
        min-height: 35px;
        text-align: center;
        font-family: 'Cairo';
    }}
    QScrollBar:vertical {{
        background-color: {COLORS['bg_medium']};
        width: 10px;
        border-radius: 5px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {COLORS['primary']};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: #005BC5;
    }}
    QScrollBar:horizontal {{
        background-color: {COLORS['bg_medium']};
        height: 10px;
        border-radius: 5px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {COLORS['primary']};
        border-radius: 5px;
        min-width: 30px;
    }}
"""

# ============================================================
# 📱 RESPONSIVE BUTTON STYLES
# ============================================================

RESPONSIVE_BUTTON_STYLE = f"""
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['primary']}, stop:1 #005BC5);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        min-height: 36px;
        min-width: 100px;
        font-weight: bold;
        font-size: 13px;
        font-family: 'Cairo';
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
"""

# ============================================================
# 📱 RESPONSIVE INPUT STYLES
# ============================================================

RESPONSIVE_INPUT_STYLE = f"""
    QLineEdit, QTextEdit {{
        background-color: {COLORS['bg_medium']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 8px 12px;
        min-height: 32px;
        color: {COLORS['text_primary']};
        font-size: 13px;
        font-family: 'Cairo';
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border: 2px solid {COLORS['primary']};
    }}
    QLineEdit:hover, QTextEdit:hover {{
        border: 1px solid {COLORS['primary']};
    }}
    QComboBox {{
        background-color: {COLORS['bg_medium']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 8px 12px;
        min-height: 32px;
        min-width: 120px;
        color: {COLORS['text_primary']};
        font-size: 13px;
        font-family: 'Cairo';
    }}
    QComboBox:focus {{
        border: 2px solid {COLORS['primary']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 25px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLORS['bg_medium']};
        color: {COLORS['text_primary']};
        selection-background-color: {COLORS['primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
    }}
    QSpinBox, QDoubleSpinBox {{
        background-color: {COLORS['bg_medium']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 8px 12px;
        min-height: 32px;
        color: {COLORS['text_primary']};
        font-size: 13px;
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 2px solid {COLORS['primary']};
    }}
    QDateEdit {{
        background-color: {COLORS['bg_medium']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 8px 12px;
        min-height: 32px;
        color: {COLORS['text_primary']};
        font-size: 13px;
    }}
    QDateEdit:focus {{
        border: 2px solid {COLORS['primary']};
    }}
    QDateEdit::drop-down {{
        border: none;
        width: 25px;
    }}
"""

# ============================================================
# 📱 RESPONSIVE DIALOG STYLE
# ============================================================

RESPONSIVE_DIALOG_STYLE = f"""
    QDialog {{
        background-color: {COLORS['bg_dark']};
        color: {COLORS['text_primary']};
        font-family: 'Cairo';
    }}
    QDialog QLabel {{
        color: {COLORS['text_primary']};
        font-size: 13px;
        background: transparent;
    }}
    QDialog QGroupBox {{
        font-weight: bold;
        font-size: 13px;
        border: 1px solid {COLORS['border']};
        border-radius: 10px;
        margin-top: 15px;
        padding: 15px 10px 10px 10px;
        color: {COLORS['text_primary']};
        background-color: {COLORS['bg_light']};
    }}
    QDialog QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top right;
        right: 15px;
        padding: 0 8px;
        color: {COLORS['primary']};
        background-color: {COLORS['bg_light']};
    }}
"""

# ============================================================
# 📱 RESPONSIVE TAB STYLE
# ============================================================

RESPONSIVE_TAB_STYLE = f"""
    QTabWidget::pane {{
        border: 1px solid {COLORS['border']};
        background-color: {COLORS['bg_dark']};
        border-radius: 8px;
        padding: 5px;
    }}
    QTabBar::tab {{
        background-color: {COLORS['bg_light']};
        color: {COLORS['text_secondary']};
        padding: 10px 18px;
        margin: 2px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        font-size: 13px;
        font-weight: bold;
        min-width: 100px;
        font-family: 'Cairo';
    }}
    QTabBar::tab:hover {{
        background-color: rgba(10, 108, 241, 0.2);
        color: {COLORS['text_primary']};
    }}
    QTabBar::tab:selected {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLORS['primary']}, stop:1 #005BC5);
        color: white;
    }}
    QTabBar::tab:!selected {{
        margin-top: 3px;
    }}
"""


# ============================================================
# 📱 HELPER FUNCTIONS FOR RESPONSIVE UI
# ============================================================

def setup_responsive_table(table, stretch_columns: list = None, fixed_columns: dict = None):
    """
    إعداد جدول متجاوب مع الشاشة
    
    Args:
        table: QTableWidget
        stretch_columns: قائمة بأرقام الأعمدة التي تتمدد
        fixed_columns: قاموس {رقم_العمود: العرض} للأعمدة الثابتة
    """
    from PyQt6.QtWidgets import QHeaderView, QSizePolicy
    
    # تطبيق الستايل
    table.setStyleSheet(RESPONSIVE_TABLE_STYLE)
    
    # سياسة التمدد
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    # إعداد الأعمدة
    header = table.horizontalHeader()
    if header:
        # الأعمدة المتمددة
        if stretch_columns:
            for col in stretch_columns:
                if col < table.columnCount():
                    header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        
        # الأعمدة الثابتة
        if fixed_columns:
            for col, width in fixed_columns.items():
                if col < table.columnCount():
                    table.setColumnWidth(col, width)
                    header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        
        # توسيط العناوين
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
    
    # إعدادات إضافية
    table.setAlternatingRowColors(True)
    table.verticalHeader().setDefaultSectionSize(42)
    table.setShowGrid(True)


def setup_responsive_dialog(dialog, min_width: int = 450, min_height: int = 400, 
                           screen_ratio: float = 0.7):
    """
    إعداد نافذة حوار متجاوبة
    
    Args:
        dialog: QDialog
        min_width: الحد الأدنى للعرض
        min_height: الحد الأدنى للارتفاع
        screen_ratio: نسبة حجم النافذة من الشاشة (0.0 - 1.0)
    """
    from PyQt6.QtWidgets import QApplication, QSizePolicy
    
    # الحد الأدنى
    dialog.setMinimumWidth(min_width)
    dialog.setMinimumHeight(min_height)
    
    # سياسة التمدد
    dialog.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    # حجم متجاوب مع الشاشة
    screen = QApplication.primaryScreen()
    if screen:
        screen_size = screen.availableGeometry()
        width = int(screen_size.width() * screen_ratio)
        height = int(screen_size.height() * screen_ratio)
        
        # لا تتجاوز الحد الأقصى المعقول
        width = min(width, 1400)
        height = min(height, 900)
        
        dialog.resize(width, height)
        
        # توسيط النافذة
        x = (screen_size.width() - width) // 2
        y = (screen_size.height() - height) // 2
        dialog.move(x, y)
    
    # تطبيق الستايل
    dialog.setStyleSheet(RESPONSIVE_DIALOG_STYLE)
    
    # شريط العنوان المخصص
    setup_custom_title_bar(dialog)


def create_action_buttons(parent_layout, buttons_config: list, alignment: str = "right"):
    """
    إنشاء أزرار الإجراءات بشكل موحد
    
    Args:
        parent_layout: التخطيط الأب
        buttons_config: قائمة من القواميس [{"text": "حفظ", "style": "primary", "callback": func}, ...]
        alignment: محاذاة الأزرار ("right", "left", "center")
    
    Returns:
        dict: قاموس بالأزرار {text: button}
    """
    from PyQt6.QtWidgets import QHBoxLayout, QPushButton
    
    buttons_layout = QHBoxLayout()
    buttons_layout.setSpacing(10)
    
    if alignment == "right":
        buttons_layout.addStretch()
    elif alignment == "center":
        buttons_layout.addStretch()
    
    buttons = {}
    for config in buttons_config:
        btn = QPushButton(config.get("text", ""))
        
        # تطبيق الستايل
        style_name = config.get("style", "primary")
        if style_name in BUTTON_STYLES:
            btn.setStyleSheet(BUTTON_STYLES[style_name])
        else:
            btn.setStyleSheet(RESPONSIVE_BUTTON_STYLE)
        
        # الحد الأدنى للعرض
        btn.setMinimumWidth(config.get("min_width", 100))
        
        # ربط الحدث
        if "callback" in config and config["callback"]:
            btn.clicked.connect(config["callback"])
        
        buttons_layout.addWidget(btn)
        buttons[config.get("text", "")] = btn
    
    if alignment == "center":
        buttons_layout.addStretch()
    
    parent_layout.addLayout(buttons_layout)
    return buttons


def apply_responsive_styles_to_widget(widget):
    """
    تطبيق أنماط التجاوب على widget وكل أطفاله
    """
    from PyQt6.QtWidgets import (
        QComboBox, QDateEdit, QDialog, QDoubleSpinBox, QGroupBox,
        QLineEdit, QPushButton, QSpinBox, QTableWidget, QTabWidget, QTextEdit
    )
    
    # تطبيق على الـ widget نفسه
    if isinstance(widget, QDialog):
        widget.setStyleSheet(widget.styleSheet() + RESPONSIVE_DIALOG_STYLE)
    elif isinstance(widget, QTableWidget):
        widget.setStyleSheet(RESPONSIVE_TABLE_STYLE)
    elif isinstance(widget, QTabWidget):
        widget.setStyleSheet(RESPONSIVE_TAB_STYLE)
    elif isinstance(widget, QGroupBox):
        widget.setStyleSheet(RESPONSIVE_GROUPBOX_STYLE)
    
    # تطبيق على الأطفال
    for child in widget.findChildren(QTableWidget):
        child.setStyleSheet(RESPONSIVE_TABLE_STYLE)
    
    for child in widget.findChildren(QTabWidget):
        child.setStyleSheet(RESPONSIVE_TAB_STYLE)
    
    for child in widget.findChildren(QGroupBox):
        child.setStyleSheet(RESPONSIVE_GROUPBOX_STYLE)


# ============================================================
# 📱 SCREEN SIZE UTILITIES
# ============================================================

def get_screen_size():
    """
    الحصول على حجم الشاشة المتاح
    
    Returns:
        tuple: (width, height)
    """
    from PyQt6.QtWidgets import QApplication
    
    screen = QApplication.primaryScreen()
    if screen:
        geometry = screen.availableGeometry()
        return geometry.width(), geometry.height()
    return 1920, 1080  # قيمة افتراضية


def calculate_responsive_size(base_width: int, base_height: int, 
                             min_ratio: float = 0.5, max_ratio: float = 0.9):
    """
    حساب حجم متجاوب بناءً على حجم الشاشة
    
    Args:
        base_width: العرض الأساسي المطلوب
        base_height: الارتفاع الأساسي المطلوب
        min_ratio: الحد الأدنى لنسبة الشاشة
        max_ratio: الحد الأقصى لنسبة الشاشة
    
    Returns:
        tuple: (width, height)
    """
    screen_width, screen_height = get_screen_size()
    
    # حساب النسبة المثالية
    width_ratio = base_width / screen_width
    height_ratio = base_height / screen_height
    
    # تطبيق الحدود
    width_ratio = max(min_ratio, min(max_ratio, width_ratio))
    height_ratio = max(min_ratio, min(max_ratio, height_ratio))
    
    return int(screen_width * width_ratio), int(screen_height * height_ratio)


# ============================================================
# 📊 TABLE HELPERS - دوال مساعدة للجداول
# ============================================================

def create_centered_item(text, background_color=None):
    """
    إنشاء عنصر جدول مع توسيط النص
    
    Args:
        text: النص المراد عرضه
        background_color: لون الخلفية (اختياري) - يمكن أن يكون Qt.GlobalColor أو QColor
        
    Returns:
        QTableWidgetItem: عنصر الجدول مع التوسيط
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTableWidgetItem
    
    item = QTableWidgetItem(str(text) if text is not None else "")
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
    
    if background_color:
        item.setBackground(background_color)
    
    return item


def center_all_table_items(table):
    """
    توسيط جميع عناصر الجدول الموجودة
    
    Args:
        table: QTableWidget المراد توسيط عناصره
    """
    from PyQt6.QtCore import Qt
    
    # توسيط العناوين
    header = table.horizontalHeader()
    if header:
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
    
    # توسيط كل الخلايا
    for row in range(table.rowCount()):
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)


def setup_professional_table(table, style=None, rtl_fix=True):
    """
    إعداد جدول احترافي مع التوسيط والستايل
    
    Args:
        table: QTableWidget المراد إعداده
        style: الستايل المراد تطبيقه (اختياري، الافتراضي TABLE_STYLE_DARK)
        rtl_fix: إصلاح مشكلة انعكاس الأعمدة في RTL (الافتراضي True)
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTableWidget
    
    # تطبيق الستايل
    if style is None:
        style = TABLE_STYLE_DARK
    table.setStyleSheet(style)
    
    # إصلاح مشكلة انعكاس الأعمدة في RTL
    # الجدول يجب أن يكون LTR حتى لا تنعكس الأعمدة
    if rtl_fix:
        table.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        # لكن العناوين تبقى RTL للنص العربي
        header = table.horizontalHeader()
        if header:
            header.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    
    # إعدادات الجدول
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    
    # توسيط العناوين
    header = table.horizontalHeader()
    if header:
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
    
    # توسيط العناصر الموجودة
    center_all_table_items(table)


def fix_table_rtl(table):
    """
    إصلاح مشكلة انعكاس الأعمدة في الجداول مع RTL
    مع الحفاظ على محاذاة النص العربي
    
    Args:
        table: QTableWidget المراد إصلاحه
    """
    from PyQt6.QtCore import Qt
    
    # الجدول بالكامل يكون LTR لمنع انعكاس الأعمدة
    table.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    
    # الـ header يكون LTR لضمان ترتيب الأعمدة الصحيح
    # لكن النص يكون في الوسط
    header = table.horizontalHeader()
    if header:
        header.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
    
    # الـ vertical header
    v_header = table.verticalHeader()
    if v_header:
        v_header.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
