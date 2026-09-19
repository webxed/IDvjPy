"""Тексты сидов по языкам (`seed_text/<lang>/*.yml`, см. src/seed_text/README.md).

Проверяем три вещи: перевод покрывает **все** встроенные комментарии, в `en`
нет кириллицы, и откат к встроенному тексту работает (язык без файлов).
"""
from __future__ import annotations

import importlib
import pathlib
import re

import pytest
import yaml

import seed_lib
from seed_lib import SEED_TEXT_DIR, load_seed_text, localized_comment, localized_tags

CYRILLIC = re.compile(r"[\u0400-\u04FF]")
# Не хэндбуки: библиотека, каталог `:welcome`, группировка, сводный `seed_ops`.
HELPER_MODULES = {"lib", "catalog", "groups", "ops"}


@pytest.fixture(autouse=True)
def _fresh_text_cache():
    seed_lib.reset_seed_text_cache()
    yield
    seed_lib.reset_seed_text_cache()


def _inline_comments() -> dict[tuple[str, int | None], str]:
    """Встроенные комментарии сидов: `(тег, позиция|None)` → текст."""
    out: dict[tuple[str, int | None], str] = {}
    src = pathlib.Path(seed_lib.__file__).parent
    for path in sorted(src.glob("seed_*.py")):
        if path.stem[5:] in HELPER_MODULES:
            continue
        mod = importlib.import_module(path.stem)
        if hasattr(mod, "SEED_TAGS"):
            for tag, (tag_comment, commands) in mod.SEED_TAGS.items():
                if tag_comment:
                    out[(tag, None)] = tag_comment
                for index, (_, comment) in enumerate(commands):
                    if comment:
                        out[(tag, index)] = comment
            continue
        if hasattr(mod, "SEED_COMMANDS"):  # linux: канонические + extra-комментарии
            for tag in mod.SEED_COMMANDS:
                tag_comment = mod.TAG_COMMENTS.get(tag, "")
                if tag_comment:
                    out[(tag, None)] = tag_comment
                for index, (_, comment) in enumerate(mod._seed_items(tag)):
                    if comment:
                        out[(tag, index)] = comment
            for (tag, tid), comment in mod.EXTRA_COMMENTS.items():
                out[(tag, tid - 1)] = comment
            logs_comment = mod.TAG_COMMENTS.get("logs", "")
            if logs_comment:
                out[("logs", None)] = logs_comment
    return out


def _en_files() -> list[pathlib.Path]:
    return sorted((SEED_TEXT_DIR / "en").glob("*.yml"))


def test_en_seed_text_covers_every_inline_comment():
    index = load_seed_text("en")
    missing: list[str] = []
    for (tag, position), _comment in _inline_comments().items():
        block = index.get(tag) or {}
        if position is None:
            if not str(block.get("comment") or "").strip():
                missing.append(f"{tag} (tag comment)")
            continue
        commands = block.get("commands") or {}
        if not str(commands.get(position) or "").strip():
            missing.append(f"{tag}[{position}]")
    assert not missing, f"нет английского текста: {sorted(missing)}"


def test_en_seed_text_has_no_cyrillic():
    bad: list[str] = []
    for path in _en_files():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for tag, block in (data.get("tags") or {}).items():
            texts = [block.get("comment")]
            texts.extend((block.get("commands") or {}).values())
            for text in texts:
                if text and CYRILLIC.search(str(text)):
                    bad.append(f"{path.name}:{tag}: {text}")
    assert not bad, f"кириллица в seed_text/en: {bad}"


def test_every_tag_lives_in_exactly_one_file():
    seen: dict[str, str] = {}
    clashes: list[str] = []
    for path in _en_files():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for tag in (data.get("tags") or {}):
            if tag in seen:
                clashes.append(f"{tag}: {seen[tag]} + {path.name}")
            seen[tag] = path.name
    assert not clashes, f"тег встречается дважды (индекс перезапишется): {clashes}"


def test_unknown_language_falls_back_to_inline_text():
    assert localized_comment("git", 1, "встроенный", "zz") == "встроенный"
    tags = {"git": ("встроенный тег", [("git status -sb", "встроенный")])}
    assert localized_tags(tags, "zz") == tags


def test_seed_language_comes_from_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("IDVJPY_LANG", raising=False)
    (tmp_path / "settings.yml").write_text("language: ru\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    seed_lib.reset_seed_text_cache()
    assert seed_lib.resolve_seed_language() == "ru"
    # Для ru файлов нет — значит остаётся встроенный (базовый) текст.
    assert localized_comment("git", 1, "встроенный", "ru") == "встроенный"

    (tmp_path / "settings.yml").write_text("language: en\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    seed_lib.reset_seed_text_cache()
    assert seed_lib.resolve_seed_language() == "en"
    assert localized_comment("git", 1, "") == "short status"


def test_broken_seed_text_file_is_skipped(tmp_path, monkeypatch):
    """Битый файл языка (не UTF-8 / сломанный YAML) пропускается, а не роняет сид."""
    directory = tmp_path / "en"
    directory.mkdir()
    (directory / "broken.yml").write_bytes(b"\xff\xfe not utf8")
    (directory / "worse.yml").write_text("tags: [\n", encoding="utf-8")
    (directory / "ok.yml").write_text(
        'tags:\n  git:\n    comment: "ok"\n', encoding="utf-8"
    )
    monkeypatch.setattr(seed_lib, "SEED_TEXT_DIR", tmp_path)
    seed_lib.reset_seed_text_cache()
    index = seed_lib.load_seed_text("en")
    assert (index.get("git") or {}).get("comment") == "ok"
    # Откат тоже работает: неизвестный тег отдаёт встроенный комментарий.
    assert seed_lib.localized_tag_comment("nope", "fallback") == "fallback"
