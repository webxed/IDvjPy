#!/usr/bin/env python3
"""Bump CommandRunner.VERSION and keep the release docs in sync.

Thin launcher: the logic lives in src/version_bump.py (see there for flags).
    python3 bump_version.py [--set vX.YY] [--dry-run] [--check]
"""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import version_bump as _version_bump  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_version_bump.main())
