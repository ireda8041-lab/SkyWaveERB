# الملف: services/update_service.py
# خدمة التحقق من التحديثات وتنزيلها

import os
import sys
import subprocess
import requests
import json
from pathlib import Path
from typing import Optional, Tuple, Callable
from PyQt6.QtCore import QThread, pyqtSignal


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
            # تنزيل ملف version.json
            response = requests.get(self.check_url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            remote_version = data.get("version", "")
            download_url = data.get("url", "")
            
            if not remote_version or not download_url:
                self.error_occurred.emit("ملف التحديث غير صحيح")
                return
            
            # مقارنة الإصدارات
            if self._is_newer_version(remote_version, self.current_version):
                self.update_available.emit(remote_version, download_url)
            else:
                self.no_update.emit()
                
        except requests.RequestException as e:
            self.error_occurred.emit(f"فشل الاتصال بالخادم: {str(e)}")
        except json.JSONDecodeError:
            self.error_occurred.emit("خطأ في قراءة بيانات التحديث")
        except Exception as e:
            self.error_occurred.emit(f"خطأ غير متوقع: {str(e)}")
    
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
            remote_parts = [int(x) for x in remote.split('.')]
            local_parts = [int(x) for x in local.split('.')]
            
            # مقارنة كل جزء
            for r, l in zip(remote_parts, local_parts):
                if r > l:
                    return True
                elif r < l:
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
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(self.save_path, 'wb') as f:
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
        except IOError as e:
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
        app_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'SkyWaveERP')
        os.makedirs(app_data_dir, exist_ok=True)
        self.temp_update_path = os.path.join(app_data_dir, "temp_update.zip")
    
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
    
    def apply_update(self, zip_path: str, executable_name: str = "main.py") -> bool:
        """
        تطبيق التحديث عن طريق تشغيل updater.exe
        
        Args:
            zip_path: مسار ملف ZIP المحمل
            executable_name: اسم الملف التنفيذي للبرنامج
        
        Returns:
            True إذا تم تشغيل المحدث بنجاح
        """
        try:
            # تحديد المجلد الحالي
            if getattr(sys, 'frozen', False):
                # البرنامج مجمع (EXE)
                current_dir = os.path.dirname(sys.executable)
                app_executable = os.path.basename(sys.executable)
            else:
                # البرنامج يعمل من Python
                current_dir = os.path.dirname(os.path.abspath(__file__))
                current_dir = os.path.dirname(current_dir)  # العودة للمجلد الرئيسي
                app_executable = "main.py"
            
            # مسار updater.exe أو updater.py
            updater_exe = os.path.join(current_dir, "updater.exe")
            updater_py = os.path.join(current_dir, "updater.py")
            
            # اختيار المحدث المناسب
            if os.path.exists(updater_exe):
                updater_path = updater_exe
                command = [updater_path, current_dir, zip_path, app_executable]
            elif os.path.exists(updater_py):
                updater_path = updater_py
                command = [sys.executable, updater_path, current_dir, zip_path, app_executable]
            else:
                raise FileNotFoundError("لم يتم العثور على updater.exe أو updater.py")
            
            # تشغيل المحدث في عملية منفصلة
            subprocess.Popen(
                command,
                cwd=current_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
            
            return True
            
        except Exception as e:
            print(f"خطأ في تطبيق التحديث: {e}")
            return False
    
    def cleanup_temp_files(self):
        """حذف الملفات المؤقتة"""
        try:
            if os.path.exists(self.temp_update_path):
                os.remove(self.temp_update_path)
        except Exception as e:
            print(f"تحذير: فشل حذف الملفات المؤقتة: {e}")
