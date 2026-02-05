from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from core.auth_models import User, UserRole
from ui.login_window import LoginWindow

from .qt_helpers import wait_until


class _FakeAuthService:
    def __init__(self, valid_username: str = "admin", valid_password: str = "pass"):
        self._valid_username = valid_username
        self._valid_password = valid_password

    def authenticate(self, username: str, password: str) -> User | None:
        if username == self._valid_username and password == self._valid_password:
            return User(
                id="u1",
                username=username,
                password_hash="x",
                role=UserRole.ADMIN,
                full_name="Admin",
                is_active=True,
            )
        return None


def test_login_requires_username_and_password(qapp):
    dialog = LoginWindow(_FakeAuthService())
    dialog.show()

    QTest.mouseClick(dialog.login_btn, Qt.MouseButton.LeftButton)

    assert dialog.error_label.isVisible()
    assert "يرجى" in dialog.error_label.text()
    assert dialog.login_btn.isEnabled()


def test_login_rejects_invalid_credentials(qapp):
    dialog = LoginWindow(_FakeAuthService(valid_password="correct"))
    dialog.show()

    dialog.username_input.setText("admin")
    dialog.password_input.setText("wrong")
    QTest.mouseClick(dialog.login_btn, Qt.MouseButton.LeftButton)

    assert dialog.error_label.isVisible()
    assert "غير صحيحة" in dialog.error_label.text()
    assert dialog.login_btn.isEnabled()
    assert dialog.password_input.text() == ""


def test_login_accepts_valid_credentials_after_delay(qapp):
    dialog = LoginWindow(_FakeAuthService(valid_password="correct"))
    dialog.show()

    dialog.username_input.setText("admin")
    dialog.password_input.setText("correct")
    QTest.mouseClick(dialog.login_btn, Qt.MouseButton.LeftButton)

    wait_until(lambda: dialog.result() == dialog.DialogCode.Accepted, timeout_ms=2500)
    assert dialog.get_authenticated_user() is not None
