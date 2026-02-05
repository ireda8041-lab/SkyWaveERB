from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from ui.settings_tab import SettingsTab


class _FakeSettingsService:
    def __init__(self):
        self._settings = {}

    def get_settings(self):
        return dict(self._settings)

    def update_settings(self, data):
        self._settings.update(data or {})

    def save_logo_from_file(self, _path: str) -> bool:
        return False

    def get_logo_as_pixmap(self):
        return None


def test_settings_search_switches_tabs(qapp):
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)
    tab.show()
    qapp.processEvents()

    assert "بيانات الشركة" in tab.tabs.tabText(tab.tabs.currentIndex())

    tab.search_input.setText("العملات")
    QTest.keyClick(tab.search_input, Qt.Key.Key_Return)
    qapp.processEvents()

    assert "العملات" in tab.tabs.tabText(tab.tabs.currentIndex())


def test_settings_tab_switch_does_not_crash_without_repo(qapp):
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)
    tab.show()
    qapp.processEvents()

    for i in range(tab.tabs.count()):
        tab.tabs.setCurrentIndex(i)
        qapp.processEvents()
