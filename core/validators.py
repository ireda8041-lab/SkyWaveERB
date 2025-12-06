# الملف: core/validators.py
"""
نظام التحقق من صحة البيانات (Validators)

يوفر:
- التحقق من صحة بيانات العملاء
- التحقق من صحة بيانات المشاريع
- التحقق من صحة بيانات الفواتير
- التحقق من صحة القيود المحاسبية

المؤلف: Sky Wave Team
الإصدار: 1.0.0
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """استثناء خطأ التحقق"""

    def __init__(self, message: str, field: str | None = None, errors: list[str] | None = None):
        self.message = message
        self.field = field
        self.errors = errors or [message]
        super().__init__(message)


class BaseValidator:
    """
    المحقق الأساسي

    يوفر دوال مساعدة للتحقق من البيانات
    """

    @staticmethod
    def is_empty(value: Any) -> bool:
        """التحقق من أن القيمة فارغة"""
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        if isinstance(value, (list, dict)) and len(value) == 0:
            return True
        return False

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """التحقق من صحة البريد الإلكتروني"""
        if not email:
            return True  # البريد اختياري
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @staticmethod
    def is_valid_phone(phone: str) -> bool:
        """التحقق من صحة رقم الهاتف"""
        if not phone:
            return True  # الهاتف اختياري
        # إزالة المسافات والشرطات
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        # التحقق من أن الرقم يحتوي على أرقام فقط (مع + اختياري في البداية)
        pattern = r'^\+?[0-9]{8,15}$'
        return bool(re.match(pattern, cleaned))

    @staticmethod
    def is_positive_number(value: float) -> bool:
        """التحقق من أن الرقم موجب"""
        return value is not None and value >= 0

    @staticmethod
    def is_valid_percentage(value: float) -> bool:
        """التحقق من أن النسبة صحيحة (0-100)"""
        return value is not None and 0 <= value <= 100

    @staticmethod
    def is_valid_date(date: Any) -> bool:
        """التحقق من صحة التاريخ"""
        return date is not None and isinstance(date, datetime)

    @staticmethod
    def is_future_date(date: datetime) -> bool:
        """التحقق من أن التاريخ في المستقبل"""
        return date is not None and date > datetime.now()


class ClientValidator(BaseValidator):
    """
    محقق بيانات العملاء
    """

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        التحقق من صحة بيانات العميل

        Args:
            data: بيانات العميل

        Returns:
            (صحيح/خاطئ, قائمة الأخطاء)
        """
        errors = []

        # التحقق من الاسم (مطلوب)
        if self.is_empty(data.get('name')):
            errors.append("اسم العميل مطلوب")
        elif len(data.get('name', '')) < 2:
            errors.append("اسم العميل يجب أن يكون حرفين على الأقل")

        # التحقق من البريد الإلكتروني (اختياري)
        if not self.is_valid_email(data.get('email', '')):
            errors.append("البريد الإلكتروني غير صحيح")

        # التحقق من رقم الهاتف (اختياري)
        if not self.is_valid_phone(data.get('phone', '')):
            errors.append("رقم الهاتف غير صحيح")

        is_valid = len(errors) == 0

        if not is_valid:
            logger.warning(f"[ClientValidator] فشل التحقق: {errors}")

        return is_valid, errors


class ProjectValidator(BaseValidator):
    """
    محقق بيانات المشاريع
    """

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        التحقق من صحة بيانات المشروع

        Args:
            data: بيانات المشروع

        Returns:
            (صحيح/خاطئ, قائمة الأخطاء)
        """
        errors = []

        # التحقق من اسم المشروع (مطلوب)
        if self.is_empty(data.get('name')):
            errors.append("اسم المشروع مطلوب")

        # التحقق من معرف العميل (مطلوب)
        if self.is_empty(data.get('client_id')):
            errors.append("يجب تحديد العميل")

        # التحقق من البنود
        items = data.get('items', [])
        if items:
            for i, item in enumerate(items):
                item_errors = self._validate_item(item, i + 1)
                errors.extend(item_errors)

        # التحقق من نسبة الخصم
        discount_rate = data.get('discount_rate', 0)
        if not self.is_valid_percentage(discount_rate):
            errors.append("نسبة الخصم يجب أن تكون بين 0 و 100")

        # التحقق من نسبة الضريبة
        tax_rate = data.get('tax_rate', 0)
        if not self.is_valid_percentage(tax_rate):
            errors.append("نسبة الضريبة يجب أن تكون بين 0 و 100")

        is_valid = len(errors) == 0

        if not is_valid:
            logger.warning(f"[ProjectValidator] فشل التحقق: {errors}")

        return is_valid, errors

    def _validate_item(self, item: dict[str, Any], index: int) -> list[str]:
        """التحقق من صحة بند المشروع"""
        errors = []
        prefix = f"البند {index}"

        if self.is_empty(item.get('description')):
            errors.append(f"{prefix}: الوصف مطلوب")

        quantity = item.get('quantity', 0)
        if not self.is_positive_number(quantity) or quantity <= 0:
            errors.append(f"{prefix}: الكمية يجب أن تكون أكبر من صفر")

        unit_price = item.get('unit_price', 0)
        if not self.is_positive_number(unit_price):
            errors.append(f"{prefix}: سعر الوحدة يجب أن يكون موجباً")

        return errors


class InvoiceValidator(BaseValidator):
    """
    محقق بيانات الفواتير
    """

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        التحقق من صحة بيانات الفاتورة

        Args:
            data: بيانات الفاتورة

        Returns:
            (صحيح/خاطئ, قائمة الأخطاء)
        """
        errors = []

        # التحقق من رقم الفاتورة (مطلوب)
        if self.is_empty(data.get('invoice_number')):
            errors.append("رقم الفاتورة مطلوب")

        # التحقق من معرف العميل (مطلوب)
        if self.is_empty(data.get('client_id')):
            errors.append("يجب تحديد العميل")

        # التحقق من تاريخ الإصدار
        issue_date = data.get('issue_date')
        if not self.is_valid_date(issue_date):
            errors.append("تاريخ الإصدار غير صحيح")

        # التحقق من تاريخ الاستحقاق
        due_date = data.get('due_date')
        if not self.is_valid_date(due_date):
            errors.append("تاريخ الاستحقاق غير صحيح")
        elif issue_date and due_date and due_date < issue_date:
            errors.append("تاريخ الاستحقاق يجب أن يكون بعد تاريخ الإصدار")

        # التحقق من البنود
        items = data.get('items', [])
        if not items:
            errors.append("الفاتورة يجب أن تحتوي على بند واحد على الأقل")
        else:
            for i, item in enumerate(items):
                item_errors = self._validate_item(item, i + 1)
                errors.extend(item_errors)

        is_valid = len(errors) == 0

        if not is_valid:
            logger.warning(f"[InvoiceValidator] فشل التحقق: {errors}")

        return is_valid, errors

    def _validate_item(self, item: dict[str, Any], index: int) -> list[str]:
        """التحقق من صحة بند الفاتورة"""
        errors = []
        prefix = f"البند {index}"

        if self.is_empty(item.get('description')):
            errors.append(f"{prefix}: الوصف مطلوب")

        quantity = item.get('quantity', 0)
        if not self.is_positive_number(quantity) or quantity <= 0:
            errors.append(f"{prefix}: الكمية يجب أن تكون أكبر من صفر")

        unit_price = item.get('unit_price', 0)
        if not self.is_positive_number(unit_price):
            errors.append(f"{prefix}: سعر الوحدة يجب أن يكون موجباً")

        return errors


class ExpenseValidator(BaseValidator):
    """
    محقق بيانات المصروفات
    """

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        التحقق من صحة بيانات المصروف

        Args:
            data: بيانات المصروف

        Returns:
            (صحيح/خاطئ, قائمة الأخطاء)
        """
        errors = []

        # التحقق من الفئة (مطلوب)
        if self.is_empty(data.get('category')):
            errors.append("فئة المصروف مطلوبة")

        # التحقق من المبلغ (مطلوب وموجب)
        amount = data.get('amount', 0)
        if not self.is_positive_number(amount) or amount <= 0:
            errors.append("المبلغ يجب أن يكون أكبر من صفر")

        # التحقق من حساب المصروف (مطلوب)
        if self.is_empty(data.get('account_id')):
            errors.append("يجب تحديد حساب المصروف")

        # التحقق من حساب الدفع (مطلوب)
        if self.is_empty(data.get('payment_account_id')):
            errors.append("يجب تحديد حساب الدفع")

        # التحقق من التاريخ
        date = data.get('date')
        if not self.is_valid_date(date):
            errors.append("التاريخ غير صحيح")

        is_valid = len(errors) == 0

        if not is_valid:
            logger.warning(f"[ExpenseValidator] فشل التحقق: {errors}")

        return is_valid, errors


class JournalEntryValidator(BaseValidator):
    """
    محقق قيود اليومية
    """

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        التحقق من صحة قيد اليومية

        Args:
            data: بيانات القيد

        Returns:
            (صحيح/خاطئ, قائمة الأخطاء)
        """
        errors = []

        # التحقق من الوصف (مطلوب)
        if self.is_empty(data.get('description')):
            errors.append("وصف القيد مطلوب")

        # التحقق من التاريخ
        date = data.get('date')
        if not self.is_valid_date(date):
            errors.append("التاريخ غير صحيح")

        # التحقق من الأسطر
        lines = data.get('lines', [])
        if len(lines) < 2:
            errors.append("القيد يجب أن يحتوي على سطرين على الأقل")
        else:
            total_debit = 0.0
            total_credit = 0.0

            for i, line in enumerate(lines):
                line_errors = self._validate_line(line, i + 1)
                errors.extend(line_errors)

                total_debit += line.get('debit', 0) or 0
                total_credit += line.get('credit', 0) or 0

            # التحقق من توازن القيد
            if abs(total_debit - total_credit) > 0.01:
                errors.append(f"القيد غير متوازن: مدين={total_debit:.2f}, دائن={total_credit:.2f}")

        is_valid = len(errors) == 0

        if not is_valid:
            logger.warning(f"[JournalEntryValidator] فشل التحقق: {errors}")

        return is_valid, errors

    def _validate_line(self, line: dict[str, Any], index: int) -> list[str]:
        """التحقق من صحة سطر القيد"""
        errors = []
        prefix = f"السطر {index}"

        # التحقق من معرف الحساب
        if self.is_empty(line.get('account_id')):
            errors.append(f"{prefix}: يجب تحديد الحساب")

        debit = line.get('debit', 0) or 0
        credit = line.get('credit', 0) or 0

        # التحقق من أن أحدهما على الأقل موجب
        if debit == 0 and credit == 0:
            errors.append(f"{prefix}: يجب تحديد مبلغ مدين أو دائن")

        # التحقق من عدم وجود مدين ودائن معاً
        if debit > 0 and credit > 0:
            errors.append(f"{prefix}: لا يمكن أن يكون السطر مدين ودائن في نفس الوقت")

        return errors


class AccountValidator(BaseValidator):
    """
    محقق بيانات الحسابات
    """

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        التحقق من صحة بيانات الحساب

        Args:
            data: بيانات الحساب

        Returns:
            (صحيح/خاطئ, قائمة الأخطاء)
        """
        errors = []

        # التحقق من الاسم (مطلوب)
        if self.is_empty(data.get('name')):
            errors.append("اسم الحساب مطلوب")

        # التحقق من الكود (مطلوب)
        code = data.get('code', '')
        if self.is_empty(code):
            errors.append("كود الحساب مطلوب")
        elif not code.isdigit():
            errors.append("كود الحساب يجب أن يحتوي على أرقام فقط")

        # التحقق من النوع (مطلوب)
        if self.is_empty(data.get('type')):
            errors.append("نوع الحساب مطلوب")

        is_valid = len(errors) == 0

        if not is_valid:
            logger.warning(f"[AccountValidator] فشل التحقق: {errors}")

        return is_valid, errors


# دوال مساعدة للاستخدام السريع

def validate_client(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """التحقق من صحة بيانات العميل"""
    return ClientValidator().validate(data)


def validate_project(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """التحقق من صحة بيانات المشروع"""
    return ProjectValidator().validate(data)


def validate_invoice(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """التحقق من صحة بيانات الفاتورة"""
    return InvoiceValidator().validate(data)


def validate_expense(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """التحقق من صحة بيانات المصروف"""
    return ExpenseValidator().validate(data)


def validate_journal_entry(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """التحقق من صحة قيد اليومية"""
    return JournalEntryValidator().validate(data)


def validate_account(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """التحقق من صحة بيانات الحساب"""
    return AccountValidator().validate(data)
