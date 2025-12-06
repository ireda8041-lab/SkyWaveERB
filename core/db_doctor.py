import sqlite3
import logging
import json
import sys

# إعداد اللوجر
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Fix Unicode output on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def run_health_check():
    conn = sqlite3.connect('skywave_local.db')
    cursor = conn.cursor()
    
    print("[HEALTH] Starting Database Health Check...")
    errors = 0
    
    # 1. فحص توازن القيود المحاسبية (أهم فحص)
    # يجب أن يكون مجموع المدين = مجموع الدائن لكل قيد
    cursor.execute("SELECT id, description, lines FROM journal_entries")
    entries = cursor.fetchall()
    
    unbalanced = []
    for entry in entries:
        entry_id, description, lines_json = entry
        if lines_json:
            try:
                lines = json.loads(lines_json)
                total_debit = sum(float(line.get('debit', 0) or 0) for line in lines)
                total_credit = sum(float(line.get('credit', 0) or 0) for line in lines)
                
                if abs(total_debit - total_credit) > 0.001:
                    unbalanced.append((entry_id, description, total_debit, total_credit))
            except (json.JSONDecodeError, TypeError):
                logging.warning(f"[!] Entry ID {entry_id}: Invalid JSON in lines field")
    
    if unbalanced:
        logging.error(f"[X] CRITICAL: Found {len(unbalanced)} unbalanced journal entries!")
        for row in unbalanced:
            print(f"   - Entry ID {row[0]}: Debit {row[2]} != Credit {row[3]}")
        errors += 1
    else:
        logging.info("[OK] Accounting Integrity: All journal entries are balanced.")
    
    # 2. فحص الأيتام (Orphaned Records)
    # مشاريع بدون عملاء (client_id يحتوي على اسم العميل وليس ID)
    cursor.execute("SELECT count(*) FROM projects WHERE client_id NOT IN (SELECT name FROM clients)")
    orphans = cursor.fetchone()[0]
    
    if orphans > 0:
        logging.warning(f"[!] Found {orphans} projects linked to non-existent clients.")
        # عرض أسماء العملاء المفقودين
        cursor.execute("SELECT DISTINCT client_id FROM projects WHERE client_id NOT IN (SELECT name FROM clients)")
        missing = cursor.fetchall()
        for m in missing[:5]:  # عرض أول 5 فقط
            print(f"   - Missing client: '{m[0]}'")
        if len(missing) > 5:
            print(f"   ... and {len(missing) - 5} more")
        errors += 1
    else:
        logging.info("[OK] Relational Integrity: No orphaned projects.")
    
    # 3. فحص أرقام الفواتير المكررة
    cursor.execute("SELECT invoice_number, count(*) FROM invoices GROUP BY invoice_number HAVING count(*) > 1")
    duplicates = cursor.fetchall()
    
    if duplicates:
        logging.error(f"[X] CRITICAL: Found duplicate invoice numbers!")
        for dup in duplicates:
            print(f"   - Invoice #{dup[0]} appears {dup[1]} times")
        errors += 1
    else:
        logging.info("[OK] Data Uniqueness: Invoice numbers are unique.")
    
    # 4. فحص الحسابات بدون أرصدة صحيحة
    cursor.execute("SELECT id, name, balance FROM accounts WHERE balance IS NULL")
    null_balances = cursor.fetchall()
    
    if null_balances:
        logging.warning(f"[!] Found {len(null_balances)} accounts with NULL balance.")
        errors += 1
    else:
        logging.info("[OK] Account Balances: All accounts have valid balances.")
    
    conn.close()
    
    if errors == 0:
        print("\n[SUCCESS] SYSTEM HEALTH: 100% PERFECT!")
    else:
        print(f"\n[FAIL] SYSTEM HEALTH: {errors} ISSUES FOUND. FIX IMMEDIATELY.")


if __name__ == "__main__":
    run_health_check()
