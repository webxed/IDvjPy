"""Импорт истории оболочки пользователя (`:h import`) — Linux, macOS, Windows.

Модуль только **читает**: находит файлы истории известных оболочек (с учётом ОС и
`$HISTFILE`), разбирает их форматы и отдаёт команды по одной на строку — их
дописывает `history_store.append_history_file_lines` в `history_<instance>.txt`.
Ничего не исполняется и не удаляется; битые байты заменяются (``errors="replace"``).

Форматы:

* **zsh** — extended (`: 1700000000:0;cmd`) и обычный; внутренние переводы строк
  сворачиваются в ` ; ` (в истории приложения одна команда — одна строка);
* **bash** / **sh** / **ksh** — обычный, строки-метки времени `#1700000000`
  (bash пишет их при `HISTTIMEFORMAT`) пропускаются;
* **fish** — YAML-подобный `- cmd: …` (значение может быть в кавычках, `\\n` —
  перевод строки внутри команды);
* **PowerShell** (`PSReadLine/ConsoleHost_history.txt`) и **nushell** — обычный.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field

# Последние N строк каждого источника (0 — без ограничения). Импорт чужой истории
# — это хвост: тысячи строк незачем, важен недавний опыт.
DEFAULT_IMPORT_LIMIT = 5000

KNOWN_SHELLS: tuple[str, ...] = (
    "zsh",
    "bash",
    "fish",
    "ksh",
    "nu",
    "pwsh",
    "powershell",
    "sh",
)

_RE_ZSH_EXT = re.compile(r"^: \d+:\d+;")
_RE_ZSH_RECORD = re.compile(r"(?m)^(?=: \d+:\d+;)")
_RE_BASH_TIMESTAMP = re.compile(r"^#\d{6,}$")
_FISH_CMD_PREFIXES = ("- cmd: ", "cmd: ")
# Хвост больших историй: парсеру нужны только последние `limit` команд, поэтому
# многомегабайтный файл целиком в память не тянем.
MAX_READ_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class Source:
    """Файл истории: оболочка и путь."""

    shell: str
    path: str


@dataclass
class SourceResult:
    """Что прочитано из источника: команды (последние `limit`) или ошибка."""

    shell: str
    path: str
    commands: list[str] = field(default_factory=list)
    error: str = ""


def _shell_from_path(path: str) -> str:
    """Оболочка по имени файла (`$HISTFILE` может быть любым)."""
    name = os.path.basename(path).lower()
    if "nushell" in name:
        return "nu"
    for shell in ("zsh", "bash", "fish", "ksh"):
        if shell in name:
            return shell
    return "sh"


def data_home(env: dict[str, str], home: str) -> str:
    """XDG-каталог данных — его понимают fish и PowerShell Core на всех ОС."""
    return env.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")


def _nu_data_home(env: dict[str, str], home: str, system: str) -> str:
    """Каталог данных nushell: он следует за системным (dirs::data_dir)."""
    if system == "darwin":
        return os.path.join(home, "Library", "Application Support")
    return data_home(env, home)


def candidate_sources(
    *,
    env: dict[str, str] | None = None,
    platform: str | None = None,
    home: str | None = None,
) -> list[Source]:
    """Все кандидаты путей истории (существование не проверяется).

    Заданный ``$HISTFILE`` идёт первым: оболочка сама сказала, где лежит её история.
    Остальные пути — по ОС и по тому, как каждая оболочка хранит данные: fish и
    PowerShell Core — XDG-каталог (`~/.local/share`) на любых ОС, nushell —
    системный каталог данных (`Application Support` / `%APPDATA%`), PowerShell —
    `%APPDATA%` на Windows. Пути «чужой» ОС в список не попадают: они всё равно
    не найдутся, но засоряют сообщение «где искали».
    """
    environ = dict(os.environ if env is None else env)
    system = platform or sys.platform
    home_dir = (
        home
        or environ.get("HOME")
        or environ.get("USERPROFILE")
        or os.path.expanduser("~")
    )
    appdata = environ.get("APPDATA") or home_dir

    if system == "win32":
        # Windows: PowerShell 7 (pwsh) и Windows PowerShell 5.1 держат историю в
        # `%APPDATA%`; `~/.bash_history` — Git Bash / WSL-профиль.
        sources = [
            Source("bash", os.path.join(home_dir, ".bash_history")),
            Source("nu", os.path.join(appdata, "nushell", "history.txt")),
            Source(
                "pwsh",
                os.path.join(
                    appdata, "Microsoft", "PowerShell", "PSReadLine",
                    "ConsoleHost_history.txt",
                ),
            ),
            Source(
                "powershell",
                os.path.join(
                    appdata, "Microsoft", "Windows", "PowerShell", "PSReadLine",
                    "ConsoleHost_history.txt",
                ),
            ),
        ]
    else:
        sources = [
            Source("zsh", os.path.join(home_dir, ".zsh_history")),
            Source("zsh", os.path.join(home_dir, ".histfile")),
            Source("bash", os.path.join(home_dir, ".bash_history")),
            Source("fish", os.path.join(data_home(environ, home_dir), "fish", "fish_history")),
            Source("ksh", os.path.join(home_dir, ".sh_history")),
            Source(
                "nu",
                os.path.join(_nu_data_home(environ, home_dir, system), "nushell", "history.txt"),
            ),
            Source(
                "pwsh",
                os.path.join(
                    data_home(environ, home_dir), "powershell", "PSReadLine",
                    "ConsoleHost_history.txt",
                ),
            ),
        ]
    histfile = (environ.get("HISTFILE") or "").strip()
    if histfile:
        sources.insert(
            0,
            Source(
                _shell_from_path(histfile),
                os.path.abspath(os.path.expanduser(histfile)),
            ),
        )
    return sources


def _wanted(shell: str | None) -> str | None:
    """Имя оболочки в каноническом виде (`sh` — это ksh-подобная `.sh_history`)."""
    name = (shell or "").strip().lower()
    if not name:
        return None
    return "ksh" if name == "sh" else name


def _candidates(shell: str | None, **kwargs) -> list[Source]:
    wanted = _wanted(shell)
    sources = [src for src in candidate_sources(**kwargs) if not wanted or src.shell == wanted]
    # Один путь — один раз (`~/.zsh_history` и `$HISTFILE` могут совпасть).
    unique: list[Source] = []
    seen: set[str] = set()
    for src in sources:
        key = os.path.normcase(os.path.abspath(src.path))
        if key in seen:
            continue
        seen.add(key)
        unique.append(src)
    return unique


def searched_paths(shell: str | None = None, **kwargs) -> list[str]:
    """Пути-кандидаты для сообщения «история не найдена»."""
    return [src.path for src in _candidates(shell, **kwargs)]


def find_sources(shell: str | None = None, **kwargs) -> list[Source]:
    """Существующие файлы истории (уникальные пути) для оболочки (или всех)."""
    return [src for src in _candidates(shell, **kwargs) if os.path.isfile(src.path)]


def _flatten(command: str) -> str:
    """Многострочный ввод → одна строка: история приложения хранит команда = строка."""
    parts = [part.strip() for part in command.splitlines() if part.strip()]
    return " ; ".join(parts)


def _parse_plain(text: str, *, drop_timestamps: bool) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if drop_timestamps and _RE_BASH_TIMESTAMP.match(line):
            continue
        out.append(line)
    return out


def _parse_zsh(text: str) -> list[str]:
    # zsh кодирует перенос внутри записи как `\`+перевод строки: снимаем его до
    # разбора, иначе в команде остаётся хвостовой `\` (`do\ ; echo … не выполнится`).
    text = text.replace("\\\n", "\n")
    if not _RE_ZSH_RECORD.search(text):
        return _parse_plain(text, drop_timestamps=False)  # extended выключен
    out: list[str] = []
    for chunk in _RE_ZSH_RECORD.split(text):
        command = _flatten(_RE_ZSH_EXT.sub("", chunk, count=1))
        if command:
            out.append(command)
    return out


def _unquote(value: str) -> str:
    """Снять кавычки YAML-формы (старый fish)."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _fish_unescape(value: str) -> str:
    r"""Однопроходный unescape значений fish: `\` — обратный слеш, `\n` — перенос.

    Замена «по порядку подстрок» путала `\\n` (литеральный `\`+`n`, например
    `C:\new`) с переносом строки и портила команду.
    """
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\" or index + 1 >= len(value):
            out.append(char)
            index += 1
            continue
        nxt = value[index + 1]
        if nxt == "\\":
            out.append("\\")
        elif nxt == "n":
            out.append(" ; ")
        else:
            out.append(nxt)
        index += 2
    return "".join(out)


def _parse_fish(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        for prefix in _FISH_CMD_PREFIXES:
            if line.startswith(prefix):
                command = _unquote(line[len(prefix):].strip())
                command = _fish_unescape(command).strip()
                if command:
                    out.append(command)
                break
    return out


def parse_history(text: str, shell: str) -> list[str]:
    """Команды из текста истории оболочки (одна команда — один элемент)."""
    code = _wanted(shell) or "ksh"
    if code != "zsh" and _RE_ZSH_RECORD.search(text):
        # Неопознанный `$HISTFILE` (например `~/.history`) с zsh-extended записями:
        # иначе маркеры `: ts:dur;` остались бы прямо в тексте команды.
        code = "zsh"
    if code == "fish":
        return _parse_fish(text)
    if code == "zsh":
        return _parse_zsh(text)
    if code in ("bash", "ksh"):
        return _parse_plain(text, drop_timestamps=True)
    return _parse_plain(text, drop_timestamps=False)


def _read_history_text(path: str) -> str:
    """Прочитать историю: BOM снимается, бинарный файл — ошибка, большие — хвост.

    Парсеру нужны только последние `limit` команд, поэтому у файлов больше
    ``MAX_READ_BYTES`` читаем конец файла (первую, возможно обрезанную, строку
    отбрасываем): многомегабайтная история не должна тормозить UI-поток.
    """
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        if size > MAX_READ_BYTES:
            handle.seek(size - MAX_READ_BYTES)
            data = handle.read()
            cut = data.find(b"\n")
            data = data[cut + 1:] if cut >= 0 else data
        else:
            data = handle.read()
    if b"\x00" in data[:8192]:
        raise ValueError("binary file, not a shell history")
    return data.decode("utf-8-sig", errors="replace")


def read_sources(
    shell: str | None = None,
    *,
    limit: int = DEFAULT_IMPORT_LIMIT,
    **kwargs,
) -> list[SourceResult]:
    """Прочитать найденные источники: последние ``limit`` команд каждого (0 — все).

    Существующий, но нечитаемый файл (права, бинарь) попадает в результат с
    ``error`` — вызывающий решает, сообщать ли об этом.
    """
    results: list[SourceResult] = []
    for source in find_sources(shell, **kwargs):
        try:
            text = _read_history_text(source.path)
        except (OSError, ValueError) as exc:
            results.append(SourceResult(source.shell, source.path, [], str(exc)))
            continue
        commands = parse_history(text, source.shell)
        if limit > 0:
            commands = commands[-limit:]
        results.append(SourceResult(source.shell, source.path, commands))
    return results
