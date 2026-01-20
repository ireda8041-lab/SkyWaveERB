# الملف: services/export_service.py
"""
خدمة التصدير - تصدير البيانات إلى Excel, CSV, PDF
"""

import csv
import os
import platform
import subprocess
import sys
from datetime import datetime
from typing import Any

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    safe_print("WARNING: [ExportService] pandas not available. Install with: pip install pandas openpyxl")


class ExportService:
    """خدمة التصدير الشاملة"""

    def __init__(self):
        # ⚡ حفظ التصدير في مجلد exports داخل مسار التثبيت
        if getattr(sys, 'frozen', False):
            # البرنامج مجمع (EXE) - مسار التثبيت هو مجلد الـ EXE
            install_path = os.path.dirname(sys.executable)
        else:
            # البرنامج يعمل من Python
            install_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.export_folder = os.path.join(install_path, "exports")
        self._ensure_export_folder()

    def _ensure_export_folder(self):
        """إنشاء مجلد التصدير إذا لم يكن موجود"""
        if not os.path.exists(self.export_folder):
            os.makedirs(self.export_folder)
            safe_print(f"INFO: [ExportService] Created exports folder: {self.export_folder}")

    def export_to_excel(self, data: list[dict[str, Any]], filename: str | None = None, sheet_name: str = "البيانات") -> str | None:
        """تصدير البيانات إلى Excel"""
        if not PANDAS_AVAILABLE:
            safe_print("ERROR: [ExportService] pandas not available for Excel export")
            return None

        if not data:
            safe_print("WARNING: [ExportService] No data to export")
            return None

        try:
            # إنشاء اسم الملف
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"export_{timestamp}.xlsx"

            if not filename.endswith('.xlsx'):
                filename += '.xlsx'

            filepath = os.path.join(self.export_folder, filename)

            # تحويل البيانات إلى DataFrame
            df = pd.DataFrame(data)

            # تصدير إلى Excel
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)

            safe_print(f"INFO: [ExportService] Excel exported: {filepath}")
            return filepath

        except Exception as e:
            safe_print(f"ERROR: [ExportService] Failed to export Excel: {e}")
            return None

    def export_to_csv(self, data: list[dict[str, Any]], filename: str | None = None) -> str | None:
        """تصدير البيانات إلى CSV"""
        if not data:
            safe_print("WARNING: [ExportService] No data to export")
            return None

        try:
            # إنشاء اسم الملف
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"export_{timestamp}.csv"

            if not filename.endswith('.csv'):
                filename += '.csv'

            filepath = os.path.join(self.export_folder, filename)

            # كتابة CSV
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                if data:
                    fieldnames = data[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)

            safe_print(f"INFO: [ExportService] CSV exported: {filepath}")
            return filepath

        except Exception as e:
            safe_print(f"ERROR: [ExportService] Failed to export CSV: {e}")
            return None

    def export_clients_to_excel(self, clients: list) -> str | None:
        """تصدير العملاء إلى Excel"""
        data = []
        for client in clients:
            data.append({
                'الاسم': client.name,
                'الشركة': client.company_name or '',
                'الهاتف': client.phone or '',
                'البريد الإلكتروني': client.email or '',
                'العنوان': client.address or '',
                'الدولة': client.country or '',
                'نوع العميل': client.client_type.value if hasattr(client.client_type, 'value') else str(client.client_type),
                'مجال العمل': client.work_field or '',
                'الرقم الضريبي': client.vat_number or '',
                'الحالة': client.status.value if hasattr(client.status, 'value') else str(client.status)
            })

        return self.export_to_excel(data, "clients_export.xlsx", "العملاء")

    def import_clients_from_excel(self, filepath: str) -> tuple[list[dict], list[str]]:
        """
        استيراد العملاء من ملف Excel

        Returns:
            tuple: (قائمة العملاء المستوردة, قائمة الأخطاء)
        """
        if not PANDAS_AVAILABLE:
            return [], ["pandas غير متوفر. قم بتثبيته: pip install pandas openpyxl"]

        try:
            # قراءة ملف Excel
            df = pd.read_excel(filepath)

            clients_data = []
            errors = []

            # التحقق من الأعمدة المطلوبة
            required_columns = ['الاسم']
            for col in required_columns:
                if col not in df.columns:
                    errors.append(f"العمود المطلوب '{col}' غير موجود في الملف")
                    return [], errors

            # معالجة كل صف
            for index, row in df.iterrows():
                try:
                    # التحقق من وجود الاسم
                    if pd.isna(row.get('الاسم')) or not str(row.get('الاسم')).strip():
                        errors.append(f"الصف {index + 2}: الاسم مطلوب")
                        continue

                    client_dict = {
                        'name': str(row.get('الاسم', '')).strip(),
                        'company_name': str(row.get('الشركة', '')) if not pd.isna(row.get('الشركة')) else None,
                        'phone': str(row.get('الهاتف', '')) if not pd.isna(row.get('الهاتف')) else None,
                        'email': str(row.get('البريد الإلكتروني', '')) if not pd.isna(row.get('البريد الإلكتروني')) else None,
                        'address': str(row.get('العنوان', '')) if not pd.isna(row.get('العنوان')) else None,
                        'country': str(row.get('الدولة', '')) if not pd.isna(row.get('الدولة')) else None,
                        'client_type': str(row.get('نوع العميل', 'فرد')) if not pd.isna(row.get('نوع العميل')) else 'فرد',
                        'work_field': str(row.get('مجال العمل', '')) if not pd.isna(row.get('مجال العمل')) else None,
                        'vat_number': str(row.get('الرقم الضريبي', '')) if not pd.isna(row.get('الرقم الضريبي')) else None,
                        'status': 'نشط'  # افتراضياً نشط
                    }

                    clients_data.append(client_dict)

                except Exception as e:
                    errors.append(f"الصف {index + 2}: خطأ في المعالجة - {str(e)}")

            return clients_data, errors

        except Exception as e:
            return [], [f"خطأ في قراءة الملف: {str(e)}"]

    def export_projects_to_excel(self, projects: list) -> str | None:
        """تصدير المشاريع إلى Excel"""
        data = []
        for project in projects:
            data.append({
                'اسم المشروع': project.name,
                'العميل': project.client_id or '',
                'الحالة': project.status.value if hasattr(project.status, 'value') else str(project.status),
                'تاريخ البدء': project.start_date.strftime('%Y-%m-%d') if project.start_date else '',
                'تاريخ الانتهاء': project.end_date.strftime('%Y-%m-%d') if project.end_date else '',
                'المبلغ الإجمالي': project.total_amount or 0,
                'العملة': project.currency.value if hasattr(project.currency, 'value') else str(project.currency),
                'الوصف': project.description or ''
            })

        return self.export_to_excel(data, "projects_export.xlsx", "المشاريع")

    def export_expenses_to_excel(self, expenses: list) -> str | None:
        """تصدير المصروفات إلى Excel"""
        data = []
        for expense in expenses:
            data.append({
                'التاريخ': expense.date.strftime('%Y-%m-%d') if expense.date else '',
                'الفئة': expense.category or '',
                'المبلغ': expense.amount or 0,
                'الوصف': expense.description or '',
                'المشروع': expense.project_id or '',
                'حساب المصروف': expense.account_id or '',
                'حساب الدفع': expense.payment_account_id or ''
            })

        return self.export_to_excel(data, "expenses_export.xlsx", "المصروفات")

    def export_accounts_to_excel(self, accounts: list) -> str | None:
        """تصدير الحسابات إلى Excel"""
        data = []
        for account in accounts:
            data.append({
                'الكود': account.code or '',
                'الاسم': account.name or '',
                'النوع': account.type.value if hasattr(account.type, 'value') else str(account.type),
                'الحساب الأب': account.parent_code or '',
                'الرصيد': account.balance or 0,
                'العملة': account.currency.value if hasattr(account.currency, 'value') else str(account.currency),
                'الحالة': account.status.value if hasattr(account.status, 'value') else str(account.status),
                'الوصف': account.description or ''
            })

        return self.export_to_excel(data, "accounts_export.xlsx", "الحسابات")

    @staticmethod
    def open_file(filepath: str):
        """فتح الملف في البرنامج الافتراضي"""
        try:
            if platform.system() == 'Windows':
                os.startfile(filepath)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', filepath])
            else:  # Linux
                subprocess.run(['xdg-open', filepath])

            safe_print(f"INFO: [ExportService] Opened file: {filepath}")
        except Exception as e:
            safe_print(f"ERROR: [ExportService] Failed to open file: {e}")

    def get_export_folder(self) -> str:
        """الحصول على مجلد التصدير"""
        return str(os.path.abspath(self.export_folder))
