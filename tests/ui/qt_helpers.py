from __future__ import annotations

import time
from collections.abc import Callable

from PyQt6.QtWidgets import QApplication


def pump_events(ms: int = 50) -> None:
    deadline = time.monotonic() + (ms / 1000)
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.001)


def wait_until(predicate: Callable[[], bool], timeout_ms: int = 2000, step_ms: int = 25) -> None:
    deadline = time.monotonic() + (timeout_ms / 1000)
    step_s = max(step_ms / 1000, 0.001)
    while time.monotonic() < deadline:
        if predicate():
            return
        QApplication.processEvents()
        time.sleep(step_s)
    raise TimeoutError("Condition not satisfied before timeout")
