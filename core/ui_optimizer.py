# الملف: core/ui_optimizer.py
"""
⚡ محسّن واجهة المستخدم - Sky Wave ERP
================================
يوفر تحسينات للواجهة لمنع التجميد وتسريع الاستجابة
"""

import functools
import time
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QTableWidget, QWidget

from core.logger import get_logger

logger = get_logger(__name__)


class UIOptimizer:
    """
    ⚡ محسّن الواجهة
    يوفر أدوات لتحسين أداء الواجهة
    """
    
    @staticmethod
    def process_events_safely():
        """⚡ معالجة الأحداث بأمان"""
        try:
            app = QApplication.instance()
            if app:
                app.processEvents()
        except Exception:
            pass
    
    @staticmethod
    def defer_execution(func: Callable, delay_ms: int = 0):
        """⚡ تأجيل تنفيذ دالة"""
        QTimer.singleShot(delay_ms, func)
    
    @staticmethod
    def batch_table_update(table: QTableWidget, data: list, 
                           row_builder: Callable, batch_size: int = 50):
        """
        ⚡ تحديث الجدول على دفعات لمنع التجميد
        
        Args:
            table: الجدول
            data: البيانات
            row_builder: دالة تبني الصف
            batch_size: حجم الدفعة
        """
        table.setUpdatesEnabled(False)
        table.setRowCount(0)
        
        def add_batch(start_idx: int):
            end_idx = min(start_idx + batch_size, len(data))
            
            for i in range(start_idx, end_idx):
                row_builder(table, data[i], i)
            
            if end_idx < len(data):
                QTimer.singleShot(10, lambda: add_batch(end_idx))
            else:
                table.setUpdatesEnabled(True)
        
        if data:
            table.setRowCount(len(data))
            add_batch(0)
        else:
            table.setUpdatesEnabled(True)
    
    @staticmethod
    def optimize_table(table: QTableWidget):
        """⚡ تطبيق تحسينات على الجدول"""
        # تعطيل التحديثات أثناء التعديل
        table.setUpdatesEnabled(False)
        
        # تحسينات الأداء
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)  # تعطيل الترتيب أثناء التحميل
        
        # إعادة تفعيل التحديثات
        table.setUpdatesEnabled(True)
    
    @staticmethod
    def freeze_widget(widget: QWidget):
        """⚡ تجميد widget أثناء التحديث"""
        widget.setUpdatesEnabled(False)
        return lambda: widget.setUpdatesEnabled(True)


class DebouncedSignal(QObject):
    """
    ⚡ إشارة مع debounce
    تمنع الاستدعاءات المتكررة السريعة
    """
    
    triggered = pyqtSignal(object)
    
    def __init__(self, delay_ms: int = 300, parent=None):
        super().__init__(parent)
        self.delay_ms = delay_ms
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit)
        self._pending_value = None
    
    def emit_debounced(self, value: Any = None):
        """إرسال الإشارة مع debounce"""
        self._pending_value = value
        self._timer.start(self.delay_ms)
    
    def _emit(self):
        """إرسال الإشارة الفعلي"""
        self.triggered.emit(self._pending_value)
    
    def cancel(self):
        """إلغاء الإشارة المعلقة"""
        self._timer.stop()


class ThrottledSignal(QObject):
    """
    ⚡ إشارة مع throttle
    تحدد الحد الأقصى لمعدل الاستدعاء
    """
    
    triggered = pyqtSignal(object)
    
    def __init__(self, min_interval_ms: int = 100, parent=None):
        super().__init__(parent)
        self.min_interval = min_interval_ms / 1000.0
        self._last_emit = 0
    
    def emit_throttled(self, value: Any = None):
        """إرسال الإشارة مع throttle"""
        now = time.time()
        if now - self._last_emit >= self.min_interval:
            self._last_emit = now
            self.triggered.emit(value)


def debounce(wait_ms: int = 300):
    """
    ⚡ Decorator لتأخير تنفيذ الدالة
    مفيد للبحث والتصفية
    """
    def decorator(func: Callable) -> Callable:
        timer = [None]
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def call_func():
                func(*args, **kwargs)
            
            if timer[0]:
                timer[0].stop()
            
            timer[0] = QTimer()
            timer[0].setSingleShot(True)
            timer[0].timeout.connect(call_func)
            timer[0].start(wait_ms)
        
        return wrapper
    
    return decorator


def throttle(min_interval_ms: int = 100):
    """
    ⚡ Decorator لتحديد معدل الاستدعاء
    """
    def decorator(func: Callable) -> Callable:
        last_call = [0.0]
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            if now - last_call[0] >= min_interval_ms / 1000.0:
                last_call[0] = now
                return func(*args, **kwargs)
            return None
        
        return wrapper
    
    return decorator


def run_in_main_thread(func: Callable) -> Callable:
    """
    ⚡ Decorator لتشغيل الدالة في الـ main thread
    مهم لتحديثات الواجهة من threads أخرى
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        QTimer.singleShot(0, lambda: func(*args, **kwargs))
    
    return wrapper


class ProgressiveLoader:
    """
    ⚡ محمّل تدريجي للبيانات الكبيرة
    يُحمّل البيانات على دفعات مع تحديث الواجهة
    """
    
    def __init__(self, batch_size: int = 100, delay_ms: int = 10):
        self.batch_size = batch_size
        self.delay_ms = delay_ms
        self._is_loading = False
        self._cancelled = False
    
    def load(self, data: list, processor: Callable, 
             on_progress: Callable | None = None,
             on_complete: Callable | None = None):
        """
        تحميل البيانات تدريجياً
        
        Args:
            data: البيانات
            processor: دالة معالجة كل عنصر
            on_progress: callback للتقدم (current, total)
            on_complete: callback عند الاكتمال
        """
        if self._is_loading:
            return
        
        self._is_loading = True
        self._cancelled = False
        total = len(data)
        
        def process_batch(start_idx: int):
            if self._cancelled:
                self._is_loading = False
                return
            
            end_idx = min(start_idx + self.batch_size, total)
            
            for i in range(start_idx, end_idx):
                processor(data[i], i)
            
            if on_progress:
                on_progress(end_idx, total)
            
            UIOptimizer.process_events_safely()
            
            if end_idx < total:
                QTimer.singleShot(self.delay_ms, lambda: process_batch(end_idx))
            else:
                self._is_loading = False
                if on_complete:
                    on_complete()
        
        if data:
            process_batch(0)
        else:
            self._is_loading = False
            if on_complete:
                on_complete()
    
    def cancel(self):
        """إلغاء التحميل"""
        self._cancelled = True
    
    @property
    def is_loading(self) -> bool:
        return self._is_loading


class VirtualTableModel:
    """
    ⚡ نموذج جدول افتراضي
    يُحمّل فقط الصفوف المرئية للأداء
    """
    
    def __init__(self, data_fetcher: Callable, page_size: int = 50):
        self.data_fetcher = data_fetcher
        self.page_size = page_size
        self._cache: dict[int, Any] = {}
        self._total_count = 0
    
    def get_row(self, index: int) -> Any:
        """جلب صف بالـ index"""
        page = index // self.page_size
        
        if page not in self._cache:
            # تحميل الصفحة
            offset = page * self.page_size
            self._cache[page] = self.data_fetcher(offset, self.page_size)
        
        page_data = self._cache.get(page, [])
        local_index = index % self.page_size
        
        if local_index < len(page_data):
            return page_data[local_index]
        return None
    
    def invalidate(self):
        """إبطال الـ cache"""
        self._cache.clear()
    
    def set_total_count(self, count: int):
        """تعيين العدد الإجمالي"""
        self._total_count = count
    
    @property
    def total_count(self) -> int:
        return self._total_count
