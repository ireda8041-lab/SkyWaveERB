# 🔧 إعداد Git ورفع المشروع

دليل خطوة بخطوة لرفع المشروع على GitHub

---

## 📋 الخطوات

### 1. التأكد من Git

```bash
# تحقق من تثبيت Git
git --version

# إذا لم يكن مثبتاً، حمله من:
# https://git-scm.com/download/win
```

### 2. إعداد Git (أول مرة فقط)

```bash
# ضع اسمك وبريدك
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# اختياري: ضبط المحرر
git config --global core.editor "code --wait"
```

### 3. تهيئة المشروع

```bash
# إذا لم يكن المشروع Git repository بعد
git init

# إضافة remote
git remote add origin https://github.com/ireda8041-lab/SkyWaveERB.git

# أو إذا كان موجود بالفعل
git remote set-url origin https://github.com/ireda8041-lab/SkyWaveERB.git
```

### 4. إضافة الملفات

```bash
# إضافة جميع الملفات
git add .

# أو إضافة ملفات محددة
git add README.md
git add requirements.txt
git add main.py
```


### 5. Commit التغييرات

```bash
# عمل commit
git commit -m "Release v2.0.0 - نظام محسّن ومستقر"

# أو commit مفصل
git commit -m "Release v2.0.0" -m "
- تحسينات شاملة في الأداء
- إصلاح جميع المشاكل المعروفة
- واجهة محسّنة
- نظام مزامنة مستقر
"
```

### 6. Push إلى GitHub

```bash
# أول مرة
git push -u origin main

# المرات التالية
git push
```

### 7. إنشاء Tag للإصدار

```bash
# إنشاء tag
git tag -a v2.0.0 -m "Release v2.0.0"

# رفع tag
git push origin v2.0.0

# أو رفع جميع tags
git push --tags
```

---

## 🔄 تحديث المشروع

### عند عمل تغييرات جديدة

```bash
# 1. تحقق من الحالة
git status

# 2. أضف التغييرات
git add .

# 3. عمل commit
git commit -m "وصف التغييرات"

# 4. رفع التغييرات
git push
```


---

## 🚀 إنشاء Release على GitHub

### الطريقة 1: من الموقع

1. اذهب إلى: https://github.com/ireda8041-lab/SkyWaveERB
2. اضغط على "Releases"
3. اضغط "Create a new release"
4. املأ البيانات:
   - Tag: `v2.0.0`
   - Title: `Sky Wave ERP v2.0.0`
   - Description: انسخ من CHANGELOG.md
5. ارفع الملفات (EXE, ZIP)
6. اضغط "Publish release"

### الطريقة 2: من GitHub CLI

```bash
# تثبيت GitHub CLI
# https://cli.github.com/

# تسجيل الدخول
gh auth login

# إنشاء release
gh release create v2.0.0 \
  --title "Sky Wave ERP v2.0.0" \
  --notes-file CHANGELOG.md \
  dist/SkyWaveERP-Setup-2.0.0.exe
```

---

## 📝 ملفات مهمة للتحقق منها

قبل الرفع، تأكد من:

- [ ] `.gitignore` محدث
- [ ] `README.md` محدث
- [ ] `CHANGELOG.md` محدث
- [ ] `requirements.txt` محدث
- [ ] `version.py` محدث
- [ ] `version.json` محدث
- [ ] `pyproject.toml` محدث
- [ ] لا توجد ملفات حساسة (.env, passwords)
- [ ] لا توجد ملفات كبيرة غير ضرورية

---

## ⚠️ ملاحظات مهمة

### ملفات لا يجب رفعها

- `.env` (إعدادات محلية)
- `skywave_local.db` (قاعدة بيانات محلية)
- `__pycache__/` (ملفات Python المؤقتة)
- `build/`, `dist/` (ملفات البناء)
- `.venv/` (البيئة الافتراضية)

### التأكد من .gitignore

```bash
# عرض الملفات التي سيتم رفعها
git status

# عرض الملفات المتجاهلة
git status --ignored
```

---

**Made with ❤️ by Sky Wave Team**
