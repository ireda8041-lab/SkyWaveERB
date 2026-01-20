"""
فحص بيانات الدفعات في قاعدة البيانات
"""
import sqlite3
from datetime import datetime

# الاتصال بقاعدة البيانات
conn = sqlite3.connect('skywave_local.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 80)
print("فحص بيانات الدفعات في قاعدة البيانات")
print("=" * 80)

# جلب كل الدفعات
cursor.execute("SELECT * FROM payments LIMIT 10")
payments = cursor.fetchall()

print(f"\nعدد الدفعات: {len(payments)}")
print("\n" + "=" * 80)

for i, payment in enumerate(payments, 1):
    print(f"\nدفعة #{i}:")
    print(f"  ID: {payment['id']}")
    print(f"  المشروع: {payment['project_id']}")
    print(f"  العميل: {payment['client_id']}")
    print(f"  المبلغ: {payment['amount']}")
    print(f"  التاريخ: {payment['date']}")
    print(f"  الحساب: {payment['account_id']}")
    print(f"  الملاحظات: {payment['notes'] if 'notes' in payment.keys() else 'N/A'}")
    print("-" * 80)

# فحص أسماء المشاريع
print("\n" + "=" * 80)
print("أسماء المشاريع المرتبطة بالدفعات:")
print("=" * 80)
cursor.execute("SELECT DISTINCT project_id FROM payments")
projects = cursor.fetchall()
for proj in projects:
    print(f"  - {proj['project_id']}")

# فحص أسماء الحسابات
print("\n" + "=" * 80)
print("أسماء الحسابات المرتبطة بالدفعات:")
print("=" * 80)
cursor.execute("SELECT DISTINCT account_id FROM payments")
accounts = cursor.fetchall()
for acc in accounts:
    print(f"  - {acc['account_id']}")

# فحص جدول الحسابات
print("\n" + "=" * 80)
print("فحص جدول الحسابات (accounts):")
print("=" * 80)
cursor.execute("SELECT code, name, type FROM accounts LIMIT 10")
accounts_table = cursor.fetchall()
for acc in accounts_table:
    print(f"  - الكود: {acc['code']}, الاسم: {acc['name']}, النوع: {acc['type']}")

conn.close()
print("\n" + "=" * 80)
print("انتهى الفحص")
print("=" * 80)
