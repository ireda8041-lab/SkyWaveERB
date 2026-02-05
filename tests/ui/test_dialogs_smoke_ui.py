from __future__ import annotations

from PyQt6.QtWidgets import QDialog


class _DummyService:
    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return None

        return _noop


def test_client_editor_dialog_instantiates(monkeypatch, qapp):
    from ui import styles

    monkeypatch.setattr(
        styles, "setup_custom_title_bar", lambda *args, **kwargs: None, raising=True
    )

    from ui.client_editor_dialog import ClientEditorDialog

    dialog = ClientEditorDialog(client_service=_DummyService())
    dialog.show()
    qapp.processEvents()
    assert isinstance(dialog, QDialog)
    dialog.reject()


def test_service_editor_dialog_instantiates(monkeypatch, qapp):
    from ui import styles

    monkeypatch.setattr(
        styles, "setup_custom_title_bar", lambda *args, **kwargs: None, raising=True
    )

    from ui.service_editor_dialog import ServiceEditorDialog

    dialog = ServiceEditorDialog(service_service=_DummyService())
    dialog.show()
    qapp.processEvents()
    assert isinstance(dialog, QDialog)
    dialog.reject()
