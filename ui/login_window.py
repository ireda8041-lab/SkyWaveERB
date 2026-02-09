"""
نافذة تسجيل الدخول - تصميم متجاوب مع الشاشات الصغيرة
"""

from __future__ import annotations

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
        self._ui_scale = 1.0

        self.setWindowOpacity(0.0)
        self.setWindowTitle("Sky Wave ERP - تسجيل الدخول")

        self._configure_responsive_size()

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        from ui.styles import setup_custom_title_bar

        setup_custom_title_bar(self)

        self.init_ui()
        self.center_on_screen()

        self.setWindowOpacity(0.95)

    def _configure_responsive_size(self):
        screen = QApplication.primaryScreen()
        if not screen:
            self.setMinimumSize(320, 460)
            self.resize(460, 760)
            return

        geo = screen.availableGeometry()
        screen_w = max(800, geo.width())
        screen_h = max(600, geo.height())

        # Scale down layout on smaller screens while preserving readability.
        self._ui_scale = max(0.72, min(screen_w / 1366.0, screen_h / 900.0, 1.0))

        width = int(min(560, max(360, screen_w * 0.42)))
        height = int(min(860, max(520, screen_h * 0.90)))

        self.setMinimumSize(320, 460)
        self.setMaximumSize(max(420, screen_w - 40), max(560, screen_h - 20))
        self.resize(width, height)

    def _sx(self, px: int, minimum: int = 0) -> int:
        return max(minimum, int(px * self._ui_scale))

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setObjectName("container")
        container.setStyleSheet(self._get_styles())

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            self._sx(50, 20), self._sx(40, 16), self._sx(50, 20), self._sx(40, 16)
        )
        layout.setSpacing(0)

        layout.addSpacing(self._sx(20, 8))

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setMinimumHeight(self._sx(120, 90))

        logo_pixmap = QPixmap(get_resource_path("logo.png"))
        if not logo_pixmap.isNull():
            logo_label.setPixmap(
                logo_pixmap.scaled(
                    self._sx(150, 100),
                    self._sx(150, 100),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        layout.addWidget(logo_label)
        layout.addSpacing(self._sx(48, 14))

        title = QLabel("Sky Wave ERB")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(self._sx(-15))

        subtitle = QLabel("ادارة موارد مؤسسة سكاي ويف")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(self._sx(15, 6))

        user_label = QLabel("اسمك ايــه")
        user_label.setObjectName("label")
        layout.addWidget(user_label)
        layout.addSpacing(self._sx(10, 4))

        self.username_input = QLineEdit()
        self.username_input.setObjectName("input")
        self.username_input.setPlaceholderText("اصحااااا")
        self.username_input.setMaxLength(50)
        self.username_input.clear()
        self.username_input.setText("")
        layout.addWidget(self.username_input)
        layout.addSpacing(self._sx(15, 6))

        pass_label = QLabel("هــات الباس")
        pass_label.setObjectName("label")
        layout.addWidget(pass_label)
        layout.addSpacing(self._sx(10, 4))

        self.password_input = QLineEdit()
        self.password_input.setObjectName("input")
        self.password_input.setPlaceholderText("يلا بينااا")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMaxLength(100)
        self.password_input.clear()
        self.password_input.setText("")
        layout.addWidget(self.password_input)
        layout.addSpacing(self._sx(20, 8))

        self.error_label = QLabel("")
        self.error_label.setObjectName("error")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)
        layout.addSpacing(self._sx(24, 10))

        self.login_btn = QPushButton("خش  هاجيبك")
        self.login_btn.setObjectName("loginBtn")
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.clicked.connect(self.attempt_login)
        layout.addWidget(self.login_btn)
        layout.addSpacing(self._sx(16, 8))

        cancel_btn = QPushButton("غور")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        layout.addSpacing(self._sx(22, 10))

        footer = QLabel("© 2026 Sky Wave Digital Marketing")
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        main_layout.addWidget(container)

        self.username_input.returnPressed.connect(self.attempt_login)
        self.password_input.returnPressed.connect(self.attempt_login)

    def _get_styles(self) -> str:
        s = self._ui_scale
        title_size = max(20, int(28 * s))
        subtitle_size = max(11, int(14 * s))
        label_size = max(11, int(13 * s))
        input_font = max(12, int(15 * s))
        input_padding_v = max(10, int(16 * s))
        input_padding_h = max(14, int(25 * s))
        input_radius = max(12, int(20 * s))
        btn_radius = max(10, int(16 * s))
        login_font = max(14, int(19 * s))
        cancel_font = max(13, int(17 * s))
        footer_size = max(10, int(12 * s))
        container_radius = max(24, int(50 * s))

        return f"""
            #container {{
                background: #1e2139;
                border-radius: {container_radius}px;
                border: 1px solid #2a2d45;
            }}

            #title {{
                font-size: {title_size}px;
                font-weight: bold;
                color: #4da6ff;
            }}

            #subtitle {{
                font-size: {subtitle_size}px;
                color: #7a7f9d;
            }}

            #label {{
                font-size: {label_size}px;
                color: #a0a5c0;
                font-weight: 500;
            }}

            QLineEdit#input {{
                background: #252842;
                border: 2px solid #353a55;
                border-radius: {input_radius}px;
                padding: {input_padding_v}px {input_padding_h}px;
                font-size: {input_font}px;
                color: #e0e3f0;
                min-height: {max(16, int(25 * s))}px;
            }}

            QLineEdit#input:focus {{
                border-color: #4da6ff;
                background: #2a2f4a;
            }}

            #error {{
                color: #ff6b6b;
                font-size: {max(11, int(13 * s))}px;
                background: #3d1f1f;
                border-radius: 8px;
                padding: {max(6, int(10 * s))}px;
            }}

            #loginBtn {{
                background: #4da6ff;
                color: white;
                border: none;
                border-radius: {btn_radius}px;
                padding: {max(12, int(22 * s))}px;
                font-size: {login_font}px;
                font-weight: bold;
                min-height: {max(26, int(35 * s))}px;
            }}

            #loginBtn:hover {{
                background: #3d8bdb;
            }}

            #loginBtn:pressed {{
                background: #2d6bb5;
            }}

            #cancelBtn {{
                background: transparent;
                color: #7a7f9d;
                border: 2px solid #353a55;
                border-radius: {btn_radius}px;
                padding: {max(10, int(20 * s))}px;
                font-size: {cancel_font}px;
                font-weight: 500;
                min-height: {max(24, int(35 * s))}px;
            }}

            #cancelBtn:hover {{
                background: #dc3545;
                color: white;
            }}

            #footer {{
                font-size: {footer_size}px;
                color: #fff;
            }}
        """

    def attempt_login(self):
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
            self.login_btn.setStyleSheet(
                """
                background: #2ecc71;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 16px;
                font-size: 16px;
                font-weight: bold;
            """
            )
            QTimer.singleShot(800, self.accept)
        else:
            self.show_error("اسم المستخدم أو كلمة المرور غير صحيحة")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("تسجيل الدخول")
            self.password_input.clear()
            self.password_input.setFocus()

    def show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.setVisible(True)

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(max(geo.x(), x), max(geo.y(), y))

    def get_authenticated_user(self):
        return self.authenticated_user
