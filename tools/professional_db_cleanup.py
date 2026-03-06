from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

WS_RE = re.compile(r"\s+")
ARABIC_FOLD = str.maketrans(
    {
        "\u0623": "\u0627",  # Alif with hamza above -> Alif
        "\u0625": "\u0627",  # Alif with hamza below -> Alif
        "\u0622": "\u0627",  # Alif madda -> Alif
        "\u0649": "\u064a",  # Alif maqsura -> Ya
        "\u0624": "\u0648",  # Waw with hamza -> Waw
        "\u0626": "\u064a",  # Ya with hamza -> Ya
    }
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return WS_RE.sub(" ", str(value)).strip()


def project_key(value: Any) -> str:
    return normalize_text(value).translate(ARABIC_FOLD).casefold().strip()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    row = cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row and int(row[0]) > 0)


def table_columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    if not table_exists(cur, table):
        return set()
    rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def active_where(columns: set[str]) -> str:
    filters: list[str] = []
    if "sync_status" in columns:
        filters.append("(sync_status != 'deleted' OR sync_status IS NULL)")
    if "is_deleted" in columns:
        filters.append("(is_deleted = 0 OR is_deleted IS NULL)")
    return " AND ".join(filters) if filters else "1=1"


def parse_count(cur: sqlite3.Cursor, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = cur.execute(sql, params).fetchone()
    return int(row[0] if row else 0)


def collect_table_state(cur: sqlite3.Cursor, table: str) -> dict[str, int]:
    cols = table_columns(cur, table)
    if not cols:
        return {"total": 0, "active": 0, "deleted": 0}

    total = parse_count(cur, f"SELECT COUNT(*) FROM {table}")
    active = parse_count(cur, f"SELECT COUNT(*) FROM {table} WHERE {active_where(cols)}")
    deleted = (
        parse_count(cur, f"SELECT COUNT(*) FROM {table} WHERE is_deleted = 1")
        if "is_deleted" in cols
        else 0
    )
    return {"total": total, "active": active, "deleted": deleted}


def payment_duplicate_rows(cur: sqlite3.Cursor) -> int:
    cols = table_columns(cur, "payments")
    if not cols:
        return 0

    rows = cur.execute(
        f"""
        SELECT id, project_id, client_id, date, amount
        FROM payments
        WHERE {active_where(cols)}
        """
    ).fetchall()
    grouped: dict[tuple[str, str, float, str], list[int]] = defaultdict(list)
    for r in rows:
        signature = (
            project_key(r[1]),
            str(r[3] or "")[:10],
            round(float(r[4] or 0.0), 2),
            project_key(r[2]),
        )
        grouped[signature].append(int(r[0]))
    return sum(len(v) - 1 for v in grouped.values() if len(v) > 1)


def expense_duplicate_rows(cur: sqlite3.Cursor) -> int:
    cols = table_columns(cur, "expenses")
    if not cols:
        return 0

    rows = cur.execute(
        f"""
        SELECT id, project_id, date, amount, category, description, account_id, payment_account_id
        FROM expenses
        WHERE {active_where(cols)}
        """
    ).fetchall()
    grouped: dict[tuple[str, str, float, str, str, str, str], list[int]] = defaultdict(list)
    for r in rows:
        amount = round(float(r[3] or 0.0), 2)
        account_id = normalize_text(r[6])
        payment_account_id = normalize_text(r[7]) or account_id
        signature = (
            project_key(r[1]),
            str(r[2] or "")[:10],
            amount,
            normalize_text(r[4]).casefold(),
            normalize_text(r[5]).casefold(),
            account_id.casefold(),
            payment_account_id.casefold(),
        )
        grouped[signature].append(int(r[0]))
    return sum(len(v) - 1 for v in grouped.values() if len(v) > 1)


def collect_overview(cur: sqlite3.Cursor) -> dict[str, Any]:
    tracked_tables = [
        "projects",
        "payments",
        "expenses",
        "clients",
        "accounts",
        "journal_entries",
        "invoice_numbers",
        "tasks",
    ]
    return {
        "tables": {table: collect_table_state(cur, table) for table in tracked_tables},
        "payment_duplicate_rows_normalized": payment_duplicate_rows(cur),
        "expense_duplicate_rows_normalized": expense_duplicate_rows(cur),
    }


@dataclass(frozen=True)
class ProjectRow:
    id: int
    name: str
    client_id: str
    mongo_id: str
    project_code: str


class ProjectResolver:
    def __init__(self, cur: sqlite3.Cursor) -> None:
        cols = table_columns(cur, "projects")
        if not cols:
            self.projects: list[ProjectRow] = []
            self.by_name: dict[str, ProjectRow] = {}
            self.by_id: dict[str, ProjectRow] = {}
            self.by_mongo: dict[str, ProjectRow] = {}
            self.by_code: dict[str, list[ProjectRow]] = {}
            self.by_key: dict[str, list[ProjectRow]] = {}
            return

        rows = cur.execute(
            f"""
            SELECT id, name, COALESCE(client_id, ''), COALESCE(_mongo_id, ''), COALESCE(project_code, '')
            FROM projects
            WHERE {active_where(cols)}
            """
        ).fetchall()

        projects = [
            ProjectRow(
                id=int(r[0]),
                name=str(r[1] or ""),
                client_id=str(r[2] or ""),
                mongo_id=str(r[3] or ""),
                project_code=str(r[4] or ""),
            )
            for r in rows
            if str(r[1] or "").strip()
        ]
        self.projects = projects
        self.by_name = {p.name: p for p in projects}
        self.by_id = {str(p.id): p for p in projects}
        self.by_mongo = {p.mongo_id: p for p in projects if p.mongo_id}
        self.by_code = defaultdict(list)
        self.by_key = defaultdict(list)
        for p in projects:
            if p.project_code:
                self.by_code[p.project_code].append(p)
            self.by_key[project_key(p.name)].append(p)

    def resolve(self, ref: Any, client_id: Any = "") -> ProjectRow | None:
        raw = str(ref or "")
        if not raw:
            return None

        candidate = normalize_text(raw)
        client_k = project_key(client_id)

        if raw in self.by_name:
            return self.by_name[raw]
        if candidate in self.by_name:
            return self.by_name[candidate]
        if candidate in self.by_id:
            return self.by_id[candidate]
        if candidate in self.by_mongo:
            return self.by_mongo[candidate]

        if candidate in self.by_code:
            code_matches = self.by_code[candidate]
            if len(code_matches) == 1:
                return code_matches[0]
            if client_k:
                filtered = [p for p in code_matches if project_key(p.client_id) == client_k]
                if len(filtered) == 1:
                    return filtered[0]

        matches = self.by_key.get(project_key(candidate), [])
        if len(matches) == 1:
            return matches[0]
        if client_k:
            filtered = [p for p in matches if project_key(p.client_id) == client_k]
            if len(filtered) == 1:
                return filtered[0]
        return None


def normalize_soft_deleted_sync_status(cur: sqlite3.Cursor, table: str, now: str) -> int:
    cols = table_columns(cur, table)
    if "is_deleted" not in cols or "sync_status" not in cols:
        return 0

    updates: list[str] = ["sync_status = 'deleted'"]
    params: list[Any] = []
    if "dirty_flag" in cols:
        updates.append("dirty_flag = 1")
    if "last_modified" in cols:
        updates.append("last_modified = ?")
        params.append(now)

    sql = f"""
        UPDATE {table}
        SET {', '.join(updates)}
        WHERE is_deleted = 1
          AND (sync_status IS NULL OR sync_status != 'deleted')
    """
    cur.execute(sql, tuple(params))
    return int(cur.rowcount or 0)


def _update_row_with_project_ref(
    cur: sqlite3.Cursor,
    table: str,
    row_id: int,
    id_col: str,
    ref_col: str,
    new_ref: str,
    now: str,
) -> None:
    cols = table_columns(cur, table)
    set_parts = [f"{ref_col} = ?"]
    params: list[Any] = [new_ref]
    if "last_modified" in cols:
        set_parts.append("last_modified = ?")
        params.append(now)
    if "dirty_flag" in cols:
        set_parts.append("dirty_flag = 1")
    if "sync_status" in cols:
        set_parts.append(
            "sync_status = CASE "
            "WHEN sync_status IN ('new_offline', 'new') THEN sync_status "
            "ELSE 'modified_offline' END"
        )
    params.append(row_id)
    cur.execute(
        f"UPDATE {table} SET {', '.join(set_parts)} WHERE {id_col} = ?",
        tuple(params),
    )


def canonicalize_project_references(
    cur: sqlite3.Cursor,
    resolver: ProjectResolver,
    table: str,
    id_col: str,
    ref_col: str,
    client_col: str | None,
    now: str,
) -> dict[str, int]:
    cols = table_columns(cur, table)
    if not cols or id_col not in cols or ref_col not in cols:
        return {"scanned": 0, "updated": 0, "unresolved": 0}

    select_cols = [id_col, ref_col]
    if client_col and client_col in cols:
        select_cols.append(client_col)
    query = f"SELECT {', '.join(select_cols)} FROM {table} WHERE {active_where(cols)}"
    rows = cur.execute(query).fetchall()

    scanned = 0
    updated = 0
    unresolved = 0

    for row in rows:
        row_map = {select_cols[i]: row[i] for i in range(len(select_cols))}
        raw_ref = str(row_map.get(ref_col) or "")
        if not raw_ref.strip():
            continue

        scanned += 1
        client_value = str(row_map.get(client_col or "") or "")
        resolved = resolver.resolve(raw_ref, client_value)
        if not resolved:
            unresolved += 1
            continue

        canonical = resolved.name
        if canonical != raw_ref:
            _update_row_with_project_ref(
                cur=cur,
                table=table,
                row_id=int(row_map[id_col]),
                id_col=id_col,
                ref_col=ref_col,
                new_ref=canonical,
                now=now,
            )
            updated += 1

    return {"scanned": scanned, "updated": updated, "unresolved": unresolved}


def _soft_delete_ids(
    cur: sqlite3.Cursor,
    table: str,
    id_col: str,
    ids: list[int],
    now: str,
) -> int:
    if not ids:
        return 0

    cols = table_columns(cur, table)
    placeholders = ", ".join("?" for _ in ids)
    if "is_deleted" in cols:
        updates = ["is_deleted = 1"]
        params: list[Any] = []
        if "sync_status" in cols:
            updates.append("sync_status = 'deleted'")
        if "dirty_flag" in cols:
            updates.append("dirty_flag = 1")
        if "last_modified" in cols:
            updates.append("last_modified = ?")
            params.append(now)
        sql = f"UPDATE {table} SET {', '.join(updates)} WHERE {id_col} IN ({placeholders})"
        cur.execute(sql, tuple(params + ids))
        return int(cur.rowcount or 0)

    cur.execute(f"DELETE FROM {table} WHERE {id_col} IN ({placeholders})", tuple(ids))
    return int(cur.rowcount or 0)


def deduplicate_payments(cur: sqlite3.Cursor, now: str) -> dict[str, int]:
    cols = table_columns(cur, "payments")
    if not cols:
        return {"groups": 0, "removed": 0}

    rows = cur.execute(
        f"""
        SELECT id, _mongo_id, project_id, client_id, date, amount, created_at
        FROM payments
        WHERE {active_where(cols)}
        ORDER BY COALESCE(created_at, ''), id
        """
    ).fetchall()

    grouped: dict[tuple[str, str, float, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        signature = (
            project_key(row[2]),
            str(row[4] or "")[:10],
            round(float(row[5] or 0.0), 2),
            project_key(row[3]),
        )
        grouped[signature].append(row)

    removed_ids: list[int] = []
    duplicate_groups = 0
    for items in grouped.values():
        if len(items) <= 1:
            continue
        duplicate_groups += 1
        ordered = sorted(
            items,
            key=lambda r: (
                0 if str(r[1] or "").strip() else 1,  # prefer cloud-linked row
                str(r[6] or ""),
                int(r[0]),
            ),
        )
        for row in ordered[1:]:
            removed_ids.append(int(row[0]))

    removed = _soft_delete_ids(
        cur=cur,
        table="payments",
        id_col="id",
        ids=removed_ids,
        now=now,
    )
    return {"groups": duplicate_groups, "removed": removed}


def deduplicate_expenses(cur: sqlite3.Cursor, now: str) -> dict[str, int]:
    cols = table_columns(cur, "expenses")
    if not cols:
        return {"groups": 0, "removed": 0}

    rows = cur.execute(
        f"""
        SELECT id, _mongo_id, project_id, date, amount, category, description, account_id,
               payment_account_id, created_at
        FROM expenses
        WHERE {active_where(cols)}
        ORDER BY COALESCE(created_at, ''), id
        """
    ).fetchall()

    grouped: dict[tuple[str, str, float, str, str, str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        amount = round(float(row[4] or 0.0), 2)
        account = normalize_text(row[7])
        payment_account = normalize_text(row[8]) or account
        signature = (
            project_key(row[2]),
            str(row[3] or "")[:10],
            amount,
            normalize_text(row[5]).casefold(),
            normalize_text(row[6]).casefold(),
            account.casefold(),
            payment_account.casefold(),
        )
        grouped[signature].append(row)

    removed_ids: list[int] = []
    duplicate_groups = 0
    for items in grouped.values():
        if len(items) <= 1:
            continue
        duplicate_groups += 1
        ordered = sorted(
            items,
            key=lambda r: (
                0 if str(r[1] or "").strip() else 1,  # prefer cloud-linked row
                str(r[9] or ""),
                int(r[0]),
            ),
        )
        for row in ordered[1:]:
            removed_ids.append(int(row[0]))

    removed = _soft_delete_ids(
        cur=cur,
        table="expenses",
        id_col="id",
        ids=removed_ids,
        now=now,
    )
    return {"groups": duplicate_groups, "removed": removed}


def run_cleanup(
    db_path: Path,
    apply: bool,
    backup_dir: Path,
    report_dir: Path,
    vacuum: bool,
) -> dict[str, Any]:
    start_ts = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    ensure_dir(backup_dir)
    ensure_dir(report_dir)

    report: dict[str, Any] = {
        "timestamp": timestamp,
        "db_path": str(db_path.resolve()),
        "mode": "apply" if apply else "dry_run",
        "backup_path": None,
        "prechecks": {},
        "actions": {},
        "before": {},
        "after_preview": {},
        "after_applied": {},
        "duration_seconds": 0.0,
    }

    if apply:
        backup_path = (
            backup_dir / f"{db_path.stem}_professional_cleanup_{timestamp}{db_path.suffix}"
        )
        shutil.copy2(db_path, backup_path)
        report["backup_path"] = str(backup_path.resolve())

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        report["before"] = collect_overview(cur)
        report["prechecks"]["integrity_check"] = [
            r[0] for r in cur.execute("PRAGMA integrity_check")
        ]
        report["prechecks"]["foreign_key_check"] = [
            list(r) for r in cur.execute("PRAGMA foreign_key_check").fetchall()
        ]

        now = now_iso()
        cur.execute("BEGIN IMMEDIATE")

        # Step 1: Normalize soft-delete consistency
        tables = [
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        normalized_sync_rows = 0
        for table in tables:
            normalized_sync_rows += normalize_soft_deleted_sync_status(cur, table, now)
        report["actions"]["normalize_soft_delete_sync"] = {"updated_rows": normalized_sync_rows}

        # Step 2: Canonicalize project references across dependent tables
        resolver = ProjectResolver(cur)
        canonical_targets = [
            ("payments", "id", "project_id", "client_id"),
            ("expenses", "id", "project_id", None),
            ("invoices", "id", "project_id", "client_id"),
            ("tasks", "id", "related_project_id", None),
            ("invoice_numbers", "id", "project_name", None),
        ]
        canonicalize_report: dict[str, dict[str, int]] = {}
        for table, id_col, ref_col, client_col in canonical_targets:
            canonicalize_report[table] = canonicalize_project_references(
                cur=cur,
                resolver=resolver,
                table=table,
                id_col=id_col,
                ref_col=ref_col,
                client_col=client_col,
                now=now,
            )
        report["actions"]["canonicalize_project_refs"] = canonicalize_report

        # Step 3: Deduplicate payments and expenses using normalized signatures
        report["actions"]["deduplicate_payments"] = deduplicate_payments(cur, now)
        report["actions"]["deduplicate_expenses"] = deduplicate_expenses(cur, now)

        # Step 4: Analyze stats after mutations (preview)
        report["after_preview"] = collect_overview(cur)
        cur.execute("PRAGMA optimize")
        cur.execute("ANALYZE")

        if apply:
            conn.commit()
            if vacuum:
                cur.execute("VACUUM")
            report["after_applied"] = collect_overview(cur)
        else:
            conn.rollback()
            report["after_applied"] = report["before"]

        return report
    finally:
        report["duration_seconds"] = round(time.time() - start_ts, 3)
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Professional safe cleanup for SkyWaveERP SQLite database."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("skywave_local.db"),
        help="Path to SQLite database (default: ./skywave_local.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag, the tool runs in dry-run mode.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path("backups"),
        help="Directory for backup files in apply mode.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports"),
        help="Directory where JSON report is written.",
    )
    parser.add_argument(
        "--skip-vacuum",
        action="store_true",
        help="Skip VACUUM after apply.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path: Path = args.db
    if not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}")
        return 1

    report = run_cleanup(
        db_path=db_path,
        apply=bool(args.apply),
        backup_dir=args.backup_dir,
        report_dir=args.report_dir,
        vacuum=not bool(args.skip_vacuum),
    )

    report_dir = args.report_dir
    ensure_dir(report_dir)
    ts = report["timestamp"]
    mode = report["mode"]
    report_path = report_dir / f"db_cleanup_report_{mode}_{ts}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    before = report.get("before", {})
    after = report.get("after_preview", {})
    print(f"[OK] Cleanup mode: {mode}")
    print(f"[OK] Database: {report.get('db_path')}")
    if report.get("backup_path"):
        print(f"[OK] Backup: {report.get('backup_path')}")
    print(f"[OK] Report: {report_path.resolve()}")
    print(
        "[SUMMARY] Payments duplicates (normalized): "
        f"{before.get('payment_duplicate_rows_normalized')} -> "
        f"{after.get('payment_duplicate_rows_normalized')}"
    )
    print(
        "[SUMMARY] Expenses duplicates (normalized): "
        f"{before.get('expense_duplicate_rows_normalized')} -> "
        f"{after.get('expense_duplicate_rows_normalized')}"
    )
    print("[SUMMARY] Duration seconds: " f"{report.get('duration_seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
