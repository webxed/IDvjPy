"""Переменные .bashrc_term, алиасы из ~/.bashrc и подстановка $1."""
from __future__ import annotations

import json
import os
import re
import shlex
from collections.abc import Mapping

RE_VAR_SUBST = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)\b"
)
RE_ALIAS_POS = re.compile(r'\$\{(\d+|[@*])\}|\$(\d+|[@*])')
RE_VAR_NAME = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
RE_OUT_PLACEHOLDER = re.compile(r"\$\{OUT\}|\$OUT\b")
LAZY_PLACEHOLDERS = frozenset({"OUT"})

# Shell/TTY bookkeeping — do not copy back into the TUI process.
TTY_ENV_SKIP = frozenset({
    "_",
    "SHLVL",
    "BASHPID",
    "PPID",
    "PWD",
    "OLDPWD",
    "COLUMNS",
    "LINES",
    "PIPESTATUS",
    "SHELLOPTS",
    "BASHOPTS",
    "BASH_ARGV0",
    "HISTCMD",
    "PS1",
    "PS2",
    "PS4",
    "PROMPT_COMMAND",
})


def parse_bashrc_assignment(line: str) -> tuple[str, str] | None:
    """Разбирает `export VAR=val` или `VAR=val`. Комментарии пропускает."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if not RE_VAR_NAME.match(key):
        return None
    value = value.strip().strip('"').strip("'")
    return key, value


def parse_alias_line(line: str) -> tuple[str, str] | None:
    """Разбирает `alias name='command'`. Иначе None."""
    line = line.strip()
    if not line.startswith("alias ") or "=" not in line:
        return None
    alias_def = line[6:]
    parts = alias_def.split("=", 1)
    if len(parts) != 2:
        return None
    alias_name = parts[0].strip()
    alias_value = parts[1].strip().strip('"').strip("'")
    return alias_name, alias_value


def load_aliases_from_file(path: str, encoding: str = "utf-8") -> dict[str, str]:
    """Читает файл алиасов (обычно ~/.bashrc) и возвращает {name: body}."""
    aliases: dict[str, str] = {}
    with open(path, encoding=encoding) as f:
        for line in f:
            parsed = parse_alias_line(line)
            if parsed:
                aliases[parsed[0]] = parsed[1]
    return aliases


def substitute_variables(
    command: str,
    local_env: Mapping[str, str],
    environ: Mapping[str, str] | None = None,
    extra: Mapping[str, str] | None = None,
) -> str:
    """Заменяет $VAR. Приоритет: extra > local_env > environ.

    ``extra`` — ленивые плейсхолдеры (например OUT): считаются только в момент
    подстановки, в local_env / .bashrc_term не пишутся.
    """
    env = os.environ if environ is None else environ
    extra = extra or {}

    def replacer(match: re.Match) -> str:
        var_name = match.group(1) or match.group(2)
        if var_name in extra:
            return extra[var_name]
        if var_name in local_env:
            return local_env[var_name]
        if var_name in env:
            return env[var_name]
        return match.group(0)

    return RE_VAR_SUBST.sub(replacer, command)


def command_requests_placeholder(command: str, name: str = "OUT") -> bool:
    """True if the command mentions a lazy placeholder (no stored copy needed)."""
    if name == "OUT":
        return bool(RE_OUT_PLACEHOLDER.search(command or ""))
    return f"${name}" in (command or "") or f"${{{name}}}" in (command or "")


def unexpanded_variables(text: str) -> list[str]:
    """Имена `$VAR` / `${VAR}`, оставшихся в тексте после подстановки.

    Нужны там, где литеральный `$` — почти наверняка опечатка в имени переменной
    (например путь для `:editor`), и лучше явная ошибка, чем файл с именем
    `$NOPE.yaml`.
    """
    names = {(match.group(1) or match.group(2)) for match in RE_VAR_SUBST.finditer(text or "")}
    return sorted(names)


def last_nonempty_line(text: str) -> str:
    """Last non-empty line without splitting the whole buffer into a list."""
    raw = text or ""
    end = len(raw)
    while end > 0 and raw[end - 1] in "\r\n":
        end -= 1
    if end == 0:
        return ""
    start = raw.rfind("\n", 0, end)
    line = raw[start + 1 : end]
    if line.endswith("\r"):
        line = line[:-1]
    return line.strip()


def expand_aliases(command: str, aliases: Mapping[str, str]) -> str:
    """
    Раскрывает алиас в первом слове.

    Если в теле есть $1, $2, $@ / $* — подставляет аргументы (как у shell-функции).
    Иначе классический alias: тело + оставшаяся строка.
    """
    raw = command.strip()
    if not raw:
        return command
    try:
        tokens = shlex.split(raw, posix=True)
    except ValueError:
        tokens = raw.split()
    if not tokens:
        return command
    name = tokens[0]
    if name not in aliases:
        return command
    body = aliases[name]
    args = tokens[1:]
    if not RE_ALIAS_POS.search(body):
        if len(raw.split(None, 1)) > 1:
            return f"{body} {raw.split(None, 1)[1]}"
        return body

    used_max = 0
    used_all = False

    def repl(match: re.Match) -> str:
        nonlocal used_max, used_all
        token = match.group(1) or match.group(2)
        if token in ("@", "*"):
            used_all = True
            return " ".join(shlex.quote(a) for a in args)
        idx = int(token)
        if idx == 0:
            return shlex.quote(name)
        used_max = max(used_max, idx)
        if 1 <= idx <= len(args):
            return shlex.quote(args[idx - 1])
        return ""

    expanded = RE_ALIAS_POS.sub(repl, body).strip()
    if not used_all and used_max < len(args):
        extra = " ".join(shlex.quote(a) for a in args[used_max:])
        if extra:
            expanded = f"{expanded} {extra}".strip()
    return expanded


def parse_standalone_cd(command: str) -> str | None:
    """
    Если команда — одиночный cd без &&/||/|;, вернуть путь.
    Пустая строка = домашний каталог. None = это не builtin cd.
    """
    raw = command.strip()
    if not raw or re.search(r"[&|;]", raw):
        return None
    try:
        tokens = shlex.split(raw, posix=True)
    except ValueError:
        tokens = raw.split()
    if not tokens or tokens[0] != "cd":
        return None
    args = tokens[1:]
    if not args:
        return ""
    if args[0] == "--":
        return args[1] if len(args) > 1 else ""
    return args[0]


def skip_tty_env_key(key: str) -> bool:
    """True for keys that must not be imported from a TTY child dump."""
    if not key or key in TTY_ENV_SKIP:
        return True
    if key.startswith("BASH_FUNC_"):
        return True
    return not bool(RE_VAR_NAME.match(key))


def load_env_dump(path: str) -> dict[str, str] | None:
    """JSON object of KEY→value from a child shell. None if missing or invalid."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or not data:
        return None
    out: dict[str, str] = {}
    for key, value in data.items():
        name = str(key)
        if skip_tty_env_key(name):
            continue
        out[name] = "" if value is None else str(value)
    return out


def diff_exported_env(
    before: Mapping[str, str],
    after: Mapping[str, str],
) -> tuple[dict[str, str], list[str]]:
    """Changed/new keys and keys unset in the child (skip list already applied)."""
    updates: dict[str, str] = {}
    for key, value in after.items():
        if skip_tty_env_key(key):
            continue
        if before.get(key) != value:
            updates[key] = value
    removed: list[str] = []
    for key in before:
        if skip_tty_env_key(key):
            continue
        if key not in after:
            removed.append(key)
    return updates, removed


def wrap_tty_command(
    command: str,
    env_path: str,
    pwd_path: str,
    python_exe: str,
) -> str:
    """Bash script: run ``command``, then dump env/PWD on EXIT (keeps $? )."""
    dump_py = (
        "import json,os,sys;"
        "json.dump(dict(os.environ), open(sys.argv[1],'w'), ensure_ascii=False)"
    )
    q_env = shlex.quote(env_path)
    q_pwd = shlex.quote(pwd_path)
    q_py = shlex.quote(python_exe)
    q_code = shlex.quote(dump_py)
    return (
        "_idvjopy_dump_env() {\n"
        f"  printf '%s' \"$PWD\" > {q_pwd} || true\n"
        f"  {q_py} -c {q_code} {q_env} || true\n"
        "}\n"
        "trap _idvjopy_dump_env EXIT\n"
        "set +e\n"
        f"{command}\n"
    )


def format_env_followup(names: list[str], cwd: str | None = None) -> list[str]:
    """Short journal lines after TTY: env names and optional cwd."""
    lines: list[str] = []
    if names:
        shown = names[:12]
        extra = f" (+{len(names) - 12})" if len(names) > 12 else ""
        lines.append(f"env: {', '.join(shown)}{extra}")
    if cwd:
        lines.append(f"cwd: {cwd}")
    return lines
