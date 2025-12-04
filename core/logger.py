# الملف: core/logger.py
# نظام التسجيل (Logging) المركزي

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class LoggerSetup:
    """
    إعداد نظام التسجيل المركزي لـ Sky Wave ERP.
    يوفر تسجيل متقدم مع دعم الملفات الدوارة.
    """
    
    # إعدادات افتراضية
    # استخدام مجلد AppData للمستخدم بدلاً من مجلد البرنامج (لتجنب مشاكل الصلاحيات)
    LOG_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SkyWaveERP', 'logs')
    LOG_FILE = "skywave_erp.log"
    MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
    BACKUP_COUNT = 5  # عدد الملفات الاحتياطية
    
    _logger_initialized = False
    
    @staticmethod
    def setup_logger(
        log_level: int = logging.DEBUG,
        log_to_console: bool = True,
        log_to_file: bool = True
    ) -> logging.Logger:
        """
        إعداد نظام التسجيل.
        
        Args:
            log_level: مستوى التسجيل (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_console: هل نسجل في الكونسول؟
            log_to_file: هل نسجل في ملف؟
        
        Returns:
            Logger object
        """
        # تجنب الإعداد المتكرر
        if LoggerSetup._logger_initialized:
            return logging.getLogger("SkyWaveERP")
        
        # إنشاء Logger
        logger = logging.getLogger("SkyWaveERP")
        logger.setLevel(log_level)
        
        # مسح أي handlers موجودة
        logger.handlers.clear()
        
        # تنسيق الرسائل
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 1. File Handler (التسجيل في ملف)
        if log_to_file:
            # إنشاء مجلد logs إذا لم يكن موجوداً
            os.makedirs(LoggerSetup.LOG_DIR, exist_ok=True)
            
            log_file_path = os.path.join(LoggerSetup.LOG_DIR, LoggerSetup.LOG_FILE)
            
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=LoggerSetup.MAX_LOG_SIZE,
                backupCount=LoggerSetup.BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)  # نسجل كل شيء في الملف
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            print(f"✅ تم إعداد التسجيل في الملف: {log_file_path}")
        
        # 2. Console Handler (التسجيل في الكونسول)
        if log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)  # نعرض INFO وما فوق في الكونسول
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
            print("✅ تم إعداد التسجيل في الكونسول")
        
        # تسجيل رسالة البداية
        logger.info("="*80)
        logger.info(f"Sky Wave ERP - بدء التشغيل في {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        LoggerSetup._logger_initialized = True
        return logger
    
    @staticmethod
    def get_logger(name: Optional[str] = None) -> logging.Logger:
        """
        الحصول على Logger.
        
        Args:
            name: اسم الـ Logger (اختياري)
        
        Returns:
            Logger object
        """
        if not LoggerSetup._logger_initialized:
            LoggerSetup.setup_logger()
        
        if name:
            return logging.getLogger(f"SkyWaveERP.{name}")
        return logging.getLogger("SkyWaveERP")
    
    @staticmethod
    def log_function_call(func):
        """
        Decorator لتسجيل استدعاء الدوال تلقائياً.
        
        الاستخدام:
        @LoggerSetup.log_function_call
        def my_function(arg1, arg2):
            # الكود هنا
        """
        def wrapper(*args, **kwargs):
            logger = LoggerSetup.get_logger(func.__module__)
            logger.debug(f"استدعاء دالة: {func.__name__} مع المعاملات: args={args}, kwargs={kwargs}")
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"انتهت دالة: {func.__name__} بنجاح")
                return result
            except Exception as e:
                logger.error(f"فشلت دالة: {func.__name__} بخطأ: {e}")
                raise
        
        return wrapper
    
    @staticmethod
    def create_session_log():
        """
        إنشاء ملف log منفصل لكل جلسة.
        مفيد للتتبع المفصل.
        """
        session_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        session_log_file = os.path.join(
            LoggerSetup.LOG_DIR,
            f"session_{session_time}.log"
        )
        
        logger = logging.getLogger("SkyWaveERP")
        
        session_handler = logging.FileHandler(
            session_log_file,
            encoding='utf-8'
        )
        session_handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        session_handler.setFormatter(formatter)
        
        logger.addHandler(session_handler)
        logger.info(f"تم إنشاء ملف log للجلسة: {session_log_file}")
        
        return session_log_file
    
    @staticmethod
    def cleanup_old_logs(days: int = 30):
        """
        حذف ملفات الـ log القديمة.
        
        Args:
            days: عدد الأيام (الملفات الأقدم من هذا سيتم حذفها)
        """
        logger = LoggerSetup.get_logger()
        
        if not os.path.exists(LoggerSetup.LOG_DIR):
            return
        
        current_time = datetime.now()
        deleted_count = 0
        
        for filename in os.listdir(LoggerSetup.LOG_DIR):
            if not filename.endswith('.log'):
                continue
            
            file_path = os.path.join(LoggerSetup.LOG_DIR, filename)
            
            # التحقق من عمر الملف
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            age_days = (current_time - file_time).days
            
            if age_days > days:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"تم حذف ملف log قديم: {filename} (العمر: {age_days} يوم)")
                except Exception as e:
                    logger.error(f"فشل حذف ملف log: {filename} - {e}")
        
        if deleted_count > 0:
            logger.info(f"تم حذف {deleted_count} ملف log قديم")


# --- دوال مساعدة سريعة ---

def debug(message: str, context: Optional[str] = None):
    """تسجيل رسالة DEBUG"""
    logger = LoggerSetup.get_logger(context)
    logger.debug(message)


def info(message: str, context: Optional[str] = None):
    """تسجيل رسالة INFO"""
    logger = LoggerSetup.get_logger(context)
    logger.info(message)


def warning(message: str, context: Optional[str] = None):
    """تسجيل رسالة WARNING"""
    logger = LoggerSetup.get_logger(context)
    logger.warning(message)


def error(message: str, context: Optional[str] = None):
    """تسجيل رسالة ERROR"""
    logger = LoggerSetup.get_logger(context)
    logger.error(message)


def critical(message: str, context: Optional[str] = None):
    """تسجيل رسالة CRITICAL"""
    logger = LoggerSetup.get_logger(context)
    logger.critical(message)


# --- اختبار ---
if __name__ == "__main__":
    print("--- اختبار نظام التسجيل ---\n")
    
    # إعداد Logger
    logger = LoggerSetup.setup_logger()
    
    # اختبار مستويات مختلفة
    logger.debug("هذه رسالة DEBUG")
    logger.info("هذه رسالة INFO")
    logger.warning("هذه رسالة WARNING")
    logger.error("هذه رسالة ERROR")
    logger.critical("هذه رسالة CRITICAL")
    
    # اختبار الدوال المساعدة
    info("اختبار الدالة المساعدة info()")
    warning("اختبار الدالة المساعدة warning()")
    
    # اختبار Decorator
    @LoggerSetup.log_function_call
    def test_function(x, y):
        return x + y
    
    result = test_function(5, 3)
    print(f"\nنتيجة الدالة: {result}")
    
    # اختبار إنشاء session log
    session_file = LoggerSetup.create_session_log()
    print(f"\nتم إنشاء ملف الجلسة: {session_file}")
    
    # اختبار تنظيف الملفات القديمة
    LoggerSetup.cleanup_old_logs(days=30)
    
    print("\n--- انتهى الاختبار ---")
    print(f"تحقق من مجلد '{LoggerSetup.LOG_DIR}' لرؤية ملفات الـ log")


# دالة مساعدة للحصول على Logger بسهولة
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    دالة مساعدة للحصول على Logger.
    
    Args:
        name: اسم Logger (اختياري)
    
    Returns:
        Logger object
    """
    return LoggerSetup.get_logger(name)
