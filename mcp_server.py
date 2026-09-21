#!/usr/bin/env python3
"""Launch the IDvjPy_term MCP server (read-only, stdio) from the data directory.

The server lives in src/mcp_server.py; this file is a thin launcher. It is loaded
by file path, so ``import mcp_server`` cannot resolve back to this launcher
(the same trick as the root ``app.py`` / ``backup_db.py``).

Client config (Claude Code, Cursor, …):

    claude mcp add idvjpy -- python3 /path/to/IDvjPy/mcp_server.py

    {"mcpServers": {"idvjpy": {"command": "python3",
                               "args": ["/path/to/IDvjPy/mcp_server.py"]}}}

Reads only: the library (`database_tags_file`), the session history and — with
``--shell-history`` — the shell's own history files. Nothing is modified, no port
is opened, no secrets are read (`:? mcp` in the app tells the same story).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parent / "src"
_SERVER_FILE = _SRC / "mcp_server.py"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _load_src_server() -> Any:
    spec = importlib.util.spec_from_file_location("mcp_server", _SERVER_FILE)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {_SERVER_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["mcp_server"] = module
    spec.loader.exec_module(module)
    return module


_real = _load_src_server()

if __name__ == "__main__":
    sys.exit(_real.main())
