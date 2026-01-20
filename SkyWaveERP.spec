# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ('ui', 'ui'), 
    ('services', 'services'), 
    ('core', 'core'), 
    ('assets', 'assets'), 
    ('skywave_settings.json', '.'), 
    ('version.json', '.'), 
    ('version.py', '.'), 
    ('updater.py', '.'), 
    ('update_settings.json', '.'), 
    ('icon.ico', '.'), 
    ('logo.png', '.'), 
    ('site logo.png', '.'),
    ('skywave_local.db', '.')  # قاعدة البيانات الأولية
]
binaries = []

# ⚡ كل المكتبات المطلوبة
hiddenimports = [
    # PyQt6
    'PyQt6.QtCore', 
    'PyQt6.QtGui', 
    'PyQt6.QtWidgets', 
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtPrintSupport',
    'PyQt6.sip',
    
    # MongoDB (اختياري)
    'pymongo',
    'pymongo.errors',
    'pymongo.collection',
    'pymongo.database',
    'bson',
    'bson.objectid',
    'dns',
    'dns.resolver',
    
    # PDF & Printing
    'reportlab',
    'reportlab.lib',
    'reportlab.lib.colors',
    'reportlab.lib.pagesizes',
    'reportlab.lib.units',
    'reportlab.lib.styles',
    'reportlab.lib.enums',
    'reportlab.lib.utils',
    'reportlab.pdfbase',
    'reportlab.pdfbase.pdfmetrics',
    'reportlab.pdfbase.ttfonts',
    'reportlab.pdfgen',
    'reportlab.pdfgen.canvas',
    'reportlab.platypus',
    
    # Images
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageOps',
    'PIL.ImageFilter',
    'pillow',
    
    # Excel
    'openpyxl',
    'openpyxl.workbook',
    'openpyxl.worksheet',
    
    # Charts (matplotlib) - اختياري
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.figure',
    'matplotlib.backends',
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_agg',
    
    # Arabic text
    'arabic_reshaper',
    'bidi',
    'bidi.algorithm',
    
    # Templates
    'jinja2',
    'jinja2.environment',
    'jinja2.loaders',
    
    # Network
    'requests',
    'urllib3',
    'certifi',
    
    # Standard library
    'json',
    'sqlite3',
    'threading',
    'datetime',
    'typing',
    'dataclasses',
    'enum',
    'functools',
    'pathlib',
    'base64',
    'hashlib',
    'uuid',
    're',
    'os',
    'sys',
    'shutil',
    'logging',
    'traceback',
]

# جمع كل ملفات reportlab
tmp_ret = collect_all('reportlab')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# جمع كل ملفات jinja2
try:
    tmp_ret = collect_all('jinja2')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except:
    pass

# جمع كل ملفات matplotlib (اختياري)
try:
    tmp_ret = collect_all('matplotlib')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except:
    pass

# جمع كل ملفات PIL
try:
    tmp_ret = collect_all('PIL')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except:
    pass

# جمع كل ملفات arabic_reshaper
try:
    tmp_ret = collect_all('arabic_reshaper')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except:
    pass

# جمع كل ملفات bidi
try:
    tmp_ret = collect_all('bidi')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except:
    pass

# جمع كل ملفات openpyxl
try:
    tmp_ret = collect_all('openpyxl')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except:
    pass

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

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
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SkyWaveERP',
)
