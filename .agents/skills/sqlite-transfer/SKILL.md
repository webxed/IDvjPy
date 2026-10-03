---
name: sqlite-transfer
description: Change IDvjPy_term SQLite library behavior or JSON/CSV/Markdown import-export without creating duplicate schemas or database write paths.
---

# IDvjPy_term SQLite and transfer workflow

Use for the tag library schema, database reads/writes, backups, and import/export. Consult `AGENTS.md` and `DATABASE.md` before changing storage behavior.

## Boundaries

- `src/database_v2.py` owns low-level SQLite primitives and schema operations. Keep business-level file transfer in `src/db_transfer.py`.
- TUI `:export`/`:import`, CLI `backup_db.py`, and remote import must use the shared transfer path. For remote sources, preserve `src/remote_source.py` and the `plan_import` → `import_payload` flow. Do not add a second JSON parser, schema, or SQL insertion path.
- JSON/CSV/Markdown transfer does not carry global database IDs. Exact database snapshots use the SQLite backup mechanism (`:backup` / `backup_db.py backup`).
- Preserve soft-delete semantics (`deleted = 1`) unless the feature explicitly requires existing hard-delete behavior. Before seed replacement or destructive changes, snapshot a non-empty live DB.
- Never include live DBs, history, personal settings, or backups in Git.

## Workflow

1. Trace the relevant API and all callers with `codegraph_explore`; inspect migration/schema and transfer contracts before editing.
2. Add tests for round-trip, duplicate handling, deleted rows, IDs/tids, and failure/confirmation behavior as appropriate. Keep imports previewable/dry-run when existing UX supports it; no unconfirmed external import mutation.
3. Treat imported comments and commands as untrusted text. Do not execute imported commands or runbook steps. Preserve secret refusal/masking invariants and ensure audit records remain metadata-only.
4. Validate with focused tests such as `python3 -m pytest tests/test_db_transfer.py tests/test_remote_import.py tests/test_backup_cli.py -q`, selecting only the files relevant to the change. Do not run full `pytest tests/` unless explicitly requested.
