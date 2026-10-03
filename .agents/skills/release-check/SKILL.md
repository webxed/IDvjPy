---
name: release-check
description: Prepare and validate an IDvjPy_term change for commit by running focused checks, synchronizing version markers, updating changelog, and guarding user data from Git.
---

# IDvjPy_term release check

Use when the user asks to prepare a commit/release or when a requested commit needs the repository's mandatory version metadata. Do not commit, push, merge, or create branches unless the user explicitly asks.

## Before commit

1. Inspect `git status --short --branch` and the diff. Preserve user work; stage only files belonging to the requested task. Never stage `.codegraph/`, local DB/history/settings, `demo_cmd.txt`, `test_ses.txt`, or local playbooks.
2. Run targeted tests for touched behavior. Prefer `python3 -m pytest tests/test_X.py tests/test_Y.py -q`, then `ruff` and `basedpyright` when installed. The full `python3 -m pytest tests/ -v` takes about 20 minutes and must only run when explicitly requested.
3. For each requested project commit, bump the minor `CommandRunner.VERSION` across project markers using `python3 bump_version.py`; inspect and replace the generated TODO under the new heading in `COMPACT_SUMMARY.md`.
4. Run `python3 bump_version.py --check`, inspect `git diff --check`, staged file list, and final status. Confirm no personal data is staged.
5. Commit with a concise message only after the user requested it. Do not push unless separately requested.

## Reporting

State the commit hash, summary, actual tests/checks run, and whether the working tree is clean. Report unavailable tools or failed checks accurately; do not claim they passed.
