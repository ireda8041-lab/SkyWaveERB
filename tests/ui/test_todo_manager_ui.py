from __future__ import annotations

from datetime import datetime, timedelta

from ui.todo_manager import Task, TaskService, TodoManagerWidget


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
