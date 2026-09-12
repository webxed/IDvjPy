"""Синхронизация версии релиза во всех файлах (``bump_version``).

Источник правды — ``VERSION`` в ``src/app.py``. Один прогон поднимает минор
(``v1.97`` → ``v1.98``) или ставит явную версию (``--set``) и обновляет
маркеры, которые проверяет ``tests/test_release_meta.py``:

    src/app.py, README.md, COMPACT_SUMMARY.md, CLAUDE.md, AGENTS.md,
    test_cmd.md, tests/test_cmd_scenarios.py, DEMO.md

Плюс номер версии документа в ``test_cmd.md`` (+1) и строка плана
(``Manual plan vNN (app vX.YY)``) в ``COMPACT_SUMMARY.md``. Секция changelog
для новой версии добавляется заглушкой — текст изменений вписывает автор.

    python3 bump_version.py              # минор +1 и записать
    python3 bump_version.py --set v2.0   # явная версия
    python3 bump_version.py --dry-run    # показать diff, не писать
    python3 bump_version.py --check      # проверить синхронность (exit 1)
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

VERSION_RE = re.compile(r"^v(\d+)\.(\d+)$")
APP_VERSION_RE = re.compile(r'^(\s*VERSION = ")(v\d+\.\d+)(")', re.M)

# Файлы релиза в порядке обхода (docs рядом с кодом).
TARGETS = (
    "src/app.py",
    "README.md",
    "COMPACT_SUMMARY.md",
    "CLAUDE.md",
    "AGENTS.md",
    "test_cmd.md",
    "tests/test_cmd_scenarios.py",
    "DEMO.md",
)


class VersionBumpError(Exception):
    """Ошибка чтения/обновления версии (понятное сообщение для CLI)."""


def parse_version(text: str) -> tuple[int, int]:
    """``vMAJOR.MINOR`` → (major, minor). Иначе VersionBumpError."""
    match = VERSION_RE.match((text or "").strip())
    if not match:
        raise VersionBumpError(
            f"bad version {text!r}: expected vMAJOR.MINOR, e.g. v1.98"
        )
    return int(match.group(1)), int(match.group(2))


def format_version(major: int, minor: int) -> str:
    return f"v{major}.{minor}"


def next_minor(version: str) -> str:
    """``v1.97`` → ``v1.98`` (минор +1, мажор не трогаем)."""
    major, minor = parse_version(version)
    return format_version(major, minor + 1)


def read_current_version(root: Path) -> str:
    """Текущий ``VERSION`` из ``src/app.py``."""
    path = root / "src" / "app.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VersionBumpError(f"cannot read {path}: {exc}") from None
    match = APP_VERSION_RE.search(text)
    if not match:
        raise VersionBumpError(f"VERSION not found in {path}")
    return match.group(2)


def _sub_literal(text: str, pattern: str, literal: str) -> str:
    """Заменить первое совпадение шаблона на литерал (без backslash-сюрпризов)."""
    return re.sub(pattern, lambda _m: literal, text, count=1)


def _insert_changelog(text: str, new: str) -> str:
    """Вставить заглушку ``## <new>`` перед первой секцией changelog."""
    if f"## {new}" in text:
        return text
    stub = f"## {new}\n\n- TODO: описать изменения этого коммита.\n\n"
    match = re.search(r"^## v\d+\.\d+", text, re.M)
    if not match:
        tail = "\n" if text.endswith("\n") else "\n\n"
        return text + tail + stub.rstrip() + "\n"
    return text[: match.start()] + stub + text[match.start() :]


def plan_changes(root: Path, new: str, *, bump_doc: bool = True) -> dict[str, str]:
    """Спланировать правки: ``{relative_path: new_text}`` только для изменённых.

    ``new`` — целевая версия приложения; номер версии документа в
    ``test_cmd.md`` инкрементируется (когда ``bump_doc``), и то же число
    попадает в строку плана ``COMPACT_SUMMARY.md``.
    """
    new_next = next_minor(new)
    changes: dict[str, str] = {}

    def load(rel: str) -> str:
        try:
            return (root / rel).read_text(encoding="utf-8")
        except OSError as exc:
            raise VersionBumpError(f"cannot read {root / rel}: {exc}") from None

    def note(rel: str, old_text: str, new_text: str) -> None:
        if new_text != old_text:
            changes[rel] = new_text

    # src/app.py — единственное место, где VERSION хранится явно.
    rel = "src/app.py"
    text = load(rel)
    note(
        rel,
        text,
        re.sub(
            r'^(\s*VERSION = ")v\d+\.\d+(")',
            lambda m: f"{m.group(1)}{new}{m.group(2)}",
            text,
            count=1,
            flags=re.M,
        ),
    )

    rel = "README.md"
    text = load(rel)
    note(
        rel,
        text,
        re.sub(
            r"(\*\*IDvjPy_term\*\* )v\d+\.\d+( —)",
            lambda m: f"{m.group(1)}{new}{m.group(2)}",
            text,
            count=1,
        ),
    )

    # test_cmd.md — версия приложения и версия документа (+1).
    rel = "test_cmd.md"
    text = load(rel)
    new_text = re.sub(
        r"(# План тестирования IDvjPy_term )v\d+\.\d+",
        lambda m: f"{m.group(1)}{new}",
        text,
        count=1,
    )
    new_text = re.sub(
        r"(\*\*Версия приложения\*\*: )v\d+\.\d+",
        lambda m: f"{m.group(1)}{new}",
        new_text,
        count=1,
    )
    doc_holder: dict[str, str] = {}

    def _bump_doc(match: re.Match[str]) -> str:
        doc = format_version(int(match.group(2)), int(match.group(3)) + 1)
        doc_holder["new"] = doc
        return f"{match.group(1)}{doc}"

    if bump_doc:
        new_text = re.sub(
            r"(\*\*Версия документа\*\*: )v(\d+)\.(\d+)", _bump_doc, new_text, count=1
        )
    note(rel, text, new_text)
    new_doc = doc_holder.get("new")

    rel = "COMPACT_SUMMARY.md"
    text = load(rel)
    new_text = re.sub(
        r"(Версия: \*\*)v\d+\.\d+(\*\*\.)",
        lambda m: f"{m.group(1)}{new}{m.group(2)}",
        text,
        count=1,
    )
    new_text = re.sub(
        r"(\| `src/app.py` \| TUI \(`CommandRunner`\), )v\d+\.\d+( \|)",
        lambda m: f"{m.group(1)}{new}{m.group(2)}",
        new_text,
        count=1,
    )
    new_text = re.sub(
        r"(\(app )v\d+\.\d+(\))",
        lambda m: f"{m.group(1)}{new}{m.group(2)}",
        new_text,
        count=1,
    )
    if new_doc is not None:
        new_text = re.sub(
            r"(\| `test_cmd.md` \| Manual plan )v\d+\.\d+",
            lambda m: f"{m.group(1)}{new_doc}",
            new_text,
            count=1,
        )
    new_text = _insert_changelog(new_text, new)
    note(rel, text, new_text)

    # CLAUDE.md / AGENTS.md — текущая версия и инструкция «X → X+1».
    for rel in ("CLAUDE.md", "AGENTS.md"):
        text = load(rel)
        new_text = re.sub(
            r"(IDvjPy_term \()v\d+\.\d+(\))",
            lambda m: f"{m.group(1)}{new}{m.group(2)}",
            text,
            count=1,
        )
        new_text = _sub_literal(
            new_text, r"\(`v\d+\.\d+` → `v\d+\.\d+`\)", f"(`{new}` → `{new_next}`)"
        )
        note(rel, text, new_text)

    rel = "tests/test_cmd_scenarios.py"
    text = load(rel)
    note(
        rel,
        text,
        re.sub(
            r"(\(IDvjPy_term )v\d+\.\d+(\))",
            lambda m: f"{m.group(1)}{new}{m.group(2)}",
            text,
            count=1,
        ),
    )

    rel = "DEMO.md"
    text = load(rel)
    note(
        rel,
        text,
        re.sub(
            r"(Версия приложения: \*\*)v\d+\.\d+(\*\*)",
            lambda m: f"{m.group(1)}{new}{m.group(2)}",
            text,
            count=1,
        ),
    )

    return changes


def bump(
    root: Path, *, new_version: str | None = None, dry_run: bool = False
) -> tuple[str, dict[str, str]]:
    """Поднять/поставить версию и записать правки. Возвращает (new, changes)."""
    current = read_current_version(root)
    new = new_version.strip() if new_version else next_minor(current)
    parse_version(new)  # валидация до любых записей
    changes = plan_changes(root, new, bump_doc=(new != current))
    if not dry_run:
        for rel, text in changes.items():
            (root / rel).write_text(text, encoding="utf-8")
    return new, changes


def check(root: Path) -> list[tuple[str, str]]:
    """Проверить, что все файлы называют текущий VERSION. Список расхождений."""
    current = read_current_version(root)
    nxt = next_minor(current)
    required: list[tuple[str, str]] = [
        ("src/app.py", f'VERSION = "{current}"'),
        ("README.md", f"**IDvjPy_term** {current} —"),
        ("COMPACT_SUMMARY.md", f"Версия: **{current}**."),
        ("COMPACT_SUMMARY.md", f"| `src/app.py` | TUI (`CommandRunner`), {current} |"),
        ("COMPACT_SUMMARY.md", f"## {current}"),
        ("CLAUDE.md", f"IDvjPy_term ({current})"),
        ("CLAUDE.md", f"(`{current}` → `{nxt}`)"),
        ("AGENTS.md", f"(`{current}` → `{nxt}`)"),
        ("test_cmd.md", f"# План тестирования IDvjPy_term {current}"),
        ("test_cmd.md", f"**Версия приложения**: {current}"),
        ("tests/test_cmd_scenarios.py", f"(IDvjPy_term {current})"),
        ("DEMO.md", f"Версия приложения: **{current}**"),
    ]
    missing: list[tuple[str, str]] = []
    for rel, needle in required:
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except OSError as exc:
            missing.append((rel, f"cannot read: {exc}"))
            continue
        if needle not in text:
            missing.append((rel, needle))
    return missing


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _print_diff(root: Path, changes: dict[str, str]) -> None:
    for rel in sorted(changes):
        old_text = (root / rel).read_text(encoding="utf-8")
        diff = difflib.unified_diff(
            old_text.splitlines(keepends=True),
            changes[rel].splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
        sys.stdout.writelines(diff)
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bump_version",
        description="Bump CommandRunner.VERSION and sync the release docs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 bump_version.py\n"
            "  python3 bump_version.py --set v2.0\n"
            "  python3 bump_version.py --dry-run\n"
            "  python3 bump_version.py --check\n"
        ),
    )
    parser.add_argument(
        "--set",
        dest="set_version",
        metavar="vX.YY",
        help="set an explicit version instead of bumping the minor",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show the diff, write nothing"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the docs name the current VERSION; exit 1 on drift",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    try:
        if args.check:
            missing = check(root)
            if not missing:
                print("version markers consistent")
                return 0
            print("version markers out of sync:", file=sys.stderr)
            for rel, needle in missing:
                print(f"  {rel}: missing {needle!r}", file=sys.stderr)
            return 1

        current = read_current_version(root)
        new = args.set_version.strip() if args.set_version else next_minor(current)
        parse_version(new)
        changes = plan_changes(root, new, bump_doc=(new != current))
        if args.dry_run:
            print(f"{current} -> {new} (dry run, {len(changes)} file(s))")
            _print_diff(root, changes)
            return 0
        for rel, text in changes.items():
            (root / rel).write_text(text, encoding="utf-8")
        print(f"{current} -> {new}: updated {len(changes)} file(s)")
        for rel in sorted(changes):
            print(f"  {rel}")
        if "COMPACT_SUMMARY.md" in changes:
            print(f"note: fill in the changelog under '## {new}' in COMPACT_SUMMARY.md")
        return 0
    except VersionBumpError as exc:
        print(f"bump_version: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
