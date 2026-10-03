#!/usr/bin/env python3
"""Read-only pre-commit check: version, changelog, diff whitespace and user data."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from repo_checks import git_changed_files, protected_data_paths
from version_bump import check, read_current_version

TODO = "TODO: описать изменения этого коммита."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="compare base...HEAD instead of working tree")
    parser.add_argument("--staged", action="store_true", help="check the Git index")
    parser.add_argument("--strict", action="store_true", help="fail when there are no changed files")
    args = parser.parse_args(argv)
    try:
        paths = git_changed_files(base=args.base, staged=args.staged)
    except RuntimeError as exc:
        print(f"check_release: {exc}", file=sys.stderr)
        return 2
    failures: list[str] = []
    if args.strict and not paths:
        failures.append("no changed files")
    for rel, needle in check(ROOT):
        failures.append(f"version marker: {rel}: missing {needle!r}")
    version = read_current_version(ROOT)
    summary = (ROOT / "COMPACT_SUMMARY.md").read_text(encoding="utf-8")
    section = summary.split(f"## {version}", 1)
    if len(section) != 2 or TODO in section[1].split("\n## ", 1)[0]:
        failures.append(f"COMPACT_SUMMARY.md: fill changelog for {version}")
    private = protected_data_paths(paths)
    failures.extend(f"protected user data: {path}" for path in private)
    diff_args = ["git", "diff", "--check", "--cached"] if args.staged else ["git", "diff", "--check"]
    diff = subprocess.run(diff_args, cwd=ROOT, capture_output=True, text=True, check=False)
    if diff.returncode:
        failures.append(diff.stdout.strip() or diff.stderr.strip() or "git diff --check failed")
    if failures:
        print("release check failed:", file=sys.stderr)
        print("\n".join(f"  - {item}" for item in failures), file=sys.stderr)
        return 1
    print(f"release check passed ({len(paths)} changed file(s)); version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
