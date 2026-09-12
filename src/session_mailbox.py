"""Межсессионная пересылка команд: файловый ящик ``inbox_<session>.jsonl``.

Сессии — это отдельные процессы (окна ``:new``); общего сокета/демона нет.
Обмен идёт через data-каталог, тем же приёмом, что и остальные файлы проекта
(``history_*.txt``, ``kctx.json``): отправитель дописывает JSON-строку под
exclusive-блокировкой (portalocker через :mod:`history_store`), получатель
периодически «вычерпывает» ящик и доставляет команду у себя — вставляет во
ввод (``mode`` = ``insert``) или выполняет (``mode`` = ``run``).

Ящик персистентный: сообщение, отправленное в незапущенную сессию, лежит до её
старта (первый опрос читает и обнуляет файл). Значения секретов ``$$`` в ящик
не попадают — отправитель маскирует их до записи. Права файла ``0600``.
"""
from __future__ import annotations

import datetime
import json
import os

from history_store import (
    FileLockTimeoutError,
    acquire_file_lock,
    release_file_lock,
)

MODE_INSERT = "insert"
MODE_RUN = "run"
MODES = (MODE_INSERT, MODE_RUN)

INBOX_PREFIX = "inbox_"
INBOX_SUFFIX = ".jsonl"
LOCK_TIMEOUT = 2
MAX_COMMAND_BYTES = 64 * 1024


class MailboxError(Exception):
    """Сбой записи в ящик; текст показывается пользователю."""


def inbox_file_for(session: str) -> str:
    """Имя файла ящика для сессии (без каталога)."""
    return f"{INBOX_PREFIX}{session}{INBOX_SUFFIX}"


def inbox_path(data_dir: str, session: str) -> str:
    """Полный путь к ящику сессии в data-каталоге."""
    return os.path.join(data_dir, inbox_file_for(session))


def make_message(
    target: str, command: str, *, sender: str, mode: str = MODE_INSERT
) -> dict[str, str]:
    """Собрать сообщение ящика (без записи)."""
    return {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "from": sender or "",
        "to": target or "",
        "mode": mode if mode in MODES else MODE_INSERT,
        "command": command or "",
    }


def send_message(
    data_dir: str,
    target: str,
    command: str,
    *,
    sender: str,
    mode: str = MODE_INSERT,
    lock_timeout: int = LOCK_TIMEOUT,
) -> None:
    """Дописать сообщение в ящик ``target``. Бросает :class:`MailboxError`."""
    text = (command or "").strip()
    if not text:
        raise MailboxError("empty command")
    if len(text.encode("utf-8", "replace")) > MAX_COMMAND_BYTES:
        raise MailboxError("command is too long")
    if mode not in MODES:
        mode = MODE_INSERT
    line = json.dumps(
        make_message(target, text, sender=sender, mode=mode), ensure_ascii=False
    )
    path = inbox_path(data_dir, target)
    try:
        os.makedirs(data_dir, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    except OSError as exc:
        raise MailboxError(str(exc)) from None
    try:
        os.chmod(path, 0o600)  # уже существующий файл тоже прячем
    except OSError:
        pass
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            locked = False
            try:
                acquire_file_lock(handle, lock_timeout)
                locked = True
            except FileLockTimeoutError:
                pass  # без блокировки всё равно допишем одной строкой
            try:
                handle.write(line + "\n")
                handle.flush()
            finally:
                if locked:
                    release_file_lock(handle)
    except OSError as exc:
        raise MailboxError(str(exc)) from None


def _parse_messages(data: str) -> list[dict[str, str]]:
    """Разобрать содержимое ящика; битые строки пропускаются."""
    messages: list[dict[str, str]] = []
    for raw in data.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue
        command = obj.get("command")
        if not isinstance(command, str) or not command.strip():
            continue
        messages.append(
            {
                "ts": str(obj.get("ts") or ""),
                "from": str(obj.get("from") or ""),
                "to": str(obj.get("to") or ""),
                "mode": str(obj.get("mode") or MODE_INSERT),
                "command": command,
            }
        )
    return messages


def drain_inbox(path: str, lock_timeout: int = LOCK_TIMEOUT) -> list[dict[str, str]]:
    """Прочитать и обнулить ящик; вернуть сообщения.

    Нет файла, пусто или писатель держит блокировку — пустой список
    (следующий опрос попробует снова). Битая строка пропускается целиком.
    """
    try:
        handle = open(path, "r+", encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError:
        return []
    with handle:
        locked = False
        try:
            acquire_file_lock(handle, lock_timeout)
            locked = True
        except (OSError, FileLockTimeoutError):
            return []
        try:
            data = handle.read()
            if not data:
                return []
            handle.seek(0)
            handle.truncate()
            handle.flush()
        except OSError:
            return []
        finally:
            if locked:
                release_file_lock(handle)
    return _parse_messages(data)


def pending_sessions(data_dir: str) -> list[str]:
    """Сессии, у которых ящик непустой (ожидают доставки)."""
    names: list[str] = []
    try:
        entries = os.listdir(data_dir)
    except OSError:
        return names
    for entry in entries:
        if not (entry.startswith(INBOX_PREFIX) and entry.endswith(INBOX_SUFFIX)):
            continue
        session = entry[len(INBOX_PREFIX):-len(INBOX_SUFFIX)]
        if not session:
            continue
        try:
            if os.path.getsize(os.path.join(data_dir, entry)) > 0:
                names.append(session)
        except OSError:
            continue
    return sorted(names)
