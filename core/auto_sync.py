# الملف: core/auto_sync.py
"""
نظام المزامنة التلقائية (Auto Sync)
يقوم بـ Pull & Push تلقائياً عند بدء البرنامج
"""

import threading
import time
from datetime import datetime
from typing import Optional
import json


class AutoSync:
    """
    ⚡ مدير المزامنة التلقائية - محسّن للسرعة
    - Pull: جلب البيانات من MongoDB إلى SQLite
    - Push: رفع البيانات من SQLite إلى MongoDB
    """
    
    def __init__(self, repository):
        """
        تهيئة المزامنة التلقائية
        
        Args:
            repository: كائن Repository للوصول للبيانات
        """
        self.repository = repository
        self.is_syncing = False
        self.is_running = False  # ✅ للتحكم في إيقاف المزامنة
        self.last_sync_time = None
        self.sync_stats = {
            'pulled': 0,
            'pushed': 0,
            'failed': 0
        }
        self._batch_size = 50  # ⚡ حجم الدفعة للمزامنة
        self._sync_thread = None  # ✅ مرجع للـ thread
    
    def start_auto_sync(self, delay_seconds: int = 3):
        """
        ⚡ بدء المزامنة التلقائية في الخلفية (محسّن)
        
        Args:
            delay_seconds: التأخير قبل بدء المزامنة (بالثواني)
        """
        self.is_running = True
        
        def sync_worker():
            time.sleep(delay_seconds)
            if not self.is_running:
                print("INFO: [AutoSync] تم إلغاء المزامنة قبل البدء")
                return
            print("INFO: [AutoSync] ⚡ بدء المزامنة السريعة...")
            self.perform_sync()
        
        # تشغيل في thread منفصل بأولوية منخفضة
        self._sync_thread = threading.Thread(
            target=sync_worker, 
            daemon=True, 
            name="AutoSyncThread"
        )
        self._sync_thread.start()
        print(f"INFO: [AutoSync] ⚡ جدولة المزامنة (بعد {delay_seconds} ثانية)")
    
    def stop_auto_sync(self):
        """✅ إيقاف المزامنة التلقائية"""
        print("INFO: [AutoSync] جاري إيقاف المزامنة التلقائية...")
        self.is_running = False
        self.is_syncing = False
        
        # انتظار انتهاء الـ thread إذا كان يعمل
        if self._sync_thread and self._sync_thread.is_alive():
            try:
                self._sync_thread.join(timeout=2.0)  # انتظار 2 ثانية كحد أقصى
            except Exception as e:
                print(f"WARNING: [AutoSync] فشل انتظار انتهاء thread: {e}")
        
        print("INFO: [AutoSync] ✅ تم إيقاف المزامنة التلقائية")
    
    def perform_sync(self):
        """تنفيذ المزامنة الكاملة (Pull ثم Push)"""
        if self.is_syncing:
            print("WARNING: [AutoSync] المزامنة جارية بالفعل")
            return
        
        if not self.is_running:
            print("INFO: [AutoSync] المزامنة متوقفة - تم إلغاء العملية")
            return
        
        self.is_syncing = True
        start_time = time.time()
        
        try:
            # التحقق من الاتصال
            if not self.repository.online:
                print("WARNING: [AutoSync] لا يوجد اتصال بالإنترنت - تم إلغاء المزامنة")
                return
            
            # التحقق من أن المزامنة لا تزال مطلوبة
            if not self.is_running:
                print("INFO: [AutoSync] تم إيقاف المزامنة")
                return
            
            print("=" * 80)
            print("🔄 المزامنة التلقائية")
            print("=" * 80)
            
            # Step 1: Pull (جلب من MongoDB)
            print("\n📥 Step 1: Pull - جلب البيانات من MongoDB...")
            pulled = self._pull_from_mongo()
            self.sync_stats['pulled'] = pulled
            
            # Step 2: Push (رفع إلى MongoDB)
            print("\n📤 Step 2: Push - رفع البيانات إلى MongoDB...")
            pushed = self._push_to_mongo()
            self.sync_stats['pushed'] = pushed
            
            # النتيجة
            elapsed = time.time() - start_time
            self.last_sync_time = datetime.now()
            
            print("\n" + "=" * 80)
            print("✅ اكتملت المزامنة التلقائية")
            print(f"  📥 تم جلب: {pulled} سجل")
            print(f"  📤 تم رفع: {pushed} سجل")
            print(f"  ⏱️ الوقت: {elapsed:.2f} ثانية")
            print("=" * 80)
            
        except Exception as e:
            print(f"ERROR: [AutoSync] فشلت المزامنة: {e}")
            self.sync_stats['failed'] += 1
            import traceback
            traceback.print_exc()
        
        finally:
            self.is_syncing = False
    
    def _pull_from_mongo(self) -> int:
        """
        جلب البيانات من MongoDB إلى SQLite
        
        Returns:
            عدد السجلات المجلوبة
        """
        total_pulled = 0
        
        try:
            # جلب الحسابات
            accounts = list(self.repository.mongo_db.accounts.find())
            for acc in accounts:
                try:
                    acc_dict = dict(acc)
                    mongo_id = str(acc_dict.pop('_id'))
                    
                    # تحويل datetime
                    for key in ['created_at', 'last_modified']:
                        if key in acc_dict and hasattr(acc_dict[key], 'isoformat'):
                            acc_dict[key] = acc_dict[key].isoformat()
                    
                    # تحديث أو إدراج
                    self.repository.sqlite_cursor.execute("""
                        INSERT OR REPLACE INTO accounts 
                        (_mongo_id, name, code, type, parent_id, balance, currency, 
                         description, created_at, last_modified, sync_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                    """, (
                        mongo_id,
                        acc_dict.get('name'),
                        acc_dict.get('code'),
                        acc_dict.get('type'),
                        acc_dict.get('parent_id'),
                        acc_dict.get('balance', 0.0),
                        acc_dict.get('currency', 'EGP'),
                        acc_dict.get('description'),
                        acc_dict.get('created_at'),
                        acc_dict.get('last_modified'),
                    ))
                    total_pulled += 1
                except Exception as e:
                    print(f"  ⚠️ فشل جلب حساب: {e}")
            
            self.repository.sqlite_conn.commit()
            print(f"  ✅ تم جلب {total_pulled} حساب")
            
            # جلب العملاء (مع إصلاح مشكلة cursor)
            try:
                clients_cursor = self.repository.mongo_db.clients.find()
                clients = list(clients_cursor)
                clients_cursor.close()  # إغلاق cursor لتجنب مشكلة recursive use
                
                clients_pulled = 0
                for client in clients:
                    try:
                        c = dict(client)
                        mongo_id = str(c.pop('_id'))
                        
                        # تحويل datetime
                        for key in ['created_at', 'last_modified']:
                            if key in c and hasattr(c[key], 'isoformat'):
                                c[key] = c[key].isoformat()
                        
                        self.repository.sqlite_cursor.execute("""
                            INSERT OR REPLACE INTO clients 
                            (_mongo_id, name, company_name, email, phone, address, country,
                             vat_number, status, client_type, work_field, logo_path,
                             client_notes, created_at, last_modified, sync_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                        """, (
                            mongo_id,
                            c.get('name'),
                            c.get('company_name'),
                            c.get('email'),
                            c.get('phone'),
                            c.get('address'),
                            c.get('country'),
                            c.get('vat_number'),
                            c.get('status', 'نشط'),
                            c.get('client_type'),
                            c.get('work_field'),
                            c.get('logo_path'),
                            c.get('client_notes'),
                            c.get('created_at'),
                            c.get('last_modified'),
                        ))
                        clients_pulled += 1
                    except Exception as e:
                        print(f"  ⚠️ فشل جلب عميل: {e}")
                
                self.repository.sqlite_conn.commit()
                total_pulled += clients_pulled
                print(f"  ✅ تم جلب {clients_pulled} عميل")
                
            except Exception as e:
                print(f"  ❌ فشل جلب العملاء: {e}")
            
            # جلب المشاريع
            projects = list(self.repository.mongo_db.projects.find())
            projects_pulled = 0
            for proj in projects:
                try:
                    p = dict(proj)
                    mongo_id = str(p.pop('_id'))
                    
                    # تحويل datetime
                    for key in ['created_at', 'last_modified', 'start_date', 'end_date']:
                        if key in p and hasattr(p[key], 'isoformat'):
                            p[key] = p[key].isoformat()
                    
                    # تحويل items إلى JSON
                    items_json = json.dumps(p.get('items', []))
                    
                    # ⚡ جلب قيمة status_manually_set
                    status_manually_set = 1 if p.get('status_manually_set', False) else 0
                    
                    self.repository.sqlite_cursor.execute("""
                        INSERT OR REPLACE INTO projects 
                        (_mongo_id, name, client_id, status, status_manually_set, description, start_date, end_date,
                         items, subtotal, discount_rate, discount_amount, tax_rate, tax_amount,
                         total_amount, currency, project_notes, created_at, last_modified, sync_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                    """, (
                        mongo_id,
                        p.get('name'),
                        p.get('client_id'),
                        p.get('status', 'نشط'),
                        status_manually_set,
                        p.get('description'),
                        p.get('start_date'),
                        p.get('end_date'),
                        items_json,
                        p.get('subtotal', 0.0),
                        p.get('discount_rate', 0.0),
                        p.get('discount_amount', 0.0),
                        p.get('tax_rate', 0.0),
                        p.get('tax_amount', 0.0),
                        p.get('total_amount', 0.0),
                        p.get('currency', 'EGP'),
                        p.get('project_notes'),
                        p.get('created_at'),
                        p.get('last_modified'),
                    ))
                    projects_pulled += 1
                except Exception as e:
                    print(f"  ⚠️ فشل جلب مشروع: {e}")
            
            self.repository.sqlite_conn.commit()
            total_pulled += projects_pulled
            print(f"  ✅ تم جلب {projects_pulled} مشروع")
            
            # جلب الدفعات
            payments = list(self.repository.mongo_db.payments.find())
            payments_pulled = 0
            for pay in payments:
                try:
                    p = dict(pay)
                    mongo_id = str(p.pop('_id'))
                    
                    # تحويل datetime
                    for key in ['created_at', 'last_modified', 'date']:
                        if key in p and hasattr(p[key], 'isoformat'):
                            p[key] = p[key].isoformat()
                    
                    self.repository.sqlite_cursor.execute("""
                        INSERT OR REPLACE INTO payments 
                        (_mongo_id, project_id, client_id, date, amount, account_id, method,
                         created_at, last_modified, sync_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                    """, (
                        mongo_id,
                        p.get('project_id'),
                        p.get('client_id'),
                        p.get('date'),
                        p.get('amount', 0.0),
                        p.get('account_id'),
                        p.get('method'),
                        p.get('created_at'),
                        p.get('last_modified'),
                    ))
                    payments_pulled += 1
                except Exception as e:
                    print(f"  ⚠️ فشل جلب دفعة: {e}")
            
            self.repository.sqlite_conn.commit()
            total_pulled += payments_pulled
            print(f"  ✅ تم جلب {payments_pulled} دفعة")
            
            # جلب القيود المحاسبية (journal entries)
            try:
                journal_entries = list(self.repository.mongo_db.journal_entries.find())
                entries_pulled = 0
                for entry in journal_entries:
                    try:
                        e = dict(entry)
                        mongo_id = str(e.pop('_id'))
                        
                        # تحويل datetime
                        for key in ['created_at', 'last_modified', 'date']:
                            if key in e and hasattr(e[key], 'isoformat'):
                                e[key] = e[key].isoformat()
                        
                        # تحويل lines إلى JSON
                        lines_json = json.dumps(e.get('lines', []))
                        
                        self.repository.sqlite_cursor.execute("""
                            INSERT OR REPLACE INTO journal_entries 
                            (_mongo_id, date, description, lines, related_document_id,
                             created_at, last_modified, sync_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 'synced')
                        """, (
                            mongo_id,
                            e.get('date'),
                            e.get('description', ''),
                            lines_json,
                            e.get('related_document_id'),
                            e.get('created_at'),
                            e.get('last_modified'),
                        ))
                        entries_pulled += 1
                    except Exception as ex:
                        print(f"  ⚠️ فشل جلب قيد محاسبي: {ex}")
                
                self.repository.sqlite_conn.commit()
                total_pulled += entries_pulled
                print(f"  ✅ تم جلب {entries_pulled} قيد محاسبي")
            except Exception as e:
                print(f"  ❌ فشل جلب القيود المحاسبية: {e}")
            
            # جلب الفواتير
            try:
                invoices = list(self.repository.mongo_db.invoices.find())
                invoices_pulled = 0
                for inv in invoices:
                    try:
                        i = dict(inv)
                        mongo_id = str(i.pop('_id'))
                        
                        # تحويل datetime
                        for key in ['created_at', 'last_modified', 'issue_date', 'due_date']:
                            if key in i and hasattr(i[key], 'isoformat'):
                                i[key] = i[key].isoformat()
                        
                        # تحويل items إلى JSON
                        items_json = json.dumps(i.get('items', []))
                        
                        self.repository.sqlite_cursor.execute("""
                            INSERT OR REPLACE INTO invoices 
                            (_mongo_id, invoice_number, client_id, project_id, issue_date, due_date,
                             items, subtotal, discount_rate, discount_amount, tax_rate, tax_amount,
                             total_amount, currency, status, notes, created_at, last_modified, sync_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                        """, (
                            mongo_id,
                            i.get('invoice_number'),
                            i.get('client_id'),
                            i.get('project_id'),
                            i.get('issue_date'),
                            i.get('due_date'),
                            items_json,
                            i.get('subtotal', 0.0),
                            i.get('discount_rate', 0.0),
                            i.get('discount_amount', 0.0),
                            i.get('tax_rate', 0.0),
                            i.get('tax_amount', 0.0),
                            i.get('total_amount', 0.0),
                            i.get('currency', 'EGP'),
                            i.get('status', 'مسودة'),
                            i.get('notes'),
                            i.get('created_at'),
                            i.get('last_modified'),
                        ))
                        invoices_pulled += 1
                    except Exception as e:
                        print(f"  ⚠️ فشل جلب فاتورة: {e}")
                
                self.repository.sqlite_conn.commit()
                total_pulled += invoices_pulled
                print(f"  ✅ تم جلب {invoices_pulled} فاتورة")
            except Exception as e:
                print(f"  ❌ فشل جلب الفواتير: {e}")
            
            # جلب الخدمات
            try:
                services = list(self.repository.mongo_db.services.find())
                services_pulled = 0
                for srv in services:
                    try:
                        s = dict(srv)
                        mongo_id = str(s.pop('_id'))
                        
                        # تحويل datetime
                        for key in ['created_at', 'last_modified']:
                            if key in s and hasattr(s[key], 'isoformat'):
                                s[key] = s[key].isoformat()
                        
                        self.repository.sqlite_cursor.execute("""
                            INSERT OR REPLACE INTO services 
                            (_mongo_id, name, description, default_price, category, status,
                             created_at, last_modified, sync_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                        """, (
                            mongo_id,
                            s.get('name'),
                            s.get('description'),
                            s.get('default_price', 0.0),
                            s.get('category', 'General'),
                            s.get('status', 'نشط'),
                            s.get('created_at'),
                            s.get('last_modified'),
                        ))
                        services_pulled += 1
                    except Exception as e:
                        print(f"  ⚠️ فشل جلب خدمة: {e}")
                
                self.repository.sqlite_conn.commit()
                total_pulled += services_pulled
                print(f"  ✅ تم جلب {services_pulled} خدمة")
            except Exception as e:
                print(f"  ❌ فشل جلب الخدمات: {e}")
            
            # جلب المصروفات
            try:
                expenses = list(self.repository.mongo_db.expenses.find())
                expenses_pulled = 0
                for exp in expenses:
                    try:
                        e = dict(exp)
                        mongo_id = str(e.pop('_id'))
                        
                        # تحويل datetime
                        for key in ['created_at', 'last_modified', 'date']:
                            if key in e and hasattr(e[key], 'isoformat'):
                                e[key] = e[key].isoformat()
                        
                        self.repository.sqlite_cursor.execute("""
                            INSERT OR REPLACE INTO expenses 
                            (_mongo_id, date, category, amount, description, account_id,
                             payment_account_id, project_id, created_at, last_modified, sync_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                        """, (
                            mongo_id,
                            e.get('date'),
                            e.get('category'),
                            e.get('amount', 0.0),
                            e.get('description'),
                            e.get('account_id'),
                            e.get('payment_account_id'),
                            e.get('project_id'),
                            e.get('created_at'),
                            e.get('last_modified'),
                        ))
                        expenses_pulled += 1
                    except Exception as ex:
                        print(f"  ⚠️ فشل جلب مصروف: {ex}")
                
                self.repository.sqlite_conn.commit()
                total_pulled += expenses_pulled
                print(f"  ✅ تم جلب {expenses_pulled} مصروف")
            except Exception as e:
                print(f"  ❌ فشل جلب المصروفات: {e}")
            
            # جلب عروض الأسعار
            try:
                quotations = list(self.repository.mongo_db.quotations.find())
                quotations_pulled = 0
                for quot in quotations:
                    try:
                        q = dict(quot)
                        mongo_id = str(q.pop('_id'))
                        
                        # تحويل datetime
                        for key in ['created_at', 'last_modified', 'issue_date', 'expiry_date']:
                            if key in q and hasattr(q[key], 'isoformat'):
                                q[key] = q[key].isoformat()
                        
                        # تحويل items إلى JSON
                        items_json = json.dumps(q.get('items', []))
                        
                        self.repository.sqlite_cursor.execute("""
                            INSERT OR REPLACE INTO quotations 
                            (_mongo_id, quote_number, client_id, project_id, issue_date, expiry_date,
                             items, subtotal, discount_rate, discount_amount, tax_rate, tax_amount,
                             total_amount, status, currency, notes, created_at, last_modified, sync_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                        """, (
                            mongo_id,
                            q.get('quote_number'),
                            q.get('client_id'),
                            q.get('project_id'),
                            q.get('issue_date'),
                            q.get('expiry_date'),
                            items_json,
                            q.get('subtotal', 0.0),
                            q.get('discount_rate', 0.0),
                            q.get('discount_amount', 0.0),
                            q.get('tax_rate', 0.0),
                            q.get('tax_amount', 0.0),
                            q.get('total_amount', 0.0),
                            q.get('status', 'مسودة'),
                            q.get('currency', 'EGP'),
                            q.get('notes'),
                            q.get('created_at'),
                            q.get('last_modified'),
                        ))
                        quotations_pulled += 1
                    except Exception as ex:
                        print(f"  ⚠️ فشل جلب عرض سعر: {ex}")
                
                self.repository.sqlite_conn.commit()
                total_pulled += quotations_pulled
                print(f"  ✅ تم جلب {quotations_pulled} عرض سعر")
            except Exception as e:
                print(f"  ❌ فشل جلب عروض الأسعار: {e}")
            
            # جلب العملات
            try:
                currencies = list(self.repository.mongo_db.currencies.find())
                currencies_pulled = 0
                for curr in currencies:
                    try:
                        c = dict(curr)
                        mongo_id = str(c.pop('_id'))
                        
                        # تحويل datetime
                        for key in ['created_at', 'last_modified']:
                            if key in c and hasattr(c[key], 'isoformat'):
                                c[key] = c[key].isoformat()
                        
                        self.repository.sqlite_cursor.execute("""
                            INSERT OR REPLACE INTO currencies 
                            (_mongo_id, code, name, symbol, rate, is_base, active,
                             created_at, last_modified, sync_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                        """, (
                            mongo_id,
                            c.get('code'),
                            c.get('name'),
                            c.get('symbol', ''),
                            c.get('rate', 1.0),
                            1 if c.get('is_base', False) else 0,
                            1 if c.get('active', True) else 0,
                            c.get('created_at'),
                            c.get('last_modified'),
                        ))
                        currencies_pulled += 1
                    except Exception as ex:
                        print(f"  ⚠️ فشل جلب عملة: {ex}")
                
                self.repository.sqlite_conn.commit()
                total_pulled += currencies_pulled
                print(f"  ✅ تم جلب {currencies_pulled} عملة")
            except Exception as e:
                print(f"  ❌ فشل جلب العملات: {e}")
            
            # جلب الإشعارات
            try:
                notifications = list(self.repository.mongo_db.notifications.find())
                notifications_pulled = 0
                for notif in notifications:
                    try:
                        n = dict(notif)
                        mongo_id = str(n.pop('_id'))
                        
                        # تحويل datetime
                        for key in ['created_at', 'last_modified', 'expires_at']:
                            if key in n and hasattr(n[key], 'isoformat'):
                                n[key] = n[key].isoformat()
                        
                        self.repository.sqlite_cursor.execute("""
                            INSERT OR REPLACE INTO notifications 
                            (_mongo_id, title, message, type, priority, is_read, 
                             related_entity_type, related_entity_id, action_url, expires_at,
                             created_at, last_modified, sync_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                        """, (
                            mongo_id,
                            n.get('title'),
                            n.get('message'),
                            n.get('type', 'info'),
                            n.get('priority', 'normal'),
                            1 if n.get('is_read', False) else 0,
                            n.get('related_entity_type'),
                            n.get('related_entity_id'),
                            n.get('action_url'),
                            n.get('expires_at'),
                            n.get('created_at'),
                            n.get('last_modified'),
                        ))
                        notifications_pulled += 1
                    except Exception as ex:
                        print(f"  ⚠️ فشل جلب إشعار: {ex}")
                
                self.repository.sqlite_conn.commit()
                total_pulled += notifications_pulled
                print(f"  ✅ تم جلب {notifications_pulled} إشعار")
            except Exception as e:
                print(f"  ❌ فشل جلب الإشعارات: {e}")
            
            # جلب المهام (tasks)
            try:
                tasks = list(self.repository.mongo_db.tasks.find())
                tasks_pulled = 0
                for task in tasks:
                    try:
                        t = dict(task)
                        mongo_id = str(t.pop('_id'))
                        
                        # تحويل datetime
                        for key in ['created_at', 'last_modified', 'due_date', 'completed_at']:
                            if key in t and hasattr(t[key], 'isoformat'):
                                t[key] = t[key].isoformat()
                        
                        # تحويل tags إلى JSON
                        tags_json = json.dumps(t.get('tags', []))
                        
                        self.repository.sqlite_cursor.execute("""
                            INSERT OR REPLACE INTO tasks 
                            (_mongo_id, title, description, priority, status, category,
                             due_date, due_time, completed_at, related_project_id, related_client_id,
                             tags, reminder, reminder_minutes, assigned_to,
                             created_at, last_modified, sync_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                        """, (
                            mongo_id,
                            t.get('title'),
                            t.get('description'),
                            t.get('priority', 'MEDIUM'),
                            t.get('status', 'TODO'),
                            t.get('category', 'GENERAL'),
                            t.get('due_date'),
                            t.get('due_time'),
                            t.get('completed_at'),
                            t.get('related_project_id'),
                            t.get('related_client_id'),
                            tags_json,
                            1 if t.get('reminder', False) else 0,
                            t.get('reminder_minutes', 30),
                            t.get('assigned_to'),
                            t.get('created_at'),
                            t.get('last_modified'),
                        ))
                        tasks_pulled += 1
                    except Exception as ex:
                        print(f"  ⚠️ فشل جلب مهمة: {ex}")
                
                self.repository.sqlite_conn.commit()
                total_pulled += tasks_pulled
                print(f"  ✅ تم جلب {tasks_pulled} مهمة")
            except Exception as e:
                print(f"  ❌ فشل جلب المهام: {e}")
            
        except Exception as e:
            print(f"ERROR: [AutoSync] فشل Pull: {e}")
        
        return total_pulled
    
    def _push_to_mongo(self) -> int:
        """
        رفع البيانات من SQLite إلى MongoDB
        
        Returns:
            عدد السجلات المرفوعة
        """
        total_pushed = 0
        
        # قائمة الجداول المراد رفعها مع الحقول الخاصة بكل جدول
        tables_config = {
            'clients': {
                'date_fields': ['created_at', 'last_modified'],
                'json_fields': []
            },
            'projects': {
                'date_fields': ['created_at', 'last_modified', 'start_date', 'end_date'],
                'json_fields': ['items']
            },
            'accounts': {
                'date_fields': ['created_at', 'last_modified'],
                'json_fields': []
            },
            'notifications': {
                'date_fields': ['created_at', 'last_modified', 'expires_at'],
                'json_fields': []
            },
            'services': {
                'date_fields': ['created_at', 'last_modified'],
                'json_fields': []
            },
            'expenses': {
                'date_fields': ['created_at', 'last_modified', 'date'],
                'json_fields': []
            },
            'payments': {
                'date_fields': ['created_at', 'last_modified', 'date'],
                'json_fields': []
            },
            'invoices': {
                'date_fields': ['created_at', 'last_modified', 'issue_date', 'due_date'],
                'json_fields': ['items']
            },
            'quotations': {
                'date_fields': ['created_at', 'last_modified', 'issue_date', 'expiry_date'],
                'json_fields': ['items']
            },
            'journal_entries': {
                'date_fields': ['created_at', 'last_modified', 'date'],
                'json_fields': ['lines']
            },
            'currencies': {
                'date_fields': ['created_at', 'last_modified'],
                'json_fields': []
            },
            'tasks': {
                'date_fields': ['created_at', 'last_modified', 'due_date', 'completed_at'],
                'json_fields': ['tags']
            }
        }
        
        from bson import ObjectId
        
        for table_name, config in tables_config.items():
            try:
                # جلب السجلات غير المتزامنة
                self.repository.sqlite_cursor.execute(f"""
                    SELECT * FROM {table_name} 
                    WHERE sync_status IN ('new_offline', 'modified_offline')
                """)
                
                unsynced_rows = self.repository.sqlite_cursor.fetchall()
                if not unsynced_rows:
                    continue
                
                table_pushed = 0
                collection = self.repository.mongo_db[table_name]
                
                for row in unsynced_rows:
                    try:
                        row_dict = dict(row)
                        local_id = row_dict.pop('id')
                        mongo_id = row_dict.pop('_mongo_id', None)
                        row_dict.pop('sync_status', None)
                        
                        # تحويل datetime
                        for key in config['date_fields']:
                            if key in row_dict and isinstance(row_dict[key], str):
                                try:
                                    row_dict[key] = datetime.fromisoformat(row_dict[key])
                                except (ValueError, TypeError, AttributeError):
                                    pass
                        
                        # تحويل JSON fields
                        for key in config['json_fields']:
                            if key in row_dict and isinstance(row_dict[key], str):
                                try:
                                    row_dict[key] = json.loads(row_dict[key])
                                except (json.JSONDecodeError, TypeError):
                                    row_dict[key] = []
                        
                        if mongo_id:
                            # تحديث سجل موجود
                            collection.update_one(
                                {'_id': ObjectId(mongo_id)},
                                {'$set': row_dict}
                            )
                        else:
                            # إدراج سجل جديد
                            result = collection.insert_one(row_dict)
                            mongo_id = str(result.inserted_id)
                            
                            # تحديث SQLite بالـ mongo_id
                            self.repository.sqlite_cursor.execute(
                                f"UPDATE {table_name} SET _mongo_id = ? WHERE id = ?",
                                (mongo_id, local_id)
                            )
                        
                        # تحديث sync_status
                        self.repository.sqlite_cursor.execute(
                            f"UPDATE {table_name} SET sync_status = 'synced' WHERE id = ?",
                            (local_id,)
                        )
                        
                        table_pushed += 1
                        total_pushed += 1
                        
                    except Exception as e:
                        print(f"  ⚠️ فشل رفع سجل من {table_name}: {e}")
                
                self.repository.sqlite_conn.commit()
                if table_pushed > 0:
                    print(f"  ✅ تم رفع {table_pushed} سجل من {table_name}")
                    
            except Exception as e:
                print(f"  ❌ فشل رفع جدول {table_name}: {e}")
        
        return total_pushed
