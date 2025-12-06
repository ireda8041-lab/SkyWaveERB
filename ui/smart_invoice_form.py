# الملف: ui/smart_invoice_form.py
"""
واجهة الفاتورة الذكية مع Smart Scan
يمكن تشغيل هذا الملف مباشرة لتجربة الميزة بمعزل عن باقي البرنامج.
"""

import json
import os
import sys

# إضافة المسار الجذر للمشروع عند التشغيل المباشر
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QDate, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.smart_scan_service import SmartScanService


# ---------------------------------------------------------
# 🧵 Worker Thread: الجندي المجهول
# وظيفته: القيام بالعمل الشاق في الخلفية لكي لا تتجمد الواجهة
# ---------------------------------------------------------
class ScanWorker(QThread):
    finished = pyqtSignal(dict)  # إشارة نجاح مع البيانات
    error = pyqtSignal(str)  # إشارة خطأ

    def __init__(self, service: SmartScanService, image_path: str):
        super().__init__()
        self.service = service
        self.image_path = image_path

    def run(self):
        try:
            # استدعاء Gemini API (قد يستغرق 3-5 ثواني)
            data = self.service.scan_invoice_image(self.image_path)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------
# 🖥️ UI Class: واجهة الفاتورة الذكية
# ---------------------------------------------------------
class SmartInvoiceForm(QWidget):
    """نموذج فاتورة ذكي مع دعم المسح بالذكاء الاصطناعي"""

    def __init__(self, api_key: str | None = None):
        super().__init__()
        self.setWindowTitle("SkyWave ERP - فاتورة جديدة ⚡")
        self.resize(800, 600)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)  # اتجاه عربي

        # تحميل مفتاح API من الإعدادات أو المعامل
        self.api_key = api_key or self._load_api_key()
        
        # تهيئة خدمة الذكاء الاصطناعي
        self.scan_service = SmartScanService(api_key=self.api_key)
        
        self.worker: ScanWorker | None = None
        self.progress: QProgressDialog | None = None
        
        self.init_ui()

    def _load_api_key(self) -> str | None:
        """تحميل مفتاح API من ملف الإعدادات"""
        settings_path = "skywave_settings.json"
        if os.path.exists(settings_path):
            try:
                with open(settings_path, encoding="utf-8") as f:
                    settings = json.load(f)
                    return settings.get("smart_scan", {}).get("gemini_api_key")
            except Exception:
                pass
        return os.getenv("GEMINI_API_KEY")

    def init_ui(self):
        layout = QVBoxLayout()

        # --- الشريط العلوي (العنوان وزر الذكاء الاصطناعي) ---
        top_bar = QHBoxLayout()

        title = QLabel("إدخال فاتورة جديدة")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))

        self.btn_smart_scan = QPushButton(" مسح ذكي (Smart Scan) 🤖")
        self.btn_smart_scan.setStyleSheet("""
            QPushButton {
                background-color: #6200ea;
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7c4dff;
            }
            QPushButton:disabled {
                background-color: #9e9e9e;
            }
        """)
        self.btn_smart_scan.clicked.connect(self.start_smart_scan)
        
        # تعطيل الزر إذا لم يكن هناك مفتاح API
        if not self.scan_service.is_available():
            self.btn_smart_scan.setEnabled(False)
            self.btn_smart_scan.setToolTip("مفتاح Gemini API غير موجود")

        top_bar.addWidget(title)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_smart_scan)
        layout.addLayout(top_bar)

        # --- حقول البيانات الأساسية ---
        form_layout = QVBoxLayout()

        # اسم العميل / المورد
        self.lbl_client = QLabel("اسم العميل / المورد:")
        self.txt_client = QLineEdit()
        self.txt_client.setPlaceholderText("سيتم تعبئته تلقائياً...")
        self.txt_client.setStyleSheet("padding: 8px; font-size: 14px;")

        # التاريخ
        self.lbl_date = QLabel("تاريخ الفاتورة:")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setStyleSheet("padding: 8px; font-size: 14px;")

        # العملة والمبلغ
        self.lbl_total = QLabel("الإجمالي النهائي:")
        self.spin_total = QDoubleSpinBox()
        self.spin_total.setMaximum(10_000_000.0)
        self.spin_total.setDecimals(2)
        self.spin_total.setPrefix("ج.م ")
        self.spin_total.setStyleSheet("padding: 8px; font-size: 14px;")

        # الضريبة
        self.lbl_tax = QLabel("الضريبة:")
        self.spin_tax = QDoubleSpinBox()
        self.spin_tax.setMaximum(1_000_000.0)
        self.spin_tax.setDecimals(2)
        self.spin_tax.setPrefix("ج.م ")
        self.spin_tax.setStyleSheet("padding: 8px; font-size: 14px;")

        form_layout.addWidget(self.lbl_client)
        form_layout.addWidget(self.txt_client)
        form_layout.addWidget(self.lbl_date)
        form_layout.addWidget(self.date_edit)
        form_layout.addWidget(self.lbl_tax)
        form_layout.addWidget(self.spin_tax)
        form_layout.addWidget(self.lbl_total)
        form_layout.addWidget(self.spin_total)
        layout.addLayout(form_layout)

        # --- جدول الأصناف ---
        layout.addWidget(QLabel("بنود الفاتورة:"))
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(4)
        self.items_table.setHorizontalHeaderLabels(["الصنف / الخدمة", "الكمية", "السعر", "الإجمالي"])
        
        header = self.items_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        self.items_table.setStyleSheet("""
            QTableWidget {
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #6200ea;
                color: white;
                padding: 8px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.items_table)

        # --- أزرار الإجراءات ---
        buttons_layout = QHBoxLayout()
        
        btn_add_row = QPushButton("➕ إضافة بند")
        btn_add_row.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)
        btn_add_row.clicked.connect(self.add_empty_row)
        
        btn_clear = QPushButton("🗑️ مسح الكل")
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #ef5350;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
        """)
        btn_clear.clicked.connect(self.clear_form)
        
        btn_save = QPushButton("💾 حفظ الفاتورة")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                padding: 10px 30px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
        """)
        
        buttons_layout.addWidget(btn_add_row)
        buttons_layout.addWidget(btn_clear)
        buttons_layout.addStretch()
        buttons_layout.addWidget(btn_save)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    # ---------------------------------------------------------
    # 🧠 Logic: منطق الربط
    # ---------------------------------------------------------

    def start_smart_scan(self):
        """1. فتح نافذة اختيار الملف"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "اختر صورة الفاتورة",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
        )
        if file_path:
            self.run_ai_processing(file_path)

    def run_ai_processing(self, image_path: str):
        """2. تشغيل الـ Thread"""
        # إظهار رسالة تحميل
        self.progress = QProgressDialog(
            "جاري تحليل الفاتورة بواسطة Gemini AI...",
            "إلغاء",
            0, 0,
            self
        )
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setWindowTitle("المسح الذكي")
        self.progress.show()

        # إعداد وتشغيل العامل
        self.worker = ScanWorker(self.scan_service, image_path)
        self.worker.finished.connect(self.on_scan_success)
        self.worker.error.connect(self.on_scan_error)
        self.worker.start()

    def on_scan_success(self, data: dict):
        """3. استقبال البيانات وتعبئة الحقول"""
        if self.progress:
            self.progress.close()

        # التحقق من وجود خطأ في الرد
        if "error" in data:
            QMessageBox.warning(
                self,
                "تحذير",
                f"لم نتمكن من تحليل الفاتورة بشكل كامل:\n{data.get('raw_text', '')[:200]}"
            )
            return

        # تعبئة الحقول الأساسية
        if data.get("merchant_name"):
            self.txt_client.setText(data["merchant_name"])
            self.txt_client.setStyleSheet(
                "border: 2px solid #6200ea; padding: 8px; font-size: 14px;"
            )

        if data.get("total_amount"):
            self.spin_total.setValue(float(data["total_amount"]))

        if data.get("tax_amount"):
            self.spin_tax.setValue(float(data["tax_amount"]))

        if data.get("invoice_date"):
            try:
                y, m, d = map(int, data["invoice_date"].split('-'))
                self.date_edit.setDate(QDate(y, m, d))
            except (ValueError, AttributeError):
                pass

        # تعبئة الجدول
        items = data.get("items", [])
        if items:
            self.items_table.setRowCount(len(items))
            for row, item in enumerate(items):
                name = str(item.get("name", ""))
                qty = float(item.get("qty", 1) or 1)
                price = float(item.get("price", 0) or 0)
                total = qty * price

                self.items_table.setItem(row, 0, QTableWidgetItem(name))
                self.items_table.setItem(row, 1, QTableWidgetItem(f"{qty:.2f}"))
                self.items_table.setItem(row, 2, QTableWidgetItem(f"{price:.2f}"))
                self.items_table.setItem(row, 3, QTableWidgetItem(f"{total:.2f}"))

        QMessageBox.information(
            self,
            "✅ تم بنجاح",
            f"تم استخراج البيانات بنجاح!\n"
            f"• التاجر: {data.get('merchant_name', 'غير معروف')}\n"
            f"• المبلغ: {data.get('total_amount', 0)} {data.get('currency', 'EGP')}\n"
            f"• عدد البنود: {len(items)}\n\n"
            f"يرجى المراجعة قبل الحفظ."
        )

    def on_scan_error(self, error_msg: str):
        """4. معالجة الأخطاء"""
        if self.progress:
            self.progress.close()
        QMessageBox.warning(
            self,
            "❌ خطأ في المسح",
            f"فشل تحليل الفاتورة:\n{error_msg}"
        )

    def add_empty_row(self):
        """إضافة صف فارغ للجدول"""
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        self.items_table.setItem(row, 0, QTableWidgetItem(""))
        self.items_table.setItem(row, 1, QTableWidgetItem("1"))
        self.items_table.setItem(row, 2, QTableWidgetItem("0"))
        self.items_table.setItem(row, 3, QTableWidgetItem("0"))

    def clear_form(self):
        """مسح جميع الحقول"""
        reply = QMessageBox.question(
            self,
            "تأكيد",
            "هل تريد مسح جميع البيانات؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.txt_client.clear()
            self.txt_client.setStyleSheet("padding: 8px; font-size: 14px;")
            self.date_edit.setDate(QDate.currentDate())
            self.spin_total.setValue(0)
            self.spin_tax.setValue(0)
            self.items_table.setRowCount(0)


# --- التشغيل المستقل ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # تطبيق ستايل داكن
    app.setStyleSheet("""
        QWidget {
            background-color: #1e1e1e;
            color: #ffffff;
            font-family: 'Segoe UI', 'Cairo', sans-serif;
        }
        QLineEdit, QDoubleSpinBox, QDateEdit {
            background-color: #2d2d2d;
            border: 1px solid #404040;
            border-radius: 4px;
            color: white;
        }
        QTableWidget {
            background-color: #2d2d2d;
            gridline-color: #404040;
        }
        QLabel {
            color: #e0e0e0;
        }
    """)
    
    window = SmartInvoiceForm()
    window.show()
    sys.exit(app.exec())
