# الملف: ui/login_window.py
"""
نافذة تسجيل الدخول - تصميم احترافي
"""


from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.auth_models import AuthService, User
from core.resource_utils import get_resource_path


class LoginWindow(QDialog):
    """نافذة تسجيل الدخول"""

    def __init__(self, auth_service: AuthService, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.authenticated_user: User | None = None

        # إخفاء النافذة مؤقتاً لمنع الشاشة البيضاء
        self.setWindowOpacity(0.0)

        self.setWindowTitle("Sky Wave ERP - تسجيل الدخول")
        
        # 📱 تصميم متجاوب - حساب الحجم بناءً على الشاشة
        screen = QApplication.primaryScreen()
        if screen:
            screen_size = screen.availableGeometry()
            # حجم مناسب للشاشات المختلفة
            width = min(520, int(screen_size.width() * 0.4))
            height = min(850, int(screen_size.height() * 0.9))
            self.setFixedSize(width, height)
        else:
            self.setFixedSize(520, 850)
        
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # تطبيق شريط العنوان المخصص
        from ui.styles import setup_custom_title_bar
        setup_custom_title_bar(self)

        self.init_ui()
        self.center_on_screen()

        # إظهار النافذة بعد تطبيق الستايل
        self.setWindowOpacity(0.95)

    def init_ui(self):
        """إنشاء واجهة المستخدم"""
        # Layout رئيسي
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # الحاوية الرئيسية
        container = QWidget()
        container.setObjectName("container")
        container.setStyleSheet(self._get_styles())

        layout = QVBoxLayout(container)
        layout.setContentsMargins(50, 40, 50, 40)
        layout.setSpacing(0)

        # مساحة كبيرة في الأعلى
        layout.addSpacing(20)

        # === اللوجو ===
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setMinimumHeight(125)
        logo_pixmap = QPixmap(get_resource_path("logo.png"))
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(
                150, 150,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        layout.addWidget(logo_label)
        layout.addSpacing(50)

        # === العنوان الإنجليزي ===
        title = QLabel("Sky Wave ERB")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(-15)

        # === العنوان العربي ===
        subtitle = QLabel("ادارة موارد مؤسسة سكاي ويف")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(15)

        # === حقل اسم المستخدم ===
        user_label = QLabel("اسمك ايــه")
        user_label.setObjectName("label")
        layout.addWidget(user_label)
        layout.addSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setObjectName("input")
        self.username_input.setPlaceholderText("اصحاااا")
        # أمان: تأكد من أن الحقول فارغة تماماً
        self.username_input.clear()
        self.username_input.setText("")
        layout.addWidget(self.username_input)
        layout.addSpacing(15)

        # === حقل كلمة المرور ===
        pass_label = QLabel("هـات الباس")
        pass_label.setObjectName("label")
        layout.addWidget(pass_label)
        layout.addSpacing(10)

        self.password_input = QLineEdit()
        self.password_input.setObjectName("input")
        self.password_input.setPlaceholderText("يلا بينااا")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        # أمان: تأكد من أن الحقول فارغة تماماً
        self.password_input.clear()
        self.password_input.setText("")
        layout.addWidget(self.password_input)
        layout.addSpacing(20)

        # === رسالة الخطأ ===
        self.error_label = QLabel("")
        self.error_label.setObjectName("error")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)
        layout.addSpacing(30)

        # === زر تسجيل الدخول ===
        self.login_btn = QPushButton("خش  هاتجيبك")
        self.login_btn.setObjectName("loginBtn")
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.clicked.connect(self.attempt_login)
        layout.addWidget(self.login_btn)
        layout.addSpacing(35)

        # === زر الإلغاء ===
        cancel_btn = QPushButton("غور")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        layout.addSpacing(50)

        # === التذييل ===
        footer = QLabel("© 2026 Sky Wave Digital Marketing")
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        main_layout.addWidget(container)

        # ربط Enter
        self.username_input.returnPressed.connect(self.attempt_login)
        self.password_input.returnPressed.connect(self.attempt_login)

    def _get_styles(self):
        """التصميم"""
        return """
            #container {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 33, 57, 0.85), stop:1 rgba(21, 23, 40, 0.85));
                border-radius: 20px;
                border: 1px solid rgba(42, 45, 69, 0.6);
                backdrop-filter: blur(10px);
            }

            #title {
                font-size: 28px;
                font-weight: bold;
                color: #4da6ff;
            }

            #subtitle {
                font-size: 14px;
                color: #7a7f9d;
            }

            #label {
                font-size: 13px;
                color: #a0a5c0;
                font-weight: 500;
            }

            #input {
                background: rgba(37, 40, 66, 0.7);
                border: 2px solid rgba(53, 58, 85, 0.6);
                border-radius: 12px;
                padding: 16px 20px;
                font-size: 15px;
                color: #e0e3f0;
                min-height: 20px;
            }

            #input:focus {
                border-color: rgba(77, 166, 255, 0.8);
                background: rgba(42, 47, 74, 0.8);
            }

            #input::placeholder {
                color: #5a5f7a;
            }

            #error {
                color: #ff6b6b;
                font-size: 13px;
                background: rgba(255, 107, 107, 0.1);
                border-radius: 8px;
                padding: 10px;
            }

            #loginBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(77, 166, 255, 0.9), stop:1 rgba(61, 139, 219, 0.9));
                color: white;
                border: none;
                border-radius: 16px;
                padding: 22px;
                font-size: 19px;
                font-weight: bold;
                min-height: 35px;
            }

            #loginBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(61, 139, 219, 1.0), stop:1 rgba(45, 107, 181, 1.0));
            }

            #loginBtn:pressed {
                background: rgba(45, 107, 181, 1.0);
            }

            #cancelBtn {
                background: transparent;
                color: rgba(122, 127, 157, 0.9);
                border: 2px solid rgba(53, 58, 85, 0.6);
                border-radius: 16px;
                padding: 20px;
                font-size: 17px;
                font-weight: 500;
                min-height: 35px;
            }

            #cancelBtn:hover {
                background: rgba(220, 53, 69, 0.8);
                color: white;
            }

            #footer {
                font-size: 12px;
                color: #fff;
            }
        """

    def attempt_login(self):
        """محاولة تسجيل الدخول"""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self.show_error("يرجى إدخال اسم المستخدم وكلمة المرور")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("جاري التحقق...")

        user = self.auth_service.authenticate(username, password)

        if user:
            self.authenticated_user = user
            self.error_label.setVisible(False)
            self.login_btn.setText("✓ تم بنجاح")
            self.login_btn.setStyleSheet("""
                background: #2ecc71;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 16px;
                font-size: 16px;
                font-weight: bold;
            """)
            QTimer.singleShot(800, self.accept)
        else:
            self.show_error("اسم المستخدم أو كلمة المرور غير صحيحة")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("تسجيل الدخول")
            self.password_input.clear()
            self.password_input.setFocus()

    def show_error(self, msg):
        """عرض رسالة خطأ"""
        self.error_label.setText(msg)
        self.error_label.setVisible(True)

    def center_on_screen(self):
        """توسيط النافذة"""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def get_authenticated_user(self):
        """الحصول على المستخدم"""
        return self.authenticated_user
