"""
خدمة التحديث التلقائي - Sky Wave ERP
تتحقق من التحديثات تلقائياً في الخلفية
"""

import json
import os
from datetime import datetime

import requests
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from core.logger import get_logger
from version import (
    AUTO_UPDATE_ENABLED,
    AUTO_UPDATE_INTERVAL_HOURS,
    AUTO_UPDATE_ON_STARTUP,
    CURRENT_VERSION,
    UPDATE_CHECK_URL,
    compare_versions,
)

logger = get_logger(__name__)


class BackgroundUpdateChecker(QThread):
    """Thread للتحقق من التحديثات في الخلفية"""

    update_found = pyqtSignal(str, str, str)  # version, url, changelog
    check_completed = pyqtSignal(bool)  # has_update
    error_occurred = pyqtSignal(str)

    def __init__(self, current_version: str, check_url: str):
        super().__init__()
        self.current_version = current_version
        self.check_url = check_url

    def run(self):
        """التحقق من التحديثات"""
        try:
            response = requests.get(self.check_url, timeout=15)
            response.raise_for_status()

            data = response.json()
            remote_version = data.get("version", "")
            download_url = data.get("url", "")
            changelog = data.get("changelog", "")

            if remote_version and compare_versions(remote_version, self.current_version) > 0:
                logger.info(f"تحديث جديد متاح: {remote_version}")
                self.update_found.emit(remote_version, download_url, changelog)
                self.check_completed.emit(True)
            else:
                logger.debug("لا توجد تحديثات جديدة")
                self.check_completed.emit(False)

        except requests.RequestException as e:
            logger.warning(f"فشل التحقق من التحديثات: {e}")
            self.error_occurred.emit(str(e))
            self.check_completed.emit(False)
        except Exception as e:
            logger.error(f"خطأ في التحقق من التحديثات: {e}")
            self.error_occurred.emit(str(e))
            self.check_completed.emit(False)


class AutoUpdateService(QObject):
    """
    خدمة التحديث التلقائي
    تعمل في الخلفية وتتحقق من التحديثات بشكل دوري
    """

    # إشارات
    update_available = pyqtSignal(str, str, str)  # version, url, changelog
    update_check_started = pyqtSignal()
    update_check_finished = pyqtSignal(bool)  # has_update

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_version = CURRENT_VERSION
        self.check_url = UPDATE_CHECK_URL
        self.enabled = AUTO_UPDATE_ENABLED
        self.check_interval = AUTO_UPDATE_INTERVAL_HOURS * 60 * 60 * 1000  # بالمللي ثانية

        self._checker_thread: BackgroundUpdateChecker | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)

        self._last_check: datetime | None = None
        self._pending_update: dict | None = None

        # تحميل آخر وقت فحص
        self._load_last_check_time()

        logger.info(f"خدمة التحديث التلقائي جاهزة - الإصدار الحالي: {self.current_version}")

    def start(self):
        """بدء خدمة التحديث التلقائي"""
        if not self.enabled:
            logger.info("التحديث التلقائي معطل")
            return

        # التحقق عند بدء التشغيل
        if AUTO_UPDATE_ON_STARTUP:
            # تأخير 30 ثانية بعد بدء التشغيل
            QTimer.singleShot(30000, self.check_for_updates)

        # بدء المؤقت الدوري
        self._timer.start(self.check_interval)
        logger.info(f"بدء التحقق الدوري كل {AUTO_UPDATE_INTERVAL_HOURS} ساعات")

    def stop(self):
        """إيقاف خدمة التحديث التلقائي"""
        try:
            # التحقق من أن QTimer لم يتم حذفه بواسطة Qt
            if self._timer is not None:
                try:
                    self._timer.stop()
                except RuntimeError:
                    # QTimer تم حذفه بالفعل
                    pass
        except Exception as e:
            logger.debug(f"تحذير عند إيقاف المؤقت: {e}")
        
        if self._checker_thread and self._checker_thread.isRunning():
            self._checker_thread.quit()
            self._checker_thread.wait()
        logger.info("تم إيقاف خدمة التحديث التلقائي")

    def check_for_updates(self):
        """التحقق من التحديثات الآن"""
        if self._checker_thread and self._checker_thread.isRunning():
            logger.debug("التحقق جاري بالفعل...")
            return

        logger.info("بدء التحقق من التحديثات...")
        self.update_check_started.emit()

        self._checker_thread = BackgroundUpdateChecker(
            self.current_version,
            self.check_url
        )
        self._checker_thread.update_found.connect(self._on_update_found)
        self._checker_thread.check_completed.connect(self._on_check_completed)
        self._checker_thread.error_occurred.connect(self._on_error)
        self._checker_thread.start()

    def _on_timer_tick(self):
        """عند انتهاء المؤقت"""
        self.check_for_updates()

    def _on_update_found(self, version: str, url: str, changelog: str):
        """عند العثور على تحديث"""
        self._pending_update = {
            "version": version,
            "url": url,
            "changelog": changelog
        }
        self.update_available.emit(version, url, changelog)
        logger.info(f"تحديث جديد: {version}")

    def _on_check_completed(self, has_update: bool):
        """عند اكتمال الفحص"""
        self._last_check = datetime.now()
        self._save_last_check_time()
        self.update_check_finished.emit(has_update)

    def _on_error(self, error: str):
        """عند حدوث خطأ"""
        logger.warning(f"خطأ في التحقق من التحديثات: {error}")

    def get_pending_update(self) -> dict | None:
        """الحصول على التحديث المعلق"""
        return self._pending_update

    def get_last_check_time(self) -> datetime | None:
        """الحصول على آخر وقت فحص"""
        return self._last_check

    def _get_settings_path(self) -> str:
        """مسار ملف الإعدادات - في مجلد AppData لتجنب مشاكل الصلاحيات"""
        app_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SkyWaveERP')
        os.makedirs(app_data_dir, exist_ok=True)
        return os.path.join(app_data_dir, "update_settings.json")

    def _load_last_check_time(self):
        """تحميل آخر وقت فحص"""
        try:
            path = self._get_settings_path()
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    if "last_check" in data:
                        self._last_check = datetime.fromisoformat(data["last_check"])
        except Exception as e:
            logger.debug(f"فشل تحميل وقت الفحص: {e}")

    def _save_last_check_time(self):
        """حفظ آخر وقت فحص"""
        try:
            path = self._get_settings_path()
            data = {}
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)

            data["last_check"] = self._last_check.isoformat() if self._last_check else None

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"فشل حفظ وقت الفحص: {e}")


# Singleton instance
_auto_update_service: AutoUpdateService | None = None


def get_auto_update_service() -> AutoUpdateService:
    """الحصول على خدمة التحديث التلقائي (Singleton)"""
    global _auto_update_service
    if _auto_update_service is None:
        _auto_update_service = AutoUpdateService()
    return _auto_update_service
