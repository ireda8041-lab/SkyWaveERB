# الملف: auto_updater.py
"""
⚡ نظام التحديث التلقائي - Sky Wave ERP
يستخدم للتحقق من التحديثات عند بدء التشغيل
"""

import requests

from core.logger import get_logger
from version import CURRENT_VERSION, UPDATE_CHECK_URL, compare_versions

logger = get_logger(__name__)


def check_for_updates() -> tuple[bool, str, str, list]:
    """
    التحقق من وجود تحديثات جديدة
    
    Returns:
        tuple: (has_update, latest_version, download_url, changelog)
    """
    try:
        response = requests.get(UPDATE_CHECK_URL, timeout=10)
        response.raise_for_status()

        data = response.json()
        remote_version = data.get("version", "")
        download_url = data.get("url", "")
        changelog = data.get("changelog", [])

        if remote_version and compare_versions(remote_version, CURRENT_VERSION) > 0:
            logger.info(f"🆕 تحديث جديد متاح: v{remote_version}")
            return True, remote_version, download_url, changelog
        else:
            logger.debug(f"✅ الإصدار الحالي ({CURRENT_VERSION}) هو الأحدث")
            return False, CURRENT_VERSION, "", []

    except requests.Timeout:
        logger.warning("⏱️ انتهت مهلة التحقق من التحديثات")
        return False, CURRENT_VERSION, "", []
    except requests.RequestException as e:
        logger.warning(f"⚠️ فشل التحقق من التحديثات: {e}")
        return False, CURRENT_VERSION, "", []
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع في التحقق من التحديثات: {e}")
        return False, CURRENT_VERSION, "", []


def get_update_info() -> dict:
    """
    الحصول على معلومات التحديث الكاملة
    
    Returns:
        dict: معلومات التحديث
    """
    has_update, version, url, changelog = check_for_updates()
    return {
        "has_update": has_update,
        "current_version": CURRENT_VERSION,
        "latest_version": version,
        "download_url": url,
        "changelog": changelog
    }
