from __future__ import annotations

from ui.client_editor_dialog import ClientEditorDialog


class _FakeClientService:
    def create_client(self, *_args, **_kwargs):
        return True

    def update_client(self, *_args, **_kwargs):
        return True


def test_client_dialog_vip_checkbox_uses_global_indicator_and_toggles(qapp):
    dialog = ClientEditorDialog(client_service=_FakeClientService())
    dialog.show()
    qapp.processEvents()

    assert dialog.vip_checkbox.isChecked() is False
    assert "QCheckBox {" in dialog.vip_checkbox.styleSheet()
    assert "QCheckBox::indicator" not in dialog.vip_checkbox.styleSheet()

    dialog.vip_checkbox.click()
    qapp.processEvents()
    assert dialog.vip_checkbox.isChecked() is True

    dialog.vip_checkbox.click()
    qapp.processEvents()
    assert dialog.vip_checkbox.isChecked() is False

    dialog.close()
