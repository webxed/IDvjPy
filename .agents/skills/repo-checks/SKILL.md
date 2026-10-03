---
name: repo-checks
description: Run IDvjPy_term focused, read-only local checks (release metadata, doc links, changed-file tests, TUI contract groups) instead of the full 25-minute pytest suite to save tokens and time. Use when validating an edit, selecting which tests to run, or preparing a commit.
---

# IDvjPy_term focused checks

Use these helpers instead of re-deriving checks by hand or running the whole test suite. They are read-only: they never write app data, the database, or the Git index. Run them from the repository root.

The scripts lives in the repo root; shared logic is in `src/repo_checks.py`. They complement the `release-check` skill (which covers the commit itself) — use this skill to pick and run the cheap checks.

## Pick the right script

| Need | Command |
|---|---|
| Version markers, changelog TODO, whitespace in diff, protected user data | `python3 check_release.py` |
| Same, but against the Git index | `python3 check_release.py --staged` |
| Local Markdown links + canonical TUI help present | `python3 check_docs.py` |
| Only links (`--links-only`) or only help (`--help-only`) | `python3 check_docs.py --links-only` |
| Minimal pytest set for the changed files | `python3 test_changed.py` |
| Run that set (and lint Python) | `python3 test_changed.py --run --lint` |
| List TUI contract groups | `python3 check_tui_contracts.py --list` |
| Plan or run selected contract groups | `python3 check_tui_contracts.py --contracts secrets,tty` / `... --run` |

Contract groups: `literal`, `secrets`, `history`, `nonblocking`, `tty`, `routing`, `input-mouse`.

## Rules

1. **Plan first, run second.** `test_changed.py` and `check_tui_contracts.py` print the plan and exit without running anything unless `--run` is passed. Run the printed files with `python3 -m pytest <files> -q` (or add `--run`), then report the real result.
2. **Never launch the full suite.** `python3 -m pytest tests/` takes ~20–25 minutes; only run it when the user explicitly asks. `test_changed.py` exists to avoid exactly that.
3. **Add `-m "not slow"`** to skip the Pilot-heavy `slow` marker unless the change touches TUI interaction. `--include-slow` / `--fast` toggles this in the scripts.
4. **Exit codes:** `0` = pass, `1` = check failed (fix the reported item), `2` = usage error or Git problem (not a code failure).
5. **When `check_release.py` fails:**
   - missing/failed version markers → `python3 bump_version.py` (then fill the generated TODO under the new `## vX.YYY` heading in `COMPACT_SUMMARY.md`), re-check with `python3 bump_version.py --check`;
   - protected user data staged → unstage it (`settings.yml`, `*.db`, `history*.txt`, `secrets_*.json`, `inbox_*.jsonl`, `session_*.pid`, `.bashrc_term*`, `.codegraph/`, `backups/`, `demo_cmd.txt`, `test_ses.txt`, `playbook.yml`);
   - whitespace errors → fix them, do not commit.
6. **When `check_docs.py` fails:** fix the relative link at the reported file. Localized docs resolve against their own directory — e.g. a root target from `docs/en/` needs `../../`, not `../`. Do not edit the Russian base to match a wrong localized path.
7. **Protected data:** `check_release.py` also lists untracked files (`git status --porcelain`), so newly created user data is caught before it is committed.
8. **`test_changed.py --strict`** fails if any changed `src/*.py` has no mapped test. If the module is intentionally untested, say so instead of weakening the check.

## Reporting

State which script(s) you ran, their exact exit result, and the failing lines if any. Do not claim a check passed unless you ran it and saw it pass. If a tool is missing (e.g. `basedpyright`), report it as skipped, not passed.
