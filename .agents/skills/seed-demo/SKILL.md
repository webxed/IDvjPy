---
name: seed-demo
description: Add or update IDvjPy_term seed handbooks and demo tours with safe real-tool examples, localized text, backup behavior, and focused tests.
---

# IDvjPy_term seeds and demos

Use for `src/seed_*.py`, bundled demos in `src/demos/`, localized seed/demo content, and handbook documentation. Follow `AGENTS.md` before changes; it defines seed ownership, backup, and safe-runbook rules.

## Seed workflow

1. Inspect the target seed module, its tests, `src/seed_groups.py`, and `src/seed_text/README.md`. Never overwrite another handbook's tags.
2. Seed scripts must replace only their own tag set. Preserve backup-before-mutation behavior; do not snapshot an empty DB. A combined seed should create at most one backup.
3. Show real DevOps utilities and explain their command/flags/output. Prefer inspect/read-only examples. Do not hide tools behind project-specific wrappers.
4. Keep built-in Russian comments in `src/seed_*.py` as the base layer. Put translated comments in `src/seed_text/<lang>/<handbook>.yml`; retain exact tag names and command-position keys. Run `:relang`/localization tests when relevant.
5. Mutating steps in a `:run` chain must be marked `run:manual`; do not add installs, deletes, chmod mutations, unbounded loops, or interactive TTY commands to bundled tours. Keep bundled `short`, `full`, and `ip` tours finite.

## Demo workflow

1. Keep base tour structure in `src/demos/*.yml`; localize text in `src/demos/text/<lang>/` without changing command semantics.
2. Do not put `> htop`/other TTY commands into YAML demos. Do not put `:q` mid-tour when the output tail should be recorded; use `--demo-quit` only for final exit behavior.
3. Add/update tests in `tests/test_seed_*.py`, `tests/test_demo.py`, or `tests/test_demo_i18n.py`, plus the matching docs under `docs/` when user-visible behavior changes.
4. Run only affected tests, e.g. `python3 -m pytest tests/test_seed_git.py tests/test_seed_i18n.py -q` or the corresponding demo tests. Do not run the full suite without an explicit request.
