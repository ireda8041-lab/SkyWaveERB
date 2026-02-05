import os
import sys
import time

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _measure(label: str, fn, runs: int = 50):
    start = time.perf_counter()
    result = None
    for _ in range(runs):
        result = fn()
    total = time.perf_counter() - start
    avg_ms = (total / runs) * 1000
    print(f"{label}: {avg_ms:.2f} ms (avg over {runs})")
    return result


def main():
    import functools

    from core.event_bus import EventBus
    from core.repository import Repository
    from services.accounting_service import AccountingService

    print("== SkyWaveERP Benchmarks ==")

    repo = _measure("Repository()", Repository, runs=1)
    bus = _measure("EventBus()", EventBus, runs=1)

    svc = _measure(
        "AccountingService(repo,bus)", functools.partial(AccountingService, repo, bus), runs=1
    )

    _measure("get_dashboard_stats()", svc.get_dashboard_stats, runs=10)
    _measure(
        "get_recent_journal_entries(8)",
        functools.partial(svc.get_recent_journal_entries, 8),
        runs=10,
    )
    _measure("get_recent_activity(8)", functools.partial(svc.get_recent_activity, 8), runs=10)


if __name__ == "__main__":
    main()
