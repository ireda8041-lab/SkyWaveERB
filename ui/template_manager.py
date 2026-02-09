# الملف: ui/template_manager.py
"""
مدير قوالب الفواتير - واجهة إدارة القوالب
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.template_service import TemplateService
from ui.invoice_preview_dialog import InvoicePreviewDialog
from ui.styles import BUTTON_STYLES, TABLE_STYLE_DARK, create_centered_item, get_cairo_font


class TemplateEditorDialog(QDialog):
    """نافذة تحرير القوالب"""

    def __init__(self, template_service: TemplateService, template_data=None, parent=None):
        super().__init__(parent)
        self.template_service = template_service
        self.template_data = template_data
        self.setup_ui()

        if template_data:
            self.load_template_data()

        # ⚡ تطبيق الستايلات المتجاوبة
        from ui.styles import setup_auto_responsive_dialog

        setup_auto_responsive_dialog(self)

    def setup_ui(self):
        """إعداد واجهة المستخدم"""
        self.setWindowTitle("تحرير قالب الفاتورة")
        self.setModal(True)
        self.resize(800, 600)
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        # 📱 سياسة التمدد
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # تطبيق شريط العنوان المخصص
        try:
            from ui.styles import setup_custom_title_bar

            setup_custom_title_bar(self)
        except (ImportError, AttributeError):
            pass

        layout = QVBoxLayout(self)

        # معلومات القالب
        info_group = QGroupBox("معلومات القالب")
        info_layout = QFormLayout(info_group)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("اسم القالب")
        info_layout.addRow("الاسم:", self.name_input)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("وصف القالب")
        info_layout.addRow("الوصف:", self.description_input)

        layout.addWidget(info_group)

        # محرر HTML
        editor_group = QGroupBox("محتوى القالب (HTML)")
        editor_layout = QVBoxLayout(editor_group)

        self.html_editor = QTextEdit()
        self.html_editor.setFont(get_cairo_font(10))
        self.html_editor.setPlaceholderText("أدخل كود HTML للقالب...")
        editor_layout.addWidget(self.html_editor)

        # أزرار المساعدة
        help_layout = QHBoxLayout()

        variables_btn = QPushButton("📋 المتغيرات المتاحة")
        variables_btn.clicked.connect(self.show_available_variables)
        help_layout.addWidget(variables_btn)

        sample_btn = QPushButton("📄 قالب نموذجي")
        sample_btn.clicked.connect(self.load_sample_template)
        help_layout.addWidget(sample_btn)

        help_layout.addStretch()
        editor_layout.addLayout(help_layout)

        layout.addWidget(editor_group)

        # أزرار الحفظ والإلغاء
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save_template)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # تطبيق الأنماط
        self.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Cairo';
            }
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                background-color: #007acc;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """
        )

    def load_template_data(self):
        """تحميل بيانات القالب للتحرير"""
        if self.template_data:
            self.name_input.setText(self.template_data.get("name", ""))
            self.description_input.setText(self.template_data.get("description", ""))

            # تحميل محتوى الملف
            template_file = self.template_data.get("template_file", "")
            if template_file:
                try:
                    import os

                    template_path = os.path.join("templates", template_file)
                    if os.path.exists(template_path):
                        with open(template_path, encoding="utf-8") as f:
                            content = f.read()
                        self.html_editor.setPlainText(content)
                except Exception as e:
                    QMessageBox.warning(self, "خطأ", f"فشل في تحميل محتوى القالب: {e}")

    def show_available_variables(self):
        """عرض المتغيرات المتاحة"""
        variables_text = """
المتغيرات المتاحة في القوالب:

معلومات الفاتورة:
- {{ invoice_id }} - رقم الفاتورة
- {{ date }} - تاريخ الفاتورة

معلومات العميل:
- {{ client_name }} - اسم العميل
- {{ client_phone }} - هاتف العميل
- {{ client_email }} - بريد العميل
- {{ client_address }} - عنوان العميل

الخدمات (حلقة تكرار):
{% for item in items %}
- {{ item.name }} - اسم الخدمة
- {{ item.qty }} - الكمية
- {{ item.price }} - السعر
- {{ item.discount }} - الخصم
- {{ item.total }} - الإجمالي
{% endfor %}

الإجماليات:
- {{ subtotal }} - المجموع الفرعي
- {{ discount_amount }} - مبلغ الخصم
- {{ tax_amount }} - مبلغ الضريبة
- {{ grand_total }} - الإجمالي النهائي

مثال على الاستخدام:
<h1>فاتورة رقم {{ invoice_id }}</h1>
<p>العميل: {{ client_name }}</p>
<table>
{% for item in items %}
<tr>
    <td>{{ item.name }}</td>
    <td>{{ item.total }}</td>
</tr>
{% endfor %}
</table>
<p>الإجمالي: {{ grand_total }}</p>
        """

        QMessageBox.information(self, "المتغيرات المتاحة", variables_text)

    def load_sample_template(self):
        """تحميل قالب نموذجي"""
        sample_html = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>فاتورة - {{ invoice_id }}</title>
    <style>
        body { font-family: 'Cairo', sans-serif; direction: rtl; }
        .header { background: #007acc; color: white; padding: 20px; }
        .content { padding: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
        th { background: #f2f2f2; }
        .total { font-weight: bold; font-size: 1.2em; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Sky Wave</h1>
        <p>فاتورة رقم: {{ invoice_id }}</p>
        <p>التاريخ: {{ date }}</p>
    </div>

    <div class="content">
        <h2>معلومات العميل</h2>
        <p><strong>الاسم:</strong> {{ client_name }}</p>
        <p><strong>الهاتف:</strong> {{ client_phone }}</p>

        <h2>الخدمات</h2>
        <table>
            <thead>
                <tr>
                    <th>الخدمة</th>
                    <th>الكمية</th>
                    <th>السعر</th>
                    <th>الإجمالي</th>
                </tr>
            </thead>
            <tbody>
                {% for item in items %}
                <tr>
                    <td>{{ item.name }}</td>
                    <td>{{ item.qty }}</td>
                    <td>{{ item.price }}</td>
                    <td>{{ item.total }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div class="total">
            <p>الإجمالي النهائي: {{ grand_total }} ج.م</p>
        </div>
    </div>
</body>
</html>"""

        self.html_editor.setPlainText(sample_html)

    def save_template(self):
        """حفظ القالب"""
        name = self.name_input.text().strip()
        description = self.description_input.text().strip()
        content = self.html_editor.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم القالب")
            return

        if not content:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال محتوى القالب")
            return

        try:
            if self.template_data:
                # تحديث قالب موجود
                template_id = self.template_data["id"]
                success = self.template_service.update_template(
                    template_id, name, description, content
                )
                if success:
                    QMessageBox.information(self, "نجح", "تم تحديث القالب بنجاح")
                    self.accept()
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في تحديث القالب")
            else:
                # إضافة قالب جديد
                success = self.template_service.add_template(name, description, content)
                if success:
                    QMessageBox.information(self, "نجح", "تم حفظ القالب بنجاح")
                    self.accept()
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في حفظ القالب")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء حفظ القالب: {e}")


class TemplateManager(QWidget):
    """مدير قوالب الفواتير"""

    template_changed = pyqtSignal()

    def __init__(self, template_service: TemplateService, parent=None):
        super().__init__(parent)
        self.template_service = template_service
        self._current_page = 1
        self._page_size = 50
        self._templates: list[dict] = []

        # 📱 تصميم متجاوب
        from PyQt6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setup_ui()
        self.load_templates()

    def setup_ui(self):
        """إعداد واجهة المستخدم"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # عنوان القسم
        title_label = QLabel("إدارة قوالب الفواتير")
        title_label.setFont(get_cairo_font(14, bold=True))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # أزرار التحكم
        buttons_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ إضافة قالب جديد")
        self.add_btn.clicked.connect(self.add_template)
        buttons_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ تعديل القالب")
        self.edit_btn.clicked.connect(self.edit_template)
        self.edit_btn.setEnabled(False)
        buttons_layout.addWidget(self.edit_btn)

        self.preview_btn = QPushButton("👁️ معاينة")
        self.preview_btn.clicked.connect(self.preview_template)
        self.preview_btn.setEnabled(False)
        buttons_layout.addWidget(self.preview_btn)

        self.set_default_btn = QPushButton("⭐ تعيين كافتراضي")
        self.set_default_btn.clicked.connect(self.set_default_template)
        self.set_default_btn.setEnabled(False)
        buttons_layout.addWidget(self.set_default_btn)

        self.delete_btn = QPushButton("🗑️ حذف")
        self.delete_btn.clicked.connect(self.delete_template)
        self.delete_btn.setEnabled(False)
        buttons_layout.addWidget(self.delete_btn)

        buttons_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 تحديث")
        self.refresh_btn.clicked.connect(self.load_templates)
        buttons_layout.addWidget(self.refresh_btn)

        layout.addLayout(buttons_layout)

        # جدول القوالب
        self.templates_table = QTableWidget()
        self.templates_table.setColumnCount(5)
        self.templates_table.setHorizontalHeaderLabels(
            ["الاسم", "الوصف", "ملف القالب", "افتراضي", "تاريخ الإنشاء"]
        )

        # تعديل عرض الأعمدة
        header = self.templates_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.templates_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.templates_table.setAlternatingRowColors(True)
        self.templates_table.itemSelectionChanged.connect(self.on_selection_changed)

        layout.addWidget(self.templates_table)

        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 6, 0, 0)
        pagination_layout.setSpacing(8)

        self.prev_page_button = QPushButton("◀ السابق")
        self.prev_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.prev_page_button.setFixedHeight(26)
        self.prev_page_button.clicked.connect(self._go_prev_page)

        self.next_page_button = QPushButton("التالي ▶")
        self.next_page_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.next_page_button.setFixedHeight(26)
        self.next_page_button.clicked.connect(self._go_next_page)

        self.page_info_label = QLabel("صفحة 1 / 1")
        self.page_info_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["25", "50", "100", "كل"])
        self.page_size_combo.setCurrentText("50")
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)

        pagination_layout.addWidget(self.prev_page_button)
        pagination_layout.addWidget(self.next_page_button)
        pagination_layout.addStretch(1)
        pagination_layout.addWidget(QLabel("حجم الصفحة:"))
        pagination_layout.addWidget(self.page_size_combo)
        pagination_layout.addWidget(self.page_info_label)
        layout.addLayout(pagination_layout)

        # تطبيق الأنماط
        self.templates_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl

        fix_table_rtl(self.templates_table)

    def load_templates(self):
        """تحميل قائمة القوالب"""
        try:
            self._templates = self.template_service.get_all_templates()
            self._render_current_page()

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في تحميل القوالب: {e}")

    def _get_total_pages(self) -> int:
        total = len(self._templates)
        if total == 0:
            return 1
        if self._page_size <= 0:
            return 1
        return (total + self._page_size - 1) // self._page_size

    def _render_current_page(self):
        total_pages = self._get_total_pages()
        if self._current_page > total_pages:
            self._current_page = total_pages
        if self._current_page < 1:
            self._current_page = 1

        if not self._templates:
            self.templates_table.setRowCount(0)
            self._update_pagination_controls(total_pages)
            return

        if self._page_size <= 0:
            page_items = self._templates
        else:
            start_index = (self._current_page - 1) * self._page_size
            end_index = start_index + self._page_size
            page_items = self._templates[start_index:end_index]

        self._populate_templates_table(page_items)
        self._update_pagination_controls(total_pages)

    def _populate_templates_table(self, templates: list[dict]):
        self.templates_table.setRowCount(len(templates))
        for row, template in enumerate(templates):
            name_item = create_centered_item(template["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, template["id"])
            self.templates_table.setItem(row, 0, name_item)

            self.templates_table.setItem(
                row, 1, create_centered_item(template["description"] or "")
            )

            self.templates_table.setItem(row, 2, create_centered_item(template["template_file"]))

            self.templates_table.setItem(
                row, 3, create_centered_item("✓" if template["is_default"] else "")
            )

            self.templates_table.setItem(
                row,
                4,
                create_centered_item(template["created_at"][:10] if template["created_at"] else ""),
            )

    def _update_pagination_controls(self, total_pages: int):
        self.page_info_label.setText(f"صفحة {self._current_page} / {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

    def _on_page_size_changed(self, value: str):
        if value == "كل":
            self._page_size = max(1, len(self._templates))
        else:
            try:
                self._page_size = int(value)
            except Exception:
                self._page_size = 50
        self._current_page = 1
        self._render_current_page()

    def _go_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._render_current_page()

    def _go_next_page(self):
        if self._current_page < self._get_total_pages():
            self._current_page += 1
            self._render_current_page()

    def on_selection_changed(self):
        """عند تغيير التحديد"""
        # ⚡ تجاهل التحديث إذا كان الكليك يمين
        from core.context_menu import is_right_click_active

        if is_right_click_active():
            return

        selected_rows = self.templates_table.selectionModel().selectedRows()
        has_selection = len(selected_rows) > 0

        self.edit_btn.setEnabled(has_selection)
        self.preview_btn.setEnabled(has_selection)
        self.set_default_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def get_selected_template_id(self):
        """جلب معرف القالب المحدد"""
        selected_rows = self.templates_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            name_item = self.templates_table.item(row, 0)
            return name_item.data(Qt.ItemDataRole.UserRole)
        return None

    def add_template(self):
        """إضافة قالب جديد"""
        dialog = TemplateEditorDialog(self.template_service, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_templates()
            self.template_changed.emit()

    def edit_template(self):
        """تعديل القالب المحدد"""
        template_id = self.get_selected_template_id()
        if template_id:
            template_data = self.template_service.get_template_by_id(template_id)
            if template_data:
                dialog = TemplateEditorDialog(self.template_service, template_data, parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self.load_templates()
                    self.template_changed.emit()

    def preview_template(self):
        """معاينة القالب المحدد"""
        template_id = self.get_selected_template_id()
        if template_id:
            try:
                # إنشاء بيانات تجريبية للمعاينة

                # بيانات مشروع تجريبية
                sample_project = type(
                    "Project",
                    (),
                    {
                        "id": 1,
                        "items": [
                            type(
                                "Item",
                                (),
                                {
                                    "description": "تصميم موقع إلكتروني",
                                    "quantity": 1.0,
                                    "unit_price": 5000.0,
                                    "discount_rate": 10.0,
                                    "total": 4500.0,
                                },
                            )(),
                            type(
                                "Item",
                                (),
                                {
                                    "description": "إدارة وسائل التواصل الاجتماعي",
                                    "quantity": 3.0,
                                    "unit_price": 1000.0,
                                    "discount_rate": 0.0,
                                    "total": 3000.0,
                                },
                            )(),
                        ],
                        "discount_rate": 5.0,
                        "tax_rate": 14.0,
                    },
                )()

                # بيانات عميل تجريبية
                sample_client = {
                    "name": "أحمد محمد علي",
                    "phone": "+20 10 123 4567",
                    "email": "ahmed@example.com",
                    "address": "القاهرة، مصر",
                }

                # معاينة القالب
                html_content = self.template_service.generate_invoice_html(
                    sample_project, sample_client, template_id
                )
                exports_dir = self.template_service.get_exports_dir()
                filename = self.template_service.build_export_basename(
                    sample_project, sample_client
                )

                dialog = InvoicePreviewDialog(
                    html_content=html_content,
                    title="معاينة القالب",
                    base_url=self.template_service.templates_dir,
                    exports_dir=exports_dir,
                    file_basename=filename,
                    auto_print=False,
                    parent=self,
                )
                dialog.exec()

            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء المعاينة: {e}")

    def set_default_template(self):
        """تعيين القالب كافتراضي"""
        template_id = self.get_selected_template_id()
        if template_id:
            reply = QMessageBox.question(
                self,
                "تأكيد",
                "هل تريد تعيين هذا القالب كافتراضي؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                success = self.template_service.set_default_template(template_id)
                if success:
                    self.load_templates()
                    self.template_changed.emit()
                    QMessageBox.information(self, "نجح", "تم تعيين القالب كافتراضي")
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في تعيين القالب كافتراضي")

    def delete_template(self):
        """حذف القالب المحدد"""
        template_id = self.get_selected_template_id()
        if template_id:
            reply = QMessageBox.question(
                self,
                "تأكيد الحذف",
                "هل تريد حذف هذا القالب نهائياً؟\nلا يمكن التراجع عن هذا الإجراء.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                success = self.template_service.delete_template(template_id)
                if success:
                    self.load_templates()
                    self.template_changed.emit()
                    QMessageBox.information(self, "نجح", "تم حذف القالب")
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في حذف القالب")
