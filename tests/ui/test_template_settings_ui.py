from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget


def test_template_settings_lazily_initializes_template_tools(monkeypatch, qapp):
    from ui import template_settings as template_module

    events: list[str] = []

    class _FakeTemplateService:
        def __init__(self, repository, settings_service):
            events.append("service_init")

        @staticmethod
        def get_all_templates():
            return [{"id": 1, "name": "Default", "is_default": True}]

        @staticmethod
        def get_default_template():
            return {"id": 1, "name": "Default", "is_default": True}

    class _FakeTemplateManager(QWidget):
        template_changed = pyqtSignal()

        def __init__(self, template_service):
            super().__init__()
            events.append("manager_init")

    monkeypatch.setattr(template_module, "TemplateService", _FakeTemplateService, raising=True)
    monkeypatch.setattr(template_module, "TemplateManager", _FakeTemplateManager, raising=True)

    settings_service = type("_Settings", (), {"repo": object()})()
    widget = template_module.TemplateSettings(settings_service)

    assert events == []

    widget.show()
    qapp.processEvents()

    assert events == ["service_init", "manager_init"]
    assert widget.templates_count_label.text() == "عدد القوالب: 1"
    assert widget.default_template_label.text() == "القالب الافتراضي: Default"
