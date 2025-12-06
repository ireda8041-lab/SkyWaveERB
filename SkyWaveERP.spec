# -*- mode: python ; coding: utf-8 -*-
"""
Sky Wave ERP - PyInstaller Spec File (OneDir Mode)
"""

block_cipher = None
import os
import sys
import shutil

# ============================================
# جمع كل الملفات والمجلدات المطلوبة
# ============================================
added_files = [
    # الملفات الأساسية
    ('logo.png', '.'),
    ('icon.ico', '.'),
    ('site logo.png', '.'),
    ('Sky Wave template.jpg', '.'),
    ('version.json', '.'),
    ('skywave_settings.json', '.'),
    ('updater.exe', '.'),  # ملف التحديث
    
    # مجلد assets بالكامل مع كل المحتويات
    ('assets/arrow.png', 'assets'),
    ('assets/down-arrow.png', 'assets'),
    ('assets/up-arrow.png', 'assets'),
    ('assets/font', 'assets/font'),
    ('assets/templates', 'assets/templates'),
]

# ============================================
# Hidden Imports - كل الموديولات المطلوبة
# ============================================
hidden_imports = [
    # PyQt6 - كل الموديولات
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtPrintSupport',
    'PyQt6.QtNetwork',
    'PyQt6.sip',
    
    # Pydantic
    'pydantic',
    'pydantic.fields',
    'pydantic.main',
    'pydantic.types',
    'pydantic.dataclasses',
    'pydantic.networks',
    'pydantic.version',
    'pydantic.config',
    'pydantic_core',
    'pydantic_core._pydantic_core',
    'annotated_types',
    'typing_extensions',
    
    # Data libraries
    'pandas',
    'openpyxl',
    'numpy',
    
    # PDF & Templates
    'jinja2',
    'jinja2.ext',
    'reportlab',
    'reportlab.lib',
    'reportlab.lib.pagesizes',
    'reportlab.lib.colors',
    'reportlab.lib.styles',
    'reportlab.lib.units',
    'reportlab.lib.enums',
    'reportlab.platypus',
    'reportlab.pdfgen',
    'reportlab.pdfbase',
    'reportlab.pdfbase.ttfonts',
    'arabic_reshaper',
    'bidi',
    'bidi.algorithm',
    
    # Images
    'PIL',
    'PIL.Image',
    
    # Network
    'requests',
    'pymongo',
    'dns',
    'dns.resolver',
    
    # Logging
    'colorlog',
    
    # Threading
    'concurrent.futures',
    'threading',
    'queue',
    
    # Database
    'sqlite3',
    
    # Core modules - كل موديولات المشروع
    'core',
    'core.data_loader',
    'core.advanced_sync_manager',
    'core.auto_sync',
    'core.logger',
    'core.schemas',
    'core.signals',
    'core.auth_models',
    'core.base_service',
    'core.error_handler',
    'core.event_bus',
    'core.keyboard_shortcuts',
    'core.monitoring',
    'core.performance',
    'core.repository',
    'core.resource_utils',
    'core.speed_optimizer',
    'core.sync_manager',
    'core.validators',
    
    # Services
    'services',
    'services.printing_service',
]

# ============================================
# إضافة PyQt6 plugins
# ============================================
pyqt6_binaries = []
pyqt6_datas = []

try:
    import PyQt6
    pyqt6_path = os.path.dirname(PyQt6.__file__)
    qt_path = os.path.join(pyqt6_path, 'Qt6')
    
    # إضافة plugins
    plugins_path = os.path.join(qt_path, 'plugins')
    if os.path.exists(plugins_path):
        pyqt6_datas.append((plugins_path, 'PyQt6/Qt6/plugins'))
    
    # إضافة bin (للـ DLLs)
    bin_path = os.path.join(qt_path, 'bin')
    if os.path.exists(bin_path):
        for f in os.listdir(bin_path):
            if f.endswith('.dll'):
                pyqt6_binaries.append((os.path.join(bin_path, f), '.'))
    
    print(f"✅ PyQt6 plugins added from: {plugins_path}")
except Exception as e:
    print(f"⚠️ Warning: Could not find PyQt6: {e}")

# ============================================
# إضافة pydantic_core binaries
# ============================================
pydantic_binaries = []
try:
    import pydantic_core
    pydantic_core_path = os.path.dirname(pydantic_core.__file__)
    for f in os.listdir(pydantic_core_path):
        if f.endswith(('.pyd', '.dll', '.so')):
            src = os.path.join(pydantic_core_path, f)
            pydantic_binaries.append((src, 'pydantic_core'))
    print(f"✅ pydantic_core binaries added")
except Exception as e:
    print(f"⚠️ Warning: Could not find pydantic_core: {e}")

# ============================================
# دمج كل الـ binaries و datas
# ============================================
all_binaries = pyqt6_binaries + pydantic_binaries
all_datas = added_files + pyqt6_datas

print(f"📦 Total data entries: {len(all_datas)}")
print(f"📦 Total binary entries: {len(all_binaries)}")

# ============================================
# Analysis
# ============================================
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'tkinter',
        'unittest',
        'pytest',
        'IPython',
        'notebook',
        'sphinx',
        'weasyprint',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ============================================
# PYZ
# ============================================
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ============================================
# EXE (onedir mode)
# ============================================
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SkyWaveERP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

# ============================================
# COLLECT - يجمع كل الملفات في مجلد واحد
# ============================================
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SkyWaveERP',
)
