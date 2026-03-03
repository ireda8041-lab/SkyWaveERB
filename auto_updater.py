# الملف: auto_updater.py
"""
⚡ نظام التحديث التلقائي - Sky Wave ERP
يستخدم للتحقق من التحديثات عند بدء التشغيل
"""

import requests

from core.logger import get_logger
from version import CURRENT_VERSION, UPDATE_CHECK_URL, compare_versions

logger = get_logger(__name__)


def _extract_update_payload(data: dict) -> tuple[str, str, list]:
    """
    Parse update payload from either:
    1) GitHub Releases API format
    2) version.json custom format
    """
    # GitHub Releases API format
    if "tag_name" in data:
        remote_version = str(data.get("tag_name", "")).lstrip("v").strip()
        download_url = ""
        for asset in data.get("assets", []):
            name = str(asset.get("name", "")).lower()
            if name.endswith(".exe"):
                download_url = str(asset.get("browser_download_url", "")).strip()
                break
        if not download_url:
            download_url = str(data.get("html_url", "")).strip()

        body = str(data.get("body", "") or "").strip()
        changelog = []
        if body:
            for line in body.splitlines():
                cleaned = line.strip()
                if not cleaned:
                    continue
                if cleaned.startswith("- "):
                    cleaned = cleaned[2:].strip()
                elif cleaned.startswith("* "):
                    cleaned = cleaned[2:].strip()
                changelog.append(cleaned)
        return remote_version, download_url, changelog

    # version.json format
    remote_version = str(data.get("version", "")).strip()
    download_url = str(data.get("url", "")).strip()
    raw_changelog = data.get("changelog", [])
    if isinstance(raw_changelog, list):
        changelog = [str(item).strip() for item in raw_changelog if str(item).strip()]
    elif isinstance(raw_changelog, str):
        changelog = [raw_changelog.strip()] if raw_changelog.strip() else []
    else:
        changelog = []
    return remote_version, download_url, changelog


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
        remote_version, download_url, changelog = _extract_update_payload(data)

        if remote_version and compare_versions(remote_version, CURRENT_VERSION) > 0:
            logger.info("🆕 تحديث جديد متاح: v%s", remote_version)
            return True, remote_version, download_url, changelog
        else:
            logger.debug("✅ الإصدار الحالي (%s) هو الأحدث", CURRENT_VERSION)
            return False, CURRENT_VERSION, "", []

    except requests.Timeout:
        logger.warning("⏱️ انتهت مهلة التحقق من التحديثات")
        return False, CURRENT_VERSION, "", []
    except requests.RequestException as e:
        logger.warning("⚠️ فشل التحقق من التحديثات: %s", e)
        return False, CURRENT_VERSION, "", []
    except Exception as e:
        logger.error("❌ خطأ غير متوقع في التحقق من التحديثات: %s", e)
        return False, CURRENT_VERSION, "", []


def get_update_info() -> dict:
    """
    الحصول على معلومات التحديث الكاملة.

    Returns:
        dict: معلومات التحديث
    """
    has_update, version, url, changelog = check_for_updates()
    return {
        "has_update": has_update,
        "current_version": CURRENT_VERSION,
        "latest_version": version,
        "download_url": url,
        "changelog": changelog,
    }
