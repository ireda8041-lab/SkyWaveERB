# دليل تكامل الواتساب - Chrome-Only Strategy

## نظرة عامة

تم إنشاء نظام موحد جديد لإدارة الفواتير وإرسالها عبر الواتساب باستخدام **Chrome-Only Strategy**.

## الملفات الجديدة

### 1. `services/smart_invoice_manager.py`
**الوحدة الأساسية** - تحتوي على:
- `SmartInvoiceManager` - الكلاس الرئيسي
- `generate_pdf_from_html()` - إنشاء PDF من HTML
- `send_pdf_via_whatsapp()` - إرسال PDF عبر الواتساب
- `process_and_send()` - العملية الكاملة

### 2. تحديث `ui/project_manager.py`
- ✅ إضافة زر "📱 إرسال للواتساب"
- ✅ دالة `send_invoice_whatsapp()` مع التحقق الصارم
- ✅ جلب البيانات الحقيقية من قاعدة البيانات

## كيفية العمل

### المرحلة 1: إنشاء PDF
```python
# استخدام Chrome Headless لإنشاء PDF
driver = webdriver.Chrome(options=chrome_options)
driver.get(f"file:///{html_file}")
pdf_data = driver.execute_cdp_cmd("Page.printToPDF", print_options)
```

### المرحلة 2: إرسال عبر الواتساب
```python
# استخدام نفس Chrome لفتح WhatsApp Web
driver.get(f"https://web.whatsapp.com/send?phone={phone}")
# رفع الملف وإرساله
```

## المتطلبات

### 1. المكتبات المطلوبة
```bash
pip install selenium>=4.15.0
pip install webdriver-manager>=4.0.0
```

### 2. متطلبات النظام
- ✅ Google Chrome مثبت
- ✅ اتصال إنترنت
- ✅ حساب WhatsApp

## الاستخدام

### من الواجهة الرسومية:
1. افتح البرنامج
2. اذهب إلى إدارة المشاريع
3. اختر مشروع
4. اضغط "📱 إرسال للواتساب"

### برمجياً:
```python
from services.smart_invoice_manager import SmartInvoiceManager

manager = SmartInvoiceManager()
success, message = manager.process_and_send(
    invoice_data=invoice_data,
    html_content=html_content,
    phone_number="201234567890",
    message="مرحباً، إليك الفاتورة"
)
```

## التحقق الصارم من البيانات

### 1. التحقق من تحديد المشروع
```python
if not self.selected_project:
    show_error("يرجى تحديد مشروع أولاً")
    return
```

### 2. التحقق من بيانات العميل
```python
client = self.client_service.get_client_by_id(project.client_id)
if not client:
    show_error("لم يتم العثور على معلومات العميل")
    return
```

### 3. التحقق الصارم من رقم الهاتف
```python
client_phone = getattr(client, 'phone', None)
if not client_phone or not client_phone.strip():
    show_error("العميل لا يحتوي على رقم هاتف!")
    return

# تنظيف والتحقق من صحة الرقم
clean_phone = client_phone.replace("+", "").replace(" ", "").replace("-", "")
if not clean_phone.isdigit() or len(clean_phone) < 10:
    show_error("رقم الهاتف غير صحيح!")
    return
```

### 4. جلب البيانات الحقيقية
```python
# بيانات الفاتورة الحقيقية
invoice_data = {
    'client_name': client.name,  # ❌ ليس hardcoded
    'client_phone': client_phone,  # ❌ ليس test data
    'project_name': project.name,  # ✅ من المشروع المحدد
    'date': datetime.now().strftime('%Y-%m-%d')  # ✅ التاريخ الحالي
}

# الدفعات الحقيقية
payments = self.project_service.get_payments_for_project(project.name)
```

## الميزات الأمنية

### 1. جلسة Chrome المستمرة
- مجلد منفصل: `erp_browser_profile`
- تسجيل دخول WhatsApp يبقى محفوظ
- لا حاجة لإعادة المسح الضوئي

### 2. إعدادات Chrome المقاومة للأعطال
```python
options.add_argument("--remote-debugging-port=9222")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
```

### 3. CSS محسن للطباعة
```css
@page { size: A4; margin: 0; }
body { width: 210mm; height: 297mm; overflow: hidden; }
```

## استكشاف الأخطاء

### المشكلة: "Chrome driver not found"
**الحل:**
```bash
pip install webdriver-manager
```

### المشكلة: "WhatsApp Web not loading"
**الحل:**
1. تأكد من الاتصال بالإنترنت
2. امسح بيانات المتصفح: احذف مجلد `erp_browser_profile`
3. أعد تسجيل الدخول

### المشكلة: "PDF generation failed"
**الحل:**
1. تأكد من تثبيت Chrome
2. تحقق من صلاحيات الكتابة في مجلد `exports`

### المشكلة: "Phone number invalid"
**الحل:**
1. تأكد من إدخال رقم الهاتف في بيانات العميل
2. الرقم يجب أن يكون بالصيغة: `201234567890`

## الاختبار

### 1. اختبار إنشاء PDF
```python
from services.smart_invoice_manager import generate_invoice_pdf

html = "<html><body><h1>Test</h1></body></html>"
pdf_path = generate_invoice_pdf(html, "test")
print(f"PDF created: {pdf_path}")
```

### 2. اختبار الإرسال
```python
from services.smart_invoice_manager import send_invoice_whatsapp

success = send_invoice_whatsapp("path/to/invoice.pdf", "201234567890", "Test message")
print(f"Sent: {success}")
```

## الخطوات التالية

1. ✅ تثبيت المتطلبات: `pip install selenium webdriver-manager`
2. ✅ تشغيل البرنامج
3. ✅ اختبار إنشاء PDF
4. ✅ تسجيل الدخول في WhatsApp Web (أول مرة)
5. ✅ اختبار الإرسال

## الدعم

للمساعدة:
1. تحقق من ملف السجل: `logs/skywave_erp.log`
2. تأكد من تثبيت Chrome
3. تحقق من اتصال الإنترنت

🎉 النظام جاهز للاستخدام!