# الملف: core/resource_utils.py
"""
أدوات إدارة الموارد - Resource Utilities
يحل مشكلة مسارات الملفات في PyInstaller (onefile و onedir)
"""

import sys
import os


def get_base_path():
    """
    الحصول على المسار الأساسي للتطبيق
    يعمل مع PyInstaller (onefile و onedir) و Python العادي
    """
    if getattr(sys, 'frozen', False):
        # التطبيق يعمل كـ EXE
        # في onedir: المسار هو مجلد الـ EXE
        # في onefile: المسار هو _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        else:
            return os.path.dirname(sys.executable)
    else:
        # التطبيق يعمل كـ Python script
        return os.path.abspath(".")


def get_resource_path(relative_path):
    """
    الحصول على المسار الصحيح للملفات في .exe أو في التطوير
    
    Args:
        relative_path (str): المسار النسبي للملف
        
    Returns:
        str: المسار الكامل للملف
    """
    base_path = get_base_path()
    
    # جرب المسارات المختلفة
    possible_paths = [
        os.path.join(base_path, "_internal", relative_path),  # PyInstaller onedir
        os.path.join(base_path, relative_path),  # PyInstaller onefile أو dev
        os.path.join(os.path.dirname(sys.executable), "_internal", relative_path),
        relative_path,  # مسار نسبي
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # إرجاع المسار الافتراضي
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