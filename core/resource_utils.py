# الملف: core/resource_utils.py
"""
أدوات إدارة الموارد - Resource Utilities
يحل مشكلة مسارات الملفات في PyInstaller
"""

import sys
import os


def get_resource_path(relative_path):
    """
    الحصول على المسار الصحيح للملفات في .exe أو في التطوير
    
    Args:
        relative_path (str): المسار النسبي للملف
        
    Returns:
        str: المسار الكامل للملف
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_asset_path(filename):
    """
    الحصول على مسار ملف في مجلد assets
    
    Args:
        filename (str): اسم الملف
        
    Returns:
        str: المسار الكامل للملف
    """
    return get_resource_path(os.path.join("assets", filename))


def get_ui_asset_path(filename):
    """
    الحصول على مسار ملف في مجلد ui
    
    Args:
        filename (str): اسم الملف
        
    Returns:
        str: المسار الكامل للملف
    """
    return get_resource_path(os.path.join("ui", filename))


def get_font_path(font_filename):
    """
    الحصول على مسار ملف خط في مجلد assets/font
    
    Args:
        font_filename (str): اسم ملف الخط
        
    Returns:
        str: المسار الكامل لملف الخط
    """
    return get_resource_path(os.path.join("assets", "font", font_filename))