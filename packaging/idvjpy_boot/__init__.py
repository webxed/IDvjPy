"""Bootstrapper для установленного пакета IDvjPy_term.

При сборке wheel весь каталог ``src/`` копируется внутрь этого пакета
(``idvjpy_boot/src``), поэтому ресурсы (app.css, demos/*.yml, примеры
конфигов) едут вместе с кодом. При запуске эта вложенная ``src/``
добавляется в sys.path — топ-левел импорты приложения (``app``,
``database_v2``, …) работают как при запуске из репозитория.
"""
from __future__ import annotations

import importlib
import os
import re
import sys
from typing import Any

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")


def _package_version() -> str:
    """Версия wheel берётся из CommandRunner.VERSION вложенной src/app.py."""
    try:
        with open(os.path.join(_SRC, "app.py"), encoding="utf-8") as f:
            match = re.search(r'VERSION = "v(\d+)\.(\d+)"', f.read())
        if match:
            return f"{match.group(1)}.{match.group(2)}.0"
    except OSError:
        pass
    return "1.0.0"


__version__ = _package_version()


def main() -> None:
    """Console entry point: тот же запуск, что `python3 app.py` из repo.

    Модуль ``app`` резолвится только в рантайме — из вложенной ``src/``,
    которую мы кладём в sys.path. Статическим анализаторам этот импорт
    недоступен (они видят корневой лаунчер ``app.py`` без этих имён),
    поэтому обращение идёт через importlib, а модуль типизирован как Any.
    """
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)
    app: Any = importlib.import_module("app")

    args = app.parse_arguments()
    app.apply_instance_name(args.instance_name)
    demo_spec = app.load_demo_for_cli(args.demo) if args.demo else None
    application = app.CommandRunner(
        demo=demo_spec,
        demo_speed=args.demo_speed,
        demo_quit=args.demo_quit,
        data_dir=args.data_dir,
    )
    application.run()


if __name__ == "__main__":
    main()
