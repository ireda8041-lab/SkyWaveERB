# الملف: services/update_service.py
# خدمة التحقق من التحديثات وتنزيلها

import json
import os
import sys

import requests
from PyQt6.QtCore import QThread, pyqtSignal

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


UPDATE_SETUP_FILENAMES = (
    "SkyWaveERP_Update.exe",
    "SkyWave-Setup-Update.exe",
)


class UpdateChecker(QThread):
    """
    Thread للتحقق من وجود تحديثات جديدة
    """

    # إشارات
    update_available = pyqtSignal(str, str)  # (version, url)
    no_update = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, current_version: str, check_url: str):
        super().__init__()
        self.current_version = current_version
        self.check_url = check_url

    def run(self):
        """التحقق من التحديثات"""
        try:
            # إضافة headers لـ GitHub API
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "SkyWaveERP-Updater",
            }

            response = requests.get(self.check_url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            # دعم كلا الصيغتين: GitHub API و version.json العادي
            if "tag_name" in data:
                # GitHub API format
                remote_version = data.get("tag_name", "").lstrip("v")  # إزالة 'v' من البداية
                # البحث عن ملف exe في assets
                download_url = ""
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith(".exe"):
                        download_url = asset.get("browser_download_url", "")
                        break

                # ⚡ إذا لم نجد ملف exe، استخدم رابط الإصدار
                if not download_url:
                    download_url = data.get("html_url", "")
            else:
                # version.json format
                remote_version = data.get("version", "")
                download_url = data.get("url", "")

            # ⚡ إذا لم نجد إصدار، لا نعتبرها خطأ - فقط لا توجد تحديثات
            if not remote_version:
                self.no_update.emit()
                return

            # مقارنة الإصدارات
            if self._is_newer_version(remote_version, self.current_version):
                # ⚡ حتى لو لم يكن هناك رابط تحميل، نخبر المستخدم بوجود تحديث
                self.update_available.emit(remote_version, download_url or "")
            else:
                self.no_update.emit()

        except requests.Timeout:
            # ⚡ timeout ليس خطأ حرج - نتجاهله
            self.no_update.emit()
        except requests.RequestException:
            # ⚡ أخطاء الشبكة ليست حرجة - نتجاهلها
            self.no_update.emit()
        except json.JSONDecodeError:
            # ⚡ خطأ في قراءة JSON - نتجاهله
            self.no_update.emit()
        except Exception:
            # ⚡ أي خطأ آخر - نتجاهله
            self.no_update.emit()

    def _is_newer_version(self, remote: str, local: str) -> bool:
        """
        مقارنة رقمي الإصدارات
        يدعم صيغة YY.MM.DD (مثل 25.12.04) والصيغة التقليدية (مثل 1.0.0)

        Args:
            remote: رقم الإصدار البعيد
            local: رقم الإصدار المحلي

        Returns:
            True إذا كان الإصدار البعيد أحدث
        """
        try:
            remote_parts = [int(x) for x in remote.split(".")]
            local_parts = [int(x) for x in local.split(".")]

            # مقارنة كل جزء
            for remote_part, local_part in zip(remote_parts, local_parts, strict=False):
                if remote_part > local_part:
                    return True
                elif remote_part < local_part:
                    return False

            # إذا كانت متساوية حتى الآن، تحقق من الطول
            return len(remote_parts) > len(local_parts)

        except (ValueError, AttributeError):
            return False


class UpdateDownloader(QThread):
    """
    Thread لتنزيل ملف التحديث
    """

    # إشارات
    progress_updated = pyqtSignal(int)  # نسبة التقدم (0-100)
    download_completed = pyqtSignal(str)  # مسار الملف المحمل
    error_occurred = pyqtSignal(str)

    def __init__(self, download_url: str, save_path: str):
        super().__init__()
        self.download_url = download_url
        self.save_path = save_path
        self._is_cancelled = False

    def run(self):
        """تنزيل ملف التحديث"""
        try:
            # إنشاء المجلد إذا لم يكن موجوداً
            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)

            # تنزيل الملف مع تتبع التقدم
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0

            with open(self.save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._is_cancelled:
                        f.close()
                        os.remove(self.save_path)
                        return

                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # حساب النسبة المئوية
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            self.progress_updated.emit(progress)

            self.download_completed.emit(self.save_path)

        except requests.RequestException as e:
            self.error_occurred.emit(f"فشل التنزيل: {str(e)}")
        except OSError as e:
            self.error_occurred.emit(f"خطأ في حفظ الملف: {str(e)}")
        except Exception as e:
            self.error_occurred.emit(f"خطأ غير متوقع: {str(e)}")

    def cancel(self):
        """إلغاء التنزيل"""
        self._is_cancelled = True


class UpdateService:
    """
    خدمة إدارة التحديثات
    """

    def __init__(self, current_version: str, check_url: str):
        """
        Args:
            current_version: رقم الإصدار الحالي
            check_url: رابط ملف version.json
        """
        self.current_version = current_version
        self.check_url = check_url
        # استخدام مجلد AppData لتجنب مشاكل الصلاحيات في Program Files
        self.update_staging_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SkyWaveERP"
        )
        os.makedirs(self.update_staging_dir, exist_ok=True)
        self.temp_update_path = os.path.join(self.update_staging_dir, UPDATE_SETUP_FILENAMES[0])
        self.legacy_temp_update_path = os.path.join(
            self.update_staging_dir, UPDATE_SETUP_FILENAMES[1]
        )

    def _normalize_setup_path(self, setup_path: str | None) -> str | None:
        if not isinstance(setup_path, str):
            return None
        cleaned = setup_path.strip()
        if not cleaned:
            return None
        if os.path.isabs(cleaned):
            return os.path.normpath(cleaned)
        return os.path.normpath(os.path.abspath(cleaned))

    def _candidate_setup_paths(self, setup_path: str | None) -> list[str]:
        normalized = self._normalize_setup_path(setup_path)
        candidates = [
            normalized,
            self.temp_update_path,
            self.legacy_temp_update_path,
            os.path.join(os.path.dirname(self.temp_update_path), "SkyWaveERP_Update.exe"),
            os.path.join(os.path.dirname(self.temp_update_path), "SkyWave-Setup-Update.exe"),
        ]
        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not candidate:
                continue
            path = os.path.normpath(candidate)
            if path in seen:
                continue
            seen.add(path)
            unique.append(path)
        return unique

    def _resolve_setup_path(self, setup_path: str | None) -> str | None:
        for candidate in self._candidate_setup_paths(setup_path):
            if os.path.exists(candidate) and os.path.isfile(candidate):
                return candidate
        return None

    def _download_setup_file(self, download_url: str, target_path: str) -> bool:
        if not download_url:
            return False
        if not os.path.isabs(target_path):
            target_path = os.path.abspath(target_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()
        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        return os.path.exists(target_path) and os.path.getsize(target_path) > 0

    def _download_setup_with_fallback(self, download_url: str) -> str | None:
        targets = [self.temp_update_path, self.legacy_temp_update_path]
        for target in targets:
            try:
                if self._download_setup_file(download_url, target):
                    return target
            except Exception as e:
                safe_print(f"WARNING: فشل تنزيل التحديث إلى {target}: {e}")
            try:
                if os.path.exists(target):
                    os.remove(target)
            except OSError:
                pass
        return None

    def check_for_updates(self) -> UpdateChecker:
        """
        إنشاء Thread للتحقق من التحديثات

        Returns:
            UpdateChecker thread
        """
        checker = UpdateChecker(self.current_version, self.check_url)
        return checker

    def download_update(self, download_url: str) -> UpdateDownloader:
        """
        إنشاء Thread لتنزيل التحديث

        Args:
            download_url: رابط تنزيل التحديث

        Returns:
            UpdateDownloader thread
        """
        downloader = UpdateDownloader(download_url, self.temp_update_path)
        return downloader

    def apply_update(self, setup_path: str, download_url: str | None = None) -> bool:
        """
        تطبيق التحديث عن طريق تشغيل updater.exe

        Args:
            setup_path: مسار ملف Setup (exe) المحمل
            download_url: رابط تنزيل التحديث (اختياري)

        Returns:
            True إذا تم تشغيل المحدث بنجاح
        """
        try:
            # تحديد المجلد الحالي
            if getattr(sys, "frozen", False):
                # البرنامج مجمع (EXE)
                current_dir = os.path.dirname(sys.executable)
            else:
                # البرنامج يعمل من Python
                current_dir = os.path.dirname(os.path.abspath(__file__))
                current_dir = os.path.dirname(current_dir)  # العودة للمجلد الرئيسي

            # مسار updater.exe أو updater.py
            updater_exe = os.path.join(current_dir, "updater.exe")
            updater_py = os.path.join(current_dir, "updater.py")

            setup_path = self._resolve_setup_path(setup_path)

            # قراءة عنوان التحميل من الإصدار إذا لم يكن ملف الإعداد متاحاً
            if not setup_path:
                try:
                    version_json = os.path.join(current_dir, "version.json")
                    if os.path.exists(version_json):
                        with open(version_json, encoding="utf-8") as f:
                            data = json.load(f)
                            url = str(data.get("url") or "").strip()
                            if url:
                                download_url = url
                                safe_print(f"INFO: استخدام رابط التحديث من version.json: {url}")
                except Exception as e:
                    safe_print(f"WARNING: فشل قراءة version.json: {e}")

            if download_url and not setup_path:
                try:
                    setup_path = self._download_setup_with_fallback(download_url)
                    if setup_path:
                        safe_print(f"INFO: مسار ملف التحديث: {setup_path}")
                    else:
                        safe_print("ERROR: فشل تنزيل التحديث لكل مسارات staging المتاحة")
                        return False
                except Exception as e:
                    safe_print(f"ERROR: فشل تنزيل التحديث: {e}")
                    return False

            setup_path = self._resolve_setup_path(setup_path)
            setup_exists = bool(setup_path)
            prefer_py = not getattr(sys, "frozen", False) and os.path.exists(updater_py)

            # اختيار المحدث المناسب مع تمرير إما setup_path أو download_url
            if prefer_py:
                updater_path = updater_py
                if download_url and not setup_exists:
                    command = [sys.executable, updater_path, download_url]
                else:
                    command = [sys.executable, updater_path, current_dir, setup_path]
                    if download_url:
                        command.append(download_url)
            elif os.path.exists(updater_exe):
                updater_path = updater_exe
                if download_url and not setup_exists:
                    command = [updater_path, download_url]
                else:
                    command = [updater_path, current_dir, setup_path]
                    if download_url:
                        command.append(download_url)
            else:
                # updater.exe غير موجود - شغّل ملف Setup مباشرة أو حمّل من الرابط
                if download_url and not setup_exists:
                    # تشغيل المُحدّث النصي لتنزيل الملف وتثبيته
                    safe_print("INFO: تشغيل المُحدّث النصي مع رابط التنزيل...")
                    os.spawnv(
                        os.P_NOWAIT,
                        sys.executable,
                        [sys.executable, os.path.join(current_dir, "updater.py"), download_url],
                    )
                    return True
                if not setup_exists or not setup_path:
                    safe_print("ERROR: لا يوجد ملف setup صالح لتشغيل التحديث")
                    return False
                safe_print("updater.exe غير موجود - تشغيل Setup مباشرة...")
                os.spawnv(os.P_NOWAIT, setup_path, [setup_path])
                return True

            # تشغيل المحدث في عملية منفصلة
            os.spawnv(os.P_NOWAIT, command[0], command)

            return True

        except Exception as e:
            safe_print(f"خطأ في تطبيق التحديث: {e}")
            return False

    def cleanup_temp_files(self):
        """حذف الملفات المؤقتة"""
        try:
            for path in (self.temp_update_path, self.legacy_temp_update_path):
                if path and os.path.exists(path):
                    os.remove(path)
        except Exception as e:
            safe_print(f"تحذير: فشل حذف الملفات المؤقتة: {e}")
