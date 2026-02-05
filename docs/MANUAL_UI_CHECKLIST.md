# قائمة تحقق يدوية شاملة (UI)

هذه القائمة مخصصة لاختبار التطبيق تفاعليًا (بالماوس/لوحة المفاتيح) وتوثيق الحالة: يعمل/لا يعمل/جزئي، مع ملاحظات الأداء والأولوية.

## قواعد التسجيل (قبل البدء)

- لكل عنصر: الحالة + خطوات التنفيذ + المتوقع/الفعلي + ملاحظة أداء (إن وجدت).
- الأولوية:
  - P0: يمنع الاستخدام أو يفقد بيانات
  - P1: عطل رئيسي في مسار مهم
  - P2: عطل متوسط/واجهة/رسائل
  - P3: تحسينات/تجميل/حواف

## 1) التشغيل وتسجيل الدخول

- تشغيل التطبيق:
  - تحقق من عدم وجود شاشة بيضاء طويلة أو تجمّد.
  - تحقق من الأيقونة والعنوان.
- [LoginWindow](file:///d:/blogs/appas/SkyWaveERB/ui/login_window.py)
  - إدخال فارغ → رسالة خطأ واضحة
  - بيانات خاطئة → رسالة خطأ + تركيز يعود لكلمة المرور
  - بيانات صحيحة → انتقال للنافذة الرئيسية
  - Enter داخل حقلي المستخدم/كلمة المرور ينفذ تسجيل الدخول
  - زر الإلغاء يغلق النافذة بشكل صحيح

## 2) النافذة الرئيسية والتنقّل

- [MainWindow](file:///d:/blogs/appas/SkyWaveERB/ui/main_window.py)
  - عرض التبويبات بالكامل بدون قص/تشوّه (RTL)
  - تبديل سريع بين التبويبات 10 مرات بدون تجمّد
  - إعادة فتح التطبيق بعد إغلاقه بدون أخطاء
- شريط الحالة [StatusBarWidget](file:///d:/blogs/appas/SkyWaveERB/ui/status_bar_widget.py)
  - زر المزامنة: حالة (syncing/synced/offline/error) + عدم تجمّد UI

## 3) تبويب الصفحة الرئيسية (Dashboard)

- [DashboardTab](file:///d:/blogs/appas/SkyWaveERB/ui/dashboard_tab.py)
  - عرض بطاقات الإحصائيات (إن وجدت بيانات) أو رسالة “لا توجد بيانات”
  - تغيير فترة التاريخ (إن وُجد) ينعكس على الجداول/المخططات
  - المخطط (إن توفر matplotlib) لا يسبب انهيارًا
  - الأداء: فتح التبويب لأول مرة / تحديث البيانات

## 4) تبويب العملاء

- [ClientManagerTab](file:///d:/blogs/appas/SkyWaveERB/ui/client_manager.py)
  - إضافة عميل جديد: فتح Dialog + حفظ + ظهور العميل في القائمة
  - تعديل عميل: تحديد صف → تعديل → حفظ → تحديث الصف
  - حذف عميل: تأكيد → حذف → اختفاء العميل
  - تصدير Excel / استيراد Excel: رسائل نجاح/فشل واضحة
  - البحث/الفلترة: [UniversalSearchBar](file:///d:/blogs/appas/SkyWaveERB/ui/universal_search.py)
  - إظهار المؤرشفين: يعمل ويحدّث القائمة

## 5) تبويب الخدمات والباقات

- [ServiceManagerTab](file:///d:/blogs/appas/SkyWaveERB/ui/service_manager.py)
  - إضافة خدمة/باقة: حفظ + ظهورها في القائمة
  - تعديل خدمة: حفظ + تحديث الصف
  - أرشفة خدمة + إظهار المؤرشفين
  - البحث/الفلترة يعمل

## 6) تبويب المشاريع

- [ProjectManagerTab](file:///d:/blogs/appas/SkyWaveERB/ui/project_manager.py)
  - إنشاء مشروع جديد بمسار كامل:
    - اختيار عميل/خدمة/مواعيد
    - في حال عدم وجود عميل/خدمة: قبول الإنشاء “بالطيران” وفتح Dialog ثم الرجوع للمشروع
  - تسجيل دفعة لمشروع
  - فتح تقرير الربحية
  - الانتقال بين حالات المشروع/الأرشفة (إن وجدت)

## 7) تبويب المصروفات

- [ExpenseManagerTab](file:///d:/blogs/appas/SkyWaveERB/ui/expense_manager.py)
  - إضافة مصروف + حفظ
  - تعديل مصروف + حفظ
  - فلاتر/بحث (إن وجدت)

## 8) تبويب الدفعات

- [PaymentsManagerTab](file:///d:/blogs/appas/SkyWaveERB/ui/payments_manager.py)
  - إضافة دفعة + حفظ
  - ربط الدفعة بعميل/مشروع (حسب التصميم)
  - فلاتر/بحث/تحديث

## 9) تبويب المحاسبة

- [AccountingManagerTab](file:///d:/blogs/appas/SkyWaveERB/ui/accounting_manager.py)
  - إضافة حساب + حفظ
  - تعديل حساب + حفظ
  - قيود/تقارير (إن وجدت) تعمل وتعرض بيانات صحيحة

## 10) تبويب المهام

- [TodoManagerWidget](file:///d:/blogs/appas/SkyWaveERB/ui/todo_manager.py)
  - إضافة مهمة / إكمالها / حذفها
  - حفظ الحالة بعد إعادة تشغيل التطبيق

## 11) تبويب الإعدادات

- [SettingsTab](file:///d:/blogs/appas/SkyWaveERB/ui/settings_tab.py)
  - العملات: إضافة/تعديل عبر Dialog [currency_editor_dialog.py](file:///d:/blogs/appas/SkyWaveERB/ui/currency_editor_dialog.py)
  - المستخدمين: إضافة/تعديل عبر Dialog [user_editor_dialog.py](file:///d:/blogs/appas/SkyWaveERB/ui/user_editor_dialog.py)
  - صلاحيات المستخدم: Dialog [user_permissions_dialog.py](file:///d:/blogs/appas/SkyWaveERB/ui/user_permissions_dialog.py)

## 12) المزايا المتقدمة

- الإشعارات: [notification_system.py](file:///d:/blogs/appas/SkyWaveERB/ui/notification_system.py)
  - ظهور Toast، عدم تراكب مكسور، إغلاق تلقائي
- الحقول المخصصة: [custom_fields_manager.py](file:///d:/blogs/appas/SkyWaveERB/core/custom_fields_manager.py)
  - إضافة/حذف قيمة، تحقق من حفظها بعد إعادة التشغيل
- سيناريوهات اتصال:
  - العمل بدون MongoDB (Offline) بدون انهيار
  - العودة للاتصال (إن وُجد) بدون تجمّد

