# 🔨 تعليمات بناء EXE - Sky Wave ERP

## الطريقة 1: سكريبت Python (موصى به)

### الخطوات
```bash
# 1. تشغيل سكريبت البناء
python build_exe.py
```

### ماذا يفعل
- ✅ يتحقق من PyInstaller
- ✅ يثبته إذا لم يكن موجود
- ✅ ينظف المجلدات القديمة
- ✅ ينشئ ملف spec محسّن
- ✅ يبني EXE
- ✅ ينسخ الملفات الإضافية
- ✅ ينشئ README

### النتيجة
```
dist/
  └── SkyWaveERP/
      ├── SkyWaveERP.exe          ← الملف الرئيسي
      ├── skywave_local.db         ← قاعدة البيانات
      ├── skywave_settings.json    ← الإعدادات
      ├── assets/                  ← الموارد
      ├── exports/                 ← الصادرات
      ├── logs/                    ← السجلات
      ├── README.txt               ← التعليمات
      └── ... (ملفات أخرى)
```

---

## الطريقة 2: Batch File (Windows)

### الخطوات
```bash
# 1. تشغيل ملف bat
build_exe_simple.bat
```

### ماذا يفعل
- ✅ يتحقق من PyInstaller
- ✅ يبني EXE مباشرة
- ✅ ينسخ الملفات الإضافية

---

## الطريقة 3: يدوياً (للمتقدمين)

### الخطوات

#### 1. تثبيت PyInstaller
```bash
pip install pyinstaller
```

#### 2. بناء EXE
```bash
pyinstaller --name=SkyWaveERP ^
    --onedir ^
    --windowed ^
    --icon=icon.ico ^
    --add-data="assets;assets" ^
    --add-data="core;core" ^
    --add-data="services;services" ^
    --add-data="ui;ui" ^
    --add-data="logo.png;." ^
    --add-data="icon.ico;." ^
    --add-data="version.json;." ^
    --hidden-import=pymongo ^
    --hidden-import=PyQt6 ^
    --hidden-import=jinja2 ^
    --hidden-import=arabic_reshaper ^
    --hidden-import=bidi ^
    --hidden-import=PIL ^
    --hidden-import=reportlab ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --clean ^
    main.py
```

#### 3. نسخ الملفات الإضافية
```bash
copy skywave_local.db dist\SkyWaveERP\
copy skywave_settings.json dist\SkyWaveERP\
mkdir dist\SkyWaveERP\exports
mkdir dist\SkyWaveERP\logs
```

---

## المتطلبات

### Python Packages
```bash
pip install -r requirements.txt
pip install pyinstaller
```

### الملفات المطلوبة
- ✅ `main.py` - الملف الرئيسي
- ✅ `icon.ico` - أيقونة البرنامج
- ✅ `logo.png` - شعار البرنامج
- ✅ `version.json` - معلومات الإصدار
- ✅ `assets/` - مجلد الموارد
- ✅ `core/` - مجلد الكود الأساسي
- ✅ `services/` - مجلد الخدمات
- ✅ `ui/` - مجلد الواجهة

---

## الخيارات المتقدمة

### بناء ملف واحد (One File)
```bash
pyinstaller --onefile --name=SkyWaveERP main.py
```
⚠️ **تحذير:** أبطأ في التشغيل، لكن ملف واحد فقط

### بناء بدون كونسول (No Console)
```bash
pyinstaller --windowed --name=SkyWaveERP main.py
```
⚠️ **تحذير:** لن تظهر رسائل التتبع

### بناء مع UPX (ضغط)
```bash
pyinstaller --upx-dir=C:\upx --name=SkyWaveERP main.py
```
💡 **ملاحظة:** يقلل حجم الملف

---

## حل المشاكل

### المشكلة 1: PyInstaller غير موجود
```bash
pip install pyinstaller
```

### المشكلة 2: ModuleNotFoundError
```bash
# أضف المكتبة المفقودة
pip install <library_name>

# أضفها لـ hidden-import
--hidden-import=<library_name>
```

### المشكلة 3: الملفات مفقودة
```bash
# تأكد من إضافة المجلدات
--add-data="folder;folder"
```

### المشكلة 4: الأيقونة لا تظهر
```bash
# تأكد من وجود icon.ico
--icon=icon.ico
```

### المشكلة 5: البرنامج لا يعمل
```bash
# شغل مع الكونسول لرؤية الأخطاء
pyinstaller --console main.py
```

---

## الاختبار

### 1. اختبار محلي
```bash
cd dist\SkyWaveERP
SkyWaveERP.exe
```

### 2. اختبار على جهاز آخر
- انسخ مجلد `dist\SkyWaveERP` كامل
- شغل `SkyWaveERP.exe`

### 3. التحقق من الملفات
```
✅ SkyWaveERP.exe موجود
✅ assets/ موجود
✅ skywave_local.db موجود
✅ البرنامج يفتح بدون أخطاء
```

---

## التوزيع

### إنشاء ZIP
```bash
# ضغط المجلد
cd dist
tar -a -c -f SkyWaveERP-v1.0.3.zip SkyWaveERP
```

### إنشاء Installer (اختياري)
استخدم Inno Setup أو NSIS لإنشاء installer احترافي

---

## الحجم المتوقع

- **EXE:** ~15-20 MB
- **المجلد الكامل:** ~100-150 MB
- **ZIP:** ~50-70 MB

---

## الملاحظات المهمة

### ✅ افعل
- اختبر EXE قبل التوزيع
- احتفظ بنسخة من الكود المصدري
- وثق أي تغييرات

### ❌ لا تفعل
- لا تحذف مجلد `dist` قبل النسخ
- لا توزع بدون اختبار
- لا تنسى الملفات الإضافية

---

## الدعم

إذا واجهت مشاكل:
1. راجع رسائل الخطأ
2. تأكد من المتطلبات
3. جرب البناء مع `--console`
4. راجع سجلات PyInstaller

---

**تاريخ التحديث:** 2025-12-03  
**الإصدار:** 1.0.3  
**الحالة:** ✅ جاهز للبناء
