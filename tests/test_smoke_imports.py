import importlib
import os


def test_target_modules_import_cleanly():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    modules = [
        "ui.main_window",
        "ui.settings_tab",
        "ui.status_bar_widget",
        "services.accounting_service",
        "services.printing_service",
        "services.template_service",
        "ui.notification_system",
        "ui.project_manager",
        "ui.todo_manager",
    ]

    for module_name in modules:
        importlib.import_module(module_name)
