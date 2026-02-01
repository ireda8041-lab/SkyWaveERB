from core.data_loader import DataLoaderRunnable


def test_data_loader_cancel_prevents_execution_and_signal(qt_app):
    called = []
    finished = []

    def load_function(is_cancelled):
        called.append(True)
        return 123

    runnable = DataLoaderRunnable(load_function)
    runnable.signals.finished.connect(lambda value: finished.append(value))

    runnable.cancel()
    runnable.run()

    assert called == []
    assert finished == []
