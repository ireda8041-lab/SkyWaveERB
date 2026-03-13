from ui.styles import BUTTON_STYLES, RESPONSIVE_BUTTON_STYLE


def test_button_styles_use_compact_shared_dimensions():
    assert "border-radius: 8px;" in BUTTON_STYLES["primary"]
    assert "padding: 4px 12px;" in BUTTON_STYLES["primary"]
    assert "font-size: 11px;" in BUTTON_STYLES["primary"]
    assert "min-height: 14px;" in BUTTON_STYLES["primary"]
    assert "min-height: 36px;" in RESPONSIVE_BUTTON_STYLE
    assert "min-width: 92px;" in RESPONSIVE_BUTTON_STYLE


def test_secondary_and_danger_button_palettes_are_distinct():
    assert "#2b4d76" in BUTTON_STYLES["secondary"]
    assert "#f15a72" in BUTTON_STYLES["danger"]


def test_global_table_headers_use_compact_vertical_padding():
    from ui.styles import COMPLETE_STYLESHEET

    assert "padding: 7px 8px;" in COMPLETE_STYLESHEET
    assert "min-height: 30px;" in COMPLETE_STYLESHEET


def test_general_styles_do_not_force_background_on_every_qwidget():
    from ui.styles import COMPLETE_STYLESHEET

    general_section = COMPLETE_STYLESHEET.split("/* === 2. Inputs (Clean & Simple) === */", 1)[0]

    assert "QMainWindow, QDialog {" in general_section
    assert "QWidget {\n    background-color:" not in general_section


def test_complete_stylesheet_uses_explicit_checkbox_and_radio_indicators():
    from ui.styles import COMPLETE_STYLESHEET, get_icon_url

    assert "QCheckBox::indicator:checked" in COMPLETE_STYLESHEET
    assert "QCheckBox::indicator:pressed" in COMPLETE_STYLESHEET
    assert f'image: url({get_icon_url("checkmark")});' in COMPLETE_STYLESHEET
    assert "QRadioButton::indicator:checked" in COMPLETE_STYLESHEET
    assert "QRadioButton::indicator:pressed" in COMPLETE_STYLESHEET
    assert f'image: url({get_icon_url("radio-dot")});' in COMPLETE_STYLESHEET


def test_setup_custom_title_bar_defers_native_handle_creation(monkeypatch):
    import ui.styles as styles

    scheduled: list[tuple[int, object]] = []

    class _FakeWindow:
        def __init__(self):
            self.win_id_calls = 0

        def winId(self):
            self.win_id_calls += 1
            return 123

    monkeypatch.setattr(styles, "_IS_WINDOWS", True, raising=True)
    monkeypatch.setattr(
        styles.QTimer,
        "singleShot",
        lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        raising=True,
    )

    window = _FakeWindow()
    styles.setup_custom_title_bar(window)

    assert scheduled
    assert scheduled[0][0] == 0
    assert window.win_id_calls == 0

    styles.setup_custom_title_bar(window)
    assert len(scheduled) == 1
