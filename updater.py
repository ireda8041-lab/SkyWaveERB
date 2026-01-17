#!/usr/bin/env python3
"""
Sky Wave ERP - Professional Updater v2.0
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime

# Fix for PyInstaller windowed mode - redirect stdin/stdout/stderr to devnull
# This prevents "RuntimeError: lost sys.stdin" when running without console
if sys.stdin is None:
    sys.stdin = open(os.devnull)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

try:
    from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QFont, QFontDatabase
    from PyQt6.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QProgressBar,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    HAS_GUI = True
except ImportError:
    HAS_GUI = False

APP_NAME = "Sky Wave ERP"


# تحميل خط Cairo
def get_cairo_font(size=13, bold=False):
    """الحصول على خط Cairo"""
    font = QFont("Cairo", size)
    if bold:
        font.setWeight(QFont.Weight.Bold)
    return font


def load_cairo_font():
    """تحميل خط Cairo من الملف"""
    try:
        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        font_path = os.path.join(base_path, "assets", "font", "Cairo-VariableFont_slnt,wght.ttf")
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    return families[0]
    except Exception:
        pass
    return "Cairo"


class UpdateSignals(QObject):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    detail = pyqtSignal(str)
    speed = pyqtSignal(str)
    finished = pyqtSignal(bool, str)


class UpdateManager:
    def __init__(self, signals=None):
        self.signals = signals
        self.cancelled = False
        self.last_downloaded = 0
        self.last_time = time.time()

    def emit_status(self, text):
        if self.signals:
            self.signals.status.emit(text)

    def emit_detail(self, text):
        if self.signals:
            self.signals.detail.emit(text)

    def emit_progress(self, value):
        if self.signals:
            self.signals.progress.emit(value)

    def emit_speed(self, text):
        if self.signals:
            self.signals.speed.emit(text)

    def cancel(self):
        self.cancelled = True

    def calculate_speed(self, downloaded):
        current_time = time.time()
        time_diff = current_time - self.last_time
        if time_diff >= 0.5:
            bytes_diff = downloaded - self.last_downloaded
            speed = bytes_diff / time_diff
            self.last_downloaded = downloaded
            self.last_time = current_time
            if speed >= 1024 * 1024:
                return f"{speed / (1024 * 1024):.1f} MB/s"
            elif speed >= 1024:
                return f"{speed / 1024:.1f} KB/s"
            return f"{speed:.0f} B/s"
        return ""

    def download_file(self, url, dest_path):
        try:
            self.emit_status("Downloading...")
            request = urllib.request.Request(url, headers={"User-Agent": "SkyWaveERP-Updater/2.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                block_size = 8192
                with open(dest_path, "wb") as f:
                    while True:
                        if self.cancelled:
                            return False
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        downloaded += len(buffer)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.emit_progress(progress)
                            speed = self.calculate_speed(downloaded)
                            if speed:
                                self.emit_speed(speed)
                            dm = downloaded / (1024 * 1024)
                            tm = total_size / (1024 * 1024)
                            self.emit_detail(f"Downloaded {dm:.1f} MB / {tm:.1f} MB")
            return True
        except Exception as e:
            self.emit_detail(f"Error: {str(e)}")
            return False

    def create_backup(self, app_folder):
        try:
            self.emit_status("Creating backup...")
            backup_dir = os.path.join(tempfile.gettempdir(), "SkyWaveERP_Backup")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"backup_{timestamp}")
            os.makedirs(backup_path, exist_ok=True)
            files = [
                "skywave_local.db",
                "skywave_settings.json",
                "sync_config.json",
                "custom_fields.json",
            ]
            for filename in files:
                src = os.path.join(app_folder, filename)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(backup_path, filename))
                    self.emit_detail(f"Backed up: {filename}")
            return backup_path
        except Exception as e:
            self.emit_detail(f"Backup warning: {str(e)}")
            return ""

    def wait_for_app_close(self, timeout=30):
        self.emit_status("Waiting for app to close...")
        start = time.time()
        while time.time() - start < timeout:
            if self.cancelled:
                return False
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq SkyWaveERP.exe"],
                    capture_output=True,
                    text=True,
                    shell=True,
                )
                if "skywaveerp" not in result.stdout.lower():
                    return True
            except Exception:
                # فشل فحص العملية - نفترض أنها مغلقة
                return True
            remaining = int(timeout - (time.time() - start))
            self.emit_detail(f"Waiting {remaining}s...")
            time.sleep(1)
        return False

    def run_installer(self, setup_path, silent=False):
        try:
            self.emit_status("Starting installer...")
            if not os.path.exists(setup_path):
                self.emit_detail(f"File not found: {setup_path}")
                return False
            args = [setup_path]
            if silent:
                args.append("/SILENT")
            subprocess.Popen(args, shell=False)
            return True
        except Exception as e:
            self.emit_detail(f"Installer error: {str(e)}")
            return False

    def run_installer_and_wait(self, setup_path, signals=None):
        """Run installer in VERYSILENT mode and wait for completion"""
        try:
            if not os.path.exists(setup_path):
                self.emit_detail(f"File not found: {setup_path}")
                return False

            # Use VERYSILENT to hide the installer window completely
            # /SUPPRESSMSGBOXES suppresses message boxes
            # /NORESTART prevents automatic restart
            args = [
                setup_path,
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/CLOSEAPPLICATIONS",
            ]

            self.emit_detail("Running silent installation...")
            self.emit_status("Installing... Please wait")

            # Run and wait for completion
            process = subprocess.Popen(args, shell=False)

            # Monitor the process
            start_time = time.time()
            while process.poll() is None:
                if self.cancelled:
                    process.terminate()
                    return False

                elapsed = int(time.time() - start_time)
                self.emit_detail(f"Installing... ({elapsed}s)")
                time.sleep(1)

                # Timeout after 5 minutes
                if elapsed > 300:
                    self.emit_detail("Installation timeout!")
                    process.terminate()
                    return False

            # Check exit code
            exit_code = process.returncode
            if exit_code == 0:
                self.emit_detail("Installation completed successfully!")
                return True
            else:
                self.emit_detail(f"Installer exited with code: {exit_code}")
                return False

        except Exception as e:
            self.emit_detail(f"Installer error: {str(e)}")
            return False


if HAS_GUI:

    class UpdaterWindow(QMainWindow):
        def __init__(self, setup_path=None, app_folder=None, download_url=None, version_info=None):
            super().__init__()
            self.setup_path = setup_path
            self.app_folder = app_folder or os.getcwd()
            self.download_url = download_url
            self.version_info = version_info or {}
            self.signals = UpdateSignals()
            self.update_manager = UpdateManager(self.signals)
            self._init_ui()
            self._connect_signals()
            QTimer.singleShot(1000, self._start_update)

        def _init_ui(self):
            self.setWindowTitle(f"{APP_NAME} - Update")
            self.setFixedSize(520, 400)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

            central = QWidget()
            central.setStyleSheet("background: transparent;")
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(10, 10, 10, 10)

            main_frame = QFrame()
            main_frame.setObjectName("mainFrame")
            main_frame.setStyleSheet("""
                QFrame#mainFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #001A3A, stop:1 #0A2A55);
                    border: none;
                    border-radius: 30px;
                }
            """)

            frame_layout = QVBoxLayout(main_frame)
            frame_layout.setContentsMargins(35, 25, 35, 25)
            frame_layout.setSpacing(12)

            # Title bar
            title_bar = QFrame()
            title_bar.setStyleSheet("background: transparent; border: none;")
            title_layout = QHBoxLayout(title_bar)
            title_layout.setContentsMargins(0, 0, 0, 0)

            title = QLabel("Sky Wave ERP")
            title.setFont(get_cairo_font(20, bold=True))
            title.setStyleSheet("color: #0A6CF1; background: transparent; border: none;")
            title_layout.addWidget(title)
            title_layout.addStretch()

            close_btn = QPushButton("✕")
            close_btn.setFixedSize(32, 32)
            close_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; color: #64748B; font-size: 16px; border-radius: 16px; }
                QPushButton:hover { background: rgba(239, 68, 68, 0.2); color: #EF4444; }
            """)
            close_btn.clicked.connect(self._on_cancel)
            title_layout.addWidget(close_btn)
            frame_layout.addWidget(title_bar)

            # Version info
            if self.version_info:
                ver = self.version_info.get("version", "?")
                ver_label = QLabel(f"New Version: {ver}")
                ver_label.setFont(get_cairo_font(12))
                ver_label.setStyleSheet("color: #10B981; background: transparent; border: none;")
                ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                frame_layout.addWidget(ver_label)

            # Status
            self.status_label = QLabel("Preparing...")
            self.status_label.setFont(get_cairo_font(14, bold=True))
            self.status_label.setStyleSheet("color: white; background: transparent; border: none;")
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_layout.addWidget(self.status_label)

            # Progress bar
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setFixedHeight(24)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    border-radius: 12px;
                    background-color: rgba(30, 58, 95, 0.5);
                    text-align: center;
                    color: white;
                    font-weight: bold;
                    font-size: 11px;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #0A6CF1, stop:1 #10B981);
                    border-radius: 12px;
                }
            """)
            frame_layout.addWidget(self.progress_bar)

            # Speed
            self.speed_label = QLabel("")
            self.speed_label.setFont(get_cairo_font(10))
            self.speed_label.setStyleSheet("color: #64B5F6; background: transparent; border: none;")
            self.speed_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            frame_layout.addWidget(self.speed_label)

            # Details
            details_frame = QFrame()
            details_frame.setStyleSheet(
                "background: rgba(0, 26, 58, 0.6); border: none; border-radius: 18px;"
            )
            details_frame.setFixedHeight(100)
            details_layout = QVBoxLayout(details_frame)
            details_layout.setContentsMargins(15, 12, 15, 12)

            self.details_text = QTextEdit()
            self.details_text.setReadOnly(True)
            self.details_text.setStyleSheet(
                "background: transparent; border: none; color: #90CAF9; font-size: 11px;"
            )
            details_layout.addWidget(self.details_text)
            frame_layout.addWidget(details_frame)

            frame_layout.addStretch()

            # Cancel button
            self.cancel_btn = QPushButton("Cancel")
            self.cancel_btn.setFixedSize(130, 40)
            self.cancel_btn.setFont(get_cairo_font(11, bold=True))
            self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.cancel_btn.setStyleSheet("""
                QPushButton { background: rgba(239, 68, 68, 0.15); border: none; border-radius: 20px; color: #EF4444; }
                QPushButton:hover { background: #EF4444; color: white; }
            """)
            self.cancel_btn.clicked.connect(self._on_cancel)

            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            btn_layout.addWidget(self.cancel_btn)
            btn_layout.addStretch()
            frame_layout.addLayout(btn_layout)

            layout.addWidget(main_frame)
            self._center_window()

        def _center_window(self):
            screen = QApplication.primaryScreen()
            if screen:
                g = screen.geometry()
                self.move((g.width() - self.width()) // 2, (g.height() - self.height()) // 2)

        def _connect_signals(self):
            self.signals.progress.connect(self._update_progress)
            self.signals.status.connect(self._update_status)
            self.signals.detail.connect(self._add_detail)
            self.signals.speed.connect(self._update_speed)
            self.signals.finished.connect(self._on_finished)

        def _update_progress(self, value):
            self.progress_bar.setValue(value)

        def _update_status(self, text):
            self.status_label.setText(text)

        def _add_detail(self, text):
            ts = datetime.now().strftime("%H:%M:%S")
            self.details_text.append(f"[{ts}] {text}")
            sb = self.details_text.verticalScrollBar()
            sb.setValue(sb.maximum())

        def _update_speed(self, text):
            self.speed_label.setText(f"Speed: {text}")

        def _on_finished(self, success, message):
            if success:
                self.status_label.setText("✓ " + message)
                self.status_label.setStyleSheet(
                    "color: #10B981; background: transparent; border: none;"
                )
                self.cancel_btn.setText("Close")
                self.cancel_btn.setStyleSheet("""
                    QPushButton { background: rgba(16, 185, 129, 0.2); border: none; border-radius: 20px; color: #10B981; font-weight: bold; }
                    QPushButton:hover { background: #10B981; color: white; }
                """)
                # Don't auto-close - let _restart_app handle it
            else:
                self.status_label.setText("✗ " + message)
                self.status_label.setStyleSheet(
                    "color: #EF4444; background: transparent; border: none;"
                )
                self.cancel_btn.setText("Close")

        def _on_cancel(self):
            self.update_manager.cancel()
            self.close()

        def _start_update(self):
            threading.Thread(target=self._run_update, daemon=True).start()

        def _run_update(self):
            try:
                self.signals.progress.emit(5)
                self.update_manager.wait_for_app_close(timeout=10)
                self.signals.progress.emit(10)

                # Backup
                backup = self.update_manager.create_backup(self.app_folder)
                if backup:
                    self.signals.detail.emit(f"Backup: {backup}")
                self.signals.progress.emit(20)

                # Download if needed
                if self.download_url and not self.setup_path:
                    temp_dir = tempfile.gettempdir()
                    self.setup_path = os.path.join(temp_dir, "SkyWaveERP_Update.exe")
                    if not self.update_manager.download_file(self.download_url, self.setup_path):
                        if self.update_manager.cancelled:
                            return
                        self.signals.finished.emit(False, "Download failed")
                        return

                self.signals.progress.emit(80)

                # Verify
                if not self.setup_path or not os.path.exists(self.setup_path):
                    self.signals.finished.emit(False, "Setup file not found")
                    return

                if os.path.getsize(self.setup_path) < 1000:
                    self.signals.finished.emit(False, "Setup file is corrupted")
                    return

                self.signals.progress.emit(90)
                self.signals.status.emit("Installing update...")
                self.signals.detail.emit("Starting silent installation...")

                # Run installer in SILENT mode and WAIT for it to complete
                if not self.update_manager.run_installer_and_wait(self.setup_path, self.signals):
                    self.signals.finished.emit(False, "Installation failed")
                    return

                self.signals.progress.emit(100)
                self.signals.finished.emit(True, "Update completed! Restarting...")

                # Restart the app after successful update
                QTimer.singleShot(2000, self._restart_app)

            except Exception as e:
                self.signals.finished.emit(False, str(e))

        def _restart_app(self):
            """Restart Sky Wave ERP after update"""
            try:
                app_exe = os.path.join(self.app_folder, "SkyWaveERP.exe")
                if os.path.exists(app_exe):
                    subprocess.Popen([app_exe], shell=False)
                    self.signals.detail.emit("App restarted successfully!")
            except Exception as e:
                self.signals.detail.emit(f"Could not restart app: {e}")
            finally:
                QTimer.singleShot(1000, self.close)


def run_console_updater(setup_path=None, app_folder=None, download_url=None):
    print("=" * 50)
    print(f"  {APP_NAME} Updater v2.0")
    print("=" * 50)

    manager = UpdateManager()

    print("\nWaiting for app to close...")
    time.sleep(3)

    if app_folder:
        backup = manager.create_backup(app_folder)
        if backup:
            print(f"Backup created: {backup}")

    if download_url and not setup_path:
        print("\nDownloading update...")
        temp_dir = tempfile.gettempdir()
        setup_path = os.path.join(temp_dir, "SkyWaveERP_Update.exe")
        if not manager.download_file(download_url, setup_path):
            print("Download failed!")
            time.sleep(3)
            return

    if not setup_path or not os.path.exists(setup_path):
        print("Setup file not found!")
        time.sleep(3)
        return

    print("\nStarting installer...")
    if manager.run_installer(setup_path):
        print("Installer started successfully!")
    else:
        print("Failed to start installer!")
        time.sleep(3)

    time.sleep(2)


def main():
    app_folder = None
    setup_path = None
    download_url = None
    version_info = {}

    args = sys.argv[1:]
    if len(args) >= 2:
        app_folder = args[0]
        setup_path = args[1]
    elif len(args) == 1:
        if args[0].startswith("http"):
            download_url = args[0]
        else:
            setup_path = args[0]

    # Read version info
    try:
        vf = os.path.join(app_folder or os.getcwd(), "version.json")
        if os.path.exists(vf):
            with open(vf, encoding="utf-8") as f:
                version_info = json.load(f)
                if not download_url:
                    download_url = version_info.get("url")
    except Exception:
        # فشل قراءة معلومات الإصدار
        pass

    if HAS_GUI:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        window = UpdaterWindow(setup_path, app_folder, download_url, version_info)
        window.show()
        sys.exit(app.exec())
    else:
        run_console_updater(setup_path, app_folder, download_url)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Safe print for windowed mode
        try:
            print(f"Fatal error: {e}")
            import traceback

            traceback.print_exc()
        except Exception:
            # فشل طباعة الخطأ
            pass
        time.sleep(5)
        sys.exit(1)
