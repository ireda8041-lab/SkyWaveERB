from core.signals import app_signals


class _FakeSyncManager:
    def __init__(self):
        self.pings: list[str] = []
        self.scheduled: list[str] = []

    def emit_sync_ping_for_table(self, table_name: str):
        self.pings.append(str(table_name))
        return True

    def schedule_instant_sync(self, table_name: str):
        self.scheduled.append(str(table_name))
        return True


def test_emit_data_changed_triggers_ping_and_instant_sync():
    manager = _FakeSyncManager()
    app_signals.set_sync_manager(manager)
    app_signals._last_emitted.clear()  # type: ignore[attr-defined]

    app_signals.emit_data_changed("services")

    assert manager.pings == ["services"]
    assert manager.scheduled == ["services"]


def test_emit_ui_data_changed_does_not_trigger_sync_side_effects():
    manager = _FakeSyncManager()
    app_signals.set_sync_manager(manager)
    app_signals._last_emitted.clear()  # type: ignore[attr-defined]

    app_signals.emit_ui_data_changed("services")

    assert manager.pings == []
    assert manager.scheduled == []
