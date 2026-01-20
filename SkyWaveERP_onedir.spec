# -*- mode: python ; coding: utf-8 -*-
"""
Sky Wave ERP - PyInstaller Spec File (One Directory Mode)
أسرع في التشغيل وأفضل للبرامج الكبيرة
✅ FIXED: Added all required files and folders
"""

block_cipher = None

# جمع كل الملفات المطلوبة - ✅ FIXED: Added all required files
added_files = [
    ('ui', 'ui'),  # ✅ Added
    ('services', 'services'),  # ✅ Added
    ('core', 'core'),  # ✅ Added
    ('assets', 'assets'),
    ('skywave_settings.json', '.'),
    ('version.json', '.'),
    ('version.py', '.'),
    ('updater.py', '.'),
    ('update_settings.json', '.'),
    ('icon.ico', '.'),
    ('logo.png', '.'),
    ('site logo.png', '.'),
    ('Sky Wave template.jpg', '.'),
    ('skywave_local.db', '.'),  # ✅ Added database
]

# جمع كل الـ submodules - ✅ FIXED: Added more imports
hidden_imports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtPrintSupport',
    'PyQt6.sip',
    'pymongo',
    'pymongo.errors',
    'pymongo.collection',
    'pymongo.database',
    'bson',
    'bson.objectid',
    'pydantic',
    'pydantic_core',
    'openpyxl',
    'jinja2',
    'reportlab',
    'arabic_reshaper',
    'bidi',
    'bidi.algorithm',
    'PIL',
    'requests',
    'colorlog',
    'dns',
    'dns.resolver',
    'certifi',
    'urllib3',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# === One Directory Mode (أسرع في التشغيل) ===
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # مهم لـ Onedir
    name='SkyWaveERP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Window Based - إخفاء الكونسول
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

# === جمع كل الملفات في مجلد واحد ===
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
