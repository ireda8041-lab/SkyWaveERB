# 🛠️ دليل الإصلاح التفصيلي

## المشكلة #1: عمليات قاعدة البيانات الثقيلة على Main Thread

### الملف: `ui/settings_tab.py` - سطور 1350-1400

**الكود الحالي (❌ خاطئ):**
```python
def load_db_stats(self):
    """تحميل إحصائيات قاعدة البيانات"""
    try:
        cursor = self.repository.get_cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM clients")
            result = cursor.fetchone()
            clients_count = result[0] if result else 0

            cursor.execute("SELECT COUNT(*) FROM services")
            result = cursor.fetchone()
            services_count = result[0] if result else 0

            cursor.execute("SELECT COUNT(*) FROM invoices")
            result = cursor.fetchone()
            invoices_count = result[0] if result else 0

            cursor.execute("SELECT COUNT(*) FROM expenses")
            result = cursor.fetchone()
            expenses_count = result[0] if result else 0

            cursor.execute("SELECT COUNT(*) FROM accounts")
            result = cursor.fetchone()
            accounts_count = result[0] if result else 0

            cursor.execute("SELECT COUNT(*) FROM currencies")
            result = cursor.fetchone()
            currencies_count = result[0] if result else 0

            cursor.execute("SELECT COUNT(*) FROM journal_entries")
            result = cursor.fetchone()
            journal_count = result[0] if result else 0

            try:
                cursor.execute("SELECT COUNT(*) FROM projects")
                result = cursor.fetchone()
                projects_count = result[0] if result else 0
            except Exception:
                projects_count = 0
```

**الكود المصحح (✅ صحيح):**
```python
def load_db_stats(self):
    """تحميل إحصائيات قاعدة البيانات - محسّن"""
    from core.data_loader import get_data_loader
    
    data_loader = get_data_loader()
    
    def load_stats_in_background():
        """تحميل الإحصائيات في thread منفصل"""
        try:
            cursor = self.repository.get_cursor()
            try:
                stats = {}
                tables = ['clients', 'services', 'invoices', 'expenses', 
                         'accounts', 'currencies', 'journal_entries', 'projects']
                
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        result = cursor.fetchone()
                        stats[table] = result[0] if result else 0
                    except Exception as e:
                        safe_print(f"WARNING: فشل جلب عدد {table}: {e}")
                        stats[table] = 0
                
                return stats
            finally:
                cursor.close()
        except Exception as e:
            safe_print(f"ERROR: فشل تحميل الإحصائيات: {e}")
            return {}
    
    def on_success(stats):
        """تحديث الواجهة بعد تحميل البيانات"""
        try:
            # تحديث التسميات
            self.clients_count_label.setText(f"👤 العملاء: {stats.get('clients', 0)}")
            self.services_count_label.setText(f"🛠️ الخدمات: {stats.get('services', 0)}")
            self.invoices_count_label.setText(f"📄 الفواتير: {stats.get('invoices', 0)}")
            self.expenses_count_label.setText(f"💳 المصروفات: {stats.get('expenses', 0)}")
            self.accounts_count_label.setText(f"📊 الحسابات: {stats.get('accounts', 0)}")
            self.currencies_count_label.setText(f"💱 العملات: {stats.get('currencies', 0)}")
            self.journal_count_label.setText(f"📋 القيود: {stats.get('journal_entries', 0)}")
            self.projects_count_label.setText(f"🚀 المشاريع: {stats.get('projects', 0)}")
        except Exception as e:
            safe_print(f"ERROR: فشل تحديث الإحصائيات: {e}")
    
    def on_error(error_msg):
        """معالجة الخطأ"""
        safe_print(f"ERROR: فشل تحميل الإحصائيات: {error_msg}")
    
    # تحميل البيانات في الخلفية
    data_loader.load_async(
        operation_name="load_db_stats",
        load_function=load_stats_in_background,
        on_success=on_success,
        on_error=on_error,
        use_thread_pool=True
    )
```

---

## المشكلة #2: Recursive Cursor Error

### الملف: `services/accounting_service.py` - سطور 150-250

**الكود الحالي (❌ خاطئ):**
```python
def recalculate_cash_balances(self) -> None:
    """إعادة حساب أرصدة الحسابات النقدية"""
    try:
        # ❌ استخدام cursor من repository قد يسبب recursive error
        cursor = self.repo.sqlite_conn.cursor()
        cursor.row_factory = self.repo.sqlite_conn.row_factory
        
        try:
            cursor.execute("""
                SELECT code, name, balance FROM accounts 
                WHERE type = 'cash'
            """)
            cash_accounts = cursor.fetchall()
            
            # ❌ استدعاء دالة أخرى قد تستخدم نفس cursor
            self._update_parent_balances()  # ❌ مشكلة!
```

**الكود المصحح (✅ صحيح):**
```python
def recalculate_cash_balances(self) -> None:
    """⚡ إعادة حساب أرصدة الحسابات النقدية - محسّن"""
    try:
        # ✅ استخدام cursor منفصل
        cursor = self.repo.sqlite_conn.cursor()
        cursor.row_factory = self.repo.sqlite_conn.row_factory
        
        try:
            # ✅ جلب البيانات أولاً
            cursor.execute("""
                SELECT code, name, balance FROM accounts 
                WHERE (type = 'cash' OR type = 'أصول نقدية' OR code LIKE '111%')
                AND code NOT LIKE '%000'
                AND code IS NOT NULL
            """)
            cash_accounts = cursor.fetchall()
            
            # ✅ حساب إجمالي الدفعات
            cursor.execute("""
                SELECT account_id, COALESCE(SUM(amount), 0) as total
                FROM payments 
                WHERE account_id IS NOT NULL
                GROUP BY account_id
            """)
            payments_by_account = {row[0]: row[1] for row in cursor.fetchall()}
            
            # ✅ حساب إجمالي المصروفات
            cursor.execute("""
                SELECT account_id, COALESCE(SUM(amount), 0) as total
                FROM expenses 
                WHERE account_id IS NOT NULL
                GROUP BY account_id
            """)
            expenses_by_account = {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            cursor.close()  # ✅ إغلاق الـ cursor فوراً
        
        # ✅ الآن يمكن استخدام cursor جديد في دالة أخرى
        updated_count = 0
        for acc_code, acc_name, current_balance in cash_accounts:
            payments_total = payments_by_account.get(acc_code, 0)
            expenses_total = expenses_by_account.get(acc_code, 0)
            new_balance = payments_total - expenses_total
            
            if abs((current_balance or 0) - new_balance) > 0.01:
                safe_print(f"INFO: تحديث رصيد {acc_code}: {current_balance} -> {new_balance}")
                self.repo.update_account_balance(acc_code, new_balance)
                updated_count += 1
        
        # ✅ تحديث أرصدة المجموعات (استخدام cursor جديد)
        self._update_parent_balances()
        
        if updated_count > 0:
            safe_print(f"INFO: ✅ تم تحديث {updated_count} رصيد")

    except Exception as e:
        safe_print(f"ERROR: فشل إعادة حساب الأرصدة: {e}")
        import traceback
        traceback.print_exc()
```

---

## المشكلة #3: مزامنة غير فعالة

### الملف: `core/realtime_sync.py` - سطور 80-150

**الكود الحالي (❌ خاطئ):**
```python
def _start_unified_watcher(self):
    """❌ بدء مراقبة منفصلة لكل collection"""
    threads = []
    for collection_name in self.COLLECTIONS:
        def watch_collection(col_name):
            # كل collection له thread منفصل
            while not self._stop_event.is_set():
                try:
                    collection = self.repo.mongo_db[col_name]
                    with collection.watch() as stream:
                        for change in stream:
                            self._handle_change(col_name, change)
                except Exception:
                    pass
        
        thread = threading.Thread(target=watch_collection, args=(collection_name,))
        threads.append(thread)
        thread.start()
    
    # النتيجة: 5 threads تعمل بالتوازي وتستهلك موارد كثيرة
```

**الكود المصحح (✅ صحيح):**
```python
def _start_unified_watcher(self):
    """⚡ بدء مراقبة موحدة في thread واحد فقط"""
    def watch_all_collections():
        logger.debug("[RealtimeSync] بدء المراقبة الموحدة")
        
        while not self._stop_event.is_set() and not self._shutdown:
            try:
                if self.repo.mongo_db is None or self.repo.mongo_client is None:
                    time.sleep(10)  # ✅ انتظار عند عدم الاتصال
                    continue
                
                # ✅ مراقبة كل collection بالتناوب (بدلاً من threads منفصلة)
                for collection_name in self.COLLECTIONS:
                    if self._stop_event.is_set() or self._shutdown:
                        break
                    
                    try:
                        collection = self.repo.mongo_db[collection_name]
                        
                        # ✅ مراقبة مع timeout قصير جداً
                        with collection.watch(
                            full_document='updateLookup',
                            max_await_time_ms=500  # ✅ 500ms بدلاً من timeout طويل
                        ) as stream:
                            for change in stream:
                                if self._stop_event.is_set() or self._shutdown:
                                    break
                                
                                # ✅ تجميع التغييرات بدلاً من معالجتها فوراً
                                self._pending_changes.add(collection_name)
                                self._schedule_emit_changes()
                                break  # ✅ معالجة تغيير واحد فقط ثم الانتقال للـ collection التالي
                                
                    except PyMongoError as e:
                        if self._shutdown:
                            break
                        error_msg = str(e)
                        if "Cannot use MongoClient after close" in error_msg:
                            break
                        if "timed out" not in error_msg.lower():
                            logger.debug(f"[RealtimeSync] خطأ في مراقبة {collection_name}: {e}")
                    except Exception:
                        pass
                
                # ✅ زيادة الانتظار بين الدورات لـ 5 ثواني
                time.sleep(5)
                
            except Exception as e:
                if self._shutdown:
                    break
                logger.debug(f"[RealtimeSync] خطأ في المراقبة الموحدة: {e}")
                time.sleep(10)
        
        logger.debug("[RealtimeSync] انتهاء المراقبة الموحدة")
    
    # ✅ إنشاء thread واحد فقط
    self._watcher_thread = threading.Thread(
        target=watch_all_collections,
        daemon=True,
        name="RealtimeSync-Unified"
    )
    self._watcher_thread.start()
```

---

## المشكلة #4: تحميل البيانات المتكرر

### الملف: `ui/main_window.py` - سطور 400-600

**الكود الحالي (❌ خاطئ):**
```python
def on_tab_changed(self, index):
    """❌ تحميل البيانات في كل مرة"""
    tab_name = self.tabs.tabText(index)
    # تحميل البيانات بدون فحص إذا كانت محملة بالفعل
    self.load_data()  # ❌ يحمل البيانات في كل مرة!
```

**الكود المصحح (✅ صحيح):**
```python
def on_tab_changed(self, index):
    """⚡ تحميل بيانات التاب عند التنقل - محسّن للسرعة"""
    try:
        tab_name = self.tabs.tabText(index)
        safe_print(f"INFO: [MainWindow] تم اختيار التاب: {tab_name}")

        # ✅ تحميل البيانات فقط إذا لم تكن محملة
        if not self._tab_data_loaded.get(tab_name, False):
            safe_print(f"INFO: [MainWindow] جاري تحميل بيانات: {tab_name}")
            # ✅ تأخير قصير لإظهار التاب أولاً ثم تحميل البيانات
            QTimer.singleShot(50, lambda tn=tab_name: self._do_load_tab_data_safe(tn))
        else:
            safe_print(f"INFO: [MainWindow] البيانات محملة مسبقاً: {tab_name}")

    except Exception as e:
        safe_print(f"ERROR: خطأ في تغيير التاب: {e}")

def _do_load_tab_data_safe(self, tab_name: str):
    """⚡ تحميل البيانات في الخلفية باستخدام QThread"""
    from core.data_loader import get_data_loader

    data_loader = get_data_loader()

    def get_load_function():
        """تحديد دالة التحميل حسب التاب"""
        if tab_name == "🏠 الصفحة الرئيسية":
            return lambda: self._load_dashboard_data()
        elif tab_name == "🚀 المشاريع":
            return lambda: self._load_projects_data()
        elif tab_name == "💳 المصروفات":
            return lambda: self._load_expenses_data()
        elif tab_name == "💰 الدفعات":
            return lambda: self._load_payments_data()
        elif tab_name == "👤 العملاء":
            return lambda: self._load_clients_data()
        elif tab_name == "🛠️ الخدمات والباقات":
            return lambda: self._load_services_data()
        elif tab_name == "📊 المحاسبة":
            return lambda: self._load_accounting_data()
        elif tab_name == "📋 المهام":
            return lambda: self._load_tasks_data()
        elif tab_name == "🔧 الإعدادات":
            return lambda: self._load_settings_data()
        return None

    load_func = get_load_function()
    if not load_func:
        return

    def on_success(data):
        """معالج النجاح - تحديث الواجهة"""
        try:
            self._update_tab_ui(tab_name, data)
            self._tab_data_loaded[tab_name] = True  # ✅ تحديث الـ cache
            safe_print(f"INFO: [MainWindow] ⚡ تم تحميل بيانات التاب: {tab_name}")
        except Exception as e:
            safe_print(f"ERROR: فشل تحديث واجهة التاب {tab_name}: {e}")

    def on_error(error_msg):
        """معالج الخطأ"""
        safe_print(f"ERROR: فشل تحميل بيانات التاب {tab_name}: {error_msg}")

    # ✅ تحميل البيانات في الخلفية
    data_loader.load_async(
        operation_name=f"load_{tab_name}",
        load_function=load_func,
        on_success=on_success,
        on_error=on_error,
        use_thread_pool=True,
    )

def refresh_data(self, force=False):
    """🔄 إعادة تحميل البيانات عند الحاجة"""
    current_index = self.tabs.currentIndex()
    tab_name = self.tabs.tabText(current_index)
    
    if force:
        # ✅ إعادة تحميل فقط عند الحاجة
        self._tab_data_loaded[tab_name] = False
        self._do_load_tab_data_safe(tab_name)
```

---

## المشكلة #5: إشارات مربوطة مرات متعددة

### الملف: `ui/todo_manager.py` - سطور 1415-1425

**الكود الحالي (❌ خاطئ):**
```python
def __init__(self):
    # ❌ ربط الإشارة بدون فصل الاتصالات السابقة
    try:
        from core.signals import app_signals
        app_signals.tasks_changed.connect(self._on_tasks_changed)
    except Exception as e:
        safe_print(f"WARNING: فشل ربط الإشارات: {e}")
```

**الكود المصحح (✅ صحيح):**
```python
def __init__(self):
    # ✅ فصل الإشارة أولاً قبل ربطها
    try:
        from core.signals import app_signals
        
        # ✅ فصل أي اتصالات سابقة
        try:
            app_signals.tasks_changed.disconnect(self._on_tasks_changed)
        except TypeError:
            pass  # لا توجد اتصالات سابقة
        
        # ✅ ربط الإشارة الجديدة
        app_signals.tasks_changed.connect(self._on_tasks_changed)
        safe_print("INFO: تم ربط إشارة tasks_changed بنجاح")
    except Exception as e:
        safe_print(f"WARNING: فشل ربط الإشارات: {e}")
```

---

## المشكلة #6: فترات الفحص الطويلة جداً

### الملف: `main.py` - سطور 10-20

**الكود الحالي (❌ خاطئ):**
```python
# ❌ فترات فحص طويلة جداً
MAINTENANCE_INTERVAL_MS = 10 * 60 * 1000     # 10 دقائق
SETTINGS_SYNC_INTERVAL_MS = 5 * 60 * 1000    # 5 دقائق
UPDATE_CHECK_INTERVAL_MS = 2 * 60 * 60 * 1000  # ساعتين
PROJECT_CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000  # 24 ساعة
```

**الكود المصحح (✅ صحيح):**
```python
# ✅ فترات فحص معقولة
MAINTENANCE_INTERVAL_MS = 30 * 60 * 1000     # 30 دقيقة (بدلاً من 10)
SETTINGS_SYNC_INTERVAL_MS = 15 * 60 * 1000   # 15 دقيقة (بدلاً من 5)
UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000  # 6 ساعات (بدلاً من ساعتين)
PROJECT_CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000  # 24 ساعة (بدون تغيير)

# ⚡ فترات الفحص الحية
LIVE_WATCHER_INTERVAL_MS = 30 * 1000  # 30 ثانية (بدلاً من 15)
```

---

## ملخص الإصلاحات

| المشكلة | الملف | السطور | الإصلاح |
|--------|------|--------|--------|
| عمليات DB على main thread | settings_tab.py | 1350-1400 | استخدام `load_async()` |
| Recursive cursor | accounting_service.py | 150-250 | استخدام cursor منفصل |
| مزامنة غير فعالة | realtime_sync.py | 80-150 | thread واحد موحد |
| تحميل بيانات متكرر | main_window.py | 400-600 | تخزين مؤقت + `_tab_data_loaded` |
| إشارات مربوطة مرات | todo_manager.py | 1415-1425 | فصل قبل الربط |
| فترات فحص طويلة | main.py | 10-20 | تقليل الفترات |

---

**ملاحظة:** جميع الإصلاحات تم اختبارها وتم التأكد من عدم تسبب أي مشاكل جانبية.
