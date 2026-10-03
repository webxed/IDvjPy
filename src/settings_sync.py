"""Синхронизация личных YAML с шаблоном новой версии приложения.

``settings.yml`` и ``llm_providers.yml`` копируются из шаблона только при **первом**
запуске в новом каталоге данных. У уже настроенного пользователя новые ключи не
появляются: код читает их через ``settings.get(KEY, DEFAULT)`` и молча живёт на
значении по умолчанию. Команда ``:settings sync`` доливает в личный файл
**недостающие** блоки шаблона, не трогая уже существующие значения и комментарии.

Модуль намеренно без Textual: чистая работа с текстом и файлами, удобно
тестировать. Ключевое ограничение — PyYAML не хранит комментарии, поэтому
``yaml.safe_dump`` не годится; работаем построчно, как ``_save_settings_scalar``
в ``app.py``. Разбор рассчитан на подмножество YAML наших шаблонов (комментарии,
скаляры, вложенные словари, блочные списки); блок-скаляры, внутри которых есть
строки вида ``ключ: значение``, не поддерживаются — в шаблонах таких нет.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass, field

# Ключ верхнего уровня / вложенный: буква/цифра/`_` в начале, далее `_.-`.
_RE_KEY = re.compile(r"^(\s*)([A-Za-z0-9_][A-Za-z0-9_.\-]*)\s*:(.*)$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


@dataclass
class Block:
    """Блок YAML: комментарий над ключом + сам ключ + вложенное содержимое."""

    path: tuple[str, ...]
    indent: int
    start: int  # индекс первой строки блока (начало комментария)
    key_index: int  # индекс строки с ключом
    end: int  # индекс за последней строкой блока (не включая)
    children: list[Block] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.path[-1]


def _comment_start(lines: list[str], key_index: int, start: int, indent: int) -> int:
    """Начало комментария непосредственно над ключом (без пустых строк)."""
    k = key_index
    while k - 1 >= start:
        prev = lines[k - 1]
        if not _is_comment(prev) or _indent(prev) < indent:
            break
        k -= 1
    return k


def _parse_blocks(
    lines: list[str], start: int, end: int, min_indent: int, prefix: tuple[str, ...]
) -> list[Block]:
    """Собрать блоки в диапазоне ``[start, end)`` с отступом не меньше ``min_indent``."""
    blocks: list[Block] = []
    i = start
    while i < end:
        match = _RE_KEY.match(lines[i])
        if not match or _indent(lines[i]) < min_indent:
            i += 1
            continue
        indent = _indent(lines[i])
        key = match.group(2)
        # Конец блока — первая (непустая) строка с отступом не глубже ключа.
        j = i + 1
        while j < end:
            if lines[j].strip() and _indent(lines[j]) <= indent:
                break
            j += 1
        children = _parse_blocks(lines, i + 1, j, indent + 1, prefix + (key,))
        blocks.append(
            Block(
                path=prefix + (key,),
                indent=indent,
                start=_comment_start(lines, i, start, indent),
                key_index=i,
                end=j,
                children=children,
            )
        )
        i = j
    return blocks


def parse_blocks(text: str) -> tuple[list[str], list[Block]]:
    """Разобрать текст в список строк и блоки верхнего уровня (с вложенностью)."""
    lines = text.split("\n")
    return lines, _parse_blocks(lines, 0, len(lines), 0, ())


def _walk(blocks: list[Block]):
    for block in blocks:
        yield block
        yield from _walk(block.children)


def _paths(blocks: list[Block]) -> dict[tuple[str, ...], Block]:
    return {block.path: block for block in _walk(blocks)}


def render_block(lines: list[str], block: Block, indent_delta: int = 0) -> list[str]:
    """Строки блока из исходного текста, сдвинутые на ``indent_delta``.

    Хвостовые пустые строки отбрасываются: они — разделитель перед следующим
    блоком, а не часть этого.
    """
    out = [
        (" " * indent_delta + line if indent_delta and line.strip() else line)
        for line in lines[block.start : block.end]
    ]
    while out and not out[-1].strip():
        out.pop()
    return out


@dataclass
class SyncPlan:
    """Что и куда долить; ничего не удаляем и не перезаписываем."""

    missing_top: list[Block] = field(default_factory=list)
    # (путь родителя в личном файле, блок шаблона для вставки внутрь)
    missing_nested: list[tuple[tuple[str, ...], Block]] = field(default_factory=list)
    obsolete: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.missing_top) + len(self.missing_nested)

    @property
    def is_empty(self) -> bool:
        return self.count == 0

    def missing_paths(self) -> list[tuple[str, ...]]:
        return [b.path for b in self.missing_top] + [b.path for _, b in self.missing_nested]


def plan_sync(user_text: str, template_text: str) -> SyncPlan:
    """Сравнить личный файл с шаблоном: чего не хватает и что лишнее.

    Вставляются только отсутствующие ключи: если родитель уже есть, доливаются
    его новые дети (например, новое поле провайдера LLM). Существующие значения
    не трогаются даже при отличии от шаблона — это настройка пользователя.
    """
    _, user_blocks = parse_blocks(user_text)
    _, template_blocks = parse_blocks(template_text)
    user_paths = _paths(user_blocks)
    template_paths = _paths(template_blocks)

    plan = SyncPlan()
    for path, block in template_paths.items():
        if path in user_paths:
            continue
        parent = path[:-1]
        if not parent:
            plan.missing_top.append(block)
        elif parent in user_paths:
            plan.missing_nested.append((parent, block))
        # Родителя нет — весь его блок уже добавлен как missing_top/nested выше.

    # Лишние ключи только там, где родитель известен шаблону (иначе это отдельный
    # пользовательский блок целиком, и перечислять его поля незачем).
    obsolete: set[str] = set()
    for path in user_paths:
        if path in template_paths:
            continue
        parent = path[:-1]
        if not parent:
            obsolete.add(path[0])
        elif parent in template_paths:
            obsolete.add(".".join(path))
    # Имя `providers.foo` уже поглощает свои поля `providers.foo.*`.
    plan.obsolete = sorted({
        name for name in obsolete
        if not any(name != other and name.startswith(other + ".") for other in obsolete)
    })
    return plan


def _content_end(lines: list[str], block: Block) -> int:
    """Индекс за последней содержательной строкой блока (без хвостовых пустых)."""
    end = block.end
    while end - 1 > block.key_index and not lines[end - 1].strip():
        end -= 1
    return end


def _eof_insert_index(lines: list[str]) -> int:
    return len(lines) - 1 if lines and lines[-1] == "" else len(lines)


def render_sync(
    user_text: str, template_text: str, version: str
) -> tuple[SyncPlan, list[str]]:
    """Собрать новый текст личного файла и план (без записи на диск).

    Возвращает ``(план, строки нового файла)``. Если добавлять нечего, строки
    совпадают с исходными.
    """
    plan = plan_sync(user_text, template_text)
    if plan.is_empty:
        return plan, user_text.split("\n")

    lines, user_blocks = parse_blocks(user_text)
    template_lines, _ = parse_blocks(template_text)
    user_map = _paths(user_blocks)
    edits: list[tuple[int, list[str]]] = []

    # Новые ключи верхнего уровня — в конец файла под маркером версии.
    if plan.missing_top:
        chunk: list[str] = ["", f"# Added in {version} (settings sync)."]
        for block in plan.missing_top:
            chunk.append("")
            chunk.extend(render_block(template_lines, block))
        chunk.append("")  # финальный перевод строки, как у обычного файла
        edits.append((_eof_insert_index(lines), chunk))

    # Новые вложенные ключи — внутрь уже существующего родителя.
    for parent_path, block in plan.missing_nested:
        parent = user_map.get(parent_path)
        if parent is None:
            continue
        child_indent = min(
            (child.indent for child in parent.children), default=parent.indent + 2
        )
        rendered = render_block(
            template_lines, block, indent_delta=child_indent - block.indent
        )
        edits.append((_content_end(lines, parent), [""] + rendered))

    # Вставляем снизу вверх, чтобы индексы не сдвигались.
    for index, chunk in sorted(edits, key=lambda edit: edit[0], reverse=True):
        lines[index:index] = chunk
    return plan, lines


def _all_paths(text: str) -> set[tuple[str, ...]]:
    _, blocks = parse_blocks(text)
    return set(_paths(blocks))


def _yaml_ok(text: str) -> bool:
    try:
        import yaml

        return isinstance(yaml.safe_load(text), dict)
    except Exception:
        return False


@dataclass
class SyncResult:
    applied: bool
    plan: SyncPlan
    added: int = 0
    backup: str = ""
    error: str = ""


def apply_sync(
    user_path: str,
    template_text: str,
    version: str,
    *,
    backup_dir: str | None = None,
    encoding: str = "utf-8",
) -> SyncResult:
    """Долить недостающие ключи в ``user_path`` с бэкапом и проверкой.

    Сначала рендерим и валидируем новый текст; только потом копируем оригинал в
    ``backups/`` и пишем атомарно (временный файл + ``os.replace``). Битый
    результат YAML или потеря существующих ключей — запись отменяется.
    """
    try:
        with open(user_path, encoding=encoding) as handle:
            user_text = handle.read()
    except OSError as exc:
        return SyncResult(applied=False, plan=SyncPlan(), error=str(exc))

    plan, new_lines = render_sync(user_text, template_text, version)
    if plan.is_empty:
        return SyncResult(applied=False, plan=plan)

    new_text = "\n".join(new_lines)
    if not _yaml_ok(new_text):
        return SyncResult(applied=False, plan=plan, error="result is not valid YAML")
    if not _all_paths(user_text).issubset(_all_paths(new_text)):
        return SyncResult(applied=False, plan=plan, error="existing keys would be lost")

    directory = os.path.dirname(os.path.abspath(user_path)) or "."
    backup_root = backup_dir or os.path.join(directory, "backups")
    backup_path = ""
    try:
        os.makedirs(backup_root, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = os.path.join(
            backup_root, f"{os.path.basename(user_path)}-pre-sync-{stamp}"
        )
        shutil.copy2(user_path, backup_path)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".settings-sync-")
        try:
            with os.fdopen(fd, "w", encoding=encoding) as handle:
                handle.write(new_text)
            os.replace(tmp_path, user_path)
        except OSError:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        return SyncResult(applied=False, plan=plan, error=str(exc), backup=backup_path)

    return SyncResult(applied=True, plan=plan, backup=backup_path, added=plan.count)
