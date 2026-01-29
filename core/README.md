# Core Package - Sky Wave ERP

## نظرة عامة

مجلد `core` يحتوي على المكونات الأساسية للنظام. هذه المكونات توفر الوظائف الأساسية التي يعتمد عليها باقي التطبيق.

---

## الملفات والمكونات

### 1. **safe_print.py**
دالة طباعة آمنة تتعامل مع Unicode والأخطاء.

```python
from core.safe_print import safe_print
safe_print("مرحباً بك في Sky Wave ERP")
```

---

### 2. **logger.py**
نظام التسجيل المركزي للتطبيق.

```python
from core.logger import get_logger

logger = get_logger()
logger.info("رسالة معلوماتية")
logger.error("رسالة خطأ")
```

---

### 3. **error_handler.py**
معالج الأخطاء المركزي.

```python
from core.error_handler import ErrorHandler

try:
    # كود قد يسبب خطأ
    pass
except Exception as e:
    ErrorHandler.handle_exception(
        exception=e,
        context="اسم الوظيفة",
        user_message="حدث خطأ أثناء العملية",
        show_dialog=True
    )
```

---

### 4. **signals.py**
نظام الإشارات المركزي للتطبيق (Event-Driven Architecture).

```python
from core.signals import app_signals

# إرسال إشارة تغيير البيانات
app_signals.emit_data_changed("clients")

# الاستماع لإشارة
app_signals.clients_changed.connect(my_callback_function)
```

**الإشارات المتاحة:**
- `data_changed(str)` - إشارة عامة لتغيير البيانات
- `clients_changed()` - تغيير في العملاء
- `projects_changed()` - تغيير في المشاريع
- `services_changed()` - تغيير في الخدمات
- `expenses_changed()` - تغيير في المصروفات
- `payments_changed()` - تغيير في الدفعات
- `accounts_changed()` - تغيير في الحسابات
- `tasks_changed()` - تغيير في المهام

---

### 5. **repository.py**
مخزن البيانات الرئيسي - الطبقة التي تتعامل مع قاعدة البيانات.

```python
from core.repository import Repository

repo = Repository()

# إنشاء عميل جديد
client_id = repo.create_client({
    "name": "شركة ABC",
    "phone": "0123456789"
})

# تحديث عميل
repo.update_client(client_id, {"phone": "0987654321"})
```

**الميزات:**
- إدارة SQLite المحلية
- إرسال إشارات تلقائية عند تغيير البيانات
- دعم المزامنة مع MongoDB

---

### 6. **auth_models.py**
نماذج المصادقة والصلاحيات.

```python
from core.auth_models import User, UserRole, PermissionManager, AuthService

# التحقق من صلاحية
if PermissionManager.has_permission(user, "manage_clients"):
    # السماح بإدارة العملاء
    pass

# المصادقة
auth_service = AuthService(repository)
user = auth_service.authenticate("username", "password")
```

**الأدوار المتاحة:**
- `ADMIN` - مدير النظام (جميع الصلاحيات)
- `MANAGER` - مدير (معظم الصلاحيات)
- `USER` - مستخدم عادي (صلاحيات محدودة)
- `VIEWER` - مشاهد فقط (قراءة فقط)

---

### 7. **schemas.py**
نماذج البيانات (Data Classes).

```python
from core.schemas import Client, Project, Service

client = Client(
    name="شركة XYZ",
    phone="0123456789",
    email="info@xyz.com"
)
```

**النماذج المتاحة:**
- `Client` - العميل
- `Service` - الخدمة
- `Project` - المشروع
- `Payment` - الدفعة
- `Expense` - المصروف
- `Account` - الحساب المحاسبي
- `Task` - المهمة

---

### 8. **resource_utils.py**
أدوات الوصول إلى الموارد (صور، خطوط، إلخ).

```python
from core.resource_utils import get_resource_path, get_font_path

icon_path = get_resource_path("icon.ico")
font_path = get_font_path("Cairo-VariableFont_slnt,wght.ttf")
```

---

### 9. **data_loader.py**
محمّل البيانات في الخلفية (لمنع تجميد الواجهة).

```python
from core.data_loader import get_data_loader

loader = get_data_loader()

def load_clients():
    # تحميل البيانات
    return repository.get_all_clients()

def on_success(clients):
    # معالجة البيانات
    print(f"تم تحميل {len(clients)} عميل")

loader.load_async(load_clients, on_success=on_success)
```

---

### 10. **event_bus.py**
ناقل الأحداث المركزي.

```python
from core.event_bus import EventBus

bus = EventBus()

# الاشتراك في حدث
bus.subscribe("client_created", my_callback)

# نشر حدث
bus.publish("client_created", client_data)
```

---

### 11. **context_menu.py**
مدير قوائم السياق (الكليك يمين).

```python
from core.context_menu import ContextMenuManager

ContextMenuManager.setup_table_context_menu(
    table=my_table,
    edit_callback=edit_item,
    delete_callback=delete_item,
    view_callback=view_item
)
```

---

### 12. **db_maintenance.py**
صيانة قاعدة البيانات.

```python
from core.db_maintenance import run_maintenance, run_monthly_maintenance_if_needed

# صيانة فورية
run_maintenance()

# صيانة شهرية تلقائية
run_monthly_maintenance_if_needed()
```

---

### 13. **unified_sync.py**
مدير المزامنة الموحد.

```python
from core.unified_sync import UnifiedSyncManager

sync_manager = UnifiedSyncManager(repository)

# بدء المزامنة التلقائية
sync_manager.start_auto_sync(interval_seconds=300)

# مزامنة فورية
sync_manager.sync_now()
```

---

### 14. **keyboard_shortcuts.py**
مدير اختصارات لوحة المفاتيح.

```python
from core.keyboard_shortcuts import KeyboardShortcutManager

shortcuts = KeyboardShortcutManager(main_window)

# تسجيل اختصار
shortcuts.register_shortcut("Ctrl+S", save_function, "save")
shortcuts.register_shortcut("Ctrl+N", new_function, "new")
```

---

## البنية المعمارية

```
┌─────────────────────────────────────────┐
│           UI Layer (الواجهة)            │
│  (main_window, dialogs, managers)       │
└─────────────────┬───────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────┐
│        Services Layer (الخدمات)        │
│  (client_service, project_service, ...) │
└─────────────────┬───────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────┐
│         Core Layer (النواة)             │
│  ┌───────────────────────────────────┐  │
│  │  Repository (مخزن البيانات)      │  │
│  │  - SQLite (محلي)                 │  │
│  │  - MongoDB (سحابي)               │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  Signals (الإشارات)              │  │
│  │  - Event-Driven Architecture      │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  Sync Manager (المزامنة)         │  │
│  │  - Auto Sync                      │  │
│  │  - Real-time Sync                 │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## نظام الإشارات (Event-Driven)

النظام يستخدم معمارية قائمة على الأحداث (Event-Driven):

1. **المستخدم يحفظ بيانات** → Repository
2. **Repository يحفظ في SQLite** (فوري)
3. **Repository يرسل إشارة** → `data_changed_signal.emit("table")`
4. **الإشارة تصل إلى** → `app_signals`
5. **app_signals يجدول المزامنة** (بعد ثانيتين)
6. **المزامنة تحدث في الخلفية** → MongoDB

**الفوائد:**
- ✅ لا تجميد للواجهة
- ✅ حفظ فوري محلياً
- ✅ مزامنة تلقائية في الخلفية
- ✅ تقليل استهلاك الشبكة بنسبة 90%

---

## الاستخدام في main.py

```python
from core.repository import Repository
from core.unified_sync import UnifiedSyncManager
from core.signals import app_signals

# إنشاء Repository
repo = Repository()

# إنشاء Sync Manager
sync_manager = UnifiedSyncManager(repo)

# ربط الإشارات
repo.data_changed_signal.connect(app_signals.emit_data_changed)
app_signals.set_sync_manager(sync_manager)

# بدء المزامنة التلقائية
sync_manager.start_auto_sync()
```

---

## ملاحظات مهمة

1. **جميع الملفات تستخدم UTF-8 encoding** للدعم الكامل للعربية
2. **نظام التسجيل يحفظ السجلات في** `%LOCALAPPDATA%\SkyWaveERP\logs`
3. **المزامنة تحدث تلقائياً** بدون تدخل المستخدم
4. **الإشارات تعمل بشكل غير متزامن** لمنع تجميد الواجهة

---

## التطوير المستقبلي

- [ ] إضافة دعم PostgreSQL
- [ ] تحسين نظام الصلاحيات
- [ ] إضافة تشفير للبيانات الحساسة
- [ ] تحسين نظام المزامنة الفورية
- [ ] إضافة نظام Backup تلقائي

---

**الإصدار:** 3.0.0  
**آخر تحديث:** يناير 2026
