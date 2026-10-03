#!/usr/bin/env python3
"""Plan or run focused Textual TUI contract tests; default is plan-only."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from repo_checks import TUI_CONTRACT_GROUPS, unique


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", help="comma-separated groups")
    parser.add_argument("--fast", action="store_true", help="exclude pytest slow marker")
    parser.add_argument("--list", action="store_true", help="list groups and exit")
    parser.add_argument("--run", action="store_true", help="run the selected focused tests")
    args = parser.parse_args(argv)
    if args.list:
        for name, tests in TUI_CONTRACT_GROUPS.items():
            print(f"{name}:\n  " + "\n  ".join(tests))
        return 0
    names = args.contracts.split(",") if args.contracts else list(TUI_CONTRACT_GROUPS)
    invalid = [name for name in names if name not in TUI_CONTRACT_GROUPS]
    if invalid:
        print(f"unknown contract group(s): {', '.join(invalid)}", file=sys.stderr)
        return 2
    tests = unique([test for name in names for test in TUI_CONTRACT_GROUPS[name]])
    missing = [test for test in tests if not (ROOT / test).is_file()]
    if missing:
        print(f"missing contract tests: {', '.join(missing)}", file=sys.stderr)
        return 1
    print("contracts:", *names, sep="\n  ")
    print("tests:", *tests, sep="\n  ")
    if not args.run:
        print("plan only; add --run to execute pytest")
        return 0
    command = [sys.executable, "-m", "pytest", *tests, "-q"]
    if args.fast:
        command += ["-m", "not slow"]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
