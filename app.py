#!/usr/bin/env python3
"""Launch IDvjPy_term from the data directory (settings.yml, DB, .bashrc_term).

Application code lives in src/. This file is a launcher and also re-exports
src/app.py as module ``app``, so ``from app import CommandRunner`` keeps working.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parent / "src"
_APP_FILE = _SRC / "app.py"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _load_src_app():
    spec = importlib.util.spec_from_file_location("app", _APP_FILE)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {_APP_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["app"] = module
    spec.loader.exec_module(module)
    return module


_real = _load_src_app()
globals().update({k: v for k, v in vars(_real).items() if k != "__name__"})


def __getattr__(name: str) -> Any:
    """PEP 562 hook so static checkers see the re-exports.

    The real names are injected by ``globals().update`` above, so at runtime this
    is only reached for genuinely missing attributes. Type checkers cannot follow
    that update, and without this hook ``from app import CommandRunner`` in a
    root-level script is reported as an unknown import symbol; delegating via
    ``__getattr__`` resolves it to the ``src/app.py`` object instead.
    """
    return getattr(_real, name)

if __name__ == "__main__":
    args = _real.parse_arguments()
    _real.apply_instance_name(args.instance_name)
    _real.apply_language(args.lang)
    demo_spec = _real.load_demo_for_cli(args.demo) if args.demo else None
    application = _real.CommandRunner(
        demo=demo_spec,
        demo_speed=args.demo_speed,
        demo_quit=args.demo_quit,
        data_dir=args.data_dir,
    )
    application.run()
