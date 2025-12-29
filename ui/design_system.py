# الملف: ui/design_system.py
"""
🎨 نظام التصميم الموحد (Design System) لتطبيق Sky Wave ERP
يوفر تجربة مستخدم متسقة ومتجاوبة على جميع أحجام الشاشات
"""

import os
import sys
from enum import Enum
from typing import Optional, Tuple

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


def _get_asset_path_ds(filename):
    """الحصول على المسار الصحيح للـ assets"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "assets", filename).replace("\\", "/")


# ============================================================
# 📐 SPACING & SIZING TOKENS
# ============================================================

class Spacing:
    """نظام المسافات الموحد"""
    NONE = 0
    XS = 4      # مسافة صغيرة جداً
    SM = 8      # مسافة صغيرة
    MD = 12     # مسافة متوسطة
    LG = 16     # مسافة كبيرة
    XL = 24     # مسافة كبيرة جداً
    XXL = 32    # مسافة ضخمة
    XXXL = 48   # مسافة ضخمة جداً


class ComponentSize(Enum):
    """أحجام المكونات الموحدة"""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# أحجام الأزرار حسب الحجم
BUTTON_SIZES = {
    ComponentSize.SMALL: {"min_height": 32, "min_width": 80, "padding": "8px 16px", "font_size": 12},
    ComponentSize.MEDIUM: {"min_height": 40, "min_width": 100, "padding": "10px 20px", "font_size": 14},
    ComponentSize.LARGE: {"min_height": 48, "min_width": 120, "padding": "14px 28px", "font_size": 16},
}

# أحجام الحقول حسب الحجم
INPUT_SIZES = {
    ComponentSize.SMALL: {"min_height": 32, "padding": "6px 10px", "font_size": 12},
    ComponentSize.MEDIUM: {"min_height": 40, "padding": "10px 14px", "font_size": 14},
    ComponentSize.LARGE: {"min_height": 48, "padding": "12px 16px", "font_size": 16},
}


# ============================================================
# 📱 BREAKPOINTS للتجاوب مع أحجام الشاشات
# ============================================================

class Breakpoints:
    """نقاط التوقف لأحجام الشاشات المختلفة"""
    MOBILE = 480      # هواتف
    TABLET = 768      # أجهزة لوحية
    LAPTOP = 1024     # لابتوب صغير
    DESKTOP = 1280    # سطح مكتب
    LARGE = 1440      # شاشة كبيرة
    XLARGE = 1920     # شاشة كبيرة جداً


def get_screen_category() -> str:
    """تحديد فئة الشاشة الحالية"""
    screen = QApplication.primaryScreen()
    if not screen:
        return "desktop"
    
    width = screen.availableGeometry().width()
    
    if width < Breakpoints.TABLET:
        return "mobile"
    elif width < Breakpoints.LAPTOP:
        return "tablet"
    elif width < Breakpoints.DESKTOP:
        return "laptop"
    elif width < Breakpoints.LARGE:
        return "desktop"
    else:
        return "large"


def get_responsive_value(mobile: int, tablet: int, desktop: int, large: int = None) -> int:
    """الحصول على قيمة متجاوبة حسب حجم الشاشة"""
    category = get_screen_category()
    
    if large is None:
        large = desktop
    
    values = {
        "mobile": mobile,
        "tablet": tablet,
        "laptop": desktop,
        "desktop": desktop,
        "large": large,
    }
    
    return values.get(category, desktop)


# ============================================================
# 🎨 COLORS - ألوان النظام
# ============================================================

class Colors:
    """ألوان SkyWave Brand Identity"""
    # Primary Colors
    PRIMARY = "#0A6CF1"
    PRIMARY_HOVER = "#2563eb"
    PRIMARY_DARK = "#1d4ed8"
    PRIMARY_LIGHT = "#60a5fa"
    
    # Accent Colors
    SUCCESS = "#10b981"
    WARNING = "#FF6636"
    DANGER = "#FF4FD8"
    INFO = "#8B2CF5"
    
    # Background Colors
    BG_DARK = "#001A3A"
    BG_MEDIUM = "#0A2A55"
    BG_LIGHT = "#052045"
    BG_CARD = "#001A3A"
    
    # Text Colors
    TEXT_PRIMARY = "#EAF3FF"
    TEXT_SECONDARY = "#B0C4DE"
    TEXT_MUTED = "#6B7280"
    
    # Border Colors
    BORDER = "#1E3A5F"
    BORDER_LIGHT = "#374151"
    
    # Header
    HEADER_BG = "#052045"


# ============================================================
# 📝 TYPOGRAPHY - نظام الخطوط
# ============================================================

class Typography:
    """نظام الخطوط الموحد"""
    FONT_FAMILY = "Cairo"
    
    # أحجام الخطوط المتجاوبة
    @staticmethod
    def get_font_size(level: str) -> int:
        """الحصول على حجم الخط المتجاوب"""
        sizes = {
            "h1": get_responsive_value(20, 24, 28, 32),
            "h2": get_responsive_value(18, 20, 24, 26),
            "h3": get_responsive_value(16, 18, 20, 22),
            "h4": get_responsive_value(14, 16, 18, 20),
            "body": get_responsive_value(12, 13, 14, 15),
            "small": get_responsive_value(10, 11, 12, 13),
            "caption": get_responsive_value(9, 10, 11, 12),
        }
        return sizes.get(level, 14)
    
    @staticmethod
    def get_font(level: str = "body", bold: bool = False) -> QFont:
        """الحصول على خط بالحجم المطلوب"""
        font = QFont(Typography.FONT_FAMILY, Typography.get_font_size(level))
        if bold:
            font.setWeight(QFont.Weight.Bold)
        return font


# ============================================================
# 📦 LAYOUT HELPERS - مساعدات التخطيط
# ============================================================

class ResponsiveLayout:
    """مساعدات إنشاء تخطيطات متجاوبة"""
    
    @staticmethod
    def create_vbox(
        spacing: int = Spacing.MD,
        margins: Tuple[int, int, int, int] = None
    ) -> QVBoxLayout:
        """إنشاء تخطيط عمودي متجاوب"""
        layout = QVBoxLayout()
        layout.setSpacing(spacing)
        
        if margins:
            layout.setContentsMargins(*margins)
        else:
            # هوامش متجاوبة
            margin = get_responsive_value(8, 12, 16, 20)
            layout.setContentsMargins(margin, margin, margin, margin)
        
        return layout
    
    @staticmethod
    def create_hbox(
        spacing: int = Spacing.MD,
        margins: Tuple[int, int, int, int] = None
    ) -> QHBoxLayout:
        """إنشاء تخطيط أفقي متجاوب"""
        layout = QHBoxLayout()
        layout.setSpacing(spacing)
        
        if margins:
            layout.setContentsMargins(*margins)
        else:
            margin = get_responsive_value(8, 12, 16, 20)
            layout.setContentsMargins(margin, margin, margin, margin)
        
        return layout
    
    @staticmethod
    def create_grid(
        columns: int = 2,
        h_spacing: int = Spacing.MD,
        v_spacing: int = Spacing.MD
    ) -> QGridLayout:
        """إنشاء تخطيط شبكي متجاوب"""
        layout = QGridLayout()
        layout.setHorizontalSpacing(h_spacing)
        layout.setVerticalSpacing(v_spacing)
        
        margin = get_responsive_value(8, 12, 16, 20)
        layout.setContentsMargins(margin, margin, margin, margin)
        
        return layout
    
    @staticmethod
    def create_form_layout(parent: QWidget = None) -> QVBoxLayout:
        """إنشاء تخطيط نموذج متجاوب"""
        layout = QVBoxLayout(parent)
        layout.setSpacing(get_responsive_value(10, 12, 15, 18))
        
        margin = get_responsive_value(12, 16, 20, 24)
        layout.setContentsMargins(margin, margin, margin, margin)
        
        return layout


# ============================================================
# 🔘 BUTTON FACTORY - مصنع الأزرار الموحدة
# ============================================================

class ButtonFactory:
    """مصنع إنشاء أزرار موحدة ومتجاوبة"""
    
    @staticmethod
    def get_button_style(
        variant: str = "primary",
        size: ComponentSize = ComponentSize.MEDIUM
    ) -> str:
        """الحصول على ستايل الزر"""
        
        size_config = BUTTON_SIZES[size]
        
        # ألوان حسب النوع
        colors = {
            "primary": {
                "bg": f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Colors.PRIMARY}, stop:1 #005BC5)",
                "bg_hover": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #005BC5, stop:1 #004A9F)",
                "text": "#FFFFFF",
            },
            "success": {
                "bg": f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Colors.SUCCESS}, stop:1 #059669)",
                "bg_hover": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #059669, stop:1 #047857)",
                "text": "#FFFFFF",
            },
            "warning": {
                "bg": f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Colors.WARNING}, stop:1 #d97706)",
                "bg_hover": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #d97706, stop:1 #b45309)",
                "text": "#FFFFFF",
            },
            "danger": {
                "bg": f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Colors.DANGER}, stop:1 #D430B0)",
                "bg_hover": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #D430B0, stop:1 #B01090)",
                "text": "#FFFFFF",
            },
            "secondary": {
                "bg": f"{Colors.BG_MEDIUM}",
                "bg_hover": "#1E3A5F",
                "text": Colors.TEXT_PRIMARY,
            },
            "ghost": {
                "bg": "transparent",
                "bg_hover": "rgba(10, 108, 241, 0.1)",
                "text": Colors.PRIMARY,
            },
        }
        
        color_config = colors.get(variant, colors["primary"])
        
        return f"""
            QPushButton {{
                background: {color_config['bg']};
                color: {color_config['text']};
                border: none;
                border-radius: 8px;
                padding: {size_config['padding']};
                min-height: {size_config['min_height']}px;
                min-width: {size_config['min_width']}px;
                font-weight: bold;
                font-size: {size_config['font_size']}px;
                font-family: '{Typography.FONT_FAMILY}';
            }}
            QPushButton:hover {{
                background: {color_config['bg_hover']};
            }}
            QPushButton:pressed {{
                background: {color_config['bg_hover']};
                padding-top: 2px;
            }}
            QPushButton:disabled {{
                background-color: #4b5563;
                color: #9ca3af;
            }}
        """
    
    @staticmethod
    def create_button(
        text: str,
        variant: str = "primary",
        size: ComponentSize = ComponentSize.MEDIUM,
        icon: str = None,
        parent: QWidget = None
    ) -> QPushButton:
        """إنشاء زر موحد"""
        btn = QPushButton(text, parent)
        btn.setStyleSheet(ButtonFactory.get_button_style(variant, size))
        btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn


# ============================================================
# 📝 INPUT FACTORY - مصنع الحقول الموحدة
# ============================================================

class InputFactory:
    """مصنع إنشاء حقول إدخال موحدة ومتجاوبة"""
    
    @staticmethod
    def get_input_style(size: ComponentSize = ComponentSize.MEDIUM) -> str:
        """الحصول على ستايل الحقل"""
        
        size_config = INPUT_SIZES[size]
        
        return f"""
            QLineEdit, QTextEdit {{
                background-color: {Colors.BG_MEDIUM};
                border: 2px solid {Colors.BORDER};
                border-radius: 8px;
                padding: {size_config['padding']};
                min-height: {size_config['min_height']}px;
                color: {Colors.TEXT_PRIMARY};
                font-size: {size_config['font_size']}px;
                font-family: '{Typography.FONT_FAMILY}';
            }}
            QSpinBox, QDoubleSpinBox, QDateEdit {{
                background-color: {Colors.BG_MEDIUM};
                border: 2px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 8px 10px 8px 28px;
                min-height: {size_config['min_height']}px;
                color: {Colors.TEXT_PRIMARY};
                font-size: {size_config['font_size']}px;
                font-family: '{Typography.FONT_FAMILY}';
            }}
            QComboBox {{
                background-color: {Colors.BG_MEDIUM};
                border: 2px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 8px 10px 8px 28px;
                min-height: {size_config['min_height']}px;
                color: {Colors.TEXT_PRIMARY};
                font-size: {size_config['font_size']}px;
                font-family: '{Typography.FONT_FAMILY}';
            }}
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, 
            QDoubleSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
                border: 2px solid {Colors.PRIMARY};
            }}
            QLineEdit:hover, QTextEdit:hover, QSpinBox:hover,
            QDoubleSpinBox:hover, QDateEdit:hover, QComboBox:hover {{
                border: 2px solid {Colors.PRIMARY_LIGHT};
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button, QDateEdit::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top left;
                width: 22px; height: 14px;
                background: {Colors.BG_LIGHT};
                border: none;
                border-top-left-radius: 6px;
            }}
            QSpinBox::down-button, QDoubleSpinBox::down-button, QDateEdit::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom left;
                width: 22px; height: 14px;
                background: {Colors.BG_LIGHT};
                border: none;
                border-bottom-left-radius: 6px;
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QDateEdit::up-arrow {{
                image: url({_get_asset_path_ds("up-arrow.png")});
                width: 10px; height: 10px;
            }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QDateEdit::down-arrow {{
                image: url({_get_asset_path_ds("down-arrow.png")});
                width: 10px; height: 10px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 24px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({_get_asset_path_ds("down-arrow.png")});
                width: 10px; height: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.BG_MEDIUM};
                color: {Colors.TEXT_PRIMARY};
                selection-background-color: {Colors.PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 5px;
            }}
        """
    
    @staticmethod
    def get_label_style(level: str = "body", bold: bool = True) -> str:
        """الحصول على ستايل التسمية"""
        font_size = Typography.get_font_size(level)
        weight = "bold" if bold else "normal"
        
        return f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: {font_size}px;
                font-weight: {weight};
                font-family: '{Typography.FONT_FAMILY}';
                background: transparent;
                padding: 4px 0px;
            }}
        """


# ============================================================
# 📦 CARD & CONTAINER STYLES
# ============================================================

class ContainerFactory:
    """مصنع إنشاء حاويات موحدة"""
    
    @staticmethod
    def get_card_style() -> str:
        """ستايل البطاقة"""
        return f"""
            QFrame {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
                padding: {get_responsive_value(12, 16, 20, 24)}px;
            }}
        """
    
    @staticmethod
    def get_groupbox_style() -> str:
        """ستايل مجموعة العناصر"""
        padding = get_responsive_value(15, 18, 22, 26)
        margin_top = get_responsive_value(15, 18, 20, 24)
        font_size = Typography.get_font_size("h4")
        
        return f"""
            QGroupBox {{
                font-family: '{Typography.FONT_FAMILY}';
                font-weight: bold;
                font-size: {font_size}px;
                border: 2px solid {Colors.BORDER};
                border-radius: 12px;
                margin-top: {margin_top}px;
                padding: {padding}px {padding - 3}px {padding - 5}px {padding - 3}px;
                color: {Colors.TEXT_PRIMARY};
                background-color: {Colors.BG_LIGHT};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top right;
                right: 15px;
                padding: 2px 12px;
                color: {Colors.PRIMARY};
                background-color: {Colors.BG_LIGHT};
                font-size: {font_size}px;
                font-weight: bold;
            }}
        """
    
    @staticmethod
    def create_card(parent: QWidget = None) -> QFrame:
        """إنشاء بطاقة"""
        card = QFrame(parent)
        card.setStyleSheet(ContainerFactory.get_card_style())
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return card
    
    @staticmethod
    def create_groupbox(title: str, parent: QWidget = None) -> QGroupBox:
        """إنشاء مجموعة عناصر"""
        group = QGroupBox(title, parent)
        group.setStyleSheet(ContainerFactory.get_groupbox_style())
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return group


# ============================================================
# 📊 TABLE STYLES
# ============================================================

class TableFactory:
    """مصنع إنشاء جداول موحدة"""
    
    @staticmethod
    def get_table_style() -> str:
        """ستايل الجدول المتجاوب"""
        header_height = get_responsive_value(36, 40, 44, 48)
        row_height = get_responsive_value(38, 42, 46, 50)
        font_size = Typography.get_font_size("body")
        header_font_size = Typography.get_font_size("body")
        
        return f"""
            QTableWidget {{
                background-color: {Colors.BG_DARK};
                alternate-background-color: {Colors.BG_MEDIUM};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
                gridline-color: {Colors.BORDER};
                selection-background-color: {Colors.PRIMARY};
                font-size: {font_size}px;
                font-family: '{Typography.FONT_FAMILY}';
            }}
            QTableWidget::item {{
                padding: 10px 8px;
                min-height: {row_height}px;
                border-bottom: 1px solid {Colors.BORDER};
                text-align: center;
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.PRIMARY};
                color: white;
            }}
            QTableWidget::item:hover {{
                background-color: rgba(10, 108, 241, 0.15);
            }}
            QHeaderView::section {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {Colors.PRIMARY}, stop:1 #005BC5);
                color: white;
                padding: 12px 8px;
                border: none;
                border-right: 1px solid rgba(255,255,255,0.2);
                font-weight: bold;
                font-size: {header_font_size}px;
                min-height: {header_height}px;
                text-align: center;
                font-family: '{Typography.FONT_FAMILY}';
            }}
            QScrollBar:vertical {{
                background-color: {Colors.BG_MEDIUM};
                width: 10px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {Colors.PRIMARY};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #005BC5;
            }}
            QScrollBar:horizontal {{
                background-color: {Colors.BG_MEDIUM};
                height: 10px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {Colors.PRIMARY};
                border-radius: 5px;
                min-width: 30px;
            }}
        """


# ============================================================
# 🗂️ TAB STYLES
# ============================================================

class TabFactory:
    """مصنع إنشاء تابات موحدة"""
    
    @staticmethod
    def get_tab_style() -> str:
        """ستايل التابات المتجاوب"""
        tab_padding = get_responsive_value(10, 12, 14, 16)
        tab_min_width = get_responsive_value(100, 110, 120, 140)
        font_size = Typography.get_font_size("body")
        
        return f"""
            QTabWidget::pane {{
                border: 2px solid {Colors.BORDER};
                background-color: {Colors.BG_DARK};
                border-radius: 10px;
                padding: 10px;
            }}
            QTabBar::tab {{
                background-color: {Colors.BG_LIGHT};
                color: {Colors.TEXT_SECONDARY};
                padding: {tab_padding}px {tab_padding + 8}px;
                margin: 3px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                font-size: {font_size}px;
                font-weight: bold;
                min-width: {tab_min_width}px;
                font-family: '{Typography.FONT_FAMILY}';
            }}
            QTabBar::tab:hover {{
                background-color: rgba(10, 108, 241, 0.2);
                color: {Colors.TEXT_PRIMARY};
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {Colors.PRIMARY}, stop:1 #005BC5);
                color: white;
            }}
            QTabBar::tab:!selected {{
                margin-top: 4px;
            }}
        """


# ============================================================
# 🖼️ DIALOG FACTORY - مصنع النوافذ المنبثقة
# ============================================================

class DialogFactory:
    """مصنع إنشاء نوافذ منبثقة متجاوبة"""
    
    @staticmethod
    def get_dialog_style() -> str:
        """ستايل النافذة المنبثقة المتجاوب"""
        input_height = get_responsive_value(36, 40, 44, 48)
        button_height = get_responsive_value(38, 42, 46, 50)
        font_size = Typography.get_font_size("body")
        label_font_size = Typography.get_font_size("body")
        
        return f"""
            QDialog {{
                background-color: {Colors.BG_DARK};
                color: {Colors.TEXT_PRIMARY};
                font-family: '{Typography.FONT_FAMILY}';
                font-size: {font_size}px;
            }}
            
            QDialog QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: {label_font_size}px;
                font-weight: bold;
                background: transparent;
                padding: 6px 0px;
                min-height: 28px;
            }}
            
            QDialog QLineEdit, QDialog QComboBox, QDialog QDateEdit {{
                min-height: {input_height}px;
                padding: 10px 14px;
                margin-bottom: 8px;
                background-color: {Colors.BG_MEDIUM};
                border: 2px solid {Colors.BORDER};
                border-radius: 8px;
                color: {Colors.TEXT_PRIMARY};
                font-size: {font_size}px;
            }}
            
            QDialog QLineEdit:focus, QDialog QComboBox:focus, QDialog QDateEdit:focus {{
                border: 2px solid {Colors.PRIMARY};
            }}
            
            QDialog QTextEdit {{
                min-height: 80px;
                padding: 12px 14px;
                margin-bottom: 8px;
                background-color: {Colors.BG_MEDIUM};
                border: 2px solid {Colors.BORDER};
                border-radius: 8px;
                color: {Colors.TEXT_PRIMARY};
                font-size: {font_size}px;
            }}
            
            QDialog QTextEdit:focus {{
                border: 2px solid {Colors.PRIMARY};
            }}
            
            QDialog QSpinBox, QDialog QDoubleSpinBox {{
                min-height: {input_height}px;
                padding: 10px 14px;
                margin-bottom: 8px;
                background-color: {Colors.BG_MEDIUM};
                border: 2px solid {Colors.BORDER};
                border-radius: 8px;
                color: {Colors.TEXT_PRIMARY};
                font-size: {font_size}px;
            }}
            
            QDialog QPushButton {{
                min-height: {button_height}px;
                padding: 12px 24px;
                margin: 5px 3px;
                border-radius: 8px;
                font-weight: bold;
                font-size: {font_size}px;
            }}
            
            QDialog QCheckBox {{
                min-height: 32px;
                font-size: {font_size}px;
                font-weight: bold;
                padding: 8px 0px;
                spacing: 10px;
                color: {Colors.TEXT_PRIMARY};
            }}
            
            QDialog QGroupBox {{
                font-weight: bold;
                font-size: {Typography.get_font_size('h4')}px;
                border: 2px solid {Colors.BORDER};
                border-radius: 12px;
                margin-top: 20px;
                padding: 22px 15px 15px 15px;
                color: {Colors.TEXT_PRIMARY};
                background-color: {Colors.BG_LIGHT};
            }}
            
            QDialog QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top right;
                right: 15px;
                padding: 0 10px;
                color: {Colors.PRIMARY};
                background-color: {Colors.BG_LIGHT};
            }}
        """
    
    @staticmethod
    def setup_responsive_dialog(
        dialog: QDialog,
        min_width: int = 450,
        min_height: int = 400,
        screen_ratio: float = 0.7
    ):
        """إعداد نافذة منبثقة متجاوبة"""
        
        # تطبيق الستايل
        dialog.setStyleSheet(DialogFactory.get_dialog_style())
        
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
            
            # حدود معقولة
            width = min(max(width, min_width), 1400)
            height = min(max(height, min_height), 900)
            
            dialog.resize(width, height)
            
            # توسيط النافذة
            x = (screen_size.width() - width) // 2
            y = (screen_size.height() - height) // 2
            dialog.move(x, y)
        
        # تعديل الحجم تلقائياً
        dialog.adjustSize()


# ============================================================
# 📱 RESPONSIVE WIDGET WRAPPER
# ============================================================

class ResponsiveWidget(QWidget):
    """Widget أساسي متجاوب يمكن وراثته"""
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._setup_responsive()
    
    def _setup_responsive(self):
        """إعداد التجاوب الأساسي"""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # تطبيق الستايل الأساسي
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_DARK};
                color: {Colors.TEXT_PRIMARY};
                font-family: '{Typography.FONT_FAMILY}';
            }}
        """)


class ResponsiveScrollArea(QScrollArea):
    """منطقة تمرير متجاوبة"""
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._setup()
    
    def _setup(self):
        """إعداد منطقة التمرير"""
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background-color: {Colors.BG_MEDIUM};
                width: 10px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {Colors.PRIMARY};
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


# ============================================================
# 🛠️ UTILITY FUNCTIONS
# ============================================================

def apply_design_system(app: QApplication):
    """تطبيق نظام التصميم على التطبيق بالكامل"""
    
    # تحميل الخط
    from core.resource_utils import get_font_path
    font_path = get_font_path("Cairo-VariableFont_slnt,wght.ttf")
    
    font_id = QFontDatabase.addApplicationFont(font_path)
    if font_id != -1:
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        if font_families:
            Typography.FONT_FAMILY = font_families[0]
    
    # تطبيق الخط الافتراضي
    app.setFont(Typography.get_font("body"))
    
    # تطبيق الستايل العام
    app.setStyleSheet(get_global_stylesheet())


def get_global_stylesheet() -> str:
    """الحصول على الستايل العام للتطبيق"""
    font_size = Typography.get_font_size("body")
    
    return f"""
        * {{
            font-family: '{Typography.FONT_FAMILY}';
        }}
        
        QWidget {{
            background-color: {Colors.BG_DARK};
            color: {Colors.TEXT_PRIMARY};
            font-size: {font_size}px;
        }}
        
        QMainWindow {{
            background-color: {Colors.BG_DARK};
        }}
        
        QDialog {{
            background-color: {Colors.BG_DARK};
        }}
        
        QToolTip {{
            background-color: {Colors.BG_MEDIUM};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER};
            border-radius: 6px;
            padding: 8px;
            font-size: {font_size}px;
        }}
        
        QMenu {{
            background-color: {Colors.BG_MEDIUM};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER};
            border-radius: 8px;
            padding: 5px;
        }}
        
        QMenu::item {{
            padding: 10px 30px;
            border-radius: 4px;
        }}
        
        QMenu::item:selected {{
            background-color: {Colors.PRIMARY};
            color: white;
        }}
        
        QMenuBar {{
            background-color: {Colors.BG_DARK};
            color: {Colors.TEXT_PRIMARY};
            border-bottom: 1px solid {Colors.BORDER};
            padding: 5px;
        }}
        
        QMenuBar::item {{
            padding: 8px 15px;
            border-radius: 4px;
        }}
        
        QMenuBar::item:selected {{
            background-color: {Colors.PRIMARY};
            color: white;
        }}
        
        QStatusBar {{
            background-color: {Colors.BG_DARK};
            border-top: 1px solid {Colors.BORDER};
            font-size: {Typography.get_font_size('small')}px;
        }}
        
        QStatusBar QLabel {{
            background-color: transparent;
            color: {Colors.TEXT_SECONDARY};
            padding: 5px 10px;
        }}
    """


# ============================================================
# 🎯 SIZE POLICY HELPERS
# ============================================================

class SizePolicies:
    """سياسات الحجم الموحدة"""
    
    @staticmethod
    def expanding() -> QSizePolicy:
        """سياسة التمدد الكامل"""
        return QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    @staticmethod
    def expanding_horizontal() -> QSizePolicy:
        """سياسة التمدد الأفقي فقط"""
        return QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    
    @staticmethod
    def expanding_vertical() -> QSizePolicy:
        """سياسة التمدد العمودي فقط"""
        return QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    
    @staticmethod
    def fixed() -> QSizePolicy:
        """سياسة الحجم الثابت"""
        return QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    
    @staticmethod
    def minimum() -> QSizePolicy:
        """سياسة الحد الأدنى"""
        return QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
    
    @staticmethod
    def preferred() -> QSizePolicy:
        """سياسة الحجم المفضل"""
        return QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)


# ============================================================
# 🔧 FORM BUILDER - بناء النماذج
# ============================================================

class FormBuilder:
    """بناء نماذج متجاوبة بسهولة"""
    
    def __init__(self, parent: QWidget = None):
        self.parent = parent
        self.layout = ResponsiveLayout.create_form_layout(parent)
        self.fields = {}
    
    def add_field(
        self,
        name: str,
        label: str,
        widget: QWidget,
        stretch: bool = True
    ) -> 'FormBuilder':
        """إضافة حقل للنموذج"""
        
        # إنشاء التسمية
        lbl = QLabel(label)
        lbl.setStyleSheet(InputFactory.get_label_style())
        
        # تطبيق سياسة التمدد
        if stretch:
            widget.setSizePolicy(SizePolicies.expanding_horizontal())
        
        # إضافة للتخطيط
        row_layout = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        # في RTL، التسمية على اليمين
        row_layout.addWidget(widget, 1)
        row_layout.addWidget(lbl, 0)
        
        self.layout.addLayout(row_layout)
        self.fields[name] = widget
        
        return self
    
    def add_row(self, widgets: list, stretch_factors: list = None) -> 'FormBuilder':
        """إضافة صف من العناصر"""
        
        row_layout = ResponsiveLayout.create_hbox(spacing=Spacing.MD)
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        if stretch_factors is None:
            stretch_factors = [1] * len(widgets)
        
        for widget, stretch in zip(widgets, stretch_factors):
            row_layout.addWidget(widget, stretch)
        
        self.layout.addLayout(row_layout)
        return self
    
    def add_buttons(self, buttons: list, alignment: str = "right") -> 'FormBuilder':
        """إضافة أزرار"""
        
        btn_layout = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        btn_layout.setContentsMargins(0, Spacing.LG, 0, 0)
        
        if alignment == "right":
            btn_layout.addStretch()
        elif alignment == "center":
            btn_layout.addStretch()
        
        for btn in buttons:
            btn_layout.addWidget(btn)
        
        if alignment == "center":
            btn_layout.addStretch()
        
        self.layout.addLayout(btn_layout)
        return self
    
    def add_spacer(self, height: int = Spacing.LG) -> 'FormBuilder':
        """إضافة مسافة"""
        spacer = QSpacerItem(0, height, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.layout.addItem(spacer)
        return self
    
    def add_stretch(self) -> 'FormBuilder':
        """إضافة تمدد"""
        self.layout.addStretch()
        return self
    
    def get_field(self, name: str) -> QWidget:
        """الحصول على حقل بالاسم"""
        return self.fields.get(name)
    
    def get_layout(self) -> QVBoxLayout:
        """الحصول على التخطيط"""
        return self.layout
