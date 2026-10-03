#!/usr/bin/env python3
"""Plan focused pytest from changed files; use --run to execute the plan."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from repo_checks import focused_tests_for_path, focused_tests_for_paths, git_changed_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="compare base...HEAD")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--run", action="store_true", help="run the planned focused pytest files")
    parser.add_argument("--include-slow", action="store_true")
    parser.add_argument("--lint", action="store_true", help="also run available ruff/basedpyright")
    parser.add_argument("--strict", action="store_true", help="fail when changed Python has no mapped test")
    args = parser.parse_args(argv)
    try:
        paths = git_changed_files(base=args.base, staged=args.staged)
    except RuntimeError as exc:
        print(f"test_changed: {exc}", file=sys.stderr)
        return 2
    tests = focused_tests_for_paths(paths)
    print("changed:", *paths, sep="\n  ") if paths else print("changed: none")
    print("focused tests:", *tests, sep="\n  ") if tests else print("focused tests: none")
    unmapped = [
        path
        for path in paths
        if path.startswith("src/") and path.endswith(".py") and not focused_tests_for_path(path)
    ]
    if args.strict and unmapped:
        print(f"unmapped Python paths: {', '.join(unmapped)}", file=sys.stderr)
        return 1
    if args.lint:
        source_paths = [path for path in paths if path.endswith(".py") and (ROOT / path).is_file()]
        for tool in ("ruff", "basedpyright"):
            executable = shutil.which(tool)
            if not executable:
                print(f"{tool}: skipped (not installed)")
                continue
            result = subprocess.run([executable, "check", *source_paths] if tool == "ruff" else [executable, *source_paths], cwd=ROOT, check=False)
            if result.returncode:
                return result.returncode
    if not args.run or not tests:
        if not args.run:
            print("plan only; add --run to execute pytest")
        return 0
    command = [sys.executable, "-m", "pytest", *tests, "-q"]
    if not args.include_slow:
        command += ["-m", "not slow"]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
