# Implementation Plan

## Smart Scan Payment Feature

- [x] 1. إعداد البنية الأساسية والتكوين





  - [x] 1.1 إضافة إعدادات Smart Scan في ملف الإعدادات


    - إضافة قسم `smart_scan` في `skywave_settings.json`
    - دعم `openai_api_key`, `enabled`, `model`, `max_image_size_mb`
    - _Requirements: 5.1_
  - [x] 1.2 إنشاء ScanResult dataclass


    - إنشاء `core/scan_result.py` مع الحقول: success, amount, date, reference_number, sender_name, platform, error_message
    - _Requirements: 2.2_

- [x] 2. إنشاء خدمة المسح الذكي (SmartScanService)







  - [x] 2.1 إنشاء ملف الخدمة الأساسي


    - إنشاء `services/smart_scan_service.py`
    - تنفيذ `__init__` مع تحميل API key من الإعدادات
    - تنفيذ `is_available()` للتحقق من توفر الخدمة
    - _Requirements: 5.1, 5.2_
  - [x] 2.2 تنفيذ دالة ترميز الصورة

    - تنفيذ `_encode_image()` لتحويل الصورة إلى Base64
    - التحقق من حجم الصورة (max 10MB)
    - _Requirements: 2.1_
  - [x] 2.3 تنفيذ دالة المسح الرئيسية

    - تنفيذ `scan_receipt()` للتواصل مع OpenAI API
    - إرسال الصورة مع الـ Prompt المحدد
    - _Requirements: 2.1, 2.5_
  - [x] 2.4 تنفيذ دالة تحليل الاستجابة

    - تنفيذ `_parse_response()` لتحليل JSON من AI
    - تحويل التاريخ لصيغة YYYY-MM-DD
    - تحويل المبلغ لرقم float
    - _Requirements: 2.2, 2.3, 2.4_
  - [ ]* 2.5 كتابة Property Test لتحليل الاستجابة
    - **Property 2: AI Response Parsing Consistency**
    - **Validates: Requirements 2.2, 2.4**
  - [ ]* 2.6 كتابة Property Test لتنسيق التاريخ
    - **Property 3: Date Format Normalization**
    - **Validates: Requirements 2.3**
  - [ ]* 2.7 كتابة Property Test لتحويل المبلغ
    - **Property 4: Amount Type Conversion**
    - **Validates: Requirements 2.3**

- [x] 3. إنشاء Widget رفع الصور (SmartScanDropzone)



  - [x] 3.1 إنشاء Widget الأساسي


    - إنشاء `ui/smart_scan_dropzone.py`
    - تصميم واجهة Dropzone مع أيقونة رفع ونص توضيحي
    - دعم Drag & Drop للصور
    - _Requirements: 1.1, 1.4_

  - [x] 3.2 تنفيذ التحقق من نوع الملف

    - قبول ملفات الصور فقط (jpg, png, gif, webp)
    - عرض رسالة خطأ للملفات غير المدعومة
    - _Requirements: 1.3_
  - [ ]* 3.3 كتابة Property Test للتحقق من نوع الملف
    - **Property 1: File Type Validation**

    - **Validates: Requirements 1.3**
  - [ ] 3.4 تنفيذ حالة التحميل
    - عرض مؤشر تحميل "جاري المسح الذكي..."

    - تعطيل التفاعل أثناء المسح
    - _Requirements: 1.2_
  - [ ] 3.5 تنفيذ عرض الأخطاء
    - عرض رسائل الخطأ بالعربية
    - زر "حاول مرة أخرى"




    - _Requirements: 4.1, 4.2, 4.3, 4.4_



- [ ] 4. Checkpoint - التأكد من عمل الخدمة والـ Widget
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. دمج Smart Scan مع شاشة الدفعات

  - [ ] 5.1 إضافة SmartScanDropzone لـ PaymentDialog
    - إضافة Widget فوق حقول الإدخال
    - ربط الـ signals مع الـ dialog
    - _Requirements: 1.1_
  - [ ] 5.2 تنفيذ الملء التلقائي للحقول
    - ملء حقل المبلغ

    - ملء حقل التاريخ
    - إضافة حقل الرقم المرجعي (إذا غير موجود)
    - _Requirements: 3.1, 3.2, 3.3_




  - [ ] 5.3 تنفيذ مطابقة المحفظة
    - البحث عن الحساب المطابق للمنصة (Vodafone Cash, InstaPay)

    - اختيار الحساب تلقائياً
    - _Requirements: 3.4_

  - [ ]* 5.4 كتابة Property Test لمطابقة المحفظة
    - **Property 5: Platform Account Matching**

    - **Validates: Requirements 3.4**
  - [ ] 5.5 التأكد من قابلية التعديل بعد الملء
    - الحقول تبقى قابلة للتعديل
    - المستخدم يراجع قبل الحفظ
    - _Requirements: 3.5_

- [ ] 6. معالجة الأخطاء والحالات الخاصة
  - [ ] 6.1 معالجة خطأ API غير متاح
    - عرض رسالة "خدمة المسح الذكي غير متاحة حالياً"
    - _Requirements: 4.2_
  - [ ] 6.2 معالجة خطأ API Key غير صالح
    - عرض رسالة "مفتاح API غير صالح"
    - _Requirements: 5.3_
  - [ ] 6.3 معالجة خطأ صورة غير واضحة
    - عرض رسالة "الصورة غير واضحة، يرجى رفع صورة أوضح"
    - _Requirements: 4.1_
  - [ ] 6.4 معالجة عدم وجود بيانات
    - عرض رسالة "لم يتم العثور على بيانات دفع في الصورة"
    - _Requirements: 4.3_


- [x] 7. Final Checkpoint - التأكد من عمل الميزة كاملة

  - Ensure all tests pass, ask the user if questions arise.
