#!/usr/bin/env python
"""اختبار الأرصدة"""
from core.event_bus import EventBus
from core.repository import Repository
from services.accounting_service import AccountingService

repo = Repository()
bus = EventBus()
acc_service = AccountingService(repo, bus)

# إبطال الـ cache
AccountingService._hierarchy_cache = None
AccountingService._hierarchy_cache_time = 0

# جلب الملخص المالي
print("\n" + "=" * 60)
print("الملخص المالي:")
print("=" * 60)
summary = acc_service.get_financial_summary()
for key, value in summary.items():
    print(f"  {key}: {value:,.2f}")

# جلب الشجرة
print("\n" + "=" * 60)
print("الشجرة:")
print("=" * 60)
tree = acc_service.get_hierarchy_with_balances(force_refresh=True)
for code, node in tree.items():
    acc = node['obj']
    total = node['total']
    children = len(node.get('children', []))
    print(f"  {code}: {acc.name} = {total:.2f} (أبناء: {children})")
