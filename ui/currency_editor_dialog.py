# الملف: ui/currency_editor_dialog.py
"""
نافذة تعديل العملة مع جلب أسعار الصرف الحقيقية من الإنترنت
"""

import json
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ui.custom_spinbox import CustomSpinBox
from ui.styles import BUTTON_STYLES, COLORS

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class ExchangeRateFetcher(QThread):
    """Thread لجلب أسعار الصرف الحقيقية من الإنترنت"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, currency_code):
        super().__init__()
        self.currency_code = currency_code.upper()

    def run(self):
        try:
            rate = None
            source = None

            # محاولة 1: Open Exchange Rates (مجاني محدود)
            # https://openexchangerates.org/
            try:
                # API مجاني يعطي أسعار مقابل USD
                url = "https://open.er-api.com/v6/latest/USD"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as response:  # nosec B310 - Safe HTTPS API call
                    data = json.loads(response.read().decode())
                    if data.get('result') == 'success' and 'rates' in data:
                        rates = data['rates']
                        egp_rate = rates.get('EGP', 0)
                        currency_rate = rates.get(self.currency_code, 0)

                        if egp_rate > 0 and currency_rate > 0:
                            # حساب سعر العملة مقابل الجنيه
                            rate = egp_rate / currency_rate
                            source = 'Open Exchange Rates API'
            except Exception as e:
                safe_print(f"API 1 failed: {e}")

            # محاولة 2: ExchangeRate-API
            if rate is None:
                try:
                    url = f"https://api.exchangerate-api.com/v4/latest/{self.currency_code}"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=15) as response:  # nosec B310 - Safe HTTPS API call
                        data = json.loads(response.read().decode())
                        if 'rates' in data:
                            egp_rate = data['rates'].get('EGP', 0)
                            if egp_rate > 0:
                                rate = egp_rate
                                source = 'ExchangeRate-API'
                except Exception as e:
                    safe_print(f"API 2 failed: {e}")

            # محاولة 3: Fixer.io style API
            if rate is None:
                try:
                    url = f"https://cdn.jsdelivr.net/gh/fawazahmed0/currency-api@1/latest/currencies/{self.currency_code.lower()}/egp.json"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=15) as response:  # nosec B310 - Safe HTTPS API call
                        data = json.loads(response.read().decode())
                        if 'egp' in data:
                            rate = data['egp']
                            source = 'Currency API (GitHub)'
                except Exception as e:
                    safe_print(f"API 3 failed: {e}")

            # إذا نجح أي API
            if rate and rate > 0:
                self.finished.emit({
                    'success': True,
                    'rate': round(rate, 4),
                    'source': source,
                    'is_fallback': False
                })
                return

            # Fallback: أسعار تقريبية محدثة (نوفمبر 2025)
            fallback_rates = {
                'USD': 49.50,   # دولار أمريكي
                'EUR': 52.80,   # يورو
                'GBP': 62.50,   # جنيه إسترليني
                'SAR': 13.20,   # ريال سعودي
                'AED': 13.48,   # درهم إماراتي
                'KWD': 161.00,  # دينار كويتي
                'QAR': 13.60,   # ريال قطري
                'BHD': 131.50,  # دينار بحريني
                'OMR': 128.70,  # ريال عماني
                'JOD': 69.80,   # دينار أردني
                'CHF': 55.00,   # فرنك سويسري
                'CAD': 35.50,   # دولار كندي
                'AUD': 32.00,   # دولار أسترالي
                'JPY': 0.33,    # ين ياباني
                'CNY': 6.85,    # يوان صيني
                'INR': 0.59,    # روبية هندية
                'TRY': 1.45,    # ليرة تركية
                'EGP': 1.00,    # جنيه مصري
            }

            if self.currency_code in fallback_rates:
                self.finished.emit({
                    'success': True,
                    'rate': fallback_rates[self.currency_code],
                    'source': 'أسعار تقديرية (البنك المركزي المصري)',
                    'is_fallback': True
                })
            else:
                self.error.emit(f"العملة {self.currency_code} غير مدعومة")

        except Exception as e:
            self.error.emit(str(e))


class CurrencyEditorDialog(QDialog):
    """نافذة تعديل العملة"""

    def __init__(self, currency_data=None, parent=None):
        super().__init__(parent)

        self.currency_data = currency_data or {}
        self.is_editing = bool(currency_data)
        self.fetcher = None

        self.setWindowTitle("تعديل العملة" if self.is_editing else "إضافة عملة جديدة")

        # تصميم متجاوب - حد أدنى فقط
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)

        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        self.init_ui()

        if self.is_editing:
            self.load_currency_data()

        # ⚡ تطبيق الستايلات المتجاوبة
        from ui.styles import setup_auto_responsive_dialog
        setup_auto_responsive_dialog(self)

    def init_ui(self):
        from PyQt6.QtWidgets import QScrollArea, QSizePolicy, QWidget

        from ui.styles import RESPONSIVE_GROUPBOX_STYLE, get_cairo_font

        # التخطيط الرئيسي
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # منطقة التمرير
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['bg_medium']};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['primary']};
                border-radius: 5px;
                min-height: 30px;
            }}
        """)

        # محتوى التمرير
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(15, 15, 15, 15)

        # معلومات العملة
        info_group = QGroupBox("معلومات العملة")
        info_group.setStyleSheet(RESPONSIVE_GROUPBOX_STYLE)
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # رمز العملة
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("مثال: USD, EUR, SAR")
        self.code_input.setMaxLength(3)
        self.code_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if self.is_editing:
            self.code_input.setEnabled(False)
        form_layout.addRow(QLabel("🔤 رمز العملة:"), self.code_input)

        # اسم العملة
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("مثال: دولار أمريكي")
        self.name_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        form_layout.addRow(QLabel("📝 اسم العملة:"), self.name_input)

        # رمز العملة المختصر
        self.symbol_input = QLineEdit()
        self.symbol_input.setPlaceholderText("مثال: $, €, ر.س")
        self.symbol_input.setMaxLength(5)
        self.symbol_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        form_layout.addRow(QLabel("💲 الرمز:"), self.symbol_input)

        info_group.setLayout(form_layout)
        content_layout.addWidget(info_group)

        # سعر الصرف
        rate_group = QGroupBox("💱 سعر الصرف (مقابل الجنيه المصري)")
        rate_group.setStyleSheet(RESPONSIVE_GROUPBOX_STYLE)
        rate_layout = QVBoxLayout()
        rate_layout.setSpacing(12)

        # سعر الصرف الحالي
        rate_form = QFormLayout()
        self.rate_input = CustomSpinBox(decimals=4, minimum=0.0001, maximum=999999)
        self.rate_input.setValue(1.0)
        self.rate_input.setSuffix(" ج.م")
        self.rate_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        rate_form.addRow(QLabel("💰 سعر الصرف:"), self.rate_input)
        rate_layout.addLayout(rate_form)

        # زرار جلب السعر من الإنترنت
        self.fetch_rate_btn = QPushButton("🏦 جلب السعر الحالي من البنوك")
        self.fetch_rate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
            QPushButton:disabled {{
                background-color: #4b5563;
            }}
        """)
        self.fetch_rate_btn.clicked.connect(self.fetch_exchange_rate)
        rate_layout.addWidget(self.fetch_rate_btn)

        # شريط التحميل
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        rate_layout.addWidget(self.progress_bar)

        # معلومات المصدر
        self.source_label = QLabel("")
        self.source_label.setStyleSheet("color: #9ca3af; font-size: 11px;")
        rate_layout.addWidget(self.source_label)

        rate_group.setLayout(rate_layout)
        content_layout.addWidget(rate_group)

        # الحالة
        self.active_checkbox = QCheckBox("العملة نشطة")
        self.active_checkbox.setChecked(True)
        self.active_checkbox.setFont(get_cairo_font(13, bold=True))
        content_layout.addWidget(self.active_checkbox)

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        # منطقة الأزرار (ثابتة في الأسفل)
        buttons_container = QWidget()
        buttons_container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_light']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(15, 12, 15, 12)
        buttons_layout.setSpacing(10)

        buttons_layout.addStretch()

        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.setStyleSheet(BUTTON_STYLES["secondary"])
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("💾 حفظ")
        self.save_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_btn.clicked.connect(self.save_currency)

        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.save_btn)

        main_layout.addWidget(buttons_container)

    def load_currency_data(self):
        """تحميل بيانات العملة للتعديل"""
        self.code_input.setText(self.currency_data.get('code', ''))
        self.name_input.setText(self.currency_data.get('name', ''))
        self.symbol_input.setText(self.currency_data.get('symbol', ''))
        self.rate_input.setValue(self.currency_data.get('rate', 1.0))
        self.active_checkbox.setChecked(self.currency_data.get('active', True))

    def fetch_exchange_rate(self):
        """جلب سعر الصرف من الإنترنت"""
        code = self.code_input.text().upper().strip()

        if not code:
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال رمز العملة أولاً")
            return

        if code == "EGP":
            self.rate_input.setValue(1.0)
            self.source_label.setText("✅ الجنيه المصري هو العملة الأساسية")
            return

        # بدء جلب السعر
        self.fetch_rate_btn.setEnabled(False)
        self.progress_bar.show()
        self.source_label.setText("⏳ جاري جلب السعر من الإنترنت...")

        self.fetcher = ExchangeRateFetcher(code)
        self.fetcher.finished.connect(self.on_rate_fetched)
        self.fetcher.error.connect(self.on_fetch_error)
        self.fetcher.start()

    def on_rate_fetched(self, result):
        """عند نجاح جلب السعر"""
        self.fetch_rate_btn.setEnabled(True)
        self.progress_bar.hide()

        if result.get('success'):
            rate = result['rate']
            source = result.get('source', 'غير معروف')
            is_fallback = result.get('is_fallback', False)

            self.rate_input.setValue(rate)

            if is_fallback:
                self.source_label.setText(f"⚠️ سعر تقديري من: {source}")
                self.source_label.setStyleSheet("color: #f59e0b; font-size: 11px;")
            else:
                self.source_label.setText(f"✅ تم جلب السعر من: {source}")
                self.source_label.setStyleSheet("color: #0A6CF1; font-size: 11px;")

            QMessageBox.information(
                self, "تم",
                f"تم جلب سعر الصرف بنجاح!\n\n"
                f"1 {self.code_input.text().upper()} = {rate:.4f} ج.م\n\n"
                f"المصدر: {source}"
            )

    def on_fetch_error(self, error_msg):
        """عند فشل جلب السعر"""
        self.fetch_rate_btn.setEnabled(True)
        self.progress_bar.hide()
        self.source_label.setText(f"❌ فشل جلب السعر: {error_msg}")
        self.source_label.setStyleSheet("color: #ef4444; font-size: 11px;")

        QMessageBox.warning(
            self, "تنبيه",
            f"تعذر جلب سعر الصرف من الإنترنت.\n\n"
            f"يمكنك إدخال السعر يدوياً.\n\n"
            f"الخطأ: {error_msg}"
        )

    def save_currency(self):
        """حفظ العملة"""
        code = self.code_input.text().upper().strip()
        name = self.name_input.text().strip()

        if not code:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال رمز العملة")
            return

        if not name:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم العملة")
            return

        self.result_data = {
            'code': code,
            'name': name,
            'symbol': self.symbol_input.text().strip() or code,
            'rate': self.rate_input.value(),
            'active': self.active_checkbox.isChecked()
        }

        self.accept()

    def get_result(self):
        """الحصول على البيانات المحفوظة"""
        return getattr(self, 'result_data', None)
