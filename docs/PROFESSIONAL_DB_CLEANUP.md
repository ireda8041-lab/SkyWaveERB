# Professional DB Cleanup

This project now includes a safe cleanup tool:

- Script: `tools/professional_db_cleanup.py`
- Supports: `dry-run` (default) and `apply` mode
- Always creates a backup in apply mode
- Writes a JSON report in `reports/`

## Usage

Dry run:

```bash
python tools/professional_db_cleanup.py --db skywave_local.db
```

Apply cleanup:

```bash
python tools/professional_db_cleanup.py --db skywave_local.db --apply
```

Skip vacuum step:

```bash
python tools/professional_db_cleanup.py --db skywave_local.db --apply --skip-vacuum
```

## What it does

1. Pre-checks
- `PRAGMA integrity_check`
- `PRAGMA foreign_key_check`

2. Data fixes
- Normalize soft-delete consistency (`is_deleted=1` -> `sync_status='deleted'`)
- Canonicalize project references in:
  - `payments.project_id`
  - `expenses.project_id`
  - `invoices.project_id`
  - `tasks.related_project_id`
  - `invoice_numbers.project_name`

3. De-duplication
- Deduplicate payments by normalized signature:
  - `project_id + client_id + date(YYYY-MM-DD) + amount`
- Deduplicate expenses by normalized signature:
  - `project_id + date + amount + category + description + account_id + payment_account_id`

4. Optimization
- `PRAGMA optimize`
- `ANALYZE`
- `VACUUM` (apply mode, unless skipped)

## Safety model

- In `dry-run` mode, all changes are rolled back.
- In `apply` mode, a timestamped backup is created before any mutation.
- Duplicate removals are soft-delete when table supports `is_deleted`.
