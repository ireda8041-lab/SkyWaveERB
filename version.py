"""
معلومات الإصدار - Sky Wave ERP
"""

__version__ = "2.1.9"
__version_name__ = "Sky Wave ERP v2.1.9"
__release_date__ = "2026-02-09"
__author__ = "Sky Wave Team"
__email__ = "dev@skywave.agency"
__website__ = "https://skywave.agency"

# للتوافق مع الكود القديم
CURRENT_VERSION = __version__
APP_NAME = "Sky Wave ERP"
VERSION_NAME = __version_name__
RELEASE_DATE = __release_date__

# ⚡ إعدادات تحسين الأداء
PERFORMANCE_MODE = True  # تفعيل وضع الأداء العالي
LAZY_LOADING = True  # تحميل كسول للبيانات
CACHE_ENABLED = True  # تفعيل الـ cache

# رابط التحقق من التحديثات - نستخدم GitHub API لتجنب مشاكل الـ cache
UPDATE_CHECK_URL = "https://api.github.com/repos/ireda8041-lab/SkyWaveERB/releases/latest"

# إعدادات التحديث التلقائي
AUTO_UPDATE_ENABLED = True  # مفعّل للتحقق التلقائي من التحديثات
AUTO_UPDATE_INTERVAL_HOURS = 24  # التحقق كل 24 ساعة
AUTO_UPDATE_ON_STARTUP = False  # ⚡ معطّل عند بدء التشغيل لتجنب التعليق


def compare_versions(v1, v2):
    """مقارنة نسختين: 1 إذا v1 > v2، -1 إذا v1 < v2، 0 إذا متساويين"""
    try:

        def normalize(v):
            return [int(x) for x in v.split(".")]

        return (normalize(v1) > normalize(v2)) - (normalize(v1) < normalize(v2))
    except Exception:
        return 0
