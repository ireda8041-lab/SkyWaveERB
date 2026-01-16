#!/usr/bin/env python3
"""
نظام إدارة المهام الاحترافي - Sky Wave ERP
Professional TODO Management System
تصميم متوافق مع باقي البرنامج
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from PyQt6.QtCore import QDate, Qt, QTime, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ui.styles import BUTTON_STYLES, COLORS, TABLE_STYLE_DARK, get_cairo_font, create_centered_item, get_arrow_url
from ui.smart_combobox import SmartFilterComboBox

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass

# مسار ملف إعدادات المهام
TASK_SETTINGS_FILE = "task_settings.json"


class TaskPriority(Enum):
    """أولوية المهمة"""
    LOW = "منخفضة"
    MEDIUM = "متوسطة"
    HIGH = "عالية"
    URGENT = "عاجلة"


class TaskStatus(Enum):
    """حالة المهمة"""
    TODO = "قيد الانتظار"
    IN_PROGRESS = "قيد التنفيذ"
    COMPLETED = "مكتملة"
    CANCELLED = "ملغاة"


class TaskCategory(Enum):
    """فئة المهمة"""
    GENERAL = "عامة"
    PROJECT = "مشروع"
    CLIENT = "عميل"
    PAYMENT = "دفعة"
    MEETING = "اجتماع"
    FOLLOW_UP = "متابعة"
    DEADLINE = "موعد نهائي"


class DueDateAction(Enum):
    """ما يحدث عند انتهاء تاريخ المهمة"""
    KEEP_VISIBLE = "keep_visible"
    MOVE_TO_COMPLETED = "move_to_completed"
    AUTO_DELETE = "auto_delete"
    HIDE_ONLY = "hide_only"


@dataclass
class TaskSettings:
    """إعدادات نظام المهام"""
    due_date_action: DueDateAction = DueDateAction.KEEP_VISIBLE
    auto_delete_after_days: int = 7
    show_completed_tasks: bool = True
    reminder_enabled: bool = True
    default_reminder_minutes: int = 30
    sound_notification: bool = True
    show_overdue_warning: bool = True
    auto_archive_completed: bool = False
    archive_after_days: int = 30

    def to_dict(self) -> dict:
        return {
            "due_date_action": self.due_date_action.value,
            "auto_delete_after_days": self.auto_delete_after_days,
            "show_completed_tasks": self.show_completed_tasks,
            "reminder_enabled": self.reminder_enabled,
            "default_reminder_minutes": self.default_reminder_minutes,
            "sound_notification": self.sound_notification,
            "show_overdue_warning": self.show_overdue_warning,
            "auto_archive_completed": self.auto_archive_completed,
            "archive_after_days": self.archive_after_days,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TaskSettings':
        return cls(
            due_date_action=DueDateAction(data.get("due_date_action", "keep_visible")),
            auto_delete_after_days=data.get("auto_delete_after_days", 7),
            show_completed_tasks=data.get("show_completed_tasks", True),
            reminder_enabled=data.get("reminder_enabled", True),
            default_reminder_minutes=data.get("default_reminder_minutes", 30),
            sound_notification=data.get("sound_notification", True),
            show_overdue_warning=data.get("show_overdue_warning", True),
            auto_archive_completed=data.get("auto_archive_completed", False),
            archive_after_days=data.get("archive_after_days", 30),
        )

    @classmethod
    def load(cls) -> 'TaskSettings':
        """تحميل الإعدادات من الملف"""
        try:
            if os.path.exists(TASK_SETTINGS_FILE):
                with open(TASK_SETTINGS_FILE, encoding='utf-8') as f:
                    data = json.load(f)
                    return cls.from_dict(data)
        except Exception as e:
            safe_print(f"WARNING: [TaskSettings] فشل تحميل الإعدادات: {e}")
        return cls()

    def save(self):
        """حفظ الإعدادات في الملف"""
        try:
            with open(TASK_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            safe_print("INFO: [TaskSettings] تم حفظ الإعدادات")
        except Exception as e:
            safe_print(f"ERROR: [TaskSettings] فشل حفظ الإعدادات: {e}")


@dataclass
class Task:
    """نموذج المهمة"""
    id: str
    title: str
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    category: TaskCategory = TaskCategory.GENERAL
    due_date: datetime | None = None
    due_time: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    related_project: str = ""
    related_client: str = ""
    tags: list[str] = field(default_factory=list)
    reminder: bool = False
    reminder_minutes: int = 30
    is_archived: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.name,
            "status": self.status.name,
            "category": self.category.name,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "due_time": self.due_time,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "related_project": self.related_project,
            "related_client": self.related_client,
            "tags": self.tags,
            "reminder": self.reminder,
            "reminder_minutes": self.reminder_minutes,
            "is_archived": self.is_archived,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            priority=TaskPriority[data.get("priority", "MEDIUM")],
            status=TaskStatus[data.get("status", "TODO")],
            category=TaskCategory[data.get("category", "GENERAL")],
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            due_time=data.get("due_time"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            related_project=data.get("related_project", ""),
            related_client=data.get("related_client", ""),
            tags=data.get("tags", []),
            reminder=data.get("reminder", False),
            reminder_minutes=data.get("reminder_minutes", 30),
            is_archived=data.get("is_archived", False),
        )

    def is_overdue(self) -> bool:
        """هل المهمة متأخرة؟"""
        if not self.due_date:
            return False
        if self.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            return False
        return self.due_date < datetime.now()

    def is_due_today(self) -> bool:
        """هل المهمة مستحقة اليوم؟"""
        if not self.due_date:
            return False
        return self.due_date.date() == datetime.now().date()

    def days_until_due(self) -> int | None:
        """عدد الأيام حتى الاستحقاق"""
        if not self.due_date:
            return None
        delta = self.due_date.date() - datetime.now().date()
        return delta.days


class TaskService:
    """خدمة إدارة المهام - مرتبطة بقاعدة البيانات"""

    _instance = None
    _repository = None

    def __new__(cls, repository=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, repository=None):
        if repository:
            self._repository = repository
            TaskService._repository = repository
        elif TaskService._repository:
            self._repository = TaskService._repository

        if self._initialized and self._repository:
            return

        self._initialized = True
        self.tasks: list[Task] = []
        self.settings = TaskSettings.load()
        self._reminder_shown: set[str] = set()

        if not self._repository:
            safe_print("WARNING: [TaskService] لم يتم تعيين Repository")

        if self._repository:
            self.load_tasks()

    @classmethod
    def set_repository(cls, repository):
        """تعيين Repository من الخارج"""
        cls._repository = repository
        if cls._instance:
            cls._instance._repository = repository
            cls._instance._initialized = True
            try:
                cls._instance.load_tasks()
            except Exception as e:
                safe_print(f"WARNING: [TaskService] فشل تحميل المهام: {e}")

    def load_tasks(self):
        """تحميل المهام من قاعدة البيانات"""
        try:
            if self._repository:
                tasks_data = self._repository.get_all_tasks()
                self.tasks = [self._dict_to_task(t) for t in tasks_data]
                safe_print(f"INFO: [TaskService] تم تحميل {len(self.tasks)} مهمة")
            else:
                self._load_from_file()
        except Exception as e:
            safe_print(f"ERROR: [TaskService] فشل تحميل المهام: {e}")
            self.tasks = []

    def _load_from_file(self):
        """تحميل من ملف JSON"""
        storage_path = "tasks.json"
        try:
            if os.path.exists(storage_path):
                with open(storage_path, encoding='utf-8') as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(t) for t in data]
        except Exception as e:
            safe_print(f"ERROR: [TaskService] فشل تحميل المهام من الملف: {e}")
            self.tasks = []

    def _dict_to_task(self, data: dict) -> Task:
        """تحويل dict من قاعدة البيانات إلى Task"""
        try:
            due_date = None
            if data.get('due_date'):
                if isinstance(data['due_date'], str):
                    due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
                else:
                    due_date = data['due_date']

            completed_at = None
            if data.get('completed_at'):
                if isinstance(data['completed_at'], str):
                    completed_at = datetime.fromisoformat(data['completed_at'].replace('Z', '+00:00'))
                else:
                    completed_at = data['completed_at']

            created_at = datetime.now()
            if data.get('created_at'):
                if isinstance(data['created_at'], str):
                    created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
                else:
                    created_at = data['created_at']

            return Task(
                id=str(data.get('id', '')),
                title=data.get('title', ''),
                description=data.get('description', ''),
                priority=TaskPriority[data.get('priority', 'MEDIUM')],
                status=TaskStatus[data.get('status', 'TODO')],
                category=TaskCategory[data.get('category', 'GENERAL')],
                due_date=due_date,
                due_time=data.get('due_time'),
                created_at=created_at,
                completed_at=completed_at,
                related_project=data.get('related_project_id', ''),
                related_client=data.get('related_client_id', ''),
                tags=data.get('tags', []) if isinstance(data.get('tags'), list) else [],
                reminder=data.get('reminder', False),
                reminder_minutes=data.get('reminder_minutes', 30),
                is_archived=data.get('is_archived', False),
            )
        except Exception as e:
            safe_print(f"ERROR: [TaskService] فشل تحويل المهمة: {e}")
            return Task(id=str(data.get('id', '')), title=data.get('title', 'مهمة'))

    def _task_to_dict(self, task: Task) -> dict:
        """تحويل Task إلى dict لقاعدة البيانات"""
        # تحويل القيم الفارغة إلى None لتجنب مشاكل FOREIGN KEY
        related_project = task.related_project if task.related_project else None
        related_client = task.related_client if task.related_client else None
        
        return {
            'id': task.id,
            'title': task.title,
            'description': task.description or None,
            'priority': task.priority.name,
            'status': task.status.name,
            'category': task.category.name,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'due_time': task.due_time if task.due_time else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'related_project_id': related_project,
            'related_client_id': related_client,
            'tags': json.dumps(task.tags, ensure_ascii=False) if task.tags else '[]',
            'reminder': task.reminder,
            'reminder_minutes': task.reminder_minutes,
            'is_archived': task.is_archived,
        }


    def add_task(self, task: Task) -> Task:
        """إضافة مهمة جديدة"""
        try:
            if self._repository:
                task_dict = self._task_to_dict(task)
                result = self._repository.create_task(task_dict)
                task.id = str(result.get('id', task.id))
                safe_print(f"INFO: [TaskService] تم حفظ المهمة: {task.title}")

            self.tasks.append(task)
            self._emit_change_signal()
            return task
        except Exception as e:
            safe_print(f"ERROR: [TaskService] فشل إضافة المهمة: {e}")
            import traceback
            traceback.print_exc()
            return task

    def update_task(self, task: Task):
        """تحديث مهمة"""
        try:
            if self._repository:
                task_dict = self._task_to_dict(task)
                self._repository.update_task(task.id, task_dict)

            for i, t in enumerate(self.tasks):
                if t.id == task.id:
                    self.tasks[i] = task
                    break

            self._emit_change_signal()
            safe_print(f"INFO: [TaskService] تم تحديث مهمة: {task.title}")
        except Exception as e:
            safe_print(f"ERROR: [TaskService] فشل تحديث المهمة: {e}")

    def delete_task(self, task_id: str):
        """حذف مهمة"""
        try:
            if self._repository:
                self._repository.delete_task(task_id)

            self.tasks = [t for t in self.tasks if t.id != task_id]
            self._emit_change_signal()
            safe_print(f"INFO: [TaskService] تم حذف مهمة (ID: {task_id})")
        except Exception as e:
            safe_print(f"ERROR: [TaskService] فشل حذف المهمة: {e}")

    def _emit_change_signal(self):
        """إرسال إشارة تغيير البيانات"""
        try:
            from core.signals import app_signals
            app_signals.emit_data_changed('tasks')
        except Exception:
            pass

    def get_task(self, task_id: str) -> Task | None:
        """الحصول على مهمة بالـ ID"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_all_tasks(self) -> list[Task]:
        """الحصول على جميع المهام"""
        return self.tasks

    def get_active_tasks(self) -> list[Task]:
        """الحصول على المهام النشطة"""
        return [t for t in self.tasks
                if t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
                and not t.is_archived]

    def get_completed_tasks(self) -> list[Task]:
        """الحصول على المهام المكتملة"""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED and not t.is_archived]

    def get_archived_tasks(self) -> list[Task]:
        """الحصول على المهام المؤرشفة"""
        return [t for t in self.tasks if t.is_archived]

    def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        """الحصول على المهام حسب الحالة"""
        return [t for t in self.tasks if t.status == status]

    def get_tasks_by_priority(self, priority: TaskPriority) -> list[Task]:
        """الحصول على المهام حسب الأولوية"""
        return [t for t in self.tasks if t.priority == priority]

    def get_overdue_tasks(self) -> list[Task]:
        """الحصول على المهام المتأخرة"""
        return [t for t in self.tasks if t.is_overdue() and not t.is_archived]

    def get_today_tasks(self) -> list[Task]:
        """الحصول على مهام اليوم"""
        return [t for t in self.tasks if t.is_due_today() and not t.is_archived]

    def get_upcoming_tasks(self, days: int = 7) -> list[Task]:
        """الحصول على المهام القادمة"""
        now = datetime.now()
        end_date = now + timedelta(days=days)
        return [t for t in self.tasks
                if t.due_date and now <= t.due_date <= end_date
                and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
                and not t.is_archived]

    def get_tasks_by_project(self, project_id: str) -> list[Task]:
        """الحصول على المهام المرتبطة بمشروع"""
        return [t for t in self.tasks if t.related_project == project_id]

    def get_tasks_by_client(self, client_id: str) -> list[Task]:
        """الحصول على المهام المرتبطة بعميل"""
        return [t for t in self.tasks if t.related_client == client_id]

    def get_statistics(self) -> dict:
        """الحصول على إحصائيات المهام"""
        total = len([t for t in self.tasks if not t.is_archived])
        completed = len([t for t in self.tasks if t.status == TaskStatus.COMPLETED and not t.is_archived])
        in_progress = len([t for t in self.tasks if t.status == TaskStatus.IN_PROGRESS and not t.is_archived])
        todo = len([t for t in self.tasks if t.status == TaskStatus.TODO and not t.is_archived])
        overdue = len(self.get_overdue_tasks())
        today = len(self.get_today_tasks())
        archived = len(self.get_archived_tasks())

        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "todo": todo,
            "overdue": overdue,
            "today": today,
            "archived": archived,
            "completion_rate": (completed / total * 100) if total > 0 else 0
        }

    def generate_id(self) -> str:
        """توليد ID فريد"""
        import uuid
        return str(uuid.uuid4())[:8]

    def refresh(self):
        """تحديث المهام من قاعدة البيانات"""
        self.load_tasks()


    def process_due_date_actions(self):
        """معالجة المهام حسب إعدادات تاريخ الانتهاء"""
        now = datetime.now()
        tasks_to_delete = []
        tasks_to_update = []

        for task in self.tasks:
            if task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                continue
            if not task.due_date or task.is_archived:
                continue
            if task.due_date >= now:
                continue

            action = self.settings.due_date_action

            if action == DueDateAction.MOVE_TO_COMPLETED:
                task.status = TaskStatus.COMPLETED
                task.completed_at = now
                tasks_to_update.append(task)

            elif action == DueDateAction.AUTO_DELETE:
                days_overdue = (now - task.due_date).days
                if days_overdue >= self.settings.auto_delete_after_days:
                    tasks_to_delete.append(task.id)

            elif action == DueDateAction.HIDE_ONLY:
                task.is_archived = True
                tasks_to_update.append(task)

        for task in tasks_to_update:
            self.update_task(task)

        for task_id in tasks_to_delete:
            self.delete_task(task_id)

        if tasks_to_update or tasks_to_delete:
            safe_print(f"INFO: [TaskService] معالجة {len(tasks_to_update)} مهمة، حذف {len(tasks_to_delete)} مهمة")

    def archive_old_completed_tasks(self):
        """أرشفة المهام المكتملة القديمة"""
        if not self.settings.auto_archive_completed:
            return

        now = datetime.now()
        archive_threshold = now - timedelta(days=self.settings.archive_after_days)

        for task in self.tasks:
            if task.status == TaskStatus.COMPLETED and not task.is_archived:
                if task.completed_at and task.completed_at < archive_threshold:
                    task.is_archived = True
                    self.update_task(task)

    def get_tasks_needing_reminder(self) -> list[Task]:
        """الحصول على المهام التي تحتاج تذكير"""
        if not self.settings.reminder_enabled:
            return []

        now = datetime.now()
        tasks_to_remind = []

        for task in self.tasks:
            if not task.reminder or task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                continue
            if task.id in self._reminder_shown:
                continue
            if not task.due_date:
                continue

            reminder_time = task.due_date - timedelta(minutes=task.reminder_minutes)
            if reminder_time <= now <= task.due_date:
                tasks_to_remind.append(task)
                self._reminder_shown.add(task.id)

        return tasks_to_remind


class TaskSettingsDialog(QDialog):
    """نافذة إعدادات المهام - تصميم متوافق مع باقي الأقسام"""

    def __init__(self, settings: TaskSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.result_settings: TaskSettings | None = None

        self.setWindowTitle("⚙️ إعدادات المهام")
        self.setMinimumWidth(420)
        self.setMinimumHeight(450)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """تهيئة الواجهة - تصميم متوافق مع باقي البرنامج"""
        # ستايلات الحقول - الأسهم على اليسار (RTL)
        field_style = f"""
            QSpinBox {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px 7px 22px;
                font-size: 11px;
                min-height: 16px;
            }}
            QSpinBox:hover {{
                border-color: {COLORS['primary']};
            }}
            QSpinBox:focus {{
                border: 1px solid {COLORS['primary']};
            }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top left;
                width: 18px;
                height: 14px;
                border: none;
                background: transparent;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom left;
                width: 18px;
                height: 14px;
                border: none;
                background: transparent;
            }}
            QSpinBox::up-arrow {{
                image: url({get_arrow_url("up")});
                width: 10px;
                height: 10px;
            }}
            QSpinBox::down-arrow {{
                image: url({get_arrow_url("down")});
                width: 10px;
                height: 10px;
            }}
        """
        
        radio_style = f"color: {COLORS['text_primary']}; font-size: 11px; padding: 4px;"
        checkbox_style = f"color: {COLORS['text_primary']}; font-size: 11px;"
        label_style = f"color: {COLORS['text_secondary']}; font-size: 10px;"

        # التخطيط الرئيسي
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # منطقة التمرير
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {COLORS['bg_dark']};
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['bg_medium']};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['primary']};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)

        # === إعدادات تاريخ الانتهاء ===
        due_date_label = QLabel("📅 عند انتهاء تاريخ المهمة:")
        due_date_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: bold;")
        layout.addWidget(due_date_label)

        self.due_date_action_group = QButtonGroup(self)

        self.radio_keep_visible = QRadioButton("🔔 تبقى ظاهرة مع تحذير (متأخرة)")
        self.radio_keep_visible.setStyleSheet(radio_style)
        self.due_date_action_group.addButton(self.radio_keep_visible)
        layout.addWidget(self.radio_keep_visible)

        self.radio_move_completed = QRadioButton("✅ تنتقل تلقائياً للمهام المنتهية")
        self.radio_move_completed.setStyleSheet(radio_style)
        self.due_date_action_group.addButton(self.radio_move_completed)
        layout.addWidget(self.radio_move_completed)

        self.radio_hide = QRadioButton("👁️ تختفي من القائمة (تبقى في قاعدة البيانات)")
        self.radio_hide.setStyleSheet(radio_style)
        self.due_date_action_group.addButton(self.radio_hide)
        layout.addWidget(self.radio_hide)

        auto_delete_row = QHBoxLayout()
        auto_delete_row.setSpacing(8)
        self.radio_auto_delete = QRadioButton("🗑️ تُحذف تلقائياً بعد")
        self.radio_auto_delete.setStyleSheet(radio_style)
        self.due_date_action_group.addButton(self.radio_auto_delete)
        auto_delete_row.addWidget(self.radio_auto_delete)

        self.auto_delete_days = QSpinBox()
        self.auto_delete_days.setRange(1, 365)
        self.auto_delete_days.setValue(7)
        self.auto_delete_days.setSuffix(" يوم")
        self.auto_delete_days.setFixedWidth(110)
        self.auto_delete_days.setStyleSheet(field_style)
        auto_delete_row.addWidget(self.auto_delete_days)
        auto_delete_row.addStretch()
        layout.addLayout(auto_delete_row)

        # فاصل
        layout.addSpacing(8)

        # === إعدادات التذكيرات ===
        reminder_label = QLabel("⏰ التذكيرات:")
        reminder_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: bold;")
        layout.addWidget(reminder_label)

        self.reminder_enabled = QCheckBox("🔔 تفعيل التذكيرات")
        self.reminder_enabled.setStyleSheet(checkbox_style)
        layout.addWidget(self.reminder_enabled)

        reminder_row = QHBoxLayout()
        reminder_row.setSpacing(8)
        reminder_time_label = QLabel("⏱️ وقت التذكير:")
        reminder_time_label.setStyleSheet(label_style)
        reminder_row.addWidget(reminder_time_label)

        self.default_reminder_minutes = QSpinBox()
        self.default_reminder_minutes.setRange(5, 1440)
        self.default_reminder_minutes.setValue(30)
        self.default_reminder_minutes.setSuffix(" دقيقة قبل")
        self.default_reminder_minutes.setFixedWidth(140)
        self.default_reminder_minutes.setStyleSheet(field_style)
        reminder_row.addWidget(self.default_reminder_minutes)
        reminder_row.addStretch()
        layout.addLayout(reminder_row)

        self.sound_notification = QCheckBox("🔊 تشغيل صوت عند التذكير")
        self.sound_notification.setStyleSheet(checkbox_style)
        layout.addWidget(self.sound_notification)

        # فاصل
        layout.addSpacing(8)

        # === إعدادات العرض ===
        display_label = QLabel("👁️ العرض:")
        display_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: bold;")
        layout.addWidget(display_label)

        self.show_completed = QCheckBox("✅ عرض المهام المكتملة في القائمة الرئيسية")
        self.show_completed.setStyleSheet(checkbox_style)
        layout.addWidget(self.show_completed)

        self.show_overdue_warning = QCheckBox("⚠️ عرض تحذير للمهام المتأخرة")
        self.show_overdue_warning.setStyleSheet(checkbox_style)
        layout.addWidget(self.show_overdue_warning)

        # فاصل
        layout.addSpacing(8)

        # === الأرشفة التلقائية ===
        archive_label = QLabel("📦 الأرشفة التلقائية:")
        archive_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: bold;")
        layout.addWidget(archive_label)

        self.auto_archive = QCheckBox("📁 أرشفة المهام المكتملة تلقائياً")
        self.auto_archive.setStyleSheet(checkbox_style)
        layout.addWidget(self.auto_archive)

        archive_row = QHBoxLayout()
        archive_row.setSpacing(8)
        archive_days_label = QLabel("📅 أرشفة بعد:")
        archive_days_label.setStyleSheet(label_style)
        archive_row.addWidget(archive_days_label)

        self.archive_after_days = QSpinBox()
        self.archive_after_days.setRange(1, 365)
        self.archive_after_days.setValue(30)
        self.archive_after_days.setSuffix(" يوم")
        self.archive_after_days.setFixedWidth(110)
        self.archive_after_days.setStyleSheet(field_style)
        archive_row.addWidget(self.archive_after_days)
        archive_row.addStretch()
        layout.addLayout(archive_row)

        layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        # منطقة الأزرار
        buttons_container = QWidget()
        buttons_container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_medium']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(14, 10, 14, 10)
        buttons_layout.setSpacing(8)

        buttons_layout.addStretch()

        save_btn = QPushButton("💾 حفظ")
        save_btn.setStyleSheet(BUTTON_STYLES["primary"])
        save_btn.setFixedSize(90, 30)
        save_btn.clicked.connect(self.save_settings)
        buttons_layout.addWidget(save_btn)

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        cancel_btn.setFixedSize(70, 30)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        main_layout.addWidget(buttons_container)

    def load_settings(self):
        """تحميل الإعدادات الحالية"""
        if self.settings.due_date_action == DueDateAction.KEEP_VISIBLE:
            self.radio_keep_visible.setChecked(True)
        elif self.settings.due_date_action == DueDateAction.MOVE_TO_COMPLETED:
            self.radio_move_completed.setChecked(True)
        elif self.settings.due_date_action == DueDateAction.HIDE_ONLY:
            self.radio_hide.setChecked(True)
        elif self.settings.due_date_action == DueDateAction.AUTO_DELETE:
            self.radio_auto_delete.setChecked(True)

        self.auto_delete_days.setValue(self.settings.auto_delete_after_days)
        self.reminder_enabled.setChecked(self.settings.reminder_enabled)
        self.default_reminder_minutes.setValue(self.settings.default_reminder_minutes)
        self.sound_notification.setChecked(self.settings.sound_notification)
        self.show_completed.setChecked(self.settings.show_completed_tasks)
        self.show_overdue_warning.setChecked(self.settings.show_overdue_warning)
        self.auto_archive.setChecked(self.settings.auto_archive_completed)
        self.archive_after_days.setValue(self.settings.archive_after_days)

    def save_settings(self):
        """حفظ الإعدادات"""
        if self.radio_keep_visible.isChecked():
            due_action = DueDateAction.KEEP_VISIBLE
        elif self.radio_move_completed.isChecked():
            due_action = DueDateAction.MOVE_TO_COMPLETED
        elif self.radio_hide.isChecked():
            due_action = DueDateAction.HIDE_ONLY
        else:
            due_action = DueDateAction.AUTO_DELETE

        self.result_settings = TaskSettings(
            due_date_action=due_action,
            auto_delete_after_days=self.auto_delete_days.value(),
            show_completed_tasks=self.show_completed.isChecked(),
            reminder_enabled=self.reminder_enabled.isChecked(),
            default_reminder_minutes=self.default_reminder_minutes.value(),
            sound_notification=self.sound_notification.isChecked(),
            show_overdue_warning=self.show_overdue_warning.isChecked(),
            auto_archive_completed=self.auto_archive.isChecked(),
            archive_after_days=self.archive_after_days.value(),
        )

        self.result_settings.save()
        self.accept()

    def get_settings(self) -> TaskSettings | None:
        return self.result_settings


class TaskEditorDialog(QDialog):
    """نافذة إضافة/تعديل مهمة - تصميم متوافق مع باقي الأقسام"""

    def __init__(self, task: Task | None = None, parent=None, project_service=None, client_service=None, default_settings: TaskSettings = None):
        super().__init__(parent)
        self.task = task
        self.is_editing = task is not None
        self.result_task: Task | None = None
        self.project_service = project_service
        self.client_service = client_service
        self.default_settings = default_settings or TaskSettings.load()

        self.projects_list: list[Any] = []
        self.clients_list: list[Any] = []
        self._load_projects_and_clients()

        self.setWindowTitle("✏️ تعديل مهمة" if self.is_editing else "➕ مهمة جديدة")
        self.setMinimumWidth(420)
        self.setMinimumHeight(500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass

        self.init_ui()

        if self.is_editing:
            self.load_task_data()

    def _load_projects_and_clients(self):
        """تحميل قوائم المشاريع والعملاء"""
        try:
            if self.project_service:
                projects = self.project_service.get_all_projects()
                self.projects_list = [(str(p.id), p.name) for p in projects if hasattr(p, 'id') and hasattr(p, 'name')]
        except Exception as e:
            safe_print(f"WARNING: [TaskEditor] فشل تحميل المشاريع: {e}")

        try:
            if self.client_service:
                clients = self.client_service.get_all_clients()
                self.clients_list = [(str(c.id), c.name) for c in clients if hasattr(c, 'id') and hasattr(c, 'name')]
        except Exception as e:
            safe_print(f"WARNING: [TaskEditor] فشل تحميل العملاء: {e}")

    def init_ui(self):
        """تهيئة الواجهة - تصميم متوافق مع باقي البرنامج"""
        # ستايلات الحقول مع إظهار الأسهم داخل الحقل
        field_style = f"""
            QLineEdit {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px;
                font-size: 11px;
                min-height: 16px;
            }}
            QLineEdit:hover {{
                border-color: {COLORS['primary']};
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['primary']};
            }}
            QComboBox {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px 7px 22px;
                font-size: 11px;
                min-height: 16px;
            }}
            QComboBox:hover {{
                border-color: {COLORS['primary']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 20px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: url({get_arrow_url("down")});
                width: 10px;
                height: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                selection-background-color: {COLORS['primary']};
                selection-color: white;
            }}
            QSpinBox, QDateEdit, QTimeEdit {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px 7px 22px;
                font-size: 11px;
                min-height: 16px;
            }}
            QSpinBox:hover, QDateEdit:hover, QTimeEdit:hover {{
                border-color: {COLORS['primary']};
            }}
            QSpinBox::up-button, QDateEdit::up-button, QTimeEdit::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top left;
                width: 18px;
                height: 14px;
                border: none;
                background: transparent;
            }}
            QSpinBox::down-button, QDateEdit::down-button, QTimeEdit::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom left;
                width: 18px;
                height: 14px;
                border: none;
                background: transparent;
            }}
            QSpinBox::up-arrow, QDateEdit::up-arrow, QTimeEdit::up-arrow {{
                image: url({get_arrow_url("up")});
                width: 10px;
                height: 10px;
            }}
            QSpinBox::down-arrow, QDateEdit::down-arrow, QTimeEdit::down-arrow {{
                image: url({get_arrow_url("down")});
                width: 10px;
                height: 10px;
            }}
            QTextEdit {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 6px;
                font-size: 11px;
            }}
        """
        
        label_style = f"color: {COLORS['text_secondary']}; font-size: 10px;"
        checkbox_style = f"color: {COLORS['text_primary']}; font-size: 11px;"

        # التخطيط الرئيسي
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # منطقة التمرير
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {COLORS['bg_dark']};
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['bg_medium']};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['primary']};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 14, 14, 14)

        # عنوان المهمة
        title_label = QLabel("📝 العنوان *")
        title_label.setStyleSheet(label_style)
        layout.addWidget(title_label)
        self.title_input = QLineEdit()
        self.title_input.setStyleSheet(field_style)
        self.title_input.setPlaceholderText("أدخل عنوان المهمة...")
        layout.addWidget(self.title_input)

        # الوصف
        desc_label = QLabel("📋 الوصف")
        desc_label.setStyleSheet(label_style)
        layout.addWidget(desc_label)
        self.description_input = QTextEdit()
        self.description_input.setStyleSheet(field_style)
        self.description_input.setPlaceholderText("وصف المهمة (اختياري)...")
        self.description_input.setFixedHeight(60)
        layout.addWidget(self.description_input)

        # صف الأولوية والفئة
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        
        priority_cont = QVBoxLayout()
        priority_cont.setSpacing(2)
        priority_label = QLabel("⚡ الأولوية")
        priority_label.setStyleSheet(label_style)
        priority_cont.addWidget(priority_label)
        self.priority_combo = QComboBox()
        self.priority_combo.setStyleSheet(field_style)
        for priority in TaskPriority:
            icon = '🔴' if priority == TaskPriority.URGENT else '🟠' if priority == TaskPriority.HIGH else '🟡' if priority == TaskPriority.MEDIUM else '🟢'
            self.priority_combo.addItem(f"{icon} {priority.value}", priority)
        self.priority_combo.setCurrentIndex(1)
        priority_cont.addWidget(self.priority_combo)
        row1.addLayout(priority_cont, 1)
        
        category_cont = QVBoxLayout()
        category_cont.setSpacing(2)
        category_label = QLabel("📁 الفئة")
        category_label.setStyleSheet(label_style)
        category_cont.addWidget(category_label)
        self.category_combo = QComboBox()
        self.category_combo.setStyleSheet(field_style)
        for category in TaskCategory:
            self.category_combo.addItem(category.value, category)
        category_cont.addWidget(self.category_combo)
        row1.addLayout(category_cont, 1)
        
        layout.addLayout(row1)

        # صف التاريخ والوقت
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        
        date_cont = QVBoxLayout()
        date_cont.setSpacing(2)
        date_label = QLabel("📅 تاريخ الاستحقاق")
        date_label.setStyleSheet(label_style)
        date_cont.addWidget(date_label)
        self.due_date_input = QDateEdit()
        self.due_date_input.setCalendarPopup(True)
        self.due_date_input.setDate(QDate.currentDate().addDays(1))
        self.due_date_input.setStyleSheet(field_style)
        date_cont.addWidget(self.due_date_input)
        row2.addLayout(date_cont, 1)
        
        time_cont = QVBoxLayout()
        time_cont.setSpacing(2)
        time_label = QLabel("⏰ الوقت")
        time_label.setStyleSheet(label_style)
        time_cont.addWidget(time_label)
        self.due_time_input = QTimeEdit()
        self.due_time_input.setTime(QTime(12, 0))
        self.due_time_input.setStyleSheet(field_style)
        time_cont.addWidget(self.due_time_input)
        row2.addLayout(time_cont, 1)
        
        layout.addLayout(row2)

        # الحالة (للتعديل فقط)
        if self.is_editing:
            status_label = QLabel("📊 الحالة")
            status_label.setStyleSheet(label_style)
            layout.addWidget(status_label)
            self.status_combo = QComboBox()
            self.status_combo.setStyleSheet(field_style)
            for status in TaskStatus:
                icon = "⏳" if status == TaskStatus.TODO else "🔄" if status == TaskStatus.IN_PROGRESS else "✅" if status == TaskStatus.COMPLETED else "❌"
                self.status_combo.addItem(f"{icon} {status.value}", status)
            layout.addWidget(self.status_combo)

        # صف المشروع والعميل
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        
        project_cont = QVBoxLayout()
        project_cont.setSpacing(2)
        project_label = QLabel("📁 المشروع")
        project_label.setStyleSheet(label_style)
        project_cont.addWidget(project_label)
        # SmartFilterComboBox مع فلترة ذكية
        self.project_combo = SmartFilterComboBox()
        self.project_combo.setStyleSheet(field_style)
        self.project_combo.addItem("-- بدون مشروع --", "")
        for project_id, project_name in self.projects_list:
            self.project_combo.addItem(project_name, project_id)
        project_cont.addWidget(self.project_combo)
        row3.addLayout(project_cont, 1)
        
        client_cont = QVBoxLayout()
        client_cont.setSpacing(2)
        client_label = QLabel("👤 العميل")
        client_label.setStyleSheet(label_style)
        client_cont.addWidget(client_label)
        # SmartFilterComboBox مع فلترة ذكية
        self.client_combo = SmartFilterComboBox()
        self.client_combo.setStyleSheet(field_style)
        self.client_combo.addItem("-- بدون عميل --", "")
        for client_id, client_name in self.clients_list:
            self.client_combo.addItem(client_name, client_id)
        client_cont.addWidget(self.client_combo)
        row3.addLayout(client_cont, 1)
        
        layout.addLayout(row3)

        # التذكير
        reminder_row = QHBoxLayout()
        reminder_row.setSpacing(8)
        self.reminder_checkbox = QCheckBox("⏰ تفعيل التذكير")
        self.reminder_checkbox.setChecked(self.default_settings.reminder_enabled)
        self.reminder_checkbox.setStyleSheet(checkbox_style)
        reminder_row.addWidget(self.reminder_checkbox)

        self.reminder_minutes = QSpinBox()
        self.reminder_minutes.setRange(5, 1440)
        self.reminder_minutes.setValue(self.default_settings.default_reminder_minutes)
        self.reminder_minutes.setSuffix(" دقيقة قبل")
        self.reminder_minutes.setFixedWidth(140)
        self.reminder_minutes.setStyleSheet(field_style)
        reminder_row.addWidget(self.reminder_minutes)
        reminder_row.addStretch()
        layout.addLayout(reminder_row)

        layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        # منطقة الأزرار
        buttons_container = QWidget()
        buttons_container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_medium']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(14, 10, 14, 10)
        buttons_layout.setSpacing(8)

        buttons_layout.addStretch()

        save_btn = QPushButton("💾 حفظ")
        save_btn.setStyleSheet(BUTTON_STYLES["primary"])
        save_btn.setFixedSize(90, 30)
        save_btn.clicked.connect(self.save_task)
        buttons_layout.addWidget(save_btn)

        if self.is_editing:
            complete_btn = QPushButton("✅ إكمال")
            complete_btn.setStyleSheet(BUTTON_STYLES["success"])
            complete_btn.setFixedSize(80, 30)
            complete_btn.clicked.connect(self._quick_complete)
            buttons_layout.addWidget(complete_btn)

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        cancel_btn.setFixedSize(70, 30)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        main_layout.addWidget(buttons_container)

    def load_task_data(self):
        """تحميل بيانات المهمة للتعديل"""
        if not self.task:
            return

        self.title_input.setText(self.task.title)
        self.description_input.setText(self.task.description)

        for i in range(self.priority_combo.count()):
            if self.priority_combo.itemData(i) == self.task.priority:
                self.priority_combo.setCurrentIndex(i)
                break

        for i in range(self.category_combo.count()):
            if self.category_combo.itemData(i) == self.task.category:
                self.category_combo.setCurrentIndex(i)
                break

        if hasattr(self, 'status_combo'):
            for i in range(self.status_combo.count()):
                if self.status_combo.itemData(i) == self.task.status:
                    self.status_combo.setCurrentIndex(i)
                    break

        if self.task.due_date:
            self.due_date_input.setDate(QDate(self.task.due_date.year, self.task.due_date.month, self.task.due_date.day))
        if self.task.due_time:
            parts = self.task.due_time.split(":")
            if len(parts) >= 2:
                self.due_time_input.setTime(QTime(int(parts[0]), int(parts[1])))

        if self.task.related_project:
            for i in range(self.project_combo.count()):
                if self.project_combo.itemData(i) == self.task.related_project:
                    self.project_combo.setCurrentIndex(i)
                    break

        if self.task.related_client:
            for i in range(self.client_combo.count()):
                if self.client_combo.itemData(i) == self.task.related_client:
                    self.client_combo.setCurrentIndex(i)
                    break

        self.reminder_checkbox.setChecked(self.task.reminder)
        self.reminder_minutes.setValue(self.task.reminder_minutes)

    def _quick_complete(self):
        """إكمال المهمة بسرعة"""
        if hasattr(self, 'status_combo'):
            for i in range(self.status_combo.count()):
                if self.status_combo.itemData(i) == TaskStatus.COMPLETED:
                    self.status_combo.setCurrentIndex(i)
                    break
        self.save_task()

    def save_task(self):
        """حفظ المهمة"""
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال عنوان المهمة")
            return

        if self.is_editing:
            task_id = self.task.id
            created_at = self.task.created_at
            status = self.status_combo.currentData() if hasattr(self, 'status_combo') else self.task.status
            completed_at = self.task.completed_at
            is_archived = self.task.is_archived

            if status == TaskStatus.COMPLETED and self.task.status != TaskStatus.COMPLETED:
                completed_at = datetime.now()
            elif status != TaskStatus.COMPLETED:
                completed_at = None
        else:
            import uuid
            task_id = str(uuid.uuid4())[:8]
            created_at = datetime.now()
            status = TaskStatus.TODO
            completed_at = None
            is_archived = False

        due_date = self.due_date_input.date().toPyDate()
        due_datetime = datetime.combine(due_date, datetime.min.time())
        due_time = self.due_time_input.time().toString("HH:mm")

        selected_project = self.project_combo.currentData() or ""
        selected_client = self.client_combo.currentData() or ""

        self.result_task = Task(
            id=task_id,
            title=title,
            description=self.description_input.toPlainText(),
            priority=self.priority_combo.currentData(),
            status=status,
            category=self.category_combo.currentData(),
            due_date=due_datetime,
            due_time=due_time,
            created_at=created_at,
            completed_at=completed_at,
            related_project=selected_project,
            related_client=selected_client,
            reminder=self.reminder_checkbox.isChecked(),
            reminder_minutes=self.reminder_minutes.value(),
            is_archived=is_archived,
        )

        self.accept()

    def get_task(self) -> Task | None:
        return self.result_task


class TodoManagerWidget(QWidget):
    """
    ويدجت إدارة المهام الاحترافي
    تصميم متوافق مع ProjectManagerTab
    """

    def __init__(self, parent=None, project_service=None, client_service=None):
        super().__init__(parent)
        
        # 📱 تصميم متجاوب
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.task_service = TaskService()
        self.project_service = project_service
        self.client_service = client_service
        self.selected_task: Task | None = None

        self._projects_cache = {}
        self._clients_cache = {}
        self._cache_loaded = False
        self._is_loading = False

        self.init_ui()

        QTimer.singleShot(100, self._load_cache_and_tasks)

        try:
            from core.signals import app_signals
            app_signals.tasks_changed.connect(self._on_tasks_changed)
        except Exception as e:
            safe_print(f"WARNING: [TodoManager] فشل ربط الإشارات: {e}")

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._periodic_update)
        self.update_timer.start(300000)  # ⚡ 5 دقائق بدلاً من دقيقة

    def _load_cache_and_tasks(self):
        """تحميل الـ cache ثم المهام"""
        self._load_projects_clients_cache()
        self.load_tasks()

    def _load_projects_clients_cache(self):
        """تحميل قوائم المشاريع والعملاء"""
        if self._cache_loaded:
            return
        try:
            if self.project_service:
                projects = self.project_service.get_all_projects()
                self._projects_cache = {str(p.id): p.name for p in projects if hasattr(p, 'id') and hasattr(p, 'name')}
        except Exception as e:
            safe_print(f"WARNING: [TodoManager] فشل تحميل المشاريع: {e}")
        try:
            if self.client_service:
                clients = self.client_service.get_all_clients()
                self._clients_cache = {str(c.id): c.name for c in clients if hasattr(c, 'id') and hasattr(c, 'name')}
        except Exception as e:
            safe_print(f"WARNING: [TodoManager] فشل تحميل العملاء: {e}")
        self._cache_loaded = True

    def _on_tasks_changed(self):
        """معالج تحديث المهام"""
        QTimer.singleShot(50, self._do_refresh_tasks)

    def _do_refresh_tasks(self):
        """تنفيذ تحديث المهام"""
        self.task_service.load_tasks()
        self.load_tasks()

    def _periodic_update(self):
        """التحديث الدوري"""
        self.task_service.process_due_date_actions()
        self.task_service.archive_old_completed_tasks()
        self.check_reminders()
        self.update_statistics()


    def init_ui(self):
        """تهيئة الواجهة الرئيسية - تصميم متوافق مع ProjectManagerTab"""
        from PyQt6.QtWidgets import QSizePolicy
        
        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(main_layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # === الجزء الأيسر (الجدول والأزرار) ===
        left_panel = QVBoxLayout()

        # === شريط الأزرار المتجاوب ===
        from ui.responsive_toolbar import ResponsiveToolbar
        self.toolbar = ResponsiveToolbar()

        self.add_button = QPushButton("➕ مهمة جديدة")
        self.add_button.setStyleSheet(BUTTON_STYLES["success"])
        self.add_button.setFixedHeight(28)
        self.add_button.clicked.connect(self.add_task)

        self.edit_button = QPushButton("✏️ تعديل")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.edit_selected_task)
        self.edit_button.setEnabled(False)

        self.complete_button = QPushButton("✅ إكمال")
        self.complete_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.complete_button.setFixedHeight(28)
        self.complete_button.clicked.connect(self.complete_selected_task)
        self.complete_button.setEnabled(False)

        self.delete_button = QPushButton("🗑️ حذف")
        self.delete_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_button.setFixedHeight(28)
        self.delete_button.clicked.connect(self.delete_selected_task)
        self.delete_button.setEnabled(False)

        self.settings_button = QPushButton("⚙️")
        self.settings_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.settings_button.setFixedHeight(28)
        self.settings_button.setFixedWidth(40)
        self.settings_button.setToolTip("إعدادات المهام")
        self.settings_button.clicked.connect(self.open_settings)

        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.setFixedHeight(28)
        self.refresh_button.clicked.connect(self.refresh_tasks)

        # إضافة الأزرار للـ toolbar المتجاوب
        self.toolbar.addButton(self.add_button)
        self.toolbar.addButton(self.edit_button)
        self.toolbar.addButton(self.complete_button)
        self.toolbar.addButton(self.delete_button)
        self.toolbar.addButton(self.refresh_button)
        self.toolbar.addButton(self.settings_button)

        left_panel.addWidget(self.toolbar)

        # === فلاتر البحث ===
        filter_layout = QHBoxLayout()

        # فلتر الحالة
        self.status_filter = QComboBox()
        self.status_filter.addItem("جميع الحالات", "all")
        self.status_filter.addItem("📋 المهام النشطة", "active")
        self.status_filter.addItem("✅ المهام المنتهية", "completed")
        self.status_filter.addItem("📦 الأرشيف", "archived")
        self.status_filter.currentIndexChanged.connect(self.load_tasks)
        filter_layout.addWidget(self.status_filter)

        # فلتر الأولوية
        self.priority_filter = QComboBox()
        self.priority_filter.addItem("جميع الأولويات", "all")
        for priority in TaskPriority:
            self.priority_filter.addItem(priority.value, priority.name)
        self.priority_filter.currentIndexChanged.connect(self.load_tasks)
        filter_layout.addWidget(self.priority_filter)

        # فلتر الفئة
        self.category_filter = QComboBox()
        self.category_filter.addItem("جميع الفئات", "all")
        for category in TaskCategory:
            self.category_filter.addItem(category.value, category.name)
        self.category_filter.currentIndexChanged.connect(self.load_tasks)
        filter_layout.addWidget(self.category_filter)

        filter_layout.addStretch()
        left_panel.addLayout(filter_layout)

        # === جدول المهام ===
        table_groupbox = QGroupBox("📋 قائمة المهام")
        table_layout = QVBoxLayout()
        table_groupbox.setLayout(table_layout)

        # شريط البحث
        from ui.universal_search import UniversalSearchBar
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(6)
        self.tasks_table.setHorizontalHeaderLabels(["المهمة", "الأولوية", "الحالة", "الفئة", "تاريخ الاستحقاق", "المشروع"])

        self.search_bar = UniversalSearchBar(
            self.tasks_table,
            placeholder="🔍 بحث في المهام..."
        )
        table_layout.addWidget(self.search_bar)

        # إعدادات الجدول
        self.tasks_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.tasks_table)
        self.tasks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tasks_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tasks_table.setSortingEnabled(True)

        h_header = self.tasks_table.horizontalHeader()
        v_header = self.tasks_table.verticalHeader()
        if h_header:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # المهمة - يتمدد
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # الأولوية
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # الفئة
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # تاريخ الاستحقاق
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # المشروع - يتمدد
            h_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        if v_header:
            v_header.setDefaultSectionSize(45)
            v_header.setVisible(False)

        self.tasks_table.itemSelectionChanged.connect(self.on_task_selection_changed)
        self.tasks_table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tasks_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tasks_table.customContextMenuRequested.connect(self._on_table_context_menu)

        table_layout.addWidget(self.tasks_table)
        left_panel.addWidget(table_groupbox, 1)

        main_layout.addLayout(left_panel, 3)


        # === الجزء الأيمن (لوحة المعاينة والإحصائيات) ===
        from PyQt6.QtWidgets import QSizePolicy
        
        self.preview_groupbox = QGroupBox("📊 معاينة المهمة والإحصائيات")
        self.preview_groupbox.setMinimumWidth(280)
        # ⚡ إزالة setMaximumWidth للتجاوب التلقائي
        self.preview_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        preview_layout = QVBoxLayout()
        preview_layout.setSpacing(8)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        self.preview_groupbox.setLayout(preview_layout)

        # === بطاقات الإحصائيات - صف أول ===
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(6)

        self.total_card = self._create_stat_card("الإجمالي", "0", COLORS["primary"])
        self.today_card = self._create_stat_card("اليوم", "0", COLORS["info"])
        self.overdue_card = self._create_stat_card("متأخرة", "0", COLORS["danger"])

        stats_layout.addWidget(self.total_card)
        stats_layout.addWidget(self.today_card)
        stats_layout.addWidget(self.overdue_card)
        preview_layout.addLayout(stats_layout)

        # === بطاقات الإحصائيات - صف ثاني ===
        stats_layout2 = QHBoxLayout()
        stats_layout2.setSpacing(6)

        self.todo_card = self._create_stat_card("انتظار", "0", COLORS["secondary"])
        self.progress_card = self._create_stat_card("تنفيذ", "0", COLORS["warning"])
        self.completed_card = self._create_stat_card("مكتملة", "0", COLORS["success"])

        stats_layout2.addWidget(self.todo_card)
        stats_layout2.addWidget(self.progress_card)
        stats_layout2.addWidget(self.completed_card)
        preview_layout.addLayout(stats_layout2)

        # === شريط التقدم ===
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 5, 0, 5)
        progress_label = QLabel("الإنجاز:")
        progress_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        progress_layout.addWidget(progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 6px;
                background-color: {COLORS['bg_medium']};
                text-align: center;
                color: white;
                font-weight: bold;
                font-size: 10px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['success']}, stop:1 {COLORS['primary']});
                border-radius: 6px;
            }}
        """)
        progress_layout.addWidget(self.progress_bar, 1)
        preview_layout.addLayout(progress_layout)

        # === تفاصيل المهمة المحددة ===
        details_group = QGroupBox("📝 تفاصيل المهمة")
        details_group.setStyleSheet(f"""
            QGroupBox {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['bg_medium']},
                    stop:1 {COLORS['bg_light']});
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 2px 12px;
                background: {COLORS['primary']};
                border-radius: 6px;
                color: white;
                font-weight: bold;
            }}
        """)
        details_layout = QVBoxLayout()
        details_layout.setSpacing(10)
        details_layout.setContentsMargins(12, 20, 12, 12)
        details_group.setLayout(details_layout)

        self.task_title_label = QLabel("اختر مهمة لعرض التفاصيل")
        self.task_title_label.setStyleSheet(f"""
            color: {COLORS['text_primary']}; 
            font-size: 14px; 
            font-weight: bold; 
            padding: 8px;
            background: {COLORS['bg_light']};
            border-radius: 6px;
        """)
        self.task_title_label.setWordWrap(True)
        details_layout.addWidget(self.task_title_label)

        self.task_description_label = QLabel("")
        self.task_description_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']}; 
            font-size: 12px; 
            padding: 8px;
            background: {COLORS['bg_medium']};
            border-radius: 6px;
            border-left: 3px solid {COLORS['primary']};
        """)
        self.task_description_label.setWordWrap(True)
        self.task_description_label.setMinimumHeight(60)
        details_layout.addWidget(self.task_description_label)

        self.task_info_label = QLabel("")
        self.task_info_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; padding: 5px 0;")
        self.task_info_label.setWordWrap(True)
        details_layout.addWidget(self.task_info_label)

        preview_layout.addWidget(details_group)

        # === أزرار الإجراءات السريعة ===
        quick_actions_group = QGroupBox("⚡ إجراءات سريعة")
        quick_actions_group.setStyleSheet(f"""
            QGroupBox {{
                background: {COLORS['bg_medium']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 2px 12px;
                background: {COLORS['warning']};
                border-radius: 6px;
                color: white;
                font-weight: bold;
            }}
        """)
        quick_actions_layout = QVBoxLayout()
        quick_actions_layout.setSpacing(8)
        quick_actions_layout.setContentsMargins(10, 18, 10, 10)
        quick_actions_group.setLayout(quick_actions_layout)

        # صف أول: إكمال وقيد التنفيذ
        quick_btn_layout = QHBoxLayout()
        quick_btn_layout.setSpacing(8)

        self.quick_complete_btn = QPushButton("✅ إكمال")
        self.quick_complete_btn.setStyleSheet(BUTTON_STYLES["success"])
        self.quick_complete_btn.setMinimumHeight(36)
        self.quick_complete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.quick_complete_btn.clicked.connect(self.complete_selected_task)
        self.quick_complete_btn.setEnabled(False)
        quick_btn_layout.addWidget(self.quick_complete_btn)

        self.quick_progress_btn = QPushButton("🔄 قيد التنفيذ")
        self.quick_progress_btn.setStyleSheet(BUTTON_STYLES["warning"])
        self.quick_progress_btn.setMinimumHeight(36)
        self.quick_progress_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.quick_progress_btn.clicked.connect(self._set_in_progress)
        self.quick_progress_btn.setEnabled(False)
        quick_btn_layout.addWidget(self.quick_progress_btn)

        quick_actions_layout.addLayout(quick_btn_layout)

        # صف ثاني: أرشفة واستعادة
        archive_btn_layout = QHBoxLayout()
        archive_btn_layout.setSpacing(8)

        self.archive_btn = QPushButton("📦 أرشفة")
        self.archive_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.archive_btn.setMinimumHeight(36)
        self.archive_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.archive_btn.clicked.connect(self._archive_selected_task)
        self.archive_btn.setEnabled(False)
        archive_btn_layout.addWidget(self.archive_btn)

        self.restore_btn = QPushButton("♻️ استعادة")
        self.restore_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.restore_btn.setMinimumHeight(36)
        self.restore_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.restore_btn.clicked.connect(self._restore_selected_task)
        self.restore_btn.setEnabled(False)
        archive_btn_layout.addWidget(self.restore_btn)

        quick_actions_layout.addLayout(archive_btn_layout)
        preview_layout.addWidget(quick_actions_group)

        preview_layout.addStretch()
        main_layout.addWidget(self.preview_groupbox)


    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """إنشاء بطاقة إحصائية احترافية مع تأثيرات بصرية"""
        from PyQt6.QtWidgets import QSizePolicy
        
        card = QFrame()
        card.setFixedHeight(80)
        card.setMinimumWidth(95)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['bg_medium']},
                    stop:1 {COLORS['bg_light']});
                border: 2px solid {color};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 2px solid {color};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {color}22,
                    stop:1 {COLORS['bg_medium']});
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(2)
        card_layout.setContentsMargins(6, 8, 6, 8)

        # القيمة أولاً (أكبر)
        value_label = QLabel(value)
        value_label.setObjectName("value_label")
        value_label.setStyleSheet(f"""
            color: {color}; 
            font-size: 26px; 
            font-weight: bold; 
            background: transparent;
        """)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(value_label)

        # العنوان تحت القيمة
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']}; 
            font-size: 11px; 
            font-weight: 500; 
            background: transparent;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_label)

        return card

    def _update_stat_card(self, card: QFrame, value: str):
        """تحديث قيمة بطاقة إحصائية"""
        value_label = card.findChild(QLabel, "value_label")
        if value_label:
            value_label.setText(str(value))

    def on_task_selection_changed(self):
        """معالج تغيير اختيار المهمة"""
        # ⚡ تجاهل التحديث إذا كان الكليك يمين
        from core.context_menu import is_right_click_active
        if is_right_click_active():
            return
        
        selected_rows = self.tasks_table.selectedIndexes()
        if selected_rows:
            row = selected_rows[0].row()
            task_title_item = self.tasks_table.item(row, 0)
            if task_title_item:
                task_title = task_title_item.text()
                # البحث عن المهمة
                self.selected_task = None
                for task in self.task_service.tasks:
                    if task.title == task_title:
                        self.selected_task = task
                        break

                if self.selected_task:
                    self._update_task_preview()
                    self._update_action_buttons()
                    return

        self.selected_task = None
        self._clear_task_preview()
        self._update_action_buttons()

    def _update_task_preview(self):
        """تحديث معاينة المهمة"""
        if not self.selected_task:
            return

        task = self.selected_task
        self.task_title_label.setText(f"📝 {task.title}")
        self.task_description_label.setText(task.description or "لا يوجد وصف")

        # معلومات إضافية
        info_parts = []
        info_parts.append(f"الأولوية: {task.priority.value}")
        info_parts.append(f"الحالة: {task.status.value}")
        info_parts.append(f"الفئة: {task.category.value}")

        if task.due_date:
            due_str = task.due_date.strftime("%Y-%m-%d")
            if task.is_overdue():
                info_parts.append(f"⚠️ متأخرة: {due_str}")
            elif task.is_due_today():
                info_parts.append(f"📅 اليوم: {due_str}")
            else:
                info_parts.append(f"الاستحقاق: {due_str}")

        if task.related_project:
            project_name = self._projects_cache.get(task.related_project, task.related_project)
            info_parts.append(f"المشروع: {project_name}")

        if task.related_client:
            client_name = self._clients_cache.get(task.related_client, task.related_client)
            info_parts.append(f"العميل: {client_name}")

        self.task_info_label.setText(" | ".join(info_parts))

    def _clear_task_preview(self):
        """مسح معاينة المهمة"""
        self.task_title_label.setText("اختر مهمة لعرض التفاصيل")
        self.task_description_label.setText("")
        self.task_info_label.setText("")

    def _update_action_buttons(self):
        """تحديث حالة أزرار الإجراءات"""
        has_selection = self.selected_task is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self.quick_complete_btn.setEnabled(has_selection)
        self.quick_progress_btn.setEnabled(has_selection)
        self.archive_btn.setEnabled(has_selection)
        self.restore_btn.setEnabled(has_selection and self.selected_task.is_archived if self.selected_task else False)

        if self.selected_task:
            is_completed = self.selected_task.status == TaskStatus.COMPLETED
            self.complete_button.setEnabled(has_selection and not is_completed)
            self.quick_complete_btn.setEnabled(has_selection and not is_completed)
        else:
            self.complete_button.setEnabled(False)


    def load_tasks(self):
        """تحميل وعرض المهام في الجدول"""
        if self._is_loading:
            return

        self._is_loading = True
        from PyQt6.QtWidgets import QApplication

        try:
            self.tasks_table.setSortingEnabled(False)
            self.tasks_table.setUpdatesEnabled(False)
            self.tasks_table.blockSignals(True)
            self.tasks_table.setRowCount(0)

            # جلب المهام حسب الفلتر
            status_filter = self.status_filter.currentData()
            if status_filter == "active":
                tasks = self.task_service.get_active_tasks()
            elif status_filter == "completed":
                tasks = self.task_service.get_completed_tasks()
            elif status_filter == "archived":
                tasks = self.task_service.get_archived_tasks()
            else:
                tasks = self.task_service.get_all_tasks()

            # فلتر الأولوية
            priority_filter = self.priority_filter.currentData()
            if priority_filter != "all":
                tasks = [t for t in tasks if t.priority.name == priority_filter]

            # فلتر الفئة
            category_filter = self.category_filter.currentData()
            if category_filter != "all":
                tasks = [t for t in tasks if t.category.name == category_filter]

            # ترتيب المهام
            tasks = self._sort_tasks(tasks)

            # ⚡ تعيين عدد الصفوف مرة واحدة (أسرع من insertRow)
            self.tasks_table.setRowCount(len(tasks))

            # ملء الجدول
            for row, task in enumerate(tasks):
                # عنوان المهمة
                title_item = create_centered_item(task.title)
                if task.status == TaskStatus.COMPLETED:
                    font = title_item.font()
                    font.setStrikeOut(True)
                    title_item.setFont(font)
                self.tasks_table.setItem(row, 0, title_item)

                # الأولوية
                priority_item = self._create_priority_item(task)
                self.tasks_table.setItem(row, 1, priority_item)

                # الحالة
                status_item = self._create_status_item(task)
                self.tasks_table.setItem(row, 2, status_item)

                # الفئة
                self.tasks_table.setItem(row, 3, create_centered_item(task.category.value))

                # تاريخ الاستحقاق
                due_item = self._create_due_date_item(task)
                self.tasks_table.setItem(row, 4, due_item)

                # المشروع
                project_name = self._projects_cache.get(task.related_project, task.related_project) if task.related_project else "-"
                self.tasks_table.setItem(row, 5, create_centered_item(project_name))

            self.tasks_table.blockSignals(False)
            self.tasks_table.setUpdatesEnabled(True)
            self.tasks_table.setSortingEnabled(True)

            self.update_statistics()
            safe_print(f"INFO: [TodoManager] ✅ تم تحميل {len(tasks)} مهمة")

        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل تحميل المهام: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_loading = False
            self.tasks_table.blockSignals(False)
            self.tasks_table.setUpdatesEnabled(True)
            self.tasks_table.setSortingEnabled(True)

    def _sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """ترتيب المهام"""
        def sort_key(task):
            priority_order = {TaskPriority.URGENT: 0, TaskPriority.HIGH: 1, TaskPriority.MEDIUM: 2, TaskPriority.LOW: 3}
            status_order = {TaskStatus.IN_PROGRESS: 0, TaskStatus.TODO: 1, TaskStatus.COMPLETED: 2, TaskStatus.CANCELLED: 3}
            overdue_order = 0 if task.is_overdue() else 1
            today_order = 0 if task.is_due_today() else 1
            return (
                overdue_order,
                today_order,
                status_order.get(task.status, 4),
                priority_order.get(task.priority, 4),
                task.due_date or datetime.max
            )
        return sorted(tasks, key=sort_key)

    def _create_priority_item(self, task: Task) -> QTableWidgetItem:
        """إنشاء عنصر الأولوية"""
        priority_colors = {
            TaskPriority.LOW: "#10B981",
            TaskPriority.MEDIUM: "#0A6CF1",
            TaskPriority.HIGH: "#FF6636",
            TaskPriority.URGENT: "#FF4FD8"
        }
        priority_icons = {
            TaskPriority.LOW: "🟢",
            TaskPriority.MEDIUM: "🟡",
            TaskPriority.HIGH: "🟠",
            TaskPriority.URGENT: "🔴"
        }

        item = QTableWidgetItem(f"{priority_icons.get(task.priority, '')} {task.priority.value}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(QColor(priority_colors.get(task.priority, COLORS['text_primary'])))
        return item

    def _create_status_item(self, task: Task) -> QTableWidgetItem:
        """إنشاء عنصر الحالة"""
        status_colors = {
            TaskStatus.TODO: COLORS["text_secondary"],
            TaskStatus.IN_PROGRESS: COLORS["warning"],
            TaskStatus.COMPLETED: COLORS["success"],
            TaskStatus.CANCELLED: COLORS["danger"]
        }
        status_icons = {
            TaskStatus.TODO: "⏳",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.CANCELLED: "❌"
        }

        item = QTableWidgetItem(f"{status_icons.get(task.status, '')} {task.status.value}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(QColor(status_colors.get(task.status, COLORS['text_primary'])))
        return item

    def _create_due_date_item(self, task: Task) -> QTableWidgetItem:
        """إنشاء عنصر تاريخ الاستحقاق"""
        if not task.due_date:
            item = QTableWidgetItem("-")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            return item

        due_str = task.due_date.strftime("%Y-%m-%d")

        if task.is_overdue():
            item = QTableWidgetItem(f"⚠️ {due_str}")
            item.setForeground(QColor(COLORS["danger"]))
        elif task.is_due_today():
            item = QTableWidgetItem(f"📅 {due_str}")
            item.setForeground(QColor(COLORS["warning"]))
        else:
            item = QTableWidgetItem(due_str)

        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item


    def update_statistics(self):
        """تحديث الإحصائيات"""
        stats = self.task_service.get_statistics()

        self._update_stat_card(self.total_card, str(stats["total"]))
        self._update_stat_card(self.today_card, str(stats["today"]))
        self._update_stat_card(self.overdue_card, str(stats["overdue"]))
        self._update_stat_card(self.todo_card, str(stats["todo"]))
        self._update_stat_card(self.progress_card, str(stats["in_progress"]))
        self._update_stat_card(self.completed_card, str(stats["completed"]))

        self.progress_bar.setValue(int(stats["completion_rate"]))

    def add_task(self):
        """إضافة مهمة جديدة"""
        try:
            dialog = TaskEditorDialog(
                parent=self,
                project_service=self.project_service,
                client_service=self.client_service,
                default_settings=self.task_service.settings
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                task = dialog.get_task()
                if task:
                    self.task_service.add_task(task)
                    self.load_tasks()
                    QMessageBox.information(self, "تم", f"تم إضافة المهمة: {task.title} ✅")
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل إضافة المهمة: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل إضافة المهمة: {e}")

    def edit_selected_task(self):
        """تعديل المهمة المحددة"""
        if not self.selected_task:
            QMessageBox.information(self, "تنبيه", "الرجاء اختيار مهمة أولاً")
            return

        try:
            dialog = TaskEditorDialog(
                task=self.selected_task,
                parent=self,
                project_service=self.project_service,
                client_service=self.client_service,
                default_settings=self.task_service.settings
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                updated_task = dialog.get_task()
                if updated_task:
                    self.task_service.update_task(updated_task)
                    self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل تعديل المهمة: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل تعديل المهمة: {e}")

    def complete_selected_task(self):
        """إكمال المهمة المحددة"""
        if not self.selected_task:
            return

        try:
            self.selected_task.status = TaskStatus.COMPLETED
            self.selected_task.completed_at = datetime.now()
            self.task_service.update_task(self.selected_task)
            self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل إكمال المهمة: {e}")

    def _set_in_progress(self):
        """تعيين المهمة كقيد التنفيذ"""
        if not self.selected_task:
            return

        try:
            self.selected_task.status = TaskStatus.IN_PROGRESS
            self.selected_task.completed_at = None
            self.task_service.update_task(self.selected_task)
            self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل تغيير حالة المهمة: {e}")

    def _archive_selected_task(self):
        """أرشفة المهمة المحددة"""
        if not self.selected_task:
            return

        try:
            self.selected_task.is_archived = True
            self.task_service.update_task(self.selected_task)
            self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل أرشفة المهمة: {e}")

    def _restore_selected_task(self):
        """استعادة المهمة المحددة من الأرشيف"""
        if not self.selected_task:
            return

        try:
            self.selected_task.is_archived = False
            self.task_service.update_task(self.selected_task)
            self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل استعادة المهمة: {e}")

    def delete_selected_task(self):
        """حذف المهمة المحددة"""
        if not self.selected_task:
            QMessageBox.information(self, "تنبيه", "الرجاء اختيار مهمة أولاً")
            return

        try:
            reply = QMessageBox.question(
                self, "تأكيد الحذف",
                f"هل أنت متأكد من حذف المهمة:\n{self.selected_task.title}؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.task_service.delete_task(self.selected_task.id)
                self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل حذف المهمة: {e}")

    def refresh_tasks(self):
        """تحديث قائمة المهام"""
        try:
            self._cache_loaded = False
            self._load_projects_clients_cache()
            self.task_service.refresh()
            self.load_tasks()
            QMessageBox.information(self, "تم", "تم تحديث قائمة المهام ✅")
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل تحديث المهام: {e}")

    def open_settings(self):
        """فتح نافذة الإعدادات"""
        try:
            dialog = TaskSettingsDialog(self.task_service.settings, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_settings = dialog.get_settings()
                if new_settings:
                    self.task_service.settings = new_settings
                    QMessageBox.information(self, "تم", "تم حفظ الإعدادات بنجاح ✅")
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل فتح الإعدادات: {e}")

    def check_reminders(self):
        """فحص التذكيرات"""
        try:
            tasks_to_remind = self.task_service.get_tasks_needing_reminder()
            for task in tasks_to_remind:
                QMessageBox.information(
                    self, "⏰ تذكير",
                    f"المهمة '{task.title}' مستحقة خلال {task.reminder_minutes} دقيقة!"
                )
                task.reminder = False
                self.task_service.update_task(task)
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل فحص التذكيرات: {e}")


    def _on_item_double_clicked(self, item):
        """معالجة الضغط المزدوج على عنصر"""
        if item:
            self.edit_selected_task()

    def _on_table_context_menu(self, pos):
        """عرض قائمة السياق عند الضغط بالزر الأيمن"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction

        item = self.tasks_table.itemAt(pos)
        if not item:
            return

        row = item.row()
        task_title_item = self.tasks_table.item(row, 0)
        if not task_title_item:
            return

        task_title = task_title_item.text()
        task = None
        for t in self.task_service.tasks:
            if t.title == task_title:
                task = t
                break

        if not task:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                color: white;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #334155;
            }
            QMenu::separator {
                height: 1px;
                background: #334155;
                margin: 4px 8px;
            }
        """)

        # قائمة فرعية لتغيير الحالة
        status_menu = menu.addMenu("🔄 تغيير الحالة")
        status_options = [
            ("⏳ قيد الانتظار", TaskStatus.TODO),
            ("🔄 قيد التنفيذ", TaskStatus.IN_PROGRESS),
            ("✅ مكتملة", TaskStatus.COMPLETED),
            ("❌ ملغاة", TaskStatus.CANCELLED),
        ]

        for display_text, status in status_options:
            action = QAction(display_text, status_menu)
            if task.status == status:
                action.setEnabled(False)
                action.setText(f"✓ {display_text}")
            action.triggered.connect(
                lambda checked, t=task, s=status: self._change_task_status(t, s)
            )
            status_menu.addAction(action)

        # قائمة فرعية لتغيير الأولوية
        priority_menu = menu.addMenu("⚡ تغيير الأولوية")
        priority_options = [
            ("🟢 منخفضة", TaskPriority.LOW),
            ("🟡 متوسطة", TaskPriority.MEDIUM),
            ("🟠 عالية", TaskPriority.HIGH),
            ("🔴 عاجلة", TaskPriority.URGENT),
        ]

        for display_text, priority in priority_options:
            action = QAction(display_text, priority_menu)
            if task.priority == priority:
                action.setEnabled(False)
                action.setText(f"✓ {display_text}")
            action.triggered.connect(
                lambda checked, t=task, p=priority: self._change_task_priority(t, p)
            )
            priority_menu.addAction(action)

        menu.addSeparator()

        # خيارات أخرى
        edit_action = QAction("✏️ تعديل المهمة", menu)
        edit_action.triggered.connect(self.edit_selected_task)
        menu.addAction(edit_action)

        if not task.is_archived:
            archive_action = QAction("📦 أرشفة", menu)
            archive_action.triggered.connect(lambda: self._archive_task(task))
            menu.addAction(archive_action)
        else:
            restore_action = QAction("♻️ استعادة", menu)
            restore_action.triggered.connect(lambda: self._restore_task(task))
            menu.addAction(restore_action)

        menu.addSeparator()

        delete_action = QAction("🗑️ حذف", menu)
        delete_action.triggered.connect(lambda: self._delete_task(task))
        menu.addAction(delete_action)

        menu.exec(self.tasks_table.viewport().mapToGlobal(pos))

    def _change_task_status(self, task: Task, new_status: TaskStatus):
        """تغيير حالة المهمة"""
        try:
            task.status = new_status
            if new_status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now()
            else:
                task.completed_at = None
            self.task_service.update_task(task)
            self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل تغيير حالة المهمة: {e}")

    def _change_task_priority(self, task: Task, new_priority: TaskPriority):
        """تغيير أولوية المهمة"""
        try:
            task.priority = new_priority
            self.task_service.update_task(task)
            self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل تغيير أولوية المهمة: {e}")

    def _archive_task(self, task: Task):
        """أرشفة مهمة"""
        try:
            task.is_archived = True
            self.task_service.update_task(task)
            self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل أرشفة المهمة: {e}")

    def _restore_task(self, task: Task):
        """استعادة مهمة"""
        try:
            task.is_archived = False
            self.task_service.update_task(task)
            self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل استعادة المهمة: {e}")

    def _delete_task(self, task: Task):
        """حذف مهمة"""
        try:
            reply = QMessageBox.question(
                self, "تأكيد الحذف",
                f"هل أنت متأكد من حذف المهمة:\n{task.title}؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.task_service.delete_task(task.id)
                self.load_tasks()
        except Exception as e:
            safe_print(f"ERROR: [TodoManager] فشل حذف المهمة: {e}")


# للاختبار المستقل
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyleSheet(f"""
        QWidget {{
            background-color: {COLORS['bg_dark']};
            color: {COLORS['text_primary']};
            font-family: 'Cairo';
        }}
    """)

    window = TodoManagerWidget()
    window.setWindowTitle("نظام إدارة المهام - Sky Wave ERP")
    window.resize(1200, 800)
    window.show()

    sys.exit(app.exec())
