# دليل تثبيت مولد PDF

## المشكلة
البرنامج يحفظ الفواتير كملفات HTML بدلاً من PDF لأن مولد PDF غير مثبت.

## الحلول المتاحة

### الحل 1: تثبيت wkhtmltopdf (موصى به) ⭐

#### خطوات التثبيت على Windows:

1. **تحميل البرنامج:**
   - اذهب إلى: https://wkhtmltopdf.org/downloads.html
   - اختر "Windows (MSVC 2015) 64-bit"
   - حمل الملف: `wkhtmltox-0.12.6-1.msvc2015-win64.exe`

2. **التثبيت:**
   - شغل الملف المحمل
   - اتبع خطوات التثبيت
   - المسار الافتراضي: `C:\Program Files\wkhtmltopdf`

3. **التحقق من التثبيت:**
   ```cmd
   wkhtmltopdf --version
   ```
   يجب أن تظهر رسالة تحتوي على رقم الإصدار

4. **إعادة تشغيل البرنامج:**
   - أغلق برنامج Sky Wave ERP
   - شغله من جديد
   - جرب إنشاء فاتورة

### الحل 2: استخدام Chrome/Edge (بديل)

إذا كان لديك Google Chrome أو Microsoft Edge مثبت، البرنامج سيستخدمه تلقائياً.

**المسارات المدعومة:**
- `C:\Program Files\Google\Chrome\Application\chrome.exe`
- `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`
- `C:\Program Files\Microsoft\Edge\Application\msedge.exe`
- `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`

### الحل 3: استخدام HTML مباشرة

إذا لم تستطع تثبيت أي من الحلول السابقة:
1. البرنامج سيحفظ الفاتورة كملف HTML
2. افتح الملف في المتصفح
3. اطبع من المتصفح (Ctrl+P)
4. اختر "Save as PDF"

## التحقق من نجاح التثبيت

بعد تثبيت wkhtmltopdf:

1. افتح Command Prompt
2. اكتب: `wkhtmltopdf --version`
3. يجب أن تظهر رسالة مثل:
   ```
   wkhtmltopdf 0.12.6 (with patched qt)
   ```

## استكشاف الأخطاء

### المشكلة: "wkhtmltopdf not found"
**الحل:**
- تأكد من التثبيت في المسار الصحيح
- أعد تشغيل الكمبيوتر
- تأكد من إضافة wkhtmltopdf إلى PATH

### المشكلة: "Access Denied"
**الحل:**
- شغل البرنامج كمسؤول (Run as Administrator)
- تأكد من صلاحيات الكتابة في مجلد exports

### المشكلة: "Chrome not found"
**الحل:**
- ثبت Google Chrome من: https://www.google.com/chrome/
- أو ثبت Microsoft Edge (مثبت افتراضياً في Windows 10/11)

## ملاحظات

- ✅ wkhtmltopdf أسرع وأفضل للإنتاج
- ✅ Chrome/Edge يعمل لكن أبطأ قليلاً
- ✅ HTML يعمل دائماً كبديل احتياطي

## الدعم

إذا واجهت مشاكل:
1. تحقق من سجل الأخطاء في `logs/skywave_erp.log`
2. تأكد من تشغيل البرنامج بصلاحيات كافية
3. جرب إعادة تشغيل الكمبيوتر بعد التثبيت
