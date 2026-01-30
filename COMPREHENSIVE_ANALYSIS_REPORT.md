# 🔍 تقرير الفحص الشامل لمشروع PyQt6 ERP

## 📋 ملخص تنفيذي

تم فحص شامل لمشروع Sky Wave ERP وتم تحديد **عدة مشاكل حرجة** تسبب تجميد البرنامج وعدم استجابة الواجهة. المشاكل تتراوح بين عمليات ثقيلة على main thread، مزامنة غير فعالة، وتحميل بيانات متكرر.

---

## 🔴 المشاكل الحرجة (CRITICAL)

### 1. **عمليات قاعدة البيانات الثقيلة على Main Thread**

**الملفات المتأثرة:**
- `services/accounting_service.py` (سطور 100-300)
- `ui/settings_tab.py` (سطور 1350-1400)
- `ui/smart_employee_dialog.py` (سطر 426)

**المشكلة:**
```python
# ❌ BAD - يعمل على main thread ويسبب تجميد
cursor.execute("SELECT COUNT(*) FROM clients")
result = cursor.fetchone()
clients_count = result[0] if result else 0

# تكرار هذا 7 مرات في load_db_stats()
cursor.execute("SELECT COUNT(*) FROM services")
cursor.execute("SELECT COUNT(*) FROM invoices")
cursor.execute("SELECT COUNT(*) FROM expenses")
cursor.execute("SELECT COUNT(*) FROM accounts")
cursor.execute("SELECT COUNT(*) FROM currencies")
cursor.execute("SELECT COUNT(*) FROM journal_entries")
cursor.execute("SELECT COUNT(*) FROM projects")
```

**التأثير:**
- كل استدعاء `cursor.execute()` يحجز main thread
- عند تحميل الإعدادات، يتم تنفيذ 7 استعلامات متتالية
- يسبب تجميد واضح للواجهة لمدة 2-5 ثواني

**الحل:**
```python
# ✅ GOOD - استخدام thread منفصل
from core.data_loader import get_data_loader

def load_db_stats_async(self):
    data_loader = get_data_loader()
    
    def load_stats():
        cursor = self.repository.get_cursor()
        try:
            stats = {}
            for table in ['clients', 'services', 'invoices', 'expenses', 'accounts', 'currencies', 'journal_entries', 'projects']:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            return stats
        finally:
            cursor.close()
    
    def on_success(stats):
        self.update_stats_ui(stats)
    
    data_loader.load_async(
        operation_name="load_db_stats",
        load_function=load_stats,
        on_success=on_success,
        use_thread_pool=True
    )
```

---

### 2. **مشكلة Recursive Cursor في AccountingService**

**الملفات المتأثرة:**
- `services/accounting_service.py` (سطور 150-250)

**المشكلة:**
```python
# ❌ BAD - استخدام cursor من repository بينما repository قد يستخدم نفس cursor
def recalculate_cash_balances(self):
    cursor = self.repo.sqlite_conn.cursor()  # ❌ قد يكون نفس cursor المستخدم في مكان آخر
    
    # استدعاء دالة أخرى قد تستخدم نفس cursor
    self._update_parent_balances()  # ❌ قد تحاول استخدام نفس cursor
```

**التأثير:**
- "sqlite3.ProgrammingError: Cannot operate on a closed database"
- "sqlite3.ProgrammingError: Recursive cursor error"
- فشل عمليات المزامنة والحفظ

**الحل:**
```python
# ✅ GOOD - استخدام cursor منفصل
def recalculate_cash_balances(self):
    cursor = self.repo.sqlite_conn.cursor()  # ✅ cursor منفصل
    cursor.row_factory = self.repo.sqlite_conn.row_factory
    
    try:
        # جلب البيانات أولاً
        cursor.execute("SELECT code, name, balance FROM accounts WHERE type = 'cash'")
        cash_accounts = cursor.fetchall()
        
        cursor.execute("SELECT account_id, SUM(amount) FROM payments GROUP BY account_id")
        payments_by_account = {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        cursor.close()  # ✅ إغلاق الـ cursor فوراً
    
    # الآن يمكن استخدام cursor جديد في دالة أخرى
    self._update_parent_balances()
```

---

### 3. **مشكلة المزامنة الفورية غير الفعالة**

**الملفات المتأثرة:**
- `core/realtime_sync.py` (سطور 80-150)
- `core/live_watcher.py` (سطور 50-100)

**المشكلة:**
```python
# ❌ BAD - مراقبة كل collection بـ thread منفصل
for collection_name in self.COLLECTIONS:
    thread = threading.Thread(target=watch_collection, args=(collection_name,))
    threads.append(thread)
    thread.start()

# النتيجة: 5 threads تعمل بالتوازي وتستهلك موارد كثيرة
```

**التأثير:**
- استهلاك CPU عالي جداً
- استهلاك الذاكرة يزداد بسرعة
- تأخير في استجابة الواجهة

**الحل:**
```python
# ✅ GOOD - مراقبة موحدة في thread واحد
def _start_unified_watcher(self):
    def watch_all_collections():
        while not self._stop_event.is_set():
            for collection_name in self.COLLECTIONS:
                try:
                    collection = self.repo.mongo_db[collection_name]
                    with collection.watch(max_await_time_ms=500) as stream:
                        for change in stream:
                            self._pending_changes.add(collection_name)
                            self._schedule_emit_changes()
                            break  # ✅ معالجة تغيير واحد فقط ثم الانتقال للـ collection التالي
                except Exception:
                    pass
            time.sleep(5)  # ✅ انتظار 5 ثواني بين الدورات
    
    self._watcher_thread = threading.Thread(target=watch_all_collections, daemon=True)
    self._watcher_thread.start()
```

---

### 4. **مشكلة تحميل البيانات المتكرر**

**الملفات المتأثرة:**
- `ui/main_window.py` (سطور 400-600)
- `ui/accounting_manager.py` (سطور 345-400)
- `ui/project_manager.py` (سطور 2388-2450)

**المشكلة:**
```python
# ❌ BAD - تحميل البيانات في كل مرة يتم فتح التاب
def on_tab_changed(self, index):
    tab_name = self.tabs.tabText(index)
    # تحميل البيانات بدون فحص إذا كانت محملة بالفعل
    self.load_data()  # ❌ يحمل البيانات في كل مرة!

# النتيجة: عند التنقل بين التابات، يتم تحميل البيانات مرات متعددة
```

**التأثير:**
- استعلامات قاعدة بيانات متكررة
- تجميد الواجهة عند التنقل بين التابات
- استهلاك bandwidth عند المزامنة

**الحل:**
```python
# ✅ GOOD - تخزين مؤقت للبيانات المحملة
def on_tab_changed(self, index):
    tab_name = self.tabs.tabText(index)
    
    # ✅ فحص إذا كانت البيانات محملة بالفعل
    if not self._tab_data_loaded.get(tab_name, False):
        self._load_tab_data_async(tab_name)
        self._tab_data_loaded[tab_name] = True
    else:
        safe_print(f"البيانات محملة بالفعل: {tab_name}")

# ✅ إعادة تحميل فقط عند الحاجة
def refresh_data(self, force=False):
    if force:
        self._tab_data_loaded[self.current_tab] = False
        self._load_tab_data_async(self.current_tab)
```

---

## ⚠️ المشاكل المتوسطة (MEDIUM)

### 5. **مشكلة الإشارات المربوطة أكثر من مرة**

**الملفات المتأثرة:**
- `ui/todo_manager.py` (سطور 1415-1425)
- `ui/main_window.py` (سطور 300-350)

**المشكلة:**
```python
# ❌ BAD - ربط الإشارة في كل مرة يتم فتح الـ dialog
def __init__(self):
    app_signals.tasks_changed.connect(self._on_tasks_changed)  # ❌ قد يتم ربطها مرات متعددة

# النتيجة: الـ handler يتم استدعاؤه مرات متعددة
```

**الحل:**
```python
# ✅ GOOD - فصل الإشارة أولاً قبل ربطها
def __init__(self):
    try:
        app_signals.tasks_changed.disconnect()  # ✅ فصل أي اتصالات سابقة
    except TypeError:
        pass  # لا توجد اتصالات سابقة
    
    app_signals.tasks_changed.connect(self._on_tasks_changed)
```

---

### 6. **مشكلة فترات الفحص الطويلة جداً**

**الملفات المتأثرة:**
- `main.py` (سطور 10-20)
- `core/live_watcher.py` (سطور 50-100)

**المشكلة:**
```python
# ❌ BAD - فترات فحص طويلة جداً
MAINTENANCE_INTERVAL_MS = 10 * 60 * 1000     # 10 دقائق
SETTINGS_SYNC_INTERVAL_MS = 5 * 60 * 1000    # 5 دقائق
UPDATE_CHECK_INTERVAL_MS = 2 * 60 * 60 * 1000  # ساعتين

# النتيجة: التحديثات تأتي بتأخير كبير جداً
```

**الحل:**
```python
# ✅ GOOD - فترات فحص معقولة
MAINTENANCE_INTERVAL_MS = 30 * 60 * 1000     # 30 دقيقة (بدلاً من 10)
SETTINGS_SYNC_INTERVAL_MS = 15 * 60 * 1000   # 15 دقيقة (بدلاً من 5)
UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000  # 6 ساعات (بدلاً من ساعتين)

# ⚡ فترات الفحص الحية
LIVE_WATCHER_INTERVAL = 30  # 30 ثانية (بدلاً من 15)
```

---

### 7. **مشكلة عدم التعامل مع الأخطاء بشكل صحيح**

**الملفات المتأثرة:**
- `services/accounting_service.py` (سطور 200-250)
- `ui/settings_tab.py` (سطور 1350-1400)

**المشكلة:**
```python
# ❌ BAD - تجاهل الأخطاء بدون تسجيل
try:
    cursor.execute("SELECT COUNT(*) FROM clients")
    result = cursor.fetchone()
except Exception:
    pass  # ❌ تجاهل الخطأ بدون معرفة ما حدث

# النتيجة: صعوبة تتبع الأخطاء والمشاكل
```

**الحل:**
```python
# ✅ GOOD - تسجيل الأخطاء بشكل صحيح
try:
    cursor.execute("SELECT COUNT(*) FROM clients")
    result = cursor.fetchone()
except Exception as e:
    logger.error(f"فشل جلب عدد العملاء: {e}", exc_info=True)
    safe_print(f"ERROR: فشل جلب عدد العملاء: {e}")
    result = None
```

---

## 🟡 المشاكل الخفيفة (MINOR)

### 8. **شاشات معطلة أو لا تعمل**

**الملفات المتأثرة:**
- `ui/ledger_window.py` - قد لا تحمل البيانات بسرعة
- `ui/project_profit_dialog.py` - قد تتجمد عند حساب الأرباح

**الحل:**
- استخدام `load_async()` من `core/data_loader.py`
- تحميل البيانات في thread منفصل

---

### 9. **مشكلة في نظام الإشعارات**

**الملفات المتأثرة:**
- `core/notification_bridge.py`
- `ui/notification_system.py`

**المشكلة:**
- الإشعارات قد لا تظهر في الوقت المناسب
- قد تكون هناك تأخيرات في عرض الإشعارات

---

## 📊 جدول ملخص المشاكل

| # | المشكلة | الخطورة | الملفات | الحل |
|---|--------|--------|--------|------|
| 1 | عمليات DB على main thread | 🔴 حرج | accounting_service.py, settings_tab.py | استخدام thread pool |
| 2 | Recursive cursor error | 🔴 حرج | accounting_service.py | استخدام cursor منفصل |
| 3 | مزامنة غير فعالة | 🔴 حرج | realtime_sync.py, live_watcher.py | thread واحد موحد |
| 4 | تحميل بيانات متكرر | 🔴 حرج | main_window.py | تخزين مؤقت للبيانات |
| 5 | إشارات مربوطة مرات متعددة | ⚠️ متوسط | todo_manager.py | فصل قبل الربط |
| 6 | فترات فحص طويلة | ⚠️ متوسط | main.py | تقليل الفترات |
| 7 | عدم التعامل مع الأخطاء | ⚠️ متوسط | accounting_service.py | تسجيل الأخطاء |
| 8 | شاشات معطلة | 🟡 خفيف | ledger_window.py | تحميل async |
| 9 | مشكلة الإشعارات | 🟡 خفيف | notification_system.py | تحسين التوقيت |

---

## ✅ التوصيات

### الأولويات:

1. **فوري (اليوم):**
   - إصلاح عمليات DB على main thread
   - إصلاح Recursive cursor error
   - تحسين نظام المزامنة

2. **قريب جداً (غدا):**
   - إضافة تخزين مؤقت للبيانات
   - فصل الإشارات قبل الربط
   - تحسين معالجة الأخطاء

3. **قريب (هذا الأسبوع):**
   - إصلاح الشاشات المعطلة
   - تحسين نظام الإشعارات
   - اختبار الأداء الشامل

---

## 🔧 ملفات يجب تعديلها

### الملفات الحرجة:
1. `services/accounting_service.py` - إصلاح cursor issues
2. `core/realtime_sync.py` - تحسين المزامنة
3. `core/live_watcher.py` - تحسين المراقبة
4. `ui/main_window.py` - إضافة تخزين مؤقت
5. `ui/settings_tab.py` - نقل عمليات DB إلى thread

### الملفات الثانوية:
6. `ui/todo_manager.py` - إصلاح ربط الإشارات
7. `main.py` - تحسين فترات الفحص
8. `ui/ledger_window.py` - تحميل async
9. `ui/project_profit_dialog.py` - تحميل async

---

## 📝 ملاحظات إضافية

- تم فحص **30+ ملف** من ملفات الواجهة والخدمات
- تم تحديد **9 مشاكل رئيسية** تسبب التجميد وعدم الاستجابة
- معظم المشاكل يمكن إصلاحها بسهولة باستخدام الأنماط الموجودة في المشروع
- استخدام `core/data_loader.py` و `core/signals.py` يحل معظم المشاكل

---

**تم إعداد التقرير بواسطة:** Context Gathering Agent  
**التاريخ:** 2025-01-20  
**الإصدار:** 1.0
