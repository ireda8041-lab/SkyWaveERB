class _DummyButton:
    def __init__(self):
        self.enabled = True
        self.text = ""

    def setEnabled(self, value: bool):
        self.enabled = bool(value)

    def setText(self, value: str):
        self.text = value


class _FakeLoader:
    def load_async(
        self,
        operation_name,
        load_function,
        on_success=None,
        on_error=None,
        use_thread_pool=True,
        *args,
        **kwargs,
    ):
        if on_error:
            on_error("boom")


def test_dashboard_refresh_data_reenables_button_on_error(qt_app, monkeypatch):
    import core.data_loader
    from ui.dashboard_tab import DashboardTab

    monkeypatch.setattr(core.data_loader, "get_data_loader", lambda: _FakeLoader())

    fake = type("FakeDashboard", (), {})()
    fake._is_refreshing = False
    fake._last_refresh_time = 0
    fake._MIN_REFRESH_INTERVAL = 0
    fake.refresh_btn = _DummyButton()

    DashboardTab.refresh_data(fake)

    assert fake._is_refreshing is False
    assert fake.refresh_btn.enabled is True
    assert fake.refresh_btn.text == "🔄 تحديث"
