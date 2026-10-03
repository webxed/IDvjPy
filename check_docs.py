#!/usr/bin/env python3
"""Read-only structural check for local Markdown links and canonical TUI help."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from help_texts import HELP_TEXTS
from repo_checks import local_link_error, markdown_links
from version_bump import check


def _markdown_files() -> list[Path]:
    return sorted([ROOT / "README.md", ROOT / "test_cmd.md", *ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md")])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links-only", action="store_true")
    parser.add_argument("--help-only", action="store_true")
    args = parser.parse_args(argv)
    if args.links_only and args.help_only:
        parser.error("--links-only and --help-only cannot be combined")
    failures: list[str] = []
    if not args.help_only:
        for markdown in dict.fromkeys(_markdown_files()):
            if not markdown.is_file():
                continue
            for target in markdown_links(markdown.read_text(encoding="utf-8")):
                error = local_link_error(markdown, target)
                if error:
                    failures.append(f"{markdown.relative_to(ROOT)}: {target!r}: {error}")
    if not args.links_only:
        for rel, needle in check(ROOT):
            failures.append(f"version marker: {rel}: missing {needle!r}")
        help_dir = ROOT / "src" / "locales" / "help" / "en"
        for name in HELP_TEXTS:
            path = help_dir / f"{name}.txt"
            if not path.is_file() or not path.read_text(encoding="utf-8").strip():
                failures.append(f"canonical help missing or empty: {path.relative_to(ROOT)}")
    if failures:
        print("docs check failed:", file=sys.stderr)
        print("\n".join(f"  - {item}" for item in failures), file=sys.stderr)
        return 1
    print("docs check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
