"""`:ed` — открыть файл или вывод блока во внешнем редакторе.

Редактор берётся так: ключ `editor:` в settings.yml → `$VISUAL` → `$EDITOR`
→ системный список (`sensible-editor`, `nano`, `vi`/`vim`; Windows — `notepad`).
Значение может содержать аргументы (`editor: code --wait`, `editor: nvim -u NONE`).

Запуск — в настоящем TTY (TUI на паузе, как `> cmd`), поэтому подходит и
терминальный (vim/nano), и GUI-редактор с флагом ожидания. Модуль без Textual:
здесь только разбор команды и временные файлы для вывода блока.
"""
from __future__ import annotations

import os
import shlex
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence

TEMP_PREFIX = "idvjopy_editor_"
# Порядок системного поиска, если ни settings.yml, ни $VISUAL/$EDITOR не заданы.
LINUX_EDITORS = ("sensible-editor", "nano", "vi", "vim")
WINDOWS_EDITORS = ("notepad",)


class EditorError(Exception):
    """Понятная пользователю ошибка: нет редактора, пустое значение, битый путь."""


def _fallback_editors(platform: str | None = None) -> tuple[str, ...]:
    plat = sys.platform if platform is None else platform
    if plat.startswith("win"):
        return WINDOWS_EDITORS
    return LINUX_EDITORS


def resolve_editor(
    setting: str | None,
    environ: Mapping[str, str],
    *,
    platform: str | None = None,
) -> list[str]:
    """argv редактора: settings.yml → $VISUAL → $EDITOR → системный список.

    Бросает `EditorError`, если значение нельзя разобрать или бинарника нет
    в `$PATH` (никакого молчаливого отката на другой редактор).
    """
    for source, raw in (
        ("editor: in settings.yml", setting),
        ("$VISUAL", environ.get("VISUAL")),
        ("$EDITOR", environ.get("EDITOR")),
    ):
        value = (raw or "").strip()
        if not value:
            continue
        try:
            argv = shlex.split(value)
        except ValueError as e:
            raise EditorError(f"Cannot parse {source} ({value!r}): {e}") from e
        if not argv:
            continue
        if shutil.which(argv[0]) is None:
            raise EditorError(
                f"'{argv[0]}' not found ({source}); set `editor:` in settings.yml."
            )
        return argv
    for name in _fallback_editors(platform):
        if shutil.which(name) is not None:
            return [name]
    raise EditorError(
        "No editor found; set `editor:` in settings.yml (e.g. editor: vim) "
        "or export $EDITOR."
    )


def build_editor_command(editor_argv: Sequence[str], path: str) -> str:
    """Командная строка для `_run_in_tty`: редактор + путь (без shell-инъекций).

    GUI-редакторам обычно нужен флаг ожидания — он задаётся в settings.yml
    (`editor: code --wait`), иначе приложение продолжит работу сразу.
    """
    return shlex.join([*editor_argv, path])


def write_temp_text(text: str) -> str:
    """Временный .txt с текстом (UTF-8). Путь возвращается; удаляет вызывающий."""
    fd, path = tempfile.mkstemp(prefix=TEMP_PREFIX, suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def read_text_file(path: str) -> str:
    """Читает UTF-8 (не-UTF-8 байты заменяются) — для сравнения до/после правки."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()
