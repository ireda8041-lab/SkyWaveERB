# 🚀 دليل رفع الملفات على GitHub

## المشكلة الحالية:
```
remote: Repository not found.
fatal: repository 'https://github.com/imhzm/SkyWaveERB.git/' not found
```

هذا يعني أن GitHub يحتاج **مصادقة** (Authentication).

---

## ✅ الحل السريع (3 طرق):

### الطريقة 1: استخدام GitHub Desktop (الأسهل) 🎯

1. **حمل GitHub Desktop:** https://desktop.github.com/
2. **سجل دخول** بحسابك
3. **Add Existing Repository** → اختر المجلد: `D:\blogs\SkyWaveERB`
4. **اضغط "Push origin"**
5. **خلاص!** ✅

---

### الطريقة 2: استخدام Personal Access Token

#### الخطوة 1: إنشاء Token
1. روح على GitHub → **Settings** → **Developer settings**
2. **Personal access tokens** → **Tokens (classic)**
3. **Generate new token (classic)**
4. **اختار Scopes:**
   - ✅ `repo` (كل الصلاحيات)
5. **Generate token**
6. **انسخ الـ Token** (هيظهر مرة واحدة بس!)

#### الخطوة 2: استخدام الـ Token
```bash
# غير الـ remote URL
git remote set-url origin https://YOUR_TOKEN@github.com/imhzm/SkyWaveERB.git

# استبدل YOUR_TOKEN بالـ token اللي نسخته

# ثم ارفع الملفات
git push -u origin main
```

---

### الطريقة 3: استخدام SSH (للمحترفين)

#### الخطوة 1: إنشاء SSH Key
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

#### الخطوة 2: إضافة الـ Key لـ GitHub
1. انسخ الـ public key:
```bash
cat ~/.ssh/id_ed25519.pub
```
2. روح GitHub → **Settings** → **SSH and GPG keys**
3. **New SSH key** → الصق الـ key

#### الخطوة 3: غير الـ remote
```bash
git remote set-url origin git@github.com:imhzm/SkyWaveERB.git
git push -u origin main
```

---

## 🎯 الطريقة الموصى بها:

**استخدم GitHub Desktop** - أسهل وأسرع حل! 

بعد ما ترفع الملفات، تأكد من:
1. ✅ ملف `version.json` موجود في المجلد الرئيسي
2. ✅ الرابط شغال: https://raw.githubusercontent.com/imhzm/SkyWaveERB/main/version.json

---

## 📝 بعد الرفع:

### اختبار النظام:
```bash
python main.py
# ثم: الإعدادات → التحديثات → التحقق من التحديثات
```

### إنشاء أول Release (اختياري):
1. روح GitHub → **Releases** → **Create new release**
2. **Tag:** `v1.0.0`
3. **Title:** `الإصدار 1.0.0`
4. **ارفع:** `update.zip` (اضغط كل ملفات المشروع)
5. **Publish release**

---

## ✅ الخلاصة:

1. **حمل GitHub Desktop** (الأسهل)
2. **سجل دخول**
3. **Add Repository** → `D:\blogs\SkyWaveERB`
4. **Push**
5. **خلاص!** 🎉

---

**بعد الرفع، نظام التحديث هيشتغل على أي جهاز!** 🚀
