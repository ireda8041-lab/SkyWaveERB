from __future__ import annotations

import os

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


def test_toast_notification_instantiates(qapp):
    from ui import notification_system as ns

    toast = ns.ToastNotification(message="Hello", duration=10)
    toast.show()
    qapp.processEvents()
    toast.close()
