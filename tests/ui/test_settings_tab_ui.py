from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QBoxLayout, QWidget

from ui.settings_tab import SettingsTab


class _FakeSettingsService:
    def __init__(self, initial=None):
        self._settings = dict(initial or {})
        self.update_setting_calls: list[tuple[str, object]] = []

    def get_settings(self):
        return dict(self._settings)

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def update_settings(self, data):
        self._settings.update(data or {})

    def update_setting(self, key, value):
        self._settings[key] = value
        self.update_setting_calls.append((key, value))

    def save_logo_from_file(self, _path: str) -> bool:
        return False

    def get_logo_as_pixmap(self):
        return None


class _ImmediateLoader:
    def load_async(
        self,
        operation_name,
        load_function,
        *args,
        on_success=None,
        on_error=None,
        use_thread_pool=True,
        **kwargs,
    ):
        try:
            result = load_function()
        except Exception as exc:  # pragma: no cover - defensive
            if on_error:
                on_error(str(exc))
            return
        if on_success:
            on_success(result)


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


def test_settings_tab_lazily_builds_company_tab(qapp):
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)

    assert not hasattr(tab, "company_name_input")

    tab.show()
    qapp.processEvents()

    assert hasattr(tab, "company_name_input")
    assert tab.tabs.currentWidget() is tab.company_tab


def test_settings_tab_lazily_creates_template_subtab(monkeypatch, qapp):
    import ui.settings_tab as settings_module

    created = {"count": 0}

    class _FakeTemplateSettings(QWidget):
        def __init__(self, settings_service):
            super().__init__()
            self.settings_service = settings_service
            created["count"] += 1

    monkeypatch.setattr(
        settings_module,
        "_get_template_settings_class",
        lambda: _FakeTemplateSettings,
        raising=True,
    )

    tab = settings_module.SettingsTab(
        settings_service=_FakeSettingsService(), repository=None, current_user=None
    )
    tab.show()
    qapp.processEvents()

    assert created["count"] == 0
    assert tab.template_tab is None

    tab.tabs.setCurrentIndex(tab._template_tab_index)
    qapp.processEvents()

    assert created["count"] == 1
    assert tab.template_tab is not None


def test_settings_tab_lazily_creates_hidden_search_bars(monkeypatch, qapp):
    import ui.settings_tab as settings_module

    created = {"count": 0}

    class _FakeSearchBar(QWidget):
        def __init__(self, table, placeholder=""):
            super().__init__()
            self.table = table
            self.placeholder = placeholder
            created["count"] += 1

    monkeypatch.setattr(
        settings_module,
        "_get_universal_search_bar_class",
        lambda: _FakeSearchBar,
        raising=True,
    )

    tab = settings_module.SettingsTab(
        settings_service=_FakeSettingsService(), repository=None, current_user=None
    )
    tab.show()
    qapp.processEvents()

    assert created["count"] == 0
    assert tab.payment_methods_search is None
    assert tab.note_templates_search is None

    tab.tabs.setCurrentWidget(tab.payment_methods_tab)
    qapp.processEvents()

    assert created["count"] == 1
    assert tab.payment_methods_search is not None
    assert tab.note_templates_search is None

    tab.tabs.setCurrentWidget(tab.project_notes_tab)
    qapp.processEvents()

    assert created["count"] == 2
    assert tab.note_templates_search is not None


def test_settings_tab_lazily_builds_hidden_heavy_tabs(qapp):
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)
    tab.show()
    qapp.processEvents()

    assert not hasattr(tab, "db_stats_label")
    assert not hasattr(tab, "currencies_table")
    assert not hasattr(tab, "auto_sync_enabled")

    tab.tabs.setCurrentWidget(tab.currency_tab)
    qapp.processEvents()
    assert hasattr(tab, "currencies_table")

    tab.tabs.setCurrentWidget(tab.backup_tab)
    qapp.processEvents()
    assert hasattr(tab, "db_stats_label")

    tab.tabs.setCurrentWidget(tab.sync_tab)
    qapp.processEvents()
    assert hasattr(tab, "auto_sync_enabled")


def test_settings_tab_does_not_include_default_accounts_tab(qapp):
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)
    tab.show()
    qapp.processEvents()

    tab_labels = [tab.tabs.tabText(i) for i in range(tab.tabs.count())]

    assert not hasattr(tab, "default_accounts_tab")
    assert all("الحسابات الافتراضية" not in label for label in tab_labels)


def test_sync_settings_save_realtime_and_lazy_fields(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)
    tab.show()
    qapp.processEvents()
    tab.tabs.setCurrentWidget(tab.sync_tab)
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


def test_sync_settings_load_runtime_defaults_when_config_missing(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class _UnifiedSync:
        _enabled = True
        _auto_sync_interval = 30 * 60 * 1000
        _quick_sync_interval = 15 * 1000
        _delta_sync_interval_seconds = 15
        _connection_check_interval = 30 * 1000
        _realtime_enabled = True
        _realtime_auto_detect = False
        _realtime_change_stream_max_await_ms = 275
        _lazy_logo_enabled = False
        _logo_fetch_batch_limit = 7

    class _Repo:
        unified_sync = _UnifiedSync()

    tab = SettingsTab(
        settings_service=_FakeSettingsService(), repository=_Repo(), current_user=None
    )
    tab.show()
    qapp.processEvents()
    tab.tabs.setCurrentWidget(tab.sync_tab)
    qapp.processEvents()

    assert tab.full_sync_interval.value() == 30
    assert tab.quick_sync_interval.value() == 15
    assert tab.connection_check_interval.value() == 30
    assert tab.realtime_enabled_checkbox.isChecked() is True
    assert tab.realtime_auto_detect_checkbox.isChecked() is False
    assert tab.realtime_change_stream_max_await_ms.value() == 275
    assert tab.lazy_logo_enabled_checkbox.isChecked() is False
    assert tab.logo_fetch_batch_limit.value() == 7


def test_refresh_sync_status_renders_multiline_html(qapp):
    class _UnifiedSync:
        is_online = True
        _is_syncing = False

        def get_sync_status(self):
            return {"is_online": True, "is_syncing": False, "tables": {"clients": {"pending": 0}}}

        def get_sync_metrics(self):
            return {
                "total_syncs": 12,
                "successful_syncs": 11,
                "failed_syncs": 1,
                "last_sync_time": "2026-03-13T00:59:44",
                "total_records_synced": 22,
            }

    class _Repo:
        unified_sync = _UnifiedSync()

    tab = SettingsTab(
        settings_service=_FakeSettingsService(), repository=_Repo(), current_user=None
    )
    tab.show()
    qapp.processEvents()
    tab.tabs.setCurrentWidget(tab.sync_tab)
    qapp.processEvents()

    tab.refresh_sync_status()
    qapp.processEvents()

    assert tab.sync_status_label.textFormat() == Qt.TextFormat.RichText
    assert "<br>" in tab.sync_status_label.text()
    assert "إحصائيات المزامنة" in tab.sync_status_label.text()


def test_settings_active_subtab_refreshes_only_dirty_section(qapp, monkeypatch):
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)
    tab.show()
    qapp.processEvents()

    calls: list[str] = []
    monkeypatch.setattr(tab, "load_settings_data", lambda: calls.append("company"))
    monkeypatch.setattr(tab, "load_users", lambda: calls.append("users"))
    monkeypatch.setattr(tab, "load_currencies", lambda: calls.append("currencies"))

    tab.tabs.setCurrentWidget(tab.currency_tab)
    qapp.processEvents()
    calls.clear()

    tab.mark_data_changed("currencies")
    tab.load_active_subtab_data(force_reload=False)

    assert calls == ["currencies"]


def test_load_currencies_uses_local_defaults_without_repo(monkeypatch, qapp):
    import ui.settings_tab as settings_module

    monkeypatch.setattr(
        settings_module,
        "_create_data_loader",
        lambda: (_ for _ in ()).throw(AssertionError("data loader should not be used")),
        raising=True,
    )

    tab = settings_module.SettingsTab(
        settings_service=_FakeSettingsService(), repository=None, current_user=None
    )
    tab.show()
    qapp.processEvents()
    tab.tabs.setCurrentWidget(tab.currency_tab)
    qapp.processEvents()

    assert tab.currencies_table.rowCount() >= 1
    assert tab._currencies_all


def test_load_payment_methods_does_not_rewrite_existing_settings(qapp):
    service = _FakeSettingsService(
        {
            "payment_methods": [
                {"name": "Cash", "description": "Cash", "details": "", "active": True}
            ]
        }
    )
    tab = SettingsTab(settings_service=service, repository=None, current_user=None)
    tab.show()
    tab.load_settings_data()
    qapp.processEvents()

    service.update_setting_calls.clear()
    tab.load_payment_methods()

    assert service.update_setting_calls == []


def test_load_payment_methods_seeds_configured_payment_channels(qapp):
    service = _FakeSettingsService({"payment_methods": []})
    tab = SettingsTab(settings_service=service, repository=None, current_user=None)
    tab.show()
    qapp.processEvents()

    seeded = service.get_setting("payment_methods")

    assert [method["name"] for method in seeded] == [
        "VF Cash",
        "InstaPay",
        "Bank Misr Local",
        "Bank Misr Intl",
        "Cash",
    ]
    assert seeded[0]["details"] == "01067894321 - حازم أشرف\n01021965200 - رضا سامي"
    assert seeded[3]["details"].endswith("SWIFT CODE: BMISEGCXXXX")
    assert seeded[4]["details"] == "الخزنة النقدية - مقر الشركة"


def test_settings_action_buttons_use_consistent_labels(qapp):
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)
    tab.show()
    qapp.processEvents()
    tab._ensure_section_ui("currencies")
    tab._ensure_section_ui("users")
    tab._ensure_section_ui("payment_methods")
    tab._ensure_section_ui("project_notes")

    assert tab.select_logo_btn.text() == "📷 اختيار شعار الشركة"
    assert tab.remove_logo_btn.text() == "🗑️ حذف الشعار"
    assert tab.edit_currency_btn.text() == "✏️ تعديل العملة"
    assert tab.delete_currency_btn.text() == "🗑️ حذف العملة"
    assert tab.edit_user_btn.text() == "✏️ تعديل المستخدم"
    assert tab.permissions_btn.text() == "🔐 إدارة الصلاحيات"
    assert tab.delete_user_btn.text() == "🗑️ تعطيل المستخدم"
    assert tab.activate_user_btn.text() == "✅ تفعيل المستخدم"
    assert tab.edit_payment_method_btn.text() == "✏️ تعديل طريقة الدفع"
    assert tab.delete_payment_method_btn.text() == "🗑️ حذف طريقة الدفع"
    assert tab.add_note_template_btn.text() == "➕ إضافة قالب ملاحظة"
    assert tab.edit_note_template_btn.text() == "✏️ تعديل قالب الملاحظة"
    assert tab.delete_note_template_btn.text() == "🗑️ حذف قالب الملاحظة"


def test_sync_checkboxes_keep_native_indicator_rendering(qapp):
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)
    tab.show()
    qapp.processEvents()
    tab._ensure_section_ui("sync")

    assert "QCheckBox::indicator" not in tab.auto_sync_enabled.styleSheet()
    assert "QCheckBox::indicator" not in tab.realtime_enabled_checkbox.styleSheet()

    tab.auto_sync_enabled.setChecked(True)
    tab.auto_sync_enabled.click()
    qapp.processEvents()
    assert tab.auto_sync_enabled.isChecked() is False

    tab.auto_sync_enabled.click()
    qapp.processEvents()
    assert tab.auto_sync_enabled.isChecked() is True


def test_company_tab_switches_to_compact_layout_on_resize(qapp):
    tab = SettingsTab(settings_service=_FakeSettingsService(), repository=None, current_user=None)
    tab.resize(1600, 900)
    tab.show()
    qapp.processEvents()

    assert tab._company_main_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert tab._company_logo_buttons_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert tab._company_badges_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert tab._company_logo_frame.minimumWidth() == 320

    tab.resize(1100, 900)
    qapp.processEvents()

    assert tab._company_main_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert tab._company_logo_buttons_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert tab._company_badges_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert tab._company_logo_frame.minimumWidth() == 0


def test_company_tab_updates_status_badges_and_preview_meta(qapp):
    service = _FakeSettingsService(
        {
            "company_name": "Sky Wave",
            "company_phone": "01012345678",
            "company_email": "info@skywave.com",
            "company_website": "skywave.com",
        }
    )
    tab = SettingsTab(settings_service=service, repository=None, current_user=None)
    tab.show()
    tab.load_settings_data()
    qapp.processEvents()

    assert tab.company_status_badge.text() == "محفوظ"
    assert "اكتمال 4/7" == tab.company_completeness_badge.text()
    assert "\n" in tab.company_preview_meta.text()
    assert tab.save_company_btn.isEnabled() is False

    tab.company_tagline_input.setText("وكالة تسويق رقمي")
    qapp.processEvents()

    assert tab.company_status_badge.text() == "تغييرات غير محفوظة"
    assert tab.company_completeness_badge.text() == "اكتمال 5/7"
    assert tab.save_company_btn.isEnabled() is True


def test_load_settings_data_batches_company_form_updates(monkeypatch, qapp):
    import ui.settings_tab as settings_module

    service = _FakeSettingsService(
        {
            "company_name": "Sky Wave",
            "company_tagline": "Agency",
            "company_address": "Cairo",
            "company_phone": "01012345678",
            "company_email": "info@skywave.com",
            "company_website": "skywave.com",
            "company_vat": "12345",
        }
    )
    calls = {"count": 0}
    original = settings_module.SettingsTab._on_company_form_changed

    def counted(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(settings_module.SettingsTab, "_on_company_form_changed", counted)

    tab = settings_module.SettingsTab(settings_service=service, repository=None, current_user=None)
    tab.show()
    qapp.processEvents()
    calls["count"] = 0

    tab.load_settings_data()
    qapp.processEvents()

    assert calls["count"] == 1


def test_create_backup_reports_partial_failures(monkeypatch, qapp, tmp_path):
    import ui.settings_tab as settings_module

    class _Repo:
        def get_all_clients(self):
            return []

        def get_all_services(self):
            return []

        def get_all_projects(self):
            return []

        def get_all_invoices(self):
            return []

        def get_all_expenses(self):
            return []

        def get_all_accounts(self):
            return []

        def get_all_currencies(self):
            return []

        def get_all_journal_entries(self):
            return []

        def get_all_payments(self):
            return []

    class _BrokenTaskService:
        def get_all_tasks(self):
            raise RuntimeError("tasks offline")

    service = _FakeSettingsService()

    def _broken_get_settings():
        raise RuntimeError("settings unavailable")

    service.get_settings = _broken_get_settings  # type: ignore[method-assign]

    info_calls: list[str] = []
    backup_path = tmp_path / "backup.json"

    monkeypatch.setattr(
        settings_module.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(backup_path), "JSON Files (*.json)"),
        raising=True,
    )
    monkeypatch.setattr(
        settings_module,
        "_create_data_loader",
        lambda: _ImmediateLoader(),
        raising=True,
    )
    monkeypatch.setattr(
        settings_module,
        "_get_task_service_class",
        lambda: _BrokenTaskService,
        raising=True,
    )
    monkeypatch.setattr(
        settings_module.QMessageBox,
        "information",
        lambda *args, **kwargs: info_calls.append(args[2]),
        raising=True,
    )

    tab = settings_module.SettingsTab(
        settings_service=service, repository=_Repo(), current_user=None
    )
    tab.show()
    qapp.processEvents()
    tab.tabs.setCurrentWidget(tab.backup_tab)
    qapp.processEvents()

    tab.create_backup()
    qapp.processEvents()

    assert backup_path.exists()
    assert info_calls
    assert "⚠️ تمت متابعة النسخ مع ملاحظات" in info_calls[0]
    assert "tasks: tasks offline" in info_calls[0]
    assert "settings: settings unavailable" in info_calls[0]
