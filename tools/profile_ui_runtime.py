from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt6.QtWidgets import QApplication  # pylint: disable=wrong-import-position

from ui.dashboard_tab import DashboardTab  # pylint: disable=wrong-import-position
from ui.login_window import LoginWindow  # pylint: disable=wrong-import-position
from ui.settings_tab import SettingsTab  # pylint: disable=wrong-import-position


class _StubAuthService:
    def authenticate(self, username: str, password: str):
        return None


class _StubSettingsService:
    def __init__(self):
        self._settings = {}

    def get_settings(self):
        return dict(self._settings)

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def update_settings(self, data):
        self._settings.update(data or {})

    def update_setting(self, key, value):
        self._settings[key] = value

    def save_logo_from_file(self, _path: str) -> bool:
        return False

    def get_logo_as_pixmap(self):
        return None


class _StubAccountingService:
    def get_dashboard_stats(self):
        return {
            "monthly_sales": 0,
            "monthly_expenses": 0,
            "net_profit": 0,
            "active_projects": 0,
            "new_clients": 0,
        }

    def get_recent_journal_entries(self, limit: int = 8):
        return []

    def get_recent_activity(self, limit: int = 8):
        return []


def _measure_widget(factory, app: QApplication, runs: int = 5) -> dict:
    durations = []
    for _ in range(runs):
        start = time.perf_counter()
        widget = factory()
        durations.append((time.perf_counter() - start) * 1000)
        widget.deleteLater()
        app.processEvents()
    return {
        "avg_ms": round(sum(durations) / len(durations), 2),
        "min_ms": round(min(durations), 2),
        "max_ms": round(max(durations), 2),
        "runs": runs,
    }


def main() -> int:
    app = QApplication.instance() or QApplication([])

    results = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "screens": {
            "LoginWindow": _measure_widget(lambda: LoginWindow(_StubAuthService()), app),
            "SettingsTab": _measure_widget(
                lambda: SettingsTab(
                    settings_service=_StubSettingsService(),
                    repository=None,
                    current_user=None,
                ),
                app,
            ),
            "DashboardTab": _measure_widget(
                lambda: DashboardTab(_StubAccountingService()),
                app,
            ),
        },
    }
    results["ranked"] = sorted(
        ({"screen": screen_name, **metrics} for screen_name, metrics in results["screens"].items()),
        key=lambda item: item["avg_ms"],
        reverse=True,
    )

    out_dir = Path("docs/perf")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ui_runtime_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] UI runtime profile written: {out_path}")
    for item in results["ranked"]:
        print(
            f"{item['screen']}: avg={item['avg_ms']} ms "
            f"min={item['min_ms']} ms max={item['max_ms']} ms"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
