# -*- coding: utf-8 -*-
"""
⚡ نظام إدارة الإصدارات - Sky Wave ERP
الإصدار بصيغة: YY.MM.DD (السنة.الشهر.اليوم)
مثال: 25.12.04 = 4 ديسمبر 2025
"""

from datetime import datetime
import os
import json

# ==================== معلومات الإصدار ====================
# صيغة الإصدار: YY.MM.DD (السنة.الشهر.اليوم)
# يتم تحديثه تلقائياً عند كل تحديث

def _get_today_version() -> str:
    """توليد رقم الإصدار من تاريخ اليوم"""
    now = datetime.now()
    return f"{now.year % 100}.{now.month:02d}.{now.day:02d}"

CURRENT_VERSION = "1.0.3"  # الإصدار الثابت
APP_NAME = "Sky Wave ERP"
APP_AUTHOR = "Sky Wave Team"

# ==================== روابط التحديث ====================
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/ireda8041-lab/SkyWaveERB/main/version.json"

# ==================== إعدادات التحديث التلقائي ====================
AUTO_UPDATE_ENABLED = True
AUTO_UPDATE_INTERVAL_HOURS = 24  # التحقق كل 4 ساعات
AUTO_UPDATE_ON_STARTUP = True   # التحقق عند بدء التشغيل


def get_version_info() -> dict:
    """الحصول على معلومات الإصدار الكاملة"""
    return {
        "version": CURRENT_VERSION,
        "app_name": APP_NAME,
        "author": APP_AUTHOR,
        "version_date": parse_version_date(CURRENT_VERSION),
        "build_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def parse_version_date(version: str) -> str:
    """تحويل رقم الإصدار لتاريخ مقروء"""
    try:
        parts = version.split(".")
        if len(parts) == 3:
            year = int(parts[0]) + 2000
            month = int(parts[1])
            day = int(parts[2])
            return f"{day}/{month}/{year}"
    except (ValueError, IndexError):
        pass
    return version


def generate_version_from_date(date: datetime = None) -> str:
    """توليد رقم إصدار من تاريخ"""
    if date is None:
        date = datetime.now()
    return f"{date.year % 100}.{date.month:02d}.{date.day:02d}"


def compare_versions(v1: str, v2: str) -> int:
    """
    مقارنة إصدارين
    Returns: 1 إذا v1 > v2, -1 إذا v1 < v2, 0 إذا متساويين
    """
    try:
        parts1 = [int(x) for x in v1.split(".")]
        parts2 = [int(x) for x in v2.split(".")]
        
        for p1, p2 in zip(parts1, parts2):
            if p1 > p2:
                return 1
            elif p1 < p2:
                return -1
        return 0
    except (ValueError, AttributeError):
        return 0


def update_version_file():
    """
    ⚡ تحديث ملف version.json بالإصدار الجديد
    يُستدعى عند عمل تحديث جديد
    """
    version_data = {
        "version": CURRENT_VERSION,
        "url": "https://github.com/imhzm/SkyWaveERB/releases/latest",
        "changelog": [
            f"تحديث {parse_version_date(CURRENT_VERSION)}",
            "تحسينات في الأداء والسرعة",
            "إصلاح الأخطاء"
        ],
        "release_date": datetime.now().strftime("%Y-%m-%d")
    }
    
    try:
        with open("version.json", "w", encoding="utf-8") as f:
            json.dump(version_data, f, ensure_ascii=False, indent=2)
        print(f"✅ تم تحديث version.json للإصدار {CURRENT_VERSION}")
    except Exception as e:
        print(f"❌ فشل تحديث version.json: {e}")
