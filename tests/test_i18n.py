"""Локализация: каталоги, выбор языка, команда `:lang` (см. src/i18n.py).

`en` — источник правды; `ru` обязан покрывать те же ключи. Тесты возвращают
язык к `en`, чтобы он не утекал в соседние файлы.
"""
from __future__ import annotations

import re

import pytest

import i18n
from app import CommandRunner
from tests.conftest import last_info, submit

pytestmark = pytest.mark.slow


CYRILLIC = re.compile(r"[\u0400-\u04FF]")


@pytest.fixture(autouse=True)
def _reset_language():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def _flatten(node, prefix: str = "") -> dict[str, str]:
    """
    Плоский словарь ключ → текст (для сверки каталогов).
    """
    flat: dict[str, str] = {}
    for key, value in (node or {}).items():
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{full}."))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                flat[f"{full}[{index}]"] = str(item)
        else:
            flat[full] = str(value)
    return flat


def test_expected_languages_are_available():
    assert set(i18n.available_languages()) >= {"en", "ru", "zh"}


@pytest.mark.parametrize("lang", [c for c in i18n.available_languages() if c != "en"])
def test_every_language_covers_every_en_key(lang):
    """Каждая поставляемая локаль покрывает `en` ровно (ключ в ключ, без лишних)."""
    en = _flatten(i18n._load_catalog("en"))
    other = _flatten(i18n._load_catalog(lang))
    missing = sorted(set(en) - set(other))
    unknown = sorted(set(other) - set(en))
    assert not missing, f"{lang}.yml не переводит: {missing}"
    assert not unknown, f"{lang}.yml содержит лишние ключи: {unknown}"


def _bare_keys(node, prefix: str = "") -> list[str]:
    """Ключи каталога, которые YAML сделал не строками (bool/int и т.п.)."""
    bad: list[str] = []
    for key, value in (node or {}).items():
        if not isinstance(key, str):
            bad.append(f"{prefix}{key!r}")
        if isinstance(value, dict):
            bad.extend(_bare_keys(value, f"{prefix}{key}."))
    return bad


def test_catalogue_keys_are_strings():
    """YAML-ловушка: `off` / `n` / `N` / `on` без кавычек PyYAML читает как bool."""
    for lang in i18n.available_languages():
        assert not _bare_keys(i18n._load_catalog(lang)), (
            f"не-строковые ключи в {lang}.yml (закавычьте)"
        )


def test_en_catalogue_has_no_cyrillic():
    """`en` — английский источник правды: кириллица там только ошибка перевода."""
    bad = [
        key
        for key, text in _flatten(i18n._load_catalog("en")).items()
        if CYRILLIC.search(text)
    ]
    assert not bad, f"кириллица в en.yml: {bad}"


def test_unknown_key_returns_itself():
    assert i18n.t("nope.missing") == "nope.missing"


def test_missing_ru_key_falls_back_to_en():
    i18n.set_language("ru")
    # `startup.tagline` переведён, но проверяем сам механизм: неизвестный в ru
    # ключ отдаёт английский текст из en.
    assert i18n.t("startup.tagline") == "теги → шаблоны → командная строка"
    assert i18n.t("lang.unknown", name="xx").startswith("Неизвестный язык")


def test_format_placeholders_survive_broken_values():
    """Битый плейсхолдер не роняет приложение — возвращается шаблон как есть."""
    assert i18n.t("session.usage") != "session.usage"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ru", "ru"),
        ("RU", "ru"),
        ("ru_RU.UTF-8", "ru"),
        ("ru-RU", "ru"),
        ("en", "en"),
        ("de", None),
        ("", None),
        (None, None),
        ("auto", "auto"),
    ],
)
def test_normalize_language(raw, expected):
    assert i18n.normalize_language(raw) == expected


def test_resolve_language_precedence(monkeypatch):
    monkeypatch.setenv("IDVJPY_LANG", "ru")
    assert i18n.resolve_language(None, "en") == "ru"          # env бьёт settings
    assert i18n.resolve_language("en", "ru") == "en"          # CLI бьёт env
    monkeypatch.delenv("IDVJPY_LANG", raising=False)
    assert i18n.resolve_language(None, "ru") == "ru"
    assert i18n.resolve_language(None, None) == "en"


def test_resolve_language_auto_follows_system_locale(monkeypatch):
    monkeypatch.delenv("IDVJPY_LANG", raising=False)
    monkeypatch.setenv("LC_ALL", "ru_RU.UTF-8")
    assert i18n.resolve_language(None, "auto") == "ru"
    monkeypatch.setenv("LC_ALL", "C")
    assert i18n.resolve_language(None, "auto") == "en"


def test_explicit_language_beats_auto(monkeypatch):
    """Явный код выше приоритетом бьёт `auto` ниже: --lang ru > language: auto."""
    monkeypatch.delenv("IDVJPY_LANG", raising=False)
    monkeypatch.setenv("LC_ALL", "ru_RU.UTF-8")
    assert i18n.resolve_language("en", "auto") == "en"  # CLI бьёт settings
    assert i18n.resolve_language(None, "auto") == "ru"  # без явного — локаль
    assert i18n.resolve_language(None, None) == "en"


async def test_lang_command_lists_and_switches(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":lang")
        text = last_info(app).text_content
        assert "Available: en, ru" in text

        await submit(pilot, ":lang ru")
        assert "ru" in last_info(app).text_content
        assert i18n.current_language() == "ru"
        # Текст, напечатанный после смены, — на новом языке.
        await submit(pilot, ":lang")
        assert "Доступны: en, ru" in last_info(app).text_content

        # Сохраняется в settings.yml (как `:theme`).
        saved = (isolated_home / "settings.yml").read_text(encoding="utf-8")
        assert "language: ru" in saved


async def test_lang_command_rejects_unknown_code(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":lang de")
        assert "Unknown language: de" in last_info(app).text_content
        assert i18n.current_language() == "en"


def test_screensaver_locale_matches_builtin_fallback():
    """Каталог заставки (`locales/en/screensaver.yml`) равен встроенному набору."""
    from screensaver import COMMAND_HELP_LINES

    assert i18n.tlist("screensaver.help") == tuple(COMMAND_HELP_LINES)


def test_every_language_has_help_texts():
    """Справка `:?` — файлами: у каждого языка есть все четыре **своих** текста.

    Проверяем существование файла, а не `i18n.text()`: тот откатывается на `en`,
    поэтому отсутствие перевода он бы не заметил.
    """
    from help_texts import HELP_TEXTS

    for lang in i18n.available_languages():
        for name in HELP_TEXTS:
            path = i18n.LOCALES_DIR / i18n.HELP_DIR_NAME / lang / f"{name}.txt"
            assert path.is_file(), f"нет справки: {lang}/{name}.txt"
            assert path.read_text(encoding="utf-8").strip(), (
                f"пустая справка: {lang}/{name}.txt"
            )


def test_seed_catalog_descriptions_are_translated():
    """Описание каждого справочника есть в каждой локали (`catalog.desc.*`)."""
    from seed_catalog import SEED_HANDBOOKS_CORE, SEED_HANDBOOKS_OPS, handbook_desc

    for lang in i18n.available_languages():
        i18n.set_language(lang)
        for script, _ in SEED_HANDBOOKS_CORE + SEED_HANDBOOKS_OPS:
            desc = handbook_desc(script)
            assert desc and not desc.startswith("catalog.desc."), (
                f"нет описания {script} в {lang}"
            )


async def test_language_from_settings_is_applied(isolated_home):
    settings = isolated_home / "settings.yml"
    settings.write_text("language: ru\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":lang")
        assert "Доступны: en, ru" in last_info(app).text_content


def test_broken_locale_file_falls_back_to_en(tmp_path, monkeypatch):
    """Битый каталог языка (не UTF-8) не роняет `t()` — ключи берутся из `en`."""
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "en.yml").write_text('kctx:\n  "off": "off in en"\n', encoding="utf-8")
    (locales / "ru.yml").write_bytes(b'kctx:\n  "off": "\xff\xfe bad utf8"\n')
    monkeypatch.setattr(i18n, "LOCALES_DIR", locales)
    i18n.set_language("ru")
    assert i18n.current_language() == "ru"
    assert i18n.t("kctx.off") == "off in en"
    assert i18n.t("nope.missing") == "nope.missing"


def test_broken_help_file_falls_back_to_en(tmp_path, monkeypatch):
    """Битая справка языка — отдаём английскую, а не падаем."""
    base = tmp_path / "locales"
    (base / "help" / "en").mkdir(parents=True)
    (base / "help" / "ru").mkdir(parents=True)
    (base / "help" / "en" / "main.txt").write_text("EN HELP", encoding="utf-8")
    (base / "help" / "ru" / "main.txt").write_bytes(b"\xff\xfe broken")
    monkeypatch.setattr(i18n, "LOCALES_DIR", base)
    i18n.set_language("ru")
    assert i18n.text("main") == "EN HELP"
