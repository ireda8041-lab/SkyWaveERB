# الملف: core/schemas.py

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClientStatus(str, Enum):
    ACTIVE = "نشط"
    ARCHIVED = "مؤرشف"

class ServiceStatus(str, Enum):
    ACTIVE = "نشط"
    ARCHIVED = "مؤرشف"

class AccountType(str, Enum):
    """ أنواع الحسابات الرئيسية في شجرة الحسابات """
    ASSET = "أصول"
    CASH = "أصول نقدية"
    LIABILITY = "خصوم"
    EQUITY = "حقوق ملكية"
    REVENUE = "إيرادات"
    EXPENSE = "مصروفات"


class AccountStatus(str, Enum):
    """ حالات الحساب داخل شجرة الحسابات """
    ACTIVE = "نشط"
    ARCHIVED = "مؤرشف"

class CurrencyCode(str, Enum):
    """ العملات المدعومة - يمكن إضافة المزيد """
    EGP = "EGP"
    USD = "USD"
    SAR = "SAR"
    AED = "AED"

class InvoiceStatus(str, Enum):
    """ حالات الفاتورة """
    DRAFT = "مسودة"
    SENT = "مرسلة"
    PAID = "مدفوعة"
    PARTIAL = "مدفوعة جزئياً"
    VOID = "ملغاة"

class ProjectStatus(str, Enum):
    """ حالات المشروع """
    PLANNING = "تخطيط"
    ACTIVE = "نشط"
    COMPLETED = "مكتمل"
    ON_HOLD = "معلق"
    ARCHIVED = "مؤرشف"

# --- هياكل البيانات الأساسية (Schemas) ---

class BaseSchema(BaseModel):
    """
    نموذج أساسي للمشاركة
    - هنستخدمه عشان نضمن إن كل حاجة ليها تاريخ إنشاء وتعديل
    - الـ 'Field(default_factory=datetime.now)' بتخلي التاريخ يتسجل أوتوماتيك
    """
    id: int | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    last_modified: datetime = Field(default_factory=datetime.now)

    # الحقول الخاصة بالمزامنة (دي مهمة جداً)
    mongo_id: str | None = Field(default=None, alias="_mongo_id")
    sync_status: str = Field(default="new_offline") # (new_offline, synced, modified_offline)

    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)

    @property
    def _mongo_id(self) -> str | None:
        return self.mongo_id

    @_mongo_id.setter
    def _mongo_id(self, value: str | None) -> None:
        self.mongo_id = value


class Account(BaseSchema):
    """
    نموذج شجرة الحسابات (من collection 'accounts')
    ده اللي هيشغل المحاسبة الأوتوماتيك
    """
    name: str
    code: str  # كود الحساب (مثلاً: 1010) - يجب أن يكون فريداً
    type: AccountType # نوع الحساب (أصول، إيرادات...)
    parent_code: str | None = None # كود الحساب الأب (للشجرة الهرمية)
    parent_id: str | None = None # عشان نعمل شجرة (حساب أب) - للتوافق مع الكود القديم
    is_group: bool = False # هل هذا حساب مجموعة (له أطفال) أم حساب نهائي
    balance: float = 0.0 # الرصيد المحسوب (من قيود اليومية)
    debit_total: float = 0.0 # إجمالي المدين
    credit_total: float = 0.0 # إجمالي الدائن
    currency: CurrencyCode | None = CurrencyCode.EGP  # العملة
    description: str | None = None  # وصف الحساب
    status: AccountStatus = AccountStatus.ACTIVE

    def model_post_init(self, __context: Any) -> None:
        """مزامنة parent_code و parent_id بعد إنشاء الكائن"""
        # إذا كان parent_id موجود و parent_code فارغ، انسخ القيمة
        if self.parent_id and not self.parent_code:
            self.parent_code = self.parent_id
        # إذا كان parent_code موجود و parent_id فارغ، انسخ القيمة
        elif self.parent_code and not self.parent_id:
            self.parent_id = self.parent_code

    def add_debit(self, amount: float):
        """إضافة مبلغ مدين"""
        self.debit_total += amount
        self._recalculate_balance()

    def add_credit(self, amount: float):
        """إضافة مبلغ دائن"""
        self.credit_total += amount
        self._recalculate_balance()

    def _recalculate_balance(self):
        """إعادة حساب الرصيد بناءً على طبيعة الحساب"""
        if self.type in [AccountType.ASSET, AccountType.CASH, AccountType.EXPENSE]:
            # الأصول والمصروفات: الرصيد = المدين - الدائن
            self.balance = self.debit_total - self.credit_total
        else:
            # الخصوم والإيرادات وحقوق الملكية: الرصيد = الدائن - المدين
            self.balance = self.credit_total - self.debit_total

class Client(BaseSchema):
    """ نموذج العميل (من collection 'clients') """
    name: str
    company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    country: str | None = None # (مهم لشركة Sky Wave عشان شغلهم في EGY/KSA/UAE)
    vat_number: str | None = None # الرقم الضريبي
    status: ClientStatus = ClientStatus.ACTIVE
    client_type: str | None = "فرد"
    work_field: str | None = None
    logo_path: str | None = None  # مسار الصورة المحلي (للتوافق القديم)
    logo_data: str | None = None  # بيانات الصورة بصيغة base64 (للمزامنة بين الأجهزة)
    client_notes: str | None = None

class Currency(BaseSchema):
    """ نموذج العملات (من collection 'currencies') """
    code: CurrencyCode  # EGP, USD... - يجب أن يكون فريداً
    name: str # (جنيه مصري، دولار أمريكي)
    exchange_rate: float = 1.0 # سعر الصرف مقابل العملة الأساسية (مثلاً EGP)

class Service(BaseSchema):
    """
    نموذج الخدمات والباقات (من collection 'services')
    دي الخدمات اللي في ملف الشركة (SEO, Ads, Starter Package...)
    """
    name: str
    description: str | None = None
    default_price: float
    category: str | None = "General" # (مثلاً: SEO, Web Dev, Packages)
    status: ServiceStatus = ServiceStatus.ACTIVE

class ProjectItem(BaseModel):
    """نموذج بند المشروع مع دعم تحليل الربحية"""
    service_id: str
    description: str
    quantity: float
    unit_price: float
    discount_rate: float = 0.0  # نسبة الخصم على البند (%)
    discount_amount: float = 0.0  # مبلغ الخصم على البند
    total: float  # الإجمالي بعد الخصم
    # ⚡ Enterprise: تحليل الربحية
    estimated_cost: float = 0.0  # التكلفة التقديرية للبند


# ==================== نظام الدفعات المرحلية (Milestones) ====================
class MilestoneStatus(str, Enum):
    """حالات الدفعة المرحلية"""
    PENDING = "قيد الانتظار"
    PAID = "مدفوعة"
    OVERDUE = "متأخرة"


class ProjectMilestone(BaseModel):
    """
    نموذج الدفعة المرحلية (Milestone)
    يستخدم لتقسيم مدفوعات المشروع على مراحل
    """
    id: str | None = None
    name: str  # مثلاً: دفعة التعاقد، دفعة التسليم
    percentage: float = 0.0  # نسبة مئوية من إجمالي المشروع
    amount: float = 0.0  # قيمة نقدية
    due_date: datetime | None = None  # تاريخ الاستحقاق
    status: MilestoneStatus = MilestoneStatus.PENDING
    invoice_id: str | None = None  # ربط بالفاتورة
    paid_date: datetime | None = None  # تاريخ الدفع الفعلي
    notes: str | None = None


# ==================== نظام العقود (Retainer) ====================
class RenewalCycle(str, Enum):
    """دورة التجديد للعقود"""
    MONTHLY = "شهري"
    QUARTERLY = "ربع سنوي"
    YEARLY = "سنوي"


class ContractType(str, Enum):
    """نوع العقد"""
    ONE_TIME = "مرة واحدة"
    RETAINER = "اشتراك/عقد"


class Project(BaseSchema):
    """
    🏢 نموذج المشروع Enterprise Level
    يدعم: التكويد الذكي، تحليل الربحية، مراكز التكلفة، العقود المتكررة
    """
    name: str  # يجب أن يكون فريداً
    client_id: str
    status: ProjectStatus = ProjectStatus.ACTIVE
    status_manually_set: bool = False  # ⚡ هل الحالة تم تعيينها يدوياً؟
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    items: list[ProjectItem] = Field(default_factory=list)

    subtotal: float = 0.0
    discount_rate: float = 0.0
    discount_amount: float = 0.0
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    total_amount: float = 0.0

    currency: CurrencyCode = CurrencyCode.EGP
    project_notes: str | None = None
    invoice_number: str | None = None  # ⚡ رقم الفاتورة الثابت

    # ==================== Enterprise Features ====================
    # 1. Smart Coding
    project_code: str | None = None  # كود المشروع الذكي (e.g., 2025-SEO-SKY-001)
    sequence_number: int = 0  # الرقم التسلسلي

    # 2. Cost Center Mapping
    cost_center_id: str | None = None  # ربط بمركز التكلفة (حساب في شجرة الحسابات)

    # 3. Retainer Logic (العقود المتكررة)
    contract_type: ContractType | None = ContractType.ONE_TIME
    is_retainer: bool = False  # هل هو عقد متكرر؟
    renewal_cycle: RenewalCycle | None = None  # دورة التجديد
    next_renewal_date: datetime | None = None  # تاريخ التجديد القادم

    # 4. Payment Milestones (الدفعات المرحلية) - يقبل None ويحولها لقائمة فارغة
    milestones: list[ProjectMilestone] = Field(default_factory=list)

    # 5. Profitability Analysis
    total_estimated_cost: float = 0.0  # إجمالي التكلفة التقديرية
    estimated_profit: float = 0.0  # الربح المتوقع
    profit_margin: float = 0.0  # هامش الربح %

    # 6. Project Manager
    project_manager_id: str | None = None  # مدير المشروع

    # ⚡ Pydantic v2 Validator لتحويل None إلى قائمة فارغة
    @field_validator('milestones', 'items', mode='before')
    @classmethod
    def convert_none_to_list(cls, v):
        """تحويل None إلى قائمة فارغة"""
        if v is None:
            return []
        return v

class Expense(BaseSchema):
    """ نموذج المصروفات (من collection 'expenses') """
    date: datetime
    category: str # (إيجار، مرتبات، إعلانات مدفوعة، اشتراكات برامج)
    amount: float
    description: str | None = None
    account_id: str # ربط بحساب المصروف في شجرة الحسابات
    payment_account_id: str | None = None # الحساب اللي اتدفع منه (خزينة، بنك، فودافون كاش، إلخ)
    project_id: str | None = None

class User(BaseSchema):
    """ نموذج المستخدمين (من collection 'users') """
    username: str  # يجب أن يكون فريداً
    hashed_password: str # مش هنخزن الباسورد أبداً كنص عادي
    full_name: str
    role: str # (مثلاً: admin, user)

# --- الهياكل المعقدة (الفواتير والقيود) ---

class InvoiceItem(BaseModel):
    """ نموذج البند الواحد جوه الفاتورة """
    service_id: str
    description: str # (هييجي أوتوماتيك من الخدمة بس نقدر نعدله)
    quantity: float
    unit_price: float
    discount_rate: float = 0.0  # نسبة الخصم على البند (%)
    discount_amount: float = 0.0  # مبلغ الخصم على البند
    total: float # الإجمالي بعد الخصم

class Invoice(BaseSchema):
    """ نموذج الفاتورة (من collection 'invoices') """
    invoice_number: str  # رقم الفاتورة - يجب أن يكون فريداً
    client_id: str
    project_id: str | None = None
    issue_date: datetime
    due_date: datetime
    items: list[InvoiceItem]
    subtotal: float

    discount_rate: float = 0.0 # نسبة الخصم
    discount_amount: float = 0.0 # مبلغ الخصم

    tax_rate: float = 0.0 # نسبة الضريبة
    tax_amount: float = 0.0
    total_amount: float
    amount_paid: float = 0.0
    status: InvoiceStatus = InvoiceStatus.DRAFT
    currency: CurrencyCode = CurrencyCode.EGP
    notes: str | None = None

class JournalEntryLine(BaseModel):
    """
    نموذج السطر الواحد في قيد اليومية (مدين أو دائن)
    ده اللي هيعمله الروبوت المحاسبي لوحده
    """
    account_id: str # ID الحساب من 'accounts'
    account_code: str | None = None # كود الحساب (للبحث السريع)
    account_name: str | None = None # اسم الحساب (للعرض)
    debit: float = 0.0  # مدين
    credit: float = 0.0 # دائن
    description: str | None = None

    def validate_entry(self) -> bool:
        """التحقق من صحة السطر"""
        # لا يمكن أن يكون السطر مدين ودائن في نفس الوقت
        if self.debit > 0 and self.credit > 0:
            return False
        # يجب أن يكون أحدهما على الأقل أكبر من صفر
        if self.debit == 0 and self.credit == 0:
            return False
        return True

class JournalEntry(BaseSchema):
    """ نموذج قيد اليومية (من collection 'journal_entries') """
    date: datetime
    description: str # (مثلاً: "إثبات فاتورة رقم 123 للعميل س")
    lines: list[JournalEntryLine]
    reference_type: str | None = None # نوع المرجع (invoice, expense, payment)
    reference_id: str | None = None # معرف المرجع
    related_document_id: str | None = None # (ID الفاتورة أو المصروف اللي عمل القيد) - للتوافق
    entry_number: str | None = None # رقم القيد
    is_balanced: bool = True # هل القيد متوازن
    total_debit: float = 0.0 # إجمالي المدين
    total_credit: float = 0.0 # إجمالي الدائن

    def calculate_totals(self):
        """حساب إجماليات القيد"""
        self.total_debit = sum(line.debit for line in self.lines)
        self.total_credit = sum(line.credit for line in self.lines)
        self.is_balanced = abs(self.total_debit - self.total_credit) < 0.01

    def validate_entry(self) -> tuple[bool, str]:
        """التحقق من صحة القيد"""
        if not self.lines:
            return False, "القيد يجب أن يحتوي على أسطر"

        if len(self.lines) < 2:
            return False, "القيد يجب أن يحتوي على سطرين على الأقل"

        for line in self.lines:
            if not line.validate_entry():
                return False, f"سطر غير صحيح: {line.description}"

        self.calculate_totals()
        if not self.is_balanced:
            return False, f"القيد غير متوازن: مدين={self.total_debit}, دائن={self.total_credit}"

        return True, "القيد صحيح"

class Payment(BaseSchema):
    """
    نموذج الدفعة (التحصيل).
    ده بيمثل أي فلوس استلمناها من العميل.
    """
    project_id: str   # المشروع اللي الدفعة دي تابعة ليه
    client_id: str    # العميل اللي دفع
    date: datetime    # تاريخ التحصيل
    amount: float     # المبلغ اللي اندفع
    account_id: str   # كود الحساب اللي استلم الفلوس (مثلاً: 1110 البنك)
    method: str | None = "Bank Transfer" # (طريقة الدفع: تحويل، كاش، ...)

class SyncOperation(str, Enum):
    """ أنواع عمليات المزامنة """
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

class SyncPriority(str, Enum):
    """ أولويات المزامنة """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class SyncStatus(str, Enum):
    """ حالات المزامنة """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncQueueItem(BaseSchema):
    """
    نموذج عنصر في قائمة انتظار المزامنة
    يستخدم لتتبع العمليات التي تحتاج للمزامنة مع MongoDB
    """
    entity_type: str  # نوع الكيان (clients, projects, expenses, etc.)
    entity_id: str    # معرف الكيان المحلي
    operation: SyncOperation  # نوع العملية (create, update, delete)
    priority: SyncPriority = SyncPriority.MEDIUM  # أولوية المزامنة
    status: SyncStatus = SyncStatus.PENDING  # حالة المزامنة
    retry_count: int = 0  # عدد محاولات إعادة المزامنة
    max_retries: int = 3  # الحد الأقصى لمحاولات إعادة المزامنة
    data: dict[str, Any] | None = None  # البيانات المراد مزامنتها
    error_message: str | None = None  # رسالة الخطأ في حالة الفشل
    last_attempt: datetime | None = None  # وقت آخر محاولة

# تم تحميل schemas.py بنجاح

class NotificationType(str, Enum):
    """ أنواع الإشعارات """
    INFO = "معلومة"
    WARNING = "تحذير"
    ERROR = "خطأ"
    SUCCESS = "نجاح"
    PROJECT_DUE = "موعد_استحقاق_مشروع"
    PAYMENT_RECEIVED = "دفعة_مستلمة"
    SYNC_FAILED = "فشل_المزامنة"

class NotificationPriority(str, Enum):
    """ أولويات الإشعارات """
    LOW = "منخفضة"
    MEDIUM = "متوسطة"
    HIGH = "عالية"
    URGENT = "عاجلة"

class Notification(BaseSchema):
    """
    نموذج الإشعار
    يستخدم لإشعار المستخدم بالأحداث المهمة
    """
    title: str  # عنوان الإشعار
    message: str  # نص الإشعار
    type: NotificationType  # نوع الإشعار
    priority: NotificationPriority = NotificationPriority.MEDIUM  # الأولوية
    is_read: bool = False  # هل تم قراءة الإشعار
    related_entity_type: str | None = None  # نوع الكيان المرتبط (projects, clients, etc.)
    related_entity_id: str | None = None  # معرف الكيان المرتبط
    action_url: str | None = None  # رابط الإجراء (اختياري)
    expires_at: datetime | None = None  # تاريخ انتهاء الصلاحية (للإشعارات المؤقتة)



# ==================== نظام المهام (Tasks) ====================

class TaskPriority(str, Enum):
    """أولوية المهمة"""
    LOW = "منخفضة"
    MEDIUM = "متوسطة"
    HIGH = "عالية"
    URGENT = "عاجلة"


class TaskStatus(str, Enum):
    """حالة المهمة"""
    TODO = "قيد الانتظار"
    IN_PROGRESS = "قيد التنفيذ"
    COMPLETED = "مكتملة"
    CANCELLED = "ملغاة"


class TaskCategory(str, Enum):
    """فئة المهمة"""
    GENERAL = "عامة"
    PROJECT = "مشروع"
    CLIENT = "عميل"
    PAYMENT = "دفعة"
    MEETING = "اجتماع"
    FOLLOW_UP = "متابعة"
    DEADLINE = "موعد نهائي"


# ==================== نماذج لوحة التحكم المحسّنة (Enhanced Dashboard) ====================

class KPIData(BaseModel):
    """
    نموذج بيانات مؤشر الأداء الرئيسي (KPI)
    يستخدم لعرض KPIs مع مؤشرات الاتجاه في لوحة التحكم
    Requirements: 1.4, 1.5, 1.6, 1.7
    """
    name: str  # اسم المؤشر (مثل "إجمالي الإيرادات")
    current_value: float  # القيمة الحالية
    previous_value: float | None = None  # القيمة السابقة للمقارنة

    @property
    def change_percentage(self) -> float:
        """
        نسبة التغير بين القيمة الحالية والسابقة
        Returns: النسبة المئوية للتغير
        Validates: Requirements 1.4
        """
        if self.previous_value is None or self.previous_value == 0:
            return 0.0
        return ((self.current_value - self.previous_value) / self.previous_value) * 100

    @property
    def trend_direction(self) -> str:
        """
        اتجاه التغير: up (أخضر), down (أحمر), neutral (محايد)
        Validates: Requirements 1.5, 1.6, 1.7
        """
        if self.previous_value is None:
            return "neutral"
        if self.current_value > self.previous_value:
            return "up"
        elif self.current_value < self.previous_value:
            return "down"
        return "neutral"


class CashFlowEntry(BaseModel):
    """
    نموذج إدخال التدفق النقدي
    يستخدم لتمثيل التدفقات النقدية الداخلة والخارجة في فترة زمنية
    Requirements: 2.5
    """
    date: datetime  # تاريخ الإدخال
    inflow: float = 0.0  # التدفق الداخل (الدفعات المحصلة)
    outflow: float = 0.0  # التدفق الخارج (المصروفات)

    @property
    def net_flow(self) -> float:
        """
        صافي التدفق النقدي = التدفق الداخل - التدفق الخارج
        Validates: Requirements 2.5
        """
        return self.inflow - self.outflow


class DashboardSettings(BaseModel):
    """
    إعدادات لوحة التحكم
    يستخدم لحفظ تفضيلات المستخدم للوحة التحكم
    Requirements: 4.4
    """
    auto_refresh_enabled: bool = True  # هل التحديث التلقائي مفعل
    auto_refresh_interval: int = 30  # فترة التحديث بالثواني
    selected_period: str = "this_month"  # الفترة المحددة (today, this_week, this_month, this_year, custom)
    custom_start_date: datetime | None = None  # تاريخ البداية للفترة المخصصة
    custom_end_date: datetime | None = None  # تاريخ النهاية للفترة المخصصة


class Task(BaseSchema):
    """
    نموذج المهمة (من collection 'tasks')
    يستخدم لإدارة المهام والتذكيرات
    """
    title: str  # عنوان المهمة
    description: str | None = None  # وصف المهمة
    priority: TaskPriority = TaskPriority.MEDIUM  # الأولوية
    status: TaskStatus = TaskStatus.TODO  # الحالة
    category: TaskCategory = TaskCategory.GENERAL  # الفئة
    due_date: datetime | None = None  # تاريخ الاستحقاق
    due_time: str | None = None  # وقت الاستحقاق (HH:MM)
    completed_at: datetime | None = None  # تاريخ الإكمال
    related_project_id: str | None = None  # معرف المشروع المرتبط
    related_client_id: str | None = None  # معرف العميل المرتبط
    tags: list[str] = Field(default_factory=list)  # الوسوم
    reminder: bool = False  # هل التذكير مفعل
    reminder_minutes: int = 30  # دقائق قبل الموعد للتذكير
    assigned_to: str | None = None  # المستخدم المسؤول
