# -*- mode: python ; coding: utf-8 -*-
"""
Sky Wave ERP - PyInstaller Spec File
"""

block_cipher = None

# جمع كل الملفات المطلوبة
added_files = [
    ('logo.png', '.'),
    ('icon.ico', '.'),
    ('site logo.png', '.'),
    ('Sky Wave template.jpg', '.'),
    ('version.json', '.'),
    ('skywave_settings.json', '.'),
    ('assets', 'assets'),
]

# جمع كل الـ submodules
hidden_imports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtPrintSupport',
    'pymongo',
    'pydantic',
    'pydantic_core',
    'pandas',
    'openpyxl',
    'jinja2',
    'reportlab',
    'arabic_reshaper',
    'bidi',
    'PIL',
    'requests',
    'colorlog',
    'dns',
    'dns.resolver',
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
        'matplotlib',
        'scipy',
        'tkinter',
        'unittest',
        'pytest',
        'IPython',
        'notebook',
        'sphinx',
        'weasyprint',  # إزالة weasyprint لأنه يسبب مشاكل
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SkyWaveERP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
