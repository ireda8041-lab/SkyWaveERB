# pylint: disable=too-many-lines,too-many-nested-blocks,too-many-positional-arguments,too-many-public-methods
# الملف: services/accounting_service.py

import time
import traceback
from datetime import datetime, timedelta
from typing import Any

from core import schemas
from core.event_bus import EventBus
from core.logger import get_logger
from core.repository import Repository
from core.signals import app_signals

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


# إشعارات العمليات
try:
    from core.notification_bridge import notify_operation
except ImportError:

    def notify_operation(action, entity_type, entity_name):
        pass


logger = get_logger(__name__)


class AccountingService:
    """
    الروبوت المحاسبي (Service Layer).
    يستمع للأحداث المالية (زي إنشاء فاتورة)
    ويقوم بإنشاء قيود اليومية المحاسبية أوتوماتيكياً.
    """

    # ==================== أكواد الحسابات الرئيسية (Enterprise 6-Digit System) ====================
    # الأصول
    ACC_RECEIVABLE_CODE = "112100"  # حساب العملاء التجاريين - مستحقات (مدين)
    CASH_ACCOUNT_CODE = "111101"  # حساب الخزنة الرئيسية (مدين عند التحصيل)

    # الإيرادات
    SERVICE_REVENUE_CODE = "410100"  # حساب إيرادات التسويق الرقمي (دائن)
    DISCOUNT_ALLOWED_CODE = "610002"  # خصم مسموح به (مصروف)

    # الخصوم
    VAT_PAYABLE_CODE = "212200"  # حساب ضريبة القيمة المضافة (دائن - خصوم)
    UNEARNED_REVENUE_CODE = "212100"  # دفعات مقدمة من العملاء (التزام)

    # تكاليف الإيرادات (COGS) - كود 5
    COGS_ADS_CODE = "510001"  # ميزانية إعلانات
    COGS_HOSTING_CODE = "510002"  # تكلفة استضافة
    COGS_OUTSOURCING_CODE = "510003"  # أجور مستقلين

    # المصروفات التشغيلية (OPEX) - كود 6
    OPEX_SALARIES_CODE = "620001"  # رواتب الموظفين
    OPEX_RENT_CODE = "620002"  # إيجار ومرافق
    OPEX_BANK_FEES_CODE = "630001"  # رسوم بنكية

    # ⚡ Cache للشجرة المحاسبية
    _hierarchy_cache = None
    _hierarchy_cache_time = 0
    _HIERARCHY_CACHE_TTL = 300  # ⚡ 5 دقائق بدلاً من 60 ثانية

    def __init__(self, repository: Repository, event_bus: EventBus):
        """
        تهيئة الروبوت المحاسبي

        Args:
            repository: مخزن البيانات الرئيسي
            event_bus: نظام الأحداث للتواصل بين الخدمات
        """
        self.repo = repository
        self.bus = event_bus
        logger.info("الروبوت المحاسبي (AccountingService) جاهز")

        # أهم خطوة: الروبوت بيشترك في الأحداث أول ما يشتغل
        self._subscribe_to_events()

        # ⚡ التحقق من وجود الحسابات الأساسية
        self._ensure_default_accounts_exist()

    def _ensure_default_accounts_exist(self) -> None:
        """
        ⚡ التحقق من وجود الحسابات المحاسبية الأساسية وإعادة حساب الأرصدة

        الحسابات الضرورية للنظام:
        - حساب العملاء (112100) - للقيود المحاسبية عند إنشاء مشروع
        - حساب الإيرادات (410100) - للقيود المحاسبية عند إنشاء مشروع
        - حسابات النقدية (111xxx) - للدفعات والمصروفات
        """
        try:
            existing_accounts = self.repo.get_all_accounts()
            existing_codes = {acc.code for acc in existing_accounts if acc.code}

            required_accounts = {
                "112100": {
                    "name": "حساب العملاء",
                    "type": schemas.AccountType.ASSET,
                    "description": "حساب أصول (مدين) لتجميع مديونيات العملاء",
                },
                "410100": {
                    "name": "إيرادات الخدمات",
                    "type": schemas.AccountType.REVENUE,
                    "description": "حساب إيرادات (دائن) لتجميع إيرادات الخدمات",
                },
            }

            missing = [code for code in required_accounts.keys() if code not in existing_codes]
            if missing:
                safe_print(f"WARNING: [AccountingService] ⚠️ حسابات مفقودة: {missing}")
                for code in missing:
                    try:
                        meta = required_accounts[code]
                        created = self.repo.create_account(
                            schemas.Account(
                                name=meta["name"],
                                code=code,
                                type=meta["type"],
                                parent_code=None,
                                is_group=False,
                                balance=0.0,
                                description=meta["description"],
                            )
                        )
                        safe_print(
                            f"INFO: [AccountingService] ✅ تم إنشاء الحساب الافتراضي: {created.code} - {created.name}"
                        )
                    except Exception as create_err:
                        safe_print(
                            f"WARNING: [AccountingService] فشل إنشاء الحساب الافتراضي {code}: {create_err}"
                        )

                existing_accounts = self.repo.get_all_accounts()
                existing_codes = {acc.code for acc in existing_accounts if acc.code}

            cash_count = sum(1 for acc in existing_accounts if acc.type == schemas.AccountType.CASH)
            safe_print(
                f"INFO: [AccountingService] ✅ تم العثور على {len(existing_codes)} حساب ({cash_count} نقدية)"
            )

            # ⚡ إعادة حساب أرصدة الحسابات النقدية من الدفعات والمصروفات
            self._recalculate_cash_balances()

            # ⚠️ معطل: لا يتم إنشاء حسابات عملاء وإيرادات للمشاريع
            # self._recalculate_project_accounts()

        except Exception as e:
            safe_print(f"WARNING: [AccountingService] فشل التحقق من الحسابات: {e}")

    def _recalculate_project_accounts(self) -> None:
        """
        ⚡ إعادة حساب أرصدة حسابات العملاء والإيرادات من إجمالي المشاريع
        - حساب العملاء (112100) = إجمالي قيمة المشاريع
        - حساب الإيرادات (410100) = إجمالي قيمة المشاريع
        """
        try:
            cursor = self.repo.sqlite_conn.cursor()
            try:
                # حساب إجمالي المشاريع
                cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM projects")
                total_projects = cursor.fetchone()[0]

                # تحديث حساب العملاء
                cursor.execute(
                    "UPDATE accounts SET balance = ? WHERE code = ?",
                    (total_projects, self.ACC_RECEIVABLE_CODE),
                )

                # تحديث حساب الإيرادات
                cursor.execute(
                    "UPDATE accounts SET balance = ? WHERE code = ?",
                    (total_projects, self.SERVICE_REVENUE_CODE),
                )

                self.repo.sqlite_conn.commit()
                safe_print(
                    f"INFO: [AccountingService] ✅ تم تحديث حسابات المشاريع: {total_projects}"
                )
            finally:
                cursor.close()
        except Exception as e:
            safe_print(f"WARNING: [AccountingService] فشل تحديث حسابات المشاريع: {e}")

    def _recalculate_cash_balances(self) -> None:
        """
        ⚡ إعادة حساب أرصدة الحسابات النقدية من الدفعات والمصروفات
        الرصيد = إجمالي الدفعات المستلمة - إجمالي المصروفات المدفوعة

        ⚠️ هذه الدالة تُستدعى فقط عند بدء البرنامج لضمان صحة الأرصدة
        ⚡ محسّنة: تستخدم cursor منفصل لتجنب Recursive cursor error
        """
        try:
            # ⚡ استخدام cursor منفصل
            cursor = self.repo.sqlite_conn.cursor()
            cursor.row_factory = self.repo.sqlite_conn.row_factory

            try:
                # ⚡ جلب الحسابات النقدية (الأوراق فقط - ليس المجموعات)
                # المجموعات تنتهي بـ 000 (مثل 111000)
                # نوع الحساب قد يكون 'cash' أو 'أصول نقدية'
                cursor.execute(
                    """
                    SELECT code, name, balance FROM accounts
                    WHERE (type = 'cash' OR type = 'أصول نقدية' OR code LIKE '111%')
                    AND code NOT LIKE '%000'
                    AND code IS NOT NULL
                """
                )
                cash_accounts = cursor.fetchall()

                if not cash_accounts:
                    return

                # ⚡ حساب إجمالي الدفعات لكل حساب باستخدام SQL
                cursor.execute(
                    """
                    SELECT account_id, COALESCE(SUM(amount), 0) as total
                    FROM payments
                    WHERE account_id IS NOT NULL
                    GROUP BY account_id
                """
                )
                payments_by_account = {row[0]: row[1] for row in cursor.fetchall()}

                # ⚡ حساب إجمالي المصروفات لكل حساب باستخدام SQL
                cursor.execute(
                    """
                    SELECT account_id, COALESCE(SUM(amount), 0) as total
                    FROM expenses
                    WHERE account_id IS NOT NULL
                    GROUP BY account_id
                """
                )
                expenses_by_account = {row[0]: row[1] for row in cursor.fetchall()}
            finally:
                cursor.close()

            # تحديث أرصدة الحسابات النقدية
            updated_count = 0
            for acc_code, acc_name, current_balance in cash_accounts:
                payments_total = payments_by_account.get(acc_code, 0)
                expenses_total = expenses_by_account.get(acc_code, 0)
                new_balance = payments_total - expenses_total

                # تحديث الرصيد إذا تغير
                if abs((current_balance or 0) - new_balance) > 0.01:
                    safe_print(
                        f"INFO: [AccountingService] تحديث رصيد {acc_code} ({acc_name}): {current_balance} -> {new_balance}"
                    )
                    self.repo.update_account_balance(acc_code, new_balance)
                    updated_count += 1

            # تحديث أرصدة المجموعات (مجموع الأبناء)
            self._update_parent_balances()

            if updated_count > 0:
                safe_print(f"INFO: [AccountingService] ✅ تم تحديث {updated_count} رصيد حساب نقدي")
                # ⚡ إبطال الـ cache بعد التحديث
                AccountingService._hierarchy_cache = None
                AccountingService._hierarchy_cache_time = 0

        except Exception as e:
            safe_print(f"WARNING: [AccountingService] فشل إعادة حساب الأرصدة: {e}")

            traceback.print_exc()

    def recalculate_account_balance(self, account_code: str) -> float:
        """
        ⚡ إعادة حساب رصيد حساب نقدي واحد من الدفعات والمصروفات
        يُستخدم بعد إضافة/تعديل/حذف دفعة أو مصروف

        ⚡ محسّن: يستخدم cursor منفصل لتجنب Recursive cursor error

        Returns:
            الرصيد الجديد
        """
        try:
            # ⚡ استخدام cursor منفصل لتجنب Recursive cursor error
            cursor = self.repo.sqlite_conn.cursor()
            cursor.row_factory = self.repo.sqlite_conn.row_factory

            try:
                # حساب إجمالي الدفعات لهذا الحساب
                cursor.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE account_id = ?",
                    (account_code,),
                )
                payments_total = cursor.fetchone()[0]

                # حساب إجمالي المصروفات لهذا الحساب
                cursor.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE account_id = ?",
                    (account_code,),
                )
                expenses_total = cursor.fetchone()[0]
            finally:
                cursor.close()

            # الرصيد = الدفعات - المصروفات
            new_balance = payments_total - expenses_total

            # تحديث الرصيد في قاعدة البيانات
            self.repo.update_account_balance(account_code, new_balance)

            safe_print(
                f"SUCCESS: [AccountingService] ✅ تم تحديث رصيد {account_code} = {new_balance}"
            )

            # إبطال الـ cache
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0

            return new_balance

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل إعادة حساب رصيد {account_code}: {e}")
            return 0.0

    def recalculate_cash_balances(self) -> dict[str, float]:
        """
        ⚡ إعادة حساب أرصدة الحسابات النقدية من الدفعات والمصروفات
        يُستخدم لإصلاح الأرصدة الخاطئة

        Returns:
            قاموس بالأرصدة الجديدة {account_code: new_balance}
        """
        results = {}
        try:
            safe_print("INFO: [AccountingService] 🔄 جاري إعادة حساب الأرصدة النقدية...")

            # ⚡ استخدام cursor منفصل
            cursor = self.repo.sqlite_conn.cursor()
            cursor.row_factory = self.repo.sqlite_conn.row_factory

            try:
                # جلب جميع الحسابات النقدية
                # نوع الحساب قد يكون 'cash' أو 'أصول نقدية'
                cursor.execute(
                    """
                    SELECT code, name, balance FROM accounts
                    WHERE (type = 'cash' OR type = 'أصول نقدية' OR code LIKE '111%')
                    AND code IS NOT NULL
                """
                )
                cash_accounts = cursor.fetchall()

                # حساب إجمالي الدفعات لكل حساب
                cursor.execute(
                    """
                    SELECT account_id, COALESCE(SUM(amount), 0) as total
                    FROM payments WHERE account_id IS NOT NULL
                    GROUP BY account_id
                """
                )
                payments_by_account = {row[0]: row[1] for row in cursor.fetchall()}

                # حساب إجمالي المصروفات لكل حساب
                cursor.execute(
                    """
                    SELECT account_id, COALESCE(SUM(amount), 0) as total
                    FROM expenses WHERE account_id IS NOT NULL
                    GROUP BY account_id
                """
                )
                expenses_by_account = {row[0]: row[1] for row in cursor.fetchall()}
            finally:
                cursor.close()

            # تحديث أرصدة الحسابات النقدية
            for acc_code, acc_name, current_balance in cash_accounts:
                # تخطي المجموعات (سيتم حسابها لاحقاً)
                if acc_code.endswith("000"):
                    continue

                payments_total = payments_by_account.get(acc_code, 0)
                expenses_total = expenses_by_account.get(acc_code, 0)
                new_balance = payments_total - expenses_total

                # تحديث الرصيد
                if abs((current_balance or 0) - new_balance) > 0.01:
                    safe_print(
                        f"INFO: [AccountingService] تصحيح {acc_code} ({acc_name}): {current_balance} -> {new_balance}"
                    )
                    self.repo.update_account_balance(acc_code, new_balance)

                results[acc_code] = new_balance

            # تحديث أرصدة المجموعات
            self._update_parent_balances()

            # إبطال الـ cache
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0

            safe_print(f"INFO: [AccountingService] ✅ تم إعادة حساب {len(results)} رصيد")
            return results

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل إعادة حساب الأرصدة: {e}")
            return results

    def _update_parent_balances(self) -> None:
        """
        تحديث أرصدة الحسابات الأب (المجموعات) = مجموع أرصدة الأبناء
        ⚡ محسّنة: تستخدم cursor منفصل لتجنب Recursive cursor error
        """
        try:
            # ⚡ استخدام cursor منفصل
            cursor = self.repo.sqlite_conn.cursor()
            cursor.row_factory = self.repo.sqlite_conn.row_factory

            try:
                # ⚡ جلب كل الحسابات مع أرصدتها باستخدام SQL
                # العمود اسمه parent_id مش parent_code
                cursor.execute(
                    "SELECT code, balance, parent_id FROM accounts WHERE code IS NOT NULL"
                )
                rows = cursor.fetchall()
                accounts_data = {row[0]: row[1] or 0 for row in rows}
                parent_ids = {row[0]: row[2] for row in rows}
            finally:
                cursor.close()

            # ⚡ تحديث المجموعات بناءً على parent_id الفعلي
            # جمع الأبناء لكل أب
            children_by_parent: dict[str, list[str]] = {}
            for code, parent_id in parent_ids.items():
                if parent_id and parent_id in accounts_data:
                    if parent_id not in children_by_parent:
                        children_by_parent[parent_id] = []
                    children_by_parent[parent_id].append(code)

            # تحديث رصيد كل أب = مجموع أرصدة أبنائه
            for parent_code, children in children_by_parent.items():
                children_balance = sum(accounts_data.get(child, 0) for child in children)
                current_balance = accounts_data.get(parent_code, 0)

                if abs(current_balance - children_balance) > 0.01:
                    self.repo.update_account_balance(parent_code, children_balance)
                    safe_print(
                        f"INFO: [AccountingService] تحديث مجموعة {parent_code}: {children_balance}"
                    )

        except Exception as e:
            safe_print(f"WARNING: [AccountingService] فشل تحديث أرصدة المجموعات: {e}")

    def _subscribe_to_events(self) -> None:
        """
        الاشتراك في أحداث الدفعات والمصروفات فقط
        ⚠️ مبسط: بدون قيود يومية - فقط تحديث أرصدة الحسابات النقدية
        """
        self.bus.subscribe("EXPENSE_CREATED", self.handle_new_expense)
        self.bus.subscribe("EXPENSE_UPDATED", self.handle_updated_expense)
        self.bus.subscribe("EXPENSE_DELETED", self.handle_deleted_expense)
        self.bus.subscribe("PAYMENT_RECEIVED", self.handle_new_payment)
        self.bus.subscribe("PAYMENT_UPDATED", self.handle_updated_payment)
        self.bus.subscribe("PAYMENT_DELETED", self.handle_deleted_payment)
        # ⚠️ معطل: لا قيود للمشاريع والفواتير
        # self.bus.subscribe("PROJECT_CREATED", self.handle_new_project)
        # self.bus.subscribe("PROJECT_EDITED", self.handle_edited_project)
        # self.bus.subscribe("INVOICE_CREATED", self.handle_new_invoice)
        logger.info("[AccountingService] تم الاشتراك في أحداث الدفعات والمصروفات")

    def get_all_journal_entries(self) -> list[schemas.JournalEntry]:
        """
        جلب كل قيود اليومية

        Returns:
            قائمة بجميع قيود اليومية
        """
        try:
            return self.repo.get_all_journal_entries()
        except Exception as e:
            logger.error("[AccountingService] فشل جلب قيود اليومية: %s", e, exc_info=True)
            return []

    def recalculate_all_balances(self) -> bool:
        """
        🔄 إعادة حساب جميع أرصدة الحسابات من القيود المحاسبية

        هذه الدالة تُستخدم لإصلاح الأرصدة في حالة عدم تطابقها مع القيود

        Returns:
            True إذا نجحت العملية
        """
        safe_print("INFO: [AccountingService] 🔄 جاري إعادة حساب جميع الأرصدة من القيود...")

        try:
            # 1. جلب جميع الحسابات
            accounts = self.repo.get_all_accounts()
            if not accounts:
                safe_print("WARNING: [AccountingService] لا توجد حسابات")
                return False

            # 2. جلب جميع القيود
            journal_entries = self.repo.get_all_journal_entries()
            safe_print(f"INFO: [AccountingService] تم جلب {len(journal_entries)} قيد محاسبي")

            # 3. حساب الحركات لكل حساب
            account_movements = {}  # {code: {'debit': 0, 'credit': 0}}

            # إنشاء قاموس لربط account_id بـ account_code
            account_id_to_code = {}
            for acc in accounts:
                if acc.code:
                    if hasattr(acc, "_mongo_id") and acc._mongo_id:
                        account_id_to_code[str(acc._mongo_id)] = acc.code
                    if hasattr(acc, "id") and acc.id:
                        account_id_to_code[str(acc.id)] = acc.code
                    account_id_to_code[acc.code] = acc.code

            for entry in journal_entries:
                for line in entry.lines:
                    code = getattr(line, "account_code", None)
                    if not code:
                        acc_id = getattr(line, "account_id", None)
                        if acc_id:
                            code = account_id_to_code.get(str(acc_id))

                    if not code:
                        continue

                    if code not in account_movements:
                        account_movements[code] = {"debit": 0.0, "credit": 0.0}
                    account_movements[code]["debit"] += getattr(line, "debit", 0) or 0.0
                    account_movements[code]["credit"] += getattr(line, "credit", 0) or 0.0

            # 4. تحديث أرصدة الحسابات
            updated_count = 0
            asset_types = [
                schemas.AccountType.ASSET,
                schemas.AccountType.CASH,
                schemas.AccountType.EXPENSE,
            ]

            for acc in accounts:
                if not acc.code:
                    continue

                movements = account_movements.get(acc.code, {"debit": 0.0, "credit": 0.0})
                debit_total = movements["debit"]
                credit_total = movements["credit"]

                # حساب الرصيد حسب طبيعة الحساب
                if acc.type in asset_types:
                    new_balance = debit_total - credit_total
                else:
                    new_balance = credit_total - debit_total

                # تحديث الرصيد إذا تغير
                if abs(acc.balance - new_balance) > 0.01:
                    safe_print(
                        f"INFO: تحديث {acc.code} ({acc.name}): {acc.balance} -> {new_balance}"
                    )
                    account_id = acc._mongo_id or str(acc.id)
                    self.repo.update_account(
                        account_id, acc.model_copy(update={"balance": new_balance})
                    )
                    updated_count += 1

            # 5. إبطال الـ cache
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0

            safe_print(f"SUCCESS: [AccountingService] ✅ تم تحديث {updated_count} حساب")
            return True

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل إعادة حساب الأرصدة: {e}")

            traceback.print_exc()
            return False

    def get_hierarchy_with_balances(self, force_refresh: bool = False) -> dict[str, dict]:
        """
        ⚡ جلب شجرة الحسابات مع حساب الأرصدة التراكمية للمجموعات (مع cache)
        ⚡ محسّن للسرعة: يستخدم الأرصدة المخزنة مباشرة بدلاً من حساب القيود

        Returns:
            Dict[code, {obj: Account, total: float, children: []}]
        """

        # ⚡ استخدام الـ cache إذا كان صالحاً
        current_time = time.time()
        if (
            not force_refresh
            and AccountingService._hierarchy_cache
            and (current_time - AccountingService._hierarchy_cache_time)
            < AccountingService._HIERARCHY_CACHE_TTL
        ):
            return AccountingService._hierarchy_cache

        try:
            accounts = self.repo.get_all_accounts()

            if not accounts:
                return {}

            # ⚡ إنشاء قاموس للوصول السريع O(1)
            tree_map: dict[str, dict] = {}
            for acc in accounts:
                if acc.code:
                    # ⚡ استخدام الرصيد المخزن مباشرة (أسرع بكثير)
                    stored_balance = getattr(acc, "balance", 0.0) or 0.0
                    tree_map[acc.code] = {
                        "obj": acc,
                        "total": stored_balance,
                        "children": [],
                        "is_group": getattr(acc, "is_group", False),
                    }

            # ⚡ دالة استنتاج كود الأب
            def get_parent_code_from_code(code: str) -> str | None:
                if not code:
                    return None
                code_len = len(code)
                if code_len == 6:
                    if code.endswith("00000"):
                        return None
                    elif code.endswith("0000"):
                        return code[0] + "00000"
                    elif code.endswith("000"):
                        return code[:2] + "0000"
                    elif code.endswith("00"):
                        return code[:3] + "000"
                    else:
                        return code[:4] + "00"
                elif code_len == 4:
                    if code.endswith("000"):
                        return None
                    elif code.endswith("00"):
                        return code[0] + "000"
                    else:
                        return code[:2] + "00"
                return None

            # ⚡ ربط الحسابات بالآباء
            for acc in accounts:
                if not acc.code:
                    continue
                code_len = len(acc.code)
                if (code_len == 6 and acc.code.endswith("00000")) or (
                    code_len == 4 and acc.code.endswith("000")
                ):
                    continue
                parent_code = getattr(acc, "parent_id", None) or getattr(acc, "parent_code", None)
                if not parent_code:
                    parent_code = get_parent_code_from_code(acc.code)
                if parent_code and parent_code in tree_map and parent_code != acc.code:
                    tree_map[parent_code]["children"].append(tree_map[acc.code])

            # ⚡ حساب الأرصدة التراكمية للمجموعات
            def calculate_total(node: dict) -> float:
                if not node["children"]:
                    return float(node["total"])
                total = sum(calculate_total(child) for child in node["children"])
                node["total"] = total
                return float(total)

            # ⚡ حساب الجذور
            for _, node in tree_map.items():
                acc = node["obj"]
                parent_id = getattr(acc, "parent_id", None) or getattr(acc, "parent_code", None)
                if not parent_id or parent_id not in tree_map:
                    calculate_total(node)

            # ⚡ حفظ في الـ cache
            AccountingService._hierarchy_cache = tree_map
            AccountingService._hierarchy_cache_time = int(time.time())

            return tree_map

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل حساب الأرصدة التراكمية: {e}")
            return {}

    def get_financial_summary(self) -> dict[str, float]:
        """
        جلب ملخص مالي سريع (الأصول، الخصوم، الإيرادات، المصروفات، صافي الربح)

        ⚡ محسّن:
        - يحسب الإيرادات من الدفعات المستلمة من المشاريع
        - يحسب المصروفات من جدول expenses

        Returns:
            Dict مع المفاتيح: assets, liabilities, equity, revenue, expenses, cogs, opex, gross_profit, net_profit
        """
        try:
            tree_map = self.get_hierarchy_with_balances()

            # استخراج الأرصدة من الحسابات الرئيسية (يدعم 4 و 6 أرقام)
            assets = tree_map.get("100000", {}).get("total", 0.0) or tree_map.get("1000", {}).get(
                "total", 0.0
            )
            liabilities = tree_map.get("200000", {}).get("total", 0.0) or tree_map.get(
                "2000", {}
            ).get("total", 0.0)
            equity = tree_map.get("300000", {}).get("total", 0.0) or tree_map.get("3000", {}).get(
                "total", 0.0
            )

            # ⚡ حساب الإيرادات من حسابات الإيرادات أو من الدفعات
            revenue = tree_map.get("400000", {}).get("total", 0.0) or tree_map.get("4000", {}).get(
                "total", 0.0
            )

            # ⚡ إذا لم توجد حسابات إيرادات، احسب من الدفعات المستلمة باستخدام SQL
            if revenue == 0:
                try:
                    # ⚡ استخدام cursor منفصل لتجنب Recursive cursor error
                    cursor = self.repo.sqlite_conn.cursor()
                    try:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments")
                        revenue = cursor.fetchone()[0]
                        safe_print(f"INFO: [AccountingService] الإيرادات من الدفعات: {revenue}")
                    finally:
                        cursor.close()
                except Exception as e:
                    safe_print(f"WARNING: [AccountingService] فشل جلب الدفعات: {e}")

            # ⚡ Enterprise: فصل COGS عن OPEX
            cogs = tree_map.get("500000", {}).get("total", 0.0)
            opex = tree_map.get("600000", {}).get("total", 0.0)

            # للتوافق مع النظام القديم (4 أرقام)
            if cogs == 0 and opex == 0:
                expenses_from_accounts = tree_map.get("5000", {}).get("total", 0.0)
                cogs = expenses_from_accounts
                opex = 0

            # إجمالي المصروفات من الحسابات
            total_expenses = cogs + opex

            # ⚡ إذا لم توجد حسابات مصروفات، احسب من جدول expenses مباشرة باستخدام SQL
            if total_expenses == 0:
                try:
                    # ⚡ استخدام cursor منفصل لتجنب Recursive cursor error
                    cursor = self.repo.sqlite_conn.cursor()
                    try:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses")
                        total_expenses = cursor.fetchone()[0]
                        safe_print(
                            f"INFO: [AccountingService] المصروفات من جدول expenses: {total_expenses}"
                        )
                    finally:
                        cursor.close()
                except Exception as e:
                    safe_print(f"WARNING: [AccountingService] فشل جلب المصروفات: {e}")

            # ⚡ حساب الأصول من الحسابات النقدية إذا لم توجد حسابات أصول رئيسية
            if assets == 0:
                for code, node in tree_map.items():
                    if code.startswith("11") and not node.get("children"):
                        assets += node.get("total", 0.0)
                if assets == 0:
                    for code, node in tree_map.items():
                        if code.startswith("111") and node.get("children"):
                            assets = node.get("total", 0.0)
                            break

            # ⚡ هامش الربح الإجمالي
            gross_profit = revenue - cogs

            # ⚡ صافي الربح = الإيرادات (الدفعات) - المصروفات
            net_profit = revenue - total_expenses

            return {
                "assets": assets,
                "liabilities": liabilities,
                "equity": equity,
                "revenue": revenue,
                "cogs": cogs,
                "opex": opex,
                "expenses": total_expenses,
                "gross_profit": gross_profit,
                "net_profit": net_profit,
            }

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل جلب الملخص المالي: {e}")
            return {
                "assets": 0.0,
                "liabilities": 0.0,
                "equity": 0.0,
                "revenue": 0.0,
                "cogs": 0.0,
                "opex": 0.0,
                "expenses": 0.0,
                "gross_profit": 0.0,
                "net_profit": 0.0,
            }

    def handle_new_invoice(self, data: dict):
        """
        معالج إنشاء فاتورة جديدة - ينشئ قيد يومية تلقائياً

        القيد المحاسبي للفاتورة:
        - مدين: حساب العملاء (1140) - يزيد المستحقات
        - دائن: حساب الإيرادات (4110) - يزيد الإيرادات
        """
        invoice: schemas.Invoice = data["invoice"]
        safe_print(
            f"INFO: [AccountingService] تم استقبال حدث فاتورة جديدة: {invoice.invoice_number}"
        )

        try:
            # إنشاء معرف الفاتورة
            invoice_id = (
                getattr(invoice, "_mongo_id", None)
                or str(getattr(invoice, "id", ""))
                or invoice.invoice_number
            )

            # إنشاء القيد المحاسبي الرئيسي (العملاء مدين، الإيرادات دائن)
            success = self.post_journal_entry(
                date=invoice.issue_date or datetime.now(),
                description=f"فاتورة مبيعات: {invoice.invoice_number}",
                ref_type="invoice",
                ref_id=invoice_id,
                debit_account_code=self.ACC_RECEIVABLE_CODE,  # حساب العملاء (مدين)
                credit_account_code=self.SERVICE_REVENUE_CODE,  # حساب الإيرادات (دائن)
                amount=invoice.total_amount,
            )

            if success:
                safe_print(
                    f"SUCCESS: [AccountingService] تم إنشاء قيد اليومية للفاتورة {invoice.invoice_number}"
                )
            else:
                safe_print(
                    f"ERROR: [AccountingService] فشل إنشاء قيد اليومية للفاتورة {invoice.invoice_number}"
                )

        except Exception as e:
            safe_print(
                f"ERROR: [AccountingService] فشل معالجة الفاتورة {invoice.invoice_number}: {e}"
            )

            traceback.print_exc()

    def handle_new_project(self, data: dict):
        """
        ✅ معالج إنشاء مشروع جديد
        ⚠️ معطل: لا يتم إنشاء قيود محاسبية للمشاريع
        """
        project: schemas.Project = data["project"]
        safe_print(f"INFO: [AccountingService] تم استقبال حدث مشروع جديد: {project.name}")
        # ⚠️ معطل - لا يتم إنشاء قيود محاسبية
        pass

    def handle_edited_project(self, data: dict):
        """
        ✅ معالج تعديل مشروع
        ⚠️ معطل: لا يتم تحديث قيود محاسبية للمشاريع
        """
        project: schemas.Project = data["project"]
        safe_print(f"INFO: [AccountingService] تم استقبال حدث تعديل مشروع: {project.name}")
        # ⚠️ معطل - لا يتم تحديث قيود محاسبية
        pass

    def handle_new_expense(self, data):
        """
        معالج إنشاء مصروف جديد - يعيد حساب رصيد الحساب

        عند إنشاء مصروف:
        - يتم إعادة حساب رصيد حساب الدفع من جميع الدفعات والمصروفات
        """
        # دعم استقبال البيانات كـ dict أو كـ Expense مباشرة
        if isinstance(data, dict):
            expense = data.get("expense", data)
            if isinstance(expense, dict):
                expense = schemas.Expense(**expense)
        else:
            expense = data

        safe_print(
            f"INFO: [AccountingService] تم استقبال حدث مصروف جديد: {expense.category} - {expense.amount} جنيه"
        )

        try:
            # ⚡ إبطال الـ cache أولاً
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0

            # تحديد حساب الدفع
            payment_account_code = getattr(expense, "account_id", None) or getattr(
                expense, "payment_account_id", None
            )

            if not payment_account_code:
                safe_print("WARNING: [AccountingService] لم يتم تحديد حساب الدفع!")
                return

            # ⚡ إعادة حساب رصيد الحساب من جميع الدفعات والمصروفات
            new_balance = self.recalculate_account_balance(payment_account_code)

            safe_print(
                f"SUCCESS: [AccountingService] ✅ تم تحديث رصيد {payment_account_code} = {new_balance}"
            )

            # ⚡ إرسال إشارات التحديث الفوري
            try:
                app_signals.emit_data_changed("accounting")
                app_signals.emit_data_changed("expenses")
            except Exception as sig_err:
                safe_print(f"WARNING: [AccountingService] فشل إرسال الإشارات: {sig_err}")

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل معالجة المصروف: {e}")

            traceback.print_exc()

    def handle_updated_expense(self, data):
        """
        ✅ معالج تعديل مصروف - يعيد حساب أرصدة جميع الحسابات النقدية
        """
        try:
            # ⚡ إبطال الـ cache أولاً
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0

            # ⚡ إعادة حساب جميع الحسابات النقدية (لأن الحساب القديم قد يكون مختلفاً)
            self._recalculate_cash_balances()

            # ⚡ إرسال إشارات التحديث
            try:
                app_signals.emit_data_changed("accounting")
                app_signals.emit_data_changed("expenses")
            except:
                pass

        except Exception:
            pass

    def handle_deleted_expense(self, data: dict):
        """
        ✅ معالج حذف مصروف - يعيد حساب أرصدة جميع الحسابات النقدية
        """
        try:
            # ⚡ إبطال الـ cache أولاً
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0

            self._recalculate_cash_balances()
            try:
                app_signals.emit_data_changed("accounting")
                app_signals.emit_data_changed("expenses")
            except:
                pass
        except Exception:
            pass

    def handle_new_payment(self, data: dict):
        """معالج استلام دفعة جديدة"""
        try:
            # ⚡ إبطال الـ cache أولاً
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0
            self._recalculate_cash_balances()
            try:
                app_signals.emit_data_changed("accounting")
                app_signals.emit_data_changed("payments")
            except:
                pass
        except Exception:
            pass

    def handle_updated_payment(self, data: dict):
        """معالج تعديل دفعة"""
        try:
            # ⚡ إبطال الـ cache أولاً
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0
            self._recalculate_cash_balances()
            try:
                app_signals.emit_data_changed("accounting")
                app_signals.emit_data_changed("payments")
            except:
                pass
        except Exception:
            pass

    def handle_deleted_payment(self, data: dict):
        """معالج حذف دفعة"""
        try:
            # ⚡ إبطال الـ cache أولاً
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0
            self._recalculate_cash_balances()
            try:
                app_signals.emit_data_changed("accounting")
                app_signals.emit_data_changed("payments")
            except:
                pass
        except Exception:
            pass

    def _update_account_balance(self, account, amount: float, is_debit: bool):
        """تحديث رصيد الحساب"""
        try:
            old_balance = account.balance or 0.0

            # الأصول والمصروفات: المدين يزيد، الدائن ينقص
            # الخصوم والإيرادات وحقوق الملكية: الدائن يزيد، المدين ينقص

            # ⚡ دعم كل من enum و string
            account_type = account.type
            if hasattr(account_type, "value"):
                account_type_str = account_type.value
            else:
                account_type_str = str(account_type)

            # الأنواع التي تزيد بالمدين
            debit_increase_types = ["ASSET", "CASH", "EXPENSE", "أصول", "أصول نقدية", "مصروفات"]

            is_debit_increase_type = account_type_str in debit_increase_types

            if is_debit_increase_type:
                new_balance = old_balance + amount if is_debit else old_balance - amount
            else:
                # الإيرادات والخصوم تزيد بالدائن
                new_balance = old_balance - amount if is_debit else old_balance + amount

            safe_print(f"DEBUG: [AccountingService] تحديث رصيد {account.name} ({account.code}):")
            safe_print(f"  - نوع الحساب: {account_type_str}")
            safe_print(f"  - الرصيد القديم: {old_balance}")
            safe_print(f"  - المبلغ: {amount} ({'مدين' if is_debit else 'دائن'})")
            safe_print(f"  - الرصيد الجديد: {new_balance}")

            # ⚡ إصلاح: التحقق من وجود ID صالح - استخدام code كـ fallback
            account_id = (
                account._mongo_id or (str(account.id) if account.id else None) or account.code
            )
            if not account_id:
                safe_print(f"ERROR: [AccountingService] ❌ لا يوجد ID صالح للحساب {account.name}")
                return

            updated_account = account.model_copy(update={"balance": new_balance})
            result = self.repo.update_account(account_id, updated_account)

            if result:
                safe_print(
                    f"SUCCESS: [AccountingService] ✅ تم تحديث رصيد {account.name}: {old_balance} -> {new_balance}"
                )
            else:
                safe_print(f"WARNING: [AccountingService] ⚠️ فشل تحديث رصيد {account.name}")

            # إبطال الـ cache لإعادة حساب الأرصدة
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] ❌ فشل تحديث رصيد الحساب {account.name}: {e}")

            traceback.print_exc()

    def get_profit_and_loss(self, start_date: datetime, end_date: datetime) -> dict:
        """حساب تقرير الأرباح والخسائر لفترة محددة مع التفاصيل"""
        safe_print(f"INFO: [AccountingService] جاري حساب P&L من {start_date} إلى {end_date}")
        try:
            total_revenue = 0.0
            total_expenses = 0.0
            revenue_breakdown = {}
            expense_breakdown = {}

            all_accounts = self.repo.get_all_accounts()
            account_info = {
                str(acc._mongo_id or acc.id): {"type": acc.type, "name": acc.name, "code": acc.code}
                for acc in all_accounts
            }
            # أيضاً نضيف بالكود للبحث
            for acc in all_accounts:
                account_info[acc.code] = {"type": acc.type, "name": acc.name, "code": acc.code}

            all_entries = self.repo.get_all_journal_entries()

            for entry in all_entries:
                entry_date = entry.date
                if hasattr(entry_date, "replace"):
                    # تأكد من أن التاريخ بدون timezone
                    pass

                if start_date <= entry_date <= end_date:
                    for line in entry.lines:
                        acc_id = str(line.account_id)
                        acc_data = account_info.get(acc_id)

                        if not acc_data:
                            continue

                        acc_type = acc_data["type"]
                        acc_name = acc_data["name"]

                        if acc_type == schemas.AccountType.REVENUE:
                            total_revenue += line.credit
                            if acc_name not in revenue_breakdown:
                                revenue_breakdown[acc_name] = 0.0
                            revenue_breakdown[acc_name] += line.credit

                        elif acc_type == schemas.AccountType.EXPENSE:
                            total_expenses += line.debit
                            if acc_name not in expense_breakdown:
                                expense_breakdown[acc_name] = 0.0
                            expense_breakdown[acc_name] += line.debit

            net_profit = total_revenue - total_expenses

            return {
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "net_profit": net_profit,
                "revenue_breakdown": revenue_breakdown,
                "expense_breakdown": expense_breakdown,
            }

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل حساب P&L: {e}")
            return {
                "total_revenue": 0.0,
                "total_expenses": 0.0,
                "net_profit": 0.0,
                "revenue_breakdown": {},
                "expense_breakdown": {},
            }

    def handle_voided_invoice(self, invoice: schemas.Invoice):
        """
        (جديدة) المعالج الذي يتم استدعاؤه أوتوماتيكياً عند إلغاء فاتورة.
        """
        safe_print(
            f"INFO: [AccountingService] تم استقبال حدث إلغاء فاتورة: {invoice.invoice_number}"
        )

        try:
            doc_id = invoice._mongo_id or str(invoice.id)
            original_entry = self.repo.get_journal_entry_by_doc_id(doc_id)

            if not original_entry:
                safe_print(
                    f"WARNING: [AccountingService] لم يتم العثور على قيد أصلي للفاتورة {invoice.invoice_number} لعكسه."
                )
                return

            reversed_lines = []
            for line in original_entry.lines:
                reversed_lines.append(
                    schemas.JournalEntryLine(
                        account_id=line.account_id,
                        debit=line.credit,
                        credit=line.debit,
                        description=f"عكس قيد: {line.description}",
                    )
                )

            journal_entry_data = schemas.JournalEntry(
                date=datetime.now(),
                description=f"قيد آلي لعكس أثر الفاتورة الملغاة {invoice.invoice_number}",
                lines=reversed_lines,
                related_document_id=doc_id,
            )

            self.repo.create_journal_entry(journal_entry_data)
            safe_print(
                f"SUCCESS: [AccountingService] تم إنشاء القيد العكسي للفاتورة {invoice.invoice_number}."
            )

        except Exception as e:
            safe_print(
                f"ERROR: [AccountingService] فشل إنشاء القيد العكسي للفاتورة {invoice.invoice_number}: {e}"
            )

    def handle_edited_invoice(self, data: dict):
        """
        (معدلة) تعديل القيد الأصلي للفاتورة (باللوجيك الرباعي).
        """
        invoice: schemas.Invoice = data["invoice"]
        safe_print(
            f"INFO: [AccountingService] تم استقبال حدث تعديل فاتورة: {invoice.invoice_number}"
        )

        try:
            ar_account = self.repo.get_account_by_code(self.ACC_RECEIVABLE_CODE)
            rev_account = self.repo.get_account_by_code(self.SERVICE_REVENUE_CODE)
            discount_account = self.repo.get_account_by_code(self.DISCOUNT_ALLOWED_CODE)
            vat_account = self.repo.get_account_by_code(self.VAT_PAYABLE_CODE)

            if (
                ar_account is None
                or rev_account is None
                or discount_account is None
                or vat_account is None
            ):
                safe_print(
                    "CRITICAL_ERROR: [AccountingService] لا يمكن إيجاد كل الحسابات المحاسبية (للتعديل)."
                )
                return

            new_lines = []
            new_lines.append(
                schemas.JournalEntryLine(
                    account_id=ar_account._mongo_id or str(ar_account.id),
                    debit=invoice.total_amount,
                    credit=0.0,
                    description=f"قيمة فاتورة {invoice.invoice_number} (معدلة)",
                )
            )

            if invoice.discount_amount > 0:
                new_lines.append(
                    schemas.JournalEntryLine(
                        account_id=discount_account._mongo_id or str(discount_account.id),
                        debit=invoice.discount_amount,
                        credit=0.0,
                        description=f"خصم على فاتورة {invoice.invoice_number} (معدلة)",
                    )
                )

            new_lines.append(
                schemas.JournalEntryLine(
                    account_id=rev_account._mongo_id or str(rev_account.id),
                    debit=0.0,
                    credit=invoice.subtotal,
                    description=f"إثبات إيراد فاتورة {invoice.invoice_number} (معدلة)",
                )
            )

            if invoice.tax_amount > 0:
                new_lines.append(
                    schemas.JournalEntryLine(
                        account_id=vat_account._mongo_id or str(vat_account.id),
                        debit=0.0,
                        credit=invoice.tax_amount,
                        description=f"ضريبة ق.م. فاتورة {invoice.invoice_number} (معدلة)",
                    )
                )

            new_description = f"تعديل آلي لقيد الفاتورة {invoice.invoice_number}"

            success = self.repo.update_journal_entry_by_doc_id(
                doc_id=invoice._mongo_id or str(invoice.id),
                new_lines=new_lines,
                new_description=new_description,
            )

            if success:
                safe_print(
                    f"SUCCESS: [AccountingService] تم تعديل القيد المحاسبي للفاتورة {invoice.invoice_number}."
                )
            else:
                safe_print(
                    f"ERROR: [AccountingService] فشل في تحديث القيد المحاسبي للفاتورة {invoice.invoice_number}."
                )

        except Exception as e:
            safe_print(
                f"ERROR: [AccountingService] فشل تعديل القيد للفاتورة {invoice.invoice_number}: {e}"
            )

    def get_dashboard_kpis(self) -> dict:
        """
        (جديدة) تطلب أرقام الداشبورد الرئيسية من المخزن.
        """
        safe_print("INFO: [AccountingService] جاري طلب أرقام الداشبورد...")
        try:
            return self.repo.get_dashboard_kpis()
        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل جلب أرقام الداشبورد: {e}")
            return {
                "total_collected": 0,
                "total_outstanding": 0,
                "total_expenses": 0,
                "net_profit_cash": 0,
            }

    def get_dashboard_stats(self) -> dict:
        """
        مصدر موحد للبيانات لضمان تطابق الأرقام في الداشبورد 100%

        Returns:
            dict مع: total_sales, cash_collected, receivables, expenses, net_profit
        """
        safe_print("INFO: [AccountingService] جاري حساب إحصائيات الداشبورد الموحدة...")
        try:
            # جلب الملخص المالي من الحسابات
            summary = self.get_financial_summary()

            # جلب KPIs من المشاريع والدفعات
            kpis = self.repo.get_dashboard_kpis()

            # توحيد البيانات
            total_sales = summary.get("revenue", 0)  # إجمالي الإيرادات من الحسابات
            cash_collected = kpis.get("total_collected", 0)  # النقدية المحصلة من الدفعات
            receivables = kpis.get("total_outstanding", 0)  # المستحقات المتبقية
            expenses = kpis.get("total_expenses", 0)  # المصروفات
            net_profit = cash_collected - expenses  # صافي الربح النقدي

            return {
                "total_sales": total_sales,
                "cash_collected": cash_collected,
                "receivables": receivables,
                "expenses": expenses,
                "net_profit": net_profit,
            }
        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل حساب إحصائيات الداشبورد: {e}")
            return {
                "total_sales": 0,
                "cash_collected": 0,
                "receivables": 0,
                "expenses": 0,
                "net_profit": 0,
            }

    def get_recent_journal_entries(self, limit: int = 5) -> list[dict]:
        """
        جلب آخر القيود المحاسبية لعرضها في لوحة التحكم

        Args:
            limit: عدد القيود المطلوبة (افتراضي 5)

        Returns:
            قائمة بآخر القيود مع التاريخ والوصف والمبلغ
        """
        try:
            entries = self.repo.get_all_journal_entries()
            # ترتيب حسب التاريخ (الأحدث أولاً)
            sorted_entries = sorted(
                entries, key=lambda x: x.date if x.date else datetime.min, reverse=True
            )[:limit]

            results = []
            for entry in sorted_entries:
                # حساب إجمالي المبلغ من السطور
                total = sum(line.debit for line in entry.lines if line.debit)
                results.append(
                    {
                        "date": entry.date.strftime("%Y-%m-%d") if entry.date else "",
                        "description": entry.description or "",
                        "amount": total,
                    }
                )

            return results
        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل جلب آخر القيود: {e}")
            return []

    def get_recent_activity(self, limit: int = 8) -> list[dict]:
        """
        جلب آخر العمليات لعرضها في لوحة التحكم.

        الأولوية: قيود اليومية، ثم fallback إلى الدفعات + المصروفات إذا لم توجد قيود.
        """
        journal = self.get_recent_journal_entries(limit)
        if journal:
            return journal

        try:
            recent_items: list[tuple[datetime, dict]] = []

            if hasattr(self.repo, "get_all_payments"):
                payments = self.repo.get_all_payments()
                for p in payments:
                    if not getattr(p, "date", None):
                        continue
                    client_name = ""
                    try:
                        if getattr(p, "client_id", None) and hasattr(self.repo, "get_client_by_id"):
                            client = self.repo.get_client_by_id(str(p.client_id))
                            if client and getattr(client, "name", None):
                                client_name = f" - {client.name}"
                    except Exception:
                        client_name = ""

                    project_name = ""
                    try:
                        if getattr(p, "project_id", None) and hasattr(
                            self.repo, "get_project_by_number"
                        ):
                            project = self.repo.get_project_by_number(str(p.project_id))
                            if project and getattr(project, "name", None):
                                project_name = f"{project.name}"
                    except Exception:
                        project_name = str(getattr(p, "project_id", "")) or ""

                    method = str(getattr(p, "method", "") or "").strip()
                    method_part = f" ({method})" if method else ""
                    description = f"تحصيل{method_part}: {project_name}{client_name}".strip()

                    recent_items.append(
                        (
                            p.date,
                            {
                                "date": p.date.strftime("%Y-%m-%d"),
                                "description": description,
                                "amount": float(getattr(p, "amount", 0) or 0),
                            },
                        )
                    )

            if hasattr(self.repo, "get_all_expenses"):
                expenses = self.repo.get_all_expenses()
                for e in expenses:
                    if not getattr(e, "date", None):
                        continue
                    category = str(getattr(e, "category", "") or "").strip()
                    desc = str(getattr(e, "description", "") or "").strip()
                    desc_part = f" - {desc}" if desc else ""
                    description = f"مصروف: {category}{desc_part}".strip()

                    recent_items.append(
                        (
                            e.date,
                            {
                                "date": e.date.strftime("%Y-%m-%d"),
                                "description": description,
                                "amount": -float(getattr(e, "amount", 0) or 0),
                            },
                        )
                    )

            recent_items.sort(key=lambda x: x[0], reverse=True)
            return [item for _, item in recent_items[:limit]]
        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل جلب آخر العمليات: {e}")
            return []

    def create_account(self, account_data: dict) -> schemas.Account:
        """إضافة حساب جديد مع التحقق من parent_code"""
        safe_print(f"INFO: [AccountingService] استلام طلب إضافة حساب: {account_data.get('name')}")
        try:
            # التحقق من صحة parent_code إذا كان موجوداً
            if account_data.get("parent_code"):
                parent_account = self.repo.get_account_by_code(account_data["parent_code"])
                if not parent_account:
                    raise ValueError(f"الحساب الأب '{account_data['parent_code']}' غير موجود")

            # إنشاء كائن الحساب
            new_account_schema = schemas.Account(**account_data)
            created_account = self.repo.create_account(new_account_schema)

            # تحديث علامات is_group للحسابات
            if hasattr(self.repo, "update_is_group_flags"):
                self.repo.update_is_group_flags()

            # إرسال إشارة التحديث العامة
            app_signals.emit_data_changed("accounts")

            # 🔔 إشعار
            notify_operation(
                "created", "account", f"{created_account.code} - {created_account.name}"
            )

            safe_print(
                f"SUCCESS: [AccountingService] تم إنشاء الحساب '{created_account.name}' بالكود '{created_account.code}'"
            )
            return created_account
        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل إضافة الحساب: {e}")
            raise

    def update_account(self, account_id: str, new_data: dict) -> schemas.Account | None:
        """تعديل بيانات حساب مع التحقق من parent_code"""
        safe_print(f"INFO: [AccountingService] استلام طلب تعديل الحساب ID: {account_id}")
        try:
            # محاولة جلب الحساب بطرق مختلفة
            existing_account = self.repo.get_account_by_id(account_id)

            # إذا لم يتم العثور عليه بالـ ID، جرب بالـ code
            if not existing_account and isinstance(account_id, str):
                existing_account = self.repo.get_account_by_code(account_id)

            if not existing_account:
                safe_print(f"ERROR: [AccountingService] الحساب {account_id} غير موجود")
                raise ValueError(f"الحساب {account_id} غير موجود للتعديل.")

            # التحقق من صحة parent_code الجديد إذا كان موجوداً
            # وتحويله إلى parent_id للتوافق مع قاعدة البيانات
            if new_data.get("parent_code"):
                parent_account = self.repo.get_account_by_code(new_data["parent_code"])
                if not parent_account:
                    raise ValueError(f"الحساب الأب '{new_data['parent_code']}' غير موجود")

                # التأكد من عدم إنشاء حلقة مفرغة (الحساب لا يمكن أن يكون أباً لنفسه)
                if new_data["parent_code"] == existing_account.code:
                    raise ValueError("لا يمكن للحساب أن يكون أباً لنفسه")

                # ✅ تحويل parent_code إلى parent_id للتوافق مع الـ repository
                new_data["parent_id"] = new_data["parent_code"]
            else:
                # إذا لم يكن هناك parent_code، نضع parent_id = None
                new_data["parent_id"] = None
                new_data["parent_code"] = None

            # ⚠️ حماية الرصيد: لا نسمح بتعديل الرصيد يدوياً عند التحديث
            # الرصيد يُحسب فقط من القيود المحاسبية
            if "balance" in new_data:
                safe_print(
                    "WARNING: [AccountingService] Removing 'balance' from update data to preserve calculated balance"
                )
                new_data = {k: v for k, v in new_data.items() if k != "balance"}

            # حفظ الأرصدة الحالية قبل التحديث
            current_balance = existing_account.balance
            current_debit_total = existing_account.debit_total
            current_credit_total = existing_account.credit_total

            updated_account_schema = existing_account.model_copy(update=new_data)

            # استعادة الأرصدة المحسوبة
            updated_account_schema.balance = current_balance
            updated_account_schema.debit_total = current_debit_total
            updated_account_schema.credit_total = current_credit_total

            saved_account = self.repo.update_account(account_id, updated_account_schema)

            # تحديث علامات is_group للحسابات
            if hasattr(self.repo, "update_is_group_flags"):
                self.repo.update_is_group_flags()

            if saved_account is not None:
                # ⚡ إرسال إشارة التحديث الفوري
                app_signals.emit_data_changed("accounts")
                # 🔔 إشعار
                notify_operation(
                    "updated", "account", f"{saved_account.code} - {saved_account.name}"
                )
                safe_print(
                    f"SUCCESS: [AccountingService] تم تعديل الحساب {saved_account.name} بنجاح."
                )
            return saved_account
        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل تعديل الحساب: {e}")

            traceback.print_exc()
            raise

    def update_account_by_code(self, account_code: str, new_data: dict) -> schemas.Account | None:
        """تعديل بيانات حساب باستخدام الكود"""
        safe_print(f"INFO: [AccountingService] تعديل الحساب بالكود: {account_code}")
        try:
            existing_account = self.repo.get_account_by_code(account_code)
            if not existing_account:
                raise ValueError(f"الحساب بالكود '{account_code}' غير موجود للتعديل.")

            # الحصول على الـ id من الحساب الموجود
            account_id = existing_account._mongo_id or str(existing_account.id)
            safe_print(f"DEBUG: [AccountingService] Found account ID: {account_id}")

            # استدعاء دالة التحديث العادية
            return self.update_account(account_id, new_data)
        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل تعديل الحساب بالكود: {e}")
            raise

    def delete_account(self, account_id: str) -> bool:
        """حذف حساب نهائياً من قاعدة البيانات"""
        safe_print(f"INFO: [AccountingService] استلام طلب حذف الحساب ID: {account_id}")
        try:
            # جلب اسم الحساب قبل الحذف
            account = self.repo.get_account_by_id(account_id)
            if not account:
                account = self.repo.get_account_by_code(account_id)
            account_name = f"{account.code} - {account.name}" if account else f"حساب #{account_id}"

            result = self.repo.delete_account_permanently(account_id)
            if result:
                # ⚡ إرسال إشارة التحديث الفوري
                app_signals.emit_data_changed("accounts")
                # 🔔 إشعار
                notify_operation("deleted", "account", account_name)
            return result
        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل حذف الحساب: {e}")
            raise

    def post_transaction(
        self,
        date: datetime,
        description: str,
        amount: float,
        currency: str,
        exchange_rate: float,
        debit_account_code: str,
        credit_account_code: str,
        ref_type: str = "manual",
        ref_id: str | None = None,
    ) -> bool:
        """
        Smart Transaction Engine - The Brain of the Financial System

        Features:
        - Multi-currency support with automatic conversion to base currency (EGP)
        - Stores both original and converted amounts
        - Immediate balance updates (recursive for parent accounts)
        - Real-time GL posting

        Args:
            date: Transaction date
            description: Transaction description
            amount: Original amount in transaction currency
            currency: Currency code (EGP, USD, SAR, AED)
            exchange_rate: Exchange rate to EGP (1.0 for EGP)
            debit_account_code: Debit account code
            credit_account_code: Credit account code
            ref_type: Reference type (expense, payment, invoice, manual)
            ref_id: Reference document ID

        Returns:
            True if successful
        """
        safe_print(f"INFO: [AccountingService] Smart Transaction: {description}")
        safe_print(
            f"  Amount: {amount} {currency} @ {exchange_rate} = {amount * exchange_rate} EGP"
        )

        try:
            # 1. Convert to base currency (EGP)
            amount_egp = amount * exchange_rate

            # 2. Verify accounts exist
            debit_account = self.repo.get_account_by_code(debit_account_code)
            credit_account = self.repo.get_account_by_code(credit_account_code)

            if not debit_account:
                safe_print(f"ERROR: Debit account {debit_account_code} not found!")
                return False

            if not credit_account:
                safe_print(f"ERROR: Credit account {credit_account_code} not found!")
                return False

            # 3. Create journal entry with currency info
            journal_entry = schemas.JournalEntry(
                date=date,
                description=f"{description} ({amount:,.2f} {currency})",
                lines=[
                    schemas.JournalEntryLine(
                        account_id=debit_account.code,
                        account_code=debit_account.code,
                        account_name=debit_account.name,
                        debit=amount_egp,
                        credit=0.0,
                        description=f"مدين: {debit_account.name}",
                    ),
                    schemas.JournalEntryLine(
                        account_id=credit_account.code,
                        account_code=credit_account.code,
                        account_name=credit_account.name,
                        debit=0.0,
                        credit=amount_egp,
                        description=f"دائن: {credit_account.name}",
                    ),
                ],
                related_document_id=ref_id
                or f"{ref_type}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            )

            # 4. Save to database
            self.repo.create_journal_entry(journal_entry)

            # 5. Update balances immediately (with recursive parent update)
            self._update_account_balance_recursive(debit_account, amount_egp, is_debit=True)
            self._update_account_balance_recursive(credit_account, amount_egp, is_debit=False)

            safe_print("SUCCESS: Smart transaction posted successfully!")
            return True

        except Exception as e:
            safe_print(f"ERROR: Failed to post transaction: {e}")

            traceback.print_exc()
            return False

    def _update_parent_balance_recursive(self, parent_code: str):
        """
        تحديث رصيد الحساب الأب بناءً على مجموع أرصدة الأبناء
        """
        try:
            parent_account = self.repo.get_account_by_code(parent_code)
            if not parent_account:
                return

            # جلب جميع الحسابات الأبناء
            all_accounts = self.repo.get_all_accounts()
            children = [acc for acc in all_accounts if acc.parent_code == parent_code]

            # حساب مجموع أرصدة الأبناء
            total_balance = sum(acc.balance or 0 for acc in children)

            # تحديث رصيد الأب
            if abs((parent_account.balance or 0) - total_balance) > 0.01:
                account_id = parent_account._mongo_id or str(parent_account.id) or parent_code
                updated_account = parent_account.model_copy(update={"balance": total_balance})
                self.repo.update_account(account_id, updated_account)
                safe_print(
                    f"INFO: [AccountingService] تحديث رصيد الأب {parent_account.name}: {total_balance}"
                )

            # تحديث الأب الأعلى إن وجد
            if parent_account.parent_code:
                self._update_parent_balance_recursive(parent_account.parent_code)

        except Exception as e:
            safe_print(f"WARNING: [AccountingService] فشل تحديث رصيد الأب: {e}")

    def _update_account_balance_recursive(self, account, amount: float, is_debit: bool):
        """
        Update account balance and recursively update all parent accounts

        This ensures the tree view shows correct aggregated balances in real-time
        """
        try:
            # Update current account
            self._update_account_balance(account, amount, is_debit)

            # Recursively update parent accounts
            if account.parent_code:
                parent_account = self.repo.get_account_by_code(account.parent_code)
                if parent_account:
                    self._update_account_balance_recursive(parent_account, amount, is_debit)

        except Exception as e:
            safe_print(f"WARNING: Failed to update balance recursively: {e}")

    def post_journal_entry(
        self,
        date: datetime,
        description: str,
        ref_type: str,
        ref_id: str,
        debit_account_code: str,
        credit_account_code: str,
        amount: float,
    ) -> bool:
        """
        إنشاء قيد يومية كامل مع تحديث الأرصدة

        هذه الدالة الرئيسية لإنشاء القيود المحاسبية:
        1. إنشاء قيد اليومية (Journal Entry Header)
        2. إنشاء بنود القيد (Debit & Credit Lines)
        3. تحديث أرصدة الحسابات فوراً

        Args:
            date: تاريخ القيد
            description: وصف القيد
            ref_type: نوع المرجع (expense, payment, invoice)
            ref_id: معرف المستند المرتبط
            debit_account_code: كود الحساب المدين
            credit_account_code: كود الحساب الدائن
            amount: المبلغ

        Returns:
            True إذا نجحت العملية
        """
        safe_print(f"INFO: [AccountingService] post_journal_entry: {description} - {amount} جنيه")
        safe_print(
            f"INFO: [AccountingService] مدين: {debit_account_code} | دائن: {credit_account_code}"
        )

        try:
            # 1. التحقق من وجود الحسابات
            debit_account = self.repo.get_account_by_code(debit_account_code)
            credit_account = self.repo.get_account_by_code(credit_account_code)

            if not debit_account:
                safe_print(
                    f"ERROR: [AccountingService] الحساب المدين {debit_account_code} غير موجود!"
                )
                return False

            if not credit_account:
                safe_print(
                    f"ERROR: [AccountingService] الحساب الدائن {credit_account_code} غير موجود!"
                )
                return False

            safe_print(
                f"INFO: [AccountingService] الحسابات موجودة: {debit_account.name} (رصيد: {debit_account.balance}) | {credit_account.name} (رصيد: {credit_account.balance})"
            )

            # 2. إنشاء قيد اليومية
            journal_entry = schemas.JournalEntry(
                date=date,
                description=description,
                lines=[
                    schemas.JournalEntryLine(
                        account_id=debit_account.code,  # استخدام الكود للتتبع
                        account_code=debit_account.code,
                        account_name=debit_account.name,
                        debit=amount,
                        credit=0.0,
                        description=f"مدين: {debit_account.name}",
                    ),
                    schemas.JournalEntryLine(
                        account_id=credit_account.code,  # استخدام الكود للتتبع
                        account_code=credit_account.code,
                        account_name=credit_account.name,
                        debit=0.0,
                        credit=amount,
                        description=f"دائن: {credit_account.name}",
                    ),
                ],
                related_document_id=ref_id,
            )

            # 3. حفظ القيد في قاعدة البيانات
            created_entry = self.repo.create_journal_entry(journal_entry)
            safe_print(
                f"SUCCESS: [AccountingService] تم حفظ القيد في قاعدة البيانات (ID: {getattr(created_entry, 'id', 'N/A')})"
            )

            # 4. تحديث أرصدة الحسابات فوراً
            safe_print(f"DEBUG: [AccountingService] تحديث رصيد الحساب المدين: {debit_account.name}")
            self._update_account_balance(debit_account, amount, is_debit=True)

            safe_print(
                f"DEBUG: [AccountingService] تحديث رصيد الحساب الدائن: {credit_account.name}"
            )
            self._update_account_balance(credit_account, amount, is_debit=False)

            # 5. إبطال الـ cache لإعادة حساب الأرصدة
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0

            # ⚡ التحقق من تحديث الأرصدة
            updated_debit = self.repo.get_account_by_code(debit_account_code)
            updated_credit = self.repo.get_account_by_code(credit_account_code)
            safe_print("SUCCESS: [AccountingService] ✅ الأرصدة بعد التحديث:")
            safe_print(
                f"  - {debit_account.name}: {updated_debit.balance if updated_debit else 'N/A'}"
            )
            safe_print(
                f"  - {credit_account.name}: {updated_credit.balance if updated_credit else 'N/A'}"
            )

            # ⚡ إرسال إشارات التحديث الفوري (Real-time Sync)
            try:
                entry_id = str(
                    getattr(created_entry, "id", "")
                    or getattr(created_entry, "_mongo_id", "")
                    or ref_id
                )
                app_signals.emit_journal_entry_created(entry_id)
                app_signals.emit_data_changed("accounting")
                safe_print("INFO: [AccountingService] ✅ تم إرسال إشارات التحديث الفوري")
            except Exception as sig_err:
                safe_print(f"WARNING: [AccountingService] فشل إرسال الإشارات: {sig_err}")

            safe_print("SUCCESS: [AccountingService] ✅ تم إنشاء القيد وتحديث الأرصدة بنجاح")
            return True

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل إنشاء القيد: {e}")

            traceback.print_exc()
            return False

    def create_transaction(
        self,
        date: datetime,
        description: str,
        ref_type: str,
        ref_id: str,
        debit_account_code: str,
        credit_account_code: str,
        amount: float,
    ) -> bool:
        """
        إنشاء معاملة محاسبية كاملة (قيد يومية + تحديث الأرصدة)

        Args:
            date: تاريخ المعاملة
            description: وصف المعاملة
            ref_type: نوع المرجع (expense, payment, invoice)
            ref_id: معرف المرجع
            debit_account_code: كود الحساب المدين
            credit_account_code: كود الحساب الدائن
            amount: المبلغ

        Returns:
            True إذا نجحت العملية
        """
        safe_print(f"INFO: [AccountingService] إنشاء معاملة: {description} - {amount} جنيه")

        try:
            # 1. التحقق من وجود الحسابات
            debit_account = self.repo.get_account_by_code(debit_account_code)
            credit_account = self.repo.get_account_by_code(credit_account_code)

            if not debit_account:
                raise ValueError(f"الحساب المدين {debit_account_code} غير موجود")

            if not credit_account:
                raise ValueError(f"الحساب الدائن {credit_account_code} غير موجود")

            # 2. إنشاء قيد اليومية
            journal_entry = schemas.JournalEntry(
                date=date,
                description=description,
                lines=[
                    schemas.JournalEntryLine(
                        account_id=debit_account._mongo_id or str(debit_account.id),
                        debit=amount,
                        credit=0.0,
                        description=f"مدين - {description}",
                    ),
                    schemas.JournalEntryLine(
                        account_id=credit_account._mongo_id or str(credit_account.id),
                        debit=0.0,
                        credit=amount,
                        description=f"دائن - {description}",
                    ),
                ],
                related_document_id=ref_id,
            )

            # 3. حفظ القيد
            created_entry = self.repo.create_journal_entry(journal_entry)

            # 4. تحديث أرصدة الحسابات
            self._update_account_balance(debit_account, amount, is_debit=True)
            self._update_account_balance(credit_account, amount, is_debit=False)

            safe_print(
                f"SUCCESS: [AccountingService] تم إنشاء المعاملة بنجاح - القيد #{created_entry.id if hasattr(created_entry, 'id') else 'N/A'}"
            )
            return True

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل إنشاء المعاملة: {e}")

            traceback.print_exc()
            return False

    def get_account_ledger(
        self, account_id: str, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        """
        جلب كشف حساب (تاريخ المعاملات) لحساب معين

        Args:
            account_id: معرف الحساب (ID أو Code)
            start_date: تاريخ البداية
            end_date: تاريخ النهاية

        Returns:
            قائمة بالمعاملات مع الرصيد الجاري
        """
        safe_print(
            f"INFO: [AccountingService] جلب كشف حساب {account_id} من {start_date} إلى {end_date}"
        )

        try:
            # جلب الحساب
            account = self.repo.get_account_by_id(account_id)
            if not account:
                account = self.repo.get_account_by_code(account_id)

            if not account:
                safe_print(f"ERROR: الحساب {account_id} غير موجود")
                return []

            # جلب جميع قيود اليومية في الفترة المحددة
            all_entries = self.repo.get_all_journal_entries()

            ledger_transactions = []

            for entry in all_entries:
                # التحقق من التاريخ
                entry_date = entry.date
                if not start_date <= entry_date <= end_date:
                    continue

                # البحث عن الأسطر المتعلقة بهذا الحساب
                for line in entry.lines:
                    # مقارنة بالـ ID أو الكود
                    line_account_id = str(line.account_id)
                    account_match = (
                        line_account_id == str(account._mongo_id)
                        or line_account_id == str(account.id)
                        or line_account_id == account.code
                    )

                    if account_match:
                        ledger_transactions.append(
                            {
                                "date": entry_date,
                                "description": line.description or entry.description,
                                "reference": entry.related_document_id or "-",
                                "debit": line.debit,
                                "credit": line.credit,
                            }
                        )

            # ترتيب حسب التاريخ
            ledger_transactions.sort(key=lambda x: str(x.get("date", "")))

            safe_print(f"INFO: تم جلب {len(ledger_transactions)} معاملة للحساب {account.name}")
            return ledger_transactions

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل جلب كشف الحساب: {e}")

            traceback.print_exc()
            return []

    def get_account_ledger_report(
        self, account_id: str, start_date: datetime, end_date: datetime
    ) -> dict:
        """
        جلب كشف حساب لحساب معين مع الرصيد الافتتاحي والرصيد الجاري.

        هذا التقرير يعتمد على:
        - قيود اليومية (journal_entries) إن وجدت
        - الدفعات (payments) للحسابات النقدية
        - المصروفات (expenses) للحسابات النقدية/المصروفات
        """

        def _account_type_str(acc: schemas.Account) -> str:
            acc_type = getattr(acc, "type", None)
            return acc_type.value if hasattr(acc_type, "value") else str(acc_type or "")

        def _is_debit_increase_type(type_str: str) -> bool:
            return type_str in {
                "ASSET",
                "CASH",
                "EXPENSE",
                "أصول",
                "أصول نقدية",
                "مصروفات",
                "cash",
            }

        def _delta(type_str: str, debit: float, credit: float) -> float:
            if _is_debit_increase_type(type_str):
                return (debit or 0) - (credit or 0)
            return (credit or 0) - (debit or 0)

        safe_print(
            f"INFO: [AccountingService] جلب تقرير كشف حساب {account_id} من {start_date} إلى {end_date}"
        )

        try:
            account = self.repo.get_account_by_id(account_id)
            if not account:
                account = self.repo.get_account_by_code(account_id)

            if not account:
                safe_print(f"ERROR: الحساب {account_id} غير موجود")
                return {
                    "account": None,
                    "opening_balance": 0.0,
                    "ending_balance": 0.0,
                    "total_debit": 0.0,
                    "total_credit": 0.0,
                    "net_movement": 0.0,
                    "movements": [],
                }

            type_str = _account_type_str(account)
            identifiers = {
                str(getattr(account, "_mongo_id", "") or ""),
                str(getattr(account, "id", "") or ""),
                str(getattr(account, "code", "") or ""),
            }
            identifiers = {x for x in identifiers if x}

            start_iso = start_date.isoformat()
            end_iso = end_date.isoformat()

            opening_balance = 0.0

            opening_payments = float(self.repo.sum_payments_before(account.code, start_iso) or 0.0)
            opening_balance += _delta(type_str, opening_payments, 0.0)

            opening_exp_paid = float(
                self.repo.sum_expenses_paid_before(account.code, start_iso) or 0.0
            )
            opening_balance += _delta(type_str, 0.0, opening_exp_paid)

            opening_exp_charged = float(
                self.repo.sum_expenses_charged_before(account.code, start_iso) or 0.0
            )
            opening_balance += _delta(type_str, opening_exp_charged, 0.0)

            try:
                entries_before = self.repo.get_journal_entries_before(start_iso) or []
            except Exception:
                entries_before = []

            for entry in entries_before:
                entry_date = getattr(entry, "date", None)
                if not entry_date:
                    continue
                for line in getattr(entry, "lines", []) or []:
                    line_ids = {
                        str(getattr(line, "account_code", "") or ""),
                        str(getattr(line, "account_id", "") or ""),
                    }
                    if not (identifiers & {x for x in line_ids if x}):
                        continue
                    opening_balance += _delta(
                        type_str,
                        float(getattr(line, "debit", 0) or 0),
                        float(getattr(line, "credit", 0) or 0),
                    )

            raw_movements: list[dict] = []

            try:
                entries_in_range = self.repo.get_journal_entries_between(start_iso, end_iso) or []
            except Exception:
                entries_in_range = []

            for entry in entries_in_range:
                entry_date = getattr(entry, "date", None)
                if not entry_date:
                    continue

                for line in getattr(entry, "lines", []) or []:
                    line_ids = {
                        str(getattr(line, "account_code", "") or ""),
                        str(getattr(line, "account_id", "") or ""),
                    }
                    if not (identifiers & {x for x in line_ids if x}):
                        continue

                    raw_movements.append(
                        {
                            "date": entry_date,
                            "description": getattr(line, "description", None)
                            or getattr(entry, "description", ""),
                            "reference": getattr(entry, "related_document_id", None) or "",
                            "debit": float(getattr(line, "debit", 0) or 0),
                            "credit": float(getattr(line, "credit", 0) or 0),
                        }
                    )

            for p in self.repo.get_payments_by_account(account.code, start_iso, end_iso) or []:
                raw_movements.append(
                    {
                        "date": getattr(p, "date", None),
                        "description": f"تحصيل ({getattr(p, 'method', '') or 'تحصيل'}): {getattr(p, 'client_id', '') or ''}",
                        "reference": getattr(p, "_mongo_id", None)
                        or str(getattr(p, "id", "") or ""),
                        "debit": float(getattr(p, "amount", 0) or 0),
                        "credit": 0.0,
                    }
                )

            for exp in (
                self.repo.get_expenses_paid_from_account(account.code, start_iso, end_iso) or []
            ):
                exp_date = getattr(exp, "date", None)
                if not exp_date:
                    continue
                desc_parts = [f"مصروف: {getattr(exp, 'category', '') or ''}"]
                if exp.description:
                    desc_parts.append(str(exp.description))
                raw_movements.append(
                    {
                        "date": exp_date,
                        "description": " - ".join([p for p in desc_parts if p]),
                        "reference": getattr(exp, "_mongo_id", None)
                        or str(getattr(exp, "id", "") or ""),
                        "debit": 0.0,
                        "credit": float(getattr(exp, "amount", 0) or 0),
                    }
                )

            for exp in (
                self.repo.get_expenses_charged_to_account(account.code, start_iso, end_iso) or []
            ):
                exp_date = getattr(exp, "date", None)
                if not exp_date:
                    continue
                desc_parts = [f"مصروف: {getattr(exp, 'category', '') or ''}"]
                if exp.description:
                    desc_parts.append(str(exp.description))
                raw_movements.append(
                    {
                        "date": exp_date,
                        "description": " - ".join([p for p in desc_parts if p]),
                        "reference": getattr(exp, "_mongo_id", None)
                        or str(getattr(exp, "id", "") or ""),
                        "debit": float(getattr(exp, "amount", 0) or 0),
                        "credit": 0.0,
                    }
                )

            raw_movements = [m for m in raw_movements if m.get("date")]
            raw_movements.sort(key=lambda x: x["date"])

            movements: list[dict] = []
            running = opening_balance
            total_debit = 0.0
            total_credit = 0.0

            for m in raw_movements:
                debit = float(m.get("debit", 0) or 0)
                credit = float(m.get("credit", 0) or 0)
                running += _delta(type_str, debit, credit)
                total_debit += debit
                total_credit += credit

                movements.append(
                    {
                        "date": m["date"],
                        "description": m.get("description", ""),
                        "reference": m.get("reference", "") or "",
                        "debit": debit,
                        "credit": credit,
                        "balance": running,
                    }
                )

            net_movement = sum(
                _delta(type_str, m.get("debit", 0), m.get("credit", 0)) for m in movements
            )
            ending_balance = movements[-1]["balance"] if movements else opening_balance

            return {
                "account": account,
                "opening_balance": opening_balance,
                "ending_balance": ending_balance,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "net_movement": net_movement,
                "movements": movements,
            }

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل جلب تقرير كشف الحساب: {e}")
            traceback.print_exc()
            return {
                "account": None,
                "opening_balance": 0.0,
                "ending_balance": 0.0,
                "total_debit": 0.0,
                "total_credit": 0.0,
                "net_movement": 0.0,
                "movements": [],
            }

    def seed_test_transactions(self) -> dict:
        """
        إنشاء معاملات اختبارية لتجربة كشف الحساب
        """
        safe_print("=" * 60)
        safe_print("INFO: [AccountingService] بدء إنشاء معاملات اختبارية...")
        safe_print("=" * 60)

        created_count = 0
        errors = []

        try:
            # التحقق من وجود الحسابات المطلوبة
            accounts_needed = {
                "1111": "الخزنة الرئيسية",
                "1121": "البنك الأهلي",
                "1140": "العملاء",
                "4100": "إيرادات الخدمات",
                "5110": "الرواتب والأجور",
                "1131": "فودافون كاش",
            }

            for code, name in accounts_needed.items():
                account = self.repo.get_account_by_code(code)
                if not account:
                    safe_print(f"WARNING: الحساب {code} - {name} غير موجود")

            # معاملة 1: إيداع نقدي في البنك (10000 جنيه)
            try:
                bank_account = self.repo.get_account_by_code("1121")
                cash_account = self.repo.get_account_by_code("1111")

                if bank_account and cash_account:
                    entry1 = schemas.JournalEntry(
                        date=datetime.now() - timedelta(days=30),
                        description="إيداع نقدي في البنك الأهلي",
                        lines=[
                            schemas.JournalEntryLine(
                                account_id=bank_account._mongo_id or str(bank_account.id),
                                debit=10000.0,
                                credit=0.0,
                                description="إيداع في البنك الأهلي",
                            ),
                            schemas.JournalEntryLine(
                                account_id=cash_account._mongo_id or str(cash_account.id),
                                debit=0.0,
                                credit=10000.0,
                                description="سحب من الخزينة الرئيسية",
                            ),
                        ],
                        related_document_id="DEP-001",
                    )
                    self.repo.create_journal_entry(entry1)
                    safe_print("✅ تم إنشاء معاملة: إيداع في البنك (10000 جنيه)")
                    created_count += 1
            except Exception as e:
                error_msg = f"فشل إنشاء معاملة الإيداع: {e}"
                safe_print(f"❌ {error_msg}")
                errors.append(error_msg)

            # معاملة 2: بيع خدمة (1500 جنيه)
            try:
                receivable_account = self.repo.get_account_by_code("1140")
                revenue_account = self.repo.get_account_by_code("4100")

                if receivable_account and revenue_account:
                    entry2 = schemas.JournalEntry(
                        date=datetime.now() - timedelta(days=20),
                        description="بيع خدمة تطوير موقع",
                        lines=[
                            schemas.JournalEntryLine(
                                account_id=receivable_account._mongo_id
                                or str(receivable_account.id),
                                debit=1500.0,
                                credit=0.0,
                                description="مستحق من العميل - شركة ABC",
                            ),
                            schemas.JournalEntryLine(
                                account_id=revenue_account._mongo_id or str(revenue_account.id),
                                debit=0.0,
                                credit=1500.0,
                                description="إيراد خدمة تطوير موقع",
                            ),
                        ],
                        related_document_id="INV-001",
                    )
                    self.repo.create_journal_entry(entry2)
                    safe_print("✅ تم إنشاء معاملة: بيع خدمة (1500 جنيه)")
                    created_count += 1
            except Exception as e:
                error_msg = f"فشل إنشاء معاملة بيع الخدمة: {e}"
                safe_print(f"❌ {error_msg}")
                errors.append(error_msg)

            # معاملة 3: دفع راتب (2000 جنيه)
            try:
                salary_account = self.repo.get_account_by_code("5110")
                vodafone_account = self.repo.get_account_by_code("1131")

                if salary_account and vodafone_account:
                    entry3 = schemas.JournalEntry(
                        date=datetime.now() - timedelta(days=10),
                        description="دفع راتب شهر نوفمبر",
                        lines=[
                            schemas.JournalEntryLine(
                                account_id=salary_account._mongo_id or str(salary_account.id),
                                debit=2000.0,
                                credit=0.0,
                                description="راتب الموظف - أحمد محمد",
                            ),
                            schemas.JournalEntryLine(
                                account_id=vodafone_account._mongo_id or str(vodafone_account.id),
                                debit=0.0,
                                credit=2000.0,
                                description="دفع عبر فودافون كاش",
                            ),
                        ],
                        related_document_id="SAL-001",
                    )
                    self.repo.create_journal_entry(entry3)
                    safe_print("✅ تم إنشاء معاملة: دفع راتب (2000 جنيه)")
                    created_count += 1
            except Exception as e:
                error_msg = f"فشل إنشاء معاملة دفع الراتب: {e}"
                safe_print(f"❌ {error_msg}")
                errors.append(error_msg)

            # معاملة 4: تحصيل من العميل (1500 جنيه)
            try:
                receivable_account = self.repo.get_account_by_code("1140")
                cash_account = self.repo.get_account_by_code("1111")

                if receivable_account and cash_account:
                    entry4 = schemas.JournalEntry(
                        date=datetime.now() - timedelta(days=5),
                        description="تحصيل من العميل - شركة ABC",
                        lines=[
                            schemas.JournalEntryLine(
                                account_id=cash_account._mongo_id or str(cash_account.id),
                                debit=1500.0,
                                credit=0.0,
                                description="تحصيل نقدي",
                            ),
                            schemas.JournalEntryLine(
                                account_id=receivable_account._mongo_id
                                or str(receivable_account.id),
                                debit=0.0,
                                credit=1500.0,
                                description="سداد من العميل - شركة ABC",
                            ),
                        ],
                        related_document_id="REC-001",
                    )
                    self.repo.create_journal_entry(entry4)
                    safe_print("✅ تم إنشاء معاملة: تحصيل من العميل (1500 جنيه)")
                    created_count += 1
            except Exception as e:
                error_msg = f"فشل إنشاء معاملة التحصيل: {e}"
                safe_print(f"❌ {error_msg}")
                errors.append(error_msg)

            safe_print("\n" + "=" * 60)
            safe_print(f"✅ تم إنشاء {created_count} معاملة اختبارية")
            if errors:
                safe_print(f"❌ فشل إنشاء {len(errors)} معاملة")
            safe_print("=" * 60)

            return {
                "success": True,
                "created": created_count,
                "errors": errors,
                "message": f"تم إنشاء {created_count} معاملة اختبارية",
            }

        except Exception as e:
            error_msg = f"فشل إنشاء المعاملات الاختبارية: {e}"
            safe_print(f"ERROR: [AccountingService] {error_msg}")

            traceback.print_exc()
            return {
                "success": False,
                "created": created_count,
                "errors": errors + [error_msg],
                "message": error_msg,
            }

    def reset_and_seed_agency_accounts(self) -> dict:
        """
        RESET & SEED: Wipe existing accounts and create fresh Digital Marketing Agency structure

        WARNING: This will delete ALL existing accounts and journal entries!
        Use only for initial setup or complete reset.
        """
        safe_print("=" * 60)
        safe_print("⚠️  WARNING: RESETTING ALL ACCOUNTING DATA!")
        safe_print("=" * 60)

        try:
            # 1. Delete all existing accounts (if method exists)
            if hasattr(self.repo, "delete_all_accounts"):
                self.repo.delete_all_accounts()
                safe_print("✅ Deleted all existing accounts")

            # 2. Seed new accounts
            result = self.seed_default_accounts()

            safe_print("=" * 60)
            safe_print("✅ RESET COMPLETE - Fresh Agency Accounts Created!")
            safe_print("=" * 60)

            return result

        except Exception as e:
            safe_print(f"ERROR: Failed to reset accounts: {e}")

            traceback.print_exc()
            return {"success": False, "created": 0, "errors": [str(e)], "message": "Reset failed"}

    def seed_default_accounts(self) -> dict:
        """
        🏢 إنشاء شجرة حسابات Enterprise Level لـ SkyWave

        ✅ نظام 6 أرقام (Scalability) - يدعم 999 حساب فرعي تحت كل بند
        ✅ فصل COGS (5xxxxx) عن OPEX (6xxxxx) لتحليل الربحية
        ✅ دفعات مقدمة من العملاء (Unearned Revenue)
        """
        safe_print("=" * 60)
        safe_print("INFO: [AccountingService] 🏢 إنشاء شجرة حسابات Enterprise Level...")
        safe_print("=" * 60)

        # ==================== شجرة الحسابات الاحترافية (6 أرقام) ====================
        ENTERPRISE_ACCOUNTS: list[dict[str, Any]] = [  # pylint: disable=invalid-name
            # ==================== 1. الأصول (100000) ====================
            {
                "code": "100000",
                "name": "الأصول",
                "type": schemas.AccountType.ASSET,
                "parent": None,
                "is_group": True,
            },
            # الأصول المتداولة (110000)
            {
                "code": "110000",
                "name": "الأصول المتداولة",
                "type": schemas.AccountType.ASSET,
                "parent": "100000",
                "is_group": True,
            },
            # النقدية وما في حكمها (111000)
            {
                "code": "111000",
                "name": "النقدية وما في حكمها",
                "type": schemas.AccountType.CASH,
                "parent": "110000",
                "is_group": True,
            },
            # الخزائن النقدية (111100)
            {
                "code": "111100",
                "name": "الخزائن النقدية",
                "type": schemas.AccountType.CASH,
                "parent": "111000",
                "is_group": True,
            },
            {
                "code": "111101",
                "name": "الخزنة الرئيسية (المقر)",
                "type": schemas.AccountType.CASH,
                "parent": "111100",
                "is_group": False,
            },
            {
                "code": "111102",
                "name": "عهد نقدية موظفين",
                "type": schemas.AccountType.CASH,
                "parent": "111100",
                "is_group": False,
            },
            # الحسابات البنكية (111200)
            {
                "code": "111200",
                "name": "الحسابات البنكية",
                "type": schemas.AccountType.CASH,
                "parent": "111000",
                "is_group": True,
            },
            {
                "code": "111201",
                "name": "بنك مصر - جاري (..86626)",
                "type": schemas.AccountType.CASH,
                "parent": "111200",
                "is_group": False,
            },
            # المحافظ الإلكترونية (111300)
            {
                "code": "111300",
                "name": "المحافظ الإلكترونية وبوابات الدفع",
                "type": schemas.AccountType.CASH,
                "parent": "111000",
                "is_group": True,
            },
            {
                "code": "111301",
                "name": "فودافون كاش (الرئيسي) ..321",
                "type": schemas.AccountType.CASH,
                "parent": "111300",
                "is_group": False,
            },
            {
                "code": "111302",
                "name": "فودافون كاش (الفرعي) ..200",
                "type": schemas.AccountType.CASH,
                "parent": "111300",
                "is_group": False,
            },
            {
                "code": "111303",
                "name": "مدفوعات تحت التسوية (InstaPay)",
                "type": schemas.AccountType.CASH,
                "parent": "111300",
                "is_group": False,
            },
            # العملاء وأوراق القبض (112000)
            {
                "code": "112000",
                "name": "العملاء وأوراق القبض",
                "type": schemas.AccountType.ASSET,
                "parent": "110000",
                "is_group": True,
            },
            {
                "code": "112100",
                "name": "عملاء تجاريين (شركات)",
                "type": schemas.AccountType.ASSET,
                "parent": "112000",
                "is_group": False,
            },
            {
                "code": "112200",
                "name": "عملاء أفراد",
                "type": schemas.AccountType.ASSET,
                "parent": "112000",
                "is_group": False,
            },
            # أرصدة مدينة أخرى (113000)
            {
                "code": "113000",
                "name": "أرصدة مدينة أخرى",
                "type": schemas.AccountType.ASSET,
                "parent": "110000",
                "is_group": True,
            },
            {
                "code": "113100",
                "name": "مصروفات مدفوعة مقدماً",
                "type": schemas.AccountType.ASSET,
                "parent": "113000",
                "is_group": False,
            },
            {
                "code": "113200",
                "name": "سلف العاملين",
                "type": schemas.AccountType.ASSET,
                "parent": "113000",
                "is_group": False,
            },
            # الأصول غير المتداولة (120000)
            {
                "code": "120000",
                "name": "الأصول غير المتداولة",
                "type": schemas.AccountType.ASSET,
                "parent": "100000",
                "is_group": True,
            },
            {
                "code": "121000",
                "name": "الأصول الثابتة الملموسة",
                "type": schemas.AccountType.ASSET,
                "parent": "120000",
                "is_group": True,
            },
            {
                "code": "121100",
                "name": "أجهزة حاسب آلي وسيرفرات",
                "type": schemas.AccountType.ASSET,
                "parent": "121000",
                "is_group": False,
            },
            {
                "code": "121200",
                "name": "أثاث وتجهيزات مكتبية",
                "type": schemas.AccountType.ASSET,
                "parent": "121000",
                "is_group": False,
            },
            # ==================== 2. الخصوم (200000) ====================
            {
                "code": "200000",
                "name": "الخصوم",
                "type": schemas.AccountType.LIABILITY,
                "parent": None,
                "is_group": True,
            },
            # الخصوم المتداولة (210000)
            {
                "code": "210000",
                "name": "الخصوم المتداولة",
                "type": schemas.AccountType.LIABILITY,
                "parent": "200000",
                "is_group": True,
            },
            # الموردين (211000)
            {
                "code": "211000",
                "name": "الموردين",
                "type": schemas.AccountType.LIABILITY,
                "parent": "210000",
                "is_group": True,
            },
            {
                "code": "211100",
                "name": "موردين تشغيل (خدمات تقنية)",
                "type": schemas.AccountType.LIABILITY,
                "parent": "211000",
                "is_group": False,
            },
            {
                "code": "211200",
                "name": "مستحقات مستقلين (Freelancers)",
                "type": schemas.AccountType.LIABILITY,
                "parent": "211000",
                "is_group": False,
            },
            # أرصدة دائنة أخرى (212000) - ⚡ مهم جداً
            {
                "code": "212000",
                "name": "أرصدة دائنة أخرى",
                "type": schemas.AccountType.LIABILITY,
                "parent": "210000",
                "is_group": True,
            },
            {
                "code": "212100",
                "name": "دفعات مقدمة من العملاء (هام)",
                "type": schemas.AccountType.LIABILITY,
                "parent": "212000",
                "is_group": False,
            },  # Unearned Revenue
            {
                "code": "212200",
                "name": "ضريبة القيمة المضافة",
                "type": schemas.AccountType.LIABILITY,
                "parent": "212000",
                "is_group": False,
            },
            # ==================== 3. حقوق الملكية (300000) ====================
            {
                "code": "300000",
                "name": "حقوق الملكية",
                "type": schemas.AccountType.EQUITY,
                "parent": None,
                "is_group": True,
            },
            {
                "code": "310000",
                "name": "رأس المال",
                "type": schemas.AccountType.EQUITY,
                "parent": "300000",
                "is_group": False,
            },
            {
                "code": "320000",
                "name": "جاري المالك (مسحوبات)",
                "type": schemas.AccountType.EQUITY,
                "parent": "300000",
                "is_group": False,
            },
            {
                "code": "330000",
                "name": "الأرباح المرحلة",
                "type": schemas.AccountType.EQUITY,
                "parent": "300000",
                "is_group": False,
            },
            # ==================== 4. الإيرادات (400000) ====================
            {
                "code": "400000",
                "name": "الإيرادات",
                "type": schemas.AccountType.REVENUE,
                "parent": None,
                "is_group": True,
            },
            {
                "code": "410000",
                "name": "إيرادات التشغيل الرئيسية",
                "type": schemas.AccountType.REVENUE,
                "parent": "400000",
                "is_group": True,
            },
            {
                "code": "410100",
                "name": "إيرادات خدمات التسويق الرقمي",
                "type": schemas.AccountType.REVENUE,
                "parent": "410000",
                "is_group": False,
            },
            {
                "code": "410200",
                "name": "إيرادات تطوير المواقع والتطبيقات",
                "type": schemas.AccountType.REVENUE,
                "parent": "410000",
                "is_group": False,
            },
            {
                "code": "410300",
                "name": "إيرادات الباقات والعقود السنوية",
                "type": schemas.AccountType.REVENUE,
                "parent": "410000",
                "is_group": False,
            },
            # ==================== 5. تكاليف الإيرادات - COGS (500000) ====================
            # ⚡ هذا القسم يخبرك كم كلفك المشروع تقنياً (Direct Costs)
            {
                "code": "500000",
                "name": "تكاليف الإيرادات (المباشرة)",
                "type": schemas.AccountType.EXPENSE,
                "parent": None,
                "is_group": True,
            },
            {
                "code": "510000",
                "name": "تكاليف الحملات والتشغيل",
                "type": schemas.AccountType.EXPENSE,
                "parent": "500000",
                "is_group": True,
            },
            {
                "code": "510001",
                "name": "ميزانية إعلانات (Ads Spend)",
                "type": schemas.AccountType.EXPENSE,
                "parent": "510000",
                "is_group": False,
            },
            {
                "code": "510002",
                "name": "تكلفة استضافة وسيرفرات",
                "type": schemas.AccountType.EXPENSE,
                "parent": "510000",
                "is_group": False,
            },
            {
                "code": "510003",
                "name": "أجور مستقلين (Outsourcing)",
                "type": schemas.AccountType.EXPENSE,
                "parent": "510000",
                "is_group": False,
            },
            # ==================== 6. المصروفات التشغيلية - OPEX (600000) ====================
            # ⚡ هذا القسم يخبرك كم كلفتك إدارة الشركة (Indirect Costs)
            {
                "code": "600000",
                "name": "المصروفات التشغيلية والإدارية",
                "type": schemas.AccountType.EXPENSE,
                "parent": None,
                "is_group": True,
            },
            # المصروفات التسويقية (610000)
            {
                "code": "610000",
                "name": "المصروفات التسويقية",
                "type": schemas.AccountType.EXPENSE,
                "parent": "600000",
                "is_group": True,
            },
            {
                "code": "610001",
                "name": "دعاية وإعلان للشركة",
                "type": schemas.AccountType.EXPENSE,
                "parent": "610000",
                "is_group": False,
            },
            {
                "code": "610002",
                "name": "عمولات البيع",
                "type": schemas.AccountType.EXPENSE,
                "parent": "610000",
                "is_group": False,
            },
            # المصروفات الإدارية والعمومية (620000)
            {
                "code": "620000",
                "name": "المصروفات الإدارية والعمومية",
                "type": schemas.AccountType.EXPENSE,
                "parent": "600000",
                "is_group": True,
            },
            {
                "code": "620001",
                "name": "رواتب الموظفين",
                "type": schemas.AccountType.EXPENSE,
                "parent": "620000",
                "is_group": False,
            },
            {
                "code": "620002",
                "name": "إيجار ومرافق",
                "type": schemas.AccountType.EXPENSE,
                "parent": "620000",
                "is_group": False,
            },
            {
                "code": "620003",
                "name": "إنترنت واتصالات",
                "type": schemas.AccountType.EXPENSE,
                "parent": "620000",
                "is_group": False,
            },
            {
                "code": "620004",
                "name": "اشتراكات برمجيات (SaaS)",
                "type": schemas.AccountType.EXPENSE,
                "parent": "620000",
                "is_group": False,
            },
            # المصروفات المالية (630000)
            {
                "code": "630000",
                "name": "المصروفات المالية",
                "type": schemas.AccountType.EXPENSE,
                "parent": "600000",
                "is_group": True,
            },
            {
                "code": "630001",
                "name": "رسوم بنكية وعمولات سحب",
                "type": schemas.AccountType.EXPENSE,
                "parent": "630000",
                "is_group": False,
            },
        ]

        DEFAULT_ACCOUNTS: list[dict[str, Any]] = ENTERPRISE_ACCOUNTS  # pylint: disable=invalid-name

        created_count = 0
        skipped_count = 0
        errors = []

        try:
            # جلب الحسابات الموجودة للتحقق من التكرار
            existing_accounts = self.repo.get_all_accounts()
            existing_codes = {acc.code for acc in existing_accounts}

            safe_print(f"INFO: عدد الحسابات الموجودة حالياً: {len(existing_codes)}")

            # إنشاء الحسابات بالترتيب (الآباء أولاً)
            for account_template in DEFAULT_ACCOUNTS:
                code = account_template["code"]

                # التحقق من عدم التكرار
                if code in existing_codes:
                    safe_print(f"⏭️  تخطي: {code} - {account_template['name']} (موجود مسبقاً)")
                    skipped_count += 1
                    continue

                try:
                    # إنشاء بيانات الحساب
                    account_data = {
                        "code": code,
                        "name": account_template["name"],
                        "type": account_template["type"],
                        "parent_code": account_template["parent"],
                        "is_group": account_template["is_group"],
                        "balance": 0.0,
                        "currency": "EGP",
                        "status": schemas.AccountStatus.ACTIVE,
                    }

                    # إنشاء الحساب
                    new_account = schemas.Account(**account_data)
                    self.repo.create_account(new_account)

                    # إضافة إلى قائمة الأكواد الموجودة
                    existing_codes.add(code)

                    group_indicator = "📁" if account_template["is_group"] else "📄"
                    parent_info = (
                        f" (تحت {account_template['parent']})" if account_template["parent"] else ""
                    )
                    safe_print(
                        f"✅ {group_indicator} {code} - {account_template['name']}{parent_info}"
                    )

                    created_count += 1

                except Exception as e:
                    error_msg = f"❌ فشل إنشاء {code} - {account_template['name']}: {e}"
                    safe_print(error_msg)
                    errors.append(error_msg)

            safe_print("\n" + "=" * 60)
            safe_print(f"✅ تم إنشاء {created_count} حساب جديد")
            safe_print(f"⏭️  تم تخطي {skipped_count} حساب (موجود مسبقاً)")
            if errors:
                safe_print(f"❌ فشل إنشاء {len(errors)} حساب")
            safe_print("=" * 60)

            return {
                "success": True,
                "created": created_count,
                "skipped": skipped_count,
                "errors": errors,
                "message": f"تم إنشاء {created_count} حساب، تخطي {skipped_count} حساب موجود",
            }

        except Exception as e:
            error_msg = f"فشل إنشاء الحسابات الافتراضية: {e}"
            safe_print(f"ERROR: [AccountingService] {error_msg}")

            traceback.print_exc()
            return {
                "success": False,
                "created": created_count,
                "skipped": skipped_count,
                "errors": errors + [error_msg],
                "message": error_msg,
            }

    def cleanup_client_sub_accounts(self) -> dict:
        """
        تنظيف الحسابات الفرعية تحت حساب العملاء (1140)

        هذه الدالة تحذف أي حسابات فرعية تم إنشاؤها تحت حساب العملاء الرئيسي
        وتضمن أن حساب 1140 هو حساب معاملات (ليس مجموعة)

        Control Account Pattern:
        - جميع معاملات العملاء تُسجل في حساب 1140 مباشرة
        - لا يتم إنشاء حسابات فرعية لكل عميل
        - تتبع العملاء يتم عبر جدول العملاء وليس شجرة الحسابات
        """
        safe_print("=" * 60)
        safe_print("INFO: [AccountingService] بدء تنظيف الحسابات الفرعية للعملاء...")
        safe_print("=" * 60)

        deleted_count = 0
        errors = []

        try:
            # جلب جميع الحسابات
            all_accounts = self.repo.get_all_accounts()

            # البحث عن الحسابات الفرعية تحت 1140
            sub_accounts_to_delete = []
            main_account = None

            for acc in all_accounts:
                # حساب العملاء الرئيسي
                if acc.code == self.ACC_RECEIVABLE_CODE:
                    main_account = acc
                    continue

                # الحسابات الفرعية (تبدأ بـ 1140 أو parent_code = 1140)
                if acc.code and acc.code.startswith("1140") and acc.code != "1140":
                    sub_accounts_to_delete.append(acc)
                elif acc.parent_code == self.ACC_RECEIVABLE_CODE:
                    sub_accounts_to_delete.append(acc)

            safe_print(f"INFO: تم العثور على {len(sub_accounts_to_delete)} حساب فرعي للحذف")

            # حذف الحسابات الفرعية
            for acc in sub_accounts_to_delete:
                try:
                    account_id = acc._mongo_id or str(acc.id)
                    # أرشفة الحساب بدلاً من الحذف الكامل
                    success = self.repo.archive_account_by_id(account_id)
                    if success:
                        safe_print(f"✅ تم أرشفة: {acc.code} - {acc.name}")
                        deleted_count += 1
                    else:
                        safe_print(f"⚠️ فشل أرشفة: {acc.code} - {acc.name}")
                except Exception as e:
                    error_msg = f"فشل أرشفة {acc.code}: {e}"
                    safe_print(f"❌ {error_msg}")
                    errors.append(error_msg)

            # التأكد من أن حساب 1140 هو حساب معاملات (ليس مجموعة)
            if main_account:
                if getattr(main_account, "is_group", True):
                    try:
                        account_id = main_account._mongo_id or str(main_account.id)
                        updated_data = {"is_group": False}
                        self.repo.update_account(
                            account_id, main_account.model_copy(update=updated_data)
                        )
                        safe_print("✅ تم تحديث حساب العملاء (1140) ليكون حساب معاملات")
                    except Exception as e:
                        error_msg = f"فشل تحديث حساب 1140: {e}"
                        safe_print(f"❌ {error_msg}")
                        errors.append(error_msg)
                else:
                    safe_print("✅ حساب العملاء (1140) هو بالفعل حساب معاملات")
            else:
                safe_print("⚠️ حساب العملاء (1140) غير موجود!")

            safe_print("\n" + "=" * 60)
            safe_print(f"✅ تم أرشفة {deleted_count} حساب فرعي")
            if errors:
                safe_print(f"❌ فشل {len(errors)} عملية")
            safe_print("=" * 60)

            return {
                "success": len(errors) == 0,
                "deleted": deleted_count,
                "errors": errors,
                "message": f"تم أرشفة {deleted_count} حساب فرعي تحت العملاء",
            }

        except Exception as e:
            error_msg = f"فشل تنظيف الحسابات الفرعية: {e}"
            safe_print(f"ERROR: [AccountingService] {error_msg}")

            traceback.print_exc()
            return {
                "success": False,
                "deleted": deleted_count,
                "errors": errors + [error_msg],
                "message": error_msg,
            }

    def get_client_balance(self, client_id: str) -> float:
        """
        حساب رصيد عميل معين من قيود اليومية

        بما أننا نستخدم Control Account (1140) لجميع العملاء،
        نحتاج لحساب رصيد كل عميل من خلال تتبع القيود المرتبطة به

        Args:
            client_id: معرف العميل

        Returns:
            رصيد العميل (موجب = مستحق على العميل، سالب = مستحق للعميل)
        """
        try:
            # جلب جميع الفواتير للعميل
            invoices = (
                self.repo.get_invoices_by_client(client_id)
                if hasattr(self.repo, "get_invoices_by_client")
                else []
            )

            # جلب جميع الدفعات للعميل
            payments = (
                self.repo.get_payments_by_client(client_id)
                if hasattr(self.repo, "get_payments_by_client")
                else []
            )

            # حساب إجمالي الفواتير (مستحق على العميل)
            total_invoiced = sum(
                inv.total_amount for inv in invoices if hasattr(inv, "total_amount")
            )

            # حساب إجمالي المدفوعات (مدفوع من العميل)
            total_paid = sum(pay.amount for pay in payments if hasattr(pay, "amount"))

            # الرصيد = الفواتير - المدفوعات
            balance = total_invoiced - total_paid

            return float(balance)

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل حساب رصيد العميل {client_id}: {e}")
            return 0.0

    def get_all_clients_balances(self) -> list[dict]:
        """
        جلب أرصدة جميع العملاء

        Returns:
            قائمة بأرصدة العملاء [{client_id, client_name, balance}, ...]
        """
        try:
            # جلب جميع العملاء
            clients = self.repo.get_all_clients() if hasattr(self.repo, "get_all_clients") else []

            balances = []
            for client in clients:
                client_id = (
                    client._mongo_id or str(client.id)
                    if hasattr(client, "_mongo_id")
                    else str(client.id)
                )
                balance = self.get_client_balance(client_id)

                balances.append(
                    {
                        "client_id": client_id,
                        "client_name": client.name,
                        "balance": balance,
                        "status": "مستحق" if balance > 0 else ("مسدد" if balance == 0 else "دائن"),
                    }
                )

            return balances

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل جلب أرصدة العملاء: {e}")
            return []

    def fix_accounts_parent_codes(self) -> dict:
        """
        إصلاح ربط الحسابات بالآباء الصحيحين (Enterprise 6-Digit System)

        هذه الدالة تقوم بتحديث parent_code لجميع الحسابات بناءً على
        الهيكل المنطقي لشجرة الحسابات الاحترافية

        Returns:
            dict مع نتائج الإصلاح
        """
        safe_print("=" * 60)
        safe_print("INFO: [AccountingService] إصلاح ربط الحسابات بالآباء (Enterprise)...")
        safe_print("=" * 60)

        # خريطة الحسابات والآباء الصحيحين (Enterprise 6-Digit System)
        CORRECT_PARENT_MAP = {  # pylint: disable=invalid-name
            # ==================== الأصول (100000) ====================
            "100000": None,  # الأصول - جذر
            "110000": "100000",  # الأصول المتداولة
            "111000": "110000",  # النقدية وما في حكمها
            "111100": "111000",  # الخزائن النقدية
            "111101": "111100",  # الخزنة الرئيسية
            "111102": "111100",  # عهد نقدية موظفين
            "111200": "111000",  # الحسابات البنكية
            "111201": "111200",  # بنك مصر
            "111300": "111000",  # المحافظ الإلكترونية
            "111301": "111300",  # فودافون كاش الرئيسي
            "111302": "111300",  # فودافون كاش الفرعي
            "111303": "111300",  # InstaPay
            "112000": "110000",  # العملاء وأوراق القبض
            "112100": "112000",  # عملاء تجاريين
            "112200": "112000",  # عملاء أفراد
            "113000": "110000",  # أرصدة مدينة أخرى
            "113100": "113000",  # مصروفات مدفوعة مقدماً
            "113200": "113000",  # سلف العاملين
            "120000": "100000",  # الأصول غير المتداولة
            "121000": "120000",  # الأصول الثابتة
            "121100": "121000",  # أجهزة حاسب
            "121200": "121000",  # أثاث
            # ==================== الخصوم (200000) ====================
            "200000": None,  # الخصوم - جذر
            "210000": "200000",  # الخصوم المتداولة
            "211000": "210000",  # الموردين
            "211100": "211000",  # موردين تشغيل
            "211200": "211000",  # مستحقات مستقلين
            "212000": "210000",  # أرصدة دائنة أخرى
            "212100": "212000",  # دفعات مقدمة من العملاء
            "212200": "212000",  # ضريبة القيمة المضافة
            # ==================== حقوق الملكية (300000) ====================
            "300000": None,  # حقوق الملكية - جذر
            "310000": "300000",  # رأس المال
            "320000": "300000",  # جاري المالك
            "330000": "300000",  # الأرباح المرحلة
            # ==================== الإيرادات (400000) ====================
            "400000": None,  # الإيرادات - جذر
            "410000": "400000",  # إيرادات التشغيل
            "410100": "410000",  # إيرادات التسويق الرقمي
            "410200": "410000",  # إيرادات تطوير المواقع
            "410300": "410000",  # إيرادات الباقات
            # ==================== تكاليف الإيرادات COGS (500000) ====================
            "500000": None,  # تكاليف الإيرادات - جذر
            "510000": "500000",  # تكاليف الحملات والتشغيل
            "510001": "510000",  # ميزانية إعلانات
            "510002": "510000",  # تكلفة استضافة
            "510003": "510000",  # أجور مستقلين
            # ==================== المصروفات التشغيلية OPEX (600000) ====================
            "600000": None,  # المصروفات التشغيلية - جذر
            "610000": "600000",  # المصروفات التسويقية
            "610001": "610000",  # دعاية وإعلان
            "610002": "610000",  # عمولات البيع
            "620000": "600000",  # المصروفات الإدارية
            "620001": "620000",  # رواتب الموظفين
            "620002": "620000",  # إيجار ومرافق
            "620003": "620000",  # إنترنت واتصالات
            "620004": "620000",  # اشتراكات برمجيات
            "630000": "600000",  # المصروفات المالية
            "630001": "630000",  # رسوم بنكية
        }

        updated_count = 0
        skipped_count = 0
        errors = []

        try:
            # جلب جميع الحسابات
            all_accounts = self.repo.get_all_accounts()
            safe_print(f"INFO: عدد الحسابات: {len(all_accounts)}")

            for acc in all_accounts:
                if not acc.code:
                    continue

                # الحصول على الأب الصحيح
                correct_parent = CORRECT_PARENT_MAP.get(acc.code)
                # قاعدة البيانات تستخدم parent_id
                current_parent = getattr(acc, "parent_id", None) or getattr(
                    acc, "parent_code", None
                )

                # إذا لم يكن الكود في الخريطة، نحاول استنتاج الأب
                if acc.code not in CORRECT_PARENT_MAP:
                    # استنتاج الأب من الكود (مثال: 1105 -> 1100)
                    if len(acc.code) == 4:
                        possible_parent = acc.code[:2] + "00"
                        if possible_parent in CORRECT_PARENT_MAP or any(
                            a.code == possible_parent for a in all_accounts
                        ):
                            correct_parent = possible_parent
                        else:
                            possible_parent = acc.code[:1] + "000"
                            if possible_parent in CORRECT_PARENT_MAP or any(
                                a.code == possible_parent for a in all_accounts
                            ):
                                correct_parent = possible_parent

                # التحقق مما إذا كان التحديث مطلوباً
                current_str = str(current_parent).strip() if current_parent else None
                correct_str = str(correct_parent).strip() if correct_parent else None

                if current_str != correct_str:
                    try:
                        account_id = acc._mongo_id or str(acc.id)

                        # تحديث الحساب - استخدام parent_id لأن قاعدة البيانات تستخدمه
                        updated_data = acc.model_copy(
                            update={"parent_id": correct_parent, "parent_code": correct_parent}
                        )
                        self.repo.update_account(account_id, updated_data)

                        safe_print(
                            f"✅ تحديث {acc.code} ({acc.name}): {current_parent} -> {correct_parent}"
                        )
                        updated_count += 1

                    except Exception as e:
                        error_msg = f"فشل تحديث {acc.code}: {e}"
                        safe_print(f"❌ {error_msg}")
                        errors.append(error_msg)
                else:
                    skipped_count += 1

            safe_print("\n" + "=" * 60)
            safe_print(f"✅ تم تحديث {updated_count} حساب")
            safe_print(f"⏭️  تم تخطي {skipped_count} حساب (صحيح بالفعل)")
            if errors:
                safe_print(f"❌ فشل {len(errors)} عملية")
            safe_print("=" * 60)

            # إرسال إشارة التحديث
            app_signals.emit_data_changed("accounts")

            return {
                "success": len(errors) == 0,
                "updated": updated_count,
                "skipped": skipped_count,
                "errors": errors,
                "message": f"تم تحديث {updated_count} حساب",
            }

        except Exception as e:
            error_msg = f"فشل إصلاح الحسابات: {e}"
            safe_print(f"ERROR: [AccountingService] {error_msg}")

            traceback.print_exc()
            return {
                "success": False,
                "updated": updated_count,
                "skipped": skipped_count,
                "errors": errors + [error_msg],
                "message": error_msg,
            }

    def cleanup_all_data(self) -> dict:
        """
        تنظيف شامل للبيانات المكررة وإصلاح العلاقات

        يقوم بـ:
        1. تنظيف العملاء المكررين
        2. تنظيف المشاريع المكررة
        3. تنظيف الدفعات المكررة
        4. إصلاح ربط الحسابات بالآباء
        5. تنظيف الحسابات الفرعية للعملاء

        Returns:
            dict مع نتائج التنظيف الشامل
        """
        safe_print("=" * 70)
        safe_print("INFO: [AccountingService] ========== بدء التنظيف الشامل ==========")
        safe_print("=" * 70)

        results = {}

        try:
            # 1. تنظيف التكرارات من Repository
            if hasattr(self.repo, "cleanup_all_duplicates"):
                safe_print("\n📋 الخطوة 1: تنظيف التكرارات...")
                results["duplicates"] = self.repo.cleanup_all_duplicates()

            # 2. إصلاح ربط الحسابات
            safe_print("\n📋 الخطوة 2: إصلاح ربط الحسابات...")
            results["accounts_fix"] = self.fix_accounts_parent_codes()

            # 3. تنظيف الحسابات الفرعية للعملاء
            safe_print("\n📋 الخطوة 3: تنظيف الحسابات الفرعية للعملاء...")
            results["client_accounts"] = self.cleanup_client_sub_accounts()

            # إرسال إشارات التحديث
            app_signals.emit_data_changed("clients")
            app_signals.emit_data_changed("projects")
            app_signals.emit_data_changed("payments")
            app_signals.emit_data_changed("accounts")

            safe_print("\n" + "=" * 70)
            safe_print("INFO: [AccountingService] ========== انتهى التنظيف الشامل ==========")
            safe_print("=" * 70)

            return {"success": True, "results": results, "message": "تم التنظيف الشامل بنجاح"}

        except Exception as e:
            error_msg = f"فشل التنظيف الشامل: {e}"
            safe_print(f"ERROR: [AccountingService] {error_msg}")

            traceback.print_exc()
            return {"success": False, "results": results, "message": error_msg}

    def reset_to_enterprise_accounts(self) -> dict:
        """
        🔄 إعادة تعيين شجرة الحسابات إلى Enterprise Level (6 أرقام)

        هذه الدالة تقوم بـ:
        1. حذف جميع الحسابات القديمة (4 أرقام)
        2. إنشاء شجرة الحسابات الجديدة (6 أرقام)

        ⚠️ تحذير: هذه العملية ستحذف جميع الحسابات القديمة!
        """
        safe_print("=" * 70)
        safe_print("🔄 [AccountingService] إعادة تعيين شجرة الحسابات إلى Enterprise Level...")
        safe_print("=" * 70)

        deleted_count = 0
        errors = []

        try:
            # 1. جلب جميع الحسابات الموجودة
            all_accounts = self.repo.get_all_accounts()
            safe_print(f"INFO: عدد الحسابات الموجودة: {len(all_accounts)}")

            # 2. تحديد الحسابات القديمة (4 أرقام أو أقل)
            old_accounts = []
            for acc in all_accounts:
                if acc.code and len(acc.code) <= 4:
                    old_accounts.append(acc)

            safe_print(f"INFO: عدد الحسابات القديمة (4 أرقام): {len(old_accounts)}")

            # 3. حذف الحسابات القديمة (من الأوراق للجذور)
            # ترتيب الحسابات بحيث نحذف الأبناء أولاً
            old_accounts.sort(key=lambda x: len(x.code or ""), reverse=True)

            for acc in old_accounts:
                try:
                    account_id = acc._mongo_id or str(acc.id) or acc.code
                    success = self.repo.delete_account_permanently(account_id)
                    if success:
                        safe_print(f"✅ تم حذف: {acc.code} - {acc.name}")
                        deleted_count += 1
                    else:
                        safe_print(f"⚠️ فشل حذف: {acc.code} - {acc.name}")
                except Exception as e:
                    error_msg = f"فشل حذف {acc.code}: {e}"
                    safe_print(f"❌ {error_msg}")
                    errors.append(error_msg)

            safe_print(f"\n✅ تم حذف {deleted_count} حساب قديم")

            # 4. إنشاء الحسابات الجديدة (Enterprise Level)
            safe_print("\n📊 جاري إنشاء شجرة الحسابات الجديدة (Enterprise Level)...")
            seed_result = self.seed_default_accounts()

            # 5. إبطال الـ cache
            AccountingService._hierarchy_cache = None
            AccountingService._hierarchy_cache_time = 0

            # 6. إرسال إشارات التحديث
            app_signals.emit_data_changed("accounts")

            safe_print("\n" + "=" * 70)
            safe_print("✅ [AccountingService] تم إعادة تعيين شجرة الحسابات بنجاح!")
            safe_print("=" * 70)

            return {
                "success": True,
                "deleted": deleted_count,
                "created": seed_result.get("created", 0),
                "skipped": seed_result.get("skipped", 0),
                "errors": errors + seed_result.get("errors", []),
                "message": f"تم حذف {deleted_count} حساب قديم وإنشاء {seed_result.get('created', 0)} حساب جديد",
            }

        except Exception as e:
            error_msg = f"فشل إعادة تعيين شجرة الحسابات: {e}"
            safe_print(f"ERROR: [AccountingService] {error_msg}")

            traceback.print_exc()
            return {
                "success": False,
                "deleted": deleted_count,
                "created": 0,
                "skipped": 0,
                "errors": errors + [error_msg],
                "message": error_msg,
            }

    # ==================== Enhanced Dashboard Methods ====================
    # Requirements: 1.2, 1.4, 2.1, 2.2, 4.2

    def get_kpis_with_trends(self, start_date: datetime, end_date: datetime) -> dict:
        """
        جلب KPIs مع بيانات الفترة السابقة للمقارنة

        يحسب KPIs للفترة المحددة ويقارنها بالفترة السابقة المماثلة
        لحساب نسبة التغير واتجاه الاتجاه.

        Args:
            start_date: تاريخ بداية الفترة
            end_date: تاريخ نهاية الفترة

        Returns:
            dict مع KPIs وقيمها الحالية والسابقة:
            {
                "total_revenue": {"current": float, "previous": float},
                "total_expenses": {"current": float, "previous": float},
                "net_profit": {"current": float, "previous": float},
                "cash_collected": {"current": float, "previous": float},
                "receivables": {"current": float, "previous": float}
            }

        Requirements: 1.2, 1.4
        """
        safe_print(
            f"INFO: [AccountingService] جلب KPIs مع الاتجاهات من {start_date} إلى {end_date}"
        )

        try:
            # حساب طول الفترة لتحديد الفترة السابقة المماثلة
            period_length = (end_date - start_date).days + 1
            previous_end = start_date - timedelta(days=1)
            previous_start = previous_end - timedelta(days=period_length - 1)

            # جلب بيانات الفترة الحالية
            current_data = self._calculate_period_kpis(start_date, end_date)

            # جلب بيانات الفترة السابقة
            previous_data = self._calculate_period_kpis(previous_start, previous_end)

            return {
                "total_revenue": {
                    "current": current_data.get("total_revenue", 0.0),
                    "previous": previous_data.get("total_revenue", 0.0),
                },
                "total_expenses": {
                    "current": current_data.get("total_expenses", 0.0),
                    "previous": previous_data.get("total_expenses", 0.0),
                },
                "net_profit": {
                    "current": current_data.get("net_profit", 0.0),
                    "previous": previous_data.get("net_profit", 0.0),
                },
                "cash_collected": {
                    "current": current_data.get("cash_collected", 0.0),
                    "previous": previous_data.get("cash_collected", 0.0),
                },
                "receivables": {
                    "current": current_data.get("receivables", 0.0),
                    "previous": previous_data.get("receivables", 0.0),
                },
            }

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل جلب KPIs مع الاتجاهات: {e}")

            traceback.print_exc()
            return {
                "total_revenue": {"current": 0.0, "previous": 0.0},
                "total_expenses": {"current": 0.0, "previous": 0.0},
                "net_profit": {"current": 0.0, "previous": 0.0},
                "cash_collected": {"current": 0.0, "previous": 0.0},
                "receivables": {"current": 0.0, "previous": 0.0},
            }

    def _calculate_period_kpis(self, start_date: datetime, end_date: datetime) -> dict:
        """
        حساب KPIs لفترة محددة

        Args:
            start_date: تاريخ البداية
            end_date: تاريخ النهاية

        Returns:
            dict مع قيم KPIs للفترة
        """
        try:
            total_revenue = 0.0
            total_expenses = 0.0
            cash_collected = 0.0

            # جلب قيود اليومية للفترة
            all_entries = self.repo.get_all_journal_entries()

            # جلب معلومات الحسابات
            all_accounts = self.repo.get_all_accounts()
            account_types = {acc.code: acc.type for acc in all_accounts if acc.code}

            for entry in all_entries:
                entry_date = entry.date
                if not entry_date:
                    continue

                # التحقق من أن القيد ضمن الفترة
                if not start_date <= entry_date <= end_date:
                    continue

                for line in entry.lines:
                    acc_code = getattr(line, "account_code", None) or str(line.account_id)
                    acc_type = account_types.get(acc_code)

                    if acc_type == schemas.AccountType.REVENUE:
                        total_revenue += line.credit
                    elif acc_type == schemas.AccountType.EXPENSE:
                        total_expenses += line.debit

            # جلب الدفعات المحصلة للفترة
            if hasattr(self.repo, "get_all_payments"):
                all_payments = self.repo.get_all_payments()
                for payment in all_payments:
                    payment_date = payment.date
                    if payment_date and start_date <= payment_date <= end_date:
                        cash_collected += payment.amount

            # حساب المستحقات (من المشاريع)
            receivables = 0.0
            if hasattr(self.repo, "get_all_projects"):
                all_projects = self.repo.get_all_projects()
                for project in all_projects:
                    project_start = getattr(project, "start_date", None)
                    if project_start and start_date <= project_start <= end_date:
                        # المستحقات = إجمالي المشروع - المدفوع
                        project_total = getattr(project, "total_amount", 0) or 0
                        # جلب الدفعات للمشروع
                        project_id = project._mongo_id or str(project.id)
                        project_payments = 0.0
                        if hasattr(self.repo, "get_payments_by_project"):
                            payments = self.repo.get_payments_by_project(project_id)
                            project_payments = sum(p.amount for p in payments)
                        receivables += max(0, project_total - project_payments)

            net_profit = total_revenue - total_expenses

            return {
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "net_profit": net_profit,
                "cash_collected": cash_collected,
                "receivables": receivables,
            }

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل حساب KPIs للفترة: {e}")
            return {
                "total_revenue": 0.0,
                "total_expenses": 0.0,
                "net_profit": 0.0,
                "cash_collected": 0.0,
                "receivables": 0.0,
            }

    def get_cash_flow_data(
        self, start_date: datetime, end_date: datetime, period: str = "monthly"
    ) -> dict:
        """
        جلب بيانات التدفق النقدي مجمعة حسب الفترة الزمنية

        Args:
            start_date: تاريخ البداية
            end_date: تاريخ النهاية
            period: الفترة الزمنية للتجميع ("daily", "weekly", "monthly")

        Returns:
            dict مع بيانات التدفق النقدي:
            {
                "inflows": [(date_str, amount), ...],
                "outflows": [(date_str, amount), ...],
                "net_flow": [(date_str, amount), ...]
            }

        Requirements: 2.1, 2.2
        """
        safe_print(
            f"INFO: [AccountingService] جلب بيانات التدفق النقدي ({period}) من {start_date} إلى {end_date}"
        )

        try:
            # جمع البيانات الخام
            raw_inflows: list[tuple[datetime, float]] = []
            raw_outflows: list[tuple[datetime, float]] = []

            # جلب الدفعات (التدفقات الداخلة)
            if hasattr(self.repo, "get_all_payments"):
                all_payments = self.repo.get_all_payments()
                for payment in all_payments:
                    payment_date = payment.date
                    if payment_date and start_date <= payment_date <= end_date:
                        raw_inflows.append((payment_date, payment.amount))

            # جلب المصروفات (التدفقات الخارجة)
            if hasattr(self.repo, "get_all_expenses"):
                all_expenses = self.repo.get_all_expenses()
                for expense in all_expenses:
                    expense_date = expense.date
                    if expense_date and start_date <= expense_date <= end_date:
                        raw_outflows.append((expense_date, expense.amount))

            # تجميع البيانات حسب الفترة
            aggregated_inflows = self._aggregate_cash_flow_by_period(raw_inflows, period)
            aggregated_outflows = self._aggregate_cash_flow_by_period(raw_outflows, period)

            # حساب صافي التدفق
            all_periods = set(aggregated_inflows.keys()) | set(aggregated_outflows.keys())
            net_flow = {}
            for period_key in all_periods:
                inflow = aggregated_inflows.get(period_key, 0.0)
                outflow = aggregated_outflows.get(period_key, 0.0)
                net_flow[period_key] = inflow - outflow

            # تحويل إلى قوائم مرتبة
            sorted_periods = sorted(all_periods)

            return {
                "inflows": [(p, aggregated_inflows.get(p, 0.0)) for p in sorted_periods],
                "outflows": [(p, aggregated_outflows.get(p, 0.0)) for p in sorted_periods],
                "net_flow": [(p, net_flow.get(p, 0.0)) for p in sorted_periods],
            }

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل جلب بيانات التدفق النقدي: {e}")

            traceback.print_exc()
            return {"inflows": [], "outflows": [], "net_flow": []}

    def _aggregate_cash_flow_by_period(
        self, data: list[tuple[datetime, float]], period: str
    ) -> dict[str, float]:
        """
        تجميع بيانات التدفق النقدي حسب الفترة الزمنية

        Args:
            data: قائمة من (التاريخ، المبلغ)
            period: الفترة الزمنية ("daily", "weekly", "monthly")

        Returns:
            dict مع المفتاح = الفترة والقيمة = المجموع

        Requirements: 2.2
        """
        aggregated: dict[str, float] = {}

        for date_val, amount in data:
            if period == "daily":
                # التجميع اليومي: YYYY-MM-DD
                period_key = date_val.strftime("%Y-%m-%d")
            elif period == "weekly":
                # التجميع الأسبوعي: YYYY-WXX (رقم الأسبوع)
                year, week, _ = date_val.isocalendar()
                period_key = f"{year}-W{week:02d}"
            else:  # monthly
                # التجميع الشهري: YYYY-MM
                period_key = date_val.strftime("%Y-%m")

            if period_key not in aggregated:
                aggregated[period_key] = 0.0
            aggregated[period_key] += amount

        return aggregated

    def get_filtered_data_by_date_range(
        self, start_date: datetime, end_date: datetime, data_type: str = "all"
    ) -> dict:
        """
        فلترة البيانات المالية حسب نطاق التاريخ

        Args:
            start_date: تاريخ البداية
            end_date: تاريخ النهاية
            data_type: نوع البيانات ("all", "payments", "expenses", "projects", "journal_entries")

        Returns:
            dict مع البيانات المفلترة

        Requirements: 4.2
        """
        safe_print(
            f"INFO: [AccountingService] فلترة البيانات ({data_type}) من {start_date} إلى {end_date}"
        )

        result = {"payments": [], "expenses": [], "projects": [], "journal_entries": []}

        try:
            # فلترة الدفعات
            if data_type in ["all", "payments"] and hasattr(self.repo, "get_all_payments"):
                all_payments = self.repo.get_all_payments()
                result["payments"] = [
                    p for p in all_payments if p.date and start_date <= p.date <= end_date
                ]

            # فلترة المصروفات
            if data_type in ["all", "expenses"] and hasattr(self.repo, "get_all_expenses"):
                all_expenses = self.repo.get_all_expenses()
                result["expenses"] = [
                    e for e in all_expenses if e.date and start_date <= e.date <= end_date
                ]

            # فلترة المشاريع
            if data_type in ["all", "projects"] and hasattr(self.repo, "get_all_projects"):
                all_projects = self.repo.get_all_projects()
                result["projects"] = [
                    p
                    for p in all_projects
                    if (getattr(p, "start_date", None) and start_date <= p.start_date <= end_date)
                ]

            # فلترة قيود اليومية
            if data_type in ["all", "journal_entries"]:
                all_entries = self.repo.get_all_journal_entries()
                result["journal_entries"] = [
                    e for e in all_entries if e.date and start_date <= e.date <= end_date
                ]

            safe_print(
                f"INFO: [AccountingService] تم فلترة: {len(result['payments'])} دفعة، "
                f"{len(result['expenses'])} مصروف، {len(result['projects'])} مشروع، "
                f"{len(result['journal_entries'])} قيد"
            )

            return result

        except Exception as e:
            safe_print(f"ERROR: [AccountingService] فشل فلترة البيانات: {e}")

            traceback.print_exc()
            return result
