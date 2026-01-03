from core.repository import Repository
from core import schemas

repo = Repository()

print('جاري إنشاء الحسابات الأساسية...')

# الحسابات الأساسية المطلوبة
basic_accounts = [
    # الأصول
    {'code': '100000', 'name': 'الأصول', 'type': schemas.AccountType.ASSET, 'is_group': True},
    {'code': '110000', 'name': 'الأصول المتداولة', 'type': schemas.AccountType.ASSET, 'is_group': True},
    {'code': '111000', 'name': 'النقدية', 'type': schemas.AccountType.CASH, 'is_group': True},
    {'code': '112000', 'name': 'المستحقات', 'type': schemas.AccountType.ASSET, 'is_group': True},
    {'code': '112100', 'name': 'حساب العملاء', 'type': schemas.AccountType.ASSET, 'is_group': False},
    
    # الخصوم
    {'code': '200000', 'name': 'الخصوم', 'type': schemas.AccountType.LIABILITY, 'is_group': True},
    
    # حقوق الملكية
    {'code': '300000', 'name': 'حقوق الملكية', 'type': schemas.AccountType.EQUITY, 'is_group': True},
    
    # الإيرادات
    {'code': '400000', 'name': 'الإيرادات', 'type': schemas.AccountType.REVENUE, 'is_group': True},
    {'code': '410000', 'name': 'إيرادات التشغيل', 'type': schemas.AccountType.REVENUE, 'is_group': True},
    {'code': '410100', 'name': 'إيرادات التسويق الرقمي', 'type': schemas.AccountType.REVENUE, 'is_group': False},
    
    # المصروفات
    {'code': '500000', 'name': 'تكاليف الإيرادات', 'type': schemas.AccountType.EXPENSE, 'is_group': True},
    {'code': '600000', 'name': 'المصروفات التشغيلية', 'type': schemas.AccountType.EXPENSE, 'is_group': True},
]

created_count = 0
for acc_data in basic_accounts:
    try:
        # التحقق من وجود الحساب
        existing = repo.get_account_by_code(acc_data['code'])
        if existing:
            print(f'الحساب {acc_data["code"]} موجود بالفعل')
            continue
        
        # إنشاء الحساب
        account = schemas.Account(
            code=acc_data['code'],
            name=acc_data['name'],
            type=acc_data['type'],
            balance=0.0,
            is_group=acc_data.get('is_group', False)
        )
        
        created = repo.create_account(account)
        if created:
            print(f'تم إنشاء الحساب: {acc_data["code"]} - {acc_data["name"]}')
            created_count += 1
        
    except Exception as e:
        print(f'خطأ في إنشاء الحساب {acc_data["code"]}: {e}')

print(f'تم إنشاء {created_count} حساب جديد')