from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt


def _grid_position_for_widget(grid, widget):
    for index in range(grid.count()):
        item = grid.itemAt(index)
        if item is not None and item.widget() is widget:
            return grid.getItemPosition(index)
    return None


def test_dashboard_formats_last_update_in_twelve_hour_clock(qapp):
    from ui.dashboard_tab import DashboardTab

    text = DashboardTab._format_datetime_badge(datetime(2026, 3, 7, 23, 16), "آخر تحديث")

    assert text == "آخر تحديث: 07-03-2026 • 11:16 م"


def test_dashboard_recent_table_renders_operation_and_details_columns(qapp):
    from ui.dashboard_tab import DashboardTab

    tab = DashboardTab(MagicMock())
    try:
        tab._populate_recent_table(
            [
                {
                    "timestamp": datetime(2026, 3, 7, 23, 16),
                    "operation": "تعديل عميل",
                    "description": "Katkoty kids wear",
                    "details": "هاتف: 01000000000",
                    "amount": None,
                }
            ]
        )

        assert tab.recent_table.columnCount() == 4
        assert tab.recent_table.horizontalHeaderItem(0).text() == "التوقيت"
        assert tab.recent_table.horizontalHeaderItem(1).text() == "العملية"
        assert tab.recent_table.horizontalHeaderItem(2).text() == "البيان"
        assert tab.recent_table.horizontalHeaderItem(3).text() == "القيمة"
        assert tab.recent_table.item(0, 1).text() == "تعديل عميل"
        assert "Katkoty kids wear" in tab.recent_table.item(0, 2).text()
        assert "هاتف: 01000000000" in tab.recent_table.item(0, 2).text()
        assert tab.recent_table.item(0, 3).text() == "—"
        assert tab.recent_table.item(0, 0).text().endswith("م")
        assert tab.recent_table.item(0, 2).textAlignment() == int(Qt.AlignmentFlag.AlignCenter)
        assert tab.recent_table.item(0, 3).textAlignment() == int(Qt.AlignmentFlag.AlignCenter)
    finally:
        tab.close()


def test_dashboard_keeps_recent_activity_section_visible_and_enabled(qapp):
    from ui.dashboard_tab import DashboardTab

    tab = DashboardTab(MagicMock())
    try:
        assert tab._show_recent_activity is True
        assert tab._load_recent_activity_data is True
        assert not tab.table_container.isHidden()
        assert tab.bottom_splitter.count() == 2
    finally:
        tab.close()


def test_dashboard_recent_hint_mentions_verified_operations_from_all_sections(qapp):
    from ui.dashboard_tab import DashboardTab

    tab = DashboardTab(MagicMock())
    try:
        assert "العملاء" in tab.recent_hint_lbl.text()
        assert "المشاريع" in tab.recent_hint_lbl.text()
        assert "الفواتير" in tab.recent_hint_lbl.text()
        assert "الدفعات" in tab.recent_hint_lbl.text()
        assert "المصروفات" in tab.recent_hint_lbl.text()
    finally:
        tab.close()


def test_dashboard_formats_aware_recent_timestamps_in_local_time(qapp):
    from ui.dashboard_tab import DashboardTab

    utc_value = datetime(2026, 3, 7, 21, 16, tzinfo=timezone.utc)
    local_value = utc_value.astimezone().replace(tzinfo=None)

    text = DashboardTab._format_recent_timestamp(utc_value)

    assert text == (
        f"{local_value.strftime('%d-%m-%Y')} • "
        f"{DashboardTab._format_twelve_hour_time(local_value)}"
    )


def test_dashboard_uses_single_row_cards_layout_on_wide_screens(qapp):
    from ui.dashboard_tab import DashboardTab

    tab = DashboardTab(MagicMock())
    try:
        tab.resize(1800, 900)
        tab._rearrange_cards()

        position = _grid_position_for_widget(tab.cards_grid, tab.card_net_profit)

        assert position is not None
        assert position[0] == 0
        assert position[1] == 4
        assert tab.cards_container.height() <= tab.card_sales.maximumHeight() + 4
    finally:
        tab.close()


def test_dashboard_recent_pagination_group_is_centered_and_ltr(qapp):
    from ui.dashboard_tab import DashboardTab

    tab = DashboardTab(MagicMock())
    try:
        assert tab.recent_pagination_widget.layoutDirection() == Qt.LayoutDirection.LeftToRight
        assert tab.recent_prev_button.parentWidget() is tab.recent_pagination_widget
        assert tab.recent_next_button.parentWidget() is tab.recent_pagination_widget
        assert tab.recent_page_size_combo.parentWidget() is tab.recent_pagination_widget
        assert tab.recent_page_info_label.parentWidget() is tab.recent_pagination_widget
        assert tab.recent_pagination_size_label.parentWidget() is tab.recent_pagination_widget
        assert tab.recent_prev_button.height() == tab.recent_next_button.height()
        assert tab.recent_prev_button.height() == tab.recent_page_size_combo.height()
        assert tab.recent_prev_button.height() == tab.recent_page_info_label.height()
        assert tab.recent_prev_button.height() == tab.recent_pagination_size_label.height()
    finally:
        tab.close()
