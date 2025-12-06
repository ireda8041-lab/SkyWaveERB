#!/usr/bin/env python3
"""
خدمة البحث الذكي - Smart Search Service
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SearchScope(Enum):
    """نطاق البحث"""
    ALL = "الكل"
    PROJECTS = "المشاريع"
    CLIENTS = "العملاء"
    INVOICES = "الفواتير"
    EXPENSES = "المصروفات"
    ACCOUNTS = "الحسابات"
    QUOTATIONS = "عروض الأسعار"
    PAYMENTS = "الدفعات"
    SERVICES = "الخدمات"
    ACCOUNTING = "المحاسبة"


class SearchType(Enum):
    """نوع البحث"""
    TEXT = "نص"
    NUMBER = "رقم"
    DATE = "تاريخ"
    AMOUNT = "مبلغ"
    EXACT = "مطابق"
    FUZZY = "تقريبي"
    PARTIAL = "جزئي"


@dataclass
class SearchFilter:
    """فلتر البحث"""
    field: str = ""
    operator: str = ""
    value: Any = None
    date_from: Any = None
    date_to: Any = None
    amount_min: float | None = None
    amount_max: float | None = None
    status: str | None = None
    client_id: str | None = None
    project_id: str | None = None


@dataclass
class SearchResult:
    """نتيجة البحث"""
    type: str
    id: str
    title: str
    subtitle: str
    data: dict[str, Any]
    score: float = 1.0


class SmartSearchService:
    """
    خدمة البحث الذكي - تبحث في جميع أنواع البيانات
    """

    def __init__(self, repository):
        self.repo = repository

    def search(
        self,
        query: str,
        scope: SearchScope = SearchScope.ALL,
        filters: list[SearchFilter] | None = None
    ) -> list[SearchResult]:
        """
        البحث الذكي في النظام

        Args:
            query: نص البحث
            scope: نطاق البحث
            filters: فلاتر إضافية

        Returns:
            قائمة نتائج البحث
        """
        results = []

        if scope == SearchScope.ALL or scope == SearchScope.PROJECTS:
            results.extend(self._search_projects(query, filters))

        if scope == SearchScope.ALL or scope == SearchScope.CLIENTS:
            results.extend(self._search_clients(query, filters))

        if scope == SearchScope.ALL or scope == SearchScope.EXPENSES:
            results.extend(self._search_expenses(query, filters))

        if scope == SearchScope.ALL or scope == SearchScope.ACCOUNTS:
            results.extend(self._search_accounts(query, filters))

        # ترتيب النتائج حسب الأهمية
        results.sort(key=lambda x: x.score, reverse=True)

        return results

    def _search_projects(self, query: str, filters: list[SearchFilter] | None = None) -> list[SearchResult]:
        """البحث في المشاريع - يشمل البحث برقم الفاتورة"""
        results = []

        try:
            projects = self.repo.get_all_projects()
            query_lower = query.lower()
            query_upper = query.upper()

            for idx, project in enumerate(projects):
                score = 0.0

                # ⚡ استخدم رقم الفاتورة المحفوظ أولاً، وإلا ولّد رقم جديد
                invoice_number = getattr(project, 'invoice_number', None)
                if not invoice_number:
                    local_id = getattr(project, 'id', None) or (idx + 1)
                    invoice_number = f"SW-{97161 + int(local_id)}"

                # البحث برقم الفاتورة (أعلى أولوية)
                if query_upper in invoice_number.upper() or query in invoice_number:
                    score += 1.5

                # البحث في الاسم
                if query_lower in project.name.lower():
                    score += 1.0

                # البحث في اسم العميل
                if query_lower in project.client_id.lower():
                    score += 0.8

                # البحث في الوصف
                if project.project_notes and query_lower in project.project_notes.lower():
                    score += 0.5

                # البحث في الحالة
                if project.status and query_lower in project.status.value.lower():
                    score += 0.4

                if score > 0:
                    results.append(SearchResult(
                        type="project",
                        id=project.name,
                        title=f"{invoice_number} - {project.name}",
                        subtitle=f"العميل: {project.client_id} | {project.total_amount:,.2f} جنيه | {project.status.value}",
                        data={
                            "name": project.name,
                            "client": project.client_id,
                            "amount": project.total_amount,
                            "status": project.status.value,
                            "invoice_number": invoice_number
                        },
                        score=score
                    ))

        except Exception as e:
            print(f"ERROR: [SearchService] فشل البحث في المشاريع: {e}")

        return results

    def _search_clients(self, query: str, filters: list[SearchFilter] | None = None) -> list[SearchResult]:
        """البحث في العملاء"""
        results = []

        try:
            clients = self.repo.get_all_clients()
            query_lower = query.lower()

            for client in clients:
                score = 0.0

                # البحث في الاسم
                if query_lower in client.name.lower():
                    score += 1.0

                # البحث في الهاتف
                if client.phone and query in client.phone:
                    score += 0.9

                # البحث في البريد
                if client.email and query_lower in client.email.lower():
                    score += 0.8

                if score > 0:
                    results.append(SearchResult(
                        type="client",
                        id=str(client.id),
                        title=client.name,
                        subtitle=f"الهاتف: {client.phone or 'N/A'} | البريد: {client.email or 'N/A'}",
                        data={
                            "name": client.name,
                            "phone": client.phone,
                            "email": client.email
                        },
                        score=score
                    ))

        except Exception as e:
            print(f"ERROR: [SearchService] فشل البحث في العملاء: {e}")

        return results

    def _search_expenses(self, query: str, filters: list[SearchFilter] | None = None) -> list[SearchResult]:
        """البحث في المصروفات"""
        results = []

        try:
            expenses = self.repo.get_all_expenses()
            query_lower = query.lower()

            for expense in expenses:
                score = 0.0

                # البحث في الفئة
                if query_lower in expense.category.lower():
                    score += 1.0

                # البحث في الوصف
                if expense.description and query_lower in expense.description.lower():
                    score += 0.8

                # البحث في المبلغ
                if query in str(expense.amount):
                    score += 0.6

                if score > 0:
                    results.append(SearchResult(
                        type="expense",
                        id=str(expense.id),
                        title=expense.category,
                        subtitle=f"{expense.amount:,.2f} جنيه | {expense.date.strftime('%Y-%m-%d') if expense.date else 'N/A'}",
                        data={
                            "category": expense.category,
                            "amount": expense.amount,
                            "date": expense.date
                        },
                        score=score
                    ))

        except Exception as e:
            print(f"ERROR: [SearchService] فشل البحث في المصروفات: {e}")

        return results

    def _search_accounts(self, query: str, filters: list[SearchFilter] | None = None) -> list[SearchResult]:
        """البحث في الحسابات"""
        results = []

        try:
            accounts = self.repo.get_all_accounts()
            query_lower = query.lower()

            for account in accounts:
                score = 0.0

                # البحث في الاسم
                if query_lower in account.name.lower():
                    score += 1.0

                # البحث في الكود
                if account.code and query in account.code:
                    score += 0.9

                if score > 0:
                    results.append(SearchResult(
                        type="account",
                        id=account.code,
                        title=account.name,
                        subtitle=f"الكود: {account.code} | الرصيد: {account.balance:,.2f} جنيه",
                        data={
                            "name": account.name,
                            "code": account.code,
                            "balance": account.balance
                        },
                        score=score
                    ))

        except Exception as e:
            print(f"ERROR: [SearchService] فشل البحث في الحسابات: {e}")

        return results
