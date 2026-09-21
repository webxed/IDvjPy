"""Bootstrapper для установленного пакета IDvjPy_term.

При сборке wheel весь каталог ``src/`` копируется внутрь этого пакета
(``idvjpy_boot/src``), поэтому ресурсы (app.tcss, demos/*.yml, примеры
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
# В checkout (git-установка) вложенной src/ ещё нет — версию читаем из
# исходного ../../../src/app.py (пакет лежит в packaging/idvjpy_boot).
_REPO_SRC_APP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "src", "app.py"
)
_REPO_SRC = os.path.normpath(os.path.dirname(_REPO_SRC_APP))


def _src_dir() -> str:
    """Каталог с кодом: вложенная `src/` собранного wheel'а или repo'шная (checkout).

    В установленном пакете есть только первый вариант; из рабочей копии работает
    второй — так `python3 -m idvjpy_boot` и `idvjpy mcp` проверяются и в
    репозитории, а не только после сборки.
    """
    return _SRC if os.path.isdir(_SRC) else _REPO_SRC


def _package_version() -> str:
    """Версия пакета = CommandRunner.VERSION (`vMAJOR.MINOR` → `MAJOR.MINOR.0`)."""
    for candidate in (_SRC + os.sep + "app.py", _REPO_SRC_APP):
        try:
            with open(candidate, encoding="utf-8") as f:
                match = re.search(r'VERSION = "v(\d+)\.(\d+)"', f.read())
        except OSError:
            continue
        if match:
            return f"{match.group(1)}.{match.group(2)}.0"
    return "1.0.0"


__version__ = _package_version()


def mcp_main(argv: list[str] | None = None) -> int:
    """MCP-сервер (`idvjpy mcp [--data-dir …]`) — то же, что `python3 mcp_server.py`.

    Транспорт stdio: клиент запускает процесс сам, портов приложение не слушает.
    Сервер только читает (см. `src/mcp_server.py` и `:? mcp` в приложении).
    """
    src = _src_dir()
    if src not in sys.path:
        sys.path.insert(0, src)
    server: Any = importlib.import_module("mcp_server")
    return int(server.main(sys.argv[1:] if argv is None else argv))


def main() -> None:
    """Console entry point: тот же запуск, что `python3 app.py` из repo.

    Плюс подкоманда `idvjpy mcp […аргументы сервера]` — её разбираем до
    `parse_arguments()`, чтобы флаг не попал в CLI приложения.

    Модуль ``app`` резолвится только в рантайме — из вложенной ``src/``,
    которую мы кладём в sys.path. Статическим анализаторам этот импорт
    недоступен (они видят корневой лаунчер ``app.py`` без этих имён),
    поэтому обращение идёт через importlib, а модуль типизирован как Any.
    """
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        raise SystemExit(mcp_main(sys.argv[2:]))
    src = _src_dir()
    if src not in sys.path:
        sys.path.insert(0, src)
    app: Any = importlib.import_module("app")

    args = app.parse_arguments()
    app.apply_instance_name(args.instance_name)
    app.apply_language(args.lang)
    demo_spec = app.load_demo_for_cli(args.demo) if args.demo else None
    application = app.CommandRunner(
        demo=demo_spec,
        demo_speed=args.demo_speed,
        demo_quit=args.demo_quit,
        data_dir=args.data_dir,
    )
    application.run()
    # Сменить каталог родительской оболочки процесс не может — говорим готовую
    # команду `cd '…'` (тихо, если каталог не менялся); обёртка — `$IDVJPY_CWD_FILE`.
    note = application.exit_cwd_note()
    if note:
        print(app.t("exit.cwd_note", cwd=os.getcwd(), hint=note), file=sys.stderr)


if __name__ == "__main__":
    main()
