import json
import os
import sys
import time
import tracemalloc
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)


@dataclass
class Sample:
    name: str
    ms: float
    peak_kb: int
    extra: dict


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _measure(name: str, fn, extra: dict | None = None) -> Sample:
    extra = extra or {}
    tracemalloc.start()
    start = time.perf_counter()
    value = fn()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_kb = int(peak / 1024)
    if value is not None and "result" not in extra:
        if isinstance(value, (int, float, str, bool)):
            extra["result"] = value
        elif isinstance(value, (list, tuple, dict, set)):
            extra["result_size"] = len(value)
    return Sample(name=name, ms=elapsed_ms, peak_kb=peak_kb, extra=extra)


def _write_report(samples: list[Sample], out_path: Path) -> Path:
    payload = {
        "generated_at": datetime.now().isoformat(),
        "samples": [
            {"name": s.name, "ms": s.ms, "peak_kb": s.peak_kb, "extra": s.extra} for s in samples
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from core.event_bus import EventBus
    from core.repository import Repository
    from services.accounting_service import AccountingService

    samples: list[Sample] = []

    repo = _measure("Repository()", lambda: Repository(), extra={"runs": 1})
    samples.append(repo)

    repository = Repository()
    bus = EventBus()
    svc = AccountingService(repository, bus)

    samples.append(_measure("repo.get_all_accounts()", repository.get_all_accounts))
    samples.append(_measure("repo.get_all_payments()", repository.get_all_payments))
    samples.append(_measure("repo.get_all_expenses()", repository.get_all_expenses))
    samples.append(_measure("repo.get_all_journal_entries()", repository.get_all_journal_entries))

    samples.append(_measure("svc.get_dashboard_stats()", svc.get_dashboard_stats))
    samples.append(_measure("svc.get_recent_activity(8)", lambda: svc.get_recent_activity(8)))

    accounts = repository.get_all_accounts()
    account_code = None
    for a in accounts:
        code = getattr(a, "code", None)
        if code and str(code).startswith("111") and not str(code).endswith("000"):
            account_code = str(code)
            break
    if not account_code and accounts:
        account_code = str(accounts[0].code)

    if account_code:
        end = datetime.now()
        start = end - timedelta(days=60)
        samples.append(
            _measure(
                "svc.get_account_ledger_report(60d)",
                lambda: svc.get_account_ledger_report(account_code, start, end),
                extra={"account_code": account_code},
            )
        )

    out = Path("docs") / "perf" / f"perf_{_now_tag()}.json"
    out_path = _write_report(samples, out)

    print(f"[OK] Perf report written: {out_path.as_posix()}")
    for s in samples:
        print(f"{s.name}: {s.ms:.2f} ms, peak={s.peak_kb} KB, extra={s.extra}")


if __name__ == "__main__":
    main()
