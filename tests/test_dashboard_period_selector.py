from datetime import date


def test_period_selector_uses_appdata_path(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("SKYWAVEERP_DATA_DIR", str(tmp_path))
    from ui.dashboard_tab import PeriodSelector

    selector = PeriodSelector()
    assert str(tmp_path) in selector.SETTINGS_FILE


def test_get_date_range_custom_falls_back_without_recursion(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("SKYWAVEERP_DATA_DIR", str(tmp_path))
    from ui.dashboard_tab import PeriodSelector

    selector = PeriodSelector()
    selector._current_period = "custom"
    selector._custom_start = None
    selector._custom_end = None

    start, end = selector.get_date_range()
    assert start <= end
    assert start.day == 1


def test_get_date_range_custom_swaps_if_reversed(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("SKYWAVEERP_DATA_DIR", str(tmp_path))
    from ui.dashboard_tab import PeriodSelector

    selector = PeriodSelector()
    selector._current_period = "custom"
    selector._custom_start = date(2026, 2, 10)
    selector._custom_end = date(2026, 2, 1)

    start, end = selector.get_date_range()
    assert start.date() == date(2026, 2, 1)
    assert end.date() == date(2026, 2, 10)
