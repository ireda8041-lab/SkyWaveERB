"""
Stress Testing - اختبار التحمل
يختبر قدرة قاعدة البيانات على التعامل مع كميات كبيرة من البيانات
"""

import random
import sqlite3
import sys
import time
from datetime import datetime

# Fix Unicode output on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def database_stress_test():
    """اختبار إدخال 10,000 سجل في قاعدة البيانات"""
    
    # استخدام قاعدة بيانات مؤقتة للاختبار (لا نريد تلويث البيانات الحقيقية)
    conn = sqlite3.connect(':memory:')  # في الذاكرة للاختبار
    
    # تفعيل السرعة القصوى
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA temp_store=MEMORY")
    
    # إنشاء جدول الفواتير للاختبار (مطابق للهيكل الحقيقي)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            _mongo_id TEXT,
            sync_status TEXT NOT NULL DEFAULT 'new_offline',
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            invoice_number TEXT NOT NULL UNIQUE,
            client_id TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            items TEXT NOT NULL,
            subtotal REAL NOT NULL,
            discount_rate REAL DEFAULT 0.0,
            discount_amount REAL DEFAULT 0.0,
            tax_rate REAL DEFAULT 0.0,
            tax_amount REAL DEFAULT 0.0,
            total_amount REAL NOT NULL,
            amount_paid REAL DEFAULT 0.0,
            status TEXT NOT NULL,
            currency TEXT NOT NULL,
            notes TEXT,
            project_id TEXT
        )
    """)
    
    # إنشاء index لتحسين الأداء
    conn.execute("CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status)")
    
    print("[STRESS] Starting Stress Test: Inserting 10,000 Records...")
    print("-" * 50)
    
    start_time = time.time()
    now = datetime.now().isoformat()
    
    # تحضير البيانات
    data = []
    statuses = ['مسودة', 'مرسلة', 'مدفوعة جزئياً', 'مدفوعة', 'متأخرة']
    currencies = ['EGP', 'USD', 'SAR']
    
    for i in range(10000):
        subtotal = random.uniform(100, 50000)
        tax_rate = random.choice([0, 14, 15])
        tax_amount = subtotal * (tax_rate / 100)
        total = subtotal + tax_amount
        
        data.append((
            now,                                    # created_at
            now,                                    # last_modified
            f"STRESS-{i:06d}",                      # invoice_number
            f"Client-{random.randint(1, 100)}",    # client_id
            "2025-12-06",                          # issue_date
            "2025-12-20",                          # due_date
            '[]',                                   # items (JSON)
            subtotal,                              # subtotal
            0.0,                                   # discount_rate
            0.0,                                   # discount_amount
            tax_rate,                              # tax_rate
            tax_amount,                            # tax_amount
            total,                                 # total_amount
            0.0,                                   # amount_paid
            random.choice(statuses),               # status
            random.choice(currencies),             # currency
        ))
    
    # إدخال البيانات دفعة واحدة
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO invoices (
            created_at, last_modified, invoice_number, client_id,
            issue_date, due_date, items, subtotal, discount_rate,
            discount_amount, tax_rate, tax_amount, total_amount,
            amount_paid, status, currency
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, data)
    conn.commit()
    
    insert_time = time.time()
    insert_duration = insert_time - start_time
    
    print(f"[OK] INSERT: {insert_duration:.2f} seconds ({10000/insert_duration:.0f} records/sec)")
    
    # اختبار القراءة
    print("\n[READ] Testing READ performance...")
    
    # اختبار 1: قراءة كل السجلات
    start_read = time.time()
    cursor.execute("SELECT * FROM invoices")
    all_records = cursor.fetchall()
    read_all_time = time.time() - start_read
    print(f"   - Read ALL (10,000): {read_all_time:.3f}s")
    
    # اختبار 2: بحث بالعميل
    start_search = time.time()
    cursor.execute("SELECT * FROM invoices WHERE client_id = ?", ("Client-50",))
    client_records = cursor.fetchall()
    search_time = time.time() - start_search
    print(f"   - Search by client: {search_time:.4f}s ({len(client_records)} records)")
    
    # اختبار 3: تجميع حسب الحالة
    start_group = time.time()
    cursor.execute("SELECT status, COUNT(*), SUM(total_amount) FROM invoices GROUP BY status")
    grouped = cursor.fetchall()
    group_time = time.time() - start_group
    print(f"   - Group by status: {group_time:.4f}s")
    
    # اختبار 4: حساب الإجماليات
    start_sum = time.time()
    cursor.execute("SELECT SUM(total_amount), AVG(total_amount), MAX(total_amount) FROM invoices")
    totals = cursor.fetchone()
    sum_time = time.time() - start_sum
    print(f"   - Calculate totals: {sum_time:.4f}s")
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    print("\n" + "=" * 50)
    print("[RESULTS] SUMMARY")
    print("=" * 50)
    print(f"Total Records: 10,000")
    print(f"Total Time: {total_duration:.2f} seconds")
    print(f"Insert Speed: {10000/insert_duration:.0f} records/second")
    print(f"Total Amount: {totals[0]:,.2f}")
    print(f"Average Amount: {totals[1]:,.2f}")
    
    # تقييم الأداء
    print("\n" + "=" * 50)
    if insert_duration < 1:
        print("[PERF] BLAZING FAST!")
    elif insert_duration < 3:
        print("[PERF] EXCELLENT")
    elif insert_duration < 5:
        print("[PERF] GOOD")
    elif insert_duration < 10:
        print("[PERF] ACCEPTABLE (could be better)")
    else:
        print("[PERF] SLOW - Optimization needed!")
    
    conn.close()
    
    return insert_duration


def concurrent_access_test():
    """اختبار الوصول المتزامن"""
    import threading
    
    print("\n" + "=" * 50)
    print("[CONCURRENT] Testing Concurrent Access...")
    print("=" * 50)
    
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE test_concurrent (
            id INTEGER PRIMARY KEY,
            value TEXT,
            created_at TEXT
        )
    """)
    
    errors = []
    success_count = [0]
    lock = threading.Lock()
    
    def writer(thread_id):
        try:
            for i in range(100):
                with lock:
                    conn.execute(
                        "INSERT INTO test_concurrent (value, created_at) VALUES (?, ?)",
                        (f"Thread-{thread_id}-{i}", datetime.now().isoformat())
                    )
                    conn.commit()
                    success_count[0] += 1
        except Exception as e:
            errors.append(f"Thread {thread_id}: {e}")
    
    threads = []
    start = time.time()
    
    # إنشاء 10 threads كل واحد يكتب 100 سجل
    for i in range(10):
        t = threading.Thread(target=writer, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    duration = time.time() - start
    
    if errors:
        print(f"[X] Errors: {len(errors)}")
        for e in errors[:3]:
            print(f"   - {e}")
    else:
        print(f"[OK] All {success_count[0]} concurrent writes successful!")
        print(f"[TIME] Duration: {duration:.2f}s ({success_count[0]/duration:.0f} writes/sec)")
    
    conn.close()


if __name__ == "__main__":
    print("=" * 50)
    print("SKY WAVE ERP - STRESS TEST")
    print("=" * 50)
    print()
    
    # اختبار الإدخال الكثيف
    database_stress_test()
    
    # اختبار الوصول المتزامن
    concurrent_access_test()
    
    print("\n" + "=" * 50)
    print("[OK] All stress tests completed!")
    print("=" * 50)
