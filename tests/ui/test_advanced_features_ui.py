from __future__ import annotations

import os
import time

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem


def test_universal_search_filters_table(qapp):
    from ui.universal_search import UniversalSearchBar

    table = QTableWidget()
    table.setColumnCount(2)
    table.setRowCount(3)
    table.setItem(0, 0, QTableWidgetItem("Ahmed"))
    table.setItem(0, 1, QTableWidgetItem("Cairo"))
    table.setItem(1, 0, QTableWidgetItem("Mona"))
    table.setItem(1, 1, QTableWidgetItem("Giza"))
    table.setItem(2, 0, QTableWidgetItem("Omar"))
    table.setItem(2, 1, QTableWidgetItem("Cairo"))

    search = UniversalSearchBar(table)
    search.setText("cairo")
    qapp.processEvents()

    assert table.isRowHidden(0) is False
    assert table.isRowHidden(1) is True
    assert table.isRowHidden(2) is False

    search.setText("")
    qapp.processEvents()
    assert table.isRowHidden(0) is False
    assert table.isRowHidden(1) is False
    assert table.isRowHidden(2) is False


def test_custom_fields_manager_persists_to_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("SKYWAVEERP_DATA_DIR", str(data_dir))

    from core import custom_fields_manager as cfm

    cfm.CustomFieldsManager._instance = None
    manager = cfm.CustomFieldsManager()

    assert manager.add_value("countries", "Egypt") is True
    assert "Egypt" in manager.get_values("countries")
    assert os.path.exists(manager._file_path)

    cfm.CustomFieldsManager._instance = None
    manager2 = cfm.CustomFieldsManager()
    assert "Egypt" in manager2.get_values("countries")


def test_status_bar_toast_defaults_to_ten_seconds(qapp):
    from ui.status_bar_widget import ToastNotification

    toast = ToastNotification("Done", "Saved")

    assert toast.duration == 10000

    toast.close()


def test_toast_notification_instantiates(qapp):
    from ui import notification_system as ns

    toast = ns.ToastNotification(message="Hello", duration=10)
    toast.show()
    qapp.processEvents()
    toast.close()


def test_toast_notification_exposes_twelve_hour_time_badge(qapp):
    from PyQt6.QtWidgets import QLabel

    from ui import notification_system as ns

    toast = ns.ToastNotification(message="Hello", duration=10)
    time_label = toast.findChild(QLabel, "notif_time_label")

    assert time_label is not None
    assert time_label.text().endswith(("ص", "م"))

    toast.close()


def test_warning_toast_uses_prominent_layout_and_type_badge(qapp):
    from PyQt6.QtWidgets import QLabel

    from ui import notification_system as ns

    info_toast = ns.ToastNotification(message="Info", duration=10)
    warning_toast = ns.ToastNotification(
        message="Warning",
        duration=10,
        notification_type=ns.NotificationType.WARNING,
    )

    type_badge = warning_toast.findChild(QLabel, "notif_type_badge")

    assert type_badge is not None
    assert type_badge.text().strip() != ""
    assert warning_toast.width() > info_toast.width()

    info_toast.close()
    warning_toast.close()


def test_toast_notification_shows_operation_details_when_metadata_exists(qapp):
    from PyQt6.QtWidgets import QLabel

    from ui import notification_system as ns

    toast = ns.ToastNotification(
        message="Katkoty kids wear",
        title="تم تعديل عميل",
        duration=10,
        entity_type="client",
        action="updated",
    )

    details_label = toast.findChild(QLabel, "notif_operation_details")
    message_label = toast.findChild(QLabel, "notif_message_label")

    assert details_label is not None
    assert details_label.text() == "تم تعديل بيانات العميل بنجاح"
    assert message_label is not None
    assert message_label.text() == "Katkoty kids wear"

    toast.close()


def test_toast_meta_controls_use_transparent_backgrounds(qapp):
    from PyQt6.QtWidgets import QLabel, QPushButton

    from ui import notification_system as ns

    toast = ns.ToastNotification(message="Hello", duration=10)
    time_label = toast.findChild(QLabel, "notif_time_label")
    type_badge = toast.findChild(QLabel, "notif_type_badge")

    assert time_label is not None
    assert type_badge is not None
    assert "background: transparent" in time_label.styleSheet()
    assert "background: transparent" in type_badge.styleSheet()
    assert toast.findChild(QPushButton, "notif_close_button") is None

    toast.close()


def test_toast_notification_visibility_guard_runs_until_close(qapp):
    from ui import notification_system as ns

    toast = ns.ToastNotification(message="Hello", duration=10)
    toast.show_notification()
    qapp.processEvents()

    assert toast.duration == 10000
    assert toast._visibility_guard_timer.isActive() is True

    toast.close_notification()
    qapp.processEvents()

    assert toast._visibility_guard_timer.isActive() is False


def test_toast_notification_uses_standalone_non_tool_window_flags(qapp):
    from PyQt6.QtCore import Qt

    from ui import notification_system as ns

    toast = ns.ToastNotification(message="Hello", duration=10)

    flags = toast.windowFlags()

    assert toast.windowType() == Qt.WindowType.Window
    assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
    assert bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus)
    assert toast.focusPolicy() == Qt.FocusPolicy.NoFocus

    toast.close()


def test_notification_manager_keeps_toast_visible_after_dialog_closes(qapp):
    from PyQt6.QtWidgets import QDialog, QMainWindow

    from ui import notification_system as ns

    ns.NotificationManager.shutdown()
    ns.NotificationManager._instance = None
    ns.NotificationManager._app_is_quitting = False
    qapp.setProperty("_skywave_force_quit", False)

    main_window = QMainWindow()
    dialog = QDialog(main_window)
    dialog.setModal(True)

    try:
        main_window.show()
        qapp.processEvents()
        dialog.show()
        qapp.processEvents()

        ns.NotificationManager.show("Saved", title="Done", sync=False)

        for _ in range(6):
            qapp.processEvents()
            time.sleep(0.03)

        manager = ns.NotificationManager()
        assert manager._notifications
        toast = manager._notifications[-1]

        dialog.accept()
        qapp.processEvents()

        for _ in range(12):
            qapp.processEvents()
            time.sleep(0.03)

        assert toast.parent() is None
        assert toast.owner_window() is main_window
        assert toast.isVisible() is True
    finally:
        ns.NotificationManager.shutdown()
        ns.NotificationManager._instance = None
        ns.NotificationManager._app_is_quitting = False
        qapp.setProperty("_skywave_force_quit", False)
        dialog.close()
        main_window.close()
        qapp.processEvents()
