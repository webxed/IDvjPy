#!/usr/bin/env python3
"""Bump CommandRunner.VERSION and keep the release docs in sync.

Thin launcher: the logic lives in src/version_bump.py. Loaded by file path
(like the root app.py / backup_db.py), so no ``import`` is needed and the
module name cannot collide with this launcher.

    python3 bump_version.py [--set vX.YY] [--dry-run] [--check]
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parent / "src"
_BUMP_FILE = _SRC / "version_bump.py"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _load_src_version_bump() -> Any:
    spec = importlib.util.spec_from_file_location("version_bump", _BUMP_FILE)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {_BUMP_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["version_bump"] = module
    spec.loader.exec_module(module)
    return module


_real = _load_src_version_bump()

if __name__ == "__main__":
    raise SystemExit(_real.main())
