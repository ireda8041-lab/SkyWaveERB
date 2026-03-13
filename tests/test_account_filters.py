from types import SimpleNamespace

from core import schemas
from core.account_filters import (
    filter_operational_cashboxes,
    get_cashbox_treasury_type,
    infer_payment_method_from_account,
    is_operational_cashbox,
)


def _account(
    code: str,
    account_type: schemas.AccountType,
    name: str = "اختبار",
    *,
    is_group: bool = False,
):
    return schemas.Account(name=name, code=code, type=account_type, is_group=is_group)


def test_is_operational_cashbox_excludes_non_cash_accounts():
    assert not is_operational_cashbox(_account("112100", schemas.AccountType.ASSET))
    assert not is_operational_cashbox(_account("212100", schemas.AccountType.LIABILITY))
    assert not is_operational_cashbox(_account("410100", schemas.AccountType.REVENUE))


def test_is_operational_cashbox_excludes_group_rows():
    assert not is_operational_cashbox(_account("111000", schemas.AccountType.CASH, is_group=True))


def test_is_operational_cashbox_accepts_user_cashboxes():
    assert is_operational_cashbox(_account("111000", schemas.AccountType.CASH))
    assert is_operational_cashbox(_account("111301", schemas.AccountType.CASH))
    assert is_operational_cashbox(
        SimpleNamespace(code="111555", type=schemas.AccountType.CASH.value, is_group=False)
    )


def test_filter_operational_cashboxes_keeps_only_real_cashboxes():
    accounts = [
        _account("111000", schemas.AccountType.CASH, "الخزنة الرئيسية"),
        _account("111300", schemas.AccountType.CASH, "مجموعة خزن", is_group=True),
        _account("112100", schemas.AccountType.ASSET, "حساب العملاء"),
        _account("111002", schemas.AccountType.CASH, "VF Cash"),
    ]

    filtered = filter_operational_cashboxes(accounts)

    assert [account.code for account in filtered] == ["111000", "111002"]


def test_get_cashbox_treasury_type_prefers_serialized_description():
    account = schemas.Account(
        name="إنستا باي",
        code="111003",
        type=schemas.AccountType.CASH,
        description="نوع الخزنة: إنستا باي\n\nبيانات الخزنة:\nskywaveads@instapay",
    )

    assert get_cashbox_treasury_type(account) == "إنستا باي"


def test_get_cashbox_treasury_type_skips_group_parent_accounts():
    account = schemas.Account(
        name="قنوات التحصيل",
        code="111000",
        type=schemas.AccountType.CASH,
        is_group=True,
        description="الحساب الرئيسي لقنوات التحصيل النقدية والإلكترونية والتحويلات البنكية.",
    )

    assert get_cashbox_treasury_type(account) == ""
    assert infer_payment_method_from_account(account) == "Other"


def test_infer_payment_method_from_account_handles_arabic_instapay_spacing():
    account = schemas.Account(
        name="إنستا باي",
        code="111003",
        type=schemas.AccountType.CASH,
        description="نوع الخزنة: إنستا باي\n\nبيانات الخزنة:\n01067894321 - حازم أشرف",
    )

    assert infer_payment_method_from_account(account) == "InstaPay"


def test_infer_payment_method_from_account_recognizes_cash_payment_cashbox():
    account = schemas.Account(
        name="Cash",
        code="111006",
        type=schemas.AccountType.CASH,
        description="نوع الخزنة: خزنة نقدية\n\nبيانات الخزنة:\nالخزنة النقدية - مقر الشركة",
    )

    assert get_cashbox_treasury_type(account) == "خزنة نقدية"
    assert infer_payment_method_from_account(account) == "Cash"
