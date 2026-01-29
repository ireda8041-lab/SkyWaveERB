"""
معلومات الإصدار - Sky Wave ERP
"""

__version__ = "2.0.1"
__version_name__ = "Sky Wave ERP v2.0.1"
__release_date__ = "2026-01-20"
__author__ = "Sky Wave Team"
__email__ = "dev@skywave.agency"
__website__ = "https://skywave.agency"

# للتوافق مع الكود القديم
CURRENT_VERSION = __version__
APP_NAME = "Sky Wave ERP"
VERSION_NAME = __version_name__
RELEASE_DATE = __release_date__

# رابط التحقق من التحديثات
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/ireda8041-lab/SkyWaveERB/main/version.json"

# إعدادات التحديث التلقائي
AUTO_UPDATE_ENABLED = False  # معطّل للاستقرار
AUTO_UPDATE_INTERVAL_HOURS = 24  # التحقق كل 24 ساعة
AUTO_UPDATE_ON_STARTUP = False  # عدم التحقق عند بدء التشغيل


def compare_versions(v1, v2):
    """مقارنة نسختين: 1 إذا v1 > v2، -1 إذا v1 < v2، 0 إذا متساويين"""
    try:

        def normalize(v):
            return [int(x) for x in v.split(".")]

        return (normalize(v1) > normalize(v2)) - (normalize(v1) < normalize(v2))
    except Exception:
        return 0
