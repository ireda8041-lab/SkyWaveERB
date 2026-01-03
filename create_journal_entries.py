from core.repository import Repository
from services.accounting_service import AccountingService
from core.event_bus import EventBus

repo = Repository()
bus = EventBus()
acc_service = AccountingService(repo, bus)

print('جاري إنشاء القيود المحاسبية للمشاريع والدفعات الموجودة...')

# إنشاء قيود للمشاريع
projects = repo.get_all_projects()
for project in projects:
    if project.total_amount and project.total_amount > 0:
        print(f'إنشاء قيد للمشروع: {project.name} - {project.total_amount}')
        try:
            acc_service.handle_new_project({'project': project})
        except Exception as e:
            print(f'خطأ في المشروع {project.name}: {e}')

# فحص النتيجة
journal_entries = repo.get_all_journal_entries()
print(f'تم إنشاء {len(journal_entries)} قيد محاسبي')

if journal_entries:
    print('القيود المنشأة:')
    for entry in journal_entries:
        print(f'  - {entry.description}')
        for line in entry.lines:
            print(f'    {line.account_code}: مدين={line.debit}, دائن={line.credit}')