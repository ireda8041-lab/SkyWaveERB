from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
CURRENT_SITE_PACKAGES = [
    entry
    for entry in sys.path
    if entry and ("site-packages" in entry.lower() or "dist-packages" in entry.lower())
]


def _run_project_subprocess(code: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    pythonpath_parts = [str(PROJECT_ROOT)]
    if Path(sys.executable).resolve().is_relative_to((PROJECT_ROOT / ".venv").resolve()):
        pythonpath_parts.append(str(PROJECT_SITE_PACKAGES))
    else:
        pythonpath_parts.extend(CURRENT_SITE_PACKAGES)
    existing = env.get("PYTHONPATH", "")
    if existing:
        pythonpath_parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )


def test_startup_maintenance_runs_in_background(monkeypatch):
    import core.data_loader as data_loader_mod
    import core.db_maintenance as db_maintenance_mod
    import main

    events: list[str] = []

    class _FakeLoader:
        def load_async(
            self,
            operation_name,
            load_function,
            *args,
            on_success=None,
            on_error=None,
            use_thread_pool=True,
            **kwargs,
        ):
            events.append(operation_name)
            result = load_function()
            if on_success:
                on_success(result)

    monkeypatch.setattr(
        db_maintenance_mod,
        "run_monthly_maintenance_if_needed",
        lambda: events.append("maintenance") or True,
        raising=True,
    )
    monkeypatch.setattr(data_loader_mod, "get_data_loader", lambda: _FakeLoader(), raising=True)

    fake_app = type("_FakeApp", (), {"_startup_maintenance_started": False})()

    main.SkyWaveERPApp._run_startup_maintenance_if_needed(fake_app)

    assert fake_app._startup_maintenance_started is True
    assert events == ["startup_monthly_maintenance", "maintenance"]


def test_startup_maintenance_is_scheduled_once(monkeypatch):
    import core.data_loader as data_loader_mod
    import main

    class _FakeLoader:
        def load_async(self, *args, **kwargs):
            raise AssertionError("load_async should not be called twice")

    monkeypatch.setattr(data_loader_mod, "get_data_loader", lambda: _FakeLoader(), raising=True)

    fake_app = type("_FakeApp", (), {"_startup_maintenance_started": True})()

    main.SkyWaveERPApp._run_startup_maintenance_if_needed(fake_app)


def test_core_package_keeps_repository_lazy_when_importing_auth_models():
    result = _run_project_subprocess(
        "import sys; import core.auth_models; print('core.repository' in sys.modules)"
    )

    assert result.stdout.strip() == "False"


def test_core_package_lazy_exports_preserve_schemas_access():
    result = _run_project_subprocess(
        "from core import schemas; print(hasattr(schemas, 'Account') and hasattr(schemas, 'Client'))"
    )

    assert result.stdout.strip() == "True"


def test_login_services_are_initialized_lazily(monkeypatch):
    import core.auth_models as auth_models
    import core.repository as repository_module
    import main

    created: list[str] = []

    class _FakeRepository:
        def __init__(self):
            created.append("repo")

        def close(self):
            created.append("close")

    class _FakeAuthService:
        def __init__(self, repository):
            assert isinstance(repository, _FakeRepository)
            created.append("auth")

    monkeypatch.setattr(repository_module, "Repository", _FakeRepository, raising=True)
    monkeypatch.setattr(auth_models, "AuthService", _FakeAuthService, raising=True)

    app = main.SkyWaveERPApp()
    assert app.repository is None
    assert app.auth_service is None

    app._initialize_login_services()
    assert isinstance(app.repository, _FakeRepository)
    assert isinstance(app.auth_service, _FakeAuthService)
    assert created == ["repo", "auth"]

    app._initialize_login_services()
    assert created == ["repo", "auth"]


def test_dashboard_tab_import_stays_lightweight():
    result = _run_project_subprocess(
        "import sys; import ui.dashboard_tab; print('services.accounting_service' in sys.modules, 'core.repository' in sys.modules)"
    )

    assert result.stdout.strip() == "False False"


def test_accounting_service_import_keeps_schemas_lazy():
    result = _run_project_subprocess(
        "import sys; import services.accounting_service; print('core.schemas' in sys.modules)"
    )

    assert result.stdout.splitlines()[-1].strip() == "False"


def test_payments_manager_import_stays_lightweight():
    result = _run_project_subprocess(
        "import sys; import ui.payments_manager; print('services.accounting_service' in sys.modules, 'services.project_service' in sys.modules, 'services.client_service' in sys.modules, 'core.schemas' in sys.modules)"
    )

    assert result.stdout.splitlines()[-1].strip() == "False False False False"


def test_accounting_service_has_no_duplicate_active_cash_recalc_methods():
    path = Path(r"D:\blogs\appas\SkyWaveERB\services\accounting_service.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    duplicates: dict[str, list[int]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "AccountingService":
            seen: dict[str, list[int]] = {}
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith("_legacy_"):
                    seen.setdefault(item.name, []).append(item.lineno)
            duplicates = {name: lines for name, lines in seen.items() if len(lines) > 1}
            break

    assert "_recalculate_cash_balances" not in duplicates
    assert "recalculate_account_balance" not in duplicates
    assert "recalculate_cash_balances" not in duplicates
