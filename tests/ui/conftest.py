import os

import pytest
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox


@pytest.fixture(autouse=True, scope="session")
def _configure_headless_qt(tmp_path_factory):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SKYWAVEERP_DATA_DIR", str(tmp_path_factory.mktemp("skywave_data")))
    os.environ.setdefault("MPLBACKEND", "Agg")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _avoid_blocking_dialogs(monkeypatch):
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
        raising=False,
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
        raising=False,
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
        raising=False,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
        raising=False,
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("", ""), raising=False
    )
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args, **kwargs: ("", ""), raising=False
    )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args, **kwargs: "", raising=False
    )


@pytest.fixture()
def disable_repository_mongo(monkeypatch):
    try:
        from core.repository import Repository
    except Exception:
        return

    monkeypatch.setattr(Repository, "_start_mongo_connection", lambda self: None, raising=True)


@pytest.fixture()
def sqlite_repo(tmp_path, monkeypatch, disable_repository_mongo):
    import core.repository as repo_mod

    db_path = tmp_path / "skywave_test.db"
    monkeypatch.setattr(repo_mod, "LOCAL_DB_FILE", str(db_path), raising=True)

    repo = repo_mod.Repository()
    try:
        yield repo
    finally:
        repo.close()
