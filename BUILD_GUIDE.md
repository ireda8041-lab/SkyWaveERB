# 🔨 دليل البناء والنشر - Build & Deploy Guide

دليل شامل لبناء ونشر Sky Wave ERP

---

## 📋 المتطلبات الأساسية

### البرامج المطلوبة
- Python 3.10 أو أحدث
- Git
- PyInstaller
- Inno Setup (لإنشاء Setup Installer)

### تثبيت المتطلبات

```bash
# تثبيت Python packages
pip install -r requirements.txt

# تثبيت PyInstaller
pip install pyinstaller

# تحميل Inno Setup من:
# https://jrsoftware.org/isdl.php
```

---

## 🏗️ بناء ملف EXE

### الطريقة 1: استخدام PyInstaller مباشرة

```bash
# بناء ملف واحد (onefile)
pyinstaller --clean SkyWaveERP.spec

# بناء مجلد (onedir) - أسرع في التشغيل
pyinstaller --clean SkyWaveERP_onedir.spec
```

### الطريقة 2: استخدام سكريبت البناء

```bash
# تشغيل سكريبت البناء الآلي
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

الملفات المبنية ستكون في مجلد `dist/`


---

## 📦 إنشاء Setup Installer

### استخدام Inno Setup

1. افتح ملف `SkyWaveERP_Setup.iss` في Inno Setup
2. اضغط على Build > Compile
3. الملف سيكون في `installer_output/`

### أو استخدام سكريبت البناء الكامل

```bash
# بناء EXE + Setup Installer
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

---

## 🧪 اختبار البناء

### قبل النشر، تأكد من:

```bash
# 1. اختبار الاستيرادات
python -c "import main; print('OK')"

# 2. تشغيل الاختبارات
pytest

# 3. فحص الكود
ruff check .
black --check .

# 4. اختبار EXE المبني
cd dist/SkyWaveERP
./SkyWaveERP.exe
```

---

## 🚀 النشر على GitHub

### 1. تحديث رقم الإصدار

تأكد من تحديث:
- `version.py` → `CURRENT_VERSION`
- `version.json` → `version`
- `pyproject.toml` → `version`

### 2. Commit التغييرات

```bash
git add .
git commit -m "Release v2.0.0"
git tag v2.0.0
git push origin main
git push origin v2.0.0
```


### 3. إنشاء Release على GitHub

1. اذهب إلى: https://github.com/ireda8041-lab/SkyWaveERB/releases/new
2. اختر Tag: `v2.0.0`
3. عنوان Release: `Sky Wave ERP v2.0.0`
4. الوصف: انسخ من `CHANGELOG.md`
5. ارفع الملفات:
   - `SkyWaveERP-Setup-2.0.0.exe`
   - `SkyWaveERP-Portable-2.0.0.zip`
6. اضغط Publish Release

---

## 📝 Checklist قبل النشر

- [ ] تحديث رقم الإصدار في جميع الملفات
- [ ] تحديث CHANGELOG.md
- [ ] اختبار البرنامج بشكل كامل
- [ ] بناء EXE بنجاح
- [ ] اختبار EXE على جهاز نظيف
- [ ] إنشاء Setup Installer
- [ ] اختبار Setup Installer
- [ ] Commit وPush إلى GitHub
- [ ] إنشاء Tag
- [ ] إنشاء Release
- [ ] رفع الملفات
- [ ] اختبار رابط التحميل

---

## 🔍 استكشاف الأخطاء

### مشكلة: PyInstaller لا يجد الملفات

```bash
# تأكد من وجود جميع الملفات في .spec
# أضف الملفات المفقودة في datas
```

### مشكلة: EXE لا يعمل

```bash
# شغل من CMD لرؤية الأخطاء
cd dist/SkyWaveERP
SkyWaveERP.exe

# أو شغل مع console
pyinstaller --console SkyWaveERP.spec
```

### مشكلة: مكتبة مفقودة

```bash
# أضف المكتبة في hiddenimports في .spec
hiddenimports=['missing_module']
```

---

**Made with ❤️ by Sky Wave Team**
