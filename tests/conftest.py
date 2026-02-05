from unittest.mock import MagicMock

import pytest

try:
    from PyQt6.QtWidgets import QApplication
except Exception:
    QApplication = None


@pytest.fixture(autouse=True)
def _disable_mongo_for_tests(monkeypatch):
    monkeypatch.setenv("SKYWAVE_DISABLE_MONGO", "1")
    yield


@pytest.fixture(scope="session")
def qt_app():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if QApplication is None:
        return None
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture()
def mock_event_bus():
    bus = MagicMock()
    bus.subscribe = MagicMock()
    bus.publish = MagicMock()
    return bus


@pytest.fixture()
def mock_repo():
    repo = MagicMock()
    repo.online = False
    repo.get_all_payments.return_value = []
    repo.get_all_expenses.return_value = []
    repo.get_all_journal_entries.return_value = []
    repo.sum_payments_before.return_value = 0.0
    repo.sum_expenses_paid_before.return_value = 0.0
    repo.sum_expenses_charged_before.return_value = 0.0
    repo.get_journal_entries_before.return_value = []
    repo.get_journal_entries_between.return_value = []
    repo.get_payments_by_account.return_value = []
    repo.get_expenses_paid_from_account.return_value = []
    repo.get_expenses_charged_to_account.return_value = []
    return repo


@pytest.fixture()
def sample_client_data():
    from core import schemas

    return schemas.Client(name="Test Client", phone="01000000000", email="t@example.com")
