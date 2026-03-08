from __future__ import annotations

import time
from datetime import datetime, timedelta

from PyQt6.QtTest import QTest

from core import schemas
from ui import todo_manager as todo_module
from ui.todo_manager import Task, TaskEditorDialog, TaskService, TodoManagerWidget


def _wait_until(qapp, predicate, timeout_ms: int = 1500) -> bool:
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        QTest.qWait(10)
    qapp.processEvents()
    return bool(predicate())


def test_taskservice_task_to_dict_keeps_tags_as_list():
    TaskService._instance = None
    TaskService._repository = None
    service = TaskService(repository=None)
    task = Task(id="1", title="t", tags=["a", "b"])
    payload = service._task_to_dict(task)
    assert isinstance(payload["tags"], list)
    assert payload["tags"] == ["a", "b"]


def test_todo_selection_uses_task_id_not_title(qapp):
    TaskService._instance = None
    TaskService._repository = None
    service = TaskService(repository=None)
    service.tasks = [Task(id="1", title="X"), Task(id="2", title="X")]

    widget = TodoManagerWidget(project_service=None, client_service=None)
    widget.update_timer.stop()
    widget.show()
    qapp.processEvents()

    widget._load_cache_and_tasks()
    qapp.processEvents()
    assert _wait_until(qapp, lambda: widget.tasks_table.rowCount() >= 2)

    assert widget.tasks_table.rowCount() >= 2

    widget.tasks_table.selectRow(1)
    qapp.processEvents()

    assert widget.selected_task is not None
    assert widget.selected_task.id == "2"


def test_task_reminder_uses_due_time(qapp):
    TaskService._instance = None
    TaskService._repository = None
    service = TaskService(repository=None)
    service.settings.reminder_enabled = True
    service._reminder_shown.clear()

    now = datetime.now()
    due_clock = now + timedelta(minutes=5)
    task = Task(
        id="r1",
        title="rem",
        due_date=now.replace(hour=0, minute=0, second=0, microsecond=0),
        due_time=due_clock.strftime("%H:%M"),
        reminder=True,
        reminder_minutes=10,
    )
    service.tasks = [task]

    tasks = service.get_tasks_needing_reminder()
    assert len(tasks) == 1
    assert tasks[0].id == "r1"


def test_task_editor_preserves_mongo_project_and_client_refs(qapp):
    project = schemas.Project(
        id=None,
        _mongo_id="mongo-project-1",
        name="Mongo Project",
        client_id="mongo-client-1",
        total_amount=500.0,
    )
    client = schemas.Client(name="Mongo Client")
    client.id = None
    client._mongo_id = "mongo-client-1"
    task = Task(
        id="task-1",
        title="Linked Task",
        related_project="mongo-project-1",
        related_client="mongo-client-1",
    )

    project_service = type(
        "_ProjectService", (), {"get_all_projects": staticmethod(lambda: [project])}
    )()
    client_service = type(
        "_ClientService", (), {"get_all_clients": staticmethod(lambda: [client])}
    )()

    dialog = TaskEditorDialog(
        task=task, project_service=project_service, client_service=client_service
    )
    dialog.show()
    qapp.processEvents()

    assert dialog.project_combo.currentData() == "mongo-project-1"
    assert dialog.client_combo.currentData() == "mongo-client-1"

    dialog.save_task()
    assert dialog.result_task is not None
    assert dialog.result_task.related_project == "mongo-project-1"
    assert dialog.result_task.related_client == "mongo-client-1"


def test_task_editor_preserves_mongo_refs_when_local_ids_also_exist(qapp):
    project = schemas.Project(
        id=15,
        _mongo_id="mongo-project-15",
        name="Mixed Project",
        client_id="mongo-client-15",
        total_amount=500.0,
    )
    client = schemas.Client(name="Mixed Client")
    client.id = 15
    client._mongo_id = "mongo-client-15"
    task = Task(
        id="task-15",
        title="Mixed Linked Task",
        related_project="mongo-project-15",
        related_client="mongo-client-15",
    )

    project_service = type(
        "_ProjectService", (), {"get_all_projects": staticmethod(lambda: [project])}
    )()
    client_service = type(
        "_ClientService", (), {"get_all_clients": staticmethod(lambda: [client])}
    )()

    dialog = TaskEditorDialog(
        task=task, project_service=project_service, client_service=client_service
    )
    dialog.show()
    qapp.processEvents()

    assert dialog.project_combo.currentData() == "mongo-project-15"
    assert dialog.client_combo.currentData() == "mongo-client-15"

    dialog.save_task()
    assert dialog.result_task is not None
    assert dialog.result_task.related_project == "mongo-project-15"
    assert dialog.result_task.related_client == "mongo-client-15"


def test_todo_widget_displays_mongo_project_and_client_names(qapp):
    TaskService._instance = None
    TaskService._repository = None
    service = TaskService(repository=None)
    service.tasks = [
        Task(
            id="mongo-task-1",
            title="Mongo Linked",
            related_project="mongo-project-1",
            related_client="mongo-client-1",
        )
    ]

    project = schemas.Project(
        id=None,
        _mongo_id="mongo-project-1",
        name="Mongo Project",
        client_id="mongo-client-1",
        total_amount=100.0,
    )
    client = schemas.Client(name="Mongo Client")
    client.id = None
    client._mongo_id = "mongo-client-1"

    project_service = type(
        "_ProjectService", (), {"get_all_projects": staticmethod(lambda: [project])}
    )()
    client_service = type(
        "_ClientService", (), {"get_all_clients": staticmethod(lambda: [client])}
    )()

    widget = TodoManagerWidget(project_service=project_service, client_service=client_service)
    widget.update_timer.stop()
    widget.show()
    qapp.processEvents()

    widget._cache_loaded = False
    widget._load_cache_and_tasks()
    qapp.processEvents()
    assert _wait_until(qapp, lambda: widget.tasks_table.rowCount() > 0)

    assert widget._projects_cache["mongo-project-1"] == "Mongo Project"
    assert widget._clients_cache["mongo-client-1"] == "Mongo Client"
    assert widget.tasks_table.item(0, 5).text() == "Mongo Project"


def test_todo_widget_maps_mongo_refs_when_entities_also_have_local_ids(qapp):
    TaskService._instance = None
    TaskService._repository = None
    service = TaskService(repository=None)
    service.tasks = [
        Task(
            id="mixed-task-1",
            title="Mixed Linked",
            related_project="mongo-project-15",
            related_client="mongo-client-15",
        )
    ]

    project = schemas.Project(
        id=15,
        _mongo_id="mongo-project-15",
        name="Mixed Project",
        client_id="mongo-client-15",
        total_amount=100.0,
    )
    client = schemas.Client(name="Mixed Client")
    client.id = 15
    client._mongo_id = "mongo-client-15"

    project_service = type(
        "_ProjectService", (), {"get_all_projects": staticmethod(lambda: [project])}
    )()
    client_service = type(
        "_ClientService", (), {"get_all_clients": staticmethod(lambda: [client])}
    )()

    widget = TodoManagerWidget(project_service=project_service, client_service=client_service)
    widget.update_timer.stop()
    widget.show()
    qapp.processEvents()

    widget._cache_loaded = False
    widget._load_cache_and_tasks()
    qapp.processEvents()
    assert _wait_until(qapp, lambda: widget.tasks_table.rowCount() > 0)

    assert widget._projects_cache["mongo-project-15"] == "Mixed Project"
    assert widget._projects_cache["15"] == "Mixed Project"
    assert widget._clients_cache["mongo-client-15"] == "Mixed Client"
    assert widget._clients_cache["15"] == "Mixed Client"
    assert widget.tasks_table.item(0, 5).text() == "Mixed Project"


def test_todo_widget_load_tasks_uses_background_loader(qapp, monkeypatch):
    TaskService._instance = None
    TaskService._repository = None
    service = TaskService(repository=None)
    service.tasks = [Task(id="task-1", title="Async Task")]

    class _ImmediateLoader:
        def load_async(
            self,
            operation_name,
            load_function,
            *args,
            on_success=None,
            on_error=None,
            **kwargs,
        ):
            assert operation_name.startswith("todo_tasks_view_")
            try:
                result = load_function(*args)
            except Exception as exc:
                if on_error:
                    on_error(str(exc))
                return
            if on_success:
                on_success(result)

    monkeypatch.setattr(todo_module, "get_data_loader", lambda: _ImmediateLoader())

    widget = TodoManagerWidget(project_service=None, client_service=None)
    widget.update_timer.stop()
    widget.show()
    qapp.processEvents()

    monkeypatch.setattr(
        widget.task_service,
        "get_all_tasks",
        lambda: (_ for _ in ()).throw(
            AssertionError("load_tasks must not call get_all_tasks مباشرة")
        ),
    )

    widget.load_tasks()
    qapp.processEvents()
    assert _wait_until(qapp, lambda: widget.tasks_table.rowCount() == 1)

    assert widget.tasks_table.rowCount() == 1
    assert widget.tasks_table.item(0, 0).text() == "Async Task"
