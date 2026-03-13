from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent, QKeySequence
from PyQt6.QtWidgets import QDialog, QLineEdit, QMainWindow

from core.keyboard_shortcuts import KeyboardShortcutManager


def _build_manager(window: QMainWindow) -> KeyboardShortcutManager:
    manager = KeyboardShortcutManager(window)
    manager._sequence_map = {
        name: QKeySequence(definition["key"])
        for name, definition in manager.shortcut_definitions.items()
    }
    return manager


def test_keyboard_shortcuts_do_not_override_copy_in_line_edit(qt_app):
    window = QMainWindow()
    line_edit = QLineEdit(window)
    line_edit.setText("SkyWave")
    line_edit.selectAll()
    window.setCentralWidget(line_edit)
    window.show()
    line_edit.setFocus()
    qt_app.processEvents()

    manager = _build_manager(window)
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_C,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert manager.eventFilter(line_edit, event) is False


def test_keyboard_shortcuts_do_not_override_select_all_in_line_edit(qt_app):
    window = QMainWindow()
    line_edit = QLineEdit(window)
    line_edit.setText("SkyWave")
    window.setCentralWidget(line_edit)
    window.show()
    line_edit.setFocus()
    qt_app.processEvents()

    manager = _build_manager(window)
    event = QKeyEvent(
        QEvent.Type.ShortcutOverride,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert manager.eventFilter(line_edit, event) is False


def test_keyboard_shortcuts_block_tab_switch_while_modal_dialog_is_open(qt_app):
    window = QMainWindow()
    dialog = QDialog(window)
    dialog.setModal(True)
    dialog.show()
    qt_app.processEvents()

    manager = _build_manager(window)

    assert manager._should_bypass_shortcut("tab_dashboard") is True
    assert manager._should_bypass_shortcut("save") is True


def test_keyboard_shortcuts_do_not_handle_global_shortcuts_while_other_dialog_is_active(qt_app):
    window = QMainWindow()
    window.show()

    dialog = QDialog(window)
    dialog.setModal(False)
    dialog.show()
    dialog.activateWindow()
    dialog.raise_()
    qt_app.processEvents()

    manager = _build_manager(window)

    assert manager._should_bypass_shortcut("save") is True
    assert manager._should_bypass_shortcut("select_all") is True
