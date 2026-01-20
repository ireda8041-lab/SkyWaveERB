# الملف: ui/client_editor_dialog.py
"""
نافذة إضافة/تعديل العملاء - تصميم متجاوب (Responsive)
"""

import os
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from core.custom_fields_manager import custom_fields
from services.client_service import ClientService
from ui.smart_combobox import SmartFilterComboBox

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass

# استيراد دوال الإشعارات
try:
    from ui.notification_system import notify_error, notify_success
except ImportError:
    def notify_success(msg, title=""):
        safe_print(f"INFO: {title} - {msg}")
    def notify_error(msg, title=""):
        safe_print(f"ERROR: {title} - {msg}")


class ClientEditorDialog(QDialog):
    """نافذة إضافة/تعديل عميل - تصميم متجاوب"""

    def __init__(self, client_service: ClientService, client_to_edit: schemas.Client | None = None, parent=None):
        super().__init__(parent)

        self.client_service = client_service
        self.client_to_edit = client_to_edit
        self.is_editing = client_to_edit is not None
        self._logo_deleted = False  # ⚡ flag لتتبع حذف الصورة

        if self.is_editing and client_to_edit is not None:
            self.setWindowTitle(f"تعديل العميل: {client_to_edit.name}")
        else:
            self.setWindowTitle("إضافة عميل جديد")

        # 📱 الديالوج على قد المحتوى بالضبط - بدون scroll
        self.setMinimumWidth(520)
        self.setMinimumHeight(680)  # ⚡ زيادة قليلة لإظهار كل المحتوى
        
        # ⚡ فتح الديالوج بحجم ثابت مناسب للمحتوى
        self.resize(520, 680)  # حجم ثابت مناسب
        
        # وضع الديالوج في منتصف الشاشة
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            x = (screen_geo.width() - 520) // 2
            y = (screen_geo.height() - 680) // 2
            self.move(x, y)
        
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        self.init_ui()

    def init_ui(self):
        from ui.styles import BUTTON_STYLES, COLORS, get_arrow_url

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
                background-color: {COLORS['bg_dark']};
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['bg_medium']};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['primary']};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 14, 14, 14)

        # ستايل الحقول مع أسهم واضحة (RTL)
        field_style = f"""
            QLineEdit {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px;
                font-size: 11px;
                min-height: 16px;
            }}
            QLineEdit:hover {{
                border-color: {COLORS['primary']};
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['primary']};
            }}
            QComboBox {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px 7px 25px;
                font-size: 11px;
                min-height: 16px;
            }}
            QComboBox:hover {{
                border-color: {COLORS['primary']};
            }}
            QComboBox:focus {{
                border: 1px solid {COLORS['primary']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 22px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({get_arrow_url("down")});
                width: 10px;
                height: 10px;
            }}
            QTextEdit {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 6px;
                font-size: 11px;
            }}
        """

        label_style = f"color: {COLORS['text_secondary']}; font-size: 10px;"

        # === البيانات الأساسية ===
        # الاسم
        name_label = QLabel("الاسم بالكامل *")
        name_label.setStyleSheet(label_style)
        layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setStyleSheet(field_style)
        self.name_input.setPlaceholderText("اسم العميل...")
        layout.addWidget(self.name_input)

        # صف الشركة والنوع
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        company_cont = QVBoxLayout()
        company_cont.setSpacing(2)
        company_label = QLabel("الشركة")
        company_label.setStyleSheet(label_style)
        company_cont.addWidget(company_label)
        self.company_input = QLineEdit()
        self.company_input.setStyleSheet(field_style)
        self.company_input.setPlaceholderText("اختياري")
        company_cont.addWidget(self.company_input)
        row1.addLayout(company_cont, 2)

        type_cont = QVBoxLayout()
        type_cont.setSpacing(2)
        type_label = QLabel("النوع")
        type_label.setStyleSheet(label_style)
        type_cont.addWidget(type_label)
        self.client_type_combo = QComboBox()
        self.client_type_combo.setStyleSheet(field_style)
        self.client_type_combo.addItems(["فرد", "شركة"])
        type_cont.addWidget(self.client_type_combo)
        row1.addLayout(type_cont, 1)

        layout.addLayout(row1)

        # صف الهاتف والبريد
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        phone_cont = QVBoxLayout()
        phone_cont.setSpacing(2)
        phone_label = QLabel("📱 الهاتف")
        phone_label.setStyleSheet(label_style)
        phone_cont.addWidget(phone_label)
        self.phone_input = QLineEdit()
        self.phone_input.setStyleSheet(field_style)
        phone_cont.addWidget(self.phone_input)
        row2.addLayout(phone_cont, 1)

        email_cont = QVBoxLayout()
        email_cont.setSpacing(2)
        email_label = QLabel("📧 البريد")
        email_label.setStyleSheet(label_style)
        email_cont.addWidget(email_label)
        self.email_input = QLineEdit()
        self.email_input.setStyleSheet(field_style)
        email_cont.addWidget(self.email_input)
        row2.addLayout(email_cont, 1)

        layout.addLayout(row2)

        # صف العنوان والدولة
        row3 = QHBoxLayout()
        row3.setSpacing(8)

        address_cont = QVBoxLayout()
        address_cont.setSpacing(2)
        address_label = QLabel("📍 العنوان")
        address_label.setStyleSheet(label_style)
        address_cont.addWidget(address_label)
        self.address_input = QLineEdit()
        self.address_input.setStyleSheet(field_style)
        address_cont.addWidget(self.address_input)
        row3.addLayout(address_cont, 2)

        country_cont = QVBoxLayout()
        country_cont.setSpacing(2)
        country_label = QLabel("🌍 الدولة")
        country_label.setStyleSheet(label_style)
        country_cont.addWidget(country_label)
        self.country_input = QLineEdit()
        self.country_input.setStyleSheet(field_style)
        self.country_input.setPlaceholderText("EGY")
        country_cont.addWidget(self.country_input)
        row3.addLayout(country_cont, 1)

        layout.addLayout(row3)

        # صف مجال العمل والرقم الضريبي
        row4 = QHBoxLayout()
        row4.setSpacing(8)

        work_cont = QVBoxLayout()
        work_cont.setSpacing(2)
        work_label = QLabel("مجال العمل")
        work_label.setStyleSheet(label_style)
        work_cont.addWidget(work_label)

        # SmartFilterComboBox مع فلترة ذكية
        self.work_field_input = SmartFilterComboBox()
        self.work_field_input.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 7px 10px 7px 25px;
                font-size: 11px;
                min-height: 16px;
            }}
            QComboBox:hover {{
                border-color: {COLORS['primary']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 22px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({get_arrow_url("down")});
                width: 10px;
                height: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                selection-background-color: {COLORS['primary']};
                selection-color: white;
                padding: 4px;
            }}
        """)

        # تحميل مجالات العمل (الافتراضية + المخصصة)
        self.work_field_input.addItem("")  # خيار فارغ
        business_fields = custom_fields.get_all_business_fields()
        for field in business_fields:
            self.work_field_input.addItem(field)
        self.work_field_input.lineEdit().setPlaceholderText("اكتب للبحث أو أدخل مجال جديد...")

        work_cont.addWidget(self.work_field_input)
        row4.addLayout(work_cont, 1)

        vat_cont = QVBoxLayout()
        vat_cont.setSpacing(2)
        vat_label = QLabel("الرقم الضريبي")
        vat_label.setStyleSheet(label_style)
        vat_cont.addWidget(vat_label)
        self.vat_input = QLineEdit()
        self.vat_input.setStyleSheet(field_style)
        self.vat_input.setPlaceholderText("اختياري")
        vat_cont.addWidget(self.vat_input)
        row4.addLayout(vat_cont, 1)

        layout.addLayout(row4)

        # اللوجو
        logo_label = QLabel("🖼️ صورة/لوجو")
        logo_label.setStyleSheet(label_style)
        layout.addWidget(logo_label)

        logo_layout = QHBoxLayout()
        logo_layout.setSpacing(8)
        self.logo_path_label = QLabel("لم يتم اختيار صورة")
        self.logo_path_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
        self.logo_path_label.setWordWrap(True)
        self.logo_path_label.setMaximumHeight(40)  # ⚡ منع التمدد الزائد
        self.logo_path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        # زرار اختيار الصورة
        select_logo_btn = QPushButton("اختيار...")
        select_logo_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_medium']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
            }}
        """)
        select_logo_btn.clicked.connect(self.select_logo_file)

        # زرار حذف الصورة
        self.delete_logo_btn = QPushButton("🗑️ حذف")
        self.delete_logo_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        self.delete_logo_btn.clicked.connect(self.delete_logo)

        logo_layout.addWidget(self.logo_path_label, 1)
        logo_layout.addWidget(select_logo_btn)
        logo_layout.addWidget(self.delete_logo_btn)
        layout.addLayout(logo_layout)

        # الملاحظات
        notes_label = QLabel("📝 ملاحظات")
        notes_label.setStyleSheet(label_style)
        layout.addWidget(notes_label)

        self.notes_input = QTextEdit()
        self.notes_input.setStyleSheet(field_style)
        self.notes_input.setPlaceholderText("ملاحظات إضافية...")
        self.notes_input.setFixedHeight(50)
        layout.addWidget(self.notes_input)

        # الحالة
        self.status_checkbox = QCheckBox("العميل نشط")
        self.status_checkbox.setChecked(True)
        self.status_checkbox.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px;")
        layout.addWidget(self.status_checkbox)

        # ⚡ عميل VIP مميز
        self.vip_checkbox = QCheckBox("⭐ عميل مميز VIP")
        self.vip_checkbox.setChecked(False)
        self.vip_checkbox.setStyleSheet("""
            QCheckBox {
                color: #fbbf24;
                font-size: 12px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:checked {
                background-color: #fbbf24;
                border: 2px solid #f59e0b;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.vip_checkbox)

        layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        # منطقة الأزرار
        buttons_container = QWidget()
        buttons_container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_medium']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(14, 10, 14, 10)
        buttons_layout.setSpacing(8)

        buttons_layout.addStretch()

        self.save_button = QPushButton("💾 حفظ")
        self.save_button.setStyleSheet(BUTTON_STYLES["primary"])
        self.save_button.setFixedSize(90, 30)
        self.save_button.clicked.connect(self.save_client)
        buttons_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.cancel_button.setFixedSize(70, 30)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)

        main_layout.addWidget(buttons_container)

        if self.is_editing:
            self.load_client_data()
            self.save_button.setText("💾 حفظ")

    def select_logo_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "اختر صورة", "", "Image Files (*.png *.jpg *.jpeg)")
        if file_path:
            normalized = file_path.replace("/", "\\")
            self.logo_path_label.setText(normalized)
            self.logo_path_label.setStyleSheet("font-style: normal; color: #111827;")
            self._logo_deleted = False  # ⚡ إعادة تعيين flag الحذف عند اختيار صورة جديدة

    def delete_logo(self):
        """حذف صورة العميل"""
        from ui.styles import COLORS

        # إعادة تعيين الـ label
        self.logo_path_label.setText("لم يتم اختيار صورة")
        self.logo_path_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; font-style: italic;")

        # ⚡ تعيين flag للحذف الصريح
        self._logo_deleted = True

        # مسح بيانات الصورة من العميل الحالي (لو موجود)
        if self.is_editing and self.client_to_edit:
            self.client_to_edit.logo_data = None
            self.client_to_edit.logo_path = None

        safe_print("INFO: 🗑️ تم تحديد صورة العميل للحذف")

    def load_client_data(self):
        """يملأ الحقول ببيانات العميل القديمة"""
        self.name_input.setText(self.client_to_edit.name)
        self.company_input.setText(self.client_to_edit.company_name or "")
        self.email_input.setText(self.client_to_edit.email or "")
        self.phone_input.setText(self.client_to_edit.phone or "")
        self.address_input.setText(self.client_to_edit.address or "")
        self.country_input.setText(self.client_to_edit.country or "")
        self.vat_input.setText(self.client_to_edit.vat_number or "")
        self.client_type_combo.setCurrentText(self.client_to_edit.client_type or "فرد")
        # تعيين مجال العمل في ComboBox
        work_field = self.client_to_edit.work_field or ""
        index = self.work_field_input.findText(work_field)
        if index >= 0:
            self.work_field_input.setCurrentIndex(index)
        else:
            self.work_field_input.setCurrentText(work_field)

        has_logo_data = hasattr(self.client_to_edit, 'logo_data') and self.client_to_edit.logo_data
        logo_path = self.client_to_edit.logo_path or ""

        if has_logo_data:
            self.logo_path_label.setText("✅ صورة محفوظة في قاعدة البيانات")
            self.logo_path_label.setStyleSheet("font-style: normal; color: #10B981; font-weight: bold;")
        elif logo_path:
            self.logo_path_label.setText(logo_path)
            self.logo_path_label.setStyleSheet("font-style: normal; color: #111827;")
        else:
            self.logo_path_label.setText("لم يتم اختيار صورة")
            self.logo_path_label.setStyleSheet("font-style: italic; color: #888;")

        self.notes_input.setText(self.client_to_edit.client_notes or "")
        self.status_checkbox.setChecked(self.client_to_edit.status == schemas.ClientStatus.ACTIVE)

        # ⚡ تحميل حالة VIP
        is_vip = getattr(self.client_to_edit, 'is_vip', False)
        self.vip_checkbox.setChecked(bool(is_vip))

    def _convert_image_to_base64(self, image_path: str) -> str:
        """تحويل صورة إلى base64 للحفظ في قاعدة البيانات - محسّن للأداء والجودة"""
        import base64

        if not image_path or not os.path.exists(image_path):
            return ""

        try:
            from PyQt6.QtCore import QBuffer, QIODevice
            from PyQt6.QtGui import QPixmap

            # تحميل الصورة الأصلية
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                safe_print(f"ERROR: فشل تحميل الصورة: {image_path}")
                return ""

            original_size = f"{pixmap.width()}x{pixmap.height()}"
            safe_print(f"INFO: 📷 تحميل صورة {original_size}")

            # ⚡ تصغير ذكي حسب الحجم
            max_size = 400  # حجم أصغر للأداء الأفضل
            if pixmap.width() > max_size or pixmap.height() > max_size:
                pixmap = pixmap.scaled(
                    max_size, max_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                safe_print(f"INFO: 📷 تم تصغير الصورة إلى {pixmap.width()}x{pixmap.height()}")

            # ⚡ ضغط ذكي - JPEG للصور الكبيرة، PNG للصور الصغيرة
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)

            # تجربة JPEG أولاً (أصغر حجماً)
            pixmap.save(buffer, "JPEG", 85)  # جودة 85% - توازن جيد
            jpeg_size = buffer.size()

            # إعادة تعيين البافر
            buffer.close()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)

            # تجربة PNG
            pixmap.save(buffer, "PNG", 100)
            png_size = buffer.size()

            # اختيار الأصغر حجماً
            if jpeg_size < png_size * 0.7:  # JPEG أصغر بـ 30% على الأقل
                buffer.close()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                pixmap.save(buffer, "JPEG", 85)
                format_used = "JPEG"
            else:
                format_used = "PNG"

            img_data = buffer.data().data()
            buffer.close()

            # التحقق من الحجم النهائي
            size_kb = len(img_data) / 1024
            safe_print(f"INFO: 📷 حجم الصورة النهائي: {size_kb:.1f} KB ({format_used})")

            # تحذير إذا كانت الصورة كبيرة جداً
            if size_kb > 500:
                safe_print(f"WARNING: 📷 الصورة كبيرة ({size_kb:.1f} KB) - قد تؤثر على الأداء")

            base64_str = base64.b64encode(img_data).decode('utf-8')
            return f"data:image/{format_used.lower()};base64,{base64_str}"

        except Exception as e:
            safe_print(f"ERROR: فشل تحويل الصورة إلى base64: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def get_form_data(self) -> dict[str, Any]:
        """يجمع البيانات من الحقول"""
        status = schemas.ClientStatus.ACTIVE if self.status_checkbox.isChecked() else schemas.ClientStatus.ARCHIVED
        logo_text = self.logo_path_label.text()

        logo_value = ""
        logo_data = None  # None = لم يتم تحديد (سيتم الاحتفاظ بالقديم)

        # ⚡ التحقق من حالة الصورة باستخدام flag الحذف
        if self._logo_deleted:
            # تم حذف الصورة صراحة بالضغط على زر الحذف
            logo_value = ""
            logo_data = "__DELETE__"  # علامة خاصة للحذف
            safe_print("INFO: 🗑️ سيتم حذف صورة العميل (flag)")
        elif "محفوظة في قاعدة البيانات" in logo_text:
            # الاحتفاظ بالصورة القديمة (لا نرسل logo_data)
            logo_data = None  # None = الاحتفاظ بالقديم
            safe_print("INFO: 📷 الاحتفاظ بالصورة القديمة")
        elif "لم يتم" in logo_text:
            # لم يتم اختيار صورة (عميل جديد بدون صورة)
            logo_value = ""
            logo_data = ""
            safe_print("INFO: ℹ️ عميل بدون صورة")
        else:
            # صورة جديدة من مسار محلي
            logo_value = logo_text
            if logo_value and os.path.exists(logo_value):
                logo_data = self._convert_image_to_base64(logo_value)
                safe_print(f"INFO: 📷 تم تحويل الصورة إلى base64 ({len(logo_data)} حرف)")

        result = {
            "name": self.name_input.text(),
            "company_name": self.company_input.text(),
            "email": self.email_input.text(),
            "phone": self.phone_input.text(),
            "address": self.address_input.text(),
            "country": self.country_input.text(),
            "vat_number": self.vat_input.text(),
            "status": status,
            "client_type": self.client_type_combo.currentText(),
            "work_field": self.work_field_input.currentText(),
            "logo_path": logo_value,
            "client_notes": self.notes_input.toPlainText(),
            "is_vip": self.vip_checkbox.isChecked(),  # ⚡ حالة VIP
        }

        # إضافة logo_data فقط إذا تم تحديده
        if logo_data is not None:
            result["logo_data"] = logo_data

        return result

    def save_client(self):
        """يحفظ (أو يعدل) العميل عبر الخدمة"""
        client_data = self.get_form_data()

        # ⚡ تسجيل بيانات الصورة
        safe_print(f"DEBUG: [save_client] logo_path = {client_data.get('logo_path', '')}")
        safe_print(f"DEBUG: [save_client] logo_data length = {len(client_data.get('logo_data', ''))}")

        if not client_data["name"]:
            QMessageBox.warning(self, "خطأ", "اسم العميل مطلوب")
            return

        try:
            # حفظ مجال العمل الجديد إذا لم يكن موجوداً
            work_field = client_data.get("work_field", "")
            if work_field and work_field.strip():
                custom_fields.add_value("business_fields", work_field)

            if self.is_editing:
                client_id = self.client_to_edit._mongo_id or str(self.client_to_edit.id)
                safe_print(f"DEBUG: [save_client] تعديل العميل {client_id} مع logo_data ({len(client_data.get('logo_data', ''))} حرف)")
                self.client_service.update_client(client_id, client_data)

                # 🔔 إشعار محسّن للتحديث
                if client_data.get('logo_data') and client_data['logo_data'] != "__DELETE__":
                    notify_success(
                        f"تم تحديث العميل '{client_data['name']}' مع اللوجو 🖼️",
                        "✅ تحديث عميل"
                    )
                elif client_data.get('logo_data') == "__DELETE__":
                    notify_success(
                        f"تم تحديث العميل '{client_data['name']}' وحذف اللوجو 🗑️",
                        "✅ تحديث عميل"
                    )
                else:
                    notify_success(
                        f"تم تحديث العميل '{client_data['name']}'",
                        "✅ تحديث عميل"
                    )

                QMessageBox.information(self, "تم", f"تم حفظ تعديلات العميل '{client_data['name']}' بنجاح.")
            else:
                safe_print(f"DEBUG: [save_client] إضافة عميل جديد مع logo_data ({len(client_data.get('logo_data', ''))} حرف)")
                new_client_schema = schemas.Client(**client_data)
                self.client_service.create_client(new_client_schema)

                # 🔔 إشعار محسّن للإضافة
                if client_data.get('logo_data') and client_data['logo_data']:
                    notify_success(
                        f"تم إضافة العميل '{client_data['name']}' مع اللوجو 🖼️",
                        "✅ عميل جديد"
                    )
                else:
                    notify_success(
                        f"تم إضافة العميل '{client_data['name']}'",
                        "✅ عميل جديد"
                    )

                QMessageBox.information(self, "تم", f"تم إضافة العميل '{client_data['name']}' بنجاح.")

            self.accept()

        except Exception as e:
            safe_print(f"ERROR: [ClientEditorDialog] فشل حفظ العميل: {e}")
            notify_error(f"فشل حفظ العميل: {str(e)}", "❌ خطأ")
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")
