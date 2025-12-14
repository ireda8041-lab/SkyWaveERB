# الملف: core/lazy_tab_loader.py
"""
⚡ نظام التحميل الكسول للتابات - Sky Wave ERP
================================
يؤخر تحميل التابات حتى يتم فتحها لأول مرة
مما يُسرّع بدء تشغيل البرنامج بشكل كبير
"""

import threading
import time
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from core.logger import get_logger

logger = get_logger(__name__)


class LazyTabPlaceholder(QWidget):
    """
    ⚡ Placeholder يظهر أثناء تحميل التاب
    """
    
    def __init__(self, tab_name: str, parent=None):
        super().__init__(parent)
        self.tab_name = tab_name
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # رسالة التحميل
        self.loading_label = QLabel(f"⏳ جاري تحميل {self.tab_name}...")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: #60A5FA;
                font-size: 16px;
                font-weight: bold;
                padding: 20px;
            }
        """)
        layout.addWidget(self.loading_label)
        layout.addStretch()


class LazyTabLoader(QObject):
    """
    ⚡ مدير التحميل الكسول للتابات
    
    الاستخدام:
    ```python
    loader = LazyTabLoader(tab_widget)
    loader.register_tab("المشاريع", lambda: ProjectManagerTab(...))
    ```
    """
    
    # إشارات
    tab_loading_started = pyqtSignal(str)  # اسم التاب
    tab_loading_finished = pyqtSignal(str, object)  # اسم التاب + الـ widget
    tab_loading_error = pyqtSignal(str, str)  # اسم التاب + رسالة الخطأ
    
    def __init__(self, tab_widget, parent=None):
        super().__init__(parent)
        self.tab_widget = tab_widget
        
        # تخزين معلومات التابات
        self._tab_factories: dict[str, Callable] = {}
        self._tab_indices: dict[str, int] = {}
        self._loaded_tabs: dict[str, QWidget] = {}
        self._loading_tabs: set[str] = set()
        
        # ربط إشارة تغيير التاب
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        
        logger.info("⚡ [LazyTabLoader] تم تهيئة نظام التحميل الكسول")
    
    def register_tab(self, name: str, factory: Callable, icon: str = "") -> int:
        """
        تسجيل تاب للتحميل الكسول
        
        Args:
            name: اسم التاب
            factory: دالة تُنشئ الـ widget
            icon: أيقونة التاب (اختياري)
        
        Returns:
            index التاب في الـ TabWidget
        """
        # إنشاء placeholder
        placeholder = LazyTabPlaceholder(name)
        
        # إضافة للـ TabWidget
        tab_text = f"{icon} {name}" if icon else name
        index = self.tab_widget.addTab(placeholder, tab_text)
        
        # تخزين المعلومات
        self._tab_factories[name] = factory
        self._tab_indices[name] = index
        
        logger.debug(f"⚡ [LazyTabLoader] تم تسجيل التاب: {name} (index={index})")
        return index
    
    def _on_tab_changed(self, index: int):
        """معالج تغيير التاب"""
        # البحث عن اسم التاب
        tab_name = None
        for name, idx in self._tab_indices.items():
            if idx == index:
                tab_name = name
                break
        
        if not tab_name:
            return
        
        # التحقق إذا كان التاب محمل بالفعل
        if tab_name in self._loaded_tabs:
            return
        
        # التحقق إذا كان التاب قيد التحميل
        if tab_name in self._loading_tabs:
            return
        
        # بدء التحميل
        self._load_tab(tab_name)
    
    def _load_tab(self, tab_name: str):
        """تحميل التاب"""
        if tab_name not in self._tab_factories:
            return
        
        self._loading_tabs.add(tab_name)
        self.tab_loading_started.emit(tab_name)
        
        logger.info(f"⚡ [LazyTabLoader] بدء تحميل التاب: {tab_name}")
        
        # تحميل في الـ main thread (لأن PyQt يتطلب ذلك)
        QTimer.singleShot(10, lambda: self._do_load_tab(tab_name))
    
    def _do_load_tab(self, tab_name: str):
        """تنفيذ التحميل الفعلي"""
        try:
            start_time = time.perf_counter()
            
            # إنشاء الـ widget
            factory = self._tab_factories[tab_name]
            widget = factory()
            
            # استبدال الـ placeholder
            index = self._tab_indices[tab_name]
            old_widget = self.tab_widget.widget(index)
            
            # الحفاظ على النص والأيقونة
            tab_text = self.tab_widget.tabText(index)
            
            # إزالة الـ placeholder وإضافة الـ widget الجديد
            self.tab_widget.removeTab(index)
            self.tab_widget.insertTab(index, widget, tab_text)
            
            # تحديث الـ index الحالي
            self.tab_widget.setCurrentIndex(index)
            
            # تنظيف الـ placeholder
            if old_widget:
                old_widget.deleteLater()
            
            # تخزين الـ widget المحمل
            self._loaded_tabs[tab_name] = widget
            self._loading_tabs.discard(tab_name)
            
            elapsed = time.perf_counter() - start_time
            logger.info(f"⚡ [LazyTabLoader] ✅ تم تحميل {tab_name} في {elapsed:.2f}s")
            
            self.tab_loading_finished.emit(tab_name, widget)
            
            # معالجة الأحداث
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"⚡ [LazyTabLoader] ❌ فشل تحميل {tab_name}: {e}")
            self._loading_tabs.discard(tab_name)
            self.tab_loading_error.emit(tab_name, str(e))
    
    def preload_tab(self, tab_name: str):
        """تحميل تاب مسبقاً في الخلفية"""
        if tab_name in self._loaded_tabs:
            return
        
        if tab_name in self._loading_tabs:
            return
        
        # تحميل بعد تأخير قصير
        QTimer.singleShot(100, lambda: self._load_tab(tab_name))
    
    def preload_all(self, delay_between: int = 500):
        """تحميل كل التابات في الخلفية"""
        tabs_to_load = [
            name for name in self._tab_factories.keys()
            if name not in self._loaded_tabs
        ]
        
        for i, tab_name in enumerate(tabs_to_load):
            QTimer.singleShot(delay_between * (i + 1), lambda n=tab_name: self.preload_tab(n))
    
    def is_tab_loaded(self, tab_name: str) -> bool:
        """التحقق إذا كان التاب محمل"""
        return tab_name in self._loaded_tabs
    
    def get_loaded_tab(self, tab_name: str) -> QWidget | None:
        """الحصول على widget التاب المحمل"""
        return self._loaded_tabs.get(tab_name)
    
    def reload_tab(self, tab_name: str):
        """إعادة تحميل تاب"""
        if tab_name in self._loaded_tabs:
            del self._loaded_tabs[tab_name]
        self._load_tab(tab_name)
    
    def get_stats(self) -> dict:
        """إحصائيات التحميل"""
        return {
            "total_tabs": len(self._tab_factories),
            "loaded_tabs": len(self._loaded_tabs),
            "loading_tabs": len(self._loading_tabs),
            "pending_tabs": len(self._tab_factories) - len(self._loaded_tabs) - len(self._loading_tabs)
        }


class PriorityTabLoader(LazyTabLoader):
    """
    ⚡ مدير تحميل مع أولويات
    يُحمّل التابات الأكثر استخداماً أولاً
    """
    
    def __init__(self, tab_widget, parent=None):
        super().__init__(tab_widget, parent)
        self._tab_priorities: dict[str, int] = {}
        self._tab_usage: dict[str, int] = {}
    
    def register_tab_with_priority(self, name: str, factory: Callable, 
                                    priority: int = 5, icon: str = "") -> int:
        """
        تسجيل تاب مع أولوية
        
        Args:
            priority: 1 (أعلى) إلى 10 (أدنى)
        """
        index = self.register_tab(name, factory, icon)
        self._tab_priorities[name] = priority
        self._tab_usage[name] = 0
        return index
    
    def _on_tab_changed(self, index: int):
        """معالج تغيير التاب مع تتبع الاستخدام"""
        # تحديث الاستخدام
        for name, idx in self._tab_indices.items():
            if idx == index:
                self._tab_usage[name] = self._tab_usage.get(name, 0) + 1
                break
        
        super()._on_tab_changed(index)
    
    def preload_by_priority(self, max_tabs: int = 3):
        """تحميل التابات حسب الأولوية"""
        # ترتيب حسب الأولوية ثم الاستخدام
        tabs_to_load = [
            name for name in self._tab_factories.keys()
            if name not in self._loaded_tabs
        ]
        
        tabs_to_load.sort(key=lambda n: (
            self._tab_priorities.get(n, 5),
            -self._tab_usage.get(n, 0)
        ))
        
        for i, tab_name in enumerate(tabs_to_load[:max_tabs]):
            QTimer.singleShot(500 * (i + 1), lambda n=tab_name: self.preload_tab(n))
