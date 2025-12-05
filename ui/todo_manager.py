#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نظام إدارة المهام الاحترافي - Sky Wave ERP
Professional TODO Management System
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QDialog, QFormLayout, QMessageBox, QGroupBox, QCheckBox,
    QProgressBar, QSplitter, QListWidget, QListWidgetItem,
    QGraphicsDropShadowEffect, QScrollArea, QMenu, QSpinBox
)
from PyQt6.QtCore import Qt, QDate, QTime, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QCursor, QIcon, QAction
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from enum import Enum
from dataclasses import dataclass, field
import json
import os

# ألوان SkyWave Brand
COLORS = {
    "primary": "#0A6CF1",
    "secondary": "#6B7280",
    "success": "#10B981",
    "warning": "#FF6636",
    "danger": "#FF4FD8",
    "info": "#8B2CF5",
    "bg_dark": "#001A3A",
    "bg_medium": "#0A2A55",
    "bg_light": "#052045",
    "text_primary": "#EAF3FF",
    "text_secondary": "#B0C4DE",
    "border": "#1E3A5F",
}


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


@dataclass
class Task:
    """نموذج المهمة"""
    id: str
    title: str
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    category: TaskCategory = TaskCategory.GENERAL
    due_date: Optional[datetime] = None
    due_time: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    related_project: str = ""
    related_client: str = ""
    tags: List[str] = field(default_factory=list)
    reminder: bool = False
    reminder_minutes: int = 30
    
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
            "reminder_minutes": self.reminder_minutes
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
            reminder_minutes=data.get("reminder_minutes", 30)
        )


class TaskService:
    """
    خدمة إدارة المهام - مرتبطة بقاعدة البيانات
    تستخدم Repository للحفظ في SQLite و MongoDB
    """
    
    _instance = None
    _repository = None
    
    def __new__(cls, repository=None):
        """Singleton pattern لضمان استخدام نفس الـ instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, repository=None):
        if self._initialized:
            return
        
        self._initialized = True
        self.tasks: List[Task] = []
        
        # استخدام Repository المُمرر أو إنشاء واحد جديد
        if repository:
            self._repository = repository
        else:
            try:
                from core.repository import Repository
                self._repository = Repository()
            except Exception as e:
                print(f"WARNING: [TaskService] فشل الاتصال بقاعدة البيانات: {e}")
                self._repository = None
        
        self.load_tasks()
    
    @classmethod
    def set_repository(cls, repository):
        """تعيين Repository من الخارج"""
        cls._repository = repository
        if cls._instance:
            cls._instance.load_tasks()
    
    def load_tasks(self):
        """تحميل المهام من قاعدة البيانات"""
        try:
            if self._repository:
                tasks_data = self._repository.get_all_tasks()
                self.tasks = [self._dict_to_task(t) for t in tasks_data]
                print(f"INFO: [TaskService] تم تحميل {len(self.tasks)} مهمة من قاعدة البيانات")
            else:
                # Fallback للملف المحلي إذا لم يكن هناك Repository
                self._load_from_file()
        except Exception as e:
            print(f"ERROR: [TaskService] فشل تحميل المهام: {e}")
            self.tasks = []
    
    def _load_from_file(self):
        """تحميل من ملف JSON (للتوافق مع الإصدارات القديمة)"""
        storage_path = "tasks.json"
        try:
            if os.path.exists(storage_path):
                with open(storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(t) for t in data]
                print(f"INFO: [TaskService] تم تحميل {len(self.tasks)} مهمة من الملف المحلي")
        except Exception as e:
            print(f"ERROR: [TaskService] فشل تحميل المهام من الملف: {e}")
            self.tasks = []
    
    def _dict_to_task(self, data: dict) -> Task:
        """تحويل dict من قاعدة البيانات إلى Task object"""
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
                tags=data.get('tags', []),
                reminder=data.get('reminder', False),
                reminder_minutes=data.get('reminder_minutes', 30)
            )
        except Exception as e:
            print(f"ERROR: [TaskService] فشل تحويل المهمة: {e}")
            return Task(id=str(data.get('id', '')), title=data.get('title', 'مهمة'))
    
    def _task_to_dict(self, task: Task) -> dict:
        """تحويل Task object إلى dict لقاعدة البيانات"""
        return {
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'priority': task.priority.name,
            'status': task.status.name,
            'category': task.category.name,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'due_time': task.due_time,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'related_project_id': task.related_project,
            'related_client_id': task.related_client,
            'tags': task.tags,
            'reminder': task.reminder,
            'reminder_minutes': task.reminder_minutes
        }
    
    def add_task(self, task: Task) -> Task:
        """إضافة مهمة جديدة"""
        try:
            if self._repository:
                task_dict = self._task_to_dict(task)
                result = self._repository.create_task(task_dict)
                task.id = result.get('id', task.id)
            
            self.tasks.append(task)
            # ⚡ إرسال إشارة التحديث
            try:
                from core.signals import app_signals
                app_signals.emit_data_changed('tasks')
            except Exception:
                pass
            print(f"INFO: [TaskService] تم إضافة مهمة: {task.title}")
            return task
        except Exception as e:
            print(f"ERROR: [TaskService] فشل إضافة المهمة: {e}")
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
            
            # ⚡ إرسال إشارة التحديث
            try:
                from core.signals import app_signals
                app_signals.emit_data_changed('tasks')
            except Exception:
                pass
            print(f"INFO: [TaskService] تم تحديث مهمة: {task.title}")
        except Exception as e:
            print(f"ERROR: [TaskService] فشل تحديث المهمة: {e}")
    
    def delete_task(self, task_id: str):
        """حذف مهمة"""
        try:
            if self._repository:
                self._repository.delete_task(task_id)
            
            self.tasks = [t for t in self.tasks if t.id != task_id]
            # ⚡ إرسال إشارة التحديث
            try:
                from core.signals import app_signals
                app_signals.emit_data_changed('tasks')
            except Exception:
                pass
            print(f"INFO: [TaskService] تم حذف مهمة (ID: {task_id})")
        except Exception as e:
            print(f"ERROR: [TaskService] فشل حذف المهمة: {e}")
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """الحصول على مهمة بالـ ID"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_all_tasks(self) -> List[Task]:
        """الحصول على جميع المهام"""
        return self.tasks
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """الحصول على المهام حسب الحالة"""
        return [t for t in self.tasks if t.status == status]
    
    def get_tasks_by_priority(self, priority: TaskPriority) -> List[Task]:
        """الحصول على المهام حسب الأولوية"""
        return [t for t in self.tasks if t.priority == priority]
    
    def get_overdue_tasks(self) -> List[Task]:
        """الحصول على المهام المتأخرة"""
        now = datetime.now()
        return [t for t in self.tasks 
                if t.due_date and t.due_date < now and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]]
    
    def get_today_tasks(self) -> List[Task]:
        """الحصول على مهام اليوم"""
        today = datetime.now().date()
        return [t for t in self.tasks 
                if t.due_date and t.due_date.date() == today]
    
    def get_upcoming_tasks(self, days: int = 7) -> List[Task]:
        """الحصول على المهام القادمة"""
        now = datetime.now()
        end_date = now + timedelta(days=days)
        return [t for t in self.tasks 
                if t.due_date and now <= t.due_date <= end_date 
                and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]]
    
    def get_tasks_by_project(self, project_id: str) -> List[Task]:
        """الحصول على المهام المرتبطة بمشروع"""
        return [t for t in self.tasks if t.related_project == project_id]
    
    def get_tasks_by_client(self, client_id: str) -> List[Task]:
        """الحصول على المهام المرتبطة بعميل"""
        return [t for t in self.tasks if t.related_client == client_id]
    
    def get_statistics(self) -> Dict:
        """الحصول على إحصائيات المهام"""
        total = len(self.tasks)
        completed = len([t for t in self.tasks if t.status == TaskStatus.COMPLETED])
        in_progress = len([t for t in self.tasks if t.status == TaskStatus.IN_PROGRESS])
        todo = len([t for t in self.tasks if t.status == TaskStatus.TODO])
        overdue = len(self.get_overdue_tasks())
        
        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "todo": todo,
            "overdue": overdue,
            "completion_rate": (completed / total * 100) if total > 0 else 0
        }
    
    def generate_id(self) -> str:
        """توليد ID فريد"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def refresh(self):
        """تحديث المهام من قاعدة البيانات"""
        self.load_tasks()



class TaskItemWidget(QFrame):
    """ويدجت عرض مهمة واحدة"""
    
    clicked = pyqtSignal(str)
    status_changed = pyqtSignal(str, TaskStatus)
    delete_requested = pyqtSignal(str)
    
    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self.init_ui()
    
    def init_ui(self):
        """تهيئة الواجهة"""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # تحديد الألوان حسب الأولوية والحالة
        priority_colors = {
            TaskPriority.LOW: "#10B981",
            TaskPriority.MEDIUM: "#0A6CF1",
            TaskPriority.HIGH: "#FF6636",
            TaskPriority.URGENT: "#FF4FD8"
        }
        border_color = priority_colors.get(self.task.priority, COLORS["primary"])
        
        # تحديد الخلفية حسب الحالة
        if self.task.status == TaskStatus.COMPLETED:
            bg_color = f"{COLORS['bg_medium']}80"
            opacity = "0.7"
        else:
            bg_color = COLORS["bg_dark"]
            opacity = "1"
        
        self.setStyleSheet(f"""
            TaskItemWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {bg_color}, stop:1 {COLORS['bg_light']});
                border-left: 5px solid {border_color};
                border-radius: 12px;
                padding: 12px;
                margin: 4px 2px;
            }}
            TaskItemWidget:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['bg_light']}, stop:1 {COLORS['bg_medium']});
            }}
        """)
        
        # إضافة ظل
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # الصف الأول: Checkbox + العنوان + الأولوية
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        # Checkbox للإكمال
        self.complete_checkbox = QCheckBox()
        self.complete_checkbox.setChecked(self.task.status == TaskStatus.COMPLETED)
        self.complete_checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 22px;
                height: 22px;
                border-radius: 11px;
                border: 2px solid {border_color};
                background-color: {COLORS['bg_medium']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {border_color};
                image: url(none);
            }}
        """)
        self.complete_checkbox.stateChanged.connect(self._on_checkbox_changed)
        header_layout.addWidget(self.complete_checkbox)
        
        # العنوان
        title_label = QLabel(self.task.title)
        title_font = QFont("Segoe UI", 12)
        title_font.setBold(True)
        if self.task.status == TaskStatus.COMPLETED:
            title_font.setStrikeOut(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {COLORS['text_primary']}; background: transparent;")
        header_layout.addWidget(title_label, 1)
        
        # شارة الأولوية
        priority_badge = QLabel(self.task.priority.value)
        priority_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {border_color};
                color: white;
                padding: 4px 10px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        header_layout.addWidget(priority_badge)
        
        # زر الحذف
        delete_btn = QPushButton("✕")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_secondary']};
                border: none;
                border-radius: 12px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['danger']};
                color: white;
            }}
        """)
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.task.id))
        header_layout.addWidget(delete_btn)
        
        layout.addLayout(header_layout)
        
        # الصف الثاني: الوصف (إذا وجد)
        if self.task.description:
            desc_label = QLabel(self.task.description[:100] + "..." if len(self.task.description) > 100 else self.task.description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; padding-right: 32px; background: transparent;")
            layout.addWidget(desc_label)
        
        # الصف الثالث: المعلومات الإضافية
        info_layout = QHBoxLayout()
        info_layout.setSpacing(15)
        
        # الفئة
        category_label = QLabel(f"📁 {self.task.category.value}")
        category_label.setStyleSheet(f"color: {COLORS['info']}; font-size: 10px; background: transparent;")
        info_layout.addWidget(category_label)
        
        # تاريخ الاستحقاق
        if self.task.due_date:
            due_str = self.task.due_date.strftime("%Y-%m-%d")
            if self.task.due_time:
                due_str += f" {self.task.due_time}"
            
            # تحديد لون التاريخ
            if self.task.due_date < datetime.now() and self.task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                due_color = COLORS["danger"]
                due_icon = "⚠️"
            elif self.task.due_date.date() == datetime.now().date():
                due_color = COLORS["warning"]
                due_icon = "📅"
            else:
                due_color = COLORS["text_secondary"]
                due_icon = "📅"
            
            due_label = QLabel(f"{due_icon} {due_str}")
            due_label.setStyleSheet(f"color: {due_color}; font-size: 10px; background: transparent;")
            info_layout.addWidget(due_label)
        
        # المشروع المرتبط
        if self.task.related_project:
            project_label = QLabel(f"📋 {self.task.related_project}")
            project_label.setStyleSheet(f"color: {COLORS['primary']}; font-size: 10px; background: transparent;")
            info_layout.addWidget(project_label)
        
        info_layout.addStretch()
        
        # الحالة
        status_label = QLabel(self.task.status.value)
        status_colors = {
            TaskStatus.TODO: COLORS["text_secondary"],
            TaskStatus.IN_PROGRESS: COLORS["warning"],
            TaskStatus.COMPLETED: COLORS["success"],
            TaskStatus.CANCELLED: COLORS["danger"]
        }
        status_label.setStyleSheet(f"color: {status_colors.get(self.task.status, COLORS['text_secondary'])}; font-size: 10px; font-weight: bold; background: transparent;")
        info_layout.addWidget(status_label)
        
        layout.addLayout(info_layout)
        
        self.setLayout(layout)
    
    def _on_checkbox_changed(self, state):
        """معالج تغيير حالة الـ checkbox"""
        if state == Qt.CheckState.Checked.value:
            self.status_changed.emit(self.task.id, TaskStatus.COMPLETED)
        else:
            self.status_changed.emit(self.task.id, TaskStatus.TODO)
    
    def mousePressEvent(self, event):
        """معالج الضغط على المهمة (لا يفتح التعديل - فقط للتحديد)"""
        super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """معالج الدابل كليك على المهمة - يفتح نافذة التعديل"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.task.id)
        super().mouseDoubleClickEvent(event)


class TaskEditorDialog(QDialog):
    """نافذة إضافة/تعديل مهمة"""
    
    def __init__(self, task: Optional[Task] = None, parent=None):
        super().__init__(parent)
        self.task = task
        self.is_editing = task is not None
        self.result_task: Optional[Task] = None
        
        self.setWindowTitle("تعديل مهمة" if self.is_editing else "مهمة جديدة")
        self.setMinimumWidth(500)
        self.setMinimumHeight(550)
        
        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar
            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            # الدالة غير متوفرة
            pass
        
        self.init_ui()
        
        if self.is_editing:
            self.load_task_data()
    
    def init_ui(self):
        """تهيئة الواجهة"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # العنوان
        header_label = QLabel("✏️ تعديل مهمة" if self.is_editing else "➕ إضافة مهمة جديدة")
        header_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: bold;
                color: {COLORS['primary']};
                padding: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['bg_light']}, stop:1 {COLORS['bg_medium']});
                border-radius: 8px;
            }}
        """)
        layout.addWidget(header_label)
        
        # نموذج الإدخال
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        # عنوان المهمة
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("أدخل عنوان المهمة...")
        self.title_input.setStyleSheet(self._get_input_style())
        form_layout.addRow("العنوان:", self.title_input)
        
        # الوصف
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("أدخل وصف المهمة (اختياري)...")
        self.description_input.setMaximumHeight(100)
        self.description_input.setStyleSheet(self._get_input_style())
        form_layout.addRow("الوصف:", self.description_input)
        
        # الأولوية
        self.priority_combo = QComboBox()
        for priority in TaskPriority:
            self.priority_combo.addItem(priority.value, priority)
        self.priority_combo.setCurrentIndex(1)  # متوسطة افتراضياً
        self.priority_combo.setStyleSheet(self._get_input_style())
        form_layout.addRow("الأولوية:", self.priority_combo)
        
        # الفئة
        self.category_combo = QComboBox()
        for category in TaskCategory:
            self.category_combo.addItem(category.value, category)
        self.category_combo.setStyleSheet(self._get_input_style())
        form_layout.addRow("الفئة:", self.category_combo)
        
        # تاريخ الاستحقاق
        date_layout = QHBoxLayout()
        self.due_date_input = QDateEdit()
        self.due_date_input.setCalendarPopup(True)
        self.due_date_input.setDate(QDate.currentDate().addDays(1))
        self.due_date_input.setStyleSheet(self._get_input_style())
        date_layout.addWidget(self.due_date_input)
        
        self.due_time_input = QTimeEdit()
        self.due_time_input.setTime(QTime(12, 0))
        self.due_time_input.setStyleSheet(self._get_input_style())
        date_layout.addWidget(self.due_time_input)
        
        form_layout.addRow("تاريخ الاستحقاق:", date_layout)
        
        # المشروع المرتبط
        self.project_input = QLineEdit()
        self.project_input.setPlaceholderText("اسم المشروع (اختياري)...")
        self.project_input.setStyleSheet(self._get_input_style())
        form_layout.addRow("المشروع:", self.project_input)
        
        # العميل المرتبط
        self.client_input = QLineEdit()
        self.client_input.setPlaceholderText("اسم العميل (اختياري)...")
        self.client_input.setStyleSheet(self._get_input_style())
        form_layout.addRow("العميل:", self.client_input)
        
        # التذكير
        reminder_layout = QHBoxLayout()
        self.reminder_checkbox = QCheckBox("تفعيل التذكير")
        self.reminder_checkbox.setStyleSheet(f"color: {COLORS['text_primary']};")
        reminder_layout.addWidget(self.reminder_checkbox)
        
        self.reminder_minutes = QSpinBox()
        self.reminder_minutes.setRange(5, 1440)
        self.reminder_minutes.setValue(30)
        self.reminder_minutes.setSuffix(" دقيقة قبل")
        self.reminder_minutes.setStyleSheet(self._get_input_style())
        reminder_layout.addWidget(self.reminder_minutes)
        
        form_layout.addRow("التذكير:", reminder_layout)
        
        layout.addLayout(form_layout)
        
        # أزرار التحكم
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        save_btn = QPushButton("💾 حفظ")
        save_btn.setStyleSheet(self._get_button_style(COLORS["primary"]))
        save_btn.clicked.connect(self.save_task)
        buttons_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setStyleSheet(self._get_button_style(COLORS["secondary"]))
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def _get_input_style(self) -> str:
        return f"""
            QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit, QSpinBox {{
                background-color: {COLORS['bg_medium']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus, QSpinBox:focus {{
                border: 2px solid {COLORS['primary']};
            }}
        """
    
    def _get_button_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {color}CC;
            }}
        """
    
    def load_task_data(self):
        """تحميل بيانات المهمة للتعديل"""
        if not self.task:
            return
        
        self.title_input.setText(self.task.title)
        self.description_input.setText(self.task.description)
        
        # الأولوية
        for i in range(self.priority_combo.count()):
            if self.priority_combo.itemData(i) == self.task.priority:
                self.priority_combo.setCurrentIndex(i)
                break
        
        # الفئة
        for i in range(self.category_combo.count()):
            if self.category_combo.itemData(i) == self.task.category:
                self.category_combo.setCurrentIndex(i)
                break
        
        # التاريخ والوقت
        if self.task.due_date:
            self.due_date_input.setDate(QDate(self.task.due_date.year, self.task.due_date.month, self.task.due_date.day))
        if self.task.due_time:
            parts = self.task.due_time.split(":")
            if len(parts) >= 2:
                self.due_time_input.setTime(QTime(int(parts[0]), int(parts[1])))
        
        self.project_input.setText(self.task.related_project)
        self.client_input.setText(self.task.related_client)
        self.reminder_checkbox.setChecked(self.task.reminder)
        self.reminder_minutes.setValue(self.task.reminder_minutes)
    
    def save_task(self):
        """حفظ المهمة"""
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال عنوان المهمة")
            return
        
        # إنشاء أو تحديث المهمة
        if self.is_editing:
            task_id = self.task.id
            created_at = self.task.created_at
            status = self.task.status
            completed_at = self.task.completed_at
        else:
            import uuid
            task_id = str(uuid.uuid4())[:8]
            created_at = datetime.now()
            status = TaskStatus.TODO
            completed_at = None
        
        due_date = self.due_date_input.date().toPyDate()
        due_datetime = datetime.combine(due_date, datetime.min.time())
        due_time = self.due_time_input.time().toString("HH:mm")
        
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
            related_project=self.project_input.text().strip(),
            related_client=self.client_input.text().strip(),
            reminder=self.reminder_checkbox.isChecked(),
            reminder_minutes=self.reminder_minutes.value()
        )
        
        self.accept()
    
    def get_task(self) -> Optional[Task]:
        return self.result_task



class TodoManagerWidget(QWidget):
    """
    ويدجت إدارة المهام الاحترافي
    Professional TODO Manager Widget
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.task_service = TaskService()
        self.current_filter = "all"
        self.init_ui()
        self.load_tasks()
        
        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث القائمة أوتوماتيك)
        try:
            from core.signals import app_signals
            app_signals.tasks_changed.connect(self._on_tasks_changed)
        except Exception as e:
            print(f"WARNING: [TodoManager] فشل ربط الإشارات: {e}")
        
        # تحديث دوري للمهام المتأخرة
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.check_reminders)
        self.update_timer.start(60000)  # كل دقيقة
    
    def _on_tasks_changed(self):
        """معالج تحديث المهام من مصدر خارجي"""
        self.task_service.load_tasks()
        self.load_tasks()
    
    def init_ui(self):
        """تهيئة الواجهة"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # === 1. الهيدر ===
        header_layout = QHBoxLayout()
        
        # العنوان
        title_label = QLabel("📋 إدارة المهام")
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 22px;
                font-weight: bold;
                color: {COLORS['text_primary']};
            }}
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # زر إضافة مهمة
        add_btn = QPushButton("➕ مهمة جديدة")
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary']}, stop:1 #005BC5);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #005BC5, stop:1 {COLORS['primary']});
            }}
        """)
        add_btn.clicked.connect(self.add_task)
        header_layout.addWidget(add_btn)
        
        layout.addLayout(header_layout)
        
        # === 2. بطاقات الإحصائيات ===
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)
        
        self.total_card = self._create_stat_card("📊 الإجمالي", "0", COLORS["primary"])
        self.todo_card = self._create_stat_card("⏳ قيد الانتظار", "0", COLORS["text_secondary"])
        self.progress_card = self._create_stat_card("🔄 قيد التنفيذ", "0", COLORS["warning"])
        self.completed_card = self._create_stat_card("✅ مكتملة", "0", COLORS["success"])
        self.overdue_card = self._create_stat_card("⚠️ متأخرة", "0", COLORS["danger"])
        
        stats_layout.addWidget(self.total_card)
        stats_layout.addWidget(self.todo_card)
        stats_layout.addWidget(self.progress_card)
        stats_layout.addWidget(self.completed_card)
        stats_layout.addWidget(self.overdue_card)
        
        layout.addLayout(stats_layout)
        
        # === 3. شريط البحث والفلاتر ===
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        # البحث
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 بحث في المهام...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_medium']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 15px;
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {COLORS['primary']};
            }}
        """)
        self.search_input.textChanged.connect(self.filter_tasks)
        filter_layout.addWidget(self.search_input, 2)
        
        # فلتر الحالة
        self.status_filter = QComboBox()
        self.status_filter.addItem("جميع الحالات", "all")
        self.status_filter.addItem("⏳ قيد الانتظار", TaskStatus.TODO.name)
        self.status_filter.addItem("🔄 قيد التنفيذ", TaskStatus.IN_PROGRESS.name)
        self.status_filter.addItem("✅ مكتملة", TaskStatus.COMPLETED.name)
        self.status_filter.addItem("⚠️ متأخرة", "overdue")
        self.status_filter.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['bg_medium']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px;
                color: {COLORS['text_primary']};
                min-width: 150px;
            }}
        """)
        self.status_filter.currentIndexChanged.connect(self.filter_tasks)
        filter_layout.addWidget(self.status_filter)
        
        # فلتر الأولوية
        self.priority_filter = QComboBox()
        self.priority_filter.addItem("جميع الأولويات", "all")
        for priority in TaskPriority:
            self.priority_filter.addItem(priority.value, priority.name)
        self.priority_filter.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['bg_medium']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px;
                color: {COLORS['text_primary']};
                min-width: 150px;
            }}
        """)
        self.priority_filter.currentIndexChanged.connect(self.filter_tasks)
        filter_layout.addWidget(self.priority_filter)
        
        layout.addLayout(filter_layout)
        
        # === 4. قائمة المهام ===
        self.tasks_scroll = QScrollArea()
        self.tasks_scroll.setWidgetResizable(True)
        self.tasks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tasks_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['bg_medium']};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['primary']};
                border-radius: 4px;
                min-height: 30px;
            }}
        """)
        
        self.tasks_container = QWidget()
        self.tasks_container.setStyleSheet("background-color: transparent;")
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setSpacing(8)
        self.tasks_layout.setContentsMargins(5, 5, 5, 5)
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.tasks_scroll.setWidget(self.tasks_container)
        layout.addWidget(self.tasks_scroll)
        
        # رسالة عدم وجود مهام
        self.no_tasks_label = QLabel("📭 لا توجد مهام\n\nاضغط على 'مهمة جديدة' لإضافة مهمتك الأولى")
        self.no_tasks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_tasks_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_secondary']};
                font-size: 16px;
                padding: 50px;
                background-color: {COLORS['bg_light']};
                border-radius: 12px;
            }}
        """)
        self.no_tasks_label.setVisible(False)
        layout.addWidget(self.no_tasks_label)
        
        # === 5. شريط التقدم ===
        progress_layout = QHBoxLayout()
        
        progress_label = QLabel("نسبة الإنجاز:")
        progress_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        progress_layout.addWidget(progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 8px;
                background-color: {COLORS['bg_medium']};
                height: 16px;
                text-align: center;
                color: white;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['success']}, stop:1 {COLORS['primary']});
                border-radius: 8px;
            }}
        """)
        progress_layout.addWidget(self.progress_bar, 1)
        
        layout.addLayout(progress_layout)
        
        self.setLayout(layout)
    
    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """إنشاء بطاقة إحصائية"""
        card = QFrame()
        card.setFixedHeight(100)  # ارتفاع أكبر للوضوح
        card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['bg_light']}, stop:1 {COLORS['bg_medium']});
                border: 1px solid {color}40;
                border-left: 3px solid {color};
                border-radius: 8px;
                padding: 5px;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)
        card_layout.setContentsMargins(12, 10, 12, 10)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px; background: transparent;")
        card_layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setObjectName("value_label")
        value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold; background: transparent;")
        card_layout.addWidget(value_label)
        
        return card
    
    def _update_stat_card(self, card: QFrame, value: str):
        """تحديث قيمة بطاقة إحصائية"""
        value_label = card.findChild(QLabel, "value_label")
        if value_label:
            value_label.setText(value)
    
    def load_tasks(self):
        """تحميل وعرض المهام"""
        self.filter_tasks()
        self.update_statistics()
    
    def filter_tasks(self):
        """فلترة وعرض المهام"""
        # مسح المهام الحالية
        while self.tasks_layout.count():
            item = self.tasks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # الحصول على المهام
        tasks = self.task_service.get_all_tasks()
        
        # تطبيق فلتر البحث
        search_text = self.search_input.text().strip().lower()
        if search_text:
            tasks = [t for t in tasks if search_text in t.title.lower() or search_text in t.description.lower()]
        
        # تطبيق فلتر الحالة
        status_filter = self.status_filter.currentData()
        if status_filter == "overdue":
            tasks = self.task_service.get_overdue_tasks()
        elif status_filter != "all":
            tasks = [t for t in tasks if t.status.name == status_filter]
        
        # تطبيق فلتر الأولوية
        priority_filter = self.priority_filter.currentData()
        if priority_filter != "all":
            tasks = [t for t in tasks if t.priority.name == priority_filter]
        
        # ترتيب المهام (العاجلة أولاً، ثم حسب التاريخ)
        def sort_key(task):
            priority_order = {TaskPriority.URGENT: 0, TaskPriority.HIGH: 1, TaskPriority.MEDIUM: 2, TaskPriority.LOW: 3}
            status_order = {TaskStatus.IN_PROGRESS: 0, TaskStatus.TODO: 1, TaskStatus.COMPLETED: 2, TaskStatus.CANCELLED: 3}
            return (
                status_order.get(task.status, 4),
                priority_order.get(task.priority, 4),
                task.due_date or datetime.max
            )
        
        tasks.sort(key=sort_key)
        
        # عرض المهام
        if tasks:
            self.no_tasks_label.setVisible(False)
            self.tasks_scroll.setVisible(True)
            
            for task in tasks:
                task_widget = TaskItemWidget(task)
                task_widget.clicked.connect(self.edit_task)
                task_widget.status_changed.connect(self.change_task_status)
                task_widget.delete_requested.connect(self.delete_task)
                self.tasks_layout.addWidget(task_widget)
        else:
            self.no_tasks_label.setVisible(True)
            self.tasks_scroll.setVisible(False)
    
    def update_statistics(self):
        """تحديث الإحصائيات"""
        stats = self.task_service.get_statistics()
        
        self._update_stat_card(self.total_card, str(stats["total"]))
        self._update_stat_card(self.todo_card, str(stats["todo"]))
        self._update_stat_card(self.progress_card, str(stats["in_progress"]))
        self._update_stat_card(self.completed_card, str(stats["completed"]))
        self._update_stat_card(self.overdue_card, str(stats["overdue"]))
        
        self.progress_bar.setValue(int(stats["completion_rate"]))
    
    def add_task(self):
        """إضافة مهمة جديدة"""
        dialog = TaskEditorDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            task = dialog.get_task()
            if task:
                self.task_service.add_task(task)
                self.load_tasks()
                print(f"INFO: [TodoManager] تم إضافة مهمة: {task.title}")
    
    def edit_task(self, task_id: str):
        """تعديل مهمة"""
        task = self.task_service.get_task(task_id)
        if not task:
            return
        
        dialog = TaskEditorDialog(task=task, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_task = dialog.get_task()
            if updated_task:
                self.task_service.update_task(updated_task)
                self.load_tasks()
                print(f"INFO: [TodoManager] تم تحديث مهمة: {updated_task.title}")
    
    def change_task_status(self, task_id: str, new_status: TaskStatus):
        """تغيير حالة مهمة"""
        task = self.task_service.get_task(task_id)
        if not task:
            return
        
        task.status = new_status
        if new_status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now()
        else:
            task.completed_at = None
        
        self.task_service.update_task(task)
        self.load_tasks()
        print(f"INFO: [TodoManager] تم تغيير حالة مهمة '{task.title}' إلى {new_status.value}")
    
    def delete_task(self, task_id: str):
        """حذف مهمة"""
        task = self.task_service.get_task(task_id)
        if not task:
            return
        
        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف المهمة:\n{task.title}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.task_service.delete_task(task_id)
            self.load_tasks()
            print(f"INFO: [TodoManager] تم حذف مهمة: {task.title}")
    
    def check_reminders(self):
        """فحص التذكيرات"""
        now = datetime.now()
        tasks = self.task_service.get_all_tasks()
        
        for task in tasks:
            if not task.reminder or task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                continue
            
            if task.due_date:
                reminder_time = task.due_date - timedelta(minutes=task.reminder_minutes)
                if reminder_time <= now <= task.due_date:
                    # إظهار تذكير
                    QMessageBox.information(
                        self,
                        "⏰ تذكير",
                        f"المهمة '{task.title}' مستحقة خلال {task.reminder_minutes} دقيقة!"
                    )
                    # تعطيل التذكير بعد إظهاره
                    task.reminder = False
                    self.task_service.update_task(task)


# للاختبار
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setStyleSheet(f"""
        QWidget {{
            background-color: {COLORS['bg_dark']};
            color: {COLORS['text_primary']};
            font-family: 'Segoe UI', 'Cairo', sans-serif;
        }}
    """)
    
    window = TodoManagerWidget()
    window.setWindowTitle("نظام إدارة المهام - Sky Wave ERP")
    window.resize(900, 700)
    window.show()
    
    sys.exit(app.exec())
