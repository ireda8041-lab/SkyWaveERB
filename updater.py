#!/usr/bin/env python3
"""
Sky Wave ERP - Professional Updater
محدث احترافي مع واجهة رسومية
"""

import os
import subprocess
import sys
import threading
import time

try:
    from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QFont, QIcon  # noqa: F401
    from PyQt6.QtWidgets import (
        QApplication,
        QFrame,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
    HAS_GUI = True
except ImportError:
    HAS_GUI = False


class UpdateSignals(QObject):
    """إشارات للتواصل بين الـ threads"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)


class UpdaterWindow(QMainWindow):
    """نافذة المحدث الاحترافية"""

    def __init__(self, setup_path: str, app_folder: str):
        super().__init__()
        self.setup_path = setup_path
        self.app_folder = app_folder
        self.signals = UpdateSignals()

        self.init_ui()
        self.connect_signals()

        # بدء التحديث بعد ثانية
        QTimer.singleShot(1000, self.start_update)

    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        self.setWindowTitle("Sky Wave ERP - تحديث البرنامج")
        self.setFixedSize(500, 300)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # الويدجت الرئيسي
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # الإطار الرئيسي
        main_frame = QFrame()
        main_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
                border: 2px solid #00d4ff;
                border-radius: 15px;
            }
        """)
        frame_layout = QVBoxLayout(main_frame)
        frame_layout.setContentsMargins(30, 30, 30, 30)
        frame_layout.setSpacing(20)

        # العنوان
        title = QLabel("🚀 Sky Wave ERP")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Cairo", 24, QFont.Weight.Bold))
        title.setStyleSheet("color: #00d4ff; background: transparent;")
        frame_layout.addWidget(title)

        # العنوان الفرعي
        subtitle = QLabel("جاري تحديث البرنامج...")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Cairo", 12))
        subtitle.setStyleSheet("color: #ffffff; background: transparent;")
        frame_layout.addWidget(subtitle)

        frame_layout.addSpacing(20)

        # شريط التقدم
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #00d4ff;
                border-radius: 10px;
                background-color: #1a1a2e;
                height: 25px;
                text-align: center;
                color: white;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00d4ff, stop:1 #00ff88);
                border-radius: 8px;
            }
        """)
        frame_layout.addWidget(self.progress_bar)

        # حالة التحديث
        self.status_label = QLabel("⏳ جاري التحضير...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Cairo", 11))
        self.status_label.setStyleSheet("color: #aaaaaa; background: transparent;")
        frame_layout.addWidget(self.status_label)

        frame_layout.addStretch()

        # زر الإلغاء
        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.setFixedSize(120, 40)
        self.cancel_btn.setFont(QFont("Cairo", 11))
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 2px solid #ff4757;
                border-radius: 10px;
                color: #ff4757;
            }
            QPushButton:hover {
                background: #ff4757;
                color: white;
            }
        """)
        self.cancel_btn.clicked.connect(self.close)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        frame_layout.addLayout(btn_layout)

        layout.addWidget(main_frame)

        # توسيط النافذة
        self.center_window()

    def center_window(self):
        """توسيط النافذة على الشاشة"""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def connect_signals(self):
        """ربط الإشارات"""
        self.signals.progress.connect(self.update_progress)
        self.signals.status.connect(self.update_status)
        self.signals.finished.connect(self.on_finished)

    def update_progress(self, value: int):
        """تحديث شريط التقدم"""
        self.progress_bar.setValue(value)

    def update_status(self, text: str):
        """تحديث نص الحالة"""
        self.status_label.setText(text)

    def on_finished(self, success: bool, message: str):
        """عند انتهاء التحديث"""
        if success:
            self.status_label.setText("✅ " + message)
            self.status_label.setStyleSheet("color: #00ff88; background: transparent;")
            self.cancel_btn.setText("إغلاق")
            QTimer.singleShot(2000, self.close)
        else:
            self.status_label.setText("❌ " + message)
            self.status_label.setStyleSheet("color: #ff4757; background: transparent;")
            self.cancel_btn.setText("إغلاق")

    def start_update(self):
        """بدء عملية التحديث"""
        thread = threading.Thread(target=self.run_update, daemon=True)
        thread.start()

    def run_update(self):
        """تنفيذ التحديث"""
        try:
            # الخطوة 1: التحضير
            self.signals.status.emit("⏳ انتظار إغلاق البرنامج...")
            self.signals.progress.emit(10)
            time.sleep(2)

            # الخطوة 2: التحقق من الملف
            self.signals.status.emit("🔍 التحقق من ملف التحديث...")
            self.signals.progress.emit(30)

            if not os.path.exists(self.setup_path):
                self.signals.finished.emit(False, "ملف التحديث غير موجود")
                return

            time.sleep(1)

            # الخطوة 3: تشغيل ملف Setup
            self.signals.status.emit("🚀 تشغيل برنامج التثبيت...")
            self.signals.progress.emit(60)

            # تشغيل ملف الـ Setup بدون shell لتجنب ثغرات الأمان
            subprocess.Popen([self.setup_path], shell=False)

            self.signals.progress.emit(90)
            time.sleep(1)

            # الخطوة 4: الانتهاء
            self.signals.progress.emit(100)
            self.signals.finished.emit(True, "تم تشغيل برنامج التثبيت بنجاح!")

        except Exception as e:
            self.signals.finished.emit(False, f"خطأ: {str(e)}")


def run_console_updater(setup_path: str, app_folder: str):
    """تشغيل المحدث في وضع الكونسول (بدون GUI)"""
    print("=" * 60)
    print("🚀 Sky Wave ERP Updater")
    print("=" * 60)

    print(f"📦 ملف التحديث: {setup_path}")
    print(f"📁 مجلد البرنامج: {app_folder}")

    print("\n⏳ انتظار إغلاق البرنامج...")
    time.sleep(3)

    if not os.path.exists(setup_path):
        print(f"❌ خطأ: ملف التحديث غير موجود: {setup_path}")
        input("اضغط Enter للخروج...")
        return

    print("🚀 تشغيل برنامج التثبيت...")

    try:
        subprocess.Popen([setup_path], shell=False)
        print("✅ تم تشغيل برنامج التثبيت بنجاح!")
        print("\n📌 يرجى متابعة التثبيت من نافذة برنامج التثبيت")
    except Exception as e:
        print(f"❌ خطأ: {e}")
        input("اضغط Enter للخروج...")
        return

    time.sleep(2)


def main():
    """الدالة الرئيسية"""
    # التحقق من المعاملات
    if len(sys.argv) < 3:
        print("❌ خطأ: معاملات غير كافية")
        print("الاستخدام: updater.py <app_folder> <setup_path>")
        input("اضغط Enter للخروج...")
        sys.exit(1)

    app_folder = sys.argv[1]
    setup_path = sys.argv[2]

    # تشغيل المحدث
    if HAS_GUI:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        window = UpdaterWindow(setup_path, app_folder)
        window.show()

        sys.exit(app.exec())
    else:
        run_console_updater(setup_path, app_folder)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ خطأ فادح: {e}")
        import traceback
        traceback.print_exc()
        input("اضغط Enter للخروج...")
        sys.exit(1)
