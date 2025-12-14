# الملف: ui/invoice_scan_widget.py
"""
InvoiceScanWidget - Widget لمسح الفواتير بالذكاء الاصطناعي 🧠

يدعم:
- Drag & Drop للصور
- اختيار ملف من الجهاز
- عرض حالة التحميل
- إرجاع البيانات المستخرجة للنموذج
"""

import os
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QMessageBox,
)

from ui.styles import COLORS, get_cairo_font


class InvoiceScanWorker(QThread):
    """Worker thread لمسح الفواتير بدون تجميد الواجهة"""

    finished = pyqtSignal(dict)  # نتيجة المسح
    error = pyqtSignal(str)  # رسالة الخطأ

    def __init__(self, image_path: str, api_key: Optional[str] = None):
        super().__init__()
        self.image_path = image_path
        self.api_key = api_key

    def run(self):
        try:
            from services.smart_scan_service import SmartScanService
            
            service = SmartScanService(api_key=self.api_key)
            
            if not service.is_available():
                self.error.emit("خدمة المسح الذكي غير متاحة. تحقق من مفتاح API")
                return
            
            result = service.scan_invoice_image(self.image_path)
            
            if "error" in result:
                self.error.emit(result.get("raw_text", "فشل في تحليل الصورة"))
            else:
                self.finished.emit(result)
                
        except FileNotFoundError as e:
            self.error.emit(f"الملف غير موجود: {e}")
        except Exception as e:
            self.error.emit(f"خطأ: {str(e)}")


class InvoiceScanWidget(QFrame):
    """
    Widget لمسح الفواتير بالذكاء الاصطناعي
    
    Signals:
        scan_started: يُرسل عند بدء المسح
        scan_completed: يُرسل عند اكتمال المسح مع البيانات (dict)
        scan_failed: يُرسل عند فشل المسح مع رسالة الخطأ (str)
    """

    # Signals
    scan_started = pyqtSignal()
    scan_completed = pyqtSignal(dict)
    scan_failed = pyqtSignal(str)

    # الصيغ المدعومة
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

    def __init__(self, parent=None, api_key: Optional[str] = None):
        super().__init__(parent)

        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._worker: Optional[InvoiceScanWorker] = None
        self._is_loading = False
        self._last_result: Optional[dict] = None

        self._setup_ui()
        self._apply_styles()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        """إعداد واجهة المستخدم"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 25, 20, 20)
        layout.setSpacing(8)

        # أيقونة - حجم أكبر للوضوح
        self._icon_label = QLabel("📷")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("font-size: 48px;")
        layout.addWidget(self._icon_label)

        # النص الرئيسي
        self._text_label = QLabel("اسحب صورة الفاتورة هنا")
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setWordWrap(True)
        self._text_label.setFont(get_cairo_font(14, bold=True))
        self._text_label.setStyleSheet(f"color: {COLORS.get('text_primary', '#ffffff')};")
        layout.addWidget(self._text_label)

        # النص الفرعي
        self._sub_label = QLabel("أو اضغط لاختيار ملف • يدعم JPG, PNG, WEBP")
        self._sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_label.setFont(get_cairo_font(11))
        self._sub_label.setStyleSheet(f"color: {COLORS.get('text_secondary', '#888')};")
        layout.addWidget(self._sub_label)

        # زر إعادة المحاولة (مخفي افتراضياً)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self._retry_btn = QPushButton("🔄 حاول مرة أخرى")
        self._retry_btn.setVisible(False)
        self._retry_btn.clicked.connect(self.reset)
        self._retry_btn.setFixedWidth(160)
        self._retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(self._retry_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # إعدادات الحجم
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(180)
        self.setMaximumHeight(220)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_styles(self):
        """تطبيق الأنماط"""
        primary = COLORS.get('primary', '#0A6CF1')
        bg = COLORS.get('bg_medium', '#2D2D2D')
        border = COLORS.get('border', '#404040')
        warning = COLORS.get('warning', '#F59E0B')
        
        self.setStyleSheet(f"""
            InvoiceScanWidget {{
                background-color: {bg};
                border: 2px dashed {border};
                border-radius: 16px;
            }}
            InvoiceScanWidget:hover {{
                border-color: {primary};
                background-color: rgba(10, 108, 241, 0.08);
            }}
        """)

        self._retry_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {warning};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #E55025;
            }}
        """)

    def _validate_file(self, file_path: str) -> tuple[bool, str]:
        """التحقق من صحة الملف"""
        if not os.path.exists(file_path):
            return False, "الملف غير موجود"

        _, ext = os.path.splitext(file_path)
        if ext.lower() not in self.SUPPORTED_EXTENSIONS:
            supported = ", ".join(self.SUPPORTED_EXTENSIONS)
            return False, f"صيغة غير مدعومة. الصيغ المدعومة: {supported}"

        # التحقق من الحجم (5 MB كحد أقصى)
        file_size = os.path.getsize(file_path)
        if file_size > 5 * 1024 * 1024:
            return False, "حجم الملف كبير جداً (الحد الأقصى 5 MB)"

        return True, ""

    def _start_scan(self, file_path: str):
        """بدء مسح الفاتورة"""
        # التحقق من الملف
        is_valid, error_msg = self._validate_file(file_path)
        if not is_valid:
            self._show_error(error_msg)
            return

        # التحقق من مفتاح API
        if not self._api_key:
            self._show_error("مفتاح Gemini API غير موجود. أضفه في الإعدادات")
            return

        # تعيين حالة التحميل
        self._set_loading(True)
        self.scan_started.emit()

        # بدء المسح في thread منفصل
        self._worker = InvoiceScanWorker(file_path, self._api_key)
        self._worker.finished.connect(self._on_scan_success)
        self._worker.error.connect(self._on_scan_error)
        self._worker.start()

    def _on_scan_success(self, result: dict):
        """معالجة نجاح المسح"""
        self._set_loading(False)
        self._last_result = result
        self._show_success(result)
        self.scan_completed.emit(result)

    def _on_scan_error(self, error_msg: str):
        """معالجة فشل المسح"""
        self._set_loading(False)
        self._show_error(error_msg)
        self.scan_failed.emit(error_msg)

    def _set_loading(self, loading: bool):
        """تعيين حالة التحميل"""
        self._is_loading = loading
        primary = COLORS.get('primary', '#0A6CF1')

        if loading:
            self._icon_label.setText("⏳")
            self._text_label.setText("جاري تحليل الفاتورة بالذكاء الاصطناعي...")
            self._sub_label.setText("يرجى الانتظار قليلاً")
            self._sub_label.setStyleSheet(f"color: {primary};")
            self._retry_btn.setVisible(False)
            self.setEnabled(False)
            self.setCursor(Qt.CursorShape.WaitCursor)

            self.setStyleSheet(f"""
                InvoiceScanWidget {{
                    background-color: rgba(10, 108, 241, 0.1);
                    border: 2px solid {primary};
                    border-radius: 16px;
                }}
            """)
        else:
            self.setEnabled(True)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _show_success(self, result: dict):
        """عرض حالة النجاح"""
        merchant = result.get('merchant_name', 'غير معروف')
        total = result.get('total_amount', 0)
        currency = result.get('currency', 'EGP')
        items_count = len(result.get('items', []))

        self._icon_label.setText("✅")
        self._text_label.setText("تم استخراج البيانات بنجاح!")
        self._sub_label.setText(f"{merchant} • {total} {currency} • {items_count} بند")
        self._sub_label.setStyleSheet("color: #10B981;")
        self._retry_btn.setVisible(False)

        self.setStyleSheet("""
            InvoiceScanWidget {
                background-color: rgba(16, 185, 129, 0.1);
                border: 2px solid #10B981;
                border-radius: 16px;
            }
        """)

    def _show_error(self, message: str):
        """عرض حالة الخطأ بشكل هادئ"""
        self._is_loading = False
        warning = COLORS.get('warning', '#F59E0B')
        
        # تحديد نوع الخطأ لعرض رسالة مناسبة
        if "API" in message or "مفتاح" in message:
            self._icon_label.setText("🔑")
            self._text_label.setText("ميزة المسح الذكي غير مفعّلة")
            self._sub_label.setText("أضف مفتاح Gemini API في الإعدادات لتفعيلها")
            self._sub_label.setStyleSheet(f"color: {warning};")
            border_color = warning
        else:
            self._icon_label.setText("⚠️")
            self._text_label.setText(message)
            self._sub_label.setText("يمكنك إدخال البيانات يدوياً")
            self._sub_label.setStyleSheet(f"color: {COLORS.get('text_secondary', '#888')};")
            border_color = COLORS.get('danger', '#EF4444')
        
        self._retry_btn.setVisible(True)
        self.setEnabled(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setStyleSheet(f"""
            InvoiceScanWidget {{
                background-color: rgba(245, 158, 11, 0.08);
                border: 2px dashed {border_color};
                border-radius: 16px;
            }}
        """)

    # === Public Methods ===

    def reset(self):
        """إعادة تعيين الـ Widget للحالة الأولية"""
        self._is_loading = False
        self._last_result = None
        self._icon_label.setText("📷")
        self._text_label.setText("اسحب صورة الفاتورة هنا")
        self._sub_label.setText("أو اضغط لاختيار ملف • يدعم JPG, PNG, WEBP")
        self._sub_label.setStyleSheet(f"color: {COLORS.get('text_secondary', '#888')};")
        self._retry_btn.setVisible(False)
        self.setEnabled(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_styles()

    def set_api_key(self, api_key: str):
        """تعيين مفتاح API"""
        self._api_key = api_key

    def get_last_result(self) -> Optional[dict]:
        """الحصول على آخر نتيجة مسح"""
        return self._last_result

    def is_available(self) -> bool:
        """هل الخدمة متاحة؟"""
        return bool(self._api_key)

    # === Event Handlers ===

    def mousePressEvent(self, event):
        """معالجة النقر لفتح نافذة اختيار الملف"""
        if self._is_loading:
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._open_file_dialog()

    def _open_file_dialog(self):
        """فتح نافذة اختيار الملف"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "اختر صورة الفاتورة",
            "",
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp);;All Files (*)"
        )

        if file_path:
            self._start_scan(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """معالجة دخول السحب"""
        if self._is_loading:
            event.ignore()
            return

        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                _, ext = os.path.splitext(file_path)
                if ext.lower() in self.SUPPORTED_EXTENSIONS:
                    event.acceptProposedAction()
                    primary = COLORS.get('primary', '#0A6CF1')
                    self.setStyleSheet(f"""
                        InvoiceScanWidget {{
                            background-color: rgba(10, 108, 241, 0.15);
                            border: 2px solid {primary};
                            border-radius: 16px;
                        }}
                    """)
                    return

        event.ignore()

    def dragLeaveEvent(self, event):
        """معالجة مغادرة السحب"""
        self._apply_styles()

    def dropEvent(self, event: QDropEvent):
        """معالجة الإفلات"""
        if self._is_loading:
            event.ignore()
            return

        self._apply_styles()

        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                _, ext = os.path.splitext(file_path)
                if ext.lower() in self.SUPPORTED_EXTENSIONS:
                    event.acceptProposedAction()
                    self._start_scan(file_path)
                    return

        self._show_error("يرجى اختيار ملف صورة صالح")
