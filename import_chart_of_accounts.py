"""
سكريبت استيراد شجرة الحسابات الاحترافية إلى SkyWave ERP
===========================================================

هذا السكريبت يقوم بـ:
1. قراءة ملف JSON الخاص بشجرة الحسابات
2. تحويل البنية الهرمية إلى حسابات في قاعدة البيانات
3. ربط الحسابات الأب والأبناء بشكل صحيح
4. التعامل مع الحسابات الموجودة (تحديث أو تخطي)

الاستخدام:
----------
python import_chart_of_accounts.py [--force] [--clear]

الخيارات:
- --force: تحديث الحسابات الموجودة
- --clear: حذف جميع الحسابات القديمة قبل الاستيراد (خطير!)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# إضافة المسار الحالي للـ sys.path
sys.path.insert(0, str(Path(__file__).parent))

from core.repository import Repository
from core.schemas import Account, AccountStatus, AccountType, CurrencyCode


class ChartOfAccountsImporter:
    """مستورد شجرة الحسابات الاحترافية"""

    def __init__(self, repo: Repository):
        self.repo = repo
        self.imported_count = 0
        self.updated_count = 0
        self.skipped_count = 0
        self.error_count = 0

        # خريطة تحويل الأكواد إلى أنواع الحسابات
        self.code_to_type = {
            '1': AccountType.ASSET,      # الأصول
            '2': AccountType.LIABILITY,  # الخصوم
            '3': AccountType.EQUITY,     # حقوق الملكية
            '4': AccountType.REVENUE,    # الإيرادات
            '5': AccountType.EXPENSE,    # تكاليف الإيرادات (COGS)
            '6': AccountType.EXPENSE,    # المصروفات التشغيلية (OPEX)
        }

    def get_account_type(self, code: str) -> AccountType:
        """تحديد نوع الحساب بناءً على الكود"""
        first_digit = code[0] if code else '1'

        # حسابات نقدية خاصة (111xxx)
        if code.startswith('111'):
            return AccountType.CASH

        return self.code_to_type.get(first_digit, AccountType.ASSET)

    def import_account(
        self,
        account_data: dict,
        parent_code: str | None = None,
        force_update: bool = False
    ) -> Account | None:
        """
        استيراد حساب واحد مع أطفاله

        Args:
            account_data: بيانات الحساب من JSON
            parent_code: كود الحساب الأب
            force_update: هل نحدث الحسابات الموجودة؟

        Returns:
            Account object أو None في حالة الفشل
        """
        code = account_data.get('code')
        name_ar = account_data.get('name_ar')
        name_en = account_data.get('name_en', '')
        account_data.get('is_transactional', False)
        children = account_data.get('children', [])

        if not code or not name_ar:
            print(f"⚠️  تخطي حساب بدون كود أو اسم: {account_data}")
            self.skipped_count += 1
            return None

        try:
            # التحقق من وجود الحساب
            existing_account = self.repo.get_account_by_code(code)

            if existing_account and not force_update:
                print(f"⏭️  تخطي حساب موجود: {code} - {name_ar}")
                self.skipped_count += 1
                account = existing_account
            else:
                # تحديد نوع الحساب
                account_type = self.get_account_type(code)

                # إنشاء أو تحديث الحساب
                account_obj = Account(
                    code=code,
                    name=f"{name_ar} | {name_en}" if name_en else name_ar,
                    type=account_type,
                    parent_code=parent_code,
                    is_group=len(children) > 0,  # إذا كان له أطفال فهو مجموعة
                    balance=0.0,
                    debit_total=0.0,
                    credit_total=0.0,
                    currency=CurrencyCode.EGP,
                    description=name_en if name_en else None,
                    status=AccountStatus.ACTIVE,
                    created_at=datetime.now(),
                    last_modified=datetime.now()
                )

                if existing_account:
                    # تحديث
                    account_obj.id = existing_account.id
                    account_obj.mongo_id = existing_account.mongo_id
                    updated = self.repo.update_account(str(existing_account.id), account_obj)
                    account = updated if updated else account_obj
                    print(f"🔄 تحديث: {code} - {name_ar}")
                    self.updated_count += 1
                else:
                    # إنشاء جديد
                    account = self.repo.create_account(account_obj)
                    print(f"✅ إضافة: {code} - {name_ar}")
                    self.imported_count += 1

            # استيراد الحسابات الفرعية
            for child_data in children:
                self.import_account(child_data, parent_code=code, force_update=force_update)

            return account

        except Exception as e:
            print(f"❌ خطأ في استيراد الحساب {code}: {e}")
            self.error_count += 1
            return None

    def import_from_json(self, json_file: str, force_update: bool = False):
        """
        استيراد شجرة الحسابات من ملف JSON

        Args:
            json_file: مسار ملف JSON
            force_update: هل نحدث الحسابات الموجودة؟
        """
        print(f"\n{'='*60}")
        print(f"🚀 بدء استيراد شجرة الحسابات من: {json_file}")
        print(f"{'='*60}\n")

        try:
            with open(json_file, encoding='utf-8') as f:
                accounts_data = json.load(f)

            print(f"📄 تم قراءة {len(accounts_data)} حساب رئيسي من الملف\n")

            # استيراد كل حساب رئيسي
            for account_data in accounts_data:
                self.import_account(account_data, force_update=force_update)

            # طباعة الإحصائيات
            print(f"\n{'='*60}")
            print("📊 إحصائيات الاستيراد:")
            print(f"{'='*60}")
            print(f"✅ تم إضافة: {self.imported_count} حساب")
            print(f"🔄 تم تحديث: {self.updated_count} حساب")
            print(f"⏭️  تم تخطي: {self.skipped_count} حساب")
            print(f"❌ أخطاء: {self.error_count} حساب")
            print(f"{'='*60}\n")

            if self.error_count == 0:
                print("🎉 تم الاستيراد بنجاح!")
            else:
                print("⚠️  تم الاستيراد مع بعض الأخطاء")

        except FileNotFoundError:
            print(f"❌ الملف غير موجود: {json_file}")
        except json.JSONDecodeError as e:
            print(f"❌ خطأ في قراءة ملف JSON: {e}")
        except Exception as e:
            print(f"❌ خطأ غير متوقع: {e}")

    def clear_all_accounts(self):
        """حذف جميع الحسابات (خطير!)"""
        print("\n⚠️  تحذير: سيتم حذف جميع الحسابات!")
        confirm = input("هل أنت متأكد؟ اكتب 'نعم' للتأكيد: ")

        if confirm.strip() == 'نعم':
            try:
                accounts = self.repo.get_all_accounts()
                for account in accounts:
                    self.repo.delete_account(account.id)
                print(f"✅ تم حذف {len(accounts)} حساب")
            except Exception as e:
                print(f"❌ خطأ في الحذف: {e}")
        else:
            print("❌ تم إلغاء العملية")


def main():
    """الدالة الرئيسية"""
    import argparse

    parser = argparse.ArgumentParser(
        description='استيراد شجرة الحسابات الاحترافية إلى SkyWave ERP'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='تحديث الحسابات الموجودة'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='حذف جميع الحسابات القديمة قبل الاستيراد (خطير!)'
    )
    parser.add_argument(
        '--file',
        default='chart_of_accounts_enterprise.json',
        help='مسار ملف JSON (افتراضي: chart_of_accounts_enterprise.json)'
    )

    args = parser.parse_args()

    # إنشاء Repository
    try:
        repo = Repository()
        importer = ChartOfAccountsImporter(repo)

        # حذف الحسابات القديمة إذا طلب المستخدم
        if args.clear:
            importer.clear_all_accounts()

        # استيراد الحسابات
        importer.import_from_json(args.file, force_update=args.force)

    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
