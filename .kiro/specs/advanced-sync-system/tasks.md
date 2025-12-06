# Implementation Tasks: Advanced Sync System

## تحليل الوضع الحالي

### ✅ ما هو موجود:
- `SyncManager` - مدير المزامنة الأساسي مع Queue System
- `AdvancedSyncManager` - مدير متقدم مع ConnectionChecker و SyncWorker
- `AutoSync` - مزامنة تلقائية عند بدء التطبيق
- جدول `sync_queue` في SQLite لتخزين العمليات المعلقة

### ❌ ما ينقص:
- `ConflictResolver` - آلية حل التعارضات
- Exponential Backoff محسّن
- جدول `conflict_log` لتسجيل التعارضات
- `SyncStatusWidget` - واجهة عرض حالة المزامنة
- تحسين ConnectionChecker للفحص السريع

---

## Phase 1: Conflict Resolution System (الأولوية: عالية) ✅ مكتمل

### Task 1.1: إنشاء جدول conflict_log ✅
- [x] إضافة migration لإنشاء جدول `conflict_log` في SQLite
- [x] إضافة indexes للبحث السريع

### Task 1.2: إنشاء ConflictResolver class ✅
- [x] إنشاء ملف `core/conflict_resolver.py`
- [x] تنفيذ `detect_and_resolve()` - كشف وحل التعارض
- [x] تنفيذ Smart Field-Level Merge:
  - دمج تلقائي للحقول غير الحساسة
  - تسجيل للمراجعة للحقول الحساسة (amount, quantity, items)
- [x] تنفيذ `log_conflict()` - تسجيل التعارض للمراجعة
- [x] تنفيذ `get_pending_conflicts()` - جلب التعارضات المعلقة
- [x] تنفيذ `resolve_conflict_manually()` - حل يدوي

### Task 1.3: دمج ConflictResolver مع SyncManager ✅
- [x] إنشاء `core/smart_sync_manager.py` - مدير مزامنة ذكي
- [x] تنفيذ `smart_pull_and_merge()` مع حل التعارضات
- [x] إضافة إشارات PyQt للتعارضات (conflict_detected, critical_conflict)
- [x] تصدير الـ modules في `core/__init__.py`

### الملفات المُنشأة:
- `core/conflict_resolver.py` - نظام حل التعارضات
- `core/smart_sync_manager.py` - مدير المزامنة الذكي

---

## Phase 2: Enhanced Connection Checker (الأولوية: عالية)

### Task 2.1: تحسين ConnectionChecker
- [ ] تقليل `check_interval` من 10 إلى 5 ثواني
- [ ] إضافة `quick_check_interval` = 2 ثواني بعد فقدان الاتصال
- [ ] استخدام multiple endpoints للفحص (Google DNS, MongoDB, custom endpoint)
- [ ] إضافة timeout أقصر (3 ثواني بدلاً من 5)

### Task 2.2: إضافة Network Quality Detection
- [ ] قياس latency للاتصال
- [ ] تصنيف جودة الاتصال (excellent, good, poor)
- [ ] تعديل سلوك المزامنة حسب جودة الاتصال

---

## Phase 3: Exponential Backoff Enhancement (الأولوية: متوسطة)

### Task 3.1: تحسين آلية إعادة المحاولة
- [ ] تعديل `SyncWorker._sync_with_retry()` لاستخدام exponential backoff
- [ ] delays = [1, 2, 4, 8, 16] ثواني
- [ ] إضافة jitter لتجنب thundering herd
- [ ] تسجيل كل محاولة فاشلة

### Task 3.2: Smart Retry Logic
- [ ] تصنيف الأخطاء (network, server, validation)
- [ ] إعادة المحاولة فقط للأخطاء القابلة للاسترداد
- [ ] إيقاف المحاولات للأخطاء الدائمة (validation errors)

---

## Phase 4: Sync Status Widget (الأولوية: متوسطة)

### Task 4.1: إنشاء SyncStatusWidget
- [ ] إنشاء ملف `ui/widgets/sync_status_widget.py`
- [ ] تصميم الـ widget:
  - 🟢/🔴 مؤشر الاتصال
  - نص الحالة (متصل/غير متصل/جاري المزامنة)
  - badge لعدد العمليات المعلقة
  - شريط تقدم للمزامنة

### Task 4.2: دمج Widget مع MainWindow
- [ ] إضافة SyncStatusWidget إلى Status Bar
- [ ] ربط الإشارات من AdvancedSyncManager
- [ ] إضافة قائمة منسدلة بتفاصيل المزامنة

### Task 4.3: إضافة Notifications
- [ ] إشعار عند فقدان الاتصال
- [ ] إشعار عند استعادة الاتصال
- [ ] إشعار عند اكتمال المزامنة
- [ ] إشعار عند حدوث تعارض حرج

---

## Phase 5: Data Integrity & Transactions (الأولوية: عالية)

### Task 5.1: تحسين Batch Sync
- [ ] استخدام transactions لكل batch
- [ ] rollback عند فشل أي عملية في الـ batch
- [ ] تسجيل حالة كل batch

### Task 5.2: Data Validation
- [ ] إضافة validation قبل الدمج
- [ ] التحقق من required fields
- [ ] التحقق من data types
- [ ] تسجيل validation errors

---

## Phase 6: Testing & Documentation (الأولوية: منخفضة)

### Task 6.1: Unit Tests
- [ ] اختبار ConflictResolver
- [ ] اختبار ConnectionChecker
- [ ] اختبار Exponential Backoff
- [ ] اختبار SyncStatusWidget

### Task 6.2: Integration Tests
- [ ] اختبار دورة المزامنة الكاملة
- [ ] اختبار سيناريو offline → online
- [ ] اختبار حل التعارضات

---

## ملخص الأولويات

| Phase | الوصف | الأولوية | الوقت المقدر |
|-------|-------|----------|--------------|
| 1 | Conflict Resolution | 🔴 عالية | 4-6 ساعات |
| 2 | Enhanced Connection | 🔴 عالية | 2-3 ساعات |
| 3 | Exponential Backoff | 🟡 متوسطة | 2-3 ساعات |
| 4 | Sync Status Widget | 🟡 متوسطة | 3-4 ساعات |
| 5 | Data Integrity | 🔴 عالية | 3-4 ساعات |
| 6 | Testing | 🟢 منخفضة | 4-6 ساعات |

**المجموع المقدر: 18-26 ساعة عمل**

---

## خطة البدء المقترحة

1. **اليوم الأول**: Phase 1 (ConflictResolver) + Phase 5 (Data Integrity)
2. **اليوم الثاني**: Phase 2 (ConnectionChecker) + Phase 3 (Backoff)
3. **اليوم الثالث**: Phase 4 (UI Widget) + Phase 6 (Testing)
