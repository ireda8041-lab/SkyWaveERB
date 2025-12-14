# الملف: core/data_loader.py
"""
⚡ نظام تحميل البيانات في الخلفية (Background Data Loader)
يمنع تجميد الواجهة أثناء تحميل البيانات من قاعدة البيانات
الإصدار المحسّن مع دعم الأولويات والإلغاء
"""

from collections.abc import Callable
from enum import IntEnum

from PyQt6.QtCore import QObject, QRunnable, QThread, QThreadPool, pyqtSignal


class LoadPriority(IntEnum):
    """أولويات التحميل"""
    CRITICAL = 0  # فوري (الداشبورد)
    HIGH = 1      # عالي (التاب الحالي)
    NORMAL = 2    # عادي
    LOW = 3       # منخفض (التابات غير المفتوحة)


class DataLoaderWorker(QThread):
    """
    Worker thread لتحميل البيانات في الخلفية
    """
    # إشارات
    finished = pyqtSignal(object)  # البيانات المحملة
    error = pyqtSignal(str)  # رسالة الخطأ
    progress = pyqtSignal(int)  # نسبة التقدم (0-100)

    def __init__(self, load_function: Callable, *args, **kwargs):
        super().__init__()
        self.load_function = load_function
        self.args = args
        self.kwargs = kwargs
        self._is_cancelled = False

    def run(self):
        """تنفيذ التحميل في thread منفصل"""
        try:
            if self._is_cancelled:
                return

            # تنفيذ دالة التحميل
            result = self.load_function(*self.args, **self.kwargs)

            if not self._is_cancelled:
                self.finished.emit(result)

        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(str(e))
                print(f"ERROR: [DataLoader] فشل التحميل: {e}")

    def cancel(self):
        """إلغاء التحميل"""
        self._is_cancelled = True


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
        self.kwargs = kwargs
        self.signals = self.Signals()
        self.setAutoDelete(True)

    def run(self):
        """تنفيذ التحميل"""
        try:
            result = self.load_function(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
            print(f"ERROR: [DataLoaderRunnable] فشل التحميل: {e}")


class BackgroundDataLoader(QObject):
    """
    مدير تحميل البيانات في الخلفية
    يوفر واجهة موحدة لتحميل البيانات بدون تجميد الواجهة
    """

    # إشارات عامة
    loading_started = pyqtSignal(str)  # اسم العملية
    loading_finished = pyqtSignal(str, object)  # اسم العملية + البيانات
    loading_error = pyqtSignal(str, str)  # اسم العملية + رسالة الخطأ

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_workers = {}
        self._thread_pool = QThreadPool.globalInstance()
        # ⚡ تحديد عدد الـ threads المتاحة (أقل = أقل استهلاك للموارد)
        import os
        cpu_count = os.cpu_count() or 4
        optimal_threads = min(cpu_count, 4)  # حد أقصى 4 threads
        self._thread_pool.setMaxThreadCount(optimal_threads)
        
        # ⚡ قائمة انتظار للعمليات ذات الأولوية المنخفضة
        self._pending_operations: list[tuple] = []
        self._is_busy = False

    def load_async(
        self,
        operation_name: str,
        load_function: Callable,
        on_success: Callable | None = None,
        on_error: Callable | None = None,
        use_thread_pool: bool = True,
        *args,
        **kwargs
    ):
        """
        تحميل البيانات بشكل غير متزامن

        Args:
            operation_name: اسم العملية (للتتبع)
            load_function: دالة التحميل
            on_success: callback عند النجاح
            on_error: callback عند الفشل
            use_thread_pool: استخدام ThreadPool (أسرع) أو QThread (أكثر تحكم)
        """
        print(f"INFO: [DataLoader] ⚡ بدء تحميل: {operation_name}")
        self.loading_started.emit(operation_name)

        # إلغاء أي عملية سابقة بنفس الاسم
        self.cancel_operation(operation_name)

        if use_thread_pool:
            # استخدام QThreadPool (أخف وأسرع)
            runnable = DataLoaderRunnable(load_function, *args, **kwargs)

            def handle_success(data):
                print(f"INFO: [DataLoader] ✅ اكتمل تحميل: {operation_name}")
                self.loading_finished.emit(operation_name, data)
                if on_success:
                    on_success(data)

            def handle_error(error_msg):
                print(f"ERROR: [DataLoader] ❌ فشل تحميل: {operation_name} - {error_msg}")
                self.loading_error.emit(operation_name, error_msg)
                if on_error:
                    on_error(error_msg)

            runnable.signals.finished.connect(handle_success)
            runnable.signals.error.connect(handle_error)

            self._thread_pool.start(runnable)

        else:
            # استخدام QThread (أكثر تحكم)
            worker = DataLoaderWorker(load_function, *args, **kwargs)

            def handle_success(data):
                print(f"INFO: [DataLoader] ✅ اكتمل تحميل: {operation_name}")
                self.loading_finished.emit(operation_name, data)
                if on_success:
                    on_success(data)
                # تنظيف
                if operation_name in self._active_workers:
                    del self._active_workers[operation_name]

            def handle_error(error_msg):
                print(f"ERROR: [DataLoader] ❌ فشل تحميل: {operation_name} - {error_msg}")
                self.loading_error.emit(operation_name, error_msg)
                if on_error:
                    on_error(error_msg)
                # تنظيف
                if operation_name in self._active_workers:
                    del self._active_workers[operation_name]

            worker.finished.connect(handle_success)
            worker.error.connect(handle_error)

            self._active_workers[operation_name] = worker
            worker.start()

    def cancel_operation(self, operation_name: str):
        """إلغاء عملية تحميل"""
        if operation_name in self._active_workers:
            worker = self._active_workers[operation_name]
            worker.cancel()
            worker.quit()
            worker.wait(1000)  # انتظار ثانية كحد أقصى
            del self._active_workers[operation_name]
            print(f"INFO: [DataLoader] تم إلغاء: {operation_name}")

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
