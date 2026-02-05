from core.data_loader import DataLoaderRunnable


def test_data_loader_cancel_prevents_execution_and_signal(qt_app):
    called = []
    finished = []

    def load_function(is_cancelled):
        called.append(True)
        return 123

    runnable = DataLoaderRunnable(load_function)

    def _on_finished(value):
        finished.append(value)

    runnable.signals.finished.connect(_on_finished)

    runnable.cancel()
    runnable.run()

    assert not called
    assert not finished
