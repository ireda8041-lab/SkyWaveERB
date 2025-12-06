# الملف: ui/template_settings.py
"""
إعدادات قوالب الفواتير في تاب الإعدادات
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.template_service import TemplateService
from ui.styles import BUTTON_STYLES
from ui.template_manager import TemplateManager


class TemplateSettings(QWidget):
    """إعدادات قوالب الفواتير"""

    def __init__(self, settings_service, parent=None):
        super().__init__(parent)
        self.settings_service = settings_service

        # إنشاء خدمة القوالب
        # نحتاج repository من settings_service
        if hasattr(settings_service, 'repo'):
            repository = settings_service.repo
        else:
            # إنشاء repository مؤقت
            from core.repository import Repository
            repository = Repository()

        self.template_service = TemplateService(repository, settings_service)

        self.setup_ui()
        self.load_template_settings()

    def setup_ui(self):
        """إعداد واجهة المستخدم"""
        layout = QVBoxLayout(self)

        # عنوان القسم
        title_label = QLabel("🎨 إدارة قوالب الفواتير")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title_label)

        # معلومات سريعة
        info_group = QGroupBox("📋 معلومات سريعة")
        info_layout = QVBoxLayout(info_group)

        self.templates_count_label = QLabel("عدد القوالب: جاري التحميل...")
        self.default_template_label = QLabel("القالب الافتراضي: جاري التحميل...")

        info_layout.addWidget(self.templates_count_label)
        info_layout.addWidget(self.default_template_label)

        layout.addWidget(info_group)

        # إعدادات سريعة
        quick_group = QGroupBox("⚡ إعدادات سريعة")
        quick_layout = QVBoxLayout(quick_group)

        # اختيار القالب الافتراضي
        default_layout = QHBoxLayout()
        default_layout.addWidget(QLabel("القالب الافتراضي:"))

        self.default_template_combo = QComboBox()
        default_layout.addWidget(self.default_template_combo)

        default_layout.addStretch()
        quick_layout.addLayout(default_layout)

        layout.addWidget(quick_group)

        # أزرار الإجراءات السريعة
        actions_group = QGroupBox("🚀 إجراءات سريعة")
        actions_layout = QVBoxLayout(actions_group)

        buttons_layout = QHBoxLayout()

        self.preview_btn = QPushButton("👁️ معاينة القالب الافتراضي")
        self.preview_btn.setStyleSheet(BUTTON_STYLES["info"])
        self.preview_btn.clicked.connect(self.preview_default_template)
        buttons_layout.addWidget(self.preview_btn)

        self.manage_btn = QPushButton("🔧 إدارة القوالب")
        self.manage_btn.setStyleSheet(BUTTON_STYLES["primary"])
        self.manage_btn.clicked.connect(self.open_template_manager)
        buttons_layout.addWidget(self.manage_btn)

        buttons_layout.addStretch()
        actions_layout.addLayout(buttons_layout)

        layout.addWidget(actions_group)

        # خط فاصل
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # مدير القوالب المدمج
        self.template_manager = TemplateManager(self.template_service)
        self.template_manager.template_changed.connect(self.load_template_settings)
        layout.addWidget(self.template_manager)

        layout.addStretch()

    def load_template_settings(self):
        """تحميل إعدادات القوالب"""
        try:
            # تحديث عدد القوالب
            templates = self.template_service.get_all_templates()
            self.templates_count_label.setText(f"عدد القوالب: {len(templates)}")

            # تحديث القالب الافتراضي
            default_template = self.template_service.get_default_template()
            if default_template:
                self.default_template_label.setText(f"القالب الافتراضي: {default_template['name']}")
            else:
                self.default_template_label.setText("القالب الافتراضي: غير محدد")

            # تحديث قائمة القوالب في الـ ComboBox
            self.default_template_combo.clear()
            for template in templates:
                self.default_template_combo.addItem(
                    f"{'⭐ ' if template['is_default'] else ''}{template['name']}",
                    template['id']
                )

            # تحديد القالب الافتراضي في الـ ComboBox
            if default_template:
                for i in range(self.default_template_combo.count()):
                    if self.default_template_combo.itemData(i) == default_template['id']:
                        self.default_template_combo.setCurrentIndex(i)
                        break

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في تحميل إعدادات القوالب: {e}")

    def change_default_template(self):
        """تغيير القالب الافتراضي"""
        template_id = self.default_template_combo.currentData()
        if template_id:
            try:
                success = self.template_service.set_default_template(template_id)
                if success:
                    self.load_template_settings()
                    # إشعار بسيط
                    self.default_template_label.setText("✅ تم تغيير القالب الافتراضي")
                else:
                    QMessageBox.warning(self, "خطأ", "فشل في تغيير القالب الافتراضي")
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"حدث خطأ: {e}")

    def preview_default_template(self):
        """معاينة القالب الافتراضي"""
        try:
            default_template = self.template_service.get_default_template()
            if not default_template:
                QMessageBox.warning(self, "تنبيه", "لا يوجد قالب افتراضي محدد")
                return

            # إنشاء بيانات تجريبية للمعاينة

            # بيانات مشروع تجريبية
            sample_project = type('Project', (), {
                'id': 1001,
                'items': [
                    type('Item', (), {
                        'description': 'تصميم موقع إلكتروني احترافي',
                        'quantity': 1.0,
                        'unit_price': 8000.0,
                        'discount_rate': 10.0,
                        'total': 7200.0
                    })(),
                    type('Item', (), {
                        'description': 'إدارة وسائل التواصل الاجتماعي (3 أشهر)',
                        'quantity': 3.0,
                        'unit_price': 1500.0,
                        'discount_rate': 5.0,
                        'total': 4275.0
                    })(),
                    type('Item', (), {
                        'description': 'تحسين محركات البحث SEO',
                        'quantity': 1.0,
                        'unit_price': 3000.0,
                        'discount_rate': 0.0,
                        'total': 3000.0
                    })()
                ],
                'discount_rate': 5.0,
                'tax_rate': 14.0
            })()

            # بيانات عميل تجريبية
            sample_client = {
                'name': 'شركة النجاح للتجارة والاستيراد',
                'phone': '+20 10 123 4567',
                'email': 'info@success-company.com',
                'address': 'شارع التحرير، وسط البلد، القاهرة، مصر'
            }

            # معاينة القالب
            success = self.template_service.preview_template(
                sample_project, sample_client, default_template['id']
            )

            if not success:
                QMessageBox.warning(self, "خطأ", "فشل في معاينة القالب")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء المعاينة: {e}")

    def open_template_manager(self):
        """فتح مدير القوالب في نافذة منفصلة"""
        try:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout

            dialog = QDialog(self)
            dialog.setWindowTitle("إدارة قوالب الفواتير")
            dialog.setModal(True)
            dialog.resize(1000, 700)

            layout = QVBoxLayout(dialog)

            # إنشاء مدير قوالب جديد للنافذة
            template_manager = TemplateManager(self.template_service)
            template_manager.template_changed.connect(self.load_template_settings)
            layout.addWidget(template_manager)

            # زرار إغلاق
            close_btn = QPushButton("إغلاق")
            close_btn.setStyleSheet(BUTTON_STYLES["secondary"])
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في فتح مدير القوالب: {e}")
