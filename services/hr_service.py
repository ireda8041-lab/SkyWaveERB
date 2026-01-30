# الملف: services/hr_service.py
"""
🏢 خدمة الموارد البشرية (HR Service) - Production Grade
========================================================
نظام متكامل لإدارة:
- الموظفين
- الحضور والانصراف
- الإجازات
- السلف
- المرتبات
"""

from datetime import datetime, timedelta
from typing import Any

from core.event_bus import EventBus
from core.logger import get_logger
from core.repository import Repository

try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass

logger = get_logger(__name__)


class HRService:
    """خدمة الموارد البشرية"""

    def __init__(self, repository: Repository, event_bus: EventBus = None):
        self.repo = repository
        self.bus = event_bus
        logger.info("[HRService] ✅ خدمة الموارد البشرية جاهزة")

    # ==================== الموظفين ====================
    def get_all_employees(self) -> list[dict]:
        """جلب جميع الموظفين"""
        return self.repo.get_all_employees()

    def get_active_employees(self) -> list[dict]:
        """جلب الموظفين النشطين"""
        return self.repo.get_active_employees()

    def get_employee(self, employee_id: int) -> dict | None:
        """جلب موظف بالمعرف"""
        return self.repo.get_employee_by_id(employee_id)

    def create_employee(self, data: dict) -> dict | None:
        """إنشاء موظف جديد"""
        result = self.repo.create_employee(data)
        if result and self.bus:
            self.bus.publish("EMPLOYEE_CREATED", {"employee": result})
        return result

    def update_employee(self, employee_id: int, data: dict) -> dict | None:
        """تحديث بيانات موظف"""
        result = self.repo.update_employee(employee_id, data)
        if result and self.bus:
            self.bus.publish("EMPLOYEE_UPDATED", {"employee": result})
        return result

    def delete_employee(self, employee_id: int) -> bool:
        """حذف موظف"""
        result = self.repo.delete_employee(employee_id)
        if result and self.bus:
            self.bus.publish("EMPLOYEE_DELETED", {"employee_id": employee_id})
        return result

    # ==================== الحضور والانصراف ====================
    def get_employee_attendance(self, employee_id: int, month: str = None) -> list[dict]:
        """جلب سجل حضور موظف"""
        return self.repo.get_employee_attendance(employee_id, month)

    def get_today_attendance(self) -> list[dict]:
        """جلب حضور اليوم"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.repo.get_all_attendance_for_date(today)

    def get_attendance_for_date(self, date: str) -> list[dict]:
        """جلب حضور يوم معين"""
        return self.repo.get_all_attendance_for_date(date)

    def check_in(self, employee_id: int, time: str = None) -> dict | None:
        """تسجيل حضور"""
        now = datetime.now()
        data = {
            "employee_id": employee_id,
            "date": now.strftime("%Y-%m-%d"),
            "check_in_time": time or now.strftime("%H:%M"),
            "status": "حاضر"
        }
        # تحقق من التأخير (بعد 9:00 صباحاً)
        check_time = datetime.strptime(data["check_in_time"], "%H:%M")
        if check_time.hour >= 9 and check_time.minute > 15:
            data["status"] = "متأخر"
        
        result = self.repo.record_attendance(data)
        if result and self.bus:
            self.bus.publish("ATTENDANCE_RECORDED", {"attendance": result})
        return result

    def check_out(self, employee_id: int, time: str = None) -> dict | None:
        """تسجيل انصراف"""
        now = datetime.now()
        check_out_time = time or now.strftime("%H:%M")
        
        # جلب سجل اليوم لحساب ساعات العمل
        today = now.strftime("%Y-%m-%d")
        attendance = self.repo.get_employee_attendance(employee_id)
        today_record = next((a for a in attendance if a["date"].startswith(today)), None)
        
        work_hours = 0
        overtime_hours = 0
        if today_record and today_record.get("check_in_time"):
            try:
                check_in = datetime.strptime(today_record["check_in_time"], "%H:%M")
                check_out = datetime.strptime(check_out_time, "%H:%M")
                diff = (check_out - check_in).seconds / 3600
                work_hours = min(diff, 8)  # الحد الأقصى 8 ساعات عادية
                overtime_hours = max(0, diff - 8)
            except ValueError:
                pass
        
        data = {
            "employee_id": employee_id,
            "date": today,
            "check_out_time": check_out_time,
            "work_hours": round(work_hours, 2),
            "overtime_hours": round(overtime_hours, 2),
        }
        
        # تحقق من الانصراف المبكر (قبل 5:00 مساءً)
        check_time = datetime.strptime(check_out_time, "%H:%M")
        if check_time.hour < 17:
            data["status"] = "انصراف مبكر"
        
        return self.repo.record_attendance(data)

    def record_absence(self, employee_id: int, date: str, reason: str = None) -> dict | None:
        """تسجيل غياب"""
        data = {
            "employee_id": employee_id,
            "date": date,
            "status": "غائب",
            "notes": reason
        }
        return self.repo.record_attendance(data)

    # ==================== الإجازات ====================
    def get_all_leaves(self, status: str = None) -> list[dict]:
        """جلب جميع طلبات الإجازات"""
        return self.repo.get_employee_leaves(status=status)

    def get_employee_leaves(self, employee_id: int) -> list[dict]:
        """جلب إجازات موظف"""
        return self.repo.get_employee_leaves(employee_id=employee_id)

    def get_pending_leaves(self) -> list[dict]:
        """جلب طلبات الإجازات المعلقة"""
        return self.repo.get_employee_leaves(status="معلق")

    def request_leave(self, data: dict) -> dict | None:
        """تقديم طلب إجازة"""
        # حساب عدد الأيام
        try:
            start = datetime.strptime(data["start_date"], "%Y-%m-%d")
            end = datetime.strptime(data["end_date"], "%Y-%m-%d")
            data["days_count"] = (end - start).days + 1
        except (ValueError, KeyError):
            data["days_count"] = 1
        
        result = self.repo.create_leave_request(data)
        if result and self.bus:
            self.bus.publish("LEAVE_REQUESTED", {"leave": result})
        return result

    def approve_leave(self, leave_id: int, approved_by: str) -> bool:
        """الموافقة على طلب إجازة"""
        result = self.repo.update_leave_status(leave_id, "موافق عليه", approved_by)
        if result and self.bus:
            self.bus.publish("LEAVE_APPROVED", {"leave_id": leave_id})
        return result

    def reject_leave(self, leave_id: int, approved_by: str) -> bool:
        """رفض طلب إجازة"""
        result = self.repo.update_leave_status(leave_id, "مرفوض", approved_by)
        if result and self.bus:
            self.bus.publish("LEAVE_REJECTED", {"leave_id": leave_id})
        return result

    # ==================== السلف ====================
    def get_all_loans(self, status: str = None) -> list[dict]:
        """جلب جميع السلف"""
        return self.repo.get_employee_loans(status=status)

    def get_employee_loans(self, employee_id: int) -> list[dict]:
        """جلب سلف موظف"""
        return self.repo.get_employee_loans(employee_id=employee_id)

    def get_active_loans(self) -> list[dict]:
        """جلب السلف النشطة"""
        return self.repo.get_employee_loans(status="نشط")

    def create_loan(self, data: dict) -> dict | None:
        """إنشاء سلفة جديدة"""
        result = self.repo.create_loan(data)
        if result and self.bus:
            self.bus.publish("LOAN_CREATED", {"loan": result})
        return result

    def pay_loan_installment(self, loan_id: int, amount: float) -> bool:
        """سداد قسط من السلفة"""
        loans = self.repo.get_employee_loans()
        loan = next((l for l in loans if l["id"] == loan_id), None)
        if not loan:
            return False
        
        new_remaining = max(0, loan["remaining_amount"] - amount)
        status = "مسدد" if new_remaining == 0 else "نشط"
        
        return self.repo.update_loan(loan_id, {
            "remaining_amount": new_remaining,
            "monthly_deduction": loan["monthly_deduction"],
            "status": status,
            "notes": loan.get("notes")
        })

    # ==================== المرتبات ====================
    def get_salaries(self, month: str = None) -> list[dict]:
        """جلب المرتبات"""
        return self.repo.get_employee_salaries(month=month)

    def get_employee_salaries(self, employee_id: int) -> list[dict]:
        """جلب مرتبات موظف"""
        return self.repo.get_employee_salaries(employee_id=employee_id)

    def calculate_salary(self, employee_id: int, month: str) -> dict | None:
        """حساب راتب موظف لشهر معين"""
        employee = self.repo.get_employee_by_id(employee_id)
        if not employee:
            return None
        
        basic_salary = employee.get("salary", 0)
        
        # جلب السلف النشطة للموظف
        loans = self.repo.get_employee_loans(employee_id=employee_id, status="نشط")
        loan_deductions = sum(l.get("monthly_deduction", 0) for l in loans)
        
        # جلب سجل الحضور للشهر
        attendance = self.repo.get_employee_attendance(employee_id, month)
        overtime_hours = sum(a.get("overtime_hours", 0) for a in attendance)
        overtime_rate = basic_salary / 30 / 8 * 1.5  # سعر الساعة الإضافية
        overtime_amount = overtime_hours * overtime_rate
        
        # حساب الخصومات
        absent_days = sum(1 for a in attendance if a.get("status") == "غائب")
        daily_rate = basic_salary / 30
        absence_deduction = absent_days * daily_rate
        
        data = {
            "employee_id": employee_id,
            "month": month,
            "basic_salary": basic_salary,
            "allowances": 0,
            "bonuses": 0,
            "overtime_hours": overtime_hours,
            "overtime_rate": round(overtime_rate, 2),
            "overtime_amount": round(overtime_amount, 2),
            "loan_deductions": loan_deductions,
            "insurance_deduction": 0,
            "tax_deduction": 0,
            "other_deductions": round(absence_deduction, 2),
            "payment_status": "محسوب"
        }
        
        result = self.repo.create_or_update_salary(data)
        if result and self.bus:
            self.bus.publish("SALARY_CALCULATED", {"salary": result})
        return result

    def calculate_all_salaries(self, month: str) -> list[dict]:
        """حساب مرتبات جميع الموظفين النشطين"""
        employees = self.repo.get_active_employees()
        results = []
        for emp in employees:
            result = self.calculate_salary(emp["id"], month)
            if result:
                results.append(result)
        return results

    def pay_salary(self, salary_id: int, payment_method: str = "تحويل بنكي") -> bool:
        """صرف راتب"""
        payment_date = datetime.now().strftime("%Y-%m-%d")
        result = self.repo.update_salary_status(salary_id, "مدفوع", payment_date, payment_method)
        if result and self.bus:
            self.bus.publish("SALARY_PAID", {"salary_id": salary_id})
        return result

    # ==================== الإحصائيات ====================
    def get_statistics(self) -> dict:
        """جلب إحصائيات الموارد البشرية"""
        return self.repo.get_hr_statistics()

    def get_monthly_report(self, month: str) -> dict:
        """تقرير شهري للموارد البشرية"""
        salaries = self.repo.get_employee_salaries(month=month)
        
        total_gross = sum(s.get("gross_salary", 0) for s in salaries)
        total_net = sum(s.get("net_salary", 0) for s in salaries)
        total_deductions = sum(
            s.get("loan_deductions", 0) + s.get("insurance_deduction", 0) + 
            s.get("tax_deduction", 0) + s.get("other_deductions", 0)
            for s in salaries
        )
        
        paid_count = sum(1 for s in salaries if s.get("payment_status") == "مدفوع")
        pending_count = len(salaries) - paid_count
        
        return {
            "month": month,
            "employees_count": len(salaries),
            "total_gross": total_gross,
            "total_net": total_net,
            "total_deductions": total_deductions,
            "paid_count": paid_count,
            "pending_count": pending_count,
            "salaries": salaries
        }
