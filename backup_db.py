#!/usr/bin/env python3
"""Launch backup_db from the data directory (settings.yml, DB, backups/)."""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(_SRC))

import backup_db as _backup  # noqa: E402

if __name__ == "__main__":
    _backup.main()
