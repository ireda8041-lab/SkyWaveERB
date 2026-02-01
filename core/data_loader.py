# الملف: core/data_loader.py
"""
⚡ نظام تحميل البيانات في الخلفية (Background Data Loader)
يمنع تجميد الواجهة أثناء تحميل البيانات من قاعدة البيانات
الإصدار المحسّن مع دعم الإلغاء
"""

import inspect
from collections.abc import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class DataLoaderRunnable(QRunnable):
    """
    Runnable لتحميل البيانات باستخدام QThreadPool
    أخف من QThread للعمليات السريعة
    """

    class Signals(QObject):
        finished = pyqtSignal(object)
        error = pyqtSignal(str)

    def __init__(self, load_function: Callable, *args, **kwargs):
        super().__init__()
        self.load_function = load_function
        self.args = args
        self.kwargs = dict(kwargs)
        self.signals = self.Signals()
        self.setAutoDelete(False)
        self._cancelled = False
        try:
            sig = inspect.signature(load_function)
            if "is_cancelled" in sig.parameters and "is_cancelled" not in self.kwargs:
                self.kwargs["is_cancelled"] = self.is_cancelled
        except Exception:
            pass

    def run(self):
        """تنفيذ التحميل"""
        try:
            if self._cancelled:
                return
            result = self.load_function(*self.args, **self.kwargs)
            if not self._cancelled:
                self.signals.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.signals.error.emit(str(e))
            safe_print(f"ERROR: [DataLoaderRunnable] فشل التحميل: {e}")

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled


class BackgroundDataLoader(QObject):
    """
    مدير تحميل البيانات في الخلفية - محسّن للسرعة القصوى
    """

    # إشارات عامة
    loading_started = pyqtSignal(str)
    loading_finished = pyqtSignal(str, object)
    loading_error = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_workers = {}
        self._thread_pool = QThreadPool.globalInstance()
        # ⚡ استخدام كل الـ CPU cores للسرعة القصوى
        import os

        cpu_count = os.cpu_count() or 4
        self._thread_pool.setMaxThreadCount(cpu_count)

    def load_async(
        self,
        operation_name: str,
        load_function: Callable,
        on_success: Callable | None = None,
        on_error: Callable | None = None,
        use_thread_pool: bool = True,
        *args,
        **kwargs,
    ):
        """تحميل البيانات بشكل غير متزامن - محسّن للسرعة"""
        # إلغاء أي عملية سابقة بنفس الاسم
        self.cancel_operation(operation_name)

        # استخدام QThreadPool دائماً (أسرع)
        runnable = DataLoaderRunnable(load_function, *args, **kwargs)

        def handle_success(data):
            current = self._active_workers.get(operation_name)
            if current is runnable:
                self._active_workers.pop(operation_name, None)
                if on_success:
                    on_success(data)

        def handle_error(error_msg):
            current = self._active_workers.get(operation_name)
            if current is runnable:
                self._active_workers.pop(operation_name, None)
                if on_error:
                    on_error(error_msg)

        runnable.signals.finished.connect(handle_success)
        runnable.signals.error.connect(handle_error)

        self._active_workers[operation_name] = runnable
        self._thread_pool.start(runnable)

    def cancel_operation(self, operation_name: str):
        """إلغاء عملية تحميل"""
        runnable = self._active_workers.pop(operation_name, None)
        if runnable is not None:
            runnable.cancel()

    def cancel_all(self):
        """إلغاء كل العمليات"""
        for name in list(self._active_workers.keys()):
            self.cancel_operation(name)
        self._thread_pool.clear()

    def is_loading(self, operation_name: str) -> bool:
        """التحقق إذا كانت العملية قيد التحميل"""
        return operation_name in self._active_workers


# Singleton instance
_data_loader_instance: BackgroundDataLoader | None = None


def get_data_loader() -> BackgroundDataLoader:
    """الحصول على instance واحد من DataLoader"""
    global _data_loader_instance
    if _data_loader_instance is None:
        _data_loader_instance = BackgroundDataLoader()
    return _data_loader_instance
