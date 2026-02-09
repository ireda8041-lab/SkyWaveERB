from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    title: str
    details: str


def _safe_print(line: str) -> None:
    """Print defensively on Windows consoles that cannot encode Unicode text."""
    encoding = sys.stdout.encoding or "utf-8"
    try:
        safe_line = line.encode(encoding, errors="replace").decode(encoding, errors="replace")
    except Exception:
        safe_line = line.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    print(safe_line, flush=True)


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=10.0)


def _single_value(cur: sqlite3.Cursor, sql: str) -> str | None:
    cur.execute(sql)
    row = cur.fetchone()
    return str(row[0]) if row and row[0] is not None else None


def audit(db_path: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    if not db_path.exists():
        return [
            CheckResult(
                ok=False,
                title="ملف قاعدة البيانات غير موجود",
                details=str(db_path),
            )
        ]

    try:
        conn = _connect_readonly(db_path)
    except sqlite3.Error as e:
        return [
            CheckResult(
                ok=False,
                title="فشل فتح قاعدة البيانات",
                details=str(e),
            )
        ]

    try:
        cur = conn.cursor()

        integrity = _single_value(cur, "PRAGMA integrity_check;")
        results.append(
            CheckResult(
                ok=(integrity == "ok"),
                title="PRAGMA integrity_check",
                details=integrity or "بدون نتيجة",
            )
        )

        cur.execute("PRAGMA foreign_key_check;")
        fk_rows = cur.fetchall()
        if fk_rows:
            details = "\n".join(str(r) for r in fk_rows[:50])
            if len(fk_rows) > 50:
                details += f"\n... ({len(fk_rows) - 50} صف إضافي)"
            results.append(
                CheckResult(
                    ok=False,
                    title="PRAGMA foreign_key_check",
                    details=details,
                )
            )
        else:
            results.append(
                CheckResult(
                    ok=True,
                    title="PRAGMA foreign_key_check",
                    details="لا توجد مخالفات.",
                )
            )

        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
        )
        tables = [r[0] for r in cur.fetchall()]
        results.append(
            CheckResult(
                ok=True,
                title="عدد الجداول",
                details=str(len(tables)),
            )
        )

        missing_indexes: list[str] = []
        for table in tables:
            cur.execute(f"PRAGMA index_list('{table}');")
            idx = cur.fetchall()
            if not idx:
                missing_indexes.append(table)

        if missing_indexes:
            results.append(
                CheckResult(
                    ok=True,
                    title="جداول بلا فهارس (للمراجعة)",
                    details=", ".join(missing_indexes),
                )
            )

    finally:
        conn.close()

    return results


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        db_path = Path(argv[1]).resolve()
    else:
        db_path = Path("skywave_local.db").resolve()

    results = audit(db_path)

    _safe_print(f"SQLite audit: {db_path}")
    exit_code = 0
    for r in results:
        status = "OK" if r.ok else "FAIL"
        _safe_print(f"- {status}: {r.title}")
        if r.details:
            for line in str(r.details).splitlines():
                _safe_print(f"  {line}")
        if not r.ok:
            exit_code = 2

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
