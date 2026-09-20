"""Область видимости тегов в сессии (`:scope`).

Сессии делят **одну** библиотеку тегов, но конкретному окну нужен свой фокус:
«сессия git — видно только наборы git». Scope — это фильтр **представления**,
свойство сессии, а не данных: в SQLite ничего не пишется, теги остаются на месте
для соседних окон, сидов, `:relang`, `:backup` и `:send`. Поэтому scope живёт в
своём файле `scope_<session>.json` рядом с `history_<session>.txt`, а не в таблице
БД: библиотеку носят через `:export`/`backup_db.py`, а область видимости —
свойство окна и в перенос попадать не должна.

Инвариант: scope влияет **только** на списки и подсказки. Явные адреса
(`?tag`, `!tag[tid]`, `:run <tag>`), команды (`:stats`, `:export`, `:alias`,
`:mv`) и учёт запусков работают как раньше — иначе фильтр ломал бы сохранённые
цепочки и чужие ссылки.

Два режима — ровно две формулировки задачи:
  * ``only`` — видно перечисленное (группы хендбуков и/или отдельные теги);
  * ``hide`` — видно всё, кроме перечисленного.

Пустой scope — фильтра нет (видно всё). Режим задаёт первая команда:
`:scope add …` включает ``only``, `:scope rm …` — ``hide``; смешивать их в одном
scope нельзя (явная ошибка вместо тихого сброса). Группы — канонические наборы
сидов из ``seed_groups`` (git, k8s, docker, helm, …), поэтому `:scope add git`
показывает именно теги, которые кладёт `seed_git`.
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, replace

from seed_groups import group_for_tag, group_tags, known_group_names

MODE_ONLY = "only"
MODE_HIDE = "hide"

SCOPE_PREFIX = "scope_"


def scope_file_for(session: str) -> str:
    """Имя файла области видимости сессии (без каталога)."""
    return f"{SCOPE_PREFIX}{session}.json"


def scope_path(data_dir: str, session: str) -> str:
    """Полный путь к файлу области видимости."""
    return os.path.join(data_dir, scope_file_for(session))


@dataclass(frozen=True)
class TagScope:
    """Что показывать в списках: режим + группы хендбуков и отдельные теги."""

    mode: str = ""
    groups: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Пустой scope — фильтра нет."""
        return not self.groups and not self.tags

    @property
    def names(self) -> tuple[str, ...]:
        """Перечисленные имена: группы, затем теги (для сообщений)."""
        return (*self.groups, *self.tags)

    @property
    def label(self) -> str:
        """Короткая подпись для заголовка окна: `only git, k8s`."""
        if self.is_empty:
            return ""
        return f"{self.mode} {', '.join(self.names)}"

    def matches(self, tag: str) -> bool:
        """Показывать ли этот тег в списках."""
        if self.is_empty:
            return True
        listed = tag in self.tags or group_for_tag(tag) in self.groups
        return listed if self.mode == MODE_ONLY else not listed

    def split(self, tags: Iterable[str]) -> tuple[list[str], list[str]]:
        """Разделить теги на (видимые, скрытые scope'ом), сохраняя порядок."""
        visible: list[str] = []
        hidden: list[str] = []
        for tag in tags:
            (visible if self.matches(tag) else hidden).append(tag)
        return visible, hidden

    def add(self, names: Iterable[str]) -> TagScope:
        """Оставить только эти имена (режим `only`).

        `add` к scope, который уже скрывает (`hide`), — явная ошибка: смешивать
        «только это» и «всё, кроме этого» в одном файле нельзя, иначе непонятно,
        что означает список. Сначала `:scope clear`.
        """
        return self._listed(names, mode=MODE_ONLY)

    def drop(self, names: Iterable[str]) -> TagScope:
        """Убрать имена из перечисленных; пустой список — снова видно всё.

        Первый `rm` на пустом scope включает режим «всё, кроме этого» (`hide`):
        так выражается «прятать», а не перечисление всего остального вручную.
        """
        if self.is_empty:
            return self._listed(names, mode=MODE_HIDE)
        result = replace(
            self,
            groups=tuple(name for name in self.groups if name not in set(names)),
            tags=tuple(name for name in self.tags if name not in set(names)),
        )
        return TagScope() if result.is_empty else result

    def _listed(self, names: Iterable[str], *, mode: str) -> TagScope:
        """Начать/продолжить перечисление в указанном режиме."""
        if self.mode and self.mode != mode:
            raise ScopeModeError(self.mode, mode)
        groups = list(self.groups)
        tags = list(self.tags)
        known_groups = known_group_names()
        for name in names:
            bucket = groups if name in known_groups else tags
            if name not in bucket:
                bucket.append(name)
        if not groups and not tags:
            return TagScope()
        return TagScope(mode=mode, groups=tuple(groups), tags=tuple(tags))

    def describe(self) -> str:
        """Человеческая расшифровка: что именно сейчас ограничено."""
        if self.is_empty:
            return "no filter"
        parts: list[str] = []
        for group in self.groups:
            tags = ", ".join(group_tags(group) or ())
            parts.append(f"{group} ({tags})" if tags else group)
        parts.extend(self.tags)
        return f"{self.mode}: " + "; ".join(parts)


class ScopeModeError(Exception):
    """Попытка смешать `only` и `hide` в одном scope."""

    def __init__(self, current: str, wanted: str) -> None:
        super().__init__(f"scope is already '{current}', not '{wanted}'")
        self.current = current
        self.wanted = wanted


def split_names(args: Iterable[str]) -> list[str]:
    """Разобрать аргументы `:scope` в имена: пробелы и запятые — разделители."""
    names: list[str] = []
    for arg in args:
        for token in str(arg).replace(",", " ").split():
            name = token.strip()
            if name and name not in names:
                names.append(name)
    return names


def classify(
    names: Iterable[str], known_tags: Iterable[str]
) -> tuple[list[str], list[str], list[str]]:
    """Разложить имена на (группы, теги, неизвестные).

    Группа проверяется первой: `:scope add git` — это набор git, а не одноимённый
    тег (`ip`, `file` могут совпасть — тогда группа шире и включает его).
    """
    tag_names = set(known_tags)
    groups: list[str] = []
    tags: list[str] = []
    unknown: list[str] = []
    for name in names:
        if name in known_group_names():
            groups.append(name)
        elif name in tag_names:
            tags.append(name)
        else:
            unknown.append(name)
    return groups, tags, unknown


def load_scope(data_dir: str, session: str) -> tuple[TagScope, str]:
    """Прочитать область видимости сессии: ``(scope, ошибка)``.

    Нет файла — пустой scope (фильтра нет). Битый файл не роняем и не гадаем:
    фильтр выключен, а текст ошибки приложение покажет в журнале.
    """
    path = scope_path(data_dir, session)
    if not os.path.isfile(path):
        return TagScope(), ""
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        return TagScope(), f"{os.path.basename(path)}: {exc}"
    if not isinstance(payload, dict):
        return TagScope(), f"{os.path.basename(path)}: JSON root must be an object"
    mode = str(payload.get("mode") or "").strip().lower()
    if mode not in (MODE_ONLY, MODE_HIDE):
        return TagScope(), f"{os.path.basename(path)}: unknown mode '{mode}'"
    groups = tuple(str(name) for name in payload.get("groups") or () if str(name).strip())
    tags = tuple(str(name) for name in payload.get("tags") or () if str(name).strip())
    return TagScope(mode=mode, groups=groups, tags=tags), ""


def save_scope(data_dir: str, session: str, scope: TagScope) -> bool:
    """Записать область видимости (пустой scope — файл удаляется)."""
    path = scope_path(data_dir, session)
    if scope.is_empty:
        try:
            os.unlink(path)
        except OSError:
            pass
        return True
    payload = {"mode": scope.mode, "groups": list(scope.groups), "tags": list(scope.tags)}
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError:
        return False
    return True
