from __future__ import annotations

import json

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


def test_sync_settings_save_realtime_and_lazy_fields(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)
    tab.show()
    qapp.processEvents()

    tab.realtime_enabled_checkbox.setChecked(True)
    tab.realtime_auto_detect_checkbox.setChecked(True)
    tab.realtime_change_stream_max_await_ms.setValue(300)
    tab.lazy_logo_enabled_checkbox.setChecked(True)
    tab.logo_fetch_batch_limit.setValue(12)
    tab.save_sync_settings()
    qapp.processEvents()

    cfg = json.loads((tmp_path / "sync_config.json").read_text(encoding="utf-8"))
    assert cfg["realtime_enabled"] is True
    assert cfg["realtime_auto_detect"] is True
    assert cfg["realtime_change_stream_max_await_ms"] == 300
    assert cfg["lazy_logo_enabled"] is True
    assert cfg["logo_fetch_batch_limit"] == 12
