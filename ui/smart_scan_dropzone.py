"""
SmartScanDropzone - Widget لرفع صور إيصالات الدفع
Supports drag & drop and file selection for payment receipt scanning.
"""

import os

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from core.scan_result import ScanResult
from services.smart_scan_service import SmartScanService
from ui.styles import COLORS


class ScanWorker(QThread):
    """Worker thread for scanning receipts without blocking UI."""

    finished = pyqtSignal(object)  # ScanResult

    def __init__(self, service: SmartScanService, image_path: str):
        super().__init__()
        self.service = service
        self.image_path = image_path

    def run(self):
        result = self.service.scan_receipt(self.image_path)
        self.finished.emit(result)


class SmartScanDropzone(QFrame):
    """
    Widget لرفع صور إيصالات الدفع مع دعم Drag & Drop

    Signals:
        scan_started: يُرسل عند بدء المسح
        scan_completed: يُرسل عند اكتمال المسح مع البيانات (dict)
        scan_failed: يُرسل عند فشل المسح مع رسالة الخطأ (str)
    """

    # Signals
    scan_started = pyqtSignal()
    scan_completed = pyqtSignal(dict)
    scan_failed = pyqtSignal(str)

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

    def __init__(self, parent=None, settings: dict | None = None):
        super().__init__(parent)

        self._settings = settings
        self._service: SmartScanService | None = None
        self._worker: ScanWorker | None = None
        self._is_loading = False

        self._init_service()
        self._setup_ui()
        self._apply_styles()

        # Enable drag & drop
        self.setAcceptDrops(True)

    def _init_service(self):
        """Initialize the SmartScanService."""
        try:
            self._service = SmartScanService(settings=self._settings)
        except Exception as e:
            print(f"WARNING: [SmartScanDropzone] فشل تهيئة الخدمة: {e}")
            self._service = None


    def _setup_ui(self):
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Icon label
        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setText("📷")
        self._icon_label.setFont(QFont("Segoe UI Emoji", 32))
        layout.addWidget(self._icon_label)

        # Main text label
        self._text_label = QLabel("ارفع سكرين شوت التحويل لملء البيانات تلقائياً")
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setWordWrap(True)
        self._text_label.setFont(QFont("Cairo", 12, QFont.Weight.Bold))
        layout.addWidget(self._text_label)

        # Sub text label (for loading/error states)
        self._sub_label = QLabel("أو اضغط لاختيار ملف")
        self._sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_label.setFont(QFont("Cairo", 10))
        self._sub_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(self._sub_label)

        # Retry button (hidden by default)
        self._retry_btn = QPushButton("حاول مرة أخرى")
        self._retry_btn.setVisible(False)
        self._retry_btn.clicked.connect(self.reset)
        self._retry_btn.setFixedWidth(150)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self._retry_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Set size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(120)
        self.setMaximumHeight(150)

    def _apply_styles(self):
        """Apply styles to the widget."""
        self.setStyleSheet(f"""
            SmartScanDropzone {{
                background-color: {COLORS['bg_medium']};
                border: 2px dashed {COLORS['border']};
                border-radius: 12px;
            }}
            SmartScanDropzone:hover {{
                border-color: {COLORS['primary']};
                background-color: rgba(10, 108, 241, 0.1);
            }}
        """)

        self._retry_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['warning']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #E55025;
            }}
        """)

    def _validate_file(self, file_path: str) -> tuple[bool, str]:
        """
        Validate if the file is a supported image.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not os.path.exists(file_path):
            return False, "الملف غير موجود"

        _, ext = os.path.splitext(file_path)
        if ext.lower() not in self.SUPPORTED_EXTENSIONS:
            return False, "يرجى اختيار ملف صورة (JPG, PNG, GIF, WEBP)"

        return True, ""


    def _start_scan(self, file_path: str):
        """Start scanning the receipt image."""
        # Validate file first
        is_valid, error_msg = self._validate_file(file_path)
        if not is_valid:
            self.set_error(error_msg)
            return

        # Check if service is available
        if not self._service or not self._service.is_available():
            self.set_error("خدمة المسح الذكي غير متاحة. تحقق من إعدادات API")
            return

        # Set loading state
        self.set_loading(True)
        self.scan_started.emit()

        # Start worker thread
        self._worker = ScanWorker(self._service, file_path)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.start()

    def _on_scan_finished(self, result: ScanResult):
        """Handle scan completion."""
        self.set_loading(False)

        if result.success:
            # Convert ScanResult to dict for signal
            data = {
                'amount': result.amount,
                'date': result.date,
                'reference_number': result.reference_number,
                'sender_name': result.sender_name,
                'platform': result.platform
            }
            self._show_success()
            self.scan_completed.emit(data)
        else:
            self.set_error(result.error_message or "حدث خطأ غير متوقع")
            self.scan_failed.emit(result.error_message or "حدث خطأ غير متوقع")

    def _show_success(self):
        """Show success state briefly."""
        self._icon_label.setText("✅")
        self._text_label.setText("تم استخراج البيانات بنجاح!")
        self._sub_label.setText("تم ملء الحقول تلقائياً")
        self._sub_label.setStyleSheet("color: #10B981;")  # Green
        self._retry_btn.setVisible(False)

        self.setStyleSheet("""
            SmartScanDropzone {
                background-color: rgba(16, 185, 129, 0.1);
                border: 2px solid #10B981;
                border-radius: 12px;
            }
        """)

    # === Public Methods ===

    def set_loading(self, loading: bool):
        """Toggle loading state."""
        self._is_loading = loading

        if loading:
            self._icon_label.setText("⏳")
            self._text_label.setText("جاري المسح الذكي...")
            self._sub_label.setText("يرجى الانتظار")
            self._sub_label.setStyleSheet(f"color: {COLORS['primary']};")
            self._retry_btn.setVisible(False)
            self.setEnabled(False)

            self.setStyleSheet(f"""
                SmartScanDropzone {{
                    background-color: rgba(10, 108, 241, 0.1);
                    border: 2px solid {COLORS['primary']};
                    border-radius: 12px;
                }}
            """)
        else:
            self.setEnabled(True)

    def set_error(self, message: str):
        """Display error message."""
        self._is_loading = False
        self._icon_label.setText("❌")
        self._text_label.setText(message)
        self._sub_label.setText("")
        self._retry_btn.setVisible(True)
        self.setEnabled(True)

        self.setStyleSheet(f"""
            SmartScanDropzone {{
                background-color: rgba(255, 79, 216, 0.1);
                border: 2px solid {COLORS['danger']};
                border-radius: 12px;
            }}
        """)

    def reset(self):
        """Reset to initial state."""
        self._is_loading = False
        self._icon_label.setText("📷")
        self._text_label.setText("ارفع سكرين شوت التحويل لملء البيانات تلقائياً")
        self._sub_label.setText("أو اضغط لاختيار ملف")
        self._sub_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self._retry_btn.setVisible(False)
        self.setEnabled(True)
        self._apply_styles()

    def is_available(self) -> bool:
        """Check if the smart scan service is available."""
        return self._service is not None and self._service.is_available()


    # === Event Handlers ===

    def mousePressEvent(self, event):
        """Handle mouse click to open file dialog."""
        if self._is_loading:
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._open_file_dialog()

    def _open_file_dialog(self):
        """Open file dialog to select an image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "اختر صورة إيصال الدفع",
            "",
            "Images (*.jpg *.jpeg *.png *.gif *.webp);;All Files (*)"
        )

        if file_path:
            self._start_scan(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent | None):  # type: ignore[override]
        """Handle drag enter event."""
        if event is None or self._is_loading:
            if event:
                event.ignore()
            return

        mime_data = event.mimeData()
        if mime_data is not None and mime_data.hasUrls():
            # Check if at least one file is an image
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                _, ext = os.path.splitext(file_path)
                if ext.lower() in self.SUPPORTED_EXTENSIONS:
                    event.acceptProposedAction()
                    # Visual feedback
                    self.setStyleSheet(f"""
                        SmartScanDropzone {{
                            background-color: rgba(10, 108, 241, 0.2);
                            border: 2px solid {COLORS['primary']};
                            border-radius: 12px;
                        }}
                    """)
                    return

        event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self._apply_styles()

    def dropEvent(self, event: QDropEvent | None):  # type: ignore[override]
        """Handle drop event."""
        if event is None or self._is_loading:
            if event:
                event.ignore()
            return

        self._apply_styles()

        mime_data = event.mimeData()
        if mime_data is not None and mime_data.hasUrls():
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                _, ext = os.path.splitext(file_path)
                if ext.lower() in self.SUPPORTED_EXTENSIONS:
                    event.acceptProposedAction()
                    self._start_scan(file_path)
                    return

        # No valid image found
        self.set_error("يرجى اختيار ملف صورة (JPG, PNG, GIF, WEBP)")
