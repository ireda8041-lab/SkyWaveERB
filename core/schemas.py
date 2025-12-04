# الملف: core/schemas.py

from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional, Any, Dict

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
    id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
    last_modified: datetime = Field(default_factory=datetime.now)
    
    # الحقول الخاصة بالمزامنة (دي مهمة جداً)
    mongo_id: Optional[str] = Field(default=None, alias="_mongo_id")
    sync_status: str = Field(default="new_offline") # (new_offline, synced, modified_offline)

    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)

    @property
    def _mongo_id(self) -> Optional[str]:
        return self.mongo_id

    @_mongo_id.setter
    def _mongo_id(self, value: Optional[str]) -> None:
        self.mongo_id = value


class Account(BaseSchema):
    """ 
    نموذج شجرة الحسابات (من collection 'accounts')
    ده اللي هيشغل المحاسبة الأوتوماتيك
    """
    name: str
    code: str  # كود الحساب (مثلاً: 1010) - يجب أن يكون فريداً
    type: AccountType # نوع الحساب (أصول، إيرادات...)
    parent_code: Optional[str] = None # كود الحساب الأب (للشجرة الهرمية)
    parent_id: Optional[str] = None # عشان نعمل شجرة (حساب أب) - للتوافق مع الكود القديم
    is_group: bool = False # هل هذا حساب مجموعة (له أطفال) أم حساب نهائي
    balance: float = 0.0 # الرصيد المحسوب (من قيود اليومية)
    debit_total: float = 0.0 # إجمالي المدين
    credit_total: float = 0.0 # إجمالي الدائن
    currency: Optional[CurrencyCode] = CurrencyCode.EGP  # العملة
    description: Optional[str] = None  # وصف الحساب
    status: AccountStatus = AccountStatus.ACTIVE
    
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
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None # (مهم لشركة Sky Wave عشان شغلهم في EGY/KSA/UAE)
    vat_number: Optional[str] = None # الرقم الضريبي
    status: ClientStatus = ClientStatus.ACTIVE
    client_type: Optional[str] = "فرد"
    work_field: Optional[str] = None
    logo_path: Optional[str] = None
    client_notes: Optional[str] = None

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
    description: Optional[str] = None
    default_price: float
    category: Optional[str] = "General" # (مثلاً: SEO, Web Dev, Packages)
    status: ServiceStatus = ServiceStatus.ACTIVE

class ProjectItem(BaseModel):
    service_id: str
    description: str
    quantity: float
    unit_price: float
    discount_rate: float = 0.0  # نسبة الخصم على البند (%)
    discount_amount: float = 0.0  # مبلغ الخصم على البند
    total: float  # الإجمالي بعد الخصم


class Project(BaseSchema):
    """
    (معدل) نموذج المشروع (أصبح هو العقد المالي)
    """
    name: str  # يجب أن يكون فريداً
    client_id: str
    status: ProjectStatus = ProjectStatus.ACTIVE
    status_manually_set: bool = False  # ⚡ هل الحالة تم تعيينها يدوياً؟
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    items: List[ProjectItem] = Field(default_factory=list)

    subtotal: float = 0.0
    discount_rate: float = 0.0
    discount_amount: float = 0.0
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    total_amount: float = 0.0

    currency: CurrencyCode = CurrencyCode.EGP
    project_notes: Optional[str] = None

class Expense(BaseSchema):
    """ نموذج المصروفات (من collection 'expenses') """
    date: datetime
    category: str # (إيجار، مرتبات، إعلانات مدفوعة، اشتراكات برامج)
    amount: float
    description: Optional[str] = None
    account_id: str # ربط بحساب المصروف في شجرة الحسابات
    payment_account_id: Optional[str] = None # الحساب اللي اتدفع منه (خزينة، بنك، فودافون كاش، إلخ)
    project_id: Optional[str] = None

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
    project_id: Optional[str] = None
    issue_date: datetime
    due_date: datetime
    items: List[InvoiceItem]
    subtotal: float

    discount_rate: float = 0.0 # نسبة الخصم
    discount_amount: float = 0.0 # مبلغ الخصم

    tax_rate: float = 0.0 # نسبة الضريبة
    tax_amount: float = 0.0
    total_amount: float
    amount_paid: float = 0.0
    status: InvoiceStatus = InvoiceStatus.DRAFT
    currency: CurrencyCode = CurrencyCode.EGP
    notes: Optional[str] = None

class JournalEntryLine(BaseModel):
    """ 
    نموذج السطر الواحد في قيد اليومية (مدين أو دائن)
    ده اللي هيعمله الروبوت المحاسبي لوحده
    """
    account_id: str # ID الحساب من 'accounts'
    account_code: Optional[str] = None # كود الحساب (للبحث السريع)
    account_name: Optional[str] = None # اسم الحساب (للعرض)
    debit: float = 0.0  # مدين
    credit: float = 0.0 # دائن
    description: Optional[str] = None
    
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
    lines: List[JournalEntryLine]
    reference_type: Optional[str] = None # نوع المرجع (invoice, expense, payment)
    reference_id: Optional[str] = None # معرف المرجع
    related_document_id: Optional[str] = None # (ID الفاتورة أو المصروف اللي عمل القيد) - للتوافق
    entry_number: Optional[str] = None # رقم القيد
    is_balanced: bool = True # هل القيد متوازن
    total_debit: float = 0.0 # إجمالي المدين
    total_credit: float = 0.0 # إجمالي الدائن
    
    def calculate_totals(self):
        """حساب إجماليات القيد"""
        self.total_debit = sum(line.debit for line in self.lines)
        self.total_credit = sum(line.credit for line in self.lines)
        self.is_balanced = abs(self.total_debit - self.total_credit) < 0.01
    
    def validate(self) -> tuple[bool, str]:
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
    method: Optional[str] = "Bank Transfer" # (طريقة الدفع: تحويل، كاش، ...)

class QuotationStatus(str, Enum):
    """ حالات عرض السعر """
    DRAFT = "مسودة"
    SENT = "مُرسل"
    ACCEPTED = "مقبول"
    REJECTED = "مرفوض"

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


class QuotationItem(BaseModel):
    """ نموذج البند الواحد جوه عرض السعر. """
    service_id: str
    description: str
    quantity: float
    unit_price: float
    discount_rate: float = 0.0  # نسبة الخصم على البند (%)
    discount_amount: float = 0.0  # مبلغ الخصم على البند
    total: float  # الإجمالي بعد الخصم

class Quotation(BaseSchema):
    """ نموذج عرض السعر. """
    quote_number: str  # يجب أن يكون فريداً
    client_id: str
    project_id: Optional[str] = None
    issue_date: datetime
    expiry_date: datetime
    items: List[QuotationItem]
    subtotal: float
    discount_rate: float = 0.0
    discount_amount: float = 0.0
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    total_amount: float
    status: QuotationStatus = QuotationStatus.DRAFT
    currency: CurrencyCode = CurrencyCode.EGP
    notes: Optional[str] = None

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
    data: Optional[Dict[str, Any]] = None  # البيانات المراد مزامنتها
    error_message: Optional[str] = None  # رسالة الخطأ في حالة الفشل
    last_attempt: Optional[datetime] = None  # وقت آخر محاولة

# تم تحميل schemas.py بنجاح

class NotificationType(str, Enum):
    """ أنواع الإشعارات """
    INFO = "معلومة"
    WARNING = "تحذير"
    ERROR = "خطأ"
    SUCCESS = "نجاح"
    PROJECT_DUE = "موعد_استحقاق_مشروع"
    PAYMENT_RECEIVED = "دفعة_مستلمة"
    QUOTATION_EXPIRED = "عرض_سعر_منتهي"
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
    related_entity_type: Optional[str] = None  # نوع الكيان المرتبط (projects, clients, etc.)
    related_entity_id: Optional[str] = None  # معرف الكيان المرتبط
    action_url: Optional[str] = None  # رابط الإجراء (اختياري)
    expires_at: Optional[datetime] = None  # تاريخ انتهاء الصلاحية (للإشعارات المؤقتة)



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


class Task(BaseSchema):
    """
    نموذج المهمة (من collection 'tasks')
    يستخدم لإدارة المهام والتذكيرات
    """
    title: str  # عنوان المهمة
    description: Optional[str] = None  # وصف المهمة
    priority: TaskPriority = TaskPriority.MEDIUM  # الأولوية
    status: TaskStatus = TaskStatus.TODO  # الحالة
    category: TaskCategory = TaskCategory.GENERAL  # الفئة
    due_date: Optional[datetime] = None  # تاريخ الاستحقاق
    due_time: Optional[str] = None  # وقت الاستحقاق (HH:MM)
    completed_at: Optional[datetime] = None  # تاريخ الإكمال
    related_project_id: Optional[str] = None  # معرف المشروع المرتبط
    related_client_id: Optional[str] = None  # معرف العميل المرتبط
    tags: List[str] = Field(default_factory=list)  # الوسوم
    reminder: bool = False  # هل التذكير مفعل
    reminder_minutes: int = 30  # دقائق قبل الموعد للتذكير
    assigned_to: Optional[str] = None  # المستخدم المسؤول
