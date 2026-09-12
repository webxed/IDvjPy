#!/usr/bin/env python3
"""Launch backup_db from the data directory (settings.yml, DB, backups/).

The tool lives in src/backup_db.py; this file is a thin launcher. It is loaded
by file path, so ``import backup_db`` cannot resolve back to this launcher
(the same trick as the root ``app.py``).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parent / "src"
_BACKUP_FILE = _SRC / "backup_db.py"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _load_src_backup() -> Any:
    spec = importlib.util.spec_from_file_location("backup_db", _BACKUP_FILE)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {_BACKUP_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["backup_db"] = module
    spec.loader.exec_module(module)
    return module


_real = _load_src_backup()

if __name__ == "__main__":
    _real.main()
